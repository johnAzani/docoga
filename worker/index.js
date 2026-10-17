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
 *   POST /business/team/renew     Phase 4 (C9): owner renewal at purchase price
 *                       (active within 90d of expiry, or grace, or free) →
 *                       renewal invoice via the same transfer/card machinery.
 *   POST /business/team/usage     Phase 4 (C8): best-effort monthly usage meter
 *                       (KV incr, capped at 2× band; soft caps only, §6.4).
 *   scheduled() (daily 07:00)    Phase 4 (C9): T-90/30/7 renewal emails,
 *                       expiry→grace(14d)→free, 90-day retention then delete
 *                       (invoices kept), 100%/150% monthly overage emails.
 *   GET  /business/invoice/:id    C10 (Phase 3): authoritative invoice as a
 *                       printable HTML document (print → Save as PDF in the
 *                       browser — no PDF lib, ₦0; binary .pdf is a v2 upgrade
 *                       if teams demand attachments). Any seat of the team;
 *                       other teams' ids are 404 (no enumeration).
 *   /admin/*            OWNER DASHBOARD API (12 Oct 2026) — revenue, passes,
 *                       teams, leads, webhook health + direct-sale issue /
 *                       revoke / extend. Passphrase login → 12h KV-backed
 *                       session. 503 admin_disabled unless BOTH
 *                       ADMIN_PASSPHRASE and ADMIN_AUTH_SECRET are set.
 *                       See ADMIN_DASHBOARD.md for the whole design.
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
 *   ADMIN_PASSPHRASE    the owner's dashboard passphrase (secret). Unset = the
 *                       whole /admin/* surface is 503 admin_disabled (fail-closed)
 *   ADMIN_AUTH_SECRET   long random string (secret) — signs admin session
 *                       tokens. Rotating it logs every admin session out.
 *                       Must NOT equal ADMIN_PASSPHRASE or TEAM_AUTH_SECRET.
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

/* ---------- Owner ledger ----------
 * Every number the dashboard shows comes from an ATOMIC day counter (KV.incr),
 * never from a keyspace scan on a request path. Why: a Workers Free invocation
 * gets 10 ms of CPU and ~1 000 KV ops, so "SELECT *"-style dashboards are the
 * classic thing that works at 40 customers and dies at 4 000. Counting at the
 * moment of the event costs one extra write per sale and reads back as a
 * handful of gets.
 * The KV record stays authoritative: anything the dashboard LISTS is re-read
 * from code:* before it is shown, so a counter that drifts never lies about a
 * specific customer's pass.
 * Field names are whitelisted: a typo must not mint an unbounded key family. */
const STAT_FIELDS = "sold,rev,offline,manual,revoked,wait,bizcreate,bizpaid,bizrev".split(",");

/* ---------- Channel attribution (17 Oct 2026) ----------
 * Every link the social lanes post carries `?s=<tag>`; the site keeps the first tag it saw
 * (localStorage, 30 days) and sends it with the checkout tap (POST /tap) and the /verify
 * call. Two whitelisted families of weekly counters — never a key per visitor, never an
 * email — so the Monday scorecard can say which channel *sold* a pass, not only which one
 * got likes. A counter must never fail the money path. */
const SRC_TAGS = { tg: "telegram", fb: "facebook", ig: "instagram", th: "threads", li: "linkedin", tt: "tiktok", yt: "youtube", wa: "whatsapp", google: "google", direct: "direct" };
const SRC_KINDS = ["checkout", "sale"];
const SRC_WEEKS = 5; // weeks the snapshot reports (28 days + the current one)
function srcName(raw) {
  const t = String(raw || "").toLowerCase().slice(0, 12);
  if (!t) return "direct";
  if (SRC_TAGS[t]) return SRC_TAGS[t];
  const byName = Object.keys(SRC_TAGS).map(k => SRC_TAGS[k]);
  return byName.indexOf(t) >= 0 ? t : "other";
}
function isoWeek(ms) {
  const d = new Date(ms); d.setUTCHours(0, 0, 0, 0);
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const y0 = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return d.getUTCFullYear() + "-W" + String(Math.ceil(((d - y0) / 864e5 + 1) / 7)).padStart(2, "0");
}
async function srcBump(env, kind, raw) {
  // One small JSON row per (kind, ISO week): {channel: n}. Read-modify-write rather than one
  // atomic counter per channel because the snapshot must stay cheap (10 reads for 5 weeks ×
  // 2 kinds, inside /admin/data's budget). Taps are a handful a day, so the race window is
  // academic; the money path itself never depends on this.
  if (SRC_KINDS.indexOf(kind) < 0) return;
  try {
    const key = "src:" + kind + ":" + isoWeek(Date.now());
    let row = {};
    try { row = JSON.parse(await env.KV.get(key) || "{}"); } catch (e) {}
    if (!row || typeof row !== "object") row = {};
    const name = srcName(raw);
    row[name] = Number(row[name] || 0) + 1;
    await env.KV.put(key, JSON.stringify(row), { expirationTtl: 60 * 86400 });
  } catch (e) { /* attribution never breaks a sale */ }
}
async function readSources(env) {
  const weeks = []; for (let i = 0; i < SRC_WEEKS; i++) weeks.push(isoWeek(Date.now() - i * 7 * 864e5));
  const out = {};
  for (const kind of SRC_KINDS) {
    out[kind] = {};
    const rows = await Promise.all(weeks.map(w => env.KV.get("src:" + kind + ":" + w, { cacheTtl: 300 }).catch(() => null)));
    weeks.forEach((w, i) => { let row = {}; try { row = JSON.parse(rows[i] || "{}"); } catch (e) {} out[kind][w] = (row && typeof row === "object") ? row : {}; });
  }
  return out;
}
async function handleTap(request, env, cors) {
  let body = null;
  try { body = await request.json(); } catch (e) {}
  const kind = body && String(body.kind || "");
  if (SRC_KINDS.indexOf(kind) < 0 || kind === "sale") return json({ ok: false }, cors, 400); // sales are counted by /verify, never self-reported
  await srcBump(env, kind, body.src);
  return json({ ok: true }, cors);
}
const STAT_TTL_SEC = 400 * 86400; // outlives any dashboard window we would want
const EXP_INDEX_TTL_SEC = 130 * 86400; // buckets are only interesting around their own date
const EXP_INDEX_CAP = 300; // max codes remembered per expiry-date

async function statBump(env, field, amount = 1) {
  if (STAT_FIELDS.indexOf(field) < 0) return;
  const n = Number(amount);
  if (!isFinite(n) || n === 0) return;
  try {
    await env.KV.incr("stat:" + field + ":" + new Date().toISOString().slice(0, 10), n, { expirationTtl: STAT_TTL_SEC });
  } catch (e) { /* the money path never fails for a counter */ }
}

/** Remember which codes expire on a given date, so "expiring soon" and
 *  "active passes" are 1 get per day instead of a scan of every code. */
async function expIndexAdd(env, code, expMs) {
  if (!code || !expMs) return;
  const day = new Date(expMs).toISOString().slice(0, 10);
  try {
    const key = "adm:exp:" + day;
    let arr = [];
    try { arr = JSON.parse(await env.KV.get(key, { cacheTtl: 60 }) || "[]"); } catch (e) {}
    if (!Array.isArray(arr)) arr = [];
    if (arr.indexOf(code) < 0) {
      arr.push(code);
      await env.KV.put(key, JSON.stringify(arr.slice(-EXP_INDEX_CAP)), { expirationTtl: EXP_INDEX_TTL_SEC });
    }
  } catch (e) {}
}

/** Create a code, remember it in KV, email the buyer. Returns the code.
 * `amount` is what the owner actually received for it: the webhook path passes
 * PRICE_NGN implicitly, a dashboard sale carries the naira the owner typed (0 =
 * a comp/gift, which is then counted but not revenue). */
async function issueCode(env, { email, ref, source = "online", days = 30, note = "", amount = null }) {
  const code = makeCode();
  const span = Math.min(Math.max(Number(days) || 30, 1), 365) * 864e5;
  const rec = { code, email: email || "", ref: ref || "", issuedAt: Date.now(), used: false, source, exp: Date.now() + span }; // dies 30 days from purchase
  if (note) rec.note = String(note).slice(0, 120);
  await env.KV.put("code:" + code, JSON.stringify(rec));
  if (ref) await env.KV.put("ref:" + ref, code); // idempotency: ref -> code
  if (source === "manual") await statBump(env, "manual");
  else await statBump(env, "sold");
  const ngn = amount === null ? (source === "online" ? PRICE_NGN : 0) : Math.max(0, Math.round(Number(amount) || 0));
  if (ngn > 0) await statBump(env, "rev", ngn);
  await expIndexAdd(env, code, rec.exp);
  await adminEmailIndex(env, rec.email, code); // support lookup by email, for every path
  await adminRecentPush(env, { kind: source, code, email: rec.email || "", ngn, days: Math.round(span / 864e5) });
  try {
    if (email) await emailCode(env, email, code);
  } catch (e) {
    // Never log the recipient, pass code, provider response body, or secret.
    // A payment/pass remains valid even when the separate email hand-off fails.
    console.error(`[docoga-mail] pass_email_not_accepted reason=${safeMailFailureReason(e)}`);
    rec.mailFailed = true;
    try { await env.KV.put("code:" + code, JSON.stringify(rec)); } catch (e2) {}
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
  await statBump(env, "wait"); // lead counter: the waitlist is counted, never scanned, on the dashboard
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
  // Phase 4 (C9/C8): the portal needs the renewal price (owner only — renewal is
  // a money action) and the monthly usage meter (any seat; the dashboard shows
  // the allowance line).
  let renewal = undefined;
  if (s.role === "owner" && ["active", "grace", "free"].includes(s.team.status)) {
    const p = teamRenewalPrice(s.team);
    renewal = { base: p.base, vat: p.vat, total: p.total, expiry: s.team.expiry, status: s.team.status };
  }
  let usage = undefined;
  if (teamLive(s.team)) {
    const month = new Date().toISOString().slice(0, 7);
    usage = { used: Number((await env.KV.get("team:" + s.id + ":usage:" + month)) || "0"), band: Number(s.team.docs) || 100 };
  }
  return json({
    ok: true,
    team: { id: s.id, slug: s.team.slug, name: s.team.name, status: s.team.status, expiry: s.team.expiry, plan: s.team.plan },
    email: s.email, role: s.role,
    seats: publicSeats(await loadSeats(env, s.id), s),
    brand,
    // Unpaid teams need the published quote to render checkout (C3 formula)
    quote: s.team.status === "unpaid" ? businessQuote(s.team.seats, s.team.docs) : undefined,
    openInvoice: s.team.status === "unpaid" ? (await currentInvoice(env, s.id)) : undefined,
    renewal,
    usage
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
  if (team.status === "grace") return true; // 14-day grace — owner renews from the dashboard; cron caps it (then "free")
  if (team.status === "free") return true;  // downgraded — free banner until renewed; cron retires the data at 90 days
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
  await statBump(env, "bizcreate");
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
/* ---------- Phase 4 (Autonomy, 11 Oct 2026) — C8 metering + C9 renewal cron ----------
 * Renewal (dossier §6.4/§7.1, no human):
 *   - price at renewal = price at purchase (renewal_* fields stored on the team
 *     at (re)activation; fallback = published formula recomputed)
 *   - POST /business/team/renew (owner): active within 90 days of expiry, or
 *     grace (14 days post-expiry), or free (downgraded) → renewal invoice
 *     (transfer VA or card, same machinery as first purchase)
 *   - webhook on a renewal invoice extends from the FUTURE expiry if there is
 *     one (early renewal never loses days), else from now
 *   - scheduled() daily sweep: T-90/30/7 reminder emails (deduped on the team
 *     record, reset at each (re)activation); expiry → "grace" (14 days, banner
 *     off, dashboard renewal); grace-end → "free" (data kept BIZ_RETAIN_DAYS);
 *     retention end → team/brand/seats deleted, invoices KEPT (tax records),
 *     owner notified.
 * Volume (C8, §6.4 soft — no hard cut-off of in-progress documents in v1):
 *   - POST /business/team/usage: best-effort monthly counter (KV incr, capped
 *     at 2× the band — the meter is stated as best-effort, generation is
 *     browser-side exactly like the retail pass; the honest gate is v2's
 *     server-side render endpoint, out of v1 scope)
 *   - daily sweep emails the owner at 100% and 150% of the monthly band
 *     (deduped per month), suggesting a right-sized plan via business@ */
const BIZ_GRACE_DAYS = 14, BIZ_RETAIN_DAYS = 90, BIZ_RENEW_WINDOW_DAYS = 90;
function teamRenewalPrice(team) {
  if (team && team.renewal_total && team.renewal_base !== undefined && team.renewal_vat !== undefined)
    return { base: team.renewal_base, vat: team.renewal_vat, total: team.renewal_total };
  return businessQuote(team && team.seats, team && team.docs);
}
function renewalLink(env) { return (env.SITE_URL || "https://docoga.com.ng") + "/#team"; }
async function sendRenewalMail(env, team, owner, subject, body, html) {
  try { await sendMail(env, owner.email, subject, body, mailShell(html)); }
  catch (e) { console.error(`[docoga-biz] renewal_email_not_accepted reason=${safeMailFailureReason(e)}`); }
}
async function handleBusinessRenew(request, env, cors) {
  const s = await teamSession(request, env);
  if (!s) return json({ ok: false, error: "sign_in_required" }, cors, 401);
  if (s.role !== "owner") return json({ ok: false, error: "owner_only" }, cors, 403);
  const st = s.team.status;
  if (st === "unpaid") return json({ ok: false, error: "use the payment step on your team dashboard" }, cors, 400);
  if (st === "active") {
    const end = Date.parse((s.team.expiry || "") + "T23:59:59Z");
    const days = end ? Math.ceil((end - Date.now()) / 864e5) : Infinity;
    if (days > BIZ_RENEW_WINDOW_DAYS) return json({ ok: false, error: "renewals open 90 days before expiry — email business@docoga.com.ng for anything sooner" }, cors, 400);
  }
  if (st !== "active" && st !== "grace" && st !== "free") return json({ ok: false, error: "team not renewable" }, cors, 400);
  const body = await request.json().catch(() => ({ method: "transfer" }));
  const method = String((body && body.method) || "transfer");
  if (method !== "transfer" && method !== "card") return json({ ok: false, error: "method must be transfer or card" }, cors, 400);
  const existing = await currentInvoice(env, s.id);
  if (existing && existing.status === "open" && existing.kind === "renewal") {
    // Same re-issue rule as first purchase (§7.4): reuse while the VA is alive
    const va = JSON.parse(await env.KV.get("inv:" + existing.id + ":va") || "null");
    const vaAlive = va && !va.voided && (!va.expires || Date.parse(va.expires) > Date.now());
    if (method === existing.method && vaAlive) {
      return json({ ok: true, reused: true, invoice: { id: existing.id, base: existing.amount, vat: existing.vat, total: existing.total }, va, reference: existing.ref });
    }
  }
  try {
    const k = "bizrenew:" + s.id + ":" + new Date().toISOString().slice(0, 10);
    const n = Number((await env.KV.get(k)) || "0") + 1;
    await env.KV.put(k, String(n), { expirationTtl: 86400 });
    if (n > 5) return json({ ok: false, error: "too many renewal links today — try again tomorrow" }, cors, 429);
  } catch (e) {}
  const p = teamRenewalPrice(s.team); // price at purchase — no silent increases (§6.4)
  const id = "INV-" + Math.random().toString(36).slice(2, 10).toUpperCase();
  const now = new Date().toISOString();
  const inv = { id, team: s.id, kind: "renewal", amount: p.base, vat: p.vat, total: p.total, seats: s.team.seats, docs: s.team.docs, plan: s.team.plan, method, status: "open", ref: id, flw_ref: "", created: now };
  if (method === "transfer") {
    const exp = new Date(Date.now() + 7 * 864e5).toISOString();
    let pm;
    try {
      pm = await flw4Post(env, "/v1/payment_methods", {
        type: "bank_account", currency: "NGN",
        amount: p.total * 100,
        reference: id,
        note: "DocOga Business — RENEWAL — " + s.team.name + " — pay exactly " + p.total + " NGN",
        account_expiration_datetime: exp,
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
        amount: p.total * 100, currency: "NGN", reference: id,
        payment_method: { type: "generic" },
        customer: { email: s.email },
        return_url: (env.SITE_URL || "https://docoga.com.ng") + "/?team_inv=" + id,
        description: "DocOga Business — RENEWAL — " + s.team.name,
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
  let invIndex = []; try { invIndex = JSON.parse(await env.KV.get("teaminv:" + s.id) || "[]"); } catch (e) {}
  invIndex = [{ id, total: p.total, method, status: "open", created: now }].concat(invIndex).slice(0, 24);
  try { await env.KV.put("teaminv:" + s.id, JSON.stringify(invIndex)); } catch (e) {}
  const out = { ok: true, reused: false, invoice: { id, base: inv.amount, vat: inv.vat, total: inv.total }, renewal: true };
  if (method === "transfer") out.va = JSON.parse(await env.KV.get("inv:" + id + ":va"));
  else out.pay_url = inv.pay_url;
  return json(out, cors);
}
async function handleBusinessUsage(request, env, cors) {
  const s = await teamSession(request, env);
  if (!s) return json({ ok: false, error: "sign_in_required" }, cors, 401);
  if (!teamLive(s.team)) return json({ ok: false, error: "metering_active_only" }, cors, 400);
  const month = new Date().toISOString().slice(0, 7);
  const key = "team:" + s.id + ":usage:" + month;
  const band = Number(s.team.docs) || 100;
  let used = Number((await env.KV.get(key)) || "0");
  if (used >= band * 2) return json({ ok: true, used, band, capped: true }); // best-effort meter: stop counting past 2× the band
  try { used = Number(await env.KV.incr(key, 1, { expirationTtl: 45 * 86400 })) || (used + 1); } catch (e) { used += 1; }
  return json({ ok: true, used, band, capped: used >= band * 2 });
}
async function sweepOneBusinessTeam(env, team, now) {
  const id = team.id;
  const seats = await loadSeats(env, id);
  const owner = seats.find(x => x.role === "owner");
  if (team.status === "active") {
    const end = Date.parse((team.expiry || "") + "T23:59:59Z");
    let changed = false;
    if (end) {
      const days = Math.ceil((end - now) / 864e5);
      if (days < 0) {
        // Expiry passed → 14-day grace: branding off (banner back), renewal stays self-serve
        team.status = "grace";
        team.grace_until = new Date(now + BIZ_GRACE_DAYS * 864e5).toISOString();
        changed = true;
        if (owner) await sendRenewalMail(env, team, owner,
          "DocOga: " + team.name + " — 14-day grace period, branding paused",
          "Your " + team.name + " licence expired on " + (team.expiry || "the last day") + ".\n\nYou have 14 days to renew — nothing is lost. During grace, documents show the DocOga banner instead of your firm's branding; your seats, branding and invoices stay exactly as they are.\n\nRenew now (same price you paid): sign in → Team dashboard → Renew (bank transfer or card).\n" + renewalLink(env) + "\n\nIf the 14 days run out, the team moves to the free tier and its data is kept 90 days.\n\n— DocOga, Abuja",
          `<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">14-day grace period</h2><p style="margin:0 0 12px;font-size:14px;color:#33415C;line-height:1.6">Nothing is lost — renew from your team dashboard at the price you paid, and branding comes straight back.</p>`);
        await env.KV.put("team:" + id, JSON.stringify(team));
        return; // just flipped to grace — no overage metering for a non-active team
      } else if (days <= 7 && !team.rem7) {
        // fire the MOST URGENT pending milestone and consume the coarser ones
        // (a team first seen at T-26 gets the T-30 notice, not a stale
        // "window open" email a moment later)
        team.rem7 = true; team.rem30 = true; team.rem90 = true; changed = true;
        const price = teamRenewalPrice(team);
        if (owner) await sendRenewalMail(env, team, owner,
          "DocOga: " + team.name + " renews in " + days + " days — " + price.total + " NGN",
          "Your " + team.name + " licence (renewal price " + price.total + " NGN incl. VAT — the price you paid) expires on " + team.expiry + ".\n\nRenew from your team dashboard — bank transfer or card, same price, automatic activation:\n" + renewalLink(env) + "\n\nOr reply to business@docoga.com.ng. This is automatic — no WhatsApp, no chasing.\n\n— DocOga, Abuja",
          `<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">Renews in ${days} day${days === 1 ? "" : "s"}</h2><p style="margin:0 0 12px;font-size:14px;color:#33415C;line-height:1.6">${price.total} NGN (incl. VAT) — the price you paid. Renew from the team dashboard: transfer or card, automatic activation.</p>`);
      } else if (days <= 30 && !team.rem30) {
        team.rem30 = true; team.rem90 = true; changed = true; // consume the stale T-90 milestone too
        const price = teamRenewalPrice(team);
        if (owner) await sendRenewalMail(env, team, owner,
          "DocOga: " + team.name + " renews in " + days + " days — plan ahead",
          "Heads-up: your " + team.name + " licence expires on " + team.expiry + " (" + days + " days). Renewal is " + price.total + " NGN incl. VAT — the price you paid, no increase.\n\nRenew from your team dashboard when it suits you (renewals open 90 days before expiry):\n" + renewalLink(env) + "\n\n— DocOga, Abuja",
          `<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">Renews in ${days} days</h2><p style="margin:0;font-size:14px;color:#33415C;line-height:1.6">Renewal stays at your purchase price: ${price.total} NGN (incl. VAT). Dashboard → Renew, transfer or card.</p>`);
      } else if (days <= BIZ_RENEW_WINDOW_DAYS && !team.rem90) {
        team.rem90 = true; changed = true;
        const price = teamRenewalPrice(team);
        if (owner) await sendRenewalMail(env, team, owner,
          "DocOga: " + team.name + " renewal window is open",
          "Your " + team.name + " licence is within 90 days of expiry (" + team.expiry + "). The renewal window is open from now — " + price.total + " NGN incl. VAT, the price you paid.\n\nRenew from your team dashboard (bank transfer or card) and the next 12 months stack on — early renewal never loses days.\n" + renewalLink(env) + "\n\n— DocOga, Abuja",
          `<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">Renewal window open</h2><p style="margin:0;font-size:14px;color:#33415C;line-height:1.6">${price.total} NGN (incl. VAT) — your purchase price. Renewal stacks on your remaining days.</p>`);
      }
    }
    // C8 soft caps (§6.4): email at 100% and 150% of the monthly band, deduped
    // per month. NO hard cut-off of in-progress documents in v1 — stated honestly.
    const month = new Date(now).toISOString().slice(0, 7);
    const band = Number(team.docs) || 100;
    const used = Number((await env.KV.get("team:" + id + ":usage:" + month)) || "0");
    if (used >= band * 1.5 && team.usage150 !== month) {
      team.usage150 = month; changed = true;
      if (owner) await sendRenewalMail(env, team, owner,
        "DocOga: " + team.name + " is at " + Math.round(used / band * 100) + "% of its monthly document allowance",
        "This month " + team.name + " has generated about " + used + " documents against a " + band + "/month allowance (" + Math.round(used / band * 100) + "%).\n\nNothing is cut off — the v1 limit is soft and in-progress documents are never interrupted. But you're well above the band, so let's right-size the plan: email business@docoga.com.ng (or write from the team dashboard) and we'll confirm an upgrade by email, with the written record.\n\n— DocOga, Abuja",
        `<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">${Math.round(used / band * 100)}% of monthly allowance</h2><p style="margin:0;font-size:14px;color:#33415C;line-height:1.6">Soft limit — nothing is cut off. If this is the new normal, email business@docoga.com.ng and we'll right-size the plan by email.</p>`);
    } else if (used >= band && team.usage100 !== month) {
      team.usage100 = month; changed = true;
      if (owner) await sendRenewalMail(env, team, owner,
        "DocOga: " + team.name + " hit 100% of its monthly document allowance",
        "Heads-up: " + team.name + " has generated about " + used + " documents this month — the full " + band + "/month allowance.\n\nThe limit is soft (dossier-honest): documents keep generating and in-progress ones are never interrupted. If you keep hitting the band, an upgrade keeps things smooth — email business@docoga.com.ng and a human confirms it by email.\n\n— DocOga, Abuja",
        `<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">100% of monthly allowance</h2><p style="margin:0;font-size:14px;color:#33415C;line-height:1.6">Soft limit — nothing stops. If you're consistently above the band, we'll right-size the plan by email.</p>`);
    }
    if (changed) await env.KV.put("team:" + id, JSON.stringify(team));
    return;
  }
  if (team.status === "grace") {
    const limit = Date.parse(team.grace_until || "2000-01-01T00:00:00Z");
    if (limit && now >= limit) {
      // Grace ended → free tier; data (brand, seats, history) kept BIZ_RETAIN_DAYS
      team.status = "free";
      team.retire_at = new Date(now + BIZ_RETAIN_DAYS * 864e5).toISOString();
      await env.KV.put("team:" + id, JSON.stringify(team));
      if (owner) await sendRenewalMail(env, team, owner,
        "DocOga: " + team.name + " moved to the free tier — data kept 90 days",
        "The 14-day grace period for " + team.name + " has ended, so the team is now on the free tier: documents show the DocOga banner and the firm branding is paused.\n\nNothing is deleted yet — your seats, branding and invoice history are kept for 90 days. Renewing from the team dashboard restores everything at the price you paid:\n" + renewalLink(env) + "\n\nIf the 90 days pass without a renewal, the team data is deleted (invoices remain available from us on request).\n\n— DocOga, Abuja",
        `<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">Moved to the free tier</h2><p style="margin:0 0 12px;font-size:14px;color:#33415C;line-height:1.6">Nothing deleted — 90 days of data retention. Renew from the team dashboard at your purchase price and branding comes straight back.</p>`);
    }
    return;
  }
  if (team.status === "free") {
    const retire = Date.parse(team.retire_at || "2000-01-01T00:00:00Z");
    if (retire && now >= retire) {
      // 90-day retention ended: delete team data; KEEP invoices (tax records)
      if (owner) await sendRenewalMail(env, team, owner,
        "DocOga: " + team.name + " — team data deleted, invoices kept",
        "As agreed after the 90-day retention period, the " + team.name + " team data (branding, seats) has been deleted. Your invoices are kept — email business@docoga.com.ng and we'll send any of them by email.\n\nIf you want the team back, set it up again from docoga.com.ng — it takes 2 minutes.\n\n— DocOga, Abuja",
        `<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">Team data deleted</h2><p style="margin:0;font-size:14px;color:#33415C;line-height:1.6">Invoices are kept. Email business@docoga.com.ng for any of them. Re-setup takes 2 minutes.</p>`);
      for (const x of seats) await env.KV.delete("seatidx:" + String(x.email || "").toLowerCase());
      for (const x of seats) await env.KV.delete("auth:" + String(x.email || "").toLowerCase());
      await env.KV.delete("team:" + id + ":seats");
      await env.KV.delete("brand:" + id);
      await env.KV.delete("team:" + id + ":inv");
      await env.KV.delete("teaminv:" + id);
      await env.KV.delete("team:" + id);
      console.log("[docoga-biz] team_retired id=" + id);
    }
  }
}
async function dailyBusinessRenewals(env) {
  const now = Date.now();
  let cursor = undefined;
  do {
    const page = await env.KV.list({ prefix: "team:", cursor });
    for (const k of page.keys) {
      // team:{id} only — team:{id}:seats / :usage / :inv share the prefix
      if (String(k.name).split(":").length !== 2) continue;
      let team = null;
      try { team = JSON.parse(await env.KV.get(k.name) || "null"); } catch (e) {}
      if (!team || !team.id || !["active", "grace", "free"].includes(team.status)) continue;
      try { await sweepOneBusinessTeam(env, team, now); } catch (e) { /* one bad record never stops the loop */ }
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
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
    // Correct amount → activate. Renewal-aware (Phase 4, C9): if the team
    // already has a FUTURE expiry (early renewal), the new year stacks on top
    // of it — no days lost. First activation has no future expiry → from now.
    // Renewal price at purchase is remembered (dossier §6.4: no silent
    // increases) and the reminder dedupe flags reset for the next cycle.
    const teamRaw = await env.KV.get("team:" + inv.team);
    let team = null; if (teamRaw) { try { team = JSON.parse(teamRaw); } catch (e) {} }
    if (team) {
      const cur = Date.parse((team.expiry || "") + "T23:59:59Z");
      const base = (cur > Date.now()) ? cur : Date.now();
      const end = new Date(base + 365 * 864e5);
      team.status = "active"; team.expiry = end.toISOString().slice(0, 10);
      team.renewal_base = inv.amount; team.renewal_vat = inv.vat; team.renewal_total = inv.total;
      team.rem90 = false; team.rem30 = false; team.rem7 = false;
      await env.KV.put("team:" + inv.team, JSON.stringify(team));
    }
    inv.status = "paid"; inv.paid_at = new Date().toISOString(); inv.received_amount = amt;
    await statBump(env, "bizpaid");
    await statBump(env, "bizrev", Number(inv.total) || 0);
    if (d.flw_ref) inv.flw_ref = String(d.flw_ref);
    await env.KV.put("inv:" + inv.id, JSON.stringify(inv));
    try {
      let invIndex = []; try { invIndex = JSON.parse(await env.KV.get("teaminv:" + inv.team) || "[]"); } catch (e) {}
      const i = invIndex.findIndex(x => x && x.id === inv.id);
      if (i >= 0) { invIndex[i].status = "paid"; invIndex[i].paid_at = inv.paid_at; await env.KV.put("teaminv:" + inv.team, JSON.stringify(invIndex)); }
    } catch (e) {}
    try {
      if (team && owner) {
        const isRenewal = inv.kind === "renewal";
        await sendMail(env, owner.email,
          isRenewal ? ("Your " + team.name + " licence is renewed on DocOga") : ("Your " + team.name + " team is live on DocOga"),
          "Payment received — invoice " + inv.id + " (" + inv.total + " NGN incl. VAT) is paid.\n\n" + (isRenewal ? team.name + " is active again for 12 months — branding is back on every document. " : team.name + " is now active for 12 months. Sign in and invite your team — each member signs in with their own email and every document carries your firm's name and logo. ") + "\n\nhttps://docoga.com.ng\n\n— DocOga, Abuja",
          mailShell(`<h2 style="margin:0 0 12px;font-size:20px;color:#0B1B3F">${isRenewal ? htmlEsc(team.name) + " is renewed ✅" : htmlEsc(team.name) + " is live 🎉"}</h2><p style="margin:0 0 12px;font-size:14px;color:#33415C;line-height:1.6">Invoice <b>${htmlEsc(inv.id)}</b> — <b>${inv.total} NGN</b> (incl. VAT) — received. Your team is active for 12 months.</p><p style="margin:0;font-size:14px;color:#33415C;line-height:1.6">${isRenewal ? "Branding is back on every document your team produces." : "Next: sign in and invite your team. Every document carries your firm's name and logo."}</p>`)
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
    await srcBump(env, "sale", url.searchParams.get("src"));
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
  await srcBump(env, "sale", url.searchParams.get("src"));
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
    await expIndexAdd(env, rec.code, rec.exp); // the carry pushed the expiry: index the new date too
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
      await statBump(env, "offline"); // the sale happened on WhatsApp; this is the only signal we get
      await expIndexAdd(env, key, rec.exp);
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
  if (rec.revoked)
    return json({ ok: false, error: "This pass was cancelled by DocOga. If that looks wrong, WhatsApp support — +234 902 185 2845." }, cors, 403);
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

/* ============================================================================
 * OWNER ADMIN DASHBOARD — the app owner's read/write surface over the same KV
 * the money paths write to. UI: site/admin.html (public, inert, no secrets).
 * Doc: ADMIN_DASHBOARD.md. Rules, each of them earned:
 *
 * 1. FAIL CLOSED. ADMIN_PASSPHRASE or ADMIN_AUTH_SECRET missing → every
 *    /admin/* route answers 503 admin_disabled. A half-configured admin is a
 *    hole, not a feature (same pattern as TEAM_AUTH_SECRET / RESEND_EMAIL_ENABLED).
 * 2. NO SECRET EVER SHIPS. site/admin.html and the Android APK contain only the
 *    URL of this API. The passphrase is typed by the owner and exchanged for a
 *    12-hour session token; nothing in the repo or the bundle can be reversed
 *    into access.
 * 3. SESSION = random sid + HMAC(ADMIN_AUTH_SECRET) + a KV record that is
 *    re-checked on EVERY call. "Log out everywhere" deletes the records, so a
 *    stolen token dies immediately instead of living out its expiry.
 * 4. BEARER HEADER, NOT A COOKIE. The site and this Worker are different
 *    origins and no credential is attached automatically → no CSRF surface,
 *    and the same token works from a browser and from a WebView app.
 * 5. NEVER SCAN THE KEYSPACE ON A REQUEST PATH. Workers Free gives an
 *    invocation 10 ms of CPU and ~1 000 KV operations, so a dashboard that
 *    reads every `code:` key works at 40 customers and dies at 4 000 — i.e.
 *    exactly when the product succeeds. Everything here is either an atomic
 *    day counter (stat:*), a small capped index written at the moment of the
 *    event (adm:exp:*, adm:em:*, adm:recent), or a 6-hour snapshot (adm:snap)
 *    built by the daily cron. The KV record stays authoritative: every code
 *    the dashboard shows is re-read before it is rendered.
 * 6. PII DISCIPLINE. Customers' emails are shown (it is the owner's own
 *    customer list) but the stored raw webhook body is never echoed, virtual
 *    account numbers are masked to their last 4 digits, and no route returns
 *    any secret value.
 *
 * Routes (session required except /admin/login):
 *   POST /admin/login     {pass} → {token, expiresInSeconds}  (5 strikes / 30 min per IP)
 *   GET  /admin/me        who am I + when this session expires
 *   POST /admin/logout    drop this session
 *   GET  /admin/data      today's counters + snapshot + webhook health   (~13 KV reads)
 *   POST /admin/snapshot  rebuild the snapshot (throttled to 1 per 5 min)
 *   GET  /admin/codes?q=  exact code / email / payment-ref lookup; &deep=1 = bounded scan
 *   POST /admin/issue     direct sale: mint a code, optional email, days, naira, note
 *   POST /admin/resend    re-send the pass email for a stored code
 *   POST /admin/revoke    kill a pass now (also kills the device fence)
 *   POST /admin/extend    push a pass's synced expiry
 *   GET  /admin/sessions  list live admin sessions
 *   POST /admin/session   {sid} drop one · {all:true} drop every other one
 *   GET  /admin/social    today's posting plan vs what GitHub Actions did, last 7 days, clock health
 *   POST /admin/social/run {workflow, inputs?} ask a lane to run now (one per lane per 10 min)
 *   GET  /admin/site      website visits (Cloudflare Web Analytics, 7 + 28 days)
 * ========================================================================== */
const ADMIN_SESSION_TTL = 43200;      // 12 h, slid forward while the owner keeps using it
const ADMIN_SNAP_TTL = 6 * 3600;      // freshness target for the heavy rollup
const ADMIN_REBUILD_LOCK = 300;       // at most one rebuild per 5 min, however many tabs
const ADMIN_FAIL_LIMIT = 5;           // wrong passphrases per IP inside the window
const ADMIN_FAIL_WINDOW = 1800;       // 30 min, sliding from the last failure
const ADMIN_ISSUE_CAP = 200;          // codes mintable per day (a runaway guard, not a quota)
const ADMIN_LEDGER_DAYS = 31;         // length of the daily series in the snapshot
const ADMIN_EXP_WINDOW = 90;          // how far ahead the expiry index is read
const ADMIN_TEAM_CAP = 40;            // teams described per snapshot
const ADMIN_LEAD_CAP = 150;           // waitlist rows read per snapshot
const ADMIN_RECENT_CAP = 40;          // rolling "last events" feed
const ADMIN_SCAN_CAP = 400;           // deep-search budget (KV ops, not rows)
const ADMIN_EMAIL_CODES_CAP = 24;     // codes remembered per email
const ADMIN_DAILY = 5;                // per-day reads bundled in /admin/data (today + yesterday)

function adminReady(env) { return !!(env.KV && env.ADMIN_PASSPHRASE && env.ADMIN_AUTH_SECRET); }
function adminIp(request) {
  return ((request.headers.get("cf-connecting-ip") || request.headers.get("x-real-ip") || "unknown")
    .replace(/[^a-zA-Z0-9.:_-]/g, "").slice(0, 64)) || "unknown";
}
function adminIpMask(ip) {
  const v6 = String(ip).indexOf(":") >= 0;
  const parts = String(ip).split(v6 ? ":" : ".");
  return parts.slice(0, 2).join(v6 ? ":" : ".") + (v6 ? ":••" : ".••");
}
function adminHex(bytes) {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, "0")).join("");
}
/* Compare two secrets by their digests. A plain `===` on a guessable secret
 * leaks its prefix through timing; a compare on SHA-256 digests leaks nothing
 * about the input, and costs one hash. */
async function adminEq(a, b) {
  const x = await teamSha256Hex(String(a));
  const y = await teamSha256Hex(String(b));
  return x === y;
}
async function adminSig(env, payload) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(env.ADMIN_AUTH_SECRET), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(payload));
  let bin = ""; const bytes = new Uint8Array(mac);
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

/* Rolling feed of value events, so "what happened today" costs one get. */
async function adminRecentPush(env, row) {
  try {
    let arr = [];
    try { arr = JSON.parse(await env.KV.get("adm:recent") || "[]"); } catch (e) {}
    if (!Array.isArray(arr)) arr = [];
    arr.unshift(Object.assign({ at: Date.now() }, row));
    await env.KV.put("adm:recent", JSON.stringify(arr.slice(0, ADMIN_RECENT_CAP)));
  } catch (e) {}
}
/* email → codes, so support lookup is O(1) instead of a scan. */
async function adminEmailIndex(env, email, code) {
  if (!email || !code) return;
  try {
    const key = "adm:em:" + String(email).toLowerCase();
    let arr = [];
    try { arr = JSON.parse(await env.KV.get(key) || "[]"); } catch (e) {}
    if (!Array.isArray(arr)) arr = [];
    if (arr.indexOf(code) < 0) {
      arr.unshift(code);
      await env.KV.put(key, JSON.stringify(arr.slice(0, ADMIN_EMAIL_CODES_CAP)));
    }
  } catch (e) {}
}

async function adminSession(request, env) {
  if (!adminReady(env)) return null;
  const h = request.headers.get("authorization") || "";
  const tok = h.startsWith("Bearer ") ? h.slice(7).trim() : "";
  const dot = tok.lastIndexOf(".");
  if (dot < 16 || dot > 80) return null;
  const sid = tok.slice(0, dot), sig = tok.slice(dot + 1);
  if (!/^[a-f0-9]{16,64}$/.test(sid)) return null;
  if (!(await adminEq(sig, await adminSig(env, "ad_" + sid)))) return null; // signature over the sid only
  const raw = await env.KV.get("adm:sess:" + sid); // revocation is instant because this is never cached
  if (!raw) return null;
  let s = null; try { s = JSON.parse(raw); } catch (e) {}
  const now = Math.floor(Date.now() / 1000);
  if (!s || Number(s.exp) <= now) return null;
  if (s.exp - now < ADMIN_SESSION_TTL / 2) { // slide the expiry while it is in use
    s.exp = now + ADMIN_SESSION_TTL;
    try { await env.KV.put("adm:sess:" + sid, JSON.stringify(s), { expirationTtl: ADMIN_SESSION_TTL }); } catch (e) {}
  }
  s.sid = sid;
  return s;
}

async function handleAdminLogin(request, env, cors) {
  if (!adminReady(env)) return json({ ok: false, error: "admin_disabled" }, cors, 503);
  const body = await request.json().catch(() => null);
  const pass = String((body && body.pass) || "").slice(0, 4096);
  const ip = adminIp(request);
  const fkey = "adm:fail:" + ip;
  let fails = 0;
  try { fails = Number(await env.KV.get(fkey) || "0"); } catch (e) {}
  if (fails >= ADMIN_FAIL_LIMIT)
    return json({ ok: false, error: "too many failed attempts — wait 30 minutes", retryInSec: ADMIN_FAIL_WINDOW }, cors, 429);
  if (!pass || !(await adminEq(pass, env.ADMIN_PASSPHRASE))) {
    try { await env.KV.incr(fkey, 1, { expirationTtl: ADMIN_FAIL_WINDOW }); } catch (e) {}
    return json({ ok: false, error: "wrong passphrase" }, cors, 401);
  }
  try { await env.KV.delete(fkey); } catch (e) {}
  const sid = adminHex(crypto.getRandomValues(new Uint8Array(16)));
  const now = Math.floor(Date.now() / 1000);
  const sess = { at: now, exp: now + ADMIN_SESSION_TTL, ip: adminIpMask(ip), ua: String(request.headers.get("user-agent") || "").slice(0, 90) };
  await env.KV.put("adm:sess:" + sid, JSON.stringify(sess), { expirationTtl: ADMIN_SESSION_TTL });
  try { await env.KV.put("adm:lastlogin", JSON.stringify({ at: Date.now(), ip: adminIpMask(ip) }), { expirationTtl: 400 * 86400 }); } catch (e) {}
  return json({ ok: true, token: sid + "." + await adminSig(env, "ad_" + sid), expiresInSeconds: ADMIN_SESSION_TTL }, cors);
}

/* ---------- the read path ---------- */
async function readCounters(env, date) {
  const out = {};
  const vals = await Promise.all(STAT_FIELDS.map(async (f) => {
    try { return Number(await env.KV.get("stat:" + f + ":" + date) || "0"); } catch (e) { return 0; }
  }));
  STAT_FIELDS.forEach((f, i) => { out[f] = Number(vals[i] || 0); });
  return out;
}
function adminWebhookVitals(env) {
  return (async () => {
    const v = { lastWebhookMinutesAgo: null, event: null };
    try {
      const [ts, raw] = await Promise.all([
        env.KV.get("debug:last-webhook-ts", { cacheTtl: 60 }),
        env.KV.get("debug:last-webhook", { cacheTtl: 60 }),
      ]);
      if (ts) v.lastWebhookMinutesAgo = Math.round((Date.now() - Number(ts)) / 60000);
      if (raw) { // never echo the body: it carries the buyer's email and provider ids
        let j = null; try { j = JSON.parse(raw); } catch (e) {}
        const d = (j && j.data) || {};
        v.event = {
          type: String((j && (j.type || j.event)) || "").slice(0, 40),
          status: String(d.status || "").slice(0, 20),
          amount: Number(d.amount && d.amount.value !== undefined ? d.amount.value : d.amount) || null,
          currency: String(d.currency || "").slice(0, 4),
          ref: String(d.tx_ref || d.reference || "").slice(0, 40),
        };
      }
    } catch (e) {}
    return v;
  })();
}

/** The expensive rollup: 31 days of counters, the expiry index, the team
 *  table, the lead list and a drift self-check. Runs in the daily cron and on
 *  an explicit refresh — never on an ordinary dashboard load. */
async function buildAdminSnapshot(env) {
  const now = Date.now();
  const dayMs = 864e5;
  const iso = (ms) => new Date(ms).toISOString().slice(0, 10);
  const days = [];
  for (let i = 0; i < ADMIN_LEDGER_DAYS; i++) days.push(iso(now - i * dayMs));
  const counts = await Promise.all(days.map(d => readCounters(env, d)));
  const series = days.map((d, i) => Object.assign({ date: d }, counts[i])).reverse(); // oldest → newest
  const totals = {};
  STAT_FIELDS.forEach(f => { totals[f] = series.reduce((a, x) => a + (x[f] || 0), 0); });

  // Expiry buckets: distinct codes with a future expiry, plus the ≤14-day nudge list.
  const future = new Set();
  const expiring = [];
  const buckets = [];
  for (let i = 0; i <= ADMIN_EXP_WINDOW; i++) buckets.push(iso(now + i * dayMs));
  const bucketRaw = await Promise.all(buckets.map(d => env.KV.get("adm:exp:" + d, { cacheTtl: 300 }).catch(() => null)));
  bucketRaw.forEach((raw, i) => {
    let arr = []; try { arr = JSON.parse(raw || "[]"); } catch (e) {}
    if (!Array.isArray(arr)) return;
    for (const c of arr) {
      if (typeof c !== "string" || future.has(c)) continue;
      future.add(c);
      if (i <= 14) expiring.push({ code: c, expires: buckets[i], daysLeft: i });
    }
  });
  expiring.sort((a, b) => a.daysLeft - b.daysLeft);
  // The index is advisory; the record is authoritative. Re-read the ones we are
  // about to show so a stale bucket can never print a wrong name or a revoked
  // pass as "needs a nudge". Bounded by the same cap as the table itself.
  const expiringRows = [];
  {
    const picked = expiring.slice(0, 60);
    const live = await Promise.all(picked.map(async (x) => {
      let r = null; try { r = JSON.parse(await env.KV.get("code:" + x.code, { cacheTtl: 60 }) || "null"); } catch (e) {}
      return r;
    }));
    for (let i = 0; i < picked.length; i++) {
      const r = live[i];
      if (!r || r.revoked || r.succ || Number(r.exp) <= now) continue;
      const daysLeft = Math.ceil((Number(r.exp) - now) / dayMs);
      if (daysLeft < 0 || daysLeft > 14) continue; // stale bucket entry
      expiringRows.push({ code: String(r.code), email: String(r.email || ""), expires: iso(r.exp), daysLeft, source: String(r.source || ""), note: String(r.note || "").slice(0, 120), amount: Number(r.amount) || 0 });
    }
    expiringRows.sort((a, b) => a.daysLeft - b.daysLeft);
  }

  // Keys only — no values — so "did the counter family break" costs 3 KV calls.
  let codesStored = 0, listPage = undefined, pages = 0;
  do {
    try {
      const p = await env.KV.list({ prefix: "code:", cursor: listPage });
      codesStored += p.keys.length; pages++;
      listPage = p.list_complete ? undefined : p.cursor;
    } catch (e) { listPage = undefined; }
  } while (listPage && pages < 3);

  const teams = [];
  let teamScanCapped = false;
  try {
    const p = await env.KV.list({ prefix: "team:", limit: 1000 });
    const ids = p.keys.map(k => k.name).filter(n => /^team:[A-Za-z0-9_-]+$/.test(n)).map(n => n.slice(5));
    teamScanCapped = ids.length > ADMIN_TEAM_CAP;
    const slice = ids.slice(0, ADMIN_TEAM_CAP);
    const month = iso(now).slice(0, 7);
    const rows = await Promise.all(slice.map(async (id) => {
      let t = null; try { t = JSON.parse(await env.KV.get("team:" + id) || "null"); } catch (e) {}
      if (!t) return null;
      let seats = []; try { seats = JSON.parse(await env.KV.get("team:" + id + ":seats") || "[]") || []; } catch (e) {}
      let used = 0; try { used = Number(await env.KV.get("team:" + id + ":usage:" + month) || "0"); } catch (e) {}
      let inv = []; try { inv = JSON.parse(await env.KV.get("teaminv:" + id) || "[]") || []; } catch (e) {}
      const open = inv.filter(x => x && x.status !== "paid").slice(0, 3);
      return {
        id, name: String(t.name || "").slice(0, 120), status: String(t.status || ""), plan: String(t.plan || ""),
        seats: Number(t.seats) || 0, members: Array.isArray(seats) ? seats.length : 0,
        docs: Number(t.docs) || 0, used, expiry: String(t.expiry || ""), created: String(t.created || "").slice(0, 10),
        total: Number(t.total) || 0, price: Number(t.price) || 0, segment: String(t.segment || ""),
        owner: (Array.isArray(seats) && seats.find(x => x && x.role === "owner") || {}).email || "",
        openInvoices: open.map(x => ({ id: String(x.id || "").slice(0, 40), total: Number(x.total) || 0, status: String(x.status || ""), created: String(x.created || "").slice(0, 10) })),
      };
    }));
    for (const r of rows) if (r) teams.push(r);
    teams.sort((a, b) => (a.status === "active" ? 0 : 1) - (b.status === "active" ? 0 : 1) || String(b.created).localeCompare(String(a.created)));
  } catch (e) {}

  const leads = [];
  let leadTotal = 0;
  try {
    const p = await env.KV.list({ prefix: "bizwait:", limit: 1000 });
    const keys = p.keys.map(k => k.name).filter(n => n.indexOf(":ip:") < 0);
    leadTotal = keys.length;
    const rows = await Promise.all(keys.slice(0, ADMIN_LEAD_CAP).map(async (k) => {
      let j = null; try { j = JSON.parse(await env.KV.get(k) || "null"); } catch (e) {}
      if (!j || !j.email) return null;
      return { email: String(j.email).slice(0, 254), company: String(j.company || "").slice(0, 120), segment: String(j.segment || "").slice(0, 40), at: String(j.at || "").slice(0, 24) };
    }));
    for (const r of rows) if (r) leads.push(r);
    leads.sort((a, b) => String(b.at).localeCompare(String(a.at)));
  } catch (e) {}

  let recent = []; try { recent = JSON.parse(await env.KV.get("adm:recent") || "[]") || []; } catch (e) {}
  if (!Array.isArray(recent)) recent = [];
  let lastlogin = null; try { lastlogin = JSON.parse(await env.KV.get("adm:lastlogin") || "null"); } catch (e) {}

  // Self-check: a broken counter family must be visible, not silently optimistic.
  // 17 Oct 2026: compare like with like. `code:` keys live forever; the day counters live
  // 31 days — so "every code ever vs. this month's sales" rang the alarm from the moment the
  // business was a month old (8 stored, 0 counted, on the first day the counters existed).
  // Now a baseline {codes, since} is pinned the first time this runs and rolled forward
  // every 28 days (one KV write, at most once a month); the check is "codes created since
  // the baseline vs. sales counted since the baseline", both inside the counters' window.
  let baseline = null;
  try { baseline = JSON.parse(await env.KV.get("adm:baseline") || "null"); } catch (e) {}
  const today = iso(now);
  const baselineAge = baseline && baseline.since ? Math.floor((now - Date.parse(baseline.since)) / dayMs) : null;
  if (!baseline || typeof baseline.codes !== "number" || !baseline.since || baselineAge === null || baselineAge >= 28 || baselineAge < 0) {
    baseline = { codes: codesStored, since: today };
    try { await env.KV.put("adm:baseline", JSON.stringify(baseline)); } catch (e) {}
  }
  const sinceRows = series.filter(x => x.date >= baseline.since);
  const countedSince = sinceRows.reduce((a, x) => a + (x.sold || 0) + (x.manual || 0) + (x.offline || 0), 0);
  const newCodes = Math.max(0, codesStored - baseline.codes);
  const drift = {
    codesStored, counted: totals.sold + totals.manual + totals.offline,
    since: baseline.since, baselineCodes: baseline.codes, newCodes, countedSince,
    suspect: newCodes > countedSince + 5,
  };

  const snap = {
    at: now,
    series, totals,
    sources: await readSources(env).catch(() => null), // weekly checkout taps and verified sales by channel tag
    passes: { stored: codesStored, activeEstimate: future.size, activeBasis: "distinct codes in the expiry index (an upper bound: revoked and renewed codes are only subtracted inside the 14-day verified window)", expiringWindowDays: 14, expiring: expiringRows, expiringTotal: expiring.length, indexOnly: expiring.length - expiringRows.length },
    teams, teamScanCapped,
    leads: { total: leadTotal, bySegment: leads.reduce((a, x) => { const k = x.segment || "unspecified"; a[k] = (a[k] || 0) + 1; return a; }, {}), rows: leads.slice(0, 60) },
    recent: recent.slice(0, 24),
    lastlogin,
    drift,
    windows: { ledgerDays: ADMIN_LEDGER_DAYS, expDays: ADMIN_EXP_WINDOW, scanCap: ADMIN_SCAN_CAP },
  };
  try { await env.KV.put("adm:snap", JSON.stringify(snap), { expirationTtl: 7 * 86400 }); } catch (e) {}
  return snap;
}

async function handleAdminData(request, env, cors, ctx) {
  const today = new Date().toISOString().slice(0, 10);
  const [todayC, ydayC, snapRaw, vitals] = await Promise.all([
    readCounters(env, today),
    readCounters(env, new Date(Date.now() - 864e5).toISOString().slice(0, 10)),
    env.KV.get("adm:snap", { cacheTtl: 60 }).catch(() => null),
    adminWebhookVitals(env),
  ]);
  let snap = null; let snapFresh = false;
  try { snap = JSON.parse(snapRaw || "null"); } catch (e) { snap = null; }
  if (!snap) { snap = await buildAdminSnapshot(env); snapFresh = true; } // first run ever: pay it once, inline
  else if (Date.now() - Number(snap.at || 0) > ADMIN_SNAP_TTL * 1000 && ctx && ctx.waitUntil) {
    ctx.waitUntil(rebuildThrottled(env)); // stale: answer now, rebuild after the response
  }
  let issuedToday = 0;
  try { issuedToday = Number(await env.KV.get("adm:issue:" + today) || "0"); } catch (e) {}
  return json({
    ok: true, now: Date.now(), date: today, priceNGN: PRICE_NGN, currency: "NGN",
    today: todayC, yesterday: ydayC, issuedByHandToday: issuedToday,
    snapshot: snap, snapshotAt: Number(snap && snap.at) || null, snapshotJustBuilt: snapFresh,
    health: vitals,
    limits: { issuePerDay: ADMIN_ISSUE_CAP },
  }, cors);
}

async function rebuildThrottled(env) {
  try {
    if (await env.KV.get("adm:snap:lock")) return false;
    await env.KV.put("adm:snap:lock", String(Date.now()), { expirationTtl: ADMIN_REBUILD_LOCK });
  } catch (e) { return false; }
  try { await buildAdminSnapshot(env); } catch (e) {}
  return true;
}

async function handleAdminSnapshot(request, env, cors) {
  let started = false;
  try {
    if (!(await env.KV.get("adm:snap:lock"))) {
      started = true;
      await env.KV.put("adm:snap:lock", String(Date.now()), { expirationTtl: ADMIN_REBUILD_LOCK });
    }
  } catch (e) {}
  if (!started) return json({ ok: false, error: "a refresh ran in the last 5 minutes", retryInSec: ADMIN_REBUILD_LOCK }, cors, 429);
  const snap = await buildAdminSnapshot(env);
  return json({ ok: true, snapshot: snap }, cors);
}

/* ---------- code lookup ---------- */
function adminCodeView(rec) {
  if (!rec) return null;
  const now = Date.now();
  return {
    code: String(rec.code || ""), email: String(rec.email || ""), ref: String(rec.ref || ""),
    source: String(rec.source || ""), issuedAt: Number(rec.issuedAt) || 0, exp: Number(rec.exp) || 0,
    active: !!rec.exp && rec.exp > now && !rec.revoked,
    daysLeft: rec.exp ? Math.ceil((rec.exp - now) / 864e5) : null,
    devices: Array.isArray(rec.devices) ? rec.devices.length : 0,
    revoked: !!rec.revoked, mailFailed: !!rec.mailFailed, reminded: !!rec.remindedAt,
    prev: rec.prev ? String(rec.prev) : "", succ: rec.succ ? String(rec.succ) : "",
    note: String(rec.note || ""),
  };
}
async function handleAdminCodes(request, url, env, cors) {
  const q = String(url.searchParams.get("q") || "").trim();
  const deep = url.searchParams.get("deep") === "1";
  if (!q) {
    let snap = null; try { snap = JSON.parse(await env.KV.get("adm:snap", { cacheTtl: 60 }) || "null"); } catch (e) {}
    return json({ ok: true, mode: "recent", rows: (snap && snap.recent || []).filter(x => x && x.code).map(x => ({ code: String(x.code), email: String(x.email || ""), at: Number(x.at) || 0, source: String(x.kind || x.source || "") })) }, cors);
  }
  const norm = normalizeCode(q.toUpperCase().replace(/[\s-]/g, ""));
  const direct = [];
  for (const key of ["code:" + norm, "code:" + norm.replace(/-/g, "")]) {
    let rec = null; try { rec = JSON.parse(await env.KV.get(key) || "null"); } catch (e) {}
    if (rec) { direct.push(rec); break; }
  }
  if (!direct.length) {
    let byRef = null;
    try { byRef = await env.KV.get("ref:" + q); } catch (e) {}
    if (byRef) {
      try { const r = JSON.parse(await env.KV.get("code:" + byRef) || "null"); if (r) direct.push(r); } catch (e) {}
    }
  }
  if (direct.length) return json({ ok: true, mode: "exact", rows: direct.map(adminCodeView) }, cors);
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(q)) { // email index: 1 get + one per code, capped
    let codes = [];
    try { codes = JSON.parse(await env.KV.get("adm:em:" + q.toLowerCase()) || "[]") || []; } catch (e) {}
    if (!Array.isArray(codes)) codes = [];
    const rows = await Promise.all(codes.slice(0, ADMIN_EMAIL_CODES_CAP).map(async (c) => {
      try { return adminCodeView(JSON.parse(await env.KV.get("code:" + c) || "null")); } catch (e) { return null; }
    }));
    return json({ ok: true, mode: "email", rows: rows.filter(Boolean) }, cors);
  }
  if (!deep) return json({ ok: false, error: "paste a full OGA-code, a payment reference or an email — or ask for a bounded scan with deep=1" }, cors, 400);
  // Bounded scan: one list page, get until the budget is spent, cap the hits.
  let listed = [];
  try { const p = await env.KV.list({ prefix: "code:", limit: 1000 }); listed = p.keys.map(k => k.name); } catch (e) {}
  const needle = q.toLowerCase();
  const out = []; let scanned = 0; let partial = listed.length === 0;
  for (let i = 0; i < listed.length && out.length < 50 && scanned < ADMIN_SCAN_CAP; i += 8) {
    const chunk = listed.slice(i, i + 8);
    const got = await Promise.all(chunk.map(async (k) => {
      try { return JSON.parse(await env.KV.get(k, { cacheTtl: 60 }) || "null"); } catch (e) { return null; }
    }));
    scanned += chunk.length;
    for (const r of got) {
      if (!r) continue;
      const hay = (String(r.code || "") + " " + String(r.email || "") + " " + String(r.ref || "") + " " + String(r.note || "")).toLowerCase();
      if (hay.indexOf(needle) >= 0) out.push(adminCodeView(r));
      if (out.length >= 50) break;
    }
  }
  if (scanned < listed.length) partial = true;
  out.sort((a, b) => b.issuedAt - a.issuedAt);
  return json({ ok: true, mode: "deep", scanned, partial, rows: out }, cors);
}

/* ---------- the write paths (money, by hand) ---------- */
async function handleAdminIssue(request, env, cors) {
  const body = await request.json().catch(() => null);
  if (!body) return json({ ok: false, error: "json body required" }, cors, 400);
  const email = String(body.email || "").trim().slice(0, 254).toLowerCase();
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json({ ok: false, error: "that email is not valid — leave it blank to skip the email" }, cors, 400);
  const days = Math.min(Math.max(Number(body.days) || 30, 1), 365);
  const amount = Math.min(Math.max(Number(body.amount) || 0, 0), 10000000);
  const note = String(body.note || "").trim().slice(0, 120);
  const today = new Date().toISOString().slice(0, 10);
  let issued = 0;
  try { issued = Number(await env.KV.get("adm:issue:" + today) || "0"); } catch (e) {}
  if (issued >= ADMIN_ISSUE_CAP) return json({ ok: false, error: "daily issue cap reached (" + ADMIN_ISSUE_CAP + ") — check the ledger before minting more" }, cors, 429);
  const ref = "MANUAL-" + adminHex(crypto.getRandomValues(new Uint8Array(5))).toUpperCase();
  const code = await issueCode(env, { email, ref, source: "manual", days, note, amount });
  try { await env.KV.incr("adm:issue:" + today, 1, { expirationTtl: 400 * 86400 }); } catch (e) {}
  let rec = null; try { rec = JSON.parse(await env.KV.get("code:" + code) || "null"); } catch (e) {}
  return json({ ok: true, code, days, amount, exp: rec && rec.exp, mailFailed: !!(rec && rec.mailFailed), mailed: !!email && !(rec && rec.mailFailed) }, cors);
}

async function loadAdminCode(env, raw) {
  const cleaned = String(raw || "").toUpperCase().replace(/[\s-]/g, "");
  if (!cleaned) return null;
  const key = normalizeCode(cleaned);
  for (const cand of [key, key.replace(/-/g, ""), cleaned]) { // a pasted code may have any dash/space shape
    if (!cand) continue;
    let rec = null;
    try { rec = JSON.parse(await env.KV.get("code:" + cand) || "null"); } catch (e) { rec = null; }
    if (rec) return rec;
  }
  return null;
}
async function saveAdminCode(env, rec) {
  try { await env.KV.put("code:" + rec.code, JSON.stringify(rec)); } catch (e) {}
  await expIndexAdd(env, rec.code, rec.exp);
}
async function handleAdminRevoke(request, env, cors) {
  const body = await request.json().catch(() => null);
  const rec = await loadAdminCode(env, body && body.code);
  if (!rec) return json({ ok: false, error: "code not found" }, cors, 404);
  if (rec.revoked) return json({ ok: true, alreadyRevoked: true, code: rec.code }, cors);
  rec.revoked = true; rec.revokedAt = Date.now(); rec.exp = Date.now() - 1000;
  await saveAdminCode(env, rec);
  await statBump(env, "revoked");
  await adminRecentPush(env, { kind: "revoke", code: rec.code, email: rec.email || "" });
  return json({ ok: true, code: rec.code }, cors);
}
async function handleAdminExtend(request, env, cors) {
  const body = await request.json().catch(() => null);
  const rec = await loadAdminCode(env, body && body.code);
  if (!rec) return json({ ok: false, error: "code not found" }, cors, 404);
  const days = Math.min(Math.max(Number(body && body.days) || 0, 1), 365);
  const wasRevoked = !!rec.revoked;
  // A revoked pass had its expiry forced into the past: restoring it restarts
  // the clock from today instead of resurrecting the dead date. Anything else
  // stacks on top of whatever is left, so an early top-up never loses days.
  rec.exp = (wasRevoked ? Date.now() : Math.max(Number(rec.exp) || 0, Date.now())) + days * 864e5;
  rec.remindedAt = 0;          // let the renewal reminder fire again for the new date
  if (wasRevoked) rec.revoked = false;
  await saveAdminCode(env, rec);
  await adminRecentPush(env, { kind: "extend", code: rec.code, email: rec.email || "", days });
  return json({ ok: true, code: rec.code, exp: rec.exp, unrevoked: wasRevoked }, cors);
}
async function handleAdminResend(request, env, cors) {
  const body = await request.json().catch(() => null);
  const rec = await loadAdminCode(env, body && body.code);
  if (!rec) return json({ ok: false, error: "code not found" }, cors, 404);
  if (!rec.email) return json({ ok: false, error: "no email on this purchase — nothing to resend" }, cors, 400);
  try {
    await emailCode(env, rec.email, rec.code);
    delete rec.mailFailed;
    try { await env.KV.put("code:" + rec.code, JSON.stringify(rec)); } catch (e) {}
  } catch (e) {
    console.error(`[docoga-mail] admin_resend_not_accepted reason=${safeMailFailureReason(e)}`);
    return json({ ok: false, error: "the mail provider did not accept it — try again, or send the code by hand" }, cors, 502);
  }
  return json({ ok: true, sent: true }, cors);
}

/* ---------- session hygiene ---------- */
async function handleAdminSessions(request, env, cors, sid) {
  let rows = [];
  try {
    const p = await env.KV.list({ prefix: "adm:sess:", limit: 100 });
    const keys = p.keys.map(k => k.name);
    const got = await Promise.all(keys.map(async (k) => {
      let s = null; try { s = JSON.parse(await env.KV.get(k) || "null"); } catch (e) {}
      return s ? { sid: k.slice(9), at: Number(s.at) || 0, exp: Number(s.exp) || 0, ip: String(s.ip || ""), ua: String(s.ua || "") } : null;
    }));
    rows = got.filter(Boolean).sort((a, b) => b.at - a.at);
  } catch (e) {}
  return json({ ok: true, rows, current: sid, sessionTtlSeconds: ADMIN_SESSION_TTL }, cors);
}
async function handleAdminSessionKill(request, env, cors, sid) {
  const body = await request.json().catch(() => null);
  const all = !!(body && body.all);
  let killed = 0;
  if (all) {
    try {
      const p = await env.KV.list({ prefix: "adm:sess:", limit: 200 });
      for (const k of p.keys.map(x => x.name)) {
        if (k === "adm:sess:" + sid) continue;
        try { await env.KV.delete(k); killed++; } catch (e) {}
      }
    } catch (e) {}
    return json({ ok: true, killed }, cors);
  }
  const target = String((body && body.sid) || sid);
  if (!/^[a-f0-9]{16,64}$/.test(target)) return json({ ok: false, error: "unknown session" }, cors, 400);
  try { await env.KV.delete("adm:sess:" + target); } catch (e) {}
  return json({ ok: true, killed: 1, self: target === sid }, cors);
}

/* ---------- router ---------- */

/* ==========================================================================
 *  SOCIAL BOARD + WEBSITE VISITS (owner dashboard, 17 Oct 2026)
 *
 *  The owner asked: "In the admin dashboard I want to see the social media
 *  upload plans for the day, the ones that were successful, the ones that
 *  failed." Everything here is read-side glue over systems that already exist;
 *  nothing touches payments, codes or the posting lanes themselves.
 *
 *  Plan   = the clock's own schedule (GET docoga-clock /, cached 30 min). The
 *           table the dashboard shows is the table that actually rings the
 *           lanes — it cannot disagree with reality by construction.
 *  Truth  = GitHub Actions runs for the Lagos day (one API call, cached 45 s),
 *           matched to slots by workflow + nearest time. Failed runs get their
 *           reason from the job annotations (cached per run, 7 days).
 *  Retry  = POST /admin/social/run → workflow_dispatch, allow-listed to the
 *           lanes in the plan, one per lane per 10 minutes. The lane's own
 *           duplicate guards decide whether anything is published.
 *  Visits = Cloudflare Web Analytics GraphQL (7 + 28 days, cached 30 min);
 *           the site tag is read from the beacon the site itself serves.
 *
 *  Fail-closed and honest: no GH_DISPATCH_TOKEN → {connected:false, reason},
 *  never a 500 and never an empty table pretending to be a quiet day. CPU
 *  budget (Workers Free: 10 ms) is respected by keeping every GitHub answer to
 *  one page of one day and by digesting finished days into small KV records.
 * ========================================================================== */
const SOCIAL_REPO_DEFAULT = "johnAzani/docoga";
const SOCIAL_CLOCK_URL = "https://docoga-clock.johnazani.workers.dev/";
const SOCIAL_PLAN_TTL = 1800;           // clock schedule cache
const SOCIAL_TODAY_TTL = 45;            // seconds before today's runs are re-read
const SOCIAL_DAY_TTL = 14 * 86400;      // finished days keep their digest two weeks
const SOCIAL_RUN_LOCK = 600;            // one manual dispatch per lane per 10 min
const SOCIAL_FAIL_LOOKUPS = 3;          // failure reasons fetched per load (then cached)
const SOCIAL_MATCH_BEFORE = 10 * 60e3;  // a run may start this early for its slot
const SOCIAL_MATCH_AFTER = 6 * 3600e3;  // …or this late (GitHub's own schedule lag: median 4h32 measured 17 Oct 2026)
const SOCIAL_DUE_GRACE = 20 * 60e3;     // "due" before it is called "missed"
const SOCIAL_HISTORY_DAYS = 7;
const SOCIAL_HISTORY_BUILDS = 2;        // finished days rebuilt per load when missing
const WAT_MS = 3600e3;                  // Lagos is UTC+1 all year
const SITE_TTL = 1800;
const SITE_TAG_TTL = 7 * 86400;
const SITE_GRAPHQL = "https://api.cloudflare.com/client/v4/graphql";

/* workflow file → how the owner reads it. kind "post" = something a reader sees;
 * "care" = housekeeping the owner should know ran, but is not a post. */
const SOCIAL_LANES = {
  "instagram_autopost.yml": { lane: "Instagram", what: "feed post + Story", kind: "post" },
  "threads_autopost.yml": { lane: "Threads", what: "text + card", kind: "post" },
  "facebook_autopost.yml": { lane: "Facebook", what: "Page post (Reel Mon + Thu)", kind: "post" },
  "facebook_story_afternoon.yml": { lane: "Facebook", what: "Story", kind: "post" },
  "telegram_autopost.yml": { lane: "Telegram", what: "channel post", kind: "post" },
  "linkedin_autopost.yml": { lane: "LinkedIn", what: "post", kind: "post" },
  "youtube_scheduled.yml": { lane: "YouTube", what: "Short — render + schedule", kind: "post" },
  "deepdive.yml": { lane: "YouTube", what: "Deep-Dive episode", kind: "post" },
  "youtube_boost.yml": { lane: "YouTube", what: "playlist + first comment", kind: "care" },
  "brain.yml": { lane: "Brain", what: "plans tomorrow's content", kind: "care" },
  "brain_replies.yml": { lane: "Brain", what: "answers comments", kind: "care" },
  "brain_scorecard.yml": { lane: "Brain", what: "Monday scorecard", kind: "care" },
  "automation-heartbeat.yml": { lane: "Heartbeat", what: "Telegram summary to you", kind: "care" },
  "narrator_resume.yml": { lane: "Narrator", what: "resume paused voice work", kind: "care" },
  "youtube_stats.yml": { lane: "YouTube", what: "weekly stats", kind: "care" },
  "deploy-clock.yml": { lane: "Clock", what: "redeploy the clock", kind: "care" },
};
const SOCIAL_SLOT_WORDS = { morning: "morning", lunch: "lunch", evening: "evening" };

function socialRepo(env) { return (env.GH_REPO || SOCIAL_REPO_DEFAULT).replace(/[^A-Za-z0-9_.\/-]/g, ""); }
function socialReady(env) { return !!(env.GH_DISPATCH_TOKEN); }
/* Lagos calendar day of an instant, as YYYY-MM-DD. */
function watDay(ms) { return new Date(Number(ms) + WAT_MS).toISOString().slice(0, 10); }
/* UTC window [start, end) of a Lagos day. */
function watWindow(day) {
  const start = Date.parse(day + "T00:00:00Z") - WAT_MS;
  return { start, end: start + 864e5 };
}
/* Does a cron's day-of-week field admit this UTC date? Fields seen in this repo:
 * "*", "1", "1-5", "1,3,5". 7 means Sunday as well. */
function cronDowOk(field, dow) {
  if (!field || field === "*") return true;
  return String(field).split(",").some(part => {
    const m = /^(\d)(?:-(\d))?$/.exec(part.trim());
    if (!m) return false;
    const a = Number(m[1]) % 7, b = m[2] == null ? a : Number(m[2]) % 7;
    return a <= b ? (dow >= a && dow <= b) : (dow >= a || dow <= b);
  });
}
/* Slots a schedule table produces for one Lagos day, in time order. */
function socialSlotsFor(entries, day) {
  const out = [];
  const { start } = watWindow(day);
  for (const e of entries || []) {
    const parts = String(e.cron || "").trim().split(/\s+/);
    if (parts.length !== 5) continue;
    const min = Number(parts[0]), hour = Number(parts[1]);
    if (!Number.isInteger(min) || !Number.isInteger(hour)) continue;   // the clock only rings fixed times
    // Lagos day = UTC 23:00 of the previous date … 22:59 of this date.
    const utcDate = hour === 23 ? start : start + WAT_MS;               // midnight UTC of the right UTC date
    const at = Date.UTC(new Date(utcDate).getUTCFullYear(), new Date(utcDate).getUTCMonth(), new Date(utcDate).getUTCDate(), hour, min);
    if (!cronDowOk(parts[4], new Date(at).getUTCDay())) continue;
    const meta = SOCIAL_LANES[e.workflow] || { lane: e.name || e.workflow, what: "", kind: "care" };
    const slotWord = e.inputs && e.inputs.slot ? SOCIAL_SLOT_WORDS[e.inputs.slot] || e.inputs.slot : "";
    out.push({ at, workflow: e.workflow, name: e.name || e.workflow, inputs: e.inputs || {},
               lane: meta.lane, what: slotWord ? meta.what + " · " + slotWord : meta.what, kind: meta.kind });
  }
  out.sort((a, b) => a.at - b.at || a.workflow.localeCompare(b.workflow));
  return out;
}
async function socialGitHub(env, path, init) {
  const headers = Object.assign({
    "Authorization": "Bearer " + env.GH_DISPATCH_TOKEN,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "docoga-pass-admin",
  }, (init && init.headers) || {});
  const r = await fetch("https://api.github.com/repos/" + socialRepo(env) + path, Object.assign({}, init || {}, { headers }));
  let body = null;
  try { body = r.status === 204 ? {} : await r.json(); } catch (e) { body = null; }
  return { status: r.status, body };
}
/* The clock's table, cached. {entries, utc, token, paused, from} */
async function socialPlan(env) {
  let cached = null;
  try { cached = JSON.parse(await env.KV.get("adm:social:plan") || "null"); } catch (e) {}
  if (cached && cached.at && Date.now() - cached.at < SOCIAL_PLAN_TTL * 1000) return cached;
  let plan = { at: Date.now(), entries: [], clock: null };
  try {
    const r = await fetch(env.CLOCK_URL || SOCIAL_CLOCK_URL, { headers: { "User-Agent": "docoga-pass-admin" } });
    const j = await r.json();
    plan.clock = { ok: !!j.ok, token: j.token || "unknown", paused: !!j.paused, utc: j.utc || null, entries: Number(j.entries) || 0 };
    if (Array.isArray(j.entries_table)) {
      plan.entries = j.entries_table.filter(e => e && typeof e.workflow === "string" && typeof e.cron === "string")
        .map(e => ({ workflow: e.workflow.replace(/[^A-Za-z0-9_.-]/g, ""), name: String(e.name || "").slice(0, 80), cron: e.cron.slice(0, 40), inputs: e.inputs && typeof e.inputs === "object" ? e.inputs : {} }));
    }
  } catch (e) {
    plan.clock = { ok: false, error: String((e && e.message) || e).slice(0, 120) };
  }
  if (plan.entries.length || !cached) {
    try { await env.KV.put("adm:social:plan", JSON.stringify(plan), { expirationTtl: SOCIAL_PLAN_TTL * 2 }); } catch (e) {}
    return plan;
  }
  return cached;   // the clock did not answer: keep the last good table
}
function socialRunStatus(run) {
  if (!run) return null;
  if (run.status !== "completed") return "running";
  if (run.conclusion === "success") return "done";
  if (run.conclusion === "failure" || run.conclusion === "timed_out" || run.conclusion === "startup_failure") return "failed";
  if (run.conclusion === "cancelled") return "cancelled";
  return run.conclusion || "done";
}
function socialCompactRun(r) {
  return { id: r.id, url: r.html_url, event: r.event, status: r.status, conclusion: r.conclusion,
           started: Date.parse(r.run_started_at || r.created_at) || null, finished: r.status === "completed" ? (Date.parse(r.updated_at) || null) : null,
           attempt: r.run_attempt || 1, actor: r.triggering_actor && r.triggering_actor.login ? String(r.triggering_actor.login).slice(0, 40) : "" };
}
/* Why did it fail? First failure/error annotation of the failed job, minus the generic
 * "Process completed with exit code" line. Cached per run — a finished run never changes. */
async function socialFailureCause(env, runId) {
  const key = "adm:run:" + runId;
  try { const c = await env.KV.get(key); if (c !== null) return c; } catch (e) {}
  let cause = "";
  try {
    const jobs = await socialGitHub(env, "/actions/runs/" + runId + "/jobs?per_page=20");
    const failed = ((jobs.body && jobs.body.jobs) || []).find(j => j.conclusion === "failure") || null;
    if (failed) {
      const ann = await fetch("https://api.github.com/repos/" + socialRepo(env) + "/check-runs/" + failed.id + "/annotations", {
        headers: { "Authorization": "Bearer " + env.GH_DISPATCH_TOKEN, "Accept": "application/vnd.github+json", "User-Agent": "docoga-pass-admin", "X-GitHub-Api-Version": "2022-11-28" } });
      const rows = ann.ok ? await ann.json() : [];
      const pick = (Array.isArray(rows) ? rows : []).filter(a => (a.annotation_level === "failure" || a.annotation_level === "error") && !/^Process completed with exit code/.test(a.message || ""));
      const first = pick[0] || (Array.isArray(rows) ? rows.find(a => a.annotation_level === "warning") : null);
      cause = first ? ((first.title ? first.title + ": " : "") + String(first.message || "")).replace(/\s+/g, " ").slice(0, 240) : ("step “" + String(failed.name || "").slice(0, 60) + "” failed");
    }
  } catch (e) { cause = ""; }
  try { await env.KV.put(key, cause, { expirationTtl: 7 * 86400 }); } catch (e) {}
  return cause;
}
/* One Lagos day: slots vs runs. */
async function socialDigest(env, plan, day, now, withCauses) {
  const { start, end } = watWindow(day);
  const slots = socialSlotsFor(plan.entries, day);
  const q = "/actions/runs?created=" + new Date(start).toISOString().slice(0, 19) + "Z.." + new Date(end - 1000).toISOString().slice(0, 19) + "Z&per_page=100&exclude_pull_requests=true";
  const r = await socialGitHub(env, q);
  if (r.status !== 200 || !r.body || !Array.isArray(r.body.workflow_runs)) {
    return { day, ok: false, error: "github " + r.status + (r.body && r.body.message ? " " + String(r.body.message).slice(0, 80) : ""), slots: slots.map(s => Object.assign({ status: "unknown" }, s)), extras: [], counts: {} };
  }
  const runs = r.body.workflow_runs
    .filter(x => x && typeof x.path === "string" && (x.event === "workflow_dispatch" || x.event === "schedule"))
    .map(x => Object.assign({ workflow: x.path.split("/").pop(), created: Date.parse(x.created_at) }, x))
    .sort((a, b) => a.created - b.created);
  const taken = new Set(), rows = slots.map(s => Object.assign({ status: null, run: null, cause: "" }, s));
  const extras = [];
  for (const run of runs) {
    let best = -1, bestDist = Infinity;
    rows.forEach((s, i) => {
      if (s.workflow !== run.workflow || taken.has(i)) return;
      const d = run.created - s.at;
      if (d < -SOCIAL_MATCH_BEFORE || d > SOCIAL_MATCH_AFTER) return;
      if (Math.abs(d) < bestDist) { bestDist = Math.abs(d); best = i; }
    });
    const compact = socialCompactRun(run);
    if (best >= 0) { taken.add(best); rows[best].run = compact; rows[best].status = socialRunStatus(run); }
    else extras.push(Object.assign({ workflow: run.workflow, lane: (SOCIAL_LANES[run.workflow] || {}).lane || run.name, name: run.name }, compact, { status: socialRunStatus(run) }));
  }
  for (const s of rows) {
    if (s.status) continue;
    s.status = s.at > now ? "upcoming" : (now - s.at < SOCIAL_DUE_GRACE ? "due" : "missed");
  }
  if (withCauses) {
    let budget = SOCIAL_FAIL_LOOKUPS;
    for (const s of rows.concat(extras)) {
      if (s.status !== "failed" || budget <= 0) continue;
      const id = s.run ? s.run.id : s.id;
      if (!id) continue;
      budget--;
      s.cause = await socialFailureCause(env, id);
    }
  }
  const counts = { posted: 0, done: 0, failed: 0, running: 0, upcoming: 0, missed: 0, due: 0, cancelled: 0 };
  for (const s of rows) {
    counts[s.status] = (counts[s.status] || 0) + 1;
    if (s.status === "done" && s.kind === "post") counts.posted++;
  }
  return { day, ok: true, at: now, slots: rows, extras, counts, runs: runs.length };
}
async function socialDigestCached(env, plan, day, now, isToday) {
  const key = isToday ? "adm:social:today" : "adm:social:" + day;
  let cached = null;
  try { cached = JSON.parse(await env.KV.get(key) || "null"); } catch (e) {}
  if (cached && cached.ok && cached.day === day && (!isToday || now - cached.at < SOCIAL_TODAY_TTL * 1000)) return cached;
  if (!isToday && cached && cached.ok && cached.day === day) return cached;
  const d = await socialDigest(env, plan, day, now, true);
  if (d.ok) {
    try { await env.KV.put(key, JSON.stringify(d), { expirationTtl: isToday ? 300 : SOCIAL_DAY_TTL }); } catch (e) {}
  }
  return d;
}
async function handleAdminSocial(request, env, cors) {
  const now = Date.now();
  const day = watDay(now);
  if (!socialReady(env)) {
    return json({ ok: true, connected: false, day, now,
      reason: "The worker has no GH_DISPATCH_TOKEN yet. The next deploy of docoga-pass forwards the repository secret of the same name (deploy-pass-now.yml) — nothing to mint." }, cors);
  }
  const plan = await socialPlan(env);
  const today = await socialDigestCached(env, plan, day, now, true);
  // History: finished days are digested once and kept; at most two are built per load.
  const days = []; let builds = SOCIAL_HISTORY_BUILDS;
  for (let i = 1; i <= SOCIAL_HISTORY_DAYS; i++) {
    const d = watDay(now - i * 864e5);
    let dig = null;
    try { dig = JSON.parse(await env.KV.get("adm:social:" + d) || "null"); } catch (e) {}
    if (!(dig && dig.ok) && builds > 0 && plan.entries.length) { builds--; dig = await socialDigestCached(env, plan, d, now, false); }
    days.push(dig && dig.ok ? { day: d, counts: dig.counts, slots: dig.slots.map(s => ({ at: s.at, lane: s.lane, what: s.what, kind: s.kind, status: s.status, cause: s.cause || "", url: s.run ? s.run.url : null })) }
                            : { day: d, pending: true });
  }
  return json({ ok: true, connected: true, repo: socialRepo(env), day, now,
                clock: plan.clock, planFrom: plan.entries.length ? "clock" : null, planAt: plan.at,
                today, days }, cors);
}
async function handleAdminSocialRun(request, env, cors) {
  if (!socialReady(env)) return json({ ok: false, error: "not_connected" }, cors, 503);
  let b = {}; try { b = await request.json(); } catch (e) { b = {}; }
  const workflow = String(b.workflow || "").replace(/[^A-Za-z0-9_.-]/g, "").slice(0, 60);
  const plan = await socialPlan(env);
  const known = new Set(plan.entries.map(e => e.workflow).concat(Object.keys(SOCIAL_LANES)));
  if (!workflow || !known.has(workflow)) return json({ ok: false, error: "unknown_workflow" }, cors, 400);
  const inputs = {};
  if (b.inputs && typeof b.inputs === "object") {
    for (const k of Object.keys(b.inputs).slice(0, 4)) {
      if (!/^[a-z_]{1,24}$/.test(k)) continue;
      const v = String(b.inputs[k]);
      if (!/^[A-Za-z0-9_:.-]{0,40}$/.test(v)) continue;
      inputs[k] = v;
    }
  }
  const lockKey = "adm:social:lock:" + workflow;
  const held = await env.KV.get(lockKey);
  if (held) {
    const left = Math.max(1, Math.round((Number(held) + SOCIAL_RUN_LOCK * 1000 - Date.now()) / 1000));
    return json({ ok: false, error: "already_asked", retryInSeconds: left }, cors, 429);
  }
  await env.KV.put(lockKey, String(Date.now()), { expirationTtl: SOCIAL_RUN_LOCK });
  const r = await socialGitHub(env, "/actions/workflows/" + workflow + "/dispatches", {
    method: "POST", body: JSON.stringify({ ref: "main", inputs }), headers: { "Content-Type": "application/json" } });
  if (r.status !== 204) {
    try { await env.KV.delete(lockKey); } catch (e) {}
    return json({ ok: false, error: "github_" + r.status, detail: r.body && r.body.message ? String(r.body.message).slice(0, 160) : "" }, cors, 502);
  }
  await adminRecentPush(env, { kind: "dispatch", workflow, inputs });
  try { await env.KV.delete("adm:social:today"); } catch (e) {}   // the next load should see the run appear
  return json({ ok: true, workflow, inputs, startsWithinSeconds: 30 }, cors);
}

/* ---- Website visits: Cloudflare Web Analytics, read-only ---- */
const SITE_CHANNELS = [
  ["t.me", "telegram"], ["telegram.", "telegram"], ["facebook.com", "facebook"], ["fb.com", "facebook"], ["fb.me", "facebook"], ["messenger.com", "facebook"],
  ["instagram.com", "instagram"], ["threads.", "threads"], ["linkedin.com", "linkedin"], ["lnkd.in", "linkedin"], ["youtube.com", "youtube"], ["youtu.be", "youtube"],
  ["tiktok.com", "tiktok"], ["whatsapp.", "whatsapp"], ["wa.me", "whatsapp"], ["google.", "google"], ["bing.com", "search"], ["duckduckgo.com", "search"], ["yahoo.", "search"],
  ["x.com", "x"], ["twitter.com", "x"], ["t.co", "x"], ["nairaland.com", "nairaland"],
];
function siteChannel(host, own) {
  const h = String(host || "").toLowerCase();
  if (!h) return "direct";
  if (h === own || h.endsWith("." + own)) return "internal";
  for (const [needle, name] of SITE_CHANNELS) if (h.indexOf(needle) >= 0) return name;
  return "other";
}
const SITE_QUERY = `query Docoga($account: String!, $f7: AccountRumPageloadEventsAdaptiveGroupsFilter_InputObject!, $f28: AccountRumPageloadEventsAdaptiveGroupsFilter_InputObject!) {
  viewer { accounts(filter: {accountTag: $account}) {
    t7: rumPageloadEventsAdaptiveGroups(filter: $f7, limit: 1) { count sum { visits } }
    t28: rumPageloadEventsAdaptiveGroups(filter: $f28, limit: 1) { count sum { visits } }
    ref7: rumPageloadEventsAdaptiveGroups(filter: $f7, limit: 100, orderBy: [sum_visits_DESC]) { sum { visits } dimensions { refererHost } }
    path7: rumPageloadEventsAdaptiveGroups(filter: $f7, limit: 60, orderBy: [sum_visits_DESC]) { count sum { visits } dimensions { requestPath } }
    country7: rumPageloadEventsAdaptiveGroups(filter: $f7, limit: 12, orderBy: [sum_visits_DESC]) { sum { visits } dimensions { countryName } }
    days28: rumPageloadEventsAdaptiveGroups(filter: $f28, limit: 40, orderBy: [date_ASC]) { count sum { visits } dimensions { date } }
  } }
}`;
async function siteTag(env, host) {
  try { const c = await env.KV.get("adm:site:tag"); if (c) return c; } catch (e) {}
  let tag = "";
  try {
    const r = await fetch("https://" + host + "/", { headers: { "User-Agent": "docoga-pass-admin", "Accept": "text/html" } });
    const html = (await r.text()).slice(0, 400000);
    const m = /data-cf-beacon=['"]\{[^}]*?"token"\s*:\s*"([0-9a-f]{20,40})"/i.exec(html);
    if (m) tag = m[1];
  } catch (e) {}
  if (tag) { try { await env.KV.put("adm:site:tag", tag, { expirationTtl: SITE_TAG_TTL }); } catch (e) {} }
  return tag;
}
async function handleAdminSite(request, env, cors) {
  const now = Date.now();
  if (!(env.CF_ANALYTICS_TOKEN && env.CLOUDFLARE_ACCOUNT_ID)) {
    return json({ ok: true, connected: false, reason: "The worker has no CF_ANALYTICS_TOKEN / CLOUDFLARE_ACCOUNT_ID yet. The next deploy of docoga-pass forwards both from the repository secrets — nothing to mint." }, cors);
  }
  let cached = null;
  try { cached = JSON.parse(await env.KV.get("adm:site:v1") || "null"); } catch (e) {}
  if (cached && cached.at && now - cached.at < SITE_TTL * 1000) return json(Object.assign({ ok: true, connected: true, cached: true }, cached), cors);
  const host = (env.SITE_URL || "https://docoga.com.ng").replace(/^https?:\/\//, "").replace(/\/.*$/, "");
  const tag = await siteTag(env, host);
  const iso = (ms) => new Date(ms).toISOString().slice(0, 19) + "Z";
  const mk = (days) => { const f = { datetime_geq: iso(now - days * 864e5), datetime_leq: iso(now), requestHost: host }; if (tag) f.siteTag = tag; return f; };
  let data = null, problem = "";
  try {
    const r = await fetch(SITE_GRAPHQL, { method: "POST", headers: { "Authorization": "Bearer " + env.CF_ANALYTICS_TOKEN, "Content-Type": "application/json", "User-Agent": "docoga-pass-admin" },
      body: JSON.stringify({ query: SITE_QUERY, variables: { account: env.CLOUDFLARE_ACCOUNT_ID, f7: mk(7), f28: mk(28) } }) });
    const j = await r.json();
    const errs = (j && j.errors) || [];
    if (r.status !== 200 || errs.length) problem = "Cloudflare refused: " + String((errs[0] && errs[0].message) || ("http " + r.status)).slice(0, 120);
    else data = (((j.data || {}).viewer || {}).accounts || [])[0] || null;
    if (!data && !problem) problem = "Cloudflare returned no account — check CLOUDFLARE_ACCOUNT_ID";
  } catch (e) { problem = "Cloudflare unreachable: " + String((e && e.message) || e).slice(0, 100); }
  if (!data) {
    if (cached) return json(Object.assign({ ok: true, connected: true, cached: true, stale: problem }, cached), cors);
    return json({ ok: true, connected: true, error: problem, siteTag: tag ? tag.slice(0, 6) + "…" : null }, cors);
  }
  const sum = (row) => Number(((row || {}).sum || {}).visits || 0);
  const byChannel = {}, byHost = {};
  for (const row of data.ref7 || []) {
    const h = ((row.dimensions || {}).refererHost) || "";
    const ch = siteChannel(h, host);
    if (ch === "internal") continue;
    byChannel[ch] = (byChannel[ch] || 0) + sum(row);
    if (h) byHost[h] = (byHost[h] || 0) + sum(row);
  }
  const byPath = {};
  for (const row of data.path7 || []) { const p = ((row.dimensions || {}).requestPath) || "/"; byPath[p] = (byPath[p] || 0) + sum(row); }
  const byCountry = {};
  for (const row of data.country7 || []) { const c = ((row.dimensions || {}).countryName) || "?"; byCountry[c] = (byCountry[c] || 0) + sum(row); }
  const allC = Object.values(byCountry).reduce((a, b) => a + b, 0);
  const ng = (byCountry.NG || 0) + (byCountry.Nigeria || 0);
  const top = (o, n) => Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, n);
  const out = {
    at: now, host, siteTag: tag ? tag.slice(0, 6) + "…" : null,
    visits7: sum((data.t7 || [])[0]), pageviews7: Number((((data.t7 || [])[0]) || {}).count || 0),
    visits28: sum((data.t28 || [])[0]), pageviews28: Number((((data.t28 || [])[0]) || {}).count || 0),
    nigeriaShare7: allC ? Math.round(ng / allC * 1000) / 1000 : null,
    byChannel: top(byChannel, 12), byHost: top(byHost, 10), byPath: top(byPath, 15), byCountry: top(byCountry, 10),
    days28: (data.days28 || []).map(r => ({ date: (r.dimensions || {}).date, visits: sum(r), pageviews: Number(r.count || 0) })),
  };
  try { await env.KV.put("adm:site:v1", JSON.stringify(out), { expirationTtl: SITE_TTL * 4 }); } catch (e) {}
  return json(Object.assign({ ok: true, connected: true, cached: false }, out), cors);
}

export default {
  async fetch(request, env, ctx) {
    ctx = ctx || {};
    const url = new URL(request.url);
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Content-Type,X-DocOga-Key,Authorization",
      "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    /* Admin answers carry customer emails and revenue: never cacheable, and never
     * embeddable in someone else's frame (the dashboard is Bearer-driven, so no
     * cookie and no CSRF — this header only closes the click-jacking door). */
    if (url.pathname.indexOf("/admin/") === 0) {
      cors["Cache-Control"] = "no-store";
      cors["X-Frame-Options"] = "DENY";
      cors["Referrer-Policy"] = "no-referrer";
    }

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
      if (url.pathname === "/tap" && request.method === "POST") return await handleTap(request, env, cors);
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
      if (url.pathname === "/business/team/renew" && request.method === "POST") return await handleBusinessRenew(request, env, cors);
      if (url.pathname === "/business/team/usage" && request.method === "POST") return await handleBusinessUsage(request, env, cors);
      if (url.pathname.startsWith("/business/invoice/") && request.method === "GET") {
        const parts = url.pathname.split("/");
        if (parts.length === 4) return await handleBusinessInvoice(decodeURIComponent(parts[3]), request, env, cors);
      }
      /* ---- owner dashboard (fail-closed; see ADMIN_DASHBOARD.md) ---- */
      if (url.pathname.indexOf("/admin/") === 0) {
        if (!adminReady(env)) return json({ ok: false, error: "admin_disabled" }, cors, 503);
        if (url.pathname === "/admin/login" && request.method === "POST") return await handleAdminLogin(request, env, cors);
        const a = await adminSession(request, env);
        if (!a) return json({ ok: false, error: "sign_in_required" }, cors, 401);
        if (url.pathname === "/admin/logout" && request.method === "POST") {
          try { await env.KV.delete("adm:sess:" + a.sid); } catch (e) {}
          return json({ ok: true }, cors);
        }
        if (url.pathname === "/admin/me" && request.method === "GET")
          return json({ ok: true, at: a.at, exp: a.exp, ip: a.ip, ua: a.ua }, cors);
        if (url.pathname === "/admin/data" && request.method === "GET") return await handleAdminData(request, env, cors, ctx);
        if (url.pathname === "/admin/snapshot" && request.method === "POST") return await handleAdminSnapshot(request, env, cors);
        if (url.pathname === "/admin/codes" && request.method === "GET") return await handleAdminCodes(request, url, env, cors);
        if (url.pathname === "/admin/issue" && request.method === "POST") return await handleAdminIssue(request, env, cors);
        if (url.pathname === "/admin/resend" && request.method === "POST") return await handleAdminResend(request, env, cors);
        if (url.pathname === "/admin/revoke" && request.method === "POST") return await handleAdminRevoke(request, env, cors);
        if (url.pathname === "/admin/extend" && request.method === "POST") return await handleAdminExtend(request, env, cors);
        if (url.pathname === "/admin/sessions" && request.method === "GET") return await handleAdminSessions(request, env, cors, a.sid);
        if (url.pathname === "/admin/session" && request.method === "POST") return await handleAdminSessionKill(request, env, cors, a.sid);
        if (url.pathname === "/admin/social" && request.method === "GET") return await handleAdminSocial(request, env, cors);
        if (url.pathname === "/admin/social/run" && request.method === "POST") return await handleAdminSocialRun(request, env, cors);
        if (url.pathname === "/admin/site" && request.method === "GET") return await handleAdminSite(request, env, cors);
        return json({ ok: false, error: "not found" }, cors, 404);
      }
      return json({ ok: false, error: "not found" }, cors, 404);
    } catch (e) {
      return json({ ok: false, error: String((e && e.message) || e) }, cors, 500);
    }
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil((async () => {
      try { await dailyRenewalReminders(env); } catch (e) {}
      try { await dailyBusinessRenewals(env); } catch (e) {}
      // Owner dashboard rollup, last so it counts whatever the sweeps just did.
      // Fail-closed by construction: with no admin secrets set this skips the
      // work entirely instead of writing a snapshot nobody may read.
      try { if (adminReady(env)) await buildAdminSnapshot(env); } catch (e) {}
      // Yesterday's social board, digested once while it is one GitHub page — so the
      // 7-day view is ready even on days the owner never opened the dashboard.
      try {
        if (adminReady(env) && socialReady(env)) {
          const now = Date.now(), y = watDay(now - 864e5);
          await socialDigestCached(env, await socialPlan(env), y, now, false);
        }
      } catch (e) {}
    })());
  },
};
