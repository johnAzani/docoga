/**
 * DocOga Pass Automation — Cloudflare Worker
 * The "little server" that issues unlock codes automatically when money lands.
 *
 * Endpoints:
 *   POST /issue         Bridge for Selar→Zapier/Make (auth: X-DocOga-Key header)
 *                       Body: {"email":"buyer@mail.com","ref":"optional-sale-id"}
 *                       → generates a unique code, stores it in KV, emails the buyer.
 *   POST /resend-email  No-charge resend by stored purchase reference; sends only to
 *                       the stored email, returns no code, disabled unless
 *                       RESEND_EMAIL_ENABLED is exactly "true".
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
 *   POST /business/waitlist  Self-serve "notify me at launch" for the Business tier
 *                       (Phase 0, 11 Oct 2026 — replaces the retired quote-by-WhatsApp
 *                       CTA). Body: {email, company?, segment?}. Dedupes on email,
 *                       3/IP/day rate guard, best-effort confirmation email.
 *   POST /business/login     Team magic-link request {email} → one-time 10-min token
 *                       emailed. 503 team_auth_disabled until TEAM_AUTH_SECRET set.
 *   GET  /business/login?token=…  Verify magic link → 30-day stateless HMAC session
 *                       (Authorization: Bearer). KV re-checked on EVERY call, so
 *                       revoked seats / expired teams die immediately.
 *   GET  /business/team       Signed-in team: seats (owner sees all, member self),
 *                       brand (name/address/logo/footer) for branded rendering.
 *   PUT  /business/team/brand  Owner: firm name/address/footer + logo data-URI
 *                       (PNG/JPG/SVG ≤25KB, re-validated server-side).
 *   POST /business/team/seats  Owner: {action:"invite"|"revoke", email, name?} —
 *                       invite emails a magic link; revoke is immediate.
 *   POST /business/teams       Self-serve team creation (Phase 2, 11 Oct):
 *                       {email, name, seats, docs, segment?} → UNPAID team +
 *                       owner seat + magic link. Price = PUBLISHED formula
 *                       (§6.1) recomputed server-side; client never sends price.
 *   POST /business/team/charge Owner: {method:"transfer"|"card"} → invoice +
 *                       Flutterwave dynamic VA (bank transfer, PRIMARY — vendor
 *                       expiry honoured, re-issue on expiry) or v4 hosted
 *                       "generic" charge (card, P3).
 *   /flw-webhook (extended)    charge.completed that matches an invoice
 *                       reference activates the team (annual, +365 days);
 *                       wrong amount → VA voided + fresh VA + email (§7.4);
 *                       idempotent; retail pass path untouched.
 *   GET  /business/team/invoices  Portal: team invoice list (12-month window).
 *   GET  /business/invoice/:id    C10 (Phase 3): authoritative invoice as a
 *                       printable HTML document (print → Save as PDF in the
 *                       browser — no PDF lib, ₦0; binary .pdf is a v2 upgrade
 *                       if teams demand attachments). Any seat of the team;
 *                       other teams' ids are 404 (no enumeration).
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
 *   MAIL_FROM           optional sender identity; must be verified by active mail provider
 *   RESEND_EMAIL_ENABLED set exactly to "true" only after authenticating the sender
 *   TEAM_AUTH_SECRET    long random string (secret) — required for /business/login*
 *                       and /business/team*; unset = 503 team_auth_disabled (fail-closed)
 *   SITE_URL            e.g. https://docoga.com.ng (used inside the email)
 * KV binding: must be named KV (see wrangler.toml)
 */

// ₦2,000 is the minimum qualifying Oga Pass payment. The 19 Sep ₦100 rehearsal
// was below this gate and did not test code issuance.
const PRICE_NGN = 2000;
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

/* ---------- Email delivery (provider chain: Brevo > SMTP2GO > Resend) ---------- */
async function sendMail(env, to, subject, text, html) {
  if (!to) throw new Error("MAIL_NO_RECIPIENT");
  if (env.BREVO_API_KEY) {
    const from = env.MAIL_FROM || "DocOga <noreply@docoga.com.ng>";
    const m = from.match(/^(.*?)\s*<(.+)>$/) || [null, "DocOga", from];
    const response = await fetch("https://api.brevo.com/v3/smtp/email", {
      method: "POST",
      headers: { "api-key": env.BREVO_API_KEY, "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ sender: { name: m[1] || "DocOga", email: m[2] }, to: [{ email: to }], subject, textContent: text, htmlContent: html }),
    });
    if (!response.ok) throw new Error(`BREVO_HTTP_${response.status}`);
    console.info(`[docoga-mail] provider=brevo accepted http=${response.status}`);
    return;
  }
  if (env.SMTP2GO_API_KEY) {
    const response = await fetch("https://api.smtp2go.com/v3/email/send", {
      method: "POST",
      headers: { "x-smtp2go-api-key": env.SMTP2GO_API_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({ sender: env.MAIL_FROM || "DocOga <noreply@docoga.com.ng>", to: [to], subject, text_body: text, html_body: html }),
    });
    if (!response.ok) throw new Error(`SMTP2GO_HTTP_${response.status}`);
    console.info(`[docoga-mail] provider=smtp2go accepted http=${response.status}`);
    return;
  }
  if (env.RESEND_API_KEY) {
    const response = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ from: env.MAIL_FROM || "DocOga <noreply@docoga.com.ng>", to, subject, text, html }),
    });
    if (!response.ok) throw new Error(`RESEND_HTTP_${response.status}`);
    console.info(`[docoga-mail] provider=resend accepted http=${response.status}`);
    return;
  }
  throw new Error("MAIL_NO_PROVIDER");
}

function safeMailFailureReason(error) {
  const message = String(error && error.message || "");
  if (/^(BREVO|SMTP2GO|RESEND)_HTTP_[1-5][0-9]{2}$/.test(message)) return message;
  if (message === "MAIL_NO_RECIPIENT" || message === "MAIL_NO_PROVIDER") return message;
  return "MAIL_NETWORK_ERROR";
}

function mailShell(inner) {
  return `<!DOCTYPE html><html><body style="margin:0;padding:0;background:#F5F7FB;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">` +
  `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F5F7FB;padding:16px 8px;"><tr><td align="center">` +
  `<table role="presentation" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid #DCE4F0;">` +
  `<tr><td style="background:#0040E0;padding:0;">` +
  `<img src="https://docoga-pass.johnazani.workers.dev/assets/email-banner.jpg" width="600" alt="DocOga — Your Documents. Our Priority." style="display:block;width:100%;height:auto;border:0;">` +
  `</td></tr>` +
  `<tr><td style="padding:28px;">` + inner +
  `</td></tr>` +
  `<tr><td style="background:#F0F4FA;padding:16px 28px;border-top:1px solid #DCE4F0;">` +
  `<p style="margin:0;font-size:12px;color:#5B6B85;line-height:1.5;">DocOga — free Nigerian document tools: tenancy agreement, notice to quit, rent receipt, invoice, employment contract, caution fee, letter of demand, payslip, warning letter, power of attorney.<br>Abuja, Nigeria · <a href="https://docoga.com.ng" style="color:#0040E0;">docoga.com.ng</a></p>` +
  `</td></tr></table></td></tr></table></body></html>`;
}

async function emailCode(env, to, code) {
  if (!to) throw new Error("MAIL_NO_RECIPIENT");
  const site = env.SITE_URL || "https://docoga.com.ng";
  const link = `${site}/#code=${code}`;
  const subject = "Your DocOga Oga Pass — tap to activate";
  const text =
    `Thank you for your purchase!\n\n` +
    `ACTIVATE ON ANY DEVICE — tap this link:\n${link}\n\n` +
    `Your pass code (if you ever need to type it): ${code}\n\n` +
    `What you got: clean, watermark-free documents for 30 days — all 10 tools, including Power of Attorney.\n\n` +
    `Keep this email — the link keeps working for the whole life of your pass.\n\n` +
    `Need help? WhatsApp us: +234 902 185 2845\n\n` +
    `— The DocOga Team, Abuja, Nigeria`;
  const inner =
  `<p style="margin:0 0 14px;font-size:17px;color:#141F33;font-weight:700;">Thank you for your purchase! 🎉</p>` +
  `<p style="margin:0 0 20px;font-size:15px;color:#37455E;line-height:1.6;">Your <b>Oga Pass</b> is ready — <b>all 10 document tools, including Power of Attorney</b>, clean and watermark-free, for <b>30 days</b>.</p>` +
  `<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 8px;"><tr>` +
  `<td style="background:#0040E0;border-radius:10px;">` +
  `<a href="${link}" style="display:inline-block;padding:15px 34px;font-size:16px;font-weight:800;color:#ffffff;text-decoration:none;">Activate my pass →</a>` +
  `</td></tr></table>` +
  `<p style="margin:0 0 18px;font-size:13px;color:#5B6B85;text-align:center;">Tap the button on any of your devices — DocOga opens already unlocked.</p>` +
  `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px;"><tr>` +
  `<td style="background:#F0F4FA;border:1px dashed #B9C7E4;border-radius:10px;padding:14px;text-align:center;">` +
  `<span style="font-size:11px;color:#5B6B85;letter-spacing:1px;">PREFER TO TYPE IT? YOUR PASS CODE</span><br>` +
  `<span style="font-size:20px;font-weight:800;color:#0040E0;letter-spacing:2px;">${code}</span>` +
  `</td></tr></table>` +
  `<p style="margin:0 0 8px;font-size:13.5px;color:#37455E;line-height:1.6;"><b>Keep this email.</b> The button and the code keep working for the whole life of your pass — on up to 3 devices.</p>` +
  `<p style="margin:0;font-size:13.5px;color:#37455E;line-height:1.6;">Need help? WhatsApp us: <b>+234 902 185 2845</b></p>`;
  await sendMail(env, to, subject, text, mailShell(inner));
}

/* ---------- Day-27 automatic renewal reminder (cron, no charge without buyer tap) ---------- */
function fmtD(ts) {
  try { return new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }); }
  catch (e) { return new Date(ts).toISOString().slice(0, 10); }
}
async function emailRenewalReminder(env, to, code, exp) {
  const site = env.SITE_URL || "https://docoga.com.ng";
  const pay = env.PAYMENT_URL || "https://flutterwave.com/pay/ynznvgof2r21";
  const link = `${site}/#code=${code}`;
  const when = fmtD(exp);
  const subject = "Your DocOga Oga Pass expires on " + when + " — one tap renews it";
  const text =
    `Your Oga Pass expires on ${when}.\n\n` +
    `RENEW IN ONE TAP:\n${pay}\n\n` +
    `Renew before it expires and your remaining days stack on top of the new 30 — you never lose money.\n\n` +
    `Haven't activated your current pass yet? Tap your magic link:\n${link}\n\n` +
    `Questions? WhatsApp us: +234 902 185 2845\n\n` +
    `— The DocOga Team, Abuja, Nigeria`;
  const inner =
  `<p style="margin:0 0 14px;font-size:17px;color:#141F33;font-weight:700;">Your Oga Pass expires on ${when}</p>` +
  `<p style="margin:0 0 20px;font-size:15px;color:#37455E;line-height:1.6;">Renew in one tap and keep making clean, watermark-free documents with all 10 tools, including Power of Attorney.</p>` +
  `<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 8px;"><tr>` +
  `<td style="background:#0040E0;border-radius:10px;">` +
  `<a href="${pay}" style="display:inline-block;padding:15px 34px;font-size:16px;font-weight:800;color:#ffffff;text-decoration:none;">Renew my pass — ₦2,000 →</a>` +
  `</td></tr></table>` +
  `<p style="margin:0 0 18px;font-size:13.5px;color:#37455E;line-height:1.6;text-align:center;"><b>Renew before ${when} and your remaining days stack</b> — you never lose money.</p>` +
  `<p style="margin:0 0 8px;font-size:13px;color:#5B6B85;line-height:1.6;">Not activated your current pass yet? <a href="${link}" style="color:#0040E0;">Tap your magic link</a>.</p>` +
  `<p style="margin:0;font-size:13px;color:#5B6B85;line-height:1.6;">Questions? WhatsApp us: <b>+234 902 185 2845</b></p>`;
  await sendMail(env, to, subject, text, mailShell(inner));
}

async function dailyRenewalReminders(env) {
  const now = Date.now();
  let cursor = undefined;
  do {
    const page = await env.KV.list({ prefix: "code:", cursor });
    for (const k of page.keys) {
      try {
        const raw = await env.KV.get(k.name);
        if (!raw) continue;
        const r = JSON.parse(raw);
        if (r && r.email && r.exp && r.exp > now && r.exp - now <= 3 * 864e5 && !r.remindedAt) {
          try { await emailRenewalReminder(env, r.email, r.code, r.exp); } catch (e) {}
          r.remindedAt = now;
          await env.KV.put(k.name, JSON.stringify(r));
        }
      } catch (e) { /* one bad record never stops the loop */ }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
}

/** Create a code, remember it in KV, email the buyer. Returns the code. */
async function issueCode(env, { email, ref }) {
  const code = makeCode();
  const rec = { code, email: email || "", ref: ref || "", issuedAt: Date.now(), used: false, source: "online", exp: Date.now() + 30 * 864e5 }; // dies 30 days from purchase
  await env.KV.put("code:" + code, JSON.stringify(rec));
  if (ref) await env.KV.put("ref:" + ref, code); // idempotency: ref -> code
  try {
    await emailCode(env, email, code);
  } catch (e) {
    // Never log the recipient, pass code, provider response body, or secret.
    // A payment/pass remains valid even when the separate email hand-off fails.
    console.error(`[docoga-mail] pass_email_not_accepted reason=${safeMailFailureReason(e)}`);
  }
  return code;
}

/* ---------- Selar → Zapier/Make bridge ---------- */
async function handleIssue(request, env, cors) {
  if (!env.ISSUE_SECRET || request.headers.get("x-docoga-key") !== env.ISSUE_SECRET)
    return json({ ok: false, error: "unauthorized" }, cors, 401);
  const body = await request.json().catch(() => ({}));
  const email = String(body.email || "").trim().slice(0, 254);
  const ref = String(body.ref || body.saleId || body.sale_id || "").slice(0, 120) || "selar-" + Date.now();
  if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))
    return json({ ok: false, error: "valid buyer email required" }, cors, 400);
  const existing = await env.KV.get("ref:" + ref);
  const code = existing || (await issueCode(env, { email, ref }));
  return json({ ok: true, code, alreadyIssued: !!existing }, cors);
}

/* Customer-initiated, no-charge resend for a previously verified purchase.
   It sends only to the email stored with the issued code, never returns the code,
   and is throttled by code so reference aliases cannot bypass the limit. */
async function handleResendEmail(request, env, cors) {
  // Fail closed until the owner authenticates the sender in the provider and explicitly enables resends.
  if (env.RESEND_EMAIL_ENABLED !== "true") return json({ ok: false, error: "resend_disabled" }, cors, 503);
  const body = await request.json().catch(() => ({}));
  const rawIds = Array.isArray(body.ids) ? body.ids : [body.ref || body.reference];
  const ids = [...new Set(rawIds.map((value) => String(value || "").trim()).filter((value) => value && value.length <= 200))].slice(0, 8);
  if (!ids.length) return json({ ok: false, error: "ref_required" }, cors, 400);

  let code = "";
  for (const id of ids) {
    code = await env.KV.get("ref:" + id) || "";
    if (code) break;
  }
  if (!code) return json({ ok: false, error: "purchase_not_found" }, cors, 404);

  let record = await readCode(env, normalizeCode(String(code).toUpperCase().replace(/[\s-]/g, "")));
  if (!record && String(code).includes("-")) record = await readCode(env, String(code).replace(/-/g, ""));
  // A topped-up reference should resend only the newest, currently active code.
  const visitedCodes = new Set();
  for (let depth = 0; record && record.succ; depth++) {
    if (depth >= 64) return json({ ok: false, error: "pass_unavailable" }, cors, 409);
    const successorKey = normalizeCode(String(record.succ).toUpperCase().replace(/[\s-]/g, ""));
    if (!successorKey || visitedCodes.has(successorKey)) return json({ ok: false, error: "pass_unavailable" }, cors, 409);
    visitedCodes.add(successorKey);
    const newest = await readCode(env, successorKey);
    if (!newest) return json({ ok: false, error: "pass_unavailable" }, cors, 409);
    record = newest;
  }
  if (!record || !record.email) return json({ ok: false, error: "email_unavailable" }, cors, 409);
  const expiry = Number(record.exp);
  if (!Number.isFinite(expiry) || expiry <= Date.now()) return json({ ok: false, error: "pass_expired" }, cors, 410);

  const codeKey = fnv1a(String(record.code || code).toUpperCase()).toString(16).padStart(8, "0");
  const throttleKey = "email-resend:" + codeKey;
  const now = Date.now();
  const day = Math.floor(now / 864e5);
  let throttle = { day, count: 0, last: 0 };
  try { throttle = JSON.parse(await env.KV.get(throttleKey) || "null") || throttle; } catch (e) {}
  if (throttle.day === day && throttle.count >= 3)
    return json({ ok: false, error: "resend_limit_reached" }, cors, 429);
  if (throttle.last && now - throttle.last < 60000)
    return json({ ok: false, error: "resend_wait" }, cors, 429);
  throttle = { day, count: throttle.day === day ? throttle.count + 1 : 1, last: now };
  await env.KV.put(throttleKey, JSON.stringify(throttle), { expirationTtl: 172800 });

  try {
    await emailCode(env, record.email, record.code || code);
  } catch (e) {
    console.error(`[docoga-mail] resend_not_accepted reason=${safeMailFailureReason(e)}`);
    return json({ ok: false, error: "email_send_failed" }, cors, 502);
  }
  return json({ ok: true, message: "email_request_accepted" }, cors);
}

/* ---------- Business waitlist (Phase 0, 11 Oct 2026) ----------
 * Self-serve "notify me at launch" for the Business tier. Replaces the retired
 * quote-by-WhatsApp CTA (owner instruction 11 Oct 2026: Business must run
 * end-to-end without the customer sending a WhatsApp message).
 * - dedupe on email (KV bizwait:{email}); rate guard 3 per IP per day
 * - the signup is stored BEFORE any email: a signup remains valid even when
 *   the separate email hand-off fails (same rule as pass issuance)
 * - owner reads the list in the Cloudflare KV dashboard (no public read endpoint) */
async function handleBusinessWaitlist(request, env, cors) {
  const body = await request.json().catch(() => null);
  if (!body) return json({ ok: false, error: "json body required" }, cors, 400);
  const email = String(body.email || "").trim().slice(0, 254).toLowerCase();
  const company = String(body.company || "").trim().slice(0, 120);
  const segment = String(body.segment || "").trim().slice(0, 40);
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
    return json({ ok: false, error: "valid email required" }, cors, 400);
  const SEGMENTS = ["estate-agent", "property-manager", "landlord", "hr-team"];
  if (segment && !SEGMENTS.includes(segment))
    return json({ ok: false, error: "unknown segment" }, cors, 400);
  try {
    const ip = ((request.headers.get("cf-connecting-ip") || request.headers.get("x-real-ip") || "unknown").replace(/[^a-zA-Z0-9.:_-]/g, "").slice(0, 64)) || "unknown";
    const k = "bizwait:ip:" + ip + ":" + new Date().toISOString().slice(0, 10);
    const n = Number((await env.KV.get(k)) || "0") + 1;
    await env.KV.put(k, String(n), { expirationTtl: 86400 });
    if (n > 3) return json({ ok: false, error: "too many requests from your connection — try again tomorrow" }, cors, 429);
  } catch (e) {}
  const key = "bizwait:" + email;
  const existing = await env.KV.get(key);
  if (existing) return json({ ok: true, alreadyOnList: true });
  await env.KV.put(key, JSON.stringify({ email, company, segment, at: new Date().toISOString() }));
  let emailSent = false;
  try {
    await sendMail(
      env, email,
      "You're on the DocOga Business list",
      "Thanks — you're on the list for the DocOga Business tier (annual, per team, your firm's name and logo on every document).\n\nWe'll email you once, when your team can sign up. No WhatsApp, no chasing — if you don't see it, check spam.\n\n— DocOga, Abuja\nhttps://docoga.com.ng",
      mailShell(`<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">You're on the list</h2><p style="margin:0 0 12px;font-size:14px;color:#33415C;line-height:1.6">We're building the DocOga <b>Business</b> tier — annual, per team, your firm's name and logo on every document, team seats you manage yourself.</p><p style="margin:0;font-size:14px;color:#33415C;line-height:1.6">We'll email you once, when your team can sign up. No WhatsApp, no chasing.</p>`)
    );
    emailSent = true;
  } catch (e) {
    // Never log the recipient or provider response body. The signup is already stored.
    console.error(`[docoga-mail] bizwait_email_not_accepted reason=${safeMailFailureReason(e)}`);
  }
  return json({ ok: true, alreadyOnList: false, confirmationEmail: emailSent });
}

/* ---------- Business team core (Phase 1, 11 Oct 2026) ----------
 * Team/brand/seat records + magic-link auth + owner team/brand/seats API.
 * Phase 1 teams are created by the owner BY HAND in KV (recipe:
 * docs/BUSINESS_TEAM_SETUP.md; dossier: docs/BUSINESS_TIER_RESEARCH.md §10):
 *   team:{id}        {"id","slug","name","status":"active","expiry":"YYYY-MM-DD","plan"}
 *   team:{id}:seats  [{"email","name","role":"owner"|"member","status":"active","invited_at"}]
 *   brand:{id}       {"name","address","logo":data-URI(≤25KB),"footer"}
 *   seatidx:{email}  teamId
 * Security model: the magic link is a one-time 10-minute token (only its
 * SHA-256 hash is stored); the session token is a stateless
 * HMAC(payload, TEAM_AUTH_SECRET) whose validity is RE-CHECKED AGAINST KV ON
 * EVERY CALL (team status+expiry, seat status) — a revoked seat or expired
 * team loses access immediately, no token revocation needed. The site and
 * this Worker are different origins, so the session rides in
 * Authorization: Bearer (localStorage on the site), not a cookie.
 * No TEAM_AUTH_SECRET set → every /business/login* and /business/team* call
 * fails closed with 503 team_auth_disabled (same pattern as RESEND_EMAIL_ENABLED). */
const TEAM_SESSION_DAYS = 30;
const MAGIC_TTL_SEC = 600;
const LOGO_MAX_BYTES = 25 * 1024;

function htmlEsc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
async function teamSha256Hex(str) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(str));
  let s = ""; for (const b of new Uint8Array(d)) s += b.toString(16).padStart(2, "0");
  return s;
}
async function teamSig(env, payload) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(env.TEAM_AUTH_SECRET), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(payload));
  let bin = ""; const bytes = new Uint8Array(mac);
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}
async function makeSessionToken(env, teamId, email) {
  const exp = Math.floor(Date.now() / 1000) + TEAM_SESSION_DAYS * 86400;
  const payload = "tl_" + teamId + "|" + email + "|" + exp;
  return payload + "." + await teamSig(env, payload);
}
function logoValid(logo) {
  if (typeof logo !== "string" || logo === "") return true; // absent or clearing
  const m = /^data:image\/(png|jpeg|svg\+xml);base64,([A-Za-z0-9+/=]+)$/.exec(logo);
  if (!m) return false;
  return Math.floor(m[2].length * 3 / 4) <= LOGO_MAX_BYTES;
}
async function loadTeam(env, teamId) {
  const raw = await env.KV.get("team:" + teamId);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch (e) { return null; }
}
function teamLive(team) {
  if (!team || team.status !== "active") return false;
  if (team.expiry) { const t = Date.parse(team.expiry + "T23:59:59Z"); if (t && t < Date.now()) return false; }
  return true;
}
async function loadSeats(env, teamId) {
  try { const s = JSON.parse(await env.KV.get("team:" + teamId + ":seats") || "[]"); return Array.isArray(s) ? s : []; } catch (e) { return []; }
}
async function magicLinkToken(email) {
  const rand = crypto.getRandomValues(new Uint8Array(32));
  let token = email + "~";
  for (const b of rand) token += b.toString(16).padStart(2, "0");
  return token;
}
async function storeMagicToken(env, token) {
  await env.KV.put("auth:" + token.slice(0, token.lastIndexOf("~")).toLowerCase(),
    JSON.stringify({ h: await teamSha256Hex(token), exp: Math.floor(Date.now() / 1000) + MAGIC_TTL_SEC }),
    { expirationTtl: MAGIC_TTL_SEC });
}
async function sendAuthMail(env, email, name, teamName, token, introLine) {
  const link = (env.SITE_URL || "https://docoga.com.ng") + "?team_token=" + encodeURIComponent(token);
  await sendMail(
    env, email,
    introLine,
    "Hi " + (name || "") + ",\n\n" + teamName + " on DocOga — sign in with one click (no password; this link works once and expires in 10 minutes):\n\n" + link + "\n\nIf you didn't ask for this, ignore it — nothing changes.\n\n— DocOga, Abuja\nhttps://docoga.com.ng",
    mailShell(`<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">${htmlEsc(teamName)}</h2><p style="margin:0 0 16px;font-size:14px;color:#33415C;line-height:1.6">${htmlEsc(introLine === "Sign in to your DocOga team" ? "Sign in with one click — no password." : "Your team added you. Documents you generate carry your firm's name and logo.")} This link works once and expires in 10 minutes.</p><a href="${link}" style="display:inline-block;background:#0B1B3F;color:#fff;padding:12px 22px;border-radius:10px;font-size:14px;text-decoration:none;font-family:Arial,sans-serif">Sign in &rarr;</a><p style="margin:16px 0 0;font-size:12px;color:#64748B;font-family:Arial,sans-serif">Didn't ask for this? Ignore it — nothing changes.</p>`)
  );
}
async function teamLoginRateGuard(request, env, email) {
  const today = new Date().toISOString().slice(0, 10);
  try {
    const ekey = "teamlogin:em:" + email + ":" + today;
    const n = Number((await env.KV.get(ekey)) || "0") + 1;
    await env.KV.put(ekey, String(n), { expirationTtl: 86400 });
    const ip = ((request.headers.get("cf-connecting-ip") || "unknown").replace(/[^a-zA-Z0-9.:_-]/g, "").slice(0, 64)) || "unknown";
    const ikey = "teamlogin:ip:" + ip + ":" + today;
    const m = Number((await env.KV.get(ikey)) || "0") + 1;
    await env.KV.put(ikey, String(m), { expirationTtl: 86400 });
    return n <= 5 && m <= 10;
  } catch (e) { return true; } // the guard must never hard-block sign-in
}
async function handleBusinessLogin(request, env, cors) {
  if (!env.TEAM_AUTH_SECRET) return json({ ok: false, error: "team_auth_disabled" }, cors, 503);
  const body = await request.json().catch(() => null);
  const email = String((body && body.email) || "").trim().slice(0, 254).toLowerCase();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json({ ok: false, error: "valid email required" }, cors, 400);
  const teamId = await env.KV.get("seatidx:" + email);
  if (!teamId) return json({ ok: false, error: "that email is not on a DocOga team yet" }, cors, 400);
  const team = await loadTeam(env, teamId);
  if (!teamSignInOk(team)) return json({ ok: false, error: "team not active" }, cors, 400);
  const seat = (await loadSeats(env, teamId)).find(s => String(s.email || "").toLowerCase() === email);
  if (!seat || seat.status !== "active") return json({ ok: false, error: "this email can't sign in — ask your team owner" }, cors, 400);
  if (!(await teamLoginRateGuard(request, env, email))) return json({ ok: false, error: "too many sign-in requests — try again tomorrow" }, cors, 429);
  const token = await magicLinkToken(email);
  await storeMagicToken(env, token);
  try {
    await sendAuthMail(env, email, seat.name, team.name, token, "Sign in to your DocOga team");
  } catch (e) {
    console.error(`[docoga-mail] biz_auth_email_not_accepted reason=${safeMailFailureReason(e)}`);
    return json({ ok: false, error: "email_send_failed — your team is ready, try again" }, cors, 502);
  }
  return json({ ok: true, message: "check_your_email" });
}
async function handleBusinessLoginVerify(url, env, cors) {
  if (!env.TEAM_AUTH_SECRET) return json({ ok: false, error: "team_auth_disabled" }, cors, 503);
  const token = url.searchParams.get("token") || "";
  const tilde = token.lastIndexOf("~");
  if (tilde < 3) return json({ ok: false, error: "invalid link" }, cors, 400);
  const email = token.slice(0, tilde).toLowerCase();
  const storedRaw = await env.KV.get("auth:" + email);
  let stored = null; if (storedRaw) { try { stored = JSON.parse(storedRaw); } catch (e) {} }
  if (!stored || Number(stored.exp) < Date.now() / 1000 || stored.h !== await teamSha256Hex(token))
    return json({ ok: false, error: "link expired or already used — request a new one" }, cors, 400);
  await env.KV.delete("auth:" + email); // one-time
  const teamId = await env.KV.get("seatidx:" + email);
  const team = teamId ? await loadTeam(env, teamId) : null;
  const seat = teamId ? (await loadSeats(env, teamId)).find(s => String(s.email || "").toLowerCase() === email) : null;
  if (!teamSignInOk(team) || !seat || seat.status !== "active")
    return json({ ok: false, error: "this email can't sign in — ask your team owner" }, cors, 400);
  const sess = await makeSessionToken(env, teamId, email);
  return json({
    ok: true, token: sess,
    role: seat.role === "owner" ? "owner" : "member",
    team: { id: teamId, name: team.name, slug: team.slug },
    email, exp: Math.floor(Date.now() / 1000) + TEAM_SESSION_DAYS * 86400
  });
}
async function teamSession(request, env) {
  if (!env.TEAM_AUTH_SECRET) return null;
  const h = request.headers.get("authorization") || "";
  const tok = h.startsWith("Bearer ") ? h.slice(7) : (request.headers.get("x-doco-team") || "");
  if (!tok || !tok.startsWith("tl_")) return null;
  const dot = tok.lastIndexOf(".");
  if (dot < 3) return null;
  const payload = tok.slice(0, dot);
  const parts = payload.slice(3).split("|");
  if (parts.length !== 3) return null;
  const [teamId, email, expStr] = parts;
  if (!teamId || !email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return null;
  const exp = Number(expStr);
  if (!Number.isFinite(exp) || exp < Date.now() / 1000) return null;
  if (await teamSig(env, payload) !== tok.slice(dot + 1)) return null; // forged/tampered
  const team = await loadTeam(env, teamId);
  if (!teamSignInOk(team)) return null;
  const seat = (await loadSeats(env, teamId)).find(s => String(s.email || "").toLowerCase() === email.toLowerCase());
  if (!seat || seat.status !== "active") return null;
  return { id: teamId, email: email.toLowerCase(), role: seat.role === "owner" ? "owner" : "member", team };
}
function publicSeats(seats, viewer) {
  const pick = s => ({ email: s.email, name: s.name, role: s.role, status: s.status });
  return (viewer.role === "owner" ? seats : seats.filter(s => String(s.email || "").toLowerCase() === viewer.email)).map(pick);
}
async function handleBusinessTeam(request, env, cors) {
  const s = await teamSession(request, env);
  if (!s) return json({ ok: false, error: "sign_in_required" }, cors, 401);
  let brand = {}; try { brand = JSON.parse(await env.KV.get("brand:" + s.id) || "{}"); } catch (e) {}
  return json({
    ok: true,
    team: { id: s.id, slug: s.team.slug, name: s.team.name, status: s.team.status, expiry: s.team.expiry, plan: s.team.plan },
    email: s.email, role: s.role,
    seats: publicSeats(await loadSeats(env, s.id), s),
    brand,
    // Unpaid teams need the published quote to render checkout (C3 formula)
    quote: s.team.status === "unpaid" ? businessQuote(s.team.seats, s.team.docs) : undefined,
    openInvoice: s.team.status === "unpaid" ? (await currentInvoice(env, s.id)) : undefined
  });
}
async function handleBusinessBrand(request, env, cors) {
  const s = await teamSession(request, env);
  if (!s) return json({ ok: false, error: "sign_in_required" }, cors, 401);
  if (s.role !== "owner") return json({ ok: false, error: "owner_only" }, cors, 403);
  const body = await request.json().catch(() => null);
  if (!body) return json({ ok: false, error: "json body required" }, cors, 400);
  let brand = {}; try { brand = JSON.parse(await env.KV.get("brand:" + s.id) || "{}"); } catch (e) {}
  if (body.name !== undefined) {
    const name = String(body.name).trim().slice(0, 120);
    if (!name) return json({ ok: false, error: "brand name required" }, cors, 400);
    brand.name = name;
  }
  if (body.address !== undefined) brand.address = String(body.address).trim().slice(0, 200);
  if (body.footer !== undefined) brand.footer = String(body.footer).trim().slice(0, 200);
  if (body.logo !== undefined) {
    if (!logoValid(body.logo)) return json({ ok: false, error: "logo must be a PNG, JPG or SVG data-URI, ≤25KB" }, cors, 400);
    if (body.logo === "") delete brand.logo; else brand.logo = body.logo;
  }
  await env.KV.put("brand:" + s.id, JSON.stringify(brand));
  return json({ ok: true, brand });
}
async function handleBusinessSeats(request, env, cors) {
  const s = await teamSession(request, env);
  if (!s) return json({ ok: false, error: "sign_in_required" }, cors, 401);
  if (s.role !== "owner") return json({ ok: false, error: "owner_only" }, cors, 403);
  const body = await request.json().catch(() => null);
  if (!body) return json({ ok: false, error: "json body required" }, cors, 400);
  const action = String(body.action || "");
  const email = String(body.email || "").trim().slice(0, 254).toLowerCase();
  const name = String(body.name || "").trim().slice(0, 120);
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json({ ok: false, error: "valid email required" }, cors, 400);
  if (action !== "invite" && action !== "revoke") return json({ ok: false, error: "action must be invite or revoke" }, cors, 400);
  const seats = await loadSeats(env, s.id);
  const idx = seats.findIndex(x => String(x.email || "").toLowerCase() === email);
  if (action === "invite") {
    const today = new Date().toISOString().slice(0, 10);
    try {
      const k = "teamseats:" + s.id + ":" + today;
      const n = Number((await env.KV.get(k)) || "0") + 1;
      await env.KV.put(k, String(n), { expirationTtl: 86400 });
      if (n > 5) return json({ ok: false, error: "too many invites today — try again tomorrow" }, cors, 429);
    } catch (e) {}
    const other = await env.KV.get("seatidx:" + email);
    if (other && other !== s.id) return json({ ok: false, error: "that email is already on another team" }, cors, 400);
    if (idx >= 0) {
      if (seats[idx].status === "active") return json({ ok: false, error: "already a member of this team" }, cors, 400);
      seats[idx] = { email, name: name || seats[idx].name || "", role: seats[idx].role === "owner" ? "owner" : "member", status: "active", invited_at: new Date().toISOString() };
    } else {
      seats.push({ email, name, role: "member", status: "active", invited_at: new Date().toISOString() });
    }
    await env.KV.put("team:" + s.id + ":seats", JSON.stringify(seats));
    await env.KV.put("seatidx:" + email, s.id);
    // Magic link for the seat (best-effort: the seat exists even if the email hand-off fails)
    const token = await magicLinkToken(email);
    await storeMagicToken(env, token);
    let emailSent = false;
    try {
      await sendAuthMail(env, email, name, s.team.name, token, "You're on the " + s.team.name + " team (DocOga)");
      emailSent = true;
    } catch (e) {
      console.error(`[docoga-mail] biz_seat_email_not_accepted reason=${safeMailFailureReason(e)}`);
    }
    return json({ ok: true, action: "invite", emailSent });
  }
  if (idx < 0) return json({ ok: false, error: "not a member of this team" }, cors, 400);
  if (seats[idx].role === "owner") return json({ ok: false, error: "the owner seat can't be revoked here — edit the KV record" }, cors, 400);
  seats[idx] = Object.assign({}, seats[idx], { status: "revoked" });
  await env.KV.put("team:" + s.id + ":seats", JSON.stringify(seats));
  await env.KV.delete("seatidx:" + email); // allows a clean re-invite later
  await env.KV.delete("auth:" + email);
  return json({ ok: true, action: "revoke" });
}

/* ---------- Business money path (Phase 2, 11 Oct 2026) ----------
 * C3/C4/C5/C10: self-serve team creation (unpaid), invoicing, Flutterwave
 * bank-transfer (dynamic VA — PRIMARY advertised method per dossier §6.4)
 * and card (v4 hosted "generic" charge — P3, honest 502 if the account
 * doesn't support it). Webhook activates on signature + reference match;
 * the amount is validated in BOTH naira and kobo (v4 reports minor units —
 * never guess on the money path). Prices are the PUBLISHED formula
 * (dossier §6.1, PROPOSED bands): worker is authoritative — the client
 * never sends a price.
 * KV: team:{id}:inv (current invoice id) · inv:{id} (record) · inv:{id}:va
 * (bank/account/amount/expires) · invref:{ref} (invoice id; ref = invoice id)
 * VA expiry: we REQUEST a 7-day expiry on the v4 payment method but HONOUR
 * whatever account_expiration_datetime the vendor returns (dynamic VAs
 * default to 1h per Flutterwave docs); the customer sees the real expiry
 * and "get a new one" re-issues (dossier §7.4). */
const BIZ_TIERS = [
  { key: "starter", base: 96000, seats: 3, docs: 100, brands: 1 },
  { key: "standard", base: 240000, seats: 8, docs: 300, brands: 1 },
  { key: "growth", base: 480000, seats: 20, docs: 1000, brands: 2 },
];
const BIZ_SEAT_UNIT = 48000; // per extra seat/yr (above the seat band)
const BIZ_DOC_BLOCK_UNIT = 18000; // per extra 100 docs/mo block, per yr
const BIZ_VAT = 0.075; // shown line-item (dossier §6.4)
const UNPAID_TTL_DAYS = 14; // an unpaid team can sign in (to pay) for 14 days
function businessQuote(seats, docs) {
  const nseats = Math.max(1, Math.min(500, Math.floor(Number(seats) || 1)));
  const ndocs = Math.max(100, Math.min(100000, Math.floor(Number(docs) || 100)));
  const tier = BIZ_TIERS.find(t => nseats <= t.seats) || BIZ_TIERS[BIZ_TIERS.length - 1];
  const extraSeats = Math.max(0, nseats - tier.seats);
  const extraBlocks = Math.max(0, Math.ceil((ndocs - tier.docs) / 100));
  const price = tier.base + extraSeats * BIZ_SEAT_UNIT + extraBlocks * BIZ_DOC_BLOCK_UNIT;
  const vat = Math.round(price * BIZ_VAT);
  return { tier: tier.key, seats: nseats, docs: ndocs, extraSeats, extraBlocks, price, vat, total: price + vat };
}
function teamSignInOk(team) {
  if (!team) return false;
  if (team.status === "active") return teamLive(team);
  if (team.status === "unpaid") {
    const born = Date.parse(team.created || "1970-01-01T00:00:00Z");
    return born + UNPAID_TTL_DAYS * 864e5 >= Date.now();
  }
  return false;
}
async function flw4Post(env, path, body) {
  const token = await flw4Token(env);
  const r = await fetch(FLW4_BASE + path, {
    method: "POST",
    headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let j = {};
  try { j = await r.json(); } catch (e) {}
  if (!r.ok || j.status === "failure") throw new Error("FLW4_HTTP_" + r.status);
  return j;
}
async function handleBusinessTeams(request, env, cors) {
  if (!env.TEAM_AUTH_SECRET) return json({ ok: false, error: "team_auth_disabled" }, cors, 503);
  const body = await request.json().catch(() => null);
  const email = String((body && body.email) || "").trim().slice(0, 254).toLowerCase();
  const name = String((body && body.name) || "").trim().slice(0, 120);
  const segment = String((body && body.segment) || "").trim().slice(0, 40);
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json({ ok: false, error: "valid email required" }, cors, 400);
  if (!name) return json({ ok: false, error: "firm name required" }, cors, 400);
  const SEGS = ["estate-agent", "property-manager", "landlord", "hr-team"];
  if (segment && !SEGS.includes(segment)) return json({ ok: false, error: "unknown segment" }, cors, 400);
  const other = await env.KV.get("seatidx:" + email);
  if (other) return json({ ok: false, error: "that email is already on a DocOga team" }, cors, 400);
  try {
    const ip = ((request.headers.get("cf-connecting-ip") || "unknown").replace(/[^a-zA-Z0-9.:_-]/g, "").slice(0, 64)) || "unknown";
    const k = "bizcreate:ip:" + ip + ":" + new Date().toISOString().slice(0, 10);
    const n = Number((await env.KV.get(k)) || "0") + 1;
    await env.KV.put(k, String(n), { expirationTtl: 86400 });
    if (n > 10) return json({ ok: false, error: "too many team requests from your connection — try again tomorrow" }, cors, 429);
  } catch (e) {}
  const q = businessQuote(body.seats, body.docs);
  const id = "t" + Math.random().toString(36).slice(2, 8);
  const now = new Date().toISOString();
  await env.KV.put("team:" + id, JSON.stringify({
    id, slug: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 40) || id,
    name, status: "unpaid", plan: q.tier, price: q.price, vat: q.vat, total: q.total,
    seats: q.seats, docs: q.docs, segment, created: now, expiry: "",
  }));
  await env.KV.put("team:" + id + ":seats", JSON.stringify([{ email, name: "", role: "owner", status: "active", invited_at: now }]));
  await env.KV.put("brand:" + id, JSON.stringify({ name }));
  await env.KV.put("seatidx:" + email, id);
  // Magic link (best-effort: the team exists even if the email hand-off fails —
  // the owner can request a fresh link from the sign-in form)
  const token = await magicLinkToken(email);
  await storeMagicToken(env, token);
  let emailSent = false;
  try {
    await sendAuthMail(env, email, "", name, token, "Your DocOga team is ready — sign in and activate it");
    emailSent = true;
  } catch (e) {
    console.error(`[docoga-mail] biz_team_email_not_accepted reason=${safeMailFailureReason(e)}`);
  }
  return json({ ok: true, team: { id, name }, quote: q, confirmationEmail: emailSent });
}
async function currentInvoice(env, teamId) {
  const id = await env.KV.get("team:" + teamId + ":inv");
  if (!id) return null;
  const invRaw = await env.KV.get("inv:" + id);
  if (!invRaw) return null;
  try { return JSON.parse(invRaw); } catch (e) { return null; }
}
async function handleBusinessCharge(request, env, cors) {
  const s = await teamSession(request, env);
  if (!s) return json({ ok: false, error: "sign_in_required" }, cors, 401);
  if (s.role !== "owner") return json({ ok: false, error: "owner_only" }, cors, 403);
  if (s.team.status !== "unpaid") return json({ ok: false, error: "team already active — renewals are handled by DocOga by email" }, cors, 400);
  const body = await request.json().catch(() => ({ method: "transfer" }));
  const method = String((body && body.method) || "transfer");
  if (method !== "transfer" && method !== "card") return json({ ok: false, error: "method must be transfer or card" }, cors, 400);
  const existing = await currentInvoice(env, s.id);
  if (existing && existing.status === "open") {
    // Re-issue only when the VA is dead (expired/voided) — "link expired, get a new one" (§7.4)
    const va = JSON.parse(await env.KV.get("inv:" + existing.id + ":va") || "null");
    const vaAlive = va && !va.voided && (!va.expires || Date.parse(va.expires) > Date.now());
    if (method === existing.method && vaAlive) {
      return json({ ok: true, reused: true, invoice: { id: existing.id, base: existing.amount, vat: existing.vat, total: existing.total }, va, reference: existing.ref });
    }
  }
  try {
    const k = "bizcharge:" + s.id + ":" + new Date().toISOString().slice(0, 10);
    const n = Number((await env.KV.get(k)) || "0") + 1;
    await env.KV.put(k, String(n), { expirationTtl: 86400 });
    if (n > 5) return json({ ok: false, error: "too many payment links today — try again tomorrow" }, cors, 429);
  } catch (e) {}
  const q = businessQuote(s.team.seats, s.team.docs);
  const id = "INV-" + Math.random().toString(36).slice(2, 10).toUpperCase();
  const now = new Date().toISOString();
  const inv = { id, team: s.id, amount: q.price, vat: q.vat, total: q.total, seats: q.seats, docs: q.docs, plan: q.tier, method, status: "open", ref: id, flw_ref: "", created: now };
  if (method === "transfer") {
    const exp = new Date(Date.now() + 7 * 864e5).toISOString();
    let pm;
    try {
      pm = await flw4Post(env, "/v1/payment_methods", {
        type: "bank_account", currency: "NGN",
        amount: q.total * 100, // v4 reports minor units (kobo)
        reference: id,
        note: "DocOga Business — " + s.team.name + " — pay exactly " + q.total + " NGN",
        account_expiration_datetime: exp, // requested; the VENDOR'S returned expiry is what we honour
        customer: { email: s.email },
      });
    } catch (e) {
      return json({ ok: false, error: "could not create your transfer account — try again in a moment" }, cors, 502);
    }
    const d = pm.data || {};
    if (!d.account_number) return json({ ok: false, error: "could not create your transfer account — try again in a moment" }, cors, 502);
    const va = { bank: d.account_bank_name || d.bank_name || "Flutterwave MFB", account: String(d.account_number), amount: d.amount, expires: d.account_expiration_datetime || d.expiry_date || exp, note: d.note || "", flw_ref: d.reference || d.flw_ref || "" };
    await env.KV.put("inv:" + id + ":va", JSON.stringify(va));
    inv.flw_ref = va.flw_ref;
  } else {
    let ch;
    try {
      ch = await flw4Post(env, "/v1/charges", {
        amount: q.total * 100, currency: "NGN", reference: id,
        payment_method: { type: "generic" }, // hosted page: card / USSD / POS
        customer: { email: s.email },
        return_url: (env.SITE_URL || "https://docoga.com.ng") + "/?team_inv=" + id,
        description: "DocOga Business — " + s.team.name,
      });
    } catch (e) {
      return json({ ok: false, error: "card checkout is not available for your plan right now — please use bank transfer" }, cors, 502);
    }
    const d = ch.data || {};
    const payUrl = (d.next_action && (d.next_action.url || d.next_action.redirect_url)) || d.hosted_payment_url;
    if (!payUrl) return json({ ok: false, error: "card checkout is not available for your plan right now — please use bank transfer" }, cors, 502);
    inv.pay_url = payUrl;
    inv.flw_ref = d.id || "";
  }
  await env.KV.put("inv:" + id, JSON.stringify(inv));
  await env.KV.put("invref:" + id, id);
  if (inv.flw_ref && inv.flw_ref !== id) await env.KV.put("invref:" + inv.flw_ref, id);
  await env.KV.put("team:" + s.id + ":inv", id);
  // Team invoice index (newest first, cap 24) — the portal list reads this
  let invIndex = []; try { invIndex = JSON.parse(await env.KV.get("teaminv:" + s.id) || "[]"); } catch (e) {}
  invIndex = [{ id, total: q.total, method, status: "open", created: now }].concat(invIndex).slice(0, 24);
  try { await env.KV.put("teaminv:" + s.id, JSON.stringify(invIndex)); } catch (e) {}
  const out = { ok: true, reused: false, invoice: { id, base: inv.amount, vat: inv.vat, total: inv.total } };
  if (method === "transfer") out.va = JSON.parse(await env.KV.get("inv:" + id + ":va"));
  else out.pay_url = inv.pay_url;
  return json(out, cors);
}
async function handleBusinessInvoices(request, env, cors) {
  const s = await teamSession(request, env);
  if (!s) return json({ ok: false, error: "sign_in_required" }, cors, 401);
  let invIndex = []; try { invIndex = JSON.parse(await env.KV.get("teaminv:" + s.id) || "[]"); } catch (e) {}
  // 12-month download window (C10) — older invoices stay in the records, not the portal
  const cutoff = Date.now() - 365 * 864e5;
  const invoices = invIndex.filter(x => x && x.id && (Date.parse(x.created || "1970-01-01T00:00:00Z") >= cutoff)).slice(0, 20);
  return json({ ok: true, invoices });
}
function invoiceHtml(inv, team, brand, va) {
  const firm = brand.name || (team && team.name) || "Your firm";
  const logo = brand.logo ? '<img src="' + brand.logo + '" style="height:40px;max-width:180px;object-fit:contain">' : '';
  const lines = [
    '<tr><td>DocOga Business licence — ' + htmlEsc(String(inv.plan || "team")) + ' plan (' + (inv.seats || 1) + ' seats, ' + (inv.docs || 100) + ' docs/month)</td><td align="right">' + Number(inv.amount).toLocaleString('en-NG') + '</td></tr>',
    '<tr><td>VAT (7.5%)</td><td align="right">' + Number(inv.vat).toLocaleString('en-NG') + '</td></tr>',
    '<tr class="total"><td>Total — annual</td><td align="right">₦' + Number(inv.total).toLocaleString('en-NG') + '</td></tr>',
  ].join("");
  const statusChip = inv.status === "paid"
    ? '<span class="chip paid">PAID' + (inv.paid_at ? ' · ' + htmlEsc(inv.paid_at.slice(0, 10)) : '') + '</span>'
    : inv.status === "wrong_amount"
      ? '<span class="chip wrong">WRONG AMOUNT — see fresh account in your email</span>'
      : '<span class="chip open">OPEN' + (inv.method === "transfer" && va && va.account ? ' · transfer to ' + htmlEsc(va.account) + ' (' + htmlEsc(va.bank || "Flutterwave MFB") + ')' : '') + '</span>';
  return '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Invoice ' + htmlEsc(inv.id) + ' — DocOga</title>' +
    '<style>body{font-family:Arial,Helvetica,sans-serif;background:#f1f5f9;margin:0;color:#0f172a}.page{max-width:760px;margin:24px auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:36px 40px}@media print{body{background:#fff}.page{border:none;margin:0;max-width:none;padding:24px}button{display:none!important}}.top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}.firm{font-size:20px;font-weight:bold}.sub{color:#475569;font-size:13px;margin-top:2px}.inv{font-size:13px;color:#475569;text-align:right}.chip{display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:bold;margin:10px 0}.chip.paid{background:#dcfce7;color:#166534}.chip.open{background:#fef9c3;color:#854d0e}.chip.wrong{background:#fee2e2;color:#991b1b}table{width:100%;border-collapse:collapse;margin:18px 0;font-size:14px}td{padding:9px 4px;border-bottom:1px solid #e2e8f0;vertical-align:top}tr.total td{font-weight:bold;font-size:16px;border-bottom:none}.meta{font-size:12px;color:#64748b;line-height:1.7}button{background:#0B1B3F;color:#fff;border:none;padding:11px 20px;border-radius:10px;font-size:14px;cursor:pointer;margin-bottom:14px}.foot{margin-top:26px;padding-top:14px;border-top:1px dashed #cbd5e1;font-size:11px;color:#94a3b8;line-height:1.6}</style></head><body>' +
    '<button onclick="window.print()">Print / Save as PDF</button>' +
    '<div class="page"><div class="top"><div>' + logo + '<div class="firm">' + htmlEsc(firm) + '</div>' + (brand.address ? '<div class="sub">' + htmlEsc(brand.address) + '</div>' : '') + '</div><div class="inv"><b>INVOICE</b><br>' + htmlEsc(inv.id) + '<br>Issued ' + htmlEsc(String(inv.created || "").slice(0, 10)) + '</div></div>' +
    '<div>' + statusChip + '</div>' +
    '<table><tbody>' + lines + '</tbody></table>' +
    '<div class="meta"><b>Payment:</b> ' + htmlEsc(inv.method === "card" ? "Card / USSD via Flutterwave" : "Bank transfer (virtual account)") + ' · Reference ' + htmlEsc(inv.ref || inv.id) + (inv.flw_ref ? ' · Flutterwave ' + htmlEsc(inv.flw_ref) : '') + (va && va.expires ? ' · account valid until ' + htmlEsc(va.expires) : '') + '<br><b>Billed to:</b> ' + htmlEsc(firm) + ' — 12-month licence, firm branding + seat management included.<br><b>Questions:</b> business@docoga.com.ng (email — we answer within 1 working day).</div>' +
    '<div class="foot">DocOga · docoga.com.ng · This invoice is generated from the payment record — it is the authoritative statement for this team. DocOga is not a law firm and this invoice is not legal advice.</div></div></body></html>';
}
async function handleBusinessInvoice(id, request, env, cors) {
  const s = await teamSession(request, env);
  if (!s) return new Response("sign in required", { status: 401, headers: cors });
  if (!/^[A-Za-z0-9-]{6,40}$/.test(id)) return new Response("invoice not found", { status: 404, headers: cors });
  const invRaw = await env.KV.get("inv:" + id);
  if (!invRaw) return new Response("invoice not found", { status: 404, headers: cors });
  let inv = null; try { inv = JSON.parse(invRaw); } catch (e) {}
  if (!inv || inv.team !== s.id) return new Response("invoice not found", { status: 404, headers: cors }); // never leak other teams' invoices
  const team = await loadTeam(env, s.id);
  let brand = {}; try { brand = JSON.parse(await env.KV.get("brand:" + s.id) || "{}"); } catch (e) {}
  let va = null; try { va = JSON.parse(await env.KV.get("inv:" + id + ":va") || "null"); } catch (e) {}
  return new Response(invoiceHtml(inv, team, brand, va), { headers: Object.assign({}, cors, { "Content-Type": "text/html; charset=utf-8" }) });
}
async function handleInvoiceWebhook(env, d, ids) {
  // Returns true when this webhook belongs to a Business invoice (handled
  // here); false = fall through to the retail pass path.
  for (const cand of ids) {
    const invId = await env.KV.get("invref:" + cand);
    if (!invId) continue;
    const invRaw = await env.KV.get("inv:" + invId);
    let inv = null; if (invRaw) { try { inv = JSON.parse(invRaw); } catch (e) {} }
    if (!inv) continue;
    const amt = d.amount && typeof d.amount === "object" ? Number(d.amount.value) : Number(d.amount);
    // v4 reports minor units (kobo), v3 naira — accept both, never guess.
    const amountOk = amt === inv.total || amt === Math.round(inv.total * 100);
    if (inv.status === "paid") return true; // idempotent
    const owner = (JSON.parse(await env.KV.get("team:" + inv.team + ":seats") || "[]")).find(x => x.role === "owner");
    if (!amountOk) {
      // Wrong amount to the VA (§7.4): no activation, void the VA, issue a
      // fresh one, email the correct amount. No human reconciliation.
      inv.status = "wrong_amount"; inv.received_amount = amt;
      await env.KV.put("inv:" + inv.id, JSON.stringify(inv));
      try {
        let invIndex = []; try { invIndex = JSON.parse(await env.KV.get("teaminv:" + inv.team) || "[]"); } catch (e) {}
        const jx = invIndex.findIndex(x => x && x.id === inv.id);
        if (jx >= 0) { invIndex[jx].status = "wrong_amount"; await env.KV.put("teaminv:" + inv.team, JSON.stringify(invIndex)); }
      } catch (e) {}
      try {
        const oldVa = JSON.parse(await env.KV.get("inv:" + inv.id + ":va") || "null");
        if (oldVa) { oldVa.voided = true; await env.KV.put("inv:" + inv.id + ":va", JSON.stringify(oldVa)); }
        const exp = new Date(Date.now() + 7 * 864e5).toISOString();
        const newRef = inv.id + "R" + String(Date.now()).slice(-5);
        const pm = await flw4Post(env, "/v1/payment_methods", {
          type: "bank_account", currency: "NGN", amount: inv.total * 100,
          reference: newRef,
          note: "DocOga Business — pay exactly " + inv.total + " NGN (previous account closed)",
          account_expiration_datetime: exp,
          customer: owner ? { email: owner.email } : undefined,
        });
        const dpm = pm.data || {};
        if (dpm.account_number) {
          inv.ref = newRef;
          await env.KV.put("invref:" + newRef, inv.id); // the corrected transfer must match
          if (dpm.reference) await env.KV.put("invref:" + dpm.reference, inv.id);
          await env.KV.put("inv:" + inv.id + ":va", JSON.stringify({
            bank: dpm.account_bank_name || "Flutterwave MFB", account: String(dpm.account_number),
            amount: dpm.amount, expires: dpm.account_expiration_datetime || exp, note: dpm.note || "", flw_ref: dpm.reference || "",
          }));
        }
        if (owner) {
          const newVa = JSON.parse(await env.KV.get("inv:" + inv.id + ":va") || "{}");
          await sendMail(env, owner.email,
            "DocOga invoice " + inv.id + " — we received the wrong amount",
            "We received a transfer that did not match invoice " + inv.id + " (expected exactly " + inv.total + " NGN).\n\n" + (newVa.account ? "Use this fresh account instead (it replaces the old one):\nBank: " + newVa.bank + "\nAccount: " + newVa.account + "\nAmount: exactly " + inv.total + " NGN\n\n" : "A fresh transfer account will appear in your DocOga account.") + "\n\nYour team stays paused until the exact amount lands — no call, no WhatsApp, this is automatic.\n\n— DocOga, Abuja\nhttps://docoga.com.ng",
            mailShell(`<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">Invoice ${htmlEsc(inv.id)}</h2><p style="margin:0 0 12px;font-size:14px;color:#33415C;line-height:1.6">The transfer we received didn't match the exact amount of <b>${inv.total} NGN</b>.</p>${newVa.account ? `<p style="margin:0 0 12px;font-size:14px;color:#33415C;line-height:1.6">Fresh account: <b>${htmlEsc(newVa.bank)}</b> · <b>${htmlEsc(newVa.account)}</b></p>` : ""}<p style="margin:0;font-size:14px;color:#33415C;line-height:1.6">This is automatic — once the exact amount lands, your team activates by itself.</p>`)
          );
        }
      } catch (e) {
        console.error(`[docoga-inv] wrong_amount_reissue_failed reason=${safeMailFailureReason(e)}`);
      }
      return true;
    }
    // Correct amount → activate (annual licence from today)
    const teamRaw = await env.KV.get("team:" + inv.team);
    let team = null; if (teamRaw) { try { team = JSON.parse(teamRaw); } catch (e) {} }
    if (team) {
      const end = new Date(Date.now() + 365 * 864e5);
      team.status = "active"; team.expiry = end.toISOString().slice(0, 10);
      await env.KV.put("team:" + inv.team, JSON.stringify(team));
    }
    inv.status = "paid"; inv.paid_at = new Date().toISOString(); inv.received_amount = amt;
    if (d.flw_ref) inv.flw_ref = String(d.flw_ref);
    await env.KV.put("inv:" + inv.id, JSON.stringify(inv));
    try {
      let invIndex = []; try { invIndex = JSON.parse(await env.KV.get("teaminv:" + inv.team) || "[]"); } catch (e) {}
      const i = invIndex.findIndex(x => x && x.id === inv.id);
      if (i >= 0) { invIndex[i].status = "paid"; invIndex[i].paid_at = inv.paid_at; await env.KV.put("teaminv:" + inv.team, JSON.stringify(invIndex)); }
    } catch (e) {}
    try {
      if (team && owner) {
        await sendMail(env, owner.email,
          "Your " + team.name + " team is live on DocOga",
          "Payment received — invoice " + inv.id + " (" + inv.total + " NGN incl. VAT) is paid.\n\n" + team.name + " is now active for 12 months. Sign in and invite your team — each member signs in with their own email and every document carries your firm's name and logo.\n\nhttps://docoga.com.ng\n\n— DocOga, Abuja",
          mailShell(`<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">${htmlEsc(team.name)} is live 🎉</h2><p style="margin:0 0 12px;font-size:14px;color:#33415C;line-height:1.6">Invoice <b>${htmlEsc(inv.id)}</b> — <b>${inv.total} NGN</b> (incl. VAT) — received. Your team is active for 12 months.</p><p style="margin:0;font-size:14px;color:#33415C;line-height:1.6">Next: sign in and invite your team. Every document carries your firm's name and logo.</p>`)
        );
      }
    } catch (e) {
      console.error(`[docoga-mail] biz_activate_email_not_accepted reason=${safeMailFailureReason(e)}`); // activation is already stored
    }
    return true;
  }
  return false;
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
  const ids = [d.reference, d.tx_ref, d.id, d.flw_ref].filter((x) => x !== undefined && x !== null && String(x).length > 0).map(String);
  if (isCompleted && succeeded && d.currency === "NGN" && await handleInvoiceWebhook(env, d, ids))
    return new Response("ok", { status: 200 }); // Business invoice handled — never mint a retail code for it
  const amt = d.amount && typeof d.amount === "object" ? Number(d.amount.value) : Number(d.amount);
  const paid = isCompleted && succeeded && d.currency === "NGN" && amt >= PRICE_NGN;
  if (!paid) return new Response("ignored", { status: 200 });
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

/* The buyer's email, from whichever shape the charge object carries (v4 charge
   payloads nest it under customer; some redirects pass it as a query param).
   Returns "" when none is found — issuing a code must NEVER fail just because
   the email is missing. Capturing it matters: delivery email + the day-27
   renewal reminder both depend on it. */
function buyerEmailFromCharge(charge, url) {
  try {
    const c = charge || {};
    const cust = c.customer || {};
    const candidates = [
      cust.email, c.customer_email, c.email,
      c.payment_method && c.payment_method.email,
      url && url.searchParams.get("email"),
    ];
    for (const e of candidates) {
      const s = String(e == null ? "" : e).trim();
      if (s && s.length <= 254 && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(s)) return s;
    }
  } catch (e) {}
  return "";
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
    // Email captured from the charge → buyer gets the pass email + magic link,
    // and the day-27 renewal reminder can reach them. Was "" before: buyers who
    // came through the payment-link redirect were invisible to the reminder cron.
    const code = await issueCode(env, { email: buyerEmailFromCharge(charge, url), ref: matched });
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
      "Access-Control-Allow-Headers": "Content-Type,X-DocOga-Key,Authorization",
      "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    /* Public brand assets (served from KV — works even while the site CDN is behind) */
    if (url.pathname === "/assets/email-banner.jpg") {
      const img = await env.KV.get("asset:email-banner", "arrayBuffer");
      if (!img) return new Response("not found", { status: 404 });
      return new Response(img, { headers: { "Content-Type": "image/jpeg", "Cache-Control": "public, max-age=31536000, immutable", "Access-Control-Allow-Origin": "*" } });
    }

    try {
      if (url.pathname === "/") {
      let lw = null;
      try { const ts = await env.KV.get("debug:last-webhook-ts", { cacheTtl: 60 }); if (ts) lw = Math.round((Date.now() - Number(ts)) / 60000); } catch (e) {}
      return json({ ok: true, service: "docoga-pass", lastWebhookMinutesAgo: lw, priceNGN: PRICE_NGN }, cors);
    }
      if (url.pathname === "/issue" && request.method === "POST") return await handleIssue(request, env, cors);
      if (url.pathname === "/resend-email" && request.method === "POST") return await handleResendEmail(request, env, cors);
      if (url.pathname === "/flw-webhook" && request.method === "POST") return await handleFlwWebhook(request, env, cors);
      if (url.pathname === "/verify" && request.method === "GET") return await handleVerify(url, env, cors);
      if (url.pathname === "/activate" && request.method === "GET") return await handleActivate(url, env, cors);
      if (url.pathname === "/business/waitlist" && request.method === "POST") return await handleBusinessWaitlist(request, env, cors);
      if (url.pathname === "/business/login" && request.method === "POST") return await handleBusinessLogin(request, env, cors);
      if (url.pathname === "/business/login" && request.method === "GET") return await handleBusinessLoginVerify(url, env, cors);
      if (url.pathname === "/business/team" && request.method === "GET") return await handleBusinessTeam(request, env, cors);
      if (url.pathname === "/business/team/brand" && request.method === "PUT") return await handleBusinessBrand(request, env, cors);
      if (url.pathname === "/business/team/seats" && request.method === "POST") return await handleBusinessSeats(request, env, cors);
      if (url.pathname === "/business/teams" && request.method === "POST") return await handleBusinessTeams(request, env, cors);
      if (url.pathname === "/business/team/charge" && request.method === "POST") return await handleBusinessCharge(request, env, cors);
      if (url.pathname === "/business/team/invoices" && request.method === "GET") return await handleBusinessInvoices(request, env, cors);
      if (url.pathname.startsWith("/business/invoice/") && request.method === "GET") {
        const parts = url.pathname.split("/");
        if (parts.length === 4) return await handleBusinessInvoice(decodeURIComponent(parts[3]), request, env, cors);
      }
      return json({ ok: false, error: "not found" }, cors, 404);
    } catch (e) {
      return json({ ok: false, error: String((e && e.message) || e) }, cors, 500);
    }
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil((async () => {
      try { await dailyRenewalReminders(env); } catch (e) {}
    })());
  },
};
