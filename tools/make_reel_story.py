#!/usr/bin/env python3
"""
DOCOGA STORY SET — Day 2: "REEL DROP NIGHT" (5 × 1080×1920)
Supports tonight's Reel 1 upload (7–9pm WAT).  Story-safe zones respected:
top 0–250 (IG username/time overlay) and bottom 1600+ (reply bar) stay clear.

Narrative law: strike = lawyer's price ONLY; our ₦2,000 = yellow underline;
"FREE." always carries "to start. No signup. No card."

Run: python3 tools/make_reel_story.py  →  social/rs-1..5.jpg
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, 'social')
W, H = 1080, 1920
MARGIN = 84
MAXW   = W - 2 * MARGIN

NAVY, RULE   = (6, 26, 51), (20, 41, 74)
PANEL        = (15, 61, 124)
WHITE, MUTED, FAINT = (255, 255, 255), (143, 168, 201), (96, 128, 170)
BLUE, YELLOW, RED, GREEN = (74, 140, 255), (255, 201, 60), (255, 90, 95), (46, 204, 107)

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

def tracked(d, xy, text, fnt, fill, tr=8):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textbbox((0, 0), ch, font=fnt)[2] + tr
    return x - tr

def track_width(d, text, fnt, tr):
    return sum(d.textbbox((0, 0), ch, font=fnt)[2] + tr for ch in text) - tr

def fit_font(d, text, w, sz, max_w=MAXW):
    while sz > 36:
        if d.textbbox((0, 0), text, font=font(w, sz))[2] <= max_w:
            return font(w, sz)
        sz -= 4
    return font(w, sz)

def header(d, kicker):
    """Story-safe header: below IG's top overlay (y≈250)."""
    x_end = tracked(d, (MARGIN, 292), kicker, font('SemiBold', 27), BLUE, 9)
    d.rectangle([x_end + 20, 300, x_end + 34, 314], fill=(0, 135, 81))
    d.rectangle([x_end + 34, 300, x_end + 48, 314], fill=WHITE)
    d.rectangle([x_end + 48, 300, x_end + 62, 314], fill=(0, 135, 81))
    f_tr = font('SemiBold', 22)
    tw = track_width(d, 'DOCOGA', f_tr, 5)
    tracked(d, (W - MARGIN - tw, 300), 'DOCOGA', f_tr, FAINT, 5)
    d.rectangle([MARGIN, 358, W - MARGIN, 359], fill=RULE)

def foot(d, text):
    tracked(d, (MARGIN, 1520), text, font('SemiBold', 22), FAINT, 5)

def base(kicker, foot_text):
    img = Image.new('RGB', (W, H), NAVY)
    d   = ImageDraw.Draw(img)
    header(d, kicker)
    foot(d, foot_text)
    return img, d

def save(img, n):
    import numpy as np
    arr = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(400 + n)
    noise = rng.normal(0, 2.2, arr.shape[:2])[..., None]
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8)).save(
        os.path.join(OUT, f'rs-{n}.jpg'), quality=95)
    print(f'✅ rs-{n}.jpg')


# ── 1. TONIGHT — the teaser ─────────────────────────────────────────────
img, d = base('NEW VIDEO · REELS', 'DOCOGA · TONIGHT 7PM WAT')
f1 = fit_font(d, 'TONIGHT.', 'Black', 210)
d.text((MARGIN, 560), 'TONIGHT.', font=f1, fill=WHITE)
f2 = fit_font(d, '7PM', 'Black', 150)
d.text((MARGIN, 560 + f1.size + 46), '7PM', font=f2, fill=YELLOW)
sup = fit_font(d, 'the story of the ₦50,000 document', 'Light', 52)
d.text((MARGIN, 560 + f1.size + 46 + f2.size + 64),
       'the story of the ₦50,000 document', font=sup, fill=MUTED)
save(img, 1)


# ── 2. THE HOOK — lawyer price, the one price a strike may touch ────────
img, d = base('REALITY CHECK', 'ONE TENANCY AGREEMENT · NIGERIA')
big = fit_font(d, '₦50,000.', 'Black', 230)
d.text((MARGIN, 580), '₦50,000.', font=big, fill=WHITE)
bb = d.textbbox((MARGIN, 580), '₦50,000.', font=big)
my = (bb[1] + bb[3]) // 2 + 14                      # strike through the digits' mid
d.rectangle([bb[0] - 8, my - 11, bb[2] + 8, my + 11], fill=RED)   # strike = rejection (lawyer only)
sup = fit_font(d, 'one lawyer. one tenancy agreement.', 'Light', 52)
d.text((MARGIN, bb[3] + 110), 'one lawyer. one tenancy agreement.', font=sup, fill=MUTED)
save(img, 2)


# ── 3. THE ANSWER — 2 minutes, our price underlined (never struck) ─────
img, d = base('THE OTHER WAY', 'DOCOGA · THE OGA PASS')
f1 = fit_font(d, '2 MINUTES.', 'Black', 180)
d.text((MARGIN, 540), '2 MINUTES.', font=f1, fill=WHITE)
f2 = fit_font(d, '₦2,000', 'Black', 150)
py = 540 + f1.size + 90
d.text((MARGIN, py), '₦2,000', font=f2, fill=WHITE)
pb = d.textbbox((MARGIN, py), '₦2,000', font=f2)
asc, _ = font('Black', f2.size).getmetrics()
uy = py + asc + 20                                   # underline = our price, owned
d.rectangle([pb[0], uy, pb[2], uy + 16], fill=YELLOW)
sup = fit_font(d, '30 days · every document · no lawyer', 'Light', 52)
d.text((MARGIN, uy + 90), '30 days · every document · no lawyer', font=sup, fill=MUTED)
save(img, 3)


# ── 4. THE POLL — engagement frame (poll sticker drops in-app) ──────────
img, d = base('TELL ME', 'POLL · DROP YOUR ANSWER')
q1, q2 = 'WHICH DOCUMENT', 'DO YOU NEED FIRST?'
d.text((MARGIN, 500), q1, font=fit_font(d, q1, 'Black', 120), fill=WHITE)
d.text((MARGIN, 500 + 140), q2, font=fit_font(d, q2, 'Black', 120), fill=BLUE)
opts = ['Tenancy Agreement', 'Rent Receipt', 'Notice to Quit', 'Invoice']
y = 920
for o in opts:
    f = fit_font(d, o, 'SemiBold', 48)
    d.rounded_rectangle([MARGIN, y, MARGIN + MAXW, y + 104], radius=26, fill=PANEL)
    d.text((MARGIN + 44, y + 26), o, font=f, fill=WHITE)
    y += 132
save(img, 4)


# ── 5. THE DOOR — FREE. to start (link sticker drops in-app) ────────────
img, d = base('START HERE', 'DOCOGA · YOUR DOCUMENTS. OUR PRIORITY.')
f1 = fit_font(d, 'FREE.', 'Black', 260)
d.text((MARGIN, 520), 'FREE.', font=f1, fill=WHITE)
sup = fit_font(d, 'to start. No signup. No card.', 'Light', 56)
d.text((MARGIN, 520 + f1.size + 70), 'to start. No signup. No card.', font=sup, fill=MUTED)
btn_t = 'docoga.com.ng'
fb = font('Black', 56)
bw = d.textbbox((0, 0), btn_t, font=fb)[2] + 120
bx, by = MARGIN, 520 + f1.size + 70 + sup.size + 110
d.rounded_rectangle([bx, by, bx + bw, by + 128], radius=28, fill=BLUE)
d.text((bx + 60, by + 30), btn_t, font=fb, fill=WHITE)
save(img, 5)

print('DONE — 5 frames')