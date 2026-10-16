#!/usr/bin/env python3
"""brain_scorecard.py — the numbers the brain is held to, pulled every Monday.

The strategy (brain/strategy.md) names one goal — Oga Pass sales — and the
channel measures that lead it. This file pulls those measures from the channels
themselves, grades them against brain/goals.json, and turns the grades into
**orders** the editor must follow for the coming week. Everything is appended to
logs/scorecard.json (one snapshot a week, 60 kept) and summarised into
brain/feedback.md by `tools/brain.py feedback`, which the nightly plan reads.

Sources (each optional — a missing token is reported, never fatal):
    Facebook Page      FB_PAGE_ACCESS_TOKEN + FB_PAGE_ID (read_insights is on the token)
                       followers, 7-day views/engagements/follows, last 14 days of posts with
                       reactions, comments, shares, clicks, views, and the hour each went out
    Instagram          IG_TOKEN_FILE or IG_ACCESS_TOKEN (+ IG_API_PATH / IG_USER_ID)
                       followers, 7-day views/reach/engaged/interactions, per-post saves and
                       shares, and the online_followers curve (which hour the audience is awake)
    Threads            THREADS_TOKEN_FILE or THREADS_ACCESS_TOKEN
                       followers, 7-day views, likes, replies, reposts, quotes, per post
    Telegram           TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID — member count
    YouTube            logs/youtube_stats.json (pulled by youtube_stats.yml an hour earlier)
    Sales              DOCOGA_ADMIN_PASSPHRASE (+ DOCOGA_WORKER_URL) — the owner dashboard's
                       31-day series of passes sold and ₦ revenue. Optional: without it the
                       scorecard grades reach and says revenue is not connected.

Metric names follow the 2026 Graph API: impressions and page_fans are gone
(Nov 2025 / Jun 2026); views, media views and follows are what remains.

Usage
    python3 tools/brain_scorecard.py pull            # fetch, grade, append, print the summary
    python3 tools/brain_scorecard.py pull --dry-run  # fetch and print, write nothing
    python3 tools/brain_scorecard.py summary         # the latest snapshot as markdown
    python3 tools/brain_scorecard.py grade           # re-grade the latest snapshot
Exit 0 always (a missing number is a line in the summary, not a red lane),
except 2 when nothing at all could be measured.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path(os.environ.get("DOCOGA_SCORECARD") or (ROOT / "logs" / "scorecard.json"))
GOALS = ROOT / "brain" / "goals.json"
YT_STATS = ROOT / "logs" / "youtube_stats.json"
KEEP = 60
WAT = timezone(timedelta(hours=1))
GRAPH = "https://graph.facebook.com/" + os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH_IG = "https://graph.instagram.com/" + os.environ.get("META_GRAPH_VERSION", "v26.0")
THREADS = "https://graph.threads.net/v1.0"
WORKER = os.environ.get("DOCOGA_WORKER_URL", "https://docoga-pass.johnazani.workers.dev").rstrip("/")
POST_WINDOW_DAYS = 14
RANGE_DAYS = 7


# ───────────────────────────── http ─────────────────────────────
def _http(method, url, params=None, body=None, headers=None, timeout=30):
    """(status, parsed_json_or_text). Never raises for HTTP errors."""
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    data = None
    hdrs = {"User-Agent": "DocOga-scorecard/1.0 (+https://docoga.com.ng)"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        status = e.code
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, {"error": {"message": str(e)}}
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, {"error": {"message": raw[:200]}}


def _err(body):
    if isinstance(body, dict):
        e = body.get("error")
        if isinstance(e, dict):
            return "%s (code %s)" % (e.get("message", "?"), e.get("code", "?"))
        if e:
            return str(e)
    return "unexpected reply"


def _read_secret_file(env, path_env, value_env):
    """A token from a 0600 file (how the lanes pass it) or, failing that, the plain variable."""
    p = (env.get(path_env) or "").strip()
    if p:
        try:
            return Path(p).read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return (env.get(value_env) or "").strip()


def _hour_wat(iso):
    """Hour in Lagos for a Graph timestamp ('2026-10-16T08:31:02+0000' or '...Z')."""
    if not iso:
        return None
    s = str(iso).replace("Z", "+00:00")
    if len(s) >= 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    try:
        return datetime.fromisoformat(s).astimezone(WAT).hour
    except ValueError:
        return None


def _weekday(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")[:19]).strftime("%a")
    except ValueError:
        return ""


def _sum_series(payload, name):
    """Sum a Graph insights time series (or total_value) for `name`."""
    for row in (payload or {}).get("data") or []:
        if row.get("name") != name:
            continue
        if "total_value" in row:
            return int((row["total_value"] or {}).get("value") or 0)
        return sum(int((v or {}).get("value") or 0) for v in row.get("values") or [] if not isinstance((v or {}).get("value"), dict))
    return None


# ───────────────────────────── sources ─────────────────────────────
def pull_facebook(http, env, now, problems):
    token, page = env.get("FB_PAGE_ACCESS_TOKEN", "").strip(), env.get("FB_PAGE_ID", "").strip()
    if not (token and page):
        problems.append("facebook: FB_PAGE_ACCESS_TOKEN / FB_PAGE_ID not set — Page not measured")
        return None
    out = {"followers": None, "views_7d": None, "engagements_7d": None, "follows_7d": None,
           "video_views_7d": None, "posts": []}
    st, body = http("GET", "%s/%s" % (GRAPH, page), {"fields": "followers_count,fan_count,name", "access_token": token})
    if st == 200:
        out["followers"] = body.get("followers_count", body.get("fan_count"))
    else:
        problems.append("facebook: page read failed — " + _err(body))
    since, until = int((now - timedelta(days=RANGE_DAYS)).timestamp()), int(now.timestamp())
    wanted = {"page_total_media_view_unique": "views_7d", "page_post_engagements": "engagements_7d",
              "page_daily_follows_unique": "follows_7d", "page_video_views": "video_views_7d"}
    st, body = http("GET", "%s/%s/insights" % (GRAPH, page),
                    {"metric": ",".join(wanted), "period": "day", "since": since, "until": until, "access_token": token})
    if st != 200:  # one unknown metric fails the whole call: ask for them one by one
        for metric in wanted:
            st1, b1 = http("GET", "%s/%s/insights" % (GRAPH, page),
                           {"metric": metric, "period": "day", "since": since, "until": until, "access_token": token})
            if st1 == 200:
                out[wanted[metric]] = _sum_series(b1, metric)
            else:
                problems.append("facebook: %s unavailable — %s" % (metric, _err(b1)))
    else:
        for metric, key in wanted.items():
            out[key] = _sum_series(body, metric)
    st, body = http("GET", "%s/%s/posts" % (GRAPH, page),
                    {"fields": "id,created_time,message,shares,comments.summary(true).limit(0),reactions.summary(true).limit(0)",
                     "since": int((now - timedelta(days=POST_WINDOW_DAYS)).timestamp()), "limit": 30, "access_token": token})
    if st != 200:
        problems.append("facebook: posts read failed — " + _err(body))
        return out
    for p in (body.get("data") or [])[:30]:
        row = {"id": p.get("id"), "at": p.get("created_time"), "hour_wat": _hour_wat(p.get("created_time")),
               "weekday": _weekday(p.get("created_time")), "text": (p.get("message") or "")[:90],
               "reactions": int(((p.get("reactions") or {}).get("summary") or {}).get("total_count") or 0),
               "comments": int(((p.get("comments") or {}).get("summary") or {}).get("total_count") or 0),
               "shares": int((p.get("shares") or {}).get("count") or 0), "clicks": None, "views": None}
        st2, b2 = http("GET", "%s/%s/insights" % (GRAPH, p.get("id")),
                       {"metric": "post_clicks,post_media_view", "access_token": token})
        if st2 == 200:
            row["clicks"] = _sum_series(b2, "post_clicks")
            row["views"] = _sum_series(b2, "post_media_view")
        out["posts"].append(row)
    return out


def pull_instagram(http, env, now, problems):
    token = _read_secret_file(env, "IG_TOKEN_FILE", "IG_ACCESS_TOKEN")
    if not token:
        problems.append("instagram: no token (IG_TOKEN_FILE / IG_ACCESS_TOKEN) — account not measured")
        return None
    if env.get("IG_API_PATH", "instagram-login") == "facebook-login":
        base, node = GRAPH, env.get("IG_USER_ID", "").strip() or "me"
    else:
        base, node = GRAPH_IG, "me"
    out = {"followers": None, "views_7d": None, "reach_7d": None, "engaged_7d": None, "interactions_7d": None,
           "online_followers_wat": {}, "media": []}
    st, body = http("GET", "%s/%s" % (base, node), {"fields": "followers_count,media_count,username", "access_token": token})
    if st == 200:
        out["followers"] = body.get("followers_count")
        out["username"] = body.get("username")
    else:
        problems.append("instagram: account read failed — " + _err(body))
    since, until = int((now - timedelta(days=RANGE_DAYS)).timestamp()), int(now.timestamp())
    st, body = http("GET", "%s/%s/insights" % (base, node),
                    {"metric": "views,reach,accounts_engaged,total_interactions", "period": "day",
                     "metric_type": "total_value", "since": since, "until": until, "access_token": token})
    if st == 200:
        out["views_7d"] = _sum_series(body, "views")
        out["reach_7d"] = _sum_series(body, "reach")
        out["engaged_7d"] = _sum_series(body, "accounts_engaged")
        out["interactions_7d"] = _sum_series(body, "total_interactions")
    else:
        problems.append("instagram: account insights unavailable (needs instagram_business_manage_insights) — " + _err(body))
    st, body = http("GET", "%s/%s/insights" % (base, node),
                    {"metric": "online_followers", "period": "lifetime", "access_token": token})
    if st == 200:
        for row in body.get("data") or []:
            for v in row.get("values") or []:
                hours = v.get("value") or {}
                if isinstance(hours, dict):
                    for h, n in hours.items():
                        try:
                            out["online_followers_wat"][str((int(h) + 1) % 24)] = int(n)
                        except (TypeError, ValueError):
                            pass
    st, body = http("GET", "%s/%s/media" % (base, node),
                    {"fields": "id,caption,timestamp,media_type,like_count,comments_count,permalink",
                     "limit": 20, "access_token": token})
    if st != 200:
        problems.append("instagram: media read failed — " + _err(body))
        return out
    floor = (now - timedelta(days=POST_WINDOW_DAYS)).isoformat()
    for m in body.get("data") or []:
        if str(m.get("timestamp", ""))[:19] < floor[:19]:
            continue
        row = {"id": m.get("id"), "at": m.get("timestamp"), "hour_wat": _hour_wat(m.get("timestamp")),
               "weekday": _weekday(m.get("timestamp")), "type": m.get("media_type"),
               "text": (m.get("caption") or "")[:90], "likes": int(m.get("like_count") or 0),
               "comments": int(m.get("comments_count") or 0), "views": None, "reach": None, "saved": None, "shares": None}
        st2, b2 = http("GET", "%s/%s/insights" % (base, m.get("id")),
                       {"metric": "views,reach,saved,shares,total_interactions", "access_token": token})
        if st2 == 200:
            for k in ("views", "reach", "saved", "shares"):
                row[k] = _sum_series(b2, k)
        out["media"].append(row)
    return out


def pull_threads(http, env, now, problems):
    token = _read_secret_file(env, "THREADS_TOKEN_FILE", "THREADS_ACCESS_TOKEN")
    if not token:
        problems.append("threads: no token (THREADS_TOKEN_FILE / THREADS_ACCESS_TOKEN) — account not measured")
        return None
    out = {"followers": None, "views_7d": None, "likes_7d": None, "replies_7d": None, "reposts_7d": None,
           "quotes_7d": None, "posts": []}
    since, until = int((now - timedelta(days=RANGE_DAYS)).timestamp()), int(now.timestamp())
    st, body = http("GET", THREADS + "/me/threads_insights",
                    {"metric": "views,likes,replies,reposts,quotes,followers_count", "since": since, "until": until,
                     "access_token": token})
    if st == 200:
        out["views_7d"] = _sum_series(body, "views")
        out["likes_7d"] = _sum_series(body, "likes")
        out["replies_7d"] = _sum_series(body, "replies")
        out["reposts_7d"] = _sum_series(body, "reposts")
        out["quotes_7d"] = _sum_series(body, "quotes")
        out["followers"] = _sum_series(body, "followers_count")
    else:
        problems.append("threads: account insights unavailable (needs threads_manage_insights) — " + _err(body))
    st, body = http("GET", THREADS + "/me/threads", {"fields": "id,text,timestamp,permalink", "limit": 20, "access_token": token})
    if st != 200:
        problems.append("threads: posts read failed — " + _err(body))
        return out
    floor = (now - timedelta(days=POST_WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
    for p in body.get("data") or []:
        if str(p.get("timestamp", ""))[:19] < floor:
            continue
        row = {"id": p.get("id"), "at": p.get("timestamp"), "hour_wat": _hour_wat(p.get("timestamp")),
               "weekday": _weekday(p.get("timestamp")), "text": (p.get("text") or "")[:90],
               "views": None, "likes": None, "replies": None, "reposts": None, "quotes": None, "shares": None}
        st2, b2 = http("GET", "%s/%s/insights" % (THREADS, p.get("id")),
                       {"metric": "views,likes,replies,reposts,quotes,shares", "access_token": token})
        if st2 == 200:
            for k in ("views", "likes", "replies", "reposts", "quotes", "shares"):
                row[k] = _sum_series(b2, k)
        out["posts"].append(row)
    return out


def pull_telegram(http, env, now, problems):
    token, chat = env.get("TELEGRAM_BOT_TOKEN", "").strip(), env.get("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat):
        problems.append("telegram: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — channel not measured")
        return None
    st, body = http("GET", "https://api.telegram.org/bot%s/getChatMemberCount" % token, {"chat_id": chat})
    if st == 200 and body.get("ok"):
        return {"members": int(body.get("result") or 0), "chat": chat}
    problems.append("telegram: getChatMemberCount failed — %s" % (body.get("description") or _err(body)))
    return None


def pull_youtube(stats_path=YT_STATS):
    try:
        stats = json.loads(Path(stats_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    snap = stats[-1] if isinstance(stats, list) and stats else (stats if isinstance(stats, dict) else None)
    if not snap:
        return None
    ch = snap.get("channel") or {}
    vids = snap.get("videos") or []
    shorts = sorted([v for v in vids if v.get("kind") == "short"], key=lambda v: -int(v.get("views") or 0))
    return {"subscribers": ch.get("subscribers"), "views": ch.get("views"), "videos": ch.get("videos"),
            "taken_at": snap.get("taken_at"),
            "top_shorts": [{"title": v.get("topic") or v.get("title"), "views": int(v.get("views") or 0)} for v in shorts[:5]]}


def pull_sales(http, env, now, problems):
    passphrase = env.get("DOCOGA_ADMIN_PASSPHRASE", "").strip()
    if not passphrase:
        problems.append("sales: DOCOGA_ADMIN_PASSPHRASE not set — revenue not connected (optional; the dashboard passphrase as a repo secret)")
        return None
    worker = env.get("DOCOGA_WORKER_URL", WORKER).rstrip("/")
    st, body = http("POST", worker + "/admin/login", body={"pass": passphrase})
    if st != 200 or not body.get("ok"):
        problems.append("sales: dashboard login refused (%s) — %s" % (st, body.get("error") or _err(body)))
        return None
    token = body.get("token", "")
    st, data = http("GET", worker + "/admin/data", headers={"Authorization": "Bearer " + token})
    http("POST", worker + "/admin/logout", headers={"Authorization": "Bearer " + token})
    if st != 200 or not data.get("ok"):
        problems.append("sales: dashboard read failed (%s)" % st)
        return None
    series = ((data.get("snapshot") or {}).get("series") or [])
    today = data.get("today") or {}
    by_day = {}
    for row in series:
        d = row.get("date")
        if d:
            by_day[d] = {"sold": int(row.get("sold") or 0) + int(row.get("offline") or 0) + int(row.get("manual") or 0),
                         "rev": int(row.get("rev") or 0) + int(row.get("bizrev") or 0), "biz": int(row.get("bizpaid") or 0)}
    tday = data.get("date")
    if tday:
        by_day[tday] = {"sold": int(today.get("sold") or 0) + int(today.get("offline") or 0) + int(today.get("manual") or 0),
                        "rev": int(today.get("rev") or 0) + int(today.get("bizrev") or 0), "biz": int(today.get("bizpaid") or 0)}
    days = sorted(by_day)

    def window(n):
        keep = days[-n:]
        return sum(by_day[d]["sold"] for d in keep), sum(by_day[d]["rev"] for d in keep), sum(by_day[d]["biz"] for d in keep)
    s7, r7, b7 = window(7)
    s28, r28, b28 = window(28)
    return {"passes_7d": s7, "revenue_7d": r7, "business_7d": b7, "passes_28d": s28, "revenue_28d": r28,
            "business_28d": b28, "price": data.get("priceNGN"), "by_day": {d: by_day[d] for d in days[-28:]}}


# ───────────────────────────── kpis ─────────────────────────────
def _rate(num, den):
    try:
        return round(float(num) / float(den), 4) if den else None
    except (TypeError, ValueError):
        return None


def _best(rows, score, n=3, label="text"):
    scored = sorted(rows, key=lambda r: -(score(r) or 0))
    return [{"text": r.get(label, ""), "score": score(r) or 0, "hour_wat": r.get("hour_wat"), "weekday": r.get("weekday")}
            for r in scored[:n] if (score(r) or 0) > 0]


def _by_hour(rows, score):
    buckets = {}
    for r in rows:
        h = r.get("hour_wat")
        if h is None:
            continue
        buckets.setdefault(h, []).append(score(r) or 0)
    return {str(h): round(sum(v) / len(v), 2) for h, v in sorted(buckets.items()) if v}


def kpis(channels):
    k = {}
    fb = channels.get("facebook") or {}
    if fb:
        posts = fb.get("posts") or []
        views = sum(p["views"] for p in posts if p.get("views"))
        shares = sum(p.get("shares") or 0 for p in posts)
        k["facebook.followers"] = fb.get("followers")
        k["facebook.views_7d"] = fb.get("views_7d")
        k["facebook.engagements_7d"] = fb.get("engagements_7d")
        k["facebook.follows_7d"] = fb.get("follows_7d")
        k["facebook.posts_14d"] = len(posts)
        k["facebook.share_rate"] = _rate(shares, views) if views else None
        k["facebook.shares_per_post"] = _rate(shares, len(posts))
        k["facebook.comments_per_post"] = _rate(sum(p.get("comments") or 0 for p in posts), len(posts))
        k["facebook.clicks_per_post"] = _rate(sum(p.get("clicks") or 0 for p in posts if p.get("clicks")), len(posts))
        score = lambda p: (p.get("shares") or 0) * 3 + (p.get("comments") or 0) * 2 + (p.get("reactions") or 0)
        k["facebook.best_posts"] = _best(posts, score)
        k["facebook.by_hour"] = _by_hour(posts, score)
    ig = channels.get("instagram") or {}
    if ig:
        media = ig.get("media") or []
        reach = sum(m["reach"] for m in media if m.get("reach"))
        sends = sum((m.get("shares") or 0) + (m.get("saved") or 0) for m in media)
        k["instagram.followers"] = ig.get("followers")
        k["instagram.views_7d"] = ig.get("views_7d")
        k["instagram.reach_7d"] = ig.get("reach_7d")
        k["instagram.interactions_7d"] = ig.get("interactions_7d")
        k["instagram.posts_14d"] = len(media)
        k["instagram.send_rate"] = _rate(sends, reach) if reach else None
        k["instagram.sends_per_post"] = _rate(sends, len(media))
        score = lambda m: (m.get("shares") or 0) * 3 + (m.get("saved") or 0) * 2 + (m.get("comments") or 0) * 2 + (m.get("likes") or 0)
        k["instagram.best_posts"] = _best(media, score)
        k["instagram.by_hour"] = _by_hour(media, score)
        online = ig.get("online_followers_wat") or {}
        if online:
            top = sorted(online.items(), key=lambda kv: -kv[1])[:3]
            k["instagram.online_peak_hours_wat"] = [int(h) for h, _ in top]
    th = channels.get("threads") or {}
    if th:
        posts = th.get("posts") or []
        k["threads.followers"] = th.get("followers")
        k["threads.views_7d"] = th.get("views_7d")
        k["threads.posts_14d"] = len(posts)
        replies = sum(p.get("replies") or 0 for p in posts)
        k["threads.replies_per_post"] = _rate(replies, len(posts))
        k["threads.reposts_per_post"] = _rate(sum((p.get("reposts") or 0) + (p.get("quotes") or 0) for p in posts), len(posts))
        score = lambda p: (p.get("replies") or 0) * 3 + (p.get("reposts") or 0) * 3 + (p.get("quotes") or 0) * 3 + (p.get("likes") or 0)
        k["threads.best_posts"] = _best(posts, score)
        k["threads.by_hour"] = _by_hour(posts, score)
    tg = channels.get("telegram") or {}
    if tg:
        k["telegram.members"] = tg.get("members")
    yt = channels.get("youtube") or {}
    if yt:
        k["youtube.subscribers"] = yt.get("subscribers")
        k["youtube.views"] = yt.get("views")
        k["youtube.top_shorts"] = yt.get("top_shorts")
    sales = channels.get("sales") or {}
    if sales:
        k["sales.passes"] = sales.get("passes_7d")
        k["sales.revenue"] = sales.get("revenue_7d")
        k["sales.passes_28d"] = sales.get("passes_28d")
        k["sales.revenue_28d"] = sales.get("revenue_28d")
    return k


# ───────────────────────────── goals ─────────────────────────────
def load_goals(path=GOALS):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"weekly": {}, "ratios": {}}


def grade(current, previous, goals):
    """Each goal → on_track / behind / no_baseline / not_measured, with the numbers."""
    rows = []
    prev = (previous or {}).get("kpis") or {}
    for key, spec in (goals.get("weekly") or {}).items():
        actual = current.get(key)
        base = prev.get(key)
        row = {"key": key, "label": spec.get("label", key), "actual": actual, "baseline": base, "target": None}
        if actual is None:
            row["status"] = "not_measured"
        elif base is None:
            row["status"] = "no_baseline"
        else:
            if spec.get("kind") == "growth":
                target = base * (1 + float(spec.get("rate", 0)))
            else:
                target = max(float(spec.get("floor", 0)), base + float(spec.get("step", 0)))
            row["target"] = round(target, 1)
            row["status"] = "on_track" if float(actual) >= target - 1e-9 else "behind"
        rows.append(row)
    for key, spec in (goals.get("ratios") or {}).items():
        actual = current.get(key)
        row = {"key": key, "label": spec.get("label", key), "actual": actual, "target": spec.get("min"), "baseline": None}
        if actual is None:
            row["status"] = "not_measured"
        else:
            row["status"] = "on_track" if float(actual) >= float(spec.get("min", 0)) else "behind"
        rows.append(row)
    return rows


def streaks(history, grades):
    """How many consecutive weeks (including now) each goal has been behind."""
    out = {}
    past = [h.get("grades") or [] for h in history[-3:]]
    for g in grades:
        n = 1 if g["status"] == "behind" else 0
        if n:
            for rows in reversed(past):
                hit = next((r for r in rows if r.get("key") == g["key"]), None)
                if hit and hit.get("status") == "behind":
                    n += 1
                else:
                    break
        out[g["key"]] = n
    return out


def orders(k, grades, streak=None):
    """The week's instructions, from the numbers. Deterministic; strategy.md names each rule."""
    streak = streak or {}
    status = {g["key"]: g["status"] for g in grades}
    out = []

    def behind(key):
        return status.get(key) == "behind"

    if behind("facebook.share_rate") or behind("instagram.send_rate"):
        out.append("Sends are below 1.5% of reach: lead with STAKES and STAT hooks, put one named-person send line in "
                   "every post ('send this to the friend renewing in January'), and use the checklist layout twice this week.")
    if behind("threads.replies_per_post"):
        out.append("Threads replies are under 3 per post: every Threads post ends with a question answerable in five "
                   "words ('which state are you renting in?'); one opinion post this week.")
    if behind("facebook.comments_per_post"):
        out.append("Facebook comments are under 2 per post: ask for the reader's state or a yes/no in the last line; "
                   "a Thursday scenario people will argue with.")
    if behind("telegram.view_ratio"):
        out.append("Telegram views are under 40% of members: shorter posts, a forward line on every post, one "
                   "question-style post this week.")
    if behind("youtube.subscribers"):
        out.append("YouTube subscribers are behind: change the Short hook archetype for two weeks and put a number in "
                   "the first line; the title must name the loss.")
    for key in ("telegram.members", "facebook.followers", "instagram.followers", "threads.followers"):
        if behind(key) and streak.get(key, 0) >= 2:
            out.append("%s has been behind two weeks running: the state-spotlight and checklist days this week carry "
                       "the most-forwarded genre — what a landlord may and may not demand." % key.split(".")[0].title())
    if behind("sales.passes"):
        reach_up = any(status.get(key) == "on_track" for key in ("facebook.followers", "instagram.followers", "telegram.members"))
        if reach_up:
            out.append("Sales are behind while reach grows: the promo moves into the payday window (25th to month-end); "
                       "every post names the exact document and 'two minutes, free to start' in the last line; one "
                       "testimonial-style scenario this week.")
        else:
            out.append("Sales are behind: the cited know-your-rights posts carry the send line and the document name; no "
                       "discounts, no new prices — reach first, then the paper.")
    if k.get("instagram.online_peak_hours_wat"):
        hrs = k["instagram.online_peak_hours_wat"]
        out.append("Instagram followers are online most at %s WAT — the evening lanes should sit inside that window."
                   % ", ".join("%02d:00" % h for h in hrs))
    for ch in ("facebook", "instagram", "threads"):
        best = k.get(ch + ".best_posts") or []
        if best:
            out.append("%s best this fortnight: %s — write the next %s post in that register, on a different theme."
                       % (ch.title(), "; ".join("'%s' (%s)" % (b["text"][:60], b["score"]) for b in best[:2]), ch))
    if not out:
        out.append("Every measured goal is on track: do not change the mix; rotate states and hooks only.")
    return out


# ───────────────────────────── ledger + summary ─────────────────────────────
def load_history(path=None):
    path = path or LEDGER
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_history(history, path=None):
    path = Path(path or LEDGER)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(history[-KEEP:], indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def previous_week(history, now):
    """The last snapshot at least 5 days older than now (so a re-run today does not grade against itself)."""
    floor = (now - timedelta(days=5)).isoformat()
    older = [h for h in history if str(h.get("taken_at", "")) <= floor]
    return older[-1] if older else None


def build(http=None, env=None, now=None, history=None, goals=None, stats_path=YT_STATS):
    http = http or _http
    env = dict(os.environ) if env is None else env
    now = now or datetime.now(timezone.utc)
    history = load_history() if history is None else history
    goals = goals or load_goals()
    problems = []
    channels = {
        "facebook": pull_facebook(http, env, now, problems),
        "instagram": pull_instagram(http, env, now, problems),
        "threads": pull_threads(http, env, now, problems),
        "telegram": pull_telegram(http, env, now, problems),
        "youtube": pull_youtube(stats_path),
        "sales": pull_sales(http, env, now, problems),
    }
    k = kpis(channels)
    prev = previous_week(history, now)
    grades = grade(k, prev, goals)
    strk = streaks(history, grades)
    snap = {"taken_at": now.isoformat(timespec="seconds"), "week": now.strftime("%G-W%V"),
            "channels": channels, "kpis": k, "grades": grades, "streaks": strk,
            "orders": orders(k, grades, strk), "problems": problems}
    return snap


def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return ("%.1f%%" % (v * 100)) if v < 1 else ("%.1f" % v)
    return "{:,}".format(v) if isinstance(v, int) else str(v)


def summary_md(snap):
    k = snap.get("kpis") or {}
    lines = ["## Scorecard %s (taken %s)" % (snap.get("week"), str(snap.get("taken_at", ""))[:16].replace("T", " ")), ""]
    sales = (snap.get("channels") or {}).get("sales")
    if sales:
        lines.append("**Money:** %s passes / ₦%s this week · %s passes / ₦%s in 28 days"
                     % (_fmt(sales.get("passes_7d")), _fmt(sales.get("revenue_7d")), _fmt(sales.get("passes_28d")), _fmt(sales.get("revenue_28d"))))
    else:
        lines.append("**Money:** not connected — add the dashboard passphrase as `DOCOGA_ADMIN_PASSPHRASE` and sales are graded weekly.")
    lines += ["", "| Channel | Followers | 7-day views | Signal |", "|---|---|---|---|"]
    lines.append("| Facebook | %s | %s | shares/post %s · comments/post %s · clicks/post %s |"
                 % (_fmt(k.get("facebook.followers")), _fmt(k.get("facebook.views_7d")), _fmt(k.get("facebook.shares_per_post")),
                    _fmt(k.get("facebook.comments_per_post")), _fmt(k.get("facebook.clicks_per_post"))))
    lines.append("| Instagram | %s | %s | sends+saves per reach %s · per post %s |"
                 % (_fmt(k.get("instagram.followers")), _fmt(k.get("instagram.views_7d")), _fmt(k.get("instagram.send_rate")), _fmt(k.get("instagram.sends_per_post"))))
    lines.append("| Threads | %s | %s | replies/post %s · reposts/post %s |"
                 % (_fmt(k.get("threads.followers")), _fmt(k.get("threads.views_7d")), _fmt(k.get("threads.replies_per_post")), _fmt(k.get("threads.reposts_per_post"))))
    lines.append("| Telegram | %s | — | members only (Bot API has no views) |" % _fmt(k.get("telegram.members")))
    lines.append("| YouTube | %s | %s total | top Short: %s |"
                 % (_fmt(k.get("youtube.subscribers")), _fmt(k.get("youtube.views")),
                    (k.get("youtube.top_shorts") or [{}])[0].get("title", "—") if k.get("youtube.top_shorts") else "—"))
    lines += ["", "### Goals", "| Goal | Actual | Target | Status |", "|---|---|---|---|"]
    for g in snap.get("grades") or []:
        mark = {"on_track": "✅", "behind": "🔻", "no_baseline": "⏳ first measurement", "not_measured": "— not measured"}[g["status"]]
        lines.append("| %s | %s | %s | %s |" % (g["label"], _fmt(g.get("actual")), _fmt(g.get("target")), mark))
    if k.get("instagram.online_peak_hours_wat"):
        lines += ["", "Instagram followers online most at: " + ", ".join("%02d:00 WAT" % h for h in k["instagram.online_peak_hours_wat"])]
    for ch in ("facebook", "instagram", "threads"):
        by_hour = k.get(ch + ".by_hour") or {}
        if by_hour:
            top = sorted(by_hour.items(), key=lambda kv: -kv[1])[:3]
            lines.append("%s engagement by posting hour (WAT): %s" % (ch.title(), ", ".join("%s:00 → %s" % kv for kv in top)))
    lines += ["", "### Orders for the coming week"] + ["- " + o for o in snap.get("orders") or []]
    if snap.get("problems"):
        lines += ["", "### Not measured (and why)"] + ["- " + p for p in snap["problems"]]
    return "\n".join(lines) + "\n"


def feedback_section(history=None):
    """The scorecard as the block brain.py feedback pastes into brain/feedback.md."""
    history = load_history() if history is None else history
    if not history:
        return "## Scorecard\nNo scorecard yet — the first one is written on Monday by brain_scorecard.yml.\n"
    return summary_md(history[-1])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=("pull", "summary", "grade"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary-file", default=os.environ.get("GITHUB_STEP_SUMMARY"))
    a = ap.parse_args(argv)
    history = load_history()
    if a.command == "summary":
        print(feedback_section(history), end="")
        return 0
    if a.command == "grade":
        if not history:
            print("no scorecard yet")
            return 2
        snap = history[-1]
        snap["grades"] = grade(snap.get("kpis") or {}, previous_week(history[:-1], datetime.fromisoformat(snap["taken_at"])), load_goals())
        snap["orders"] = orders(snap.get("kpis") or {}, snap["grades"], streaks(history[:-1], snap["grades"]))
        print(summary_md(snap), end="")
        return 0
    snap = build(history=history)
    text = summary_md(snap)
    print(text, end="")
    if a.summary_file:
        try:
            with open(a.summary_file, "a", encoding="utf-8") as fh:
                fh.write(text)
        except OSError:
            pass
    measured = any((snap["channels"].get(c) or {}) for c in ("facebook", "instagram", "threads", "telegram", "youtube", "sales"))
    if not a.dry_run:
        history.append(snap)
        save_history(history)
        print("scorecard: appended to %s (%d kept)" % (LEDGER, min(len(history), KEEP)))
    return 0 if measured else 2


if __name__ == "__main__":
    sys.exit(main())
