# Durable read-only Analytics access — research, 10 October 2026

## Purpose

Owner wants the agent to have ongoing read-only access to DocOga's Analytics across future sessions, instead of repeated owner exports/screenshots. This document records what was verified, what was disproved, the recommended design, the cost/privacy gates, and the acceptance test that must pass before anyone calls this "connected."

Status as of **10 October 2026, after 18:20 WAT**: research, Google-side WIF setup, keyless reporter, and repository-variable entry are in place; the owner screenshot shows all three expected variable rows. The long variable values are clipped in the list, so only visible prefixes are screenshot-verifiable. The owner explicitly approved one first live aggregate report and its commit to the session branch; the trigger file is updated locally but not yet pushed. **No authenticated Analytics request has run**, no real aggregate has been committed, and the production site tag remains unchanged. Do not call the connection live until a committed snapshot reports `mode: live`. The default-branch merge/schedule, broader trust, site retag, and deploy remain separately approval-gated.

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
- The repo now contains `.github/workflows/analytics-snapshot.yml` and `tools/analytics_snapshot.py`; an earlier placeholder run proved the commit-back mechanism, not Google authentication.
- The GitHub Actions variables REST endpoint returned `HTTP 403 Resource not accessible by integration`; the installed `gh` has no `variable` subcommand. The agent cannot read or set repository variables through these interfaces. Never request secret values in chat.
- The existing production measurement ID is a tracking tag, not the numeric GA4 property ID and not reporting permission. The live site still uses the old tag; the dedicated DocOga property has a different measurement ID and has not been deployed.

## Recommended design — "repo-committed GA4 snapshot"

Because the agent can read repository contents but cannot dispatch or read logs/artifacts, the report must be **written back into the repository**; that is the only retrieval path that works in every future session.

1. **Identity:** a dedicated Google service account with **Viewer on the DocOga GA4 property only** (not account-level access to all properties). Property-level access is the documented, least-privilege Analytics grant. [1](https://support.google.com/analytics/answer/9305788?hl=en)
2. **Keyless auth:** GitHub OIDC → Google Workload Identity Federation → that service account → short-lived OAuth token scoped `https://www.googleapis.com/auth/analytics.readonly`. Trust is restricted by numeric `repository_id` (and owner id), never by reclaimable names. Google recommends numeric IDs against typosquatting. [1](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
3. **Action:** reviewed, SHA-pinned `google-github-actions/auth` with `token_format: access_token`, the service account, and explicit `access_token_scopes: https://www.googleapis.com/auth/analytics.readonly` (the default generated scope is `cloud-platform`, which is not Analytics permission). Service-account impersonation is required for generated tokens; no domain-wide delegation. [Action docs](https://github.com/google-github-actions/auth/blob/main/README.md)
4. **Runner:** `ubuntu-latest`, one Python-standard-library `urllib` script (no SDK or third-party request dependency), fixed aggregate query, bounded timeout and pagination, no credential/token logging, no Analytics write calls.
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
- The implemented report is currently one fixed aggregate: sessions, total users, and engagement rate by `sessionDefaultChannelGroup`, over seven days. No page groups, raw `pageLocation`, user identifiers, emails, pass codes, payment references, or URLs are requested. Never reverse-engineer suppressed small counts.
- Every live snapshot carries: retrieval timestamp (UTC), requested dates, numeric property ID, the verified `Africa/Lagos` timezone, property currency, row/pagination status, and GA's thresholding, sampling, schema-restriction, and `(other)`-row data-loss metadata. The code refuses an unexpected API timezone and refuses to write an incomplete report even if pagination was needed. [1](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/ResponseMetaData)
- Standard GA data is not live: processing can take 24–48 hours and recent numbers change. The implemented window ends two property-calendar days ago. [1](https://support.google.com/analytics/answer/11198161?hl=en)
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

Google-side setup is complete and verified; do not repeat Cloud Shell/IAM commands. The 18:20 WAT GitHub Variables screenshot shows all three expected rows, although long name/value previews are clipped. The owner has explicitly approved one first live read-only report commit. The refresh trigger file is updated locally; the next step is to push it on the session branch, then read the committed snapshot. No secret or key is needed.

## Mechanism proof — 10 October 2026, 13:33 WAT

The commit-back design is now **tested**, not hypothetical. Agent pushed
commit `1889753` (scaffold + refresh request) on `arena/47d148f1-docoga`.
GitHub Actions run **38052387346** succeeded, including commit-back step;
bot commit **f12c5b6** wrote a placeholder snapshot. The agent then read it
via both `git pull` and the GitHub Contents REST API. Thus the complete
**push → workflow → commit snapshot → future agent-readable file** path works.

This was a MECHANISM test only: `mode=placeholder`, `property_id=null`,
`rows=[]`, generated `2026-10-10T12:33:28Z`. No Google API was called; no
Analytics data or secret was involved. Subsequent work added the restricted,
SHA-pinned WIF auth step and live aggregate fetch. That code path is ready but
still gated by the repository variables, and the live identity exchange and
report remain untested.

## Google-side setup verified — 10 October 2026, 17:45 WAT

Owner screenshots confirm Cloud project display name **DocOga** (ID
`apt-trainer-367908`, number `635194176409`); the Analytics Data API, IAM, IAM
Credentials, and STS APIs are enabled; the global `github-actions` WIF pool and
ACTIVE `github` provider exist; and the service account has only the
`roles/iam.workloadIdentityUser` principal-set binding for repo ID `1376068242`.
The provider readback was confirmed to require owner ID `120726541`, the exact
`analytics-snapshot.yml` workflow on `arena/47d148f1-docoga`, and `push` or
`workflow_dispatch`. It intentionally excludes `main` and scheduled events.
The service account already has GA4 property-level Viewer on DocOga property
`558370565` (timezone Africa/Lagos, currency NGN).

At 17:53 WAT the GitHub Variables page showed `GA_PROPERTY_ID=558370565` saved.
`GCP_SERVICE_ACCOUNT` and `GCP_WORKLOAD_IDENTITY_PROVIDER` remain unset. The
agent's `gh variable` command is unavailable and the REST API returns 403, so
the owner UI is required. No real-data commit has been approved, the site tag
remains `G-GO8VZB3R28`, and no production retag/deploy or main merge is
approved.

The reporter hardening now uses property-local dates (seven days ending two
Lagos calendar days ago), a fixed channel-only aggregate, bounded pagination,
row completeness checks, response timezone validation, NGN/timezone provenance,
thresholding/sampling/schema/data-loss metadata, and token-redacted HTTP error
messages. Six offline unit tests pass. These tests validate code behavior only;
they are not evidence of live access.

## GitHub variables listed — 10 October 2026, 18:20 WAT

The owner screenshot shows the repository Variables page with rows for
`GA_PROPERTY_ID`, `GCP_SERVICE_ACCOUNT`, and a third label clipped to
`GCP_WORKLOAD_IDENTITY_P...`. `GA_PROPERTY_ID` is visibly `558370565`; the
other visible value prefixes begin with the expected service-account email and
provider path, but their complete values are clipped. This is screenshot
verification of row presence/prefixes, not an agent-side readback. The variables
REST API remains blocked with 403. No live run or real-data Git commit has
occurred; explicit approval was still required at that screenshot time.

## First live run approved — 10 October 2026, after 18:20 WAT

The owner selected **Approve first snapshot** in the explicit approval prompt,
authorizing exactly one read-only, seven-day aggregate fetch and its sanitized
report commit on `arena/47d148f1-docoga`. It does not authorize a site-tag
change/deploy, merge to `main`, scheduled access, or broader WIF trust.
`analytics/refresh-request.json` has been updated locally with the approved
request (UTC timestamp `2026-10-10T17:27:05Z`); it has not yet been pushed at
this log point. Therefore there is still no authenticated GA response or real
data commit; the push and committed-file readback are next.
