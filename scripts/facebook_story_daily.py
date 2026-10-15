#!/usr/bin/env python3
"""
DocOga Facebook Stories — the day's copy in the Stories tray, 2–3 times a day
=============================================================================

Owner, 15 Oct 2026: "Hope you know you are to post stories as well." Until then
Stories sat in FACEBOOK_AUTOMATION.md §8 under *not automated*. This is the lane.

What a Story is here
  * **photo Story** — the day's copy on the 9:16 brand frame
    (`social_card.story_for_post`: navy, Inter, kicker, type kept out of the
    bands Facebook covers with its own chrome).
  * **video Story** — on Reel days, the Reel that just published (≤ 60 s,
    already 9:16) goes to the tray too.

Slots (`--slot`), because a Story lives 24 h and the tray rewards cadence:
  morning    09:30 WAT, with the feed post — the post's own copy.
  afternoon  16:00 WAT (facebook_story_afternoon.yml) — the day's *other*
             rotation type (WEEKLY_SCHEDULE lists two per weekday), so the tray
             shows two different cards, not the same one twice.
  video      the Reel as a Story, straight after it publishes (Mon/Thu).

The guard reads the tray (`GET /{page}/stories`), never a file: a Story is live
for a day, so "how many did we post today" is a question the Page answers.
  morning   → skip if any photo Story exists today
  afternoon → skip if two or more photo Stories exist today
  video     → skip if a video Story exists today
`--force` posts regardless (a person asked).

Exit codes: 0 posted / skipped on purpose · 2 config · 3 Meta refused.
Usage:
    python3 scripts/facebook_story_daily.py --slot morning [--dry-run] [--force]
    python3 scripts/facebook_story_daily.py --slot afternoon
    python3 scripts/facebook_story_daily.py --slot video --video assets/videos/docoga_reel_20261016.mp4
    python3 scripts/facebook_story_daily.py --probe        # can this token open a story session?
"""

import argparse
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "tools", ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import fb_publish  # noqa: E402
import social_card  # noqa: E402
import generate_facebook_content as gen  # noqa: E402
import generate_telegram_content as tg  # noqa: E402
import docoga_log  # noqa: E402

LOG_FILE = docoga_log.log_file("social_media.log")
LAGOS = timezone(timedelta(hours=1))
ASSETS_DIR = Path("assets/facebook")
SLOTS = ("morning", "afternoon", "video")
MAX_PHOTO_STORIES = {"morning": 1, "afternoon": 2}


def log(message):
    line = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message)
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def summary(line):
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    try:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def stories_mode():
    """Repository variable FB_STORIES: on (default) / off."""
    return (os.environ.get("STORIES_MODE") or "on").strip().lower()


def copy_for(day, slot):
    """(message, post_type) for a slot. Morning = the post's copy; afternoon = the other type."""
    content = gen.generate(day, write=False)
    if slot != "afternoon":
        return content["message"], content["post_type"]
    options = list(tg.WEEKLY_SCHEDULE.get(day.weekday(), ["promo"]))
    others = [t for t in options if t != content["post_type"]] or options
    rng = random.Random("docoga-facebook-story-%s" % day.isoformat())
    post_type = rng.choice(others)
    return gen.build_message(post_type, rng), post_type


def render_story(day, slot):
    message, post_type = copy_for(day, slot)
    path = social_card.story_for_post(message, "%s-%s" % (day.isoformat(), slot), post_type,
                                      "facebook", out_dir=ASSETS_DIR)
    log("🖼  story frame (%s, %s): %s" % (slot, post_type, path))
    return path, post_type


def count_today(token, page_id, day):
    ok, hits = fb_publish.stories_today(token, page_id, when=day)
    if not ok:
        log("⚠️  the Stories guard could not read the tray (%s) — continuing" % hits)
        return None, None
    photos = sum(1 for h in hits if str(h.get("media_type", "")).lower() in ("photo", "image"))
    videos = sum(1 for h in hits if str(h.get("media_type", "")).lower() == "video")
    return photos, videos


def main(argv=None):
    parser = argparse.ArgumentParser(description="Post today's DocOga Story")
    parser.add_argument("--slot", choices=SLOTS, default="morning")
    parser.add_argument("--date", help="ISO date (default: today in Africa/Lagos)")
    parser.add_argument("--video", help=".mp4 for --slot video (the Reel that just published)")
    parser.add_argument("--dry-run", action="store_true", help="render the frame and probe the grant; publish nothing")
    parser.add_argument("--probe", action="store_true", help="only: can this token open a story session?")
    parser.add_argument("--force", action="store_true", help="post even if today's tray is already full")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    day = date.fromisoformat(args.date) if args.date else datetime.now(LAGOS).date()
    token, page_id = fb_publish.load_config()

    if args.probe:
        ok, detail = fb_publish.story_probe(token, page_id)
        print(("✅ " if ok else "❌ ") + str(detail))
        summary("| Stories probe %s | %s %s |" % (day.isoformat(), "✅" if ok else "❌", detail))
        return 0 if ok else 3

    if stories_mode() == "off":
        log("stories disabled (vars FB_STORIES=off) — nothing to do")
        summary("| Story %s (%s) | ⏭ disabled (FB_STORIES=off) |" % (day.isoformat(), args.slot))
        return 0

    if args.slot == "video":
        video = args.video
        if not video or not os.path.exists(video):
            log("❌ --slot video needs an existing --video file (got %r)" % video)
            return 2
        if not args.force and not args.dry_run:
            _, videos = count_today(token, page_id, day)
            if videos:
                log("⏭ a video Story is already in today's tray — skipping")
                summary("| Story %s (video) | ⏭ already in the tray |" % day.isoformat())
                return 0
        if args.dry_run:
            log("dry run: would post %s as a video Story" % video)
            return 0
        ok, detail = fb_publish.story_video(token, page_id, video, require_spec=False)
        if ok:
            print("✅ video Story published: %s" % detail)
            summary("| Story %s (video) | ✅ published `%s` |" % (day.isoformat(), detail.get("post_id") or detail.get("video_id")))
            return 0
        log("❌ video Story refused — %s" % detail)
        summary("| Story %s (video) | ❌ refused — %s |" % (day.isoformat(), detail))
        return 3

    frame, post_type = render_story(day, args.slot)
    if args.dry_run:
        ok, detail = fb_publish.story_probe(token, page_id)
        log(("✅ " if ok else "❌ ") + "stories grant: %s" % detail)
        summary("| Story %s (%s) | dry run — frame `%s`, grant %s |"
                % (day.isoformat(), args.slot, frame, "✅" if ok else "❌ " + str(detail)))
        return 0 if ok else 3
    if not args.force:
        photos, _ = count_today(token, page_id, day)
        if photos is not None and photos >= MAX_PHOTO_STORIES[args.slot]:
            log("⏭ today's tray already has %d photo Story(ies) — the %s slot stands down" % (photos, args.slot))
            summary("| Story %s (%s) | ⏭ tray already has %d |" % (day.isoformat(), args.slot, photos))
            return 0
    ok, detail = fb_publish.story_photo(token, page_id, frame)
    if ok:
        print("✅ photo Story published: %s" % detail)
        summary("| Story %s (%s, %s) | ✅ published `%s` |" % (day.isoformat(), args.slot, post_type, detail))
        return 0
    log("❌ photo Story refused — %s" % detail)
    summary("| Story %s (%s) | ❌ refused — %s |" % (day.isoformat(), args.slot, detail))
    return 3


if __name__ == "__main__":
    sys.exit(main())
