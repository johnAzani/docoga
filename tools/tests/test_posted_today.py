import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import posted_today  # noqa: E402


class PostedTodayTests(unittest.TestCase):
    """6 Nov 2026: GitHub's late cron ran the Instagram lane a second time inside the window on
    29 Oct, 3, 4 and 5 Nov; the caption guard refused the card, the Story (no caption) went to the
    tray twice each time. The ledger is the record both share."""

    def ledger(self, rows):
        d = tempfile.mkdtemp()
        p = pathlib.Path(d) / "instagram_sent.json"
        p.write_text(json.dumps(rows), encoding="utf-8")
        return p

    def test_counts_the_lanes_own_rows_for_the_day_and_ignores_the_reels(self):
        p = self.ledger([
            {"recorded_at": "2026-11-05T19:14:01+01:00", "date": "2026-11-05", "topic": "instagram-card"},
            {"recorded_at": "2026-11-05T19:14:01+01:00", "date": "2026-11-05", "topic": "instagram-story"},
            {"recorded_at": "2026-11-05T18:40:00+01:00", "date": "2026-11-05", "topic": "Pay the wrong agent. Lose the flat."},
            {"recorded_at": "2026-11-04T19:14:01+01:00", "date": "2026-11-04", "topic": "instagram-card"},
        ])
        self.assertEqual(posted_today.posted_today(p, "2026-11-05"), 3)
        self.assertEqual(posted_today.posted_today(p, "2026-11-05", "instagram-"), 2)
        self.assertEqual(posted_today.posted_today(p, "2026-11-06", "instagram-"), 0)

    def test_falls_back_to_recorded_at_in_lagos_time(self):
        p = self.ledger([{"recorded_at": "2026-11-05T23:30:00+00:00", "topic": "instagram-story"}])  # 00:30 Lagos, 6 Nov
        self.assertEqual(posted_today.posted_today(p, "2026-11-06", "instagram-"), 1)
        self.assertEqual(posted_today.posted_today(p, "2026-11-05", "instagram-"), 0)

    def test_a_broken_or_missing_ledger_never_silences_the_lane(self):
        self.assertEqual(posted_today.posted_today("/nonexistent/ledger.json", "2026-11-05"), 0)
        d = tempfile.mkdtemp()
        p = pathlib.Path(d) / "x.json"
        p.write_text("{not json", encoding="utf-8")
        self.assertEqual(posted_today.posted_today(p, "2026-11-05"), 0)

    def test_the_instagram_slot_gate_asks_the_ledger_before_the_hour(self):
        wf = (ROOT / ".github/workflows/instagram_autopost.yml").read_text(encoding="utf-8")
        gate = wf.split("Slot gate", 1)[1].split("publish:", 1)[0]
        self.assertIn("tools/posted_today.py logs/instagram_sent.json --topic instagram-", gate)
        self.assertLess(gate.index("posted_today.py"), gate.index('[ "$NOW" = "$WANT" ]'))
        self.assertIn('[ "$EVENT" = "schedule" ] && [ "${DONE:-0}" != "0" ]', gate, "a manual dispatch still posts")


if __name__ == "__main__":
    unittest.main()
