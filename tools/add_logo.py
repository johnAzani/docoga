#!/usr/bin/env python3
"""
DocOga LOGO COMPOSITOR — the only way the official logo ever touches a design.
The AI image generator NEVER draws the logo.  This script pastes the REAL file
(brand/official-logo-transparent.png) — unchanged design, unchanged colours —
on a clean white rounded chip, bottom center.

Usage: python3 tools/add_logo.py social/carousel-1.jpg [more.jpg ...]
       (raw, logo-free versions are kept in social/raw/)
"""
import sys, os
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = os.path.join(ROOT, 'brand', 'official-logo-transparent.png')


def process(path):
    img = Image.open(path).convert('RGB')
    W, H = img.size

    # raw backup (logo-free) for future re-layouts
    raw_dir = os.path.join(os.path.dirname(path), 'raw')
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, os.path.basename(path))
    if not os.path.exists(raw_path):
        img.save(raw_path, quality=95)

    # --- logo: crop to content, keep exact pixels ---
    logo = Image.open(LOGO).convert('RGBA')
    bbox = logo.getbbox()          # non-transparent content
    logo = logo.crop(bbox)
    lw, lh = logo.size

    # --- chip sizing: logo occupies ~26% of image width, chip adds padding ---
    target_lw = int(W * 0.26)
    target_lh = int(target_lw * lh / lw)
    if target_lh > int(H * 0.20):   # keep chip modest
        target_lh = int(H * 0.20)
        target_lw = int(target_lh * lw / lh)
    pad = int(target_lw * 0.16)
    chip_w, chip_h = target_lw + 2 * pad, target_lh + 2 * pad
    chip_x = (W - chip_w) // 2
    chip_y = H - chip_h - int(H * 0.035)

    # --- draw on RGBA overlay: soft shadow + white rounded chip ---
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d  = ImageDraw.Draw(ov)
    rad = int(chip_h * 0.22)

    # shadow
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    ds.rounded_rectangle(
        [chip_x, chip_y + 6, chip_x + chip_w, chip_y + chip_h + 6],
        radius=rad, fill=(0, 0, 30, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    ov = Image.alpha_composite(sh, ov)

    # chip
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle(
        [chip_x, chip_y, chip_x + chip_w, chip_y + chip_h],
        radius=rad, fill=(255, 255, 255, 255))

    # --- paste logo (exact colours, only scaled) ---
    logo_scaled = logo.resize((target_lw, target_lh), Image.LANCZOS)
    ov.alpha_composite(logo_scaled, (chip_x + pad, chip_y + pad))

    out = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    out.save(path, quality=95)
    print(f"✅ {path}: official logo composited (chip {chip_w}x{chip_h}px, bottom center)")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        process(p)