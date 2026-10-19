/* DocOga Receipt Ledger — a verifiable code on every receipt, and the data behind the first
 * live rent index for Nigeria. See docs/RECEIPT_LEDGER.md.
 *
 * What it stores (and what it never stores)
 * -----------------------------------------
 * A receipt registered from docoga.com.ng puts ONE small record in KV under `ledger:r:<code>`:
 *   { v, fp, st, amt, kind, from, to, d, t }
 *   fp   — SHA-256 fingerprint of the receipt's own words, computed in the issuer's browser
 *          (date | amount | payer | issuer | property | period). The server never sees the
 *          words, only the hash — so a later reader can prove the paper is unchanged without
 *          this service holding anybody's name or address.
 *   st   — state (one of 37), amt — naira integer, kind — rent/caution/service/agency/other,
 *   from/to — the period as YYYY-MM when given, d — receipt date, t — registered at (UTC).
 * No name, no address, no phone, no IP, no cookie. Under the Nigeria Data Protection Act 2023 a
 * record that cannot be related to an identifiable individual is not personal data; the design
 * also follows s.24(1)(c) (minimum necessary) as if it were.
 *
 * Why KV and not D1 (Oct 2026): the Workers Free plan allows 1,000 KV writes a day account-wide
 * and 100,000 D1 row writes a day. The site registers a few receipts a day today; KV needs no new
 * resource (this worker binds the namespace docoga-pass already has, under its own `ledger:`
 * prefix). The move to D1 is a written trigger in docs/RECEIPT_LEDGER.md: 300 registrations in
 * any one day. Metadata on each key carries the index fields, so the public stats read key
 * listings (1,000 keys per list op) and never the values.
 *
 * Routes
 *   POST /api/register       {fp, state, amount, kind?, from?, to?, date}  → {code, url}
 *   GET  /api/verify?code=   → the record (or 404)
 *   GET  /api/stats          → registrations by state, month, kind and index cell (cached 1 h)
 *   GET  /v/<code>           → the human verification page
 *   GET  /                   → what this is
 */

const STATES = ["Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno", "Cross River",
  "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT (Abuja)", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina",
  "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto",
  "Taraba", "Yobe", "Zamfara"];
const KINDS = ["rent", "caution", "service", "agency", "other"];
const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";   // Crockford base32: no I, L, O, U
const CODE_RE = /^DR-[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$/;
const MIN_AMOUNT = 1000;
const MAX_AMOUNT = 1_000_000_000;
const MAX_BODY = 2048;
const DEFAULT_ORIGINS = ["https://docoga.com.ng", "https://www.docoga.com.ng"];

export function makeCode(bytes) {
  // 8 symbols × 5 bits = 40 bits of randomness; DR-XXXX-XXXX reads aloud without ambiguity.
  const b = bytes || crypto.getRandomValues(new Uint8Array(8));
  let s = "";
  for (let i = 0; i < 8; i++) s += ALPHABET[b[i] & 31];
  return "DR-" + s.slice(0, 4) + "-" + s.slice(4);
}

export function normaliseCode(raw) {
  const s = String(raw || "").toUpperCase().replace(/[^0-9A-Z]/g, "").replace(/^DR/, "")
    .replace(/O/g, "0").replace(/[IL]/g, "1");
  if (s.length !== 8) return "";
  const code = "DR-" + s.slice(0, 4) + "-" + s.slice(4);
  return CODE_RE.test(code) ? code : "";
}

export function validate(body) {
  const errors = [];
  const fp = String(body.fp || "").toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(fp)) errors.push("fp");
  const state = String(body.state || "");
  if (!STATES.includes(state)) errors.push("state");
  const amount = Number(body.amount);
  if (!Number.isInteger(amount) || amount < MIN_AMOUNT || amount > MAX_AMOUNT) errors.push("amount");
  const kind = body.kind ? String(body.kind) : "rent";
  if (!KINDS.includes(kind)) errors.push("kind");
  const date = String(body.date || "");
  const dt = /^\d{4}-\d{2}-\d{2}$/.test(date) ? new Date(date + "T00:00:00Z") : null;
  const tomorrow = Date.now() + 36 * 3600 * 1000;
  if (!dt || isNaN(dt) || dt.getTime() > tomorrow || dt.getUTCFullYear() < 2000) errors.push("date");
  const month = (v) => (v == null || v === "") ? "" : (/^\d{4}-(0[1-9]|1[0-2])$/.test(String(v)) ? String(v) : null);
  const from = month(body.from), to = month(body.to);
  if (from === null) errors.push("from");
  if (to === null) errors.push("to");
  if (from && to && to < from) errors.push("to");
  return { ok: errors.length === 0, errors, record: { v: 1, fp, st: state, amt: amount, kind, from: from || "", to: to || "", d: date } };
}

function json(data, status = 200, extra = {}) {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...extra } });
}

function corsHeaders(request, env) {
  const allowed = String(env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  const origins = allowed.length ? allowed : DEFAULT_ORIGINS;
  const origin = request.headers.get("Origin") || "";
  const ok = origins.includes(origin);
  return { ok, headers: ok ? { "access-control-allow-origin": origin, "access-control-allow-methods": "POST, GET, OPTIONS", "access-control-allow-headers": "content-type", "vary": "Origin" } : {} };
}

async function register(request, env) {
  const cors = corsHeaders(request, env);
  if (!cors.ok) return json({ error: "origin" }, 403);
  const len = Number(request.headers.get("content-length") || 0);
  if (len > MAX_BODY) return json({ error: "too_large" }, 413, cors.headers);
  let body;
  try { body = await request.json(); } catch (e) { return json({ error: "json" }, 400, cors.headers); }
  const v = validate(body || {});
  if (!v.ok) return json({ error: "invalid", fields: v.errors }, 422, cors.headers);
  // Same words, same code: a re-print must not spend a second write or mint a second code.
  const byFp = await env.KV.get("ledger:fp:" + v.record.fp);
  if (byFp) return json({ code: byFp, url: verifyUrl(env, byFp), existing: true }, 200, cors.headers);
  let code = "";
  for (let i = 0; i < 4 && !code; i++) {
    const c = makeCode();
    if (!(await env.KV.get("ledger:r:" + c))) code = c;
  }
  if (!code) return json({ error: "collision" }, 503, cors.headers);
  const record = { ...v.record, t: new Date().toISOString().slice(0, 19) + "Z" };
  const metadata = { st: record.st, amt: record.amt, kind: record.kind, d: record.d, m: record.d.slice(0, 7) };
  await env.KV.put("ledger:r:" + code, JSON.stringify(record), { metadata });
  await env.KV.put("ledger:fp:" + record.fp, code);
  return json({ code, url: verifyUrl(env, code) }, 201, cors.headers);
}

function verifyUrl(env, code) {
  return (env.PUBLIC_URL || "https://docoga-ledger.johnazani.workers.dev").replace(/\/$/, "") + "/v/" + code;
}

async function lookup(env, raw) {
  const code = normaliseCode(raw);
  if (!code) return { code: "", record: null };
  const text = await env.KV.get("ledger:r:" + code);
  return { code, record: text ? JSON.parse(text) : null };
}

async function stats(env, ctx, request) {
  const cache = caches.default;
  const key = new Request(new URL("/api/stats", request.url).toString(), { method: "GET" });
  const hit = await cache.match(key);
  if (hit) return hit;
  const byState = {}, byMonth = {}, byKind = {}, cells = {};
  let total = 0, latest = "", cursor, pages = 0;
  do {
    const page = await env.KV.list({ prefix: "ledger:r:", cursor, limit: 1000 });
    for (const k of page.keys) {
      const m = k.metadata || {};
      total += 1;
      byState[m.st || "?"] = (byState[m.st || "?"] || 0) + 1;
      byMonth[m.m || "?"] = (byMonth[m.m || "?"] || 0) + 1;
      byKind[m.kind || "?"] = (byKind[m.kind || "?"] || 0) + 1;
      // One index cell = state × kind × month of the receipt date. A cell publishes amount
      // statistics only at 30 receipts (docs/RECEIPT_LEDGER.md §5); counts are public before that.
      const cell = (m.st || "?") + "|" + (m.kind || "?") + "|" + (m.m || "?");
      cells[cell] = (cells[cell] || 0) + 1;
      if (m.d && m.d > latest) latest = m.d;
    }
    cursor = page.list_complete ? undefined : page.cursor;
    pages += 1;
  } while (cursor && pages < 20);     // 20 list ops ≈ 20,000 receipts; the D1 trigger fires long before
  const body = { total, by_state: byState, by_month: byMonth, by_kind: byKind, cells, latest_receipt_date: latest || null,
    publish_at: 30, generated_at: new Date().toISOString(),
    note: "Counts of receipts registered on docoga.com.ng. Amount statistics are published only for cells with 30 or more receipts (docs/RECEIPT_LEDGER.md §5)." };
  const res = json(body, 200, { "cache-control": "public, max-age=3600", "access-control-allow-origin": "*" });
  ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}

export function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function fmtMonth(ym) {
  if (!/^\d{4}-\d{2}$/.test(ym || "")) return "";
  return MONTHS[Number(ym.slice(5, 7)) - 1] + " " + ym.slice(0, 4);
}
export function fmtDate(d) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d || "")) return "";
  return Number(d.slice(8, 10)) + " " + MONTHS[Number(d.slice(5, 7)) - 1] + " " + d.slice(0, 4);
}
export function fmtNaira(n) {
  return "\u20a6" + Number(n || 0).toLocaleString("en-NG");
}
const KIND_WORDS = { rent: "rent", caution: "caution / security deposit", service: "service charge", agency: "agency or legal fee", other: "a payment" };

/* The one function that must be identical in site/index.html (receiptCanonical) — tested. */
const CANONICAL_JS = `function receiptCanonical(f){
  var n=function(s){return String(s==null?'':s).replace(/\\s+/g,' ').trim().toLowerCase();};
  var amt=String(Math.round(Number(String(f.amount==null?'':f.amount).replace(/[^0-9.]/g,''))||0));
  return ['v1',n(f.date),amt,n(f.from),n(f.issuer),n(f.property),n(f.period)].join('|');
}`;

const CSS = `:root{--navy:#0B1F3A;--royal:#1F4E9A;--yellow:#FFC72C;--white:#fff;--muted:#8DA2C0;--red:#D7263D;--green:#1E9E5A;--panel:#13294B}
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--navy);color:var(--white);line-height:1.45}
main{max-width:640px;margin:0 auto;padding:28px 20px 60px}.kicker{font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);font-weight:600}
h1{font-size:30px;line-height:1.1;margin:10px 0 18px;font-weight:900}.slab{display:inline-block;background:var(--yellow);color:var(--navy);padding:4px 12px;font-weight:900;letter-spacing:.02em}
.card{background:var(--panel);border-radius:14px;padding:18px 18px 8px;margin:16px 0}.row{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid rgba(255,255,255,.08)}
.row:last-child{border-bottom:0}.row b{font-weight:700;text-align:right}.ok{color:var(--green);font-weight:900}.bad{color:#FF6B7D;font-weight:900}
.note{color:var(--muted);font-size:14px}label{display:block;font-size:13px;color:var(--muted);margin:12px 0 4px}input{width:100%;padding:12px;border-radius:10px;border:1px solid rgba(255,255,255,.15);background:#0E2447;color:#fff;font-size:16px}
button{margin-top:16px;width:100%;padding:14px;border:0;border-radius:12px;background:var(--yellow);color:var(--navy);font-weight:900;font-size:16px}
a{color:var(--yellow)}.chip{display:inline-block;border:1px solid var(--royal);border-radius:999px;padding:6px 12px;font-size:13px;color:#fff;margin-top:18px}
.code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:22px;letter-spacing:.08em}`;

function page(title, inner) {
  return new Response(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)}</title><meta name="robots" content="noindex"><style>${CSS}</style></head><body><main>${inner}
<div class="chip">FREE \u00b7 docoga.com.ng</div>
<p class="note">DocOga stores no names, addresses or phone numbers for this service \u2014 only the amount, state, period, date and a fingerprint of the receipt's words. Legal information, not legal advice.</p>
</main></body></html>`, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
}

function verifyPage(code, record) {
  if (!record) {
    return page("Receipt not found \u2014 DocOga", `<div class="kicker">DocOga \u00b7 receipt check</div>
<h1><span class="slab">Not found.</span></h1>
<div class="card"><div class="row"><span>Code</span><b class="code">${esc(code || "\u2014")}</b></div></div>
<p>No receipt with this code has been registered on DocOga. Check the code on the paper (0 and O, 1 and I are read the same). A receipt printed without the free verification box ticked has no code.</p>
<form method="get" action="/v/"><label>Try a code</label><input name="c" placeholder="DR-XXXX-XXXX" autocomplete="off"><button type="submit">Check</button></form>`);
  }
  const period = record.from ? (record.to && record.to !== record.from ? fmtMonth(record.from) + " \u2013 " + fmtMonth(record.to) : fmtMonth(record.from)) : "";
  return page("Receipt " + code + " \u2014 DocOga", `<div class="kicker">DocOga \u00b7 receipt check</div>
<h1><span class="slab">Registered.</span></h1>
<p>A receipt with this code was created on DocOga and registered at the time of printing. It has not been edited since if the words on the paper match the fingerprint below.</p>
<div class="card">
<div class="row"><span>Code</span><b class="code">${esc(code)}</b></div>
<div class="row"><span>State</span><b>${esc(record.st)}</b></div>
<div class="row"><span>Amount</span><b>${esc(fmtNaira(record.amt))}</b></div>
<div class="row"><span>For</span><b>${esc(KIND_WORDS[record.kind] || record.kind)}</b></div>
${period ? `<div class="row"><span>Period</span><b>${esc(period)}</b></div>` : ""}
<div class="row"><span>Receipt date</span><b>${esc(fmtDate(record.d))}</b></div>
<div class="row"><span>Registered</span><b>${esc(record.t.replace("T", " ").replace("Z", " UTC"))}</b></div>
</div>
<h2 style="font-size:20px;margin:26px 0 4px">Check the paper</h2>
<p class="note">Type what the receipt says. Nothing you type leaves your phone \u2014 the fingerprint is computed here and compared with the one on file.</p>
<form id="f" onsubmit="return check(event)">
<label>Receipt date</label><input id="date" type="date" value="${esc(record.d)}">
<label>Amount (\u20a6)</label><input id="amount" inputmode="numeric" value="${esc(String(record.amt))}">
<label>Received from (payer, as written)</label><input id="from" autocomplete="off">
<label>Issued by (landlord / business, as written)</label><input id="issuer" autocomplete="off">
<label>Property address (as written)</label><input id="property" autocomplete="off">
<label>Period covered (as written, or blank)</label><input id="period" autocomplete="off">
<button type="submit">Compare fingerprint</button></form>
<p id="out" style="font-size:18px;margin-top:14px"></p>
<script>${CANONICAL_JS}
var FP=${JSON.stringify(record.fp)};
async function sha256(s){var b=new TextEncoder().encode(s);var h=await crypto.subtle.digest('SHA-256',b);return Array.from(new Uint8Array(h)).map(function(x){return x.toString(16).padStart(2,'0')}).join('');}
async function check(e){e.preventDefault();var g=function(i){return document.getElementById(i).value};
var c=receiptCanonical({date:g('date'),amount:g('amount'),from:g('from'),issuer:g('issuer'),property:g('property'),period:g('period')});
var h=await sha256(c);var o=document.getElementById('out');
if(h===FP){o.innerHTML='<span class="ok">\u2713 Matches.</span> The words you typed are exactly what was registered.';}
else{o.innerHTML='<span class="bad">\u2717 Does not match.</span> One of the fields differs from what was registered \u2014 check spelling and spacing exactly as printed, then the amount and date.';}
return false;}
</script>`);
}

function home() {
  return page("DocOga receipt ledger", `<div class="kicker">DocOga \u00b7 receipt check</div>
<h1><span class="slab">Is this receipt real?</span></h1>
<p>Every receipt printed on <a href="https://docoga.com.ng/#receipt">docoga.com.ng</a> with the verification box ticked carries a code like <span class="code">DR-7K2M-9QX4</span>. Type it here.</p>
<form method="get" action="/v/"><label>Code</label><input name="c" placeholder="DR-XXXX-XXXX" autocomplete="off"><button type="submit">Check</button></form>
<p class="note">Under the Lagos Tenancy Law 2011, s.5, a landlord must issue a receipt stating the date, the names and addresses of landlord and tenant, the premises, the amount and the period \u2014 or face a \u20a6100,000 fine on conviction. The free receipt on DocOga carries every one of those lines.</p>`);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    if (request.method === "OPTIONS") {
      const cors = corsHeaders(request, env);
      return new Response(null, { status: cors.ok ? 204 : 403, headers: cors.headers });
    }
    try {
      if (path === "/api/register" && request.method === "POST") return await register(request, env);
      if (path === "/api/verify" && request.method === "GET") {
        const { code, record } = await lookup(env, url.searchParams.get("code"));
        return json(record ? { code, ...record, fp: undefined, fingerprint: record.fp } : { error: "not_found", code }, record ? 200 : 404, { "access-control-allow-origin": "*" });
      }
      if (path === "/api/stats" && request.method === "GET") return await stats(env, ctx, request);
      if (path === "/v" && request.method === "GET") {
        const raw = url.searchParams.get("c") || "";
        const code = normaliseCode(raw);
        if (code) return Response.redirect(new URL("/v/" + code, request.url).toString(), 302);
        return verifyPage(raw, null);
      }
      if (path.startsWith("/v/") && request.method === "GET") {
        const { code, record } = await lookup(env, decodeURIComponent(path.slice(3)));
        return verifyPage(code || decodeURIComponent(path.slice(3)), record);
      }
      if (path === "/" && request.method === "GET") return home();
      if (path === "/health") return json({ ok: true, service: "docoga-ledger" });
      return json({ error: "not_found" }, 404);
    } catch (e) {
      return json({ error: "server", detail: String(e && e.message || e).slice(0, 120) }, 500);
    }
  },
};

export { STATES, KINDS, CANONICAL_JS };
