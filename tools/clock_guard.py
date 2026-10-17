#!/usr/bin/env python3
"""Is the DocOga clock on duty for this workflow? — a late GitHub cron asks before posting.

Since 17 Oct 2026 the lanes are rung on time by workers/clock (workflow_dispatch) and
GitHub's own `schedule:` is only a backstop that arrives hours late, when it arrives.
For once-a-day lanes a late backstop is harmless: the duplicate guard sees today's
post and stands down. For the lanes with several slots a day it is not: a Threads
cron that fires at 16:00 UTC instead of 12:10 would read the hour, call itself the
*evening* slot and post the evening copy four hours early.

So a scheduled run of such a lane asks: "has the clock dispatched this workflow in
the last `--hours` (36)?" If yes, the clock is on duty and the late cron stands down
(CLOCK=on-duty). If no run was dispatched — the token was never minted, or it died —
the cron is the only clock left and the run goes ahead (CLOCK=idle). If GitHub cannot
be asked, the run goes ahead too (CLOCK=unknown): the publishers' own guards are the
last word, and a monitor must never be the reason a post was missed.

Prints exactly one `CLOCK=…` line and `STAND_DOWN=yes|no`; exit code is always 0.
Reads GITHUB_TOKEN (actions: read), GITHUB_REPOSITORY and GITHUB_WORKFLOW_REF, or
`--repo` / `--workflow` for tests and hand runs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
DEFAULT_HOURS = 36


def workflow_file(ref: str) -> str:
    """'owner/repo/.github/workflows/threads_autopost.yml@refs/heads/main' → 'threads_autopost.yml'."""
    path = ref.split("@", 1)[0]
    return path.rsplit("/", 1)[-1]


def fetch(url: str, token: str, opener=None) -> dict:
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer %s" % token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "docoga-clock-guard",
    })
    opener = opener or urllib.request.urlopen
    with opener(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def verdict(repo: str, workflow: str, token: str, hours: int = DEFAULT_HOURS, now=None, opener=None) -> str:
    """→ 'on-duty' | 'idle' | 'unknown'."""
    if not token or not repo or not workflow:
        return "unknown"
    now = now or dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = urllib.parse.urlencode({"event": "workflow_dispatch", "created": ">=" + since, "per_page": 10})
    url = "%s/repos/%s/actions/workflows/%s/runs?%s" % (API, repo, workflow, query)
    try:
        body = fetch(url, token, opener)
    except (urllib.error.URLError, OSError, ValueError):
        return "unknown"
    runs = body.get("workflow_runs") if isinstance(body, dict) else None
    if runs is None:
        return "unknown"
    return "on-duty" if runs else "idle"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="stand a late GitHub cron down when the clock is on duty")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--workflow", default=workflow_file(os.environ.get("GITHUB_WORKFLOW_REF", "")))
    ap.add_argument("--event", default=os.environ.get("GITHUB_EVENT_NAME", ""))
    ap.add_argument("--hours", type=int, default=DEFAULT_HOURS)
    a = ap.parse_args(argv)
    if a.event and a.event != "schedule":
        print("CLOCK=not-asked (event=%s — only a scheduled run asks)" % a.event)
        print("STAND_DOWN=no")
        return 0
    state = verdict(a.repo, a.workflow, os.environ.get("GITHUB_TOKEN", ""), a.hours)
    print("CLOCK=%s" % state)
    print("STAND_DOWN=%s" % ("yes" if state == "on-duty" else "no"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
