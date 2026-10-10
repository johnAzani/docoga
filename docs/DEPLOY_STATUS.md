# Deployment status — measured 8–9 Oct 2026

Rule Zero: everything below is measured, with the method stated. Where I could
not determine a cause, it says so rather than guessing.

**Current status — 9 Oct:** §§1–7 below preserve the 8 Oct pre-deployment
snapshot. Their statements that the payment worker and recent site work were not
live are historical and are superseded by §§8–9. PR #11 merged as `7ee8d79`, and
the site serves the Business tier and POA page. Worker deploy run `37890401771`
succeeded as version `2ddb599e-ef40-4b6a-a789-bf5742c97874`, but its Wrangler
output exposed values from Cloudflare dashboard `vars`; the PR comment was
redacted, while deleting the run log was denied to this integration. The owner
now reports replacing the exposed credentials as Worker Secrets. A subsequent
qualifying live payment returned a pass code and activated it for 30 days. The
Worker root showed `lastWebhookMinutesAgo: 6` when checked, which supports a
recent authenticated webhook but does not by itself identify the event. Brevo's
detailed event now identifies the email failure: one attempt, 0% delivered, and
an `Error` rejecting the default sender `noreply@docoga.com.ng` as invalid until
the sender is validated or the domain authenticated. This is a sender-identity
rejection, not a spam-folder or recipient-server bounce diagnosis. **Do not take
another payment or blindly resend.**

## 1. Can the agent reach workers.dev?

**Yes — no configuration change is needed.** Two paths, with different reach:

| Path | Reaches workers.dev? | Gives |
|---|---|---|
| `curl` from the sandbox | **No** — `SSL_ERROR_SYSCALL` | — |
| `fetch_page` tool | **Yes** | response body only (no status code, no POST) |
| GitHub Actions (`net-probe.yml`) | **Yes**, unrestricted | full status code, headers, body, POST, DNS, TLS |

The sandbox blocks *sockets* to everything except `github.com`,
`api.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`
(confirmed: `example.com` fails the same way as `workers.dev`, while
`github.com` returns 200). DNS resolves fine, so it is an egress allowlist, not
a name problem. The `fetch_page` tool runs on different infrastructure and is
**not** subject to it.

**Proof it works:** `https://docoga-git.johnazani.workers.dev/` returned the full
live DocOga homepage.

## 2. 8 Oct snapshot: the payment worker was not deployed

`https://docoga-pass.johnazani.workers.dev` returns Cloudflare's empty
"There is nothing here yet" page on **all three** of:

- `/`
- `/verify?ref=TESTREF123`
- `/activate?code=BOGUSTEST123`

Control: a subdomain that cannot exist
(`this-subdomain-does-not-exist-abc123xyz.johnazani.workers.dev`) returns a
**byte-identical** page. Control the other way: `docoga-git.*` returns the real
site. So the empty page is not what a deployed worker looks like.

Confirmed on the live domain too:

| URL | Result |
|---|---|
| `docoga.com.ng/privacy.html` | full content (control: site serves) |
| `docoga.com.ng/this-file-definitely-does-not-exist.html` | empty (control: 404) |
| `docoga.com.ng/verify?ref=…` | **empty → 404** |
| `docoga.com.ng/activate?code=…` | **empty → 404** |

`wrangler.jsonc` (the deployed one) has **no `main`**, so `docoga-git` serves
`./site` as static assets only — it has no payment routes. `worker/wrangler.toml`
is correctly configured (`name = "docoga-pass"`, `main = "index.js"`, real KV id)
but has evidently not been deployed, or was removed.

**Consequence: the checkout cannot issue codes.** The app degrades to its
offline path — 200 pre-generated hashes hard-coded in `worker/index.js`
(`OFFLINE_HASHES`), validated client-side when the worker is unreachable
(`site/index.html:1137`). So manual selling with those codes still works;
automatic payment→code does not.

The 19 Sep 2026 log (`logs/2026-09-19-first-real-payment-webhook.json`) records a
successful ₦100 Flutterwave charge. That proves a payment settled, **not** that a
pass was issued: `PRICE_NGN` is ₦2,000, so this underpayment is intentionally
ignored by the webhook and cannot serve as an end-to-end test.

## 3. 8 Oct snapshot: recent revenue work was not yet live

- The live site lists **9 tools** — the Power of Attorney tool is absent.
- `docoga.com.ng/power-of-attorney-nigeria.html` returns **404**.

So the sticky bars on 56 pages, the POA tool, the Business tier and the POA
landing page are all in the repo and passing tests, but not on the internet.

## 4. 8 Oct diagnosis: why PR #11's Cloudflare build failed

| Commit | Workers Builds |
|---|---|
| `b84ecfb` (main, base of branch) | **success** |
| PR #11 head | **failure** |

QA + repo integrity: pass. So merging PR #11 as it stands is risky.

## 5. What it is NOT

Ruled out by measurement:

- **Not a code or asset problem.** `wrangler deploy --dry-run` with wrangler
  4.148.0 → **exit 0**, "Read 65 files from the assets directory".
- **Not size.** `site/` is 65 files / 865,624 bytes (main was 64 / 606,255).
  No file over 1 MB.
- **Not the lockfile.** `npm ci` → exit 0; `package-lock.json` unchanged vs main.
- **Not a missing `npm run build` script.** The root `package.json` has no
  `build` script, but it is **identical on main**, which builds successfully, so
  that cannot be the difference.

## 6. What I could not determine

**The actual cause of the Cloudflare build failure is unknown.** The log is at
`dash.cloudflare.com/.../builds/<id>`, which is not in the egress allowlist and
is not fetchable as a page. Everything above is inference from controls.

## 7. Tools built to work around the network limit

- **`.github/workflows/build-check.yml`** — runs `wrangler deploy --dry-run` on
  every push (so it works on a feature branch) and **posts the output as a PR
  comment**, because the sandbox cannot download run logs
  (`results-receiver.actions.githubusercontent.com` is not allowlisted) but can
  read PR comments via `api.github.com`. Currently: **pass**.
- **`.github/workflows/net-probe.yml`** — `workflow_dispatch` with a URL,
  method and body; curls any host and returns status, headers and body. PR #11
  has since merged as `7ee8d79`, so the workflow is on the default branch;
  however, the Arena integration still cannot dispatch Actions when GitHub
  returns 403. The marker-gated deploy workflows in §11 are the reliable route.

## 8. Token diagnosis and live state — measured 8–9 Oct 2026

A Cloudflare API token was added to the repo as `CLOUDFLARE_API_TOKEN` and used
from GitHub Actions. Result per endpoint:

| Endpoint | Result |
|---|---|
| `GET /accounts` | **success** — sees `276c50d7329e162bd36d1ef8eb3e7566`, *"Azanijohn2017@gmail.com's Account"*, created 2026-09-18 |
| `GET /accounts/{id}/workers/scripts` | `{"result": []}` — empty |
| `GET /accounts/{id}/storage/kv/namespaces` | `Authentication error` (code 10000) |
| `GET /accounts/{id}/workers/scripts/docoga-pass/secrets` | `No access to the specified resource` |
| `GET /user/tokens/verify` | `Invalid API Token` (code 1000) |

**Reading these:**

- The token is **valid** and the **account ID is correct** — `/accounts` would have
  failed otherwise.
- `token/verify` returning "Invalid API Token" is **expected and not evidence of a
  bad token**: that endpoint authenticates *user* tokens, not account-scoped API
  tokens.
- The failures are therefore **permission** failures, not credential failures. The
  token cannot read Workers, cannot read KV, and cannot read Worker secrets. It has
  at most Account-level read.

**Conclusion: the token was created without the Workers permissions.** It needs the
**Edit Cloudflare Workers** template, which includes Workers Scripts:Edit *and*
Workers KV Storage:Edit. The KV permission is mandatory here — `worker/wrangler.toml`
binds namespace `f3a5afebe7d04bb0a6018c0d7d355253`.

### Proof, from 8 Oct 2026 (second token attempt)

A second token was created and stored. Fingerprint changed
(`e3d59debf81e1f1b` → `dc47a19ec3bd664a`), so the secret *was* replaced — but every
Workers call failed identically. `GET /zones` then succeeded and returned the
token's own permission set:

```
permissions: ["#zone_settings:edit","#zone_settings:read","#dns_records:read",
              "#dns_records:edit","#page_shield:read","#ssl:read","#page_shield:edit",
              "#zone:edit","#zone:read","#cache_purge:edit","#analytics:read"]
```

**Zone/DNS permissions only — nothing for Workers, KV or Pages.** That is the whole
problem. Two tokens in a row were created from a zone-scoped template.

### Third token attempt, same day — down to two missing rows

Fingerprint `030093fa0b41d28d`. Now partially working, which pinpoints the gap:

| Endpoint | Result | Meaning |
|---|---|---|
| `GET /accounts/{id}/workers/scripts` | **`success: true`, `result: []`** | Workers Scripts **Read** is granted |
| `GET /accounts/{id}/workers/scripts/docoga-pass/secrets` | `No access to the specified resource` | Workers Scripts **Edit** is missing |
| `GET /accounts/{id}/storage/kv/namespaces` | `Authentication error` | Workers KV Storage missing entirely |
| Zone permission list | now contains `#worker:edit`, `#worker:read` | Zone-level Workers Routes granted |

So the token has the **Read** level on Workers Scripts where the deploy needs **Edit**,
and has no KV permission at all. The third dropdown in the permission row reads
"Read" and must read "Edit".

**The account contains zero Workers.** `/workers/scripts` returned an empty list with
`success: true` — a genuine empty, not a permissions empty (compare: KV returns an
authentication error on the same token). The live site `docoga-git` is therefore a
**Pages project**, not a Workers script; Cloudflare surfaces Pages builds as
"Workers Builds" and does not list Pages projects under `/workers/scripts` (verifying
that would need `/pages/projects`, which needs a Pages permission this token lacks).
`docoga-pass` will be this account's first actual Worker, so wrangler's secrets probe
hits a script that does not exist yet — with Edit it will create it rather than 403.

### Initial deployment — 9 Oct 2026 (version superseded by run 37890401771)

Fourth token attempt, fingerprint `f3f99ca0ab153423`, finally had both
`Account → Workers Scripts → Write` and `Account → Workers KV Storage → Write`.
Deploy succeeded on the first try:

```
Deployed docoga-pass triggers (0.74 sec)
  https://docoga-pass.johnazani.workers.dev
  schedule: 0 7 * * *
Initial Version ID: f6370c2d-853d-46db-8aa6-d2754fb9dc88 (superseded by run 37890401771)
```

Bindings confirmed live: `env.KV` → `f3a5afebe7d04bb0a6018c0d7d355253` ("docoga-kv"),
`env.PROVIDER` = `flw`, `env.SITE_URL` = `https://docoga.com.ng`. Account
workers.dev subdomain is `johnazani`.

`WORKER_URL` in `site/index.html` (`https://docoga-pass.johnazani.workers.dev`)
matches the deployed worker exactly — that constant was right all along; the
worker simply had never been deployed under that name.

**Endpoint probes after deploy:**

- `GET /verify?ref=DOCOGA-PROBE-1` → `{"ok":false,"error":"payment not found or not successful yet"}`
- `GET /activate?code=PROBE-CODE-1` → `{"ok":false,"error":"invalid code"}`

Both were 404 before. `/activate` is the endpoint the storefront actually calls
(`site/index.html:1132`), so **activation is restored**.

### Runtime credentials and webhook — incident update, 9 Oct 2026

The owner had reported `FLW_SECRET_KEY`, `FLW_WEBHOOK_HASH`, and `BREVO_API_KEY`
set in Cloudflare, and saved
`https://docoga-pass.johnazani.workers.dev/flw-webhook` in Flutterwave. A later
`[deploy-pass]` run (`37890401771`) deployed successfully as version
`2ddb599e-ef40-4b6a-a789-bf5742c97874`, but its Wrangler config diff exposed the
values for those three names. The values were reported under remote dashboard
`vars`, not as Worker Secrets. Wrangler's default deploy removes dashboard vars
missing from `wrangler.toml`; this deployment did not use `--keep-vars`, so at that
time the payment/email configuration had to be treated as absent. The owner now
reports replacing the exposed values as Worker Secrets, but that restoration, the
active key types, and the match between the active webhook hash and Flutterwave's
saved hash are not independently verified here. The exposed `FLW_SECRET_KEY` was
the wrong key type (public key, not a secret key), so it would not authenticate the
v3 `/verify` call.

**Security response:** the PR #11 deploy comment has been replaced with a
redacted warning. The Arena integration received 403 when asked to delete the
workflow run/log; the owner still needs to attempt deletion of run `37890401771`
from GitHub Actions and report whether it succeeded. Treat the exposed credentials
as compromised regardless of the repo's private visibility. The owner reports
rotating/replacing the Worker secrets; this is not independently verified. Never
put values in this repo, a PR comment, or chat. Before any further deploy, the
owner must confirm current production secrets are in place and the webhook hash
matches Flutterwave's saved setting. Do not take a payment to test this.

| Name | Purpose | Current state / required action |
|---|---|---|
| `FLW_SECRET_KEY` | Classic v3 `/verify` lookup | owner reports replacement; confirm the active Worker Secret is a genuine secret key, not the exposed public key |
| `FLW_WEBHOOK_HASH` | `POST /flw-webhook` authentication | owner reports replacement; confirm the active Worker Secret matches Flutterwave's saved hash |
| `BREVO_API_KEY` | `emailCode()` pass delivery | owner reports replacement; confirm the active Worker Secret is the rotated key |
| `ISSUE_SECRET` | `POST /issue` (Selar/Zapier bridge) | not reported; separate from direct Flutterwave checkout |

### Post-rotation live check — owner-reported, 9 Oct 2026

The owner reports replacing the exposed Worker secrets and completing a live
qualifying purchase. The success page returned a pass and reported auto-activation
for 30 days, confirming the browser `/verify` path for this transaction. The
Worker root later showed `lastWebhookMinutesAgo: 6`; the webhook handler updates
that timestamp only after signature validation, so this supports a recent validly
signed webhook, though it is not transaction-specific without the prior timestamp
or provider delivery record. The detailed Brevo event shows one attempt, 0%
delivered, and an `Error`: the configured sender `noreply@docoga.com.ng` is not
valid; Brevo instructs validating the sender or authenticating its domain. This
confirms rejection at sender validation, not a recipient-server bounce or spam
placement issue. The event's recipient has not been explicitly compared with the
checkout address; do not record or repeat either address. No code-only change to
an unverified sender will fix this. Authenticate `docoga.com.ng` in Brevo or use a
sender Brevo already verifies. Do not repeat the purchase or blindly resend.

The pass chip showed 30 days after purchase. The owner confirms the earlier
11-day chip was in the same browser. The top-up path should carry remaining days
when the Worker recognizes the previous code. Code inspection found the site kept
a cached pass displayed if `/activate` explicitly returned `invalid code` (it only
cleared on `expired`); the site now clears cache on either definitive response.
This makes a stale 11-day badge a plausible explanation, but does not prove it was
the cause or restore any lost days. The client-side fix needs a future site deploy.
No pass code, recipient address, or transaction identifier is recorded here.

A local no-charge `/resend-email` recovery path is now implemented: it resolves the
existing issued pass from its stored purchase reference, follows top-ups to the
newest active code, sends only to the email stored with that code, never returns
the code, and throttles by pass (one attempt per 60 seconds, at most three per
UTC day). It is **fail-closed** unless the Worker runtime variable
`RESEND_EMAIL_ENABLED` is exactly `true`; leave it unset/false until Brevo confirms
the sender/domain is authenticated. The success page now offers an explicit
customer-initiated resend button. The Worker/UI changes are local, tested, and not
deployed; any mail-provider acceptance is not proof of inbox delivery.

A qualifying webhook still requires a matching `verif-hash` (or valid v4 HMAC),
`charge.completed`, a successful/succeeded status, `NGN`, and amount ≥ ₦2,000. An
authenticated ₦100 event intentionally returns HTTP 200 with body `ignored` and
issues no code. A qualifying live purchase has already confirmed the redirect
issuance path; do not take another payment. After the sender is authenticated and
the security/deployment gates are satisfied, use the existing pass's explicit
resend control and verify the provider's delivery event. Local tests are not
live-delivery proof.

Not needed: the offline-batch path is unaffected. Those codes are validated by a
hardcoded set of **FNV-1a** hashes (`OFFLINE_HASHES` in `worker/index.js:49`), not by
`ISSUE_SECRET`, so they work with no secrets at all. `unlock-codes.txt` is
gitignored on purpose (paid-product inventory) and must stay out of git.

The deploy itself uses the explicit `worker/wrangler.toml` config and reached
`docoga-pass`. Both marker-gated workflows already preserve dashboard vars and
redact Wrangler output; no deployment has been run for the current local changes.
Do not deploy until the owner has attempted the old-log cleanup and confirms
production secrets are in place (see §11). Repository Actions secrets are separate;
the Arena agent cannot write them.

## 9. The site: deployed, and the 404 that was really a cache

Sessions 24–25 (B2B pricing tier, Power of Attorney page and generator) were merged
to `main` but never went live, because **Workers Builds: docoga-git** has been failing
and publishes no error text — `output.text` is null and the dashboard link is not
reachable from CI. A failing build does not take the site down; it just silently stops
the site receiving updates, which is worse.

**What the site actually is:** `docoga-git` is a **Worker with static assets**
(`has_assets: true`, `has_modules: false` per `GET /accounts/{id}/workers/scripts`),
**not** a Pages project. So plain `wrangler deploy` at the repo root is the correct
tool, and the working token can run it. `.github/workflows/deploy-site-now.yml` now
does exactly that, gated on a `[deploy-site]` commit marker, and purges the cache
afterwards. Workers Builds is therefore no longer a blocker.

**How the custom domain reaches it:** `GET /accounts/{id}/workers/domains` shows

```
hostname docoga.com.ng     -> service docoga-git, environment production, enabled true
hostname www.docoga.com.ng -> service docoga-git, environment production, enabled true
```

There are **no Worker routes** on the zone; the domain is attached as a custom domain.
DNS holds only `AAAA docoga.com.ng -> 100::` and `AAAA www.docoga.com.ng -> 100::` —
`100::/64` is Cloudflare's placeholder for hostnames it answers for itself, so those
records are expected and are not the problem.

**The 404 that was really a cache.** After deploying, `power-of-attorney-nigeria.html`
served correctly on `docoga-git.johnazani.workers.dev` but still 404'd on
`docoga.com.ng` — same worker, same files. Cause: a 404 for a page that did not yet
exist had been cached at the edge and kept being served after the file arrived.
`POST /zones/{id}/purge_cache` with `{"purge_everything":true}` fixed it immediately.
Purging is now a permanent step in the site deploy workflow.

Verified live on `docoga.com.ng` afterwards: the Power of Attorney generator with its
full preview, the *Ojugbele v. Olasoji* (1982) SC 71 registration warning and the
no-Hague-Apostille note; and all three pricing tiers — Free, Oga Pass (₦2,000 / 30
days, MOST POPULAR) and Business (Custom, annual, per team, WhatsApp quote).

## 10. CI regression fixed the same day

`QA + repo integrity` had started failing. Step-level conclusions showed the failure
was **"YouTube automation regression tests"**; repo integrity and the QA gate were
skipped because of it.

The real failure was one date-fragile test:
`test_title_carries_the_shorts_suffix_and_topic_does_not` asserted the topic equalled a
hardcoded `"Keep a Rent Paper Trail"`. The topic comes from a **date-seeded rotation**
— the next five days are *Before You Pay an Agent*, *Moving In? Record the Condition*,
*Caution Fee: Ask These Questions*, *Tenancy Agreement Checklist*, *Keep Records of
Repairs* — so that assertion was a time bomb that broke on 2026-10-09.

It was worse than it looked. The mock in `_run_daily()` patched `generate_video` to
return that topic, but `youtube_short_daily.main()` **discards** the second return
value and uses `script["title"]`. In production the two are always identical because
`generate_video` returns `script["title"]`, so the mock was decorative and the
hardcoded assertion only ever held by coincidence. The test now asserts the real
contract without naming a topic, and adds the `topic` must not contain `#Shorts`
check its name always promised but never made.

Not a bug: `error: time data '09-10-2026' does not match format '%Y-%m-%d'` on stderr
comes from `test_a_bad_date_is_a_usage_error_not_a_duplicate`, which deliberately
feeds a DD-MM-YYYY date and asserts it exits as a usage error. Correct behaviour,
just noisy.

All 48 unit tests, `pre_push_verify.sh` and `qa.py` pass.

## 11. Agent limits, deploy routes, and run-result reporting

**The Arena agent cannot write repository Actions secrets.** `gh secret set`
returns `403 Resource not accessible by integration` for this integration. Do
not ask the agent to run it or assume a secret was saved. When deploy credentials
are absent, the owner must add `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID` in GitHub → repository **Settings → Secrets and
variables → Actions**. These repository secrets are separate from Cloudflare
Worker runtime secrets such as `FLW_SECRET_KEY`, `FLW_WEBHOOK_HASH`, and
`BREVO_API_KEY`.

Deploys use the marker-gated workflows already in the repo:

- **Worker:** `.github/workflows/deploy-pass-now.yml`, triggered by a commit
  message containing **`[deploy-pass]`**.
- **Marketing site:** `.github/workflows/deploy-site-now.yml`, triggered by a
  commit message containing **`[deploy-site]`**.

The Arena session cannot read GitHub Actions run logs directly. Both workflows
therefore post captured output as a comment on **PR #11**; use that comment as
the result record, not the unreadable run log. The workflow token must have
**`pull-requests: write`** for this comment. **`issues: write` alone is not the
right permission** for commenting on a pull request (even though the workflow
uses GitHub's issues-comment REST endpoint).

**Log hygiene is mandatory.** Run `37890401771` exposed dashboard `vars` in
Wrangler's config diff. Its PR comment has been replaced with a redacted warning;
this integration received 403 when attempting to delete the Actions log. The owner
reports rotating/restoring the runtime credentials; deletion of the old run/log
remains an owner-side best-effort cleanup. Both marker-gated deploy workflows now
pass `--keep-vars` and sanitize captured Wrangler output before it reaches Actions
logs or PR comments. The payment-to-code path has since passed once; do not make
another purchase to debug email. Any future deploy must use the hardened workflow
and preserve fresh Worker Secrets.

**Owner cleanup attempt — 10 Oct 2026:** screenshot of run `37890401771`'s
summary ellipsis menu shows only **Create status badge**; **Delete all logs** is
not offered. Status: **attempted, option unavailable**, NOT confirmed deleted.
This satisfies the best-effort attempt requirement only; credential safety still
requires owner confirmation of current production Secrets and live webhook hash.
No workflow rerun or job-log download was performed during this check.

**Current deployment gate:** do not deploy this branch's local Worker/site changes
until the owner has (1) attempted best-effort deletion of run `37890401771` and
(2) confirmed the required production Worker secrets are present and correctly
configured. That confirmation remains owner-reported, not independently verified
by this session. The Brevo sender/domain must also be authenticated before anyone
sets `RESEND_EMAIL_ENABLED=true`; keep the resend path disabled otherwise. No
payment or blind resend is part of verification.

**Re-verified 9 Oct 2026 (continuation session — branch `arena/47d148f1-docoga` at
`5cc840e`):** this gate is present at the branch head, and commit `c5283e1` does not
exist in the repository (`git cat-file -t` → not a valid object). All app-side suites
were re-run locally and are green: worker unit suite (including the six `/resend-email`
tests), DOM suite 97/97, Python suite 52/52, `qa.py` 0 errors, `pre_push_verify.sh`
✅. `RESEND_EMAIL_ENABLED` is not set anywhere in the repo; it can only be enabled as
a Worker runtime variable in the dashboard. No deploy, resend, or payment was performed,
and the owner-side gates above are unchanged.

## 12. Owner-side checklist — researched 9 Oct 2026

Everything below is sourced to the vendor's own documentation (fetched 9 Oct 2026).
The agent cannot perform any of it from this session, and none of it has been done
or verified by the agent.

### 12.1 Brevo: authenticate `docoga.com.ng` (gates `RESEND_EMAIL_ENABLED`)

> **Status 10 Oct 2026: COMPLETE (owner-performed).** The new guided Brevo flow
> (Manual, Cloudflare) generated four records, all added to the existing zone and
> verified by Brevo: TXT `@` brevo-code; CNAME `brevo1._domainkey` →
> `b1.docoga-com-ng.dkim.brevo.com`; CNAME `brevo2._domainkey` →
> `b2.docoga-com-ng.dkim.brevo.com` (both DNS only, TTL Auto); TXT `_dmarc`
> `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com`. Brevo displayed **"Your
> domain has been authenticated."** The two pre-existing Worker `100::` records
> were not modified; there was no prior DMARC record, so exactly one exists now.
> Evidence is owner screenshots; not independently verified by the agent. Steps
> below remain as the reference procedure.
>
> **Sender status 10 Oct 2026 (owner-performed):** `DocOga <noreply@docoga.com.ng>`
> added under Brevo → Senders and shows **Verified** (the address behind the
> Worker's default `MAIL_FROM` and the previously observed sender-invalid event).
> The pre-existing Gmail sender remains Verified but flagged non-compliant with
> Google/Yahoo/Microsoft requirements — expected for a gmail.com From address and
> not used by the Worker. Branded-subdomain offer skipped (not required).

1. Brevo → **Settings → Senders, Domains, IPs → Domains → Add a domain** → enter
   `docoga.com.ng`. (Some accounts have a newer guided "Set up your domain" flow;
   the manual route below works regardless.)
2. Choose **manual** authentication ("Authenticate the domain yourself"). Automatic
   setup will offer to **replace** an existing DMARC record — manual is the route
   that preserves the current policy. [Brevo help, art. 12163873383186]
3. Add exactly the records Brevo generates — typically **3–4**: **Brevo code (TXT)**,
   **DKIM (1 TXT or 2 CNAME)**, **DMARC (TXT)**. Copy Brevo's names/values; do not
   guess. [Brevo help]
4. Keep **exactly one** DMARC record. Multiple DMARC records are a documented
   Brevo failure mode. If Brevo's DMARC value differs from the existing policy,
   preserve the existing policy first — Brevo's own troubleshooting frames the
   requirement as detecting *a* DMARC policy. Only if Brevo still reports the
   domain unauthenticated after the propagation window should the conflict be
   escalated (owner decision, not agent).
5. In Cloudflare, add the Brevo DKIM CNAMEs **DNS-only (grey cloud, not proxied)**
   and turn **CNAME flattening off** — both zone-wide (zone DNS settings → "CNAME
   flattening for all CNAME records") and per-record ("Flatten" off). A proxied
   CNAME, zone-wide flattening, per-record flattening, or a stray NS record all
   break CNAME verification. [Cloudflare DNS docs]
6. Wait **up to 48 hours** for propagation and verification. Check public DNS with
   Google Admin Toolbox Dig or MX Toolbox before expecting delivery. [Brevo
   troubleshooting]
7. Once the domain shows authenticated, confirm the **sender** — the exact
   `MAIL_FROM` identity the Worker sends as — is present and compliant under
   Brevo → Senders. Unauthenticated/unverified senders may be rejected or Brevo
   may substitute a sender domain; neither behavior proves inbox delivery. The
   observed event specifically reported sender-invalid. [Brevo troubleshooting]
8. Only then may `RESEND_EMAIL_ENABLED` be set to exactly `true` as a Worker
   runtime variable — in the intentional gated release, never before.

### 12.2 Cloudflare Worker secrets + Flutterwave webhook hash (gates deploy)

> **Observed 10 Oct 2026 (owner screenshots, no edits):** production `docoga-pass`
> lists `BREVO_API_KEY`, `FLW_SECRET_KEY`, `FLW_WEBHOOK_HASH` as encrypted Secrets;
> variables `PAYMENT_URL`, `PROVIDER`, `SITE_URL`; KV binding `KV` → `docoga-kv`.
> `ISSUE_SECRET`, `MAIL_FROM`, `RESEND_EMAIL_ENABLED` are not listed. The owner
> subsequently replied **Yes** that all three encrypted Secrets are the replacement
> credentials saved after the exposed log (owner-confirmed currentness, not
> independently verified). In a separate subsequent reply the owner confirmed
> the LIVE webhook hash is the same one saved as `FLW_WEBHOOK_HASH` (not
> independently verified; no value recorded).
> Investigate `/issue` bridge use
> before any ISSUE_SECRET remediation; do not choose a random replacement.
> No deployment or resend authorized by this inspection.

- Workers & Pages → `docoga-pass` → Settings → Variables and Secrets: confirm
  `FLW_SECRET_KEY` (or `FLW_CLIENT_ID`/`FLW_CLIENT_SECRET`), `ISSUE_SECRET`,
  `BREVO_API_KEY`, and `FLW_WEBHOOK_HASH` are present. Names only — never values in
  chat, git, or logs.
> **Latest LIVE webhook screenshot, 10 Oct 2026:** V3 Live webhooks with masked
> hash and Enable v3 webhooks checked. Earlier cropped screen said V4; no version
> switch/save is confirmed. The URL path is clipped in the screenshot, but the
> owner subsequently confirmed the complete URL:
> `https://docoga-pass.johnazani.workers.dev/flw-webhook`. URL and LIVE hash match
> are now owner-confirmed, not independently verified. Recipient comparison and
> `/issue` bridge status remain open; no release authorization. Do not use
> Save, Switch to V4 webhook, or dashboard resend/test to inspect configuration.

- Flutterwave dashboard → **Settings → Webhooks** → the **secret hash** field is
  what the Worker's `FLW_WEBHOOK_HASH` must equal. **Live and test environments
  have separate hashes** — the Worker needs the **live** one. [Flutterwave support,
  "What is a Secret Hash?"]
- The earlier deploy log exposed these values; the owner reports rotating them.
  That rotation is **owner-reported and not independently verified**. Confirm the
  Worker holds the *current* dashboard values based on completed setup. Saved
  Secrets are hidden, so presence alone is not correctness proof; do not overwrite
  rotated credentials needlessly. Secret edits use Deploy and are production
  changes. Never retype values into chat.

### 12.3 GitHub Actions run `37890401771` — log cleanup

- Best-effort deletion of the run and its logs (Actions → the run → delete run /
  **⋯ → Delete all logs**). The integration received 403 when attempting this;
  owner-side write permissions are required. Report success or best-effort failure
  honestly. Deletion is not credential revocation; the rotation remains owner-
  reported, not independently verified.

### 12.4 GA baseline (corrected after code inspection)

Pull sessions/users, channels and **Engagement → Landing page** by sessions from
GA `G-GO8VZB3R28`. Pages and screens reports views, not entry pages. The repo has
homepage analytics but NO GA tag or verified-payment event in success.html.
Success-page visits would not prove payment even if tagged. Do not call a proposed
pricing/click/success funnel or views/sessions a measured purchase conversion rate.
Proper privacy-safe verified-payment tracking is an app-side follow-up.

### 12.5 Exact owner clicks and pre-release caveats

See `docs/OWNER_CLICK_GUIDE.md` for researched direct links, classic/new Brevo UI,
field mapping, Free-plan flattening controls, single preserved DMARC/reporting tags,
private recipient comparison, and STOP-before-release checkpoints. Cloudflare
flattening returns IP addresses instead of the CNAME; it does NOT convert to TXT.
Do not use a generic DMARC reporting value in place of account instructions.

**Updated 10 Oct 2026 — repaired on session branch, not released:** Worker deploy
now propagates DEXIT; manual dry-run runs an isolated no-credential build and skips
all production/API/probe/report steps. Explicit worker config throughout, no
ambiguous dry-run config probe; verbose token fingerprints/account dumps removed.
Both marker deploy scripts sanitize captured raw output, fail on sanitizer errors,
and remove raw files using EXIT traps. Worker live probe is now /activate without
a code (400/code required before KV access), NOT /verify. Python 57/57 including
stub-executed exit/cleanup/dry-run regressions; Worker/DOM green; real local Worker
build --dry-run passed. Historical green runs remain insufficient deployment proof.
Legacy deploy-pass.yml/build-check.yml are NOT the release route and have not been
hardened by these fixes; do not dispatch them or rerun old commits.

### 12.6 Latest gate state — 10 Oct 2026

- Brevo domain Authenticated and default sender Verified (owner screenshots).
- Old Actions logs: deletion attempted, option unavailable; NOT confirmed deleted.
- Three production Secrets: encrypted per screenshots, replacements current per
  owner confirmation. LIVE webhook URL and hash equality owner-confirmed.
- Recipient: **matches** between existing qualifying purchase customer/checkout and
  OLD Brevo failed event, from owner screenshots; no private values recorded.
  Old Error is historical, not a new failure after authentication.
- ISSUE_SECRET absent: code/tests show only /issue uses it and fails closed without
  it; Flutterwave does not require it. Historic manual/Selar bridge usage needs
  owner clarification before closing this dependency; never randomly replace it.
- Resend flag absent from supplied table; no enablement. No deployment authorization.
  After bridge scope and approval: marker Worker then site, intentional enablement,
  ONE existing-pass resend, NEW event plus actual receipt. No payment or blind retry.
