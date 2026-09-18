# DocOga — Zero-to-Live Deployment Guide (₦ budget: under ₦3,000)

You need: your phone or a laptop, your BVN/bank details, and about 60 minutes.
No coding knowledge required — the app is already built (`index.html`).

---

## Step 1 — Buy the domain (~₦1,500–3,000)

Cheapest first-year options (fits the ₦10,000 budget):
- **docoga.top** or **docoga.xyz** — usually ₦1,500–3,000 first year at
  Truehost.ng, Whogohost.com, or Namecheap.com *(docoga.com is also available
  but costs ~₦13,000–16,000 — upgrade later from revenue).*
- Create an account → search the domain → pay via card/transfer/USSD.

> Budget check: domain ≈ ₦2,000 → remaining budget ≈ ₦8,000 (keep as buffer).

## Step 2 — Deploy the site FREE (10 minutes)

**Recommended — GitHub → Netlify (auto-deploy on every change):**
Follow `GITHUB-NETLIFY.md` — the repo-ready package is `docoga-github-repo.zip`
in this workspace (inventory files already excluded, `netlify.toml` included so
Netlify configures itself). Netlify publishes only the `site` folder.

**Quick alternative — Netlify Drop (no GitHub):**
1. Go to `app.netlify.com/drop` and create a free account.
2. Drag the **`docoga/site` folder** onto the page — it contains ONLY the files
   meant for the public web.
3. Your site is live on a free subdomain instantly.

> **🔒 SECURITY — read this twice:** Only ever upload the `site` folder.
> The files at the `docoga` root level — `unlock-codes.txt`, `PLAN.md`,
> `DEPLOY.md`, `AUTOMATE.md` and the `worker/` folder — are **private business
> documents**. `unlock-codes.txt` is ₦374,000 of sellable inventory and
> `worker/index.js` must be edited to contain no secrets anyway. Uploading them
> publicly would leak your entire code inventory.

**Best long-term — Cloudflare Pages:** create free account → Workers & Pages →
Create → Pages → Upload assets → drag the folder. Connect your domain in
Settings → Custom domains (free SSL).

Then in your domain registrar's DNS panel, add the CNAME/A records Netlify or
Cloudflare shows you. Done — `https://docoga.top` is live with a padlock.

## Step 3 — Set up Selar (30 minutes)

1. Create a free account at **selar.co** (works without CAC registration; they
   verify with BVN/bank details; payouts land in your bank account next day).
2. **Products → Create product:**
   - Name: `DocOga Oga Pass — 30 Days`
   - Price: `₦2,000`
   - Type: Digital download / "Link" product
   - File/Link: upload a simple TXT that says:
     *"Thanks for your purchase! To get your personal pass code instantly,
     send your payment receipt to WhatsApp: [your number]. Codes are usually
     delivered in under 10 minutes."*
   - Description: sell it (clean documents, unlimited for 30 days, priority support).
3. Copy the product link.

## Step 4 — Connect the app to your payment link & WhatsApp (5 minutes)

Open `index.html` in any text editor (even Notepad). Near the bottom, find the
CONFIG block and edit four lines:

```
const PAYMENT_URL = "https://your-flutterwave-payment-link";
const SUPPORT_WHATSAPP = "2340000000000";  ← your number, e.g. 2348012345678
const SITE_URL = "https://docoga.top";     ← your real domain
const WORKER_URL = "https://docoga-pass.yourname.workers.dev"; ← after AUTOMATE.md Part 1
```

Also set `WORKER_URL` at the top of `success.html` (same value).

Save, and re-upload/drag the folder to Netlify/Cloudflare again. That's it —
buyers now pay and receive their pass instantly, with zero work from you.

## Step 5 — Selling (the daily income part)

**Option 1 — Automatic (recommended):** set up instant code delivery with
webhooks — Selar→Zapier or Flutterwave, **no CAC needed**. The full guide is
`AUTOMATE.md`, and the server code is ready in `worker/index.js`. Buyers get
their code in seconds, 24/7, without you touching anything.

**Option 2 — Manual (works from day zero):**
1. When someone buys on Selar, you get an email/notification.
2. Open `unlock-codes.txt` — give them the next **unused** code (WhatsApp it).
   Tick the checkbox to mark it issued. One code per customer, always.
3. They paste the code into DocOga → banner disappears for 30 days.
4. You have 200 codes = ₦374,000 of inventory at ₦2,000/pass (Selar fees ≈ ₦26
   per pass, so ~₦374,000 net). Generate more codes anytime — ask me.

**Customer-service script (copy-paste):**
> "You're welcome oga! 🙏 Your DocOga Pass code is **OGA-XXXX-XXXX-XXXX**.
> Open docoga.top → tap 'FREE PLAN' at the top → paste the code → Activate.
> Clean documents unlocked for 30 days. Tell your friends!"

## Step 6 — Get found by Google (same day)

1. Google Search Console (`search.google.com/search-console`) → add your
   domain → verify (Cloudflare makes this one click).
2. Submit the sitemap: `https://docoga.top/sitemap.xml` (already included in
   the folder — it uploads automatically with the site).
3. Repeat for Bing Webmaster Tools.
4. **Analytics:** create a free Google Analytics 4 property
   (`analytics.google.com`) → copy your Measurement ID (looks like
   `G-XXXXXXXXXX`) → paste it as `ANALYTICS_ID` in the index.html CONFIG block
   → redeploy. Now you can see visitors, which tools they use, and where they
   come from — measure everything, guess at nothing.

## Step 7 — First 100 customers (Weeks 1–4, ₦0)

- WhatsApp: your status + 10 property/estate/tenant groups (don't spam —
  answer real questions, drop the link helpfully).
- Nairaland: genuine posts in Property section.
- TikTok/Reels: 30-second pidgin demos — "Landlord no gimme receipt. Make I
  show you wetin I use print am myself."
- Every buyer: save their number. They renew next year. That list is gold.

## When money starts flowing

| Milestone | Action |
|---|---|
| First ₦25,000 | Register CAC Business Name (~₦15–25k) — unlocks Paystack/Flutterwave checkout + trust |
| First ₦50,000/month | Ask me for **v2**: accounts, instant automated code delivery, tenancy-expiry reminders |
| Steady ₦100,000/month | Apply for Tony Elumelu Foundation grant (free) — traction screenshots ready |

## Troubleshooting

- **Preview looks unstyled in a sandboxed viewer** → that's normal; the real
  deploy renders fully.
- **Print button does nothing in preview** → printing is blocked in sandboxed
  previews; it works on the live site.
- **"Invalid code"** → check for typos; code is case-insensitive; dashes optional.
