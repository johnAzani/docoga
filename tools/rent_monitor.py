#!/usr/bin/env python3
"""rent_monitor.py — the Rent Monitor's live counts as shelf facts the Brain may cite.

Founder's brief, 29 Oct 2026 (10:05am; silence = go): the Brain gets `rent-index-nigeria` as a
citable source and a weekly slot, so the lanes can say "X receipts verified, Lagos is N of 30"
with numbers pulled live from the ledger — no content bank, nothing invented.

Why facts and not prose: the Brain refuses any number that is not in a cited fact
(brain.statistic_problems) and Gemini's verifier checks every claim against the shelf. So the
counts enter the same way the law does — as facts with ids (`monitor:total`, `monitor:rule`,
`monitor:closest`) whose text carries the numbers. The verifier then holds the post to them.

Where the numbers come from: GET https://docoga-ledger.johnazani.workers.dev/api/stats — the
public, personal-data-free counts endpoint the owner dashboard and the Rent Monitor page read
(docs/RECEIPT_LEDGER.md). Cached an hour at the edge. A miss returns no facts: the Brain simply
has no Rent Monitor block that day and writes from the shelf as before.

    DOCOGA_MONITOR=on   the Brain lane sets this; unset = never touches the network (tests, laptops)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request

LEDGER_URL = "https://docoga-ledger.johnazani.workers.dev"   # must equal site/index.html's LEDGER_URL
PAGE = "https://docoga.com.ng/rent-index-nigeria"
MONITOR_WEEKDAY = 4          # Friday — the promo lead ("one tool, one job"); the Rent Monitor's job is the receipt
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
KIND_WORDS = {"rent": "rent", "caution": "caution-fee", "service": "service-charge", "agency": "agency-fee"}


def enabled():
    return os.environ.get("DOCOGA_MONITOR", "").strip().lower() in ("on", "1", "true", "yes")


def is_monitor_day(day):
    return day.weekday() == MONITOR_WEEKDAY


def fetch_stats(http=None, timeout=8):
    """The ledger's public counts, or None. Never raises."""
    try:
        if http is not None:
            raw = http(LEDGER_URL + "/api/stats")
        else:
            with urllib.request.urlopen(LEDGER_URL + "/api/stats", timeout=timeout) as r:
                raw = r.read().decode("utf-8")
        data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        return data if isinstance(data, dict) and "total" in data else None
    except Exception:
        return None


def _month(ym):
    try:
        y, m = ym.split("-")[:2]
        return "%s %s" % (MONTHS[int(m) - 1], y)
    except (ValueError, IndexError, AttributeError):
        return ym


def closest_cell(stats):
    """(state, kind, month, count) for the cell nearest publication, or None."""
    cells = stats.get("cells") or {}
    best = None
    for key, n in cells.items():
        parts = str(key).split("|")
        if len(parts) != 3 or parts[0] in ("", "?"):
            continue
        if best is None or int(n) > best[3]:
            best = (parts[0], parts[1], parts[2], int(n))
    return best


def facts(stats, day=None):
    """Shelf-style facts from the counts: [{id, state, slug, tier, statute, key, cite, text}].
    Empty when `stats` is None."""
    if not stats:
        return []
    day = day or dt.date.today()
    at = int(stats.get("publish_at") or 30)
    total = int(stats.get("total") or 0)
    states = [s for s in (stats.get("by_state") or {}) if s and s != "?"]
    base = dict(state="Nigeria", slug="nigeria", tier="A", statute="DocOga Rent Monitor", cite=PAGE.replace("https://", ""))
    out = [dict(base, id="monitor:total", key="total",
                text="As of %d %s %d, %d rent receipt%s carr%s a DocOga verification code, from %d state%s "
                     "(public counts from the DocOga receipt ledger; no names or addresses are held)."
                     % (day.day, MONTHS[day.month - 1], day.year, total, "" if total == 1 else "s",
                        "ies" if total == 1 else "y", len(states), "" if len(states) == 1 else "s")),
           dict(base, id="monitor:rule", key="rule",
                text="DocOga publishes a rent level for a state only when one state, one kind of payment and one "
                     "calendar month reach %d verified receipts; below %d it publishes counts only, and the level "
                     "is a median of rent actually paid, never an asking price." % (at, at))]
    cell = closest_cell(stats)
    if cell:
        st, kind, month, n = cell
        out.append(dict(base, id="monitor:closest", key="closest",
                        text="The state closest to publication is %s: %d of %d %s receipts for %s."
                             % (st, n, at, KIND_WORDS.get(kind, kind), _month(month))))
    return out


def context(day, http=None, log=print):
    """The Brain's Rent Monitor facts for `day`: only on the monitor weekday, only when enabled,
    only when the ledger answers. Otherwise []."""
    if not enabled() or not is_monitor_day(day):
        return []
    stats = fetch_stats(http=http)
    if not stats:
        log("rent monitor: ledger unreachable — no Rent Monitor facts today")
        return []
    out = facts(stats, day)
    log("rent monitor: %d facts (total=%s, states=%d)" % (len(out), stats.get("total"), len(stats.get("by_state") or {})))
    return out


def prompt_block(monitor_facts):
    if not monitor_facts:
        return ""
    lines = "\n".join("%s | %s | %s" % (f["id"], f["cite"], f["text"]) for f in monitor_facts)
    return ("\n\nRENT MONITOR DAY — DOCOGA'S OWN NUMBERS (cite them like law: every figure needs its fact id)\n"
            + lines +
            "\nToday's post is the weekly Rent Monitor: open with the count or the closest state, say in one line\n"
            "what the Monitor is (rent actually paid, by state, published at 30 receipts, no names), and point\n"
            "the reader at the free receipt with the verification code. Set `tool` to \"rent-index\". These are\n"
            "the ONLY statistics allowed; do not round, compare or project them.")


if __name__ == "__main__":
    s = fetch_stats()
    print(json.dumps(facts(s), indent=1, ensure_ascii=False) if s else "ledger unreachable")
