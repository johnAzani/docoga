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
                "testimonial_style": "from our users", "state_spotlight": "state spotlight",
                "urgent": "don't wait", "engagement": "your turn", "tip": "tenant tip",
                "guide": "guide", "manual": ""}


def is_banned_photo(path):
    rel = str(path or "").replace("\\", "/").lstrip("./")
    return any(rel.startswith(prefix) or ("/" + prefix) in rel for prefix in BANNED_PHOTO_PREFIXES)


def _brief(visual, post_type, size):
    """(kicker, background, layout, big) from the brain's visual brief, or the lane's defaults."""
    visual = dict(visual or {})
    kicker = (("DocOga · %s" % visual["kicker"]) if visual.get("kicker") else
              (("DocOga · %s" % KICKER_NAMES.get(post_type, post_type.replace("_", " "))) if post_type else "DocOga"))
    background = None
    if visual.get("plate"):
        import brain_visual  # a network fetch, only when a brief asks for a plate
        background = brain_visual.background_for(visual["plate"], size)
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
    kicker, background, layout, big = _brief(visual, post_type, (CARD_W, CARD_H))
    render(message, out, kicker=kicker, background=background, layout=layout, big=big)
    return str(out)


STORY_W, STORY_H = 1080, 1920        # 9:16 — Stories and Reels covers (docs/BRAND_STYLE.md §3)
STORY_SAFE = (250, 250)              # Facebook draws its own UI over the top and bottom bands


def story_for_post(message, day_iso, post_type, lane, out_dir=None, visual=None):
    """The same copy as a 9:16 Story frame, type kept out of the platform's chrome bands."""
    out_dir = Path(out_dir) if out_dir else LANE_CARD_DIRS[lane]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / ("%s_story_%s.jpg" % (lane, day_iso))
    kicker, background, layout, big = _brief(visual, post_type, (STORY_W, STORY_H))
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


def render(text, out_path, kicker="", quality=88, max_kb=900, footer=FOOTER, size=None, safe=(0, 0),
           background=None, layout="poster", big=""):
    """Draw `text` on a brand card (1080×1350 by default) and write a JPEG at `out_path`.

    `size` = (w, h) for another frame; `safe` = (top, bottom) pixels the platform
    covers with its own chrome (Stories), kept clear of type. `background` is a
    treated plate (tools/brain_visual.py) the navy sits on; `layout` is poster /
    stat (a `big` figure above the headline) / checklist (numbered body lines)."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    CARD_W, CARD_H = size or (globals()["CARD_W"], globals()["CARD_H"])
    safe_top, safe_bottom = safe
    if background is not None:
        image = background.convert("RGB").resize((CARD_W, CARD_H))
    else:
        image = Image.new("RGB", (CARD_W, CARD_H), INK_BG)
    draw = ImageDraw.Draw(image)

    body = plain_for_card(_drop_hashtags(plain_for_card(text)))
    if not body:
        raise ValueError("nothing left to draw after stripping undrawable characters")

    max_width = CARD_W - 2 * MARGIN
    top = 150 + safe_top

    # First line reads as the headline, the rest as body: a card is a poster, not a memo.
    parts = [block for block in body.split("\n\n") if block.strip()] or [body]
    headline, rest = parts[0], "\n\n".join(parts[1:]) if len(parts) > 1 else ""
    if layout == "checklist" and rest:
        rest = _numbered(rest)
    # A standalone link line duplicates the footer on a card: the caption keeps it, the card does not.
    if footer and rest:
        rest = "\n".join(ln for ln in rest.split("\n") if not re.fullmatch(r"\s*https?://\S+\s*", ln))
        rest = re.sub(r"\n{3,}", "\n\n", rest).strip()
    big = " ".join(plain_for_card(big).split()) if layout == "stat" else ""
    bfont_big, bsize_big = _fit_line(draw, big, "Black", max_width, 190, floor=72) if big else (None, 0)

    tall = CARD_H >= 1700            # a Story frame carries bigger type: it is held closer, alone
    hfont, hsize = fit_size(draw, headline, "Black", max_width,
                            (92 if tall else 74) if len(headline) < 90 else (70 if tall else 58))
    bfont, bsize = (None, 0)
    if rest:
        bfont, bsize = fit_size(draw, rest, "Regular", max_width,
                                (50 if tall else 42) if len(rest) < 340 else (40 if tall else 34))
    # An image that fills a phone screen and puts six lines of text in its upper third reads
    # as a mistake, and on a feed nobody scrolls to the bottom to check. Measure the block
    # first, then start it where it will look placed rather than dropped.
    headline_lines = len(wrap(draw, headline, hfont, max_width))
    body_lines = len(wrap(draw, rest, bfont, max_width)) if rest else 0
    big_block = (int(bsize_big * 1.08) + 18) if big else 0
    block = big_block + headline_lines * int(hsize * 1.18) + (26 + body_lines * int(bsize * 1.32) if rest else 0)
    ceiling, floor_top = CARD_H - 200 - safe_bottom, 150 + safe_top
    top = max(floor_top, min(ceiling - block, floor_top + (ceiling - floor_top - block) // 2))

    # Kicker and rule travel with the headline — the rule is the brand's separator and
    # sits above the headline, not under it.
    if kicker:
        kfont, _ = load_font("SemiBold", 30 if tall else 26)
        draw.text((MARGIN, top - (52 if tall else 46)), kicker.upper()[:40], font=kfont, fill=BLUE)
    draw.line([(MARGIN, top - 8), (MARGIN + 96, top - 8)], fill=ACCENT, width=4)
    y = top
    if big:
        # The stat layout: one figure in the accent, the yellow underline sweep under it (§5).
        draw.text((MARGIN, y), big, font=bfont_big, fill=WHITE)
        width = draw.textlength(big, font=bfont_big)
        draw.line([(MARGIN, y + int(bsize_big * 1.0)), (MARGIN + width, y + int(bsize_big * 1.0))],
                  fill=ACCENT, width=10)
        y += big_block
    for line in wrap(draw, headline, hfont, max_width):
        draw.text((MARGIN, y), line, font=hfont, fill=WHITE)
        y += int(hsize * 1.18)

    if rest:
        y += 26
        for line in wrap(draw, rest, bfont, max_width):
            if y > CARD_H - 200 - safe_bottom:
                draw.text((MARGIN, y), "…", font=bfont, fill=MUTED)
                break
            draw.text((MARGIN, y), line, font=bfont, fill=MUTED if line else WHITE)
            y += int(bsize * 1.32)

    if footer:
        ffont, _ = load_font("SemiBold", 24)
        width = draw.textlength(footer, font=ffont)
        draw.text(((CARD_W - width) / 2, CARD_H - 116 - safe_bottom), footer, font=ffont, fill=ACCENT)
        draw.line([(MARGIN, CARD_H - 150 - safe_bottom), (CARD_W - MARGIN, CARD_H - 150 - safe_bottom)],
                  fill=INK_PANEL, width=2)

    data = _encode(image, quality)
    while len(data) > max_kb * 1024 and quality > 45:
        quality -= 7
        data = _encode(image, quality)
    out.write_bytes(data)
    return {"path": str(out), "bytes": len(data), "quality": quality,
            "width": CARD_W, "height": CARD_H, "ratio": CARD_W / CARD_H,
            "font": load_font("Black", 60)[1], "headline_lines": len(wrap(draw, headline, hfont, max_width)),
            "stripped": plain_for_card(text) != (text or "").strip(),
            "layout": layout, "plate": background is not None}


def _encode(image, quality):
    import io
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality, optimize=True, progressive=True,
               subsampling=1)  # 4:2:0 keeps the type crisp and the bytes down
    return buffer.getvalue()


DATED_RENDER = re.compile(r"^\d{4}-\d{2}-\d{2}-instagram\.jpg$")


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
    if len(dated) <= keep:
        # Nothing past the window. Written as an early return rather than a slice expression:
        # `dated[:-0]` is `dated[0:]`, i.e. *everything*, which is the opposite of a retention
        # rule — a `…, … if … else …` one-liner here did exactly that on its first draft.
        return [], dated
    split = len(dated) - keep
    doomed, kept = dated[:split], dated[split:]
    for path in doomed:
        path.unlink()
    return [p.name for p in doomed], [p.name for p in kept]


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

    text = args.text or ""
    if args.from_json:
        blob = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        text = blob.get("text") or ""
        args.kicker = args.kicker or (blob.get("post_type") or "")

    frame = {"size": (STORY_W, STORY_H), "safe": STORY_SAFE} if args.story else {}
    brief = {}
    if args.brief:
        import brain_drafts
        pack = brain_drafts.draft_for(args.brief)
        if pack:
            size = frame.get("size", (CARD_W, CARD_H))
            kicker, background, layout, big = _brief(brain_drafts.visual(pack), brain_drafts.post_type(pack), size)
            brief = {"background": background, "layout": layout, "big": big}
            args.kicker = kicker
            print("CARD_BRIEF=%s layout=%s plate=%s" % (pack.get("theme"), layout, "yes" if background is not None else "no"))
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
