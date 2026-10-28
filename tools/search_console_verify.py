#!/usr/bin/env python3
"""search_console_verify.py — verify docoga.com.ng in Search Console under the sealed account (₦0).

28 Oct 2026: the personal-account consent (tools/google_consent.py --profile search) found that
`tagme.int@gmail.com` — the account that owns the DocOga Cloud project and the YouTube channel —
sees NO Search Console property; the site had been verified under some other account, and from
26 Oct the Monday pull answered "User does not have sufficient permission". The owner's word:
"verify a new one under tagme.int@gmail.com". This tool does that with the Site Verification API
and the META method, so no DNS permission is needed and the only thing that changes on the site
is one extra <meta name="google-site-verification"> line in site/index.html (the old one stays —
ownership by another account is not revoked).

Two commands, with a git commit between them (the workflow does the commit so a token never
touches git from inside Python):

    prepare   open the box → getToken(META) → put the tag in site/index.html (idempotent)
              prints SEARCH_VERIFY=prepared|already-verified|api-disabled|no-token|failed
              and SEARCH_VERIFY_CHANGED=yes|no
    verify    poll https://docoga.com.ng/ until the tag is live (the Workers build takes a
              minute or two), then webResource.insert(META) and sites.add — prints
              SEARCH_VERIFY=verified|already-verified|not-live|refused|no-token|failed

Exit 0 on verified / already / prepared; 9 when the Site Verification API is not enabled on the
project (the summary prints the one link that enables it); 1 otherwise. Never prints a token.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

SITE_URL = "https://docoga.com.ng/"
INDEX = ROOT / "site" / "index.html"
SV = "https://www.googleapis.com/siteVerification/v1"
SITES = "https://searchconsole.googleapis.com/webmasters/v3/sites"
PROJECT_NUMBER = "635194176409"           # the client id's prefix — the DocOga Cloud project
ENABLE_URL = ("https://console.developers.google.com/apis/api/siteverification.googleapis.com/overview?project=" + PROJECT_NUMBER)
TAG_RE = re.compile(r'<meta\s+name="google-site-verification"\s+content="([^"]+)"\s*/?>', re.I)


def _http(method, url, params=None, data=None, headers=None):
    import requests
    r = requests.request(method, url, params=params, data=data, headers=headers, timeout=30)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": (r.text or "")[:300]}
    return r.status_code, body


def _fetch_text(url):
    import requests
    r = requests.get(url, timeout=30, headers={"User-Agent": "DocOga-verify/1.0 (+https://docoga.com.ng)",
                                               "Cache-Control": "no-cache"})
    return r.status_code, r.text or ""


def access_token():
    """The personal account's access token from logs/google_search_token.box, or ''."""
    import search_console
    import yt_publish
    refresh = search_console.search_refresh_token()
    cid, csec = os.environ.get("YT_CLIENT_ID", ""), os.environ.get("YT_CLIENT_SECRET", "")
    if not (refresh and cid and csec):
        return ""
    return yt_publish.refresh_access_token(cid, csec, refresh)["access_token"]


def err_message(body):
    return str(((body or {}).get("error") or {}).get("message") or json.dumps(body or {}))[:240]


def api_disabled(status, body):
    msg = err_message(body).lower()
    return status == 403 and ("has not been used in project" in msg or "is disabled" in msg or "accessnotconfigured" in msg)


def sites_seen(token, http=_http):
    st, body = http("GET", SITES, params={"access_token": token})
    if st != 200:
        return None
    return {str(s.get("siteUrl", "")): str(s.get("permissionLevel", "")) for s in (body.get("siteEntry") or [])}


def verified_already(seen):
    return bool(seen) and any(SITE_URL == k or k == "sc-domain:docoga.com.ng" for k, v in seen.items() if v != "siteUnverifiedUser")


def meta_token(token, http=_http):
    """getToken(META) for the URL-prefix site → (status, content, detail)."""
    st, body = http("POST", SV + "/token", params={"access_token": token},
                    data=json.dumps({"verificationMethod": "META", "site": {"identifier": SITE_URL, "type": "SITE"}}),
                    headers={"Content-Type": "application/json"})
    if st != 200:
        return st, "", err_message(body)
    tag = str(body.get("token") or "")
    m = TAG_RE.search(tag)
    content = m.group(1) if m else (tag if tag and "<" not in tag else "")
    return st, content, ""


def place_tag(html, content):
    """Add the tag to <head> unless the same content is already there. Other verification tags
    (other accounts) are left exactly as they are. Returns (new_html, changed)."""
    if content in [m.group(1) for m in TAG_RE.finditer(html)]:
        return html, False
    line = '<meta name="google-site-verification" content="%s" />' % content
    existing = list(TAG_RE.finditer(html))
    if existing:
        last = existing[-1]
        return html[:last.end()] + "\n" + line + html[last.end():], True
    i = html.find("<head>")
    if i < 0:
        return html, False
    i += len("<head>")
    return html[:i] + "\n" + line + html[i:], True


def cmd_prepare(http=_http, index=INDEX, log=print):
    token = access_token()
    if not token:
        log("SEARCH_VERIFY=no-token")
        return 1
    seen = sites_seen(token, http=http)
    if verified_already(seen):
        log("search verify: %s is already a verified property of this account" % SITE_URL)
        log("SEARCH_VERIFY=already-verified")
        log("SEARCH_VERIFY_CHANGED=no")
        return 0
    st, content, detail = meta_token(token, http=http)
    if api_disabled(st, {"error": {"message": detail}}):
        log("search verify: the Site Verification API is not enabled on the DocOga project. One tap: %s → Enable, "
            "then run this workflow again." % ENABLE_URL)
        log("SEARCH_VERIFY=api-disabled")
        log("SEARCH_VERIFY_CHANGED=no")
        return 9
    if st != 200 or not content:
        log("search verify: getToken answered HTTP %s — %s" % (st, detail or "no token in the reply"))
        log("SEARCH_VERIFY=failed")
        log("SEARCH_VERIFY_CHANGED=no")
        return 1
    html = Path(index).read_text(encoding="utf-8")
    new, changed = place_tag(html, content)
    if changed:
        Path(index).write_text(new, encoding="utf-8")
    log("search verify: verification tag %s in %s" % ("added to" if changed else "already in", Path(index).name))
    log("SEARCH_VERIFY=prepared")
    log("SEARCH_VERIFY_CHANGED=%s" % ("yes" if changed else "no"))
    return 0


def tag_live(content, fetch=_fetch_text):
    st, text = fetch(SITE_URL)
    return st == 200 and content in text


def cmd_verify(http=_http, fetch=_fetch_text, index=INDEX, wait=420, every=30, sleep=time.sleep, log=print):
    token = access_token()
    if not token:
        log("SEARCH_VERIFY=no-token")
        return 1
    seen = sites_seen(token, http=http)
    if verified_already(seen):
        log("SEARCH_VERIFY=already-verified")
        return 0
    st, content, detail = meta_token(token, http=http)
    if api_disabled(st, {"error": {"message": detail}}):
        log("search verify: the Site Verification API is not enabled on the DocOga project. One tap: %s → Enable." % ENABLE_URL)
        log("SEARCH_VERIFY=api-disabled")
        return 9
    if st != 200 or not content:
        log("search verify: getToken answered HTTP %s — %s" % (st, detail))
        log("SEARCH_VERIFY=failed")
        return 1
    html = Path(index).read_text(encoding="utf-8")
    if content not in [m.group(1) for m in TAG_RE.finditer(html)]:
        log("search verify: the tag is not in site/index.html yet — run `prepare` and commit first")
        log("SEARCH_VERIFY=failed")
        return 1
    deadline = time.monotonic() + wait
    live = tag_live(content, fetch=fetch)
    while not live and time.monotonic() < deadline:
        sleep(every)
        live = tag_live(content, fetch=fetch)
    if not live:
        log("search verify: the tag is committed but %s does not serve it yet after %ds — the Workers build is "
            "still running. Run the 'Search Console — verify' workflow again in a few minutes; nothing else to do." % (SITE_URL, wait))
        log("SEARCH_VERIFY=not-live")
        return 1
    st, body = http("POST", SV + "/webResource", params={"verificationMethod": "META", "access_token": token},
                    data=json.dumps({"site": {"identifier": SITE_URL, "type": "SITE"}}),
                    headers={"Content-Type": "application/json"})
    if st != 200:
        log("search verify: Google refused the verification: HTTP %s — %s" % (st, err_message(body)))
        log("SEARCH_VERIFY=refused")
        return 1
    st, body = http("PUT", SITES + "/" + quote(SITE_URL, safe=""), params={"access_token": token})
    log("SEARCH_CONSOLE_SITE_ADD=%s" % st)
    seen = sites_seen(token, http=http) or {}
    log("search verify: %s verified; this account now sees %d Search Console propert%s"
        % (SITE_URL, len(seen), "y" if len(seen) == 1 else "ies"))
    log("SEARCH_VERIFY=verified")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="verify docoga.com.ng in Search Console under the sealed account")
    ap.add_argument("command", choices=("prepare", "verify"))
    ap.add_argument("--wait", type=int, default=420, help="seconds to wait for the tag to go live (verify)")
    a = ap.parse_args(argv)
    if a.command == "prepare":
        return cmd_prepare()
    return cmd_verify(wait=a.wait)


if __name__ == "__main__":
    sys.exit(main())
