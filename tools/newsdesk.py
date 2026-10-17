#!/usr/bin/env python3
"""newsdesk.py — what Nigeria is talking about, so the brain opens with today, not with a textbook.

Research (17 Oct 2026): the stories moving the rent conversation this month were a Lagos
landlord punched over a ₦200k→₦350k hike, Abuja rents up 40–120% in two years with fees
eating 20–30% of the package, and the Lagos 5%-agency-fee bill — still a bill, not law.
A manager who does not know that is writing for last year. This tool reads the free RSS
feeds of the Nigerian papers, keeps the stories about rent, tenants, landlords, agents,
eviction, salaries and small-business paperwork, scores them, and writes brain/newsdesk.json.
The brain's prompt shows the top stories as OPENING LINES ONLY: the law still comes from the
shelf, a cited section is still required, and the lint refuses any `news_hook` that is not
one of these headlines — so the model can never invent a story.

₦0: stdlib only, public feeds, one request per paper, 20 s budget each, never fatal.

Usage
    python3 tools/newsdesk.py pull [--out brain/newsdesk.json] [--days 7]
    python3 tools/newsdesk.py show
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("DOCOGA_NEWSDESK") or (ROOT / "brain" / "newsdesk.json"))

FEEDS = (
    ("Punch", "https://punchng.com/feed/"),
    ("Vanguard", "https://www.vanguardngr.com/feed/"),
    ("BusinessDay", "https://businessday.ng/feed/"),
    ("TheCable", "https://www.thecable.ng/feed"),
    ("Premium Times", "https://www.premiumtimesng.com/feed"),
    ("The Guardian Nigeria", "https://guardian.ng/feed/"),
    ("Nairametrics", "https://nairametrics.com/feed/"),
)

# Weighted keywords. A story is kept when it scores >= KEEP; the title counts triple.
STRONG = {"tenant": 3, "tenants": 3, "landlord": 3, "landlords": 3, "tenancy": 3, "rent": 2, "rents": 2,
          "eviction": 3, "evicted": 3, "quit notice": 3, "notice to quit": 3, "agency fee": 3, "agent fee": 3,
          "caution fee": 3, "caution deposit": 3, "lasrera": 3, "estate agent": 2, "estate agents": 2,
          "rent control": 3, "tenancy law": 3, "tenancy bill": 3, "recovery of premises": 3}
WEAK = {"housing": 1, "accommodation": 1, "lease": 1, "apartment": 1, "flat": 0, "salary": 1, "salaries": 1,
        "payslip": 2, "minimum wage": 2, "invoice": 1, "sme": 1, "small business": 1, "power of attorney": 2,
        "affidavit": 1, "nysc": 1, "lagos": 0, "abuja": 0}
NOISE = ("football", "premier league", "super eagles", "afcon", "bbnaija", "transfer window", "grammy")
KEEP = 4
TOP = 8
TIMEOUT = 20


def _http(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": "DocOga-newsdesk/1.0 (+https://docoga.com.ng)",
                                               "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def _text(node, *names):
    for name in names:
        for child in node:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == name:
                return (child.text or "").strip()
    return ""


def _when(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _strip(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", html.unescape(s)).strip()
    return re.sub(r"\s+([,.;:!?…])", r"\1", s)


def parse_feed(source, raw):
    """RSS 2.0 or Atom → [{title, link, summary, published, source}]."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    items = []
    nodes = root.iter("item")
    rows = list(nodes)
    if not rows:
        rows = [n for n in root.iter() if n.tag.rsplit("}", 1)[-1] == "entry"]
    for node in rows:
        title = _strip(_text(node, "title"))
        link = _text(node, "link")
        if not link:
            for child in node:
                if child.tag.rsplit("}", 1)[-1] == "link" and child.get("href"):
                    link = child.get("href")
                    break
        summary = _strip(_text(node, "description", "summary", "content"))[:400]
        published = _when(_text(node, "pubDate", "published", "updated", "date"))
        if title and link:
            items.append({"title": title, "link": link.strip(), "summary": summary,
                          "published": published.isoformat(timespec="seconds") if published else None, "source": source})
    return items


def score(item):
    title = item["title"].lower()
    body = (item.get("summary") or "").lower()
    if any(n in title for n in NOISE):
        return 0, []
    total, matched = 0, []
    for word, w in list(STRONG.items()) + list(WEAK.items()):
        if not w:
            continue
        in_title = word in title
        in_body = word in body
        if in_title or in_body:
            total += w * (3 if in_title else 1)
            matched.append(word)
    return total, matched


def select(items, now=None, days=7, top=TOP):
    now = now or datetime.now(timezone.utc)
    floor = now - timedelta(days=days)
    out, seen = [], set()
    for it in items:
        when = _when(it.get("published")) if it.get("published") else None
        if when and when < floor:
            continue
        s, matched = score(it)
        if s < KEEP:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", it["title"].lower()).strip()[:60]
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(it, score=s, matched=matched))
    out.sort(key=lambda r: (-r["score"], r.get("published") or ""))
    return out[:top]


def pull(http=None, now=None, days=7, log=print, feeds=FEEDS):
    http = http or _http
    items, report = [], []
    for source, url in feeds:
        try:
            status, raw = http(url)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            report.append("%s: unreachable (%s)" % (source, str(exc)[:60]))
            continue
        if status != 200:
            report.append("%s: HTTP %s" % (source, status))
            continue
        rows = parse_feed(source, raw)
        report.append("%s: %d stories" % (source, len(rows)))
        items.extend(rows)
    picked = select(items, now=now, days=days)
    for line in report:
        log("newsdesk: " + line)
    log("newsdesk: %d candidate(s), %d kept" % (len(items), len(picked)))
    return {"fetched": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
            "sources": report, "items": [{k: v for k, v in r.items() if k != "summary"} | {"summary": r.get("summary", "")[:200]}
                                          for r in picked]}


def load(path=None):
    try:
        data = json.loads(Path(path or OUT).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"items": []}
    except (OSError, ValueError):
        return {"items": []}


PINNED = Path(os.environ.get("DOCOGA_NEWSDESK_PINNED") or (ROOT / "brain" / "newsdesk_pinned.json"))
PINNED_MAX_AGE_DAYS = 21


def pinned_items(path=None, now=None, max_age_days=PINNED_MAX_AGE_DAYS):
    """Hand-dated stories the research pass found (17 Oct 2026): each carries its own date and
    paper and expires on its own — a three-week-old rent story is still the talk of a WhatsApp
    group, a two-month-old one is not. Never raises; a missing or broken file is no stories."""
    now = now or datetime.now(timezone.utc)
    try:
        rows = json.loads(Path(path or PINNED).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for it in rows if isinstance(rows, list) else (rows.get("items") or []):
        when = _when(str(it.get("published") or "") + ("T12:00:00+00:00" if len(str(it.get("published") or "")) == 10 else ""))
        if not it.get("title") or not when or (now - when) > timedelta(days=max_age_days):
            continue
        out.append({"title": it["title"], "source": it.get("source", ""), "published": str(it.get("published"))[:10],
                    "link": it.get("link", ""), "score": int(it.get("score") or 50), "pinned": True})
    return out


def fresh_items(data=None, now=None, max_age_days=7, pinned=None):
    """The headlines the brain may open with — the RSS pull when it is recent, plus the pinned
    shelf; pinned stories come first because a human dated and read them."""
    data = load() if data is None else data
    now = now or datetime.now(timezone.utc)
    fetched = _when(data.get("fetched"))
    pulled = []
    if fetched and (now - fetched) <= timedelta(days=max_age_days):
        pulled = [it for it in data.get("items") or [] if it.get("title")]
    pins = pinned_items(now=now) if pinned is None else pinned
    titles = {p["title"] for p in pins}
    return pins + [it for it in pulled if it["title"] not in titles]


def prompt_block(items):
    if not items:
        return "(no fresh stories — open with the reader's situation, not the news)"
    return "\n".join("- %s — %s%s" % (it["title"], it.get("source", ""),
                                       (" (" + it["published"][:10] + ")") if it.get("published") else "")
                     for it in items)


def main(argv=None):
    ap = argparse.ArgumentParser(description="what Nigeria is talking about")
    ap.add_argument("command", choices=("pull", "show"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args(argv)
    if a.command == "show":
        for it in fresh_items():
            print("%2d  %s — %s" % (it.get("score", 0), it["title"], it.get("source", "")))
        return 0
    data = pull(days=a.days)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote %s (%d stories)" % (a.out, len(data["items"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
