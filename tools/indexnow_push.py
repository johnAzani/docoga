#!/usr/bin/env python3
"""indexnow_push.py — tell Bing, Yandex, Naver and Seznam which pages just changed (₦0).

Why (3 Nov 2026, docs/GROWTH.md): the site had an IndexNow routine since the guides lane, but
it only ran for the Brain's guide pages, and only when the INDEXNOW_KEY variable was set — and
the key file that proves ownership (site/<key>.txt) had never reached main, so every ping was
answered with "key file missing". Meanwhile 60 state pages, the sample page and three guides
changed this week and nobody told any engine. Google ignores IndexNow; Bing does not — and the
Bing index is what Copilot, DuckDuckGo, Yahoo and (in part) ChatGPT search read from. A page can
wait weeks to be re-crawled or be fetched within the hour. The hour is free.

The key is NOT a secret. IndexNow's whole proof of ownership is that the key is readable at the
site root, so it lives in the repository as site/<key>.txt and as DEFAULT_KEY in guides_build.
Google: https://www.indexnow.org/documentation (key 8–128 chars of [a-zA-Z0-9-]; up to 10,000
URLs per POST; 200/202 = received, which is not the same as indexed).

    python3 tools/indexnow_push.py --before <sha> --after <sha>   # what this push changed
    python3 tools/indexnow_push.py --all                           # every URL in the sitemap
    python3 tools/indexnow_push.py --before <sha> --after <sha> --dry-run

Only URLs that are in site/sitemap.xml are ever submitted — the sitemap is the one list of pages
meant to be public, so /admin, /success and the samples/ PDFs (noindex by design) can never leak
into a ping. Prints INDEXNOW=ok|skipped|failed and INDEXNOW_URLS=<n>; always exits 0 — a search
engine that did not pick up the phone is not a red run.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import guides_build  # noqa: E402

HOST = guides_build.HOST
SITE = ROOT / "site"
MAX_URLS = 10_000


def sitemap_urls(text: str) -> list[str]:
    return sorted(set(re.findall(r"<loc>\s*(https://docoga\.com\.ng/[^<\s]*)\s*</loc>", text or "")))


def clean_url(rel: str) -> str:
    """site/notice-to-quit-edo.html → https://docoga.com.ng/notice-to-quit-edo (Cloudflare 307s the .html)."""
    rel = rel.replace("\\", "/")
    if rel.startswith("site/"):
        rel = rel[5:]
    if rel == "index.html":
        return HOST + "/"
    if rel.endswith("/index.html"):
        return "%s/%s/" % (HOST, rel[:-11])
    if rel.endswith(".html"):
        rel = rel[:-5]
    return "%s/%s" % (HOST, rel)


def _git(*args: str, cwd: Path = ROOT) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, OSError):
        return None


def changed_urls(before: str, after: str, root: Path = ROOT) -> list[str] | None:
    """URLs of the pages a push changed, restricted to the sitemap. None when git cannot see
    `before` (shallow checkout, forced push) — the caller then falls back to the whole sitemap."""
    if not before or set(before) == {"0"}:
        return None
    out = _git("diff", "--name-only", before, after, "--", "site", cwd=root)
    if out is None:
        return None
    current = sitemap_urls((root / "site" / "sitemap.xml").read_text(encoding="utf-8", errors="replace")
                           if (root / "site" / "sitemap.xml").is_file() else "")
    public = set(current)
    urls = set()
    for line in out.splitlines():
        line = line.strip()
        if line.endswith(".html"):
            u = clean_url(line)
            if u in public:
                urls.add(u)
    if "site/sitemap.xml" in out:
        old = _git("show", "%s:site/sitemap.xml" % before, cwd=root)
        if old is not None:
            urls.update(set(current) - set(sitemap_urls(old)))     # pages new to the sitemap
    return sorted(urls)


def all_urls(root: Path = ROOT) -> list[str]:
    p = root / "site" / "sitemap.xml"
    return sitemap_urls(p.read_text(encoding="utf-8", errors="replace")) if p.is_file() else []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--before", default=os.environ.get("INDEXNOW_BEFORE", ""))
    ap.add_argument("--after", default=os.environ.get("INDEXNOW_AFTER", "HEAD"))
    ap.add_argument("--all", action="store_true", help="submit every sitemap URL (first run, or after a key change)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args(argv)
    root = Path(a.root)

    key = guides_build.indexnow_key()
    key_file = root / "site" / ("%s.txt" % key)
    if not key_file.is_file() or key_file.read_text(encoding="utf-8").strip() != key:
        print("indexnow: key file site/%s.txt missing or wrong — commit it; engines verify the key there" % key)
        print("INDEXNOW=failed")
        print("INDEXNOW_URLS=0")
        return 0

    why = "every sitemap URL"
    urls = all_urls(root) if a.all else changed_urls(a.before, a.after or "HEAD", root)
    if urls is None:
        urls, why = all_urls(root), "every sitemap URL (the push's parent is not visible here)"
    elif not a.all:
        why = "pages changed between %s and %s" % (a.before[:7], (a.after or "HEAD")[:7])
    urls = urls[:MAX_URLS]
    print("indexnow: %d url(s) — %s" % (len(urls), why))
    for u in urls[:40]:
        print("  " + u)
    if len(urls) > 40:
        print("  … and %d more" % (len(urls) - 40))
    if not urls:
        print("INDEXNOW=skipped")
        print("INDEXNOW_URLS=0")
        return 0
    if a.dry_run:
        print("INDEXNOW=dry-run")
        print("INDEXNOW_URLS=%d" % len(urls))
        return 0
    ok = guides_build.ping(urls, key=key)
    print("INDEXNOW=%s" % ("ok" if ok else "failed"))
    print("INDEXNOW_URLS=%d" % len(urls))
    return 0


if __name__ == "__main__":
    sys.exit(main())
