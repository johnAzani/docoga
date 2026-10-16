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
            {"bg": NAVY, "text": "PAY WITHOUT A RECEIPT.\nPAY TWICE.", "sub": "cash leaves no trail — paper does", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "TAKE THE RECEIPT", "sub": "on the day — not \"later\"", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "KEEP THE TRANSFER RECORD", "sub": "date · amount · reference", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "SAY WHAT IT WAS FOR", "sub": "\"rent, flat 4, Jan to Dec\" — keep the reply", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "ONE FOLDER. TWO PLACES.", "sub": "phone plus cloud — proof survives", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Pay the wrong agent. Lose the flat.",
        "parent": "dd3",
        "slides": [
            {"bg": NAVY, "text": "PAY THE WRONG AGENT.\nLOSE THE FLAT.", "sub": "verify before money moves", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "SEE THE PROPERTY", "sub": "in person, if you can", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "ASK FOR WRITTEN AUTHORITY", "sub": "who says this person may collect rent?", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "GET TERMS IN WRITING", "sub": "fees · dates · who receives payment", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "RECEIPT IN THE LANDLORD'S NAME", "sub": "not the agent's — keep payment proof", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Skip the photos. Pay for old damage.",
        "parent": "dd2",
        "slides": [
            {"bg": NAVY, "text": "SKIP THE PHOTOS.\nPAY FOR OLD DAMAGE.", "sub": "moving in — make a simple record", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "PHOTOGRAPH EACH ROOM", "sub": "include visible damage", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "NOTE THE DATE", "sub": "keep original photos and videos", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "RECORD METER READINGS", "sub": "where applicable", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "SHARE ISSUES IN WRITING", "sub": "keep a copy of the message", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Sign without asking. Fund the repaint.",
        "parent": "dd2",
        "slides": [
            {"bg": NAVY, "text": "SIGN WITHOUT ASKING.\nFUND THE REPAINT.", "sub": "caution fee — get the details first", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "ASK WHAT IT COVERS", "sub": "and how much it is", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "WRITE DOWN THE DEDUCTIONS", "sub": "what may be taken, and for what", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "FIX THE RETURN DATE", "sub": "clarify the process and timeline", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "KEEP A SEPARATE RECEIPT", "sub": "save it with your agreement", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Sign it unread. Live by it anyway.",
        "parent": "yt:08wCJ0EmTkU",
        "slides": [
            {"bg": NAVY, "text": "SIGN IT UNREAD.\nLIVE BY IT ANYWAY.", "sub": "tenancy agreement — check the key details", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "NAMES AND CONTACTS", "sub": "are they written correctly?", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "PROPERTY AND RENT", "sub": "check the address and amount", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "DATES AND RESPONSIBILITIES", "sub": "who handles what, and when?", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "READ. ASK. KEEP A COPY.", "sub": "clarify anything you do not understand", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Report it by mouth. Own the repair bill.",
        "parent": "dd2",
        "slides": [
            {"bg": NAVY, "text": "REPORT IT BY MOUTH.\nOWN THE REPAIR BILL.", "sub": "need a repair — make the request clear", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "DESCRIBE THE ISSUE", "sub": "what happened and where", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "ADD A PHOTO IF USEFUL", "sub": "include the date", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "SEND IT IN WRITING", "sub": "keep your message and reply", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "SAVE THE REPAIR RECORD", "sub": "quotes · receipts · completion date", "color": WHITE, "duration": 4},
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