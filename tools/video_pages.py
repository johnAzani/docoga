#!/usr/bin/env python3
"""A transcript page on docoga.com.ng for every published Deep-Dive — the video's home on the web.

    python3 tools/video_pages.py build            # site/videos/<id>.html + index, sitemap entries
    python3 tools/video_pages.py build --ping     # …and IndexNow (only with INDEXNOW_KEY)

Why (visibility research, 17 Oct 2026): YouTube indexes a description; Google indexes a page.
A nine-minute episode is ~1,500 words of exactly what Nigerians type into Google — "rent
receipt Lagos Tenancy Law", "caution fee refund" — and none of it is searchable while it lives
only inside an MP4. The page carries the full transcript by chapter, the player, VideoObject
structured data (so Google can show the video result with the thumbnail and chapters), and
the tool link. It costs nothing: the words are in episodes/<id>/script.txt, the chapters in
episodes/<id>/episode.json, the video id in logs/youtube_longform.json, and the site deploys
from main on push. An unlisted episode is embeddable, so the page is its public front door.

Idempotent and safe: a page is rewritten only when its content changes, the sitemap gains an
entry once, and nothing here can fail a publish (exit 0 with a notice when there is nothing).
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(os.environ.get("DOCOGA_SITE") or (ROOT / "site"))
EPISODES = ROOT / "episodes"
LEDGER = ROOT / "logs" / "youtube_longform.json"
BUILD = ROOT / "build" / "deepdive"
HOST = "https://docoga.com.ng"
DIRNAME = "videos"
LAGOS = ZoneInfo("Africa/Lagos")
CHUNK = re.compile(r"^--- C(\d+) ---\s*$", re.M)

CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;color:#141F33;background:#F5F7FB;line-height:1.65}
.wrap{max-width:760px;margin:0 auto;padding:20px 18px 110px}
.brand{display:inline-block;font-weight:900;font-size:20px;color:#0040E0;text-decoration:none;padding:10px 0}
h1{font-size:26px;line-height:1.25;margin:10px 0 14px}
.lead{font-size:17px;color:#37455E}
.player{position:relative;padding-top:56.25%;background:#0B1733;border-radius:14px;overflow:hidden;margin:18px 0}
.player iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.box{background:#fff;border:1px solid #DCE4F0;border-radius:14px;padding:18px 20px;margin:20px 0}
h2{font-size:19px;margin-bottom:10px}
h3{font-size:16px;margin:18px 0 6px}
ol,ul{padding-left:20px}
li{margin:6px 0;font-size:15px}
.chapters a{color:#0040E0;text-decoration:none;font-weight:600}
.t{font-variant-numeric:tabular-nums;color:#5B6B85;margin-right:8px}
p{margin:8px 0;font-size:15.5px}
.meta{font-size:13px;color:#5B6B85;margin-bottom:6px}
.cta{display:inline-block;background:#0040E0;color:#fff;font-weight:800;text-decoration:none;border-radius:10px;padding:14px 24px;font-size:16px;margin:14px 0}
.links a{color:#0040E0;text-decoration:none;font-weight:600;margin-right:12px;display:inline-block}
footer{margin-top:34px;border-top:1px solid #DCE4F0;padding-top:16px;font-size:12.5px;color:#5B6B85}
.stickycta{position:fixed;left:0;right:0;bottom:0;z-index:60;background:#fff;border-top:1px solid #DCE4F0;box-shadow:0 -2px 14px rgba(20,31,51,.10);padding:10px 16px;display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap}
.stickycta span{font-size:13.5px;color:#141F33;font-weight:600}
.stickycta a{background:#0040E0;color:#fff;font-weight:800;text-decoration:none;border-radius:9px;padding:11px 18px;font-size:14.5px;white-space:nowrap}
@media print{.stickycta,.player{display:none}}"""


def esc(text):
    return html.escape(str(text or ""), quote=True)


def _stamp(seconds):
    s = int(round(float(seconds)))
    return "%d:%02d" % (s // 60, s % 60)


def _iso_duration(seconds):
    s = int(round(float(seconds)))
    return "PT%dM%dS" % (s // 60, s % 60)


def read_script(path):
    """script.txt → [(n, text)] in chunk order."""
    text = Path(path).read_text(encoding="utf-8")
    parts = CHUNK.split(text)
    out = []
    for i in range(1, len(parts) - 1, 2):
        body = " ".join(parts[i + 1].split())
        if body:
            out.append((int(parts[i]), body))
    return out


def chapter_times(episode_id, build=None):
    """{section index: start seconds} from the aligned words.json when the build exists; else {}."""
    p = Path(build or BUILD) / episode_id / "words.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, None
    secs = data.get("sections") or []
    times = {i: float(s.get("start", 0)) for i, s in enumerate(secs) if isinstance(s, dict)}
    total = None
    if secs and isinstance(secs[-1], dict) and secs[-1].get("end"):
        total = float(secs[-1]["end"])
    words = data.get("words") or []
    if total is None and words:
        total = float(words[-1].get("t1", 0))
    return times, total


def published_episodes(ledger=None, episodes=None):
    """[(episode dict, ledger row)] for every episode folder whose YouTube title is in the ledger."""
    try:
        rows = json.loads(Path(ledger or LEDGER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rows = []
    import youtube_ledger
    gone = youtube_ledger.deleted_ids()
    rows = [r for r in rows if isinstance(r, dict) and r.get("video_id") and r.get("video_id") not in gone
            and r.get("state") not in ("rejected", "failed", "missing", "deleted")]
    out = []
    for folder in sorted(Path(episodes or EPISODES).glob("dd*")):
        meta_path, script_path = folder / "episode.json", folder / "script.txt"
        if not (meta_path.is_file() and script_path.is_file()):
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        yt_title = str((meta.get("youtube") or {}).get("title") or "").strip()
        titles = {yt_title, str(meta.get("title") or "").strip()}
        matches = [r for r in rows if str(r.get("title") or "").strip() in titles or str(r.get("topic") or "").strip() in titles]
        if not matches:
            continue
        matches.sort(key=lambda r: (r.get("privacy") == "public", str(r.get("date") or "")), reverse=True)
        meta["_folder"] = folder
        out.append((meta, matches[0]))
    return out


def page_html(meta, row, now=None, build=None):
    now = now or dt.datetime.now(LAGOS)
    eid = meta["id"]
    yt = meta.get("youtube") or {}
    video_id = row["video_id"]
    url = "%s/%s/%s.html" % (HOST, DIRNAME, eid)
    watch = "https://www.youtube.com/watch?v=%s" % video_id
    title = str(yt.get("title") or meta.get("title") or "").strip()
    desc_full = str(yt.get("description") or "").strip()
    desc = " ".join(desc_full.split("\n\n")[0].split())[:300]
    chunks = read_script(meta["_folder"] / "script.txt")
    sections = [s for s in (meta.get("sections") or []) if isinstance(s, dict)]
    times, total = chapter_times(eid, build)
    day = str(row.get("date") or now.date().isoformat())
    transcript = " ".join(body for _, body in chunks)
    tags = yt.get("tags") or []
    schema = {"@context": "https://schema.org", "@type": "VideoObject", "name": title, "description": desc,
              "thumbnailUrl": ["https://i.ytimg.com/vi/%s/maxresdefault.jpg" % video_id,
                               "https://i.ytimg.com/vi/%s/hqdefault.jpg" % video_id],
              "uploadDate": day, "embedUrl": "https://www.youtube-nocookie.com/embed/%s" % video_id,
              "url": watch, "inLanguage": "en-NG", "isFamilyFriendly": True,
              "publisher": {"@type": "Organization", "name": "DocOga", "url": HOST},
              "keywords": ", ".join(str(t) for t in tags[:12]), "transcript": transcript[:5000]}
    if total:
        schema["duration"] = _iso_duration(total)
    if times and sections:
        schema["hasPart"] = [{"@type": "Clip", "name": s.get("title", "Chapter %d" % (i + 1)),
                              "startOffset": int(times.get(i, 0)),
                              "url": "%s&t=%ds" % (watch, int(times.get(i, 0)))}
                             for i, s in enumerate(sections) if i in times]
    parts = ["<!DOCTYPE html>", '<html lang="en">', "<head>", '<meta charset="UTF-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             "<title>%s</title>" % esc(title + " | DocOga"),
             '<meta name="description" content="%s">' % esc(desc),
             '<link rel="canonical" href="%s">' % esc(url),
             '<meta property="og:title" content="%s">' % esc(title),
             '<meta property="og:description" content="%s">' % esc(desc),
             '<meta property="og:url" content="%s">' % esc(url),
             '<meta property="og:type" content="video.other">',
             '<meta property="og:image" content="https://i.ytimg.com/vi/%s/maxresdefault.jpg">' % esc(video_id),
             '<script type="application/ld+json">%s</script>' % json.dumps(schema, ensure_ascii=False),
             "<style>%s</style>" % CSS, "</head>", "<body>", '<div class="wrap">',
             '<a class="brand" href="%s/">DocOga</a>' % HOST,
             '<p class="meta">Deep-Dive %s · %s · full transcript</p>'
             % (esc(meta.get("number", "")), esc(dt.date.fromisoformat(day).strftime("%d %B %Y"))),
             "<h1>%s</h1>" % esc(title),
             '<p class="lead">%s</p>' % esc(desc),
             '<div class="player"><iframe src="https://www.youtube-nocookie.com/embed/%s" title="%s" loading="lazy" '
             'allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
             'allowfullscreen></iframe></div>' % (esc(video_id), esc(title)),
             '<p class="links"><a href="%s">Watch on YouTube →</a></p>' % esc(watch)]
    if sections:
        parts.append('<div class="box chapters"><h2>Chapters</h2><ol>')
        for i, s in enumerate(sections):
            label = esc(s.get("title", "Chapter %d" % (i + 1)))
            if i in times:
                parts.append('<li><a href="%s&t=%ds"><span class="t">%s</span>%s</a></li>'
                             % (esc(watch), int(times[i]), _stamp(times[i]), label))
            else:
                parts.append("<li>%s</li>" % label)
        parts.append("</ol></div>")
    parts.append('<div class="box"><h2>Make the document in 2 minutes — free</h2>'
                 "<p>DocOga works on your phone: answer simple questions, get a clean, standard Nigerian document you can "
                 "print, save as PDF or share on WhatsApp.</p>"
                 '<a class="cta" href="%s/?s=yt">Open the tool →</a></div>' % HOST)
    parts.append('<div class="box"><h2>Transcript</h2>')
    for i, (_, body) in enumerate(chunks):
        heading = sections[i].get("title") if i < len(sections) else "Part %d" % (i + 1)
        parts.append("<h3>%s</h3><p>%s</p>" % (esc(heading), esc(body)))
    parts.append("</div>")
    parts.append('<div class="box links"><h2>More from DocOga</h2>'
                 '<a href="%s/%s/">All Deep-Dive episodes</a>'
                 '<a href="%s/guides/">Guides</a>'
                 '<a href="https://t.me/docogadaily">Daily tips on Telegram</a>'
                 '<a href="https://www.youtube.com/channel/%s">YouTube channel</a></div>'
                 % (HOST, DIRNAME, HOST, esc(os.environ.get("YT_CHANNEL_ID") or "UCeOzX7F7sYX-WchNJyBM2qA")))
    parts.append("<footer><b>DocOga</b> — free Nigerian document tools.<br><br>General information about Nigerian law and practice, "
                 "current as at %s — not legal advice. Laws differ by state and change over time; confirm the position for your "
                 "case with a qualified Nigerian lawyer.</footer></div>" % esc(dt.date.fromisoformat(day).strftime("%B %Y")))
    parts.append('<div class="stickycta"><span><b>Oga Pass</b> — ₦2,000 · 30 days · all 10 tools · no banner</span>'
                 '<a href="%s/#pricing">Get the Pass</a></div>' % HOST)
    parts.append('<script src="/analytics-consent.js" data-track-page="true" defer></script></body></html>')
    return "\n".join(parts) + "\n"


def index_html(entries, now=None):
    now = now or dt.datetime.now(LAGOS)
    parts = ["<!DOCTYPE html>", '<html lang="en">', "<head>", '<meta charset="UTF-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             "<title>DocOga Deep-Dives — tenant and landlord documents in Nigeria, explained</title>",
             '<meta name="description" content="Every DocOga Deep-Dive with its full transcript: rent receipts, caution fees, tenancy agreements and notices in Nigeria, with the law cited.">',
             '<link rel="canonical" href="%s/%s/">' % (HOST, DIRNAME),
             "<style>%s</style>" % CSS, "</head>", "<body>", '<div class="wrap">',
             '<a class="brand" href="%s/">DocOga</a>' % HOST,
             "<h1>DocOga Deep-Dives</h1>",
             '<p class="lead">Nine-minute episodes on the documents that decide rent disputes in Nigeria — each with its full transcript and chapters.</p>',
             '<div class="box"><ul>']
    for title, href, day in entries:
        parts.append('<li><a href="%s">%s</a> <span class="meta">%s</span></li>' % (esc(href), esc(title), esc(day)))
    parts += ["</ul></div>",
              "<footer><b>DocOga</b> — free Nigerian document tools. General information, not legal advice.</footer></div>",
              '<script src="/analytics-consent.js" data-track-page="true" defer></script></body></html>']
    return "\n".join(parts) + "\n"


def _write_if_changed(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def build(site=None, ledger=None, episodes=None, build_dir=None, now=None, log=print):
    """Write the pages. Returns (urls written or refreshed, all page urls)."""
    site = Path(site) if site else SITE
    now = now or dt.datetime.now(LAGOS)
    folder = site / DIRNAME
    written, entries, urls = [], [], []
    for meta, row in published_episodes(ledger, episodes):
        url = "%s/%s/%s.html" % (HOST, DIRNAME, meta["id"])
        text = page_html(meta, row, now=now, build=build_dir)
        if _write_if_changed(folder / ("%s.html" % meta["id"]), text):
            written.append(url)
        urls.append(url)
        title = str((meta.get("youtube") or {}).get("title") or meta.get("title") or "")
        entries.append((title, url, str(row.get("date") or "")))
    if not entries:
        log("video pages: no published Deep-Dive with an episode folder yet — nothing written")
        return [], []
    entries.sort(key=lambda e: e[2], reverse=True)
    index_url = "%s/%s/" % (HOST, DIRNAME)
    if _write_if_changed(folder / "index.html", index_html(entries, now=now)):
        written.append(index_url)
    try:
        import guides_build
        added = guides_build.update_sitemap(site, [index_url] + urls, now=now)
    except Exception:  # noqa: BLE001 — the sitemap is a nicety; the pages are the point
        added = 0
    log("video pages: %d page(s) written or refreshed, %d in the index, %d sitemap entr%s added"
        % (len(written), len(urls), added, "y" if added == 1 else "ies"))
    return written, urls


def main(argv=None):
    ap = argparse.ArgumentParser(description="Transcript pages for published Deep-Dives")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--ping", action="store_true", help="IndexNow the pages written (needs INDEXNOW_KEY)")
    b.add_argument("--site", default="")
    args = ap.parse_args(argv)
    written, urls = build(site=args.site or None)
    print("VIDEO_PAGES_WRITTEN=%d" % len(written))
    print("VIDEO_PAGES_TOTAL=%d" % len(urls))
    for u in written:
        print("VIDEO_PAGE_URL=%s" % u)
    if args.ping and written:
        try:
            import guides_build
            guides_build.ping(written)
        except Exception as exc:  # noqa: BLE001
            print("::notice title=IndexNow skipped::%s" % str(exc)[:160])
    return 0


if __name__ == "__main__":
    sys.exit(main())
