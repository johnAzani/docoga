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

---

## Update — 19 Sep evening: cross-browser pass report → 2 bugs found & fixed

**Trigger:** Owner reported: paid on Chrome, but FREE plan on Opera Mini / Firefox; Chrome still paid.

**Explanation (by design, not a bug):** The pass is stored in each browser's local storage. Chrome's memory ≠ Firefox's memory. **The code is the license key** — entering it on any browser activates that browser. Steps for a buyer: Pricing → "Have a code? Activate / extend" → enter code.

| # | Scenario | Status |
|---|---|---|
| 1 | **Same code re-entered on an active browser = +30 days free, forever stackable.** Modal even invited it ("entering a new code ADDS 30 days"). Both site AND success-page auto-activation forgot which code was used. | 🔴 → ✅ **FIXED.** Pass now stores the code's hash. Same code on active browser → "already active" toast, 0 days added. A NEW code still correctly adds 30 days (paid renewal). Browser-tested: 5/5 pass, 0 page errors. |
| 2 | **Worker /activate wrote to an undefined variable** (`code` instead of `key`) → used-tracking silently dead (ReferenceError swallowed). No data harm: webhook mints fresh random codes, never re-issues from a pool. | 🟡 → ✅ **FIXED** (worker 6a031928). |
| 3 | **Server-issued codes were valid forever** (no expiry check). | ✅ **FIXED.** New policy: a code is valid **30 days from its FIRST activation**; device switches allowed inside the window. One KV write per code lifetime. Live-proven: first activate 200, re-activate 200, backdated 31 days → 403 "This code has expired — buy a new Oga Pass (₦2,000).", garbage → 404. |
| 4 | Offline-batch codes (unlock-codes.txt, 200) never expire & validate locally (no server). | 🔵 **ACCEPTED** — manual/WhatsApp sales only; batch capped at 200; FNV-1a collision attack is theoretical at ₦2,000 scale. Retire the offline path once sales are online-only. |
| 5 | Opera Mini (data-savings/extreme mode) may not run JS or persist storage → site may look FREE every visit, tools may not work. | 🔵 **ACCEPTED** — support playbook: tell buyers to use Chrome, Firefox, or full Opera. Opera Mini is best-effort, not supported. |

**Support line for "I paid but it shows FREE":** "Your pass is saved per browser — go to Pricing → 'Have a code? Activate / extend' and enter your code (works on any browser/device, valid 30 days from first activation)."


---

## Update — 19 Sep night: OWNER'S PASS MODEL v2 shipped (worker LIVE, site staged)

**Owner spec (verbatim intent):** a code dies 30 days from PURCHASE · entering it on any browser continues from the SAME remaining days (day 7 on Chrome = day 7 on Firefox) · topping up makes the NEW code the source of truth — old code dies instantly, remaining days roll into the new code's 30.

**Architecture:** the Worker now owns the expiry. `/activate?code=X[&prev=OLD]` returns the server expiry; every browser stores and displays that one date (synced on every page load). Top-ups link code records: `prev.succ = new`, `new.exp = old.exp + 30d`. Renewed (dead) codes answer 410 with `renewedCode` + the new expiry — so any device holding an old code automatically adopts the newest one. All 200 offline-batch codes validate server-side via embedded FNV-1a hashes (clock starts at first activation — WhatsApp sale date is unknowable). Legacy records auto-migrate on first touch (exp = issuedAt + 30d — verified: QCK4 = exactly purchase + 30.0000 days).

**Test evidence:** 17/17 mock-KV unit tests (issuance, sync, carry math, old-code death, idempotent re-links, expiry, offline batch, legacy migration, /verify+prev); live production lifecycle (issue → activate ×2 sync → top-up carry exact → old code 410 → backdated 403 → garbage 404 → cleanup verified); 11/11 two-browser end-to-end tests on the real site incl. fresh-device old-code adoption and zero page errors. Storage isolation between profiles verified separately.

**Known window:** the LIVE site still runs the previous build (Netlify pipeline stalled — pending owner's Deploys screenshot). Until it deploys, the OLD site's local stacking quirk remains (server can't see browser-local state). Exposure: zero external customers so far. The new site build is committed, QA-green, and deploys automatically the moment Netlify wakes.

**Support lines (v2 model):**
- "I paid but it shows FREE" → enter your code on that browser (Pricing → Have a code?) — it continues from your same remaining days.
- "I topped up but old browser shows old code" → it self-heals on next page load (or re-enter any of your codes — it adopts the newest).
- "Code says renewed/expired" → renewed: use the newest code you received; expired: buy a new pass (₦2,000).

**KV budget per sale: 2 writes** (code + ref at issue) — reads only thereafter; top-up adds 2. Well within the 1,000/day free tier (~450 sales/day ceiling; act if daily sales pass ~300).
