"""Regression tests for YouTube uploader exit status handling."""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import yt_publish  # noqa: E402


class PublisherExitStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.video_path = Path(self.temp_dir.name) / "short.mp4"
        self.video_path.write_bytes(b"test video")

    def _args(self):
        return ["--video", str(self.video_path), "--title", "Regression test"]

    def test_failed_upload_returns_nonzero_for_queue_workflow(self):
        stderr = io.StringIO()
        with patch.object(yt_publish, "upload_video", return_value=None) as upload:
            with redirect_stderr(stderr):
                exit_code = yt_publish.main(self._args())

        self.assertEqual(exit_code, 1)
        self.assertIn("queue workflows retain this item", stderr.getvalue())
        upload.assert_called_once()

    def test_successful_upload_returns_zero(self):
        out = io.StringIO()
        with patch.object(yt_publish, "upload_video", return_value="video123"):
            with redirect_stdout(out):
                exit_code = yt_publish.main(self._args())

        self.assertEqual(exit_code, 0)

    def test_successful_upload_emits_a_machine_readable_video_id(self):
        """The scheduled workflow greps this to record the publish in the ledger.

        Without it a Short can go live with no id captured, so the ledger
        entry — and the duplicate guard that depends on it — is lost.
        """
        out = io.StringIO()
        with patch.object(yt_publish, "upload_video", return_value="video123"):
            with redirect_stdout(out):
                exit_code = yt_publish.main(self._args())

        self.assertEqual(exit_code, 0)
        self.assertIn("VIDEO_ID=video123", out.getvalue())


if __name__ == "__main__":
    unittest.main()
