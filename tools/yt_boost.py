#!/usr/bin/env python3
"""After-publish boosts for every DocOga video: the series playlist and the first comment.

    python3 tools/yt_boost.py plan --video-id ID --kind short --title "…" [--comment "…"]
    python3 tools/yt_boost.py run [--max 4]        # playlists now; comments once the video is public
    python3 tools/yt_boost.py show

Why (visibility research, 17 Oct 2026):
  * YouTube's leading long-form signal in 2026 is *session contribution* — did the viewer keep
    watching the channel after this video? A playlist is the cheapest way to earn it: the next
    episode autoplays, and a playlist is its own search result ("tenancy agreement Nigeria").
  * A comment from the channel under its own video is shown first, carries the Deep-Dive link
    a Short cannot put in its player, and asks the one question that turns a viewer into a
    commenter — comments are the engagement YouTube weights after watch time.
  Both used to be a paste the run summary asked the owner for. The token minted on 17 Oct
  2026 holds youtube.force-ssl (tools/token_scopes.py), so the lane does it itself.

Cost: playlists.list 1 unit, playlists.insert 50 (once per playlist, ever), playlistItems.insert
50, commentThreads.insert 50 — under 160 units a video against 10,000 a day. ₦0.

The sweep is idempotent: a small ledger (logs/youtube_boosts.json) remembers what each video
already has, and the publish ledgers (Shorts + Deep-Dives) feed it, so videos published before
this tool existed are caught up a few at a time (`--max`). A comment waits until the video is
public (scheduled uploads are private until their slot); the playlist does not have to.
Nothing here can fail a publish: the CLI exits 0 unless the ledger itself cannot be read,
and every refusal is a warning with the API's reason in plain words.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
API = "https://www.googleapis.com/youtube/v3"
LEDGER = Path(os.environ.get("YT_BOOST_LEDGER") or (ROOT / "logs" / "youtube_boosts.json"))
SHORTS_LEDGER = ROOT / "logs" / "youtube_published.json"
LONGFORM_LEDGER = ROOT / "logs" / "youtube_longform.json"
SITE = "https://docoga.com.ng/?s=yt"
MAX_COMMENT = 9000           # YouTube's own cap is 10,000 characters
DEFAULT_MAX = 4              # videos touched per sweep — bounded quota, old videos trickle in

# One playlist per series. Titles are search phrases first, brand second — a playlist ranks in
# YouTube and Google search on its own, and the viewer sees it under the video as "Up next".
PLAYLISTS = {
    "short": {
        "title": "Tenant & Landlord Tips in 60 Seconds (Nigeria) — DocOga Shorts",
        "description": ("Rent receipts, tenancy agreements, caution fees, notices to quit, agent fees — "
                        "one habit per Short, in plain English, for tenants and landlords in Nigeria. "
                        "General information, not legal advice; rules vary by state and agreement. "
                        "Free document tools: " + SITE),
    },
    "deepdive": {
        "title": "DocOga Deep-Dives: Rent, Receipts, Agreements & Notices in Nigeria",
        "description": ("The nine-minute versions: what the law actually says about rent receipts, tenancy "
                        "agreements, caution fees and notices in Nigeria, with the section cited on screen. "
                        "General information, not legal advice; rules vary by state and agreement. "
                        "Free document tools: " + SITE),
    },
}

QUESTIONS = {
    "short": "Which of these do you already do — and which one have you been skipping? Tell me below 👇",
    "deepdive": "Which part surprised you most? Drop your question below — the next episode answers the best ones.",
}


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ───────────────────────────── ledger ─────────────────────────────
def load(path=None):
    path = Path(path or LEDGER)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit("yt_boost: ledger %s is unreadable (%s) — fix it before the next sweep" % (path, exc))
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def save(rows, path=None):
    path = Path(path or LEDGER)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def default_comment(kind, title="", parent_comment=""):
    """The first comment: the Deep-Dive link when a Short has one, the question, the free tools."""
    parts = []
    if parent_comment:
        parts.append(parent_comment.strip())
    parts.append(QUESTIONS.get(kind, QUESTIONS["short"]))
    parts.append("Free receipt, tenancy agreement and notice templates (no sign-up): " + SITE)
    return "\n\n".join(parts)[:MAX_COMMENT]


def plan(rows, video_id, kind, title="", comment="", date=""):
    """Add or refresh the plan for one video. Never clears what was already done."""
    kind = kind if kind in PLAYLISTS else "short"
    for row in rows:
        if row.get("video_id") == video_id:
            row.setdefault("kind", kind)
            if title:
                row["title"] = title
            if comment and not row.get("comment_id"):
                row["comment_text"] = comment[:MAX_COMMENT]
            return row
    row = {"video_id": video_id, "kind": kind, "title": title, "date": date or now_iso()[:10],
           "comment_text": (comment or default_comment(kind, title))[:MAX_COMMENT],
           "comment_id": "", "playlist_id": "", "playlist_item_id": "", "planned_at": now_iso(), "notes": []}
    rows.append(row)
    return row


def import_publish_ledgers(rows, shorts=None, longform=None):
    """Every video the publish ledgers know and this one does not becomes a plan with the default comment."""
    added = 0
    import youtube_ledger
    gone = youtube_ledger.deleted_ids()
    for path, kind in ((shorts or SHORTS_LEDGER, "short"), (longform or LONGFORM_LEDGER, "deepdive")):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            data = data.get("entries", [])
        known = {r.get("video_id") for r in rows}
        for entry in data if isinstance(data, list) else []:
            vid = str((entry or {}).get("video_id") or "").strip()
            state = str((entry or {}).get("state") or "")
            if not vid or vid in known or vid in gone or state in ("rejected", "failed", "missing", "deleted"):
                continue
            plan(rows, vid, kind, title=str(entry.get("topic") or entry.get("title") or ""),
                 date=str(entry.get("date") or ""))
            known.add(vid)
            added += 1
    return added


def pending(rows):
    return [r for r in rows if not (r.get("comment_id") and r.get("playlist_item_id"))
            and not r.get("gave_up")]


# ───────────────────────────── API ─────────────────────────────
def _json(r):
    try:
        return r.json()
    except ValueError:
        return {}


def _reason(r):
    body = _json(r)
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        errors = err.get("errors") or [{}]
        return str((errors[0] or {}).get("reason") or err.get("status") or err.get("message") or "")[:80]
    return (getattr(r, "text", "") or "")[:80]


class Boost:
    def __init__(self, http, log=print):
        self.http = http
        self.log = log
        self._playlists = None

    # videos.list, 1 unit
    def status(self, video_id):
        r = self.http.request("GET", API + "/videos", params={"part": "status,snippet", "id": video_id})
        if r.status_code != 200:
            return None, "videos.list HTTP %s (%s)" % (r.status_code, _reason(r))
        items = _json(r).get("items") or []
        if not items:
            return None, "video not on the channel any more"
        st = items[0].get("status") or {}
        return {"privacy": st.get("privacyStatus"), "upload": st.get("uploadStatus"),
                "title": (items[0].get("snippet") or {}).get("title", "")}, ""

    def my_playlists(self):
        if self._playlists is None:
            r = self.http.request("GET", API + "/playlists", params={"part": "snippet", "mine": "true", "maxResults": 50})
            self._playlists = {}
            if r.status_code == 200:
                for item in _json(r).get("items") or []:
                    self._playlists[(item.get("snippet") or {}).get("title", "")] = item.get("id")
            else:
                self.log("::warning title=Playlists unreadable::playlists.list HTTP %s (%s)" % (r.status_code, _reason(r)))
        return self._playlists

    def ensure_playlist(self, kind):
        want = PLAYLISTS[kind]
        have = self.my_playlists()
        if want["title"] in have:
            return have[want["title"]], ""
        body = {"snippet": {"title": want["title"], "description": want["description"], "defaultLanguage": "en"},
                "status": {"privacyStatus": "public"}}
        r = self.http.request("POST", API + "/playlists", params={"part": "snippet,status"},
                              headers={"Content-Type": "application/json"}, data=json.dumps(body))
        if r.status_code not in (200, 201):
            return "", "playlists.insert HTTP %s (%s)" % (r.status_code, _reason(r))
        pid = _json(r).get("id", "")
        have[want["title"]] = pid
        return pid, ""

    def in_playlist(self, playlist_id, video_id):
        r = self.http.request("GET", API + "/playlistItems",
                              params={"part": "id", "playlistId": playlist_id, "videoId": video_id, "maxResults": 1})
        if r.status_code != 200:
            return ""
        items = _json(r).get("items") or []
        return items[0].get("id", "") if items else ""

    def add_to_playlist(self, playlist_id, video_id):
        existing = self.in_playlist(playlist_id, video_id)
        if existing:
            return existing, "already in the playlist"
        body = {"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
        r = self.http.request("POST", API + "/playlistItems", params={"part": "snippet"},
                              headers={"Content-Type": "application/json"}, data=json.dumps(body))
        if r.status_code not in (200, 201):
            return "", "playlistItems.insert HTTP %s (%s)" % (r.status_code, _reason(r))
        return _json(r).get("id", ""), "added"

    def comment(self, video_id, text):
        body = {"snippet": {"videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": text[:MAX_COMMENT]}}}}
        r = self.http.request("POST", API + "/commentThreads", params={"part": "snippet"},
                              headers={"Content-Type": "application/json"}, data=json.dumps(body))
        if r.status_code not in (200, 201):
            return "", "commentThreads.insert HTTP %s (%s)" % (r.status_code, _reason(r))
        return _json(r).get("id", ""), "posted"


def sweep(rows, boost, limit=DEFAULT_MAX, log=print):
    """Do what each pending video still lacks. Returns the count of videos touched."""
    touched = 0
    for row in pending(rows):
        if touched >= limit:
            break
        vid, kind = row["video_id"], row.get("kind") if row.get("kind") in PLAYLISTS else "short"
        did = False
        info, why = boost.status(vid)
        if info is None:
            row.setdefault("notes", []).append("%s: %s" % (now_iso(), why))
            if "not on the channel" in why:
                row["gave_up"] = True
            log("⚠️  %s: %s" % (vid, why))
            touched += 1
            continue
        if not row.get("playlist_item_id"):
            pid, err = boost.ensure_playlist(kind)
            if pid:
                item, note = boost.add_to_playlist(pid, vid)
                if item:
                    row["playlist_id"], row["playlist_item_id"] = pid, item
                    log("✅ %s: playlist — %s (%s)" % (vid, note, PLAYLISTS[kind]["title"][:40]))
                    did = True
                else:
                    row.setdefault("notes", []).append("%s: %s" % (now_iso(), note))
                    log("::warning title=Playlist add failed::%s: %s" % (vid, note))
            else:
                row.setdefault("notes", []).append("%s: %s" % (now_iso(), err))
                log("::warning title=Playlist missing::%s: %s" % (vid, err))
        if not row.get("comment_id"):
            if info.get("privacy") == "public" and info.get("upload") in (None, "processed"):
                cid, note = boost.comment(vid, row.get("comment_text") or default_comment(kind, row.get("title", "")))
                if cid:
                    row["comment_id"], row["commented_at"] = cid, now_iso()
                    log("✅ %s: first comment posted" % vid)
                    did = True
                else:
                    row.setdefault("notes", []).append("%s: %s" % (now_iso(), note))
                    if "commentsDisabled" in note or "forbidden" in note.lower():
                        row["gave_up"] = True
                    log("::warning title=Comment not posted::%s: %s" % (vid, note))
            else:
                log("ℹ️  %s is %s — the comment waits for the public slot" % (vid, info.get("privacy") or "unknown"))
        if did or not row.get("comment_id"):
            touched += 1
    return touched


# ───────────────────────────── CLI ─────────────────────────────
def main(argv=None, http=None):
    ap = argparse.ArgumentParser(description="YouTube after-publish boosts: playlist + first comment")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--video-id", required=True)
    p.add_argument("--kind", choices=sorted(PLAYLISTS), default="short")
    p.add_argument("--title", default="")
    p.add_argument("--comment", default="", help="the first comment; empty = the default question + links")
    p.add_argument("--parent-comment", default="", help="a Short's 'Full episode: …' line, prepended to the default")
    p.add_argument("--date", default="")
    r = sub.add_parser("run")
    r.add_argument("--max", type=int, default=DEFAULT_MAX)
    r.add_argument("--no-import", action="store_true", help="do not pull new videos from the publish ledgers")
    sub.add_parser("show")
    for s in (p, r):
        s.add_argument("--ledger", default="")
    args = ap.parse_args(argv)
    ledger = Path(args.ledger) if getattr(args, "ledger", "") else LEDGER
    rows = load(ledger)

    if args.cmd == "show":
        for row in rows:
            print("%s %-9s playlist=%s comment=%s %s" % (row["video_id"], row.get("kind"),
                                                        "yes" if row.get("playlist_item_id") else "no",
                                                        "yes" if row.get("comment_id") else "no", row.get("title", "")[:50]))
        print("YT_BOOST_PENDING=%d" % len(pending(rows)))
        return 0

    if args.cmd == "plan":
        comment = args.comment or default_comment(args.kind, args.title, args.parent_comment)
        row = plan(rows, args.video_id, args.kind, title=args.title, comment=comment, date=args.date)
        save(rows, ledger)
        print("YT_BOOST_PLANNED=%s" % row["video_id"])
        return 0

    added = 0 if args.no_import else import_publish_ledgers(rows)
    if added:
        print("ℹ️  %d video(s) from the publish ledgers joined the plan" % added)
    todo = pending(rows)
    if not todo:
        save(rows, ledger)
        print("YT_BOOST_RESULT=nothing-pending")
        return 0
    try:
        import yt_publish
        http, _ = yt_publish.authorize(http)
    except Exception as exc:  # noqa: BLE001 — a boost never turns a publish red
        save(rows, ledger)
        print("YT_BOOST_RESULT=no-credentials")
        print("::warning title=Boosts skipped::%s" % str(exc)[:200])
        return 0
    touched = sweep(rows, Boost(http), limit=args.max)
    save(rows, ledger)
    print("YT_BOOST_RESULT=swept")
    print("YT_BOOST_TOUCHED=%d" % touched)
    print("YT_BOOST_PENDING=%d" % len(pending(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
