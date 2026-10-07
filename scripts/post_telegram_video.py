#!/usr/bin/env python3
"""
DocOga Telegram Video Poster
Posts generated short-form videos to Telegram channel.
"""

import os
import sys
import json
import requests
from datetime import datetime
from pathlib import Path

# ===== CONFIG =====
ASSETS_DIR = Path("assets/videos")
LOG_FILE = Path("logs/social_media.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    print(log_msg, end="")
    with open(LOG_FILE, "a") as f:
        f.write(log_msg)


def validate_credentials():
    if not TELEGRAM_BOT_TOKEN:
        log("❌ TELEGRAM_BOT_TOKEN not set!")
        return False
    if not TELEGRAM_CHAT_ID:
        log("❌ TELEGRAM_CHAT_ID not set!")
        return False
    log(f"✅ Credentials loaded")
    return True


def send_video(video_path, caption=""):
    """Send a video to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"

    if not os.path.exists(video_path):
        log(f"❌ Video not found: {video_path}")
        return False, None

    file_size = os.path.getsize(video_path)
    log(f"📹 Sending video: {video_path} ({file_size / 1024:.1f} KB)")

    # Telegram limit: 50MB for videos
    if file_size > 50 * 1024 * 1024:
        log(f"❌ Video too large ({file_size / 1024 / 1024:.1f} MB). Max 50MB.")
        return False, None

    try:
        with open(video_path, "rb") as video_file:
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "Markdown",
                "supports_streaming": "true",
            }
            response = requests.post(
                url,
                data=data,
                files={"video": video_file},
                timeout=120,
            )
            response.raise_for_status()

        result = response.json()
        if result.get("ok"):
            message_id = result.get("result", {}).get("message_id")
            log(f"✅ Video sent! Message ID: {message_id}")
            return True, message_id
        else:
            log(f"❌ Telegram API error: {result.get('description', 'Unknown')}")
            return False, None
    except Exception as e:
        log(f"❌ Video upload failed: {type(e).__name__}: {e}")
        return False, None


def send_gif(gif_path, caption=""):
    """Send a GIF/animation to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAnimation"

    if not os.path.exists(gif_path):
        log(f"❌ GIF not found: {gif_path}")
        return False, None

    file_size = os.path.getsize(gif_path)
    log(f"🎞️ Sending animation: {gif_path} ({file_size / 1024:.1f} KB)")

    try:
        with open(gif_path, "rb") as gif_file:
            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "Markdown",
            }
            response = requests.post(
                url,
                data=data,
                files={"animation": gif_file},
                timeout=120,
            )
            response.raise_for_status()

        result = response.json()
        if result.get("ok"):
            message_id = result.get("result", {}).get("message_id")
            log(f"✅ Animation sent! Message ID: {message_id}")
            return True, message_id
        else:
            log(f"❌ Telegram API error: {result.get('description', 'Unknown')}")
            return False, None
    except Exception as e:
        log(f"❌ Animation upload failed: {type(e).__name__}: {e}")
        return False, None


def get_latest_video():
    """Find the latest generated video or GIF"""
    if not ASSETS_DIR.exists():
        log(f"❌ Videos directory not found: {ASSETS_DIR}")
        return None

    # Look for MP4 first, then GIF
    mp4_files = sorted(ASSETS_DIR.glob("docoga_short_*.mp4"), reverse=True)
    if mp4_files:
        return str(mp4_files[0])

    gif_files = sorted(ASSETS_DIR.glob("video_*.gif"), reverse=True)
    if gif_files:
        return str(gif_files[0])

    log("❌ No video files found")
    return None


def post_video():
    """Main function: Generate and post video"""
    log("🎬 Starting Telegram video posting...")

    if not validate_credentials():
        sys.exit(1)

    # Generate video
    log("🎥 Generating video...")
    try:
        from generate_short_video import generate_video
        video_path, title = generate_video()
        log(f"✅ Video generated: {title}")
    except Exception as e:
        log(f"❌ Video generation failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if not video_path or not os.path.exists(video_path):
        log("❌ No video generated")
        sys.exit(1)

    # Create caption
    caption = f"🎬 *{title}*\n\n📋 Get proper documents at docoga.com.ng\n🔔 Follow @docogadaily for daily tips!"

    # Send to Telegram
    ext = Path(video_path).suffix.lower()
    if ext == ".mp4":
        success, msg_id = send_video(video_path, caption)
    else:
        success, msg_id = send_gif(video_path, caption)

    if success:
        log(f"✅ Video posted successfully!")
        return True
    else:
        log(f"❌ Video posting failed")
        return False


if __name__ == "__main__":
    try:
        success = post_video()
        sys.exit(0 if success else 1)
    except Exception as e:
        log(f"❌ Fatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)