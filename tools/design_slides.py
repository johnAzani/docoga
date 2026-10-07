#!/usr/bin/env python3
"""
DocOga SOCIAL DESIGN SYSTEM v3 — editorial art direction, typographic.
Craft principles: extreme scale contrast (Black display vs Light body),
color-blocked panels, tonal watermark glyphs bleeding off-canvas,
editorial marginalia, strict 84px grid, auto-fit (no overflow ever).
NO logo stamped — brand carried by wordmark type + tagline (user direction).

Usage: python3 tools/design_slides.py   → writes social/carousel-1..6.jpg
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'social')
W = H = 1080
MARGIN = 84
MAXW = W - 2 * MARGIN  # 912

NAVY    = (6, 26, 51)     # canvas
WM_INK  = (13, 42, 79)    # tonal watermark (one step lighter than navy)
PANEL   = (15, 61, 124)   # royal color block
RULE    = (20, 41, 74)    # hairlines
WHITE   = (255, 255, 255)
MUTED   = (143, 168, 201)
FAINT   = (96, 128, 170)  # marginalia
BLUE    = (74, 140, 255)
YELLOW  = (255, 201, 60)
RED     = (255, 90, 95)

F = '/usr/share/fonts/opentype/inter/Inter-{}.otf'
try:
    from PIL import features
    RAQM = features.check('raqm')
except Exception:
    RAQM = False

def font(weight, size):
    """RAQM layout = true kerning + ligatures (professional typesetting)"""
    if RAQM:
        return ImageFont.truetype(F.format(weight), size, layout_engine=ImageFont.Layout.RAQM)
    return ImageFont.truetype(F.format(weight), size)

def fit_font(draw, text, weight, size, max_w):
    """auto-fit: no headline can ever overflow the grid"""
    while size > 40:
        f = font(weight, size)
        if draw.textbbox((0, 0), text, font=f)[2] <= max_w:
            return f
        size -= 4
    return font(weight, size)

def track_width(draw, text, fnt, tracking):
    return sum(draw.textbbox((0, 0), ch, font=fnt)[2] + tracking for ch in text) - tracking

def tracked(draw, xy, text, fnt, fill, tracking=8):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textbbox((0, 0), ch, font=fnt)[2] + tracking
    return x - tracking

def arrow(draw, x, y, color):
    """drawn arrow (never a missing-glyph box) — 32px tall, matches 30px labels"""
    draw.rectangle([x, y + 13, x + 46, y + 18], fill=color)
    draw.polygon([(x + 44, y + 3), (x + 66, y + 15), (x + 44, y + 27)], fill=color)

def watermark(img, glyph, cx, cy, size):
    """giant tonal glyph, deliberately bleeding off-canvas = depth without noise"""
    d = ImageDraw.Draw(img)
    f = font('Black', size)
    bb = d.textbbox((0, 0), glyph, font=f)
    d.text((cx - (bb[2] - bb[0]) // 2 - bb[0], cy - (bb[3] - bb[1]) // 2 - bb[1]),
           glyph, font=f, fill=WM_INK)

def header(d, kicker, topright):
    x_end = tracked(d, (MARGIN, 92), kicker, font('SemiBold', 27), BLUE, 9)
    fx = x_end + 20                                    # stylized flag: green-white-green
    d.rectangle([fx, 100, fx + 14, 112], fill=(0, 135, 81))
    d.rectangle([fx + 14, 100, fx + 28, 112], fill=WHITE)
    d.rectangle([fx + 28, 100, fx + 42, 112], fill=(0, 135, 81))
    f_tr = font('SemiBold', 22)
    tw = track_width(d, topright, f_tr, 5)
    tracked(d, (W - MARGIN - tw, 100), topright, f_tr, FAINT, 5)
    d.rectangle([MARGIN, 158, W - MARGIN, 159], fill=RULE)   # hairline

def foot(d, text):
    tracked(d, (MARGIN, 982), text, font('SemiBold', 22), FAINT, 5)

def add_grain(img, seed, sigma=2.2):
    """fine film grain — kills the flat digital-rectangle look (matte print feel)"""
    import numpy as np
    arr = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(42 + seed)
    noise = rng.normal(0, sigma, arr.shape[:2])[..., None]
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))

def save(img, n):
    os.makedirs(OUT, exist_ok=True)
    add_grain(img, n).save(os.path.join(OUT, f'carousel-{n}.jpg'), quality=95)
    print(f'✅ carousel-{n}.jpg')


# ── SLIDE 1 — the price shock ──────────────────────────────────────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
watermark(img, '₦', 790, 560, 1000)
d = ImageDraw.Draw(img)
header(d, 'TENANCY AGREEMENT FEES', 'NIGERIA · 2026')
f_big = fit_font(d, '₦50,000', 'Black', 215, MAXW)
bb = d.textbbox((0, 0), '₦50,000', font=f_big)
d.text((MARGIN, 280), '₦50,000', font=f_big, fill=WHITE)
mid = 280 + bb[3] // 2
d.rectangle([MARGIN, mid - 9, MARGIN + bb[2], mid + 9], fill=RED)      # red strike
d.text((MARGIN, 560), 'for one document.', font=font('Light', 58), fill=MUTED)
sw = track_width(d, 'SWIPE', font('SemiBold', 30), 6)
x_sw = W - MARGIN - sw - 86
tracked(d, (x_sw, 962), 'SWIPE', font('SemiBold', 30), WHITE, 6)
arrow(d, x_sw + sw + 20, 962, WHITE)
foot(d, 'THE LAWYER\u2019S PRICE')
save(img, 1)


# ── SLIDE 2 — the stakes (split layout + color block) ──────────────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
header(d, 'THE ALTERNATIVE', 'THE STAKES')
f1 = fit_font(d, 'nothing.', 'Black', 130, 548)
for i, word in enumerate(['Or', 'sign', 'nothing.']):
    d.text((MARGIN, 235 + i * 160), word, font=f1, fill=WHITE)
d.text((MARGIN, 740), '\u2026and pray.', font=font('Light', 62), fill=MUTED)
px0, px1, py0, py1 = 660, W - MARGIN, 205, 715
d.rounded_rectangle([px0, py0, px1, py1], radius=26, fill=PANEL)
f70 = fit_font(d, '70%', 'Black', 160, px1 - px0 - 80)
bb = d.textbbox((0, 0), '70%', font=f70)
d.text((px0 + (px1 - px0 - bb[2]) // 2, 260), '70%', font=f70, fill=WHITE)
d.rectangle([px0 + 60, 470, px1 - 60, 471], fill=(46, 92, 168))
for i, line in enumerate(['of Lagos tenants face', 'deposit or landlord', 'disputes.']):
    f29 = font('Regular', 30)
    lw = d.textbbox((0, 0), line, font=f29)[2]
    d.text((px0 + (px1 - px0 - lw) // 2, 505 + i * 44), line, font=f29, fill=(198, 218, 242))
foot(d, 'DO NOTHING. RISK EVERYTHING.')
save(img, 2)


# ── SLIDE 3 — the solution (underline sweep + outlined chips) ──────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
header(d, 'DOCOGA GENERATES', 'THE TOOL')
f_big = fit_font(d, '2 minutes.', 'Black', 150, MAXW)
bb = d.textbbox((0, 0), '2 minutes.', font=f_big)
d.text((MARGIN, 240), '2 minutes.', font=f_big, fill=WHITE)
d.rectangle([MARGIN, 240 + bb[3] + 14, MARGIN + bb[2], 240 + bb[3] + 28], fill=BLUE)
x, y, ch = MARGIN, 520, 60
f_chip = font('SemiBold', 26)
for lab in ['AGREEMENT', 'RECEIPT', 'CONTRACT', 'NOTICE']:
    tw = track_width(d, lab, f_chip, 4)
    cw = tw + 56
    d.rounded_rectangle([x, y, x + cw, y + ch], radius=30, outline=BLUE, width=3)
    tracked(d, (x + 28, y + 17), lab, f_chip, WHITE, 4)
    x += cw + 14
assert x - 14 <= W - MARGIN, 'chip row overflows'
d.text((MARGIN, 640), 'Every document built on your state\u2019s tenancy law.',
       font=font('Regular', 34), fill=MUTED)
foot(d, 'ALL 24 STATES COVERED')
save(img, 3)


# ── SLIDE 4 — the arsenal (giant numeral + inset panel) ────────────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
header(d, 'ONE PASS COVERS', 'THE ARSENAL')
f9 = font('Black', 260)
w9 = d.textbbox((0, 0), '9', font=f9)[2]
d.text((MARGIN, 195), '9', font=f9, fill=WHITE)
f_doc = fit_font(d, 'DOCUMENTS.', 'Black', 80, MAXW - w9 - 40)
d.text((MARGIN + w9 + 40, 300), 'DOCUMENTS.', font=f_doc, fill=WHITE)
py0, py1 = 560, 838
d.rounded_rectangle([MARGIN, py0, W - MARGIN, py1], radius=26, fill=PANEL)
cols = [('Tenancy Agreement', 'Caution Fee'),
        ('Quit Notice', 'Demand Letter'),
        ('Rent Receipt', 'Payslip'),
        ('Invoice', 'Warning Letter'),
        ('Employment Contract', None)]
f_list = font('SemiBold', 33)
for i, (left, right) in enumerate(cols):
    ry = py0 + 44 + i * 48
    d.rectangle([132, ry + 10, 144, ry + 22], fill=BLUE)
    d.text((164, ry), left, font=f_list, fill=WHITE)
    if right:
        d.rectangle([556, ry + 10, 568, ry + 22], fill=BLUE)
        d.text((588, ry), right, font=f_list, fill=WHITE)
foot(d, 'ONE PAYMENT. EVERY DOCUMENT.')
save(img, 4)


# ── SLIDE 5 — the price (centered + tonal watermark) ───────────────────
img = Image.new('RGB', (W, H), NAVY)
watermark(img, '₦', 830, 280, 900)
d = ImageDraw.Draw(img)
header(d, 'THE DOCOGA PASS', 'PRICE')
fs = font('Medium', 44)
txt = 'lawyer:  ₦50,000'
tw = d.textbbox((0, 0), txt, font=fs)[2]
d.text(((W - tw) // 2, 215), txt, font=fs, fill=MUTED)
d.rectangle([(W - tw) // 2 - 6, 240, (W + tw) // 2 + 6, 246], fill=RED)
f_big = fit_font(d, '₦2,000', 'Black', 230, 880)
txt = '₦2,000'
bb = d.textbbox((0, 0), txt, font=f_big)
tx, ty = (W - bb[2]) // 2, 295
d.text((tx, ty), txt, font=f_big, fill=WHITE)
d.rectangle([tx, ty + bb[3] + 26, tx + bb[2], ty + bb[3] + 40], fill=YELLOW)
line = '30 DAYS · UNLIMITED DOCUMENTS'
f_tr = font('SemiBold', 33)
tw = track_width(d, line, f_tr, 6)
tracked(d, ((W - tw) // 2, 665), line, f_tr, YELLOW, 6)
foot(d, 'PAY ONCE. DOWNLOAD ALL MONTH.')
save(img, 5)


# ── SLIDE 6 — the CTA (offset-shadow pill) ─────────────────────────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
header(d, 'DOCOGA', 'GET STARTED')
f_big = fit_font(d, 'Free to try.', 'Black', 150, MAXW)
d.text((MARGIN, 220), 'Free to try.', font=f_big, fill=WHITE)
for i, line in enumerate(['No signup.', 'No card.', 'No wahala.']):
    d.text((MARGIN, 420 + i * 70), line, font=font('Light', 56), fill=MUTED)
bw, bh = 620, 112
bx, by = (W - bw) // 2, 680
d.rounded_rectangle([bx + 12, by + 12, bx + bw + 12, by + bh + 12], radius=56, fill=PANEL)
d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=56, fill=WHITE)
fb = font('Bold', 46)
txt = 'docoga.com.ng'
tw = d.textbbox((0, 0), txt, font=fb)[2]
d.text(((W - tw) // 2, by + 32), txt, font=fb, fill=NAVY)
d.text((MARGIN, 960), 'Generate your first document tonight.',
       font=font('Regular', 31), fill=BLUE)
foot(d, 'YOUR DOCUMENTS. OUR PRIORITY.')
save(img, 6)


# ── contact sheet for QC ────────────────────────────────────────────────
tile, gut = 528, 24
sheet = Image.new('RGB', (3 * tile + 4 * gut, 2 * tile + 3 * gut), (11, 18, 32))
for i in range(6):
    s = Image.open(os.path.join(OUT, f'carousel-{i + 1}.jpg')).resize((tile, tile), Image.LANCZOS)
    sheet.paste(s, (gut + (i % 3) * (tile + gut), gut + (i // 3) * (tile + gut)))
sheet.save(os.path.join(OUT, 'carousel-montage.jpg'), quality=92)
print('✅ carousel-montage.jpg (contact sheet)')