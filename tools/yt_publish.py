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
        # The 9 Oct 2026 failure was this one. It is worth naming precisely,
        # because "refresh token" and "client" are different repairs:
        #   invalid_client / "The OAuth client was not found" -> the OAuth client
        #     itself is gone from the Cloud project. No amount of re-issuing a
        #     refresh token helps; the client must be recreated and all three
        #     secrets replaced together.
        #   invalid_grant -> the refresh token was revoked or has expired.
        body = r.text.lower()
        if "invalid_client" in body or "oauth client was not found" in body:
            print(
                "   ↳ The OAuth *client* no longer exists in the Google Cloud project "
                "('invalid_client'). Re-create the OAuth client and update "
                "YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN together — "
                "the upload cannot work until then."
            )
        elif "invalid_grant" in body:
            print(
                "   ↳ The refresh token was revoked or expired ('invalid_grant'). "
                "Re-run the one-time OAuth flow and update YT_REFRESH_TOKEN."
            )
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
    parser.add_argument("--video", help="Path to video file")
    parser.add_argument("--title", help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    parser.add_argument("--category", default="22", help="YouTube category ID (22=People & Blogs)")
    # Cheap credential check for the scheduled workflow: prove a token can be
    # minted before spending ten minutes rendering a video that cannot be
    # uploaded. Exists because the 9 Oct run rendered, then failed at the wire.
    parser.add_argument(
        "--check-token",
        action="store_true",
        help="Only verify that the OAuth credentials can mint a token, then exit",
    )
    
    args = parser.parse_args(argv)
    
    if args.check_token:
        get_access_token()  # exits 1, naming the cause, if the credentials are dead
        print("✅ OAuth credentials are usable — a token was minted.")
        return 0
    
    if not args.video or not args.title:
        parser.error("--video and --title are required (or use --check-token)")
    
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

    # Machine-readable id for the scheduled workflow's publish ledger. The
    # human line above stays first for anyone reading the run log.
    print(f"VIDEO_ID={video_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
