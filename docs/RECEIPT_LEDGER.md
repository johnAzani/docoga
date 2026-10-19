# The Receipt Ledger — a verification code on every receipt, and the data behind Nigeria's first live rent index

**Announced in the Founder's brief of 19 Oct 2026 (1:45pm); built the same afternoon. ₦0.**
Step 2 of the north star in `docs/MANDATE.md` § Standing orders: *document of record → verified
receipt ledger → rent index → diaspora USD → B2B → West Africa.*

---

## 1. Why this, and why now (research first — Rule Zero)

### 1a. The law already demands the receipt we print
Lagos Tenancy Law 2011, **s.5(1)–(3)** (gazette text, Lagos Ministry of Justice): every landlord
*shall* issue a rent payment receipt stating **(a)** the date rent was received, **(b)** names and
addresses of landlord and tenant, **(c)** description and location of the premises, **(d)** amount
paid, **(e)** the period the payment relates to; failure → **₦100,000 fine on conviction**
(s.5(3)); separate receipts for security deposit / service charges (s.5(4)). The 2025 draft
Tenancy and Recovery of Premises Bill (Lagos House of Assembly, Aug 2025) keeps the duty and
extends it expressly to cash, bank teller and electronic transfer (draft s.6) — Tier B until
passed. DocOga's free receipt carries every s.5(2) line. *(Tier A — primary text.)*

### 1b. Nobody in Nigeria measures the rent actually paid
- The NBS publishes CPI with a housing component monthly (rebased to 2024 in 2026; headline
  14.63% for September 2026) — a national price index, **not** a rent index, and **not** by state.
- "There is no official rent index for Lagos. The National Bureau of Statistics does not publish
  rents for the state" (rentlet.com, Oct 2026). Lagos had the highest all-items inflation of any
  state in August 2026 (23.68%).
- Private series exist but measure **asking** rents from listings (Nigeria Property Centre
  "average prices", Estate Intel, GTI's 3,200-listing Lagos study reporting 80–120% two-year
  rises against 7–9% wage growth; nigeriahousingmarket.com's tenant sample: +105.6% Lagos,
  +81.1% Abuja). Asking is not paid. Nobody holds **paid** rent at scale with date, state and
  period — because nobody issues the receipts. *(Tier B — named sources, Oct 2026.)*
- Precedents elsewhere: Zillow's ZORI (repeat-rent method, US), ONS Price Index of Private Rents
  (UK, from letting-agent data), Spain's INE Reference Index of Housing Rentals (from tax-filed
  rental data). Each became the number regulators quote. The Nigerian equivalent does not exist.

**That gap is the "world powers" door.** A live, state-level index of rent actually paid is what
a housing ministry, the CBN, the NBS, the World Bank and the AfDB would sit down for. It is
reached by being the receipt everybody uses — which is what the free tool already is.

### 1c. Privacy law shapes the design, and the design clears it
Nigeria Data Protection Act 2023: *personal data* is information relating to an **identified or
identifiable** individual (s.65; mirrors GDPR art. 4(1)); **s.24(1)(c)** data minimisation —
"adequate, relevant and limited to the minimum necessary"; GAID 2025 reads "minimum necessary"
as *the least possible data essential to the stated purpose*. Data that cannot be related to an
individual is outside the Act. So the ledger stores **no name, address, phone, IP or cookie** —
only state (37 values), amount, kind, period, date, and a one-way fingerprint of the receipt's
words computed in the issuer's browser. *(Tier A — statute text; GAID 2025.)*

### 1d. Stamp duty on receipts — recorded, not printed
Nigeria Tax Act 2025 (in force 1 Jan 2026) folded the EMTL into stamp duty: ₦50 on electronic
transfers ≥ ₦10,000, paid by the **sender**; the 2020 FIRS notice put ₦50 adhesive duty on paper
receipts. Whether a ₦50 denoting stamp is still required on a *paper* rent receipt under the 2025
Act is **not verified** (Tier C/E) — so the receipt prints nothing about it. Revisit with the
Act's schedule before any claim.

### 1e. The free-tier arithmetic (Cloudflare, Oct 2026)
Workers Free: 100,000 requests/day; **KV 1,000 writes/day, 100,000 reads/day, 1 GB**
(account-wide); **D1 100,000 row writes/day, 5M row reads/day, 5 GB** — hard-enforced since
1 Sep 2026. Today the site registers a handful of receipts a day, so KV is right: no new resource,
the namespace docoga-pass already binds, two writes per receipt (`ledger:r:<code>` with index
metadata, `ledger:fp:<hash>` for re-print dedup). **Trigger to move to D1: 300 registrations in
any one day** (60% of the shared write budget) — spending nothing, just a schema and a binding.

## 2. What was built

| Piece | Where | What it does |
|---|---|---|
| Ledger Worker | `workers/ledger/index.js`, `wrangler.toml` | `POST /api/register` (site origin only; validates 7 fields; refuses anything else; same fingerprint → same code, no second write) · `GET /v/<code>` human page with **Check the paper** (re-computes the fingerprint in the reader's browser; nothing typed leaves the phone) · `GET /api/verify?code=` · `GET /api/stats` (counts by state / month / kind from key metadata, cached 1 h) |
| Codes | `makeCode` | `DR-XXXX-XXXX`, Crockford base32 (no I/L/O/U), 40 bits; reader input forgives O→0, I/L→1, spaces, lower case |
| Site | `site/index.html` receipt tool | **State** select; **verification box ticked by default** (opt-out, plainly worded); on *Print / Save PDF* the code is minted first (≤ 3.5 s, never blocks printing), printed in a dashed strip under the signature line with the check URL; period text like "Oct 2026 – Sep 2027" is parsed to `from/to` months; the kind is inferred from "Being payment for" (caution/service/agency/rent/other) |
| Deploy | `.github/workflows/deploy-ledger.yml` | Mirrors the clock's: unit tests → `wrangler deploy --keep-vars` → redacted log → live probe. Never touches docoga-pass |
| Tests | `workers/ledger/test.mjs` (6, fake KV; run by `npm test`), `tools/tests/test_receipt_ledger.py` (10 seams) | incl. a byte-for-byte check that `receiptCanonical()` in the site and in the worker are the same function |

Fingerprint: `SHA-256("v1|date|amount|payer|issuer|property|period")`, each field whitespace-
collapsed, trimmed, lower-cased; amount as an integer. Changing one character on the paper
changes the hash.

## 3. What the owner may be asked for (not blocking)
- ~~A route `docoga.com.ng/v/*` → `docoga-ledger`~~ — **added by the owner 19 Oct 2026, 2:50pm**
  (ten taps, one per message). `PUBLIC_URL` is now `https://docoga.com.ng`; the paper, the QR
  and the check page all say `docoga.com.ng/v/DR-…`. The workers.dev address keeps answering, so
  receipts printed before 2:50pm still verify. The deploy probes the route from outside
  (`LEDGER_ROUTE=`).

## 4. What it costs and what it can break
- ₦0. Two KV writes per new receipt; reads on the verify page; `/api/stats` is cached an hour.
- The payment Worker is untouched; the ledger has its own deploy, its own tests, its own prefix.
- If the ledger is down, the receipt prints without a code (the fetch is bounded at 3.5 s).
- Abuse: `/api/register` accepts only the site's origin and seven validated fields ≤ 2 KB; a
  forged origin could still spend writes — the D1 trigger and a daily count in the dashboard
  feed are the watch. No counter is kept (a counter would itself be a write).

## 5. The index: publication rules (decided now, so the data is collected right)
1. **Unit of observation**: one registered receipt — state, kind, amount, period months, date.
2. **A cell is published only with ≥ 30 receipts** (state × kind × calendar month); below that,
   counts only. Medians and inter-quartile ranges, never means (rents are heavy-tailed).
3. **Annualise before comparing**: amount ÷ period months × 12 when the period parses; receipts
   without a period are counted but excluded from the rent level.
4. **Repeat-receipt method when the data allows** (same fingerprint lineage is impossible by
   design — so same state × kind × amount band, period-over-period), the way ZORI handles
   composition; until then, a simple median by cell with the sample size printed beside it.
5. **First publication**: when any state reaches 30 receipts in a month — a single page on the
   site and a post in every lane, with the method on the page. Lagos first, on current traffic.
6. Nothing in the index can be traced to a person; the fingerprint is never published.

## 6. Roadmap from here (each step announced in a Founder's brief before it is built)
- ~~Registration count on the owner dashboard~~ — **done 19 Oct 2026 (step 1 of "one after the
  other")**: the Today tab carries a "Receipts verified" card and the Website tab a "Receipt
  ledger" panel (total, this month, states of 37, cells ready to publish, the six cells closest
  to 30 with progress bars, by-state table). The page reads `/api/stats` straight from
  `docoga-ledger` (public counts, CORS `*`, cached an hour); the payments worker is not involved.
  `/api/stats` now also returns `cells` (`state|kind|month` → count), `latest_receipt_date` and
  `publish_at`. The D1 trigger (300 registrations/day) is what the "This month" card is for.
- ~~QR of the check URL on the paper~~ — **done 19 Oct 2026 (step 2)**. The encoder lives in
  the worker (`workers/ledger/qr.js`: byte mode, level M, versions 1–6, all eight masks with the
  penalty rules, Reed-Solomon over GF(256)) and is pinned bit-for-bit to the Python `qrcode`
  library through 59 committed fixtures (`qr_fixtures.json`), so the page carries no QR code
  at all: `/api/register` returns the SVG (`qr`), the page checks it against a strict
  allow-list regex (`QR_SAFE`) before inlining it, and the receipt prints an 18 mm square
  beside the code. `GET /qr/<code>.svg` serves the same image at 240 px for the check page and
  anything that comes later (issuer's book, WhatsApp share). Page weight +≈320 B gzipped.
- ~~`docoga.com.ng/v/*` route~~ — **done 19 Oct 2026, 2:50pm (step 3, owner's tap)**; see §3.
- Landlord/agent "book": the issuer keeps a list of their own codes in local storage; the step
  before the B2B seat.
- The index page and the first "DocOga Rent Monitor" post.

Sources read 19 Oct 2026: Lagos Tenancy Law 2011 gazette (lagosministryofjustice.org); Lagos
State House of Assembly, Tenancy and Recovery of Premises Bill 2025 (draft); NDPA 2023
(cert.gov.ng), NDPC GAID 2025, ICLG Nigeria 2026, Mondaq on minimisation (Mar 2026); Cloudflare
Workers pricing & KV limits pages (Oct 2026), D1 free-tier enforcement changelog (1 Sep 2026);
rentlet.com Lagos (Oct 2026), Guardian NG on GTI's Lagos study (19 Oct 2026),
nigeriahousingmarket.com (Dec 2025), Nigeria Property Centre average prices (Jul 2026); NBS CPI
September 2026 via Vanguard/Tribune; Kuda/UBA/GTBank notices and Deloitte on the ₦50 stamp duty.
