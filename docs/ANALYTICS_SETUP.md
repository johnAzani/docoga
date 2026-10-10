# DocOga Analytics read-only access — owner setup runbook

**Status, 10 Oct 2026, 18:28 WAT:** Google-side keyless identity is
screenshot-verified; the Variables page shows all three expected rows, with
long values clipped. The owner approved the first live attempt. Run
`38071879234` successfully exchanged the GitHub OIDC token for Google access,
but the live Analytics report step failed. The report commit step was skipped;
`latest.json` remains a placeholder, and no Analytics data was committed. The
exact API error is unknown because run logs are not readable from this agent
environment. Do not call this connected until a committed snapshot says
`"mode": "live"`.

This setup is intended to give future sessions durable, read-only access without
repeated exports. The repo snapshot is the retrieval path; screenshots are only
used to configure and verify the accounts.

## Verified configuration

| Item | Verified value/state |
| --- | --- |
| Google Cloud display name | DocOga |
| Google Cloud project ID / number | `apt-trainer-367908` / `635194176409` |
| GA4 property | DocOga, property ID `558370565` |
| GA4 property time zone / currency | `Africa/Lagos` (GMT+01:00) / `NGN` |
| Web stream | `G-BQ1YTR0ZZJ` |
| Service account | `docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com` |
| GA4 access | Service account has property-level Viewer; no broader Analytics role |
| Enabled APIs | Analytics Data API, IAM, IAM Credentials, Security Token Service |
| WIF pool | `github-actions` (global) |
| WIF provider | `projects/635194176409/locations/global/workloadIdentityPools/github-actions/providers/github`, ACTIVE |
| Provider trust | repo ID `1376068242`, owner ID `120726541`, exact Analytics workflow and session branch, only `push` / `workflow_dispatch` |
| IAM binding | `roles/iam.workloadIdentityUser` on this service account for repo ID `1376068242` |
| Cost boundary | GitHub Actions `Stop usage` budget at $0 was verified; no paid service, trial, or Cloud billing enablement |

Provider trust deliberately excludes `main`, schedules, other branches and other
workflows. Do not broaden it or merge to the default branch without separate
owner approval and a reviewed trust-condition change. No service-account key was
created. No token or password belongs in chat or the repository.

## Repository variables — 3 expected rows visible

The 18:20 WAT owner screenshot of GitHub **Settings → Secrets and variables →
Actions → Variables** shows rows for `GA_PROPERTY_ID`, `GCP_SERVICE_ACCOUNT`,
and a third label clipped to `GCP_WORKLOAD_IDENTITY_P...`. `GA_PROPERTY_ID`
shows the full correct value `558370565`; the other long value previews begin
with the expected service-account email and provider path but are truncated, so
the screenshot does not expose every character. These are owner-performed
screenshots, not an agent readback.

| Name | Value | Screenshot status |
| --- | --- | --- |
| `GA_PROPERTY_ID` | `558370565` | Full name/value visible, correct |
| `GCP_SERVICE_ACCOUNT` | `docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com` | Row and expected prefix visible; full value clipped |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/635194176409/locations/global/workloadIdentityPools/github-actions/providers/github` | Name/value preview clipped; visible prefix matches |

These are non-secret **repository variables**, not secrets or environment
variables. The `gh variable` subcommand is not installed in this sandbox, and
the GitHub Actions variables REST API returned 403 `Resource not accessible by
integration`; use the repository Variables page if correction is needed. No
secret, password, service-account key, or token is required.

## Reporter and privacy boundary

`.github/workflows/analytics-snapshot.yml` is SHA-pinned for Google auth, requests
an access token with only `https://www.googleapis.com/auth/analytics.readonly`,
and commits the report back to `analytics/reports/`. It writes a placeholder
while any required variable is missing. The refresh push path works: an earlier
placeholder-only run **38058018325** succeeded and committed **751aacd**. That
was a mechanism test, not a real GA request.

`tools/analytics_snapshot.py` requests only seven-day aggregate metrics
(`sessions`, `totalUsers`, `engagementRate`) grouped by
`sessionDefaultChannelGroup`. It uses the `Africa/Lagos` calendar, ends the
window two property-calendar days before today to allow processing lag, paginates
and records completeness, and preserves thresholding, sampling, schema
restriction, and `(other)`-row data-loss metadata. The report contains no
user-level identifiers, raw page URLs, emails, pass codes, payment references,
or access token. Offline tests cover the fixed query, pagination, timezone,
response warnings, and redaction of tokens from HTTP error messages. Run
`38071879234` proved WIF token exchange only; its Analytics `runReport` step
failed, so live reporting access is not yet proven.

**Privacy approval gate:** the owner explicitly approved one first successful
live workflow and its sanitized aggregate report commit into Git history
(`latest.json` and a dated file) through the approval prompt. That authorization
is limited to this one read-only snapshot on the session branch; it does not
cover site deployment, default-branch merge, scheduled access, or broader trust.
No real-data snapshot has been committed yet. An empty `rows` list from an
authenticated response is still a valid access proof, but it does not mean the
site has traffic.

## First live run — API failure; diagnosis pending

The owner-approved trigger produced run `38071879234` (`f3fec02`). GitHub-to-
Google Workload Identity Federation authentication succeeded, but the live
Analytics report step failed. The report-commit step was skipped; `latest.json`
remains the earlier placeholder, with no real data in Git history. The exact
GA4 API error is not visible to the agent because detailed logs redirect to
blocked hosts.

Next: the owner should open
https://github.com/johnAzani/docoga/actions/runs/38071879234 and screenshot the
failure details for **Write snapshot (live, read-only)**. Do not include any
access token if a log line reveals one. Diagnose the error first; **do not
trigger another GA4 request until the owner explicitly approves a retry**.
Authentication succeeded, but this does not prove a successful Analytics
report or a working read-only report path.

The default-branch schedule is not active for this session branch. Default
branch merge and any widening of provider trust are separately approval-gated.

## Separate later work — live website tag

The production site still uses its old tag `G-GO8VZB3R28`; the dedicated DocOga
property stream is `G-BQ1YTR0ZZJ`. Changing `site/index.html` and deploying are
production changes, **not approved or done**. Until separately approved and
deployed, the new property may correctly return no rows. Analytics access alone
does not prove purchases or revenue; no verified purchase event exists.

## What this setup does not promise

- No live connection has been confirmed yet; a placeholder is not a live report.
- Google Analytics processing can lag and recent totals can change; the report
  ends two property-calendar days ago.
- Scheduled runs can be delayed or dropped; no uptime guarantee.
- Viewer is property-wide, even though the code requests one fixed aggregate
  report. Keep the authorized workflow and provider restriction reviewed.
- Revocation can be done by removing the service account's property Viewer role
  or disabling the WIF provider/workflow. Do not create or share a long-lived key.
