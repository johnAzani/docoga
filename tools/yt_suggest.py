#!/usr/bin/env python3
"""
YouTube autocomplete research — what Nigerians actually type.

Usage: python3 tools/yt_suggest.py "notice to quit" [depth 2]

Free, no key: suggestqueries.google.com (public endpoint).
Output: ranked suggestion list + branch suggestions (a-z alphabet soup).
"""
import json, sys, urllib.request, urllib.parse

UA = {'User-Agent': 'Mozilla/5.0 (Linux; Android 13) Chrome/120'}


def suggest(q):
    """Fetch YouTube autocomplete suggestions for a query."""
    url = ('https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q='
           + urllib.parse.quote(q))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)[1]


def main():
    q = sys.argv[1] if len(sys.argv) > 1 else 'notice to quit nigeria'
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    print(f'== YouTube autocomplete: "{q}" ==')
    base = suggest(q)
    for s in base:
        print('  ', s)

    if depth >= 2:
        print(f'-- branches (a-z) --')
        seen = set(base)
        for ch in 'abcdefghijklmnopqrstuvwxyz':
            try:
                for s in suggest(f'{q} {ch}'):
                    if s not in seen:
                        print('  ', s)
                        seen.add(s)
            except Exception:
                pass


if __name__ == '__main__':
    main()