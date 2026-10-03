#!/usr/bin/env python3
"""
DocOga Telegram Content Generator
Generates Nigerian-focused content for landlords, tenants, and property managers.
Fully autonomous - no manual input needed.
"""

import json
import random
from datetime import datetime
from pathlib import Path

# ===== CONFIG =====
ASSETS_DIR = Path("assets/telegram")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path("logs/social_media.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# DocOga-specific content templates
TEMPLATES = {
    "promo": [
        "🚀 **Get Clean Tenancy Agreements in Seconds!**\n\nDocOga helps Nigerian landlords and tenants create professional documents instantly. No lawyer fees!\n\n👉 Try it free: https://docoga.com.ng",
        "📄 **Need a Rent Receipt?**\n\nGenerate legally valid rent receipts in minutes with DocOga. Perfect for Nigerian landlords and tenants.\n\n👉 https://docoga.com.ng",
        "⚖️ **Avoid Tenancy Disputes!**\n\nUse DocOga's professionally drafted agreements to protect your rights. Nigerian law compliant.\n\n👉 https://docoga.com.ng",
        "💰 **Save ₦50,000 on Legal Fees!**\n\nDocOga's Oga Pass gives you unlimited clean documents for just ₦2,000/30 days.\n\n👉 Get yours: https://docoga.com.ng",
        "🏠 **Nigerian Landlords:**\n\nGenerate tenancy agreements, rent receipts, and invoices instantly. DocOga has you covered.\n\n👉 https://docoga.com.ng",
    ],
    "educational": [
        "📌 **Did You Know?**\n\nIn Nigeria, a tenancy agreement should include:\n✅ Landlord & tenant names\n✅ Property address\n✅ Rent amount & payment terms\n✅ Duration\n✅ Notice period\n\nGenerate yours instantly: https://docoga.com.ng",
        "💡 **Tenancy Tip:**\n\nAlways get a written receipt for every rent payment. It's your proof of payment!\n\nDocOga makes it easy: https://docoga.com.ng",
        "⚠️ **Important:**\n\nIn Lagos, the standard notice to quit is 6 months for yearly tenancies. Know your rights!\n\nNeed a Notice to Quit? https://docoga.com.ng",
        "📝 **Rent Receipt Must-Haves:**\n\n✔️ Date of payment\n✔️ Amount paid\n✔️ Property address\n✔️ Landlord/agent name\n✔️ Tenant name\n\nGenerate professional receipts: https://docoga.com.ng",
        "🔍 **Caution Fee in Nigeria:**\n\nIs it refundable? It depends on your agreement! Always clarify in writing.\n\nNeed a Caution Fee Receipt? https://docoga.com.ng",
    ],
    "pidgin": [
        "🎉 **Oya Check Am!**\n\nDocOga dey help you make tenancy agreement for free! No need pay lawyer ₦50k.\n\n👉 Try am: https://docoga.com.ng",
        "💬 **Landlord wey sabi:**\n\nNo need stress for agreement. DocOga don do the work for you.\n\n👉 https://docoga.com.ng",
        "⚡ **Quick quick!**\n\nYou fit generate rent receipt for your tenant in 2 minutes. DocOga na the plug!\n\n👉 https://docoga.com.ng",
        "🤝 **No more palava!**\n\nDocOga documents na clean and legal. No lawyer, no problem.\n\n👉 https://docoga.com.ng",
        "💰 **Save your money!**\n\nInstead of ₦50k for lawyer, pay just ₦2,000 for DocOga Oga Pass.\n\n👉 https://docoga.com.ng",
    ],
    "testimonial_style": [
        "🌟 **User Testimonial**\n\n\"DocOga saved me ₦50,000 on legal fees! The tenancy agreement was accepted by my lawyer.\" - Chidi, Lagos Landlord\n\nTry it: https://docoga.com.ng",
        "💯 **5-Star Rated**\n\n\"As a tenant, I use DocOga for all my rent receipts. Fast, easy, and professional.\" - Amina, Abuja\n\nGenerate yours: https://docoga.com.ng",
        "✅ **Verified User**\n\n\"I've been using DocOga for 6 months. Never had an issue with my documents.\" - Tunde, Estate Agent\n\nJoin them: https://docoga.com.ng",
    ],
    "urgent": [
        "⏰ **Limited Time Offer!**\n\nFirst 100 users get 50% off Oga Pass! Use code: WELCOME50\n\n👉 https://docoga.com.ng",
        "🔥 **Hot Deal!**\n\nOga Pass now ₦2,000 (normally ₦3,500). Get clean documents today!\n\n👉 https://docoga.com.ng",
        "🚨 **Don't Miss Out!**\n\nYour tenancy agreement is just a click away. No signup needed.\n\n👉 https://docoga.com.ng",
    ]
}

# Hashtags for different post types
HASHTAGS = {
    "promo": "#DocOga #NigerianLandlords #TenancyAgreement #RentReceipt #NoLawyerNeeded",
    "educational": "#PropertyTips #NigerianRealEstate #LandlordTips #TenantRights #DocOga",
    "pidgin": "#DocOga #NaijaLandlord #Pidgin #NigerianProperty #EasyDocuments",
    "testimonial": "#DocOga #UserTestimonial #HappyCustomers #NigerianRealEstate",
    "urgent": "#DocOga #SpecialOffer #LimitedTime #NigerianProperty #DealAlert"
}


def log(message):
    """Log messages to file and console"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    print(log_msg, end="")
    with open(LOG_FILE, "a") as f:
        f.write(log_msg)


def generate_daily_content():
    """Generate content for today's Telegram posts"""
    log("🚀 Generating Telegram content...")
    
    # Determine post type based on day of week
    today = datetime.now()
    day_of_week = today.weekday()  # 0=Monday, 6=Sunday
    
    # Schedule: Mix of content types
    if day_of_week == 0:  # Monday - Promo
        post_type = "promo"
    elif day_of_week == 1:  # Tuesday - Educational
        post_type = "educational"
    elif day_of_week == 2:  # Wednesday - Pidgin
        post_type = "pidgin"
    elif day_of_week == 3:  # Thursday - Testimonial
        post_type = "testimonial_style"
    elif day_of_week == 4:  # Friday - Urgent/Promo
        post_type = "urgent" if random.random() > 0.5 else "promo"
    elif day_of_week == 5:  # Saturday - Educational
        post_type = "educational"
    else:  # Sunday - Pidgin
        post_type = "pidgin"
    
    # Select a random template from the chosen type
    template = random.choice(TEMPLATES[post_type])
    hashtag = HASHTAGS.get(post_type, "#DocOga #NigerianProperty")
    
    # Add date-specific element
    date_str = today.strftime("%B %d, %Y")
    
    # Create the full message
    message = f"{template}\n\n{hashtag}\n\n📅 {date_str}"
    
    # Create content object
    content = {
        "date": today.strftime("%Y-%m-%d"),
        "day_of_week": day_of_week,
        "day_name": today.strftime("%A"),
        "post_type": post_type,
        "message": message,
        "hashtags": hashtag,
        "link": "https://docoga.com.ng",
        "generated_at": today.isoformat()
    }
    
    # Save to file
    output_file = ASSETS_DIR / f"telegram_content_{today.strftime('%Y-%m-%d')}.json"
    with open(output_file, "w") as f:
        json.dump(content, f, indent=2)
    
    log(f"✅ Content generated: {post_type} post for {today.strftime('%A, %B %d')}")
    log(f"   Message preview: {message[:100]}...")
    
    return content


def generate_multiple_posts(count=3):
    """Generate multiple posts (for initial setup or batch posting)"""
    log(f"🚀 Generating {count} Telegram posts...")
    
    posts = []
    for i in range(count):
        # Rotate through post types
        post_types = list(TEMPLATES.keys())
        post_type = post_types[i % len(post_types)]
        
        template = random.choice(TEMPLATES[post_type])
        hashtag = HASHTAGS.get(post_type, "#DocOga")
        
        message = f"{template}\n\n{hashtag}"
        
        posts.append({
            "post_type": post_type,
            "message": message,
            "hashtags": hashtag
        })
    
    return posts


if __name__ == "__main__":
    # Generate today's content
    content = generate_daily_content()
    
    # Also save a general content file for the workflow
    general_content = {
        "posts": [content]
    }
    with open(ASSETS_DIR / "telegram_content_latest.json", "w") as f:
        json.dump(general_content, f, indent=2)
    
    log("✅ All Telegram content files saved!")
