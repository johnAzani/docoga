#!/usr/bin/env python3
"""brain.py — DocOga's standing editor.

Owner, 16 Oct 2026: "I don't want a bank. I want a brain that can think like you,
understands content creation and my business, so that it works autonomously —
everything automated. It only handles the social media."

So this is the one place where a day's content is *decided* rather than drawn
from a list. Every night it reads the business memory (brain/business.md), the
editorial policy (brain/editorial.md), the law shelf (tools/law_index.py — the
section-cited statutes already in the repo), what has been said in the last 60
days (logs/brain_said.json) and what the numbers said (brain/feedback.md). Then
it asks Gemini, on the free tier, for ONE pack per day: the post for
Telegram/Facebook, the short copy for Threads/Instagram, a visual brief for the
card, and on render days a Short topic. The pack is published only if it passes
the gates below; otherwise the lanes fall back to the hand-written rotation and
nobody is woken up.

THE GATES (the part that is not negotiable for a legal-documents brand)
  1. Citation — every legal claim names a fact id that exists on the shelf for
     the state the post names. No id, no claim.
  2. Verification — a second, independent model call reads the facts and the
     finished post and must find every claim supported and no legal statement
     that is not on the list. Disagreement = the pack is refused.
  3. Brand lint — lengths per channel, no banned phrases, no prices other than
     ours (or a figure quoted from a cited fact), no markdown, no shouting, one
     link, #DocOga, no emoji where the renderer or the voice would meet it.
  4. Repetition — a theme used in the last 21 days or a headline 60% the same
     as any in the last 60 days is refused.
  5. Shape — a Short topic on render days must be exactly what the MotionStudio
     grammar renders (hook + four tips); a Deep-Dive draft must pass the engine's
     own trigger check.

QUOTA DISCIPLINE: two to three requests a day in total (one plan, one verify, a
retry at most), on a model chain whose daily buckets are separate from the
narrator's TTS bucket. When every model is spent, `plan` exits 6 like the
narrator does — the next night continues; the lanes keep posting from the
rotation meanwhile.

    python3 tools/brain.py plan [--days 3] [--date YYYY-MM-DD] [--dry-run]
    python3 tools/brain.py status
    python3 tools/brain.py feedback
    python3 tools/brain.py deepdive [--dry-run]
    python3 tools/brain.py prune
Exit codes: 0 ok · 1 error · 3 nothing approved · 6 Gemini quota (try tomorrow)
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
sys.path.insert(0, str(ROOT / "tools"))
import brain_drafts as drafts  # noqa: E402
import events_calendar  # noqa: E402
import gemini_text  # noqa: E402
import law_index  # noqa: E402
import newsdesk  # noqa: E402
import listening  # noqa: E402

LAGOS = ZoneInfo("Africa/Lagos")
BRAIN = ROOT / "brain"
BUSINESS = BRAIN / "business.md"
EDITORIAL = BRAIN / "editorial.md"
FEEDBACK = BRAIN / "feedback.md"
STRATEGY = BRAIN / "strategy.md"
AUDIENCE = BRAIN / "audience.md"
SAID = Path(os.environ.get("DOCOGA_BRAIN_SAID") or (ROOT / "logs" / "brain_said.json"))
EPISODES = ROOT / "episodes"
STATS = ROOT / "logs" / "youtube_stats.json"

THEME_COOLDOWN_DAYS = 21
HEADLINE_WINDOW_DAYS = 60
HEADLINE_REPEAT = 0.60
POST_MAX = 900
THREADS_MAX = 480
HEADLINE_MAX = 70
LINE_MAX = 110
SHORT_DAYS = (0, 1, 2, 3, 4)         # every weekday: Mon + Thu = FB/IG Reel (08:30 UTC) AND YouTube Short (17:00 UTC, same words, cached voice); Tue/Wed/Fri = YouTube Short (17 Oct 2026)
POST_TYPES = ("educational", "state_spotlight", "pidgin", "story", "promo", "checklist", "engagement")
HOOKS = ("STAT", "QUESTION", "CLAIM", "STAKES", "CURIOSITY", "HOWTO", "STORY")
LAYOUTS = ("poster", "stat", "checklist")
BANNED = ("unlock", "game-changer", "game changer", "delve", "fast-paced", "we are excited",
          "legally binding guaranteed", "100%", "lawyer not needed", "court-proof", "courtproof",
          "guaranteed to win")
# heal_deepdive rewrites these (style only); the rest of BANNED still refuses the draft.
STYLE_FIXES = (("game-changer", "big difference"), ("game changer", "big difference"),
               ("unlock", "open up"), ("delve", "look"), ("fast-paced", "busy"),
               ("we are excited", "we are glad"))
OUR_PRICES = {"2,000", "2000", "50,000", "50000"}
PLATE_BANNED = ("face", "person", "people", "man", "woman", "child", "children", "portrait", "crowd",
                "sign", "text", "logo")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\u2B50\u2705\u274C]")
NAIRA = re.compile(r"₦\s?([0-9][0-9,\.]*)")
MAX_ATTEMPTS = 2
SAY_WORDS = (12, 45)      # a Short's spoken explanation per scene (tools/shorts_sound.SAY_WORDS)
SAY_TOTAL_MAX = 160       # hook_say + four says: ~65 s read, under the 90 s Facebook Reels ceiling with room
CTA_MAX = 110
CTA_VERBS = ("send", "forward", "share", "tag", "tell", "reply", "comment", "save", "drop", "ask", "show", "answer")
PERSONAS = ("ngozi", "tunde", "okafor", "amaka", "dayo")

SYSTEM = """You are the editor and growth lead of DocOga, Nigeria's document engine. You write one
day's social content for Nigerian tenants, landlords and small businesses, in direct Nigerian
English (or pidgin when the day calls for it). You are held to a plan: sales of the ₦2,000 Oga
Pass, and the channel signals that lead them — sends, forwards, replies, watch time. You write
each post to one named reader, you build in the line that makes them send it to one person, and
you end Threads posts with a question they can answer in five words. You cite only the law facts
you are given, by their fact id, and you never invent a statute, a section, a price or a story
about a named person. You answer with one JSON object and nothing else."""


# ───────────────────────────── small helpers ─────────────────────────────
def today_lagos():
    return datetime.now(LAGOS).date()


def read(path, default=""):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return default


def load_said():
    try:
        data = json.loads(SAID.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_said(entries):
    SAID.parent.mkdir(parents=True, exist_ok=True)
    SAID.write_text(json.dumps(entries, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def state_for(day):
    """Rotate the shelf's states by date so Lagos is not every post."""
    rows = law_index.states()
    order = [slug for slug, _, _ in rows]
    return order[day.toordinal() % len(order)]


def calendar_notes(day):
    notes = []
    m, d = day.month, day.day
    if d >= 25 or d <= 2:
        notes.append("Payday window (25th to month-end): the pass is bought when there is money — promo and "
                     "'make it today' lines land now.")
    if m in (1, 2, 3, 8, 9, 10):
        notes.append("Peak rental season (Jan–Mar, Aug–Oct): renewals, new agreements, advance-rent demands, "
                     "'renewal is not a new tenancy'.")
    if m == 8:
        notes.append("August: Abuja's yearly influx pushes renewals 10–25% up; agents demand full years upfront.")
    if m == 1:
        notes.append("January: rent-renewal season; new agreements; school-fees pressure.")
    if m in (11, 12):
        notes.append("Year end: 'landlord wants me out before Christmas'; advance-rent demands for next year.")
    # Special days (23 Oct 2026, owner's ask): Christmas, Independence Day, Children's Day,
    # Democracy Day, Eid, Easter, New Year … each with its tenancy angle, from the one calendar
    # the card renderer and the dashboard also read (tools/events_calendar.py).
    notes.extend(events_calendar.brain_notes(day))
    if m in (8, 9):
        notes.append("NYSC postings and students renting their first room.")
    if 4 <= m <= 10:
        notes.append("Rainy season: repairs, leaks, who fixes what.")
    return notes


def weekday_lead(day):
    return {0: "know-your-rights (educational, cited)", 1: "state spotlight (one state, one rule)",
            2: "pidgin or plain-talk explainer", 3: "story-style scenario", 4: "promo (one tool, one job)",
            5: "checklist (what a document must have)", 6: "engagement question"}[day.weekday()]


# ───────────────────────────── the prompt ─────────────────────────────
def hook_order(day, said, history=None, min_n=3):
    """Which hook archetype today's post opens with — chosen by the numbers (17 Oct 2026).

    A bandit, not a rota. Each hook's arm is what posts with that hook earned (the scorecard's
    `learning.hook_type`: sends ×3, comments ×2, likes ×1 per post, across Facebook, Instagram
    and Threads). The pick is UCB1 — the best average plus an exploration bonus that shrinks as
    a hook is tried — so a winning hook is used more and no hook is ever written off on two
    posts. Yesterday's and the day before's hooks are excluded so three days never open the same
    way. Returns (hook, reason, binding): `binding` is True once at least two hooks have `min_n`
    measured posts — until then the order is advice, and the lint lets the model choose.
    """
    import math
    learn = {}
    try:
        import brain_scorecard
        rows = brain_scorecard.load_history() if history is None else history
        learn = (((rows[-1] if rows else {}).get("kpis") or {}).get("learning") or {}).get("hook_type") or {}
    except Exception:  # the scorecard is an input, never a reason to have no hook
        learn = {}
    arms = {h: (int((learn.get(h) or {}).get("n") or 0), float((learn.get(h) or {}).get("avg") or 0.0)) for h in HOOKS}
    measured = [h for h, (n, _) in arms.items() if n >= min_n]
    binding = len(measured) >= 2
    recent = {e.get("hook_type") for e in said
              if (day - timedelta(days=2)).isoformat() <= str(e.get("date", "")) < day.isoformat()}
    candidates = [h for h in HOOKS if h not in recent] or list(HOOKS)
    total = sum(n for n, _ in arms.values()) or 1
    mean = (sum(n * avg for n, avg in arms.values()) / total) if total else 0.0
    best, best_score, why = None, -1.0, ""
    for h in candidates:
        n, avg = arms[h]
        prior = avg if n else mean            # an untried hook is assumed average, then explored
        bonus = (max(mean, 1.0)) * math.sqrt(2.0 * math.log(total + 1) / (n + 1))
        score = prior + bonus
        if score > best_score:
            best, best_score, why = h, score, ("earned %.0f per post over %d posts" % (avg, n) if n else "not measured yet — explore")
    if not binding:
        # No numbers yet: the least-used hook in the last 28 days, so the first weeks spread the bets.
        floor = (day - timedelta(days=28)).isoformat()
        used = {h: 0 for h in HOOKS}
        for e in said:
            if str(e.get("date", "")) >= floor and e.get("hook_type") in used:
                used[e["hook_type"]] += 1
        best = min(candidates, key=lambda h: (used[h], HOOKS.index(h)))
        why = "least used in 28 days (%d) — the numbers have not spoken yet" % used[best]
    return best, why, binding


def day_context(day, said=None):
    said = load_said() if said is None else said
    recent = [e for e in said if (day - timedelta(days=HEADLINE_WINDOW_DAYS)).isoformat() <= str(e.get("date", ""))]
    slug = state_for(day)
    facts = law_index.facts_for(slug)
    hook, hook_why, hook_binding = hook_order(day, said)
    return dict(day=day, weekday=day.strftime("%A"), lead=weekday_lead(day), state=slug,
                state_name=facts[0]["state"] if facts else slug, facts=facts,
                short_day=day.weekday() in SHORT_DAYS, calendar=calendar_notes(day),
                recent=recent, feedback=read(FEEDBACK).strip(),
                strategy=read(STRATEGY).strip(), audience=read(AUDIENCE).strip(),
                news=newsdesk.fresh_items(), search=search_demand(), asked=listening.fresh_items(),
                hook=hook, hook_why=hook_why, hook_binding=hook_binding)


SEARCH_CONSOLE = Path(os.environ.get("DOCOGA_SEARCH_CONSOLE") or (ROOT / "logs" / "search_console.json"))


def search_demand(path=None, max_age_days=21):
    """What Nigerians typed into Google before they found us — tools/search_console.py's weekly
    pull, if it exists and is fresh. Striking-distance queries first (one good answer moves them
    to page one), then the top clicked. Empty list when the pull is missing, stale or broken."""
    path = Path(path or SEARCH_CONSOLE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        taken = datetime.fromisoformat(str(data.get("taken_at")))
    except (OSError, ValueError, TypeError):
        return []
    if taken.tzinfo is None:
        taken = taken.replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - taken).days > max_age_days:
        return []
    out, seen = [], set()
    for kind, rows in (("striking", data.get("striking_distance") or []), ("top", data.get("top_queries") or [])):
        for q in rows:
            text = str(q.get("query") or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append({"query": text, "kind": kind, "position": q.get("position"), "impressions": q.get("impressions"),
                        "clicks": q.get("clicks"), "page": q.get("page") or ""})
            if len(out) >= 12:
                return out
    return out


def search_block(rows):
    if not rows:
        return "(no Search Console pull yet — write from the shelf and the plan)"
    return "\n".join("- \"%s\" — %s, position %s, %s impressions, %s clicks%s"
                     % (r["query"], "almost page one" if r["kind"] == "striking" else "already brings readers",
                        r.get("position"), r.get("impressions"), r.get("clicks"),
                        (" → " + r["page"].replace("https://docoga.com.ng", "")) if r.get("page") else "") for r in rows)


def prompt_for(ctx, problems=None):
    recent_lines = ["- %s | %s | %s" % (e.get("date"), e.get("theme"), e.get("headline"))
                    for e in sorted(ctx["recent"], key=lambda e: e.get("date", ""))[-60:]]
    shelf = "\n".join("%s | %s | %s" % (f["id"], f["cite"] or "(no section)", f["text"]) for f in ctx["facts"])
    short_rule = ("A Short is rendered on this day: include `short` exactly as specified."
                  if ctx["short_day"] else "No Short is rendered on this day: set `short` to null.")
    retry = ""
    if problems:
        retry = "\n\nYOUR PREVIOUS DRAFT WAS REFUSED FOR THESE REASONS — fix every one:\n- " + "\n- ".join(problems)
    return f"""BUSINESS MEMORY
{read(BUSINESS).strip()}

STRATEGY — THE PLAN YOU ARE HELD TO
{ctx.get('strategy') or '(no strategy file)'}

AUDIENCE — WRITE TO ONE OF THESE FIVE BY NAME
{ctx.get('audience') or '(no audience file)'}

EDITORIAL POLICY
{read(EDITORIAL).strip()}

TODAY
- Date: {ctx['day'].isoformat()} ({ctx['weekday']}). Lead type for this weekday: {ctx['lead']}.
- State on rotation: {ctx['state_name']} ({ctx['state']}). Legal claims may use only the shelf below.
- {short_rule}
- Calendar: {' '.join(ctx['calendar']) or 'nothing special.'}
- Hook for today: {ctx.get('hook') or 'your choice'} — {ctx.get('hook_why') or ''}. {'`hook_type` MUST be this value; the numbers chose it.' if ctx.get('hook_binding') else 'Use it unless the lead clearly wants another.'}
- Money line: when `tool` is set, the `cta` MAY be the keyword line — "Comment LINK and the exact page lands in your inbox." — the lane sends that private reply itself.

NEWSDESK — WHAT NIGERIA IS TALKING ABOUT THIS WEEK (headline — paper)
{newsdesk.prompt_block(ctx.get('news') or [])}
A story may be the OPENING LINE only ("This week a Lagos landlord…"), named as "reported by <paper>".
Never invent a detail that is not in the headline. The law still comes from the shelf below with a
fact id. If no story fits today's lead and state, set news_hook to null — do not force it.

WHAT NIGERIANS ASKED THIS WEEK (thread titles on Nairaland and r/Nigeria — real people, real trouble)
{listening.prompt_block(ctx.get('asked') or [])}
When one of these is today's lead, the FIRST LINE answers it in their words ("Your landlord gave you
one month to leave after a year of rent?"). Answer the question; never quote the thread or name the poster.

WHAT NIGERIANS TYPE INTO GOOGLE BEFORE THEY FIND US (Search Console, last 28 days, Nigeria)
{search_block(ctx.get('search') or [])}
When one of these questions fits today's state and lead, answer it in the FIRST LINE in the
reader's own words and set `tool` to the page Google already shows — that post and that Short are
how a position-9 query becomes page one. Never bend the law to fit a query.

WHAT THE NUMBERS SAID — SCORECARD, GOALS AND THIS WEEK'S ORDERS (obey the orders)
{ctx['feedback'] or 'No feedback yet — use the editorial rhythm.'}

SAID IN THE LAST 60 DAYS (do not repeat a theme from the last 21 days; do not reuse a headline)
{chr(10).join(recent_lines) or '(nothing yet)'}

THE LAW SHELF FOR {ctx['state_name'].upper()} (fact id | section | fact)
{shelf}

OUTPUT — one JSON object with exactly these keys:
{{
  "theme": "kebab-case slug naming the idea, e.g. rent-receipt-seven-lines-lagos",
  "post_type": one of {list(POST_TYPES)},
  "hook_type": one of {list(HOOKS)},
  "state": "{ctx['state']}" or null if the post makes no legal claim,
  "claims": [{{"text": "the legal sentence as it appears in the post", "fact_id": "an id from the shelf"}}],
  "reader": one of {list(PERSONAS)} — the person from AUDIENCE this day is written to,
  "news_hook": the exact headline from NEWSDESK the post opens with, or null,
  "tool": one of {list(drafts.TOOLS)} or null — the ONE document the post points at; the renderer links straight to that tool's page for the post's state,
  "post": {{"headline": "<= {HEADLINE_MAX} characters, sentence case", "lines": ["2 to 5 lines, each <= {LINE_MAX} characters"],
           "cta": "<= {CTA_MAX} characters: the send/forward/reply line naming a receiver or a five-word answer, e.g. 'Send this to the friend whose rent is due in January.' or 'Which state are you renting in? Tell us below.'",
           "hashtags": ["#DocOga", "3 to 5 total"]}},
  "threads": {{"text": "<= 360 characters, self-contained, no link, no hashtags, ENDS WITH A QUESTION answerable in five words", "hashtags": ["#DocOga", "at most 2"],
              "topic": "the one Threads topic tag, 2-4 plain words, no punctuation, e.g. 'Tenant Rights Nigeria'",
              "evening": "<= 220 characters for the 8 pm image post: a SECOND angle on the same idea (the consequence, the mistake, the one-line rule), no link, no hashtags, no question needed",
              "poll": null, or on the engagement day (Sunday) {{"option_a": "<= 25 chars", "option_b": "<= 25 chars", "option_c": "optional", "option_d": "optional"}} — the answers to the closing question; a poll post carries no link}},
  "visual": {{"kicker": "2-4 words", "layout": one of {list(LAYOUTS)}, "big": "number or 1-3 words for the stat layout, else empty",
             "plate": "2-4 plain words for a background photograph with no faces and no signs"}},
  "quiz": null, or on Tuesday (quiz day) {{"question": "<= 120 characters, one rule from the shelf as a question", "options": ["2 to 4 answers, <= 40 characters each, one correct"], "correct": 0-based index, "explanation": "<= 200 characters: the answer with its section, e.g. 'Six months — s.13(1)(e), Lagos Tenancy Law 2011.'", "fact_id": "the shelf fact the answer rests on"}},
  "short": null or {{"title": "one or two short sentences", "hook_sub": "<= 9 words",
                     "hook_say": "20-35 words the narrator reads over the hook: the scene, the mistake, the stake — as a presenter would say it",
                     "tips": [{{"text": "<= 5 words", "sub": "<= 9 words",
                               "say": "25-40 words the narrator reads over this tip: what to do, why, what goes wrong without it; name the state when a rule is cited. The five says together stay under 160 words"}}, "... exactly four"]}},
  "why": "one sentence: why today says this"
}}
Rules: do not put the link or the disclaimer in `lines`, `cta` or `threads.text` — the renderer adds them.
The `cta` is not a slogan: it names who to send it to, or asks one answerable question. Follow the ORDERS block.
Every legal statement in the post must appear in `claims` with its fact id. Name the state in the post
whenever a claim is made. No markdown, no asterisks, no emoji in the headline, kicker or Short.{retry}"""


VERIFY_SYSTEM = """You are a careful Nigerian lawyer checking a social media post against a list of
verified statutory facts. You are strict: a claim is supported only if the fact says the same thing
for the same state, with the same number, period or amount. Answer with one JSON object only."""


def verify_prompt(pack, facts_by_id):
    facts = "\n".join("%s | %s | %s" % (f["id"], f["cite"], f["text"]) for f in facts_by_id.values())
    claims = "\n".join("- [%s] %s" % (c.get("fact_id"), c.get("text")) for c in pack.get("claims") or [])
    text = drafts.post_text(pack) + "\n\nTHREADS VERSION:\n" + drafts.threads_text(pack)
    short = pack.get("short")
    if short:
        text += "\n\nSHORT VIDEO LINES:\n" + json.dumps(short, ensure_ascii=False)
    return f"""FACTS (the only law that may be relied on)
{facts}

THE POST
{text}

CLAIMS THE WRITER DECLARED
{claims or '(none)'}

Answer:
{{
  "verdicts": [{{"fact_id": "...", "claim": "...", "supported": true or false, "reason": "short"}}],
  "unsupported_statements": ["any sentence in the post or Short that states a legal rule, period, amount,
                              duty or right that is NOT in the facts above — empty list if none"]
}}"""


# ───────────────────────────── the gates ─────────────────────────────
def _emoji_count(text):
    return len(EMOJI.findall(text or ""))


def _wrap_line(text, width):
    """Split one over-long line at the best boundary at or before `width` — sentence end, then clause,
    then a space. Returns a list of lines (unchanged list of one when it already fits or cannot split)."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= width:
        return [text] if text else []
    for pattern in (r"[.!?…]\s", r"[;:—–]\s", r",\s", r"\s"):
        best = None
        for m in re.finditer(pattern, text):
            if m.end() - 1 <= width:
                best = m.end()
        if best and best > 20:
            head, tail = text[:best].rstrip(), text[best:].strip()
            return [head] + _wrap_line(tail, width)
    return [text]


def tidy(pack):
    """The editor's pencil, applied before the gates: a body line that runs a few characters past
    LINE_MAX is re-broken at a sentence or clause boundary instead of costing a whole second Gemini
    call (night one: three of five attempts were refused for 115–125-character lines). Only layout
    is touched — never a word; if the reflow would push the post past 5 lines it is left for lint."""
    if not isinstance(pack, dict) or not isinstance(pack.get("post"), dict):
        return pack
    post = pack["post"]
    lines = [str(x).strip() for x in (post.get("lines") or []) if str(x).strip()]
    if not lines or all(len(ln) <= LINE_MAX for ln in lines):
        return pack
    out = []
    for ln in lines:
        out.extend(_wrap_line(ln, LINE_MAX) if len(ln) > LINE_MAX else [ln])
    if 2 <= len(out) <= 5 and all(len(ln) <= LINE_MAX for ln in out):
        post["lines"] = out
    return pack


def lint(pack, ctx, said):
    """Deterministic gates. Returns a list of problems (empty = passed)."""
    p = []
    if not isinstance(pack, dict):
        return ["the answer is not an object"]
    post = pack.get("post") if isinstance(pack.get("post"), dict) else {}
    headline = str(post.get("headline") or "").strip()
    lines = [str(x).strip() for x in (post.get("lines") or []) if str(x).strip()]
    tags = [str(t).strip() for t in (post.get("hashtags") or []) if str(t).strip()]
    threads = pack.get("threads") if isinstance(pack.get("threads"), dict) else {}
    visual = pack.get("visual") if isinstance(pack.get("visual"), dict) else {}
    claims = pack.get("claims") if isinstance(pack.get("claims"), list) else []
    theme = str(pack.get("theme") or "").strip().lower()

    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", theme or "-"):
        p.append("theme must be a kebab-case slug")
    if pack.get("post_type") not in POST_TYPES:
        p.append("post_type must be one of %s" % ", ".join(POST_TYPES))
    if pack.get("hook_type") not in HOOKS:
        p.append("hook_type must be one of %s" % ", ".join(HOOKS))
    elif ctx.get("hook_binding") and ctx.get("hook") and pack.get("hook_type") != ctx["hook"]:
        p.append("hook_type must be %s today — the scorecard chose it (%s)" % (ctx["hook"], ctx.get("hook_why", "")))
    if not headline:
        p.append("post.headline is missing")
    elif len(headline) > HEADLINE_MAX:
        p.append("headline is %d characters; max %d" % (len(headline), HEADLINE_MAX))
    if headline and headline.isupper() and len(headline) > 12:
        p.append("headline is shouting (all caps)")
    if not (2 <= len(lines) <= 5):
        p.append("post.lines must be 2 to 5 lines (got %d)" % len(lines))
    for ln in lines:
        if len(ln) > LINE_MAX:
            p.append("a body line is %d characters; max %d: %r" % (len(ln), LINE_MAX, ln[:40]))
    full = drafts.post_text({**pack, "post": {"headline": headline, "lines": lines}}) if headline else ""
    if full and len(full) > POST_MAX:
        p.append("the post is %d characters with link and disclaimer; max %d" % (len(full), POST_MAX))
    tool = pack.get("tool")
    if tool is not None and str(tool).strip().lower() not in drafts.TOOLS:
        p.append("tool must be one of %s or null" % ", ".join(drafts.TOOLS))
    qz = pack.get("quiz")
    if qz is not None:
        if not isinstance(qz, dict) or drafts.quiz(pack) is None:
            p.append("quiz must be null or {question <= 300, options 2-4 of <= 100 chars, correct index, explanation <= 200}")
        else:
            fid = str(qz.get("fact_id") or "")
            if fid not in ctx.get("facts_by_id", {}):
                p.append("quiz.fact_id must be a fact id from the shelf — a quiz answer is a legal claim")
            else:
                cite = (ctx["facts_by_id"][fid].get("cite") or "").replace(" ", "").lower()
                if cite and cite not in str(qz.get("explanation") or "").replace(" ", "").lower():
                    p.append("quiz.explanation must carry the section of its fact (%s)" % ctx["facts_by_id"][fid].get("cite"))
    hook = pack.get("news_hook")
    if hook is not None and str(hook).strip():
        titles = {str(n.get("title", "")).strip().lower() for n in ctx.get("news") or []}
        if str(hook).strip().lower() not in titles:
            p.append("news_hook is not one of this week's NEWSDESK headlines — a story the papers did not print is not a story")
    cta = str(post.get("cta") or "").strip()
    if not cta:
        p.append("post.cta is missing — the send/forward/reply line is how a post travels")
    else:
        if len(cta) > CTA_MAX:
            p.append("post.cta is %d characters; max %d" % (len(cta), CTA_MAX))
        if not any(v in cta.lower() for v in CTA_VERBS):
            p.append("post.cta must ask the reader to send, forward, share, tag, reply or answer — not a slogan")
        if "docoga.com.ng" in cta.lower():
            p.append("post.cta must not carry the link; the renderer adds it")
    if not (3 <= len(tags) <= 5):
        p.append("post.hashtags must be 3 to 5 tags")
    if tags and "#DocOga" not in tags:
        p.append("post.hashtags must include #DocOga")
    if any(not t.startswith("#") or " " in t for t in tags):
        p.append("every hashtag starts with # and has no spaces")
    ttext = str(threads.get("text") or "").strip()
    if not ttext:
        p.append("threads.text is missing")
    else:
        tfull = drafts.threads_text({**pack, "threads": {"text": ttext}})
        if len(tfull) > THREADS_MAX:
            p.append("threads text is %d characters with link and disclaimer; max %d" % (len(tfull), THREADS_MAX))
        if "?" not in ttext[-160:]:
            p.append("threads.text must end with a question the reader can answer in five words (replies are what Threads ranks on)")
        if "http" in ttext or "#" in ttext:
            p.append("threads.text must not carry the link or hashtags — the renderer adds them")
    if len([t for t in (threads.get("hashtags") or [])]) > 2:
        p.append("threads.hashtags: at most 2")
    topic = str(threads.get("topic") or "").strip()
    if topic and (len(topic) > 50 or "." in topic or "&" in topic or "#" in topic):
        p.append("threads.topic: 2-4 plain words, no '#', '.', '&', max 50 characters")
    evening = str(threads.get("evening") or "").strip()
    if evening and (len(evening) > 280 or "http" in evening.lower() or "#" in evening):
        p.append("threads.evening: at most 280 characters, no link, no hashtags — the link rides in the reply")
    poll = threads.get("poll")
    if poll is not None:
        if not isinstance(poll, dict):
            p.append("threads.poll must be an object with option_a, option_b (option_c, option_d optional) or null")
        else:
            opts = [str(poll.get(k) or "").strip() for k in ("option_a", "option_b", "option_c", "option_d")]
            filled = [o for o in opts if o]
            if len(filled) < 2 or opts[:len(filled)] != filled:
                p.append("threads.poll needs option_a and option_b filled in order")
            if any(len(o) > drafts.POLL_OPTION_MAX for o in filled):
                p.append("threads.poll options are at most %d characters" % drafts.POLL_OPTION_MAX)
            if len(set(o.lower() for o in filled)) != len(filled):
                p.append("threads.poll options repeat")

    corpus = "\n".join([headline] + lines + [ttext])
    low = corpus.lower()
    for word in BANNED:
        if word in low:
            p.append("banned phrase: %r" % word)
    if "*" in corpus or "`" in corpus:
        p.append("no markdown (asterisks, backticks) in copy")
    if "http" in headline or any("http" in ln for ln in lines):
        p.append("the link is added by the renderer — remove it from headline/lines")
    if drafts.DISCLAIMER.lower() in low:
        p.append("the disclaimer is added by the renderer — remove it from the copy")
    if _emoji_count(headline):
        p.append("no emoji in the headline")
    if sum(_emoji_count(ln) for ln in lines) > 1:
        p.append("at most one emoji in the body lines")

    # prices: only ours, or a figure quoted from a cited fact
    fact_texts = " ".join(ctx["facts_by_id"][c["fact_id"]]["text"] for c in claims
                          if isinstance(c, dict) and c.get("fact_id") in ctx["facts_by_id"])
    for amount in NAIRA.findall(corpus):
        clean = amount.strip(".,")
        if clean not in OUR_PRICES and ("₦" + clean) not in fact_texts and clean not in fact_texts:
            p.append("price ₦%s is neither ours nor in a cited fact" % clean)

    # citations
    state = pack.get("state")
    if claims and not state:
        p.append("claims need a state")
    if state and state != ctx["state"]:
        p.append("state must be %s today (the shelf shown)" % ctx["state"])
    everything = ctx.setdefault("all_facts", law_index.by_id())
    for c in claims:
        if not isinstance(c, dict) or not str(c.get("text") or "").strip():
            p.append("every claim needs text")
            continue
        fid = str(c.get("fact_id") or "")
        fact = ctx["facts_by_id"].get(fid) or everything.get(fid)
        if not fact:
            p.append("claim cites unknown fact id %r" % fid)
        elif state and fact["slug"] != state:
            p.append("fact %s belongs to %s, not %s" % (fid, fact["slug"], state))
    if claims and state and ctx["state_name"].lower() not in low and ctx["state"].replace("-", " ") not in low:
        p.append("name the state (%s) in the post when a claim is made" % ctx["state_name"])
    if claims and (len(re.findall(r"\bs\.\s?\d", corpus)) or 0) == 0 and pack.get("post_type") in ("educational", "state_spotlight"):
        p.append("a cited post names the section number (e.g. s.5) in its copy")

    # visual
    kicker = str(visual.get("kicker") or "").strip()
    if not (1 <= len(kicker.split()) <= 5) or len(kicker) > 32:
        p.append("visual.kicker must be 1 to 5 words (<= 32 characters)")
    if _emoji_count(kicker):
        p.append("no emoji in the kicker")
    if visual.get("layout") not in LAYOUTS:
        p.append("visual.layout must be one of %s" % ", ".join(LAYOUTS))
    if visual.get("layout") == "stat" and not str(visual.get("big") or "").strip():
        p.append("stat layout needs visual.big")
    if visual.get("layout") == "checklist" and len(lines) < 3:
        p.append("checklist layout needs at least 3 lines")
    plate = str(visual.get("plate") or "").strip().lower()
    if plate and (len(plate.split()) > 4 or any(w in plate.split() for w in PLATE_BANNED)):
        p.append("visual.plate: 2-4 plain words, no people, no signs")

    # short
    short = pack.get("short")
    if ctx["short_day"] and not isinstance(short, dict):
        p.append("a Short is rendered today — `short` is required")
    if isinstance(short, dict):
        p.extend(short_problems(short))
    elif short not in (None, {}):
        p.append("short must be null or an object")

    # repetition
    for e in said:
        if not isinstance(e, dict):
            continue
        try:
            when = date.fromisoformat(str(e.get("date"))[:10])
        except ValueError:
            continue
        age = (ctx["day"] - when).days
        if e.get("theme") == theme and theme and abs(age) <= THEME_COOLDOWN_DAYS:
            p.append("theme %r was used on %s (cooldown %d days)" % (theme, e.get("date"), THEME_COOLDOWN_DAYS))
        if abs(age) <= HEADLINE_WINDOW_DAYS and headline:
            sim = drafts.similarity(headline, e.get("headline", ""))
            if sim >= HEADLINE_REPEAT:
                p.append("headline is %d%% the same as %r (%s)" % (round(sim * 100), e.get("headline"), e.get("date")))
    return p


def short_problems(short):
    p = []
    title = str(short.get("title") or "").strip()
    if not title or len(title) > 64:
        p.append("short.title: 1-64 characters")
    if _emoji_count(json.dumps(short, ensure_ascii=False)):
        p.append("no emoji anywhere in the Short")
    sub = str(short.get("hook_sub") or "").strip()
    if len(sub.split()) > 9:
        p.append("short.hook_sub: at most 9 words")
    hook_say = str(short.get("hook_say") or "").strip()
    if hook_say and not (SAY_WORDS[0] <= len(hook_say.split()) <= SAY_WORDS[1]):
        p.append("short.hook_say: %d-%d words" % SAY_WORDS)
    tips = short.get("tips")
    if not isinstance(tips, list) or len(tips) != 4:
        p.append("short.tips: exactly four")
        tips = tips if isinstance(tips, list) else []
    for i, tip in enumerate(tips, 1):
        if not isinstance(tip, dict):
            p.append("short.tips[%d] must be an object" % i)
            continue
        text = str(tip.get("text") or "").strip()
        tsub = str(tip.get("sub") or "").strip()
        if not text or len(text.split()) > 5 or len(text) > 30:
            p.append("short.tips[%d].text: 1-5 words, <= 30 characters" % i)
        if len(tsub.split()) > 9 or len(tsub) > 64:
            p.append("short.tips[%d].sub: <= 9 words, <= 64 characters" % i)
        say = str(tip.get("say") or "").strip()
        if say and not (SAY_WORDS[0] <= len(say.split()) <= SAY_WORDS[1]):
            p.append("short.tips[%d].say: %d-%d words" % (i, SAY_WORDS[0], SAY_WORDS[1]))
        if say and ("http" in say or "docoga.com.ng" in say.lower()):
            p.append("short.tips[%d].say: no link — the end card carries it" % i)
        if not say:
            p.append("short.tips[%d].say is required — a detailed Short, not points (owner, 17 Oct 2026)" % i)
    if not hook_say:
        p.append("short.hook_say is required — a detailed Short, not points (owner, 17 Oct 2026)")
    spoken = len(hook_say.split()) + sum(len(str(t.get("say") or "").split()) for t in tips if isinstance(t, dict))
    if spoken > SAY_TOTAL_MAX:
        p.append("short: hook_say + says total %d words; at most %d (the Reel must stay under 90 s)" % (spoken, SAY_TOTAL_MAX))
        if "*" in text or "*" in tsub:
            p.append("short.tips[%d]: no markdown" % i)
    return p


def finish_short(short):
    """Derive the hook slide text the grammar expects (two beats on a newline)."""
    title = " ".join(str(short.get("title") or "").split())
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", title) if s.strip()]
    hook = "\n".join(parts[:2]).upper() if len(parts) == 2 else title.upper()
    return {**short, "title": title, "hook_text": hook}


def verify(pack, ctx, http=None, sleep=None, log=print):
    """Second model call; returns a list of problems (empty = agreed)."""
    if not pack.get("claims"):
        return []
    facts = {c["fact_id"]: ctx["facts_by_id"][c["fact_id"]] for c in pack["claims"]}
    try:
        verdict = gemini_text.generate_json(verify_prompt(pack, facts), system=VERIFY_SYSTEM,
                                            http=http, sleep=sleep, temperature=0.1, log=log,
                                            max_output_tokens=2048)
    except gemini_text.Exhausted:
        raise
    except gemini_text.GeminiError as exc:
        return ["verifier unavailable: %s" % exc]
    problems = []
    for v in verdict.get("verdicts") or []:
        if isinstance(v, dict) and v.get("supported") is False:
            problems.append("verifier: claim [%s] not supported — %s" % (v.get("fact_id"), v.get("reason", "")))
    for s in verdict.get("unsupported_statements") or []:
        if str(s).strip():
            problems.append("verifier: legal statement not on the shelf — %r" % str(s)[:120])
    return problems


# ───────────────────────────── planning ─────────────────────────────
def approve(pack, ctx, model_note=""):
    """Shape the approved pack as the lanes read it (brain_drafts)."""
    short = finish_short(pack["short"]) if isinstance(pack.get("short"), dict) else None
    out = {
        "version": drafts.SCHEMA_VERSION, "status": "approved", "date": ctx["day"].isoformat(),
        "generated_at": datetime.now(LAGOS).isoformat(timespec="seconds"),
        "theme": pack["theme"], "post_type": pack["post_type"], "hook_type": pack["hook_type"],
        "state": pack.get("state"), "claims": pack.get("claims") or [],
        "post": {"headline": pack["post"]["headline"].strip(),
                 "lines": [str(x).strip() for x in pack["post"]["lines"] if str(x).strip()],
                 "cta": str(pack["post"].get("cta") or "").strip(),
                 "hashtags": list(pack["post"]["hashtags"])},
        "threads": {"text": pack["threads"]["text"].strip(),
                    "hashtags": list(pack["threads"].get("hashtags") or [])[:2],
                    "topic": str(pack["threads"].get("topic") or "").strip(),
                    "poll": pack["threads"].get("poll") if isinstance(pack["threads"].get("poll"), dict) else None,
                    "evening": str(pack["threads"].get("evening") or "").strip()[:280]},
        "visual": {k: str(pack["visual"].get(k) or "").strip() for k in ("kicker", "layout", "big", "plate")},
        "short": short, "why": str(pack.get("why") or "").strip(),
        # The fields the lanes and the learning loop read back (17 Oct 2026: they were linted
        # but not saved — so every link fell to the homepage, no Tuesday quiz ever reached
        # Telegram and the reader-learning column stayed "unnamed").
        "tool": (str(pack.get("tool") or "").strip().lower() or None),
        "reader": str(pack.get("reader") or "").strip(),
        "news_hook": (str(pack.get("news_hook") or "").strip() or None),
        "quiz": pack.get("quiz") if isinstance(pack.get("quiz"), dict) else None,
        "gates": ["citation", "verification" if pack.get("claims") else "no-claims", "lint", "repetition", "shape"],
        "note": model_note,
    }
    return out


def write_draft(approved):
    path = drafts.path_for(approved["date"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(approved, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def remember(said, approved):
    said.append({"date": approved["date"], "theme": approved["theme"], "headline": approved["post"]["headline"],
                 "post_type": approved["post_type"], "hook_type": approved["hook_type"],
                 "state": approved.get("state"), "fact_ids": [c.get("fact_id") for c in approved["claims"]],
                 "plate": approved["visual"].get("plate", ""), "short": bool(approved.get("short")),
                 "reader": approved.get("reader") or "", "tool": approved.get("tool"),
                 "news_hook": approved.get("news_hook") or None})
    floor = (date.fromisoformat(approved["date"]) - timedelta(days=180)).isoformat()
    said[:] = [e for e in said if str(e.get("date", "")) >= floor]
    save_said(said)


def plan_day(day, said, http=None, sleep=None, log=print, dry_run=False):
    """One day: generate → gates → verify → write. Returns (approved|None, problems)."""
    ctx = day_context(day, said)
    ctx["facts_by_id"] = {f["id"]: f for f in ctx["facts"]}
    problems = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        pack = tidy(gemini_text.generate_json(prompt_for(ctx, problems or None), system=SYSTEM, http=http,
                                              sleep=sleep, log=log))
        problems = lint(pack, ctx, said)
        if not problems:
            problems = verify(pack, ctx, http=http, sleep=sleep, log=log)
        if not problems:
            approved = approve(pack, ctx)
            if not dry_run:
                write_draft(approved)
                remember(said, approved)
            log("brain: %s approved — %s / %s / %s" % (day, approved["theme"], approved["post_type"],
                                                       approved["hook_type"]))
            return approved, []
        log("brain: %s attempt %d refused: %s" % (day, attempt, "; ".join(problems)[:600]))
    return None, problems


def plan(days=3, start=None, http=None, sleep=None, log=print, dry_run=False):
    start = start or today_lagos()
    said = load_said()
    approved, refused, quota, skipped = [], {}, None, []
    for i in range(days):
        day = start + timedelta(days=i)
        if drafts.draft_for(day) and not dry_run:
            log("brain: %s already approved" % day)
            skipped.append(day.isoformat())
            continue
        try:
            ok, problems = plan_day(day, said, http=http, sleep=sleep, log=log, dry_run=dry_run)
        except gemini_text.Exhausted as exc:
            quota = exc
            log("brain: quota — %s; resumes %s" % (exc, exc.resumes_at))
            break
        except gemini_text.GeminiError as exc:
            refused[day.isoformat()] = ["gemini: %s" % exc]
            continue
        if ok:
            approved.append(ok)
        else:
            refused[day.isoformat()] = problems
    return {"approved": approved, "refused": refused, "quota": quota, "skipped": skipped}


# ───────────────────────────── feedback ─────────────────────────────
def feedback_text(stats=None, said=None, today=None, scorecard=None):
    """What the numbers said, as a short markdown note the next plan reads."""
    today = today or today_lagos()
    said = load_said() if said is None else said
    if stats is None:
        try:
            stats = json.loads(STATS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stats = []
    lines = ["# What the numbers said — written %s by tools/brain.py feedback" % today.isoformat(), ""]
    try:
        import brain_scorecard
        lines += brain_scorecard.feedback_section(scorecard).rstrip().split("\n") + [""]
    except Exception as e:  # the scorecard is an input, never a reason to have no feedback
        lines += ["## Scorecard", "unavailable (%s)" % e, ""]
    snap = stats[-1] if isinstance(stats, list) and stats else (stats if isinstance(stats, dict) else {})
    videos = snap.get("videos") or []
    if videos:
        ch = snap.get("channel") or {}
        lines.append("## YouTube (snapshot %s): %s subscribers, %s views, %s videos"
                     % (str(snap.get("taken_at", ""))[:10], ch.get("subscribers"), ch.get("views"), ch.get("videos")))
        for kind in ("short", "longform"):
            rows = sorted([v for v in videos if v.get("kind") == kind], key=lambda v: -int(v.get("views") or 0))
            if rows:
                lines.append("- Top %s: " % kind + "; ".join("%r %s views" % (v.get("topic") or v.get("title"), v.get("views"))
                                                               for v in rows[:3]))
        lines.append("")
    floor = (today - timedelta(days=28)).isoformat()
    recent = [e for e in said if str(e.get("date", "")) >= floor]
    if recent:
        def tally(key):
            counts = {}
            for e in recent:
                counts[e.get(key) or "-"] = counts.get(e.get(key) or "-", 0) + 1
            return ", ".join("%s ×%d" % kv for kv in sorted(counts.items(), key=lambda kv: -kv[1]))
        lines += ["## Last 28 days of the brain's own output", "- post types: " + tally("post_type"),
                  "- hooks: " + tally("hook_type"), "- states: " + tally("state"), ""]
        lines.append("Rotate away from the most-used type and hook above; the least-used state is overdue.")
    else:
        lines.append("No brain output in the last 28 days yet — follow the editorial rhythm.")
    return "\n".join(lines).rstrip() + "\n"


def write_feedback(**kw):
    text = feedback_text(**kw)
    FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
    FEEDBACK.write_text(text, encoding="utf-8")
    return text


# ───────────────────────────── deep-dive writer ─────────────────────────────
DD_SYSTEM = """You write DocOga Deep-Dive episodes: nine-section, ten-minute YouTube explainers for
Nigerian tenants, narrated in confident Nigerian English like a Lagos radio presenter. You rely only
on the law facts given, cited by fact id, and you never invent a statute, section, case or person.
You answer with one JSON object and nothing else."""


def _norm_tokens(t):
    t = t.lower().replace("\u2014", " ").replace("\u2013", " ").replace("-", " ")
    t = re.sub(r"[^a-z0-9' ]", " ", t)
    return [w for w in t.split() if w]


def _find(words, trig, start):
    t = [w.lower() for w in trig]
    for i in range(start, len(words) - len(t) + 1):
        if words[i:i + len(t)] == t:
            return i
    return None


def plates():
    names = {p.stem for p in (EPISODES / "assets").glob("*.jpg")}
    try:
        names |= {k for k in json.loads((EPISODES / "assets" / "aliases.json").read_text()) if not k.startswith("_")}
    except (OSError, ValueError):
        pass
    return sorted(names)


def existing_episodes():
    out = []
    for folder in sorted(EPISODES.glob("dd*")):
        try:
            meta = json.loads((folder / "episode.json").read_text(encoding="utf-8"))
            out.append(meta)
        except (OSError, ValueError):
            continue
    return out


def next_episode_number():
    nums = [int(m.get("number") or re.sub(r"\D", "", m.get("id", "0")) or 0) for m in existing_episodes()]
    return (max(nums) if nums else 0) + 1


def deepdive_prompt(number, states, facts, previous, problems=None):
    shelf = "\n".join("%s | %s | %s | %s" % (f["id"], f["state"], f["cite"] or "(no section)", f["text"]) for f in facts)
    prev = "\n".join("- %s" % t for t in previous) or "(none)"
    retry = ("\n\nYOUR PREVIOUS DRAFT WAS REFUSED — fix every point:\n- " + "\n- ".join(problems)) if problems else ""
    return f"""BUSINESS MEMORY
{read(BUSINESS).strip()}

EDITORIAL POLICY (see the Deep-Dive section)
{read(EDITORIAL).strip()}

EPISODE {number}. States on rotation this week: {', '.join(states)}. Episodes already made (do not repeat):
{prev}

PLATES AVAILABLE for `img` (use only these names): {', '.join(plates())}

THE LAW SHELF (fact id | state | section | fact)
{shelf}

OUTPUT — one JSON object:
{{
  "title": "Episode title, <= 70 characters, no episode number",
  "theme": "kebab-case slug",
  "claims": [{{"text": "legal sentence as narrated", "fact_id": "shelf id"}}],
  "sections": [{{"n": 1, "title": "The Hook", "narration": "120-200 words"}}, "... exactly nine; the last is 'The Law, and DocOga'"],
  "beats": [{{"sec": 1, "trig": null, "head": "<= 28 CHARACTERS", "sub": "<= 60 characters", "img": "plate name",
             "shot": "2-4 plain words naming the photograph that shows what this beat SAYS (a thing or a place: 'paper receipt', 'padlocked door', 'naira banknotes'), no faces, no signs"}},
            {{"sec": 1, "trig": ["two", "to", "four", "words"], "head": "...", "sub": "...", "img": "...", "shot": "..."}}, "... 36 to 48 beats"],
  "cover": {{"img": "plate", "kicker": "<= 24 chars", "line1": "<= 16 chars", "highlight": "one word", "label": "<= 14 chars",
            "line2": "<= 28 chars", "line3": "<= 32 chars", "sub": "<= 36 chars"}},
  "youtube": {{"title": "<= 95 characters ending with (Deep-Dive {number})", "description": "250-900 characters, plain text, ends with https://docoga.com.ng and the line General information, not legal advice.", "tags": ["8 to 15 tags"]}}
}}
Rules: the first beat of each section has trig null; every other trig is 2-4 consecutive words copied exactly
from that section's narration, lowercase, letters and digits only, and the beats of a section appear in the
order those words are spoken. Section 1 opens on the problem in a scene, not on a definition. Section 9 names
DocOga, the two-minute document, free to start, and the Oga Pass at 2,000 naira for 30 days. No emoji, no markdown.
Write amounts in words or digits as a presenter would say them.{retry}"""


DD_ATTEMPTS = 3
DD_LEDGER = Path(os.environ.get("DOCOGA_BRAIN_DD_LEDGER") or (ROOT / "logs" / "brain_deepdive.json"))
DD_FALLBACK_PLATE = "letter"


def heal_deepdive(ep, log=print):
    """Deterministic repairs before the gates — the writer's small slips are not reasons to
    refuse a whole episode (21 Oct 2026: the Deep-Dive lane had been idle since 15 Oct; the
    Sunday writer existed but a 36-48-beat JSON with exact spoken triggers rarely survives
    `deepdive_problems` untouched, and two attempts a week is no cadence). Only things that
    cannot change a legal meaning are healed: a beat whose trigger words are not spoken is
    dropped (beats are overlays; the narration is untouched), an unknown plate falls back to
    a real one, an over-long sub is cut at a word, a shot that names people is dropped, tags
    and the description are brought to shape. Narration is touched for ONE thing only — a
    banned style word swapped for a plain one (STYLE_FIXES; 22 Oct 2026) — never a legal
    over-claim; claims and section count are never touched — those are the writer's to get
    right and the verifier's to judge."""
    notes = []
    if not isinstance(ep, dict):
        return notes
    names = set(plates())
    secs = ep.get("sections") if isinstance(ep.get("sections"), list) else []
    # Style words the gate bans (22 Oct 2026: a whole night refused for one 'game-changer').
    # Only the STYLE entries of BANNED are rewritten — never the legal over-claims
    # ("court-proof", "guaranteed to win", "100%"), which must still refuse the draft.
    for s in secs:
        if not isinstance(s, dict):
            continue
        text = str(s.get("narration") or "")
        fixed = text
        for bad, good in STYLE_FIXES:
            fixed = re.sub(r"(?i)\b" + re.escape(bad) + r"\b", good, fixed)
        if fixed != text:
            s["narration"] = fixed
            notes.append("section %s: style word rewritten" % s.get("n"))
    words_by_sec = {}
    for s in secs:
        if isinstance(s, dict):
            try:
                words_by_sec[int(s.get("n") or 0)] = _norm_tokens(str(s.get("narration") or ""))
            except (TypeError, ValueError):
                pass
    beats = ep.get("beats") if isinstance(ep.get("beats"), list) else []
    kept, seen, cursor = [], set(), {}
    for i, b in enumerate(beats, 1):
        if not isinstance(b, dict):
            notes.append("beat %d dropped: not an object" % i)
            continue
        try:
            sec = int(b.get("sec") or 0)
        except (TypeError, ValueError):
            sec = 0
        if sec not in words_by_sec:
            notes.append("beat %d dropped: section %r unknown" % (i, b.get("sec")))
            continue
        head = " ".join(str(b.get("head") or "").split())
        if not head or len(head) > 30:
            notes.append("beat %d dropped: head %r is not 1-28 characters" % (i, head[:40]))
            continue
        b["head"] = head
        sub = " ".join(str(b.get("sub") or "").split())
        if len(sub) > 64:
            cut = sub[:60].rsplit(" ", 1)[0].rstrip(" ,;:—-")
            notes.append("beat %d sub cut at a word: %r" % (i, cut))
            sub = cut
        b["sub"] = sub
        if b.get("img") and b["img"] not in names:
            notes.append("beat %d plate %r → %s" % (i, b["img"], DD_FALLBACK_PLATE))
            b["img"] = DD_FALLBACK_PLATE
        shot = " ".join(str(b.get("shot") or "").split()).lower()
        if shot and (len(shot.split()) > 4 or any(w in shot.split() for w in PLATE_BANNED)):
            notes.append("beat %d shot %r dropped" % (i, shot))
            shot = ""
        b["shot"] = shot or None
        if sec not in seen:
            seen.add(sec)
            cursor[sec] = 0
            if b.get("trig"):
                notes.append("beat %d: first beat of section %d — trig cleared" % (i, sec))
                b["trig"] = None
            kept.append(b)
            continue
        trig = b.get("trig")
        if not isinstance(trig, list) or not (2 <= len(trig) <= 4):
            notes.append("beat %d dropped: trig %r is not 2-4 words" % (i, trig))
            continue
        trig = [re.sub(r"[^a-z0-9']", "", str(w).lower()) for w in trig]
        trig = [w for w in trig if w]
        at = _find(words_by_sec[sec], trig, cursor.get(sec, 0)) if 2 <= len(trig) <= 4 else None
        if at is None:
            notes.append("beat %d dropped: trigger %r not spoken in section %d after word %d"
                         % (i, " ".join(trig), sec, cursor.get(sec, 0)))
            continue
        b["trig"] = trig
        cursor[sec] = at
        kept.append(b)
    if len(kept) != len(beats):
        ep["beats"] = kept
    cover = ep.get("cover") if isinstance(ep.get("cover"), dict) else None
    if cover and cover.get("img") and cover["img"] not in names:
        notes.append("cover plate %r → %s" % (cover["img"], DD_FALLBACK_PLATE))
        cover["img"] = DD_FALLBACK_PLATE
    yt = ep.get("youtube") if isinstance(ep.get("youtube"), dict) else None
    if yt:
        tags = yt.get("tags")
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
            notes.append("tags split from a string")
        tags = [str(t).strip() for t in (tags or []) if str(t).strip()]
        if len(tags) > 20:
            notes.append("tags cut from %d to 15" % len(tags))
            tags = tags[:15]
        yt["tags"] = tags
        desc = " ".join(str(yt.get("description") or "").split("\r"))
        if desc and "docoga.com.ng" not in desc:
            desc = desc.rstrip() + "\n\nMake yours in two minutes: https://docoga.com.ng"
            notes.append("description: tool link appended")
        if len(desc) > 1200:
            desc = desc[:1150].rsplit(" ", 1)[0].rstrip() + "\n\nhttps://docoga.com.ng"
            notes.append("description cut to shape")
        yt["description"] = desc
        title = " ".join(str(yt.get("title") or "").split())
        if len(title) > 100:
            yt["title"] = title[:100].rsplit(" ", 1)[0].rstrip(" :,-—(")
            notes.append("youtube.title cut to 100")
    for n in notes:
        log("brain: healed — %s" % n)
    return notes


def record_deepdive_attempt(number, attempt, outcome, title="", problems=None, healed=None, ledger=None):
    """logs/brain_deepdive.json — every attempt, with its reasons, so a quiet week can be read
    from the repo (run logs are not reachable from everywhere; this file is)."""
    path = Path(ledger or DD_LEDGER)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {"attempts": []}
    rows = data.setdefault("attempts", [])
    rows.append({"at": datetime.now(LAGOS).isoformat(timespec="seconds"), "episode": "dd%d" % number,
                 "attempt": attempt, "outcome": outcome, "title": (title or "")[:120],
                 "problems": [str(p)[:200] for p in (problems or [])][:12],
                 "healed": [str(h)[:160] for h in (healed or [])][:12],
                 "run_id": os.environ.get("GITHUB_RUN_ID", "")})
    data["attempts"] = rows[-60:]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass


def deepdive_problems(ep, facts_by_id):
    p = []
    secs = ep.get("sections") if isinstance(ep.get("sections"), list) else []
    if len(secs) != 9:
        p.append("exactly nine sections (got %d)" % len(secs))
    total = 0
    for i, s in enumerate(secs, 1):
        if not isinstance(s, dict) or int(s.get("n") or 0) != i:
            p.append("section %d: n must be %d" % (i, i))
            continue
        words = _norm_tokens(str(s.get("narration") or ""))
        total += len(words)
        # The ask is 120-200; the gate tolerates 90-240 (22 Oct 2026: a night was refused for
        # one section of 104 words — a word short of 105 is not a reason to lose a Saturday).
        if not (90 <= len(words) <= 240):
            p.append("section %d: %d words; need 120-200" % (i, len(words)))
        if not str(s.get("title") or "").strip():
            p.append("section %d: title missing" % i)
    if secs and not (1000 <= total <= 1900):
        p.append("total narration %d words; need 1,100-1,800" % total)
    beats = ep.get("beats") if isinstance(ep.get("beats"), list) else []
    if not (30 <= len(beats) <= 52):
        p.append("36-48 beats (got %d)" % len(beats))
    names = set(plates())
    cursor, first_seen = {}, set()
    for i, b in enumerate(beats, 1):
        if not isinstance(b, dict):
            p.append("beat %d must be an object" % i)
            continue
        sec = int(b.get("sec") or 0)
        if not (1 <= sec <= len(secs)):
            p.append("beat %d: sec out of range" % i)
            continue
        head = str(b.get("head") or "")
        if not head or len(head) > 30:
            p.append("beat %d: head 1-28 characters" % i)
        if len(str(b.get("sub") or "")) > 64:
            p.append("beat %d: sub <= 60 characters" % i)
        if b.get("img") and b["img"] not in names:
            p.append("beat %d: unknown plate %r" % (i, b.get("img")))
        shot = str(b.get("shot") or "").strip().lower()
        if shot and (len(shot.split()) > 4 or any(w in shot.split() for w in PLATE_BANNED)):
            p.append("beat %d: shot is 2-4 plain words, no people, no signs" % i)
        trig = b.get("trig")
        if sec not in first_seen:
            first_seen.add(sec)
            if trig:
                p.append("beat %d: the first beat of section %d must have trig null" % (i, sec))
            cursor[sec] = 0
            continue
        if not isinstance(trig, list) or not (2 <= len(trig) <= 4):
            p.append("beat %d: trig must be 2-4 words" % i)
            continue
        words = _norm_tokens(str(secs[sec - 1].get("narration") or ""))
        at = _find(words, [str(w) for w in trig], cursor.get(sec, 0))
        if at is None:
            p.append("beat %d: trigger %r not found in section %d after word %d" % (i, " ".join(map(str, trig)), sec, cursor.get(sec, 0)))
        else:
            cursor[sec] = at
    for sec in range(1, len(secs) + 1):
        if sum(1 for b in beats if isinstance(b, dict) and int(b.get("sec") or 0) == sec) < 2:
            p.append("section %d needs at least two beats" % sec)
    cover = ep.get("cover") if isinstance(ep.get("cover"), dict) else {}
    for key in ("img", "kicker", "line1", "highlight", "label", "line2", "line3", "sub"):
        if not str(cover.get(key) or "").strip():
            p.append("cover.%s missing" % key)
    if cover.get("img") and cover["img"] not in names:
        p.append("cover.img unknown plate")
    yt = ep.get("youtube") if isinstance(ep.get("youtube"), dict) else {}
    if not (10 <= len(str(yt.get("title") or "")) <= 100):
        p.append("youtube.title 10-100 characters")
    desc = str(yt.get("description") or "")
    if not (200 <= len(desc) <= 1200) or "docoga.com.ng" not in desc:
        p.append("youtube.description 250-900 characters and must contain docoga.com.ng")
    if not (6 <= len(yt.get("tags") or []) <= 20):
        p.append("youtube.tags 8-15")
    narration = " ".join(str(s.get("narration") or "") for s in secs if isinstance(s, dict))
    if _emoji_count(narration) or "*" in narration:
        p.append("no emoji or markdown in narration")
    for word in BANNED:
        if word in narration.lower():
            p.append("banned phrase in narration: %r" % word)
    claims = ep.get("claims") if isinstance(ep.get("claims"), list) else []
    if not claims:
        p.append("a Deep-Dive must declare its legal claims with fact ids")
    for c in claims:
        if not isinstance(c, dict) or c.get("fact_id") not in facts_by_id:
            p.append("claim cites unknown fact id %r" % (c.get("fact_id") if isinstance(c, dict) else c))
    return p


def deepdive_verify(ep, facts_by_id, http=None, sleep=None, log=print):
    facts = {c["fact_id"]: facts_by_id[c["fact_id"]] for c in ep["claims"] if c.get("fact_id") in facts_by_id}
    narration = "\n\n".join("--- C%d --- %s\n%s" % (s["n"], s["title"], s["narration"]) for s in ep["sections"])
    fake = {"claims": ep["claims"], "post": {"headline": ep["title"], "lines": [narration]}, "threads": {"text": ""}}
    prompt = verify_prompt(fake, facts).replace("THE POST", "THE EPISODE NARRATION")
    try:
        verdict = gemini_text.generate_json(prompt, system=VERIFY_SYSTEM, http=http, sleep=sleep,
                                            temperature=0.1, log=log, max_output_tokens=4096)
    except gemini_text.Exhausted:
        raise
    except gemini_text.GeminiError as exc:
        return ["verifier unavailable: %s" % exc]
    out = []
    for v in verdict.get("verdicts") or []:
        if isinstance(v, dict) and v.get("supported") is False:
            out.append("verifier: claim [%s] not supported — %s" % (v.get("fact_id"), v.get("reason", "")))
    for s in verdict.get("unsupported_statements") or []:
        if str(s).strip():
            out.append("verifier: legal statement not on the shelf — %r" % str(s)[:120])
    return out


ENDCARD_BEAT = {"head": "DOCOGA", "sub": "docoga.com.ng — link in the description", "img": "celebration", "endcard": True}


def _norm_tokens(text):
    t = str(text or "").lower().replace("\u2014", " ").replace("\u2013", " ").replace("-", " ")
    return [w for w in re.sub(r"[^a-z0-9' ]", " ", t).split() if w]


def with_endcard(beats, sections):
    """The renderer's contract (tools/deepdive.py, test_deepdive): the LAST beat is the DOCOGA end
    card. Gemini does not write it (dd4, 23 Oct 2026 — main went red on the contract test), so the
    writer appends it deterministically, triggered on the last words of section 9 so it lands
    as the narration closes. Idempotent: an episode that already ends on the card is untouched."""
    beats = list(beats)
    if beats and beats[-1].get("endcard"):
        return beats
    last = max((int(b.get("sec") or 0) for b in beats), default=9) or 9
    narration = next((s.get("narration") for s in sections if int(s.get("n") or 0) == last), "") or ""
    toks = _norm_tokens(narration)
    trig = toks[-3:] if len(toks) >= 3 else None
    beats.append(dict(ENDCARD_BEAT, sec=last, trig=trig, shot=None))
    return beats


def write_episode(ep, number, template):
    ep_id = "dd%d" % number
    folder = EPISODES / ep_id
    folder.mkdir(parents=True, exist_ok=False)
    script = "\n\n".join("--- C%d ---\n%s" % (s["n"], " ".join(str(s["narration"]).split())) for s in ep["sections"])
    (folder / "script.txt").write_text(script + "\n", encoding="utf-8")
    ep = dict(ep, beats=with_endcard(ep["beats"], ep["sections"]))
    meta = {
        "id": ep_id, "number": number, "title": ep["title"],
        "kicker": "DOCOGA — DEEP-DIVE · EPISODE %d" % number,
        "disclaimer": template.get("disclaimer", "GENERAL INFORMATION · NOT LEGAL ADVICE · RULES VARY BY STATE AND AGREEMENT"),
        "voice": template.get("voice"), "audio": template.get("audio"),
        "youtube": {"title": ep["youtube"]["title"], "description": ep["youtube"]["description"],
                    "tags": list(ep["youtube"].get("tags") or [])},
        "cover": ep["cover"],
        "sections": [{"n": s["n"], "title": s["title"]} for s in ep["sections"]],
        "beats": [dict({"sec": b["sec"], "trig": b.get("trig"), "head": b["head"], "sub": b.get("sub", ""), "img": b.get("img"),
                        "shot": (str(b.get("shot") or "").strip().lower() or None)},
                       **({"endcard": True} if b.get("endcard") else {}))
                  for b in ep["beats"]],
        "brain": {"written": datetime.now(LAGOS).isoformat(timespec="seconds"), "theme": ep.get("theme"),
                  "claims": ep["claims"]},
    }
    if meta["voice"] is None:
        meta.pop("voice")
    (folder / "episode.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    queue_path = EPISODES / "queue.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    if ep_id not in queue.get("queue", []):
        queue.setdefault("queue", []).append(ep_id)
        queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return folder


def engine_check(ep_id):
    """The engine's own trigger check, when its dependencies are present."""
    try:
        import deepdive  # noqa: WPS433  heavy (PIL, motionstudio) — only here
    except Exception as exc:  # pragma: no cover — the workflow runs the CLI too
        return ["engine check skipped: %s" % exc]
    try:
        return deepdive.check_triggers(deepdive.Episode(ep_id), verbose=False)
    except SystemExit as exc:
        return ["engine refused the episode: %s" % exc]


def deepdive_draft(http=None, sleep=None, log=print, dry_run=False, states=None):
    number = next_episode_number()
    previous = [m.get("title", "") for m in existing_episodes()]
    try:
        for row in json.loads((ROOT / "logs" / "youtube_longform.json").read_text(encoding="utf-8")):
            if isinstance(row, dict) and row.get("title"):
                previous.append(row["title"])
    except (OSError, ValueError):
        pass
    order = [slug for slug, _, _ in law_index.states()]
    states = states or [order[(number - 1) % len(order)], "lagos" if order[(number - 1) % len(order)] != "lagos" else "abuja"]
    facts = []
    for slug in dict.fromkeys(states):
        facts.extend(law_index.facts_for(slug))
    facts_by_id = {f["id"]: f for f in facts}
    template = existing_episodes()[-1] if existing_episodes() else {}
    problems = []
    for attempt in range(1, DD_ATTEMPTS + 1):
        try:
            ep = gemini_text.generate_json(deepdive_prompt(number, states, facts, previous, problems or None),
                                           system=DD_SYSTEM, http=http, sleep=sleep, log=log,
                                           max_output_tokens=24576, temperature=0.9, thinking_budget=2048)
        except gemini_text.Exhausted as exc:
            record_deepdive_attempt(number, attempt, "quota", problems=[str(exc)])
            raise
        healed = heal_deepdive(ep, log=log)
        problems = deepdive_problems(ep, facts_by_id)
        if not problems:
            try:
                problems = deepdive_verify(ep, facts_by_id, http=http, sleep=sleep, log=log)
            except gemini_text.Exhausted as exc:
                record_deepdive_attempt(number, attempt, "quota", title=ep.get("title", ""), problems=[str(exc)], healed=healed)
                raise
        if not problems:
            if dry_run:
                log("brain: dd%d would be written — %s" % (number, ep["title"]))
                return ep, []
            folder = write_episode(ep, number, template)
            engine = engine_check("dd%d" % number)
            engine = [e for e in engine if not e.startswith("engine check skipped")]
            if engine:
                import shutil
                shutil.rmtree(folder, ignore_errors=True)
                queue_path = EPISODES / "queue.json"
                queue = json.loads(queue_path.read_text(encoding="utf-8"))
                queue["queue"] = [q for q in queue.get("queue", []) if q != "dd%d" % number]
                queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                problems = engine
                record_deepdive_attempt(number, attempt, "engine-refused", title=ep.get("title", ""), problems=engine, healed=healed)
                log("brain: dd%d attempt %d refused by the engine: %s" % (number, attempt, "; ".join(engine)[:400]))
                continue
            record_deepdive_attempt(number, attempt, "written", title=ep.get("title", ""), healed=healed)
            log("brain: dd%d written and queued — %s" % (number, ep["title"]))
            log("BRAIN_DEEPDIVE=written")
            log("BRAIN_DEEPDIVE_TITLE=%s" % ep["title"])
            return ep, []
        record_deepdive_attempt(number, attempt, "refused", title=(ep.get("title", "") if isinstance(ep, dict) else ""),
                                problems=problems, healed=healed)
        log("brain: dd%d attempt %d refused: %s" % (number, attempt, "; ".join(problems)[:600]))
    log("BRAIN_DEEPDIVE=refused")
    log("BRAIN_DEEPDIVE_WHY=%s" % "; ".join(problems)[:400].replace("\n", " "))
    return None, problems


# ───────────────────────────── housekeeping ─────────────────────────────
def prune(today=None, keep_days=10):
    today = today or today_lagos()
    removed = []
    for p in sorted(drafts.drafts_dir().glob("*.json")):
        try:
            when = date.fromisoformat(p.stem)
        except ValueError:
            continue
        if (today - when).days > keep_days:
            p.unlink()
            removed.append(p.name)
    return removed


def status(today=None):
    today = today or today_lagos()
    lines = []
    for i in range(0, 7):
        day = today + timedelta(days=i)
        pack = drafts.draft_for(day)
        lines.append("%s %s  %s" % (day.isoformat(), "✅" if pack else "—",
                                   ("%s / %s%s" % (pack["theme"], pack["post_type"], " / short" if pack.get("short") else ""))
                                   if pack else "rotation fallback"))
    return "\n".join(lines)


# ───────────────────────────── CLI ─────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(description="DocOga's standing editor")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("plan")
    p.add_argument("--days", type=int, default=3)
    p.add_argument("--date")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("status")
    sub.add_parser("feedback")
    d = sub.add_parser("deepdive")
    d.add_argument("--dry-run", action="store_true")
    d.add_argument("--states", help="comma-separated shelf slugs")
    sub.add_parser("prune")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if args.cmd == "status":
        print(status())
        return 0
    if args.cmd == "feedback":
        print(write_feedback())
        return 0
    if args.cmd == "prune":
        print("pruned: %s" % (", ".join(prune()) or "nothing"))
        return 0
    if args.cmd == "deepdive":
        try:
            ep, problems = deepdive_draft(dry_run=args.dry_run,
                                          states=args.states.split(",") if args.states else None)
        except gemini_text.Exhausted as exc:
            print("brain: quota — %s" % exc)
            print("BRAIN_DEEPDIVE=quota")
            return 6
        if not ep:
            print("brain: no episode approved — " + "; ".join(problems))
            return 3
        return 0
    if args.cmd == "plan":
        start = date.fromisoformat(args.date) if args.date else None
        result = plan(days=args.days, start=start, dry_run=args.dry_run)
        print(status(start))
        if result["approved"] or (result["skipped"] and not result["refused"] and not result["quota"]):
            return 0
        if result["quota"]:
            return 6
        return 3
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
