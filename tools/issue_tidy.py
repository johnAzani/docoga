#!/usr/bin/env python3
"""issue_tidy.py — the automation closes its own alerts once the lane has healed.

Every lane that fails opens a visible issue ("Threads post failed — 2026-10-18", "DocOga Live: a
control run failed"). Nothing closed them: the agent's token cannot write issues, and the owner
was being asked to tidy up after machines (27 Oct 2026: "Close them yourself"). This runs inside
the nightly heartbeat with the Actions token, which can.

Rule, in one sentence: an alert opened by github-actions is closed when the workflow that opened
it has completed a **successful** run since the alert was created — the failure it reported is
over, and a new failure opens a new issue anyway. Alerts whose run can no longer be found are
closed only after STALE_DAYS, with the reason said plainly.

Never touched: the heartbeat's own tracked issue (label `automation-heartbeat`, it manages
itself) and the living weekly scorecard (label `brain-scorecard`). Issues a human opened are
never touched either.

    python3 tools/issue_tidy.py            # close what has healed
    python3 tools/issue_tidy.py --dry-run  # say what would close, write nothing

Prints one `ISSUE_TIDY=` line per decision and `ISSUE_TIDY_CLOSED=<n>` at the end. Exit 0 always
when the API answered; a monitor that cannot read must not fail the heartbeat.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"
RUN_URL = re.compile(r"/actions/runs/(\d+)")
STALE_DAYS = 14
KEEP_LABELS = {"automation-heartbeat", "brain-scorecard"}
BOT_LOGINS = {"github-actions[bot]", "github-actions"}
HTTP_TIMEOUT = 30


def _http(method, path, token, params=None, body=None):
    url = path if path.startswith("http") else API + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "docoga-issue-tidy",
        **({"Content-Type": "application/json"} if data else {})})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"message": raw[:200]}


def _when(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def run_for(body):
    m = RUN_URL.search(body or "")
    return int(m.group(1)) if m else None


def decide(issue, run, healing_runs, now):
    """(close?, reason). `run` is the run the alert points at (or None); `healing_runs` the
    successful runs of that workflow created after the issue."""
    created = _when(issue["created_at"])
    if run and healing_runs:
        latest = max(healing_runs, key=lambda r: r["created_at"])
        return True, ("the lane has run successfully since (%s, %s) — the failure this alert reported is over; "
                      "a new failure opens a new issue" % (latest.get("name") or "run", latest.get("html_url") or ""))
    if run is None and (now - created) > timedelta(days=STALE_DAYS):
        return True, ("this alert does not point at a run I can read and is %d days old; a newer failure would have "
                      "opened a newer issue" % (now - created).days)
    if run and not healing_runs:
        return False, "no successful run of that workflow since the alert — still open"
    return False, "waiting"


def tidy(repo, token, http=_http, dry_run=False, now=None, log=print):
    now = now or datetime.now(timezone.utc)
    st, issues = http("GET", "/repos/%s/issues" % repo, token, params={"state": "open", "per_page": 100})
    if st != 200 or not isinstance(issues, list):
        log("::warning title=Issue tidy could not list issues::HTTP %s %s" % (st, json.dumps(issues)[:160]))
        log("ISSUE_TIDY_CLOSED=0")
        return 0
    closed = 0
    for issue in issues:
        if issue.get("pull_request"):
            continue
        login = (issue.get("user") or {}).get("login", "")
        labels = {l.get("name") for l in issue.get("labels") or []}
        if login not in BOT_LOGINS or labels & KEEP_LABELS:
            continue
        run_id = run_for(issue.get("body"))
        run, healing = None, []
        if run_id:
            st, run = http("GET", "/repos/%s/actions/runs/%d" % (repo, run_id), token)
            if st != 200:
                run = None
            else:
                st, runs = http("GET", "/repos/%s/actions/workflows/%s/runs" % (repo, run["workflow_id"]), token,
                                params={"status": "success", "per_page": 20, "created": ">=" + issue["created_at"][:10]})
                healing = [r for r in (runs.get("workflow_runs") or []) if st == 200
                           and _when(r["created_at"]) > _when(issue["created_at"]) and r.get("conclusion") == "success"]
        close, reason = decide(issue, run, healing, now)
        n = issue["number"]
        if not close:
            log("ISSUE_TIDY=#%d open — %s" % (n, reason))
            continue
        if dry_run:
            log("ISSUE_TIDY=#%d would close — %s" % (n, reason))
            closed += 1
            continue
        comment = "Closing automatically: %s." % reason
        http("POST", "/repos/%s/issues/%d/comments" % (repo, n), token, body={"body": comment})
        st, _ = http("PATCH", "/repos/%s/issues/%d" % (repo, n), token, body={"state": "closed", "state_reason": "completed"})
        if st == 200:
            closed += 1
            log("ISSUE_TIDY=#%d closed — %s" % (n, reason))
        else:
            log("ISSUE_TIDY=#%d not closed (HTTP %s)" % (n, st))
    log("ISSUE_TIDY_CLOSED=%d" % closed)
    return closed


def main(argv=None):
    ap = argparse.ArgumentParser(description="close automation alerts whose lane has healed")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "johnAzani/docoga"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not token:
        print("::warning title=Issue tidy skipped::no GITHUB_TOKEN")
        print("ISSUE_TIDY_CLOSED=0")
        return 0
    tidy(a.repo, token, dry_run=a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
