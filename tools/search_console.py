#!/usr/bin/env python3
"""search_console.py — what Nigerians type into Google before they find us (₦0, weekly).

docoga.com.ng is verified in Google Search Console. The Search Analytics API returns, for
the last 28 days, the queries Google showed us for, the page it showed, clicks, impressions
and the average position — the only free, first-party demand data there is. The brain uses
it two ways: the Monday scorecard grades Google clicks like any other channel, and the
"striking distance" list (queries at positions 5–20 with real impressions) becomes posts and
Shorts that answer the question in their first line, linking the page Google already ranks.

Same Google OAuth client and refresh token as the YouTube lane. The token must carry
`https://www.googleapis.com/auth/webmasters.readonly` — one re-consent that also adds
`yt-analytics.readonly` (docs/BRAIN.md). Without the scope Google answers 403; this tool
prints `SEARCH_CONSOLE=missing-scope` and writes nothing, and the scorecard says so.

    python3 tools/search_console.py [--days 28] [--out logs/search_console.json]
Exit 0 always (a data pull must never redden the stats lane); machine line SEARCH_CONSOLE=…
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import yt_publish  # noqa: E402  the OAuth client, the refresh flow, the Http wrapper

API = "https://searchconsole.googleapis.com/webmasters/v3/sites/%s/searchAnalytics/query"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
OUT = ROOT / "logs" / "search_console.json"
SITES = ("sc-domain:docoga.com.ng", "https://docoga.com.ng/")
STRIKING = (5.0, 20.0)      # average position window where one good page jumps to page one
MIN_IMPRESSIONS = 20


def query(http, site, body):
    from urllib.parse import quote
    r = http.request("POST", API % quote(site, safe=""), headers={"Content-Type": "application/json"},
                     data=json.dumps(body))
    try:
        payload = r.json()
    except ValueError:
        payload = {"raw": (r.text or "")[:200]}
    return r.status_code, payload


def rows_to_queries(rows):
    out = []
    for row in rows or []:
        keys = row.get("keys") or []
        out.append({"query": keys[0] if keys else "", "page": keys[1] if len(keys) > 1 else "",
                    "clicks": int(row.get("clicks") or 0), "impressions": int(row.get("impressions") or 0),
                    "ctr": round(float(row.get("ctr") or 0), 4), "position": round(float(row.get("position") or 0), 1)})
    return out


def striking_distance(queries):
    picks = [q for q in queries if STRIKING[0] <= q["position"] <= STRIKING[1] and q["impressions"] >= MIN_IMPRESSIONS]
    return sorted(picks, key=lambda q: -q["impressions"])[:10]


def pull(http, days=28, today=None):
    today = today or dt.date.today()
    end = today - dt.timedelta(days=3)          # Search Console finalises data ~2 days late
    start = end - dt.timedelta(days=days)
    base = {"startDate": start.isoformat(), "endDate": end.isoformat(), "dataState": "final"}
    last = None
    for site in SITES:
        status, totals = query(http, site, dict(base, dimensions=["country"], rowLimit=10))
        message = str((totals.get("error") or {}).get("message") or json.dumps(totals))[:160]
        if status == 403 and "scope" in message.lower():
            return None, "missing-scope", message
        if status in (403, 404):      # this property shape is not ours (or not shared) — try the other
            last = (status, totals)
            continue
        if status != 200:
            return None, "api-%s" % status, json.dumps(totals)[:160]
        status, by_query = query(http, site, dict(base, dimensions=["query", "page"], rowLimit=250,
                                                  dimensionFilterGroups=[{"filters": [{"dimension": "country", "operator": "equals", "expression": "nga"}]}]))
        if status != 200:
            return None, "api-%s" % status, json.dumps(by_query)[:160]
        status, by_page = query(http, site, dict(base, dimensions=["page"], rowLimit=50))
        pages = [{"page": (r.get("keys") or [""])[0], "clicks": int(r.get("clicks") or 0), "impressions": int(r.get("impressions") or 0),
                  "position": round(float(r.get("position") or 0), 1)} for r in (by_page.get("rows") or [])] if status == 200 else []
        countries = {(r.get("keys") or ["?"])[0]: int(r.get("clicks") or 0) for r in (totals.get("rows") or [])}
        clicks = sum(countries.values())
        impressions = sum(int(r.get("impressions") or 0) for r in (totals.get("rows") or []))
        queries = rows_to_queries(by_query.get("rows"))
        queries.sort(key=lambda q: (-q["clicks"], -q["impressions"]))
        return {"taken_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "site": site,
                "window": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
                "clicks": clicks, "impressions": impressions, "ctr": round(clicks / impressions, 4) if impressions else 0.0,
                "nigeria_clicks": countries.get("nga", 0), "top_queries": queries[:40], "striking_distance": striking_distance(queries),
                "top_pages": pages[:25]}, "ok", ""
    return None, "no-property", json.dumps(last[1])[:160] if last else "neither property answered"


def main(argv=None):
    ap = argparse.ArgumentParser(description="pull Google Search Console demand data for docoga.com.ng")
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    try:
        http, _ = yt_publish.authorize()
    except yt_publish.Problem as p:
        print("::notice title=Search Console skipped::%s" % p.what[:160])
        print("SEARCH_CONSOLE=no-token")
        return 0
    data, state, detail = pull(http, days=a.days)
    if state == "missing-scope":
        print("::notice title=Search Console needs one re-consent::the Google token has no webmasters.readonly — redo the "
              "YouTube consent once with the extra scope (docs/BRAIN.md → Google re-consent) and Google's queries feed the brain. %s" % detail)
        print("SEARCH_CONSOLE=missing-scope")
        return 0
    if state != "ok":
        print("::notice title=Search Console not read (%s)::%s" % (state, detail))
        print("SEARCH_CONSOLE=%s" % state)
        return 0
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Search Console: %d clicks / %d impressions in %d days (%s); %d striking-distance queries"
          % (data["clicks"], data["impressions"], a.days, data["site"], len(data["striking_distance"])))
    for q in data["striking_distance"][:5]:
        print("  pos %4.1f  %5d imp  %s" % (q["position"], q["impressions"], q["query"]))
    print("SEARCH_CONSOLE=ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
