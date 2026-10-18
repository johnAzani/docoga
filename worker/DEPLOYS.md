# Worker deploy log

- 17 Oct 2026, 5:35pm WAT — published the owner dashboard + attribution worker (code from 12 Oct 18:37 and 16 Oct had never been deployed; live worker answered `not found` on /admin/login).
- 17 Oct 2026, 6:05pm WAT — ledger cross-check fixed: compares codes minted since a pinned baseline with sales counted since it (the first open had rung a false "8 stored, 0 counted" alarm). Run 39049825243 → PR #79.
- 17 Oct 2026, ~10:00pm WAT — Social board (`/admin/social`, `/admin/social/run`) + Website visits (`/admin/site`); the deploy now forwards `GH_DISPATCH_TOKEN`, `CF_ANALYTICS_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` into the worker so neither panel needs a tap.
- 18 Oct 2026, morning WAT — `GET|HEAD /m/<name>.<ext>`: short-lived public media from KV (manifest + ≤20 MiB parts, TTL, Range) so the Facebook lane can publish the Instagram Reel by `video_url` on the Instagram-Login token — the third door, needed because Facebook refused the Page↔Instagram link twice (16 and 18 Oct). Pushed with `[deploy-pass]`.
