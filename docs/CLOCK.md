# The DocOga clock — every lane rings on time (17 Oct 2026)

## What was wrong

Every "best time to post" in this repo is a `cron:` line in a GitHub workflow. Since
**26 Aug 2026** GitHub's `schedule` trigger has not been a clock for private
repositories: the event arrives hours late or not at all (GitHub community
discussions #207346, #207370, #201472 — `created_at == run_started_at`, so it is the
event that never comes, not a busy runner; GitHub's docs call `schedule` best-effort,
and under load a run "can be dropped entirely").

Measured on this repository, 13–17 Oct 2026 (the Actions API, `event=schedule`):

| Lane | Crons / day | Runs that actually arrived | When |
|---|---|---|---|
| Telegram (09:00 WAT) | 1 | 1 | 13:05–16:41 WAT |
| Facebook (09:30 WAT) | 1 | 1 | 14:22–14:52 WAT |
| Threads (07:20 / 13:10 / 20:10) | 3 | **1** | 14:30–15:00 WAT |
| Instagram (07:10 / 13:10 / 19:10) | 3 | **1** | 11:33–14:41 WAT |
| Brain replies (11:40 / 14:40 / 20:40) | 3 | **1** | 14:54–23:11 WAT |
| YouTube Short (Mon–Fri 18:00) | 5 / week | **1 in 4 weekdays** | 20:47 WAT |
| YouTube boost (19:20) | 1 | **0** | — |

Roughly a third of the planned posts went out, almost all of them in the dead
afternoon, none at the researched peaks (07:00–08:00, 12:30–14:00, 19:00–20:30 WAT).
`workflow_dispatch`, by contrast, starts within seconds, every time.

A second, quieter risk sat underneath: a private repository on the free plan has
**2,000 Actions minutes a month**, and when they run out the lanes stop without a
word. The week of 10–17 Oct used ~480 minutes — a 2,000-minute month — and ~70% of
it was the `Verify` gate and the Cloudflare build check running on every push to
every branch, on every pull-request event, and again on every automated card and
ledger commit.

## What changed

1. **`workers/clock/` — a Cloudflare Worker** (Workers Free: one of the plan's five
   Cron Triggers, 10 ms of CPU per tick, ₦0). Every five minutes it reads
   `schedule.json` and calls
   `POST /repos/johnAzani/docoga/actions/workflows/<file>/dispatches` for each lane
   whose cron fired in the last five minutes. Windows are `(tick−5, tick]` on
   Cloudflare's *scheduled* time, so each slot is rung exactly once.
2. **`tools/clock_schedule.py`** builds that table **from the workflows' own `cron:`
   lines** — there is no second schedule to keep in step. `emit` writes the JSON (a
   test fails if the committed copy is stale), `today` prints the day in Lagos time,
   `check` is the CI guard. Threads is dispatched with the `slot` its cron stands for;
   Instagram with `clock=true`, which puts its slot gate into scheduled mode (one post
   a day, in the hour the scorecard chose).
3. **The lanes keep their `schedule:` blocks** as a backstop. For once-a-day lanes a
   late backstop is harmless (the duplicate guards see today's post). For Threads —
   where a late `slot: auto` run would call 16:00 UTC "evening" — a `gate` job asks
   `tools/clock_guard.py` whether the clock dispatched the lane in the last 36 h and
   stands the cron down if so (a skipped job, a green run). If the clock is idle or
   GitHub cannot be asked, the cron posts as before. **A monitor is never the reason a
   post was missed.**
4. **The heartbeat** (`automation-heartbeat.yml` → `tools/automation_heartbeat.py`, 9:00pm WAT daily) counts `workflow_dispatch`
   runs as the cadence being kept and prints one `CLOCK=on-duty|idle` line.
5. **Minutes budget**: `Verify` runs on pull requests and on pushes to `main` that
   are not the lanes' own bookkeeping (`logs/**`, `assets/**`, `site/social/**`,
   `site/videos/**`, `brain/**`); the Cloudflare build check only when something the
   build consumes changed. Both cancel superseded runs. Expected spend after this:
   ~20 min/day for the lanes + Deep-Dive days ≈ 700–900 min/month, inside the 2,000.
6. **`.github/workflows/deploy-clock.yml`** deploys the Worker on every push to
   `main` that touches the clock, its table or any workflow's cron, forwards the
   `GH_DISPATCH_TOKEN` repository secret into the Worker, and probes the live Worker.

## The one thing the owner does (once)

The Worker needs a GitHub token to ring the doorbell. GitHub does not let a
repository mint its own, so this is a one-time mint — and, per the owner's rule, it
is minted **with everything, never again** (`docs/TOKENS.md` §8):

1. `github.com/settings/personal-access-tokens/new` → **Token name** `docoga-clock`
   → **Expiration: No expiration** → **Repository access: Only select repositories →
   johnAzani/docoga** → **Permissions → Repository permissions**: Actions **Read and
   write** · Contents **Read and write** · Issues **Read and write** · Pull requests
   **Read and write** · Secrets **Read and write** · Variables **Read and write** ·
   Workflows **Read and write** (Metadata is read-only automatically) → **Account
   permissions**: Plan **Read-only** → **Generate token** → copy it.
2. `github.com/johnAzani/docoga/settings/secrets/actions/new` → **Name**
   `GH_DISPATCH_TOKEN` → **Secret**: paste → **Add secret**.

Nothing else. `deploy-clock.yml` runs daily and on the next push; it forwards the
secret into the Worker, and from the next five-minute tick every lane is on time.
`https://docoga-clock.johnazani.workers.dev/` answers `"token": "present"` when it is.

## Switches

| Where | What |
|---|---|
| Cloudflare → Workers → docoga-clock → Settings → Variables → `CLOCK=off` | Pause every dispatch (GitHub's own cron remains) |
| Revoke the token at `github.com/settings/personal-access-tokens` | Same effect, permanently; heartbeat says `CLOCK=idle` the next night |
| `python3 tools/clock_schedule.py today --day 2026-10-19` | See the day's plan in Lagos time |

## Why not …

* **A sleeping Actions job that dispatches the next slot** — the runner minutes
  count while it sleeps: 1,440 min/day against a 2,000 min/month plan.
* **Removing `schedule:` from the lanes** — the backstop costs nothing and keeps the
  heartbeat's cadence reading honest; the guards and the Threads gate make a double
  arrival harmless.
* **GitHub App instead of a PAT** — more taps for the owner, no gain for one private
  repository.

## The health page feeds the owner dashboard

`GET https://docoga-clock.johnazani.workers.dev/` also returns `entries_table` — every
row of `schedule.json` (workflow, cron, dispatch inputs; nothing secret). The owner
dashboard's **Social** tab (`docoga-pass` → `/admin/social`, `ADMIN_DASHBOARD.md` §5a)
reads it so the plan it shows is, by construction, the plan this clock rings.
