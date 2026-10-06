#!/usr/bin/env python3
"""
DocOga BLEND PIPELINE — how generated imagery enters a design undetectably.

Steps (mandatory for every image, no exceptions):
  1. crop_aspect  — cut to the exact grid region needed
  2. duotone      — force luminance into the brand color ramp
                    (navy -> royal panel -> royal accent -> cream).
                    Whatever palette the generator returned dies here;
                    the image exits speaking DocOga's colors.
  3. feather_paste — rounded, edge-melted composite (never a pasted sticker)
  4. grain         — the slide's own film grain is applied over the final
                    canvas, so image and type share one texture

Importable library + CLI demo:  python3 tools/blend_image.py <in> <out>
"""
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageOps
import numpy as np

# brand ramp: shadows navy, midtones royal panel/accent, highlights cream
STOPS = [(0.00, (6, 26, 51)),      # canvas navy
         (0.42, (15, 61, 124)),    # royal panel
         (0.72, (74, 140, 255)),   # royal accent
         (1.00, (226, 235, 250))]  # soft cream


def crop_aspect(img, aw, ah):
    """center-crop to aspect aw:ah"""
    w, h = img.size
    target = aw / ah
    if w / h > target:
        nw = int(h * target)
        x = (w - nw) // 2
        return img.crop((x, 0, x + nw, h))
    nh = int(w / target)
    y = (h - nh) // 2
    return img.crop((0, y, 0 + w, y + nh))


def duotone(img, stops=STOPS):
    """luminance -> brand ramp via per-channel LUTs"""
    g = ImageOps.autocontrast(img.convert('L'), cutoff=1)
    luts = ([], [], [])
    for i in range(256):
        t = i / 255.0
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                for ch in range(3):
                    luts[ch].append(int(round(c0[ch] + (c1[ch] - c0[ch]) * f)))
                break
        else:
            for ch in range(3):
                luts[ch].append(stops[-1][1][ch])
    return Image.merge('RGB', (g.point(luts[0]), g.point(luts[1]), g.point(luts[2])))


def treat(img, aw, ah):
    """crop + duotone = brand-native artwork ready to place"""
    return duotone(crop_aspect(img, aw, ah))


def feather_paste(canvas, art, box, inset=16, radius=34, blur=22):
    """paste art with rounded, edge-melted alpha — it grows out of the canvas,
    never sits ON it"""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    art = art.resize((w, h), Image.LANCZOS)
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [inset, inset, w - inset, h - inset], radius=radius, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    canvas.paste(art, (x0, y0), mask)


# ── PHOTOREAL KIT — how ultra-realistic photos stay undetectable ─────────
# AI photos get caught when they're CLEAN. Real photography is imperfect:
# grain, fade, softness, vignette. These force that imperfection.

def photo_grade(img):
    """faded-film grade: desaturate, warm highlights, lifted blacks, S-curve"""
    a = np.asarray(img.convert('RGB')).astype(np.float32)
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    a = a * 0.78 + lum[..., None] * 0.22                     # desaturate
    a[..., 0] = np.clip(a[..., 0] * 1.07, 0, 255)            # warm reds
    a[..., 2] = np.clip(a[..., 2] * 0.92, 0, 255)            # mute blues
    a = a * 0.94 + 15.0                                      # lifted blacks
    n = a / 255.0
    n = np.clip(0.55 * n + 0.45 * (n * n * (3 - 2 * n)), 0, 1)   # gentle S-curve
    return Image.fromarray((n * 255).astype(np.uint8))


def vignette(img, amount=0.38):
    """darkened corners — the physical signature of a real lens"""
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 1.414
    mask = 1.0 - amount * np.clip(r - 0.55, 0, 1) ** 1.5
    a = np.asarray(img).astype(np.float32) * mask[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def photo_grain(img, sigma=6.0, seed=7):
    """heavy film grain on the photo itself — the #1 AI camouflage"""
    a = np.asarray(img).astype(np.int16)
    rng = np.random.default_rng(seed)
    a = a + rng.normal(0, sigma, a.shape[:2])[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def filmify(img, seed=7):
    """full photoreal treatment: soft focus + grade + vignette + grain"""
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    return photo_grain(vignette(photo_grade(img)), seed=seed)


def scrim(img, color, y0, y1, a_top, a_bottom):
    """vertical gradient overlay — melts photo edges into the canvas"""
    w, h = img.size
    alpha = np.zeros((h, w), np.float32)
    alpha[y0:y1] = np.linspace(a_top, a_bottom, y1 - y0)[:, None]
    if a_bottom == 255 and y1 < h:
        alpha[y1:] = 255.0
    if a_top == 255 and y0 > 0:
        alpha[:y0] = 255.0
    a = np.asarray(img).astype(np.float32)
    overlay = np.empty_like(a)
    overlay[:] = color
    out = a * (1 - alpha[..., None] / 255.0) + overlay * (alpha[..., None] / 255.0)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('usage: blend_image.py <in> <out>')
        sys.exit(1)
    src = Image.open(sys.argv[1]).convert('RGB')
    treated = treat(src, 4, 5)
    treated.save(sys.argv[2], quality=95)
    print('treated ->', sys.argv[2])