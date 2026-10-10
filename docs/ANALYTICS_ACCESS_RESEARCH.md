# Durable read-only Analytics access — research, 10 October 2026

## Decision and current status

Owner request: agent-side reporting across future sessions, not repeated owner exports or screenshots. Recommendation: **conditionally use a repository-run GA4 Data API reporter with keyless Google authentication**, daily snapshots and on-demand refresh. This is a proposed architecture, not an installed connection or an uptime guarantee.

No authenticated GA report has been retrieved. Native connector lookup returned `unsupported`; that establishes no usable connector here, not that Google lacks an AI integration. Google publishes an official experimental Analytics MCP server, but a configured client, runtime, credentials and Google API network access are required. This environment's outbound-host allowance does not include Google APIs. Installing an MCP package alone would not solve that restriction.

Research only: no Cloud identities, IAM changes, API enablement, workflows, billing changes or production deployments performed. B2B remains paused; no meetings required.

## Verified here versus unresolved

Verified by local repository and authenticated GitHub API checks:

- Repository `johnAzani/docoga` is private, default branch `main`.
- Repository ID `1376068242`, owner ID `120726541`; IDs can constrain federation trust without relying solely on reclaimable names.
- The current GitHub connection can read repository contents, list workflows and list artifacts. The artifact list is empty: actual artifact download remains untested.
- Existing workflow inventory has no Analytics reporter. No working GA reporting SDK/configuration was established by the repository audit.
- Actions secrets, variables and permissions endpoints returned HTTP 403, `Resource not accessible by integration`. Do not equate this with all Actions access being unavailable. Do not invent secret configuration or ask for token values.
- Existing website measurement ID is a tracking identifier, not the numeric GA4 property ID or reporting permission.

Unresolved gates: numeric GA4 property ID, existing suitable Cloud project, owner's Analytics Administrator access, available Actions allowance and enforced no-paid-overage setting, Actions OIDC/auth-action policy, workflow-dispatch permission, artifact download, privacy-approved long-term report storage, and a successful Google `runReport` response. Dispatch was not tested against unrelated existing workflows because doing so could deploy or publish content.

## Recommended design

1. Create a dedicated service account in an appropriate existing Google Cloud project, if one is available. Do not grant Owner, Editor, domain-wide delegation or broad project resource permissions to the reporter.
2. Give that account **Viewer on the DocOga GA4 property only**, not account-level access to every property. This is an Analytics permission, separate from Cloud IAM. Google documents property-level access and inherited account-level access. [1](https://support.google.com/analytics/answer/9305788?hl=en)
3. Enable the Analytics Data API and the required WIF/service-account credential APIs, subject to the no-billing gate. Do not follow a quickstart into creating a VM: the Google service-account quickstart currently includes a VM example, but the proposed runtime is GitHub Actions, not a paid VM. [Google quickstart](https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart?account_type=service).
4. Use GitHub OIDC → Google Workload Identity Federation → this service account → short-lived OAuth access token. Restrict accepted identity by numeric repository and owner IDs, approved workflow/ref and intended event types. No forks, pull-request code or unrelated workflows should obtain this identity. Google specifically recommends numeric IDs against name-reclamation attacks. [1](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
5. Use the reviewed, SHA-pinned `google-github-actions/auth` action with `token_format: access_token`, the service account and explicit scope `https://www.googleapis.com/auth/analytics.readonly`. Its default generated token scope is `cloud-platform`, which is not a substitute for Analytics read permission. Service-account impersonation is required for this generated-token mode. No domain-wide delegation is needed. [Action documentation](https://github.com/google-github-actions/auth/blob/main/README.md).
6. Run a bounded reporter on a standard Linux runner: small fixed query set, timeout, concurrency guard, bounded retries/backoff, no debug credentials. Separate reporting permissions from existing deployment/payment secrets. No code/API writes to Analytics.
7. Fetch aggregate traffic reports, publish a small private artifact with explicit retention, and test that this agent can download it. Never place OAuth tokens, credential files or raw API error bodies in an artifact or log.
8. Add a daily schedule plus manual refresh only after dispatch/download validation. Scheduling operates on the default branch and may be delayed or dropped. Work stays on this session branch; any default-branch activation requires an approved PR/merge, not switching branches. The 60-day inactivity disabling rule is for public repositories, not this private repository. [1](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)

An example job lasting 1–2 minutes once daily would consume roughly 30–60 runner minutes a month, before retries or manual refreshes; this is an estimate, not measured usage. Other repository workflows share the owner's allowance.

## Cost gates: do not promise unconditional ₦0

Google lists IAM, including workload federation, as free of charge; that is not proof that all surrounding Google services are free. Avoid VMs, Cloud Run, BigQuery, external paid dashboards and paid API services for this task. [1](https://cloud.google.com/products/iam)

Private GitHub repositories have plan-dependent included minutes/storage; additional usage can be billed. GitHub Free currently includes 2,000 minutes and 500 MB artifact storage, shared with other relevant account usage. Larger runners are always charged. Owner's actual plan, current usage and spending controls have not been verified. [2](https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions)

An alert-only budget is insufficient. Verify the relevant **Stop usage when budget limit is reached** control and no-paid-overage configuration on the owner's actual screen before enabling automation. GitHub notes first-cycle budget limitations, so a newly created budget is not retroactive cost protection. [2](https://docs.github.com/en/billing/how-tos/set-up-budgets) [1](https://docs.github.com/en/billing/concepts/budgets-and-alerts)

No authoritative explicit Data API per-request pricing statement was established in this research; do not base a guarantee on secondary blogs. Inspect the actual API/project setup and stop if a paid dependency, billing requirement or trial appears. API quotas are not pricing evidence.

## Privacy, persistence and report quality

Read-only Analytics is still sensitive. Viewer is property-level, not limited to the few reports chosen by our script. Anyone able to alter the trusted reporting workflow could request other readable property data; workflow review and ref restrictions matter.

Start with aggregate users, sessions, engagement, channel/source and sanitized page-path groups; date windows 7/28/90 days, as supported by compatible schemas. Do not download user identifiers, emails, pass codes, payment references, document values or URL query strings. Do not export `pageLocation` or raw paths blindly: allowlist/sanitize page groupings and check collection practices before retaining results. Suppressed/small counts must not be reverse-engineered.

Every report must retain: retrieval timestamp in UTC, explicit requested dates, numeric property identity, property timezone, request/schema version, row counts and pagination status, metadata/thresholding/sampling/data-loss warnings, and source workflow run ID. GA response metadata documents thresholding, sampling and `(other)`-row data-loss indicators. [1](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/ResponseMetaData)

Standard report data is not guaranteed live; Google says processing can take 24–48 hours and recent reports can change. Prefer complete historical windows ending two property-calendar days ago for baseline comparisons; label yesterday/today provisional separately. Fetch time is not the same as data completeness. [1](https://support.google.com/analytics/answer/11198161?hl=en)

Artifacts expire, and a session workspace alone is not an always-on store. Recommended first stage: retained private artifacts, a documented discovery/download command and stale-report handling. Before expiry, choose an owner-approved protected long-term store for sanitized aggregates; a private repository report file is possible but visible to all repo readers, remains in Git history and may trigger other workflows. Do not silently commit analytics datasets or auto-push reports. No long-term store is selected yet.

At each future session: read this runbook, check connection permissions, locate latest successful report, check its timestamp, refresh if possible, otherwise state the last successful retrieval and failure. Never present stale cached data as current. Revoke by removing property Viewer access or disabling federation/provider/workflow; deletion of saved reports is a separate retention action.

Current instrumentation does not establish verified purchases. Reporting access does not create a purchase event or prove payment totals; do not infer sales from page views, success URLs or sessions. Fixing purchase measurement is a separate authorised task.

## Alternative assessment

- **Official Google Analytics MCP:** genuine read-only experimental implementation; attractive if Arena later provides a compatible authenticated runtime/connector and Google API network access. Not currently attached. Its credential setup requires `analytics.readonly`; user OAuth may require renewed consent/re-authentication. [Official repository](https://github.com/googleanalytics/google-analytics-mcp).
- **Service-account JSON key:** operationally simpler but long-lived credential risk, rotation burden and unnecessary secret handling; not the preferred route. Never send a key in chat.
- **Public dashboard or screenshot exports:** does not satisfy private, independent ongoing retrieval. Public publication exposes business data; repeated exports shift work back to owner.
- **Google Sheet/Looker Studio bridge:** extra connector/authentication surface and caching/refresh dependency; no verified Arena retrieval path, so not preferred here.

## Acceptance test before saying connected

1. Verify budget/allowance and approved setup, without billing activation.
2. Run an explicitly authorised reporting-only workflow and mint the intended scoped token without logging it.
3. Retrieve a real authenticated `runReport` for the confirmed DocOga property; compare one aggregate with the owner's same dates/timezone/report definition. An empty authenticated response can prove access, not traffic.
4. Download its private report through the current agent's GitHub connection.
5. Dispatch a reporting-only refresh, retrieve the new timestamped result and verify bounded failures/no credentials in outputs.
6. Prove rediscovery from a fresh session, with an approved persistence/retention policy and honest stale-state behavior.

Next owner screen: GitHub personal-account **Settings → Billing and licensing → Budgets and alerts** (label may vary). One screenshot at a time; redact private account/payment details. This checks no-paid-overage protection before Cloud setup. Screenshots are for initial setup only, not the permanent reporting mechanism.
