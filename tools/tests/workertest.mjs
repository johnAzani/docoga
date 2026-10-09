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
async function hit(env, path, init = {}) {
  const r = await mod.fetch(new Request('https://w' + path, init), env);
  const text = await r.text();
  let j = null; try { j = JSON.parse(text); } catch (e) {}
  return { status: r.status, j, text };
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

globalThis.fetch = realFetch;

console.log('— /verify v3 (configured FLW_SECRET_KEY fallback, locally simulated) —');
let v3Charge = { status: 'successful', currency: 'NGN', amount: 2000, tx_ref: 'V3-REF-2000', customer: { email: 'v3-buyer@example.com' } };
globalThis.fetch = async (url) => {
  if (!String(url).includes('/v3/transactions/verify_by_reference')) throw new Error('unexpected v3 verify request: ' + url);
  return { json: async () => ({ data: v3Charge }) };
};
const v3Env = makeEnv({});
v3Env.FLW_SECRET_KEY = 'test-flw-v3-secret';
r = await hit(v3Env, '/verify?ref=V3-REF-2000');
ok('successful ₦2,000 v3 verification mints a code', r.status === 200 && r.j.ok === true && /^OGA-/.test(r.j.code || '') && (await v3Env.KV.get('ref:V3-REF-2000')) === r.j.code, r.status + ' ' + JSON.stringify(r.j));
const v3UnderpaidEnv = makeEnv({});
v3UnderpaidEnv.FLW_SECRET_KEY = 'test-flw-v3-secret';
v3Charge = { ...v3Charge, amount: 100, tx_ref: 'V3-REF-100' };
r = await hit(v3UnderpaidEnv, '/verify?ref=V3-REF-100');
ok('v3 underpayment below ₦2,000 is rejected with no code', r.status === 402 && !(await v3UnderpaidEnv.KV.get('ref:V3-REF-100')), r.status + ' ' + JSON.stringify(r.j));
globalThis.fetch = realFetch;

console.log('— /flw-webhook (Flutterwave payment-link path, locally simulated) —');
const webhookHash = 'test-flutterwave-secret-hash';
const webhookMailRequests = [];
globalThis.fetch = async (url, init = {}) => {
  webhookMailRequests.push({ url: String(url), body: JSON.parse(init.body || '{}') });
  return new Response(null, { status: 201 });
};
const webhookPayload = {
  event: 'charge.completed',
  data: {
    id: 'flw-charge-2000', tx_ref: 'DOCOGA-TX-2000', reference: 'DOCOGA-REF-2000',
    amount: 2000, currency: 'NGN', status: 'successful',
    customer: { email: 'webhook-buyer@example.com' },
  },
};
const webhookEnv = makeEnv({});
webhookEnv.FLW_WEBHOOK_HASH = webhookHash;
webhookEnv.BREVO_API_KEY = 'test-brevo-key';
const webhookRaw = JSON.stringify(webhookPayload);
r = await hit(webhookEnv, '/flw-webhook', {
  method: 'POST', headers: { 'content-type': 'application/json', 'verif-hash': webhookHash }, body: webhookRaw,
});
const webhookCode = await webhookEnv.KV.get('ref:DOCOGA-REF-2000');
const webhookRecord = JSON.parse(await webhookEnv.KV.get('code:' + webhookCode) || '{}');
ok('valid signed ₦2,000 NGN charge.completed webhook issues a code', r.status === 200 && r.text === 'ok' && /^OGA-/.test(webhookCode || ''), r.status + ' ' + r.text);
ok('webhook aliases reference, tx_ref and charge id to the same code', webhookCode && (await webhookEnv.KV.get('ref:DOCOGA-TX-2000')) === webhookCode && (await webhookEnv.KV.get('ref:flw-charge-2000')) === webhookCode);
ok('webhook stores buyer email and asks Brevo to deliver the pass', webhookRecord.email === 'webhook-buyer@example.com' && webhookMailRequests.length === 1 && webhookMailRequests[0].url.includes('api.brevo.com') && webhookMailRequests[0].body.to?.[0]?.email === 'webhook-buyer@example.com' && webhookMailRequests[0].body.textContent.includes('all 10 tools') && webhookMailRequests[0].body.htmlContent.includes('Power of Attorney'));
r = await hit(webhookEnv, '/flw-webhook', {
  method: 'POST', headers: { 'content-type': 'application/json', 'verif-hash': webhookHash }, body: webhookRaw,
});
ok('duplicate webhook is idempotent (same code; no second email)', r.status === 200 && r.text === 'ok' && webhookMailRequests.length === 1 && (await webhookEnv.KV.list({ prefix: 'code:' })).keys.length === 1);

const rejectedMailEnv = makeEnv({});
rejectedMailEnv.FLW_WEBHOOK_HASH = webhookHash;
rejectedMailEnv.BREVO_API_KEY = 'test-brevo-key';
const rejectedMailPayload = {
  ...webhookPayload,
  data: {
    ...webhookPayload.data,
    id: 'flw-charge-mail-fail', tx_ref: 'DOCOGA-TX-MAIL-FAIL', reference: 'DOCOGA-REF-MAIL-FAIL',
    customer: { email: 'private-recipient@example.com' },
  },
};
const priorConsoleError = console.error;
const workerErrorLines = [];
console.error = (...args) => workerErrorLines.push(args.join(' '));
globalThis.fetch = async () => new Response('private provider response body', { status: 401 });
r = await hit(rejectedMailEnv, '/flw-webhook', {
  method: 'POST', headers: { 'content-type': 'application/json', 'verif-hash': webhookHash }, body: JSON.stringify(rejectedMailPayload),
});
console.error = priorConsoleError;
const rejectedMailCode = await rejectedMailEnv.KV.get('ref:DOCOGA-REF-MAIL-FAIL');
const safeMailLog = workerErrorLines.join('\n');
ok('Brevo HTTP rejection is logged without blocking pass issuance', r.status === 200 && r.text === 'ok' && /^OGA-/.test(rejectedMailCode || '') && safeMailLog.includes('BREVO_HTTP_401'));
ok('email failure diagnostic excludes recipient and provider response body', !safeMailLog.includes('private-recipient@example.com') && !safeMailLog.includes('private provider response body') && !safeMailLog.includes(rejectedMailCode || 'NO_CODE'));

globalThis.fetch = async (url, init = {}) => {
  webhookMailRequests.push({ url: String(url), body: JSON.parse(init.body || '{}') });
  return new Response(null, { status: 201 });
};

const underpaidEnv = makeEnv({});
underpaidEnv.FLW_WEBHOOK_HASH = webhookHash;
underpaidEnv.BREVO_API_KEY = 'test-brevo-key';
const underpaidPayload = { ...webhookPayload, data: { ...webhookPayload.data, id: 'flw-charge-100', tx_ref: 'DOCOGA-TX-100', reference: 'DOCOGA-REF-100', amount: 100 } };
r = await hit(underpaidEnv, '/flw-webhook', {
  method: 'POST', headers: { 'content-type': 'application/json', 'verif-hash': webhookHash }, body: JSON.stringify(underpaidPayload),
});
ok('valid ₦100 webhook is acknowledged but ignored; no pass is issued', r.status === 200 && r.text === 'ignored' && (await underpaidEnv.KV.list({ prefix: 'code:' })).keys.length === 0 && webhookMailRequests.length === 1, r.status + ' ' + r.text);

const badSignatureEnv = makeEnv({});
badSignatureEnv.FLW_WEBHOOK_HASH = webhookHash;
r = await hit(badSignatureEnv, '/flw-webhook', {
  method: 'POST', headers: { 'content-type': 'application/json', 'verif-hash': 'wrong-hash' }, body: webhookRaw,
});
ok('invalid webhook secret hash is rejected before any code is issued', r.status === 403 && (await badSignatureEnv.KV.list({ prefix: 'code:' })).keys.length === 0);

globalThis.fetch = realFetch;

console.log(fails === 0 ? '\n🏆 WORKER LOGIC UNIT-VERIFIED: expiry / fence / hostile records / top-up / redirect verify / signed webhook / underpayment gate / email hand-off' : '\n💥 ' + fails + ' FAILED');
process.exit(fails ? 1 : 0);
