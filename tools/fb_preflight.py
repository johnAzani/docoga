#!/usr/bin/env python3
"""
Facebook preflight — name the problem before spending the run on it
===================================================================

Shaped after `tools/telegram_preflight.py`, which exists because the Telegram
post failed silently for four days (7–10 Oct 2026) and nobody could tell from
the run log whether the token, the channel or the permissions were wrong.
Facebook has the same three ways to break, and a fourth that Telegram does not:
an expired token that still *looks* configured.

Answered in order, with Meta's own words:

  1. are both secrets present?                        (no network)
  2. does this token open this Page at all?           `GET /{page-id}?fields=name,link`
  3. can the feed be read?                            `GET /{page-id}/feed?limit=1`
     — the same endpoint the duplicate guard uses, so a red here means a daily
     run would also be unable to tell whether today is already posted.
  4. if META_APP_ID/META_APP_SECRET are present, is the token still alive, for
     how long, and is it the same app?                 `GET /debug_token`
  5. is today already posted?                          informational

Standard library only, so it can run before `pip install requests`. The *write*
probe (create an unpublished post, delete it) deliberately lives in
`tools/fb_publish.py --dry-run` instead: it is the only true proof of
`pages_manage_posts`, and it belongs next to the code that publishes.

Exit codes
  0  everything checked out (a post may be attempted)
  2  FB_PAGE_ACCESS_TOKEN or FB_PAGE_ID is missing
  3  the token was rejected — revoked, expired, or for a different app
  4  the Page could not be resolved from FB_PAGE_ID with this token
  5  the Page's feed could not be read (duplicate guard would be blind, and
     posting rights are almost certainly missing too)
  6  the token is expired or expires inside the warning window

Usage
  python3 tools/fb_preflight.py           # exit status only
  python3 tools/fb_preflight.py --quiet   # only problems
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH = "https://graph.facebook.com/%s" % API_VERSION
TIMEOUT = 20
EXPIRY_WARNING_DAYS = 7
LAGOS = timezone(timedelta(hours=1))


def annotate(level, title, message):
    """Emit a GitHub Actions annotation when running in Actions."""
    if os.getenv("GITHUB_ACTIONS") == "true":
        print("::%s title=%s::%s" % (level, title, message))
    else:
        print("%s: %s — %s" % (level.upper(), title, message))


def call(path, token, **params):
    """GET the Graph API. Returns (ok, payload_or_error_description).

    Never logs the token, and never includes it in a returned string: an error
    body that echoes the query string would otherwise land in the run log.
    """
    query = dict(params)
    query["access_token"] = token
    url = "%s%s?%s" % (GRAPH, path, urllib.parse.urlencode(query))
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8")
            body = json.loads(raw)
        except Exception:
            return False, {"http_status": e.code, "message": (raw or str(e.reason))[:300]}
        return False, body
    except Exception as e:  # network/DNS/TLS
        return False, {"message": "%s: %s" % (type(e).__name__, e), "network": True}
    if isinstance(body, dict) and body.get("error"):
        return False, body["error"]
    return True, body


def describe_error(err):
    """Meta's error object, in one line, without the token."""
    if isinstance(err, str):
        return err[:300]
    bits = [str(err.get("message") or "no message")]
    if err.get("type"):
        bits.append("type=%s" % err.get("type"))
    if err.get("code") is not None:
        bits.append("code=%s" % err.get("code"))
    if err.get("error_subcode") is not None:
        bits.append("subcode=%s" % err.get("error_subcode"))
    text = " ".join(bits)
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN") or ""
    if token:
        text = text.replace(token, "[token redacted]")
    return text[:400]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    quiet = "--quiet" in argv
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    page_id = os.environ.get("FB_PAGE_ID")

    # 1 — presence
    missing = [n for n, v in (("FB_PAGE_ACCESS_TOKEN", token), ("FB_PAGE_ID", page_id)) if not v]
    if missing:
        annotate("error", "Facebook secrets missing",
                 "Set these repository secrets: %s. Nothing was posted. The Page token is minted once "
                 "in the Meta developer dashboard (Business Settings → Pages → Page tokens → long-lived) "
                 "and stored with `gh secret set` — see FACEBOOK_AUTOMATION.md." % ", ".join(missing))
        return 2

    # 2 — token opens the Page
    ok, body = call("/%s" % page_id.strip(), token, fields="name,link,verification_status")
    if not ok:
        code = (body or {}).get("code") if isinstance(body, dict) else None
        if code in (190, 102) or (isinstance(body, dict) and "session" in str(body.get("message", "")).lower()):
            annotate("error", "Facebook token rejected",
                     "The Graph API refused this token (%s). Reissue a long-lived Page token and update "
                     "FB_PAGE_ACCESS_TOKEN; the Page itself is fine." % describe_error(body))
            return 3
        annotate("error", "Page not reachable with this token",
                  "GET /%s?fields=name failed (%s). Either FB_PAGE_ID is wrong, the token is for a "
                  "different Page, or the app lost the admin grant on it." % (page_id, describe_error(body)))
        return 4
    if not quiet:
        print("✅ Page reachable — %s (%s)" % (body.get("name"), body.get("link")))

    # 3 — the feed is readable (the duplicate guard depends on this)
    ok, feed = call("/%s/feed" % page_id.strip(), token, fields="id,created_time", limit=1)
    if not ok:
        annotate("error", "Page feed not readable",
                  "GET /%s/feed failed (%s). The daily run reads this endpoint to avoid posting twice, "
                  "and a token that cannot read the feed almost always cannot post to it either."
                  % (page_id, describe_error(feed)))
        return 5

    # 4 — expiry, when the app credentials are available
    app_id, app_secret = os.environ.get("META_APP_ID"), os.environ.get("META_APP_SECRET")
    if app_id and app_secret:
        ok, info = call("/debug_token", "%s|%s" % (app_id, app_secret), input_token=token)
        if ok:
            data = info.get("data") or {}
            expires_at = data.get("expires_at") or 0
            if data.get("app_id") and str(data["app_id"]) != str(app_id):
                annotate("warning", "Token belongs to another app",
                          "debug_token says app_id=%s but META_APP_ID=%s — the refresh step would fail."
                          % (data["app_id"], app_id))
            if data.get("is_valid") is False:
                annotate("error", "Facebook token is not valid",
                         "debug_token reports is_valid=false (%s)." % describe_error(data.get("error_message") or data))
                return 3
            if expires_at:
                left = datetime.fromtimestamp(int(expires_at), timezone.utc) - datetime.now(timezone.utc)
                if left.total_seconds() <= 0:
                    annotate("error", "Facebook token has expired",
                             "It expired %s. Page tokens minted from Business Settings can be made "
                             "non-expiring; reissue and store a fresh one." % datetime.fromtimestamp(int(expires_at), timezone.utc).date())
                    return 6
                if left < timedelta(days=EXPIRY_WARNING_DAYS):
                    annotate("warning", "Facebook token expiring soon",
                             "%d days left (expires %s). Renew it before the daily post starts failing."
                             % (left.days, datetime.fromtimestamp(int(expires_at), timezone.utc).date()))
                elif not quiet:
                    print("✅ Token valid for %d more days (app %s, %s)"
                          % (left.days, data.get("app_id"), ", ".join(data.get("scopes") or [])))
            elif not quiet:
                print("✅ Token is non-expiring (app %s, %s)"
                      % (data.get("app_id"), ", ".join(data.get("scopes") or [])))
        else:
            annotate("warning", "Could not read token expiry",
                     "debug_token failed (%s). Publishing may still work; the expiry check is the part "
                     "that needs the app credentials." % describe_error(info))
    elif not quiet:
        print("ℹ️  META_APP_ID/META_APP_SECRET not set — expiry not checked (the post itself only needs the Page token).")

    # 5 — is today already posted? (informational: the run will skip, not fail)
    ok, recent = call("/%s/feed" % page_id.strip(), token, fields="created_time,status", limit=5)
    if ok:
        now = datetime.now(LAGOS)
        # Graph reports UTC. A post made in Lagos between midnight and 01:00 carries
        # the *previous* UTC date, so "today" has two spellings and both are
        # checked — otherwise this notice would be wrong at certain hours for no
        # reason at all.
        dates = {now.strftime("%Y-%m-%d"), (now - timedelta(hours=1)).strftime("%Y-%m-%d")}
        posted = [p for p in (recent.get("data") or []) if str(p.get("created_time", ""))[:10] in dates]
        if posted:
            annotate("notice", "Today's post already exists",
                     "The Page already has %d post(s) dated %s (Africa/Lagos), so the scheduled run will skip. "
                     "Use --force on a manual dispatch to post again." % (len(posted), now.strftime("%Y-%m-%d")))

    if not quiet:
        print("✅ Preflight complete — a post may be attempted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
