#!/usr/bin/env python3
"""DocOga Live — the channel's always-on stream, at ₦0.

Owner, 26 Oct 2026, 4:20am: "go — I want live stream to always be on for life, pulling in
watch time, subscribers etc." The Studio screenshot that morning showed the Live Control
Room open with a Schedule Stream button and no enable-wait banner: the channel can go
live now, through an encoder, with no subscriber minimum (the 50-subscriber rule is the
phone app only — support.google.com/youtube/answer/2907883).

What this is
------------
One broadcast that stays live. A GitHub Actions runner pushes the channel's own finished
episodes — every Deep-Dive master banked on its `deepdive-<ep>` release and every weekday
Short the Shorts lane banks on the `live-library` release — over RTMPS to YouTube's ingest,
on a loop, with ffmpeg copying the already-encoded bytes (no re-encode while streaming, so a
2-vCPU runner does it with room to spare). A job may run 6 hours; this one streams for
LIVE_MINUTES (5h45m) and queues its successor the moment it starts, so the hand-over is the
concurrency group letting the next run in as this one ends: a gap of about a minute every
six hours, inside a broadcast that stays live because auto-stop is off. YouTube does not
archive a stream longer than 12 hours — fine: this is a window, not a VOD. The watch time,
the live shelf, the LIVE badge in search and the subscribers it pulls are the point.

Honesty, on the record: the title and description say the loop is pre-recorded. Nothing
here claims to be a person talking in real time; the episodes are the episodes.

What it never does: touch the Shorts or Deep-Dive uploads, use a non-Google voice, or
spend money. Kill switch: repository variable `DOCOGA_LIVE=off` ends the broadcast on the
next run and stops queuing successors.

CLI (the workflow drives these; each reads YT_* secrets from the environment):
    python3 tools/yt_live.py plan --assets assets.json --out plan.json      # which clips, in what order
    python3 tools/yt_live.py build --plan plan.json --lib DIR --reel reel.mp4 # normalise + concat
    python3 tools/yt_live.py ensure --out live.json                           # broadcast + stream key
    python3 tools/yt_live.py stream --reel reel.mp4 --ingest live.json --minutes 345
    python3 tools/yt_live.py off                                              # end every live broadcast
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import yt_publish  # noqa: E402  (auth, Http, Problem, classify)

API = "https://www.googleapis.com/youtube/v3"
RELEASE_TAG = "live-library"          # banked Shorts + normalised clips + the manifest
LEDGER = ROOT / "logs" / "youtube_live.json"

LIVE_MINUTES = 345                    # 5h45m of a 6-hour job; the successor is already queued
CANVAS = (1920, 1080)                 # one landscape canvas; Shorts stand on the brand navy
FPS = 30
GOP = 60                              # a keyframe every 2 s — YouTube ingest asks for ≤ 4 s
VIDEO_KBPS = 4500
AUDIO_KBPS = 128
STREAM_TITLE = "DocOga Live key (reusable)"

TITLE = "DocOga Live 24/7 — Nigerian rent & tenancy law, explained (pre-recorded loop)"
DESCRIPTION = (
    "Pre-recorded DocOga episodes playing on a loop, all day, every day: how to pay rent "
    "safely, what a rent receipt must carry, agent fees, caution fees, notice to quit, "
    "repairs and moving in — the law as written, state by state, in plain Nigerian English.\n\n"
    "This is not a live presenter. Every new Short and Deep-Dive joins the loop the day it "
    "publishes; the full episodes are on the channel in HD.\n\n"
    "Prove your rent was paid, in 60 seconds: https://docoga.com.ng\n\n"
    "#RentReceiptLaw #NigeriaRent #TenantRights #Lagos #Abuja"
)
assert len(TITLE) <= 100


# ----------------------------------------------------------------- the library

def _is_episode(name):
    return name.endswith("-episode.mp4")


def _is_short(name):
    return name.startswith("short-") and name.endswith(".mp4")


LONGFORM_LEDGER = ROOT / "logs" / "youtube_longform.json"
_EPISODE_NO = re.compile(r"Deep-Dive\s+(\d+)", re.I)


def hidden_episodes(rows, now=None):
    """Episodes whose Saturday has not come: a Deep-Dive scheduled public at a future
    `publish_at` (logs/youtube_longform.json) stays out of the loop until that instant — the
    live must never spoil a premiere. Rows name the episode in the title ("… (Deep-Dive 4)")."""
    now = now or datetime.now(timezone.utc)
    hidden = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        when = row.get("publish_at") or ""
        m = _EPISODE_NO.search(row.get("title") or "")
        if not (when and m):
            continue
        try:
            at = datetime.strptime(when[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if at > now:
            hidden.add("dd%s" % m.group(1))
    return hidden


def plan(assets, hidden=()):
    """The loop's running order from the release assets we can download.

    `assets` is a list of {"release": tag, "name": asset, "size": bytes}. Deep-Dive masters
    (`<ep>-episode.mp4` on `deepdive-*`) and banked Shorts (`short-<date>.mp4` on
    `live-library`) are the only clips; normalised copies and manifests are not clips.
    Order: newest Short first (the channel's freshest hook opens every loop), then Shorts
    and Deep-Dives interleaved so a viewer landing anywhere meets a Short within minutes —
    Shorts are the proven retention shape; a Deep-Dive is the depth that earns the subscribe.
    Each clip carries a `key` (name + size) that names its normalised copy, so a re-banked
    master is normalised again and an untouched one never is.
    """
    shorts, episodes = [], []
    for a in assets or []:
        name, tag = a.get("name", ""), a.get("release", "")
        if tag == RELEASE_TAG and _is_short(name):
            shorts.append(a)
        elif tag.startswith("deepdive-") and _is_episode(name):
            if name.split("-episode")[0] in set(hidden or ()):
                continue                                        # a premiere still to come
            episodes.append(a)
    shorts.sort(key=lambda a: a["name"], reverse=True)          # short-YYYY-MM-DD → newest first
    episodes.sort(key=lambda a: a["name"], reverse=True)        # dd4 before dd3
    order = []
    while shorts or episodes:
        if shorts:
            order.append(("short", shorts.pop(0)))
        if episodes:
            order.append(("episode", episodes.pop(0)))
    out = []
    for kind, a in order:
        digest = hashlib.sha1(("%s/%s/%s" % (a["release"], a["name"], a.get("size", 0))).encode()).hexdigest()[:12]
        out.append({"kind": kind, "release": a["release"], "name": a["name"], "size": a.get("size", 0),
                    "key": "norm-%s-%s.mp4" % (Path(a["name"]).stem, digest)})
    return out


def normalise_cmd(src, dst, kind, backdrop=None, canvas=CANVAS, ffmpeg="ffmpeg"):
    """ffmpeg argv that turns one clip into a loop-ready segment: one size, one frame rate,
    one codec profile, a keyframe every GOP frames and AAC 44.1 kHz stereo — identical
    settings on every clip are what let the reel be concatenated and streamed with `-c copy`.
    A Short (9:16) stands on the right of `backdrop` (the brand card at canvas size) when given,
    else on the navy; an episode (16:9) is scaled to fit."""
    w, h = canvas
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    if kind == "short" and backdrop:
        args += ["-loop", "1", "-i", str(backdrop), "-i", str(src), "-filter_complex",
                 "[1:v]scale=-2:%d:flags=lanczos,fps=%d[v];[0:v]scale=%d:%d,fps=%d[bg];"
                 "[bg][v]overlay=W-w-80:(H-h)/2:shortest=1,format=yuv420p[out]" % (h, FPS, w, h, FPS),
                 "-map", "[out]", "-map", "1:a?"]
    else:
        args += ["-i", str(src), "-vf",
                 "scale=%d:%d:force_original_aspect_ratio=decrease:flags=lanczos,"
                 "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=#0b2545,fps=%d,format=yuv420p" % (w, h, w, h, FPS)]
    args += ["-c:v", "libx264", "-preset", "veryfast", "-profile:v", "high", "-level", "4.1",
             "-b:v", "%dk" % VIDEO_KBPS, "-maxrate", "%dk" % VIDEO_KBPS, "-bufsize", "%dk" % (VIDEO_KBPS * 2),
             "-g", str(GOP), "-keyint_min", str(GOP), "-sc_threshold", "0", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "%dk" % AUDIO_KBPS, "-ar", "44100", "-ac", "2",
             "-af", "aresample=async=1:first_pts=0",
             "-movflags", "+faststart", "-shortest", str(dst)]
    return args


def concat_list(paths):
    """The concat demuxer's list file: one `file` line per segment, quoted its way."""
    return "".join("file '%s'\n" % str(p).replace("'", r"'\''") for p in paths)


def concat_cmd(list_path, reel, ffmpeg="ffmpeg"):
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path), "-c", "copy", "-movflags", "+faststart", str(reel)]


def stream_cmd(reel, ingest_url, stream_key, ffmpeg="ffmpeg"):
    """Push the reel in a loop, copying the bytes: `-re` paces it at real time, `-stream_loop -1`
    never ends, `-c copy` keeps the runner's CPU idle. The key rides on the URL — the workflow
    masks it in the log before this is ever run."""
    return [ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostdin",
            "-re", "-stream_loop", "-1", "-fflags", "+genpts", "-i", str(reel),
            "-c", "copy", "-bsf:a", "aac_adtstoasc",
            "-flvflags", "no_duration_filesize", "-f", "flv",
            "%s/%s" % (ingest_url.rstrip("/"), stream_key)]


def backdrop(out_path, size=CANVAS):
    """The brand card behind every Short in the loop: the card's words fill the left 1160 px,
    the Short stands in the clear navy on the right (tools/social_card.py colours)."""
    import social_card
    from PIL import Image
    w, h = size
    left = int(w * 0.60)
    tmp = str(Path(out_path).with_suffix(".card.jpg"))
    social_card.render("You're watching DocOga Live.\n\nRent law. On a loop. All day.\n\n"
                       "Full episodes in HD on the channel.",
                       tmp, kicker="LIVE 24/7 · PRE-RECORDED", size=(left, h), footer="docoga.com.ng")
    canvas = Image.new("RGB", (w, h), social_card.INK_BG)
    canvas.paste(Image.open(tmp).convert("RGB"), (0, 0))
    canvas.save(out_path, "JPEG", quality=92)
    Path(tmp).unlink(missing_ok=True)
    return out_path


def cover(out_path):
    """The live's thumbnail — the same card at YouTube's 1280×720."""
    import social_card
    social_card.render("Nigerian rent law, explained.\n\nAll day. Every day.\n\nPre-recorded episodes on a loop.",
                       out_path, kicker="DOCOGA LIVE 24/7", size=(1280, 720), footer="docoga.com.ng")
    return out_path


def build(plan_rows, lib_dir, reel_path, download, upload, log=print, run=subprocess.run,
          backdrop_path=None, ffmpeg="ffmpeg"):
    """Normalise what is new, keep what is not, concatenate the lot into `reel_path`.

    `download(release, name, dest_dir)` fetches one release asset; `upload(path)` banks a
    freshly normalised segment on the live-library release so the next run skips it.
    Returns the list of segment paths in loop order. Raises RuntimeError when nothing
    could be prepared — a live with no picture is not a live."""
    lib = Path(lib_dir)
    lib.mkdir(parents=True, exist_ok=True)
    segments = []
    for row in plan_rows:
        seg = lib / row["key"]
        if not seg.is_file():
            try:
                download(RELEASE_TAG, row["key"], lib)
            except Exception:  # noqa: BLE001 — not banked yet; normalise it now
                pass
        if seg.is_file() and seg.stat().st_size > 0:
            segments.append(seg)
            continue
        try:
            download(row["release"], row["name"], lib)
        except Exception as exc:  # noqa: BLE001
            log("::warning title=Clip not fetched::%s/%s — %s" % (row["release"], row["name"], exc))
            continue
        src = lib / row["name"]
        log("normalising %s (%s) → %s" % (row["name"], row["kind"], row["key"]))
        r = run(normalise_cmd(src, seg, row["kind"], backdrop=backdrop_path, ffmpeg=ffmpeg))
        if getattr(r, "returncode", 1) != 0 or not seg.is_file():
            log("::warning title=Clip not normalised::%s — ffmpeg exit %s" % (row["name"], getattr(r, "returncode", "?")))
            continue
        try:
            upload(seg)
        except Exception as exc:  # noqa: BLE001 — banking is a saving, not a condition
            log("::warning title=Segment not banked::%s — %s" % (seg.name, exc))
        segments.append(seg)
    if not segments:
        raise RuntimeError("no clip could be prepared for the loop")
    list_path = lib / "reel.txt"
    list_path.write_text(concat_list(segments), encoding="utf-8")
    r = run(concat_cmd(list_path, reel_path, ffmpeg=ffmpeg))
    if getattr(r, "returncode", 1) != 0 or not Path(reel_path).is_file():
        raise RuntimeError("the reel could not be concatenated (ffmpeg exit %s)" % getattr(r, "returncode", "?"))
    return segments


# ---------------------------------------------------------------- the broadcast

def broadcast_body(now=None, title=TITLE, description=DESCRIPTION):
    """liveBroadcasts.insert: public, starting now, auto-start when the stream arrives and
    NEVER auto-stop — the hand-over between runs is a minute of silence inside one broadcast,
    not a new video every six hours. Monitor stream off is what lets auto-start skip the
    testing stage. DVR on so a viewer can scrub back; not made for kids (it is tenancy law)."""
    now = now or datetime.now(timezone.utc)
    return {
        "snippet": {"title": title, "description": description,
                    "scheduledStartTime": now.strftime("%Y-%m-%dT%H:%M:%SZ")},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        "contentDetails": {"enableAutoStart": True, "enableAutoStop": False, "enableDvr": True,
                           "enableEmbed": True, "recordFromStart": True, "latencyPreference": "normal",
                           "monitorStream": {"enableMonitorStream": False}},
    }


def stream_body():
    """liveStreams.insert: one reusable RTMP stream whose key every run shares."""
    return {"snippet": {"title": STREAM_TITLE},
            "cdn": {"ingestionType": "rtmp", "resolution": "1080p", "frameRate": "30fps"},
            "contentDetails": {"isReusable": True}}


def _get(http, path, **params):
    r = http.request("GET", "%s/%s" % (API, path), params=params)
    if r.status_code != 200:
        raise _refusal(r, "GET %s" % path)
    return r.json() or {}


def _post(http, path, body, **params):
    r = http.request("POST", "%s/%s" % (API, path), params=params,
                     headers={"Content-Type": "application/json"}, data=json.dumps(body) if body is not None else None)
    if r.status_code not in (200, 201):
        raise _refusal(r, "POST %s" % path)
    return r.json() if r.text else {}


def _refusal(r, what):
    kind, reason, _w, action, _ = yt_publish.classify(r.status_code, r.text)
    text = (r.text or "")[:300]
    if r.status_code == 403 and "liveStreamingNotEnabled" in text:
        return yt_publish.Problem("setup", "liveStreamingNotEnabled",
                                  "%s: the channel is not enabled for live streaming" % what,
                                  "YouTube Studio → Create → Go live, verify by phone once; up to 24 h.", 2)
    return yt_publish.Problem(kind or "forbidden", reason or "refused",
                              "%s: HTTP %s — %s" % (what, r.status_code, text),
                              action or "See the reason; the stream will be retried by the next run.")


def ensure(http, now=None, log=print):
    """The live broadcast and the key to feed it: reuse whatever is already live, else make
    one and bind the reusable stream. Returns the dict the stream step reads."""
    streams = _get(http, "liveStreams", part="id,snippet,cdn,status", mine="true", maxResults=50).get("items", [])
    stream = next((s for s in streams if s.get("snippet", {}).get("title") == STREAM_TITLE), None)
    created_stream = False
    if stream is None:
        stream = _post(http, "liveStreams", stream_body(), part="id,snippet,cdn,contentDetails,status")
        created_stream = True
    ingest = (stream.get("cdn") or {}).get("ingestionInfo") or {}
    url = ingest.get("rtmpsIngestionAddress") or ingest.get("ingestionAddress") or ""
    key = ingest.get("streamName") or ""
    if not (url and key):
        raise yt_publish.Problem("forbidden", "noIngest", "the stream has no ingestion address/key",
                                 "Delete the stream in Studio → Manage streams and let the next run recreate it.")

    live = _get(http, "liveBroadcasts", part="id,snippet,status,contentDetails", mine="true",
                broadcastStatus="active", maxResults=50).get("items", [])
    ours = [b for b in live if b.get("snippet", {}).get("title") == TITLE]
    created = False
    if ours:
        bc = ours[0]
    else:
        upcoming = _get(http, "liveBroadcasts", part="id,snippet,status,contentDetails", mine="true",
                        broadcastStatus="upcoming", maxResults=50).get("items", [])
        ours = [b for b in upcoming if b.get("snippet", {}).get("title") == TITLE]
        if ours:
            bc = ours[0]
        else:
            bc = _post(http, "liveBroadcasts", broadcast_body(now), part="id,snippet,status,contentDetails")
            created = True
    bound = (bc.get("contentDetails") or {}).get("boundStreamId")
    if bound != stream["id"]:
        bc = _post(http, "liveBroadcasts/bind", None, part="id,contentDetails", id=bc["id"], streamId=stream["id"])
    out = {"broadcast_id": bc["id"], "stream_id": stream["id"], "ingest_url": url, "stream_key": key,
           "created": created, "created_stream": created_stream,
           "watch_url": "https://www.youtube.com/watch?v=%s" % bc["id"],
           "status": (bc.get("status") or {}).get("lifeCycleStatus", "")}
    log("broadcast %s (%s%s) on stream %s" % (bc["id"], out["status"] or "?", ", new" if created else "", stream["id"]))
    return out


def end_all(http, log=print):
    """`off`: transition every active broadcast of ours to complete. Returns the ids ended."""
    live = _get(http, "liveBroadcasts", part="id,snippet,status", mine="true",
                broadcastStatus="active", maxResults=50).get("items", [])
    ended = []
    for b in live:
        if b.get("snippet", {}).get("title") != TITLE:
            continue
        _post(http, "liveBroadcasts/transition", None, part="id,status", id=b["id"], broadcastStatus="complete")
        ended.append(b["id"])
        log("ended %s" % b["id"])
    return ended


def record(entry, path=LEDGER, now=None):
    """Newest-first ledger of the broadcasts this lane created — the dashboard's and the
    owner's one place to find the live's URL."""
    path = Path(path)
    rows = []
    if path.is_file():
        try:
            rows = json.loads(path.read_text(encoding="utf-8")) or []
        except ValueError:
            rows = []
    if any(r.get("broadcast_id") == entry.get("broadcast_id") for r in rows):
        return rows
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows.insert(0, dict(entry, created_at=stamp))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return rows


# ------------------------------------------------------------------ the push

def stream(reel, ingest_url, stream_key, minutes=LIVE_MINUTES, popen=subprocess.Popen, clock=time.monotonic,
           sleep=time.sleep, log=print, ffmpeg="ffmpeg", retry_wait=5.0):
    """Keep ffmpeg pushing until the deadline. A push that dies early (a network blip, an
    ingest hiccup) is restarted after `retry_wait`; a push that keeps dying inside its first
    minute is a fault, and after five of those in a row the run stops with exit 3 so the
    issue is visible rather than a silent six hours of reconnects. Returns the exit code."""
    deadline = clock() + minutes * 60
    quick_deaths = 0
    attempts = 0
    while clock() < deadline:
        attempts += 1
        started = clock()
        proc = popen(stream_cmd(reel, ingest_url, stream_key, ffmpeg=ffmpeg))
        while clock() < deadline:
            code = proc.poll()
            if code is not None:
                break
            sleep(5)
        else:
            try:
                proc.terminate()
                proc.wait(timeout=20)
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
            log("window complete after %d push(es); the next run is already queued" % attempts)
            return 0
        ran = clock() - started
        if ran < 60:
            quick_deaths += 1
        else:
            quick_deaths = 0
        log("::warning title=Push ended::ffmpeg exited %s after %ds; reconnecting" % (code, int(ran)))
        if quick_deaths >= 5:
            log("::error title=Ingest refused::five pushes died inside a minute each — see the stream key, the broadcast state and the reel")
            return 3
        sleep(retry_wait)
    return 0


# --------------------------------------------------------------------- CLI

def _gh(args, env=None):
    return subprocess.run(["gh"] + list(args), check=True, capture_output=True, text=True, env=env).stdout


def gh_download(release, name, dest_dir):
    _gh(["release", "download", release, "--pattern", name, "-D", str(dest_dir), "--clobber"])


def gh_upload(path, release=RELEASE_TAG):
    _gh(["release", "upload", release, str(path), "--clobber"])


def main(argv=None, http=None):
    ap = argparse.ArgumentParser(description="DocOga Live — the always-on stream")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan"); p.add_argument("--assets", required=True); p.add_argument("--out", required=True)
    p.add_argument("--ledger", default=str(LONGFORM_LEDGER))
    b = sub.add_parser("build"); b.add_argument("--plan", required=True); b.add_argument("--lib", required=True)
    b.add_argument("--reel", required=True); b.add_argument("--backdrop", default="")
    e = sub.add_parser("ensure"); e.add_argument("--out", required=True); e.add_argument("--cover", default="")
    s = sub.add_parser("stream"); s.add_argument("--reel", required=True); s.add_argument("--ingest", required=True)
    s.add_argument("--minutes", type=int, default=LIVE_MINUTES)
    sub.add_parser("off")
    c = sub.add_parser("cover"); c.add_argument("--out", required=True)
    bd = sub.add_parser("backdrop"); bd.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "plan":
        assets = json.loads(Path(a.assets).read_text(encoding="utf-8"))
        try:
            ledger_rows = json.loads(Path(a.ledger).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            ledger_rows = []
        hidden = hidden_episodes(ledger_rows)
        if hidden:
            print("LIVE_HIDDEN=%s" % ",".join(sorted(hidden)))
        rows = plan(assets, hidden=hidden)
        Path(a.out).write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print("LIVE_CLIPS=%d" % len(rows))
        for r in rows:
            print("  %-8s %s" % (r["kind"], r["name"]))
        return 0 if rows else 5
    if a.cmd == "cover":
        cover(a.out); print(a.out); return 0
    if a.cmd == "backdrop":
        backdrop(a.out); print(a.out); return 0
    if a.cmd == "build":
        rows = json.loads(Path(a.plan).read_text(encoding="utf-8"))
        try:
            segs = build(rows, a.lib, a.reel, gh_download, gh_upload, backdrop_path=a.backdrop or None)
        except RuntimeError as exc:
            print("::error title=No reel::%s" % exc); return 5
        print("LIVE_SEGMENTS=%d" % len(segs)); return 0
    try:
        http, _ = yt_publish.authorize(http)
        if a.cmd == "ensure":
            info = ensure(http)
            Path(a.out).write_text(json.dumps(info) + "\n", encoding="utf-8")
            os.chmod(a.out, 0o600)
            if info.get("created"):
                record({"broadcast_id": info["broadcast_id"], "watch_url": info["watch_url"],
                        "stream_id": info["stream_id"], "title": TITLE})
                if a.cover:
                    import yt_thumbnail
                    ok, note = yt_thumbnail.set_thumbnail(info["broadcast_id"], a.cover, http=http)
                    print(("cover: %s" % note) if ok else "::warning title=Live cover not set::%s" % note)
            print("LIVE_URL=%s" % info["watch_url"])
            print("LIVE_CREATED=%s" % ("yes" if info.get("created") else "no"))
            return 0
        if a.cmd == "off":
            ended = end_all(http)
            print("LIVE_ENDED=%d" % len(ended)); return 0
        if a.cmd == "stream":
            info = json.loads(Path(a.ingest).read_text(encoding="utf-8"))
            return stream(a.reel, info["ingest_url"], info["stream_key"], minutes=a.minutes)
    except yt_publish.Problem as exc:
        print("::error title=DocOga Live %s::%s %s" % (exc.kind, exc.what, exc.action))
        return getattr(exc, "exit_code", 1) or 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
