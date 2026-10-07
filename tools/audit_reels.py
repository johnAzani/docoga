#!/usr/bin/env python3
"""
audit_reels.py — permanent reel-creator debugger (boss mandate: 100% bug free).

Checks tools/make_reels.py for:
  1. syntax (ast.parse)
  2. arity: every call vs its def, DEFAULT-AWARE
     (positional count within [required, total])
  3. stale references to removed machinery
  4. ASR anchor sanity: every _wf/_wt word lookup in REEL4
     resolves in renders/r4-words.json

Exit 0 = clean; nonzero = bugs found.
Run BEFORE every render.
"""
import ast, io, json, os, re, sys

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = os.path.join(ROOT, 'tools', 'make_reels.py')
FAIL     = []

src = io.open(SRC_PATH, encoding='utf-8').read()

# 1. syntax
try:
    tree = ast.parse(src)
except SyntaxError as e:
    print(f'SYNTAX ERROR line {e.lineno}: {e.msg}'); sys.exit(1)
print('1. syntax: OK')

# 2. arity (default-aware)
defs = {}
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        n_def = len(node.args.defaults)
        total = len(node.args.args)
        req   = total - n_def
        defs[node.name] = (req, total, total + (1 if node.args.kwarg else 0),
                           bool(node.args.vararg))

bad = 0
for node in ast.walk(tree):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in defs):
        req, total, total_kw, has_var = defs[node.func.id]
        got = len(node.args)
        kw_names = {k.arg for k in node.keywords if k.arg}
        ok = (got >= req and got <= total) or has_var
        if not ok:
            bad += 1
            FAIL.append(f'line {node.lineno}: {node.func.id}() {got} args, '
                        f'def wants {req}..{total}')
print(f'2. arity: {"OK — all call sites match" if bad == 0 else f"{bad} MISMATCHES"}')

# 3. stale references
stale  = ['_PANELS', 'load_panel', 'story_panel', '_PID', 'draw_icon', 'ghost_num']
found  = [s for s in stale if s in src]
print(f'3. stale refs: {"OK — none" if not found else found}')
if found:
    FAIL.append('stale: ' + ','.join(found))

# 4. ASR anchors used by REEL4 resolve
wj = os.path.join(ROOT, 'renders', 'r4-words.json')
if os.path.exists(wj):
    W   = json.load(open(wj))['segments']
    pat = re.compile(
        r"_wf\((\d+),\s*'([^']+)'\s*(?:,\s*(\d+))?\)"
        r"|_wt\((\d+),\s*'([^']+)'\s*(?:,\s*(\d+))?\)")
    n = 0
    for m in pat.finditer(src):
        seg = int(m.group(1) or m.group(4))
        txt = m.group(2) or m.group(5)
        occ = int(m.group(3) or m.group(6) or 1)
        if seg >= len(W):
            FAIL.append(f'anchor S{seg:02d} out of range'); continue
        c = sum(1 for w in W[seg]['words'] if w['w'] == txt)
        if c < occ:
            FAIL.append(f'anchor {txt!r} occ{occ} not in S{seg:02d}')
        n += 1
    print(f'4. ASR anchors: {n} lookups, '
          f'{"all resolve" if not any("anchor" in f for f in FAIL) else "FAILURES"}')
else:
    print('4. ASR anchors: words.json missing (will rebuild via align_vosk)')

# 5. every referenced sprite/render path exists on disk
import re as _re
paths   = sorted(set(_re.findall(r"'(renders/[A-Za-z0-9_./-]+)'", src)))
missing = [p for p in paths if not os.path.exists(os.path.join(ROOT, p))]
print(f'5. sprite paths: {len(paths)} referenced, '
      f'{"all exist" if not missing else "MISSING: " + str(missing)}')
if missing:
    FAIL.append('missing sprites: ' + ','.join(missing))

if FAIL:
    print('\nBUGS:')
    [print('  ' + f) for f in FAIL]; sys.exit(1)

print('\nAUDIT CLEAN — safe to render')