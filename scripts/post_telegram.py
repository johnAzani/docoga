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

import os
import sys
import json
import requests
from datetime import datetime
from pathlib import Path

# Shared escaper/stripper. tools/ is a sibling of scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from telegram_mdv2 import to_plain  # noqa: E402

# ===== CONFIG =====
ASSETS_DIR = Path("assets/telegram")
LOG_FILE = Path("logs/social_media.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

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


def log(message):
    """Log messages to file and console"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    print(log_msg, end="")
    with open(LOG_FILE, "a") as f:
        f.write(log_msg)


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
            return True

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
                return True
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
            return True

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
                return True
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


def post_to_telegram():
    """Main function: generate and post content to Telegram"""
    log("🚀 Starting Telegram auto-post...")

    if not validate_credentials():
        log("❌ Cannot post — missing credentials")
        return False

    posts = load_content()
    if not posts:
        log("❌ No content to post")
        return False

    success_count = 0
    for i, post in enumerate(posts):
        log(f"\n📝 Posting message {i + 1}/{len(posts)}...")

        message = post.get("message", "")
        post_type = post.get("post_type", "unknown")
        send_photo = post.get("send_photo", False)
        photo_path = post.get("photo_path")

        if send_photo and photo_path:
            ok = send_photo_message(photo_path, caption=message)
        else:
            ok = send_text_message(message)

        if ok:
            success_count += 1
            log(f"   ✅ Posted {post_type} message")
        else:
            log(f"   ❌ Failed to post {post_type} message")

    log(f"\n📊 Complete: {success_count}/{len(posts)} messages sent")
    return success_count > 0


if __name__ == "__main__":
    success = post_to_telegram()
    if success:
        log("✅ Telegram auto-posting completed successfully!")
        sys.exit(0)
    else:
        log("❌ Telegram auto-posting failed!")
        sys.exit(1)
