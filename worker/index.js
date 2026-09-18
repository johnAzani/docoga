/**
 * DocOga Pass Automation — Cloudflare Worker
 * The "little server" that issues unlock codes automatically when money lands.
 *
 * Endpoints:
 *   POST /issue         Bridge for Selar→Zapier/Make (auth: X-DocOga-Key header)
 *                       Body: {"email":"buyer@mail.com","ref":"optional-sale-id"}
 *                       → generates a unique code, stores it in KV, emails the buyer.
 *   POST /flw-webhook   Flutterwave webhook (auth: verif-hash header, set in FLW dashboard)
 *                       → verifies amount & status, issues + emails code. Idempotent.
 *   GET  /verify?ref=X  Verifies a payment reference via Flutterwave or Paystack API
 *                       and returns the code (creates it if first time). Used by success.html.
 *   GET  /activate?code=X  Online activation check for server-issued codes
 *                       (the site calls this as a fallback when a code isn't in the offline list).
 *
 * Free-tier capacity: Workers 100k req/day · KV 1k writes/day · Resend 3k emails/month.
 *
 * Setup (secrets — set in Cloudflare dashboard → Worker → Settings → Variables):
 *   ISSUE_SECRET        shared secret for /issue (you invent it, e.g. a long random string)
 *   FLW_SECRET_KEY      Flutterwave SECRET key (Path B)
 *   FLW_WEBHOOK_HASH    Flutterwave webhook secret hash (optional if using redirect+verify)
 *   PAYSTACK_SECRET_KEY Paystack secret key (Path C — after CAC)
 *   PROVIDER            "flw" (default) or "paystack" — which API /verify should call
 *   RESEND_API_KEY      free key from resend.com (email delivery — optional)
 *   MAIL_FROM           e.g. "DocOga <passes@docoga.com.ng>" (requires verified domain in Resend)
 *   SITE_URL            e.g. https://docoga.com.ng (used inside the email)
 * KV binding: must be named KV (see wrangler.toml)
 */

const PRICE_NGN = 2000; // change if you change the pass price
const ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

function makeCode() {
  const grp = () =>
    Array.from(crypto.getRandomValues(new Uint8Array(4)))
      .map((b) => ALPHA[b % ALPHA.length])
      .join("");
  return `OGA-${grp()}-${grp()}-${grp()}`;
}

function json(obj, cors, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...cors },
  });
}

async function emailCode(env, to, code) {
  if (!env.RESEND_API_KEY || !to) return;
  const from = env.MAIL_FROM || "DocOga <onboarding@resend.dev>";
  const site = env.SITE_URL || "https://docoga.com.ng";
  await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from,
      to,
      subject: "Your DocOga Oga Pass code",
      text:
        `Thank you for your purchase!\n\n` +
        `Your Oga Pass code: ${code}\n\n` +
        `How to use it:\n` +
        `1. Open ${site}\n` +
        `2. Tap "FREE PLAN" at the top\n` +
        `3. Paste this code and tap Activate\n\n` +
        `Clean, watermark-free documents unlocked for 30 days.\n\n` +
        `Keep this email. Screenshot the code for safekeeping.\n\n` +
        `— The DocOga Team, Abuja, Nigeria`,
    }),
  });
}

/** Create a code, remember it in KV, email the buyer. Returns the code. */
async function issueCode(env, { email, ref }) {
  const code = makeCode();
  const rec = { code, email: email || "", ref: ref || "", issuedAt: Date.now(), used: false };
  await env.KV.put("code:" + code, JSON.stringify(rec));
  if (ref) await env.KV.put("ref:" + ref, code); // idempotency: ref -> code
  try { await emailCode(env, email, code); } catch (e) { /* email failure must not break issuing */ }
  return code;
}

/* ---------- Selar → Zapier/Make bridge ---------- */
async function handleIssue(request, env, cors) {
  if (!env.ISSUE_SECRET || request.headers.get("x-docoga-key") !== env.ISSUE_SECRET)
    return json({ ok: false, error: "unauthorized" }, cors, 401);
  const body = await request.json().catch(() => ({}));
  const email = String(body.email || "").trim();
  const ref = String(body.ref || body.saleId || body.sale_id || "") || "selar-" + Date.now();
  if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))
    return json({ ok: false, error: "valid buyer email required" }, cors, 400);
  const existing = await env.KV.get("ref:" + ref);
  const code = existing || (await issueCode(env, { email, ref }));
  return json({ ok: true, code, alreadyIssued: !!existing }, cors);
}

/* ---------- Flutterwave webhook (optional — redirect+verify also works) ---------- */
async function handleFlwWebhook(request, env, cors) {
  if (!env.FLW_WEBHOOK_HASH || request.headers.get("verif-hash") !== env.FLW_WEBHOOK_HASH)
    return new Response("forbidden", { status: 403 });
  const body = await request.json().catch(() => null);
  if (!body) return new Response("bad request", { status: 400 });
  const d = body.data || {};
  const paid =
    (body.event === "charge.completed" || d.status === "successful") &&
    d.status === "successful" &&
    d.currency === "NGN" &&
    Number(d.amount) >= PRICE_NGN;
  if (!paid) return new Response("ignored", { status: 200 });
  const ref = d.tx_ref || String(d.id || Date.now());
  const existing = await env.KV.get("ref:" + ref);
  if (!existing)
    await issueCode(env, { email: (d.customer && d.customer.email) || "", ref });
  return new Response("ok", { status: 200 });
}

/* ---------- Verify a payment reference (called by success.html) ---------- */
async function handleVerify(url, env, cors) {
  const ref = url.searchParams.get("ref");
  if (!ref) return json({ ok: false, error: "ref required" }, cors, 400);

  const existing = await env.KV.get("ref:" + ref);
  if (existing) return json({ ok: true, code: existing }, cors);

  const provider = String(env.PROVIDER || "flw").toLowerCase();
  let paid = false;
  let buyerEmail = url.searchParams.get("email") || "";

  try {
    if (provider === "paystack" && env.PAYSTACK_SECRET_KEY) {
      const r = await fetch(
        `https://api.paystack.co/transaction/verify/${encodeURIComponent(ref)}`,
        { headers: { Authorization: `Bearer ${env.PAYSTACK_SECRET_KEY}` } }
      );
      const j = await r.json().catch(() => ({}));
      paid =
        j && j.data && j.data.status === "success" &&
        j.data.currency === "NGN" && j.data.amount / 100 >= PRICE_NGN;
      buyerEmail = (j.data && j.data.customer && j.data.customer.email) || buyerEmail;
    } else if (env.FLW_SECRET_KEY) {
      const r = await fetch(
        `https://api.flutterwave.com/v3/transactions/verify_by_reference?tx_ref=${encodeURIComponent(ref)}`,
        { headers: { Authorization: `Bearer ${env.FLW_SECRET_KEY}` } }
      );
      const j = await r.json().catch(() => ({}));
      paid =
        j && j.data && j.data.status === "successful" &&
        j.data.currency === "NGN" && Number(j.data.amount) >= PRICE_NGN;
      buyerEmail = (j.data && j.data.customer && j.data.customer.email) || buyerEmail;
    }
  } catch (e) {
    return json({ ok: false, error: "verification error: " + e.message }, cors, 502);
  }

  if (!paid)
    return json({ ok: false, error: "payment not found or not successful yet" }, cors, 402);

  const code = await issueCode(env, { email: buyerEmail, ref });
  return json({ ok: true, code }, cors);
}

/* ---------- Online activation for server-issued codes ---------- */
async function handleActivate(url, env, cors) {
  const raw = (url.searchParams.get("code") || "").toUpperCase().replace(/[\s-]/g, "");
  if (!raw) return json({ ok: false, error: "code required" }, cors, 400);
  // KV stores codes in dashed form (OGA-XXXX-XXXX-XXXX) — rebuild from the stripped form.
  let key = raw;
  const m = raw.match(/^(OGA)([A-Z2-9]{4})([A-Z2-9]{4})([A-Z2-9]{4})$/);
  if (m) key = m[1] + "-" + m[2] + "-" + m[3] + "-" + m[4];
  let rec = await env.KV.get("code:" + key);
  if (!rec && key !== raw) rec = await env.KV.get("code:" + raw);
  if (!rec) return json({ ok: false, error: "invalid code" }, cors, 404);
  // Re-activation allowed (buyer may switch device) — we just track usage stats.
  try {
    const data = JSON.parse(rec);
    data.used = true;
    data.usedAt = Date.now();
    await env.KV.put("code:" + code, JSON.stringify(data));
  } catch (e) {}
  return json({ ok: true }, cors);
}

/* ---------- router ---------- */
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Content-Type,X-DocOga-Key",
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    try {
      if (url.pathname === "/") return json({ ok: true, service: "docoga-pass" }, cors);
      if (url.pathname === "/issue" && request.method === "POST") return await handleIssue(request, env, cors);
      if (url.pathname === "/flw-webhook" && request.method === "POST") return await handleFlwWebhook(request, env, cors);
      if (url.pathname === "/verify" && request.method === "GET") return await handleVerify(url, env, cors);
      if (url.pathname === "/activate" && request.method === "GET") return await handleActivate(url, env, cors);
      return json({ ok: false, error: "not found" }, cors, 404);
    } catch (e) {
      return json({ ok: false, error: String((e && e.message) || e) }, cors, 500);
    }
  },
};
