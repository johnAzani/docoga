#!/usr/bin/env python3
"""footage_ledger.py — what has already been shown behind the words, so it is not shown again.

Owner, 29 Oct 2026: "I am seeing the same image or video clips behind the card of all the videos."
Why it happened: stock_media.choose() took the single best-scoring candidate for a query, and
shot_match.pick() took the first relevant one. The queries come from a short glossary (a sentence
about a receipt always asks for "paper receipt"), the search results are stable from day to day,
and the `used` set that stops a clip repeating lived for ONE render only. So every Short, Reel and
card about receipts opened on the same Pixabay clip, and every one about court on the same gavel.

Two defences, both ₦0, both deterministic so a test can prove them:

  1. A ledger of ids with the day each was last shown (logs/footage_used.json, committed by the
     lanes that render). A candidate shown in the last COOLDOWN_DAYS is pushed to the back of the
     queue — chosen only when nothing else relevant exists. Older than that it carries a small
     penalty, so the pool rotates rather than ping-pongs.
  2. A day-seeded tie-break among the near-best candidates. Even on a runner that lost the
     ledger (a lane that does not commit it, a fresh clone), the same query on two different
     days lands on two different clips, because the pick among the near-best is a hash of
     (day, query), not position 0.

The ledger never holds the media itself — only the door id ("pixabay:12345"), the query that
found it, the lane, the day and a count. 180 days of history, pruned on save.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "logs" / "footage_used.json"
COOLDOWN_DAYS = 21        # shown inside this window → last resort only
MEMORY_DAYS = 180         # older entries are forgotten on save
RECENT_PENALTY = 100      # effectively "after everything else"
OLD_PENALTY = 2           # a nudge so the rotation keeps moving
NEAR_BEST = 1             # candidates within this many points of the best share the day's draw

_STATE = {"data": None, "path": None}


def path():
    """logs/footage_used.json — or FOOTAGE_LEDGER; under unittest with no override, a scratch file,
    so a fake-http render in the suite never dirties the committed ledger."""
    if os.environ.get("FOOTAGE_LEDGER"):
        return Path(os.environ["FOOTAGE_LEDGER"])
    if "unittest" in sys.modules and not os.environ.get("FOOTAGE_LEDGER_REAL"):
        return Path("/tmp/docoga_footage_unittest.json")
    return LEDGER


def today():
    return (os.environ.get("RUN_DATE") or dt.date.today().isoformat())[:10]


def load(force=False):
    p = path()
    if _STATE["data"] is not None and _STATE["path"] == p and not force:
        return _STATE["data"]
    data = {"used": {}}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("used"), dict):
            data = raw
    except (OSError, ValueError):
        pass
    _STATE.update(data=data, path=p)
    return data


def _days_since(day, ref):
    try:
        return (dt.date.fromisoformat(ref[:10]) - dt.date.fromisoformat(day[:10])).days
    except (TypeError, ValueError):
        return None


def last_shown(media_id):
    """ISO day the id was last shown, or None."""
    rec = load()["used"].get(str(media_id))
    return rec.get("last") if rec else None


def penalty(media_id, day=None):
    """Points to subtract from a candidate's score: RECENT_PENALTY inside the cool-down, OLD_PENALTY
    after it, 0 if never shown."""
    last = last_shown(media_id)
    if not last:
        return 0
    age = _days_since(last, day or today())
    if age is None:
        return 0
    return RECENT_PENALTY if age < COOLDOWN_DAYS else OLD_PENALTY


def draw(day, query, n):
    """A stable index in range(n) for this (day, query): the day's pick among equals."""
    if n <= 1:
        return 0
    h = hashlib.sha1(("%s|%s" % (day, " ".join(str(query).lower().split()))).encode("utf-8")).hexdigest()
    return int(h[:8], 16) % n


def choose(cands, score, query, day=None, key=lambda c: c.get("id")):
    """The candidate to show: best (score − penalty); among those within NEAR_BEST of the best,
    the day's draw. `score(c)` is the caller's relevance score. None when `cands` is empty."""
    if not cands:
        return None
    day = day or today()
    ranked = sorted(((score(c) - penalty(key(c), day), i, c) for i, c in enumerate(cands)),
                    key=lambda t: (-t[0], t[1]))
    best = ranked[0][0]
    pool = [c for s, _, c in ranked if s >= best - NEAR_BEST]
    return pool[draw(day, query, len(pool))]


def record(media_id, query="", door="", lane="", day=None, save_now=True):
    """Remember that `media_id` was shown today. Writes through unless save_now=False."""
    if not media_id:
        return
    data = load()
    day = day or today()
    rec = data["used"].get(str(media_id)) or {"n": 0}
    rec.update(last=day, n=int(rec.get("n") or 0) + 1, query=query or rec.get("query", ""),
               door=door or rec.get("door", ""), lane=lane or os.environ.get("DOCOGA_LANE", rec.get("lane", "")))
    data["used"][str(media_id)] = rec
    if save_now:
        save()


def save():
    data = load()
    ref = today()
    keep = {}
    for k, v in data["used"].items():
        age = _days_since(v.get("last", ""), ref)
        if age is None or age <= MEMORY_DAYS:
            keep[k] = v
    data["used"] = dict(sorted(keep.items(), key=lambda kv: kv[1].get("last", ""), reverse=True))
    p = path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass        # a ledger that cannot be written must never cost the video
    return p


def status(day=None):
    data = load()
    day = day or today()
    recent = sum(1 for v in data["used"].values() if (_days_since(v.get("last", ""), day) or 10**6) < COOLDOWN_DAYS)
    return {"entries": len(data["used"]), "in_cooldown": recent, "cooldown_days": COOLDOWN_DAYS}


if __name__ == "__main__":
    print(json.dumps(status(), indent=1))
