"""tools/linkedin_publish.py — the ₦0 LinkedIn profile lane.

What these pin: the little-text escaping LinkedIn rejects posts without, the 60-day token
clock that warns from day 50, a dormant lane when there is no secret, a dead token named as
one (exit 3), the duplicate guard, and the article card falling back to plain text.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import linkedin_publish as li  # noqa: E402


class FakeHttp(object):
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, method, url, token, body=None, timeout=45):
        self.calls.append({"method": method, "url": url, "token": token, "body": body})
        for key, answer in self.routes.items():
            m, _, path = key.partition(" ")
            if m == method and path in url:
                status, resp, headers = answer(body) if callable(answer) else answer
                return status, resp, headers
        return 404, '{"message":"no route"}', {}


ME = (200, json.dumps({"sub": "AbC123", "name": "John Azani"}), {})
POSTED = (201, "", {"x-restli-id": "urn:li:share:7000"})


class LinkedInTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = os.path.join(self.tmp, "linkedin_posts.json")
        self._orig = (li.LEDGER, li.http)
        li.LEDGER = Path(self.ledger)
        os.environ["DOCOGA_BRAIN_DRAFTS"] = os.path.join(self.tmp, "no-drafts")
        os.environ["LINKEDIN_ACCESS_TOKEN"] = "tok-1"

    def tearDown(self):
        li.LEDGER, li.http = self._orig
        os.environ.pop("LINKEDIN_ACCESS_TOKEN", None)
        os.environ.pop("DOCOGA_BRAIN_DRAFTS", None)

    def run_main(self, argv, routes=None):
        fake = FakeHttp(routes or {})
        li.http = fake
        out = io.StringIO()
        with redirect_stdout(out):
            code = li.main(argv)
        return code, out.getvalue(), fake

    # ── copy ──
    def test_reserved_characters_are_escaped_but_links_are_not(self):
        text = "Rent (Lagos) — s.13(1)(e) #DocOga https://docoga.com.ng/rent-receipt-lagos.html"
        esc = li.escape(text)
        self.assertIn("\\(Lagos\\)", esc)
        self.assertIn("s.13\\(1\\)\\(e\\)", esc)
        self.assertIn("\\#DocOga", esc)
        self.assertIn("https://docoga.com.ng/rent-receipt-lagos.html", esc)

    def test_hashtags_are_dropped_from_the_copy(self):
        self.assertEqual(li.strip_hashtags("Hello\n\n#DocOga #Lagos\n\nhttps://docoga.com.ng"), "Hello\n\nhttps://docoga.com.ng")

    def test_copy_without_a_pack_comes_from_the_rotation_and_carries_our_link(self):
        from datetime import date
        text, link, source = li.copy_for(date(2026, 10, 21))
        self.assertTrue(source.startswith("rotation:"))
        self.assertIn("docoga.com.ng", link)
        self.assertNotIn("#", text)
        self.assertEqual(li.check_copy(text), [])

    def test_a_foreign_link_or_an_empty_post_is_refused(self):
        self.assertTrue(li.check_copy(""))
        self.assertTrue(li.check_copy("see https://example.com/rent"))

    # ── lane behaviour ──
    def test_no_secret_means_dormant_not_red(self):
        os.environ.pop("LINKEDIN_ACCESS_TOKEN")
        code, out, fake = self.run_main(["--day", "2026-10-21"])
        self.assertEqual(code, 0)
        self.assertIn("LINKEDIN_RESULT=dormant", out)
        self.assertEqual(fake.calls, [])

    def test_a_post_goes_out_as_the_member_with_the_article_card_and_is_recorded(self):
        code, out, fake = self.run_main(["--day", "2026-10-21"], {"GET /v2/userinfo": ME, "POST /rest/posts": POSTED})
        self.assertEqual(code, 0, out)
        self.assertIn("LINKEDIN_RESULT=sent", out)
        self.assertIn("LINKEDIN_URL=https://www.linkedin.com/feed/update/urn:li:share:7000/", out)
        post = [c for c in fake.calls if c["url"].endswith("/rest/posts")][0]
        self.assertEqual(post["body"]["author"], "urn:li:person:AbC123")
        self.assertEqual(post["body"]["lifecycleState"], "PUBLISHED")
        self.assertEqual(post["body"]["visibility"], "PUBLIC")
        self.assertIn("docoga.com.ng", post["body"]["content"]["article"]["source"])
        self.assertNotIn("#", post["body"]["commentary"].replace("\\#", ""))
        ledger = json.loads(Path(self.ledger).read_text())
        self.assertEqual(ledger["entries"][0]["urn"], "urn:li:share:7000")
        # The same text a second time is refused, offline, before any network call.
        code, out, fake = self.run_main(["--day", "2026-10-21"], {"GET /v2/userinfo": ME, "POST /rest/posts": POSTED})
        self.assertEqual(code, 0)
        self.assertIn("LINKEDIN_RESULT=duplicate", out)
        self.assertEqual([c for c in fake.calls if c["method"] == "POST"], [])

    def test_the_article_card_is_a_bonus_the_text_never_waits_for(self):
        seen = []

        def posts(body):
            seen.append(body)
            if "content" in body:
                return 422, '{"message":"article thumbnail required"}', {}
            return POSTED

        code, out, fake = self.run_main(["--text", "Payslips in 60 seconds. https://docoga.com.ng/payslip-nigeria.html",
                                         "--link", "https://docoga.com.ng/payslip-nigeria.html"],
                                        {"GET /v2/userinfo": ME, "POST /rest/posts": posts})
        self.assertEqual(code, 0, out)
        self.assertEqual(len(seen), 2)
        self.assertNotIn("content", seen[1])
        self.assertIn("LINKEDIN_RESULT=sent", out)

    def test_a_dead_token_is_named_with_the_tap_that_fixes_it_and_exits_3(self):
        dead = (401, '{"serviceErrorCode":65601,"message":"The token used in the request has been revoked by the user"}', {})
        code, out, fake = self.run_main(["--day", "2026-10-21"], {"GET /v2/userinfo": dead})
        self.assertEqual(code, 3)
        self.assertIn("LINKEDIN_RESULT=failed", out)
        self.assertIn("LINKEDIN_CAUSE=credentials", out)
        self.assertIn("LINKEDIN_ACCESS_TOKEN", out)
        self.assertIn("w_member_social", out)
        self.assertEqual([c for c in fake.calls if c["method"] == "POST"], [])

    def test_the_sixty_day_clock_warns_from_day_fifty(self):
        then = (datetime.now(timezone.utc) - timedelta(days=51)).isoformat(timespec="seconds")
        Path(self.ledger).write_text(json.dumps({"entries": [], "tokens": {li.fingerprint("tok-1"): then}}))
        code, out, _ = self.run_main(["--probe"], {"GET /v2/userinfo": ME})
        self.assertEqual(code, 0)
        self.assertIn("LINKEDIN_TOKEN_AGE=51", out)
        self.assertIn("::warning title=LinkedIn token is 51 days old", out)
        # A fresh token starts its own clock.
        os.environ["LINKEDIN_ACCESS_TOKEN"] = "tok-2"
        code, out, _ = self.run_main(["--probe"], {"GET /v2/userinfo": ME})
        self.assertIn("LINKEDIN_TOKEN_AGE=0", out)
        self.assertNotIn("::warning", out)

    def test_a_dry_run_touches_no_network(self):
        code, out, fake = self.run_main(["--day", "2026-10-21", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("LINKEDIN_RESULT=dry-run", out)
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
