"""Tests for the unattended Shorts publish ledger.

The scheduled workflow publishes **public, twice a week, with nobody
watching**. The ledger is the only thing standing between a re-run and a
duplicate Short on the channel, so these tests cover the two ways it can fail
dangerously:

* failing to block a duplicate (the channel gets a repeat upload);
* blocking a publish that is not a duplicate, or blocking forever because the
  ledger file is damaged (the channel goes quiet).

Both directions are tested, because a guard that cannot fail is not a guard.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import youtube_ledger as ledger  # noqa: E402


class LedgerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "youtube_published.json")

    def run_cli(self, argv, ledger_path=None):
        """`--ledger` is a top-level option, so it must precede the subcommand.

        Passing it after the subcommand is a loud argparse error, not a silent
        fall back to the real repo ledger — which is the behaviour we want.
        """
        out = io.StringIO()
        with redirect_stdout(out):
            code = ledger.main(["--ledger", ledger_path or self.path] + list(argv))
        return code, out.getvalue()

    def publish(self, title="Keep a Rent Paper Trail #Shorts", date="2026-10-09", video_id="abc123", **extra):
        return self.run_cli(
            [
                "record",
                "--title", title,
                "--video-id", video_id,
                "--url", "https://youtube.com/watch?v=%s" % video_id,
                "--privacy", "public",
                "--date", date,
                "--run-id", "1",
            ]
            + [item for pair in extra.items() for item in ("--%s" % pair[0].replace("_", "-"), str(pair[1]))]
        )


class DuplicateGuardTests(LedgerTestCase):
    def test_missing_ledger_is_clear_to_publish(self):
        code, out = self.run_cli(["check", "--title", "Anything #Shorts", "--date", "2026-10-09"])
        self.assertEqual(code, ledger.EXIT_CLEAR, out)
        self.assertIn("No recent duplicate", out)

    def test_same_title_same_day_is_blocked(self):
        self.publish()
        code, out = self.run_cli(["check", "--title", "Keep a Rent Paper Trail #Shorts", "--date", "2026-10-09"])
        self.assertEqual(code, ledger.EXIT_DUPLICATE, out)
        self.assertIn("already in the ledger", out)

    def test_retry_two_days_later_is_still_blocked(self):
        """A GitHub re-run or a manual re-dispatch lands inside the window."""
        self.publish(date="2026-10-09")
        code, _ = self.run_cli(["check", "--title", "Keep a Rent Paper Trail #Shorts", "--date", "2026-10-11"])
        self.assertEqual(code, ledger.EXIT_DUPLICATE)

    def test_the_natural_three_week_rotation_is_not_blocked(self):
        """6 topics x 2 runs/week = a title returns after ~3 weeks. That is intended."""
        self.publish(date="2026-10-09")
        code, out = self.run_cli(["check", "--title", "Keep a Rent Paper Trail #Shorts", "--date", "2026-10-30"])
        self.assertEqual(code, ledger.EXIT_CLEAR, out)

    def test_a_different_title_on_the_same_day_is_allowed(self):
        self.publish(title="Keep a Rent Paper Trail #Shorts")
        code, _ = self.run_cli(["check", "--title", "Before You Pay an Agent #Shorts", "--date", "2026-10-09"])
        self.assertEqual(code, ledger.EXIT_CLEAR)

    def test_title_matching_is_case_and_whitespace_insensitive(self):
        self.publish(title="Keep a Rent Paper Trail #Shorts")
        code, _ = self.run_cli(["check", "--title", "  keep a rent paper trail #shorts ", "--date", "2026-10-09"])
        self.assertEqual(code, ledger.EXIT_DUPLICATE)

    def test_record_then_check_round_trip(self):
        """Proves the guard actually trips on the state the workflow writes."""
        code, _ = self.run_cli(["check", "--title", "Tenancy Agreement Checklist #Shorts", "--date", "2026-10-13"])
        self.assertEqual(code, ledger.EXIT_CLEAR)
        self.publish(title="Tenancy Agreement Checklist #Shorts", date="2026-10-13", video_id="xyz789")
        code, _ = self.run_cli(["check", "--title", "Tenancy Agreement Checklist #Shorts", "--date", "2026-10-13"])
        self.assertEqual(code, ledger.EXIT_DUPLICATE)


class LedgerIntegrityTests(LedgerTestCase):
    def test_corrupt_ledger_never_blocks_publishing(self):
        Path(self.path).write_text("{ this is not json", encoding="utf-8")
        code, _ = self.run_cli(["check", "--title", "Anything #Shorts", "--date", "2026-10-09"])
        self.assertEqual(code, ledger.EXIT_CLEAR)

    def test_corrupt_ledger_is_backed_up_not_silently_overwritten(self):
        Path(self.path).write_text("{ this is not json", encoding="utf-8")
        self.run_cli(["check", "--title", "Anything #Shorts", "--date", "2026-10-09"])
        backups = list(Path(self.tmp.name).glob("youtube_published.json.corrupt-*"))
        self.assertEqual(len(backups), 1, "the damaged history must be recoverable")
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "{ this is not json")

    def test_wrong_shaped_ledger_never_blocks_publishing(self):
        Path(self.path).write_text('{"entries": "not a list"}', encoding="utf-8")
        code, _ = self.run_cli(["check", "--title", "Anything #Shorts", "--date", "2026-10-09"])
        self.assertEqual(code, ledger.EXIT_CLEAR)

    def test_undated_entry_is_treated_as_recent_rather_than_ignored(self):
        Path(self.path).write_text(json.dumps([{"title": "Anything #Shorts", "video_id": "old"}]), encoding="utf-8")
        code, _ = self.run_cli(["check", "--title", "Anything #Shorts", "--date", "2026-10-09"])
        self.assertEqual(code, ledger.EXIT_DUPLICATE)

    def test_a_bad_date_is_a_usage_error_not_a_duplicate(self):
        """Exit 3 means 'skip, nothing to do'. Bad input must never look like that."""
        code, _ = self.run_cli(["check", "--title", "Anything #Shorts", "--date", "09-10-2026"])
        self.assertEqual(code, ledger.EXIT_USAGE)
        self.assertNotEqual(code, ledger.EXIT_DUPLICATE)


class LedgerGrowthTests(LedgerTestCase):
    def test_newest_entry_is_first(self):
        self.publish(title="First #Shorts", date="2026-10-09", video_id="v1")
        self.publish(title="Second #Shorts", date="2026-10-13", video_id="v2")
        entries = ledger.load(self.path)
        self.assertEqual([e["video_id"] for e in entries], ["v2", "v1"])

    def test_re_recording_the_same_video_id_does_not_duplicate_it(self):
        self.publish(video_id="v1", size_bytes=100)
        self.publish(video_id="v1", size_bytes=100)
        self.assertEqual(len(ledger.load(self.path)), 1)

    def test_ledger_is_capped_so_the_repo_cannot_grow_forever(self):
        real_max = ledger.MAX_ENTRIES
        ledger.MAX_ENTRIES = 5
        self.addCleanup(setattr, ledger, "MAX_ENTRIES", real_max)
        for i in range(9):
            self.publish(title="Short %d" % i, date="2026-10-09", video_id="v%d" % i)
        entries = ledger.load(self.path)
        self.assertEqual(len(entries), 5)
        # The newest publish survives the trim — the one we just made.
        self.assertEqual(entries[0]["video_id"], "v8")

    def test_show_prints_recent_publishes(self):
        self.publish(title="First #Shorts", date="2026-10-09", video_id="v1")
        code, out = self.run_cli(["show"])
        self.assertEqual(code, ledger.EXIT_CLEAR)
        self.assertIn("First #Shorts", out)
        self.assertIn("https://youtube.com/watch?v=v1", out)

    def test_record_keeps_the_topic_and_size_the_workflow_passes(self):
        self.publish(title="First #Shorts", date="2026-10-09", video_id="v1", topic="First", size_bytes=1234)
        entry = ledger.load(self.path)[0]
        self.assertEqual(entry["topic"], "First")
        self.assertEqual(entry["size_bytes"], 1234)
        self.assertEqual(entry["privacy"], "public")


if __name__ == "__main__":
    unittest.main()
