#!/usr/bin/env python3
"""
DOCOGA STORIES — Episode 01: "The ₦450,000 Mistake"
Narrative carousel (5 x 1080x1080).  Series format = recurring content that
builds returning followers.  Scenes pass the blend pipeline (duotone →
feather → shared grain); one pure-typographic slide hits as the gut punch.

Run: python3 tools/make_story_carousel.py  →  social/story-1..5.jpg + montage
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont

# blend_image may not exist yet — graceful fallback
try:
    from blend_image import treat, feather_paste
    HAS_BLEND = True
except ImportError:
    HAS_BLEND = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, 'social')
W = H = 1080
MARGIN = 84
MAXW   = W - 2 * MARGIN

NAVY, RULE    = (6, 26, 51), (20, 41, 74)
WM_INK, PANEL = (13, 42, 79), (15, 61, 124)
WHITE, MUTED, FAINT = (255, 255, 255), (143, 168, 201), (96, 128, 170)
BLUE, YELLOW, RED   = (74, 140, 255), (255, 201, 60), (255, 90, 95)

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

def track_width(d, text, fnt, tr):
    return sum(d.textbbox((0, 0), ch, font=fnt)[2] + tr for ch in text) - tr

def header(d, kicker):
    x_end = tracked(d, (MARGIN, 92), kicker, font('SemiBold', 27), BLUE, 9)
    d.rectangle([x_end + 20, 100, x_end + 34, 114], fill=(0, 135, 81))
    d.rectangle([x_end + 34, 100, x_end + 48, 114], fill=WHITE)
    d.rectangle([x_end + 48, 100, x_end + 62, 114], fill=(0, 135, 81))
    f_tr = font('SemiBold', 22)
    tw = track_width(d, 'DOCOGA STORIES', f_tr, 5)
    tracked(d, (W - MARGIN - tw, 100), 'DOCOGA STORIES', f_tr, FAINT, 5)
    d.rectangle([MARGIN, 158, W - MARGIN, 159], fill=RULE)

def foot(d, text):
    tracked(d, (MARGIN, 982), text, font('SemiBold', 22), FAINT, 5)

def scene_slide(n, kicker, foot_text, raw_name, line1, line2, line2_fill):
    img = Image.new('RGB', (W, H), NAVY)
    d = ImageDraw.Draw(img)
    header(d, kicker)

    if HAS_BLEND:
        art = treat(Image.open(os.path.join(OUT, 'assets', 'raw', raw_name)).convert('RGB'), 812, 560)
        feather_paste(img, art, (MARGIN, 190, W - MARGIN, 750))
    else:
        # Fallback: simple panel with accent border
        d.rounded_rectangle([MARGIN, 190, W - MARGIN, 750], radius=44, fill=PANEL)
        d.text((MARGIN + 60, 420), '📸', font=font('Black', 120), fill=(*WHITE, 80))

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([MARGIN, 190, W - MARGIN, 750], radius=44, outline=PANEL, width=3)
    d.text((MARGIN, 788), line1, font=fit_font(d, line1, 'Black', 84), fill=WHITE)
    d.text((MARGIN, 876), line2, font=fit_font(d, line2, 'Black', 84), fill=line2_fill)
    foot(d, foot_text)
    return img

def save(img, n):
    import numpy as np
    os.makedirs(OUT, exist_ok=True)
    arr = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(100 + n)
    noise = rng.normal(0, 2.2, arr.shape[:2])[..., None]
    Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8)).save(
        os.path.join(OUT, f'story-{n}.jpg'), quality=95)
    print(f'✅ story-{n}.jpg')


# ── 1. THE MISTAKE ──────────────────────────────────────────────────────
img = scene_slide(1, 'THE MISTAKE', 'PAYMENT WITHOUT PROOF', 'story-cash-raw.png',
                  '₦450,000 in cash.', 'No agreement. No receipt.', YELLOW)
save(img, 1)


# ── 2. THE DISPUTE ──────────────────────────────────────────────────────
img = scene_slide(2, 'THE DISPUTE', 'HIS WORD AGAINST CHIDI\u2019S', 'story-dispute-raw.png',
                  '18 months later —', '\u201CYou never paid me.\u201D', WHITE)
save(img, 2)


# ── 3. THE LOSS (typographic gut punch) ─────────────────────────────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
f_wm = font('Black', 900)
bb = d.textbbox((0, 0), '₦', font=f_wm)
d.text((830 - (bb[2] - bb[0]) // 2 - bb[0], 300 - (bb[3] - bb[1]) // 2 - bb[1]), '₦',
       font=f_wm, fill=WM_INK)
d = ImageDraw.Draw(img)
header(d, 'THE LOSS')
d.text((MARGIN, 250), 'No paper.', font=fit_font(d, 'No paper.', 'Black', 150), fill=WHITE)
f2 = fit_font(d, 'No proof.', 'Black', 150)
d.text((MARGIN, 440), 'No proof.', font=f2, fill=WHITE)
w2 = d.textbbox((0, 0), 'No proof.', font=f2)[2]
d.rectangle([MARGIN, 440 + 186, MARGIN + w2, 440 + 198], fill=RED)
f_sub = font('Light', 46)
x = MARGIN
for txt, col in [('₦450,000 gone.', RED), ('  The apartment too.', MUTED)]:
    d.text((x, 680), txt, font=f_sub, fill=col)
    x += d.textbbox((0, 0), txt, font=f_sub)[2]
foot(d, 'THE COST OF \u2018TRUST ME\u2019')
save(img, 3)


# ── 4. THE TURN ─────────────────────────────────────────────────────────
img = scene_slide(4, 'THE TURN', 'TWO MINUTES. THAT\u2019S ALL.', 'phone-raw.png',
                  '2 minutes of paperwork', 'would have saved him.', YELLOW)
save(img, 4)


# ── 5. THE MORAL (CTA) ─────────────────────────────────────────────────
img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
header(d, 'THE MORAL')
d.text((MARGIN, 230), 'Don\u2019t be Chidi.',
       font=fit_font(d, 'Don\u2019t be Chidi.', 'Black', 150), fill=WHITE)
d.text((MARGIN, 430), 'Tenancy agreements and receipts — 2 minutes.',
       font=fit_font(d, 'Tenancy agreements and receipts — 2 minutes.', 'Light', 46), fill=MUTED)
bw, bh = 620, 112
bx, by = (W - bw) // 2, 560
d.rounded_rectangle([bx + 12, by + 12, bx + bw + 12, by + bh + 12], radius=56, fill=PANEL)
d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=56, fill=WHITE)
fb = font('Bold', 46)
txt = 'docoga.com.ng'
tw = d.textbbox((0, 0), txt, font=fb)[2]
d.text(((W - tw) // 2, by + 32), txt, font=fb, fill=NAVY)
d.text((MARGIN, 740), 'Free to try. No signup.', font=font('Regular', 32), fill=BLUE)
foot(d, 'YOUR DOCUMENTS. OUR PRIORITY.')
save(img, 5)


# ── montage 3×2 with series title tile ──────────────────────────────────
tile, gut = 480, 24
sheet = Image.new('RGB', (3 * tile + 4 * gut, 2 * tile + 3 * gut), (11, 18, 32))
sd = ImageDraw.Draw(sheet)

def s_tr(xy, text, fnt, fill, tr):
    x, y = xy
    for ch in text:
        sd.text((x, y), ch, font=fnt, fill=fill)
        x += sd.textbbox((0, 0), ch, font=fnt)[2] + tr
    return x

# title tile = last cell (row 2 col 3)
tx, ty = gut + 2 * (tile + gut), gut
sd.text((tx + 84, ty + 130), 'DOCOGA', font=font('Black', 68), fill=WHITE)
s_tr((tx + 86, ty + 218), 'STORIES', font('SemiBold', 30), (96, 128, 170), 10)
sd.rectangle([tx + 86, ty + 280, tx + 100, ty + 294], fill=(0, 135, 81))
sd.rectangle([tx + 100, ty + 280, tx + 114, ty + 294], fill=WHITE)
sd.rectangle([tx + 114, ty + 280, tx + 128, ty + 294], fill=(0, 135, 81))
sd.text((tx + 86, ty + 330), 'Episode 01', font=font('Light', 36), fill=(143, 168, 201))
sd.text((tx + 86, ty + 378), 'The ₦450,000', font=font('SemiBold', 34), fill=WHITE)
sd.text((tx + 86, ty + 420), 'Mistake', font=font('SemiBold', 34), fill=WHITE)

for i in range(5):
    s = Image.open(os.path.join(OUT, f'story-{i + 1}.jpg')).resize((tile, tile), Image.LANCZOS)
    sheet.paste(s, (gut + (i % 3) * (tile + gut), gut + (i // 3) * (tile + gut)))
sheet.save(os.path.join(OUT, 'story-montage.jpg'), quality=92)
print('✅ story-montage.jpg')