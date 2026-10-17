"""The DocOga clock (17 Oct 2026): workers/clock rings every scheduled lane on time.

Pinned here: the committed schedule table is exactly what the workflows' crons say;
every dispatch input is one the workflow declares (an unknown input is a 422, i.e. a
missed post); Threads gets the slot its cron stands for and Instagram the `clock`
flag; the five-minute windows cover a day with no slot missed and none doubled; the
Python matcher and the Worker's JavaScript matcher agree; the Worker dispatches to
the right URL with the right body and stays idle without a token or when paused; the
late-cron guard stands down only when a dispatch exists; and the heartbeat counts a
clock dispatch as the cadence being kept.
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import clock_guard  # noqa: E402
import clock_schedule as cs  # noqa: E402

UTC = dt.timezone.utc
WORKER = ROOT / "workers" / "clock"


def utc(*parts):
    return dt.datetime(*parts, tzinfo=UTC)


class Table(unittest.TestCase):
    def setUp(self):
        self.rows = cs.entries()
        self.by_file = {}
        for row in self.rows:
            self.by_file.setdefault(row["workflow"], []).append(row)

    def test_the_committed_table_is_current(self):
        self.assertEqual(cs.SCHEDULE_JSON.read_text(encoding="utf-8"), cs.render(),
                         "run: python3 tools/clock_schedule.py emit")

    def test_every_scheduled_lane_is_rung_and_only_with_inputs_it_declares(self):
        lanes = {lane["file"]: lane for lane in cs.lanes()}
        self.assertIn("threads_autopost.yml", lanes)
        self.assertIn("youtube_scheduled.yml", lanes)
        for lane in lanes.values():
            if lane["dispatch"]:
                self.assertEqual(sorted(r["cron"] for r in self.by_file[lane["file"]]), sorted(lane["crons"]), lane["file"])
            for row in self.by_file.get(lane["file"], []):
                for key in row["inputs"]:
                    self.assertIn(key, lane["declared_inputs"], "%s sends undeclared input %r" % (lane["file"], key))
                for value in row["inputs"].values():
                    self.assertIsInstance(value, str, "dispatch inputs travel as strings")

    def test_threads_gets_its_slot_and_instagram_its_clock_flag(self):
        slots = {r["cron"]: r["inputs"]["slot"] for r in self.by_file["threads_autopost.yml"]}
        self.assertEqual(slots, {"20 6 * * *": "morning", "10 12 * * *": "lunch", "10 19 * * *": "evening"})
        for row in self.by_file["instagram_autopost.yml"]:
            self.assertEqual(row["inputs"], {"clock": "true"})
        for row in self.by_file["telegram_autopost.yml"]:
            self.assertEqual(row["inputs"], {})

    def test_a_day_of_ticks_dispatches_every_slot_exactly_once(self):
        day = dt.date(2026, 10, 19)                                       # a Monday: Shorts, LinkedIn, stats, scorecard
        want = sorted((when.astimezone(UTC).isoformat(), row["workflow"]) for when, row in cs.day_plan(self.rows, day))
        got = []
        start = dt.datetime.combine(day, dt.time(0, 0), tzinfo=cs.LAGOS)
        tick = start.astimezone(UTC)
        tick = tick.replace(minute=tick.minute - tick.minute % 5)
        while tick <= start + dt.timedelta(days=1):
            for row in cs.due(self.rows, tick):
                got.append((row["fires_at"], row["workflow"]))
            tick += dt.timedelta(minutes=5)
        got = sorted((f, w) for f, w in got if start.astimezone(UTC).isoformat() <= f < (start + dt.timedelta(days=1)).astimezone(UTC).isoformat())
        self.assertEqual(got, want)
        self.assertGreaterEqual(len(want), 20)
        self.assertEqual(len(want), len(set(want)))

    def test_a_late_tick_still_scans_its_own_window_only(self):
        rows = [{"workflow": "a.yml", "name": "a", "cron": "12 7 * * *", "inputs": {}}]
        self.assertEqual([r["workflow"] for r in cs.due(rows, utc(2026, 10, 19, 7, 15, 40))], ["a.yml"])
        self.assertEqual(cs.due(rows, utc(2026, 10, 19, 7, 10)), [])
        self.assertEqual(cs.due(rows, utc(2026, 10, 19, 7, 20)), [])

    def test_weekday_crons(self):
        self.assertTrue(cs.matches("0 17 * * 1-5", utc(2026, 10, 19, 17, 0)))    # Monday
        self.assertFalse(cs.matches("0 17 * * 1-5", utc(2026, 10, 18, 17, 0)))   # Sunday
        self.assertTrue(cs.matches("30 7 * * 1,3,5", utc(2026, 10, 21, 7, 30)))  # Wednesday
        self.assertTrue(cs.matches("0 5 * * 1", utc(2026, 10, 19, 5, 0)))
        self.assertTrue(cs.matches("*/5 * * * *", utc(2026, 10, 19, 5, 35)))
        self.assertFalse(cs.matches("0 5 * * 0", utc(2026, 10, 19, 5, 0)))
        self.assertTrue(cs.matches("0 5 * * 7", utc(2026, 10, 18, 5, 0)))       # 7 = Sunday too

    def test_check_cli_reports_current(self):
        out = subprocess.run([sys.executable, str(TOOLS / "clock_schedule.py"), "check"], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("CLOCK_SCHEDULE=current", out.stdout)


@unittest.skipUnless(shutil.which("node"), "node is not on PATH here")
class Worker(unittest.TestCase):
    """The JavaScript side, run under Node against the same fixtures."""

    def node(self, script):
        out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, cwd=WORKER)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def test_the_two_matchers_agree(self):
        crons = ["0 17 * * 1-5", "30 7 * * 1,3,5", "0 5 * * 1", "12 7 * * *", "20 6 * * *", "35 3 * * *", "0 5 * * 7", "*/5 * * * *"]
        stamps = [utc(2026, 10, d, h, m) for d in (18, 19, 21) for h in (3, 5, 6, 7, 17) for m in (0, 12, 20, 30, 35)]
        want = [[cs.matches(c, s) for s in stamps] for c in crons]
        script = """
import { matches } from './index.js';
const crons = %s, stamps = %s;
console.log(JSON.stringify(crons.map(c => stamps.map(s => matches(c, new Date(s))))));
""" % (json.dumps(crons), json.dumps([s.isoformat() for s in stamps]))
        self.assertEqual(json.loads(self.node(script)), want)

    def test_due_rows_from_the_committed_table(self):
        script = """
import { due } from './index.js';
import s from './schedule.json' with { type: 'json' };
const t = Date.UTC(2026, 9, 19, 12, 10);
console.log(JSON.stringify(due(s.entries, t, s.tick_minutes).map(r => [r.workflow, r.inputs])));
"""
        got = json.loads(self.node(script))
        self.assertIn(["instagram_autopost.yml", {"clock": "true"}], got)
        self.assertIn(["threads_autopost.yml", {"slot": "lunch"}], got)

    def test_tick_dispatches_with_the_right_call_and_stays_idle_without_a_token(self):
        script = """
import { tick } from './index.js';
const calls = [];
globalThis.fetch = async (url, init) => { calls.push({ url, method: init.method, auth: init.headers.Authorization, body: JSON.parse(init.body) }); return { status: 204, text: async () => '' }; };
const log = () => {};
const t = Date.UTC(2026, 9, 19, 12, 10);
const a = await tick({ GH_REPO: 'johnAzani/docoga', GH_DISPATCH_TOKEN: 'github_pat_x' }, t, log);
const b = await tick({ GH_REPO: 'johnAzani/docoga' }, t, log);
const c = await tick({ GH_REPO: 'johnAzani/docoga', GH_DISPATCH_TOKEN: 'github_pat_x', CLOCK: 'off' }, t, log);
console.log(JSON.stringify({ calls, a: a.results.length, b: [b.due.length, b.results.length], c: [c.paused, c.results.length] }));
"""
        got = json.loads(self.node(script))
        urls = [c["url"] for c in got["calls"]]
        self.assertIn("https://api.github.com/repos/johnAzani/docoga/actions/workflows/threads_autopost.yml/dispatches", urls)
        for call in got["calls"]:
            self.assertEqual(call["method"], "POST")
            self.assertEqual(call["auth"], "Bearer github_pat_x")
            self.assertEqual(call["body"]["ref"], "main")
        threads = next(c for c in got["calls"] if "threads" in c["url"])
        self.assertEqual(threads["body"]["inputs"], {"slot": "lunch"})
        self.assertEqual(got["a"], len(got["calls"]))
        self.assertEqual(got["b"], [got["a"], 0], "no token → nothing dispatched, the due list still computed")
        self.assertEqual(got["c"], [True, 0])

    def test_wrangler_config_uses_one_cron_trigger(self):
        toml = (WORKER / "wrangler.toml").read_text(encoding="utf-8")
        self.assertIn('crons = ["*/5 * * * *"]', toml)
        self.assertIn('name = "docoga-clock"', toml)
        self.assertNotIn("github_pat_", toml)


class Guard(unittest.TestCase):
    def opener(self, body=None, error=None):
        class Resp:
            def __init__(self, data):
                self.data = data

            def read(self):
                return json.dumps(self.data).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def open_(req, timeout=0):
            self.url = req.full_url
            if error:
                raise error
            return Resp(body)
        return open_

    def test_on_duty_when_a_dispatch_exists(self):
        v = clock_guard.verdict("o/r", "threads_autopost.yml", "t", now=utc(2026, 10, 19, 14, 0),
                                opener=self.opener({"workflow_runs": [{"id": 1}]}))
        self.assertEqual(v, "on-duty")
        self.assertIn("/repos/o/r/actions/workflows/threads_autopost.yml/runs?", self.url)
        self.assertIn("event=workflow_dispatch", self.url)
        self.assertIn("created=%3E%3D2026-10-18T02%3A00%3A00Z", self.url)

    def test_idle_without_a_dispatch_and_unknown_on_error(self):
        self.assertEqual(clock_guard.verdict("o/r", "x.yml", "t", opener=self.opener({"workflow_runs": []})), "idle")
        self.assertEqual(clock_guard.verdict("o/r", "x.yml", "t", opener=self.opener(error=urllib.error.URLError("down"))), "unknown")
        self.assertEqual(clock_guard.verdict("o/r", "x.yml", "", opener=self.opener({"workflow_runs": [1]})), "unknown")

    def test_only_a_scheduled_run_asks(self):
        out = subprocess.run([sys.executable, str(TOOLS / "clock_guard.py"), "--event", "workflow_dispatch", "--repo", "o/r", "--workflow", "x.yml"],
                             capture_output=True, text=True, env=dict(os.environ, GITHUB_TOKEN=""))
        self.assertIn("STAND_DOWN=no", out.stdout)
        self.assertIn("CLOCK=not-asked", out.stdout)
        self.assertEqual(clock_guard.workflow_file("johnAzani/docoga/.github/workflows/threads_autopost.yml@refs/heads/main"), "threads_autopost.yml")


class Workflows(unittest.TestCase):
    def test_threads_stands_down_behind_the_gate(self):
        import yaml
        doc = yaml.safe_load((ROOT / ".github/workflows/threads_autopost.yml").read_text(encoding="utf-8"))
        self.assertEqual(doc["jobs"]["publish"]["needs"], "gate")
        self.assertIn("needs.gate.outputs.go == 'true'", doc["jobs"]["publish"]["if"])
        self.assertEqual(doc["permissions"]["actions"], "read")
        gate = yaml.safe_dump(doc["jobs"]["gate"])
        self.assertIn("clock_guard.py", gate)

    def test_instagram_declares_the_clock_flag_and_its_gate_honours_it(self):
        import yaml
        doc = yaml.safe_load((ROOT / ".github/workflows/instagram_autopost.yml").read_text(encoding="utf-8"))
        on = doc.get(True) or doc.get("on")
        self.assertEqual(on["workflow_dispatch"]["inputs"]["clock"]["type"], "boolean")
        step = next(s for s in doc["jobs"]["slot"]["steps"] if s.get("id") == "gate")
        self.assertEqual(step["env"]["CLOCK"], "${{ inputs.clock }}")
        self.assertIn('if [ "${CLOCK:-false}" = "true" ]; then EVENT=schedule; fi', step["run"])

    def test_the_deployer_builds_the_table_and_forwards_the_token(self):
        text = (ROOT / ".github/workflows/deploy-clock.yml").read_text(encoding="utf-8")
        self.assertIn("python3 tools/clock_schedule.py emit", text)
        self.assertIn("secret put GH_DISPATCH_TOKEN", text)
        self.assertIn("secrets.GH_DISPATCH_TOKEN", text)
        self.assertNotIn("[skip ci]", text)

    def test_verify_and_build_check_no_longer_run_for_bookkeeping_pushes(self):
        import yaml
        verify = yaml.safe_load((ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8"))
        on = verify.get(True) or verify.get("on")
        self.assertEqual(on["push"]["branches"], ["main"])
        for path in ("logs/**", "assets/**", "site/social/**"):
            self.assertIn(path, on["push"]["paths-ignore"])
        self.assertIn("pull_request", on)
        build = yaml.safe_load((ROOT / ".github/workflows/build-check.yml").read_text(encoding="utf-8"))
        on = build.get(True) or build.get("on")
        self.assertEqual(on["push"]["branches"], ["main"])
        self.assertIn("site/**", on["push"]["paths"])


class Heartbeat(unittest.TestCase):
    def test_a_clock_dispatch_counts_as_the_cadence_being_kept(self):
        import automation_heartbeat as hb
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "repos/x/y/actions/workflows/777"))
            with open(os.path.join(tmp, "repos/x/y/actions/workflows/777/runs.json"), "w", encoding="utf-8") as handle:
                json.dump({"workflow_runs": [
                    {"created_at": "2026-10-19T12:10:30Z", "status": "completed", "conclusion": "success",
                     "html_url": "u1", "head_branch": "main", "event": "workflow_dispatch", "display_title": "clock"},
                ]}, handle)
            client = hb.GitHub("x", "y", fixture=tmp)
            runs = hb.recent_runs(client, 777, "main")
        self.assertEqual([r["url"] for r in runs], ["u1"], "the same run fetched under two event filters is one run")
        self.assertEqual(runs[0]["event"], "workflow_dispatch")
        now = utc(2026, 10, 19, 20, 0)
        line = hb.clock_line({777: runs}, now)
        self.assertTrue(line.startswith("CLOCK=on-duty dispatched_24h=1 github_cron_24h=0"))
        self.assertTrue(hb.clock_line({}, now).startswith("CLOCK=idle"))


if __name__ == "__main__":
    unittest.main()
