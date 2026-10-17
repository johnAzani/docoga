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
SAID = Path(os.environ.get("DOCOGA_BRAIN_SAID") or (ROOT / "logs" / "brain_said.json"))


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


def pull_search(problems, env=None, path=None):
    """Google Search Console, as written weekly by tools/search_console.py (same Google consent
    as the YouTube lane, scope webmasters.readonly). Stale beyond 14 days = not measured."""
    env = dict(os.environ) if env is None else env
    path = Path(path or env.get("DOCOGA_SEARCH_CONSOLE") or (ROOT / "logs" / "search_console.json"))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        problems.append("google: no Search Console pull yet — re-consent the YouTube token with webmasters.readonly (docs/BRAIN.md) and youtube_stats.yml writes logs/search_console.json")
        return None
    taken = str(data.get("taken_at") or "")
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(taken)).days
    except ValueError:
        age = 99
    if env.get("DOCOGA_SEARCH_CONSOLE"):
        age = 0  # a fixture is as fresh as the test says
    if age > 14:
        problems.append("google: the Search Console pull is %d days old" % age)
        return None
    return data


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
    out = {"passes_7d": s7, "revenue_7d": r7, "business_7d": b7, "passes_28d": s28, "revenue_28d": r28,
           "business_28d": b28, "price": data.get("priceNGN"), "by_day": {d: by_day[d] for d in days[-28:]}}
    out.update(sources_from(((data.get("snapshot") or {}).get("sources") or {}), now))
    return out


def sources_from(sources, now):
    """The worker's weekly `src:*` counters → checkout taps and verified sales by channel,
    for the week that just ended (+ today's) and for the whole window the worker keeps."""
    if not sources:
        return {}
    this_week = now.strftime("%G-W%V")
    last_week = (now - timedelta(days=7)).strftime("%G-W%V")
    out = {}
    for kind in ("checkout", "sale"):
        weeks = sources.get(kind) or {}
        recent, total = {}, {}
        for week, row in weeks.items():
            for ch, n in (row or {}).items():
                total[ch] = total.get(ch, 0) + int(n or 0)
                if week in (this_week, last_week):
                    recent[ch] = recent.get(ch, 0) + int(n or 0)
        out[kind + "s_by_source_7d"] = dict(sorted(recent.items(), key=lambda kv: -kv[1]))
        out[kind + "s_by_source_28d"] = dict(sorted(total.items(), key=lambda kv: -kv[1]))
    return out


def pull_site(env, now, problems):
    try:
        import site_analytics
    except ImportError:
        return None
    data, problem = site_analytics.pull(env=env, days=RANGE_DAYS, now=now)
    if problem:
        problems.append(problem)
        return None
    return data


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


def _by_hour_n(rows):
    counts = {}
    for r in rows:
        h = r.get("hour_wat")
        if h is not None:
            counts[str(h)] = counts.get(str(h), 0) + 1
    return counts


def _date_wat(iso):
    s = str(iso or "").replace("Z", "+00:00")
    if len(s) >= 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    try:
        return datetime.fromisoformat(s).astimezone(WAT).date().isoformat()
    except ValueError:
        return None


def load_said(path=None):
    try:
        data = json.loads(Path(path or SAID).read_text(encoding="utf-8"))
        return {str(e.get("date")): e for e in data if isinstance(e, dict) and e.get("date")}
    except (OSError, ValueError):
        return {}


def learning(channels, said=None):
    """What the brain's own choices earned: average engagement by hook, post type and reader.

    Each post is joined to the pack the brain wrote for that Lagos date (logs/brain_said.json).
    Days the rotation posted (no pack) are counted under 'rotation', so the brain is also measured
    against the hand-written baseline it replaced. Scores are the same per-channel scores the
    best-post lists use, so a hook that earns sends on Facebook shows as such."""
    said = load_said() if said is None else said
    scorers = {
        "facebook": ("posts", lambda p: (p.get("shares") or 0) * 3 + (p.get("comments") or 0) * 2 + (p.get("reactions") or 0)),
        "instagram": ("media", lambda m: (m.get("shares") or 0) * 3 + (m.get("saved") or 0) * 2 + (m.get("comments") or 0) * 2 + (m.get("likes") or 0)),
        "threads": ("posts", lambda p: (p.get("replies") or 0) * 3 + (p.get("reposts") or 0) * 3 + (p.get("quotes") or 0) * 3 + (p.get("likes") or 0)),
    }
    out = {"hook_type": {}, "post_type": {}, "reader": {}, "source": {}}
    for ch, (key, score) in scorers.items():
        for row in ((channels.get(ch) or {}).get(key) or []):
            day = _date_wat(row.get("at"))
            pack = said.get(day) if day else None
            labels = {"hook_type": (pack or {}).get("hook_type") or "rotation",
                      "post_type": (pack or {}).get("post_type") or "rotation",
                      "reader": (pack or {}).get("reader") or ("rotation" if not pack else "unnamed"),
                      "source": "brain" if pack else "rotation"}
            for dim, label in labels.items():
                bucket = out[dim].setdefault(label, {"n": 0, "total": 0.0})
                bucket["n"] += 1
                bucket["total"] += float(score(row) or 0)
    for dim in out:
        for label, b in out[dim].items():
            b["avg"] = round(b["total"] / b["n"], 1) if b["n"] else 0.0
    return out


def kpis(channels, said=None):
    k = {}
    k["learning"] = learning(channels, said)
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
        k["instagram.by_hour_n"] = _by_hour_n(media)
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
        if sales.get("sales_by_source_28d") is not None:
            k["sales.by_source_28d"] = sales.get("sales_by_source_28d")
            k["sales.checkouts_by_source_28d"] = sales.get("checkouts_by_source_28d")
            k["sales.by_source_7d"] = sales.get("sales_by_source_7d")
    site = channels.get("site") or {}
    if site:
        k["site.visits_7d"] = site.get("visits")
        k["site.by_channel"] = site.get("by_channel")
        k["site.top_pages"] = site.get("by_path")
        k["site.nigeria_share"] = site.get("nigeria_share")
    search = channels.get("search") or {}
    if search:
        k["google.clicks_28d"] = search.get("clicks")
        k["google.impressions_28d"] = search.get("impressions")
        k["google.ctr"] = search.get("ctr")
        k["google.top_queries"] = search.get("top_queries")
        k["google.striking_distance"] = search.get("striking_distance")
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


def milestones(k, goals, history, now):
    """How far each platform threshold is, at the pace of the last four weeks (17 Oct 2026).
    The thresholds are where an audience becomes a second income (Facebook Stars at 500
    followers for 30 days; YouTube fan funding at 500 subs; Instagram/Telegram at 1,000). A
    milestone whose ETA is more than two weeks past its due date is flagged `behind_pace`."""
    out = []
    four_weeks_ago = (now - timedelta(days=26)).isoformat()
    older = [h for h in history if str(h.get("taken_at", "")) <= four_weeks_ago]
    base = older[-1] if older else (history[0] if history else None)
    for key, m in (goals.get("milestones") or {}).items():
        current = k.get(key)
        if current is None:
            continue
        target = int(m.get("target") or 0)
        remaining = max(target - int(current), 0)
        pace = None
        if base and (base.get("kpis") or {}).get(key) is not None:
            then = base["kpis"][key]
            weeks = max((now - datetime.fromisoformat(str(base["taken_at"]))).days / 7.0, 1.0)
            pace = (int(current) - int(then)) / weeks
        weeks_to_go = None if not pace or pace <= 0 else remaining / pace
        due = m.get("due")
        status = "reached" if remaining == 0 else "no-pace-yet"
        needed = None
        if due:
            weeks_left = max((datetime.fromisoformat(due).replace(tzinfo=timezone.utc) - now).days / 7.0, 0.0)
            needed = (remaining / weeks_left) if weeks_left > 0 else None
            if remaining and weeks_to_go is not None:
                status = "on_pace" if weeks_to_go <= weeks_left + 2 else "behind_pace"
            elif remaining and pace is not None and pace <= 0:
                status = "behind_pace"
        out.append({"key": key, "label": m.get("label"), "unlocks": m.get("unlocks"), "target": target, "current": int(current),
                    "remaining": remaining, "pace_per_week": round(pace, 1) if pace is not None else None,
                    "weeks_to_go": round(weeks_to_go, 1) if weeks_to_go is not None else None,
                    "needed_per_week": round(needed, 1) if needed is not None else None, "due": due, "status": status})
    return out


def slot_advice(k):
    """Where the audience is awake versus when we post (Instagram's online_followers curve, WAT)."""
    peaks = k.get("instagram.online_peak_hours_wat") or []
    if not peaks:
        return None
    ours = 19     # instagram_autopost.yml: 18:10 UTC = 19:10 WAT
    best = peaks[0]
    gap = min(abs(best - ours), 24 - abs(best - ours))
    return {"peak_hours_wat": peaks, "our_hour_wat": ours, "move": gap >= 2, "suggest_hour_wat": best if gap >= 2 else ours}


# ───────────────────────────── posting slots ─────────────────────────────
SLOTS = Path(os.environ.get("DOCOGA_SLOTS") or (ROOT / "brain" / "slots.json"))
# The hours (WAT) a lane's workflow actually fires at. Each is a cron in the lane's file; the
# slot gate lets exactly one of them post. Nigeria's windows: 06:00–08:00, 12:30–14:00, 19:00–20:30.
SLOT_CANDIDATES = {"instagram": (7, 13, 19)}
SLOT_DEFAULT = {"instagram": 19}


def slot_plan(k, previous=None, now=None):
    """Which of a lane's candidate hours posts this week — decided by the numbers (17 Oct 2026).

    Two witnesses, in order: what our own posts earned by posting hour (`instagram.by_hour`, the
    scorecard's engagement score averaged per hour) when at least two candidate windows have
    three measured posts each; else Instagram's `online_followers` curve (the top hour the
    audience is awake), moved to the nearest candidate when the current slot is two or more
    hours off the peak. Otherwise the slot stays where it is: a slot that moves on thin evidence
    is a slot that never accumulates evidence. Returns the plan `{lane: {hour_wat, why, …}}`.
    """
    now = now or datetime.now(timezone.utc)
    previous = previous or {}
    plan = {"written": now.isoformat(timespec="seconds"), "lanes": {}}
    for lane, candidates in SLOT_CANDIDATES.items():
        current = int(((previous.get("lanes") or {}).get(lane) or {}).get("hour_wat") or SLOT_DEFAULT[lane])
        chosen, why = current, "no new evidence — the slot stays at %02d:10 WAT" % current
        by_hour = {int(h): float(v) for h, v in (k.get("%s.by_hour" % lane) or {}).items()}
        counts = {int(h): int(v) for h, v in (k.get("%s.by_hour_n" % lane) or {}).items()}
        windows = {}
        for c in candidates:
            hours = [h for h in by_hour if min(abs(h - c), 24 - abs(h - c)) <= 1]
            n = sum(counts.get(h, 0) for h in hours)
            if n >= 3:
                windows[c] = (sum(by_hour[h] * counts.get(h, 1) for h in hours) / max(1, sum(counts.get(h, 1) for h in hours)), n)
        if len(windows) >= 2:
            best = max(windows.items(), key=lambda kv: kv[1][0])
            if best[0] != current and best[1][0] >= 1.25 * windows.get(current, (0.0, 0))[0]:
                chosen = best[0]
                why = "our posts at %02d:xx earned %.0f per post (n=%d) against %.0f at %02d:xx — measured, not guessed" % (
                    best[0], best[1][0], best[1][1], windows.get(current, (0.0, 0))[0], current)
            else:
                why = "our own numbers keep %02d:10 WAT (%s)" % (current, ", ".join("%02d:xx %.0f/n=%d" % (c, v[0], v[1]) for c, v in sorted(windows.items())))
        else:
            peaks = k.get("%s.online_peak_hours_wat" % lane) or []
            if peaks:
                peak = int(peaks[0])
                gap = min(abs(peak - current), 24 - abs(peak - current))
                nearest = min(candidates, key=lambda c: min(abs(peak - c), 24 - abs(peak - c)))
                if gap >= 2 and nearest != current and min(abs(peak - nearest), 24 - abs(peak - nearest)) <= 1:
                    chosen = nearest
                    why = "the audience is online most at %02d:00 WAT; %02d:10 is the nearest window we fire in" % (peak, nearest)
                else:
                    why = "the audience peaks at %02d:00 WAT; %02d:10 already sits in that window" % (peak, current)
        plan["lanes"][lane] = {"hour_wat": chosen, "candidates": list(candidates), "why": why,
                               "changed": chosen != current}
    return plan


def load_slots(path=None):
    try:
        data = json.loads(Path(path or SLOTS).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_slots(plan, path=None):
    path = Path(path or SLOTS)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def slot_hour(lane, plan=None):
    """The hour (WAT) `lane` posts at this week — the plan's, else the lane's default."""
    plan = load_slots() if plan is None else plan
    try:
        return int(((plan.get("lanes") or {}).get(lane) or {}).get("hour_wat") or SLOT_DEFAULT.get(lane, 19))
    except (TypeError, ValueError):
        return SLOT_DEFAULT.get(lane, 19)


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
    learn = k.get("learning") or {}
    hooks = {h: b for h, b in (learn.get("hook_type") or {}).items() if h != "rotation" and b.get("n", 0) >= 2}
    if len(hooks) >= 2:
        ranked = sorted(hooks.items(), key=lambda kv: -kv[1]["avg"])
        best, worst = ranked[0], ranked[-1]
        if best[1]["avg"] > 0 and best[1]["avg"] >= 1.5 * max(worst[1]["avg"], 0.1):
            out.append("Hooks, by what they earned this fortnight: %s — use %s on two of the four cited days; "
                       "rest %s for two weeks." % (", ".join("%s %.0f (n=%d)" % (h, b["avg"], b["n"]) for h, b in ranked),
                                                  best[0], worst[0]))
    readers = {r: b for r, b in (learn.get("reader") or {}).items() if r not in ("rotation", "unnamed") and b.get("n", 0) >= 2}
    if len(readers) >= 2:
        ranked = sorted(readers.items(), key=lambda kv: -kv[1]["avg"])
        out.append("Readers, by what they earned: %s — write to %s again this week on a new theme; do not drop the others."
                   % (", ".join("%s %.0f" % (r.title(), b["avg"]) for r, b in ranked), ranked[0][0].title()))
    src = learn.get("source") or {}
    if src.get("brain", {}).get("n", 0) >= 3 and src.get("rotation", {}).get("n", 0) >= 3:
        b, r = src["brain"]["avg"], src["rotation"]["avg"]
        out.append("Brain-written days averaged %.0f against %.0f for rotation days (%s)."
                   % (b, r, "keep going" if b >= r else "the hand-written baseline is winning — study its hooks"))
    for m in k.get("milestones") or []:
        if m["status"] == "behind_pace" and m.get("needed_per_week"):
            out.append("%s is behind pace: %s to go, %s a week now, %s a week needed by %s — this week every %s post ends with "
                       "the follow line ('follow for the next rule') and the Reel/Short names the Page by hand."
                       % (m["unlocks"] or m["key"], _fmt(m["remaining"]), _fmt(m["pace_per_week"] or 0), _fmt(m["needed_per_week"]),
                          m["due"], m["key"].split(".")[0].title()))
        elif m["status"] == "reached":
            out.append("%s reached (%s ≥ %s): switch it on in the platform's Professional dashboard and say so once in the channel."
                       % (m["unlocks"] or m["key"], _fmt(m["current"]), _fmt(m["target"])))
    advice = k.get("slot_advice") or {}
    if advice.get("move"):
        out.append("Instagram's audience is online most at %s WAT and we post at %s:10 — brain/slots.json moves the "
                   "Instagram slot to %02d:10 WAT by itself from this week; no tap needed."
                   % (", ".join("%02d:00" % h for h in advice["peak_hours_wat"]), advice["our_hour_wat"], advice["suggest_hour_wat"]))
    sold = k.get("sales.by_source_28d") or {}
    taps = k.get("sales.checkouts_by_source_28d") or {}
    if sum(sold.values()) >= 3:
        top = next(iter(sold))
        out.append("Money follows %s: %d of %d tagged passes in 28 days came through it — its send line names the "
                   "document and the price every day this week; the other channels copy its best hook."
                   % (top.title(), sold[top], sum(sold.values())))
    elif sum(taps.values()) >= 5:
        top = next(iter(taps))
        out.append("Checkout taps come mostly from %s (%d of %d) but few close: that channel's posts carry 'free to "
                   "start, ₦2,000 only when you need the stamp' in the last line this week." % (top.title(), taps[top], sum(taps.values())))
    visits = k.get("site.by_channel") or {}
    if visits:
        social = {c: n for c, n in visits.items() if c in ("telegram", "facebook", "instagram", "threads", "linkedin", "youtube", "tiktok", "whatsapp")}
        if social and sum(social.values()) >= 20:
            best = max(social.items(), key=lambda kv: kv[1])
            weak = [c for c, n in social.items() if n * 5 < best[1]]
            out.append("Readers reach the site from %s most (%d visits); %s"
                       % (best[0].title(), best[1], ("%s send almost none — their posts put the link where it can be tapped (first comment, reply, bio) and name the page" % ", ".join(weak)) if weak else "keep the mix"))
    striking = k.get("google.striking_distance") or []
    if striking:
        out.append("Google is already showing us for %s — one post and one Short this week answer each of those "
                   "questions in the first line, linking the page Google ranks."
                   % ", ".join("'%s' (pos %s, %s impressions)" % (q["query"], q["position"], q["impressions"]) for q in striking[:3]))
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


def build(http=None, env=None, now=None, history=None, goals=None, stats_path=YT_STATS, said=None):
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
        "site": pull_site(env, now, problems),
        "search": pull_search(problems, env),
    }
    k = kpis(channels, said)
    prev = previous_week(history, now)
    grades = grade(k, prev, goals)
    strk = streaks(history, grades)
    k["milestones"] = milestones(k, goals, history, now)
    k["slot_advice"] = slot_advice(k)
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
    if k.get("site.visits_7d") is not None:
        chans = ", ".join("%s %s" % (c, n) for c, n in list((k.get("site.by_channel") or {}).items())[:6]) or "no referrers yet"
        lines.append("**Traffic:** %s visits to the site this week (Nigeria %s) — %s"
                     % (_fmt(k["site.visits_7d"]), _fmt(k.get("site.nigeria_share")), chans))
    if k.get("sales.by_source_28d") is not None:
        sold = ", ".join("%s %s" % kv for kv in list(k["sales.by_source_28d"].items())[:6]) or "none tagged yet"
        taps = ", ".join("%s %s" % kv for kv in list((k.get("sales.checkouts_by_source_28d") or {}).items())[:6]) or "none yet"
        lines.append("**Sold by channel (28 days):** %s · checkout taps: %s" % (sold, taps))
    if k.get("google.clicks_28d") is not None:
        qs = ", ".join("'%s' (%s clicks, pos %s)" % (q["query"], q["clicks"], q["position"]) for q in (k.get("google.top_queries") or [])[:4])
        lines.append("**Google (28 days):** %s clicks / %s impressions, CTR %s — %s"
                     % (_fmt(k["google.clicks_28d"]), _fmt(k["google.impressions_28d"]), _fmt(k.get("google.ctr")), qs or "no queries yet"))
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
    if k.get("milestones"):
        lines += ["", "### Milestones (where the audience becomes income)", "| Milestone | Now | To go | Pace/week | Needed/week | ETA | Status |", "|---|---|---|---|---|---|---|"]
        for m in k["milestones"]:
            mark = {"reached": "🏁 reached", "on_pace": "✅ on pace", "behind_pace": "🔻 behind pace", "no-pace-yet": "⏳ measuring"}[m["status"]]
            eta = ("%s wk" % _fmt(m["weeks_to_go"])) if m.get("weeks_to_go") is not None else "—"
            lines.append("| %s | %s | %s | %s | %s | %s | %s (due %s) |" % (m["label"], _fmt(m["current"]), _fmt(m["remaining"]),
                         _fmt(m.get("pace_per_week")), _fmt(m.get("needed_per_week")), eta, mark, m.get("due")))
    if k.get("instagram.online_peak_hours_wat"):
        lines += ["", "Instagram followers online most at: " + ", ".join("%02d:00 WAT" % h for h in k["instagram.online_peak_hours_wat"])]
    for ch in ("facebook", "instagram", "threads"):
        by_hour = k.get(ch + ".by_hour") or {}
        if by_hour:
            top = sorted(by_hour.items(), key=lambda kv: -kv[1])[:3]
            lines.append("%s engagement by posting hour (WAT): %s" % (ch.title(), ", ".join("%s:00 → %s" % kv for kv in top)))
    learn = k.get("learning") or {}
    rows = [(dim, label, b) for dim in ("hook_type", "post_type", "reader", "source")
            for label, b in sorted((learn.get(dim) or {}).items(), key=lambda kv: -kv[1].get("avg", 0)) if b.get("n")]
    if rows:
        lines += ["", "### What the brain's choices earned (avg engagement score, posts)", "| Dimension | Choice | Avg | n |", "|---|---|---|---|"]
        lines += ["| %s | %s | %s | %d |" % (dim, label, b.get("avg"), b.get("n")) for dim, label, b in rows]
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
    ap.add_argument("command", choices=("pull", "summary", "grade", "slot"))
    ap.add_argument("lane", nargs="?", default="instagram", help="for `slot`: which lane's hour to print")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary-file", default=os.environ.get("GITHUB_STEP_SUMMARY"))
    a = ap.parse_args(argv)
    if a.command == "slot":
        plan = load_slots()
        hour = slot_hour(a.lane, plan)
        print("SLOT_HOUR_WAT=%d" % hour)
        print("SLOT_WHY=%s" % (((plan.get("lanes") or {}).get(a.lane) or {}).get("why") or "default — no plan written yet"))
        return 0
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
        plan = slot_plan(snap.get("kpis") or {}, load_slots())
        save_slots(plan)
        for lane, row in plan["lanes"].items():
            print("SLOT_%s=%02d:10 WAT%s — %s" % (lane.upper(), row["hour_wat"], " (moved)" if row["changed"] else "", row["why"]))
    return 0 if measured else 2


if __name__ == "__main__":
    sys.exit(main())
