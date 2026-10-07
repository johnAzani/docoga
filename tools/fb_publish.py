#!/usr/bin/env python3
"""
DocOga Facebook Page Publisher
==============================
Publishes text, photos, and videos to the DocOga Facebook Page.

Requirements (GitHub Secrets):
  - FB_PAGE_ACCESS_TOKEN  (long-lived Page Access Token)
  - FB_PAGE_ID            (102466208923830)

Usage:
  python3 tools/fb_publish.py --text "Your post message"
  python3 tools/fb_publish.py --photo-url "https://example.com/image.jpg" --text "Caption"
  python3 tools/fb_publish.py --video-url "https://example.com/video.mp4" --text "Caption"
"""
import os, sys, argparse
import requests

BASE = "https://graph.facebook.com/v21.0"

def get_config():
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    page_id = os.environ.get("FB_PAGE_ID", "102466208923830")
    if not token:
        print("ERROR: FB_PAGE_ACCESS_TOKEN must be set")
        sys.exit(1)
    return token, page_id


def post_text(token, page_id, message):
    """Publish a text post to the Page"""
    r = requests.post(f"{BASE}/{page_id}/feed", data={
        "message": message,
        "access_token": token,
    })
    if r.status_code == 200:
        post_id = r.json()["id"]
        print(f"✅ Text post published: {post_id}")
        return post_id
    else:
        print(f"❌ Failed: {r.status_code} — {r.text[:300]}")
        return None


def post_photo(token, page_id, image_url, message=""):
    """Publish a photo to the Page"""
    r = requests.post(f"{BASE}/{page_id}/photos", data={
        "url": image_url,
        "message": message,
        "access_token": token,
    })
    if r.status_code == 200:
        post_id = r.json().get("id", r.json().get("post_id"))
        print(f"✅ Photo published: {post_id}")
        return post_id
    else:
        print(f"❌ Failed: {r.status_code} — {r.text[:300]}")
        return None


def post_video(token, page_id, video_url, title="", description=""):
    """Publish a video to the Page"""
    r = requests.post(f"{BASE}/{page_id}/videos", data={
        "file_url": video_url,
        "title": title,
        "description": description,
        "access_token": token,
    })
    if r.status_code == 200:
        video_id = r.json()["id"]
        print(f"✅ Video published: {video_id}")
        return video_id
    else:
        print(f"❌ Failed: {r.status_code} — {r.text[:300]}")
        return None


def refresh_token(token, app_id, app_secret):
    """Refresh long-lived token"""
    r = requests.get(f"{BASE}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": token,
    })
    if r.status_code == 200:
        new_token = r.json().get("access_token", token)
        print(f"Token refreshed: {new_token[:30]}...")
        return new_token
    else:
        print(f"Refresh failed: {r.status_code}")
        return token


def main():
    parser = argparse.ArgumentParser(description="DocOga Facebook Page Publisher")
    parser.add_argument("--text", help="Text message to post")
    parser.add_argument("--photo-url", help="Public URL to image")
    parser.add_argument("--video-url", help="Public URL to video")
    parser.add_argument("--title", default="", help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--refresh-token", action="store_true")

    args = parser.parse_args()
    token, page_id = get_config()

    if args.refresh_token:
        app_id = os.environ.get("META_APP_ID", "4401202890209558")
        app_secret = os.environ.get("META_APP_SECRET", "7dbde4fe1f4fd004748153ff93c17b31")
        refresh_token(token, app_id, app_secret)
        return

    if args.video_url:
        post_video(token, page_id, args.video_url, args.title, args.text or args.description)
    elif args.photo_url:
        post_photo(token, page_id, args.photo_url, args.text or "")
    elif args.text:
        post_text(token, page_id, args.text)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()