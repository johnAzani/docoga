#!/usr/bin/env python3
"""Set a YouTube video's custom thumbnail — the one call tools/yt_publish.py does not make.

Usage: python3 tools/yt_thumbnail.py --video-id ID --image build/deepdive/dd2/dd2-cover.jpg

Uses the same credentials and transport as yt_publish.py (YT_REFRESH_TOKEN /
YT_CLIENT_ID / YT_CLIENT_SECRET). thumbnails.set costs ~50 quota units and needs
the channel to be verified for custom thumbnails; when it is not, YouTube answers
403 `forbidden` and this exits 2 with that said in plain words — the video is
already up, so a thumbnail failure must never fail the publish.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yt_publish  # noqa: E402

THUMB_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
MAX_BYTES = 2 * 1024 * 1024


def set_thumbnail(video_id, image_path, http=None):
    image_path = Path(image_path)
    if not image_path.is_file():
        return False, "thumbnail file missing: %s" % image_path
    if image_path.stat().st_size > MAX_BYTES:
        return False, "thumbnail is %d bytes; YouTube's limit is 2 MB" % image_path.stat().st_size
    http, _ = yt_publish.authorize(http)
    with open(image_path, "rb") as fh:
        r = http.request("POST", THUMB_URL, params={"videoId": video_id, "uploadType": "media"},
                         headers={"Content-Type": "image/jpeg"}, data=fh.read())
    if r.status_code == 200:
        return True, "thumbnail set"
    kind, reason, what, action, _ = yt_publish.classify(r.status_code, r.text)
    if r.status_code == 403:
        return False, ("YouTube refused the custom thumbnail (HTTP 403 %s). Custom thumbnails need a "
                       "verified channel: YouTube Studio → Settings → Channel → Feature eligibility → "
                       "verify by phone. The video is published; set the thumbnail by hand this time."
                       % (reason or "forbidden"))
    return False, "thumbnail failed: HTTP %s — %s" % (r.status_code, (r.text or "")[:200])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Set a YouTube custom thumbnail")
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--image", required=True)
    args = ap.parse_args(argv)
    try:
        ok, msg = set_thumbnail(args.video_id, args.image)
    except yt_publish.Problem as p:
        print("YT_THUMBNAIL=failed")
        print("::warning title=Thumbnail not set::%s" % p.what)
        return 2
    print("YT_THUMBNAIL=%s" % ("set" if ok else "failed"))
    print(("✅ " if ok else "::warning title=Thumbnail not set::") + msg)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
