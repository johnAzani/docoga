#!/usr/bin/env python3
"""
Shorts → Deep-Dive linking. Every Short is a trailer for one long-form episode;
this module answers "which episode, and where does it live on YouTube?"

Why (14 Oct 2026, first stats snapshot): the Shorts collect the views (108 on
the best one) while the long-forms sit at 0–2. Nothing pointed a Short viewer
at the episode it was cut from. Now each rotation topic names a `parent`:

    "parent": "dd3"             — a Deep-Dive lane episode (episodes/dd3/episode.json);
                                  resolved through logs/youtube_longform.json, so the
                                  link appears the moment the episode is published and
                                  is simply absent before that.
    "parent": "yt:08wCJ0EmTkU"  — a legacy long-form already on the channel.

`parent_link(parent)` returns (title, url) or None. Callers put the link in the
description; the same text is offered as a pinned-comment suggestion (posting
comments needs the youtube.force-ssl scope the uploader token does not hold).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LONGFORM_LEDGER = ROOT / "logs" / "youtube_longform.json"
EPISODES_DIR = ROOT / "episodes"
STATS_LOG = ROOT / "logs" / "youtube_stats.json"

WATCH = "https://www.youtube.com/watch?v=%s"
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def episode_title(episode_id, episodes_dir=EPISODES_DIR):
    ep = _load(Path(episodes_dir) / episode_id / "episode.json")
    if not ep:
        return None
    return (ep.get("youtube") or {}).get("title") or ep.get("title")


def published_episode(episode_id, ledger=LONGFORM_LEDGER, episodes_dir=EPISODES_DIR):
    """(title, url) of the newest *uploaded* ledger entry for a lane episode, else None."""
    title = episode_title(episode_id, episodes_dir)
    if not title:
        return None
    entries = _load(ledger) or []
    for e in entries:  # the ledger is newest-first; a re-published copy wins
        if e.get("title") == title and e.get("video_id") and e.get("state", "uploaded") != "failed":
            return title, e.get("url") or WATCH % e["video_id"]
    return None


def legacy_title(video_id, stats_log=STATS_LOG):
    snaps = _load(stats_log) or []
    if isinstance(snaps, dict):
        snaps = [snaps]
    for snap in reversed(snaps):
        for v in snap.get("videos") or []:
            if (v.get("video_id") or v.get("id")) == video_id and v.get("title"):
                return v["title"]
    return None


def parent_link(parent, ledger=LONGFORM_LEDGER, episodes_dir=EPISODES_DIR, stats_log=STATS_LOG):
    """Resolve a rotation topic's `parent` to (title, url); None when it is not on YouTube yet."""
    if not parent:
        return None
    parent = str(parent).strip()
    if parent.startswith("yt:"):
        vid = parent[3:]
        if not _VIDEO_ID.match(vid):
            raise ValueError("parent %r is not yt:<11-char video id>" % parent)
        return (legacy_title(vid, stats_log) or "The full Deep-Dive"), WATCH % vid
    if not (Path(episodes_dir) / parent / "episode.json").is_file():
        raise ValueError("parent %r is neither a Deep-Dive episode folder nor yt:<video id>" % parent)
    return published_episode(parent, ledger, episodes_dir)


def description_block(link):
    """The lines a Short's description carries for its parent (empty when unpublished)."""
    if not link:
        return ""
    title, url = link
    return "Watch the full Deep-Dive — %s:\n%s\n\n" % (title, url)


def pinned_comment(link):
    if not link:
        return ""
    title, url = link
    return "Full episode (free, 9 minutes): %s — %s" % (title, url)


if __name__ == "__main__":  # pragma: no cover — tiny CLI for the workflow log
    import sys
    for p in sys.argv[1:] or ["dd2", "dd3"]:
        print(p, "->", parent_link(p))
