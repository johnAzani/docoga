#!/usr/bin/env python3
"""
The caption a Short wears when it travels as a Reel (Facebook Page, @docoga.ng)
=================================================================================

Owner, 21 Oct 2026: "Improve more on all my social media … beat the algorithm."
Research the same afternoon, from what the platforms have said on the record:

* Instagram (Mosseri, 22 Jan 2025, repeated through 2026): the three signals that
  rank a Reel are **watch time**, **likes per reach** and **sends per reach** — and
  sends count most for reaching people who do not follow us. Captions are indexed
  for search since 2024; the first ~125 characters show before "more".
* Facebook (13 Mar 2026, about.fb.com): original Reels are preferred in Feed and
  Reels; views and time spent on original Reels doubled in H2 2025. Links in the
  caption are allowed on a Page.
* Both: hashtags are a weak signal — three to five, on-topic; never a wall.

So a Reel caption is built the same way every day, from the Short's own words:

    1. the spoken hook sentence (the Short's first line) — the only line most people
       read, and the words search indexes;
    2. the tip headlines as plain lines ("→ …") — keywords in text, not pixels;
    3. ONE send line that names a receiver (brain `post.cta` when the day has an
       approved pack; otherwise a dated rotation of eight) — the sends-per-reach line;
    4. where the free templates are (the Page may carry the link; Instagram points
       to the bio);
    5. four hashtags.

Everything is deterministic for a date, so a re-run writes the same caption and the
publishers' duplicate guards still work. No model is called here: the brain already
wrote the day's words at 1:30am, or the rotation did.

    python3 tools/reel_caption.py --platform instagram --topic "Pay without a receipt. Pay twice." \
        --description-file /tmp/short_description.txt --date 2026-10-21
"""

import argparse
import json
import re
import sys
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SITE = "https://docoga.com.ng"
HASHTAGS = {
    "facebook": "#DocOga #NigeriaRent #TenantRights #LagosTenancy",
    "instagram": "#DocOga #NigeriaRent #TenantRights #LagosTenancy",
    # TikTok (22 Oct 2026): five is the in-app ceiling since Aug 2025 — two broad, three niche.
    "tiktok": "#DocOga #Nigeria #TenantRights #LagosRent #RentInNigeria",
}
# TikTok is a search engine first (2026): the caption's opening characters are weighted most
# and are all a viewer sees before "more", so the search phrase leads. The brain's own SEO
# line for the day wins; otherwise one of these, by day, so a week of drafts never repeats.
TIKTOK_KEYWORDS = (
    "Tenant rights Nigeria",
    "Rent in Nigeria",
    "Lagos tenancy law",
    "Rent receipt Nigeria",
    "Tenancy agreement Nigeria",
    "Notice to quit Nigeria",
    "House rent Nigeria",
)
TIKTOK_MAX = 2200       # TikTok's caption ceiling (raised from 2,000 late 2025)
TIKTOK_TARGET = 360     # search-friendly (150–300 ideal, tips carry the indexed words); the feed shows ~100 before "more"
HOOK_MAX = 125          # Instagram shows about this much before "more"
TIPS_MAX = 3
CAPTION_MAX = 2200      # Instagram's ceiling; Facebook's is far higher

# The receiver is named on purpose: "send this to someone" is a wish, "send this to the
# friend renewing in January" is an instruction. Eight, so a fortnight of Reels never
# repeats the line twice in a row (the index is the day of the year).
SEND_LINES = (
    "Send this to the friend whose rent is due this month.",
    "Forward this to one person who pays cash and never asks for a receipt.",
    "Send this to the friend house-hunting in Lagos right now.",
    "Send this to your landlord's favourite tenant — they need it most.",
    "Forward this to the group chat before someone signs this weekend.",
    "Send this to the friend who just paid an agent they met online.",
    "Send this to the one who keeps saying 'my landlord is nice' — until the deposit.",
    "Forward this to someone renewing before December.",
)


# The account's own first comment under an Instagram post or Reel (22 Oct 2026): ONE question
# that a renter can answer in five words — Instagram ranks two-way conversation (Mar 2026) and
# every reply is a second impression for the post — plus the templates line, which lives here
# so the caption stays clean. The brain's `post.cta` wins when it is a question.
QUESTIONS = (
    "Which state are you renting in? Tell us below — the rules differ.",
    "When is your rent next due? January renewals, this one is for you.",
    "Did your last landlord give you a receipt without being asked? Yes or no.",
    "Agent or landlord — who collected your last rent?",
    "Has anyone ever kept your caution fee? What reason did they give?",
    "How many months' notice did your last landlord give you?",
    "Do you have your tenancy agreement on your phone right now?",
    "What is the one clause you wish you had read before signing?",
)
TEMPLATES_LINE = "Free receipt, agreement and notice templates: docoga.com.ng"


def first_comment(day, pack=None, description=""):
    cta = _clean(((pack or {}).get("post") or {}).get("cta")) if pack else ""
    question = cta if (cta.endswith("?") and len(cta) <= 140) else QUESTIONS[(day.timetuple().tm_yday + 3) % len(QUESTIONS)]
    parts = [question, TEMPLATES_LINE]
    series = series_parts(description)
    if series:
        # Series week (23 Oct 2026): Instagram cannot link, so the comment says where the earlier
        # parts are — the Reels before this one on the profile — and when the next one lands.
        where = ["Part %d of %d · %s." % (series["part"], series["total"], series["name"])]
        if series["part"] > 1:
            where.append("The earlier parts are the Reels before this one on our profile.")
        if series["part"] < series["total"]:
            where.append("Part %d lands tomorrow at 7:00pm." % (series["part"] + 1))
        parts.insert(0, " ".join(where))
    return "\n\n".join(parts)


def _clean(text):
    return " ".join(str(text or "").split())


def hook_from(description, topic=""):
    """The spoken hook: the first paragraph of the Short's description that is not the
    Deep-Dive link block, trimmed to one sentence that fits before "more"."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", str(description or "")) if p.strip()]
    for p in paragraphs:
        if p.startswith("Watch the full Deep-Dive") or p.startswith("In this Short") or "http" in p:
            continue
        if p.startswith("#"):
            continue
        hook = _clean(p)
        break
    else:
        hook = _clean(topic)
    if len(hook) > HOOK_MAX:
        cut = hook[:HOOK_MAX]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        hook = cut[: end + 1] if end > 40 else cut.rsplit(" ", 1)[0] + "…"
    return hook


def tips_from(description):
    """The '• …' headlines under 'In this Short:' as plain lines."""
    out = []
    block = re.search(r"In this Short:\n((?:• .+\n?)+)", str(description or ""))
    if block:
        for line in block.group(1).splitlines():
            line = _clean(line.lstrip("• ").strip())
            if line:
                out.append(line)
    return out[:TIPS_MAX]


_SERIES = re.compile(r"^(Part \d+ of \d+ in this week's series on [^\n]+)$", re.M)


def series_from(description):
    """The series line the Short's description carries ('Part 2 of 5 in this week's series on the
    rent receipt law. Tomorrow: …'), or ''. Read back from the description rather than recomputed,
    so the caption can never claim a part the video does not wear (tools/series_week.py)."""
    m = _SERIES.search(str(description or ""))
    return _clean(m.group(1)) if m else ""


def series_parts(description):
    """{"name": "Rent receipt law", "short": "Part 1 of 5 · Rent receipt law · tomorrow: …"} or None."""
    line = series_from(description)
    m = re.match(r"Part (\d+) of (\d+) in this week's series on the ([^.]+)\.(?:\s*Tomorrow: ([^.]+)\.)?", line)
    if not m:
        return None
    name = m.group(3).strip()
    name = name[:1].upper() + name[1:]
    short = "Part %s of %s · %s" % (m.group(1), m.group(2), name)
    if m.group(4):
        short += " · tomorrow: %s" % m.group(4).strip()
    return {"name": name, "short": short, "part": int(m.group(1)), "total": int(m.group(2))}


def send_line(day, pack=None):
    """The brain's own send/forward line when today's pack carries one; else the rotation."""
    cta = _clean(((pack or {}).get("post") or {}).get("cta")) if pack else ""
    if cta and re.match(r"(?i)^(send|forward|share)\b", cta) and len(cta) <= 140:
        return cta
    return SEND_LINES[day.timetuple().tm_yday % len(SEND_LINES)]


def pack_for(day, root=ROOT):
    path = root / "brain" / "drafts" / ("%s.json" % day.isoformat())
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return pack if isinstance(pack, dict) and pack.get("status") == "approved" else None


def tiktok_keyword(day, pack=None):
    seo = ""
    if pack:
        try:
            sys.path.insert(0, str(ROOT / "tools"))
            from brain_drafts import seo_line  # noqa: WPS433 — optional, the pack may be absent
            seo = _clean(seo_line(pack))
        except Exception:  # noqa: BLE001 — the rotation is the fallback by design
            seo = ""
    seo = fit_phrase(seo)
    if seo and 8 <= len(seo) <= 60:
        return seo
    return TIKTOK_KEYWORDS[day.timetuple().tm_yday % len(TIKTOK_KEYWORDS)]


PHRASE_MAX = 26          # the cover masthead's width (tools/shorts_reel.search_kicker)
PHRASE_FILLER = ("sample", "format", "template")


def fit_phrase(phrase):
    """The search phrase at masthead width, so screen and caption say the same words (24 Oct
    2026: "Tenancy agreement sample Nigeria" was 32 characters, the cover fell back to "Rent in
    Nigeria" and the two disagreed). Filler words go first ("Rent receipt format Nigeria" →
    "Rent receipt Nigeria"); a phrase still too long is dropped, and the day's rotation keyword
    speaks instead. The state in brackets is not counted — the cover strips it."""
    phrase = " ".join(str(phrase or "").split())
    if not phrase:
        return ""
    bare = re.sub(r"\s*\(.*?\)", "", phrase).strip()
    tail = phrase[len(bare):]
    if len(bare) <= PHRASE_MAX:
        return phrase
    words = [w for w in bare.split() if w.lower() not in PHRASE_FILLER]
    bare = " ".join(words)
    return (bare + tail) if len(bare) <= PHRASE_MAX else ""


def tiktok_caption(topic, description, day, pack=None):
    """Search phrase first, the spoken hook, two tips, a save line, bio pointer, five tags.
    150–300 characters is the 2026 sweet spot for TikTok search; the ceiling is 2,200."""
    hook = hook_from(description, topic)
    series = series_parts(description)
    # A series day leads with the series' own search phrase ("Rent receipt law Nigeria"), so the
    # caption, the cover and the title all name the same query (tools/series_week.py).
    keyword = ("%s Nigeria" % series["name"]) if series else tiktok_keyword(day, pack)
    first = hook if hook.lower().startswith(keyword.lower()) else "%s: %s" % (keyword, hook)
    tips = tips_from(description)[:2]
    parts = [first]
    if tips:
        parts.append(" · ".join(tips))
    if series:
        parts.append(series["short"])
    parts.append("Save this for your next rent. " + send_line(day, pack))
    parts.append("Free templates — link in bio (docoga.com.ng)")
    parts.append(HASHTAGS["tiktok"])
    text = "\n".join(parts)
    while len(text) > TIKTOK_TARGET and tips:
        tips = tips[:-1]
        parts[1:2] = [" · ".join(tips)] if tips else []
        text = "\n".join(parts)
    return text[:TIKTOK_MAX]


def caption(platform, topic, description, day, pack=None):
    platform = (platform or "facebook").strip().lower()
    if platform not in HASHTAGS:
        raise ValueError("platform must be facebook, instagram or tiktok, not %r" % platform)
    if platform == "tiktok":
        return tiktok_caption(topic, description, day, pack)
    hook = hook_from(description, topic)
    tips = tips_from(description)
    parts = [hook]
    if tips:
        parts.append("\n".join("→ " + t for t in tips))
    series = series_from(description)
    if series:
        parts.append(series)
    parts.append(send_line(day, pack))
    if platform == "facebook":
        parts.append("Free receipt, agreement and notice templates: %s" % SITE)
    else:
        parts.append("Free receipt, agreement and notice templates — link in bio (docoga.com.ng).")
    parts.append(HASHTAGS[platform])
    text = "\n\n".join(parts)
    if len(text) > CAPTION_MAX:
        text = text[: CAPTION_MAX - 1].rsplit("\n", 1)[0]
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--platform", required=True, choices=sorted(HASHTAGS))
    parser.add_argument("--topic", default="")
    parser.add_argument("--description-file", help="file holding the Short's YouTube description")
    parser.add_argument("--description", default="")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today in Lagos)")
    parser.add_argument("--first-comment", action="store_true", help="print the first comment instead of the caption")
    args = parser.parse_args(argv)
    description = args.description
    if args.description_file:
        description = Path(args.description_file).read_text(encoding="utf-8")
    if args.date:
        day = _date.fromisoformat(args.date)
    else:
        from datetime import datetime, timedelta, timezone
        day = datetime.now(timezone(timedelta(hours=1))).date()
    if args.first_comment:
        sys.stdout.write(first_comment(day, pack_for(day), description) + "\n")
        return 0
    sys.stdout.write(caption(args.platform, args.topic, description, day, pack_for(day)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
