# DocOga 🇳🇬 — The Oga of Documents

Free tenancy agreement, notice to quit, rent receipt and invoice generator
for Nigeria. Single-file static app — no build step, no server, 0 Naira/month to run.

## Structure
- `site/` — the website (the ONLY folder that is deployed publicly)
  - `index.html` — the entire app: 4 document tools + Oga Pass payment system
  - `success.html` — instant pass-delivery page (payment redirect target)
  - `privacy.html`, `terms.html`, `robots.txt`, `sitemap.xml`
- `worker/` — Cloudflare Worker for automatic pass-code delivery
  (deploy to Cloudflare Workers — NOT to the website)

## Deploy (Netlify)
1. Import this repository in Netlify (Add new site → Import from GitHub)
2. Settings are auto-detected from `netlify.toml` — nothing to configure
3. Every push to `main` deploys automatically

## Configuration
Edit the CONFIG block at the top of the `<script>` in `site/index.html`
(`PAYMENT_URL`, `SUPPORT_WHATSAPP`, `SITE_URL`, `WORKER_URL`, `ANALYTICS_ID`)
and `WORKER_URL` in `site/success.html`.

## Security — read this
- `unlock-codes.txt` is **gitignored** — it is paid-product inventory. NEVER commit it.
- Payment-provider secret keys live ONLY in Cloudflare Worker secrets. Never in this repo.
- Keep this repository **PRIVATE**.

© 2026 DocOga, Abuja, Nigeria. All rights reserved.
