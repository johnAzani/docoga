#!/usr/bin/env python3
"""Does the Page convert a visit into a follow? Read the profile, fill what the token may, name the rest.

    python3 tools/fb_page_audit.py            # audit (and fill empty text fields) — needs FB_PAGE_ACCESS_TOKEN, FB_PAGE_ID
    python3 tools/fb_page_audit.py --read-only

4 Nov 2026 research (`tools/fb_follow.py` header): Reels bring strangers to the Page; an empty
About, no website, no profile photo or cover sends them away again. Nobody on the team opens the
Page's settings, so the preflight of every Facebook run (`tools/fb_preflight.py`) calls
`audit()`:

  1. GET /{page}?fields=username,about,description,website,category,emails,phone,
     picture{is_silhouette},cover,is_published,link,followers_count
  2. The text fields the Graph API lets a Page token write (`about`, `description`,
     `website` — scope pages_manage_metadata) are filled from DESIRED when they are empty.
     Never overwritten when the owner has written his own words.
  3. What no API can set (profile photo, cover, the action button) is named as ONE warning with
     the exact tap, only while it is missing. The username is checked against the address the
     Shorts, the site footer and the weekly report print (`fb_follow.PAGE_USERNAME`) — a renamed
     Page would otherwise 404 every link we have ever published.

Stdlib only (the preflight is deliberately dependency-free). Never prints the token. ₦0.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fb_follow  # noqa: E402

API_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH = "https://graph.facebook.com/%s" % API_VERSION
TIMEOUT = 30
FIELDS = "username,about,description,website,category,emails,phone,picture{is_silhouette},cover,is_published,link,followers_count"

DESIRED = {
    "about": ("Free Nigerian tenancy agreement, rent receipt, notice to quit and 6 more documents — built on "
              "your phone in two minutes. One rent rule for your state here every morning at 9:30."),
    "website": "https://docoga.com.ng/?s=fb",
    "description": ("DocOga is the Oga of Documents: free Nigerian document tools — tenancy agreement, notice to "
                    "quit, rent receipt, invoice, employment contract, caution fee receipt, letter of demand, "
                    "payslip, warning letter and power of attorney — built on your phone in two minutes, no "
                    "sign-up. Every morning at 9:30 this Page posts one tenancy-law rule for one Nigerian "
                    "state, cited to the section; every evening a 60-second video. General information, not "
                    "legal advice."),
}
assert len(DESIRED["about"]) <= 255

# What no API can set — the one-time taps, named only while missing.
TAPS = {
    "picture": "Page → Edit → profile photo: upload brand/ logo (square)",
    "cover": "Page → Edit → cover photo: a 1640×624 brand frame",
    "is_published": "Page → Settings → Page visibility: Published",
}


def _http(method, url, data=None, timeout=TIMEOUT):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8") or "{}")
        except ValueError:
            return e.code, {"error": {"message": "HTTP %s" % e.code}}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, {"error": {"message": "%s: %s" % (type(e).__name__, e)}}


def _err(body):
    e = (body or {}).get("error") or {}
    return "%s%s" % (e.get("message") or "unknown error", " (code %s)" % e["code"] if e.get("code") else "")


def read(token, page_id, http=None):
    http = http or _http
    url = "%s/%s?%s" % (GRAPH, page_id, urllib.parse.urlencode({"fields": FIELDS, "access_token": token}))
    st, body = http("GET", url)
    if st != 200 or body.get("error"):
        return None, _err(body)
    return body, None


def fill(token, page_id, fields, http=None):
    """POST the empty text fields. → (ok, detail). A permission refusal is a detail, not a failure."""
    http = http or _http
    st, body = http("POST", "%s/%s" % (GRAPH, page_id), dict(fields, access_token=token))
    if st == 200 and not body.get("error") and body.get("success", True):
        return True, "filled %s" % ", ".join(sorted(fields))
    return False, _err(body)


def audit(token, page_id, http=None, fix=True):
    """→ {"ok": bool, "problems": [str], "filled": [str], "page": {...}, "detail": str}."""
    page, err = read(token, page_id, http)
    if page is None:
        return {"ok": False, "problems": [], "filled": [], "page": {}, "detail": "could not read the Page — %s" % err}
    problems, filled = [], []

    empty = {k: v for k, v in DESIRED.items() if not str(page.get(k) or "").strip()}
    if empty and fix:
        ok, detail = fill(token, page_id, empty, http)
        if ok:
            filled = sorted(empty)
        else:
            problems.append("About/website empty (%s) and the token could not write them (%s) — Page → Edit → "
                            "About: paste the text from tools/fb_page_audit.py DESIRED" % (", ".join(sorted(empty)), detail))
    elif empty:
        problems.append("empty: %s" % ", ".join(sorted(empty)))

    pic = page.get("picture") or {}
    pic = pic.get("data") if isinstance(pic.get("data"), dict) else pic
    if not pic or pic.get("is_silhouette") is True:
        problems.append("no profile photo — " + TAPS["picture"])
    if not page.get("cover"):
        problems.append("no cover photo — " + TAPS["cover"])
    if page.get("is_published") is False:
        problems.append("Page is unpublished — " + TAPS["is_published"])

    username = str(page.get("username") or "").strip()
    if not username:
        problems.append("no username — Page → Settings → Username: %s (every link we publish uses it)" % fb_follow.PAGE_USERNAME)
    elif username.lower() != fb_follow.PAGE_USERNAME.lower():
        problems.append("username is %r but the Shorts, the site footer and the report print %r — fix fb_follow.PAGE_USERNAME"
                        % (username, fb_follow.PAGE_USERNAME))
    return {"ok": not problems, "problems": problems, "filled": filled, "page": page, "detail": ""}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    token, page_id = (os.environ.get("FB_PAGE_ACCESS_TOKEN") or "").strip(), (os.environ.get("FB_PAGE_ID") or "").strip()
    if not token or not page_id:
        print("FB_PAGE_ACCESS_TOKEN / FB_PAGE_ID not set")
        return 2
    out = audit(token, page_id, fix="--read-only" not in argv)
    if out["detail"]:
        print("⚠️ %s" % out["detail"])
        return 1
    p = out["page"]
    print("Page: %s · username=%s · followers=%s · website=%s" % (p.get("link"), p.get("username"), p.get("followers_count"), p.get("website")))
    if out["filled"]:
        print("✍️ filled: %s" % ", ".join(out["filled"]))
    for problem in out["problems"]:
        print("• " + problem)
    print("FB_PAGE_AUDIT=%s" % ("ok" if out["ok"] else "%d problem(s)" % len(out["problems"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
