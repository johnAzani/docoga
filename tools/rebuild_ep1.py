#!/usr/bin/env python3
"""
Unattended Episode-1 rebuild (v2 voice + v2 visuals).

Flow: ensure deps -> wait for TTS quota reset -> regen 9 chunks (ASR-gated,
fallback models) -> master -> re-align -> update meta chapters -> render all
+ cover -> QC -> upload -> verify -> swap announcement queue -> status file.

Usage: python3 tools/rebuild_ep1.py [--skip-tts]

The --skip-tts flag skips TTS generation (uses existing clean chunks).
Status written to build/REBUILD-STATUS.json after each stage.
"""
import json, os, re, subprocess, sys, time, datetime, urllib.request

ROOT = '/home/user/docoga'
FF = f'{ROOT}/tools/bin/ffmpeg'
INS = "Narrate this in a natural Nigerian English accent, like a confident Lagos radio presenter:"
BAD = ['narrate', 'accent', 'presenter', 'articulation', 'radio', 'instruction', 'voice artist']
MODELS = ['gemini-3.8-flash-tts', 'gemini-3.1-flash-tts-preview', 'gemini-2.5-flash-preview-tts']
OLD_VID = 'd6ra8tw0AQg'
STATUS = {'steps': []}


def get_admin_key():
    """Get admin key from env or secrets file — never hardcoded."""
    key = os.environ.get('ADMIN_KEY', '')
    if key:
        return key
    try:
        for line in open(f'{ROOT}/.worker-secrets.env'):
            if line.startswith('ADMIN_PASSCODE='):
                return line.split('=', 1)[1].strip()
    except FileNotFoundError:
        pass
    sys.exit('ADMIN_KEY not found in env or .worker-secrets.env')


def log(m):
    line = f"[{datetime.datetime.utcnow().strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    STATUS['steps'].append(line)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ensure_deps():
    """Install all dependencies: vosk, mutagen, ffmpeg, vosk model, video clips."""
    for mod in ['vosk', 'mutagen']:
        r = run(['python3', '-c', f'import {mod}'])
        if r.returncode:
            run(['pip', 'install', '-q', mod])

    if not os.path.exists(FF):
        run(['pip', 'install', '-q', 'imageio-ffmpeg'])
        src = run(['python3', '-c',
                   'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())']).stdout.strip()
        os.makedirs(f'{ROOT}/tools/bin', exist_ok=True)
        import shutil
        shutil.copy(src, FF)
        os.chmod(FF, 0o755)

    if not os.path.isdir('/tmp/vosk/vosk-model-small-en-us-0.15'):
        os.makedirs('/tmp/vosk', exist_ok=True)
        run(['curl', '-sL',
             'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip',
             '-o', '/tmp/vosk/m.zip'])
        run(['python3', '-c',
             "import zipfile;zipfile.ZipFile('/tmp/vosk/m.zip').extractall('/tmp/vosk')"])
        os.remove('/tmp/vosk/m.zip')

    if not os.path.isdir(f'{ROOT}/build/clips-graded') or \
       not os.listdir(f'{ROOT}/build/clips-graded'):
        log('clips missing — re-fetching from manifest')
        _fetch_clips()

    log('deps ready')


def _fetch_clips():
    """Fetch and grade video clips from manifest."""
    os.makedirs(f'{ROOT}/build/clips-raw', exist_ok=True)
    os.makedirs(f'{ROOT}/build/clips-graded', exist_ok=True)
    UA = 'Mozilla/5.0 (Linux; Android 12) Chrome/124.0 Mobile Safari/537.36'
    procs = []
    manifest = f'{ROOT}/renders/clips/MANIFEST.txt'
    if not os.path.exists(manifest):
        log('no MANIFEST.txt — skipping clip fetch')
        return
    for line in open(manifest):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, url = line.split()
        procs.append(subprocess.Popen(['curl', '-s', '-m', '300', '-A', UA, '-L', url, '-o',
                                       f'{ROOT}/build/clips-raw/{name}.mp4']))
    for p in procs:
        p.wait()
    for f in os.listdir(f'{ROOT}/build/clips-raw'):
        n = f[:-4]
        run([FF, '-y', '-i', f'{ROOT}/build/clips-raw/{f}', '-t', '10', '-vf',
             'scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,'
             'eq=saturation=0.45:contrast=1.06:brightness=-0.03,'
             'colorbalance=bs=0.10:bm=0.05:rm=-0.02',
             '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
             f'{ROOT}/build/clips-graded/{n}.mp4'])
        if os.path.exists(f'{ROOT}/build/clips-graded/{n}.mp4'):
            os.remove(f'{ROOT}/build/clips-raw/{f}')
    import shutil as sh
    sh.rmtree(f'{ROOT}/build/clips-raw', ignore_errors=True)


def wait_for_reset():
    """Wait for TTS quota reset (07:03 UTC daily)."""
    now = datetime.datetime.utcnow()
    target = now.replace(hour=7, minute=4, second=0)
    if target < now:
        return
    w = (target - now).total_seconds()
    log(f'waiting {w/60:.0f}m for TTS quota reset')
    time.sleep(w + 20)
    log('quota window open')


def script_chunks():
    """Load DD1 script sections (9 chunks with myth/expiry split)."""
    text = open(f'{ROOT}/renders/dd1-script.txt').read()
    secs = [s.strip() for s in re.split(r'--- C\d+ ---', text)[1:] if s.strip()]
    marker = "So \u2014 the notice is valid, and the date arrives."
    myth, expiry = secs[5].split(marker, 1)
    secs = secs[:5] + [myth.strip(), (marker + expiry).strip()] + secs[6:]
    assert len(secs) == 9
    return secs


def asr_text(path):
    """Run Vosk ASR and return full text (lowercase)."""
    from vosk import Model, KaldiRecognizer
    pcm = subprocess.run([FF, '-i', path, '-ar', '16000', '-ac', '1', '-f', 's16le', '-'],
                         capture_output=True).stdout
    rec = KaldiRecognizer(Model('/tmp/vosk/vosk-model-small-en-us-0.15'), 16000)
    rec.SetWords(True)
    words = []
    for j in range(0, len(pcm), 8000):
        chunk = pcm[j:j+8000]
        if rec.AcceptWaveform(chunk):
            words += [w['word'] for w in json.loads(rec.Result()).get('result', [])]
    words += [w['word'] for w in json.loads(rec.FinalResult()).get('result', [])]
    return ' '.join(words).lower()


def gen_chunk(i, text):
    """Generate a single TTS chunk with ASR leak verification + model fallback."""
    for attempt in range(4):
        for model in MODELS:
            r = run(['python3', f'{ROOT}/tools/gemini_tts.py', '--model', model, '--voice', 'Orus',
                     '--instruction', INS, '--text', text, '--out',
                     f'{ROOT}/renders/dd1-c{i}.mp3'])
            if r.returncode:
                log(f'c{i} gen fail ({model}): {r.stderr.strip()[:120]}')
                continue
            heard = asr_text(f'{ROOT}/renders/dd1-c{i}.mp3')
            leak = [b for b in BAD if b in heard]
            if not leak:
                if i in (1, 9) and not any(k in heard for k in ['docoga', 'koga', 'oga', 'oga dot']):
                    log(f'c{i}: clean but DocOga not detected — regenerating')
                    continue
                log(f'c{i}: CLEAN via {model} (attempt {attempt+1})')
                return True
            log(f'c{i}: LEAK {leak} via {model} — regenerating')
            time.sleep(2)
    return False


def rebuild_master():
    """Concatenate 9 chunks + loudnorm into master VO."""
    lst = '/tmp/dd1-list.txt'
    open(lst, 'w').write('\n'.join(f"file '{ROOT}/renders/dd1-c{i}.mp3'" for i in range(1, 10)))
    run([FF, '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy',
         f'{ROOT}/renders/dd1-raw.mp3'])
    run([FF, '-y', '-i', f'{ROOT}/renders/dd1-raw.mp3',
         '-af', 'loudnorm=I=-14.5:TP=-1.5:LRA=11',
         '-ar', '44100', '-c:a', 'libmp3lame', '-b:a', '192k', '-write_xing', '1',
         f'{ROOT}/renders/dd1-vo-master.mp3'])
    os.remove(f'{ROOT}/renders/dd1-raw.mp3')
    from mutagen.mp3 import MP3
    d = MP3(f'{ROOT}/renders/dd1-vo-master.mp3').info.length
    log(f'master rebuilt: {int(d//60)}:{int(d%60):02d}')
    return d


def update_meta_chapters():
    """Re-align ASR + update YouTube meta chapters from new timings."""
    r = run(['python3', f'{ROOT}/tools/align_dd1.py'])
    if r.returncode:
        log('ALIGN FAILED: ' + r.stderr[-300:])
        return False
    secs = json.load(open(f'{ROOT}/renders/dd1-words.json'))['sections']
    meta = json.load(open(f'{ROOT}/renders/dd1-yt-meta.json'))
    titles = [
        'A notice lands at your door',
        'Why the law protects you (1960 to today)',
        'How much notice? The full table',
        'The counting trap \u2014 when the clock starts',
        'The five requirements of a valid notice',
        'Myth killed: rent after a notice',
        'After the notice expires',
        'Self-help \u2014 the landlord becomes the defendant',
        'What to do right now',
    ]
    lines = ['CHAPTERS', '0:00 ' + titles[0]]
    for k, s in enumerate(secs[1:], 1):
        t = int(s['start'])
        lines.append(f'{t//60}:{t%60:02d} ' + titles[k])
    meta['description'] = meta['description'].split('CHAPTERS')[0] + '\n'.join(lines) + \
        '\n\n' + meta['description'].split('What to do right now\n', 1)[-1].split('\n', 1)[-1]
    json.dump(meta, open(f'{ROOT}/renders/dd1-yt-meta.json', 'w'), indent=2, ensure_ascii=False)
    log('chapters updated from new timings')
    return True


def render_and_qc():
    """Render all 9 scenes + cover + verify duration."""
    r = run(['python3', f'{ROOT}/tools/make_longform.py', 'all'], timeout=2400)
    log('render: ' + ('done' if r.returncode == 0 else 'FAIL ' + r.stderr[-200:]))
    if r.returncode:
        return False
    run(['python3', f'{ROOT}/tools/make_longform.py', 'cover'])
    probe = run([FF, '-i', f'{ROOT}/build/dd1-episode.mp4', '-t', '1', '-f', 'null', '-'])
    dur = [l for l in probe.stderr.splitlines() if 'Duration' in l]
    log('video: ' + (dur[0].split('Duration:')[1].split(',')[0].strip() if dur else '?'))
    return 'Duration: 00:10:' in probe.stderr or 'Duration: 00:09:' in probe.stderr


def upload(admin_key):
    """Upload to YouTube with scheduled publish."""
    env = dict(os.environ, ADMIN_KEY=admin_key)
    r = run(['python3', f'{ROOT}/tools/yt_upload_long.py',
             f'{ROOT}/renders/dd1-yt-meta.json',
             f'{ROOT}/build/dd1-episode.mp4',
             f'{ROOT}/renders/dd1-cover.jpg',
             '2026-09-28T17:00:00Z'],
            env=env, timeout=1500)
    out = r.stdout + r.stderr
    m = re.search(r'videoId = (\S+)', out)
    if not m:
        log('UPLOAD FAILED: ' + out[-400:])
        return None
    vid = m.group(1)
    open(f'{ROOT}/build/new-vid.txt', 'w').write(vid)
    log('UPLOADED new videoId = ' + vid)
    return vid


def swap_queue(vid, admin_key):
    """Swap announcement queue with new video URL."""
    url = f'https://www.youtube.com/watch?v={vid}'
    for qid in ['qmuksa4qd38s17', 'qmuksa4qd5qavs', 'qmuksa4qdn515x']:
        run(['curl', '-s', '-X', 'POST', 'https://docoga.com.ng/api/admin/queue',
             '-H', f'x-admin-key: {admin_key}', '-H', 'Content-Type: application/json',
             '--data', json.dumps({'action': 'cancel', 'id': qid})])
    items = [
        {'platform': 'tg', 'scheduledAt': '2026-09-28T17:05:00Z', 'payload': {'text':
            f'DEEP-DIVE #1 IS LIVE \u2014 NOTICE TO QUIT: THE LEGAL TIMELINE.\n\n'
            f'10 minutes that could save your home \u2014 or your property:\n'
            f'\u2014 the real notice periods (Lagos and Abuja)\n'
            f'\u2014 when the clock actually starts\n'
            f'\u2014 the 5 requirements that make a notice survive court\n'
            f'\u2014 the rent-after-notice myth, killed by the Supreme Court\n\n'
            f'Watch now: {url}\n\n'
            f'Then generate your own court-ready notice \u2014 free to start, no signup, no card: '
            f'https://docoga.com.ng'}},
        {'platform': 'th', 'scheduledAt': '2026-09-28T17:07:00Z', 'payload': {'text':
            f'One wrong word can void a notice to quit. Deep-Dive #1 breaks down the full legal '
            f'timeline \u2014 with real Supreme Court cases. Every tenant and landlord in Nigeria '
            f'needs this: {url}'}},
        {'platform': 'fb', 'scheduledAt': '2026-09-28T17:12:00Z', 'payload': {
            'photo': 'https://docoga.com.ng/social/dd1-cover.jpg', 'caption':
            f'One wrong word on a notice to quit can void the entire notice. Our first Deep-Dive '
            f'breaks down the full legal timeline \u2014 the real notice periods, when the clock '
            f'starts, the five requirements, and the rent-after-notice myth killed by the Supreme '
            f'Court. Watch it \u2014 then send it to every tenant and landlord you know: {url}'}}
    ]
    r = run(['curl', '-s', '-X', 'POST', 'https://docoga.com.ng/api/admin/queue',
             '-H', f'x-admin-key: {admin_key}', '-H', 'Content-Type: application/json',
             '--data', json.dumps({'items': items})])
    log('queue swap: ' + r.stdout[:120])


def main():
    skip_tts = '--skip-tts' in sys.argv
    admin_key = get_admin_key()

    ensure_deps()
    if not skip_tts:
        wait_for_reset()

    chunks = script_chunks()
    for i, text in enumerate(chunks, 1):
        if skip_tts:
            log(f'c{i}: SKIPPED (using existing clean chunk)')
            continue
        if not gen_chunk(i, text):
            STATUS['ok'] = False
            STATUS['error'] = f'chunk {i} unresolved leak'
            json.dump(STATUS, open(f'{ROOT}/build/REBUILD-STATUS.json', 'w'), indent=1)
            log('ABORTED — leak unresolved')
            return

    rebuild_master()
    if not update_meta_chapters():
        STATUS['ok'] = False
        json.dump(STATUS, open(f'{ROOT}/build/REBUILD-STATUS.json', 'w'), indent=1)
        return

    if not render_and_qc():
        STATUS['ok'] = False
        json.dump(STATUS, open(f'{ROOT}/build/REBUILD-STATUS.json', 'w'), indent=1)
        return

    vid = upload(admin_key)
    if not vid:
        STATUS['ok'] = False
        json.dump(STATUS, open(f'{ROOT}/build/REBUILD-STATUS.json', 'w'), indent=1)
        return

    swap_queue(vid, admin_key)

    STATUS['ok'] = True
    STATUS['videoId'] = vid
    STATUS['old_video_must_be_deleted_by_boss'] = OLD_VID
    json.dump(STATUS, open(f'{ROOT}/build/REBUILD-STATUS.json', 'w'), indent=1)
    log('REBUILD COMPLETE — new video: https://www.youtube.com/watch?v=' + vid)


if __name__ == '__main__':
    main()