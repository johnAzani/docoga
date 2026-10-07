#!/usr/bin/env python3
"""
DD3 one-command TTS batch: generate all 9 chunks (Gemini Orus, compact INS),
trim instruction preambles via ASR timestamps, verify each chunk clean.

Quota: 9 requests (10/day bucket). Resumable: skips chunks that already pass verification.

Usage: python3 tools/tts_batch_dd3.py

Reads:  renders/dd3-script.txt
Writes: renders/dd3-c{1..9}.mp3
"""
import json, os, re, subprocess, sys

ROOT = '/home/user/docoga'
FF = f'{ROOT}/tools/bin/ffmpeg'
MODEL = '/tmp/vosk/vosk-model-small-en-us-0.15'
INS = "Narrate this in a natural Nigerian English accent, like a confident Lagos radio presenter:"
BAD = ['narrate', 'narrator', 'narrates', 'accent', 'presenter', 'articulation', 'radio', 'instruction']
FIRST = {
    1: ['clause'],
    2: ['what', 'a', 'tenancy'],
    3: ['clause', 'one'],
    4: ['now', 'the', 'money'],
    5: ['the', 'notice', 'clause'],
    6: ['the', 'repair', 'clause'],
    7: ['now', 'let', 'me'],
    8: ['the', 'renewal', 'trap'],
    9: ['so', 'what', 'do'],
}
SCRIPT_HEAD = {}


def ensure_vosk():
    """Install Vosk ASR engine and model if missing."""
    try:
        from vosk import Model  # noqa
    except ImportError:
        subprocess.run(['pip', 'install', '-q', 'vosk'])
    if not os.path.exists(MODEL):
        os.makedirs('/tmp/vosk', exist_ok=True)
        subprocess.run(['curl', '-sL', '-o', '/tmp/v.zip',
                        'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip'])
        import zipfile
        zipfile.ZipFile('/tmp/v.zip').extractall('/tmp/vosk')
        os.remove('/tmp/v.zip')


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


def script_secs():
    """Load DD3 script sections from renders/dd3-script.txt."""
    global SCRIPT_HEAD
    text = open(f'{ROOT}/renders/dd3-script.txt').read()
    secs = [t.strip() for t in re.split(r'--- C\d+ ---', text)[1:] if t.strip()]
    for i, t in enumerate(secs, 1):
        SCRIPT_HEAD[i] = t.split()[:8]
    return secs


def verify(i, p):
    """Verify a chunk is clean: no preamble leak, starts with script words."""
    w = asr_words(p)
    n = [norm(x['word']) for x in w]
    leak = [b for b in BAD if b in ' '.join(n[:26])]
    sec_words = [norm(x) for x in SCRIPT_HEAD[i]]
    starts_ok = len(n) > 0 and any(x in sec_words for x in n[:6])
    return (not leak) and starts_ok, n[:6], leak


def gen(i, text):
    """Generate TTS for a chunk using Gemini Orus voice."""
    out = f'{ROOT}/renders/dd3-c{i}.mp3'
    r = subprocess.run(['python3', f'{ROOT}/tools/gemini_tts.py', '--model', 'gemini-3.8-flash-tts',
                        '--voice', 'Orus', '--instruction', INS, '--text', text, '--out', out],
                       capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(out)


def trim(i, p):
    """Trim TTS instruction preamble from a chunk using ASR word timestamps."""
    w = asr_words(p)
    n = [norm(x['word']) for x in w]
    target = [norm(t) for t in FIRST[i]]
    sec_words = [norm(x) for x in SCRIPT_HEAD[i]]
    cut = None

    # 1) best anchor: the script's own opening word (+ confirmation nearby)
    if sec_words:
        for k in range(min(len(n) - 3, 30)):
            if n[k] != sec_words[0]:
                continue
            if any(sec_words[j] in n[k+1:k+6] for j in (1, 2, 3)):
                cut = max(0.0, w[k]['start'] - 0.35)
                break

    # 2) legacy FIRST[] anchor
    if cut is None:
        for k in range(len(n) - 2):
            if n[k] != target[0]:
                continue
            if len(target) == 1 or any(t in n[k+1:k+4] for t in target[1:]):
                cut = max(0.0, w[k]['start'] - 0.35)
                break

    # 3) fallback: the preamble always ends with a BAD word — cut just after the last one
    if cut is None:
        last_bad = None
        for k in range(min(26, len(w))):
            if norm(w[k]['word']) in [norm(b) for b in BAD]:
                last_bad = w[k]
        if last_bad is not None:
            cut = last_bad['end'] + 0.12

    if cut is None or cut <= 0.05 or cut > 0.2 * w[-1]['end']:
        return False

    # verify in the ORIGINAL decode (immune to re-encode ASR drift):
    badset = [norm(b) for b in BAD]
    post = [x for x in w if x['start'] >= cut - 0.02][:6]
    leak_left = [x['word'] for x in post if norm(x['word']) in badset]
    match = any(norm(x['word']) in sec_words for x in post[:5]) if sec_words else True
    if leak_left or not match or len(post) < 3:
        return False

    subprocess.run([FF, '-y', '-ss', f'{cut:.2f}', '-i', p, '-c:a', 'libmp3lame',
                    '-b:a', '192k', '-write_xing', '1', '/tmp/dd3t.mp3'], capture_output=True)
    if not (os.path.exists('/tmp/dd3t.mp3') and os.path.getsize('/tmp/dd3t.mp3') > 10000):
        return False

    subprocess.run(['cp', '/tmp/dd3t.mp3', p])  # cross-device safe
    return True


def main():
    ensure_vosk()
    secs = script_secs()
    assert len(secs) == 9, f'Expected 9 sections, got {len(secs)}'

    done = 0
    for i, text in enumerate(secs, 1):
        p = f'{ROOT}/renders/dd3-c{i}.mp3'
        if os.path.exists(p):
            ok, head, leak = verify(i, p)
            if ok:
                print(f'c{i}: already clean ({head[0]}) — skip')
                done += 1
                continue
            print(f'c{i}: exists but fails verify — regenerating')

        if not gen(i, text):
            print(f'c{i}: GENERATION FAILED (quota?) — stopping')
            sys.exit(1)

        ok, head, leak = verify(i, p)
        if ok:
            print(f'c{i}: clean on first pass ({head[0]})')
            done += 1
            continue

        print(f'c{i}: leak {leak} — trimming preamble')
        if trim(i, p):
            print(f'c{i}: trimmed + verified')
            done += 1
        else:
            print(f'c{i}: TRIM FAILED — continuing, will retry next run')

    print(f'BATCH COMPLETE: {done}/9 clean chunks')


if __name__ == '__main__':
    main()