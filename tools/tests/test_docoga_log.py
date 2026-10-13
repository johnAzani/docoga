"""One answer for "where do the scratch files live", and the invariant that keeps it one.

`logs/social_media.log` is written by four scripts. For a while it was written by the
test suite too — 1,468 lines of simulated publishes in the file a human would read as
evidence — because each script computed the path itself, relative to the current
directory, and nothing redirected it. The fix is a shared helper plus two rules, and
this file is what stops the third regression (someone adding a fifth script with a
hand-rolled path) from undoing it.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import docoga_log  # noqa: E402

SOCIAL_SCRIPTS = ("post_facebook.py", "generate_facebook_content.py",
                  "generate_telegram_content.py", "post_telegram.py",
                  "post_telegram_video.py")


class HelperTests(unittest.TestCase):
    def test_the_default_is_rooted_at_the_repo_not_at_the_cwd(self):
        env = {key: value for key, value in os.environ.items() if key != "DOCOGA_LOG_DIR"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(docoga_log.log_dir(), ROOT / "logs")
            self.assertEqual(docoga_log.log_file("x.log"), ROOT / "logs" / "x.log")

    def test_the_override_moves_the_whole_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"DOCOGA_LOG_DIR": tmp}):
                path = docoga_log.log_file("social_media.log")
                self.assertEqual(str(path.parent), tmp)
                self.assertTrue(path.parent.is_dir(), "log_file() creates the directory")

    def test_a_missing_directory_is_created_once_and_never_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = os.path.join(tmp, "a", "b")
            with patch.dict(os.environ, {"DOCOGA_LOG_DIR": nested}):
                path = docoga_log.log_file("x.log")
            self.assertTrue(Path(nested).is_dir())
            self.assertTrue(str(path).endswith("x.log"))

    def test_append_survives_an_unwritable_target(self):
        """A log is bookkeeping. The channel's post is the product."""
        with tempfile.TemporaryDirectory() as tmp:
            blocked = Path(tmp) / "nope" / "deep" / "x.log"   # parent does not exist
            self.assertFalse(docoga_log.append(blocked, "line\n"))
            good = Path(tmp) / "x.log"
            self.assertTrue(docoga_log.append(good, "line\n"))
            self.assertEqual(good.read_text(encoding="utf-8"), "line\n")


class NoStrayPathsTests(unittest.TestCase):
    def test_no_social_script_composes_its_own_log_path(self):
        """`Path("logs/…")` relative to the cwd is how a stray `logs/` directory and a
        polluted repo log both happened. One helper, and the scripts ask it."""
        for name in SOCIAL_SCRIPTS:
            text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            with self.subTest(script=name):
                self.assertNotIn('Path("logs/', text,
                                 "%s builds its own log path; use docoga_log.log_file()" % name)
                self.assertIn("docoga_log", text, "%s does not use the helper" % name)

    def test_the_helper_is_the_only_place_the_repo_root_is_assumed(self):
        text = (ROOT / "tools" / "docoga_log.py").read_text(encoding='utf-8')
        self.assertIn("parents[1]", text)
        self.assertIn("DOCOGA_LOG_DIR", text)

    def test_the_repo_log_is_not_written_by_the_test_suite(self):
        """Asserted structurally, not by watching the file: the suite sets
        `DOCOGA_LOG_DIR` before importing any social script, so the repo's own log is
        out of reach however the tests are ordered."""
        for name in ("test_post_facebook.py", "test_post_facebook_reels.py",
                     "test_post_telegram.py", "test_post_telegram_ledger.py"):
            text = (ROOT / "tools" / "tests" / name).read_text(encoding="utf-8")
            guard_at = text.index("DOCOGA_LOG_DIR")
            found = [text.find(marker) for marker in ("import post_", "import generate_")
                     if text.find(marker) >= 0]
            self.assertTrue(found, "%s imports no social script at all" % name)
            first_import = min(found)
            with self.subTest(module=name):
                self.assertLess(guard_at, first_import,
                                "the env guard must run before the scripts are imported")


if __name__ == "__main__":
    unittest.main(verbosity=2)
