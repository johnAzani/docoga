#!/usr/bin/env python3
"""dashboard_feed.py — what the owner dashboard cannot see from Cloudflare: the repo's own records.

The dashboard (site/admin.html + worker/index.js /admin/*) reads KV. The social lanes and
the brain write their truth into this repository — ledgers under logs/, approved packs
under brain/drafts/, the weekly scorecard, the YouTube snapshot. The worker holds a
GitHub token that may read Actions but not contents, so a workflow on this side builds
one compact JSON ("the feed") and PUTs it into the worker's KV namespace with the
Cloudflare token the deploys already use. One key, ₦0, no new secret.

    python3 tools/dashboard_feed.py build  [--out feed.json]     # the JSON, from the repo
    python3 tools/dashboard_feed.py push   [--in feed.json]      # PUT it to KV (needs
          CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID; the namespace id is read from
          worker/wrangler.toml so it cannot drift from the worker)

What the feed carries (ADMIN_DASHBOARD.md §5c):
  plan     today + next 2 days: the brain's approved pack per day (theme, headline, Threads
           line, Short title, who it is for, why) — or "no approved pack: the lanes post
           from the rotation", which is the honest sentence when the brain had no quota.
  posted   the last 40 things the lanes published, newest first, with the link.
  youtube  the latest channel snapshot + what is scheduled to go public.
  growth   followers per platform from the last scorecard (YouTube from its own snapshot
           until then), each with the milestone it is walking towards.
  deepdive the next episode in the queue.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAGOS = timezone(timedelta(hours=1))
KV_KEY = "adm:feed"
POSTED_CAP = 40

# ledger file → (platform, kind). Every ledger is a list of youtube_ledger.py-shaped rows.
LEDGERS = [
    ("logs/instagram_sent.json", "instagram", "post"),
    ("logs/threads_sent.json", "threads", "post"),
    ("logs/telegram_sent.json", "telegram", "post"),
    ("logs/facebook_reels.json", "facebook", "reel"),
    ("logs/linkedin_posts.json", "linkedin", "post"),
    ("logs/youtube_published.json", "youtube", "short"),
    ("logs/youtube_longform.json", "youtube", "deep-dive"),
]
GROWTH_KEYS = [
    ("facebook.followers", "Facebook", "followers"),
    ("instagram.followers", "Instagram", "followers"),
    ("threads.followers", "Threads", "followers"),
    ("telegram.members", "Telegram", "members"),
    ("youtube.subscribers", "YouTube", "subscribers"),
    ("linkedin.followers", "LinkedIn", "followers"),
]


def _load_from(root, rel):
    try:
        return json.loads((root / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _stamp(value):
    """ISO stamp (any zone, or a bare date) → aware UTC datetime, or None."""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LAGOS)
    return parsed.astimezone(timezone.utc)


def _first_line(text, limit=140):
    line = str(text or "").strip().split("\n")[0].strip()
    return (line[: limit - 1] + "…") if len(line) > limit else line


def plan(now, root=ROOT, days=3):
    """The brain's approved packs for today and the next days, or the honest absence."""
    out = []
    today = now.astimezone(LAGOS).date()
    for i in range(days):
        day = today + timedelta(days=i)
        p = root / "brain" / "drafts" / ("%s.json" % day.isoformat())
        row = {"date": day.isoformat(), "approved": False}
        try:
            pack = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
        except (OSError, ValueError):
            pack = None
        if isinstance(pack, dict) and pack.get("status") == "approved" and (pack.get("post") or {}).get("headline"):
            short = pack.get("short") if isinstance(pack.get("short"), dict) else {}
            threads = pack.get("threads") if isinstance(pack.get("threads"), dict) else {}
            row.update({
                "approved": True,
                "theme": str(pack.get("theme") or "")[:60],
                "headline": _first_line(pack["post"].get("headline"), 120),
                "lines": [_first_line(x, 120) for x in (pack["post"].get("lines") or [])][:5],
                "threads": _first_line(threads.get("text"), 160),
                "threads_evening": _first_line(threads.get("evening"), 160),
                "short": _first_line(short.get("title"), 120) if short else "",
                "reader": str(pack.get("reader") or "")[:80],
                "tool": pack.get("tool"),
                "state": pack.get("state"),
                "why": _first_line(pack.get("why"), 160),
                "quiz": bool(pack.get("quiz")),
                "generated_at": pack.get("generated_at"),
            })
        out.append(row)
    return out


def posted(root=ROOT, cap=POSTED_CAP):
    rows = []
    for rel, platform, kind in LEDGERS:
        data = _load_from(root, rel)
        if not isinstance(data, list):
            continue
        for e in data:
            if not isinstance(e, dict):
                continue
            at = _stamp(e.get("recorded_at") or e.get("date"))
            if at is None:
                continue
            url = str(e.get("url") or "")
            if platform == "facebook" and url.startswith("/"):
                url = "https://www.facebook.com" + url
            rows.append({
                "at": at.isoformat().replace("+00:00", "Z"), "platform": platform, "kind": kind,
                "title": _first_line(e.get("topic") if kind in ("short", "deep-dive", "reel") else (e.get("title") or e.get("topic")), 120) or _first_line(e.get("title"), 120),
                "url": url, "privacy": e.get("privacy") or "", "state": e.get("state") or "",
                "publish_at": e.get("publish_at") or e.get("publishAt") or None,
            })
    rows.sort(key=lambda r: r["at"], reverse=True)
    return rows[:cap]


def youtube(root=ROOT):
    stats = _load_from(root, "logs/youtube_stats.json")
    latest = stats[-1] if isinstance(stats, list) and stats else None
    out = {"snapshot": None, "scheduled": []}
    if isinstance(latest, dict):
        ch = latest.get("channel") or {}
        out["snapshot"] = {"taken_at": latest.get("taken_at"), "subscribers": ch.get("subscribers"), "views": ch.get("views"), "videos": ch.get("videos"),
                           "top": sorted([{"title": _first_line(v.get("title"), 80), "views": v.get("views") or 0, "kind": v.get("kind"), "id": v.get("id")}
                                          for v in (latest.get("videos") or []) if isinstance(v, dict)], key=lambda v: -int(v["views"] or 0))[:5]}
    for rel in ("logs/youtube_published.json", "logs/youtube_longform.json"):
        data = _load_from(root, rel)
        for e in data if isinstance(data, list) else []:
            if not isinstance(e, dict):
                continue
            when = e.get("publish_at") or e.get("publishAt")
            if str(e.get("privacy") or "") == "private" or when:
                out["scheduled"].append({"title": _first_line(e.get("title"), 100), "url": e.get("url"), "publish_at": when, "privacy": e.get("privacy"), "state": e.get("state")})
    return out


def growth(root=ROOT):
    """Latest audience numbers + milestones. Scorecard first; YouTube's own snapshot fills in."""
    hist = _load_from(root, "logs/scorecard.json")
    latest = hist[-1] if isinstance(hist, list) and hist else None
    prev = hist[-2] if isinstance(hist, list) and len(hist) > 1 else None
    k = (latest or {}).get("kpis") or {}
    pk = (prev or {}).get("kpis") or {}
    goals = _load_from(root, "brain/goals.json") or {}
    milestones = goals.get("milestones") or {}
    yt = _load_from(root, "logs/youtube_stats.json")
    yt_latest = (yt[-1] if isinstance(yt, list) and yt else {}) or {}
    rows = []
    for key, label, unit in GROWTH_KEYS:
        now_v = k.get(key)
        source = "scorecard" if now_v is not None else None
        if now_v is None and key == "youtube.subscribers" and (yt_latest.get("channel") or {}).get("subscribers") is not None:
            now_v, source = yt_latest["channel"]["subscribers"], "youtube_stats"
        ms = milestones.get(key) or {}
        rows.append({"key": key, "label": label, "unit": unit, "value": now_v, "previous": pk.get(key), "source": source,
                     "target": ms.get("target"), "due": ms.get("due"), "unlocks": ms.get("unlocks")})
    return {"taken_at": (latest or {}).get("taken_at") or None, "week": (latest or {}).get("week"), "rows": rows,
            "sales_week": k.get("sales.passes"), "grades": (latest or {}).get("grades") or {},
            "orders": [str(o)[:160] for o in ((latest or {}).get("orders") or [])][:6]}


def deepdive_next(root=ROOT):
    try:
        r = subprocess.run([sys.executable, str(root / "tools" / "deepdive_queue.py"), "next"], capture_output=True, text=True, timeout=30, cwd=str(root))
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def build(now=None, root=ROOT):
    now = now or datetime.now(timezone.utc)
    feed = {
        "version": 1,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "plan": plan(now, root),
        "posted": posted(root),
        "youtube": youtube(root),
        "growth": growth(root),
        "deepdive_next": deepdive_next(root),
    }
    feed["brain_note"] = ("the brain has an approved pack for today" if feed["plan"] and feed["plan"][0]["approved"]
                          else "no approved pack for today — the lanes post from the rotation (the brain had no quota, or every draft failed a gate)")
    return feed


def namespace_id(root=ROOT):
    text = (root / "worker" / "wrangler.toml").read_text(encoding="utf-8")
    m = re.search(r'\[\[kv_namespaces\]\][^\[]*?\bid\s*=\s*"([0-9a-f]{32})"', text, re.S)
    if not m:
        raise SystemExit("worker/wrangler.toml: no kv_namespaces id")
    return m.group(1)


def push(feed, env=None, root=ROOT, http=None):
    env = dict(os.environ) if env is None else env
    token = (env.get("CLOUDFLARE_API_TOKEN") or "").strip()
    account = (env.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    if not (token and account):
        return 0, "CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID not set"
    url = "https://api.cloudflare.com/client/v4/accounts/%s/storage/kv/namespaces/%s/values/%s" % (account, namespace_id(root), KV_KEY)
    body = json.dumps(feed, separators=(",", ":")).encode("utf-8")
    if len(body) > 400_000:
        return 0, "feed is %d bytes — too large for one key; trim POSTED_CAP" % len(body)
    req = urllib.request.Request(url, data=body, method="PUT", headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    sender = http or (lambda r: urllib.request.urlopen(r, timeout=40))
    try:
        with sender(req) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8", "replace"))
            msg = "; ".join(str(x.get("message")) for x in (detail.get("errors") or [])) or str(e.code)
        except ValueError:
            msg = str(e.code)
        return e.code, msg
    except (urllib.error.URLError, OSError) as e:
        return 0, str(e)


def main(argv=None):
    ap = argparse.ArgumentParser(description="build / push the owner-dashboard feed")
    ap.add_argument("cmd", choices=["build", "push"])
    ap.add_argument("--out", default="")
    ap.add_argument("--in", dest="inp", default="")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        feed = build()
        text = json.dumps(feed, indent=1, ensure_ascii=False)
        if a.out:
            Path(a.out).write_text(text, encoding="utf-8")
        else:
            print(text)
        print("FEED_POSTED=%d FEED_PLAN=%s" % (len(feed["posted"]), ",".join("%s:%s" % (p["date"], "ok" if p["approved"] else "rotation") for p in feed["plan"])), file=sys.stderr)
        return 0
    feed = json.loads(Path(a.inp).read_text(encoding="utf-8")) if a.inp else build()
    status, problem = push(feed)
    if status == 200:
        print("FEED_PUSH=ok bytes=%d" % len(json.dumps(feed, separators=(",", ":"))))
        return 0
    print("FEED_PUSH=failed status=%s %s" % (status, problem))
    print("::error title=Dashboard feed not pushed::%s — the Content tab shows the last feed it had, with its age" % (problem or status))
    return 1


if __name__ == "__main__":
    sys.exit(main())
