"""The one Google consent, from a phone: the secret never leaves GitHub; the token is minted
once with every scope, refused when short, sealed in the vault, and every Google-facing lane
reads the vault before the secret."""
import glob
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import google_consent as gc  # noqa: E402
import token_scopes  # noqa: E402
import token_vault  # noqa: E402
import yt_publish  # noqa: E402

KEY = "a" * 64
FULL = " ".join(gc.SCOPES)


def fake(scope=FULL, status=200, refresh="RT-1"):
    def http(method, url, data=None, params=None):
        if url == gc.TOKEN_URL:
            body = {"access_token": "at", "scope": scope}
            if refresh:
                body["refresh_token"] = refresh
            return status, body if status == 200 else {"error": "invalid_grant", "error_description": "Bad Request"}
        return 200, {}
    http.calls = []
    return http


class ConsentUrlTests(unittest.TestCase):
    def test_the_link_asks_for_all_seven_scopes_offline_with_consent_forced(self):
        q = parse_qs(urlparse(gc.consent_url("cid")).query)
        self.assertEqual(set(q["scope"][0].split()), set(token_scopes.WANT["google"]))
        self.assertEqual(len(token_scopes.WANT["google"]), 7)
        self.assertEqual(q["access_type"], ["offline"])
        self.assertEqual(q["prompt"], ["consent"])
        self.assertEqual(q["redirect_uri"], [gc.REDIRECT_URI])
        self.assertEqual(q["client_id"], ["cid"])

    def test_the_code_is_read_from_the_whole_playground_address_or_bare(self):
        self.assertEqual(gc.code_from("https://developers.google.com/oauthplayground/?code=4%2F0Aabc&scope=x"), "4/0Aabc")
        self.assertEqual(gc.code_from(" 4/0Aabc "), "4/0Aabc")
        self.assertEqual(gc.code_from(""), "")


class ExchangeTests(unittest.TestCase):
    def setUp(self):
        self.box = os.path.join(tempfile.mkdtemp(), "yt.box")
        self.env = {"YT_CLIENT_ID": "c", "YT_CLIENT_SECRET": "s"}

    def test_a_token_for_the_wrong_channel_is_refused_and_the_old_one_stays(self):
        # 19 Oct 2026: the 17 Oct mint picked the personal channel on Google's second chooser.
        def chan(method, url, data=None, params=None):
            if url == gc.CHANNELS_URL:
                return 200, {"items": [{"id": "UC-personal", "snippet": {"title": "Millionaire_money1"}}]}
            return fake()(method, url, data, params)
        out = []
        env = dict(self.env, YT_CHANNEL_ID="UC-docoga")
        with patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": KEY}):
            rc = gc.run_exchange("4/0Aabc", env=env, http=chan, log=out.append, vault_path=self.box)
        self.assertEqual(rc, 6)
        self.assertIn("GOOGLE_CONSENT=wrong_channel", out)
        self.assertIn("GOOGLE_CHANNEL=UC-personal Millionaire_money1", out)
        self.assertFalse(os.path.exists(self.box))
        # The right channel seals.
        def ok(method, url, data=None, params=None):
            if url == gc.CHANNELS_URL:
                return 200, {"items": [{"id": "UC-docoga", "snippet": {"title": "DocOga"}}]}
            return fake()(method, url, data, params)
        out = []
        with patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": KEY}):
            rc = gc.run_exchange("4/0Aabc", env=env, http=ok, log=out.append, vault_path=self.box)
        self.assertEqual(rc, 0)
        self.assertIn("GOOGLE_CONSENT=ok", out)

    def test_a_complete_token_is_sealed_and_never_printed(self):
        out = []
        with patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": KEY}):
            rc = gc.run_exchange("4/0Aabc", env=self.env, http=fake(), log=out.append, vault_path=self.box)
        self.assertEqual(rc, 0)
        self.assertIn("GOOGLE_CONSENT=ok", out)
        self.assertTrue(os.path.isfile(self.box))
        self.assertNotIn("RT-1", "\n".join(out))
        self.assertNotIn("RT-1", open(self.box).read())

    def test_a_short_token_is_refused_and_nothing_is_written(self):
        out = []
        with patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": KEY}):
            rc = gc.run_exchange("x", env=self.env, http=fake(scope=" ".join(gc.SCOPES[:4])), log=out.append, vault_path=self.box)
        self.assertEqual(rc, 4)
        self.assertIn("GOOGLE_CONSENT=refused", out)
        self.assertTrue(any(l.startswith("GOOGLE_SCOPES_MISSING=") and "webmasters.readonly" in l for l in out))
        self.assertFalse(os.path.isfile(self.box))

    def test_accept_partial_seals_anyway_and_says_partial(self):
        out = []
        with patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": KEY}):
            rc = gc.run_exchange("x", env=self.env, http=fake(scope=" ".join(gc.SCOPES[:4])), log=out.append,
                                 vault_path=self.box, accept_partial=True)
        self.assertEqual(rc, 0)
        self.assertIn("GOOGLE_CONSENT=partial", out)

    def test_google_refusing_the_code_is_exit_3_with_a_hint(self):
        out = []
        rc = gc.run_exchange("x", env=self.env, http=fake(status=400), log=out.append, vault_path=self.box)
        self.assertEqual(rc, 3)
        self.assertTrue(any("older than ~10 minutes" in l for l in out))

    def test_missing_client_is_exit_2(self):
        self.assertEqual(gc.run_exchange("x", env={}, http=fake(), log=lambda *a: None, vault_path=self.box), 2)


class VaultFirstTests(unittest.TestCase):
    def test_authorize_and_the_scope_audit_prefer_the_vault_over_the_secret(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp()
        os.chdir(tmp)
        try:
            with patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": KEY, "YT_REFRESH_TOKEN": "OLD", "YT_CLIENT_ID": "c",
                                         "YT_CLIENT_SECRET": "s"}):
                token_vault.seal("YT_REFRESH_TOKEN", "NEW")
                self.assertEqual(yt_publish.vault_refresh_token(), "NEW")
                seen = {}

                class H:
                    def request(self, method, url, headers=None, data=None, **kw):
                        seen.update(data or {})

                        class R:
                            status_code = 200
                            text = "{}"

                            def json(self):
                                return {"access_token": "at", "expires_in": 3600}
                        return R()
                yt_publish.authorize(H())
                self.assertEqual(seen["refresh_token"], "NEW")
                calls = []

                def http(method, url, data=None, params=None):
                    calls.append((url, data))
                    if url.endswith("/token"):
                        return 200, {"access_token": "at"}
                    return 200, {"scope": "a b"}
                token_scopes.read_google(dict(os.environ), http=http)
                self.assertEqual(calls[0][1]["refresh_token"], "NEW")
        finally:
            os.chdir(cwd)

    def test_without_a_box_the_secret_still_works(self):
        cwd = os.getcwd()
        os.chdir(tempfile.mkdtemp())
        try:
            with patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": KEY}):
                self.assertEqual(yt_publish.vault_refresh_token(), "")
        finally:
            os.chdir(cwd)


class WorkflowTests(unittest.TestCase):
    def test_every_env_block_with_the_google_token_also_carries_the_vault_key(self):
        for f in glob.glob(str(ROOT / ".github" / "workflows" / "*.yml")):
            lines = open(f, encoding="utf-8").read().splitlines()
            for i, ln in enumerate(lines):
                m = re.match(r"^(\s+)YT_REFRESH_TOKEN: \$\{\{ secrets\.YT_REFRESH_TOKEN \}\}", ln)
                if not m:
                    continue
                ind = m.group(1)
                j = i
                while j - 1 >= 0 and re.match(r"^" + ind + r"[A-Za-z_]+:", lines[j - 1]):
                    j -= 1
                k = i
                while k + 1 < len(lines) and re.match(r"^" + ind + r"[A-Za-z_]+:", lines[k + 1]):
                    k += 1
                block = "\n".join(lines[j:k + 1])
                self.assertIn("SOCIAL_TOKEN_KEY:", block, "%s line %d: Google token without the vault key" % (os.path.basename(f), i + 1))

    def test_the_consent_workflow_holds_the_client_and_refuses_partial_by_default(self):
        text = (ROOT / ".github" / "workflows" / "google_consent.yml").read_text(encoding="utf-8")
        for need in ("YT_CLIENT_ID: ${{ secrets.YT_CLIENT_ID }}", "YT_CLIENT_SECRET: ${{ secrets.YT_CLIENT_SECRET }}",
                     "SOCIAL_TOKEN_KEY: ${{ secrets.SOCIAL_TOKEN_KEY }}", "google_consent.py url",
                     "google_consent.py exchange", "logs/yt_refresh_token.box", "accept_partial", "set +e"):
            self.assertIn(need, text)
        self.assertNotIn("echo \"$GOOGLE_AUTH_CODE\"", text)

    def test_the_google_lanes_install_cryptography_so_the_vault_can_open(self):
        for name in ("youtube_stats.yml", "youtube_manage.yml", "youtube_autopost.yml", "youtube_queue.yml",
                     "youtube_scheduled.yml", "deepdive.yml", "brain_scorecard.yml"):
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertTrue("cryptography" in text or "requirements-youtube.txt" in text, name)
        self.assertIn("cryptography", (ROOT / "requirements-youtube.txt").read_text())


if __name__ == "__main__":
    unittest.main()
