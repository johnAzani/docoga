#!/usr/bin/env node
/* Generates the Android launcher icons and splash screens for the DocOga Owner
 * APK from the committed brand files. No image library beyond `pngjs` (pure JS,
 * no native build, no network fetch at install time) — which is exactly why this
 * exists instead of @capacitor/assets: sharp downloads a libvips binary from
 * GitHub at install time, and a build step that needs a CDN is a build step that
 * fails in a locked-down CI at the worst possible moment.
 *
 *   npm i --no-save pngjs && node tools/make-icons.mjs
 *
 * Output is committed under android/app/src/main/res/, so a normal CI build never
 * runs this file. Run it again when the brand changes.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE = path.resolve(HERE, '..');
const REPO = path.resolve(MOBILE, '..');
const RES = path.join(MOBILE, 'android', 'app', 'src', 'main', 'res');

let PNG;
try { ({ PNG } = await import('pngjs')); }
catch (e) {
  console.error('pngjs is not installed. Run:  npm i --no-save pngjs   (from ./mobile)');
  process.exit(1);
}

const NAVY = [0x0B, 0x1B, 0x3F, 0xFF];        // docs/BRAND_STYLE.md — DocOga ink
const LOGO = path.join(REPO, 'brand', 'official-logo-transparent.png');

/* ---------- pixel helpers (RGBA everywhere) ---------- */
function toRgba(file) {
  const png = PNG.sync.read(fs.readFileSync(file));
  return { width: png.width, height: png.height, data: png.data };
}
/* Box filter on premultiplied alpha — averaging straight alpha smears the
 * transparent halo over the logo edges, which is exactly what you notice on a
 * 48px launcher icon. */
function resize(src, tw, th) {
  const { width: sw, height: sh, data } = src;
  const out = Buffer.alloc(tw * th * 4);
  for (let y = 0; y < th; y++) {
    const y0 = Math.floor((y * sh) / th), y1 = Math.max(y0 + 1, Math.floor(((y + 1) * sh) / th));
    for (let x = 0; x < tw; x++) {
      const x0 = Math.floor((x * sw) / tw), x1 = Math.max(x0 + 1, Math.floor(((x + 1) * sw) / tw));
      let r = 0, g = 0, b = 0, a = 0, n = 0;
      for (let sy = y0; sy < Math.min(y1, sh); sy++) {
        for (let sx = x0; sx < Math.min(x1, sw); sx++) {
          const i = (sy * sw + sx) * 4, al = data[i + 3] / 255;
          r += data[i] * al; g += data[i + 1] * al; b += data[i + 2] * al; a += al; n++;
        }
      }
      const o = (y * tw + x) * 4;
      const A = Math.round((a / n) * 255);
      if (A === 0) { out[o + 3] = 0; continue; }
      out[o] = Math.min(255, Math.round(r / a));
      out[o + 1] = Math.min(255, Math.round(g / a));
      out[o + 2] = Math.min(255, Math.round(b / a));
      out[o + 3] = A;
    }
  }
  return { width: tw, height: th, data: out };
}
function canvas(w, h, fill) {
  const data = Buffer.alloc(w * h * 4);
  for (let i = 0; i < w * h; i++) { data[i * 4] = fill[0]; data[i * 4 + 1] = fill[1]; data[i * 4 + 2] = fill[2]; data[i * 4 + 3] = fill[3] == null ? 255 : fill[3]; }
  return { width: w, height: h, data };
}
/* Centre `img` on `bg`, scaled to `frac` of the smaller side. */
function centre(bg, img, frac) {
  const side = Math.round(Math.min(bg.width, bg.height) * frac);
  const s = resize(img, side, Math.round((side * img.height) / img.width));
  const ox = Math.round((bg.width - s.width) / 2), oy = Math.round((bg.height - s.height) / 2);
  for (let y = 0; y < s.height; y++) {
    for (let x = 0; x < s.width; x++) {
      const dy = oy + y, dx = ox + x;
      if (dx < 0 || dy < 0 || dx >= bg.width || dy >= bg.height) continue;
      const si = (y * s.width + x) * 4, di = (dy * bg.width + dx) * 4;
      const a = s.data[si + 3] / 255, ia = 1 - a;
      bg.data[di] = Math.round(s.data[si] * a + bg.data[di] * ia);
      bg.data[di + 1] = Math.round(s.data[si + 1] * a + bg.data[di + 1] * ia);
      bg.data[di + 2] = Math.round(s.data[si + 2] * a + bg.data[di + 2] * ia);
      bg.data[di + 3] = Math.min(255, Math.round(s.data[si + 3] + bg.data[di + 3] * ia));
    }
  }
  return bg;
}
/* Content bounding box, then the mark alone.
 * The brand file is a stacked lockup: glyph, then the wordmark, then the
 * tagline. At 48 px on a launcher the two lines of text are mush, so the icons
 * get the glyph only and the splash (where there is room) keeps the full logo.
 * The split is detected, not hardcoded: the first empty row band below the
 * middle of the artwork is the gap between the glyph and the wordmark. */
function alphaRows(img) {
  const rows = [];
  for (let y = 0; y < img.height; y++) {
    let a = 0;
    for (let x = 0; x < img.width; x++) a += img.data[(y * img.width + x) * 4 + 3];
    rows.push(a / (img.width * 255));
  }
  return rows;
}
function bbox(img) {
  const rows = alphaRows(img);
  let top = rows.findIndex(v => v > 0.01), bottom = img.height - 1;
  while (bottom > 0 && rows[bottom] <= 0.01) bottom--;
  let left = img.width, right = 0;
  for (let x = 0; x < img.width; x++) {
    let has = false;
    for (let y = top; y <= bottom; y++) if (img.data[(y * img.width + x) * 4 + 3] > 12) { has = true; break; }
    if (has) { if (x < left) left = x; if (x > right) right = x; }
  }
  return { top, bottom, left, right };
}
function markOf(img) {
  const box = bbox(img), rows = alphaRows(img);
  let cut = img.height;
  for (let y = Math.round(box.top + (box.bottom - box.top) * 0.45); y <= box.bottom; y++) {
    if (rows[y] <= 0.01) { // start of an empty band inside the artwork = the lockup gap
      let end = y; while (end <= box.bottom && rows[end] <= 0.01) end++;
      if (end - y >= 12) { cut = y; break; }
      y = end;
    }
  }
  const src = { width: img.width, height: img.height, data: img.data };
  const h = cut - box.top, w = img.width;
  const out = Buffer.alloc(w * h * 4);
  for (let y = 0; y < h; y++) src.data.copy(out, y * w * 4, (box.top + y) * w * 4, (box.top + y + 1) * w * 4);
  const nb = bbox({ width: w, height: h, data: out });
  const cw = nb.right - nb.left + 1, ch = nb.bottom - nb.top + 1;
  const crop = Buffer.alloc(cw * ch * 4);
  for (let y = 0; y < ch; y++) out.copy(crop, y * cw * 4, (nb.top + y) * w * 4 + nb.left * 4, (nb.top + y) * w * 4 + nb.left * 4 + cw * 4);
  return { width: cw, height: ch, data: crop };
}

/* Circular mask for ic_launcher_round (older launchers request it). */
function circle(img) {
  const { width: w, height: h, data } = img;
  const cx = w / 2, cy = h / 2, r = Math.min(w, h) / 2;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const d = Math.hypot(x + 0.5 - cx, y + 0.5 - cy);
    if (d > r + 0.5) { data[(y * w + x) * 4 + 3] = 0; continue; }
    if (d > r - 0.5) data[(y * w + x) * 4 + 3] = Math.round(data[(y * w + x) * 4 + 3] * (r + 0.5 - d));
  }
  return img;
}
const write = (file, img) => {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  // PNG.sync.write takes a PNG instance, not a raw buffer
  const out = new PNG({ width: img.width, height: img.height });
  out.data.copy ? img.data.copy(out.data) : (out.data = Buffer.from(img.data));
  fs.writeFileSync(file, PNG.sync.write(out));
  console.log(`  ${path.relative(MOBILE, file)}  ${img.width}×${img.height}`);
};

if (!fs.existsSync(LOGO)) { console.error('missing brand source: ' + LOGO); process.exit(1); }
const logo = toRgba(LOGO);
const mark = markOf(logo);
console.log('source: brand/official-logo-transparent.png', logo.width + '×' + logo.height);
console.log('glyph only for the launcher:', mark.width + '×' + mark.height, '(the wordmark is illegible at 48 px)');

/* Legacy + adaptive launcher. Adaptive icons are 108dp with a 72dp safe zone in
 * the middle: the logo takes 62% so the mask (circle/squircle/rounded square any
 * launcher applies) never clips the mark itself. */
const DENSITIES = { mdpi: 48, hdpi: 72, xhdpi: 96, xxhdpi: 144, xxxhdpi: 192 };
const ADAPTIVE = { mdpi: 108, hdpi: 162, xhdpi: 216, xxhdpi: 324, xxxhdpi: 432 };
console.log('launcher icons:');
for (const [d, px] of Object.entries(DENSITIES)) {
  const sq = centre(canvas(px, px, NAVY), mark, 0.62);
  write(path.join(RES, `mipmap-${d}`, 'ic_launcher.png'), sq);
  write(path.join(RES, `mipmap-${d}`, 'ic_launcher_round.png'), circle({ width: px, height: px, data: Buffer.from(sq.data) }));
}
console.log('adaptive foregrounds:');
for (const [d, px] of Object.entries(ADAPTIVE)) {
  write(path.join(RES, `mipmap-${d}`, 'ic_launcher_foreground.png'), centre(canvas(px, px, [0, 0, 0, 0]), mark, 0.46));
}
/* The launch/splash frame: navy with the mark, at the dimensions Capacitor's
 * template shipped, so nothing about the layout changes. The unqualified
 * `drawable/` bucket is included on purpose — it is the fallback for a density
 * with no bucket of its own, and if it holds the template's rocket (or nothing)
 * the cold start flashes the wrong artwork. */
console.log('splash frames:');
const splashDirs = ['drawable', ...fs.readdirSync(RES).filter(x => /^drawable-(port|land)-/.test(x))];
for (const dir of splashDirs) {
  const file = path.join(RES, dir, 'splash.png');
  let size = { width: 720, height: 1280 };
  if (fs.existsSync(file)) { const png = toRgba(file); size = { width: png.width, height: png.height }; }
  write(file, centre(canvas(size.width, size.height, NAVY), logo, 0.34));
}
console.log('\nnow set the adaptive background colour:');
const colFile = path.join(RES, 'values', 'ic_launcher_background.xml');
const col = fs.readFileSync(colFile, 'utf8').replace(/<color name="ic_launcher_background">[^<]*</, '<color name="ic_launcher_background">#0B1B3F<');
fs.writeFileSync(colFile, col);
console.log('  values/ic_launcher_background.xml → #0B1B3F');
console.log('\ndone. Commit the res/ changes; CI does not need to run this script.');
