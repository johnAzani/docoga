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

# ===== CONTENT TEMPLATES =====

TEMPLATES = {
    "promo": [
        "🚀 *Get Clean Tenancy Agreements in Seconds\\!*\n\nDocOga helps Nigerian landlords and tenants create professional documents instantly\\. No lawyer fees\\!\n\n👉 Try it free: https://docoga\\.com\\.ng",
        "📄 *Need a Rent Receipt?*\n\nGenerate legally valid rent receipts in minutes with DocOga\\. Perfect for Nigerian landlords and tenants\\.\n\n👉 https://docoga\\.com\\.ng",
        "⚖️ *Avoid Tenancy Disputes\\!*\n\nUse DocOga's professionally drafted agreements to protect your rights\\. Nigerian law compliant\\.\n\n👉 https://docoga\\.com\\.ng",
        "💰 *Save ₦50,000 on Legal Fees\\!*\n\nDocOga's Oga Pass gives you unlimited clean documents for just ₦2,000/30 days\\.\n\n👉 Get yours: https://docoga\\.com\\.ng",
        "🏠 *Nigerian Landlords:*\n\nGenerate tenancy agreements, rent receipts, and invoices instantly\\. DocOga has you covered\\.\n\n👉 https://docoga\\.com\\.ng",
        "📋 *9 Document Tools, 1 Platform*\n\nTenancy Agreement • Notice to Quit • Rent Receipt • Invoice • Employment Contract • Caution Fee Receipt • Letter of Demand and more\\.\n\nAll free at https://docoga\\.com\\.ng",
        "🔑 *Moving into a new place?*\n\nBefore you pay that rent, make sure you have a proper tenancy agreement\\. DocOga generates one in 2 minutes — free\\.\n\n👉 https://docoga\\.com\\.ng",
    ],
    "educational": [
        "📌 *Did You Know?*\n\nIn Nigeria, a tenancy agreement should include:\n✅ Landlord & tenant names\n✅ Property address\n✅ Rent amount & payment terms\n✅ Duration\n✅ Notice period\n\nGenerate yours instantly: https://docoga\\.com\\.ng",
        "💡 *Tenancy Tip:*\n\nAlways get a written receipt for every rent payment\\. It's your proof of payment\\!\n\nDocOga makes it easy: https://docoga\\.com\\.ng",
        "⚠️ *Important:*\n\nIn Lagos, a yearly tenant gets 6 months' notice to quit under s\\.13\\(1\\)\\(e\\) of the Tenancy Law 2011 \\(3 months is for quarterly and half\\-yearly tenants\\)\\. Know your rights\\!\n\nNeed a Notice to Quit? https://docoga\\.com\\.ng",
        "📝 *Rent Receipt Must\\-Haves:*\n\n✔️ Date of payment\n✔️ Amount paid\n✔️ Property address\n✔️ Landlord/agent name\n✔️ Tenant name\n\nGenerate professional receipts: https://docoga\\.com\\.ng",
        "🔍 *Caution Fee in Nigeria:*\n\nA caution fee is a refundable security deposit — typically 5\\-10% of rent\\. It MUST be refunded when you vacate if the property is in good condition\\.\n\nGet a Caution Fee Receipt: https://docoga\\.com\\.ng",
        "📖 *Tenant Rights 101:*\n\nAs a Nigerian tenant, you have the right to:\n🔹 Peaceful enjoyment of the property\n🔹 A written rent receipt\n🔹 Proper notice before eviction\n🔹 Return of caution fee\n\nLearn more: https://docoga\\.com\\.ng/tenant\\-rights\\-nigeria\\.html",
        "🏛️ *Stamp Duty on Tenancy Agreements:*\n\nIn Lagos, tenancy agreements are subject to stamp duty of approximately 0\\.78% of the rent\\. This is a government tax — separate from agent fees\\.\n\nGenerate your agreement: https://docoga\\.com\\.ng",
        "📊 *Nigeria's Housing Crisis:*\n\nNigeria has a 14\\.9 million unit housing deficit\\. Lagos alone: 3\\.4 million units\\. With 15M\\+ renters in Lagos, the demand for proper documentation is massive\\.\n\nBe prepared: https://docoga\\.com\\.ng",
    ],
    "pidgin": [
        "🎉 *Oya Check Am\\!*\n\nDocOga dey help you make tenancy agreement for free\\! No need pay lawyer ₦50k\\.\n\n👉 Try am: https://docoga\\.com\\.ng",
        "💬 *Landlord wey sabi:*\n\nNo need stress for agreement\\. DocOga don do the work for you\\.\n\n👉 https://docoga\\.com\\.ng",
        "⚡ *Quick quick\\!*\n\nYou fit generate rent receipt for your tenant in 2 minutes\\. DocOga na the plug\\!\n\n👉 https://docoga\\.com\\.ng",
        "🤝 *No more palava\\!*\n\nDocOga documents na clean and legal\\. No lawyer, no problem\\.\n\n👉 https://docoga\\.com\\.ng",
        "💰 *Save your money\\!*\n\nInstead of ₦50k for lawyer, pay just ₦2,000 for DocOga Oga Pass\\. Unlimited clean documents for 30 days\\.\n\n👉 https://docoga\\.com\\.ng",
        "🏠 *You wan rent house?*\n\nBefore you sign anything, make sure you get proper agreement\\. DocOga go help you generate am sharp sharp\\.\n\n👉 https://docoga\\.com\\.ng",
        "📢 *Make I tell you something:*\n\nYour landlord suppose give you receipt every time you pay rent\\. If e no dey give you, use DocOga generate your own\\!\n\n👉 https://docoga\\.com\\.ng",
    ],
    "testimonial_style": [
        "🌟 *What Users Are Saying*\n\n\"DocOga saved me ₦50,000 on legal fees\\! The tenancy agreement was accepted by my lawyer\\.\" — Chidi, Lagos Landlord\n\nTry it: https://docoga\\.com\\.ng",
        "💯 *Trusted by Nigerians*\n\n\"As a tenant, I use DocOga for all my rent receipts\\. Fast, easy, and professional\\.\" — Amina, Abuja\n\nGenerate yours: https://docoga\\.com\\.ng",
        "✅ *Real Results*\n\n\"I've been using DocOga for my properties\\. The documents are clean and my tenants love it\\.\" — Tunde, Estate Agent\n\nJoin them: https://docoga\\.com\\.ng",
        "🏆 *Why Nigerians Choose DocOga*\n\n\"I needed a notice to quit urgently\\. DocOga generated it in 2 minutes\\. My lawyer said it was perfect\\.\" — Ngozi, Port Harcourt\n\nTry it free: https://docoga\\.com\\.ng",
    ],
    "state_spotlight": [
        "📍 *Lagos Tenancy Guide*\n\nLagos tenants: a yearly tenancy gets 6 months' notice to quit under s\\.13\\(1\\)\\(e\\) of the Lagos Tenancy Law 2011; monthly tenants get one month\\.\n\nGet your Notice to Quit: https://docoga\\.com\\.ng/notice\\-to\\-quit\\-lagos\\.html",
        "📍 *Abuja Tenancy Guide*\n\nFCT tenants: always get a written tenancy agreement before moving in\\. DocOga generates one for Abuja properties in minutes\\.\n\n👉 https://docoga\\.com\\.ng/tenancy\\-agreement\\-abuja\\.html",
        "📍 *Rivers State Guide*\n\nPort Harcourt landlords: proper rent receipts protect you AND your tenant\\. Generate professional receipts instantly\\.\n\n👉 https://docoga\\.com\\.ng/rent\\-receipt\\-rivers\\.html",
        "📍 *Kano Tenancy Tips*\n\nIn Kano, tenancy agreements should clearly state the rent amount, duration, and renewal terms\\. DocOga covers all states\\.\n\n👉 https://docoga\\.com\\.ng/tenancy\\-agreement\\-kano\\.html",
        "📍 *Oyo State Landlords*\n\nIbadan property owners: use DocOga to generate clean tenancy agreements, rent receipts, and invoices\\. Free and instant\\.\n\n👉 https://docoga\\.com\\.ng/tenancy\\-agreement\\-oyo\\.html",
        "📍 *Enugu Property Guide*\n\nCoal City tenants and landlords: protect yourselves with proper documentation\\. DocOga works for all 36 states \\+ FCT\\.\n\n👉 https://docoga\\.com\\.ng/tenancy\\-agreement\\-enugu\\.html",
    ],
    "urgent": [
        "⏰ *Don't Wait Until There's a Problem\\!*\n\nMost landlord\\-tenant disputes happen because there was no written agreement\\. Get yours today — it takes 2 minutes\\.\n\n👉 https://docoga\\.com\\.ng",
        "🔥 *Oga Pass — ₦2,000*\n\nUnlimited clean documents for 30 days\\. No watermark, no banner\\. Professional documents every time\\.\n\n👉 https://docoga\\.com\\.ng",
        "🚨 *Rent Due Soon?*\n\nMake sure you have a proper rent receipt ready\\. Landlords: generate receipts for your tenants instantly\\.\n\n👉 https://docoga\\.com\\.ng",
    ],
    "engagement": [
        "🤔 *Question of the Day:*\n\nWhat's the biggest challenge you face as a tenant or landlord in Nigeria?\n\nDrop your answer below 👇\n\nNeed documents? https://docoga\\.com\\.ng",
        "📊 *Poll Time\\!*\n\nHow much did you pay for your last tenancy agreement?\n\nA\\) Free \\(DIY\\)\nB\\) ₦5,000 \\- ₦15,000\nC\\) ₦20,000 \\- ₦50,000\nD\\) I don't have one 😱\n\nDocOga gives you clean agreements for ₦2,000/30 days: https://docoga\\.com\\.ng",
        "💭 *True or False?*\n\n\"A verbal agreement is just as good as a written one\\.\"\n\n*FALSE\\!* Always get it in writing\\. Verbal agreements are nearly impossible to enforce in Nigerian courts\\.\n\nGenerate your written agreement: https://docoga\\.com\\.ng",
        "🎯 *This or That?*\n\nWould you rather:\nA\\) Pay ₦50,000 to a lawyer for ONE agreement\nB\\) Pay ₦2,000 for UNLIMITED documents for 30 days\n\nThe answer is obvious 👉 https://docoga\\.com\\.ng",
    ],
}

# Hashtags for different post types
HASHTAGS = {
    "promo": "#DocOga #NigerianLandlords #TenancyAgreement #RentReceipt #NoLawyerNeeded",
    "educational": "#PropertyTips #NigerianRealEstate #LandlordTips #TenantRights #DocOga",
    "pidgin": "#DocOga #NaijaLandlord #Pidgin #NigerianProperty #EasyDocuments",
    "testimonial_style": "#DocOga #UserTestimonial #HappyCustomers #NigerianRealEstate",
    "state_spotlight": "#DocOga #Nigeria #PropertyGuide #TenancyLaws #RealEstate",
    "urgent": "#DocOga #SpecialOffer #NigerianProperty #DocumentsNow",
    "engagement": "#DocOga #NaijaProperty #LandlordLife #TenantLife #Nigeria",
}

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
    if pack:
        # The brain's words are plain text; escape them once for MarkdownV2 like the hashtags.
        post_type = brain_drafts.post_type(pack)
        template = escape(brain_drafts.tag_links(brain_drafts.post_text(pack), "telegram"))
        hashtag = brain_drafts.hashtags(pack, "telegram")
        visual = brain_drafts.visual(pack)
        log("🧠 brain pack for %s: %s (%s)" % (pack["date"], pack.get("theme"), post_type))
    else:
        # Pick a post type from today's options
        options = WEEKLY_SCHEDULE.get(day_of_week, ["promo"])
        post_type = random.choice(options)

        # Select a random template from the chosen type
        template = brain_drafts.tag_links_mdv2(random.choice(TEMPLATES[post_type]), "telegram")
        hashtag = HASHTAGS.get(post_type, "#DocOga #NigerianProperty")

    # Build the full message. The templates carry their own MarkdownV2 escapes
    # (that is deliberate — they were written for it), but the hashtag block is
    # generated text, so it MUST go through the escaper: `#` is reserved in
    # MarkdownV2 and a raw hashtag makes Telegram reject the entire post with
    # "can't parse entities: Character '#' is reserved". That was the 7 Oct
    # 2026 outage — every post failed, every day, for four days.
    message = f"{template}\n\n{escape(hashtag)}"

    # Fail loudly in the log rather than silently in the channel. The unit
    # tests in tools/tests/test_telegram_mdv2.py cover every template; this is
    # the runtime tripwire for a template added later without its escapes.
    problems = validate(message)
    if problems:
        log("⚠️ Message is not valid MarkdownV2 — the poster will fall back to plain text:")
        for problem in problems:
            log(f"   • {problem}")

    # Decide on photo vs text post (a brain day always carries its card)
    send_photo = True if pack else should_send_photo()
    photo_path = None
    if send_photo:
        photo_path = render_card(message, today.strftime("%Y-%m-%d"), post_type, visual)
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
        "link": "https://docoga.com.ng",
        "send_photo": send_photo,
        "photo_path": photo_path,
        "generated_at": today.isoformat(),
        "brain": pack.get("theme") if pack else None,
        "quiz": brain_drafts.quiz(pack) if pack else None,
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
