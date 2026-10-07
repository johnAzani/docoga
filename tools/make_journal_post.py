#!/usr/bin/env python3
"""
DOCOGA JOURNAL — Issue 01: "Paper is power." (1080x1350, 4:5)
The photoreal test: ultra-realistic documentary photo, filmified
(soft focus + faded grade + vignette + heavy grain), full-bleed magazine
layout with gradient scrims melting it into the navy design world.

Run: python3 tools/make_journal_post.py  →  social/journal-1-paper.jpg
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from blend_image import crop_aspect, filmify, scrim

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, 'social')
W, H = 1080, 1350
MARGIN = 84
MAXW   = W - 2 * MARGIN

NAVY  = (6, 26, 51)
PANEL = (15, 61, 124)
WHITE, MUTED, FAINT = (255, 255, 255), (143, 168, 201), (96, 128, 170)
BLUE, YELLOW = (74, 140, 255), (255, 201, 60)

F = '/usr/share/fonts/opentype/inter/Inter-{}.otf'
try:
    from PIL import features
    RAQM = features.check('raqm')
except Exception:
    RAQM = False

def font(w, sz):
    if RAQM:
        return ImageFont.truetype(F.format(w), sz, layout_engine=ImageFont.Layout.RAQM)
    return ImageFont.truetype(F.format(w), sz)

def fit_font(d, text, w, sz, max_w=MAXW):
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

def fit_tracked(d, text, sz, max_w, tr=5):
    while sz > 20:
        f = font('SemiBold', sz)
        if track_width(d, text, f, tr) <= max_w:
            return f
        sz -= 2
    return font('SemiBold', sz)

def track_width(d, text, fnt, tr):
    return sum(d.textbbox((0, 0), ch, font=fnt)[2] + tr for ch in text) - tr


img = Image.new('RGB', (W, H), NAVY)


# ── the filmified photo, full-bleed top ─────────────────────────────────
raw_path = os.path.join(OUT, 'assets', 'raw', 'journal-paper-raw.png')
if os.path.exists(raw_path):
    raw = Image.open(raw_path).convert('RGB')
    photo = filmify(crop_aspect(raw, W, 780).resize((W, 780), Image.LANCZOS), seed=11)
    img.paste(photo, (0, 0))
    # melt into the design: dark scrim for the masthead, navy fade at the bottom
    img = scrim(img, NAVY, 0, 185, 205, 0)          # top: masthead readability
    img = scrim(img, NAVY, 585, 780, 0, 255)        # bottom: photo → navy melt
else:
    # fallback: navy panel with accent
    d_tmp = ImageDraw.Draw(img)
    d_tmp.rounded_rectangle([MARGIN, 120, W - MARGIN, 750], radius=44, fill=PANEL)

d = ImageDraw.Draw(img)


# ── masthead on the photo ───────────────────────────────────────────────
x_end = tracked(d, (MARGIN, 92), 'DOCOGA JOURNAL', font('SemiBold', 27), WHITE, 9)
d.rectangle([x_end + 20, 100, x_end + 34, 114], fill=(0, 135, 81))
d.rectangle([x_end + 34, 100, x_end + 48, 114], fill=WHITE)
d.rectangle([x_end + 48, 100, x_end + 62, 114], fill=(0, 135, 81))
f_tr = font('SemiBold', 22)
tw = track_width(d, 'ISSUE 01', f_tr, 5)
tracked(d, (W - MARGIN - tw, 100), 'ISSUE 01', f_tr, (208, 220, 238), 5)


# ── headline + copy ─────────────────────────────────────────────────────
d.text((MARGIN, 812), 'Paper is power.',
       font=fit_font(d, 'Paper is power.', 'Black', 112), fill=WHITE)
d.text((MARGIN, 962), 'Your receipt is your voice.',
       font=fit_font(d, 'Your receipt is your voice.', 'Light', 46), fill=MUTED)
d.rectangle([MARGIN, 1048, MARGIN + 180, 1062], fill=YELLOW)
line = 'RECEIPTS · AGREEMENTS · NOTICES — 2 MINUTES'
f_line = fit_tracked(d, line, 30, MAXW)
tw = track_width(d, line, f_line, 5)
tracked(d, (MARGIN, 1088), line, f_line, YELLOW, 5)


# ── CTA pill ────────────────────────────────────────────────────────────
bw, bh = 620, 112
bx, by = (W - bw) // 2, 1150
d.rounded_rectangle([bx + 12, by + 12, bx + bw + 12, by + bh + 12], radius=56, fill=PANEL)
d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=56, fill=WHITE)
fb = font('Bold', 46)
txt = 'docoga.com.ng'
tw = d.textbbox((0, 0), txt, font=fb)[2]
d.text(((W - tw) // 2, by + 32), txt, font=fb, fill=NAVY)


# ── footer marginalia ───────────────────────────────────────────────────
tracked(d, (MARGIN, 1284), 'DOCOGA JOURNAL — PROOF EDITION',
        font('SemiBold', 22), FAINT, 5)


# ── one shared film grain over everything ────────────────────────────────
arr = np.asarray(img).astype(np.int16)
rng = np.random.default_rng(200)
noise = rng.normal(0, 2.2, arr.shape[:2])[..., None]
img = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))
os.makedirs(OUT, exist_ok=True)
img.save(os.path.join(OUT, 'journal-1-paper.jpg'), quality=95)
print('✅ journal-1-paper.jpg (DOCOGA JOURNAL Issue 01, filmified photoreal)')


# spare asset: dusk street scene, filmified for the WhatsApp pack
street_path = os.path.join(OUT, 'assets', 'raw', 'journal-street-raw.png')
if os.path.exists(street_path):
    spare = filmify(Image.open(street_path).convert('RGB'), seed=12)
    os.makedirs(os.path.join(OUT, 'assets'), exist_ok=True)
    spare.save(os.path.join(OUT, 'assets', 'blend-street-treated.jpg'), quality=95)
    print('✅ assets/blend-street-treated.jpg (WhatsApp pack ammo)')
else:
    print('⚠️ journal-street-raw.png not found — skipping WhatsApp pack asset')