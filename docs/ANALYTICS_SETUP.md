# DocOga Analytics read-only access — owner setup runbook

Goal: future sessions can read DocOga Analytics directly, without you sending
exports or screenshots. This runbook is the remaining setup. Screenshots are for
setup only; the permanent mechanism is the committed snapshot.

## Already done (10 Oct 2026)

| Item | Value |
| --- | --- |
| Google Cloud project | `apt-trainer-367908` |
| Reporting identity | `docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com` |
| GA4 property | DocOga |
| **Numeric GA4 property ID** | **558370565** |
| Web stream / measurement ID | DocOga Web / `G-BQ1YTR0ZZJ` |
| Analytics permission | service account = **Viewer** on the DocOga property only |
| GitHub repo | `johnAzani/docoga`, repo ID `1376068242`, owner ID `120726541` |
| Cost gate | Actions budget hard stop at $0 (verified) |
| Retrieval mechanism | workflow commits `analytics/reports/latest.json`; verified working |

## Keyless setup progress — 10 October 2026, 17:27 WAT

Owner screenshots confirm:
- Cloud project display name changed to **DocOga**; ID remains `apt-trainer-367908`, project number `635194176409`.
- Cloud Shell started in that project.
- `analyticsdata.googleapis.com`, `iam.googleapis.com`, `iamcredentials.googleapis.com`, and `sts.googleapis.com` enabled successfully.
- Workload identity pool `github-actions` created successfully.

**Do not repeat creation or run the earlier all-in-one script.** The commands
below replace it. Stop and inspect errors instead of masking them with `|| true`.
Continue one screenshot/command at a time.

### Next: create the narrowly trusted provider

Only repository ID `1376068242`, owner ID `120726541`, and the Analytics
workflow on the current session branch may use this provider, for `push` or
`workflow_dispatch` events. Pull-request code, unrelated workflows and other
branches are not authorised. Scheduled default-branch access is intentionally
excluded until the owner approves default-branch activation; then the trust
policy must be reviewed and updated explicitly. Do not broaden to all workflows.
Anyone who can modify the authorised workflow can still change what it reads
within the service account's property-level Viewer grant; code review matters.

```bash
gcloud iam workload-identity-pools providers create-oidc github \
  --project=apt-trainer-367908 --location=global \
  --workload-identity-pool=github-actions \
  --display-name="DocOga Analytics GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref,attribute.workflow_ref=assertion.workflow_ref,attribute.event_name=assertion.event_name" \
  --attribute-condition="assertion.repository_id=='1376068242' && assertion.repository_owner_id=='120726541' && assertion.ref=='refs/heads/arena/47d148f1-docoga' && assertion.workflow_ref=='johnAzani/docoga/.github/workflows/analytics-snapshot.yml@refs/heads/arena/47d148f1-docoga' && assertion.event_name in ['push','workflow_dispatch']"
```

Screenshot the result before continuing. If it says already exists, inspect the
existing provider rather than treating this command as a successful update.
Provider creation alone does not grant service-account impersonation.

### Later: grant impersonation on this service account only

After verifying the provider creation/condition, add this binding:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com \
  --project=apt-trainer-367908 \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/635194176409/locations/global/workloadIdentityPools/github-actions/attribute.repository_id/1376068242"
```

This principal set is limited further by the provider condition above. A new
provider added to the same pool could change its trust boundary; keep this pool
dedicated and review future IAM/provider changes. Do not grant Owner, Editor,
project-wide Token Creator or domain-wide delegation. No service-account key.

The provider configuration value (not a secret) will be:
`projects/635194176409/locations/global/workloadIdentityPools/github-actions/providers/github`.

## Remaining step 2 — set three repository variables

GitHub → repo **Settings → Secrets and variables → Actions → Variables → New repository variable**:

| Name | Value |
| --- | --- |
| `GA_PROPERTY_ID` | `558370565` |
| `GCP_SERVICE_ACCOUNT` | `docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | the `projects/<number>/...` line from step 1 |

These are configuration, **not secrets** — no key or password is involved.

## Remaining step 3 — run it and verify

1. GitHub → **Actions → Analytics snapshot → Run workflow** (or the agent
   pushes `analytics/refresh-request.json`).
2. It should commit a snapshot with `"mode": "live"` and a successful authenticated response. Rows may be empty in this newly created property.

The agent then reads `analytics/reports/latest.json` in any future session.

## Remaining step 4 — start collecting DocOga data (separate, later)

The live site still sends to the **old** tag `G-GO8VZB3R28`. To feed the new
property, `site/index.html`'s `ANALYTICS_ID` must become `G-BQ1YTR0ZZJ` and be
deployed. **This is a production change and is NOT done yet** — it will be a
separate owner-approved step. Until then the new property legitimately has no
data, and reports will be empty (which still proves access works).

## What the agent can and cannot do (verified)

- ✅ Read repository files and `api.github.com`; push commits (triggers workflows)
- ❌ Trigger workflows via API (403) — hence push-to-refresh
- ❌ Read run logs or artifacts (blocked hosts) — hence commit-back
- ❌ Reach Google APIs from the sandbox — hence running inside GitHub Actions

## Honesty notes

- Reports are aggregate only and carry retrieval time, date range, property ID,
  property ID. Timezone/sampling/data-loss metadata handling still needs hardening before production reporting; the current scaffold does not preserve every required flag. Standard GA data can lag 24–48 h.
- No purchase/sales tracking exists yet; Analytics access cannot prove revenue.
- No uptime guarantee: scheduled runs can be delayed or dropped; the agent will
  always state the last successful retrieval time.
- Revoke anytime by removing the service account's Viewer role or disabling the
  WIF provider/workflow.
