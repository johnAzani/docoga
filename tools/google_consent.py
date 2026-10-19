#!/usr/bin/env python3
"""
tools/google_consent.py — the one Google consent, done from a phone
=====================================================================

The owner works from a phone. Google's normal re-consent wants a machine with a browser
*and* the client secret pasted into a form; the phone layout of the Cloud console never
shows the secret. So the secret never leaves GitHub:

    1. `url`      prints the consent link — ALL 7 scopes (docs/TOKENS.md), offline access,
                  forced consent, redirect to Google's own OAuth Playground page.
    2. the owner opens it, ticks every box, lands on the Playground with `?code=4/0A…`
       in the address bar, copies the address (or just the code),
    3. `exchange` (run by .github/workflows/google_consent.yml, which holds YT_CLIENT_ID and
       YT_CLIENT_SECRET) swaps the code for a refresh token, checks the token carries every
       scope, and seals it into the vault — logs/yt_refresh_token.box, AES-256-GCM under
       SOCIAL_TOKEN_KEY, exactly like the Instagram and Threads tokens.
    4. yt_publish.authorize() (every YouTube / Analytics / Search Console call goes through
       it) and token_scopes.read_google() prefer the vault over the YT_REFRESH_TOKEN secret.

A partial token (an unticked box) is REFUSED and the old one stays — the owner's rule is
"minted once, complete; I will not remint it" — unless --accept-partial is given.
Nothing here prints a token, a code or a secret.

Machine lines: GOOGLE_CONSENT=ok|partial|refused|failed  GOOGLE_SCOPES_MISSING=<space list>
Exit: 0 sealed · 2 missing env · 3 Google refused the code · 4 partial and not accepted · 6 wrong channel ·
5 vault error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import token_scopes  # noqa: E402
import token_vault  # noqa: E402

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
REDIRECT_URI = "https://developers.google.com/oauthplayground"
VAULT_NAME = "YT_REFRESH_TOKEN"
SCOPES = tuple(token_scopes.WANT["google"])


def consent_url(client_id):
    """The link the owner opens once. Every scope, offline, consent forced so a refresh token
    is issued even though one exists, and granted scopes merged in."""
    q = {"client_id": client_id, "redirect_uri": REDIRECT_URI, "response_type": "code",
         "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent",
         "include_granted_scopes": "true"}
    return AUTH_URL + "?" + urlencode(q)


def code_from(text):
    """Accept the bare code or the whole Playground address the phone copied."""
    text = (text or "").strip().strip("'\"")
    if not text:
        return ""
    if "code=" in text:
        qs = parse_qs(urlparse(text).query if "://" in text else text.split("?", 1)[-1])
        got = qs.get("code") or []
        if got:
            return got[0].strip()
    return text


def _http(method, url, data=None, params=None):
    import requests
    r = requests.request(method, url, data=data, params=params, timeout=30)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": (r.text or "")[:300]}
    return r.status_code, body


def exchange(code, client_id, client_secret, http=_http):
    """Code → tokens. Returns (status, body); never logs either."""
    return http("POST", TOKEN_URL, data={"code": code, "client_id": client_id, "client_secret": client_secret,
                                        "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code"})


def granted_scopes(body, http=_http):
    """Scopes on the new token: Google's own `scope` field, else tokeninfo."""
    scope = str(body.get("scope") or "").split()
    if scope:
        return scope
    st, info = http("GET", TOKENINFO_URL, params={"access_token": body.get("access_token", "")})
    return str((info or {}).get("scope") or "").split() if st == 200 else []


def run_exchange(code, env=None, http=_http, accept_partial=False, log=print, vault_path=None):
    env = os.environ if env is None else env
    cid, csec = env.get("YT_CLIENT_ID", "").strip(), env.get("YT_CLIENT_SECRET", "").strip()
    code = code_from(code)
    if not (cid and csec and code):
        log("google consent: need YT_CLIENT_ID, YT_CLIENT_SECRET and the code")
        log("GOOGLE_CONSENT=failed")
        return 2
    st, body = exchange(code, cid, csec, http=http)
    refresh = (body or {}).get("refresh_token") if st == 200 else None
    if not refresh:
        err = (body or {}).get("error", "")
        desc = str((body or {}).get("error_description", ""))[:160]
        hint = {"invalid_grant": "the code was already used or is older than ~10 minutes — open the link again and copy the new one",
                "redirect_uri_mismatch": "the client is missing the Playground redirect URI",
                "invalid_client": "YT_CLIENT_ID / YT_CLIENT_SECRET do not match the client that issued the code"}.get(err, "")
        log("google consent: Google refused the code: HTTP %s %s %s %s" % (st, err, desc, ("— " + hint) if hint else ""))
        log("GOOGLE_CONSENT=failed")
        return 3
    have = set(granted_scopes(body, http=http))
    missing = [s for s in SCOPES if s not in have]
    log("GOOGLE_SCOPES_MISSING=%s" % " ".join(missing))
    if missing and not accept_partial:
        log("google consent: the new token is short of %d scope(s) — a box was left unticked. "
            "Refused; the old token stays. Open the link again and tick every box." % len(missing))
        log("GOOGLE_CONSENT=refused")
        return 4
    # Which channel did the owner pick? (19 Oct 2026: the 17 Oct mint picked the account's
    # personal channel, not the DocOga brand channel — every YouTube lane then talked to an empty
    # channel. Google shows a second chooser after the account: the brand channel must be picked
    # there.) With YT_CHANNEL_ID set, a mismatch is refused and the old token stays.
    want = str(env.get("YT_CHANNEL_ID", "")).strip()
    st, chan = http("GET", CHANNELS_URL, params={"part": "snippet", "mine": "true",
                                                 "access_token": body.get("access_token", "")})
    items = (chan or {}).get("items") or [] if st == 200 else []
    got_id = str(items[0].get("id", "")) if items else ""
    got_title = str(((items[0].get("snippet") or {}).get("title", "")) if items else "")
    log("GOOGLE_CHANNEL=%s %s" % (got_id or "unknown", got_title))
    if want and got_id and got_id != want:
        log("google consent: this token is for the channel '%s' (%s), not DocOga (%s). Refused; the old "
            "token stays. Open the link again, pick the Google account, and on the SECOND chooser "
            "pick the DocOga channel, not the personal one." % (got_title, got_id, want))
        log("GOOGLE_CONSENT=wrong_channel")
        return 6
    rc = token_vault.seal(VAULT_NAME, refresh, path=vault_path, out=sys.stdout)
    if rc:
        log("GOOGLE_CONSENT=failed")
        return 5
    log("google consent: %d of %d scopes, sealed into the vault — no lane needs a secret pasted"
        % (len(SCOPES) - len(missing), len(SCOPES)))
    log("GOOGLE_CONSENT=%s" % ("partial" if missing else "ok"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("command", choices=("url", "exchange"))
    ap.add_argument("--code", default="", help="the code, or the whole Playground address")
    ap.add_argument("--accept-partial", action="store_true")
    a = ap.parse_args(argv)
    if a.command == "url":
        cid = os.environ.get("YT_CLIENT_ID", "").strip()
        if not cid:
            print("google consent: YT_CLIENT_ID is not set", file=sys.stderr)
            return 2
        print(consent_url(cid))
        return 0
    return run_exchange(a.code or os.environ.get("GOOGLE_AUTH_CODE", ""), accept_partial=a.accept_partial)


if __name__ == "__main__":
    sys.exit(main())
