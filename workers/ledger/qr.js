/**
 * qr.js — a small, dependency-free QR encoder for the receipt ledger (19 Oct 2026).
 *
 * Byte mode, error-correction level M, versions 1–6 (up to 106 characters — the check URL is
 * 28–56). The matrix is returned as an SVG so the receipt can inline it without any script on
 * the page (the site's gzip budget is nearly spent). Verified bit-for-bit against the Python
 * `qrcode` library in workers/ledger/test.mjs fixtures (every mask, several lengths).
 *
 * ISO/IEC 18004 essentials implemented: mode/count/terminator/padding, Reed-Solomon over
 * GF(256) with the 0x11D polynomial, block interleaving, finder/separator/timing/alignment/dark
 * modules, BCH(15,5) format information, zigzag placement, all eight masks with the four
 * penalty rules.
 */

// version → [totalCodewords, ecPerBlock, blocks] for level M (ISO 18004 table 9)
const VERSIONS_M = { 1: [26, 10, 1], 2: [44, 16, 1], 3: [70, 26, 1], 4: [100, 18, 2], 5: [134, 24, 2], 6: [172, 16, 4] };
const ALIGN = { 2: 18, 3: 22, 4: 26, 5: 30, 6: 34 };   // single alignment pattern centre for v2–6

const EXP = new Uint8Array(512), LOG = new Uint8Array(256);
(function initGF() {
  let x = 1;
  for (let i = 0; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 0x100) x ^= 0x11D; }
  for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
})();
const mul = (a, b) => (a && b) ? EXP[LOG[a] + LOG[b]] : 0;

function generator(n) {
  let g = [1];
  for (let i = 0; i < n; i++) {
    const next = new Array(g.length + 1).fill(0);
    for (let j = 0; j < g.length; j++) { next[j] ^= g[j]; next[j + 1] ^= mul(g[j], EXP[i]); }
    g = next;
  }
  return g;
}

function rsEncode(data, n) {
  const g = generator(n), out = new Array(n).fill(0);
  for (const d of data) {
    const f = d ^ out.shift(); out.push(0);
    if (f) for (let j = 0; j < n; j++) out[j] ^= mul(g[j + 1], f);
  }
  return out;
}

export function chooseVersion(len) {
  for (let v = 1; v <= 6; v++) {
    const [total, ec, blocks] = VERSIONS_M[v];
    if (total - ec * blocks - 2 >= len) return v;    // 2 bytes: mode (4 bits) + count (8) + terminator (4)
  }
  return 0;
}

function codewords(bytes, v) {
  const [total, ec, blocks] = VERSIONS_M[v], dataLen = total - ec * blocks;
  const bits = [];
  const push = (val, n) => { for (let i = n - 1; i >= 0; i--) bits.push((val >> i) & 1); };
  push(0b0100, 4); push(bytes.length, 8);
  for (const b of bytes) push(b, 8);
  push(0, Math.min(4, dataLen * 8 - bits.length));
  while (bits.length % 8) bits.push(0);
  const data = [];
  for (let i = 0; i < bits.length; i += 8) data.push(parseInt(bits.slice(i, i + 8).join(""), 2));
  for (let p = 0; data.length < dataLen; p++) data.push(p % 2 ? 0x11 : 0xEC);
  // split into blocks (level M, v1–6: every block the same size), compute EC, interleave
  const size = dataLen / blocks, dBlocks = [], eBlocks = [];
  for (let b = 0; b < blocks; b++) { const d = data.slice(b * size, (b + 1) * size); dBlocks.push(d); eBlocks.push(rsEncode(d, ec)); }
  const out = [];
  for (let i = 0; i < size; i++) for (const d of dBlocks) out.push(d[i]);
  for (let i = 0; i < ec; i++) for (const e of eBlocks) out.push(e[i]);
  return out;
}

function baseMatrix(v) {
  const n = v * 4 + 17;
  const m = Array.from({ length: n }, () => new Int8Array(n).fill(-1));   // -1 = free data module
  const set = (r, c, val) => { if (r >= 0 && c >= 0 && r < n && c < n) m[r][c] = val; };
  const finder = (r0, c0) => {
    for (let r = -1; r <= 7; r++) for (let c = -1; c <= 7; c++) {
      const inner = r >= 0 && c >= 0 && r <= 6 && c <= 6;
      const dark = inner && (r === 0 || r === 6 || c === 0 || c === 6 || (r >= 2 && r <= 4 && c >= 2 && c <= 4));
      set(r0 + r, c0 + c, dark ? 1 : 0);
    }
  };
  finder(0, 0); finder(0, n - 7); finder(n - 7, 0);
  for (let i = 8; i < n - 8; i++) { const t = i % 2 ? 0 : 1; m[6][i] = t; m[i][6] = t; }
  if (ALIGN[v]) {
    const p = ALIGN[v];
    for (let r = -2; r <= 2; r++) for (let c = -2; c <= 2; c++)
      set(p + r, p + c, (Math.max(Math.abs(r), Math.abs(c)) === 1) ? 0 : 1);
  }
  m[n - 8][8] = 1;                                   // the dark module
  // reserve format-information modules (filled after masking)
  for (let i = 0; i <= 8; i++) { if (m[8][i] === -1) m[8][i] = 0; if (m[i][8] === -1) m[i][8] = 0; }
  for (let i = 0; i < 8; i++) { if (m[8][n - 1 - i] === -1) m[8][n - 1 - i] = 0; if (m[n - 1 - i][8] === -1) m[n - 1 - i][8] = 0; }
  return m;
}

function isFunction(v, r, c) {
  const n = v * 4 + 17;
  if (r === 6 || c === 6) return true;
  if ((r <= 8 && c <= 8) || (r <= 8 && c >= n - 8) || (r >= n - 8 && c <= 8)) return true;
  if (ALIGN[v]) { const p = ALIGN[v]; if (Math.abs(r - p) <= 2 && Math.abs(c - p) <= 2) return true; }
  return false;
}

const MASKS = [
  (r, c) => (r + c) % 2 === 0,
  (r) => r % 2 === 0,
  (r, c) => c % 3 === 0,
  (r, c) => (r + c) % 3 === 0,
  (r, c) => (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0,
  (r, c) => ((r * c) % 2) + ((r * c) % 3) === 0,
  (r, c) => (((r * c) % 2) + ((r * c) % 3)) % 2 === 0,
  (r, c) => (((r + c) % 2) + ((r * c) % 3)) % 2 === 0,
];

function place(v, cw) {
  const n = v * 4 + 17, m = baseMatrix(v);
  const bits = [];
  for (const b of cw) for (let i = 7; i >= 0; i--) bits.push((b >> i) & 1);
  let k = 0, up = true;
  for (let right = n - 1; right >= 1; right -= 2) {
    if (right === 6) right = 5;
    for (let i = 0; i < n; i++) {
      const r = up ? n - 1 - i : i;
      for (const c of [right, right - 1]) {
        if (m[r][c] === -1) { m[r][c] = k < bits.length ? bits[k] : 0; k++; }
      }
    }
    up = !up;
  }
  return m;
}

function formatBits(mask) {
  // level M = 00
  const data = (0b00 << 3) | mask;
  let rem = data << 10;
  for (let i = 14; i >= 10; i--) if (rem & (1 << i)) rem ^= 0b10100110111 << (i - 10);
  return ((data << 10) | rem) ^ 0b101010000010010;
}

function applyMask(v, base, mask) {
  const n = v * 4 + 17, m = base.map((row) => Int8Array.from(row)), f = MASKS[mask];
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (!isFunction(v, r, c) && f(r, c)) m[r][c] ^= 1;
  const bits = formatBits(mask);
  const b = (i) => (bits >> i) & 1;
  // around the top-left finder (bits 14..0)
  const tl = [[8, 0], [8, 1], [8, 2], [8, 3], [8, 4], [8, 5], [8, 7], [8, 8], [7, 8], [5, 8], [4, 8], [3, 8], [2, 8], [1, 8], [0, 8]];
  tl.forEach(([r, c], i) => { m[r][c] = b(14 - i); });
  // second copy: bits 0–7 along row 8 from the right edge inwards, bits 14–8 down the left
  // column from the bottom (ISO 18004 figure 25; same layout as Nayuki's reference encoder)
  for (let i = 0; i < 8; i++) m[8][n - 1 - i] = b(i);
  for (let j = 0; j < 7; j++) m[n - 1 - j][8] = b(14 - j);
  return m;
}

export function penalty(m) {
  const n = m.length; let score = 0;
  // rule 1: runs of 5+ same colour in rows and columns
  for (let r = 0; r < n; r++) {
    let runR = 1, runC = 1;
    for (let c = 1; c < n; c++) {
      if (m[r][c] === m[r][c - 1]) { runR++; if (runR === 5) score += 3; else if (runR > 5) score++; } else runR = 1;
      if (m[c][r] === m[c - 1][r]) { runC++; if (runC === 5) score += 3; else if (runC > 5) score++; } else runC = 1;
    }
  }
  // rule 2: 2×2 blocks
  for (let r = 0; r < n - 1; r++) for (let c = 0; c < n - 1; c++) {
    const v = m[r][c]; if (m[r][c + 1] === v && m[r + 1][c] === v && m[r + 1][c + 1] === v) score += 3;
  }
  // rule 3: finder-like 1011101 with 4 light modules on either side
  const pat = [1, 0, 1, 1, 1, 0, 1];
  const match = (get, len) => {
    for (let i = 0; i + 7 <= len; i++) {
      let ok = true; for (let j = 0; j < 7; j++) if (get(i + j) !== pat[j]) { ok = false; break; }
      if (!ok) continue;
      if (i >= 4 && [1, 2, 3, 4].every((d) => get(i - d) === 0)) score += 40;
      if (i + 7 + 4 <= len && [0, 1, 2, 3].every((d) => get(i + 7 + d) === 0)) score += 40;
    }
  };
  for (let r = 0; r < n; r++) { match((i) => m[r][i], n); match((i) => m[i][r], n); }
  // rule 4: dark proportion
  let dark = 0; for (const row of m) for (const x of row) dark += x;
  const pct = (dark * 100) / (n * n), k = Math.floor(Math.abs(pct - 50) / 5);
  score += k * 10;
  return score;
}

/** Encode `text` (UTF-8) → { version, mask, size, modules } choosing the lowest-penalty mask. */
export function encode(text, forceMask) {
  const bytes = Array.from(new TextEncoder().encode(String(text)));
  const v = chooseVersion(bytes.length);
  if (!v) throw new Error("too long for a version-6 code");
  const base = place(v, codewords(bytes, v));
  let best = null, bestScore = Infinity, bestMask = 0;
  const candidates = forceMask == null ? [0, 1, 2, 3, 4, 5, 6, 7] : [forceMask];
  for (const mk of candidates) {
    const m = applyMask(v, base, mk), s = penalty(m);
    if (s < bestScore) { best = m; bestScore = s; bestMask = mk; }
  }
  return { version: v, mask: bestMask, size: best.length, modules: best.map((row) => Array.from(row)) };
}

/** A compact SVG (one path, 4-module quiet zone) in DocOga navy. `px` is the rendered width. */
export function svg(text, px = 96, colour = "#0B1B3F") {
  const q = encode(text), quiet = 4, n = q.size + quiet * 2;
  let d = "";
  for (let r = 0; r < q.size; r++) {
    let c = 0;
    while (c < q.size) {
      if (!q.modules[r][c]) { c++; continue; }
      let w = 1; while (c + w < q.size && q.modules[r][c + w]) w++;
      d += "M" + (c + quiet) + " " + (r + quiet) + "h" + w + "v1h-" + w + "z";
      c += w;
    }
  }
  return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + n + " " + n + '" width="' + px + '" height="' + px +
    '" shape-rendering="crispEdges" role="img" aria-label="QR code: ' + String(text).replace(/[<>&"]/g, "") + '">' +
    '<rect width="' + n + '" height="' + n + '" fill="#fff"/><path d="' + d + '" fill="' + colour + '"/></svg>';
}
