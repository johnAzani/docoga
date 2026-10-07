#!/usr/bin/env python3
"""
THE DOCOGA LAUNCH POST v3 — "CRYSTAL CLEAR" (8 slides x 1080x1350, 4:5).
Research-upgraded (2026): 4:5 portrait = ~30% more feed screen space;
8-10 slides = engagement returns at slide 8; saves/shares = top ranking
signals; toddler-grade clarity (1-3 words + red-X/green-check language).

Run: python3 tools/make_launch_post.py → social/carousel-1..8.jpg + montage
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from blend_image import crop_aspect, filmify, scrim, treat, feather_paste

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, 'social')
W, H = 1080, 1350                    # 4:5 portrait — maximum feed real estate
MARGIN = 84
MAXW   = W - 2 * MARGIN

NAVY, RULE, PANEL = (6, 26, 51), (20, 41, 74), (15, 61, 124)
WHITE, MUTED, FAINT = (255, 255, 255), (143, 168, 201), (96, 128, 170)
SOFT = (198, 218, 242)
BLUE, YELLOW, RED, GREEN = (74, 140, 255), (255, 201, 60), (255, 90, 95), (46, 204, 113)

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

def track_width(d, text, fnt, tr):
    return sum(d.textbbox((0, 0), ch, font=fnt)[2] + tr for ch in text) - tr

def tracked(d, xy, text, fnt, fill, tr=8):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textbbox((0, 0), ch, font=fnt)[2] + tr
    return x - tr

def fit_tracked(d, text, sz, max_w, tr=5):
    while sz > 18:
        f = font('SemiBold', sz)
        if track_width(d, text, f, tr) <= max_w:
            return f
        sz -= 2
    return font('SemiBold', sz)

def arrow(d, x, y, color):
    d.rectangle([x, y + 13, x + 46, y + 18], fill=color)
    d.polygon([(x + 44, y + 3), (x + 66, y + 15), (x + 44, y + 27)], fill=color)

def badge(d, cx, cy, r, color, kind):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    lw = max(10, int(r * 0.26))
    if kind == 'check':
        d.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.08, cy + r * 0.38),
                (cx + r * 0.5, cy - r * 0.32)], fill=WHITE, width=lw, joint='curve')
    else:
        d.line([(cx - r * 0.38, cy - r * 0.38), (cx + r * 0.38, cy + r * 0.38)], fill=WHITE, width=lw)
        d.line([(cx + r * 0.38, cy - r * 0.38), (cx - r * 0.38, cy + r * 0.38)], fill=WHITE, width=lw)

def masthead(d, kicker):
    x_end = tracked(d, (MARGIN, 92), kicker, font('SemiBold', 27), BLUE, 9)
    d.rectangle([x_end + 20, 100, x_end + 34, 114], fill=(0, 135, 81))
    d.rectangle([x_end + 34, 100, x_end + 48, 114], fill=WHITE)
    d.rectangle([x_end + 48, 100, x_end + 62, 114], fill=(0, 135, 81))
    d.rectangle([MARGIN, 158, W - MARGIN, 159], fill=RULE)

def foot(d, text):
    tracked(d, (MARGIN, 1282), text, font('SemiBold', 22), FAINT, 5)

def save(img, n, seed):
    os.makedirs(OUT, exist_ok=True)
    arr = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 2.2, arr.shape[:2])[..., None]
    Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8)).save(
        os.path.join(OUT, f'carousel-{n}.jpg'), quality=95)
    print(f'✅ carousel-{n}.jpg')

def raw(name):
    return Image.open(os.path.join(OUT, 'assets', 'raw', name)).convert('RGB')


# ── SLIDE 1 — ₦50,000 ✗ TOO MUCH. ─────────────────────────────────────
img = Image.new('RGB', (W, H), NAVY)
try:
    photo = filmify(crop_aspect(raw('launch-desk-raw.png'), W, 940).resize((W, 940), Image.LANCZOS), seed=21)
    img.paste(photo, (0, 0))
    img = scrim(img, NAVY, 0, 200, 205, 0)
    img = scrim(img, NAVY, 680, 940, 0, 255)
except FileNotFoundError:
    pass  # fallback: plain navy
d = ImageDraw.Draw(img)
x_end = tracked(d, (MARGIN, 92), 'DOCOGA', font('SemiBold', 27), BLUE, 9)
d.rectangle([x_end + 20, 100, x_end + 34, 114], fill=(0, 135, 81))
d.rectangle([x_end + 34, 100, x_end + 48, 114], fill=WHITE)
d.rectangle([x_end + 48, 100, x_end + 62, 114], fill=(0, 135, 81))
f_big = fit_font(d, '₦50,000', 'Black', 150)
bb = d.textbbox((0, 0), '₦50,000', font=f_big)
d.text((MARGIN, 980), '₦50,000', font=f_big, fill=WHITE)
mid = 980 + bb[3] // 2
d.rectangle([MARGIN, mid - 9, MARGIN + bb[2], mid + 9], fill=RED)
badge(d, 116, 1218, 34, RED, 'cross')
d.text((170, 1180), 'TOO MUCH.', font=fit_font(d, 'TOO MUCH.', 'Black', 78), fill=WHITE)
f_sw = font('SemiBold', 30)
tw = track_width(d, 'SWIPE', f_sw, 6)
sw_x = W - MARGIN - tw - 86
tracked(d, (sw_x, 1196), 'SWIPE', f_sw, WHITE, 6)
arrow(d, sw_x + tw + 20, 1196, WHITE)
save(img, 1, 501)


# ── SLIDE 2 — NO PAPER? BIG TROUBLE. ───────────────────────────────────
def scene_panel(raw_name, y0, y1):
    img = Image.new('RGB', (W, H), NAVY)
    try:
        art = treat(raw(raw_name), 912, y1 - y0)
        feather_paste(img, art, (MARGIN, y0, W - MARGIN, y1))
    except FileNotFoundError:
        d_tmp = ImageDraw.Draw(img)
        d_tmp.rounded_rectangle([MARGIN, y0, W - MARGIN, y1], radius=44, fill=PANEL)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([MARGIN, y0, W - MARGIN, y1], radius=44, outline=PANEL, width=3)
    return img, d

img, d = scene_panel('story-dispute-raw.png', 190, 830)
masthead(d, 'WITHOUT PAPER')
tracked(d, (MARGIN, 880), 'NO PAPER?', font('SemiBold', 36), MUTED, 6)
d.text((MARGIN, 950), 'BIG TROUBLE.', font=fit_font(d, 'BIG TROUBLE.', 'Black', 108), fill=WHITE)
foot(d, 'THIS IS HOW PEOPLE LOSE EVERYTHING')
save(img, 2, 502)


# ── SLIDE 3 — 2 MINUTES ✓ ──────────────────────────────────────────────
img, d = scene_panel('phone-raw.png', 190, 830)
masthead(d, 'WITH DOCOGA')
badge(d, 130, 990, 50, GREEN, 'check')
d.text((206, 940), '2 MINUTES.', font=fit_font(d, '2 MINUTES.', 'Black', 100), fill=WHITE)
foot(d, 'MADE FOR NIGERIA')
save(img, 3, 503)


# ── SLIDE 4 — WORKS ON YOUR PHONE ✓ ────────────────────────────────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
masthead(d, 'NO LAPTOP NEEDED')
cx = W // 2
d.rounded_rectangle([cx - 210, 220, cx + 210, 810], radius=60, outline=BLUE, width=16)
d.rounded_rectangle([cx - 172, 272, cx + 172, 758], radius=26, fill=PANEL)
d.rounded_rectangle([cx - 92, 330, cx + 92, 620], radius=14, fill=WHITE)
for i in range(3):
    d.line([(cx - 58, 385 + i * 44), (cx + 58, 385 + i * 44)], fill=(170, 195, 228), width=9)
d.line([(cx - 58, 560), (cx + 10, 560)], fill=YELLOW, width=12)
badge(d, cx + 92, 620, 58, GREEN, 'check')
d.line([(cx - 40, 715), (cx + 40, 715)], fill=SOFT, width=7)
d.text((MARGIN, 900), 'WORKS ON YOUR PHONE.', font=fit_font(d, 'WORKS ON YOUR PHONE.', 'Black', 92), fill=WHITE)
d.text((MARGIN, 1040), 'No app. No laptop. No wahala.', font=font('Light', 44), fill=MUTED)
foot(d, 'PRINT OR SAVE AS PDF')
save(img, 4, 504)


# ── SLIDE 5 — EVERYTHING. ───────────────────────────────────────────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
masthead(d, 'ONE PASS')
d.text((MARGIN, 200), 'EVERYTHING.', font=fit_font(d, 'EVERYTHING.', 'Black', 124), fill=WHITE)
d.rounded_rectangle([MARGIN, 420, W - MARGIN, 940], radius=26, fill=PANEL)
size = 180
row1 = ['icon-agreement', 'icon-receipt', 'icon-seal', 'icon-house']
row2 = ['icon-shield', 'icon-clock', 'icon-coin']
w1 = 4 * size + 3 * 56
x0 = MARGIN + (MAXW - w1) // 2
for i, name in enumerate(row1):
    ic_path = os.path.join(OUT, 'assets', name + '.png')
    if os.path.exists(ic_path):
        ic = Image.open(ic_path).resize((size, size), Image.LANCZOS)
        img.paste(ic, (x0 + i * (size + 56), 465), ic)
w2 = 3 * size + 2 * 56
x0 = MARGIN + (MAXW - w2) // 2
for i, name in enumerate(row2):
    ic_path = os.path.join(OUT, 'assets', name + '.png')
    if os.path.exists(ic_path):
        ic = Image.open(ic_path).resize((size, size), Image.LANCZOS)
        img.paste(ic, (x0 + i * (size + 56), 705), ic)
d = ImageDraw.Draw(img)
d.text((MARGIN, 985), 'Agreements. Receipts. Notices. Contracts.',
       font=font('Regular', 36), fill=MUTED)
foot(d, '9 DOCUMENTS — ONE PASS')
save(img, 5, 505)


# ── SLIDE 6 — REAL NIGERIAN LAW ✓ ──────────────────────────────────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
masthead(d, 'NOT A TOY')
seal_path = os.path.join(OUT, 'assets', 'icon-seal.png')
if os.path.exists(seal_path):
    seal = Image.open(seal_path).resize((430, 430), Image.LANCZOS)
    img.paste(seal, ((W - 430) // 2, 210), seal)
d = ImageDraw.Draw(img)
d.text((MARGIN, 700), 'REAL NIGERIAN LAW.', font=fit_font(d, 'REAL NIGERIAN LAW.', 'Black', 96), fill=WHITE)
badge(d, 124, 920, 40, GREEN, 'check')
tracked(d, (186, 900), 'ALL 24 STATES COVERED', fit_tracked(d, 'ALL 24 STATES COVERED', 34, MAXW - 110), YELLOW, 6)
foot(d, 'BUILT ON YOUR STATE\u2019S TENANCY LAW')
save(img, 6, 506)


# ── SLIDE 7 — ₦2,000 ✓ ────────────────────────────────────────────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
masthead(d, 'THE PRICE')
fs = font('Medium', 54)
txt = '₦50,000'
tw = d.textbbox((0, 0), txt, font=fs)[2]
d.text((MARGIN, 250), txt, font=fs, fill=MUTED)
d.rectangle([MARGIN, 280, MARGIN + tw, 287], fill=RED)
badge(d, MARGIN + tw + 50, 284, 28, RED, 'cross')
f_big = fit_font(d, '₦2,000', 'Black', 240, 880)
txt = '₦2,000'
bb = d.textbbox((0, 0), txt, font=f_big)
d.text((MARGIN, 380), txt, font=f_big, fill=WHITE)
d.rectangle([MARGIN, 380 + bb[3] + 30, MARGIN + bb[2], 380 + bb[3] + 44], fill=YELLOW)
badge(d, 124, 900, 44, GREEN, 'check')
line = '30 DAYS. UNLIMITED.'
tracked(d, (190, 878), line, fit_tracked(d, line, 38, MAXW - 110), YELLOW, 6)
d.text((MARGIN, 1010), 'One payment. Every document.', font=font('Light', 42), fill=MUTED)
foot(d, 'PAY ONCE. USE ALL MONTH.')
save(img, 7, 507)


# ── SLIDE 8 — FREE. (CTA) ──────────────────────────────────────────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
masthead(d, 'START NOW')
d.text((MARGIN, 230), 'FREE.', font=fit_font(d, 'FREE.', 'Black', 220), fill=WHITE)
d.text((MARGIN, 560), 'Try it. No card.', font=font('Light', 54), fill=MUTED)
bw, bh = 620, 112
bx, by = (W - bw) // 2, 700
d.rounded_rectangle([bx + 12, by + 12, bx + bw + 12, by + bh + 12], radius=56, fill=PANEL)
d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=56, fill=WHITE)
fb = font('Bold', 46)
txt = 'docoga.com.ng'
tw = d.textbbox((0, 0), txt, font=fb)[2]
d.text(((W - tw) // 2, by + 32), txt, font=fb, fill=NAVY)
d.text((MARGIN, 900), 'Your first document — tonight.', font=font('Regular', 34), fill=BLUE)
foot(d, 'YOUR DOCUMENTS. OUR PRIORITY.')
save(img, 8, 508)


# ── montage (4×2) ───────────────────────────────────────────────────────
tile, gut = 400, 20
th = int(tile * H / W)
sheet = Image.new('RGB', (4 * tile + 5 * gut, 2 * th + 3 * gut), (11, 18, 32))
for i in range(8):
    s = Image.open(os.path.join(OUT, f'carousel-{i + 1}.jpg')).resize((tile, th), Image.LANCZOS)
    sheet.paste(s, (gut + (i % 4) * (tile + gut), gut + (i // 4) * (th + gut)))
sheet.save(os.path.join(OUT, 'carousel-montage.jpg'), quality=92)
print('✅ carousel-montage.jpg')