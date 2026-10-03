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
| Cloudflare Pages outage | Rare, short; repo is source of truth. (Was "Netlify outage" — hosting moved to Cloudflare Pages 3 Oct 2026) | >1h downtime |
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

## Device Fence (built 19 Sep 2026 — live, 16/16 unit + 6/6 e2e)
- **Risk:** one shared pass code = unlimited freeloaders.
- **Control:** 1 pass = 3 devices (did = docoga_did fingerprint, set by worker on first activate). 4th device → friendly 403 block + ₦2,000 renew hint. Devices inherited on top-up. No-did clients never blocked. MAX_DEVICES=3 single constant.
- **Owner override:** buyer WhatsApps receipt to 2349021852845 → fresh offline code (199 left).
- **Failure modes covered:** device clear/reinstall (new did = counts as new device — acceptable, override exists); shared cookie unlikely.

## Magic Pass Link (built 19 Sep 2026 — 6/6 e2e live)
- **Risk:** retyping OGA-XXXX codes cross-browser = friction; browsers cannot read each other's storage (security by design).
- **Control:** success.html green "Save to WhatsApp" button → wa.me prefilled text with https://docoga.com.ng/#code=OGA-… (hash fragment never sent to server/logs; ?code= also supported). Loader IIFE on index: regex [A-Za-z0-9-]{8,24} → history.replaceState strips URL → same-code guard toast → submitCode(c). Security = the code itself; 3-device fence caps sharing.
- **Failure modes covered:** invalid link → nothing stored, stays FREE; same link twice → "already active", no double-count; hash navigation doesn't reload → loader runs on load only (tested).

## Tools 8+9: Payslip + Warning Letter (built 19 Sep 2026 — 15/15 e2e)
- **Deliberate: NO auto-PAYE computation** (Nigeria Tax Act 2026 band changes = accuracy risk). Employer enters amounts; hint text states DocOga does not compute tax.
- Payslip computes gross/deductions/net + nairaWords(net); negative net flagged. XSS re-proven on all 16 new text fields (0 executions).

## State SEO pages (built 19 Sep 2026 — 24 pages)
- Facts verified before publishing: Lagos Tenancy Law 2011 s.13(1) notice table, s.4 advance cap, s.13(2)-(3) arrears; Recovery of Premises Act s.8 (FCT). Rivers/Oyo/Kano/Enugu pages use honest general framing + "confirm with a lawyer" wording — no invented specifics.
- All pages: "general information, not legal advice" footer; sitemap +24; home state-guides block.

## Email Automation (live 20 Sep 2026 — Brevo)
- **SMTP2GO REJECTED for Nigeria**: signup returns "Error code 3 - Service unavailable" (documented by SMTP2GO: "we don't currently operate in every territory"). Pivoted to Brevo same day.
- **Brevo free**: 300 emails/day, no card, never expires. Sender = azanijohn2017@gmail.com (verified). Direct API test 201 + full /issue end-to-end pass. Deliverability ~80% (vs SMTP2GO 96%) — acceptable: email is the BACKUP layer; code delivery never depends on it.
- **Owner decision (20 Sep 2026): the Brevo API key stays in chat, un-rotated** — owner explicitly wants AI in full control of infrastructure. Risk accepted by owner: chat is account-private, key has zero financial power (no card, no data), and rotation takes <60s on owner request. Secrets live in worker (BREVO_API_KEY + MAIL_FROM) and gitignored .worker-secrets.env.
- Brevo dashboard IP-blocking feature deliberately NOT activated (would block Cloudflare worker IPs).

## Day-27 Automatic Renewal Reminders (live 20 Sep 2026)
- Cron 0 7 * * * (08:00 WAT daily) on the worker → scans KV codes → any pass expiring within 3 days with an email and no `remindedAt` gets a branded renewal email (Brevo): expiry date, one-tap renew button (FLW link), "days stack if you renew early", magic link for unactivated passes, WhatsApp support. `remindedAt` stamp prevents re-sends.
- **No charge ever happens without the buyer's tap** (deliberate: Nigerian cards block most silent recurring debits; true auto-debit deferred to post-CAC with the yearly plan).
- Proven live via wrangler dev --remote + /__scheduled (real KV, real Brevo): reminder sent, remindedAt stamped, no double-send.
- Scaling note: full KV scan per run is fine below ~1k codes; index by expiry month if ever needed.

## Debug Round 2 (20 Sep 2026) — full-stack sweep
- Fixed: /issue now caps email at 254 chars / ref at 120 (was accepting 1000-char emails; deployed f6e96e50).
- Verified live: forged webhooks (underpay ₦1 / failed status / wrong currency) all rejected with ZERO codes minted; signatures enforced (403); all endpoints graceful under hostile params; expired code → live 403; device idempotency + 3-device cap unit-verified.
- success.html hostile loads, all secondary pages, dark mode, corrupted localStorage, legacy pass format: all survive clean.
- **TEST TRAP (documented): pass codes use alphabet [A-Z2-9] — no 0/1/I/O (anti-misread by design). Test codes containing 0/1 look like KV propagation lag but are actually rejected by normalizeCode.**
- New persistent tool: tools/tests/workertest.mjs (real worker code + mock KV, deterministic unit coverage: expiry, fence, hostile records, top-up).

---

## Update — 1 Oct 2026: independent audit from a fresh clone — 4 defects fixed, 1 revenue gap closed

**Scope:** full re-audit of `worker/index.js`, `site/index.html` (pass + payment + all 9 tools),
`site/success.html`, `tools/qa.py` and the test suites — performed from a *fresh* checkout, i.e.
exactly how a new operator, a CI runner or a future me sees the repo.

| # | Defect | Impact if it had shipped unnoticed | Status |
|---|---|---|---|
| 1 | `tools/qa.py` called `warn()` with 1 of its 2 required arguments whenever `.worker-secrets.env` was absent — which is **always** true on a fresh clone / CI | Pre-push gate crashed with a traceback and exit 1 (pushes blocked for no real reason), and the **secret-leak scan silently never ran** — the one check standing between a pasted secret and a public repo | ✅ **FIXED** — emits a warning instead; the scan still runs whenever the file exists |
| 2 | `site/index.html`: `getDocs()` returned `null` when the stored value was `'null'` (interrupted write, storage-quota error, another tab). `init()` then called `.filter()` on it → uncaught TypeError → **init() aborted before wiring anything** (defaults, draft restore, autosave listeners, WhatsApp links, GA4) on **every load, permanently**, for that browser | A "the site is broken, nothing works" report with no visible cause; the only fix is clearing browser storage — which no landlord will ever do | ✅ **FIXED** — `getDocs()` now always returns an array; a corrupt-storage row in the new DOM suite proves boot survives 5 hostile storage permutations |
| 3 | `worker/index.js` `sendMail()` sent the SMTP2GO header as `x-smtpto2go-api-key` (typo) | If Brevo is ever removed or key-rotated, the fallback provider fails **silently** — codes still appear on screen, so nobody notices until buyers complain about missing emails | ✅ **FIXED** |
| 4 | `worker/index.js` `/verify` minted codes with `email: ""` on the Flutterwave **v4** path — the primary payment-link flow — even though the charge payload carries `customer.email` | Buyers who arrived through the redirect path were **invisible to the day-27 renewal-reminder cron** (it skips records with no email) and got no pass email: the recurring-revenue mechanism silently missed the main sales channel | ✅ **FIXED** — email captured defensively (`customer.email` → `customer_email` → `payment_method.email` → `?email=`), never blocks code issuing |

### New safety net that runs anywhere (no browser, no Chromium)

`tools/tests/domtest.mjs` — loads the **real** `site/index.html` in jsdom and drives **65 checks**:
12 routes · all 9 tools filled with hostile payloads (XSS inert, output escaped) · print path ·
WhatsApp share · saved documents (incl. corrupt/unknown-type records) · draft restore ·
pass activation / same-code re-entry / top-up carry-over / renewed-code adoption / expiry /
4th-device fence / offline batch codes · magic links (`#code=` and `?code=`) · 5 corrupt-storage
permutations · live config values. The puppeteer suites are stronger but need Chromium (often
unavailable: fresh sandbox, CI, locked-down laptop) — this one needs only `npm i jsdom`, and
auto-skips with a notice if jsdom is missing, so it can never block a push on a fresh clone.

Both suites are now wired into `tools/qa.py` (**step 9**), together with a new
**anchor-integrity gate (step 10)**: a push can no longer land with a failing app-level
regression or a dead in-page link.

### Independently verified this round (no change needed)

- State SEO pages deep-link correctly (`#agreement`, `#notice`, `#receipt`, `#caution` → real SPA routes).
- Sitemap is complete: 27 locs = 24 state pages + privacy + terms + root; no stale entries.
- No duplicate `const` maps; `printCurrent` covers all 9 tools (the 7-tool regression stays fixed).
- The reported "static buy buttons don't react to pass state" **does not reproduce**: the SEO pages
  carry CTA links (correct by design), while the SPA's `#buy-btn` updates correctly in all three
  pass states (FREE / active / renewed), verified in the DOM suite.

### Still open — owner action

**Is the LIVE Netlify build the v2 pass model or the older build?** The audit sandbox cannot reach
`docoga.com.ng` (network allowlist), so this must be confirmed by running `python3 tools/verify_live.py`
from the owner's machine (or just opening the site and checking the Pricing page copy).
GitHub itself is current: `main` = `30e2ca6` (20 Sep), same tree as this audit started from.

---

## Update — 3 Oct 2026: SEO guide pages shipped + 1 factual defect fixed in the live Lagos pages

**Scope:** PLAN.md §4 keyword cluster (the content engine — §8 calls distribution ~80% of the
outcome, and until today the site had 24 state pages and **zero** national guide pages).

### Built: `tools/gen_guide_pages.py` → 7 national guide pages

| Page | Target query |
|---|---|
| `tenancy-agreement-nigeria.html` | tenancy agreement format Nigeria (**pillar**, priority 0.9) |
| `notice-to-quit-nigeria.html` | notice to quit in Nigeria — how many months |
| `caution-fee-nigeria.html` | is caution fee refundable in Nigeria |
| `rent-receipt-format-nigeria.html` | rent receipt format Nigeria / how to write one |
| `tenant-rights-nigeria.html` | rights of a tenant in Nigeria / landlord obligations |
| `shop-tenancy-agreement-nigeria.html` | agreement between landlord and tenant for a shop |
| `invoice-format-nigeria.html` | invoice format for small business Nigeria / 7.5% VAT |

Each page: FAQPage JSON-LD (rich-snippet eligible), canonical + og:url, cross-links to the other
guides, the 6 state pages and all 9 tools, and the standard not-legal-advice footer. Homepage gained
a "Free guides" block above the State guides block; sitemap 27 → **34** locs. The generator is
idempotent — re-running rewrites the pages and reports sitemap/index as already up to date.

**Every legal/tax claim was verified from sources before publishing** (the 19 Sep rule), including:
s.4 advance cap · s.13(1) notice table · s.13(2)-(3) arrears · s.44 self-help offence (₦250,000 /
6 months) · s.7 landlord obligations · s.9 business-premises access protection · the rent-receipt
duty and its ₦10,000 fine · separate receipt + 6-monthly account for deposits and service charges ·
compensation for consented improvements · VAT at 7.5% under the Nigeria Tax Act 2025 (1 Jan 2026)
with residential rent zero-rated. Where 2026 advisories disagree (the exact VAT registration
threshold) the page says so and points at the NRS/accountant instead of inventing a number. The 2026
Lagos Tenancy Bill is described as **a bill, not law**.

### 🔴 Defect found & fixed: the Lagos pages understated the law's exemptions

`s.1(3) Lagos Tenancy Law 2011` excludes **four** areas — **Apapa**, Ikeja GRA, Ikoyi and Victoria
Island — but all 4 live `*-lagos.html` pages (and `gen_state_pages.py`) listed only three, omitting
Apapa. Impact: an Apapa landlord or tenant is told the 2011 Law protects them when it does not apply
to their premises at all. Fixed in the generator **and** in the 4 published pages.
Verified against 4 independent sources (Nigeria Property Centre, LawPàdí, Koriat Law, aolegal FAQ).

### Gate strengthened: qa.py step 11 (site-wide, not index-only)

Step 6 parsed JSON-LD **only** in `index.html`, so the 31 non-index pages could ship broken
FAQPage schema with a green gate. New step 11 checks, on every page: JSON-LD parses · every absolute
`…/#route` deep link resolves to a real SPA route · every sitemap `<loc>` is a file we ship.
**Negative-tested**, because a check that cannot fail is not a check: injecting (a) a removed brace
in a page's JSON-LD, (b) a `#bogus` deep link, (c) a phantom sitemap loc → **3 ❌, exit 1, push
blocked**. Restored → green.

Current gate: **QA GREEN, 0 errors, 1 warning** (the warning is the absent gitignored
`.worker-secrets.env`, so the secret-leak scan is skipped — expected on a fresh clone).
`domtest.mjs` runs for real here (jsdom installed): **65 checks passed, 0 failed**.

### Still owner-side

`tools/verify_live.py` cannot run from the sandbox — it reaches `docoga.com.ng` over the network and
fails with `URLError: TLS/SSL connection has been closed (EOF)`. The 1 Oct open question
(*is the live Netlify build the v2 pass model?*) is therefore still unanswered and must be checked
from the owner's machine. Nothing in this update was pushed: the working tree is QA-green and ready
for `tools/ship.sh`.

---

## Update — 3 Oct 2026 (evening): hosting moved off Netlify to Cloudflare Pages — and the Git connection was found missing

**Owner instruction:** no Netlify at all; Cloudflare only, connected to Git so that a push deploys.

### What was verified before changing anything

| Check | Command / source | Result |
|---|---|---|
| Does a Pages project exist? | DNS lookup | `docoga.pages.dev` → **172.66.44.157**. Control: `zzq-docoga-does-not-exist-88213.pages.dev` → **NXDOMAIN**, so `*.pages.dev` is not a wildcard zone — the project is real |
| Where does the domain point? | DNS lookup | `docoga.com.ng` and `www` → **104.21.33.145 / 172.67.146.104** + `2606:4700::/32` = Cloudflare anycast. **Not** Netlify's old `75.2.60.5` |
| Is Netlify still connected? | `gh api …/commits/43d644c/status` | **YES** — `netlify/docoga/deploy-preview` → success → `deploy-preview-2--docoga.netlify.app` (2026-10-03T03:16:14Z), plus 3 check-runs from the GitHub App `netlify` |
| Is Cloudflare Pages connected to Git? | same call | **NO** — zero `cloudflare/pages` statuses or check-runs on that commit, and zero on `main` (`30e2ca6`) |
| Is `docoga.netlify.app` still up? | DNS lookup | Resolves to 13.52.188.95 / 52.52.192.191 (AWS) — the site exists but no longer serves our domain |

**Conclusion:** the Pages project and the domain are on Cloudflare, but the
project was **hand-uploaded**, not Git-connected. Every push to GitHub has been
silently *not* reaching production, while Netlify — a platform the owner no
longer wants — kept building the private repo.

### 🔴 Risk this closes

| Scenario | Impact | Status |
|---|---|---|
| Owner edits the repo, pushes, and believes the site changed | Live site silently drifts from source; a bug fix or a price change never reaches buyers; nobody notices because the push "succeeded" | 🔴 **IDENTIFIED 3 Oct** — fix is owner-side (Cloudflare dashboard: *Connect to Git*, production branch `main`, build command blank, **output directory `site`**). `GITHUB-CLOUDFLARE.md` documents it and the 30-second verification |
| Netlify GitHub App left installed on a private repo | A platform no longer in use keeps cloning and building the private repo on every push | 🔴 **IDENTIFIED 3 Oct** — disconnect steps in `GITHUB-CLOUDFLARE.md` Step 4; verify with the same `gh api` call |
| Cloudflare Pages output directory left blank or `/` | Publishes the **repo root**: PLAN.md, AUTOMATE.md, this risk log, `worker/` source, and `unlock-codes.txt` (₦374,000 of inventory) | 🟡 **MITIGATED BY DOCUMENTATION** — the field is called out as a security setting in README, DEPLOY.md and GITHUB-CLOUDFLARE.md |

### Repo changes in this migration

- **`netlify.toml` deleted** — deliberately *after* the disconnect steps were
  written down. While Netlify is still connected it pins Netlify's publish
  directory to `site/`; deleting it first would have been the dangerous order.
- **`GITHUB-NETLIFY.md` deleted → `GITHUB-CLOUDFLARE.md`** written, including
  the verification evidence above so a future operator does not have to
  re-derive it.
- README deploy section, DEPLOY.md Step 2 + Step 4 + the domain/DNS block,
  PLAN.md week-1 checkbox, QA-PROTOCOL.md ship.sh description, and
  `tools/ship.sh` steps 4 (label + comment) all switched to Cloudflare.
- DEPLOY.md's DNS block was **stale and wrong** — it still recorded
  `A @ -> 75.2.60.5` and `CNAME www -> docoga.netlify.app`. Replaced with the
  3 Oct verified records and a one-liner to re-check them.
- qa.py **step 12**: no Netlify deploy config may come back into the repo.

### Not verifiable from the sandbox (unchanged limitation)

Egress here is allowlisted to `api.github.com` and `registry.npmjs.org`. DNS
resolves fine, but every HTTPS call to `docoga.com.ng`, `*.pages.dev`,
`*.netlify.app`, `*.workers.dev` and `dash.cloudflare.com` fails with
`SSL_ERROR_SYSCALL`. So **which project actually serves docoga.com.ng today
cannot be confirmed from here** — only that the domain is on Cloudflare and the
repo is not wired to it.
