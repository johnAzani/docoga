# DocOga Analytics read-only access — owner setup runbook

**Status, 10 Oct 2026, 18:34 WAT:** Google-side keyless identity is
screenshot-verified; the Variables page shows all three expected rows, with
long values clipped. Run `38071879234` successfully exchanged the GitHub OIDC
token, but the live report step failed with `Google Analytics response is
missing a valid rowCount`. The commit step was skipped; `latest.json` remains a
placeholder and no Analytics data was committed. The parser fix now treats a
missing count as zero only for a recognized empty RunReport response. Targeted
tests pass 8/8; the full suite passes 71/71; `tools/qa.py` is green with two
environment-only warnings; and both `git diff --check` and `tools/pre_push_verify.sh` pass. The
code/docs fix was pushed as `801a1ea` to `arena/47d148f1-docoga`; the trigger
and placeholder report were unchanged, and no new Analytics run started. Do not
call this connected until a committed snapshot says `"mode": "live"`.

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
response warnings, empty-report row-count handling, and token redaction. Run
`38071879234` proved WIF token exchange only; its Analytics `runReport` step
failed, so live reporting access is not yet proven.

**Privacy approval gate:** the owner approved one initial live attempt and its
sanitized report commit to Git history (`latest.json` and a dated file). That
attempt failed before writing any report, so no real data was committed. Treat
the approval as exercised; obtain fresh explicit approval before another GA4
request. No approval exists for site deployment, default-branch merge, scheduled
access, or broader trust. An empty `rows` list from a successful authenticated
response would prove access, not site traffic.

## First live attempt — empty-response row-count handling; retry approval pending

The owner-approved trigger produced run `38071879234` (`f3fec02`). WIF
authentication succeeded, but the live Analytics report step failed with the
screenshot-confirmed message `Google Analytics response is missing a valid
rowCount`. Commit-back was skipped; `latest.json` remains the earlier
placeholder, with no real data in Git history.

Google's [RunReportResponse schema](https://github.com/googleapis/googleapis/blob/master/google/analytics/data/v1beta/data.proto)
defines `row_count` as a proto3 `int32` and `kind` as the fixed
`analyticsData#runReport`. For a new property returning no rows, omission of a
zero-valued `rowCount` is the likely cause, but the raw JSON was not captured.
The parser fix accepts a missing count as zero **only** when `kind` identifies a
RunReport and the `rows` list is empty; it continues to reject missing counts
for nonempty or unrecognized responses. The targeted reporter tests pass 8/8;
the full Python suite passes 71/71, `tools/qa.py` is green (two environment-only
warnings), and `git diff --check` passes.

The first attempt did not commit Analytics data. The tested code/docs fix is
pushed as `801a1ea` on `arena/47d148f1-docoga`; `analytics/refresh-request.json`
and `analytics/reports/latest.json` were not changed, and no new report run
started. Get explicit owner approval before retrying. WIF success is not proof
that `runReport` succeeded.

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
