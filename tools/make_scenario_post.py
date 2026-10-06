#!/usr/bin/env python3
"""
DocOga POST #2 — "Rent Day" scenario single (1080x1350, 4:5 = max IG feed area).

First production use of the BLEND PIPELINE: generated editorial illustration
-> duotone -> feathered into the canvas -> grid-anchored, type stays hero.

Run: python3 tools/make_scenario_post.py   -> social/post-2-rentday.jpg
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from blend_image import treat, feather_paste

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'social')
W, H = 1080, 1350                    # 4:5 portrait — IG feed single
MARGIN = 84
MAXW = W - 2 * MARGIN

NAVY, RULE = (6, 26, 51), (20, 41, 74)
WHITE, MUTED, FAINT = (255, 255, 255), (143, 168, 201), (96, 128, 170)
BLUE, YELLOW = (74, 140, 255), (255, 201, 60)

F = os.path.join(ROOT, 'tools', 'fonts', 'Inter-Variable.ttf')

_fc = {}
def font(w, sz):
    key = (w, sz)
    if key not in _fc:
        _f = ImageFont.truetype(F, sz)
        try: _f.set_variation_by_name(w)
        except Exception: pass
        _fc[key] = _f
    return _fc[key]

def fit_font(d, text, w, sz, max_w):
    while sz > 40:
        f = font(w, sz)
        if d.textbbox((0, 0), text, font=f)[2] <= max_w:
            return f
        sz -= 4
    return font(w, sz)

def tracked(d, xy, text, fnt, fill, tr=8):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textbbox((0, 0), ch, font=fnt)[2] + tr
    return x - tr

def track_width(d, text, fnt, tr):
    return sum(d.textbbox((0, 0), ch, font=fnt)[2] + tr for ch in text) - tr


def make_post():
    img = Image.new('RGB', (W, H), NAVY)
    d = ImageDraw.Draw(img)

    # header system (same grid as the carousel)
    x_end = tracked(d, (MARGIN, 92), 'RENT DAY', font('SemiBold', 27), BLUE, 9)
    d.rectangle([x_end + 20, 100, x_end + 34, 114], fill=(0, 135, 81))
    d.rectangle([x_end + 34, 100, x_end + 48, 114], fill=WHITE)
    d.rectangle([x_end + 48, 100, x_end + 62, 114], fill=(0, 135, 81))
    f_tr = font('SemiBold', 22)
    tw = track_width(d, 'SCENARIO', f_tr, 5)
    tracked(d, (W - MARGIN - tw, 100), 'SCENARIO', f_tr, FAINT, 5)
    d.rectangle([MARGIN, 158, W - MARGIN, 159], fill=RULE)

    # ── the blended illustration (grid region, feathered, duotoned) ──
    art_src = Image.open(os.path.join(OUT, 'assets', 'raw', 'rentday-raw.png')).convert('RGB')
    art = treat(art_src, 812, 640)                       # crop to region aspect
    feather_paste(img, art, (MARGIN, 196, W - MARGIN, 836))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([MARGIN, 196, W - MARGIN, 836], radius=44,
                        outline=(15, 61, 124), width=3)  # royal frame ties it to the grid

    # ── typography (the hero stays type) ──
    d.text((MARGIN, 892), 'Every kobo.', font=fit_font(d, 'Every kobo.', 'Black', 96, MAXW), fill=WHITE)
    d.text((MARGIN, 1000), 'Every receipt.', font=fit_font(d, 'Every receipt.', 'Black', 96, MAXW), fill=WHITE)
    d.rectangle([MARGIN, 1136, MARGIN + 180, 1150], fill=YELLOW)          # yellow sweep
    d.text((MARGIN, 1180), 'Rent receipts and agreements — 2 minutes flat.',
           font=fit_font(d, 'Rent receipts and agreements — 2 minutes flat.', 'Light', 42, MAXW),
           fill=MUTED)
    tracked(d, (MARGIN, 1272), 'RECEIPTS THAT PROTECT YOU', font('SemiBold', 22), FAINT, 5)
    f_cta = font('SemiBold', 30)
    tw = track_width(d, 'docoga.com.ng', f_cta, 2)
    tracked(d, (W - MARGIN - tw, 1268), 'docoga.com.ng', f_cta, BLUE, 2)

    # ── one film grain over everything (image + type share the texture) ──
    import numpy as np
    arr = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(42 + 2)
    noise = rng.normal(0, 2.2, arr.shape[:2])[..., None]
    img = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))

    os.makedirs(OUT, exist_ok=True)
    img.save(os.path.join(OUT, 'post-2-rentday.jpg'), quality=95)
    print('✅ post-2-rentday.jpg (4:5, blend pipeline v1)')

    # spare asset for the WhatsApp pack: phone illustration, treated
    art2 = treat(Image.open(os.path.join(OUT, 'assets', 'raw', 'phone-raw.png')).convert('RGB'), 1, 1)
    art2.save(os.path.join(OUT, 'assets', 'blend-phone-treated.jpg'), quality=95)
    print('✅ assets/blend-phone-treated.jpg (WhatsApp pack ammo)')


if __name__ == '__main__':
    make_post()