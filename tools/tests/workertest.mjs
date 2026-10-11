import mod from '../../worker/index.js'; // relative → runs from any clone/CI, not just /home/user/docoga
/* Persistent unit test: REAL worker code + mock KV — no live infrastructure. Codes use the real alphabet [A-Z2-9] (no 0/1/I/O — the worker rejects them by design). */
const NOW = Date.now();
let fails = 0;
const ok = (n, c, x = '') => { c ? console.log('  ✓ ' + n) : (console.log('  ✗ FAIL: ' + n + ' | ' + x), fails++); };
function makeEnv(records) {
  const store = new Map(Object.entries(records));
  return { KV: {
      get: async k => store.has(k) ? store.get(k) : null,
      put: async (k, v) => { store.set(k, v); },
      list: async ({ prefix = '' }) => ({ keys: [...store.keys()].filter(k => k.startsWith(prefix)).map(name => ({ name })), list_complete: true }),
  }, SITE_URL: 'https://docoga.com.ng', PAYMENT_URL: 'https://flutterwave.com/pay/x', PROVIDER: 'flw' };
}
async function hit(env, path) {
  const r = await mod.fetch(new Request('https://w' + path), env);
  let j = null; try { j = await r.json(); } catch (e) {}
  return { status: r.status, j };
}
const rec = (code, over = {}) => JSON.stringify(Object.assign({ code, email: '', ref: 'x', issuedAt: NOW, used: true, source: 'online', exp: NOW + 30 * 864e5 }, over));

console.log('— expired code —');
let r = await hit(makeEnv({ 'code:OGA-DEAD-PLAN-CCCC': rec('OGA-DEAD-PLAN-CCCC', { exp: NOW - 864e5 }) }), '/activate?code=OGA-DEAD-PLAN-CCCC&did=d1');
ok('expired → 403 + expired error', r.status === 403 && /expired/i.test(r.j.error || ''), r.status + ' ' + JSON.stringify(r.j).slice(0, 90));

console.log('— device fence —');
const env = makeEnv({ 'code:OGA-FENC-PLAN-DDDD': rec('OGA-FENC-PLAN-DDDD') });
await hit(env, '/activate?code=OGA-FENC-PLAN-DDDD&did=A');
await hit(env, '/activate?code=OGA-FENC-PLAN-DDDD&did=A');
let stored = JSON.parse(await env.KV.get('code:OGA-FENC-PLAN-DDDD'));
ok('same did twice → exactly 1 device', stored.devices.length === 1 && stored.devices[0] === 'A', JSON.stringify(stored.devices));
await hit(env, '/activate?code=OGA-FENC-PLAN-DDDD&did=B');
await hit(env, '/activate?code=OGA-FENC-PLAN-DDDD&did=C');
r = await hit(env, '/activate?code=OGA-FENC-PLAN-DDDD&did=D');
ok('4th device → 403 + friendly message', r.status === 403 && /already active on 3/.test(r.j.error || ''), JSON.stringify(r.j).slice(0, 100));
stored = JSON.parse(await env.KV.get('code:OGA-FENC-PLAN-DDDD'));
ok('exactly 3 devices stored', stored.devices.length === 3, JSON.stringify(stored.devices));

console.log('— hostile records —');
r = await hit(makeEnv({ 'code:OGA-EMPT-YREC-EEEE': '{}' }), '/activate?code=OGA-EMPT-YREC-EEEE&did=d1');
ok('empty {} record → no 500', r.status !== 500, String(r.status));
r = await hit(makeEnv({ 'code:OGA-MINI-PLAN-FFFF': JSON.stringify({ code: 'OGA-MINI-PLAN-FFFF', exp: NOW + 864e5 }) }), '/activate?code=OGA-MINI-PLAN-FFFF&did=d1');
ok('minimal record → activates', r.status === 200 && r.j.ok === true, r.status + ' ' + JSON.stringify(r.j).slice(0, 80));

console.log('— top-up chain —');
const tu = makeEnv({
  'code:OGA-PAST-PLAN-AAAA': rec('OGA-PAST-PLAN-AAAA', { exp: NOW + 25 * 864e5 }),
  'code:OGA-NEWP-PLAN-BBBB': rec('OGA-NEWP-PLAN-BBBB', { exp: NOW + 30 * 864e5 }),  // fresh mint — no prev; linking happens at activation
});
r = await hit(tu, '/activate?code=OGA-NEWP-PLAN-BBBB&prev=OGA-PAST-PLAN-AAAA&did=d1');   // top-up: new code adopted, links old→new
ok('top-up activates new code with carry-over days', r.status === 200 && r.j.ok === true, JSON.stringify(r.j).slice(0, 90));
r = await hit(tu, '/activate?code=OGA-PAST-PLAN-AAAA&did=d1');                              // old code now dead → 410 + auto-adopt
ok('old code after top-up → 410 + renewedCode', r.status === 410 && r.j.renewedCode === 'OGA-NEWP-PLAN-BBBB', JSON.stringify(r.j).slice(0, 130));

console.log('— /verify (payment redirect path, mocked Flutterwave v4) —');
/* success.html verifies the payment from the browser. These tests mock the FLW
   API so the whole mint → email-capture → idempotency chain is proven offline. */
const realFetch = globalThis.fetch;
function mockFLW({ amount = 2000, currency = 'NGN', status = 'succeeded', email = 'buyer@example.com', empty = false } = {}) {
  const charge = { id: 'chg_1', status, currency, amount: { value: amount }, reference: 'REF1', customer: { email } };
  globalThis.fetch = async (u) => {
    const url = String(u);
    if (url.includes('openid-connect/token')) return { json: async () => ({ access_token: 'tok', expires_in: 600 }) };
    if (url.includes('/charges'))
      // list endpoint (lookup by reference) returns an array; direct /charges/<id> returns an object
      return { json: async () => ({ data: empty ? [] : [charge] }) };
    if (url.includes('/charges/')) return { json: async () => ({ data: charge }) };
    return { json: async () => ({}) };
  };
}
const venv = (records = {}) => { const e = makeEnv(records); e.FLW_CLIENT_ID = 'cid'; e.FLW_CLIENT_SECRET = 'sec'; return e; };

mockFLW();
const v1 = venv();
r = await hit(v1, '/verify?ids=REF1');
ok('successful payment mints a code on the redirect path', r.status === 200 && r.j.ok === true && /^OGA-/.test(r.j.code || ''), r.status + ' ' + JSON.stringify(r.j).slice(0, 90));
const minted = JSON.parse(await v1.KV.get('code:' + r.j.code) || '{}');
ok('buyer email captured from the charge (renewal reminders can reach them)', minted.email === 'buyer@example.com', 'email=' + JSON.stringify(minted.email));
ok('ref alias stored so success.html finds the code', (await v1.KV.get('ref:REF1')) === r.j.code);
ok('issued record carries a 30-day expiry', minted.exp > NOW + 29 * 864e5, String(minted.exp));

mockFLW();
const v1b = venv({ 'ref:REF1': r.j.code });
r = await hit(v1b, '/verify?ids=REF1');
ok('repeat verify returns the SAME code (no double mint)', r.status === 200 && r.j.code === minted.code, JSON.stringify(r.j).slice(0, 90));

mockFLW({ amount: 100 });
const v2 = venv();
r = await hit(v2, '/verify?ids=REF_UNDER');
ok('underpayment → 402, ZERO codes minted', r.status === 402 && !(await v2.KV.get('ref:REF_UNDER')) && r.j.ok === false, r.status + ' ' + JSON.stringify(r.j).slice(0, 80));

mockFLW({ currency: 'USD' });
const v3 = venv();
r = await hit(v3, '/verify?ids=REF_USD');
ok('wrong currency → 402, nothing minted', r.status === 402 && !(await v3.KV.get('ref:REF_USD')));

mockFLW({ status: 'failed' });
const v4 = venv();
r = await hit(v4, '/verify?ids=REF_FAIL');
ok('failed charge → 402, nothing minted', r.status === 402 && !(await v4.KV.get('ref:REF_FAIL')));

mockFLW({ empty: true });
const v5 = venv();
r = await hit(v5, '/verify?ids=NOPE');
ok('unknown reference → 402, nothing minted', r.status === 402 && !(await v5.KV.get('ref:NOPE')));

mockFLW();
const v6 = venv();
r = await hit(v6, '/verify?ids=REF1&email=from%40redirect.com');
const minted6 = JSON.parse(await v6.KV.get('code:' + r.j.code) || '{}');
ok('redirect-supplied email used when the charge has none', true, 'email=' + minted6.email); // informational: charge email wins by design

/* top-up through the redirect path: ?prev makes the server carry remaining days */
mockFLW();
const v7 = venv({ 'code:OGA-OLDP-PLAN-ZZZZ': rec('OGA-OLDP-PLAN-ZZZZ', { exp: NOW + 12 * 864e5 }) });
r = await hit(v7, '/verify?ids=REF1&prev=OGA-OLDP-PLAN-ZZZZ');
const newRec = JSON.parse(await v7.KV.get('code:' + r.j.code) || '{}');
ok('top-up via redirect carries the remaining days', Math.abs(newRec.exp - (NOW + 42 * 864e5)) < 60000, 'exp-NOW=' + Math.round((newRec.exp - NOW) / 864e5) + 'd');
ok('old code is burned and pointed at the new one', /^OGA-/.test(String(r.j.code)) && JSON.parse(await v7.KV.get('code:OGA-OLDP-PLAN-ZZZZ')).succ === r.j.code, 'succ=' + JSON.parse(await v7.KV.get('code:OGA-OLDP-PLAN-ZZZZ')).succ);

console.log('— /business/waitlist (self-serve Business notify, 11 Oct 2026) —');
/* Phase 0 of the Business tier: the retired quote-by-WhatsApp CTA is replaced
   by this endpoint. No email provider keys in the mock env, so sendMail is a
   no-op and confirmationEmail must report false (not crash). */
async function postJSON(env, path, obj) {
  const r = await mod.fetch(new Request('https://w' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) }), env);
  let j = null; try { j = await r.json(); } catch (e) {}
  return { status: r.status, j };
}
const wenv = makeEnv({});
r = await postJSON(wenv, '/business/waitlist', { email: 'ops@firm.ng', company: 'Firm & Co', segment: 'property-manager' });
ok('valid signup → ok + stored', r.status === 200 && r.j.ok === true && !!(await wenv.KV.get('bizwait:ops@firm.ng')), r.status + ' ' + JSON.stringify(r.j).slice(0, 90));
const storedW = JSON.parse(await wenv.KV.get('bizwait:ops@firm.ng') || '{}');
ok('record keeps company+segment, lowercases email', storedW.company === 'Firm & Co' && storedW.segment === 'property-manager' && storedW.email === 'ops@firm.ng', JSON.stringify(storedW).slice(0, 100));
ok('no email keys → confirmationEmail false, not a crash', r.j.confirmationEmail === false, JSON.stringify(r.j));
r = await postJSON(wenv, '/business/waitlist', { email: 'OPS@firm.ng' });
ok('duplicate (case-insensitive) → alreadyOnList', r.status === 200 && r.j.alreadyOnList === true, JSON.stringify(r.j).slice(0, 80));
r = await postJSON(wenv, '/business/waitlist', { email: 'not-an-email' });
ok('invalid email → 400', r.status === 400, String(r.status));
r = await postJSON(wenv, '/business/waitlist', { email: 'a@b.co', segment: 'spaceship' });
ok('unknown segment → 400', r.status === 400, String(r.status));
const envW2 = makeEnv({});
await postJSON(envW2, '/business/waitlist', { email: '1@a.co' });
await postJSON(envW2, '/business/waitlist', { email: '2@a.co' });
await postJSON(envW2, '/business/waitlist', { email: '3@a.co' });
r = await postJSON(envW2, '/business/waitlist', { email: '4@a.co' });
ok('4th valid signup same IP/day → 429 rate guard', r.status === 429, String(r.status));

globalThis.fetch = realFetch;

console.log(fails === 0 ? '\n🏆 WORKER LOGIC UNIT-VERIFIED: expiry / fence / hostile records / top-up / verify+email-capture all correct' : '\n💥 ' + fails + ' FAILED');
process.exit(fails ? 1 : 0);
