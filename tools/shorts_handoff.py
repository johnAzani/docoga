#!/usr/bin/env python3
"""
tools/shorts_handoff.py — the day's Short, handed to the Threads evening slot
==============================================================================

Owner, 21 Oct 2026: "Threads has never posted videos, why." The publisher could not (TEXT and
IMAGE only — fixed in tools/threads_publish.py), and nothing kept a copy of the Short where
Threads could fetch it: the render lives inside the 6:00pm Shorts run and goes to YouTube,
TikTok's inbox and Telegram, then the runner is gone. Threads fetches media by **public URL**
(`media_type=VIDEO&video_url=`), so the file has to be reachable at 8:10pm.

The Shorts lane therefore hands the file over (`host`): tools/media_host.py puts it in the
`docoga-pass` KV namespace under a 32-character random name (the Instagram third door, ₦0,
four KV writes for a ~50 MB Short, gone by itself after `--ttl-hours`), and the URL is written
to `logs/shorts_media.json`, which the lane commits with its publish ledger. The Threads lane
asks (`today`) whether there is a Short from today whose hosting has not expired, and posts it.

    host  --video FILE --video-id ID --title T [--date YYYY-MM-DD] [--ttl-hours 30]
          → HANDOFF_URL=  HANDOFF_NAME=  HANDOFF_EXPIRES=  (exit 0; exit 2 = not hosted, reason printed)
    today [--date YYYY-MM-DD] [--min-minutes 20]
          → THREADS_VIDEO_URL=<url>  THREADS_VIDEO_TITLE=<title>  (empty URL when there is none; exit 0)

Lagos days: the Short renders at 6:00pm and Threads posts at 8:10pm the same evening.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import media_host  # noqa: E402

LAGOS = timezone(timedelta(hours=1))
LEDGER = ROOT / "logs" / "shorts_media.json"
KEEP = 14                    # days of history kept in the ledger
DEFAULT_TTL_HOURS = 30       # 6:00pm today → gone by midnight tomorrow; Threads fetched it at 8:10pm


def lagos_today(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(LAGOS).strftime("%Y-%m-%d")


def load(path=LEDGER):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("history", [])
    return data


def save(data, path=LEDGER):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def host(video, video_id, title, date=None, ttl_hours=DEFAULT_TTL_HOURS, ledger=LEDGER, env=None,
         http=None, sleeper=None, now=None, log=print, series="", series_topic=""):
    """Host the file and record it. Returns the record; raises media_host.HostError."""
    kwargs = {"env": env, "http": http}
    if sleeper is not None:
        kwargs["sleeper"] = sleeper
    put = media_host.put(video, ttl_hours=ttl_hours, verify_seconds=180, **kwargs)
    if not put.get("live"):
        # Hosted but not answering yet: keep the record — Threads polls the URL again at 8:10pm.
        log("::warning title=Short hosted but not live yet::%s answered %s after %ss — the Threads lane re-checks "
            "before posting" % (put["url"], put.get("status"), put.get("waited")))
    now = now or datetime.now(timezone.utc)
    record = {"date": date or lagos_today(now), "video_id": video_id, "title": title,
              "url": put["url"], "name": put["name"], "bytes": put["bytes"],
              "hosted_at": now.isoformat(timespec="seconds"),
              "expires_at": (now + timedelta(seconds=put["ttl"])).isoformat(timespec="seconds"),
              "run_id": os.environ.get("GITHUB_RUN_ID", ""),
              # the week's series frame (23 Oct 2026): "Part 2 of 5 · Rent receipt law" and the
              # Threads topic tag the evening video post wears; empty on a plain day
              "series": " ".join(str(series or "").split()), "series_topic": " ".join(str(series_topic or "").split())}
    data = load(ledger)
    data["latest"] = record
    data["history"] = ([r for r in data["history"] if r.get("date") != record["date"]] + [record])[-KEEP:]
    save(data, ledger)
    log("HANDOFF_URL=%s" % record["url"])
    log("HANDOFF_NAME=%s" % record["name"])
    log("HANDOFF_EXPIRES=%s" % record["expires_at"])
    return record


def today(date=None, min_minutes=20, ledger=LEDGER, now=None):
    """The record for `date` (Lagos today) if its hosting outlives the next `min_minutes`; else None."""
    now = now or datetime.now(timezone.utc)
    date = date or lagos_today(now)
    data = load(ledger)
    rows = [data.get("latest") or {}] + list(reversed(data.get("history", [])))
    for row in rows:
        if row.get("date") != date or not row.get("url"):
            continue
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except (KeyError, ValueError):
            continue
        if expires - now >= timedelta(minutes=min_minutes):
            return row
        return None
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("host")
    h.add_argument("--video", required=True)
    h.add_argument("--video-id", required=True)
    h.add_argument("--title", default="")
    h.add_argument("--date")
    h.add_argument("--ttl-hours", type=float, default=DEFAULT_TTL_HOURS)
    h.add_argument("--series", default="", help='"Part 2 of 5 · Rent receipt law" on a series day')
    h.add_argument("--series-topic", default="", help="the Threads topic tag for the video post on a series day")
    h.add_argument("--ledger", default=str(LEDGER))
    t = sub.add_parser("today")
    t.add_argument("--date")
    t.add_argument("--min-minutes", type=int, default=20)
    t.add_argument("--ledger", default=str(LEDGER))
    args = ap.parse_args(argv)
    if args.cmd == "host":
        try:
            host(args.video, args.video_id, args.title, date=args.date, ttl_hours=args.ttl_hours,
                 ledger=Path(args.ledger), series=args.series, series_topic=args.series_topic)
        except media_host.HostError as exc:
            print("::warning title=Short not handed to Threads::%s — tonight's Threads post carries the card instead" % exc)
            print("HANDOFF_URL=")
            return 2
        return 0
    row = today(date=args.date, min_minutes=args.min_minutes, ledger=Path(args.ledger))
    if row:
        print("THREADS_VIDEO_URL=%s" % row["url"])
        print("THREADS_VIDEO_TITLE=%s" % " ".join(str(row.get("title") or "").split()))
        print("THREADS_VIDEO_ID=%s" % row.get("video_id", ""))
        print("THREADS_VIDEO_SERIES=%s" % " ".join(str(row.get("series") or "").split()))
        print("THREADS_VIDEO_TOPIC=%s" % " ".join(str(row.get("series_topic") or "").split()))
    else:
        print("no Short hosted for %s (or its hosting ends within %d minutes) — the card posts as usual"
              % (args.date or lagos_today(), args.min_minutes))
        print("THREADS_VIDEO_URL=")
    return 0


if __name__ == "__main__":
    sys.exit(main())
