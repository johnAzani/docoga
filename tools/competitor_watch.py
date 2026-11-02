#!/usr/bin/env python3
"""competitor_watch.py — what the field published this week, so DocOga writes knowing it.

Owner, 2 Nov 2026: "always research very very in-depth to the thinnest details on things around my
business, always keep me way ahead of my competitors — even in the social media space; I want to
dominate." The Strategy Office charter (docs/STRATEGY_OFFICE.md §8) carries the order; this is the
machine that keeps it every week without a hand:

  * `brain/competitors.json` is the verified field map (names, what they do, public feeds) — written
    from research that was actually read (docs/COMPETITOR_WATCH.md), never guessed.
  * `pull` reads each competitor's PUBLIC feeds — RSS/Atom, sitemaps (lastmod), YouTube channel
    feeds — keeps what moved in the last `days`, and writes `logs/competitor_watch.json`. ₦0:
    stdlib only, no login, one request per feed, a 20 s budget each, never fatal. TikTok and
    Instagram publish no feed at ₦0: those rows say so instead of pretending.
  * `prompt_block` hands the brain THE FIELD: titles only, with the rule — say it better, cite the
    section they did not, take the angle they missed, never copy a headline, never name a rival.
  * `scorecard_lines` is the Monday block "Competitor watch".

Usage
    python3 tools/competitor_watch.py pull [--days 14]
    python3 tools/competitor_watch.py show
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import newsdesk  # noqa: E402 — the feed parser is the same one the papers are read with

FIELD = Path(os.environ.get("DOCOGA_COMPETITORS") or (ROOT / "brain" / "competitors.json"))
OUT = Path(os.environ.get("DOCOGA_COMPETITOR_WATCH") or (ROOT / "logs" / "competitor_watch.json"))
TIMEOUT = 20
MAX_PER_COMPETITOR = 6
MAX_TOTAL = 30
# Only what touches the business: a competitor's cookie recipe is not the field.
TOPIC = re.compile(r"\b(rent|tenan|landlord|lease|quit|evict|agent|agency|caution|deposit|receipt|agreement|"
                   r"premises|housing|property|propert|apartment|flat|house|lagos|abuja|tenancy|lasrera|bill)\w*",
                   re.I)
UA = "DocOga-field/1.0 (+https://docoga.com.ng)"


def _http(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def load_field(path=None):
    try:
        data = json.loads(Path(path or FIELD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = data.get("competitors") if isinstance(data, dict) else data
    return [r for r in (rows or []) if isinstance(r, dict) and r.get("name")]


def _slug_title(url):
    """A sitemap has no titles: the last path piece, de-hyphenated, is the best honest label."""
    path = re.sub(r"[?#].*$", "", url or "").rstrip("/")
    piece = path.rsplit("/", 1)[-1]
    piece = re.sub(r"\.(html?|php)$", "", piece)
    return re.sub(r"[-_]+", " ", piece).strip().capitalize()


def parse_sitemap(source, raw, now, days):
    """<urlset> → [{title, link, published, source}] for entries with a lastmod inside the window.
    A <sitemapindex> is followed one level (its children are fetched by the caller)."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return [], []
    tag = root.tag.rsplit("}", 1)[-1]
    since = now - timedelta(days=days)
    if tag == "sitemapindex":
        children = [newsdesk._text(n, "loc") for n in root if n.tag.rsplit("}", 1)[-1] == "sitemap"]
        return [], [c for c in children if c]
    items = []
    for node in root:
        if node.tag.rsplit("}", 1)[-1] != "url":
            continue
        loc = newsdesk._text(node, "loc")
        when = newsdesk._when(newsdesk._text(node, "lastmod"))
        if not loc or not when or when < since:
            continue
        items.append({"title": _slug_title(loc), "link": loc, "published": when.isoformat(timespec="seconds"),
                      "source": source})
    return items, []


def youtube_feed_for(url, http=None):
    """A channel page → its public Atom feed URL (the channelId is in the page), or None."""
    if "youtube.com" not in (url or ""):
        return None
    m = re.search(r"channel_id=([A-Za-z0-9_-]{10,})", url) or re.search(r"/channel/([A-Za-z0-9_-]{10,})", url)
    if m:
        return "https://www.youtube.com/feeds/videos.xml?channel_id=" + m.group(1)
    try:
        status, raw = (http or _http)(url)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if status != 200:
        return None
    m = re.search(rb'"channelId":"(UC[A-Za-z0-9_-]{10,})"', raw) or re.search(rb"channel_id=(UC[A-Za-z0-9_-]{10,})", raw)
    return ("https://www.youtube.com/feeds/videos.xml?channel_id=" + m.group(1).decode()) if m else None


def _read_feed(source, url, http, now, days, depth=0):
    try:
        status, raw = http(url)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return [], "%s: unreachable (%s)" % (url, str(exc)[:50])
    if status != 200:
        return [], "%s: HTTP %s" % (url, status)
    head = raw[:400].lower()
    if b"<urlset" in head or b"<sitemapindex" in head:
        items, children = parse_sitemap(source, raw, now, days)
        for child in children[:4] if depth == 0 else []:
            more, _ = _read_feed(source, child, http, now, days, depth=1)
            items.extend(more)
        return items, "%s: %d changed page(s)" % (url, len(items))
    rows = newsdesk.parse_feed(source, raw)
    since = now - timedelta(days=days)
    kept = [r for r in rows if r.get("published") and newsdesk._when(r["published"]) and newsdesk._when(r["published"]) >= since]
    return kept, "%s: %d fresh post(s)" % (url, len(kept))


def pull(http=None, now=None, days=14, log=print, field=None):
    http = http or _http
    now = now or datetime.now(timezone.utc)
    items, report, unwatchable = [], [], []
    for comp in (field if field is not None else load_field()):
        feeds = list(comp.get("feeds") or [])
        if not feeds and "youtube.com" in (comp.get("url") or ""):
            yt = youtube_feed_for(comp["url"], http=http)
            if yt:
                feeds.append(yt)
        if not feeds:
            unwatchable.append(comp["name"])
            continue
        mine = []
        for url in feeds[:3]:
            rows, line = _read_feed(comp["name"], url, http, now, days)
            report.append(line)
            mine.extend(rows)
        seen, fresh = set(), []
        for r in sorted(mine, key=lambda r: r.get("published") or "", reverse=True):
            if r["link"] in seen or not TOPIC.search((r.get("title") or "") + " " + (r.get("summary") or "")):
                continue
            seen.add(r["link"])
            fresh.append({"competitor": comp["name"], "kind": comp.get("kind", ""), "title": r["title"][:160],
                          "link": r["link"], "published": r.get("published")})
            if len(fresh) >= MAX_PER_COMPETITOR:
                break
        items.extend(fresh)
    items.sort(key=lambda r: r.get("published") or "", reverse=True)
    for line in report:
        log("field: " + line)
    log("field: %d fresh item(s) from %d feed(s); not watchable at ₦0: %s"
        % (len(items), len(report), ", ".join(unwatchable) or "none"))
    return {"pulled_at": now.isoformat(timespec="seconds"), "days": days, "items": items[:MAX_TOTAL],
            "sources": report, "unwatchable": unwatchable}


def load(path=None):
    try:
        data = json.loads(Path(path or OUT).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"items": []}
    except (OSError, ValueError):
        return {"items": []}


def fresh_items(data=None, now=None, max_age_days=10):
    """This week's field, or [] when the pull is older than `max_age_days` (a stale field misleads)."""
    data = data if data is not None else load()
    now = now or datetime.now(timezone.utc)
    when = newsdesk._when(data.get("pulled_at"))
    if not when or when < now - timedelta(days=max_age_days):
        return []
    return list(data.get("items") or [])


def prompt_block(items, field=None):
    """THE FIELD for the brain's prompt: what rivals published, and the standing edge to press."""
    field = field if field is not None else load_field()
    lines = ["THE FIELD — what the competition published lately (titles only). Your job: say it better, "
             "cite the section they did not, take the angle they missed. Never copy a headline, never name "
             "a rival or a rival's price in copy."]
    if items:
        lines += ["- %s: %s%s" % (it["competitor"], it["title"], (" (" + it["published"][:10] + ")") if it.get("published") else "")
                  for it in items[:12]]
    else:
        lines.append("- (nothing new from the field this week — lead, do not follow)")
    tools = [c for c in field if c.get("kind") == "tool"]
    if tools:
        lines.append("DocOga's standing edge over the %d document tools on the field: every line cited to the state's own "
                     "section, Nigerian English, one price, no watermark, no account — write like the only one who read the law."
                     % len(tools))
    return "\n".join(lines)


def scorecard_lines(data=None, now=None):
    data = data if data is not None else load()
    items = fresh_items(data, now=now)
    if not data.get("pulled_at"):
        return ["- not pulled yet — the brain's Monday run writes logs/competitor_watch.json"]
    by = {}
    for it in items:
        by.setdefault(it["competitor"], []).append(it)
    lines = ["- field pulled %s: %d item(s) from %d competitor(s); not watchable at ₦0: %s"
             % (str(data.get("pulled_at", ""))[:10], len(items), len(by), ", ".join(data.get("unwatchable") or []) or "none")]
    for name, rows in sorted(by.items(), key=lambda kv: -len(kv[1]))[:6]:
        lines.append("- %s — %s" % (name, "; ".join(r["title"][:70] for r in rows[:3])))
    if not items:
        lines.append("- nothing new on the field this window — DocOga posted every day of it")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description="what the field published this week")
    ap.add_argument("command", choices=("pull", "show"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args(argv)
    if a.command == "show":
        for it in fresh_items():
            print("%s  %s — %s" % ((it.get("published") or "")[:10], it["competitor"], it["title"]))
        return 0
    data = pull(days=a.days)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote %s (%d items)" % (a.out, len(data["items"])))
    print("FIELD_ITEMS=%d" % len(data["items"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
