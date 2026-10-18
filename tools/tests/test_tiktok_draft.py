"""tools/tiktok_draft.py — the Short into the owner's TikTok inbox, no audit, ₦0."""
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

import tiktok_draft as tt  # noqa: E402


class FakeHttp(object):
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, method, url, headers=None, data=None, timeout=60):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "data": data})
        for key, answer in self.routes.items():
            m, _, path = key.partition(" ")
            if m == method and path in url:
                if callable(answer):
                    answer = answer(self.calls[-1])
                return answer[0], answer[1], {}
        return 404, '{"error":{"code":"no_route","message":"no route"}}', {}


def okjson(data):
    return 200, json.dumps({"data": data, "error": {"code": "ok", "message": ""}})


TOKEN = (200, json.dumps({"access_token": "acc-1", "open_id": "open-9", "refresh_token": "ref-2",
                          "expires_in": 86400, "refresh_expires_in": 31536000, "scope": "user.info.basic,video.upload"}))
INIT = okjson({"publish_id": "v_inbox_file~v2.123", "upload_url": "https://open-upload.tiktokapis.com/video/?upload_id=1"})


class TikTokTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = (tt.LEDGER, tt.http, tt.sleeper)
        tt.LEDGER = Path(self.tmp) / "tiktok_drafts.json"
        tt.sleeper = lambda s: None
        self.video = os.path.join(self.tmp, "short.mp4")
        with open(self.video, "wb") as fh:
            fh.write(b"\x00" * 4096)
        os.environ.update({"TIKTOK_CLIENT_KEY": "ck", "TIKTOK_CLIENT_SECRET": "cs", "TIKTOK_REFRESH_TOKEN": "ref-1"})
        os.environ.pop("SOCIAL_TOKEN_KEY", None)

    def tearDown(self):
        tt.LEDGER, tt.http, tt.sleeper = self._orig
        for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"):
            os.environ.pop(k, None)

    def run_main(self, argv, routes):
        fake = FakeHttp(routes)
        tt.http = fake
        out = io.StringIO()
        with redirect_stdout(out):
            code = tt.main(argv)
        return code, out.getvalue(), fake

    def test_no_secrets_means_dormant_not_red(self):
        os.environ.pop("TIKTOK_REFRESH_TOKEN")
        code, out, fake = self.run_main(["send", "--video", self.video], {})
        self.assertEqual(code, 0)
        self.assertIn("TIKTOK_RESULT=dormant", out)
        self.assertEqual(fake.calls, [])

    def test_the_short_lands_in_the_inbox_in_one_chunk_and_is_recorded(self):
        statuses = iter([okjson({"status": "PROCESSING_UPLOAD"}), okjson({"status": "SEND_TO_USER_INBOX"})])
        code, out, fake = self.run_main(["send", "--video", self.video, "--caption", "Rent receipt in 60 seconds"],
                                        {"POST /v2/oauth/token/": TOKEN, "POST /inbox/video/init/": INIT,
                                         "PUT open-upload": (201, ""), "POST /status/fetch/": lambda c: next(statuses)})
        self.assertEqual(code, 0, out)
        self.assertIn("TIKTOK_RESULT=inbox", out)
        self.assertIn("TIKTOK_PUBLISH_ID=v_inbox_file~v2.123", out)
        init = [c for c in fake.calls if "/inbox/video/init/" in c["url"]][0]
        body = json.loads(init["data"])
        self.assertEqual(body["source_info"], {"source": "FILE_UPLOAD", "video_size": 4096, "chunk_size": 4096, "total_chunk_count": 1})
        self.assertEqual(init["headers"]["Authorization"], "Bearer acc-1")
        put = [c for c in fake.calls if c["method"] == "PUT"][0]
        self.assertEqual(put["headers"]["Content-Range"], "bytes 0-4095/4096")
        self.assertEqual(len(put["data"]), 4096)
        # The refresh grant used the client key and the bootstrap secret, as a form.
        tok = [c for c in fake.calls if "/oauth/token/" in c["url"]][0]
        self.assertIn(b"grant_type=refresh_token", tok["data"])
        self.assertIn(b"refresh_token=ref-1", tok["data"])
        ledger = json.loads(tt.LEDGER.read_text())
        self.assertEqual(ledger["entries"][0]["status"], "SEND_TO_USER_INBOX")
        # The same bytes again are a duplicate, decided offline.
        code, out, fake = self.run_main(["send", "--video", self.video], {"POST /v2/oauth/token/": TOKEN})
        self.assertEqual(code, 0)
        self.assertIn("TIKTOK_RESULT=duplicate", out)
        self.assertEqual([c for c in fake.calls if "/inbox/" in c["url"]], [])

    def test_a_rotated_refresh_token_without_a_vault_key_is_a_warning_not_a_silence(self):
        code, out, _ = self.run_main(["probe"], {"POST /v2/oauth/token/": TOKEN})
        self.assertEqual(code, 0)
        self.assertIn("TIKTOK_RESULT=probed", out)
        self.assertIn("rotated its refresh token", out)

    def test_a_dead_refresh_token_is_credentials_and_exit_3(self):
        dead = (400, json.dumps({"error": "invalid_grant", "error_description": "Refresh token is invalid or expired."}))
        code, out, _ = self.run_main(["send", "--video", self.video], {"POST /v2/oauth/token/": dead})
        self.assertEqual(code, 3)
        self.assertIn("TIKTOK_CAUSE=credentials", out)
        self.assertIn("tiktok-connect.html", out)

    def test_five_pending_in_a_day_is_tiktoks_wall_and_we_stop_before_it(self):
        now = datetime.now(timezone.utc)
        entries = [{"recorded_at": (now - timedelta(hours=h)).isoformat(timespec="seconds"), "key": "k%d" % h,
                    "status": "SEND_TO_USER_INBOX"} for h in range(1, 6)]
        tt.LEDGER.write_text(json.dumps({"entries": entries}))
        code, out, fake = self.run_main(["send", "--video", self.video], {"POST /v2/oauth/token/": TOKEN})
        self.assertEqual(code, 0)
        self.assertIn("TIKTOK_RESULT=skipped", out)
        self.assertEqual([c for c in fake.calls if "/inbox/" in c["url"]], [])

    def test_a_video_tiktok_rejects_is_a_named_failure(self):
        code, out, _ = self.run_main(["send", "--video", self.video],
                                     {"POST /v2/oauth/token/": TOKEN, "POST /inbox/video/init/": INIT, "PUT open-upload": (201, ""),
                                      "POST /status/fetch/": okjson({"status": "FAILED", "fail_reason": "video_too_short"})})
        self.assertEqual(code, 6)
        self.assertIn("video_too_short", out)
        self.assertIn("TIKTOK_CAUSE=video", out)

    def test_big_files_are_chunked_at_ten_megabytes(self):
        self.assertEqual(tt.plan_chunks(4096), (4096, 1))
        self.assertEqual(tt.plan_chunks(64 * 1024 * 1024), (64 * 1024 * 1024, 1))
        size, count = tt.plan_chunks(95 * 1024 * 1024)
        self.assertEqual((size, count), (10 * 1024 * 1024, 9))


class ConnectTests(unittest.TestCase):
    """`connect` — the one-time code becomes a sealed box; no token is ever printed."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = (tt.http, tt.BOX_PATH)
        os.environ.update({"TIKTOK_CLIENT_KEY": "ck", "TIKTOK_CLIENT_SECRET": "cs",
                           "SOCIAL_TOKEN_KEY": "a3f9c2e17b84d6052f1e9c4ab07d3e68c5f2a1947be06d3c8e1f5a2b9c7d4e06"})
        os.environ.pop("TIKTOK_REFRESH_TOKEN", None)
        self.cwd = os.getcwd()
        os.chdir(self.tmp)                      # token_vault writes logs/<name>.box under the cwd
        tt.BOX_PATH = Path(self.tmp) / "logs" / "tiktok_refresh_token.box"

    def tearDown(self):
        os.chdir(self.cwd)
        tt.http, tt.BOX_PATH = self._orig
        for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "SOCIAL_TOKEN_KEY"):
            os.environ.pop(k, None)

    def run_main(self, argv, routes):
        fake = FakeHttp(routes)
        tt.http = fake
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out):
            old = sys.stderr; sys.stderr = err
            try:
                code = tt.main(argv)
            finally:
                sys.stderr = old
        return code, out.getvalue() + err.getvalue(), fake

    def test_connect_seals_the_refresh_token_and_names_the_account(self):
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography not installed")
        full = (200, json.dumps({"access_token": "acc-1", "open_id": "open-9", "refresh_token": "ref-secret-2",
                                 "expires_in": 86400, "refresh_expires_in": 31536000, "scope": ",".join(tt.SCOPES)}))
        routes = {"POST /v2/oauth/token/": full,
                  "GET /v2/user/info/": okjson({"user": {"open_id": "open-9", "display_name": "DocOga", "username": "docoga.ng", "follower_count": 12}})}
        code, out, fake = self.run_main(["connect", "--code", "abc%2A1%21xyz", "--redirect-uri", "https://docoga.com.ng/tiktok-connect.html"], routes)
        self.assertEqual(code, 0, out)
        self.assertIn("TIKTOK_CONNECT=ok", out)
        self.assertIn("TIKTOK_USER=@docoga.ng", out)
        self.assertIn("TIKTOK_VAULT=sealed", out)
        self.assertNotIn("ref-secret-2", out, "the refresh token must never reach a log")
        self.assertNotIn("acc-1", out, "nor the access token")
        body = fake.calls[0]["data"].decode()
        self.assertIn("code=abc%2A1%21xyz", body, "a pasted, percent-encoded code is decoded before the exchange (then re-encoded as a form field)")
        self.assertIn("grant_type=authorization_code", body)
        st = tt.box_status()
        self.assertTrue(st["present"])
        self.assertEqual(st["expires_at"], (datetime.now(timezone.utc) + timedelta(days=365)).date().isoformat())
        # and the lane now finds it without any TIKTOK_REFRESH_TOKEN secret
        value, where = tt.refresh_token_value()
        self.assertEqual(value, "ref-secret-2")
        self.assertTrue(where.startswith("vault"))
        code, out, _ = self.run_main(["status"], {})
        self.assertIn("TIKTOK_CONNECTED=yes", out)

    def test_a_refused_code_is_exit_3_with_a_retry_hint_and_no_box(self):
        routes = {"POST /v2/oauth/token/": (400, json.dumps({"error": "invalid_grant", "error_description": "Authorization code is expired."}))}
        code, out, _ = self.run_main(["connect", "--code", "stale", "--redirect-uri", "https://docoga.com.ng/tiktok-connect.html"], routes)
        self.assertEqual(code, 3)
        self.assertIn("TIKTOK_CONNECT=refused", out)
        self.assertIn("tap the Connect link again", out)
        self.assertFalse(tt.box_status()["present"])

    def test_without_video_upload_the_connect_is_a_red_run(self):
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography not installed")
        narrow = (200, json.dumps({"access_token": "acc-1", "open_id": "open-9", "refresh_token": "ref-3",
                                   "expires_in": 86400, "refresh_expires_in": 31536000, "scope": "user.info.basic"}))
        routes = {"POST /v2/oauth/token/": narrow, "GET /v2/user/info/": okjson({"user": {"display_name": "DocOga"}})}
        code, out, _ = self.run_main(["connect", "--code", "c", "--redirect-uri", "https://docoga.com.ng/tiktok-connect.html"], routes)
        self.assertEqual(code, 3)
        self.assertIn("video.upload was not granted", out)

    def test_no_vault_key_refuses_to_proceed_before_spending_the_code(self):
        os.environ.pop("SOCIAL_TOKEN_KEY")
        code, out, fake = self.run_main(["connect", "--code", "c", "--redirect-uri", "https://docoga.com.ng/tiktok-connect.html"], {})
        self.assertEqual(code, 2)
        self.assertEqual(fake.calls, [], "the single-use code is not burned when it cannot be stored")

    def test_status_without_a_box_is_not_connected(self):
        code, out, _ = self.run_main(["status"], {})
        self.assertEqual(code, 0)
        self.assertIn("TIKTOK_CONNECTED=no", out)
        self.assertIn("TIKTOK_BOX=absent", out)

    def test_the_scope_superset_is_the_owners_rule(self):
        for scope in ("user.info.basic", "user.info.profile", "user.info.stats", "video.list", "video.upload", "video.publish"):
            self.assertIn(scope, tt.SCOPES)


if __name__ == "__main__":
    unittest.main()
