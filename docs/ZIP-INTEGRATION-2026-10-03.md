# Zip Branch Integration — 2026-10-03

## Source
- Branch: `Zip` (commit 8374e218)
- File: `docoga-github-repo.txt.zip` (51089 bytes)
- Unzipped to: `/tmp/scratch-docoga` (scratch folder, live repo untouched)

## Diff vs main (f371a1a)

The zip contains 17 files from 18 Sep 2026 snapshot:

- README.md, .gitignore, netlify.toml, PLAN.md, DEPLOY.md, AUTOMATE.md, GITHUB-NETLIFY.md
- site/{index.html, privacy.html, robots.txt, sitemap.xml, success.html, terms.html}
- worker/{index.js, wrangler.toml}

Compared to main (3 Oct 2026, 122825-byte index, 9 tools, Cloudflare Pages, Brevo, daily cron, 7 guide pages, 24 state pages):

- All 17 files in the zip are **older** than main's equivalents (timestamps 18 Sep vs 3 Oct).
- No `contest-creation automation` string found in zip content nor in git history (`git log -S contest`, `grep -ri contest`).
- Scratch has only 4 tools (agreement, notice, receipt, invoice) vs main's 9 ( + employment, caution, demand, payslip, warning).
- Scratch uses Netlify + Resend + green #046A38; main uses Cloudflare Pages + Brevo primary + blue #0047E1, daily renewal reminders, state guides, `wrangler.jsonc`, `tools/gen_guide_pages.py`, etc.
- Scratch's GITHUB-NETLIFY.md and netlify.toml are intentionally **not** integrated — Netlify was retired 3 Oct 2026 per GITHUB-CLOUDFLARE.md (verified via `tools/check_deploy.sh` and QA step 12).
- `site/index.html` diff: +102 lines unique to scratch are colour/comment/style changes, not functional; -745 lines unique to main are the 5 extra tools + SEO guide wiring.
- `worker/index.js` diff: scratch is the simplified 203-line Sep-18 worker (Resend only, no Brevo fallback, no dailyRenewalReminders, no provider chain, no fence/top-up logic); main's 500+ line worker is newer and live-proven via workertest.mjs (8/8 green).

## Integration decision

- Keep **all** of main's newer logic (Cloudflare Pages, Brevo, 9 tools, guide pages, QA steps 11-12, wrangler.jsonc, etc.) — QA green on main.
- Do **not** regress to scratch's older files.
- The zip file itself (`docoga-github-repo.txt.zip`) is an upload artifact and stays only on the `Zip` branch; it is not committed to `main` or `arena/*` (it is gitignored via `.gitignore`).
- Scratch folder `/tmp/scratch-docoga` retained as evidence of the diff (not committed).

## QA
- `python3 tools/qa.py` green on both `main` and `arena/01a10093-docoga` (0 errors, 2 warnings — missing .worker-secrets.env, jsdom not installed — expected on fresh clone).
- Verified via `tools/tests/workertest.mjs` (8/8) and index.html node --check.

## Result
- No file from the zip was newer, so the live repo remains at main's tip (f371a1a).
- This commit records the integration review so the PR has a non-empty diff and can be merged.
