// site/tiktok-connect.html — the Login Kit landing page, in a real DOM.
// TikTok sends the owner back with ?code=…; the page must hand it to the worker with the
// dashboard session this origin already holds, wipe it from the address bar, and fall back
// to a copyable code when it cannot. Runs under jsdom; skips cleanly when jsdom is absent.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const PAGE = path.join(ROOT, 'site', 'tiktok-connect.html');
const html = fs.readFileSync(PAGE, 'utf8');

let pass = 0, fail = 0;
function check(name, cond, detail = '') {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ FAIL: ' + name + (detail ? ' | ' + detail : '')); }
}

/* ---- static facts, no DOM needed ---- */
const adminHtml = fs.readFileSync(path.join(ROOT, 'site', 'admin.html'), 'utf8');
const workerUrl = (s) => (/WORKER_URL\s*=\s*"([^"]+)"/.exec(s) || [])[1];
check('WORKER_URL equals admin.html’s', workerUrl(html) && workerUrl(html) === workerUrl(adminHtml), workerUrl(html));
check('the page is noindexed and sends no referrer (the code would ride along otherwise)', /name="robots" content="noindex/.test(html) && /name="referrer" content="no-referrer"/.test(html));
check('no analytics script on an owner page', !/analytics-consent\.js|googletagmanager/.test(html));
check('the consent asks for the whole scope superset in one go (owner’s rule: never re-mint)',
  /user\.info\.basic,user\.info\.profile,user\.info\.stats,video\.list,video\.upload,video\.publish/.test(html));
check('the redirect URI in the page is the page itself', /REDIRECT = "https:\/\/docoga\.com\.ng\/tiktok-connect\.html"/.test(html));
check('_headers hardens /tiktok-connect.html like /admin', /\/tiktok-connect\.html\n\s+X-Robots-Tag: noindex/.test(fs.readFileSync(path.join(ROOT, 'site', '_headers'), 'utf8')));
check('the connect workflow uses the same redirect URI', /REDIRECT_URI: https:\/\/docoga\.com\.ng\/tiktok-connect\.html/.test(fs.readFileSync(path.join(ROOT, '.github', 'workflows', 'tiktok_connect.yml'), 'utf8')));

/* ---- jsdom ---- */
let JSDOM = null;
for (const dir of [process.env.JSDOM_PATH, path.join(ROOT, 'node_modules', 'jsdom'), '/home/user/node_modules/jsdom'].filter(Boolean)) {
  try { const api = await import('file://' + path.join(dir, 'lib', 'api.js')); JSDOM = api.JSDOM; break; } catch (e) { /* next */ }
}
if (!JSDOM) { try { JSDOM = (await import('jsdom')).JSDOM; } catch (e) {} }
if (!JSDOM) {
  console.log('⚠️  jsdom not installed — static checks only (npm i jsdom, or set JSDOM_PATH).');
  console.log(fail ? `❌ TIKTOK CONNECT PAGE — ${fail} failed` : `🏆 TIKTOK CONNECT PAGE — ${pass} static checks passed`);
  process.exit(fail ? 1 : 0);
}

const tick = (ms = 5) => new Promise(r => setTimeout(r, ms));
async function until(fn, tries = 60) { for (let i = 0; i < tries; i++) { if (fn()) return true; await tick(); } return fn(); }
const CODE = 'q7Zr0Xk*1!Abcdefghijklmnopqrstuvwxyz0123456789-_';

function open(url, { token, reply }) {
  const dom = new JSDOM(html, { url, runScripts: 'outside-only', pretendToBeVisual: true });
  const win = dom.window;
  if (token) win.localStorage.setItem('docoga.admin.token', token);
  const calls = [];
  win.fetch = async (input, init = {}) => {
    calls.push({ url: String(input), init });
    const r = reply(String(input), init);
    return { status: r.status, ok: r.status < 400, json: async () => r.body, text: async () => JSON.stringify(r.body) };
  };
  const script = /<script>([\s\S]*?)<\/script>/.exec(html)[1];
  win.eval(script);
  return { dom, win, doc: win.document, calls };
}

console.log('— back from TikTok, signed in: the code goes to the worker —');
{
  const { win, doc, calls } = open('https://docoga.com.ng/tiktok-connect.html?code=' + encodeURIComponent(CODE) + '&state=docogaabc', {
    token: 'sid.tok', reply: () => ({ status: 200, body: { ok: true, workflow: 'tiktok_connect.yml' } }) });
  await until(() => /Sent/.test(doc.getElementById('code-msg').textContent));
  check('exactly one POST to /admin/tiktok/connect, bearer = the dashboard session, body = the decoded code',
    calls.length === 1 && calls[0].url === 'https://docoga-pass.johnazani.workers.dev/admin/tiktok/connect' && calls[0].init.method === 'POST'
      && calls[0].init.headers.authorization === 'Bearer sid.tok' && JSON.parse(calls[0].init.body).code === CODE, JSON.stringify(calls[0] || {}).slice(0, 200));
  check('the page says Sent ✓ and points to the Social tab', /Sent ✓/.test(doc.getElementById('code-msg').textContent) && /Social/.test(doc.getElementById('code-actions').textContent));
  check('the code is wiped from the address bar', !win.location.search, win.location.href);
  check('the manual route stays hidden on success', doc.getElementById('manual').classList.contains('hide'));
  check('the code never appears in page text outside the hidden manual box', !doc.getElementById('code-msg').textContent.includes('q7Zr0Xk') && !doc.getElementById('code-actions').textContent.includes('q7Zr0Xk'));
}

console.log('— back from TikTok, not signed in: the copyable fallback —');
{
  const { doc, calls } = open('https://docoga.com.ng/tiktok-connect.html?code=' + encodeURIComponent(CODE), { token: null, reply: () => ({ status: 500, body: {} }) });
  await until(() => /not signed in/.test(doc.getElementById('code-msg').textContent));
  check('no request is made without a session', calls.length === 0, calls.length + '');
  check('the manual box opens with the code and the Actions link', doc.getElementById('manual').open && doc.getElementById('code-box').textContent === CODE
    && /github\.com\/johnAzani\/docoga\/actions\/workflows\/tiktok_connect\.yml/.test(doc.getElementById('actions-link').href));
  check('there is a button to open the dashboard and a button to send again', /Open the dashboard/.test(doc.getElementById('code-actions').textContent) && !!doc.getElementById('again'));
}

console.log('— back from TikTok, session expired: 401 becomes the fallback, not a dead page —');
{
  const { doc } = open('https://docoga.com.ng/tiktok-connect.html?code=' + encodeURIComponent(CODE), { token: 'old', reply: () => ({ status: 401, body: { ok: false, error: 'sign_in_required' } }) });
  await until(() => /expired/.test(doc.getElementById('code-msg').textContent));
  check('401 is explained and the manual route opens', /expired/.test(doc.getElementById('code-msg').textContent) && doc.getElementById('manual').open);
}

console.log('— TikTok said no —');
{
  const { doc, win } = open('https://docoga.com.ng/tiktok-connect.html?error=access_denied&error_description=User%20cancelled', { token: null, reply: () => ({ status: 500, body: {} }) });
  check('the error and its description are shown with a Try again link', /access_denied — User cancelled/.test(doc.getElementById('err-msg').textContent) && !doc.getElementById('s-error').classList.contains('hide'));
  check('the error is wiped from the address bar too', !win.location.search, win.location.href);
}

console.log('— the start screen —');
{
  const { doc, win } = open('https://docoga.com.ng/tiktok-connect.html', { token: null, reply: () => ({ status: 500, body: {} }) });
  check('the start screen asks for the public client key only', !doc.getElementById('s-start').classList.contains('hide') && /Client key/.test(doc.getElementById('s-start').textContent) && !/secret\b[^n]/i.test(doc.getElementById('ck').placeholder));
  doc.getElementById('ck').value = 'not a key!!';
  doc.getElementById('go').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
  check('a malformed client key is refused before leaving the page', /does not look like a client key/.test(doc.getElementById('start-msg').textContent));
}

console.log('');
console.log(fail ? `❌ TIKTOK CONNECT PAGE — ${pass} passed, ${fail} FAILED` : `🏆 TIKTOK CONNECT PAGE GREEN — ${pass} checks passed`);
process.exit(fail ? 1 : 0);
