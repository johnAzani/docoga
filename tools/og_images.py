#!/usr/bin/env python3
"""og_images.py — a brand preview image for every page, so a shared link is never a bare grey box.

Owner, 29 Oct 2026 (7:55pm): "Improve on what you think I have not added and is needed and can be
automated — remember the ₦0." Checked: not one page on docoga.com.ng carried an `og:image` — not
the homepage, not the 9 guides, not the 60 state pages, not the Brain's daily guides. So every
link pasted into WhatsApp, Facebook, Threads, LinkedIn, Telegram or X showed a text-only preview,
on the same day a "Share on WhatsApp" button went onto every page. Link previews with an image
are tapped more than previews without one; WhatsApp is where Nigerian rent talk happens.

What this does (₦0, no network, the renderer the lanes already use):
  * For every public page (site/*.html with a <title>, site/guides/*.html) render a 1200×630
    JPEG with tools/social_card.py — navy, slab headline from the page's <title>, DocOga chip —
    into site/og/<slug>.jpg. Only missing images are rendered (idempotent; `--force` redraws).
  * Inject (or refresh) the tags after og:description in the page:
        <meta property="og:image" content="https://docoga.com.ng/og/<slug>.jpg">
        <meta property="og:image:width" content="1200"> / height 630 / og:image:alt
        <meta name="twitter:card" content="summary_large_image">
    The generators (gen_guide_pages, gen_state_pages, guides_build) now emit the same tags
    themselves, so regeneration does not strip them; this tool covers the hand-written pages
    (index.html, power-of-attorney-nigeria.html …) and renders the files.
  * `--check` exits 1 if any public page lacks the tags or points at an image that is not there,
    or if an image is over OG_MAX_KB (WhatsApp drops previews above ~300 KB) — qa.py runs it.

    python3 tools/og_images.py            # render missing + inject tags
    python3 tools/og_images.py --force    # redraw every image (after a title change)
    python3 tools/og_images.py --check
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
OG_DIR = SITE / "og"
HOST = "https://docoga.com.ng"
W, H = 1200, 630
OG_MAX_KB = 280
SKIP = {"success.html", "admin.html", "tiktok-connect.html"}

TITLE = re.compile(r"<title>(.*?)</title>", re.S)
CANON = re.compile(r'<link rel="canonical" href="([^"]+)"')
OG_DESC = re.compile(r'<meta property="og:description" content="[^"]*">')
OG_BLOCK = re.compile(r'\n?<meta property="og:image" content="[^"]*">(?:\n?<meta (?:property|name)="(?:og:image:[a-z]+|twitter:card)" content="[^"]*">)*')
HOMEPAGE_TITLE = "Free tenancy agreement, notice to quit, rent receipt and invoice maker for Nigeria"


def pages():
    out = [p for p in sorted(SITE.glob("*.html")) if p.name not in SKIP and not p.name.startswith("admin")]
    out += sorted((SITE / "guides").glob("*.html"))
    return out


def slug_for(page: Path) -> str:
    if page.parent == SITE:
        return "home" if page.name == "index.html" else page.stem
    return "%s-%s" % (page.parent.name, page.stem)


def image_url(slug: str) -> str:
    return "%s/og/%s.jpg" % (HOST, slug)


def tags(slug: str, alt: str) -> str:
    return ('<meta property="og:image" content="%s">\n'
            '<meta property="og:image:width" content="%d">\n'
            '<meta property="og:image:height" content="%d">\n'
            '<meta property="og:image:alt" content="%s">\n'
            '<meta name="twitter:card" content="summary_large_image">'
            % (image_url(slug), W, H, html.escape(alt, quote=True)))


def clean_title(raw: str) -> str:
    t = html.unescape(re.sub(r"\s+", " ", raw or "")).strip()
    t = re.sub(r"\s*(?:\||—|–)\s*DocOga\s*$", "", t)
    t = re.sub(r"\s*\|\s*Nigeria\s*$", "", t)
    t = re.sub(r"\s*[—–-]\s*Free (?:Nigerian )?Generator \(\d{4}\)\s*$", "", t)
    return t or "DocOga"


def kicker_for(page: Path, title: str) -> str:
    if page.parent.name == "guides":
        return "DocOga · Guide"
    if page.name == "index.html":
        return "DocOga · The Oga of Documents"
    m = re.search(r" in ([A-Z][A-Za-z ]+?(?: State)?)(?: \([^)]*\))?[:—–-]", title)
    if m and page.stem.split("-")[-1] in ("lagos", "abuja", "rivers", "oyo", "kano", "enugu", "delta", "kaduna",
                                            "ogun", "anambra", "edo", "plateau"):
        return "DocOga · %s" % m.group(1).strip()
    return "DocOga · Free guide"


def headline_for(page: Path, title: str) -> str:
    if page.name == "index.html":
        return HOMEPAGE_TITLE
    t = re.sub(r"\s*\([^)]*\)", "", title)          # "(Benin City)" is for Google, not the card
    return t


def render(page: Path, out: Path, title: str) -> bool:
    """Draw the card. False (and no file) if the renderer cannot run — never raises."""
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import social_card
        social_card.render(headline_for(page, title), out, kicker=kicker_for(page, title), size=(W, H), quality=82)
        return out.is_file() and out.stat().st_size > 0
    except Exception as exc:  # a missing Pillow on a laptop must not break a build
        print("og: could not render %s: %s" % (page.name, str(exc)[:80]), file=sys.stderr)
        return False


def inject(text: str, slug: str, alt: str) -> str:
    block = tags(slug, alt)
    if ('og:image" content="%s"' % image_url(slug)) in text and 'name="twitter:card"' in text:
        return text            # the generator already wrote the right tags — leave its formatting alone
    if OG_BLOCK.search(text):
        return OG_BLOCK.sub("\n" + block, text, count=1)
    m = OG_DESC.search(text) or CANON.search(text) or TITLE.search(text)
    if not m:
        return text
    end = text.index(">", m.end() - 1) + 1 if m.re is CANON else m.end()
    sep = "\n" if text[end:end + 1] == "\n" else ""
    return text[:end] + sep + block + text[end:]


def run(force=False, log=print) -> int:
    OG_DIR.mkdir(exist_ok=True)
    drawn = tagged = 0
    for page in pages():
        text = page.read_text(encoding="utf-8")
        if not TITLE.search(text):
            continue
        slug = slug_for(page)
        title = clean_title((TITLE.search(text) or [None, ""])[1])
        out = OG_DIR / ("%s.jpg" % slug)
        if force or not out.is_file():
            if render(page, out, title):
                drawn += 1
        new = inject(text, slug, title)
        if new != text:
            page.write_text(new, encoding="utf-8")
            tagged += 1
    log("og_images: %d drawn, %d pages tagged" % (drawn, tagged))
    return 0


def check(log=print) -> int:
    bad = []
    for page in pages():
        text = page.read_text(encoding="utf-8")
        if not TITLE.search(text):
            continue
        m = re.search(r'<meta property="og:image" content="%s/og/([^"]+)\.jpg">' % re.escape(HOST), text)
        if not m:
            bad.append("%s: no og:image" % page.relative_to(SITE))
            continue
        if 'name="twitter:card" content="summary_large_image"' not in text:
            bad.append("%s: no twitter:card" % page.relative_to(SITE))
        f = OG_DIR / ("%s.jpg" % m.group(1))
        if not f.is_file():
            bad.append("%s: og image missing (%s)" % (page.relative_to(SITE), f.name))
        elif f.stat().st_size > OG_MAX_KB * 1024:
            bad.append("%s: og image %d KB > %d" % (page.relative_to(SITE), f.stat().st_size // 1024, OG_MAX_KB))
    for b in bad:
        log("og_images: " + b)
    log("og_images: %d problem(s)" % len(bad))
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    return check() if a.check else run(force=a.force)


if __name__ == "__main__":
    sys.exit(main())
