#!/usr/bin/env python3
"""
DOCOGA SFX fetcher — Freesound CC0 (public domain, no attribution, no claims).

Recipe: search page with license:"Creative Commons 0" filter
        -> cdn preview -hq.mp3 URLs.

Usage: python3 tools/fetch_sfx.py            (downloads the curated set to renders/sfx/)
       python3 tools/fetch_sfx.py "gavel" 3  (custom search, top N)

All CC0 = safe for monetized YouTube, forever.
"""
import re, subprocess, sys, os, urllib.request

ROOT = '/home/user/docoga'
OUT  = f'{ROOT}/renders/sfx'
UA   = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# curated set for the DocOga beat map (name: query)
SET = {
    'gavel':    'gavel bang',
    'paper':    'paper rustle',
    'knock':    'door knock',
    'crowd':    'african market crowd',
    'typing':   'keyboard typing',
    'money':    'cash register',
    'siren':    'lagos traffic',
}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def search(query, n=3):
    q   = query.replace(' ', '+')
    url = f'https://freesound.org/search/?q={q}&f=license:%22Creative+Commons+0%22'
    html = fetch(url).decode('utf-8', 'replace')
    ids  = re.findall(
        r'https://cdn\.freesound\.org/previews/(\d+)/(\d+)_[\w]+-lq\.mp3', html)
    seen, out = set(), []
    for dirn, idn in ids:
        if idn in seen:
            continue
        seen.add(idn)
        out.append(
            f'https://cdn.freesound.org/previews/{dirn}/{idn}_SEED-hq.mp3')
        if len(out) >= n:
            break
    return out, html


def seed_for(url_lq_pattern, html):
    # the -lq URL carries the uploader seed; rebuild -hq with the same seed
    m = re.search(
        r'https://cdn\.freesound\.org/previews/(\d+)/(\d+_[\w]+)-lq\.mp3',
        html)
    return None


def download(name, query, n=2):
    os.makedirs(OUT, exist_ok=True)
    q   = query.replace(' ', '+')
    url = f'https://freesound.org/search/?q={q}&f=license:%22Creative+Commons+0%22'
    html = fetch(url).decode('utf-8', 'replace')

    # full preview URLs with seeds (lq) — swap to hq
    links = re.findall(
        r'https://cdn\.freesound\.org/previews/(\d+)/(\d+_[\w]+)-lq\.mp3',
        html)
    seen, got = set(), 0
    for dirn, base in links:
        if base in seen:
            continue
        seen.add(base)
        hq  = f'https://cdn.freesound.org/previews/{dirn}/{base}-hq.mp3'
        dst = f'{OUT}/{name}.mp3' if got == 0 else f'{OUT}/{name}-{got+1}.mp3'
        try:
            data = fetch(hq)
            if len(data) < 8000:
                continue
            open(dst, 'wb').write(data)
            print(f'  {name}: {len(data)//1024}KB <- {hq}')
            got += 1
            if got >= n:
                break
        except Exception as e:
            print(f'  {name}: FAIL {str(e)[:60]}')
    return got


if __name__ == '__main__':
    if len(sys.argv) > 1:
        download(
            sys.argv[1].replace('-', '_'),
            sys.argv[1],
            int(sys.argv[2]) if len(sys.argv) > 2 else 2)
    else:
        total = 0
        for name, q in SET.items():
            total += download(name, q)
        print(f'SFX set: {total} files in {OUT}')