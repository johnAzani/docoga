# docoga-clock

The Cloudflare Worker that rings every scheduled lane of this repository on time.
Design, measurements and the owner's one-time token: `docs/CLOCK.md`.

* `index.js` — the five-minute tick, the cron matcher (mirrored in
  `tools/clock_schedule.py`), the GitHub `workflow_dispatch` call.
* `schedule.json` — generated from `.github/workflows/*.yml` by
  `python3 tools/clock_schedule.py emit`; never edit by hand.
* `wrangler.toml` — one Cron Trigger (`*/5 * * * *`), the `GH_REPO` var.
* Health: `https://docoga-clock.johnazani.workers.dev/` → `{"token": "present"|"missing", "due_this_tick": [...]}`.
* Pause: Cloudflare dashboard → docoga-clock → Settings → Variables → `CLOCK = off`.

Deployed by `.github/workflows/deploy-clock.yml` on every push to `main` touching
this folder, the table, or any workflow's cron; it also forwards the
`GH_DISPATCH_TOKEN` repository secret into the Worker (token added 17 Oct 2026, 16:47 WAT).
