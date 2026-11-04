"""The Facebook publisher's behaviour — the parts a workflow test cannot see.

`test_workflow_contract.py` proves the YAML is wired in the right order. What it
cannot prove is the half that made the October Telegram outage expensive: a step
that exits 0 having published nothing, an error message thrown away, a field the
API ignores. So these tests drive `scripts/post_facebook.py` and
`tools/fb_publish.py` against a fake Graph API and assert the observable
contract:

  * what was sent, to which endpoint, with which field names;
  * that a rejected photo still produces the day's text post;
  * that an already-posted day is skipped as *success* (so it opens no issue),
    while a run that published nothing exits non-zero (so it does);
  * that a credential never reaches a log line, not even as a prefix.

The copy itself is covered in `test_de_escaping_leaves_no_markup`: the templates
are written for Telegram's MarkdownV2, and Facebook publishes whatever it is
given, so an unstripped `\\.` or `*` would appear on the Page verbatim.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for rel in ("tools", "scripts"):
    if str(ROOT / rel) not in sys.path:
        sys.path.insert(0, str(ROOT / rel))

# The social scripts append to `logs/social_media.log`, and importing them binds that
# path. Redirected before the import so the repo's real log stays a record of publishes
# rather than a record of tests — see tools/docoga_log.py.
os.environ.setdefault("DOCOGA_LOG_DIR", tempfile.mkdtemp(prefix="docoga-social-log-"))


import fb_publish  # noqa: E402
import generate_facebook_content  # noqa: E402
import post_facebook  # noqa: E402
import social_card  # noqa: E402
from PIL import Image  # noqa: E402

TOKEN = "EAAB" + "x" * 60          # shaped like a real token; never printed
PAGE = "102466208923830"


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON")
        return self._payload


def ok(payload=None):
    return FakeResponse(payload if payload is not None else {"id": "%s_1" % PAGE})


def api_error(code, message, status=400, **extra):
    body = {"error": dict(message=message, type="OAuthException", code=code, **extra)}
    return FakeResponse(body, status)


class Graph:
    """Records every call and answers from a queue keyed by (method, path tail)."""

    def __init__(self, replies=None):
        self.calls = []
        self.replies = replies or {}
        self.default = ok()

    def _reply_for(self, url, data, files, method):
        for key, reply in self.replies.items():
            if key in url:
                if callable(reply):
                    return reply(url, data, files, method)
                return reply
        return self.default

    def request(self, method, url, **kwargs):
        data = kwargs.get("data")
        files = kwargs.get("files")
        self.calls.append({"method": method, "url": url, "data": data, "files": files,
                          "params": kwargs.get("params")})
        return self._reply_for(url, data, files, method)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def urls(self, method=None):
        return [c["url"] for c in self.calls if method is None or c["method"] == method]


class Base(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"FB_PAGE_ACCESS_TOKEN": TOKEN, "FB_PAGE_ID": PAGE}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def card(self, text):
        """A real brand card in a temp dir — the only kind of photo the lane may post."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "card.jpg"
        with redirect_stdout(io.StringIO()):
            social_card.render(text, out, kicker="test")
        return out

    def run_poster(self, graph, argv=()):
        with patch.object(fb_publish.requests, "get", graph.get), \
             patch.object(fb_publish.requests, "post", graph.post), \
             patch.object(fb_publish.requests, "delete", graph.delete), \
             redirect_stdout(io.StringIO()) as out:
            code = post_facebook.main(list(argv))
        return code, out.getvalue()


class PostingTests(Base):
    def test_a_text_post_goes_to_the_feed_with_message(self):
        graph = Graph({"/feed": ok({"id": "PAGE_99"})})
        code, log = self.run_poster(graph, ["--date", "2026-10-12", "--text", "Rent receipt, no lawyer fees"])
        self.assertEqual(code, 0, log)
        posts = [c for c in graph.calls if c["method"] == "POST" and "/feed" in c["url"]]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["data"]["message"], "Rent receipt, no lawyer fees")
        self.assertNotIn("link", posts[0]["data"],
                         "sending `link` alongside `message` makes Facebook render a "
                         "link card and drop the copy — the URL belongs in the text")

    def test_a_photo_post_sends_caption_not_message(self):
        """The silent one: `message` on /photos is accepted and ignored, so the
        photo went out with no words and the run was green."""
        graph = Graph({"/photos": ok({"id": "p1", "post_id": "PAGE_p1"})})
        photo = self.card("Nine tools, one page")
        code, log = self.run_poster(graph, ["--date", "2026-10-12", "--text", "Nine tools, one page",
                                            "--photo-file", str(photo)])
        self.assertEqual(code, 0, log)
        posts = [c for c in graph.calls if c["method"] == "POST" and "/photos" in c["url"]]
        self.assertTrue(posts, "expected a photo upload: %s" % log)
        self.assertIn("caption", posts[0]["data"])
        self.assertNotIn("message", posts[0]["data"])
        self.assertEqual(posts[0]["data"]["caption"], "Nine tools, one page")
        self.assertIn("source", posts[0]["files"], "the bytes must be uploaded, not fetched by URL")

    def test_a_refused_photo_still_posts_the_words(self):
        graph = Graph({"/photos": api_error(353, "Unexpected image data"), "/feed": ok({"id": "PAGE_2"})})
        photo = self.card("Notice to quit in minutes")
        code, log = self.run_poster(graph, ["--date", "2026-10-12", "--text", "Notice to quit in minutes",
                                            "--photo-file", str(photo)])
        self.assertEqual(code, 0, log)
        self.assertIn("photo post refused", log)
        self.assertIn("falling back to a text post", log)
        self.assertTrue(any("/feed" in u for u in graph.urls("POST")), "the text fallback must fire")
        self.assertIn("353", log, "Meta's own error code belongs in the log, not only the run body")

    def test_a_brand_folder_photo_is_refused_before_it_reaches_the_page(self):
        graph = Graph({"/photos": ok({"id": "p1", "post_id": "PAGE_p1"}), "/feed": ok({"id": "PAGE_3"})})
        code, log = self.run_poster(graph, ["--date", "2026-10-12", "--text", "Rent receipt, no lawyer fees",
                                            "--photo-file", "brand/comparison.png"])
        self.assertEqual(code, 0, log)
        self.assertFalse(any("/photos" in u for u in graph.urls("POST")), "brand/ must never be uploaded")
        self.assertTrue(any("/feed" in u for u in graph.urls("POST")), "the words still go out")
        self.assertIn("not post art", log)

    def test_a_missing_photo_file_is_not_a_failed_day(self):
        graph = Graph({"/feed": ok({"id": "PAGE_3"})})
        code, log = self.run_poster(graph, ["--date", "2026-10-12", "--text", "Today's copy",
                                            "--photo-file", "assets/facebook/does-not-exist.jpg"])
        self.assertEqual(code, 0, log)
        self.assertIn("not found", log)

    def test_a_run_that_posts_nothing_fails_loudly(self):
        graph = Graph({"/feed": api_error(200, "(#200) Permission failed", error_subcode=534)})
        code, log = self.run_poster(graph, ["--date", "2026-10-12", "--text", "Today's copy"])
        self.assertEqual(code, 3, "a red run is the only signal that nothing was published")
        self.assertIn("Facebook refused", log)
        self.assertIn("200", log)
        self.assertIn("534", log, "the subcode is what identifies a missing pages_manage_posts grant")

    def test_the_graph_api_version_and_host_are_used(self):
        graph = Graph({"/feed": ok()})
        self.run_poster(graph, ["--date", "2026-10-12", "--text", "hi"])
        post_url = graph.urls("POST")[-1]
        self.assertTrue(post_url.startswith("https://graph.facebook.com/v"))
        self.assertRegex(post_url, r"/v\d{2}\.0/%s/feed$" % PAGE)
        self.assertEqual(fb_publish.API_VERSION, post_url.split("/graph.facebook.com/")[1].split("/")[0])

    def test_a_video_post_uses_the_video_host(self):
        graph = Graph({"/videos": ok({"id": "v1"})})
        code, log = self.run_poster(graph, ["--date", "2026-10-12", "--text", "Watch this"])
        # the poster's daily path never posts video; that is fb_publish's job
        del code, log
        with patch.object(fb_publish.requests, "post", graph.post), redirect_stdout(io.StringIO()):
            okflag, res = fb_publish.post_video(TOKEN, PAGE, "https://example.com/a.mp4", "T", "D")
        self.assertTrue(okflag, res)
        self.assertIn("graph-video.facebook.com", graph.urls("POST")[-1])


class DuplicateGuardTests(Base):
    def test_a_day_already_posted_is_skipped_as_success(self):
        today = date.today().isoformat()
        graph = Graph({"/feed": lambda url, data, files, method:
                       ok({"data": [{"id": "x", "created_time": today + "T07:30:00+0000",
                                     "status": "published"}]}) if method == "GET" else ok()})
        code, log = self.run_poster(graph, ["--date", today])
        self.assertEqual(code, 0, "skipping is not a failure — a failure opens an issue")
        self.assertIn("skipped", log)
        self.assertFalse([u for u in graph.urls("POST")], "nothing may be published")

    def test_a_reel_earlier_today_does_not_cost_the_card(self):
        """4 Nov 2026: a made-up Short became a Reel at 9:16am and the 9:30am card stood down."""
        today = date.today().isoformat()
        graph = Graph({"/photos": ok({"id": "p1", "post_id": "PAGE_p1"}), "/comments": ok({"id": "c"}),
                       "/feed": lambda url, data, files, method:
                       ok({"data": [{"id": "x", "created_time": today + "T08:16:00+0000", "status": "published",
                                     "status_type": "added_video"}]}) if method == "GET" else ok({"id": "new"})})
        code, log = self.run_poster(graph, ["--date", today])
        self.assertEqual(code, 0, log)
        self.assertNotIn("skipped", log)
        self.assertTrue(any(u.endswith("/photos") for u in graph.urls("POST")), "the card still goes out")
        feed_reads = [c for c in graph.calls if c["method"] == "GET" and c["url"].endswith("/feed")]
        self.assertIn("status_type", feed_reads[0]["params"]["fields"])
        # …but a card already there today still stands the run down.
        graph = Graph({"/feed": lambda url, data, files, method:
                       ok({"data": [{"id": "x", "created_time": today + "T08:31:00+0000", "status": "published",
                                     "status_type": "added_photos"}]}) if method == "GET" else ok()})
        code, log = self.run_poster(graph, ["--date", today])
        self.assertEqual(code, 0)
        self.assertIn("skipped", log)
        self.assertFalse(graph.urls("POST"))

    def test_force_overrides_the_guard(self):
        today = date.today().isoformat()
        graph = Graph({"/feed": lambda url, data, files, method:
                       ok({"data": [{"id": "x", "created_time": today + "T07:30:00+0000",
                                     "status": "published"}]}) if method == "GET" else ok({"id": "new"})})
        code, log = self.run_poster(graph, ["--date", today, "--text", "on purpose", "--force"])
        self.assertEqual(code, 0, log)
        self.assertTrue([u for u in graph.urls("POST") if "/feed" in u])

    def test_a_blind_guard_posts_anyway_and_says_so(self):
        """If the feed cannot be read, publishing beats silence — but the run must
        say the guard was blind, or a double post looks like a random bug."""
        graph = Graph({"/feed": lambda url, data, files, method:
                       api_error(190, "invalid token") if method == "GET" else ok({"id": "new"})})
        code, log = self.run_poster(graph, ["--date", "2026-10-12"])
        self.assertEqual(code, 0, log)
        self.assertIn("duplicate guard could not read the feed", log)

    def test_an_explicit_message_is_a_human_asking_so_the_guard_stands_aside(self):
        """`--text` on the daily path is a deliberate post, like `--force`; the
        once-a-day guard exists for the unattended run, not for the owner."""
        graph = Graph({"/feed": ok({"data": [{"id": "x", "created_time": "2026-10-12T07:30:00+0000",
                                             "status": "published"}]})})
        code, log = self.run_poster(graph, ["--date", "2026-10-12", "--text", "One more, on purpose"])
        self.assertEqual(code, 0, log)
        self.assertTrue([u for u in graph.urls("POST") if "/feed" in u])
        self.assertNotIn("duplicate guard could not read", log)

    def test_an_early_morning_lagos_post_is_still_today(self):
        """23:30 UTC is 00:30 in Lagos the next day; comparing raw UTC dates would
        let a second post through an hour after the first."""
        from datetime import datetime, timedelta, timezone
        lagos = timezone(timedelta(hours=1))
        now_lagos = datetime(2026, 10, 12, 0, 30, tzinfo=lagos)
        utc_stamp = now_lagos.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")
        self.assertEqual(utc_stamp[:10], "2026-10-11", "the UTC date really is the day before")
        graph = Graph({"/feed": ok({"data": [{"id": "x", "created_time": utc_stamp, "status": "published"}]})})
        with patch.object(fb_publish.requests, "get", graph.get):
            guard, detail = fb_publish.posted_on_date(TOKEN, PAGE, when=now_lagos.date())
        self.assertTrue(guard, detail)


class CredentialHygieneTests(Base):
    def test_the_token_is_never_printed_not_even_a_prefix(self):
        printed = fb_publish.fingerprint(TOKEN)
        self.assertNotIn(TOKEN[:6], printed)
        self.assertIn(str(len(TOKEN)), printed)
        self.assertTrue(printed.startswith("sha256:"))

    def test_an_error_body_that_echoes_the_token_is_redacted(self):
        body = {"error": {"message": "invalid token %s" % TOKEN, "type": "OAuthException", "code": 190}}
        response = FakeResponse(body)
        line = fb_publish._error_line(response)
        self.assertNotIn(TOKEN, line)
        self.assertIn("[token redacted]", line)

    def test_no_secret_shaped_default_exists_in_the_source(self):
        """Regression: this file used to default META_APP_SECRET, which put the
        app secret in git history. Deleting the line is not enough — it must be
        rotated — but the default must not come back."""
        src = (ROOT / "tools" / "fb_publish.py").read_text(encoding="utf-8")
        for name in ("META_APP_SECRET", "META_APP_ID", "FB_PAGE_ACCESS_TOKEN", "FB_PAGE_ID"):
            self.assertNotIn('environ.get("%s", "' % name, src, "%s must have no default" % name)
            self.assertNotIn('os.environ.get("%s", "' % name, src)

    def test_missing_configuration_names_both_secrets_and_exits_2(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as caught, redirect_stdout(io.StringIO()) as out:
                fb_publish.load_config()
        self.assertEqual(caught.exception.code, 2)
        text = out.getvalue()
        self.assertIn("FB_PAGE_ACCESS_TOKEN", text)
        self.assertIn("FB_PAGE_ID", text)


class ContentTests(unittest.TestCase):
    """The copy Facebook will actually show."""

    def generate(self, day):
        """generate() logs to stdout and to logs/; the assertion here is about the
        dict, so the run stays quiet."""
        with redirect_stdout(io.StringIO()):
            return generate_facebook_content.generate(day, write=False)

    def test_de_escaping_leaves_no_markup(self):
        gen = generate_facebook_content
        problems = []
        for post_type, templates in gen.tg.TEMPLATES.items():
            for index, template in enumerate(templates):
                plain = gen.to_plain(template)
                for marker in ("\\", "*", "||"):
                    if marker in plain:
                        problems.append("%s[%d] keeps %r" % (post_type, index, marker))
                if len(plain.strip()) < 40:
                    problems.append("%s[%d] de-escapes to almost nothing" % (post_type, index))
        self.assertFalse(problems, "the templates are shared with Telegram; Facebook has no markup to "
                                   "interpret, so anything left behind is published literally:\n  "
                                   + "\n  ".join(problems))

    def test_the_same_date_yields_the_same_post(self):
        a = self.generate(date(2026, 10, 14))
        b = self.generate(date(2026, 10, 14))
        self.assertEqual(a["message"], b["message"])
        self.assertEqual(a["photo_path"], b["photo_path"])
        self.assertEqual(a["post_type"], b["post_type"])

    def test_a_week_is_seven_different_days_not_one_template(self):
        types = {self.generate(date(2026, 10, day))["post_type"]
                 for day in range(12, 19)}
        self.assertGreaterEqual(len(types), 3, "the weekday rotation must survive the port")

    def test_the_hashtag_block_is_appended_plain(self):
        content = self.generate(date(2026, 10, 14))
        self.assertIn("#DocOga", content["message"])
        self.assertNotIn("\\#", content["message"], "hashtags need no escaping outside MarkdownV2")

    def test_the_photo_is_the_rendered_brand_card_never_a_brand_file(self):
        """Owner, 15 Oct 2026, looking at brand/comparison.png on the Page: "this is
        not my brand style". The photo is now the day's copy on the navy card."""
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(generate_facebook_content, "ASSETS_DIR", Path(tmp)), \
             redirect_stdout(io.StringIO()):
            content = generate_facebook_content.generate(date(2026, 10, 15), write=True)
            self.assertTrue(content["send_photo"])
            self.assertTrue(content["photo_path"].endswith("facebook_card_2026-10-15.jpg"))
            self.assertFalse(social_card.is_banned_photo(content["photo_path"]))
            path = Path(content["photo_path"])
            self.assertTrue(path.exists())
            size = path.stat().st_size
            self.assertGreaterEqual(size, generate_facebook_content.MIN_PHOTO_BYTES)
            self.assertLessEqual(size, generate_facebook_content.MAX_PHOTO_BYTES)
            with Image.open(path) as im:
                self.assertEqual(im.size, (social_card.CARD_W, social_card.CARD_H))
                self.assertEqual(im.format, "JPEG")
                # navy ground at the corner — the brand card, not a white logo sheet
                r, g, b = im.convert("RGB").getpixel((10, 10))
                self.assertLess(r + g + b, 120, "the card ground must be the deep navy")

    def test_the_generator_no_longer_knows_the_brand_folder(self):
        source = (ROOT / "scripts" / "generate_facebook_content.py").read_text(encoding="utf-8")
        self.assertNotIn("FB_PHOTO_IMAGES", source)
        self.assertNotIn("brand/official", source)
        self.assertNotIn("brand/comparison", source)
        tg_source = (ROOT / "scripts" / "generate_telegram_content.py").read_text(encoding="utf-8")
        self.assertNotIn("PHOTO_POST_IMAGES", tg_source)
        self.assertNotIn("brand/comparison", tg_source)

    def test_a_brand_file_handed_in_by_hand_is_refused_and_the_words_still_post(self):
        for rel in ("brand/comparison.png", "brand/official-4.png", str(ROOT / "brand" / "logo-primary.png")):
            self.assertTrue(social_card.is_banned_photo(rel), rel)
        self.assertFalse(social_card.is_banned_photo("assets/facebook/facebook_card_2026-10-15.jpg"))

    def test_the_link_is_in_the_copy(self):
        for day in range(12, 19):
            content = self.generate(date(2026, 10, day))
            message = content["message"]
            if content["post_type"] == "deepdive":
                # 17 Oct 2026: the day after a Deep-Dive goes public the post is the episode's
                # trailer and its one link is the YouTube URL (lifted into the first comment).
                self.assertIn("https://www.youtube.com/watch?v=", message)
                continue
            self.assertIn("https://docoga.com.ng", message,
                          "there is no `link` field on the request, so the URL must be in the text")



class LinkInFirstCommentTests(Base):
    """17 Oct 2026: the body is link-free, the first comment carries the link — or the post is edited to."""

    def test_the_daily_post_puts_the_link_in_the_first_comment(self):
        graph = Graph({"/comments": ok({"id": "PAGE_p1_c1"}), "/photos": ok({"id": "p1", "post_id": "PAGE_p1"}),
                       "/feed": lambda url, data, files, method: ok({"data": []}) if method == "GET" else ok({"id": "PAGE_t1"})})
        code, log = self.run_poster(graph, ["--date", "2026-10-13", "--force"])
        self.assertEqual(code, 0, log)
        published = [c for c in graph.calls if c["method"] == "POST" and ("/photos" in c["url"] or c["url"].endswith("/feed"))]
        self.assertTrue(published, log)
        words = published[0]["data"].get("caption") or published[0]["data"].get("message")
        self.assertNotIn("https://docoga.com.ng", words, "the body must be native — a link in the body costs ~75% of reach")
        self.assertIn("#DocOga", words, "the hashtags stay with the words")
        comments = [c for c in graph.calls if c["method"] == "POST" and "/comments" in c["url"]]
        self.assertEqual(len(comments), 1, log)
        self.assertIn("https://docoga.com.ng", comments[0]["data"]["message"])
        self.assertIn("?s=fb", comments[0]["data"]["message"], "the link keeps its channel tag")
        self.assertIn("FB_LINK=comment", log)
        # 4 Nov 2026: the first comment opens with one answerable question — the conversation
        # starter — and the link line follows it.
        first = comments[0]["data"]["message"]
        self.assertTrue(first.split("\n")[0].rstrip().endswith("?"), first)
        self.assertLess(first.index("?"), first.index("https://"), "question first, link second")
        self.assertNotRegex(first.lower(), r"\b(like|share|follow)\b.*\bif\b", "never bait")

    def test_without_the_comment_permission_the_post_is_edited_to_carry_the_link(self):
        graph = Graph({"/comments": api_error(200, "(#200) Requires pages_manage_engagement", status=403),
                       "/photos": ok({"id": "p1", "post_id": "PAGE_p1"}),
                       "/feed": lambda url, data, files, method: ok({"data": []}) if method == "GET" else ok({"id": "PAGE_t1"})})
        code, log = self.run_poster(graph, ["--date", "2026-10-13", "--force"])
        self.assertEqual(code, 0, log)
        edits = [c for c in graph.calls if c["method"] == "POST" and c["url"].endswith("/PAGE_p1")]
        self.assertEqual(len(edits), 1, "the post itself is edited so the day keeps its link: %s" % log)
        self.assertIn("https://docoga.com.ng", edits[0]["data"]["message"])
        self.assertIn("FB_LINK=body", log)
        self.assertIn("pages_manage_engagement", log)

    def test_the_switch_restores_the_old_shape(self):
        graph = Graph({"/photos": ok({"id": "p1", "post_id": "PAGE_p1"}),
                       "/feed": lambda url, data, files, method: ok({"data": []}) if method == "GET" else ok({"id": "PAGE_t1"})})
        with patch.dict(os.environ, {"FB_LINK_IN_COMMENT": "off"}):
            code, log = self.run_poster(graph, ["--date", "2026-10-13", "--force"])
        self.assertEqual(code, 0, log)
        self.assertFalse([c for c in graph.calls if "/comments" in c["url"]])
        published = [c for c in graph.calls if c["method"] == "POST" and ("/photos" in c["url"] or c["url"].endswith("/feed"))]
        self.assertIn("https://docoga.com.ng", published[0]["data"].get("caption") or published[0]["data"].get("message"))

    def test_split_link_leaves_an_inline_link_alone(self):
        self.assertEqual(fb_publish.split_link("Read https://docoga.com.ng today."), ("Read https://docoga.com.ng today.", None))
        body, link = fb_publish.split_link("Words.\n\n👉 https://docoga.com.ng/x.html?s=fb\n\n#DocOga")
        self.assertEqual((body, link), ("Words.\n\n#DocOga", "https://docoga.com.ng/x.html?s=fb"))

if __name__ == "__main__":
    unittest.main()


class FirstQuestionTests(unittest.TestCase):
    def test_the_brains_question_wins_else_the_rotation_offset_from_instagrams(self):
        import reel_caption
        day = date(2026, 11, 4)
        self.assertEqual(post_facebook.first_question(day, {"post": {"cta": "Which state is your rent in?"}}), "Which state is your rent in?")
        self.assertIn(post_facebook.first_question(day, {"post": {"cta": "Send this to a friend."}}), reel_caption.QUESTIONS)
        self.assertNotEqual(post_facebook.first_question(day, None), reel_caption.first_comment(day).split("\n")[0],
                            "Facebook and Instagram never ask the same question on the same day")
        self.assertEqual(fb_publish.link_line("https://docoga.com.ng/x?s=fb", "Who collected your last rent?"),
                         "Who collected your last rent?\n\nThe page, free to start: https://docoga.com.ng/x?s=fb")
        self.assertEqual(fb_publish.link_line("https://docoga.com.ng/x?s=fb", ""), "The page, free to start: https://docoga.com.ng/x?s=fb")


class NativeVideoTests(Base):
    """4 Nov 2026: the Deep-Dive feature day uploads the episode itself (`/videos`, multipart
    `source`), sets the cover as the thumbnail, puts the links in the first comment — and any
    refusal falls back to the card, so the day is never lost to the new path."""

    VIDEO = {"episode": "dd3", "title": "T (Deep-Dive 3)", "youtube": "https://www.youtube.com/watch?v=NEW",
             "file_url": "https://github.com/johnAzani/docoga/releases/download/deepdive-dd3/dd3-episode.mp4",
             "cover_url": "https://github.com/johnAzani/docoga/releases/download/deepdive-dd3/dd3-cover.jpg",
             "description": "🎬 Deep-Dive 3 (9 minutes): T\n\nHook.\n\nWhich part should I break down? #DocOga",
             "comment": "▶ Also on YouTube: https://www.youtube.com/watch?v=NEW\n📄 Transcript: https://docoga.com.ng/videos/dd3.html?s=fb"}

    def content(self, day="2026-10-20"):
        card = self.card("T\n• a")
        return {"date": day, "post_type": "deepdive", "send_photo": True, "photo_path": str(card),
                "message": "🎬 New Deep-Dive (9 minutes): T\n\nWatch the full episode on YouTube:\nhttps://www.youtube.com/watch?v=NEW\n\n#DocOga",
                "video": dict(self.VIDEO)}

    def run_native(self, graph, content, fetch_ok=True, env=None, argv=("--date", "2026-10-20", "--force")):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        def fetch(url, dest, max_bytes=None, http=None):
            if not fetch_ok:
                return False, "HTTP 404 fetching %s" % url
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b"\x00" * 2048)
            return True, str(dest)

        with patch.object(post_facebook, "load_today", lambda day: (content, "test")), \
             patch.object(post_facebook, "ASSETS_DIR", Path(tmp.name)), \
             patch.object(fb_publish, "fetch_file", fetch), \
             patch.dict(os.environ, env or {}, clear=False):
            return self.run_poster(graph, argv)

    def test_the_feature_day_uploads_the_episode_natively_with_cover_and_first_comment(self):
        graph = Graph({"/videos": lambda url, data, files, method: ok({"data": []}) if method == "GET" else ok({"id": "V1"}),
                       "/V1/thumbnails": ok({"success": True}),
                       "/comments": ok({"id": "V1_c1"}),
                       "/feed": lambda url, data, files, method: ok({"data": []}) if method == "GET" else ok({"id": "PAGE_t1"})})
        code, log = self.run_native(graph, self.content())
        self.assertEqual(code, 0, log)
        uploads = [c for c in graph.calls if c["method"] == "POST" and c["url"].endswith("/%s/videos" % PAGE)]
        self.assertEqual(len(uploads), 1, log)
        up = uploads[0]
        self.assertTrue(up["url"].startswith(fb_publish.GRAPH_VIDEO), "uploads go to graph-video.facebook.com")
        self.assertIn("source", up["files"], "the bytes travel as multipart `source`")
        self.assertEqual(up["data"]["title"], "T (Deep-Dive 3)")
        self.assertEqual(up["data"]["description"], self.VIDEO["description"])
        self.assertNotIn("http", up["data"]["description"], "no link in the body")
        self.assertNotIn("/photos", "".join(graph.urls("POST")), "the card was not posted as well")
        thumbs = [c for c in graph.calls if c["url"].endswith("/V1/thumbnails")]
        self.assertEqual(len(thumbs), 1, "the episode cover becomes the preferred thumbnail")
        self.assertEqual(thumbs[0]["data"]["is_preferred"], "true")
        self.assertIn("source", thumbs[0]["files"])
        comments = [c for c in graph.calls if c["method"] == "POST" and c["url"].endswith("/V1/comments")]
        self.assertEqual(len(comments), 1, log)
        self.assertEqual(comments[0]["data"]["message"], self.VIDEO["comment"])
        self.assertIn("FB_VIDEO_ID=V1", log)
        self.assertIn("FB_LINK=comment", log)
        self.assertIn("native video: deepdive_dd3.mp4", log)
        self.assertIn("episode cover set", log)

    def test_a_refused_upload_falls_back_to_the_card_and_the_youtube_link_in_the_comment(self):
        graph = Graph({"/videos": lambda url, data, files, method: ok({"data": []}) if method == "GET"
                       else api_error(100, "Invalid parameter", status=400),
                       "/photos": ok({"id": "p1", "post_id": "PAGE_p1"}), "/comments": ok({"id": "PAGE_p1_c1"}),
                       "/feed": lambda url, data, files, method: ok({"data": []}) if method == "GET" else ok({"id": "PAGE_t1"})})
        code, log = self.run_native(graph, self.content())
        self.assertEqual(code, 0, log)
        self.assertTrue(any(c["url"].endswith("/photos") for c in graph.calls if c["method"] == "POST"), "the card went out instead")
        comments = [c for c in graph.calls if c["method"] == "POST" and c["url"].endswith("/comments")]
        self.assertEqual(len(comments), 1)
        self.assertIn("https://www.youtube.com/watch?v=NEW", comments[0]["data"]["message"])
        self.assertIn("native video not published", log)

    def test_a_master_that_cannot_be_fetched_is_not_a_lost_day(self):
        graph = Graph({"/photos": ok({"id": "p1", "post_id": "PAGE_p1"}), "/comments": ok({"id": "c"}),
                       "/feed": lambda url, data, files, method: ok({"data": []}) if method == "GET" else ok({"id": "PAGE_t1"})})
        code, log = self.run_native(graph, self.content(), fetch_ok=False)
        self.assertEqual(code, 0, log)
        self.assertFalse(any(c["url"].endswith("/videos") for c in graph.calls if c["method"] == "POST"))
        self.assertTrue(any(c["url"].endswith("/photos") for c in graph.calls if c["method"] == "POST"))
        self.assertIn("could not fetch the master", log)

    def test_the_switch_restores_the_card(self):
        graph = Graph({"/photos": ok({"id": "p1", "post_id": "PAGE_p1"}), "/comments": ok({"id": "c"}),
                       "/feed": lambda url, data, files, method: ok({"data": []}) if method == "GET" else ok({"id": "PAGE_t1"})})
        code, log = self.run_native(graph, self.content(), env={"FB_NATIVE_VIDEO": "off"})
        self.assertEqual(code, 0, log)
        self.assertFalse(any(c["url"].endswith("/videos") for c in graph.calls if c["method"] == "POST"))
        self.assertTrue(any(c["url"].endswith("/photos") for c in graph.calls if c["method"] == "POST"))

    def test_a_video_post_without_the_comment_scope_is_edited_in_description_not_message(self):
        graph = Graph({"/videos": lambda url, data, files, method: ok({"data": []}) if method == "GET" else ok({"id": "V1"}),
                       "/V1/thumbnails": ok({"success": True}),
                       "/comments": api_error(200, "(#200) Requires pages_manage_engagement", status=403),
                       "/feed": lambda url, data, files, method: ok({"data": []}) if method == "GET" else ok({"id": "PAGE_t1"})})
        code, log = self.run_native(graph, self.content())
        self.assertEqual(code, 0, log)
        edits = [c for c in graph.calls if c["method"] == "POST" and c["url"].endswith("/V1")]
        self.assertEqual(len(edits), 1, log)
        self.assertIn("description", edits[0]["data"], "a video's words live in `description`")
        self.assertNotIn("message", edits[0]["data"])
        self.assertIn("https://www.youtube.com/watch?v=NEW", edits[0]["data"]["description"])
        self.assertIn("FB_LINK=body", log)

    def test_the_generator_hands_the_video_plan_to_the_poster(self):
        feature = {"stage": "feature", "post_type": "deepdive", "episode": "dd3", "title": "T", "url": "https://www.youtube.com/watch?v=NEW",
                   "text": "🎬 New Deep-Dive (9 minutes): T\n\nWatch the full episode on YouTube:\nhttps://www.youtube.com/watch?v=NEW\n\n#DocOga",
                   "card_text": "T\n• a", "reply_text": "▶", "buttons": [], "video": dict(self.VIDEO)}
        import deepdive_promo
        with patch.object(deepdive_promo, "pack_for", lambda day, channel, **k: feature if channel == "facebook" else None), \
             patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": tempfile.mkdtemp() + "/none"}):
            content = generate_facebook_content.generate(date(2026, 10, 20), write=False)
        self.assertEqual(content["video"]["file_url"], self.VIDEO["file_url"])
        with patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": tempfile.mkdtemp() + "/none"}), \
             patch.object(deepdive_promo, "pack_for", lambda day, channel, **k: None):
            self.assertIsNone(generate_facebook_content.generate(date(2026, 10, 21), write=False)["video"], "an ordinary day carries no video")


class FetchFileTests(unittest.TestCase):
    def test_a_streamed_fetch_follows_redirects_caps_size_and_removes_a_partial_file(self):
        class R:
            status_code = 200

            def __init__(self, chunks):
                self.chunks = chunks

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def iter_content(self, chunk_size=0):
                return iter(self.chunks)

        class Net:
            def __init__(self, chunks):
                self.chunks, self.kw = chunks, None

            def get(self, url, **kw):
                self.kw = kw
                return R(self.chunks)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name) / "a" / "ep.mp4"
        net = Net([b"ab", b"cd"])
        ok_, got = fb_publish.fetch_file("https://github.com/x/releases/download/t/ep.mp4", dest, http=net)
        self.assertTrue(ok_, got)
        self.assertEqual(dest.read_bytes(), b"abcd")
        self.assertTrue(net.kw["allow_redirects"], "GitHub releases 302 to their CDN")
        self.assertTrue(net.kw["stream"])
        big = Path(tmp.name) / "big.mp4"
        ok_, got = fb_publish.fetch_file("https://x/big.mp4", big, max_bytes=3, http=Net([b"ab", b"cd"]))
        self.assertFalse(ok_)
        self.assertIn("OverflowError", got)
        self.assertFalse(big.exists(), "a partial file is removed")
