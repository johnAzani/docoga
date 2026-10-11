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
      delete: async k => { store.delete(k); },
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

console.log('— disabled manual bridge and side-effect-free deployment probe —');
const bridgeDisabledEnv = makeEnv({});
let unexpectedCalls = 0;
const beforeBridgeFetch = globalThis.fetch;
globalThis.fetch = async () => { unexpectedCalls++; throw new Error('unexpected provider request'); };
for (const headers of [{}, { 'x-docoga-key': 'fake-bridge-key' }]) {
  const blocked = await hit(bridgeDisabledEnv, '/issue', {
    method: 'POST', headers: { 'content-type': 'application/json', ...headers },
    body: JSON.stringify({ email: 'bridge-buyer@example.com', ref: 'TEST-BRIDGE-REF' }),
  });
  ok('missing ISSUE_SECRET keeps /issue closed even with a supplied key', blocked.status === 401 && blocked.j.error === 'unauthorized');
}
const missingCodeProbe = await hit(bridgeDisabledEnv, '/activate');
ok('deployment probe without code returns 400 and cannot issue or email',
   missingCodeProbe.status === 400 && missingCodeProbe.j.error === 'code required' &&
   (await bridgeDisabledEnv.KV.list({ prefix: 'code:' })).keys.length === 0 && unexpectedCalls === 0);
globalThis.fetch = beforeBridgeFetch;

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
ok('Flutterwave works without ISSUE_SECRET', !webhookEnv.ISSUE_SECRET && r.status === 200 && !!webhookCode);
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

console.log('— /resend-email (no-charge recovery path) —');
const resendCode = 'OGA-RESN-TEST-8236';
const resendRequests = [];
const disabledResendEnv = makeEnv({
  'ref:FLW-REF-RESEND-A': resendCode,
  ['code:' + resendCode]: rec(resendCode, { email: 'resend-buyer@example.com', exp: NOW + 30 * 864e5 }),
});
disabledResendEnv.BREVO_API_KEY = 'test-brevo-key';
r = await hit(disabledResendEnv, '/resend-email', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ids: ['FLW-REF-RESEND-A'] }),
});
ok('resend is fail-closed until explicitly enabled after sender authentication', r.status === 503 && r.j.error === 'resend_disabled' && resendRequests.length === 0);
const resendEnv = makeEnv({
  'ref:FLW-REF-RESEND-A': resendCode,
  'ref:FLW-REF-RESEND-B': resendCode, // aliases for the same purchase must share a throttle
  ['code:' + resendCode]: rec(resendCode, { email: 'resend-buyer@example.com', exp: NOW + 30 * 864e5 }),
});
resendEnv.BREVO_API_KEY = 'test-brevo-key';
resendEnv.RESEND_EMAIL_ENABLED = 'true';
globalThis.fetch = async (url, init = {}) => {
  resendRequests.push({ url: String(url), body: JSON.parse(init.body || '{}') });
  return new Response(null, { status: 201 });
};
r = await hit(resendEnv, '/resend-email', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ids: ['FLW-REF-RESEND-A'] }),
});
ok('resend sends the stored pass to its stored email without returning the code', r.status === 200 && r.j.ok === true && !JSON.stringify(r.j).includes(resendCode) && resendRequests.length === 1 && resendRequests[0].body.to?.[0]?.email === 'resend-buyer@example.com' && resendRequests[0].body.textContent.includes(resendCode));
r = await hit(resendEnv, '/resend-email', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ids: ['FLW-REF-RESEND-B'] }),
});
ok('resend throttle covers reference aliases for the same pass', r.status === 429 && r.j.error === 'resend_wait' && resendRequests.length === 1);

const topupOldCode = 'OGA-OLDP-PLAN-8234';
const topupNewCode = 'OGA-NEWP-PLAN-8235';
const topupResendEnv = makeEnv({
  'ref:FLW-REF-RESEND-TOPUP': topupOldCode,
  ['code:' + topupOldCode]: rec(topupOldCode, { email: 'old-buyer@example.com', succ: topupNewCode, exp: NOW + 10 * 864e5 }),
  ['code:' + topupNewCode]: rec(topupNewCode, { email: 'current-buyer@example.com', exp: NOW + 40 * 864e5 }),
});
topupResendEnv.BREVO_API_KEY = 'test-brevo-key';
topupResendEnv.RESEND_EMAIL_ENABLED = 'true';
r = await hit(topupResendEnv, '/resend-email', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ref: 'FLW-REF-RESEND-TOPUP' }),
});
ok('top-up reference resends only the newest active code to its stored email', r.status === 200 && !JSON.stringify(r.j).includes(topupNewCode) && resendRequests.length === 2 && resendRequests[1].body.to?.[0]?.email === 'current-buyer@example.com' && resendRequests[1].body.textContent.includes(topupNewCode) && !resendRequests[1].body.textContent.includes(topupOldCode));
const expiredResendCode = 'OGA-EXPR-PLAN-8234';
const expiredResendEnv = makeEnv({
  'ref:FLW-REF-RESEND-EXPIRED': expiredResendCode,
  ['code:' + expiredResendCode]: rec(expiredResendCode, { email: 'expired-buyer@example.com', exp: NOW - 864e5 }),
});
expiredResendEnv.BREVO_API_KEY = 'test-brevo-key';
expiredResendEnv.RESEND_EMAIL_ENABLED = 'true';
r = await hit(expiredResendEnv, '/resend-email', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ref: 'FLW-REF-RESEND-EXPIRED' }),
});
ok('expired passes cannot be resent', r.status === 410 && r.j.error === 'pass_expired' && resendRequests.length === 2);

const failedResendCode = 'OGA-FALX-RESE-8237';
const failedResendEnv = makeEnv({
  'ref:FLW-REF-RESEND-FAIL': failedResendCode,
  ['code:' + failedResendCode]: rec(failedResendCode, { email: 'private-resend@example.com', exp: NOW + 30 * 864e5 }),
});
failedResendEnv.BREVO_API_KEY = 'test-brevo-key';
failedResendEnv.RESEND_EMAIL_ENABLED = 'true';
let resendFailureLogs = [];
const originalConsoleError = console.error;
console.error = (...args) => resendFailureLogs.push(args.join(' '));
globalThis.fetch = async () => new Response('private provider response body', { status: 401 });
r = await hit(failedResendEnv, '/resend-email', {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ref: 'FLW-REF-RESEND-FAIL' }),
});
console.error = originalConsoleError;
const resendFailureLog = resendFailureLogs.join(' ');
ok('provider rejection fails the resend without exposing the code', r.status === 502 && r.j.error === 'email_send_failed' && !JSON.stringify(r.j).includes(failedResendCode));
ok('resend failure diagnostic excludes recipient and provider body', resendFailureLog.includes('BREVO_HTTP_401') && !resendFailureLog.includes('private-resend@example.com') && !resendFailureLog.includes('private provider response body') && !resendFailureLog.includes(failedResendCode));

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

console.log('— /business/waitlist (self-serve Business notify, Phase 0, 11 Oct 2026) —');
/* The retired quote-by-WhatsApp CTA is replaced by this endpoint. No email
   provider keys in the mock env, so sendMail throws MAIL_NO_PROVIDER: the
   signup must still be stored and confirmationEmail must report false. */
const wenv = makeEnv({});
r = await hit(wenv, '/business/waitlist', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'ops@firm.ng', company: 'Firm & Co', segment: 'property-manager' }) });
ok('valid signup → ok + stored', r.status === 200 && r.j.ok === true && !!(await wenv.KV.get('bizwait:ops@firm.ng')), r.status + ' ' + JSON.stringify(r.j).slice(0, 90));
const storedW = JSON.parse(await wenv.KV.get('bizwait:ops@firm.ng') || '{}');
ok('record keeps company+segment, lowercases email', storedW.company === 'Firm & Co' && storedW.segment === 'property-manager' && storedW.email === 'ops@firm.ng', JSON.stringify(storedW).slice(0, 100));
ok('no email keys → stored anyway, confirmationEmail false, not a crash', r.j.confirmationEmail === false, JSON.stringify(r.j));
r = await hit(wenv, '/business/waitlist', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'OPS@firm.ng' }) });
ok('duplicate (case-insensitive) → alreadyOnList', r.status === 200 && r.j.alreadyOnList === true, JSON.stringify(r.j).slice(0, 80));
r = await hit(wenv, '/business/waitlist', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'not-an-email' }) });
ok('invalid email → 400, nothing stored', r.status === 400 && (await wenv.KV.list({ prefix: 'bizwait:not' })).keys.length === 0, String(r.status));
r = await hit(wenv, '/business/waitlist', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'a@b.co', segment: 'spaceship' }) });
ok('unknown segment → 400', r.status === 400, String(r.status));
const envW2 = makeEnv({});
await hit(envW2, '/business/waitlist', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: '1@a.co' }) });
await hit(envW2, '/business/waitlist', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: '2@a.co' }) });
await hit(envW2, '/business/waitlist', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: '3@a.co' }) });
r = await hit(envW2, '/business/waitlist', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: '4@a.co' }) });
ok('4th valid signup same IP/day → 429 rate guard', r.status === 429, String(r.status));

console.log('— /business/* team core (Phase 1, 11 Oct 2026) —');
/* Phase 1 teams are owner-created-by-hand in KV (docs/BUSINESS_TEAM_SETUP.md);
   the tests write the same records directly. Magic-link emails are captured by
   mocking globalThis.fetch on the RESEND provider path. */
const T1 = (email, name, role, status = 'active') => ({ email, name, role, status, invited_at: new Date().toISOString() });
function teamEnv() {
  const env = makeEnv({
    'team:t1': JSON.stringify({ id: 't1', slug: 'firm', name: 'Firm & Co', status: 'active', expiry: '2027-01-01', plan: 'starter' }),
    'team:t1:seats': JSON.stringify([T1('owner@firm.ng', 'Owner', 'owner'), T1('staff@firm.ng', 'Staff', 'member')]),
    'brand:t1': JSON.stringify({ name: 'Firm & Co' }),
    'seatidx:owner@firm.ng': 't1', 'seatidx:staff@firm.ng': 't1',
  });
  env.TEAM_AUTH_SECRET = 'test-team-secret';
  env.RESEND_API_KEY = 're_test';
  return env;
}
const mailCap = [];
globalThis.fetch = async (url, opts) => {
  mailCap.push({ url: String(url), body: opts && opts.body ? JSON.parse(opts.body) : null });
  return new Response(JSON.stringify({ id: 'mail-x' }), { status: 200, headers: { 'content-type': 'application/json' } });
};
const authed = (tok) => ({ headers: { authorization: 'Bearer ' + tok } });
const postBody = (tok, obj) => ({ method: 'POST', headers: Object.assign(authed(tok).headers, { 'content-type': 'application/json' }), body: JSON.stringify(obj) });
const putBody = (tok, obj) => ({ method: 'PUT', headers: Object.assign(authed(tok).headers, { 'content-type': 'application/json' }), body: JSON.stringify(obj) });

r = await hit(makeEnv({}), '/business/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'owner@firm.ng' }) });
ok('no TEAM_AUTH_SECRET → 503 team_auth_disabled (fail-closed)', r.status === 503 && r.j.error === 'team_auth_disabled', String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 60));

const te = teamEnv();
r = await hit(te, '/business/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'ghost@nowhere.co' }) });
ok('login with unknown email → 400, no token stored', r.status === 400 && (await te.KV.list({ prefix: 'auth:' })).keys.length === 0, String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 80));

r = await hit(te, '/business/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'owner@firm.ng' }) });
ok('login with known owner email → 200 + magic link emailed', r.status === 200 && r.j.ok === true, String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 80));
const linkMail = mailCap[mailCap.length - 1];
ok('magic link email goes to the seat, carries ?team_token= link', !!(linkMail && linkMail.body && linkMail.body.to === 'owner@firm.ng') && /team_token=owner(%40|@)firm\.ng~[0-9a-f]{64}/.test((linkMail && linkMail.body && (linkMail.body.text || '')) || ''), JSON.stringify((linkMail && linkMail.body) || {}).slice(0, 100));
const magicTok = decodeURIComponent(((linkMail && linkMail.body && (linkMail.body.text || '')) || '').match(/team_token=([\w.~@%]+)/)[1]);
const storedAuth = await te.KV.get('auth:owner@firm.ng');
ok('magic token stored only as SHA-256 hash with 10-min expiry', !!storedAuth && !String(storedAuth).includes(magicTok), String(storedAuth).slice(0, 90));

r = await hit(te, '/business/login?token=' + encodeURIComponent(magicTok));
ok('magic link verified → 30-day HMAC session, one-time (record deleted)', r.status === 200 && r.j.ok === true && r.j.role === 'owner' && String(r.j.token).startsWith('tl_t1|owner@firm.ng|') && !(await te.KV.get('auth:owner@firm.ng')), String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 90));
const ownerTok = r.j.token;
r = await hit(te, '/business/login?token=' + encodeURIComponent(magicTok));
ok('reused magic link → 400 (one-time)', r.status === 400, String(r.status));

r = await hit(te, '/business/team', authed(ownerTok));
ok('GET /business/team (owner session) → team + all seats + brand', r.status === 200 && r.j.team.name === 'Firm & Co' && r.j.seats.length === 2 && r.j.brand.name === 'Firm & Co', String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 140));
r = await hit(te, '/business/team', {});
ok('GET /business/team without token → 401', r.status === 401, String(r.status));
r = await hit(te, '/business/team', authed(ownerTok.replace('owner@firm.ng', 'hacker@evil.co')));
ok('tampered session payload → 401', r.status === 401, String(r.status));

const tinyPng = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
r = await hit(te, '/business/team/brand', putBody(ownerTok, { name: 'Firm & Co Ltd', logo: tinyPng }));
ok('owner PUT brand (name+logo) → stored', r.status === 200 && r.j.brand.name === 'Firm & Co Ltd' && r.j.brand.logo === tinyPng, String(r.status) + ' ' + JSON.stringify(r.j.brand || {}).slice(0, 80));
r = await hit(te, '/business/team/brand', putBody(ownerTok, { logo: 'data:image/png;base64,' + 'A'.repeat(Math.ceil(26 * 1024 * 4 / 3)) }));
ok('26KB logo → 400 (25KB cap, server re-validates)', r.status === 400, String(r.status));
r = await hit(te, '/business/team/brand', putBody(ownerTok, { logo: 'http://evil/logo.png' }));
ok('non-data-URI logo → 400', r.status === 400, String(r.status));

r = await hit(te, '/business/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'staff@firm.ng' }) });
const staffMagic = decodeURIComponent((((mailCap[mailCap.length - 1] || {}).body || {}).text || '').match(/team_token=([\w.~@%]+)/)[1]);
r = await hit(te, '/business/login?token=' + encodeURIComponent(staffMagic));
const staffTok = r.j.token;
r = await hit(te, '/business/team', authed(staffTok));
ok('member GET /business/team sees only own seat', r.status === 200 && r.j.seats.length === 1 && r.j.seats[0].email === 'staff@firm.ng', String(r.status) + ' ' + JSON.stringify(r.j.seats || []).slice(0, 80));
r = await hit(te, '/business/team/brand', putBody(staffTok, { name: 'Hacked' }));
ok('member PUT brand → 403 owner_only', r.status === 403, String(r.status));

r = await hit(te, '/business/team/seats', postBody(ownerTok, { action: 'invite', email: 'new@firm.ng', name: 'New' }));
ok('owner invite → seat active + index set + magic link emailed', r.status === 200 && r.j.emailSent === true && (await te.KV.get('seatidx:new@firm.ng')) === 't1' && /team_token=new(%40|@)firm\.ng~/.test((((mailCap[mailCap.length - 1] || {}).body || {}).text || '')), String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 80));
r = await hit(te, '/business/team/seats', postBody(ownerTok, { action: 'invite', email: 'staff@firm.ng' }));
ok('invite an existing active member → 400', r.status === 400, String(r.status));

r = await hit(te, '/business/team/seats', postBody(ownerTok, { action: 'revoke', email: 'staff@firm.ng' }));
ok('owner revoke → seat revoked + index deleted', r.status === 200 && r.j.action === 'revoke' && !(await te.KV.get('seatidx:staff@firm.ng')), String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 80));
r = await hit(te, '/business/team', authed(staffTok));
ok('revoked seat session dies immediately (Phase 1 gate)', r.status === 401, String(r.status));

await te.KV.put('team:t2', JSON.stringify({ id: 't2', slug: 'old', name: 'Old Firm', status: 'active', expiry: '2020-01-01', plan: 'starter' }));
await te.KV.put('team:t2:seats', JSON.stringify([T1('late@old.co', 'Late', 'owner')]));
await te.KV.put('seatidx:late@old.co', 't2');
const mailsBefore = mailCap.length;
r = await hit(te, '/business/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'late@old.co' }) });
ok('expired team → login blocked 400, no email sent', r.status === 400 && r.j.error === 'team not active' && mailCap.length === mailsBefore, String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 60));

console.log('— /business/* money path (Phase 2, 11 Oct 2026) —');
/* Flutterwave + mail routed through one fetch mock: the VA/charge responses
   are canned v4 shapes; the VENDOR'S expiry (1h) differs from the one we
   requested (7d) on purpose — the worker must honour the vendor's. */
const flwCalls = [];
globalThis.fetch = async (url, opts) => {
  url = String(url);
  const o = opts || {};
  if (url.includes('api.resend.com')) { mailCap.push({ url, body: o.body ? JSON.parse(o.body) : null }); return new Response(JSON.stringify({ id: 'm' }), { status: 200, headers: { 'content-type': 'application/json' } }); }
  if (url.includes('idp.flutterwave.com')) return new Response(JSON.stringify({ access_token: 'test-v4-token', expires_in: 600 }), { status: 200, headers: { 'content-type': 'application/json' } });
  if (url.includes('/v1/payment_methods')) {
    const d = JSON.parse(o.body);
    flwCalls.push(d);
    return new Response(JSON.stringify({ status: 'success', data: { account_number: '1234567890', account_bank_name: 'WEMA BANK', amount: d.amount, reference: 'van_' + flwCalls.length, account_expiration_datetime: new Date(Date.now() + 3600e3).toISOString(), note: d.note } }), { status: 200, headers: { 'content-type': 'application/json' } });
  }
  if (url.includes('/v1/charges')) return new Response(JSON.stringify({ status: 'success', data: { id: 'chg_test', next_action: { url: 'https://checkout.flutterwave.com/hosted/test' } } }), { status: 200, headers: { 'content-type': 'application/json' } });
  return new Response('{}', { status: 404 });
};
function moneyEnv() {
  const env = teamEnv();
  env.FLW_CLIENT_ID = 'FLWV4-ID'; env.FLW_CLIENT_SECRET = 'FLWV4-SECRET';
  env.FLW_WEBHOOK_HASH = webhookHash;
  return env;
}
const wh = (env, payload) => hit(env, '/flw-webhook', { method: 'POST', headers: { 'content-type': 'application/json', 'verif-hash': webhookHash }, body: JSON.stringify(payload) });

/* published formula (§6.1): 5 seats/500 docs → standard base + 2 blocks */
const te2 = moneyEnv();
r = await hit(te2, '/business/teams', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'boss@newfirm.ng', name: 'New Firm', seats: 5, docs: 500, segment: 'property-manager' }) });
ok('team creation → unpaid team + owner seat + PUBLISHED price (server-computed)', r.status === 200 && r.j.team.id.startsWith('t') && r.j.quote.price === 276000 && r.j.quote.vat === 20700 && r.j.quote.total === 296700, String(r.status) + ' ' + JSON.stringify(r.j.quote || {}).slice(0, 100));
const team1 = r.j.team.id;
const t1rec = JSON.parse(await te2.KV.get('team:' + team1));
ok('created team stored unpaid with seat index + magic link emailed', t1rec.status === 'unpaid' && t1rec.name === 'New Firm' && (await te2.KV.get('seatidx:boss@newfirm.ng')) === team1 && /team_token=boss(%40|@)newfirm\.ng~/.test((((mailCap[mailCap.length - 1] || {}).body || {}).text || '')), JSON.stringify(t1rec).slice(0, 100));
r = await hit(te2, '/business/teams', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'boss@newfirm.ng', name: 'New Firm', seats: 3, docs: 100 }) });
ok('same email creating a second team → 400 (one team per email)', r.status === 400, String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 80));

/* formula edges: 25 seats → growth + 5×₦48k; 2 seats/5000 docs → starter + 49 blocks */
r = await hit(te2, '/business/teams', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'big@bigfirm.ng', name: 'Big Firm', seats: 25, docs: 1000 }) });
ok('25 seats/1000 docs → ₦720,000 (growth + 5 seat units)', r.status === 200 && r.j.quote.price === 720000 && r.j.quote.total === 774000, JSON.stringify(r.j.quote || {}).slice(0, 100));
r = await hit(te2, '/business/teams', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'vol@volfirm.ng', name: 'Vol Firm', seats: 2, docs: 5000 }) });
ok('2 seats/5000 docs → ₦978,000 (starter + 49 doc blocks)', r.status === 200 && r.j.quote.price === 978000, JSON.stringify(r.j.quote || {}).slice(0, 100));

/* unpaid sign-in is allowed (to pay) and exposes the quote — no branding yet */
r = await hit(te2, '/business/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'boss@newfirm.ng' }) });
ok('unpaid team can request a sign-in link (to reach checkout)', r.status === 200, String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 80));
const bossMagic = decodeURIComponent((((mailCap[mailCap.length - 1] || {}).body || {}).text || '').match(/team_token=([\w.~@%]+)/)[1]);
r = await hit(te2, '/business/login?token=' + encodeURIComponent(bossMagic));
const bossTok = r.j.token;
r = await hit(te2, '/business/team', authed(bossTok));
ok('unpaid session → /business/team returns status unpaid + quote (no active licence)', r.status === 200 && r.j.team.status === 'unpaid' && r.j.quote.total === 296700, String(r.status) + ' ' + JSON.stringify(r.j.team || {}).slice(0, 100));
await te2.KV.put('team:told', JSON.stringify({ id: 'told', slug: 'old', name: 'Old Unpaid', status: 'unpaid', created: new Date(Date.now() - 20 * 864e5).toISOString(), expiry: '' }));
await te2.KV.put('team:told:seats', JSON.stringify([T1('late2@old.co', 'Late', 'owner')]));
await te2.KV.put('seatidx:late2@old.co', 'told');
r = await hit(te2, '/business/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'late2@old.co' }) });
ok('unpaid team older than 14 days → sign-in blocked', r.status === 400, String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 80));

/* transfer charge: VA from Flutterwave, vendor expiry honoured */
r = await hit(te2, '/business/team/charge', Object.assign(authed(bossTok), { method: 'POST', headers: Object.assign(authed(bossTok).headers, { 'content-type': 'application/json' }), body: JSON.stringify({ method: 'transfer' }) }));
ok('charge(transfer) → invoice + VA (vendor expiry HONOURED, not our requested 7d)', r.status === 200 && r.j.invoice.total === 296700 && r.j.va.account === '1234567890' && r.j.va.bank === 'WEMA BANK' && Math.abs(Date.parse(r.j.va.expires) - Date.now()) < 3700e3, String(r.status) + ' ' + JSON.stringify(r.j.va || {}).slice(0, 100));
const inv1 = r.j.invoice.id;
const invRec = JSON.parse(await te2.KV.get('inv:' + inv1));
ok('invoice stored open with reference index + team pointer', invRec.status === 'open' && (await te2.KV.get('invref:' + inv1)) === inv1 && (await te2.KV.get('team:' + team1 + ':inv')) === inv1, JSON.stringify(invRec).slice(0, 90));
r = await hit(te2, '/business/team/charge', Object.assign(authed(bossTok), { method: 'POST', headers: Object.assign(authed(bossTok).headers, { 'content-type': 'application/json' }), body: JSON.stringify({ method: 'transfer' }) }));
ok('second charge while one is open → reuses it (no duplicate VA)', r.status === 200 && r.j.reused === true && r.j.invoice.id === inv1, String(r.status) + ' ' + JSON.stringify(r.j.invoice || {}).slice(0, 80));

/* webhook: correct amount (naira) → team active +365d, invoice paid, owner emailed */
r = await wh(te2, { event: 'charge.completed', 'event.type': 'BANK_TRANSFER_TRANSACTION', data: { status: 'successful', currency: 'NGN', amount: 296700, tx_ref: inv1, flw_ref: 'FLW-ACT-1', customer: { email: 'boss@newfirm.ng' } } });
const t1after = JSON.parse(await te2.KV.get('team:' + team1));
ok('webhook correct amount (naira) → 200 + team active +365d + invoice paid', r.status === 200 && t1after.status === 'active' && (await te2.KV.get('inv:' + inv1)).includes('"paid"') && Math.abs(Math.abs(new Date(t1after.expiry).getTime() - Date.now()) - 365 * 864e5) < 2 * 864e5, String(r.status) + ' team=' + JSON.stringify(t1after).slice(0, 90));
ok('activation email sent to the team owner', /is live on DocOga/i.test((((mailCap[mailCap.length - 1] || {}).body || {}).subject || '')), JSON.stringify(((mailCap[mailCap.length - 1] || {}).body || {}).subject || '').slice(0, 80));
const expiryBefore = t1after.expiry;
r = await wh(te2, { event: 'charge.completed', 'event.type': 'BANK_TRANSFER_TRANSACTION', data: { status: 'successful', currency: 'NGN', amount: 296700, tx_ref: inv1, flw_ref: 'FLW-ACT-1', customer: { email: 'boss@newfirm.ng' } } });
ok('duplicate webhook → idempotent (200, expiry unchanged)', r.status === 200 && (await te2.KV.get('team:' + team1)).includes(expiryBefore), String(r.status));

/* wrong amount → no activation, VA voided + fresh VA + email (§7.4) */
r = await hit(te2, '/business/teams', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'wa@wa.co', name: 'Wrong Amount Co', seats: 3, docs: 100 }) });
const team2 = r.j.team.id;
r = await hit(te2, '/business/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'wa@wa.co' }) });
const boss2Magic = decodeURIComponent((((mailCap[mailCap.length - 1] || {}).body || {}).text || '').match(/team_token=([\w.~@%]+)/)[1]);
r = await hit(te2, '/business/login?token=' + encodeURIComponent(boss2Magic));
const boss2Tok = r.j.token;
r = await hit(te2, '/business/team/charge', Object.assign(authed(boss2Tok), { method: 'POST', headers: Object.assign(authed(boss2Tok).headers, { 'content-type': 'application/json' }), body: JSON.stringify({ method: 'transfer' }) }));
const inv2 = r.j.invoice.id;
const vaCallsBefore = flwCalls.length;
r = await wh(te2, { event: 'charge.completed', 'event.type': 'BANK_TRANSFER_TRANSACTION', data: { status: 'successful', currency: 'NGN', amount: 50000, tx_ref: inv2, flw_ref: 'FLW-WRONG-1', customer: { email: 'wa@wa.co' } } });
const t2after = JSON.parse(await te2.KV.get('team:' + team2));
const inv2rec = JSON.parse(await te2.KV.get('inv:' + inv2));
ok('wrong amount → 200, NO activation, invoice wrong_amount, fresh VA issued + owner emailed', r.status === 200 && t2after.status === 'unpaid' && inv2rec.status === 'wrong_amount' && inv2rec.received_amount === 50000 && flwCalls.length === vaCallsBefore + 1 && /wrong amount/i.test((((mailCap[mailCap.length - 1] || {}).body || {}).subject || '')), String(r.status) + ' inv=' + JSON.stringify(inv2rec).slice(0, 100));

/* kobo units (v4 minor units) → accepted */
r = await hit(te2, '/business/teams', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'kobo@kobo.co', name: 'Kobo Co', seats: 4, docs: 300 }) });
const team3 = r.j.team.id;
r = await hit(te2, '/business/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'kobo@kobo.co' }) });
const koboMagic = decodeURIComponent((((mailCap[mailCap.length - 1] || {}).body || {}).text || '').match(/team_token=([\w.~@%]+)/)[1]);
r = await hit(te2, '/business/login?token=' + encodeURIComponent(koboMagic));
const koboTok = r.j.token;
r = await hit(te2, '/business/team/charge', Object.assign(authed(koboTok), { method: 'POST', headers: Object.assign(authed(koboTok).headers, { 'content-type': 'application/json' }), body: JSON.stringify({ method: 'transfer' }) }));
const inv3 = r.j.invoice.id;
const total3 = r.j.invoice.total;
r = await wh(te2, { type: 'charge.completed', data: { status: 'succeeded', currency: 'NGN', amount: total3 * 100, reference: inv3, customer: { email: 'kobo@kobo.co' } } });
ok('v4-style webhook in KOBO (minor units) → activated (both units accepted)', r.status === 200 && (await te2.KV.get('team:' + team3)).includes('"active"'), String(r.status) + ' total=' + total3);

/* card (v4 hosted generic charge) */
r = await hit(te2, '/business/teams', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'card@card.co', name: 'Card Co', seats: 3, docs: 100 }) });
const team4 = r.j.team.id;
r = await hit(te2, '/business/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: 'card@card.co' }) });
const cardMagic = decodeURIComponent((((mailCap[mailCap.length - 1] || {}).body || {}).text || '').match(/team_token=([\w.~@%]+)/)[1]);
r = await hit(te2, '/business/login?token=' + encodeURIComponent(cardMagic));
const cardTok = r.j.token;
r = await hit(te2, '/business/team/charge', Object.assign(authed(cardTok), { method: 'POST', headers: Object.assign(authed(cardTok).headers, { 'content-type': 'application/json' }), body: JSON.stringify({ method: 'card' }) }));
ok('charge(card) → v4 hosted checkout URL returned', r.status === 200 && r.j.pay_url === 'https://checkout.flutterwave.com/hosted/test', String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 100));
r = await hit(te2, '/business/team/charge', Object.assign(authed(bossTok), { method: 'POST', headers: Object.assign(authed(bossTok).headers, { 'content-type': 'application/json' }), body: JSON.stringify({ method: 'transfer' }) }));
ok('active team cannot create a new charge (renewals are by email in Phase 2)', r.status === 400, String(r.status) + ' ' + JSON.stringify(r.j).slice(0, 90));

globalThis.fetch = realFetch;

console.log(fails === 0 ? '\n🏆 WORKER LOGIC UNIT-VERIFIED: expiry / fence / hostile records / top-up / redirect verify / signed webhook / underpayment gate / email hand-off / business waitlist / team core (magic-link auth, brand, seats, revoke)' : '\n💥 ' + fails + ' FAILED');
process.exit(fails ? 1 : 0);
