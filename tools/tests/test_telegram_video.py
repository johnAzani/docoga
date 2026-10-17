"""tools/telegram_video.py — the Short as a native Telegram video, with the link as the net."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import telegram_video as tv  # noqa: E402


class R(object):
    def __init__(self, status, body):
        self.status_code, self._b = status, body
        self.content = json.dumps(body).encode()

    def json(self):
        return self._b


class TelegramVideoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.video = Path(self.tmp) / "short.mp4"
        self.video.write_bytes(b"\x00" * 2048)
        self.calls = []

    def post(self, answer):
        def _post(url, data=None, files=None, timeout=None):
            self.calls.append((url.rsplit("/", 1)[-1], data, files))
            return answer(url, data, files)
        return _post

    def test_the_video_is_uploaded_as_multipart_with_a_caption_under_1024(self):
        state, detail = tv.send("T", "@docogadaily", str(self.video), "Six months' notice — Lagos", "https://youtube.com/shorts/abc",
                                post=self.post(lambda u, d, f: R(200, {"ok": True, "result": {"message_id": 77}})))
        self.assertEqual(state, "sent", detail)
        method, data, files = self.calls[0]
        self.assertEqual(method, "sendVideo")
        self.assertIn("video", files)
        self.assertEqual(data["chat_id"], "@docogadaily")
        self.assertEqual(data["supports_streaming"], "true")
        self.assertIn("docoga.com.ng/?s=tg", data["caption"], "the channel-tagged link rides in the caption")
        self.assertIn("youtube.com/shorts/abc", data["caption"])
        self.assertLessEqual(len(data["caption"]), 1024)

    def test_a_refused_upload_falls_back_to_the_link(self):
        def answer(url, data, files):
            if url.endswith("sendVideo"):
                return R(400, {"ok": False, "description": "Bad Request: file is too big"})
            return R(200, {"ok": True, "result": {"message_id": 78}})
        state, detail = tv.send("T", "@c", str(self.video), "t", "https://youtube.com/shorts/abc", post=self.post(answer))
        self.assertEqual(state, "link")
        self.assertIn("file is too big", detail)
        self.assertEqual([c[0] for c in self.calls], ["sendVideo", "sendMessage"])

    def test_an_oversized_file_is_not_even_attempted(self):
        with mock.patch.object(tv, "MAX_BYTES", 1024):
            state, detail = tv.send("T", "@c", str(self.video), "t", "https://youtube.com/x",
                                    post=self.post(lambda u, d, f: R(200, {"ok": True, "result": {}})))
        self.assertEqual(state, "link")
        self.assertEqual([c[0] for c in self.calls], ["sendMessage"])
        self.assertIn("50 MB", detail)

    def test_missing_secrets_skip_quietly_and_exit_zero(self):
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}), redirect_stdout(io.StringIO()) as out:
            code = tv.main(["--video", str(self.video)])
        self.assertEqual(code, 0)
        self.assertIn("TELEGRAM_VIDEO=skipped", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class ParentLink(unittest.TestCase):
    """17 Oct 2026: the Short's Telegram caption names the Deep-Dive it trails."""

    def test_caption_carries_the_episode_when_given(self):
        text = tv.caption_for("Pay without a receipt. Pay twice. #Shorts", "https://youtube.com/shorts/abc",
                              "https://www.youtube.com/watch?v=NEW", "Rent Receipt in Nigeria (Deep-Dive 3)")
        self.assertTrue(text.startswith("Pay without a receipt. Pay twice.\n\n▶ The full Deep-Dive (9 min) — Rent Receipt"))
        self.assertIn("https://www.youtube.com/watch?v=NEW", text)
        self.assertNotIn("#Shorts", text)
        self.assertTrue(text.endswith("Watch on YouTube: https://youtube.com/shorts/abc"))
        self.assertLessEqual(len(text), 1024)

    def test_without_an_episode_the_caption_is_as_before(self):
        self.assertNotIn("Deep-Dive", tv.caption_for("t", "https://youtube.com/x"))
