#!/usr/bin/env python3
"""
DOCOGA v2.2 final audio mux — DD3 (The Tenancy Agreement: 8 Clauses).

Port of the proven mux_dd2.py — identical chain (Law 24: loudnorm-only, no v2.4 EQ):
voice + soft ducked music bed + CC0 SFX + loudnorm to -16 LUFS.

Usage: python3 tools/mux_dd3.py [--no-music] [--no-sfx]

Reads:  build/dd3-vid/video.mp4, renders/dd3-vo-master.mp3,
        renders/dd3-words.json, renders/music/bed-smooth-meditation.mp3, renders/sfx/*.mp3,
        BEATS from tools/make_longform_dd3.py (sfx timing from word timestamps)
Writes: build/dd3-episode.mp4
"""
import json, os, subprocess, sys

ROOT = '/home/user/docoga'
FF = f'{ROOT}/tools/bin/ffmpeg'

# Self-provision ffmpeg if missing
if not os.path.exists(FF):
    try:
        import imageio_ffmpeg, shutil
        os.makedirs(f'{ROOT}/tools/bin', exist_ok=True)
        shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(), FF)
        os.chmod(FF, 0o755)
    except Exception:
        print('ERROR: ffmpeg not found and imageio_ffmpeg not available')
        sys.exit(1)

VIDEO   = f'{ROOT}/build/dd3-vid/video.mp4'
VO      = f'{ROOT}/renders/dd3-vo-master.mp3'
WORDS   = f'{ROOT}/renders/dd3-words.json'
BED     = f'{ROOT}/renders/music/bed-smooth-meditation.mp3'
SFX_DIR = f'{ROOT}/renders/sfx'
OUT     = f'{ROOT}/build/dd3-episode.mp4'

BED_LEVEL  = os.environ.get('BED_DB', '-27dB')  # pre-duck level; Law 42 default -27
SFX_LEVEL  = '-19dB'     # one-shot effects sit just under the voice
DUCK       = 'threshold=0.03:ratio=6:attack=20:release=500'

# beat visual -> sfx name (fire at beat start) — DD3 beats use the same four mappable visuals
SFX_MAP = {
    'court': 'gavel',
    'letter': 'paper',
    'door': 'knock',
    'clip:money-count': 'money',
}


def sfx_events():
    """Extract SFX timing from DD3 beat triggers + word timestamps."""
    if not os.path.exists(WORDS):
        print('sfx: words.json not built yet (run align first) — skipping sfx')
        return []
    sys.path.insert(0, f'{ROOT}/tools')
    import make_longform_dd3 as eng
    words, secs, by_sec = eng.load()

    def norm(w):
        return ''.join(c for c in w.lower() if c.isalnum() or c == "'")

    events = []
    for b in eng.BEATS:
        sfx = SFX_MAP.get(b['img'])
        if not sfx or not os.path.exists(f'{SFX_DIR}/{sfx}.mp3'):
            continue
        sw = by_sec.get(b['sec'], [])
        if not sw:
            continue
        if b['trig'] is None:
            t = sw[0]['t0']
        else:
            t = sw[0]['t0']
            n = [norm(w['w']) for w in sw]
            tg = [norm(x) for x in b['trig']]
            for i in range(len(n) - len(tg) + 1):
                if n[i:i+len(tg)] == tg:
                    t = sw[i]['t0']
                    break
        events.append((max(0.0, t - 0.15), sfx))

    # cap: at most one sfx per 12 seconds (subtle, alive not noisy)
    events.sort()
    kept, last = [], -99
    for t, n in events:
        if t - last >= 12:
            kept.append((t, n))
            last = t
    return kept


def main():
    music   = '--no-music' not in sys.argv
    sfx_on  = '--no-sfx' not in sys.argv

    for f in (VIDEO, VO):
        if not os.path.exists(f):
            sys.exit(f'missing {f}')

    inputs = ['-i', VIDEO, '-i', VO]
    fc = []
    mix_labels = ['[1:a]']
    idx = 2

    # Music bed: looped, ducked under voice
    if music and os.path.exists(BED):
        inputs += ['-stream_loop', '-1', '-i', BED]
        fc.append(f'[{idx}:a]volume={BED_LEVEL}[bedv]')
        fc.append(f'[bedv][1:a]sidechaincompress={DUCK}[bedd]')
        mix_labels.append('[bedd]')
        idx += 1

    # SFX: one-shots timed to beat triggers
    ev_count = 0
    if sfx_on:
        ev = sfx_events()
        ev_count = len(ev)
        print(f'sfx events: {ev_count}')
        for i, (t, name) in enumerate(ev):
            inputs += ['-i', f'{SFX_DIR}/{name}.mp3']
            ms = int(t * 1000)
            fc.append(f'[{idx}:a]volume={SFX_LEVEL},adelay={ms}|{ms}[s{i}]')
            mix_labels.append(f'[s{i}]')
            idx += 1

    # Mix all audio tracks + loudnorm
    n = len(mix_labels)
    fc.append(f"{''.join(mix_labels)}amix=inputs={n}:duration=first:normalize=0[premix]")
    fc.append('[premix]loudnorm=I=-16:TP=-1.5:LRA=11[aout]')

    cmd = [FF, '-y', *inputs, '-filter_complex', ';'.join(fc),
           '-map', '0:v', '-map', '[aout]', '-c:v', 'copy',
           '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', OUT]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-600:])
        sys.exit(1)

    size = os.path.getsize(OUT) / 1e6

    # Verify loudness
    v = subprocess.run([FF, '-i', OUT, '-af', 'loudnorm=print_format=summary', '-f', 'null', '-'],
                       capture_output=True, text=True)
    for l in v.stderr.split('\n'):
        if 'Input Integrated' in l:
            print('final', l.split('Input Integrated:')[1].strip(), 'LUFS')

    print(f'FINAL: {OUT} ({size:.0f}MB, music={"ON" if music else "OFF"}, sfx={ev_count if sfx_on else 0})')


if __name__ == '__main__':
    main()