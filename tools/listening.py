#!/usr/bin/env python3
"""listening.py — what Nigerians are ASKING about rent this week, and one answer a week.

The newsdesk hears the papers. This hears the people: thread titles on Nairaland's
Properties / Family / Politics boards and r/Nigeria, where tenants ask the exact
questions DocOga's documents answer ("landlord wants me out after 2 months",
"is 2 years' rent in advance legal", "no receipt — can I still prove I paid"). No
API, no login, no posting — a GET of public pages, a score, a JSON file.

Two outputs, both ₦0:

  pull    → brain/listening.json  — the top questions (title, url, board, score)
            The brain's prompt carries them as WHAT NIGERIANS ASKED THIS WEEK, so a
            day's post answers a real question in the reader's own words.
  answer  → brain/answers/YYYY-MM-DD.md — ONE cited, link-carrying reply to the best
            open thread, drafted by Gemini from the law shelf and gated exactly like a
            post (every legal claim names a shelf fact and appears verbatim). The
            owner pastes it by hand: Nairaland has no posting API and an automated
            account there is a ban, not a channel. The Monday issue carries it.
            When no thread deserves a reply (most weeks — the Properties board is
            adverts), it drafts a thread OPENER instead: one state, one topic, cited.

Everything degrades to silence: no network → the brain plans without it; no model
→ no answer file, the lanes are untouched.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import law_index  # noqa: E402

OUT = Path(os.environ.get("DOCOGA_LISTENING") or (ROOT / "brain" / "listening.json"))
ANSWERS = Path(os.environ.get("DOCOGA_ANSWERS") or (ROOT / "brain" / "answers"))
LINK = "https://docoga.com.ng/?s=nl"
TIMEOUT = 20
TOP = 12
UA = "Mozilla/5.0 (compatible; DocOga-listening/1.0; +https://docoga.com.ng)"

SOURCES = (
    {"name": "Nairaland Properties", "url": "https://www.nairaland.com/properties", "kind": "nairaland", "board": "properties"},
    {"name": "Nairaland Family", "url": "https://www.nairaland.com/family", "kind": "nairaland", "board": "family"},
    {"name": "Nairaland Politics", "url": "https://www.nairaland.com/politics", "kind": "nairaland", "board": "politics"},
    {"name": "r/Nigeria", "url": "https://www.reddit.com/r/Nigeria/search.json?q=landlord%20OR%20rent%20OR%20tenant&restrict_sr=1&sort=new&limit=50",
     "kind": "reddit", "board": "r/Nigeria"},
)

# A thread title is a question DocOga can answer when it carries the problem words …
STRONG = {"landlord": 3, "landlady": 3, "tenant": 3, "tenants": 3, "tenancy": 3, "quit notice": 4, "notice to quit": 4,
          "eviction": 3, "evict": 3, "evicted": 3, "ejection": 3, "rent": 2, "rents": 2, "caution fee": 4, "caution deposit": 4,
          "agreement fee": 3, "agency fee": 3, "legal fee": 2, "receipt": 2, "deposit": 1, "advance": 1, "increase": 1,
          "increment": 2, "agent": 1, "caretaker": 2, "lock": 1, "locked": 2, "padlock": 3, "pack out": 3, "packed out": 2,
          "court": 1, "lawyer": 1, "refund": 2, "arrears": 2, "service charge": 2, "estate": 0, "house": 0}
# … and the question words that mark a person asking, not a firm selling.
ASKING = ("?", "how ", "can ", "what ", "is it", "is this", "should ", "pls", "please", "advice", "advise", "help",
          "my landlord", "my landlady", "my tenant", "my agent", "my caretaker", "legal", "right", "rights", "law",
          "what to do", "wetin", "abeg", "urgent")
# Adverts and listings, which dominate the Properties board.
NOISE = ("for sale", "for rent", "to let", "4 sale", "shortlet", "short let", "sqm", "plots", "plot of", "acres", "hectare",
         "c of o", "c-of-o", "governor's consent", "distress sale", "mortgage", "duplex", "bungalow", "terrace", "semi-detached",
         "fully detached", "off plan", "offplan", "estate launch", "promo", "available", "selling", "buy ", "bq ", "lekki phase",
         "ibeju", "epe", "₦", "naira", "million", "price", "cheap", "affordable", "investment", "roi", "hostel space", "roommate")

NAIRALAND_LINK = re.compile(r'<a\s+href="(?:https?://www\.nairaland\.com)?/(\d{4,9})/([a-z0-9\-]+)(?:/\d+)?(?:#\d+)?"[^>]*>(.*?)</a>',
                            re.I | re.S)
TAG = re.compile(r"<[^>]+>")


def _http(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html, application/json, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def _clean(title):
    return " ".join(html.unescape(TAG.sub("", str(title))).split())


def parse_nairaland(raw, board):
    """Thread titles on a board page → items. Thread ids rise with time, so a higher id is fresher."""
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    seen, items = set(), []
    for tid, slug, inner in NAIRALAND_LINK.findall(text):
        title = _clean(inner)
        if not title or len(title) < 12 or tid in seen or title.lower().startswith(("re:", "page ")):
            continue
        seen.add(tid)
        items.append({"title": title, "url": "https://www.nairaland.com/%s/%s" % (tid, slug), "board": board,
                      "source": "Nairaland", "order": int(tid)})
    return items


def parse_reddit(raw, board):
    try:
        data = json.loads(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
    except ValueError:
        return []
    items = []
    for child in ((data.get("data") or {}).get("children") or []):
        d = child.get("data") or {}
        title = _clean(d.get("title") or "")
        if not title or not d.get("permalink"):
            continue
        items.append({"title": title, "url": "https://www.reddit.com" + d["permalink"], "board": board, "source": "Reddit",
                      "order": int(d.get("created_utc") or 0), "comments": int(d.get("num_comments") or 0)})
    return items


# Whole words only (31 Oct 2026): "rent" used to match inside "paRENT" and "diffeRENT", which is
# how a baby-sleep thread became the week's best rent question.
_STRONG_RE = {word: re.compile(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])") for word in STRONG}


def score(item):
    t = " " + item["title"].lower() + " "
    s = 0
    for word, w in STRONG.items():
        if _STRONG_RE[word].search(t):
            s += w
    if s == 0:
        return 0
    asked = sum(1 for q in ASKING if q in t)
    s += min(asked, 3) * 2
    if any(n in t for n in NOISE):
        s -= 6
    if item.get("comments", 0) >= 10:
        s += 2
    return max(0, s)


def select(items, top=TOP):
    scored = []
    for it in items:
        s = score(it)
        if s >= 5:
            scored.append({**it, "score": s})
    scored.sort(key=lambda i: (-i["score"], -i.get("order", 0)))
    out, seen = [], set()
    for it in scored:
        key = it["title"].lower()[:60]
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
        if len(out) >= top:
            break
    return out


def pull(http=None, now=None, log=print, sources=SOURCES):
    http = http or _http
    now = now or dt.datetime.now(dt.timezone.utc)
    items, heard = [], []
    for src in sources:
        try:
            status, raw = http(src["url"])
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            log("listening: %s — %s" % (src["name"], str(exc)[:80]))
            continue
        if status != 200:
            log("listening: %s — HTTP %s" % (src["name"], status))
            continue
        got = parse_nairaland(raw, src["board"]) if src["kind"] == "nairaland" else parse_reddit(raw, src["board"])
        heard.append("%s: %d" % (src["name"], len(got)))
        items += got
    chosen = select(items)
    previous = load()
    answered = previous.get("answered") or []
    log("listening: heard %s → %d questions kept" % (", ".join(heard) or "nothing", len(chosen)))
    return {"pulled_at": now.isoformat(timespec="seconds"), "items": chosen, "answered": answered[-52:],
            "sources": heard}


def load(path=None):
    p = Path(path) if path else OUT
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def fresh_items(data=None, now=None, max_age_days=8):
    data = data if data is not None else load()
    try:
        pulled = dt.datetime.fromisoformat(str(data.get("pulled_at")))
    except (TypeError, ValueError):
        return []
    now = now or dt.datetime.now(dt.timezone.utc)
    if pulled.tzinfo is None:
        pulled = pulled.replace(tzinfo=dt.timezone.utc)
    if (now - pulled).days > max_age_days:
        return []
    return list(data.get("items") or [])


def prompt_block(items):
    if not items:
        return "(no questions heard this week — write to the audience file's personas)"
    return "\n".join("- \"%s\" — %s" % (it["title"], it.get("board") or it.get("source", "")) for it in items[:10])


# ───────────────────────────── the weekly answer ─────────────────────────────
ANSWER_SYSTEM = ("You are DocOga's editor answering one Nigerian in a public forum. Plain Nigerian English, warm, "
                 "no legalese, no 'as an AI'. Every legal statement must be one of the shelf facts, cited by its section "
                 "in brackets. Never invent a rule. You are not their lawyer: end with the line 'General information, "
                 "not legal advice.' and the DocOga link.")


def answer_prompt(item, facts, state_name):
    shelf = "\n".join("%s | %s | %s" % (f["id"], f["cite"] or "(no section)", f["text"]) for f in facts)
    return f"""THE THREAD (title only — answer the question the title asks; do not assume facts it does not state)
"{item['title']}" — {item.get('board') or item.get('source')}

THE LAW SHELF FOR {state_name.upper()} (fact id | section | fact) — the only law you may state
{shelf}

If the thread does not say which state, answer for {state_name} and say in one line that the rule differs by state.

OUTPUT — one JSON object:
{{
  "answer": "180 to 1200 characters, 3 to 6 short paragraphs separated by blank lines. First line restates their situation in their words. Then the rule(s) with the section in brackets, e.g. (s.13(1)(e), Lagos Tenancy Law 2011). Then the ONE thing to do next. Last two lines exactly: 'General information, not legal advice.' then '{LINK}'",
  "claims": [{{"text": "a legal sentence exactly as it appears in answer", "fact_id": "an id from the shelf"}}],
  "state": "{state_name}",
  "why": "one sentence: why this thread, this week"
}}"""


def gate(result, facts_by_id):
    """Same bar as a post: cited, verbatim, bounded, link present. Returns the list of problems."""
    problems = []
    answer = str((result or {}).get("answer") or "")
    claims = result.get("claims") if isinstance((result or {}).get("claims"), list) else []
    if not 180 <= len(answer) <= 1400:
        problems.append("answer length %d is outside 180-1400" % len(answer))
    if LINK not in answer:
        problems.append("the DocOga link is missing")
    if "not legal advice" not in answer.lower():
        problems.append("the 'not legal advice' line is missing")
    if not claims:
        problems.append("no claims — an answer with no cited rule is not an answer")
    for c in claims:
        fid = str(c.get("fact_id") or "")
        text = str(c.get("text") or "").strip()
        if fid not in facts_by_id:
            problems.append("claim cites unknown fact %r" % fid)
        if text and " ".join(text.split()) not in " ".join(answer.split()):
            problems.append("claim text is not in the answer verbatim: %r" % text[:60])
    for bad in ("as an ai", "i am not a lawyer but", "six months free", "free rent"):
        if bad in answer.lower():
            problems.append("forbidden phrase: %r" % bad)
    return problems


def pick_thread(items, answered):
    done = {a.get("url") for a in answered}
    for it in items:
        if it.get("url") not in done:
            return it
    return None


def state_for(item, default="lagos"):
    t = item["title"].lower()
    for slug, name, _tier in law_index.states():
        if name.split(" (")[0].lower() in t or slug.replace("-", " ") in t:
            return slug
    return default


def answer(generate=None, data=None, now=None, log=print, out_dir=None, write=True):
    """Draft this week's one forum answer. Returns (path, result) or (None, reason)."""
    data = data if data is not None else load()
    items = fresh_items(data, now=now)
    thread = pick_thread(items, data.get("answered") or [])
    if not thread:
        return None, "no open question this week"
    slug = state_for(thread)
    facts = law_index.facts_for(slug)
    if not facts:
        return None, "no shelf for %s" % slug
    facts_by_id = {f["id"]: f for f in facts}
    state_name = facts[0]["state"]
    if generate is None:
        import gemini_text  # noqa: WPS433 — only when a model is really needed
        generate = lambda prompt, system: gemini_text.generate_json(prompt, system=system, lane="listening",  # noqa: E731
                                                                    temperature=0.6, max_output_tokens=4096)
    result = generate(answer_prompt(thread, facts, state_name), ANSWER_SYSTEM)
    problems = gate(result, facts_by_id)
    if problems:
        log("listening: answer refused — " + "; ".join(problems))
        return None, "refused: " + "; ".join(problems)
    now = now or dt.datetime.now(dt.timezone.utc)
    day = now.date().isoformat()
    out_dir = Path(out_dir) if out_dir else ANSWERS
    path = out_dir / ("%s.md" % day)
    body = ("# Forum answer — %s\n\nThread: %s\nURL: %s\nState: %s\nWhy: %s\n\n---\n\n%s\n"
            % (day, thread["title"], thread["url"], state_name, result.get("why", ""), result["answer"].strip()))
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        data.setdefault("answered", []).append({"date": day, "url": thread["url"], "title": thread["title"]})
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log("listening: answer written for %r → %s" % (thread["title"], path))
    return path, result


# ───────────────────────────── the thread opener ─────────────────────────────
# 31 Oct 2026: in two weeks of listening the Properties board never produced a reply-worthy
# question — its front page is adverts — so the Monday lane never wrote a line, and the owner's
# first Nairaland post was drafted by hand. When there is no thread to answer, open one: a
# cited explainer on one state's law, in the form that worked on 30 Oct 2026
# (https://www.nairaland.com/8774812/before-pay-rent-lagos-5). Nairaland's rules shape the
# gate: no advert tone, no ALL CAPS, no bold, one link, a subject that fits their box.
OPENER_SUBJECT_MAX = 70
OPENER_BOARD = "Properties"
OPENER_TOPICS = ("receipts", "notice_ladder", "advance_rent", "protections", "caution_fee", "notice_extras",
                 "increase_challenge", "repairs", "rent_relief")
OPENER_SYSTEM = ("You are DocOga's editor opening one new topic on Nairaland's Properties board for Nigerian tenants and "
                 "landlords. Plain Nigerian English, warm, no legalese, no advert tone, no 'as an AI'. Every legal statement "
                 "must be one of the shelf facts, cited by its section in brackets. Never invent a rule, a number or a "
                 "case. No ALL CAPS words, no bold, no emoji. One link only, on the last line but one.")


def opener_prompt(state_name, topic, facts):
    shelf = "\n".join("%s | %s | %s" % (f["id"], f["cite"] or "(no section)", f["text"]) for f in facts)
    return f"""THE TOPIC: {topic.replace('_', ' ')} under the tenancy law of {state_name}.

THE LAW SHELF (fact id | section | fact) — the only law you may state
{shelf}

OUTPUT — one JSON object:
{{
  "subject": "a Nairaland topic title of at most {OPENER_SUBJECT_MAX} characters, Title Case, naming {state_name} and the problem (e.g. 'Before You Pay Rent In Lagos: 5 Things The Tenancy Law Actually Says')",
  "body": "700 to 1800 characters. First paragraph: the everyday wahala in two sentences. Then 3 to 5 numbered points, each ONE rule with its section in brackets, e.g. (s.5(3)). Then one short paragraph on the ONE thing to do next (keep receipts / count the months / write, do not pack). Then the line: 'I built a free tenancy agreement, quit notice and rent receipt generator for every state: {LINK}'. Last line exactly: 'General information, not legal advice.'",
  "claims": [{{"text": "a legal sentence exactly as it appears in body", "fact_id": "an id from the shelf"}}],
  "state": "{state_name}",
  "why": "one sentence: why this topic now"
}}"""


def opener_gate(result, facts_by_id):
    problems = []
    subject = str((result or {}).get("subject") or "").strip()
    body = str((result or {}).get("body") or "")
    if not 20 <= len(subject) <= OPENER_SUBJECT_MAX:
        problems.append("subject length %d is outside 20-%d (Nairaland clips it)" % (len(subject), OPENER_SUBJECT_MAX))
    if not 700 <= len(body) <= 2200:
        problems.append("body length %d is outside 700-2200" % len(body))
    if body.count(LINK) != 1:
        problems.append("the DocOga link must appear exactly once")
    if "not legal advice" not in body.lower():
        problems.append("the 'not legal advice' line is missing")
    claims = result.get("claims") if isinstance((result or {}).get("claims"), list) else []
    if len(claims) < 3:
        problems.append("fewer than 3 cited claims — an opener with no law is an advert")
    for c in claims:
        fid = str(c.get("fact_id") or "")
        text = " ".join(str(c.get("text") or "").split())
        if fid not in facts_by_id:
            problems.append("claim cites unknown fact %r" % fid)
        if text and text not in " ".join(body.split()):
            problems.append("claim text is not in the body verbatim: %r" % text[:60])
    if "**" in body or "**" in subject:
        problems.append("bold markup (Nairaland rule 11)")
    if re.search(r"\b[A-Z]{5,}\b", body.replace("DOCOGA", "")):
        problems.append("an ALL CAPS word (Nairaland rule 11)")
    for bad in ("as an ai", "i am not a lawyer but", "dm me", "whatsapp me", "call me", "promo", "discount"):
        if bad in body.lower():
            problems.append("forbidden phrase: %r" % bad)
    return problems


def opener_choice(answered, now=None):
    """(slug, topic) not yet opened: Tier A states in turn, then the next topic each cycle."""
    used = {(a.get("state_slug"), a.get("topic")) for a in answered if a.get("kind") == "thread_opener"}
    states = [s for s, _n, tier in law_index.states() if tier == "A"] or [s for s, _n, _t in law_index.states()]
    # Lagos last in each cycle: the 30 Oct 2026 hand-made opener already covered Lagos receipts, advance
    # rent, notice and protections, so the other Tier A states get their turn first.
    states = sorted(states, key=lambda s: (s == "lagos", s))
    for topic in OPENER_TOPICS:
        for slug in states:
            if (slug, topic) in used:
                continue
            facts = [f for f in law_index.facts_for(slug) if f["id"].split(":")[1] == topic]
            if len(facts) >= 3:
                return slug, topic, facts
    return None, None, []


def opener(generate=None, data=None, now=None, log=print, out_dir=None, write=True):
    """Draft one Nairaland thread opener when no open question deserved a reply. (path, result) or (None, why)."""
    data = data if data is not None else load()
    answered = data.get("answered") or []
    slug, topic, facts = opener_choice(answered, now=now)
    if not slug:
        return None, "every state and topic has been opened once — nothing new to say"
    all_facts = law_index.facts_for(slug)
    facts_by_id = {f["id"]: f for f in all_facts}
    state_name = all_facts[0]["state"]
    if generate is None:
        import gemini_text  # noqa: WPS433
        generate = lambda prompt, system: gemini_text.generate_json(prompt, system=system, lane="listening",  # noqa: E731
                                                                    temperature=0.6, max_output_tokens=4096)
    result = generate(opener_prompt(state_name, topic, facts), OPENER_SYSTEM)
    problems = opener_gate(result, facts_by_id)
    if problems:
        log("listening: opener refused — " + "; ".join(problems))
        return None, "refused: " + "; ".join(problems)
    now = now or dt.datetime.now(dt.timezone.utc)
    day = now.date().isoformat()
    out_dir = Path(out_dir) if out_dir else ANSWERS
    path = out_dir / ("%s.md" % day)
    subject = str(result["subject"]).strip()
    body = ("# Nairaland thread opener — %s\n\nBoard: %s → Create New Topic. Paste the subject, then the body, then Submit. "
            "If your account is new and the post is held, repost without the link line and add the link as your first reply.\n"
            "State: %s · Topic: %s\nWhy: %s\n\nSubject:\n\n```text\n%s\n```\n\nBody:\n\n```text\n%s\n```\n"
            % (day, OPENER_BOARD, state_name, topic.replace("_", " "), result.get("why", ""), subject, str(result["body"]).strip()))
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        data.setdefault("answered", []).append({"date": day, "url": "opener:%s:%s:%s" % (slug, topic, day), "title": subject,
                                                "kind": "thread_opener", "state_slug": slug, "topic": topic, "board": "properties"})
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log("listening: opener written for %s / %s → %s" % (state_name, topic, path))
    return path, result


def latest_answer(out_dir=None, max_age_days=8, now=None):
    out_dir = Path(out_dir) if out_dir else ANSWERS
    if not out_dir.is_dir():
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    for p in sorted(out_dir.glob("*.md"), reverse=True):
        try:
            day = dt.date.fromisoformat(p.stem)
        except ValueError:
            continue
        if (now.date() - day).days <= max_age_days:
            return p
        break
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="what Nigerians are asking about rent")
    ap.add_argument("command", choices=("pull", "show", "answer", "latest"))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    if a.command == "show":
        for it in fresh_items():
            print("%2d  %s — %s" % (it.get("score", 0), it["title"], it.get("board", "")))
        return 0
    if a.command == "latest":
        p = latest_answer()
        print("LISTENING_ANSWER=%s" % (p or "none"))
        return 0
    if a.command == "answer":
        try:
            path, result = answer()
            if path is None and str(result).startswith("no open question"):
                print("listening: no reply-worthy thread this week — opening one instead")
                path, result = opener()
        except Exception as exc:  # noqa: BLE001 — a missing answer must never fail the brain
            print("listening: answer skipped — %s" % str(exc)[:160])
            print("LISTENING_ANSWER=none")
            return 0
        print("LISTENING_ANSWER=%s" % (path or "none"))
        if not path:
            print("listening: %s" % result)
        return 0
    data = pull()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote %s (%d questions)" % (a.out, len(data["items"])))
    print("LISTENING_HEARD=%d" % len(data["items"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
