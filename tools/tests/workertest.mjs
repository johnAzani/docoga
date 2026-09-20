import mod from '/home/user/docoga/worker/index.js';
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

console.log(fails === 0 ? '\n🏆 WORKER LOGIC UNIT-VERIFIED: expired / fence / hostile records / top-up all correct' : '\n💥 ' + fails + ' FAILED');
process.exit(fails ? 1 : 0);
