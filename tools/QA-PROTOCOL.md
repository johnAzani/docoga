# DocOga QA Protocol — Non-Negotiable Rules

> Written 19 Sep 2026, the day a one-character bug (a stripped `//` comment
> marker) took down every button on the live site for ~20 minutes.
> Root cause: the edit was verified at LINE level, not FILE level.
> This protocol makes that class of error impossible to ship again.

## The Two Rules

1. **NO PUSH unless `python3 tools/qa.py` exits green.** No exceptions, no
   "it's a tiny change". Especially not "it's a tiny change" — that's exactly
   what the last incident was.
2. **No "it's live" claim unless `python3 tools/verify_live.py` is green.**
   This fetches the real production pages and syntax-parses the real
   JavaScript customers' browsers will execute.

## The One Command

```bash
GITHUB_TOKEN=github_pat_xxx tools/ship.sh "commit message"
```

Runs the full pipeline and refuses to finish if any stage fails:
QA gate → commit → push → wait for the Cloudflare Pages deploy → live verification.

## What the gates check

| Gate | Checks |
|---|---|
| `tools/qa.py` (pre-push) | Every inline script in every HTML file parsed by `node --check` · no placeholders · config complete & consistent across pages · canonical/og/sitemap/robots agree · every JS-referenced id exists · script tags balanced · worker parses · wrangler KV id real · **secret-leak scan** (nothing from `.worker-secrets.env` in deployable files) |
| `tools/verify_live.py` (post-deploy) | Live pages fetch · **live JavaScript parses** · live config values correct · SEO wiring live · Worker healthy |
| `.git/hooks/pre-push` | Runs qa.py automatically on `git push` (belt & suspenders; may need reinstall after a fresh sandbox — see below) |
| `tools/tests/workertest.mjs` (in qa.py step 9) | Real worker code + mock KV: expiry, device fence, hostile records, top-up chain, and the **payments ` /verify` path** (mocked FLW v4: mint, email capture, idempotency, underpay/wrong-currency/failed all rejected with zero codes). No deps, runs everywhere. |
| `tools/tests/domtest.mjs` (in qa.py step 9) | Executes the REAL `site/index.html` in jsdom: 12 routes, all 9 tools, hostile-input XSS, print, share, saved docs, drafts, pass activation/top-up/fence/magic links, corrupt storage, live config values. Needs `npm i jsdom`; **auto-skips** (never blocks) when jsdom is absent. |
| qa.py step 10 | Anchor integrity: every in-page `href="#x"` must resolve to a real `id` (or the SPA's `page-x` route). Catches dead nav/CTA links. |
| qa.py step 12 | Hosting guard: no `netlify.toml` or `.netlify` in the repo, no Netlify references in deployable `site/` files, and README still documents Cloudflare Pages + the `site` publish-directory warning. Netlify was retired 3 Oct 2026; the silent failure this prevents is the next operator being sent to the wrong dashboard while production stops updating |
| qa.py step 11 | Site-wide schema & deep-link integrity across **every** page, not just index.html: every JSON-LD block parses (a broken FAQPage silently costs the rich snippet) · every absolute `…/#route` deep link is a real SPA route (`#code=` magic links excluded by design) · every sitemap `<loc>` is a file we actually ship. Added 3 Oct 2026 with the guide pages — negative-tested: injecting a bad brace, a dead route and a phantom loc each fail the gate with exit 1. |

## Optional dependencies for the app-level suites

The browser suites (`debugsweep.js`, `magictest.js`, `fencetest.js`, `modeltest.js`,
`newtoolstest.js`) need Chromium via puppeteer-core; when no browser binary exists they simply
cannot run. That used to leave **no** app-level safety net at all. `domtest.mjs` closes that hole:
it needs only jsdom (`npm i jsdom`, or `JSDOM_PATH=/path/to/jsdom`). It is deliberately
skip-safe — a missing jsdom prints a notice and exits 0, so a fresh clone is never blocked.

## Sandbox note (for the AI operator)

- **First thing in a fresh workspace:** `npm ci` at the repo root. The root
  `package.json`/`package-lock.json` pin `jsdom`, which is what makes
  `tools/tests/domtest.mjs` run for real instead of auto-skipping. Without it
  the gate still passes but the app-level suite silently does not execute.
- `.git/config` and possibly `.git/hooks/` do not survive workspace snapshots.
  After a fresh session: `git config user.name "DocOga"`,
  `git config user.email "docoga@users.noreply.github.com"`, reinstall the
  pre-push hook (`cp tools/pre-push .git/hooks/pre-push && chmod +x ...`),
  re-add the remote with the user's token when pushing.
- `tesseract` and `wrangler` need reinstalling after a fresh session
  (`sudo apt-get install -y tesseract-ocr`, `npm i -g wrangler`).
- Secrets live in `.worker-secrets.env` (gitignored). NEVER paste secret
  values into files that ship. The qa.py leak-scan enforces this.
- **Everything is pushed to GitHub as it is produced** (owner's standing
  instruction, 3 Oct 2026) so a new workspace or a different agent can pick up
  exactly where the work stopped. Session work goes to the session branch and
  on to `main` by pull request — **Cloudflare Pages** deploys `main` (output dir `site`).

## Incident log

| Date | What happened | Root cause | Prevention now in place |
|---|---|---|---|
| 19 Sep 2026 | `WORKER_URL` config fill stripped the `//` comment marker → raw text in JS → `SyntaxError` → every interactive feature on the live site dead ~20 min. Caught by owner testing on phone, not by any automated check. | Edit verified at line level; the "verification" grep even displayed the broken line and it was not recognized. | qa.py step 1 (full-script parse of every page) + verify_live.py (parse the LIVE script) + ship.sh pipeline + pre-push hook. |
| 1 Oct 2026 | Fresh-clone audit: a corrupt `docoga_docs` value (`'null'`) made `getDocs()` return `null`, so `init()` threw and the whole app booted dead for that browser — permanently. Same audit found qa.py crashed (silently skipping the secret scan) whenever `.worker-secrets.env` was missing, a typo'd SMTP2GO header, and `/verify` minting codes with no email (renewal reminders could never reach redirect-path buyers). | Storage was read with `JSON.parse(...) || '[]'` — which does not protect against a stored literal `null`; the other three were unexercised code paths. | `getDocs()` now type-guards; qa.py fixed + two dependency-light suites wired into the gate (step 9) + anchor-integrity gate (step 10); corrupt-storage and payment-path tests now run on every push. |
