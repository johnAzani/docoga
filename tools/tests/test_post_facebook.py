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
