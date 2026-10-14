#!/usr/bin/env python3
"""DocOga sound kit — a synthesized music bed and sound effects, cued from the beats.

Why synthesize instead of downloading "free" music: a track that is CC0 today can be
re-licensed tomorrow, the host can vanish, and a Content ID claim on the channel is a
morning lost. Everything here is built from sine waves and shaped noise by this file,
deterministically (a seed), so it is owned outright, costs ₦0, and renders the same on
every run. The palette is deliberately small and quiet — the voice is the product.

The kit
  bed      a slow navy-mood pad: detuned triads following a four-chord minor progression,
           one chord per section, a soft sub pulse on every second beat (72 BPM)
  riser    1.2 s of filtered noise sweeping up into a section title
  hit      a sub thump + short noise burst on the title beat
  whoosh   250 ms band-passed noise falling in pitch on an ordinary beat change
  tick     a 30 ms blip as each numbered row appears
  stinger  a warm major swell under the end card

Levels are expressed relative to the voice, measured from the voice itself (speech RMS),
so a louder or quieter TTS read never changes the balance. The bed is side-chain ducked:
quieter under speech, swelling in the gaps. The final loudnorm to −16 LUFS happens in
ffmpeg, downstream of this file.
"""

import json
import math
import subprocess
from pathlib import Path

import numpy as np

SR = 48000

DEFAULTS = {
    "bed": True,
    "bpm": 72,
    "seed": 7,
    "bed_gap_db": -18.0,       # bed RMS vs speech RMS, in the gaps between sentences
    "bed_speech_db": -27.0,    # bed RMS vs speech RMS, under speech
    "duck_attack_s": 0.12,
    "duck_release_s": 0.70,
    "sfx_db": -16.0,           # SFX peak vs voice peak
    "hit_db": -13.0,
    "tick_db": -20.0,
    "riser_db": -19.0,
    "stinger_db": -14.0,
    "tail_fade_s": 4.0,        # bed fades to silence over the last N seconds
}

# A minor, four chords, one per section, cycling: i · VI · III · VII  (A F C G)
PROGRESSION = [
    (110.00, 130.81, 164.81),   # A2 C3 E3
    (87.31, 110.00, 130.81),    # F2 A2 C3
    (130.81, 164.81, 196.00),   # C3 E3 G3
    (98.00, 123.47, 146.83),    # G2 B2 D3
]
SUB_HZ = 55.0


def db(x):
    return 10 ** (x / 20.0)


def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if len(x) else 0.0


def to_db(x):
    return 20 * math.log10(max(x, 1e-9))


# ───────────────────────────── primitives ─────────────────────────────
def _env(n, a, r, hold=None):
    """Attack / (hold) / release envelope, all in samples."""
    e = np.ones(n, dtype=np.float32)
    a = min(a, n)
    if a:
        e[:a] = np.linspace(0, 1, a, dtype=np.float32)
    r = min(r, n)
    if r:
        e[n - r:] *= np.linspace(1, 0, r, dtype=np.float32)
    return e


def _bandpass_noise(n, f_lo, f_hi, rng):
    """White noise restricted to [f_lo, f_hi] Hz via the FFT (short clips only)."""
    x = rng.standard_normal(n).astype(np.float32)
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    mask = ((freqs >= f_lo) & (freqs <= f_hi)).astype(np.float32)
    # soft edges so the band does not ring
    edge = max(1, int(len(freqs) * 0.01))
    mask = np.convolve(mask, np.ones(edge) / edge, mode="same")
    return np.fft.irfft(spec * mask, n).astype(np.float32)


def _sweep_noise(n, f0, f1, bw, rng):
    """Noise whose band-pass centre glides from f0 to f1 — the riser and the whoosh."""
    x = rng.standard_normal(n).astype(np.float32)
    # time-varying filter by overlap-add of short band-passed grains
    g = 2048
    out = np.zeros(n + g, dtype=np.float32)
    win = np.hanning(g).astype(np.float32)
    k = 0
    while k < n:
        frac = k / max(1, n)
        fc = f0 * (f1 / f0) ** frac
        seg = x[k:k + g]
        if len(seg) < g:
            seg = np.pad(seg, (0, g - len(seg)))
        spec = np.fft.rfft(seg * win)
        freqs = np.fft.rfftfreq(g, 1 / SR)
        mask = np.exp(-0.5 * ((freqs - fc) / (bw * fc)) ** 2).astype(np.float32)
        out[k:k + g] += np.fft.irfft(spec * mask, g).astype(np.float32)
        k += g // 2
    out = out[:n]
    m = np.max(np.abs(out)) or 1.0
    return out / m


def sfx(kind, rng):
    """One sound effect as float32 at SR, peak-normalised to 1.0."""
    if kind == "riser":
        n = int(1.2 * SR)
        y = _sweep_noise(n, 180, 3200, 0.35, rng) * (np.linspace(0, 1, n, dtype=np.float32) ** 2.2)
    elif kind == "whoosh":
        n = int(0.25 * SR)
        y = _sweep_noise(n, 2400, 500, 0.5, rng) * np.sin(np.linspace(0, math.pi, n)).astype(np.float32) ** 1.5
    elif kind == "hit":
        n = int(0.7 * SR)
        t = np.arange(n) / SR
        sub = np.sin(2 * math.pi * (48 + 20 * np.exp(-t * 12)) * t) * np.exp(-t * 5.5)
        burst = _bandpass_noise(int(0.06 * SR), 300, 2500, rng) * np.exp(-np.arange(int(0.06 * SR)) / SR * 60)
        y = sub.astype(np.float32)
        y[:len(burst)] += 0.55 * burst / (np.max(np.abs(burst)) or 1)
    elif kind == "tick":
        n = int(0.035 * SR)
        t = np.arange(n) / SR
        y = (np.sin(2 * math.pi * 1900 * t) * np.exp(-t * 180)).astype(np.float32)
        y[:12] += np.linspace(0.6, 0, 12, dtype=np.float32)
    elif kind == "stinger":
        n = int(2.8 * SR)
        t = np.arange(n) / SR
        y = np.zeros(n, dtype=np.float32)
        for f, w in ((220.0, 1.0), (277.18, 0.8), (329.63, 0.7), (440.0, 0.5)):   # A major
            for det in (-0.6, 0.6):
                y += w * np.sin(2 * math.pi * (f + det) * t).astype(np.float32)
        y *= _env(n, int(0.9 * SR), int(1.6 * SR))
    else:
        raise ValueError(kind)
    m = float(np.max(np.abs(y))) or 1.0
    return (y / m).astype(np.float32)


def bed(total_s, section_starts, bpm, seed):
    """The pad + pulse for the whole episode. Chord changes at section starts, 2 s crossfade."""
    n = int(total_s * SR)
    t = np.arange(n, dtype=np.float32) / SR
    out = np.zeros(n, dtype=np.float32)
    bounds = list(section_starts) + [total_s]
    xf = 2.0
    for k in range(len(section_starts)):
        s0, s1 = bounds[k], bounds[k + 1]
        chord = PROGRESSION[k % len(PROGRESSION)]
        a = max(0, int((s0 - xf / 2) * SR))
        b = min(n, int((s1 + xf / 2) * SR))
        if b <= a:
            continue
        seg_t = t[a:b]
        seg = np.zeros(b - a, dtype=np.float32)
        for i, f in enumerate(chord):
            w = 1.0 if i == 0 else 0.7
            for det in (-0.35, 0.35):
                seg += w * np.sin(2 * math.pi * (f + det) * seg_t + 0.7 * i)
            seg += 0.18 * w * np.sin(2 * math.pi * (2 * f) * seg_t)      # a little air
        # breathing: slow LFO so the pad never sits still
        seg *= (0.82 + 0.18 * np.sin(2 * math.pi * 0.07 * seg_t + k)).astype(np.float32)
        seg *= _env(b - a, int(xf * SR), int(xf * SR))
        out[a:b] += seg
    out /= (np.max(np.abs(out)) or 1.0)
    # sub pulse every second beat
    beat = 60.0 / bpm
    pulse = np.zeros(n, dtype=np.float32)
    pn = int(0.42 * SR)
    pt = np.arange(pn) / SR
    one = (np.sin(2 * math.pi * SUB_HZ * pt) * np.exp(-pt * 9)).astype(np.float32)
    k = 0.0
    while k < total_s:
        i = int(k * SR)
        j = min(n, i + pn)
        pulse[i:j] += one[:j - i]
        k += 2 * beat
    out = out * 0.85 + pulse * 0.45
    return (out / (np.max(np.abs(out)) or 1.0)).astype(np.float32)


# ───────────────────────────── the voice side ─────────────────────────────
def decode(ffmpeg, path):
    """Any audio file → float32 mono at SR."""
    r = subprocess.run([ffmpeg, "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
                        "-ar", str(SR), "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def speech_mask(voice, attack_s, release_s, block_s=0.01, floor_db=-38.0):
    """1.0 where the narrator is speaking, 0.0 in the gaps, with asymmetric smoothing."""
    nb = int(block_s * SR)
    nblk = len(voice) // nb
    blocks = voice[:nblk * nb].reshape(nblk, nb)
    level = np.sqrt(np.mean(blocks ** 2, axis=1))
    ref = np.percentile(level[level > 0], 90) if np.any(level > 0) else 1.0
    gate = (level > ref * db(floor_db)).astype(np.float32)
    # one-pole follower, fast up / slow down (in blocks)
    ka = math.exp(-block_s / max(attack_s, 1e-3))
    kr = math.exp(-block_s / max(release_s, 1e-3))
    out = np.empty_like(gate)
    y = 0.0
    for i, g in enumerate(gate):
        y = g + (y - g) * (ka if g > y else kr)
        out[i] = y
    full = np.repeat(out, nb)
    if len(full) < len(voice):
        full = np.pad(full, (0, len(voice) - len(full)), constant_values=full[-1] if len(full) else 0)
    return full[:len(voice)], gate


# ───────────────────────────── the cue sheet ─────────────────────────────
def cue_sheet(beat_spans, row_times, section_starts, total_s, cfg):
    """From beat timings to a list of {t, kind, db, why}. Pure; the test suite pins it.

    beat_spans: [(sec, beat_dict, start_s)] in episode order. row_times: {id(beat): [t|None]}.
    """
    cues = []
    first_in_sec = set()
    for sec, b, st in beat_spans:
        if b.get("endcard"):
            cues.append({"t": round(st, 3), "kind": "stinger", "db": cfg["stinger_db"], "why": "end card"})
            continue
        if sec not in first_in_sec:
            first_in_sec.add(sec)
            if st >= 1.3:
                cues.append({"t": round(st - 1.2, 3), "kind": "riser", "db": cfg["riser_db"],
                             "why": "into section %d" % sec})
            cues.append({"t": round(max(0.0, st), 3), "kind": "hit", "db": cfg["hit_db"],
                         "why": "section %d title: %s" % (sec, b["head"])})
        else:
            cues.append({"t": round(max(0.0, st - 0.08), 3), "kind": "whoosh", "db": cfg["sfx_db"],
                         "why": "beat: %s" % b["head"]})
        for rt in row_times.get(id(b), []):
            if rt is not None:
                cues.append({"t": round(rt, 3), "kind": "tick", "db": cfg["tick_db"], "why": "row"})
    cues = [c for c in cues if 0 <= c["t"] < total_s]
    cues.sort(key=lambda c: c["t"])
    return cues


def render_mix(ffmpeg, voice_path, cues, section_starts, total_s, cfg, out_wav, report_path=None):
    """voice + ducked bed + SFX → out_wav (float32 WAV). Returns the mix report dict."""
    cfg = {**DEFAULTS, **(cfg or {})}
    rng = np.random.default_rng(cfg["seed"])
    voice = decode(ffmpeg, voice_path)
    n = int(total_s * SR)
    if len(voice) < n:
        voice = np.pad(voice, (0, n - len(voice)))
    voice = voice[:n]
    mask, gate = speech_mask(voice, cfg["duck_attack_s"], cfg["duck_release_s"])
    speech = voice[np.repeat(gate, int(0.01 * SR))[:n] > 0.5] if np.any(gate) else voice
    v_rms = rms(speech) or 0.1
    v_peak = float(np.max(np.abs(voice))) or 0.5

    mix = voice.copy()
    report = {"voice_speech_rms_db": to_db(v_rms), "voice_peak_db": to_db(v_peak),
              "speech_fraction": float(np.mean(gate)) if len(gate) else 0.0, "cues": len(cues)}

    if cfg["bed"]:
        b = bed(total_s, section_starts, cfg["bpm"], cfg["seed"])[:n]
        b_rms = rms(b) or 1.0
        gap_gain = v_rms * db(cfg["bed_gap_db"]) / b_rms
        sp_gain = v_rms * db(cfg["bed_speech_db"]) / b_rms
        gain = gap_gain + (sp_gain - gap_gain) * mask
        tail = int(cfg["tail_fade_s"] * SR)
        if tail and tail < n:
            gain[n - tail:] *= np.linspace(1, 0, tail, dtype=np.float32)
        gain[:int(1.5 * SR)] *= np.linspace(0, 1, int(1.5 * SR), dtype=np.float32)
        bed_track = b * gain
        mix += bed_track
        under = mask > 0.5
        report.update({
            "bed_under_speech_db": to_db(rms(bed_track[under])) if np.any(under) else None,
            "bed_in_gaps_db": to_db(rms(bed_track[~under])) if np.any(~under) else None,
        })
        report["bed_separation_db"] = (report["voice_speech_rms_db"] - report["bed_under_speech_db"]
                                       if report.get("bed_under_speech_db") is not None else None)

    cache = {}
    for c in cues:
        kind = c["kind"]
        if kind not in cache:
            cache[kind] = sfx(kind, rng)
        s = cache[kind] * (v_peak * db(c["db"]))
        i = int(c["t"] * SR)
        j = min(n, i + len(s))
        if j > i:
            mix[i:j] += s[:j - i]

    peak = float(np.max(np.abs(mix))) or 1.0
    if peak > 0.98:
        mix *= 0.98 / peak
        report["pre_limit_peak_db"] = to_db(peak)
    report["mix_peak_db"] = to_db(float(np.max(np.abs(mix))))
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-c:a", "pcm_s16le", str(out_wav)], input=mix.astype(np.float32).tobytes(), check=True)
    if report_path:
        Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def export_kit(ffmpeg, out_dir, seed=7):
    """Write each effect and 20 s of bed as WAVs, for auditioning the kit by ear."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    for kind in ("riser", "hit", "whoosh", "tick", "stinger"):
        y = sfx(kind, rng) * 0.8
        subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                        str(out_dir / ("%s.wav" % kind))], input=y.tobytes(), check=True)
    y = bed(20.0, [0.0, 10.0], 72, seed) * 0.5
    subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    str(out_dir / "bed-20s.wav")], input=y.tobytes(), check=True)
    return sorted(p.name for p in out_dir.glob("*.wav"))
