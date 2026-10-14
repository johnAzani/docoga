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

Levels are expressed relative to the voice, measured from the voice itself, so a louder or
quieter TTS read never changes the balance. The bed is side-chain ducked: quieter under
speech, swelling in the gaps. The final loudnorm to −16 LUFS happens in ffmpeg, downstream.

Lesson from DD2 run #1 (14 Oct 2026, owner: "I did not hear background music"): the first
bed lived at 55–165 Hz and sat 27 dB under the voice by raw power. Phone speakers do not
reproduce much below ~200 Hz and raw power over-counts low notes, so the gauge said
"healthy" while the ear heard nothing. Now: the bed's body is in the 220–880 Hz band, the
levels are broadcast-documentary (≈16 dB under speech, ≈8 dB in gaps), and every level in
this file — targets and the QA gate — is measured **A-weighted**, i.e. as ears hear it.
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
    "bed_gap_db": -8.0,        # bed vs speech, A-weighted, in the gaps between sentences
    "bed_speech_db": -16.0,    # bed vs speech, A-weighted, under speech
    "duck_attack_s": 0.12,
    "duck_release_s": 0.70,
    "sfx_db": -12.0,           # SFX peak vs voice peak
    "hit_db": -9.0,
    "tick_db": -16.0,
    "riser_db": -14.0,
    "stinger_db": -9.0,
    "tail_fade_s": 4.0,        # bed fades to silence over the last N seconds
}

# A minor, four chords, one per section, cycling: i · VI · III · VII  (A F C G).
# Voiced where phones can play it: pad triads around A3–A4, pluck arpeggio A4–E5, a soft
# bass root an octave down, a sub pulse underneath as support only.
PROGRESSION = [
    (220.00, 261.63, 329.63, 440.00),   # A3 C4 E4 A4
    (174.61, 220.00, 261.63, 349.23),   # F3 A3 C4 F4
    (261.63, 329.63, 392.00, 523.25),   # C4 E4 G4 C5
    (196.00, 246.94, 293.66, 392.00),   # G3 B3 D4 G4
]
SUB_HZ = 55.0


def a_weight_gain(freqs):
    """IEC 61672 A-weighting as linear gain per frequency — what the ear does to a spectrum."""
    f2 = np.square(freqs.astype(np.float64)) + 1e-9
    ra = (12194.0 ** 2 * f2 ** 2) / ((f2 + 20.6 ** 2) * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194.0 ** 2))
    return (ra * 10 ** (2.0 / 20)).astype(np.float32)


def a_weighted_block_rms(x, block=4800):
    """A-weighted RMS per 100 ms block (at SR). Returns float64 array of linear RMS values."""
    nblk = len(x) // block
    if nblk == 0:
        return np.zeros(0)
    blocks = x[:nblk * block].reshape(nblk, block).astype(np.float32)
    win = np.hanning(block).astype(np.float32)
    spec = np.fft.rfft(blocks * win, axis=1)
    w = a_weight_gain(np.fft.rfftfreq(block, 1 / SR))
    power = np.mean(np.abs(spec * w) ** 2, axis=1) / (np.mean(win ** 2) * block / 2)
    return np.sqrt(power / block)


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
    """The pad + pluck arpeggio + bass + sub pulse for the whole episode.

    Chord changes at section starts with a 2 s crossfade; the arpeggio walks the chord tones
    on every beat so the bed moves instead of droning. Peak-normalised to 1.0.
    """
    n = int(total_s * SR)
    t = np.arange(n, dtype=np.float32) / SR
    pad = np.zeros(n, dtype=np.float32)
    bass = np.zeros(n, dtype=np.float32)
    bounds = list(section_starts) + [total_s]
    xf = 2.0
    chord_at = []                      # (start_sample, end_sample, chord) for the arpeggio
    for k in range(len(section_starts)):
        s0, s1 = bounds[k], bounds[k + 1]
        chord = PROGRESSION[k % len(PROGRESSION)]
        a = max(0, int((s0 - xf / 2) * SR))
        b = min(n, int((s1 + xf / 2) * SR))
        if b <= a:
            continue
        chord_at.append((int(s0 * SR), int(s1 * SR), chord))
        seg_t = t[a:b]
        seg = np.zeros(b - a, dtype=np.float32)
        for i, f in enumerate(chord):
            w = (1.0, 0.8, 0.8, 0.55)[i]
            for det in (-0.7, 0.7):                                   # gentle chorus
                seg += w * np.sin(2 * math.pi * (f + det) * seg_t + 0.9 * i)
            seg += 0.22 * w * np.sin(2 * math.pi * (2 * f) * seg_t)   # a little air an octave up
        seg *= (0.80 + 0.20 * np.sin(2 * math.pi * 0.06 * seg_t + k)).astype(np.float32)   # breathing
        env = _env(b - a, int(xf * SR), int(xf * SR))
        pad[a:b] += seg * env
        root = chord[0] / 2.0                                          # bass an octave down
        bass[a:b] += (np.sin(2 * math.pi * root * seg_t) + 0.3 * np.sin(2 * math.pi * 2 * root * seg_t)) * env
    pad /= (np.max(np.abs(pad)) or 1.0)
    bass /= (np.max(np.abs(bass)) or 1.0)

    # pluck arpeggio: one chord tone per beat, an octave above the pad, 0.55 s decay
    beat = 60.0 / bpm
    pluck = np.zeros(n, dtype=np.float32)
    pn = int(0.55 * SR)
    pt = np.arange(pn) / SR
    decay = np.exp(-pt * 6.0).astype(np.float32)
    order = (0, 2, 1, 3, 2, 0, 3, 1)
    k = 0
    tt = 0.0
    while tt < total_s:
        i = int(tt * SR)
        chord = next((c for a0, b0, c in chord_at if a0 <= i < b0), PROGRESSION[0])
        f = chord[order[k % len(order)]] * 2.0
        tone = (np.sin(2 * math.pi * f * pt) + 0.35 * np.sin(2 * math.pi * 2 * f * pt)
                + 0.12 * np.sin(2 * math.pi * 3 * f * pt)) * decay
        tone[:int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR), dtype=np.float32)
        j = min(n, i + pn)
        pluck[i:j] += tone[:j - i] * (0.9 if k % 2 == 0 else 0.7)
        k += 1
        tt += beat
    pluck /= (np.max(np.abs(pluck)) or 1.0)

    # shimmer: a very soft fifth two octaves up with slow tremolo, so the top end is alive
    shimmer = np.zeros(n, dtype=np.float32)
    for a0, b0, chord in chord_at:
        a = max(0, a0 - int(SR)); b = min(n, b0 + int(SR))
        seg_t = t[a:b]
        shimmer[a:b] += np.sin(2 * math.pi * chord[2] * 2 * seg_t) * (0.5 + 0.5 * np.sin(2 * math.pi * 0.25 * seg_t)) \
            * _env(b - a, int(SR), int(SR))
    shimmer /= (np.max(np.abs(shimmer)) or 1.0)

    # sub pulse every second beat — support, not body
    pulse = np.zeros(n, dtype=np.float32)
    sn = int(0.42 * SR)
    st = np.arange(sn) / SR
    one = (np.sin(2 * math.pi * SUB_HZ * st) * np.exp(-st * 9)).astype(np.float32)
    tt = 0.0
    while tt < total_s:
        i = int(tt * SR); j = min(n, i + sn)
        pulse[i:j] += one[:j - i]
        tt += 2 * beat
    out = pad * 0.70 + pluck * 0.55 + bass * 0.22 + shimmer * 0.10 + pulse * 0.15
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
    """voice + ducked bed + SFX → out_wav (16-bit WAV). Returns the mix report dict.

    Every level here is A-weighted: the bed's gain is set so that its A-weighted level sits
    `bed_speech_db` under the narrator's A-weighted speech level while he talks and
    `bed_gap_db` under it in the gaps; the report measures the result the same way.
    """
    cfg = {**DEFAULTS, **(cfg or {})}
    rng = np.random.default_rng(cfg["seed"])
    voice = decode(ffmpeg, voice_path)
    n = int(total_s * SR)
    if len(voice) < n:
        voice = np.pad(voice, (0, n - len(voice)))
    voice = voice[:n]
    mask, gate = speech_mask(voice, cfg["duck_attack_s"], cfg["duck_release_s"])
    v_peak = float(np.max(np.abs(voice))) or 0.5

    # A-weighted levels per 100 ms block; a block is "speech" when the duck mask says so
    BLOCK = 4800
    v_blk = a_weighted_block_rms(voice, BLOCK)
    nb = len(v_blk)
    m_blk = mask[:nb * BLOCK].reshape(nb, BLOCK).mean(axis=1) if nb else np.zeros(0)
    speech_blocks = m_blk > 0.5
    v_speech_dba = to_db(float(np.sqrt(np.mean(v_blk[speech_blocks] ** 2)))) if np.any(speech_blocks) \
        else to_db(float(np.sqrt(np.mean(v_blk ** 2))) if nb else 0.1)

    mix = voice.copy()
    report = {"weighting": "A", "voice_speech_dba": v_speech_dba, "voice_peak_db": to_db(v_peak),
              "speech_fraction": float(np.mean(gate)) if len(gate) else 0.0, "cues": len(cues)}

    if cfg["bed"]:
        b = bed(total_s, section_starts, cfg["bpm"], cfg["seed"])[:n]
        b_dba = to_db(float(np.sqrt(np.mean(a_weighted_block_rms(b, BLOCK) ** 2))) or 1e-6)
        gap_gain = db(v_speech_dba + cfg["bed_gap_db"] - b_dba)
        sp_gain = db(v_speech_dba + cfg["bed_speech_db"] - b_dba)
        gain = gap_gain + (sp_gain - gap_gain) * mask
        tail = int(cfg["tail_fade_s"] * SR)
        if tail and tail < n:
            gain[n - tail:] *= np.linspace(1, 0, tail, dtype=np.float32)
        gain[:int(1.5 * SR)] *= np.linspace(0, 1, int(1.5 * SR), dtype=np.float32)
        bed_track = (b * gain).astype(np.float32)
        mix += bed_track
        bt_blk = a_weighted_block_rms(bed_track, BLOCK)
        under = speech_blocks
        bed_speech = to_db(float(np.sqrt(np.mean(bt_blk[under] ** 2)))) if np.any(under) else None
        bed_gap = to_db(float(np.sqrt(np.mean(bt_blk[~under] ** 2)))) if np.any(~under) else None
        report.update({"bed_under_speech_dba": bed_speech, "bed_in_gaps_dba": bed_gap,
                       "bed_separation_db": (v_speech_dba - bed_speech) if bed_speech is not None else None,
                       "bed_gap_separation_db": (v_speech_dba - bed_gap) if bed_gap is not None else None,
                       "bed_gain_db_under_speech": to_db(float(sp_gain)), "bed_gain_db_in_gaps": to_db(float(gap_gain))})

    cache = {}
    for c in cues:
        kind = c["kind"]
        if kind not in cache:
            cache[kind] = sfx(kind, rng)
        sfx_wave = cache[kind] * (v_peak * db(c["db"]))
        i = int(c["t"] * SR)
        j = min(n, i + len(sfx_wave))
        if j > i:
            mix[i:j] += sfx_wave[:j - i]

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
