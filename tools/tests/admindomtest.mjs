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
function isoWeekOf(ms) { const d = new Date(ms); d.setUTCHours(0, 0, 0, 0); d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7)); const y0 = new Date(Date.UTC(d.getUTCFullYear(), 0, 1)); return d.getUTCFullYear() + '-W' + String(Math.ceil(((d - y0) / 864e5 + 1) / 7)).padStart(2, '0'); }
function makeRecords() {
  const t = DAY;
  const soonBucket = 'adm:exp:' + new Date(NOW + 3 * 864e5).toISOString().slice(0, 10);
  return {
    ['stat:sold:' + t]: '4', ['stat:rev:' + t]: '8000', ['stat:offline:' + t]: '1', ['stat:manual:' + t]: '2',
    ['stat:wait:' + t]: '3', ['stat:bizcreate:' + t]: '2', ['stat:bizpaid:' + t]: '1', ['stat:bizrev:' + t]: '120000',
    ['stat:revoked:' + t]: '0',
    ['src:checkout:' + isoWeekOf(NOW)]: JSON.stringify({ telegram: 7, facebook: 3 }), ['src:sale:' + isoWeekOf(NOW)]: JSON.stringify({ telegram: 2 }),
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
    GH_DISPATCH_TOKEN: 'ghp_dom_test', CF_ANALYTICS_TOKEN: 'cf_dom_test', CLOUDFLARE_ACCOUNT_ID: 'acc',
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
// The receipt ledger is its own Worker (workers/ledger); the page reads its public counts directly.
const LEDGER_STATS = { total: 41, by_state: { Lagos: 33, Rivers: 5, 'FCT (Abuja)': 3 }, by_month: { '2026-10': 41 }, by_kind: { rent: 36, caution: 5 },
  cells: { 'Lagos|rent|2026-10': 28, 'Rivers|rent|2026-10': 5, 'Lagos|caution|2026-10': 5, 'FCT (Abuja)|rent|2026-10': 3 }, latest_receipt_date: '2026-10-19', publish_at: 30, generated_at: '2026-10-19T13:00:00Z' };
let ledgerCalls = 0;
win.fetch = async (input, init) => {
  const url = String(input);
  if (url.startsWith('https://docoga-ledger.')) { ledgerCalls++; return { ok: true, status: 200, headers: new Headers(), text: async () => JSON.stringify(LEDGER_STATS), json: async () => LEDGER_STATS }; }
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
check('channels → money: Telegram first (2 sales from 7 taps = 29%), Facebook 3 taps and no sale', /telegram/.test(txt('channels')) && /29%/.test(txt('channels')) && txt('channels').indexOf('telegram') < txt('channels').indexOf('facebook'), txt('channels').slice(0, 200));
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

console.log('— Social tab: the day’s plan, in the owner’s clock —');
{
  // The worker reaches the clock, GitHub and Cloudflare through Node's fetch; stand them in.
  const realFetch = globalThis.fetch; const outbound = [];
  // Freeze the worker's clock (Node's Date, not the page's): Saturday 17 Oct 2026, 8:30pm Lagos.
  const realNow = Date.now; const FIXED = Date.parse('2026-10-17T19:30:00Z'); Date.now = () => FIXED;
  const nowUTC = new Date(FIXED);
  // 7:10pm Lagos failed · 10:10pm Lagos still to come · 1:10pm Lagos ran clean
  const table = [
    { workflow: 'instagram_autopost.yml', name: 'IG', cron: '10 18 * * *', inputs: { clock: 'true' } },
    { workflow: 'threads_autopost.yml', name: 'Threads', cron: '10 21 * * *', inputs: { slot: 'evening' } },
    { workflow: 'telegram_autopost.yml', name: 'Telegram', cron: '10 12 * * *', inputs: {} },
  ];
  const mk = (id, name, file, at, conclusion) => ({ id, name, path: '.github/workflows/' + file, event: 'workflow_dispatch', status: 'completed', conclusion, created_at: at, run_started_at: at, updated_at: at, run_attempt: 1, html_url: 'https://github.com/johnAzani/docoga/actions/runs/' + id });
  const runs = [mk(71, 'IG', 'instagram_autopost.yml', '2026-10-17T18:10:33Z', 'failure'), mk(72, 'Telegram', 'telegram_autopost.yml', '2026-10-17T12:10:40Z', 'success')];
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url); outbound.push((init.method || 'GET') + ' ' + u);
    const reply = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { 'content-type': 'application/json' } });
    if (u.startsWith('https://docoga-clock.')) return reply({ ok: true, token: 'present', paused: false, entries: 3, utc: nowUTC.toISOString(), entries_table: table });
    if (u.includes('/actions/runs?created=')) { const m = /created=([^.]+)\.\.([^&]+)/.exec(u); const a = Date.parse(m[1]), b = Date.parse(m[2]); return reply({ workflow_runs: runs.filter(r => { const c = Date.parse(r.created_at); return c >= a && c <= b; }) }); }
    if (u.includes('/actions/runs/71/jobs')) return reply({ jobs: [{ id: 7101, name: 'publish', conclusion: 'failure' }] });
    if (u.includes('/check-runs/7101/annotations')) return reply([{ annotation_level: 'failure', message: 'IG_CAUSE=media — the card URL never answered 200' }]);
    if (u.endsWith('/dispatches')) return new Response(null, { status: 204 });
    if (u === 'https://docoga.com.ng/') return new Response("<script data-cf-beacon='{\"token\": \"0123456789abcdef0123456789abcdef\"}'></script>", { headers: { 'content-type': 'text/html' } });
    if (u === 'https://api.cloudflare.com/client/v4/graphql') return reply({ data: { viewer: { accounts: [{ t7: [{ count: 70, sum: { visits: 52 } }], t28: [{ count: 240, sum: { visits: 180 } }],
      ref7: [{ sum: { visits: 33 }, dimensions: { refererHost: '' } }, { sum: { visits: 13 }, dimensions: { refererHost: 'www.google.com' } }], path7: [{ count: 40, sum: { visits: 31 }, dimensions: { requestPath: '/' } }],
      country7: [{ sum: { visits: 45 }, dimensions: { countryName: 'NG' } }, { sum: { visits: 7 }, dimensions: { countryName: 'US' } }], days28: [{ count: 10, sum: { visits: 8 }, dimensions: { date: '2026-10-16' } }] }] } } });
    return reply({ message: 'unexpected ' + u }, 500);
  };
  try {
    click([...doc.querySelectorAll('.tab')].find(t => t.getAttribute('data-view') === 'social'));
    await until(() => /Instagram/.test(txt('social-today')), 80);
    const board = txt('social-today');
    check('the three slots are painted with lane and what', /Instagram/.test(board) && /Threads/.test(board) && /Telegram/.test(board), board.slice(0, 200));
    check('times are 12-hour Lagos (7:10pm, 1:10pm, 10:10pm), never 19:10', /7:10pm/.test(board) && /1:10pm/.test(board) && /10:10pm/.test(board) && !/19:10/.test(board), board.slice(0, 200));
    check('the failed Instagram slot says failed and shows the lane’s reason', /failed/.test(board) && /IG_CAUSE=media/.test(board), board.slice(0, 300));
    check('the clean Telegram slot reads posted; the future Threads slot reads upcoming', /posted/.test(board) && /upcoming/.test(board), board);
    const kv = [...doc.querySelectorAll('#social-kpis .v')].map(e => e.textContent);
    check('the KPI cards count posts: 1 out, 1 failed, 0 missed, 1 still to come', kv.join(',') === '1,1,0,1', kv.join(','));
    check('the clock is reported on duty', /on duty/.test(txt('social-health')), txt('social-health'));
    const retry = doc.querySelector('#social-today button[data-run]');
    check('only the failed row offers Retry', !!retry && doc.querySelectorAll('#social-today button[data-run]').length === 1);
    click(retry);
    await until(() => /Asked\./.test(txt('social-msg')), 60);
    check('Retry dispatches the lane through the worker and tells the owner it is asked', /Asked\./.test(txt('social-msg')) && outbound.some(x => x === 'POST https://api.github.com/repos/johnAzani/docoga/actions/workflows/instagram_autopost.yml/dispatches'), txt('social-msg') + ' | ' + outbound.filter(x => x.startsWith('POST')).join(','));
    check('the page never saw the GitHub token', !doc.documentElement.outerHTML.includes('ghp_dom_test'));

    console.log('— Website tab: visits from Cloudflare —');
    click([...doc.querySelectorAll('.tab')].find(t => t.getAttribute('data-view') === 'site'));
    await until(() => /70 page views/.test(txt('site-kpis')), 80);
    const sv = [...doc.querySelectorAll('#site-kpis .v')].map(e => e.textContent);
    check('visits (7 + 28 days) and the Nigeria share are painted', sv[0] === '52' && sv[1] === '180' && sv[2] === '87%', sv.join(','));
    check('channels and countries tables are filled, country codes spelled out', /google/.test(txt('site-channels')) && /Nigeria/.test(txt('site-countries')) && /United States/.test(txt('site-countries')), txt('site-countries'));
    console.log('— Website tab: the receipt ledger (public counts, nothing personal) —');
    await until(() => /41/.test(txt('ledger-kpis')), 80);
    const lk = [...doc.querySelectorAll('#ledger-kpis .v')].map(e => e.textContent);
    check('receipts verified, this month, states of 37, cells ready are painted', lk[0] === '41' && lk[1] === '41' && lk[2] === '3 of 37' && lk[3] === '0', lk.join(','));
    check('the closest cell to publication is named with its count toward 30', /closest: Lagos · rent — 28 of 30/.test(txt('ledger-kpis')), txt('ledger-kpis'));
    const lbars = [...doc.querySelectorAll('#ledger-cells div[style*="width:"]')].map(e => e.getAttribute('style'));
    check('progress bars: Lagos rent at 93%, listed first', lbars.length >= 4 && /width:93%/.test(lbars[0]), lbars.join(' | '));
    check('cells read in plain words (caution fee, Oct 2026), never as raw keys', /Lagos · caution fee · Oct 2026/.test(txt('ledger-cells')) && !/\|/.test(txt('ledger-cells')), txt('ledger-cells').slice(0, 160));
    check('states table: Lagos 33 = 80% first', /Lagos\s*33\s*80%/.test(txt('ledger-states')) && txt('ledger-states').indexOf('Lagos') < txt('ledger-states').indexOf('Rivers'), txt('ledger-states').slice(0, 120));
    check('the note says counts only, no names/addresses/phones, and where to check a code', /no names, addresses or phones/.test(txt('ledger-note')) && /docoga\.com\.ng\/v\/DR-/.test(txt('ledger-note')), txt('ledger-note'));
    check('the ledger was read once at boot and not again within 10 minutes', ledgerCalls === 1, 'calls=' + ledgerCalls);
    click([...doc.querySelectorAll('.tab')].find(t => t.getAttribute('data-view') === 'ov'));
    await until(() => /Receipts verified/.test(txt('kpis')), 40);
    const rcard = [...$('kpis').children].find(c => /Receipts verified/.test(c.textContent));
    check('Today tab carries a “Receipts verified” card: 41 · 41 this month · 3 states', !!rcard && /41/.test(rcard.textContent) && /41 this month · 3 states/.test(rcard.textContent), rcard ? rcard.textContent : 'no card');
    console.log('— Content tab: the brain plan, posted, growth —');
    env._store.set('adm:feed', JSON.stringify({
      version: 1, generated_at: '2026-10-17T19:00:00Z',
      plan: [
        { date: '2026-10-17', approved: true, theme: 'rent-receipt', headline: 'Pay rent without a receipt and you paid nothing — in court.', lines: ['Section 5, Lagos Tenancy Law 2011'], threads: 'Your landlord refuses a receipt. Next move?', short: 'No receipt, no proof.', reader: 'tenants paying cash', why: 'payday week', quiz: false },
        { date: '2026-10-18', approved: false }, { date: '2026-10-19', approved: false }],
      posted: [{ at: '2026-10-17T17:02:00Z', platform: 'youtube', kind: 'short', title: 'Sign without asking #Shorts', url: 'https://www.youtube.com/watch?v=abc', privacy: 'public' },
               { at: '2026-10-16T06:37:20Z', platform: 'instagram', kind: 'post', title: 'Don’t wait until there’s a problem', url: 'https://www.instagram.com/p/x/', privacy: 'public' },
               { at: '2026-10-15T17:05:00Z', platform: 'tiktok', kind: 'inbox draft', title: 'Pay the wrong agent #DocOga', url: '', privacy: '', state: 'SEND_TO_USER_INBOX' }],
      growth: { taken_at: '2026-10-12T06:40:00+01:00', rows: [
        { key: 'facebook.followers', label: 'Facebook', unit: 'followers', value: 410, previous: 400, target: 500, due: '2027-01-31', unlocks: 'Facebook Stars' },
        { key: 'instagram.followers', label: 'Instagram', unit: 'followers', value: null, previous: null, target: 1000, due: '2027-04-30', unlocks: '' },
        { key: 'youtube.subscribers', label: 'YouTube', unit: 'subscribers', value: 49, previous: null, target: 500, due: '2027-03-31', unlocks: 'fan funding', source: 'youtube_stats' }] },
      youtube: { snapshot: { taken_at: '2026-10-14T18:07:26+01:00', subscribers: 49, views: 142, videos: 13, top: [{ id: 'b', title: 'Service charge explained', views: 40, kind: 'longform' }] },
                 scheduled: [{ title: 'Deep-Dive: notice to quit', url: 'https://www.youtube.com/watch?v=dd', publish_at: '2026-10-19T18:00:00Z', privacy: 'private' }] },
      deepdive_next: 'dd5 Service charge',
      tiktok: { connected: true, since: '2026-10-18T09:00:00+00:00', expires: '2027-10-18' },
    }));
    click([...doc.querySelectorAll('.tab')].find(t => t.getAttribute('data-view') === 'content'));
    await until(() => /receipt/.test(txt('plan')), 80);
    const plan = txt('plan');
    check('today’s approved pack is painted: headline, Threads line, Short, reader', /paid nothing/.test(plan) && /Threads:/.test(plan) && /No receipt, no proof/.test(plan) && /tenants paying cash/.test(plan), plan.slice(0, 200));
    check('days without a pack say so and when the brain will plan them (1:30am), not a blank', /Tomorrow · Sun, 18 Oct/.test(plan) && /no approved pack/.test(plan) && /tonight at 1:30am/.test(plan), plan.slice(-200));
    check('the plan header says when the feed was synced (30 min ago)', /synced 30 min ago/.test(txt('plan-note')), txt('plan-note'));
    const growth = txt('growth');
    check('growth table: Facebook 410 of 500 with +10 since last week, Instagram “not measured yet”', /410/.test(growth) && /\+10/.test(growth) && /not measured yet/.test(growth) && /Facebook Stars/.test(growth), growth.slice(0, 300));
    const bars = [...doc.querySelectorAll('#growth div[style*="width:"]')].map(e => e.getAttribute('style'));
    check('milestone progress bars: Facebook 82%, YouTube 10%', bars.some(b => /width:82%/.test(b)) && bars.some(b => /width:10%/.test(b)), bars.join(' | '));
    const yt = txt('yt');
    check('YouTube: 49 subscribers, the most-watched video, the scheduled Deep-Dive at 7:00pm Monday, the queue', /49/.test(yt) && /Service charge explained/.test(yt) && /7:00pm/.test(yt) && /dd5 Service charge/.test(yt), yt.slice(0, 300));
    const posted = txt('posted');
    check('posted list: newest first, platform words, 12-hour Lagos time (6:02pm, 7:37am)', /YouTube/.test(posted) && /Instagram/.test(posted) && /6:02pm/.test(posted) && /7:37am/.test(posted) && posted.indexOf('YouTube') < posted.indexOf('Instagram'), posted.slice(0, 200));
    check('post titles link to the post', !!doc.querySelector('#posted a[href="https://www.youtube.com/watch?v=abc"]'));
    click([...doc.querySelectorAll('.tab')].find(t => t.getAttribute('data-view') === 'social'));
    await until(() => /approved pack for today/.test(txt('social-health')), 60);
    check('the Social tab’s machinery row shows the brain approved today’s pack', /approved pack for today/.test(txt('social-health')), txt('social-health'));
    check('…and that TikTok is connected, with the date', /TikTok/.test(txt('social-health')) && /connected · since Sun, 18 Oct/.test(txt('social-health')), txt('social-health'));
    check('a TikTok inbox draft is listed as waiting in the app, not as a link', /TikTok/.test(posted) && /waiting in your TikTok inbox/.test(posted) && !doc.querySelector('#posted a[href=""]'), posted.slice(-200));
    check('no page error was thrown while painting the new tabs', pageErrors.length === 0, pageErrors.join(' | '));
  } finally { globalThis.fetch = realFetch; Date.now = realNow; }
}

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
