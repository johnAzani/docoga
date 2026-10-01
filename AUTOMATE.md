# DocOga — Automatic Instant Code Delivery (no CAC needed)

> **✅ DECISION (18 Sep 2026): Path B chosen — Flutterwave Individual account.**
> Confirmed by Flutterwave's own docs: *"As a Nigerian merchant, you can signup
> as an Individual, a Registered Business, or Other Entity"* — no CAC needed
> for the Individual type. Follow Part 1, then Part 2B below.

This guide removes the human from the loop. A buyer pays → a code is issued and
delivered **instantly**, 24/7, even while you sleep. All on free tiers.

**What a webhook is (plain English):** when a payment succeeds, the payment
company's server automatically phones *your* little server (a Cloudflare Worker)
with the receipt. Your Worker checks the amount, mints a unique code, and
emails/shows it. No WhatsApp, no typing, no delay.

---

## Choose your path

| | Path A — Selar + Zapier | Path B — Flutterwave (unregistered) | Path C — Paystack |
|---|---|---|---|
| CAC needed? | **No** | **No** (unregistered/sole-proprietor account; availability shown at signup) | Yes |
| Buyer experience | Pay on Selar → code arrives by email | Pay → auto-redirect → **code on screen + auto-activated** | Same as B |
| Automation | Zapier fires on "New Sale" → Worker | Redirect + verify (webhook optional) | Redirect + verify |
| Free capacity | ~50 sales/month (Zapier free = 100 tasks) | ~1,000 sales/day (Worker/KV limits) | Same |
| When to use | Now, keep Selar | Now, best UX | After CAC |

You can run A now and switch to B/C later — the same Worker serves all three.

---

## Part 1 — Deploy the Worker (once, ~20 minutes, all paths)

1. Create a free **Cloudflare** account → dashboard.
2. **Storage & Databases → KV → Create namespace** → name it `docoga`.
3. **Workers & Pages → Create → Worker** → name `docoga-pass` → Edit code →
   paste the entire contents of `worker/index.js` → Deploy.
4. In the Worker's **Settings → Variables and Secrets**:
   - Bind the KV namespace, variable name exactly: `KV`
   - Add secrets (encrypted):
     - `ISSUE_SECRET` = any long random string you invent (Path A)
     - `FLW_SECRET_KEY` = Flutterwave **Secret key** (Path B)
     - `FLW_WEBHOOK_HASH` = Flutterwave webhook hash (optional)
     - `BREVO_API_KEY` = free key from **brevo.com** — PRIMARY email provider
       (300 emails/day, no card, never expires; the worker also accepts
       `SMTP2GO_API_KEY` then `RESEND_API_KEY` as fallbacks — see sendMail())
   - Add plain variables:
     - `PROVIDER` = `flw` (or `paystack` on CAC day)
     - `SITE_URL` = `https://docoga.com.ng`
     - `MAIL_FROM` = `DocOga <passes@docoga.com.ng>` (the sender address verified in Brevo)
5. Copy your Worker URL, e.g. `https://docoga-pass.yourname.workers.dev`
6. Test it: open `https://your-worker.workers.dev/` in a browser →
   you should see `{"ok":true,"service":"docoga-pass"}`.
7. Edit `success.html` (set `WORKER_URL`) and `index.html` (set `WORKER_URL` in
   the CONFIG block) → redeploy the site. Done — the automation layer is live.

**Email delivery note:** Resend's test sender (`onboarding@resend.dev`) can only
email your own account address. To email *buyers*, verify your domain in Resend
(free: add 2 DNS records) and set `MAIL_FROM`. Until then, Path B still works
perfectly because the code is shown **on screen**, not by email.

---

## Part 2A — Selar → Zapier → Worker (no CAC)

1. In Zapier, create a Zap:
   - **Trigger:** Selar → **New Sale** (connect your Selar account)
   - **Action:** Webhooks by Zapier → **POST**
     - URL: `https://your-worker.workers.dev/issue`
     - Headers: `X-DocOga-Key` = your `ISSUE_SECRET`
     - Payload type: JSON. Body: `{ "email": "{{map the buyer email field}}" }`
       (map the buyer's email from the Selar trigger; also map the sale/order id
       as `ref` if available)
2. Turn the Zap on. Every Selar sale now mints + emails a code automatically.
3. Optional extra action: "Email by Zapier" using the `code` from the Worker's
   response — a backup email channel that needs no domain verification.

**Test it:** buy your own ₦2,000 pass (Selar charges you back as payout), or
temporarily price a test product at ₦100 and watch the Zap fire.

## Part 2B — Flutterwave unregistered account (no CAC, best UX)

1. Sign up at **flutterwave.com** → during onboarding choose the
   **unregistered business / sole-proprietor** account type if offered for
   Nigeria (BVN + personal bank account + valid ID; your BVN name, ID name and
   bank account name must match).
2. Dashboard → **Settings → API** → copy your **Secret key** → put it in the
   Worker as `FLW_SECRET_KEY`. Copy the **Webhook hash** → `FLW_WEBHOOK_HASH`.
3. Dashboard → **Payment Links** → create: name "DocOga Oga Pass — 30 Days",
   amount ₦2,000, currency NGN, **Redirect URL:** `https://docoga.com.ng/success.html`
4. (Optional) Set the webhook URL to `https://your-worker.workers.dev/flw-webhook`
   — belt and braces; redirect+verify alone is enough.
5. Update the app: set `SELAR_URL` in `index.html` CONFIG to your Flutterwave
   payment link (the button label says Selar — I can rename it "Pay" when you
   confirm which you use).

**Buyer flow:** pay (card/transfer/USSD) → Flutterwave redirects with
`?tx_ref=...` → `success.html` asks the Worker to verify → code appears on
screen AND is auto-activated AND emailed. Zero seconds, zero humans.

## Part 2C — After CAC registration (Paystack)

Same as 2B but with Paystack: set `PROVIDER`=`paystack`,
`PAYSTACK_SECRET_KEY` secret key; Paystack Page's callback URL =
`https://docoga.com.ng/success.html`. On-site checkout integration (embed
Paystack's inline popup directly in DocOga) is the next upgrade after that —
ask me and I'll build it.

---

## Security rules (important)

- **Never** put `FLW_SECRET_KEY` / `PAYSTACK_SECRET_KEY` in index.html,
  success.html, or any file that goes to the browser. They live only in the
  Worker's encrypted secrets.
- The `/issue` endpoint only accepts requests carrying your `ISSUE_SECRET`
  header — only your Zapier action knows it.
- Codes are 12 random characters from a 32-character alphabet (≈ a
  trillion-trillion combinations) — guessing is not practical.
- All endpoints are idempotent: a double webhook or page refresh issues only
  ONE code per payment reference.
- Your 200 offline codes in `unlock-codes.txt` keep working exactly as before —
  the site checks them locally first, then falls back to the Worker online check.

## Free-tier ceiling (what "exponential" costs before it costs money)

| Layer | Free allowance | Enough for |
|---|---|---|
| Cloudflare Workers | 100,000 requests/day | ~50k sales/day |
| Cloudflare KV | 1,000 writes/day | 1,000 sales/day |
| Resend email | 3,000/month (100/day) | 100 sales/day by email (screen delivery unlimited) |
| Zapier free | 100 tasks/month | ~50 sales/month — switch to Path B past that |
| Flutterwave/Paystack fees | ~1.5%–2% per transaction | comes out of the ₦2,000 |

When you outgrow these, the paid tiers are cheap and you'll have revenue —
that's what exponential growth looks like on a balance sheet.

## Troubleshooting

- `{"ok":true}` at the Worker root but `/verify` says "payment not found" →
  check `PROVIDER`, the secret key, and that the payment succeeded (not pending).
- Zapier didn't fire → check the Zap's task history; confirm the Selar trigger
  is connected to the right Selar account.
- Email not arriving → until your domain is verified in Resend, the
  `onboarding@resend.dev` sender only emails your own address. Verify the
  domain (2 DNS records) or rely on screen delivery (Path B).
- Buyer says code "invalid" → they must paste the FULL code including `OGA-`
  (dashes/case don't matter). Server codes need `WORKER_URL` set in index.html.
