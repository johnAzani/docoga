#!/usr/bin/env python3
"""telegram_video.py — put the day's Short in the Telegram channel as a native video (₦0).

Telegram counts views on the file it hosts, autoplays it in the channel and lets readers
forward it — a YouTube link gets a preview card and a tap-away. Bot API `sendVideo` takes a
multipart upload up to 50 MB; a Short is 3–8 MB. Over the limit (or on any refusal) the lane
falls back to `sendMessage` with the YouTube link, so the channel never misses the Short.

    python3 tools/telegram_video.py --video out/short.mp4 --title "…" --url https://youtube.com/shorts/…
Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Exit 0 always; machine line TELEGRAM_VIDEO=sent|link|skipped|failed.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

API = "https://api.telegram.org/bot%s/%s"
MAX_BYTES = 50 * 1024 * 1024
TIMEOUT = (10, 180)
SITE = "https://docoga.com.ng/?s=tg"


def caption_for(title, url, parent_url="", parent_title=""):
    """The Short's caption. `parent_url` (17 Oct 2026, owner: promote the Deep-Dives everywhere)
    names the nine-minute episode this Short trails, so the channel's video post is a trailer
    with its feature attached, not a dead end."""
    title = (title or "").strip().replace(" #Shorts", "")
    lines = [title] if title else []
    if parent_url:
        lines.append("▶ The full Deep-Dive (9 min)%s: %s" % ((" — " + parent_title.strip()) if parent_title.strip() else "", parent_url))
    lines.append("Free Nigerian tenancy documents: %s" % SITE)
    if url:
        lines.append("Watch on YouTube: %s" % url)
    return "\n\n".join(lines)[:1024]          # Telegram's caption limit


def send(token, chat_id, video, title, url, post=None, parent_url="", parent_title=""):
    """→ (state, detail). state ∈ sent | link | failed."""
    post = post or requests.post
    caption = caption_for(title, url, parent_url, parent_title)
    path = Path(video) if video else None
    if path and path.is_file() and path.stat().st_size <= MAX_BYTES:
        try:
            with path.open("rb") as fh:
                r = post(API % (token, "sendVideo"),
                         data={"chat_id": chat_id, "caption": caption, "supports_streaming": "true"},
                         files={"video": (path.name, fh, "video/mp4")}, timeout=TIMEOUT)
            body = r.json() if r.content else {}
            if r.status_code == 200 and body.get("ok"):
                return "sent", "message %s" % (body.get("result") or {}).get("message_id")
            reason = str(body.get("description") or r.status_code)[:160]
        except (requests.RequestException, ValueError) as exc:
            reason = "%s: %s" % (type(exc).__name__, str(exc)[:120])
    elif path and path.is_file():
        reason = "file is %d MB, over Telegram's 50 MB bot limit" % (path.stat().st_size // (1024 * 1024))
    else:
        reason = "no video file at %s" % video
    if not url:
        return "failed", reason
    try:
        r = post(API % (token, "sendMessage"), data={"chat_id": chat_id, "text": caption}, timeout=TIMEOUT)
        body = r.json() if r.content else {}
        if r.status_code == 200 and body.get("ok"):
            return "link", "video not sent (%s) — posted the YouTube link instead" % reason
        return "failed", "%s; link post refused: %s" % (reason, str(body.get("description") or r.status_code)[:120])
    except (requests.RequestException, ValueError) as exc:
        return "failed", "%s; link post failed: %s" % (reason, type(exc).__name__)


def main(argv=None):
    ap = argparse.ArgumentParser(description="post a Short to the Telegram channel as a native video")
    ap.add_argument("--video", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--url", default="", help="the YouTube URL (fallback text and the caption's last line)")
    ap.add_argument("--parent-url", default="", help="the Deep-Dive this Short trails (its link rides in the caption)")
    ap.add_argument("--parent-title", default="")
    a = ap.parse_args(argv)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("TELEGRAM_VIDEO=skipped")
        print("Telegram secrets not present in this job — the Short stays on YouTube only.")
        return 0
    state, detail = send(token, chat_id, a.video, a.title, a.url, parent_url=a.parent_url, parent_title=a.parent_title)
    detail = detail.replace(token, "<token>")
    if state == "failed":
        print("::warning title=Telegram video not posted::%s" % detail)
    else:
        print("Telegram: %s — %s" % (state, detail))
    print("TELEGRAM_VIDEO=%s" % state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
