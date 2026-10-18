#!/usr/bin/env python3
"""brain_visual.py — the photograph behind a card, found and treated at ₦0.

The brain's visual brief says `plate: "lagos rooftops dusk"`. This module turns
those words into a navy-duotone background the card renderer can draw type on,
or into None — the card is the contract, the plate is a wish.

Where the picture comes from (research, 16 Oct 2026):
  * Gemini's image models have no free tier (pricing page, Oct 2026) — never asked.
  * Pexels has paused issuing new API keys (pexels.com/api, Oct 2026) — not usable.
  * Unsplash's API requires hotlinking and download-tracking for API apps —
    wrong shape for a composited card.
  * **Openverse** (api.openverse.org, WordPress) searches openly licensed media
    anonymously, no key, ~20 requests/minute and ~200/day. Filtered to
    `license=cc0,pdm` the result is public-domain: no attribution obligation,
    commercial use fine. One card needs one request, cached per query.

Brand discipline (docs/BRAND_STYLE.md §6): the plate is cropped to the card,
pushed through the brand duotone ramp, darkened, grained and scrimmed so the
generator palette dies and the type stays legible; the brief may not ask for
faces or signs (tools/brain.py refuses such plates) and the search adds the same
exclusions. A result that is too small, fails to download in 12 s, or is not an
image is skipped, silently — a post is never late because of a picture.

    BRAIN_PLATES=off           never fetch (tests, air-gapped runners)
    BRAIN_PLATE_CACHE=<dir>    where fetched originals are kept (default assets/plates)
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

OPENVERSE = "https://api.openverse.org/v1/images/"
UA = "DocOgaBrain/1.0 (+https://docoga.com.ng; automated social cards)"
TIMEOUT_S = 12
MAX_BYTES = 9 * 1024 * 1024
MIN_SIDE = 900
EXCLUDE = ("face", "portrait", "selfie", "man", "woman", "people", "child", "sign", "text", "logo", "poster")
NAVY = (6, 26, 51)


def enabled():
    return os.environ.get("BRAIN_PLATES", "on").strip().lower() not in ("off", "0", "no", "false")


def cache_dir():
    return Path(os.environ.get("BRAIN_PLATE_CACHE") or (ROOT / "assets" / "plates"))


def _get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return resp.read(MAX_BYTES + 1), resp.headers.get("Content-Type", "")


def search(query, http=None):
    """Openverse CC0/PDM candidates for `query`: [{id, url, title, width, height, license}]."""
    http = http or _get
    params = {"q": query, "license": "cc0,pdm", "page_size": 20, "mature": "false",
              "size": "large,medium", "category": "photograph"}
    try:
        body, _ = http(OPENVERSE + "?" + urllib.parse.urlencode(params))
        data = json.loads(body.decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return [], "search failed: %s" % exc
    out = []
    for r in data.get("results") or []:
        title = " ".join(str(r.get("title") or "").lower().split())
        tags = " ".join(str(t.get("name", "")).lower() for t in (r.get("tags") or []) if isinstance(t, dict))
        if any(word in (title + " " + tags).split() for word in EXCLUDE):
            continue
        try:
            w, h = int(r.get("width") or 0), int(r.get("height") or 0)
        except (TypeError, ValueError):
            w = h = 0
        if min(w, h) and min(w, h) < MIN_SIDE:
            continue
        out.append({"id": r.get("id"), "url": r.get("url"), "title": r.get("title"),
                    "tags_text": tags,   # for tools/shot_match.relevant(): does it show what was asked?
                    "width": w, "height": h, "license": r.get("license"),
                    "creator": r.get("creator"), "foreign": r.get("foreign_landing_url")})
    return out, "%d candidates" % len(out)


def fetch_candidate(cand, query, http=None):
    """Download one search candidate → (PIL image, provenance) or (None, why). Cached under
    `cache_dir()` by candidate id so a beat and a card asking for the same picture pay once."""
    http = http or _get
    if not cand or not cand.get("url"):
        return None, "no url"
    cdir = cache_dir()
    key = hashlib.sha1(str(cand.get("id") or cand["url"]).encode("utf-8")).hexdigest()[:16]
    cached, side = cdir / ("%s.jpg" % key), cdir / ("%s.json" % key)
    if cached.is_file():
        try:
            return Image.open(cached).convert("RGB"), (json.loads(side.read_text()) if side.is_file() else dict(cand))
        except (OSError, ValueError):
            pass
    try:
        body, _ = http(cand["url"], accept="image/*")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, "download failed"
    if not body or len(body) > MAX_BYTES:
        return None, "empty or too large"
    try:
        img = Image.open(io.BytesIO(body))
        img.load()
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (OSError, ValueError):
        return None, "not an image"
    if min(img.size) < MIN_SIDE:
        return None, "too small"
    prov = {"query": query, **{k: v for k, v in cand.items() if k != "tags_text"}}
    try:
        cdir.mkdir(parents=True, exist_ok=True)
        img.save(cached, quality=90)
        side.write_text(json.dumps(prov, ensure_ascii=False, indent=1))
    except OSError:
        pass
    return img, prov


def fetch(query, http=None):
    """The first usable original for `query` as a PIL image, plus a provenance dict; or (None, why)."""
    if not enabled() or not query or not query.strip():
        return None, "plates off" if not enabled() else "no query"
    http = http or _get
    key = hashlib.sha1(query.strip().lower().encode("utf-8")).hexdigest()[:16]
    cdir = cache_dir()
    cached = cdir / ("%s.jpg" % key)
    side = cdir / ("%s.json" % key)
    if cached.is_file():
        try:
            return Image.open(cached).convert("RGB"), json.loads(side.read_text()) if side.is_file() else {}
        except (OSError, ValueError):
            pass
    candidates, note = search(query, http=http)
    for cand in candidates[:4]:
        if not cand.get("url"):
            continue
        try:
            body, ctype = http(cand["url"], accept="image/*")
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
        if len(body) > MAX_BYTES or not body:
            continue
        try:
            img = Image.open(io.BytesIO(body))
            img.load()
            img = ImageOps.exif_transpose(img).convert("RGB")
        except (OSError, ValueError):
            continue
        if min(img.size) < MIN_SIDE:
            continue
        try:
            cdir.mkdir(parents=True, exist_ok=True)
            img.save(cached, quality=90)
            side.write_text(json.dumps({"query": query, **cand}, ensure_ascii=False, indent=1))
        except OSError:
            pass
        return img, cand
    return None, note


def treat(img, size, darken=0.58, seed=7):
    """Crop to `size`, brand duotone, darken for type, grain and a navy scrim top and bottom.

    `darken` is how much of the photograph survives: 0.42 (17 Oct) capped the brightest pixel
    near 100/255 and the cards read as plain navy on a phone (owner, 18 Oct 2026). 0.58 keeps
    the picture plainly visible under the scrims; the Shorts pass 0.68 (tools/shorts_reel.py)."""
    import numpy as np
    import blend_image
    w, h = size
    art = blend_image.crop_aspect(img, w, h).resize((w, h), Image.LANCZOS)
    art = blend_image.duotone(art)
    a = np.asarray(art).astype(np.float32) * darken
    art = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    art = blend_image.photo_grain(art, sigma=4.0, seed=seed)
    art = blend_image.scrim(art, NAVY, 0, int(h * 0.5), 170, 90)
    art = blend_image.scrim(art, NAVY, int(h * 0.5), h, 90, 225)
    return art


def background_for(query, size, http=None):
    """One call for the renderer: a treated background or None (never raises)."""
    try:
        img, _ = fetch(query, http=http)
        if img is None:
            return None
        return treat(img, size)
    except Exception:  # a picture must never cost the post
        return None
