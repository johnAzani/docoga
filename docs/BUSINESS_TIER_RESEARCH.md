# DocOga Business Tier — Deep Research: Custom · Annual · Per Team

**Date:** 11 October 2026 · **Owner:** John Azani · **Operator:** Arena agent under `docs/MANDATE.md`
**Status:** Research dossier + proposed design. No code changed, no price published, no outreach sent.

**Owner instruction (11 Oct 2026):** The Business tier is **Custom**, **annual**, **per team**,
serving **estate agents, property managers, landlords & HR teams**. It must be **automated —
a customer should not need to send a WhatsApp message** at any point in the buy, use, renew
or support path.

Rule Zero applies with full force: every market number below is **cited** (source register,
§12) or tagged **UNVERIFIED** / **ADVERTISED** (a vendor's own claim) / **HYPOTHESIS**
(this document's reasoning). Nothing is invented to make the arithmetic look better.

---

## 0. Executive summary

1. **The model the owner fixed is viable and matches how the Nigerian market prices.**
   Local property-management software prices by *units + team members* (Dwellrs ₦10,000/mo
   for 5 units; Rentyx ₦80,000/mo for 10 units + 1 team member; ADVERTISED, both live-checked
   11 Oct 2026). "Annual, per team" sits inside that pattern. DocOga is a **document** product,
   not a property-management suite, so it prices by **seats + document volume**, which must
   price *below* the suites it does not replace.

2. **The real competitor is not software — it is the per-document bill.** For every tenancy
   event in Nigeria, a business currently pays: agency fee **10% of one year's rent**
   (LASRERA-capped in Lagos), legal/agreement fee **5–10%** (lawyers: 10% of annual rent per
   the LPRO 2023 guideline; ₦20,000–₦80,000 flat in practice), plus receipts for rent and
   caution fee. On a ₦1.5m/yr rental that is **₦150,000–₦300,000 per agreement** before any
   staff time. A team pass that removes the *document* cost of those events is the value
   story — not "cheaper than a pass".

3. **Full automation is technically proven on the current stack.** Flutterwave provides
   every primitive needed: **virtual accounts with instant `charge.completed` webhooks**
   (bank transfers auto-detected — no human reconciliation), **payment plans** (card
   auto-renewal with pre-charge emails and self-serve unsubscribe), **invoices**, and 2.0%
   local fees. Combined with the existing Worker + KV + Brevo (all inside the ₦0-infra
   mandate), the entire buy→issue→use→renew loop can run with **zero customer WhatsApp**
   and near-zero owner time. The worker's existing dual-signature webhook handler
   (`worker/index.js`) already settles a real payment end-to-end; the business path
   extends the same machinery.

4. **The live Business card is a liability until fixed or fulfilled.** It promises (a) the
   firm's name **and logo** on every document, (b) one shared pass, (c) invoice + bank
   transfer, (d) **a named human on WhatsApp**, (e) **a quote within one working day**.
   None of (a)–(c) is implemented; (d)–(e) are exactly what the owner now orders removed.
   Two compliant paths: **ship the automation that delivers (a)–(c)** (recommended), or
   correct the card to stop promising them. Selling with today's card while the backend
   is absent is the single biggest commercial and reputational risk in this dossier.

5. **Recommended shape (PROPOSED, not validated):** four annual tiers priced by seats +
   document volume — Starter (3 seats) **₦96,000/yr**, Standard (8 seats) **₦240,000/yr**,
   Growth (20 seats) **₦480,000/yr**, and **Custom** computed by a published **self-serve
   configurator** (seat unit price + volume unit price) so "Custom" never means "wait for a
   human". Every price is a config change, not a code change, so discovery can re-price
   without touching the product.

6. **Market denominators (all cited):** NIESV lists **1,433–1,496 registered firms** and the
   profession counts **~4,450–5,000** registered estate surveyors/valuers; a Lagos
   government statement put CAC-registered agents/developers in Lagos at **50,000** (2020 —
   stale, treated as order-of-magnitude only); Nigeria Property Centre's live directory
   lists **16,946** self-listed agents (UNVERIFIED as a current true count). The HR segment
   sits in **~1.24 million registered small+medium enterprises** (SMEDAN/NBS, Dec 2020).
   The national housing deficit is **>28 million units** with Lagos stock ~1.49m vs demand
   ~4.69m (PAC Research 2026) — the rental paperwork this tier serves is structural, not
   cyclical.

7. **What remains unknown (Rule Zero, stated plainly):** actual buyer pain, frequency and
   spend per segment (no interviews yet — the discovery groundwork of 10 Oct 2026 is
   unexecuted), willingness to pay at any of the proposed prices, whether a business will
   pay by card/transfer through an automated checkout vs expecting a relationship, and
   whether the Flutterwave account is KYC-approved for virtual accounts and invoices.
   Discovery (permissioned, per the groundwork) and a bounded pilot remain the validation
   gates. **The automation is buildable now; the price is not yet validated.**

---

## 1. Owner instruction and scope

### 1.1 What the instruction fixes

| Dimension | Owner decision | Consequence for design |
|---|---|---|
| Price model | **Custom** | No single number is "the price". Custom must still be **instant and self-serve** — a configurator that computes a quote in-page, not a person. |
| Billing period | **Annual** | One invoice per year per team. Cash upfront; refunds and renewals must be automated (a human chasing annual renewals breaks the mandate's autonomy rule). |
| Unit | **Per team** | The licence is the **team** (organisation), with **seats** inside it. Not per document, not per pass-holder, not per browser. |
| Segments | Estate agents, property managers, landlords, HR teams | Four segment presets in the configurator; one product underneath. |
| Friction rule | **No WhatsApp from the customer** | Every step — quote, signup, payment, issuance, seat changes, invoices, renewal, support — runs on the site + email. WhatsApp remains available as an *optional* convenience for consumers on the retail tier; the Business path must be completable without it. |

### 1.2 What "automated" must mean operationally

- **Quote:** in-page, instant, from a published formula. No "get a quote" button that opens a chat.
- **Onboarding:** email + magic link (no passwords to reset — every reset is a support ticket).
- **Payment:** card/USSD/POS via Flutterwave checkout, **or** bank transfer into a per-invoice
  virtual account that the webhook confirms automatically. No "send a transfer and message us
  the screenshot".
- **Issuance:** webhook-driven. The moment `charge.completed` fires, the team is live and
  every seat gets an email. Target: < 5 minutes payment → live, no owner action.
- **Use:** team members sign in on any device; documents carry the firm's name/logo.
- **Seats:** owner adds/removes people by email in the portal; removal revokes access the same day.
- **Invoices:** PDF, VAT-inclusive, auto-emailed; downloadable from the portal for 12+ months.
- **Renewal:** automated reminders (90/30/7 days), auto-charge if a card is stored,
  otherwise a fresh invoice + virtual account. Grace period, then graceful downgrade — never silent lockout.
- **Support:** email (Brevo) with a stated response target, in-app FAQ, status page.
  The owner may keep WhatsApp *internally* to answer email; it must never be a required
  customer step.

### 1.3 Relation to the discovery groundwork (10 Oct 2026)

The groundwork's rules stay in force for **validation** (permissioned interviews, no cold
WhatsApp, no scraped lists, evidence ladder 0–7). This dossier does not override them:
**shipping a self-serve product is not outreach.** The product can exist publicly with an
honest price; interviews, if run, use the workbook unchanged. The one tension — the
groundwork says price discovery should follow interviews, the owner has fixed the model —
is resolved by: the **model** (custom/annual/per-team, configurator) ships now; the
**numbers** inside the configurator are labelled PROPOSED and are a config change until
discovery (or live usage data) says otherwise.

---

## 2. Business as it exists on the live site today

Observed from `site/index.html` (repo state at session start, 11 Oct 2026) and
`worker/index.js`, cross-checked against the 10 Oct capability inspection in
`docs/B2B_OUTREACH_GROUNDWORK.md` (on `arena/47d148f1-docoga`).

### 2.1 The card, word for word (live)

> **Business — Custom — annual, per team** — *For estate agents, property managers,
> landlords & HR teams*
> - Everything in Oga Pass, for your whole team
> - **Your firm's name and logo** on every document instead of ours
> - **One shared pass** — no per-person codes to chase
> - **Invoice and bank transfer, no cards, no reimbursements**
> - **A named human on WhatsApp who knows your account**
>
> [Get a Business quote →] *(wa.me/2349021852845 "I'd like a Business quote for my team")*
> *One annual invoice. Cheaper than a single lawyer-drafted agreement per branch.
> We quote within one working day.*

### 2.2 Promise vs capability (the gap table)

| # | Card promise | Repo-observed reality | Gap class |
|---|---|---|---|
| P1 | Firm's **name and logo** on every document | No logo upload or rendering flow anywhere in `site/index.html`; some templates take a firm-name field, but no branding pipeline | **Not built** |
| P2 | **One shared pass** for the team | The pass is a **bearer code** with expiry/reference/email data. No accounts, no seats, no roles, no offboarding. "Sharing" a code is a terms violation in practice (codes are non-transferable per `site/terms.html`) | **Not built** (and a compliance hazard if sold as-is) |
| P3 | **Invoice and bank transfer** | The `/issue` bridge (Selar→Zapier) exists in code but is **intentionally disabled**; there is no invoice object, no VAT-inclusive B2B invoice, and no automatic transfer confirmation. The worker only auto-setstle the ₦2,000 retail pass via the Flutterwave webhook | **Not built** |
| P4 | **Named human on WhatsApp** | = the owner's personal time, 24/7, unbounded. Not a product; violates the mandate's autonomy rule ("If it needs a human every day, it is broken") | **Human cost, not automation** |
| P5 | **Quote within one working day** | Manual, owner-dependent, no quoting tool exists | **Human cost, not automation** |
| P6 | "Everything in Oga Pass" | True — the 10 tools exist and work (repo-observed; DOM suite guards them) | **Deliverable** |
| P7 | Annual billing | Nothing annual exists; pass is 30-day from activation. Terms describe 30-day codes | **Not built** |

**Consequence:** the card is currently selling an un-built product with a human-in-the-loop
quote. Under the owner's 11 Oct instruction, P4 and P5 are to be **deleted** and P1–P3,
P7 **built**. Section 8 gives the exact replacement copy.

### 2.3 What the existing machinery already provides (repo-observed, `worker/index.js`, 538 lines)

| Component | State | Reuse for Business |
|---|---|---|
| `POST /flw-webhook` — dual-signature (v3 `verif-hash` + v4 `flutterwave-signature`), idempotent, aliases every id under reference/tx_ref | **Live, proven with real money** (₦100 rehearsal 19 Sep; production passes since) | Extend: recognise business charge amounts/refs → activate team instead of retail code |
| `GET /verify`, `GET /activate` — server-owned expiry, top-up carry-over | Live | Retail only; business uses team records |
| KV store (`docoga-kv`), cron `scheduled()` handler (07:00 daily) | Live | Team/brand/seat/invoice records; renewal sweeps |
| Email via Brevo (primary; SMTP2GO/Resend fallback) — **verified working 10 Oct, owner received test pass email** | Live | All customer emails (issuance, invoices, renewals, seat invites) |
| Flutterwave account: local card/transfer/USSD proven; **international approval open question** (REVENUE.md §5) | Partial | Business is NGN-only for v1 (no international approval needed) |
| Paystack fallback code (`PROVIDER` env) | Coded, untested in prod | Optional backup path |
| Site: Cloudflare Worker with static assets (`docoga-git`), custom domain `docoga.com.ng`, cache-purge deploy step | Live | Business pages/portal are static + worker API; deploy path exists and is automated |

---

## 3. The four segments, in depth

Each segment: who they are (numbers), scale, the document workflow mapped onto DocOga's 10
tools, current method + cost anchors, who buys, what "team" means to them, value arithmetic,
and objections. Volume figures are **HYPOTHESIS models** (clearly labelled) built on cited
market mechanics — they are planning inputs, not measurements.

### 3.1 Estate agents (letting agents)

**Who and how many (cited):**
- NIESV (the professional body) lists **1,496 registered firms** on its national "List of
  Firms" page and **1,433** on its directory sub-domain (both accessed 11 Oct 2026 — the two
  counts differ; treat as ~1.4–1.5k).
- The profession itself: NIESV leadership has publicly stated **~4,450 registered** estate
  surveyors and valuers (chairman statement, "another 98 approved"), and separately "**about
  5,000 members**" — i.e., ~4.5–5k *individual professionals*.
- Lagos State government (2020, via The Nation): **50,000** estate agents and property
  developers registered with CAC in Lagos, excluding law firms. **Stale (2020)** — used only
  as order-of-magnitude.
- Nigeria Property Centre live directory: **16,946** self-listed agents nationwide
  (accessed 11 Oct 2026; self-listing, UNVERIFIED as a true headcount — includes
  duplicates/inactives).
- AEAN (Association of Estate Agents of Nigeria) exists as a professionalisation channel
  (membership page reviewed in the 10 Oct groundwork).

**Reality of the base:** a large informal agent population around ~1.4–1.5k professional
firms and thousands of registered individuals. The **paying** segment is the formal tail:
registered firms and established agents who bill agency fees professionally — plausibly
**thousands, not tens of thousands** (UNVERIFIED; no sourced figure for active paying agents).

**Scale:** a typical letting agent handles a handful to a few dozen lettings/year.
An agent doing 20 lettings/year on average ₦1.5m/yr rentals touches:
- 20 tenancy agreements (+ renewals at 50–75% of original drafting fee — cited below)
- 20 agency-fee receipts (10% of one year's rent, ~₦150k each on that rent)
- 20 caution-fee receipts (1–2 months' rent; ~₦125k–₦250k)
- 20+ rent receipts (annual advance → ~1–2 per tenancy/year)
- Quit notices / demand letters at turnover (Lagos: 30-day quit notice practice per
  Tenancy Law s.13 — see `docs/STATE_TENANCY_RESEARCH.md` for verified state law)

**Current method + cost (cited):**
- Tenancy agreement drafted/reviewed by a lawyer: **10% of one year's rent** (LPRO 2023
  guideline; Lagos practice often 10% of *two* years' rent) — **₦150k–₦300k** on
  ₦1.5m/yr rent. Renewal agreements: **50–75%** of the original drafting fee.
- Agreement/legal fee flat in practice: **₦20,000–₦80,000** (Cabans, 2026).
- Self-serve documents exist (LawDepot NG: **₦8,500** per residential tenancy document;
  Wonder.legal: free basic, pay for customisations — **exact price UNVERIFIED**).
- Or: Word template + Word + PDF, prepared by an admin — staff time, no cost line,
  error-prone, no branding consistency. **HYPOTHESIS:** most small agents are here.

**Who buys:** the agent principal (often the owner). Decision is fast (one person),
budget is the admin fee line. Procurement friction: low — but invoicing with VAT matters
for firms that keep books properly.

**What "team" means:** 1–5 seats (principal + admin(s) + estate surveyor). Roles matter
less; **consistency of output under the firm's name** matters most.

**Value arithmetic (HYPOTHESIS, worked on cited anchors):** 20 lettings/yr × (₦150k–300k
agreement cost) = **₦3.0m–₦6.0m/yr of document-adjacent spend** avoided or compressed,
plus admin hours (agreement prep is commonly 30–90 min of skilled time — HYPOTHESIS, to be
measured in discovery). Against that, a Standard team at ₦240k/yr is ~4–8% of the
document-adjacent spend. The pass does not compete with a lawyer's *review* of unusual
terms — it competes with the *routine drafting* bill, which is the repeatable part.

**Objections:** "tenants/landlords expect a lawyer-stamped document"; "our agreements are
custom"; "I already have a Word template". Response pattern: the product is for the
*routine 80%* (standard residential lettings, renewals, receipts, notices); unusual terms
go to counsel — the documents stay accurate because the state-law content is sourced
(`docs/STATE_TENANCY_RESEARCH.md`), and the tool says so on every page.

### 3.2 Property management firms

**Who:** firms managing rental portfolios for landlords — the NIESV directory includes a
"Property and Facility Management" category (repo: `B2B_OUTREACH_GROUNDWORK.md` §6
prospect table, e.g. JMJ Properties, Aadum & Co, Bello & Co — **ADVERTISED** service
claims, not verified operations). Abuja and Lagos concentrate the formal tail.

**Scale:** 10–250 units is the realistic DocOga-relevant band. (Dwellrs' own tiers —
5/50 units and "enterprise" — and Rentyx' 10/50/250 brackets, both ADVERTISED, are the
market's own read of this band.)

**Scale-based document model (HYPOTHESIS, 50-unit portfolio, 30% annual turnover —
turnover rate itself UNVERIFIED for Nigerian rentals; Lagos rent-advance mechanics make
tenancies 1–2 yr, which *lowers* annual turnover vs monthly-rent markets):**
- New tenancies: ~15/yr → 15 agreements + 15 caution receipts + 15 agency receipts
- Renewals: ~35/yr → 35 agreements (renewals at 50–75% of drafting fee if outsourced)
  + 35 rent receipts
- Ongoing: 50 rent receipts/yr (annual advance) to 600 (monthly, if the firm collects
  monthly — common for commercial units) + periodic service-charge invoices
- Arrears: 5–15 demand letters/yr; 5–15 quit notices/yr
- **Total: ~100–700 documents/yr** depending on collection cadence. This is the segment
  where volume bands in §6 earn their keep.

**Current method + cost (cited where cited):**
- Management fee income: **5–10% of annual rent** (Mumtaz 2026; Cabans 2026) — i.e., a
  firm managing ₦10m/yr of rent earns ₦500k–₦1m/yr. A ₦240k–₦480k/yr tool is 25–50% of
  *gross* management income at the small end — **too rich** if framed as "software",
  right-sized if framed as "the paperwork your admin does every day" (a fraction of one
  admin's loaded cost — HYPOTHESIS).
- Many use the property-management suites (Dwellrs/Rentyx/MyTenant — §4) **or**
  spreadsheets + Word. The suites handle rent collection/maintenance/tenants but
  (per ADVERTISED feature lists) treat documents as an afterthought; several are
  free-with-pay-as-you-go (MyTenant) which crowds the low end.
- **Key positioning constraint (from the groundwork, carried forward):** if the buyer's
  pain is collections/records/approvals, DocOga is *not* the answer — do not reposition
  into a property suite. DocOga's job here: **the outgoing document layer** under whatever
  record system they already have.

**Who buys:** managing director / operations head. Approver = payer (small firms).
Procurement: low friction, but they want an invoice they can file (VAT-inclusive PDF —
P3 in §2.1).

**What "team" means:** 3–20 seats: ops lead, 1–4 field/admin staff, accountant (invoice
tool), principal (approver). This is the segment where **seat offboarding** (staff leave;
the 10 Oct groundwork flags shared devices and offboarding as a real question) and
**branding** (client-facing documents under the firm's name) carry genuine value.

### 3.3 Landlords (semi-professional, 3–30 units)

**Who:** individuals/family offices with several rentals — the largest *count* of the four
segments (the housing stock alone is ~1.49m units in Lagos vs 4.69m demand — PAC Research
2026; national deficit >28m units). Most are invisible to B2B tooling: they are not "firms".
The DocOga-relevant slice: landlords with **3+ units who currently pay per-document fees**
(agency/legal per letting) or employ an admin — HYPOTHESIS: a few percent of the
multi-unit base; no sourced denominator exists.

**Scale-based document model (HYPOTHESIS, 10 units, 1-year tenancies, Lagos mechanics):**
- 6–10 tenancy events/yr (new + renewals) → agreements + caution receipts + agency receipts
- 10 rent receipts/yr (annual advance)
- 1–3 demand letters, 1–2 quit notices/yr
- **Total: ~25–40 documents/yr** — a Starter-tier volume.

**Current method + cost (cited):** the tenant-side fee stack is the landlord/agent-side
mirror: agency 10% + legal 5–10% + caution 10–20% (DeyWithMe/Cabans/LandsOfNigeria fee
tables, 2026). On ₦2m/yr rent that's **₦350k–₦550k of fees per tenancy event**
(cabans worked example: ₦2.52m all-in on ₦2m/yr with 1-yr advance). The landlord who
prepares documents themselves still pays the *agreement* fee to a lawyer for stamping
validity and keeps receipts ad hoc.

**Who buys:** the landlord themselves. No approval chain. Price sensitivity: high in
naira, but the anchor is the per-event fee, not the pass. **Key friction:** they are not
"software buyers" — the configurator must sell in their language: *"your firm's name on
the paper, one invoice a year, pay by transfer like you already do."*

**What "team" means:** 1–3 seats (landlord + family member/agent/admin). Branding =
family/firm name. This segment will understate team needs; **sell them 2–3 seats and let
the configurator price it.**

### 3.4 HR teams (SMEs)

**Who and how many (cited):**
- **~39.65m MSMEs** operated in Nigeria (Dec 2020, SMEDAN/NBS via The Guardian), of which
  **small+medium (SMEs) = 1,240,965** (3.1%) — the registered, formal businesses with
  payroll. That ~1.24m is the true HR-segment denominator.
- MSMEs ≈ **96.7% of businesses** and ~**46–48% of GDP** (SMEDAN/NBS; PwC via
  entrepreneurs.ng). Classification: small = 10–49 employees, ₦5m–₦50m turnover;
  medium = 50–199, ₦50m–₦500m (National MSME Policy definitions, cited via
  entrepreneurs.ng).

**Scale-based document model (HYPOTHESIS, 50-employee SME):**
- Employment contracts: at ~20% annual attrition + hiring ≈ **10–15/yr**
- Payslips: **600/yr** (50 staff × 12) *if* the firm prints/emails payslips — firms that
  outsource payroll to an HR platform do **not** need this; the fit is SMEs running
  payroll in-house (typical of the small band, 10–49 staff — HYPOTHESIS)
- Warning letters: 0–5/yr
- Termination/settlement letters, secondment/contractor letters: a few/yr
- Invoices (supplier/freelancer side): the invoice tool already serves this
- **Total: ~620–680 documents/yr for the 50-staff case; ~130–150 for a 10-staff shop.**

**Current method + cost (cited anchors):**
- Full HR SaaS in Nigeria: **$6–8 PEPM** (Talstack, ADVERTISED ≈ ₦9k–13k/employee/mo);
  US-built platforms **$15–25 PEPM** (≈₦24k–40k at ₦1,550/$ — **FX UNVERIFIED**);
  global HR software band **$5–30 PEPM** (UKG/Compono/Guru guides); a Nigerian
  HR/payroll/bookkeeping vendor prices from **$0.99/user/mo (annual)** with 5-employee
  minimums (hrpayhub.com, ADVERTISED).
- **DocOga is not an HR suite** — it supplies the document layer (contracts, payslips,
  warning letters) at a fraction of suite pricing. A 20-person shop's HR document need at
  Starter/Standard (₦96k–240k/yr) is well below one HR SaaS seat-year.
- Lawyer cost for a single employment contract: the same 10%-style drafting practice
  applies (LPRO 2023 covers tenancy explicitly; employment drafting fees are **UNVERIFIED**
  as a published rate — do not cite a number).

**Who buys:** the HR manager or, in small firms, the owner/operations lead. The HR
manager is the champion; the owner pays. Decision cycle: weeks, not days (it's a
software purchase, not a fee payment).

**What "team" means:** 1–10 seats: HR manager, admin, finance (payslip sign-off), owner
(viewer). **Payslip volume** is the metering story: a generous document band matters here
more than in property (600 payslips/yr ≈ 50/mo for 50 staff — must fit comfortably in a
band, or HR churns instantly).

### 3.5 Cross-segment summary

| Segment | Paying base (order) | Typical team | Docs/yr (HYP.) | What they pay today (cited) | Entry tier fit |
|---|---|---|---|---|---|
| Estate agents (letting) | ~1.4–1.5k firms + thousands informal (UNVERIFIED active count) | 1–5 seats | 60–120 | ₦20k–300k per agreement event + staff time | Starter/Standard |
| Property managers | Formal tail of NIESV "Property & Facility Mgmt" category (UNVERIFIED count) | 3–20 seats | 100–700 | Suite software ₦10k–850k/mo (ADVERTISED) **or** Word + admin | Standard/Growth |
| Semi-pro landlords | % of multi-unit base (no sourced denominator) | 1–3 seats | 25–40 | ₦350k–550k fees per tenancy event on ₦2m rent (cited tables) | Starter |
| HR teams (SMEs) | ~1.24m registered SMEs (2020) — small fraction document-hungry | 1–10 seats | 130–680 | HR suite $0.99–25 PEPM (ADVERTISED) or Word | Starter/Standard |

**Design consequence:** one product, four *presets* (the configurator pre-fills typical
seat/volume shapes per segment), one price engine. The presets do not change capability —
they change defaults and the words used.

---

## 4. Competitive landscape (checked 11 Oct 2026)

### 4.1 Nigerian, live-checked (ADVERTISED unless noted)

| Product | Price (as advertised) | Model | What it actually is | DocOga relation |
|---|---|---|---|---|
| **Dwellrs** (dwellrs.com) | **₦10,000/mo** Starter (≤5 units); **₦30,000/mo** Pro (≤50 units); Enterprise custom | Per-portfolio, monthly | Full PM suite: rent collection (card/USSD/OPay/transfer/direct debit), receipts, maintenance, quit notices, tenant app; 90-day Pro trial | The **ceiling anchor** — DocOga does a subset (the document layer) and must price under it at equal units |
| **Rentyx** (rentyx.org) | **₦80,000/mo** (≤10 units, 1 team member); **₦250,000/mo** (≤50 units, 3 members); **₦850,000/mo** (≤250 units, unlimited members); +0.75% platform fee on collected rent (cap ₦25k/payment) | Per-portfolio + seats, monthly | PM suite, Flutterwave-powered, "AI copilot" beta; 14-day trial, no contracts | The **upper anchor** for established managers. Note their explicit **seats-in-price** model (1/3/unlimited members) — validates "per team" language |
| **MyTenant** (mytenant.ng) | **Free basic**; pay-as-you-go SMS/ID-verification | Freemium | Onboarding, rent collection, e-sign leases, maintenance; claims "₦6.4T Nigerian rental market" (marketing figure, UNVERIFIED) | **Crowds the low end for free.** DocOga cannot win on feature count; wins on document correctness/branding and zero-suite migration |
| **RentPro** (via Taiwo Salam & Co. comparison) | **₦5,000+/mo** | Monthly | PM-lite (no mobile app, no branding per their own table) | Low-end anchor; their table also lists per-unit pricing **₦100–₦500/unit/mo** and monthly **₦3k–30k+** as market ranges |
| **Our Property NG / Spleet / Fibre** | Free / subscription / paid-only (same comparison table) | Various | PM tools with/without mobile | Context only |
| **Wonder.legal** | "Free basic; pay for customisations" (crm.africa comparison, 2025) — **exact prices UNVERIFIED** | Per-document | Guided-Q&A tenancy templates, editable Word/PDF | The **per-document self-serve** anchor (pre-dates DocOga's plan per `docs/BUSINESS_PLAN.md`) |
| **LawDepot NG** | **₦8,500** per single document (residential tenancy) | Per-document, one-off | International document generator, NGN-priced | Per-document anchor for a *single* agreement |
| **Lawyers (routine tenancy drafting)** | **10% of one year's rent** (LPRO 2023 guideline); Lagos practice 10% of 2 yrs; renewals **50–75%** of original fee; flat ₦20k–80k in practice | Per-event | Drafting + review | The **economic anchor**: the bill DocOga compresses for routine cases |

### 4.2 International per-seat anchors (for "what a seat costs" psychology, cited)

| Product | Price | Model |
|---|---|---|
| DocuSign | **$10** Personal (1 user, 5 envelopes/mo); **$25** Standard; **$40** Business Pro (per user/mo, annual billing) | Per-seat, envelope-capped |
| PandaDoc | **$19** Starter; **$49** Business (per user/mo, annual); $35/$65 monthly | Per-seat |
| Buildium | from **$58/mo** (Softwaresuggest listing) | Per-portfolio |
| AppFolio | from **$250/mo** (Softwaresuggest listing) | Per-portfolio |
| Rent Manager | from **$1/unit/mo**, unlimited users | Per-unit |
| HR SaaS (global) | **$5–30 PEPM** (UKG/Compono/Guru/SHRM-cited guides); small orgs $50–750/mo | Per-employee |
| HR SaaS (Nigeria) | **$6–8 PEPM** (Talstack, ADVERTISED); **$0.99/user/mo** entry (hrpayhub, ADVERTISED) | Per-employee |

**Read:** "per user per month" is the global seat psychology ($10–49/u/mo ≈ ₦15.5k–77.5k
at ₦1,550/$ — **FX UNVERIFIED**). The Nigerian market is 5–20× below that in naira terms.
DocOga's seat price must live between "12 retail passes" (₦24k/yr) and "1/10 of a PM
suite" — the §6 bands do exactly that.

### 4.3 Positioning conclusions

1. **Do not fight the suites on features.** Dwellrs/Rentyx/MyTenant own rent collection,
   maintenance, tenant portals. DocOga owns *the paper that goes out the door* — correct,
   state-law-sourced, branded, infinite. The suites' own advertised feature lists treat
   documents as a checkbox.
2. **Price under the suites, above the retail pass.** Per-portfolio equivalence: a 10-unit
   Dwellrs Starter is ₦120k/yr for *suite* functionality; DocOga Standard at ₦240k/yr for
   *8 seats of unlimited document work* is only defensible against **document spend**, not
   against Dwellrs — §6 shows the arithmetic against document spend.
3. **The per-document bill is the wedge** — it's the only cost every segment already pays
   and recognises (agency/legal fees, per-doc templates, lawyer drafting).
4. **MyTenant's free basic** means the *smallest* teams (1 unit, 1 person) are a retail
   pass market, not a Business market. Business starts where **branding + seats + annual
   invoice** matter — i.e., 2+ humans or a firm name on the paper.

---

## 5. Demand arithmetic (document volume models)

Nigerian rental mechanics that drive document frequency (all cited):

- **Advance rent:** Lagos Tenancy Law 2011 **s.4 caps residential advance at 1 year**;
  2-year advance remains the widespread practice and is "widely ignored" enforcement
  (LegalDoc 2026; Daily Trust 2026; Ownkey 2026). → Tenancies are **1–2 year events**:
  agreement + receipts cluster at move-in and renewal, not monthly.
- **Fee stack per tenancy event:** agency **10%** (LASRERA-capped in Lagos; 5–15%
  elsewhere) + legal/agreement **5–10%** (₦20k–80k flat in practice) + caution **1–2
  months / 10–20%** + rent receipt. On ₦1m/yr rent: **~₦200k of fees** (LandsOfNigeria
  worked example, 2026); on ₦2m/yr: **~₦500k** (Cabans worked example: ₦2.52m all-in).
- **Receipt right:** tenants are entitled to a receipt for *every* payment (Lagos law
  s.13-era provisions; DeyWithMe/Cabans 2026) → receipt volume is as large as payment
  events, i.e., every rent payment, every fee.
- **Renewals:** renewal agreements at **50–75%** of the original drafting fee (naijaproperty
  2026) → renewals are cheap-but-paid events, and they recur every 1–2 years per unit.
- **Short-lets** (Lagos ₦281bn/2025, Edala via Guardian 2026) are a different,
  per-night document shape (billing statements, not tenancy) — **out of scope for v1**
  (no sourced demand from this dossier; flag only).

### 5.1 Volume model (HYPOTHESIS — planning inputs, to be replaced by discovery)

| Case | Assumptions (HYP.) | Docs/yr |
|---|---|---|
| Agent, 20 lettings, ₦1.5m avg rent | 20 new + ~20 renewals; each: agreement + 2–3 receipts + occasional notice | **100–160** |
| Manager, 50 units, 30% turnover, annual advance | 15 new + 35 renewals; 50 rent receipts; 10 notices/demands | **~135–170** (monthly-collection case: **~700**) |
| Landlord, 10 units, 1-yr tenancies | 6–10 events × 3–4 docs + 10 receipts | **~40–50** |
| HR, 50 staff, in-house payslips | 600 payslips + 10–15 contracts + a few letters | **~630** |
| HR, 10 staff | 120 payslips + 3–5 contracts | **~130** |

**Metering consequence:** volume bands must be **per-month, not per-year** (annual-advance
rentals spike at renewal season; payslips are flat monthly). Proposed bands: 100 / 300 /
1,000 docs/month with soft-cap behaviour (§7.4). A 50-staff HR team (≈50/mo payslips +
spikes) fits Standard (300/mo) with headroom; a monthly-collection 50-unit manager
(≈55/mo + spikes to 150 in renewal months) fits Standard–Growth boundary — **the
configurator, not the salesperson, must show them which.**

---

## 6. Pricing: "Custom · Annual · Per Team" — the design

### 6.1 "Custom" that is automated

**Principle:** custom = *computed*, not *conversed*. The configurator publishes the
formula; the number is the product of the buyer's own inputs.

Inputs (segment preset → pre-filled):
1. **Seats** (number of named team members)
2. **Document volume band** (docs/month: 100 / 300 / 1,000 / more)
3. **Brands** (1 firm name + logo; +1 per additional brand at Growth)
4. **Extras** (none in v1 — the list exists so adding e.g. API access later doesn't change the page)

Output: **instant annual price** = included-band base price, or, above the published
tiers, the **custom formula**:

```
Annual price = (included base for the top published band)
             + (extra seats × per-seat annual unit price)
             + (extra volume blocks × per-block annual unit price)
```

**Proposed unit prices (PROPOSED — config, not code, until validated):**
- Per additional seat: **₦48,000/yr** (₦4,000/mo — between "a retail pass ×12 = ₦24k" and
  "1/5 of a Dwellrs seat-equivalent month")
- Per additional 100 docs/mo block: **₦18,000/yr** (₦1,500/mo)
- Minimum published entry: **₦96,000/yr** (Starter, 3 seats/100 docs-mo)

Every figure above the entry tier is a **PROPOSED** number. The anchors that bound them
are cited; the exact values are what discovery/usage should move. **Nothing in this section
is a validated price.**

### 6.2 The four tiers (PROPOSED bands, all annual, NGN, VAT shown at invoice)

| | **Starter** | **Standard** | **Growth** | **Custom** |
|---|---|---|---|---|
| Annual price | **₦96,000** | **₦240,000** | **₦480,000** | computed (§6.1), floor ₦480,000 |
| Seats | 3 | 8 | 20 | 20 + ₦48k/seat |
| Document volume | 100/mo | 300/mo | 1,000/mo | +₦18k per 100/mo |
| Brands (name + logo) | 1 | 1 | 2 | 2 + ₦48k/brand |
| Everything in Oga Pass | ✅ | ✅ | ✅ | ✅ |
| Firm name + logo on every document | ✅ | ✅ | ✅ | ✅ |
| Seat management (add/remove by email) | ✅ | ✅ | ✅ | ✅ |
| Annual VAT-inclusive invoice (PDF, emailed) | ✅ | ✅ | ✅ | ✅ |
| Pay by card / transfer (auto-confirmed) / USSD | ✅ | ✅ | ✅ | ✅ |
| Support | Email, 1-working-day target | same | same | same (+ named contact, *optional, owner decision* §11) |

**Seat arithmetic vs retail (anti-arbitrage, stated honestly):** 3 seats cost
₦96,000/yr = 4× the price of three 12-month retail passes (₦72,000). The premium buys:
(1) the right to *share* a licence across named people (a retail pass is non-transferable
per `site/terms.html` — sharing it is already a terms violation), (2) firm branding,
(3) seat offboarding, (4) an invoice for books, (5) the annual commitment. If discovery
shows teams would just buy 3 passes and share, the card's team value is not real and the
price must fall — this is a discovery question, stated here so it is not forgotten.

### 6.3 Why these anchors (every number cited or tagged)

- **Floor (cost side):** ₦0 infra (static + Worker free tier + Brevo free 300/day +
  R2-free/logo-data-URI), Flutterwave 2.0% local (cited) → marginal cost per team ≈
  payment fees only. Floor is ~₦2k/yr. The floor is not what prices the product; the
  *job* prices it.
- **Job anchor (property):** one routine tenancy event's document-adjacent bill is
  **₦200k–₦550k** on ₦1m–2m rents (§3.1/§3.3, cited). A Standard team (₦240k/yr) must be
  seen as replacing *several* events' worth, not as "software".
- **Job anchor (HR):** one HR SaaS seat-year at $6–8 PEPM ≈ ₦86k–114k (FX UNVERIFIED);
  a Starter/Standard at ₦96k–240k/yr for the whole *document layer* of a 10–50 staff
  firm is competitive with a *fraction* of a suite year.
- **Ceiling (suite side):** Dwellrs 50-unit Pro = ₦360k/yr **with rent collection**
  (ADVERTISED) — DocOga Growth at ₦480k/yr exceeds it, but Growth buys 20 seats ×
  1,000 docs/mo of *document* throughput under 2 brands; the comparison only holds for
  the document layer. The configurator copy must make that boundary explicit to avoid
  a lost comparison.
- **Retail-side psychology:** the public ₦2,000 pass cannot be hidden (groundwork rule,
  carried forward) — the tiers' "everything in Oga Pass" line keeps it visible as the
  base, and the card must state per-seat equivalence plainly.

### 6.4 Billing rules (automated, no human)

- **Annual, NGN only** (USD stays behind the separate diaspora gate — groundwork §11).
- **VAT 7.5%** shown line-item on the invoice (the site's invoice tool already computes
  7.5% — consistency with our own published convention).
- **Payment methods:** Flutterwave card, transfer-to-virtual-account (auto-confirmed by
  webhook), USSD/POS. "Bank transfer" is *kept* as the advertised method (card P3) but
  now with automatic confirmation — the promise becomes stronger, not weaker.
- **Refund window (PROPOSED, owner decision §11):** 14 days full refund, no questions,
  then no refunds on the document licence (consumables like passes stay non-refundable).
- **Renewal pricing:** price at renewal = price at purchase (no silent increases);
  increases require 60-day email notice with a lock-in option for the renewal year.
- **Mid-year seat changes:** add = prorated invoice (extra seats × unit price × months
  left, rounded up, minimum 1 month); remove = effective at next renewal (removed seats
  keep access until year-end — no prorated refunds mid-year).
- **Volume overage:** soft — banner + email at 100% of band, 2× grace at 150%,
  upgrade invoice suggested; **no hard cut-off of in-progress documents in v1** (§7.4).

---

## 7. Automation architecture (the no-WhatsApp machine)

### 7.1 End-to-end customer journey (target: zero owner touches)

```
[site card: Business — "from ₦96,000/yr · set up your team in 2 minutes"]
        │  (replaces: wa.me quote link)
        ▼
CONFIGURATOR (static page /#business-setup)
  1. segment preset (agent / manager / landlord / HR) → pre-fills seats+volume
  2. seats, volume band, firm name, logo (optional now, required before clean docs)
  3. live price (published formula) + VAT line
  4. [Continue → create team]
        ▼
TEAM CREATION (worker)
  - contact email + firm details → team record (status: unpaid)
  - magic-link email (Brevo) → click → team signed in, no password
        ▼
CHECKOUT (Flutterwave)
  - card / USSD / POS  →  standard charge  →  webhook
  - OR "Pay by bank transfer" → per-invoice DYNAMIC VIRTUAL ACCOUNT
    (bank + account + exact amount + reference shown on screen and in email)
    → customer transfers from their bank → Flutterwave webhook
        ▼
WEBHOOK (existing /flw-webhook, extended)
  - signature verified (dual-sig, already live)
  - amount+ref matches invoice → team status: ACTIVE (expiry = +365 days)
  - idempotent (already built for retail)
        ▼
AUTOMATED ISSUANCE
  - email to owner: team live, seats, invoice PDF attached, "invite your team"
  - each invited seat: magic-link email → signs in → documents branded
        ▼
USE (any device)
  - team member signs in (magic link) → branding (name+logo) fetched from worker
  - generates any of the 10 tools; output carries firm name/logo, no DocOga banner
  - volume counted (per doc, per team, per month — KV counter)
        ▼
SEAT MANAGEMENT (owner portal)
  - invite by email / revoke by name (revoke = access removed same day)
        ▼
RENEWAL (cron — existing scheduled() handler)
  - T-90/T-30/T-7 days: email with renewal invoice + VA link (or auto-charge notice
    if card stored via Flutterwave payment plan — pre-charge email + self-serve
    unsubscribe, both native Flutterwave features)
  - expiry + 14-day grace: banner returns (documents keep a "expires" line), portal
    shows outstanding invoice; after grace: team → FREE (bannered) until paid —
    data (brand, seats, history) retained 90 days
        ▼
SUPPORT
  - email inbox (Brevo) + in-app FAQ + status page; owner answers email (optional
    internal WhatsApp relay). No customer WhatsApp step anywhere above.
```

**Owner-touch budget at steady state:** 0 per team for buy/issue/renew; ≤ 1 email reply
per team per quarter is the target (support). Anything more is a product bug to fix,
not a process to staff.

### 7.2 Components against the real stack (₦0 infra)

| # | Component | Where it lives | Build detail |
|---|---|---|---|
| C1 | **Team/Brand/Seat records** | KV (`docoga-kv`) | Keys: `team:{id}` (name, slug, status, expiry, plan, volume band, vat details), `team:{id}:seats` (list: email, name, role, status, invited_at), `team:{id}:usage:{yyyy-mm}` (int), `brand:{id}` (name, address, logo data-URI, footer text), `inv:{id}` (team, amount, vat, status, va_ref, flw_ref, paid_at), `inv:{id}:va` (bank, number, amount, expiry), `auth:{email}` (magic-link token hash, expiry) |
| C2 | **Magic-link auth** | Worker | `POST /business/login` (email → 10-min token emailed via Brevo) → `GET /business/login?token=…` (verify, set signed cookie `doco-team` = HMAC-signed team+role token). No passwords → zero reset tickets. Same cookie pattern extends retail (optional later) |
| C3 | **Configurator** | Static (`site/business.html` or `/#business`) | Pure client-side math from a published price table embedded in JS (QA-guarded like the pricing card — `qa.py` already gates pricing copy). Writes nothing until team creation |
| C4 | **Team creation + portal API** | Worker | `POST /business/teams` (creates unpaid team, sends magic link), `GET /business/team` (owner: seats, usage, invoices, brand), `POST /business/team/seats` (invite/revoke), `PUT /business/team/brand` (name/logo), `GET /business/invoice/:id` (PDF) |
| C5 | **Invoicing + virtual account** | Worker + Flutterwave API | On "pay": create invoice object → Flutterwave **dynamic VA** (v3 `charges?type=bank_transfer` or v4 payment-method + `next_action: requires_bank_transfer`) → show bank/account/amount/reference → webhook `charge.completed` (`BANK_TRANSFER_TRANSACTION`, amount + narration matched to invoice) → `inv:{id}.status=paid` → activate. **Open check before launch:** NGN dynamic-VA expiry semantics (GHS sample shows 1h expiry; NGN sample shows `expiry_date: "N/A"` for static) — if dynamic VAs expire fast, fallback = **static VA per team** + exact-amount matching (webhook carries amount, so auto-match still works; a 10-minute window + team-slug narration reduces collisions) |
| C6 | **Card/USSD checkout** | Worker + Flutterwave | Standard hosted checkout (same path as the retail pass — already proven); for card customers, optionally enrol the stored method in a **payment plan** (annual interval) for auto-renewal — native Flutterwave recurring, with their pre-charge email + unsubscribe (no custom code) |
| C7 | **Branded rendering** | `site/index.html` JS | When signed in as team member: fetch brand from C4 → render header (firm name + logo image) in place of DocOga banner across all 10 renderers. **Logo storage v1: base64 data-URI in KV brand record, 25KB cap, PNG/JPG/SVG validated client-side** — zero storage infra. (R2 10GB-free is the v2 upgrade path if teams bring large logos; not needed in v1) |
| C8 | **Volume metering** | Worker + site JS | On each branded render: `kv.incr(team:{id}:usage:{yyyy-mm})` (rate-limited, non-blocking — render must not wait on network in v1; counter is best-effort, stated honestly). Soft-cap behaviour per §6.4. **Honest limit:** generation is browser-side (the retail pass has the same property) — the meter and the branding fetch are the enforcement points, not a cryptographic gate. A server-side render endpoint (v2) would be the hard gate; it changes the product and is out of v1 scope |
| C9 | **Renewal cron** | Worker `scheduled()` (exists, 07:00 daily) | Sweep teams: T-90/30/7 → email (invoice PDF + VA link or auto-charge notice); expiry → grace banner state; grace-end → FREE downgrade + retention timer; auto-charge failures → retry ×3 then email |
| C10 | **Invoices (PDF)** | Worker | Server-rendered simple HTML→PDF (or static-template client-render at checkout — decide at build; server-render keeps the invoice authoritative). VAT line, firm details, payment ref, 12-month download window from portal |
| C11 | **Support surface** | Brevo + static | Dedicated `business@docoga.com.ng` (Brevo, already authenticated 10 Oct), auto-reply with FAQ + status, canned responses in the repo (`docs/support/`) the owner copies from. FAQ page in the portal. **No WhatsApp in the loop** |

**Deploy:** everything ships through the existing automated deploy path
(`deploy-site-now.yml` for the site, `wrangler deploy --config wrangler.toml` for the
worker) — no new infra, no new paid service, cache-purge step already permanent.

### 7.3 Data flow and what the server stores (NDPR-relevant, must be in the privacy update)

| Data | Stored where | Why | Retention |
|---|---|---|---|
| Firm name, VAT/billing details, brand logo | KV | licence + rendering | Life of team + 90 days |
| Seat emails + names | KV | licensing/offboarding | Life of team + 90 days |
| Payment: amount, status, flw_ref, VA ref, method | KV | billing (cardholder data stays at Flutterwave — we never see PANs) | Life of team + 24 months (books) |
| Magic-link tokens (hashed) | KV | auth | 10 min |
| **Document content** | **Browser only** (unchanged from retail design) | — | not stored |

The "data stays on your device" line stays true for document content; it is **not** true
for licensing/billing/brand data — the privacy policy must say exactly that (groundwork
P0 flag, carried forward as a launch gate).

### 7.4 Edge cases (decided now, so builds don't improvise)

| Case | Behaviour |
|---|---|
| Transfer of wrong amount to the VA | Webhook amount ≠ invoice → **no activation**; email to customer with the correct amount + a fresh VA (old one voided). No human reconciliation in the common case |
| Two transfers, one correct | Idempotent activation on the correct one; the extra = credit note email (owner decides refund path — §11) |
| Duplicate webhook | Already idempotent (retail) |
| VA expires before transfer (if dynamic-VA expiry applies) | Show "link expired — get a new one" button; re-issue on click, no email needed |
| Customer pays but team email bounces | Retry ×3 over 24h → portal shows "payment received, activate with the email on file or contact business@ (email only)" — the *one* residual human step, by email, not WhatsApp |
| Seat added for a leaver | Owner revokes in portal; access dies at next magic-link (tokens are per-team; revoked seats fail auth immediately) |
| Logo too big / wrong format | Client-side validation before upload (≤25KB, PNG/JPG/SVG); server re-validates |
| Team exceeds volume band | Soft: banner + email at 100%; 150% grace; then suggested upgrade invoice. **Never** interrupt a half-filled form |
| Renewal auto-charge fails (card) | Retry ×3 (3/1/0 days), then fall back to invoice + VA email; grace still applies |
| Refund request in window | Owner processes in Flutterwave dashboard (manual, owner-side only); status flips on webhook |
| Team wants API/bulk/export (v2 ask) | Portal "request" → email (this is where the *optional* named-human tier answer goes — §11) |

### 7.5 What stays on WhatsApp (and what doesn't)

- **Consumer retail (Oga Pass):** unchanged — WhatsApp support stays as an optional
  convenience (the card's "WhatsApp us and a human sorts it out" line stays *there*).
- **Business:** WhatsApp is **never required** and never the CTA. It may remain an
  *optional* channel if the owner adds it to their own inbox relay — but the product
  must be completable, and must be advertised, without it.

---

## 8. Correcting the public promises (launch gate)

**Old card (live today):** see §2.1. **New card (exact copy, ready to ship with §7):**

> **Business** — **from ₦96,000/year** — *annual, per team*
> *For estate agents, property managers, landlords & HR teams*
> - Everything in Oga Pass, for your whole team — **no sharing personal codes**
> - **Your firm's name and logo** on every document instead of ours
> - **Team seats** — invite and remove people by email, access ends the same day
> - **One annual invoice with VAT** (PDF in your inbox, kept 12 months)
> - Pay by **card, bank transfer (auto-confirmed) or USSD** — or pay quarterly by card
> - **Email support** — business@docoga.com.ng, 1-working-day target
>
> [Set up my team — 2 minutes →] *(→ /#business-setup)*
> *Your team is live the moment payment confirms — no waiting, no message needed.*

Removed promises: "named human on WhatsApp who knows your account" (replaced by the
email SLA), "quote within one working day" (replaced by the instant configurator).
Kept and *strengthened*: "invoice and bank transfer" (now auto-confirmed).
**QA guard:** extend the existing pricing-card DOM assertions (3 tiers, copy, wiring)
to assert the new card's strings and that no `wa.me` link appears in the Business card —
the suite already fails on stale pricing copy, so this is one new test block.

**Terms/privacy (launch gates from the groundwork, unchanged):**
- Terms: add team licence definition (seats, named members, offboarding, non-transferable
  brand licence, annual period, renewal price notice, refund window).
- Privacy: add the §7.3 data table (licensing/billing/brand data stored; document
  content not stored; processor = Flutterwave for payment, Brevo for email; retention).
- No claim of "no data ever leaves your device" beyond document content (groundwork rule).

---

## 9. Unit economics (honest arithmetic, PROPOSED prices)

| Line | Value | Basis |
|---|---|---|
| Marginal cost/team/yr | **~₦1,920–4,800** (Starter→Growth at 2.0% Flutterwave local; 4.8% for any international card) | cited fee schedule; ₦0 hosting (CF static + Worker free tier), Brevo free tier 300 emails/day (well inside per-team volume), no paid APIs |
| Refund exposure | ≤ 14-day window → negligible at low volume; track as a line, not a guess | §6.4 |
| Owner time (steady state) | Target **< 2 min/team/month** (email support average) — the actual cost centre; measure from day 1 of live teams | mandate autonomy rule |
| ARPU (PROPOSED) | Starter ₦96k · Standard ₦240k · Growth ₦480k · Custom ₦480k+ | §6.2 |
| CAC | Sales-conversation-driven (no ad spend): owner/agent discovery time per grounded groundwork; the *product* costs nothing to acquire (SEO surface already exists — 56/60 pages carry a pay path) | REVENUE.md §4 |
| Scenario (PROPOSED prices, HYPOTHESIS adoption): 3 months | 20 teams @ mix ~₦200k ARPU = **₦4.0m/yr run-rate**, ~₦3.9m net of fees | arithmetic only |
| Scenario: 12 months | 100 teams @ ~₦220k = **₦22m/yr run-rate** | arithmetic only — requires ~8 new teams/month sustained; no sourced demand figure supports either scenario (Rule Zero: both are arithmetic, not forecasts) |
| vs the ₦1bn/month mandate | B2B is a **share**, not the whole: even 1,000 teams @ ₦240k = ₦2.4m/month. The diaspora USD path (REVENUE.md Path A) remains the other lever; this dossier does not re-derive it | REVENUE.md §3 |

**The honest line:** at PROPOSED prices, Business is a **₦-millions-per-year** business,
not a billions one — and that is the *point* of the tier: fewer customers, bigger
cheques, stickier, no ad spend (REVENUE.md Path B, unchanged), and every naira is
nearly all margin because the infra is ₦0.

---

## 10. Build sequence and gates

Sequencing on the "least blocked" rule (mandate). Every phase ships behind the existing
QA gate (`qa.py` + DOM suite + `pre_push_verify.sh` + CI).

| Phase | Content | Exit gate |
|---|---|---|
| **0 — Stop the leak** (hours) | Ship §8 card correction (even before the backend exists — the card must not promise un-built service); publish a "Business: launching — reserve" state or take the card down; capability sheet honest version | QA green; no card promises un-fulfilled |
| **1 — Brand + team core** (build C1, C2, C4, C7) | Team records, magic-link auth, branded rendering (name + logo) for one manually-created team (owner creates it in KV by hand) | Synthetic test: owner + 1 seat, branded PDFs across all 10 tools, revoke works; DOM suite extended |
| **2 — Money path** (C3, C5, C6, C10) | Configurator, team creation, Flutterwave checkout (card + dynamic VA transfer), webhook activation, invoice PDF | **End-to-end with a real small payment** (the established rehearsal pattern: small real amount, logged, PRICE unchanged for retail); both payment methods proven; wrong-amount transfer case proven |
| **3 — Self-serve surface** (C4 full, C11) | Owner portal (seats, brand, invoices), support email + FAQ + auto-reply | 2 friendly real teams (owner's own businesses/contacts, *with permission* per groundwork) complete buy→use with zero owner touches |
| **4 — Autonomy** (C8, C9) | Volume metering + soft caps, renewal cron (90/30/7), grace/downgrade, auto-renewal enrolment | Simulated renewal cycle (test team with short expiry); overage emails; downgrade data-retention proven |
| **5 — Publish** | Business card flips from "launching" to live with prices; state pages' pay-path bar keeps pointing at retail (Business is card-level CTA only, to avoid confusing consumers) | Owner sign-off; first real external team (any segment) |

**Discovery (parallel, per the 10 Oct groundwork):** runs alongside Phases 0–2; any
interview finding that moves a §6 number = config change + note in the decision log,
no rebuild. The price bands are explicitly **re-pricing candidates**, not commitments.

**Explicit non-goals (v1):** e-signature (ET Act 2011 + Evidence Act 2011 s.100–108 make
electronic signatures valid in Nigeria — cited — but tenancy practice still runs on
signed/stamped paper; e-sign is a v2 feature with its own legal review), rent collection,
tenant portal, property records, short-let billing, USD pricing, API access, multi-
country law. The 10 Oct groundwork's rule stands: **do not secretly build a
property-management suite.**

---

## 11. Open questions for the owner (short, specific)

1. **Named human:** the old card promised one on WhatsApp. The new design gives an email
   SLA to all Business tiers. Do you want a *named* contact for Growth/Custom tiers
   anyway (email-only, or is WhatsApp fine as an optional second channel for just those
   tiers)? Recommendation: email-only for everyone; "named" only if you will actually
   answer it.
2. **Refund window:** 14 days full / then none (proposed) — accept or change?
3. **Published entry price:** "from ₦96,000/yr" on the card, or strictly "Custom —
   compute yours in 2 minutes" with no number? A number converts SMEs; pure "Custom"
   converts only the confident. Recommendation: publish the entry number.
4. **Entity & payment readiness (facts, not opinions — the groundwork flagged CAC as an
   open item for the transfer path):** (a) is the CAC business-name registration done?
   (b) is the Flutterwave account KYC-approved for **virtual accounts and invoices**
   (business settlement)? Both are hard prerequisites for Phase 2; if not, tell me which
   and I will sequence the owner-side steps (the 10 Oct Brevo enablement shows the
   owner-guided path works).
5. **Support capacity:** what is a realistic 1-working-day email target for how many
   Business teams (10? 50? 200?)? This sets the published SLA and the growth ceiling.
6. **Discovery in parallel:** permissioned interviews per the 10 Oct workbook — proceed
   (needs your relationship/channel choice), or ship self-serve first and let usage
   speak? Recommendation: proceed with *two* introductions max, while Phase 1–2 builds.
7. **Quarterly-by-card option** (§6.2 Growth line mentions "or pay quarterly by card" as
   a possible convenience): include in v1 or keep strictly annual? Recommendation:
   annual only in v1 (the owner's word is "annual"; quarterly adds refund/surface area).

---

## 12. Source register (accessed 11 Oct 2026 unless noted)

**Evidence tags:** OFFICIAL (regulator/body), ORG (organisation's own site — advertised,
not independently verified), REPORT (named research body), PRESS (newspaper), METHOD
(practitioner guidance), REPO (this repository), HYP/UNV (this document's hypothesis /
unverified).

1. NIESV national "List of Firms" — 1,496 registered firms. OFFICIAL. https://niesv.org.ng/registered_firms.php
2. NIESV Firms Directory — 1,433 listed, categories incl. "Property and Facility Management". OFFICIAL. http://firms.niesv.org.ng/niesva-zfirms.php
3. NIESV news: ~4,450 registered professionals ("another 98 approved"); separately "about 5,000 members". OFFICIAL (body's own statements). https://niesv.org.ng/blog_details.php
4. The Nation (2020): Lagos State — 50,000 estate agents/developers CAC-registered (excl. law firms). PRESS, **stale (2020)**, order-of-magnitude only. https://thenationonlineng.net/50000-estate-agents-registered/
5. Nigeria Property Centre agents directory — 16,946 self-listed agents (Lagos areas listed). ORG live count, UNVERIFIED true headcount. https://nigeriapropertycentre.com/agents
6. PAC Research reports (via nigeriahousingmarket.com + ThisDay, May 2026): national housing deficit >28m units; Lagos stock ~1.49m vs demand ~4.69m; Lagos +475k residents/yr; VI 3-bed up to ₦18m/yr rent. REPORT. https://www.nigeriahousingmarket.com/news/nigeria-lagos-housing-deficit-investment-opportunities ; https://www.thisdaylive.com/2026-05-20/pac-research-unveils-reports-on-nigeria-lagos-housing-market/
7. nigeriahousingmarket.com (Jan 2026): 2025 GDP rebase — real estate >₦41tn, 13.36% GDP share; rental yields 6–10%. REPORT lookback. https://www.nigeriahousingmarket.com/market-forecasts/nigeria-real-estate-2025-predictions-lookback-gdp-rebasing
8. Edala Homes report (via Guardian, Mar 2026): Lagos short-let ₦281.03bn revenue 2025 (5,806 listings analysed). REPORT. https://guardian.ng/property/c25-property/lagos-short-let-market-generates-n281-billion-in-2025/
9. Dwellrs (dwellrs.com, FAQ JSON-LD read in full): ₦10,000/mo Starter ≤5 units; ₦30,000/mo Pro ≤50 units; Enterprise custom; 90-day Pro trial; naira rent collection incl. USSD/OPay/direct debit; caution-fee/stamp-duty handling. ORG/ADVERTISED. https://dwellrs.com/
10. Rentyx (rentyx.org, pricing read in full): ₦80,000/mo ≤10 units/1 member; ₦250,000/mo ≤50/3; ₦850,000/mo ≤250/unlimited; 0.75% platform fee on collected rent (cap ₦25k/payment); 14-day trial. ORG/ADVERTISED. https://www.rentyx.org/
11. MyTenant (mytenant.ng): free basic, pay-as-you-go SMS/IDV; "₦6.4T rental market" marketing claim (UNVERIFIED). ORG/ADVERTISED. https://www.mytenant.ng/
12. Taiwo Salam & Co. (comparison table): RentPro ₦5,000+/mo; Our Property NG free; Spleet/Fibre; market ranges ₦3,000–30,000+/mo monthly, ₦100–500/unit/mo. ORG/ADVERTISED. https://taiwosalamandco.com/how-much-does-property-management-software-cost/
13. Softwaresuggest (Nigeria property-management listing): Buildium from $58/mo; AppFolio from $250/mo; Rent Manager $1/unit/mo; Simplifyem $10/mo. ORG (aggregator) — starting-price claims. https://www.softwaresuggest.com/property-management-software/nigeria
14. Wonder.legal via crm.africa comparison (Nov 2025): "Free basic; pay for customisations"; exact prices UNVERIFIED. ORG (secondhand). https://crm.africa/rental-lease-agreement-example/
15. LawDepot Nigeria (residential tenancy): ₦8,500 single-document license. ORG/ADVERTISED. https://www.lawdepot.com/ng/real-estate/residential-tenancy-agreement/
16. naijaproperty.com (May 2026): lawyer tenancy fees — 10% of one year's rent (LPRO 2023 guideline); Lagos practice 10% of 2 years; renewals 50–75% of original; ₦1.5m rent → ₦150k–300k. METHOD/ORG. https://naijaproperty.com/blog/finance/cost-of-hiring-a-property-lawyer-in-nigeria-full-breakdown-with-real-numbers
17. Cabans (Sep 2026): Lagos fee stack worked example (₦2m rent: 10% agency + 7.5% agreement + 1-month caution ≈ ₦2.52m all-in 1-yr advance); receipt entitlements; agency fees calculated on one year's rent. METHOD. https://cabans.ng/blog/guides/agency-and-agreement-fees-lagos
18. DeyWithMe (Apr 2026): fee reference table — agency 10% (Lagos-capped), legal 5–10%, caution 10–20% refundable, receipt rights, illegal-fee list. METHOD. https://deywithme.com/essentials/apartment-hunting-in-lagos/
19. Lands Of Nigeria (Aug 2026): ₦1m rent example — ~₦200k fair fees total (10% + 10%); LASRERA 10% cap. METHOD. https://landsofnigeria.com/how-much-should-i-pay-for-agency-fees-in-nigeria/
20. Mumtaz (Feb 2026): property management fee 5–10% of rent; rental agency 10% (5–15%); sales 5–10%. METHOD. https://mumtaz.ng/2026-02-27/real-estate-agent-fees-in-nigeria/
21. Cabans estate-agent-fees guide (May 2026): letting agency 5–10%; agreement/legal ₦20k–80k; management 5–10% residential, 15–25% short-let. METHOD. https://cabans.ng/blog/guides/estate-agent-fees-nigeria
22. Ownkey (Jun 2026): caution-fee rules; Lagos Tenancy Law s.4 max 1-yr advance residential; caution 1–2 months common practice, no statutory cap. METHOD. https://ownkey.com/ng/blog/security-deposit-rules-nigeria
23. Daily Trust (Jul 2026): s.4(1) Lagos Tenancy Law — no excess of 6 months (monthly tenant) / 1 year (yearly tenant) advance; 2-yr practice common outside Lagos. PRESS/METHOD. https://dailytrust.com/is-it-legal-for-landlords-to-demand-2-yr-rent-from-new-tenants/
24. LegalDoc (Apr 2026): s.4 prohibition "widely ignored"; tenant rights incl. written agreement. METHOD. https://legaldoc.ng/articles/property-law/tenant-rights-in-nigeria
25. UKG HR cost guide (Jul 2026): $5–30 PEPM; small orgs $50–750/mo; first-year budgets 10–75% above subscription. ORG (vendor guide). https://www.ukg.com/learn/article-library/hr-leaders/hr-software-cost-guide-how-much-should-your-organization-budget
26. Compono HR pricing guide (May 2026): $5–20 PEPM core cloud platforms. ORG (vendor guide). https://www.compono.com/articles/hr-software-pricing-guide
27. GetGuru HR pricing (Oct 2025): $4–30 PEPM; avg $5–15. ORG (vendor guide). https://www.getguru.com/reference/hr-software-pricing
28. Talstack (Jun 2026): Nigerian HR reviews ~₦9k–13k/person/mo ($6–8); US platforms $15–25 PEPM ≈ ₦24k–40k. ORG/ADVERTISED. https://www.talstack.com/blog/best-performance-review-software-nigeria
29. hrpayhub.com/pricing (read in full): from $0.99/user/mo annual (₦4,999 noted), min 5 employees; tiers to $29/user (bookkeeping). ORG/ADVERTISED. https://hrpayhub.com/pricing
30. esign.ai comparisons (Jun–Aug 2026): DocuSign $10 Personal/$25 Standard/$40 Business Pro (annual billing, envelope caps); PandaDoc $19 Starter/$49 Business annual ($35/$65 monthly). ORG (vendor comparison). https://www.esign.ai/blog/pandadoc-pricing-small-business-esignglobal ; https://www.esign.ai/blog/pandadoc-vs-docusign-fees
31. SignEasy PandaDoc pricing (Jul 2026): same $19/$49 tiers confirmed, feature lists. ORG (vendor comparison). https://signeasy.com/blog/business/pandadoc-pricing
32. Flutterwave developer docs — NGN Virtual Accounts (v3): dynamic VA creation, webhook `charge.completed` / `BANK_TRANSFER_TRANSACTION` with amount/originator; static VA `expiry_date: "N/A"`. OFFICIAL (vendor API docs). https://developer.flutterwave.com/v3.0/docs/ngn-virtual-accounts
33. Flutterwave eng (dev.to, Nov 2025): virtual accounts — instant webhook, auto-confirm, no manual tracking; dynamic VA 1h expiry (GHS sample). ORG (vendor). https://dev.to/flutterwaveeng/understanding-virtual-accounts-with-flutterwave-4mnm
34. Flutterwave eng (dev.to, Feb 2026): v4 API — General Flow for subscriptions; static vs dynamic accounts ("use static if you plan to reuse… dynamic for one-off"); `next_action: requires_bank_transfer` for PWBT; webhook final-status. OFFICIAL/ORG (vendor). https://dev.to/flutterwaveeng/how-to-collect-payments-using-the-v4-apis-4lhp
35. Flutterwave support (recurring): payment plans (dashboard/link/API), customer charged at interval, pre-charge email with unsubscribe, self-serve cancel. ORG (vendor docs). https://flutterwave.com/tz/support/payments/how-recurring-payments-work ; https://flutterwave.com/ng/support/payments/create-a-subscription-payment-page
36. Flutterwave fees: 2.0% local NGN (effective 11 Apr 2025), 4.8% international — REPO-cited in `docs/REVENUE.md` §2 with original Flutterwave support links; consistent with the ₦2-on-₦100 rehearsal log. REPO+ORG.
37. Flutterwave EU site: "Invoices — create and issue professional invoices". ORG (vendor). https://flutterwave.com/eu/
38. SMEDAN/NBS (via The Guardian, Jan 2022): 39,654,385 MSMEs (Dec 2020); small+medium = 1,240,965 (3.1%); 96.7% of businesses; 46.31% of GDP. REPORT. https://guardian.ng/business-services/over-39-65m-msmes-operate-in-nigeria-says-report/
39. entrepreneurs.ng (Dec 2025): MSMEs ~96% of businesses, ~48% GDP (PwC); National MSME Policy size classes (small 10–49 staff, ₦5m–50m; medium 50–199, ₦50m–500m). REPORT/METHOD. https://entrepreneurs.ng/msmes-in-nigeria/
40. Nigerian Journal of Law (LASJURE) article: ET Act 2011 gives validity to online contracts, e-signatures and records; Evidence Act 2011 electronic evidence (ss.100–108; s.93(2) e-signature satisfies signature requirement). METHOD (legal commentary, not an opinion on DocOga). https://www.nigerianjournalsonline.com/index.php/LASJURE/article/download/2549/2475
41. Akintunde Esan (2015, historical context): Evidence Act 2011 recognition of electronic documents/signatures; e-sign not required where no statutory form mandate. METHOD (legal commentary). https://akintundeesan.blogspot.com/2015/09/formation-validity-and-enforcement-of.html
42. REPO: `docs/MANDATE.md`, `docs/REVENUE.md` (fee schedule, paths, arithmetic), `docs/BUSINESS_PLAN.md`, `docs/SESSION_CONTEXT.md` (sessions 25–26: Business card shipped unpriced; worker + site deployed), `docs/STATE_TENANCY_RESEARCH.md` (verified state tenancy law), `site/index.html` (live card copy, 10 tools, ANALYTICS/WORKER config), `worker/index.js` (endpoints, dual-sign webhook, cron, KV, PRICE_NGN), `logs/2026-09-19-first-real-payment-webhook.json` (real payment), `docs/B2B_OUTREACH_GROUNDWORK.md` + `B2B_DISCOVERY_WORKBOOK.md` (on `arena/47d148f1-docoga`, 10 Oct 2026 — capability inspection, consent rules, discovery method, economics without inventing a price).
43. Flutterwave GHS virtual-account docs (dynamic 1h expiry sample) — OFFICIAL (vendor), used only as the expiry-semantics caution: https://developer.flutterwave.com/docs/ghs-virtual-accounts

**What we could not verify (stated, not filled):** exact Wonder.legal prices; current
active paying-agent count (all counts are directory/press figures of varying age);
typical annual turnover rate of Nigerian rental tenancies (the 30% in §5.1 is HYPOTHESIS);
employment-contract drafting fee rates (none published found); Dwellrs/Rentyx/MyTenant
actual customer counts or performance (advertised only); Flutterwave NGN *dynamic* VA
expiry (the NGN doc sample shows `N/A` — must be confirmed in Phase 2 before launch);
the ₦1,550/$ exchange rate (carried as UNVERIFIED from REVENUE.md); Dwellrs' "90-day Pro
trial" and Rentyx' trial terms in practice (advertised).

---

## 13. Decision log (this dossier)

| Decision | Choice | Why |
|---|---|---|
| Price model | Custom = **configurator-computed**, published formula, four published bands + custom formula above | Owner fixed "Custom"; automation forbids human quotes; configurator keeps re-pricing a config change |
| Billing | Annual, NGN, VAT-inclusive invoice; 14-day refund (proposed) | Owner fixed "annual"; invoice = procurement requirement of all four segments |
| Unit | Team (organisation) + seats | Owner fixed "per team"; seats give offboarding/branding a concrete shape and an honest anti-arbitrage line vs retail passes |
| Payment | Card/USSD/POS + **virtual-account transfer with webhook auto-confirm** | "Invoice and bank transfer" stays true and becomes *stronger* (auto-confirmed); zero reconciliation humans |
| Auth | Magic links (no passwords) | Every password reset is a support ticket; the mandate is autonomy |
| Logo v1 | Base64 data-URI in KV brand record, 25KB cap | Zero new infra; R2 is a v2 path, not a v1 need |
| E-sign | **Out of v1** | ET Act 2011/Evidence Act 2011 make it legally viable, but tenancy practice runs on signed/stamped paper; e-sign needs its own legal review and support surface |
| WhatsApp | Removed from the Business path entirely; consumer tier unchanged | Owner instruction, 11 Oct 2026 |
| Discovery | Parallel, per 10 Oct groundwork, ≤2 introductions while Phases 1–2 build | Groundwork's evidence ladder stays the price-validation gate; the product ships self-serve regardless |
| Suites | Not built, not imitated | Groundwork rule: the buyer's collections/records pain is not DocOga's job; the document layer is |
| **Phase 0 execution (11 Oct 2026)** | Card → honest COMING SOON + self-serve waitlist; WhatsApp CTA removed; **deploy deliberately not marked** | The card must not promise un-built service; the waitlist gives the interim state the no-WhatsApp shape. **Deploy-blocker found while shipping Phase 0:** the worker deployed in production (published 10 Oct from the `arena/47d148f1-docoga` lineage) is AHEAD of `main`'s `worker/index.js` — 91 lines `main` lacks, incl. `POST /resend-email` (sender-gated pass-email recovery, live), hardened `sendMail` error handling, and 10-tool pass-email copy (`main` still says "all 9 tools"). Deploying `main`-based worker code before porting that work would roll the production worker back. **Order is fixed: port the production worker (and its test suite) into main first, then deploy worker, then site.** |
| **Production worker port (11 Oct 2026)** | Adopted `worker/index.js` + `wrangler.toml` (comment-only delta) + `workertest.mjs` **verbatim** from the deployed lineage (`arena/47d148f1-docoga` @ `49ea7d9`), re-applied the Phase 0 waitlist on top — the ONLY deltas are +51 lines (handler + route + header doc) and +25 lines (7 unit tests). Verified branch tip == deployed worker (no commit touched `worker/` after `2cbda5f`, 9 Oct; the 10-10 `[deploy-pass]` commits only triggered publishes). Port brings: `/resend-email` (live recovery endpoint), hardened `sendMail`, 10-tool pass-email copy. Re-baselined suites: worker 47/47, DOM 99/99, qa.py 0 errors. Deploy is now a strict forward superset — awaits owner go on `[deploy-pass]`. | A deploy from the ported branch can no longer roll the production worker back; the Business build sequence can proceed in the fixed order. |
