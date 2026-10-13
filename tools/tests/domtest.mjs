/* ============================================================================
 * DocOga FULL-APP EXECUTION TEST (jsdom — no browser, no network required)
 * ============================================================================
 * Runs the REAL site/index.html, executes its REAL scripts, and drives the REAL
 * user flows: all 13 routes, all 10 document tools, hostile input, pass
 * activation (mocked worker), top-up carry-over, device fence, offline codes,
 * magic links, draft auto-save, saved documents, print path.
 *
 * Why it exists: tools/tests/*.js (puppeteer) need Chromium + a browser binary
 * that is often unavailable (fresh sandbox, CI). This suite needs only jsdom,
 * so the safety net still exists when the browser can't be installed.
 *
 * Usage:  node tools/tests/domtest.mjs
 * Deps:   npm i jsdom      (resolved from ./node_modules, /home/user/node_modules
 *                          or JSDOM_PATH; skipped with a clear message if absent)
 * Exit:   0 = all green · 1 = at least one FAIL
 * ==========================================================================*/
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const INDEX = path.join(ROOT, 'site', 'index.html');

/* ---------- jsdom resolution (works in repo, sandbox and CI) ---------- */
function jsdomDirCandidates() {
  return [
    process.env.JSDOM_PATH,
    path.join(ROOT, 'node_modules', 'jsdom'),
    '/home/user/node_modules/jsdom',
  ].filter(Boolean);
}
let JSDOM = null, VirtualConsole = null;
for (const dir of jsdomDirCandidates()) {
  try {
    const api = await import('file://' + path.join(dir, 'lib', 'api.js'));
    const vc = await import('file://' + path.join(dir, 'lib', 'jsdom', 'virtual-console.js'));
    JSDOM = api.JSDOM; VirtualConsole = vc.VirtualConsole;
    break;
  } catch (e) { /* try next */ }
}
if (!JSDOM) {
  try { const m = await import('jsdom'); JSDOM = m.JSDOM; } catch (e) {}
}
if (!JSDOM) {
  console.log('⚠️  jsdom not installed — skipping DOM suite.');
  console.log('    Install it with:  npm i jsdom     (or set JSDOM_PATH)');
  process.exit(0); // never block a push on a missing optional dep — same policy as workertest.mjs
}

/* ---------- tiny assert framework ---------- */
let pass = 0, fail = 0;
const failures = [];
function check(name, cond, detail = '') {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; failures.push(name); console.log('  ✗ FAIL: ' + name + (detail ? '  [' + detail + ']' : '')); }
}
function section(t) { console.log('\n— ' + t + ' —'); }

const HTML = fs.readFileSync(INDEX, 'utf8');
const ANALYTICS_MANAGER = fs.readFileSync(path.join(ROOT, 'site', 'analytics-consent.js'), 'utf8');
const DAY = 864e5;

/* Boot a fresh DOM of the real page.
   The bootstrap script is injected FIRST so the app sees our stubs. */
function boot({ url = 'http://localhost/index.html', worker = null, storage = null } = {}) {
  const errors = [];
  const bootstrap = `<script>
    window.__errors = [];
    window.addEventListener('error', e => window.__errors.push(String((e && e.message) || e)));
    window.__worker = ${JSON.stringify(worker)};
    window.__calls = [];
    window.fetch = function (u, opt) {
      window.__calls.push(String(u));
      var w = window.__worker || {};
      if (w.mode === 'unreachable') return Promise.reject(new Error('offline'));
      var status = w.status || 200, body = w.body;
      if (!body) {
        if (w.valid) { /* only these codes exist server-side */
          var m = /[?&]code=([^&]+)/.exec(String(u));
          var code = m ? decodeURIComponent(m[1]) : '';
          if (w.valid.indexOf(code.replace(/[^A-Z0-9]/gi, '')) === -1) { status = 404; body = { ok: false, error: 'invalid code' }; }
          else body = { ok: true, code: code, exp: Date.now() + 30 * 864e5 };
        } else {
          body = { ok: true, code: w.code || 'OGA-AAAA-BBBB-CCCC', exp: w.exp || (Date.now() + 30 * 864e5) };
        }
      }
      return Promise.resolve({ ok: status === 200, status: status, json: function () { return Promise.resolve(body); } });
    };
    window.print = function () { window.__printed = (window.__printed || 0) + 1; };
    window.open = function (u) { window.__opened = (window.__opened || []); window.__opened.push(String(u)); return null; };
    window.scrollTo = function () {};
    ${storage ? `try{ ${storage} }catch(e){}` : ''}
  </script>`;
  const html = HTML.replace('<head>', '<head>\n' + bootstrap);

  const virtualConsole = VirtualConsole ? new VirtualConsole() : undefined;
  if (virtualConsole) {
    virtualConsole.on('jsdomError', (e) => {
      const msg = String((e && e.message) || e);
      if (/Not implemented/i.test(msg)) return; // scrollTo etc. — not a product bug
      errors.push(msg);
    });
  }
  const dom = new JSDOM(html, {
    url,
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    ...(virtualConsole ? { virtualConsole } : {}),
  });
  // surface real page errors to the checks (window.onerror + jsdom internal errors)
  dom.__errs = () => (dom.window.__errors || []).concat(errors);
  return dom;
}

const w = (dom) => dom.window;
const $ = (dom, id) => w(dom).document.getElementById(id);
const wait = (ms = 40) => new Promise((r) => setTimeout(r, ms));
/* Top-level `const`/`let` in a classic script are lexical globals — reachable by
   later scripts (and eval) but NOT as window properties. Read them via eval. */
const lex = (dom, expr) => w(dom).eval(expr);
const renamer = (t) => 'render' + t.charAt(0).toUpperCase() + t.slice(1);

/* ============================ 1. BOOT & ROUTES ============================ */
section('boot & routing');
const dom = boot();
const win = w(dom);
await wait(120); // let init() + inline scripts settle
check('page loads with zero uncaught errors', dom.__errs().length === 0, dom.__errs().join(' | ').slice(0, 200));
check('localStorage store wrapper present', typeof lex(dom, 'store') === 'object' && typeof lex(dom, 'store').getItem === 'function');
check('router knows 15 pages (13 + business-setup + team dashboard)', lex(dom, 'PAGES.length') === 15, 'PAGES=' + lex(dom, 'PAGES.length'));

const PAGES = ['home', 'agreement', 'notice', 'receipt', 'invoice', 'employment', 'caution', 'demand', 'payslip', 'warning', 'poa', 'docs', 'pricing', 'business-setup'];
let routeOk = 0, routeBad = [];
for (const p of PAGES) {
  win.location.hash = '#' + p;
  win.dispatchEvent(new win.Event('hashchange'));
  const el = $(dom, 'page-' + p);
  if (el && el.style.display === 'block') routeOk++;
  else routeBad.push(p);
}
check('all 14 routes render their page', routeOk === 14, 'broken: ' + routeBad.join(','));
win.location.hash = '#not-a-real-page';
win.dispatchEvent(new win.Event('hashchange'));
check('unknown hash falls back to home', $(dom, 'page-home').style.display === 'block');

/* ---------- pricing page is a revenue surface — guard its copy ---------- */
section('pricing page (revenue surface)');
win.location.hash = '#pricing';
win.dispatchEvent(new win.Event('hashchange'));
const priceSec = $(dom, 'page-pricing');
check('pricing route renders', priceSec.style.display === 'block');

const priceText = priceSec.textContent;
const cards = priceSec.querySelectorAll('.price-card');
check('pricing shows all 3 tiers', cards.length === 3, 'cards=' + cards.length);

// The tool count is stated in marketing copy. It must match the real tool count,
// or we advertise fewer tools than we ship.
const realToolCount = lex(dom, 'Object.keys(RENDERERS).length');
for (const stale of ['All four tools', 'All 9 tools', 'All nine tools', 'All 4 tools']) {
  check('pricing copy is not stale: "' + stale + '"', !priceText.includes(stale), 'found stale copy');
}
check('pricing states the real tool count on Oga Pass',
      priceText.includes('All ' + realToolCount + ' tools') || priceText.includes('All ten tools'),
      'RENDERERS has ' + realToolCount + ' tools');

// The newest, highest-value tool must be named on the paid tier.
check('Oga Pass names Power of Attorney', /power of attorney/i.test(priceText));

// Business tier (owner instruction, 11 Oct 2026: the Business path must be fully
// self-serve — no WhatsApp step for the customer). The card sits in an honest
// "coming soon" state and carries the self-serve notify form, NOT a quote link.
check('Business tier present', priceText.includes('Business'));
const bizCard = [...priceSec.querySelectorAll('.price-card')].find(c => c.textContent.includes('Business'));
check('Business card is marked coming soon (no unmet promises)', !!bizCard && /coming soon/i.test(bizCard.textContent));
check('Business card carries no WhatsApp quote link', !!bizCard && !bizCard.querySelector('a[href*="wa.me"]'));
check('Business card carries the self-serve notify form', !!bizCard && !!bizCard.querySelector('#biz-waitlist #biz-email') && /notify me/i.test(bizCard.textContent));
check('Business notify form posts to the worker waitlist endpoint',
      /\/business\/waitlist/.test(lex(dom, 'bizWaitlistSubmit.toString()')));
check('Business card: "Configure & pay online" entry point is REMOVED while BIZ_LIVE=false (no dead-end purchase)',
      !!bizCard && !bizCard.querySelector('#biz-pay-link') && !/configure &amp; pay online|configure & pay online/i.test(bizCard.innerHTML));
check('BIZ_LIVE gate constant exists and defaults to false (Phase 5 flips it true only when FLW creds are live)',
      (() => { const m = HTML.match(/const BIZ_LIVE\s*=\s*(true|false)/); return !!m && m[1] === 'false'; })());

// Business team core (Phase 1, 11 Oct 2026): magic-link sign-in + firm branding
// through the single freeBanner() chokepoint that all 10 renderers share.
check('Business card carries the team sign-in box', !!bizCard && !!bizCard.querySelector('#biz-team-box'));
check('team sign-in UI is generated and posts to the worker login endpoint',
      /biz-login-email/.test(lex(dom, 'updateTeamUI.toString()')) &&
      /\/business\/login/.test(lex(dom, 'bizLoginSubmit.toString()')));
check('freeBanner() serves firm branding in team mode (chokepoint for all 10 renderers)',
      /teamActive/.test(lex(dom, 'freeBanner.toString()')) && /teamBrandHeader/.test(lex(dom, 'freeBanner.toString()')));
check('team brand header renders firm name + logo',
      /team-logo/.test(lex(dom, 'teamBrandHeader.toString()')) && /team-name/.test(lex(dom, 'teamBrandHeader.toString()')));
check('toolbar badge flips to TEAM in team mode', /badge team/.test(lex(dom, 'renderBadge.toString()')));
check('team boot picks up ?team_token= magic link and stores the session',
      /team_token/.test(HTML) && /docoga_team/.test(HTML));
check('sign-out clears the stored session and re-renders',
      /docoga_team/.test(lex(dom, 'teamSignOut.toString()')) && /renderAll/.test(lex(dom, 'teamSignOut.toString()')));
check('all 10 renderers still route through freeBanner()',
      (HTML.match(/freeBanner\(\)\+/g) || []).length === 10);

// The buy button must still be wired.
check('Oga Pass buy button present and wired',
      !!$(dom, 'buy-btn') && /buyPass\(/.test($(dom, 'buy-btn').getAttribute('onclick') || ''));


section('Power of Attorney (diaspora tool)');
const POWERS_KEYS = ['poa_k1','poa_k2','poa_k3','poa_k4','poa_k5','poa_k6','poa_k7','poa_k8'];

/* ---------- Power of Attorney (diaspora tool, added 8 Oct 2026) ---------- */
win.location.hash = '#poa';
win.dispatchEvent(new win.Event('hashchange'));
check('poa route renders its page', $(dom, 'page-poa').style.display === 'block');

// the 8 selectable powers must exist as real checkboxes
const poaBoxes = POWERS_KEYS.map(k => $(dom, k));
check('all 8 power checkboxes rendered', poaBoxes.every(Boolean), 'missing: ' + POWERS_KEYS.filter((k, i) => !poaBoxes[i]).join(','));

// fill the donor/donee and confirm the deed carries them
$(dom, 'poa_donor').value = 'Chinedu Okafor';
$(dom, 'poa_donee').value = 'Ngozi Okafor';
$(dom, 'poa_prop').value  = '14 Admiralty Way, Lekki Phase 1, Lagos';
$(dom, 'poa_state').value = 'Lagos State';
win.renderPoa();

const deed = $(dom, 'preview-poa').textContent;
check('deed is titled DEED OF POWER OF ATTORNEY', /DEED OF POWER OF ATTORNEY/.test(deed));
check('donor name flows into the deed',  deed.includes('Chinedu Okafor'), deed.slice(0, 120));
check('donee name flows into the deed',  deed.includes('Ngozi Okafor'));
check('property flows into the deed',    deed.includes('14 Admiralty Way'));
check('governing law flows into the deed', deed.includes('Lagos State'));
check('deed states it is NOT a transfer of ownership',
      /does\s+not\s+convey|not a transfer of ownership/i.test(deed));

// ticking a power must add it to the deed
$(dom, 'poa_k2').checked = true;
win.renderPoa();
check('ticked power appears in the deed', $(dom, 'preview-poa').textContent.includes('Let or lease the property'));
$(dom, 'poa_k2').checked = false;
win.renderPoa();
check('unticked power leaves the deed', !$(dom, 'preview-poa').textContent.includes('Let or lease the property'));

// sale power must trigger the Land Use Act s.22 warning
$(dom, 'poa_k8').checked = true;
win.renderPoa();
const sellTxt = $(dom, 'preview-poa').textContent;
check('sale power warns about Governor\'s Consent', /Governor.s Consent/.test(sellTxt));
check('sale power cites Land Use Act s.22', /section 22 of the Land Use Act/.test(sellTxt));
$(dom, 'poa_k8').checked = false;
win.renderPoa();

// the two load-bearing legal warnings must always be present
const base = $(dom, 'preview-poa').textContent;
check('registration warning cites Ojugbele v Olasoji (1982) SC 71', /Ojugbele v. Olasoji/.test(base) && /1982/.test(base));
check('warning says unregistered POA is inadmissible', /inadmissible/.test(base));
check('warning says Nigeria is not on the Hague Apostille Convention', /Hague Apostille Convention/.test(base));
check('not-legal-advice disclaimer present', /not legal advice/i.test(base));

// collect/apply round-trip
const snap = win.collectPoa();
check('collectPoa captures donor', snap.poa_donor === 'Chinedu Okafor');
win.applyPoa(Object.assign({}, snap, { poa_donor: 'Amaka Balogun' }));
check('applyPoa restores a saved draft', $(dom, 'poa_donor').value === 'Amaka Balogun');
win.applyPoa(snap);

// renderAll must not throw with the new tool in the chain
let allOk = true; try { win.renderAll(); } catch (e) { allOk = false; }
check('renderAll runs cleanly with the poa tool', allOk);
check('no uncaught errors from the poa tool', dom.__errs().length === 0, dom.__errs().join(' | ').slice(0, 200));


/* ============================ 2. NUMBER WORDS ============================ */
section('naira amount-in-words (legal documents)');
const numCases = [[0, 'Zero'], [7, 'Seven'], [15, 'Fifteen'], [42, 'Forty-Two'], [100, 'One Hundred'], [115, 'One Hundred and Fifteen'],
  [1000, 'One Thousand'], [2000, 'Two Thousand'], [55000, 'Fifty-Five Thousand'],
  [1500000, 'One Million, Five Hundred Thousand'], [12000000, 'Twelve Million'],
  [2500000000, 'Two Billion, Five Hundred Million']];
let numOk = 0, numBad = [];
for (const [n, want] of numCases) {
  const got = win.numWords(n);
  if (got === want) numOk++; else numBad.push(n + '→"' + got + '" want "' + want + '"');
}
check('numWords correct on ' + numCases.length + ' amounts', numOk === numCases.length, numBad.join(' ; '));
check('nairaWords wraps amount + ₦ value', /^Two Thousand \(₦2,000\) Naira Only$/.test(win.nairaWords(2000)), win.nairaWords(2000));
check('nairaWords(1500000) has naira formatting', win.nairaWords(1500000).includes('₦1,500,000'));

/* ============================ 3. ALL 9 TOOLS ============================ */
section('all 10 document tools (fill → render → hostile input)');
const HOSTILE = '<img src=x onerror=window.__xss=1><script>window.__xss=1</script>"\'';
const FIELDS = {
  agreement: ['ll_name', 'll_addr', 'll_phone', 'tt_name', 'tt_addr', 'tt_phone', 'prop_desc', 'prop_state', 'prop_addr', 'rent_amt', 'rent_period', 'deposit_amt', 'start_date', 'term_months', 'notice', 'prepared_by', 'custom_clauses'],
  notice: ['n_from', 'n_fromaddr', 'n_to', 'n_toaddr', 'n_prop', 'n_period', 'n_date', 'n_reason'],
  receipt: ['r_no', 'r_date', 'r_from', 'r_amt', 'r_method', 'r_purpose', 'r_prop', 'r_period', 'r_bal', 'r_issuer', 'r_phone'],
  invoice: ['i_biz', 'i_bizphone', 'i_no', 'i_date', 'i_due', 'i_client', 'i_vat', 'i_disc', 'i_notes'],
  employment: ['e_biz', 'e_addr', 'e_emp', 'e_role', 'e_start', 'e_sal', 'e_prob', 'e_leave', 'e_notice', 'e_hours', 'e_loc', 'e_duties'],
  caution: ['c_no', 'c_date', 'c_from', 'c_amt', 'c_method', 'c_prop', 'c_period', 'c_issuer', 'c_phone'],
  demand: ['d_from', 'd_addr', 'd_to', 'd_toaddr', 'd_date', 'd_amt', 'd_debt', 'd_due', 'd_days'],
  payslip: ['p_biz', 'p_addr', 'p_emp', 'p_role', 'p_id', 'p_period', 'p_date', 'p_basic', 'p_house', 'p_trans', 'p_other', 'p_paye', 'p_pen', 'p_nhf', 'p_ded', 'p_bank', 'p_acct', 'p_note'],
  warning: ['w_biz', 'w_addr', 'w_emp', 'w_role', 'w_date', 'w_count', 'w_incident', 'w_offence', 'w_prior', 'w_expect', 'w_deadline', 'w_signer'],
  poa: ['poa_donor', 'poa_donor_addr', 'poa_donor_id', 'poa_donor_occ', 'poa_donee', 'poa_donee_addr', 'poa_donee_id', 'poa_rel', 'poa_prop', 'poa_purpose', 'poa_date', 'poa_expiry', 'poa_state', 'poa_witness'],
};
const RENDERERS = ['agreement', 'notice', 'receipt', 'invoice', 'employment', 'caution', 'demand', 'payslip', 'warning', 'poa'];
const PREVIEW = { agreement: 'preview-agreement', notice: 'preview-notice', receipt: 'preview-receipt', invoice: 'preview-invoice', employment: 'preview-employment', caution: 'preview-caution', demand: 'preview-demand', payslip: 'preview-payslip', warning: 'preview-warning', poa: 'preview-poa' };

let fillOk = 0, missing = [];
for (const t of RENDERERS) {
  for (const id of FIELDS[t]) {
    const el = $(dom, id);
    if (!el) { missing.push(id); continue; }
    try { el.value = HOSTILE; fillOk++; } catch (e) { missing.push(id); }
  }
}
check('every tool field exists and accepts input (' + Object.values(FIELDS).flat().length + ' fields)', missing.length === 0, 'missing: ' + missing.slice(0, 8).join(','));

let renderOk = 0, renderBad = [];
for (const t of RENDERERS) {
  try {
    win[renamer(t)]();
    const html = $(dom, PREVIEW[t]).innerHTML;
    const live = $(dom, PREVIEW[t]).querySelectorAll('script,img,[onerror],[onload]');
    // hostile payload must be inert: no live script/img/onerror nodes, text only
    if (html.length > 400 && live.length === 0) renderOk++;
    else renderBad.push(t + '(len=' + html.length + ',live=' + live.length + ')');
  } catch (e) { renderBad.push(t + ' threw ' + e.message); }
}
check('all 10 tools render documents with hostile input inert', renderOk === 10, renderBad.join(' ; '));
check('XSS payload did not execute anywhere', !win.__xss);
check('hostile text is escaped in output', $(dom, PREVIEW.agreement).innerHTML.includes('&lt;img') && !$(dom, PREVIEW.agreement).innerHTML.includes('<img'));

/* free banner present while on FREE plan, and prints into every doc */
let bannerInAll = true;
for (const t of RENDERERS) if (!$(dom, PREVIEW[t]).innerHTML.includes('free-banner')) bannerInAll = false;
check('FREE plan watermarks every document', bannerInAll);

/* ============================ 4. PRINT PATH ============================ */
section('print / save-as-PDF path');
let printOk = 0, printBad = [];
for (const t of RENDERERS) {
  try {
    win.printCurrent(t);
    const pr = $(dom, 'print-root');
    if ((pr.innerHTML || '').length > 300 && $(dom, 'print-root').querySelectorAll('script,img,[onerror]').length === 0) printOk++;
    else printBad.push(t);
  } catch (e) { printBad.push(t + ':' + e.message); }
  win.document.body.classList.remove('printing');
  $(dom, 'print-root').innerHTML = '';
}
check('printCurrent works for all 10 tools (7-tool-map regression guard)', printOk === 10, 'failed: ' + printBad.join(','));
check('window.print() was called', (win.__printed || 0) > 0);

/* ============================ 5. SHARE / WHATSAPP ============================ */
section('share to WhatsApp');
let shareOk = 0, shareBad = [];
for (const t of RENDERERS) {
  try {
    win.__opened = [];
    win.shareDoc(t);
    const url = (win.__opened || [])[0] || '';
    if (url.startsWith('https://wa.me/?text=') && url.includes('DocOga')) shareOk++;
    else shareBad.push(t + '→' + url.slice(0, 40));
  } catch (e) { shareBad.push(t + ':' + e.message); }
}
check('shareDoc builds a WhatsApp link for all 10 tools', shareOk === 10, shareBad.join(' ; '));

/* ============================ 6. DOCUMENTS STORE ============================ */
section('saved documents (My Documents)');
win.saveDoc('agreement');
win.saveDoc('payslip');
let docs = win.getDocs();
check('saving 2 documents stores 2', docs.length === 2, 'got ' + docs.length);
check('saved docs carry type + a readable title', docs.every((d) => d.type && d.title && d.title.length > 3));
win.renderDocs();
const listHtml = $(dom, 'docs-list').innerHTML;
check('docs list renders buttons for each doc', (listHtml.match(/link-btn/g) || []).length >= 6);
check('docs list escapes hostile titles', $(dom, 'docs-list').querySelectorAll('script,img,[onerror]').length === 0);
const firstId = win.getDocs()[0].id;
win.openDoc(firstId);
await wait(120);
check('openDoc restores the document fields', $(dom, win.getDocs()[0].type === 'payslip' ? 'p_emp' : 'll_name').value === HOSTILE);
win.delDoc(firstId);
check('delDoc removes exactly one document', win.getDocs().length === 1);
/* hostile / corrupt docs store must not break the list */
lex(dom, 'store').setItem('docoga_docs', '{"not":"an array"}');
let survived = true;
try { win.renderDocs(); } catch (e) { survived = false; }
check('corrupt documents store does not crash the list', survived && $(dom, 'docs-list').innerHTML.length > 0);
lex(dom, 'store').setItem('docoga_docs', JSON.stringify([{ id: 1, type: 'evil-unknown-type', title: 'x', ts: 'not-a-date', payload: {} }]));
survived = true;
try { win.renderDocs(); } catch (e) { survived = false; }
check('document with unknown type renders without throwing', survived);

/* ============================ 7. DRAFTS ============================ */
section('draft auto-save / restore');
lex(dom, 'store').removeItem('docoga_docs');
lex(dom, 'store').setItem('docoga_draft_notice', JSON.stringify({ n_to: 'Chief Ade', n_from: 'Landlord Bello', n_prop: '12 Aba Road' }));
const dom2 = boot({ storage: "localStorage.clear(); localStorage.setItem('docoga_draft_notice', JSON.stringify({n_to:'Chief Ade',n_from:'Landlord Bello'}));" });
await wait(140);
check('draft is restored into the form on load', $(dom2, 'n_to').value === 'Chief Ade', 'got "' + $(dom2, 'n_to').value + '"');
check('storage survives across a fresh page load', $(dom2, 'n_from').value === 'Landlord Bello');

/* ============================ 8. PASS ACTIVATION (mocked worker) ========== */
section('Oga Pass — activation, top-up, fence, expiry');
const OKCODE = 'OGA-ABCD-EFGH-JKLM';

/* 8a. clean activation */
const d3 = boot({ worker: { valid: [OKCODE.replace(/-/g, '')] } });
await wait(120);
check('starts on FREE plan (banner on docs)', !w(d3).passActive() && $(d3, 'pass-chip').textContent === 'FREE PLAN');
w(d3).submitCode(OKCODE);
await wait(120);
check('valid code activates the pass', w(d3).passActive());
check('chip shows OGA PASS + days left', /OGA PASS ✓ \d+d/.test($(d3, 'pass-chip').textContent), $(d3, 'pass-chip').textContent);
check('buy button becomes a status, not an upsell', /Pass active/.test($(d3, 'buy-btn').textContent));
w(d3).renderAgreement();
check('watermark disappears for pass holders', !$(d3, 'preview-agreement').innerHTML.includes('free-banner'));
check('badge flips to OGA PASS', $(d3, 'badge-agreement').innerHTML.includes('OGA PASS'));
check('pass persisted to localStorage', !!JSON.parse(lex(d3, 'store').getItem('docoga_pass') || 'null'));
check('activation sent the device id (server fence)', (w(d3).__calls.join(' ') || '').includes('did='));
check('worker was actually called (not the offline fallback)', w(d3).__calls.length > 0);
w(d3).submitCode('OGA-1111-1111-1111'); // invalid-but-well-formed
await wait(80);
check('unknown code is rejected with a toast', /Invalid code/i.test($(d3, 'toast').textContent), $(d3, 'toast').textContent);

/* 8b. same code re-entered → no double activation, no extra worker call */
const d4 = boot({ worker: { mode: 'ok', body: { ok: true, code: OKCODE, exp: Date.now() + 30 * DAY } } });
await wait(120);
w(d4).submitCode(OKCODE); await wait(80);
const callsAfterFirst = w(d4).__calls.length;
const expAfterFirst = JSON.parse(lex(d4, 'store').getItem('docoga_pass')).exp;
w(d4).submitCode(OKCODE); await wait(80);
check('re-entering the same code adds NO days', JSON.parse(lex(d4, 'store').getItem('docoga_pass')).exp === expAfterFirst);
check('re-entering the same code short-circuits (no worker round-trip)', w(d4).__calls.length === callsAfterFirst);
check('re-entry explains top-up instead of silently stacking', /already active/i.test($(d4, 'toast').textContent), $(d4, 'toast').textContent);

/* 8c. top-up: new code, remaining days carry over from the server */
const carryExp = Date.now() + 42 * DAY; // 12 remaining + 30 new
const d5 = boot({ worker: { mode: 'ok', body: { ok: true, code: 'OGA-NEWN-EWNE-WNEW', exp: carryExp } } });
await wait(120);
w(d5).submitCode('OGA-OLDX-OLDX-OLDX'); await wait(80);
w(d5).submitCode('OGA-NEWN-EWNE-WNEW'); await wait(80);
const pass5 = JSON.parse(lex(d5, 'store').getItem('docoga_pass'));
check('top-up adopts the newest code', pass5.c.replace(/-/g, '') === 'OGANEWNEWNEWNEW');
check('top-up keeps the server expiry (days carried over)', Math.abs(pass5.exp - carryExp) < 1000);
check('top-up sends the previous code for server linking', w(d5).__calls.some((u) => u.includes('prev=')));

/* 8d. renewed (dead) code → adopts the newest code + its expiry */
const d6 = boot({ worker: { status: 410, body: { ok: false, error: 'This code was renewed — your newest code is the active one.', renewedCode: 'OGA-NEWN-EWNE-WNEW', exp: Date.now() + 20 * DAY } } });
await wait(120);
w(d6).submitCode('OGA-OLDX-OLDX-OLDX'); await wait(80);
check('renewed code silently adopts the newest code', (JSON.parse(lex(d6, 'store').getItem('docoga_pass') || 'null') || {}).c === 'OGA-NEWN-EWNE-WNEW');
check('adopted pass is active again', w(d6).passActive());

/* 8e. expired code → rejected, nothing stored */
const d7 = boot({ worker: { status: 403, body: { ok: false, error: 'This code has expired — buy a new Oga Pass (₦2,000).' } } });
await wait(120);
w(d7).submitCode('OGA-EXPR-EXPR-EXPR'); await wait(80);
check('expired code is refused', !w(d7).passActive());
check('expired message shown to the buyer', /expired/i.test($(d7, 'toast').textContent));

/* 8f. 4th device fence → refused, no pass stored */
const d8 = boot({ worker: { status: 403, body: { ok: false, error: 'This pass is already active on 3 devices. Oga Pass is one-person — your own is just ₦2,000 at docoga.com.ng, or tap WhatsApp support if this is your own new device.' } } });
await wait(120);
w(d8).submitCode(OKCODE); await wait(80);
check('4th device is blocked', !w(d8).passActive());
check('4th-device message reaches the customer', /3 devices/i.test($(d8, 'toast').textContent));
check('4th-device block does NOT wipe an existing pass elsewhere (server-side fence only)', $(d8, 'pass-chip').textContent === 'FREE PLAN');

/* 8g. worker down + offline batch code → still activates locally.
   The 200 plaintext codes live in gitignored unlock-codes.txt, so the suite proves
   the mechanism deterministically: it registers a known hash at runtime and drives
   the real fallback path (no worker round-trip). */
const d9 = boot({ worker: { mode: 'unreachable' } });
await wait(120);
const OFFLINE_CODE = 'OGA-TEST-CODE-1234';
check('offline batch set is intact (200 hashes)', lex(d9, 'CODE_HASHES.size') === 200, 'size=' + lex(d9, 'CODE_HASHES.size'));
lex(d9, 'CODE_HASHES').add(w(d9).fnv1a(OFFLINE_CODE.replace(/-/g, '')).toString(16).padStart(8, '0'));
w(d9).submitCode(OFFLINE_CODE);
await wait(80);
check('offline batch code activates even when the worker is unreachable', w(d9).passActive());
check('offline activation did not pretend to be a server activation', (w(d9).__calls || []).length > 0, 'fetch attempted then fell back');
const d9b = boot({ worker: { mode: 'unreachable' } });
await wait(120);
w(d9b).submitCode('OGA-NOPE-NOPE-NOPE');
await wait(80);
check('random code still refused while offline', !w(d9b).passActive());

/* 8h. passes that expire locally get cleared by the sync badge/UI */
const d10 = boot({ worker: { mode: 'ok', body: { ok: true, code: 'OGA-XXXX-YYYY-ZZZZ', exp: Date.now() - 1 } }, storage: "localStorage.setItem('docoga_pass', JSON.stringify({exp: Date.now()-1, c:'OGA-XXXX-YYYY-ZZZZ', h:'deadbeef'}));" });
await wait(160);
check('locally expired pass shows FREE again', !w(d10).passActive(), $(d10, 'pass-chip').textContent);

/* ============================ 9. MAGIC LINK ============================== */
section('magic pass link (#code=…)');
const d11 = boot({ url: 'http://localhost/index.html#code=' + OKCODE, worker: { mode: 'ok', body: { ok: true, code: OKCODE, exp: Date.now() + 30 * DAY } } });
await wait(200);
check('magic link auto-activates the pass', w(d11).passActive());
check('magic link strips the code from the address bar', !w(d11).location.hash.includes('code='), 'hash=' + w(d11).location.hash);
const d12 = boot({ url: 'http://localhost/index.html?code=' + OKCODE, worker: { mode: 'ok', body: { ok: true, code: OKCODE, exp: Date.now() + 30 * DAY } } });
await wait(200);
check('?code= variant also activates', w(d12).passActive());
const d13 = boot({ url: 'http://localhost/index.html#code=OGA-BAD', worker: { mode: 'ok', body: { ok: false, error: 'invalid code' } } });
await wait(200);
check('short/garbage magic link stores nothing', !w(d13).passActive());

/* ============================ 10. HOSTILE STORAGE ======================== */
section('hostile / corrupt local storage');
const corrupt = [
  ['docoga_pass', 'not-json{{'],
  ['docoga_pass', '{"exp":"soon","c":123}'],
  ['docoga_docs', 'null'],
  ['docoga_draft_agreement', '{"ll_name":{"nested":"object"}}'],
  ['docoga_profile', '[]'],
];
let corruptOk = 0, corruptBad = [];
for (const [k, v] of corrupt) {
  try {
    const d = boot({ storage: `localStorage.setItem(${JSON.stringify(k)}, ${JSON.stringify(v)});` });
    await wait(120);
    d.window.renderAll();
    d.window.route();
    if (d.__errs().length === 0) corruptOk++; else corruptBad.push(k + ':' + d.__errs()[0]);
  } catch (e) { corruptBad.push(k + ':boot threw ' + e.message); }
}
check('app survives ' + corrupt.length + ' corrupt-storage permutations', corruptOk === corrupt.length, corruptBad.join(' | ').slice(0, 200));

/* ============================ 11. CONFIG GUARDS ========================== */
/* ============================ BUSINESS TEAM MODE (PHASE 1) ============================ */
section('Business team mode — branded rendering end-to-end (Phase 1 gate)');
const teamLogo = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
const teamStorage = `
  window.fetch = function (u, opt) {
    u = String(u); window.__calls.push(u);
    if (u.indexOf('/business/team') !== -1) return Promise.resolve({ ok: true, status: 200, json: function(){ return Promise.resolve({ ok: true, team: { id: 't1', slug: 'firm', name: 'Firm & Co', status: 'active', expiry: '2027-01-01', plan: 'starter' }, email: 'owner@firm.ng', role: 'owner', seats: [{ email: 'owner@firm.ng', name: 'Owner', role: 'owner', status: 'active' }], brand: { name: 'Firm & Co', address: '12 Agents Rd, Abuja', logo: ${JSON.stringify(teamLogo)} } }); } });
    return Promise.resolve({ ok: false, status: 404, json: function(){ return Promise.resolve({ ok: false, error: 'nope' }); } });
  };
  try { localStorage.setItem('docoga_team', JSON.stringify({ token: 'tl_t1|owner@firm.ng|9999999999.sig', team: { id: 't1', name: 'Firm & Co', slug: 'firm' }, email: 'owner@firm.ng', role: 'owner', exp: 9999999999 })); } catch(e) {}
`;
const teamDom = boot({ storage: teamStorage });
const tWin = teamDom.window;
await new Promise(res => setTimeout(res, 60));
check('stored team session restored + /business/team re-validated on boot', (tWin.__calls || []).some(u => u.indexOf('/business/team') !== -1));
let brandedAll = 0, brandedBad = [];
for (const t of RENDERERS) {
  try {
    tWin.printCurrent(t);
    const pr = $(teamDom, 'print-root');
    const tb = pr.querySelector('.team-banner');
    const ok = tb && /Firm & Co/.test(tb.textContent) && !!pr.querySelector('img.team-logo') && !pr.querySelector('.free-banner');
    if (ok) brandedAll++; else brandedBad.push(t);
    tWin.document.body.classList.remove('printing');
    $(teamDom, 'print-root').innerHTML = '';
  } catch (e) { brandedBad.push(t + ':' + e.message); }
}
check('ALL 10 tools render the firm banner (name + logo) with no DocOga banner (Phase 1 gate)', brandedAll === 10, 'failed: ' + brandedBad.join(','));
check('signed-in chip replaces the sign-in form on the Business card',
      !!teamDom.window.document.querySelector('#biz-team-box .team-chip') && /signed in as/i.test(teamDom.window.document.querySelector('#biz-team-box').textContent));
tWin.teamSignOut();
tWin.printCurrent('agreement');
const tPr2 = $(teamDom, 'print-root');
check('sign-out restores the DocOga free banner immediately', !!tPr2.querySelector('.free-banner') && !tPr2.querySelector('.team-banner'));
check('sign-out restores the sign-in form', !!teamDom.window.document.querySelector('#biz-team-box #biz-login-email'));

/* ============================ BUSINESS CONFIGURATOR + CHECKOUT (PHASE 2) ============================ */
section('Business configurator + checkout (Phase 2)');
check('business-setup page registered in the router', lex(dom, "PAGES.indexOf('business-setup')") !== -1);
check('configurator page present with the four segment presets',
      !!dom.window.document.getElementById('page-business-setup') &&
      !!dom.window.document.getElementById('biz-seg-estate-agent') &&
      !!dom.window.document.getElementById('biz-seg-hr-team') &&
      !!dom.window.document.getElementById('biz-cfg-quote'));
check('published formula: 3/100 → ₦96,000 base, ₦103,200 total (VAT line)',
      (() => { const q = lex(dom, 'bizQuote(3,100)'); return q.price === 96000 && q.vat === 7200 && q.total === 103200 && q.tier === 'starter'; })());
check('published formula: 25/1000 → ₦720,000 · 8/300 → ₦240,000 · 2/5000 → ₦978,000',
      (() => { return lex(dom, 'bizQuote(25,1000)').price === 720000 && lex(dom, 'bizQuote(8,300)').price === 240000 && lex(dom, 'bizQuote(2,5000)').price === 978000; })());
lex(dom, 'bizUpdateQuote()');
check('live quote renders base + VAT + total for the defaults',
      /₦96,000/.test($(dom, 'biz-cfg-quote').textContent) && /VAT/.test($(dom, 'biz-cfg-quote').textContent) && /Total \/ year/.test($(dom, 'biz-cfg-quote').textContent));
$(dom, 'biz-cfg-seats').value = '25';
lex(dom, 'bizUpdateQuote()');
check('quote recomputes on input (25 seats → growth base + 5 seat units, ₦774,000 total)',
      /₦480,000/.test($(dom, 'biz-cfg-quote').textContent) && /\+5 seats/.test($(dom, 'biz-cfg-quote').textContent) && /₦774,000/.test($(dom, 'biz-cfg-quote').textContent));
check('create-team posts to /business/teams; payment entry point present in SOURCE (BIZ_LIVE gate controls its runtime visibility)',
      /\/business\/teams/.test(lex(dom, 'bizCreateTeam.toString()')) &&
      /id="biz-pay-link"[^>]*href="#business-setup"/.test(HTML));
check('checkout posts to /business/team/charge (transfer VA panel + card hosted URL)',
      (() => { const s = lex(dom, 'bizCharge.toString()'); return /\/business\/team\/charge/.test(s) && /biz-va-panel/.test(s) && /pay_url/.test(s); })());
const unpaidStorage = `
  window.fetch = function (u, opt) {
    u = String(u); window.__calls.push(u);
    if (u.indexOf('/business/team') !== -1) return Promise.resolve({ ok: true, status: 200, json: function(){ return Promise.resolve({ ok: true, team: { id: 't9', slug: 'pf', name: 'Pay First', status: 'unpaid', expiry: '', plan: 'starter' }, email: 'pay@first.co', role: 'owner', seats: [], brand: {}, quote: { tier: 'starter', seats: 3, docs: 100, extraSeats: 0, extraBlocks: 0, price: 96000, vat: 7200, total: 103200 } }); } });
    return Promise.resolve({ ok: false, status: 404, json: function(){ return Promise.resolve({ ok: false, error: 'nope' }); } });
  };
  try { localStorage.setItem('docoga_team', JSON.stringify({ token: 'tl_t9|pay@first.co|9999999999.sig', team: { id: 't9', name: 'Pay First', slug: 'pf', status: 'unpaid' }, email: 'pay@first.co', role: 'owner', exp: 9999999999 })); } catch(e) {}
`;
const upDom = boot({ storage: unpaidStorage });
await new Promise(res => setTimeout(res, 60));
check('unpaid team → checkout panel with total + transfer/card buttons',
      /₦103,200/.test(upDom.window.document.querySelector('#biz-team-box').textContent) &&
      !!upDom.window.document.querySelector('#biz-team-box [onclick*="transfer"]') &&
      !!upDom.window.document.querySelector('#biz-team-box [onclick*="card"]'));
upDom.window.printCurrent('agreement');
const upPr = $(upDom, 'print-root');
check('unpaid team documents still carry the DocOga banner (branding is what is paid for)',
      !!upPr.querySelector('.free-banner') && !upPr.querySelector('.team-banner'));

/* ============================ TEAM PORTAL (PHASE 3) ============================ */
section('Team portal + support surface (Phase 3)');
check('team dashboard route registered with the portal container',
      lex(dom, "PAGES.indexOf('team')") !== -1 &&
      !!dom.window.document.getElementById('page-team') &&
      !!dom.window.document.getElementById('team-portal'));
check('signed-out visitor → portal shows the sign-in hint (magic link) + setup link',
      /Sign in to your team dashboard/.test($(dom, 'team-portal').textContent) &&
      !!dom.window.document.querySelector('#team-portal #tp-login-email') &&
      !!dom.window.document.querySelector('#team-portal a[href="#business-setup"]'));
/* Phase 1 signed teamDom out (banner-restore check) — boot a fresh active-team DOM for the portal */
const teamDom3 = boot({ storage: teamStorage });
await new Promise(res => setTimeout(res, 80));
const tpAct = teamDom3.window.document.querySelector('#team-portal');
check('active team → portal shows the licence card (firm + ACTIVE + expiry)',
      /Firm & Co/.test(tpAct.textContent) && /ACTIVE · until/.test(tpAct.textContent),
      tpAct.textContent.slice(0, 160));
check('owner gets the branding editor (firm name pre-filled, logo input PNG/JPG/SVG)',
      !!teamDom3.window.document.querySelector('#team-portal #tp-brand-name') &&
      teamDom3.window.document.querySelector('#team-portal #tp-brand-name').value === 'Firm & Co' &&
      /image\/svg\+xml/.test(teamDom3.window.document.querySelector('#team-portal #tp-brand-logo').getAttribute('accept') || ''));
check('seats card lists the owner seat + the invite form (owner only)',
      /owner@firm\.ng/.test(tpAct.textContent) &&
      !!teamDom3.window.document.querySelector('#team-portal #tp-invite-email'));
check('invoices card present + support card links business@ and the FAQ',
      !!teamDom3.window.document.querySelector('#team-portal #tp-invoices') &&
      !!teamDom3.window.document.querySelector('#team-portal a[href="mailto:business@docoga.com.ng"]') &&
      !!teamDom3.window.document.querySelector('#team-portal a[href="support.html"]'));
check('active + unpaid chips both get the “Team dashboard →” link',
      !!teamDom3.window.document.querySelector('#biz-team-box a[href="#team"]') &&
      !!upDom.window.document.querySelector('#biz-team-box a[href="#team"]'));
check('unpaid team portal → UNPAID licence card with the quote total + pay buttons',
      /UNPAID/.test($(upDom, 'team-portal').textContent) &&
      /₦103,200/.test($(upDom, 'team-portal').textContent) &&
      !!upDom.window.document.querySelector('#team-portal [onclick*="transfer"]'),
      'portal=' + $(upDom, 'team-portal').textContent.slice(0, 160) + ' | chip=' + upDom.window.document.querySelector('#biz-team-box').textContent.slice(0,120));
check('teamRefresh persists the seats list for the portal',
      lex(dom, 'teamRefresh.toString()').includes('team.seats=j.seats'));
check('portal wiring: invoices list + printable invoice links + seats actions + brand PUT',
      (() => {
        const inv = lex(dom, 'teamInvoicesLoad.toString()');
        const seatA = lex(dom, 'teamInvite.toString()') + lex(dom, 'teamRevoke.toString()');
        const brand = lex(dom, 'teamBrandSave.toString()');
        return inv.includes('/business/team/invoices') && inv.includes('/business/invoice/') &&
               seatA.includes('/business/team/seats') && seatA.includes("action:'invite'") && seatA.includes("action:'revoke'") &&
               brand.includes('/business/team/brand') && brand.includes("method:'PUT'");
      })());
check('logo upload validated client-side: type whitelist + 25KB cap',
      (() => { const s = lex(dom, 'teamBrandLogoChange.toString()'); return s.includes('25*1024') && s.includes('png|jpe?g|svg'); })());
const supportHtml = fs.readFileSync(path.join(ROOT, 'site', 'support.html'), 'utf8');
check('support.html: noindex, business@ everywhere, wrong-amount + renewal + data answers',
      /noindex/.test(supportHtml) && (supportHtml.match(/business@docoga\.com\.ng/g) || []).length >= 5 &&
      /wrong amount/i.test(supportHtml) && /renew/i.test(supportHtml) && /Privacy Policy/.test(supportHtml));
check('support.html makes NO fixed REFUND-window promise (§11 pending; the 14-day GRACE period is lifecycle, not refunds)',
      !/14[- ]day[^<]{0,80}refund/i.test(supportHtml) && !/refund[^<]{0,80}14[- ]day/i.test(supportHtml));
check('privacy.html: Business Teams section (account data spelled out) + dated 13 Oct',
      /<h2>5\. Business teams<\/h2>/.test(fs.readFileSync(path.join(ROOT, 'site', 'privacy.html'), 'utf8')) &&
      /13 October 2026/.test(fs.readFileSync(path.join(ROOT, 'site', 'privacy.html'), 'utf8')));
check('footer links the public support page', !!dom.window.document.querySelector('footer a[href="support.html"]'));

/* ============================ AUTONOMY (PHASE 4) ============================ */
section('Autonomy — renewal + usage metering (Phase 4)');
check('renewal posts to /business/team/renew (owner; server owns window + price)',
      (() => { const s = lex(dom, 'bizRenew.toString()'); return /\/business\/team\/renew/.test(s) && s.includes("method:'POST'") && /biz-renew-panel/.test(s); })());
check('usage beacon: best-effort, non-blocking, throttled (C8 honesty)',
      (() => { const s = lex(dom, 'usageBeacon.toString()'); return /\/business\/team\/usage/.test(s) && s.includes('keepalive:true') && /10\*60\*1000/.test(s) && /teamActive/.test(s); })());
check('revenue funnel events wired for BOTH funnels (retail pass + business) with gtag guard',
      (() => { const s = HTML; const g = lex(dom, 'trackEvent.toString()');
        return ['pass_checkout_opened','pass_activated','pass_topup','business_team_created','business_charge_started','business_team_activated','business_renewal_started'].every(n => s.includes(n)) && /window\.gtag/.test(g); })());
const p4Team = (over) => `
  window.fetch = function (u, opt) {
    u = String(u); window.__calls.push(u);
    if (u.indexOf('/business/team') !== -1) return Promise.resolve({ ok: true, status: 200, json: function(){ return Promise.resolve(${JSON.stringify(Object.assign({ ok: true, team: { id: 'tp4', slug: 'p4', name: 'P4 Firm', status: 'active', expiry: '2026-11-10', plan: 'starter' }, email: 'o@p4.ng', role: 'owner', seats: [], brand: {} }, over))}); } });
    return Promise.resolve({ ok: false, status: 404, json: function(){ return Promise.resolve({ ok: false, error: 'nope' }); } });
  };
  try { localStorage.setItem('docoga_team', JSON.stringify({ token: 'tl_tp4|o@p4.ng|9999999999.sig', team: { id: 'tp4', name: 'P4 Firm', slug: 'p4', status: 'active' }, email: 'o@p4.ng', role: 'owner', exp: 9999999999 })); } catch(e) {}
`;
const nearDom = boot({ storage: p4Team({ team: { id: 'tp4', slug: 'p4', name: 'P4 Firm', status: 'active', expiry: '2026-11-10', plan: 'starter' }, renewal: { base: 96000, vat: 7200, total: 103200, expiry: '2026-11-10', status: 'active' }, usage: { used: 120, band: 100 } }) });
await new Promise(res => setTimeout(res, 80));
const nearP = nearDom.window.document.querySelector('#team-portal');
check('active near expiry (T-30) → renewal offered at the PURCHASE price with both methods',
      /Renews/.test(nearP.textContent) && /₦103,200/.test(nearP.textContent) &&
      !!nearDom.window.document.querySelector('#team-portal [onclick*="bizRenew"]') &&
      !!nearDom.window.document.querySelector('#team-portal #biz-renew-panel'));
check('monthly allowance line renders overage honestly (120/100 = soft, no cut-off)',
      /Documents this month:/.test(nearP.textContent) && /120 \/ 100/.test(nearP.textContent) && /soft/i.test(nearP.textContent));
nearDom.window.printCurrent('agreement');
check('branded print fires the usage beacon (non-blocking, throttled)',
      (nearDom.window.__calls || []).some(u => u.indexOf('/business/team/usage') !== -1));
const graceDom = boot({ storage: p4Team({ team: { id: 'tp4', slug: 'p4', name: 'P4 Firm', status: 'grace', expiry: '2026-09-01', plan: 'starter' }, renewal: { base: 96000, vat: 7200, total: 103200, expiry: '2026-09-01', status: 'grace' } }) });
await new Promise(res => setTimeout(res, 80));
const graceP = graceDom.window.document.querySelector('#team-portal');
check('grace team → 14-day grace card + self-serve Renew + chip hint (no beacon: not active)',
      /14-day grace/.test(graceP.textContent) &&
      !!graceDom.window.document.querySelector('#team-portal [onclick*="bizRenew"]') &&
      /grace/i.test(graceDom.window.document.querySelector('#biz-team-box').textContent) &&
      !(graceDom.window.__calls || []).some(u => u.indexOf('/business/team/usage') !== -1));
const freeDom = boot({ storage: p4Team({ team: { id: 'tp4', slug: 'p4', name: 'P4 Firm', status: 'free', expiry: '2026-09-01', plan: 'starter' }, renewal: { base: 96000, vat: 7200, total: 103200, expiry: '2026-09-01', status: 'free' } }) });
await new Promise(res => setTimeout(res, 80));
const freeP = freeDom.window.document.querySelector('#team-portal');
check('free-tier team → 90-day retention notice + self-serve Renew (reactivation at purchase price)',
      /free tier/.test(freeP.textContent) && /90 days/.test(freeP.textContent) &&
      !!freeDom.window.document.querySelector('#team-portal [onclick*="bizRenew"]'));

section('config values used by customers');
const CFG = { PAYMENT_URL: lex(dom, 'PAYMENT_URL'), SUPPORT_WHATSAPP: lex(dom, 'SUPPORT_WHATSAPP'), SITE_URL: lex(dom, 'SITE_URL'), WORKER_URL: lex(dom, 'WORKER_URL') };
check('PAYMENT_URL is a live https link', /^https:\/\/flutterwave\.com\/pay\//.test(CFG.PAYMENT_URL), CFG.PAYMENT_URL);
check('SUPPORT_WHATSAPP is intl format (no + or spaces)', /^\d{10,15}$/.test(CFG.SUPPORT_WHATSAPP), CFG.SUPPORT_WHATSAPP);
check('SITE_URL is the live domain', CFG.SITE_URL === 'https://docoga.com.ng', CFG.SITE_URL);
check('WORKER_URL points at the deployed worker', /^https:\/\/[a-z0-9.-]+\.workers\.dev$/i.test(CFG.WORKER_URL || ''), CFG.WORKER_URL);
check('whatsapp support links are wired', $(dom, 'wa-float').href === 'https://wa.me/' + CFG.SUPPORT_WHATSAPP);
check('legacy GA loader removed; dedicated tag is consent/release-gated',
      !HTML.includes('G-GO8VZB3R28') && !/googletagmanager\.com\/gtag\/js/.test(HTML) &&
      ANALYTICS_MANAGER.includes("var GA4_ID = 'G-BQ1YTR0ZZJ'") &&
      ANALYTICS_MANAGER.includes('var ANALYTICS_RELEASE_ENABLED = false;'));

/* ============================ RESULT ===================================== */
console.log('\n' + '═'.repeat(78));
if (fail === 0) console.log(`🏆 DOM SUITE GREEN — ${pass} checks passed, 0 failed.`);
else {
  console.log(`⛔ DOM SUITE FAILED — ${pass} passed, ${fail} FAILED:`);
  failures.forEach((f) => console.log('   • ' + f));
}
console.log('═'.repeat(78));
process.exit(fail === 0 ? 0 : 1);
