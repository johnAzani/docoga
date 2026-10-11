# business@docoga.com.ng — setup + auto-reply (one-time, owner)

> Phase 3 (11 Oct 2026). The whole Business support lane runs through this
> mailbox. It must be REAL before Phase 3's exit rehearsal (two friendly teams
> buy → use with zero owner touch needs a live inbox). Cost: ₦0 (free mailbox /
> free Brevo tier) — if it can't be done at ₦0, fall back to the existing
> personal email and relabel the site (support.html + privacy.html + footer).

## Step 1 — create the mailbox (pick one, both free)

1. **Brevo mailbox** (recommended — same dashboard as the transactional mail the
   worker already uses for magic links and receipts):
   brevo.com → *Email* → create mailbox on your domain `docoga.com.ng`.
   Follow their DNS steps (add the MX/SPF records at your domain registrar —
   the domain already points where the worker's email flow expects it).
2. **Or a free Google Workspace / Zoho free-tier mailbox** on the same domain,
   with the same MX + SPF DNS records.

Verify: send a test mail from a personal address to business@docoga.com.ng —
it must land, and the sender address in the header must show the domain.

## Step 2 — SPF sanity check (one-time)

The worker already sends mail through Brevo transactional (magic links,
wrong-amount notices). Make sure the domain's SPF TXT record includes BOTH
senders (Brevo's `include:brevo.com` or equivalent, plus whatever Step 1 added).
Run the result through a public SPF check (mxtoolbox free tier) — invalid SPF
is the #1 reason support mail bounces into a void nobody sees.

## Step 3 — auto-reply (set ON for Phase 3 launch, review after 30 days)

In the mailbox settings → Auto-responses, enable with **this exact text**:

```
Subject: Received — you'll hear from us within 1 working day

Hi,

Thanks for writing to DocOga Business.

This is an automatic reply — a real person (the owner) answers every email
within 1 working day (Monday–Friday), and the reply keeps your email thread,
so there's a written record of everything we agree.

Meanwhile, most things are self-serve and faster than waiting:

• Pay for your team (transfer or card): docoga.com.ng → Set up your team, or the
  Team dashboard once you've signed in
• Your team dashboard (seats, branding, invoices, PDF invoices):
  docoga.com.ng → Team dashboard (sign in with your work email — magic link,
  no password)
• Everything else: the Business FAQ — docoga.com.ng/support

If you're waiting on a payment that already went through (bank transfer), don't
re-send it — the system confirms the exact amount automatically and your team
activates on its own.

DocOga · Abuja, Nigeria
DocOga provides self-help document templates; it is not a law firm and does
not provide legal advice.
```

Notes:
- The auto-reply keeps the "no WhatsApp" promise intact and sets the SLA in
  writing (FAQ.md invariant: "1 working day" is a real commitment — the
  auto-reply is where it's made).
- Keep the auto-reply to **external senders only**, so the owner's own
  replies/threads don't trigger it.
- After 30 days of real traffic: read every thread, prune the FAQ rows that
  came up often, and decide whether the SLA held (dossier: the scoreboard is
  revenue, but the support lane is the thing that protects it).

## Step 4 — daily habit (2 minutes)

- Check the inbox twice a day (morning + after 15:00 WAT).
- Answer with CANNED.md as the starting point — edit, don't paste blindly.
- Any email that reveals a bug or a money problem (wrong amount that didn't
  trigger the auto-email, a team that didn't activate) → fix the product first,
  then reply (Rule Zero: the fix is the answer).
