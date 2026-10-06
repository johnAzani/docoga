#!/usr/bin/env python3
"""
DocOga VECTOR KIT — brand icons drawn 100% in code (PIL primitives).

Zero AI pixels, zero photos: every line is a coordinate. On-brand by
construction. Strokes: royal blue structure, white detail, yellow accent.

Output: social/assets/icon-*.png (transparent) + preview-sheet.jpg

Usage: python3 tools/vector_kit.py
"""
import os, math
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'social', 'assets')
os.makedirs(OUT, exist_ok=True)

S = 480
BLUE, WHITE, YELLOW, SOFT = (74, 140, 255), (255, 255, 255), (255, 201, 60), (198, 218, 242)

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

def canvas():
    return Image.new('RGBA', (S, S), (0, 0, 0, 0))

def save(img, name):
    img.save(os.path.join(OUT, name + '.png'))
    print(f'\u2705 {name}')


# ── 1. RECEIPT (zigzag tear, item lines, yellow total) ──
def make_receipt():
    img = canvas(); d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 104, 64, 376, 400
    pts = [(x0, y0), (x1, y0), (x1, y1 - 26)]
    zx = 6; step = (x1 - x0) / zx
    for i in range(zx, -1, -1):
        pts.append((x0 + i * step, y1 - 26 + (16 if i % 2 else 0)))
    pts.append((x0, y0))
    d.line(pts, fill=BLUE, width=16, joint='curve')
    for i, w in enumerate([10, 10, 10]):
        d.line([(x0 + 56, 150 + i * 52), (x1 - 56, 150 + i * 52)], fill=SOFT, width=w)
    d.line([(x0 + 56, 320), (x0 + 200, 320)], fill=YELLOW, width=14)
    save(img, 'icon-receipt')

# ── 2. AGREEMENT (folded page + signature line) ──
def make_agreement():
    img = canvas(); d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 128, 64, 352, 416; fold = 72
    d.line([(x0, y0), (x1 - fold, y0), (x1, y0 + fold), (x1, y1), (x0, y1), (x0, y0)],
           fill=BLUE, width=16, joint='curve')
    d.line([(x1 - fold, y0), (x1 - fold, y0 + fold), (x1, y0 + fold)], fill=BLUE, width=10)
    for i in range(3):
        d.line([(x0 + 44, 190 + i * 48), (x1 - 44, 190 + i * 48)], fill=SOFT, width=9)
    d.line([(x0 + 44, 356), (x0 + 120, 344), (x0 + 170, 362), (x1 - 44, 350)],
           fill=YELLOW, width=12, joint='curve')
    save(img, 'icon-agreement')

# ── 3. SEAL (double ring + check + ribbons) ──
def make_seal():
    img = canvas(); d = ImageDraw.Draw(img)
    d.polygon([(178, 320), (146, 434), (206, 408), (232, 446)], fill=BLUE)
    d.polygon([(302, 320), (334, 434), (274, 408), (248, 446)], fill=BLUE)
    d.ellipse([100, 90, 380, 370], outline=BLUE, width=16)
    d.ellipse([132, 122, 348, 338], outline=BLUE, width=7)
    d.line([(198, 226), (233, 262), (292, 190)], fill=YELLOW, width=18, joint='curve')
    save(img, 'icon-seal')

# ── 4. HOUSE (tenancy) ──
def make_house():
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(240, 84), (104, 226), (376, 226)], fill=BLUE, width=16, joint='curve')
    d.line([(146, 226), (146, 404), (334, 404), (334, 226)], fill=BLUE, width=16, joint='curve')
    d.line([(206, 404), (206, 300), (274, 300), (274, 404)], fill=YELLOW, width=11, joint='curve')
    save(img, 'icon-house')

# ── 5. CLOCK (2 minutes) ──
def make_clock():
    img = canvas(); d = ImageDraw.Draw(img)
    d.ellipse([86, 86, 394, 394], outline=BLUE, width=16)
    d.line([(240, 240), (240, 140)], fill=WHITE, width=14)
    d.line([(240, 240), (316, 276)], fill=YELLOW, width=14)
    d.ellipse([226, 226, 254, 254], fill=WHITE)
    for i in range(12):
        a = math.radians(i * 30)
        d.line([(240 + 148 * math.sin(a), 240 - 148 * math.cos(a)),
                (240 + 166 * math.sin(a), 240 - 166 * math.cos(a))],
               fill=SOFT, width=6)
    save(img, 'icon-clock')

# ── 6. SHIELD + CHECK (protected) ──
def make_shield():
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(240, 76), (392, 136), (372, 276), (240, 420), (108, 276), (88, 136), (240, 76)],
           fill=BLUE, width=16, joint='curve')
    d.line([(172, 252), (220, 300), (314, 196)], fill=YELLOW, width=20, joint='curve')
    save(img, 'icon-shield')

# ── 7. NAIRA COIN ──
def make_coin():
    img = canvas(); d = ImageDraw.Draw(img)
    d.ellipse([80, 80, 400, 400], outline=BLUE, width=18)
    d.ellipse([108, 108, 372, 372], outline=SOFT, width=6)
    f = font('Black', 160)
    bb = d.textbbox((0, 0), '\u20A6', font=f)
    d.text((240 - (bb[2] - bb[0]) // 2 - bb[0], 240 - (bb[3] - bb[1]) // 2 - bb[1]),
           '\u20A6', font=f, fill=WHITE)
    save(img, 'icon-coin')


# ── preview sheet (navy, 3×3) ──
def make_preview():
    icons = ['icon-receipt', 'icon-agreement', 'icon-seal', 'icon-house',
             'icon-clock', 'icon-shield', 'icon-coin']
    tile, gut = 480, 24
    sheet = Image.new('RGB', (3 * tile + 4 * gut, 3 * tile + 4 * gut), (6, 26, 51))
    sd = ImageDraw.Draw(sheet)

    def tracked(xy, text, fnt, fill, tr):
        x, y = xy
        for ch in text:
            sd.text((x, y), ch, font=fnt, fill=fill)
            x += sd.textbbox((0, 0), ch, font=fnt)[2] + tr
        return x

    cx0, cy0 = gut, gut
    # title tile
    sd.text((cx0 + 150, cy0 + 160), 'DOCOGA', font=font('Black', 72), fill=WHITE)
    tracked((cx0 + 152, cy0 + 260), 'VECTOR KIT', font('SemiBold', 30), (96, 128, 170), 8)
    sd.rectangle([cx0 + 152, cy0 + 320, cx0 + 166, cy0 + 334], fill=(0, 135, 81))
    sd.rectangle([cx0 + 166, cy0 + 320, cx0 + 180, cy0 + 334], fill=WHITE)
    sd.rectangle([cx0 + 180, cy0 + 320, cx0 + 194, cy0 + 334], fill=(0, 135, 81))

    for i, name in enumerate(icons):
        tx = gut + ((i + 1) % 3) * (tile + gut)
        ty = gut + ((i + 1) // 3) * (tile + gut)
        ic = Image.open(os.path.join(OUT, name + '.png'))
        sheet.paste(ic, (tx, ty), ic)

    # tagline tile (last cell)
    tx, ty = gut + 2 * (tile + gut), gut + 2 * (tile + gut)
    sd.text((tx + 96, ty + 190), 'Your Documents.', font=font('Light', 42), fill=(143, 168, 201))
    sd.text((tx + 96, ty + 250), 'Our Priority.', font=font('Light', 42), fill=(143, 168, 201))

    sheet.save(os.path.join(OUT, 'preview-sheet.jpg'), quality=92)
    print('\u2705 preview-sheet.jpg')


def main():
    make_receipt()
    make_agreement()
    make_seal()
    make_house()
    make_clock()
    make_shield()
    make_coin()
    make_preview()
    print('VECTOR KIT COMPLETE — 7 icons + preview sheet')


if __name__ == '__main__':
    main()