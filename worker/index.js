/**
 * DocOga Pass Automation — Cloudflare Worker
 * The "little server" that issues unlock codes automatically when money lands.
 *
 * Endpoints:
 *   POST /issue         Bridge for Selar→Zapier/Make (auth: X-DocOga-Key header)
 *                       Body: {"email":"buyer@mail.com","ref":"optional-sale-id"}
 *                       → generates a unique code, stores it in KV, emails the buyer.
 *   POST /flw-webhook   Flutterwave webhook (auth: v3 verif-hash OR v4 flutterwave-signature HMAC)
 *                       → verifies amount & status, issues + emails code, aliases it under
 *                       every id (reference/tx_ref/id) so /verify matches. Idempotent.
 *   GET  /verify?ids=a,b,c (or ?ref=X)
 *                       Verifies payment identifiers (charge id / reference / tx_ref)
 *                       via Flutterwave v4 (OAuth) or Paystack API and returns the code.
 *   GET  /activate?code=X  Online activation check for server-issued codes
 *                       (the site calls this as a fallback when a code isn't in the offline list).
 *
 * Free-tier capacity: Workers 100k req/day · KV 1k writes/day · Resend 3k emails/month.
 *
 * Setup (secrets — set in Cloudflare dashboard → Worker → Settings → Variables):
 *   ISSUE_SECRET        shared secret for /issue (you invent it, e.g. a long random string)
 *   FLW_CLIENT_ID       Flutterwave v4 Client ID (new accounts: live keys are v4-only)
 *   FLW_CLIENT_SECRET   Flutterwave v4 Client Secret
 *   FLW_SECRET_KEY      Flutterwave classic SECRET key (legacy v3 accounts only)
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

/* ---------- Flutterwave webhook — PRIMARY instant-delivery path for payment links ---------- */
/* Accepts BOTH shapes: classic v3 (event + verif-hash header) and v4
 * (type + flutterwave-signature = HMAC-SHA256(rawBody, secretHash) base64).
 * Stores the issued code under EVERY identifier (reference / tx_ref / id)
 * so the success page's /verify matches whichever the redirect carries. */
async function flwHmacMatches(raw, signature, secret) {
  if (!signature || !secret) return false;
  try {
    const enc = new TextEncoder();
    const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    const mac = await crypto.subtle.sign("HMAC", key, enc.encode(raw));
    let bin = "";
    const bytes = new Uint8Array(mac);
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin) === signature;
  } catch (e) {
    return false;
  }
}

async function handleFlwWebhook(request, env, cors) {
  const raw = await request.text();
  const v3ok = !!(env.FLW_WEBHOOK_HASH && request.headers.get("verif-hash") === env.FLW_WEBHOOK_HASH);
  const v4ok = await flwHmacMatches(raw, request.headers.get("flutterwave-signature"), env.FLW_WEBHOOK_HASH || "");
  if (!v3ok && !v4ok) return new Response("forbidden", { status: 403 });
  let body = null;
  try { body = JSON.parse(raw); } catch (e) {}
  if (!body) return new Response("bad request", { status: 400 });
  const d = body.data || {};
  const isCompleted = body.type === "charge.completed" || body.event === "charge.completed";
  const succeeded = d.status === "succeeded" || d.status === "successful";
  const amt = d.amount && typeof d.amount === "object" ? Number(d.amount.value) : Number(d.amount);
  const paid = isCompleted && succeeded && d.currency === "NGN" && amt >= PRICE_NGN;
  if (!paid) return new Response("ignored", { status: 200 });
  const ids = [d.reference, d.tx_ref, d.id].filter((x) => x !== undefined && x !== null && String(x).length > 0).map(String);
  const ref = ids[0] || String(Date.now());
  const existing = await env.KV.get("ref:" + ref);
  if (existing) return new Response("ok", { status: 200 });
  const code = await issueCode(env, { email: (d.customer && d.customer.email) || "", ref });
  for (const id of ids.slice(1)) {
    if (id !== ref) await env.KV.put("ref:" + id, code);
  }
  return new Response("ok", { status: 200 });
}

/* ---------- Flutterwave v4 (OAuth) helpers ---------- */
const FLW4_TOKEN_URL = "https://idp.flutterwave.com/realms/flutterwave/protocol/openid-connect/token";
const FLW4_BASE = "https://f4bexperience.flutterwave.com";

async function flw4Token(env) {
  const cached = await env.KV.get("flw4:token");
  if (cached) {
    try {
      const t = JSON.parse(cached);
      if (t.exp > Date.now() + 60000) return t.token;
    } catch (e) {}
  }
  const body = new URLSearchParams({
    client_id: env.FLW_CLIENT_ID,
    client_secret: env.FLW_CLIENT_SECRET,
    grant_type: "client_credentials",
  });
  const r = await fetch(FLW4_TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const j = await r.json().catch(() => ({}));
  if (!j.access_token) throw new Error("could not obtain v4 access token");
  try {
    await env.KV.put("flw4:token", JSON.stringify({ token: j.access_token, exp: Date.now() + (j.expires_in || 600) * 1000 }));
  } catch (e) {}
  return j.access_token;
}

async function flw4GetCharge(env, idOrRef) {
  const token = await flw4Token(env);
  const headers = {
    Authorization: "Bearer " + token,
    "Content-Type": "application/json",
    "X-Trace-Id": "docoga-verify-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8),
  };
  // 1) Direct charge-id lookup (chg_...)
  if (/^chg_/i.test(idOrRef)) {
    const r = await fetch(FLW4_BASE + "/charges/" + encodeURIComponent(idOrRef), { headers });
    const j = await r.json().catch(() => null);
    if (j && j.data) return j.data;
  }
  // 2) Lookup by merchant reference
  const r2 = await fetch(
    FLW4_BASE + "/charges?reference=" + encodeURIComponent(idOrRef) + "&page=1&size=10",
    { headers }
  );
  const j2 = await r2.json().catch(() => null);
  if (j2 && Array.isArray(j2.data) && j2.data.length) return j2.data[0];
  return null;
}

function flw4Paid(c) {
  if (!c || c.status !== "succeeded" || c.currency !== "NGN") return false;
  const amt = c.amount && typeof c.amount === "object" ? Number(c.amount.value) : Number(c.amount);
  return amt >= PRICE_NGN;
}

/* ---------- Verify a payment (called by success.html) — ?ids=a,b,c or ?ref=X ---------- */
async function handleVerify(url, env, cors) {
  const idsParam = url.searchParams.get("ids") || url.searchParams.get("ref");
  if (!idsParam) return json({ ok: false, error: "ref required" }, cors, 400);
  const ids = [...new Set(idsParam.split(",").map((s) => s.trim()).filter(Boolean))].slice(0, 8);
  if (!ids.length) return json({ ok: false, error: "ref required" }, cors, 400);

  // Idempotency: any known id returns the already-issued code.
  for (const id of ids) {
    const existing = await env.KV.get("ref:" + id);
    if (existing) return json({ ok: true, code: existing }, cors);
  }

  const provider = String(env.PROVIDER || "flw").toLowerCase();

  // Primary: Flutterwave v4 (OAuth Client ID + Secret)
  if (provider === "flw" && env.FLW_CLIENT_ID && env.FLW_CLIENT_SECRET) {
    let charge = null, matched = null;
    try {
      for (const id of ids) {
        charge = await flw4GetCharge(env, id);
        if (charge) { matched = id; break; }
      }
    } catch (e) {
      return json({ ok: false, error: "verification error: " + e.message }, cors, 502);
    }
    if (!flw4Paid(charge))
      return json({ ok: false, error: "payment not found or not successful yet" }, cors, 402);
    const code = await issueCode(env, { email: "", ref: matched });
    return json({ ok: true, code }, cors);
  }

  // Fallback: legacy v3 (Paystack / classic Flutterwave secret key)
  const ref = ids[0];
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
