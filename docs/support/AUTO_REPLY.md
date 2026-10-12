# business@docoga.com.ng — fully-autonomous support lane (one-time setup)

> Phase 3 (11 Oct 2026) → **redesigned 12 Oct 2026 per owner instruction:
> no human interaction, no replying to emails.** The lane is fully
> autonomous — like buying the Oga Pass, nobody is meant to reach the owner
> by hand, before OR after paying. What the mailbox does with zero owner
> touch:
>
> 1. Every inbound mail is **archived silently** — a copy lands in the
>    owner's Gmail. A record, never a task: FLW/CAC/provider notices
>    addressed to business@ and dispute evidence stop being silently deleted.
> 2. Qualifying mail (external, human, not a bounce/list/auto-responder)
>    **auto-replies AS business@** with the exact self-serve text below.
>
> Cost: **₦0** — built only from infrastructure DocOga already runs
> (Cloudflare free plan + Brevo free tier). No mailbox vendor, no trials,
> no auto-conversions, nothing to read, nothing to answer.
>
> **How we got here (12 Oct 2026):** the Phase-3 doc assumed a "free Brevo
> mailbox" — no such product exists (Brevo is a send-only platform; verified
> against their docs + 2026 free-email guides). The verified fallback was
> **Zoho Mail Free** — its signup is BLOCKED for this account ("unable to
> create your account right now": Zoho's generic queued/spam-filtered
> account-creation message, reported worldwide; the
> `support-az@zohocorp.com` address printed on that screen is a dead
> mailbox — bounced on send 12 Oct). Official channels if the Zoho route is
> ever revisited: the Zoho Cares portal (help.zoho.com → "Submit a request")
> and @ZohoCares on X. Rather than make a region-gated third party the
> critical path, the lane is self-built. Zoho stays as the zero-code
> alternative if its signup ever clears — it is no longer on the critical
> path.

## Domain state (LIVE — post go-live, direct DNS queries 12 Oct 2026)

| Record | Value |
|---|---|
| NS / SOA | `beau./elly.ns.cloudflare.com` — DNS lives in the **Cloudflare dashboard**; every edit happens there (never the registrar) |
| A | `104.21.33.145`, `172.67.146.104` — Cloudflare proxy (the site) |
| MX | CF routing: `route1.mx.cloudflare.net` (21), `route3.mx.cloudflare.net` (34), `route2.mx.cloudflare.net` (71) |
| TXT (apex) | **SPF (merged, live-verified 14:50):** `v=spf1 include:spf.brevo.com include:_spf.mx.cloudflare.net ~all` + `brevo-code:e5a4c9356a5a68c472613f64e4237b80` (Brevo domain verification) |
| DKIM | `brevo1._domainkey` / `brevo2._domainkey` (CNAME → dkim.brevo.com — the worker's magic links send DKIM-signed) + `cf2024-1._domainkey` (CF routing — signs the lane's reply()) |
| DMARC | `_dmarc = v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com` (monitoring only — leave as-is) |

## Live status (12 Oct 2026 — deployed + both test mails pass)

The lane is **LIVE**. Go-live was walked with the owner on the phone, entirely
in the Cloudflare dashboard — **the owner has no wrangler machine, so the
dashboard code-paste below is the canonical owner deploy path** (the CLI
commands in Step 2 remain the desktop alternative).

- **07:05** Onboard Domain → Activate. CF added the 3 MX + `cf2024-1._domainkey`
  + the apex SPF; the apex SPF was then merged (one record, both senders).
- **07:32** Destination `azanijohn2017@gmail.com` verified (the archive target).
- **12:53** Worker `docoga-support-mail`: Workers & Pages → Create application →
  "Start with Hello World!" → name it `docoga-support-mail` → Deploy → the "…"
  overflow → **Edit code** → replace ALL the placeholder with
  `worker/support-mail/index.js` → Save and Deploy → Settings → Variables and
  Secrets: variable `ARCHIVE_TO`, secret `BREVO_API_KEY` (a FRESH Brevo v3 key —
  Brevo → ⚙ Settings → SMTP & API; direct link `app.brevo.com/settings/keys/api`).
  Code verified live via the editor test panel: the response is
  `Error: No fetch handler!` — the expected answer for an email-only worker
  (no web route by design; the public URL's 1101 is that, not a fault).
- **13:54** Routing rule: `business@docoga.com.ng` → Send to a Worker →
  `docoga-support-mail`.
- **14:24 Test 1** (subject "Test 1 - normal mail"): archive copy in Gmail +
  auto-reply FROM business@, **threaded** under the original (CF native
  `reply()` used the sender's valid DMARC — the anti-spoof gate is satisfied),
  verbatim contract copy, landed in **Primary** (not spam) within ~3 min.
- **14:37 Test 2** (subject "Mail Delivery Failure"): archive copy only, no
  auto-reply — the subject guard works. Activity log: 2 inbound + 1 outbound
  (the reply); zero outbound for Test 2.

Remaining 1-minute checks (non-blocking): the pinned **Catch-all** routing
rule's action (it should reject unmatched addresses — otherwise
random-address spam archives into the owner's Gmail) and CF usage after the
tests (settles whether `reply()` bills as paid "Email Sending"; the Brevo
fallback makes the answer irrelevant to ₦0).

The steps below are the original walkthrough — kept for a future
re-provision (or the desktop/wrangler alternative).

## Step 1 — Cloudflare Email Routing (dashboard, ~5 min)

1. *Compute → Email Service → Email Routing → Onboard Domain* →
   `docoga.com.ng`. CF auto-adds: MX (`route1/2/3.mx.cloudflare.net`), the
   routing DKIM (`cf2024-1._domainkey`), and an SPF TXT at the apex.
2. **Edit that apex SPF so it covers BOTH senders (exactly one record):**
   `v=spf1 include:spf.brevo.com include:_spf.mx.cloudflare.net ~all`
   (Brevo = the worker's transactional sender; CF = the lane's auto-reply
   sender. Leave the `brevo-code` TXT and `_dmarc` untouched.)
3. *Destinations → Add* → `azanijohn2017@gmail.com` → **Verify** (the silent
   archive target — verification is a one-time code to that Gmail).

## Step 2 — deploy the lane worker (~5 min, on the machine with wrangler)

```
npx wrangler secret put BREVO_API_KEY --config worker/support-mail/wrangler.toml
npx wrangler deploy --config worker/support-mail/wrangler.toml
```

- `BREVO_API_KEY` = the SAME key `docoga-pass` already uses. It is consumed
  ONLY if Cloudflare's native `reply()` fails or is switched off
  (`USE_CF_REPLY=off` var) — the auto-reply then goes out through Brevo's
  transactional API (300/day free, same key pattern as the magic links), so
  the reply is delivered **either way**.
- Then, in the dashboard: *Email Routing → Custom addresses* →
  `business@docoga.com.ng` → **Route to: Worker → `docoga-support-mail`**.

## Step 3 — prove it (2 test mails + 1 check)

1. From a personal address → business@docoga.com.ng, any subject. Expect
   BOTH: (a) a copy in your Gmail (archive), (b) an auto-reply **FROM
   business@** with the text below, threaded under your message.
2. A mail whose subject is "Mail Delivery Failure" (any body) → archive copy
   ONLY, no auto-reply (the guard, proven live).
3. mxtoolbox free SPF check on the merged record.

## The auto-reply text

**Single source of truth: `worker/support-mail/index.js` → `REPLY_TEXT`.**
(Keep the site and this doc aligned with it; the unit test locks the
contract.)

```
Subject: Received - DocOga Business is fully self-serve

Hi,

Thanks for writing to DocOga Business.

This is an automated inbox - DocOga is built to be fully self-serve, and
most things are faster done than explained:

- Pay for your team (bank transfer or card): docoga.com.ng -> Set up your
  team, or the Team dashboard once you've signed in
- Your team dashboard (seats, branding, invoices, printable PDF):
  docoga.com.ng -> Team dashboard (sign in with your work email - magic link,
  no password)
- A payment that already went through: don't re-send the transfer - the
  system verifies the exact amount automatically and your team activates on
  its own. If the amount was wrong, the system already emailed you a fresh
  account number for the correct amount.
- Everything else: the Business FAQ - docoga.com.ng/support

Prefer to talk it through? The green WhatsApp button on docoga.com.ng
reaches the support line directly.

Every message you send is kept on record.

DocOga - Abuja, Nigeria
DocOga provides self-help document templates; it is not a law firm and does
not provide legal advice.
```

**Honesty contract (mandate: no deceptive copy):** this text makes NO
human-response promise (it points at the WhatsApp float as the optional
human valve — a channel, not a commitment). The old "a real person answers within 1 working
day" promise was on the live site in four places (support.html ×3, the
team-dashboard support card in index.html) plus the FAQ doc — all removed in
the same commit that built this lane. Whatever the site or the auto-reply
says, the machine must actually deliver it; `tools/tests/emailworkertest.mjs`
locks the copy to that contract.

## Replying by hand is not part of this lane

The auto-reply is the entire lane. If a recorded case ever needs a human
answer (e.g. a refund decision made from the archive), `CANNED.md` is the
starting point and the answer goes out off-lane as the owner — an owner
decision, not a step of the system. The WhatsApp float is DocOga's **general support channel — pre- and
post-purchase** (owner clarification, 12 Oct); nothing in this lane touches
it. What does NOT change: the Business *purchase flow* is pay-first and
self-serve — nobody needs to WhatsApp to buy (the Business card has no
WhatsApp CTA, Phase 0), and the support page still tells Business teams
everything is self-serve first.

## Problem-reporting channel (owner decision, 12 Oct)

**No "Report a problem" form.** Owner: "Any problems can be sent to the
WhatsApp support" — the general float (pre- and post-purchase) IS the human
valve for the rare case the self-serve flow can't fix. Implementation
consequence: the auto-reply carries ONE optional line pointing at the green
button ("Prefer to talk it through? The green WhatsApp button on
docoga.com.ng reaches the support line directly") — no `wa.me` link or raw
number inside the email (dossier invariant: no WhatsApp links in Business
replies), no response-time promise, and nothing in the lane *requires*
WhatsApp (the pay-first self-serve flow is untouched; the float is an
option, not a step).

## Rejected alternatives (12 Oct research — verified per source, to vendor docs)

- **Zoho Mail Free** — the only "real mailbox" free option; signup blocked
  for this account/region (header). Kept as the zero-code alternative, OFF
  the critical path.
- **Brevo "mailbox"** — does not exist (send-only platform).
- **mail.com free** — generous (65GB) but NO custom domain: shared domains
  like @consultant.com. Fails the address itself.
- **ImprovMX free** — forwarding only, 500 emails/day cap, no SMTP send and
  no auto-reply on free → strictly dominated by Cloudflare Email Routing.
- **Google Workspace / Microsoft 365** — no free custom-domain tier
  (trials only — trial clocks violate the no-trials rule).
- **Proton Mail / Tuta free** — custom domain requires a paid plan.
- **Neo Mail** — 15-day trial clock.
- **Self-hosted mail on a free VPS (Oracle Always Free etc.)** — free-tier
  accounts CANNOT open the service request required for PTR/rDNS records
  (paid/PAYG only), and cloud IP ranges are refused by major receivers for
  mail anyway → deliverability dead on arrival; plus an owner-maintained
  mail server breaks the autonomy mandate.
- **Nigerian "free mailbox with hosting" bundles** — the mailbox is free
  because the hosting isn't.
- **Zoho via VPN / other region** — ToS risk + ongoing regional mismatch;
  not a mandate-compliant path.
