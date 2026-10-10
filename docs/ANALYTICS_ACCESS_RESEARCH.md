# Durable read-only Analytics access — research, 10 October 2026

## Purpose

Owner wants the agent to have ongoing read-only access to DocOga's Analytics across future sessions, instead of repeated owner exports/screenshots. This document records what was verified, what was disproved, the recommended design, the cost/privacy gates, and the acceptance test that must pass before anyone calls this "connected."

Status: **research + environment verification complete; nothing connected; no authenticated report retrieved yet.** No Google identity, IAM change, API enablement, workflow, budget change or deployment has been performed.

## What was tested and disproved (correcting earlier assumptions)

Earlier drafts of this plan assumed the agent could dispatch workflows and read run logs/artifacts. Direct tests on 10 Oct 2026 show otherwise:

1. **No native Analytics connector.** `list_connector_tools("google_analytics")` → `unsupported` (repeat). A `google` connector is also `unsupported`. This proves there is no *usable* connector here; it does **not** prove no external Google access was ever granted elsewhere.
2. **The agent cannot trigger workflows.** `gh workflow run net-probe.yml ...` → `HTTP 403: Resource not accessible by integration` on `.../actions/workflows/{id}/dispatches`. So `workflow_dispatch`-only designs cannot be driven by the agent.
3. **The agent cannot read run logs.** `gh run view <id> --log` and the REST job-log endpoint both redirect to `results-receiver.actions.githubusercontent.com` / `productionresultssa*.blob.core.windows.net`, which are outside this sandbox's host allowlist → `EOF`. **Any design that reads its result from a run log is unusable.**
4. **The agent cannot read artifacts.** The artifact list is readable (currently empty), but artifact download redirects to the same blocked storage host.
5. **The agent CAN read and write repository contents.** Repo `permissions` = admin/maintain/push/triage; `git push` to the session branch works and triggers workflows (the `Verify` workflow runs on every push). Repository files and `api.github.com` metadata are fully readable.
6. **Cost gate is real and enforced.** Personal billing shows **GitHub Free**, current cycle included usage **$2.96** (docoga $1.97), no payment due, and a **Budgets and alerts** entry for **Actions: Stop usage = Yes, budget $0**. Paid Actions overage is therefore hard-stopped. Alerts-only would not have been sufficient; this is the stronger control. GitHub documents private-repo included minutes (Free = 2,000/month, 500 MB artifacts) and that larger runners are always billed. [2](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions)
7. **GitHub runners have unrestricted egress; this sandbox does not.** The repository already contains `.github/workflows/net-probe.yml`, built explicitly as an egress bridge because the sandbox cannot reach workers.dev / docoga.com.ng. This confirms the bridge concept, but its documented read-out method (run log) is now blocked (point 3) — so results must be returned via the repository, not the log.
8. **Reusing the existing Google OAuth client is fragile.** The repo already holds `YT_CLIENT_ID` / `YT_CLIENT_SECRET` / `YT_REFRESH_TOKEN` for YouTube, so a Google Cloud project very likely exists. But Google expires refresh tokens after **7 days** when an external OAuth app is in **Testing**, and adding the Analytics read scope to an external app requires **sensitive-scope verification**. [1](https://developers.google.com/identity/protocols/oauth2) [1](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification) Both are avoided by a service account.
9. `contents: write` and commit-back are already an established pattern here (`youtube_queue.yml`, `youtube_scheduled.yml` commit a publish ledger). A committed report file will not break `verify.yml` (it runs `pre_push_verify.sh` + `qa.py`, which target `site/` and `worker/`).

## Verified facts about the repository

- Private repo, default branch `main`; repository **ID 1376068242**, owner **ID 120726541**.
- 12 workflows, all active; none is an Analytics reporter. No GA reporting SDK/config found.
- Actions secrets/variables/permissions endpoints → `HTTP 403`; the agent cannot read or set secrets. Never request secret values in chat.
- Existing measurement ID is a tracking tag, not the numeric GA4 property ID and not reporting permission.

## Recommended design — "repo-committed GA4 snapshot"

Because the agent can read repository contents but cannot dispatch or read logs/artifacts, the report must be **written back into the repository**; that is the only retrieval path that works in every future session.

1. **Identity:** a dedicated Google service account with **Viewer on the DocOga GA4 property only** (not account-level access to all properties). Property-level access is the documented, least-privilege Analytics grant. [1](https://support.google.com/analytics/answer/9305788?hl=en)
2. **Keyless auth:** GitHub OIDC → Google Workload Identity Federation → that service account → short-lived OAuth token scoped `https://www.googleapis.com/auth/analytics.readonly`. Trust is restricted by numeric `repository_id` (and owner id), never by reclaimable names. Google recommends numeric IDs against typosquatting. [1](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
3. **Action:** reviewed, SHA-pinned `google-github-actions/auth` with `token_format: access_token`, the service account, and explicit `access_token_scopes: https://www.googleapis.com/auth/analytics.readonly` (the default generated scope is `cloud-platform`, which is not Analytics permission). Service-account impersonation is required for generated tokens; no domain-wide delegation. [Action docs](https://github.com/google-github-actions/auth/blob/main/README.md)
4. **Runner:** `ubuntu-latest`, one small `requests`-based script (no SDK dependency), fixed aggregate query set, `timeout-minutes` bound, no credential/token logging, no Analytics write calls.
5. **Output:** a sanitized aggregate JSON committed to `analytics/reports/YYYY-MM-DD.json` and `analytics/reports/latest.json`, committed with `[skip ci]` so it does not re-trigger CI loops.
6. **Triggers (in priority order):**
   - `push` with a path filter on a refresh-request file → **the agent can trigger a refresh by pushing that file** (push works; dispatch does not). Runs on the pushed branch and commits the snapshot back to it.
   - `workflow_dispatch` → owner taps "Run workflow" for a manual refresh.
   - `schedule` → hands-off daily snapshot, but this runs **only on the default branch** and may be delayed or dropped; it requires an owner-approved merge to `main`. The 60-day inactivity auto-disable rule applies to public repos, not this private one. [1](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
7. **Retrieval:** in any future session the agent reads `analytics/reports/latest.json` via git/`api.github.com` and reports its timestamp, date range and warning flags.

## Cost

Identity (IAM/WIF/service accounts) is free; the runner stays inside the included Actions allowance, and the **$0 hard-stop budget** prevents paid overage. Avoid VMs, Cloud Run, BigQuery, Looker and any paid dashboard. An estimate of 1–2 minutes once daily is ~30–60 runner minutes/month, shared with existing workflows — an estimate, not measured usage. A newly created budget is not retroactive cost protection. Do not proceed if a paid dependency or billing requirement appears.

## Privacy, freshness and honesty

- Read-only Analytics is still sensitive. Viewer is property-wide, not limited to the reports our script requests; anyone able to edit the trusted workflow could request other readable property data, so workflow review and ref restrictions matter.
- Aggregate only: users/sessions/engagement/channel/source and **sanitized** page groups; 7/28/90-day windows. No user identifiers, emails, pass codes, payment references or URL query strings. Do not export raw `pageLocation` blindly. Never reverse-engineer suppressed small counts.
- Every report must carry: retrieval timestamp (UTC), requested dates, numeric property id, property timezone, row/pagination status, and GA's thresholding/sampling/`(other)`-row data-loss flags. [1](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/ResponseMetaData)
- Standard GA data is not live: processing can take 24–48 hours and recent numbers change. Prefer complete windows ending two property-calendar days ago; label yesterday/today provisional. [1](https://support.google.com/analytics/answer/11198161?hl=en)
- No uptime guarantee. Scheduled runs can be delayed/dropped and the agent cannot force one via dispatch; on-demand refresh depends on the push path. The agent will always state the last successful retrieval and the reason for any gap, and will never present a stale snapshot as current.
- Reporting access does not create purchase tracking. The site has no verified purchase event; Analytics access cannot prove sales. That is a separate authorised task.

## Alternatives assessed

- **Official Google Analytics MCP** — genuine read-only experimental server, but requires a configured client/runtime, `analytics.readonly` credentials and Google API network access. Not attached here and not usable from this sandbox. [Official repo](https://github.com/googleanalytics/google-analytics-mcp)
- **Service-account JSON key** — simpler but a long-lived secret to store and rotate; rejected. Never send a key in chat.
- **Reuse the YouTube OAuth client** — 7-day expiry in Testing plus sensitive-scope verification; also widens blast radius by sharing the uploader's grant. Rejected.
- **Public dashboard / screenshot exports** — do not give private, independent, ongoing retrieval.

## Acceptance test before saying "connected"

1. Owner-side setup complete (identity + property Viewer + WIF + repo variables), within the no-paid-overage gate.
2. Reporter runs and mints the `analytics.readonly` token without logging it.
3. A real authenticated `runReport` succeeds for the confirmed DocOga property; one aggregate matches the owner's same dates/timezone/report definition. An empty-but-authenticated response still proves access, not traffic.
4. The committed snapshot is readable by the agent in a **fresh session** (this is the make-or-break test given the blocked log/artifact hosts).
5. The push-triggered refresh produces a newer timestamped snapshot; failures are bounded and leak no credentials.
6. Rediscovery + stale-state behaviour documented.

## Next owner step (one screen at a time)

Open the Google Cloud console and show the project selector: **https://console.cloud.google.com** — do not enable billing, start a trial, or change IAM yet. We will confirm whether the existing YouTube/Gemini project can host the service account before creating anything. Screenshots are for setup only, never the permanent reporting mechanism.
