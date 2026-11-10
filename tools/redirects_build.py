#!/usr/bin/env python3
"""site/_redirects — a permanent 301 from every `/x.html` to its clean URL (10 Nov 2026).

Why: Cloudflare's default `html_handling = "auto-trailing-slash"` answers `/x.html` with a **307**
to `/x`. A 307 is a *temporary* redirect, and Google treats it as one: two weeks after the clean
canonicals of 28 Oct (`tools/clean_urls.py`), the 9 Nov Search Console pull still showed the same
page counted twice — `/notice-to-quit-nigeria` 74 impressions AND `/notice-to-quit-nigeria.html`
33; `/notice-to-quit-kano` and `.html`, `/notice-to-quit-enugu` and `.html`, `/rent-receipt-lagos`
and `.html` — the position of every split page diluted between its two selves ("quit notice":
`.html` at position 1.0 with 0 clicks). A `_redirects` file in the asset directory is read by
Workers static assets before HTML handling ("redirects are always followed, regardless of whether
or not an asset matches"), so a **301** there is what Google needs to fold the two into one. The
site worker is assets-only (`wrangler.jsonc` has no `main`), so the file applies to every request.

Static lines only (one per page; the limit is 2,000 and we have about a hundred): the docs allow a
single splat but show it only at the end of a path, so `/*.html` is not relied on. The guides lane
writes new pages nightly — `tools/guides_build.py` calls `build()` after it builds, and the brain
workflow commits `site/_redirects` with the guides.

    python3 tools/redirects_build.py           # write site/_redirects
    python3 tools/redirects_build.py --check   # exit 1 when the file is missing or stale
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
OUT = SITE / "_redirects"
# Functional or private pages: noindex, query strings that matter, the owner dashboard. They keep
# Cloudflare's own 307 and are never listed (a 301 on /admin.html would also be a public hint).
SKIP = {"success.html", "admin.html", "tiktok-connect.html"}
HEADER = """# Permanent redirects for Workers static assets (tools/redirects_build.py — generated, do not edit).
# Cloudflare 307s /x.html → /x by default; Google reads a 307 as temporary and kept indexing both
# (Search Console, 9 Nov 2026). A 301 here is evaluated before HTML handling and folds them.
"""


def pairs(site=None):
    """[(source, destination)] for every public HTML page, sorted, clean URLs as the site links them."""
    site = Path(site or SITE)
    out = []
    for path in sorted(site.rglob("*.html")):
        rel = path.relative_to(site).as_posix()
        if path.name in SKIP or rel.startswith("admin/"):
            continue
        if path.name == "index.html":
            dest = "/" + rel[: -len("index.html")]
        else:
            dest = "/" + rel[: -len(".html")]
        out.append(("/" + rel, dest))
    return out


def render(site=None):
    return HEADER + "".join("%s %s 301\n" % (src, dst) for src, dst in pairs(site))


def build(site=None, out=None):
    text = render(site)
    target = Path(out or (Path(site) / "_redirects" if site else OUT))
    changed = (not target.exists()) or target.read_text(encoding="utf-8") != text
    if changed:
        target.write_text(text, encoding="utf-8")
    return changed


def check(site=None, out=None):
    target = Path(out or (Path(site) / "_redirects" if site else OUT))
    if not target.exists():
        return "site/_redirects missing — run python3 tools/redirects_build.py"
    if target.read_text(encoding="utf-8") != render(site):
        return "site/_redirects stale — run python3 tools/redirects_build.py"
    return ""


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        problem = check()
        print(problem or "redirects_build: current (%d rules)" % len(pairs()))
        return 1 if problem else 0
    changed = build()
    print("redirects_build: %s (%d rules)" % ("wrote site/_redirects" if changed else "current", len(pairs())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
