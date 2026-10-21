#!/usr/bin/env python3
"""
tools/publish_calendar.py — when a DocOga video goes public
============================================================

Owner, 21 Oct 2026: "I want the Shorts and Deep-Dive to go out scheduled to the time and date
it will be public." Both lanes already upload *private + publishAt* (YouTube flips the video
public itself at that instant; `tools/yt_publish.py`). What was missing is one place that says
**which** instant, so a Deep-Dive without an explicit date does not silently inherit "today at
7pm" — the Shorts' slot — and land on a Tuesday night next to a Short.

The calendar (Lagos time, UTC+1, no DST):

    Shorts      weekdays, 7:00pm   — render at 6:00pm, public at 7:00pm (unchanged since 17 Oct)
    Deep-Dive   Saturday, 7:00pm   — long-form watch time in Nigeria peaks weekend evenings; the
                                     week's Shorts trail it, so the episode is the week's close

`next_slot(kind, now)` returns the next calendar instant at least LEAD_MINUTES ahead (YouTube
rejects a publishAt in the past and needs processing time) — and, for Deep-Dives, not a
Saturday that already has an episode scheduled (both YouTube ledgers are read), so two
episodes written in one week take two Saturdays. `episode.json → youtube.publish_at`
still wins when an episode names its own date; this is only the default.

CLI:  python3 tools/publish_calendar.py deepdive        → 2026-10-25T19:00 (WAT, naive ISO)
      python3 tools/publish_calendar.py shorts
Machine line on stdout only; nothing else is printed, so a workflow can `$(…)` it.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAGOS = timezone(timedelta(hours=1))
SLOT_HOUR = 19          # 7:00pm WAT — the hour both lanes publish
LEAD_MINUTES = 10       # YouTube wants the instant in the future, with processing room
SATURDAY = 5            # datetime.weekday()

KINDS = ("shorts", "deepdive")


def _now(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(LAGOS)


def taken_deepdive_days(root=None):
    """Lagos dates ('YYYY-MM-DD') on which a Deep-Dive is already set to go public — read from
    the long-form ledger (`publish_at` of a scheduled upload) and the manage ledger (`schedule`
    lines applied by tools/yt_manage.py). Two episodes must never share a Saturday: the second
    would bury the first, and the week after would be empty."""
    root = Path(root) if root else ROOT
    days = set()
    try:
        for row in json.loads((root / "logs" / "youtube_longform.json").read_text(encoding="utf-8")):
            when = _parse(row.get("publish_at")) if isinstance(row, dict) else None
            if when:
                days.add(when.astimezone(LAGOS).strftime("%Y-%m-%d"))
    except (OSError, ValueError):
        pass
    try:
        for row in json.loads((root / "logs" / "youtube_manage.json").read_text(encoding="utf-8")).get("done", []):
            result = str(row.get("result") or "")
            when = _parse(result.split(" ", 1)[1]) if result.startswith("scheduled ") else None
            if when:
                days.add(when.astimezone(LAGOS).strftime("%Y-%m-%d"))
    except (OSError, ValueError, AttributeError):
        pass
    return days


def _parse(text):
    text = str(text or "").strip()
    if not text:
        return None
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=LAGOS)


def next_slot(kind, now=None, taken=None):
    """The next publish instant for `kind`, as a Lagos-aware datetime. `taken` = Lagos dates
    already holding a video of this kind (default for Deep-Dives: both ledgers); those days
    are skipped, so a second episode in one week takes the Saturday after."""
    if kind not in KINDS:
        raise ValueError("kind must be one of %s, not %r" % (", ".join(KINDS), kind))
    if taken is None:
        taken = taken_deepdive_days() if kind == "deepdive" else set()
    now_l = _now(now)
    floor = now_l + timedelta(minutes=LEAD_MINUTES)
    day = now_l.replace(hour=SLOT_HOUR, minute=0, second=0, microsecond=0)
    for _ in range(0, 7 + 7 * (len(taken) + 1)):  # a free day always exists within that many
        ok_day = (day.weekday() < 5) if kind == "shorts" else (day.weekday() == SATURDAY)
        if ok_day and day >= floor and day.strftime("%Y-%m-%d") not in taken:
            return day
        day += timedelta(days=1)
    raise RuntimeError("no slot found — the calendar is broken")


def iso_wat(when):
    """'YYYY-MM-DDTHH:MM' in Lagos time — what yt_publish.parse_publish_at reads as WAT."""
    return when.astimezone(LAGOS).strftime("%Y-%m-%dT%H:%M")


def human(when):
    """'Sat 25 Oct 2026, 7:00pm' — the owner reads 12-hour clocks."""
    w = when.astimezone(LAGOS)
    hour = w.hour % 12 or 12
    return "%s %d %s %d, %d:%02d%s" % (w.strftime("%a"), w.day, w.strftime("%b"), w.year,
                                       hour, w.minute, "am" if w.hour < 12 else "pm")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1 or argv[0] not in KINDS:
        print("usage: publish_calendar.py shorts|deepdive", file=sys.stderr)
        return 2
    print(iso_wat(next_slot(argv[0])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
