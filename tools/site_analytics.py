#!/usr/bin/env python3
"""site_analytics.py — who sends readers to docoga.com.ng, from Cloudflare Web Analytics (₦0).

Cloudflare's Web Analytics is a cookieless browser beacon (no consent banner, no Google)
with a GraphQL dataset — `rumPageloadEventsAdaptiveGroups` — that answers "visits by
referring host and by page" for six months, on the free plan. The Monday scorecard reads
it so the brain can see which channel actually moves people to which tool page, next to
the worker's "checkout taps and verified sales by channel tag" counters.

Needs (all read-only):
  CLOUDFLARE_ACCOUNT_ID                 already a repo secret
  CF_ANALYTICS_TOKEN                    API token with *Account Analytics: Read*
                                        (falls back to CLOUDFLARE_API_TOKEN if it has that scope)
  CF_WEB_ANALYTICS_SITE_TAG (optional)  the siteTag from the beacon snippet, when the account
                                        has more than one site
Without them the pull reports "not connected" and nothing else changes.

    python3 tools/site_analytics.py [--days 7] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"
HOST = os.environ.get("DOCOGA_SITE_HOST", "docoga.com.ng")
CHANNEL_HOSTS = (
    ("t.me", "telegram"), ("telegram.org", "telegram"), ("telegram.me", "telegram"),
    ("facebook.com", "facebook"), ("fb.com", "facebook"), ("fb.me", "facebook"), ("messenger.com", "facebook"),
    ("instagram.com", "instagram"), ("threads.net", "threads"), ("threads.com", "threads"),
    ("linkedin.com", "linkedin"), ("lnkd.in", "linkedin"), ("youtube.com", "youtube"), ("youtu.be", "youtube"),
    ("tiktok.com", "tiktok"), ("whatsapp.com", "whatsapp"), ("whatsapp.net", "whatsapp"), ("wa.me", "whatsapp"),
    ("google.", "google"), ("bing.com", "search"), ("duckduckgo.com", "search"), ("yahoo.", "search"),
    ("x.com", "x"), ("twitter.com", "x"), ("t.co", "x"), ("nairaland.com", "nairaland"),
)
QUERY = """
query Docoga($account: String!, $filter: AccountRumPageloadEventsAdaptiveGroupsFilter_InputObject!) {
  viewer { accounts(filter: {accountTag: $account}) {
    total: rumPageloadEventsAdaptiveGroups(filter: $filter, limit: 1) { count sum { visits } }
    referers: rumPageloadEventsAdaptiveGroups(filter: $filter, limit: 200, orderBy: [sum_visits_DESC]) {
      count sum { visits } dimensions { refererHost } }
    paths: rumPageloadEventsAdaptiveGroups(filter: $filter, limit: 200, orderBy: [sum_visits_DESC]) {
      count sum { visits } dimensions { requestPath } }
    countries: rumPageloadEventsAdaptiveGroups(filter: $filter, limit: 20, orderBy: [sum_visits_DESC]) {
      count sum { visits } dimensions { countryName } }
  } }
}"""


def channel_for(host):
    h = (host or "").lower().strip()
    if not h:
        return "direct"
    if h == HOST or h.endswith("." + HOST):
        return "internal"
    for needle, name in CHANNEL_HOSTS:
        if needle in h:
            return name
    return "other"


def _post(token, body, timeout=40):
    req = urllib.request.Request(GRAPHQL, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace") or "{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, {"errors": [{"message": str(e)}]}


http = _post

# The Web Analytics beacon Cloudflare injects into every page: its "token" IS the site tag.
BEACON_RE = re.compile(r'data-cf-beacon=[\'"]\{[^}]*?"token"\s*:\s*"([0-9a-f]{20,40})"', re.I)
RUM_SITES = "https://api.cloudflare.com/client/v4/accounts/%s/rum/site_info/list"


def _get(url, token=None, timeout=15):
    headers = {"User-Agent": "docoga-site-analytics/1 (+https://docoga.com.ng)", "Accept": "*/*"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(400000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(4000).decode("utf-8", "replace")
        except OSError:
            return e.code, ""
    except (urllib.error.URLError, OSError, ValueError):
        return 0, ""


fetch = _get


def discover_site_tag(account, token, host=HOST):
    """The Web Analytics *site tag* the GraphQL filter wants (not the account id, not the zone id).

    Cloudflare's dashboard always sends one, and without it the RUM dataset answers
    "unable to execute query". Two ₦0 ways to learn it, no extra tap from the owner:
      1. the account's Web Analytics site list (REST, same read-only token);
      2. the beacon the site itself serves — its data-cf-beacon token is the site tag.
    Returns "" when neither works; the caller then queries without the filter.
    """
    status, text = fetch(RUM_SITES % account, token)
    if status == 200:
        try:
            sites = (json.loads(text) or {}).get("result") or []
        except ValueError:
            sites = []
        for s in sites:
            h = (s.get("host") or "").lower().strip()
            if h in (host, "www." + host) and s.get("site_tag"):
                return str(s["site_tag"])
        if len(sites) == 1 and sites[0].get("site_tag"):
            return str(sites[0]["site_tag"])
    status, html = fetch("https://%s/" % host)
    m = BEACON_RE.search(html or "")
    return m.group(1) if m else ""


def pull(env=None, days=7, now=None):
    """→ dict or (None, reason). Visits by channel, by page, by country, for the last `days`."""
    env = dict(os.environ) if env is None else env
    account = (env.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    token = (env.get("CF_ANALYTICS_TOKEN") or env.get("CLOUDFLARE_API_TOKEN") or "").strip()
    if not (account and token):
        return None, "site: CF_ANALYTICS_TOKEN (Account Analytics: Read) not set — visits by channel not connected"
    now = now or datetime.now(timezone.utc)
    flt = {"datetime_geq": (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "datetime_leq": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "requestHost": HOST}
    site_tag = (env.get("CF_WEB_ANALYTICS_SITE_TAG") or "").strip() or discover_site_tag(account, token)
    if site_tag:
        flt["siteTag"] = site_tag
    # One call normally. "try again later" is Cloudflare's transient 503 → one retry after a
    # pause; an "unknown field" on an optional filter → drop it and retry once. Never more.
    attempts, status, data, errors = 0, 0, {}, []
    while attempts < 3:
        attempts += 1
        status, data = http(token, {"query": QUERY, "variables": {"account": account, "filter": flt}})
        errors = data.get("errors") or []
        if status == 200 and not errors:
            break
        msg = ((errors[0].get("message") if errors else "") or "").lower()
        if "try again later" in msg and attempts < 3:
            time.sleep(4)
            continue
        break
    if status != 200 or errors:
        msg = (errors[0].get("message") if errors else "HTTP %s" % status) or "unknown"
        hint = " — the token needs Account Analytics: Read" if "auth" in msg.lower() or status in (401, 403) else ""
        where = " [siteTag %s]" % (site_tag[:6] + "…" if site_tag else "not found — set CF_WEB_ANALYTICS_SITE_TAG")
        return None, "site: Cloudflare analytics refused (%s)%s%s" % (msg[:120], hint, where)
    accounts = ((data.get("data") or {}).get("viewer") or {}).get("accounts") or []
    if not accounts:
        return None, "site: Cloudflare returned no account — check CLOUDFLARE_ACCOUNT_ID"
    acc = accounts[0]
    total = (acc.get("total") or [{}])[0] if acc.get("total") else {}
    by_channel, by_host = {}, {}
    for row in acc.get("referers") or []:
        host = (row.get("dimensions") or {}).get("refererHost") or ""
        visits = int((row.get("sum") or {}).get("visits") or 0)
        ch = channel_for(host)
        if ch == "internal":
            continue
        by_channel[ch] = by_channel.get(ch, 0) + visits
        if host:
            by_host[host] = by_host.get(host, 0) + visits
    by_path = {}
    for row in acc.get("paths") or []:
        path = (row.get("dimensions") or {}).get("requestPath") or "/"
        by_path[path] = by_path.get(path, 0) + int((row.get("sum") or {}).get("visits") or 0)
    by_country = {}
    for row in acc.get("countries") or []:
        c = (row.get("dimensions") or {}).get("countryName") or "?"
        by_country[c] = by_country.get(c, 0) + int((row.get("sum") or {}).get("visits") or 0)
    nigeria = by_country.get("Nigeria", 0) + by_country.get("NG", 0)   # the dataset answers ISO codes ("NG")
    all_c = sum(by_country.values()) or 0
    return {"days": days, "site_tag": site_tag or None,
            "visits": int((total.get("sum") or {}).get("visits") or 0), "pageviews": int(total.get("count") or 0),
            "by_channel": dict(sorted(by_channel.items(), key=lambda kv: -kv[1])),
            "by_host": dict(sorted(by_host.items(), key=lambda kv: -kv[1])[:15]),
            "by_path": dict(sorted(by_path.items(), key=lambda kv: -kv[1])[:20]),
            "nigeria_share": round(nigeria / all_c, 3) if all_c else None}, None


def main(argv=None):
    ap = argparse.ArgumentParser(description="visits to docoga.com.ng by channel (Cloudflare Web Analytics)")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    data, problem = pull(days=a.days)
    if problem:
        print("::notice title=Site analytics::%s" % problem)
        print("SITE_ANALYTICS=not-connected")
        return 0
    if a.json:
        print(json.dumps(data, indent=1))
    else:
        print("%d visits / %d pageviews in %d days; Nigeria share %s" % (data["visits"], data["pageviews"], a.days, data["nigeria_share"]))
        print("by channel:")
        for ch, n in data["by_channel"].items():
            print("  %-10s %d" % (ch, n))
        print("top pages:")
        for path, n in list(data["by_path"].items())[:10]:
            print("  %-40s %d" % (path[:40], n))
    print("SITE_ANALYTICS=ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
