#!/usr/bin/env python3
"""gemini_quota.py — the narrator's bucket, known rather than guessed.

Owner, 15 Oct 2026, after a Short shipped without its voice: "I want to
automatically know when the voice over resets and automatically continue at that
time instead of a retry cron three hours after. I want it to be knowledgeable."

What the machine knows, and where it learns it:

  * A Gemini 429 is not just a `retryDelay`. Its QuotaFailure detail names the
    quota that tripped — `quotaId` says **PerMinute** or **PerDay**, `quotaValue`
    is the limit, `quotaDimensions.model` the model. `parse_refusal()` reads all
    of it. A per-minute refusal is a short wait; a per-day refusal is an
    appointment.
  * Free-tier daily buckets reset at **midnight Pacific time**. `next_reset()`
    computes that instant from the zone itself (America/Los_Angeles), so it is
    08:00 WAT now and becomes 09:00 WAT when US clocks change — no hour is hard-coded.
  * A small ledger (`LEDGER`, kept beside the narrator's clip cache so the same
    actions/cache entry carries both) counts every narrator request per Pacific
    day across all lanes and remembers the last refusal. Google offers no
    "remaining quota" endpoint; this count, corrected by what the API reports on a
    refusal, is as knowledgeable as the platform allows.

CLI (used by the workflows):
  status                      one line: used / limit / resets at
  just-reset [--window MIN]   exit 0 if a Pacific midnight passed within MIN minutes
  owed [--date YYYY-MM-DD]    which scheduled Shorts/Reels have no publish yet
  resets-at                   the next reset, ISO, Lagos time
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PACIFIC = ZoneInfo("America/Los_Angeles")
LAGOS = ZoneInfo("Africa/Lagos")
LEDGER = Path(os.environ.get("GEMINI_QUOTA_LEDGER") or (ROOT / "assets" / "shorts_voice" / "quota.json"))

# Planning hint until the API has named the real limit on a refusal. The TTS
# preview models' free bucket is small; the figure is overwritten by `quotaValue`.
DEFAULT_DAILY_LIMIT_HINT = int(os.environ.get("GEMINI_TTS_DAILY_LIMIT", "10"))
JUST_RESET_WINDOW_MIN = 90


# ───────────────────────────── time ─────────────────────────────
def now_utc():
    return datetime.now(timezone.utc)


def pacific_day(now=None):
    return (now or now_utc()).astimezone(PACIFIC).date().isoformat()


def next_reset(now=None):
    """The next midnight in America/Los_Angeles, as an aware UTC datetime."""
    now = now or now_utc()
    local = now.astimezone(PACIFIC)
    midnight = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), tzinfo=PACIFIC)
    return midnight.astimezone(timezone.utc)


def last_reset(now=None):
    now = now or now_utc()
    local = now.astimezone(PACIFIC)
    midnight = datetime.combine(local.date(), datetime.min.time(), tzinfo=PACIFIC)
    return midnight.astimezone(timezone.utc)


def just_reset(now=None, window_min=JUST_RESET_WINDOW_MIN):
    now = now or now_utc()
    return (now - last_reset(now)) <= timedelta(minutes=window_min)


def lagos(dt):
    return dt.astimezone(LAGOS).strftime("%H:%M WAT, %a %d %b")


def human_wait(seconds):
    seconds = max(0, int(seconds))
    h, m = divmod(seconds // 60, 60)
    if h:
        return "%d h %02d min" % (h, m)
    return "%d min" % m if m else "%d s" % seconds


# ───────────────────────────── the refusal ─────────────────────────────
def parse_refusal(body):
    """Read a Gemini 429 body. Returns a dict:
    scope: 'day' | 'minute' | 'unknown'; retry_s: float|None; limit: int|None;
    model: str; quota_id: str; metric: str."""
    out = {"scope": "unknown", "retry_s": None, "limit": None, "model": "", "quota_id": "", "metric": ""}
    text = body if isinstance(body, str) else json.dumps(body)
    m = re.search(r"retry in ([0-9.]+)\s*s", text, re.I) or re.search(r'"retryDelay":\s*"([0-9.]+)s"', text)
    if m:
        out["retry_s"] = float(m.group(1))
    data = None
    if isinstance(body, dict):
        data = body
    else:
        try:
            data = json.loads(text)
        except ValueError:
            data = None
    violations = []
    if isinstance(data, dict):
        for detail in (data.get("error") or {}).get("details") or []:
            for v in detail.get("violations") or []:
                violations.append(v)
    if violations:
        v = violations[0]
        out["quota_id"] = str(v.get("quotaId") or "")
        out["metric"] = str(v.get("quotaMetric") or "")
        out["model"] = str((v.get("quotaDimensions") or {}).get("model") or "")
        try:
            out["limit"] = int(float(v.get("quotaValue")))
        except (TypeError, ValueError):
            pass
    probe = (out["quota_id"] + " " + out["metric"] + " " + text[:800]).lower()
    if "perday" in probe or "per day" in probe or "daily" in probe or "requests_per_day" in probe:
        out["scope"] = "day"
    elif "perminute" in probe or "per minute" in probe or "requests_per_minute" in probe:
        out["scope"] = "minute"
    elif out["retry_s"] is not None and out["retry_s"] >= 3600:
        out["scope"] = "day"
    return out


def wait_seconds(refusal, now=None):
    """How long to wait before the *next* request can succeed.
    Per-day: until the Pacific midnight. Otherwise what the API said (fallback 60 s)."""
    now = now or now_utc()
    if refusal.get("scope") == "day":
        return max(60.0, (next_reset(now) - now).total_seconds() + 60.0)
    return float(refusal.get("retry_s") or 60.0)


# ───────────────────────────── the ledger ─────────────────────────────
def _empty(day):
    return {"pacific_day": day, "requests": {}, "limit": {}, "exhausted": {}, "updated": None}


def load(now=None):
    day = pacific_day(now)
    try:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _empty(day)
    if data.get("pacific_day") != day:
        # A new Pacific day: the counts and the refusal are history; the learnt limits stay.
        fresh = _empty(day)
        fresh["limit"] = data.get("limit") or {}
        return fresh
    data.setdefault("requests", {})
    data.setdefault("limit", {})
    data.setdefault("exhausted", {})
    return data


def save(data):
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass  # a read-only checkout must never fail a render over bookkeeping


def note_request(model, outcome, refusal=None, lane=None, now=None):
    """Record one narrator request. outcome: 'ok' | 'exhausted' | 'fail'."""
    now = now or now_utc()
    lane = lane or os.environ.get("NARRATOR_LANE") or os.environ.get("GITHUB_WORKFLOW") or "local"
    data = load(now)
    model = model or "unknown"
    data["requests"].setdefault(model, {"ok": 0, "exhausted": 0, "fail": 0, "by_lane": {}})
    rec = data["requests"][model]
    rec[outcome] = rec.get(outcome, 0) + 1
    rec["by_lane"][lane] = rec["by_lane"].get(lane, 0) + 1
    if refusal:
        if refusal.get("limit"):
            data["limit"][model] = refusal["limit"]
        if refusal.get("scope") == "day":
            data["exhausted"][model] = {"at": now.isoformat(timespec="seconds"),
                                       "resumes_at": next_reset(now).isoformat(timespec="seconds"),
                                       "quota_id": refusal.get("quota_id", "")}
    data["updated"] = now.isoformat(timespec="seconds")
    save(data)
    return data


def state(now=None):
    """What the machine knows right now."""
    now = now or now_utc()
    data = load(now)
    used = sum(r.get("ok", 0) for r in data["requests"].values())
    limits = [v for v in data["limit"].values() if v]
    limit = min(limits) if limits else None
    resumes = None
    for ex in data["exhausted"].values():
        try:
            when = datetime.fromisoformat(ex["resumes_at"])
        except (KeyError, ValueError):
            continue
        if when > now and (resumes is None or when < resumes):
            resumes = when
    return {"pacific_day": data["pacific_day"], "used": used, "limit": limit,
            "limit_hint": limit or DEFAULT_DAILY_LIMIT_HINT, "limit_known": limit is not None,
            "exhausted": resumes is not None, "resumes_at": resumes, "next_reset": next_reset(now)}


def remaining(need=0, now=None):
    """(enough, remaining_estimate) for a lane that needs `need` more requests."""
    st = state(now)
    if st["exhausted"]:
        return False, 0
    left = max(0, st["limit_hint"] - st["used"])
    return left >= need, left


def status_line(now=None):
    now = now or now_utc()
    st = state(now)
    limit = "%d" % st["limit_hint"] + ("" if st["limit_known"] else " (hint; the API names the real limit on the first refusal)")
    line = "narrator bucket: %d of %s used this Pacific day" % (st["used"], limit)
    if st["exhausted"]:
        line += " · EXHAUSTED — resumes %s (in %s)" % (lagos(st["resumes_at"]),
                                                      human_wait((st["resumes_at"] - now).total_seconds()))
    else:
        line += " · resets %s (in %s)" % (lagos(st["next_reset"]), human_wait((st["next_reset"] - now).total_seconds()))
    return line


# ───────────────────────────── what is owed ─────────────────────────────
# A lane is owed when its most recent scheduled slot has passed and nothing has
# been published since. "Since" matters: a hand-run publish the next morning
# settles the debt; the resumer must not add a third Short to the week.
SHORTS_SLOT = {"weekdays": (1, 4), "utc_hour": 17, "utc_minute": 0}    # youtube_scheduled.yml
REELS_SLOT = {"weekdays": (0, 3), "utc_hour": 8, "utc_minute": 30}     # facebook_autopost.yml, Mon/Thu
OWED_LOOKBACK_DAYS = 3


def _last_due(now, slot, lookback=OWED_LOOKBACK_DAYS):
    for back in range(lookback + 1):
        d = now.astimezone(timezone.utc).date() - timedelta(days=back)
        if d.weekday() not in slot["weekdays"]:
            continue
        at = datetime(d.year, d.month, d.day, slot["utc_hour"], slot["utc_minute"], tzinfo=timezone.utc)
        if at <= now:
            return at
    return None


def _ledger_dates(path, keys=("date", "run_date", "day", "recorded_at")):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    items = data if isinstance(data, list) else (data.get("published") or data.get("entries") or data.get("reels") or [])
    out = set()
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        for k in keys:
            v = it.get(k)
            if isinstance(v, str) and len(v) >= 10:
                out.add(v[:10])
                break
    return out


def owed(now=None, root=ROOT):
    """Lanes whose most recent scheduled slot has passed with no publish on or after it."""
    now = now or now_utc()
    out = []
    for lane, slot, ledger in (("shorts", SHORTS_SLOT, root / "logs" / "youtube_published.json"),
                               ("reel", REELS_SLOT, root / "logs" / "facebook_reels.json")):
        due = _last_due(now, slot)
        if not due:
            continue
        due_day = due.astimezone(LAGOS).date().isoformat()
        if not any(d >= due_day for d in _ledger_dates(ledger)):
            out.append({"lane": lane, "date": due_day})
    return out


# ───────────────────────────── CLI ─────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("resets-at")
    jr = sub.add_parser("just-reset")
    jr.add_argument("--window", type=int, default=JUST_RESET_WINDOW_MIN)
    ow = sub.add_parser("owed")
    ow.add_argument("--date", help="ISO date (judged at 23:00 UTC that day) or ISO datetime")
    args = ap.parse_args(argv)
    now = now_utc()
    if args.cmd == "status":
        print(status_line(now))
        return 0
    if args.cmd == "resets-at":
        print(next_reset(now).astimezone(LAGOS).isoformat(timespec="minutes"))
        return 0
    if args.cmd == "just-reset":
        ok = just_reset(now, args.window)
        print("%s — last Pacific midnight %s, now %s" % ("yes" if ok else "no", lagos(last_reset(now)), lagos(now)))
        gh = os.environ.get("GITHUB_OUTPUT")
        if gh:
            with open(gh, "a", encoding="utf-8") as fh:
                fh.write("just_reset=%s\n" % ("yes" if ok else "no"))
        return 0 if ok else 1
    if args.cmd == "owed":
        at = (datetime.fromisoformat(args.date).replace(tzinfo=timezone.utc) if "T" in args.date
              else datetime.combine(date.fromisoformat(args.date), datetime.min.time(), tzinfo=timezone.utc)
              + timedelta(hours=23)) if args.date else now
        items = owed(at)
        for it in items:
            print("%s %s" % (it["lane"], it["date"]))
        if not items:
            print("nothing owed — every scheduled Short/Reel in the last %d days is in its ledger" % OWED_LOOKBACK_DAYS)
        gh = os.environ.get("GITHUB_OUTPUT")
        if gh:
            with open(gh, "a", encoding="utf-8") as fh:
                fh.write("owed_shorts=%s\n" % ("yes" if any(i["lane"] == "shorts" for i in items) else "no"))
                fh.write("owed_reel=%s\n" % ("yes" if any(i["lane"] == "reel" for i in items) else "no"))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
