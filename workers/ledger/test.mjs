// node --test test.mjs — the ledger worker against a fake KV. No network.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import worker, { makeCode, normaliseCode, validate, CANONICAL_JS } from "./index.js";
import * as qr from "./qr.js";

class FakeKV {
  constructor() { this.map = new Map(); this.writes = 0; }
  async get(k) { const v = this.map.get(k); return v ? v.value : null; }
  async put(k, value, opts = {}) { this.writes += 1; this.map.set(k, { value, metadata: opts.metadata }); }
  async list({ prefix = "", limit = 1000 } = {}) {
    const keys = [...this.map.entries()].filter(([k]) => k.startsWith(prefix)).slice(0, limit)
      .map(([name, v]) => ({ name, metadata: v.metadata }));
    return { keys, list_complete: true };
  }
}
class FakeCache { constructor() { this.m = new Map(); } async match(r) { return this.m.get(r.url) || null; } async put(r, res) { this.m.set(r.url, res); } }
globalThis.caches = { default: new FakeCache() };

const env = () => ({ KV: new FakeKV(), PUBLIC_URL: "https://ledger.test", ALLOWED_ORIGINS: "https://docoga.com.ng" });
const ctx = { waitUntil() {} };
const sha = (s) => createHash("sha256").update(s).digest("hex");
const good = (over = {}) => ({ fp: sha("v1|2026-10-19|850000|ada obi|mr k. bello|12 allen avenue, ikeja|oct 2026 – sep 2027"),
  state: "Lagos", amount: 850000, kind: "rent", from: "2026-10", to: "2027-09", date: "2026-10-19", ...over });
const post = (e, body, origin = "https://docoga.com.ng") => worker.fetch(new Request("https://ledger.test/api/register", {
  method: "POST", headers: { "content-type": "application/json", ...(origin ? { Origin: origin } : {}) }, body: JSON.stringify(body) }), e, ctx);

test("codes are DR-XXXX-XXXX in Crockford base32 and read back through confusable letters", () => {
  const c = makeCode();
  assert.match(c, /^DR-[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$/);
  assert.equal(normaliseCode("dr 7k2m 9qx4"), "DR-7K2M-9QX4");
  assert.equal(normaliseCode("DR-7K2M-9QXA"), "DR-7K2M-9QXA");
  assert.equal(normaliseCode("DR-OK2M-9QXI"), "DR-0K2M-9QX1");     // O→0, I→1
  assert.equal(normaliseCode("DR-7K2M"), "");
  assert.equal(makeCode(new Uint8Array([0, 1, 2, 3, 4, 5, 6, 7])), "DR-0123-4567");
});

test("validation refuses anything that is not the five index fields in range", () => {
  assert.equal(validate(good()).ok, true);
  assert.deepEqual(validate(good({ fp: "abc" })).errors, ["fp"]);
  assert.deepEqual(validate(good({ state: "Lagos State" })).errors, ["state"]);
  assert.deepEqual(validate(good({ amount: 500 })).errors, ["amount"]);
  assert.deepEqual(validate(good({ amount: 850000.5 })).errors, ["amount"]);
  assert.deepEqual(validate(good({ kind: "bribe" })).errors, ["kind"]);
  assert.deepEqual(validate(good({ date: "2031-01-01" })).errors, ["date"]);
  assert.deepEqual(validate(good({ from: "Oct 2026" })).errors, ["from"]);
  assert.deepEqual(validate(good({ from: "2027-01", to: "2026-12" })).errors, ["to"]);
  assert.equal(validate(good({ kind: undefined, from: "", to: "" })).record.kind, "rent");
  // Nothing personal survives validation even if a client sends it.
  const rec = validate(good({ name: "Ada Obi", phone: "0803", address: "12 Allen" })).record;
  assert.deepEqual(Object.keys(rec).sort(), ["amt", "d", "fp", "from", "kind", "st", "to", "v"]);
});

test("register: only the site may call it, it stores two keys with index metadata, and a re-print reuses the code", async () => {
  const e = env();
  let r = await post(e, good(), "https://evil.example");
  assert.equal(r.status, 403);
  r = await post(e, good(), null);
  assert.equal(r.status, 403);
  r = await post(e, good());
  assert.equal(r.status, 201);
  const body = await r.json();
  assert.match(body.code, /^DR-/);
  assert.equal(body.url, "https://ledger.test/v/" + body.code);
  assert.equal(e.KV.writes, 2);
  const stored = e.KV.map.get("ledger:r:" + body.code);
  const rec = JSON.parse(stored.value);
  assert.equal(rec.st, "Lagos"); assert.equal(rec.amt, 850000); assert.equal(rec.from, "2026-10"); assert.match(rec.t, /Z$/);
  assert.deepEqual(stored.metadata, { st: "Lagos", amt: 850000, kind: "rent", d: "2026-10-19", m: "2026-10" });
  assert.ok(!JSON.stringify(rec).includes("Ada"), "no payer name in the record");
  // Same fingerprint again → same code, no new write.
  r = await post(e, good());
  assert.equal(r.status, 200);
  assert.equal((await r.json()).code, body.code);
  assert.equal(e.KV.writes, 2);
  // Bad body → 422 with the field names, no write.
  r = await post(e, good({ amount: 10 }));
  assert.equal(r.status, 422);
  assert.deepEqual((await r.json()).fields, ["amount"]);
  assert.equal(e.KV.writes, 2);
});

test("verify: JSON and the human page find the record; unknown codes say so without leaking anything", async () => {
  const e = env();
  const { code } = await (await post(e, good())).json();
  let r = await worker.fetch(new Request("https://ledger.test/api/verify?code=" + code.toLowerCase()), e, ctx);
  assert.equal(r.status, 200);
  const j = await r.json();
  assert.equal(j.code, code); assert.equal(j.st, "Lagos"); assert.equal(j.fingerprint, good().fp);
  r = await worker.fetch(new Request("https://ledger.test/v/" + code), e, ctx);
  assert.equal(r.status, 200);
  const html = await r.text();
  assert.ok(html.includes("Registered."));
  assert.ok(html.includes("₦850,000") || html.includes("\u20a6850,000"));
  assert.ok(html.includes("Oct 2026 – Sep 2027"));
  assert.ok(html.includes("function receiptCanonical"));
  assert.ok(!html.includes("Ada"), "the page cannot show what it never stored");
  r = await worker.fetch(new Request("https://ledger.test/v/DR-0000-0000"), e, ctx);
  assert.equal(r.status, 200);
  assert.ok((await r.text()).includes("Not found."));
  r = await worker.fetch(new Request("https://ledger.test/v/?c=dr+7k2m+9qx4"), e, ctx);
  assert.equal(r.status, 302);
  assert.equal(r.headers.get("location"), "https://ledger.test/v/DR-7K2M-9QX4");
  r = await worker.fetch(new Request("https://ledger.test/api/verify?code=nope"), e, ctx);
  assert.equal(r.status, 404);
});

test("stats count by state, month and kind from key metadata — never from values", async () => {
  const e = env();
  await post(e, good());
  await post(e, good({ fp: sha("two"), state: "Rivers", amount: 1200000, kind: "caution", date: "2026-09-02", from: "", to: "" }));
  e.KV.get = async (k) => { if (k.startsWith("ledger:r:") || k.startsWith("ledger:fp:")) return e.KV.map.get(k)?.value ?? null; throw new Error("stats must not read values"); };
  const r = await worker.fetch(new Request("https://ledger.test/api/stats"), e, ctx);
  assert.equal(r.status, 200);
  const j = await r.json();
  assert.equal(j.total, 2);
  assert.deepEqual(j.by_state, { Lagos: 1, Rivers: 1 });
  assert.deepEqual(j.cells, { "Lagos|rent|2026-10": 1, "Rivers|caution|2026-09": 1 }, "one index cell per state × kind × month");
  assert.equal(j.latest_receipt_date, "2026-10-19");
  assert.equal(j.publish_at, 30);
  assert.deepEqual(j.by_month, { "2026-10": 1, "2026-09": 1 });
  assert.deepEqual(j.by_kind, { rent: 1, caution: 1 });
  assert.ok(j.note.includes("30 or more"));
});

test("the canonical function in the worker is byte-for-byte the one the site prints with", () => {
  const site = readFileSync(new URL("../../site/index.html", import.meta.url), "utf8");
  const m = site.match(/function receiptCanonical\(f\)\{[\s\S]*?\n\}/);
  assert.ok(m, "site/index.html must define receiptCanonical");
  assert.equal(m[0], CANONICAL_JS);
  // And it does what the fingerprint test above assumed.
  const fn = new Function(CANONICAL_JS + "; return receiptCanonical;")();
  assert.equal(fn({ date: "2026-10-19", amount: "850,000", from: "  Ada   Obi ", issuer: "Mr K. Bello", property: "12 Allen Avenue, Ikeja", period: "Oct 2026 – Sep 2027" }),
    "v1|2026-10-19|850000|ada obi|mr k. bello|12 allen avenue, ikeja|oct 2026 – sep 2027");
});

test("QR: bit-for-bit the Python qrcode library for every mask, versions 1–6 (fixtures), and the auto mask is one of them", () => {
  const fx = JSON.parse(readFileSync(new URL("./qr_fixtures.json", import.meta.url), "utf8"));
  assert.ok(fx.length >= 50);
  const versions = new Set();
  for (const f of fx) {
    const q = qr.encode(f.text, f.mask);
    versions.add(q.version);
    assert.equal(q.version, f.version, f.text + " mask " + f.mask);
    assert.equal(q.modules.map((r) => r.join("")).join("\n"), f.rows.join("\n"), "matrix differs: " + f.text + " mask " + f.mask);
  }
  assert.deepEqual([...versions].sort(), [1, 2, 3, 4, 5, 6]);
  const auto = qr.encode("https://docoga-ledger.johnazani.workers.dev/v/DR-7K3M-Q2XA");
  const forced = qr.encode("https://docoga-ledger.johnazani.workers.dev/v/DR-7K3M-Q2XA", auto.mask);
  assert.deepEqual(auto.modules, forced.modules);
  assert.ok([0, 1, 2, 3, 4, 5, 6, 7].map((m) => qr.penalty(qr.encode("docoga.com.ng/v/DR-0000-0000", m).modules)).every((s) => s >= qr.penalty(qr.encode("docoga.com.ng/v/DR-0000-0000").modules)), "auto picks the lowest penalty");
  assert.throws(() => qr.encode("x".repeat(107)), /too long/);
});

test("QR: the receipt gets an inline SVG of its check URL; /qr/<code>.svg serves the same code; nothing else is encoded", async () => {
  const e = env();
  const r = await post(e, good());
  const j = await r.json();
  assert.match(j.qr, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="0 0 \d+ \d+" width="68" height="68"/);
  assert.ok(j.qr.includes('aria-label="QR code: ' + j.url + '"'));
  assert.ok(!/<script|on[a-z]+=|href/.test(j.qr));
  const again = await (await post(e, good())).json();
  assert.equal(again.qr, j.qr, "a re-print carries the same QR");
  const img = await worker.fetch(new Request("https://ledger.test/qr/" + j.code.toLowerCase() + ".svg"), e, ctx);
  assert.equal(img.status, 200);
  assert.equal(img.headers.get("content-type"), "image/svg+xml; charset=utf-8");
  const body = await img.text();
  assert.ok(body.includes('aria-label="QR code: ' + j.url + '"') && body.includes('width="240"'));
  assert.equal((await worker.fetch(new Request("https://ledger.test/qr/short.svg"), e, ctx)).status, 404);
  const page = await (await worker.fetch(new Request("https://ledger.test/v/" + j.code), e, ctx)).text();
  assert.ok(page.includes("<svg ") && page.includes("This QR opens this page"));
});
