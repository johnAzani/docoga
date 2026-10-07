#!/usr/bin/env python3
"""
tools/gen_feed_5docs.py — feed post: "5 DOCUMENTS BEFORE YOU PAY RENT" (1080x1350, 4:5)
House rules: flat navy, Inter, no emoji, no logo, typed DOCOGA kicker, no key elements top-right.
Motion-narrative law: strike-through ONLY on lawyer price (external); own price yellow underline, never struck.
"""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1080, 1350
NAVY  = (6, 26, 51)
PANEL = (15, 61, 124)
BLUE  = (74, 140, 255)
YELLOW = (255, 201, 60)
RED   = (255, 90, 95)
WHITE = (255, 255, 255)
MUTED = (150, 175, 220)
GREEN = (0, 135, 81)

FP = '/usr/share/fonts/opentype/inter/Inter-{}.otf'
F = lambda w, s: ImageFont.truetype(FP.format(w), s)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'social')
os.makedirs(OUT, exist_ok=True)

img = Image.new('RGB', (W, H), NAVY)
d = ImageDraw.Draw(img)
PAD = 72

def ls_text(x, y, s, font, fill, ls):
    for ch in s:
        d.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + ls
    return x

MAXW = W - PAD - 24

def fit(text, weight, size, max_w=MAXW):
    """Anticipate-overflow guard: shrink until the line fits the content width."""
    while size > 20:
        f = F(weight, size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return F(weight, 20)


# ── kicker (top-LEFT — never top-right) ─────────────────────────────────
y = 62
ls_text(PAD, y, 'DOCOGA', F('Bold', 30), WHITE, 10)
fx = ls_text(PAD, y + 46, 'LAGOS RENT SEASON', F('Bold', 24), BLUE, 8)
# flag: green-white-green bar under kicker
fy = y + 92
d.rectangle([PAD, fy, PAD + 150, fy + 8], fill=GREEN)
d.rectangle([PAD + 150, fy, PAD + 180, fy + 8], fill=WHITE)
d.rectangle([PAD + 180, fy, PAD + 330, fy + 8], fill=GREEN)


# ── headline ────────────────────────────────────────────────────────────
y = 178
d.text((PAD, y), '5 DOCUMENTS', font=F('ExtraBold', 112), fill=WHITE)
y += 128
d.text((PAD, y), 'BEFORE YOU PAY RENT.', font=F('Bold', 62), fill=BLUE)
y += 96


# ── checklist ───────────────────────────────────────────────────────────
items = [
    ('01', 'TENANCY AGREEMENT', 'Signed by both parties — not just the landlord\u2019s copy'),
    ('02', 'RENT RECEIPT', 'Required by law — Lagos Tenancy Law, s.10'),
    ('03', 'CAUTION FEE RECEIPT', 'Your refund ticket when you move out'),
    ('04', 'INVENTORY PHOTOS', 'Date-stamped, before you move in'),
    ('05', 'PROOF OF OWNERSHIP', 'Confirm who actually owns the flat'),
]
row_h = 118
for i, (num, title, detail) in enumerate(items):
    ry = y + i * row_h
    d.text((PAD, ry), num, font=F('ExtraBold', 40), fill=YELLOW)
    d.text((PAD + 100, ry - 4), title, font=F('Bold', 44), fill=WHITE)
    d.text((PAD + 100, ry + 48), detail, font=F('Regular', 30), fill=MUTED)
    if i < len(items) - 1:
        d.line([(PAD, ry + 96), (W - PAD, ry + 96)], fill=PANEL, width=2)
y += len(items) * row_h + 10


# ── price block ─────────────────────────────────────────────────────────
MAXW = W - PAD - 24
strike = 'One lawyer document: ₦50,000'
f_st = fit(strike, 'Medium', 36, MAXW)
sw = d.textlength(strike, font=f_st)
d.text((PAD, y), strike, font=f_st, fill=MUTED)
d.rectangle([PAD, y + 26, PAD + sw, y + 31], fill=RED)  # strike bar spans the digits exactly
y += 66

own = 'ALL 5 ON DOCOGA — ₦2,000 / 30 DAYS'
f_own = fit(own, 'ExtraBold', 54, MAXW)
ow = d.textlength(own, font=f_own)
d.text((PAD, y), own, font=f_own, fill=WHITE)
d.rectangle([PAD, y + 70, PAD + ow, y + 80], fill=YELLOW)  # confident underline — never struck
y += 118


# ── bottom CTA ──────────────────────────────────────────────────────────
d.text((PAD, y), 'FREE to start. No signup. No card.', font=F('Medium', 36), fill=WHITE)
y += 58
d.text((PAD, y), 'docoga.com.ng', font=F('ExtraBold', 62), fill=YELLOW)
y += 84
assert y <= H, f'OVERFLOW: {y} > {H}'

out_path = os.path.join(OUT, 'post-3-5docs.jpg')
img.save(out_path, quality=92)
print(f'saved {os.path.getsize(out_path)} bytes; content ends at y = {y}')