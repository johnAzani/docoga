#!/usr/bin/env python3
"""
DocOga Short-Form Video Generator
Creates 30-60 second vertical videos (9:16) for Telegram, YouTube Shorts, Reels
Uses moviepy with FFmpeg for video creation

BRAND COLORS (from official-logo-white.png):
  Navy:        #002040  RGB(0, 32, 64)
  Brand Blue:  #0060e0  RGB(0, 96, 224)
  Royal Blue:  #0040c0  RGB(0, 64, 192)
  Sky Blue:    #0080e0  RGB(0, 128, 224)
"""

import os
from datetime import date, datetime
from pathlib import Path

try:
    from moviepy import ImageClip, concatenate_videoclips
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

from PIL import Image, ImageDraw, ImageFont

# ===== CONFIG =====
WIDTH = 1080
HEIGHT = 1920
FPS = 24
OUTPUT_DIR = Path("assets/videos")
BRAND_DIR = Path("brand")
LOGO_PATH = BRAND_DIR / "official-logo-white.png"

# ===== BRAND COLORS (from official-logo-white.png) =====
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
VIDEO_SCRIPTS = [
    {
        "title": "Keep a Rent Paper Trail",
        "slides": [
            {"bg": NAVY, "text": "KEEP A PAPER TRAIL", "sub": "for every rent payment", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "SAVE YOUR RECEIPT", "sub": "after each payment", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "KEEP THE TRANSFER RECORD", "sub": "date · amount · reference", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "SAVE YOUR AGREEMENT", "sub": "and messages about changes", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "ONE FOLDER. EASY TO FIND.", "sub": "Keep copies somewhere safe", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Before You Pay an Agent",
        "slides": [
            {"bg": NAVY, "text": "BEFORE YOU PAY", "sub": "pause and verify", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "SEE THE PROPERTY", "sub": "in person, if you can", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "CHECK WHO IS LETTING IT", "sub": "ask how they are authorised", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "GET TERMS IN WRITING", "sub": "fees · dates · who receives payment", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "KEEP PAYMENT PROOF", "sub": "and ask for a receipt", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Moving In? Record the Condition",
        "slides": [
            {"bg": NAVY, "text": "MOVING IN?", "sub": "make a simple record", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "PHOTOGRAPH EACH ROOM", "sub": "include visible damage", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "NOTE THE DATE", "sub": "keep original photos and videos", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "RECORD METER READINGS", "sub": "where applicable", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "SHARE ISSUES IN WRITING", "sub": "keep a copy of the message", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Caution Fee: Ask These Questions",
        "slides": [
            {"bg": NAVY, "text": "CAUTION FEE?", "sub": "get the details first", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "HOW MUCH IS IT?", "sub": "ask what the payment covers", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "WHAT CAN BE DEDUCTED?", "sub": "ask for the conditions in writing", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "WHEN IS IT RETURNED?", "sub": "clarify the process and timeline", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "KEEP A SEPARATE RECEIPT", "sub": "save it with your agreement", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Tenancy Agreement Checklist",
        "slides": [
            {"bg": NAVY, "text": "BEFORE YOU SIGN", "sub": "check the key details", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "NAMES AND CONTACTS", "sub": "are they written correctly?", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "PROPERTY AND RENT", "sub": "check the address and amount", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "DATES AND RESPONSIBILITIES", "sub": "who handles what, and when?", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "READ. ASK. KEEP A COPY.", "sub": "clarify anything you do not understand", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
    {
        "title": "Keep Records of Repairs",
        "slides": [
            {"bg": NAVY, "text": "NEED A REPAIR?", "sub": "make the request clear", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK, "text": "DESCRIBE THE ISSUE", "sub": "what happened and where", "color": WHITE, "duration": 4},
            {"bg": DARK, "text": "ADD A PHOTO IF USEFUL", "sub": "include the date", "color": YELLOW, "duration": 4},
            {"bg": DARK, "text": "SEND IT IN WRITING", "sub": "keep your message and reply", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "SAVE THE REPAIR RECORD", "sub": "quotes · receipts · completion date", "color": WHITE, "duration": 4},
            {"bg": NAVY, "text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement", "color": YELLOW, "duration": 4},
        ],
    },
]


def script_for_date(run_date: date):
    """Return a repeatable topic for a local calendar date."""
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


def create_slide_image(slide_data, logo_path=None):
    """Create a single slide as a PIL Image"""
    bg_color = slide_data.get("bg", DARK)
    text = slide_data.get("text", "")
    sub = slide_data.get("sub", "")
    text_color = slide_data.get("color", WHITE)

    img = Image.new("RGB", (WIDTH, HEIGHT), bg_color)
    draw = ImageDraw.Draw(img)

    # Add logo at top if exists
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo_max = 300
            ratio = min(logo_max / logo.width, logo_max / logo.height)
            new_w = int(logo.width * ratio)
            new_h = int(logo.height * ratio)
            logo = logo.resize((new_w, new_h), Image.LANCZOS)
            logo_x = (WIDTH - new_w) // 2
            img.paste(logo, (logo_x, 80), logo if logo.mode == "RGBA" else None)
        except Exception:
            pass

    # Main text — shrink long lines so mobile viewers never lose cropped words.
    lines = text.split("\n")
    y_start = 700 if (logo_path and os.path.exists(logo_path)) else 600
    safe_width = WIDTH - 120

    for i, line in enumerate(lines):
        font_main = fit_font(draw, line, 72, safe_width)
        bbox = draw.textbbox((0, 0), line, font=font_main)
        tw = bbox[2] - bbox[0]
        tx = (WIDTH - tw) // 2
        ty = y_start + i * 100
        # Shadow
        draw.text((tx + 3, ty + 3), line, fill=(0, 0, 0), font=font_main)
        draw.text((tx, ty), line, fill=text_color, font=font_main)

    # Subtitle
    if sub:
        sub_lines = sub.split("\n")
        sub_y = y_start + len(lines) * 100 + 60
        for i, sline in enumerate(sub_lines):
            font_sub = fit_font(draw, sline, 42, safe_width, min_size=26)
            bbox = draw.textbbox((0, 0), sline, font=font_sub)
            sw = bbox[2] - bbox[0]
            sx = (WIDTH - sw) // 2
            draw.text((sx, sub_y + i * 60), sline, fill=(200, 200, 200), font=font_sub)

    # Bottom bar — BRAND_BLUE
    draw.rectangle([0, HEIGHT - 100, WIDTH, HEIGHT], fill=BRAND_BLUE)
    font_brand = get_font(32)
    bbox = draw.textbbox((0, 0), "DOCOGA.COM.NG", font=font_brand)
    bw = bbox[2] - bbox[0]
    draw.text(((WIDTH - bw) // 2, HEIGHT - 70), "DOCOGA.COM.NG", fill=WHITE, font=font_brand)

    return img


def add_official_logo(img):
    """
    Composite the REAL official logo onto a PIL Image using the same
    approach as tools/add_logo.py: white rounded chip, bottom center.
    Never redraws the logo — pastes the exact pixels from brand/official-logo-transparent.png.
    """
    from PIL import ImageFilter
    
    logo_path = BRAND_DIR / "official-logo-transparent.png"
    if not logo_path.exists():
        return img
    
    img = img.convert("RGBA")
    W, H = img.size
    
    logo = Image.open(logo_path).convert("RGBA")
    bbox = logo.getbbox()
    if bbox:
        logo = logo.crop(bbox)
    lw, lh = logo.size
    
    # Chip sizing: logo ~26% of image width
    target_lw = int(W * 0.26)
    target_lh = int(target_lw * lh / lw)
    if target_lh > int(H * 0.20):
        target_lh = int(H * 0.20)
        target_lw = int(target_lh * lw / lh)
    pad = int(target_lw * 0.16)
    chip_w, chip_h = target_lw + 2 * pad, target_lh + 2 * pad
    chip_x = (W - chip_w) // 2
    chip_y = H - chip_h - int(H * 0.035)
    
    rad = int(chip_h * 0.22)
    
    # Shadow
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    ds.rounded_rectangle(
        [chip_x, chip_y + 6, chip_x + chip_w, chip_y + chip_h + 6],
        radius=rad, fill=(0, 0, 30, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, sh)
    
    # White chip
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle(
        [chip_x, chip_y, chip_x + chip_w, chip_y + chip_h],
        radius=rad, fill=(255, 255, 255, 255))
    
    # Paste logo (exact colours, only scaled)
    logo_scaled = logo.resize((target_lw, target_lh), Image.LANCZOS)
    ov.alpha_composite(logo_scaled, (chip_x + pad, chip_y + pad))
    
    img = Image.alpha_composite(img, ov)
    return img.convert("RGB")


def generate_video(script=None, output_path=None):
    """Generate a short-form video from a script."""
    if script is None:
        script = script_for_date(datetime.now().date())

    print(f"🎬 Generating video: {script['title']}")

    # Create slide images with official logo composited
    slide_images = []
    for i, slide in enumerate(script["slides"]):
        img = create_slide_image(slide, logo_path=None)  # no inline logo
        img = add_official_logo(img)  # composite real logo via chip
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