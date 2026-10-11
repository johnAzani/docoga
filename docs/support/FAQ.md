# Business teams — FAQ (source of truth)

> Phase 3 (11 Oct 2026). This file is the **source of truth**; `site/support.html`
> is its public rendering. If you change the answers here, update the site page
> the same day (they must never disagree). Answers must stay TRUE as far as the
> build has gone — anything not yet built says "a human confirms", never a
> self-serve promise.

## What is this?

Support surface for Business teams (C11 in the dossier). Two lanes, by design:

1. **Self-serve** — the team dashboard (`index.html#team`): licence state, firm
   branding (owner edits), seats (invite/remove), invoices (open / save PDF),
   pay buttons when unpaid. Every action is a worker call; nothing here needs a
   human.
2. **Human, by email only** — `business@docoga.com.ng`. A real person (the owner)
   replies within 1 working day. No WhatsApp for Business teams: the dossier
   rule is *customers must not need to send a WhatsApp message*, and email is
   the written record that protects both sides (dossier §8).

## The answers (mirror of support.html)

| Question | Answer (current truth, 11 Oct 2026) |
|---|---|
| What does the licence include? | Annual, per-team: firm name + logo on every document, named seats, docs/month allowance, one annual invoice with VAT, automatic activation on payment. |
| How do I pay? | Dashboard → bank transfer (one-time virtual account, exact amount) or card/USSD via Flutterwave. Activation is automatic the moment the exact amount lands. |
| Wrong amount transferred? | Money is safe; licence does NOT activate; email with a fresh account number goes out automatically; old VA stops working. |
| Invite / remove members? | Dashboard → Team seats (owner only). Invite = magic link by email. Remove = one tap, documents already created are unaffected. **Adding seats beyond the licensed count mid-year = email business@** (human confirms — no self-serve seat purchase in v1). |
| Invoice as PDF? | Dashboard → Invoices → Open / Save PDF → print (or browser Print → Save as PDF). 12-month window in the dashboard; older = email business@. |
| Change name / logo? | Dashboard → Firm branding (owner only). Logo: PNG/JPG/SVG ≤ 25KB. Applies to documents from that moment. |
| Renewals? | Self-serve since Phase 4: we email at T-90/30/7 (deduped, most-urgent-first); renewal window opens 90 days before expiry; **Team dashboard → Renew** (transfer or card) at the purchase price; early renewal stacks on remaining days (none lost). Post-expiry: 14-day grace (branding paused, nothing deleted) → free tier with 90-day data retention → then team data deleted, invoices kept (tax). Renewing at any point restores everything. |
| Refunds? | Owner decides each case personally via business@. **No fixed window is promised publicly** (the 14-day window is PROPOSED in dossier §11 — pending owner decision; do NOT publish it until decided). |
| Where is my data? | Documents never leave the device (same as free). Team account stores firm name, branding, seat emails, invoice/payment status, hashed sign-in token. See privacy.html §5. |
| Response time? | Within 1 working day, Mon–Fri. Business = business@; Oga Pass individuals = WhatsApp. |

## Invariants (do not break in later edits)

- **No WhatsApp in the Business flow.** The wa button is for Oga Pass individuals only.
- **No 14-day refund promise** until the owner decides §11. If the owner picks
  14 days later: update this table + support.html in the same commit.
- **Mid-year seat adds stay human (email)** in v1. If a self-serve seat-purchase
  endpoint is ever built, that's when this row changes.
- **Never invent SLAs.** "1 working day" is a real commitment the owner makes —
  keep it, and keep the mailbox real (see AUTO_REPLY.md).
- **Renewals are self-serve since Phase 4** (`POST /business/team/renew`,
  window-grated: T-90 / grace / free; price at purchase, server-side). What
  stays human: refunds, mid-year seat adds, and anything the cron can't see
  (a customer writing in confused). The renewal price is the `renewal_total`
  stored on the team at (re)activation — no silent increases (§6.4); a price
  increase requires 60-day email notice with a lock-in option.
- **Lifecycle is fixed (cron, daily 07:00):** active → (expiry) grace 14d →
  free (90-day retention) → deleted (invoices kept). Don't hand-edit team
  status without understanding the `rem90/30/7`, `grace_until`, `retire_at`
  fields — the cron reasons about them (docs/BUSINESS_TEAM_SETUP.md).
