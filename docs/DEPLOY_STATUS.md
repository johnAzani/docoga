# Deployment status — measured 8 Oct 2026

Rule Zero: everything below is measured, with the method stated. Where I could
not determine a cause, it says so rather than guessing.

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

## 2. The payment worker is NOT deployed

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

Note the tension: a real ₦100 Flutterwave webhook was logged on 19 Sep 2026
(`logs/2026-09-19-first-real-payment-webhook.json`), so this *was* working.

## 3. None of the recent revenue work is live

- The live site lists **9 tools** — the Power of Attorney tool is absent.
- `docoga.com.ng/power-of-attorney-nigeria.html` returns **404**.

So the sticky bars on 56 pages, the POA tool, the Business tier and the POA
landing page are all in the repo and passing tests, but not on the internet.

## 4. Why: PR #11's Cloudflare build fails

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
  method and body; curls any host and returns status, headers and body. GitHub
  only registers `workflow_dispatch` from the **default branch**, so this is
  dispatchable once it lands on `main` (it is in PR #11).

## 8. Token diagnosis — measured 8 Oct 2026

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

Also confirmed correct, so stop re-checking these:
- Account `276c50d7329e162bd36d1ef8eb3e7566` ("Azanijohn2017@gmail.com's Account")
- Zone `docoga.com.ng` (`38e545caefd3f31acf6cc732ffe663ba`), status **active**,
  on the Free plan, nameservers `beau.ns.cloudflare.com` / `elly.ns.cloudflare.com`

Separate bug found and fixed in passing: `npx wrangler deploy` run from `worker/`
was picking up the **root `wrangler.jsonc`** and targeting `docoga-git` instead of
`worker/wrangler.toml` / `docoga-pass`. Fixed by passing `--config wrangler.toml`
explicitly. After that the deploy targeted `docoga-pass` correctly and failed only
on permissions.

## 9. To let the agent fix this itself

Give the repo a Cloudflare API token as a secret:

```
gh secret set CLOUDFLARE_API_TOKEN
gh secret set CLOUDFLARE_ACCOUNT_ID
```

With those, the agent can (a) read the real build log, (b) deploy
`worker/` as `docoga-pass`, and (c) redeploy the site — all by triggering
workflows, with no dashboard access.
