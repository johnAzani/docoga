# DocOga Analytics read-only access — owner setup runbook

**Status, 10 Oct 2026, 18:51 WAT:** Google-side keyless identity is
screenshot-verified. The first live run (`38071879234`) failed on an omitted
`rowCount`; the conservative parser fix was pushed as `801a1ea`. The owner then
approved exactly one retry. Run `38073371592` completed WIF authentication,
Analytics `runReport`, and report commit-back successfully; bot commit `bbde8dd`
added live `latest.json` and the dated report. The report covers 2–8 October
2026, has zero rows (`row_count: 0`, source `implicit_empty_response`), and
confirms the response's `Africa/Lagos` timezone and `NGN` currency. This proves
the read-only report path works; it does not prove site traffic or purchases.
No further live request is approved. The site tag/deploy, default-branch merge,
schedule, and broader trust remain unapproved.

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
response warnings, empty-report row-count handling, and token redaction. The
first run `38071879234` proved WIF token exchange only; the approved retry
`38073371592` completed `runReport` and report commit-back, confirming live
read-only reporting. Details follow.

**Privacy approval gate:** the owner approved the initial live attempt and,
after the parser fix was pushed, exactly one retry with a sanitized aggregate
report commit. The first attempt failed before writing a report; the approved
retry succeeded. Both approvals are now exercised. Obtain fresh explicit
approval before any further GA4 request. No approval exists for site deployment,
default-branch merge, scheduled access, or broader trust. The successful empty
`rows` response proves the read-only report path, not site traffic.

## Live report validation — first attempt failed, approved retry succeeded

### First attempt — row-count validation failure

The owner-approved trigger produced run `38071879234` (`f3fec02`). WIF
authentication succeeded, but the live Analytics report step failed with the
screenshot-confirmed message `Google Analytics response is missing a valid
rowCount`. Commit-back was skipped; `latest.json` remains the earlier
placeholder, with no real data in Git history.

Google's [RunReportResponse schema](https://github.com/googleapis/googleapis/blob/master/google/analytics/data/v1beta/data.proto)
defines `row_count` as a proto3 `int32` and `kind` as the fixed
`analyticsData#runReport`. The first failure was consistent with an omitted
default-zero count. The successful retry recorded
`row_count_source: implicit_empty_response`, confirming the narrow fallback was
used for a recognized empty RunReport. The raw API JSON is not retained. The
parser accepts a missing count as zero **only** for that recognized empty
response; missing counts for nonempty or unrecognized responses still fail
closed. Targeted reporter tests pass 8/8; the full Python suite passes 71/71;
`tools/qa.py` is green (two environment-only warnings); `git diff --check` and
`tools/pre_push_verify.sh` pass.

### Approved retry — live empty report committed

After the parser/docs fix (`801a1ea`, `29eff4e`) was pushed, the owner approved
exactly one retry. Trigger commit `4062832` ran workflow `38073371592`; WIF,
`Write snapshot (live, read-only)`, and commit-back all succeeded. Bot commit
`bbde8dd` added `analytics/reports/latest.json` and
`analytics/reports/2026-10-10.json`, both with `mode: live`. The report covers
2026-10-02 through 2026-10-08 in `Africa/Lagos`, with `NGN` currency, zero rows,
and `row_count: 0`. No raw identifiers, URLs, or user-level data are present.
This confirms live read-only reporting, not site traffic or purchases. The
separate site-tag change/deploy remains unapproved. This retry approval is
exercised; do not issue another Analytics request without fresh explicit
approval.

The default-branch schedule is not active for this session branch. Default
branch merge and any widening of provider trust are separately approval-gated.

## Separate later work — live website tag

The production site still uses its old tag `G-GO8VZB3R28`; the dedicated DocOga
property stream is `G-BQ1YTR0ZZJ`. Changing `site/index.html` and deploying are
production changes, **not approved or done**. Until separately approved and
deployed, the new property may correctly return no rows. Analytics access alone
does not prove purchases or revenue; no verified purchase event exists.

## What this setup does not promise

- Live read-only reporting was confirmed by run `38073371592`; a placeholder from an earlier run is still not a live report.
- Google Analytics processing can lag and recent totals can change; the report
  ends two property-calendar days ago.
- Scheduled runs can be delayed or dropped; no uptime guarantee.
- Viewer is property-wide, even though the code requests one fixed aggregate
  report. Keep the authorized workflow and provider restriction reviewed.
- A fresh-session readback and an owner-side comparison are still acceptance
  checks; the current empty report cannot be compared to a nonempty baseline.
- Revocation can be done by removing the service account's property Viewer role
  or disabling the WIF provider/workflow. Do not create or share a long-lived key.
