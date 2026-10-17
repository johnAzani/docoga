#!/usr/bin/env python3
"""
automation_heartbeat.py — is any growth lane quietly dead?
==========================================================

The failure this exists for is not "a run failed". It is *nobody noticed*:

  * Telegram: four silent failed days in early Oct 2026 (the poster exited 0 on
    API errors), then **six** consecutive scheduled failures from 8 Oct because a
    red tick in a repo nobody opens is also silence;
  * Facebook: `docs/GROWTH_ENGINE.md` asserted "live 26 Sep — photos + videos" for
    a workflow whose run count was **zero** and which had no schedule at all;
  * YouTube: one scheduled failure on 9 Oct, no run since, no diagnosis.

Every one of those is "the pipeline is not running" meeting "nothing tells the
owner". Per-workflow issues already cover the first half of that story — a lane
that fails *loudly*. What nothing covered is the lane that stops failing loudly by
being switched off, renamed, disabled by GitHub for inactivity, or edited until its
`schedule:` disappears. A workflow that never runs produces no failure and no
notification. That is the gap this fills.

Method — expectations are derived, never hardcoded
--------------------------------------------------
The lanes come from this repo's own `.github/workflows/*.yml`: a file with
`on.schedule[].cron` is a lane with a cadence; a file without one is a manual tool
and is reported as such, never alarmed. The expected gap is computed by enumerating
this cron's own fire times over a 60-day window and taking the largest gap between
two consecutive ones — so `0 8 * * *` is 1 day, `0 17 * * 2,5` is ~4 days (the
weekend), `0 0 1 * *` is ~31 days, and a hand-written `*/15 9-17 * * 1-5` measures
itself. No table of lanes to update when a schedule changes, which is the failure
mode every "monitoring config" drifts into. Two details that were both wrong in the
first draft and are now asserted in tests:

  * **all `cron:` entries of one workflow are measured together.** GitHub treats them
    as one alternative set, so `0 8 * * *` + `0 20 * * *` is a 12-hour lane. Taking
    the max gap *per entry* called it two 24-hour lanes and tolerated a day of
    silence from a lane that should have spoken twice;
  * **the enumeration is exact, not a sampled scan.** A 15-minute sampler cannot see
    `30 8 * * *`'s neighbour `7 0 * * *`, and a cron it cannot see is a cadence of
    zero — which reads as "never late".

A lane is `fail` when any of these is true:
  1. its file declares a cron but GitHub has never registered the workflow, or the
     workflow's state is not `active` (GitHub sets `disabled_inactivity` /
     `disabled_missing_permissions` on its own, silently, and that is precisely a
     lane going dark without a failure);
  2. no **successful** scheduled run on the default branch within
     `2 × expected_gap + slack` (slack = 12 h, capped at one cycle so a fast lane
     cannot hide behind a slow lane's tolerance) — the 12 h is not padding: GitHub delays
     `schedule` events by hours under load, and this repo's own history shows it
     (Telegram's "daily 08:30 UTC" ran at 17:31, 14:45 and 14:19 UTC on three
     consecutive days). Judging by wall-clock instead of age is how a monitor ends
     up crying wolf and getting ignored;
  3. there is no completed scheduled run at all and the lane's file is older than
     the grace window (a lane merged an hour ago is not "silent" yet — `--grace-days`).
A scheduled `fail` is *downgraded to `warn`* when this checkout is not the default
branch and the default branch's copy of that file has no `schedule:` — GitHub only
runs schedules from the default branch, so "it has never fired" is a statement about
the merge queue, not about the lane. It is also left out of the signature: a monitor
that files issues about unmerged branches is a monitor that gets muted.
A lane is `warn` (never red) on `streak`: 2+ consecutive failed scheduled runs, or
a last run that failed once. A `warn` with no `fail` is a green run carrying
annotations — the loud version is reserved for "nothing arrived".

Why it exits green on a repeat, and red on a change
---------------------------------------------------
A daily red run is a daily email. Once the owner has been told, the correct signal
is *still visible, louder only when it changes*. So the verdicts are hashed into a
short `HEARTBEAT_SIGNATURE`; the workflow compares it against the open heartbeat
issue and files/comment + exits 1 only when the signature is new. Steady-state
broken ⇒ one comment a day, green run, same issue. This is the same
"skipped ≠ failed" law the publishers use, applied to the monitor itself.

What the issue says
-------------------
Per failing lane: the verdict, the deadline arithmetic that produced it, the two `gh`
commands that confirm it in one line, and **the names of the secrets and `vars.` that
lane reads** — lifted from the same file's `${{ secrets.* }}` references, with its own
failure-issue label (`gh issue list --label telegram-automation --state open`) when it
files one. Values are never readable from here and the body says so; "check the
config" is not an instruction, `gh secret list` is.

Usage
-----
  python3 tools/automation_heartbeat.py                      # live, needs a token
  python3 tools/automation_heartbeat.py --dry-run --verbose   # never writes anything
  python3 tools/automation_heartbeat.py --fixture /tmp/hb     # offline replay (tests)

Exit codes
----------
  0  every scheduled lane is within its cadence (or there is nothing scheduled)
  1  at least one lane is dead/silent/disabled — new verdict signature
  3  the heartbeat could not answer (no token, API refused, YAML unreadable).
     It must not report "all lanes healthy" when it could not look: a monitor that
     guesses optimism is worse than no monitor.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

try:
    import yaml
except ImportError:                                            # pragma: no cover
    sys.stderr.write("automation_heartbeat needs PyYAML: pip install pyyaml\n")
    raise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS_DIR = os.path.join(ROOT, ".github", "workflows")

# GitHub's scheduler is not punctual — see the docstring. Hours of delay is normal,
# so the deadline has to be generous or the monitor becomes noise.
SCHEDULE_JITTER = timedelta(hours=12)
# How long the gap a cadence may miss before it counts as silence.
MISSES_BEFORE_SILENT = 2
# A lane whose file was just merged gets this long before "never ran" is a finding.
DEFAULT_LANE_GRACE = timedelta(days=2)
RUNS_PER_LANE = 20
CRON_WINDOW_DAYS = 60
HTTP_TIMEOUT = 30

# Which fields a 5-part cron has, in order. Only what cron(5) needs; `@daily` and
# friends are expanded, because a schedule written that way is still a cadence and
# "unsupported expression" is a bad reason to skip a lane.
CRON_ALIASES = {
    "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
CRON_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
FIELD_NAMES = ("minute", "hour", "day-of-month", "month", "day-of-week")


# ── small time helpers ──────────────────────────────────────────────────────
def parse_stamp(value):
    """GitHub's ISO-8601 (`2026-10-12T17:31:57Z`) → aware datetime. None if absent."""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def iso(value):
    return value.isoformat() if value is not None else ""


# ── cron: enumerate, then measure the gap ───────────────────────────────────
def _cron_field(spec, low, high):
    """One cron field → the set of integers it matches. Raises ValueError if not."""
    spec = (spec or "*").strip()
    values = set()
    for part in spec.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            part, _, step_text = part.partition("/")
            try:
                step = int(step_text)
            except ValueError:
                raise ValueError("bad step in %r" % spec)
            if step < 1:
                raise ValueError("step must be >= 1 in %r" % spec)
        part = part.strip()
        if part in ("", "*"):
            start, end = low, high
        elif "-" in part:
            start_text, _, end_text = part.partition("-")
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(part)
        if start < low or end > high or end < start:
            raise ValueError("%r is outside %d-%d" % (part, low, high))
        values.update(range(start, end + 1, step))
    return values


def cron_matches(fields, moment):
    minute, hour, dom, month, dow = fields
    # Vixie-cron rule: when both day fields are restricted, either may match.
    dom_restricted = dom != set(range(1, 32))
    dow_restricted = dow != set(range(0, 7))
    day_ok = (moment.day in dom or moment.weekday_cron in dow) if (
        dom_restricted and dow_restricted) else (moment.day in dom and moment.weekday_cron in dow)
    return (moment.minute in minute and moment.hour in hour and day_ok
            and moment.month in month)


class _Moment(object):
    """The five numbers cron cares about, with cron's Sunday=0 weekday."""

    __slots__ = ("minute", "hour", "day", "month", "weekday_cron")

    def __init__(self, when):
        self.minute = when.minute
        self.hour = when.hour
        self.day = when.day
        self.month = when.month
        # python: Monday=0..Sunday=6 → cron: Sunday=0..Saturday=6
        self.weekday_cron = (when.weekday() + 1) % 7


def parse_cron(expression):
    """`'0 17 * * 2,5'` → list of five int-sets. ValueError on anything odd."""
    text = CRON_ALIASES.get((expression or "").strip(), (expression or "").strip())
    parts = text.split()
    if len(parts) != 5:
        raise ValueError("expected 5 fields, got %d: %r" % (len(parts), expression))
    return [_cron_field(part, low, high) for part, (low, high) in zip(parts, CRON_RANGES)]


def cron_times(expression, start, days=CRON_WINDOW_DAYS):
    """Every time this cron fires in [start, start+days). Exact, not a scan.

    A 15-minute sampling scan was the first version and it was wrong twice over: it
    cannot see a cron that fires at minute 7, and it measures each `cron:` entry
    separately when GitHub treats several entries as one alternative set. Enumerating
    the minute×hour product per matching day is both exact and cheaper than the scan.
    """
    fields = parse_cron(expression)
    minute, hour, dom, month, dow = fields
    minutes = sorted(minute)
    hours = sorted(hour)
    dom_restricted = dom != set(range(1, 32))
    dow_restricted = dow != set(range(0, 7))
    out = []
    cursor = datetime.combine(start.date(), datetime.min.time(), tzinfo=timezone.utc)
    for offset in range(days + 1):
        day = cursor + timedelta(days=offset)
        cron_weekday = (day.weekday() + 1) % 7
        dom_ok = day.day in dom
        dow_ok = cron_weekday in dow
        if dom_restricted and dow_restricted:
            day_ok = dom_ok or dow_ok
        else:
            day_ok = dom_ok and dow_ok
        if not day_ok or day.month not in month:
            continue
        for hour_value in hours:
            for minute_value in minutes:
                moment = day.replace(hour=hour_value, minute=minute_value)
                if moment >= start:
                    out.append(moment)
    out.sort()
    return out


def expected_gap(crons, start=None):
    """Largest gap between consecutive fires of *all* the entries, in seconds.

    All entries are measured together because that is what GitHub does: a workflow
    with `0 8 * * *` and `0 20 * * *` is a 12-hour lane, not two 24-hour lanes, and
    judging it as the latter means the monitor tolerates a day of silence from a
    lane that should have spoken twice.

    Returns (seconds, detail) or (None, why-not). A cron that matches nothing in the
    window is reported rather than assumed to be daily — an unmeasurable cadence is a
    finding about the schedule, which is a different and more useful thing than a
    finding about the lane.
    """
    start = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
    times = []
    for expression in crons:
        try:
            times.extend(cron_times(expression, start))
        except (ValueError, TypeError) as exc:
            return None, "cron %r is not readable (%s)" % (expression, exc)
    if not times:
        return None, "no cron in %s fires in %d days — the schedule matches nothing" % (
            ", ".join(repr(c) for c in crons), CRON_WINDOW_DAYS)
    times.sort()
    if len(times) == 1:
        # Monthly or rarer: the window is the only honest estimate.
        return CRON_WINDOW_DAYS * 86400, "one fire in %d days" % CRON_WINDOW_DAYS
    internal = [int((b - a).total_seconds()) for a, b in zip(times, times[1:])]
    wrap = int((times[0] + timedelta(days=CRON_WINDOW_DAYS) - times[-1]).total_seconds())
    gap = max(internal + [wrap])
    return gap, "%d entry(ies), max gap %s" % (len(crons), human_duration(gap))


def silence_deadline(gap, jitter, misses):
    """Seconds after the last success before a lane counts as silent.

    The scheduler slack is capped at one cycle: GitHub's delay is measured in hours,
    and 12 h of tolerance on a lane that fires every 30 minutes would mean the
    monitor can only ever notice that the lane is *gone*, not that it stopped.
    """
    slack = min(int(jitter), max(int(gap), 3600))
    return int(gap) * max(1, int(misses)) + slack


def human_duration(seconds):
    seconds = int(seconds)
    if seconds < 90:
        return "%ds" % seconds
    if seconds < 5400:
        return "%dm" % round(seconds / 60.0)
    if seconds < 2 * 86400:
        return "%.1fh" % (seconds / 3600.0)
    return "%.1f days" % (seconds / 86400.0)


# ── lane discovery ──────────────────────────────────────────────────────────
_REFERENCES = re.compile(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)")
_VAR_REFERENCES = re.compile(r"vars\.([A-Za-z_][A-Za-z0-9_]*)")
_ISSUE_LABEL = re.compile(r"--label ([a-z0-9][a-z0-9-]*)")
# Which durable record a lane promises to write, read from the workflow's own text for
# the same reason the cadence is: the day a lane grows a ledger (or renames one), the
# monitor should notice without anyone editing a list in here.
_LEDGER_FILE = re.compile(r"\blogs/([A-Za-z0-9_.-]+\.json)")


def _named(names, drop=None):
    """Unique, in first-use order. A workflow references the same secret in three
    steps; a list with duplicates in an issue body reads like a bug in the reader."""
    seen, out = set(), []
    for item in names:
        if item == drop or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def discover_lanes(workflows_dir=WORKFLOWS_DIR):
    """Every workflow file, with the cadence it declares (possibly none).

    `on:` parses as the boolean True in YAML 1.1 — the same trap the repo's contract
    tests document — so both spellings are checked.
    """
    lanes = []
    if not os.path.isdir(workflows_dir):
        return lanes
    for name in sorted(os.listdir(workflows_dir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        path = os.path.join(workflows_dir, name)
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
                doc = yaml.safe_load(text) or {}
        except Exception as exc:
            lanes.append({"file": name, "error": "unreadable YAML (%s)" % exc.__class__.__name__,
                          "crons": [], "name": name, "scheduled": False,
                          "secrets": [], "vars": [], "labels": [], "ledgers": []})
            continue
        on = doc.get("on") if isinstance(doc.get("on"), dict) else doc.get(True) or {}
        if not isinstance(on, dict):
            on = {}
        crons = []
        for entry in (on.get("schedule") or []):
            if isinstance(entry, dict) and entry.get("cron"):
                crons.append(str(entry["cron"]))
        job_name = ""
        jobs = doc.get("jobs") or {}
        if isinstance(jobs, dict) and jobs:
            first = list(jobs.values())[0]
            if isinstance(first, dict):
                job_name = str(first.get("name") or "")
        lanes.append({
            "file": name,
            "name": doc.get("name") or name,
            "job": job_name,
            "crons": crons,
            "scheduled": bool(crons),
            "dispatch": bool(on.get("workflow_dispatch") is not None
                             or "workflow_dispatch" in (on or {})),
            "path": ".github/workflows/" + name,
            # Names, never values, and read out of the file rather than a table: when a
            # lane starts needing a new secret, the heartbeat notices without anyone
            # remembering to update a list. GITHUB_TOKEN belongs to Actions itself and
            # is always present, so naming it would only teach the reader to skip.
            "secrets": _named(_REFERENCES.findall(text), drop="GITHUB_TOKEN"),
            "vars": _named(_VAR_REFERENCES.findall(text)),
            # Which label this lane files its own failure issues under, read from the
            # `gh issue create --label …` line in the same file. The advice below can
            # then say "open the lane's issue" instead of guessing from a table.
            "labels": _named(_ISSUE_LABEL.findall(text)),
            "ledgers": _named(_LEDGER_FILE.findall(text)),
        })
    return lanes


# ── the GitHub side ────────────────────────────────────────────────────────
class GitHub(object):
    """Thin, boring REST client: one endpoint, one token, no dependencies.

    `fixture` replays recorded JSON instead of the network, which is how the tests
    and `--fixture` runs exercise *this* code path rather than a mock of it.
    """

    def __init__(self, owner, repo, token=None, api=None, fixture=None, branch="main"):
        self.owner = owner
        self.repo = repo
        self.token = token
        self.api = (api or "https://api.github.com").rstrip("/")
        self.fixture = fixture
        self.branch = branch

    def _from_fixture(self, rel):
        candidate = os.path.join(self.fixture, rel.strip("/") + ".json")
        candidate = candidate.replace("/", os.sep)
        if not os.path.exists(candidate):
            # A fixture may also be a flat directory of `<name>.json` files keyed by
            # the last path segment — recorded pulls are usually saved that way.
            candidate = os.path.join(self.fixture, os.path.basename(rel.strip("/")) + ".json")
        try:
            with open(candidate, encoding="utf-8") as handle:
                return json.load(handle)
        except ValueError as exc:
            raise RuntimeError("fixture %s is not readable JSON (%s)" % (candidate, exc))
        except OSError as exc:
            raise RuntimeError("no fixture for %s (%s)" % (rel, exc.__class__.__name__))

    def contents(self, path, ref=None):
        """One file, as text, from one ref. `content` arrives base64-chunked."""
        body = self.get("/repos/%s/%s/contents/%s" % (self.owner, self.repo, path),
                        {"ref": ref} if ref else None)
        if not isinstance(body, dict) or not body.get("content"):
            raise RuntimeError("GitHub returned no file content for %s@%s" % (path, ref))
        return base64.b64decode(body["content"]).decode("utf-8", "replace")

    def get(self, path, params=None):
        rel = path.lstrip("/")
        if params:
            rel = "%s?%s" % (rel, urllib.parse.urlencode(params))
        if self.fixture:
            return self._from_fixture(path)
        if not self.token:
            raise RuntimeError("no token — set GITHUB_TOKEN (or GH_TOKEN) or pass --token")
        url = "%s/%s" % (self.api, path.lstrip("/"))
        if params:
            url = "%s?%s" % (url, urllib.parse.urlencode(params))
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer %s" % self.token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "docoga-automation-heartbeat",
        })
        payload = None
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                payload = response.read().decode("utf-8") or "{}"
        except urllib.error.HTTPError as exc:
            # Read before the generic transport error: the status code *is* the
            # diagnosis (403 = the token cannot see this repo, 404 = wrong owner/name,
            # 422 = a parameter GitHub dislikes), and flattening all three into "could
            # not reach GitHub" sends the reader to the network instead of the config.
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            raise RuntimeError("GitHub refused %s (HTTP %s): %s" % (path, exc.code, detail))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("could not reach GitHub for %s (%s)" % (path, exc.__class__.__name__))
        try:
            return json.loads(payload)
        except ValueError as exc:
            raise RuntimeError("GitHub answered %s with something that is not JSON (%s)"
                               % (path, exc.__class__.__name__))


def crons_from_text(text):
    """The `cron:` lines a workflow YAML declares — the same read discover_lanes does,
    against a string instead of a file, so a *different* revision can be asked."""
    try:
        doc = yaml.safe_load(text)
    except Exception:
        return None                      # not "no schedule": "I could not tell"
    if not isinstance(doc, dict):
        # An empty file or a scalar document parses fine and has no `on:` — which is
        # not the same fact as "a workflow that declares no schedule", and answering
        # [] here would excuse a broken lane instead of reporting it.
        return None
    on = doc.get("on") if isinstance(doc.get("on"), dict) else doc.get(True) or {}
    if not isinstance(on, dict):
        return None
    crons = []
    for entry in (on.get("schedule") or []):
        if isinstance(entry, dict) and entry.get("cron"):
            crons.append(str(entry["cron"]))
    return crons


def default_branch_crons(client, lanes, branch):
    """`path` → cron list on the default branch, for the lanes that have one here.

    Only worth the API calls when this checkout is not the default branch: a schedule
    that lives on an unmerged branch cannot be judged for silence at all, and the
    difference between "the lane is dead" and "the lane is not merged yet" is exactly
    the difference between an issue that is worth someone's morning and one that is
    noise. A file that cannot be read is left out of the map — unreadable never excuses.
    """
    out = {}
    for lane in lanes:
        if not lane.get("crons") or lane.get("error"):
            continue
        path = lane.get("path")
        try:
            found = crons_from_text(client.contents(path, branch))
        except RuntimeError:
            continue
        if found is not None:
            out[path] = found
    return out


def workflow_index(client):
    """`path` → {id, state, name}. By path, because names get reworded."""
    body = client.get("/repos/%s/%s/actions/workflows" % (client.owner, client.repo),
                      {"per_page": 100})
    out = {}
    for entry in body.get("workflows", []) if isinstance(body, dict) else []:
        out[entry.get("path")] = {"id": entry.get("id"), "state": entry.get("state"),
                                  "name": entry.get("name")}
    return out


# Since 17 Oct 2026 the lanes are rung on time by the DocOga clock (workers/clock), which
# arrives as `workflow_dispatch`, while GitHub's own `schedule` event is a late backstop.
# Both are "the cadence being kept", so a lane's recent runs are the union of the two.
CADENCE_EVENTS = ("schedule", "workflow_dispatch")


def recent_runs(client, workflow_id, branch, event="schedule", per_page=RUNS_PER_LANE):
    events = CADENCE_EVENTS if event == "schedule" else (event,)
    seen, raw = set(), []
    for name in events:
        body = client.get("/repos/%s/%s/actions/workflows/%s/runs" % (
            client.owner, client.repo, workflow_id),
            {"per_page": per_page, "event": name, "branch": branch})
        for run in body.get("workflow_runs", []) if isinstance(body, dict) else []:
            key = run.get("html_url") or run.get("id") or id(run)
            if key in seen:
                continue
            seen.add(key)
            raw.append(run)
    runs = []
    for run in raw:
        runs.append({
            "created_at": parse_stamp(run.get("created_at")),
            "updated_at": parse_stamp(run.get("updated_at")),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "url": run.get("html_url") or "",
            "branch": run.get("head_branch"),
            "event": run.get("event"),
            "title": run.get("display_title") or "",
        })
    runs.sort(key=lambda item: item["created_at"] or datetime.min.replace(tzinfo=timezone.utc),
              reverse=True)
    return runs


def file_age(client, path, ref=None):
    """When the lane's own file last changed — the only fair clock for `never ran`."""
    params = {"path": path, "per_page": 1}
    if ref:
        params["sha"] = ref
    try:
        commits = client.get("/repos/%s/%s/commits" % (client.owner, client.repo), params)
    except RuntimeError:
        return None
    if isinstance(commits, list) and commits:
        commit = commits[0].get("commit") or {}
        stamp = (commit.get("committer") or {}).get("date") or (commit.get("author") or {}).get("date")
        return parse_stamp(stamp)
    return None


# ── the verdict ─────────────────────────────────────────────────────────────
def ledger_freshness(client, path, ref, now):
    """What one ledger file says about the lane's last publish, as of `ref`.

    Four states, because collapsing them is how a monitor lies:

      * `ok`         — parsed, and the newest entry has a usable timestamp;
      * `empty`      — parsed, nothing usable in it: the file exists, no publish inside;
      * `absent`     — no file on the default branch: the lane has never recorded a post;
      * `unreadable` — it is there and does not parse, which is *not* "nothing published".

    A ledger is the lane's own evidence, written at the moment the platform accepted the
    post. Run history is only the CI's memory, and the two disagree in both directions.
    """
    try:
        body = json.loads(client.contents(path, ref))
    except RuntimeError:
        return {"path": path, "state": "absent", "newest": None}
    except ValueError as exc:
        return {"path": path, "state": "unreadable", "newest": None,
                "detail": type(exc).__name__}
    entries = body.get("entries") if isinstance(body, dict) else body
    if not isinstance(entries, list):
        return {"path": path, "state": "unreadable", "newest": None,
                "detail": "the ledger is not a list"}
    newest, newest_stamp, url = None, "", ""
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        stamp = entry.get("recorded_at") or entry.get("date") or ""
        moment = parse_stamp(stamp)
        if moment is None:
            continue
        if newest is None or moment > newest:
            newest, newest_stamp, url = moment, str(stamp), entry.get("url") or ""
    return {"path": path, "state": "ok" if newest else "empty", "newest": newest,
            "newest_stamp": newest_stamp, "url": url, "entries": len(entries)}


def apply_publish_evidence(verdict, ledgers, now):
    """Cross-check the CI story against the lane's own record of publishing.

    The two directions are deliberately not symmetric:

      * CI is silent and the ledger is fresh -> still a failure, because the schedule
        really is broken, but the note says so. "The lane died" and "nobody received
        anything" are different sentences, and on 13 Oct 2026 this repo's Telegram lane
        is the case where only one of them was true.
      * CI is green and the ledger is stale -> *that* failure is its own kind, and the
        scarier one: a run that reports success without recording a publish is green, so
        nothing else in the system looks at it.

    An absent or unreadable ledger changes nothing. Missing evidence is not evidence of a
    missing publish.
    """
    verdict["publish_evidence"] = ", ".join(
        "%s=%s" % (item["path"], item["state"]) for item in (ledgers or [])) or "no ledger declared"
    if ledgers and not verdict.get("ledgers"):
        # Whatever assembled this verdict, the renderer is told what was actually read.
        # A lane's declared ledger and the file the monitor fetched are the same fact,
        # and the summary line must not silently disappear when one of the two paths is
        # built by hand (tests, or a future caller).
        verdict["ledgers"] = [item["path"] for item in ledgers]
    known = [item for item in (ledgers or []) if item.get("state") == "ok" and item.get("newest")]
    if known:
        newest = max(item["newest"] for item in known)
        where = [item for item in known if item["newest"] == newest][0]
        verdict["last_publish"] = iso(newest)
        verdict["publish_age"] = int((now - newest).total_seconds())
        deadline = verdict.get("silent_after")
        if verdict["status"] == "ok" and deadline and verdict["publish_age"] > deadline:
            verdict["status"] = "fail"
            verdict["kind"] = "green-but-quiet"
            verdict["reason"] = (
                "the runs go green, but %s has nothing newer than %s (%s old, past the %s "
                "silence deadline) - a run that succeeds without recording a publish"
                % ("`%s`" % where["path"], verdict["last_publish"],
                   human_duration(verdict["publish_age"]), human_duration(deadline)))
        elif verdict["status"] in ("fail", "unknown", "warn") and deadline \
                and verdict["publish_age"] <= deadline:
            verdict["publish_note"] = (
                "%s records a publish %s ago%s, so the schedule is broken while readers are "
                "still being served: fix the cron, but do not write \"nothing was published\""
                % ("`%s`" % where["path"], human_duration(verdict["publish_age"]),
                   " at " + where["url"] if where.get("url") else ""))
    elif any(item.get("state") == "absent" for item in (ledgers or [])):
        verdict["publish_note"] = (
            "no publish evidence either way: %s is not on the default branch yet"
            % ", ".join("`%s`" % item["path"] for item in ledgers if item.get("state") == "absent"))
    elif any(item.get("state") == "unreadable" for item in (ledgers or [])):
        verdict["publish_note"] = (
            "the ledger exists and does not parse, which is not \"nothing published\" - the "
            "ledger tool backs such a file up and starts fresh")
    return verdict


def judge(lane, info, runs, lane_since, now, grace=DEFAULT_LANE_GRACE,
          jitter=SCHEDULE_JITTER, misses=MISSES_BEFORE_SILENT):
    """One lane → one verdict. Returns a dict; `status` ∈ ok|warn|fail|manual|unknown."""
    verdict = {
        "lane": lane.get("name") or lane.get("file"),
        "file": lane.get("file"),
        "crons": list(lane.get("crons") or []),
        "status": "ok",
        "reason": "",
        "expected_gap": None,
        "last_run": iso(runs[0]["created_at"]) if runs else "",
        "last_conclusion": (runs[0].get("conclusion") or runs[0].get("status")) if runs else "",
        "last_url": runs[0].get("url") if runs else "",
        "streak": 0,
        "silent_after": None,
        "state": (info or {}).get("state"),
        "kind": "ok",
        "secrets": list(lane.get("secrets") or []),
        "vars": list(lane.get("vars") or []),
        "labels": list(lane.get("labels") or []),
        "ledgers": list(lane.get("ledgers") or []),
        "last_publish": "",
        "publish_age": None,
        "publish_evidence": "",
        "publish_note": "",
    }
    if lane.get("error"):
        # Before the "no schedule" answer: a file this tool could not parse also has
        # no parsed schedule, and reporting that as `manual` would hide a broken
        # workflow from the one thing whose job is to notice broken workflows.
        verdict["status"] = "unknown"
        verdict["kind"] = "unreadable"
        verdict["reason"] = lane["error"]
        return verdict
    if not lane.get("scheduled"):
        verdict["status"] = "manual"
        verdict["kind"] = "manual"
        verdict["reason"] = ("no `schedule:` — a dispatch-only tool, so a quiet run "
                             "history is expected, not a finding")
        return verdict

    gap, detail = expected_gap(lane["crons"], start=now - timedelta(days=CRON_WINDOW_DAYS))
    if gap is None:
        verdict["status"] = "unknown"
        verdict["kind"] = "unreadable-cadence"
        verdict["reason"] = detail
        return verdict
    verdict["expected_gap"] = gap
    verdict["silent_after"] = silence_deadline(gap, jitter.total_seconds(), misses)
    verdict["jitter_used"] = min(int(jitter.total_seconds()), max(int(gap), 3600))
    deadline = now - timedelta(seconds=verdict["silent_after"])

    state = (info or {}).get("state")
    if info is None:
        # Never registered with Actions at all.
        if lane_since and (now - lane_since) > grace:
            verdict["status"] = "fail"
            verdict["kind"] = "never-run"
            verdict["reason"] = ("GitHub has never seen this workflow, although it has had a "
                                 "`schedule:` for %s — it has never run"
                                 % human_duration((now - lane_since).total_seconds()))
        else:
            verdict["status"] = "warn"
            verdict["kind"] = "unregistered"
            verdict["reason"] = "not registered with Actions yet (lane is new)"
        return verdict
    if state and state != "active":
        verdict["status"] = "fail"
        verdict["kind"] = "disabled"
        verdict["reason"] = ("workflow state is `%s` — GitHub stops running it and files no "
                             "failure anywhere. Re-enable it, or delete the lane" % state)
        return verdict

    completed = [run for run in runs if run.get("status") == "completed"]
    for run in completed:
        if run.get("conclusion") != "success":
            verdict["streak"] += 1
        else:
            break

    successes = [run for run in completed if run.get("conclusion") == "success"]
    newest = successes[0] if successes else None
    last = completed[0] if completed else None

    if last is None:
        age = (now - lane_since) if lane_since else None
        if age is not None and age <= grace:
            verdict["status"] = "warn"
            verdict["kind"] = "too-new"
            verdict["reason"] = ("no completed scheduled run yet, and the lane is only %s old — "
                                 "its first fire may not have happened" % human_duration(max(0, age.total_seconds())))
        else:
            verdict["status"] = "fail"
            verdict["kind"] = "never-run"
            verdict["reason"] = ("it has never run: a `cron:` since %s with no completed "
                                 "scheduled run to show for it" % (iso(lane_since) or "forever"))
        return verdict

    if newest is None:
        verdict["status"] = "fail"
        verdict["kind"] = "never-succeeded"
        verdict["reason"] = ("%d scheduled run(s), not one successful — this lane has never "
                             "published anything, whatever its README says" % len(completed))
        verdict["last_run"] = iso(last.get("created_at"))
        verdict["last_conclusion"] = last.get("conclusion")
        verdict["last_url"] = last.get("url") or ""
        return verdict

    verdict["last_successful"] = iso(newest.get("created_at"))
    verdict["last_url"] = newest.get("url") or last.get("url") or ""
    age_since_success = now - (newest.get("created_at") or now)
    if age_since_success > timedelta(seconds=verdict["silent_after"]):
        verdict["status"] = "fail"
        verdict["kind"] = "silent"
        verdict["reason"] = ("nothing has succeeded in %s; its cadence says the deadline was %s "
                             "(gap %s × %d, + %s of scheduler slack)"
                             % (human_duration(age_since_success.total_seconds()),
                                iso(newest.get("created_at") + timedelta(seconds=verdict["silent_after"])),
                                human_duration(gap), misses, human_duration(verdict["jitter_used"])))
        return verdict

    if verdict["streak"] >= 2:
        verdict["status"] = "warn"
        verdict["kind"] = "streak"
        verdict["reason"] = ("%d consecutive failures, still inside the silence deadline — the "
                             "lane's own issue should already be open" % verdict["streak"])
    elif verdict["streak"] == 1:
        verdict["status"] = "ok"
        verdict["reason"] = "last scheduled run failed (%s) — inside one cycle, so not yet a finding" % (
            last.get("conclusion") or "?")
    else:
        verdict["reason"] = "ran %s and succeeded" % human_duration(age_since_success.total_seconds())
    return verdict


def build_verdicts(lanes, index, runs_by_id, since_by_path, now, options):
    out = []
    for lane in lanes:
        info = index.get(lane.get("path"))
        runs = runs_by_id.get((info or {}).get("id"), []) if info else []
        on_default_branch = since_by_path.get(lane.get("path")) is not None
        verdict = judge(lane, info, runs, since_by_path.get(lane.get("path")), now,
                        grace=options.get("grace", DEFAULT_LANE_GRACE),
                        jitter=options.get("jitter", SCHEDULE_JITTER),
                        misses=options.get("misses", MISSES_BEFORE_SILENT))
        # Runs are counted on the default branch; the schedule being *judged* comes
        # from this checkout. On a branch that has not merged, "never ran" is a
        # statement about the merge, not about the lane — and a monitor that calls a
        # pending merge a failure gets muted within a week. Downgrade, and say why.
        apply_publish_evidence(verdict, (options.get("ledger_data") or {}).get(lane.get("path")),
                               now)
        judged = options.get("ref")
        pending_here = bool(judged) and judged != options.get("branch")
        silence_claims = ("never-run", "silent", "streak")
        if pending_here and verdict["status"] == "fail" and verdict["kind"] in silence_claims:
            known = options.get("default_crons") or {}
            why = ""
            if lane.get("path") in known:
                if not known[lane["path"]]:
                    why = "no `schedule:` on `%s`" % options.get("branch")
            elif not on_default_branch:
                why = "the file is not on `%s` yet" % options.get("branch")
            if why:
                # Nothing on the default branch could have run, so "it is silent" is a
                # statement about the merge queue, not about the lane.
                verdict["status"] = "warn"
                verdict["pending_merge"] = True
                verdict["reason"] += (" — but this schedule only exists on `%s`, and GitHub runs "
                                      "schedules from `%s` (%s): merge it to make the lane live"
                                      % (judged, options.get("branch"), why))
        out.append(verdict)
    order = {"fail": 0, "unknown": 1, "warn": 2, "ok": 3, "manual": 4}
    out.sort(key=lambda item: (order.get(item["status"], 5), str(item["lane"])))
    return out


def signature(verdicts):
    """A short hash of *which* lanes are in *which* state.

    Deliberately built from status only — not from timestamps or reasons — so a
    lane that stays broken the same way is a repeat (green run, one comment), while
    a second lane joining it, or one healing, is new and gets the email.
    """
    parts = sorted("%s:%s" % (item["file"], item["status"]) for item in verdicts
                   if item["status"] in ("fail", "unknown", "warn") and not item.get("pending_merge"))
    digest = hashlib.sha256(("|".join(parts) or "healthy").encode("utf-8")).hexdigest()
    return digest[:12]


def clock_line(runs_by_id, now, window=timedelta(hours=24)):
    """One line on the DocOga clock (workers/clock): how many lanes it rang in the last
    24 h versus how many GitHub's own scheduler delivered. `CLOCK=on-duty` once any
    dispatch arrived; `CLOCK=idle` means the token is missing or dead (docs/CLOCK.md),
    and every slot is riding GitHub's late, best-effort cron again."""
    rung = late = 0
    floor = now - window
    for runs in runs_by_id.values():
        for run in runs:
            created = run.get("created_at")
            if not created or created < floor:
                continue
            if run.get("event") == "workflow_dispatch":
                rung += 1
            elif run.get("event") == "schedule":
                late += 1
    state = "on-duty" if rung else "idle"
    return ("CLOCK=%s dispatched_24h=%d github_cron_24h=%d — %s" % (
        state, rung, late,
        "the clock is ringing the lanes on time" if rung else
        "no clock dispatch in 24 h: GH_DISPATCH_TOKEN missing or dead (docs/CLOCK.md); "
        "GitHub's own cron is the only clock"))


def markdown(verdicts, now=None, repo=None, branch_hint=None):
    lines = ["", "## Automation heartbeat — %s" % (iso(now) if now else ""), ""]
    if repo:
        lines.append("Repo: `%s` · rules: `tools/automation_heartbeat.py`" % repo)
        lines.append("")
    glyph = {"ok": "✅", "warn": "⚠️", "fail": "❌", "unknown": "❓", "manual": "🔧"}
    # Manual-only workflows are listed as a count, not as ten rows. A table where
    # nothing is wrong is a table nobody reads, and the ten 🔧 lines are always
    # nothing-wrong — they would bury the one row that matters.
    judged_rows = [item for item in verdicts if item.get("crons")]
    manual = [item for item in verdicts if not item.get("crons")]
    lines.append("| lane | cadence | last success | verdict |")
    lines.append("|---|---|---|---|")
    for item in judged_rows:
        cadence = ", ".join("`%s`" % c for c in item.get("crons") or []) or "— manual"
        if item.get("expected_gap"):
            cadence += " (≤ %s)" % human_duration(item["expected_gap"])
        last = item.get("last_successful") or item.get("last_run") or "never"
        if last != "never" and item.get("last_conclusion"):
            last = "%s · %s" % (last, item["last_conclusion"])
        # When the lane's own ledger is newer than the last green run, that is the
        # number the owner needs in the table: it is the difference between "nothing has
        # been published for 9 days" and "the cron has been broken for 9 days".
        publish = item.get("last_publish") or ""
        # Compare the moments, not the strings: a ledger timestamp is +01:00 and a run
        # timestamp is Z, and "…19:43:59+00:00" sorts before "…10:18:00+01:00" as text
        # while being later as time.
        if publish:
            publish_at, run_at = parse_stamp(publish), parse_stamp(item.get("last_run") or "")
            if run_at is None or publish_at > run_at:
                last = "%s · ledger" % publish
        lines.append("| %s %s | %s | %s | %s |" % (
            glyph.get(item["status"], "•"), item["lane"], cadence, last,
            (item.get("reason") or "").replace("|", "/")))
    if manual:
        lines.append("")
        lines.append("_%d more workflow(s) have no `schedule:` (dispatch/deploy/CI) and are not "
                     "judged: %s_" % (len(manual), ", ".join("`%s`" % m["file"] for m in manual)))
    failures = [item for item in verdicts if item["status"] in ("fail", "unknown")]
    # Only the notes that *contradict* the table get a blockquote: three lanes saying
    # "no ledger yet" in three near-identical sentences buries the one line that says
    # "the schedule is broken and the channel is still being served". The rest is
    # counted, once.
    disagreed = [item["publish_note"] for item in verdicts
                 if item.get("publish_note") and "records a publish" in item["publish_note"]]
    if disagreed:
        lines.append("")
        lines.extend("> %s" % note for note in dict.fromkeys(disagreed))
    declared = [item for item in verdicts if item.get("ledgers")]
    if declared:
        quiet = [item for item in declared if "not on the default branch yet" in item.get("publish_note", "")]
        lines.append("")
        if quiet:
            lines.append("_%d of %d lane(s) declare a publish ledger; %s have no file on `%s` "
                         "yet, so their rows above are run-history only, not proof of silence._"
                         % (len(declared), len(judged_rows) or len(declared),
                            "all of them" if len(quiet) == len(declared) else "%d of them" % len(quiet),
                            (branch_hint or "main")))
        else:
            lines.append("_%d lane(s) keep a publish ledger; the table's last column and the "
                         "· ledger marker above are read from it._" % len(declared))
    lines.append("")
    if failures:
        lines.append("**%d lane(s) need a decision.** Each row above says which and why; the "
                     "fix is a setting, not a code change, in every case this tool can name." % len(failures))
    else:
        warns = [item for item in verdicts if item["status"] == "warn"]
        lines.append("No dead lanes.%s" % (" %d warning(s) above." % len(warns) if warns else ""))
    return "\n".join(lines) + "\n"


def triage(verdicts, ref="main"):
    """Per-lane "do this", ordered by the tool's own confidence in it."""
    options_hint = ref or "main"
    out = []
    for item in verdicts:
        if item["status"] not in ("fail", "unknown"):
            continue
        lines = ["### %s (`%s`)" % (item["lane"], item.get("file")), "",
                 "Verdict: %s" % item.get("reason"), ""]
        lines.append("```")
        lines.append("gh run list --workflow '%s' --limit 5" % item["lane"])
        lines.append("gh workflow view .github/workflows/%s   # or open the file" % item.get("file"))
        lines.append("```")
        lines.append("")
        named = ["`%s`" % secret for secret in item.get("secrets") or []]
        knobs = ["`vars.%s`" % knob for knob in item.get("vars") or []]
        if named or knobs:
            # The most common shape of "the job runs and nothing appears" is a secret
            # that is unset on this repo or scoped to the wrong environment, so the
            # issue names the keys to look at instead of saying "check the config".
            lines.append("- Reads %s. An unset or wrong-scoped one is the usual reason a run "
                         "goes green while nothing is published. `gh secret list` / "
                         "`gh variable list` show names only; when in doubt, re-set it."
                         % ", ".join(named + knobs))
        kind = item.get("kind")
        if item.get("publish_note"):
            lines.append("- %s" % item["publish_note"])
        if kind == "green-but-quiet":
            lines.append("- The run is green and the ledger has nothing new, so the gap is "
                         "between \"the job finished\" and \"the post exists\": read the "
                         "ledger step first, because a failed `git push` there is a warning "
                         "on purpose, and a lost warning is exactly this shape.")
        if kind == "never-run":
            lines.append("- A `schedule:` that has never fired usually means the workflow is not on "
                         "the **default branch** yet — GitHub runs scheduled workflows only from there. "
                         "Merge it, or dispatch it once from the branch to test.")
        elif kind == "disabled":
            lines.append("- GitHub disabled it. Re-enable: Actions → this workflow → *Enable workflow*. "
                         "`disabled_inactivity` after 60 days of no runs is GitHub being tidy, not wrong.")
        elif kind == "never-succeeded":
            label = (item.get("labels") or [None])[0]
            where = ("- Its failure issues are labelled `%s`, so `gh issue list --label %s "
                     "--state open` is where the preflight's own words already are."
                     % (label, label)) if label else \
                ("- This workflow files no failure issue of its own, so the run log is the "
                 "only record: `gh run view --log` on the newest one.")
            lines.append("- The lane has run and never worked, which is different from "
                         "\"stopped working\": there is no known-good run to compare against.\n"
                         + where)
        else:
            lines.append("- It succeeded once and then stopped arriving in cadence. Either the cron "
                         "changed, the workflow was disabled, or every run since has failed — the "
                         "commands above say which in one line.")
        lines.append("- Then prove it again by hand (a dry run first, if the lane has one): "
                     "`gh workflow run %s --ref %s`" % (item.get("file"), options_hint))
        out.append("\n".join(lines))
    return "\n\n---\n\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report which DocOga automation lanes are silent")
    parser.add_argument("--repo", default=os.environ.get("HEARTBEAT_REPO", ""),
                        help="owner/name (default: $HEARTBEAT_REPO, else $GITHUB_REPOSITORY)")
    parser.add_argument("--branch", default=os.environ.get("HEARTBEAT_BRANCH", "main"),
                        help="default branch: schedules run from here, so runs are counted here")
    parser.add_argument("--ref", default=os.environ.get("GITHUB_REF_NAME", ""),
                        help="the branch this checkout came from ($GITHUB_REF_NAME in Actions)")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
                        help="read token; defaults to $GITHUB_TOKEN/$GH_TOKEN")
    parser.add_argument("--api", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    parser.add_argument("--workflows", default=WORKFLOWS_DIR, help="dir of workflow YAML to read")
    parser.add_argument("--now", help="override 'now' (ISO), for deterministic runs and tests")
    parser.add_argument("--grace-days", type=float, default=DEFAULT_LANE_GRACE.days,
                        help="how old a new lane may be before 'never ran' is a finding")
    parser.add_argument("--jitter-hours", type=float,
                        default=SCHEDULE_JITTER.total_seconds() / 3600.0,
                        help="how late GitHub's scheduler may be before a run counts as missing")
    parser.add_argument("--misses", type=int, default=MISSES_BEFORE_SILENT,
                        help="how many times a cadence may be missed before it is 'silent'")
    parser.add_argument("--fixture", help="replay JSON from a directory instead of the network")
    parser.add_argument("--out", help="write the verdicts as JSON here")
    parser.add_argument("--markdown", help="write the summary table here (Actions: $GITHUB_STEP_SUMMARY)")
    parser.add_argument("--triage", help="write the per-lane fix notes here (Actions: append to the issue body)")
    parser.add_argument("--dry-run", action="store_true", help="print everything, write nothing")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    repo = args.repo or os.environ.get("GITHUB_REPOSITORY", "")
    if not repo or "/" not in repo:
        print("❌ --repo owner/name is required (or set GITHUB_REPOSITORY)")
        return 3
    owner, name = repo.split("/", 1)
    now = parse_stamp(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        print("❌ --now is not ISO-8601: %r" % args.now)
        return 3
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    lanes = discover_lanes(args.workflows)
    if not lanes:
        print("❌ no workflow files in %s — refusing to report a healthy repo I cannot see" % args.workflows)
        return 3

    client = GitHub(owner, name, token=args.token, api=args.api, fixture=args.fixture,
                    branch=args.branch)
    since_ref = args.ref or args.branch
    options = {"branch": args.branch, "ref": since_ref,
               "grace": timedelta(days=max(0.0, args.grace_days)),
               "jitter": timedelta(hours=max(0.0, args.jitter_hours)),
               "misses": max(1, args.misses), "default_crons": {}}
    try:
        index = workflow_index(client)
        runs_by_id, since_by_path = {}, {}
        for lane in lanes:
            info = index.get(lane.get("path"))
            if info and info.get("id") is not None:
                runs_by_id[info["id"]] = recent_runs(client, info["id"], args.branch)
            since_by_path[lane.get("path")] = file_age(client, lane.get("path"))
        # Publish evidence comes from the default branch, always: a ledger on a branch
        # proves nobody outside CI published, which is the opposite of what this is for.
        ledger_data = {}
        for lane in lanes:
            wanted = lane.get("ledgers") or []
            if wanted and not lane.get("error"):
                ledger_data[lane.get("path")] = [
                    ledger_freshness(client, "logs/" + name, args.branch, now)
                    for name in wanted]
        options["ledger_data"] = ledger_data
        if args.ref and args.ref != args.branch:
            # Assigned into `options`, not rebound locally: `options` already holds the
            # empty dict, so `default_crons = …` here would look correct and hand
            # build_verdicts an empty map — i.e. every branch-only schedule judged as a
            # real failure, in silence.
            options["default_crons"] = default_branch_crons(client, lanes, args.branch)
    except RuntimeError as exc:
        print("❌ the heartbeat could not look: %s" % exc)
        print("   Reporting 'all clear' without data would be the worst thing this tool can do.")
        return 3

    verdicts = build_verdicts(lanes, index, runs_by_id, since_by_path, now, options)
    sig = signature(verdicts)
    fails = [item for item in verdicts if item["status"] in ("fail", "unknown")]

    print(markdown(verdicts, now=now, repo=repo, branch_hint=args.branch))
    print(clock_line(runs_by_id, now))
    for item in verdicts:
        if args.verbose or item["status"] in ("fail", "unknown", "warn"):
            print("%-4s %-38s %s" % (item["status"].upper(), str(item["lane"])[:38], item["reason"]))
    print("HEARTBEAT_SIGNATURE=%s" % sig)
    print("HEARTBEAT_STATE=%s" % ("degraded" if fails else "healthy"))
    print("HEARTBEAT_SILENT=%s" % (",".join(str(item["file"]) for item in fails) or "-"))
    print("HEARTBEAT_LANES=%d scheduled, %d manual-only" % (
        len([v for v in verdicts if v["crons"]]), len([v for v in verdicts if not v["crons"]])))

    if not args.dry_run:
        if args.out:
            with open(args.out, "w", encoding="utf-8") as handle:
                json.dump({"generated_at": iso(now), "repo": repo,
                           "signature": sig, "branch": args.branch, "ref": since_ref,
                           "options": {"grace_days": args.grace_days,
                                                          "jitter_hours": args.jitter_hours,
                                                          "misses": args.misses},
                           "verdicts": verdicts}, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
        if args.markdown:
            with open(args.markdown, "a", encoding="utf-8") as handle:
                handle.write(markdown(verdicts, now=now, repo=repo, branch_hint=args.branch))
        if args.triage and fails:
            with open(args.triage, "w", encoding="utf-8") as handle:
                handle.write(triage(verdicts, ref=args.branch) + "\n")

    if fails:
        print("::error title=Automation heartbeat::%d lane(s) silent or disabled — signature %s" % (
            len(fails), sig))
        return 1
    if any(item["status"] == "warn" for item in verdicts):
        print("::warning title=Automation heartbeat::warnings only; no lane is past its silence deadline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
