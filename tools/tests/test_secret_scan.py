"""tools/secret_scan.py — the gate that makes a public repository safe to be public."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import secret_scan as ss  # noqa: E402


class ShapesAreCaught(unittest.TestCase):
    def _hits(self, text):
        return [label for _, _, label, _ in ss.scan_text("x", text)]

    def test_the_two_shapes_that_actually_leaked_are_caught(self):
        # 20 Oct 2026: a BotFather token in a stray script and a 64-hex vault key in a fixture.
        # Built at runtime so this file never carries the shape itself (the scan reads tests too).
        bot = "8852331279" + ":AA" + "HU8f5hfM0GfkU5K0O5y1ZJ4UCahpbqBS1"[:33]
        key = "a3f9c2e17b84d605" + "2f1e9c4ab07d3e68" + "c5f2a1947be06d3c" + "8e1f5a2b9c7d4e07"
        self.assertEqual(self._hits('BOT_TOKEN="%s"' % bot), ["telegram bot token"])
        self.assertEqual(self._hits('"SOCIAL_TOKEN_KEY": "%s"' % key), ["64-hex vault key"])

    def test_the_other_shapes(self):
        samples = {
            "google api key": "key=AIza" + "b" * 35,
            "google access token": "ya29." + "A" * 40,
            "meta access token": "EAA" + "B" * 70,
            "github token": "ghp_" + "c" * 36,
            "tiktok token": "act." + "d" * 40,
            "payment key": "FLWSECK-" + "e" * 24,
            "private key block": "-----BEGIN RSA " + "PRIVATE KEY-----",
        }
        for label, text in samples.items():
            self.assertIn(label, self._hits(text), label)

    def test_obvious_fakes_and_hashes_pass(self):
        self.assertEqual(self._hits('"SOCIAL_TOKEN_KEY": "0f" * 32'), [])
        self.assertEqual(self._hits("KEY = '" + "0f" * 32 + "'"), [])
        self.assertEqual(self._hits('_lock_sha = "697e3233c630632bfa394317cc8902f0ab51e6d70670921c360d2161e6cff663"'), [])
        self.assertEqual(self._hits("sha256: " + "9" * 64), [])
        self.assertEqual(self._hits("TELEGRAM_BOT_TOKEN=123456789:AAH4k-testtokenvalueaaaaaaaaaaaaaaa"), [])

    def test_the_value_is_never_echoed_in_full(self):
        hits = ss.scan_text("x", "ghp_" + "c" * 36)
        self.assertTrue(all(len(h[3]) == 7 and h[3].endswith("…") for h in hits))


class TheTreeIsClean(unittest.TestCase):
    def test_tracked_files_carry_no_secret_shape(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "secret_scan.py")],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_files_that_leaked_are_gone_and_box_fixtures_are_fake(self):
        self.assertFalse((ROOT / "send_test_post.sh").exists())
        self.assertFalse((ROOT / "logs" / "2026-09-19-first-real-payment-webhook.json").exists())
        fixture = (ROOT / "tools" / "tests" / "test_tiktok_draft.py").read_text(encoding="utf-8")
        self.assertIn('"SOCIAL_TOKEN_KEY": "0f" * 32', fixture)

    def test_qa_runs_the_scan(self):
        qa = (ROOT / "tools" / "qa.py").read_text(encoding="utf-8")
        self.assertIn("secret_scan.py", qa)

    def test_ciphertext_is_skipped_on_purpose(self):
        # The vault's design: ciphertext in the repo, key in Actions. A box is not a finding.
        self.assertIn(".box", ss.SKIP_SUFFIX)


if __name__ == "__main__":
    unittest.main()
