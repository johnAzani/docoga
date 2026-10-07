#!/usr/bin/env python3
"""
DOCOGA Deep-Dive long-form engine — 16:9 1920x1080 30fps, word-synced.

Usage:
  python3 tools/make_longform.py scene N    # render scene N
  python3 tools/make_longform.py all        # render all 9 scenes + final video
  python3 tools/make_longform.py cover      # render YouTube thumbnail

Outputs: build/dd2-vid/sN.mp4 segments, renders/dd2-cover.jpg
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

OUT = f'{ROOT}/build/dd2-vid'
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
    "The Hook", "Why the Law Protects You", "The Notice Table", "The Counting Trap",
    "The Five Requirements", "The Myth, Killed", "After the Notice Expires",
    "Self-Help Has No Place", "The Close"
]


# ──────── data ────────
def norm(w):
    return ''.join(c for c in w.lower() if c.isalnum() or c == "'")


def load():
    d = json.load(open(f'{ROOT}/renders/dd2-words.json'))
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
    B(1, None, 'CAUTION FEE', 'the refund war — Deep-Dive 2', 'clip:money-count'),
    B(1, ['two', 'hundred', 'thousand'], 'TWO HUNDRED THOUSAND NAIRA', 'the deposit every tenant fears losing', 'kiosk'),
    B(1, ['gone'], 'GONE.', 'management fee. repainting. admin.', 'dusk'),
    B(1, ['the', 'law', 'does', 'not'], "NOT THE LANDLORD'S MONEY", 'yours — held in security', 'market'),
    B(1, ['paperwork'], 'THE DIFFERENCE IS PAPERWORK', 'not luck', 'letter'),
    B(1, ['this', 'is', 'docoga'], 'DOCOGA', "Nigeria's document engine", 'clip:money-count'),
    B(2, None, 'WHAT A CAUTION FEE IS', 'and what it is not', 'kiosk'),
    B(2, ['not', 'rent'], 'NOT RENT. NOT A GIFT.', "not the landlord's income", 'letter'),
    B(2, ['parked'], 'YOUR MONEY, PARKED', 'against the day you move out', 'clip:money-count'),
    B(2, ['five', 'to', 'ten'], 'THE MARKET NORM: 5-10%', "of annual rent — or 1-3 months'", 'market'),
    B(2, ['push', 'back'], 'HIGH DEMAND, HARD PUSH', 'push back harder', 'danfo'),
    B(2, ['red', 'flag'], "IF THE TOTALS DON'T ADD UP", 'not a negotiation — a red flag', 'keke'),
    B(3, None, 'WHAT A LANDLORD MAY DEDUCT', 'only four things', 'court'),
    B(3, ['four', 'things'], 'THE ONLY FOUR DEDUCTIONS', '', 'court',
      rows=['damage beyond fair wear and tear', 'unpaid rent', 'unpaid utilities', 'written breach costs'],
      row_trigs=[['damage', 'beyond'], ['unpaid', 'rent'], ['light,', 'water'], ['written', 'into']]),
    B(3, ['faded', 'naturally'], "FAIR WEAR AND TEAR", "the landlord's cost — not yours", 'ankara'),
    B(3, ['broken', 'window'], 'A BROKEN WINDOW IS DAMAGE', 'that may come out', 'door'),
    B(3, ['repainting'], 'REPAINTING IS NOT AUTOMATIC', 'unless the walls were actually damaged', 'ankara'),
    B(3, ['listed', 'and', 'proved'], 'LISTED AND PROVED', 'every single naira', 'letter'),
    B(4, None, 'THE RECEIPT', 'the part most tenants skip', 'market'),
    B(4, ['receipted', 'separately'], 'RECEIPT IT SEPARATELY', 'never lump it into the rent figure', 'market'),
    B(4, ['five', 'things'], 'A PROPER RECEIPT: FIVE THINGS', '', 'pen',
      rows=['the parties', 'the property', 'amount — figures and words', 'the date', 'the refund clause'],
      row_trigs=[['names', 'of', 'the'], ['property'], ['in', 'figures'], ['the', 'date'], ['refund', 'clause']]),
    B(4, ['one', 'line'], 'THE REFUND CLAUSE', 'worth more than ten arguments on moving day', 'letter'),
    B(4, ['refund', 'deadline'], 'ADD A REFUND DEADLINE', 'seven to thirty days after handover', 'dusk'),
    B(4, ['whenever', 'the'], 'NO DEADLINE = NEVER', 'state it — in writing', 'dusk'),
    B(5, None, 'FIVE PROTECTIONS', 'set up on payment day', 'clip:artisan'),
    B(5, ['complete', 'armour'], 'THE COMPLETE ARMOUR', 'thirty minutes of work', 'clip:artisan',
      rows=['receipt it separately', 'the written refund clause', 'the refund deadline',
            'the move-in condition record', 'the itemised-deduction clause'],
      row_trigs=[['one', 'receipt'], ['two', 'the'], ['three', 'the'], ['four', 'the'], ['five', 'the']]),
    B(5, ['years', 'of'], 'THIRTY MINUTES OF WORK', 'years of protection afterwards', 'rooftops'),
    B(6, None, 'THE MYTH', 'everyone has heard it', 'danfo'),
    B(6, ['gone', 'money'], 'DEPOSITS NEVER COME BACK?', 'a story told by tenants who lost', 'danfo'),
    B(6, ['held', 'in', 'security'], 'THE LAW SEES IT AS YOURS', 'held in security — not his', 'court'),
    B(6, ['justify', 'every'], 'JUSTIFY EVERY NAIRA', 'or refund it all', 'pen'),
    B(6, ['seizing', 'a', "tenant's"], 'SEIZING YOUR GENERATOR?', 'that is self-help', 'generator'),
    B(6, ['ihenacho'], 'Ihenacho v. Uzochukwu (1997)', 'Supreme Court — self-help is trespass', 'court'),
    B(6, ['paid', 'back', 'twice'], 'RECOVER IT LAWFULLY', 'or pay it back twice', 'generator'),
    B(7, None, 'DOES YOUR STATE CHANGE IT?', 'the deposit rules live in your agreement', 'rooftops'),
    B(7, ['lagos,', 'the'], 'LAGOS: TENANCY LAW 2011', 'advance caps + receipts demanded', 'kiosk'),
    B(7, ['tenancy', 'bill'], 'A NEW BILL IS MOVING', 'a bill — not law. do not quote it yet', 'keke'),
    B(7, ['abuja'], 'ABUJA: RECOVERY OF PREMISES ACT', 'procedure governs possession', 'rooftops'),
    B(7, ['agreement', 'and', 'the'], 'YOUR AGREEMENT IS THE DEPOSIT LAW', 'that matters most', 'letter'),
    B(8, None, 'THE ESCALATION LADDER', 'climb it in order', 'dusk'),
    B(8, ['step', 'one'], 'STEP 1 — THE WRITTEN DEMAND', 'dated letter, 7-14 day deadline', 'letter'),
    B(8, ['step', 'two'], 'STEP 2 — WITNESSES + MEDIATION', 'unions, agents, leaders', 'clip:trader-woman'),
    B(8, ['step', 'three'], "STEP 3 — MAGISTRATES' COURT", 'a simple money claim', 'court'),
    B(8, ['exhibits'], 'YOUR EXHIBITS DO THE TALKING', 'receipt + record + photographs', 'pen'),
    B(8, ['whoever', 'kept'], 'WHOEVER KEEPS THE PAPERWORK WINS', 'not who shouted. not who suffered.', 'clip:money-count'),
    B(9, None, 'WHAT TO DO RIGHT NOW', 'both paths start with paper', 'clip:celebration'),
    B(9, ['paying', 'a', 'caution'], 'PAYING THIS WEEK?', 'receipt + clause + deadline + record', 'market'),
    B(9, ['owed', 'a', 'refund'], 'OWED A REFUND?', 'send the written demand this week', 'letter'),
    B(9, ['hold', 'the', 'deposit'], 'LANDLORD?', 'a refund reputation is the cheapest advert', 'rooftops'),
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
    final = f'{ROOT}/build/dd2-episode.mp4'
    os.makedirs(os.path.dirname(final), exist_ok=True)

    subprocess.run([FF, '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy',
                    f'{OUT}/video.mp4'], check=True)
    subprocess.run([FF, '-y', '-i', f'{OUT}/video.mp4', '-i', f'{ROOT}/renders/dd2-vo-master.mp3',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart',
                    final], check=True)
    print('FINAL:', final)


def cover():
    c = Image.new('RGB', (1280, 720), NAVY)
    try:
        im = treated('kiosk').crop((480, 135, 480 + 1280, 135 + 720)).resize((700, 720), Image.LANCZOS)
        c.paste(im, (580, 0))
        g = left_grad().resize((1280, 720))
        c.paste(NAVY, (0, 0), g)
    except Exception:
        pass
    d = ImageDraw.Draw(c)
    X = 66
    d.text((X, 52), 'AFTER YOU PACK OUT', font=font('SemiBold', 36), fill=MUTED)
    f1 = font('Black', 104)
    d.text((X, 96), 'HE KEEPS', font=f1, fill=WHITE)
    tw = d.textlength('CAUTION FEE', font=f1)
    d.rectangle([X - 14, 210, X + tw + 26, 210 + 132], fill=YELLOW)
    d.text((X, 216), 'CAUTION FEE', font=f1, fill=NAVY)
    d.text((X, 366), 'THE LAW SAYS', font=font('SemiBold', 36), fill=MUTED)
    f2 = font('Black', 84)
    d.text((X, 406), 'ONLY 4 DEDUCTIONS', font=f2, fill=WHITE)
    d.rectangle([X, 546, X + 180, 554], fill=BLUE)
    d.text((X, 572), 'THE DEPOSIT REFUND WAR', font=font('Bold', 42), fill=WHITE)
    d.text((X, 644), 'receipts beat excuses — every time', font=font('SemiBold', 30), fill=MUTED)
    d.text((X, 692), 'DOCOGA', font=font('Bold', 28), fill=FAINT)
    os.makedirs(f'{ROOT}/renders', exist_ok=True)
    c.save(f'{ROOT}/renders/dd2-cover.jpg', quality=92)
    print('cover saved')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: make_longform.py scene N | all | cover')
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