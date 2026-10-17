#!/usr/bin/env python3
"""The DocOga clock — the one schedule table, read from the workflows themselves.

Why this exists (17 Oct 2026)
-----------------------------
GitHub's `schedule:` trigger stopped being a clock for private repositories on
26 Aug 2026 (community discussions #207346, #207370, #201472): a cron that should
fire three times a day creates 0–2 runs, hours late, or none at all —
`created_at == run_started_at`, so it is the event that never arrives, not a
runner that is busy. Measured on this repo, 13–17 Oct: Threads (3 crons/day) ran
once a day; Instagram (3/day) once; Brain replies (3/day) once; the Shorts lane
(Mon–Fri) once in four weekdays; the YouTube boost sweep never; and the 09:00 WAT
Telegram post landed between 13:00 and 16:40 WAT. Every "best time to post" in
this repo was being decided by a queue in another time zone.

`workflow_dispatch`, on the other hand, starts within seconds, every time. So a
Cloudflare Worker (`workers/clock/`, Workers Free: one Cron Trigger of the five
the plan allows, 10 ms of CPU per tick, no charge) wakes every five minutes and
dispatches whichever lanes were due in the last five minutes, through
`POST /repos/{owner}/{repo}/actions/workflows/{file}/dispatches`. The lanes keep
their `schedule:` blocks — GitHub's late fire is a backstop, and each lane's
duplicate guard makes a second arrival harmless.

This module is the single source of truth the worker ships with:

* `lanes()` reads every `.github/workflows/*.yml` that has a `schedule:` — the
  same discovery `tools/automation_heartbeat.py` does, so a cron edited in a
  workflow is a cron the clock dispatches, with no second table to forget.
* `inputs_for()` names the dispatch inputs a lane needs to behave exactly as its
  scheduled run would (Threads: the slot the cron stands for; Instagram: the
  `clock` flag that puts its slot gate into scheduled mode).
* `emit()` writes `workers/clock/schedule.json`; `due()` is the Python mirror of
  the worker's matcher, so tests can pin both to the same answers.

CLI:  python3 tools/clock_schedule.py emit            # rewrite workers/clock/schedule.json
      python3 tools/clock_schedule.py today [--day D] # what the clock dispatches that day (WAT)
      python3 tools/clock_schedule.py check           # exit 1 if schedule.json is stale
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SCHEDULE_JSON = ROOT / "workers" / "clock" / "schedule.json"
REF = "main"
TICK_MINUTES = 5
LAGOS = dt.timezone(dt.timedelta(hours=1), "WAT")

# Workflows with a `schedule:` the clock must NOT dispatch. Empty on purpose: a lane
# that is scheduled is a lane that is owed its slot — even deploy-clock.yml, whose
# daily run re-applies the dispatch token (harmless when the clock rings it).
SKIP: set[str] = set()


def _yaml():
    try:
        import yaml  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover — PyYAML is a repo requirement
        raise SystemExit("PyYAML is required: pip install pyyaml") from exc
    return yaml


def lanes(workflows_dir: Path = WORKFLOWS) -> list[dict]:
    """Every scheduled workflow: {file, name, crons, dispatch, inputs(declared)}."""
    yaml = _yaml()
    out = []
    for path in sorted(workflows_dir.glob("*.yml")):
        if path.name in SKIP:
            continue
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 — a broken file is the heartbeat's finding, not ours
            continue
        on = doc.get(True) if True in doc else doc.get("on")
        if not isinstance(on, dict) or not on.get("schedule"):
            continue
        crons = [str(entry.get("cron", "")).strip() for entry in on["schedule"] if isinstance(entry, dict)]
        crons = [c for c in crons if c]
        dispatch = on.get("workflow_dispatch")
        declared = sorted((dispatch or {}).get("inputs", {}).keys()) if isinstance(dispatch, dict) else []
        out.append({
            "file": path.name,
            "name": str(doc.get("name") or path.stem),
            "crons": crons,
            "dispatch": "workflow_dispatch" in on,
            "declared_inputs": declared,
        })
    return out


# ---------------------------------------------------------------- inputs per lane

def threads_slot(hour_utc: int) -> str:
    """The slot a Threads cron stands for — the same bands threads_autopost.yml uses
    when `slot: auto`: before 09:00 UTC morning, from 15:00 UTC evening, lunch between."""
    if hour_utc >= 15:
        return "evening"
    if hour_utc < 9:
        return "morning"
    return "lunch"


def inputs_for(file: str, cron: str, declared: list[str] | None = None) -> dict:
    """Dispatch inputs that make the run behave exactly like the scheduled one.
    Only inputs the workflow declares are sent — GitHub answers 422 to an unknown
    input, and a 422 is a missed post."""
    minute, hour = cron.split()[:2]
    inputs: dict[str, str] = {}
    if file == "threads_autopost.yml":
        inputs["slot"] = threads_slot(int(hour)) if hour.isdigit() else "auto"
    elif file == "instagram_autopost.yml":
        inputs["clock"] = "true"
    if declared is not None:
        inputs = {k: v for k, v in inputs.items() if k in declared}
    return inputs


# ---------------------------------------------------------------- the table

def entries(workflows_dir: Path = WORKFLOWS) -> list[dict]:
    """One row per (workflow, cron) — what the worker iterates on every tick."""
    rows = []
    for lane in lanes(workflows_dir):
        if not lane["dispatch"]:
            continue                       # nothing to dispatch; the heartbeat will say so
        for cron in lane["crons"]:
            rows.append({
                "workflow": lane["file"],
                "name": lane["name"],
                "cron": cron,
                "inputs": inputs_for(lane["file"], cron, lane["declared_inputs"]),
            })
    return rows


def table(workflows_dir: Path = WORKFLOWS) -> dict:
    return {
        "_": "Generated by tools/clock_schedule.py from .github/workflows/*.yml — do not edit by hand.",
        "ref": REF,
        "tick_minutes": TICK_MINUTES,
        "entries": entries(workflows_dir),
    }


def render(workflows_dir: Path = WORKFLOWS) -> str:
    return json.dumps(table(workflows_dir), indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- cron matching (mirror of index.js)

def _field(spec: str, lo: int, hi: int) -> set[int]:
    values: set[int] = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)
        if part == "*":
            start, end = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(part)
        for v in range(start, end + 1, step):
            if lo <= v <= hi:
                values.add(v)
    return values


def matches(cron: str, when: dt.datetime) -> bool:
    """Does this 5-field cron (UTC) fire at this minute? Day-of-month and day-of-week
    are ORed when both are restricted, as cron and GitHub do."""
    minute, hour, dom, month, dow = cron.split()
    when = when.astimezone(dt.timezone.utc)
    if when.minute not in _field(minute, 0, 59) or when.hour not in _field(hour, 0, 23):
        return False
    if when.month not in _field(month, 1, 12):
        return False
    dom_ok = when.day in _field(dom, 1, 31)
    dow_ok = ((when.weekday() + 1) % 7) in _field(dow, 0, 7) or (when.weekday() + 1) in _field(dow, 0, 7)
    if dom == "*" and dow == "*":
        return True
    if dom == "*":
        return dow_ok
    if dow == "*":
        return dom_ok
    return dom_ok or dow_ok


def due(rows: list[dict], tick: dt.datetime, tick_minutes: int = TICK_MINUTES) -> list[dict]:
    """Rows whose cron fires in the window (tick - tick_minutes, tick] — the same
    minutes the worker scans. Disjoint windows ⇒ every slot is dispatched exactly once."""
    tick = tick.astimezone(dt.timezone.utc).replace(second=0, microsecond=0)
    out = []
    for row in rows:
        for back in range(tick_minutes):
            if matches(row["cron"], tick - dt.timedelta(minutes=back)):
                out.append(dict(row, fires_at=(tick - dt.timedelta(minutes=back)).isoformat()))
                break
    return out


def day_plan(rows: list[dict], day: dt.date) -> list[tuple[dt.datetime, dict]]:
    """Every dispatch of a Lagos day, in order — for `today` and for the docs."""
    start = dt.datetime.combine(day, dt.time(0, 0), tzinfo=LAGOS)
    plan = []
    for i in range(24 * 60):
        minute = start + dt.timedelta(minutes=i)
        for row in rows:
            if matches(row["cron"], minute):
                plan.append((minute, row))
    return plan


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("emit", help="rewrite workers/clock/schedule.json")
    sub.add_parser("check", help="exit 1 if workers/clock/schedule.json is stale")
    today = sub.add_parser("today", help="list the day's dispatches in Lagos time")
    today.add_argument("--day", default="")
    a = ap.parse_args(argv)

    if a.cmd == "emit":
        SCHEDULE_JSON.parent.mkdir(parents=True, exist_ok=True)
        SCHEDULE_JSON.write_text(render(), encoding="utf-8")
        print("CLOCK_SCHEDULE=%s entries=%d" % (SCHEDULE_JSON.relative_to(ROOT), len(entries())))
        return 0
    if a.cmd == "check":
        current = SCHEDULE_JSON.read_text(encoding="utf-8") if SCHEDULE_JSON.exists() else ""
        if current == render():
            print("CLOCK_SCHEDULE=current")
            return 0
        print("CLOCK_SCHEDULE=stale — run: python3 tools/clock_schedule.py emit")
        return 1
    day = dt.date.fromisoformat(a.day) if a.day else dt.datetime.now(LAGOS).date()
    rows = entries()
    print("Clock plan for %s (%s), Lagos time:" % (day.isoformat(), day.strftime("%A")))
    for when, row in day_plan(rows, day):
        extra = (" " + json.dumps(row["inputs"])) if row["inputs"] else ""
        print("  %s  %-28s %s%s" % (when.strftime("%H:%M"), row["workflow"], row["name"][:40], extra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
