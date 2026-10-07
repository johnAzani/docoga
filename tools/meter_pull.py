#!/usr/bin/env python3
"""
Cross-platform meter pull (boss mandate: always research + improve metrics).

Pulls every platform's live numbers via existing admin endpoints, prints a chat
report, POSTs the snapshot to /api/admin/metrics (dashboard feed), saves local copy.
Tolerant: a failing platform never kills the pull.

Usage: python3 tools/meter_pull.py

Platforms: YouTube, Instagram, Facebook, Threads, Telegram
Output: renders/metrics/latest.json + dashboard POST
"""
import json, os, subprocess, sys, datetime

BASE = 'https://docoga.com.ng'
KEY = os.environ.get('ADMIN_KEY', '')
if not KEY:
    try:
        for line in open('/home/user/docoga/.worker-secrets.env'):
            if line.startswith('ADMIN_PASSCODE='):
                KEY = line.split('=', 1)[1].strip()
    except FileNotFoundError:
        pass

UA = 'Mozilla/5.0 (X11; Linux x86_64) DocOgaPipeline/1.0'
OUT = '/home/user/docoga/renders/metrics'


def get(path):
    r = subprocess.run(['curl', '-s', '-m', '60', '-A', UA, BASE + path,
                        '-H', 'x-admin-key: ' + KEY], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {'ok': False, 'error': 'unparseable: ' + r.stdout[:120]}


def num(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def pull_yt():
    d = get('/api/yt/status')
    if not d.get('ok'):
        return {'ok': False, 'note': str(d.get('error', ''))[:80]}
    ch = d.get('channel') or {}
    vids = d.get('videos') or []
    v = [{'title': (x.get('snippet') or {}).get('title', '')[:40],
          'views': num((x.get('statistics') or {}).get('viewCount')),
          'likes': num((x.get('statistics') or {}).get('likeCount')),
          'comments': num((x.get('statistics') or {}).get('commentCount')),
          'id': x.get('id')} for x in vids]
    return {'ok': True,
            'subs': num((ch.get('statistics') or {}).get('subscriberCount')),
            'channelViews': num((ch.get('statistics') or {}).get('viewCount')),
            'videos': v}


def pull_ig():
    d = get('/api/ig/insights')
    if not d.get('ok'):
        return {'ok': False, 'note': str(d.get('error', ''))[:80]}
    media = d.get('media') or []
    posts = []
    for m in media:
        ins = m.get('insights') or {}
        posts.append({'caption': str(m.get('caption', ''))[:34],
                      'views': num(ins.get('views')),
                      'likes': num(ins.get('likes', m.get('likes'))),
                      'comments': num(ins.get('comments', m.get('comments'))),
                      'saves': num(ins.get('saved')), 'shares': num(ins.get('shares')),
                      'reach': num(ins.get('reach'))})
    tot = {k: sum(p[k] for p in posts) for k in ('views', 'likes', 'comments', 'saves', 'shares', 'reach')}
    return {'ok': True, 'followers': num(d.get('followers')),
            'posts': posts[-12:], 'totals': tot, 'postCount': len(media)}


def pull_fb():
    d = get('/api/fb/status')
    if not d.get('ok'):
        return {'ok': False, 'note': str(d.get('error', ''))[:80]}
    page = d.get('page') or {}
    vids = d.get('videos') or []
    return {'ok': True, 'followers': num(page.get('followers', page.get('fans'))),
            'fanCount': num(page.get('fans', page.get('followers'))),
            'videoCount': len(vids),
            'videos': [{'title': str(v.get('title', ''))[:34], 'views': num(v.get('views'))}
                       for v in vids][-6:]}


def pull_th():
    d = get('/api/threads/status')
    if not d.get('ok'):
        return {'ok': False, 'note': str(d.get('error', ''))[:80]}
    u = d.get('profile') or d.get('user') or {}
    return {'ok': True, 'followers': num(u.get('followers_count')),
            'posts': len(d.get('posts') or []),
            'username': u.get('username'), 'tokenRefreshed': bool(d.get('tokenRefreshed'))}


def pull_tg(secrets='/home/user/docoga/.worker-secrets.env'):
    tok = None
    try:
        for line in open(secrets):
            if line.startswith('TG_BOT_TOKEN='):
                tok = line.split('=', 1)[1].strip()
    except FileNotFoundError:
        return {'ok': False, 'note': 'no secrets file'}
    if not tok:
        return {'ok': False, 'note': 'no bot token'}
    chat = os.environ.get('TG_CHAT_ID', '')
    if not chat:
        try:
            for line in open(secrets):
                if line.startswith('TG_CHAT_ID='):
                    chat = line.split('=', 1)[1].strip()
        except FileNotFoundError:
            pass
    if not chat:
        return {'ok': False, 'note': 'no chat id in env'}
    r = subprocess.run(['curl', '-s', '-m', '30',
                        f'https://api.telegram.org/bot{tok}/getChatMemberCount?chat_id={chat}'],
                       capture_output=True, text=True)
    try:
        j = json.loads(r.stdout)
        return {'ok': bool(j.get('ok')),
                'members': num(j.get('result')) if j.get('ok') else 0,
                'note': '' if j.get('ok') else str(j.get('description', ''))[:60]}
    except Exception:
        return {'ok': False, 'note': 'unparseable'}


def main():
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    snap = {'pulledAt': now, 'platforms': {
        'yt': pull_yt(), 'ig': pull_ig(), 'fb': pull_fb(), 'th': pull_th(), 'tg': pull_tg()}}

    os.makedirs(OUT, exist_ok=True)
    json.dump(snap, open(f'{OUT}/latest.json', 'w'), indent=1)

    # POST to dashboard
    r = subprocess.run(['curl', '-s', '-m', '30', '-A', UA, '-X', 'POST',
                        BASE + '/api/admin/metrics', '-H', 'x-admin-key: ' + KEY,
                        '-H', 'Content-Type: application/json',
                        '-d', json.dumps(snap)], capture_output=True, text=True)
    try:
        stored = json.loads(r.stdout)
    except Exception:
        stored = {'ok': False}

    # ---- chat report ----
    p = snap['platforms']
    print(f"METER PULL {now[:16]}Z")

    y = p['yt']
    if y.get('ok'):
        print(f"  YOUTUBE   subs {y['subs']} | channel views {y['channelViews']} | {len(y['videos'])} videos")
        for v in y['videos'][:4]:
            print(f"    - {v['views']:>5} views {v['likes']:>3} likes  {v['comments']:>2} cm  {v['title']}")
    else:
        print(f"  YOUTUBE   unreachable: {y.get('note')}")

    i = p['ig']
    if i.get('ok'):
        t = i['totals']
        print(f"  INSTAGRAM {i.get('followers')} followers | {i['postCount']} posts | "
              f"views {t['views']} reach {t['reach']} | likes {t['likes']} saves {t['saves']} shares {t['shares']}")
    else:
        print(f"  INSTAGRAM unreachable: {i.get('note')}")

    f = p['fb']
    if f.get('ok'):
        print(f"  FACEBOOK  followers {f['followers'] or f['fanCount']} | {f['videoCount']} videos")
        for v in f['videos'][:3]:
            print(f"    - {v['views']:>5} views  {v['title']}")
    else:
        print(f"  FACEBOOK  unreachable: {f.get('note')}")

    t = p['th']
    if t.get('ok'):
        print(f"  THREADS   followers {t['followers']} | posts {t['posts']}")
    else:
        print(f"  THREADS   unreachable: {str(t.get('note'))}")

    t = p['tg']
    if t.get('ok'):
        print(f"  TELEGRAM  members {t['members']}")
    else:
        print(f"  TELEGRAM  unreachable: {str(t.get('note'))}")

    if stored.get('ok'):
        print(f"  SNAPSHOT: stored ({stored.get('snapshots')} in history)")
    else:
        print(f"  SNAPSHOT: store failed: {str(stored)[:80]}")


if __name__ == '__main__':
    main()