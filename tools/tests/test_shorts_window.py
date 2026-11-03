"""3 Nov 2026, 12:46am: GitHub's cron fired the Monday-6pm Shorts run after midnight Lagos, tried to
make Tuesday's Short, failed and opened issue #183 — while the clock's 6pm dispatch had already
published Monday's. A raw cron run must stand down outside its window; dispatches always proceed."""
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


class ShortsWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / ".github" / "workflows" / "youtube_scheduled.yml").read_text(encoding="utf-8")
        cls.doc = yaml.safe_load(cls.text)

    def test_a_late_cron_stands_down_and_a_dispatch_always_runs(self):
        jobs = self.doc["jobs"]
        self.assertIn("window", jobs)
        gate = jobs["window"]["steps"][-1]["run"]
        self.assertIn('TZ=Africa/Lagos date +%-H', gate)
        self.assertIn('[ "$EVENT" != "schedule" ] || [ "$NOW" = "18" ] || [ "$NOW" = "19" ]', gate,
                      "the cron hour and one hour of scheduler lag; anything else is not 6pm")
        self.assertIn("no quota spent, no issue opened", gate)
        publish = jobs["generate-and-publish"]
        self.assertEqual(publish["needs"], "window")
        self.assertIn("needs.window.outputs.go == 'true'", publish["if"])
        self.assertIn("probe_only != 'true' || github.event_name == 'schedule'", publish["if"], "the probe path is unchanged")
        self.assertEqual(self.doc[True]["schedule"], [{"cron": "0 17 * * 1-5"}], "the window matches the only cron")


if __name__ == "__main__":
    unittest.main()
