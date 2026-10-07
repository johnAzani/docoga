#!/usr/bin/env python3
"""
Direct long-form YouTube upload (for files >25MB that can't route via Pages).

Usage: ADMIN_KEY=... python3 tools/yt_upload_long.py META.json VIDEO.mp4 THUMB.jpg [PUBLISH_AT_UTC]

Uses /api/yt/token (admin) -> resumable upload -> thumbnail -> verify. Prints videoId.

Args:
  META.json     — JSON with title, description, tags, categoryId, madeForKids
  VIDEO.mp4     — video file (any size, resumable upload)
  THUMB.jpg     — thumbnail image
  PUBLISH_AT_UTC — optional ISO 8601 datetime for scheduled publish
"""
import json, os, subprocess, sys

BASE = 'https://docoga.com.ng'
UA = 'Mozilla/5.0 (X11; Linux x86_64) DocOgaPipeline/1.0'


def api(path, key):
    """Call DocOga admin API endpoint."""
    r = subprocess.run(['curl', '-s', '-m', '60', '-A', UA, BASE + path,
                        '-H', 'x-admin-key: ' + key], capture_output=True, text=True)
    return json.loads(r.stdout)


def main():
    if len(sys.argv) < 4:
        print('Usage: yt_upload_long.py META.json VIDEO.mp4 THUMB.jpg [PUBLISH_AT_UTC]')
        sys.exit(1)

    meta = json.load(open(sys.argv[1]))
    video, thumb = sys.argv[2], sys.argv[3]
    publish_at = sys.argv[4] if len(sys.argv) > 4 else None
    key = os.environ.get('ADMIN_KEY', '')
    if not key:
        sys.exit('ADMIN_KEY env required')

    # Get YouTube access token
    tok = api('/api/yt/token', key)['accessToken']
    print('token ok')

    # Build video metadata
    status = {
        'privacyStatus': 'private',
        'selfDeclaredMadeForKids': bool(meta.get('madeForKids', False)),
    }
    if publish_at:
        status['publishAt'] = publish_at

    init = {
        'snippet': {
            'title': meta['title'],
            'description': meta['description'],
            'tags': meta['tags'],
            'categoryId': meta['categoryId'],
        },
        'status': status,
    }
    open('/tmp/yt-init.json', 'w').write(json.dumps(init))

    # Initiate resumable upload session
    r = subprocess.run(['curl', '-s', '-X', 'POST',
        'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
        '-H', f'Authorization: Bearer {tok}', '-H', 'Content-Type: application/json',
        '--data', '@/tmp/yt-init.json', '-o', '/dev/null', '-D', '-'],
        capture_output=True, text=True)

    loc = [l for l in r.stdout.splitlines() if l.lower().startswith('location:')]
    if not loc:
        sys.exit('no session location: ' + r.stdout[:300] + r.stderr[:200])
    location = loc[0].split(':', 1)[1].strip()
    print('resumable session open')

    # Upload video (with retry + resume)
    total = os.path.getsize(video)
    resp = None
    for attempt in range(3):
        r = subprocess.run(['curl', '-s', '--max-time', '1500', '-X', 'PUT', location,
                            '-H', 'Content-Type: video/mp4', '--data-binary', '@' + video],
                           capture_output=True, text=True)
        try:
            resp = json.loads(r.stdout)
            if 'id' in resp:
                break
        except Exception:
            pass

        # Find resume offset
        st = subprocess.run(['curl', '-s', '-X', 'PUT', location,
                             '-H', f'Content-Range: bytes */{total}'],
                            capture_output=True, text=True)
        rng = [l for l in (st.stdout + st.stderr).splitlines() if 'Range:' in l]
        off = int(rng[0].split('=')[1].split('-')[1]) + 1 if rng and '=' in rng[0] else 0
        print(f'attempt {attempt+1} failed, resuming from byte {off}')

        if off and off < total:
            subprocess.run(f'tail -c +{off+1} "{video}" > /tmp/yt-part.bin', shell=True)
            r = subprocess.run(['curl', '-s', '--max-time', '1500', '-X', 'PUT', location,
                                '-H', f'Content-Range: bytes {off}-{total-1}/{total}',
                                '-H', 'Content-Type: video/mp4',
                                '--data-binary', '@/tmp/yt-part.bin'],
                               capture_output=True, text=True)
            try:
                resp = json.loads(r.stdout)
                if 'id' in resp:
                    break
            except Exception:
                pass

    if not resp or 'id' not in resp:
        sys.exit('upload failed: ' + (r.stdout or '')[:400])

    vid = resp['id']
    print('UPLOADED videoId =', vid)

    # Set thumbnail
    t = subprocess.run(['curl', '-s', '-X', 'POST',
        f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}',
        '-H', f'Authorization: Bearer {tok}', '-H', 'Content-Type: image/jpeg',
        '--data-binary', '@' + thumb], capture_output=True, text=True)
    print('thumbnail:', 'ok' if '"default"' in t.stdout or 'width' in t.stdout else t.stdout[:200])

    # Verify
    r = subprocess.run(['curl', '-s', '-m', '60',
        f'https://www.googleapis.com/youtube/v3/videos?part=snippet,status&id={vid}',
        '-H', f'Authorization: Bearer {tok}'], capture_output=True, text=True)
    v = json.loads(r.stdout)['items'][0]
    print('VERIFY:', json.dumps({
        'title': v['snippet']['title'][:60],
        'privacy': v['status']['privacyStatus'],
        'publishAt': v['status'].get('publishAt'),
        'uploadStatus': v['status']['uploadStatus'],
    }))
    print('URL: https://www.youtube.com/watch?v=' + vid)


if __name__ == '__main__':
    main()