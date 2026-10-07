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
QA gate → commit → push → wait for Netlify deploy → live verification.

## What the gates check

| Gate | Checks |
|---|---|
| `tools/qa.py` (pre-push) | Every inline script in every HTML file parsed by `node --check` · no placeholders · config complete & consistent across pages · canonical/og/sitemap/robots agree · every JS-referenced id exists · script tags balanced · worker parses · wrangler KV id real · **secret-leak scan** (nothing from `.worker-secrets.env` in deployable files) |
| `tools/verify_live.py` (post-deploy) | Live pages fetch · **live JavaScript parses** · live config values correct · SEO wiring live · Worker healthy |
| `.git/hooks/pre-push` | Runs qa.py automatically on `git push` (belt & suspenders; may need reinstall after a fresh sandbox — see below) |

## Sandbox note (for the AI operator)

- `.git/config` and possibly `.git/hooks/` do not survive workspace snapshots.
  After a fresh session: `git config user.name "DocOga"`,
  `git config user.email "docoga@users.noreply.github.com"`, reinstall the
  pre-push hook (`cp tools/pre-push .git/hooks/pre-push && chmod +x ...`),
  re-add the remote with the user's token when pushing.
- `tesseract` and `wrangler` need reinstalling after a fresh session
  (`sudo apt-get install -y tesseract-ocr`, `npm i -g wrangler`).
- Secrets live in `.worker-secrets.env` (gitignored). NEVER paste secret
  values into files that ship. The qa.py leak-scan enforces this.

## Incident log

| Date | What happened | Root cause | Prevention now in place |
|---|---|---|---|
| 19 Sep 2026 | `WORKER_URL` config fill stripped the `//` comment marker → raw text in JS → `SyntaxError` → every interactive feature on the live site dead ~20 min. Caught by owner testing on phone, not by any automated check. | Edit verified at line level; the "verification" grep even displayed the broken line and it was not recognized. | qa.py step 1 (full-script parse of every page) + verify_live.py (parse the LIVE script) + ship.sh pipeline + pre-push hook. |