#!/usr/bin/env python3
"""
tools/social_card.py — today's copy as a JPEG Instagram is willing to fetch
===========================================================================

Instagram's publishing API does not accept a file. It accepts a **URL**, and Meta's
servers download it. That single fact is why `instagram_autopost.yml` has been
dispatch-only this long: the renders this repo makes live in gitignored `assets/`, and a
URL to a gitignored file is a 404 in a foreign datacentre.

The fix costs nothing, because DocOga already owns a public file host: `site/` is the
deployed Cloudflare site at https://docoga.com.ng. A render committed under
`site/social/` is therefore a public URL after the site deploy, at ₦0, with no new
account, no bucket, and no third party holding our content. This file writes those
renders; the lane waits for the URL to answer 200 (`ig_publish.py --wait-url`) before it
creates a container, because git knows about a file before the web does.

Three things this renderer guarantees, and each is checkable:

  1. **1080×1350 — exactly 4:5**, the narrowest ratio Instagram accepts for a feed photo.
     `ig_publish.jpeg_spec()` reads the header and refuses anything outside 4:5…1.91:1, so
     a card that came from here always passes that gate, and a test proves it.
  2. **JPEG, under `--max-kb` (default 900)** — Meta's cap is 8 MB, but a card that heavy
     is a slow fetch that can time out on their side, and a timeout arrives as
     "Unsupported URL request". Quality is walked down until the file fits.
  3. **No glyph the runner cannot draw.** Inter is not a stock font on the runners and the
     brand copy is full of 🏛️ 📄 ⚠️, which DejaVu renders as empty boxes on a *public
     post*. So emoji are stripped from what is **drawn** and kept in the **caption** — the
     caption is text Instagram renders with its own fonts, the card is our job.

The palette is `docs/BRAND_STYLE.md`'s (deep navy ground, white type, one accent), and it
is deliberately not a second design system: same ink, same rule line, same footer voice
as the Telegram and Facebook cards.

Usage
    python3 tools/social_card.py --from-json assets/threads/threads_content_latest.json \
        --out site/social/2026-10-13.jpg --base-url https://docoga.com.ng
    python3 tools/social_card.py --text "one line" --out /tmp/card.jpg --print
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]

CARD_W, CARD_H = 1080, 1350          # exactly 4:5 — the documented narrowest feed ratio
MARGIN = 96
FOOTER = "docoga.com.ng"

# docs/BRAND_STYLE.md: navy ground, white type, one accent. Kept as literals rather than
# a config file because a config file that is not in the image's own header is a rumour.
INK_BG = (6, 26, 51)
INK_RULE = (20, 41, 74)
INK_PANEL = (13, 42, 79)
WHITE = (255, 255, 255)
MUTED = (143, 168, 201)
ACCENT = (255, 201, 60)
BLUE = (74, 140, 255)

_USER_FONTS = os.path.expanduser("~/.local/share/fonts/inter")
FONT_CANDIDATES = {
    "Black": ["/usr/share/fonts/opentype/inter/Inter-Black.otf",
              _USER_FONTS + "/Inter-Black.otf", _USER_FONTS + "/Inter-Black.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
    "SemiBold": ["/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
                 _USER_FONTS + "/Inter-SemiBold.otf", _USER_FONTS + "/Inter-SemiBold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
    "Medium": ["/usr/share/fonts/opentype/inter/Inter-Medium.otf",
               _USER_FONTS + "/Inter-Medium.otf", _USER_FONTS + "/Inter-Medium.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
    "Regular": ["/usr/share/fonts/opentype/inter/Inter-Regular.otf",
                _USER_FONTS + "/Inter-Regular.otf", _USER_FONTS + "/Inter-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
}

# Anything outside Latin-1 plus the punctuation this type can draw is a box on the card.
# This is a *conservative* whitelist on purpose: a new brand glyph fails by being stripped
# (visible in the render, easy to fix here) rather than by shipping tofu to 4,000 readers.
DRAWABLE = re.compile(
    "[^\\x09\\x0a\\x20-\\x7e\\xa0-\\xff"
    " —‘’“”…•·₦ºª×÷−⁄]"
)
WHITESPACE = re.compile(r"[ \t]+\n|\n[ \t]+")


def plain_for_card(text):
    """What the card can actually draw: no emoji, no markup, no trailing spaces."""
    out = DRAWABLE.sub("", text or "")
    out = out.replace("**", "").replace("__", "").replace("~~", "")
    out = WHITESPACE.sub("\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


HASHTAG_LINE = re.compile(r"^\s*(?:#[\w\u00c0-\u024f]+\s*)+$")


def _drop_hashtags(text):
    """Trailing hashtag lines are caption furniture, not card copy.

    The caption is Instagram's own text, rendered in its own font, and that is where a
    discovery tag does something. The same words printed at the bottom of a navy card are
    noise that also steals vertical room from the sentence the reader came for.
    """
    lines = (text or "").split("\n")
    while lines and (HASHTAG_LINE.match(lines[-1]) or not lines[-1].strip()):
        lines.pop()
    return "\n".join(lines)


def _font_path(weight):
    for candidate in FONT_CANDIDATES[weight]:
        if Path(candidate).exists():
            return candidate
    return None


def load_font(weight, size):
    path = _font_path(weight)
    if path:
        return ImageFont.truetype(path, size), os.path.basename(path)
    # Pillow 10's load_default() takes a size and scales a bitmap; anything that returns a
    # fixed 10px font would silently produce a card with unreadable type on a runner whose
    # fonts changed, which is exactly the failure this function exists to avoid.
    try:
        return ImageFont.load_default(size=size), "PIL-default"
    except TypeError:  # older Pillow
        return ImageFont.load_default(), "PIL-default(unsized)"


def wrap(draw, text, font, max_width):
    """Greedy wrap by measured width, preserving explicit newlines.

    Words longer than the line (a URL) are placed on their own line rather than split:
    a hyphenated URL on a legal card reads like a changed URL.
    """
    lines = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            lines.append("")
            continue
        current = ""
        for word in para.split():
            trial = (current + " " + word).strip()
            if draw.textlength(trial, font=font) <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def fit_size(draw, text, weight, max_width, start, floor=34, step=2):
    size = start
    while size > floor:
        font, _ = load_font(weight, size)
        if all(draw.textlength(line, font=font) <= max_width for line in wrap(draw, text, font, max_width)):
            return font, size
        size -= step
    font, _ = load_font(weight, floor)
    return font, floor


# Where the daily lanes' cards go. Under assets/ (gitignored) because the Facebook and
# Telegram lanes upload bytes, not URLs — only the Instagram lane needs site/social/.
LANE_CARD_DIRS = {"facebook": Path("assets/facebook"), "telegram": Path("assets/telegram")}

# Post art the lanes may NOT ship. The files under brand/ are logo explorations and
# comparison sheets from the identity work — the owner saw one on the Page on
# 15 Oct 2026 ("this is not my brand style"). Every social photo is a rendered card.
BANNED_PHOTO_PREFIXES = ("brand/",)


# What the kicker says for each rotation post type (the raw key is a variable name).
KICKER_NAMES = {"promo": "free documents", "educational": "know your rights", "pidgin": "oya, make we talk",
                "testimonial_style": "picture this", "state_spotlight": "state spotlight",
                "urgent": "don't wait", "engagement": "your turn", "tip": "tenant tip",
                "guide": "guide", "manual": "", "morning": "morning question", "deepdive": "new deep-dive · 9 min"}


def is_banned_photo(path):
    rel = str(path or "").replace("\\", "/").lstrip("./")
    return any(rel.startswith(prefix) or ("/" + prefix) in rel for prefix in BANNED_PHOTO_PREFIXES)


def _brief(visual, post_type, size, said=None):
    """(kicker, background, layout, big) from the brain's visual brief, or the lane's defaults.
    `said` is the card's own copy — the words the photograph behind it must match."""
    visual = dict(visual or {})
    if said and not visual.get("said"):
        visual["said"] = said
    kicker = (("DocOga · %s" % visual["kicker"]) if visual.get("kicker") else
              (("DocOga · %s" % KICKER_NAMES.get(post_type, post_type.replace("_", " "))) if post_type else "DocOga"))
    background = None
    if visual.get("plate") or visual.get("said"):
        # A network fetch, only when there are words to match. The brain's `plate` is the hint;
        # `said` (the card's own copy) is what the picture must match — tools/shot_match.py
        # scores every result against it, so a rotation card gets a photo as surely as a
        # brain card (owner, 17 Oct 2026: "make sure it matches what is being said").
        import shot_match
        background, _ = shot_match.photo_for(visual.get("said") or visual["plate"], hint=visual.get("plate"), size=size)
    layout = visual.get("layout") if visual.get("layout") in ("poster", "stat", "checklist") else "poster"
    return kicker, background, layout, (visual.get("big") or "").strip()


def card_for_post(message, day_iso, post_type, lane, out_dir=None, visual=None):
    """Render a lane's daily copy as the brand card; returns the repo-relative path.

    `message` may be MarkdownV2 (Telegram) or plain (Facebook) — the stripper in
    plain_for_card() handles both. The kicker names the lane's post type so a
    "tip" card and a "promo" card read differently at a glance. `visual` is the
    brain's brief (tools/brain.py): kicker, layout, big figure, plate query."""
    out_dir = Path(out_dir) if out_dir else LANE_CARD_DIRS[lane]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / ("%s_card_%s.jpg" % (lane, day_iso))
    kicker, background, layout, big = _brief(visual, post_type, (CARD_W, CARD_H), said=message)
    render(message, out, kicker=kicker, background=background, layout=layout, big=big)
    return str(out)


STORY_W, STORY_H = 1080, 1920        # 9:16 — Stories and Reels covers (docs/BRAND_STYLE.md §3)
STORY_SAFE = (250, 250)              # Facebook draws its own UI over the top and bottom bands


def story_for_post(message, day_iso, post_type, lane, out_dir=None, visual=None):
    """The same copy as a 9:16 Story frame, type kept out of the platform's chrome bands."""
    out_dir = Path(out_dir) if out_dir else LANE_CARD_DIRS[lane]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / ("%s_story_%s.jpg" % (lane, day_iso))
    kicker, background, layout, big = _brief(visual, post_type, (STORY_W, STORY_H), said=message)
    render(message, out, kicker=kicker, size=(STORY_W, STORY_H), safe=STORY_SAFE,
           background=background, layout=layout, big=big)
    return str(out)


def _fit_line(draw, text, weight, max_width, start, floor=60, step=4):
    """The largest size at which `text` fits on ONE line (the stat figure never wraps)."""
    size = start
    while size > floor:
        font, _ = load_font(weight, size)
        if draw.textlength(text, font=font) <= max_width:
            return font, size
        size -= step
    return load_font(weight, floor)[0], floor


def _numbered(rest):
    """Checklist layout: every body line carries its number, unless the writer already did."""
    out, n = [], 0
    for line in rest.split("\n"):
        if line.strip() and not line.strip().startswith(("http", "General information")):
            n += 1
            if not re.match(r"^\s*(\d+[.)]|[-•✓✔])\s", line):
                line = "%d. %s" % (n, line.strip())
        out.append(line)
    return "\n".join(out)


# ── The card's design system (18 Oct 2026, "make the design more beautiful") ──────────────
# The same language as the Short cover (tools/short_cover.py, docs/SHORT_COVER.md), because a
# feed that recognises the cover should recognise the card: the headline on stepped yellow
# slabs in navy Inter Black, a flat royal block offset behind the stack for depth (no shadow,
# no gradient — BRAND_STYLE §1/§4), a tracked small-caps kicker, body copy with the brand's
# devices as bullets (green ✓ validation, red ✗ rejection, royal numerals), the outlined
# "FREE · docoga.com.ng" chip, the giant tonal glyph when there is no photograph, film grain.
# Hierarchy by size (slab ≥ 1.6× body), ≤ 3 slab lines, 60-30-10 colour (navy / yellow / white),
# everything inside the 1:1 grid crop of a 4:5 post (Instagram's profile grid shows the centre
# square; 135 px top and bottom are lost) — the "squint test" these cards must pass at 200 px.
PANEL = (15, 61, 124)       # royal: the offset block, the numeral chips, the chip outline
NAVY2 = (12, 38, 70)        # the tonal glyph
FAINT = (96, 128, 170)
SOFT = (226, 234, 246)      # body white — a notch under pure white so the slab stays brightest
RED, GREEN = (255, 90, 95), (46, 204, 107)
GRID_SAFE = 135             # a 4:5 card loses this much top and bottom in the 1:1 grid
SLAB_PAD_X, SLAB_PAD_Y, SLAB_GAP, OFFSET = 28, 8, 6, 14
SLAB_MAX_LINES = 3

# Line markers the copy may carry. Detected on the raw text (before the emoji are stripped for
# drawing) so a "✅ Rent amount" line becomes a green check beside white words, not a bare line.
MARKERS = (
    ("check", re.compile(r"^\s*(?:\u2705|\u2714\ufe0f?|\u2713|\u2611\ufe0f?)\s*")),
    ("x", re.compile(r"^\s*(?:\u274c|\u2717|\u2718|\U0001f6ab)\s*")),
    ("num", re.compile(r"^\s*(\d{1,2})[.)]\s+")),
    ("option", re.compile(r"^\s*([A-D])[.)]\s+")),
    ("bullet", re.compile(r"^\s*(?:\u2022|\U0001f539|\U0001f538|\u25aa\ufe0f?|\u25e6|-|\u2013|\u2014|\u2192|\U0001f449)\s+")),
)
COUNTER = re.compile(r"^\s*(\d+)\s+of\s+(\d+)\s*$", re.I)
URL_IN_LINE = re.compile(r"\s*https?://\S+")


def classify(line):
    """(kind, label, words) for one body line: check / x / num / option / bullet / plain."""
    for kind, pattern in MARKERS:
        m = pattern.match(line)
        if m:
            label = m.group(1) if m.groups() else ""
            return kind, label, line[m.end():].strip()
    return "plain", "", line.strip()


def structure(text, footer=True, layout="poster"):
    """Headline + typed body lines from the lane's copy (plain or MarkdownV2 — both stripped).

    The first paragraph is the headline; every later line is body, with its marker read before
    the emoji are removed. Lines that only carried a link (or little more) are the caption's,
    not the card's — the chip at the foot already says where to go."""
    raw = _drop_hashtags((text or "").replace("**", "").replace("__", "").replace("~~", ""))
    parts = [b for b in raw.split("\n\n") if b.strip()] or [raw]
    headline = " ".join(plain_for_card(parts[0]).split())
    rest = "\n\n".join(parts[1:])
    if layout == "checklist" and rest:
        rest = _numbered(rest)
    body = []
    for line in rest.split("\n"):
        if not line.strip():
            if body and body[-1][0] != "gap":
                body.append(("gap", "", ""))
            continue
        had_url = bool(URL_IN_LINE.search(line))
        if footer and had_url:
            line = URL_IN_LINE.sub("", line)
            if len(line.split()) <= 3:
                continue
        kind, label, words = classify(line)
        words = " ".join(plain_for_card(words).split()).rstrip(":") if had_url else " ".join(plain_for_card(words).split())
        if words:
            body.append((kind, label, words))
    while body and body[-1][0] == "gap":
        body.pop()
    return headline, body


def _luma(region):
    import numpy as np
    a = np.asarray(region.convert("L"), dtype=np.float32)
    return float(a.mean()) if a.size else 0.0


def _band(image, y0, y1, alpha):
    """A translucent navy band behind the type when a photograph sits under it (contrast ≥ 7:1
    is what the yellow-on-navy thumbnail data rewards; the plate's own scrims are not enough on
    a bright picture)."""
    if alpha <= 0:
        return image
    band = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(band).rectangle([0, int(y0), image.width, int(y1)], fill=INK_BG + (int(alpha),))
    return Image.alpha_composite(image.convert("RGBA"), band).convert("RGB")


def _tracked(draw, xy, text, font, fill, tracking=6):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking
    return x - tracking


def _tracked_width(draw, text, font, tracking=6):
    return sum(draw.textlength(ch, font=font) for ch in text) + tracking * max(0, len(text) - 1)


def _badge(draw, cx, cy, r, color, shape):
    """The brand's two marks (BRAND_STYLE §5): green check = validation, red ✗ = rejection."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    lw = max(4, int(r * 0.26))
    if shape == "check":
        draw.line([(cx - r * .45, cy + r * .02), (cx - r * .08, cy + r * .38), (cx + r * .5, cy - r * .32)],
                  fill=WHITE, width=lw, joint="curve")
    else:
        draw.line([(cx - r * .38, cy - r * .38), (cx + r * .38, cy + r * .38)], fill=WHITE, width=lw)
        draw.line([(cx + r * .38, cy - r * .38), (cx - r * .38, cy + r * .38)], fill=WHITE, width=lw)


def _chip(draw, cx, cy, text, font, fill=WHITE, outline=PANEL, pad=(26, 14), width=3):
    tw = draw.textlength(text, font=font)
    asc, desc = font.getmetrics()
    th = asc + desc
    box = [cx - tw / 2 - pad[0], cy - th / 2 - pad[1], cx + tw / 2 + pad[0], cy + th / 2 + pad[1]]
    draw.rounded_rectangle(box, radius=int((box[3] - box[1]) / 2), outline=outline, width=width)
    draw.text((cx - tw / 2, cy - th / 2), text, font=font, fill=fill)
    return box


def tonal_glyph(image, letter, size, clip=None):
    """BRAND_STYLE §4: the headline's first letter as a giant royal watermark bleeding off the
    bottom-right — depth for a card with no photograph. `clip` = (y0, y1) keeps it out of a
    Story's chrome bands (the platform's own UI sits there; the band stays pure ground)."""
    if not letter:
        return image
    font, name = load_font("Black", size)
    if name.startswith("PIL-default"):
        return image
    w, h = image.size
    layer = image.copy()
    ImageDraw.Draw(layer).text((w - int(size * 0.50), h - int(size * 0.70)), letter, font=font, fill=NAVY2)
    if clip:
        y0, y1 = int(clip[0]), int(clip[1])
        image.paste(layer.crop((0, y0, w, y1)), (0, y0))
        return image
    return layer


def plan(draw, headline, body, big, frame):
    """Choose sizes so the whole piece fits the frame's safe box: slab headline when it can sit
    on ≤ 3 slabs at a size that out-weighs the body, else a white headline; body shrinks before
    it is cut. Returns a dict the drawing pass follows (also handy for tests)."""
    W, H, top, ceiling, tall = frame["w"], frame["h"], frame["top"], frame["ceiling"], frame["tall"]
    max_width = W - 2 * MARGIN
    slab_width = max_width - 2 * SLAB_PAD_X
    out = {"mode": "white", "max_width": max_width}
    # The stat figure: one line on the slab, as large as the width allows.
    if big:
        font, size = _fit_line(draw, big, "Black", slab_width, 230 if tall else 200, floor=84)
        out.update(big=big, big_font=font, big_size=size)
    # Slab headline: the largest size at which ≤ 3 lines fit.
    if headline:
        lo, hi = (72, 150) if tall else (64, 136)
        if big:
            lo, hi = (52, 84) if tall else (48, 76)   # under a stat the headline is the second voice
        for size in range(hi, lo - 1, -4):
            font, _ = load_font("Black", size)
            lines = wrap(draw, headline, font, slab_width)
            if size > (128 if tall else 112) and len(lines) > 2:
                continue        # three slabs of display type would be more yellow than card
            if len(lines) <= SLAB_MAX_LINES and not big:
                out.update(mode="slab", h_font=font, h_size=size, h_lines=lines)
                break
            if big and len(lines) <= 3:
                out.update(mode="stat", h_font=font, h_size=size, h_lines=lines)
                break
        if "h_font" not in out:
            start = (84 if tall else 72) if body else (112 if tall else 100)   # alone, the headline is the piece
            font, size = fit_size(draw, headline, "Black", max_width, start, floor=44)
            out.update(mode="stat" if big else "white", h_font=font, h_size=size,
                       h_lines=wrap(draw, headline, font, max_width))
    else:
        out.update(h_font=None, h_size=0, h_lines=[])
    # Body: shrink until the block fits, then (last resort) cut.
    chars = sum(len(w) for _, _, w in body)
    body_start = (60 if tall else 54) if chars < 220 else (52 if tall else 46) if chars < 400 else (44 if tall else 38)
    body_floor = 30
    if out["mode"] == "slab" and out["h_size"]:
        body_start = min(body_start, int(out["h_size"] / 1.6))   # hierarchy: the slab out-weighs the body
    body_start = max(body_start, body_floor)
    for bsize in range(body_start, body_floor - 1, -2):
        bfont, _ = load_font("Medium", bsize)
        indent = int(bsize * 1.5)
        blines = []
        for kind, label, words in body:
            if kind == "gap":
                blines.append(("gap", "", "", 0))
                continue
            width = max_width - (indent if kind != "plain" else 0)
            for i, ln in enumerate(wrap(draw, words, bfont, width)):
                blines.append((kind if i == 0 else "cont", label if i == 0 else "", ln, indent if kind != "plain" else 0))
        out.update(b_font=bfont, b_size=bsize, b_lines=blines, indent=indent)
        if _height(out, tall) <= ceiling - top:
            break
    # Cut if even the floor overflows: keep whole lines, end with an ellipsis.
    while out["b_lines"] and _height(out, tall) > ceiling - top:
        out["b_lines"].pop()
        if out["b_lines"]:
            k, l, t, ind = out["b_lines"][-1]
            out["b_lines"][-1] = (k, l, t.rstrip(" ,;:") + "\u2026", ind)
    out["height"] = _height(out, tall)
    return out


def _height(p, tall):
    h = 0
    if p.get("big"):
        h += int(p["big_size"] * 1.02) + 2 * SLAB_PAD_Y + 24
    if p["h_lines"]:
        lh = p["h_size"] * (1.0 if p["mode"] == "slab" else 1.06)
        if p["mode"] == "slab":
            h += len(p["h_lines"]) * (int(p["h_size"] * 1.0) + 2 * SLAB_PAD_Y + SLAB_GAP) - SLAB_GAP + OFFSET
        else:
            h += int(len(p["h_lines"]) * lh)
    if p["b_lines"]:
        h += (40 if tall else 34)
        for kind, _, _, _ in p["b_lines"]:
            h += int(p["b_size"] * 0.6) if kind == "gap" else int(p["b_size"] * 1.34)
    return h


def render(text, out_path, kicker="", quality=88, max_kb=900, footer=FOOTER, size=None, safe=(0, 0),
           background=None, layout="poster", big=""):
    """Draw `text` on a brand card (1080×1350 by default) and write a JPEG at `out_path`.

    `size` = (w, h) for another frame; `safe` = (top, bottom) pixels the platform covers with
    its own chrome (Stories), kept clear of type. `background` is a treated plate
    (tools/brain_visual.py) the navy sits on; `layout` is poster / stat (a `big` figure on the
    slab above the headline) / checklist (numbered body lines)."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    W, H = size or (globals()["CARD_W"], globals()["CARD_H"])
    safe_top, safe_bottom = safe
    tall = H >= 1700
    four_five = abs(W / H - 0.8) < 0.02
    if background is not None:
        image = background.convert("RGB").resize((W, H))
    else:
        image = Image.new("RGB", (W, H), INK_BG)
    draw = ImageDraw.Draw(image)

    headline, body = structure(text, footer=bool(footer), layout=layout)
    if not headline and not body:
        raise ValueError("nothing left to draw after stripping undrawable characters")
    big = " ".join(plain_for_card(big).split()) if (layout == "stat" and big) else ""

    # The safe box: Stories lose their chrome bands; a 4:5 card loses 135 px top and bottom in
    # the grid, so the piece lives in the centre square and breathes at the edges.
    edge_top = max(safe_top, GRID_SAFE if four_five else 0)
    edge_bottom = max(safe_bottom, GRID_SAFE if four_five else 0)
    kicker_h = (30 if tall else 26) + 28
    top = edge_top + (60 if four_five else 56) + (kicker_h if kicker else 0)
    chip_h = 64 if tall else 58
    ceiling = H - edge_bottom - (60 if four_five else 56) - (chip_h + 40 if footer else 0)
    frame = {"w": W, "h": H, "top": top, "ceiling": ceiling, "tall": tall}
    p = plan(draw, headline, body, big, frame)

    # Optical placement: a touch above true centre of the safe box.
    room = (ceiling - top) - p["height"]
    y0 = top + max(0, int(room * 0.40))

    if background is None:
        glyph = next((c for c in (big or headline) if c.isalnum()), "")
        image = tonal_glyph(image, glyph.upper(), int(H * 0.72),
                            clip=(safe_top, H - safe_bottom) if (safe_top or safe_bottom) else None)
    else:
        band_top = min(y0, top) - kicker_h - 40
        region = image.crop((0, band_top, W, min(H, y0 + p["height"] + 40)))
        luma = _luma(region)
        image = _band(image, band_top, y0 + p["height"] + 40, 188 if luma > 120 else 140 if luma > 70 else 92)
    draw = ImageDraw.Draw(image)
    max_width = p["max_width"]

    # Kicker: tracked small caps, muted, pinned to the top of the safe box like a masthead (so a
    # carousel's slides line up); a "2 of 6" label becomes a counter top-right and the kicker
    # says DocOga.
    if kicker:
        kfont, _ = load_font("SemiBold", 30 if tall else 26)
        ky = top - kicker_h
        label = kicker.strip()
        counter = COUNTER.match(label)
        if counter:
            right = "%s / %s" % counter.groups()
            draw.text((W - MARGIN - draw.textlength(right, font=kfont), ky), right, font=kfont, fill=MUTED)
            label = "DocOga"
        _tracked(draw, (MARGIN, ky), label.upper()[:40], kfont, MUTED, tracking=6)

    y = y0
    # The stat figure on its slab (one line), the headline under it in white.
    if big:
        bw = draw.textlength(big, font=p["big_font"])
        sh = int(p["big_size"] * 1.02) + 2 * SLAB_PAD_Y
        draw.rectangle([MARGIN + OFFSET, y + OFFSET, MARGIN + bw + 2 * SLAB_PAD_X + OFFSET, y + sh + OFFSET], fill=PANEL)
        draw.rectangle([MARGIN, y, MARGIN + bw + 2 * SLAB_PAD_X, y + sh], fill=ACCENT)
        asc, _ = p["big_font"].getmetrics()
        draw.text((MARGIN + SLAB_PAD_X, y + SLAB_PAD_Y + (sh - 2 * SLAB_PAD_Y - int(p["big_size"] * 1.02)) // 2 - int(p["big_size"] * 0.08)),
                  big, font=p["big_font"], fill=INK_BG)
        y += sh + 24
    if p["h_lines"]:
        if p["mode"] == "slab":
            size_ = p["h_size"]
            sh = int(size_ * 1.0) + 2 * SLAB_PAD_Y
            widths = [draw.textlength(ln, font=p["h_font"]) + 2 * SLAB_PAD_X for ln in p["h_lines"]]
            stack_h = len(widths) * (sh + SLAB_GAP) - SLAB_GAP
            # One flat royal block offset behind the whole stack: depth with no shadow.
            draw.rectangle([MARGIN + OFFSET, y + OFFSET, MARGIN + max(widths) + OFFSET, y + stack_h + OFFSET], fill=PANEL)
            for ln, wd in zip(p["h_lines"], widths):
                draw.rectangle([MARGIN, y, MARGIN + wd, y + sh], fill=ACCENT)
                draw.text((MARGIN + SLAB_PAD_X, y + SLAB_PAD_Y - int(size_ * 0.1)), ln, font=p["h_font"], fill=INK_BG)
                y += sh + SLAB_GAP
            y += OFFSET - SLAB_GAP
        else:
            lh = int(p["h_size"] * 1.06)
            for ln in p["h_lines"]:
                draw.text((MARGIN, y), ln, font=p["h_font"], fill=WHITE)
                y += lh

    if p["b_lines"]:
        y += (40 if tall else 34)
        bsize, bfont, indent = p["b_size"], p["b_font"], p["indent"]
        nfont, _ = load_font("Black", int(bsize * 0.78))
        for kind, label, ln, ind in p["b_lines"]:
            if kind == "gap":
                y += int(bsize * 0.6)
                continue
            cy = y + int(bsize * 0.62)
            r = int(bsize * 0.42)
            if kind == "check":
                _badge(draw, MARGIN + r, cy, r, GREEN, "check")
            elif kind == "x":
                _badge(draw, MARGIN + r, cy, r, RED, "x")
            elif kind in ("num", "option"):
                box = [MARGIN, cy - r, MARGIN + 2 * r, cy + r]
                draw.rounded_rectangle(box, radius=int(r * 0.3), fill=PANEL)
                tw = draw.textlength(label, font=nfont)
                nasc, ndesc = nfont.getmetrics()
                draw.text((MARGIN + r - tw / 2, cy - (nasc + ndesc) / 2 + int(bsize * 0.02)), label, font=nfont, fill=WHITE)
            elif kind == "bullet":
                d = max(5, int(bsize * 0.14))
                draw.rectangle([MARGIN + r - d, cy - d, MARGIN + r + d, cy + d], fill=MUTED)
            draw.text((MARGIN + ind, y), ln, font=bfont, fill=SOFT)
            y += int(bsize * 1.34)

    if footer:
        ffont, _ = load_font("SemiBold", 28 if tall else 26)
        label = ("FREE \u00b7 %s" % footer) if footer == FOOTER else footer
        _chip(draw, W / 2, H - edge_bottom - (60 if four_five else 56) - chip_h / 2, label, ffont)

    try:
        import blend_image
        image = blend_image.photo_grain(image, sigma=2.2, seed=11)
    except Exception:  # numpy missing on a thin runner: the card ships without grain
        pass

    data = _encode(image, quality)
    while len(data) > max_kb * 1024 and quality > 45:
        quality -= 7
        data = _encode(image, quality)
    out.write_bytes(data)
    return {"path": str(out), "bytes": len(data), "quality": quality,
            "width": W, "height": H, "ratio": W / H,
            "font": load_font("Black", 60)[1], "headline_lines": len(p["h_lines"]),
            "stripped": plain_for_card(text) != (text or "").strip(),
            "layout": layout, "plate": background is not None, "mode": p["mode"],
            "headline_size": p["h_size"], "body_size": p["b_size"] if p["b_lines"] else 0}


def _encode(image, quality):
    import io
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality, optimize=True, progressive=True,
               subsampling=1)  # 4:2:0 keeps the type crisp and the bytes down
    return buffer.getvalue()


# The card, its Story frame and its carousel slides (17 Oct 2026) — one day's renders share one
# date, and `prune` keeps the newest `keep` DAYS, so a carousel day does not cost six days of window.
DATED_RENDER = re.compile(r"^(\d{4}-\d{2}-\d{2})-(?:instagram(?:-story|-slide-\d+)?|threads(?:-evening|-morning)?)\.jpg$")


def prune(directory, keep=60):
    """Delete every dated render but the newest `keep`. Returns (deleted, kept).

    Two details are the whole design:

    * **mtime is useless here.** A CI checkout stamps every file with *today*, so the obvious
      `find -mtime +60` matches nothing forever and `site/social/` grows one JPEG a day without
      limit in the one directory the deploy publishes. The lane names its renders
      `YYYY-MM-DD-instagram.jpg`, and the name is the only clock that survives a re-clone.
    * **only its own files.** Anything else in that directory — a hand-added image, a future
      lane's naming — is not this step's to delete, so the pattern is exact rather than a prefix.

    `keep` is floored at 1 because a run that pruned today's own card would hand Instagram a URL
    that 404s, and that failure reads as a permissions problem.
    """
    keep = max(1, int(keep))
    directory = Path(directory)
    if not directory.is_dir():
        return [], []
    dated = sorted(p for p in directory.iterdir() if DATED_RENDER.match(p.name))
    days = sorted({DATED_RENDER.match(p.name).group(1) for p in dated})
    if len(days) <= keep:
        # Nothing past the window. Written as an early return rather than a slice expression:
        # `days[:-0]` is `days[0:]`, i.e. *everything*, which is the opposite of a retention
        # rule — a `…, … if … else …` one-liner here did exactly that on its first draft.
        return [], [p.name for p in dated]
    survivors = set(days[len(days) - keep:])
    doomed = [p for p in dated if DATED_RENDER.match(p.name).group(1) not in survivors]
    kept = [p for p in dated if DATED_RENDER.match(p.name).group(1) in survivors]
    for path in doomed:
        path.unlink()
    return [p.name for p in doomed], [p.name for p in kept]


def public_url(path, base_url):
    """The URL the deployed site serves this repo path at (`site/` is the web root)."""
    absolute = Path(path).resolve()
    relative = absolute.relative_to(ROOT) if str(absolute).startswith(str(ROOT)) else absolute
    serving = str(relative).replace(os.sep, "/")
    if serving.startswith("site/"):
        serving = serving[len("site/"):]
    return "%s/%s" % (base_url.rstrip("/"), serving.lstrip("/"))


def render_slides(args):
    """`--slides`: the carousel for the brain pack of `--brief`, one JPEG per slide.

    Prints `CARD_SLIDES=<n>` and `CARD_URLS=<url …>` (space-separated, in order). `CARD_SLIDES=0`
    with exit 0 means "no carousel today" — the pack had fewer than two lines or there is no
    pack — so the workflow falls back to the single card without going red.
    """
    import brain_drafts
    pack = brain_drafts.draft_for(args.brief) if args.brief else None
    slides = brain_drafts.carousel_slides(pack) if pack else []
    if not slides:
        print("CARD_SLIDES=0")
        print("CARD_URLS=")
        return 0
    size = (CARD_W, CARD_H)
    kicker, background, layout, big = _brief(brain_drafts.visual(pack), brain_drafts.post_type(pack), size)
    stem = re.sub(r"\.jpe?g$", "", args.out, flags=re.I)
    urls, total = [], 0
    for index, (label, text) in enumerate(slides, 1):
        out = "%s-%d.jpg" % (stem, index)
        # The hook and the close carry the brain's plate and kicker; the points sit on the
        # plain navy so the words, not the picture, are what a thumb stops on.
        first_or_last = index in (1, len(slides))
        result = render(text, out, kicker=(kicker or label) if index == 1 else label,
                        quality=args.quality, max_kb=args.max_kb,
                        footer="" if args.no_footer else FOOTER,
                        background=background if first_or_last else None,
                        layout=layout if first_or_last else "poster", big=big if index == 1 else "")
        urls.append(public_url(result["path"], args.base_url))
        total += result["bytes"]
        print("CARD_SLIDE=%d %s %dx%d %dKB" % (index, out, result["width"], result["height"], result["bytes"] // 1024))
    print("CARD_SLIDES=%d" % len(slides))
    print("CARD_URLS=%s" % " ".join(urls))
    print("CARD_BYTES=%d" % total)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a brand card for a URL-only API")
    parser.add_argument("--text", help="the copy to draw")
    parser.add_argument("--from-json", dest="from_json", help="read .text from a content JSON")
    parser.add_argument("--kicker", default="", help="small caps line above the rule")
    parser.add_argument("--out", help="where to write the JPEG")
    parser.add_argument("--prune", metavar="DIR",
                        help="delete every dated render in DIR but the newest --keep, then exit")
    parser.add_argument("--keep", type=int, default=60, help="how many dated renders to keep")
    parser.add_argument("--base-url", default=os.environ.get("SITE_BASE_URL", "https://docoga.com.ng"),
                        help="public origin the file will be served from")
    parser.add_argument("--quality", type=int, default=88)
    parser.add_argument("--max-kb", type=int, default=900)
    parser.add_argument("--no-footer", action="store_true")
    parser.add_argument("--story", action="store_true",
                        help="draw a 9:16 Story frame (1080x1920) with the platform's chrome bands kept clear")
    parser.add_argument("--brief", metavar="YYYY-MM-DD",
                        help="apply the brain's visual brief for this date when brain/drafts has one")
    parser.add_argument("--slides", action="store_true",
                        help="render the brain pack's carousel (needs --brief): --out is the stem, "
                             "files are <stem>-1.jpg … and CARD_URLS lists them in order")
    parser.add_argument("--print", dest="show", action="store_true")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.prune:
        deleted, kept = prune(args.prune, keep=args.keep)
        for name in deleted:
            print("pruned %s" % name)
        print("RENDER_PRUNED=%d RENDER_KEPT=%d" % (len(deleted), len(kept)))
        return 0
    if not args.out:
        parser.error("--out is required unless --prune is doing the work")

    if args.slides:
        return render_slides(args)

    text = args.text or ""
    if args.from_json:
        blob = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        text = blob.get("card_text") or blob.get("text") or ""   # card_text: a promo day's tighter card copy
        post_type = str(blob.get("post_type") or "")
        if not args.kicker and post_type:
            # the same words _brief() would choose — a rotation day's kicker is never the raw key
            args.kicker = "DocOga · " + KICKER_NAMES.get(post_type, post_type.replace("_", " "))

    frame = {"size": (STORY_W, STORY_H), "safe": STORY_SAFE} if args.story else {}
    brief = {}
    if args.brief:
        import brain_drafts
        pack = brain_drafts.draft_for(args.brief)
        size = frame.get("size", (CARD_W, CARD_H))
        if pack:
            kicker, background, layout, big = _brief(brain_drafts.visual(pack), brain_drafts.post_type(pack), size, said=text)
            brief = {"background": background, "layout": layout, "big": big}
            args.kicker = kicker
            print("CARD_BRIEF=%s layout=%s plate=%s" % (pack.get("theme"), layout, "yes" if background is not None else "no"))
        else:
            # No pack (rotation day, brain paused): the copy itself picks the photograph.
            _, background, _, _ = _brief({}, "", size, said=text)
            brief = {"background": background}
            print("CARD_BRIEF=rotation plate=%s" % ("yes" if background is not None else "no"))
    result = render(text, args.out, kicker=args.kicker, quality=args.quality,
                    max_kb=args.max_kb, footer="" if args.no_footer else FOOTER, **frame, **brief)

    absolute = Path(result["path"]).resolve()
    relative = absolute.relative_to(ROOT) if str(absolute).startswith(str(ROOT)) else absolute
    serving = str(relative).replace(os.sep, "/")
    # The public path drops `site/`: `wrangler.jsonc` publishes `./site` as the *root*, so
    # `site/social/x.jpg` is served at `/social/x.jpg`. Building the URL from the repo path
    # would hand Meta a `/site/` prefix that 404s forever, and Instagram's answer to a 404
    # is "Unsupported URL request" — which reads like a permissions bug and is not one.
    if serving.startswith("site/"):
        serving = serving[len("site/"):]
    url = "%s/%s" % (args.base_url.rstrip("/"), serving.lstrip("/"))
    print("CARD_PATH=%s" % relative)
    print("CARD_URL=%s" % url)
    print("CARD_BYTES=%d" % result["bytes"])
    print("CARD_SPEC=%dx%d %.3f:1 quality=%d font=%s"
          % (result["width"], result["height"], result["ratio"], result["quality"],
             result["font"]))
    if result["stripped"]:
        print("CARD_STRIPPED=1 — the copy contained characters the card cannot draw "
              "(they stay in the caption)")
    if not serving.startswith(("social/", "assets/")) and not str(relative).startswith("site/"):
        print("::warning title=render is outside site/::%s will not be publicly reachable, so "
              "Instagram cannot fetch it. Write renders under site/social/." % relative)
    if args.show:
        print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
