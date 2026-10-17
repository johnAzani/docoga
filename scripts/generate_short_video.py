#!/usr/bin/env python3
"""
DocOga Short-Form Video — the WORDS of the daily rotation
=========================================================

Publish lanes (YouTube Shorts, Facebook Reels, Telegram video) take only
`VIDEO_SCRIPTS` / `script_for_date()` from this module. The picture is rendered
by MotionStudio (`tools/motionstudio.py`) through `tools/shorts_reel.py` —
Inter on #061A33, springs, the yellow underline, the grain (docs/BRAND_STYLE.md).

The static-card renderer below (`create_slide_image`, `generate_video`) is
RETIRED from every publish lane: it is off-palette and off-typeface and was the
reason the 14 Oct 2026 Short shipped looking like nothing else DocOga makes.
It stays only for its own regression tests and for local previews of the copy;
`tools/qa.py` refuses any lane that imports it to render.

Legacy notes (the old card renderer; not the brand palette):

BRAND COLORS (sampled from the official brand mark, 18 Sep 2026):
  Navy:        #002040  RGB(0, 32, 64)
  Brand Blue:  #0060e0  RGB(0, 96, 224)
  Royal Blue:  #0040c0  RGB(0, 64, 192)
  Sky Blue:    #0080e0  RGB(0, 128, 224)
"""

import os
import sys
from datetime import date, datetime
from pathlib import Path

# tools/brain_drafts.py — the brain's Short for a date, when it approved one.
_TOOLS = str(Path(__file__).resolve().parents[1] / "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

try:
    from moviepy import ImageClip, concatenate_videoclips
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

from PIL import Image, ImageChops, ImageDraw, ImageFont

# ===== CONFIG =====
WIDTH = 1080
HEIGHT = 1920
FPS = 24
OUTPUT_DIR = Path("assets/videos")
BRAND_DIR = Path("brand")

# ===== LOCKED BRAND RULES ENCODED HERE =====
# 🔴 THE OFFICIAL LOGO IS NOT STAMPED ON SOCIAL POSTS — AND NEVER ON VIDEO.
# Owner direction 21 Sep 2026 (docs/DESIGN_SYSTEM.md §1): the logo is not
# stamped on social posts. docs/SESSION_CONTEXT.md is explicit for motion:
# "NEVER stamp the logo on reels or videos. Logo goes on static images only
# (carousels, status posts). NEVER on video. PERMANENT RULE."
#
# Therefore nothing in this module may read brand/*.png into a frame. The one
# sanctioned way the real logo touches a design is tools/add_logo.py, which
# pastes the exact pixels onto STATIC images. Regression tests enforce this.
LOGO_FORBIDDEN_ON_VIDEO = True

# CTA bar — the brand checklist requires "CTA: docoga.com.ng present".
CTA_TEXT = "DOCOGA.COM.NG"
CTA_BAR_H = 132
CTA_FONT_SIZE = 44

# BRAND_STYLE.md §3 "Always present": film grain, σ≈2.2 luminance noise.
FILM_GRAIN_SIGMA = 2.2

# BRAND_STYLE.md §3 grid: 84px margins / safe areas respected.
SAFE_MARGIN = 84

# ===== BRAND COLORS (sampled from the official brand mark) =====
NAVY       = (0, 32, 64)      # #002040
BRAND_BLUE = (0, 96, 224)     # #0060e0
ROYAL_BLUE = (0, 64, 192)     # #0040c0
SKY_BLUE   = (0, 128, 224)    # #0080e0
WHITE      = (255, 255, 255)
YELLOW     = (255, 215, 0)
RED        = (220, 53, 69)
DARK       = (10, 15, 30)     # Near-black with blue tint

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ===== FACT-SAFE CONTENT SCRIPTS =====
# These are practical record-keeping prompts, not legal conclusions. Every Short
# ends with a reminder that rules vary by state and agreement.
# Hook law (data, 14 Oct 2026 — docs/YOUTUBE_PERFORMANCE.md): the STAKES pattern
# "Do the careless thing. Suffer the consequence." took 108 views on its first
# outing ("Change the lock. Become the defendant."); every QUESTION hook on the
# channel sits at 2–16. So the opening slide of every rotation topic is a
# two-beat consequence line — imperative, no question mark — and the title is
# that same line, because the title is what the Shorts feed shows under the
# frame. `parent` names the Deep-Dive each Short trails (tools/deepdive_links.py
# turns it into the watch link in the description).
VIDEO_SCRIPTS = [
    {
        "title": "Pay without a receipt. Pay twice.",
        "parent": "dd3",
        "slides": [
            {"bg": NAVY, "text": "PAY WITHOUT A RECEIPT.\nPAY TWICE.", "say": "You pay rent in cash, the landlord says thank you, and nobody writes anything down. Months later someone asks for proof, and all you have is your word. Four habits fix that.", "sub": "cash leaves no trail — paper does", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "TAKE THE RECEIPT", "say": "Collect the receipt the day you pay, not later. It should show the date, the amount, the months it covers, the address, and the landlord's name and signature.", "sub": "on the day — not \"later\"", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "KEEP THE TRANSFER RECORD", "say": "If you paid by transfer, screenshot the confirmation and keep the alert. The date, amount, account name and reference together are your evidence. Save them where you will find them.", "sub": "date · amount · reference", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "SAY WHAT IT WAS FOR", "say": "When you send the money, say what it is for: rent, which flat, which months. Then keep the landlord's reply. A payment with its purpose attached is hard to argue about.", "sub": "\"rent, flat 4, Jan to Dec\" — keep the reply", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "ONE FOLDER. TWO PLACES.", "say": "Put every receipt and screenshot in one folder on your phone, and copy it to the cloud. Phones get lost. Proof that lives in two places survives the day one disappears.", "sub": "phone plus cloud — proof survives", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Pay the wrong agent. Lose the flat.",
        "parent": "dd3",
        "slides": [
            {"bg": NAVY, "text": "PAY THE WRONG AGENT.\nLOSE THE FLAT.", "say": "Someone shows you a flat, collects your money, and disappears. The real landlord has never heard of you. It happens every week, and these four rules cost nothing.", "sub": "verify before money moves", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "SEE THE PROPERTY", "say": "Go and see the flat yourself before any money moves. Walk the rooms, check water and light, talk to a neighbour. A flat you have only seen in photos, you have not seen.", "sub": "in person, if you can", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "ASK FOR WRITTEN AUTHORITY", "say": "Ask the agent one question: who says you may collect rent here? A genuine agent can show a letter or agreement from the landlord. If the answer is a story, slow down.", "sub": "who says this person may collect rent?", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "GET TERMS IN WRITING", "say": "Before you pay, get the terms on paper: rent, agency fee, caution fee, start date, and who exactly receives each payment. Writing turns a conversation into something you can hold someone to.", "sub": "fees · dates · who receives payment", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "RECEIPT IN THE LANDLORD'S NAME", "say": "Pay into the landlord's account where you can, and make sure the receipt carries the landlord's name, not only the agent's. That receipt, kept with your agreement, proves you are the tenant.", "sub": "not the agent's — keep payment proof", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Skip the photos. Pay for old damage.",
        "parent": "dd2",
        "slides": [
            {"bg": NAVY, "text": "SKIP THE PHOTOS.\nPAY FOR OLD DAMAGE.", "say": "You move in and the wall is already cracked. You move out, and the landlord deducts repairs from your caution fee for damage you met there. Ten minutes on day one prevents it.", "sub": "moving in — make a simple record", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "PHOTOGRAPH EACH ROOM", "say": "The day you collect the keys, photograph every room wall by wall and film a slow walk through the flat. Get close to any damage: cracks, stains, broken fittings.", "sub": "include visible damage", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "NOTE THE DATE", "say": "Keep the original photos and videos, not copies forwarded through a chat app, because originals carry the date. Send the set to the landlord the same day, so the date is on record.", "sub": "keep original photos and videos", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "RECORD METER READINGS", "say": "Write down the electricity and water meter readings on the day you move in, and photograph the meters showing them. Your readings prove where your usage began.", "sub": "where applicable", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "SHARE ISSUES IN WRITING", "say": "Send the landlord or agent a short written list of what you found: the leaking tap, the cracked wall, the missing key. Keep the message and the reply.", "sub": "keep a copy of the message", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Sign without asking. Fund the repaint.",
        "parent": "dd2",
        "slides": [
            {"bg": NAVY, "text": "SIGN WITHOUT ASKING.\nFUND THE REPAINT.", "say": "A caution fee is meant to be refundable. But if nobody wrote down what it covers, the landlord decides at the end, and your deposit becomes his repainting budget. Ask four things first.", "sub": "caution fee — get the details first", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "ASK WHAT IT COVERS", "say": "Ask exactly what the caution fee is for and how much it is. Damage only, or also unpaid bills and cleaning? Get the figure and the purpose into the agreement itself.", "sub": "and how much it is", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "WRITE DOWN THE DEDUCTIONS", "say": "Agree in writing what may be deducted and for what. Normal wear from living in a place is not damage. When the agreement lists what counts, the end is a checklist, not an argument.", "sub": "what may be taken, and for what", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "FIX THE RETURN DATE", "say": "Agree when the deposit comes back and how. Fourteen days after you hand over the keys, by transfer, is common and reasonable. A refund with no date attached can wait forever.", "sub": "clarify the process and timeline", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "KEEP A SEPARATE RECEIPT", "say": "Get a separate receipt for the caution fee, showing the amount and the word deposit. Do not let it hide inside the rent receipt. Keep it with your agreement.", "sub": "save it with your agreement", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Sign it unread. Live by it anyway.",
        "parent": "yt:08wCJ0EmTkU",
        "slides": [
            {"bg": NAVY, "text": "SIGN IT UNREAD.\nLIVE BY IT ANYWAY.", "say": "Most people sign a tenancy agreement in the agent's office in under a minute, then live under it for a year. Read it slowly before you sign. These four parts matter most.", "sub": "tenancy agreement — check the key details", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "NAMES AND CONTACTS", "say": "Check that your full name and the landlord's full name are spelled correctly, and that a phone number and address for the landlord are written in. Wrong names protect nobody.", "sub": "are they written correctly?", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "PROPERTY AND RENT", "say": "Confirm the address is exact, down to the flat number, and that the rent, the period it covers and the payment date are stated in figures and in words. If they disagree, ask before you sign.", "sub": "check the address and amount", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "DATES AND RESPONSIBILITIES", "say": "Look for the start date, the end date, and who handles what: repairs, the generator, service charge, security. Every duty written down is one you cannot be surprised by later.", "sub": "who handles what, and when?", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "READ. ASK. KEEP A COPY.", "say": "Read every page, ask about any sentence you do not understand, then sign. Take a signed copy away with you that day, photograph every page, and keep it with your receipts.", "sub": "clarify anything you do not understand", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Report it by mouth. Own the repair bill.",
        "parent": "dd2",
        "slides": [
            {"bg": NAVY, "text": "REPORT IT BY MOUTH.\nOWN THE REPAIR BILL.", "say": "The roof leaks, you mention it to the caretaker, and months later the ceiling comes down. Now the landlord says you never told him. A written request changes who pays.", "sub": "need a repair — make the request clear", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "DESCRIBE THE ISSUE", "say": "Describe the problem clearly: what is wrong, where, since when, and what it is affecting. Leaking kitchen tap since Monday, water under the cabinet. Specific words get specific action.", "sub": "what happened and where", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "ADD A PHOTO IF USEFUL", "say": "Attach a photo or a short video that shows the problem, with the date visible or written in the message. A picture dated today settles when the landlord first knew.", "sub": "include the date", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "SEND IT IN WRITING", "say": "Send the request by text, chat or email, even if you also spoke in person. Keep your message and any reply. The written request proves the landlord was told, and when.", "sub": "keep your message and reply", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "SAVE THE REPAIR RECORD", "say": "Keep everything the repair produces: quotes, receipts, the date it was finished, photos of the finished work. If you paid yourself, that record is how you ask for the money back.", "sub": "quotes · receipts · completion date", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
]


def script_for_date(run_date: date):
    """The brain's Short for the date when it approved one, else the rotation's topic."""
    try:
        import brain_drafts
        pack = brain_drafts.draft_for(run_date)
        topic = brain_drafts.short_topic(pack) if pack else None
    except Exception:  # the rotation must never be lost to the brain
        topic = None
    if topic:
        return topic
    return VIDEO_SCRIPTS[(run_date.toordinal() - 1) % len(VIDEO_SCRIPTS)]


def get_font(size):
    """Get a font, falling back to default"""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def fit_font(draw, text, size, max_width, min_size=32):
    """Shrink a line until it fits the safe area of a portrait slide."""
    while size > min_size:
        font = get_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 2
    return get_font(min_size)


def add_film_grain(img, sigma=FILM_GRAIN_SIGMA):
    """Brand texture: zero-mean gaussian luminance noise (σ≈2.2).

    BRAND_STYLE.md §3 lists film grain as "always present" on every finished
    piece, video included. Pure PIL so the test job stays dependency-light:
    ImageChops.add(..., offset=-128) is img + (noise - 128) — zero-mean grain.
    """
    noise = Image.effect_noise((img.width, img.height), sigma).convert("RGB")
    return ImageChops.add(img, noise, scale=1.0, offset=-128)


def _text_height(draw, line, font):
    box = draw.textbbox((0, 0), line, font=font)
    return box[3] - box[1]


def create_slide_image(slide_data):
    """Render one slide.

    Deliberately takes no logo argument: see the locked brand rule at the top
    of this file. Text and the CTA bar are the only content.
    """
    bg_color = slide_data.get("bg", DARK)
    text = slide_data.get("text", "")
    sub = slide_data.get("sub", "")
    text_color = slide_data.get("color", WHITE)

    img = Image.new("RGB", (WIDTH, HEIGHT), bg_color)
    draw = ImageDraw.Draw(img)

    # Main text — shrink long lines so mobile viewers never lose cropped words.
    safe_width = WIDTH - 2 * SAFE_MARGIN
    lines = text.split("\n")
    main_fonts = [fit_font(draw, line, 72, safe_width) for line in lines]
    sub_lines = sub.split("\n") if sub else []
    sub_fonts = [fit_font(draw, line, 42, safe_width, min_size=26) for line in sub_lines]

    # Lay the block out as one unit and centre it above the CTA bar. The old
    # fixed y=600 start left every frame top-heavy with a dead gap beneath it.
    line_stride = 100
    sub_gap = 60
    sub_stride = 60
    block_h = (len(lines) - 1) * line_stride + _text_height(draw, lines[-1], main_fonts[-1])
    if sub_lines:
        block_h += sub_gap + (len(sub_lines) - 1) * sub_stride
        block_h += _text_height(draw, sub_lines[-1], sub_fonts[-1])

    content_h = HEIGHT - CTA_BAR_H
    y = max(SAFE_MARGIN, (content_h - block_h) // 2)

    for i, (line, font_main) in enumerate(zip(lines, main_fonts)):
        bbox = draw.textbbox((0, 0), line, font=font_main)
        tw = bbox[2] - bbox[0]
        tx = (WIDTH - tw) // 2 - bbox[0]
        ty = y + i * line_stride - bbox[1]
        # Shadow
        draw.text((tx + 3, ty + 3), line, fill=(0, 0, 0), font=font_main)
        draw.text((tx, ty), line, fill=text_color, font=font_main)

    if sub_lines:
        sub_y = (
            y
            + (len(lines) - 1) * line_stride
            + _text_height(draw, lines[-1], main_fonts[-1])
            + sub_gap
        )
        for i, (sline, font_sub) in enumerate(zip(sub_lines, sub_fonts)):
            bbox = draw.textbbox((0, 0), sline, font=font_sub)
            sw = bbox[2] - bbox[0]
            sx = (WIDTH - sw) // 2 - bbox[0]
            draw.text((sx, sub_y + i * sub_stride - bbox[1]), sline, fill=(200, 200, 200), font=font_sub)

    # CTA bar — brand checklist requires "CTA: docoga.com.ng present". Drawn
    # and centred with the real glyph box so the type never collides with the
    # bar edges (the old logo chip overlapped this bar on every slide).
    draw.rectangle([0, HEIGHT - CTA_BAR_H, WIDTH, HEIGHT], fill=BRAND_BLUE)
    font_cta = get_font(CTA_FONT_SIZE)
    box = draw.textbbox((0, 0), CTA_TEXT, font=font_cta)
    cw, ch = box[2] - box[0], box[3] - box[1]
    draw.text(
        ((WIDTH - cw) // 2 - box[0], HEIGHT - CTA_BAR_H + (CTA_BAR_H - ch) // 2 - box[1]),
        CTA_TEXT,
        fill=WHITE,
        font=font_cta,
    )

    # Grain last, over type and all, so "image + type = one texture".
    return add_film_grain(img)


def generate_video(script=None, output_path=None):
    """Generate a short-form video from a script."""
    if script is None:
        script = script_for_date(datetime.now().date())

    print(f"🎬 Generating video: {script['title']}")

    # No logo on these frames — locked brand rule, see the top of this file.
    slide_images = []
    for i, slide in enumerate(script["slides"]):
        img = create_slide_image(slide)
        slide_images.append((img, slide.get("duration", 3)))
        print(f"   📸 Slide {i+1}: {slide['text'][:30]}... ({slide['duration']}s)")

    if not MOVIEPY_AVAILABLE:
        raise RuntimeError("MoviePy is required for YouTube Shorts generation; refusing to emit a GIF.")

    # Use a date-based name in scheduled runs so a retry overwrites the same
    # generated file instead of leaving multiple ambiguous outputs.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = Path(output_path) if output_path else OUTPUT_DIR / f"docoga_short_{timestamp}.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)

    clips = []
    for img, duration in slide_images:
        tmp_path = OUTPUT_DIR / f"_tmp_slide_{len(clips)}.png"
        img.save(tmp_path)
        clip = ImageClip(str(tmp_path)).with_duration(duration)
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    final = final.with_fps(FPS)

    print(f"   🎥 Rendering {video_path}...")
    final.write_videofile(
        str(video_path),
        fps=FPS,
        codec="libx264",
        audio=False,
        preset="ultrafast",
        logger=None,
    )

    # Cleanup
    for tmp in OUTPUT_DIR.glob("_tmp_slide_*.png"):
        tmp.unlink()
    for clip in clips:
        clip.close()
    final.close()

    file_size = os.path.getsize(video_path)
    print(f"✅ Video saved: {video_path} ({file_size / 1024:.1f} KB)")
    return str(video_path), script["title"]


if __name__ == "__main__":
    print("🎬 DocOga Short Video Generator")
    print("🎨 Brand: NAVY #002040 | BLUE #0060e0 | SKY #0080e0")
    print("=" * 50)
    run_date = datetime.now().date()
    script = script_for_date(run_date)
    output_path = OUTPUT_DIR / f"docoga_short_{run_date:%Y%m%d}.mp4"
    video_path, title = generate_video(script=script, output_path=output_path)
    print(f"\n📊 Result:")
    print(f"   Title: {title}")
    print(f"   Path: {video_path}")
    print(f"   Format: MP4 {WIDTH}x{HEIGHT} (9:16)")
    print(f"   Ready for Telegram! ✅")