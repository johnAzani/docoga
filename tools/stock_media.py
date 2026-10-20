#!/usr/bin/env python3
"""stock_media.py — a free VIDEO CLIP behind every spoken sentence; a photograph where no clip exists.

Owner, 20 Oct 2026 (second brief of the day): "free video clip per spoken sentence; where there is
no video clip use image per spoken sentence, not per scene; try as many free platforms as possible;
make sure it matches what is being said and it has the Nigerian feel; quality beyond After Effects."

This module is the one place a sentence becomes footage. shot_match.py still decides WHAT to look
for (its glossary turns "the landlord must give you a receipt" into "paper receipt"); this module
decides WHERE to look, in what order, and what "matches" and "Nigerian" mean in numbers.

The doors — every one ₦0, every one optional, every miss silent:

  video  pixabay   PIXABAY_API_KEY     100 req/min · Content License, no attribution · film clips
  video  pexels    PEXELS_API_KEY      200 req/h · Pexels License · NEW KEYS PAUSED since 30 Sep 2026
                                       (pexels.com/api) — the door is built and waits for the key
  video  commons   (no key)            Wikimedia Commons API · public-domain / CC0 only · webm/ogv
  photo  pixabay   PIXABAY_API_KEY
  photo  pexels    PEXELS_API_KEY
  photo  flickr    FLICKR_API_KEY      CC0 / PDM / no-known-restrictions · GEOFENCED to Nigeria (bbox)
  photo  unsplash  UNSPLASH_ACCESS_KEY 50 req/h demo · Unsplash License
  photo  commons   (no key)            public-domain / CC0 only
  photo  openverse (no key)            CC0 / PDM, via shot_match.photo_for (the 17 Oct door)

Order of asking, per sentence (so the Nigerian clip wins when one exists and the API budget is not
burnt when it does not): the subject + "nigeria" at every VIDEO door → the plain subject at every
video door → the same two queries at every PHOTO door. The first relevant, unused hit is taken.
Search results are cached per (door, query) for the run (Pixabay asks for 24 h caching; a Short
re-asks the same subject three or four times).

"Matches what is being said": a candidate must share a content word (stemmed) with the query in
its title / tags / slug — shot_match.relevant, unchanged. "Nigerian feel": +3 for Nigeria, Lagos,
Abuja, Naija, danfo …; +2 for Africa/African and West-African neighbours; Flickr results inside
the Nigeria bounding box carry the bonus by construction. Portrait and ≥1080-px-tall media score
higher (the Short is 1080×1920); a clip at least as long as the sentence scores higher still.

No close faces: portrait / selfie / headshot / face / close-up are excluded (a street, a market, a
hand with a receipt are fine — that is what b-roll is). shot_match's photo door keeps its stricter
no-people rule for cards.

A clip is BAKED once by ffmpeg into brand-treated frames (bake_clip): cover-scale to 1080×1920,
grey, living film grain, the brand duotone + darken as one 1-D LUT, the navy scrims — the same
look as brain_visual.treat on a photograph, so a clip and a photograph sit in one Short without
a seam. MotionStudio then runs its camera over the frames exactly as it does over a photograph.

    DOCOGA_SHOTS=on    the lanes set this; unset = nothing touches the network (tests, laptops)
    STOCK_MEDIA=off    kill switch for this module only (photographs via shot_match still work)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

UA = "DocOga/1.0 (+https://docoga.com.ng; social@docoga.com.ng) stock_media"
TIMEOUT_S = 20
CLIP_MAX_BYTES = 90 * 1024 * 1024      # a 1080p clip of 10–20 s is 5–40 MB
PHOTO_MAX_BYTES = 14 * 1024 * 1024
FPS = 30
W, H = 1080, 1920

NIGERIA_BBOX = "2.67,4.27,14.68,13.89"   # minlon,minlat,maxlon,maxlat — Flickr geofence
NIGERIA_WORDS = ("nigeria", "nigerian", "lagos", "abuja", "naija", "yoruba", "igbo", "hausa", "kano",
                 "ibadan", "enugu", "harcourt", "calabar", "benin", "kaduna", "jos", "danfo", "okada",
                 "keke", "ankara", "agbada", "naira", "lekki", "ikeja", "yaba", "surulere", "balogun")
AFRICA_WORDS = ("africa", "african", "ghana", "accra", "kenya", "nairobi", "senegal", "dakar", "benin",
                "togo", "lome", "cameroon", "douala", "west")
EXCLUDE = ("portrait", "selfie", "headshot", "face", "faces", "closeup", "close-up", "close", "model", "models",
           "logo", "poster", "sign", "text", "nude", "bikini")

PACE = {"pixabay": 0.7, "pexels": 1.0, "commons": 1.0, "flickr": 1.0, "unsplash": 1.5}
_last = {}
_CACHE = {}


# ───────────────────────── gates and keys ─────────────────────────
def enabled():
    import shot_match
    if os.environ.get("STOCK_MEDIA", "on").strip().lower() in ("off", "0", "no", "false"):
        return False
    return shot_match.enabled()


def keys():
    g = lambda k: (os.environ.get(k) or "").strip()
    return {"pixabay": g("PIXABAY_API_KEY"), "pexels": g("PEXELS_API_KEY"),
            "flickr": g("FLICKR_API_KEY"), "unsplash": g("UNSPLASH_ACCESS_KEY")}


def doors(kind):
    """The doors to try for `kind` ('video' | 'photo'), in order, given the keys present."""
    k = keys()
    if kind == "video":
        return [d for d, ok in (("pixabay", k["pixabay"]), ("pexels", k["pexels"]), ("commons", True)) if ok]
    return [d for d, ok in (("pixabay", k["pixabay"]), ("pexels", k["pexels"]), ("flickr", k["flickr"]),
                            ("unsplash", k["unsplash"]), ("commons", True)) if ok]


def door_status():
    """The machine line's truth: which doors are open this run."""
    k = keys()
    return ",".join("%s:%s" % (d, "on" if k.get(d, True) else "nokey")
                    for d in ("pixabay", "pexels", "flickr", "unsplash", "commons", "openverse"))


# ───────────────────────── words ─────────────────────────
def nigeria_bonus(text):
    words = set(re.findall(r"[a-z]+", str(text or "").lower()))
    if words & set(NIGERIA_WORDS):
        return 3
    if words & set(AFRICA_WORDS):
        return 2
    return 0


def excluded(text):
    words = set(re.findall(r"[a-z\-]+", str(text or "").lower()))
    return bool(words & set(EXCLUDE))


def queries_for(text, hint=None):
    """[(query, nigerian)] in asking order: the first two subjects of shot_match's chain, each
    first with 'nigeria' and then plain; the chain's own Nigerian setting last. ≤ 5, deduplicated."""
    import shot_match
    chain = shot_match.query_chain(text, hint)
    out = []
    for q in chain[:2]:
        if "nigeria" not in q and "lagos" not in q:
            out.append((q + " nigeria", True))
            out.append((q, False))
        else:
            out.append((q, True))
    if (chain[-1], True) not in out and (chain[-1], False) not in out:
        out.append((chain[-1], True))
    seen, uniq = set(), []
    for q, n in out:
        if q not in seen:
            seen.add(q)
            uniq.append((q, n))
    return uniq[:5]


def relevant(cand, query):
    import shot_match
    return shot_match.relevant(cand, query)


def score(cand, query, need_s=0.0):
    """Higher is better. Relevance words ×2, the Nigerian bonus, portrait, ≥1080 tall, clip long
    enough for the sentence (video), a short clip loses a point."""
    import shot_match
    have = {shot_match._stem(w) for w in shot_match._words(" ".join([str(cand.get("title") or ""),
                                                                    str(cand.get("tags_text") or "")]))}
    want = {shot_match._stem(w) for w in shot_match._words(query)}
    s = 2 * len(have & want)
    s += cand.get("nigeria", 0) or nigeria_bonus(" ".join([str(cand.get("title") or ""), str(cand.get("tags_text") or ""),
                                                           str(cand.get("page") or "")]))
    w, h = int(cand.get("width") or 0), int(cand.get("height") or 0)
    if h > w:
        s += 1
    if h >= 1080:
        s += 1
    if cand.get("kind") == "video":
        d = float(cand.get("duration") or 0)
        if need_s and d >= need_s:
            s += 1
        elif need_s and d and d < 0.6 * need_s:
            s -= 1
    return s


def choose(cands, query, need_s=0.0, used=()):
    kept = [c for c in cands if c.get("url") and c.get("id") not in used and relevant(c, query)
            and not excluded(" ".join([str(c.get("title") or ""), str(c.get("tags_text") or "")]))]
    if not kept:
        return None
    return max(kept, key=lambda c: (score(c, query, need_s), -len(str(c.get("title") or ""))))


# ───────────────────────── http ─────────────────────────
def _http(url, headers=None, accept="application/json", max_bytes=PHOTO_MAX_BYTES):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return resp.read(max_bytes + 1), resp.headers.get("Content-Type", "")


def _json(url, http, headers=None):
    body, _ = http(url, headers=headers)
    return json.loads(body.decode("utf-8", "replace"))


def _pace(door, sleeper=None):
    wait = PACE.get(door, 1.0) - (time.monotonic() - _last.get(door, 0.0))
    if wait > 0:
        (sleeper or time.sleep)(wait)
    _last[door] = time.monotonic()


# ───────────────────────── the doors ─────────────────────────
def _slug_words(url):
    """Pexels results carry no tags; the page slug ('/video/lagos-street-market-12345/') does."""
    m = re.search(r"/(?:video|photo)/([a-z0-9\-]+?)-?\d*/?$", str(url or ""))
    return (m.group(1).replace("-", " ") if m else "")


def search_pixabay(query, kind, http, key):
    base = "https://pixabay.com/api/videos/" if kind == "video" else "https://pixabay.com/api/"
    params = {"key": key, "q": query[:100], "per_page": 25, "safesearch": "true", "lang": "en"}
    if kind == "video":
        params.update(video_type="film")
    else:
        params.update(image_type="photo", min_width=1080, orientation="vertical")
    data = _json(base + "?" + urllib.parse.urlencode(params), http)
    out = []
    for h in data.get("hits") or []:
        tags = str(h.get("tags") or "").lower()
        if kind == "video":
            files = h.get("videos") or {}
            pick = None
            for name in ("large", "medium", "small"):
                f = files.get(name) or {}
                if f.get("url") and int(f.get("height") or 0) >= 720 and int(f.get("size") or 0) <= CLIP_MAX_BYTES:
                    pick = f
                    if int(f.get("height") or 0) >= 1080 and (int(f.get("size") or 0) <= 60 * 1024 * 1024):
                        break
            if not pick:
                continue
            out.append({"door": "pixabay", "kind": "video", "id": "pixabay:%s" % h.get("id"), "url": pick["url"],
                        "width": pick.get("width"), "height": pick.get("height"), "duration": h.get("duration"),
                        "title": tags, "tags_text": tags, "page": h.get("pageURL"), "license": "pixabay",
                        "credit": h.get("user")})
        else:
            url = h.get("largeImageURL") or h.get("webformatURL")
            out.append({"door": "pixabay", "kind": "photo", "id": "pixabay:%s" % h.get("id"), "url": url,
                        "width": h.get("imageWidth"), "height": h.get("imageHeight"), "title": tags,
                        "tags_text": tags, "page": h.get("pageURL"), "license": "pixabay", "credit": h.get("user")})
    return out


def search_pexels(query, kind, http, key):
    hdr = {"Authorization": key}
    if kind == "video":
        url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
            {"query": query, "orientation": "portrait", "size": "medium", "per_page": 20})
        data = _json(url, http, headers=hdr)
        out = []
        for v in data.get("videos") or []:
            files = [f for f in (v.get("video_files") or []) if f.get("link") and (f.get("height") or 0) >= 1080
                     and str(f.get("file_type") or "").endswith("mp4")]
            files.sort(key=lambda f: (int(f.get("height") or 0), int(f.get("size") or 0)))
            if not files:
                continue
            f = files[0]
            words = _slug_words(v.get("url"))
            out.append({"door": "pexels", "kind": "video", "id": "pexels:%s" % v.get("id"), "url": f["link"],
                        "width": f.get("width"), "height": f.get("height"), "duration": v.get("duration"),
                        "title": words, "tags_text": words, "page": v.get("url"), "license": "pexels",
                        "credit": (v.get("user") or {}).get("name")})
        return out
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": query, "orientation": "portrait", "size": "medium", "per_page": 20})
    data = _json(url, http, headers=hdr)
    out = []
    for p in data.get("photos") or []:
        src = p.get("src") or {}
        words = " ".join([_slug_words(p.get("url")), str(p.get("alt") or "").lower()])
        out.append({"door": "pexels", "kind": "photo", "id": "pexels:%s" % p.get("id"),
                    "url": src.get("large2x") or src.get("large") or src.get("original"),
                    "width": p.get("width"), "height": p.get("height"), "title": words, "tags_text": words,
                    "page": p.get("url"), "license": "pexels", "credit": p.get("photographer")})
    return out


COMMONS_FREE = ("public domain", "pd", "cc0", "cc-zero", "no restrictions")


def search_commons(query, kind, http):
    srch = ("filetype:video " if kind == "video" else "filetype:bitmap ") + query
    params = {"action": "query", "generator": "search", "gsrsearch": srch, "gsrnamespace": 6, "gsrlimit": 20,
              "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 2048,
              "format": "json", "formatversion": 2}
    data = _json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params), http)
    out = []
    for pg in ((data.get("query") or {}).get("pages") or []):
        ii = (pg.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata") or {}
        lic = str((meta.get("LicenseShortName") or {}).get("value") or "").lower()
        if not any(f in lic for f in COMMONS_FREE):
            continue
        title = re.sub(r"^file:|\.[a-z0-9]+$", "", str(pg.get("title") or ""), flags=re.I).replace("_", " ").lower()
        cats = str((meta.get("Categories") or {}).get("value") or "").lower().replace("|", " ")
        desc = re.sub(r"<[^>]+>", " ", str((meta.get("ImageDescription") or {}).get("value") or "")).lower()[:300]
        mime = str(ii.get("mime") or "")
        if kind == "video" and not mime.startswith("video/"):
            continue
        if kind == "photo" and not mime.startswith("image/"):
            continue
        url = ii.get("url") if kind == "video" else (ii.get("thumburl") or ii.get("url"))
        out.append({"door": "commons", "kind": kind, "id": "commons:%s" % pg.get("pageid"), "url": url,
                    "width": ii.get("width"), "height": ii.get("height"),
                    "duration": ii.get("duration"), "title": title, "tags_text": cats + " " + desc,
                    "page": ii.get("descriptionurl"), "license": lic,
                    "credit": re.sub(r"<[^>]+>", "", str((meta.get("Artist") or {}).get("value") or ""))[:80]})
    return out


def search_flickr(query, http, key):
    params = {"method": "flickr.photos.search", "api_key": key, "text": query, "license": "7,9,10",
              "bbox": NIGERIA_BBOX, "content_type": 1, "media": "photos", "safe_search": 1, "sort": "relevance",
              "extras": "url_l,url_c,tags,o_dims", "per_page": 25, "format": "json", "nojsoncallback": 1}
    data = _json("https://api.flickr.com/services/rest/?" + urllib.parse.urlencode(params), http)
    out = []
    for p in ((data.get("photos") or {}).get("photo") or []):
        url = p.get("url_l") or p.get("url_c")
        if not url:
            continue
        w, h = int(p.get("width_l") or p.get("width_c") or 0), int(p.get("height_l") or p.get("height_c") or 0)
        title = str(p.get("title") or "").lower()
        out.append({"door": "flickr", "kind": "photo", "id": "flickr:%s" % p.get("id"), "url": url,
                    "width": w, "height": h, "title": title, "tags_text": str(p.get("tags") or "").lower(),
                    "page": "https://www.flickr.com/photos/%s/%s" % (p.get("owner"), p.get("id")),
                    "license": "flickr:%s" % p.get("license"), "credit": p.get("owner"), "nigeria": 3})
    return out


def search_unsplash(query, http, key):
    url = "https://api.unsplash.com/search/photos?" + urllib.parse.urlencode(
        {"query": query, "orientation": "portrait", "per_page": 20, "content_filter": "high"})
    data = _json(url, http, headers={"Authorization": "Client-ID " + key, "Accept-Version": "v1"})
    out = []
    for p in data.get("results") or []:
        words = " ".join([str(p.get("alt_description") or ""), str(p.get("description") or ""),
                          " ".join(str(t.get("title") or "") for t in (p.get("tags") or []) if isinstance(t, dict))]).lower()
        urls = p.get("urls") or {}
        out.append({"door": "unsplash", "kind": "photo", "id": "unsplash:%s" % p.get("id"),
                    "url": (urls.get("raw") + "&w=1600&q=85&fm=jpg") if urls.get("raw") else urls.get("regular"),
                    "width": p.get("width"), "height": p.get("height"), "title": words, "tags_text": words,
                    "page": (p.get("links") or {}).get("html"), "license": "unsplash",
                    "credit": (p.get("user") or {}).get("name"),
                    "download_location": (p.get("links") or {}).get("download_location")})
    return out


def search(door, query, kind, http=None, sleeper=None):
    """Candidates from one door, cached per (door, query, kind) for the run. Never raises."""
    http = http or _http
    ck = (door, query, kind)
    if ck in _CACHE:
        return _CACHE[ck]
    k = keys()
    try:
        _pace(door, sleeper)
        if door == "pixabay":
            out = search_pixabay(query, kind, http, k["pixabay"])
        elif door == "pexels":
            out = search_pexels(query, kind, http, k["pexels"])
        elif door == "commons":
            out = search_commons(query, kind, http)
        elif door == "flickr":
            out = search_flickr(query, http, k["flickr"]) if kind == "photo" else []
        elif door == "unsplash":
            out = search_unsplash(query, http, k["unsplash"]) if kind == "photo" else []
        else:
            out = []
    except Exception as exc:  # a door that is down is a door that is closed
        print("  · %s %s search failed: %s" % (door, kind, str(exc)[:80]))
        out = []
    _CACHE[ck] = out
    return out


# ───────────────────────── download ─────────────────────────
def cache_dir():
    return Path(os.environ.get("STOCK_MEDIA_CACHE") or "/tmp/docoga_stock")


def download(cand, http=None):
    """The candidate's file on disk (cached by id) or None."""
    http = http or _http
    cdir = cache_dir()
    cdir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(str(cand.get("id") or cand["url"]).encode("utf-8")).hexdigest()[:16]
    ext = ".mp4" if cand.get("kind") == "video" else ".jpg"
    if cand.get("kind") == "video":
        low = str(cand["url"]).lower().split("?")[0]
        for e in (".webm", ".ogv", ".ogg", ".mov"):
            if low.endswith(e):
                ext = e
    dest = cdir / (key + ext)
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    try:
        body, _ = http(cand["url"], accept="*/*",
                       max_bytes=CLIP_MAX_BYTES if cand.get("kind") == "video" else PHOTO_MAX_BYTES)
    except Exception as exc:
        print("  · download failed (%s): %s" % (cand.get("id"), str(exc)[:80]))
        return None
    limit = CLIP_MAX_BYTES if cand.get("kind") == "video" else PHOTO_MAX_BYTES
    if not body or len(body) > limit:
        return None
    dest.write_bytes(body)
    if cand.get("door") == "unsplash" and cand.get("download_location"):
        try:   # Unsplash API guideline: a download must be reported
            http(cand["download_location"] + "?client_id=" + keys()["unsplash"], max_bytes=4096)
        except Exception:
            pass
    side = cdir / (key + ".json")
    try:
        side.write_text(json.dumps({k: v for k, v in cand.items() if k != "tags_text"}, ensure_ascii=False, indent=1))
    except OSError:
        pass
    return dest


# ───────────────────────── the one call ─────────────────────────
def media_for(text, hint=None, need_s=4.0, used=None, kinds=("video", "photo"), http=None, sleeper=None):
    """(candidate with 'path', note) for what is being said — a clip when any door has one, else a
    photograph — or (None, why). `used` is the set of candidate ids already in this Short; the
    chosen id is added. Never raises."""
    used = used if used is not None else set()
    if not enabled():
        return None, "stock off"
    try:
        qs = queries_for(text, hint)
        for kind in kinds:
            for query, _nig in qs:
                for door in doors(kind):
                    cands = search(door, query, kind, http=http, sleeper=sleeper)
                    cand = choose(cands, query, need_s, used)
                    if cand is None:
                        continue
                    path = download(cand, http=http)
                    if path is None:
                        used.add(cand["id"])      # do not re-download a dead link on the next sentence
                        continue
                    used.add(cand["id"])
                    out = dict(cand)
                    out.update(path=str(path), query=query)
                    return out, "%s %s" % (door, kind)
        return None, "no door had %s" % "/".join(kinds)
    except Exception as exc:
        return None, "error: %s" % exc


# ───────────────────────── bake: clip → brand frames ─────────────────────────
def _ffmpeg():
    import motionstudio
    return motionstudio.find_ffmpeg()


def duotone_lut(lo=0, hi=255, darken=0.68):
    """256 RGB triples (0–1 floats): grey level → brand ramp (blend_image.STOPS) × darken, after
    the same 1 %-cutoff stretch ImageOps.autocontrast gives a photograph (lo/hi from the clip's
    first frame)."""
    import blend_image
    stops = blend_image.STOPS
    span = max(1, hi - lo)
    out = []
    for i in range(256):
        t = min(1.0, max(0.0, (i - lo) / span))
        rgb = stops[-1][1]
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                rgb = tuple(c0[ch] + (c1[ch] - c0[ch]) * f for ch in range(3))
                break
        out.append(tuple(min(1.0, max(0.0, v * darken / 255.0)) for v in rgb))
    return out


def write_cube(path, lut):
    lines = ['TITLE "docoga duotone"', "LUT_1D_SIZE 256", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"]
    lines += ["%.6f %.6f %.6f" % rgb for rgb in lut]
    Path(path).write_text("\n".join(lines) + "\n")


def write_scrim(path):
    """The navy scrims brain_visual.treat lays over a photograph (170→90 over the top half,
    90→225 over the bottom), as one RGBA PNG for ffmpeg's overlay."""
    import numpy as np
    from PIL import Image
    import brain_visual
    alpha = np.zeros((H, W), np.float32)
    half = H // 2
    alpha[:half] = np.linspace(170, 90, half)[:, None]
    alpha[half:] = np.linspace(90, 225, H - half)[:, None]
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = brain_visual.NAVY
    rgba[..., 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(path)


def first_frame_levels(clip, ffmpeg, start=0.0):
    """(lo, hi) grey levels at the 1 % / 99 % points of the clip's first used frame — the stretch a
    photograph gets from autocontrast(cutoff=1), fixed for the whole clip so it cannot flicker."""
    import numpy as np
    from PIL import Image
    import io
    cmd = [ffmpeg, "-v", "error", "-ss", "%.3f" % start, "-i", str(clip), "-frames:v", "1",
           "-vf", "scale=240:-2,format=gray", "-f", "image2pipe", "-vcodec", "png", "-"]
    try:
        png = subprocess.run(cmd, capture_output=True, timeout=60).stdout
        a = np.asarray(Image.open(io.BytesIO(png)).convert("L")).ravel()
        lo, hi = int(np.percentile(a, 1)), int(np.percentile(a, 99))
        if hi - lo < 16:
            return 0, 255
        return lo, hi
    except Exception:
        return 0, 255


def bake_clip(clip, need_s, out_dir, darken=0.68, duration=None, ffmpeg=None, timeout=240):
    """Turn a downloaded clip into brand-treated 1080×1920 JPEG frames at 30 fps under `out_dir`
    for `need_s` seconds (held on its last frame if the clip is shorter — the camera keeps moving).
    Returns {'frames': dir, 'n': count} or None. Never raises."""
    try:
        ffmpeg = ffmpeg or _ffmpeg()
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in out_dir.glob("f_*.jpg"):
            old.unlink()
        start = 0.0
        if duration and float(duration) > need_s + 1.0:
            start = min(0.15 * float(duration), float(duration) - need_s - 0.6)   # past the handheld settle / fade-in
        lo, hi = first_frame_levels(clip, ffmpeg, start)
        cube, scrim = out_dir / "duotone.cube", out_dir / "scrim.png"
        write_cube(cube, duotone_lut(lo, hi, darken))
        write_scrim(scrim)
        n_frames = int(round(need_s * FPS))
        vf = ("[0:v]fps=%d,scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
              "format=gray,tpad=stop_mode=clone:stop_duration=%.2f,noise=alls=9:allf=t+u,format=rgb24,lut1d=file=%s[v];"
              "[v][1:v]overlay=format=auto,format=yuvj444p"
              % (FPS, W + 2, H + 4, W, H, need_s + 1.0, str(cube).replace(":", "\\:")))
        # -frames:v, not trim: with the image2 muxer's constant-rate sync, trim after tpad drops
        # a frame in six (126 of 150 measured, ffmpeg 7.0); counting output frames does not.
        cmd = [ffmpeg, "-y", "-v", "error", "-ss", "%.3f" % start, "-i", str(clip), "-i", str(scrim),
               "-filter_complex", vf, "-fps_mode", "passthrough", "-frames:v", str(n_frames), "-q:v", "2",
               str(out_dir / "f_%04d.jpg")]
        subprocess.run(cmd, capture_output=True, timeout=timeout, check=True)
        n = len(list(out_dir.glob("f_*.jpg")))
        if n < max(2, int(0.9 * n_frames)):
            print("  · bake short: %d of %d frames" % (n, n_frames))
            return None
        return {"frames": str(out_dir), "n": n}
    except subprocess.CalledProcessError as exc:
        print("  · bake failed: %s" % (exc.stderr or b"")[-200:].decode("utf-8", "replace").strip())
        return None
    except Exception as exc:
        print("  · bake failed: %s" % str(exc)[:120])
        return None


if __name__ == "__main__":
    for line in sys.argv[1:] or ["If you paid by transfer, screenshot the confirmation."]:
        print("%-60s → %s" % (line[:60], " | ".join(q for q, _ in queries_for(line))))
    print("doors:", door_status())
