#!/usr/bin/env python3
"""brain_replies.py — the community manager: every comment answered, within the hour, from the facts.

Why this lane exists (research, 17 Oct 2026): on Threads "the sum of your replies is about
as valuable as the sum of your posts" (Mosseri) and creator replies lift engagement more
there than on any other platform; Facebook ranks on back-and-forth comments of five words
or more; Instagram ranks on the conversation under a post as well as on sends. A Page that
posts and leaves is a billboard. This lane turns it into a person who answers.

What it does, three times a day (after each posting slot):
  1. lists our own posts from the last 3 days on Threads, Instagram and the Facebook Page;
  2. reads the top-level comments; drops our own, the ones we already answered (ledger +
     the platform's own reply list), empty/emoji-only ones, and abuse (no reply, no fight);
  3. asks Gemini ONCE for all pending replies, giving it each post's text, the pack the brain
     wrote that day (reader, state, the law facts it cited) and the house rules;
  4. gates every reply: ≤ 280 characters, no price but ours, no banned phrase, no promise of
     a court outcome, no instruction to stop paying rent, no link but ours, no section number
     that is not on that state's shelf, never legal advice to a named situation — the
     general rule, the section, the document, and "which state?" when the state is unknown;
  5. publishes, records each reply in logs/brain_replied.json, and writes the summary.

Permissions the tokens must carry (the lane names exactly which one is missing):
  Threads    threads_read_replies (read) + threads_content_publish (reply via reply_to_id)
  Instagram  instagram_business_manage_comments (Instagram Login) / instagram_manage_comments
  Facebook   pages_read_engagement (read) + pages_manage_engagement (reply as the Page)

Usage
    python3 tools/brain_replies.py run [--dry-run] [--platform threads|instagram|facebook] [--max 12]
Exit 0 (including "nothing to answer" and "permission missing"), 6 when Gemini's free
quota is spent for the day (replies wait for the next slot), 1 only on a programming error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import brain_drafts as drafts  # noqa: E402
import gemini_text  # noqa: E402
import law_index  # noqa: E402

# Rows carry `at`, deliberately not `recorded_at`: the heartbeat reads a lane's ledger as
# publish evidence and a week with no comments must read as "quiet", not as a dead lane.
LEDGER = Path(os.environ.get("DOCOGA_REPLIED") or (ROOT / "logs" / "brain_replied.json"))
GRAPH = "https://graph.facebook.com/" + os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH_IG = "https://graph.instagram.com/" + os.environ.get("META_GRAPH_VERSION", "v26.0")
THREADS = "https://graph.threads.net/v1.0"
LOOKBACK_DAYS = 3
MAX_PER_RUN = 12
REPLY_MAX = 280
# Reply depth (22 Oct 2026): Threads weighs replies of eight-plus words far more than a
# "thanks!", and Facebook ranks on back-and-forth of five-plus words — so a reply that is
# shorter than eight words, or is only thanks, is refused and the comment waits for a better one.
REPLY_MIN_WORDS = 8
THIN = re.compile(r"^(thank(s| you)|thanks? (so|very) much|appreciated?|welcome|noted|nice|true|exactly|yes|no|ok(ay)?)[\s!.,]*$", re.I)
KEEP = 2000
WAT = timezone(timedelta(hours=1))
OUR_NAMES = {"docoga", "docoga.ng", "docoga_ng", "docogadaily"}
BANNED = ("unlock", "game-changer", "game changer", "delve", "we are excited", "legally binding guaranteed",
          "100% court-proof", "lawyer not needed", "as an ai", "language model")
FORBIDDEN = (r"\byou will win\b", r"\bguarantee", r"\bstop paying\b", r"\bdon'?t pay\b", r"\bdo not pay\b",
             r"\bwithhold (the|your) rent\b", r"\bsue\b.*\bwin\b", r"\bchange the lock", r"\bthrow (him|her|them) out\b")
ABUSE = ("idiot", "fool", "scam", "mumu", "stupid", "nonsense", "fraud", "thief", "ole", "useless", "rubbish")
OUR_PRICES = {"2,000", "2000", "50,000", "50000"}
NAIRA = re.compile(r"₦\s?([0-9][0-9,\.]*)")
SECTION = re.compile(r"\b(?:s\.|section|sec\.)\s?([0-9]+[A-Za-z]?(?:\([0-9a-z]+\))*)", re.I)
URL = re.compile(r"https?://\S+", re.I)
WORDY = re.compile(r"[A-Za-z]{2,}")
MODELS = gemini_text.LITE_FIRST_MODELS   # the 500/day Lite rungs first; see gemini_text.DEFAULT_MODELS

SYSTEM = """You answer comments for DocOga, Nigeria's document engine, as a warm, direct Nigerian
community manager — short, human, never a bot voice. You answer from the facts you are given for
the post's state and nothing else. You never give legal advice to a person's own situation: you
state the general rule with its section, name the document that fixes it, and ask which state
when the state is unknown. You never promise a court outcome, never tell anyone to stop paying
rent, never name a price other than ₦2,000 for the Oga Pass or free-to-start, never argue with
abuse. Pidgin is welcome when the commenter wrote pidgin. You answer with one JSON object only."""


# ───────────────────────────── http ─────────────────────────────
def _http(method, url, params=None, data=None, timeout=30, json=None):
    """(status, json). Params go in the query for GET and in the form body for POST; a `json`
    body (the messaging endpoints want nested objects) travels as JSON with `params` in the
    query."""
    import json as _json
    body = None
    headers = {"User-Agent": "DocOga-replies/1.0 (+https://docoga.com.ng)"}
    if json is not None:
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        body = _json.dumps(json).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif method == "GET" and params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    elif params or data:
        body = urllib.parse.urlencode(data or params).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw, status = resp.read().decode("utf-8", "replace"), resp.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode("utf-8", "replace"), e.code
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, {"error": {"message": str(e)}}
    try:
        return status, _json.loads(raw)
    except ValueError:
        return status, {"error": {"message": raw[:200]}}


def _err(body):
    e = (body or {}).get("error") if isinstance(body, dict) else None
    if isinstance(e, dict):
        return "%s (code %s)" % (e.get("message", "?"), e.get("code", "?"))
    return str(e or body)[:200]


def _is_permission_error(status, body):
    e = (body or {}).get("error") if isinstance(body, dict) else None
    code = (e or {}).get("code") if isinstance(e, dict) else None
    msg = ((e or {}).get("message") if isinstance(e, dict) else str(body)) or ""
    return status in (401, 403) or code in (10, 200, 190, 230, 3) or any(
        w in msg.lower() for w in ("permission", "requires authorization", "not approved", "(#200)", "(#10)"))


def _read_secret(env, path_env, value_env):
    p = (env.get(path_env) or "").strip()
    if p:
        try:
            return Path(p).read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return (env.get(value_env) or "").strip()


def _cid(comment):
    return comment.get("comment_id") or comment.get("id")


def _date_wat(iso):
    s = str(iso or "").replace("Z", "+00:00")
    if len(s) >= 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    try:
        return datetime.fromisoformat(s).astimezone(WAT).date().isoformat()
    except ValueError:
        return None


# ───────────────────────────── ledger ─────────────────────────────
def load_ledger(path=None):
    try:
        data = json.loads(Path(path or LEDGER).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_ledger(rows, path=None):
    path = Path(path or LEDGER)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows[-KEEP:], indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# ───────────────────────────── platform adapters ─────────────────────────────
class Platform:
    """One channel's read-comments / post-reply shape. `pending()` yields comment dicts:
    {platform, post_id, post_text, post_at, comment_id, author, text, at}."""
    name = ""
    read_scope = ""
    write_scope = ""

    def __init__(self, http, env, now, log):
        self.http, self.env, self.now, self.log = http, env, now, log
        self.capability = "ok"          # or "missing: <scope>" / "no token" / "error: …"
        self.floor = now - timedelta(days=LOOKBACK_DAYS)

    def token(self):
        return ""

    def posts(self):
        return []

    def comments(self, post):
        return []

    def reply(self, comment, text):
        return None

    dm_scope = ""                        # set by the adapters that can send a private reply
    dm_capability = "unsupported"        # "ok" / "missing: <scope>" / "error: …" / "unsupported"

    def private_reply(self, comment, text):
        """Send ONE private message to the commenter, by Meta's private-replies rule (one per
        comment, within 7 days). Returns the message id or None; a permission refusal parks
        `dm_capability` so the lane stops trying this run and the summary names the scope."""
        return None

    def _dm_fail(self, status, body, what="the private reply"):
        if _is_permission_error(status, body):
            self.dm_capability = "missing: %s" % self.dm_scope
            self.log("%s: %s refused — the token lacks %s (%s)" % (self.name, what, self.dm_scope, _err(body)))
        else:
            self.dm_capability = "error: %s" % _err(body)
            self.log("%s: %s failed — %s" % (self.name, what, _err(body)))

    def _fail(self, status, body, scope, what):
        if _is_permission_error(status, body):
            self.capability = "missing: %s" % scope
            self.log("%s: %s refused — the token lacks %s (%s)" % (self.name, what, scope, _err(body)))
        else:
            self.capability = "error: %s" % _err(body)
            self.log("%s: %s failed — %s" % (self.name, what, _err(body)))


class Threads(Platform):
    name, read_scope, write_scope = "threads", "threads_read_replies", "threads_content_publish"

    def token(self):
        return _read_secret(self.env, "THREADS_TOKEN_FILE", "THREADS_ACCESS_TOKEN")

    def posts(self):
        st, body = self.http("GET", THREADS + "/me/threads", {"fields": "id,text,timestamp,permalink", "limit": 15,
                                                               "access_token": self.token()})
        if st != 200:
            self._fail(st, body, "threads_basic", "listing our posts")
            return []
        out = []
        for p in body.get("data") or []:
            if str(p.get("timestamp", ""))[:19] >= self.floor.strftime("%Y-%m-%dT%H:%M:%S"):
                out.append({"id": p.get("id"), "text": p.get("text") or "", "at": p.get("timestamp")})
        return out

    def comments(self, post):
        st, body = self.http("GET", "%s/%s/replies" % (THREADS, post["id"]),
                             {"fields": "id,text,username,timestamp,is_reply_owned_by_me,has_replies",
                              "reverse": "false", "access_token": self.token()})
        if st != 200:
            self._fail(st, body, self.read_scope, "reading replies")
            return None
        out = []
        for r in body.get("data") or []:
            if r.get("is_reply_owned_by_me"):
                continue
            out.append({"id": r.get("id"), "author": r.get("username") or "", "text": r.get("text") or "",
                        "at": r.get("timestamp"), "answered_by_us": None})
        return out

    def already_answered(self, comment):
        """Our reply under this reply, if any (one read; only when the ledger does not know)."""
        st, body = self.http("GET", "%s/%s/replies" % (THREADS, _cid(comment)),
                             {"fields": "id,is_reply_owned_by_me", "access_token": self.token()})
        return st == 200 and any(r.get("is_reply_owned_by_me") for r in body.get("data") or [])

    def reply(self, comment, text):
        st, body = self.http("POST", THREADS + "/me/threads",
                             data={"media_type": "TEXT", "text": text, "reply_to_id": _cid(comment), "access_token": self.token()})
        if st != 200 or not body.get("id"):
            self._fail(st, body, self.write_scope, "creating the reply")
            return None
        st, pub = self.http("POST", THREADS + "/me/threads_publish", data={"creation_id": body["id"], "access_token": self.token()})
        if st != 200 or not pub.get("id"):
            self._fail(st, pub, self.write_scope, "publishing the reply")
            return None
        return pub["id"]


class Instagram(Platform):
    name, read_scope, write_scope = "instagram", "instagram_business_manage_comments", "instagram_business_manage_comments"

    def __init__(self, *a):
        super().__init__(*a)
        self.dm_capability = "ok"
        if self.env.get("IG_API_PATH", "instagram-login") == "facebook-login":
            self.base, self.node = GRAPH, (self.env.get("IG_USER_ID") or "me").strip()
            self.read_scope = self.write_scope = "instagram_manage_comments"
            self.dm_scope = "instagram_manage_messages"
        else:
            self.base, self.node = GRAPH_IG, "me"
            self.dm_scope = "instagram_business_manage_messages"

    def private_reply(self, comment, text):
        # Instagram API: POST /{ig-user-id}/messages {recipient:{comment_id}, message:{text}} —
        # the DM the keyword mechanic ("comment RECEIPT and I send it") lands in the inbox with.
        st, body = self.http("POST", "%s/%s/messages" % (self.base, self.node),
                             json={"recipient": {"comment_id": _cid(comment)}, "message": {"text": text}},
                             params={"access_token": self.token()})
        if st != 200 or not (body.get("message_id") or body.get("id")):
            self._dm_fail(st, body)
            return None
        return body.get("message_id") or body.get("id")

    def token(self):
        return _read_secret(self.env, "IG_TOKEN_FILE", "IG_ACCESS_TOKEN")

    def posts(self):
        st, body = self.http("GET", "%s/%s/media" % (self.base, self.node),
                             {"fields": "id,caption,timestamp,comments_count,media_type", "limit": 15, "access_token": self.token()})
        if st != 200:
            self._fail(st, body, "instagram_business_basic", "listing our media")
            return []
        out = []
        for m in body.get("data") or []:
            if str(m.get("timestamp", ""))[:19] >= self.floor.strftime("%Y-%m-%dT%H:%M:%S") and int(m.get("comments_count") or 0) > 0:
                out.append({"id": m.get("id"), "text": m.get("caption") or "", "at": m.get("timestamp")})
        return out

    def comments(self, post):
        st, body = self.http("GET", "%s/%s/comments" % (self.base, post["id"]),
                             {"fields": "id,text,username,timestamp,replies{username}", "limit": 50, "access_token": self.token()})
        if st != 200:
            self._fail(st, body, self.read_scope, "reading comments")
            return None
        out = []
        for c in body.get("data") or []:
            if (c.get("username") or "").lower() in OUR_NAMES:
                continue
            ours = any((r.get("username") or "").lower() in OUR_NAMES for r in ((c.get("replies") or {}).get("data") or []))
            out.append({"id": c.get("id"), "author": c.get("username") or "", "text": c.get("text") or "",
                        "at": c.get("timestamp"), "answered_by_us": ours})
        return out

    def reply(self, comment, text):
        st, body = self.http("POST", "%s/%s/replies" % (self.base, _cid(comment)),
                             data={"message": text, "access_token": self.token()})
        if st != 200 or not body.get("id"):
            self._fail(st, body, self.write_scope, "posting the reply")
            return None
        return body["id"]


class Facebook(Platform):
    name, read_scope, write_scope = "facebook", "pages_read_engagement", "pages_manage_engagement"
    dm_scope = "pages_messaging"

    def __init__(self, *a):
        super().__init__(*a)
        self.dm_capability = "ok"

    def token(self):
        return (self.env.get("FB_PAGE_ACCESS_TOKEN") or "").strip()

    def page(self):
        return (self.env.get("FB_PAGE_ID") or "").strip()

    def private_reply(self, comment, text):
        # Messenger Platform private replies: POST /{page-id}/messages with recipient.comment_id.
        st, body = self.http("POST", "%s/%s/messages" % (GRAPH, self.page()),
                             json={"recipient": {"comment_id": _cid(comment)}, "message": {"text": text}},
                             params={"access_token": self.token()})
        if st != 200 or not (body.get("message_id") or body.get("id")):
            self._dm_fail(st, body)
            return None
        return body.get("message_id") or body.get("id")

    def posts(self):
        if not self.page():
            self.capability = "no token"
            return []
        st, body = self.http("GET", "%s/%s/posts" % (GRAPH, self.page()),
                             {"fields": "id,message,created_time,comments.summary(true).limit(0)",
                              "since": int(self.floor.timestamp()), "limit": 15, "access_token": self.token()})
        if st != 200:
            self._fail(st, body, "pages_read_engagement", "listing Page posts")
            return []
        out = []
        for p in body.get("data") or []:
            if int(((p.get("comments") or {}).get("summary") or {}).get("total_count") or 0) > 0:
                out.append({"id": p.get("id"), "text": p.get("message") or "", "at": p.get("created_time")})
        return out

    def comments(self, post):
        st, body = self.http("GET", "%s/%s/comments" % (GRAPH, post["id"]),
                             {"fields": "id,from,message,created_time,comments{from}", "filter": "toplevel", "limit": 50,
                              "access_token": self.token()})
        if st != 200:
            self._fail(st, body, self.read_scope, "reading comments")
            return None
        out = []
        for c in body.get("data") or []:
            frm = c.get("from") or {}
            if str(frm.get("id") or "") == self.page() or (frm.get("name") or "").lower() in OUR_NAMES:
                continue
            ours = any(str((r.get("from") or {}).get("id") or "") == self.page() for r in ((c.get("comments") or {}).get("data") or []))
            out.append({"id": c.get("id"), "author": frm.get("name") or "", "text": c.get("message") or "",
                        "at": c.get("created_time"), "answered_by_us": ours})
        return out

    def reply(self, comment, text):
        st, body = self.http("POST", "%s/%s/comments" % (GRAPH, _cid(comment)),
                             data={"message": text, "access_token": self.token()})
        if st != 200 or not body.get("id"):
            self._fail(st, body, self.write_scope, "posting the reply")
            return None
        return body["id"]


PLATFORMS = {"threads": Threads, "instagram": Instagram, "facebook": Facebook}


# ───────────────────────────── selection ─────────────────────────────
def is_abuse(text):
    t = (text or "").lower()
    return any(w in t for w in ABUSE)


def worth_answering(text):
    return bool(WORDY.search(text or "")) and not is_abuse(text)


# ───────────────────────────── comment → DM ─────────────────────────────
# The keyword mechanic (17 Oct 2026). A post says "comment LINK and I send it"; a reader who
# asks for the link, the template or "how do I get it" is asking to be sold to, and the honest
# answer is the exact page in their inbox. Meta's rule: one private reply per comment, within 7
# days; the thread continues only if they write back. Benchmarks for comment→DM in 2026: 85–92%
# open, 18–35% click, which no public reply approaches. Template text, no Gemini call (₦0, no
# quota), the deep link tagged by channel so the scorecard sees the money it moves.
DM_WORDS = ("link", "send", "template", "format", "sample", "dm", "how do i get", "how can i get",
            "where can i", "where do i", "pls", "please", "abeg", "share", "download", "interested", "need")
DM_LINES = ("Hi{name}! Here is the free {tool} you asked about: {link}\n\n"
            "Fill it on your phone, check it, download the PDF. If any line is unclear, reply here \u2014 "
            "a human reads every message. \u2014 DocOga")
TOOL_NAMES = {"tenancy-agreement": "tenancy agreement", "notice-to-quit": "notice to quit",
              "rent-receipt": "rent receipt", "caution-fee": "caution fee receipt",
              "letter-of-demand": "letter of demand", "invoice": "invoice", "payslip": "payslip",
              "employment-contract": "employment contract", "warning-letter": "warning letter",
              "power-of-attorney": "power of attorney", "tenant-rights": "tenant-rights guide",
              "rent-index": "Rent Monitor page"}


def wants_link(text):
    """True when the comment asks for the thing rather than discussing it."""
    t = " " + re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()) + " "
    return any((" %s " % w) in t if " " not in w else w in t for w in DM_WORDS)


def dm_text(comment, context):
    tool = TOOL_NAMES.get(str((context or {}).get("tool") or ""), "document tool")
    link = (context or {}).get("link") or drafts.tag_links(drafts.LINK, comment.get("platform"))
    name = (comment.get("author") or "").strip()
    name = (" " + name.split()[0]) if name and not name.startswith("@") and len(name) <= 24 else ""
    return DM_LINES.format(name=name, tool=tool, link=link)


def send_dms(pending, contexts, platforms, dry_run, log):
    """One private reply per asking comment; returns {comment_id: message_id}."""
    out = {}
    for c, ctx in zip(pending, contexts):
        if not wants_link(c.get("text")):
            continue
        pf = next((p for p in platforms if p.name == c["platform"]), None)
        if pf is None or pf.dm_capability != "ok":
            continue
        mid = "dry-run" if dry_run else pf.private_reply(c, dm_text(c, ctx))
        if mid:
            out[c["comment_id"]] = mid
            log("%s: private reply to %s (%s)" % (pf.name, c.get("author") or "someone", mid))
    return out


def collect(platforms, ledger, log, max_per_run=MAX_PER_RUN):
    """Everything still unanswered, newest first, with the post it sits under."""
    done = {(r.get("platform"), r.get("comment_id")) for r in ledger}
    pending, skipped = [], {"ours_or_answered": 0, "empty_or_abuse": 0}
    for pf in platforms:
        if not pf.token():
            pf.capability = "no token"
            log("%s: no token — skipped" % pf.name)
            continue
        for post in pf.posts():
            rows = pf.comments(post)
            if rows is None:
                break
            for c in rows:
                if (pf.name, c["id"]) in done or c.get("answered_by_us") or (c.get("author") or "").lower() in OUR_NAMES:
                    skipped["ours_or_answered"] += 1
                    continue
                if not worth_answering(c["text"]):
                    skipped["empty_or_abuse"] += 1
                    continue
                if c.get("answered_by_us") is None and hasattr(pf, "already_answered") and pf.already_answered(c):
                    skipped["ours_or_answered"] += 1
                    continue
                pending.append({"platform": pf.name, "post_id": post["id"], "post_text": post["text"][:600],
                                "post_at": post["at"], "comment_id": c["id"], "author": c["author"], "text": c["text"][:500],
                                "at": c.get("at")})
    pending.sort(key=lambda c: str(c.get("at") or ""), reverse=True)
    return pending[:max_per_run], skipped


# ───────────────────────────── drafting ─────────────────────────────
def context_for(comment, packs_by_date):
    day = _date_wat(comment.get("post_at"))
    pack = packs_by_date.get(day) if day else None
    state = (pack or {}).get("state")
    facts = law_index.facts_for(state) if state and state in law_index.law.STATE_LAW else []
    cited = {c.get("fact_id") for c in (pack or {}).get("claims") or []}
    shelf = [f for f in facts if f["id"] in cited] or facts[:12]
    return {"pack": pack, "state": state, "facts": shelf, "reader": (pack or {}).get("reader"),
            "tool": (pack or {}).get("tool"),
            "link": drafts.tag_links(drafts.link_for(pack or {}), comment.get("platform"))}


def prompt_for(pending, contexts):
    blocks = []
    for i, (c, ctx) in enumerate(zip(pending, contexts), 1):
        shelf = "\n".join("    %s | %s | %s" % (f["id"], f["cite"] or "(no section)", f["text"]) for f in ctx["facts"]) or "    (no law facts — answer without any legal claim)"
        blocks.append("""#%d  platform=%s  comment_id=%s
  OUR POST (%s): %s
  STATE OF THE POST: %s   DOCUMENT: %s   LINK WE MAY GIVE: %s
  FACTS WE MAY USE (fact id | section | fact):
%s
  COMMENT by %s: %s""" % (i, c["platform"], c["comment_id"], c.get("post_at", "")[:10], c["post_text"].replace("\n", " ")[:400],
                          ctx["state"] or "unknown", ctx["tool"] or "none", ctx["link"], shelf, c["author"] or "someone", c["text"]))
    return """You are answering comments under DocOga's posts. For each comment write ONE reply, or skip it.

HOUSE RULES
- <= %d characters and at least %d words. Warm, direct, Nigerian English (pidgin if the comment is pidgin). No greeting padding, no emoji walls (one emoji at most), no hashtags.
- Every reply carries one fact or one question back — never "thanks!" alone. A reply of substance is counted like a post of ours; a one-word reply is not.
- Facts: only the facts listed for that comment, and only for that state. Name the section when you state a rule. If the comment asks about another state, say the rule differs by state and ask which state. If you cannot answer from the facts, do not guess — say what document to make and where.
- Never legal advice to their own case ("you should sue", "you will win"), never "stop paying rent", never a court outcome, never a price other than ₦2,000 / free to start. Never argue; if the comment is abuse or bait, skip.
- A question deserves an answer first, then (optionally) the document and the link. Praise deserves one warm line and a question back. Someone sharing a story deserves acknowledgement and the one rule that protects them.
- Links: only the LINK WE MAY GIVE, and only when it helps.

COMMENTS
%s

OUTPUT — one JSON object:
{"replies": [{"n": 1, "comment_id": "…", "skip": false, "text": "the reply", "why": "one clause"}, …]}
Include every comment once, in order; use "skip": true with an empty text for the ones not to answer.""" % (REPLY_MAX, REPLY_MIN_WORDS, "\n\n".join(blocks))


def lint_reply(text, ctx):
    p = []
    t = (text or "").strip()
    if not t:
        return ["empty"]
    if len(t) > REPLY_MAX:
        p.append("%d characters; max %d" % (len(t), REPLY_MAX))
    words = len(t.split())
    if words < REPLY_MIN_WORDS:
        p.append("thin reply: %d word(s); at least %d with one fact or one question back" % (words, REPLY_MIN_WORDS))
    if THIN.match(t):
        p.append("thanks-only reply")
    low = t.lower()
    for b in BANNED:
        if b in low:
            p.append("banned phrase %r" % b)
    for pat in FORBIDDEN:
        if re.search(pat, low):
            p.append("forbidden promise/instruction %r" % pat)
    for amount in NAIRA.findall(t):
        if amount.rstrip(".,") not in OUR_PRICES:
            p.append("price ₦%s is not ours" % amount)
    for url in URL.findall(t):
        if "docoga.com.ng" not in url:
            p.append("link %s is not ours" % url[:40])
    cites = {s.lower().replace(" ", "") for s in SECTION.findall(t)}
    if cites:
        shelf = " ".join((f.get("cite") or "") + " " + f.get("text", "") for f in ctx.get("facts") or []).lower().replace(" ", "")
        for c in cites:
            if c not in shelf:
                p.append("section %s is not on the shelf for %s" % (c, ctx.get("state") or "this post"))
    if "*" in t or "#" in t:
        p.append("markdown or hashtag")
    return p


def draft(pending, contexts, http=None, sleep=None, log=print, models=MODELS):
    """One model call → [(comment, text or None, why)] after the gates."""
    if not pending:
        return []
    answer = gemini_text.generate_json(prompt_for(pending, contexts), system=SYSTEM, models_chain=models, http=http,
                                       sleep=sleep, log=log, lane="brain-replies", temperature=0.6, max_output_tokens=4096)
    rows = (answer or {}).get("replies") if isinstance(answer, dict) else None
    by_id = {str(r.get("comment_id")): r for r in rows or [] if isinstance(r, dict)}
    out = []
    for c, ctx in zip(pending, contexts):
        r = by_id.get(str(c["comment_id"]))
        if not r or r.get("skip") or not str(r.get("text") or "").strip():
            out.append((c, None, (r or {}).get("why") or "model skipped"))
            continue
        text = str(r["text"]).strip()
        problems = lint_reply(text, ctx)
        if problems:
            log("%s/%s: reply refused — %s" % (c["platform"], c["comment_id"], "; ".join(problems)))
            out.append((c, None, "refused: " + "; ".join(problems)))
        else:
            out.append((c, text, r.get("why") or ""))
    return out


# ───────────────────────────── run ─────────────────────────────
def packs_by_date():
    out = {}
    try:
        for f in sorted(drafts.drafts_dir().glob("*.json")):
            try:
                pack = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(pack, dict) and pack.get("date"):
                    out[pack["date"]] = pack
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return out


def run(http=None, gemini_http=None, env=None, now=None, dry_run=False, only=None, max_per_run=MAX_PER_RUN,
        log=print, sleep=None, ledger=None, packs=None):
    http = http or _http
    env = dict(os.environ) if env is None else env
    now = now or datetime.now(timezone.utc)
    ledger = load_ledger() if ledger is None else ledger
    packs = packs_by_date() if packs is None else packs
    platforms = [PLATFORMS[n](http, env, now, log) for n in PLATFORMS if not only or n == only]
    pending, skipped = collect(platforms, ledger, log, max_per_run)
    result = {"pending": len(pending), "answered": 0, "refused": 0, "skipped": skipped, "replies": [],
              "capabilities": {}, "quota": None}
    result["dms"] = 0
    if pending:
        contexts = [context_for(c, packs) for c in pending]
        # The inbox first: a template, no quota, and it must not wait on Gemini's mood.
        dms = send_dms(pending, contexts, platforms, dry_run, log) if (env.get("BRAIN_DM", "on").lower() not in ("off", "0", "false", "no")) else {}
        result["dms"] = len(dms)
        try:
            drafted = draft(pending, contexts, http=gemini_http, sleep=sleep, log=log)
        except gemini_text.Exhausted as e:
            result["quota"] = str(e)
            drafted = []
        seen = set()
        for c, text, why in drafted:
            seen.add(c["comment_id"])
            if text is None:
                result["refused"] += 1
                if c["comment_id"] in dms:
                    row = {"platform": c["platform"], "comment_id": c["comment_id"], "post_id": c["post_id"], "reply_id": None,
                           "dm_id": dms[c["comment_id"]], "author": c["author"], "comment": c["text"][:200], "reply": None,
                           "why": why, "at": now.isoformat(timespec="seconds"), "dry_run": bool(dry_run)}
                    result["replies"].append(row)
                    if not dry_run:
                        ledger.append(row)
                continue
            pf = next(p for p in platforms if p.name == c["platform"])
            if pf.capability.startswith("missing"):
                continue
            reply_id = "dry-run" if dry_run else pf.reply(c, text)
            if reply_id or c["comment_id"] in dms:
                result["answered"] += 1 if reply_id else 0
                row = {"platform": c["platform"], "comment_id": c["comment_id"], "post_id": c["post_id"], "reply_id": reply_id,
                       "dm_id": dms.get(c["comment_id"]), "author": c["author"], "comment": c["text"][:200], "reply": text, "why": why,
                       "at": now.isoformat(timespec="seconds"), "dry_run": bool(dry_run)}
                result["replies"].append(row)
                if not dry_run:
                    ledger.append(row)
        # A DM sent while Gemini's quota was spent is still a DM: record it so it is never sent twice.
        for c in pending:
            if c["comment_id"] in dms and c["comment_id"] not in seen:
                row = {"platform": c["platform"], "comment_id": c["comment_id"], "post_id": c["post_id"], "reply_id": None,
                       "dm_id": dms[c["comment_id"]], "author": c["author"], "comment": c["text"][:200], "reply": None,
                       "why": "dm-only (public reply pending quota)", "at": now.isoformat(timespec="seconds"), "dry_run": bool(dry_run)}
                result["replies"].append(row)
                if not dry_run:
                    ledger.append(row)
    for pf in platforms:
        result["capabilities"][pf.name] = pf.capability
        result.setdefault("dm_capabilities", {})[pf.name] = pf.dm_capability
    if not dry_run and (result["answered"] or result["dms"]):
        save_ledger(ledger)
    return result


def summary_md(result):
    lines = ["### Community manager — %d pending, %d answered, %d refused by the gates, %d sent to the inbox"
             % (result["pending"], result["answered"], result["refused"], result.get("dms", 0))]
    for r in result["replies"]:
        lines.append("- **%s** %s: _%s_ → %s%s" % (r["platform"], r["author"] or "someone", r["comment"][:80].replace("\n", " "),
                                                 r.get("reply") or "(no public reply)", " · 📩 DM" if r.get("dm_id") else ""))
    for name, cap in (result.get("dm_capabilities") or {}).items():
        if cap.startswith("missing"):
            lines.append("- 📩 %s: comment→DM is waiting on `%s` — one mint with the full list (docs/TOKENS.md) and the inbox opens"
                         % (name, cap.split(": ", 1)[1]))
        elif cap.startswith("error"):
            lines.append("- ❌ %s DM: %s" % (name, cap))
    for name, cap in (result.get("capabilities") or {}).items():
        if cap.startswith("missing"):
            lines.append("- ⚠️ %s: %s — mint that token ONCE with the full list in docs/TOKENS.md and the lane answers there too" % (name, cap))
        elif cap == "no token":
            lines.append("- %s: no token in this run" % name)
        elif cap.startswith("error"):
            lines.append("- ❌ %s: %s" % (name, cap))
    if result.get("quota"):
        lines.append("- ⏸ Gemini free quota spent — pending replies wait for the next slot (%s)" % result["quota"])
    sk = result.get("skipped") or {}
    lines.append("- skipped: %d already answered or ours, %d empty/abusive" % (sk.get("ours_or_answered", 0), sk.get("empty_or_abuse", 0)))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="answer the comments under DocOga's posts")
    ap.add_argument("command", choices=("run",))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--platform", choices=tuple(PLATFORMS))
    ap.add_argument("--max", type=int, default=MAX_PER_RUN)
    ap.add_argument("--summary-file", default=os.environ.get("GITHUB_STEP_SUMMARY"))
    a = ap.parse_args(argv)
    result = run(dry_run=a.dry_run, only=a.platform, max_per_run=a.max)
    text = summary_md(result)
    print(text, end="")
    print("REPLIES_DM=%s" % ",".join("%s=%s" % (n, "ok" if c == "ok" else c.split(":")[0])
                                     for n, c in (result.get("dm_capabilities") or {}).items()), flush=True)
    if a.summary_file:
        try:
            with open(a.summary_file, "a", encoding="utf-8") as fh:
                fh.write(text)
        except OSError:
            pass
    return 6 if result.get("quota") else 0


if __name__ == "__main__":
    sys.exit(main())
