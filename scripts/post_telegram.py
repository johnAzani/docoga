#!/usr/bin/env python3
"""
DocOga Telegram Auto-Poster
Posts generated content to Telegram channel automatically.
Supports text posts and photo posts with captions.
Fully autonomous — runs on GitHub Actions or local cron.

Failure-handling contract (hardened 11 Oct 2026, after the four-day outage):
  1. Every Telegram rejection is logged with its HTTP status AND the API's
     `description`. The old code logged the first attempt's error and then
     discarded the retry's — which is why a failing post was diagnosable only
     by someone who could open the run log, and why nobody could tell whether
     the token, the chat or the message was at fault.
  2. A MarkdownV2 parse failure retries as plain text (markup stripped).
  3. A photo that cannot be sent falls back to a text post — a bad image must
     not cost the channel its daily post.
  4. The process still exits non-zero when nothing was posted, so the workflow
     can raise a visible issue.
"""

import hashlib
import os
import sys
import json
import requests
from datetime import date, datetime, timedelta
from pathlib import Path

# Shared escaper/stripper. tools/ is a sibling of scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from telegram_mdv2 import to_plain  # noqa: E402
import docoga_log  # noqa: E402  where the scratch files live
import telegram_preview  # noqa: E402  reads the channel's own public preview page
import youtube_ledger as ledger  # noqa: E402  — the same bookkeeping the Shorts and
# Reels lanes use, pointed at this lane's file. A forked ledger drifts.

REPO_ROOT = Path(__file__).resolve().parents[1]


# ===== CONFIG =====
# Absolute and rooted at the repo, like the ledger tool's own default: `logs/…`
# relative to the cwd works in CI (cwd happens to be the checkout) and writes a stray
# `logs/` directory wherever a human last cd'd to.
ASSETS_DIR = REPO_ROOT / "assets" / "telegram"
# Both paths are overridable, and the difference matters more than it looks. The log
# is gitignored scratch; the ledger is committed, because it is the only answer in the
# repo to "did this lane ever publish?". `python3 -m unittest` used to scribble 1,400
# lines into the real log file — the tests set TELEGRAM_LOG_FILE to a temp path now.
LOG_FILE = Path(os.getenv("TELEGRAM_LOG_FILE") or docoga_log.log_file("social_media.log"))
LEDGER_FILE = Path(os.getenv("TELEGRAM_LEDGER") or docoga_log.log_file("telegram_sent.json"))
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# What "already published" means: the same text (not merely the same day) inside this
# window. On 3 Oct 2026 the channel received the same caution-fee paragraph four times
# in four hours, because every retry and every manual dispatch started from zero
# knowledge. 7 days blocks the accident and still lets the rotation come back.
DUPLICATE_WINDOW_DAYS = int(os.getenv("TELEGRAM_DUP_WINDOW_DAYS", "7"))
FORCE = os.getenv("TELEGRAM_FORCE", "").lower() in ("1", "true", "yes")

# West Africa Time, the same clock the ledger tool stamps and the same one the
# "daily" cadence is promised on. Deriving the date in UTC would call a 00:30 Lagos
# post yesterday's, and a lane that posts at 08:00 UTC is on the same day either way.
WAT = timedelta(hours=1)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TELEGRAM_API = "https://api.telegram.org"

# Telegram limits: message text 4096 characters, photo caption 1024. Exceeding
# either is a hard "Bad Request" with no retry path, so both are clamped here.
MAX_MESSAGE_CHARS = 4096
MAX_CAPTION_CHARS = 1024

# Telegram's parse errors, in the shapes the API actually returns.
PARSE_ERROR_MARKERS = ("can't parse", "can't find end of", "unsupported start tag")

# ===== THE LIVE DUPLICATE GUARD =====
# The ledger refuses a duplicate only as well as the last successful commit did: a ledger
# push that failed, a fresh clone, a run from another branch — and the channel is free to
# receive the same paragraph twice again, which is the complaint that started this. The
# reading itself lives in tools/telegram_preview.py so the preflight and the poster cannot
# disagree about what "already on the channel" means; what stays here is the policy.
PREVIEW_PAGES = int(os.getenv("TELEGRAM_CHANNEL_GUARD_PAGES", "1"))
CHANNEL_GUARD_ENABLED = os.getenv("TELEGRAM_SKIP_CHANNEL_CHECK", "").lower() not in ("1", "true", "yes")
# A message shorter than this is not compared at all: a few words are far too easy to find
# inside somebody else's sentence, and refusing on that would silence the lane over a
# coincidence. The ledger still guards them, as it always did.
GUARD_MIN_CHARS = int(os.getenv("TELEGRAM_CHANNEL_GUARD_MIN", "24"))


def channel_duplicate(message):
    """(state, detail) for one outgoing message: clear | match | unavailable | skipped.

    Fail-open by design. A CDN blip, a private channel or a Telegram markup change must not
    cost the channel its daily post: this guard is an addition to the ledger, never a
    replacement for it, and never a reason for silence.
    """
    if not CHANNEL_GUARD_ENABLED:
        return "skipped", "TELEGRAM_SKIP_CHANNEL_CHECK is set — the ledger is the only guard"
    if not telegram_preview.channel_handle():
        return "skipped", "TELEGRAM_CHAT_ID is numeric, so the channel has no public preview to read"
    if len(telegram_preview.normalize_for_match(message)) < GUARD_MIN_CHARS:
        return "skipped", "the message is too short to compare safely"
    posts, error = telegram_preview.recent_posts(pages=PREVIEW_PAGES)
    if error:
        return "unavailable", error
    hit = telegram_preview.find(message, posts)
    if hit:
        channel, message_id = hit
        return "match", "t.me/%s/%d already carries this text" % (channel, message_id)
    return "clear", "%d recent channel post(s) checked, none of them this message" % len(posts)



def log(message):
    """Log messages to file and console.

    A missing or unwritable log must not cost the channel its post: this is the only
    place the file is opened, and it stays quiet on failure for that reason.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    print(log_msg, end="")
    docoga_log.append(LOG_FILE, log_msg)


def run_date():
    return (datetime.utcnow() + WAT).date()


def content_key(post_type, message):
    """Ledger title: the text's own fingerprint, not the date.

    `telegram photo 6f2c1a…`. Keying on the content is what catches the Oct 3 shape —
    the same paragraph posted four times in one afternoon — while leaving a legitimate
    re-use of a topic a week later alone. Keying on the date would have missed three of
    those four posts, because they came from four separate runs of the same file.
    """
    digest = hashlib.sha1((message or "").strip().encode("utf-8")).hexdigest()[:10]
    return "telegram %s %s" % (post_type or "text", digest)


def channel_link(message_id):
    """A URL that outlives the run log. For a public channel, the real permalink;
    otherwise the id itself, which is still answerable from the Bot API."""
    if message_id is None:
        return ""
    username = os.getenv("TELEGRAM_CHANNEL_USERNAME") or ""
    if not username and str(TELEGRAM_CHAT_ID or "").startswith("@"):
        username = str(TELEGRAM_CHAT_ID)[1:]
    if username:
        return "https://t.me/%s/%s" % (username, message_id)
    return "https://t.me/telegram-message-id/%s" % message_id


def _clamp(text, limit, label):
    """Trim to Telegram's limit, saying so — never fail on length alone."""
    if len(text) <= limit:
        return text
    log(f"⚠️ {label} is {len(text)} characters; Telegram's limit is {limit} — trimmed.")
    return text[: limit - 1].rstrip() + "…"


def _describe(response):
    """Return 'HTTP 400 — <Telegram's own words>' for any API response."""
    try:
        body = response.json()
        description = body.get("description") or body.get("error_description")
    except ValueError:
        description = (response.text or "").strip()[:300] or "no response body"
    if not description:
        description = "no description in response"
    return f"HTTP {response.status_code} — {description}"


def _is_parse_error(description):
    return any(marker in (description or "").lower() for marker in PARSE_ERROR_MARKERS)


def validate_credentials():
    """Check if Telegram credentials are set"""
    if not TELEGRAM_BOT_TOKEN:
        log("❌ TELEGRAM_BOT_TOKEN not set!")
        return False
    if not TELEGRAM_CHAT_ID:
        log("❌ TELEGRAM_CHAT_ID not set!")
        return False
    return True


def send_text_message(text, parse_mode="MarkdownV2"):
    """Send a text-only message to Telegram.

    Returns True if the message reached the channel, by any route.
    """
    url = f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = _clamp(text, MAX_MESSAGE_CHARS, "message")

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }

    try:
        r = requests.post(url, json=payload, timeout=30)
        result = r.json()
        if result.get("ok"):
            msg_id = result["result"].get("message_id")
            log(f"✅ Text message sent (id={msg_id})")
            # The id, not True: the ledger needs the permalink, and an id of 0 would
            # be falsy only in theory — Telegram starts counting at 1.
            return msg_id or True

        description = result.get("description", "Unknown error")
        log(f"❌ Telegram API error: {_describe(r)}")

        # Fallback to plain text if Markdown parsing failed.
        if _is_parse_error(description):
            log("⚠️ Markdown parse failed, retrying as plain text...")
            payload.pop("parse_mode", None)
            payload["text"] = _clamp(to_plain(text), MAX_MESSAGE_CHARS, "plain message")
            r2 = requests.post(url, json=payload, timeout=30)
            r2_result = r2.json()
            if r2_result.get("ok"):
                log("✅ Sent as plain text fallback")
                return (r2_result.get("result") or {}).get("message_id") or True
            # The old code threw this error away. It is the one that says what
            # is really wrong (token, chat rights, payload), so it is logged.
            log(f"❌ Plain-text retry also failed: {_describe(r2)}")
        return False
    except requests.exceptions.RequestException as e:
        log(f"❌ Request failed: {e}")
        return False


def send_photo_message(photo_path, caption=None, parse_mode="MarkdownV2"):
    """Send a photo with optional caption to Telegram.

    If the photo cannot be sent for any reason — a parse error, an unsupported
    image, an upload failure — the caption is posted as a text message instead,
    so the channel still gets its daily post.
    """
    url = f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    if not os.path.exists(photo_path):
        log(f"❌ Photo not found: {photo_path}")
        if caption:
            log("⚠️ Falling back to text-only post")
            return send_text_message(caption, parse_mode)
        return False

    caption = _clamp(caption, MAX_CAPTION_CHARS, "caption") if caption else caption

    try:
        data = {"chat_id": TELEGRAM_CHAT_ID}
        if caption:
            data["caption"] = caption
            data["parse_mode"] = parse_mode

        with open(photo_path, "rb") as photo:
            files = {"photo": photo}
            r = requests.post(url, data=data, files=files, timeout=60)

        result = r.json()
        if result.get("ok"):
            msg_id = result["result"].get("message_id")
            log(f"✅ Photo message sent (id={msg_id})")
            return msg_id or True

        description = result.get("description", "Unknown error")
        log(f"❌ Photo API error: {_describe(r)}")

        # Retry with the caption as plain text if the failure was the markup.
        if _is_parse_error(description):
            log("⚠️ Caption parse failed, retrying plain...")
            data.pop("parse_mode", None)
            if caption:
                data["caption"] = _clamp(
                    to_plain(caption), MAX_CAPTION_CHARS, "plain caption"
                )
            with open(photo_path, "rb") as photo:
                files = {"photo": photo}
                r2 = requests.post(url, data=data, files=files, timeout=60)
            r2_result = r2.json()
            if r2_result.get("ok"):
                log("✅ Photo sent with plain caption")
                return (r2_result.get("result") or {}).get("message_id") or True
            log(f"❌ Plain-caption retry also failed: {_describe(r2)}")

        # Not a markup problem, or the plain retry failed too: post the words.
        if caption:
            log("⚠️ Photo could not be sent — falling back to a text post")
            return send_text_message(caption, parse_mode)
        return False
    except requests.exceptions.RequestException as e:
        log(f"❌ Photo upload failed: {e}")
        if caption:
            log("⚠️ Falling back to a text post")
            return send_text_message(caption, parse_mode)
        return False


def load_content():
    """Load generated content from file"""
    content_file = ASSETS_DIR / "telegram_content_latest.json"

    if not content_file.exists():
        log("⚠️ No content file found — generating fresh content...")
        sys.path.insert(0, str(Path(__file__).parent))
        from generate_telegram_content import generate_daily_content

        content = generate_daily_content()
        return [content]

    try:
        with open(content_file) as f:
            data = json.load(f)
            return data.get("posts", [data])
    except Exception as e:
        log(f"❌ Failed to load content: {e}")
        return []


def already_sent(entries, key, on_date):
    """The ledger's own rule, wrapped so this file has one opinion about duplicates."""
    return ledger.already_published(entries, key, on_date, DUPLICATE_WINDOW_DAYS)


def post_to_telegram():
    """Main function: generate and post content to Telegram.

    Returns the number of messages that reached the channel. The ledger is consulted
    before each send and written after it, which is the whole duplicate fix: a retry, a
    second dispatch, or an operator re-running yesterday's file now costs the channel
    nothing it has already carried. `TELEGRAM_FORCE=1` overrides, and says so in the
    log, because the override has to exist for the day the ledger is the thing that is
    wrong.
    """
    global FORCE
    if "--force" in sys.argv:
        FORCE = True
    log("\U0001f680 Starting Telegram auto-post...")

    if not validate_credentials():
        log("❌ Cannot post — missing credentials")
        return -1

    posts = load_content()
    if not posts:
        log("❌ No content to post")
        return -1

    today = run_date()
    entries = ledger.load(str(LEDGER_FILE))
    if entries:
        log("   ledger: %d previous publish(es), newest %s"
            % (len(entries), entries[0].get("date") or entries[0].get("recorded_at") or "?"))
    else:
        log("   ledger: empty (%s) \u2014 every post today counts as new" % LEDGER_FILE)

    sent = 0
    skipped = 0
    failed = 0
    guard_states = []
    for i, post in enumerate(posts):
        log("\n\U0001f4dd Posting message %d/%d..." % (i + 1, len(posts)))

        message = post.get("message", "")
        post_type = post.get("post_type", "unknown")
        send_photo = post.get("send_photo", False)
        photo_path = post.get("photo_path")

        key = content_key(post_type, message)
        duplicate = already_sent(entries, key, today)
        if duplicate and not FORCE:
            skipped += 1
            log("   \u26a0\ufe0f Skipped \u2014 this exact text is already in the ledger (%s, %s). "
                "Set TELEGRAM_FORCE=1 or pass --force to post it again."
                % (duplicate.get("date", "undated"), duplicate.get("url") or "no url"))
            continue
        if duplicate and FORCE:
            log("   \u26a0\ufe0f force is on: re-posting %s, already recorded on %s"
                % (key, duplicate.get("date")))

        # The live guard runs *after* the ledger, which is free and offline, and *before*
        # anything is sent. A "match" is the refusal the ledger would have made had it been
        # told; "unavailable" only logs, because an unreadable page must not cost the post.
        guard_state, guard_detail = channel_duplicate(message)
        guard_states.append(guard_state)
        if guard_state == "match" and not FORCE:
            skipped += 1
            log("   \u23ed Skipped — %s. The channel is the authority, so this is refused even "
                "though the ledger never saw it." % guard_detail)
            continue
        if guard_state == "match":
            log("   \u26a0\ufe0f force is on: re-posting text the channel already carries (%s)"
                % guard_detail)
        elif guard_state in ("unavailable", "skipped") and i == 0:
            log("   \u2139\ufe0f live channel guard %s — %s. The ledger is guarding this run."
                % (guard_state, guard_detail))

        if send_photo and photo_path:
            ok = send_photo_message(photo_path, caption=message)
        else:
            ok = send_text_message(message)

        if ok:
            sent += 1
            log("   \u2705 Posted %s message" % post_type)
            message_id = ok if isinstance(ok, int) else None
            # Re-read before writing: a second lane sharing this file (or a re-run that
            # got as far as recording) must not have its entries dropped by a stale list.
            entries = ledger.load(str(LEDGER_FILE))
            ledger.record(
                entries,
                path=str(LEDGER_FILE),
                title=key,
                topic=post_type or "text",
                # The content key, not (date, index): `record` de-duplicates by
                # video_id, so an index would overwrite a different post's entry on the
                # same day — which is how "2 entries" quietly became 1.
                video_id=key,
                url=channel_link(message_id),
                date=today.isoformat(),
                run_id=os.getenv("GITHUB_RUN_ID", ""),
                privacy="channel",
                characters=len(message or ""),
                chat=str(TELEGRAM_CHAT_ID or ""),
            )
        else:
            failed += 1
            log("   \u274c Failed to post %s message" % post_type)

    log("\n\U0001f4ca Complete: %d sent, %d already published, %d refused, %d in the file"
        % (sent, skipped, failed, len(posts)))
    # Machine-readable for the workflow, in the same style as the reel lane's
    # REEL_VIDEO_ID line: the steps after this one read the log, and a lane that has to
    # re-parse prose gets it wrong on the day the prose changes.
    print("TELEGRAM_SENT=%d" % sent)
    print("TELEGRAM_SKIPPED=%d" % skipped)
    print("TELEGRAM_FAILED=%d" % failed)
    print("TELEGRAM_LEDGER=%s" % LEDGER_FILE)
    # One word for the run summary, so "the guard was watching" and "the guard could not read
    # the channel" are never again the same-looking green run.
    if "match" in guard_states:
        print("TELEGRAM_CHANNEL_GUARD=refused-a-duplicate")
    elif "clear" in guard_states:
        print("TELEGRAM_CHANNEL_GUARD=live")
    elif "unavailable" in guard_states:
        print("TELEGRAM_CHANNEL_GUARD=unavailable")
    else:
        print("TELEGRAM_CHANNEL_GUARD=%s" % (guard_states[0] if guard_states else "none"))
    # Three outcomes, not two. "Already published" is the lane working; "Telegram
    # refused everything" is the four-day outage, and it has to be red even though
    # `sent == 0` in both cases. Collapsing them is how a poster used to exit 0 on an
    # API error, which is the sentence this whole file exists to make impossible.
    if sent == 0 and failed:
        return -1
    return sent


if __name__ == "__main__":
    result = post_to_telegram()
    if result > 0:
        log("✅ Telegram auto-posting completed successfully!")
        sys.exit(0)
    if result == 0:
        # Nothing went out and nothing was wrong: every post in the file is already on
        # the channel. Exiting 1 here would open a failure issue for a lane that is
        # working; exiting 0 in silence would hide a content file that went empty.
        log("\u2139\ufe0f Nothing posted — the ledger or the channel already has today's content.")
        sys.exit(0)
    log("❌ Telegram auto-posting failed!")
    sys.exit(1)
