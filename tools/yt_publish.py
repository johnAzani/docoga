#!/usr/bin/env python3
"""
DocOga YouTube Publisher
========================
Uploads videos to the DocOga YouTube channel.

Requirements (GitHub Secrets):
  - YT_REFRESH_TOKEN  (OAuth refresh token)
  - YT_CLIENT_ID      (OAuth client ID)
  - YT_CLIENT_SECRET  (OAuth client secret)
  - YT_CHANNEL_ID     (optional, for reference)

Usage:
  python3 tools/yt_publish.py --video video.mp4 --title "Title" --description "Description"
  python3 tools/yt_publish.py --video video.mp4 --title "Title" --tags "law,tenant" --privacy public
"""
import os, sys, argparse
import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def get_access_token():
    """Get a fresh access token using the refresh token"""
    refresh_token = os.environ.get("YT_REFRESH_TOKEN")
    client_id = os.environ.get("YT_CLIENT_ID")
    client_secret = os.environ.get("YT_CLIENT_SECRET")
    
    if not all([refresh_token, client_id, client_secret]):
        print("ERROR: YT_REFRESH_TOKEN, YT_CLIENT_ID, YT_CLIENT_SECRET must be set")
        sys.exit(1)
    
    r = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })
    
    if r.status_code != 200:
        print(f"❌ Token refresh failed: {r.status_code} — {r.text[:300]}")
        sys.exit(1)
    
    return r.json()["access_token"]


def upload_video(video_path, title, description="", tags="", privacy="public", category_id="22"):
    """Upload a video to YouTube"""
    token = get_access_token()
    
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags else [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        }
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    # Step 1: Initiate resumable upload
    r = requests.post(
        f"{UPLOAD_URL}?uploadType=resumable&part=snippet,status",
        headers=headers,
        json=metadata,
    )
    
    if r.status_code != 200:
        print(f"❌ Upload initiation failed: {r.status_code} — {r.text[:300]}")
        return None
    
    upload_url = r.headers.get("Location")
    if not upload_url:
        print("❌ No upload URL returned")
        return None
    
    # Step 2: Upload the video file
    with open(video_path, "rb") as f:
        video_data = f.read()
    
    r = requests.put(
        upload_url,
        headers={"Content-Type": "video/mp4"},
        data=video_data,
    )
    
    if r.status_code == 200:
        video_id = r.json()["id"]
        print(f"✅ Video uploaded: https://youtube.com/watch?v={video_id}")
        return video_id
    else:
        print(f"❌ Upload failed: {r.status_code} — {r.text[:300]}")
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="DocOga YouTube Publisher")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    parser.add_argument("--category", default="22", help="YouTube category ID (22=People & Blogs)")
    
    args = parser.parse_args(argv)
    
    if not os.path.exists(args.video):
        print(f"❌ Video file not found: {args.video}")
        sys.exit(1)
    
    video_id = upload_video(
        args.video,
        args.title,
        args.description,
        args.tags,
        args.privacy,
        args.category,
    )
    if not video_id:
        print(
            "❌ Upload failed; exiting non-zero so queue workflows retain this item.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
