"""tools/token_scopes.py — the one permission list per token, and the audit that checks it.

Owner, 17 Oct 2026: "make sure all permissions are granted … I will not want to re-mint it."
These tests pin (1) the list is a superset of every scope the lanes actually ask for in code,
(2) docs/TOKENS.md names every scope the code wants, (3) the audit says `complete`,
`missing:<names>`, `unreadable` or `no-token` — never complete on a guess — and (4) the Monday
lane runs it with the secrets it needs.
"""
import io
import contextlib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import token_scopes as ts  # noqa: E402


class FakeHttp:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, method, url, params=None, data=None, headers=None, timeout=30):
        self.calls.append((method, url, dict(params or {}), dict(data or {})))
        for needle, resp in self.routes:
            if needle in url:
                return resp
        return 404, {"error": {"message": "no route " + url}}


class ListTests(unittest.TestCase):
    def test_the_list_is_a_superset_of_every_scope_the_code_asks_for(self):
        """Every scope string a lane names in code (its `_fail(..., scope, ...)` calls, its
        `read_scope`/`write_scope`, the Google scopes in yt tooling) must be on WANT — a lane
        that needs a scope the mint list lacks is a re-mint waiting to happen."""
        wanted = {s for scopes in ts.WANT.values() for s in scopes}
        code = ""
        for p in list((ROOT / "tools").glob("*.py")) + list((ROOT / "scripts").glob("*.py")):
            if p.name == "token_scopes.py":
                continue
            code += p.read_text(encoding="utf-8")
        # Scope names in Meta's grammar only: field names and file stems share the prefixes.
        grammar = re.compile(r"^(pages_(show_list|read_engagement|read_user_content|manage_(posts|metadata|engagement|ads|cta)|messaging)"
                             r"|read_insights|publish_video|business_management"
                             r"|instagram_(basic|content_publish|manage_(comments|insights|messages)|shopping_tag_products"
                             r"|business_(basic|content_publish|manage_(comments|messages|insights)))"
                             r"|threads_(basic|content_publish|manage_(replies|insights|mentions)|read_replies|keyword_search|delete"
                             r"|location_tagging|profile_discovery))$")
        named = {n for n in re.findall(r"\b(pages_[a-z_]+|instagram_[a-z_]+|threads_[a-z_]+|read_insights|publish_video|business_management)\b", code)
                 if grammar.match(n)}
        missing = sorted(n for n in named if n not in wanted)
        self.assertEqual(missing, [], "scopes the code names but the mint list lacks")
        self.assertIn("instagram_business_manage_comments", named, "the extractor sees the replies lane's scopes")
        google = set(re.findall(r"https://www\.googleapis\.com/auth/[a-z.\-]+", code))
        self.assertTrue(google <= set(ts.WANT["google"]), google - set(ts.WANT["google"]))

    def test_the_doc_names_every_scope_in_the_code_list(self):
        doc = (ROOT / "docs" / "TOKENS.md").read_text(encoding="utf-8")
        for name, scopes in ts.WANT.items():
            for s in scopes:
                self.assertIn(s, doc, "%s scope %r is in the code but not on the owner's page" % (name, s))

    def test_the_messaging_and_insight_scopes_the_sixth_round_needs_are_on_it(self):
        self.assertIn("pages_messaging", ts.WANT["facebook"])
        self.assertIn("pages_manage_engagement", ts.WANT["facebook"])
        self.assertIn("instagram_business_manage_messages", ts.WANT["instagram"])
        self.assertIn("instagram_business_manage_insights", ts.WANT["instagram"])
        self.assertIn("threads_delete", ts.WANT["threads"])
        self.assertIn("https://www.googleapis.com/auth/webmasters.readonly", ts.WANT["google"])
        self.assertIn("https://www.googleapis.com/auth/yt-analytics.readonly", ts.WANT["google"])


class AuditTests(unittest.TestCase):
    def test_facebook_reads_me_permissions_and_names_what_is_missing(self):
        granted = [{"permission": s, "status": "granted"} for s in ts.WANT["facebook"] if s not in ("pages_messaging", "pages_manage_engagement")]
        granted.append({"permission": "pages_manage_engagement", "status": "declined"})
        http = FakeHttp([("/me/permissions", (200, {"data": granted}))])
        rows = ts.audit({"FB_PAGE_ACCESS_TOKEN": "t"}, http, only="facebook")
        self.assertEqual(rows[0]["state"], "missing")
        self.assertEqual(rows[0]["missing"], ["pages_manage_engagement", "pages_messaging"])
        self.assertEqual(ts.machine_lines(rows), ["SCOPES_FACEBOOK=missing:pages_manage_engagement,pages_messaging"])
        md = ts.markdown(rows)
        self.assertIn("comment → DM on Facebook", md)
        self.assertIn("docs/TOKENS.md", md)

    def test_a_complete_token_is_complete_and_extra_scopes_do_not_hurt(self):
        granted = [{"permission": s, "status": "granted"} for s in ts.WANT["facebook"] + ["public_profile", "ads_read"]]
        http = FakeHttp([("/me/permissions", (200, {"data": granted}))])
        rows = ts.audit({"FB_PAGE_ACCESS_TOKEN": "t"}, http, only="facebook")
        self.assertEqual((rows[0]["state"], rows[0]["extra"]), ("complete", ["ads_read"]))
        self.assertEqual(ts.machine_lines(rows), ["SCOPES_FACEBOOK=complete"])

    def test_instagram_uses_debug_token_with_the_app_token_and_reads_granular_scopes(self):
        body = {"data": {"scopes": ["instagram_business_basic"], "granular_scopes": [{"scope": "instagram_business_content_publish"}]}}
        http = FakeHttp([("graph.facebook.com", (200, body))])
        rows = ts.audit({"IG_ACCESS_TOKEN": "IGQVJ-SECRET-VALUE", "META_APP_ID": "1", "META_APP_SECRET": "s"}, http, only="instagram")
        self.assertEqual(rows[0]["state"], "missing")
        self.assertEqual(rows[0]["missing"], ["instagram_business_manage_comments", "instagram_business_manage_messages",
                                              "instagram_business_manage_insights"])
        self.assertEqual(http.calls[0][2]["access_token"], "1|s")
        self.assertNotIn("IGQVJ-SECRET-VALUE", ts.markdown(rows) + " ".join(ts.machine_lines(rows)), "the token value is never printed")

    def test_unreadable_is_unreadable_not_complete(self):
        http = FakeHttp([("/debug_token", (400, {"error": {"message": "(#100) nope"}}))])
        rows = ts.audit({"THREADS_ACCESS_TOKEN": "t"}, http, only="threads")
        self.assertEqual((rows[0]["state"], rows[0]["complete"]), ("unreadable", False))
        self.assertIn("would not list", ts.markdown(rows))
        self.assertEqual(ts.audit({}, http, only="threads")[0]["state"], "no-token")

    def test_google_refreshes_then_asks_tokeninfo_and_the_token_file_path_is_honoured(self):
        import tempfile
        http = FakeHttp([("tokeninfo", (200, {"scope": "https://www.googleapis.com/auth/youtube.force-ssl https://www.googleapis.com/auth/youtube.upload"})),
                         ("oauth2.googleapis.com/token", (200, {"access_token": "acc"}))])
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write("refresh-from-file\n")
        rows = ts.audit({"YT_REFRESH_TOKEN_FILE": fh.name, "YT_CLIENT_ID": "c", "YT_CLIENT_SECRET": "s"}, http, only="google")
        self.assertEqual(http.calls[0][3]["refresh_token"], "refresh-from-file")
        self.assertEqual(rows[0]["state"], "missing")
        self.assertIn("https://www.googleapis.com/auth/webmasters.readonly", rows[0]["missing"])
        self.assertIn("Search Console", ts.markdown(rows))

    def test_the_cli_prints_the_machine_lines_and_appends_the_markdown(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = ts.main(["list", "threads"])
            self.assertEqual(code, 0)
            self.assertIn("threads_delete", out.getvalue())
            path = Path(d) / "s.md"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                # no tokens in this environment → every line is no-token, nothing is fetched
                import os
                saved = dict(os.environ)
                for k in list(os.environ):
                    if k.endswith(("_TOKEN", "_TOKEN_FILE", "_SECRET", "_ID")):
                        os.environ.pop(k, None)
                try:
                    code = ts.main(["audit", "--markdown", str(path)])
                finally:
                    os.environ.clear()
                    os.environ.update(saved)
            self.assertEqual(code, 0)
            self.assertIn("SCOPES_FACEBOOK=no-token", out.getvalue())
            self.assertIn("Token permissions", path.read_text(encoding="utf-8"))


class WorkflowTests(unittest.TestCase):
    def test_the_monday_lane_audits_the_tokens_with_the_secrets_it_needs_and_never_goes_red_for_it(self):
        import yaml
        text = (ROOT / ".github" / "workflows" / "brain_scorecard.yml").read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        steps = doc["jobs"][next(iter(doc["jobs"]))]["steps"]
        step = next(s for s in steps if "token_scopes.py audit" in (s.get("run") or ""))
        self.assertTrue(step.get("continue-on-error"), "an audit must never stop the scorecard")
        for secret in ("FB_PAGE_ACCESS_TOKEN", "META_APP_ID", "META_APP_SECRET", "YT_REFRESH_TOKEN", "YT_CLIENT_ID", "YT_CLIENT_SECRET"):
            self.assertIn(secret, step["env"], secret)
        self.assertIn("--markdown /tmp/scorecard.md", step["run"], "the verdict rides into the weekly issue")
        names = [s.get("name", "") for s in steps]
        self.assertLess(names.index(step["name"]), names.index(next(n for n in names if "weekly scorecard issue" in n)))


if __name__ == "__main__":
    unittest.main()


class GoogleReadsTheVaultWithoutRequests(unittest.TestCase):
    """27 Oct 2026: the Monday scorecard said Google was 'short 6 permissions' while every YouTube
    lane and YouTube Analytics worked. The audit had gone through yt_publish (which imports
    `requests`); in a job that installed only `cryptography` the import failed quietly and the
    audit graded the bootstrap YT_REFRESH_TOKEN secret instead of the vault. The reader now opens
    the box through token_vault directly and names which token it graded."""

    def test_the_vault_token_wins_and_is_named_even_if_yt_publish_cannot_import(self):
        import importlib
        import sys
        from unittest import mock
        seen = {}

        def fake_http(method, url, params=None, data=None, headers=None, timeout=30):
            if url.endswith("/token"):
                seen["refresh"] = data["refresh_token"]
                return 200, {"access_token": "acc"}
            return 200, {"scope": " ".join(ts.WANT["google"])}

        tv = importlib.import_module("token_vault")
        with mock.patch.dict(sys.modules, {"yt_publish": None}), \
             mock.patch.object(tv, "_vault_path", return_value=mock.Mock(is_file=lambda: True)), \
             mock.patch.object(tv, "open_box", return_value=("VAULT-REFRESH", {"name": "YT_REFRESH_TOKEN"})):
            rows = ts.audit({"SOCIAL_TOKEN_KEY": "k", "YT_REFRESH_TOKEN": "OLD-SECRET", "YT_CLIENT_ID": "c",
                             "YT_CLIENT_SECRET": "s"}, fake_http, only="google")
        self.assertEqual(seen["refresh"], "VAULT-REFRESH")
        self.assertEqual(rows[0]["state"], "complete")
        self.assertIn("vault", rows[0]["how"])
        self.assertNotIn("import yt_publish", open(ts.__file__, encoding="utf-8").read().split("def _vault_refresh_token")[1])

    def test_without_a_vault_the_secret_is_graded_and_the_summary_says_so(self):
        from unittest import mock
        import importlib
        tv = importlib.import_module("token_vault")

        def fake_http(method, url, params=None, data=None, headers=None, timeout=30):
            if url.endswith("/token"):
                return 200, {"access_token": "acc"}
            return 200, {"scope": "https://www.googleapis.com/auth/youtube.force-ssl"}

        with mock.patch.object(tv, "_vault_path", return_value=mock.Mock(is_file=lambda: False)):
            rows = ts.audit({"SOCIAL_TOKEN_KEY": "k", "YT_REFRESH_TOKEN": "OLD-SECRET", "YT_CLIENT_ID": "c",
                             "YT_CLIENT_SECRET": "s"}, fake_http, only="google")
        self.assertEqual(rows[0]["state"], "missing")
        self.assertIn("YT_REFRESH_TOKEN secret", rows[0]["how"])
        md = ts.markdown(rows)
        self.assertIn("read via tokeninfo on the YT_REFRESH_TOKEN secret", md)
