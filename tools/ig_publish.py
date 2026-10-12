#!/usr/bin/env python3
"""
DocOga Instagram Publisher — Reels, Carousels, Photos
=====================================================
Publishes content to Instagram via the Graph API.

Requirements (stored in GitHub Secrets):
  - IG_ACCESS_TOKEN  (long-lived, 60-day, refreshed automatically)
  - IG_USER_ID       (numeric Instagram user ID)
  - META_APP_ID      (from Meta Developer Dashboard)
  - META_APP_SECRET  (from Meta Developer Dashboard)

Usage:
  python3 tools/ig_publish.py --reel social/reel-stakes-final.mp4 --caption "Your caption" --cover social/reel-stakes-cover.jpg
  python3 tools/ig_publish.py --photo social/status-oct3.jpg --caption "Your caption"
  python3 tools/ig_publish.py --carousel social/slide1.jpg social/slide2.jpg --caption "Your caption"
"""
import os, sys, time, argparse, json
import requests

# ── Configuration ──
# One constant for the whole Meta surface, and it is overridable from a repository
# variable because Meta sunsets a Graph API version roughly every two years:
# v21.0 (this file's original pin) goes away on 21 Jan 2027, and v26.0 has been
# current since 29 Jul 2026. A version buried in a dozen f-strings is a migration
# you find out about from a failing post.
API_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
BASE = f"https://graph.facebook.com/{API_VERSION}"
INSTAGRAM_BASE = f"https://graph.instagram.com/{API_VERSION}"

def get_config():
    """Load config from environment or GitHub Secrets"""
    token = os.environ.get("IG_ACCESS_TOKEN")
    user_id = os.environ.get("IG_USER_ID")
    app_id = os.environ.get("META_APP_ID")
    app_secret = os.environ.get("META_APP_SECRET")

    if not all([token, user_id]):
        print("ERROR: IG_ACCESS_TOKEN and IG_USER_ID must be set in environment")
        print("Add them as GitHub Secrets or export them locally")
        sys.exit(1)

    return token, user_id, app_id, app_secret


def refresh_token(token, app_id, app_secret):
    """Refresh long-lived token (valid 60 days, refresh before expiry)"""
    if not app_id or not app_secret:
        print("WARNING: Cannot refresh token without META_APP_ID and META_APP_SECRET")
        return token

    r = requests.get(f"{BASE}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": token,
    })

    if r.status_code == 200:
        new_token = r.json().get("access_token", token)
        print(f"Token refreshed successfully (valid 60 days)")
        return new_token
    else:
        print(f"Token refresh failed: {r.status_code} — {r.text[:200]}")
        return token


def check_quota(user_id, token):
    """Check daily publishing quota"""
    r = requests.get(f"{BASE}/{user_id}/content_publishing_limit", params={
        "fields": "config,quota_usage",
        "access_token": token,
    })

    if r.status_code == 200:
        data = r.json().get("data", [{}])[0]
        usage = data.get("quota_usage", 0)
        total = data.get("config", {}).get("quota_total", 100)
        print(f"Publishing quota: {usage}/{total}")
        return usage < total
    else:
        print(f"Quota check failed: {r.status_code}")
        return True  # Assume OK if check fails


def upload_video_for_reel(video_path, token):
    """Upload video using resumable upload API (required for Reels)"""
    # Get file size
    file_size = os.path.getsize(video_path)
    print(f"Uploading video ({file_size / 1024 / 1024:.1f} MB)...")

    # Step 1: Start upload session
    r = requests.post(f"https://rupload.facebook.com/media/{API_VERSION}", headers={
        "Authorization": f"OAuth {token}",
        "offset": "0",
        "file_size": str(file_size),
    })

    if r.status_code != 200:
        print(f"Upload session failed: {r.status_code} — {r.text[:200]}")
        return None

    upload_id = r.json().get("id")
    if not upload_id:
        print(f"No upload ID returned: {r.text[:200]}")
        return None

    # Step 2: Upload file
    with open(video_path, "rb") as f:
        r = requests.post(f"https://rupload.facebook.com/media/{API_VERSION}/{upload_id}", headers={
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(file_size),
        }, data=f)

    if r.status_code != 200:
        print(f"Upload failed: {r.status_code} — {r.text[:200]}")
        return None

    print(f"Video uploaded successfully (ID: {upload_id})")
    return upload_id


def create_reel_container(user_id, video_url, caption, cover_url, token):
    """Create a Reel container"""
    body = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": token,
    }
    if cover_url:
        body["cover_url"] = cover_url

    r = requests.post(f"{BASE}/{user_id}/media", data=body)

    if r.status_code == 200:
        container_id = r.json()["id"]
        print(f"Reel container created: {container_id}")
        return container_id
    else:
        print(f"Container creation failed: {r.status_code} — {r.text[:200]}")
        return None


def create_photo_container(user_id, image_url, caption, token):
    """Create a photo container"""
    r = requests.post(f"{BASE}/{user_id}/media", data={
        "image_url": image_url,
        "caption": caption,
        "access_token": token,
    })

    if r.status_code == 200:
        container_id = r.json()["id"]
        print(f"Photo container created: {container_id}")
        return container_id
    else:
        print(f"Container creation failed: {r.status_code} — {r.text[:200]}")
        return None


def create_carousel_container(user_id, image_urls, caption, token):
    """Create a carousel container (2-10 items)"""
    child_ids = []

    for i, url in enumerate(image_urls):
        r = requests.post(f"{BASE}/{user_id}/media", data={
            "image_url": url,
            "is_carousel_item": "true",
            "access_token": token,
        })

        if r.status_code == 200:
            child_id = r.json()["id"]
            child_ids.append(child_id)
            print(f"  Carousel item {i+1}/{len(image_urls)}: {child_id}")
        else:
            print(f"  Carousel item {i+1} failed: {r.status_code} — {r.text[:200]}")
            return None

    # Create carousel container
    r = requests.post(f"{BASE}/{user_id}/media", data={
        "media_type": "CAROUSEL",
        "caption": caption,
        "children": ",".join(child_ids),
        "access_token": token,
    })

    if r.status_code == 200:
        container_id = r.json()["id"]
        print(f"Carousel container created: {container_id}")
        return container_id
    else:
        print(f"Carousel container failed: {r.status_code} — {r.text[:200]}")
        return None


def wait_for_processing(container_id, token, timeout=600):
    """Poll until container is ready to publish"""
    print("Waiting for processing...")
    deadline = time.time() + timeout
    delay = 10

    while time.time() < deadline:
        r = requests.get(f"{BASE}/{container_id}", params={
            "fields": "status_code",
            "access_token": token,
        })

        if r.status_code == 200:
            status = r.json().get("status_code")
            print(f"  Status: {status}")

            if status == "FINISHED":
                return True
            elif status in ("ERROR", "EXPIRED"):
                print(f"  Container failed: {status}")
                return False
        else:
            print(f"  Status check failed: {r.status_code}")

        time.sleep(delay)
        delay = min(delay * 1.5, 60)

    print("  Timeout waiting for processing")
    return False


def publish_container(container_id, user_id, token):
    """Publish a processed container"""
    r = requests.post(f"{BASE}/{user_id}/media_publish", data={
        "creation_id": container_id,
        "access_token": token,
    })

    if r.status_code == 200:
        media_id = r.json()["id"]
        print(f"✅ Published! Media ID: {media_id}")
        print(f"   https://www.instagram.com/p/{media_id}/")
        return media_id
    else:
        print(f"❌ Publish failed: {r.status_code} — {r.text[:200]}")
        return None


def publish_reel(video_url, caption, cover_url=None, token=None, user_id=None):
    """Publish a Reel to Instagram"""
    print(f"\n📤 Publishing Reel...")
    print(f"   Video: {video_url}")
    print(f"   Caption: {caption[:80]}...")

    # Check quota
    if not check_quota(user_id, token):
        print("❌ Daily quota exhausted. Try again tomorrow.")
        return None

    # Create container
    container_id = create_reel_container(user_id, video_url, caption, cover_url, token)
    if not container_id:
        return None

    # Wait for processing
    if not wait_for_processing(container_id, token):
        return None

    # Publish
    return publish_container(container_id, user_id, token)


def publish_photo(image_url, caption, token=None, user_id=None):
    """Publish a photo to Instagram"""
    print(f"\n📤 Publishing Photo...")
    print(f"   Image: {image_url}")

    if not check_quota(user_id, token):
        print("❌ Daily quota exhausted.")
        return None

    container_id = create_photo_container(user_id, image_url, caption, token)
    if not container_id:
        return None

    # Photos process fast, but poll just in case
    time.sleep(5)
    return publish_container(container_id, user_id, token)


def publish_carousel(image_urls, caption, token=None, user_id=None):
    """Publish a carousel to Instagram (2-10 items)"""
    print(f"\n📤 Publishing Carousel ({len(image_urls)} items)...")

    if not check_quota(user_id, token):
        print("❌ Daily quota exhausted.")
        return None

    container_id = create_carousel_container(user_id, image_urls, caption, token)
    if not container_id:
        return None

    time.sleep(10)
    return publish_container(container_id, user_id, token)


def main():
    parser = argparse.ArgumentParser(description="DocOga Instagram Publisher")
    parser.add_argument("--reel", help="Path to Reel video file")
    parser.add_argument("--photo", help="Path to photo file")
    parser.add_argument("--carousel", nargs="+", help="Paths to carousel images (2-10)")
    parser.add_argument("--caption", required=True, help="Post caption")
    parser.add_argument("--cover", help="Path to Reel cover image")
    parser.add_argument("--video-url", help="Public URL to video (for Reels)")
    parser.add_argument("--image-url", help="Public URL to image (for photos)")
    parser.add_argument("--image-urls", nargs="+", help="Public URLs to images (for carousels)")
    parser.add_argument("--refresh-token", action="store_true", help="Refresh the access token")

    args = parser.parse_args()

    # Load config
    token, user_id, app_id, app_secret = get_config()

    # Refresh token if requested
    if args.refresh_token:
        token = refresh_token(token, app_id, app_secret)
        print(f"New token: {token[:20]}...")
        return

    # Publish based on type
    if args.reel or args.video_url:
        video_url = args.video_url
        if not video_url and args.reel:
            print("ERROR: --video-url is required for Reels (must be publicly accessible)")
            print("Upload the video to a CDN first, then pass the URL")
            sys.exit(1)
        publish_reel(video_url, args.caption, args.cover, token, user_id)

    elif args.photo or args.image_url:
        image_url = args.image_url
        if not image_url and args.photo:
            print("ERROR: --image-url is required (must be publicly accessible)")
            sys.exit(1)
        publish_photo(image_url, args.caption, token, user_id)

    elif args.carousel or args.image_urls:
        image_urls = args.image_urls or []
        if not image_urls and args.carousel:
            print("ERROR: --image-urls is required (must be publicly accessible)")
            sys.exit(1)
        publish_carousel(image_urls, args.caption, token, user_id)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()