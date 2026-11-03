#!/usr/bin/env python3
"""freshness.py — honest "updated" dates, Article + BreadcrumbList JSON-LD, sitemap <lastmod>.

Why (3 Nov 2026, docs/GROWTH.md): Google retired FAQ rich results for everyone on 7 May 2026 and
its 15 May 2026 guide says no special markup is needed for AI Overviews — what still counts is
what always counted: a page that is plainly owned, plainly dated, and plainly about one thing.
Our 60 state pages carried no date and no structured data at all; the guide pages carried only
FAQPage. This module gives every generated page:

  * one visible line under the title — "Updated 3 November 2026 · law shelf reviewed 8 October
    2026 · DocOga" — with a <time datetime> the machine can read;
  * an Article JSON-LD block whose dateModified is THE SAME date (structured data that does not
    match the visible page is the one thing Google's guidance calls out), with author/publisher
    = DocOga, the canonical as mainEntityOfPage, the OG card as image, inLanguage en-NG, and the
    page's cited primary sources as `citation`;
  * a BreadcrumbList (Home → the national guide → this page);
  * a <lastmod> in the sitemap entry equal to the same date (Google reads lastmod when it is
    consistent; Bing hears about the change by IndexNow).

The date is honest by construction. A generator rebuilds all its pages on every run, so "today"
would be a lie for a page whose words did not change. stamp() compares the new page with the one
already on disk — with the three dated spots masked — and keeps the old date unless the content
really differs. Rebuild sixty pages, nothing moved → sixty unchanged dates. Fix one sentence on
one page → one page says today. No ledger file, nothing to forget.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

HOST = "https://docoga.com.ng"
ISO = "@@UPDATED_ISO@@"
HUMAN = "@@UPDATED_HUMAN@@"
LAGOS = dt.timezone(dt.timedelta(hours=1))

# the three places a date appears on a generated page; stamp() masks exactly these on the old file
_SPOTS = (
    re.compile(r'(data-updated=")(\d{4}-\d{2}-\d{2})(")'),
    re.compile(r'("dateModified": ")(\d{4}-\d{2}-\d{2})(")'),
    re.compile(r'(<time datetime=")(\d{4}-\d{2}-\d{2})(">)([^<]*)(</time>)'),
)


def today_iso(now=None) -> str:
    return (now or dt.datetime.now(LAGOS)).date().isoformat()


def human(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return "%d %s %d" % (d.day, d.strftime("%B"), d.year)


def previous_date(existing: str) -> str | None:
    m = _SPOTS[0].search(existing or "")
    return m.group(2) if m else None


def _mask(existing: str) -> str:
    s = _SPOTS[0].sub(lambda m: m.group(1) + ISO + m.group(3), existing)
    s = _SPOTS[1].sub(lambda m: m.group(1) + ISO + m.group(3), s)
    s = _SPOTS[2].sub(lambda m: m.group(1) + ISO + m.group(3) + HUMAN + m.group(5), s)
    return s


def stamp(path, html: str, today: str | None = None):
    """Fill the @@UPDATED_*@@ tokens in `html`. Keeps the date already on disk at `path` when the
    rest of the page is byte-identical; otherwise uses `today`. Returns (html, iso, changed)."""
    today = today or today_iso()
    p = Path(path)
    iso, changed = today, True
    if p.is_file():
        existing = p.read_text(encoding="utf-8", errors="replace")
        prev = previous_date(existing)
        if _mask(existing) == html:
            changed = False
            if prev:
                iso = prev
    out = html.replace(ISO, iso).replace(HUMAN, human(iso))
    return out, iso, changed


def updated_line(reviewed: str | None = None, reviewed_label: str = "law shelf reviewed") -> str:
    """The visible line. Carries the tokens; stamp() fills them."""
    extra = (" · %s %s" % (reviewed_label, human(reviewed))) if reviewed else ""
    return ('<p class="updated" data-updated="%s">Updated <time datetime="%s">%s</time>%s · '
            '<a href="%s/">DocOga</a></p>' % (ISO, ISO, HUMAN, extra, HOST))


def article(*, url: str, headline: str, description: str, image: str, citations=(), about: str = "",
            jurisdiction: str = "", date_published: str | None = None, language: str = "en-NG") -> dict:
    """schema.org Article. dateModified carries the token so it is always the visible date."""
    org = {"@type": "Organization", "name": "DocOga", "url": HOST + "/"}
    d = {
        "@context": "https://schema.org",
        "@type": "Article",
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "headline": headline[:110],
        "description": description,
        "image": image,
        "inLanguage": language,
        "isAccessibleForFree": True,
        "author": org,
        "publisher": {"@type": "Organization", "name": "DocOga", "url": HOST + "/",
                      "logo": {"@type": "ImageObject", "url": HOST + "/apple-touch-icon.png"}},
        "dateModified": ISO,
    }
    if date_published:
        d["datePublished"] = date_published
    cites = [c for c in citations if isinstance(c, str) and c.startswith("http")]
    if cites:
        d["citation"] = cites[:12]
    if about:
        ab = {"@type": "Legislation", "name": about}
        if jurisdiction:
            ab["legislationJurisdiction"] = {"@type": "AdministrativeArea", "name": jurisdiction}
        d["about"] = ab
    return d


def breadcrumbs(items) -> dict:
    """items: [(name, url), ...] from Home to this page."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(items)
        ],
    }


def breadcrumb_nav(items) -> str:
    """The visible trail the BreadcrumbList describes — same names, same URLs, current page unlinked.
    Google shows breadcrumbs from markup only when the page actually carries them (desktop results
    since Jan 2025), and its general rule is that markup must describe what the reader can see."""
    parts = []
    for i, (name, url) in enumerate(items):
        last = i == len(items) - 1
        parts.append('<span aria-current="page">%s</span>' % _esc(name) if last else '<a href="%s">%s</a>' % (url, _esc(name)))
    return '<nav class="crumbs" aria-label="Breadcrumb">%s</nav>' % " › ".join(parts)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


CRUMBS_CSS = ".crumbs{font-size:13px;color:#6B7A90;margin:0 0 10px}.crumbs a{color:#6B7A90}.crumbs span{color:#37455E}"


def jsonld(*blocks) -> str:
    return "\n".join('<script type="application/ld+json">\n%s\n</script>'
                     % json.dumps(b, ensure_ascii=False, indent=1) for b in blocks)


def sitemap_lastmod(xml: str, loc: str, iso: str) -> str:
    """Set <lastmod> on the <url> whose <loc> is `loc` (insert after <loc> if absent). No entry → unchanged."""
    pat = re.compile(r"(<url>\s*<loc>\s*%s\s*</loc>)(.*?)(</url>)" % re.escape(loc), re.S)
    m = pat.search(xml)
    if not m:
        return xml
    body = m.group(2)
    if "<lastmod>" in body:
        body = re.sub(r"<lastmod>[^<]*</lastmod>", "<lastmod>%s</lastmod>" % iso, body, count=1)
    else:
        body = "\n    <lastmod>%s</lastmod>" % iso + body
    return xml[:m.start()] + m.group(1) + body + m.group(3) + xml[m.end():]


def urls_from_file(html: str, pattern=r'https?://[^\s"<>\]]+') -> list[str]:
    return re.findall(pattern, html)
