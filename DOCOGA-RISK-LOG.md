# DocOga — Worst-Case Scenario Log & Owner Rituals

*Red-team audit performed 19 Sep 2026 against LIVE systems. Every scenario below is
either TESTED, MITIGATED, or consciously ACCEPTED with a reason.*

## 🔴 Found & FIXED during this audit

| # | Scenario | Impact if unfixed | Status |
|---|---|---|---|
| 1 | Bot floods `/flw-webhook` with garbage → old flight-recorder v2 wrote KV on EVERY attempt → burns 1,000/day KV write budget → real customers' codes can't save | Silent sales failure at night | **FIXED 19 Sep** — recorder v2 removed; KV writes now happen ONLY behind a valid Flutterwave signature. Verified live: flood → 403, zero writes. |
| 2 | `/issue` endpoint brute-force (old secret, unknown strength) | Free codes minted | **FIXED 19 Sep** — ISSUE_SECRET rotated to 48-char random; verified: new key works (200), wrong/missing key 401. |
| 3 | No way to notice webhooks stopped arriving (e.g. FLW changes signature scheme) | Sales die silently for days | **FIXED 19 Sep** — Worker root now reports vitals: `{"ok":true,"priceNGN":2000,"lastWebhookMinutesAgo":N}`. One URL = instant health check. |
| 4 | XSS through document form fields (preview, docs list, print) | Customer data theft, site takeover | **TESTED 19 Sep** — injected `<script>`, `onerror`, `-alert-` payloads into 17 fields across all 5 docs: ZERO executions; all rendered inert (esc() discipline holds). |

## 🟡 Mitigated by design (already in place)

| Scenario | Safety net |
|---|---|
| Webhook never arrives / buyer closes browser before redirect | success.html → WhatsApp fallback with receipt → manual issue via `/issue` (owner key in .worker-secrets.env) |
| Buyer pays twice (network retry) | Idempotent per-reference; extra code(s) issued → refund policy via WhatsApp; rare |
| Buyer underpays / wrong currency | Worker gate: amount ≥ ₦2,000 AND currency NGN else "ignored" — tested live |
| Forged webhook signature | 403 (dual-scheme HMAC v3+v4) — tested live |
| Pass state confusion (sell to active member) | State-aware CTAs + QA regression check #29 — tested 3 states |
| localStorage unavailable (private mode) | store wrapper falls back gracefully (no crash) |
| Worker outage (Cloudflare down) | Site still works free; buy → WhatsApp manual path; SELAR fallback documented (AUTOMATE.md Path A) |
| Print blocked (embedded browsers) | try/catch → toast guidance |

## 🔵 Accepted risks (eyes open)

| Scenario | Why accepted | Trigger to act |
|---|---|---|
| KYC rejected | Fix & resubmit — no funds lost | FLW notification |
| Chargeback on stolen card after code issued | ₦2,000 loss, rare at this scale | >1 per month |
| KV 1k writes/day ceiling (~200 sales/day) | Free tier; 200 sales/day = ₦400k/mo — a good problem | >100 sales/day sustained |
| Netlify outage | Rare, short; repo is source of truth | >1h downtime |
| Copycat clones site | Moat = codes+machine+SEO history+price | Traffic drop in GA4 |
| Flutterwave itself frozen | Payouts pause (money safe); Selar alternative | FLW notice |

## 🔑 Owner rituals (protect the machine in 60 seconds/day)

**Daily (10 seconds):** open `https://docoga-pass.johnazani.workers.dev/`
→ must say `"ok":true`. If you had a sale recently, `lastWebhookMinutesAgo` should be small.
If it says something else → message me / check dashboard.

**Weekly (1 minute):** FLW dashboard → Balances + Transactions vs site sales; GA4 → users.
Ask me to run `tools/verify_live.py` (full 20-check sweep).

**Yearly:** renew domain **docoga.com.ng** at GO54 (~₦3,000, expires Sep 2027) — set a phone
reminder for Aug 2027 NOW. Also: rotate GitHub PAT after setup sessions; delete pasted tokens
from chat.

**If a customer says "I paid but no code":** 1) check WhatsApp for their receipt,
2) Worker root URL (health), 3) message me the payment reference — I can issue a code in
seconds via `/issue`. Refund is always an option after KYC unlocks withdrawals.

*Test keys/debug keys: `debug:last-webhook` + `debug:last-webhook-ts` remain (valid-signature
only, safe from flooding). Delete them after the first ~10 real customers for privacy hygiene.*
