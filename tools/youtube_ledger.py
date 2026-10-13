#!/usr/bin/env python3
"""Publish ledger for the unattended DocOga YouTube Shorts pipeline.

Why this file exists
--------------------
`.github/workflows/youtube_scheduled.yml` renders a Short and uploads it
**public, twice a week, with nobody watching**. The topic rotation in
`scripts/generate_short_video.py` is deterministic and date-seeded, so:

* a manual re-run, a GitHub retry, or a second dispatch on the same day
  uploads the *same* Short again and the channel silently carries a
  duplicate — nothing in the repo records that it happened;
* and there is no answer in the repo to "what did we actually publish, and
  where is it?" without logging into YouTube and reading the channel.

The ledger is the durable answer to both. It is a small JSON file
(`logs/youtube_published.json`) committed back by the workflow after a
successful upload.

Design rules — they matter, because the workflow commits this file to the
default branch by itself:

1. **stdlib only.** The CI job must stay dependency-light.
2. **A missing or corrupt ledger never blocks publishing.** It warns and
   treats the history as empty. A bookkeeping file must not be able to stop
   the channel going quiet.
3. **Bounded.** Newest first, capped at `MAX_ENTRIES`, so a file we push to
   twice a week cannot grow forever.

Exit codes for `check` (deliberately not 2 — argparse owns that for bad
usage, and a usage error must never look like "duplicate, skip"):

    0  clear to publish
    3  this title is already in the ledger inside the duplicate window

Usage
-----
    python3 tools/youtube_ledger.py check  --title "..." --date 2026-10-09
    python3 tools/youtube_ledger.py record --title "..." --video-id abc123 \
        --url https://youtube.com/watch?v=abc123 --privacy public \
        --date 2026-10-09 --run-id 123456789 --topic "Keep a Rent Paper Trail"
    python3 tools/youtube_ledger.py show --limit 10
"""
import argparse
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_LEDGER = os.path.join(ROOT, "logs", "youtube_published.json")

# The rotation holds 6 topics and the schedule fires twice a week, so a title
# naturally returns after ~3 weeks. 7 days therefore blocks only the accident
# we care about (same-day re-run / retry) and never the natural repeat.
DEFAULT_WINDOW_DAYS = 7
MAX_ENTRIES = 200

EXIT_CLEAR = 0
EXIT_USAGE = 1
EXIT_DUPLICATE = 3

WAT = timezone(timedelta(hours=1))


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def load(path=DEFAULT_LEDGER):
    """Return the entries, oldest-last. Missing or unreadable -> empty list.

    A corrupt ledger is backed up beside the original instead of being
    silently overwritten, so the history is recoverable, and it never blocks
    a publish.
    """
    if not os.path.exists(path):
        return []
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (ValueError, OSError) as exc:
        backup = "%s.corrupt-%s" % (path, datetime.now(WAT).strftime("%Y%m%dT%H%M%S"))
        try:
            os.replace(path, backup)
            warn("ledger at %s was unreadable (%s); moved to %s" % (path, exc, os.path.basename(backup)))
        except OSError:
            warn("ledger at %s was unreadable (%s) and could not be backed up" % (path, exc))
        return []
    if isinstance(data, dict):  # tolerate an older {"entries": [...]} shape
        data = data.get("entries", [])
    if not isinstance(data, list):
        warn("ledger at %s is not a list; treating it as empty" % path)
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def save(entries, path=DEFAULT_LEDGER):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    trimmed = entries[:MAX_ENTRIES]
    with io.open(path, "w", encoding="utf-8") as handle:
        json.dump(trimmed, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return trimmed


def _label():
    """The annotation title. This ledger tool serves more than one lane now
    (Facebook Reels reuse it on logs/facebook_reels.json), and a
    "YouTube publish ledger" warning on a Facebook run costs an afternoon of
    reading the wrong workflow. Default keeps YouTube's wording unchanged.
    """
    return os.environ.get("LEDGER_LABEL", "YouTube publish ledger")


def warn(message):
    """A GitHub Actions notice when running in CI, plain text otherwise."""
    if os.environ.get("GITHUB_ACTIONS"):
        print("::warning title=%s::%s" % (_label(), message))
    else:
        print("warning: %s" % message, file=sys.stderr)


def notice(message):
    if os.environ.get("GITHUB_ACTIONS"):
        print("::notice title=%s::%s" % (_label(), message))
    else:
        print(message)


def already_published(entries, title, on_date, window_days=DEFAULT_WINDOW_DAYS):
    """Return the matching entry if `title` went out within the window."""
    wanted = (title or "").strip().lower()
    if not wanted:
        return None
    for entry in entries:
        if (entry.get("title") or "").strip().lower() != wanted:
            continue
        try:
            published = parse_date(str(entry.get("date") or entry.get("run_date") or ""))
        except ValueError:
            # An undated entry is treated as recent: better to skip than to
            # publish a duplicate we cannot place in time.
            return entry
        if abs((on_date - published).days) <= window_days:
            return entry
    return None


def record(entries, path=DEFAULT_LEDGER, **fields):
    """Append one publish, newest first, de-duplicated by video id."""
    entry = {"recorded_at": datetime.now(WAT).isoformat(timespec="seconds")}
    entry.update(fields)
    entries = [e for e in entries if e.get("video_id") != entry.get("video_id")]
    entries.insert(0, entry)
    save(entries, path)
    return entry


def cmd_check(args):
    entries = load(args.ledger)
    duplicate = already_published(entries, args.title, parse_date(args.date), args.window_days)
    if duplicate:
        notice(
            '"%s" is already in the ledger (%s, %s) — inside the %d-day duplicate window.'
            % (
                args.title,
                duplicate.get("date", "unknown date"),
                duplicate.get("url", "no url recorded"),
                args.window_days,
            )
        )
        return EXIT_DUPLICATE
    print("No recent duplicate of \"%s\" in %s (%d entries checked)." % (args.title, args.ledger, len(entries)))
    return EXIT_CLEAR


def cmd_record(args):
    entries = load(args.ledger)
    entry = record(
        entries,
        path=args.ledger,
        title=args.title,
        topic=args.topic or args.title,
        video_id=args.video_id,
        url=args.url or ("https://youtube.com/watch?v=%s" % args.video_id),
        privacy=args.privacy,
        date=args.date,
        run_id=args.run_id or "",
        size_bytes=args.size_bytes,
    )
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    print("Recorded in %s (%d entries)." % (args.ledger, len(load(args.ledger))))
    return EXIT_CLEAR


def cmd_show(args):
    entries = load(args.ledger)
    if not entries:
        print("No Shorts recorded in %s yet." % args.ledger)
        return EXIT_CLEAR
    for entry in entries[: args.limit]:
        print(
            "%s  %-10s  %-45s  %s"
            % (
                entry.get("date", "?")[:10],
                entry.get("privacy", "?"),
                (entry.get("title") or "?")[:45],
                entry.get("url", "?"),
            )
        )
    return EXIT_CLEAR


def build_parser():
    parser = argparse.ArgumentParser(description="DocOga YouTube Shorts publish ledger")
    parser.add_argument("--ledger", default=DEFAULT_LEDGER, help="path to the ledger JSON file")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="exit 3 if this title was already published recently")
    check.add_argument("--title", required=True)
    check.add_argument("--date", required=True, help="run date, YYYY-MM-DD (WAT)")
    check.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    check.set_defaults(func=cmd_check)

    rec = subparsers.add_parser("record", help="append a successful publish")
    rec.add_argument("--title", required=True)
    rec.add_argument("--video-id", required=True)
    rec.add_argument("--url", default="")
    rec.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    rec.add_argument("--date", required=True, help="run date, YYYY-MM-DD (WAT)")
    rec.add_argument("--run-id", default="")
    rec.add_argument("--topic", default="")
    rec.add_argument("--size-bytes", type=int, default=0)
    rec.set_defaults(func=cmd_record)

    show = subparsers.add_parser("show", help="print recent publishes")
    show.add_argument("--limit", type=int, default=20)
    show.set_defaults(func=cmd_show)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
