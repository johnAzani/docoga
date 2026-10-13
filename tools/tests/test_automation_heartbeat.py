"""The heartbeat's own behaviour — and it is the one tool here with no second opinion.

Every other automation in this repo is checked by "did the post land?". Nothing
checks *that* the checkers still run, which is the gap that let a lane sit red for six
mornings and another be described as live for two weeks at zero runs. So this suite is
about whether the judge is right:

  * the cadence arithmetic, because the silence deadline is derived from each cron
    rather than from a table someone forgets to update;
  * every verdict kind, including the two that must *not* alarm (a brand-new lane,
    and a lane whose schedule only exists on an unmerged branch);
  * the signature, because "red only when the set of broken lanes changes" is what
    makes a daily monitor readable instead of muted;
  * and the failure it must never survive: reporting "all clear" when it could not
    fetch anything.

Fixtures replay real recorded shapes (see `--fixture`), so the HTTP layer is not
mocked away — `GitHub.get` is the code under test too.
"""

import base64
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for rel in ("tools", "scripts"):
    if str(ROOT / rel) not in sys.path:
        sys.path.insert(0, str(ROOT / rel))

import automation_heartbeat as hb  # noqa: E402

NOW = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "automation-heartbeat.yml"


def lane(file="telegram_autopost.yml", name="DocOga Telegram Auto-Post", crons=("0 8 * * *",),
          scheduled=True, error=None):
    out = {"file": file, "name": name, "crons": list(crons), "scheduled": scheduled,
           "path": ".github/workflows/" + file, "dispatch": True}
    if error:
        out["error"] = error
    return out


def info(state="active", wf_id=777):
    return {"id": wf_id, "state": state, "name": "whatever"}


def run(hours_ago=3, conclusion="success", status="completed"):
    return {"created_at": NOW - timedelta(hours=hours_ago), "updated_at": NOW,
            "status": status, "conclusion": conclusion,
            "url": "https://github.com/o/r/actions/runs/1", "branch": "main",
            "event": "schedule", "title": "x"}


def judge(one_lane=None, one_info=None, runs=None, since=None, **kwargs):
    options = {"grace": kwargs.pop("grace", hb.DEFAULT_LANE_GRACE),
               "jitter": kwargs.pop("jitter", hb.SCHEDULE_JITTER),
               "misses": kwargs.pop("misses", hb.MISSES_BEFORE_SILENT)}
    options.update(kwargs)
    return hb.judge(one_lane or lane(), one_info if one_info is not None else info(),
                    runs if runs is not None else [run()],
                    since if since is not None else NOW - timedelta(days=30), NOW, **options)


class CadenceTests(unittest.TestCase):
    """The deadline is computed from the cron. A typo here silences the monitor."""

    def gap(self, *crons):
        return hb.expected_gap(list(crons), start=NOW - timedelta(days=hb.CRON_WINDOW_DAYS))

    def test_a_minute_offset_is_not_rounded_away(self):
        """`30 8 * * *` is still a 24 h cadence. A scan aligned to 15 or 60 minutes
        either finds no fire at all or the wrong one, and either mistake moves the
        silence deadline by hours."""
        self.assertEqual(self.gap("30 8 * * *")[0], 86400)
        self.assertEqual(self.gap("7 0 * * *")[0], 86400)

    def test_a_daily_cron_measures_one_day(self):
        gap, detail = self.gap("0 8 * * *")
        self.assertEqual(gap, 86400)
        self.assertIn("24.0h", detail)

    def test_two_crons_a_day_measure_the_shorter_gap(self):
        self.assertEqual(self.gap("0 8 * * *", "0 20 * * *")[0], 43200)

    def test_the_shorts_cron_measures_the_weekend(self):
        """`0 17 * * 2,5` — Tue and Fri. The gap a monitor must tolerate is Fri→Tue,
        four days, not the two days between Tue and Fri: judging by the short one is
        how a twice-weekly lane gets a false alarm every weekend."""
        gap, _ = self.gap("0 17 * * 2,5")
        self.assertEqual(gap, 4 * 86400)

    def test_aliases_are_cadences_too(self):
        self.assertEqual(self.gap("@daily")[0], 86400)
        self.assertEqual(self.gap("@hourly")[0], 3600)

    def test_business_hours_measures_the_weekend_gap(self):
        # Fri 17:45 → Mon 09:00 = 2 days + 15 h 15 min
        gap, _ = self.gap("*/15 9-17 * * 1-5")
        self.assertEqual(gap, 2 * 86400 + 15 * 3600 + 15 * 60)

    def test_a_monthly_cron_is_not_mistaken_for_a_daily_one(self):
        gap, _ = self.gap("0 0 1 * *")
        self.assertGreaterEqual(gap, 28 * 86400)

    def test_an_unreadable_expression_is_a_finding_not_a_default(self):
        gap, detail = self.gap("0 8 * *")
        self.assertIsNone(gap)
        self.assertIn("not readable", detail)

    def test_a_cron_that_never_matches_is_reported(self):
        gap, detail = self.gap("0 0 30 2 *")          # 30 February
        self.assertIsNone(gap)
        self.assertIn("matches nothing", detail)   # greppable in the issue body

    def test_out_of_range_fields_are_rejected(self):
        for bad in ("0 8 * * 8", "61 8 * * *", "0 25 * * *", "0 8 * * */0"):
            with self.subTest(cron=bad):
                with self.assertRaises(ValueError):
                    hb.parse_cron(bad)

    def test_lists_ranges_and_steps_are_all_parsed(self):
        fields = hb.parse_cron("0,30 9-11 * * 1,3,5")
        self.assertEqual(sorted(fields[0]), [0, 30])
        self.assertEqual(sorted(fields[1]), [9, 10, 11])
        self.assertEqual(sorted(fields[4]), [1, 3, 5])


class VerdictTests(unittest.TestCase):
    def test_a_lane_that_ran_recently_is_ok(self):
        verdict = judge(runs=[run(hours_ago=3)])
        self.assertEqual(verdict["status"], "ok")
        self.assertEqual(verdict["streak"], 0)
        self.assertIn("succeeded", verdict["reason"])

    def test_the_silence_deadline_is_two_cadences_plus_scheduler_slack(self):
        verdict = judge(runs=[run(hours_ago=24 * 10)])
        self.assertEqual((verdict["status"], verdict["kind"]), ("fail", "silent"))
        self.assertEqual(verdict["silent_after"], 2 * 86400 + 12 * 3600)

    def test_one_missed_cycle_is_a_note_not_an_alarm(self):
        """A daily lane 36 h after its last success is inside one tolerated miss: the
        deadline is 2 cycles + slack. A monitor that fires on the first miss is wrong
        about the schedule, and gets muted inside a week."""
        verdict = judge(runs=[run(hours_ago=36)])
        self.assertEqual(verdict["status"], "ok")
        self.assertIn("ran 36.0h and succeeded", verdict["reason"])
        failed_once = judge(runs=[run(hours_ago=36, conclusion="failure"),
                                  run(hours_ago=60, conclusion="success")])
        self.assertEqual(failed_once["status"], "ok")
        self.assertIn("inside one cycle", failed_once["reason"])

    def test_the_boundary_is_strict(self):
        at_limit = judge(runs=[run(hours_ago=(2 * 24 + 12))])
        just_past = judge(runs=[run(hours_ago=(2 * 24 + 12), conclusion="failure"),
                               run(hours_ago=(2 * 86400 + 43200) / 3600 + 0.1,
                                   conclusion="success")])
        self.assertEqual(at_limit["status"], "ok")
        self.assertEqual(just_past["status"], "fail")

    def test_a_streak_inside_the_deadline_warns_instead_of_failing(self):
        verdict = judge(runs=[run(hours_ago=6, conclusion="failure"),
                              run(hours_ago=18, conclusion="failure"),
                              run(hours_ago=30, conclusion="failure"),
                              run(hours_ago=42, conclusion="success")])
        self.assertEqual((verdict["status"], verdict["kind"]), ("warn", "streak"))
        self.assertEqual(verdict["streak"], 3)
        self.assertIn("lane's own issue should already be open", verdict["reason"])

    def test_running_forever_without_ever_succeeding_is_a_failure(self):
        """This is the YouTube shape: the lane has runs, so nothing looks abandoned —
        but it has never once produced an outcome. "It runs" is not "it works"."""
        verdict = judge(runs=[run(hours_ago=4, conclusion="failure"),
                              run(hours_ago=28, conclusion="failure")])
        self.assertEqual((verdict["status"], verdict["kind"]), ("fail", "never-succeeded"))
        self.assertIn("not one successful", verdict["reason"])
        self.assertIn("README", verdict["reason"])

    def test_the_scheduler_slack_never_buys_more_than_one_cycle(self):
        """12 h of slack is right for a daily lane and absurd for a 30-minute one: it
        would mean the monitor can only notice that a fast lane is *gone*, never that
        it stopped. The cap is what keeps one rule honest across both shapes."""
        fast = judge(one_lane=lane(crons=("*/30 * * * *",)), runs=[run(hours_ago=3)])
        self.assertEqual((fast["status"], fast["kind"]), ("fail", "silent"))
        self.assertEqual(fast["expected_gap"], 1800)
        self.assertEqual(fast["jitter_used"], 3600)
        self.assertEqual(fast["silent_after"], 2 * 1800 + 3600)
        slow = judge(runs=[run(hours_ago=3)])
        self.assertEqual(slow["jitter_used"], 12 * 3600)

    def test_a_dead_schedule_on_an_old_file_is_a_failure(self):
        verdict = judge(runs=[])
        self.assertEqual((verdict["status"], verdict["kind"]), ("fail", "never-run"))

    def test_a_lane_merged_minutes_ago_is_only_warned_about(self):
        """`schedule:` + zero runs is *normal* for a lane that has not reached its
        first fire. Alarm on day 12, not day 1, or the monitor is wrong."""
        verdict = judge(runs=[], since=NOW - timedelta(hours=5))
        self.assertEqual((verdict["status"], verdict["kind"]), ("warn", "too-new"))

    def test_github_disabling_a_workflow_is_the_loudest_kind_of_quiet(self):
        for state in ("disabled_inactivity", "disabled_missing_permissions", "inactive"):
            with self.subTest(state=state):
                verdict = judge(lane(), info(state=state), runs=[run()])
                self.assertEqual((verdict["status"], verdict["kind"]), ("fail", "disabled"))
                self.assertIn("Re-enable", verdict["reason"])

    def test_a_workflow_github_has_never_seen_with_an_old_file_is_a_failure(self):
        verdict = judge(lane(), None, runs=[])
        self.assertEqual((verdict["status"], verdict["kind"]), ("fail", "never-run"))
        self.assertIn("never run", verdict["reason"])

    def test_a_file_without_a_schedule_is_never_an_alarm(self):
        verdict = judge(lane(crons=(), scheduled=False))
        self.assertEqual(verdict["status"], "manual")
        self.assertIn("expected, not a finding", verdict["reason"])

    def test_an_unreadable_workflow_is_unknown_not_ok(self):
        verdict = judge(lane(error="unreadable YAML (ParserError)"))
        self.assertEqual((verdict["status"], verdict["kind"]), ("unknown", "unreadable"))

    def test_an_unmeasurable_cadence_is_unknown_not_ok(self):
        verdict = judge(lane(crons=("every morning",), scheduled=True))
        self.assertEqual(verdict["status"], "unknown")
        self.assertIn("not readable", verdict["reason"])

    def test_the_tunables_move_the_deadline_as_documented(self):
        old = judge(runs=[run(hours_ago=24 * 10)], misses=1, jitter=timedelta(hours=0))
        lenient = judge(runs=[run(hours_ago=24 * 10)], misses=10, jitter=timedelta(hours=0))
        self.assertEqual(old["status"], "fail")
        self.assertEqual(lenient["status"], "ok")


class BuildVerdictsTests(unittest.TestCase):
    LANE = lane()
    PATH = LANE["path"]

    def build(self, index, runs, since, ref="main", branch="main", default_crons=None):
        options = {"grace": hb.DEFAULT_LANE_GRACE, "jitter": hb.SCHEDULE_JITTER,
                   "misses": hb.MISSES_BEFORE_SILENT, "ref": ref, "branch": branch}
        if default_crons is not None:
            options["default_crons"] = default_crons
        return hb.build_verdicts([self.LANE], index, runs, {self.PATH: since}, NOW, options)

    def test_a_schedule_that_only_exists_on_the_branch_cannot_be_called_silent(self):
        """The Facebook shape, exactly: the file is on `main` (so the old downgrade,
        which only fires when the file is missing, let it through) but `main` has no
        `schedule:` in it, so GitHub never had a chance to run it. Silence here is a
        statement about the merge queue. Saying "it has never run" without that suffix
        is how a monitor loses the room."""
        out = self.build({self.PATH: info()},
                         {}, NOW - timedelta(days=30), ref="arena/x",
                         default_crons={self.PATH: []})
        verdict = out[0]
        self.assertEqual(verdict["status"], "warn")
        self.assertTrue(verdict["pending_merge"])
        self.assertIn("no `schedule:` on `main`", verdict["reason"])
        self.assertEqual(hb.signature(out), hb.signature([]))

    def test_the_rule_covers_a_lane_that_ran_and_then_stopped(self):
        """`silent` is excused for the same reason as `never-run`: if the cadence only
        exists on this branch, "it stopped" is not a fact about main."""
        out = self.build({self.PATH: info()}, {777: [run(hours_ago=24 * 12)]},
                         NOW - timedelta(days=30), ref="arena/x",
                         default_crons={self.PATH: []})
        self.assertEqual((out[0]["status"], out[0]["kind"]), ("warn", "silent"))
        self.assertTrue(out[0]["pending_merge"])

    def test_not_being_able_to_read_main_is_never_an_excuse(self):
        """`default_crons` simply lacking the path means *unknown* — and unknown must
        not be quietly promoted to "excused", which is how a rate-limited run turns a
        real failure into a green check."""
        out = self.build({self.PATH: info()}, {}, NOW - timedelta(days=30), ref="arena/x",
                         default_crons={})
        self.assertEqual((out[0]["status"], out[0]["kind"]), ("fail", "never-run"))
        self.assertNotIn("pending_merge", out[0])

    def test_pending_merge_downgrades_a_lane_the_default_branch_does_not_have(self):
        """The one way this monitor could cry wolf: judging a branch's new schedule
        against main's run history. The finding is real ("not live") but it is a
        statement about a merge, so it must not be red and must not enter the
        signature."""
        out = self.build({self.PATH: info()}, {}, None, ref="arena/x", branch="main")
        verdict = out[0]
        self.assertEqual((verdict["status"], verdict["kind"]), ("warn", "never-run"))
        self.assertTrue(verdict["pending_merge"])
        self.assertIn("merge it to make the lane live", verdict["reason"])
        self.assertEqual(hb.signature(out), hb.signature([]))     # noise, not news

    def test_a_lane_that_exists_on_main_and_has_never_succeeded_stays_red(self):
        out = self.build({self.PATH: info()}, {777: [run(hours_ago=4, conclusion="failure"),
                                                      run(hours_ago=30, conclusion="failure")]},
                         NOW - timedelta(days=20), ref="arena/x", branch="main")
        self.assertEqual((out[0]["status"], out[0]["kind"]), ("fail", "never-succeeded"))
        self.assertNotIn("pending_merge", out[0])

    def test_no_downgrade_when_the_heartbeat_runs_where_the_schedule_lives(self):
        out = self.build({self.PATH: info()}, {}, None, ref="main", branch="main")
        self.assertEqual(out[0]["status"], "fail")
        self.assertNotIn("pending_merge", out[0])

    def test_failures_sort_before_health(self):
        lanes = [lane(file="a.yml", name="healthy", crons=("0 8 * * *",)),
                 lane(file="b.yml", name="dead", crons=("0 8 * * *",)),
                 lane(file="c.yml", name="manual", scheduled=False, crons=())]
        index = {l["path"]: info(wf_id=i) for i, l in enumerate(lanes, start=1)}
        out = hb.build_verdicts(lanes, index, {1: [run()], 2: [], 3: []},
                                {l["path"]: NOW - timedelta(days=40) for l in lanes}, NOW,
                                {"grace": hb.DEFAULT_LANE_GRACE, "jitter": hb.SCHEDULE_JITTER,
                                 "misses": hb.MISSES_BEFORE_SILENT, "ref": "main", "branch": "main"})
        self.assertEqual([item["status"] for item in out], ["fail", "ok", "manual"])


class DefaultBranchScheduleTests(unittest.TestCase):
    """`crons_from_text` + the fetch that uses it — three lines of glue, but they are
    the whole difference between an issue and a false alarm."""

    def test_the_schedules_are_read_out_of_another_revision(self):
        self.assertEqual(hb.crons_from_text("on:\n  schedule:\n    - cron: '0 8 * * *'\n"),
                         ["0 8 * * *"])
        self.assertEqual(hb.crons_from_text("on:\n  workflow_dispatch: {}\n"), [])
        self.assertEqual(hb.crons_from_text("'on':\n  schedule:\n    - cron: '5 4 * * 1'\n"),
                         ["5 4 * * 1"], "`on:` parses as boolean True on any spelling")

    def test_unreadable_yaml_is_unknown_not_empty(self):
        """Returning [] for a file this tool could not parse would mark every broken
        lane as excused. None means "I do not know", and the caller treats it so."""
        self.assertIsNone(hb.crons_from_text("on: [unclosed\n"))
        self.assertIsNone(hb.crons_from_text(""))

    def test_the_fetch_asks_only_about_lanes_that_claim_a_schedule(self):
        lanes = [lane(file="a.yml"), lane(file="b.yml", scheduled=False, crons=()),
                 lane(file="c.yml", error="unreadable YAML")]
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "repos/x/y/contents/.github/workflows"))
            for name, body in (("a.yml", "on:\n  schedule:\n    - cron: '0 8 * * *'\n"),
                               ("b.yml", "on:\n  workflow_dispatch: {}\n")):
                payload = base64.b64encode(body.encode()).decode()
                with open(os.path.join(tmp, "repos/x/y/contents/.github/workflows/" + name + ".json"),
                          "w", encoding="utf-8") as handle:
                    json.dump({"content": payload}, handle)
            client = hb.GitHub("x", "y", fixture=tmp)
            found = hb.default_branch_crons(client, lanes, "main")
        self.assertEqual(found, {".github/workflows/a.yml": ["0 8 * * *"]},
                         "b has no schedule to compare, c could not be read — neither belongs in the map")

    def test_a_file_github_returns_without_content_is_a_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "repos/x/y/contents/.github/workflows"))
            with open(os.path.join(tmp, "repos/x/y/contents/.github/workflows/a.yml.json"),
                      "w", encoding="utf-8") as handle:
                json.dump({"message": "Not Found"}, handle)
            client = hb.GitHub("x", "y", fixture=tmp)
            with self.assertRaises(RuntimeError) as caught:
                client.contents(".github/workflows/a.yml", "main")
        self.assertIn("no file content", str(caught.exception))


class PublishEvidenceTests(unittest.TestCase):
    """The second source of truth: what the lane says it published, not what CI remembers.

    On 13 Oct 2026 the Telegram lane had two true and contradictory sentences — "no
    scheduled run has succeeded in 9.4 days" and "the channel carried a post on 7 Oct".
    A monitor that reads only run history prints the first and gets "nothing was
    published", which is a different claim. And its inverse is nastier: a green run that
    published nothing, which nothing else in the system looks at because it is green.
    """

    def ledger(self, age=None, state="ok", url="https://t.me/docogadaily/33", path="logs/telegram_sent.json"):
        item = {"path": path, "state": state, "newest": None if age is None else NOW - age}
        if url and age is not None:
            item["url"] = url
        return item

    def apply(self, verdict, ledgers):
        return hb.apply_publish_evidence(verdict, ledgers, NOW)

    def test_a_green_lane_with_a_stale_ledger_is_a_failure(self):
        verdict = judge(runs=[run(hours_ago=3)])
        self.assertEqual(verdict["status"], "ok")
        self.apply(verdict, [self.ledger(age=timedelta(days=9))])
        self.assertEqual((verdict["status"], verdict["kind"]), ("fail", "green-but-quiet"))
        self.assertIn("runs go green", verdict["reason"])
        self.assertIn("`logs/telegram_sent.json`", verdict["reason"])
        self.assertIn("without recording a publish", verdict["reason"])

    def test_a_fresh_ledger_makes_a_green_lane_boringly_correct(self):
        verdict = judge(runs=[run(hours_ago=3)])
        self.apply(verdict, [self.ledger(age=timedelta(hours=2))])
        self.assertEqual(verdict["status"], "ok")
        self.assertEqual(verdict["kind"], "ok")
        self.assertEqual(verdict["last_publish"], hb.iso(NOW - timedelta(hours=2)))

    def test_a_silent_lane_with_a_fresh_ledger_keeps_the_verdict_and_adds_the_fact(self):
        """Downgrading to "warn" would hide the broken cron; leaving "9 days, nothing
        published" would invent a worse fact than the true one. So: same colour, better
        sentence."""
        verdict = judge(runs=[run(hours_ago=24 * 10)])
        self.assertEqual((verdict["status"], verdict["kind"]), ("fail", "silent"))
        self.apply(verdict, [self.ledger(age=timedelta(hours=6))])
        self.assertEqual(verdict["status"], "fail", "the schedule is still broken")
        self.assertIn("records a publish 6.0h ago", verdict["publish_note"])
        self.assertIn("t.me/docogadaily/33", verdict["publish_note"])
        self.assertIn("fix the cron", verdict["publish_note"],
                      "the note must say what to do, not only that the numbers disagree")

    def test_an_absent_ledger_proves_nothing(self):
        """`absent` is "this lane has never written evidence", not "it never published".
        Reading it as the second would turn a brand-new lane into an accusation."""
        verdict = judge(runs=[run(hours_ago=24 * 10)])
        before = dict(verdict)
        self.apply(verdict, [self.ledger(age=None, state="absent")])
        self.assertEqual(verdict["status"], before["status"])
        self.assertIn("not on the default branch yet", verdict["publish_note"])

    def test_an_unreadable_ledger_is_not_read_as_silence(self):
        verdict = judge(runs=[run(hours_ago=3)])
        self.apply(verdict, [self.ledger(age=None, state="unreadable")])
        self.assertEqual(verdict["status"], "ok", "a corrupt file is the ledger tool's "
                                                "problem to survive, not a lane failure")
        self.assertIn("does not parse", verdict["publish_note"])

    def test_an_empty_ledger_is_evidence_of_nothing_published(self):
        """`empty` is the one state that *does* mean "no publishes" — the file exists
        and is readable and has nothing in it."""
        verdict = judge(runs=[run(hours_ago=3)])
        self.apply(verdict, [self.ledger(age=None, state="empty")])
        self.assertEqual(verdict["status"], "ok",
                         "with no timestamp there is no deadline to miss; say it in the "
                         "row, do not guess a failure")
        self.assertIn("empty", verdict["publish_evidence"])

    def test_the_newest_of_several_ledgers_wins(self):
        verdict = judge(runs=[run(hours_ago=3)])
        self.apply(verdict, [self.ledger(age=timedelta(days=30), path="logs/a.json"),
                             self.ledger(age=timedelta(minutes=5), path="logs/b.json")])
        self.assertEqual(verdict["publish_age"], 300)

    def test_the_table_shows_the_number_that_answers_the_question(self):
        verdict = judge(runs=[run(hours_ago=24 * 10)])
        self.apply(verdict, [self.ledger(age=timedelta(hours=6))])
        text = hb.markdown([verdict], now=NOW, repo="o/r")
        self.assertIn("· ledger", text, "the row must not claim the last run is the last publish")
        self.assertEqual(len([line for line in text.splitlines() if "Telegram" in line][0].split("|")), 6)

    def test_only_a_contradiction_gets_a_blockquote(self):
        """Three lanes each saying "no ledger yet" in near-identical sentences buries the
        one sentence that matters. The quiet case is counted on one line; the
        disagreement is quoted."""
        silent = judge(runs=[run(hours_ago=24 * 10)])
        self.apply(silent, [self.ledger(age=None, state="absent", path="logs/a.json")])
        other = judge(one_lane=lane(file="youtube_queue.yml", name="Other"),
                      runs=[run(hours_ago=24 * 10)], since=NOW - timedelta(days=30))
        self.apply(other, [self.ledger(age=None, state="absent", path="logs/b.json")])
        text = hb.markdown([silent, other], now=NOW, repo="o/r", branch_hint="main")
        self.assertIn("2 lane(s) declare a publish ledger", text)
        self.assertNotIn("> no publish evidence either way", text)
        loud = judge(runs=[run(hours_ago=24 * 10)])
        self.apply(loud, [self.ledger(age=timedelta(hours=6), path="logs/c.json")])
        text = hb.markdown([loud], now=NOW, repo="o/r", branch_hint="main")
        self.assertIn("> `logs/c.json` records a publish", text)

    def test_the_notes_survive_as_one_blockquote(self):
        verdict = judge(runs=[run(hours_ago=24 * 10)])
        other = judge(one_lane=lane(file="youtube_queue.yml", name="Other"),
                      runs=[run(hours_ago=24 * 10)], since=NOW - timedelta(days=30))
        self.apply(verdict, [self.ledger(age=timedelta(hours=6))])
        text = hb.markdown([verdict, other], now=NOW, repo="o/r")
        self.assertEqual(text.count("records a publish 6.0h ago"), 1,
                         "two lanes saying it is two notes; the same note twice is noise")

    def test_triage_reads_the_ledger_step_first(self):
        verdict = judge(runs=[run(hours_ago=3)])
        self.apply(verdict, [self.ledger(age=timedelta(days=9))])
        text = hb.triage([verdict], ref="main")
        self.assertIn("ledger step", text)
        self.assertIn("git push", text, "a swallowed warning there is the usual cause")

    def test_triage_carries_the_contradiction_into_the_issue(self):
        verdict = judge(runs=[run(hours_ago=24 * 10)])
        self.apply(verdict, [self.ledger(age=timedelta(hours=6))])
        self.assertIn("records a publish", hb.triage([verdict], ref="main"))

    def test_the_signature_moves_when_a_lane_goes_green_but_quiet(self):
        healthy = judge(runs=[run(hours_ago=3)])
        quiet = judge(runs=[run(hours_ago=3)])
        self.apply(quiet, [self.ledger(age=timedelta(days=9))])
        self.assertNotEqual(hb.signature([healthy]), hb.signature([quiet]))


class LedgerDiscoveryTests(unittest.TestCase):
    """`logs/x.json` references are read out of the workflows, like everything else."""

    def test_a_lane_that_writes_a_ledger_is_found(self):
        lanes = {lane["file"]: lane
                 for lane in hb.discover_lanes(str(ROOT / ".github" / "workflows"))}
        self.assertIn("telegram_sent.json", lanes["telegram_autopost.yml"]["ledgers"])
        self.assertIn("facebook_reels.json", lanes["facebook_autopost.yml"]["ledgers"])
        self.assertEqual(lanes["verify.yml"]["ledgers"], [],
                         "a workflow with no ledger must not be judged for lacking one")

    def test_the_states_come_back_from_the_contents_api(self):
        import base64 as _b64

        def fixture(entries):
            tmp = tempfile.mkdtemp()
            where = os.path.join(tmp, "repos/x/y/contents/logs")
            os.makedirs(where)
            body = _b64.b64encode(json.dumps(entries).encode("utf-8")).decode()
            with open(os.path.join(where, "telegram_sent.json.json"), "w", encoding="utf-8") as handle:
                json.dump({"content": body}, handle)
            return hb.GitHub("x", "y", fixture=tmp)

        client = fixture([{"title": "telegram tip abc", "date": "2026-10-07",
                           "recorded_at": "2026-10-07T11:18:00+01:00",
                           "url": "https://t.me/docogadaily/32"}])
        found = hb.ledger_freshness(client, "logs/telegram_sent.json", "main", NOW)
        self.assertEqual(found["state"], "ok")
        self.assertEqual(found["url"], "https://t.me/docogadaily/32")
        self.assertEqual(found["newest"].utcoffset(), timedelta(hours=1))
        self.assertEqual(found["entries"], 1)

        client = fixture([])
        self.assertEqual(hb.ledger_freshness(client, "logs/telegram_sent.json", "main", NOW)["state"],
                         "empty")
        client = fixture({"entries": [{"date": "not a date"}]})
        self.assertEqual(hb.ledger_freshness(client, "logs/telegram_sent.json", "main", NOW)["state"],
                         "empty", "an entry nobody can place in time is not a publish")
        missing = hb.GitHub("x", "y", fixture=tempfile.mkdtemp())
        self.assertEqual(hb.ledger_freshness(missing, "logs/telegram_sent.json", "main", NOW)["state"],
                         "absent")

    def test_a_ledger_entry_without_a_timestamp_is_ignored_not_invented(self):
        import base64 as _b64
        tmp = tempfile.mkdtemp()
        where = os.path.join(tmp, "repos/x/y/contents/logs")
        os.makedirs(where)
        body = _b64.b64encode(json.dumps([{"title": "x"}]).encode()).decode()
        with open(os.path.join(where, "l.json.json"), "w", encoding="utf-8") as handle:
            json.dump({"content": body}, handle)
        found = hb.ledger_freshness(hb.GitHub("x", "y", fixture=tmp), "logs/l.json", "main", NOW)
        self.assertEqual(found["state"], "empty")


class SignatureTests(unittest.TestCase):
    def verdict(self, file, status, reason="x", **extra):
        out = {"file": file, "status": status, "reason": reason, "lane": file}
        out.update(extra)
        return out

    def test_the_signature_ignores_prose_and_timestamps(self):
        a = [self.verdict("t.yml", "fail", "dead for 9.4 days", last_run="2026-10-01"),
             self.verdict("y.yml", "ok", "fine")]
        b = [self.verdict("t.yml", "fail", "dead for 10.1 days", last_run="2026-10-02"),
             self.verdict("y.yml", "ok", "still fine")]
        self.assertEqual(hb.signature(a), hb.signature(b))

    def test_a_second_broken_lane_is_new_news(self):
        a = [self.verdict("t.yml", "fail")]
        b = [self.verdict("t.yml", "fail"), self.verdict("f.yml", "fail")]
        self.assertNotEqual(hb.signature(a), hb.signature(b))

    def test_a_lane_healing_is_new_news(self):
        self.assertNotEqual(hb.signature([self.verdict("t.yml", "fail")]),
                            hb.signature([self.verdict("t.yml", "ok")]))

    def test_all_healthy_is_one_stable_value(self):
        self.assertEqual(hb.signature([self.verdict("t.yml", "ok"), self.verdict("y.yml", "manual")]),
                         hb.signature([self.verdict("z.yml", "ok")]))

    def test_a_warning_is_news_once_and_then_quiet(self):
        first = [self.verdict("t.yml", "warn", "2 failures")]
        self.assertEqual(hb.signature(first), hb.signature(first))


class RenderTests(unittest.TestCase):
    def markdown(self, *verdicts):
        return hb.markdown(list(verdicts), now=NOW, repo="o/r")

    def test_the_table_shows_the_cadence_and_the_verdict(self):
        text = self.text_of_a_silent_lane()
        self.assertIn("| ❌ DocOga Telegram Auto-Post |", text)
        self.assertIn("`0 8 * * *`", text)
        self.assertIn("24.0h", text)
        self.assertIn("nothing has succeeded", text)

    def text_of_a_silent_lane(self):
        verdict = judge(runs=[run(hours_ago=24 * 10)])
        return self.markdown(verdict)

    def test_manual_workflows_are_collapsed_into_one_line(self):
        """Ten rows of "🔧 nothing wrong" bury the one row that is wrong. The count is
        the useful part; the names belong in a footnote."""
        manual = [judge(lane(file="v%d.yml" % i, name="Manual %d" % i, scheduled=False, crons=()))
                  for i in range(4)]
        text = self.markdown(judge(runs=[run()]), *manual)
        self.assertIn("4 more workflow(s) have no `schedule:`", text)
        self.assertIn("are not judged", text)
        self.assertEqual(text.count("| 🔧"), 0, "manual lanes must not occupy table rows")
        for i in range(4):
            self.assertIn("`v%d.yml`" % i, text)      # named once each, in the footnote

    def test_the_manual_count_survives_a_repo_with_no_manual_workflows(self):
        text = self.markdown(judge(runs=[run()]))
        self.assertNotIn("more workflow(s)", text)

    def test_pipe_characters_cannot_break_the_table(self):
        verdict = judge(runs=[run()])
        verdict["reason"] = "a | b | c from the API"
        row = [line for line in self.markdown(verdict).splitlines() if "DocOga" in line][0]
        self.assertEqual(row.count("|"), 5, row)   # four cells, always

    def test_triage_names_the_fix_for_each_kind(self):
        """A reader must be able to act from the issue body alone — and each verdict
        kind needs a *different* action, which is why this asserts the kind as well as
        the sentence (a mis-set kind silently ships the wrong advice)."""
        silent = judge(runs=[run(hours_ago=24 * 12)])
        self.assertEqual(silent["kind"], "silent")
        text = hb.triage([silent], ref="main")
        self.assertIn("cron changed", text)
        self.assertIn("gh workflow run telegram_autopost.yml --ref main", text)
        self.assertIn("gh run list --workflow 'DocOga Telegram Auto-Post'", text)

        never = judge(runs=[], since=NOW - timedelta(days=30))
        self.assertEqual(never["kind"], "never-run")
        self.assertIn("default branch", hb.triage([never], ref="main"))

        disabled = judge(one_info=info("disabled_inactivity"))
        self.assertEqual(disabled["kind"], "disabled")
        self.assertIn("Enable workflow", hb.triage([disabled]))

        never_worked = judge(runs=[run(hours_ago=4, conclusion="failure"),
                                   run(hours_ago=28, conclusion="failure")])
        self.assertEqual(never_worked["kind"], "never-succeeded")
        advice = hb.triage([never_worked], ref="main")
        never_worked["labels"] = ["telegram-automation"]
        advice = hb.triage([never_worked], ref="main")
        self.assertIn("gh issue list --label telegram-automation --state open", advice,
                      "the lane's own issue label is where the preflight's words live")
        no_label = judge(runs=[run(hours_ago=4, conclusion="failure")])
        no_label["labels"] = []
        text_unlabelled = hb.triage([no_label], ref="main")
        self.assertIn("gh run view --log", text_unlabelled,
                      "a workflow that files no issue must be told where to look instead")
        self.assertNotIn("telegram-automation", text_unlabelled,
                         "another lane's label in this lane's advice is a wrong pointer")

        self.assertEqual(hb.triage([judge()], ref="main"), "",
                         "a healthy lane gets no section — an empty body is the signal")

    def test_the_issue_body_points_at_the_keys_to_check(self):
        verdict = judge(runs=[run(hours_ago=24 * 12)])
        verdict["secrets"] = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
        text = hb.triage([verdict], ref="main")
        self.assertIn("`TELEGRAM_CHAT_ID`", text)
        self.assertIn("gh secret list", text)
        self.assertIn("names only", text, "the body must not promise to show values")

    def test_a_lane_with_no_secrets_says_nothing_about_secrets(self):
        verdict = judge(runs=[run(hours_ago=24 * 12)])
        verdict["secrets"] = []
        self.assertNotIn("gh secret list", hb.triage([verdict], ref="main"))

    def test_human_duration_reads_as_a_deadline_not_a_number(self):
        self.assertEqual(hb.human_duration(45), "45s")
        self.assertEqual(hb.human_duration(900), "15m")
        self.assertEqual(hb.human_duration(3 * 3600), "3.0h")
        self.assertEqual(hb.human_duration(4 * 86400), "4.0 days")


class DiscoveryTests(unittest.TestCase):
    def write(self, directory, name, body):
        with open(os.path.join(directory, name), "w", encoding="utf-8") as handle:
            handle.write(body)

    def test_it_reads_the_real_workflows_and_finds_the_real_lanes(self):
        """No fixture: this reads this checkout. If a schedule is renamed or removed,
        the monitor notices, and so does this test."""
        lanes = hb.discover_lanes(str(ROOT / ".github" / "workflows"))
        by_file = {lane["file"]: lane for lane in lanes}
        self.assertIn("telegram_autopost.yml", by_file)
        self.assertEqual(by_file["telegram_autopost.yml"]["crons"], ["0 8 * * *"])
        self.assertTrue(by_file["facebook_autopost.yml"]["scheduled"])
        self.assertFalse(by_file["instagram_autopost.yml"]["scheduled"],
                         "Instagram is dispatch-only on purpose; the heartbeat must say so, not alarm")
        self.assertIn("automation-heartbeat.yml", by_file,
                      "the monitor must judge itself — a silent monitor is the failure it exists for")
        for lane_entry in lanes:
            if lane_entry["scheduled"]:
                gap, detail = hb.expected_gap(lane_entry["crons"], start=NOW - timedelta(days=60))
                with self.subTest(lane=lane_entry["file"]):
                    self.assertIsNotNone(gap, detail)

    def test_a_lane_names_the_keys_it_reads(self):
        """The brief is "name the secret to check", so the names come out of the
        workflow file itself — a hardcoded list would be stale the day someone adds a
        key, and stale advice in an issue is worse than no advice."""
        lanes = {lane["file"]: lane
                 for lane in hb.discover_lanes(str(ROOT / ".github" / "workflows"))}
        telegram = lanes["telegram_autopost.yml"]
        self.assertIn("TELEGRAM_BOT_TOKEN", telegram["secrets"])
        self.assertIn("TELEGRAM_CHAT_ID", telegram["secrets"])
        self.assertNotIn("GITHUB_TOKEN", telegram["secrets"],
                         "Actions' own token is always present; naming it trains the reader to skip")
        self.assertIn("HEARTBEAT_JITTER_HOURS",
                      lanes["automation-heartbeat.yml"]["vars"])
        for file_name, entry in lanes.items():
            for key in ("secrets", "vars"):
                with self.subTest(lane=file_name, key=key):
                    self.assertEqual(len(entry[key]), len(set(entry[key])),
                                     "%s repeats a name in %s — the same secret referenced "
                                     "by three steps must appear once" % (file_name, key))

    def test_a_lane_carries_the_label_it_files_issues_under(self):
        """Read from the workflow's own `gh issue create --label …`, not a table: the
        advice has to stay true when a lane's label changes."""
        lanes = {lane["file"]: lane
                 for lane in hb.discover_lanes(str(ROOT / ".github" / "workflows"))}
        self.assertEqual(lanes["telegram_autopost.yml"]["labels"], ["telegram-automation"])
        self.assertEqual(lanes["facebook_autopost.yml"]["labels"], ["facebook-automation"])
        self.assertEqual(lanes["build-check.yml"]["labels"], [],
                         "a workflow with no issue step must not be sent looking for one")

    def test_a_broken_yaml_file_is_reported_as_unknown_not_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "broken.yml", "name: [unclosed\n")
            lanes = hb.discover_lanes(tmp)
        self.assertEqual(len(lanes), 1, "an unreadable file must still be a finding")
        self.assertIn("unreadable YAML", lanes[0]["error"])
        self.assertFalse(lanes[0]["scheduled"])
        self.assertEqual(judge(lanes[0])["status"], "unknown")

    def test_on_is_read_both_ways(self):
        """`on:` parses as the boolean True in YAML 1.1 — a discovery routine that
        only looks for the string "on" silently finds no lanes and reports a healthy
        repo, which is the worst possible outcome for a monitor."""
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "a.yml", "on:\n  schedule:\n    - cron: '0 8 * * *'\njobs:\n  j:\n    steps: []\n")
            self.write(tmp, "b.yml", "'on':\n  schedule:\n    - cron: '30 8 * * *'\njobs:\n  j:\n    steps: []\n")
            lanes = {lane["file"]: lane for lane in hb.discover_lanes(tmp)}
        self.assertEqual(lanes["a.yml"]["crons"], ["0 8 * * *"])
        self.assertEqual(lanes["b.yml"]["crons"], ["30 8 * * *"])


class GithubApiTests(unittest.TestCase):
    def test_the_run_list_is_newest_first_and_carries_the_fields_the_verdict_needs(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "repos/x/y/actions/workflows/777"))
            with open(os.path.join(tmp, "repos/x/y/actions/workflows/777/runs.json"), "w",
                      encoding="utf-8") as handle:
                json.dump({"workflow_runs": [
                    {"created_at": "2026-10-11T08:30:00Z", "status": "completed",
                     "conclusion": "success", "html_url": "u1", "head_branch": "main",
                     "event": "schedule", "display_title": "newer"},
                    {"created_at": "2026-10-10T08:30:00Z", "status": "completed",
                     "conclusion": "failure", "html_url": "u0", "head_branch": "main",
                     "event": "schedule", "display_title": "older"},
                ]}, handle)
            client = hb.GitHub("x", "y", fixture=tmp)
            runs = hb.recent_runs(client, 777, "main")
        self.assertEqual([run_["url"] for run_ in runs], ["u1", "u0"])
        self.assertEqual(runs[0]["created_at"].year, 2026)
        self.assertEqual(runs[1]["conclusion"], "failure")

    def test_an_http_refusal_keeps_the_status_code(self):
        """403 (the token cannot see this), 404 (wrong owner/name) and 422 (a bad
        parameter) need three different fixes; flattening them into "could not reach
        GitHub" sends the reader to the network instead of the config."""
        import urllib.error

        def explode(*args, **kwargs):
            raise urllib.error.HTTPError(
                "https://api.github.com/x", 403, "Forbidden", {},
                io.BytesIO(b'{"message":"Resource not accessible by integration"}'))

        client = hb.GitHub("x", "y", token="t")
        with patch("urllib.request.urlopen", explode), self.assertRaises(RuntimeError) as caught:
            client.get("/repos/x/y/actions/workflows")
        message = str(caught.exception)
        self.assertIn("HTTP 403", message)
        self.assertIn("not accessible", message)

    def test_a_missing_fixture_is_an_error_message_not_a_crash(self):
        """`path` vs `rel` was a NameError here, which the CLI only reports as exit 3
        if something else catches it — the message must name the file you forgot."""
        with tempfile.TemporaryDirectory() as tmp:
            client = hb.GitHub("x", "y", fixture=tmp)
            with self.assertRaises(RuntimeError) as caught:
                client.get("/repos/x/y/actions/workflows")
        self.assertIn("repos/x/y/actions/workflows", str(caught.exception))
        self.assertNotIn("name 'path' is not defined", str(caught.exception))

    def test_a_missing_token_is_a_refusal_not_an_empty_answer(self):
        client = hb.GitHub("x", "y", token=None)
        with self.assertRaises(RuntimeError) as caught:
            client.get("/repos/x/y/actions/workflows")
        self.assertIn("no token", str(caught.exception))

    def test_timestamps_that_do_not_parse_never_become_a_verdict(self):
        self.assertIsNone(hb.parse_stamp(""))
        self.assertIsNone(hb.parse_stamp("tom morning"))
        self.assertEqual(hb.parse_stamp("2026-10-12T17:31:57Z").hour, 17)
        self.assertEqual(hb.parse_stamp("2026-10-12T17:31:57+01:00").utcoffset(),
                         timedelta(hours=1))


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.workflow_dir = os.path.join(self.tmp, "workflows")
        os.makedirs(self.workflow_dir)
        for name, body in (("telegram_autopost.yml",
                            "name: DocOga Telegram Auto-Post\non:\n  schedule:\n"
                            "    - cron: '0 8 * * *'\njobs:\n  j:\n    steps: []\n"),
                           ("instagram_autopost.yml",
                            "name: Instagram Autopost\non:\n  workflow_dispatch: {}\n"
                            "jobs:\n  j:\n    steps: []\n")):
            with open(os.path.join(self.workflow_dir, name), "w", encoding="utf-8") as handle:
                handle.write(body)
        self.fixture = os.path.join(self.tmp, "fixture")
        os.makedirs(os.path.join(self.fixture, "repos/x/y/actions"))
        os.makedirs(os.path.join(self.fixture, "repos/x/y/actions/workflows/777"))
        os.makedirs(os.path.join(self.fixture, "repos/x/y/actions/workflows/888"))
        with open(os.path.join(self.fixture, "repos/x/y/actions/workflows.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"workflows": [
                {"id": 777, "state": "active", "name": "DocOga Telegram Auto-Post",
                 "path": ".github/workflows/telegram_autopost.yml"},
                {"id": 888, "state": "active", "name": "Instagram Autopost",
                 "path": ".github/workflows/instagram_autopost.yml"},
            ]}, handle)
        with open(os.path.join(self.fixture, "repos/x/y/actions/workflows/777/runs.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"workflow_runs": [{"created_at": "2026-09-20T08:30:00Z",
                                          "status": "completed", "conclusion": "success",
                                          "html_url": "https://github.com/x/y/actions/runs/9",
                                          "head_branch": "main", "event": "schedule"}]}, handle)
        with open(os.path.join(self.fixture, "repos/x/y/actions/workflows/888/runs.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"workflow_runs": []}, handle)
        with open(os.path.join(self.fixture, "repos/x/y/commits.json"), "w",
                  encoding="utf-8") as handle:
            json.dump([{"commit": {"committer": {"date": "2026-09-01T00:00:00Z"}}}], handle)

    def drive(self, *extra):
        """`--ref` and `--branch` are pinned, not inherited: main() reads them from
        $GITHUB_REF_NAME / $HEARTBEAT_BRANCH, and this whole class runs on `main`'s
        fixtures. A CI job on a pull request has GITHUB_REF_NAME=`19/merge`, which
        turns on the branch-only-schedule downgrade and quietly flips the expected
        exit code — a test whose answer depends on which ref happened to trigger the
        job is not a test, and that is exactly how this one failed in Actions while
        passing on every laptop."""
        out = io.StringIO()
        argv = ["--repo", "x/y", "--fixture", self.fixture, "--workflows", self.workflow_dir,
                "--now", "2026-10-13T18:00:00Z", "--branch", "main", "--ref", "main"]
        argv += list(extra)
        with redirect_stdout(out):
            code = hb.main(argv)
        return code, out.getvalue()

    def test_a_silent_lane_exits_one_and_names_the_file(self):
        code, text = self.drive("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("HEARTBEAT_STATE=degraded", text)
        self.assertIn("HEARTBEAT_SILENT=telegram_autopost.yml", text)
        self.assertRegex(text, r"HEARTBEAT_SIGNATURE=[0-9a-f]{12}")
        self.assertIn("`instagram_autopost.yml`", text)   # footnoted, not failed

    def test_dry_run_writes_no_files(self):
        self.drive("--dry-run", "--out", os.path.join(self.tmp, "hb.json"),
                   "--markdown", os.path.join(self.tmp, "hb.md"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "hb.json")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "hb.md")))

    def test_the_written_files_are_the_contracts_the_workflow_reads(self):
        json_path = os.path.join(self.tmp, "hb.json")
        md_path = os.path.join(self.tmp, "hb.md")
        triage_path = os.path.join(self.tmp, "triage.md")
        self.drive("--out", json_path, "--markdown", md_path, "--triage", triage_path)
        data = json.load(open(json_path, encoding="utf-8"))
        self.assertEqual(data["repo"], "x/y")
        self.assertEqual(len(data["verdicts"]), 2)
        self.assertEqual(data["verdicts"][0]["kind"], "silent")
        self.assertIn("Automation heartbeat", open(md_path, encoding="utf-8").read())
        self.assertIn("cron changed", open(triage_path, encoding="utf-8").read())   # silent kind

    def test_the_ref_downgrade_is_wired_end_to_end(self):
        """The unit tests can pass while main() forgets to hand `default_crons` to
        build_verdicts — rebinding a local name instead of mutating the options dict
        did exactly that, and every branch-only schedule still read as a failure. Only
        a run through the CLI catches the wiring, so this is that run.

        The fixture says: main's copy of telegram_autopost.yml has no `schedule:`, so
        the silence this branch reports is a merge, not a dead lane.
        """
        contents = os.path.join(self.fixture, "repos/x/y/contents/.github/workflows")
        os.makedirs(contents, exist_ok=True)
        main_copy = "name: DocOga Telegram Auto-Post\non:\n  workflow_dispatch: {}\n" \
                    "jobs:\n  j:\n    steps: []\n"
        with open(os.path.join(contents, "telegram_autopost.yml.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"content": base64.b64encode(main_copy.encode()).decode()}, handle)

        code, text = self.drive("--ref", "feature/x")
        self.assertEqual(code, 0, "an unmerged schedule is not a dead lane")
        self.assertIn("HEARTBEAT_STATE=healthy", text)
        self.assertIn("HEARTBEAT_SILENT=-", text)
        self.assertIn("no `schedule:` on `main`", text)
        self.assertNotIn("HEARTBEAT_SIGNATURE=-\n", text,
                         "the signature must still be a hash, or the workflow's grep is comparing noise")

        code, text = self.drive()
        self.assertEqual(code, 1, "the same numbers read on main are a real failure")
        self.assertIn("HEARTBEAT_STATE=degraded", text)

    def test_every_cli_call_pins_the_ref(self):
        """Ambient `$GITHUB_REF_NAME` is `19/merge` in a pull-request check and `main`
        on the schedule — and one test in this file changed its expected exit code
        between the two (it passed on every laptop and failed in Actions). main()
        reads the ref from the environment on purpose; the tests must not.

        The rule has no exceptions because the one call that does not need a ref does
        not need a fixture either: `test_no_repo_is_a_refusal_to_guess` proves the
        refusal happens before any I/O, so it passes neither."""
        src = Path(__file__).read_text(encoding="utf-8")
        offenders = [block for block in re.findall(r"hb\.main\(\[.*?\]\)", src, re.S)
                     if "--ref" not in block and "--fixture" in block]
        self.assertEqual([], offenders, "route new CLI tests through self.drive() — it pins --ref/--branch")

    def test_no_repo_is_a_refusal_to_guess(self):
        """No `--fixture`, no `--ref`, nothing else: the point is that this refusal
        needs no data at all, which is also why it is the one main() call in this file
        that does not care which ref the runner thinks it is on."""
        out = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(out):
            code = hb.main(["--workflows", self.workflow_dir])
        self.assertEqual(code, 3)
        self.assertIn("--repo owner/name is required", out.getvalue())

    def test_an_empty_workflows_directory_is_exit_three_not_all_clear(self):
        """The single most important property: 'I could not look' must never be
        printable as 'everything is fine'."""
        empty = os.path.join(self.tmp, "nothing")
        os.makedirs(empty, exist_ok=True)
        code, text = self.drive("--workflows", empty)
        self.assertEqual(code, 3)
        self.assertIn("refusing to report a healthy repo", text)

    def test_a_broken_api_call_is_exit_three(self):
        with open(os.path.join(self.fixture, "repos/x/y/actions/workflows.json"), "w",
                  encoding="utf-8") as handle:
            handle.write("{ this is not json")
        code, text = self.drive()
        self.assertEqual(code, 3)
        self.assertIn("could not look", text)


class IssueFlowTests(unittest.TestCase):
    """The workflow's filing step, actually executed — against a `gh` that only logs.

    This bash is the half that touches the owner's issue tracker, and nothing else in
    the repo runs it: the tool decides a verdict, the *colour* and the *issue* are
    decided here. Reasoning about which branch a shell script takes is how a monitor
    ends up filing a fresh issue every morning, which is the thing that makes people
    mute it. So each branch below is executed and the recorded `gh` calls are asserted.

    `/tmp/` in the step is rewritten into a temp directory, which keeps the tests
    parallel-safe and lets the issue body be read back.
    """

    @classmethod
    def setUpClass(cls):
        import yaml as _yaml
        doc = _yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
        steps = doc["jobs"]["heartbeat"]["steps"]
        cls.step = [entry for entry in steps
                    if "File, update or close" in str(entry.get("name"))]
        assert cls.step, "the filing step was renamed; the tests must follow it or say so"
        cls.script = cls.step[0]["run"]

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        self.log = os.path.join(self.tmp, "gh.log")
        for name in ("heartbeat.md", "heartbeat-triage.md", "heartbeat.log"):
            with open(os.path.join(self.tmp, name), "w", encoding="utf-8") as handle:
                handle.write("| lane | table |\n\n- Reads `TELEGRAM_BOT_TOKEN`.\n" if name.endswith(".md")
                             else "HEARTBEAT_SIGNATURE=abc123abc123\n")

    def gh_shim(self):
        shim = os.path.join(self.bin, "gh")
        with open(shim, "w", encoding="utf-8") as handle:
            # Plain shell text, no %-formatting on this string: a doubled %% here would
            # print a literal "%s" into the log and every assertion about the recorded
            # calls would fail while the shim itself looks like it works.
            handle.write('#!/bin/sh\n'
                         'printf \'%s\\n\' "$*" >> "$GH_LOG"\n'
                         'case "$1 $2" in\n'
                         '  "issue list")  printf \'%s\\n\' "${FAKE_NUMBER:-}" ;;\n'
                         '  "issue view")  printf \'%s\\n\' "${FAKE_BODY:-}" ;;\n'
                         '  *) exit 0 ;;\n'
                         'esac\n')
        os.chmod(shim, 0o755)

    @staticmethod
    def mutations(calls):
        """The `gh` calls that change the repo's state. Reads (`issue list`,
        `issue view`) are how the step decides, so they belong in every branch and
        must not be counted as side effects."""
        return [line for line in calls if line.split()[:2] in
                (["issue", "close"], ["issue", "comment"], ["issue", "create"],
                 ["label", "create"])]

    def run_step(self, signature="abc123abc123", state="degraded", silent="telegram_autopost.yml",
                 code="1", dry_run="false", number="", body=""):
        self.gh_shim()
        env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ["PATH"],
                   GH_LOG=self.log, SIGNATURE=signature, STATE=state, SILENT=silent,
                   CODE=code, DRY_RUN=dry_run, RUN_URL="https://example.invalid/run/1",
                   FAKE_NUMBER=number, FAKE_BODY=body, TMPDIR=self.tmp)
        result = subprocess.run(["bash", "-c", self.script.replace("/tmp/", self.tmp + "/")],
                                capture_output=True, text=True, env=env, cwd=self.tmp,
                                timeout=60)
        calls = []
        if os.path.exists(self.log):
            with open(self.log, encoding="utf-8") as handle:
                calls = [line.rstrip("\n") for line in handle]
        return result, calls

    def test_a_healthy_repo_closes_the_tracked_issue(self):
        result, calls = self.run_step(state="healthy", number="16")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(any(c.startswith("issue close 16") for c in calls), calls)
        self.assertFalse(any("issue create" in c for c in calls))
        self.assertFalse(any("issue comment" in c for c in calls),
                         "closing with a comment is enough; a comment too is noise")

    def test_healthy_with_nothing_open_is_silent_and_green(self):
        result, calls = self.run_step(state="healthy", number="")
        self.assertEqual(result.returncode, 0)
        # A healthy non-dry run still makes sure the label exists — that is a
        # preparation, not a finding. What must not happen is touching an issue.
        self.assertEqual([c for c in self.mutations(calls) if c.startswith("issue ")], [])
        self.assertIn("Nothing to close", result.stdout)

    def test_the_same_verdict_set_comments_and_stays_green(self):
        """The whole livability rule, in bash: same signature ⇒ comment, exit 0. If
        this ever returns 1, every morning is a red run and an email."""
        result, calls = self.run_step(number="16", body="verdict signature `abc123abc123`\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(any(c.startswith("issue comment 16") for c in calls), calls)
        self.assertFalse(any("issue create" in c for c in calls))
        self.assertIn("staying green", result.stdout)

    def test_a_changed_verdict_set_updates_the_issue_and_goes_red(self):
        result, calls = self.run_step(number="16", body="old signature xyz\n")
        self.assertEqual(result.returncode, 1, "red is the email, on purpose")
        self.assertTrue(any("--body-file" in c and c.startswith("issue comment 16") for c in calls), calls)
        self.assertFalse(any("issue create" in c for c in calls),
                         "one tracked issue, updated — not one per day")

    def test_the_first_failure_files_one_labelled_issue(self):
        result, calls = self.run_step(number="")
        self.assertEqual(result.returncode, 1)
        created = [c for c in calls if c.startswith("issue create")]
        self.assertEqual(len(created), 1, calls)
        self.assertIn("--label automation-heartbeat", created[0])
        self.assertIn("--body-file", created[0])
        self.assertTrue(any(c.startswith("label create automation-heartbeat") for c in calls),
                        "the label must be created before it is used, or the issue fails")
        self.assertEqual(calls[0].split()[:2], ["label", "create"],
                         "the label is the only thing allowed before the issue")

    def test_a_dry_run_prints_the_body_and_touches_nothing(self):
        result, calls = self.run_step(dry_run="true", number="")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.mutations(calls), [],
                         "the dispatch button is how the owner looks without side effects — "
                         "not even a label")
        self.assertIn("Dry run", result.stdout)

    def test_no_signature_is_reported_as_a_failure_to_judge(self):
        """Empty signature means the tool never reached a verdict. Filing "0 lanes are
        silent" in that case would be the monitor lying about its own outage."""
        result, calls = self.run_step(signature="", number="")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no signature was printed", result.stdout)
        self.assertEqual([c for c in calls if c.split()[:2] in (["issue", "comment"],
                                                                ["issue", "create"])], [])

    def test_the_dry_run_still_reports_a_missing_signature(self):
        result, _ = self.run_step(signature="", dry_run="true")
        self.assertEqual(result.returncode, 0, "dry run must not turn a report into a failure")

    def test_the_body_carries_the_table_the_triage_and_the_signature(self):
        self.run_step(number="")
        path = os.path.join(self.tmp, "issue_body.md")
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
        self.assertIn("| lane | table |", body)
        self.assertIn("Reads `TELEGRAM_BOT_TOKEN`", body)
        self.assertIn("abc123abc123", body)
        self.assertIn("telegram_autopost.yml", body)

    def test_no_command_injection_from_the_tool_log(self):
        """The log tail is pasted into the issue body, and it is GitHub's API output —
        text that arrived over a network. Backticks are stripped for a reason."""
        with open(os.path.join(self.tmp, "heartbeat.log"), "w", encoding="utf-8") as handle:
            handle.write("saw `id $(touch /tmp/pwned)` from the API\n")
        self.run_step(number="")
        with open(os.path.join(self.tmp, "issue_body.md"), encoding="utf-8") as handle:
            body = handle.read()
        pasted = body.split("```")[1]      # the fenced tool output, nothing else
        self.assertNotIn("`", pasted, "the fences stay; the payload's backticks must not")
        self.assertIn("saw id $(touch /tmp/pwned) from the API", pasted,
                      "the text is still shown — stripping is not censoring")
        self.assertFalse(os.path.exists("/tmp/pwned"), "the backticks must never reach a shell")


class HeartbeatWorkflowTests(unittest.TestCase):
    """The job file, checked as a contract rather than as YAML that happens to parse."""

    @classmethod
    def setUpClass(cls):
        import yaml as _yaml
        cls.path = WORKFLOW_PATH
        cls.text = cls.path.read_text(encoding="utf-8")
        cls.doc = _yaml.safe_load(cls.text)
        cls.job = cls.doc["jobs"]["heartbeat"]
        cls.names = [step.get("name") for step in cls.job["steps"]]

    def test_it_asks_for_exactly_the_permissions_it_uses(self):
        perms = self.doc.get("permissions") or {}
        self.assertEqual(perms.get("actions"), "read",
                         "without it there is no run history, and the tool must then exit 3")
        self.assertEqual(perms.get("issues"), "write")
        self.assertEqual(perms.get("contents"), "read",
                         "a monitor has no business pushing; it commits nothing")

    def test_it_can_be_run_without_filing_anything(self):
        on = self.doc[True] if True in self.doc else self.doc["on"]
        self.assertIn("dry_run", (on.get("workflow_dispatch") or {}).get("inputs") or {})
        self.assertIn('DRY_RUN: ${{ inputs.dry_run }}', self.text,
                      "the flag reaches the shell through env:, never interpolated")

    def test_a_monitor_may_be_cancelled_but_a_publisher_may_not(self):
        self.assertIs(self.doc["concurrency"]["cancel-in-progress"], True,
                      "two overlapping judgements produce the same numbers; the rule is "
                      "the opposite of the publishers' on purpose")

    def test_the_tools_exit_code_is_read_before_anything_else_overwrites_it(self):
        """`$(…)` resets PIPESTATUS. Capturing the exit code after the first
        `echo "x=$(sed …)"` line records a true number about the wrong command —
        which is worse than not recording it, because it reads like evidence."""
        block = self.text.split("tee /tmp/heartbeat.log")[1]
        code_at = block.index("CODE=${PIPESTATUS[0]}")
        first_subshell_use = block.index('echo "signature=')
        self.assertLess(code_at, first_subshell_use,
                        "the capture must precede the first command substitution")
        self.assertIn('echo "code=$CODE"', block)
        self.assertNotIn('echo "code=${PIPESTATUS[0]}"', block)

    def test_every_gh_call_has_a_token(self):
        for step in self.job["steps"]:
            if "gh " in str(step.get("run", "")):
                with self.subTest(step=step.get("name")):
                    self.assertIn("GH_TOKEN", str(step.get("env", "")))

    def test_the_red_only_when_new_rule_is_visible_in_the_file(self):
        self.assertIn("grep -q \"$SIGNATURE\"", self.text)
        self.assertIn("commenting, staying green", self.text)
        self.assertIn("gh issue close", self.text, "healthy must clear the issue, or the "
                                                   "label becomes a graveyard")

    def test_it_schedules_itself_after_the_lanes_it_judges(self):
        import re as _re
        on = self.doc[True] if True in self.doc else self.doc["on"]
        mine = on["schedule"][0]["cron"].split()
        lanes = {lane["file"]: lane for lane in hb.discover_lanes(str(ROOT / ".github" / "workflows"))}
        for file_name, entry in lanes.items():
            if not entry["scheduled"] or file_name == "automation-heartbeat.yml":
                continue
            for cron in entry["crons"]:
                other = cron.split()
                if other[1] == "*" or other[1] == mine[1]:
                    continue
                with self.subTest(lane=file_name, other=cron):
                    self.assertGreater(int(mine[1]), int(other[1]),
                                       "%s fires later than the lane it judges — judging "
                                       "'nothing arrived' before the arrival window closes is "
                                       "a daily false alarm" % file_name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
