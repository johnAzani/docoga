#!/usr/bin/env python3
"""Pull the DocOga channel's YouTube numbers so decisions are made on data, not memory.

Two sources, used in order of what the credentials allow:

  1. YouTube Data API v3 (`youtube.readonly` — the scope the uploader already has):
     channel totals + per-video views / likes / comments / duration / privacy for every
     video the lane has published (both ledgers) plus the latest uploads on the channel.
  2. YouTube Analytics API (`yt-analytics.readonly` — needs one extra consent):
     per-video watch time, average view duration, average % viewed, impressions and
     click-through, traffic sources, subscribers gained. When the token lacks the scope the
     report says so in plain words and everything from source 1 still lands.

Output
  logs/youtube_stats.json        append-only snapshots (one per run) — the record
  docs/YOUTUBE_PERFORMANCE.md    the latest snapshot as a readable table + deltas vs the previous

Exit codes: 0 ok · 2 credentials/no channel · 1 anything else. Never touches a video.
"""

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import yt_publish  # noqa: E402

LEDGERS = (ROOT / "logs" / "youtube_published.json", ROOT / "logs" / "youtube_longform.json")
STATS = ROOT / "logs" / "youtube_stats.json"
REPORT = ROOT / "docs" / "YOUTUBE_PERFORMANCE.md"
DATA = "https://www.googleapis.com/youtube/v3"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
ANALYTICS_METRICS = ("views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
                     "subscribersGained,likes,comments,shares")
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"


def iso_duration_seconds(s):
    """PT1H2M3S → 3723. The Data API's only duration format."""
    import re
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def ledger_ids():
    out = {}
    for path in LEDGERS:
        if not path.is_file():
            continue
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        lane = "short" if path.name == "youtube_published.json" else "longform"
        for e in entries:
            vid = e.get("video_id")
            if vid:
                out[vid] = {"lane": lane, "title": e.get("title", ""), "published": e.get("date", ""),
                            "topic": e.get("topic", "")}
    return out


def get_json(http, url, params):
    r = http.request("GET", url, params=params)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": (r.text or "")[:300]}
    return r.status_code, body


def channel_snapshot(http):
    status, body = get_json(http, DATA + "/channels", {"part": "snippet,statistics,contentDetails", "mine": "true"})
    if status != 200 or not body.get("items"):
        return None, "channels.list → HTTP %s %s" % (status, json.dumps(body)[:200])
    ch = body["items"][0]
    st = ch.get("statistics", {})
    return {
        "id": ch["id"], "title": ch["snippet"]["title"],
        "subscribers": int(st.get("subscriberCount", 0)), "views": int(st.get("viewCount", 0)),
        "videos": int(st.get("videoCount", 0)),
        "uploads_playlist": ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads"),
    }, None


def recent_upload_ids(http, playlist, limit=50):
    if not playlist:
        return []
    status, body = get_json(http, DATA + "/playlistItems",
                            {"part": "contentDetails", "playlistId": playlist, "maxResults": min(limit, 50)})
    if status != 200:
        return []
    return [i["contentDetails"]["videoId"] for i in body.get("items", [])]


def video_rows(http, ids):
    rows = {}
    ids = list(dict.fromkeys(ids))
    for k in range(0, len(ids), 50):
        chunk = ids[k:k + 50]
        status, body = get_json(http, DATA + "/videos",
                                {"part": "snippet,statistics,contentDetails,status", "id": ",".join(chunk)})
        if status != 200:
            continue
        for v in body.get("items", []):
            st = v.get("statistics", {})
            secs = iso_duration_seconds(v.get("contentDetails", {}).get("duration"))
            rows[v["id"]] = {
                "id": v["id"], "title": v["snippet"]["title"], "published_at": v["snippet"].get("publishedAt", ""),
                "privacy": v.get("status", {}).get("privacyStatus", ""), "seconds": secs,
                "kind": "short" if secs and secs <= 180 and secs > 0 else "longform",
                "views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
            }
    return rows


def analytics_rows(http, channel_id, ids, start, end):
    """Per-video analytics; returns (rows_by_id, note). A 403 means the scope is missing."""
    if not ids:
        return {}, None
    params = {"ids": "channel==%s" % channel_id, "startDate": start, "endDate": end,
              "metrics": ANALYTICS_METRICS, "dimensions": "video",
              "filters": "video==%s" % ",".join(ids[:200]), "sort": "-views"}
    status, body = get_json(http, ANALYTICS, params)
    if status == 403:
        return {}, ("analytics: the token lacks %s — the Data API numbers above are complete; "
                    "re-consent with that scope to add watch time, retention and impressions" % ANALYTICS_SCOPE)
    if status != 200:
        return {}, "analytics: HTTP %s %s" % (status, json.dumps(body)[:160])
    cols = [c["name"] for c in body.get("columnHeaders", [])]
    out = {}
    for row in body.get("rows", []):
        rec = dict(zip(cols, row))
        out[rec.pop("video")] = rec
    # traffic sources for the channel as a whole (one cheap call)
    status, body = get_json(http, ANALYTICS, {"ids": "channel==%s" % channel_id, "startDate": start, "endDate": end,
                                              "metrics": "views", "dimensions": "insightTrafficSourceType",
                                              "sort": "-views"})
    traffic = {}
    if status == 200:
        for src, views in body.get("rows", []):
            traffic[src] = views
    return {"videos": out, "traffic": traffic}, None


def snapshot(http=None, days=28, now=None):
    http, _ = yt_publish.authorize(http)
    now = now or dt.datetime.now(dt.timezone(dt.timedelta(hours=1)))
    ch, err = channel_snapshot(http)
    if err:
        raise yt_publish.Problem("forbidden", "channel", err, "Check the YouTube secrets / channel.", 2)
    ledger = ledger_ids()
    ids = list(ledger) + recent_upload_ids(http, ch.get("uploads_playlist"))
    rows = video_rows(http, ids)
    for vid, meta in ledger.items():
        if vid in rows:
            rows[vid]["lane"] = meta["lane"]
            rows[vid]["topic"] = meta["topic"]
    end = now.date().isoformat()
    start = (now.date() - dt.timedelta(days=days)).isoformat()
    an, note = analytics_rows(http, ch["id"], list(rows), start, end)
    if an:
        for vid, rec in an.get("videos", {}).items():
            if vid in rows:
                rows[vid]["analytics"] = rec
    snap = {
        "taken_at": now.isoformat(timespec="seconds"), "window_days": days,
        "channel": {k: v for k, v in ch.items() if k != "uploads_playlist"},
        "videos": sorted(rows.values(), key=lambda r: r.get("published_at", ""), reverse=True),
        "traffic": an.get("traffic", {}) if an else {},
        "analytics_note": note,
    }
    return snap


def load_stats():
    if STATS.is_file():
        try:
            return json.loads(STATS.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return []


def save_snapshot(snap, keep=120):
    history = load_stats()
    history.append(snap)
    history = history[-keep:]
    STATS.parent.mkdir(parents=True, exist_ok=True)
    STATS.write_text(json.dumps(history, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return history


def fmt_secs(s):
    s = int(s or 0)
    return "%d:%02d" % (s // 60, s % 60)


def render_report(history):
    snap = history[-1]
    prev = history[-2] if len(history) > 1 else None
    prev_videos = {v["id"]: v for v in prev["videos"]} if prev else {}
    ch = snap["channel"]
    lines = ["# DocOga on YouTube — performance", "",
             "_Auto-generated by `tools/yt_stats.py` (weekly + on demand). Latest snapshot: **%s**; window for "
             "analytics metrics: last %d days. Read this before deciding what to make next._" % (snap["taken_at"], snap["window_days"]),
             "", "## Channel", "", "| | now | since last snapshot |", "|---|---:|---:|"]
    for key, label in (("subscribers", "Subscribers"), ("views", "Total views"), ("videos", "Videos")):
        d = (ch[key] - prev["channel"][key]) if prev else None
        lines.append("| %s | %s | %s |" % (label, format(ch[key], ","), ("%+d" % d) if d is not None else "—"))
    lines += ["", "## Videos", ""]
    has_an = any("analytics" in v for v in snap["videos"])
    head = "| Published | Kind | Title | Privacy | Length | Views | Δ | Likes | Comments"
    head += " | Avg view | % viewed | Min watched | Subs |" if has_an else " |"
    lines.append(head)
    lines.append("|---|---|---|---|---:|---:|---:|---:|---:|" + ("---:|---:|---:|---:|" if has_an else ""))
    for v in snap["videos"]:
        pv = prev_videos.get(v["id"])
        delta = ("%+d" % (v["views"] - pv["views"])) if pv else "new"
        row = "| %s | %s | [%s](https://www.youtube.com/watch?v=%s) | %s | %s | %s | %s | %s | %s" % (
            (v.get("published_at") or "")[:10], v.get("lane") or v["kind"], v["title"].replace("|", "¦")[:70],
            v["id"], v["privacy"], fmt_secs(v["seconds"]), format(v["views"], ","), delta, v["likes"], v["comments"])
        if has_an:
            a = v.get("analytics", {})
            row += " | %s | %s | %s | %s" % (fmt_secs(a.get("averageViewDuration")) if a else "—",
                                             ("%.0f%%" % a["averageViewPercentage"]) if a.get("averageViewPercentage") is not None else "—",
                                             format(int(a.get("estimatedMinutesWatched", 0)), ",") if a else "—",
                                             a.get("subscribersGained", "—") if a else "—")
        lines.append(row + " |")
    if snap.get("traffic"):
        lines += ["", "## Where views came from (last %d days)" % snap["window_days"], "", "| Source | Views |", "|---|---:|"]
        for src, views in sorted(snap["traffic"].items(), key=lambda kv: -kv[1]):
            lines.append("| %s | %s |" % (src, views))
    lines += ["", "## Reading the numbers", ""]
    shorts = [v for v in snap["videos"] if (v.get("lane") or v["kind"]) == "short"]
    longs = [v for v in snap["videos"] if (v.get("lane") or v["kind"]) == "longform"]
    if shorts:
        best = max(shorts, key=lambda v: v["views"])
        lines.append("- Best Short so far: **%s** (%s views). The Shorts lane's hook ledger should lean toward its pattern." % (best["title"], format(best["views"], ",")))
    if longs:
        best = max(longs, key=lambda v: v["views"])
        lines.append("- Best Deep-Dive so far: **%s** (%s views)." % (best["title"], format(best["views"], ",")))
    unlisted = [v for v in snap["videos"] if v["privacy"] != "public"]
    if unlisted:
        lines.append("- %d video(s) are not public (unlisted/private) — they cannot be found by anyone; views on them are the owner's own." % len(unlisted))
    if snap.get("analytics_note"):
        lines += ["", "> ⚠️ " + snap["analytics_note"]]
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=28, help="analytics window (default 28)")
    ap.add_argument("--no-save", action="store_true", help="print the snapshot, write nothing")
    a = ap.parse_args(argv)
    try:
        snap = snapshot(days=a.days)
    except yt_publish.Problem as p:
        print(p.report())
        return p.exit_code
    if a.no_save:
        print(json.dumps(snap, indent=1, ensure_ascii=False))
        return 0
    history = save_snapshot(snap)
    REPORT.write_text(render_report(history), encoding="utf-8")
    ch = snap["channel"]
    print("YT_STATS=ok channel=%s subs=%d views=%d videos=%d tracked=%d analytics=%s"
          % (ch["title"], ch["subscribers"], ch["views"], ch["videos"], len(snap["videos"]),
             "yes" if not snap.get("analytics_note") else "no"))
    if snap.get("analytics_note"):
        print("::notice title=Analytics scope::" + snap["analytics_note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
