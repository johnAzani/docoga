#!/usr/bin/env python3
"""
tools/money.py — the daily money metre: yesterday's naira, and the one stage that is leaking.

The dashboard already knows what sold; the weekly scorecard already grades it. Neither answers the
question the owner asks every morning — *did any money come in, and if not, which step is broken?* —
and neither keeps a day-by-day record of it. This does both, once a day, from the owner dashboard
API the scorecard already reads (`/admin/data` for today/yesterday counters and the 28-day series,
`/admin/site` for visits):

    python3 tools/money.py pull [--summary-file /tmp/money.md] [--dry-run]
    python3 tools/money.py brief [--days 14]        # render from the ledger, no network
    python3 tools/money.py status                    # today's line only

It writes `logs/money_ledger.json` (one row per day, idempotent: a re-run replaces the day) and a
markdown brief. The brief does one thing beyond counting: it names the stage the money is stuck at —
unmeasured, no-traffic, offer-unseen, checkout-broken, converting-weak, renewal-gap — or that it
earned, and prints the arithmetic, so the gap between the target and today is a number rather than a
feeling.

Machine lines (the workflow reads them; a renamed key reads as "healthy", so they are pinned by
`tools/tests/test_money.py`):

    MONEY_TODAY=<naira>      MONEY_7D=<naira>        MONEY_28D=<naira>
    MONEY_TARGET=<naira>     MONEY_STAGE=<stage>     MONEY_VISITS_PER_DAY=<n>

Env: DOCOGA_ADMIN_PASSPHRASE (the dashboard passphrase, as a secret — never in this file),
     DOCOGA_WORKER_URL (default: the live worker), DOCOGA_DAILY_TARGET (default ₦5,000).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER_PATH = os.path.join(ROOT, "logs", "money_ledger.json")
WORKER = os.environ.get("DOCOGA_WORKER_URL", "https://docoga-pass.johnazani.workers.dev").rstrip("/")
DEFAULT_TARGET = 5000
KEEP_DAYS = 400        # a year and a bit: enough to see a trend, small enough to commit daily
PRICE_FALLBACK = 2000  # used only when the worker does not report its own price
CONVERSION = 0.01      # a pass per 100 visits: the assumption the stages are graded against


# ── the HTTP boundary (injectable, so the tests never touch the network) ─────────────────────

def http_json(method, url, body=None, headers=None, timeout=30):
    """`(status, parsed_json)`. Never raises for an HTTP error; returns the status instead."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    hdrs = {"User-Agent": "DocOgaMoney/1.0", "Accept": "application/json"}
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw, status = exc.read(), exc.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, {}
    try:
        return status, json.loads(raw.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return status, {}


def pull(worker=WORKER, passphrase="", http=http_json):
    """Log into the owner dashboard, read the money and the visits, log out.

    Returns `(payload, problems)`. `payload` is None when nothing could be read, and the problems
    say why in words the owner can act on — a silently zeroed brief is worse than no brief.
    """
    problems = []
    if not passphrase:
        return None, ["DOCOGA_ADMIN_PASSPHRASE is not set, so the dashboard cannot be read"]
    status, login = http("POST", worker + "/admin/login", {"pass": passphrase})
    if status != 200 or not login.get("ok"):
        return None, ["dashboard login refused (%s: %s)" % (status, login.get("error") or "no body")]
    auth = {"Authorization": "Bearer " + str(login.get("token") or "")}
    status, data = http("GET", worker + "/admin/data", None, auth)
    if status != 200 or not data.get("ok"):
        http("POST", worker + "/admin/logout", None, auth)
        return None, ["dashboard read failed (%s)" % status]
    status, site = http("GET", worker + "/admin/site", None, auth)
    http("POST", worker + "/admin/logout", None, auth)
    if status != 200 or not site.get("ok"):
        site, site_problem = {}, "visits: /admin/site answered %s" % status
    else:
        site_problem = "" if site.get("connected", True) and not site.get("error") else \
            "visits: %s" % (site.get("reason") or site.get("error") or "not connected")
    if site_problem:
        problems.append(site_problem)
    return {"data": data, "site": site}, problems


# ── rows and the ledger ─────────────────────────────────────────────────────────────────────

def _counters(row):
    """One day's counters → the four numbers money is made of. `sold` is the provider's verified
    sale; `offline`/`manual` are the ones the owner closed by hand — all three are money in."""
    row = row or {}
    return {
        "passes": int(row.get("sold") or 0) + int(row.get("offline") or 0) + int(row.get("manual") or 0),
        "revenue": int(row.get("rev") or 0) + int(row.get("bizrev") or 0),
        "business": int(row.get("bizpaid") or 0),
        "waitlist": int(row.get("wait") or 0),
    }


def _site_bits(site):
    """The visit numbers the site API hands over: 7- and 28-day totals, never a daily series."""
    if not site or not (site.get("connected") and not site.get("error")):
        return {}
    out = {}
    for key, value in (("visits_7d", site.get("visits7")), ("visits_28d", site.get("visits28")),
                       ("pageviews_7d", site.get("pageviews7")), ("pageviews_28d", site.get("pageviews28"))):
        if value is not None:
            out[key] = int(value or 0)
    top = []
    for row in (site.get("top_paths") or [])[:5]:
        if isinstance(row, dict) and row.get("path"):
            top.append({"path": str(row.get("path")), "visits": int(row.get("visits") or 0)})
    if top:
        out["top_paths"] = top
    if isinstance(site.get("by_channel"), dict):
        out["channels"] = {str(k): int(v or 0) for k, v in site["by_channel"].items()}
    return out


def _iso_week(date_str, weeks_back=0):
    day = _day(date_str) - timedelta(days=7 * weeks_back)
    year, week, _weekday = day.isocalendar()
    return "%04d-W%02d" % (year, week)


def _sources(snapshot, today):
    """The worker's weekly `src:*` counters → checkout taps and tagged sales, by channel.

    These are the only numbers that say *where* a buyer came from, and they are weekly, not daily —
    so they ride along on the day they were read rather than pretending to be a daily series.
    """
    raw = (snapshot or {}).get("sources") or {}
    out, extras = {}, {}
    for kind, label in (("checkout", "checkouts"), ("sale", "sales")):
        weeks = raw.get(kind) or {}
        if not isinstance(weeks, dict):
            continue
        total, recent = {}, {}
        for week, row in weeks.items():
            if not isinstance(row, dict):
                continue
            for channel, count in row.items():
                try:
                    number = int(count or 0)
                except (TypeError, ValueError):
                    continue
                if number <= 0:
                    continue
                total[str(channel)] = total.get(str(channel), 0) + number
                if week in (_iso_week(today), _iso_week(today, 1)):
                    recent[str(channel)] = recent.get(str(channel), 0) + number
        if total:
            out[label] = dict(sorted(total.items(), key=lambda kv: -kv[1]))
        extras[label + "_7d"] = sum(recent.values())
        extras[label + "_28d"] = sum(total.values())
    if out:
        out.update(extras)
    return out


def rows_from(payload, taken_at=None):
    """The dashboard payload → one ledger row per day (the 28-day series plus today's counters).

    The series and `today` overlap on the same date; today's counters win because they are the ones
    the worker reads live.
    """
    taken_at = taken_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = (payload or {}).get("data") or {}
    site = _site_bits((payload or {}).get("site") or {})
    price = int(data.get("priceNGN") or PRICE_FALLBACK)
    rows = {}
    for series_row in ((data.get("snapshot") or {}).get("series") or []):
        day = str(series_row.get("date") or "")
        if not day:
            continue
        row = {"date": day, "price": price, "taken_at": taken_at}
        row.update(_counters(series_row))
        rows[day] = row
    today = str(data.get("date") or taken_at[:10])
    row = {"date": today, "price": price, "taken_at": taken_at}
    row.update(_counters(data.get("today") or {}))
    row.update(site)   # visits are a 7/28-day reading, stamped on the day it was taken
    sources = _sources(data.get("snapshot"), today)
    if sources:
        row["sources"] = sources   # channel attribution: a weekly reading, like the visits
    rows[today] = row
    return [rows[day] for day in sorted(rows)]


def merge(ledger, rows):
    """Append rows to the ledger, replacing any day already recorded. Newest last, capped."""
    days = {}
    for row in (ledger or {}).get("days") or []:
        if isinstance(row, dict) and row.get("date"):
            days[str(row["date"])] = row
    for row in rows or []:
        if not isinstance(row, dict) or not row.get("date"):
            continue
        merged = dict(days.get(row["date"]) or {})
        merged.update(row)
        days[row["date"]] = merged
    ordered = [days[day] for day in sorted(days)][-KEEP_DAYS:]
    return {"days": ordered}


def load_ledger(path=LEDGER_PATH):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {"days": []}
    if not isinstance(data, dict) or not isinstance(data.get("days"), list):
        return {"days": []}
    return {"days": [row for row in data["days"] if isinstance(row, dict) and row.get("date")]}


def save_ledger(ledger, path=LEDGER_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(ledger, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write("\n")


# ── the arithmetic ─────────────────────────────────────────────────────────────────────────

def _day(date):
    return datetime.strptime(date, "%Y-%m-%d").date()


def window(ledger, days, today):
    """Rows inside the last `days` days, inclusive of `today`."""
    end = _day(today)
    start = end - timedelta(days=days - 1)
    keep = []
    for row in (ledger or {}).get("days") or []:
        try:
            day = _day(str(row.get("date")))
        except ValueError:
            continue
        if start <= day <= end:
            keep.append(row)
    return keep


def totals(ledger, days, today):
    rows = window(ledger, days, today)
    return {
        "days": len(rows),
        "revenue": sum(int(row.get("revenue") or 0) for row in rows),
        "passes": sum(int(row.get("passes") or 0) for row in rows),
        "business": sum(int(row.get("business") or 0) for row in rows),
    }


def latest_with_site(ledger):
    """The most recent row that carries visit numbers (they are only stamped on pull days)."""
    for row in reversed((ledger or {}).get("days") or []):
        if row.get("visits_7d") is not None or row.get("visits_28d") is not None:
            return row
    return None


def visits_per_day(ledger):
    row = latest_with_site(ledger)
    if not row:
        return None, None
    if row.get("visits_7d") is not None:
        return round(int(row["visits_7d"]) / 7.0, 1), 7
    if row.get("visits_28d") is not None:
        return round(int(row["visits_28d"]) / 28.0, 1), 28
    return None, None


def diagnosis(ledger, today, target=DEFAULT_TARGET):
    """Where the money is stuck, and the single action that moves it — from the numbers alone.

    The order is the funnel, and the first stage that is empty is the one to work on: there is no
    point rewriting a checkout nobody reached. The threshold between "too few visitors to judge the
    offer" and "the offer is the leak" is arithmetic, not taste: at a 1% conversion, a week needs
    100+ visits before zero sales means anything other than "not enough people came".
    """
    rows = [row for row in (ledger or {}).get("days") or []]
    week = totals(ledger, 7, today)
    month = totals(ledger, 28, today)
    per_day, window_days = visits_per_day(ledger)
    today_row = next((row for row in rows if row.get("date") == today), None)
    if today_row is None and rows:
        today_row = rows[-1]
    revenue_today = int((today_row or {}).get("revenue") or 0)
    price = int((today_row or {}).get("price") or PRICE_FALLBACK) or PRICE_FALLBACK
    visits_7d = None
    for row in reversed(rows):
        if row.get("visits_7d") is not None:
            visits_7d = int(row["visits_7d"])
            break
    base = {"revenue_today": revenue_today, "week": week, "month": month,
            "visits_per_day": per_day, "visits_7d": visits_7d, "price": price, "target": target}

    if not rows:
        base.update(stage="unmeasured",
                    action="Add the dashboard passphrase as the `DOCOGA_ADMIN_PASSPHRASE` secret, then "
                           "run this lane once — until it is set, the money metre is blind.")
        return base
    if target and revenue_today >= target:
        base.update(stage="at-target",
                    action="Today's target is met. Repeat exactly what the lanes published yesterday — "
                           "the paid sale came through %s." % _best_source(rows))
        return base
    if revenue_today > 0:
        base.update(stage="earning",
                    action="Money came in. The channel it came through is `%s` — publish to it again "
                           "today and name the pass in the first line." % _best_source(rows))
        return base
    checkouts_7d = 0
    for row in reversed(rows):
        sources = row.get("sources") or {}
        if isinstance(sources, dict) and sources.get("checkouts_7d") is not None:
            checkouts_7d = int(sources["checkouts_7d"])
            break
    base["checkouts_7d"] = checkouts_7d
    if checkouts_7d > 0 and week["passes"] == 0:
        base.update(stage="checkout-broken",
                    action="%s checkout %s in seven days and none completed. The offer is being "
                           "reached and the payment is the leak: open /admin/codes and the live probe, "
                           "and check the worker's webhook vitals (`lastWebhookMinutesAgo`)."
                           % (_fmt(checkouts_7d), "tap" if checkouts_7d == 1 else "taps"))
        return base
    if week["passes"] > 0 and week["revenue"] < (target * 7 * 0.5):
        base.update(stage="converting-weak",
                    action="%s in seven days for ₦%s — the buyers exist but the ticket is too "
                           "small for ₦%s a day. The move is a bigger sale to the same person (the "
                           "Business tier at 20 seats), not more traffic."
                           % (_passes(week["passes"]), _fmt(week["revenue"]), _fmt(target)))
        return base
    if month["passes"] > 0 and week["passes"] == 0:
        base.update(stage="renewal-gap",
                    action="Nothing sold this week after %d last month — the buyers were one-off. "
                           "Open /admin/codes, find last month's buyers and send the renewal link."
                           % month["passes"])
        return base
    if per_day is None:
        base.update(stage="no-traffic-data",
                    action="The dashboard cannot see visits yet (Cloudflare Web Analytics not "
                           "connected), so the funnel cannot be graded. Connect it, then re-run.")
        return base
    # One sale per 100 visits is the assumption the whole metre uses; below one *expected* sale the
    # week has not tested the offer, it has tested the reach.
    expected = (visits_7d if visits_7d is not None else per_day * 7) * CONVERSION
    if expected >= 1.0:
        base.update(stage="offer-unseen",
                    action="%s visits a day and no sale in seven — about %s sales were due at a 1%% "
                           "conversion, so the offer is the leak, not the traffic. Put the ₦%s pass "
                           "line above the fold on %s."
                           % (_fmt(per_day), _fmt(round(expected, 1)), _fmt(price),
                              _top_path(ledger) or "the busiest tool page"))
        return base
    base.update(stage="no-traffic",
                action="The site gets %s visits a day — under the 100 a week it takes to test an "
                       "offer at a 1%% conversion. At ₦%s a pass that is a ceiling of about ₦%s a day "
                       "even if every visitor bought, so today's money is distribution: publish one "
                       "page for a buying-intent question and let the lanes post it."
                       % (_fmt(per_day), _fmt(price), _fmt(round(per_day * price * CONVERSION))))
    return base


def _best_source(rows):
    """The channel that sold, if the worker tagged it; otherwise the honest 'manual or untagged'."""
    for row in reversed(rows):
        if isinstance(row.get("sources"), dict):
            sales = row["sources"].get("sales") or {}
            if sales:
                channel = max(sales.items(), key=lambda kv: int(kv[1] or 0))[0]
                return channel
    return "manual or untagged"


def _top_path(ledger):
    row = latest_with_site(ledger)
    paths = (row or {}).get("top_paths") or []
    if not paths:
        return ""
    return "%s (%s visits in 7 days)" % (paths[0]["path"], _fmt(paths[0]["visits"]))


def _passes(count):
    number = int(count or 0)
    return "%s %s" % (_fmt(number), "pass" if number == 1 else "passes")


def _fmt(value):
    try:
        return "{:,}".format(int(round(float(value))))
    except (TypeError, ValueError):
        return "—"


def required_visits(target, price, conversion=0.01):
    """How many visits a day the target needs at a given conversion. The honest denominator."""
    per_sale = max(1.0, float(price)) * max(0.0001, float(conversion))
    return int(round(float(target) / per_sale))


# ── the brief ─────────────────────────────────────────────────────────────────────────────

def brief(ledger, today, target=DEFAULT_TARGET, days=14, problems=None):
    """The markdown the owner reads on his phone: three numbers, the stage, one action, the ledger."""
    found = diagnosis(ledger, today, target)
    week, month = found["week"], found["month"]
    per_day = found["visits_per_day"]
    price = found["price"]
    out = ["### 💰 Money — %s" % today, ""]
    day_row = (window(ledger, 1, today) or [{}])[-1]
    out.append("**Yesterday/today:** ₦%s · %s · %s business teams"
               % (_fmt(found["revenue_today"]), _passes(day_row.get("passes")),
                  _fmt(day_row.get("business") or 0)))
    out.append("**7 days:** ₦%s · %s · %s"
               % (_fmt(week["revenue"]), _passes(week["passes"]),
                  ("%s visits a day" % _fmt(per_day)) if per_day is not None else "visits not connected"))
    out.append("**28 days:** ₦%s · %s" % (_fmt(month["revenue"]), _passes(month["passes"])))
    out.append("**Target:** ₦%s a day — gap ₦%s"
               % (_fmt(target), _fmt(max(0, target - found["revenue_today"]))))
    out.append("")
    out.append("**Stage: `%s`**" % found["stage"])
    out.append("")
    out.append("**Today's one action:** %s" % found["action"])
    out.append("")
    if per_day is not None:
        need = required_visits(target, price)
        out.append("**The arithmetic:** ₦%s a pass at 1%% conversion needs **%s visits a day** for "
                   "₦%s a day. This site has **%s**."
                   % (_fmt(price), _fmt(need), _fmt(target),
                      _fmt(per_day) if per_day is not None else "no reading"))
        out.append("")
    rows = window(ledger, days, today)
    if rows:
        out.append("<details><summary>Last %d days</summary>" % len(rows))
        out.append("")
        out.append("| day | passes | ₦ | visits/day |")
        out.append("|---|---|---|---|")
        for row in reversed(rows):
            out.append("| %s | %s | %s | %s |" % (
                row.get("date"), _fmt(row.get("passes")), _fmt(row.get("revenue")),
                _fmt(((row.get("visits_7d") or 0) / 7.0)) if row.get("visits_7d") is not None else "—"))
        out.append("")
        out.append("</details>")
        out.append("")
    for problem in problems or []:
        out.append("_Not measured: %s._" % problem)
    if problems:
        out.append("")
    out.append("_Daily, from the owner dashboard API (passes, ₦, business teams) and Cloudflare Web "
               "Analytics (visits). The ledger is `logs/money_ledger.json`._")
    return "\n".join(out)


def machine_lines(found):
    return [
        "MONEY_TODAY=%d" % int(found.get("revenue_today") or 0),
        "MONEY_7D=%d" % int((found.get("week") or {}).get("revenue") or 0),
        "MONEY_28D=%d" % int((found.get("month") or {}).get("revenue") or 0),
        "MONEY_TARGET=%d" % int(found.get("target") or DEFAULT_TARGET),
        "MONEY_STAGE=%s" % found.get("stage", "unmeasured"),
        "MONEY_VISITS_PER_DAY=%s" % (found.get("visits_per_day") if found.get("visits_per_day") is not None else "unknown"),
    ]


# ── CLI ──────────────────────────────────────────────────────────────────────────────────

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="The daily money metre")
    sub = parser.add_subparsers(dest="cmd")

    p_pull = sub.add_parser("pull", help="read the dashboard and record today")
    p_pull.add_argument("--summary-file", default="")
    p_pull.add_argument("--dry-run", action="store_true", help="read and print, write nothing")
    p_pull.add_argument("--today", default="", help="override the date (tests)")

    p_brief = sub.add_parser("brief", help="render the ledger as markdown (no network)")
    p_brief.add_argument("--days", type=int, default=14)
    p_brief.add_argument("--today", default="")

    sub.add_parser("status", help="one line: today's naira and the stage")

    args = parser.parse_args(argv)
    today = getattr(args, "today", "") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if args.cmd == "pull":
        payload, problems = pull(passphrase=os.environ.get("DOCOGA_ADMIN_PASSPHRASE", "").strip())
        ledger = load_ledger()
        if payload:
            ledger = merge(ledger, rows_from(payload))
            if not args.dry_run:
                save_ledger(ledger)
        target = int(os.environ.get("DOCOGA_DAILY_TARGET") or DEFAULT_TARGET)
        found = diagnosis(ledger, today, target)
        text = brief(ledger, today, target, problems=problems)
        if args.summary_file:
            with open(args.summary_file, "w", encoding="utf-8") as handle:
                handle.write(text + "\n")
        print(text)
        for line in machine_lines(found):
            print(line)
        return 0

    if args.cmd == "brief":
        target = int(os.environ.get("DOCOGA_DAILY_TARGET") or DEFAULT_TARGET)
        print(brief(load_ledger(), today, target, days=args.days))
        return 0

    if args.cmd == "status":
        target = int(os.environ.get("DOCOGA_DAILY_TARGET") or DEFAULT_TARGET)
        found = diagnosis(load_ledger(), today, target)
        print("₦%s today · ₦%s in 7 days · stage %s"
              % (_fmt(found["revenue_today"]), _fmt(found["week"]["revenue"]), found["stage"]))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
