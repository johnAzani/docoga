#!/usr/bin/env python3
"""
R4 word-level ASR alignment for reel content.
Aligns spoken audio to known script segments using dynamic programming.
Output: renders/r4-words.json {segments:[{start,end,words:[{w,t,e}]}]}
"""
import json, re, os, sys, subprocess

SEG_TEXTS = [
    'Sixty-six years of independence -',
    'and the average Nigerian tenant cannot name one right the law gives him.',
    'Not one.',
    'So listen carefully.',
    'One:',
    "a year's rent,",
    'maximum,',
    'in advance.',
    'Two:',
    'written notice before any eviction.',
    'Three:',
    'nobody -',
    'and I mean nobody -',
    'throws your things outside.',
    'Four:',
    'only a court order can remove you.',
    'Five:',
    'a receipt for every single payment.',
    'Six:',
    'your caution fee is refundable -',
    'a deposit,',
    'not a gift!',
    'Sixty-six years.',
    'Six rights.',
    'And every single one lives inside a document you can generate free.',
    'Right now!'
]


def norm_tokens(t):
    t = t.lower()
    t = re.sub(r"[^a-z' ]", ' ', t)
    toks = []
    for w in t.split():
        if w == 'cannot':
            toks += ['can', 'not']
        elif w == 'sixty-six':
            toks += ['sixty', 'six']
        else:
            toks.append(w)
    return toks


script = []
for i, s in enumerate(SEG_TEXTS):
    for w in norm_tokens(s):
        script.append((i, w))

root = os.path.dirname(os.path.abspath(__file__))
asr_path = os.path.join(root, '..', 'renders', 'r4-asr.json')

if not os.path.exists(asr_path):
    subprocess.run(['bash', '-c',
        'pip3 install --quiet vosk; mkdir -p /tmp/vosk && cd /tmp/vosk; '
        '[ -d vosk-model-small-en-us-0.15 ] || { curl -sL -o m.zip https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip && unzip -q m.zip; }; '
        '/home/user/docoga/tools/bin/ffmpeg -y -loglevel error -i /home/user/docoga/renders/r4-vo-master.mp3 -ar 16000 -ac 1 -c:a pcm_s16le /tmp/vosk/t.wav; '
        'python3 -c "import json,wave;from vosk import Model,KaldiRecognizer;'
        "w=wave.open('/tmp/vosk/t.wav');r=KaldiRecognizer(Model('/tmp/vosk/vosk-model-small-en-us-0.15'),16000);r.SetWords(True);ws=[]\\n"
        'while True:\\n d=w.readframes(4000)\\n if not d: break\\n if r.AcceptWaveform(d): ws+=json.loads(r.Result()).get("result",[])\\n'
        'ws+=json.loads(r.FinalResult()).get("result",[]);json.dump(ws,open(\'/home/user/docoga/renders/r4-asr.json\',\'w\'))"'],
        cwd=os.path.join(root, '..'), check=True)

asr = json.load(open(asr_path))
av = [w['word'].lower() for w in asr]
n, m = len(script), len(av)

# Dynamic programming alignment
INF = 1e18
dp = [[INF] * (m + 1) for _ in range(n + 1)]
bk = [[None] * (m + 1) for _ in range(n + 1)]
dp[0][0] = 0

for i in range(n + 1):
    for j in range(m + 1):
        if dp[i][j] >= INF:
            continue
        c = dp[i][j]
        if i < n and j < m:
            cost = 0 if script[i][1] == av[j] else 1.2
            if c + cost < dp[i + 1][j + 1]:
                dp[i + 1][j + 1] = c + cost
                bk[i + 1][j + 1] = 'diag'
        if i < n and c + 1.0 < dp[i + 1][j]:
            dp[i + 1][j] = c + 1.0
            bk[i + 1][j] = 'skip_asr'
        if j < m and c + 1.0 < dp[i][j + 1]:
            dp[i][j + 1] = c + 1.0
            bk[i][j + 1] = 'skip_script'

i, j = n, m
matches = []
while i > 0 or j > 0:
    a = bk[i][j]
    if a == 'diag':
        matches.append((i - 1, j - 1))
        i -= 1; j -= 1
    elif a == 'skip_asr':
        i -= 1
    else:
        j -= 1
matches.reverse()

mism = [(script[i][1], av[j]) for i, j in matches if script[i][1] != av[j]]
print('ASR alignment: %d/%d script words matched, mismatches: %s' % (len(matches), n, mism[:6]))

word_t = {}
for si, aj in matches:
    word_t.setdefault(si, []).append((script[si][1], asr[aj]['start'], asr[aj]['end']))

for si in range(n):
    if si not in word_t:
        prev = None
        for k in range(si - 1, -1, -1):
            if k in word_t:
                prev = word_t[k][-1]; break
        nxt = None
        for k in range(si + 1, n):
            if k in word_t:
                nxt = word_t[k][0]; break
        if prev and nxt:
            mid = (prev[1] + nxt[1]) / 2
            word_t[si] = [(script[si][1], mid, mid)]
        elif prev:
            word_t[si] = [(script[si][1], prev[2], prev[2])]

segs = []
for k, s in enumerate(SEG_TEXTS):
    idxs = [si for si in range(n) if script[si][0] == k]
    words = []
    for si in idxs:
        for wname, st, en in word_t.get(si, []):
            words.append({'w': wname, 't': round(st, 3), 'e': round(en, 3)})
    segs.append({'start': words[0]['t'], 'end': words[-1]['e'], 'words': words})

json.dump({'segments': segs}, open(os.path.join(root, '..', 'renders', 'r4-words.json'), 'w'), indent=1)

nums = {}
for k in (4, 8, 10, 14, 16, 18):
    nums['right%d' % ({4:1,8:2,10:3,14:4,16:5,18:6}[k])] = segs[k]['start']

print('NUMBER-WORD TIMES (ground truth):', {k: round(v, 2) for k, v in nums.items()})
print('synth at %.2f, endcard at %.2f' % (segs[22]['start'], segs[25]['start']))