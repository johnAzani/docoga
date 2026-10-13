#!/usr/bin/env python3
"""Read the last runs of an automation lane, and what they said about themselves.

Why this exists: the log *bytes* of a run live on a host sandboxes usually cannot reach
(`results-receiver.actions.githubusercontent.com`), so `gh run view --log` fails right when the
answer is needed most. The job and step *conclusions*, and the check-run **annotations**, are plain
REST and readable with any token — including the Actions token, including from a locked-down
agent. That is exactly how `chat not found` was found on 13 Oct 2026: a preflight's own `::error`
line, two years of handbooks later, still the fastest truth in this repo.

Read-only by construction. Nothing here posts, files, comments, downloads logs, or prints a
secret — the output goes through a redaction pass, because an annotation quoting a bot token
would otherwise become the leak this tool exists to avoid.

    python3 tools/lane_status.py --lane telegram
    python3 tools/lane_status.py --lane youtube --limit 3 --json

Exit codes: 0 the newest run succeeded · 1 it failed or is still running red · 2 the lane could not
be read (no `gh`, no runs, no permission). The point of a status tool is that it can be a gate.
"""

import argparse
import json
import os
import re
import subprocess
import sys

# Lane aliases, so nobody has to remember whether the file is `youtube_scheduled.yml` or
# `youtube_autopost.yml` (both exist, and only one of them is the scheduled one).
LANES = {
    "telegram": "telegram_autopost.yml",
    "facebook": "facebook_autopost.yml",
    "youtube": "youtube_scheduled.yml",
    "youtube-legacy": "youtube_autopost.yml",
    "instagram": "instagram_autopost.yml",
    "threads": "threads_autopost.yml",
    "heartbeat": "automation-heartbeat.yml",
}

REPO_FALLBACK = "johnAzani/docoga"

# What a run's annotations might contain if a `::error` line quotes the thing it was given. These
# are deliberately blunt: better a redacted diagnostic than a careful one that leaks.
REDACTIONS = (
    re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{20,}"),          # Telegram bot token
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),               # GitHub token
    re.compile(r"\bya29\.[A-Za-z0-9_\-]{20,}"),                # Google access token
    re.compile(r"\b1//[\w-]{40,}"),                            # Google refresh token
    re.compile(r"(?i)(secret|token|password)\s*[=:]\s*\S+"),
    re.compile(r"-100\d{8,}"),                                  # numeric channel id
)

# The runner's own bookkeeping steps, and the *mirrors* of `Post <step>` cleanup lines. A prefix
# rule looks harmless until it swallows `Post to Telegram`, which is the step that matters most.
RUNNER_BOOKKEEPING = ("Set up job", "Complete job")


def redact(text):
    out = text if isinstance(text, str) else str(text)
    for pattern in REDACTIONS:
        out = pattern.sub("[redacted]", out)
    return out


def gh_api(endpoint, run=None):
    """One `gh api` GET. Injectable so the tests never depend on a token or a network."""
    run = run or subprocess.run
    result = run(["gh", "api", endpoint], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "gh api failed").strip()[:300])
    return json.loads(result.stdout or "{}")


def resolve(workflow, repo, run=None):
    """The workflow file's id and state, so a typo is an error and not an empty report."""
    data = gh_api("repos/%s/actions/workflows" % repo, run=run)
    for item in data.get("workflows", []):
        if item.get("path", "").endswith("/" + workflow):
            return item
    return None


def recent_runs(workflow_id, repo, branch=None, limit=1, run=None):
    endpoint = "repos/%s/actions/workflows/%s/runs?per_page=%d" % (repo, workflow_id, max(1, limit))
    if branch:
        endpoint += "&branch=%s" % branch
    data = gh_api(endpoint, run=run)
    return data.get("workflow_runs", [])


def executed(item, repo, run=None):
    """Did the runner actually run this, or did Actions only file it?

    A `push` that touches a workflow file whose copy on the default branch differs from the
    pushed one produces a run with `conclusion=failure` and **no jobs**: nothing executed, nothing
    annotated, nothing posted. `lane_status` used to print that as the lane's latest failure, and
    it is a convincing lie — on 13 Oct 2026 it sent the author of the Instagram lane hunting for a
    posting failure that had never touched the API. So ask the one question that decides it, and
    only ask it when a run would otherwise be believed.
    """
    if item.get("conclusion") not in ("failure", "cancelled", "timed_out"):
        return True  # a run that *succeeded* obviously executed; asking would cost a call to
                     # confirm good news. The artefact's shape is a completed failure with no jobs,
                     # so only those are questioned.
    data = gh_api("repos/%s/actions/runs/%s/jobs" % (repo, item.get("id")), run=run)
    return bool(data.get("jobs"))


def drop_unexecuted(runs, repo, run=None):
    """Drop the runs Actions filed without executing, and count them.

    The whole list is filtered rather than truncated to the requested `--limit`: the history and
    the consecutive-failure streak are computed from it, and a report that quietly kept one run
    would turn "5 consecutive failures" into "no pattern" — which `tools/tests/test_lane_status.py`
    caught the day this function was written.
    """
    kept, skipped = [], 0
    for item in runs:
        if executed(item, repo, run=run):
            kept.append(item)
        else:
            skipped += 1
    return kept, skipped


def job_detail(run_id, repo, run=None):
    """Every job, its failing steps, and its annotations — the whole story of one run."""
    jobs = []
    data = gh_api("repos/%s/actions/runs/%s/jobs" % (repo, run_id), run=run)
    for job in data.get("jobs", []):
        names = [s.get("name", "") for s in job.get("steps", [])]
        failed = []
        for step in job.get("steps", []):
            name = step.get("name", "")
            if step.get("conclusion") not in ("failure", "cancelled"):
                continue
            if name in RUNNER_BOOKKEEPING:
                continue
            # `Post Checkout repository` is the runner cleaning up after `Checkout repository`.
            # It counts as bookkeeping only while that mirror exists — otherwise a real step that
            # happens to start with "Post " (in this repo: `Post to Telegram`) would be swallowed.
            if name.startswith("Post ") and name[len("Post "):] in names:
                continue
            failed.append(step)
        skipped = [s.get("name") for s in job.get("steps", []) if s.get("conclusion") == "skipped"]
        try:
            payload = gh_api("repos/%s/check-runs/%s/annotations" % (repo, job.get("id")), run=run)
            # A bare array from the REST endpoint, or wrapped by whoever proxied it: accept both,
            # because a status tool that crashes on a shape it did not predict is worse than one
            # that says "unreadable".
            annotations = payload if isinstance(payload, list) else (payload or {}).get("annotations", [])
        except Exception as exc:  # annotations are a bonus; missing them is not a missing status
            # A `warning`, not a `notice`: notices are filtered from the report as routine runner
            # chatter, and this line is the opposite of routine — it says what is *not* known.
            annotations = [{"annotation_level": "warning",
                            "message": "annotations unreadable for job %s: %s" % (job.get("id"), exc)}]
        jobs.append({
            "name": job.get("name"),
            "conclusion": job.get("conclusion"),
            "id": job.get("id"),
            "failed_steps": [{"step": s.get("name"), "conclusion": s.get("conclusion")} for s in failed],
            "skipped_after": skipped[:4],
            "annotations": [{"level": a.get("annotation_level"),
                             "where": "%s:%s" % (a.get("path"), a.get("start_line")),
                             "message": redact(a.get("message") or "")} for a in annotations],
        })
    return jobs


def describe(run_id, repo, run=None):
    lines = []
    for job in job_detail(run_id, repo, run=run):
        lines.append("  job %s → %s" % (job["name"], job["conclusion"]))
        for step in job["failed_steps"]:
            lines.append("    ✗ %s (%s)" % (step["step"], step["conclusion"]))
        if job["skipped_after"]:
            lines.append("    – never ran: %s" % ", ".join(job["skipped_after"]))
        for note in job["annotations"]:
            if note["level"] == "notice":
                continue
            lines.append("    [%s] %s" % (note["level"], note["message"][:220]))
    return lines


def main(argv=None, run=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--lane", required=True, help="telegram | facebook | youtube | instagram | heartbeat")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY") or REPO_FALLBACK)
    parser.add_argument("--branch", default="", help="default: the repository's default branch")
    parser.add_argument("--limit", type=int, default=1, help="how many recent runs to report (max 10)")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    workflow = LANES.get(args.lane, args.lane)
    try:
        found = resolve(workflow, args.repo, run=run)
        if not found:
            print("lane_status: no workflow named %s in %s — known lanes: %s"
                  % (workflow, args.repo, ", ".join(sorted(LANES))), file=sys.stderr)
            return 2
        runs = recent_runs(found["id"], args.repo, branch=args.branch or None,
                           limit=min(10, max(1, args.limit)), run=run)
    except Exception as exc:
        print("lane_status: could not read %s (%s)" % (workflow, redact(str(exc))), file=sys.stderr)
        return 2

    if not runs:
        print("lane_status: %s has never run on %s" % (workflow, args.branch or "the default branch"))
        return 2

    runs, skipped = drop_unexecuted(runs, args.repo, run=run)
    if not runs:
        print("lane_status: %s has %d recent run(s) on record and the runner executed none of "
              "them — Actions files an empty run when a workflow's copy on a branch differs from "
              "the default branch's. Nothing was posted and nothing failed; merge the file."
              % (workflow, skipped))
        return 2

    newest = runs[0]
    report = {
        "workflow": workflow,
        "unexecuted_runs_ignored": skipped,
        "state": found.get("state"),
        "run_id": newest.get("id"),
        "created": newest.get("created_at"),
        "event": newest.get("event"),
        "branch": (newest.get("head_branch") or ""),
        "conclusion": newest.get("status") == "completed" and newest.get("conclusion") or newest.get("status"),
        "history": [{"created": r.get("created_at"), "event": r.get("event"),
                     "conclusion": r.get("conclusion"), "branch": r.get("head_branch"),
                     "id": r.get("id")} for r in runs],
    }
    if not args.as_json:
        print("%s — %s" % (workflow, report["state"]))
        print("  latest: %s  [%s]  %s on %s" % (report["created"], report["conclusion"],
                                                report["event"], report["branch"]))
        if skipped:
            print("  · %d run(s) with no jobs ignored: Actions filed them without executing the "
                  "file — they are not lane outcomes" % skipped)
        for line in describe(newest.get("id"), args.repo, run=run):
            print(line)
        if len(runs) > 1:
            # Counted from the newest backwards, inclusive, so the number is the streak and not
            # the streak-minus-one; "3 consecutive failures" is the sentence that changes a plan.
            streak = 0
            for older in runs:
                if older.get("conclusion") != newest.get("conclusion"):
                    break
                streak += 1
            if streak > 1:
                print("  ⚠️ %d consecutive runs with conclusion=%s — this is a pattern, not a blip"
                      % (streak, report["conclusion"]))
    else:
        report["detail"] = job_detail(newest.get("id"), args.repo, run=run)
        print(json.dumps(report, indent=2, sort_keys=True))

    return 0 if report["conclusion"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
