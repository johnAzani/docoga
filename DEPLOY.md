# DocOga — Zero-to-Live Deployment Guide (₦ budget: under ₦3,000)

You need: your phone or a laptop, your BVN/bank details, and about 60 minutes.
No coding knowledge required — the app is already built (`index.html`).

---

## Step 1 — Buy the domain (~₦1,500–3,000)

Cheapest first-year options (fits the ₦10,000 budget):
- **docoga.com.ng** or **docoga.xyz** — usually ₦1,500–3,000 first year at
  Truehost.ng, Whogohost.com, or Namecheap.com *(docoga.com is also available
  but costs ~₦13,000–16,000 — upgrade later from revenue).*
- Create an account → search the domain → pay via card/transfer/USSD.

> Budget check: domain ≈ ₦2,000 → remaining budget ≈ ₦8,000 (keep as buffer).

## Step 2 — Deploy the site FREE on Cloudflare Pages (10 minutes)

**Recommended — GitHub → Cloudflare Pages (auto-deploy on every push):**
Follow `GITHUB-CLOUDFLARE.md`. The three settings that matter:

| Setting | Value |
|---|---|
| Production branch | `main` |
| Build command | *(leave blank — there is no build step)* |
| Build output directory | **`site`** |

Then in the Pages project → **Custom domains**, add `docoga.com.ng` and
`www.docoga.com.ng`. Free SSL is issued automatically.

**Quick alternative — direct upload (no GitHub, but no auto-deploy either):**
1. `dash.cloudflare.com` → **Workers & Pages → Create → Pages → Upload assets**.
2. Drag the **`docoga/site` folder** — it contains ONLY the files meant for the
   public web.
3. Or from the command line: `wrangler pages deploy site --project-name=docoga`.

> **🔒 SECURITY — read this twice:** Only ever publish the `site` folder.
> The files at the `docoga` root level — `unlock-codes.txt`, `PLAN.md`,
> `DEPLOY.md`, `AUTOMATE.md` and the `worker/` folder — are **private business
> documents**. `unlock-codes.txt` is ₦374,000 of sellable inventory and
> `worker/index.js` must be edited to contain no secrets anyway. Uploading them
> publicly would leak your entire code inventory. In Cloudflare Pages this is
> controlled by the **Build output directory** field: it must say `site`, never
> blank and never `/`.

> **Netlify is no longer used.** `netlify.toml` was removed from the repo on
> 3 Oct 2026 and the migration steps (including disconnecting Netlify's GitHub
> App, which was still building this repo) are in `GITHUB-CLOUDFLARE.md`.

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
const SITE_URL = "https://docoga.com.ng";     ← your real domain
const WORKER_URL = "https://docoga-pass.yourname.workers.dev"; ← after AUTOMATE.md Part 1
```

Also set `WORKER_URL` at the top of `success.html` (same value).

Save, commit and push — Cloudflare Pages redeploys `main` automatically (or
`wrangler pages deploy site --project-name=docoga` if you need it now). That's
it — buyers now pay and receive their pass instantly, with zero work from you.

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
> Open docoga.com.ng → tap 'FREE PLAN' at the top → paste the code → Activate.
> Clean documents unlocked for 30 days. Tell your friends!"

## Step 6 — Get found by Google (same day)

1. Google Search Console (`search.google.com/search-console`) → add your
   domain → verify (Cloudflare makes this one click).
2. Submit the sitemap: `https://docoga.com.ng/sitemap.xml` (already included in
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

### Domain — docoga.com.ng (decision 18 Sep 2026; DNS moved to Cloudflare, verified 3 Oct 2026)
- Registrar: GO54/WhoGoHost (panel.whogohost.com) — NGN3,000 year 1, NGN7,200/yr renewal (due Sep 2027) — keep account funded / auto-renew ON. **Set a phone reminder for Aug 2027.**
- **Current DNS (verified by lookup on 3 Oct 2026):** `docoga.com.ng` and `www.docoga.com.ng` both resolve to Cloudflare anycast — `104.21.33.145`, `172.67.146.104`, and `2606:4700:3033::ac43:9268` / `2606:4700:3034::6815:2191`. HTTPS is issued by Cloudflare.
- The original Netlify records (`A @ -> 75.2.60.5`, `CNAME www -> docoga.netlify.app`) are **no longer in use** and should be deleted from the registrar panel if they are still there.
- Re-check any time with: `python3 -c "import socket;print(socket.getaddrinfo('docoga.com.ng',None))"` — Cloudflare ranges are `104.16-31.x.x`, `172.64-71.x.x` and `2606:4700::/32`.
