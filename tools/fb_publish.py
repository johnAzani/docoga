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
  4  a file/URL argument could not be used

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
  python3 tools/fb_publish.py --text "Would-be post" --dry-run
  python3 tools/fb_publish.py --text "Retrying today on purpose" --force
"""

import argparse
import hashlib
import json
import os
import sys
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


def posted_on_date(token, page_id, when=None, limit=10):
    """True if the Page already has a *published* post on `when` (default today,
    Africa/Lagos).

    This is the duplicate guard, and it is asked of Facebook rather than kept in
    a local file: GitHub Actions runners are disposable, so a marker written in
    the workspace would be forgotten by the next run and a re-run of a failed
    job would post the same copy twice on the same day.
    """
    when = when or datetime.now(LAGOS)
    try:
        r = requests.get("%s/%s/feed" % (GRAPH, page_id),
                         params={"fields": "id,created_time,status", "limit": limit,
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
        if stamp.strftime("%Y-%m-%d") == want and item.get("status") in (None, "published", "scheduled"):
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
    args = parser.parse_args(argv)

    token, page_id = load_config()

    if args.refresh_token:
        return 0 if refresh_token(token, os.environ.get("META_APP_ID"),
                                  os.environ.get("META_APP_SECRET")) else 3

    if args.dry_run:
        ok, body = whoami(token, page_id)
        if not ok:
            print("❌ token or Page id rejected — %s" % body)
            return 3
        print("✅ Page reachable: %s (id %s)" % (body.get("name"), body.get("id")))
        allowed, detail = write_permission_probe(token, page_id)
        print("✅ posting rights: %s — %s" % (allowed, detail))
        print("(dry run: nothing was published)")
        return 0

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
