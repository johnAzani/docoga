#!/usr/bin/env python3
"""
DocOga Telegram Content Generator
Generates Nigerian-focused content for landlords, tenants, and property managers.
Fully autonomous — no manual input needed.

Post types rotate by day of week with variety within each type.
Photo posts use brand images from the brand/ folder.
"""

import json
import random
import re
import os
import sys
from datetime import datetime
from pathlib import Path

# The escaper lives in tools/ so the poster and the tests share one definition.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from telegram_mdv2 import escape, validate  # noqa: E402

# ===== CONFIG =====
ASSETS_DIR = Path("assets/telegram")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
import docoga_log  # noqa: E402  one answer for "where do the scratch files live"

LOG_FILE = docoga_log.log_file("social_media.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
BRAND_DIR = Path("brand")

# Photo posts carry the day's copy rendered as the brand card (tools/social_card.py
# — navy ground, Inter, DOCOGA kicker, docoga.com.ng footer), never a file from
# brand/: those are logo explorations, and one reached a public feed on
# 15 Oct 2026 ("this is not my brand style").
import social_card  # noqa: E402
from telegram_mdv2 import to_plain  # noqa: E402
# The brain (tools/brain.py) may have decided today's post the night before; when it
# has, the rotation below is the fallback, not the voice.
import brain_drafts  # noqa: E402
import deepdive_promo  # noqa: E402  — the Deep-Dive's week in this channel

# ===== CONTENT TEMPLATES =====
#
# Rewritten 18 Oct 2026 ("improve the content … make the design more beautiful"), against what
# the 2026 data says a post must do on every one of our channels:
#
#   * Facebook: the first 40–80 characters decide it (posts ≤ 80 chars earn ~66 % more
#     engagement; the hook must land before "See more"); questions and polls are the
#     highest-engagement format per effort; the link goes in the first comment.
#   * Threads: under 200 characters reads best, replies are the ranking signal, so a
#     question beats an announcement.
#   * Instagram: the first line stands alone above "more"; saves and sends are what the
#     2026 ranking weighs, so a post must be worth keeping (a checklist, a number, a rule).
#   * Telegram: the channel reads the whole message, so structure (bold line, ✅/❌ lines,
#     one link) matters more than brevity.
#
# So every template is built the same way, and the card renderer draws that shape:
#   1. a HEADLINE under 48 characters that carries one specific tension (a number, a
#      named law, a mistake the reader may be making right now) — it lands on the yellow
#      slabs of the card and before Facebook's fold;
#   2. a BODY of one to five short lines — ✅ for what to insist on, ❌ for what to refuse,
#      numbers for a checklist, A)–D) for a poll — never a paragraph;
#   3. a QUESTION or one clear next step, and the link on its own line (the Facebook
#      poster moves a standalone link to the first comment; the card drops it — its chip
#      already says where to go).
#
# Legal lines are limited to what this repo has verified (Lagos Tenancy Law 2011: s.4
# advance rent, s.5 the receipt, s.13(1) notice periods). No invented statistics, and no
# invented customers: the "testimonial_style" slot is now a PICTURE THIS scenario, plainly
# framed as one — the brand never puts words in the mouth of a person who does not exist.
#
# `_tpl()` writes the MarkdownV2 for us (first line bold, everything escaped), which is
# why no template below carries a hand-typed backslash — the 7 Oct 2026 outage was one
# missed escape, and tools/tests/test_telegram_mdv2.py validates every template here.

LINK = "https://docoga.com.ng"


def _tpl(headline, body, link=LINK):
    """One template: bold headline, escaped body, the link on its own last line."""
    parts = ["*%s*" % escape(headline), escape(body)]
    if link:
        parts.append(escape(link))
    return "\n\n".join(parts)


TEMPLATES = {
    "promo": [
        _tpl("A tenancy agreement in 2 minutes. Free.",
             "Names, address, rent, period, notice — filled in, laid out, ready to print.\n"
             "No lawyer's fee. No template from 2009."),
        _tpl("Your rent receipt, before the money moves.",
             "Date. Amount. Period covered. Address. Who paid, who received.\n"
             "Generate it free, and hand it over with the cash."),
        _tpl("₦2,000 a month. Unlimited clean documents.",
             "Oga Pass: tenancy agreements, receipts, notices and invoices for 30 days.\n"
             "No watermark, no banner, no lawyer's queue."),
        _tpl("9 documents. 1 page. ₦0 to start.",
             "1. Tenancy Agreement\n2. Rent Receipt\n3. Notice to Quit\n4. Caution Fee Receipt\n"
             "5. Letter of Demand\n6. Invoice\n7. Employment Contract\n8. Payslip\n9. Warning Letter"),
        _tpl("Moving in this month? Do this first.",
             "✅ A written tenancy agreement, signed by both sides\n"
             "✅ A receipt for every naira you hand over\n"
             "❌ \"We'll sort the paper later\""),
        _tpl("Landlords: the receipt protects you too.",
             "A dated receipt is your proof of what was paid, for which period, by whom.\n"
             "It ends the \"I paid you already\" argument before it starts."),
        _tpl("Stop paying ₦50,000 for one agreement.",
             "A lawyer drafts one tenancy agreement for ₦30,000–₦50,000 in Lagos.\n"
             "DocOga drafts it free — and the Oga Pass covers every document after it."),
    ],
    "educational": [
        _tpl("5 lines every tenancy agreement must have.",
             "1. Landlord and tenant, by full name\n2. The property address\n3. Rent, and the period it covers\n"
             "4. How long the tenancy runs\n5. The notice that ends it\n\nMissing one? That is where the dispute starts."),
        _tpl("No receipt is not a favour. It is a risk.",
             "In Lagos, a landlord must issue a receipt for rent paid — Tenancy Law 2011, s.5.\n"
             "Paid cash with no paper? Today you have a debt with no proof.\n\n"
             "Has anyone ever asked you to pay \"without receipt\"?"),
        _tpl("Lagos: 6 months' notice for a yearly tenant.",
             "Lagos Tenancy Law 2011, s.13(1):\n"
             "✅ Yearly tenant — 6 months\n✅ Quarterly or half-yearly — 3 months\n✅ Monthly — 1 month\n\n"
             "A notice shorter than the law allows is not a notice."),
        _tpl("Your rent receipt needs these 6 things.",
             "✅ Date of payment\n✅ Amount, in figures and words\n✅ The period it covers\n"
             "✅ Property address\n✅ Landlord or agent name\n✅ Tenant name\n\nAnything less is a note, not a receipt."),
        _tpl("Caution fee is a deposit, not a gift.",
             "It is refundable when you leave the place in good condition, less genuine damage.\n"
             "Insist on a Caution Fee Receipt that names the amount and the condition agreed.\n\n"
             "Did you get yours back the last time you moved?"),
        _tpl("4 rights every Nigerian tenant has.",
             "1. Peaceful enjoyment of the property you pay for\n2. A written receipt for rent\n"
             "3. Proper notice before any eviction\n4. Your caution fee back, less real damage",
             link="https://docoga.com.ng/tenant-rights-nigeria.html"),
        _tpl("Stamp duty is a tax, not an agent's fee.",
             "In Lagos a tenancy agreement attracts stamp duty of roughly 0.78% of the rent, paid to government.\n"
             "An \"agreement fee\" of 10% is something else entirely — ask what it is for."),
        _tpl("Lagos: a year's rent upfront is the legal limit.",
             "Lagos Tenancy Law 2011, s.4: a landlord may not demand more than one year's rent in advance from a yearly tenant, "
             "or more than six months from a monthly tenant.\n\nWhat were you asked to pay last time?"),
    ],
    "pidgin": [
        _tpl("Oga, no pay rent without receipt.",
             "Cash don enter hand, paper no follow? Tomorrow na your word against im own.\n"
             "DocOga go make the receipt for you — free, sharp sharp."),
        _tpl("Lawyer ₦50k for agreement? Abeg.",
             "DocOga dey make tenancy agreement for you free. Oga Pass na ₦2,000 for 30 days, unlimited documents.\n"
             "Keep your money for the actual rent."),
        _tpl("Landlord wey sabi dey give receipt.",
             "E protect you, e protect the tenant, e end \"I don pay you before\" argument one time.\n"
             "Two minutes, free, print am."),
        _tpl("You wan pack enter new house? Hold on.",
             "✅ Agreement wey you and landlord sign\n✅ Receipt for every kobo wey you pay\n❌ \"We go write am later\"\n\n"
             "Later na the day problem go start."),
        _tpl("Lagos yearly tenant: 6 months' notice. Full stop.",
             "Na Tenancy Law 2011, s.13(1) talk am — no be landlord mouth.\n"
             "Monthly tenant na 1 month. Anything shorter no be notice."),
        _tpl("Caution fee no be landlord own forever.",
             "Na deposit. If you leave the house as you meet am, e suppose come back to you.\n"
             "Collect Caution Fee Receipt before you pay — e go talk for you later.\n\nYou don collect your own back before?"),
        _tpl("Agent don tell you \"pay first, see paper later\"?",
             "Na the oldest line for Lagos. Agreement first, money second — if dem no gree, waka.\n\n"
             "Wetin be the worst agent line you don hear?"),
    ],
    "testimonial_style": [
        _tpl("Picture this: two years of rent, zero receipts.",
             "The landlord sells the house. The new owner asks for proof you paid.\n"
             "You have transfers to an agent's personal account, and nothing else.\n\n"
             "What would you show him?"),
        _tpl("Picture this: two weeks' notice, on a Friday.",
             "A yearly tenant in Lagos, told to leave in two weeks.\n"
             "The law says six months — s.13(1)(e), Tenancy Law 2011. The letter is worth nothing.\n\n"
             "Would you have known to stand your ground?"),
        _tpl("Picture this: the agent \"forgot\" the caution fee.",
             "₦150,000 paid in cash at move-in. No receipt that names it a deposit.\n"
             "Three years later it is \"part of the rent\".\n\nOne receipt would have ended that conversation."),
        _tpl("Picture this: a tenancy that lived on WhatsApp.",
             "Rent agreed in a voice note. Increase announced in a text. No signed agreement anywhere.\n"
             "Who decides what was agreed?\n\nWrite it down — it takes two minutes."),
    ],
    "state_spotlight": [
        _tpl("Lagos tenants: your notice period, by law.",
             "Tenancy Law 2011, s.13(1):\n✅ Yearly — 6 months\n✅ Quarterly or half-yearly — 3 months\n✅ Monthly — 1 month\n\n"
             "Save this before you need it.",
             link="https://docoga.com.ng/notice-to-quit-lagos.html"),
        _tpl("Abuja: the agreement is your only map.",
             "In the FCT, what the written agreement says about rent, period and notice is what a court will read first.\n"
             "Get it signed before the first payment, not after.",
             link="https://docoga.com.ng/tenancy-agreement-abuja.html"),
        _tpl("Port Harcourt: receipts protect both sides.",
             "A dated receipt settles \"how much, for which months, to whom\" without an argument.\n"
             "Landlords and tenants in Rivers generate them free on DocOga.",
             link="https://docoga.com.ng/rent-receipt-rivers.html"),
        _tpl("Kano: 3 terms every agreement must state.",
             "1. The rent, and what period it covers\n2. How long the tenancy runs\n3. How and when it renews\n\n"
             "Unwritten terms are the ones people fight about.",
             link="https://docoga.com.ng/tenancy-agreement-kano.html"),
        _tpl("Ibadan landlords: one page ends most disputes.",
             "A signed agreement, a receipt for every payment, a proper notice when it ends.\n"
             "All three, free, in minutes.",
             link="https://docoga.com.ng/tenancy-agreement-oyo.html"),
        _tpl("Enugu: tenants and landlords, same paper.",
             "The same agreement protects whoever kept a copy. Keep yours.\n"
             "DocOga drafts it for every state and the FCT.",
             link="https://docoga.com.ng/tenancy-agreement-enugu.html"),
    ],
    "urgent": [
        _tpl("Rent due this week? Get the receipt ready.",
             "Landlords: generate the receipt before the tenant arrives.\n"
             "Tenants: do not leave without one. Two minutes, free."),
        _tpl("Most disputes start the same way: no paper.",
             "Not a bad landlord, not a bad tenant — an agreement that was never written down.\n"
             "Fix it today, before there is anything to argue about."),
        _tpl("Oga Pass — ₦2,000 for 30 days.",
             "Unlimited agreements, receipts, notices, invoices. No watermark, no banner.\n"
             "Less than one bottle of fuel; more than one lawyer's visit."),
        _tpl("Signing this weekend? Read these 4 lines.",
             "✅ Rent and the period it covers\n✅ The notice that ends the tenancy\n✅ Who holds the caution fee, and when it returns\n"
             "❌ \"Cash only, no receipt\""),
    ],
    "engagement": [
        _tpl("How much did your last agreement cost?",
             "A) Nothing — I wrote it myself\nB) ₦5,000 – ₦15,000\nC) ₦20,000 – ₦50,000\nD) I don't have one\n\n"
             "Reply with your letter."),
        _tpl("True or false: a verbal agreement is enough.",
             "False. It can exist in law — and it is nearly impossible to prove when it matters.\n"
             "Write it down, sign it, keep a copy.\n\nHave you ever had to prove a verbal deal?"),
        _tpl("Tenants and landlords: one question each.",
             "Tenants — what is the one line you wish your agreement had?\n"
             "Landlords — what is the one clause you will never leave out again?"),
        _tpl("Which one would you rather?",
             "A) ₦50,000, one agreement\nB) ₦2,000, every document — for 30 days\n\n"
             "Tell us in one line."),
        _tpl("What did your agent ask you to pay for?",
             "Agency fee. Agreement fee. Caution. Service charge. Legal fee.\n"
             "Which of these did you actually get paper for?"),
    ],
}

# Hashtags for different post types — a discovery tag or two, not a wall; the lanes trim to
# what each platform rewards (Instagram ≤ 5, Threads one topic tag).
HASHTAGS = {
    "promo": "#DocOga #TenancyAgreement #RentReceipt #NigerianLandlords",
    "educational": "#TenantRights #TenancyLaw #NigerianRealEstate #DocOga",
    "pidgin": "#DocOga #NaijaLandlord #NaijaTenant #Lagos",
    "testimonial_style": "#DocOga #TenantRights #NigerianRealEstate",
    "state_spotlight": "#DocOga #TenancyLaw #Nigeria #PropertyGuide",
    "urgent": "#DocOga #RentReceipt #TenancyAgreement",
    "engagement": "#DocOga #NaijaProperty #TenantLife #LandlordLife",
}

POLL_OPTION = re.compile(r"^\s*([A-D])\)\s+(.+?)\s*$")


def poll_from_text(plain):
    """{"question", "options"} when the copy carries A)–D) lines, else None.

    An opinion poll is the one tap a reader gives who would never type (Facebook's
    highest-engagement format per effort in 2026; a Telegram poll is native; Threads ranks by
    replies and counts a vote as one). The rotation's engagement days already ask the question
    in A)–D) shape, so the poll is read from the words rather than written twice. Options are
    clipped to Threads' 25 characters so one poll serves every channel."""
    lines = [ln for ln in (plain or "").split("\n")]
    options = [m.group(2) for m in (POLL_OPTION.match(ln) for ln in lines) if m]
    if not 2 <= len(options) <= 4:
        return None
    question = plain.split("\n\n")[0].strip()
    if not question.endswith("?"):
        return None
    options = [re.sub(r"\s+", " ", o) for o in options]
    options = [o if len(o) <= 25 else re.sub(r"\s*\u2014.*$", "", o)[:25].rstrip(" ,;:") for o in options]
    if len(set(options)) < len(options):
        return None
    return {"question": question[:300], "options": options}


# Weekly schedule with variety
WEEKLY_SCHEDULE = {
    0: ["promo", "educational"],           # Monday
    1: ["educational", "state_spotlight"], # Tuesday
    2: ["pidgin", "promo"],                # Wednesday
    3: ["testimonial_style", "engagement"],# Thursday
    4: ["urgent", "promo"],                # Friday
    5: ["educational", "state_spotlight"], # Saturday
    6: ["pidgin", "engagement"],           # Sunday
}


def log(message):
    """Log messages to file and console"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    print(log_msg, end="")
    with open(LOG_FILE, "a") as f:
        f.write(log_msg)


def render_card(message, day_iso, post_type, visual=None):
    """The day's copy as the brand card (repo-relative path), or None if it cannot render."""
    try:
        return social_card.card_for_post(to_plain(message), day_iso, post_type, "telegram", visual=visual)
    except Exception as exc:
        log(f"⚠️ card render failed ({type(exc).__name__}: {exc}) — text post instead")
        return None


def telegram_buttons_for(pack, promo):
    """The usual two rows; a feature day leads with the episode, a footer day appends it."""
    if promo and promo["stage"] == "feature":
        return promo["buttons"] + brain_drafts.telegram_buttons(pack)
    rows = brain_drafts.telegram_buttons(pack)
    if promo and promo["stage"] == "footer":
        rows = rows + promo["buttons"]
    return rows


def should_send_photo():
    """Decide if today's post should include a photo (40% chance)"""
    return random.random() < 0.4


def generate_daily_content():
    """Generate content for today's Telegram post"""
    log("🚀 Generating Telegram content...")

    today = datetime.now()
    day_of_week = today.weekday()  # 0=Monday, 6=Sunday

    pack = brain_drafts.draft_for(today)
    visual = None
    # The Deep-Dive's week (tools/deepdive_promo.py, 17 Oct 2026): the day after an episode
    # goes public this post IS the episode — card, hook, chapters, watch + read buttons; for a
    # fortnight after, the usual post simply gains a "▶ This week's Deep-Dive" button.
    promo = deepdive_promo.pack_for(today.date(), "telegram")
    card_text = None
    if promo and promo["stage"] == "feature":
        post_type = "deepdive"
        template = escape(promo["text"])
        hashtag = ""
        card_text = promo["card_text"]
        log("🎬 Deep-Dive feature day: %s" % promo["title"])
    elif pack:
        # The brain's words are plain text; escape them once for MarkdownV2 like the hashtags.
        post_type = brain_drafts.post_type(pack)
        template = escape(brain_drafts.tag_links(brain_drafts.post_text(pack), "telegram"))
        hashtag = brain_drafts.hashtags(pack, "telegram")
        visual = brain_drafts.visual(pack)
        log("🧠 brain pack for %s: %s (%s)" % (pack["date"], pack.get("theme"), post_type))
    else:
        # The rotation, with a memory (24 Oct 2026, owner: "make sure you are not repeating or
        # recycling contents"): `random.choice` here had none, so a template could come round
        # two mornings running. generate_facebook_content.pick() replays the seeded walk and
        # reads this channel's own ledger, so the words are never ones the channel carried
        # inside fresh.FRESH_DAYS. Lazy import: that module imports this one.
        import generate_facebook_content as fb
        post_type, template = fb.pick(today.date(), channel="telegram")
        template = brain_drafts.tag_links_mdv2(template, "telegram")
        hashtag = HASHTAGS.get(post_type, "#DocOga #NigerianProperty")

    # Build the full message. The templates carry their own MarkdownV2 escapes
    # (that is deliberate — they were written for it), but the hashtag block is
    # generated text, so it MUST go through the escaper: `#` is reserved in
    # MarkdownV2 and a raw hashtag makes Telegram reject the entire post with
    # "can't parse entities: Character '#' is reserved". That was the 7 Oct
    # 2026 outage — every post failed, every day, for four days.
    message = f"{template}\n\n{escape(hashtag)}" if hashtag else template

    # Fail loudly in the log rather than silently in the channel. The unit
    # tests in tools/tests/test_telegram_mdv2.py cover every template; this is
    # the runtime tripwire for a template added later without its escapes.
    problems = validate(message)
    if problems:
        log("⚠️ Message is not valid MarkdownV2 — the poster will fall back to plain text:")
        for problem in problems:
            log(f"   • {problem}")

    # Decide on photo vs text post (a brain day always carries its card)
    send_photo = True if (pack or card_text) else should_send_photo()
    photo_path = None
    if send_photo:
        photo_path = render_card(card_text or message, today.strftime("%Y-%m-%d"), post_type, visual)
        if photo_path:
            log(f"📸 Photo post: brand card rendered at {photo_path}")
        else:
            send_photo = False

    # Create content object
    content = {
        "date": today.strftime("%Y-%m-%d"),
        "day_of_week": day_of_week,
        "day_name": today.strftime("%A"),
        "post_type": post_type,
        "message": message,
        "hashtags": hashtag,
        "link": brain_drafts.tag_links(brain_drafts.link_for(pack) if pack else brain_drafts.LINK, "telegram"),
        "buttons": telegram_buttons_for(pack, promo),
        "send_photo": send_photo,
        "photo_path": photo_path,
        "generated_at": today.isoformat(),
        "brain": pack.get("theme") if pack else None,
        "quiz": brain_drafts.quiz(pack) if pack else None,
        "poll": None if pack else poll_from_text(to_plain(template)),
    }

    # Save to files
    output_file = ASSETS_DIR / f"telegram_content_{today.strftime('%Y-%m-%d')}.json"
    with open(output_file, "w") as f:
        json.dump(content, f, indent=2)

    log(f"✅ Content generated: {post_type} post for {today.strftime('%A, %B %d')}")
    log(f"   Message preview: {message[:120]}...")

    return content


if __name__ == "__main__":
    content = generate_daily_content()

    # Also save as latest for the poster
    with open(ASSETS_DIR / "telegram_content_latest.json", "w") as f:
        json.dump({"posts": [content]}, f, indent=2)

    log("✅ All Telegram content files saved!")
