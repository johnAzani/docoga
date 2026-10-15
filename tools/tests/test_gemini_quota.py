"""The narrator's bucket, known rather than guessed (tools/gemini_quota.py + narrator_resume.yml).

Owner, 15 Oct 2026: "I want to automatically know when the voice over resets and
automatically continue at that time instead of a retry cron three hours after."
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import gemini_quota as q  # noqa: E402

try:
    import yaml
    YAML_OK = True
except ImportError:
    YAML_OK = False

UTC = timezone.utc

DAY_REFUSAL = json.dumps({"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
    "message": "You exceeded your current quota, please check your plan and billing details. Please retry in 23.5s.",
    "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
            {"quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
             "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
             "quotaDimensions": {"model": "gemini-2.5-flash-preview-tts", "location": "global"},
             "quotaValue": "10"}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "23s"}]}})

MINUTE_REFUSAL = DAY_REFUSAL.replace("GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                                     "GenerateRequestsPerMinutePerProjectPerModel-FreeTier").replace('"quotaValue": "10"', '"quotaValue": "3"')


class RefusalTests(unittest.TestCase):
    def test_a_daily_refusal_is_read_whole(self):
        r = q.parse_refusal(DAY_REFUSAL)
        self.assertEqual(r["scope"], "day")
        self.assertEqual(r["limit"], 10)
        self.assertEqual(r["model"], "gemini-2.5-flash-preview-tts")
        self.assertAlmostEqual(r["retry_s"], 23.5)

    def test_a_per_minute_refusal_is_a_short_wait(self):
        r = q.parse_refusal(MINUTE_REFUSAL)
        self.assertEqual(r["scope"], "minute")
        self.assertEqual(r["limit"], 3)
        self.assertAlmostEqual(q.wait_seconds(r), 23.5)

    def test_a_daily_refusal_waits_for_the_pacific_midnight_not_the_retry_delay(self):
        """The API says 'retry in 23 s' even when the DAY is spent. The machine knows better."""
        now = datetime(2026, 10, 15, 8, 24, tzinfo=UTC)          # 09:24 WAT, 01:24 Pacific (PDT)
        wait = q.wait_seconds(q.parse_refusal(DAY_REFUSAL), now)
        self.assertGreater(wait, 22 * 3600)
        self.assertLess(wait, 23 * 3600)

    def test_an_unstructured_body_still_yields_a_sane_answer(self):
        r = q.parse_refusal("Resource has been exhausted (e.g. check quota). retry in 40s")
        self.assertEqual(r["scope"], "unknown")
        self.assertAlmostEqual(q.wait_seconds(r), 40.0)


class ResetClockTests(unittest.TestCase):
    def test_reset_is_midnight_pacific_in_summer_and_winter(self):
        # 15 Oct 2026: PDT → 07:00 UTC. 6 Nov 2026 (after the 1 Nov change): PST → 08:00 UTC.
        self.assertEqual(q.next_reset(datetime(2026, 10, 15, 9, 0, tzinfo=UTC)), datetime(2026, 10, 16, 7, 0, tzinfo=UTC))
        self.assertEqual(q.next_reset(datetime(2026, 11, 6, 9, 0, tzinfo=UTC)), datetime(2026, 11, 7, 8, 0, tzinfo=UTC))

    def test_no_hour_is_hard_coded(self):
        src = (ROOT / "tools" / "gemini_quota.py").read_text(encoding="utf-8")
        self.assertIn("America/Los_Angeles", src)
        self.assertNotRegex(src, r"next_reset.*\b0?7\b.*utc", "the reset comes from the zone, not a UTC hour")

    def test_just_reset_window(self):
        self.assertTrue(q.just_reset(datetime(2026, 10, 16, 7, 12, tzinfo=UTC), 45))     # 00:12 PDT
        self.assertFalse(q.just_reset(datetime(2026, 10, 16, 8, 12, tzinfo=UTC), 45))    # 01:12 PDT
        self.assertTrue(q.just_reset(datetime(2026, 11, 7, 8, 12, tzinfo=UTC), 45))      # 00:12 PST
        self.assertFalse(q.just_reset(datetime(2026, 11, 7, 7, 12, tzinfo=UTC), 45))     # 23:12 PST, day before

    def test_the_two_cron_lines_cover_both_seasons_and_only_one_fires(self):
        """07:12 and 08:12 UTC: in each season exactly one is within 45 min of a Pacific midnight."""
        for day in (datetime(2026, 10, 16, tzinfo=UTC), datetime(2026, 11, 7, tzinfo=UTC), datetime(2027, 3, 20, tzinfo=UTC)):
            hits = [h for h in (7, 8) if q.just_reset(day.replace(hour=h, minute=12), 45)]
            self.assertEqual(len(hits), 1, (day, hits))

    def test_lagos_rendering(self):
        self.assertTrue(q.lagos(datetime(2026, 10, 16, 7, 0, tzinfo=UTC)).startswith("08:00 WAT"))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = patch.object(q, "LEDGER", Path(self.tmp.name) / "quota.json")
        self.p.start()
        self.addCleanup(self.p.stop)
        self.now = datetime(2026, 10, 15, 8, 24, tzinfo=UTC)

    def test_requests_are_counted_per_pacific_day_and_per_lane(self):
        with patch.dict(os.environ, {"NARRATOR_LANE": "deepdive"}):
            for _ in range(4):
                q.note_request("m", "ok", now=self.now)
        with patch.dict(os.environ, {"NARRATOR_LANE": "shorts"}):
            q.note_request("m", "ok", now=self.now)
        st = q.state(self.now)
        self.assertEqual(st["used"], 5)
        data = q.load(self.now)
        self.assertEqual(data["requests"]["m"]["by_lane"], {"deepdive": 4, "shorts": 1})

    def test_a_daily_refusal_teaches_the_limit_and_the_resume_time(self):
        q.note_request("m", "exhausted", q.parse_refusal(DAY_REFUSAL), now=self.now)
        st = q.state(self.now)
        self.assertTrue(st["exhausted"])
        self.assertTrue(st["limit_known"])
        self.assertEqual(st["limit"], 10)
        self.assertEqual(st["resumes_at"], datetime(2026, 10, 16, 7, 0, tzinfo=UTC))
        self.assertIn("EXHAUSTED", q.status_line(self.now))
        self.assertIn("08:00 WAT", q.status_line(self.now))

    def test_the_new_pacific_day_clears_the_count_but_keeps_the_learnt_limit(self):
        q.note_request("m", "exhausted", q.parse_refusal(DAY_REFUSAL), now=self.now)
        later = datetime(2026, 10, 16, 7, 5, tzinfo=UTC)
        st = q.state(later)
        self.assertEqual(st["used"], 0)
        self.assertFalse(st["exhausted"])
        self.assertEqual(st["limit"], 10)

    def test_remaining_uses_the_hint_until_the_api_speaks(self):
        enough, left = q.remaining(need=6, now=self.now)
        self.assertTrue(enough)
        self.assertEqual(left, q.DEFAULT_DAILY_LIMIT_HINT)
        for _ in range(q.DEFAULT_DAILY_LIMIT_HINT - 2):
            q.note_request("m", "ok", now=self.now)
        enough, left = q.remaining(need=6, now=self.now)
        self.assertFalse(enough)
        self.assertEqual(left, 2)

    def test_an_unwritable_ledger_never_fails_a_render(self):
        with patch.object(q, "LEDGER", Path("/proc/does-not-exist/quota.json")):
            q.note_request("m", "ok", now=self.now)   # no raise
            self.assertEqual(q.state(self.now)["used"], 0)


class OwedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "logs").mkdir()

    def ledgers(self, shorts=(), reels=()):
        (self.root / "logs" / "youtube_published.json").write_text(json.dumps(
            [{"title": "t", "date": d, "state": "published"} for d in shorts]), encoding="utf-8")
        (self.root / "logs" / "facebook_reels.json").write_text(json.dumps(
            [{"title": "t", "date": d, "state": "uploaded"} for d in reels]), encoding="utf-8")

    # Calendar: Mon 12 · Tue 13 · Wed 14 · Thu 15 · Fri 16 · Sat 17 · Sun 18 · Mon 19 · Tue 20 Oct 2026.
    # Shorts: Tue/Fri 17:00 UTC. Reels: Mon/Thu 08:30 UTC. Look-back: 3 days.

    def test_nothing_owed_before_the_slot_passes(self):
        self.ledgers(shorts=["2026-10-13"], reels=["2026-10-15"])
        # Friday 07:10 UTC: today's Short is due at 17:00 — not owed yet; Tue and Thu are settled.
        self.assertEqual(q.owed(datetime(2026, 10, 16, 7, 10, tzinfo=UTC), self.root), [])

    def test_a_missed_short_is_owed_the_next_morning(self):
        self.ledgers(shorts=["2026-10-13"], reels=["2026-10-15"])
        got = q.owed(datetime(2026, 10, 17, 7, 10, tzinfo=UTC), self.root)   # Saturday morning
        self.assertEqual(got, [{"lane": "shorts", "date": "2026-10-16"}])

    def test_a_publish_since_the_slot_settles_it(self):
        """15 Oct: the Tue 13 slot had no entry, but hand-runs published on 14 and 15 → nothing owed."""
        self.ledgers(shorts=["2026-10-14", "2026-10-15"], reels=["2026-10-15"])
        self.assertEqual(q.owed(datetime(2026, 10, 15, 23, 0, tzinfo=UTC), self.root), [])

    def test_a_missed_reel_is_owed(self):
        self.ledgers(shorts=["2026-10-16"], reels=["2026-10-15"])
        got = q.owed(datetime(2026, 10, 20, 7, 10, tzinfo=UTC), self.root)   # Tue; Mon 19 Reel slot passed
        self.assertEqual(got, [{"lane": "reel", "date": "2026-10-19"}])

    def test_old_debts_are_forgotten(self):
        self.ledgers()
        got = q.owed(datetime(2026, 10, 17, 7, 10, tzinfo=UTC), self.root)   # Sat: Fri Short (1 back) + Thu Reel (2 back)
        self.assertEqual([g["lane"] for g in got], ["shorts", "reel"])
        got = q.owed(datetime(2026, 10, 19, 7, 10, tzinfo=UTC), self.root)   # Mon 07:10: Fri Short 3 back; Thu Reel 4 back → gone
        self.assertEqual([g["lane"] for g in got], ["shorts"])


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = q.main(list(argv))
        return code, buf.getvalue()

    def test_status_and_resets_at(self):
        with patch.object(q, "LEDGER", Path(tempfile.mkdtemp()) / "q.json"):
            code, out = self.run_cli("status")
        self.assertEqual(code, 0)
        self.assertIn("narrator bucket", out)
        code, out = self.run_cli("resets-at")
        self.assertEqual(code, 0)
        self.assertIn("+01:00", out, "the reset is printed in Lagos time")

    def test_just_reset_writes_a_step_output(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as fh:
            path = fh.name
        with patch.dict(os.environ, {"GITHUB_OUTPUT": path}):
            self.run_cli("just-reset", "--window", "45")
        self.assertRegex(Path(path).read_text(), r"just_reset=(yes|no)")


@unittest.skipUnless(YAML_OK, "PyYAML not installed")
class ResumerWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.doc = yaml.safe_load((ROOT / ".github" / "workflows" / "narrator_resume.yml").read_text(encoding="utf-8"))
        self.steps = {s.get("name"): s for s in self.doc["jobs"]["resume"]["steps"]}

    def test_two_cron_lines_one_per_season(self):
        crons = [c["cron"] for c in self.doc[True]["schedule"]]
        self.assertEqual(crons, ["12 7 * * *", "12 8 * * *"])

    def test_the_reset_check_gates_everything_and_has_a_tight_window(self):
        check = self.steps["Did a Pacific midnight just pass?"]
        self.assertIn("just-reset --window 45", check["run"])
        for name, step in self.steps.items():
            if name in ("Check out the repository", "Set up Python", "Did a Pacific midnight just pass?", "Run summary"):
                continue
            self.assertIn("steps.reset.outputs.go == 'yes'", step.get("if", ""), name)

    def test_warm_up_then_save_then_dispatch_in_that_order(self):
        names = list(self.steps)
        warm = names.index("Warm up — today's narration into the cache (no render, no publish)")
        save = names.index("Save the narrator's cached clips and the quota ledger")
        owed = names.index("What is owed? (a slot passed, nothing published since)")
        short = names.index("Resume the Short that is owed")
        reel = names.index("Resume the Reel that is owed")
        self.assertLess(warm, save)
        self.assertLess(save, owed)
        self.assertLess(owed, short)
        self.assertLess(owed, reel)

    def test_dispatches_carry_the_owed_date_and_the_token_can_dispatch(self):
        self.assertEqual(self.doc["permissions"]["actions"], "write")
        short = self.steps["Resume the Short that is owed"]["run"]
        reel = self.steps["Resume the Reel that is owed"]["run"]
        self.assertIn("gh workflow run youtube_scheduled.yml", short)
        self.assertIn('-f for_date="$FOR_DATE"', short)
        self.assertIn("gh workflow run facebook_autopost.yml", reel)
        self.assertIn("-f mode=reel", reel)
        self.assertIn('-f for_date="$FOR_DATE"', reel)

    def test_the_lanes_accept_for_date(self):
        for wf in ("youtube_scheduled.yml", "facebook_autopost.yml"):
            doc = yaml.safe_load((ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8"))
            self.assertIn("for_date", doc[True]["workflow_dispatch"]["inputs"], wf)

    def test_warm_up_never_reddens_the_run(self):
        warm = self.steps["Warm up — today's narration into the cache (no render, no publish)"]
        self.assertEqual(warm["env"]["SHORTS_VOICE"], "optional")
        self.assertIn("set +e", warm["run"])


if __name__ == "__main__":
    unittest.main()
