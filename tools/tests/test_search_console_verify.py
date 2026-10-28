"""tools/search_console_verify.py — docoga.com.ng verified under the sealed personal account:
META tag placed idempotently (other accounts' tags untouched), live-page poll, insert, sites.add;
the disabled-API case named with its enable link; nothing printed that looks like a token."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import search_console_verify as scv  # noqa: E402

TAG = '<meta name="google-site-verification" content="NEWTOKEN123" />'
HTML = ('<!DOCTYPE html>\n<html><head>\n<meta charset="UTF-8">\n'
        '<meta name="google-site-verification" content="OLDACCOUNT" />\n<title>x</title></head><body></body></html>')


def fake_http(sites=(), token_status=200, insert_status=200, api_disabled=False):
    def http(method, url, params=None, data=None, headers=None):
        http.calls.append((method, url))
        if url == scv.SITES and method == "GET":
            return 200, {"siteEntry": [{"siteUrl": s, "permissionLevel": "siteOwner"} for s in http.sites]}
        if url.endswith("/token"):
            if api_disabled:
                return 403, {"error": {"message": "Google Site Verification API has not been used in project 635194176409 before or it is disabled."}}
            return token_status, {"method": "META", "token": TAG} if token_status == 200 else {"error": {"message": "nope"}}
        if url.endswith("/webResource"):
            if insert_status == 200:
                http.sites = list(http.sites) + [scv.SITE_URL]
                return 200, {"id": "https%3A%2F%2Fdocoga.com.ng%2F", "site": {"identifier": scv.SITE_URL, "type": "SITE"}}
            return insert_status, {"error": {"message": "The necessary verification token could not be found on your site."}}
        if method == "PUT" and url.startswith(scv.SITES + "/"):
            return 204, {}
        return 404, {}
    http.calls, http.sites = [], list(sites)
    return http


class PlaceTagTests(unittest.TestCase):
    def test_the_tag_is_added_after_the_existing_one_and_only_once(self):
        new, changed = scv.place_tag(HTML, "NEWTOKEN123")
        self.assertTrue(changed)
        self.assertIn('content="OLDACCOUNT"', new)
        self.assertIn('content="NEWTOKEN123"', new)
        self.assertLess(new.index("OLDACCOUNT"), new.index("NEWTOKEN123"))
        again, changed2 = scv.place_tag(new, "NEWTOKEN123")
        self.assertFalse(changed2)
        self.assertEqual(again, new)

    def test_a_page_without_any_tag_gets_it_right_after_head(self):
        new, changed = scv.place_tag("<html><head>\n<title>x</title></head></html>", "T")
        self.assertTrue(changed)
        self.assertTrue(new.startswith('<html><head>\n<meta name="google-site-verification" content="T" />'))

    def test_the_live_site_index_still_carries_the_original_tag(self):
        html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(scv.TAG_RE.findall(html)), 1)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.index = Path(tempfile.mkdtemp()) / "index.html"
        self.index.write_text(HTML, encoding="utf-8")
        self.logs = []

    def run_prepare(self, http):
        with patch.object(scv, "access_token", lambda: "AT"):
            return scv.cmd_prepare(http=http, index=self.index, log=self.logs.append)

    def run_verify(self, http, fetch, wait=60):
        slept = []
        with patch.object(scv, "access_token", lambda: "AT"):
            rc = scv.cmd_verify(http=http, fetch=fetch, index=self.index, wait=wait, every=10, sleep=slept.append, log=self.logs.append)
        return rc, slept

    def test_prepare_writes_the_tag_and_says_changed(self):
        http = fake_http()
        self.assertEqual(self.run_prepare(http), 0)
        self.assertIn("SEARCH_VERIFY=prepared", self.logs)
        self.assertIn("SEARCH_VERIFY_CHANGED=yes", self.logs)
        self.assertIn('content="NEWTOKEN123"', self.index.read_text(encoding="utf-8"))
        self.logs.clear()
        self.assertEqual(self.run_prepare(fake_http()), 0)
        self.assertIn("SEARCH_VERIFY_CHANGED=no", self.logs)

    def test_prepare_with_the_api_disabled_is_exit_9_with_the_enable_link(self):
        rc = self.run_prepare(fake_http(api_disabled=True))
        self.assertEqual(rc, 9)
        self.assertIn("SEARCH_VERIFY=api-disabled", self.logs)
        self.assertTrue(any(scv.ENABLE_URL in l for l in self.logs))
        self.assertNotIn("NEWTOKEN123", self.index.read_text(encoding="utf-8"))

    def test_an_already_verified_account_skips_everything(self):
        http = fake_http(sites=[scv.SITE_URL])
        self.assertEqual(self.run_prepare(http), 0)
        self.assertIn("SEARCH_VERIFY=already-verified", self.logs)
        self.assertFalse(any(u.endswith("/token") for _, u in http.calls))

    def test_verify_waits_for_the_live_page_then_inserts_and_adds_the_site(self):
        self.run_prepare(fake_http())
        http = fake_http()
        answers = iter([(200, "<html>old build</html>"), (200, "<html>old build</html>"), (200, self.index.read_text(encoding="utf-8"))])
        rc, slept = self.run_verify(http, lambda url: next(answers))
        self.assertEqual(rc, 0, self.logs)
        self.assertEqual(len(slept), 2)
        self.assertIn("SEARCH_VERIFY=verified", self.logs)
        self.assertIn("SEARCH_CONSOLE_SITE_ADD=204", self.logs)
        self.assertIn(("POST", scv.SV + "/webResource"), http.calls)
        self.assertTrue(any(m == "PUT" for m, _ in http.calls))
        self.assertFalse(any("AT" == l for l in self.logs))

    def test_verify_before_the_page_is_live_says_not_live_and_does_not_insert(self):
        self.run_prepare(fake_http())
        http = fake_http()
        rc, slept = self.run_verify(http, lambda url: (200, "<html>old build</html>"), wait=1)
        self.assertEqual(rc, 1)
        self.assertIn("SEARCH_VERIFY=not-live", self.logs)
        self.assertFalse(any(u.endswith("/webResource") for _, u in http.calls))

    def test_google_refusing_the_insert_is_named(self):
        self.run_prepare(fake_http())
        rc, _ = self.run_verify(fake_http(insert_status=400), lambda url: (200, self.index.read_text(encoding="utf-8")))
        self.assertEqual(rc, 1)
        self.assertIn("SEARCH_VERIFY=refused", self.logs)
        self.assertTrue(any("could not be found" in l for l in self.logs))


class WorkflowTests(unittest.TestCase):
    def test_both_workflows_commit_the_tag_without_skip_ci_so_the_site_rebuilds(self):
        for name in ("google_search_consent.yml", "search_console_verify.yml"):
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertIn("search_console_verify.py prepare", text, name)
            self.assertIn("search_console_verify.py verify", text, name)
            self.assertIn('git commit -m "Search Console: verification tag for the personal account (site rebuild)"', text, name)
            self.assertIn("SOCIAL_TOKEN_KEY: ${{ secrets.SOCIAL_TOKEN_KEY }}", text, name)
            self.assertIn("tools/search_console.py", text, name)

    def test_the_search_profile_asks_for_the_verify_and_add_scopes_in_the_same_consent(self):
        import token_scopes
        want = token_scopes.WANT["google_search"]
        for s in ("https://www.googleapis.com/auth/siteverification", "https://www.googleapis.com/auth/webmasters",
                  "https://www.googleapis.com/auth/webmasters.readonly", "https://www.googleapis.com/auth/analytics.readonly",
                  "https://www.googleapis.com/auth/userinfo.email"):
            self.assertIn(s, want)


if __name__ == "__main__":
    unittest.main()
