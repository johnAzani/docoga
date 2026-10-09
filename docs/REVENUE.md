# DocOga — Revenue Plan

Owner: John Azani (johnAzani). Operator: Arena agent, under `docs/MANDATE.md`.

**Status: this is the operating document for revenue.** Baseline 8 Oct 2026; payment and sequencing state updated 9 Oct 2026.

Rule Zero applies to strategy and pricing: every number below is *measured from this
repo* or *cited to a source*. Where I could not verify something, it is marked
**UNVERIFIED** rather than filled in.

---

## 1. What already works — measured, not assumed

This is the most important section. The app is **not** unmonetised: the Worker,
checkout, webhook and code-issuance paths exist, and local unit tests cover them.
However, the historical ₦100 charge was below the Worker’s ₦2,000 gate, so the
live payment-to-pass-and-email path still needs one qualifying purchase.

| Fact | Value | Source |
|---|---|---|
| Payment worker deployed | `https://docoga-pass.johnazani.workers.dev` | `site/index.html` (`WORKER_URL`) |
| Real payment settlement | `charge.completed`, **₦100 charged, ₦2 fee, status `successful`**, bank transfer, 19 Sep 2026 | `logs/2026-09-19-first-real-payment-webhook.json` |
| Payment link | `https://flutterwave.com/pay/ynznvgof2r21` | log `meta_data.__CheckoutInitAddress`, gated in `tools/qa.py:84` |
| Price | `PRICE_NGN = 2000` — Oga Pass, 30 days; the live site advertises 10 tools | `worker/index.js` (price) and `site/index.html` (tier copy) |
| Endpoints | `POST /issue`, `POST /flw-webhook`, `GET /verify`, `GET /activate` | `worker/index.js` |
| Fallbacks already coded | Flutterwave v4 OAuth + v3 verify; Paystack ("Path C — after CAC"); Selar→Zapier bridge | `worker/index.js` |
| Tools shipping | 10: agreement, notice, receipt, invoice, employment, caution, demand, payslip, warning, power of attorney | `site/index.html` (10 renderer types) |
| SEO surface | 48 state pages | `tools/gen_state_pages.py` |
| Analytics | GA property `G-GO8VZB3R28` | `site/index.html` (`ANALYTICS_ID`) |
| Support | WhatsApp `2349021852845` | `site/index.html` (`SUPPORT_WHATSAPP`) |

**Conclusion: distribution and pricing are the growth gaps, but the live
₦2,000 payment-to-pass path is not ready for its end-to-end proof yet.** The 19 Sep
log proves Flutterwave completed a real **₦100** payment; it does **not** prove code
issuance because the Worker requires `amount >= ₦2,000`. A signed ₦100 webhook is
intentionally acknowledged with HTTP 200 and ignored. Although the owner reported
`FLW_SECRET_KEY`, `FLW_WEBHOOK_HASH`, and `BREVO_API_KEY` set, deploy run
`37890401771` exposed dashboard variable values and Wrangler's default deployment
may have removed them. The PR comment was redacted, but the run log could not be
deleted through the Arena integration. Treat those credentials as compromised;
rotate and restore them as Cloudflare Worker Secrets before attempting a purchase.

---

## 2. Fees — verified

| Channel | Rate | Source |
|---|---|---|
| Flutterwave, Nigeria local (cards, transfer, USSD) | **2.0%** (1.4% transaction + 0.6% platform), effective 11 Apr 2025 | [1](https://flutterwave.com/ng/support/pricing/pricing-for-receiving-payment), [5](https://flutterwave.com/eu/support/pricing/fee-increase-for-local-ngn-payments) |
| Flutterwave, international cards | **4.8%** effective (3.8% + 1% to receive internationally) | [1](https://flutterwave.com/ng/support/pricing/pricing-for-receiving-payment), [4](https://brands.ng/flutterwave-review-before-you-open-a-flutterwave-account-read-this-first/) |
| USD settlement | Flutterwave can settle USD to a domiciliary account; 150+ currencies | [7](https://etestweb.com/blog/accept-dollar-payment-nigerian-website) |

Net per local Oga Pass: ₦2,000 − 2.0% = **₦1,960**.

*(The 19 Sep log shows ₦2 fee on ₦100 = 2.0%, consistent with the current rate.)*

---

## 3. The arithmetic on "billions monthly" — the honest answer

Target: **₦1,000,000,000 per month.**

At ₦2,000 gross / ₦1,960 net per pass:

> ₦1,000,000,000 ÷ ₦1,960 = **510,204 passes per month**
> ≈ **17,000 new paying customers every single day.**

**This is not reachable at ₦2,000.** It is not a traffic problem that more SEO
eventually solves — at that price the required volume exceeds the plausible size of
Nigeria's entire online subscription market. **UNVERIFIED:** I do not have a sourced
figure for Nigeria's paying online-subscriber base, so I am not going to invent one
to make the arithmetic look better.

Per the mandate ("be honest about the arithmetic and say when a target needs a
different model rather than more of the same"): **this target needs a different
model.** Not more pages. Not more of the same price.

Three changes make billions arithmetically reachable. They are not mutually exclusive.

### Path A — Diaspora, priced in USD  ← biggest revenue-per-customer lever

- Nigerians abroad: **"more than 15 million"** is the widely cited figure; Africa Check
  found the claim **contested**, with experts noting official remittance data only
  captures funds sent through banks, so the true number is incomplete
  [4](https://africacheck.org/fact-checks/reports/how-many-nigerians-abroad-and-how-much-cash-do-they-send-home).
  The **US has over 2 million Nigerian residents** [2](https://www.openpr.com/news/4308074/nigeria-remittance-market-surges-to-usd-23-billion-in-2025-as).
- Remittances to Nigeria: **$21.8bn in 2025** (CBN)
  [3](https://brandspurng.com/2026/05/19/nigerias-diaspora-remittances-hold-steady-at-21-8bn-in-2025-despite-global-economic-pressures/).
  A second source puts 2025 at $23bn [2](https://www.openpr.com/news/4308074/nigeria-remittance-market-surges-to-usd-23-billion-in-2025-as).
- **Why they buy:** a diaspora Nigerian constantly needs Nigerian documents — power of
  attorney, affidavit, tenancy, land/property, next-of-kin. Today they pay an agent or
  lawyer. They earn in dollars.

**Illustrative arithmetic only — $20 is not an adopted price.** At $20 per pass
(~₦31,000 at ₦1,550/$, **UNVERIFIED** exchange rate; confirm at launch):

> ₦1bn/month ÷ ₦31,000 ≈ **32,000 diaspora passes per month**
> ≈ **0.2% of a 15M diaspora.**

This is a sensitivity example, not a forecast or price recommendation. The 15×
revenue-per-customer comparison and 32,000-customer count depend on that
unvalidated assumption. Research the diaspora offer, international-payment
approval, settlement and current exchange rate before choosing a USD price.
It remains a different-volume model than 510,204 local passes.

### Path A is only real if we sell what the diaspora actually buys

Rule Zero check before pricing anything: **what document do they actually need?**

The sources are unusually consistent, and the answer is not a tenancy agreement:

- A Power of Attorney is *"by far the most common use among diaspora Nigerians"*
  [legaldoc.ng](https://legaldoc.ng/articles/family-law/power-of-attorney-in-nigeria-template-and-a-z-guide).
- It is the instrument a Nigerian lawyer needs in order to act for someone abroad —
  to file, appear, sign and receive evidence
  [Olamide Oyetayo Legal](https://olamideoyetayolegal.com/how-to-sue-someone-in-nigeria-while-living-abroad/).
- POA registration alone runs **₦50,000**
  [nigisservices.com](https://www.nigisservices.com/index.php/landfolio-4/10-power-of-attorney).
- The demand is driven by fear, which is a strong buyer emotion: the Guardian
  reported a UK-based Nigerian who sent money to build in Enugu and found the land
  *did not exist or had been resold*
  [Guardian](https://guardian.ng/property/how-diaspora-investments-are-reshaping-real-estate-market/).

**DocOga had zero mentions of "power of attorney" anywhere in the site.** The
most-wanted, highest-priced document in the target market was not in the product.

→ **Shipped 8 Oct 2026: Power of Attorney is now the 10th tool** (commit `9f41acd`),
with 8 tick-box powers and sourced legal warnings (s.22 Land Use Act; *Ojugbele v.
Olasoji* (1982) SC 71 — an unregistered registrable POA is inadmissible; stamp duty;
notarisation; Nigeria is not on the Hague Apostille Convention, so consular
legalisation not apostille).

**This is the product to put in front of the diaspora**, not the tenancy agreement.
The POA landing page is live (8 Oct); what remains is evidence-backed USD pricing
and confirmation that international collection/settlement is enabled.

### Path B — B2B / bulk / API

Estate agents, property managers, landlords' associations, HR platforms, co-working
operators, SMEs. The **Business tier is live and deliberately unpriced** (Custom,
annual, per team; WhatsApp quote). Do not invent or publish a price. Start with
outreach and discovery: document team size, document volume, current workflow,
procurement constraints, required support/integrations, and willingness to pay.
Set a quote only after evidence from real conversations.

No sourced count of addressable Nigerian businesses or validated monthly account
value is available, so there is no honest customer-count forecast yet. Once the
account value is measured, the target arithmetic is `₦1bn ÷ validated monthly
account value`; until then, do not turn a hypothetical price into a forecast.

### Path C — Local volume at ₦2,000

Keep it as the local entry product, and use it to validate real checkout-to-pass
conversion only after a qualifying ₦2,000 purchase succeeds end to end. The ₦100
September charge proves payment settlement, not pass issuance. Local volume can feed
A and B, but it is the funnel, not the destination.

---

## 4. Sequencing — next revenue actions

1. **Conversion surface.** ✅ **DONE 8 Oct 2026.** 48/59 pages carry a pay path
   (sticky bar + inline CTA → `https://docoga.com.ng/#pricing`); the POA page and
   Business tier are live.
2. **Recover the payment credentials before testing.** The Flutterwave webhook URL
   is saved, but deploy run `37890401771` exposed the dashboard values for
   `BREVO_API_KEY`, `FLW_SECRET_KEY`, and `FLW_WEBHOOK_HASH`; the deploy may also have
   removed those vars. Delete the run log in GitHub Actions if possible, revoke/rotate
   the Brevo key, create a genuine Flutterwave secret key, generate a fresh webhook
   hash, remove any stale plain-text vars, and save the new values as Cloudflare
   Worker **Secrets**. Do not take a payment until this is complete. The Arena session cannot delete the
   run log or write repo secrets.
3. **Verify the direct payment path.** After credential recovery, make one real
   successful **₦2,000** purchase and confirm webhook acceptance, pass email, and
   reference lookup. An authenticated ₦100 event is below `PRICE_NGN` and is silently
   acknowledged as `ignored`; it is not a valid pass test. Local mocks are not proof.
4. **B2B outreach first.** The Business tier is live, deliberately unpriced, and
   available by WhatsApp quote. Start discovery conversations; record buyer needs,
   team/document volume, procurement and willingness-to-pay evidence. Do not invent
   or publish a Business price.
5. **Diaspora USD pricing second.** The POA landing page is live. Research what
   diaspora buyers need and what they pay, confirm Flutterwave international-payment
   approval and settlement details, then recommend a USD price. The `$20` figure in
   §3 is an illustrative sensitivity case only, not a selected price.
6. **Measure the baseline in parallel.** The owner must read GA (`G-GO8VZB3R28`):
   sessions/month, top landing pages and current conversion rate. The Arena session
   cannot read GA; traffic data is essential for forecasting volume, though it does
   not block B2B discovery.

---

## 5. Open questions blocking the next step

Rule Zero: these are unknowns, not assumptions.

- **Traffic.** How many sessions/month, and what is the current free→paid conversion?
  Cannot be read from the repo. **Owner must check GA.**
- **Are the payment credentials restored safely, and does the webhook work at the
  paid threshold?** Run `37890401771` exposed remote dashboard vars, and the worker
  deploy may have removed them. The PR comment is redacted; run-log deletion is an
  owner action. Rotate/re-add them as Worker Secrets first. Only then can one real
  successful ₦2,000 purchase confirm webhook acceptance, code issuance and email.
- **Is the Flutterwave account approved for international payments?** Required for Path A
  [7](https://etestweb.com/blog/accept-dollar-payment-nigerian-website).
- **Is the ₦2,000 price tested?** No evidence of a conversion test at any other price.
  Path A partly answers this, but a local A/B (₦2,000 vs ₦3,500) is cheap to run once
  there is enough traffic to read.

---

## 6. Guardrails carried from the mandate

- Infra cost stays **₦0**.
- No deceptive SEO — the state pages are legal *information*, not legal advice, and say so.
- Rule Zero: no invented market numbers. Anything unverified is marked.
