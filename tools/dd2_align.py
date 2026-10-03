#!/usr/bin/env python3
"""
DD2 word-sync (clone of DD1 aligner): per-chunk vosk ASR + fuzzy alignment
to the known script.
Output: renders/dd2-words.json {words:[{w,t0,t1,sec}], sections:[{sec,start,end,title}]}
"""
import json, re, subprocess, sys
from difflib import SequenceMatcher
from mutagen.mp3 import MP3

ROOT   = '/home/user/docoga'
MODEL  = '/tmp/vosk/vosk-model-small-en-us-0.15'
FF     = "/home/user/docoga/tools/bin/ffmpeg"

SECTION_TITLES = [
    "The Hook: Amaka's 200k",
    "What a Caution Fee Is",
    "The Refund Rule",
    "The Receipt",
    "Five Protections on Payment Day",
    "The Myth, Killed",
    "State Differences",
    "The Escalation Ladder",
    "What to Do Right Now",
]


def script_chunks():
    text = open(f'{ROOT}/renders/dd2-script.txt').read()
    secs = [s.strip() for s in re.split(r'--- C\d+ ---', text)[1:] if s.strip()]
    assert len(secs) == 9, f"expected 9 sections, got {len(secs)}"
    return secs


def norm_tokens(t):
    t = t.lower().replace('\u2014', ' ').replace('\u2013', ' ')
    t = re.sub(r"[^a-z' ]", ' ', t)
    return [w for w in t.split() if w]


def asr_words(path):
    from vosk import Model, KaldiRecognizer
    pcm = subprocess.run([FF, '-i', path, '-ar', '16000', '-ac', '1', '-f', 's16le', '-'],
                         capture_output=True).stdout
    rec = KaldiRecognizer(Model(MODEL), 16000)
    rec.SetWords(True)
    out = []
    for i in range(0, len(pcm), 8000):
        if rec.AcceptWaveform(pcm[i:i+8000]):
            r = json.loads(rec.Result())
            out += r.get('result', [])
    out += json.loads(rec.FinalResult()).get('result', [])
    return [(w['word'], w['start'], w['end']) for w in out]


def align(sec_idx, text, rec):
    stoks = norm_tokens(text)
    rtoks = [norm_tokens(r[0]) or [r[0].lower()] for r in rec]
    rt_flat = []
    for (tok, t0, t1), expanded in zip(rec, rtoks):
        for e in expanded:
            rt_flat.append((e, t0, t1))

    sm = SequenceMatcher(None, [r[0] for r in rt_flat], stoks, autojunk=False)
    words = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                words.append({'w': stoks[j1+k], 't0': rt_flat[i1+k][1],
                              't1': rt_flat[i1+k][2], 'sec': sec_idx})
        else:
            span = [rt_flat[i1-1][2] if i1 > 0 else 0.0,
                    rt_flat[i2][1] if i2 < len(rt_flat) else None]
            n = j2 - j1
            if n == 0:
                continue
            end_ref = span[1] if span[1] is not None else (rt_flat[-1][2] if rt_flat else span[0])
            t0 = span[0]; dt = (end_ref - span[0]) / n
            for k in range(n):
                words.append({'w': stoks[j1+k], 't0': round(t0 + k*dt, 3),
                              't1': round(t0 + (k+1)*dt, 3), 'sec': sec_idx})
    return words


def main():
    secs = script_chunks()
    durs = [MP3(f'{ROOT}/renders/dd2-c{i}.mp3').info.length for i in range(1, 10)]
    offsets = [0.0]
    for d in durs:
        offsets.append(offsets[-1] + d)

    all_words, sections = [], []
    for i, text in enumerate(secs, 1):
        rec = asr_words(f'{ROOT}/renders/dd2-c{i}.mp3')
        ws = align(i, text, rec)
        for w in ws:
            w['t0'] = round(w['t0'] + offsets[i-1], 3)
            w['t1'] = round(w['t1'] + offsets[i-1], 3)
        all_words += ws
        sections.append({
            'sec': i, 'title': SECTION_TITLES[i-1],
            'start': round(offsets[i-1], 2), 'end': round(offsets[i], 2),
            'asr_words': len(rec), 'script_words': len(norm_tokens(text)),
            'matched': sum(1 for t,_,_ in [(w,0,0) for w in ws])
        })
        print(f"c{i}: ASR {len(rec)} | script {len(norm_tokens(text))} | aligned {len(ws)} | {SECTION_TITLES[i-1]}")

    json.dump({'words': all_words, 'sections': sections},
              open(f'{ROOT}/renders/dd2-words.json', 'w'))
    print(f"TOTAL: {len(all_words)} words | audio span {all_words[0]['t0']:.1f}s \u2192 {all_words[-1]['t1']:.1f}s")


if __name__ == '__main__':
    main()