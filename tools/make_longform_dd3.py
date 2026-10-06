#!/usr/bin/env python3
"""
DOCOGA Deep-Dive long-form engine — 16:9 1920x1080 30fps, word-synced.

Usage:
  python3 tools/make_longform_dd3.py scene N    # render scene N
  python3 tools/make_longform_dd3.py all        # render all 9 scenes + final video
  python3 tools/make_longform_dd3.py cover      # render YouTube thumbnail

DD3 = The Tenancy Agreement: 8 Clauses
Outputs: build/dd3-vid/sN.mp4 segments, renders/dd3-cover.jpg
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

OUT = f'{ROOT}/build/dd3-vid'
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
    "The Hook", "What It Actually Is", "The Parties & The Premises",
    "The Money Clauses", "The Notice Clause", "The Repair Clause",
    "The Myth, Killed", "The Renewal Trap", "The Close"
]


# ──────── data ────────
def norm(w):
    return ''.join(c for c in w.lower() if c.isalnum() or c == "'")


def load():
    d = json.load(open(f'{ROOT}/renders/dd3-words.json'))
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
    B(1, None, 'THE TENANCY AGREEMENT', 'the 8 clauses that decide everything', 'clip:sign-document'),
    B(1, ['where', 'it', 'usually', 'hides'], 'CLAUSE SIX', 'that is where it usually hides', 'letter'),
    B(1, ['never', 'reads', 'the', 'paper'], 'SIGNED. PAID. MOVED IN.', 'and never read the paper again', 'letter'),
    B(1, ['caution', 'fee'], 'EVERYTHING HE LOST', 'two weeks. the deposit. the roof.', 'dusk'),
    B(1, ['entire', 'case'], 'NOT A FORMALITY', 'the entire case — written in advance', 'court'),
    B(1, ['what', 'does', 'the', 'agreement'], 'WHAT DOES THE AGREEMENT SAY?', 'every dispute ends here', 'pen'),
    B(1, ['this', 'is', 'docoga'], 'DOCOGA', "Nigeria's document engine", 'clip:sign-document'),
    # ── Scene 2: What It Actually Is ──
    B(2, None, 'A CONTRACT', 'not a formality. not a receipt. not just paper.', 'letter'),
    B(2, ['statutory', 'defaults'], 'DEFAULTS FILL SILENCE', 'your clause beats the default', 'court'),
    B(2, ['twenty', 'to', 'fifty'], 'DRAFTED BY HIS LAWYER', 'for twenty to fifty thousand naira', 'kiosk'),
    B(2, ['like', 'scripture'], 'SIGNED LIKE SCRIPTURE', 'it is not scripture', 'pen'),
    B(2, ['window', 'closes'], 'THE WINDOW CLOSES', 'read, question, negotiate — before the ink dries', 'pen'),
    B(2, ['no', 'written', 'agreement'], 'NO AGREEMENT = NO PROOF', 'no paper is a choice to lose', 'dusk'),
    # ── Scene 3: The Parties & The Premises ──
    B(3, None, 'CLAUSE 1 — THE PARTIES', 'sounds basic. it is not.', 'rooftops'),
    B(3, ['who', 'exactly', 'is'], 'WHO IS YOUR LANDLORD?', 'not the caretaker. not the agent. not the son abroad.', 'market'),
    B(3, ['written', 'authority'], 'OR AN AGENT — IN WRITING', 'authority you can see', 'letter'),
    B(3, ['hole', 'in', 'it'], 'THE HOLE IN YOUR RENT HISTORY', 'rent paid to the wrong person', 'keke'),
    B(3, ['vague', 'premises'], 'DESCRIBE THE PREMISES', 'the flat, the shop, the parking — in writing', 'door'),
    B(3, ['the', 'named', 'party'], 'PAY THE NAMED PARTY', 'receipts in the same names', 'pen'),
    # ── Scene 4: The Money Clauses ──
    B(4, None, 'CLAUSE 2 — THE MONEY', 'where most agreements fail', 'clip:money-count'),
    B(4, ['in', 'figures', 'and', 'in', 'words'], 'FIGURES AND WORDS', 'never "as agreed"', 'letter'),
    B(4, ['caps', 'advance', 'rent'], 'LAGOS: ONE-YEAR CAP', 'Tenancy Law 2011 — s.4', 'kiosk'),
    B(4, ['smells', 'like'], 'COUNT THE TOTAL', 'if it smells like two years — stop', 'keke'),
    B(4, ['real', 'name'], 'CAUTION FEE — YOUR MONEY', 'amount, purpose, refund terms', 'market'),
    B(4, ['is', 'a', 'donation'], 'NO REFUND CLAUSE = DONATION', 'write the refund into the agreement', 'dusk'),
    B(4, ['request', 'not', 'a', 'debt'], 'NOT IN THE AGREEMENT?', 'a request — not a debt', 'letter'),
    # ── Scene 5: The Notice Clause ──
    B(5, None, 'CLAUSE 3 — THE NOTICE', 'the most powerful line in Nigerian tenancy', 'dusk'),
    B(5, ['more', 'notice', 'than'], 'MORE THAN THE MINIMUM', 'and it can be enforced', 'court'),
    B(5, ['is', 'the', 'floor'], 'THE STATUTE IS THE FLOOR', 'your clause builds above it', 'court'),
    B(5, ['half', 'a', 'year'], 'HALF A YEAR, SIGNED AWAY', "two weeks' notice on a yearly tenancy", 'letter'),
    B(5, ['shot', 'his', 'own'], 'LANDLORDS SHOOT THEIR CASE TOO', 'one month on a yearly tenant', 'keke'),
    B(5, ['one', 'line', 'of', 'drafting'], 'ONE LINE OF DRAFTING', 'months of protection', 'pen'),
    # ── Scene 6: The Repair Clause ──
    B(6, None, 'CLAUSE 4 — REPAIRS', 'who fixes what, in writing', 'generator'),
    B(6, ['keeps', 'the', 'structure'], 'LANDLORD: THE STRUCTURE', 'roof, walls, foundations — the bones', 'rooftops'),
    B(6, ['tenantable', 'repair'], 'TENANT: GOOD REPAIR', 'fair wear and tear excepted', 'ankara'),
    B(6, ['you', 'just', 'bought'], 'READ IT AGAIN', 'or you just bought a roof', 'door'),
    B(6, ['expect', 'a', 'fight'], 'A MUDDY CLAUSE = A FIGHT', 'structural repairs stay with the landlord', 'court'),
    B(6, ['reasonable', 'hours'], 'ACCESS WITH NOTICE', 'reasonable hours of the daytime', 'dusk'),
    # ── Scene 7: The Myth, Killed ──
    B(7, None, 'MYTH: "THAT IS JUST HOW IT IS"', 'the biggest myth in Nigerian renting', 'danfo'),
    B(7, ['negotiation', 'before'], 'A NEGOTIATION FIRST', 'then a document', 'clip:sign-document'),
    B(7, ['changed', 'his', 'own', 'future'], 'EVERY CLAUSE IS A CONVERSATION', 'ask — before you sign', 'market'),
    B(7, ['refusal', 'is', 'information'], 'REFUSAL IS INFORMATION', 'the dispute, shown in advance', 'keke'),
    B(7, ['cheaply', 'now'], 'WALK AWAY CHEAPLY', 'or expensively later', 'dusk'),
    B(7, ['like', 'family'], '"WE ARE LIKE FAMILY"', 'every court story starts that way', 'danfo'),
    # ── Scene 8: The Renewal Trap ──
    B(8, None, 'THE RENEWAL TRAP', 'three checks, sixty days before expiry', 'dusk'),
    B(8, ['automatic', 'renewal'], 'CHECK 1 — AUTO-RENEWAL', 'or you may have bought another year', 'calendar'),
    B(8, ['rent-review', 'clause'], 'CHECK 2 — THE REVIEW CLAUSE', '', 'letter',
      rows=['when rent can be reviewed', 'by how much', 'with what notice'],
      row_trigs=[['when', 'rent', 'can'], ['by', 'how', 'much'], ['with', 'what', 'notice']]),
    B(8, ['tenant', 'at', 'sufferance'], 'CHECK 3 — HOLDOVER', 'tenant at sufferance — the protection changes', 'rooftops'),
    B(8, ['sixty', 'days', 'of', 'attention'], 'SIXTY DAYS OF ATTENTION', 'beats six months of court', 'court'),
    B(8, ['renew', 'in', 'writing'], 'RENEW IN WRITING', 'sign again. receipt again.', 'pen'),
    # ── Scene 9: The Close ──
    B(9, None, 'WHAT TO DO RIGHT NOW', 'read it like it will be read in court', 'clip:sign-document'),
    B(9, ['four', 'that', 'matter'], 'THE FOUR TO NEGOTIATE', '', 'letter',
      rows=['notice', 'refund', 'repairs', 'renewal'],
      row_trigs=[['notice,'], ['refund,'], ['repairs,'], ['renewal.']]),
    B(9, ['living', 'on', 'a', 'bad'], 'ON A BAD AGREEMENT NOW?', 'fix it at the renewal window', 'letter'),
    B(9, ['about', 'two', 'minutes'], 'BUILT ON YOUR PHONE', 'both parties. witness lines. print or PDF.', 'pen'),
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
    final = f'{ROOT}/build/dd3-episode.mp4'
    os.makedirs(os.path.dirname(final), exist_ok=True)

    subprocess.run([FF, '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy',
                    f'{OUT}/video.mp4'], check=True)
    subprocess.run([FF, '-y', '-i', f'{OUT}/video.mp4', '-i', f'{ROOT}/renders/dd3-vo-master.mp3',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart',
                    final], check=True)
    print('FINAL:', final)


def cover():
    c = Image.new('RGB', (1280, 720), NAVY)
    try:
        im = treated('letter').crop((560, 150, 560 + 1280, 150 + 720)).resize((700, 720), Image.LANCZOS)
        c.paste(im, (580, 0))
        g = left_grad().resize((1280, 720))
        c.paste(NAVY, (0, 0), g)
    except Exception:
        pass
    d = ImageDraw.Draw(c)
    X = 66
    d.text((X, 52), 'YOU SIGNED IT', font=font('SemiBold', 36), fill=MUTED)
    f1 = font('Black', 104)
    d.text((X, 96), 'WITHOUT', font=f1, fill=WHITE)
    d.text((X, 216), 'READING?', font=f1, fill=WHITE)
    f2 = font('Black', 100)
    tw = d.textlength('THE 8 CLAUSES', font=f2)
    d.rectangle([X - 14, 386, X + tw + 26, 386 + 132], fill=YELLOW)
    d.text((X, 392), 'THE 8 CLAUSES', font=f2, fill=NAVY)
    d.rectangle([X, 556, X + 180, 564], fill=BLUE)
    d.text((X, 582), 'THE TENANCY AGREEMENT', font=font('Bold', 42), fill=WHITE)
    d.text((X, 654), 'one signature binds you both', font=font('SemiBold', 30), fill=MUTED)
    d.text((X, 692), 'DOCOGA', font=font('Bold', 28), fill=FAINT)
    os.makedirs(f'{ROOT}/renders', exist_ok=True)
    c.save(f'{ROOT}/renders/dd3-cover.jpg', quality=92)
    print('cover saved')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: make_longform_dd3.py scene N | all | cover')
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