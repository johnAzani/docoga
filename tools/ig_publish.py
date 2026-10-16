#!/usr/bin/env python3
"""
DocOga Instagram publisher — Reels, Carousels, Photos, and an honest exit code
==============================================================================

Rewritten 13 Oct 2026. The previous version of this file published nothing and **exited
0**, because every failure path was `return None` into a `main()` that ignored the value.
On a runner that is a green tick next to a day that never happened — the same class of bug
that kept the Telegram lane silently dead for five days, and the reason this file now has
an exit code for every outcome and a test named after that specific bug. Three other
things changed, each for a reason you can check:

  * **A token is never printed.** `--refresh-token` used to print `New token: <first 20
    characters>…` into the run log, which is 20 characters of a live credential in a file
    that Actions does not mask line-by-line. It prints a fingerprint now.
  * **The media is examined before Meta is asked.** The publishing API fetches
    `image_url` itself and its failure for a wrong aspect ratio or a PNG is famous for
    being unreadable. So `media_spec()` reads the JPEG header (stdlib, no Pillow, and no
    download of the whole file beyond a few KB) and refuses locally, with a cause, at the
    size and ratio Instagram documents: **JPEG only, ≤ 8 MB, between 4:5 (0.8) and
    1.91:1**. `tools/social_card.py` renders to exactly that box, so the pipeline agrees
    with the API by construction rather than by luck.
  * **`--wait-url` exists, because our media host is the deployed site.** Instagram takes
    a URL, not a file, and DocOga has no CDN — it has `site/`, which Cloudflare serves at
    https://docoga.com.ng for ₦0. The lane commits a render to `site/social/`, the site
    deploy publishes it, and there is a window in which the file exists in git and 404s on
    the web. `wait_until_live` polls that URL until it answers 200 (bounded), so the
    container is never created against a URL Meta cannot fetch. That is what turns "the
    Reels API needs a public URL, so an unattended run would publish nothing more often
    than not" — the reason this lane was dispatch-only — into a lane that can be scheduled.

Two API paths, and the file picks by which credential you gave it
------------------------------------------------------------------
`graph.instagram.com` (**Instagram API with Instagram Login**) is the newer path:
`instagram_business_basic` + `instagram_business_content_publish`, no Facebook Page
required, Business *or* Creator account. `graph.facebook.com` (**Facebook Login**) needs
the Instagram account linked to a Page and uses `instagram_content_publish`. Set
`IG_API_PATH=instagram-login` (default) or `facebook-login`. The older scope names in
this file's first draft (`instagram_content_publish` on the Instagram-Login host) were
deprecated on 27 Jan 2025, which is the kind of thing that fails at 09:00 UTC with a
message about permissions.

For **our** account this needs no App Review: Standard Access covers accounts owned by
someone with a role on the app, and publishing on your own profile is exactly that. App
Review and Business Verification are what a *third-party SaaS* needs to publish for
other people's accounts. (Do not let a 2023 tutorial tell you otherwise; the reason the
lane was blocked was never review.)

Exit codes
    0  published · refused a duplicate · probe ok · dry run
    2  config missing (setup, not an outage)
    3  token rejected, expired, or the app is not approved for the operation
    4  publishing quota spent (100 per 24 h per account)
    5  our own copy or media is not sendable — a bug to fix here, not on Instagram
    6  an API failure this file does not recognise (the raw body is printed, redacted)
    7  published, but the read-back disagrees

Usage
    python3 tools/ig_publish.py --probe
    python3 tools/ig_publish.py --image-url https://docoga.com.ng/social/x.jpg \
        --caption "…" --wait-url
    python3 tools/ig_publish.py --image-urls A.jpg B.jpg --caption "…" --dry-run
"""

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH_FACEBOOK = "https://graph.facebook.com/" + API_VERSION
GRAPH_INSTAGRAM = "https://graph.instagram.com/" + API_VERSION
RUPLOAD = "https://rupload.facebook.com/media/" + API_VERSION

# 4:5 … 1.91:1, JPEG, ≤ 8 MB — Meta's documented content-publishing image limits.
ASPECT_MIN, ASPECT_MAX = 0.8, 1.91
MAX_IMAGE_BYTES = 8 * 1024 * 1024
CAPTION_MAX = 2200

CAPTION_MARKERS = ("instagram_content_publish", "instagram_business_content_publish")

REDACTIONS = (
    (re.compile(r"(access_token=)[^&\s\"]+"), r"\1[redacted]"),
    (re.compile(r"(\"access_token\"\s*:\s*\")[^\"]+"), r"\1[redacted]"),
    (re.compile(r"\bEAA[A-Za-z0-9_-]{20,}"), "[redacted-token]"),
    (re.compile(r"\b\d{6,16}:[A-Za-z0-9_-]{20,}"), "[redacted-bot-token]"),
    (re.compile(r"\b(gh[pousr]_)[A-Za-z0-9]{16,}"), r"\1[redacted]"),
    (re.compile(r"\bya29\.[A-Za-z0-9_-]{10,}"), "[redacted-oauth]"),
)

CAUSES = (
    ("credentials", ("error code 190", "invalid oauth access token", "expired",
                     "the access token is invalid", "please login again", "code 102")),
    ("permission", ("(#200)", "permission", "not approved", "requires authorization",
                    "app is not authorized", "(#368)", "checkpoint", "challenge")),
    ("chat", ("has no profile", "user not found", "(#3)")),
    ("quota", ("content publishing limit", "code 32", "rate limit", "too many requests",
               "code 613", "(#4)")),
    ("media", ("unsupported url request", "could not fetch", "invalid image",
               "image_url", "video_url", "FAILED_PROCESSING", "INVALID_ASPEC",
               "requested url could not be served", "size exceeded")),
    ("state", ("media upload in progress", "container has expired", "status", "still in progress")),
    ("account", ("only business accounts", "professional account", "not a business")),
)


def redact(text):
    out = str(text)
    for pattern, repl in REDACTIONS:
        out = pattern.sub(repl, out)
    return out


def fingerprint(secret):
    return hashlib.sha256(str(secret).encode("utf-8")).hexdigest()[:10]


class ApiError(Exception):
    def __init__(self, status, body, where=""):
        self.status = status
        self.body = body or ""
        self.where = where
        super().__init__("%sHTTP %s: %s" % (where + ": " if where else "", status, self.blurb))

    @property
    def blurb(self):
        return redact(self.body)[:600]

    @property
    def cause(self):
        hay = self.body.lower()
        for cause, needles in CAUSES:
            if any(needle.lower() in hay for needle in needles):
                return cause
        if self.status == 0:
            return "transport"
        return "run"


def machine(result, cause=None, *, stream=None, **extra):
    """One fact per line: the workflow reads these with `sed`, and a shell should not have
    to split a compound line to find out whether a post happened.

    `stream` exists because the token-refresh path runs with stdout redirected into the file
    handed to `token_vault.py seal`: a machine line in that file is a parse error, so its facts
    go to stderr instead. It defaults to `None` and resolves `sys.stdout` *per call* on purpose —
    a default of `sys.stdout` is bound at import time, which quietly defeats every test (and every
    `$(…)` capture) that redirects the stream. Found the hard way: the machine lines simply
    stopped appearing in the lane's own output.
    """
    stream = stream or sys.stdout
    print("IG_RESULT=%s" % result, file=stream)
    if cause:
        print("IG_CAUSE=%s" % cause, file=stream)
    for key, value in extra.items():
        if value:
            print("%s=%s" % (key, value), file=stream)


def api_path(token=None):
    """Which of the two Instagram APIs this credential belongs to."""
    return (os.environ.get("IG_API_PATH") or "instagram-login").strip().lower()


def base_url():
    return GRAPH_INSTAGRAM if api_path() != "facebook-login" else GRAPH_FACEBOOK


def http(method, url, params=None, data=None, timeout=45, headers=None):
    query = dict(params or {})
    if data is None:
        target = "%s?%s" % (url, urllib.parse.urlencode(query, doseq=True)) if query else url
        body = None
    else:
        target = url
        body = urllib.parse.urlencode({**query, **data}, doseq=True).encode("utf-8")
        headers = dict(headers or {}, **{"Content-Type": "application/x-www-form-urlencoded"})
    request = urllib.request.Request(target, data=body, method=method,
                                     headers=dict({"User-Agent": "DocOgaGrowthEngine/1.0"},
                                                  **(headers or {})))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace"), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace"), {}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ApiError(0, "transport failure: %s" % (exc,), "network")


def call(method, path, token, params=None, data=None):
    payload = dict(params or {})
    payload["access_token"] = token
    status, body, _headers = http(method, "%s%s" % (base_url(), path), payload, data)
    try:
        parsed = json.loads(body) if body.strip().startswith(("{", "[")) else {}
    except json.JSONDecodeError:
        parsed = {}
    if status >= 400 or (isinstance(parsed, dict) and parsed.get("error")):
        raise ApiError(status, body or json.dumps(parsed), path.split("?")[0])
    return parsed


def get_config():
    token = (os.environ.get("IG_ACCESS_TOKEN") or "").strip()
    user_id = (os.environ.get("IG_USER_ID") or "").strip()
    app_id = (os.environ.get("META_APP_ID") or "").strip()
    app_secret = (os.environ.get("META_APP_SECRET") or "").strip()
    if not token:
        print("::error title=Instagram secrets missing::IG_ACCESS_TOKEN is not set (and no "
              "vault file). This is a setup step, not an outage.")
        machine("refused", "setup")
        raise SystemExit(2)
    return token, user_id, app_id, app_secret


PROFESSIONAL = ("business", "media_creator", "creator")


def whoami(token):
    # The field is `account_type` (BUSINESS / MEDIA_CREATOR / PERSONAL). 16 Oct 2026: the
    # first real probe asked for a field that does not exist and the API answered
    # `(#100) Tried accessing nonexisting field` — a valid token reported as a credentials
    # failure. The Facebook-Login IG User node has no account-type field at all.
    fields = ("user_id,username,account_type,media_count" if api_path() != "facebook-login"
              else "id,username")
    return call("GET", "/me", token, {"fields": fields})


def account_type(who):
    return str(who.get("account_type") or "").lower()


def check_quota(token, user_id):
    """Fail-open with a named warning: refusing a legitimate post because a counter could
    not be read is the failure mode this whole system was rebuilt to avoid."""
    try:
        data = call("GET", "/%s/content_publishing_limit" % user_id, token,
                    {"fields": "config,quota_usage"})
    except ApiError as exc:
        print("::warning title=Publishing quota unreadable::%s — assuming there is room"
              % exc.blurb[:180])
        return None
    row = data
    if isinstance(data.get("data"), list) and data["data"]:
        row = data["data"][0]
    config = row.get("config") or {}
    return {"usage": int(row.get("quota_usage") or 0),
            "total": int(config.get("quota_total") or 100)}


def jpeg_spec(data):
    """(width, height, format) from the header alone — no Pillow, no full download.

    A JPEG's SOF0/SOF1/SOF2 marker carries height then width, big-endian, 2 bytes each.
    Reading it costs nothing and answers the two questions Meta's error message is worst
    at asking: is this actually a JPEG, and will the crop it wants fit.
    """
    if data[:2] != b"\xff\xd8":
        return None, None, "not-jpeg"
    i, sof = 2, None
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xDA:  # start of scan: the header is over, no SOF found
            break
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            sof = i + 2
            break
        i += 2 + length
    if sof is None:
        return None, None, "no-SOF"
    height, width = struct.unpack(">HH", data[sof + 3:sof + 7])
    return width, height, "jpeg"


def raw_head(url, max_bytes=65536, timeout=30):
    """(status, headers, first bytes) — the only fetch in this file that keeps bytes as bytes.

    `http()` decodes for JSON. A JPEG header cannot survive that, and downloading the whole
    file to learn its size would cost the run's time for no extra truth: the first 64 KB
    already contains SOF0, and `Content-Length` already contains the size.
    """
    request = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "DocOgaGrowthEngine/1.0",
                                              "Range": "bytes=0-%d" % (max_bytes - 1)})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read(max_bytes)
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), b""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ApiError(0, "transport failure while reading the media: %s" % (exc,), "media")


def media_spec_ok(url, allow_unknown=False):
    """Read just enough of the media to know Instagram will take it. Returns (ok, why).

    The checks are Meta's documented ones — JPEG, ≤ 8 MB, aspect between 4:5 and 1.91:1 —
    and they happen here because the API's own answer to a 4:3 PNG is
    `Unsupported URL requested`, which every human who has ever read that has
    mis-diagnosed as a permissions problem. `allow_unknown` is for video: an MP4 has no SOF
    marker to parse, so a Reel URL is checked for reachability and size only.
    """
    try:
        status, headers, data = raw_head(url)
    except ApiError as exc:
        if allow_unknown:
            return True, "unreachable but allowed by --allow-unknown-specs"
        return False, exc.blurb[:160]
    if status not in (200, 206, 416):
        return False, "HTTP %s from %s" % (status, urllib.parse.urlparse(url).netloc)
    length = headers.get("Content-Length") or headers.get("content-length")
    if length:
        try:
            if int(length) > MAX_IMAGE_BYTES and not allow_unknown:
                return False, "%s bytes is over Instagram's %d MB cap" % (
                    length, MAX_IMAGE_BYTES // 1048576)
        except ValueError:
            pass
    # An MP4 box header is `size`(4 bytes) then `ftyp`(4 bytes) — and a container with no
    # SOF marker is exactly the case where guessing from the extension would be a lie, so
    # the bytes decide.
    if url.lower().endswith((".mp4", ".mov")) or data[4:8] == b"ftyp":
        return True, "video container, %d KB sampled" % (len(data) // 1024)
    width, height, fmt = jpeg_spec(data)
    if fmt != "jpeg":
        if allow_unknown:
            return True, "%s, allowed by --allow-unknown-specs" % fmt
        return False, ("%s — Instagram's publishing API takes JPEG only (a PNG of the same "
                       "pixels is rejected with an unreadable message)" % fmt)
    if not width:
        return True, "jpeg, dimensions beyond the sampled head"
    ratio = width / float(height or 1)
    if not ASPECT_MIN - 1e-6 <= ratio <= ASPECT_MAX + 1e-6:
        return False, ("%dx%d is %.3f:1 — Instagram takes between 4:5 (0.800) and 1.91:1"
                       % (width, height, ratio))
    return True, "%dx%d (%.3f:1), within 4:5…1.91:1" % (width, height, ratio)


def wait_until_live(url, deadline_seconds=600, delay=15, sleeper=time.sleep, opener=None):
    """Poll a URL until it answers 200, because git knows about the file before the web does.

    The render is committed to `site/social/…`; `https://docoga.com.ng/social/…` only works
    once the Pages/Worker deploy has finished. Without this, the container is created
    against a 404 and Meta's answer is a generic "Unsupported URL request", which reads
    like a permissions problem and is actually a race we caused.
    """
    opener = opener or (lambda target: http("GET", target, None, timeout=20)[0])
    waited = 0
    while True:
        try:
            status = opener(url)
        except ApiError as exc:
            status = "error %s" % exc.blurb[:80]
        if status == 200:
            if waited:
                print("media became reachable after %ds" % waited)
            return True, waited
        if waited >= deadline_seconds:
            return False, waited
        print("media not live yet (status %s) — retrying in %ds" % (status, delay))
        sleeper(delay)
        waited += delay


def recent_captions(token, user_id, limit=12):
    return call("GET", "/%s/media" % user_id, token,
                {"fields": "id,caption,permalink,media_product_type", "limit": min(int(limit), 50)}
                ).get("data", [])


def normalize(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def find_duplicate(posts, caption):
    needle = normalize(caption)
    if not needle:
        return None
    for post in posts or []:
        if normalize(post.get("caption")) == needle:
            return post.get("permalink") or post.get("id")
    return None


def create_container(token, user_id, data):
    payload = dict(data)
    payload["access_token"] = token
    status, body, _ = http("POST", "%s/%s/media" % (base_url(), user_id), None, payload)
    try:
        parsed = json.loads(body) if body.strip().startswith("{") else {}
    except json.JSONDecodeError:
        parsed = {}
    if status >= 400 or parsed.get("error"):
        raise ApiError(status, body, "/media")
    return parsed["id"]


def wait_for_processing(token, container_id, timeout=900, delay=10, sleeper=time.sleep):
    """Reels and carousels are genuinely asynchronous; photos are not, and this returns on
    the first OK rather than sleeping a fixed time. A container that is ERROR or EXPIRED
    must never be published — publishing an expired container is the 24-hour trap."""
    deadline = time.time() + timeout
    while True:
        try:
            data = call("GET", "/%s" % container_id, token, {"fields": "status_code,status"})
        except ApiError as exc:
            print("::warning title=container status unreadable::%s" % exc.blurb[:180])
            return "UNKNOWN"
        state = (data.get("status_code") or data.get("status") or "").upper()
        if state in ("FINISHED", "OK"):
            return state
        if state in ("ERROR", "EXPIRED", "FAILED"):
            return state
        if time.time() + delay > deadline:
            return state or "TIMEOUT"
        print("  container %s — waiting %ds" % (state or "queued", delay))
        sleeper(delay)
        delay = min(delay * 1.5, 60)


def publish_container(token, user_id, container_id):
    return call("POST", "/%s/media_publish" % user_id, token, None,
                {"creation_id": container_id})["id"]


def permalink_for(token, media_id, username=None):
    try:
        data = call("GET", "/%s" % media_id, token, {"fields": "permalink,shortcode,username"})
    except ApiError as exc:
        print("::warning title=permalink unreadable::%s" % exc.blurb[:160])
        data = {}
    link = data.get("permalink") or (
        "https://www.instagram.com/p/%s/" % data["shortcode"] if data.get("shortcode") else None)
    if not link and username:
        link = "https://www.instagram.com/%s/" % username
    return link, data


def refresh_token(token, app_id, app_secret):
    """60-day long-lived token, wound forward. Prints only a fingerprint: the *value* is
    handed back for the caller to seal (tools/token_vault.py), never echoed to a log."""
    if api_path() != "facebook-login":
        # `/refresh_access_token` winds a long-lived token forward with nothing but the token.
        # `/access_token` is the short→long *exchange* and demands `client_secret` — the first
        # real run's warning was exactly that message because the old code called the wrong one.
        params = {"grant_type": "ig_refresh_token", "access_token": token}
        url = GRAPH_INSTAGRAM + "/refresh_access_token"
    else:
        if not (app_id and app_secret):
            print("::warning title=token not refreshed::META_APP_ID/META_APP_SECRET are needed "
                  "for the Facebook-Login exchange, so the 60-day clock is still running down")
            return None
        params = {"grant_type": "fb_exchange_token", "client_id": app_id,
                  "client_secret": app_secret, "fb_exchange_token": token}
        url = GRAPH_FACEBOOK + "/oauth/access_token"
    status, body, _ = http("GET", url, params)
    try:
        parsed = json.loads(body) if body.strip().startswith("{") else {}
    except json.JSONDecodeError:
        parsed = {}
    if status >= 400 or parsed.get("error"):
        raise ApiError(status, body, url)
    new = parsed.get("access_token")
    if not new:
        raise ApiError(status, "no access_token in the refresh response", url)
    print("token refreshed (fingerprint %s)" % fingerprint(new))
    return parsed


def send(token, user_id, container_data, caption, kind):
    """container → (poll) → publish → read back. The shared spine of all three shapes."""
    problems = []
    if not caption.strip():
        problems.append("an empty caption is accepted by the API and useless in a feed")
    if len(caption) > CAPTION_MAX:
        problems.append("caption is %d characters, over Instagram's %d" % (len(caption), CAPTION_MAX))
    for problem in problems:
        print("::error title=copy rejected::%s" % problem)
    if problems:
        machine("refused", "copy")
        return 5

    limit = check_quota(token, user_id)
    if limit and limit["usage"] >= limit["total"]:
        print("::error title=Instagram publishing quota used up::%s/%s in 24 h. Tomorrow's "
              "run is unaffected." % (limit["usage"], limit["total"]))
        machine("refused", "quota")
        return 4

    try:
        container_id = create_container(token, user_id, container_data)
    except ApiError as exc:
        print("::error title=container rejected (%s)::%s" % (exc.cause, exc.blurb))
        machine("failed", exc.cause)
        return 6
    print("%s container %s created" % (kind, container_id))

    if kind != "photo":
        state = wait_for_processing(token, container_id)
        if state not in ("FINISHED", "OK", "UNKNOWN"):
            print("::error title=container did not finish::status=%s. Containers die after 24 "
                  "hours, so do not re-run this blindly expecting a different answer." % state)
            machine("failed", "state")
            return 6

    try:
        media_id = publish_container(token, user_id, container_id)
    except ApiError as exc:
        print("::error title=publish rejected (%s)::%s" % (exc.cause, exc.blurb))
        machine("failed", exc.cause)
        return 3 if exc.cause in ("credentials", "permission") else 6

    link, seen = permalink_for(token, media_id)
    if kind == "photo" and not (seen.get("permalink") or seen.get("shortcode")):
        print("::error title=read-back incomplete::media %s published but Instagram returned no "
              "permalink, so nothing can be checked from here" % media_id)
        machine("mismatch", "verification", IG_MEDIA_ID=media_id)
        return 7
    print("✅ published %s %s — %s" % (kind, media_id, link or "(no permalink returned)"))
    machine("sent", None, IG_MEDIA_ID=media_id, IG_PERMALINK=link or "")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="DocOga Instagram publisher")
    parser.add_argument("--caption", default="", help="post caption (≤2200 characters)")
    parser.add_argument("--image-url", help="public JPEG URL for a photo")
    parser.add_argument("--image-urls", nargs="+", help="public JPEG URLs for a carousel (2-10)")
    parser.add_argument("--video-url", help="public video URL for a Reel")
    parser.add_argument("--cover-url", help="public JPEG cover for a Reel")
    parser.add_argument("--reel", help="local video path (accepted for compatibility; it is "
                                      "not uploadable — Instagram takes a URL, so this must "
                                      "be published somewhere first: see tools/social_card.py)")
    parser.add_argument("--photo", help="local image path (same URL-only caveat as --reel)")
    parser.add_argument("--carousel", nargs="+", help="local image paths (same caveat)")
    parser.add_argument("--probe", action="store_true",
                        help="ask Instagram who this token is and stop; creates nothing")
    parser.add_argument("--dry-run", action="store_true", help="validate, guard, send nothing")
    parser.add_argument("--wait-url", action="store_true",
                        help="poll the media URL until it is live (the site-deploy race)")
    parser.add_argument("--wait-url-deadline", type=int, default=600)
    parser.add_argument("--no-guard", action="store_true", help="skip the caption read-back check")
    parser.add_argument("--force", action="store_true", help="publish even if it is a duplicate")
    parser.add_argument("--allow-unknown-specs", action="store_true",
                        help="publish a URL whose header could not be read (videos, mostly)")
    parser.add_argument("--refresh-token", action="store_true")
    parser.add_argument("--skip-pages", type=int, default=12)
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    token, user_id, app_id, app_secret = get_config()

    if args.refresh_token:
        try:
            payload = refresh_token(token, app_id, app_secret)
        except ApiError as exc:
            # See tools/threads_publish.py's `--refresh`: the same two reasons — stdout is the
            # vault's input, and the workflows downgrade this to a warning because Meta allows one
            # refresh per 24 h, which setup day trips for real.
            print("instagram refresh failed (%s): %s" % (exc.cause, redact(exc.blurb)),
                  file=sys.stderr)
            machine("refresh-failed", exc.cause, stream=sys.stderr)
            return 3 if exc.cause == "credentials" else 6
        if payload is None:
            return 0
        print(json.dumps(payload))  # to stdout for `token_vault.py seal`; never to a log
        return 0

    try:
        who = whoami(token)
    except ApiError as exc:
        print("::error title=Instagram credentials::/me failed (token fingerprint %s): %s"
              % (fingerprint(token), exc.blurb))
        machine("refused", exc.cause)
        return 3

    username = who.get("username") or "?"
    user_id = user_id or str(who.get("id") or who.get("user_id") or "")
    print("token authorises @%s (id %s, path %s, profile %s)"
          % (username, user_id, api_path(), who.get("account_type") or "?"))
    if not user_id:
        print("::error title=IG_USER_ID unknown::no id from /me and IG_USER_ID is empty")
        machine("refused", "setup")
        return 2
    if api_path() != "facebook-login" and account_type(who) not in PROFESSIONAL:
        print("::error title=not a professional account::account_type=%r — the Instagram API "
              "publishes for Business or Creator accounts only; a personal account has no API "
              "path at all" % who.get("account_type"))
        machine("refused", "account")
        return 3

    if args.probe:
        limit = check_quota(token, user_id)
        print("probe: @%s — %d media on the account, %s" % (
            username, who.get("media_count", "?"),
            "quota %s/%s used" % (limit["usage"], limit["total"]) if limit else "quota unreadable"))
        if api_path() != "facebook-login" and account_type(who) not in PROFESSIONAL:
            print("::warning title=account_type is not business/creator::publishing will be "
                  "refused until the account is switched in the Instagram app")
        machine("probed")
        return 0

    urls = args.image_urls or args.carousel
    if args.image_url:
        kind, media = "photo", {"image_url": args.image_url, "caption": args.caption}
    elif urls:
        kind, media = "carousel", {"media_type": "CAROUSEL", "caption": args.caption}
    elif args.video_url or args.reel:
        if not args.video_url:
            print("::error title=Reels need a public URL::--reel points at a file Instagram "
                  "cannot fetch. Commit the render to site/social/ (see "
                  ".github/workflows/instagram_autopost.yml) or pass --video-url.")
            machine("refused", "media")
            return 5
        kind = "reel"
        media = {"media_type": "REELS", "video_url": args.video_url, "caption": args.caption,
                 "share_to_feed": "true"}
        if args.cover_url:
            media["cover_url"] = args.cover_url
    elif args.photo:
        print("::error title=photos need a public URL::--photo points at a file; Instagram's "
              "publishing API has no multipart upload. Publish the render and pass --image-url.")
        machine("refused", "media")
        return 5
    else:
        parser.print_help()
        machine("refused", "usage")
        return 5

    # The media gate, before any container exists: cheap, and the only place a bad JPEG can
    # be fixed with a sentence instead of an opaque API error.
    check_targets = [args.image_url] if kind == "photo" else (urls or [args.video_url])
    for url in [u for u in check_targets if u]:
        if args.wait_url:
            live, waited = wait_until_live(url, args.wait_url_deadline)
            if not live:
                print("::error title=media never became public::%s did not answer 200 within "
                      "%ds. The render is committed but the site deploy has not published it — "
                      "this is a race, not a credential problem." % (url, args.wait_url_deadline))
                machine("refused", "media")
                return 5
        ok, why = media_spec_ok(url, args.allow_unknown_specs or url.lower().endswith(".mp4"))
        if not ok:
            print("::error title=media rejected before sending::%s → %s" % (url, why))
            machine("refused", "media")
            return 5
        print("media ok: %s (%s)" % (url.rsplit("/", 1)[-1], why))

    if kind == "carousel":
        if not 2 <= len(urls) <= 10:
            print("::error title=carousel size::Instagram takes 2-10 children, got %d" % len(urls))
            machine("refused", "copy")
            return 5
        children = []
        try:
            for index, url in enumerate(urls, 1):
                children.append(create_container(token, user_id,
                                                 {"image_url": url, "is_carousel_item": "true"}))
                print("  child %d/%d: %s" % (index, len(urls), children[-1]))
            media["children"] = ",".join(children)
        except ApiError as exc:
            print("::error title=carousel child rejected (%s)::%s" % (exc.cause, exc.blurb))
            machine("failed", exc.cause)
            return 6

    if not args.no_guard:
        try:
            posts = recent_captions(token, user_id, args.skip_pages)
        except ApiError as exc:
            print("::warning title=duplicate guard unavailable::the account's recent media "
                  "could not be read (%s), so this post goes out on the ledger's word alone"
                  % exc.blurb[:160])
        else:
            hit = find_duplicate(posts, args.caption)
            if hit and not args.force:
                print("refused-a-duplicate: this caption is already on @%s — %s" % (username, hit))
                machine("refused-duplicate", None, IG_PERMALINK=hit)
                return 0
            print("duplicate guard: live — %d recent post(s) on @%s checked" % (len(posts), username))

    if args.dry_run:
        print("Dry run — the credential works, the media reads as publishable, and the caption "
              "is not already on the account. Nothing was created.")
        machine("dry-run")
        return 0

    return send(token, user_id, media, args.caption, kind)


if __name__ == "__main__":
    sys.exit(main())
