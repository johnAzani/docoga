#!/usr/bin/env python3
"""
Soundtrack for the Shorts / Reels render — voice-over, music bed, sound effects
===============================================================================

Until 15 Oct 2026 every Short and every Facebook Reel left MotionStudio with an
*empty* audio track (`anullsrc`). The owner, after the first Reel went live:
"there are Reels it used to upload before that have the voice-over, the sound
effects, the background sounds" — and he is right: `tools/make_reels.py` reel 3
had a voice. This module puts sound back, and it does it with parts the repo
already owns and the owner already approved:

  voice   the Deep-Dive narrator — Gemini TTS, **Orus**, the locked instruction
          (`tools/deepdive.py`, fingerprinted; this file never restates it, it
          *imports* it, so the lock tests keep guarding one definition).
  music   `tools/soundkit.py`'s synthesized navy-mood bed — owned outright,
          ₦0, no Content ID — side-chain ducked under the voice at the DD2
          levels the owner called "perfect" (≈16 dB(A) under speech, ≈8 in gaps).
  sfx     the same kit: a hit on the hook, a whoosh into every tip, a tick as
          the check badge pops, a riser into the end card, a stinger under FREE.

Timing is voice-first. Each scene's narration is one TTS clip; the clip's
measured length stretches that scene so the words and the type land together,
instead of a 3.4-second scene cutting a 4-second sentence in half. The reel's
cap is raised to fit (Shorts allow 3 min, Reels 90 s; `HARD_CAP_S` holds it
under both).

Detailed, not points (owner, 17 Oct 2026: "like the long form video"). A slide
may carry `say` — the explanation the narrator actually reads, two to four
sentences — and then the scene is captioned like a Deep-Dive: each sentence
appears under the headline while it is spoken (`caption_beats`, MotionStudio
kind 'caption'), timed by its share of the clip. Without `say` the old read
(headline + sub-line) stands, and nothing is captioned.

Free plan, always — and knowledgeable about it (owner, 15 Oct 2026: "I want to
automatically know when the voice over resets and automatically continue at that
time"). One Short is six requests. `tools/gemini_quota.py` reads every refusal
for *which* bucket tripped: a per-minute refusal is waited out; a per-day
refusal is an appointment at the Pacific midnight. The policy is then:

  SHORTS_VOICE=required (default)  no voice → no publish. If the bucket refills
                                   within VOICE_RESUME_WINDOW_MIN the run sleeps
                                   until then and continues; otherwise it raises
                                   VoiceUnavailable naming the resume time, and
                                   the resumer workflow (narrator_resume.yml)
                                   finishes the job minutes after the reset.
  SHORTS_VOICE=optional            the old behaviour: ship music + SFX, say why.

A silent clip is the one outcome that is never allowed (`assert_not_silent`).
Clips are cached by text hash (`assets/shorts_voice/`, carried between runs and
lanes by `actions/cache`), and `warm` synthesises the day's lines right after
the reset — so the evening publish needs no fresh quota at all.

The output is a JSON report beside the mp4 (`<name>.audio.json`): which lines
were spoken, by whom, the A-weighted separation the mix achieved, and whether
the voice was dropped. The lanes print it; the tests pin it.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import soundkit  # noqa: E402
import gemini_quota  # noqa: E402

SR = soundkit.SR
VOICE_CACHE_DIR = ROOT / "assets" / "shorts_voice"
HARD_CAP_S = 90.0          # Shorts ≤ 3 min, Reels ≤ 90 s, TikTok ≤ 10 min; a detailed Short (owner, 17 Oct
                           # 2026: "detailed, not just points, like the long form") reads 60–80 s
VOICE_LEAD_S = 0.30        # the clip starts after the scene's transition has landed
VOICE_TAIL_S = 0.45        # room after the last word before the next scene cuts
SILENCE_FLOOR_DBFS = -45.0  # a finished soundtrack quieter than this (RMS, dBFS) is "silent"
DEFAULT_WAIT_BUDGET_MIN = 8
VOICE_RESUME_WINDOW_MIN = 20    # a reset this close is waited for in-run (the lane jobs have 30-minute
                                # timeouts); further away → narrator_resume.yml finishes it after the reset


class VoiceUnavailable(RuntimeError):
    """The narrator cannot speak now and the policy says no voice → no publish."""

    def __init__(self, reason, resumes_at=None):
        super().__init__(reason)
        self.reason = reason
        self.resumes_at = resumes_at


def voice_policy():
    """SHORTS_VOICE: required (default) | optional."""
    v = os.environ.get("SHORTS_VOICE", "required").strip().lower()
    return "optional" if v in ("optional", "off", "no", "0", "false", "music") else "required"


def resume_window_min():
    try:
        return float(os.environ.get("VOICE_RESUME_WINDOW_MIN", VOICE_RESUME_WINDOW_MIN))
    except ValueError:
        return float(VOICE_RESUME_WINDOW_MIN)


def _sleep_until(when, log=print, sleep=time.sleep):
    secs = (when - gemini_quota.now_utc()).total_seconds()
    if secs > 0:
        log("  ⏳ the bucket refills at %s — waiting %s in this run, then continuing"
            % (gemini_quota.lagos(when), gemini_quota.human_wait(secs)))
        sleep(secs + 30)

# The Short's sound sits a touch closer than the Deep-Dive's: a 25-second clip on a phone
# in a bus has no quiet passages for the bed to "swell" into, so the bed is a little higher
# under speech and the effects a little brighter. Still measured A-weighted, still under.
MIX_CFG = {
    "bed_speech_db": -15.0,
    "bed_gap_db": -7.0,
    "sfx_db": -11.0,
    "hit_db": -8.0,
    "tick_db": -15.0,
    "riser_db": -13.0,
    "stinger_db": -8.0,
    "tail_fade_s": 1.5,
    "seed": 7,
}


def _deepdive():
    """Lazy: the Deep-Dive module brings PIL + motionstudio with it."""
    import deepdive  # noqa: E402  the locked voice, the TTS call, the key lookup
    return deepdive


# ───────────────────────────── what gets said ─────────────────────────────
def sentence(text):
    """SHOUTED SLIDE TEXT → a sentence the narrator can read.

    "TAKE THE RECEIPT" → "Take the receipt." · "date · amount · reference" →
    "date, amount, reference." Brand and URL spellings are protected."""
    t = " ".join(str(text or "").split())
    if not t:
        return ""
    if t.isupper():
        t = t.lower()
        t = t[0].upper() + t[1:]
        # sentence case after a full stop inside the line
        out, cap = [], False
        for ch in t:
            if cap and ch.isalpha():
                ch = ch.upper()
                cap = False
            if ch in ".!?":
                cap = True
            out.append(ch)
        t = "".join(out)
    t = t.replace(" · ", ", ").replace("·", ",")
    t = t[0].upper() + t[1:]
    t = t.replace("DocOga", "Doc Oga").replace("docoga", "Doc Oga").replace("Docoga", "Doc Oga")
    t = t.replace("Doc Oga.com.ng", "Doc Oga dot com dot N G")
    if t[-1] not in ".!?":
        t += "."
    return t


_SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9₦\"'(])")
SAY_WORDS = (12, 45)       # a `say` shorter than this is a point, longer is a lecture (tools/brain.SAY_WORDS)


def spoken(text):
    """A `say` paragraph as the narrator reads it: whitespace folded, the brand spelled for the
    ear, a full stop at the end. Case is the writer's — this is prose, not a slide."""
    t = " ".join(str(text or "").split())
    if not t:
        return ""
    t = t.replace(" · ", ", ").replace("·", ",")
    t = t.replace("docoga.com.ng", "Doc Oga dot com dot N G").replace("DocOga", "Doc Oga").replace("Docoga", "Doc Oga")
    t = t.replace("Doc Oga.com.ng", "Doc Oga dot com dot N G")
    if t[-1] not in ".!?":
        t += "."
    return t


def sentences(text):
    """Split a read into the sentences the captions will show, one at a time."""
    parts = [p.strip() for p in _SENT_END.split(str(text or "").strip()) if p.strip()]
    return parts or ([str(text).strip()] if str(text or "").strip() else [])


def narration_for(reel, topic):
    """One narration line per scene, in scene order: [{scene, role, text, detailed, sentences}].

    `detailed` is True when the slide carried `say` (the explanation, not the point); the
    captioner only works on detailed scenes."""
    slides = list(topic.get("slides") or [])
    hook, tips, _disc = slides[0], slides[1:-1], slides[-1]
    lines = []

    def line(scene, role, slide, fallback):
        say = spoken(slide.get("say"))
        text = say or fallback
        lines.append({"scene": scene, "role": role, "text": text, "detailed": bool(say),
                      "sentences": sentences(text)})
    # The hook reads from the title (natural case, two sentences) with its sub-line — or its `say`.
    hook_text = sentence(topic.get("title") or hook.get("text"))
    sub = sentence(hook.get("sub"))
    line(reel["scenes"][0]["id"], "hook", hook, (hook_text + " " + sub).strip())
    for sc, tip in zip(reel["scenes"][1:1 + len(tips)], tips):
        line(sc["id"], "tip", tip, (sentence(tip.get("text")) + " " + sentence(tip.get("sub"))).strip())
    lines.append({"scene": reel["scenes"][-1]["id"], "role": "conclusion", "detailed": False,
                  "text": "Free, at Doc Oga dot com dot N G. No signup. General information only."})
    lines[-1]["sentences"] = sentences(lines[-1]["text"])
    return lines


def sync_words(clips, log=print):
    """When each word of each clip is said (tools/wordsync.py): Vosk on the publish lanes, the
    letter-weighted estimate elsewhere. Sets clip["words"] (clip seconds) and clip["wordsync"];
    returns the engine the run used ("vosk" when every clip aligned, else "estimate"). Prints
    the machine line WORDSYNC=<engine> the lane summaries read."""
    import wordsync
    engines = set()
    for c in clips:
        if not c.get("seconds"):
            continue
        words, engine = wordsync.words_for(c.get("path"), c["text"], float(c["seconds"]))
        c["words"], c["wordsync"] = words, engine
        engines.add(engine)
    engine = "vosk" if engines == {"vosk"} else ("estimate" if engines else "none")
    log("WORDSYNC=%s" % engine)
    return engine


def _sentence_times(c, sents, dur):
    """[(t0, t1, words)] per sentence in scene-local seconds. With word times the sentence
    starts where its first word is heard (VOICE_LEAD_S for the first) and hands over at the
    midpoint of the pause before the next; without them, by the sentence's share of the clip's
    characters (the proxy tools/deepdive.py uses before alignment)."""
    import wordsync
    seconds = float(c["seconds"])
    words = c.get("words") or []
    if words and len(words) == len(wordsync.display_words(" ".join(sents))):
        spans = wordsync.sentence_spans(words, sents)
        if all(spans) and len(spans) == len(sents):
            out, t = [], VOICE_LEAD_S
            for i, sp in enumerate(spans):
                if i + 1 < len(spans):
                    t1 = VOICE_LEAD_S + (sp[-1]["t1"] + spans[i + 1][0]["t0"]) / 2
                else:
                    t1 = VOICE_LEAD_S + seconds
                t0, t1 = round(t, 2), round(min(t1, dur - 0.05), 2)
                local = [{"d": w["d"], "t0": round(w["t0"] + VOICE_LEAD_S, 3), "t1": round(w["t1"] + VOICE_LEAD_S, 3)} for w in sp]
                out.append((t0, t1, local))
                t = t1
            return out
    total_chars = sum(len(x) for x in sents) or 1
    out, t = [], VOICE_LEAD_S
    for sent in sents:
        share = len(sent) / total_chars * seconds
        t0, t1 = round(t, 2), round(min(t + share, dur - 0.05), 2)
        out.append((t0, t1, None))
        t += share
    return out


def caption_beats(reel, clips, ms=None):
    """Caption every detailed scene like a Deep-Dive: one MotionStudio 'caption' beat per
    sentence. With word times (sync_words) the beat carries `words` in scene seconds and the
    engine draws it kinetically — phrase by phrase, the word being said lit; without them it is
    the plain timed sentence. The scene's sub-line beat makes way — the captions ARE the
    explanation. Returns the number of captions added. Pure: no rendering."""
    ms = ms or _motionstudio()
    by_scene = {c["scene"]: c for c in clips}
    added = 0
    for sc in reel["scenes"]:
        c = by_scene.get(sc["id"])
        if not c or not c.get("detailed") or not c.get("sentences") or not c.get("seconds"):
            continue
        sents = list(c["sentences"])
        sc["beats"] = [b for b in sc["beats"] if b["kind"] != "support"]
        for sent, (t0, t1, words) in zip(sents, _sentence_times(c, sents, float(sc["dur"]))):
            if t1 - t0 >= 0.6:
                b = ms.Beat("caption", "caption", sent, t0=t0, t1=t1, exempt=True, color=ms.WHITE)
                if words:
                    b["words"] = [w for w in words if w["t0"] < t1]
                sc["beats"].append(b)
                added += 1
    return added


def _motionstudio():
    import motionstudio
    return motionstudio


# ───────────────────────────── voice (locked narrator) ─────────────────────────────
def _cache_path(voice, instruction, text):
    key = hashlib.sha256(("\n".join([voice, instruction, text])).encode("utf-8")).hexdigest()[:20]
    return VOICE_CACHE_DIR / ("%s.mp3" % key)


def _duration(ffmpeg, path):
    return len(soundkit.decode(ffmpeg, path)) / SR


def narrate(lines, log=print, wait_budget_min=None, tts=None, sleep=None):
    """Synthesize every line with the locked narrator. Returns (clips, dropped_reason).

    clips: [{**line, path, seconds}] in order, or [] when the voice is dropped.
    The voice is all-or-nothing: a Short where half the scenes talk is stranger
    than one with music alone. Successful clips stay cached for next time.
    """
    dd = _deepdive()
    ffmpeg = dd.ffmpeg()
    if not dd.gemini_key():
        return [], "no GEMINI_API_KEY — music and effects only"
    voice, instruction = dd.locked_voice()
    tts = tts or dd.gemini_tts
    sleep = sleep or time.sleep
    budget = float(os.environ.get("SHORTS_TTS_WAIT_MIN", wait_budget_min or DEFAULT_WAIT_BUDGET_MIN))
    budget_end = time.time() + 60 * budget
    window_s = 60 * resume_window_min()
    VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    clips = []
    uncached = [l for l in lines if not _cache_path(voice, instruction, l["text"]).is_file()]
    # Known before the first request: is the daily bucket already empty, and does it
    # refill soon enough to wait for? (The ledger remembers the last refusal.)
    st = gemini_quota.state()
    if uncached and st["exhausted"]:
        secs = (st["resumes_at"] - gemini_quota.now_utc()).total_seconds()
        if secs <= window_s and voice_policy() == "required":
            _sleep_until(st["resumes_at"], log, sleep)
        else:
            return [], ("the narrator's daily bucket is empty (%d of %d used) — it refills at %s, in %s"
                        % (st["used"], st["limit_hint"], gemini_quota.lagos(st["resumes_at"]),
                           gemini_quota.human_wait(secs)))
    elif uncached:
        log("  " + gemini_quota.status_line())
    for line in lines:
        p = _cache_path(voice, instruction, line["text"])
        if p.is_file() and p.stat().st_size > 1000:
            clips.append({**line, "path": str(p), "seconds": round(_duration(ffmpeg, p), 2), "cached": True})
            log("  voice %s ✅ cached (%.1fs)" % (line["scene"], clips[-1]["seconds"]))
            continue
        status = "fail"
        for attempt in range(3):
            status, wait = tts(line["text"], voice, instruction, p)
            if status == "ok":
                break
            if status == "wait":
                if time.time() + wait <= budget_end:
                    log("  quota holds — API says retry in %.0fs; waiting (budget %.0f min)" % (wait, budget))
                    sleep(wait + 2)
                    continue
                # Beyond the minute-budget: this is the daily bucket. The ledger now knows
                # exactly when it refills; wait for it if that is near, else name the time.
                st = gemini_quota.state()
                resumes = st["resumes_at"] or gemini_quota.next_reset()
                secs = (resumes - gemini_quota.now_utc()).total_seconds()
                if secs <= window_s and voice_policy() == "required":
                    _sleep_until(resumes, log, sleep)
                    continue
                return [], ("the narrator's daily bucket ran out on scene %s (%d of %d used) — it refills at %s, "
                            "in %s" % (line["scene"], st["used"], st["limit_hint"], gemini_quota.lagos(resumes),
                                       gemini_quota.human_wait(secs)))
            sleep(2)
        if status != "ok" or not p.is_file():
            return [], "Gemini TTS failed on scene %s — music and effects only this run" % line["scene"]
        secs = _duration(ffmpeg, p)
        words = len(line["text"].split())
        # A read that is wildly long for its word count is a preamble ("Sure! Here is…").
        # No ASR in this lane, so the clip is refused by arithmetic and not cached.
        if secs > 1.1 * words + 2.5:
            p.unlink(missing_ok=True)
            return [], ("scene %s read %.1fs for %d words — looks like a preamble; music and effects only" %
                        (line["scene"], secs, words))
        clips.append({**line, "path": str(p), "seconds": round(secs, 2), "cached": False})
        log("  voice %s ✅ %.1fs (%d words)" % (line["scene"], secs, words))
    return clips, ""


# ───────────────────────────── fitting the picture to the words ─────────────────────────────
def fit_scenes(reel, clips):
    """Stretch each scene so its narration fits; raise the cap to match. Returns the new total."""
    by_scene = {c["scene"]: c for c in clips}
    for sc in reel["scenes"]:
        c = by_scene.get(sc["id"])
        if not c:
            continue
        need = round(VOICE_LEAD_S + c["seconds"] + VOICE_TAIL_S, 2)
        if need > sc["dur"]:
            sc["dur"] = need
    total = round(sum(sc["dur"] for sc in reel["scenes"]), 2)
    if total > HARD_CAP_S:
        raise RuntimeError("narration makes this reel %.1fs; the hard cap is %.0fs — shorten the copy"
                           % (total, HARD_CAP_S))
    # The engine trims scenes back to the *reading* time when a reel is over its cap, and
    # reading time knows nothing about the voice. With narration the only cap is the hard one.
    reel["cap"] = HARD_CAP_S
    return total


def scene_starts(reel):
    starts, t = [], 0.0
    for sc in reel["scenes"]:
        starts.append(round(t, 3))
        t += float(sc["dur"])
    return starts, round(t, 3)


def cue_sheet(reel, cfg=None):
    """SFX cues from the scene list — pure, so the tests can pin it."""
    cfg = {**soundkit.DEFAULTS, **MIX_CFG, **(cfg or {})}
    starts, total = scene_starts(reel)
    cues = []
    for sc, st in zip(reel["scenes"], starts):
        role = sc.get("role")
        if role == "hook":
            cues.append({"t": round(st + 0.05, 3), "kind": "hit", "db": cfg["hit_db"], "why": "hook lands"})
        elif role == "conclusion":
            if st >= 1.3:
                cues.append({"t": round(st - 1.2, 3), "kind": "riser", "db": cfg["riser_db"], "why": "into FREE."})
            cues.append({"t": round(st + 0.05, 3), "kind": "stinger", "db": cfg["stinger_db"], "why": "FREE."})
        else:
            cues.append({"t": round(max(0.0, st - 0.08), 3), "kind": "whoosh", "db": cfg["sfx_db"],
                         "why": "into tip %s" % sc["id"]})
            cues.append({"t": round(st + 0.22, 3), "kind": "tick", "db": cfg["tick_db"], "why": "check badge"})
    cues = [c for c in cues if 0 <= c["t"] < total]
    cues.sort(key=lambda c: c["t"])
    return cues


# ───────────────────────────── the mix ─────────────────────────────
def _voice_track(ffmpeg, reel, clips, total):
    """All clips placed at their scene start + lead, as one float32 mono buffer."""
    n = int(total * SR)
    track = np.zeros(n, dtype=np.float32)
    starts, _ = scene_starts(reel)
    at = dict(zip((sc["id"] for sc in reel["scenes"]), starts))
    for c in clips:
        y = soundkit.decode(ffmpeg, c["path"])
        i = int((at[c["scene"]] + VOICE_LEAD_S) * SR)
        j = min(n, i + len(y))
        if j > i:
            track[i:j] += y[:j - i]
    return track


def _write_wav(ffmpeg, buf, path):
    subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-c:a", "pcm_s16le", str(path)], input=buf.astype(np.float32).tobytes(), check=True)


def _music_only_mix(reel, cues, total, cfg):
    """No narrator: bed + SFX at a nominal level (loudnorm downstream sets the loudness)."""
    rng = np.random.default_rng(cfg["seed"])
    starts, _ = scene_starts(reel)
    n = int(total * SR)
    b = soundkit.bed(total, starts, cfg["bpm"], cfg["seed"])[:n]
    mix = b * 0.45
    fade_in = int(1.0 * SR)
    mix[:fade_in] *= np.linspace(0, 1, fade_in, dtype=np.float32)
    tail = int(cfg["tail_fade_s"] * SR)
    if tail < n:
        mix[n - tail:] *= np.linspace(1, 0, tail, dtype=np.float32)
    cache = {}
    for c in cues:
        if c["kind"] not in cache:
            cache[c["kind"]] = soundkit.sfx(c["kind"], rng)
        w = cache[c["kind"]] * (0.8 * soundkit.db(c["db"] + 6))
        i = int(c["t"] * SR)
        j = min(n, i + len(w))
        if j > i:
            mix[i:j] += w[:j - i]
    peak = float(np.max(np.abs(mix))) or 1.0
    if peak > 0.98:
        mix *= 0.98 / peak
    return mix.astype(np.float32), {"weighting": "A", "mode": "music_only", "cues": len(cues),
                                    "mix_peak_db": soundkit.to_db(float(np.max(np.abs(mix))))}


def track_level_dbfs(buf):
    """Whole-track RMS in dBFS. (soundkit's A-weighted gauge is a *relative* scale, used for
    voice-vs-bed separation; an absolute silence test needs an absolute unit.)"""
    return soundkit.to_db(soundkit.rms(buf)) if len(buf) else -120.0


def assert_not_silent(ffmpeg, video_path):
    """The one hard rule: nothing silent leaves this module."""
    y = soundkit.decode(ffmpeg, video_path)
    level = track_level_dbfs(y)
    if level < SILENCE_FLOOR_DBFS:
        raise RuntimeError("the soundtrack is silent (%.1f dBFS) — refusing to ship it" % level)
    return level


def mux(ffmpeg, video_in, audio_wav, video_out):
    """Replace the render's empty track with the mix; loudness-normalised for phones."""
    cmd = [ffmpeg, "-loglevel", "error", "-y", "-i", str(video_in), "-i", str(audio_wav),
           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
           "-shortest", "-movflags", "+faststart", str(video_out)]
    subprocess.run(cmd, check=True)


def score(reel, clips, video_path, log=print, dropped_reason="", report_path=None):
    """Mix voice + bed + SFX for the *final* reel timings and mux it into video_path in place."""
    dd = _deepdive()
    ffmpeg = dd.ffmpeg()
    video_path = Path(video_path)
    cfg = {**soundkit.DEFAULTS, **MIX_CFG}
    starts, total = scene_starts(reel)
    cues = cue_sheet(reel, cfg)
    with tempfile.TemporaryDirectory(prefix="shorts-sound-") as tmp:
        tmp = Path(tmp)
        mix_wav = tmp / "mix.wav"
        if clips:
            voice_wav = tmp / "voice.wav"
            _write_wav(ffmpeg, _voice_track(ffmpeg, reel, clips, total), voice_wav)
            report = soundkit.render_mix(ffmpeg, voice_wav, cues, starts, total, cfg, mix_wav)
            report["mode"] = "voice"
        else:
            mix, report = _music_only_mix(reel, cues, total, cfg)
            _write_wav(ffmpeg, mix, mix_wav)
        out = tmp / "scored.mp4"
        mux(ffmpeg, video_path, mix_wav, out)
        level = assert_not_silent(ffmpeg, out)
        out.replace(video_path)
    report.update({
        "voice": (dd.LOCKED_VOICE_NAME if clips else None),
        "voice_dropped": (not clips),
        "voice_dropped_reason": dropped_reason or None,
        "lines": [{k: c[k] for k in ("scene", "role", "text", "seconds")} for c in clips],
        "scene_starts": starts,
        "total_s": total,
        "track_level_dbfs": round(level, 1),
        "cue_sheet": cues,
    })
    report_path = Path(report_path) if report_path else video_path.with_suffix(".audio.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log("  soundtrack: %s · %d cues · %.1fs · track %.1f dBFS%s"
        % ("voice " + report["voice"] if clips else "music + SFX (no voice)", len(cues), total, level,
           (" · bed %.0f dB(A) under speech" % report["bed_separation_db"])
           if report.get("bed_separation_db") is not None else ""))
    if dropped_reason:
        log("  ⚠️  voice dropped: " + dropped_reason)
    return report


def summary_line(video_path):
    """One line for a run summary, read back from the report beside the mp4."""
    rp = Path(video_path).with_suffix(".audio.json")
    if not rp.is_file():
        return "silent (no soundtrack report)"
    try:
        r = json.loads(rp.read_text(encoding="utf-8"))
    except ValueError:
        return "unreadable soundtrack report"
    if r.get("voice"):
        sep = r.get("bed_separation_db")
        return "voice %s · %d lines · bed %s · %d cues" % (
            r["voice"], len(r.get("lines") or []),
            ("%.0f dB(A) under speech" % sep) if sep is not None else "n/a", len(r.get("cue_sheet") or []))
    return "music + SFX, no voice (%s)" % (r.get("voice_dropped_reason") or "dropped")


def resumes_at():
    """When the narrator can speak again (None when nothing says it cannot)."""
    return gemini_quota.state()["resumes_at"]


def require_voice(clips, dropped, log=print):
    """Apply the policy after narrate(): raise VoiceUnavailable when required and absent."""
    if clips or voice_policy() != "required":
        return
    when = resumes_at()
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as fh:
            fh.write("voice=unavailable\n")
            fh.write("voice_reason=%s\n" % dropped.replace("\n", " "))
            fh.write("voice_resumes_at=%s\n" % (gemini_quota.lagos(when) if when else ""))
    log("  ⛔ voice required (SHORTS_VOICE=required) and unavailable: " + dropped)
    raise VoiceUnavailable(dropped, when)


def warm(day=None, log=print, tts=None):
    """Synthesize and cache the day's lines without rendering. Returns (clips, dropped)."""
    import shorts_reel
    from datetime import datetime
    from zoneinfo import ZoneInfo
    day = day or datetime.now(ZoneInfo("Africa/Lagos")).date()
    topic = shorts_reel.topic_for(day)
    reel = shorts_reel.reel_from_topic(topic, "/tmp/_warm.mp4")
    lines = narration_for(reel, topic)
    log("warming the narrator's cache for %s — %s (%d lines)" % (day.isoformat(), topic["title"], len(lines)))
    clips, dropped = narrate(lines, log=log, tts=tts)
    if clips:
        log("  ✅ %d lines ready (%d freshly synthesised) · %s"
            % (len(clips), sum(1 for c in clips if not c.get("cached")), gemini_quota.status_line()))
    else:
        log("  ⚠️  " + dropped)
    return clips, dropped


def main(argv=None):
    import argparse
    from datetime import date
    ap = argparse.ArgumentParser(description="Shorts/Reels soundtrack utilities")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("warm", help="synthesise and cache today's narration (no render)")
    w.add_argument("--date")
    sub.add_parser("status", help="the narrator's bucket, as the ledger knows it")
    args = ap.parse_args(argv)
    if args.cmd == "status":
        print(gemini_quota.status_line())
        return 0
    clips, dropped = warm(date.fromisoformat(args.date) if args.date else None)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("- narrator warm-up: %s\n- %s\n" % (
                ("✅ %d lines cached" % len(clips)) if clips else "⚠️ " + dropped, gemini_quota.status_line()))
    return 0 if clips else 1


if __name__ == "__main__":
    sys.exit(main())
