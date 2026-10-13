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
  2. **Pick an image Facebook can actually show.** `brand/official-logo-white.png`
     is in the Telegram set because Telegram is dark; on a white Facebook feed it
     is a blank card. So the list is separate and deliberate, and every candidate
     is checked for size before it is offered.
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

# Facebook renders photo posts on a light surface and crops to a 1:1 tile in the
# feed. `official-logo-white.png` (Telegram's hero image) is deliberately absent.
FB_PHOTO_IMAGES = [
    "brand/official-logo-transparent.png",
    "brand/logo-primary.png",
    "brand/logo-stamp.png",
    "brand/official-3.png",
    "brand/official-4.png",
    "brand/official-5.png",
    "brand/comparison.png",
    "brand/comparison-2.png",
]

# tools/fb_publish.py refuses a `source` upload above 4 MB; rejecting it here is
# a log line instead of an API error, and the post still goes out as text.
MAX_PHOTO_BYTES = 4 * 1024 * 1024
MIN_PHOTO_BYTES = 8 * 1024

# Photo posts carry the feed on Facebook far better than bare text, so the
# default leans that way — but the poster always has a text fallback.
PHOTO_ODDS = 6 / 7


def log(message):
    line = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message)
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as handle:
            handle.write(line + "\n")
    except OSError:
        pass  # logging must never be the reason a day's post fails


def available_photos():
    out = []
    for rel in FB_PHOTO_IMAGES:
        path = ROOT / rel
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if MIN_PHOTO_BYTES <= size <= MAX_PHOTO_BYTES:
            out.append(rel)
        else:
            log("⚠️  skipping %s (%d bytes — outside the %d KB…%d MB window)"
                % (rel, size, MIN_PHOTO_BYTES // 1024, MAX_PHOTO_BYTES // (1024 * 1024)))
    return out


def build_message(post_type, rng):
    """One template for this type, de-escaped, with the hashtag block appended."""
    template = rng.choice(tg.TEMPLATES[post_type])
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


def generate(day=None, write=True):
    """Return today's Facebook post, and (by default) write it to assets/."""
    day = day or datetime.now(LAGOS).date()
    rng = random.Random("docoga-facebook-%s" % day.isoformat())

    post_type = rng.choice(tg.WEEKLY_SCHEDULE.get(day.weekday(), ["promo"]))
    message = build_message(post_type, rng)

    photos = available_photos()
    want_photo = bool(photos) and rng.random() < PHOTO_ODDS
    photo = rng.choice(photos) if want_photo else None

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
