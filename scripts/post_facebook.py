#!/usr/bin/env python3
"""
DocOga Facebook auto-poster — one day's post, or a clear reason why not
======================================================================

Runs unattended from `.github/workflows/facebook_autopost.yml`, and by hand:

    python3 scripts/post_facebook.py --dry-run     # nothing is published
    python3 scripts/post_facebook.py               # today's post
    python3 scripts/post_facebook.py --force       # a second post today, on purpose

The failure-handling contract is inherited from the Telegram poster
(`scripts/post_telegram.py`), which was rewritten after four days of silent
failure in Oct 2026. In short:

  * **Never exit 0 having posted nothing.** Every path either publishes or
    returns non-zero with the API's own words, so a red run means a missing post.
  * **A bad image must not cost the day its words.** A rejected photo falls back
    to a text post, and the photo failure is still logged.
  * **A re-run must not double-post.** The guard asks Facebook (the Page's own
    feed) rather than trusting a file, because a runner's filesystem does not
    survive between runs. Skipping is exit 0 — a skipped day is not a failure,
    and a failure is what opens an issue.
  * **Both attempts' errors are printed.** Logging the first and discarding the
    retry's is exactly what made the October outage expensive to diagnose.

Configuration comes from `tools/fb_publish.py`: `FB_PAGE_ACCESS_TOKEN` and
`FB_PAGE_ID`, always as secrets, never as defaults in a file.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "tools", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import fb_publish  # noqa: E402  the Graph API layer
import generate_facebook_content  # noqa: E402  the copy

ASSETS_DIR = Path("assets/facebook")
LOG_FILE = Path("logs/social_media.log")
LAGOS = timezone(timedelta(hours=1))


def log(message):
    line = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message)
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as handle:
            handle.write(line + "\n")
    except OSError:
        pass  # logging is never the reason a post fails


def summary(line):
    """Append to the Actions step summary when running in Actions."""
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    try:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def load_today(day):
    """Today's content: the file the generator wrote, or generate it now.

    Reading the file (rather than always regenerating) is what keeps the poster
    and the generator two steps of one pipeline, exactly like Telegram's; and
    because generation is deterministic per date, a missing file cannot produce a
    different post than the one that was reviewed.
    """
    # Parenthesised: `Path / str % args` would apply the % to the PosixPath, which
    # is a TypeError the daily path only reaches when the generated file is read
    # back — i.e. only in production, and only when it matters. (Caught by
    # tools/tests/test_post_facebook.py.)
    path = ASSETS_DIR / ("facebook_content_%s.json" % day.isoformat())
    if path.exists():
        try:
            with open(path, encoding="utf-8") as handle:
                content = json.load(handle)
            if content.get("message"):
                return content, str(path.relative_to(ROOT))
            log("⚠️  %s has no message — regenerating" % path)
        except (ValueError, OSError) as exc:
            log("⚠️  could not read %s (%s) — regenerating" % (path, exc))
    return generate_facebook_content.generate(day), "generated in-process"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Post today's content to the DocOga Facebook Page")
    parser.add_argument("--date", help="ISO date to post for (default: today in Africa/Lagos)")
    parser.add_argument("--dry-run", action="store_true",
                        help="check credentials and posting rights; publish nothing")
    parser.add_argument("--force", action="store_true", help="post even if today is already taken")
    parser.add_argument("--text", help="override the generated copy (manual dispatch)")
    parser.add_argument("--photo-file", help="override the photo (path relative to the repo root)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    day = date.fromisoformat(args.date) if args.date else datetime.now(LAGOS).date()
    token, page_id = fb_publish.load_config()

    if args.dry_run:
        log("dry run — Graph API %s, Page id %s, token %s"
            % (fb_publish.API_VERSION, page_id, fb_publish.fingerprint(token)))
        ok, body = fb_publish.whoami(token, page_id)
        if not ok:
            print("❌ token or Page id rejected — %s" % body)
            return 3
        print("✅ Page reachable — %s" % (body or {}).get("name"))
        allowed, detail = fb_publish.write_permission_probe(token, page_id)
        print("%s posting rights: %s — %s" % ("✅" if allowed is True else "⚠️", allowed, detail))
        content, source = load_today(day)
        print("would post (%s): %s" % (source, content["message"][:160].replace("\n", " ⏎ ")))
        print("photo: %s" % (content.get("photo_path") or "none (text post)"))
        summary("| Facebook dry run | %s |" % ("✅ page reachable, rights: %s" % allowed))
        return 0

    if not (args.text or args.force):
        guard, detail = fb_publish.posted_on_date(token, page_id)
        if guard is True:
            print("⏭ skipped — the Page already has a post today (%s)." % detail)
            summary("| Facebook post %s | ⏭ skipped — already posted today |" % day.isoformat())
            return 0
        if guard is None:
            log("⚠️  the duplicate guard could not read the feed (%s) — continuing" % detail)

    if args.text:
        content = {"message": args.text, "send_photo": bool(args.photo_file),
                   "photo_path": args.photo_file, "post_type": "manual"}
    else:
        content, source = load_today(day)
        log("using %s" % source)

    message = content["message"]
    # An explicit --photo-file wins (that is the manual override); otherwise the
    # generator's decision is honoured, including its "no photo" answer.
    photo_rel = args.photo_file or (content.get("photo_path") if content.get("send_photo") else None)

    if photo_rel:
        photo_abs = photo_rel if os.path.isabs(photo_rel) else str(ROOT / photo_rel)
        ok, result = fb_publish.post_photo_file(token, page_id, photo_abs, message)
        if ok:
            print("✅ photo post published: %s" % result)
            summary("| Facebook post %s | ✅ published (photo) `%s` |" % (day.isoformat(), result))
            return 0
        log("❌ photo post refused — %s" % result)
        log("↩︎ falling back to a text post so the day is not lost")

    ok, result = fb_publish.post_text(token, page_id, message)
    if ok:
        print("✅ text post published: %s" % result)
        summary("| Facebook post %s | ✅ published (text) `%s` |" % (day.isoformat(), result))
        return 0

    print("❌ Facebook refused the post — %s" % result)
    summary("| Facebook post %s | ❌ failed — see the run log |" % day.isoformat())
    return 3


if __name__ == "__main__":
    sys.exit(main())
