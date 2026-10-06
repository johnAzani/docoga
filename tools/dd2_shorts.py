#!/usr/bin/env python3
"""
DD2 SHORTS A/B/C — vertical 1080x1920 kinetic-typography cuts, full DD2 chunk voice.

Law compliance: REEL 4 v12 embedded-cover law (hook card + PAD before speech starts),
v9 VIS_LEAD word-level sync from REAL ASR (renders/dd2-words.json), REEL 3 primitives,
no emoji, typed DOCOGA kicker, docoga.com.ng end button, "Free to start. No signup.
No card."  Self-provisions ffmpeg (recycle-proof).  Audio: chunk + PAD lead + loudnorm -16.

Outputs: renders/dd2short-{a,b,c}.mp4
"""
import json, math, os, re, subprocess, sys

ROOT = '/home/user/docoga'
FF   = f'{ROOT}/tools/bin/ffmpeg'

# Self-provision ffmpeg if missing
if not os.path.exists(FF):
    try:
        import imageio_ffmpeg, shutil
    except ImportError:
        subprocess.run(['pip3', 'install', '-q', '--break-system-packages', 'imageio-ffmpeg'])
        import imageio_ffmpeg, shutil
    os.makedirs(os.path.dirname(FF), exist_ok=True)
    shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(), FF)
    os.chmod(FF, 0o755)

from PIL import Image, ImageDraw, ImageChops, ImageFont
import numpy as np

W, H, FPS, CX = 1080, 1920, 30, 540
MAXW = 860
NAVY  = (6, 26, 51);  NAVY2 = (12, 38, 70);  PANEL = (15, 61, 124)
WHITE, MUTED, FAINT  = (255, 255, 255), (143, 168, 201), (96, 128, 170)
BLUE, YELLOW, RED, GREEN = (74, 140, 255), (255, 201, 60), (255, 90, 95), (46, 204, 113)
FONT_PATH = f'{ROOT}/tools/fonts/Inter-Variable.ttf'
PAD     = 2.6          # hook-card lead before speech (embedded-cover law)
TAIL    = 1.0          # end-card hold after speech
VIS_LEAD = 0.07

_fc = {}
def font(w, sz):
    key = (w, sz)
    if key not in _fc:
        f = ImageFont.truetype(FONT_PATH, sz)
        try: f.set_variation_by_name(w)
        except Exception: pass
        _fc[key] = f
    return _fc[key]

def ease_cubic(p): return 1 - (1 - p) ** 3
def ease_back(p, s=1.70158):
    p -= 1; return p * p * ((s + 1) * p + s) + 1
def lerp_c(c1, c2, t): return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

def ctext(d, cx, y, text, f, fill):
    w = d.textbbox((0, 0), text, font=f)[2]
    d.text((cx - w // 2, y), text, font=f, fill=fill)
    return w

def tracked_w(d, text, f, tr):
    return sum(d.textlength(ch, font=f) + tr for ch in text) - tr

def ctracked(d, cx, y, text, f, fill, tr=6):
    x = cx - tracked_w(d, text, f, tr) / 2
    for ch in text:
        if ch != ' ':
            d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + tr

def fit(d, text, w, sz, max_w=MAXW):
    while sz > 30:
        f = font(w, sz)
        if d.textbbox((0, 0), text, font=f)[2] <= max_w:
            return f
        sz -= 4
    return font(w, sz)

def ctext_drop(d, lt, t0, stag, text, f, y, fill, dy=30):
    if lt < t0: return
    x = CX - (sum(d.textlength(ch, font=f) for ch in text)) / 2
    for k, ch in enumerate(text):
        p = (lt - t0 - k * stag) / 0.30
        if p > 0:
            p = min(1.0, p)
            yy = y + int(dy * (1 - ease_back(p, 1.2)))
            col = lerp_c(NAVY2, fill, min(1, p * 1.7))
            if ch != ' ':
                d.text((x, yy), ch, font=f, fill=col)
        x += d.textlength(ch, font=f)

def kicker_in(d, lt, t0, y, text, sz, fill):
    if lt < t0: return
    p = min(1.0, (lt - t0) / 0.35)
    tr = int(18 - 12 * ease_cubic(p))
    col = lerp_c(NAVY2, fill, min(1.0, (lt - t0) / 0.30))
    ctracked(d, CX, y, text, font('SemiBold', sz), col, tr)

def badge(d, cx, cy, r, color, kind, pop=1.0):
    r = int(r * max(0.05, pop))
    if r < 4: return
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    lw = max(8, int(r * 0.26))
    if kind == 'check':
        d.line([(cx - r * .45, cy + r * .02), (cx - r * .08, cy + r * .38),
                (cx + r * .5, cy - r * .32)], fill=WHITE, width=lw, joint='curve')
    elif kind == 'x':
        d.line([(cx - r * .38, cy - r * .38), (cx + r * .38, cy + r * .38)], fill=WHITE, width=lw)
        d.line([(cx + r * .38, cy - r * .38), (cx - r * .38, cy + r * .38)], fill=WHITE, width=lw)
    else:  # number
        n = font('Black', int(r * 1.1))
        tw = d.textlength(kind, font=n)
        d.text((cx - tw / 2, cy - r * 0.62), kind, font=n, fill=NAVY)

def ring(d, cx, cy, r, p, color):
    if p <= 0 or p >= 1: return
    rr = int(r + 130 * ease_cubic(p))
    wdt = max(2, int(9 * (1 - p)))
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
              outline=lerp_c(color, NAVY2, p), width=wdt)

def underline_sweep(d, lt, t0, text, f, y, color=YELLOW):
    if lt <= t0: return
    g = ease_cubic(min(1.0, (lt - t0) / 0.40))
    tw = d.textbbox((0, 0), text, font=f)[2] * 0.92
    d.rectangle([CX - tw / 2, y, CX - tw / 2 + tw * g, y + 12], fill=color)

def end_button(d, lt, t0, by):
    p = min(1.0, max(0.0, (lt - t0) / 0.5))
    if p <= 0: return
    yy = by + int(40 * (1 - ease_back(p)))
    d.rounded_rectangle([CX - 320 + 10, yy + 10, CX + 320 + 10, yy + 118 + 10], 54, fill=PANEL)
    d.rounded_rectangle([CX - 320, yy, CX + 320, yy + 118], 54, fill=WHITE)
    fb = font('Bold', 46)
    tw = d.textbbox((0, 0), 'docoga.com.ng', font=fb)[2]
    d.text((CX - tw // 2, yy + 34), 'docoga.com.ng', font=fb, fill=NAVY)
    b = 0.5 + 0.5 * math.sin(2 * math.pi * (lt - t0) / 1.1)
    d.rounded_rectangle([CX - 329, yy - 8, CX + 329, yy + 126], 59,
                        outline=lerp_c((28, 88, 180), BLUE, b), width=5)

def build_base():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - CX) / 620.0) ** 2 + ((yy - 760) / 760.0) ** 2)
    b = 1.0 + 0.15 * np.exp(-r ** 2 / 0.5) - 0.15 * (r / 1.9) ** 2.2
    b = np.clip(b, 0.83, 1.15)[..., None]
    arr = np.clip(np.array(NAVY, dtype=np.float32) * b, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    d = ImageDraw.Draw(img)
    dot = tuple(min(255, c + 9) for c in NAVY)
    for gy in range(36, H, 72):
        for gx in range(36, W, 72):
            d.ellipse([gx - 2, gy - 2, gx + 2, gy + 2], fill=dot)
    return img

BASE = build_base()
WHITE_IMG = Image.new('RGB', (W, H), WHITE)

def zoom(img, s):
    if abs(s - 1.0) < 0.001: return img
    w2, h2 = int(W / s), int(H / s)
    x0, y0 = (W - w2) // 2, (H - h2) // 2
    return img.crop((x0, y0, x0 + w2, y0 + h2)).resize((W, H), Image.BICUBIC)

def envelope(img, lt, dur, is_last):
    if lt < 0.5:
        img = zoom(img, 1.045 - 0.045 * ease_cubic(lt / 0.5))
    if not is_last and lt > dur - 0.22:
        p = (lt - (dur - 0.22)) / 0.22
        img = zoom(img, 1.0 + 0.06 * ease_cubic(p))
        img = Image.blend(img, BASE, min(1.0, ease_cubic(p)))
    if lt < 0.09:
        img = Image.blend(img, WHITE_IMG, 0.30 * (1 - lt / 0.09))
    return img

def apply_shake(img, lt, impacts):
    for ti in impacts:
        dt = lt - ti
        if 0 <= dt < 0.24:
            a = 1 - dt / 0.24
            dx = int(6 * a * math.sin(46 * dt))
            dy = int(4 * a * math.cos(39 * dt))
            return ImageChops.offset(img, dx, dy)
    return img


# ── card renderer: one layout, data-driven ──────────────────────────────
def make_card(spec):
    """spec keys: num, kicker, head, head2, sub, sub2, kick2, sweep, xbadge, end."""
    def draw(d, img, lt, dur):
        impacts = []
        y_head = 560
        if spec.get('num'):
            p = min(1.0, max(0.0, (lt - 0.10) / 0.35))
            badge(d, CX, 330, 74, YELLOW, str(spec['num']), p)
            if p > 0: ring(d, CX, 330, 74, p, YELLOW)
            y_head = 620
        if spec.get('xbadge'):
            p = min(1.0, max(0.0, (lt - 0.10) / 0.35))
            badge(d, CX, 330, 74, RED, spec['xbadge'], p)
            if p > 0: ring(d, CX, 330, 74, p, RED)
            y_head = 620
        if spec.get('kicker'):
            kicker_in(d, lt, 0.05, y_head - 140, spec['kicker'], 30, BLUE)
        if spec.get('head'):
            f = fit(d, spec['head'], 'Black', 118)
            ctext_drop(d, lt, 0.35, 0.05, spec['head'], f, y_head, WHITE)
            impacts.append(0.35)
            if spec.get('sweep'):
                underline_sweep(d, lt, 1.15, spec['head'], f, y_head + int(f.size * 1.18))
        if spec.get('head2'):
            f2 = fit(d, spec['head2'], 'Black', 92)
            ctext_drop(d, lt, 1.0, 0.05, spec['head2'], f2, y_head + 150, YELLOW)
        if spec.get('sub'):
            ctext_drop(d, lt, 1.7, 0.04, spec['sub'], font('Light', 52), y_head + 300, MUTED)
        if spec.get('sub2'):
            ctext_drop(d, lt, 2.2, 0.04, spec['sub2'], font('Light', 52), y_head + 380, MUTED)
        if spec.get('kick2'):
            kicker_in(d, lt, 2.6, y_head + 470, spec['kick2'], 28, FAINT)
        if spec.get('end'):
            end_button(d, lt, 2.2, 880)
            if lt > 2.9:
                ctext(d, CX, 1050, 'Free to start. No signup. No card.',
                      font('Light', 42), lerp_c(NAVY2, MUTED, min(1, (lt - 2.9) / 0.35)))
            kicker_in(d, lt, 3.4, 1150, 'FULL EPISODE PREMIERES MONDAY, 6PM', 26, YELLOW)
            kicker_in(d, lt, 3.6, 1198, 'DOCOGA', 24, FAINT)
        return impacts
    return draw


# ── the three shorts ────────────────────────────────────────────────────
SHORTS = {
    'b': dict(chunk=3, title='ONLY 4 THINGS DEDUCTABLE', cards=[
        dict(kicker='THE RULE THAT DECIDES EVERYTHING', head='WHAT CAN HE', head2='LEGALLY DEDUCT?',
             sub='when you move out'),
        dict(kicker='THE LAW SAYS', head='ONLY FOUR THINGS.', sweep=True),
        dict(num=1, head='DAMAGE BEYOND', head2='FAIR WEAR AND TEAR', kick2='PHOTOS OR ITEMISED REPAIR COST'),
        dict(num=2, head='UNPAID RENT.'),
        dict(num=3, head='UNPAID UTILITIES', kick2='LIGHT, WATER, SERVICE CHARGE, WASTE'),
        dict(num=4, head='BREACH COSTS', kick2='ONLY IF WRITTEN INTO THE AGREEMENT'),
        dict(kicker='EVERYTHING ELSE', head='MUST BE REFUNDED.', sweep=True),
        dict(xbadge='x', kicker='FAIR WEAR AND TEAR IS NOT DAMAGE', head='FADED PAINT. WORN TAP.',
             head2='NOT DAMAGE.', sub='the landlord\u2019s cost — not yours'),
        dict(xbadge='x', kicker='THAT IS DAMAGE', head='A BROKEN WINDOW.', head2='A BURNT SOCKET.',
             sub='those may come out of the deposit'),
        dict(kicker='THE RULE IN ONE LINE', head='LISTED. AND PROVED.', sub='every deduction, proved — or refunded',
             end=True),
    ], trigs=[None, ['only','four','things'], ['damage','beyond','fair'], ['unpaid','rent'],
              ['unpaid','utility','bills'], ['breach','costs'],
              ['everything','else','must'], ['a','room','that','faded'], ['a','broken','window'],
              ['the','rule','in','one','line']]),
    'c': dict(chunk=8, title='THE LADDER', cards=[
        dict(kicker='HE REFUSES TO REFUND', head='THE LADDER.', head2='CLIMB IT IN ORDER'),
        dict(num=1, kicker='STEP ONE', head='ASK IN WRITING.', sub='dated demand letter · 7–14 day deadline',
             kick2='MOST DISPUTES DIE ON THIS STEP'),
        dict(num=2, kicker='STEP TWO', head='WITNESSES + MEDIATION.', sub='tenant associations · agents · community leaders'),
        dict(num=3, kicker='STEP THREE', head='THE MAGISTRATES\u2019 COURT.', sub='a simple money claim — the file does the talking'),
        dict(kicker='THROUGH EVERY STEP', head='DOCUMENT EVERYTHING.', sub='dates · names · messages · receipts',
             kick2='WHOEVER KEPT THE PAPERWORK WINS'),
        dict(kicker='THE LADDER WINS', head='PAPERWORK. NOT NOISE.', sweep=True, end=True),
    ], trigs=[None, ['step','one'], ['step','two'], ['step','three'], ['document','everything'],
              ['whoever','kept','the','paperwork']]),
    'a': dict(chunk=9, title='DO THIS RIGHT NOW', cards=[
        dict(kicker='HE IS HOLDING YOUR DEPOSIT', head='DO THIS.', head2='RIGHT NOW.'),
        dict(kicker='PAYING A CAUTION FEE?', head='NEVER CASH', head2='AND HOPE.', sub='receipt it separately — same day',
             kick2='REFUND CLAUSE + DEADLINE + MOVE-IN RECORD'),
        dict(kicker='OWED A REFUND?', head='SEND THE DEMAND.', head2='THIS WEEK.', sub='seven-day deadline — then climb the ladder'),
        dict(kicker='ARE YOU THE LANDLORD?', head='HOLD IT', head2='THE LAWFUL WAY.', sub='separate receipt · signed record · refund on time',
             kick2='A REFUND REPUTATION IS THE CHEAPEST VACANCY ADVERT'),
        dict(kicker='YOUR DEPOSIT IS NOT GONE', head='IT IS YOUR MONEY.', sweep=True, sub='go and get it', end=True),
    ], trigs=[None, ['paying','a','caution','fee'], ['owed','a','refund'], ['if','you','are','a','landlord'],
              ['your','deposit','is','not','gone']]),
}


def norm(w):
    return ''.join(c for c in w.lower() if c.isalnum() or c == "'")


def load_words():
    sys.path.insert(0, f'{ROOT}/tools')
    # Try to import the longform engine; fall back to json
    try:
        import make_longform_dd2 as eng
        words, secs, by_sec = eng.load()
        return secs, by_sec
    except ImportError:
        # Fallback: load from renders/dd2-words.json
        wj = f'{ROOT}/renders/dd2-words.json'
        if os.path.exists(wj):
            data = json.load(open(wj))
            words = data.get('words', [])
            secs = data.get('sections', [])
            by_sec = {}
            for w in words:
                by_sec.setdefault(w.get('sec', 0), []).append(w)
            return secs, by_sec
        print(f'❌ No word data found. Run dd2_align.py first or provide renders/dd2-words.json')
        sys.exit(1)


def chunk_words(by_sec, n):
    return by_sec.get(n, [])


def trig_time(ws, trig):
    if trig is None:
        return 0.0
    n = [norm(w['w']) for w in ws]
    L = len(trig)
    for i in range(len(n) - L + 1):
        if n[i:i + L] == trig:
            return ws[i]['t0']
    return None


def build(short_key):
    spec = SHORTS[short_key]
    n = spec['chunk']
    secs, by_sec = load_words()
    sec = [s for s in secs if s['sec'] == n][0]
    ws = chunk_words(by_sec, n)
    start = sec['start']
    end = sec['end']
    audio_dur = (end - start) + TAIL
    total = PAD + audio_dur

    # scene boundaries from triggers
    times = []
    for t in spec['trigs']:
        tt = trig_time(ws, t)
        if tt is None:
            print(f'  WARN: trigger {t} not found — even fallback')
            times.append(None)
        else:
            times.append(tt - start + PAD - VIS_LEAD)

    bounds, prev = [], PAD * 0.72
    for i, tt in enumerate(times):
        if tt is None:
            continue
        s = max(prev, tt)
        bounds.append((s, i))
        prev = s

    # ensure min scene length 1.8s
    fixed = []
    for k, (s, i) in enumerate(bounds):
        e = bounds[k + 1][0] if k + 1 < len(bounds) else total
        fixed.append((s, i, e))
    for k in range(len(fixed) - 1):
        if fixed[k][2] - fixed[k][0] < 1.8:
            shift = 1.8 - (fixed[k][2] - fixed[k][0])
            for j in range(k + 1, len(fixed)):
                fixed[j] = (fixed[j][0] + shift, fixed[j][1], fixed[j][2] + shift)

    scenes = []
    for s, i, e in fixed:
        scenes.append((min(e, total) - s, make_card(spec['cards'][i])))
    # hook card: from 0 to first bound
    first_b = fixed[0][0] if fixed else PAD
    scenes.insert(0, (first_b, make_card(spec['cards'][0])))

    print(f'  short {short_key.upper()}: {len(scenes)} cards, {total:.1f}s, voice chunk c{n}')

    # Render frames
    frames_dir = f'/tmp/short_{short_key}'
    os.makedirs(frames_dir, exist_ok=True)
    nf = int(total * FPS)
    cum, b0 = [], 0.0
    for dur, _ in scenes:
        cum.append((b0, b0 + dur))
        b0 += dur

    for i in range(nf):
        t = i / FPS
        si = max(k for k, (aa, bb) in enumerate(cum) if aa <= t < bb or (k == len(cum) - 1 and t >= bb))
        aa, bb = cum[si]
        lt = min(t - aa, scenes[si][0])
        img = BASE.copy()
        d = ImageDraw.Draw(img)
        impacts = scenes[si][1](d, img, lt, scenes[si][0]) or []
        img = apply_shake(img, lt, impacts)
        img = envelope(img, lt, scenes[si][0], si == len(scenes) - 1)
        img.save(f'{frames_dir}/f_{i:04d}.png')
        if i % 150 == 0:
            print(f'    frame {i}/{nf}')

    # Encode silent video
    vid = f'{frames_dir}/vid.mp4'
    r = subprocess.run([FF, '-y', '-framerate', str(FPS), '-i', f'{frames_dir}/f_%04d.png',
                        '-c:v', 'libx264', '-preset', 'veryfast', '-threads', '2',
                        '-pix_fmt', 'yuv420p', '-crf', '20', '-vf', 'noise=alls=4:allf=t',
                        '-x264-params', 'rc-lookahead=12', '-r', str(FPS), vid],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-400:])
        raise SystemExit('encode failed')

    # Audio: pad + loudnorm
    ms = int(PAD * 1000)
    aud = f'{frames_dir}/aud.m4a'
    r = subprocess.run([FF, '-y', '-i', f'{ROOT}/renders/dd2-c{n}.mp3',
                        '-af', f'adelay={ms}|{ms},loudnorm=I=-16:TP=-1.5:LRA=11',
                        '-ar', '44100', '-c:a', 'aac', '-b:a', '160k', aud],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-400:])
        raise SystemExit('audio failed')

    # Mux
    out = f'{ROOT}/renders/dd2short-{short_key}.mp4'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    r = subprocess.run([FF, '-y', '-i', vid, '-i', aud, '-map', '0:v', '-map', '1:a',
                        '-c:v', 'copy', '-c:a', 'copy', '-shortest',
                        '-movflags', '+faststart', out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-400:])
        raise SystemExit('mux failed')

    subprocess.run(['rm', '-rf', frames_dir])
    print(f'  OK {out} ({os.path.getsize(out)//1024} KB)')


if __name__ == '__main__':
    keys = sys.argv[1:] or ['a', 'b', 'c']
    for k in keys:
        build(k)
    print('DONE')