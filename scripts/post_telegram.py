#!/usr/bin/env python3
"""
DocOga Telegram Auto-Poster
Posts generated content to Telegram channel automatically.
Sends photo posts with DocOga branding for maximum engagement.
Fully autonomous - runs on GitHub Actions or local cron.
"""

import os
import sys
import json
import random
import requests
from datetime import datetime
from pathlib import Path

# ===== CONFIG =====
ASSETS_DIR = Path("assets/telegram")
BRAND_DIR = Path("brand")
LOG_FILE = Path("logs/social_media.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Primary DocOga logo for photo posts
PRIMARY_LOGO = "brand/official-logo-white.png"

# Additional brand images for variety (used on some days)
BRAND_IMAGES = [
    "brand/official-logo-white.png",
    "brand/official-logo-transparent.png",
    "brand/official-3.png",
    "brand/official-4.png",
    "brand/official-5.png",
    "brand/comparison.png",
    "brand/comparison-2.png",
]

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


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
    log(f"✅ Credentials loaded: BOT_TOKEN={TELEGRAM_BOT_TOKEN[:5]}..., CHAT_ID={TELEGRAM_CHAT_ID}")
    return True


def send_telegram_photo(photo_path, caption):
    """Send a photo with caption to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    if not os.path.exists(photo_path):
        log(f"❌ Photo not found: {photo_path}")
        return False, None

    try:
        with open(photo_path, "rb") as photo:
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "Markdown",
            }
            response = requests.post(url, data=data, files={"photo": photo}, timeout=30)
            response.raise_for_status()

        result = response.json()
        if result.get("ok"):
            message_id = result.get("result", {}).get("message_id")
            log(f"✅ Photo post sent! Message ID: {message_id}")
            return True, message_id
        else:
            log(f"❌ Telegram API error: {result.get('description', 'Unknown error')}")
            return False, None
    except Exception as e:
        log(f"❌ Photo upload failed: {type(e).__name__}: {e}")
        return False, None


def send_telegram_message(text, parse_mode="Markdown", disable_web_page_preview=None):
    """Send a text message to Telegram (fallback)"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }

    if disable_web_page_preview is not None:
        payload["disable_web_page_preview"] = disable_web_page_preview

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        if result.get("ok"):
            message_id = result.get("result", {}).get("message_id")
            log(f"✅ Text message sent! ID: {message_id}")
            return True, message_id
        else:
            log(f"❌ Telegram API error: {result.get('description', 'Unknown error')}")
            return False, None
    except Exception as e:
        log(f"❌ Telegram request failed: {type(e).__name__}: {e}")
        return False, None


def pick_brand_image():
    """Pick brand image — primary logo 80% of the time, variety 20%"""
    # 80% chance: use the official DocOga logo
    # 20% chance: use a different brand image for variety
    if os.path.exists(PRIMARY_LOGO) and random.random() < 0.8:
        log(f"📸 Using primary logo: {PRIMARY_LOGO}")
        return PRIMARY_LOGO
    
    available = [img for img in BRAND_IMAGES if os.path.exists(img) and img != PRIMARY_LOGO]
    if available:
        chosen = random.choice(available)
        log(f"📸 Using variety image: {chosen}")
        return chosen
    
    # Fallback to primary logo
    if os.path.exists(PRIMARY_LOGO):
        log(f"📸 Fallback to primary logo: {PRIMARY_LOGO}")
        return PRIMARY_LOGO
    
    log("⚠️ No brand images found, falling back to text post")
    return None


def load_content():
    """Load generated content from file"""
    content_file = ASSETS_DIR / "telegram_content_latest.json"

    if not content_file.exists():
        log("⚠️ No content file found. Generating fresh content...")
        try:
            from scripts.generate_telegram_content import generate_daily_content
            content = generate_daily_content()
            return [content]
        except Exception as e:
            log(f"❌ Failed to generate content: {e}")
            return []

    try:
        with open(content_file) as f:
            data = json.load(f)
            return data.get("posts", [data])
    except Exception as e:
        log(f"❌ Failed to load content: {e}")
        return []


def post_to_telegram():
    """Main function: Post content to Telegram with photos"""
    log("🚀 Starting Telegram posting...")

    # Validate credentials
    if not validate_credentials():
        log("❌ Cannot post: Missing credentials")
        sys.exit(1)

    # Load content
    posts = load_content()

    if not posts:
        log("❌ No content to post")
        sys.exit(1)

    # Post each message with a brand photo
    success_count = 0
    for i, post in enumerate(posts):
        log(f"\n📝 Posting message {i+1}/{len(posts)}...")

        message = post.get("message", "")
        post_type = post.get("post_type", "unknown")

        # Pick a brand image for this post
        image_path = pick_brand_image()

        if image_path:
            # Send as photo post with caption
            success, message_id = send_telegram_photo(image_path, message)
        else:
            # Fallback to text-only post
            disable_preview = post_type in ["promo", "urgent"]
            success, message_id = send_telegram_message(
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=disable_preview,
            )

        if success:
            success_count += 1
            log(f"   ✅ Posted {post_type} {'photo' if image_path else 'text'} message")
        else:
            log(f"   ❌ Failed to post {post_type} message")

    log(f"\n📊 Posting complete: {success_count}/{len(posts)} messages sent")
    return success_count > 0


if __name__ == "__main__":
    try:
        success = post_to_telegram()
        if success:
            log("✅ Telegram auto-posting completed successfully!")
            sys.exit(0)
        else:
            log("❌ Telegram auto-posting failed!")
            sys.exit(1)
    except Exception as e:
        log(f"❌ Fatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)