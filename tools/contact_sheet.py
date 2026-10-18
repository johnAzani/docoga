#!/usr/bin/env python3
"""contact_sheet.py — one small JPEG that shows what a rendered video looks like.

Run artifacts and run logs are not reachable from everywhere the owner's helpers work; a
~150 KB contact sheet committed to the `review` branch is (`tools/review_push.sh`). Frame 0
(the cover every platform shows), then frames spread across the video, each labelled with its
time and the mean brightness of its background — the numbers that tell "navy" from "photo"
without a screen (a navy frame reads ≈ 20; a photographed one ≥ 35).

    python3 tools/contact_sheet.py --video short.mp4 --out review/short.jpg [--cover short.cover.jpg] [--frames 8]
Prints `SHEET=<path>` and `SHEET_BRIGHTNESS=<frame0>,<f1>,…`. Needs ffmpeg (FFMPEG_BIN or PATH).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

TILE_W, TILE_H, GAP, LABEL = 216, 384, 8, 26


def find_ffmpeg():
    for cand in (os.environ.get("FFMPEG_BIN", ""), shutil.which("ffmpeg")):
        if cand and os.path.isfile(cand):
            return cand
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def duration_of(ff, video):
    r = subprocess.run([ff, "-i", str(video)], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            hms = line.split()[1].rstrip(",")
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def grab(ff, video, t, out):
    cmd = [ff, "-y", "-loglevel", "error", "-ss", "%.3f" % t, "-i", str(video), "-frames:v", "1", "-q:v", "3", str(out)]
    return subprocess.run(cmd, capture_output=True).returncode == 0 and Path(out).is_file()


def brightness(im):
    """Mean luminance of the picture's margins (left/right 12 %), where no type sits — the
    background itself. Navy ≈ 20; a treated photograph ≥ 35."""
    from PIL import ImageStat
    w, h = im.size
    g = im.convert("L")
    left = g.crop((0, 0, max(1, w // 8), h))
    right = g.crop((w - max(1, w // 8), 0, w, h))
    return round((ImageStat.Stat(left).mean[0] + ImageStat.Stat(right).mean[0]) / 2.0, 1)


def build(video, out, cover=None, frames=8, ff=None):
    from PIL import Image, ImageDraw
    ff = ff or find_ffmpeg()
    if not ff:
        raise SystemExit("ffmpeg not found")
    video = Path(video)
    dur = duration_of(ff, video)
    times = [0.0] + [dur * (i + 0.5) / max(1, frames - 1) for i in range(frames - 1)] if dur else [0.0]
    tiles, brights = [], []
    with tempfile.TemporaryDirectory() as td:
        for i, t in enumerate(times):
            fp = Path(td) / ("f%02d.jpg" % i)
            if grab(ff, video, min(t, max(0.0, dur - 0.05)), fp):
                im = Image.open(fp).convert("RGB")
                brights.append(brightness(im))
                tiles.append(("%.1fs" % t if i else "frame 0 (cover)", im.resize((TILE_W, TILE_H), Image.LANCZOS)))
        if cover and Path(cover).is_file():
            im = Image.open(cover).convert("RGB")
            tiles.insert(0, ("cover.jpg", im.resize((TILE_W, TILE_H), Image.LANCZOS)))
    if not tiles:
        raise SystemExit("no frames could be read from %s" % video)
    cols = min(5, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (TILE_W + GAP) + GAP, rows * (TILE_H + LABEL + GAP) + GAP), (240, 240, 240))
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(tiles):
        x = GAP + (i % cols) * (TILE_W + GAP)
        y = GAP + (i // cols) * (TILE_H + LABEL + GAP)
        sheet.paste(im, (x, y))
        d.text((x + 4, y + TILE_H + 6), label, fill=(20, 20, 20))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, "JPEG", quality=72, optimize=True)
    return out, brights, dur


def main(argv=None):
    ap = argparse.ArgumentParser(description="a labelled contact sheet of a rendered video")
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cover", default="")
    ap.add_argument("--frames", type=int, default=8)
    a = ap.parse_args(argv)
    out, brights, dur = build(a.video, a.out, cover=a.cover or None, frames=a.frames)
    print("sheet %s (%d KB) — %.1fs video, %d frames" % (out, out.stat().st_size // 1024, dur, len(brights)))
    print("SHEET=%s" % out)
    print("SHEET_BRIGHTNESS=%s" % ",".join(str(b) for b in brights))
    photo_like = sum(1 for b in brights if b >= 35)
    print("SHEET_PHOTO_FRAMES=%d/%d" % (photo_like, len(brights)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
