#!/usr/bin/env python3
"""
DEEPDIVE — the DocOga long-form engine (16:9 · 1920×1080 · 30 fps · word-synced)
================================================================================

One tool, one episode folder, every stage — so an episode can be produced
unattended on a GitHub runner and nothing lives only on a laptop again.

    episodes/<id>/episode.json   title, voice, section titles, beats, cover, YouTube meta
    episodes/<id>/script.txt     the narration, nine sections split by `--- C1 --- … --- C9 ---`
    episodes/assets/<name>.jpg   the photographic plates (treated to the navy duotone at render)

    build/deepdive/<id>/voice/c{1..9}.mp3   Gemini TTS, preamble-trimmed, ASR-verified
    build/deepdive/<id>/words.json          word timings (Vosk) — the sync source for everything
    build/deepdive/<id>/scenes/s{1..9}.mp4  one segment per section (render in parallel)
    build/deepdive/<id>/<id>-episode.mp4    master: concat + voice + loudnorm −16 LUFS
    build/deepdive/<id>/<id>-cover.jpg      1280×720 thumbnail

Stages (each resumable, each idempotent):
    python3 tools/deepdive.py dd2 check            # script ↔ beats: every trigger phrase present, in order
    python3 tools/deepdive.py dd2 tts [--wait-budget-min 40]   # Gemini TTS, skips verified chunks
    python3 tools/deepdive.py dd2 align [--synthetic]           # Vosk word-sync → words.json
    python3 tools/deepdive.py dd2 render all|N
    python3 tools/deepdive.py dd2 master [--allow-synthetic]
    python3 tools/deepdive.py dd2 cover
    python3 tools/deepdive.py dd2 qa
    python3 tools/deepdive.py dd2 meta             # title/description/tags for the uploader

Look (docs/BRAND_STYLE.md "Deep-Dive Videos"): navy canvas, left gradient over a
duotone plate, Inter Black headlines with the yellow accent rule, numbered rows
panel, ASR captions, progress bar, DOCOGA end card, grain at encode. Palette and
Inter come from tools/motionstudio.py — there is no second palette here.

Exit codes: 0 ok · 1 error · 2 environment (fonts/ffmpeg/vosk/key) · 5 TTS quota
(chunks so far are kept — re-run when the daily bucket refills).
"""

import argparse
import base64
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import motionstudio as ms  # noqa: E402  — palette, Inter, ffmpeg
import gemini_quota  # noqa: E402  — the narrator's bucket: which quota, how much, when it refills

W, H, FPS = 1920, 1080, 30
NAVY, PANEL, WHITE, MUTED, FAINT = ms.NAVY, ms.PANEL, ms.WHITE, ms.MUTED, ms.FAINT
BLUE, YELLOW, RED, GREEN = ms.BLUE, ms.YELLOW, ms.RED, ms.GREEN
RULE = ms.NAVY2
PLATE_DARK = (2, 10, 22)        # the duotone's black point — a shade of the canvas, not a new colour
PLATE_LIGHT = (202, 222, 248)   # the duotone's white point
GLASS = (4, 16, 33)             # caption / rows panel fill (alpha applied at draw time)

# ───────────────────────────── THE VOICE — LOCKED ─────────────────────────────
# Owner instruction, 14 Oct 2026: "Lock that voice in. On no occasion shall it change — not
# even by one sentence or word, not even by mistake."
#
# This is the DocOga narrator for every Deep-Dive, now and later. It is the only place the
# voice is defined. episode.json cannot override it, no environment variable reaches it, no
# CLI flag selects another, and the TTS request is built from these two strings alone.
# If a future episode file carries a different `voice` block the engine refuses to run.
# tools/tests/test_deepdive.py and tools/qa.py pin the exact bytes by SHA-256; editing this
# block (even whitespace) turns CI red. Do not edit it.
LOCKED_VOICE_NAME = "Orus"
LOCKED_VOICE_INSTRUCTION = ("Narrate this in a natural Nigerian English accent, "
                            "like a confident Lagos radio presenter:")
LOCKED_VOICE_SHA256 = "697e3233c630632bfa394317cc8902f0ab51e6d70670921c360d2161e6cff663"
LOCKED_VOICE_NOTE = "voice is locked by the owner (14 Oct 2026) — do not edit"


def locked_voice():
    """The narrator, verified against its own fingerprint before every use."""
    import hashlib
    digest = hashlib.sha256((LOCKED_VOICE_NAME + "\n" + LOCKED_VOICE_INSTRUCTION).encode("utf-8")).hexdigest()
    if digest != LOCKED_VOICE_SHA256:
        die("LOCKED VOICE TAMPERED: the narrator constants in tools/deepdive.py no longer match their "
            "fingerprint. " + LOCKED_VOICE_NOTE, 2)
    return LOCKED_VOICE_NAME, LOCKED_VOICE_INSTRUCTION


def voice_problems(meta):
    """An episode may omit `voice`, or restate the locked one exactly. Anything else is refused."""
    v = meta.get("voice")
    if v is None:
        return []
    if not isinstance(v, dict):
        return ["episode.json `voice` must be absent or exactly the locked voice — " + LOCKED_VOICE_NOTE]
    probs = []
    if v.get("name") != LOCKED_VOICE_NAME:
        probs.append("episode.json voice.name is %r; the narrator is %r — %s"
                     % (v.get("name"), LOCKED_VOICE_NAME, LOCKED_VOICE_NOTE))
    if v.get("instruction") != LOCKED_VOICE_INSTRUCTION:
        probs.append("episode.json voice.instruction differs from the locked instruction — " + LOCKED_VOICE_NOTE)
    extra = set(v) - {"name", "instruction", "_locked"}
    if extra:
        probs.append("episode.json voice has unexpected keys %s — %s" % (sorted(extra), LOCKED_VOICE_NOTE))
    return probs


EPISODES = ROOT / "episodes"
ASSETS = EPISODES / "assets"
BUILD = ROOT / "build" / "deepdive"

GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
# The narrator's ladder. 2.5 Flash TTS is what the lock was fingerprinted on; 2.5 Pro TTS left the
# free tier in Oct 2026 and 3.8 Flash-Lite TTS joined it — the voice (Orus) and the instruction are
# the same prebuilt-voice contract on every rung, so the lock holds whichever rung answers.
GEMINI_MODELS = ("gemini-2.5-flash-preview-tts", "gemini-3.8-flash-lite-tts", "gemini-2.5-pro-preview-tts")
VOSK_MODEL_DIR = Path(os.environ.get("VOSK_MODEL_DIR", "/tmp/vosk/vosk-model-small-en-us-0.15"))
VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
# Words the TTS model sometimes reads aloud from the style instruction. If any of them
# is heard in the first seconds of a chunk the preamble leaked and the chunk is trimmed.
PREAMBLE_WORDS = ("narrate", "narrator", "narrates", "accent", "presenter", "articulation",
                  "radio", "instruction")

MIN_EPISODE_SECONDS = 240      # under four minutes is not a Deep-Dive
MAX_BED_SEPARATION_DB = 22    # further than this and the owner hears no music at all (run #1 was 27 by raw power)
RENDERING_STAGES = ("tts", "align", "render", "master", "cover", "qa")   # need Inter + ffmpeg
MIN_BED_SEPARATION_DB = 11    # music under speech, at least this far below the voice — A-weighted (as heard)
MAX_EPISODE_SECONDS = 1500


# ───────────────────────────── small helpers ─────────────────────────────
def ffmpeg():
    ff = ms.find_ffmpeg()
    if not ff:
        die("ffmpeg not found (set FFMPEG_BIN or install ffmpeg)", 2)
    return ff


def die(msg, code=1):
    print("❌ " + msg, flush=True)
    sys.exit(code)


def norm(w):
    return "".join(c for c in w.lower() if c.isalnum() or c == "'")


def norm_tokens(t):
    t = t.lower().replace("\u2014", " ").replace("\u2013", " ").replace("-", " ")
    t = re.sub(r"[^a-z0-9' ]", " ", t)
    return [w for w in t.split() if w]


def display_tokens(t):
    """Same split as norm_tokens, original casing kept — what the captions show."""
    t = t.replace("\u2014", " ").replace("\u2013", " ").replace("-", " ")
    t = re.sub(r"[^A-Za-z0-9' ]", " ", t)
    toks = [w for w in t.split() if w]
    assert [w.lower() for w in toks] == norm_tokens(t), "display/norm tokenisation drifted"
    return toks


def find_idx(sec_words, trig, from_i=0):
    t = [norm(x) for x in trig]
    n = [norm(w["w"]) for w in sec_words]
    for i in range(from_i, len(n) - len(t) + 1):
        if n[i:i + len(t)] == t:
            return i
    return None


_fc = {}


def font(weight, size):
    key = (weight, size)
    if key not in _fc:
        _fc[key] = ImageFont.truetype(ms.F.format(weight), size)
    return _fc[key]


def media_duration(path):
    """Seconds, from ffmpeg's own banner (no ffprobe dependency)."""
    r = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        return 0.0
    hh, mm, ss = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return hh * 3600 + mm * 60 + ss


# ───────────────────────────── episode model ─────────────────────────────
class Episode:
    def __init__(self, ep_id):
        self.id = ep_id
        self.dir = EPISODES / ep_id
        if not (self.dir / "episode.json").is_file():
            die("no such episode: %s (expected %s/episode.json)" % (ep_id, self.dir))
        self.meta = json.loads((self.dir / "episode.json").read_text(encoding="utf-8"))
        text = (self.dir / "script.txt").read_text(encoding="utf-8")
        parts = re.split(r"---\s*C(\d+)\s*---", text)
        self.sections = []
        for i in range(1, len(parts) - 1, 2):
            self.sections.append(parts[i + 1].strip())
        n = len(self.meta["sections"])
        if len(self.sections) != n:
            die("%s: script has %d sections, episode.json declares %d" % (ep_id, len(self.sections), n))
        vp = voice_problems(self.meta)
        if vp:
            die("%s: %s" % (ep_id, "; ".join(vp)), 2)
        self.build = BUILD / ep_id
        self.voice_dir = self.build / "voice"
        self.scene_dir = self.build / "scenes"
        self.words_path = self.build / "words.json"
        self.master_path = self.build / ("%s-episode.mp4" % ep_id)
        self.cover_path = self.build / ("%s-cover.jpg" % ep_id)

    @property
    def n(self):
        return len(self.sections)

    def chunk(self, i):
        return self.voice_dir / ("c%d.mp3" % i)

    def section_title(self, i):
        return self.meta["sections"][i - 1]["title"]

    def beats(self, sec=None):
        bs = [dict(b) for b in self.meta["beats"]]
        for b in bs:
            b.setdefault("sub", "")
            b.setdefault("img", None)
            b.setdefault("shot", None)
            b.setdefault("rows", [])
            b.setdefault("row_trigs", [])
            b.setdefault("center", False)
            b.setdefault("endcard", False)
            b.setdefault("trig", None)
        return [b for b in bs if sec is None or b["sec"] == sec]

    def load_words(self):
        if not self.words_path.is_file():
            die("%s missing — run `align` first" % self.words_path)
        d = json.loads(self.words_path.read_text(encoding="utf-8"))
        by_sec = {}
        for w in d["words"]:
            by_sec.setdefault(w["sec"], []).append(w)
        return d, d["words"], d["sections"], by_sec


# ───────────────────────────── stage: check ─────────────────────────────
def check_triggers(ep, verbose=True):
    """Every beat trigger (and row trigger) must occur in its section's script, in order.

    This is the contract between the writer and the renderer: a beat whose trigger
    is never spoken snaps to the section start and the headline lands early.
    Runs without audio, so it is also a unit test.
    """
    problems = []
    for s in range(1, ep.n + 1):
        toks = [{"w": t} for t in norm_tokens(ep.sections[s - 1])]
        cursor = 0
        for b in ep.beats(s):
            if b["trig"]:
                i = find_idx(toks, b["trig"], cursor)
                if i is None:
                    problems.append("section %d: trigger %r for '%s' not found after word %d"
                                    % (s, " ".join(b["trig"]), b["head"], cursor))
                else:
                    cursor = i
            for rt in b["row_trigs"]:
                if find_idx(toks, rt, 0) is None:
                    problems.append("section %d: row trigger %r for '%s' not found"
                                    % (s, " ".join(rt), b["head"]))
    problems += voice_problems(ep.meta)
    words = sum(len(norm_tokens(t)) for t in ep.sections)
    if verbose:
        for p in problems:
            print("  ❌ " + p)
        print("  narrator: %s — locked by the owner, fingerprint %s…" % (locked_voice()[0], LOCKED_VOICE_SHA256[:12]))
        est = words / 2.45
        print("  script: %d words ≈ %d:%02d at narration pace · %d beats · %d sections"
              % (words, est // 60, est % 60, len(ep.beats()), ep.n))
        print("  ✅ every trigger phrase is in the script, in order" if not problems
              else "  → %d trigger problem(s)" % len(problems))
    return problems


# ───────────────────────────── stage: tts ─────────────────────────────
def gemini_key():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k
    env_path = ROOT / ".worker-secrets.env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    return ""


def parse_retry_seconds(body):
    m = re.search(r"retry in ([0-9.]+)s", body, re.I) or re.search(r'"retryDelay":\s*"([0-9.]+)s"', body)
    return float(m.group(1)) if m else None


def gemini_tts(text, voice, instruction, out_mp3, models=None):
    """One request → one mp3. Returns ('ok', 0) | ('wait', seconds) | ('fail', 0)."""
    if (voice, instruction) != locked_voice():
        die("refusing to synthesize with a voice other than the locked narrator — " + LOCKED_VOICE_NOTE, 2)
    key = gemini_key()
    if not key:
        die("GEMINI_API_KEY is not set (repository secret on CI; .worker-secrets.env locally)", 2)
    env_model = os.environ.get("GEMINI_TTS_MODEL", "").strip()
    models = models or ((env_model,) if env_model else ()) + GEMINI_MODELS
    prompt = (instruction.strip() + " " if instruction.strip() else "") + text
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    last = ""
    for model in models:
        req = urllib.request.Request(GEMINI_API.format(model), data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                resp = json.loads(r.read())
        except urllib.error.HTTPError as e:
            full = e.read().decode("utf-8", "replace")
            last = full[:600]
            if e.code == 429:
                # Read the whole refusal: which bucket (per-minute or per-day), its limit,
                # and therefore *when* the next request can succeed. A per-day refusal
                # is an appointment at the Pacific midnight, not a number of seconds.
                refusal = gemini_quota.parse_refusal(full)
                gemini_quota.note_request(model, "exhausted", refusal)
                wait = gemini_quota.wait_seconds(refusal)
                if refusal["scope"] == "day":
                    print("  quota: the free DAILY bucket for %s is empty%s — it refills at %s"
                          % (model, (" (limit %d/day)" % refusal["limit"]) if refusal.get("limit") else "",
                             gemini_quota.lagos(gemini_quota.next_reset())))
                return "wait", wait
            if e.code == 404:
                print("  model %s not available here — trying the next" % model)
                continue
            print("  HTTP %d from %s: %s" % (e.code, model, last[:200]))
            gemini_quota.note_request(model, "fail")
            return "fail", 0
        except Exception as exc:  # network
            print("  %s: %s" % (type(exc).__name__, exc))
            gemini_quota.note_request(model, "fail")
            return "fail", 0
        gemini_quota.note_request(model, "ok")
        try:
            inline = resp["candidates"][0]["content"]["parts"][0]["inlineData"]
            pcm = base64.b64decode(inline["data"])
        except (KeyError, IndexError):
            print("  unexpected response: " + json.dumps(resp)[:300])
            return "fail", 0
        rate = 24000
        m = re.search(r"rate=(\d+)", inline.get("mimeType", ""))
        if m:
            rate = int(m.group(1))
        out_mp3 = Path(out_mp3)
        out_mp3.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([ffmpeg(), "-y", "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "-",
                            "-c:a", "libmp3lame", "-b:a", "192k", "-write_xing", "1", str(out_mp3)],
                           input=pcm, capture_output=True)
        if r.returncode != 0 or not out_mp3.is_file():
            print("  encode failed: " + r.stderr.decode("utf-8", "replace")[-200:])
            return "fail", 0
        return "ok", 0
    print("  no TTS model answered: " + last[:200])
    return "fail", 0


def vosk_available():
    try:
        import vosk  # noqa: F401
    except ImportError:
        return False
    return VOSK_MODEL_DIR.is_dir()


def ensure_vosk(install=False):
    if vosk_available():
        return True
    if not install:
        return False
    try:
        import vosk  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "vosk"], check=False)
    if not VOSK_MODEL_DIR.is_dir():
        VOSK_MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
        zpath = VOSK_MODEL_DIR.parent / "model.zip"
        subprocess.run(["curl", "-fsSL", "-o", str(zpath), VOSK_MODEL_URL], check=False)
        if zpath.is_file():
            import zipfile
            zipfile.ZipFile(zpath).extractall(VOSK_MODEL_DIR.parent)
            zpath.unlink()
    return vosk_available()


_vosk_model = None


def asr_words(path):
    """[(word, start, end)] from Vosk."""
    global _vosk_model
    from vosk import KaldiRecognizer, Model, SetLogLevel
    SetLogLevel(-1)
    if _vosk_model is None:
        _vosk_model = Model(str(VOSK_MODEL_DIR))
    pcm = subprocess.run([ffmpeg(), "-i", str(path), "-ar", "16000", "-ac", "1", "-f", "s16le", "-"],
                         capture_output=True).stdout
    rec = KaldiRecognizer(_vosk_model, 16000)
    rec.SetWords(True)
    out = []
    for i in range(0, len(pcm), 8000):
        if rec.AcceptWaveform(pcm[i:i + 8000]):
            out += json.loads(rec.Result()).get("result", [])
    out += json.loads(rec.FinalResult()).get("result", [])
    return [(w["word"], w["start"], w["end"]) for w in out]


def chunk_verdict(ep, i, heard):
    """(clean, reason) — no preamble words early, and the section's opening words are heard."""
    n = [norm(w) for w, _, _ in heard]
    head = [norm(x) for x in norm_tokens(ep.sections[i - 1])[:8]]
    leak = [b for b in PREAMBLE_WORDS if b in n[:26]]
    starts_ok = bool(n) and any(x in head for x in n[:4])
    if leak:
        return False, "preamble leaked: %s" % ",".join(leak)
    if not starts_ok:
        return False, "does not open with the script (heard: %s)" % " ".join(n[:6])
    return True, "ok"


def trim_preamble(ep, i, path):
    """Cut the spoken style instruction off the front of a chunk, using ASR timings."""
    heard = asr_words(path)
    if not heard:
        return False
    n = [norm(w) for w, _, _ in heard]
    head = [norm(x) for x in norm_tokens(ep.sections[i - 1])[:8]]
    cut = None
    for k in range(min(len(n) - 3, 40)):
        if n[k] == head[0] and any(head[j] in n[k + 1:k + 6] for j in (1, 2, 3)):
            cut = max(0.0, heard[k][1] - 0.35)
            break
    if cut is None:
        last_bad = None
        for k in range(min(30, len(heard))):
            if n[k] in PREAMBLE_WORDS:
                last_bad = heard[k]
        if last_bad:
            cut = last_bad[2] + 0.12
    if cut is None or cut <= 0.05 or cut > 0.25 * heard[-1][2]:
        return False
    tmp = path.with_suffix(".trim.mp3")
    subprocess.run([ffmpeg(), "-y", "-ss", "%.2f" % cut, "-i", str(path), "-c:a", "libmp3lame",
                    "-b:a", "192k", "-write_xing", "1", str(tmp)], capture_output=True)
    if not (tmp.is_file() and tmp.stat().st_size > 10_000):
        return False
    tmp.replace(path)
    return True


def voice_manifest(ep):
    man = {"episode": ep.id, "chunks": {}}
    for i in range(1, ep.n + 1):
        p = ep.chunk(i)
        if p.is_file():
            man["chunks"][str(i)] = {"seconds": round(media_duration(p), 2),
                                     "sha1": hashlib.sha1(p.read_bytes()).hexdigest()[:12],
                                     "verified": (ep.voice_dir / ("c%d.ok" % i)).is_file()}
    (ep.voice_dir / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    return man


def stage_tts(ep, args):
    ep.voice_dir.mkdir(parents=True, exist_ok=True)
    have_asr = ensure_vosk(install=args.install_deps)
    if not have_asr and not args.no_asr:
        die("Vosk (ASR) is not available — needed to verify and trim each chunk. "
            "Run with --install-deps on a machine that can reach alphacephei.com, or --no-asr "
            "to generate unverified chunks.", 2)
    voice, instruction = locked_voice()          # never from episode.json, env, or flags
    print("  narrator: %s — locked (%s…)" % (voice, LOCKED_VOICE_SHA256[:12]))
    budget_end = time.time() + 60 * args.wait_budget_min
    requests_made = 0
    pending = []
    for i in range(1, ep.n + 1):
        p = ep.chunk(i)
        ok_flag = ep.voice_dir / ("c%d.ok" % i)
        if p.is_file() and ok_flag.is_file():
            print("  c%d ✅ banked (%.1fs)" % (i, media_duration(p)))
            continue
        if p.is_file() and have_asr:
            clean, why = chunk_verdict(ep, i, asr_words(p))
            if not clean and "preamble" in why and trim_preamble(ep, i, p):
                clean, why = chunk_verdict(ep, i, asr_words(p))
            if clean:
                ok_flag.touch()
                print("  c%d ✅ verified existing (%.1fs)" % (i, media_duration(p)))
                continue
            print("  c%d ✗ existing chunk rejected (%s) — regenerating" % (i, why))
            p.unlink()
        pending.append(i)

    for i in pending:
        if args.max_requests and requests_made >= args.max_requests:
            print("  stopping at --max-requests %d" % args.max_requests)
            break
        text = ep.sections[i - 1]
        p = ep.chunk(i)
        for attempt in range(3):
            if args.max_requests and requests_made >= args.max_requests:
                voice_manifest(ep)
                print("  --max-requests %d reached mid-chunk; %d of %d banked — continuing tomorrow"
                      % (args.max_requests, len(list(ep.voice_dir.glob("c*.ok"))), ep.n))
                sys.exit(5)
            print("  c%d → Gemini TTS (%s, %d words)…" % (i, voice, len(text.split())), flush=True)
            status, wait = gemini_tts(text, voice, instruction, p)
            requests_made += 1
            if status == "ok":
                break
            if status == "wait":
                if time.time() + wait <= budget_end:
                    print("  quota holds — API says retry in %.0fs; waiting (budget %d min)"
                          % (wait, args.wait_budget_min), flush=True)
                    time.sleep(wait + 2)
                    continue
                voice_manifest(ep)
                print("  quota exhausted and the wait (%s) exceeds the budget. %d of %d chunks are banked; "
                      "the nightly run continues after the bucket refills at %s."
                      % (gemini_quota.human_wait(wait), len(list(ep.voice_dir.glob("c*.ok"))), ep.n,
                         gemini_quota.lagos(gemini_quota.next_reset())))
                print("  " + gemini_quota.status_line())
                sys.exit(5)
            time.sleep(3)
        else:
            voice_manifest(ep)
            die("c%d: TTS failed three times" % i)
        if have_asr:
            heard = asr_words(p)
            clean, why = chunk_verdict(ep, i, heard)
            if not clean and "preamble" in why:
                if trim_preamble(ep, i, p):
                    clean, why = chunk_verdict(ep, i, asr_words(p))
            if not clean:
                print("  c%d ✗ %s — will regenerate on the next run" % (i, why))
                p.unlink(missing_ok=True)
                continue
            (ep.voice_dir / ("c%d.ok" % i)).touch()
        print("  c%d ✅ %.1fs" % (i, media_duration(p)))
    man = voice_manifest(ep)
    banked = sum(1 for c in man["chunks"].values() if c["verified"] or args.no_asr)
    print("  voice: %d/%d chunks banked · %.1f s total"
          % (banked, ep.n, sum(c["seconds"] for c in man["chunks"].values())))
    if banked < ep.n:
        sys.exit(5 if pending else 1)


# ───────────────────────────── stage: align ─────────────────────────────
def align_section(sec_idx, text, rec):
    stoks = norm_tokens(text)
    disp = display_tokens(text)
    rt_flat = []
    for tok, t0, t1 in rec:
        for e in (norm_tokens(tok) or [tok.lower()]):
            rt_flat.append((e, t0, t1))
    sm = SequenceMatcher(None, [r[0] for r in rt_flat], stoks, autojunk=False)
    words = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                words.append({"w": stoks[j1 + k], "d": disp[j1 + k], "t0": rt_flat[i1 + k][1],
                              "t1": rt_flat[i1 + k][2], "sec": sec_idx})
        else:
            n = j2 - j1
            if n == 0:
                continue
            start = rt_flat[i1 - 1][2] if i1 > 0 else 0.0
            end = rt_flat[i2][1] if i2 < len(rt_flat) else (rt_flat[-1][2] if rt_flat else start)
            dt = max(0.0, end - start) / n
            for k in range(n):
                words.append({"w": stoks[j1 + k], "d": disp[j1 + k], "t0": round(start + k * dt, 3),
                              "t1": round(start + (k + 1) * dt, 3), "sec": sec_idx})
    return words


def synthetic_words(ep, seconds_per_section=None):
    """Timings from pace alone — for previews and tests, never for a publish."""
    words, sections, off = [], [], 0.0
    for i, text in enumerate(ep.sections, 1):
        toks = norm_tokens(text)
        disp = display_tokens(text)
        dur = seconds_per_section[i - 1] if seconds_per_section else len(toks) / 2.45 + 0.8
        dt = (dur - 0.6) / max(1, len(toks))
        for k, w in enumerate(toks):
            words.append({"w": w, "d": disp[k], "t0": round(off + 0.3 + k * dt, 3),
                          "t1": round(off + 0.3 + (k + 0.85) * dt, 3), "sec": i})
        sections.append({"sec": i, "title": ep.section_title(i), "start": round(off, 2),
                         "end": round(off + dur, 2), "asr_words": 0, "script_words": len(toks)})
        off += dur
    return {"words": words, "sections": sections, "engine": "synthetic", "synthetic": True}


def stage_align(ep, args):
    ep.build.mkdir(parents=True, exist_ok=True)
    chunks = [ep.chunk(i) for i in range(1, ep.n + 1)]
    if args.synthetic:
        durs = [media_duration(c) for c in chunks] if all(c.is_file() for c in chunks) else None
        if args.seconds_per_section:
            durs = [float(args.seconds_per_section)] * ep.n
            for c in chunks:
                c.unlink(missing_ok=True)
        d = synthetic_words(ep, durs)
        if durs is None or args.seconds_per_section:
            # No voice yet: make silent stand-in chunks so render/master can be exercised.
            ep.voice_dir.mkdir(parents=True, exist_ok=True)
            for i, s in enumerate(d["sections"], 1):
                subprocess.run([ffmpeg(), "-y", "-f", "lavfi", "-t", "%.2f" % (s["end"] - s["start"]),
                                "-i", "anullsrc=r=24000:cl=mono", "-c:a", "libmp3lame", "-b:a", "64k",
                                str(ep.chunk(i))], capture_output=True)
        ep.words_path.write_text(json.dumps(d), encoding="utf-8")
        print("  ⚠️  SYNTHETIC timings written (%d words, %.0fs) — preview only, master will refuse"
              % (len(d["words"]), d["sections"][-1]["end"]))
        return
    missing = [c.name for c in chunks if not c.is_file()]
    if missing:
        die("voice chunks missing: %s — run `tts` first" % ", ".join(missing))
    if not ensure_vosk(install=args.install_deps):
        die("Vosk is not available for alignment (use --install-deps on a runner)", 2)
    offsets = [0.0]
    for c in chunks:
        offsets.append(offsets[-1] + media_duration(c))
    all_words, sections = [], []
    for i, text in enumerate(ep.sections, 1):
        rec = asr_words(chunks[i - 1])
        ws = align_section(i, text, rec)
        for w in ws:
            w["t0"] = round(w["t0"] + offsets[i - 1], 3)
            w["t1"] = round(w["t1"] + offsets[i - 1], 3)
        all_words += ws
        sections.append({"sec": i, "title": ep.section_title(i), "start": round(offsets[i - 1], 2),
                         "end": round(offsets[i], 2), "asr_words": len(rec),
                         "script_words": len(norm_tokens(text))})
        print("  c%d: ASR %3d | script %3d | aligned %3d | %s"
              % (i, len(rec), len(norm_tokens(text)), len(ws), ep.section_title(i)))
    d = {"words": all_words, "sections": sections, "engine": "vosk", "synthetic": False}
    ep.words_path.write_text(json.dumps(d), encoding="utf-8")
    print("  words.json: %d words · %.1f s" % (len(all_words), sections[-1]["end"]))


# ───────────────────────────── render: layers ─────────────────────────────
_plates = {}


def treat_plate(im, size=(2400, 1350)):
    """Any photograph → the brand duotone plate at `size` (the same ramp every plate wears, so a
    fetched picture and a shipped one sit side by side without a seam)."""
    tw, th = size
    im = im.convert("L")
    im = ImageOps.colorize(im, black=(8, 24, 46), white=PLATE_LIGHT).convert("RGB")
    im = ImageEnhance.Contrast(im).enhance(1.05)
    im = ImageEnhance.Brightness(im).enhance(1.14)
    r = max(tw / im.width, th / im.height)
    im = im.resize((math.ceil(im.width * r), math.ceil(im.height * r)), Image.LANCZOS)
    x = (im.width - tw) // 2
    y = (im.height - th) // 2
    return im.crop((x, y, x + tw, y + th))


def plate_for_beat(b):
    """The picture behind a beat: a CC0 photograph that MATCHES the beat's words (owner, 17 Oct
    2026: "make sure it matches what is being said"), else the beat's named plate, else None.

    tools/shot_match.py does the matching — the brain's `shot` hint first, then the glossary
    read of head + sub, every result scored against the query. Cached per beat so a 30 fps
    scene asks once. DOCOGA_SHOTS unset/off keeps the fixed plates (tests, air-gapped runners)."""
    key = ("beat", id(b))
    if key in _plates:
        return _plates[key]
    im = None
    try:
        import shot_match
        if shot_match.enabled():
            said = " ".join(str(b.get(k) or "") for k in ("head", "sub"))
            img, prov = shot_match.photo_for(said, hint=b.get("shot"))
            if img is not None:
                im = treat_plate(img)
                noise = Image.effect_noise(im.size, 16).convert("L")
                im = Image.composite(im, Image.new("RGB", im.size, PLATE_DARK), noise.point(lambda v: 255 - min(42, v // 4)))
                vig = Image.radial_gradient("L").resize(im.size).point(lambda v: min(85, v * 2))
                im = Image.composite(Image.new("RGB", im.size, PLATE_DARK), im, vig)
                print("  📷 beat %r ← %s (%s)" % (str(b.get("head") or "")[:28], prov.get("query"), prov.get("license") or "cc0"))
    except Exception as exc:  # a picture must never cost the episode
        print("  ⚠️  shot lookup failed for %r: %s" % (str(b.get("head") or "")[:28], exc))
    if im is None and b.get("img"):
        im = plate(b["img"])
    _plates[key] = im
    return im


def plate(name):
    """The duotone photographic plate (2400×1350) or a quiet generated one if the asset is absent."""
    if name in _plates:
        return _plates[name]
    tw, th = 2400, 1350
    p = ASSETS / ("%s.jpg" % name)
    if not p.is_file():
        alias_file = ASSETS / "aliases.json"
        aliases = json.loads(alias_file.read_text(encoding="utf-8")) if alias_file.is_file() else {}
        if name in aliases and (ASSETS / ("%s.jpg" % aliases[name])).is_file():
            p = ASSETS / ("%s.jpg" % aliases[name])
    if p.is_file():
        im = treat_plate(Image.open(p), (tw, th))
    else:
        print("  ⚠️  plate '%s' missing (%s) — using a generated glow" % (name, p))
        im = Image.new("RGB", (tw, th), PLATE_DARK)
        glow = Image.radial_gradient("L").resize((tw, th)).point(lambda v: max(0, 120 - v) * 2)
        im = Image.composite(Image.new("RGB", (tw, th), PANEL), im, glow)
    noise = Image.effect_noise((tw, th), 16).convert("L")
    im = Image.composite(im, Image.new("RGB", (tw, th), PLATE_DARK), noise.point(lambda v: 255 - min(42, v // 4)))
    vig = Image.radial_gradient("L").resize((tw, th)).point(lambda v: min(85, v * 2))
    im = Image.composite(Image.new("RGB", (tw, th), PLATE_DARK), im, vig)
    _plates[name] = im
    return im


_LG = None


def left_grad():
    global _LG
    if _LG is None:
        import numpy as np
        x = np.arange(W, dtype=np.float32)
        row = np.clip(235 * (1 - x / 1150), 0, 235).astype(np.uint8)   # 235 at the left edge → 0 at x=1150
        full = Image.fromarray(np.tile(row, (H, 1)), "L")
        _LG = Image.new("RGBA", (W, H), NAVY + (0,))
        _LG.putalpha(full)
    return _LG


_TOP = None


def top_band():
    """A soft dark band behind the kicker and the section label, so they read on bright plates."""
    global _TOP
    if _TOP is None:
        import numpy as np
        y = np.arange(140, dtype=np.float32)
        col = np.clip(170 * (1 - y / 140), 0, 170).astype(np.uint8)
        band = Image.fromarray(np.tile(col[:, None], (1, W)), "L")
        _TOP = Image.new("RGBA", (W, 140), NAVY + (0,))
        _TOP.putalpha(band)
    return _TOP


_WASH = None


def endcard_wash():
    """The end card sits on a near-solid navy wash — the plate is texture, not competition."""
    global _WASH
    if _WASH is None:
        _WASH = Image.new("RGBA", (W, H), NAVY + (222,))
    return _WASH


def base_plate():
    b = Image.new("RGB", (W, H), NAVY)
    ImageDraw.Draw(b).rectangle([0, 0, W, 4], fill=RULE)
    return b


def wrap_fit(text, weight, size, maxw):
    while size > 40:
        f = font(weight, size)
        lines, cur = [], ""
        for wd in text.replace("\n", " \n ").split():
            if wd == "\n":
                if cur:
                    lines.append(cur)
                cur = ""
                continue
            t = (cur + " " + wd).strip()
            if f.getlength(t) <= maxw:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        if all(f.getlength(ln) <= maxw for ln in lines) and len(lines) <= 4:
            return f, lines, size
        size -= 6
    return f, lines, size


def beat_layer(head, sub, accent=YELLOW, head_color=WHITE, center=False, top=False):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    maxw = 1180
    hsz = 108 if top else (148 if len(head) < 26 else 116)
    hf, hlines, hsize = wrap_fit(head, "Black", hsz, maxw)
    sf, slines, _ = wrap_fit(sub, "SemiBold", 42 if top else 46, maxw - 80) if sub else (None, [], 0)
    lh = int(hsize * 1.08)
    sh = 58
    total = 40 + len(hlines) * lh + (14 + len(slines) * sh if slines else 0)
    y = 132 if top else (H - total) // 2 - 30
    x0 = (W - max(hf.getlength(ln) for ln in hlines)) // 2 if center else 150
    d.rectangle([x0, y, x0 + 170, y + 10], fill=accent)
    y += 44
    for ln in hlines:
        x = (W - hf.getlength(ln)) // 2 if center else x0
        d.text((x, y), ln, font=hf, fill=head_color)
        y += lh
    if slines:
        y += 14
        for ln in slines:
            x = (W - sf.getlength(ln)) // 2 if center else x0
            d.text((x, y), ln, font=sf, fill=MUTED)
            y += sh
    return lay


def rows_layer(rows, shown):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    if len(rows) > 4:
        sz, y0, lh = 52, 528, 76
    else:
        sz, y0, lh = 62, 560, 92
    f = font("Bold", sz)
    nf = font("Black", sz)
    vis = rows[:shown]
    panel_h = len(vis) * lh + 36
    d.rectangle([120, y0 - 24, 1800, y0 - 24 + panel_h], fill=GLASS + (200,))
    d.rectangle([120, y0 - 24, 128, y0 - 24 + panel_h], fill=YELLOW)
    y = y0
    for k, r in enumerate(vis, 1):
        d.text((170, y), "%02d" % k, font=nf, fill=YELLOW)
        d.text((320, y), r, font=f, fill=WHITE)
        y += lh
    return lay


def endcard_layer(meta):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    k = font("SemiBold", 40)
    f1 = font("Black", 190)
    f2 = font("Bold", 58)
    f3 = font("SemiBold", 44)
    d.text(((W - k.getlength("D E E P - D I V E")) // 2, 230), "D E E P - D I V E", font=k, fill=MUTED)
    d.text(((W - f1.getlength("DOCOGA")) // 2, 300), "DOCOGA", font=f1, fill=WHITE)
    d.text(((W - f2.getlength("docoga.com.ng")) // 2, 540), "docoga.com.ng", font=f2, fill=YELLOW)
    t = "EVERY DOCUMENT A NIGERIAN NEEDS"
    d.text(((W - f3.getlength(t)) // 2, 640), t, font=f3, fill=MUTED)
    d.rectangle([(W - 240) // 2, 710, (W + 240) // 2, 716], fill=RULE)
    t = "LINK IN THE DESCRIPTION"
    d.text(((W - f3.getlength(t)) // 2, 740), t, font=f3, fill=WHITE)
    t = meta.get("disclaimer", "GENERAL INFORMATION · NOT LEGAL ADVICE · RULES VARY BY STATE AND AGREEMENT")
    d.text(((W - k.getlength(t)) // 2, 850), t, font=k, fill=FAINT)
    return lay


def caption_groups(sw):
    caps, grp = [], []
    f = font("Medium", 40)
    for wi, w in enumerate(sw):
        grp.append(w)
        nxt = sw[wi + 1] if wi + 1 < len(sw) else None
        pause = (nxt["t0"] - w["t1"]) if nxt else 1.0
        if len(grp) >= 8 or (pause > 0.55 and len(grp) >= 4) or nxt is None:
            text = " ".join(x.get("d", x["w"]) for x in grp)
            if f.getlength(text) > 1500 and len(grp) > 5:
                best, bdiff = None, 1e18
                for k in range(3, len(grp) - 2):
                    l1 = " ".join(x.get("d", x["w"]) for x in grp[:k])
                    l2 = " ".join(x.get("d", x["w"]) for x in grp[k:])
                    diff = abs(f.getlength(l1) - f.getlength(l2))
                    if diff < bdiff:
                        best, bdiff = (l1, l2), diff
                lines = list(best)
            else:
                lines = [text]
            caps.append((grp[0]["t0"], grp[-1]["t1"] + 0.25, lines))
            grp = []
    return caps


# ───────────────────────────── render: scene ─────────────────────────────
def seg_cmd(path):
    return [ffmpeg(), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS),
            "-i", "-", "-c:v", "libx264", "-preset", "faster", "-crf", "21", "-pix_fmt", "yuv420p",
            "-vf", "noise=alls=3:allf=t", str(path)]


def scene_timing(ep, n, sw, t0, beats=None, verbose=True):
    """When each beat of scene n fires, and when each numbered row appears.

    One function for the picture AND the sound: the renderer and the cue sheet read the same
    timings, so a whoosh can never land on a different frame than the headline it announces.
    """
    beats = ep.beats(n) if beats is None else beats
    spans, cursor = [], 0
    for b in beats:
        if b["trig"] is None:
            st = t0
        else:
            i = find_idx(sw, b["trig"], cursor)
            if i is None:
                if verbose:
                    print("  ⚠️  scene %d: trigger %r not heard — '%s' snaps to the previous beat + 2.5s"
                          % (n, " ".join(b["trig"]), b["head"]))
                st = (spans[-1][1] + 2.5) if spans else t0
            else:
                st, cursor = sw[i]["t0"], i
        spans.append((b, st))
    row_times = {}
    for b, _ in spans:
        if b["rows"]:
            ts = []
            for rt in b["row_trigs"]:
                i = find_idx(sw, rt, 0)
                ts.append(sw[i]["t0"] if i is not None else None)
            row_times[id(b)] = ts
    return spans, row_times


def plan_cues(ep, d):
    """The episode's sound cue sheet from its word timings. Pure apart from reading `d`."""
    import soundkit
    secs = d["sections"]
    by_sec = {}
    for w in d["words"]:
        by_sec.setdefault(w["sec"], []).append(w)
    all_spans, all_rows = [], {}
    for sec in secs:
        n = sec["sec"]
        spans, rows = scene_timing(ep, n, by_sec.get(n, []), sec["start"], verbose=False)
        all_spans += [(n, b, st) for b, st in spans]
        all_rows.update(rows)
    cfg = {**soundkit.DEFAULTS, **ep.meta.get("audio", {})}
    starts = [sec["start"] for sec in secs]
    return soundkit.cue_sheet(all_spans, all_rows, starts, secs[-1]["end"], cfg), cfg, starts


def render_scene(ep, n, words, secs, by_sec, out_path=None, preview_every=0):
    ep.scene_dir.mkdir(parents=True, exist_ok=True)
    sec = [s for s in secs if s["sec"] == n][0]
    t0, t1 = sec["start"], sec["end"]
    nf = int(round((t1 - t0) * FPS))
    beats = ep.beats(n)
    beat_index = {id(b): k for k, b in enumerate(beats)}
    sw = by_sec.get(n, [])
    caps = caption_groups(sw)

    spans, row_times = scene_timing(ep, n, sw, t0, beats=beats)
    layers = [(b, st, endcard_layer(ep.meta) if b["endcard"] else
               beat_layer(b["head"], b["sub"], b.get("accent") and tuple(b["accent"]) or YELLOW,
                          WHITE, b["center"], top=bool(b["rows"])))
              for b, st in spans]

    kicker_f, label_f, cap_f = font("SemiBold", 30), font("SemiBold", 28), font("Medium", 40)
    kicker = ep.meta.get("kicker", "DOCOGA — DEEP-DIVE")
    total = secs[-1]["end"]
    out_path = Path(out_path) if out_path else ep.scene_dir / ("s%d.mp4" % n)
    proc = subprocess.Popen(seg_cmd(out_path), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    previews = []
    for fi in range(nf):
        t = t0 + fi / FPS
        cur, cur_st, cur_lay = layers[0]
        for b, st, lay in layers:
            if t >= st:
                cur, cur_st, cur_lay = b, st, lay
        frame = base_plate()
        im = plate_for_beat(cur) if (cur["img"] or cur.get("shot")) else None
        if im is not None:
            u = min(1.0, (t - cur_st) / max(0.001, (t1 - cur_st)))
            d = 1 if beat_index[id(cur)] % 2 == 0 else -1
            zw, zh = int(W - 85 * u), int(H - 48 * u)
            px = max(0, min(2400 - zw, int(110 + u * d * 260)))
            py = max(0, min(1350 - zh, int(60 + u * d * 120)))
            frame.paste(im.crop((px, py, px + zw, py + zh)).resize((W, H), Image.BILINEAR), (0, 0))
            frame.paste(NAVY, (0, 0), left_grad())
            frame.paste(NAVY, (0, 0), top_band())
        if cur["endcard"]:
            frame.paste(NAVY, (0, 0), endcard_wash())
        a = max(0, min(255, int(255 * (t - cur_st) / 0.4))) if (cur_st > t0 or cur["trig"]) else 255
        lay = cur_lay
        if a < 255:
            lay = lay.copy()
            lay.putalpha(lay.getchannel("A").point(lambda p: p * a // 255))
        frame.paste(lay, (0, 0), lay)
        if cur["rows"]:
            ts = row_times.get(id(cur), [])
            shown, last_t = 0, t0
            for rt_t in ts:
                if rt_t is not None and rt_t <= t:
                    shown += 1
                    last_t = rt_t
            if shown:
                rlay = rows_layer(cur["rows"], shown)
                ra = max(0, min(255, int(255 * (t - last_t) / 0.35)))
                if ra < 255:
                    rlay.putalpha(rlay.getchannel("A").point(lambda p: p * ra // 255))
                frame.paste(rlay, (0, 0), rlay)
        d = ImageDraw.Draw(frame, "RGBA")
        d.text((70, 52), kicker, font=kicker_f, fill=FAINT)
        lab = "%d \u00B7 %s" % (n, ep.section_title(n).upper())
        d.text((W - 70 - label_f.getlength(lab), 56), lab, font=label_f, fill=FAINT)
        cap = None
        for cg in caps:
            if cg[0] <= t < cg[1]:
                cap = cg
                break
        if cap is None and caps and t >= caps[-1][1]:
            cap = caps[-1]
        if cap is not None:
            lines = cap[2]
            a2 = max(0.0, min(1.0, (t - cap[0]) / 0.18)) * max(0.0, min(1.0, (cap[1] - t) / 0.18 + 1.0))
            bh = 34 + len(lines) * 50
            d.rectangle([W // 2 - 810, 986 - bh, W // 2 + 810, 986], fill=GLASS + (int(205 * a2),))
            for li, ln in enumerate(lines):
                d.text(((W - cap_f.getlength(ln)) / 2, 1002 - bh + 16 + li * 50), ln, font=cap_f,
                       fill=WHITE + (int(255 * a2),))
        d.rectangle([0, H - 6, int(W * t / total), H], fill=YELLOW)
        proc.stdin.write(frame.tobytes())
        if preview_every and fi % preview_every == 0:
            previews.append(frame.copy())
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        die("scene %d: ffmpeg failed" % n)
    return out_path, previews


def stage_render(ep, args):
    d, words, secs, by_sec = ep.load_words()
    targets = range(1, ep.n + 1) if args.scene == "all" else [int(args.scene)]
    for n in targets:
        t_start = time.time()
        p, _ = render_scene(ep, n, words, secs, by_sec)
        print("  scene %d ✅ %s (%.0fs render, %d KB)" % (n, p.name, time.time() - t_start,
                                                        p.stat().st_size // 1024), flush=True)


# ───────────────────────────── stage: master ─────────────────────────────
def stage_master(ep, args):
    d, words, secs, by_sec = ep.load_words()
    if d.get("synthetic") and not args.allow_synthetic:
        die("words.json is SYNTHETIC (pace-estimated) — a master from it would be out of sync with the "
            "voice. Run `align` with real audio, or pass --allow-synthetic for a preview.")
    scenes = [ep.scene_dir / ("s%d.mp4" % n) for n in range(1, ep.n + 1)]
    missing = [s.name for s in scenes if not s.is_file()]
    if missing:
        die("scenes missing: %s" % ", ".join(missing))
    chunks = [ep.chunk(i) for i in range(1, ep.n + 1)]
    if any(not c.is_file() for c in chunks):
        die("voice chunks missing — run `tts`")
    ff = ffmpeg()
    lst = ep.build / "scenes.txt"
    lst.write_text("\n".join("file '%s'" % s for s in scenes), encoding="utf-8")
    video = ep.build / "video.mp4"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(video)],
                   check=True, capture_output=True)
    vlst = ep.build / "voice.txt"
    vlst.write_text("\n".join("file '%s'" % c for c in chunks), encoding="utf-8")
    voice = ep.build / "voice.mp3"
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(vlst), "-c", "copy", str(voice)],
                   check=True, capture_output=True)
    audio_in = voice
    if not args.no_music:
        import soundkit
        cues, cfg, starts = plan_cues(ep, d)
        (ep.build / "cues.json").write_text(json.dumps(cues, indent=1), encoding="utf-8")
        report = soundkit.render_mix(ff, voice, cues, starts, secs[-1]["end"], cfg,
                                     ep.build / "mix.wav", ep.build / "mix_report.json")
        audio_in = ep.build / "mix.wav"
        print("  🎚  bed %s · %d cues · bed %s dB(A) under speech, %s dB(A) under in the gaps · peak %.1f dBFS"
              % ("on" if cfg["bed"] else "off", len(cues),
                 ("%.1f" % report["bed_separation_db"]) if report.get("bed_separation_db") is not None else "—",
                 ("%.1f" % report["bed_gap_separation_db"]) if report.get("bed_gap_separation_db") is not None else "—",
                 report["mix_peak_db"]))
    subprocess.run([ff, "-y", "-i", str(video), "-i", str(audio_in),
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
                    "-movflags", "+faststart", str(ep.master_path)], check=True, capture_output=True)
    print("  ✅ %s (%.1f s, %d MB)%s" % (ep.master_path, media_duration(ep.master_path),
                                         ep.master_path.stat().st_size // (1024 * 1024),
                                         "  ⚠️ SYNTHETIC PREVIEW" if d.get("synthetic") else ""))


# ───────────────────────────── stage: cues ─────────────────────────────
def stage_cues(ep, args):
    """Print the sound cue sheet — every effect, the second it lands, and why."""
    d, words, secs, by_sec = ep.load_words()
    cues, cfg, _ = plan_cues(ep, d)
    print("  bed %s · %d BPM · gaps %.0f dB / under speech %.0f dB vs voice · seed %d"
          % ("on" if cfg["bed"] else "off", cfg["bpm"], cfg["bed_gap_db"], cfg["bed_speech_db"], cfg["seed"]))
    for c in cues:
        m, sec = divmod(c["t"], 60)
        print("  %02d:%06.3f  %-8s %6.1f dB  %s" % (int(m), sec, c["kind"], c["db"], c["why"]))
    kinds = {}
    for c in cues:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print("  %d cues: %s" % (len(cues), ", ".join("%d %s" % (v, k) for k, v in sorted(kinds.items()))))


# ───────────────────────────── stage: cover ─────────────────────────────
def stage_cover(ep, args):
    c = ep.meta["cover"]
    im = Image.new("RGB", (1280, 720), NAVY)
    pl = plate(c.get("img", "kiosk")).crop((480, 135, 480 + 1280, 135 + 720)).resize((700, 720), Image.LANCZOS)
    im.paste(pl, (580, 0))
    im.paste(NAVY, (0, 0), left_grad().resize((1280, 720)))
    d = ImageDraw.Draw(im)
    X = 66
    d.text((X, 52), c["kicker"].upper(), font=font("SemiBold", 36), fill=MUTED)
    f1 = font("Black", 104)
    d.text((X, 96), c["line1"].upper(), font=f1, fill=WHITE)
    tw = d.textlength(c["highlight"].upper(), font=f1)
    d.rectangle([X - 14, 210, X + tw + 26, 210 + 132], fill=YELLOW)
    d.text((X, 216), c["highlight"].upper(), font=f1, fill=NAVY)
    d.text((X, 366), c["label"].upper(), font=font("SemiBold", 36), fill=MUTED)
    d.text((X, 406), c["line2"].upper(), font=font("Black", 84), fill=WHITE)
    d.rectangle([X, 546, X + 180, 554], fill=BLUE)
    d.text((X, 572), c["line3"].upper(), font=font("Bold", 42), fill=WHITE)
    d.text((X, 634), c["sub"], font=font("SemiBold", 30), fill=MUTED)
    d.text((X, 678), "DOCOGA", font=font("Bold", 26), fill=FAINT)
    ep.build.mkdir(parents=True, exist_ok=True)
    im.save(ep.cover_path, quality=92)
    print("  ✅ %s" % ep.cover_path)


# ───────────────────────────── stage: qa ─────────────────────────────
def stage_qa(ep, args):
    fails, warns = [], []
    probs = check_triggers(ep, verbose=False)
    fails += probs
    if not ep.words_path.is_file():
        fails.append("words.json missing")
    else:
        d = json.loads(ep.words_path.read_text(encoding="utf-8"))
        if d.get("synthetic") and not args.allow_synthetic:
            fails.append("words.json is synthetic — not publishable")
        secs = d["sections"]
        total = secs[-1]["end"]
        if not (MIN_EPISODE_SECONDS <= total <= MAX_EPISODE_SECONDS):
            fails.append("episode is %.0fs; a Deep-Dive is %d–%ds" % (total, MIN_EPISODE_SECONDS, MAX_EPISODE_SECONDS))
        for s in secs:
            if s.get("asr_words") is not None and s.get("script_words") and not d.get("synthetic"):
                ratio = s["asr_words"] / max(1, s["script_words"])
                if ratio < 0.6:
                    fails.append("section %d: ASR heard only %d of %d script words — chunk is probably cut or wrong"
                                 % (s["sec"], s["asr_words"], s["script_words"]))
        by_sec = {}
        for w in d["words"]:
            by_sec.setdefault(w["sec"], []).append(w)
        for n in range(1, ep.n + 1):
            sw = by_sec.get(n, [])
            cursor = 0
            for b in ep.beats(n):
                if b["trig"]:
                    i = find_idx(sw, b["trig"], cursor)
                    if i is None:
                        warns.append("section %d: trigger %r not in the aligned words (beat snaps late)"
                                     % (n, " ".join(b["trig"])))
                    else:
                        cursor = i
    if not ep.master_path.is_file():
        fails.append("master missing: %s" % ep.master_path)
    else:
        info = subprocess.run([ffmpeg(), "-i", str(ep.master_path)], capture_output=True, text=True).stderr
        if "1920x1080" not in info:
            fails.append("master is not 1920x1080")
        if "h264" not in info:
            fails.append("master is not H.264")
        if "aac" not in info:
            fails.append("master has no AAC audio")
        dur = media_duration(ep.master_path)
        if ep.words_path.is_file():
            want = json.loads(ep.words_path.read_text(encoding="utf-8"))["sections"][-1]["end"]
            if abs(dur - want) > 2.0:
                fails.append("master is %.1fs but the voice is %.1fs — scenes and audio drifted" % (dur, want))
        if ep.master_path.stat().st_size < 5_000_000:
            fails.append("master is suspiciously small (%d bytes)" % ep.master_path.stat().st_size)
        rep_path = ep.build / "mix_report.json"
        if rep_path.is_file():
            rep = json.loads(rep_path.read_text(encoding="utf-8"))
            sep = rep.get("bed_separation_db")
            if sep is not None and sep < MIN_BED_SEPARATION_DB:
                fails.append("music bed sits only %.1f dB(A) under the voice (need ≥ %d) — it would mask the words"
                             % (sep, MIN_BED_SEPARATION_DB))
            if sep is not None and sep > MAX_BED_SEPARATION_DB:
                fails.append("music bed is %.1f dB(A) under the voice — inaudible on a phone (DD2 run #1 lesson; max %d)"
                             % (sep, MAX_BED_SEPARATION_DB))
            if rep.get("mix_peak_db", 0) > -0.1:
                fails.append("mix clips (peak %.2f dBFS)" % rep["mix_peak_db"])
            if rep.get("cues", 0) < ep.n:
                warns.append("only %d sound cues for %d sections" % (rep.get("cues", 0), ep.n))
            if rep.get("speech_fraction", 1) < 0.5 and not d.get("synthetic"):
                warns.append("narrator speaks for only %.0f%% of the runtime — long silences?"
                             % (100 * rep["speech_fraction"]))
        elif not args.no_music:
            warns.append("no mix_report.json — master was built without the sound kit")
    if not ep.cover_path.is_file():
        fails.append("cover missing")
    for p in fails:
        print("  ❌ " + p)
    for p in warns:
        print("  ⚠️  " + p)
    print("  %s — %d fail, %d warn" % ("QA PASS" if not fails else "QA FAIL", len(fails), len(warns)))
    if fails:
        sys.exit(1)


# ───────────────────────────── stage: meta ─────────────────────────────
def stage_meta(ep, args):
    yt = ep.meta["youtube"]
    desc = yt["description"].rstrip() + "\n\n" + chapters_text(ep)
    more = crosslinks_text()
    if more:
        desc = (desc.rstrip() + "\n\n" + more)[:4900]
    out = {"video_path": str(ep.master_path), "cover_path": str(ep.cover_path),
           "title": yt["title"], "topic": ep.meta["title"], "description": desc,
           "tags": yt.get("tags", "docoga,nigeria,tenant,landlord,tenancy"),
           "category": str(yt.get("category", 27)),
           # the date the episode is meant to go public (episodes/<id>/episode.json → youtube.publish_at,
           # 'YYYY-MM-DD' or an ISO instant, WAT); empty = the slot hour on the day it is published
           "publish_at": str(yt.get("publish_at") or "")}
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as fh:
            for k, v in out.items():
                if "\n" in v:
                    fh.write("%s<<EOF_%s\n%s\nEOF_%s\n" % (k, k, v, k))
                else:
                    fh.write("%s=%s\n" % (k, v))
    for k, v in out.items():
        print("%s=%s" % (k, v.replace("\n", " / ") if k == "description" else v))


def crosslinks_text(limit=3, root=None):
    """'More from DocOga' — the latest public Shorts and the previous Deep-Dives, from the ledgers.

    YouTube's Shorts→long-form "Related video" link is a Studio-only tap (no API, Oct 2026), so
    the description carries the funnel the other way round: a Deep-Dive names the channel's
    recent Shorts and earlier episodes, and the viewer who finished one has the next in reach."""
    root = Path(root) if root else ROOT
    lines = []
    for ledger, label in ((root / "logs" / "youtube_longform.json", "Earlier Deep-Dives"),
                          (root / "logs" / "youtube_published.json", "60-second versions (Shorts)")):
        try:
            rows = json.loads(ledger.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        public = [r for r in rows if isinstance(r, dict) and r.get("privacy") == "public" and r.get("url")]
        public.sort(key=lambda r: str(r.get("date") or ""), reverse=True)
        picked = public[:limit]
        if picked:
            lines.append(label + ":")
            lines += ["%s — %s" % (str(r.get("topic") or r.get("title") or "").split(" #Shorts")[0].strip()[:70], r["url"])
                      for r in picked]
            lines.append("")
    return "\n".join(lines).rstrip()


def chapters_text(ep):
    if not ep.words_path.is_file():
        return ""
    secs = json.loads(ep.words_path.read_text(encoding="utf-8"))["sections"]
    lines = ["Chapters:"]
    for s in secs:
        st = int(s["start"])
        lines.append("%d:%02d %s" % (st // 60, st % 60, s["title"]))
    return "\n".join(lines)


# ───────────────────────────── CLI ─────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(description="DocOga Deep-Dive long-form engine")
    ap.add_argument("episode", help="episode id, e.g. dd2")
    ap.add_argument("stage", choices=["check", "tts", "align", "render", "master", "cues", "cover", "qa", "meta", "env"])
    ap.add_argument("scene", nargs="?", default="all", help="render: scene number or 'all'")
    ap.add_argument("--wait-budget-min", type=int, default=0,
                    help="tts: how long to wait for a quota slot before giving up (exit 5)")
    ap.add_argument("--max-requests", type=int, default=12,
                    help="tts: never make more than N Gemini requests in one run (free-tier guard)")
    ap.add_argument("--no-music", action="store_true", help="master/qa: voice only, no bed or SFX")
    ap.add_argument("--install-deps", action="store_true", help="pip install vosk + download the model")
    ap.add_argument("--no-asr", action="store_true", help="tts: skip the ASR verification/trim")
    ap.add_argument("--synthetic", action="store_true", help="align: pace-estimated timings (preview only)")
    ap.add_argument("--allow-synthetic", action="store_true", help="master/qa: accept synthetic timings")
    ap.add_argument("--seconds-per-section", type=float, default=0,
                    help="align --synthetic: force every section to N seconds (smoke tests)")
    args = ap.parse_args(argv)

    if args.stage == "env":
        probs = ms.check_environment()
        print("  fonts  : %s" % (ms.find_font_template() or "MISSING"))
        print("  ffmpeg : %s" % (ms.find_ffmpeg() or "MISSING"))
        print("  vosk   : %s" % ("ok" if vosk_available() else "missing (needed for tts/align)"))
        print("  gemini : %s" % ("key present" if gemini_key() else "GEMINI_API_KEY missing (needed for tts)"))
        for p in probs:
            print("  ❌ " + p)
        sys.exit(2 if probs else 0)

    ep = Episode(args.episode)
    print("DEEPDIVE · %s — %s · stage %s" % (ep.id, ep.meta["title"], args.stage))
    if args.stage == "check":
        sys.exit(1 if check_triggers(ep) else 0)
    # Only the stages that draw or encode need Inter and ffmpeg. `meta` and `cues` read JSON;
    # the publish job (14 Oct 2026, run #1) died on exactly this check with a finished master
    # banked and nothing uploaded — the environment must not gate stages that don't use it.
    if args.stage in RENDERING_STAGES and ms.check_environment():
        die("; ".join(ms.check_environment()), 2)
    {"tts": stage_tts, "align": stage_align, "render": stage_render, "master": stage_master,
     "cues": stage_cues, "cover": stage_cover, "qa": stage_qa, "meta": stage_meta}[args.stage](ep, args)


if __name__ == "__main__":
    main()
