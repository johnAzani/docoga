#!/usr/bin/env python3
"""
DOCOGA Deep-Dive long-form engine — 16:9 1920x1080 30fps, word-synced.

Usage:
  python3 tools/make_longform_dd4.py scene N    # render scene N
  python3 tools/make_longform_dd4.py all        # render all 9 scenes + final video
  python3 tools/make_longform_dd4.py cover      # render YouTube thumbnail

DD4 = The Rent Receipt
Outputs: build/dd4-vid/sN.mp4 segments, renders/dd4-cover.jpg
"""
import json, os, subprocess, sys, math
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance, ImageFilter

ROOT = '/home/user/docoga'
FF   = f'{ROOT}/tools/bin/ffmpeg'

# Self-provision ffmpeg if missing
if not os.path.exists(FF):
    import subprocess as _sp
    _sp.run(['pip', 'install', '-q', 'imageio-ffmpeg'], capture_output=True)
    _src = _sp.run(['python3', '-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'],
                   capture_output=True, text=True).stdout.strip()
    import shutil
    os.makedirs(f'{ROOT}/tools/bin', exist_ok=True)
    shutil.copy(_src, FF)
    os.chmod(FF, 0o755)

OUT = f'{ROOT}/build/dd4-vid'
W, H, FPS = 1920, 1080, 30
NAVY, RULE, PANEL = (6, 26, 51), (20, 41, 74), (15, 61, 124)
WHITE, MUTED, FAINT = (255, 255, 255), (143, 168, 201), (96, 128, 170)
BLUE, YELLOW, RED   = (74, 140, 255), (255, 201, 60), (255, 90, 95)
TTF = f'{ROOT}/tools/fonts/Inter-Variable.ttf'

_fc = {}
def font(w, s):
    key = (w, s)
    if key not in _fc:
        f = ImageFont.truetype(TTF, s)
        try: f.set_variation_by_name(w)
        except Exception: pass
        _fc[key] = f
    return _fc[key]

IMG = {n: f'{ROOT}/renders/dd1-img-{n}.jpg' for n in
       ['door', 'letter', 'history', 'calendar', 'pen', 'court', 'padlock', 'bags', 'keys', 'phone',
        'danfo', 'keke', 'market', 'generator', 'rooftops', 'ankara', 'kiosk', 'dusk']}

CLIPS = f'{ROOT}/build/clips-graded'


class ClipReader:
    def __init__(self, name):
        self.name = name
        self.proc = subprocess.Popen(
            [FF, '-stream_loop', '-1', '-i', f'{CLIPS}/{name}.mp4',
             '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=W*H*3)

    def frame(self):
        data = self.proc.stdout.read(W*H*3)
        if len(data) < W*H*3:
            self.close()
            self.__init__(self.name)
            data = self.proc.stdout.read(W*H*3)
        return Image.frombytes('RGB', (W, H), data)

    def close(self):
        try:
            self.proc.kill()
            self.proc.wait()
        except Exception:
            pass


SEC_TITLES = [
    "The Hook", "What a Receipt Is", "The Seven Lines", "The Quiet Traps",
    "The Paper Family", "Myths, Killed", "Digital Proof", "What To Do Now", "The Close"
]


# ──────── data ────────
def norm(w):
    return ''.join(c for c in w.lower() if c.isalnum() or c == "'")


def load():
    d = json.load(open(f'{ROOT}/renders/dd4-words.json'))
    words = d['words']
    secs  = d['sections']
    by_sec = {}
    for w in words:
        by_sec.setdefault(w['sec'], []).append(w)
    return words, secs, by_sec


def find_idx(sec_words, trig, from_i=0):
    t = [norm(x) for x in trig]
    n = [norm(w['w']) for w in sec_words]
    for i in range(from_i, len(n) - len(t) + 1):
        if n[i:i+len(t)] == t:
            return i
    return None


# ──────── imagery ────────
_G = {}
def treated(name):
    if name in _G:
        return _G[name]
    im = Image.open(IMG[name]).convert('L')
    im = ImageOps.colorize(im, black=(8, 24, 46), white=(202, 222, 248)).convert('RGB')
    im = ImageEnhance.Contrast(im).enhance(1.05)
    im = ImageEnhance.Brightness(im).enhance(1.14)
    tw, th = 2400, 1350
    r = max(tw / im.width, th / im.height)
    im = im.resize((math.ceil(im.width * r), math.ceil(im.height * r)), Image.LANCZOS)
    x = (im.width - tw) // 2; y = (im.height - th) // 2
    im = im.crop((x, y, x + tw, y + th))
    noise = Image.effect_noise((tw, th), 16).convert('L')
    im = Image.composite(im, Image.new('RGB', (tw, th), (2, 10, 22)),
                         noise.point(lambda p: 255 - min(42, p // 4)))
    vig = Image.radial_gradient('L').resize((tw, th)).point(lambda p: min(85, p * 2))
    im = Image.composite(Image.new('RGB', (tw, th), (2, 10, 22)), im, vig)
    _G[name] = im
    return im


_LG = None
def left_grad():
    global _LG
    if _LG is None:
        g = Image.new('L', (W, H))
        px = g.load()
        for x in range(W):
            a = int(max(0, 235 * (1 - x / 1150)))
            for y in range(H):
                px[x, y] = a
        _LG = Image.new('RGBA', (W, H), NAVY + (0,))
        _LG.putalpha(g)
    return _LG


def base_plate():
    b = Image.new('RGB', (W, H), NAVY)
    d = ImageDraw.Draw(b)
    d.rectangle([0, 0, W, 4], fill=RULE)
    return b


# ──────── text ────────
def wrap_fit(text, weight, size, maxw):
    while size > 40:
        f = font(weight, size)
        lines, cur = [], ''
        for wd in text.replace('\n', ' \n ').split():
            if wd == '\n':
                if cur: lines.append(cur)
                cur = ''; continue
            t = (cur + ' ' + wd).strip()
            if f.getlength(t) <= maxw:
                cur = t
            else:
                if cur: lines.append(cur)
                cur = wd
        if cur: lines.append(cur)
        if all(f.getlength(l) <= maxw for l in lines) and len(lines) <= 4:
            return f, lines, size
        size -= 6
    return f, lines, size


def beat_layer(head, sub, accent=YELLOW, head_color=WHITE, center=False, top=False):
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    maxw = 1180
    hsz = 108 if top else (148 if len(head) < 26 else 116)
    hf, hlines, hsize = wrap_fit(head, 'Black', hsz, maxw)
    sf, slines, _ = wrap_fit(sub, 'SemiBold', 42 if top else 46, maxw - 80) if sub else (None, [], 0)
    lh = int(hsize * 1.08); sh = 58
    total = 22 + 8 + 10 + len(hlines) * lh + (14 + len(slines) * sh if slines else 0)
    y = 132 if top else (H - total) // 2 - 30
    if center:
        x0 = (W - max(hf.getlength(l) for l in hlines)) // 2
    else:
        x0 = 150
    d.rectangle([x0, y, x0 + 170, y + 10], fill=accent)
    y += 44
    for l in hlines:
        if center:
            x = (W - hf.getlength(l)) // 2
        else:
            x = x0
        d.text((x, y), l, font=hf, fill=head_color)
        y += lh
    if slines:
        y += 14
        for l in slines:
            if center:
                x = (W - sf.getlength(l)) // 2
            else:
                x = x0
            d.text((x, y), l, font=sf, fill=MUTED)
            y += sh
    return lay


def rows_layer(rows, shown):
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    n_all = len(rows)
    if n_all > 4:
        sz, y0, lh = 52, 528, 76
    else:
        sz, y0, lh = 62, 560, 92
    f = font('Bold', sz); nf = font('Black', sz)
    vis = rows[:shown]
    panel_h = len(vis) * lh + 36
    d.rectangle([120, y0 - 24, 1800, y0 - 24 + panel_h], fill=(4, 16, 33, 200))
    d.rectangle([120, y0 - 24, 128, y0 - 24 + panel_h], fill=YELLOW)
    y = y0
    for r in vis:
        num = r.split('\u00B7')[0].strip()
        rest = r.split('\u00B7', 1)[1].strip() if '\u00B7' in r else ''
        d.text((170, y), num, font=nf, fill=YELLOW)
        d.text((320, y), rest, font=f, fill=WHITE)
        y += lh
    return lay


def endcard_layer():
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    k = font('SemiBold', 40); f1 = font('Black', 190); f2 = font('Bold', 58); f3 = font('SemiBold', 44)
    t = 'DOCOGA'
    d.text(((W - f1.getlength(t)) // 2, 300), t, font=f1, fill=WHITE)
    d.text(((W - k.getlength('D E E P - D I V E')) // 2, 230), 'D E E P - D I V E', font=k, fill=MUTED)
    t = 'docoga.com.ng'
    d.text(((W - f2.getlength(t)) // 2, 540), t, font=f2, fill=YELLOW)
    t = 'EVERY DOCUMENT A NIGERIAN NEEDS'
    d.text(((W - f3.getlength(t)) // 2, 640), t, font=f3, fill=MUTED)
    t = 'LINK IN THE DESCRIPTION'
    d.text(((W - f3.getlength(t)) // 2, 730), t, font=f3, fill=WHITE)
    d.rectangle([(W - 240) // 2, 620, (W + 240) // 2, 626], fill=RULE)
    return lay


# ──────── beats ────────
def B(sec, trig, head, sub='', img=None, color=WHITE, accent=YELLOW, rows=None, row_trigs=None,
      center=False, endcard=False):
    return dict(sec=sec, trig=trig, head=head, sub=sub, img=img, color=color, accent=accent,
                rows=rows or [], row_trigs=row_trigs or [], center=center, endcard=endcard)

BEATS = [
    # ── Scene 1: The Hook ──
    B(1, None, 'SHOW ME YOUR RECEIPTS', 'the four words that end rent disputes', 'clip:money-count'),
    B(1, ['three', 'years', 'of', 'rent'], 'THREE YEARS OF RENT', 'paid in cash. every year. same landlord.', 'market'),
    B(1, ['never', 'paid', 'me'], '"YOU NEVER PAID ME A KOBO"', 'and he can look you in the eye', 'dusk'),
    B(1, ['no', 'receipts'], 'NO RECEIPTS. NO RECORDS.', 'memory against memory', 'letter'),
    B(1, ['holding', 'the', 'paper'], 'THE MAN HOLDING PAPER WINS', 'not the man shouting louder', 'court'),
    B(1, ['this', 'is', 'docoga'], 'DOCOGA', "Nigeria's document engine", 'clip:money-count'),
    # ── Scene 2: What a Receipt Is ──
    B(2, None, 'WHAT A RECEIPT IS', 'and what it is not', 'letter'),
    B(2, ['acknowledgement', 'of', 'payment'], 'AN ACKNOWLEDGEMENT', 'money moved. how much. what for.', 'pen'),
    B(2, ['it', 'is', 'not', 'a', 'contract'], 'NOT A CONTRACT', 'your agreement does that job', 'clip:sign-document'),
    B(2, ['who', 'can', 'issue'], 'WHO MAY ISSUE ONE?', 'the named landlord — or an agent in writing', 'court'),
    B(2, ['the', 'caretaker'], 'NOT THE CARETAKER', 'not the son abroad. not a stranger.', 'keke'),
    # ── Scene 3: The Seven Lines ──
    B(3, None, 'SEVEN LINES OF PROOF', 'count them on your fingers', 'pen'),
    B(3, ['one', 'the', 'date'], 'ONE — THE DATE', '"when" is often the whole fight', 'calendar'),
    B(3, ['two', 'and', 'three'], 'TWO + THREE — THE PARTIES', 'full names, matching your agreement', 'letter'),
    B(3, ['figures', 'and', 'in', 'words'], 'FOUR — FIGURES AND WORDS', 'never "as agreed"', 'clip:money-count'),
    B(3, ['the', 'word', 'rent'], 'FIVE — THE PURPOSE', 'not a gift. not a loan. rent.', 'pen'),
    B(3, ['which', 'month'], 'SIX — THE PERIOD COVERED', 'which month. which year of the tenancy.', 'calendar'),
    B(3, ['seven', 'the', 'signature'], 'SEVEN — THE SIGNATURE', 'of the receiver', 'clip:sign-document'),
    B(3, ['thirty', 'seconds', 'to', 'write'], 'THIRTY SECONDS TO WRITE', 'years of arguments prevented', 'market'),
    # ── Scene 4: The Quiet Traps ──
    B(4, None, 'THE QUIET TRAPS', 'how Nigerians lose their own proof', 'dusk'),
    B(4, ['the', 'receipt', 'says'], 'THE WRONG-NAME RECEIPT', 'landlord is Mr Ade — receipt says Tunde', 'keke'),
    B(4, ['part', 'payment'], 'PART PAYMENT, NO RECEIPT', 'the first half vanishes with the second', 'letter'),
    B(4, ['receipt', 'later'], '"I WILL GIVE YOU LATER"', 'later is where receipts go to die', 'dusk'),
    B(4, ["agent's", 'personal', 'account'], "THE AGENT'S ACCOUNT", '"he never received a kobo" — and he is right', 'court'),
    B(4, ['nobody', 'receipts', 'year', 'two'], 'THE RENEWAL TRAP', '"we already have an understanding"', 'market'),
    # ── Scene 5: The Paper Family ──
    B(5, None, 'THE PAPER-TRAIL FAMILY', 'agreement. receipts. notice.', 'clip:sign-document'),
    B(5, ['claims', 'arrears'], 'CLAIM: "HE OWES RENT"', 'answer: your receipts — dated, matched', 'court'),
    B(5, ['tenancy', 'never', 'existed'], 'CLAIM: "NO TENANCY"', 'answer: the agreement plus the receipts', 'letter'),
    B(5, ['what', 'rent', 'applied'], 'CLAIM: "WRONG RENT"', 'answer: the year-three receipt, in words', 'clip:money-count'),
    B(5, ['who', 'is', 'holding', 'proof'], 'THE FIGHT IS NOT ABOUT SHOUTING', 'it is about who holds proof', 'court'),
    # ── Scene 6: Myths, Killed ──
    B(6, None, 'MYTHS, KILLED', 'three lies that cost tenants money', 'danfo'),
    B(6, ['paid', 'in', 'cash'], '"I PAID CASH — NO RECEIPT"', 'cash is when you need one most', 'clip:money-count'),
    B(6, ['receipts', 'are', 'for', 'businesses'], '"RECEIPTS ARE FOR BUSINESSES"', 'disputes happen at the end, not the start', 'market'),
    B(6, ['the', 'bank', 'record'], '"THE ALERT IS MY RECEIPT"', 'it proves movement — not purpose', 'phone'),
    # ── Scene 7: Digital Proof ──
    B(7, None, 'DIGITAL PROOF', 'where Nigerian tenants live now', 'phone'),
    B(7, ['record', 'is', 'strong'], 'THE BANK PROVES MOVEMENT', 'only the receipt names the purpose', 'court'),
    B(7, ['message', 'that', 'says'], 'THE PERFECT MESSAGE', '"received rent for Flat 4, January to December"', 'phone'),
    B(7, ['photograph', 'it', 'the', 'day'], 'PHOTOGRAPH IT THE SAME DAY', 'keep the original where fire cannot reach', 'pen'),
    B(7, ['two', 'places'], 'KEEP EVERYTHING TWICE', 'proof in two places survives one disaster', 'letter'),
    # ── Scene 8: What To Do Now ──
    B(8, None, 'WHAT TO DO RIGHT NOW', 'even if years sit unreceipted', 'dusk'),
    B(8, ['write', 'to', 'the', 'person'], 'THE BACKFILL LETTER', 'confirm past payments — in writing', 'letter'),
    B(8, ['they', 'refuse', 'or', 'stay'], 'REFUSAL IS INFORMATION', 'fix your future fast', 'keke'),
    B(8, ['never', 'move', 'money'], 'NEVER AGAIN WITHOUT ONE', 'every payment. every part. receipted.', 'clip:money-count'),
    B(8, ['drafted', 'and', 'they', 'signed'], 'DRAFT IT YOURSELF', 'a receipt you wrote beats no receipt', 'pen'),
    B(8, ['landlord', 'watching', 'this'], 'LANDLORDS — YOU TOO', 'a receipt book prevents a court season', 'court'),
    # ── Scene 9: The Close ──
    B(9, None, 'THE RENT RECEIPT', 'not paper. your money, wearing proof.', 'clip:money-count'),
    B(9, ['two', 'minutes'], 'BUILT ON YOUR PHONE', 'figures to words. automatic. balance line.', 'pen'),
    B(9, ['print', 'it'], 'PRINT IT. OR SAVE IT.', 'hand it over for signature', 'clip:sign-document'),
    B(9, ['free', 'to', 'start'], 'FREE TO START', 'no signup. no card.', 'clip:celebration'),
    B(9, ['docoga', 'dot', 'com'], 'DOCOGA', 'docoga.com.ng — link in the description', 'clip:celebration', endcard=True),
]


def seg_cmd(path):
    return [FF, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
            '-i', '-', '-c:v', 'libx264', '-preset', 'faster', '-crf', '21',
            '-pix_fmt', 'yuv420p', path]


def render_scene(n, words, secs, by_sec):
    os.makedirs(OUT, exist_ok=True)
    sec = [s for s in secs if s['sec'] == n][0]
    t0, t1 = sec['start'], sec['end']
    dur = t1 - t0
    nf = int(round(dur * FPS))
    beats = [b for b in BEATS if b['sec'] == n]
    sw = by_sec[n]

    # Build caption groups
    caps = []
    _grp = []
    for _wi, _w in enumerate(sw):
        _grp.append(_w)
        _nxt = sw[_wi + 1] if _wi + 1 < len(sw) else None
        _pause = (_nxt['t0'] - _w['t1']) if _nxt else 1.0
        if len(_grp) >= 8 or (_pause > 0.55 and len(_grp) >= 4) or _nxt is None:
            _text = ' '.join(x['w'] for x in _grp)
            _f = font('Medium', 40)
            if _f.getlength(_text) > 1500:
                _best, _bdiff = None, 1e18
                for _k in range(3, len(_grp) - 2):
                    _l1 = ' '.join(x['w'] for x in _grp[:_k])
                    _l2 = ' '.join(x['w'] for x in _grp[_k:])
                    _diff = abs(_f.getlength(_l1) - _f.getlength(_l2))
                    if _diff < _bdiff:
                        _best, _bdiff = (_l1, _l2), _diff
                _lines = list(_best)
            else:
                _lines = [_text]
            caps.append((_grp[0]['t0'], _grp[-1]['t1'] + 0.25, _lines))
            _grp = []

    # Build beat spans
    spans = []
    for i, b in enumerate(beats):
        if b['trig'] is None:
            st = t0; st_i = 0
        else:
            st_i = find_idx(sw, b['trig'], spans[-1][2] if spans else 0)
            st = sw[st_i]['t0'] if st_i is not None else t0
        spans.append((b, st, st_i if st_i is not None else 0))

    # Build layers
    layers = []
    for b, st, si in spans:
        lay = endcard_layer() if b['endcard'] else beat_layer(
            b['head'], b['sub'], b['accent'], b['color'], b.get('center', False), top=bool(b.get('rows')))
        layers.append((b, st, lay))

    kicker_f = font('SemiBold', 30)
    label_f = font('SemiBold', 28)
    cap_f   = font('Medium', 40)
    clip_reader = None

    proc = subprocess.Popen(seg_cmd(f'{OUT}/s{n}.mp4'), stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for fi in range(nf):
        t = t0 + fi / FPS
        gt = t - t0
        cur, cur_st, cur_lay = layers[-1]
        for b, st, lay in layers:
            if t >= st:
                cur, cur_st, cur_lay = b, st, lay

        frame = base_plate()

        if cur['img']:
            if str(cur['img']).startswith('clip:'):
                cname = str(cur['img'])[5:]
                if clip_reader is None or clip_reader.name != cname:
                    if clip_reader: clip_reader.close()
                    clip_reader = ClipReader(cname)
                frame = clip_reader.frame().copy()
                frame.paste(NAVY, (0, 0), left_grad())
            else:
                im = treated(cur['img'])
                u = min(1.0, (t - cur_st) / max(0.001, (t1 - cur_st)))
                d = 1 if (BEATS.index(cur) % 2 == 0) else -1
                zw = int(W - 85 * u); zh = int(H - 48 * u)
                px = max(0, min(2400 - zw, int(110 + u * d * 260)))
                py = max(0, min(1350 - zh, int(60 + u * d * 120)))
                frame.paste(im.crop((px, py, px + zw, py + zh)).resize((W, H), Image.BILINEAR), (0, 0))
                frame.paste(NAVY, (0, 0), left_grad())

        # beat layer with fade-in
        a = max(0, min(255, int(255 * (t - cur_st) / 0.4))) if cur_st > t0 or cur['trig'] else 255
        lay = cur_lay
        if a < 255:
            lay = lay.copy()
            al = lay.getchannel('A').point(lambda p: p * a // 255)
            lay.putalpha(al)
        frame.paste(lay, (0, 0), lay)

        # rows
        if cur['rows']:
            shown = 0; last_t = t0
            for rt in cur['row_trigs']:
                ri = find_idx(sw, rt, 0)
                if ri is not None and sw[ri]['t0'] <= t:
                    shown += 1; last_t = sw[ri]['t0']
            if shown:
                rlay = rows_layer(cur['rows'], shown)
                ra = max(0, min(255, int(255 * (t - last_t) / 0.35)))
                if ra < 255:
                    al = rlay.getchannel('A').point(lambda p: p * ra // 255)
                    rlay.putalpha(al)
                frame.paste(rlay, (0, 0), rlay)

        # kicker + scene label
        d = ImageDraw.Draw(frame)
        d.text((70, 52), 'DOCOGA — DEEP-DIVE \u00B7 EPISODE 1', font=kicker_f, fill=FAINT)
        lab = f'{n} \u00B7 {SEC_TITLES[n-1].upper()}'
        d.text((W - 70 - label_f.getlength(lab), 56), lab, font=label_f, fill=FAINT)

        # captions
        cap = None
        for cg in caps:
            if cg[0] <= t < cg[1]:
                cap = cg; break
        if cap is None and caps and t >= caps[-1][1]:
            cap = caps[-1]
        if cap is not None:
            lines = cap[2]
            a2 = max(0.0, min(1.0, (t - cap[0]) / 0.18)) * max(0.0, min(1.0, (cap[1] - t) / 0.18 + 1.0))
            bh = 34 + len(lines) * 50
            d.rectangle([W//2 - 810, 986 - bh, W//2 + 810, 986], fill=(4, 16, 33, int(205 * a2)))
            for li, ln in enumerate(lines):
                lw = cap_f.getlength(ln)
                col = (255, 255, 255, int(255 * a2))
                d.text(((W - lw) / 2, 1002 - bh + 16 + li * 50), ln, font=cap_f, fill=col)

        # progress bar
        total = secs[-1]['end']
        d.rectangle([0, H - 6, int(W * t / total), H], fill=YELLOW)

        proc.stdin.write(frame.tobytes())

    if clip_reader:
        clip_reader.close()
    proc.stdin.close()
    proc.wait()
    return f'{OUT}/s{n}.mp4'


def build_all():
    words, secs, by_sec = load()
    for n in range(1, 10):
        p = render_scene(n, words, secs, by_sec)
        print(f'scene {n} done', flush=True)

    lst = f'{OUT}/list.txt'
    open(lst, 'w').write('\n'.join(f"file '{OUT}/s{i}.mp4'" for i in range(1, 10)))
    final = f'{ROOT}/build/dd4-episode.mp4'
    os.makedirs(os.path.dirname(final), exist_ok=True)

    subprocess.run([FF, '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy',
                    f'{OUT}/video.mp4'], check=True)
    subprocess.run([FF, '-y', '-i', f'{OUT}/video.mp4', '-i', f'{ROOT}/renders/dd4-vo-master.mp3',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart',
                    final], check=True)
    print('FINAL:', final)


def cover():
    c = Image.new('RGB', (1280, 720), NAVY)
    try:
        im = treated('pen').crop((560, 150, 560 + 1280, 150 + 720)).resize((700, 720), Image.LANCZOS)
        c.paste(im, (580, 0))
        g = left_grad().resize((1280, 720))
        c.paste(NAVY, (0, 0), g)
    except Exception:
        pass
    d = ImageDraw.Draw(c)
    X = 66
    d.text((X, 52), 'THE LANDLORD SAYS:', font=font('SemiBold', 36), fill=MUTED)
    f1 = font('Black', 104)
    d.text((X, 96), '"YOU NEVER', font=f1, fill=WHITE)
    d.text((X, 216), 'PAID ME."', font=f1, fill=WHITE)
    f2 = font('Black', 88)
    tw = d.textlength('THE RECEIPT WINS', font=f2)
    d.rectangle([X - 14, 392, X + tw + 26, 392 + 120], fill=YELLOW)
    d.text((X, 398), 'THE RECEIPT WINS', font=f2, fill=NAVY)
    d.rectangle([X, 548, X + 180, 556], fill=BLUE)
    d.text((X, 576), 'THE RENT RECEIPT', font=font('Bold', 42), fill=WHITE)
    d.text((X, 648), 'your money, wearing proof', font=font('SemiBold', 30), fill=MUTED)
    d.text((X, 688), 'DOCOGA', font=font('Bold', 28), fill=FAINT)
    os.makedirs(f'{ROOT}/renders', exist_ok=True)
    c.save(f'{ROOT}/renders/dd4-cover.jpg', quality=92)
    print('cover saved')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: make_longform_dd4.py scene N | all | cover')
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'cover':
        cover()
    elif cmd == 'scene':
        render_scene(int(sys.argv[2]), *load())
    elif cmd == 'all':
        build_all()
    else:
        print(f'Unknown command: {cmd}')
        sys.exit(1)