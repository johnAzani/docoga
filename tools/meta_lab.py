#!/usr/bin/env python3
"""
META LAB (Law 49 enforcement) — research meters BEFORE generating, then build
and validate platform metadata against 2026 ranking benchmarks.

Usage:
  python3 tools/meta_lab.py research "seed phrase" ["seed 2" ...]
      -> autocomplete demand table (the BEFORE-generating evidence)
  python3 tools/meta_lab.py build yt-long renders/dd2-yt-meta.json
      -> validates + scores the metadata package; exits 1 on any FAIL

Platform rules (Law 47/49): title lengths, hook placement, keyword block,
chapters, tag budget, CTA lines, hashtag caps. The lab never writes copy —
it proves the copy is right.
"""
import json, os, re, subprocess, sys

ROOT = '/home/user/docoga'

RULES = {
    'yt-long': {
        'title_max': 70, 'hook_max': 150, 'tags_budget': 500, 'hashtags_max': 3,
        'needs': ['title', 'description', 'tags', 'categoryId'],
        'desc_blocks': ['CHAPTERS', 'docoga.com.ng'],
        'cta': ('send-worthy framing + free-to-start line', ['Free to start', 'free to start']),
    },
    'yt-short': {
        'title_max': 90, 'hook_max': 100, 'tags_budget': 500, 'hashtags_max': 3,
        'needs': ['title', 'description', 'tags'],
        'desc_blocks': ['docoga.com.ng'],
        'cta': ('link to full episode', ['full episode', 'watch the full', '#deep-dive']),
    },
    'ig': {
        'title_max': 2200, 'hook_max': 125, 'tags_budget': 0, 'hashtags_max': 5,
        'needs': ['caption'],
        'desc_blocks': ['docoga.com.ng'],
        'cta': ('send CTA + question ending', ['send this', 'Send this', 'tag ', 'Tag ']),
    },
    'fb': {
        'title_max': 5000, 'hook_max': 140, 'tags_budget': 0, 'hashtags_max': 3,
        'needs': ['caption'], 'desc_blocks': ['docoga.com.ng'],
        'cta': ('share CTA', ['Share', 'share']),
    },
    'th': {
        'title_max': 500, 'hook_max': 100, 'tags_budget': 0, 'hashtags_max': 2,
        'needs': ['text'], 'desc_blocks': ['docoga.com.ng'],
        'cta': ('question ending', ['?']),
    },
    'tg': {
        'title_max': 4096, 'hook_max': 120, 'tags_budget': 0, 'hashtags_max': 0,
        'needs': ['text'], 'desc_blocks': ['docoga.com.ng'],
        'cta': ('forward CTA', ['forward', 'Forward']),
    },
}

FIELDS = {
    'yt-long': ('title', 'description'), 'yt-short': ('title', 'description'),
    'ig': ('caption',), 'fb': ('caption',), 'th': ('text',), 'tg': ('text',),
}


def research(seeds):
    """Meter research: run BEFORE generating — Law 49."""
    print('METER RESEARCH (run BEFORE generating — Law 49)\n' + '=' * 52)
    for seed in seeds:
        r = subprocess.run(['python3', f'{ROOT}/tools/yt_suggest.py', seed],
                           capture_output=True, text=True)
        lines = [l.strip() for l in r.stdout.splitlines() if l.strip() and not l.startswith('==')]
        print(f'\n"{seed}" — what people actually type:')
        for l in lines[:8]:
            print('   ' + re.sub(r'^\s*\S+\s+', '', l) if re.match(r'^\s*\d', l) else '   ' + l)


def build(platform, path):
    """Build and validate a metadata package against platform rules."""
    m = json.load(open(path))
    R = RULES[platform]
    field = 'description' if platform.startswith('yt') else FIELDS[platform][0]
    body = m.get(field, '') or ''
    score, fails, notes = 0, [], []

    def chk(name, ok, pts, note=''):
        nonlocal score
        if ok:
            score += pts
        else:
            fails.append(name + (f' ({note})' if note else ''))
        if note and ok:
            notes.append(note)

    title = m.get('title', m.get(field, ''))
    chk('field presence', all(m.get(k) for k in R['needs']), 20)
    chk(f'title <= {R["title_max"]}c', len(title) <= R['title_max'], 15, f'{len(title)}c')

    first150 = body[:R['hook_max']]
    chk('hook in first window', len(first150.strip()) > 30, 10)

    for blk in R['desc_blocks']:
        chk(f'block "{blk[:24]}"' if len(blk) > 24 else f'block "{blk}"', blk in body, 5)

    if platform.startswith('yt'):
        tags = m.get('tags', [])
        tlen = sum(len(t) for t in tags)
        chk(f'tags <= {R["tags_budget"]}c', tlen <= R['tags_budget'], 10, f'{len(tags)} tags, {tlen}c')

        STOP = {'the', 'and', 'for', 'from', 'your', 'you', 'that', 'this', 'with',
                'what', 'when', 'how', 'only', 'things', 'nigeria'}
        tw = [w.strip('?:!.,').lower() for w in title.split()
              if len(w) > 3 and w.lower() not in STOP]
        hits = sum(1 for w in tw if any(w in t.lower() for t in tags))
        chk('keywords in tags (>=2 title words)', hits >= 2, 10, f'{hits} title words found in tags')

        hash_in_desc = re.findall(r'(?:^|\s)#\w+', body)
        chk(f'<= {R["hashtags_max"]} hashtags', len(hash_in_desc) <= R['hashtags_max'], 5,
            f'{len(hash_in_desc)}')

    cta_ok = any(c.lower() in body.lower() for c in R['cta'][1])
    chk(f'CTA: {R["cta"][0]}', cta_ok, 15)

    # freshness marker for evergreen legal content
    chk('year/freshness marker', bool(re.search(r'202[4-9]', body) or '202' in title), 5)

    # question/tension in title (CTR law 36 alignment): ? ! or power words
    POWER = ('decide', 'never', 'warning', 'stop', 'mistake', 'everything', 'lost',
             'wins', 'refuses', 'explains', 'only')
    tension = ('?' in title) or ('!' in title) or any(p in title.lower() for p in POWER)
    chk('title tension (?:/!/power)', tension, 5, '"' + title[:40] + '"')

    print(f'META LAB — {platform} — {os.path.basename(path)}')
    print(f'  SCORE {score} pts — {len(fails)} fail(s)')
    for n in notes:
        print(f'    . {n}')
    if fails:
        print('  FAILS:')
        for f in fails:
            print(f'    X {f}')
        sys.exit(1)
    print('  PACKAGE: PASS — cleared for upload')
    return score


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] == 'research':
        research(sys.argv[2:])
    elif sys.argv[1] == 'build':
        if len(sys.argv) < 4:
            print('Usage: meta_lab.py build <platform> <path-to-meta.json>')
            sys.exit(1)
        build(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)