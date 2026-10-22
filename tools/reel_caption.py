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
}
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


def first_comment(day, pack=None):
    cta = _clean(((pack or {}).get("post") or {}).get("cta")) if pack else ""
    question = cta if (cta.endswith("?") and len(cta) <= 140) else QUESTIONS[(day.timetuple().tm_yday + 3) % len(QUESTIONS)]
    return question + "\n\n" + TEMPLATES_LINE


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


def caption(platform, topic, description, day, pack=None):
    platform = (platform or "facebook").strip().lower()
    if platform not in HASHTAGS:
        raise ValueError("platform must be facebook or instagram, not %r" % platform)
    hook = hook_from(description, topic)
    tips = tips_from(description)
    parts = [hook]
    if tips:
        parts.append("\n".join("→ " + t for t in tips))
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
        sys.stdout.write(first_comment(day, pack_for(day)) + "\n")
        return 0
    sys.stdout.write(caption(args.platform, args.topic, description, day, pack_for(day)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
