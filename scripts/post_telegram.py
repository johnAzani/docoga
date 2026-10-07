#!/usr/bin/env python3
"""
DocOga Telegram Auto-Poster
Posts generated content to Telegram channel automatically.
Supports text posts and photo posts with captions.
Fully autonomous — runs on GitHub Actions or local cron.
"""

import os
import sys
import json
import requests
from datetime import datetime
from pathlib import Path

# ===== CONFIG =====
ASSETS_DIR = Path("assets/telegram")
LOG_FILE = Path("logs/social_media.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TELEGRAM_API = "https://api.telegram.org"


def log(message):
    """Log messages to file and console"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    print(log_msg, end="")
    with open(LOG_FILE, "a") as f:
        f.write(log_msg)


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
    """Send a text-only message to Telegram"""
    url = f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

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
        else:
            desc = result.get("description", "Unknown error")
            log(f"❌ Telegram API error: {desc}")
            # Fallback to plain text if Markdown fails
            if "can't parse" in desc.lower():
                log("⚠️ Markdown parse failed, retrying as plain text...")
                payload.pop("parse_mode")
                # Strip markdown characters for plain text fallback
                plain = text.replace("\\", "").replace("*", "")
                payload["text"] = plain
                r2 = requests.post(url, json=payload, timeout=30)
                r2_result = r2.json()
                if r2_result.get("ok"):
                    log("✅ Sent as plain text fallback")
                    return True
            return False
    except requests.exceptions.RequestException as e:
        log(f"❌ Request failed: {e}")
        return False


def send_photo_message(photo_path, caption=None, parse_mode="MarkdownV2"):
    """Send a photo with optional caption to Telegram"""
    url = f"{TELEGRAM_API}/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    if not os.path.exists(photo_path):
        log(f"❌ Photo not found: {photo_path}")
        # Fall back to text-only
        if caption:
            log("⚠️ Falling back to text-only post")
            return send_text_message(caption, parse_mode)
        return False

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
        else:
            desc = result.get("description", "Unknown error")
            log(f"❌ Photo API error: {desc}")
            # Fallback: retry without parse mode
            if "can't parse" in desc.lower():
                log("⚠️ Caption parse failed, retrying plain...")
                data.pop("parse_mode", None)
                if caption:
                    plain = caption.replace("\\", "").replace("*", "")
                    data["caption"] = plain
                with open(photo_path, "rb") as photo:
                    files = {"photo": photo}
                    r2 = requests.post(url, data=data, files=files, timeout=60)
                if r2.json().get("ok"):
                    log("✅ Photo sent with plain caption")
                    return True
            return False
    except requests.exceptions.RequestException as e:
        log(f"❌ Photo upload failed: {e}")
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
