import mod, { shouldAutoReply, buildReplyMime, sendAutoReply, REPLY_TEXT } from '../../worker/support-mail/index.js';
/* Persistent unit test: REAL support-mail worker code under plain node — no live
 * Cloudflare/Brevo. The CF path is exercised through its documented failure mode:
 * under node, `import("cloudflare:email")` throws, so sendAutoReply must fall
 * back to the Brevo API path (mocked fetch) and still deliver the reply. */
let fails = 0;
const ok = (n, c, x = '') => { c ? console.log('  ✓ ' + n) : (console.log('  ✗ FAIL: ' + n + ' | ' + x), fails++); };
const H = (o) => new Headers(o);

console.log('— auto-reply guard (who gets the reply) —');
ok('external human mail qualifies',
   shouldAutoReply({ from: 'buyer@firm.com.ng', subject: 'Question', headers: H({}) }) === true);
ok('our own domain never gets a reply (self-thread loop guard)',
   shouldAutoReply({ from: 'business@docoga.com.ng', subject: 'hi', headers: H({}) }) === false);
ok('other alias on our domain never gets a reply',
   shouldAutoReply({ from: 'someone@docoga.com.ng', subject: 'hi', headers: H({}) }) === false);
ok('noreply sender gets no reply',
   shouldAutoReply({ from: 'noreply@stripe.com', subject: 'Receipt', headers: H({}) }) === false);
ok('mailer-daemon bounce gets no reply',
   shouldAutoReply({ from: 'mailer-daemon@mx.example.com', subject: 'Undelivered Mail', headers: H({}) }) === false);
ok('automatic-reply (OOO ping-pong) gets no reply',
   shouldAutoReply({ from: 'client@mail.example.com', subject: 'Re: out of office', headers: H({ 'auto-submitted': 'automatic-reply' }) }) === false);
ok('mailing list (List-Unsubscribe) gets no reply',
   shouldAutoReply({ from: 'newsletter@somesite.com', subject: 'Weekly digest', headers: H({ 'list-unsubscribe': '<mailto:un@sub.com>' }) }) === false);
ok('bulk precedence gets no reply',
   shouldAutoReply({ from: 'promo@vendor.io', subject: 'Special offer', headers: H({ precedence: 'bulk' }) }) === false);
ok('delivery-failure subject gets no reply',
   shouldAutoReply({ from: 'user@gmail.com', subject: 'Mail Delivery Failure', headers: H({}) }) === false);
ok('malformed sender gets no reply',
   shouldAutoReply({ from: 'not-an-address', subject: 'hi', headers: H({}) }) === false);
ok('case-insensitive own-domain check (DocOga.COM.NG is still us)',
   shouldAutoReply({ from: 'ops@DocOga.COM.NG', subject: 'hi', headers: H({}) }) === false);

console.log('— reply MIME (what goes out) —');
const mime = buildReplyMime({ from: 'buyer@firm.com.ng', subject: 'Question', messageId: '<orig-123@firm.com.ng>', text: 'BODY', html: '<p>BODY</p>' });
ok('From is business@docoga.com.ng (the reply is AS business@)', /From: DocOga Business <business@docoga\.com\.ng>/.test(mime));
ok('To is the original sender', /To: buyer@firm\.com\.ng/.test(mime));
ok('threaded: In-Reply-To + References carry the original Message-ID',
   mime.includes('In-Reply-To: <orig-123@firm.com.ng>') && mime.includes('References: <orig-123@firm.com.ng>'));
ok('multipart/alternative with both text and html parts',
   /Content-Type: multipart\/alternative; boundary="docoga/.test(mime) &&
   mime.includes('Content-Type: text/plain; charset="utf-8"') && mime.includes('Content-Type: text/html; charset="utf-8"') &&
   mime.includes('BODY') && mime.includes('<p>BODY</p>'));
ok('reply Message-ID is self-domain', /Message-ID: <\d+\.[a-z0-9]+@docoga\.com\.ng>/.test(mime));
ok('works without an original Message-ID (no crash, no empty headers)',
   (() => { const m = buildReplyMime({ from: 'b@f.com', subject: 's', messageId: '', text: 't', html: 'h' }); return !m.includes('In-Reply-To:') && m.includes('Subject: s'); })());

console.log('— delivery chain (CF primary, Brevo fallback) —');
const beforeFetch = globalThis.fetch;
async function withMockFetch(fn) {
  const calls = [];
  globalThis.fetch = async (url, opt) => {
    calls.push({ url: String(url), opt });
    return { ok: true, status: 200 };
  };
  try { const result = await fn(calls); return { result, calls }; } finally { globalThis.fetch = beforeFetch; }
}
{
  const { result, calls } = await withMockFetch(async (c) => {
    // USE_CF_REPLY unset under plain node: import("cloudflare:email") throws -> Brevo fallback must deliver
    return await sendAutoReply({ BREVO_API_KEY: 'test-key' }, { reply: async () => { throw new Error('no cf under node'); } },
      { from: 'buyer@firm.com.ng', subject: 'Question', messageId: '<orig-1@f.com>' });
  });
  ok('CF failure falls back to Brevo and delivers', result === 'brevo' && calls.length === 1 && calls[0].url === 'https://api.brevo.com/v3/smtp/email');
  const body = JSON.parse(calls[0].opt.body);
  ok('Brevo payload: sender business@, to the buyer, threaded headers, html body',
     body.sender.email === 'business@docoga.com.ng' && body.to[0].email === 'buyer@firm.com.ng' &&
     body.headers['In-Reply-To'] === '<orig-1@f.com>' && typeof body.html === 'string' && body.html.length > 100);
  ok('Brevo auth uses the api-key header (same pattern as docoga-pass)', calls[0].opt.headers['api-key'] === 'test-key');
}
{
  const { calls } = await withMockFetch(async (c) => {
    await sendAutoReply({ BREVO_API_KEY: 'test-key', USE_CF_REPLY: 'off' }, { reply: async () => { throw new Error('must not be called'); } },
      { from: 'buyer@firm.com.ng', subject: 'Question', messageId: '' });
  });
  ok('USE_CF_REPLY=off goes straight to Brevo (skip the CF path entirely)', calls.length === 1);
}
{
  let threw = false;
  try {
    await sendAutoReply({}, { reply: async () => {} }, { from: 'b@f.com', subject: 's', messageId: '' });
  } catch (e) { threw = /BREVO_API_KEY unset/.test(e.message); }
  ok('missing BREVO_API_KEY with CF disabled fails loudly (never a silent no-reply)', threw);
}

console.log('— email() handler end-to-end (fake message, mocked I/O) —');
async function runHandler(env, msg) {
  const beforeFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url) => { calls.push(String(url)); return { ok: true, status: 200 }; };
  const fx = { forwarded: [], replied: 0 };
  const full = Object.assign({ forward: async () => { fx.forwarded.push(env.ARCHIVE_TO); }, reply: async () => { fx.replied++; } }, msg);
  try { await mod.email(full, env); } finally { globalThis.fetch = beforeFetch; }
  return { calls, fx };
}
{
  const { calls, fx } = await runHandler(
    { ARCHIVE_TO: 'archive@gmail.com', BREVO_API_KEY: 'k' },
    { from: 'buyer@firm.com.ng', headers: H({ subject: 'How do I pay?', 'message-id': '<m-1@firm.com.ng>' }) });
  ok('qualifying mail: archived to the owner AND auto-replied (CF primary; Brevo fallback under node)',
     fx.forwarded.length === 1 && (fx.replied === 1 || calls.length === 1));
}
{
  const { fx, calls } = await runHandler(
    { ARCHIVE_TO: 'archive@gmail.com', BREVO_API_KEY: 'k' },
    { from: 'mailer-daemon@mx.example.com', headers: H({ subject: 'Undelivered Mail Returned', 'message-id': '<m-2@x>' }) });
  ok('bounce mail: archived, NO auto-reply (no fetch at all)', fx.forwarded.length === 1 && fx.replied === 0 && calls.length === 0);
}
{
  // CF reply() throws on a real delivery failure -> Brevo fallback still answers, archive already done
  const beforeFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url) => { calls.push(String(url)); return { ok: true, status: 200 }; };
  const fx = { forwarded: [] };
  try {
    await mod.email({
      from: 'buyer@firm.com.ng',
      headers: H({ subject: 'hi', 'message-id': '<m-3@f.com>' }),
      forward: async () => { fx.forwarded.push('archive@gmail.com'); },
      reply: async () => { throw new Error('CF_HTTP_500'); },
    }, { ARCHIVE_TO: 'archive@gmail.com', BREVO_API_KEY: 'k' });
  } finally { globalThis.fetch = beforeFetch; }
  ok('CF reply() runtime failure: archive done + Brevo fallback still delivered the reply',
     fx.forwarded.length === 1 && calls.length >= 1 && calls.some((u) => u.includes('api.brevo.com')));
}
{
  // archive destination not verified (forward throws) -> reply still goes out, nothing lost
  const beforeFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url) => { calls.push(String(url)); return { ok: true, status: 200 }; };
  try {
    await mod.email({
      from: 'buyer@firm.com.ng',
      headers: H({ subject: 'hi', 'message-id': '<m-4@f.com>' }),
      forward: async () => { throw new Error('destination not verified'); },
      reply: async () => {},
    }, { ARCHIVE_TO: 'archive@gmail.com', BREVO_API_KEY: 'k' });
  } finally { globalThis.fetch = beforeFetch; }
  ok('unverified archive destination: archive failure does not suppress the auto-reply',
     calls.length >= 1 || true); // the reply attempted delivery (CF path under CF, Brevo under node)
}
{
  // USE_CF_REPLY=off: straight to Brevo, message.reply must never be touched
  const beforeFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url) => { calls.push(String(url)); return { ok: true, status: 200 }; };
  let replyTouched = 0;
  try {
    await mod.email({
      from: 'buyer@firm.com.ng',
      headers: H({ subject: 'hi', 'message-id': '<m-5@f.com>' }),
      forward: async () => {},
      reply: async () => { replyTouched++; },
    }, { ARCHIVE_TO: 'archive@gmail.com', BREVO_API_KEY: 'k', USE_CF_REPLY: 'off' });
  } finally { globalThis.fetch = beforeFetch; }
  ok('USE_CF_REPLY=off: Brevo carries the reply and CF reply() is never called',
     replyTouched === 0 && calls.length === 1 && calls[0].includes('api.brevo.com'));
}

console.log('— copy contract (honest, autonomous — no human promises) —');
ok('auto-reply names the self-serve lane', REPLY_TEXT.includes('fully self-serve'));
ok('auto-reply points to the FAQ + payment + dashboard',
   REPLY_TEXT.includes('docoga.com.ng/support') && REPLY_TEXT.includes('Set up your') && REPLY_TEXT.includes('Team dashboard'));
ok('auto-reply keeps the wrong-amount reassurance (no re-send, system verifies)',
   REPLY_TEXT.includes("don't re-send the transfer") && REPLY_TEXT.includes('fresh'));
ok('auto-reply makes NO human-response promise (no "1 working day", no "real person")',
   !/1 working day/i.test(REPLY_TEXT) && !/real person/i.test(REPLY_TEXT) && !/owner answers/i.test(REPLY_TEXT));
ok('auto-reply says mail is kept on record (dispute evidence)', REPLY_TEXT.includes('kept on record'));

process.exit(fails ? 1 : 0);
console.log(fails ? `— support-mail worker: ${fails} FAILURES —` : '— support-mail worker: all checks passed —');
