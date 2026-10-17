#!/usr/bin/env python3
"""Upload closed captions for a Deep-Dive from its own word timings — the SEO the burn-in cannot give.

    python3 tools/yt_captions.py --video-id ID --words build/deepdive/dd2/words.json
    python3 tools/yt_captions.py --words build/deepdive/dd2/words.json --srt /tmp/dd2.srt   # file only

Why: YouTube indexes caption text for search (the burned-in words on the frame are pixels to
it); viewers on a phone watch muted; and a caption track is the accessibility line the brand
file promises. The Vosk alignment that already drives the picture and the cue sheet gives the
timings for free — so no second ASR pass, no quota beyond the one call.

Cost: captions.insert = 400 quota units of the 10,000/day (one episode a week). Needs the
`youtube.force-ssl` scope the uploader already holds. A failure here never fails the publish:
the video is up, the exit is 2 with the reason in plain words, and the run summary names it.

The SRT follows the Shorts/long-form readability rule from the research: at most two lines,
at most 42 characters a line, a cue 1-6 s long, broken at punctuation when it can be.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

CAPTIONS_URL = "https://www.googleapis.com/upload/youtube/v3/captions"
LINE_MAX = 42
LINES_MAX = 2
CUE_MAX_S = 6.0
CUE_MIN_S = 1.0
GAP_BREAK_S = 0.7


def _stamp(t):
    t = max(0.0, float(t))
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return "%02d:%02d:%02d,%03d" % (int(h), int(m), int(s), int(round((s - int(s)) * 1000)))


def _word_text(w):
    return str(w.get("d") or w.get("w") or "").strip()


def cues_from_words(words):
    """Word dicts ({d|w, t0, t1}) → list of (start, end, text) cues obeying the readability rule."""
    cues, cur, cur_start, cur_end, prev_end = [], [], None, None, None
    cap = LINE_MAX * LINES_MAX

    def flush():
        if cur:
            cues.append((cur_start, max(cur_end, cur_start + CUE_MIN_S), " ".join(cur)))

    for w in words:
        text = _word_text(w)
        if not text:
            continue
        t0, t1 = float(w.get("t0", 0)), float(w.get("t1", 0))
        if cur:
            too_long = len(" ".join(cur + [text])) > cap
            too_slow = (t1 - cur_start) > CUE_MAX_S
            gap = prev_end is not None and (t0 - prev_end) > GAP_BREAK_S
            ends = cur[-1].endswith((".", "?", "!")) and (t1 - cur_start) > 2.5
            if too_long or too_slow or gap or ends:
                flush()
                cur, cur_start = [], None
        if not cur:
            cur_start = t0
        cur.append(text)
        cur_end, prev_end = t1, t1
    flush()
    # no overlaps: a cue ends where the next begins when they would collide
    out = []
    for i, (a, b, text) in enumerate(cues):
        if i + 1 < len(cues):
            b = min(b, cues[i + 1][0] - 0.01) if cues[i + 1][0] > a else b
        out.append((a, max(b, a + 0.4), text))
    return out


def wrap_two_lines(text):
    if len(text) <= LINE_MAX:
        return text
    words, first = text.split(), []
    while words and len(" ".join(first + [words[0]])) <= LINE_MAX:
        first.append(words.pop(0))
    if not first:
        first, words = [words[0]], words[1:]
    return " ".join(first) + "\n" + " ".join(words)


def srt_text(words):
    cues = cues_from_words(words)
    blocks = []
    for n, (a, b, text) in enumerate(cues, 1):
        blocks.append("%d\n%s --> %s\n%s\n" % (n, _stamp(a), _stamp(b), wrap_two_lines(text)))
    return "\n".join(blocks)


def srt_from_words_file(words_path):
    data = json.loads(Path(words_path).read_text(encoding="utf-8"))
    if data.get("synthetic"):
        raise ValueError("words.json is synthetic (pace-estimated) — captions from it would drift; no upload")
    words = data.get("words") or []
    if len(words) < 20:
        raise ValueError("words.json holds %d words — too few to caption" % len(words))
    return srt_text(words), len(words)


def upload(video_id, srt, http=None, name="English", language="en"):
    """captions.insert, multipart/related (metadata JSON + the SRT body). Returns (ok, message)."""
    import yt_publish  # noqa: WPS433 — the uploader's credentials and transport
    http, _ = yt_publish.authorize(http)
    boundary = "docoga-captions-boundary"
    meta = json.dumps({"snippet": {"videoId": video_id, "language": language, "name": name, "isDraft": False}})
    body = ("--%s\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n%s\r\n"
            "--%s\r\nContent-Type: application/octet-stream\r\n\r\n" % (boundary, meta, boundary)).encode("utf-8")
    body += srt.encode("utf-8") + ("\r\n--%s--\r\n" % boundary).encode("utf-8")
    r = http.request("POST", CAPTIONS_URL, params={"part": "snippet", "uploadType": "multipart"},
                     headers={"Content-Type": "multipart/related; boundary=%s" % boundary}, data=body)
    if r.status_code in (200, 201):
        try:
            cid = r.json().get("id")
        except ValueError:
            cid = None
        return True, "captions uploaded (track %s)" % (cid or "?")
    if r.status_code == 403:
        return False, ("YouTube refused the caption track (HTTP 403). The token needs youtube.force-ssl — "
                       "one Google re-consent with the full list in docs/TOKENS.md. The video is published.")
    if r.status_code == 409:
        return False, "a caption track with this name already exists on the video (HTTP 409) — nothing to do"
    return False, "captions failed: HTTP %s — %s" % (r.status_code, (r.text or "")[:200])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Upload a Deep-Dive's captions from words.json")
    ap.add_argument("--words", required=True, help="build/deepdive/<id>/words.json")
    ap.add_argument("--video-id", default="", help="YouTube video id; omit with --srt to only write the file")
    ap.add_argument("--srt", default="", help="also write the SRT here")
    ap.add_argument("--name", default="English (DocOga)")
    args = ap.parse_args(argv)
    try:
        srt, n = srt_from_words_file(args.words)
    except (OSError, ValueError) as exc:
        print("YT_CAPTIONS=skipped")
        print("::warning title=Captions skipped::%s" % exc)
        return 2
    cues = srt.count("-->")
    print("captions: %d words → %d cues" % (n, cues))
    if args.srt:
        Path(args.srt).parent.mkdir(parents=True, exist_ok=True)
        Path(args.srt).write_text(srt, encoding="utf-8")
        print("wrote %s" % args.srt)
    if not args.video_id:
        print("YT_CAPTIONS=file-only")
        return 0
    try:
        ok, msg = upload(args.video_id, srt, name=args.name)
    except Exception as exc:  # noqa: BLE001 — never fail the publish over a caption track
        print("YT_CAPTIONS=failed")
        print("::warning title=Captions not uploaded::%s" % str(exc)[:200])
        return 2
    print("YT_CAPTIONS=%s" % ("uploaded" if ok else "failed"))
    print(("✅ " if ok else "::warning title=Captions not uploaded::") + msg)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
