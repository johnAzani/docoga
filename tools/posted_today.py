#!/usr/bin/env python3
"""posted_today.py — how many records a lane's ledger already carries for today (Africa/Lagos).

    python3 tools/posted_today.py logs/instagram_sent.json            # prints a number
    python3 tools/posted_today.py logs/instagram_sent.json --date 2026-11-05

6 Nov 2026. GitHub's cron fires late and *in addition to* the clock's dispatch; a lane whose
window is "the hour and the next" can therefore run twice in one evening. The feed post has a
caption guard; a Story has no caption. The ledger the lane commits after every post is the one
record both share, so a scheduled run that finds today's date already in it does nothing.
Reads `date` (YYYY-MM-DD) or, failing that, the day part of `recorded_at`/`posted_at`. Any
unreadable ledger counts as 0 — a broken file must never silence a lane.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import zoneinfo

LAGOS = zoneinfo.ZoneInfo("Africa/Lagos")


def rows_of(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("sent", "posts", "items", "published", "entries"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def day_of(row) -> str:
    if not isinstance(row, dict):
        return ""
    d = str(row.get("date") or "")
    if len(d) >= 10:
        return d[:10]
    for key in ("recorded_at", "posted_at", "created_at"):
        v = str(row.get(key) or "")
        if len(v) >= 10:
            try:
                t = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
                if t.tzinfo is not None:
                    t = t.astimezone(LAGOS)
                return t.date().isoformat()
            except ValueError:
                return v[:10]
    return ""


def posted_today(path, today: str | None = None, topic_prefix: str = "") -> int:
    today = today or dt.datetime.now(LAGOS).date().isoformat()
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    n = 0
    for row in rows_of(data):
        if day_of(row) != today:
            continue
        if topic_prefix and not str(row.get("topic") or "").startswith(topic_prefix):
            continue
        n += 1
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ledger")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today in Africa/Lagos)")
    ap.add_argument("--topic", default="", help="count only rows whose topic starts with this")
    a = ap.parse_args(argv)
    print(posted_today(a.ledger, a.date, a.topic))
    return 0


if __name__ == "__main__":
    sys.exit(main())
