#!/usr/bin/env python3
"""
DocOga Telegram Auto-Poster
Posts generated content to Telegram channel automatically.
Fully autonomous - runs on GitHub Actions or local cron.
"""

import os
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


def send_telegram_message(text, parse_mode="Markdown", disable_web_page_preview=None):
    """Send a text message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode
    }
    
    if disable_web_page_preview is not None:
        payload["disable_web_page_preview"] = disable_web_page_preview
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        if result.get("ok"):
            message_id = result.get("result", {}).get("message_id")
            log(f"✅ Telegram message sent! ID: {message_id}")
            return True, message_id
        else:
            log(f"❌ Telegram API error: {result.get('description', 'Unknown error')}")
            return False, None
    except requests.exceptions.RequestException as e:
        log(f"❌ Telegram request failed: {e}")
        return False, None


def send_telegram_photo(photo_path, caption=None, parse_mode="Markdown"):
    """Send a photo to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    if not os.path.exists(photo_path):
        log(f"❌ Photo file not found: {photo_path}")
        return False, None
    
    try:
        with open(photo_path, "rb") as photo_file:
            files = {"photo": photo_file}
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
            }
            if caption:
                data["caption"] = caption
                data["parse_mode"] = parse_mode
            
            response = requests.post(url, files=files, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get("ok"):
                message_id = result.get("result", {}).get("message_id")
                log(f"✅ Telegram photo sent! ID: {message_id}")
                return True, message_id
            else:
                log(f"❌ Telegram photo API error: {result.get('description', 'Unknown error')}")
                return False, None
    except Exception as e:
        log(f"❌ Telegram photo upload failed: {e}")
        return False, None


def load_content():
    """Load generated content from file"""
    content_file = ASSETS_DIR / "telegram_content_latest.json"
    
    if not content_file.exists():
        log("⚠️ No content file found. Generating fresh content...")
        # Import and run the generator
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
    """Main function: Post content to Telegram"""
    log("🚀 Starting Telegram posting...")
    
    # Validate credentials
    if not validate_credentials():
        log("❌ Cannot post: Missing credentials")
        return False
    
    # Load content
    posts = load_content()
    
    if not posts:
        log("❌ No content to post")
        return False
    
    # Post each message
    success_count = 0
    for i, post in enumerate(posts):
        log(f"\n📝 Posting message {i+1}/{len(posts)}...")
        
        message = post.get("message", "")
        post_type = post.get("post_type", "unknown")
        
        # For some post types, disable link preview
        disable_preview = post_type in ["promo", "urgent"]
        
        success, message_id = send_telegram_message(
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=disable_preview
        )
        
        if success:
            success_count += 1
            log(f"   ✅ Posted {post_type} message")
        else:
            log(f"   ❌ Failed to post {post_type} message")
    
    log(f"\n📊 Posting complete: {success_count}/{len(posts)} messages sent")
    return success_count > 0


def post_custom_message(message, parse_mode="Markdown"):
    """Post a custom message (for testing or manual use)"""
    if not validate_credentials():
        return False
    
    success, _ = send_telegram_message(
        text=message,
        parse_mode=parse_mode
    )
    return success


if __name__ == "__main__":
    # Run the auto-poster
    success = post_to_telegram()
    
    if success:
        log("✅ Telegram auto-posting completed successfully!")
        exit(0)
    else:
        log("❌ Telegram auto-posting failed!")
        exit(1)
