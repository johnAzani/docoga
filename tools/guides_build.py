#!/usr/bin/env python3
"""guides_build.py — every approved brain pack becomes a cited guide page on docoga.com.ng.

A social post lives a day. The same words, as a page with the section numbers, a FAQ block
and a link to the tool, are a Google result for years — and the site is already static files
on Cloudflare, so a page costs ₦0 and publishes with the brain's own commit. This is the one
piece of the brain that touches the website; it writes ONLY under site/guides/ and the sitemap,
never a tool page and never the payment flow. `BRAIN_GUIDES=off` turns it off.

    python3 tools/guides_build.py build            # packs dated ≤ today → site/guides/<theme>.html + index + sitemap
    python3 tools/guides_build.py build --day 2026-10-20
    python3 tools/guides_build.py ping             # IndexNow (Bing, Yandex, Naver; free) — only with INDEXNOW_KEY set

What a page carries: the headline as <h1>, the post's lines as the opening, "The law" — each
claim with its section and statute from the shelf (tools/law_index.py), the Tuesday quiz as a
FAQ (with FAQPage schema), the tool link for the post's state, and the standing "general
information, not legal advice" footer. Nothing is generated here: a page is a faithful
re-layout of a pack that already passed the citation, verification and lint gates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import brain_drafts as drafts  # noqa: E402
import law_index  # noqa: E402

SITE = Path(os.environ.get("DOCOGA_SITE") or (ROOT / "site"))
GUIDES_DIRNAME = "guides"
HOST = "https://docoga.com.ng"
LAGOS = ZoneInfo("Africa/Lagos")
MANIFEST = "guides.json"
MAX_INDEX = 400
INDEXNOW = "https://api.indexnow.org/indexnow"

CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;color:#141F33;background:#F5F7FB;line-height:1.6}
.wrap{max-width:760px;margin:0 auto;padding:20px 18px 110px}
.brand{display:inline-block;font-weight:900;font-size:20px;color:#0040E0;text-decoration:none;padding:10px 0}
h1{font-size:26px;line-height:1.25;margin:10px 0 14px}
.lead{font-size:17px;color:#37455E}
.box{background:#fff;border:1px solid #DCE4F0;border-radius:14px;padding:18px 20px;margin:20px 0}
h2{font-size:19px;margin-bottom:10px}
ul{padding-left:20px}
li{margin:8px 0;font-size:15px}
.law{font-size:13px;color:#5B6B85}
.cta{display:inline-block;background:#0040E0;color:#fff;font-weight:800;text-decoration:none;border-radius:10px;padding:14px 24px;font-size:16px;margin:14px 0}
details{background:#fff;border:1px solid #DCE4F0;border-radius:12px;padding:14px 18px;margin:10px 0}
summary{font-weight:700;cursor:pointer}
p{margin:8px 0}
.meta{font-size:13px;color:#5B6B85;margin-bottom:6px}
.links{font-size:14px}
.links a{color:#0040E0;text-decoration:none;font-weight:600;margin-right:12px;white-space:nowrap;display:inline-block}
footer{margin-top:34px;border-top:1px solid #DCE4F0;padding-top:16px;font-size:12.5px;color:#5B6B85}
.stickycta{position:fixed;left:0;right:0;bottom:0;z-index:60;background:#fff;border-top:1px solid #DCE4F0;box-shadow:0 -2px 14px rgba(20,31,51,.10);padding:10px 16px;display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap}
.stickycta span{font-size:13.5px;color:#141F33;font-weight:600}
.stickycta a{background:#0040E0;color:#fff;font-weight:800;text-decoration:none;border-radius:9px;padding:11px 18px;font-size:14.5px;white-space:nowrap}
@media print{.stickycta{display:none}}"""

MORE = (("notice-to-quit-nigeria.html", "Notice to quit: how many months"),
        ("caution-fee-nigeria.html", "Is the caution fee refundable?"),
        ("rent-receipt-format-nigeria.html", "Rent receipt format"),
        ("tenancy-agreement-nigeria.html", "Tenancy agreement format"),
        ("tenant-rights-nigeria.html", "Rights of a tenant in Nigeria"))


def enabled():
    return os.environ.get("BRAIN_GUIDES", "on").strip().lower() not in ("off", "0", "false", "no")


def guides_dir(site=None):
    return (Path(site) if site else SITE) / GUIDES_DIRNAME


def slug_for(pack):
    raw = str(pack.get("theme") or pack.get("post", {}).get("headline") or "guide").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")[:80] or "guide"
    state = str(pack.get("state") or "").strip().lower()
    if state and state not in slug:
        slug = "%s-%s" % (slug, state)
    return slug


def esc(text):
    return html.escape(str(text or ""), quote=True)


def description_for(pack):
    lines = pack.get("post", {}).get("lines") or []
    text = " ".join(str(x).strip() for x in lines)[:300]
    if len(text) > 155:
        text = text[:152].rsplit(" ", 1)[0] + "…"
    return text or str(pack.get("post", {}).get("headline") or "")


def law_rows(pack, facts_by_id=None):
    facts_by_id = facts_by_id if facts_by_id is not None else law_index.by_id()
    rows = []
    for c in pack.get("claims") or []:
        f = facts_by_id.get(str(c.get("fact_id") or ""))
        if not f:
            continue
        rows.append({"text": str(c.get("text") or "").strip(), "cite": f.get("cite") or "", "statute": f.get("statute") or "",
                     "state": f.get("state") or "", "fact": f.get("text") or ""})
    return rows


def faq_for(pack):
    q = pack.get("quiz") if isinstance(pack.get("quiz"), dict) else None
    out = []
    if q and q.get("question") and q.get("explanation"):
        out.append((str(q["question"]).strip(), str(q["explanation"]).strip()))
    t = (pack.get("threads") or {}).get("text") or ""
    m = re.search(r"([^.?!]*\?)\s*$", t.strip())
    if m and pack.get("post", {}).get("lines"):
        out.append((m.group(1).strip(), " ".join(str(x) for x in pack["post"]["lines"][:2])))
    return out[:3]


def page_html(pack, facts_by_id=None, now=None):
    now = now or dt.datetime.now(LAGOS)
    slug = slug_for(pack)
    url = "%s/%s/%s.html" % (HOST, GUIDES_DIRNAME, slug)
    headline = str(pack.get("post", {}).get("headline") or "").strip()
    lines = [str(x).strip() for x in (pack.get("post", {}).get("lines") or []) if str(x).strip()]
    rows = law_rows(pack, facts_by_id)
    faq = faq_for(pack)
    state = rows[0]["state"] if rows else ""
    statute = rows[0]["statute"] if rows else ""
    title = headline if len(headline) <= 60 else headline[:57].rsplit(" ", 1)[0] + "…"
    title_tag = "%s%s | DocOga" % (title, (" — " + state) if state and state.lower() not in title.lower() else "")
    desc = description_for(pack)
    tool_link = drafts.link_for(pack)
    tool_link += ("&" if "?" in tool_link else "?") + "s=g"
    day = str(pack.get("date") or now.date().isoformat())
    schema = {"@context": "https://schema.org", "@type": "Article", "headline": headline, "datePublished": day,
              "dateModified": now.date().isoformat(), "author": {"@type": "Organization", "name": "DocOga"},
              "publisher": {"@type": "Organization", "name": "DocOga", "url": HOST}, "mainEntityOfPage": url,
              "inLanguage": "en-NG", "about": statute or "Nigerian tenancy law"}
    faq_schema = ({"@context": "https://schema.org", "@type": "FAQPage",
                   "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
                  if faq else None)
    parts = ["<!DOCTYPE html>", '<html lang="en">', "<head>", '<meta charset="UTF-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             "<title>%s</title>" % esc(title_tag),
             '<meta name="description" content="%s">' % esc(desc),
             '<link rel="canonical" href="%s">' % esc(url),
             '<meta property="og:title" content="%s">' % esc(title_tag),
             '<meta property="og:description" content="%s">' % esc(desc),
             '<meta property="og:url" content="%s">' % esc(url),
             '<meta property="og:type" content="article">',
             '<script type="application/ld+json">%s</script>' % json.dumps(schema, ensure_ascii=False)]
    if faq_schema:
        parts.append('<script type="application/ld+json">%s</script>' % json.dumps(faq_schema, ensure_ascii=False))
    parts += ["<style>%s</style>" % CSS, "</head>", "<body>", '<div class="wrap">',
              '<a class="brand" href="%s/">DocOga</a>' % HOST,
              '<p class="meta">%s · %s</p>' % (esc(state or "Nigeria"), esc(dt.date.fromisoformat(day).strftime("%d %B %Y"))),
              "<h1>%s</h1>" % esc(headline)]
    if lines:
        parts.append('<p class="lead">%s</p>' % esc(lines[0]))
        if len(lines) > 1:
            parts.append('<div class="box">' + "".join("<p>%s</p>" % esc(x) for x in lines[1:]) + "</div>")
    if rows:
        parts.append('<div class="box"><h2>The law behind it</h2><ul>')
        for r in rows:
            parts.append("<li><b>%s</b><br><span class=\"law\">%s%s — %s</span></li>"
                         % (esc(r["text"]), esc(r["cite"] + ", " if r["cite"] else ""), esc(r["statute"]), esc(r["fact"])))
        parts.append("</ul></div>")
    parts.append('<div class="box"><h2>Make the document in 2 minutes — free</h2>'
                 "<p>DocOga works on your phone: answer simple questions, get a clean, standard Nigerian document you can "
                 "print, save as PDF or share on WhatsApp.</p>"
                 '<a class="cta" href="%s">Open the tool →</a></div>' % esc(tool_link))
    if faq:
        parts.append('<div class="box"><h2>Questions people ask</h2>')
        for q, a in faq:
            parts.append("<details><summary>%s</summary><p>%s</p></details>" % (esc(q), esc(a)))
        parts.append("</div>")
    parts.append('<div class="box links"><h2>More guides</h2>' + "".join('<a href="%s/%s">%s</a>' % (HOST, href, esc(label)) for href, label in MORE)
                 + '<a href="%s/%s/">All DocOga guides</a></div>' % (HOST, GUIDES_DIRNAME))
    parts.append("<footer><b>DocOga</b> — free Nigerian document tools.<br><br>General information about Nigerian law and practice, "
                 "current as at %s — not legal advice. Laws differ by state and change over time; confirm the position for your "
                 "case with a qualified Nigerian lawyer.</footer></div>" % esc(now.strftime("%B %Y")))
    parts.append('<div class="stickycta"><span><b>Oga Pass</b> — ₦2,000 · 30 days · all 10 tools · no banner</span>'
                 '<a href="%s/#pricing">Get the Pass</a></div>' % HOST)
    parts.append('<script src="/analytics-consent.js" data-track-page="true" defer></script></body></html>')
    return "\n".join(parts) + "\n"


def index_html(entries, now=None):
    now = now or dt.datetime.now(LAGOS)
    url = "%s/%s/" % (HOST, GUIDES_DIRNAME)
    items = "".join('<li><a href="%s/%s/%s.html">%s</a> <span class="law">· %s · %s</span></li>'
                    % (HOST, GUIDES_DIRNAME, esc(e["slug"]), esc(e["title"]), esc(e.get("state") or "Nigeria"), esc(e["date"]))
                    for e in entries[:MAX_INDEX])
    return ("<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>Rent, tenancy and landlord guides for Nigeria | DocOga</title>"
            "<meta name=\"description\" content=\"Short, cited guides to Nigerian tenancy law — notice periods, rent receipts, caution fees, "
            "agreements — one a day, each with the section of the law it rests on.\">"
            "<link rel=\"canonical\" href=\"%s\"><style>%s</style></head><body><div class=\"wrap\">"
            "<a class=\"brand\" href=\"%s/\">DocOga</a><h1>Rent and tenancy guides for Nigeria</h1>"
            "<p class=\"lead\">One short guide a day, each resting on a named section of the law. Updated %s.</p>"
            "<div class=\"box\"><ul>%s</ul></div>"
            "<footer>General information, not legal advice.</footer></div>"
            "<script src=\"/analytics-consent.js\" data-track-page=\"true\" defer></script></body></html>\n"
            % (esc(url), CSS, HOST, esc(now.strftime("%d %B %Y")), items))


def load_manifest(site=None):
    p = guides_dir(site) / MANIFEST
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def packs_through(day, days_back=10, drafts_dir=None):
    """Approved packs dated in (day-days_back, day] — oldest first so a repeated theme keeps the latest."""
    out = []
    for i in range(days_back, -1, -1):
        d = day - dt.timedelta(days=i)
        pack = drafts.draft_for(d) if drafts_dir is None else _draft_in(drafts_dir, d)
        if pack:
            out.append(pack)
    return out


def _draft_in(folder, d):
    p = Path(folder) / ("%s.json" % d.isoformat())
    try:
        pack = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return pack if pack.get("status") == "approved" and pack.get("date") == d.isoformat() else None


def update_sitemap(site, urls, now=None):
    """Add <url> entries for the guides that are not yet in site/sitemap.xml. Idempotent; never removes."""
    now = now or dt.datetime.now(LAGOS)
    p = Path(site) / "sitemap.xml"
    if not p.is_file():
        return 0
    text = p.read_text(encoding="utf-8")
    added = 0
    for u in urls:
        if ("<loc>%s</loc>" % u) in text:
            continue
        entry = ("  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.6</priority>\n  </url>\n"
                 % (u, now.date().isoformat()))
        text = text.replace("</urlset>", entry + "</urlset>", 1)
        added += 1
    if added:
        p.write_text(text, encoding="utf-8")
    return added


def build(day=None, site=None, now=None, log=print, drafts_dir=None):
    """Returns the list of URLs written or refreshed this run."""
    site = Path(site) if site else SITE
    now = now or dt.datetime.now(LAGOS)
    day = day or now.date()
    folder = guides_dir(site)
    folder.mkdir(parents=True, exist_ok=True)
    manifest = {e["slug"]: e for e in load_manifest(site)}
    facts_by_id = law_index.by_id()
    written = []
    for pack in packs_through(day, drafts_dir=drafts_dir):
        if not pack.get("claims"):
            # a page with no cited law is an opinion; the site only carries law
            continue
        slug = slug_for(pack)
        page = page_html(pack, facts_by_id, now=now)
        target = folder / ("%s.html" % slug)
        if target.is_file() and target.read_text(encoding="utf-8") == page:
            continue
        target.write_text(page, encoding="utf-8")
        manifest[slug] = {"slug": slug, "title": pack["post"]["headline"], "date": pack["date"],
                          "state": (law_rows(pack, facts_by_id) or [{}])[0].get("state", ""), "theme": pack.get("theme")}
        written.append("%s/%s/%s.html" % (HOST, GUIDES_DIRNAME, slug))
        log("guide: %s ← %s" % (target.relative_to(site), pack["date"]))
    entries = sorted(manifest.values(), key=lambda e: (e["date"], e["slug"]), reverse=True)
    if written or not (folder / "index.html").is_file():
        (folder / MANIFEST).write_text(json.dumps(entries, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (folder / "index.html").write_text(index_html(entries, now=now), encoding="utf-8")
        added = update_sitemap(site, ["%s/%s/" % (HOST, GUIDES_DIRNAME)] + written, now=now)
        log("guides: %d page(s) written, %d sitemap entr%s added, %d in the index"
            % (len(written), added, "y" if added == 1 else "ies", len(entries)))
    else:
        log("guides: nothing new")
    return written


def ping(urls, key=None, http=None, log=print):
    """IndexNow — one POST tells Bing/Yandex/Naver the pages exist. Free. Needs the key file on the site."""
    key = key or os.environ.get("INDEXNOW_KEY", "").strip()
    if not key or not urls:
        log("indexnow: %s" % ("no key (set the INDEXNOW_KEY variable and commit site/<key>.txt)" if not key else "nothing to ping"))
        return False
    body = json.dumps({"host": HOST.split("//")[1], "key": key, "keyLocation": "%s/%s.txt" % (HOST, key), "urlList": list(urls)[:100]}).encode()
    req = urllib.request.Request(INDEXNOW, data=body, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        if http:
            status = http(req)
        else:
            with urllib.request.urlopen(req, timeout=20) as resp:
                status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log("indexnow: unreachable — %s" % str(exc)[:80])
        return False
    ok = status in (200, 202)
    log("indexnow: HTTP %s for %d url(s)%s" % (status, len(urls), "" if ok else " — key file missing on the site?"))
    return ok


def ensure_key_file(site=None, key=None):
    key = key or os.environ.get("INDEXNOW_KEY", "").strip()
    if not key or not re.fullmatch(r"[A-Za-z0-9\-]{8,128}", key):
        return None
    p = (Path(site) if site else SITE) / ("%s.txt" % key)
    if not p.is_file():
        p.write_text(key + "\n", encoding="utf-8")
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description="brain packs → cited guide pages")
    ap.add_argument("command", choices=("build", "ping"))
    ap.add_argument("--day", default="")
    ap.add_argument("--site", default=str(SITE))
    a = ap.parse_args(argv)
    if not enabled():
        print("guides: off (BRAIN_GUIDES)")
        print("GUIDES_WRITTEN=0")
        return 0
    if a.command == "ping":
        urls = ["%s/%s/%s.html" % (HOST, GUIDES_DIRNAME, e["slug"]) for e in load_manifest(a.site)[:20]]
        ensure_key_file(a.site)
        ok = ping(urls)
        print("INDEXNOW=%s" % ("ok" if ok else "skipped"))
        return 0
    day = dt.date.fromisoformat(a.day) if a.day else None
    written = build(day=day, site=a.site)
    print("GUIDES_WRITTEN=%d" % len(written))
    for u in written:
        print("GUIDE_URL=%s" % u)
    if written:
        ensure_key_file(a.site)
        ping(written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
