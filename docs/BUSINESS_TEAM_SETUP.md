# Business team setup

**Since Phase 2 (11 Oct 2026) teams are self-serve:**
`docoga.com.ng/#business-setup` → pick a segment preset, seats and document
volume → the published formula shows the live annual price (VAT line-item) →
"Create my team" → magic-link email → sign in → **pay by bank transfer
(dynamic virtual account, auto-confirmed by webhook) or card/USSD** → the
team activates itself for 12 months. No owner step anywhere.

What the owner does: nothing per team, unless the customer writes an email
(support, §7.5). Watch the KV dashboard for `inv:*` records to see payment
state (`open` → `paid`, or `wrong_amount` — the wrong-amount case auto-issues
a fresh VA and emails the customer, no human reconciliation).

The manual procedure below is kept for **owner-side fixes and teams created
before Phase 2** (e.g. reviving a mis-created team, or adding a seat by hand
during a rollout issue).

## 0. One-time (first team only)

Set the worker secret, from a machine with Cloudflare auth:

```
cd worker && npx wrangler secret put TEAM_AUTH_SECRET
```

Use a long random string (e.g. `openssl rand -hex 32`). Without it, every
team endpoint fails closed with `503 team_auth_disabled` (by design).

## 1. Create the team

Replace `t1`, the slug, names, emails and dates:

| KV key | Value (JSON, unless noted) |
|---|---|
| `team:t1` | `{"id":"t1","slug":"firm","name":"Firm & Co","status":"active","expiry":"2027-10-11","plan":"starter"}` |
| `team:t1:seats` | `[{"email":"owner@firm.ng","name":"Owner Name","role":"owner","status":"active","invited_at":"2026-10-11T00:00:00Z"}]` |
| `seatidx:owner@firm.ng` | `t1` (plain text, not JSON) |
| `brand:t1` | `{"name":"Firm & Co","address":"12 Agents Rd, Abuja","logo":"data:image/png;base64,…","footer":"optional footer line"}` |

Rules:

- `id` is any short unique string (`t1`, `t2`, …).
- The owner seat MUST have `"role":"owner"` — only the owner can change the
  brand or invite/revoke seats. Every other seat: `"role":"member"`.
- `expiry` is the licence end date (`YYYY-MM-DD`); the team is live until
  23:59 UTC of that day. Expired team = sign-in blocked, branding off.
- `brand.logo` is optional but clean documents need it: PNG/JPG/SVG as a
  base64 **data-URI**, **≤25 KB**. Convert any image with a base64 encoder
  (the result must start with `data:image/png;base64,` / `…jpeg;base64,` /
  `…svg+xml;base64,`). The worker re-validates format + size on save, so a
  too-big logo is rejected with a 400, not stored.
- Members can be added here too (append to `team:t1:seats` + add
  `seatidx:{email}` = `t1`), or at runtime: the owner signs in and invites
  by email — the invite emails the magic link automatically.

## 2. Signing in (the team's experience — no password, no WhatsApp)

1. `docoga.com.ng` → pricing → Business card → **“Already part of a DocOga team?”**
2. Enter the seat email → a sign-in link is emailed (works once, 10 minutes).
3. Click it → signed in. Every one of the 10 tools now renders the **firm
   name + logo in place of the DocOga banner**, and the toolbar badge shows
   **TEAM · {firm name}**.
4. The Business card shows a signed-in chip with a **Sign out** button.

The session lasts 30 days on the device. The worker re-checks team status,
licence expiry and seat status on **every** API call — a revoked seat or an
expired team loses branding immediately, even with an old session token.

## 3. Owner capabilities (Phase 1)

- **Invite a seat** by email — magic link emailed (5 invites/day cap).
- **Revoke a seat** — access dies on the member's next call (immediate).
- **Update the brand** — name, address, footer line, logo (≤25 KB).
- See the seat list (members see only themselves).

## 4. What the webhook does (Phase 2)

On a signed `charge.completed` that matches an invoice reference:
- **correct amount** (naira or kobo — v4 reports minor units) → team `active`
  for +365 days, invoice `paid`, owner emailed "your team is live".
- **wrong amount** → no activation; the old VA is voided, a fresh one issued,
  the owner emailed the exact amount — automatically (§7.4).
- **duplicate** → idempotent no-op.
- The retail pass path is untouched (the invoice branch runs first on
  reference match; pass references never match invoices).
- **renewal invoice** (`kind:"renewal"`, Phase 4) → same activation; the new
  year **stacks on a future expiry** (early renewal loses no days) and the
  team's `renewal_base/vat/total` are refreshed to this invoice (renewal
  pricing = price at purchase, §6.4).

## 5. Autonomy lifecycle (Phase 4 — what the daily cron does, 07:00)

The `scheduled()` handler sweeps every team record each day (retail pass
reminders run first, then the business sweep). The lifecycle is:

```
active ──(T-90 / T-30 / T-7)──► reminder emails (deduped: rem90/rem30/rem7 on the team record)
active ──(expiry passed)──────► grace  (14 days: branding off, banner back, renewal self-serve)
grace  ──(grace_until passed)► free   (free tier; data retained 90 days: retire_at)
free   ──(retire_at passed)──► deleted (team/brand/seats/seatidx removed; invoices KEPT — tax)
```

Team-record fields the cron reads/writes (don't hand-edit mid-lifecycle):
`status` (`unpaid|active|grace|free`), `expiry`, `grace_until`, `retire_at`,
`rem90`/`rem30`/`rem7` (reset automatically at each (re)activation),
`renewal_base`/`renewal_vat`/`renewal_total` (price at purchase),
`usage100`/`usage150` (last month a 100%/150% overage email went out).

- **Renewal** is self-serve: `POST /business/team/renew` (owner; window =
  active-within-90-days, grace, or free) → renewal invoice at the purchase
  price via the same transfer/card machinery.
- **Volume meter (C8)**: `POST /business/team/usage` (best-effort monthly
  counter `team:{id}:usage:{yyyy-mm}`, capped at 2× the band; the print
  beacon is throttled to 10 min in the site and is fire-and-forget). The cron
  emails the owner at 100% and 150% of the monthly band, deduped per month.
  **Soft caps only — v1 never hard-cuts in-progress documents** (§6.4).

Owner intervention, if ever needed (e.g. a disputed expiry): edit the team
record's `status`/`expiry`/`grace_until`/`retire_at` directly — the cron
reasons only about those fields, and a renewal payment re-baselines the
reminder flags.

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `team_auth_disabled` (503) | `TEAM_AUTH_SECRET` not set (step 0). |
| `that email is not on a DocOga team yet` | `seatidx:{email}` key missing or wrong (emails are case-insensitive, stored lowercase). |
| `team not active` | `status` ≠ `"active"` or `expiry` passed. |
| `link expired or already used` | Magic links are one-time, 10 minutes — request a fresh one. |
| No email arrives | Check the worker's mail provider (Brevo/Resend) status + spam. The signup/state still works; email is a hand-off, not a gate. |
| Sign-in works but banner unchanged | `brand:t1` missing/empty, or the logo failed validation (400) when set. |
