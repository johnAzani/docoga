#!/usr/bin/env python3
"""short_cover.py — the Short's cover: the one still every grid, search card and inbox shows.

Owner, 18 Oct 2026: "improve the Shorts thumbnail design — no one can resist." Research the
same day (vidIQ, TubeAnalytics, CTRpilot, NoteLM, thumbcrafted, fixphotolab; see
docs/SHORT_COVER.md) agrees on a short list, and this file is that list drawn in the brand:

  * Where it is seen. Not the feed (autoplay) — the channel's Shorts tab, YouTube search,
    suggested, the TikTok profile grid and TikTok search. Readable text there lifted CTR 85 %
    in a 500-Short test; dense text lowered it. Those grids crop 9:16 to 3:4 or 1:1 — only
    y ≈ 420–1500 of a 1080×1920 canvas survives everywhere, and TikTok prints the caption's
    first line over the bottom ~270 px. So: everything that matters lives in BAND.
  * One focal point, three to five words, huge. The STAKES hook already has it — the
    consequence ("PAY TWICE.", "LOSE THE FLAT.") is the verdict; the set-up is the context.
    Reducing thumbnail text from seven words to four lifted CTR 34 %.
  * Contrast is the strongest single lever (≥ 7:1 → 6.5 % vs 4.7 % CTR), and yellow-on-dark /
    dark-on-yellow is the best-performing pair (8.2 %). The verdict is set navy on brand-yellow
    slabs — the brand's "price highlight" device, flat, no shadow, one yellow per piece.
  * Strong sentiment in the image beats a neutral one (Journal of Business Research, 16,215
    covers); numbers and questions do not help. The consequence line *is* the sentiment.
  * A real photograph behind it (the matched CC0 shot, treated brighter than in the video)
    beats flat colour; brand consistency (kicker, chip, Inter) earns a small lift with
    returning viewers. Film grain σ≈2.2 on the finished piece (BRAND_STYLE §4).

The cover is frame 0 of the master (TikTok / Telegram / Facebook default) and `<master>.cover.jpg`
(YouTube custom thumbnail). It never touches the animated scenes.

    python3 tools/short_cover.py --date 2026-10-19 --out /tmp/cover.jpg [--photo some.jpg]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import motionstudio as ms  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

W, H, CX = ms.W, ms.H, ms.CX
# The band every placement keeps: TikTok grid (1:1 → y 420–1500), YouTube grid card (2:3 →
# y 150–1770), TikTok caption overlay (bottom 270), YouTube title overlay (bottom third).
BAND = (460, 1480)
SIDE = 72                      # left/right margin — grids never crop the sides
TEXT_W = W - 2 * SIDE
SLAB_PAD_X, SLAB_PAD_Y = 30, 10
SLAB_GAP = 6                   # slabs sit as one stepped block, not loose stickers
OFFSET = 16                    # the royal offset block behind the slabs — flat depth (BRAND §4)
X_BADGE = True                 # red ✗ after the set-up: the brand's rejection mark ("₦50,000 ✗")
HERO_MAX, HERO_MIN = 250, 118  # the verdict: as large as its words allow
HERO_ONE_LINE = 150            # …and on one line whenever one line can be this big
SETUP_MAX, SETUP_MIN = 150, 72 # the set-up: never more than 1/1.35 of the verdict
COVER_DARKEN = 0.80            # the photograph, brighter than in the video (0.68)
BAND_ALPHA = 92                # flat navy behind the stack so white type clears the photo


def hook_parts(reel):
    """(kicker, setup, consequence, sub) from the opening scene's beats. The yellow cascade is
    the consequence; the white one the set-up; a single-cascade hook is all verdict."""
    sc = reel["scenes"][0]
    kicker = setup = consequence = sub = ""
    for b in sc["beats"]:
        if b["kind"] == "kicker" and not kicker:
            kicker = b["text"]
        elif b["kind"] == "cascade":
            if tuple(b.get("color") or ()) == tuple(ms.YELLOW) or (setup and not consequence):
                consequence = consequence or b["text"]
            else:
                setup = setup or b["text"]
        elif b["kind"] == "support" and not sub:
            sub = b["text"]
    if not consequence:
        setup, consequence = "", setup
    return kicker, setup, consequence, sub


def fit_lines(text, weight, hi, lo, width, max_lines=2, one_line_floor=None):
    """(size, lines): the largest size in [lo, hi] at which `text` sits in ≤ max_lines lines of
    ≤ width px. One line is preferred down to `one_line_floor` (a verdict reads as one line);
    below that, two balanced lines (motionstudio.linebreak) win over a smaller single line."""
    text = " ".join(str(text or "").split())
    if not text:
        return lo, []
    if one_line_floor:
        for size in range(hi, max(lo, one_line_floor) - 1, -4):
            if ms.tw(text, weight, size) <= width:
                return size, [text]
    for size in range(hi, lo - 1, -4):
        if ms.tw(text, weight, size) <= width:
            return size, [text]
        if max_lines >= 2 and " " in text:
            lines = ms.linebreak(text, weight, size)
            if lines and all(ms.tw(l, weight, size) <= width for l in lines):
                return size, lines
    # Nothing fits at the floor: wrap greedily at the floor so the words still land inside.
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and ms.tw(trial, weight, lo) > width:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lo, lines[:3]


def tonal_glyph(img, letter):
    """BRAND_STYLE §4 'giant tonal glyph bleeding off-canvas': the verdict's first letter, royal
    watermark on the navy, when there is no photograph to give the frame depth."""
    if not letter:
        return img
    d = ImageDraw.Draw(img)
    f = ms.font("Black", 1500)
    d.text((W - 760, 620), letter, font=f, fill=ms.NAVY2)
    return img


def background(reel):
    """The matched photograph behind the cover (treated brighter than in the video), else navy
    with the tonal glyph."""
    sc = reel["scenes"][0]
    raw = sc.get("_bg_raw")
    if raw is not None:
        try:
            import brain_visual
            return brain_visual.treat(raw, (W, H), darken=COVER_DARKEN).convert("RGB")
        except Exception:
            pass
    bg = sc.get("_bg")
    if bg is not None and getattr(bg, "size", None) == (W, H):
        return bg.convert("RGB")
    _, _, consequence, _ = hook_parts(reel)
    return tonal_glyph(ms.BASE.convert("RGB").copy(), (consequence or "D")[:1])


def layout(reel):
    """Sizes and line lists, solved so the whole stack sits inside BAND."""
    kicker, setup, consequence, sub = hook_parts(reel)
    hero_w = TEXT_W - 2 * SLAB_PAD_X
    hero_size, hero_lines = fit_lines(consequence, "Black", HERO_MAX, HERO_MIN, hero_w, one_line_floor=HERO_ONE_LINE)
    setup_hi = min(SETUP_MAX, int(hero_size / 1.35))
    setup_size, setup_lines = fit_lines(setup, "Black", max(setup_hi, SETUP_MIN), SETUP_MIN, TEXT_W)
    sub_size, sub_lines = fit_lines(sub, "Medium", 46, 34, TEXT_W, max_lines=1)

    def shrink_to_band():
        nonlocal hero_size, hero_lines, setup_size, setup_lines
        while stack_height(hero_size, hero_lines, setup_size, setup_lines, sub_size, sub_lines, kicker) > (BAND[1] - BAND[0] - 120) \
                and hero_size > HERO_MIN:
            hero_size -= 8
            hero_size, hero_lines = fit_lines(consequence, "Black", hero_size, HERO_MIN, hero_w, one_line_floor=HERO_ONE_LINE)
            setup_hi2 = min(SETUP_MAX, int(hero_size / 1.35))
            setup_size, setup_lines = fit_lines(setup, "Black", max(setup_hi2, SETUP_MIN), SETUP_MIN, TEXT_W)
    shrink_to_band()
    return dict(kicker=kicker, hero=(hero_size, hero_lines), setup=(setup_size, setup_lines), sub=(sub_size, sub_lines))


def _line_h(weight, size):
    asc, desc = ms.font(weight, size).getmetrics()
    return asc + desc


def stack_height(hero_size, hero_lines, setup_size, setup_lines, sub_size, sub_lines, kicker):
    h = 0
    if kicker:
        h += _line_h("SemiBold", 32) + 34
    if setup_lines:
        h += len(setup_lines) * int(_line_h("Black", setup_size) * 0.90) + 40
    h += len(hero_lines) * (int(_line_h("Black", hero_size) * 0.84) + 2 * SLAB_PAD_Y + SLAB_GAP) - SLAB_GAP
    if sub_lines:
        h += 38 + _line_h("Medium", sub_size)
    return h


def band_alpha(img, y0, y1):
    """How much navy to lay behind the stack: light enough to keep the photograph on a dark
    frame, heavier when the picture is bright (a white document reads as cream in the duotone)
    so white type keeps ≥ 7:1 against what sits behind it."""
    from PIL import ImageStat
    region = img.convert("L").crop((0, max(0, y0), W, min(H, y1)))
    mean = ImageStat.Stat(region).mean[0] if region.size[1] > 0 else 0
    if mean < 60:
        return BAND_ALPHA
    if mean < 100:
        return BAND_ALPHA + 48
    return BAND_ALPHA + 96


def render(reel):
    """The cover as a PIL RGB image, W×H."""
    L = layout(reel)
    hero_size, hero_lines = L["hero"]
    setup_size, setup_lines = L["setup"]
    sub_size, sub_lines = L["sub"]
    kicker = L["kicker"]

    img = background(reel)
    total = stack_height(hero_size, hero_lines, setup_size, setup_lines, sub_size, sub_lines, kicker)
    chip_h = 96
    free_top, free_bot = BAND[0], BAND[1] - chip_h - 48
    y = free_top + max(0, (free_bot - free_top - total) // 2)

    # A flat navy band behind the stack (colour-blocked panel, BRAND_STYLE §4) — white type
    # clears the photograph at any brightness; the slabs stay the only yellow on the piece.
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([0, y - 56, W, y + total + 56], fill=(*ms.NAVY, band_alpha(img, y - 56, y + total + 56)))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    d = ImageDraw.Draw(img)

    if kicker:
        f = ms.font("SemiBold", 32)
        ms.ctracked(d, y, kicker, f, ms.MUTED, 8)
        y += _line_h("SemiBold", 32) + 34
    if setup_lines:
        f = ms.font("Black", setup_size)
        lh = int(_line_h("Black", setup_size) * 0.90)
        for i, line in enumerate(setup_lines):
            last = i == len(setup_lines) - 1
            if last and X_BADGE:
                # "PAY THE WRONG AGENT. ✗" — the rejection mark, inline, the line re-centred
                # with it (BRAND_STYLE §5: red X badge = rejection; the one symbol on the piece).
                r = int(setup_size * 0.30)
                gap = int(setup_size * 0.22)
                lw = ms.tw(line, "Black", setup_size)
                x = CX - (lw + gap + 2 * r) // 2
                d.text((x, y), line, font=f, fill=ms.WHITE)
                asc_s, _ = f.getmetrics()
                ms.badge(d, x + lw + gap + r, y + asc_s - int(setup_size * 0.34), r, ms.RED, "x")
            else:
                ms.ctext(d, y, line, f, ms.WHITE)
            y += lh
        y += 40
    f = ms.font("Black", hero_size)
    asc, desc = f.getmetrics()
    slab_h = int((asc + desc) * 0.84) + 2 * SLAB_PAD_Y
    widths = [ms.tw(line, "Black", hero_size) for line in hero_lines]
    block_h = len(hero_lines) * slab_h + (len(hero_lines) - 1) * SLAB_GAP
    # Flat royal block offset behind the stack: depth without a shadow (the brand's offset pill).
    bx0 = CX - max(widths) // 2 - SLAB_PAD_X
    bx1 = CX + max(widths) // 2 + SLAB_PAD_X
    d.rectangle([bx0 + OFFSET, y + OFFSET, bx1 + OFFSET, y + block_h + OFFSET], fill=ms.PANEL)
    for i, line in enumerate(hero_lines):
        lw = widths[i]
        x0, x1 = CX - lw // 2 - SLAB_PAD_X, CX + lw // 2 + SLAB_PAD_X
        d.rectangle([x0, y, x1, y + slab_h], fill=ms.YELLOW)
        # Cap height sits on the slab's optical centre: Inter's ascent carries headroom.
        d.text((CX - lw // 2, y + SLAB_PAD_Y - int(asc * 0.16)), line, font=f, fill=ms.NAVY)
        y += slab_h + (SLAB_GAP if i < len(hero_lines) - 1 else 0)
    if sub_lines:
        y += 38
        ms.ctext(d, y, sub_lines[0], ms.font("Medium", sub_size), ms.MUTED)
        y += _line_h("Medium", sub_size)

    # The brand chip — "FREE · docoga.com.ng" — the outlined CTA pill, inside the 1:1 crop
    # and above TikTok's caption overlay (bottom 270 px) and YouTube's title band.
    chip_text = "FREE · docoga.com.ng"
    cf = ms.font("SemiBold", 40)
    cw = ms.tw(chip_text, "SemiBold", 40)
    cy = BAND[1] - chip_h
    d.rounded_rectangle([CX - cw // 2 - 36, cy, CX + cw // 2 + 36, cy + chip_h - 16], 40,
                        fill=ms.NAVY, outline=ms.BLUE, width=4)
    d.text((CX - cw // 2, cy + (chip_h - 16 - 40) // 2 - 4), chip_text, font=cf, fill=ms.WHITE)

    out = img.convert("RGB")
    try:
        import blend_image
        out = blend_image.photo_grain(out, sigma=2.2, seed=11)
    except Exception:
        pass
    return out


def describe(reel):
    """One line for the log: what the cover says and how big."""
    L = layout(reel)
    return "cover: %s | %s @%dpx | %s @%dpx (slab) | %s" % (
        L["kicker"], " / ".join(L["setup"][1]) or "—", L["setup"][0],
        " / ".join(L["hero"][1]), L["hero"][0], (L["sub"][1] or ["—"])[0])


def main(argv=None):
    ap = argparse.ArgumentParser(description="render a Short's cover")
    ap.add_argument("--date", help="rotation date (ISO)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--photo", help="a photograph to put behind it (else navy)")
    a = ap.parse_args(argv)
    from datetime import date
    import shorts_reel
    day = date.fromisoformat(a.date) if a.date else date.today()
    topic = shorts_reel.topic_for(day)
    reel = shorts_reel.reel_from_topic(topic, "/tmp/_cover.mp4")
    ms.solve_sizes(reel)
    ms.solve_layout(reel)
    ms.schedule(reel)
    if a.photo:
        reel["scenes"][0]["_bg_raw"] = Image.open(a.photo).convert("RGB")
    render(reel).save(a.out, quality=92, optimize=True)
    print(describe(reel))
    print("COVER=%s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
