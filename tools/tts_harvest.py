#!/usr/bin/env python3
"""
TTS quota harvester — Law 53 v2.

The 429 body tells us EXACTLY when the next rolling-24h slot frees
("Please retry in Xs"). This driver polls, sleeps only as long as the
API says, and grabs each freed slot the moment it opens.

Targets: every missing DD2/DD3 chunk. Raw (untrimmed) output — the
resumable batches trim + verify afterwards, exactly as if they generated
it themselves. A 429 consumes nothing, so polling is free.

Budget: --minutes N (default 18)

Usage: python3 tools/tts_harvest.py [--minutes 18]
"""
import base64, json, os, re, subprocess, sys, time, urllib.request, urllib.error, wave

ROOT = '/home/user/docoga'
FF = f'{ROOT}/tools/bin/ffmpeg'
API = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-tts:generateContent'
INS = 'Narrate this in a natural Nigerian English accent, like a confident Lagos radio presenter:'
KEY = ''
try:
    KEY = [l.split('=', 1)[1].strip()
           for l in open(f'{ROOT}/.worker-secrets.env')
           if l.startswith('GEMINI_API_KEY=')][0]
except (FileNotFoundError, IndexError):
    print('ERROR: GEMINI_API_KEY not found in .worker-secrets.env')
    sys.exit(1)


def secs(path):
    """Load script sections from a DD script file."""
    text = open(path).read()
    return [s.strip() for s in re.split(r'--- C\d+ ---', text)[1:] if s.strip()]


def targets():
    """Find all missing DD2/DD3 chunks that need TTS generation."""
    t = []
    d2 = secs(f'{ROOT}/renders/dd2-script.txt')
    if len(d2) >= 9 and not os.path.exists(f'{ROOT}/renders/dd2-c9.mp3'):
        t.append(('dd2-c9', d2[8]))
    d3 = secs(f'{ROOT}/renders/dd3-script.txt')
    if len(d3) >= 9:
        for i in range(5, 10):
            if not os.path.exists(f'{ROOT}/renders/dd3-c{i}.mp3'):
                t.append((f'dd3-c{i}', d3[i - 1]))
    return t


def ensure_ff():
    """Ensure ffmpeg is available — re-provision if missing so a landed chunk is never lost."""
    global FF
    if os.path.exists(FF) and os.path.getsize(FF) > 1000000:
        return
    subprocess.run(['pip3', 'install', '-q', '--break-system-packages', 'imageio-ffmpeg'],
                   capture_output=True)
    try:
        src = subprocess.run(['python3', '-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
                             capture_output=True, text=True).stdout.strip()
        os.makedirs(os.path.dirname(FF), exist_ok=True)
        import shutil
        shutil.copy(src, FF)
        os.chmod(FF, 0o755)
    except Exception:
        pass


def call(name, text):
    """
    Call Gemini TTS API for a single chunk.
    Returns ('ok', 0) on success, ('wait', seconds) on 429/quota, ('fail', 0) on error.
    """
    ensure_ff()
    body = {
        'contents': [{'parts': [{'text': INS + ' ' + text}]}],
        'generationConfig': {
            'responseModalities': ['AUDIO'],
            'speechConfig': {
                'voiceConfig': {
                    'prebuiltVoiceConfig': {'voiceName': 'Orus'}
                }
            }
        }
    }
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                headers={'Content-Type': 'application/json',
                                         'x-goog-api-key': KEY})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        m = re.search(r'retry in ([\d.]+)s', raw)
        return ('wait', float(m.group(1)) if m else 45.0)
    except Exception:
        return ('wait', 60.0)  # timeouts / resets / network hiccups — never crash the harvest

    inline = resp['candidates'][0]['content']['parts'][0]['inlineData']
    pcm = base64.b64decode(inline['data'])
    rate = int(inline.get('mimeType', '').split('rate=')[1]) if 'rate=' in inline.get('mimeType', '') else 24000

    out = f'{ROOT}/renders/{name}.mp3'
    with wave.open('/tmp/harvest.wav', 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)

    subprocess.run([FF, '-y', '-i', '/tmp/harvest.wav', '-c:a', 'libmp3lame',
                    '-b:a', '192k', '-write_xing', '1', out], capture_output=True)

    ok = os.path.exists(out) and os.path.getsize(out) > 100000
    if ok:
        # Log to TTS ledger
        try:
            ledger = f'{ROOT}/renders/metrics/tts-ledger.log'
            os.makedirs(os.path.dirname(ledger), exist_ok=True)
            with open(ledger, 'a') as lf:
                lf.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} "
                         f"model=gemini-3.8-flash-tts voice=Orus out={out} pcm={len(pcm)}\n")
        except Exception:
            pass
    return ('ok' if ok else 'fail', 0)


def main():
    budget = 18.0
    if '--minutes' in sys.argv:
        idx = sys.argv.index('--minutes')
        if idx + 1 < len(sys.argv):
            budget = float(sys.argv[idx + 1])

    deadline = time.time() + budget * 60
    todo = targets()
    print(f'harvest targets: {[t[0] for t in todo]}', flush=True)

    if not todo:
        print('no missing chunks — nothing to harvest')
        return

    landed = 0
    while todo and time.time() < deadline:
        name, text = todo[0]
        st, x = call(name, text)
        stamp = time.strftime('%H:%M:%S')
        if st == 'ok':
            print(f'{stamp} LANDED {name}', flush=True)
            todo.pop(0)
            landed += 1
        else:
            print(f'{stamp} quota holds — API says retry in {x:.0f}s', flush=True)
            time.sleep(min(x + 2, 120))

    remaining = ', '.join(t[0] for t in todo) if todo else 'NONE'
    print(f'harvest done: {landed} landed, remaining: {remaining}', flush=True)


if __name__ == '__main__':
    main()