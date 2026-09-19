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
 *   GET  /verify?ids=a,b,c (or ?ref=X) — optional &prev=OLD links a top-up
 *                       (old code dies, remaining days roll into the new code)
 *                       Verifies payment identifiers (charge id / reference / tx_ref)
 *                       via Flutterwave v4 (OAuth) or Paystack API and returns the code.
 *   GET  /activate?code=X  Activation for ANY code (server-issued or offline batch).
 *                       Returns the SERVER expiry so every browser shares one synced
 *                       countdown. Optional &prev=OLD links a top-up on manual entry.
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

const PRICE_NGN = 2000; // Oga Pass price — proven end-to-end with real ₦100 rehearsal 19 Sep (logs/)
const ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

function makeCode() {
  const grp = () =>
    Array.from(crypto.getRandomValues(new Uint8Array(4)))
      .map((b) => ALPHA[b % ALPHA.length])
      .join("");
  return `OGA-${grp()}-${grp()}-${grp()}`;
}

/* FNV-1a — same algorithm as the site; validates offline-batch codes (unlock-codes.txt). */
function fnv1a(str){ let h=0x811c9dc5; for(let i=0;i<str.length;i++){ h^=str.charCodeAt(i); h=Math.imul(h,0x01000193)>>>0; } return h>>>0; }
const OFFLINE_HASHES = new Set("3d260bec,5422f3c7,3a5998f8,ed11779f,e07ad87a,28eda4d9,3b63966c,f142046e,8ce76209,b5044f89,01b7f119,591a90df,26f269f7,36fc62a2,d4c47cd8,9abd96b9,0094f361,86f21bd1,ed7d4b21,a1c06dd0,de00c669,d016062b,6d89dde0,71fe6e22,661d7c71,292aa934,6204dcc6,59dd44c9,56c4611d,251358c8,1b68b33b,437d11f4,50c7559e,7994e7db,e50fe950,6c87a93b,16f39498,27152284,26c064be,e5eb020e,aca6a617,a630bb83,6836e3c8,4858f309,98db7450,65a24cb7,bbd9728b,0f2522db,55804e40,6047fa66,16852ff2,87a400f3,734c51aa,57138c81,ddb2c042,b7b3e327,7b6ddea6,849a0ba6,eeccb007,fa03d49c,3f32e37f,72008561,70bd37d6,85874b8d,2bf8afff,d53f23d6,e2ea1e71,0637fea7,d657db78,faea3363,908ff0c0,06a80064,9286ab5e,d8f43c51,6b6a48f4,09aaab48,9e8b4f1d,1a45deca,24d7963e,bac6b3d9,12350627,494a8fb0,7c4ce14f,fcf87c21,7d6e8e1f,b2c5de33,95b7e3d7,db28e5bb,d7b748f2,9ca426f5,daeb9d6c,ae6bb231,94506965,d9a00c33,94c1b9a1,a25b705d,fe008395,37a2c744,31948af4,16fbd583,6d83b92d,b248e856,1eda74b3,16d32ca4,e1658ff0,079ab2e1,f95f3542,c4760957,3994bbad,11598317,ea8bb709,4da99fc8,a52aba3e,0380b946,693ed896,97f5ddbd,9d61b62b,08439e56,eb10cb71,b2ffafaa,ae374839,1305e3cf,c60ff85b,06d10b00,8c69a2b5,4f360266,807152b7,43c7f7b9,94ac6215,00e1018c,65062983,d93e5b52,2a9f55fe,6f5acddd,394c2517,3c3b89e0,398c78af,0223d98f,8a59787c,a8cc69be,44b06563,e3a0c804,53723b64,a7ee170c,37263ab1,bf348816,b8dac4e2,ed06edee,41029d44,d64cc342,e45bdc89,d93e457c,b50cf207,02774534,e1bb8ce2,d05aee1b,93af2bd3,b864c47b,753ab5c8,9cb513f7,516b42ef,27874e42,98875df4,0fc39c84,2045fc75,a9136bb3,66aed5da,0332d980,6d3c9326,6a4db4b6,b61e8046,18a733f7,40851103,a381429b,b91326e9,111c54ed,3d87395f,b6150aea,c2354a29,febc17d6,62093159,b5fc0ecb,abd4ab73,a5d98a23,fd1c84fd,82706c2d,95fd1880,6f44e916,d5b3063f,71d97827,e2971566,4185e412,58f8bb07,f146b7da,baf98c07,82627517,c279ac37,87486faf,f1804bfc,d3fe4ec0".split(","));

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
  const rec = { code, email: email || "", ref: ref || "", issuedAt: Date.now(), used: false, source: "online", exp: Date.now() + 30 * 864e5 }; // dies 30 days from purchase
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
  try { await env.KV.put("debug:last-webhook", raw); await env.KV.put("debug:last-webhook-ts", String(Date.now())); } catch (e) {} // vitals for /health — safe: only valid-signed webhooks reach this
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
    if (existing) return json({ ok: true, ...(await finalizeCode(env, existing, url.searchParams.get("prev"))) }, cors);
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
    return json({ ok: true, ...(await finalizeCode(env, code, url.searchParams.get("prev"))) }, cors);
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
  return json({ ok: true, ...(await finalizeCode(env, code, url.searchParams.get("prev"))) }, cors);
}

/* ---------- Online activation for server-issued codes ---------- */
/* ---------- Pass model (owner spec, 19 Sep): ONE synced expiry ----------
 * - A code dies 30 days from purchase (online: payment moment; offline batch:
 *   first activation, since those sales happen on WhatsApp).
 * - /activate returns the server expiry -> every browser continues from the
 *   same remaining days (day 7 on Chrome = day 7 on Firefox).
 * - Topping up (?prev=OLD) links the codes: OLD dies instantly, its remaining
 *   days roll into NEW's 30 days. The newest code is the source of truth. */

function normalizeCode(raw) {
  const m = String(raw).match(/^(OGA)([A-Z2-9]{4})([A-Z2-9]{4})([A-Z2-9]{4})$/);
  return m ? m[1] + "-" + m[2] + "-" + m[3] + "-" + m[4] : String(raw);
}
async function readCode(env, key) {
  const s = await env.KV.get("code:" + key);
  if (!s) return null;
  try { return JSON.parse(s); } catch (e) { return null; }
}
/* Top-up linking: OLD code dies, its remaining days carry into NEW. Idempotent. */
async function linkPrev(env, rec, prevRaw) {
  if (!prevRaw || rec.prev) return rec;
  const pKey = normalizeCode(String(prevRaw).toUpperCase().replace(/[\s-]/g, ""));
  if (pKey === rec.code) return rec;
  const prev = await readCode(env, pKey); // read-only: never auto-create when linking
  if (!prev || prev.succ || !prev.exp) return rec;
  if (prev.exp > Date.now()) rec.exp = prev.exp + 30 * 864e5; // remaining days roll over
  if (Array.isArray(prev.devices) && prev.devices.length) rec.devices = prev.devices.slice(); // the fence survives renewals
  rec.prev = prev.code;
  prev.succ = rec.code;
  try {
    await env.KV.put("code:" + rec.code, JSON.stringify(rec));
    await env.KV.put("code:" + prev.code, JSON.stringify(prev));
  } catch (e) {}
  return rec;
}
/* Ensure exp exists (legacy records), apply linking, return {code, exp}. */
async function finalizeCode(env, codeStr, prevRaw) {
  const key = normalizeCode(String(codeStr).toUpperCase().replace(/[\s-]/g, ""));
  let rec = await readCode(env, key);
  if (!rec && key !== key.replace(/-/g, "")) rec = await readCode(env, key.replace(/-/g, ""));
  if (!rec) return { code: codeStr };
  if (!rec.exp) {
    rec.exp = (rec.firstUsed || rec.issuedAt || Date.now()) + 30 * 864e5;
    try { await env.KV.put("code:" + rec.code, JSON.stringify(rec)); } catch (e) {}
  }
  if (!rec.succ) rec = await linkPrev(env, rec, prevRaw);
  return { code: rec.code, exp: rec.exp };
}

async function handleActivate(url, env, cors) {
  const raw = (url.searchParams.get("code") || "").toUpperCase().replace(/[\s-]/g, "");
  if (!raw) return json({ ok: false, error: "code required" }, cors, 400);
  const key = normalizeCode(raw);
  let rec = await readCode(env, key);
  if (!rec && key !== raw) rec = await readCode(env, raw);
  if (!rec) {
    // Unknown to KV: maybe an offline-batch code (unlock-codes.txt) on first use.
    if (OFFLINE_HASHES.has(fnv1a(raw).toString(16).padStart(8, "0"))) {
      rec = { code: key, email: "", ref: "", issuedAt: Date.now(), used: false, source: "offline", exp: Date.now() + 30 * 864e5 };
      await env.KV.put("code:" + key, JSON.stringify(rec)); // clock starts at first activation
    } else {
      return json({ ok: false, error: "invalid code" }, cors, 404);
    }
  }
  if (!rec.exp) { // legacy record (pre unified-expiry model) — migrate on touch
    rec.exp = (rec.firstUsed || rec.issuedAt || Date.now()) + 30 * 864e5;
    try { await env.KV.put("code:" + rec.code, JSON.stringify(rec)); } catch (e) {}
  }
  if (rec.succ) { // topped up: the newest code is the source of truth
    const succ = await readCode(env, normalizeCode(String(rec.succ).toUpperCase().replace(/[\s-]/g, "")));
    return json({ ok: false, error: "This code was renewed — your newest code is the active one.", renewedCode: rec.succ, exp: succ && succ.exp }, cors, 410);
  }
  if (Date.now() > rec.exp)
    return json({ ok: false, error: "This code has expired — buy a new Oga Pass (₦2,000)." }, cors, 403);
  // Device fairness gate: one pass, up to 3 devices (phone + laptop + spare).
  // A 4th device gets a friendly wall instead of a free ride. Missing/invalid
  // did is never blocked (backward compatible). One KV write per NEW device.
  const did = (url.searchParams.get("did") || "").trim().slice(0, 32);
  if (did && /^[A-Za-z0-9_-]+$/.test(did)) {
    if (!Array.isArray(rec.devices)) rec.devices = [];
    if (!rec.devices.includes(did)) {
      if (rec.devices.length >= 3)
        return json({ ok: false, error: "This pass is already active on 3 devices. Oga Pass is one-person — your own is just ₦2,000 at docoga.com.ng, or tap WhatsApp support if this is your own new device." }, cors, 403);
      rec.devices.push(did);
      if (rec.devices.length > 8) rec.devices = rec.devices.slice(-8);
      try { await env.KV.put("code:" + rec.code, JSON.stringify(rec)); } catch (e) {}
    }
  }
  rec = await linkPrev(env, rec, url.searchParams.get("prev"));
  return json({ ok: true, code: rec.code, exp: rec.exp }, cors);
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
      if (url.pathname === "/") {
      let lw = null;
      try { const ts = await env.KV.get("debug:last-webhook-ts", { cacheTtl: 60 }); if (ts) lw = Math.round((Date.now() - Number(ts)) / 60000); } catch (e) {}
      return json({ ok: true, service: "docoga-pass", lastWebhookMinutesAgo: lw, priceNGN: PRICE_NGN }, cors);
    }
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
