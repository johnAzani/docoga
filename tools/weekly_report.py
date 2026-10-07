#!/usr/bin/env python3
"""
tools/weekly_report.py — assemble a weekly DocOga growth report.

Pulls /api/admin/numbers (all-platform snapshot + KV history) and renders a
markdown report with data tables + verdict placeholders (the machine's analyst
fills verdicts).

Usage:
    python3 tools/weekly_report.py --week 1 [--key $DOCOGA_ADMIN_KEY] [--out REPORTS/WEEK-1.md]

Admin key comes from --key or env DOCOGA_ADMIN_KEY — NEVER hardcoded in the repo.
"""
import argparse, json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta

BASE = "https://docoga.com.ng/api/admin/numbers"


def pull(key):
    """Pull all-platform snapshot from admin API."""
    req = urllib.request.Request(BASE, headers={
        "x-admin-key": key,
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) DocOgaMachine/1.0"
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fmt(v, dash="\u2014"):
    """Format a number with commas, or dash if None."""
    if v is None:
        return dash
    try:
        return f"{int(v):,}"
    except (ValueError, TypeError):
        return str(v)


def main():
    ap = argparse.ArgumentParser(description="Assemble a weekly DocOga growth report")
    ap.add_argument("--week", type=int, required=True, help="Week number")
    ap.add_argument("--key", default=os.environ.get("DOCOGA_ADMIN_KEY", ""),
                    help="Admin key (or set DOCOGA_ADMIN_KEY env)")
    ap.add_argument("--out", default=None, help="Output path (default: REPORTS/WEEK-N.md)")
    args = ap.parse_args()

    if not args.key:
        sys.exit("Admin key required: --key or DOCOGA_ADMIN_KEY env (never commit it)")

    d = pull(args.key)
    if not d.get("ok"):
        sys.exit(f"numbers pull failed: {json.dumps(d)[:200]}")

    lagos = timezone(timedelta(hours=1))
    now = datetime.now(lagos)

    ig  = d.get("ig", {})
    yt  = d.get("yt", {})
    fb  = d.get("fb", {})
    th  = d.get("threads", {})
    tg  = d.get("tg", {})
    ytc = yt.get("channel") or {}
    fbp = fb.get("page") or {}

    lines = []
    A = lines.append

    A(f"# DocOga \u2014 Week {args.week} Growth Report")
    A(f"*Generated {now.strftime('%a %d %b %Y, %H:%M WAT')} "
      f"\u2014 machine-assembled from live platform APIs (zero screenshots).*")
    A("")

    # ── 1. Platform scoreboard ──
    A("## 1. Platform scoreboard")
    A("")
    A("| Platform | Handle | Audience | Content live | Notes |")
    A("|---|---|---|---|---|")
    n_ig_media = len(ig.get("media") or [])
    A(f"| Instagram | @docoga.ng | {fmt(ig.get('followers'))} followers | "
      f"{fmt(ig.get('mediaCount'))} media ({n_ig_media} listed) | reels + stories + feed |")
    A(f"| YouTube | @docoga_ng | {fmt(ytc.get('subs'))} subs | "
      f"{fmt(ytc.get('videoCount'))} videos, {fmt(ytc.get('views'))} views | "
      f"permanent production tokens; Deep-Dives start Mon |")
    A(f"| Facebook | facebook.com/docoga.com.ng | {fmt(fbp.get('fans'))} fans | "
      f"{fmt(len(fb.get('videos') or []))} videos | Legal Service category; vanity URL live |")
    A(f"| Threads | @{(th.get('profile') or {}).get('username', 'docoga.ng')} | "
      f"new | {fmt(len(th.get('posts') or []))} posts | connected 27 Sep |")
    A(f"| Telegram | @docogadaily | "
      f"{fmt(tg.get('members')) if tg.get('ok') else '\u2014'} members | "
      f"daily posts | |")
    A(f"| Google | docoga.com.ng | {d.get('historyDays', 0)} history days | "
      f"30 locations live | caution-fee pillar LIVE; GSC ~1 Oct |")
    A("")

    # ── 2. Content this week ──
    A("## 2. Content this week (per-media live numbers)")
    A("")
    A("| Date | Platform | Type | Views | Reach | Likes | Saves | Shares | Hook |")
    A("|---|---|---|---|---|---|---|---|---|")
    for m in (ig.get("media") or []):
        ins = m.get("insights") or {}
        A(f"| {(m.get('at') or '')[:10]} | IG | {m.get('kind')} | "
          f"{fmt(ins.get('views'))} | {fmt(ins.get('reach'))} | {fmt(m.get('likes'))} | "
          f"{fmt(ins.get('saved'))} | {fmt(ins.get('shares'))} | (see HOOK-LEDGER) |")
    for v in (yt.get("videos") or []):
        A(f"| {(v.get('at') or '')[:10]} | YT | video | {fmt(v.get('views'))} | "
          f"\u2014 | \u2014 | \u2014 | \u2014 | (see HOOK-LEDGER) |")
    A("")

    # ── 3. Hook Lab ──
    A("## 3. Hook Lab status")
    A("")
    A("*Pull from HOOK-LEDGER.md \u2014 archetypes run so far, first ranking due after 10 tagged reels.*")
    A("")

    # ── 4. Money ──
    A("## 4. Money")
    A("")
    A("*Oga Pass sales, unlock-code usage, Flutterwave balance \u2014 fill from admin dashboard.*")
    A("")

    # ── 5. Verdicts ──
    A("## 5. Verdicts & next week's bets")
    A("")
    A("*(machine analyst fills: what worked, what to stop, what to double)*")
    A("")

    # ── 6. Trend history ──
    A("## 6. Trend history (stored daily by /api/admin/numbers)")
    A("")
    hist_note = (f"{d.get('historyDays', 0)} day(s) stored in KV numbers:history "
                 f"\u2014 trend table becomes meaningful from week 2.")
    A(f"_{hist_note}_")
    A("")

    # Write report
    out = args.out or f"REPORTS/WEEK-{args.week}.md"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"report written: {out} ({len(lines)} lines)")


if __name__ == "__main__":
    main()