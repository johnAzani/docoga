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
import random
from datetime import datetime
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


# ===== CONTENT SCRIPTS =====
VIDEO_SCRIPTS = [
    {
        "title": "Caution Fee Warning",
        "slides": [
            {"bg": DARK,       "text": "⚠️ STOP!", "sub": "", "color": RED, "duration": 3},
            {"bg": DARK,       "text": "Don't pay Caution Fee\nwithout a RECEIPT!", "sub": "Many landlords no dey refund...", "color": WHITE, "duration": 4},
            {"bg": DARK,       "text": "80% of tenants", "sub": "lose their caution fee\nevery year in Nigeria", "color": RED, "duration": 4},
            {"bg": NAVY,       "text": "3 THINGS TO DO:", "sub": "", "color": YELLOW, "duration": 2},
            {"bg": NAVY,       "text": "1️⃣ Get receipt BEFORE paying", "sub": "", "color": WHITE, "duration": 3},
            {"bg": NAVY,       "text": "2️⃣ Snap the apartment\nbefore you move in", "sub": "", "color": WHITE, "duration": 3},
            {"bg": NAVY,       "text": "3️⃣ Add it to your\ntenancy agreement", "sub": "", "color": WHITE, "duration": 3},
            {"bg": DARK,       "text": "Need documents?", "sub": "DocOga dey for you!", "color": SKY_BLUE, "duration": 3},
            {"bg": BRAND_BLUE, "text": "docoga.com.ng", "sub": "FREE templates!", "color": WHITE, "duration": 3},
            {"bg": NAVY,       "text": "🔔 Follow for\ndaily tips!", "sub": "", "color": YELLOW, "duration": 3},
        ],
    },
    {
        "title": "Know Your Tenant Rights",
        "slides": [
            {"bg": NAVY,       "text": "🏠 TENANT RIGHTS", "sub": "Nigeria Edition", "color": SKY_BLUE, "duration": 3},
            {"bg": DARK,       "text": "Your landlord\ncan NOT just\nevict you!", "sub": "Na your right!", "color": YELLOW, "duration": 4},
            {"bg": DARK,       "text": "They must give you:", "sub": "", "color": WHITE, "duration": 2},
            {"bg": DARK,       "text": "📋 Written Notice", "sub": "Minimum 6 months\nfor yearly tenants", "color": SKY_BLUE, "duration": 4},
            {"bg": DARK,       "text": "📜 Notice to Quit", "sub": "Must follow legal process", "color": SKY_BLUE, "duration": 4},
            {"bg": DARK,       "text": "⚖️ Court Order", "sub": "If you refuse to leave", "color": SKY_BLUE, "duration": 4},
            {"bg": DARK,       "text": "Don't let anyone\nrush you out!", "sub": "Know your rights! 💪", "color": YELLOW, "duration": 4},
            {"bg": BRAND_BLUE, "text": "Get proper docs at", "sub": "docoga.com.ng", "color": WHITE, "duration": 3},
            {"bg": NAVY,       "text": "🔔 Follow DocOga", "sub": "for daily property tips!", "color": YELLOW, "duration": 3},
        ],
    },
    {
        "title": "Rent Receipt vs Tenancy Agreement",
        "slides": [
            {"bg": NAVY,       "text": "📄 KNOW THE DIFFERENCE", "sub": "", "color": YELLOW, "duration": 3},
            {"bg": DARK,       "text": "RENT RECEIPT", "sub": "Proof you don pay rent", "color": SKY_BLUE, "duration": 4},
            {"bg": DARK,       "text": "Shows:\n• Amount paid\n• Date\n• Landlord name\n• Property address", "sub": "", "color": WHITE, "duration": 5},
            {"bg": DARK,       "text": "TENANCY AGREEMENT", "sub": "Your protection document", "color": SKY_BLUE, "duration": 4},
            {"bg": DARK,       "text": "Shows:\n• Rent amount\n• Duration\n• Rules & terms\n• Both signatures", "sub": "", "color": WHITE, "duration": 5},
            {"bg": RED,        "text": "YOU NEED BOTH!", "sub": "No just one o!", "color": YELLOW, "duration": 3},
            {"bg": DARK,       "text": "DocOga fit generate\nboth for you!", "sub": "In 2 minutes! ⚡", "color": SKY_BLUE, "duration": 4},
            {"bg": BRAND_BLUE, "text": "docoga.com.ng", "sub": "Free to try!", "color": WHITE, "duration": 3},
            {"bg": NAVY,       "text": "🔔 Follow for more!", "sub": "", "color": YELLOW, "duration": 3},
        ],
    },
    {
        "title": "Landlord Scam Alert",
        "slides": [
            {"bg": DARK,       "text": "🚨 SCAM ALERT!", "sub": "", "color": RED, "duration": 3},
            {"bg": NAVY,       "text": "5 Ways Your\nLandlord Fit\nChop Your Money", "sub": "", "color": YELLOW, "duration": 4},
            {"bg": DARK,       "text": "1. No receipt for\n   caution fee", "sub": " = No refund", "color": RED, "duration": 3},
            {"bg": DARK,       "text": "2. Verbal agreement\n   only", "sub": " = No proof", "color": RED, "duration": 3},
            {"bg": DARK,       "text": "3. Rent increase\n   without notice", "sub": " = Illegal!", "color": RED, "duration": 3},
            {"bg": DARK,       "text": "4. No inspection\n   before you enter", "sub": " = You pay for damage\nyou never cause", "color": RED, "duration": 3},
            {"bg": DARK,       "text": "5. No tenancy\n   agreement", "sub": " = Zero protection", "color": RED, "duration": 3},
            {"bg": BRAND_BLUE, "text": "Protect yourself!", "sub": "Get proper documents\nat docoga.com.ng", "color": WHITE, "duration": 4},
            {"bg": NAVY,       "text": "🔔 Follow DocOga!", "sub": "Don't get scammed!", "color": YELLOW, "duration": 3},
        ],
    },
    {
        "title": "How to Rent in Lagos",
        "slides": [
            {"bg": BRAND_BLUE, "text": "🏠 HOW TO RENT\nIN LAGOS", "sub": "2026 Guide", "color": WHITE, "duration": 3},
            {"bg": DARK,       "text": "Step 1:", "sub": "Find house through\ntrusted agents only", "color": YELLOW, "duration": 4},
            {"bg": DARK,       "text": "Step 2:", "sub": "Inspect the house\nbefore paying anything!", "color": YELLOW, "duration": 4},
            {"bg": DARK,       "text": "Step 3:", "sub": "Get tenancy agreement\nBEFORE you pay", "color": YELLOW, "duration": 4},
            {"bg": DARK,       "text": "Step 4:", "sub": "Pay via bank transfer\nNEVER cash!", "color": YELLOW, "duration": 4},
            {"bg": DARK,       "text": "Step 5:", "sub": "Collect receipt for\nevery payment!", "color": YELLOW, "duration": 4},
            {"bg": RED,        "text": "⚠️ If landlord say\nno to any of these...", "sub": "RUN! 🏃‍♂️", "color": YELLOW, "duration": 3},
            {"bg": BRAND_BLUE, "text": "DocOga has all the\ndocuments you need!", "sub": "docoga.com.ng", "color": WHITE, "duration": 4},
            {"bg": NAVY,       "text": "🔔 Follow for\nmore Lagos tips!", "sub": "", "color": YELLOW, "duration": 3},
        ],
    },
]


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

    # Main text
    font_main = get_font(72)
    lines = text.split("\n")
    y_start = 700 if (logo_path and os.path.exists(logo_path)) else 600

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_main)
        tw = bbox[2] - bbox[0]
        tx = (WIDTH - tw) // 2
        ty = y_start + i * 100
        # Shadow
        draw.text((tx + 3, ty + 3), line, fill=(0, 0, 0), font=font_main)
        draw.text((tx, ty), line, fill=text_color, font=font_main)

    # Subtitle
    if sub:
        font_sub = get_font(42)
        sub_lines = sub.split("\n")
        sub_y = y_start + len(lines) * 100 + 60
        for i, sline in enumerate(sub_lines):
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


def generate_video(script=None):
    """Generate a short-form video from a script"""
    if script is None:
        script = random.choice(VIDEO_SCRIPTS)

    print(f"🎬 Generating video: {script['title']}")

    # Create slide images with official logo composited
    slide_images = []
    for i, slide in enumerate(script["slides"]):
        img = create_slide_image(slide, logo_path=None)  # no inline logo
        img = add_official_logo(img)  # composite real logo via chip
        slide_images.append((img, slide.get("duration", 3)))
        print(f"   📸 Slide {i+1}: {slide['text'][:30]}... ({slide['duration']}s)")

    if not MOVIEPY_AVAILABLE:
        print("⚠️ moviepy not available, saving as GIF")
        gif_path = OUTPUT_DIR / f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.gif"
        pil_frames = []
        for img, duration in slide_images:
            pil_frames.extend([img] * int(duration * 2))
        pil_frames[0].save(gif_path, save_all=True, append_images=pil_frames[1:], duration=500, loop=0)
        print(f"✅ Saved GIF: {gif_path}")
        return str(gif_path), script["title"]

    # Generate MP4 with moviepy
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_path = OUTPUT_DIR / f"docoga_short_{timestamp}.mp4"

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
    video_path, title = generate_video()
    print(f"\n📊 Result:")
    print(f"   Title: {title}")
    print(f"   Path: {video_path}")
    print(f"   Format: MP4 {WIDTH}x{HEIGHT} (9:16)")
    print(f"   Ready for Telegram! ✅")