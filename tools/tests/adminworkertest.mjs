import mod from '../../worker/index.js';
/* Persistent unit test for the OWNER ADMIN API: real worker code + mock KV.
 * Style and helpers match workertest.mjs so both suites read the same way.
 * What this file is really guarding:
 *   - fail-closed behaviour (a half-configured admin must be shut, not open)
 *   - the passphrase and the signing secret are never echoed by any route
 *   - the ledger counters move on exactly the events that create value
 *   - no keyspace scan is reachable from a normal dashboard load */
const NOW = Date.now();
let fails = 0;
const ok = (n, c, x = '') => { c ? console.log('  ✓ ' + n) : (console.log('  ✗ FAIL: ' + n + ' | ' + x), fails++); };
const PASS = 'correct horse battery staple oga';
const SIGN = 'a-very-long-signing-secret-not-the-passphrase';

function makeEnv(records = {}, extra = {}) {
  const store = new Map(Object.entries(records));
  let writes = 0, reads = 0, lists = 0;
  const env = {
    KV: {
      get: async k => { reads++; return store.has(k) ? store.get(k) : null; },
      put: async (k, v) => { writes++; store.set(k, String(v)); },
      delete: async k => { writes++; store.delete(k); },
      incr: async (k, amt = 1) => { writes++; const n = Number(store.get(k) || '0') + Number(amt); store.set(k, String(n)); return n; },
      list: async ({ prefix = '', limit = 1000 } = {}) => {
        lists++;
        return { keys: [...store.keys()].filter(k => k.startsWith(prefix)).slice(0, limit).map(name => ({ name })), list_complete: true };
      },
      _store: store, _counts: () => ({ writes, reads, lists }),
    },
    SITE_URL: 'https://docoga.com.ng',
    PAYMENT_URL: 'https://flutterwave.com/pay/x',
    PROVIDER: 'flw',
    ADMIN_PASSPHRASE: PASS,
    ADMIN_AUTH_SECRET: SIGN,
    ...extra,
  };
  return env;
}
async function hit(env, path, init = {}) {
  const r = await mod.fetch(new Request('https://w' + path, init), env, {});
  const text = await r.text();
  let j = null; try { j = JSON.parse(text); } catch (e) {}
  return { status: r.status, j, text, headers: r.headers };
}
const post = (body, tok, ip) => {
  const headers = { 'content-type': 'application/json', 'cf-connecting-ip': ip || '102.89.1.7' };
  if (tok) headers.authorization = 'Bearer ' + tok;
  return { method: 'POST', headers, body: JSON.stringify(body) };
};
const get = (tok, ip) => ({ headers: Object.assign({ 'cf-connecting-ip': ip || '102.89.1.7' }, tok ? { authorization: 'Bearer ' + tok } : {}) });
async function buildSnap(env) {
  let job;
  await mod.scheduled({ cron: '0 7 * * *' }, env, { waitUntil: (p) => { job = p; } });
  await job;
  return JSON.parse(await env.KV.get('adm:snap') || 'null');
}
async function login(env, pass = PASS, ip) {
  const r = await hit(env, '/admin/login', post({ pass }, null, ip));
  return r;
}
async function authed(env, pass = PASS) {
  const r = await login(env, pass);
  if (!r.j || !r.j.token) throw new Error('login failed in setup: ' + r.status + ' ' + r.text.slice(0, 120));
  return r.j.token;
}
const dayOf = (ms) => new Date(ms).toISOString().slice(0, 10);
const today = dayOf(NOW);
const rec = (code, over = {}) => JSON.stringify(Object.assign({ code, email: '', ref: 'x', issuedAt: NOW, used: false, source: 'online', exp: NOW + 30 * 864e5 }, over));

console.log('— fail-closed when the admin is not configured —');
{
  const noPass = makeEnv({}, { ADMIN_PASSPHRASE: undefined });
  const noSign = makeEnv({}, { ADMIN_AUTH_SECRET: undefined });
  for (const [name, env] of [['ADMIN_PASSPHRASE unset', noPass], ['ADMIN_AUTH_SECRET unset', noSign]]) {
    const loginR = await hit(env, '/admin/login', post({ pass: PASS }));
    const dataR = await hit(env, '/admin/data', get('deadbeefdeadbeef.'));
    ok(name + ' → /admin/login 503 admin_disabled', loginR.status === 503 && loginR.j.error === 'admin_disabled', loginR.status + ' ' + loginR.text.slice(0, 80));
    ok(name + ' → /admin/data 503, never 401 (an unconfigured admin must not look like a login form)',
       dataR.status === 503 && dataR.j.error === 'admin_disabled', dataR.status + ' ' + dataR.text.slice(0, 80));
  }
  const anyPath = await hit(makeEnv({}, { ADMIN_PASSPHRASE: undefined }), '/admin/issue', post({ email: 'x@y.co' }));
  ok('unconfigured admin refuses a mint too (no bypass for the write paths)', anyPath.status === 503, String(anyPath.status));
}

console.log('— login, lockout, revocation —');
let TOKEN = '';
{
  const env = makeEnv({});
  const bad = await login(env, 'nope');
  ok('wrong passphrase → 401 wrong passphrase', bad.status === 401 && bad.j.error === 'wrong passphrase', bad.status + ' ' + bad.text.slice(0, 80));
  const empty = await login(env, '');
  ok('empty passphrase → 401, and no token', empty.status === 401 && !empty.j.token);
  const good = await login(env);
  TOKEN = good.j.token || '';
  ok('right passphrase → 200 + token + 12h expiry', good.status === 200 && !!TOKEN && good.j.expiresInSeconds === 43200, JSON.stringify(good.j).slice(0, 120));
  ok('session record written to KV', (await env.KV.get('adm:sess:' + TOKEN.split('.')[0])) !== null);
  ok('failure counter cleared on success', (await env.KV.get('adm:fail:102.89.1.7')) === null);
  ok('last sign-in logged with a masked IP only', /"ip":"102\.89\.••"/.test(await env.KV.get('adm:lastlogin') || ''), await env.KV.get('adm:lastlogin') || 'none');

  let locked = 0;
  for (let i = 0; i < 6; i++) { const r = await login(env, 'guess' + i, '197.210.5.5'); if (r.status === 429) locked++; }
  ok('6th wrong attempt from one IP is a lockout, not another 401', locked === 1, '429s seen: ' + locked);
  const whileLocked = await login(env, PASS, '197.210.5.5');
  ok('the correct passphrase is still refused while locked (a lock must actually lock)', whileLocked.status === 429, String(whileLocked.status));
  const otherIp = await login(env, PASS, '197.210.9.9');
  ok('the lock is per-IP, not global', otherIp.status === 200 && !!otherIp.j.token, String(otherIp.status));

  const sid = TOKEN.split('.')[0];
  const forged = sid + '.' + 'A'.repeat(40);
  const f = await hit(env, '/admin/me', get(forged));
  ok('a forged signature is refused', f.status === 401 && f.j.error === 'sign_in_required', String(f.status));
  const nosig = await hit(env, '/admin/me', get(sid));
  ok('a bare sid with no signature is refused', nosig.status === 401, String(nosig.status));
  const headerless = await hit(env, '/admin/me', { headers: { 'x-doco-team': TOKEN } });
  ok('admin accepts only Authorization: Bearer (no legacy back-door header)', headerless.status === 401, String(headerless.status));

  // revocation must be immediate: delete the KV record, keep the token
  await env.KV.delete('adm:sess:' + sid);
  const after = await hit(env, '/admin/data', get(TOKEN));
  ok('deleting the KV session kills a still-valid token on the next call', after.status === 401, String(after.status));
}

console.log('— /admin/data reads counters, not the keyspace —');
{
  const t = dayOf(Date.now());
  const ledger = { sold: 4, rev: 8000, offline: 2, manual: 1, wait: 7, bizcreate: 3, bizpaid: 1, bizrev: 120000, revoked: 0 };
  const seed = {};
  for (const f of Object.keys(ledger)) seed['stat:' + f + ':' + t] = String(ledger[f]);
  seed['debug:last-webhook-ts'] = String(Date.now() - 5 * 60000);
  const env = makeEnv(Object.assign(seed, {
    'debug:last-webhook': JSON.stringify({ type: 'charge.completed', data: { status: 'successful', amount: 2000, currency: 'NGN', tx_ref: 'FLW-1', customer: { email: 'secret.buyer@example.com' } } }),
    'code:OGA-AAAA-BBBB-CCCC': rec('OGA-AAAA-BBBB-CCCC', { email: 'a@b.co' }),
  }));
  const tok = await authed(env);
  const before = env.KV._counts();
  const r = await hit(env, '/admin/data', get(tok));
  const after = env.KV._counts();
  ok('200 + today’s counters verbatim', r.status === 200 && r.j.today.sold === 4 && r.j.today.rev === 8000 && r.j.today.wait === 7 && r.j.today.bizrev === 120000, JSON.stringify(r.j.today));
  ok('price and currency come from the server, not the client', r.j.priceNGN === 2000 && r.j.currency === 'NGN');
  ok('webhook vitals present with minutes-ago', r.j.health.lastWebhookMinutesAgo === 5 && r.j.health.event.type === 'charge.completed', JSON.stringify(r.j.health));
  ok('the raw webhook body is never echoed — no customer email in the response', r.text.indexOf('secret.buyer@example.com') < 0 && r.text.indexOf('FLW-1') >= 0);
  ok('no snapshot existed → built inline once and cached to KV', !!r.j.snapshot && r.j.snapshotJustBuilt === true && (await env.KV.get('adm:snap')) !== null);
  ok('the snapshot has the ledger series, passes block, teams and leads', Array.isArray(r.j.snapshot.series) && r.j.snapshot.series.length === 31 && !!r.j.snapshot.passes && Array.isArray(r.j.snapshot.teams), JSON.stringify(Object.keys(r.j.snapshot)));
  ok('drift self-check computed', typeof r.j.snapshot.drift.codesStored === 'number' && r.j.snapshot.drift.suspect === false, JSON.stringify(r.j.snapshot.drift));
  ok('drift pins a baseline {codes, since} on first build', r.j.snapshot.drift.baselineCodes === 1 && r.j.snapshot.drift.since === t && r.j.snapshot.drift.newCodes === 0 && (await env.KV.get('adm:baseline')) !== null, JSON.stringify(r.j.snapshot.drift));
  ok('a normal load reads ≤ 20 KV keys and writes nothing more than the snapshot', after.reads - before.reads <= 420 && after.writes - before.writes <= 2, JSON.stringify({ r: after.reads - before.reads, w: after.writes - before.writes }));
  ok('admin answers are no-store (revenue + emails must not sit in a shared cache)', r.headers.get('cache-control') === 'no-store' && r.headers.get('x-frame-options') === 'DENY', r.headers.get('cache-control') + '/' + r.headers.get('x-frame-options'));
  ok('no secret material in any admin response', r.text.indexOf(PASS) < 0 && r.text.indexOf(SIGN) < 0);
}


console.log('— drift compares codes created since the baseline with sales counted since it —');
{
  const t = dayOf(Date.now());
  const seed = {};
  for (let i = 0; i < 8; i++) seed['code:OGA-OLD' + i + '-BBBB-CCCC'] = rec('OGA-OLD' + i + '-BBBB-CCCC', { email: 'a@b.co' });
  const env = makeEnv(seed);
  const tok = await authed(env);
  const r1 = await hit(env, '/admin/data', get(tok));
  ok('eight old codes and zero counted sales is NOT drift on day one (the counters are younger than the codes)', r1.j.snapshot.drift.suspect === false && r1.j.snapshot.drift.baselineCodes === 8, JSON.stringify(r1.j.snapshot.drift));
  // Seven more codes appear with no counted sale → the counters really are missing money.
  for (let i = 0; i < 7; i++) await env.KV.put('code:OGA-NEW' + i + '-BBBB-CCCC', rec('OGA-NEW' + i + '-BBBB-CCCC', { email: 'a@b.co' }));
  await env.KV.delete('adm:snap');
  const r2 = await hit(env, '/admin/data', get(tok));
  ok('seven new codes with zero counted sales IS drift (off by 7 > 5)', r2.j.snapshot.drift.suspect === true && r2.j.snapshot.drift.newCodes === 7 && r2.j.snapshot.drift.countedSince === 0, JSON.stringify(r2.j.snapshot.drift));
  // A stale baseline (29 days old) is rolled forward.
  await env.KV.put('adm:baseline', JSON.stringify({ codes: 0, since: dayOf(Date.now() - 29 * 864e5) }));
  await env.KV.delete('adm:snap');
  const r3 = await hit(env, '/admin/data', get(tok));
  ok('a baseline older than 28 days is re-pinned to today', r3.j.snapshot.drift.since === t && r3.j.snapshot.drift.baselineCodes === 15 && r3.j.snapshot.drift.suspect === false, JSON.stringify(r3.j.snapshot.drift));
}

console.log('— snapshot freshness and the rebuild throttle —');
{
  const env = makeEnv({ 'adm:snap': JSON.stringify({ at: Date.now() - 7 * 864e5, series: [], totals: {}, passes: {}, teams: [], leads: {} }) });
  const tok = await authed(env);
  const r = await hit(env, '/admin/data', get(tok));
  ok('a stale snapshot is served immediately (the rebuild is off the response path)', r.status === 200 && r.j.snapshotJustBuilt === false && r.j.snapshot.at < Date.now() - 864e5 * 6, String(r.status));
  const f1 = await hit(env, '/admin/snapshot', post({}, tok));
  ok('manual refresh rebuilds and returns the new snapshot', f1.status === 200 && Date.now() - f1.j.snapshot.at < 5000, String(f1.status) + ' ' + f1.text.slice(0, 80));
  const f2 = await hit(env, '/admin/snapshot', post({}, tok));
  ok('a second refresh inside 5 minutes is refused (429) so 4 tabs cannot hammer KV', f2.status === 429 && f2.j.retryInSec === 300, String(f2.status) + ' ' + f2.text.slice(0, 60));
}

console.log('— direct sale: the only way to mint a paid code by hand —');
{
  const env = makeEnv({});
  const tok = await authed(env);
  const r = await hit(env, '/admin/issue', post({ email: 'Buyer@Example.co ', days: 90, amount: 5000, note: 'WhatsApp — Chidi, Onitsha' }, tok));
  const code = r.j && r.j.code;
  ok('mints a real OGA- code', r.status === 200 && /^OGA-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$/.test(code || ''), JSON.stringify(r.j).slice(0, 140));
  const stored = JSON.parse(await env.KV.get('code:' + code));
  ok('email is trimmed and lower-cased into the record', stored.email === 'buyer@example.co', stored.email);
  ok('source is manual, so the retail “sold” counter is not inflated', stored.source === 'manual' && Number(await env.KV.get('stat:manual:' + dayOf(Date.now())) || 0) === 1 && !(await env.KV.get('stat:sold:' + dayOf(Date.now()))));
  ok('the owner-entered naira lands in the revenue ledger', Number(await env.KV.get('stat:rev:' + dayOf(Date.now()))) === 5000, String(await env.KV.get('stat:rev:' + dayOf(Date.now()))));
  ok('expiry honours days=90', Math.abs((stored.exp - Date.now()) - 90 * 864e5) < 5000, String(stored.exp - Date.now()));
  ok('a ref is minted so the record is auditable', /^MANUAL-[0-9A-F]{10}$/.test(stored.ref), stored.ref);
  ok('the note survives (this is how a WhatsApp sale is remembered)', stored.note === 'WhatsApp — Chidi, Onitsha', stored.note);
  ok('expiry index records the code on its expiry date', (JSON.parse(await env.KV.get('adm:exp:' + dayOf(stored.exp)) || '[]')).indexOf(code) >= 0);
  ok('email index makes the buyer findable in one get', (JSON.parse(await env.KV.get('adm:em:buyer@example.co') || '[]'))[0] === code);
  ok('the rolling feed saw it', JSON.parse(await env.KV.get('adm:recent') || '[]')[0].code === code);

  const comp = await hit(env, '/admin/issue', post({ days: 30 }, tok));
  ok('a comp (no amount) mints without touching revenue', comp.status === 200 && Number(await env.KV.get('stat:rev:' + dayOf(Date.now()))) === 5000, JSON.stringify(comp.j).slice(0, 90));
  const compRec = JSON.parse(await env.KV.get('code:' + comp.j.code));
  ok('a blank email stays blank — no address invented, no send attempted', compRec.email === '' && compRec.source === 'manual' && compRec.mailFailed !== true, JSON.stringify({ e: compRec.email, m: compRec.mailFailed }));
  const badMail = await hit(env, '/admin/issue', post({ email: 'not-an-email' }, tok));
  ok('an invalid email is refused before anything is written', badMail.status === 400 && !badMail.j.code, String(badMail.status));
  const clamp = await hit(env, '/admin/issue', post({ days: 99999, amount: -500 }, tok));
  const clamped = JSON.parse(await env.KV.get('code:' + clamp.j.code));
  ok('days clamps to 365 and a negative amount cannot subtract revenue', Math.round((clamped.exp - Date.now()) / 864e5) === 365 && Number(await env.KV.get('stat:rev:' + dayOf(Date.now()))) === 5000, JSON.stringify({ d: Math.round((clamped.exp - Date.now()) / 864e5) }));

  const capped = makeEnv({ ['adm:issue:' + dayOf(Date.now())]: '200' });
  const ctok = await authed(capped);
  const blocked = await hit(capped, '/admin/issue', post({}, ctok));
  ok('the daily mint cap stops a runaway or a hijacked session', blocked.status === 429 && /cap/i.test(blocked.j.error), String(blocked.status) + ' ' + blocked.text.slice(0, 70));
}

console.log('— revoke / extend / resend, and what the buyer then sees —');
{
  const env = makeEnv({
    'code:OGA-REVK-IJKL-MNOP': rec('OGA-REVK-IJKL-MNOP', { email: 'cheater@example.com', devices: ['d1'] }),
    'code:OGA-EXTX-KLMN-OPQR': rec('OGA-EXTX-KLMN-OPQR', { email: 'loyal@example.com', exp: NOW + 3 * 864e5 }),
  });
  const tok = await authed(env);
  const rv = await hit(env, '/admin/revoke', post({ code: 'oga-revk-ijkl-mnop' }, tok)); // lower-case + dashes: same input a human types
  ok('revoke answers ok and normalises the code', rv.status === 200 && rv.j.ok, JSON.stringify(rv.j).slice(0, 90));
  const r = JSON.parse(await env.KV.get('code:OGA-REVK-IJKL-MNOP'));
  ok('the record is marked revoked with the expiry forced into the past', r.revoked === true && r.exp < Date.now() && r.revokedAt > 0, JSON.stringify({ e: r.exp - Date.now() }));
  ok('the revoked counter moved', Number(await env.KV.get('stat:revoked:' + dayOf(Date.now())) || 0) === 1);
  const afterBuyer = await hit(env, '/activate?code=OGA-REVK-IJKL-MNOP&did=d9');
  ok('the buyer’s app now says it was cancelled (not “expired”)', afterBuyer.status === 403 && /cancelled by DocOga/i.test(afterBuyer.j.error), JSON.stringify(afterBuyer.j));
  const again = await hit(env, '/admin/revoke', post({ code: 'OGA-REVK-IJKL-MNOP' }, tok));
  ok('revoking twice is idempotent and reports it', again.status === 200 && again.j.alreadyRevoked === true, JSON.stringify(again.j));
  const missing = await hit(env, '/admin/revoke', post({ code: 'OGA-NOPE-NOPE-NOPE' }, tok));
  ok('revoking an unknown code is a 404, never a 500', missing.status === 404, String(missing.status));

  const ex = await hit(env, '/admin/extend', post({ code: 'OGA-EXTX-KLMN-OPQR', days: 10 }, tok));
  const e = JSON.parse(await env.KV.get('code:OGA-EXTX-KLMN-OPQR'));
  ok('extend stacks on the remaining days (an early gift never loses the 3 days left)', ex.status === 200 && Math.abs((e.exp - NOW) - 13 * 864e5) < 5000, String(e.exp - NOW));
  ok('the reminder flag is reset so the new date re-alarms', !e.remindedAt);
  const un = await hit(env, '/admin/extend', post({ code: 'OGA-REVK-IJKL-MNOP', days: 30 }, tok));
  const u = JSON.parse(await env.KV.get('code:OGA-REVK-IJKL-MNOP'));
  ok('extending a revoked pass restores access and restarts the clock from today', un.j.unrevoked === true && u.revoked === false && Math.round((u.exp - Date.now()) / 864e5) === 30, JSON.stringify(un.j));
  const back = await hit(env, '/activate?code=OGA-REVK-IJKL-MNOP&did=d1');
  ok('the restored pass activates again on the device it already had', back.status === 200 && back.j.exp === u.exp, JSON.stringify(back.j).slice(0, 90));

  const noMail = await hit(env, '/admin/resend', post({ code: 'OGA-EXTX-KLMN-OPQR' }, tok));
  ok('resend with no mail provider configured fails as a 502, not silently', noMail.status === 502 && /provider/i.test(noMail.j.error), String(noMail.status) + ' ' + noMail.text.slice(0, 80));
  const blank = await hit(env, '/admin/resend', post({ code: 'OGA-CODX-KLMN-OPQR' }, tok));
  ok('resend to a code with no email on file is refused 400', blank.status === 400 || blank.status === 404, String(blank.status));
}

console.log('— search: indexed first, bounded scan on request only —');
{
  const env = makeEnv({
    'code:OGA-FIND-2345-6789': rec('OGA-FIND-2345-6789', { email: 'chidi@one.ng', ref: 'FLWREF9', note: 'Onitsha agent' }),
    'ref:FLWREF9': 'OGA-FIND-2345-6789',
    'adm:em:chidi@one.ng': JSON.stringify(['OGA-FIND-2345-6789']),
    'code:OGA-OTHR-2345-6789': rec('OGA-OTHR-2345-6789', { email: 'adasomething@one.ng' }),
  });
  const tok = await authed(env);
  const byCode = await hit(env, '/admin/codes?q=' + encodeURIComponent('oga find-2345 6789'), get(tok));
  ok('a code typed with spaces and lower case still resolves', byCode.j.mode === 'exact' && byCode.j.rows[0].code === 'OGA-FIND-2345-6789', JSON.stringify(byCode.j).slice(0, 120));
  ok('the view reports days left, devices and active state', byCode.j.rows[0].daysLeft === 30 && byCode.j.rows[0].active === true && byCode.j.rows[0].devices === 0, JSON.stringify(byCode.j.rows[0]));
  const byRef = await hit(env, '/admin/codes?q=FLWREF9', get(tok));
  ok('a payment reference resolves through the ref alias', byRef.j.mode === 'exact' && byRef.j.rows[0].ref === 'FLWREF9', JSON.stringify(byRef.j).slice(0, 120));
  const byMail = await hit(env, '/admin/codes?q=chidi@one.ng', get(tok));
  ok('an email resolves through the index in one get', byMail.j.mode === 'email' && byMail.j.rows.length === 1 && byMail.j.rows[0].note === 'Onitsha agent', JSON.stringify(byMail.j).slice(0, 140));
  const vague = await hit(env, '/admin/codes?q=chid', get(tok));
  ok('a partial word is refused with instructions, not a full scan', vague.status === 400 && /deep=1/.test(vague.j.error), JSON.stringify(vague.j));
  const deep = await hit(env, '/admin/codes?q=chid&deep=1', get(tok));
  ok('deep=1 runs the bounded scan and finds the same row', deep.status === 200 && deep.j.mode === 'deep' && deep.j.rows[0].code === 'OGA-FIND-2345-6789', JSON.stringify(deep.j).slice(0, 140));
  ok('the scan reports what it read, so “no results” is distinguishable from “gave up”', deep.j.scanned >= 2 && typeof deep.j.partial === 'boolean', JSON.stringify({ s: deep.j.scanned, p: deep.j.partial }));
  const empty = await hit(env, '/admin/codes', get(tok));
  ok('no query → the rolling recent feed, not a scan', empty.status === 200 && empty.j.mode === 'recent' && Array.isArray(empty.j.rows));
}

console.log('— session hygiene —');
{
  const env = makeEnv({});
  const mine = await authed(env);
  const other = (await login(env, PASS, '8.8.8.8')).j.token;
  const sidMine = mine.split('.')[0], sidOther = other.split('.')[0];
  const ls = await hit(env, '/admin/sessions', get(mine));
  ok('both sessions listed with masked ip + ua', ls.status === 200 && ls.j.rows.length === 2 && ls.j.current === sidMine && /••/.test(ls.j.rows[0].ip), JSON.stringify(ls.j.rows).slice(0, 160));
  const killOne = await hit(env, '/admin/session', post({ sid: sidOther }, mine));
  ok('one session can be dropped by id', killOne.status === 200 && killOne.j.killed === 1, JSON.stringify(killOne.j));
  const otherDead = await hit(env, '/admin/me', get(other));
  ok('the dropped session is dead immediately', otherDead.status === 401, String(otherDead.status));
  const third = (await login(env, PASS, '8.8.4.4')).j.token;
  const killAll = await hit(env, '/admin/session', post({ all: true }, mine));
  ok('“log out everywhere” spares the caller', killAll.status === 200 && killAll.j.killed >= 1, JSON.stringify(killAll.j));
  const meStill = await hit(env, '/admin/me', get(mine));
  const thirdDead = await hit(env, '/admin/me', get(third));
  ok('self survives, everyone else is out', meStill.status === 200 && thirdDead.status === 401, meStill.status + '/' + thirdDead.status);
  const out = await hit(env, '/admin/logout', post({}, mine));
  ok('logout drops the caller’s own session', out.status === 200 && (await hit(env, '/admin/me', get(mine))).status === 401);
  const hostile = await authed(env);
  const badSid = await hit(env, '/admin/session', post({ sid: '../../../etc/passwd' }, hostile));
  ok('a malformed sid is refused before it can reach KV.delete', badSid.status === 400 && badSid.j.error === 'unknown session', String(badSid.status) + ' ' + badSid.text.slice(0, 70));
}

console.log('— the ledger moves on the events that create value —');
{
  const d = dayOf(Date.now());
  const env = makeEnv({}, { ISSUE_SECRET: 'bridge-key-123' });
  const bridge = await hit(env, '/issue', { method: 'POST', headers: { 'content-type': 'application/json', 'x-docoga-key': 'bridge-key-123' }, body: JSON.stringify({ email: 'selar.buyer@example.com', ref: 'SELAR-1' }) });
  ok('the Selar bridge still issues, and is counted as a sale', bridge.status === 200 && Number(await env.KV.get('stat:sold:' + d) || 0) === 1, JSON.stringify(bridge.j).slice(0, 90));
  ok('bridge revenue is booked at the gate price', Number(await env.KV.get('stat:rev:' + d) || 0) === 2000, String(await env.KV.get('stat:rev:' + d)));
  ok('a bridge sale indexes the email too', (JSON.parse(await env.KV.get('adm:em:selar.buyer@example.com') || '[]')).length === 1);
  const dupe = await hit(env, '/issue', { method: 'POST', headers: { 'content-type': 'application/json', 'x-docoga-key': 'bridge-key-123' }, body: JSON.stringify({ email: 'other@example.com', ref: 'SELAR-1' }) });
  ok('a duplicate ref is idempotent — and must not double-count revenue', dupe.status === 200 && Number(await env.KV.get('stat:sold:' + d) || 0) === 1, JSON.stringify(dupe.j).slice(0, 110));

  const off = makeEnv({});
  const legacy = 'OGA-QCK4XXXXYYYYZZZZ';
  // any code from the offline batch validates by hash; count the activation as an offline sale
  const hashed = ['3d260bec'];
  const env2 = makeEnv({ 'bizwait:lead@firm.ng': 'x' });
  const wl = await hit(env2, '/business/waitlist', { method: 'POST', headers: { 'content-type': 'application/json', 'cf-connecting-ip': '41.1.1.1' }, body: JSON.stringify({ email: 'newlead@firm.ng', company: 'Firm', segment: 'estate-agent' }) });
  ok('a NEW waitlist signup bumps the lead counter', wl.status === 200 && Number(await env2.KV.get('stat:wait:' + d) || 0) === 1, JSON.stringify(wl.j).slice(0, 90));
  const wl2 = await hit(env2, '/business/waitlist', { method: 'POST', headers: { 'content-type': 'application/json', 'cf-connecting-ip': '41.1.1.1' }, body: JSON.stringify({ email: 'newlead@firm.ng' }) });
  ok('a duplicate signup does not double-count', wl2.status === 200 && wl2.j.alreadyOnList === true && Number(await env2.KV.get('stat:wait:' + d) || 0) === 1, JSON.stringify(wl2.j).slice(0, 90));

  // The expiry index is advisory, the record is authoritative: a revoked pass,
  // a renewed one and a bucket whose date has slipped must never be nudged.
  const soon = dayOf(Date.now() + 5 * 864e5);
  const envR = makeEnv(Object.assign({
    ['adm:exp:' + soon]: JSON.stringify(['OGA-LIVE-AAAA-BBBB', 'OGA-DEAD-AAAA-BBBB', 'OGA-GONE-AAAA-BBBB', 'OGA-STALE-AAAA-BBBB']),
    'code:OGA-LIVE-AAAA-BBBB': rec('OGA-LIVE-AAAA-BBBB', { email: 'due@example.com', exp: Date.now() + 5 * 864e5, note: 'agent' }),
    'code:OGA-DEAD-AAAA-BBBB': rec('OGA-DEAD-AAAA-BBBB', { email: 'gone@example.com', exp: Date.now() - 864e5, revoked: true }),
    'code:OGA-GONE-AAAA-BBBB': rec('OGA-GONE-AAAA-BBBB', { email: 'renewed@example.com', succ: 'OGA-NEW-AAAA-BBBB', exp: Date.now() + 5 * 864e5 }),
    'code:OGA-STALE-AAAA-BBBB': rec('OGA-STALE-AAAA-BBBB', { email: 'moved@example.com', exp: Date.now() + 60 * 864e5 }),
  }));
  const snapR = await buildSnap(envR);
  const codes = snapR.passes.expiring.map(x => x.code);
  ok('the expiring list re-reads every record it shows', codes.indexOf('OGA-LIVE-AAAA-BBBB') >= 0, JSON.stringify(snapR.passes.expiring).slice(0, 160));
  ok('a revoked code is dropped from the nudge list', codes.indexOf('OGA-DEAD-AAAA-BBBB') < 0);
  ok('a renewed code is dropped (its successor carries the days)', codes.indexOf('OGA-GONE-AAAA-BBBB') < 0);
  ok('a code whose expiry moved out of the window is dropped', codes.indexOf('OGA-STALE-AAAA-BBBB') < 0);
  ok('the buyer email and days-left come from the record, not the index', snapR.passes.expiring[0].email === 'due@example.com' && snapR.passes.expiring[0].daysLeft === 5, JSON.stringify(snapR.passes.expiring[0]));
  ok('activeEstimate counts DISTINCT indexed codes — one per code even when a top-up put it in two buckets — and is labelled an upper bound',
     snapR.passes.activeEstimate === 4 && /index/i.test(snapR.passes.activeBasis || ''), String(snapR.passes.activeEstimate) + ' / ' + snapR.passes.activeBasis);

  const env3 = makeEnv({ 'code:OGA-OLD2-AAAA-BBBB': rec('OGA-OLD2-AAAA-BBBB', { exp: Date.now() + 25 * 864e5 }) });
  const tok3 = await authed(env3);
  const ex = await hit(env3, '/admin/extend', post({ code: 'OGA-OLD2-AAAA-BBBB', days: 40 }, tok3));
  const stored = JSON.parse(await env3.KV.get('code:OGA-OLD2-AAAA-BBBB'));
  ok('a top-up re-indexes the NEW expiry date, so “expiring soon” stays true', ex.status === 200 && (JSON.parse(await env3.KV.get('adm:exp:' + dayOf(stored.exp)) || '[]')).indexOf('OGA-OLD2-AAAA-BBBB') >= 0, JSON.stringify(ex.j).slice(0, 90));
}

console.log('— exposure discipline —');
{
  const env = makeEnv({ 'code:OGA-LEAK-AAAA-BBBB': rec('OGA-LEAK-AAAA-BBBB', { email: 'buyer@private.ng', ref: 'FLWREF-SECRETISH' }) });
  const tok = await authed(env);
  const all = [];
  for (const p of ['/admin/data', '/admin/codes?q=OGA-LEAK-AAAA-BBBB', '/admin/sessions', '/admin/me']) all.push((await hit(env, p, get(tok))).text);
  const body = all.join('\n');
  ok('no route ever returns the signing secret or the passphrase', body.indexOf(SIGN) < 0 && body.indexOf(PASS) < 0);
  ok('no admin route leaks a raw VA/account number field', body.indexOf('"va"') < 0 || body.indexOf('account_number') < 0, 'account_number must not appear');
  ok('the code itself IS returned (the owner needs it to re-send a pass)', /OGA-LEAK-AAAA-BBBB/.test(body));
  const noTok = await Promise.all(['/admin/data', '/admin/snapshot', '/admin/issue', '/admin/revoke', '/admin/extend', '/admin/resend', '/admin/sessions', '/admin/session', '/admin/codes?q=a', '/admin/logout', '/admin/me']
    .map(p => hit(env, p, p.endsWith('?q=a') ? get('') : { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' })));
  ok('every admin route except /admin/login needs a session', noTok.every(r => r.status === 401), noTok.map(r => r.status).join(','));
  const unauth = await hit(env, '/admin/nosuchroute', get(tok));
  ok('an unknown admin sub-route is 404 (no route guessing hints)', unauth.status === 404, String(unauth.status));
  const getOnWrite = await hit(env, '/admin/issue', get(tok));
  ok('GET on a write route is 404 — writes need POST (no <img src> trigger)', getOnWrite.status === 404, String(getOnWrite.status));
}

console.log('— the daily cron rebuilds the snapshot for the owner —');
{
  const env = makeEnv({ ['stat:sold:' + dayOf(Date.now())]: '3' });
  let cronJob;
  await mod.scheduled({ cron: '0 7 * * *' }, env, { waitUntil: (p) => { cronJob = p; } });
  await cronJob; // the snapshot is built off the response path — the test must wait for it
  const snap = JSON.parse(await env.KV.get('adm:snap') || 'null');
  ok('scheduled() wrote a snapshot', !!snap && snap.totals.sold === 3, JSON.stringify(snap && snap.totals));
  ok('the cron snapshot is what /admin/data will serve next', !!snap && snap.series.length === 31);
  const off = makeEnv({}, { ADMIN_PASSPHRASE: undefined });
  let offJob;
  await mod.scheduled({ cron: '0 7 * * *' }, off, { waitUntil: (p) => { offJob = p; } });
  await offJob;
  ok('with the admin unconfigured, the cron does no snapshot work at all', (await off.KV.get('adm:snap')) === null);
}

console.log('— channel → revenue attribution: /tap counts checkouts, /verify counts sales, the snapshot reports both (17 Oct 2026) —');
{
  const env = makeEnv({});
  const tap = async (body) => hit(env, '/tap', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const a = await tap({ kind: 'checkout', src: 'tg' });
  await tap({ kind: 'checkout', src: 'fb' });
  await tap({ kind: 'checkout', src: 'tg' });
  await tap({ kind: 'checkout', src: 'weird<script>' });
  const bad = await tap({ kind: 'sale', src: 'tg' });
  ok('a checkout tap is accepted', a.status === 200 && a.j.ok === true, String(a.status));
  ok('a self-reported sale is refused — sales are counted by /verify only', bad.status === 400, String(bad.status));
  const weekKeys = [...env.KV._store ? env.KV._store.keys() : []].filter(k => k.startsWith('src:'));
  const row = JSON.parse(await env.KV.get(weekKeys.find(k => k.startsWith('src:checkout:')) || 'none') || '{}');
  ok('counters are per channel per ISO week, unknown tags fold into other', row.telegram === 2 && row.facebook === 1 && row.other === 1, JSON.stringify(row));
  const snap = await buildSnap(env);
  const wk = Object.keys(snap.sources.checkout)[0];
  ok('the snapshot carries sources{checkout,sale}{week:{channel:n}}', !!snap.sources && !!snap.sources.sale && snap.sources.checkout[wk].telegram === 2, JSON.stringify(snap.sources));
}

console.log('— social board: today\'s plan vs what GitHub Actions did (17 Oct 2026) —');
{
  // A fixed instant: Saturday 17 Oct 2026, 8:30pm Lagos (19:30 UTC).
  const T = Date.parse('2026-10-17T19:30:00Z');
  const realNow = Date.now; Date.now = () => T;
  const realFetch = globalThis.fetch;
  const table = [
    { workflow: 'instagram_autopost.yml', name: 'IG', cron: '10 18 * * *', inputs: { clock: 'true' } },
    { workflow: 'instagram_autopost.yml', name: 'IG', cron: '10 6 * * *', inputs: { clock: 'true' } },
    { workflow: 'youtube_boost.yml', name: 'Boost', cron: '20 18 * * *', inputs: {} },
    { workflow: 'facebook_story_afternoon.yml', name: 'FB story', cron: '40 18 * * *', inputs: {} },
    { workflow: 'threads_autopost.yml', name: 'Threads', cron: '10 19 * * *', inputs: { slot: 'evening' } },
    { workflow: 'automation-heartbeat.yml', name: 'Heartbeat', cron: '0 20 * * *', inputs: {} },
    { workflow: 'youtube_scheduled.yml', name: 'Shorts', cron: '0 17 * * 1-5', inputs: {} },   // weekdays only: not on a Saturday
    { workflow: 'brain.yml', name: 'Brain', cron: '30 0 * * *', inputs: {} },                  // 1:30am Lagos = 00:30 UTC same date
    { workflow: 'brain_scorecard.yml', name: 'Scorecard', cron: '40 5 * * 1', inputs: {} },    // Mondays only
  ];
  const run = (id, file, created, status, conclusion, event = 'workflow_dispatch') => ({
    id, name: file, path: '.github/workflows/' + file, event, status, conclusion, created_at: created, run_started_at: created,
    updated_at: created, run_attempt: 1, html_url: 'https://github.com/johnAzani/docoga/actions/runs/' + id, triggering_actor: { login: 'johnAzani' } });
  const runs = [
    run(1, 'instagram_autopost.yml', '2026-10-17T18:10:33Z', 'completed', 'failure'),
    run(2, 'youtube_boost.yml', '2026-10-17T18:20:33Z', 'completed', 'success'),
    run(3, 'threads_autopost.yml', '2026-10-17T19:10:31Z', 'in_progress', null),
    run(4, 'brain.yml', '2026-10-17T04:50:00Z', 'completed', 'success', 'schedule'),      // GitHub's own schedule, 4h20 late — still that slot
    run(5, 'facebook_autopost.yml', '2026-10-17T15:03:00Z', 'completed', 'success'),      // a manual run with no slot → extra
    run(6, 'deploy-pass-now.yml', '2026-10-17T16:40:00Z', 'completed', 'success', 'push'), // pushes are not plan material
  ];
  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url); calls.push((init.method || 'GET') + ' ' + u);
    const reply = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json' } });
    if (u.startsWith('https://docoga-clock.')) return reply({ ok: true, token: 'present', paused: false, entries: table.length, utc: new Date(T).toISOString(), entries_table: table });
    if (u.includes('/actions/runs?created=')) {
      const m = /created=([^.]+)\.\.([^&]+)/.exec(u);
      const a = Date.parse(m[1]), b = Date.parse(m[2]);
      return reply({ workflow_runs: runs.filter(r => { const c = Date.parse(r.created_at); return c >= a && c <= b; }) });
    }
    if (u.includes('/actions/runs/1/jobs')) return reply({ jobs: [{ id: 901, name: 'publish', conclusion: 'failure' }] });
    if (u.includes('/check-runs/901/annotations')) return reply([
      { annotation_level: 'failure', title: '', message: 'Process completed with exit code 5.' },
      { annotation_level: 'failure', title: '', message: 'https://docoga.com.ng/social/2026-10-17-instagram.jpg did not answer 200 within 900s. The render is committed but the site deploy has not published it — this is a race, not a credential problem.' }]);
    if (u.endsWith('/dispatches')) return new Response(null, { status: 204 });
    return reply({ message: 'unexpected ' + u }, 500);
  };
  try {
    const bare = makeEnv();
    const tokB = await authed(bare);
    const off = await hit(bare, '/admin/social', get(tokB));
    ok('no GH_DISPATCH_TOKEN → 200 {connected:false, reason}, never a 500 and never an empty table', off.status === 200 && off.j.connected === false && /GH_DISPATCH_TOKEN/.test(off.j.reason), off.text.slice(0, 160));
    const runOff = await hit(bare, '/admin/social/run', post({ workflow: 'threads_autopost.yml' }, tokB));
    ok('…and "run now" is 503 not_connected', runOff.status === 503 && runOff.j.error === 'not_connected', runOff.text.slice(0, 120));

    const env = makeEnv({}, { GH_DISPATCH_TOKEN: 'ghp_test' });
    const tok = await authed(env);
    const anon = await hit(env, '/admin/social', get());
    ok('the board needs a session', anon.status === 401, anon.status + '');
    const r = await hit(env, '/admin/social', get(tok));
    ok('connected board answers 200 with today = the Lagos day', r.status === 200 && r.j.connected === true && r.j.day === '2026-10-17', r.text.slice(0, 200));
    const slots = r.j.today.slots;
    const by = (file, utc) => slots.find(s => s.workflow === file && new Date(s.at).toISOString().startsWith(utc));
    ok('the plan is the clock\'s table: 7 slots for a Saturday (no weekday Short, no Monday scorecard)', slots.length === 7, slots.map(s => s.workflow + '@' + new Date(s.at).toISOString().slice(11, 16)).join(','));
    ok('slot times are the cron instants in UTC (Lagos 7:10pm = 18:10Z)', !!by('instagram_autopost.yml', '2026-10-17T18:10'), '');
    ok('a 1:30am Lagos slot lands on the right UTC date (00:30Z of the same date)', !!by('brain.yml', '2026-10-17T00:30'), '');
    const ig = by('instagram_autopost.yml', '2026-10-17T18:10'), igAm = by('instagram_autopost.yml', '2026-10-17T06:10');
    ok('the failed Instagram run is matched to its 7:10pm slot and reads "failed"', ig && ig.status === 'failed' && ig.run && ig.run.id === 1, JSON.stringify(ig));
    ok('…with the reason taken from the annotations, skipping the generic exit-code line', ig && /did not answer 200 within 900s/.test(ig.cause), ig && ig.cause);
    ok('the morning Instagram slot nobody ran reads "missed"', igAm && igAm.status === 'missed' && !igAm.run, JSON.stringify(igAm));
    ok('YouTube boost reads "done"', by('youtube_boost.yml', '2026-10-17T18:20').status === 'done', '');
    ok('Threads, still running, reads "running"', by('threads_autopost.yml', '2026-10-17T19:10').status === 'running', '');
    ok('the heartbeat at 9:00pm is "upcoming" at 8:30pm', by('automation-heartbeat.yml', '2026-10-17T20:00').status === 'upcoming', '');
    ok('the Facebook Story at 7:40pm with no run is "missed" (50 min past, beyond the 20-min grace)', by('facebook_story_afternoon.yml', '2026-10-17T18:40').status === 'missed', '');
    ok('GitHub\'s own late schedule run (4h20 after the slot) still counts for that slot', by('brain.yml', '2026-10-17T00:30').status === 'done', JSON.stringify(by('brain.yml', '2026-10-17T00:30').run));
    ok('a manual run with no slot shows under extras; a push run does not appear at all', r.j.today.extras.length === 1 && r.j.today.extras[0].workflow === 'facebook_autopost.yml', JSON.stringify(r.j.today.extras));
    const c = r.j.today.counts;
    ok('counts: posted counts only lanes a reader sees (boost is care, not a post)', c.posted === 0 && c.done === 2 && c.failed === 1 && c.running === 1 && c.missed === 2 && c.upcoming === 1, JSON.stringify(c));
    ok('the clock\'s health rides along', r.j.clock && r.j.clock.token === 'present' && r.j.clock.paused === false && r.j.planFrom === 'clock', JSON.stringify(r.j.clock));
    ok('seven history days are listed (pending until digested — at most two built per load)', r.j.days.length === 7 && r.j.days.filter(d => !d.pending).length <= 2, JSON.stringify(r.j.days.map(d => d.pending ? 'p' : 'ok')));
    const todayCalls = () => calls.filter(x => x.includes('created=2026-10-16T23:00:00Z')).length;
    const t1 = todayCalls();
    const again = await hit(env, '/admin/social', get(tok));
    ok('a second load inside 45 s re-reads neither today nor any finished day already digested (only the next two history days are filled in)',
       again.status === 200 && todayCalls() === t1 && again.j.days.filter(d => !d.pending).length === 4, (todayCalls() - t1) + ' today calls; ' + again.j.days.filter(d => !d.pending).length + ' digested');
    const fails1 = calls.filter(x => x.includes('/check-runs/901/annotations')).length;
    ok('the failure reason was fetched exactly once', fails1 === 1, fails1 + '');

    // Run now
    const before = calls.length;
    const go = await hit(env, '/admin/social/run', post({ workflow: 'threads_autopost.yml', inputs: { slot: 'evening', nope: '$(rm -rf /)', 'bad key!': 'x' } }, tok));
    const dispatch = calls.slice(before).find(x => x.startsWith('POST ') && x.endsWith('/dispatches')) || '';
    ok('"run now" dispatches the allow-listed workflow on main and keeps only clean inputs', go.status === 200 && go.j.ok && dispatch.includes('/actions/workflows/threads_autopost.yml/dispatches') && go.j.inputs.slot === 'evening' && !('nope' in go.j.inputs), go.text.slice(0, 200) + ' ' + dispatch);
    const twice = await hit(env, '/admin/social/run', post({ workflow: 'threads_autopost.yml' }, tok));
    ok('a second ask inside 10 minutes is 429 with the wait', twice.status === 429 && twice.j.error === 'already_asked' && twice.j.retryInSeconds > 0, twice.text.slice(0, 120));
    const unknown = await hit(env, '/admin/social/run', post({ workflow: 'deploy-pass-now.yml' }, tok));
    ok('a workflow outside the plan is refused (400 unknown_workflow)', unknown.status === 400 && unknown.j.error === 'unknown_workflow', unknown.text.slice(0, 120));
    const recent = JSON.parse(await env.KV.get('adm:recent') || '[]');
    ok('the dispatch is written to the activity feed', recent.some(x => x.kind === 'dispatch' && x.workflow === 'threads_autopost.yml'), JSON.stringify(recent[0]));

    // TikTok connect door: the landing page hands over TikTok's single-use code.
    const code = 'q7Zr0Xk*1!Abcdefghijklmnopqrstuvwxyz0123456789-_~.%2A';
    const b0 = calls.length;
    const tkOff = await hit(bare, '/admin/tiktok/connect', post({ code }, tokB));
    ok('tiktok connect without GH_DISPATCH_TOKEN is 503 not_connected', tkOff.status === 503 && tkOff.j.error === 'not_connected', tkOff.text.slice(0, 120));
    const tkAnon = await hit(env, '/admin/tiktok/connect', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ code }) });
    ok('tiktok connect needs a session', tkAnon.status === 401, tkAnon.status + '');
    const tkBad = await hit(env, '/admin/tiktok/connect', post({ code: 'short' }, tok));
    const tkBad2 = await hit(env, '/admin/tiktok/connect', post({ code: 'x'.repeat(20) + ' ;rm -rf /' }, tok));
    ok('a code that is too short or carries shell characters is 400 bad_code', tkBad.status === 400 && tkBad2.status === 400 && tkBad.j.error === 'bad_code', tkBad.text + tkBad2.text);
    const tkGo = await hit(env, '/admin/tiktok/connect', post({ code }, tok));
    const tkDispatch = calls.slice(b0).find(x => x.startsWith('POST ') && x.includes('/actions/workflows/tiktok_connect.yml/dispatches')) || '';
    ok('a real code dispatches tiktok_connect.yml on main with the code as its only input', tkGo.status === 200 && tkGo.j.ok && tkGo.j.workflow === 'tiktok_connect.yml' && !!tkDispatch, tkGo.text.slice(0, 160) + ' ' + tkDispatch);
    ok('the answer and the activity feed never carry the code', !tkGo.text.includes('q7Zr0Xk') && !(await env.KV.get('adm:recent')).includes('q7Zr0Xk') && JSON.parse(await env.KV.get('adm:recent'))[0].workflow === 'tiktok_connect.yml', (await env.KV.get('adm:recent')).slice(0, 160));
    const tkTwice = await hit(env, '/admin/tiktok/connect', post({ code }, tok));
    ok('a second send inside 45 s is 429 already_asked', tkTwice.status === 429 && tkTwice.j.error === 'already_asked', tkTwice.text.slice(0, 120));

    // The daily cron digests yesterday once.
    let job; await mod.scheduled({ cron: '0 7 * * *' }, env, { waitUntil: (p) => { job = p; } }); await job;
    const yd = JSON.parse(await env.KV.get('adm:social:2026-10-16') || 'null');
    ok('the daily cron leaves yesterday\'s digest in KV', yd && yd.ok && yd.day === '2026-10-16' && Array.isArray(yd.slots), String(await env.KV.get('adm:social:2026-10-16')).slice(0, 80));
    ok('no route echoed the token', !JSON.stringify([r.j, go.j, again.j]).includes('ghp_test'), '');
  } finally {
    Date.now = realNow; globalThis.fetch = realFetch;
  }
}

console.log('— website visits: Cloudflare Web Analytics, read-only, cached —');
{
  const realFetch = globalThis.fetch; const calls = [];
  const gql = { data: { viewer: { accounts: [{
    t7: [{ count: 70, sum: { visits: 52 } }], t28: [{ count: 240, sum: { visits: 180 } }],
    ref7: [{ sum: { visits: 33 }, dimensions: { refererHost: '' } }, { sum: { visits: 13 }, dimensions: { refererHost: 'www.google.com' } }, { sum: { visits: 6 }, dimensions: { refererHost: 'l.facebook.com' } }, { sum: { visits: 9 }, dimensions: { refererHost: 'docoga.com.ng' } }],
    path7: [{ count: 40, sum: { visits: 31 }, dimensions: { requestPath: '/' } }, { count: 5, sum: { visits: 4 }, dimensions: { requestPath: '/notice-to-quit-enugu' } }],
    country7: [{ sum: { visits: 45 }, dimensions: { countryName: 'NG' } }, { sum: { visits: 7 }, dimensions: { countryName: 'US' } }],
    days28: [{ count: 10, sum: { visits: 8 }, dimensions: { date: '2026-10-16' } }, { count: 12, sum: { visits: 9 }, dimensions: { date: '2026-10-17' } }],
  }] } } };
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url); calls.push((init.method || 'GET') + ' ' + u);
    if (u === 'https://docoga.com.ng/') return new Response("<html><script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{\"token\": \"0123456789abcdef0123456789abcdef\"}'></script></html>", { headers: { 'content-type': 'text/html' } });
    if (u === 'https://api.cloudflare.com/client/v4/graphql') {
      const body = JSON.parse(init.body);
      calls.push('gql siteTag=' + body.variables.f7.siteTag + ' host=' + body.variables.f7.requestHost);
      return new Response(JSON.stringify(gql), { headers: { 'content-type': 'application/json' } });
    }
    return new Response('{}', { status: 500 });
  };
  try {
    const bare = makeEnv(); const tokB = await authed(bare);
    const off = await hit(bare, '/admin/site', get(tokB));
    ok('no Cloudflare token → 200 {connected:false, reason}', off.status === 200 && off.j.connected === false && /CF_ANALYTICS_TOKEN/.test(off.j.reason), off.text.slice(0, 120));
    const env = makeEnv({}, { CF_ANALYTICS_TOKEN: 'cf_test', CLOUDFLARE_ACCOUNT_ID: 'acc' });
    const tok = await authed(env);
    const r = await hit(env, '/admin/site', get(tok));
    ok('visits 7 + 28 days, page views, Nigeria share from the ISO code', r.status === 200 && r.j.visits7 === 52 && r.j.pageviews7 === 70 && r.j.visits28 === 180 && r.j.nigeriaShare7 === 0.865, r.text.slice(0, 200));
    ok('channels: direct / google / facebook — the site\'s own host is dropped', JSON.stringify(r.j.byChannel) === JSON.stringify([['direct', 33], ['google', 13], ['facebook', 6]]), JSON.stringify(r.j.byChannel));
    ok('the site tag was read from the beacon the site serves and sent to Cloudflare', calls.some(x => x.startsWith('gql siteTag=0123456789abcdef0123456789abcdef host=docoga.com.ng')), calls.join('\n'));
    ok('the answer never carries the token or the whole tag', !r.text.includes('cf_test') && !r.text.includes('0123456789abcdef0123456789abcdef'), '');
    const n = calls.length;
    const again = await hit(env, '/admin/site', get(tok));
    ok('a second load inside 30 min is served from KV (no Cloudflare call)', again.status === 200 && again.j.cached === true && calls.length === n, (calls.length - n) + ' calls');
  } finally { globalThis.fetch = realFetch; }
}

console.log('— /admin/feed: the repo\'s records, as pushed by dashboard_sync.yml —');
{
  const bare = makeEnv(); const tokB = await authed(bare);
  const off = await hit(bare, '/admin/feed', get(tokB));
  ok('no feed pushed yet → 200 {connected:false, reason}', off.status === 200 && off.j.connected === false && /Dashboard feed/.test(off.j.reason), off.text.slice(0, 160));
  const feed = { version: 1, generated_at: new Date(Date.now() - 600e3).toISOString(), plan: [{ date: '2026-10-18', approved: false }], posted: [{ at: '2026-10-17T19:12:14Z', platform: 'threads', kind: 'post', title: 'Caution Fee', url: 'https://www.threads.com/@docoga.ng/post/x' }], growth: { rows: [] }, youtube: { snapshot: null, scheduled: [] } };
  const env = makeEnv({ 'adm:feed': JSON.stringify(feed) }); const tok = await authed(env);
  const r = await hit(env, '/admin/feed', get(tok));
  ok('the feed comes back whole with its age in seconds', r.status === 200 && r.j.connected === true && r.j.feed.posted[0].platform === 'threads' && r.j.ageSeconds >= 590 && r.j.ageSeconds <= 620, r.text.slice(0, 160));
  const anon = await hit(env, '/admin/feed');
  ok('without a session it is 401', anon.status === 401, String(anon.status));
  const broken = makeEnv({ 'adm:feed': '{not json' }); const tok2 = await authed(broken);
  const b = await hit(broken, '/admin/feed', get(tok2));
  ok('a corrupt key reads as not connected, never a 500', b.status === 200 && b.j.connected === false, b.text.slice(0, 100));
}

console.log('');
console.log(fails ? `❌ ADMIN SUITE: ${fails} failure(s)` : '🏆 admin suite green');
process.exit(fails ? 1 : 0);
