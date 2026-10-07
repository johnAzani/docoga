#!/usr/bin/env python3
"""
DEEP METADATA RESEARCH (Law 50) — the very-very-in-depth dossier that runs
BEFORE any asset is generated.  One command, three research layers:

  1. DEMAND   — YouTube autocomplete + Google autocomplete (buyer intent)
  2. COMPETITION — YouTube ranking scrape: top videos for the phrase, with
     views, age, and title patterns (what wins, what's stale, where the gap is)
  3. PACKAGE GUIDANCE — title formulas + keyword inventory for the meta lab

Usage: python3 tools/deep_research.py "main phrase" ["seed 2" ...]
Fast by design: parallel-friendly, <10s, zero API keys.
"""
import json, re, subprocess, sys, urllib.request

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
NIGERIA_HINT = 'nigeria'


def curl(url, timeout=20):
    r = subprocess.run(
        ['curl', '-s', '-m', str(timeout), '-A', UA,
         '-H', 'Accept-Language: en', url],
        capture_output=True, text=True)
    return r.stdout


def yt_suggest(q):
    out = curl(
        'https://suggestqueries-clients6.youtube.com/complete/search'
        '?client=youtube&ds=yt&q=' + urllib.request.quote(q))
    try:
        inner = out[out.index('(') + 1:out.rindex(')')]
        return [s for s in json.loads(inner)[1]]
    except Exception:
        return []


def google_suggest(q):
    out = curl(
        'https://suggestqueries.google.com/complete/search'
        '?client=firefox&q=' + urllib.request.quote(q))
    try:
        return json.loads(out)[1]
    except Exception:
        return []


def yt_ranking(q):
    html = curl(
        'https://www.youtube.com/results?search_query='
        + urllib.request.quote(q))
    m = re.search(r'var ytInitialData = ({.*?});</script>', html)
    if not m:
        return []
    d = json.loads(m.group(1))
    rows = []

    def walk(o):
        if isinstance(o, dict):
            if 'videoRenderer' in o and len(rows) < 8:
                v = o['videoRenderer']
                t = ''.join(
                    r.get('text', '')
                    for r in v.get('title', {}).get('runs', []))
                rows.append({
                    'id': v.get('videoId', ''),
                    'title': t,
                    'views': v.get('viewCountText', {}).get('simpleText', ''),
                    'age': v.get('publishedTimeText', {}).get('simpleText', ''),
                })
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(d)
    return rows


def main():
    seeds = sys.argv[1:]
    if not seeds:
        print(__doc__)
        return

    main_q = seeds[0]

    print('=' * 66)
    print(f'DEEP RESEARCH DOSSIER — "{main_q}"')
    print('=' * 66)

    # 1. YouTube autocomplete
    print('\n[1] DEMAND — YouTube autocomplete:')
    r = subprocess.run(
        ['python3', 'tools/yt_suggest.py', main_q],
        capture_output=True, text=True)
    for l in [x.strip() for x in r.stdout.splitlines()
              if x.strip() and not x.startswith('==')][:8]:
        print('   yt: ' + re.sub(r'^\s*\d+\s+', '', l))

    # 2. Google autocomplete (buyer intent)
    print('\n[2] DEMAND — Google autocomplete (buyer intent):')
    for s in google_suggest(main_q)[:8]:
        print('   g:  ' + s)

    for extra in seeds[1:]:
        print(f'\n[+] extra seed "{extra}":')
        for s in google_suggest(extra)[:5]:
            print('   g:  ' + s)
        for s in yt_suggest(extra)[:5]:
            print('   yt: ' + s)

    # 3. YouTube top rankings
    print('\n[3] COMPETITION — YouTube top rankings:')
    for i, v in enumerate(yt_ranking(main_q), 1):
        print(f"   {i}. {v['views']:>14}  {v['age']:>10}  {v['title'][:58]}")

    # 4. Gap analysis
    print('\n[4] GAP ANALYSIS:')
    rows = yt_ranking(main_q)

    def years_old(a):
        m = re.search(r'(\d+)y', a)
        return int(m.group(1)) if m else 0

    stale = sum(1 for v in rows if years_old(v['age']) >= 3)
    naija = sum(1 for v in rows
                if 'nigeria' in v['title'].lower()
                or 'naija' in v['title'].lower())
    print(f'   stale (3yr+): {stale}/{len(rows)}  '
          f'| Nigeria-specific: {naija}/{len(rows)}')

    if stale >= len(rows) / 2:
        print('   -> GAP: rankings dominated by old videos '
              '— a fresh 2026 package outranks on recency')
    if naija <= 1:
        print('   -> GAP: almost no Nigeria-specific competition '
              '— the Nigeria angle is UNOWNED')

    # 5. Title formulas
    print('\n[5] TITLE FORMULAS (feed the meta lab):')
    print(f'   A. How to Write a {main_q.title()} in Nigeria (2026)'
          ' — matches how-to intent')
    print(f'   B. {main_q.title()} in Nigeria: The Law Explained'
          ' — authority angle')
    print(f'   C. Free {main_q.title()} Generator Nigeria'
          ' — template/sample/pdf intent (from Google demand)')


if __name__ == '__main__':
    main()