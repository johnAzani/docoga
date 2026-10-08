# DocOga — Revenue Plan

Owner: John Azani (johnAzani). Operator: Arena agent, under `docs/MANDATE.md`.

**Status: this is the operating document for revenue.** First baseline 8 Oct 2026.

Rule Zero applies to strategy and pricing: every number below is *measured from this
repo* or *cited to a source*. Where I could not verify something, it is marked
**UNVERIFIED** rather than filled in.

---

## 1. What already works — measured, not assumed

This is the most important section. The app is **not** unmonetised. The money path
was built and tested before this session.

| Fact | Value | Source |
|---|---|---|
| Payment worker deployed | `https://docoga-pass.johnazani.workers.dev` | `site/index.html` (`WORKER_URL`) |
| Real money, end-to-end | `charge.completed`, **₦100 charged, ₦2 fee, status `successful`**, bank transfer, 19 Sep 2026 | `logs/2026-09-19-first-real-payment-webhook.json` |
| Payment link | `https://flutterwave.com/pay/ynznvgof2r21` | log `meta_data.__CheckoutInitAddress`, gated in `tools/qa.py:84` |
| Price | `PRICE_NGN = 2000` — Oga Pass, 30 days, all 9 tools | `worker/index.js` |
| Endpoints | `POST /issue`, `POST /flw-webhook`, `GET /verify`, `GET /activate` | `worker/index.js` |
| Fallbacks already coded | Flutterwave v4 OAuth + v3 verify; Paystack ("Path C — after CAC"); Selar→Zapier bridge | `worker/index.js` |
| Tools shipping | 9: agreement, notice, receipt, invoice, employment, caution, demand, payslip, warning | `site/index.html` (9 `<form>` + `renderX()` handlers) |
| SEO surface | 48 state pages | `tools/gen_state_pages.py` |
| Analytics | GA property `G-GO8VZB3R28` | `site/index.html` (`ANALYTICS_ID`) |
| Support | WhatsApp `2349021852845` | `site/index.html` (`SUPPORT_WHATSAPP`) |

**Conclusion: the gap is not technology. It is distribution and price.** A working
card-to-code pipeline that has already settled real money does not need rebuilding —
it needs customers pointed at it.

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

**Arithmetic.** At $20 per pass (~₦31,000 at ₦1,550/$, **UNVERIFIED** exchange rate —
confirm at launch):

> ₦1bn/month ÷ ₦31,000 ≈ **32,000 diaspora passes per month**
> ≈ **0.2% of a 15M diaspora.**

**That is ~15× the revenue per customer for the same product, and a 32,000-customer
problem instead of a 510,204-customer problem.** Flutterwave already supports the
collection and USD settlement; the fee is 4.8% instead of 2.0%, which is irrelevant
against a 15× price.

### Path B — B2B / bulk / API

Estate agents, property managers, landlords' associations, HR platforms, co-working
operators, SMEs. Per-seat or per-document bulk.

> 500 business accounts × ₦2,000,000/month = **₦1bn/month.**

Nigeria has tens of thousands of estate agencies (**UNVERIFIED** exact count). Fewer
customers, bigger cheques, far stickier, and — critically — **no per-customer
acquisition cost**, because these are sales conversations, not ad spend.

### Path C — Local volume at ₦2,000

Keep it. It is real money now, it validates the product, and it feeds A and B. But it
is the funnel, not the destination.

---

## 4. Sequencing — shortest time to first revenue

1. **Ship the conversion fix.** ✅ **DONE 8 Oct 2026.** Only 2 of 59 pages could take
   money; all 48 traffic pages had no pay path at all. Now 48/59 carry a pay path
   (sticky bar + inline CTA → `https://docoga.com.ng/#pricing`).
2. **Measure the baseline.** Read GA (`G-GO8VZB3R28`): sessions/month, top landing
   pages, current conversion rate. **I cannot read GA from this sandbox** — owner must.
   Every number after this depends on it.
3. **Add the USD/diaspora tier.** Highest revenue-per-customer move available, and the
   product already exists. Needs: a diaspora landing page + a USD price in Flutterwave.
4. **B2B outreach.** Sales, not code.

---

## 5. Open questions blocking the next step

Rule Zero: these are unknowns, not assumptions.

- **Traffic.** How many sessions/month, and what is the current free→paid conversion?
  Cannot be read from the repo. **Owner must check GA.**
- **Is the worker still live and are its secrets still set?** The URL is in the code and
  a real payment cleared on 19 Sep, but I cannot reach `workers.dev` from this sandbox
  to re-test. A dead worker means every CTA I just shipped points at a broken checkout.
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
