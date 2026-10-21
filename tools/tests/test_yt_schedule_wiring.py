"""Owner, 17 Oct 2026: "YT_PRIVACY — I will want it scheduled in YouTube for the date intended to
go public." The uploader's scheduling is tested in test_yt_publish; this checks the lanes wire it."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"


class WiringTests(unittest.TestCase):
    def test_shorts_lane_carries_the_slot_and_switch_and_reports_scheduled(self):
        text = (WF / "youtube_scheduled.yml").read_text(encoding="utf-8")
        self.assertIn("YT_PUBLISH_HOUR_WAT: ${{ vars.YT_PUBLISH_HOUR_WAT }}", text)
        self.assertIn("YT_SCHEDULE: ${{ vars.YT_SCHEDULE }}", text)
        self.assertIn("PUBLISH_AT=$(marker YT_PUBLISH_AT)", text)
        self.assertIn('[ "$RESULT" = "scheduled" ]', text)
        self.assertIn('--publish-at "${PUBLISH_AT:-}"', text)

    def test_deepdive_lane_passes_the_episodes_intended_date(self):
        text = (WF / "deepdive.yml").read_text(encoding="utf-8")
        self.assertIn("PUBLISH_AT: ${{ steps.meta.outputs.publish_at }}", text)
        self.assertIn('--publish-at "$PUBLISH_AT"', text)
        self.assertIn('[ "$RESULT" = "scheduled" ]', text)

    def test_queue_items_may_name_their_date(self):
        text = (WF / "youtube_queue.yml").read_text(encoding="utf-8")
        self.assertIn("item.get('publish_at', '')", text)
        self.assertIn("'--publish-at', publish_at", text)

    def test_the_ledger_records_publish_at(self):
        tmp = Path(tempfile.mkdtemp()) / "ledger.json"
        subprocess.run([sys.executable, str(ROOT / "tools" / "youtube_ledger.py"), "--ledger", str(tmp), "record",
                        "--title", "T", "--video-id", "v1", "--date", "2026-10-20", "--state", "scheduled",
                        "--publish-at", "2026-10-20T18:00:00Z"], check=True, capture_output=True, text=True)
        rows = json.loads(tmp.read_text())
        rows = rows if isinstance(rows, list) else rows.get("entries") or rows.get("published") or list(rows.values())[0]
        self.assertEqual(rows[0]["publish_at"], "2026-10-20T18:00:00Z")
        subprocess.run([sys.executable, str(ROOT / "tools" / "youtube_ledger.py"), "--ledger", str(tmp), "record",
                        "--title", "T2", "--video-id", "v2", "--date", "2026-10-20"], check=True, capture_output=True, text=True)
        rows = json.loads(tmp.read_text())
        rows = rows if isinstance(rows, list) else rows.get("entries") or rows.get("published") or list(rows.values())[0]
        self.assertNotIn("publish_at", rows[0])

    def test_episode_meta_exposes_publish_at(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import deepdive
        src = Path(deepdive.__file__).read_text(encoding="utf-8")
        # episode.json's own date wins; without one, the publishing calendar's Deep-Dive slot
        # (Saturday 7:00pm Lagos) — never "today", which is the Shorts' slot (owner, 21 Oct 2026).
        self.assertIn('"publish_at": str(yt.get("publish_at") or default_publish_at())', src)
        import publish_calendar
        from datetime import datetime, timezone
        tue = datetime(2026, 10, 20, 2, 0, tzinfo=timezone.utc)                    # Tue 3:00am Lagos
        self.assertEqual(publish_calendar.iso_wat(publish_calendar.next_slot("deepdive", tue, taken=set())), "2026-10-24T19:00")
        self.assertEqual(deepdive.default_publish_at()[11:], "19:00")
        sat_late = datetime(2026, 10, 24, 17, 55, tzinfo=timezone.utc)             # Sat 6:55pm Lagos — too close
        self.assertEqual(publish_calendar.iso_wat(publish_calendar.next_slot("deepdive", sat_late, taken=set())), "2026-10-31T19:00")
        fri_night = datetime(2026, 10, 23, 19, 0, tzinfo=timezone.utc)             # Fri 8:00pm Lagos
        self.assertEqual(publish_calendar.iso_wat(publish_calendar.next_slot("shorts", fri_night)), "2026-10-26T19:00")
        self.assertEqual(publish_calendar.human(publish_calendar.next_slot("deepdive", tue, taken=set())), "Sat 24 Oct 2026, 7:00pm")

    def test_a_saturday_already_holding_an_episode_is_skipped(self):
        """Two Deep-Dives must never share a Saturday: the repo's ledgers say which are taken."""
        import json
        import tempfile
        sys.path.insert(0, str(ROOT / "tools"))
        import publish_calendar
        from datetime import datetime, timezone
        tue = datetime(2026, 10, 20, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(publish_calendar.iso_wat(publish_calendar.next_slot("deepdive", tue, taken={"2026-10-24"})),
                         "2026-10-31T19:00")
        self.assertEqual(publish_calendar.iso_wat(publish_calendar.next_slot("deepdive", tue, taken={"2026-10-24", "2026-10-31"})),
                         "2026-11-07T19:00")
        root = Path(tempfile.mkdtemp())
        (root / "logs").mkdir()
        (root / "logs" / "youtube_longform.json").write_text(json.dumps([
            {"title": "x", "publish_at": "2026-10-31T18:00:00Z"},            # scheduled upload → Sat 31 Oct Lagos
            {"title": "y", "publish_at": ""}]))
        (root / "logs" / "youtube_manage.json").write_text(json.dumps({"done": [
            {"action": "schedule 2026-10-24T19:00", "video_id": "JJhRcCgAxyQ", "result": "scheduled 2026-10-24T18:00:00Z"},
            {"action": "schedule 2026-11-07T19:00", "video_id": "pl5Z8ueg1ZI", "result": "already-public"}]}))
        self.assertEqual(publish_calendar.taken_deepdive_days(root), {"2026-10-24", "2026-10-31"})
        # The real repo: dd3 holds Sat 24 Oct, so the next episode lands on 31 Oct or later.
        self.assertIn("2026-10-24", publish_calendar.taken_deepdive_days())
        self.assertNotEqual(publish_calendar.iso_wat(publish_calendar.next_slot("deepdive", tue)), "2026-10-24T19:00")


if __name__ == "__main__":
    unittest.main()
