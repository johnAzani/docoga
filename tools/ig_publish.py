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

Reels, and why they need the *other* path (16 Oct 2026)
--------------------------------------------------------
Every image this lane publishes is a URL on docoga.com.ng. A Reel could be too, but a
rendered MP4 in the deployed tree means a 25 MiB static-asset ceiling, a deploy race with
every other push, and a CDN terms-of-service grey area — for a file Meta fetches exactly
once. Meta documents a way that needs no host at all: **resumable upload**
(developers.facebook.com/docs/instagram-platform/content-publishing/resumable-uploads).
Create the container with `upload_type=resumable`, POST the bytes to
`rupload.facebook.com/ig-api-upload/<version>/<container>` with `Authorization: OAuth`,
`offset` and `file_size` headers, poll `status_code`, publish. It is "available only for
apps that have implemented Facebook Login for Business" — i.e. the `graph.facebook.com`
path, a Page token with `instagram_basic` + `instagram_content_publish`, and the Instagram
professional account linked to the Page. That is the token the Facebook lane already holds,
so the Facebook workflow publishes the Instagram Reel from the same render (`--video-file`)
right after the Facebook one, and `--probe-reels` answers — with reads only — whether the
Page token is ready, naming exactly what is missing when it is not.

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
    IG_API_PATH=facebook-login IG_ACCESS_TOKEN=<page token> FB_PAGE_ID=<page> \
        python3 tools/ig_publish.py --probe-reels
    IG_API_PATH=facebook-login IG_ACCESS_TOKEN=<page token> IG_USER_ID=<ig id> \
        python3 tools/ig_publish.py --video-file assets/videos/docoga_reel.mp4 --caption "…"
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
# Resumable upload host for Instagram containers — a different path from the Facebook Reels
# one (`/media/`), same host, same `Authorization: OAuth` header shape.
RUPLOAD_IG = "https://rupload.facebook.com/ig-api-upload/" + API_VERSION

# 4:5 … 1.91:1, JPEG, ≤ 8 MB — Meta's documented content-publishing image limits.
ASPECT_MIN, ASPECT_MAX = 0.8, 1.91
MAX_IMAGE_BYTES = 8 * 1024 * 1024
CAPTION_MAX = 2200

# Reels by resumable upload. Meta's ceiling is 1 GB / 15 minutes; this uploader buffers the
# file to post it (a 45-second MotionStudio render is a few MB), so the cap here is ours.
VIDEO_MAX_BYTES = 300 * 1024 * 1024
VIDEO_MIN_BYTES = 10_000
# What a Page token must carry for the Facebook-Login path to publish on the linked
# Instagram account. `pages_show_list` / `pages_read_engagement` are what the Facebook lane
# already needs to read the Page at all, so they are not re-checked here.
REEL_SCOPES = ("instagram_basic", "instagram_content_publish")

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
    ("account", ("only business accounts", "professional account", "not a business",
                 "no instagram professional account", "not linked")),
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


def whoami(token, user_id=""):
    # The field is `account_type` (BUSINESS / MEDIA_CREATOR / PERSONAL). 16 Oct 2026: the
    # first real probe asked for a field that does not exist and the API answered
    # `(#100) Tried accessing nonexisting field` — a valid token reported as a credentials
    # failure. The Facebook-Login IG User node has no account-type field at all.
    if api_path() != "facebook-login":
        return call("GET", "/me", token, {"fields": "user_id,username,account_type,media_count"})
    # Facebook-Login path: the credential is a *Page* token, so `/me` is the Page — its id is
    # not an Instagram id and a container created against it fails with a sentence about
    # permissions. The Instagram account is the one linked to the Page, read from the Page.
    if not user_id:
        linked, page = linked_instagram(token)
        if not linked.get("id"):
            raise ApiError(400, json.dumps({"error": {"message": (
                "no Instagram professional account is linked to Page %s — link @docoga.ng to "
                "the Page (Instagram app → Settings → Sharing to other apps → Facebook, or the "
                "Page's Linked accounts) and run the probe again"
                % (page.get("name") or page.get("id") or "?"))}}), "/instagram_business_account")
        user_id = str(linked["id"])
    data = call("GET", "/%s" % user_id, token, {"fields": "id,username,media_count"})
    data.setdefault("user_id", data.get("id") or user_id)
    return data


def page_node():
    """The Page the Facebook-Login token belongs to — `FB_PAGE_ID`, or `me` for a Page token."""
    return (os.environ.get("FB_PAGE_ID") or "").strip() or "me"


LINK_FIELDS = ("instagram_business_account", "connected_instagram_account")


def linked_instagram(token):
    """(the Instagram professional account linked to the Page, the Page) — Facebook-Login path.

    Two Page fields can carry the link, and a Page linked the modern way (Accounts Center /
    the Facebook-Login dialog's "which Instagram account" screen) often shows the account in
    **only** `connected_instagram_account` while `instagram_business_account` stays empty —
    which is exactly how the 16 Oct 2026 probe said `page-link` for a Page whose token had just
    been minted *with* @docoga.ng selected. Both are read; the first one filled wins. Reading
    either needs `instagram_basic`, so an empty answer still means *either* no link *or* no
    scope — `reels_readiness` tells those apart with `debug_token`.
    """
    fields = "id,name," + ",".join("%s{id,username,media_count}" % f for f in LINK_FIELDS)
    page = call("GET", "/%s" % page_node(), token, {"fields": fields})
    for field in LINK_FIELDS:
        linked = page.get(field) or {}
        if linked.get("id"):
            return linked, page
    return {}, page


def token_scopes(token, app_id, app_secret):
    """The scopes on `token`, via `/debug_token` with the app token — or None when the app
    credentials are not in the environment (the fact is then unknown, not false)."""
    if not (app_id and app_secret):
        return None
    status, body, _ = http("GET", GRAPH_FACEBOOK + "/debug_token",
                           {"input_token": token, "access_token": "%s|%s" % (app_id, app_secret)})
    try:
        parsed = json.loads(body) if body.strip().startswith("{") else {}
    except json.JSONDecodeError:
        parsed = {}
    if status >= 400 or parsed.get("error"):
        print("::warning title=token scopes unreadable::debug_token answered HTTP %s: %s"
              % (status, redact(body)[:160]))
        return None
    data = parsed.get("data") or {}
    scopes = list(data.get("scopes") or [])
    for granular in data.get("granular_scopes") or []:
        if granular.get("scope") and granular["scope"] not in scopes:
            scopes.append(granular["scope"])
    return scopes


def reels_readiness(token, app_id="", app_secret=""):
    """Can this Page token publish a Reel on the linked Instagram account? Reads only.

    Three facts, each printed as a line a phone can read, and a verdict the workflow keys on:
    the Page↔Instagram link, the two Instagram scopes, and whether the Instagram node answers
    a publishing-limit read (the cheapest call that needs `instagram_content_publish`).
    """
    report = {"ready": False, "linked": False, "ig_user_id": "", "ig_username": "",
              "scopes": None, "missing": [], "why": []}
    try:
        linked, page = linked_instagram(token)
    except ApiError as exc:
        report["why"].append("the Page could not be read with this token (%s): %s"
                             % (exc.cause, exc.blurb[:160]))
        report["missing"].append("page-read")
        return report
    report["page"] = page.get("name") or page.get("id") or "?"
    if linked.get("id"):
        report["linked"] = True
        report["ig_user_id"] = str(linked["id"])
        report["ig_username"] = linked.get("username") or ""
    scopes = token_scopes(token, app_id, app_secret)
    report["scopes"] = scopes
    if scopes is not None:
        report["missing"].extend(s for s in REEL_SCOPES if s not in scopes)
        if not report["linked"] and "instagram_basic" in scopes:
            report["missing"].append("page-link")
    elif not report["linked"]:
        # Without debug_token the empty field is ambiguous; both fixes are named.
        report["missing"].extend(["page-link-or-instagram_basic"])
    if report["linked"] and "instagram_content_publish" not in report["missing"]:
        try:
            call("GET", "/%s/content_publishing_limit" % report["ig_user_id"], token,
                 {"fields": "quota_usage"})
        except ApiError as exc:
            report["why"].append("the Instagram node refused a publishing read (%s): %s"
                                 % (exc.cause, exc.blurb[:160]))
            if "instagram_content_publish" not in report["missing"]:
                report["missing"].append("instagram_content_publish")
    report["ready"] = report["linked"] and not report["missing"]
    return report


def print_readiness(report):
    """The probe's human lines, then its machine lines. Fix-it text names the exact boxes."""
    if report.get("page"):
        print("page: %s" % report["page"])
    print("instagram linked to the page: %s" % (
        "yes — @%s (id %s)" % (report["ig_username"] or "?", report["ig_user_id"])
        if report["linked"] else "no"))
    if report["scopes"] is None:
        print("token scopes: unknown (META_APP_ID/META_APP_SECRET not set, so debug_token "
              "was not asked)")
    else:
        print("token scopes: %s" % ", ".join(
            "%s %s" % ("✅" if s in report["scopes"] else "❌", s) for s in REEL_SCOPES))
    for why in report["why"]:
        print("note: %s" % why)
    if report["ready"]:
        print("✅ Reels-ready: this Page token can publish Reels on @%s by resumable upload"
              % (report["ig_username"] or report["ig_user_id"]))
    else:
        fixes = []
        if any(m in ("page-link", "page-link-or-instagram_basic") for m in report["missing"]):
            fixes.append("link the Instagram account to the Page — on the Page: "
                         "facebook.com → DocOga Page → Settings → Linked accounts → Instagram → "
                         "Connect account; or Instagram app → Settings → Business tools and "
                         "controls → Connect a Facebook Page → DocOga")
        if any(m in REEL_SCOPES or m == "page-link-or-instagram_basic" for m in report["missing"]):
            fixes.append("regenerate FB_PAGE_ACCESS_TOKEN in Graph API Explorer with "
                         "instagram_basic and instagram_content_publish ticked, Extend → Never, "
                         "then paste it into the secret")
        if "page-read" in report["missing"]:
            fixes.append("the Facebook lane's own preflight will say why the Page is unreadable")
        print("⏸ not Reels-ready yet — %s" % "; ".join(fixes or ["see the notes above"]))
    machine("probed", None, IG_REELS_READY="yes" if report["ready"] else "no",
            IG_REELS_MISSING=",".join(report["missing"]),
            IG_USER_ID=report["ig_user_id"], IG_USERNAME=report["ig_username"])


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


STORY_RATIO = 9 / 16.0  # Stories are the one feed shape that is taller than 4:5


def media_spec_ok(url, allow_unknown=False, story=False):
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
    if story:
        if abs(ratio - STORY_RATIO) > 0.02:
            return False, ("%dx%d is %.3f:1 — a Story frame is 9:16 (1080x1920); anything else "
                           "is letterboxed or cropped by Instagram" % (width, height, ratio))
        return True, "%dx%d (%.3f:1), a 9:16 Story frame" % (width, height, ratio)
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


NOT_READY = ("2207027", "media id is not available", "not ready for publishing")


def not_ready(exc):
    """Error 9007 / subcode 2207027: the container exists but the media behind it is still
    being fetched. Instagram's own text is "please wait for a moment" — a timing answer,
    not a verdict, and the first real post (run #48, 16 Oct 2026) died on it."""
    hay = exc.body.lower()
    return any(needle in hay for needle in NOT_READY)


def publish_container(token, user_id, container_id, attempts=8, delay=10, sleeper=None):
    sleeper = sleeper or time.sleep  # resolved per call so tests (and callers) can stub time.sleep
    for attempt in range(1, attempts + 1):
        try:
            return call("POST", "/%s/media_publish" % user_id, token, None,
                        {"creation_id": container_id})["id"]
        except ApiError as exc:
            if attempt == attempts or not not_ready(exc):
                raise
            print("  publish: media not ready yet (attempt %d/%d) — waiting %ds"
                  % (attempt, attempts, delay))
            sleeper(delay)
            delay = min(delay * 1.5, 60)


def video_spec_ok(path):
    """The local gate for a Reel file, before a byte leaves the runner. Returns (ok, why).

    Container and size are checked here with stdlib; the 9:16 / duration / codec judgement is
    borrowed from `tools/fb_publish.reel_spec_ok` when that module can be imported (it needs
    `requests`), because the same file has to pass the Facebook gate anyway and one gate is
    better than two that drift. Without ffprobe that judgement degrades to a warning, by that
    function's own `strict=False` contract.
    """
    if not os.path.isfile(path):
        return False, "video file not found: %s" % path
    size = os.path.getsize(path)
    if size < VIDEO_MIN_BYTES:
        return False, "%d bytes — the render did not finish" % size
    if size > VIDEO_MAX_BYTES:
        return False, "%d bytes is over this uploader's %d MB cap" % (size, VIDEO_MAX_BYTES // 1048576)
    with open(path, "rb") as handle:
        head = handle.read(12)
    if head[4:8] != b"ftyp":
        return False, "not an MP4/MOV container (no ftyp box at the start of the file)"
    try:
        import fb_publish  # noqa: WPS433 — optional: lives beside this file, needs `requests`
    except Exception:  # pragma: no cover - depends on the machine
        return True, "%d KB, MP4 container (ffprobe gate unavailable here)" % (size // 1024)
    ok, why, info = fb_publish.reel_spec_ok(path, strict=False)
    if not ok:
        return False, why
    if info.get("seconds"):
        return True, "%d KB, %dx%d, %.1fs, %s" % (size // 1024, info.get("width", 0),
                                                   info.get("height", 0), info["seconds"],
                                                   info.get("codec", "?"))
    return True, "%d KB, MP4 container (%s)" % (size // 1024, why)


def http_bytes(url, payload, headers, timeout=900):
    """The second HTTP seam: raw bytes to rupload.facebook.com. `http()` form-encodes its body
    and decodes the answer for JSON; neither is what a video upload is."""
    request = urllib.request.Request(
        url, data=payload, method="POST",
        headers=dict({"User-Agent": "DocOgaGrowthEngine/1.0",
                      "Content-Type": "application/octet-stream"}, **headers))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ApiError(0, "transport failure while uploading the video: %s" % (exc,), "rupload")


def upload_video(token, container_id, path, offset=0):
    """One POST of the file (from `offset`) to the container's rupload endpoint.

    Headers, not form fields: `Authorization: OAuth <token>`, `offset`, `file_size` — the
    documented shape, and the same one tools/fb_publish.reel_upload uses for Facebook Reels.
    """
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        if offset:
            handle.seek(offset)
        payload = handle.read()
    headers = {"Authorization": "OAuth %s" % token, "offset": str(int(offset)),
               "file_size": str(size)}
    status, body = http_bytes("%s/%s" % (RUPLOAD_IG, container_id), payload, headers)
    try:
        parsed = json.loads(body) if body.strip().startswith("{") else {}
    except json.JSONDecodeError:
        parsed = {}
    if status >= 400 or parsed.get("error") or parsed.get("debug_info") \
            or parsed.get("success") is False:
        raise ApiError(status, body or "empty answer from rupload", "rupload")
    return parsed


def bytes_transferred(token, container_id):
    """How much of the file Meta already holds — `video_status.uploading_phase.bytes_transferred`,
    the documented resume point. 0 when the field is absent."""
    data = call("GET", "/%s" % container_id, token, {"fields": "status_code,video_status"})
    phase = (data.get("video_status") or {}).get("uploading_phase") or {}
    try:
        return int(phase.get("bytes_transferred") or 0)
    except (TypeError, ValueError):
        return 0


def retriable(exc):
    return exc.status == 0 or exc.status >= 500 or '"retriable":true' in exc.body.replace(" ", "")


def upload_with_resume(token, container_id, path, attempts=3, delay=5, sleeper=None):
    """Upload, and on a transport or retriable failure resume from the byte Meta reports —
    the one feature that gives this flow its name. A non-retriable refusal is raised at once."""
    sleeper = sleeper or time.sleep
    offset = 0
    for attempt in range(1, attempts + 1):
        try:
            return upload_video(token, container_id, path, offset)
        except ApiError as exc:
            if attempt == attempts or not retriable(exc):
                raise
            try:
                offset = bytes_transferred(token, container_id)
            except ApiError:
                offset = 0
            print("  upload interrupted (%s) — resuming from byte %d (attempt %d/%d)"
                  % (exc.blurb[:120], offset, attempt + 1, attempts))
            sleeper(delay)
            delay = min(delay * 2, 60)


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
    # stderr, deliberately: with --refresh-token, stdout IS the file handed to
    # `token_vault.py seal --json`. Runs #46–#49 (16 Oct 2026) wrote this line into that file,
    # the seal failed on "Expecting value: line 1", and the workflow blamed SOCIAL_TOKEN_KEY.
    print("token refreshed (fingerprint %s)" % fingerprint(new), file=sys.stderr)
    return parsed


def send(token, user_id, container_data, caption, kind, username="", upload=None):
    """container → (upload) → poll → publish → read back. The shared spine of every shape.

    `upload` is the resumable-upload hook: for a URL-based container it is None (Meta fetches
    the URL itself); for `--video-file` it is called with the container id and sends the bytes
    before the status poll. One spine, so a Reel cannot drift from a photo in how it fails."""
    problems = []
    if not caption.strip() and kind != "story":
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

    if upload is not None:
        try:
            answer = upload(container_id)
        except ApiError as exc:
            print("::error title=video upload rejected (%s)::%s" % (exc.cause, exc.blurb))
            machine("failed", exc.cause, IG_CONTAINER_ID=container_id)
            return 3 if exc.cause in ("credentials", "permission") else 6
        print("  bytes accepted by rupload (%s)" % ((answer or {}).get("message") or "ok"))

    # Photos too: a JPEG container is usually FINISHED on the first read, but Instagram fetches
    # the URL asynchronously and publishing before that fetch completes is the "Media ID is not
    # available" failure. One cheap status read is the difference.
    state = wait_for_processing(token, container_id, timeout=300 if kind == "photo" else 900)
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

    if kind == "story":
        # A Story has no permalink: it lives 24 hours in the tray. The id is the read-back.
        link = "https://www.instagram.com/stories/%s/%s/" % (username or "docoga.ng", media_id) \
            if username else ""
        print("✅ published story %s — visible in @%s's story tray for 24 hours"
              % (media_id, username or "?"))
        machine("sent", None, IG_MEDIA_ID=media_id, IG_PERMALINK=link)
        return 0
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
    parser.add_argument("--story-url", help="public 9:16 JPEG URL for a Story (24-hour, no caption)")
    parser.add_argument("--image-urls", nargs="+", help="public JPEG URLs for a carousel (2-10)")
    parser.add_argument("--video-url", help="public video URL for a Reel")
    parser.add_argument("--cover-url", help="public JPEG cover for a Reel")
    parser.add_argument("--video-file", help="local MP4 for a Reel, sent by resumable upload "
                                            "(IG_API_PATH=facebook-login only — Meta documents "
                                            "no upload on the Instagram-Login host)")
    parser.add_argument("--video-story", action="store_true",
                        help="with --video-file: publish it as a 24-hour video Story instead of a Reel")
    parser.add_argument("--thumb-offset-ms", type=int, default=1500,
                        help="with --video-file and no --cover-url: the frame (ms) Instagram uses "
                             "as the Reel cover; 1500 lands on the navy title card")
    parser.add_argument("--no-share-to-feed", action="store_true",
                        help="Reels only: keep it off the profile grid")
    parser.add_argument("--reel", help="alias of --video-file")
    parser.add_argument("--photo", help="local image path (not uploadable: Instagram's image "
                                       "API takes a URL — publish the render and pass --image-url)")
    parser.add_argument("--carousel", nargs="+", help="local image paths (same caveat)")
    parser.add_argument("--probe", action="store_true",
                        help="ask Instagram who this token is and stop; creates nothing")
    parser.add_argument("--probe-reels", action="store_true",
                        help="facebook-login path: is this Page token ready to publish Reels on "
                             "the linked Instagram account? Reads only; prints IG_REELS_READY=")
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

    if args.probe_reels:
        if api_path() != "facebook-login":
            print("::error title=wrong API path for Reels::resumable upload exists on the "
                  "Facebook-Login path only (graph.facebook.com, a Page token). Run with "
                  "IG_API_PATH=facebook-login and IG_ACCESS_TOKEN=<FB_PAGE_ACCESS_TOKEN>.")
            machine("refused", "setup", IG_REELS_READY="no", IG_REELS_MISSING="api-path")
            return 2
        try:
            report = reels_readiness(token, app_id, app_secret)
        except ApiError as exc:  # transport only: reels_readiness catches API answers itself
            print("::error title=Reels probe could not reach Meta::%s" % exc.blurb)
            machine("refused", exc.cause, IG_REELS_READY="no", IG_REELS_MISSING="transport")
            return 6
        print_readiness(report)
        return 0

    try:
        who = whoami(token, user_id)
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
    video_file = args.video_file or args.reel
    upload = None
    if video_file:
        if api_path() != "facebook-login":
            print("::error title=Reels need the Facebook-Login path::resumable upload is "
                  "documented for graph.facebook.com only; this token is on the Instagram-Login "
                  "host. The Facebook lane publishes the Reel with the Page token "
                  "(IG_API_PATH=facebook-login) — see docs/INSTAGRAM_THREADS_AUTOMATION.md.")
            machine("refused", "setup")
            return 2
        ok, why = video_spec_ok(video_file)
        if not ok:
            print("::error title=video rejected before sending::%s → %s" % (video_file, why))
            machine("refused", "media")
            return 5
        print("video ok: %s (%s)" % (os.path.basename(video_file), why))
        if args.video_story:
            kind, media = "story", {"media_type": "STORIES", "upload_type": "resumable"}
        else:
            kind = "reel"
            media = {"media_type": "REELS", "upload_type": "resumable", "caption": args.caption,
                     "share_to_feed": "false" if args.no_share_to_feed else "true"}
            if args.cover_url:
                media["cover_url"] = args.cover_url
            else:
                media["thumb_offset"] = str(max(0, int(args.thumb_offset_ms)))

        def upload(container_id, _token=token, _path=video_file):
            return upload_with_resume(_token, container_id, _path)
    elif args.story_url:
        # Instagram API with Instagram Login publishes Stories for professional accounts:
        # the same container → publish spine, `media_type=STORIES`, image only, no caption
        # (a Story carries its words on the frame — tools/social_card.py --story draws them).
        kind, media = "story", {"media_type": "STORIES", "image_url": args.story_url}
    elif args.image_url:
        kind, media = "photo", {"image_url": args.image_url, "caption": args.caption}
    elif urls:
        kind, media = "carousel", {"media_type": "CAROUSEL", "caption": args.caption}
    elif args.video_url:
        # A hosted MP4 still works on either path; the lane itself uses --video-file.
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
    check_targets = ([] if video_file else [args.image_url] if kind == "photo"
                     else [args.story_url] if kind == "story" else (urls or [args.video_url]))
    for url in [u for u in check_targets if u]:
        if args.wait_url:
            live, waited = wait_until_live(url, args.wait_url_deadline)
            if not live:
                print("::error title=media never became public::%s did not answer 200 within "
                      "%ds. The render is committed but the site deploy has not published it — "
                      "this is a race, not a credential problem." % (url, args.wait_url_deadline))
                machine("refused", "media")
                return 5
        ok, why = media_spec_ok(url, args.allow_unknown_specs or url.lower().endswith(".mp4"),
                                story=(kind == "story"))
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

    if not args.no_guard and kind != "story":  # a Story has no caption to be a duplicate of
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

    return send(token, user_id, media, args.caption, kind, username=username, upload=upload)


if __name__ == "__main__":
    sys.exit(main())
