# Pre-launch runbook — Business tier (owner, ~1 hour)

> Phase 4 complete as of 11 Oct 2026 (branch `arena/d3f5797d-docoga`). This is
> the whole remaining owner-side path, in order. Everything here is real-money
> or real-infra, so it's yours to run; the sandbox can't (no Cloudflare egress).
> Each step says what success looks like. If a step fails, STOP and note the
> exact error — the product was built to fail honestly, so the error text is
> the diagnosis.

## 0. Flutterwave: create the "DocOga" business account (do this FIRST)

Your live FLW account is **Personal** (it runs the ₦2,000 Oga Pass via a v3
checkout link — that stays untouched). Research to the vendor's own docs (full
write-up: `docs/BUSINESS_TIER_RESEARCH.md` §14) settled three things:

1. **The Business money path is built on FLW v4 (OAuth)**, and v4 LIVE
   credentials (Client ID / Client Secret) are issued to an **approved
   business** — a Personal account very likely can't produce them. So the
   Business path needs a business account; forcing it onto the Personal one
   would be a dead end.
2. **Bank-transfer buyers see the merchant's registered name** on the virtual
   account. Personal account = your personal name on a ₦103k B2B transfer.
   Business account = "DocOga".
3. **CAC is NOT required to launch.** FLW has a **Starter (unregistered
   business)** category: personal ID + website + electric meter number +
   BVN/NIN + estimated monthly sales + business profile. No CAC certificate,
   no business bank account — it settles to FLW's MFB wallet and pays out to
   your personal bank account. CAC business-name registration (≈₦23k official
   / ≈₦45k via agent, 2–5 working days, TIN auto-issued) is deferred: it only
   adds a business-name bank account and registered-entity standing, neither
   of which blocks v1.

**Actions (≈30 min now + KYC wait):**

1. [ ] **Create the business** — Flutterwave dashboard → bottom-left →
      *Your Businesses* → **New Business +** → name **DocOga** → type
      **Starter / unregistered business**. (If that type isn't offered for NG,
      email hi@flutterwavego.com — the NG onboarding docs list it.)
2. [ ] **Complete its KYC** — personal ID, website `https://docoga.com.ng`,
      residential electric meter number, BVN + NIN, estimated monthly sales
      (e.g. "₦500,000 — B2B SaaS, 3–5 teams/month early"), short business
      profile ("DocOga generates branded tenancy/property/HR documents for
      small teams — docoga.com.ng").
3. [ ] **When approved, run the 5-point verification** (dossier §14.7) and
      report the answers here: (a) live **Client ID + Client Secret**
      (v4) visible under Settings → Developers → API Keys? (b) test VA
      creates — what name does it show? (c) account labelled Business/Starter?
      (d) transaction limits displayed (expect ≫ ₦103,200)? (e) small test
      payout from the MFB wallet to your bank lands?
4. [ ] **Optional, in parallel (does not block launch):** start CAC
      business-name registration for "DocOga" (portal: ~₦23k, 2–5 working
      days). When the certificate arrives, the account upgrades
      Starter → sole-proprietorship by adding it.

**Do NOT deploy (step 1) before item 3(a)** — the worker's credentials come
from the new business account.

## 1. Deploy (secrets first, then 2 commands)

The live worker is the **10-Oct retail-pass worker only** — Phases 0–4 have
never been deployed, so the Business endpoints don't exist in production yet.

1. **Set the four worker secrets** (Cloudflare dashboard → Workers →
   `docoga-pass` → Settings → Variables). `deploy.sh` prints the exact
   checklist when you run it — but the values must exist BEFORE the deploy.
   Three come from the **new DocOga business account** (step 0), one is yours
   to invent:
   - `TEAM_AUTH_SECRET` — any long random string (invents team auth; without
     it the team endpoints fail closed 503).
   - `FLW_CLIENT_ID` + `FLW_CLIENT_SECRET` — the business account's **v4 live**
     Client ID / Client Secret (FLW Settings → Developers → API Keys). The
     Business money path is v4-only; these are what create the VAs and the
     card charges and verify them. **Not** the classic v3 secret key.
   - `FLW_WEBHOOK_HASH` — FLW Webhooks → hash for the endpoint posted to the
     worker's `/flw-webhook`. Bank transfer (VA) confirmation is webhook-only —
     without it the transfer leg of the rehearsal hangs at "waiting for
     payment" (card works via redirect + verify).
2. **Then deploy:**

```
bash tools/deploy.sh
```

   1. `cd worker && npx wrangler deploy` — the money path + portal + cron.
   2. root `npx wrangler deploy` — the site (portal, support page, privacy).

   Known quirk (10 Oct): the first deploy attempt can hit a
   token-validation error — retry; the retry publishes.

Verify block: the script prints the curls; the Business probes should
answer **400 "valid email required"** (creation) and **401
"sign_in_required"** (renewal), not 404. If 404, the worker deploy didn't
take.

## 2. Make business@docoga.com.ng real (15 min)

Follow `docs/support/AUTO_REPLY.md`: free Brevo mailbox on the domain (or the
free-tier alternative), SPF check, enable the **exact** auto-reply text from
the doc. Then send yourself a test mail from a personal address and confirm
it lands AND the auto-reply fires.

- [ ] mailbox exists and receives
- [ ] SPF valid (mxtoolbox free check)
- [ ] auto-reply enabled (external senders only) with the doc's text

## 3. Rehearsal — one real payment (the Phase 2 gate)

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
   - [ ] NO activation; email with the fresh account arrives automatically
   - [ ] the old VA is voided; the corrected transfer activates it

If anything in 3/4 doesn't happen: the worker logs are where the diagnosis
lives (`[docoga-*]` lines), and the KV record (`team:*`, `inv:*`) shows the
state. Reply in the session with the error and the state — that's the whole
protocol.

## 4. Two friendly teams (the Phase 3 exit gate)

Two real teams (your own businesses/contacts, **with permission, no cold
outreach** per the groundwork) complete buy→use with **zero owner touches** —
you watch the KV/emails, you don't intervene. One of them can be the
rehearsal team from step 3 if it's a genuine second business of yours.

- [ ] team A: create → sign in → pay → branded docs → (owner) invite a seat
- [ ] team B: same
- [ ] you replied to zero customer messages; every state change was automatic

## 5. Then: Phase 5 (publish) — needs your §11 decisions

Flip the Business card from "launching" to live with the price. The open
owner questions are in `docs/BUSINESS_TIER_RESEARCH.md` §11 (refund window,
published entry number, named contact, SLA capacity, quarterly option,
discovery). The 14-day refund is still PROPOSED, not promised, everywhere —
a test guards it.

**Waitlist launch email** — the list lives in KV as `bizwait:{email}` (one
JSON value per person: email/company/segment). Read it in the Cloudflare KV
dashboard (by design there is no public read endpoint) and email each person.
Copy (edit the price line to whatever §11 #3 decides):

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

Send it as a plain personal email (or your mail tool's list) — the list will
be small at first. If it's grown past ~20 names by then, tell the session and
we'll add a secret-gated notify endpoint (the dossier deliberately kept the
list read-only in v1).

## Rollback

Everything deployed here is a strict forward superset of what's live; retail
(Oga Pass) is untouched by construction (the invoice branch runs before the
retail gate and pass references never match invoices). To roll back:
re-deploy the previous worker/site versions (wrangler keeps them). No data
migrations were done — the new KV keys (`teaminv:*`, `team:*:usage:*`,
`renewal_*` fields) are additive.
