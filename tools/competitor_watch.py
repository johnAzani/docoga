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
import html
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
MAX_PER_COMPETITOR = 4
MAX_TOTAL = 30
# Only what touches the business: a competitor's cookie recipe is not the field.
# 3 Nov 2026, first real pull: "property", "house", "flat" and "bill" let in listing pages, a bill-of-
# quantities template and a "Rent" menu page — the field is tenancy, so the words are tenancy words.
TOPIC = re.compile(r"\b(rent|tenan|landlord|lease|quit|evict|agent|agency|caution|deposit|receipt|agreement|"
                   r"premises|housing|apartment|lagos|abuja|tenancy|lasrera)\w*", re.I)
# A sitemap slug that is a listing id ("propertypro-1qlct") or a menu page ("rent", "list a property")
# is not something the competition *published*.
# 5 Nov 2026: a construction-cost site's sitemap dates public tenders ("Remodelling of Anambra State
# Housing Corporation office building", "Premises asphalting and re-roofing works") — "housing" and
# "premises" pass the topic test, but a tender is not a thing a rival said about renting.
# 7 Nov 2026: four more tenders passed on "caution lights", "bull housing" and "abuja" — the regex
# grows, and a map row may now carry `skip_paths` (NigeriaBuildingCost: /construction-tenders/).
TENDER = re.compile(r"\b(remodel\w*|renovat\w*|construct\w*|asphalt\w*|re-?roof\w*|landscap\w*|beautificat\w*|"
                    r"rehabilitat\w*|tender|bill of quantit\w*|boq|takeoff|take-off|borehole|drainage|"
                    r"perimeter fenc\w*|block of \d|classroom\w*|procurement|installing|install\w* of|"
                    r"upgrading|erosion|health cent\w*|livestock|rumble strip\w*|road sign\w*|site works|"
                    r"supply (?:and|&) (?:installation|delivery)|\d+\s?km)\b", re.I)
TOKEN = re.compile(r"\b(?=[a-z0-9]*\d)(?=[a-z0-9]*[a-z])[a-z0-9]{4,}\b", re.I)
MIN_SLUG_WORDS = 4
ARTICLE_SITEMAP = re.compile(r"(post|blog|news|article|guide|insight|resource|story|stories)", re.I)
UA = "DocOga-field/1.0 (+https://docoga.com.ng)"
# 4 Nov 2026: the closest rival added a ₦500 seven-day pass under its ₦4,000 one and the watch, which
# reads only what is *published*, never saw a price move. A row may now carry
#   "prices": {"url": <public pricing page>, "seen": ["₦4,000", "₦500"]}
# and the pull re-reads that one page, lists every naira figure on it and flags any figure the map
# does not know (or one that vanished). The scorecard shows the flag; the prompt never carries a price.
PRICE = re.compile(r"(?:₦|NGN\s?)\s?(\d{1,3}(?:,\d{3})+|\d{3,7})(?!\d)")
PRICE_MIN, PRICE_MAX = 100, 5_000_000   # ₦0 "free" tiers and bare years/ids are not prices


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
        children = [c for c in (newsdesk._text(n, "loc") for n in root if n.tag.rsplit("}", 1)[-1] == "sitemap") if c]
        articles = [c for c in children if ARTICLE_SITEMAP.search(c.rsplit("/", 1)[-1])]
        return [], (articles or children)
    items = []
    for node in root:
        if node.tag.rsplit("}", 1)[-1] != "url":
            continue
        loc = newsdesk._text(node, "loc")
        when = newsdesk._when(newsdesk._text(node, "lastmod"))
        if not loc or not when or when < since:
            continue
        title = _slug_title(loc)
        if len(title.split()) < MIN_SLUG_WORDS or TOKEN.search(title):
            continue
        items.append({"title": title, "link": loc, "published": when.isoformat(timespec="seconds"), "source": source})
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
    # 3 Nov 2026: the first "channelId" in a watch page belonged to a related video and the feed
    # 404ed — the page's own channel is the itemprop/externalChannelId one; the bare key comes last.
    m = (re.search(rb'itemprop="channelId"\s+content="(UC[A-Za-z0-9_-]{10,})"', raw)
         or re.search(rb'"externalChannelId":"(UC[A-Za-z0-9_-]{10,})"', raw)
         or re.search(rb'"externalId":"(UC[A-Za-z0-9_-]{10,})"', raw)
         or re.search(rb'"channelId":"(UC[A-Za-z0-9_-]{10,})"', raw)
         or re.search(rb"channel_id=(UC[A-Za-z0-9_-]{10,})", raw))
    return ("https://www.youtube.com/feeds/videos.xml?channel_id=" + m.group(1).decode()) if m else None


def price_figures(raw):
    """Every distinct naira figure on a public page, as the map writes them ("₦4,000"), page order."""
    text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw or "")
    text = html.unescape(re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I))
    text = re.sub(r"<[^>]+>", " ", text)
    out = []
    for m in PRICE.finditer(text):
        n = int(m.group(1).replace(",", ""))
        fig = "₦{:,}".format(n)
        if PRICE_MIN <= n <= PRICE_MAX and fig not in out:
            out.append(fig)
    return out


def watch_prices(field, http=None, log=print):
    """Rows with a `prices` block: re-read the pricing page, compare to what the map has `seen`."""
    http = http or _http
    rows = []
    for comp in field:
        spec = comp.get("prices")
        if not isinstance(spec, dict) or not str(spec.get("url") or "").startswith("https://"):
            continue
        seen = [str(x) for x in (spec.get("seen") or [])]
        row = {"competitor": comp["name"], "url": spec["url"], "seen": seen, "found": [], "new": [], "gone": []}
        try:
            status, raw = http(spec["url"])
            if status != 200:
                raise ValueError("HTTP %s" % status)
            row["found"] = price_figures(raw)
            row["new"] = [f for f in row["found"] if f not in seen]
            row["gone"] = [f for f in seen if f not in row["found"]]
        except (urllib.error.URLError, OSError, ValueError) as exc:
            row["error"] = str(exc)[:60]
        log("prices: %s — found %s; new %s; gone %s%s" % (comp["name"], row["found"], row["new"], row["gone"],
                                                        (" (" + row["error"] + ")") if row.get("error") else ""))
        rows.append(row)
    return rows


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
    field = field if field is not None else load_field()
    for comp in field:
        feeds = list(comp.get("feeds") or [])
        paths = [p for p in (comp.get("paths") or []) if p]   # e.g. ["/blog/"] — the rest of a marketplace sitemap is listings
        skip = [p for p in (comp.get("skip_paths") or []) if p]   # e.g. ["/construction-tenders/"] — never a publication
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
            text = (r.get("title") or "") + " " + (r.get("summary") or "")
            if r["link"] in seen or not TOPIC.search(text) or TENDER.search(r.get("title") or ""):
                continue
            if paths and not any(p in r["link"] for p in paths):
                continue
            if skip and any(p in r["link"] for p in skip):
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
    prices = watch_prices(field, http=http, log=log)
    return {"pulled_at": now.isoformat(timespec="seconds"), "days": days, "items": items[:MAX_TOTAL],
            "sources": report, "unwatchable": unwatchable, "prices": prices}


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


# ── Collisions: a rival wrote on a topic DocOga has a money page for (7 Nov 2026) ────────────────
# The 5 Nov pull carried "How much can landlord increase rent nigeria" — published the same day as
# docoga.com.ng/rent-increase-notice-nigeria — and nothing said so. Each row: the page slug, the words
# a rival's title would use, and the brain tool whose link lands on that page. Order matters: the
# first match wins, so the narrower topics come first.
COVERAGE = (
    ("rent-increase-notice-nigeria", re.compile(r"rent\s+(increase|increment|review|hike|rise)|increase\w*\s+(the\s+|your\s+|my\s+)?rent|raise\w*\s+(the\s+)?rent", re.I), "rent-review"),
    ("demand-letter-rent-arrears-nigeria", re.compile(r"demand\s+letter|arrears|unpaid\s+rent|owing\s+rent|rent\s+default", re.I), "letter-of-demand"),
    ("caution-fee-nigeria", re.compile(r"caution\s+(fee|deposit|money)|security\s+deposit|refundable\s+deposit", re.I), "caution-fee"),
    ("rent-receipt-format-nigeria", re.compile(r"rent\s+receipt|receipt\s+for\s+rent", re.I), "rent-receipt"),
    ("notice-to-quit-nigeria", re.compile(r"quit\s+notice|notice\s+to\s+quit|7\s*days?\s+notice|seven\s+days?\s+notice|evict\w*|recover\w*\s+possession", re.I), "notice-to-quit"),
    ("rent-relief-nigeria", re.compile(r"rent\s+relief|tax\s+(relief|deduction)", re.I), "tenant-rights"),
    ("shop-tenancy-agreement-nigeria", re.compile(r"shop\s+(tenancy|lease|agreement)|commercial\s+(tenancy|lease)", re.I), "tenancy-agreement"),
    ("tenancy-agreement-sample-nigeria", re.compile(r"tenancy\s+agreement|lease\s+agreement|rent\s+agreement|tenancy\s+contract", re.I), "tenancy-agreement"),
    ("tenant-rights-nigeria", re.compile(r"tenant'?s?\s+rights|landlord'?s?\s+(duties|obligations)|what\s+(a\s+)?landlord\s+cannot", re.I), "tenant-rights"),
)
SITE_DIR = ROOT / "site"
SITE_URL = "https://docoga.com.ng"


def page_date(slug, site=None):
    """The page's datePublished, or '' when the page is not there (then it is a gap, not a collision)."""
    path = Path(site or SITE_DIR) / (slug + ".html")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r'"datePublished":\s*"(\d{4}-\d{2}-\d{2})', text) or re.search(r'"dateModified":\s*"(\d{4}-\d{2}-\d{2})', text)
    return m.group(1) if m else "live"


def collisions(items, site=None):
    """[{competitor, title, published, page, page_url, page_date, tool}] — rival items on a topic
    DocOga already answers. The page must exist; a match on a missing page is reported by `gaps`."""
    out = []
    for it in items or []:
        title = str(it.get("title") or "")
        for slug, rx, tool in COVERAGE:
            if rx.search(title):
                when = page_date(slug, site)
                if when:
                    out.append({"competitor": it.get("competitor", ""), "title": title[:120], "published": (it.get("published") or "")[:10],
                                "page": slug, "page_url": "%s/%s" % (SITE_URL, slug), "page_date": when, "tool": tool})
                break
    return out


def gaps(items, site=None):
    """Rival items on the business that no COVERAGE row claims (or whose page is missing) — the
    Growth lane's candidate list, written by the field rather than by guesswork."""
    out = []
    for it in items or []:
        title = str(it.get("title") or "")
        if TENDER.search(title):   # an older pull may still carry tenders the regex has since learnt
            continue
        hit = next(((slug, tool) for slug, rx, tool in COVERAGE if rx.search(title)), None)
        if hit is None or not page_date(hit[0], site):
            out.append({"competitor": it.get("competitor", ""), "title": title[:120], "published": (it.get("published") or "")[:10]})
    return out


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
    hits = collisions(items)
    if hits:
        lines.append("COLLISIONS — a rival wrote on a question DocOga already answers with a page. Answer it from the shelf, "
                     "point the post at that page (set `tool`), and say the one thing their title cannot:")
        seen = set()
        for h in hits[:6]:
            if h["page"] in seen:
                continue
            seen.add(h["page"])
            lines.append("- %s (%s) → set tool=\"%s\"; the page is %s" % (h["title"], h["published"] or "undated", h["tool"], h["page_url"]))
    tools = [c for c in field if c.get("kind") == "tool"]
    if tools:
        lines.append("DocOga's standing edge over the %d document tools on the field: every line cited to the state's own "
                     "section, Nigerian English, one price, no watermark, no account — write like the only one who read the law."
                     % len(tools))
    return "\n".join(lines)


# ── Research freshness: the lock's measurement (docs/DOMINANCE.md §3) ───────────────────────────
DOMINANCE_DOC = ROOT / "docs" / "DOMINANCE.md"
DIVE_STALE_DAYS = 14      # a new dated research dive at least this often
MAP_STALE_DAYS = 45       # the field map re-verified at least this often


def last_research_dive(doc=None):
    """(date_iso, title) of the newest ledger line in docs/DOMINANCE.md, or (None, '')."""
    try:
        text = Path(doc or DOMINANCE_DOC).read_text(encoding="utf-8")
    except OSError:
        return None, ""
    rows = re.findall(r"^- \*\*(\d{4}-\d{2}-\d{2})\*\*\s*[—-]\s*(.+)$", text, flags=re.M)
    if not rows:
        return None, ""
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows[0][0], rows[0][1].strip()


def map_verified(path=None):
    try:
        data = json.loads(Path(path or FIELD).read_text(encoding="utf-8"))
        return str(data.get("verified") or "")[:10] or None
    except (OSError, ValueError, AttributeError):
        return None


def _days_since(stamp, now):
    when = newsdesk._when(stamp)
    return (now - when).days if when else None


def research_status(now=None, doc=None, field_path=None):
    """How fresh the research is: the last dive, the field map's verification, and ⚠️ flags."""
    now = now or datetime.now(timezone.utc)
    dive_date, dive_title = last_research_dive(doc)
    verified = map_verified(field_path)
    dive_days = _days_since(dive_date, now) if dive_date else None
    map_days = _days_since(verified, now) if verified else None
    return {"last_dive": dive_date, "last_dive_title": dive_title, "dive_days": dive_days,
            "dive_stale": dive_days is None or dive_days > DIVE_STALE_DAYS,
            "map_verified": verified, "map_days": map_days,
            "map_stale": map_days is None or map_days > MAP_STALE_DAYS}


def research_lines(status):
    lines = []
    if status.get("last_dive"):
        lines.append("- last deep research: %s (%s day(s) ago) — %s%s"
                     % (status["last_dive"], status["dive_days"], status["last_dive_title"][:90],
                        " ⚠️ past %d days — a new dive is owed" % DIVE_STALE_DAYS if status["dive_stale"] else ""))
    else:
        lines.append("- last deep research: none on the ledger ⚠️ — docs/DOMINANCE.md §5")
    if status.get("map_verified"):
        lines.append("- field map verified: %s (%s day(s) ago)%s"
                     % (status["map_verified"], status["map_days"],
                        " ⚠️ past %d days — re-verify every rival" % MAP_STALE_DAYS if status["map_stale"] else ""))
    else:
        lines.append("- field map verified: never ⚠️")
    return lines


def scorecard_lines(data=None, now=None, status=None):
    data = data if data is not None else load()
    items = fresh_items(data, now=now)
    head = research_lines(status if status is not None else research_status(now=now))
    if not data.get("pulled_at"):
        return head + ["- not pulled yet — the brain's Monday run writes logs/competitor_watch.json"]
    by = {}
    for it in items:
        by.setdefault(it["competitor"], []).append(it)
    lines = ["- field pulled %s: %d item(s) from %d competitor(s); not watchable at ₦0: %s"
             % (str(data.get("pulled_at", ""))[:10], len(items), len(by), ", ".join(data.get("unwatchable") or []) or "none")]
    for name, rows in sorted(by.items(), key=lambda kv: -len(kv[1]))[:6]:
        lines.append("- %s — %s" % (name, "; ".join(r["title"][:70] for r in rows[:3])))
    if not items:
        lines.append("- nothing new on the field this window — DocOga posted every day of it")
    for h in collisions(items)[:6]:
        lines.append("- ⚔️ collision: %s — \"%s\" (%s) ↔ /%s (ours, published %s) → the brain is told to point there"
                     % (h["competitor"], h["title"][:70], h["published"] or "undated", h["page"], h["page_date"]))
    for g in gaps(items)[:6]:
        lines.append("- ◻ uncovered: %s — \"%s\" (%s) — no DocOga page answers this title; a Growth candidate, not an order"
                     % (g["competitor"], g["title"][:70], g["published"] or "undated"))
    lines += price_lines(data.get("prices") or [])
    return head + lines


def price_lines(rows):
    """One scorecard line per watched pricing page; ⚠️ only when a figure moved against the map."""
    out = []
    for p in rows:
        seen = ", ".join(p.get("seen") or []) or "nothing"
        if p.get("error"):
            out.append("- rival prices: %s — pricing page unreadable (%s); the map says %s" % (p["competitor"], p["error"], seen))
        elif p.get("new") or p.get("gone"):
            out.append("- ⚠️ rival price moved: %s — new %s; gone %s (map said %s) → re-verify brain/competitors.json"
                       % (p["competitor"], ", ".join(p.get("new") or []) or "none", ", ".join(p.get("gone") or []) or "none", seen))
        else:
            out.append("- rival prices: %s — %s, as mapped" % (p["competitor"], ", ".join(p.get("found") or []) or seen))
    return out


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
