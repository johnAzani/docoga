"""The follow loop (4 Nov 2026): a specific ask on every Facebook post, the site pointing at the
Page, the profile audit that fills what it may and names the rest — and the fact-id leak that was
found on the way (three packs with "(lagos:receipts:1)" inline) stripped on read and at the source."""
import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for rel in ("tools", "scripts"):
    if str(ROOT / rel) not in sys.path:
        sys.path.insert(0, str(ROOT / rel))

import brain_drafts  # noqa: E402
import fb_follow  # noqa: E402
import fb_page_audit  # noqa: E402
import fb_publish  # noqa: E402

FACT_ID = re.compile(r"\([a-z-]+:[a-z0-9_]+:\d+\)")


class FollowLineTests(unittest.TestCase):
    def test_the_ask_is_specific_dated_and_never_generic(self):
        seen = {fb_follow.line(dt.date(2026, 11, 1) + dt.timedelta(days=i)) for i in range(12)}
        self.assertEqual(len(seen), len(fb_follow.LINES), "the rotation walks every line")
        for text in list(fb_follow.LINES) + [fb_follow.reel_line(), fb_follow.video_line()]:
            self.assertIn("Follow DocOga", text)
            self.assertTrue(any(w in text.lower() for w in ("every morning", "every evening", "every fortnight")),
                            "specific: what you get and when — %r" % text)
            self.assertNotIn("follow for more", text.lower())
            self.assertNotRegex(text.lower(), r"\b(like|share|comment)\b.*\bif\b", "no engagement bait")
        self.assertEqual(fb_follow.line("2026-11-04"), fb_follow.line(dt.date(2026, 11, 4)), "same words on a re-run")

    def test_append_sits_before_the_hashtags_and_leaves_the_link_line_for_the_first_comment(self):
        message = "Headline\n\nBody line.\n\nSend this to someone.\n\nhttps://docoga.com.ng/rent-receipt-lagos?s=fb\n\n#DocOga #LagosTenancy"
        out = fb_follow.append(message, dt.date(2026, 11, 4))
        self.assertTrue(out.endswith("#DocOga #LagosTenancy"), out)
        self.assertIn(fb_follow.line(dt.date(2026, 11, 4)) + "\n\n#DocOga", out)
        body, link = fb_publish.split_link(out)
        self.assertEqual(link, "https://docoga.com.ng/rent-receipt-lagos?s=fb")
        self.assertIn("Follow DocOga", body)
        self.assertEqual(fb_follow.append(out, dt.date(2026, 11, 4)), out, "asked once, never twice")
        self.assertTrue(fb_follow.append("No tags here.", dt.date(2026, 11, 4)).endswith(fb_follow.line(dt.date(2026, 11, 4))))
        self.assertEqual(fb_follow.append("", dt.date(2026, 11, 4)), "")

    def test_the_facebook_generator_asks_on_every_post(self):
        import os
        import tempfile
        from unittest import mock
        import generate_facebook_content as fb
        with mock.patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": tempfile.mkdtemp() + "/none"}):
            for day in (dt.date(2026, 11, 4), dt.date(2026, 11, 9)):
                content = fb.generate(day, write=False)
                self.assertIn("Follow DocOga", content["message"], day)
                self.assertTrue(content["message"].rstrip().endswith(tuple("#"))) if False else None
                tail = content["message"].rstrip().split("\n")[-1]
                self.assertTrue(tail.startswith("#"), "hashtags stay last: %r" % tail)

    def test_the_reel_caption_and_the_native_video_ask_too(self):
        import reel_caption
        cap = reel_caption.caption("facebook", "Pay twice.", "Pay twice.\n\n→ Ask for a receipt\n", dt.date(2026, 11, 4))
        self.assertIn(fb_follow.reel_line(), cap)
        self.assertTrue(cap.rstrip().split("\n")[-1].startswith("#"))
        ig = reel_caption.caption("instagram", "Pay twice.", "Pay twice.\n\n→ Ask for a receipt\n", dt.date(2026, 11, 4))
        self.assertNotIn("Follow DocOga", ig, "the Facebook ask is Facebook's; Instagram keeps its own shape")

    def test_the_site_row_links_every_channel_facebook_first_and_is_on_every_page(self):
        row = fb_follow.site_row()
        self.assertTrue(row.index("facebook.com") < row.index("youtube.com") < row.index("t.me"))
        self.assertIn(fb_follow.PAGE_URL, row)
        pages = sorted((ROOT / "site").glob("*.html"))
        with_footer = [p for p in pages if p.name != "admin.html" and "<footer" in p.read_text(encoding="utf-8")]
        self.assertGreaterEqual(len(with_footer), 70)
        missing = [p.name for p in with_footer if 'class="follow"' not in p.read_text(encoding="utf-8")]
        self.assertEqual(missing, [], "every page with a footer carries the follow row (regenerate with tools/gen_state_pages.py / gen_guide_pages.py)")
        index = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn(fb_follow.PAGE_URL, index)
        self.assertIn(".foot .follow", index)
        # The address the Shorts print is the same address.
        short = (ROOT / "scripts" / "youtube_short_daily.py").read_text(encoding="utf-8")
        self.assertIn("facebook.com/" + fb_follow.PAGE_USERNAME, short)


class FakeGraph:
    def __init__(self, page, post_status=200, post_body=None):
        self.page, self.post_status, self.post_body, self.posts = page, post_status, post_body or {"success": True}, []

    def __call__(self, method, url, data=None, timeout=30):
        if method == "GET":
            return 200, dict(self.page)
        self.posts.append((url, {k: v for k, v in (data or {}).items() if k != "access_token"}))
        return self.post_status, dict(self.post_body)


FULL = {"username": "docoga.com.ng", "about": "written by the owner", "website": "https://docoga.com.ng",
        "description": "d", "picture": {"data": {"is_silhouette": False}}, "cover": {"id": "c"}, "is_published": True,
        "link": "https://www.facebook.com/docoga.com.ng", "followers_count": 1}


class PageAuditTests(unittest.TestCase):
    def test_a_complete_page_is_ok_and_nothing_is_written(self):
        g = FakeGraph(FULL)
        out = fb_page_audit.audit("TOKEN", "102466208923830", http=g)
        self.assertTrue(out["ok"], out)
        self.assertEqual(g.posts, [], "the owner's own words are never overwritten")

    def test_empty_text_fields_are_filled_from_desired_and_the_taps_are_named(self):
        page = dict(FULL, about="", website=None, picture={"data": {"is_silhouette": True}}, cover=None)
        g = FakeGraph(page)
        out = fb_page_audit.audit("TOKEN", "102466208923830", http=g)
        self.assertEqual(out["filled"], ["about", "website"])
        self.assertEqual(len(g.posts), 1)
        url, data = g.posts[0]
        self.assertTrue(url.endswith("/102466208923830"))
        self.assertEqual(data["about"], fb_page_audit.DESIRED["about"])
        self.assertLessEqual(len(data["about"]), 255)
        self.assertEqual(data["website"], "https://docoga.com.ng/?s=fb")
        self.assertNotIn("description", data, "only the empty fields")
        self.assertFalse(out["ok"])
        self.assertTrue(any("profile photo" in p for p in out["problems"]), out["problems"])
        self.assertTrue(any("cover" in p for p in out["problems"]), out["problems"])

    def test_a_token_that_cannot_write_names_the_paste_and_a_renamed_page_is_caught(self):
        page = dict(FULL, about="", username="SomethingElse")
        g = FakeGraph(page, post_status=403, post_body={"error": {"message": "(#200) Requires pages_manage_metadata", "code": 200}})
        out = fb_page_audit.audit("TOKEN", "102466208923830", http=g)
        self.assertEqual(out["filled"], [])
        self.assertTrue(any("pages_manage_metadata" in p and "DESIRED" in p for p in out["problems"]), out["problems"])
        self.assertTrue(any("username is 'SomethingElse'" in p for p in out["problems"]), out["problems"])
        self.assertEqual(fb_page_audit.audit("TOKEN", "1", http=g, fix=False)["filled"], [])
        self.assertEqual(len(g.posts), 1, "--read-only writes nothing")

    def test_an_unreadable_page_is_a_detail_not_a_crash(self):
        def http(method, url, data=None, timeout=30):
            return 400, {"error": {"message": "Invalid OAuth access token", "code": 190}}
        out = fb_page_audit.audit("TOKEN", "1", http=http)
        self.assertFalse(out["ok"])
        self.assertIn("Invalid OAuth", out["detail"])
        self.assertNotIn("TOKEN", json.dumps(out))

    def test_the_preflight_prints_the_audit_line_and_never_fails_on_it(self):
        import os
        from unittest import mock
        import io
        from contextlib import redirect_stdout
        import fb_preflight
        calls = {"n": 0}

        def call(path, token, **params):
            calls["n"] += 1
            if path.endswith("/feed"):
                return True, {"data": []}
            return True, {"name": "DocOga", "link": "https://www.facebook.com/docoga.com.ng"}

        def audit(token, page_id, http=None, fix=True):
            return {"ok": False, "problems": ["no cover photo — tap"], "filled": ["about"], "page": FULL, "detail": ""}

        with mock.patch.object(fb_preflight, "call", call), mock.patch.object(fb_page_audit, "audit", audit), \
             mock.patch.dict(os.environ, {"FB_PAGE_ACCESS_TOKEN": "T", "FB_PAGE_ID": "1"}, clear=False), \
             redirect_stdout(io.StringIO()) as out:
            code = fb_preflight.main([])
        self.assertEqual(code, 0)
        self.assertIn("FB_PAGE_AUDIT=1 problem(s)", out.getvalue())
        self.assertIn("filled about", out.getvalue())
        self.assertIn("Page profile loses followers", out.getvalue())


class FactIdLeakTests(unittest.TestCase):
    def test_fact_ids_are_stripped_from_the_words_and_kept_in_the_claims(self):
        pack = {"status": "approved", "theme": "x", "claims": [{"fact_id": "lagos:receipts:1", "text": "…"}],
                "post": {"headline": "Pay with a receipt (lagos:receipts:1)",
                         "lines": ["You can go to court (lagos:increase_challenge:1).", "Two at once (lagos:a:1, lagos:b:2), fine.", "At 9:30 (ok)."],
                         "cta": "Send this.", "hashtags": ["#DocOga"]},
                "threads": {"text": "Keep the receipt (nigeria:rent_relief:1)!"}}
        out = brain_drafts.clean_words(pack)
        self.assertEqual(out["post"]["headline"], "Pay with a receipt")
        self.assertEqual(out["post"]["lines"], ["You can go to court.", "Two at once, fine.", "At 9:30 (ok)."])
        self.assertEqual(out["threads"]["text"], "Keep the receipt!")
        self.assertEqual(out["claims"][0]["fact_id"], "lagos:receipts:1", "the claims still cite")
        self.assertIsNone(FACT_ID.search(json.dumps({k: v for k, v in out.items() if k != "claims"})))

    def test_every_approved_pack_in_the_repo_reads_clean(self):
        import os
        from unittest import mock
        drafts = ROOT / "brain" / "drafts"
        days = sorted(p.stem for p in drafts.glob("2026-*.json")) if drafts.is_dir() else []
        with mock.patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": str(drafts)}):
            for day in days[-14:]:
                pack = brain_drafts.draft_for(dt.date.fromisoformat(day))
                if not pack:
                    continue
                words = json.dumps({k: v for k, v in pack.items() if k != "claims"}, ensure_ascii=False)
                self.assertIsNone(FACT_ID.search(words), "%s leaks a fact id into the words" % day)

    def test_the_brain_strips_before_its_gates(self):
        import brain
        pack = {"post": {"headline": "H", "lines": ["One rule (lagos:receipts:1).", "Two."], "cta": "c", "hashtags": []}, "claims": [{"fact_id": "lagos:receipts:1"}]}
        brain.tidy(pack)
        self.assertEqual(pack["post"]["lines"][0], "One rule.")
        self.assertEqual(pack["claims"][0]["fact_id"], "lagos:receipts:1")


if __name__ == "__main__":
    unittest.main()
