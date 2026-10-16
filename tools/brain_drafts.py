#!/usr/bin/env python3
"""brain_drafts.py — how the lanes read what the brain decided for a day.

The editor (tools/brain.py) writes one approved pack per day to
`brain/drafts/YYYY-MM-DD.json`. The content generators ask this module, at post
time, "is there a pack for today?" and shape their channel's copy from it. When
there is none — the brain was out of quota, the gates refused every draft, or
the lane is being tested with a date the brain never saw — the generators fall
back to the hand-written rotation exactly as before. Nothing in a lane blocks on
the brain; the brain only ever improves a day.

This module deliberately imports nothing heavy (no PIL, no network), because
the Telegram generator is imported by code paths that run before fonts exist.

    DOCOGA_BRAIN=off           ignore every draft (a kill switch for the lanes)
    DOCOGA_BRAIN_DRAFTS=<dir>  read drafts from another folder (tests)
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCLAIMER = "General information, not legal advice."
LINK = "https://docoga.com.ng"
SCHEMA_VERSION = 1
SITE = ROOT / "site"

# The deep link a post may carry instead of the homepage (17 Oct 2026). A reader who tapped
# "notice to quit in Lagos" should land on the Lagos notice page, not on a menu of ten tools:
# one tap less between the post and the paper. `tool` is chosen by the brain from TOOLS and
# checked by the lint; the page must exist in site/ or the link falls back, in order, to the
# national guide and then the homepage. Never a 404 from a social post.
TOOLS = ("tenancy-agreement", "notice-to-quit", "rent-receipt", "caution-fee", "letter-of-demand",
         "invoice", "payslip", "employment-contract", "warning-letter", "power-of-attorney", "tenant-rights")
NATIONAL_PAGE = {"tenancy-agreement": "tenancy-agreement-nigeria.html", "notice-to-quit": "notice-to-quit-nigeria.html",
                 "rent-receipt": "rent-receipt-format-nigeria.html", "caution-fee": "caution-fee-nigeria.html",
                 "invoice": "invoice-format-nigeria.html", "power-of-attorney": "power-of-attorney-nigeria.html",
                 "tenant-rights": "tenant-rights-nigeria.html"}
STATE_PAGE_TOOLS = ("tenancy-agreement", "notice-to-quit", "rent-receipt", "caution-fee")


def link_for(pack, site=None):
    """The one link this pack carries: state page → national guide → homepage, never a 404."""
    site = Path(site) if site else SITE
    tool = str((pack or {}).get("tool") or "").strip().lower()
    state = str((pack or {}).get("state") or "").strip().lower()
    if tool not in TOOLS:
        return LINK
    if tool in STATE_PAGE_TOOLS and state and (site / ("%s-%s.html" % (tool, state))).is_file():
        return "%s/%s-%s.html" % (LINK, tool, state)
    national = NATIONAL_PAGE.get(tool)
    if national and (site / national).is_file():
        return "%s/%s" % (LINK, national)
    return LINK


def drafts_dir():
    return Path(os.environ.get("DOCOGA_BRAIN_DRAFTS") or (ROOT / "brain" / "drafts"))


def enabled():
    return os.environ.get("DOCOGA_BRAIN", "on").strip().lower() not in ("off", "0", "no", "false")


def _iso(day):
    if isinstance(day, datetime):
        day = day.date()
    if isinstance(day, date):
        return day.isoformat()
    return str(day)[:10]


def path_for(day):
    return drafts_dir() / ("%s.json" % _iso(day))


def draft_for(day):
    """The approved pack for `day`, or None. Never raises."""
    if not enabled():
        return None
    p = path_for(day)
    try:
        if not p.is_file():
            return None
        pack = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(pack, dict) or pack.get("status") != "approved":
        return None
    if pack.get("date") != _iso(day) or int(pack.get("version", 0)) != SCHEMA_VERSION:
        return None
    if not (pack.get("post") or {}).get("headline"):
        return None
    return pack


def has_claims(pack):
    return bool(pack.get("claims"))


def post_text(pack):
    """The long-form copy (Telegram/Facebook): headline, lines, disclaimer, link."""
    post = pack["post"]
    parts = [post["headline"].strip()]
    body = "\n".join(line.strip() for line in post.get("lines") or [] if line.strip())
    if body:
        parts.append(body)
    cta = str(post.get("cta") or "").strip()
    if cta:
        parts.append(cta)   # the send/forward/reply line — the signal every 2026 feed ranks on
    if has_claims(pack):
        parts.append(DISCLAIMER)
    parts.append(link_for(pack))
    return "\n\n".join(parts)


def hashtags(pack, channel="facebook"):
    tags = list((pack.get("post") or {}).get("hashtags") or [])
    if channel == "threads":
        tags = list((pack.get("threads") or {}).get("hashtags") or tags[:2])
    if "#DocOga" not in tags:
        tags.insert(0, "#DocOga")
    return " ".join(tags)


def threads_text(pack):
    """The short copy for Threads/Instagram, link at the end, no hashtags."""
    text = ((pack.get("threads") or {}).get("text") or "").strip()
    if not text:
        text = pack["post"]["headline"].strip()
    if has_claims(pack) and DISCLAIMER.lower() not in text.lower():
        text = text.rstrip() + "\n\n" + DISCLAIMER
    if LINK not in text:
        text = text.rstrip() + "\n" + link_for(pack)
    return text


def cta(pack):
    return str(((pack.get("post") or {}).get("cta") or "")).strip()


def post_type(pack):
    return (pack.get("post_type") or "educational").strip()


def kicker(pack):
    k = ((pack.get("visual") or {}).get("kicker") or "").strip()
    return ("DocOga · %s" % k) if k else ""


def visual(pack):
    return dict(pack.get("visual") or {})


def short_topic(pack):
    """The brain's Short in the rotation's shape (title/parent/slides), or None."""
    short = pack.get("short")
    if not isinstance(short, dict) or not short.get("tips"):
        return None
    tips = [t for t in short["tips"] if isinstance(t, dict) and t.get("text")][:4]
    if len(tips) < 3:
        return None
    slides = [{"text": short.get("hook_text") or short["title"].upper(),
               "sub": short.get("hook_sub", ""), "duration": 3}]
    for tip in tips:
        slides.append({"text": tip["text"], "sub": tip.get("sub", ""), "duration": 4})
    slides.append({"text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "duration": 4})
    return {"title": short["title"], "parent": short.get("parent") or "brain",
            "brain": pack.get("date"), "slides": slides}


_WORD = re.compile(r"[a-z0-9₦']+")


def words(text):
    return set(_WORD.findall((text or "").lower()))


def similarity(a, b):
    """Jaccard over words — the repeat test the dedup gate and the tests share."""
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / float(len(wa | wb))
