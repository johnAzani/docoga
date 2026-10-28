#!/usr/bin/env python3
"""Clean URLs everywhere Google reads them — because Cloudflare already serves them that way.

The site is published as Cloudflare Workers static assets with the default
``html_handling = "auto-trailing-slash"``: a request for ``/notice-to-quit-nigeria.html`` is
answered **307 → /notice-to-quit-nigeria**, and the bare URL is the one that returns 200
(developers.cloudflare.com/workers/static-assets/routing/advanced/html-handling/). Until
28 Oct 2026 every canonical, og:url, sitemap <loc> and JSON-LD url said ``…/x.html`` — a
canonical that redirects away from itself. Search Console showed the cost: the same page
indexed twice ("quit notice": `/notice-to-quit-nigeria.html` position 1.0, 48 impressions AND
`/notice-to-quit-nigeria` position 1.4, 8 impressions; 213 of 613 impressions split that way).

    python3 tools/clean_urls.py          # rewrite site/**/*.html + sitemap.xml (idempotent)
    python3 tools/clean_urls.py --check  # exit 1 if any canonical / og:url / sitemap loc still ends .html

Rules (applied to every page except the ones listed in SKIP — the payment success page and the
admin/connect pages are noindex and carry functional query strings; they are left alone):
  * https://docoga.com.ng/<dir>/index.html  → https://docoga.com.ng/<dir>/
  * https://docoga.com.ng/<path>.html       → https://docoga.com.ng/<path>   (#hash / ?query kept)
  * href="<page>.html…" (relative, top-level pages) → href="/<page>…";  href="index.html…" → href="/…"
Nothing else is touched: no text, no scripts, no `receiptCanonical()`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
HOST = "https://docoga.com.ng"
SKIP = {"success.html", "admin.html", "tiktok-connect.html"}

ABS_INDEX = re.compile(r"https://docoga\.com\.ng/((?:[A-Za-z0-9_-]+/)*)index\.html(?=[\"'#?<\s])")
ABS_PAGE = re.compile(r"https://docoga\.com\.ng/([A-Za-z0-9_/-]+?)\.html(?=[\"'#?<\s])")
REL_INDEX = re.compile(r'href="index\.html(#[^"]*)?"')
REL_PAGE = re.compile(r'href="([a-z0-9-]+)\.html((?:#|\?)[^"]*)?"')
CANON = re.compile(r'(rel="canonical" href="|property="og:url" content="|<loc>)([^"<]+)')


def clean_text(text: str, *, relative: bool) -> str:
    text = ABS_INDEX.sub(lambda m: "%s/%s" % (HOST, m.group(1)), text)
    text = ABS_PAGE.sub(lambda m: "%s/%s" % (HOST, m.group(1)), text)
    if relative:
        text = REL_INDEX.sub(lambda m: 'href="/%s"' % (m.group(1) or ""), text)
        text = REL_PAGE.sub(lambda m: 'href="/%s%s"' % (m.group(1), m.group(2) or ""), text)
    return text


def targets():
    for p in sorted(SITE.rglob("*.html")):
        if p.name in SKIP or p.name.startswith("admin"):
            continue
        yield p


def rewrite(log=print) -> int:
    changed = 0
    for p in list(targets()) + [SITE / "sitemap.xml"]:
        old = p.read_text(encoding="utf-8")
        # relative-link rewriting only for top-level pages (a guide's "x.html" means guides/x)
        new = clean_text(old, relative=(p.parent == SITE and p.suffix == ".html"))
        if new != old:
            p.write_text(new, encoding="utf-8")
            changed += 1
            log("clean_urls: %s" % p.relative_to(ROOT))
    log("clean_urls: %d file(s) rewritten" % changed)
    return changed


def offenders():
    """(file, url) pairs where a canonical, og:url or sitemap loc still ends in .html."""
    out = []
    for p in list(targets()) + [SITE / "sitemap.xml"]:
        for m in CANON.finditer(p.read_text(encoding="utf-8")):
            url = m.group(2)
            if url.startswith(HOST) and url.split("#")[0].split("?")[0].endswith(".html"):
                out.append((str(p.relative_to(ROOT)), url))
    return out


def main(argv) -> int:
    if "--check" in argv:
        bad = offenders()
        for f, u in bad[:20]:
            print("clean_urls: %s → %s (Cloudflare 307s this to the bare URL)" % (f, u))
        print("clean_urls: %d offender(s)" % len(bad))
        return 1 if bad else 0
    rewrite()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
