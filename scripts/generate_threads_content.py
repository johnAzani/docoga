#!/usr/bin/env python3
"""
DocOga Threads content — today's copy, cut to fit a 500-character post
======================================================================

Third sibling of the same pipeline, and deliberately *not* a fourth voice:
`scripts/generate_telegram_content.py` owns the copy (templates, weekday rotation,
hashtag blocks), `scripts/generate_facebook_content.py` adapts it for a light-surfaced
feed, and this file adapts it for Threads. If Threads grew its own templates, then on
some Tuesday the two channels would say different things about the same law, and
nobody would be able to tell which one the site's content was derived from.

What Threads actually changes, and what the code therefore has to do:

  1. **500 characters, and emoji are charged by UTF-8 byte length.** Meta counts a
     post's length so that an emoji costs 4, not 1, so `len(text)` is not the number
     that decides whether the API accepts the post. `threads_cost()` is the only place
     that arithmetic lives, and `fit()` trims by it. A too-long post is not a warning
     you can ignore: the create call fails and the day is simply absent.
  2. **At most 5 links** in one post, or the API answers
     `THREADS_API__LINK_LIMIT_EXCEEDED` (enforced on 22 Dec 2025). Our copy links
     docoga.com.ng once, so this is a guard rail, not a feature — but it belongs here
     because the day someone pastes a "read all five" block, the failure lands on a
     green tick with no explanation.
  3. **No markup, ever** — same `to_plain()` stripper as Facebook, so a stray
     `\\.` cannot reach a public post.
  4. **Deterministic for the day**, seeded on the ISO date, for the same reason
     Facebook is: a re-run must produce *the same* post, or the duplicate guard in
     `tools/threads_publish.py` compares one sentence against another and finds
     nothing wrong with publishing it twice.

`--print` is how the owner sees today's post without posting it. Nothing here touches
the network, and nothing here writes outside `assets/threads/`.

    python3 scripts/generate_threads_content.py
    python3 scripts/generate_threads_content.py --date 2026-10-14 --print
"""

import argparse
import json
import random
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "tools", ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from telegram_mdv2 import to_plain          # noqa: E402  the one markup stripper
import generate_telegram_content as tg       # noqa: E402  the copy lives there
import brain_drafts  # noqa: E402  the brain's pack for the day, when there is one

import docoga_log  # noqa: E402  "where do the scratch files live", answered once

ASSETS_DIR = Path("assets/threads")
LOG_FILE = docoga_log.log_file("social_media.log")

# Africa/Lagos, because "today's post" is decided in the readers' timezone, not UTC:
# a run at 08:45 UTC is 09:45 in Lagos, and a UTC-midnight cut-over would hand Monday
# a Sunday's copy for the first hour of the Nigerian morning.
LAGOS = timezone(timedelta(hours=1))

MAX_COST = 500          # Meta: 500 characters, emoji charged at their byte length
LINK_LIMIT = 5          # Meta: >5 URLs in one post is THREADS_API__LINK_LIMIT_EXCEEDED

# Threads is a conversation, not a billboard: the hashtag block that suits a Facebook
# photo post reads like spam in a text thread. Two tags is the compromise — one source
# (postproxy's 2026 limits table) claims Threads allows exactly one hashtag per post,
# which Meta's own docs I could not find do not confirm. Two is inside the claim's
# margin for tolerance and outside every other account of the rule, and the failure
# mode of being wrong is a rejected post, not a silent one: the API says so out loud.
HASHTAG_KEEP = 2

# Cut order, and why: the tags are marketing, the sentences are the law.
TRIM_STEPS = ("hashtags", "links", "tail")


def log(message):
    line = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message)
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as handle:
            handle.write(line + "\n")
    except OSError:
        pass  # logging must never be the reason a day's post fails


def threads_cost(text):
    """What Threads charges for this string: 1 per ASCII char, UTF-8 bytes for the rest.

    `len("📸")` is 1 in Python and 4 to Meta. Everything that decides whether a post
    fits has to go through here, or the check passes locally and fails on the API.
    """
    total = 0
    for char in text:
        if ord(char) < 0x80:
            total += 1
        else:
            total += max(1, len(char.encode("utf-8")))
    return total


LINK_RE = re.compile(r"https?://\S+")


def link_count(text):
    return len(set(LINK_RE.findall(text)))


def _cut_to_cost(text, limit):
    """Shorten at a word boundary until the cost fits, so an emoji is never split.

    A ZWJ sequence (👨‍👩‍👧) is several code points with no space inside it, which is
    exactly why this trims by *words* and not by characters: cutting at an index can
    leave half a family emoji on the end of a post, and Threads will publish it.
    """
    if threads_cost(text) <= limit:
        return text
    words = text.split(" ")
    kept = []
    cost = 0
    # The ellipsis has to be paid for *in the platform's units*: "…" is U+2026, three UTF-8
    # bytes, so reserving one character overshoots a 500-byte budget by two and the API answers
    # "text too long" on a post that measured 500 locally. Found by
    # tools/tests/test_meta_lanes.test_a_trim_never_splits_a_grapheme, which is what the test is for.
    budget = limit - threads_cost("…")
    for word in words:
        add = threads_cost(word) + (1 if kept else 0)
        if cost + add > budget:
            break
        kept.append(word)
        cost += add
    if not kept:
        # A single word longer than the whole post (a pasted URL, a wall of text).
        # Fall back to a character cut, which cannot be a duplicate risk: this is the
        # only path that can split a multi-byte char, and it is unreachable for copy
        # that has a space anywhere in its first 500 bytes.
        out = ""
        for char in text:
            if threads_cost(out + char) > budget:
                break
            out += char
        return (out + "…").rstrip()
    trimmed = " ".join(kept)
    while threads_cost(trimmed + "…") > limit and kept:
        kept.pop()
        trimmed = " ".join(kept)
    return trimmed + "…"


def fit(body, hashtags):
    """Return `(text, notes)` — the post to send and, by name, what was dropped.

    The notes are the point. A generator that silently shortens your copy produces a
    post that reads fine and means something narrower, and nobody can tell afterwards.
    Every drop is reported, and the workflow prints the report.
    """
    notes = []
    text = body.strip()

    if link_count(text) > LINK_LIMIT:
        # Keep the first LINK_LIMIT URLs, defang the rest. Replacing rather than
        # deleting: "see docoga.com.ng/x" turned into "see" loses the thread's point.
        extra = len(set(LINK_RE.findall(text))) - LINK_LIMIT
        seen = []

        def _keep(match):
            if match.group(0) in seen:
                return match.group(0)
            seen.append(match.group(0))
            return match.group(0) if len(seen) <= LINK_LIMIT else ""

        text = LINK_RE.sub(_keep, text)
        notes.append("dropped %d link(s) over the %d-link cap" % (extra, LINK_LIMIT))

    block = " ".join(hashtags.split()[:HASHTAG_KEEP]) if hashtags else ""
    if block:
        candidate = "%s\n\n%s" % (text, block)
        if threads_cost(candidate) <= MAX_COST:
            text = candidate
        else:
            notes.append("dropped hashtags (%s) to fit %d characters" % (block, MAX_COST))

    if threads_cost(text) > MAX_COST:
        before = threads_cost(text)
        text = _cut_to_cost(text, MAX_COST)
        notes.append("trimmed %d → %d characters at a word boundary"
                     % (before, threads_cost(text)))

    for marker in ("\\", "*", "||", "_"):
        if marker in text:
            notes.append("markup marker %r survived de-escaping" % marker)
    return text, notes


def build(day, rng):
    """Today's Threads post: the brain's short copy when there is a pack, else one
    template, de-escaped — either way fitted to Meta's limits, with its post type."""
    pack = brain_drafts.draft_for(day)
    if pack:
        post_type = brain_drafts.post_type(pack)
        text, notes = fit(brain_drafts.threads_text(pack), brain_drafts.hashtags(pack, "threads"))
        return post_type, text, ["brain: %s" % pack.get("theme")] + list(notes)
    post_type = rng.choice(tg.WEEKLY_SCHEDULE.get(day.weekday(), ["promo"]))
    template = rng.choice(tg.TEMPLATES[post_type])
    plain = to_plain(template).strip()
    if not plain:
        raise ValueError("template for %r de-escaped to nothing" % post_type)
    hashtags = tg.HASHTAGS.get(post_type, "#DocOga")
    text, notes = fit(plain, hashtags)
    return post_type, text, notes


def generate(day=None, write=True):
    """Return today's Threads post, and by default write it under `assets/threads/`."""
    day = day or datetime.now(LAGOS).date()
    rng = random.Random("docoga-threads-%s" % day.isoformat())

    post_type, text, notes = build(day, rng)

    content = {
        "date": day.isoformat(),
        "day_of_week": day.weekday(),
        "day_name": day.strftime("%A"),
        "post_type": post_type,
        "text": text,
        "cost": threads_cost(text),
        "links": link_count(text),
        "trimmed": notes,
        "generated_at": datetime.now(LAGOS).isoformat(),
        "source": "threads",
    }

    if write:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("threads_content_%s.json" % day.isoformat(), "threads_content_latest.json"):
            with open(ASSETS_DIR / name, "w") as handle:
                json.dump(content, handle, indent=2)

    log(" Threads content for %s — %s post, %d of %d characters, trimmed=%s"
        % (day.isoformat(), post_type, content["cost"], MAX_COST,
           "; ".join(notes) if notes else "nothing"))
    return content


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate DocOga's Threads post for a day")
    parser.add_argument("--date", help="ISO date to generate for (default: today in Africa/Lagos)")
    parser.add_argument("--print", dest="show", action="store_true", help="print the post and exit")
    parser.add_argument("--no-write", action="store_true", help="do not touch assets/")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    day = date.fromisoformat(args.date) if args.date else datetime.now(LAGOS).date()
    content = generate(day, write=not args.no_write)

    if args.show:
        print("\n── today's Threads post (%d/%d characters) ─────────────────────────"
              % (content["cost"], MAX_COST))
        print(content["text"])
        print("──────────────────────────────────────────────────────────────────")
        for note in content["trimmed"]:
            print("· trimmed: %s" % note)
        if not content["trimmed"]:
            print("· nothing trimmed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
