# DocOga Analytics read-only access — owner setup runbook

**Status, 10 Oct 2026, 17:53 WAT:** Google-side keyless identity is
configured and screenshot-verified. The first repository variable is now saved.
The pipeline is **not connected yet**: the other two variables are pending, no
live authenticated GA4 request has run, and no real Analytics data has been
committed. Do not call this complete until a committed report says `"mode":
"live"`.

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

## Repository variables — 1 of 3 saved

The current GitHub **Settings → Secrets and variables → Actions → Variables**
screenshot shows `GA_PROPERTY_ID` saved with the correct value. The other two
are still required:

| Name | Value | Status |
| --- | --- | --- |
| `GA_PROPERTY_ID` | `558370565` | Saved (owner screenshot, 10 Oct 17:53 WAT) |
| `GCP_SERVICE_ACCOUNT` | `docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com` | Pending |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/635194176409/locations/global/workloadIdentityPools/github-actions/providers/github` | Pending |

These are non-secret **repository variables**, not secrets or environment
variables. The `gh variable` subcommand is not installed in this sandbox, and
the GitHub Actions variables REST API returned 403 `Resource not accessible by
integration`; use the repository Variables page. Continue screenshot-by-
screenshot, one variable at a time. The next one to add is
`GCP_SERVICE_ACCOUNT` with the exact value in the table; confirm the saved row
before adding the provider value.

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
response warnings, and redaction of tokens from HTTP error messages; they do not
prove live Google authentication.

**Privacy approval gate:** the first successful live workflow will commit real
aggregate Analytics data into Git history (`latest.json` and a dated file).
Before triggering that first live run, obtain the owner's explicit approval for
that data commit. No real-data snapshot has been authorized or committed yet.
An empty `rows` list from an authenticated response is still a valid access
proof, but it does not mean the site has traffic.

## After all three variables are saved — only after live-data approval

1. Confirm all three repository variable rows are present and exact.
2. Ask for explicit approval to publish the first aggregate snapshot into the
   repository history. Do not infer this approval from the earlier approval of
   the Google/WIF setup.
3. After approval, push a change to `analytics/refresh-request.json` on
   `arena/47d148f1-docoga`; that path triggers the workflow. The owner may also
   use **Actions → Analytics snapshot → Run workflow** on the authorised branch.
   The agent's dispatch API call returns 403, so push-to-refresh is the agent's
   available path.
4. Verify the committed `analytics/reports/latest.json` has `"mode": "live"`,
   the expected property ID, a timestamp/date range, and pagination/quality
   metadata. Do not use run logs or artifacts as the retrieval mechanism; those
   hosts are blocked from the agent environment. A live report is not proven
   until its committed file is readable.

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
