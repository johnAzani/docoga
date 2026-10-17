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
import deepdive_promo  # noqa: E402  the Deep-Dive's week in this channel (17 Oct 2026)

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


# Owner, 17 Oct 2026: "the Thread is only text it uploads." Every slot now carries a card the
# lane renders and publishes itself (site/social/<day>-threads[-evening].jpg → this URL). The old
# evening design borrowed the Instagram lane's card, so a day the Instagram slot gate skipped —
# or the restricted profile failed — left Threads with words alone.
CARD_URL = "https://docoga.com.ng/social/%s-threads%s.jpg"
CARD_PATH = "site/social/%s-threads%s.jpg"


SLOT_SUFFIX = {"lunch": "", "evening": "-evening", "morning": "-morning"}

# The 07:20 WAT post asks one of these under the day's hook. Threads ranks by reply rate first
# (every 2026 study agrees), so the morning post is a question, not an announcement — and it
# rotates, so the account never asks the same thing two days running.
MORNING_QUESTIONS = (
    "Has this happened to you or someone you know? Tell me how it ended.",
    "Tenant or landlord — which side of this have you been on?",
    "What would you have done differently?",
    "What is the one thing you would tell a first-time tenant about this?",
    "Lagos, Abuja, Port Harcourt, Kano — where are you renting, and is it the same there?",
)


def slot_suffix(slot):
    return SLOT_SUFFIX.get(slot, "")


def card_for(day, slot):
    suffix = slot_suffix(slot)
    return CARD_URL % (day.isoformat(), suffix), CARD_PATH % (day.isoformat(), suffix)


def build_morning(day, rng):
    """The 07:20 WAT post (17 Oct 2026, visibility research): 7 am is Threads' peak hour in
    Nigeria (pre-work browsing), a question earns the replies Threads ranks by, and the words
    already exist — the spoken hook of the day's Short (the brain's, or the rotation's), the
    one paragraph written to stop a thumb. Image post, no link (a link costs reach; the lunch
    post carries it), the day's topic tag, no poll (refused beside an image)."""
    import generate_short_video as words  # the Short's words; the renderer is never imported
    script = words.script_for_date(day)
    slides = script.get("slides") or []
    hook = " ".join(str((slides[0] if slides else {}).get("say") or "").split())
    if not hook:
        hook = str(script.get("title") or "").strip()
    question = MORNING_QUESTIONS[day.toordinal() % len(MORNING_QUESTIONS)]
    pack = brain_drafts.draft_for(day)
    text = hook + "\n\n" + question
    if pack and brain_drafts.has_claims(pack) and brain_drafts.DISCLAIMER.lower() not in text.lower():
        text = text + "\n\n" + brain_drafts.DISCLAIMER
    text, notes = fit(brain_drafts.strip_links(text), "")
    notes = ["morning: hook of '%s'" % script.get("title", "")] + list(notes)
    extras = extras_for(pack)
    extras["poll"] = None
    extras["image_url"], extras["card_path"] = card_for(day, "morning")
    extras["reply_text"] = None
    return "morning", text, notes, extras


def build_evening(day, rng):
    """The 20:10 WAT post (17 Oct 2026, brain/strategy.md): Threads' best hour in Nigeria is
    7–9 pm; an image post earns ~1.6× a text post; a link in the body costs reach. So the
    evening slot is the day's card as an IMAGE post, link-free words, and the link in our own
    reply. The card is the one the Instagram lane published an hour earlier (no second render,
    no second commit, ₦0); if it is not there the publisher posts the words alone."""
    pack = brain_drafts.draft_for(day)
    promo = deepdive_promo.pack_for(day, "threads_evening")
    if promo:
        # Launch night (tools/deepdive_promo.py): ~70 minutes after the episode went public.
        post_type = "deepdive"
        text, notes = fit(promo["text"], "")
        notes = ["deep-dive launch: %s" % promo["title"]] + list(notes)
    elif pack:
        post_type = brain_drafts.post_type(pack)
        text, notes = fit(brain_drafts.threads_evening(pack), "")
        notes = ["brain: %s (evening)" % pack.get("theme")] + list(notes)
    else:
        options = [t for t in tg.WEEKLY_SCHEDULE.get(day.weekday(), ["promo"]) if t != "promo"] or ["promo"]
        post_type = rng.choice(options)
        plain = to_plain(rng.choice(tg.TEMPLATES[post_type])).strip()
        plain = brain_drafts.strip_links(plain)
        if not plain:
            raise ValueError("template for %r de-escaped to nothing" % post_type)
        text, notes = fit(plain, "")
    extras = extras_for(pack)
    extras["poll"] = None                       # a poll next to an image is refused; the poll is the lunch post's
    extras["image_url"], extras["card_path"] = card_for(day, "evening")
    extras["reply_text"] = promo["reply_text"] if promo else brain_drafts.evening_reply(pack)
    if promo:
        extras["card_text"] = promo["card_text"]
    return post_type, text, notes, extras


def build(day, rng, slot="lunch"):
    """Today's Threads post: the brain's short copy when there is a pack, else one
    template, de-escaped — either way fitted to Meta's limits, with its post type."""
    if slot == "evening":
        return build_evening(day, rng)
    if slot == "morning":
        return build_morning(day, rng)
    pack = brain_drafts.draft_for(day)
    promo = deepdive_promo.pack_for(day, "threads")
    if promo:
        # Two days after the episode went public: "in case you missed it", link in our reply;
        # the Instagram lane reads the same file and gets its own caption (link in bio).
        post_type = "deepdive"
        text, notes = fit(promo["text"], "")
        extras = extras_for(pack)
        extras["poll"] = None
        extras["reply_text"] = promo["reply_text"]
        extras["card_text"] = promo["card_text"]
        extras["ig_caption"] = promo["ig_caption"]
        notes = ["deep-dive recap: %s" % promo["title"]] + list(notes)
    elif pack:
        post_type = brain_drafts.post_type(pack)
        text, notes = fit(brain_drafts.tag_links(brain_drafts.threads_text(pack), "threads"), brain_drafts.hashtags(pack, "threads"))
        extras = extras_for(pack)
        notes = ["brain: %s" % pack.get("theme")] + list(notes)
    else:
        post_type = rng.choice(tg.WEEKLY_SCHEDULE.get(day.weekday(), ["promo"]))
        template = rng.choice(tg.TEMPLATES[post_type])
        plain = to_plain(template).strip()
        if not plain:
            raise ValueError("template for %r de-escaped to nothing" % post_type)
        hashtags = tg.HASHTAGS.get(post_type, "#DocOga")
        text, notes = fit(brain_drafts.tag_links(plain, "threads"), hashtags)
        extras = extras_for(None)
    # The lunch post carries the day's card too (image posts earn ~1.6× a text post). A poll
    # cannot sit beside an image, so on poll days the publisher posts the card and asks the poll
    # in its own reply underneath.
    extras["image_url"], extras["card_path"] = card_for(day, "lunch")
    return post_type, text, notes, extras


def extras_for(pack):
    """What travels with the text: the one topic tag Threads lets a post carry, and the poll
    when the brain wrote one (engagement days). Both are ₦0 reach levers (brain/strategy.md)."""
    return {"topic_tag": brain_drafts.threads_topic(pack or {}), "poll": brain_drafts.threads_poll(pack or {})}


def generate(day=None, write=True, slot="lunch"):
    """Return today's Threads post, and by default write it under `assets/threads/`."""
    day = day or datetime.now(LAGOS).date()
    rng = random.Random("docoga-threads-%s%s" % (day.isoformat(), slot_suffix(slot)))

    post_type, text, notes, extras = build(day, rng, slot)
    pack = brain_drafts.draft_for(day)
    # Instagram reads the same copy (instagram_autopost.yml): its caption opens with the search
    # phrase (Google indexes professional posts; Instagram search reads the first line), its link
    # carries the Instagram tag, and the card gets alt text (≤1,000 chars) — ₦0 SEO, 17 Oct 2026.
    seo = brain_drafts.seo_line(pack, post_type)
    ig_caption = text.replace("?s=th", "?s=ig")
    if seo.lower() not in ig_caption.lower():
        ig_caption = seo + "\n\n" + ig_caption
    if extras.get("ig_caption"):
        ig_caption = extras["ig_caption"]           # a Deep-Dive recap day: Instagram's own words

    content = {
        "ig_caption": ig_caption,
        "alt_text": brain_drafts.alt_text(pack, text),
        "date": day.isoformat(),
        "slot": slot,
        "image_url": extras.get("image_url"),
        "card_path": extras.get("card_path"),
        "card_text": extras.get("card_text"),
        "reply_text": extras.get("reply_text"),
        "day_of_week": day.weekday(),
        "day_name": day.strftime("%A"),
        "post_type": post_type,
        "text": text,
        "cost": threads_cost(text),
        "links": link_count(text),
        "trimmed": notes,
        "topic_tag": extras["topic_tag"],
        "poll": extras["poll"],
        "generated_at": datetime.now(LAGOS).isoformat(),
        "source": "threads",
    }

    if write:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        suffix = slot_suffix(slot)
        for name in ("threads_content_%s%s.json" % (day.isoformat(), suffix), "threads_content_latest.json"):
            with open(ASSETS_DIR / name, "w") as handle:
                json.dump(content, handle, indent=2)

    log(" Threads content for %s (%s) — %s post, %d of %d characters, trimmed=%s"
        % (day.isoformat(), slot, post_type, content["cost"], MAX_COST,
           "; ".join(notes) if notes else "nothing"))
    return content


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate DocOga's Threads post for a day")
    parser.add_argument("--date", help="ISO date to generate for (default: today in Africa/Lagos)")
    parser.add_argument("--print", dest="show", action="store_true", help="print the post and exit")
    parser.add_argument("--no-write", action="store_true", help="do not touch assets/")
    parser.add_argument("--slot", choices=["morning", "lunch", "evening"], default="lunch",
                        help="morning = the 07:20 WAT question under the day's hook; lunch = the 13:10 WAT post; "
                             "evening = the 20:10 WAT image post with the link in a reply")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    day = date.fromisoformat(args.date) if args.date else datetime.now(LAGOS).date()
    content = generate(day, write=not args.no_write, slot=args.slot)

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
