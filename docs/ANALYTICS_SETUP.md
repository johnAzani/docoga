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

## Remaining step 1 — enable the Analytics Data API

In project `apt-trainer-367908`, enable **Google Analytics Data API**. Easiest
route: **Cloud Shell** (console → the `>_` icon, top-right).

Paste this whole block into Cloud Shell and press Enter. It is safe to re-run.

```bash
gcloud config set project apt-trainer-367908
gcloud services enable analyticsdata.googleapis.com sts.googleapis.com iamcredentials.googleapis.com

gcloud iam workload-identity-pools create github-actions \
  --project=apt-trainer-367908 --location=global \
  --display-name="GitHub Actions" || true

gcloud iam workload-identity-pools providers create-oidc github \
  --project=apt-trainer-367908 --location=global \
  --workload-identity-pool=github-actions \
  --display-name="GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com/" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository_id=='1376068242' && assertion.repository_owner_id=='120726541'"

PROJECT_NUMBER=$(gcloud projects describe apt-trainer-367908 --format='value(projectNumber)')

gcloud iam service-accounts add-iam-policy-binding \
  docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com \
  --project=apt-trainer-367908 \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions/attribute.repository_id/1376068242"

echo "WIF PROVIDER = projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions/providers/github"
```

Copy the printed **WIF PROVIDER** line — you need it next. It contains no secret.

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
2. It should commit a snapshot with `"mode": "live"` and real rows.

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
  timezone and GA thresholding/sampling flags. Standard GA data can lag 24–48 h.
- No purchase/sales tracking exists yet; Analytics access cannot prove revenue.
- No uptime guarantee: scheduled runs can be delayed or dropped; the agent will
  always state the last successful retrieval time.
- Revoke anytime by removing the service account's Viewer role or disabling the
  WIF provider/workflow.
