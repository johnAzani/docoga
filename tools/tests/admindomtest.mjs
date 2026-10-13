/* ============================================================================
 * DocOga OWNER DASHBOARD — EXECUTION TEST (jsdom)
 * ============================================================================
 * Loads the REAL site/admin.html, executes its REAL scripts, and drives it
 * against the REAL worker code with a mock KV. No browser, no network, no
 * live Cloudflare. This is the file that proves the dashboard is not just
 * syntactically valid but actually: signs in, refuses a wrong passphrase,
 * paints money from the server (never from the client), mints a paid code,
 * revokes one, escapes a hostile firm name, and falls back to the login screen
 * the instant its session is revoked server-side.
 *
 * Usage:  node tools/tests/admindomtest.mjs
 * Deps:   npm i jsdom   (skipped with a clear message if absent — same policy
 *         as domtest.mjs, so a fresh clone is never blocked by an optional dep)
 * Exit:   0 = all green · 1 = at least one FAIL
 * ==========================================================================*/
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import mod from '../../worker/index.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const PAGE = path.join(ROOT, 'site', 'admin.html');

function jsdomDirCandidates() {
  return [process.env.JSDOM_PATH, path.join(ROOT, 'node_modules', 'jsdom'), '/home/user/node_modules/jsdom'].filter(Boolean);
}
let JSDOM = null;
for (const dir of jsdomDirCandidates()) {
  try { const api = await import('file://' + path.join(dir, 'lib', 'api.js')); JSDOM = api.JSDOM; break; } catch (e) { /* next */ }
}
if (!JSDOM) { try { JSDOM = (await import('jsdom')).JSDOM; } catch (e) {} }
if (!JSDOM) {
  console.log('⚠️  jsdom not installed — skipping the admin DOM suite.');
  console.log('    Install it with:  npm i jsdom     (or set JSDOM_PATH)');
  process.exit(0);
}

let pass = 0, fail = 0;
const failures = [];
function check(name, cond, detail = '') {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; failures.push(name + (detail ? ' | ' + detail : '')); console.log('  ✗ FAIL: ' + name + (detail ? ' | ' + detail : '')); }
}

/* ---------------- mock KV + the real worker ---------------- */
const PASS = 'owner passphrase for tests only';
const SIGN = 'owner session signing secret for tests only';
const NOW = Date.now();
const DAY = new Date(NOW).toISOString().slice(0, 10);
function makeRecords() {
  const t = DAY;
  const soonBucket = 'adm:exp:' + new Date(NOW + 3 * 864e5).toISOString().slice(0, 10);
  return {
    ['stat:sold:' + t]: '4', ['stat:rev:' + t]: '8000', ['stat:offline:' + t]: '1', ['stat:manual:' + t]: '2',
    ['stat:wait:' + t]: '3', ['stat:bizcreate:' + t]: '2', ['stat:bizpaid:' + t]: '1', ['stat:bizrev:' + t]: '120000',
    ['stat:revoked:' + t]: '0',
    [soonBucket]: JSON.stringify(['OGA-SELL-AAAA-BBBB']),
    'code:OGA-SELL-AAAA-BBBB': JSON.stringify({ code: 'OGA-SELL-AAAA-BBBB', email: 'chidi@one.ng', ref: 'FLW-77', issuedAt: NOW - 27 * 864e5, used: true, source: 'online', exp: NOW + 3 * 864e5, devices: ['d1', 'd2'], note: '=HYPERLINK("evil")' }),
    'adm:em:chidi@one.ng': JSON.stringify(['OGA-SELL-AAAA-BBBB']),
    'team:talpha01': JSON.stringify({ id: 'talpha01', name: '<img src=x onerror=alert(1)>Okonkwo & Co', status: 'active', plan: 'standard', seats: 3, docs: 100, expiry: '2027-01-04', created: '2026-10-01T09:00:00.000Z', total: 120000, price: 100000, vat: 20000, segment: 'estate-agent' }),
    'team:talpha01:seats': JSON.stringify([{ email: 'owner@alpha.ng', name: '', role: 'owner', status: 'active', invited_at: '2026-10-01T09:00:00.000Z' }]),
    'team:talpha01:usage:2026-10': '37',
    'teaminv:talpha01': JSON.stringify([{ id: 'inv-1', total: 120000, method: 'transfer', status: 'open', created: '2026-10-02T09:00:00.000Z' }]),
    'bizwait:lead@firm.ng': JSON.stringify({ email: 'lead@firm.ng', company: 'Firm Ltd', segment: 'property-manager', at: '2026-10-11T09:00:00.000Z' }),
    'debug:last-webhook-ts': String(NOW - 9 * 60000),
    'debug:last-webhook': JSON.stringify({ type: 'charge.completed', data: { status: 'successful', amount: 2000, currency: 'NGN', tx_ref: 'FLW-77', customer: { email: 'secret.buyer@one.ng' } } }),
  };
}
function makeEnv(records) {
  const store = new Map(Object.entries(records));
  const counters = { writes: 0, reads: 0 };
  const env = {
    KV: {
      get: async (k) => { counters.reads++; return store.has(k) ? store.get(k) : null; },
      put: async (k, v) => { counters.writes++; store.set(k, String(v)); },
      delete: async (k) => { counters.writes++; store.delete(k); },
      incr: async (k, amt = 1) => { counters.writes++; const n = Number(store.get(k) || '0') + Number(amt); store.set(k, String(n)); return n; },
      list: async ({ prefix = '', limit = 1000 } = {}) => ({ keys: [...store.keys()].filter(k => k.startsWith(prefix)).slice(0, limit).map(name => ({ name })), list_complete: true }),
    },
    SITE_URL: 'https://docoga.com.ng', PAYMENT_URL: 'https://flutterwave.com/pay/x', PROVIDER: 'flw',
    ADMIN_PASSPHRASE: PASS, ADMIN_AUTH_SECRET: SIGN,
    _store: store, _c: counters,
  };
  return env;
}

/* ---------------- load the page with fetch wired to the worker ---------------- */
const env = makeEnv(makeRecords());
let pageErrors = [];
const html = fs.readFileSync(PAGE, 'utf8');
const dom = new JSDOM(html, {
  url: 'https://docoga.com.ng/admin',
  runScripts: 'dangerously',
  pretendToBeVisual: true,
});
const win = dom.window, doc = win.document;
win.confirm = () => true;
win.alert = (m) => { win.__alerts = (win.__alerts || []).concat(String(m)); };
win.URL.createObjectURL = () => 'blob:test';
win.URL.revokeObjectURL = () => {};
let blobText = null;
const RealBlob = win.Blob;
win.Blob = class extends RealBlob {
  constructor(parts, opts) { super(parts, opts); blobText = String(parts && parts[0] || ''); win.__blobType = opts && opts.type; }
};
win.fetch = async (input, init) => {
  const url = String(input);
  const r = await mod.fetch(new Request(url, init || {}), env, {});
  const text = await r.text();
  return { ok: r.ok, status: r.status, headers: r.headers, text: async () => text, json: async () => JSON.parse(text) };
};
win.addEventListener('error', (e) => pageErrors.push(String(e.message || e.error)));
const tick = (ms = 12) => new Promise(r => setTimeout(r, ms));
async function until(fn, tries = 60) { for (let i = 0; i < tries; i++) { if (fn()) return true; await tick(); } return false; }
const $ = (id) => doc.getElementById(id);
const txt = (id) => ($(id) ? $(id).textContent.replace(/\s+/g, ' ').trim() : '');
const click = (el) => el.dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
const type = (el, v) => { el.value = v; el.dispatchEvent(new win.Event('input', { bubbles: true })); };

console.log('— the page boots closed —');
check('login card is visible, the app is not', !$('login').classList.contains('hide') && $('app').classList.contains('hide'));
check('the file contains no passphrase and no secret', html.indexOf(PASS) < 0 && html.indexOf(SIGN) < 0);
check('the page declares no secret-valued constant and carries no bearer token in source',
  !/(SECRET|API_KEY|PASSPHRASE|TOKEN)\s*=\s*["'`][^"'`]{12,}/.test(html) && !/Bearer [A-Za-z0-9+/=]{16,}/.test(html));
check('it is unlistable by search engines', /name="robots" content="noindex/.test(html));
check('it works as an installed app (viewport-fit + standalone meta)', /viewport-fit=cover/.test(html) && /mobile-web-app-capable/.test(html));

console.log('— sign in —');
type($('pass'), 'wrong passphrase');
click($('btn-login'));
await until(() => txt('login-msg').length > 3);
check('a wrong passphrase shows the server’s reason on the page', /wrong passphrase/i.test(txt('login-msg')), txt('login-msg'));
check('the app stays hidden after a failed sign-in', $('app').classList.contains('hide'));
type($('pass'), PASS);
click($('btn-login'));
const authed = await until(() => !$('app').classList.contains('hide'));
check('the right passphrase opens the dashboard', authed);
check('a token is kept locally and nothing else is', /^[a-f0-9]{32}\.[^"']+$/.test(win.localStorage.getItem('docoga.admin.token') || ''), String(win.localStorage.getItem('docoga.admin.token') || '').slice(0, 40));
check('the passphrase itself is NOT persisted anywhere', (win.localStorage.getItem('docoga.admin.token') || '').indexOf(PASS) < 0 && Object.keys(win.localStorage).every(k => !/pass/i.test(k)));

console.log('— the numbers are the server’s, not the client’s —');
await until(() => /₦8,000/.test(txt('kpis')));
check('today’s revenue comes from the ledger', /₦8,000/.test(txt('kpis')), txt('kpis').slice(0, 120));
check('passes count online and hand-minted separately', /4 online · 2 by hand/.test(txt('kpis')), txt('kpis').slice(0, 160));
check('Business revenue is its own card', /₦120,000/.test(txt('kpis')));
const activeCard=[...$('kpis').children].find(c=>/Active passes/.test(c.textContent));
check('the expiry index feeds the active card', !!activeCard && activeCard.querySelector('.v').textContent.trim() === '1', activeCard ? activeCard.textContent : 'no card');
check('31 bars are drawn for revenue', $('chart-rev').querySelectorAll('.bar').length === 31, String($('chart-rev').querySelectorAll('.bar').length));
check('zero days are drawn as grey, not hidden', $('chart-rev').querySelectorAll('.bar.zero').length > 25, String($('chart-rev').querySelectorAll('.bar.zero').length));
check('webhook health says 9 min', /9 min/.test(txt('health')), txt('health').slice(0, 160));
check('the buyer email from the raw webhook body never reaches the page', txt('health').indexOf('secret.buyer@one.ng') < 0 && doc.body.innerHTML.indexOf('secret.buyer@one.ng') < 0);
check('no alert banner when the ledger cross-check is clean', $('banner').classList.contains('hide'), txt('banner').slice(0, 120));
check('the expiring table shows the re-read record, with its note', /OGA-SELL-AAAA-BBBB/.test(txt('expiring')) && /chidi@one\.ng/.test(txt('expiring')), txt('expiring').slice(0, 160));

console.log('— search, then act on a pass —');
type($('q'), 'oga sell aaaa bbbb');
click($('btn-find'));
await until(() => /OGA-SELL-AAAA-BBBB/.test(txt('results')));
check('a code typed with spaces and lower case is found', /OGA-SELL-AAAA-BBBB/.test(txt('results')));
check('days left and device count are rendered per record', $('results').querySelectorAll('tbody tr td')[3].textContent.indexOf('3 days left') >= 0 && $('results').querySelectorAll('tbody tr td')[5].textContent.trim() === '2',
  [...$('results').querySelectorAll('tbody tr td')].map(t => t.textContent.trim()).join(' | ').slice(0, 200));
check('the note is escaped, not executed (CSV/formula-hostile text stays inert)', doc.body.querySelectorAll('#results img').length === 0 && /HYPERLINK/.test(txt('results')), txt('results').slice(0, 200));
const before = env._store.get('code:OGA-SELL-AAAA-BBBB');
click($('results').querySelector('button[data-act="revoke"]'));
await until(() => /revoked/i.test(txt('results')));
check('revoke round-trips through the API and repaints the row', /revoked/i.test(txt('results')), txt('results').slice(0, 160));
check('the record really changed in KV', /"revoked":true/.test(env._store.get('code:OGA-SELL-AAAA-BBBB')) && before !== env._store.get('code:OGA-SELL-AAAA-BBBB'));
check('revoking adds one to the revoked counter', Number(env._store.get('stat:revoked:' + DAY) || 0) === 1, String(env._store.get('stat:revoked:' + DAY)));

console.log('— CSV export is the owner’s, and is spreadsheet-safe —');
click($('btn-csv'));
await tick(30);
check('a CSV blob is produced from the rows on screen', /code,email,source/.test(blobText || ''), String(blobText).slice(0, 90));
check('a stored field that starts with = is neutralised for Excel', /"'=HYPERLINK/.test(blobText || ''), String(blobText).match(/.{0,14}HYPERLINK.{0,10}/g)?.[0] || 'not found');
check('the export is typed as csv', win.__blobType === 'text/csv;charset=utf-8', String(win.__blobType));

console.log('— sell from the dashboard, the WhatsApp-sale path —');
click([...doc.querySelectorAll('.tab')].find(t => t.getAttribute('data-view') === 'sell'));
await until(() => /of 200 hand-mints used today/.test(txt('sell-cap')));
check('the daily mint cap is stated on the form itself', /0 of 200 hand-mints used today/.test(txt('sell-cap')), txt('sell-cap'));
type($('s-email'), 'buyer@two.ng');
type($('s-amt'), '2000');
type($('s-note'), 'front desk, cash');
click($('btn-sell'));
const minted = await until(() => /^OGA-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$/.test(txt('sell-code')));
const newCode = txt('sell-code');
check('minting returns a real code to copy to the buyer', minted, newCode);
const mintedRec = JSON.parse(env._store.get('code:' + newCode) || '{}');
check('it is written as a manual sale with the naira received', mintedRec.source === 'manual' && mintedRec.email === 'buyer@two.ng' && /front desk/.test(mintedRec.note), JSON.stringify(mintedRec).slice(0, 160));
check('the ledger counted it as money', Number(env._store.get('stat:manual:' + DAY)) === 3 && Number(env._store.get('stat:rev:' + DAY)) === 10000, JSON.stringify({ m: env._store.get('stat:manual:' + DAY), r: env._store.get('stat:rev:' + DAY) }));
await until(() => /₦10,000/.test(txt('kpis')));
check('the dashboard repaints with the new revenue without a reload', /₦10,000/.test(txt('kpis')), txt('kpis').slice(0, 90));
check('the copy button degrades quietly when the clipboard is unavailable', /Copied|Copy code/.test(txt('btn-copy')));

console.log('— Business and leads tabs —');
click([...doc.querySelectorAll('.tab')].find(t => t.getAttribute('data-view') === 'biz'));
await until(() => /OKONKWO|Okonkwo/.test(txt('teams')) || /no Business teams/.test(txt('teams')), 40);
check('the seeded team row is rendered from the snapshot', /Okonkwo/.test(txt('teams')) || /okconkwo/i.test(txt('teams')), txt('teams').slice(0, 140));
check('a hostile firm name is escaped — no injected element in the DOM', doc.querySelectorAll('#teams img, #teams script').length === 0);
check('open invoices are surfaced on the Business tab', /₦120,000/.test(txt('invoices')), txt('invoices').slice(0, 120));
click([...doc.querySelectorAll('.tab')].find(t => t.getAttribute('data-view') === 'leads'));
await until(() => /lead@firm\.ng/.test(txt('leads')), 40);
check('the waitlist row shows company and segment', /lead@firm\.ng/.test(txt('leads')) && /Firm Ltd/.test(txt('leads')) && /property-manager/.test(txt('leads')), txt('leads').slice(0, 160));

console.log('— security tab —');
click([...doc.querySelectorAll('.tab')].find(t => t.getAttribute('data-view') === 'sec'));
await until(() => /this device/.test(txt('sessions')), 40);
check('the live session is listed and marked as this device', /this device/.test(txt('sessions')), txt('sessions').slice(0, 160));
check('the network is shown masked, not the full IP', /\.\••/.test(txt('sessions')), txt('sessions').slice(0, 200));
check('the protection explainer is on the page', /no CSRF surface here/.test(txt('explainer')), txt('explainer').slice(0, 80));
const sid = (win.localStorage.getItem('docoga.admin.token') || '').split('.')[0];
click($('btn-killall'));
await tick(40);
check('“sign out every other device” keeps this one alive', env._store.has('adm:sess:' + sid));
check('but every other admin session is deleted from KV', [...env._store.keys()].filter(k => k.startsWith('adm:sess:')).length === 1);

console.log('— server-side revocation is felt immediately —');
env._store.delete('adm:sess:' + sid);
click($('btn-refresh')); // the next request the page makes must discover it
const kicked = await until(() => !$('login').classList.contains('hide') && $('app').classList.contains('hide'), 120);
check('deleting the KV session drops the open page back to the login card', kicked);
check('the token is wiped from localStorage on the way out', !win.localStorage.getItem('docoga.admin.token'));

console.log('— the disabled state is legible —');
{
  const offEnv = makeEnv({});
  offEnv.ADMIN_PASSPHRASE = undefined;
  const dom2 = new JSDOM(html, { url: 'https://docoga.com.ng/admin', runScripts: 'dangerously', pretendToBeVisual: true });
  dom2.window.fetch = async (input, init) => {
    const r = await mod.fetch(new Request(String(input), init || {}), offEnv, {});
    const text = await r.text();
    return { ok: r.ok, status: r.status, text: async () => text, json: async () => JSON.parse(text), headers: r.headers };
  };
  const d2 = dom2.window.document;
  d2.getElementById('pass').value = PASS;
  d2.getElementById('btn-login').dispatchEvent(new dom2.window.MouseEvent('click', { bubbles: true }));
  for (let i = 0; i < 40 && !/switched off/.test(d2.getElementById('login-msg').textContent); i++) await tick(10);
  check('503 admin_disabled is explained, not shown as a wrong passphrase', /switched off on the server/.test(d2.getElementById('login-msg').textContent), d2.getElementById('login-msg').textContent);
  dom2.window.close();
}

check('the page threw no uncaught script errors', pageErrors.length === 0, pageErrors.slice(0, 2).join(' · '));
win.close();

console.log('\n' + '═'.repeat(78));
if (fail) { failures.forEach(f => console.log('  ✗ ' + f)); console.log(`❌ ADMIN DOM SUITE — ${pass} passed, ${fail} FAILED`); }
else console.log(`🏆 ADMIN DOM SUITE GREEN — ${pass} checks passed, 0 failed.`);
process.exit(fail ? 1 : 0);
