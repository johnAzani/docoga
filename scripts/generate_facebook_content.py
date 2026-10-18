#!/usr/bin/env python3
"""
DocOga Facebook content — the same day's copy, in the shape Facebook reads
==========================================================================

The Telegram generator (`scripts/generate_telegram_content.py`) owns the copy:
the post types, the weekday rotation, the hashtag blocks. This file does not
invent a second set of templates, because two sets drift and then the two
channels say different things on the same Tuesday. It does three jobs:

  1. **De-escape.** The templates are hand-written for Telegram's MarkdownV2, so
     they literally contain `docoga\\.com\\.ng` and `*Get Clean Tenancy
     Agreements*`. Facebook has no markup — those backslashes and asterisks
     would be published as written. `telegram_mdv2.to_plain()` is the shared
     stripper the Telegram poster also uses for its plain-text fallback, so
     there is exactly one definition of "this message without markup".
  2. **Render the photo.** The day's copy is drawn on the brand card by
     `tools/social_card.py` (navy ground, Inter, DOCOGA kicker, docoga.com.ng
     footer) — the same card the Instagram lane ships. Nothing from `brand/` is
     ever the photo: those are logo-exploration sheets, and the one that reached
     the Page on 15 Oct 2026 was rejected by the owner ("not my brand style").
  3. **Be deterministic for the day.** Telegram picks with an unseeded
     `random.choice`, which is fine when a run happens once and never repeats.
     A Facebook run can be re-dispatched, retried after a red build, or run
     twice by a mis-click — and the duplicate guard in `post_facebook.py` skips a
     day that is already posted. If the copy also changed between the two runs,
     the second one would be a *different* post and no test could predict what
     today's post is. Seeding on the date makes the day reproducible, which is
     also what makes `tools/tests/test_post_facebook.py` able to assert on it.

Run directly to see what today would be:

    python3 scripts/generate_facebook_content.py
    python3 scripts/generate_facebook_content.py --date 2026-10-14 --print
"""

import argparse
import json
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "tools", ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from telegram_mdv2 import to_plain          # noqa: E402  (shared markup stripper)
import generate_telegram_content as tg       # noqa: E402  (the copy lives there)

ASSETS_DIR = Path("assets/facebook")
import docoga_log  # noqa: E402  one answer for "where do the scratch files live"

LOG_FILE = docoga_log.log_file("social_media.log")

LAGOS = timezone(timedelta(hours=1))

# The photo is the day's copy rendered as the brand card (tools/social_card.py:
# navy ground, Inter, DOCOGA kicker, docoga.com.ng footer) — the same card the
# Instagram lane ships. Until 15 Oct 2026 this lane drew from `brand/*.png`, the
# logo-exploration sheets, and the owner saw one on the Page: "this is not my
# brand style". social_card.BANNED_PHOTO_PREFIXES keeps brand/ out for good,
# and post_facebook.py refuses such a path even if one is handed to it.
import social_card  # noqa: E402  (the one card renderer for every static social post)
import brain_drafts  # noqa: E402  (the brain's pack for the day, when there is one)
import deepdive_promo  # noqa: E402  (the Deep-Dive's week in this channel, 17 Oct 2026)

# tools/fb_publish.py refuses a `source` upload above 4 MB; the card renderer
# walks JPEG quality down to stay under 900 KB, so this is belt and braces.
MAX_PHOTO_BYTES = 4 * 1024 * 1024
MIN_PHOTO_BYTES = 8 * 1024


def log(message):
    line = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message)
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as handle:
            handle.write(line + "\n")
    except OSError:
        pass  # logging must never be the reason a day's post fails


def raw_pick(day):
    """(post_type, template) the date-seeded rotation lands on for `day`, before the repeat guard."""
    rng = random.Random("docoga-facebook-%s" % day.isoformat())
    post_type = rng.choice(tg.WEEKLY_SCHEDULE.get(day.weekday(), ["promo"]))
    return post_type, rng.choice(tg.TEMPLATES[post_type])


def pick(day):
    """Today's rotation post, never the same words as yesterday's.

    Two seeded days can land on the same template (19 and 20 Oct 2026 both drew the caution-fee
    post), and a Page that says the same thing two days running reads as a bot. The guard is
    deterministic — yesterday's pick is recomputed, not remembered — so a re-run still produces
    the same post and the duplicate guard in post_facebook.py still has something to compare."""
    post_type, template = raw_pick(day)
    _, yesterday = raw_pick(day - timedelta(days=1))
    if template == yesterday:
        pool = tg.TEMPLATES[post_type]
        template = pool[(pool.index(template) + 1) % len(pool)]
    return post_type, template


def build_message(post_type, rng, template=None):
    """One template for this type, de-escaped, with the hashtag block appended."""
    template = template or rng.choice(tg.TEMPLATES[post_type])
    plain = to_plain(template).strip()
    if not plain:
        raise ValueError("template for %r de-escaped to nothing" % post_type)
    # A stray asterisk means to_plain() lost a marker Facebook would publish
    # literally — worth failing on in CI rather than on the Page.
    for marker in ("\\", "*", "||"):
        if marker in plain:
            log("⚠️  %r survived de-escaping in a %s template: %s"
                % (marker, post_type, plain[:80]))
    hashtags = tg.HASHTAGS.get(post_type, "#DocOga #NigerianProperty")
    return "%s\n\n%s" % (plain, hashtags)


def render_card(message, day, post_type, visual=None):
    """The day's copy as the brand card; None (text post) only if the render fails."""
    try:
        rel = social_card.card_for_post(message, day.isoformat(), post_type, "facebook",
                                        out_dir=ASSETS_DIR, visual=visual)
    except Exception as exc:  # a missing font or a Pillow regression must not lose the day
        log("⚠️  card render failed (%s: %s) — posting text only" % (type(exc).__name__, exc))
        return None
    size = os.path.getsize(rel)
    if not (MIN_PHOTO_BYTES <= size <= MAX_PHOTO_BYTES):
        log("⚠️  card is %d bytes — outside the upload window, posting text only" % size)
        return None
    return rel


def generate(day=None, write=True):
    """Return today's Facebook post, and (by default) write it to assets/."""
    day = day or datetime.now(LAGOS).date()
    rng = random.Random("docoga-facebook-%s" % day.isoformat())

    # The brain's pack for the day (tools/brain.py) is the voice when there is one;
    # the date-seeded rotation is the fallback, exactly as before.
    pack = brain_drafts.draft_for(day)
    promo = deepdive_promo.pack_for(day, "facebook")
    card_text = None
    if promo:
        # The day after a Deep-Dive goes public (tools/deepdive_promo.py, 17 Oct 2026): the post
        # is the episode. The YouTube link is a standalone line, so post_facebook.py moves it
        # to the first comment — a body link costs 60–80 % of the reach.
        post_type, message, visual, card_text = "deepdive", promo["text"], None, promo["card_text"]
        log("🎬 Deep-Dive feature day: %s" % promo["title"])
    elif pack:
        post_type = brain_drafts.post_type(pack)
        message = "%s\n\n%s" % (brain_drafts.tag_links(brain_drafts.post_text(pack), "facebook"), brain_drafts.hashtags(pack, "facebook"))
        visual = brain_drafts.visual(pack)
    else:
        post_type, template = pick(day)
        message = brain_drafts.tag_links(build_message(post_type, rng, template), "facebook")
        visual = None

    photo = render_card(card_text or message, day, post_type, visual) if write else None

    content = {
        "date": day.isoformat(),
        "day_of_week": day.weekday(),
        "day_name": day.strftime("%A"),
        "post_type": post_type,
        "message": message,
        "send_photo": bool(photo),
        "photo_path": photo,
        "generated_at": datetime.now(LAGOS).isoformat(),
        "source": "facebook",
        "brain": pack.get("theme") if pack else None,
    }

    if write:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("facebook_content_%s.json" % day.isoformat(), "facebook_content_latest.json"):
            with open(ASSETS_DIR / name, "w") as handle:
                json.dump(content, handle, indent=2)

    log(" Facebook content for %s — %s post, %d characters, photo=%s"
        % (day.isoformat(), post_type, len(message), photo or "none"))
    return content


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate DocOga's Facebook post for a day")
    parser.add_argument("--date", help="ISO date to generate for (default: today in Africa/Lagos)")
    parser.add_argument("--print", dest="show", action="store_true", help="print the message and exit")
    parser.add_argument("--no-write", action="store_true", help="do not touch assets/")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.date:
        day = date.fromisoformat(args.date)
    else:
        day = datetime.now(LAGOS).date()

    content = generate(day, write=not args.no_write)

    if args.show:
        print("\n── today's Facebook post ──────────────────────────────────────────")
        print(content["message"])
        print("──────────────────────────────────────────────────────────────────")
        print("photo: %s" % (content.get("photo_path") or "none (text post)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
