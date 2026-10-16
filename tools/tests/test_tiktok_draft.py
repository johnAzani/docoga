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
        self.assertIn("TIKTOK_REFRESH_TOKEN", out)

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


if __name__ == "__main__":
    unittest.main()
