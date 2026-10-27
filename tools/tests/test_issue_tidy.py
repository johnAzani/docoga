"""The automation closes its own alerts once the lane has healed (owner, 27 Oct 2026: "Close them
yourself"). Heartbeat's tracked issue, the weekly scorecard and anything a human opened stay."""
import json
import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import issue_tidy as it  # noqa: E402

NOW = datetime(2026, 10, 27, 22, 0, tzinfo=timezone.utc)
BOT = {"login": "github-actions[bot]"}


def issue(n, created, body="", labels=(), user=BOT):
    return {"number": n, "created_at": created, "body": body, "user": user,
            "labels": [{"name": l} for l in labels]}


class FakeApi:
    def __init__(self, issues, runs, healing):
        self.issues, self.runs, self.healing, self.calls = issues, runs, healing, []

    def __call__(self, method, path, token, params=None, body=None):
        self.calls.append((method, path, body))
        if path.endswith("/issues") and method == "GET":
            return 200, self.issues
        m = re.search(r"/actions/runs/(\d+)$", path)
        if m:
            r = self.runs.get(int(m.group(1)))
            return (200, r) if r else (404, {"message": "Not Found"})
        m = re.search(r"/actions/workflows/(\d+)/runs$", path)
        if m:
            return 200, {"workflow_runs": self.healing.get(int(m.group(1)), [])}
        if method in ("POST", "PATCH"):
            return 200, {}
        return 500, {}


class Tidy(unittest.TestCase):
    def test_a_healed_lane_closes_its_alert_with_the_healing_run_named(self):
        live = issue(140, "2026-10-26T06:33:26Z", "Run: https://github.com/johnAzani/docoga/actions/runs/40277819218", ["youtube-automation"])
        api = FakeApi([live], {40277819218: {"workflow_id": 7, "created_at": "2026-10-26T06:30:00Z"}},
                      {7: [{"created_at": "2026-10-27T12:05:00Z", "conclusion": "success", "name": "DocOga Live", "html_url": "https://x/runs/1"},
                           {"created_at": "2026-10-25T12:05:00Z", "conclusion": "success", "name": "DocOga Live", "html_url": "https://x/runs/0"}]})
        out = []
        n = it.tidy("johnAzani/docoga", "t", http=api, now=NOW, log=out.append)
        self.assertEqual(n, 1)
        patch = [c for c in api.calls if c[0] == "PATCH"]
        self.assertEqual(patch[0][1], "/repos/johnAzani/docoga/issues/140")
        self.assertEqual(patch[0][2]["state"], "closed")
        comment = [c for c in api.calls if c[0] == "POST"][0][2]["body"]
        self.assertIn("https://x/runs/1", comment)
        self.assertIn("a new failure opens a new issue", comment)
        self.assertIn("ISSUE_TIDY_CLOSED=1", out[-1])

    def test_an_alert_whose_lane_has_not_succeeded_since_stays_open(self):
        th = issue(98, "2026-10-18T12:12:01Z", "- Run: https://github.com/johnAzani/docoga/actions/runs/39126200072", ["threads-automation"])
        api = FakeApi([th], {39126200072: {"workflow_id": 3, "created_at": "2026-10-18T12:10:00Z"}}, {3: []})
        out = []
        self.assertEqual(it.tidy("r/r", "t", http=api, now=NOW, log=out.append), 0)
        self.assertFalse([c for c in api.calls if c[0] in ("POST", "PATCH")])
        self.assertIn("#98 open", out[0])

    def test_heartbeat_scorecard_and_human_issues_are_never_touched(self):
        rows = [issue(101, "2026-10-01T00:00:00Z", "", ["brain-scorecard"]),
                issue(88, "2026-09-01T00:00:00Z", "", ["automation-heartbeat"]),
                issue(5, "2026-09-01T00:00:00Z", "Run: https://github.com/x/actions/runs/1", ["youtube-automation"], user={"login": "johnAzani"})]
        api = FakeApi(rows, {1: {"workflow_id": 1}}, {1: [{"created_at": "2026-10-20T00:00:00Z", "conclusion": "success"}]})
        self.assertEqual(it.tidy("r/r", "t", http=api, now=NOW, log=lambda *_: None), 0)
        self.assertEqual([c for c in api.calls if c[0] != "GET"], [])

    def test_an_alert_with_no_readable_run_closes_only_after_fourteen_days(self):
        young = issue(200, "2026-10-20T00:00:00Z", "no link here", ["threads-automation"])
        old = issue(201, "2026-10-01T00:00:00Z", "Run: https://github.com/x/actions/runs/999", ["threads-automation"])
        api = FakeApi([young, old], {}, {})
        out = []
        self.assertEqual(it.tidy("r/r", "t", http=api, now=NOW, log=out.append), 1)
        self.assertIn("#200 open", out[0])
        self.assertIn("#201 closed", out[1])
        self.assertIn("26 days old", out[1])

    def test_dry_run_writes_nothing(self):
        live = issue(140, "2026-10-26T06:33:26Z", "Run: https://github.com/x/actions/runs/1", ["youtube-automation"])
        api = FakeApi([live], {1: {"workflow_id": 7}}, {7: [{"created_at": "2026-10-27T12:05:00Z", "conclusion": "success"}]})
        out = []
        self.assertEqual(it.tidy("r/r", "t", http=api, dry_run=True, now=NOW, log=out.append), 1)
        self.assertEqual([c for c in api.calls if c[0] != "GET"], [])
        self.assertIn("would close", out[0])

    def test_an_unreadable_api_never_fails_the_heartbeat(self):
        out = []
        self.assertEqual(it.tidy("r/r", "t", http=lambda *a, **k: (401, {"message": "Bad credentials"}), now=NOW, log=out.append), 0)
        self.assertIn("ISSUE_TIDY_CLOSED=0", out[-1])


class Wiring(unittest.TestCase):
    def test_the_heartbeat_runs_the_tidy_with_the_actions_token(self):
        wf = (ROOT / ".github" / "workflows" / "automation-heartbeat.yml").read_text(encoding="utf-8")
        self.assertIn("python3 tools/issue_tidy.py", wf)
        self.assertIn("issues: write", wf)
        self.assertIn("actions: read", wf)
        step = wf[wf.index("python3 tools/issue_tidy.py") - 900: wf.index("python3 tools/issue_tidy.py")]
        self.assertIn("GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}", step)
        self.assertIn("continue-on-error: true", step)


if __name__ == "__main__":
    unittest.main()
