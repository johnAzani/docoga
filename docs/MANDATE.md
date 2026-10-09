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
