#!/usr/bin/env python3
"""The ONE list of permissions each token must carry, and the audit that checks a live token
against it — so a token is minted once, with everything, and never re-minted for a feature
the repo adds later (owner, 17 Oct 2026: "make sure all permissions are granted … I will not
want to re-mint it").

    python3 tools/token_scopes.py list [facebook|instagram|threads|google|linkedin|tiktok|telegram]
    python3 tools/token_scopes.py audit            # reads the tokens in the environment, prints
                                                   # SCOPES_<TOKEN>=complete|missing:a,b|unreadable|no-token
    python3 tools/token_scopes.py audit --markdown /tmp/scopes.md

Design:
  * `WANT` is the superset — what the lanes use today PLUS what any planned lane could ask
    for (insights, messaging, mentions, delete, analytics, Search Console). Over-asking on
    our own assets costs nothing: these are standard-access permissions on assets we own,
    none needs App Review, and a token that carries them idles until a lane uses them.
  * The audit never prints a token. It reads scopes with the platform's own introspection
    (`/me/permissions`, `/debug_token`, Google `tokeninfo`, LinkedIn `introspectToken`) and
    says `unreadable` when the platform cannot tell us — never "complete" on a guess.
  * `FEATURES` are Meta app-level *features* (not token scopes). They are listed so the owner
    sees them once; for a Page and Instagram account the app's own admin owns, standard
    access is already on and there is nothing to tick.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/" + os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH_IG = "https://graph.instagram.com/" + os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH_THREADS = "https://graph.threads.net/v1.0"

# ─────────────────────────── the complete lists ───────────────────────────
WANT = {
    # Facebook Page token, minted in Graph API Explorer on the Business app (931364932955308),
    # "User or Page" → the DocOga Page. Never-expiring when the user token behind it is long-lived.
    "facebook": [
        "pages_show_list",             # list the Pages the user admins (the Explorer needs it to offer the Page token)
        "pages_read_engagement",       # posts, comments, reactions — the replies lane and the scorecard
        "pages_read_user_content",     # user comments/posts on the Page (visitor posts, mentions)
        "pages_manage_posts",          # publish posts, photos, videos, Reels, Stories
        "pages_manage_metadata",       # Page settings + webhooks subscription (the lane's refresh step)
        "pages_manage_engagement",     # reply to / like / hide comments (the community manager)
        "pages_messaging",             # Messenger private replies (comment → DM)
        "read_insights",               # Page insights (reach, follows, engagements) — the scorecard
        "publish_video",               # Live/video publishing on behalf of the Page
        "business_management",         # Business Manager assets (the Page↔Instagram link, the app)
        "instagram_basic",             # the linked Instagram account's profile and media
        "instagram_content_publish",   # Reels, photos, carousels, Stories through the Page token
        "instagram_manage_comments",   # Instagram comments (Facebook-Login path)
        "instagram_manage_insights",   # Instagram insights incl. online_followers (the slot plan)
        "instagram_manage_messages",   # Instagram private replies (Facebook-Login path)
    ],
    # Instagram token on the Instagram-Login host (the app's Instagram use case → User token generator).
    "instagram": [
        "instagram_business_basic",
        "instagram_business_content_publish",
        "instagram_business_manage_comments",
        "instagram_business_manage_messages",
        "instagram_business_manage_insights",
    ],
    # Threads token (the Threads use case → User token generator). Everything the API offers.
    "threads": [
        "threads_basic",
        "threads_content_publish",
        "threads_manage_replies",
        "threads_read_replies",
        "threads_manage_insights",
        "threads_keyword_search",      # search public posts by keyword (a future listening lane)
        "threads_manage_mentions",     # read posts that mention us (the community manager)
        "threads_delete",              # delete our own posts (the owner's "I want to be able to delete it")
        "threads_location_tagging",    # tag a location on a post
        "threads_profile_discovery",   # read public profiles (who replies to us)
    ],
    # Google OAuth consent (one screen, tick every box). Scopes are URLs.
    # 28 Oct 2026: the personal account's read-only token (logs/google_search_token.box) — Search
    # Console is verified under the personal account, which the brand-channel token cannot see.
    "google_search": [
        "https://www.googleapis.com/auth/webmasters.readonly",
        "https://www.googleapis.com/auth/analytics.readonly",
    ],
    "google": [
        "https://www.googleapis.com/auth/youtube",
        "https://www.googleapis.com/auth/youtube.force-ssl",
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
        "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
        "https://www.googleapis.com/auth/webmasters.readonly",
    ],
    "linkedin": ["openid", "profile", "email", "w_member_social"],
    "tiktok": ["user.info.basic", "user.info.profile", "user.info.stats", "video.list", "video.upload", "video.publish"],
    # Telegram has no scopes: these are the bot's admin rights in the channel, ticked once.
    "telegram": ["Post messages", "Edit messages of others", "Delete messages of others", "Post stories",
                 "Edit stories", "Delete stories", "Manage live streams", "Add subscribers", "Invite users via link"],
}

# Meta app-level features — shown once so the owner knows they are not missing anything.
FEATURES = {
    "facebook": ["Page Public Content Access (only for OTHER people's Pages — not needed for ours)",
                 "Business Asset User Profile Access (standard access is enough for our own assets)",
                 "Live Video API (only if we ever go live)"],
    "instagram": ["Instagram Public Content Access (only for other accounts' public content — not needed)"],
}

# Which scopes each lane needs TODAY, so a missing one can be named with its consequence.
USED_BY = {
    "pages_manage_engagement": "replies lane (public replies on Facebook)",
    "pages_messaging": "replies lane (comment → DM on Facebook)",
    "instagram_manage_messages": "replies lane (comment → DM on Instagram, Facebook-Login path)",
    "instagram_business_manage_messages": "replies lane (comment → DM on Instagram)",
    "instagram_business_manage_comments": "replies lane (public replies on Instagram)",
    "instagram_business_manage_insights": "scorecard (Instagram reach, online_followers → the slot plan)",
    "instagram_manage_insights": "scorecard (Instagram insights through the Page token)",
    "read_insights": "scorecard (Facebook Page reach and follows)",
    "threads_manage_replies": "replies lane (answering on Threads)",
    "threads_read_replies": "replies lane (reading Threads replies)",
    "threads_manage_insights": "scorecard (Threads views and followers)",
    "https://www.googleapis.com/auth/yt-analytics.readonly": "youtube_stats lane (watch time, subscribers gained)",
    "https://www.googleapis.com/auth/webmasters.readonly": "youtube_stats lane (Search Console → the brain's prompt)",
    "https://www.googleapis.com/auth/youtube.force-ssl": "every YouTube lane (upload, delete, thumbnails)",
}


def _http(method, url, params=None, data=None, headers=None, timeout=30):
    headers = dict(headers or {})
    headers.setdefault("User-Agent", "DocOga-token-scopes/1.0 (+https://docoga.com.ng)")
    body = None
    if method == "GET" and params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    elif data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw, status = resp.read().decode("utf-8", "replace"), resp.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode("utf-8", "replace"), e.code
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, {"error": {"message": str(e)}}
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, {"error": {"message": raw[:200]}}


def _secret(env, *names):
    """A token from a `*_FILE` path or the variable itself — never logged."""
    for name in names:
        path = env.get(name + "_FILE")
        if path and os.path.isfile(path):
            try:
                return open(path, encoding="utf-8").read().strip()
            except OSError:
                pass
        if env.get(name):
            return env[name].strip()
    return ""


# ─────────────────────────── readers (what the token actually has) ───────────────────────────
def _debug_token(http, host, token, app_token):
    st, body = http("GET", host + "/debug_token", {"input_token": token, "access_token": app_token})
    data = (body or {}).get("data") or {}
    if st != 200 or body.get("error") or not data:
        return None
    scopes = list(data.get("scopes") or [])
    for g in data.get("granular_scopes") or []:
        if g.get("scope") and g["scope"] not in scopes:
            scopes.append(g["scope"])
    return scopes


def read_facebook(env, http=_http):
    token = _secret(env, "FB_PAGE_ACCESS_TOKEN")
    if not token:
        return None, "no-token"
    st, body = http("GET", GRAPH + "/me/permissions", {"access_token": token})
    if st == 200 and isinstance(body.get("data"), list):
        granted = [p["permission"] for p in body["data"] if p.get("status") == "granted"]
        if granted:
            return granted, "me/permissions"
    app_id, app_secret = env.get("META_APP_ID", ""), env.get("META_APP_SECRET", "")
    if app_id and app_secret:
        scopes = _debug_token(http, GRAPH, token, "%s|%s" % (app_id, app_secret))
        if scopes is not None:
            return scopes, "debug_token"
    return None, "unreadable"


def read_instagram(env, http=_http):
    token = _secret(env, "IG_ACCESS_TOKEN")
    if not token:
        return None, "no-token"
    app_id, app_secret = env.get("META_APP_ID", ""), env.get("META_APP_SECRET", "")
    if app_id and app_secret:
        scopes = _debug_token(http, GRAPH, token, "%s|%s" % (app_id, app_secret))
        if scopes is not None:
            return scopes, "debug_token"
    scopes = _debug_token(http, GRAPH_IG, token, token)
    if scopes is not None:
        return scopes, "debug_token (instagram host)"
    return None, "unreadable"


def read_threads(env, http=_http):
    token = _secret(env, "THREADS_ACCESS_TOKEN")
    if not token:
        return None, "no-token"
    scopes = _debug_token(http, GRAPH_THREADS, token, token)
    if scopes is not None:
        return scopes, "debug_token"
    app_id, app_secret = env.get("META_APP_ID", ""), env.get("THREADS_APP_SECRET", "") or env.get("META_APP_SECRET", "")
    if app_id and app_secret:
        scopes = _debug_token(http, GRAPH_THREADS, token, "%s|%s" % (app_id, app_secret))
        if scopes is not None:
            return scopes, "debug_token (app token)"
    return None, "unreadable"


def _vault_refresh_token(env):
    """The refresh token the lanes actually use — logs/yt_refresh_token.box opened with
    SOCIAL_TOKEN_KEY — read through token_vault directly. It used to go through
    yt_publish.vault_refresh_token, and yt_publish imports `requests` at the top: in a job
    that installed only `cryptography` (the Monday scorecard) that import failed quietly,
    the audit fell back to the bootstrap YT_REFRESH_TOKEN secret (the old one-scope token)
    and told the owner for weeks that Google was "short 6 permissions" while every lane
    was fine (27 Oct 2026). Returns "" when there is no key or no box."""
    if not (env.get("SOCIAL_TOKEN_KEY") or os.environ.get("SOCIAL_TOKEN_KEY")):
        return ""
    try:
        import token_vault
        if not token_vault._vault_path("YT_REFRESH_TOKEN").is_file():
            return ""
        plaintext, _payload = token_vault.open_box("YT_REFRESH_TOKEN")
        return (plaintext or "").strip()
    except Exception:  # noqa: BLE001 — a damaged box falls back to the secret, named as such
        return ""


def read_google_search(env, http=_http):
    """The personal account's read-only token: vault box only, no secret fallback."""
    refresh = ""
    if env.get("SOCIAL_TOKEN_KEY"):
        try:
            import token_vault
            if token_vault._vault_path("GOOGLE_SEARCH_TOKEN").is_file():
                refresh = (token_vault.open_box("GOOGLE_SEARCH_TOKEN")[0] or "").strip()
        except Exception:  # noqa: BLE001
            refresh = ""
    cid, csec = env.get("YT_CLIENT_ID", ""), env.get("YT_CLIENT_SECRET", "")
    if not (refresh and cid and csec):
        return None, "no-token"
    st, body = http("POST", "https://oauth2.googleapis.com/token",
                    data={"client_id": cid, "client_secret": csec, "refresh_token": refresh, "grant_type": "refresh_token"})
    access = (body or {}).get("access_token") if st == 200 else None
    if not access:
        return None, "unreadable"
    st, info = http("GET", "https://oauth2.googleapis.com/tokeninfo", {"access_token": access})
    if st != 200 or not info.get("scope"):
        return None, "unreadable"
    return str(info["scope"]).split(), "tokeninfo on the vault (logs/google_search_token.box)"


def read_google(env, http=_http):
    refresh, source = _vault_refresh_token(env), "the vault (logs/yt_refresh_token.box)"
    if not refresh:
        refresh, source = _secret(env, "YT_REFRESH_TOKEN"), "the YT_REFRESH_TOKEN secret (bootstrap — not the vault)"
    cid, csec = env.get("YT_CLIENT_ID", ""), env.get("YT_CLIENT_SECRET", "")
    if not (refresh and cid and csec):
        return None, "no-token"
    st, body = http("POST", "https://oauth2.googleapis.com/token",
                    data={"client_id": cid, "client_secret": csec, "refresh_token": refresh, "grant_type": "refresh_token"})
    access = (body or {}).get("access_token") if st == 200 else None
    if not access:
        return None, "unreadable"
    st, info = http("GET", "https://oauth2.googleapis.com/tokeninfo", {"access_token": access})
    if st != 200 or not info.get("scope"):
        return None, "unreadable"
    return str(info["scope"]).split(), "tokeninfo on " + source


def read_linkedin(env, http=_http):
    token = _secret(env, "LINKEDIN_ACCESS_TOKEN")
    if not token:
        return None, "no-token"
    cid, csec = env.get("LINKEDIN_CLIENT_ID", ""), env.get("LINKEDIN_CLIENT_SECRET", "")
    if not (cid and csec):
        return None, "unreadable"
    st, body = http("POST", "https://www.linkedin.com/oauth/v2/introspectToken",
                    data={"client_id": cid, "client_secret": csec, "token": token})
    if st != 200 or not body.get("scope"):
        return None, "unreadable"
    return [s for s in str(body["scope"]).replace(",", " ").split() if s], "introspectToken"


READERS = {"facebook": read_facebook, "instagram": read_instagram, "threads": read_threads,
           "google": read_google, "google_search": read_google_search, "linkedin": read_linkedin}


# ─────────────────────────── the verdict ───────────────────────────
def compare(name, have):
    want = WANT[name]
    have = set(have or [])
    missing = [s for s in want if s not in have]
    extra = sorted(s for s in have if s not in want and s != "public_profile")
    return {"token": name, "missing": missing, "have": sorted(have), "extra": extra,
            "complete": not missing}


def audit(env=None, http=_http, only=None):
    env = dict(os.environ) if env is None else env
    out = []
    for name, reader in READERS.items():
        if only and name != only:
            continue
        have, how = reader(env, http)
        if have is None:
            out.append({"token": name, "state": how, "missing": [], "have": [], "extra": [], "complete": False, "how": how})
            continue
        row = compare(name, have)
        row.update(state="complete" if row["complete"] else "missing", how=how)
        out.append(row)
    return out


def machine_lines(rows):
    lines = []
    for r in rows:
        if r["state"] == "missing":
            lines.append("SCOPES_%s=missing:%s" % (r["token"].upper(), ",".join(r["missing"])))
        else:
            lines.append("SCOPES_%s=%s" % (r["token"].upper(), r["state"]))
    return lines


def markdown(rows):
    lines = ["### Token permissions — minted once, complete?", ""]
    for r in rows:
        name = r["token"].title()
        if r["state"] == "complete":
            lines.append("- ✅ **%s**: every permission on the list (%d, read via %s)" % (name, len(WANT[r["token"]]), r.get("how")))
        elif r["state"] == "missing":
            short = [s.rsplit("/", 1)[-1] for s in r["missing"]]
            lines.append("- ⚠️ **%s** is short %d permission(s): `%s` (read via %s) — one mint with the full list in docs/TOKENS.md ends this for good"
                         % (name, len(r["missing"]), "`, `".join(short), r.get("how")))
            for s in r["missing"]:
                if s in USED_BY:
                    lines.append("  - `%s` → %s" % (s.rsplit("/", 1)[-1], USED_BY[s]))
        elif r["state"] == "no-token":
            lines.append("- · **%s**: no token in this run (lane dormant)" % name)
        else:
            lines.append("- ❔ **%s**: the platform would not list this token's scopes (%s) — not a failure, just unknown" % (name, r.get("how")))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="the complete permission list per token, and the audit")
    ap.add_argument("command", choices=("list", "audit"))
    ap.add_argument("token", nargs="?", help="facebook | instagram | threads | google | linkedin | tiktok | telegram")
    ap.add_argument("--markdown", help="append the markdown report to this file")
    ap.add_argument("--json", action="store_true", help="print the audit as JSON")
    a = ap.parse_args(argv)
    if a.command == "list":
        for name, scopes in WANT.items():
            if a.token and name != a.token:
                continue
            print("%s (%d):" % (name, len(scopes)))
            for s in scopes:
                print("  %s%s" % (s, ("  — " + USED_BY[s]) if s in USED_BY else ""))
            for f in FEATURES.get(name, []):
                print("  [feature] %s" % f)
            print()
        return 0
    rows = audit(only=a.token)
    for line in machine_lines(rows):
        print(line)
    text = markdown(rows)
    if a.json:
        print(json.dumps(rows, indent=1))
    else:
        print(text, end="")
    if a.markdown:
        try:
            with open(a.markdown, "a", encoding="utf-8") as fh:
                fh.write("\n" + text)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
