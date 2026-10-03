#!/usr/bin/env python3
"""
Trim TTS instruction preambles from DD1 chunks (v2 leak fix).

ASR with timestamps -> locate first script words -> cut everything before -> verify clean.

Usage: python3 tools/trim_dd1.py

Reads:  renders/dd1-c{1..9}.mp3
Writes: overwrites in-place after verification
"""
import json, os, subprocess

FF = '/home/user/docoga/tools/bin/ffmpeg'
ROOT = '/home/user/docoga'
MODEL = '/tmp/vosk/vosk-model-small-en-us-0.15'

# First 4 words of each DD1 section (the script start marker)
FIRST = {
    1: ['it', 'lands', 'without', 'warning'],
    2: ['why', 'is', 'the', 'law'],
    3: ['so', 'how', 'much', 'time'],
    4: ['now', 'the', 'trap', 'that'],
    5: ['for', 'a', 'notice', 'to'],
    6: ['now', 'let', 'me', 'kill'],
    7: ['so', 'the', 'notice', 'is'],
    8: ['self', 'help', 'taking', 'the'],
    9: ['and', 'if', 'you', 'are'],
}

# Words that indicate TTS instruction preamble leaking through
BAD = ['narrate', 'narrator', 'accent', 'presenter', 'articulation',
       'radio', 'instruction', 'voice artist']


def norm(w):
    return ''.join(c for c in w.lower() if c.isalnum())


def asr_words(p):
    """Run Vosk ASR on an audio file and return word-level timestamps."""
    from vosk import Model, KaldiRecognizer
    pcm = subprocess.run([FF, '-i', p, '-ar', '16000', '-ac', '1', '-f', 's16le', '-'],
                         capture_output=True).stdout
    rec = KaldiRecognizer(Model(MODEL), 16000)
    rec.SetWords(True)
    words = []
    for j in range(0, len(pcm), 8000):
        if rec.AcceptWaveform(pcm[j:j+8000]):
            words += json.loads(rec.Result()).get('result', [])
    words += json.loads(rec.FinalResult()).get('result', [])
    return words


def main():
    for i in range(1, 10):
        p = f'{ROOT}/renders/dd1-c{i}.mp3'
        if not os.path.exists(p):
            print(f'c{i}: file not found — skipping')
            continue

        w = asr_words(p)
        n = [norm(x['word']) for x in w]
        target = [norm(x) for x in FIRST[i]]

        # Find where the script starts (fuzzy match: 2 of first 3 words)
        cut = None
        for k in range(len(n) - 2):
            if n[k] != target[0]:
                continue
            m = sum(1 for j in range(3) if n[k+j] == target[j])
            if m >= 2:
                cut = max(0.0, w[k]['start'] - 0.35)
                break

        if cut is None:
            if n[:3] == target[:3]:
                print(f'c{i}: clean start at 0 — no trim needed')
            else:
                print(f'c{i}: WARNING script-start not found; first words: {n[:8]}')
            continue

        if cut <= 0.05:
            print(f'c{i}: clean (starts at 0)')
            continue

        # Trim
        out = f'{ROOT}/renders/dd1-c{i}-t.mp3'
        subprocess.run([FF, '-y', '-ss', f'{cut:.2f}', '-i', p, '-c:a', 'libmp3lame',
                        '-b:a', '192k', '-write_xing', '1', out], capture_output=True)

        # Verify: re-ASR the trimmed file
        v = asr_words(out)
        vn = [norm(x['word']) for x in v]
        leak = [b for b in BAD if b in ' '.join(vn)]
        ok_start = vn[0] == target[0]

        if leak or not ok_start:
            print(f'c{i}: TRIM-VERIFY FAIL leak={leak} starts={vn[:4]}')
            continue

        # Replace original with trimmed version
        os.replace(out, p)
        print(f'c{i}: trimmed {cut:.2f}s preamble — verified clean, starts "{vn[0]}"')


if __name__ == '__main__':
    main()