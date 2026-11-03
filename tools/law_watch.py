#!/usr/bin/env python3
"""law_watch.py — the bills that would change our pages, read in the news every week, by a machine.

Why (3 Nov 2026). Four of the states we publish carry a bill that would change what the page says
the day it passes: the FCT advance-rent bill HB.2839 (first reading 22 Oct 2026), the Lagos Tenancy
and Recovery of Premises Bill 2025 (committee stage since July 2025), the Enugu Landlord and Tenant
(Amendment) Bill (executive bill promised within four weeks of 26 Oct 2026) and the Anambra rent and
tenancy law the Governor says is coming. Every one of our pages says "a bill, not law, as at
3 November 2026" — true today, and a lie the morning after assent if nobody is reading. The owner
has no time to read four states' news every week; the shelf's `pending_bill.watch` block says what
to read for, and this lane reads it.

What it does — and what it refuses to do:
  * `pull` asks two free news indexes (Google News RSS, Bing News RSS — public, no key, ₦0) for each
    bill's queries, keeps the last `days` of items that are about rent in that state, and classifies
    each headline: `passed` (assent, signed into law, third reading, "Assembly passes … bill"),
    `moving` (second reading, public hearing, committee) or `mention`.
  * It writes `logs/law_watch.json` (heartbeat shape: `entries[]` with `recorded_at`) and prints
    `LAW_WATCH_ALERTS=N`. The workflow opens one issue labelled `law-watch` when N > 0.
  * It NEVER edits a page, a shelf text or a `verified` date. A passage headline is a signal to a
    person who then reads the gazette, moves `watch.verified`, and rewrites the block from the text
    of the law. "Rule Zero" (docs/STATE_TENANCY_RESEARCH.md) is kept by hand, on purpose.

Usage
    python3 tools/law_watch.py pull [--days 14] [--out logs/law_watch.json]
    python3 tools/law_watch.py show
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import newsdesk  # noqa: E402 — the same RSS parser the papers are read with
import state_law_data as law  # noqa: E402

OUT = Path(os.environ.get("DOCOGA_LAW_WATCH") or (ROOT / "logs" / "law_watch.json"))
TIMEOUT = 20
MAX_PER_BILL = 8
KEEP_RUNS = 16
UA = "DocOga-lawwatch/1.0 (+https://docoga.com.ng)"

# Two public news indexes, no key. Google's wants the Nigeria edition; Bing's takes a format flag.
INDEXES = (
    ("Google News", "https://news.google.com/rss/search?q=%s&hl=en-NG&gl=NG&ceid=NG:en"),
    ("Bing News", "https://www.bing.com/news/search?q=%s&format=RSS"),
)

# A headline is about one of our bills only if it is about tenancy AND about that place.
TOPIC = re.compile(r"\b(rent|tenan\w*|landlord\w*|agency fee\w*|agent\w*|caution|premises|housing|lease)\b", re.I)
PLACE = {
    "abuja": ("abuja", "fct", "federal capital", "hb.2839", "hb 2839", "reps", "house of representatives"),
    "lagos": ("lagos", "lasrera", "ikeja", "alausa"),
    "anambra": ("anambra", "soludo", "awka", "onitsha"),
    "enugu": ("enugu", "mbah", "nkanu"),
}
# Passage words. "passed first reading" is movement, not passage, so the readings are carved out.
PASSED = re.compile(r"\b(signed into law|assent(?:ed|s)?\b|passed into law|third reading|becomes? law|"
                    r"now law|gazetted|enacted|signs? (?:the )?(?:\w+ ){0,4}bill)\b", re.I)
PASSES_BILL = re.compile(r"\bpass(?:es|ed)\b(?:(?!reading).){0,40}\b(bill|law)\b", re.I)
READING = re.compile(r"\b(first|second) reading\b", re.I)
MOVING = re.compile(r"\b(second reading|public hearing|committee|first reading|clause|debate|"
                    r"concurrence|transmitted|harmonis)\w*", re.I)


def _http(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def bills():
    """[(slug, bill)] from the shelf — the shelf is the only list; nothing is watched that no page says."""
    return law.pending_bills()


def classify(title, summary=""):
    text = "%s %s" % (title or "", summary or "")
    if PASSED.search(text) or (PASSES_BILL.search(text) and not READING.search(title or "")):
        return "passed"
    if MOVING.search(text):
        return "moving"
    return "mention"


def relevant(slug, title, summary=""):
    text = "%s %s" % (title or "", summary or "")
    low = text.lower()
    return bool(TOPIC.search(text)) and any(p in low for p in PLACE.get(slug, (slug,)))


def _strip_source(title):
    """Google News titles end ' - Punch Newspapers'; the paper goes in `source`, not the headline."""
    m = re.match(r"^(.*\S)\s+[-–—]\s+([^-–—]{2,40})$", title or "")
    return (m.group(1), m.group(2)) if m else (title or "", "")


def _read(index_name, url, http, now, days):
    try:
        status, raw = http(url)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        return [], "%s: unreachable (%s)" % (index_name, exc.__class__.__name__)
    if status != 200:
        return [], "%s: HTTP %s" % (index_name, status)
    rows = newsdesk.parse_feed(index_name, raw)
    floor = (now - timedelta(days=days)).isoformat()
    kept = [r for r in rows if not r.get("published") or r["published"] >= floor]
    return kept, "%s: %d item(s), %d in window" % (index_name, len(rows), len(kept))


def pull(http=None, now=None, days=14, log=print, watch=None, previous=None):
    http = http or _http
    now = now or datetime.now(timezone.utc)
    previous = previous if previous is not None else load()
    first_seen = {it["link"]: it.get("first_seen") for b in previous.get("bills") or [] for it in b.get("items") or []}
    report, out = [], []
    for slug, bill in (watch if watch is not None else bills()):
        wb = bill.get("watch") or {}
        verified = str(wb.get("verified") or "")
        seen, items = set(), []
        for query in (wb.get("queries") or [])[:3]:
            q = urllib.parse.quote_plus(query)
            for index_name, pattern in INDEXES:
                rows, line = _read(index_name, pattern % q, http, now, days)
                report.append("%s/%s: %s" % (slug, query[:30], line))
                for r in rows:
                    title, paper = _strip_source(r["title"])
                    if r["link"] in seen or not relevant(slug, title, r.get("summary")):
                        continue
                    seen.add(r["link"])
                    items.append({"title": title[:160], "source": paper or r.get("source") or index_name,
                                  "link": r["link"], "published": r.get("published"),
                                  "signal": classify(title, r.get("summary")),
                                  "first_seen": first_seen.get(r["link"]) or now.isoformat(timespec="seconds")})
        # Passage first, then movement, newest first inside each — the top row is the one that matters.
        items.sort(key=lambda it: it.get("published") or "", reverse=True)
        items.sort(key=lambda it: {"passed": 0, "moving": 1, "mention": 2}[it["signal"]])
        items = items[:MAX_PER_BILL]
        # An alert is a passage headline newer than the day a person last verified the stage: once the
        # shelf is re-read and `verified` moves past it, the same headline stops shouting.
        alerts = [it for it in items if it["signal"] == "passed" and (it.get("published") or "")[:10] > verified]
        signal = "passed" if alerts else ("moving" if any(it["signal"] == "moving" for it in items) else "quiet")
        out.append({"slug": slug, "state": law.STATE_LAW[slug]["name"], "title": bill.get("title", ""),
                    "verified": verified, "stage": wb.get("stage", ""), "signal": signal,
                    "alerts": len(alerts), "items": items})
        log("law watch: %s — %s, %d item(s), %d alert(s)" % (slug, signal, len(items), len(alerts)))
    for line in report:
        log("law watch: " + line)
    total = sum(b["alerts"] for b in out)
    entry = {"recorded_at": now.isoformat(timespec="seconds"), "alerts": total,
             "signals": {b["slug"]: b["signal"] for b in out}}
    entries = ([e for e in previous.get("entries") or [] if isinstance(e, dict)] + [entry])[-KEEP_RUNS:]
    return {"pulled_at": entry["recorded_at"], "days": days, "alerts": total, "bills": out,
            "entries": entries, "sources": report}


def load(path=None):
    try:
        data = json.loads(Path(path or OUT).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"bills": [], "entries": []}
    except (OSError, ValueError):
        return {"bills": [], "entries": []}


def alert_lines(data=None):
    data = data if data is not None else load()
    lines = []
    for b in data.get("bills") or []:
        for it in b.get("items") or []:
            if it["signal"] == "passed" and (it.get("published") or "")[:10] > str(b.get("verified") or ""):
                lines.append("%s — %s (%s, %s) %s" % (b["state"], it["title"], it.get("source", ""),
                                                      (it.get("published") or "")[:10], it["link"]))
    return lines


def signature(data=None):
    """The alert set as a short stable string: the workflow comments instead of filing twice."""
    import hashlib
    return hashlib.sha1("\n".join(sorted(alert_lines(data))).encode("utf-8")).hexdigest()[:10]


def scorecard_lines(data=None, now=None, max_age_days=10):
    data = data if data is not None else load()
    if not data.get("pulled_at"):
        return ["- not pulled yet — the Thursday lane writes logs/law_watch.json"]
    if data.get("seeded"):
        return ["- seeded %s, no news read yet — the first Thursday pull writes the real ledger; %d bill(s) watched: %s"
                % (str(data["pulled_at"])[:10], len(data.get("bills") or []),
                   ", ".join(b["state"] for b in data.get("bills") or []))]
    now = now or datetime.now(timezone.utc)
    stale = ""
    try:
        age = (now - datetime.fromisoformat(data["pulled_at"])).days
        if age > max_age_days:
            stale = " ⚠️ %d days old" % age
    except (TypeError, ValueError):
        pass
    lines = ["- pulled %s%s: %d bill(s) watched, %d passage alert(s)"
             % (str(data["pulled_at"])[:10], stale, len(data.get("bills") or []), data.get("alerts", 0))]
    for b in data.get("bills") or []:
        newest = (b.get("items") or [{}])[0]
        head = {"passed": "🔴 PASSAGE REPORTED — re-verify and rewrite the page",
                "moving": "🟡 moving", "quiet": "quiet"}.get(b.get("signal"), b.get("signal"))
        lines.append("- %s — %s; stage verified %s (%s)%s"
                     % (b["state"], head, b.get("verified"), (b.get("stage") or "")[:70],
                        "; newest: %s" % newest["title"][:80] if newest.get("title") else ""))
    return lines


def summary_md(data):
    out = ["### Law watch — %s, %d alert(s)" % (str(data.get("pulled_at", ""))[:10], data.get("alerts", 0)), ""]
    for b in data.get("bills") or []:
        out.append("**%s** — %s · signal `%s` · stage verified %s" % (b["state"], b["title"], b["signal"], b["verified"]))
        for it in b.get("items") or []:
            out.append("- `%s` %s — %s (%s)" % (it["signal"], (it.get("published") or "")[:10], it["title"], it.get("source", "")))
        if not b.get("items"):
            out.append("- nothing in the window")
        out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="read the news for the bills that would change our pages")
    ap.add_argument("command", choices=("pull", "show"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--summary", default="", help="also write a Markdown summary here")
    a = ap.parse_args(argv)
    if a.command == "show":
        for line in scorecard_lines():
            print(line)
        for line in alert_lines():
            print("ALERT " + line)
        return 0
    data = pull(days=a.days)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if a.summary:
        Path(a.summary).write_text(summary_md(data), encoding="utf-8")
    print("wrote %s (%d bills, %d alerts)" % (a.out, len(data["bills"]), data["alerts"]))
    for line in alert_lines(data):
        print("ALERT " + line)
    print("LAW_WATCH_ALERTS=%d" % data["alerts"])
    print("LAW_WATCH_SIGNATURE=%s" % signature(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
