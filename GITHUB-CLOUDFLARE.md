# GitHub → Cloudflare Pages — Step-by-Step Connection Guide

**Why this way?** Once connected, every push to GitHub deploys to your live site
automatically. Edit a price on your phone via github.com → site updates in about
a minute. No commands, no dragging folders, ever again.

**Status as at 3 Oct 2026 (verified, not assumed):**

| Fact | How it was verified |
|---|---|
| A Cloudflare Pages project named **`docoga`** exists | `docoga.pages.dev` resolves to 172.66.44.157, while a nonsense `*.pages.dev` name returns NXDOMAIN — so the zone is not a wildcard and the project is real |
| **`docoga.com.ng` is on Cloudflare** | DNS returns Cloudflare anycast IPs `104.21.33.145` / `172.67.146.104` + `2606:4700::/32` IPv6 — not Netlify's old `75.2.60.5` |
| The Pages project is **NOT** connected to this repo | The commit pushed 3 Oct (`43d644c`) carries a `netlify/docoga/deploy-preview` status and three `netlify` check-runs — and **zero** Cloudflare statuses. A Git-connected Pages project reports a deployment status on every branch commit, previews included |

So the site you see today was **hand-uploaded**. It will not change when you
push to GitHub, and it will silently drift from the repo. Step 2 below fixes
that.

---

## Step 1 — Make sure the repo is on GitHub ✅ (already done)

Repository: `https://github.com/johnAzani/docoga` — **private**. Keep it private.

## Step 2 — Create a NEW Git-connected Pages project

> **⚠️ Read this first — it is a Cloudflare limitation, not a preference.**
> Cloudflare's own Direct Upload docs say: *"If you choose Direct Upload, you
> cannot switch to Git integration later. You will have to create a new project
> with Git integration to use automatic deployments."*
> There is **no** "Connect to Git" button on a Direct Upload project. Do not go
> looking for one — it does not exist. The existing `docoga` project has to be
> replaced.

Do these in this order. The domain is the fragile part, so it moves last.

1. **Note what the old project is serving.** Workers & Pages → **`docoga`** →
   Custom domains. If `docoga.com.ng` is listed there, that is what you are
   about to move.
2. **Create the new project:** Workers & Pages → **Create → Pages →
   Connect to Git**.
3. Authorize Cloudflare's GitHub App. If it asks which repositories it may
   access, choose **Only select repositories** and pick **`johnAzani/docoga`**.
   *(This is the single most common reason a connection silently does nothing —
   the app gets installed but is never granted the repo.)*
4. Set exactly these:

   | Setting | Value |
   |---|---|
   | **Project name** | `docoga-git` (you can reuse `docoga` only after deleting the old one) |
   | **Production branch** | `main` |
   | **Framework preset** | *None* |
   | **Build command** | *(leave completely blank — there is no build step)* |
   | **Build output directory** | `site` |
   | **Root directory** | `/` (default) |

5. **Save and Deploy.** Wait for the first build to go green.

> **⚠️ The `site` output directory is a security setting, not a preference.**
> Cloudflare publishes *only* what you name there. If this is ever left blank or
> set to `/`, Cloudflare will publish the **repository root** — `PLAN.md`,
> `AUTOMATE.md`, `DOCOGA-RISK-LOG.md`, the `worker/` source, and (on your
> machine) `unlock-codes.txt`, which is ₦374,000 of sellable inventory. Only
> `site/` is public material.

## Step 3 — Move the custom domain onto the new project

1. **Old `docoga` project → Custom domains → remove `docoga.com.ng`** (and
   `www.docoga.com.ng`). Cloudflare will not let the same hostname sit on two
   projects at once.
2. **New project → Custom domains → Set up a custom domain** → `docoga.com.ng`,
   then `www.docoga.com.ng`.
3. Because the domain already resolves to Cloudflare, this should attach with no
   DNS changes needed. Cloudflare issues the SSL certificate automatically.
4. Check `https://docoga.com.ng` loads the new build. Only then:
5. **Delete the old `docoga` project** — which frees the name if you want to
   rename the new one to `docoga` later.

> You *can* still push an emergency build by hand after this: a Git-integrated
> project accepts `wrangler pages deploy`. What you lose is dashboard
> drag-and-drop, which you no longer need.

## Step 4 — Disconnect Netlify (do this last)

Netlify's GitHub App is **still installed on this repo and still building it** —
verified 3 Oct 2026: the commit `43d644c` carries a `netlify/docoga/deploy-preview`
status pointing at `https://deploy-preview-2--docoga.netlify.app`. Leaving it
connected means a second platform keeps building your private repo for nothing.

1. `app.netlify.com` → site **`docoga`** → **Site configuration → General →
   Delete this site** (or at minimum **Build & deploy → disconnect the repo**).
2. GitHub → `github.com/johnAzani/docoga` → **Settings → Integrations →
   GitHub Apps** (or **Installed GitHub Apps**) → **Netlify** → **Configure** →
   remove access to `johnAzani/docoga`.
3. Confirm it is gone: `gh api repos/johnAzani/docoga/commits/<new-sha>/status`
   should show a `cloudflare/pages` context and **no** `netlify/...` context.

> `netlify.toml` was deleted from the repo on 3 Oct 2026 as part of this
> migration. Do that **after** Netlify is disconnected, never before — while
> Netlify is still connected it is the file pinning Netlify's publish directory
> to `site/`.

## Step 5 — Verify it is actually wired (30 seconds)

Push anything to `main`, then check for a Cloudflare deployment status:

```bash
gh api repos/johnAzani/docoga/commits/$(git rev-parse HEAD)/status \
  --jq '[.statuses[] | {context, state, target_url}]'
```

You want to see **`cloudflare/pages`** with `"state":"success"` and a
`*.pages.dev` target URL. If you see `netlify/...` instead, Step 4 is not done.
If you see **nothing at all**, the Git connection did not take — redo Step 2.

Or the no-commands version: open the commit on github.com and look at the ✅/❌
markers under the commit message.

## Optional — deploy from the command line instead

If you ever need to push a build without Git (emergency, or the connection
breaks):

```bash
npm i -g wrangler
wrangler login                      # browser auth, once
wrangler pages deploy site --project-name=docoga
```

This uploads the `site/` folder directly. It does **not** replace the Git
connection — Git is the normal path, this is the escape hatch.

---

## Why Cloudflare and not Netlify

Both are free and both work. Cloudflare is the better fit here because:

- **The pass-delivery Worker is already on Cloudflare.** Same dashboard, same
  account, one place to look when something breaks at 2am.
- **The domain is already on Cloudflare**, so SSL and DNS are in one panel.
- **Cloudflare's free tier is more generous** on bandwidth, which matters when
  the SEO pages start pulling mobile traffic from across Nigeria.
- **One fewer third party** holding a build of your private repo.

---

## Workers Builds — why every non-`main` branch shows a red check

**Symptom.** Every PR carries a failing check, **Workers Builds: docoga-git**,
while the identical push to `main` is green. The site itself is unaffected:
`main` deploys fine, and this branch's own `Verify` workflow is green.

**What was actually tested (8 Oct 2026), from the GitHub check-runs API:**

| Commit | Branch | Workers Builds |
|---|---|---|
| `b84ecfb` | `main` | ✅ success |
| `243309d` | `arena/b51ecc68-docoga` | ❌ failure |
| `8374e21` | `Zip` | ❌ failure |

**One popular theory is wrong.** These builds run `npx wrangler deploy` from
the repo root against `wrangler.jsonc`, and Workers Builds derives a preview
URL from the branch name — so the obvious suspect was the `/` in
`arena/b51ecc68-docoga`, which cannot appear in a hostname. **`Zip` has no
slash and failed too.** The branch name is not the cause.

What is left is the only thing that actually differs between those rows:
`main` is a **production** deployment and every other branch is a **preview**
deployment. The deploy target is identical in all three cases — `wrangler.jsonc`
publishes `./site` and declares no bindings, no secrets and no build command —
so nothing in this repository can be changed to make a preview deploy succeed.
This one is the account's preview configuration, not the code.

**Fix (owner-side, ~30 seconds, dashboard only):**

1. Cloudflare dashboard → **Workers & Pages** → `docoga-git` → **Settings** →
   **Builds** (or *Workers Builds* → the connected repo).
2. Set **Production branch** to `main`.
3. Turn **off** builds/preview deployments for **non-production branches**.

That is the right setting for this repo regardless of the error: every
non-`main` branch here is a throwaway working branch, there is exactly one
deployable target (`./site`), and a preview URL is never shared with anyone.
Keeping previews on buys nothing and paints every PR red.

**If you would rather keep previews,** open the failed build from the check
(it links straight to the log in the dashboard) and read the deploy step. The
URL is not reachable from a coding sandbox — egress is limited to
`github.com`, `api.github.com`, `registry.npmjs.org` and `pypi.org` — so the
log line itself could not be read from here, and the report above stops at
what the GitHub API can prove.

**Do not** "fix" this by pointing `assets.directory` anywhere but `./site`, by
adding bindings to `wrangler.jsonc`, or by deleting `wrangler.jsonc`. The
directory line is a security setting: pointed at `/` it would publish
`PLAN.md`, `worker/` and `unlock-codes.txt` (₦374,000 of inventory).
