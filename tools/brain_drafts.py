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


# Channel tags on every link we post (17 Oct 2026, fifth research pass). `?s=tg` is short
# enough for Threads' character budget and survives MarkdownV2 escaping; the site turns it
# into a first-touch source (localStorage) that rides the checkout tap and the /verify call,
# so the scorecard can say which channel *sold* a pass, not only which one got likes.
SOURCE_TAGS = {"telegram": "tg", "facebook": "fb", "instagram": "ig", "threads": "th", "linkedin": "li",
               "tiktok": "tt", "youtube": "yt", "whatsapp": "wa"}
_OUR_LINK = re.compile(r"https://docoga\.com\.ng(?:/[^\s)\]<>\"']*)?")


def tag_links(text, channel):
    """Append `?s=<tag>` to every docoga.com.ng link in `text` that has no query string yet."""
    tag = SOURCE_TAGS.get(str(channel or "").lower())
    if not tag or not text:
        return text

    def one(m):
        url = m.group(0)
        if "?" in url or "#" in url:
            return url
        if url == LINK:
            url += "/"
        return url + "?s=" + tag
    return _OUR_LINK.sub(one, text)


_OUR_LINK_MDV2 = re.compile(r"https://docoga\\\.com\\\.ng[^\s\"']*")


def tag_links_mdv2(text, channel="telegram"):
    """`tag_links` for copy that is ALREADY MarkdownV2-escaped (the hand-written Telegram
    templates): each escaped link is unescaped, tagged, and escaped again, so `?s\\=tg` lands
    with the `=` escaped and nothing else in the message is touched. Trailing escaped
    punctuation (`\\.` `\\!` `\\,`) that belongs to the sentence stays outside the link."""
    tag = SOURCE_TAGS.get(str(channel or "").lower())
    if not tag or not text:
        return text
    import telegram_mdv2

    def one(m):
        raw = m.group(0)
        tail = ""
        while raw.endswith(("\\.", "\\!", "\\,", "\\)", "\\:")):
            tail, raw = raw[-2:] + tail, raw[:-2]
        url = re.sub(r"\\(.)", r"\1", raw)
        if not _OUR_LINK.fullmatch(url):
            return m.group(0)
        return telegram_mdv2.escape(tag_links(url, channel)) + tail
    return _OUR_LINK_MDV2.sub(one, text)


def share_line(pack):
    """The one sentence a reader forwards: the headline, link-free, ≤ 140 characters."""
    post = (pack or {}).get("post") or {}
    text = strip_links(str(post.get("headline") or "")).strip()
    if not text:
        return "Free Nigerian legal documents — tenancy, notice to quit, rent receipt."
    return (text[:137].rsplit(" ", 1)[0] + "…") if len(text) > 140 else text


def telegram_buttons(pack=None, link=None):
    """Inline buttons for the Telegram post (17 Oct 2026, sixth pass).

    Row 1 is the tap we want: the exact page the post is about, tagged `?s=tg`, so a reader
    who read "notice to quit in Lagos" lands on that page and the tap is counted. Row 2 is
    the growth loop — WhatsApp is on 96.5% of Nigerian phones every month, Telegram's own
    share sheet forwards to any chat — pre-filled with the headline and a `?s=wa` / `?s=tg`
    link, so a forward is a counted visit, not a rumour. URL buttons need no callback server
    (₦0): the attribution lives in the link. Returned as Bot API `inline_keyboard` rows.
    """
    from urllib.parse import quote
    page = link or link_for(pack)
    page = page.split("?")[0]
    tg = tag_links(page, "telegram")
    wa = tag_links(page, "whatsapp")
    line = share_line(pack)
    return [
        [{"text": "📄 Open the free tool", "url": tg}],
        [{"text": "💬 Share on WhatsApp", "url": "https://wa.me/?text=" + quote(line + " " + wa, safe="")},
         {"text": "↗️ Forward on Telegram",
          "url": "https://t.me/share/url?url=" + quote(tg, safe="") + "&text=" + quote(line, safe="")}],
    ]


def carousel_slides(pack, max_points=6):
    """The Instagram carousel copy (17 Oct 2026): hook → one point per slide → the close.

    Carousels out-engage single images on Instagram in 2026 (0.55% vs 0.37% ER, nine times the
    saves — Socialinsider/Metricool) because every swipe and every save is a signal. The brain's
    pack already has the shape: the headline is the hook, each line is a slide, the CTA closes.
    Returns a list of (kicker, text); empty when the pack has fewer than two lines, in which
    case the lane posts its single card as before.
    """
    post = (pack or {}).get("post") or {}
    headline = strip_links(str(post.get("headline") or "")).strip()
    lines = [strip_links(str(line)).strip() for line in post.get("lines") or []]
    lines = [line for line in lines if len(line) > 3][:max_points]
    if not headline or len(lines) < 2:
        return []
    slides = [("swipe \u2192", headline)]
    for index, line in enumerate(lines, 1):
        slides.append(("%d of %d" % (index, len(lines)), line))
    close = strip_links(str(post.get("cta") or "")).strip() or "Save this. Send it to one tenant who needs it."
    slides.append(("free \u00b7 docoga.com.ng", close))
    return slides


def threads_text(pack):
    """The short copy for Threads/Instagram, link at the end, no hashtags.

    A poll post carries no link: Threads refuses a poll next to a link attachment, and a
    bare URL in the text becomes one. The poll's job is replies; the link's turn is the reply."""
    text = ((pack.get("threads") or {}).get("text") or "").strip()
    if not text:
        text = pack["post"]["headline"].strip()
    if has_claims(pack) and DISCLAIMER.lower() not in text.lower():
        text = text.rstrip() + "\n\n" + DISCLAIMER
    if LINK not in text and not threads_poll(pack):
        text = text.rstrip() + "\n" + link_for(pack)
    return text


# Threads topic tags (one per post, ≤50 chars, no periods or ampersands). Meta: posts with a
# topic collect more views than posts without one — it is the subject label people browse.
TOPIC_TAGS = {"tenancy-agreement": "Tenant Rights Nigeria", "notice-to-quit": "Tenant Rights Nigeria",
              "rent-receipt": "Tenant Rights Nigeria", "caution-fee": "Tenant Rights Nigeria",
              "tenant-rights": "Tenant Rights Nigeria", "shop-tenancy-agreement": "Nigerian Small Business",
              "invoice": "Nigerian Small Business", "payslip": "Nigerian Workplace",
              "power-of-attorney": "Nigerian Law", "affidavit": "Nigerian Law"}
DEFAULT_TOPIC = "Rent in Nigeria"
# Instagram SEO (Google indexes professional accounts' posts since 10 Jul 2025; Instagram's own
# search reads the caption's first line and the alt text). One plain search phrase per tool —
# the words a Nigerian types, not a slogan.
SEO_PHRASES = {"tenancy-agreement": "Tenancy agreement sample Nigeria", "notice-to-quit": "Notice to quit Nigeria",
               "rent-receipt": "Rent receipt format Nigeria", "caution-fee": "Caution fee refund Nigeria",
               "tenant-rights": "Tenant rights in Nigeria", "shop-tenancy-agreement": "Shop tenancy agreement Nigeria",
               "invoice": "Invoice template Nigeria", "payslip": "Payslip format Nigeria",
               "power-of-attorney": "Power of attorney Nigeria", "affidavit": "Affidavit format Nigeria"}
DEFAULT_SEO = "Rent and tenancy documents Nigeria"
STATE_NAMES = {"lagos": "Lagos", "abuja": "Abuja", "fct": "Abuja", "rivers": "Rivers", "kano": "Kano", "oyo": "Oyo",
               "ogun": "Ogun", "enugu": "Enugu", "kaduna": "Kaduna", "delta": "Delta", "anambra": "Anambra"}


def seo_line(pack, post_type=None):
    """The caption's first line: the search phrase, with the state when there is one.
    'Rent receipt format Nigeria (Lagos)'."""
    tool = str((pack or {}).get("tool") or "").strip().lower()
    state = str((pack or {}).get("state") or "").strip().lower()
    phrase = SEO_PHRASES.get(tool) or DEFAULT_SEO
    if state in STATE_NAMES:
        phrase += " (%s)" % STATE_NAMES[state]
    return phrase


def alt_text(pack, text=""):
    """Alt text for the card (Instagram reads it for search and for screen readers; ≤1,000
    characters). Says what the picture IS — a DocOga text card — and what it says."""
    post = (pack or {}).get("post") or {}
    headline = str(post.get("headline") or "").strip() or strip_links(text).split("\n")[0].strip()
    lines = [str(x).strip() for x in post.get("lines") or [] if str(x).strip()]
    kicker = str(((pack or {}).get("visual") or {}).get("kicker") or "").strip()
    bits = ["DocOga navy text card%s: %s" % ((" — " + kicker) if kicker else "", headline)]
    if lines:
        bits.append(lines[0])
    bits.append(seo_line(pack) + ". docoga.com.ng")
    out = " ".join(b if b[-1] in ".?!" else b + "." for b in (x.strip() for x in bits) if b)
    return out[:1000]
POLL_OPTION_MAX = 25


def strip_links(text):
    """Remove every URL and the stub it leaves behind ("👉", "Try am:", a line of punctuation)."""
    out = []
    for line in re.sub(r"https?://\S+", "", text or "").split("\n"):
        bare = line.strip()
        if bare and not re.search(r"[A-Za-z0-9₦]", bare):
            continue                                  # "👉" alone
        if bare.endswith(":") and len(bare) <= 24:
            continue                                  # "👉 Try am:" / "Start here:"
        out.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def threads_evening(pack):
    """The 8 pm Threads post (17 Oct 2026): a second angle on the day's idea, link-free — the
    link rides in our own reply. The brain writes `threads.evening`; without it, the headline
    plus the first line plus the send/forward line is a post in its own right."""
    text = str(((pack or {}).get("threads") or {}).get("evening") or "").strip()
    if not text:
        post = (pack or {}).get("post") or {}
        lines = [str(x).strip() for x in post.get("lines") or [] if str(x).strip()]
        parts = [str(post.get("headline") or "").strip()] + lines[:1]
        cta = str(post.get("cta") or "").strip()
        if cta:
            parts.append(cta)
        text = "\n\n".join(p for p in parts if p)
    text = strip_links(text)
    if has_claims(pack or {}) and DISCLAIMER.lower() not in text.lower():
        text = text.rstrip() + "\n\n" + DISCLAIMER
    return text


def evening_reply(pack, channel="threads"):
    """The one-line self-reply that carries the page: 'The page, free to start: <link?s=th>'."""
    return "The page, free to start: " + tag_links(link_for(pack or {}), channel)


def threads_topic(pack):
    given = str(((pack or {}).get("threads") or {}).get("topic") or "").strip()
    tag = given or TOPIC_TAGS.get(str((pack or {}).get("tool") or "").strip().lower(), DEFAULT_TOPIC)
    tag = tag.replace(".", "").replace("&", "and").strip()
    return tag[:50]


def threads_poll(pack):
    """{"option_a": …, "option_b": …[, option_c, option_d]} when the pack carries a valid poll, else None."""
    poll = ((pack or {}).get("threads") or {}).get("poll")
    if not isinstance(poll, dict):
        return None
    out = {}
    for key in ("option_a", "option_b", "option_c", "option_d"):
        val = str(poll.get(key) or "").strip()
        if not val:
            break
        if len(val) > POLL_OPTION_MAX:
            return None
        out[key] = val
    return out if len(out) >= 2 else None


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


QUIZ_QUESTION_MAX = 300
QUIZ_OPTION_MAX = 100
QUIZ_EXPLANATION_MAX = 200


def quiz(pack):
    """The Telegram quiz of the day — {"question", "options", "correct", "explanation"} — or None.

    A quiz is the one Telegram format that gets a tap from a reader who would not type: the
    answer is revealed with the section, and the explanation is where the law lives."""
    q = (pack or {}).get("quiz")
    if not isinstance(q, dict):
        return None
    question = str(q.get("question") or "").strip()
    options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
    explanation = str(q.get("explanation") or "").strip()
    try:
        correct = int(q.get("correct"))
    except (TypeError, ValueError):
        return None
    if not question or len(question) > QUIZ_QUESTION_MAX or not 2 <= len(options) <= 4:
        return None
    if any(len(o) > QUIZ_OPTION_MAX for o in options) or not 0 <= correct < len(options):
        return None
    if not explanation or len(explanation) > QUIZ_EXPLANATION_MAX:
        return None
    return {"question": question, "options": options, "correct": correct, "explanation": explanation}

