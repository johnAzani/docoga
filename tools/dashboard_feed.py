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


def _series_line(series):
    """'Rent receipt law · part 2 of 5' when the Short was written to the week's series."""
    if not isinstance(series, dict) or not series.get("name"):
        return ""
    return "%s · part %s of %s" % (series["name"], series.get("part"), series.get("total"))


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
                "series": _series_line(short.get("series")) if short else "",
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
    # TikTok keeps a dict ledger ({"entries": [...]}) and no public URL: the Short sits in the
    # owner's inbox until they post it from the app, so the row says "inbox draft".
    tk = _load_from(root, "logs/tiktok_drafts.json")
    for e in (tk.get("entries") if isinstance(tk, dict) else []) or []:
        if not isinstance(e, dict):
            continue
        at = _stamp(e.get("recorded_at"))
        if at is None:
            continue
        rows.append({"at": at.isoformat().replace("+00:00", "Z"), "platform": "tiktok", "kind": "inbox draft",
                     "title": _first_line(e.get("caption"), 120) or "Short", "url": "",
                     "privacy": "", "state": str(e.get("status") or ""), "publish_at": None})
    rows.sort(key=lambda r: r["at"], reverse=True)
    return rows[:cap]


def tiktok(root=ROOT):
    """Is the TikTok lane connected? Read from the sealed box's header — never its contents.

    Since 22 Oct 2026 the dict also carries the latest inbox draft's full caption: TikTok's inbox
    API accepts no caption and the Telegram DM needs a handshake the owner has not done, so the
    dashboard is the place he copies it from (owner, 22 Oct: "I am not having the TikTok captions")."""
    try:
        payload = json.loads((root / "logs" / "tiktok_refresh_token.box").read_text(encoding="utf-8"))
        out = {"connected": bool(payload.get("ciphertext")), "since": payload.get("minted_at"), "expires": payload.get("expires_at")}
    except (OSError, ValueError):
        out = {"connected": False, "since": None, "expires": None}
    out["owner_linked"] = (root / "logs" / "telegram_owner.json").is_file()
    tk = _load_from(root, "logs/tiktok_drafts.json")
    entries = [e for e in ((tk.get("entries") if isinstance(tk, dict) else []) or []) if isinstance(e, dict) and _stamp(e.get("recorded_at"))]
    latest = max(entries, key=lambda e: _stamp(e.get("recorded_at"))) if entries else None
    out["draft"] = ({"at": _stamp(latest.get("recorded_at")).isoformat().replace("+00:00", "Z"), "video": str(latest.get("video") or ""),
                     "caption": str(latest.get("caption") or "")[:2200], "status": str(latest.get("status") or "")}
                    if latest else None)
    return out


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


# ───────────────────────────── the watch list ─────────────────────────────
# Owner, 21 Oct 2026: "I want to see this plan on my admin dashboard" — the evening's list
# ("6:00pm Short renders, uploads scheduled for 7:00pm, hands its video to Threads; 7:10pm
# Instagram; 8:10pm Threads' first video; 1:30am the Brain writes Deep-Dive 4"). The clock's
# board already shows which lane RAN; this says in plain words what each slot is MEANT to
# produce and, once the time has passed, what the repo's ledgers say came out, with the link.
# Times are the lanes' own crons (Lagos). Evidence is read from the same ledgers `posted()` reads.

WATCH_GRACE_MIN = 75          # a slot is "not recorded" only this long after its time


def _rows(root, rel):
    data = _load_from(root, rel)
    if isinstance(data, dict):
        data = data.get("entries") or data.get("history") or data.get("done") or []
    return [r for r in (data or []) if isinstance(r, dict)]


def _between(rows, start, end, key="recorded_at"):
    out = []
    for r in rows:
        at = _stamp(r.get(key) or r.get("at") or r.get("hosted_at"))
        if at and start <= at <= end:
            out.append(r)
    return out


def _lagos_at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=LAGOS).astimezone(timezone.utc)


def _ig_hour(root):
    slots = _load_from(root, "brain/slots.json") or {}
    try:
        return int(((slots.get("lanes") or {}).get("instagram") or {}).get("hour_wat") or 19)
    except (TypeError, ValueError):
        return 19


def _ev(label, ok, url=None, detail=None):
    row = {"label": label, "ok": ok}
    if url:
        row["url"] = url
    if detail:
        row["detail"] = _first_line(detail, 120)
    return row


def _settle(item, now):
    """status from the clock and the evidence: due · done · partial · missing · skipped."""
    at = _stamp(item["at"])
    if item.get("status") == "skipped":
        return item
    if now < at:
        item["status"] = "due"
        return item
    ev = item.get("evidence") or []
    hits = [e for e in ev if e.get("ok") is True]
    checks = [e for e in ev if e.get("ok") is not None]
    if not checks:
        item["status"] = "ran" if now >= at else "due"   # nothing in the repo can confirm it; the board row can
    elif len(hits) == len(checks):
        item["status"] = "done"
    elif hits:
        item["status"] = "partial"
    else:
        item["status"] = "missing" if now >= at + timedelta(minutes=WATCH_GRACE_MIN) else "running"
    return item


def watch(now=None, root=ROOT):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(LAGOS).date()
    tomorrow = today + timedelta(days=1)
    weekday = today.weekday()
    items = []
    grace = timedelta(hours=3)

    threads = _rows(root, "logs/threads_sent.json")
    insta = _rows(root, "logs/instagram_sent.json")
    tele = _rows(root, "logs/telegram_sent.json")
    shorts = _rows(root, "logs/youtube_published.json")
    longform = _rows(root, "logs/youtube_longform.json")
    media = _rows(root, "logs/shorts_media.json")
    tiktok_rows = _rows(root, "logs/tiktok_drafts.json")
    dd_attempts = _rows(root, "logs/brain_deepdive.json")
    reels = _rows(root, "logs/facebook_reels.json")

    def ledger_hit(rows, at, label, what="post"):
        got = _between(rows, at - timedelta(minutes=20), at + grace)
        if got:
            r = got[0]
            return _ev(label, True, r.get("url"), r.get("title") or r.get("topic"))
        return _ev(label, False, None, "nothing in the ledger yet")

    # 1:30am — the brain (today's run, already behind us; and tonight's, ahead)
    def brain_item(day):
        at = _lagos_at(day, 1, 30)
        pack = _load_from(root, "brain/drafts/%s.json" % day.isoformat())
        queued = deepdive_next(root)
        ev = [_ev("approved pack for %s" % day.strftime("%a %d %b"), bool(pack) if now >= at else None,
                  None, (pack or {}).get("theme") if pack else "no pack — the lanes post from the rotation")]
        tries = [a for a in dd_attempts if str(a.get("at", ""))[:10] == day.isoformat()]
        if tries:
            last = tries[-1]
            ok = last.get("outcome") == "written"
            ev.append(_ev("Deep-Dive %s" % last.get("episode", ""), ok, None,
                          ("written — %s" % last.get("title")) if ok else "%s: %s" % (last.get("outcome"), "; ".join(last.get("problems") or [])[:100])))
        elif now >= at:
            ev.append(_ev("Deep-Dive draft", None if queued else False, None,
                          ("not needed — %s is queued" % queued) if queued else "no attempt recorded"))
        expect = ["writes the day's content (Telegram/Facebook post, Threads and Instagram copy, the Short's topic)"]
        expect.append("tries to write the next Deep-Dive episode (the queue is empty)" if not queued
                      else "the Deep-Dive queue already holds %s — no new episode needed" % queued)
        return {"at": at.isoformat().replace("+00:00", "Z"), "lane": "Brain", "title": "The Brain plans the day", "expect": expect, "evidence": ev}

    items.append(brain_item(today))

    # 4:00am — Deep-Dive lane
    at = _lagos_at(today, 4, 0)
    queued = deepdive_next(root)
    got = _between(longform, at - timedelta(minutes=30), at + timedelta(hours=6))
    if got:
        r = got[0]
        ev = [_ev("episode uploaded", True, r.get("url"), r.get("title")),
              _ev("scheduled to go public", bool(r.get("publish_at")), None, r.get("publish_at") and ("public at " + _lagos_text(r["publish_at"])))]
        items.append({"at": at.isoformat().replace("+00:00", "Z"), "lane": "Deep-Dive", "title": "Deep-Dive narrated, rendered, uploaded",
                      "expect": ["narrates with the locked voice, renders, uploads private + scheduled for its Saturday 7:00pm"], "evidence": ev})
    else:
        items.append({"at": at.isoformat().replace("+00:00", "Z"), "lane": "Deep-Dive",
                      "title": ("Deep-Dive lane produces %s" % queued) if queued else "Deep-Dive lane: nothing queued — skips",
                      "expect": (["narrates, renders and uploads %s, scheduled for the next free Saturday 7:00pm" % queued] if queued
                                 else ["the queue is empty; the Brain fills it at 1:30am when the last upload is 4+ days old"]),
                      "evidence": [_ev("episode uploaded", False, None, "nothing in the long-form ledger")] if queued else [],
                      "status": None if queued else "skipped"})

    # Threads ×3
    for hour, minute, name, extra in ((7, 20, "morning card", None), (13, 10, "lunch card (+ poll in our reply)", None),
                                      (20, 10, "evening card", "video")):
        at = _lagos_at(today, hour, minute)
        expect = ["posts the %s" % name]
        ev = [ledger_hit(threads, at, "Threads post")]
        if extra == "video":
            hosted = [m for m in media if m.get("date") == today.isoformat()]
            if weekday < 5:
                expect = ["posts today's Short as a native VIDEO (the first Threads videos began 21 Oct); falls back to the card if the video is not live"]
                ev.append(_ev("Short handed over by the 6:00pm lane", bool(hosted) if now >= _lagos_at(today, 18, 40) else None, None,
                              hosted[0].get("title") if hosted else "not yet"))
        items.append({"at": at.isoformat().replace("+00:00", "Z"), "lane": "Threads", "title": "Threads — %s" % name.split(" (")[0], "expect": expect, "evidence": ev})

    # Instagram — the one hour the numbers chose
    ig_h = _ig_hour(root)
    at = _lagos_at(today, ig_h, 10)
    items.append({"at": at.isoformat().replace("+00:00", "Z"), "lane": "Instagram", "title": "Instagram feed post + Story",
                  "expect": ["posts the day's card with the caption, then the same frame as a Story (the lane fires at 7:10am, 1:10pm and 7:10pm; only the %d:10 slot posts — chosen by the numbers)" % (ig_h if ig_h <= 12 else ig_h - 12)],
                  "evidence": [ledger_hit(insta, at, "Instagram post")]})

    # LinkedIn Mon/Wed/Fri 8:30am
    if weekday in (0, 2, 4):
        at = _lagos_at(today, 8, 30)
        items.append({"at": at.isoformat().replace("+00:00", "Z"), "lane": "LinkedIn", "title": "LinkedIn post", "expect": ["the week's business-facing post"], "evidence": []})

    # Telegram 9:00am, Facebook 9:30am
    at = _lagos_at(today, 9, 0)
    items.append({"at": at.isoformat().replace("+00:00", "Z"), "lane": "Telegram", "title": "Telegram channel post",
                  "expect": ["the day's post to @docogadaily with the tap-through buttons"], "evidence": [ledger_hit(tele, at, "Telegram post")]})
    at = _lagos_at(today, 9, 30)
    ev = []
    reel_hit = _between(reels, at - timedelta(minutes=20), at + grace)
    if reel_hit:
        ev.append(_ev("Reel published", True, reel_hit[0].get("url"), reel_hit[0].get("title") or reel_hit[0].get("topic")))
    reel_day = weekday in (0, 3)          # scripts/facebook_reel_daily.py REEL_WEEKDAYS
    if reel_day and not reel_hit:
        ev.append(_ev("Reel published", False, None, "nothing in the Reels ledger yet"))
    items.append({"at": at.isoformat().replace("+00:00", "Z"), "lane": "Facebook", "title": "Facebook Page post" + (" + Reel" if reel_day else ""),
                  "expect": ["the day's card and copy on the Page"] + (["today is a Reel day (Mon/Thu): a voiced Reel on the Page, mirrored to Instagram Reels"] if reel_day else []), "evidence": ev})

    # 6:00pm Short (weekdays)
    if weekday < 5:
        at = _lagos_at(today, 18, 0)
        got = _between(shorts, at - timedelta(minutes=10), at + grace)
        hosted = [m for m in media if m.get("date") == today.isoformat()]
        tk = [t for t in tiktok_rows if str(t.get("recorded_at", ""))[:10] == now.astimezone(LAGOS).date().isoformat() or str(t.get("video", "")).endswith(today.strftime("%Y%m%d") + ".mp4")]
        ev = []
        if got:
            r = got[0]
            ev.append(_ev("Short uploaded", True, r.get("url"), r.get("topic") or r.get("title")))
            ev.append(_ev("scheduled public at 7:00pm", bool(r.get("publish_at")), None, r.get("publish_at") and ("public at " + _lagos_text(r["publish_at"]))))
        else:
            ev.append(_ev("Short uploaded", False, None, "nothing in the Shorts ledger yet"))
        ev.append(_ev("sent to the TikTok inbox", bool(tk), None, (tk[0].get("status") if tk else "not yet")))
        ev.append(_ev("video handed to Threads for 8:10pm", bool(hosted), hosted[0].get("url") if hosted else None, hosted[0].get("title") if hosted else "not yet"))
        # 21 Oct 2026: the same Short also travels as a Facebook Reel and an Instagram Reel.
        # Informational (ok=None when absent): a topic already out as a Reel inside 30 days is
        # skipped by design, and that must not paint the Short red.
        fb_reel = _between(reels, at - timedelta(minutes=10), at + grace)
        ig_reel = [r for r in _between(insta, at - timedelta(minutes=10), at + grace) if str(r.get("title", "")).startswith("Reel ·")]
        ev.append(_ev("the same Short as a Facebook Reel", True if fb_reel else None, ("https://www.facebook.com" + fb_reel[0]["url"]) if fb_reel and str(fb_reel[0].get("url", "")).startswith("/") else (fb_reel[0].get("url") if fb_reel else None),
                      fb_reel[0].get("title") if fb_reel else "not recorded — not yet, or this topic was a Reel inside 30 days"))
        ev.append(_ev("the same Short as an Instagram Reel", True if ig_reel else None, ig_reel[0].get("url") if ig_reel else None,
                      ig_reel[0].get("topic") if ig_reel else "not recorded — not yet, or this topic was a Reel inside 30 days"))
        items.append({"at": at.isoformat().replace("+00:00", "Z"), "lane": "YouTube Short", "title": "Short renders and uploads",
                      "expect": ["renders today's Short (voice, synced captions, matched footage)", "uploads it private, scheduled to go public at 7:00pm",
                                 "sends it to your TikTok inbox and the Telegram channel", "hands the video to Threads for the 8:10pm slot",
                                 "publishes the same Short as a Facebook Reel and an Instagram Reel (Trial Reel: shown to non-followers first)"], "evidence": ev})
        at7 = _lagos_at(today, 19, 0)
        pub = [r for r in got if r.get("publish_at")]
        items.append({"at": at7.isoformat().replace("+00:00", "Z"), "lane": "YouTube", "title": "The Short goes public (YouTube flips it itself)",
                      "expect": ["no run at this minute — YouTube publishes the scheduled Short and notifies subscribers"],
                      "evidence": [_ev("scheduled by the 6:00pm upload", True, pub[0].get("url"), pub[0].get("topic")) if pub else _ev("scheduled by the 6:00pm upload", False if now >= at + timedelta(minutes=WATCH_GRACE_MIN) else None, None, "waiting for the upload")]})

    # 7:40pm Facebook Story; 9:00pm heartbeat
    at = _lagos_at(today, 19, 40)
    items.append({"at": at.isoformat().replace("+00:00", "Z"), "lane": "Facebook", "title": "Facebook Story", "expect": ["the day's frame as a 24-hour Story"], "evidence": []})
    at = _lagos_at(today, 21, 0)
    items.append({"at": at.isoformat().replace("+00:00", "Z"), "lane": "Heartbeat", "title": "Evening report to your phone",
                  "expect": ["the day's runs judged and texted to you on Telegram"], "evidence": []})

    # tonight: 1:30am Brain, 4:00am Deep-Dive (tomorrow's date)
    items.append(brain_item(tomorrow))
    at = _lagos_at(tomorrow, 4, 0)
    items.append({"at": at.isoformat().replace("+00:00", "Z"), "lane": "Deep-Dive",
                  "title": ("Deep-Dive lane produces %s" % queued) if queued else "Deep-Dive lane produces whatever the Brain wrote at 1:30am",
                  "expect": ["narrates, renders and uploads it, scheduled for the next free Saturday 7:00pm — or skips if the queue is still empty"], "evidence": []})

    # the next Saturday with a Deep-Dive going public
    try:
        sys.path.insert(0, str(root / "tools"))
        import publish_calendar
        taken = sorted(d for d in publish_calendar.taken_deepdive_days(root) if d >= today.isoformat())
    except Exception:  # pragma: no cover — the calendar is optional here
        taken = []
    for d in taken[:2]:
        when = _lagos_at(date.fromisoformat(d), 19, 0)
        title = ""
        for r in longform:
            if (r.get("publish_at") or "")[:10] and _stamp(r["publish_at"]) and _stamp(r["publish_at"]).astimezone(LAGOS).date().isoformat() == d:
                title = r.get("title") or ""
        if not title:
            for r in _rows(root, "logs/youtube_manage.json"):
                if str(r.get("result", "")).startswith("scheduled ") and _stamp(r["result"].split(" ", 1)[1]) and _stamp(r["result"].split(" ", 1)[1]).astimezone(LAGOS).date().isoformat() == d:
                    title = r.get("title") or r.get("video_id") or ""
        items.append({"at": when.isoformat().replace("+00:00", "Z"), "lane": "YouTube", "title": "Deep-Dive goes public" + (": " + _first_line(title, 80) if title else ""),
                      "expect": ["YouTube flips the scheduled episode public at 7:00pm; Threads, Telegram and Facebook trail it over the following days"], "evidence": []})

    items.sort(key=lambda i: i["at"])
    return [_settle(i, now) for i in items]


def _lagos_text(stamp):
    at = _stamp(stamp)
    if not at:
        return str(stamp)
    w = at.astimezone(LAGOS)
    hour = w.hour % 12 or 12
    return "%s %d %s, %d:%02d%s" % (w.strftime("%a"), w.day, w.strftime("%b"), hour, w.minute, "am" if w.hour < 12 else "pm")


def events(now, within=45, cap=3):
    """The special days coming up (tools/events_calendar.py) — the owner asked (23 Oct 2026) that
    Christmas, Independence Day, Children's Day, Democracy Day, Eid … be in the content; this is
    where he sees the machine already knows the dates and the angle it will take."""
    try:
        import events_calendar
    except ImportError:
        return []
    today = now.astimezone(LAGOS).date()
    rows = events_calendar.events_on(today)
    rows = [dict(r, in_days=0) for r in rows] + events_calendar.upcoming(today, within)
    return [{"name": r["name"], "date": r["date"], "in_days": r["in_days"], "approx": bool(r.get("approx")),
             "greeting": r.get("greeting") or "", "frame": r.get("frame") or "", "angle": r["angle"]} for r in rows[:cap]]


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
        "tiktok": tiktok(root),
        "watch": watch(now, root),
        "events": events(now),
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
