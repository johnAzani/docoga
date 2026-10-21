# Private documents — what moved out of this repository, and why

This repository has been **public since 20 Oct 2026, 3:58am WAT** (the ₦0 answer to the
private-repo Actions allowance — `docs/TOKENS.md` §10). Code, operating guides, lane records and
brand rules are public on purpose. The owner's **plans and money** are not. On 21 Oct 2026 the
owner asked for them to be moved ("Move them"), and they now live in the private companion
repository **`johnAzani/docoga-private`** (a full import of this repository, so every file keeps
its history there).

## What moved (14 files)

| File | What it is |
|---|---|
| `docs/MANDATE.md` | the standing orders, the owner/app pay split, the fund triggers, the north star |
| `docs/SESSION_CONTEXT.md` | the 180 KB handover log — every session's decisions since September |
| `docs/GROWTH_ENGINE.md` | the audience plan, best posting times, the per-platform growth playbook |
| `docs/REVENUE.md` | money in, fees, settlement evidence |
| `docs/BUSINESS_PLAN.md` · `PLAN.md` | the business plan and the research behind the 18 Sep decision |
| `docs/BUSINESS_TIER_RESEARCH.md` | the Business-tier dossier |
| `docs/B2B_DISCOVERY.md` · `docs/B2B_DISCOVERY_WORKBOOK.md` · `docs/B2B_OUTREACH_GROUNDWORK.md` | go-to-market: who to talk to and how |
| `docs/DEPLOY_STATUS.md` | the running status page with revenue evidence |
| `docs/GROWTH_JOURNAL.md` | week-by-week performance notes |
| `DOCOGA-RISK-LOG.md` | the risk register |
| `.arena_context.md` | stale agent session notes |

## What stayed public, deliberately

`docs/INCIDENT_LOG.md` (how outages were closed — operating transparency), `docs/TOKENS.md`
(how credentials are minted; it holds no values), `docs/BRAND_STYLE.md`, `docs/SHORTS_MOTION.md`,
`docs/BRAIN.md`, every `*_AUTOMATION.md`, `brain/feedback.md` (the brain writes it; it is a weekly
scorecard, not a plan), and the lane ledgers under `logs/`.

## Honest note on history

Deleting a file from `main` removes it from GitHub search, Google and the file browser — which is
where strangers actually look. The old versions remain reachable in this repository's **commit
history** for anyone who knows to go digging. Erasing that too needs a one-time history rewrite
plus a GitHub Support purge; the owner can ask for it any time and the private import already
holds a complete copy, so nothing would be lost.

## Rules from here

* New strategy, money or go-to-market writing goes to `docoga-private`, never here.
* Prose in this repo may still *mention* a private file by name (many docstrings do); that is a
  pointer, not a leak.
* `tools/secret_scan.py` (QA §17) remains the gate for credentials; this page is the gate for plans.
