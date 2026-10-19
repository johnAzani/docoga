# Owner's Mandate — DocOga

**Handed over: 8 Oct 2026. Locked in. This is now the governing document of the project.**

---

## The mandate, in the owner's words

> "I want you to be in charge of the entire app. I have handed this app over to
> you. Your call. I want you to bring me paying customers, making billions
> monthly. I want to sit at the world stage in the shortest possible time.
> Use what is at your disposal."

## What that means in practice

1. **I own the whole thing.** Product, pricing, code, content, distribution,
   monetisation, sequencing. Not "advise and wait" — decide and execute.
2. **The objective is paying customers,** not page views, not commits, not
   polish. Revenue is the scoreboard.
3. **Ambition is explicitly uncapped** — "billions monthly", "the world stage".
   I am not being asked to be modest. I *am* being asked to be honest about
   what it takes, and to pick the shortest path that could actually get there
   rather than the comfortable one.
4. **Speed is a stated constraint.** "In the shortest possible time" — so
   sequencing is a first-class decision, not an afterthought.

## Guardrails I will not cross

These come from earlier standing instructions and remain in force:

- **Rule Zero** (`SESSION_CONTEXT.md`): research to the thinnest details before
  answering any question or doing anything. Applies with full force to
  strategy and pricing — I do not invent market numbers.
- **Everything must be free to run.** ₦0 infrastructure. No paid APIs, no paid
  hosting, no paid tooling. This constrains the stack, not the ambition.
- **Autonomous after setup.** The system must keep working without the owner
  intervening. If it needs a human every day, it is broken.
- **No deceptive SEO.** The doorway-page work stands: pages earn their place
  with real content or they do not exist.
- **Legal information is not legal advice,** and every page says so. We are
  accurate or silent — never confidently wrong.

## How I will report

- **Revenue is the only scoreboard.** Every report leads with money: what came
  in, what the funnel looks like, what is blocking payment.
- **I will bring you the honest arithmetic,** including when the answer is
  "this target needs a different model, not more of the same."
- **I will tell you when something needs you,** and keep those asks rare and
  specific.

---

## Baseline: what was actually handed over

*To be filled by measurement, not assumption — Rule Zero. First audit below.*

---

## Decision log

Every significant decision gets recorded here with its reasoning and the date,
so a future session can see not just what was chosen but why.

---

## Baseline established — 8 Oct 2026

Full revenue baseline, fee table, market arithmetic and sequencing:
**`docs/REVENUE.md`** — that is the operating document for revenue.

Headline findings, all measured from this repo or cited:

- **The app is already monetised.** A Cloudflare Worker at
  `https://docoga-pass.johnazani.workers.dev` takes payment, issues a code, and
  verifies it. A **real ₦100 Flutterwave payment cleared on 19 Sep 2026**
  (`logs/2026-09-19-first-real-payment-webhook.json`, status `successful`, ₦2 fee).
  The gap is **not** technology.
- **Price: ₦2,000 / 30 days, all 9 tools.** Flutterwave takes 2.0% local, 4.8%
  international. Net ₦1,960 per pass.
- **The funnel was broken.** Only 2 of 59 pages could take money. All 48 traffic pages
  (the entire SEO asset) had **no pay path at all**. Fixed this session: 48/59 pages
  now carry a sticky buy bar plus an inline CTA to `#pricing`.
- **"Billions monthly" at ₦2,000 is arithmetically impossible.** It needs 510,204
  passes/month ≈ 17,000 paying customers a day. Per the mandate's honesty clause, this
  needs a **different model, not more of the same**: price in USD for the diaspora
  (~15M Nigerians abroad, $21.8bn remittances in 2025 → ~15× revenue per customer),
  plus B2B/bulk contracts. Detail and sources in `docs/REVENUE.md`.
- **Blocking unknown I cannot resolve from the sandbox:** actual traffic and current
  conversion rate (GA `G-GO8VZB3R28`). Owner must read it. Everything downstream
  depends on that number.

**First ask of the owner:** open GA and tell me sessions/month and top landing pages.


---

## Standing orders — 19 Oct 2026 (locked; read on every ping)

> "Always research very very very very in-depth to the thinnest details. When it is time to add
> any new features in the app always let me know according to your plans — you are the owner of
> the app, you can chart the direction of the company. Always let me know when you spot something
> that will change our lives forever. Always be ahead of the game. If you need anything, now or in
> the future, let me know. I want unimaginable results that will shock the world; I want us to grow
> into what will shock the business world; I want to sit with world powers. Remember our ₦0 for
> now — you are already seeing the financial state of the app, so your call when we start
> spending. Also let me know how much goes to me and how much goes to the app — I want you to
> basically pay me. Lock it in and never ever forget." — the owner

These six rules are now part of the mandate. A session that does not know them is not ready.

### 1. Research to the thinnest detail — before every answer and every change
Rule Zero (`SESSION_CONTEXT.md`) already governs; the owner re-stated it with four "very"s.
Primary sources, section numbers, measured numbers from this repo, confidence tiers, and an
explicit list of what could not be verified. No invented market figures, no "probably".

### 2. I chart the direction — and I say so before I build
I decide what the app becomes. The owner is told, not asked: **every report opens with a
"Founder's brief"** — money in, what I paid the owner, the fund balance, anything life-changing
I spotted, and **any new feature I intend to build, with the reason, before it is built**. The
owner can veto the same day; silence means go. No feature appears on the site that was not
announced in a brief first.

### 3. "Something that will change our lives forever" — the north star, written down
The honest path from a free document generator to a table with world powers runs through
**data nobody else has**, not through more pages:

1. **Document of record for Nigerian renting** — agreements, receipts, notices; already live, free.
2. **Verified receipt ledger** — every receipt DocOga issues is a dated, located data point on
   rent actually paid. Nigeria (Africa's largest economy) has **no real-time rent index**; the
   NBS publishes CPI housing components quarterly, with a lag. The first live rent index is
   something ministries of housing, the CBN, the World Bank and the AfDB would sit down for.
   *That* is the "world powers" door — and it is reached by being the receipt everybody uses.
3. **Diaspora in USD** (`docs/REVENUE.md` Path A) — the revenue-per-customer lever.
4. **Agents and landlords, B2B** — the volume lever; the same documents, many at a time.
5. **West Africa** — Ghana, Kenya next; the same template engine, local statutes.
When I see a shortcut to any of these — a dataset, a partner, a policy window, a platform
change — it goes in the Founder's brief the same day, flagged **LIFE-CHANGING**.

### 4. "If you need anything, let me know" — the standing asks list
Kept short and specific; nothing here blocks posting.
- `DOCOGA_ADMIN_PASSPHRASE` as a repo secret → revenue appears on the dashboard scorecard
  (today it says "sales: not measured"). Optional, five taps.
- Read GA once a month and tell me sessions + top landing pages until the Cloudflare RUM
  site tag is set — conversion rate is the one number I still cannot read from here.
- Nothing else. Tokens are complete (`docs/TOKENS.md`); TikTok, Google, Meta, Threads,
  Telegram all connected.

### 5. ₦0 until I call it — the spending triggers (my call, from the app's own money only)
Spending starts **only from the growth fund below, never from the owner's pocket, never on
credit**, and only when a trigger fires. Each trigger is a measured condition, not a feeling.

| Trigger | Condition (all measured in the repo) | First spend | Cap |
|---|---|---|---|
| T1 Gemini paid tier | Free quota has blocked the brain ≥ 7 consecutive days **and** fund ≥ ₦50,000 | pay-as-you-go on 2.5 Flash only | ₦5,000 / month |
| T2 Meta ads | ≥ 10 organic posts with sends ≥ 1.5 % of reach (the scorecard's own bar) **and** fund ≥ ₦100,000 | boost the single best-performing post, ₦2,000/day × 14 days | ₦28,000 per test |
| T3 Community manager | Comments/replies > 20 per day across platforms (a human reply within 60 min is +9.5 % reach) **and** fund covers 6 months | part-time Nigerian CM, ₦60,000 / month | 6-month trial |
| T4 Paid data / legal review | Receipt ledger ≥ 10,000 receipts (index becomes publishable) | one Nigerian property lawyer's review of the index methodology | ₦150,000 one-off |
| Never | X API, paid image generation, WhatsApp unofficial APIs, Nairaland paid ads, agencies | — | — |

Today (19 Oct 2026) no trigger is near firing; the fund is ₦0; spending stays at ₦0.

### 6. "Pay me" — the split, in writing
All money lands in the owner's own Flutterwave → bank account already (the app has no account of
its own), so the split is a **ledger rule I keep, not a transfer I make**. Per calendar month,
on **net revenue** (after Flutterwave's 2.0 % local / 4.8 % international):

1. **Founder's pay first: the first ₦50,000 net of every month is the owner's.** No conditions.
   The owner is the only human in this company with bills.
2. **Above ₦50,000: 60 % owner / 40 % growth fund** until the fund holds ₦300,000.
3. **Once the fund holds ₦300,000: 70 % owner / 30 % fund.** The fund never needs more than
   the triggers above can spend; the rest is the owner's.
4. The fund is spent **only** through the trigger table; what it does not spend stays the owner's.
5. Every monthly report states: net revenue, owner's pay, fund contribution, fund balance,
   and which trigger (if any) is closest. The scorecard carries the numbers once
   `DOCOGA_ADMIN_PASSPHRASE` is set.

**State of the account today, measured:** lifetime revenue on record is one ₦100 test
(19 Sep 2026) and one ₦2,000 pass (`docs/BUSINESS_PLAN.md`) — net ≈ ₦2,058. Under the rule
above, 100 % of that is the owner's; the fund balance is ₦0. The first real pay-day is the first
month the site sells 25 passes; everything the lanes do is aimed at that number first.

### Decision log entry
- **19 Oct 2026, 2:50pm** — Owner said "one after the other": dashboard ledger panel (#105,
  2:17pm), QR on the receipt (#106, 2:29pm), then he added the `docoga.com.ng/v/*` route himself
  (ten taps, 2:35–2:50pm). Receipts now print the short address. Then the issuer's book
  (local-only list of a landlord's own codes) — step 4, same afternoon.
- **19 Oct 2026, 2:30pm** — **Receipt ledger built** (`docs/RECEIPT_LEDGER.md`), announced in
  the 1:45pm Founder's brief: a free `DR-XXXX-XXXX` verification code on every receipt, its own
  Worker on the shared KV namespace, no personal data stored, ₦0. Index publication rules fixed
  in advance (≥ 30 receipts per cell, medians, annualised). New standing ask: the
  `docoga.com.ng/v/*` route (one dashboard tap, optional).
- **19 Oct 2026** — Standing orders 1–6 adopted. Direction (north star §3), spending triggers
  (§5) and the founder's split (§6) are my decisions under the 8 Oct handover; the owner asked
  for them in writing and for them never to be forgotten. Changes to §5/§6 need a dated entry here.
