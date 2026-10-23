#!/usr/bin/env python3
"""series_week.py — the weekday Shorts as a five-part series, one law a week (23 Oct 2026).

    Monday     RENT RECEIPT LAW · 1 OF 5    end card: PART 2 TOMORROW · WHAT A RECEIPT MUST SHOW
    Tuesday    RENT RECEIPT LAW · 2 OF 5    end card: PART 3 TOMORROW · …
    …
    Friday     RENT RECEIPT LAW · 5 OF 5    end card: SERIES COMPLETE · ALL 5 ON THE CHANNEL

Why: a numbered series is the cheapest binge there is. A viewer who lands on part 3 looks for
parts 1 and 2 (session time — the signal YouTube Shorts, TikTok and Reels all reward in 2026),
and a viewer who finished part 1 knows exactly what tomorrow holds, so the follow has a reason.
The number also tells the algorithm the five uploads belong together; the title, the
description and the caption all say so in words it can read.

What this module is: the editorial SPINE only — which law this week, which angle today, what
tomorrow's part is called. The words of each Short are still written by the brain
(tools/brain.py reads `series_for(day)` into its prompt and writes part N to that angle), or,
when the brain has no approved pack, come from the hand-written rotation — framed as the
series only when that script actually serves the week's theme (`fits`), never dishonestly.

Deterministic from the date, so every lane (render, title, description, captions, dashboard)
agrees without talking to each other. Weekends have no Short and no part.

    SHORTS_SERIES_WEEK=off     plain daily Shorts again (kill switch, no code change)
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta

START = date(2026, 10, 26)   # the first series Monday
TOTAL = 5                    # Monday → Friday
LABEL_MAX = 30               # the masthead's size-30 ceiling (tools/shorts_reel.KICKER_MAX)

# One theme a week, five angles. `name` is a search phrase (it is what the cover and the title
# carry); `label` is the short end-card pointer (≤ 26 chars, upper-cased on screen); `angle` is
# the brief the brain writes to. `words` decide whether a rotation script may wear the series.
SERIES = [
    {"slug": "rent-receipt-law", "name": "Rent receipt law", "tool": "rent-receipt",
     "words": ("receipt",),
     "parts": [
         {"label": "Why the receipt is law", "angle": "Why the law makes a rent receipt compulsory, and whose duty it is to issue one"},
         {"label": "What a receipt must show", "angle": "What a valid rent receipt must show: names, amount, period, property, date, signature"},
         {"label": "Paid, no receipt. Now what", "angle": "You paid and got no receipt: what the law says next and what to do the same day"},
         {"label": "Transfers and agents", "angle": "Bank transfers and agents: a transfer alert is not a receipt; who must issue it when an agent collects"},
         {"label": "Demand it in writing", "angle": "How to demand a rent receipt in writing, and the free template that does it"},
     ]},
    {"slug": "tenancy-agreement", "name": "Tenancy agreement", "tool": "tenancy-agreement",
     "words": ("agreement", "sign", "unread"),
     "parts": [
         {"label": "Read before you sign", "angle": "Why you read the whole tenancy agreement before you sign, and what signing unread costs"},
         {"label": "The five clauses to find", "angle": "The five clauses to find first: rent, term, notice, repairs, what the deposit covers"},
         {"label": "Clauses the law overrides", "angle": "Clauses the law overrides no matter what the paper says, with the section cited"},
         {"label": "Who keeps the copy", "angle": "Stamping and copies: who keeps a signed copy, why the tenant must have one"},
         {"label": "Renewal without a fight", "angle": "Renewal: what changes, what cannot change mid-term, how to renew without a fight"},
     ]},
    {"slug": "notice-to-quit", "name": "Notice to quit", "tool": "notice-to-quit",
     "words": ("notice", "quit", "eviction"),
     "parts": [
         {"label": "How long the notice is", "angle": "How long a notice to quit must be for a weekly, monthly and yearly tenant, with the section"},
         {"label": "What a valid notice says", "angle": "What a valid notice to quit must say and how it must be served"},
         {"label": "After the notice expires", "angle": "After the notice expires: the seven days' notice of owner's intention and why no landlord can skip it"},
         {"label": "Locks and self-help", "angle": "Changing locks, removing doors, cutting light: why self-help eviction is unlawful and what to do"},
         {"label": "Answering a notice", "angle": "How a tenant answers a notice to quit in writing, and when to go to court"},
     ]},
    {"slug": "caution-fee", "name": "Caution fee", "tool": "caution-fee",
     "words": ("caution", "repaint", "deposit", "damage", "photos"),
     "parts": [
         {"label": "What a caution fee is", "angle": "What a caution fee is for, and what it is not: never extra rent, never an agent's fee"},
         {"label": "Photos on day one", "angle": "The move-in photos and inventory that decide the refund a year later"},
         {"label": "What may be deducted", "angle": "What a landlord may deduct: damage beyond fair wear and tear, not a routine repaint"},
         {"label": "Getting it back", "angle": "Getting the caution fee back: the timing, the written demand, the paper trail"},
         {"label": "The demand letter", "angle": "When the refund does not come: the letter of demand, and the free template"},
     ]},
    {"slug": "agent-and-landlord", "name": "Agent and landlord", "tool": "tenant-rights",
     "words": ("agent", "landlord", "wrong agent"),
     "parts": [
         {"label": "Pay the right person", "angle": "Who you pay: confirm the landlord or the agent's authority before any money moves"},
         {"label": "Agency fee limits", "angle": "What agency and legal fees the law caps, and what no tenant must pay twice"},
         {"label": "Advance rent limits", "angle": "How much rent may be demanded in advance under the state's law, with the section"},
         {"label": "Rent increase rules", "angle": "Rent increases: notice, reasonableness, and where to challenge an unreasonable one"},
         {"label": "When the agent vanishes", "angle": "When the agent disappears with the money: the paper you need and the first three steps"},
     ]},
    {"slug": "repairs-and-moving-in", "name": "Repairs and moving in", "tool": "tenant-rights",
     "words": ("repair", "photos", "moving", "damage"),
     "parts": [
         {"label": "Inspect before you pay", "angle": "Inspect the flat before any money: water, light, locks, damp — in writing"},
         {"label": "Whose repair is it", "angle": "Whose repair is it: structural and external to the landlord, small internal to the tenant, unless the agreement says otherwise"},
         {"label": "Report it in writing", "angle": "Reporting a fault by mouth leaves you with the bill: report in writing, keep the copy, date it"},
         {"label": "Repair and deduct", "angle": "When the landlord will not repair: the written notice, the quotes, and when repair-and-deduct is lawful"},
         {"label": "Moving out clean", "angle": "Moving out: the exit inspection, the photos, the keys handover note that protects the deposit"},
     ]},
]


def enabled(env=None):
    env = os.environ if env is None else env
    return str(env.get("SHORTS_SERIES_WEEK", "on")).strip().lower() not in ("off", "0", "no", "false")


def _day(day):
    if isinstance(day, datetime):
        day = day.date()
    if isinstance(day, str):
        day = date.fromisoformat(day[:10])
    return day


def week_index(day):
    """0 for the first series week, 1 for the next…; None before START."""
    day = _day(day)
    monday = day - timedelta(days=day.weekday())
    if monday < START:
        return None
    return (monday - START).days // 7


def series_for(day, env=None):
    """The part this weekday carries, or None (weekend, before START, switched off)."""
    day = _day(day)
    if not enabled(env) or day.weekday() >= TOTAL:
        return None
    idx = week_index(day)
    if idx is None:
        return None
    spec = SERIES[idx % len(SERIES)]
    part = day.weekday() + 1
    here = spec["parts"][part - 1]
    nxt = spec["parts"][part] if part < TOTAL else None
    prev = spec["parts"][part - 2] if part > 1 else None
    return {
        "slug": spec["slug"], "name": spec["name"], "tool": spec["tool"], "part": part, "total": TOTAL,
        "label": here["label"], "angle": here["angle"],
        "prev_label": prev["label"] if prev else "", "next_label": nxt["label"] if nxt else "",
        "next_angle": nxt["angle"] if nxt else "",
        "week_start": (day - timedelta(days=day.weekday())).isoformat(),
        "words": list(spec["words"]),
    }


def masthead(series):
    """`RENT RECEIPT LAW · 1 OF 5` — the opening masthead and the cover kicker."""
    text = "%s · %d OF %d" % (" ".join(series["name"].split()).upper(), series["part"], series["total"])
    return text if len(text) <= LABEL_MAX else "%s · %d OF %d" % ("PART", series["part"], series["total"])


def pointer(series, next_title=""):
    """The end-card line: tomorrow's part by name, or the series' close on Friday.
    `next_title` (tomorrow's approved Short, when the brain already wrote it) wins over the plan."""
    if series["part"] >= series["total"]:
        return "SERIES COMPLETE · ALL %d ON THE CHANNEL" % series["total"]
    name = " ".join(str(next_title or series["next_label"]).split()).rstrip(".")
    text = "PART %d TOMORROW · %s" % (series["part"] + 1, name.upper())
    if len(text) > 44:
        text = "PART %d TOMORROW · %s" % (series["part"] + 1, series["next_label"].upper())
    return text[:44]


def fits(series, script):
    """May this rotation script wear the series' frame? Only when its own words name the theme —
    a receipt Short under 'Rent receipt law', never a photos Short under it."""
    if not series or not isinstance(script, dict):
        return False
    hay = " ".join(str(script.get(k) or "") for k in ("title", "search")).lower()
    return any(w in hay for w in series.get("words") or ())


def sentence(series, next_title=""):
    """The description / caption line, in prose: 'Part 1 of 5 in this week's series on the rent
    receipt law. Tomorrow: What a receipt must show.'"""
    head = "Part %d of %d in this week's series on the %s." % (series["part"], series["total"], series["name"][0].lower() + series["name"][1:])
    if series["part"] >= series["total"]:
        return head + " All five parts are on the channel."
    return head + " Tomorrow: %s." % " ".join(str(next_title or series["next_label"]).split()).rstrip(".")


def attach(topic, day, env=None, pack_series=None):
    """Return the topic dict with `series` set when it honestly belongs to the week's series:
    a brain Short written to the part (`pack_series`), or a rotation script that fits."""
    series = series_for(day, env)
    if not series or not isinstance(topic, dict):
        return topic
    if pack_series and pack_series.get("slug") == series["slug"]:
        return dict(topic, series=series)
    if topic.get("brain"):
        return topic
    return dict(topic, series=series) if fits(series, topic) else topic


def brief(series):
    """The prompt block the brain reads."""
    if not series:
        return ""
    lines = ["THIS WEEK'S SHORTS SERIES — %s (part %d of %d today)" % (series["name"].upper(), series["part"], series["total"]),
             "- Today's part: \"%s\" — %s." % (series["label"], series["angle"]),
             "- The whole Short serves today's angle; spend no tip on another part."]
    if series["prev_label"]:
        lines.append("- Yesterday's part was \"%s\" — do not repeat it." % series["prev_label"])
    if series["next_label"]:
        lines.append("- Tomorrow's part is \"%s\" — the end card announces it; you need not." % series["next_label"])
    lines.append("- `tool` should be `%s` unless the shelf has nothing on it. The `short.title` must be about today's angle." % series["tool"])
    return "\n".join(lines)


# ───────────── the chain (23 Oct 2026, evening): every part points at the others ─────────────
PART_IN_TITLE = re.compile(r"\(part (\d+) of (\d+)\)", re.I)
SHORT_URL = "https://youtube.com/shorts/%s"


def line(series):
    """`Part 2 of 5 · Rent receipt law` — the one-line frame the captions and the handoffs carry."""
    return "Part %d of %d · %s" % (series["part"], series["total"], series["name"])


def hashtag(series):
    """`#RentReceiptLaw` — a hashtag page groups the five uploads; it goes first in the description
    because YouTube shows the first three hashtags above the title."""
    return "#" + "".join(w[:1].upper() + w[1:] for w in re.sub(r"[^A-Za-z0-9 ]", " ", series["name"]).split())


def topic_tag(series):
    """The Threads topic tag for the evening video post: the series name (≤50 chars, no '.' or '&')."""
    return series["name"].replace(".", "").replace("&", "and").strip()[:50]


def previous_parts(series, day, rows):
    """[(part, video_id)] of this week's earlier parts, read from the YouTube publish ledger
    (`logs/youtube_published.json` rows: date, title, video_id). Only this week's dates and only
    titles that carry `(part N of 5)` count — nothing is claimed that was not published."""
    day = _day(day)
    out = {}
    for r in rows or ():
        if not isinstance(r, dict) or not r.get("video_id"):
            continue
        when = str(r.get("date") or "")[:10]
        if not (series["week_start"] <= when < day.isoformat()):
            continue
        m = PART_IN_TITLE.search(str(r.get("title") or ""))
        if not m or int(m.group(2)) != series["total"]:
            continue
        part = int(m.group(1))
        if 1 <= part < series["part"] and part not in out:
            out[part] = r["video_id"]
    return sorted(out.items())


def chain_lines(series, previous):
    """The lines a comment or a caption adds under a part: where this sits, and the earlier parts
    by link. `previous` = previous_parts(...)."""
    lines = [line(series) + "."]
    for part, vid in previous:
        lines.append("Part %d: %s" % (part, SHORT_URL % vid))
    if series["part"] < series["total"]:
        lines.append("Part %d tomorrow, 7:00pm." % (series["part"] + 1))
    return lines


def playlist(series):
    """One public playlist per theme, so 'Up next' after part 1 is part 2 (tools/yt_boost.py)."""
    name = series["name"]
    return {
        "key": "series:" + series["slug"],
        "title": "%s in Nigeria — the 5-part series (DocOga Shorts)" % name,
        "description": ("%s, one part a day, Monday to Friday, in plain English for tenants and landlords in "
                        "Nigeria. Start at part 1. General information, not legal advice; rules vary by state and "
                        "agreement. Free document tools: https://docoga.com.ng/?s=yt" % name),
    }


if __name__ == "__main__":  # pragma: no cover — a glance at the next weeks
    import sys
    start = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else START
    for i in range(10):
        d = start + timedelta(days=i)
        s = series_for(d)
        print(d.isoformat(), d.strftime("%a"), masthead(s) if s else "—", "|", pointer(s) if s else "")
