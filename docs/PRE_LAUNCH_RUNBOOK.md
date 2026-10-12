# Pre-launch runbook — Business tier (owner)

> Phase 4 complete as of 11 Oct 2026 (branch `arena/d3f5797d-docoga`). This is
> the whole remaining owner-side path, in order. Steps 1–2 (mailbox, pre-deploy)
> are independent of the FLW outcome and can run NOW while the FLW matter
> (step 0) resolves. Each step says what success looks like. If a step fails,
> STOP and note the exact error — the product was built to fail honestly, so
> the error text is the diagnosis.

## 0. Flutterwave: the "DocOga" business verification (IN PROGRESS as of 11 Oct 21:00)

Background (researched to the vendor's own docs — full write-up:
`docs/BUSINESS_TIER_RESEARCH.md` §14): the live account is Personal (runs the
₦2,000 Oga Pass via a v3 checkout link — untouched); the Business money path
is FLW **v4 (OAuth)** and its live credentials are issued to an **approved
business**; bank-transfer buyers see the **merchant's registered name** on the
virtual account (so it must be "DocOga", not a personal name).

**Status (11 Oct):** the DocOga business account is **created** (sole
proprietorship, trading name DocOga, bank account added, business info
entered). The 7-step verification wizard is paused at **Step 2 (Business
information)**: the sole-proprietorship path requires a **company
registration number** ("BN …" — a CAC business-name number), which you don't
have yet, and the dashboard's business-type dropdown offers **no
unregistered option** (the "Starter / unregistered" category exists in FLW's
official Nigeria onboarding docs but is not presented in this flow).

Two paths forward — run A, start B if A doesn't resolve within a working day:

**Path A (₦0) — ask FLW support to enable the unregistered path.** In the
dashboard chat (orange bubble, bottom-right) or hi@flutterwavego.com, paste:

```
Hello, I'm onboarding my Nigerian business DocOga (Merchant ID: ___) as a
sole proprietor without CAC registration. Your Nigeria onboarding page lists
a Starter (unregistered) business category requiring only personal ID,
website, residential meter number, BVN/NIN and estimated monthly sales — but
my dashboard flow only offers registered business types and requires a
company registration number I don't have. Please enable the
unregistered/Starter onboarding path for this business, or advise the correct
process. Website: https://docoga.com.ng
```

(For the Merchant ID: dashboard top-left, "DocOga — Merchant ID:" → tap
"View here".)

**Path B (≈₦20.7k official, 2–5 working days) — CAC business-name
registration.** cac.gov.ng portal, DIY: name search/reservation ₦750 +
filing ₦20,000 + ~₦162 portal fee. Needs: NIN (scanned card — used for
e-signature), email, address. A **TIN is auto-issued** on the certificate.
Then: resume the FLW wizard, enter the **BN number** in the Company
registration number field, and add the CAC certificate when the document
step asks. (Agents charge ≈₦45k for the same result.)

**After verification approves — the 5-point check** (dossier §14.7):
(a) Settings → Developers → API Keys shows live **Client ID + Client
Secret** (v4)? (b) a test virtual account creates — and what **name** does
it show (must be "DocOga")? (c) account labelled as the business type?
(d) displayed transaction limits ≫ ₦103,200? (e) a small test payout lands
in your bank? **Report these answers in the session.**

## 1. Make business@docoga.com.ng real (~20 min — NOW, blocks the pre-deploy)

The pre-deploy (step 2) publishes a support page that tells buyers to email
business@ — so the lane must exist first. Lane model (owner, 12 Oct):
**fully autonomous** — the auto-reply is the entire lane; nobody reads,
nobody replies (CANNED.md = reference only). Zoho's free signup is blocked
for this account, so the mailbox is built from parts DocOga already runs:
**Cloudflare Email Routing + the `docoga-support-mail` worker** (auto-reply
AS business@ + silent archive copy to your Gmail). Full walkthrough, DNS
records and test plan: `docs/support/AUTO_REPLY.md`.

**DONE 12 Oct 2026** — walked live with the owner on the phone (Cloudflare
dashboard; the owner has no wrangler machine, so the worker went in by
**code-paste into the dashboard editor** — now the canonical owner deploy
path, recorded in `docs/support/AUTO_REPLY.md` "Live status").

- [x] CF dashboard: *Email Routing → Onboard Domain* `docoga.com.ng` → **Activate** (07:05). CF auto-added MX route1/2/3 (prio 21/34/71) + `cf2024-1._domainkey` DKIM + apex SPF; apex SPF then merged to `v=spf1 include:spf.brevo.com include:_spf.mx.cloudflare.net ~all` (07:24) — **live-verified by direct DNS query 14:50** (exact value; `brevo-code` TXT + `_dmarc` untouched)
- [x] CF dashboard: *Destinations → Add* `azanijohn2017@gmail.com` → **Verify** (07:32)
- [x] Worker `docoga-support-mail`: created + `worker/support-mail/index.js` pasted + deployed via the dashboard editor (12:53). Code verified live by the editor test — `Error: No fetch handler!` is the expected answer (email-only worker; the public URL's 1101 is that, not a fault). Vars: `ARCHIVE_TO` (variable) + `BREVO_API_KEY` (secret — a FRESH v3 key, 13:36; coexists with docoga-pass's old key)
- [x] CF dashboard: *Routing rules* → `business@docoga.com.ng` → **Send to a Worker → `docoga-support-mail`** (13:54)
- [x] Test 1 (14:24, subject "Test 1 - normal mail"): archive copy in Gmail **AND** auto-reply FROM business@ — threaded under the original (CF native `reply()` worked), verbatim contract copy, landed in **Primary** (not spam) within ~3 min
- [x] Test 2 (14:37, subject "Mail Delivery Failure"): archive copy only, **no** auto-reply (guard proven live)
- [x] SPF valid: merged record live-verified by direct DNS query (14:50) — exact `v=spf1 include:spf.brevo.com include:_spf.mx.cloudflare.net ~all`

Activity log: exactly 2 inbound + 1 outbound (the reply); zero outbound for
Test 2. Remaining 1-minute checks (non-blocking): what the pinned
**Catch-all** rule does with unmatched addresses (should reject — otherwise
random-address spam archives into the owner's Gmail), and CF usage after the
tests (settles whether `reply()` bills as paid "Email Sending" — the Brevo
fallback makes the answer irrelevant to ₦0).

## 2. Pre-deploy (safe NOW — the money path is sealed, everything else goes live)

The live site today still shows the OLD Business card (the "quote by
WhatsApp" flow you retired). The pre-deploy fixes that **without exposing a
broken payment flow**: the site ships with the **`BIZ_LIVE = false` gate**
— the "Configure & pay online" entry point is removed from the Business card
at load (a DOM test guards it), while the waitlist, support page, privacy
update, team portal and all worker endpoints go live normally. No public
route reaches the charge flow, so missing FLW credentials change nothing
yet.

1. **Set ONE worker secret now** (the FLW ones wait for step 0): Cloudflare
   dashboard → Workers → `docoga-pass` → Settings → Variables →
   `TEAM_AUTH_SECRET` = any long random string (required for
   `/business/login*` + `/business/team*`; without it they fail closed 503).
2. **Deploy:**

```
bash tools/deploy.sh
```

   (worker, then site. Known quirk from 10 Oct: the first attempt can hit a
   token-validation error — retry; the retry publishes.)
3. **Verify:** the script prints the probes — expect **400 "valid email
   required"** (team creation) and **401 "sign_in_required"** (renewal), not
   404. Then in a browser: the Business card shows COMING SOON + the notify
   form and **no** "Configure & pay online" link; the support page is live;
   the waitlist form accepts an entry (it lands in KV as `bizwait:{email}`).

## 3. FLW resolved → point the worker at it (15 min)

When step 0 concludes (support enabled the unregistered path, or the CAC
certificate is in hand) and the business is **approved**:

1. **FLW side (inside the DocOga business):** register a webhook — URL =
   `https://docoga-pass.johnazani.workers.dev/flw-webhook`, event = charge
   completed; copy the webhook **hash**.
2. **Worker secrets** (Cloudflare → docoga-pass → Variables — note: setting a
   secret publishes a new deploy of the same code, so this is also when the
   money path switches on):
   - `FLW_CLIENT_ID` + `FLW_CLIENT_SECRET` — the business's **v4 live**
     Client ID / Client Secret (FLW Settings → Developers → API Keys). **Not**
     a classic v3 secret key.
   - `FLW_WEBHOOK_HASH` — the hash from 3.1. Bank-transfer (VA) confirmation
     arrives ONLY by signed webhook — without it the transfer leg hangs at
     "waiting for payment" (card works via redirect + verify).
3. Re-run the step-0 5-point check (a)–(e) live.

## 4. Phase 5 (publish) — your §11 decisions, then the flip

The card flips from COMING SOON to live with the price. The open owner
questions are in `docs/BUSINESS_TIER_RESEARCH.md` §11 (refund window,
published entry number, named contact, SLA capacity, quarterly option,
discovery). The 14-day refund is still PROPOSED, not promised, everywhere —
a test guards it.

Mechanics (the session does these once the §11 answers are in):
- `site/index.html` → `const BIZ_LIVE = true;` (the pay link reappears —
  it's still in the source; the constant is the only gate)
- published price text per §11 #3 → `bash tools/deploy.sh`
- then the **waitlist launch email**: the list is KV `bizwait:{email}`
  (read in the Cloudflare KV dashboard — by design there is no public read
  endpoint); email each person. Copy (edit the price line to the §11 answer):

```
Subject: DocOga Business is live — set up your team in 2 minutes

Hi {first name},

You asked to be notified when DocOga Business launched — it has.

It's fully self-serve: pick your seats and document volume, see the price
instantly (from ₦96,000/yr, VAT line included — computed from YOUR numbers),
pay by card or bank transfer, and your team activates by itself. No quote,
no waiting, no WhatsApp.

• Your firm's name and logo on every document
• Team seats you invite and remove by email
• One annual invoice with VAT — auto-confirmed

Set it up here: https://docoga.com.ng/#business-setup

— DocOga, Abuja
https://docoga.com.ng
```

(If the list has grown past ~20 names, tell the session — we'll add a
secret-gated notify endpoint; the list stays read-only in v1.)

## 5. Rehearsal — one real payment (the Phase 2 gate)

The honest minimum is one real Business invoice. The smallest published
quote is 3 seats / 100 docs = **₦103,200 incl. VAT** — that IS the price
(retail's "small amount" pattern doesn't map: there is no smaller business
tier, and the price must not be touched for the test).

1. Go to `docoga.com.ng/#business-setup` and create a team with **your own
   business** (it doubles as friendly-team #1 of the Phase 3 gate, with your
   own permission — the dossier's own suggestion).
2. Sign in via the emailed magic link. Pay **both methods**:
   - [ ] card / USSD first (cheaper to abort if the v4 `generic` charge
         isn't enabled — expect an honest 502 + transfer fallback, not a
         silent failure)
   - [ ] then bank transfer to the generated VA, exact amount
3. Watch the automation:
   - [ ] team flips to ACTIVE by itself (no email needed from you)
   - [ ] owner email "your team is live"
   - [ ] dashboard shows ACTIVE until {date}, invoices card lists it PAID
   - [ ] every document renders with the firm name/logo, no DocOga banner
   - [ ] the invoice opens as the printable page (Print → Save as PDF)
4. **Wrong-amount case:** create a second small team (or use the first
   team's renewal window later) and transfer a deliberately wrong amount:
   - [ ] NO activation; FLW auto-reverses the underpayment (vendor
         behaviour, confirmed in docs) and the re-issue email arrives
   - [ ] the old VA is voided; the corrected transfer activates it

If anything in 3/4 doesn't happen: the worker logs are where the diagnosis
lives (`[docoga-*]` lines), and the KV record (`team:*`, `inv:*`) shows the
state. Reply in the session with the error and the state — that's the whole
protocol.

## 6. Two friendly teams (the Phase 3 exit gate)

Two real teams (your own businesses/contacts, **with permission, no cold
outreach** per the groundwork) complete buy→use with **zero owner touches** —
you watch the KV/emails, you don't intervene. One of them can be the
rehearsal team from step 5 if it's a genuine second business of yours.

- [ ] team A: create → sign in → pay → branded docs → (owner) invite a seat
- [ ] team B: same
- [ ] you replied to zero customer messages; every state change was automatic

## Rollback

Everything deployed here is a strict forward superset of what's live; retail
(Oga Pass) is untouched by construction (the invoice branch runs before the
retail gate and pass references never match invoices). To roll back:
re-deploy the previous worker/site versions (wrangler keeps them). No data
migrations were done — the new KV keys (`teaminv:*`, `team:*:usage:*`,
`renewal_*` fields) are additive. If a pre-deploy (step 2) needs to be
undone specifically: re-deploy the previous site+worker; the waitlist KV
entries and any team records are harmless to keep.
