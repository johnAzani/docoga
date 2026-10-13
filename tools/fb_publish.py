#!/usr/bin/env python3
"""
DocOga Facebook Page Publisher — the API layer, not the scheduler
==================================================================

Publishes text, photos and videos to the DocOga Facebook Page. This module is
imported by `scripts/post_facebook.py` (the unattended daily post) and can also
be run by hand, which is what `workflow_dispatch` on
`.github/workflows/facebook_autopost.yml` does.

Why the file was rewritten on 12 Oct 2026
----------------------------------------
The version before it had four defects, each of which is now a rule with a test
(`tools/tests/test_post_facebook.py`, `tools/tests/test_workflow_contract.py`):

  1. **It shipped the Meta app secret.** `META_APP_SECRET` had a literal default
     in the source, so the credential lived in git history. There is no
     secret-shaped default anywhere in this file now, and
     `tools/qa.py` §14 fails the build if one comes back. A secret that is
     already in history must be *rotated*, not just deleted — see
     `FACEBOOK_AUTOMATION.md`.
  2. **It printed a token prefix.** `print(new_token[:30])` looks harmless
     because Actions masks secrets — but masking matches the *whole* value, so a
     30-character prefix is exactly what leaks. Tokens are only ever reported
     here as a length plus a SHA-256 fingerprint.
  3. **It pinned Graph API v21.0.** Meta ships three or four versions a year and
     each lives about two years: v26.0 (29 Jul 2026) is current, and the v26.0
     behaviour changes extend to every supported version on 27 Oct 2026, with
     v21.0 itself expiring 21 Jan 2027. A pinned version is a dated decision, so
     it is one named constant, overridable with `META_GRAPH_VERSION`.
  4. **Its photo posts had no caption.** Page photo uploads take the text in
     `caption`; `message` is the `/feed` field. Sending `message` to `/photos`
     is not an error — Meta accepts the photo and silently drops the words, so a
     "successful" photo post went out with no copy. That is the same class of
     failure as the four-day Telegram outage: the pipeline was green and the
     post was wrong.

Configuration (GitHub secrets — never defaults in this file)
------------------------------------------------------------
  FB_PAGE_ACCESS_TOKEN   long-lived Page token (pages_manage_posts,
                         pages_read_engagement). Page tokens do not expire while
                         the app stays live and the admin role is held.
  FB_PAGE_ID             the Page's numeric id. There is no fallback value: a
                         wrong-but-silent default posts a paying product's
                         content to somebody else's Page.

  META_APP_ID / META_APP_SECRET   optional, only for `--refresh-token` and the
                         token-expiry read in `tools/fb_preflight.py`.

Exit codes
----------
  0  posted, or deliberately skipped (already posted today), or dry run passed
  2  configuration missing
  3  Facebook rejected the call (its own words are printed)
  4  a file/URL argument could not be used, or the reel failed its local spec gate
  5  the reel reached Meta but Meta would not publish it (start/upload ok, finish failed)

The one Graph-API quirk worth knowing before editing this file
--------------------------------------------------------------
Do **not** send `link` together with `message` on a `/feed` post: when a link
attachment is present, Facebook renders the link card and drops the message
text. The copy already contains the URL, which is why it reads correctly on a
phone with no attachment. See `docs/GROWTH_ENGINE.md`.

Usage
-----
  python3 tools/fb_publish.py --text "Post copy"
  python3 tools/fb_publish.py --photo-file brand/official-logo-transparent.png --text "Caption"
  python3 tools/fb_publish.py --photo-url https://docoga.com.ng/logo-mark.png --text "Caption"
  python3 tools/fb_publish.py --video-url https://example.com/clip.mp4 --text "Description"
  python3 tools/fb_publish.py --reel assets/videos/docoga_short_20261012.mp4 --title "Rent Receipt" --description "..."
  python3 tools/fb_publish.py --reel-probe          # dry run for the Reels lane only
  python3 tools/fb_publish.py --reel-status 1234567890   # what did Meta do with my upload?
  python3 tools/fb_publish.py --text "Would-be post" --dry-run
  python3 tools/fb_publish.py --text "Retrying today on purpose" --force
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

# One constant for the whole pipeline; `META_GRAPH_VERSION` lets the version be
# moved from a repository variable when Meta sunsets this one, without a commit.
API_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH = f"https://graph.facebook.com/{API_VERSION}"
# Videos and photos-over-1MB go to the video host; Meta routes them differently
# and the graph.facebook.com form intermittently returns 400 on file uploads.
GRAPH_VIDEO = f"https://graph-video.facebook.com/{API_VERSION}"

TIMEOUT = 60
# Nigeria is UTC+1 all year (no DST), so the "has today's post already gone out?"
# window can be computed without a tz database. See posted_on_date().
LAGOS = timezone(timedelta(hours=1))

# Facebook's own copy limit for a Page post. Far above anything we generate, but
# truncating here with a log line beats a 100-class "invalid parameter" from the
# API, which is what a naive over-long post would produce.
MAX_MESSAGE_CHARS = 63206


# ── small utilities ─────────────────────────────────────────────────────────
def fingerprint(secret):
    """How a credential may be mentioned in a log: length + digest prefix.

    GitHub's log masking replaces the *exact* secret value only, so any prefix
    (`token[:30]`) is printed in the clear. Never interpolate a token, or part
    of one, into a message.
    """
    if not secret:
        return "(unset)"
    return "sha256:%s… (%d chars)" % (hashlib.sha256(secret.encode()).hexdigest()[:8], len(secret))


def _error_line(response):
    """Facebook's reason, in one line, guaranteed free of the access token."""
    snippet = ""
    try:
        body = response.json()
        err = body.get("error") or {}
        if err:
            bits = [err.get("message") or "unknown error", "type=%s" % err.get("type"),
                    "code=%s" % err.get("code")]
            if err.get("error_subcode"):
                bits.append("subcode=%s" % err.get("error_subcode"))
            if err.get("is_transient"):
                bits.append("transient=yes")
            snippet = " ".join(str(b) for b in bits)
        else:
            snippet = json.dumps(body)[:300]
    except ValueError:
        snippet = (response.text or "")[:300]
    # Belt and braces: if a token ever ends up inside an echoed message, cut it.
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN") or ""
    if token and token in snippet:
        snippet = snippet.replace(token, "[token redacted]")
    return "HTTP %s — %s" % (response.status_code, snippet)


def _ok(response):
    """Graph API success = 2xx and no `error` object in the body."""
    if response.status_code != 200:
        return False, _error_line(response)
    try:
        body = response.json()
    except ValueError:
        return False, "HTTP 200 with a non-JSON body: %s" % (response.text or "")[:200]
    if isinstance(body, dict) and body.get("error"):
        return False, _error_line(response)
    return True, body


# ── configuration ───────────────────────────────────────────────────────────
def load_config():
    """Return (token, page_id) or exit 2 with the names of what is missing."""
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    page_id = os.environ.get("FB_PAGE_ID")
    missing = [n for n, v in (("FB_PAGE_ACCESS_TOKEN", token), ("FB_PAGE_ID", page_id)) if not v]
    if missing:
        print("ERROR: missing configuration: %s" % ", ".join(missing))
        print("       Set them as repository secrets (Actions → Secrets and variables → Actions):")
        print("         gh secret set FB_PAGE_ID --body '<page id>'")
        print("         gh secret set FB_PAGE_ACCESS_TOKEN --body '<long-lived Page token>'")
        print("       No fallback is compiled in on purpose — see this file's header.")
        sys.exit(2)
    return token.strip(), page_id.strip()


# ── the calls ───────────────────────────────────────────────────────────────
def whoami(token, page_id=None):
    """What the token says it is: the Page itself (Page token) or a user."""
    target = page_id or "me"
    try:
        r = requests.get("%s/%s" % (GRAPH, target),
                         params={"fields": "id,name,link", "access_token": token}, timeout=TIMEOUT)
    except requests.RequestException as e:
        return False, "%s: %s" % (type(e).__name__, e)
    return _ok(r)


def posted_on_date(token, page_id, when=None, limit=10, edge="feed", want_title=None):
    """True if the Page already has a *published* post on `when` (default today,
    Africa/Lagos).

    `edge` is which of the Page's edges to read: `feed` for text/photo posts,
    `videos` for Reels (a Reel is a video object, and `/{page}/video_reels`
    itself cannot be read, updated or deleted — so the guard has to go through
    the videos edge). `want_title` narrows the match to one title, which is how
    the Reel guard asks "has *this* reel gone out today?" instead of "has
    anything?".

    This is the duplicate guard, and it is asked of Facebook rather than kept in
    a local file: GitHub Actions runners are disposable, so a marker written in
    the workspace would be forgotten by the next run and a re-run of a failed
    job would post the same copy twice on the same day.
    """
    when = when or datetime.now(LAGOS)
    try:
        r = requests.get("%s/%s/%s" % (GRAPH, page_id, edge),
                         params={"fields": "id,created_time,status,title", "limit": limit,
                                  "access_token": token}, timeout=TIMEOUT)
    except requests.RequestException as e:
        return None, "%s: %s" % (type(e).__name__, e)
    ok, body = _ok(r)
    if not ok:
        return None, body
    want = when.strftime("%Y-%m-%d")
    for item in body.get("data", []) if isinstance(body, dict) else []:
        created = item.get("created_time") or ""
        # Graph returns e.g. 2026-10-12T08:00:00+0000 — convert, then compare dates.
        try:
            stamp = datetime.strptime(created, "%Y-%m-%dT%H:%M:%S%z").astimezone(LAGOS)
        except ValueError:
            continue
        if stamp.strftime("%Y-%m-%d") != want:
            continue
        # `/videos` items carry no `status` field, and a video still processing is
        # not in `/feed` yet — None means "the edge did not say", not "unpublished".
        if item.get("status") not in (None, "published", "scheduled"):
            continue
        if want_title and (item.get("title") or "").strip() != want_title.strip():
            continue
        return True, item.get("id")
    return False, None


def post_text(token, page_id, message):
    """A plain text/link-free Page post."""
    payload = {"message": message[:MAX_MESSAGE_CHARS], "access_token": token}
    try:
        r = requests.post("%s/%s/feed" % (GRAPH, page_id), data=payload, timeout=TIMEOUT)
    except requests.RequestException as e:
        return False, "%s: %s" % (type(e).__name__, e)
    ok, body = _ok(r)
    if not ok:
        return False, body
    return True, body.get("id")


def post_photo_file(token, page_id, path, caption=""):
    """Upload a local image as the post's photo (`source`, multipart form data).

    `caption` — not `message` — is the field Page photo posts read. A local file
    is deliberate: `brand/` is not deployed publicly (only `site/` is), so there
    is no URL for Meta to fetch, and requiring one would make the daily post
    depend on a second system.
    """
    if not os.path.exists(path):
        return False, "photo file not found: %s" % path
    size = os.path.getsize(path)
    if size > 4 * 1024 * 1024:
        return False, "photo is %d bytes; Page photo uploads via `source` are capped at 4 MB" % size
    try:
        with open(path, "rb") as handle:
            r = requests.post(
                "%s/%s/photos" % (GRAPH, page_id),
                data={"caption": caption[:MAX_MESSAGE_CHARS], "access_token": token},
                files={"source": (os.path.basename(path), handle, "image/png")},
                timeout=TIMEOUT,
            )
    except requests.RequestException as e:
        return False, "%s: %s" % (type(e).__name__, e)
    ok, body = _ok(r)
    if not ok:
        return False, body
    return True, body.get("post_id") or body.get("id")


def post_photo_url(token, page_id, image_url, caption=""):
    """Publish a photo Meta fetches from a public URL (used by the manual tab)."""
    payload = {"url": image_url, "caption": caption[:MAX_MESSAGE_CHARS], "access_token": token}
    try:
        r = requests.post("%s/%s/photos" % (GRAPH, page_id), data=payload, timeout=TIMEOUT)
    except requests.RequestException as e:
        return False, "%s: %s" % (type(e).__name__, e)
    ok, body = _ok(r)
    if not ok:
        return False, body
    return True, body.get("post_id") or body.get("id")


def post_video(token, page_id, video_url, title="", description=""):
    """Publish a video Meta fetches from a public URL.

    Only the URL path is automated here. Uploading bytes works too, but the
    rendered Shorts live in `assets/videos/`, which is gitignored build output —
    a workflow that wants to post one must render it in the *same* run (that is
    the documented next step in FACEBOOK_AUTOMATION.md, not a half-wired option).
    """
    payload = {"file_url": video_url, "access_token": token}
    if title:
        payload["title"] = title[:255]
    if description:
        payload["description"] = description[:MAX_MESSAGE_CHARS]
    try:
        r = requests.post("%s/%s/videos" % (GRAPH_VIDEO, page_id), data=payload, timeout=TIMEOUT)
    except requests.RequestException as e:
        return False, "%s: %s" % (type(e).__name__, e)
    ok, body = _ok(r)
    if not ok:
        return False, body
    return True, body.get("id")


# ── Reels: the three-phase `video_reels` protocol ───────────────────────────
#
# Why Reels and not `/videos`: a plain Page video post reaches roughly the Page's
# follower count, and DocOga has a few hundred to reach. A Reel goes into the
# Reels surface, which distributes to non-followers — which is the entire point of
# the lane for an account with 0 followers. (Practitioner evidence, 2026: the same
# file posted through `/videos` tracked the follower count, through `/video_reels`
# tracked the platform's usual reel line.)
#
# The protocol, from Meta's own v26.0 reference (developers.facebook.com/docs/
# graph-api/reference/page/video_reels):
#
#   1. POST /{page_id}/video_reels   upload_phase=start [+ title, description,
#                                    is_ai_generated, feed_targeting, place,
#                                    geo_locations, targeting]
#      -> {video_id, upload_url, success, message, post_id}
#   2. POST https://rupload.facebook.com/video-upload/{VER}/{video_id}
#      headers: Authorization: OAuth <page token>, offset: "0",
#               file_size: "<bytes>", Content-Type: application/octet-stream
#      body: the raw bytes  (or, instead of a body, `file_url: <public https url>`)
#   3. POST /{page_id}/video_reels   upload_phase=finish, video_id,
#                                    video_state=PUBLISHED|DRAFT|SCHEDULED
#                                    (+ scheduled_publish_time when SCHEDULED)
#
# Three properties of this edge are the reason for the code below rather than a
# naive port of the photo uploader:
#   * it cannot be read, updated or deleted through `video_reels` — so "did the
#     Reel go out?" is answered via the *video object* (`GET /{video_id}?fields=
#     status,permalink_url`) or the Page's `videos` edge, never by re-reading the
#     edge that created it;
#   * a file that breaks the spec (not 9:16, outside 3-90 s, wrong codec) is
#     **accepted by the upload and only fails at publish, often with no clear
#     error** — hence `reel_spec_ok()` refusing locally, before any bytes move;
#   * Meta caps published Reels at 30 per Page per rolling 24 hours. One a day is
#     nowhere near it, which is why the cap is a comment and not a counter.
RUPLOAD = "https://rupload.facebook.com/video-upload"
REEL_MIN_SECONDS = 3.0
REEL_MAX_SECONDS = 90.0
REEL_ASPECT = 9 / 16
REEL_ASPECT_TOLERANCE = 0.02          # 0.5625 +/- 0.02: 1080x1920 passes, 4:5 does not
REEL_MAX_BYTES = 4 * 1024 * 1024 * 1024
REEL_MEMORY_LIMIT = 256 * 1024 * 1024  # larger than this, refuse rather than buffer
REEL_POLL_TRIES = 6
REEL_POLL_DELAY = 20                  # seconds; processing a 23s clip is usually <2 min

# Meta's parameter table writes the enum as {START, FINISH} while every working
# example (and Meta's own Postman collection) sends lowercase. Both spellings are
# accepted today, so the default is the one the examples use and the first
# rejection flips the pair once — no side effect, since `start` only opens a
# session that expires if unused.
_PHASES = {"start": "start", "finish": "finish"}


def _phase(name):
    return _PHASES[name]


def _phase_spelling_is_the_problem(body):
    text = (body or "").lower()
    return "upload_phase" in text or "unsupported post request" in text


REEL_EXIT_CODES = {"spec": 4, "start": 3, "upload": 3, "publish": 5, "processing": 5}


def reel_exit_code(detail):
    """Which exit code a Reels failure deserves.

    A file that never passed the local gate is an operator error (4); Meta saying
    no to a call is a credential/API error (3); Meta taking the bytes and then
    not publishing is the failure class that used to be silent, so it gets its own
    code (5) and its own line in FACEBOOK_AUTOMATION.md.
    """
    text = str(detail)
    for stage, code in REEL_EXIT_CODES.items():
        if text.startswith(stage + " refused") or text.startswith(stage + " failed"):
            return code
    return 3

def reel_spec_ok(path, strict=True):
    """Check the file against what Meta requires for a Reel, before uploading it.

    Returns (ok, reason, info). `strict` refuses on a bad spec; with `strict=False`
    a *missing ffprobe* is only a warning (a dev laptop without ffmpeg should not be
    unable to run the lane that CI runs fine) while a *measured* bad file is still a
    refusal — the whole point is that Meta's own failure mode here is silent.
    """
    info = {}
    if not os.path.exists(path):
        return False, "reel file not found: %s" % path, info
    size = os.path.getsize(path)
    if size == 0:
        return False, "reel file is empty — the render did not finish", info
    if size > REEL_MAX_BYTES:
        return False, "reel is %d bytes; Meta caps uploads at 4 GB" % size, info
    if size > REEL_MEMORY_LIMIT:
        return False, ("reel is %d bytes; this uploader buffers the file to post it "
                       "(cap %d). Use the hosted `file_url` variant for large files"
                       % (size, REEL_MEMORY_LIMIT)), info
    if not str(path).lower().endswith(".mp4"):
        return False, "reel must be .mp4 (got %s)" % os.path.splitext(str(path))[1], info
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=width,height,codec_name,avg_frame_rate",
             "-of", "json", path],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        message = "ffprobe unavailable (%s) — the file was not spec-checked" % exc.__class__.__name__
        return (not strict), message, info
    if probe.returncode != 0:
        detail = (probe.stderr or "ffprobe failed").strip().splitlines()[-1:] or ["ffprobe failed"]
        return (not strict), "ffprobe could not read the file (%s)" % detail[0][:200], info
    try:
        data = json.loads(probe.stdout or "{}")
        streams = [st for st in data.get("streams", []) if st.get("width")]
        video = streams[0] if streams else {}
        info = {
            "seconds": float(data.get("format", {}).get("duration") or 0),
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "codec": video.get("codec_name") or "",
            "bytes": size,
        }
    except (TypeError, ValueError) as exc:
        return (not strict), "ffprobe output was not parseable (%s)" % exc, info
    if not info["seconds"]:
        return (not strict), "ffprobe reported no duration", info
    if not info["width"] or not info["height"]:
        return (not strict), "ffprobe reported no video dimensions", info
    aspect = info["width"] / info["height"]
    if abs(aspect - REEL_ASPECT) > REEL_ASPECT_TOLERANCE:
        return False, ("aspect ratio is %d:%d (%.3f); Reels need 9:16 (0.5625) — Meta "
                       "accepts the upload and then fails to publish, quietly"
                       % (info["width"], info["height"], aspect)), info
    if not (REEL_MIN_SECONDS <= info["seconds"] <= REEL_MAX_SECONDS):
        return False, ("duration is %.1fs; the Reels surface needs %.0f-%.0fs — outside it "
                       "this publishes as an ordinary video post, which is the thing "
                       "Reels were meant to avoid" % (info["seconds"], REEL_MIN_SECONDS,
                                                       REEL_MAX_SECONDS)), info
    if info["codec"] not in ("h264", "hevc", "h265"):
        return False, "codec is %r; Meta wants H.264 or H.265" % info["codec"], info
    return True, "ok", info


def reel_start(token, page_id, title="", description="", is_ai_generated=False):
    """Phase 1. Returns (ok, {"video_id":…, "upload_url":…} | error string)."""
    data = {"upload_phase": _phase("start"), "access_token": token}
    if title:
        data["title"] = title[:255]
    if description:
        data["description"] = description[:MAX_MESSAGE_CHARS]
    # Self-declared AI label. These frames are composed from brand templates by
    # moviepy, with no generative model in the path, so it stays false; if a TTS or
    # AI-voice track is ever added to the reel render, flip the default — Meta's
    # labeling rule is about the content, not the container.
    if is_ai_generated:
        data["is_ai_generated"] = "true"
    try:
        r = requests.post("%s/%s/video_reels" % (GRAPH, page_id), data=data, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)
    ok, body = _ok(r)
    if not ok:
        if _PHASES["start"] == "start" and _phase_spelling_is_the_problem(body):
            _PHASES.update({"start": "START", "finish": "FINISH"})
            print("⚠️  Meta rejected upload_phase='start' — retrying with the uppercase "
                  "enum spelling its reference table shows")
            return reel_start(token, page_id, title, description, is_ai_generated)
        return False, body
    video_id = body.get("video_id")
    if not video_id:
        return False, "start phase returned no video_id: %s" % json.dumps(body)[:200]
    return True, {"video_id": str(video_id), "upload_url": body.get("upload_url") or ""}


def reel_upload(token, video_id, path, size=None):
    """Phase 2 — raw bytes to `rupload.facebook.com`.

    Different host, different auth shape: the token is an `Authorization: OAuth`
    header, *not* an `access_token` field, and `offset`/`file_size` are header
    strings. Getting any of that wrong does not always fail fast, so it is asserted
    in tools/tests/test_post_facebook_reels.py rather than trusted.
    """
    if size is None:
        size = os.path.getsize(path)
    if size > REEL_MEMORY_LIMIT:
        return False, "reel is %d bytes; this uploader buffers it in memory (cap %d)" % (
            size, REEL_MEMORY_LIMIT)
    try:
        with open(path, "rb") as handle:
            payload = handle.read()
    except OSError as exc:
        return False, "could not read the reel: %s" % exc
    headers = {
        "Authorization": "OAuth %s" % token,
        "offset": "0",
        "file_size": str(size),
        "Content-Type": "application/octet-stream",
    }
    try:
        r = requests.post("%s/%s/%s" % (RUPLOAD, API_VERSION, video_id),
                          data=payload, headers=headers, timeout=TIMEOUT * 4)
    except requests.RequestException as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)
    if r.status_code // 100 != 2:
        return False, _error_line(r)
    try:
        body = r.json()
    except ValueError:
        body = {}
    if isinstance(body, dict) and body.get("error"):
        return False, _error_line(r)
    transferred = (body or {}).get("end_offset") if isinstance(body, dict) else None
    if transferred not in (None, size):
        # Meta answers with the byte offsets it stored. A short transfer means the
        # file is incomplete on their side, and `finish` would then publish a
        # truncated reel — stop here, where the error is still legible. (Every
        # failure path returns a 2-tuple: a 3-tuple here was caught by
        # tools/tests/test_post_facebook_reels.py as a ValueError in the caller,
        # i.e. the legible message would have been an exception instead.)
        return False, ("upload refused — rupload stored %s of %d bytes, so the reel is "
                       "incomplete on Meta's side; refusing to finish it"
                       % (transferred, size))
    return True, body or {"success": True}


def schedule_error(state, scheduled_publish_time, now=None):
    """None if a SCHEDULED publish would be accepted, else why not.

    Checked *before* the session is opened, not only in `reel_finish`: an upload
    that Meta will veto at publish time wastes the runner's minutes, the upload's
    bandwidth, and leaves an orphan video object on the Page's account.
    """
    if state != "SCHEDULED":
        return None
    when = now if isinstance(scheduled_publish_time, (int, float)) else None
    if when is None:
        try:
            when = int(scheduled_publish_time)
        except (TypeError, ValueError):
            return ("SCHEDULED needs scheduled_publish_time as a unix timestamp more "
                    "than 10 minutes from now")
    delta = when - (now_real())
    if delta < 600:
        return ("scheduled_publish_time is %.0f s away; Meta requires more than 600 s "
                "(and no more than 29 days)" % delta)
    if delta > 29 * 86400:
        return "scheduled_publish_time is more than 29 days out"
    return None


def now_real():
    return time.time()


def reel_finish(token, page_id, video_id, title="", description="",
                state="PUBLISHED", scheduled_publish_time=None):
    """Phase 3 — publish, or hold. `state` is PUBLISHED, DRAFT or SCHEDULED."""
    data = {"upload_phase": _phase("finish"), "video_id": video_id,
            "video_state": state, "access_token": token}
    if title:
        data["title"] = title[:255]
    if description:
        data["description"] = description[:MAX_MESSAGE_CHARS]
    if state == "SCHEDULED":
        problem = schedule_error(state, scheduled_publish_time)
        if problem:
            return False, problem
        data["scheduled_publish_time"] = str(int(scheduled_publish_time))
    try:
        r = requests.post("%s/%s/video_reels" % (GRAPH, page_id), data=data, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)
    ok, body = _ok(r)
    if not ok:
        return False, body
    if body.get("success") is False:
        return False, "finish phase reported success=false: %s" % json.dumps(body)[:200]
    return True, body


def reel_status(token, video_id, fields="status,permalink_url,created_time,title"):
    """Read the video object back. This is the only way to *see* a Reel's result."""
    try:
        r = requests.get("%s/%s" % (GRAPH, video_id),
                         params={"fields": fields, "access_token": token}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)
    return _ok(r)


def wait_for_reel(token, video_id, tries=REEL_POLL_TRIES, delay=REEL_POLL_DELAY, sleeper=None):
    """Bounded poll of the video object, returning ("ready"|"error"|"processing"|
    "unknown", detail).

    `processing` is not a failure and never makes the run red: `finish` already
    succeeded, and a reel that takes longer to render still appears on the Page.
    It is a warning with a link to check, because the alternative — a red run that
    says nothing is wrong — trains nobody to read the red runs.
    """
    sleep = sleeper or time.sleep
    last = {}
    for attempt in range(tries):
        ok, body = reel_status(token, video_id)
        if not ok:
            return "unknown", body
        last = body if isinstance(body, dict) else {}
        status = last.get("status") or {}
        video_status = status.get("video_status")
        if video_status == "error":
            return "error", status
        if video_status == "ready":
            publish = status.get("publishing_phase") or {}
            if publish.get("status") in (None, "complete"):
                return "ready", last
        if attempt < tries - 1:
            sleep(delay)
    return "processing", last


def reel_probe(token, page_id):
    """Dry run for the Reels lane: open a session, then abandon it.

    `video_reels` cannot be read or deleted, so there is no "post then remove"
    probe like the feed one. An unfinished upload session never reaches the Page
    and expires on Meta's side, which is enough to prove the grant that publishing
    a Reel needs — and it is the only Reel check that is safe to run unattended.
    """
    ok, res = reel_start(token, page_id, title="DocOga probe")
    if not ok:
        return False, res
    video_id = res.get("video_id")
    # Best effort: the object exists even if unpublished, and `DELETE /{id}` works
    # on video objects. If it fails, nothing is visible on the Page anyway.
    try:
        requests.delete("%s/%s" % (GRAPH, video_id),
                       params={"access_token": token}, timeout=TIMEOUT)
        cleanup = "abandoned session %s deleted" % video_id
    except requests.RequestException as exc:
        cleanup = "abandoned session %s left to expire (%s)" % (video_id, exc.__class__.__name__)
    return True, "video_reels start accepted (%s); %s" % (video_id, cleanup)


def post_reel(token, page_id, path, title="", description="", draft=False,
              scheduled_publish_time=None, require_spec=True, verify=True, sleeper=None):
    """All three phases, with the local gate first. Returns (ok, detail)."""
    ok, reason, info = reel_spec_ok(path, strict=require_spec)
    if not ok:
        return False, "spec refused — %s" % reason
    if reason != "ok":
        print("⚠️  reel spec: %s" % reason)
    state = "DRAFT" if draft else ("SCHEDULED" if scheduled_publish_time else "PUBLISHED")
    problem = schedule_error(state, scheduled_publish_time)
    if problem:
        return False, "spec refused — %s" % problem
    print("reel spec ok: %dx%d, %.1fs, %s, %d bytes"
          % (info.get("width", 0), info.get("height", 0), info.get("seconds", 0.0),
             info.get("codec", "?"), info.get("bytes", 0)))

    started, res = reel_start(token, page_id, title=title, description=description)
    if not started:
        return False, "start refused — %s" % res
    video_id = res["video_id"]
    print("reel session open: video_id %s" % video_id)

    uploaded, res = reel_upload(token, video_id, path, size=info.get("bytes"))
    if not uploaded:
        return False, ("upload refused after the session opened (video_id %s) — %s"
                       % (video_id, res))
    print("reel bytes accepted: %d" % info.get("bytes", 0))

    finished, res = reel_finish(token, page_id, video_id, title=title,
                                description=description, state=state,
                                scheduled_publish_time=scheduled_publish_time)
    if not finished:
        return False, ("publish refused after the upload was accepted (video_id %s) — %s. The reel is "
                       "held on Meta's side, not lost: finish it later with "
                       "--reel-finish %s" % (video_id, res, video_id))
    detail = {"video_id": video_id, "state": state, "permalink": res.get("permalink_url") or ""}
    if draft or state == "SCHEDULED" or not verify:
        return True, detail
    verdict, body = wait_for_reel(token, video_id, sleeper=sleeper)
    if verdict == "error":
        return False, ("processing failed — Meta accepted the publish and then failed to "
                       "render it (video_id %s): %s" % (video_id, json.dumps(body)[:300]))
    if verdict != "ready":
        print("⚠️  reel is still %s on Meta's side — it was accepted and will appear on "
              "the Page; confirm at https://facebook.com/%s/reel/%s if it does not"
              % (verdict, page_id, video_id))
    detail["verdict"] = verdict
    detail["permalink"] = (body or {}).get("permalink_url") or detail["permalink"]
    return True, detail


def write_permission_probe(token, page_id):
    """May this token actually publish? Ask, without publishing anything.

    Creates an *unpublished* feed post and deletes it immediately. `published`
    defaults to true on `/feed`, so it is set false explicitly: the object never
    appears on the Page, and the delete means nothing is left behind. This is
    the only non-reading probe Meta allows, and it is what makes `--dry-run`
    worth running instead of trusting a scope list.

    Returns (allowed, detail). An unreadable answer is reported as
    ("unknown", …) rather than a failure, because Meta's response to
    `published=false` without a schedule has changed across versions; the
    caller decides how loud to be.
    """
    try:
        r = requests.post("%s/%s/feed" % (GRAPH, page_id),
                          data={"message": "DocOga automation permission probe — not published.",
                                "published": "false", "access_token": token}, timeout=TIMEOUT)
    except requests.RequestException as e:
        return "unknown", "%s: %s" % (type(e).__name__, e)
    ok, body = _ok(r)
    if not ok:
        detail = body if isinstance(body, str) else json.dumps(body)[:300]
        # A permission error is the answer we care about; anything else is noise.
        if isinstance(body, dict) and (body.get("error") or {}).get("code") in (200, 10, 190, 2635):
            return False, detail
        return "unknown", detail
    post_id = (body or {}).get("id")
    if post_id:
        try:
            requests.delete("%s/%s" % (GRAPH, post_id), params={"access_token": token}, timeout=TIMEOUT)
        except requests.RequestException:
            pass  # an orphaned unpublished post is invisible on the Page
    return True, "unpublished probe post created and removed (%s)" % post_id


def refresh_token(token, app_id, app_secret):
    """Exchange a short/long-lived token for a fresh long-lived one.

    Needs the app credentials, which live as secrets and are *never* defaulted
    here. Prints only a fingerprint.
    """
    if not (app_id and app_secret):
        print("SKIP: token refresh needs META_APP_ID and META_APP_SECRET in the environment.")
        return False
    try:
        r = requests.get("%s/oauth/access_token" % GRAPH, params={
            "grant_type": "fb_exchange_token", "client_id": app_id,
            "client_secret": app_secret, "fb_exchange_token": token}, timeout=TIMEOUT)
    except requests.RequestException as e:
        print("FAIL: refresh request errored — %s: %s" % (type(e).__name__, e))
        return False
    ok, body = _ok(r)
    if not ok:
        print("FAIL: Meta refused the exchange — %s" % body)
        return False
    new_token = (body or {}).get("access_token")
    if not new_token:
        print("FAIL: no access_token in the response: %s" % json.dumps(body)[:200])
        return False
    # The value itself is never printed. Put it in the secret store instead:
    #   gh secret set FB_PAGE_ACCESS_TOKEN --body '<the new token>'
    print("✅ Refreshed token received — %s" % fingerprint(new_token))
    print("   Store it: gh secret set FB_PAGE_ACCESS_TOKEN   (GitHub masks only the exact value,")
    print("   so a prefix printed here would have leaked 30 characters of a live credential.)")
    return True


# ── CLI ─────────────────────────────────────────────────────────────────────
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="DocOga Facebook Page Publisher")
    parser.add_argument("--text", help="post copy (also used as the photo caption / video description)")
    parser.add_argument("--photo-url", help="public URL of an image for a photo post")
    parser.add_argument("--photo-file", help="local image file for a photo post (<= 4 MB)")
    parser.add_argument("--video-url", help="public URL of an .mp4 for a video post")
    parser.add_argument("--title", default="", help="video title")
    parser.add_argument("--description", default="", help="video description (falls back to --text)")
    parser.add_argument("--dry-run", action="store_true",
                        help="check credentials and posting rights; publish nothing")
    parser.add_argument("--force", action="store_true",
                        help="publish even if the Page already has a post today")
    parser.add_argument("--no-guard", action="store_true", help="skip the already-posted-today check")
    parser.add_argument("--refresh-token", action="store_true")
    parser.add_argument("--reel", help="local .mp4 to publish as a Reel (three-phase upload)")
    parser.add_argument("--reel-probe", action="store_true",
                        help="open and abandon a video_reels session: proves the grant, publishes nothing")
    parser.add_argument("--reel-status", metavar="VIDEO_ID",
                        help="read a reel's video object back (status, permalink)")
    parser.add_argument("--reel-finish", metavar="VIDEO_ID",
                        help="complete an upload Meta already accepted but that was never published")
    parser.add_argument("--reel-draft", action="store_true",
                        help="with --reel: leave the reel as a draft instead of publishing it")
    parser.add_argument("--reel-schedule", type=int, metavar="EPOCH",
                        help="with --reel: video_state=SCHEDULED at this unix time (>10 min, <29 days)")
    parser.add_argument("--no-spec-check", action="store_true",
                        help="skip the local 9:16 / 3-90s gate (you have the file; Meta does not care yet)")
    args = parser.parse_args(argv)

    token, page_id = load_config()

    if args.refresh_token:
        return 0 if refresh_token(token, os.environ.get("META_APP_ID"),
                                  os.environ.get("META_APP_SECRET")) else 3

    if args.reel_status:
        ok, body = reel_status(token, args.reel_status)
        print(json.dumps(body, indent=2, ensure_ascii=False)[:4000] if ok else "❌ %s" % body)
        return 0 if ok else 3

    if args.reel_finish:
        ok, body = reel_finish(token, page_id, args.reel_finish, title=args.title,
                               description=args.text or args.description,
                               state="DRAFT" if args.reel_draft else "PUBLISHED")
        print(("✅ reel published: %s" % json.dumps(body)[:200]) if ok else "❌ %s" % body)
        return 0 if ok else 5

    if args.dry_run or args.reel_probe:
        ok, body = whoami(token, page_id)
        if not ok:
            print("❌ token or Page id rejected — %s" % body)
            return 3
        print("✅ Page reachable: %s (id %s)" % (body.get("name"), body.get("id")))
        allowed, detail = write_permission_probe(token, page_id)
        print("%s posting rights: %s — %s" % ("✅" if allowed is True else "⚠️", allowed, detail))
        probe_ok, probe_detail = reel_probe(token, page_id)
        print("%s Reels grant: %s" % ("✅" if probe_ok else "⚠️", probe_detail))
        print("(dry run: nothing was published)")
        return 0 if probe_ok or args.dry_run else 3

    if args.reel:
        ok, res = post_reel(token, page_id, args.reel, title=args.title,
                            description=args.description or args.text or "",
                            draft=args.reel_draft, scheduled_publish_time=args.reel_schedule,
                            require_spec=not args.no_spec_check)
        if ok:
            link = res.get("permalink") or ""
            print("✅ reel %s: video_id %s%s" % (res.get("state", "published"),
                                                 res.get("video_id"),
                                                 " — %s" % link if link else ""))
            if res.get("verdict") and res["verdict"] != "ready":
                print("⚠️  Meta is still %s it; it will appear on the Page when done"
                      % ("processing" if res["verdict"] == "processing" else res["verdict"]))
            return 0
        # Different failures mean different things, so they must not share an exit
        # code: a bad file is the operator's, a refusal is the API's, and
        # "accepted then not published" is the class that used to be silent.
        print("❌ reel not published — %s" % res)
        return reel_exit_code(res)

    if args.video_url:
        ok, res = post_video(token, page_id, args.video_url, args.title, args.text or args.description)
    elif args.photo_file:
        ok, res = post_photo_file(token, page_id, args.photo_file, args.text or args.description or "")
    elif args.photo_url:
        ok, res = post_photo_url(token, page_id, args.photo_url, args.text or args.description or "")
    elif args.text:
        if not (args.force or args.no_guard):
            guard, detail = posted_on_date(token, page_id)
            if guard is True:
                print("⏭ skipped — the Page already has a post today (%s). Use --force to post again." % detail)
                return 0
            if guard is None:
                print("⚠️  could not ask Facebook whether today is taken (%s) — posting anyway." % detail)
        ok, res = post_text(token, page_id, args.text)
    else:
        parser.print_help()
        return 4

    if ok:
        print("✅ published: %s" % res)
        return 0
    print("❌ Facebook refused the post — %s" % res)
    return 3


if __name__ == "__main__":
    sys.exit(main())
