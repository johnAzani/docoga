#!/usr/bin/env python3
"""fresh.py — nothing twice: the one memory every rotation fallback consults before it speaks.

Owner, 24 Oct 2026: "Make sure you are not repeating or recycling contents." The audit that
morning found three ways the machine had been saying the same thing twice:

  * the Shorts rotation walked six scripts by the day's ordinal — five weekdays over a six-script
    cycle brought "Pay the wrong agent" back on 15 and 21 Oct and "Skip the photos" on 16 and
    22 Oct, and every hand-off (Reel, IG Reel, Stories, TikTok draft, Telegram video) carried the
    repeat with it;
  * the Threads morning post is the day's Short hook, so on weekends — no Short — it replayed a
    rotation hook that had already been on the profile ("Most people sign a tenancy agreement…",
    18 and 24 Oct); the live duplicate guard missed it because the profile's 25 most recent posts
    were mostly the replies lane's replies;
  * the Telegram fallback drew `random.choice` with no memory at all.

This module answers one question for all of them: *when did we last say this, on this platform?*
The ledgers are the memory (logs/youtube_published.json, logs/threads_sent.json,
logs/instagram_sent.json, logs/telegram_sent.json) — nothing new is written, so a re-run sees
exactly what the first run saw. A line is FRESH when the platform has not carried it for
FRESH_DAYS. The rotation pick starts where the old ordinal walk would have landed (so a day with
no history is unchanged and the tests that pin those days still hold) and walks forward to the
first fresh script; when every script is stale it returns the least recently used one flagged
`stale`, and the caller decides — the Shorts lane asks the brain for a new Short first and skips
the day rather than publish a repeat (scripts/youtube_short_daily.py).

    DOCOGA_FRESH=off     ignore the ledgers (tests that pin the bare rotation; never in production)
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRESH_DAYS = 28          # a platform must not carry the same words twice inside four weeks
KEY_WORDS = 6            # the first six words name a line (ledger titles keep ~60 characters)

LEDGERS = {
    "youtube": ROOT / "logs" / "youtube_published.json",
    "threads": ROOT / "logs" / "threads_sent.json",
    "instagram": ROOT / "logs" / "instagram_sent.json",
    "telegram": ROOT / "logs" / "telegram_sent.json",
    "facebook": ROOT / "logs" / "facebook_reels.json",
}

_URL = re.compile(r"https?://\S+")
_TAG = re.compile(r"(?<!\w)[#@]\w+")
_PREFIX = re.compile(r"^(?:story|reel|post|card)\s*·\s*", re.I)
_WORD = re.compile(r"[^\w\s']+", re.U)
_HASH_TITLE = re.compile(r"^telegram \w+ [0-9a-f]{10}$")   # the Telegram ledger's content key, not words


def enabled(env=None):
    env = os.environ if env is None else env
    return str(env.get("DOCOGA_FRESH", "on")).strip().lower() not in ("off", "0", "false", "no")


def key(text, words=KEY_WORDS):
    """The fingerprint of a line: lowercase, no links, tags, emoji or punctuation, first `words`
    words. "Pay the wrong agent. Lose the flat." and "Reel · Pay the wrong agent. Lose the flat."
    and the YouTube title "Renting through an agent in Nigeria: pay the wrong agent, lose the flat"
    do NOT share a key (the title is a different sentence) — which is why the YouTube history is
    read from the ledger's `topic` field, the script's own title."""
    text = _PREFIX.sub("", str(text or ""))
    text = _URL.sub(" ", text)
    text = _TAG.sub(" ", text)
    text = _WORD.sub(" ", text.lower())
    return " ".join(text.split()[:words])


def _date_of(row):
    for field in ("date", "recorded_at", "sent_at", "published_at"):
        raw = row.get(field)
        if raw:
            try:
                return datetime.fromisoformat(str(raw)[:19]).date()
            except ValueError:
                continue
    return None


def _rows(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get("items") or data.get("entries") or data.get("sent") or []
    return [r for r in data if isinstance(r, dict)]


def history(platform, path=None, env=None):
    """{key: latest date the platform carried it}. YouTube's key is the script title (`topic`);
    the others key the text the ledger kept (`title` is the first ~60 characters of the post,
    `note` the longer excerpt when there is one)."""
    if not enabled(env):
        return {}
    path = Path(path or LEDGERS[platform])
    out = {}
    for row in _rows(path):
        when = _date_of(row)
        if not when:
            continue
        texts = [row.get("topic")] if platform == "youtube" else [row.get("note"), _untruncated(row.get("title"))]
        for text in texts:
            if _HASH_TITLE.match(str(text or "").strip()):
                continue
            k = key(text)
            if not k or len(k.split()) < 3:
                continue
            if k not in out or out[k] < when:
                out[k] = when
            break
    return out


def _untruncated(title):
    """A ledger title is the post's first ~60 characters, cut mid-word; drop the cut word."""
    title = str(title or "")
    if len(title) >= 56 and title[-1:].isalnum():
        title = title.rsplit(" ", 1)[0]
    return title


def last_seen(text, hist):
    return hist.get(key(text))


def is_fresh(text, hist, day, days=FRESH_DAYS):
    """True when `hist` has not carried `text` within `days` before `day` (publishes dated on or
    after `day` are a re-run's own record, not a reason to skip)."""
    seen = last_seen(text, hist)
    if seen is None or seen >= day:
        return True
    return (day - seen).days >= days


def pick_rotation(day, scripts, hist, start=None, days=FRESH_DAYS, name=lambda s: s.get("title")):
    """The rotation's script for `day` that the platform has not carried for `days`.

    Walks from `start` (default: the old ordinal position, so an empty history changes nothing)
    through the pool in order and takes the first FRESH script; when none is fresh, the least
    recently used script is returned with `stale=True` and `last_seen` set, and the caller must
    not publish it as new. `name` reads the words that identify a script (its title by default;
    the Threads morning passes the spoken hook). Returns {"script", "stale", "last_seen"}."""
    pool = list(scripts)
    if not pool:
        return {"script": None, "stale": True, "last_seen": None}
    n = len(pool)
    i0 = (day.toordinal() - 1) % n if start is None else start % n
    order = [pool[(i0 + k) % n] for k in range(n)]
    for s in order:
        if is_fresh(name(s), hist, day, days):
            return {"script": s, "stale": False, "last_seen": last_seen(name(s), hist)}
    oldest = min(order, key=lambda s: (last_seen(name(s), hist) or date.min, order.index(s)))
    return {"script": oldest, "stale": True, "last_seen": last_seen(name(oldest), hist)}


def report(day=None, scripts=None):
    """CLI view: what each rotation script last did on YouTube."""
    day = day or date.today()
    hist = history("youtube")
    lines = []
    for s in scripts or []:
        seen = last_seen(s.get("title"), hist)
        state = "never" if seen is None else "%s (%d days)" % (seen.isoformat(), (day - seen).days)
        lines.append("%-44s %s%s" % (s.get("title"), state, "" if is_fresh(s.get("title"), hist, day) else "  STALE"))
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import generate_short_video as words  # noqa: E402
    print(report(scripts=words.VIDEO_SCRIPTS))
