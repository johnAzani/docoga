#!/usr/bin/env python3
"""growth.py — where the next naira is: the Growth lock's machine (🔒 docs/GROWTH.md).

Owner, 3 Nov 2026 (12:10pm): "the same way I want you to always always research as frequently as
possible very very in-depth to the thinnest details on how to make more success more than what we
are making now, and make sure it can be fully automated, and remember the ₦0."

What this module does, every Monday, with no hands and no spend: it reads the Search Console pull
(`logs/search_console.json`, written by tools/search_console.py) and names the leaks between what
Google shows us for and what sells — so the research dive each week starts from the numbers, not
from a feeling.

Three measures (the charter explains why these three):
  * money-page share — the share of Google impressions landing on pages that make the documents
    people pay for (receipts, agreements, invoices, the home generator). The quit-notice cluster is
    where the site ranks; the receipt lane is where the ₦2,000 pass is sold. Target 40%.
  * zero-click top spots — queries at positions 1–3 with impressions and no clicks. In 2026 that is
    the signature of an informational query answered by an AI Overview above the links (Pew, Jul
    2025: 8% of searches click a site when a summary shows vs 15% without; Ahrefs, Feb 2026:
    position-one CTR −58% with an Overview). The fix is a transactional page (sample · download ·
    make it), not a title tweak.
  * striking distance — queries at positions 4–10 with real impressions, where one better page
    moves the needle most.

    python3 tools/growth.py            # print the block the scorecard prints
    python3 tools/growth.py --json     # the measures as JSON

Never raises; a missing or stale pull prints what is missing instead.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARTER = ROOT / "docs" / "GROWTH.md"
SEARCH = ROOT / "logs" / "search_console.json"

DIVE_STALE_DAYS = 7          # a growth dive is logged in the charter ledger at least this often
MONEY_SHARE_TARGET = 0.40    # share of Google impressions that should land on money pages
ZERO_CLICK_MIN_IMPR = 5      # a top spot with fewer impressions than this is not yet a leak
STRIKING_MIN_IMPR = 10

# Pages that make the documents people pay for (the pass is sold on the receipt/agreement lanes).
MONEY_PAGE = re.compile(r"docoga\.com\.ng/(?:$|index(?:\.html)?$|rent-receipt|tenancy-agreement|shop-tenancy-agreement|"
                        r"invoice|caution-fee|rent-index-nigeria|demand-letter|rent-increase|employment-contract)")
# Query wording that already carries the intent to make or download a document.
TRANSACTIONAL = re.compile(r"\b(sample|template|format|pdf|download|generator|make|create|write|letter|form)\b", re.I)


def _path(page):
    return re.sub(r"^https?://[^/]+", "", str(page or "")) or "/"


def measures(data):
    """The three measures from one Search Console pull (dict as search_console.py writes it)."""
    pages = [p for p in (data.get("top_pages") or []) if isinstance(p, dict)]
    queries = [q for q in (data.get("top_queries") or []) if isinstance(q, dict)]
    total = sum(int(p.get("impressions") or 0) for p in pages)
    money = sum(int(p.get("impressions") or 0) for p in pages if MONEY_PAGE.search(str(p.get("page") or "")))
    share = (money / total) if total else None

    seen, zero, striking = set(), [], []
    for q in sorted(queries, key=lambda q: -int(q.get("impressions") or 0)):
        key = (str(q.get("query") or "").strip().lower(), _path(q.get("page")))
        if key in seen:
            continue
        seen.add(key)
        impr, clicks, pos = int(q.get("impressions") or 0), int(q.get("clicks") or 0), float(q.get("position") or 99)
        row = {"query": key[0], "page": key[1], "impressions": impr, "clicks": clicks, "position": round(pos, 1),
               "transactional": bool(TRANSACTIONAL.search(key[0]))}
        if pos <= 3 and clicks == 0 and impr >= ZERO_CLICK_MIN_IMPR:
            zero.append(row)
        elif 3 < pos <= 10 and impr >= STRIKING_MIN_IMPR:
            striking.append(row)
    return {"window": data.get("window") or {}, "taken_at": data.get("taken_at"),
            "impressions": int(data.get("impressions") or total), "clicks": int(data.get("clicks") or 0),
            "money_share": None if share is None else round(share, 3), "money_impressions": money, "page_impressions": total,
            "zero_click": zero[:6], "striking": striking[:6]}


def order(m):
    """The one order for the week — the biggest leak, in a sentence."""
    if m.get("money_share") is not None and m["money_share"] < MONEY_SHARE_TARGET:
        top = m["zero_click"][0] if m.get("zero_click") else None
        where = (" Google already shows us at position %s for '%s' (%d impressions, 0 clicks)" % (top["position"], top["query"], top["impressions"])) if top else ""
        return ("build the page that turns the quit-notice audience into document-makers: a sample-and-download page "
                "with the generator one tap away.%s — money-page share is %d%% against 40%%." % (where, round(m["money_share"] * 100)))
    if m.get("zero_click"):
        top = m["zero_click"][0]
        return "'%s' sits at position %s with %d impressions and no clicks — give that page a transactional block (sample · download · make it)." % (top["query"], top["position"], top["impressions"])
    if m.get("striking"):
        top = m["striking"][0]
        return "'%s' is at position %s with %d impressions — one better page moves it onto page one." % (top["query"], top["position"], top["impressions"])
    return "no leak in the pull — grow the footprint: a new intent page from the shelf."


def dive_date(text=None):
    """The newest dated row of the charter's ledger, or None."""
    try:
        text = text if text is not None else CHARTER.read_text(encoding="utf-8")
    except OSError:
        return None
    rows = re.findall(r"^- \*\*(\d{4}-\d{2}-\d{2})\*\*\s*—", text, flags=re.M)
    return max(rows) if rows else None


def dive_age(now=None, text=None):
    d = dive_date(text)
    if not d:
        return None
    today = (now or datetime.now(timezone.utc)).date()
    return (today - date.fromisoformat(d)).days


def load(path=None):
    try:
        data = json.loads(Path(path or SEARCH).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def scorecard_lines(path=None, now=None, charter_text=None):
    """The block the Monday scorecard prints. Never raises."""
    lines = []
    age = dive_age(now, charter_text)
    if age is None:
        lines.append("- ⚠️ no growth dive logged in docs/GROWTH.md yet")
    elif age > DIVE_STALE_DAYS:
        lines.append("- ⚠️ the last growth dive is %d days old (limit %d) — research first, then build" % (age, DIVE_STALE_DAYS))
    else:
        lines.append("- last growth dive: %s (%d day(s) ago; limit %d)" % (dive_date(charter_text), age, DIVE_STALE_DAYS))
    data = load(path)
    if not data:
        lines.append("- no Search Console pull to read — the leaks are not measured this week")
        return lines
    try:
        m = measures(data)
    except Exception as exc:  # noqa: BLE001 — a bonus block never breaks the scorecard
        lines.append("- growth measures failed: %s" % exc)
        return lines
    win = m.get("window") or {}
    if m["money_share"] is None:
        lines.append("- money-page share of Google impressions: not measured (no page rows in the pull)")
    else:
        mark = "✅" if m["money_share"] >= MONEY_SHARE_TARGET else "🔻"
        lines.append("- money-page share of Google impressions (%s → %s): %d%% (%d of %d) — target %d%% %s"
                     % (win.get("start", "?"), win.get("end", "?"), round(m["money_share"] * 100), m["money_impressions"],
                        m["page_impressions"], round(MONEY_SHARE_TARGET * 100), mark))
    if m["zero_click"]:
        lines.append("- zero-click top spots (pos ≤3, 0 clicks): %s → informational queries under AI Overviews; the fix is a transactional page, not a title tweak"
                     % ", ".join("'%s' pos %s ×%d" % (r["query"], r["position"], r["impressions"]) for r in m["zero_click"][:4]))
    else:
        lines.append("- zero-click top spots: none in the pull")
    if m["striking"]:
        lines.append("- striking distance (pos 4–10): %s"
                     % ", ".join("'%s' pos %s ×%d%s" % (r["query"], r["position"], r["impressions"], " (transactional)" if r["transactional"] else "") for r in m["striking"][:4]))
    lines.append("- this week's order: " + order(m))
    return lines


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    data = load()
    if "--json" in argv:
        print(json.dumps(measures(data) if data else {"error": "no Search Console pull"}, indent=2, ensure_ascii=False))
        return 0
    print("\n".join(scorecard_lines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
