# DocOga Session Context — THE SINGLE SOURCE OF TRUTH
*If you're reading this in a new session: start here. This is everything. Read this, then continue naturally.*

---

## 🔴 RULE ZERO — RESEARCH BEFORE ACTION (LOCKED 8 Oct 2026 — NEVER IGNORE)

**"I want you to always do a very very indepth research to the thinnest details
first, before answering any question or doing anything. Lock it in."** — the user,
stated twice in one session, so it is permanent.

This outranks every other rule in this file. It is the user's explicit standing
order, not a preference, and it applies to:

1. **Every question**, however small. Do not answer from memory or from a
   plausible-sounding pattern. Go and check.
2. **Every change**, before a line of it is written. Measure or source the
   current state first; then act.
3. **Every plan** inherited from a previous session. Session 19 proved why:
   the plan said "expand state pages 12 → 37". Researching first showed the 48
   existing pages were 94.2% duplicates of each other and would have been
   deindexed. **The research reversed the plan.** Had the plan been executed
   first and researched second, it would have been the most damaging thing
   available to do to this site.

### What "to the thinnest details" means here, concretely

- **Go to the primary source.** A state's own judiciary site or official laws
  portal beats a blog, a law-firm explainer, and an academic footnote. In
  session 19 this produced section-level text for Lagos (No. 14 of 2011),
  Edo (Edict No. 4 of 1977), Cross River (Cap. R3) and Kwara (1995).
- **Quote the section, not the summary.** "Six months" is a summary. "six (6)
  months notice for a yearly tenant — s.13(1)(e)" is a detail.
- **Tier every claim by confidence** (A: primary statute + sections; B: named
  statute from practitioner/academic source; C: single source; D: verified
  negative; E: nothing verified) and publish the tier, not just the claim.
- **Record the disagreements.** Where sources conflict, say so and say which
  is preferred and why. Do not silently pick one.
- **Write down what you could NOT verify.** A dossier with 20 honest
  "nothing found" entries is worth more than 37 confident guesses.
- **Measure before building.** If the task is "add more X", measure the X that
  already exists (`tools/audit_state_pages.py` exists for exactly this).

### Operational consequence

Research happens in the **same turn**, before the tool call that builds. If
research is still incomplete, the correct output is "here is what I have
verified so far, and here is what is still open" — not a confident answer
filling the gaps with invention.

---

## 🔴 CRITICAL INSTRUCTION (LOCKED — NEVER IGNORE)

**This file is a LIVING DOCUMENT. It MUST be updated at the end of EVERY work session.**

Rules:
1. **START of session:** Read this file FIRST. Then check `git log --oneline -10`. Continue naturally.
2. **END of session:** Update this file with everything that was done. Commit and push.
3. **NEVER** end a session without updating this file.
4. **NEVER** say "let me check the repo" — you already know everything here.
5. **ALWAYS** update the "Last Session" section, "What's Been Built" section, and "What's Next" section.
6. **ALWAYS** commit the update: `git add docs/SESSION_CONTEXT.md && git commit -m "Update SESSION_CONTEXT.md — [summary]" && git push origin main`
7. **FIRST, CHECK THE BRANCH IS WHERE YOU LEFT IT.** See the incident note below.
   The sandbox can reset the local branch pointer to the base commit between
   sessions while keeping the working tree. Recover with
   `git fetch origin && git reset --mixed origin/<branch>` before doing anything
   else — and never force-push to "fix" it.

This ensures the next session feels like the same person continuing.

---

## 🚨 OPERATIONAL NOTE — 12 Oct 2026: the site↔worker seam was half-published (fixed same day)

`docoga.com.ng` was serving the merged build (PR #15) while the worker the site
calls (`site/index.html:1095` → `https://docoga-pass.johnazani.workers.dev`) was
still the 11 Oct `f83be6e` revision. Every worker route the *new* site calls
answered `{"ok":false,"error":"not found"}` in production: `/business/teams`,
`/business/login` (POST + GET), `/business/team*`. The dashboard-editor check
that said "the worker already has the new code" was **true but insufficient** —
`/business/waitlist` genuinely is in `f83be6e`; the Phase 1–4 routes are not.

Root cause of the miss: the last *successful* gated deploy was `f83be6e`
(11 Oct 12:22). Phases 1–4 changed `worker/index.js` at 12:30–13:21 and every
push after that carried no `[deploy-pass]` marker, so every run after them is
`skipped` — a green "worker is deployed" belief on a stale revision.

Fixed 12 Oct 17:21 (see the branch `arena/1913fcb7-docoga` session record):
`Deploy docoga-pass (gated)` run **38283647993**, version
**`8bddd363-b819-4b90-a8a5-24e373e5f2ed`**. Verified live: `/business/team` →
**`401 sign_in_required`** (also proves `TEAM_AUTH_SECRET` is set),
`/business/login?token=bad` → **`400 invalid link`**, `/business/team/invoices`
→ 401, `/business/invoice/*` → "sign in required" HTML; retail `/verify` and
`/activate` answer exactly as before. Full record:
`docs/PRE_LAUNCH_RUNBOOK.md` §2 correction + §7 deploy log.

**Three things this exposed, worth keeping:**
1. A gated workflow reporting `success` is **not** proof of a deploy — its
   deploy step runs `set +e` and only echoes `deploy_exit=…`. Read that line.
   (In run 38283647993 it was `0`, and the publish did happen.)
2. **The probe tool caches.** A repeat probe of an unchanged URL can return the
   pre-deploy body and look like "still broken". Cache-bust (`?cb=123`) — the
   worker ignores query params for routing (`url.pathname`).
3. `gh workflow run` is unavailable to the session (`actions: write` → HTTP 403
   "Resource not accessible by integration"), so `net-probe.yml` cannot be
   triggered and the sandbox cannot POST. **GET probes via `fetch_page` are the
   agent's live-verification path**; POST probes remain owner-side (`reqbin.com`).

---

## 🚨 OPERATIONAL NOTE — 8 Oct 2026: the sandbox can reset the local branch

Between turns the local branch pointer was rolled back from `ec97606` to the
base commit `b84ecfb`. **The working tree kept every file**, so nothing was
lost on disk, and **all commits were still on GitHub** — but the local branch
looked like the session's work had never happened.

**Do not "fix" this by force-pushing.** That would have destroyed the work.

Recovery, in this order:

```
git fetch origin
git reset --mixed origin/arena/b51ecc68-docoga   # HEAD + index; working tree untouched
git status                                       # should be clean
```

`--soft` is not enough: it moves HEAD but leaves the index holding the old
base state, which makes git report your new files as staged deletions. `--mixed`
resets HEAD and index together and leaves the working tree alone, which is
exactly right when the files on disk are the ones you want.

**Verify before you act.** `git log --oneline -1` at the start of a turn is
worth two seconds.

---

## 🚨 INCIDENT — 6 Oct 2026: `main` was force-pushed and orphaned 124 commits

**Read this before touching `main`.**

`main` was force-pushed to an orphan root commit (`f7fc227`), discarding the
real lineage. Two independent lines were orphaned:

- `e7eb57d` — **124 commits / 157 files**: the content & growth system
  (`BRAND_STYLE`, `GROWTH_JOURNAL`, `BUSINESS_PLAN`, `HOOK_LEDGER`,
  `GROWTH_ENGINE`, `DESIGN_SYSTEM`) and the tool suite (`rebuild_ep1.py`,
  `yt_upload_long.py`, `yt_suggest.py`, `weekly_report.py`, `vector_kit.py`,
  `tts_harvest.py`, `tts_batch_dd3.py`, `qa.py`, `verify_live.py`)
- `85097d7` — the Oct 6 automation line (53 commits): the 5 social workflows,
  `tools/{yt,fb,ig}_publish.py`, `youtube_queue.json`, and this file

Neither descends from the other. Both were recovered with
`git fetch origin <sha>` — GitHub still serves orphaned commits, **but only
until they are garbage-collected.** They are now anchored to
`arena/a0d5b259-docoga`.

**✅ RESOLVED 7 Oct 2026 — merged to `main` as `bfa555b`, with a merge commit
(never squash: squashing would have re-flattened exactly the lineage that was
lost).** Verified after the merge, not just asserted:

- `main` is now **138 commits / 179 files** (was 56 / 112)
- `e7eb57d`, `85097d7`, `c184d6a` and `51f5444` are **all ancestors of `main`**
- `git ls-tree` diff of pre-merge `main` vs post-merge `main`:
  **zero files dropped**
- `tools/pre_push_verify.sh` ✅ and `tools/qa.py` 🏆 green on the merged tree
- CI `Verify` run `37669606893` — green on the merge commit itself

**Why nobody noticed:** `tools/pre_push_verify.sh` tested file existence with
`if git ls-tree HEAD <path>`. `git ls-tree` **exits 0 even when the path does
not exist** — it just prints nothing. Every check passed unconditionally, so
the script printed `✅ ALL CHECKS PASSED — Safe to push!` on a tree missing
all 12 files it checks. It was also never wired to anything.

**Fixed:** existence is now tested with `git cat-file -e`; the script gained a
history-safety check that flags refs with no common ancestor vs `origin/main`
and lists what a force-push would delete; `tools/pre-push` runs it alongside
`qa.py`; and `.github/workflows/verify.yml` runs both in CI on every push and
PR, where `--no-verify` cannot bypass them.

**Rules that follow from this:**
1. Never `git push --force` to `main`.
2. If a branch has no common ancestor with `main`, merge with
   `--allow-unrelated-histories` — do not overwrite.
3. Run `bash tools/pre_push_verify.sh` before any push, and trust it now.

---

## Who You're Talking To

You are continuing a conversation with the owner of **DocOga** (johnAzani/docoga). The owner is building an autonomous social media content creation and legal document generation platform for Nigerian tenants. Treat every conversation as a continuation. Never start from scratch. Never say "let me check the repo" — you already know everything below.

---

## What DocOga Is

**DocOga** = Nigerian legal document platform. Free tenant tools + paid Oga Pass (₦2,000/30 days).

- **51 tools** (52 total, 51 unique)
- **4 platforms** (Telegram, Instagram, YouTube, WhatsApp)
- **1 mission** (protect Nigerian tenants' rights)
- **Tagline:** "Your Documents. Our Priority."

---

## Brand Identity (LOCKED — Never Deviate)

### Logo:
- `brand/official-logo-white.png` — The ACTUAL logo. LOCKED IN.
- `brand/official-logo-transparent.png` — Transparent variant
- **The AI image generator NEVER draws the logo.** `tools/add_logo.py` composites the real file.

### Colors (10 LOCKED):
| Name | Hex | Usage |
|------|-----|-------|
| NAVY | `#061A33` | Backgrounds, primary |
| NAVY2 | `#0C2646` | Secondary background |
| PANEL | `#0F3D7C` | Cards, panels |
| BLUE | `#4A8CFF` | Links, interactive |
| SKY | `#0080E0` | Highlights |
| YELLOW | `#FFC93C` | Accent (ONE per design) |
| RED | `#FF5A5F` | Warnings, violations |
| GREEN | `#008751` | Success, FREE badge |
| MUTED | `#8FA8C9` | Body text |
| FAINT | `#6080AA` | Secondary text |

**THESE ARE BLUE, NOT GREEN.** Extracted from logo.

### Typography:
- **Font:** Inter (fallback: DejaVu Sans in sandbox)
- **Grid:** 84px baseline
- **Headlines:** Black weight, 80-120px
- **Body:** Light/Regular, 28-38px
- **Kickbacks:** SemiBold, 20-28px, tracked +7-12

### Voice & Tone:
- **Confident** — we know the law
- **Clear** — plain English, no jargon
- **Caring** — we're on your side
- **Concise** — respect the reader's time
- **NEVER** say "utilize" — say "use"
- **NEVER** say "commence" — say "start"
- **ALWAYS** use ₦ for Nigerian currency
- **ALWAYS** cite the law (section + statute)

### Narrative Semantics:
- **Strike** = external price rejection ONLY (when others overcharge)
- **Own price** = yellow underline sweep (when we show our price)
- **FREE** = "to start. No signup. No card."

---

## Design System (LOCKED)

### Status Post Template (`docs/STATUS_POST_TEMPLATE.md`):
```
Asymmetric layout
├── Top: Filmified hero image + scrim fade into navy
├── Middle: "01" watermark (giant, semi-transparent, right-aligned)
├── "WEEK ONE" kicker (small, tracked, faint)
├── Main headline (Black 82px, white)
├── Yellow accent bar (160px × 12px)
├── Sub-line (Light 32px, muted)
├── Detail bullets (yellow dots + tool name + description)
├── Bottom: CTA + FREE badge (green pill) + tagline
└── Film grain σ=1.8 over everything
```

### Reel Anatomy (`docs/CONTENT_SYSTEM.md`):
```
5 scenes, 14.4s, 1080×1920, 30fps
Scene 1: THE HOOK (0-2.8s) — emotional trigger
Scene 2: THE LAW (2.8-6.0s) — legal authority
Scene 3: THE EVIDENCE (6.0-9.0s) — what they owe
Scene 4: THE ACTION (9.0-11.8s) — what to do
Scene 5: THE CTA (11.8-14.4s) — the close
```

### Thumbnail Rules:
- 60-30-10 color rule
- 2-3 words max (+30% CTR)
- Single focal point
- Curiosity gap (open question, don't answer)
- Safe zone: center 1080×1080
- Mobile test: 168×94px
- Yellow on navy = maximum contrast

### Image Discipline Protocol v2:
- Owner mandates: "I must not detect AI by any means"
- Blend pipeline: filmify + scrim + vignette + editorial type
- Photorealism = film-stock mandatory
- `tools/blend_image.py` handles all blending
- **🔴 NEVER stamp the logo on reels or videos.** Logo goes on static images only (carousels, status posts). NEVER on video. NEVER on the front of a reel. PERMANENT RULE.

---

## Content System (LOCKED — 6 Documents)

### 1. Content Architecture (`docs/CONTENT_SYSTEM.md`):
- **5 Pillars:** EDUCATE (40%), ENTERTAIN (30%), TRUST (20%), PROMOTE (10%), COMMUNITY (bonus)
- **7 Frameworks:** Hook→Payoff→Loop, Before→After→Bridge, PAS, Star→Chain→Hook, Curiosity Gap, 3-Act, Monroe's
- **7 Hook Archetypes:** STAT, QUESTION, CLAIM, STAKES, CURIOSITY, HOWTO, STORY
- **Rule of 3:** Every post answers WHAT? SO WHAT? NOW WHAT?
- **7-Second Rule:** Capture attention in 7 seconds or lose it

### 2. Content Calendar (`docs/CONTENT_CALENDAR.md`):
- October 2026 — 4 weeks, 28 posts planned
- Weekly: 3 Reels + 2 Carousels + 1 Status + 1 Community
- Monthly themes: Week 1 (Launch) → Week 2 (Authority) → Week 3 (Social Proof) → Week 4 (Conversion)

### 3. Content Atomization (`docs/CONTENT_ATOMIZATION.md`):
- 1 deep-dive → 25-40 atoms → 8-12 angles → 20+ assets
- Spaced over 2-4 weeks (never all at once)
- Atom types: hooks, stats, law refs, steps, myths, stories, FAQs, frameworks, quotes, CTAs

### 4. Emotional Architecture (`docs/CONTENT_EMOTION_MAP.md`):
- **8 High-Arousal Emotions:** OUTRAGE, SURPRISE, AWE, CURIOSITY, VALIDATION, HOPE, FEAR, HUMOR
- **Contrasting Pairs:** OUTRAGE+HOPE, FEAR+CONTROL, CURIOSITY+SATISFACTION
- **Formula:** HIGH AROUSAL (first 3s) → CONTRAST (middle) → RESOLUTION (end)

### 5. Content Scoring (`docs/CONTENT_SCORING.md`):
- 10 dimensions, weighted (Hook 15%, Emotion 15%, Clarity 10%, Legal 10%, Brand 10%, CTA 10%, Visual 10%, Mobile 10%, Share 5%, Platform 5%)
- **Minimum 70/100 to ship**
- Post-publish: track saves, shares, watch time, comments, clicks, followers

### 6. Growth Engine (`docs/GROWTH_ENGINE.md`):
- **North Star:** VVSA (Valid Views per Social Action) — target 70-90%
- **Hook Lab:** Track every hook in HOOK_LEDGER.md. After 10 tagged reels: 70% winner-bias.
- **Pre-flight Law:** Before ANY new platform, complete written pre-flight.

---

## Sound Design (LOCKED — v2 Professional Grade)

`tools/make_sfx_v2.py` — 100% synthetic, CC0-safe.

### Architecture:
- **5-layer impacts:** sub boom + body thump + crack transient + debris noise + metallic sweetener
- **Stereo Haas effect** (7-18ms delay per element)
- **Frequency-managed** — each layer EQ'd to its own band (no masking)
- **Strategic silence** — 200-500ms before key impacts
- **Master bus:** plate reverb → compression (3.5:1) → soft saturation → mono sub <120Hz → -1.0 dBTP peak

### SFX Library:
| Sound | Layers | Usage |
|-------|--------|-------|
| Cinematic Impact | 5 (sub+body+crack+debris+sweetener) | Major reveals |
| Sub Hit | 2 (sine+subharmonic) | Subtle moments |
| Cinematic Whoosh | 3 (pink noise sweep+sub thump+resonant filter) | Transitions |
| Law Chime | 5 (chord+7th+shimmer+reverb+saturation) | Legal authority |
| Deny Buzz | 3 (detuned minor 2nd+sub+pink noise texture) | Violations |
| Positive Reveal | 3 (rising tone+parallel 5th+bright transient) | Solutions |
| Click | 3 (phantom transient+sub tick+high) | UI details |
| Riser | 3 (sub sweep+pink noise filter sweep+harshness) | Tension build |
| End Stinger | 4 (descending sweep+sub resolution+shimmer+reverb) | CTA close |

---

## Complete Tool Suite (52 Tools)

All in `tools/`. Key tools:

| Tool | Purpose |
|------|---------|
| `blend_image.py` | Image blending pipeline (filmify, scrim, vignette, grain) |
| `make_fresh_reel.py` | Reel generator (5 scenes, 14.4s, brand style) |
| `make_sfx_v2.py` | Professional sound design (synthetic, CC0) |
| `add_logo.py` | Logo compositor — **static images ONLY.** Never video (locked rule) |
| `weekly_report.py` | Growth report assembler |
| `yt_suggest.py` | YouTube autocomplete research |
| `yt_upload_long.py` | Direct long-form YT upload |
| `qa.py` | Pre-push QA gate (structural checks, incl. the workflow handoff audit) |
| `workflow_handoffs.py` | Audits every workflow for values that cross a step boundary and never arrive ($GITHUB_ENV same-step reads, jq `$ENV` needles with no export, dangling `steps.*.outputs.*`); called by `qa.py` |
| `rebuild_ep1.py` | Unattended Episode-1 rebuild |
| `gemini_tts.py` | Gemini TTS (voiceover) |
| `motionstudio.py` | MotionStudio v4 |
| `dd2_shorts.py` | DD2 Shorts A/B/C |
| `shorts_reel.py` | Shorts/Reels bridge (14 Oct 2026): rotation words → MotionStudio spec → `motionstudio.build` — the only renderer the YouTube/Facebook/Telegram video lanes may use (qa.py §15) |
| `generate_short_video.py` | WORDS only (`VIDEO_SCRIPTS`, `script_for_date`); its static-card renderer is retired from every lane |
| `lead_magnets.py` | Lead magnets |
| `auto_caption.py` | Auto-caption |
| `reframe.py` | 9:16 → 1:1 reframe |
| `batch_render.py` | Batch render |

**52 tools total. All committed to main.**

---

## Documentation Suite (16 Documents)

All in `docs/`. Historical documents are on `main`; new session research and
click guides are on the Arena branch until explicitly released.

| # | Document | Purpose |
|---|----------|---------|
| 1 | `SESSION_CONTEXT.md` | **THIS FILE — single source of truth** |
| 2 | `CONTENT_SYSTEM.md` | Master content architecture |
| 3 | `CONTENT_CALENDAR.md` | October 2026 calendar |
| 4 | `CONTENT_ATOMIZATION.md` | 1→20+ repurposing system |
| 5 | `CONTENT_EMOTION_MAP.md` | Emotional architecture |
| 6 | `CONTENT_SCORING.md` | Pre-publish quality gate |
| 7 | `BRAND_STYLE.md` | Brand style guide |
| 8 | `STATUS_POST_TEMPLATE.md` | Status post design |
| 9 | `DESIGN_SYSTEM.md` | Design system |
| 10 | `GROWTH_ENGINE.md` | Growth engine charter |
| 11 | `GROWTH_JOURNAL.md` | Living growth journal (Ch 0-5) |
| 12 | `HOOK_LEDGER.md` | Hook performance data |
| 13 | `BUSINESS_PLAN.md` | Business plan (original) |
| 14 | `BUSINESS_DOMINANCE.md` | **Global dominance blueprint (5 phases, $1B vision)** |
| 14 | `QA_PROTOCOL.md` | QA rules |
| 15 | `TOOLS_MANIFEST.md` | Tool documentation |
| 16 | `EPISODE_BLUEPRINT.md` | Episode template |
| 17 | `B2B_DISCOVERY.md` | Discovery research; pricing/claims require buyer and primary-source validation |
| 18 | `OWNER_CLICK_GUIDE.md` | Official-source click paths, safety checkpoints and account gates |

---

## GitHub Actions (Automation)

| Workflow | Trigger | Purpose |
|---|---|---|
| `verify.yml` | push, PR, manual | **Gate.** Runs `pre_push_verify.sh` + `qa.py` in CI |
| `telegram_autopost.yml` | 9 AM + 6 PM WAT, manual | Photo post + video short |
| `youtube_queue.yml` | manual (one click) | Uploads next item from `youtube_queue.json`, then commits the popped queue |
| `youtube_scheduled.yml` | Tue + Fri 6 PM WAT | Same queue, on a schedule |
| `youtube_autopost.yml` | manual | Single upload via `tools/yt_publish.py` |
| `facebook_autopost.yml` | 08:30 UTC daily, manual | `tools/fb_publish.py` |
| `threads_autopost.yml` | 08:45 UTC daily, manual | `tools/threads_publish.py` (needs 2 secrets — see `INSTAGRAM_THREADS_AUTOMATION.md`) |
| `instagram_autopost.yml` | 09:00 UTC daily, manual | `tools/ig_publish.py` + `tools/social_card.py`; media bridge is `site/social/` |

- Credentials live in GitHub Actions secrets (not locally accessible)
- The three workflows that commit back to the repo declare `permissions: contents: write`
- **Do not force-push `main`.** See the incident note at the top of this file.

---

## Locked-In Decisions (Owner Confirmed)

| Decision | Status | Date |
|----------|--------|------|
| Brand colors are BLUE, not green | LOCKED | Sep 2026 |
| Logo = `brand/official-logo-white.png` | LOCKED | Sep 2026 |
| AI never draws the logo | LOCKED | Sep 2026 |
| Design system uses editorial art direction | LOCKED | Sep 2026 |
| Status post template (asymmetric, "01" watermark) | LOCKED | Oct 3 2026 |
| Reel anatomy (5 scenes, 14.4s) | LOCKED | Oct 3 2026 |
| Sound design v2 (5-layer impacts, stereo) | LOCKED | Oct 4 2026 |
| Content system (5 pillars, 7 frameworks, 7 hooks) | LOCKED | Oct 4 2026 |
| Emotional architecture (8 triggers, contrasting pairs) | LOCKED | Oct 4 2026 |
| Content scoring (10 dimensions, 70/100 minimum) | LOCKED | Oct 4 2026 |
| QA Protocol: NO PUSH unless qa.py exits green | LOCKED | Sep 2026 |
| All SFX must be CC0 (public domain) | LOCKED | Sep 2026 |
| Status posts must be "beyond After Effects level" | LOCKED | Oct 3 2026 |

---

## Growth Journal (Chapters 0-5)

Documented in `docs/GROWTH_JOURNAL.md`. Key milestones:

- **Ch 0:** The Idea — Nigerian tenants need legal protection
- **Ch 1:** The Build — 52 tools created in one session
- **Ch 2:** The Design — Brand style locked in
- **Ch 3:** The Content — Reels, carousels, status posts
- **Ch 4:** The Sound — Professional-grade SFX
- **Ch 5:** The System — Content architecture complete

**Always document the growth journey.** The owner wants a living record.

---

## What's Been Built (Assets)

### Deployment safeguards (10 Oct 2026, session branch only):
- Marker Worker workflow: isolated manual dry-run, deploy failure propagation,
  sanitized output/exit cleanup, no-code read-only activation probe; site exit
  cleanup hardened too. Tested locally; not deployed.

### Social Content:
- `social/status-oct3.jpg` — Premium editorial status post (Week One)
- `social/reel-stakes-caution.mp4` — STAKES hook reel (14.4s, 5 scenes)
- `social/reel-stakes-cover.jpg` — Reel cover frame
- `social/reel-stakes-sfx-v2.mp3` — Professional SFX (stereo, synthetic)
- `social/reel-stakes-final.mp4` — Reel + audio combined
- `social/reel-stakes-thumb.jpg` — Thumbnail (1080×1920)
- `social/reel-stakes-thumb-grid.jpg` — Grid preview (1080×1080)
- `social/reel-stakes-thumb-mobile.jpg` — Mobile test (168×94)

### Analytics:
- **Last verified production baseline:** deployment run `38044933960` at commit `1335863c` used legacy tag `G-GO8VZB3R28`; `success.html` was untagged. No later deployment was made in this work.
- **Current session-branch source:** unconditional legacy loader removed; `site/analytics-consent.js` holds the dedicated ID `G-BQ1YTR0ZZJ` behind `ANALYTICS_RELEASE_ENABLED = false`. A first-party Privacy choices status control reports that Analytics is off. If the release gate is eventually cleared, a valid affirmative consent is still required before loading Google code. The manager covers the main app and every marketing HTML page except `success.html`; privacy/terms pages can manage choices but are not page-view tracked.
- **Privacy/event controls prepared:** 13 SPA routes allowlisted; manual safe page views; unsafe query keys and raw fragments are excluded, only fixed source/medium campaign enums can remain, and external referrers are reduced to origin. GA4 may still generate built-in session/engagement events; optional Enhanced Measurement remains off by release checklist. The app's WhatsApp `shareDoc` uses fixed promotional copy plus the homepage URL only (no generated form/document fields), with `noopener,noreferrer`; tests cover all 10 tools. Google Signals/ad-personalisation signals are denied; consent expires after 180 days; intended GA cookie lifetime is 90 days. Property-side settings, transfer basis, Google terms/data sharing, retention and redaction remain unverified, so the code release gate stays closed.
- **Dedicated DocOga GA4 property:** ID `558370565`, stream `G-BQ1YTR0ZZJ`, timezone `Africa/Lagos` (GMT+01:00), currency `NGN`. Its empty aggregate report is not evidence of zero site traffic.
- **Read-only reporter:** `.github/workflows/analytics-snapshot.yml` + `tools/analytics_snapshot.py` use GitHub OIDC/WIF and a property-Viewer service account; the provider is restricted to this repo, the Analytics workflow and the session branch. Google-side WIF/API setup is screenshot-verified. The 18:20 WAT Variables-page screenshot shows all three expected repository-variable rows; the long name/value previews are truncated, so only visible prefixes are screenshot-readable.
- **Snapshot mechanism:** placeholder commit-back was verified first; run `38071879234` then passed WIF but failed on omitted `rowCount`. The conservative parser fix accepts missing count only for recognized empty RunReports; targeted tests 8/8 and full suite 71/71 pass, QA is green with two environment-only warnings, and pre-push checks passed. Owner approved exactly one retry after the fix. Run `38073371592` passed WIF, `runReport`, and commit-back; bot commit `bbde8dd` wrote `mode: live` reports for 2–8 Oct 2026 with zero rows and `row_count_source: implicit_empty_response`. This proves keyless read-only report access, not site traffic or purchases. The dedicated site tag is not deployed. The owner later authorized local consent-first code preparation only; no further live request, site deployment, `main` merge, schedule, or broader trust is authorized.
- **Microsoft Clarity:** `ym9fd3sxq5` (heatmaps, session recordings, rage clicks).

### Facebook Page:
- **Page ID:** `102466208923830`
- **Page Name:** `DocOga`
- **App ID:** `931364932955308` ("DocOga Publisher", Business app; the old Consumer app `4401202890209558` is abandoned — it could not hold `pages_*` permissions)
- **Status:** ✅ Lane live since 15 Oct 2026 (daily 09:30 WAT, `.github/workflows/facebook_autopost.yml`); Page token verified "Expires: Never"
- **Post art:** the brand card from `tools/social_card.py` — never files from `brand/` (owner, 15 Oct 2026: "not my brand style")
- **Instagram:** Not linked (owner declined to link)

### YouTube:
- **Channel ID:** `UCeOzX7F7sYX-WchNJyBM2qA`
- **Client ID:** `635194176409-gupiodjn1o57r6rcp1h6ivv0h2jhusmm.apps.googleusercontent.com`
- **Status:** ✅ Connected via OAuth
- **GitHub Secrets:** `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_CHANNEL_ID`, `YT_REFRESH_TOKEN`

---

## FREE FOREVER LOCKED — Platform Limits

### YouTube Data API v3 (FREE):
- **Daily quota:** 10,000 units/day
- **Upload cost:** ~1,600 units per video
- **Max uploads:** ~6 videos/day
- **Refresh token:** Never expires (unless revoked)
- **Storage:** Unlimited (YouTube hosts it)

### GitHub Actions (FREE):
- **Public repos:** Unlimited minutes
- **Private repos:** 2,000 minutes/month
- **DocOga repo:** Public → UNLIMITED ✅

### Facebook Page (FREE):
- **Posts:** Unlimited text/photo/video
- **Token:** Short-lived (~60 min), needs refresh
- **Long-lived:** 60 days (need to fix exchange)

### Telegram (FREE):
- **Bot API:** Completely free, no limits
- **File size:** Up to 50MB per file

### ⚠️ FREE TIER RULES (NEVER BREAK):
1. **YouTube:** Max 6 uploads/day (10,000 ÷ 1,600 = 6.25)
2. **GitHub Actions:** Public repo = unlimited, use it
3. **No paid APIs** — ever
4. **No paid storage** — use GitHub + YouTube hosting
5. **No paid CDNs** — use GitHub Pages
6. **Refresh tokens before expiry** — automate it
7. **Monitor quota usage** — stay under 80% daily

### 🔴 COST RULE — ABSOLUTE:
- **₦0 FOREVER.** Zero. Nothing. Free.
- No premium plans. No paid tiers. No upgrades.
- If it costs money, find a free alternative or don't do it.
- This is NON-NEGOTIABLE. Owner has been crystal clear.

### Deep-Dives:
- **Lane (14 Oct 2026):** `tools/deepdive.py` + `.github/workflows/deepdive.yml` — Gemini TTS voice,
  Vosk sync, nine-scene parallel render, banked on release `deepdive-<id>`, publishes unlisted.
  `GEMINI_API_KEY` added by the owner 14 Oct. Nightly tick 03:00 WAT works `episodes/queue.json`;
  quota = green pause; music + SFX synthesized by `tools/soundkit.py`. Runbook `docs/LONGFORM_AUTOMATION.md`.
  **DD2 published 14 Oct 2026** → re-mastered copy https://www.youtube.com/watch?v=pl5Z8ueg1ZI (public; owner:
  "everything is perfect"; old n45ufAFv5OM to be deleted by the owner). Bed 15 dB(A) under the voice is the reference.
  **DD3 queued 14 Oct 2026** — `episodes/dd3/` *The Rent Receipt* (45 beats, 1,368 words ≈ 9:18; Lagos Tenancy
  Law 2011 s.5 cited for Lagos only). `episodes/queue.json` = `["dd2","dd3"]`, so the 03:00 WAT tick produces and
  publishes it unlisted; the owner's only job is to watch and tap Public. New plates: `calendar`, `phone`.
  **Shorts ↔ Deep-Dives (14 Oct 2026, from the first stats snapshot):** every rotation topic in
  `scripts/generate_short_video.py` carries `parent` (`dd3`, `dd2` or `yt:<legacy id>`); `tools/deepdive_links.py`
  resolves it through `logs/youtube_longform.json` and the Short's description leads with the watch link
  (pinned-comment text is printed in the run summary — the uploader token lacks `youtube.force-ssl`). Hooks are
  STAKES two-beat lines ("Pay without a receipt. Pay twice.") — 108 views vs 2–16 for question hooks; pinned by
  `tools/tests/test_shorts_parent_links.py`.
  **YouTube numbers:** `tools/yt_stats.py` weekly (Mon 06:00 WAT) → `docs/YOUTUBE_PERFORMANCE.md` — read it before
  choosing hooks/episodes. Analytics-API depth needs `yt-analytics.readonly` on the token (optional owner step).
  🔒 **VOICE LOCKED (owner, 14 Oct 2026):** Gemini Orus + "Narrate this in a natural Nigerian English accent,
  like a confident Lagos radio presenter:" — defined once in `tools/deepdive.py`, fingerprint `697e3233c630…`,
  pinned by tests + qa.py. Never change it; revert whatever breaks the check.
- `episodes/dd2/` — Caution Fee: The Refund War (51 beats, 1,462 words ≈ 10 min) — first episode on the lane
- `episodes/dd3/` — The Rent Receipt (45 beats, 1,368 words ≈ 9:18) — queued; the Tenancy Agreement long-form
  already exists on the channel (08wCJ0EmTkU), so it was skipped as the lane's DD3
- `docs/dd1/` — 66 Years of Tenancy Law (48 slides)
- `docs/dd2/` — Caution Fee (47 beats, legacy)
- `docs/dd3/` — Tenancy Agreement (49 beats)
- `docs/dd4/` — Rent Receipt (43 beats)

---

## User Constraints (Standing Instructions)

- Always check repo state and remember where we stopped across chats
- System must work autonomously without user intervention after setup
- Everything must be free (₦0)
- Lock in context so new chats don't feel like starting over
- **THIS FILE IS THE CONTEXT. READ IT FIRST.**
- Pre-flight law: before ANY new platform integration, complete written pre-flight
- Always document the growth journey
- Status posts must be "beyond After Effects level"
- 70% winner-bias after 10 tagged reels
- VVSA target: 70-90%

---

## How We Work (LOCKED BY OWNER, 10 Oct 2026)

**Owner directive — applies to every future session, no exceptions:**

1. **Screenshot-driven workflow.** This is how we solved the Brevo domain/sender
   problem, and it is the permanent method for all feature/account problems: the
   owner sends a screenshot of the current screen → the agent reads it and
   replies with the exact next taps/fields → owner sends the next screenshot.
   One screen at a time, short concrete instructions, no long checklists dumped
   at once.
2. **Never claim screenshots can't be read.** A future session must never tell
   the owner it "can no longer read or see" screenshots sent in the
   conversation. Screenshots are the owner's evidence channel and the way
   account/DNS/dashboard work gets done (the agent cannot click dashboards).
   If an image is genuinely unclear, ask for a retake or a zoomed shot — never
   claim blindness as a limitation.
3. **Do not treat new sections as amnesia.** When the owner moves to another
   app/section (Brevo → Cloudflare → GitHub → Flutterwave…), all previously
   observed values, decisions and progress from earlier screenshots remain in
   force. Cross-check against the session log and docs below instead of
   starting over or re-asking for completed steps.
4. **Screenshot evidence ≠ agent verification.** Record what screenshots show
   accurately, but keep labelling it owner-performed/owner evidence when it
   hasn't been independently verified by the agent.

## Last Session (LIVING — Update This Every Time)

**Date:** 11 Oct 2026
**Branch:** `arena/af592af6-docoga` (branched from `main` at `7ee8d79`)

### Current continuation — consent-first Analytics preparation (10 Oct 2026)

Branch checked at start: `arena/47d148f1-docoga`, synchronized to remote
`454cb576e79f414cbe2b4af36d2314c6cf96a3f3`; worktree was clean before edits.
Prepared a shared consent manager on all 59 HTML pages other than `success.html`;
57 main-app/marketing pages are tracking-eligible if later enabled, while
privacy/terms pages only manage choices. Coverage includes both SEO generators
and the manually maintained POA page.
The legacy unconditional tag is removed from source; the dedicated stream is
behind `ANALYTICS_RELEASE_ENABLED = false`. While disabled, the first-party
Privacy choices control reports the off state without asking for a choice; the
manager clears any stale choice and accessible production `_ga` cookies, creates
no dataLayer, and loads no Google library. In a future release,
affirmative opt-in, revocation/change UI, safe manual SPA page views, query/hash
scrubbing (including after a reject-then-accept change), referrer reduction, and
success-page exclusion are covered by the manager. GA4 built-in session/engagement
signals are acknowledged for the future privacy review. `success.html` remains
untagged; policy/terms pages allow choice
management but are not measured. Inspected `shareDoc` and verified across all 10
tools that its WhatsApp URL contains only fixed promotional text and the
homepage URL, never generated form/document content; it opens with
`noopener,noreferrer`. The consent suite now guards this outbound-data boundary.

Updated privacy/deployment/runbook guidance and the `tools/gen_*_pages.py`
templates. During regeneration, caught and fixed a pre-existing guide-generator
regression that would otherwise have removed the national guides' sticky Oga
Pass CTA and the POA cross-link; regenerated output keeps both and reports all
10 tools. `tools/qa.py` passed with 0 errors and one warning (`.worker-secrets.env`
absent, so secret comparison was skipped); worker, consent, and full-app DOM
suites passed, with DOM at 97/97 using a temporary jsdom install outside the
repository. Python unit tests passed (71 tests). The VM consent
suite uses a stubbed script sink and made no Analytics request. Commit
`6128fe2` was pushed to this session branch. Local pre-push verification and
GitHub QA/repo-integrity plus Wrangler dry-run build passed; both deploy workflows
were skipped. The separate Cloudflare `Workers Builds: docoga-git` check failed;
its dashboard-only failure details are not reachable here, so the precise cause
is unconfirmed. No successful production deployment, Analytics API request,
schedule change, or main merge occurred. The Worker-secret cleanup/confirmation
gate remains uncleared; keep it and `ANALYTICS_RELEASE_ENABLED = false` in force.

### Current session — 10 Oct 2026 (Brevo domain AUTHENTICATED ✅)

**Release authorization — 10 Oct 2026:** owner replied **Yes** to the explicit
proposal to deploy the corrected payment Worker first, then the site only after
Worker success, keeping resend disabled. This authorizes those two releases, NOT
resend-flag enablement, a resend, new payment, credential replacement or bridge
activation. First marker release `87d858b` / run `38044377472` failed BEFORE
publish at user-token verification (curl exit22; HTTP/body unavailable). Deploy
and live probe skipped, Worker/site unchanged. Verify/build succeeded; site skipped.
Read-only diagnostic pending: supports account-token endpoint on structured client
rejection, still requires active status and deployment-account read. No credential
changes or auth bypass. Python 63 tests pass; diagnostic marker cannot deploy/probe.
At
`76e00fa`, Verify/build succeeded and both deploy jobs were skipped; clean local
branch and remote head matched. Preserve dashboard Secrets/vars, no /verify probe.


**Milestone (owner-performed, screenshot evidence, not agent-verified):** the owner
completed Brevo domain authentication for `docoga.com.ng` in the new guided Brevo
flow (root domain, optional branded subdomain skipped, **Manual** setup, provider
Cloudflare). Four records were added to the existing Cloudflare zone, one at a
time, each checked against the pre-save form before saving:

1. TXT `@` — `brevo-code:…` (account-generated value), TTL Auto, DNS only
2. CNAME `brevo1._domainkey` → `b1.docoga-com-ng.dkim.brevo.com`, **DNS only**, TTL Auto
3. CNAME `brevo2._domainkey` → `b2.docoga-com-ng.dkim.brevo.com`, **DNS only**, TTL Auto
4. TXT `_dmarc` — `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com`, TTL Auto

The zone's two pre-existing Worker records (`@` → `100::`, `www.docoga.com.ng` →
`100::`, both Proxied) were left untouched; no SPF/MX changes; zone now shows
6 records used of 200. Brevo's own check then returned **"Your domain has been
authenticated."** Brevo notes full provider-side propagation can still take up to
48h. Record values were copied from Brevo's own generated fields; treat screenshots
as owner evidence, not independent DNS/API verification (the sandbox has no DNS or
dashboard access). DMARC count is exactly one (there was no prior DMARC record).

**Sender gate also closed 10 Oct 2026 (owner-performed, screenshot evidence):**
Brevo → Senders previously held only the old Gmail sender (Verified but not
DKIM/DMARC-compliant — the source of the orange compliance banner; left
untouched). Added **From name `DocOga`, From email `noreply@docoga.com.ng`**;
it now shows **Verified** (Shared IP), matching the Worker's default
`MAIL_FROM`. The branded-subdomain upsell was skipped again (not required).

**Log cleanup — 10 Oct 2026:** owner opened run `37890401771` (summary title
"Correct payment handover and Oga Pass email [deploy-pass] #34") and its top-right
ellipsis menu. Screenshot shows only **Create status badge**, no **Delete all
logs**. Record as **attempted, option unavailable**; logs are NOT confirmed deleted.
The best-effort attempt gate is met, but this does not prove deletion or credential
revocation. No job logs were opened/downloaded and no workflow rerun was requested.

**Production configuration snapshot — 10 Oct 2026 (owner screenshots):**
Landscape screenshots show `docoga-pass` → Settings → Production with three
Secret rows: `BREVO_API_KEY`, `FLW_SECRET_KEY`, `FLW_WEBHOOK_HASH`, each displayed
as **Value encrypted**. Three Variable rows: `PAYMENT_URL` (value not copied),
`PROVIDER`, `SITE_URL`; KV binding `KV` → `docoga-kv`. `ISSUE_SECRET`, `MAIL_FROM`
and `RESEND_EMAIL_ENABLED` are not listed in the supplied table. This establishes
presence/type only, not currentness, live-key validity or hash equality. Without
an override the repository defaults to the newly verified sender; resend remains
fail-closed without the exact true flag in repository code (not yet deployed).
`ISSUE_SECRET` is needed for the authenticated `/issue` bridge; do not invent or
replace it without checking whether that bridge is used and coordinating both ends.
**Owner confirmation 10 Oct 2026:** replied **Yes** that these three encrypted
Secrets are the replacement credentials saved after the old log exposure. Record
currentness as owner-confirmed, not independently verified. LIVE webhook-hash
equality was confirmed separately in the subsequent owner reply below.
No secret values requested or recorded.
No setting edits, Deploy, payment or resend performed.

**Flutterwave LIVE screenshot — 10 Oct 2026:** latest owner screenshot selects
Live webhooks and shows **V3 Live webhooks**, a masked Secret hash, and Enable v3
webhooks checked. An earlier cropped image showed V4 Live webhooks; do not infer
that any migration or save occurred. The visible URL targets the payment Worker,
but the field clips the path at `/flw-webh`. The owner subsequently confirmed
the full URL is `https://docoga-pass.johnazani.workers.dev/flw-webhook`. Masking itself does not establish equality with `FLW_WEBHOOK_HASH`.
**Owner subsequently replied Yes** that this LIVE hash is the same one saved as
Cloudflare `FLW_WEBHOOK_HASH` during replacement setup. Hash-match gate is now
owner-confirmed, not independently verified; no secret value was requested or
recorded. LIVE URL and hash now owner-confirmed (not independently verified).
No URL edit, Save, test, version migration or event resend was requested.
Do not reveal the hash,
switch webhook versions, Save, send tests, or resend events.

**Recipient comparison — 10 Oct 2026 (owner screenshots, no API access):**
The checkout/customer email on the existing successful qualifying purchase matches
Recipient (To) on the OLD failed Brevo Oga Pass event. Record **matches** only;
no address, message ID, payment reference, account number or pass code copied.
The old event still shows Sent then Error; it predates sender authentication and
is NOT a new delivery test. Do not delete it or click Brevo/Flutterwave resend.

**App-side work — 10 Oct 2026, not deployed:** repaired `deploy-pass-now.yml`:
nonzero DEXIT now exits the step; manual dry-run has its own credential-free local
build step and skips token checks, publishing, live probes and PR comments. All
Wrangler commands name worker/wrangler.toml explicitly; removed ambiguous-config
probe and verbose account/token-fingerprint diagnostics. Token check now reports
active status only. Production Wrangler output is sanitized and raw logs removed
on exit (including sanitizer failure); same cleanup/pipefail protection added to
the site workflow. Live probe changed from /verify to /activate WITHOUT a code:
400/code required before KV access, no activation, issuance or mail. No changes to
worker runtime or website code this turn; no flag enablement or production call.

**Validation:** Python 57/57 (5 new execution/contract tests), Worker suite green
(including missing ISSUE_SECRET rejection and no-code probe, plus Flutterwave
without bridge secret), DOM 97/97, QA 0 errors/1 warning (local secret file absent).
Executed deploy shell snippets with stubbed npx for success, failure and sanitizer
failure; old workflows correctly fail regression checks. Real credential-free
Wrangler 4.147.0 Worker build --dry-run passed; no publish. At `0f258c8`, GitHub
Verify and Cloudflare build check succeeded; both marker deploy jobs skipped
(measured in preceding turn).

**ISSUE_SECRET finding:** only /issue (Selar/Zapier/Make or manual issuing bridge)
requires it; Flutterwave webhook/verify/resend do not. Missing secret fails closed
with 401 even if a caller supplies a key. Historic docs mention a manual fallback;
**Owner confirmed "Nothing else for now"** when asked about other issuing tools:
Flutterwave only at present. Leave ISSUE_SECRET absent and /issue disabled; no
bridge repair or new secret is needed for this scoped release. If a manual or
third-party bridge is introduced later, configure both ends deliberately then.
This closes the bridge-use question, not deployment authorization.

**Next:** request explicit approval to deploy the corrected Worker first and site
second, preserving production Secrets and keeping resend disabled. No approval yet.
Resend-flag enablement and ONE existing-pass resend will be guided separately
only after successful release; no dashboard resend or additional purchase. No runtime MAIL_FROM
listed, so repository default matches authenticated sender; live code not fetched.
Never request success URLs or identifiers; owner uses the existing saved purchase
page only AFTER release approval. One deliberate resend, inspect NEW event and
actual receipt. No new payment, dashboard resend or deployment authorized yet.

### Session — 9 Oct 2026 (owner click-by-click guide)

**Branch:** `arena/47d148f1-docoga`; recovered the local base pointer to the
measured remote head `fca8025` using `git reset --mixed` (working files retained;
no branch switch or force-push). Older branch remains `5cc840e`.

**Built:** `docs/OWNER_CLICK_GUIDE.md`, researched from official GitHub, Brevo,
Cloudflare, Flutterwave and Google docs. Includes direct links, classic/new Brevo
UI branches, field mapping, expected results, and explicit STOP points. It covers
best-effort log deletion, read-only production Secret-name/type inspection, LIVE
webhook setup confirmation, account-generated Brevo DNS records, DNS-only DKIM,
single preserved DMARC, sender verification, private recipient comparison, then
only a later intentional Worker-first/site-second release and ONE existing-pass
resend. No account/DNS changes were performed or independently verified.

**Corrections from deeper research:** Cloudflare Secret edits use a Deploy button
that applies production changes; do not re-enter rotated credentials needlessly
or treat presence as proof of correctness. Do not change ISSUE_SECRET without
updating its bridge. Flattening returns IP addresses instead of the CNAME, NOT a
TXT record (Cloudflare's authoritative description corrects the Brevo article's
wording). Paid flattening controls may be absent on Free; no upgrade. Preserve
existing DMARC policy and reporting destination, avoid duplicate rua tags/records,
and use account-generated instructions, not a generic example. Delivered means
recipient-server handoff, not guaranteed inbox delivery; Error has multiple causes.

**App-side observations to resolve before release:** the Worker deploy workflow
logs DEXIT but does not exit with it, so a green run can hide deploy failure;
its manual dry_run input does not suppress the deploy step. Do not dispatch or
re-run it; fix/test those contracts locally before gated release. `success.html`
has NO GA tag or verified-purchase event. Pages and screens is NOT the landing
page report; success URL visits are not payment proof. A previously suggested
GA click-to-success conversion funnel cannot currently be measured accurately.
Proper privacy-safe verified-payment analytics is a follow-up, not historical data.
Reopening success.html calls /verify and may issue/mail for an unknown verified
purchase; it is not a harmless pre-gate inspection. KV throttling is not atomic
against simultaneous requests; stop after one intentional resend.

**Checks:** `qa.py` green, 0 errors/1 environment warning (no local secret
file, scan skipped); worker + DOM suites pass through QA. Integrity check passes.
No claim of production secrets or sender/DNS validation.

**Status:** documentation changes only; no deploy, resend, payment, credential
change, DNS change, pass-link/price change, or recipient/pass-code recording.
Account gates remain unconfirmed; report statuses only.

### Previous session — 9 Oct 2026 (research: what next)

**Branch:** `arena/47d148f1-docoga` @ `4257cdc` (pushed). Asked "research what next",
so per Rule Zero the research happened first, in the same turn, before any answer.

**Findings:**

1. **The critical path is unchanged and owner-gated.** Nothing app-side can
   substitute: run `37890401771` log cleanup; Worker secrets + **live** webhook-hash
   confirmation (Flutterwave: Settings → Webhooks — live and test hashes differ);
   Brevo domain authentication (manual route preserves the existing DMARC; 3–4
   records; up to 48 h propagation; DKIM CNAMEs DNS-only with flattening off both
   zone-wide and per-record; then confirm the sender); then the gated release —
   Worker `[deploy-pass]` → site `[deploy-site]` → enable the flag → button → check
   the new Brevo event. No payment anywhere in this path.
2. **The unblocked revenue lane is B2B discovery.** Competitors price per document
   (LawBridge ₦2–3k, LegalDoc from ₦5k, LawDepot ₦8.5k) or 10%-of-rent via
   lawyers (₦90k–₦300k on a ₦1.8M rental); the ₦2,000/30-day pass undercuts both.
   Targets: Lagos-first estate agencies/property managers (LASRERA/ESVARBON-regulated,
   WhatsApp-native, ~95% penetration), landlord bodies (LTR Initiative, TRAs), then
   HR-adjacent SMEs (FormWork ₦30k bundle proves document-bundle WTP). Local SaaS
   anchors: Canva Pro ₦5,500/mo, HRPayHub ₦499/user/mo, LawBridge Pro ₦5,000/mo.
   **No price published; Business stays Custom** — discovery produces the WTP
   evidence first.
3. **Diaspora USD stays gated.** Flutterwave international acceptance is an
   account enablement; international settlement is T+5; USD settles to a corporate
   domiciliary account ($1,000 minimum threshold); naira-card settlements stay in
   naira. `$20` remains illustrative only.

**Written down:** `docs/B2B_DISCOVERY.md` (segments, tiered pricing evidence,
discovery question set, DRAFT WhatsApp outreach — not sent) and `DEPLOY_STATUS.md`
§12 (owner-side checklist, sourced to vendor docs). QA + pre_push green. **No
deploy, no resend, no payment.**

### Previous session — 9 Oct 2026 (continuation)

**Branch:** `arena/47d148f1-docoga` — this Arena session's fixed branch. The sandbox
had reset the local pointer to the base commit `7ee8d79` (see the operational note
above); recovered by **fast-forwarding to `5cc840e`**, which carries the complete
`arena/b9e4e9d2-docoga` work with full history. That remote branch is untouched and
nothing was lost; no branch was switched and nothing was force-pushed. Arena tracks
this session by `arena/47d148f1-docoga`, so all further work lands here.

**What was done — app-side re-verification at `5cc840e`. No deploy, no resend, no payment.**

- **Docs read in order:** Session Log row 26, `DEPLOY_STATUS.md` §§8–11, `REVENUE.md`.
- **`c5283e1` confirmed absent** (`git cat-file -t` — no such object), matching the
  earlier check; the §11 deployment gate is present at the branch head.
- **Resend endpoint contract confirmed in code and tests:** fail-closed unless
  `RESEND_EMAIL_ENABLED` is exactly `true` (503 `resend_disabled`); accepts purchase
  references only (no client-supplied email); sends only to the email stored with the
  pass; follows top-up `succ` chains to the newest active code; never returns the code;
  per-pass throttle of one attempt per 60 seconds and three per UTC day, shared across
  reference aliases. `RESEND_EMAIL_ENABLED` is **not set anywhere in the repo** — it can
  only be enabled as a Worker runtime variable in the dashboard.
- **Success-page button confirmed:** posts only the payment reference ids to
  `POST /resend-email`; handles 429 / `resend_disabled` / failure states.
- **Client rollover fix confirmed** (`805f8a4`): cached pass state is cleared on
  explicit Worker `invalid code` or `expired`.
- **Gates re-run locally, all green:** worker unit suite (incl. the six `/resend-email`
  tests), DOM suite 97/97, Python suite **52/52**, `qa.py` **0 errors** (1 local
  environment warning: no `.worker-secrets.env`, secret scan skipped),
  `pre_push_verify.sh` ✅.
- **CI at `5cc840e` re-checked via API:** Verify ✅, Cloudflare build check ✅, both
  marker-gated deploy jobs ⏭ skipped — as reported.
- **Not done, by design:** no deploy, no resend, no payment, no change to the public
  pass link or price. No recipient address, pass code, or secret value is recorded here.

**Still owner-side (unchanged):** (1) best-effort deletion/cleanup of Actions run
`37890401771` logs; (2) confirm production Worker secrets are present and the webhook
hash matches Flutterwave — the owner-reported rotation is not independently verifiable
from this session; (3) authenticate `docoga.com.ng` in Brevo (or use an already-verified
sender) using only the DNS records Brevo generates — DNS-only in Cloudflare, CNAME
flattening off for the Brevo DKIM CNAMEs, preserve the existing DMARC policy with a
single record, no SPF/MX changes unless Brevo's account-specific setup requires them.
Only then: gated release — Worker first `[deploy-pass]`, then site `[deploy-site]`,
enable `RESEND_EMAIL_ENABLED=true` only in that release, use the button for the existing
pass, and check the new Brevo event. No additional payment.

### Previous session — 9 Oct 2026

**Branch:** `arena/b9e4e9d2-docoga`, originally based on `7ee8d79`.
**Revenue guardrails:** B2B discovery/outreach precedes diaspora USD pricing;
Business stays deliberately unpriced; `$20` is illustrative only; ₦1bn/month at
local net pass value requires 510,204 passes. Do not invent a price or pretend the
local-volume target is a viable plan.

**Deployment/security incident:** deploy run `37890401771` succeeded as Worker
version `2ddb599e-ef40-4b6a-a789-bf5742c97874` but Wrangler exposed remote dashboard
vars for `BREVO_API_KEY`, `FLW_SECRET_KEY`, and `FLW_WEBHOOK_HASH`. The PR #11
comment was replaced with a redacted warning; attempts to delete the run/log
returned 403. The owner reports replacing the exposed values as Worker Secrets;
this has not been independently verified from the Arena session. The current
branch hardens both marker-gated Cloudflare deploy workflows with `--keep-vars`
and raw-Wrangler-log redaction. The exposed `FLW_SECRET_KEY` value had the public
key type, not the required secret-key type.

**Owner-reported live check:** a qualifying Flutterwave payment returned a pass
and the browser success page auto-activated it for 30 days. The Worker root later
showed `lastWebhookMinutesAgo: 6`, supporting a recent signature-validated webhook
but not identifying this transaction by itself. The detailed Brevo event shows one
attempt, 0% delivered, and an `Error` rejecting the default sender
`noreply@docoga.com.ng` as invalid until the sender is validated or the domain
authenticated. This is a sender-identity rejection, not evidence of spam placement
or a recipient-server bounce. The log's recipient has not been explicitly compared
with checkout. No address, code, or transaction identifier is stored here. Do not
make another purchase or blindly resend. Brevo and Cloudflare account actions are
not accessible from this session.

The owner confirms the earlier `11d` chip and purchase were in the same browser.
The top-up path should carry remaining days when the Worker recognizes the previous
code. The site now clears local state when `/activate` explicitly returns
`invalid code` or `expired`. Stale cache remains a plausible, unconfirmed
explanation; it does not restore any days, and this fix needs a future hardened
site deploy.

**Code-side state:** Worker provider HTTP-status checks and safe diagnostics are
pushed but not deployed. The no-charge `/resend-email` flow and explicit button on
`site/success.html` are now implemented locally and tested: it resolves the
purchase's existing code from stored reference aliases, follows top-ups to the
newest active code, sends only to the stored checkout email, never returns the
code, and throttles by pass to one attempt per 60 seconds and three per UTC day.
It is fail-closed unless Worker runtime variable `RESEND_EMAIL_ENABLED` is exactly
`true`; leave it disabled until Brevo authenticates `docoga.com.ng` or a verified
sender is configured. These new Worker/UI changes are branch-only and not
deployed. The agent owns app-side tests; account/DNS changes must be made outside
this workspace. No pass code, recipient address, or transaction
identifier is stored in this handover.

### Previous session — 8 Oct 2026

**Date:** 8 Oct 2026 (second session of the day)
**Branch:** `arena/b51ecc68-docoga` (branched from `main` at `b84ecfb`)
**What was done:**

**Both autopost pipelines are broken. Read this before touching anything
automated.**

The owner asked two things: *continue the project — what next?* and *why are we
having so many arena branches?* Answering the first honestly meant checking
whether the automation was still working. It was not — and it had not been for
days, and nothing in the repo could tell him why.

### Finding 1 — Telegram has been dark since 7 Oct

The channel's last post is `t.me/docogadaily/32` (7 Oct, 11:18). Every scheduled
run since — 7, 8, 9, 10 Oct — failed. The run logs were recovered (method at the
bottom of this section) and they say the same thing every day:

```
❌ Photo API error: Bad Request: can't parse entities: Character '#' is
   reserved and must be escaped with the preceding '\'
⚠️ Caption parse failed, retrying plain...
   ❌ Failed to post educational message
📊 Complete: 0/1 messages sent
```

**Cause: all 39 message templates were invalid MarkdownV2.** The template text
is hand-escaped (`\.`, `\!`), but the hashtag block appended to every message
(`#DocOga #NigerianLandlords …`) was raw — and `#` is reserved in MarkdownV2.
It is deterministic, not intermittent: every post, every day. (The plain-text
retry should have rescued it, but its own error was discarded by the code, so
the fallback failed silently and nobody could see why. That is now impossible.)

### Finding 2 — the Shorts Friday run failed at the OAuth *client*

Issue #12 (auto-opened by the hardened workflow) said "nothing may have been
published". The log says why:

```
❌ Token refresh failed: 401 — {"error": "invalid_client",
   "error_description": "The OAuth client was not found."}
```

`invalid_client` means the OAuth **client** no longer exists in the Google Cloud
project: `YT_CLIENT_ID` / `YT_CLIENT_SECRET` are dead. Re-issuing a refresh
token cannot fix this. **Owner-only work** (Google Cloud console) — see
What's Next item 3.

### What shipped (this branch, tests included)

- **`tools/telegram_mdv2.py`** (new) — `escape()`, `validate()`, `to_plain()`:
  the one definition of the MarkdownV2 rules, shared by generator, poster and
  tests. `validate()` reports exactly why Telegram would reject a message.
- **`scripts/generate_telegram_content.py`** — hashtags escaped at render time;
  the rendered message is validated and any violation is logged. Also fixed two
  genuinely unescaped `!` in the `promo[0]` template.
- **`scripts/post_telegram.py`** — the plain-text retry's own error is now
  logged (the discarded error is what made four days undiagnosable); the
  fallback strips markup properly (it used to leave `_` and `` ` `` behind,
  which is why the channel displays literal `_**🔍**_`); a photo that cannot be
  sent falls back to a text post; over-long text/captions are trimmed instead
  of rejected.
- **`tools/telegram_preflight.py`** (new) — before a run is spent, asks
  Telegram: is the token valid (`getMe`), is the chat reachable (`getChat`),
  **may the bot actually post** (`getChatMember` → `can_post_messages`)? Exits
  3/4/5 naming the cause. This is what converts the remaining unknown — whether
  the bot still has posting rights — into a one-line answer on the next run.
- **`.github/workflows/telegram_autopost.yml`** — preflight step, `tee` of the
  poster output, and a labelled issue on failure carrying Telegram's own words.
  The missing alarm is why a four-day outage looked like a red dot.
- **`.github/workflows/youtube_scheduled.yml`** — the credential preflight now
  *mints a token* before rendering (a dead client costs 20 seconds, not a full
  render), and the failure issue embeds both logs plus a corrected triage list
  that names `invalid_client` first.
- **`tools/yt_publish.py`** — `--check-token`, and refresh failures now say
  which repair is needed (`invalid_client` = recreate the client,
  `invalid_grant` = re-issue the refresh token).
- **24 new tests** — `tools/tests/test_telegram_mdv2.py` and
  `tools/tests/test_post_telegram.py` — including the one that would have caught
  the outage: every template, in every post type, rendered exactly as the
  generator renders it, must be valid MarkdownV2. Full suite **72/72**;
  `qa.py` 🏆 green (2 environment warnings: no `.worker-secrets.env`, no jsdom).

### Branch hygiene — why there are nine `arena/*` branches

Every Arena session gets its own branch (`arena/<session-id>-docoga`), and
merging the PR does not delete it, so merged branches accumulate. Measured at
tree level this session (`git diff main <branch>` — ahead/behind is *misleading*
here, because the 6 Oct force-push recovery re-created commits with new SHAs):

| branch | what it actually holds |
|---|---|
| `01a10172`, `10e42594`, `22719d94`, `350e6ff3`, `86310b2a`, `a0d5b259`, `b51ecc68` | **nothing unique** — zero files exist on them that `main` lacks; `b51ecc68` is byte-identical to `main`. They are older snapshots, safe to delete. |
| `47d148f1` | **live, unmerged work**: `main` + 86 commits and a clean fast-forward (`main` is an ancestor). 20 files exist only here — the analytics/consent path, B2B discovery docs, deploy-log redaction, Cloudflare token verification. |
| `b9e4e9d2` | fully contained in `47d148f1` (its 10 commits are ancestors) — the payment/email-recovery fixes live on that branch. |

**Not merged, deliberately:** `47d148f1`'s own session record is explicit —
"No further Analytics request, site retag/deploy, `main` merge, schedule, or
broader trust is authorized without separate owner approval." So merging it is
an owner decision, not a cleanup.

### Reading a run log (keep this — it works)

`gh run view --log-failed` and `gh api …/jobs/<id>/logs` fail from the sandbox
(the blob host is blocked). Two steps work instead:

1. get the signed URL:
   `curl -s -o /dev/null -D - -H "Authorization: token $(gh auth token)" https://api.github.com/repos/johnAzani/docoga/actions/jobs/<job_id>/logs`
   → `HTTP/2 302` with a `location:` on `productionresultssa*.blob.core.windows.net`
2. `fetch_page` that URL. It is outside the sandbox's network restriction and
   returns the full job log (chunked).

Signed links expire in ~1.5 h; regenerate with step 1. This is how both
findings above were proved rather than guessed.


## How to Continue in a New Session

1. **Read this file** (`docs/SESSION_CONTEXT.md`) — you get everything
2. **Check git log** (`git log --oneline -10`) for recent commits
3. **Read the last 2-3 commits** to see what was just done
4. **Continue naturally** — you have full context
5. **Never say** "let me check what we've done" — you already know
6. **Always say** "Continuing from where we stopped..." and reference the last action
7. **At the end of your session:** UPDATE THIS FILE with what you did, then commit and push

---

## Session Log (Running History)

| # | Date | What Was Done | Commit |
|---|------|---------------|--------|
| 40 | 15 Oct 2026 | **The narrator's bucket is now KNOWN, and the lanes resume at the reset (owner: "automatically know when the voice over resets and automatically continue at that time … I want it to be knowledgeable").** Context: the first Short with the new soundtrack (run #8, `oBsWKR4AUNA`) shipped music + SFX but no voice — the lane only read Gemini's `retryDelay` (seconds) and could not tell a per-minute refusal from an empty day. Built: `tools/gemini_quota.py` — `parse_refusal()` reads the whole 429 (`quotaId` PerMinute/PerDay, `quotaValue`, model); `next_reset()` from `America/Los_Angeles` (08:00 WAT now, 09:00 WAT after 1 Nov — no hour hard-coded); a per-Pacific-day, per-lane ledger (`assets/shorts_voice/quota.json`) that remembers the learnt limit and the resume time, carried with the clip cache under one prefix (`shorts-voice-v2-<run id>`, restore-by-prefix + save-every-run) across Shorts/Reels/Deep-Dive/resumer; `owed()` = a slot that passed with no publish since (hand-runs settle it). `deepdive.gemini_tts()` records every request and turns a daily refusal into an appointment. `shorts_sound`: `SHORTS_VOICE=required` (default) → `VoiceUnavailable` with the resume time, exit **6** = paused (green run, nothing reaches publish, summary row `⏸️ Paused … Resumes 08:00 WAT`); refill within 150 min → the run sleeps and continues; `optional` = music-only on purpose; `warm` CLI caches the day's lines. New `narrator_resume.yml` (cron 07:12 + 08:12 UTC, `just-reset --window 45` picks the one that is 12 min after Pacific midnight): warms today's six lines, then dispatches the owed Short/Reel **for the owed date** (`for_date` input → `RUN_FOR_DATE` / `--date`). Summaries gained `Soundtrack` + `Narrator` rows. Also this day: Stories lane (PR #35) + slot-tag guard (PR #36). Tests 723 (+30), QA +4 checks. | this branch |
| 39 | 12 Oct 2026 | **Mailbox go-live DONE — runbook step 1 complete, walked live with the owner on the phone (CF dashboard); both test mails pass.** Phase A (07:05–07:32): Onboard Domain `docoga.com.ng` → Activate — CF added MX route1/2/3 (21/34/71) + `cf2024-1._domainkey` + apex SPF; apex SPF merged to `v=spf1 include:spf.brevo.com include:_spf.mx.cloudflare.net ~all` (07:24); Gmail destination verified (07:32). Phase B (12:53–13:36): `docoga-support-mail` worker by **dashboard code-paste** (no wrangler machine — now the canonical owner deploy path, recorded in AUTO_REPLY.md "Live status"); code proven live via the editor test panel (`Error: No fetch handler!` = email-only by design; the public URL 1101 is that, not a fault — public workers.dev 1101s are a known CF quirk per Sept–Oct 2026 community reports, so the editor test is the verification); vars `ARCHIVE_TO` + FRESH `BREVO_API_KEY` v3 secret (old docoga-pass key coexists). Phase C (13:54–14:40): routing rule `business@` → worker; **Test 1** "Test 1 - normal mail" → archive copy + threaded auto-reply FROM business@ (CF native `reply()` worked, Primary not spam, verbatim contract copy incl. WhatsApp-valve line); **Test 2** "Mail Delivery Failure" → archive only, no reply (guard live); Activity log = 2 inbound + 1 outbound, zero outbound for Test 2. Live DNS re-verified 14:50 (merged SPF exact; brevo-code + _dmarc untouched). **Sandbox incident (recovered):** the workspace had been re-cloned with the branch pointer re-rooted onto 34f0665 (base) while ALL branch work sat in the tree as modified/untracked — recovered with the proven sequence: proved tree == origin tip (`git diff` empty apart from untracked-index artifacts; untracked ⊆ commit files), `git checkout -f -B arena/d3f5797d-docoga origin/…`, re-gated (worker 109 / email 34 / DOM 147 after `npm ci` — jsdom was missing from the re-clone, the silent-skip trap — / QA 0 errors). Remaining 1-minute owner checks (non-blocking): Catch-all rule action screenshot + CF usage (reply() billing) + Brevo Domains evidence shot. NEXT = **runbook step 2 (pre-deploy)**: (1) `TEAM_AUTH_SECRET` on `docoga-pass` (dashboard, like today); (2) confirm whether the live worker already runs the new `/business` code (GET probes inconclusive — the 404 JSON format is identical old/new; owner runs ONE POST probe in the worker editor test panel: POST `/resend-email` → 503 = new code live, 404 = paste `worker/index.js` (1571 lines — prefer owner machine + `bash tools/deploy.sh` if one exists; the sandbox cannot publish: no CF egress, deploy.sh says so); (3) merge PR #15 to publish the SITE (`docoga-git` is GitHub-triggered — its last deploy message is "Merge pull request #14…"); (4) 400/401 probes + Business-card COMING SOON check. | Step 1 was the pre-deploy's stated blocker (the support page tells buyers to email business@ — the lane had to exist first). The self-built lane was the last third-party vendor dependency on the critical path — it's now proven live on ₦0 infra with zero owner steps at runtime (the owner's only ongoing obligation: read nothing). | this branch |
| 38 | 12 Oct 2026 | **Mailbox step REDESIGNED + BUILT — the support lane is now fully autonomous (owner instruction 12 Oct: "I don't want human interaction or replying to emails"; plus: nobody reaches the owner BEFORE paying ₦103k — same pay-first philosophy as the Oga Pass. Correction in-session: the WhatsApp float is the GENERAL support channel, pre- AND post-purchase (owner clarification 12 Oct — my "post-purchase only / never pre-sale" phrasing in AUTO_REPLY.md was fixed in the same day's follow-up commit); the Business purchase flow itself stays pay-first — nobody needs to contact the owner to buy).** Zoho Free (the previous choice) is BLOCKED for this account: signup returns the queued/spam-filtered "unable to create your account right now" (worldwide-reported, not necessarily region — corrected in-session), and the `support-az@zohocorp.com` address printed on that screen is a DEAD mailbox (bounced on send — my error for handing it over unverified; verified official channels = help.zoho.com Zoho Cares portal "Submit a request" + @ZohoCares on X). Full field research to vendor docs: mail.com free = no custom domain (shared @consultant.com-style); ImprovMX free = forwarding only, 500/day, no auto-reply on free; Workspace/M365 = no free custom-domain tier; Proton/Tuta = domain paid; Neo = 15-day trial clock; self-hosted on free VPS (Oracle Always Free etc.) = free tier can't request PTR/rDNS AND cloud IP ranges refused by receivers → deliverability dead on arrival; NG hosting bundles = hosting paid; Zoho-via-VPN = ToS risk. → Chosen: **self-built on already-owned infra — Cloudflare Email Routing (free, unlimited inbound, domain already on CF) + new `docoga-support-mail` worker** (worker/support-mail/: email() handler ~230 lines + wrangler.toml + 32-check suite tools/tests/emailworkertest.mjs wired into npm test): every inbound to business@ → (1) SILENT archive forward to the owner's Gmail (record only — FLW/provider notices + dispute evidence stop being deleted) + (2) auto-reply **AS business@** (CF native reply() primary — threaded, DMARC-gated, reply forced to the receiving domain by construction, external-only via guards: own-domain skip, bounce/noreply/daemon locals, Auto-Submitted, List-Unsubscribe, bulk/auto-reply precedence, delivery-failure subjects — with **Brevo API v3 fallback on the same key as docoga-pass**, so the reply delivers either way; `USE_CF_REPLY=off` escape hatch if CF ever classifies reply() as paid sending). **Honesty-consequence (mandate: no deceptive copy):** the "real person answers within 1 working day" promise was on the live site in FOUR places (support.html ×3 incl. refunds "owner decides each case personally" + index.html team-support card) plus the auto-reply + FAQ.md invariants — ALL de-humanized in the same commit (auto-reply = "fully self-serve" text with no human promise, contract-tested; mid-year seat adds = "not offered in v1"; refunds = "kept on record, no window promised"; CANNED.md re-scoped as reference-only). Owner decision (same day): NO form — "Any problems can be sent to the WhatsApp support" (the general float is the human valve); the auto-reply gained one optional line pointing at the green button (no wa.me link/number in the email, no response-time promise — the dossier "no WhatsApp in the Business flow" rule holds: the float is optional, never required). Owner's morning (~10 min, in AUTO_REPLY.md): CF Email Routing onboard + verify Gmail destination + wrangler secret/deploy + route business@ → worker + 2 test mails. Runbook step 1 rewritten to this path; Zoho kept as zero-code alternative, OFF the critical path. | Zoho's region/queue block made a third-party mailbox the most fragile link on the critical path; the mandate's own rules (₦0, autonomy, no trials) pointed at the self-built lane — and the "no human replies" instruction made it the SIMPLEST possible design: an auto-reply machine + a record. Nothing to read, nothing to answer, no vendor to wait on. |
| 37 | 11 Oct 2026 | **FLW onboarding walked live with the owner (screenshots): DocOga business CREATED (sole proprietorship, trading name DocOga, Al-Barakah MFB settlement, info entered). Wizard blocked at step 2 — sole-prop path REQUIRES a CAC "BN" registration number, and the dashboard's business-type dropdown has NO unregistered option (the Starter category from FLW's official NG docs is not in this flow). Path A = support message drafted for owner (hi@flutterwavego.com / dashboard chat); Path B = CAC BN DIY ≈₦20.7k / 2–5 days as fallback. Meanwhile runbook REORDERED + a new safe pre-deploy: `BIZ_LIVE=false` constant in site/index.html removes the "Configure & pay online" card link at load (it stays in source; Phase 5 flips the constant) — DOM suite now 147/147 (2 new gate checks; old Phase 2 check made source-level). Runbook order now: 0 FLW (in progress) → 1 business@ mailbox → 2 PRE-DEPLOY (waitlist/support/portal live, money path sealed, only TEAM_AUTH_SECRET needed) → 3 FLW creds + webhook → 4 Phase 5 flip (BIZ_LIVE=true + §11) → 5 rehearsal → 6 friendly teams. Dossier: new decision-log status row; worker charge-failure verified honest (502, inner try/catch on VA create). | The "unregistered" path is documented by FLW but absent from the dashboard flow — support is the gate, CAC the concrete fallback. Pre-deploying with the sealed money path gets the WhatsApp card off the live site immediately with zero dead-end risk. |
| 36 | 11 Oct 2026 | **FLW account state = PERSONAL — researched to vendor docs (thinnest detail). Decision: launch on a NEW "DocOga" BUSINESS (Starter/unregistered) sub-account, NOT on the Personal account; CAC deferred (not launch-gating).** Owner reported the live FLW account is Personal (runs the retail Oga Pass via a classic **v3** checkout link — that stays untouched). Deep dive written to **dossier §14** (decision-log row added; source register §12.44). The three findings that change the plan: (1) **the Business money path is built on FLW v4 (OAuth client_credentials)** — `worker/index.js` uses `FLW_CLIENT_ID`/`FLW_CLIENT_SECRET` for both the dynamic VA and the hosted `generic` card charge — and v4 **LIVE** credentials are issued to an **approved business**, so the Personal account very likely cannot produce them (verify in dashboard, §14.7 item a); (2) **bank-transfer buyers see the merchant's registered name** on the VA — Personal = the owner's personal name on a ₦103k B2B transfer, Business = "DocOga" (this is the real B2B trust issue, and where CAC/settlement name matters — it does NOT gate going live or card); (3) **CAC is not required** — FLW's **Starter/unregistered business** category (personal ID + website + meter no. + BVN/NIN + est. monthly sales + profile, no CAC cert, no business bank account; settles to the FLW MFB wallet → pays out to a personal account) fixes both the v4-credential and settlement-name problems. Fees confirmed (NG 2.0% local capped ₦2k / 4.8% intl — matches the price formula); limits (Personal ≈₦1m/txn, ₦5m/day; Business ≈₦2m/txn, ₦10m/day — UNVERIFIED third-party) are **not** launch-gating at our price points (smallest real invoice ₦103,200). **Runbook step 0 rewritten** around creating the Starter business + a 5-point post-approval verification checklist (dossier §14.7); **step 1 + `deploy.sh` secret list corrected** from the classic `FLW_SECRET_KEY` to the v4 `FLW_CLIENT_ID`+`FLW_CLIENT_SECRET` (they come from the new business account — do not deploy before §14.7(a) is confirmed). No worker code change (only which credentials it's pointed at). | this branch |
| 35 | 11 Oct 2026 | **Phase 4 exit gate CLOSED (test gap found on re-review) + retail GA funnel completed + Phase 5 prep.** The Phase 4 test block had NOT proven two of the dossier's exit items — fixed: **C8 overage emails** (100% → soft-cap notice, 150% → right-size notice, deduped per month, most-urgent tier only — 4 new worker checks) and **downgrade data-retention proven during the free tier** (brand/seats/invoice index present while `free`, deleted only at retention end, invoices kept). **Retail GA events** (the funnel gap found in Phase 4 was only half-fixed — business events existed, retail was still silent): `pass_checkout_opened` (buyPass), `pass_activated` / `pass_topup` (submitCode distinguishes a new code from a top-up of an existing pass), all through the now-generally-named `trackEvent` (was `bizEvent`). **Phase 5 prep:** runbook gains the waitlist launch email (copy + KV read procedure; secret-gated notify endpoint only if the list outgrows ~20 names, per the dossier's read-only-list decision). PR #15 retitled to reflect Phases 0–4. Suites: worker **109/109** (105 + 4 new), DOM **145/145** (GA check widened to both funnels), qa.py **0 errors**, gzip ≤ 48KB. State: all build phases 0–4 complete and pushed; the critical path is entirely owner-side (runbook steps 0–5) — nothing more is buildable unblocked; Phase 5's card-flip must NOT ship before the rehearsal (a live card promising an un-proven money path is exactly what Phase 0 fixed) | this branch |
| 34 | 11 Oct 2026 | **Phase 4 (Autonomy) BUILT — renewals are self-serve and the lifecycle runs on cron (owner said "start now" while the deploy/rehearsal waits on his side; FLW + CAC status = "not sure", so the runbook must carry the pre-rehearsal payment-readiness checks).** C9: `POST /business/team/renew` (owner; window = active-within-90-days / grace / free; **price at purchase** — `renewal_base/vat/total` stored on the team record at (re)activation, published formula as fallback; same VA/card machinery as first purchase incl. the "link expired → re-issue" rule; 5/day guard). Renewal webhook: **early renewal stacks on the FUTURE expiry — no days lost**; first activation starts from now; renewal flags reset; renewal-worded email. `teamSignInOk` now admits grace + free (owner renews from the dashboard; members fall to the free banner via status — nothing else changes for them). Daily `scheduled()` sweep (07:00, after the retail reminders): **T-90/30/7 reminder emails** (deduped rem90/30/7 on the team record; the most-urgent milestone CONSUMES the coarser ones — a team first seen at T-26 gets the T-30 notice, never a stale "window open" afterwards), **expiry → grace** (14 days, branding off, email), **grace-end → free** (90-day retention via `retire_at`, email), **retention-end → delete** (team/brand/seats/seatidx/auth; **invoices KEPT** — tax records; final owner email). C8 (§6.4 SOFT — no hard cut-off of in-progress documents in v1, stated honestly): `POST /business/team/usage` = best-effort monthly KV counter (`team:{id}:usage:{yyyy-mm}`, capped at 2× band, 45d TTL); site beacon in `printCurrent` is fire-and-forget keepalive throttled to 10 min; portal shows an honest "Documents this month: X / band" line (≥100% adds the overage note: soft, nothing stops, right-size via business@); cron emails at 100% + 150%, deduped per month. **Revenue funnel events (gap found this phase: the site fired ZERO GA events anywhere):** `business_team_created` / `business_charge_started` / `business_team_activated` / `business_renewal_started` via guarded `bizEvent`. Site: portal licence card gains renewal states (active-near-expiry: "Renews {date} — same price you paid {₦}" + renew buttons; grace: "14-day grace, branding paused"; free: "free tier, data kept 90 days"), grace/free chip variants, `bizRenew()` mirroring the checkout VA panel, `teamRefresh` persists renewal+usage. Docs synced: support.html renewals row → self-serve (grace/retention spelled out; the no-refund-promise DOM guard refined to refunds-only — "14-day grace" is lifecycle, not refunds), FAQ.md invariants (renewals self-serve since Phase 4; lifecycle fixed; mid-year seat adds + refunds stay human), CANNED #4 → dashboard-first, privacy §5 + "aggregate monthly usage count", BUSINESS_TEAM_SETUP.md §5 (lifecycle diagram + cron field table + owner-intervention note). **Deferred to v2 (decision logged):** FLW payment-plan auto-charge (the dossier's "auto-renewal enrolment" option) — native FLW product, cannot be unit-verified without the live KYC'd account (owner "not sure" on FLW status); v1 renewal = dashboard + VA/card, which is the journey's renewal email "or auto-charge notice" minus the mandate. Suites: worker **105/105** (92 + 12 new: meter incr/cap, portal fields, 400 outside window, T-30 renewal at purchase price, renewal-webhook stacking, grace flip, free flip, free-tier renewal, T-30 dedupe+consumption, retention-delete with invoices kept), DOM **145/145** (137 + 8 new), qa.py **0 errors**, gzip **47.9KB** ≤ 48KB. Phase 5 (publish) still gated on: owner deploy (`tools/deploy.sh`), business@ live, Phase 2 rehearsal, 2 friendly teams, §11 decisions | this branch |
| 33 | 11 Oct 2026 | **Phase 3 (self-serve surface) BUILT — teams run themselves: portal + printable invoices + support surface.** Built: **owner portal** (`site/#team`, 15th route): licence card (active/unpaid/suspended with the right next action — the unpaid card carries the same charge buttons as checkout), firm branding editor (owner-only; logo client-validated PNG/JPG/SVG ≤25KB → data-URI → the existing brand PUT; existing logo preserved when no new file is chosen), seats (owner invite/revoke through the one seats endpoint; mid-year seat ADD stays a human business@ step per the dossier), invoices card, support card (FAQ link + business@ mailto). **C10 resolved at build time (decision logged in the dossier): invoice v1 = server-rendered PRINTABLE HTML** — `GET /business/invoice/:id` (session required; another team's id → 404, no enumeration; malformed → 404) returns branded print-CSS with the line items, VAT, status/PAID date, VA details when open, business@ footer — browser Print → Save as PDF; NO PDF library, ₦0; binary .pdf = v2 only if teams demand attachments. `GET /business/team/invoices` (12-month window) reads a new `teaminv:{teamId}` summary index (cap 24, newest-first; written on invoice create, entry status updated paid/wrong_amount by the webhook — the list never re-parses invoice records). **Privacy fix (mandatory, found during the build):** the public site said "No account, no upload", which public team accounts make false → `site/privacy.html` gained §5 "Business teams" spelling out exactly what IS stored (firm name/branding, seat emails, invoice/payment status, hashed sign-in token) and what is NEVER stored (document content); dated 11 Oct 2026. **C11 support surface:** `site/support.html` (noindex, standalone subpage pattern) with the FAQ — what's included, payment, wrong amount, seats, invoice-as-PDF, branding, renewals, refunds, data, response time — and **NO fixed refund window is promised (14-day is still the §11 owner decision; a DOM test now guards against it being published)**; `docs/support/FAQ.md` (source of truth — site page must never disagree), `docs/support/AUTO_REPLY.md` (Brevo business@docoga.com.ng setup, SPF check, verbatim auto-reply text, 2-min daily habit), `docs/support/CANNED.md` (8 copy-paste replies + escalation rule). Unauthenticated portal → magic-link sign-in hint + setup link; active/unpaid chips both gain "Team dashboard →". Suites: worker **92/92** (baseline 85 + 7 new: paid-invoice list, 12-month window, wrong_amount list update, 401 no session, printable HTML content, cross-team 404, malformed 404), DOM **137/137** (122 + 15 new: route registration, unauth portal, authed portal cards, owner editor, seats, invoices+support cards, chip links, unpaid portal, source+file checks incl. the no-refund-promise guard), qa.py **0 errors**, gzip **46.4KB** ≤ 48KB. **Phase 3 exit gate (owner):** 2 friendly real teams (with permission, no cold outreach) complete buy→use with ZERO owner touch; the business@ mailbox must be real before the rehearsal (AUTO_REPLY.md). The Phase 2 live rehearsal (small real payment, both methods, wrong-amount case) still stands as the owner's pre-launch gate; deploy remains the 2 commands in `tools/deploy.sh` | this branch |
| 32 | 11 Oct 2026 | **Phase 2 (money path) BUILT — self-serve buy is complete end-to-end in code; what remains is the owner's live rehearsal (per the phase gate).** Resolved the dossier's pre-build check: NGN dynamic-VA expiry — Flutterwave docs (v3 NGN page + v4 guide, Feb 2026) show the 1h default but v4 allows a custom expiry request and returns `account_expiration_datetime` → design requests 7 days, HONOURS the vendor's returned expiry, shows the real one to the customer, "get a new one" re-issues (§7.4). Built: **C3** configurator (`site/#business-setup`: 4 segment presets, seats, volume bands, live quote from the PUBLISHED formula with VAT 7.5% line — the worker recomputes the price server-side, the client never sends it), **C4-full** `POST /business/teams` (unpaid team + owner seat + magic link; one team per email; 10/IP/day), **C5** `POST /business/team/charge` (owner; transfer = v4 dynamic-VA payment method — PRIMARY per §6.4; card = v4 hosted `generic` charge, P3, honest 502 if the account doesn't support it; reuse-while-open; 5 links/team/day) and the `/flw-webhook` extension (signature required; invoice reference match runs BEFORE the untouched retail pass path; amount accepted in BOTH naira and kobo — v4 reports minor units, never guess on the money path; activation = annual +365d + owner email; wrong amount = no activation + VA voided + fresh VA + auto-email per §7.4; idempotent). Unpaid sign-in semantics: an unpaid team may sign in for 14 days (to reach checkout) but gets NO branding — the DocOga banner stays until paid (honest: branding is what is purchased). **C10 decision (build-time, per dossier):** the invoice is the authoritative KV record + email; the downloadable PDF waits for the Phase 3 portal. No new credentials (existing v4 OAuth). Suites: worker **78/78** (16 new money-path checks), DOM **122/122** (10 new incl. live quote recompute, unpaid-checkout e2e, unpaid docs keep the DocOga banner), qa.py **0 errors**, gzip 43.2KB ≤ 48KB. Transfer is primary, card P3 (per §6.4). **Remaining gate (owner, after the deploy):** small REAL payment proving both methods + the wrong-amount case; the worker surfaces honestly (502 + transfer fallback) if the account hasn't enabled v4 charges/`generic`. One honest scope note: the card path is unit-verified against canned v4 shapes but has NOT seen the live account — that's exactly what the rehearsal proves | this branch |
| 31 | 11 Oct 2026 | **Phase 1 (Brand + team core) BUILT — all exit-gate items verified; ships in the same two deploy commands as Phase 0 (`tools/deploy.sh`).** Worker: **C1** KV records (`team:{id}`, `team:{id}:seats`, `brand:{id}`, `seatidx:{email}`, `auth:{email}` — one-time SHA-256-hashed magic tokens, 10-min TTL), **C2** magic-link auth (`POST /business/login` → one-time 10-min token emailed; `GET /business/login?token=…` → 30-day stateless HMAC session; the session is RE-VALIDATED AGAINST KV ON EVERY CALL — revoked seat / expired team dies immediately, no token revocation; 503 `team_auth_disabled` fail-closed without `TEAM_AUTH_SECRET`; 5/email/day + 10/IP/day rate guards), **C4-partial** (`GET /business/team` seats+brand — owner sees all, member self-only; `PUT /business/team/brand` owner-only, logo server-re-validated PNG/JPG/SVG data-URI ≤25KB; `POST /business/team/seats` invite/revoke owner-only, invite emails the magic link, revoke immediate), **C7** branded rendering: the single `freeBanner()` chokepoint (all 10 renderers) returns firm name + logo in team mode; toolbar badge flips to `TEAM · {firm}`; Business card carries the sign-in box + signed-in chip; `?team_token=` boot pickup. Site/API are different origins → session in localStorage + `Authorization: Bearer` (C2's "signed cookie" can't cross origins); CORS updated to allow PUT + Authorization (forward-compatible). Owner onboarding recipe: `docs/BUSINESS_TEAM_SETUP.md` (KV dashboard keys, one-time `wrangler secret put TEAM_AUTH_SECRET`, troubleshooting table). **Phase 1 exit gate met:** worker **62/62** (15 new checks incl. revoke-immediacy, expired-team login block, tampered-session 401, 25KB logo cap, one-time magic link, member self-view, 403 owner-gates) + DOM **112/112** (13 new incl. END-TO-END: stored session restored → `/business/team` re-validated → ALL 10 tools render the firm banner (name + logo) with NO DocOga banner → sign-out restores free banner + sign-in form) + qa.py **0 errors**. One bug found in the phase: a missing `}` in the DOM TEST STUB itself (the suite caught it — product code was clean). Phase 2 (money path: C3 configurator, C5 invoice + dynamic VA, C6 card checkout, C10 invoice PDF) is the next unblocked phase | this branch |
| 27 | 11 Oct 2026 | **Found and fixed the reason both autopost pipelines have been dead since 7 Oct.** Telegram: all 39 templates were invalid MarkdownV2 (raw `#` in hashtags) — fixed at the source with `tools/telegram_mdv2.py` + escaping at render time, the discarded retry error now logged, photo→text fallback, a preflight that asks Telegram whether the bot may post, and a labelled failure issue. YouTube: the Shorts failure was `401 invalid_client — The OAuth client was not found` (owner must recreate the OAuth client; a new refresh token cannot help) — preflight now mints a token before rendering and the issue carries the real log. 24 new tests, suite 72/72, qa.py green. Also explained the nine `arena/*` branches: seven hold nothing unique, `47d148f1` (main + 86 commits) and `b9e4e9d2` hold the only unmerged work, and merging is owner-gated | this branch |
| 28 | 11 Oct 2026 | **Phase 0 of the Business tier: the live card no longer sells an un-built product.** Owner instruction (11 Oct): Business = custom, annual, per team (estate agents, property managers, landlords, HR teams) and **fully automated — no WhatsApp message from the customer**. Deep research dossier landed: `docs/BUSINESS_TIER_RESEARCH.md` (43-source register; Nigerian competitive pricing live-checked — Dwellrs ₦10k–30k/mo, Rentyx ₦80k–850k/mo; the per-document fee bill — 10% agency + 5–10% legal, ₦150k–300k per agreement at ₦1.5m rent — identified as the real value anchor; Flutterwave virtual accounts + webhooks proven as the no-WhatsApp auto-issuance primitive; proposed tiers ₦96k/240k/480k/custom-formula, explicitly PROPOSED until discovery). The old card promised a logo feature, shared passes, auto-invoicing, "a named human on WhatsApp" and a 1-working-day quote — none existed, and the CTA was a wa.me link. Replaced with an honest **COMING SOON** card (annual, per team, firm branding, team seats, VAT invoice) + a self-serve notify form (email + company + segment) posting to a new `POST /business/waitlist` worker endpoint (dedupe by email, 3/IP/day rate guard, best-effort Brevo confirmation via the existing provider chain). The two DOM tests that asserted the card links to WhatsApp were retired; five new ones assert the coming-soon state, zero wa.me in the card, the form, and the endpoint. 7 new worker unit tests (signup/dedupe/invalid/rate guard/no-keys email). Full suite green. **DEPLOY NOT MARKED — integrity finding:** the worker deployed in production (published 10 Oct, `arena/47d148f1-docoga` lineage) is AHEAD of `main`'s `worker/index.js` — 91 lines `main` lacks, incl. `POST /resend-email` (sender-gated pass-email recovery, live), hardened `sendMail` (HTTP status checks, classified failures, `MAIL_NO_PROVIDER` fail-closed) and 10-tool pass-email copy (`main`'s email still says "all 9 tools"). Deploying from this branch before porting that work would roll the production worker back. Fixed order: port production worker + its `workertest.mjs` into main first → deploy worker (`[deploy-pass]`) → deploy site (`[deploy-site]`) | this branch |
| 29 | 11 Oct 2026 | **Production worker ported into the branch — the deploy blocker from session 28 is cleared.** Adopted `worker/index.js`, `worker/wrangler.toml` (comment-only delta) and `tools/tests/workertest.mjs` verbatim from the deployed lineage (`arena/47d148f1-docoga` @ `49ea7d9`), then re-applied the Phase 0 waitlist on top — verified the ONLY differences vs the production worker are +51 lines (waitlist handler + route + header doc) and +25 lines (its 7 unit tests). Proven that branch tip == deployed worker: no commit touched `worker/` after `2cbda5f` (9 Oct); the 10-10 `[deploy-pass]` commits only triggered publishes of that state. Ported state brings: `POST /resend-email` (sender-gated pass-email recovery, live), hardened `sendMail` (HTTP status checks, classified failures, `MAIL_NO_PROVIDER` fail-closed, never logs recipients), 10-tool pass-email copy, `RESEND_EMAIL_ENABLED`/`MAIL_FROM` env docs. Suites re-baselined on the production worker: worker **47/47** (40 production + 7 waitlist), DOM **99/99**, qa.py **0 errors** (2 warnings → 1: pre-existing secret-scan skip). **Not deploy-marked** — `[deploy-pass]` awaits owner go; it will be a strict forward superset of the deployed worker | this branch |
| 30 | 11 Oct 2026 | **Owner said "Continue" in direct reply to the deploy ask = authorization for the deploy sequence (worker → site, both from branch tip).** Verified the sandbox CANNOT publish: `curl https://api.cloudflare.com` → connection failed (not in egress allowlist), no CF creds in env, no `~/.wrangler`. So the publish executes on the owner's machine; everything else is done here. Shipped `tools/deploy.sh` = the two exact commands (`cd worker && npx wrangler deploy`; root `npx wrangler deploy` per `wrangler.jsonc` → `docoga-git` publishes `./site`), the 10-Oct retry quirk, a non-destructive live-verify block (503 on /resend-email proves new worker; 400 probe on /business/waitlist writes nothing; /activate regression; site grep) and the Phase 1 env note (`TEAM_AUTH_SECRET` — fail-closed 503 without it). Then continued straight into **Phase 1 (Brand + team core: C1 team/brand/seat KV records, C2 magic-link auth, C4 partial team/brand/seats endpoints, C7 branded rendering across all 10 tools)** — Phase 1 teams are owner-created-by-hand in KV per the dossier; exit gate = owner + 1 seat, branded PDFs, revoke works, DOM suite extended. Config decision: session token is localStorage + Bearer (NOT a cookie) because the site (docoga-git) and the API (docoga-pass) are different origins — a workers.dev cookie can't cross to docoga.com.ng; security model = stateless HMAC token whose validity is re-checked against KV (team status, expiry, seat status) on EVERY call, so a revoked seat dies immediately without token revocation | this branch |
| 1 | 3 Oct 2026 | Brand style locked, status post built, reel created, SFX v1 | `1f00e77` |
| 2 | 3 Oct 2026 | Status post premium rebuild (asymmetric, "01" watermark) | `5b0e07e` |
| 3 | 3 Oct 2026 | STATUS_POST_TEMPLATE.md locked in | `8b558c5` |
| 4 | 3 Oct 2026 | STAKES hook reel (14.4s, 5 scenes) | `ce98b87` |
| 5 | 3 Oct 2026 | SFX v1 + final reel (synthetic audio) | `7f4bab3` |
| 6 | 4 Oct 2026 | SFX v2 professional grade (5-layer impacts) | `b6781eb` |
| 7 | 4 Oct 2026 | Thumbnail research-backed (3 versions) | `788348c` |
| 8 | 4 Oct 2026 | CONTENT_SYSTEM.md + CONTENT_CALENDAR.md | `0cd6f19` |
| 9 | 4 Oct 2026 | CONTENT_ATOMIZATION + EMOTION_MAP + SCORING | `b98add1` |
| 10 | 4 Oct 2026 | SESSION_CONTEXT.md — single source of truth | `7cea9fd` |
| 11 | 4 Oct 2026 | Microsoft Clarity added (`ym9fd3sxq5`) | `668ddfb` |
| 12 | 4 Oct 2026 | BUSINESS_DOMINANCE.md — 5-phase global expansion | `badc06e` |
| 13 | 6 Oct 2026 | **Disaster recovery** — force-push orphaned `e7eb57d` (124 commits) + `85097d7`; recovered all 177 files. Fixed `pre_push_verify.sh` false green, added `verify.yml` CI gate, added `permissions: contents: write` to the 3 pushing workflows, removed committed `.pyc` | `8638354` |
| 14 | 7 Oct 2026 | **PR #5 merged** — recovery landed on `main` (`bfa555b`); independently verified depth 138, zero files dropped, QA + integrity green, merge push CI green | `bfa555b` |
| 15 | 7 Oct 2026 | Fixed `youtube_queue.yml`: empty queue now skips with a notice instead of failing red (mirrors the scheduler) | PR #6 |
| 16 | 8 Oct 2026 | **Caught a locked-brand-rule violation before it shipped:** the new unattended Shorts pipeline stamped the official logo on every video frame (banned) and collided with the CTA bar. Removed the logo from video, rebuilt the layout, restored film grain σ≈2.2, added 8 regression tests and proved the detector fails on the regression | `945b28e` |
| 21 | 8 Oct 2026 | **Kano and Anambra published — and Anambra turned out to be an error in our own research.** The Court of Appeal in *Amah v. Ozouli* [2010] NGCA 6 identifies the **Landlord and Tenant Law, Cap. 76, Laws of Anambra State** (ss.172–174: no possession order unless the court is satisfied **suitable alternative accommodation** is available, with a s.174 exception; s.144 channels to the Magistrate Court, limited by **s.272 of the 1999 Constitution**). We had recorded Anambra as "none in force, bill pending" — wrong. The judgment also resolves Enugu: **Cap. 101, Revised Laws of Enugu State, in operation 27 August 1991**. Kano: a second search pass found **no Nigerian authority at all**, so the verified negative stands — no rent-control statute, no standard rent, no identifiable tribunal, no advance-rent cap — with the Northern-Nigeria inheritance (Cap. 113 Vol. 3 vs Cap. 115, unresolved) published as labelled inference. Also fixed a bug where unverified states still asserted specific courts: the Ogun page said "Disputes go to the Magistrates' Courts in Ogun State" above its own tier-E disclaimer. **6 of 12 published states now verified; median similarity 50.6–53.9% (was 94.2%)** | PR #11 |
| 22 | 8 Oct 2026 | **Full handover: owner gave me the whole app to run for revenue** (`docs/MANDATE.md`). Established the business baseline — and the big surprise is that **the app is already monetised and has already settled real money**. The worker at `https://docoga-pass.johnazani.workers.dev` takes payment and issues codes; `logs/2026-09-19-first-real-payment-webhook.json` is a real Flutterwave `charge.completed` — ₦100 charged, ₦2 fee, status `successful`, bank transfer, 19 Sep 2026. `worker/index.js` carries `PRICE_NGN = 2000`, routes `/issue`, `/flw-webhook`, `/verify`, `/activate`, plus Paystack and Selar fallbacks. **So the gap was never technology — it was leakage.** Only 2 of 59 pages could take money; all 48 state/SEO pages (the entire organic-traffic asset) had no buy button, no sticky bar and no link to pricing. Fixed: every generated page now carries a fixed bottom bar and an inline CTA to `#pricing`, print-hidden, footer padding 60→110px. **48/59 pages now carry a pay path.** Corrected two of my own earlier errors: the site is *not* JS-free (index.html has 9 working tools with `renderX()` handlers), and the state pages *do* deep-link into the app (`/#agreement`) — my first two greps measured the wrong strings. Documented the honest arithmetic in `docs/REVENUE.md`: net ₦1,960/pass means ₦1bn/month needs 510,204 passes/month ≈ 17,000 paying customers a day, which is **not reachable at ₦2,000** — it needs a different model, not more pages. Recommended: USD diaspora pricing (~15M abroad, $21.8bn remittances 2025 → ~15× revenue per customer) plus B2B. **Blocking unknown: traffic and conversion rate (GA `G-GO8VZB3R28`) — I cannot read it from the sandbox.** | pushed `43c7542` |
| 23 | 8 Oct 2026 | **Built the document the diaspora actually buys.** Research first: a Power of Attorney is *"by far the most common use among diaspora Nigerians"* (legaldoc.ng), it is what a Nigerian lawyer needs to act for someone abroad (olamideoyetayolegal.com), registration alone runs **₦50,000** (nigisservices.com), and demand is fear-driven — the Guardian reported a UK-based Nigerian who sent money to build in Enugu and found the land did not exist. **DocOga had zero mentions of "power of attorney" anywhere in the site.** Shipped it as the **10th tool** (`9f41acd`): 8 tick-box powers (manage, let, collect rent, sue, register at Lands Registry, pay rates, operate account, sell), donor/donee/property/purpose/duration/governing-state fields, and a full Deed of Power of Attorney. Legal content is sourced, not invented: POA authorises *dealing with* property but does not transfer ownership; ticking "sell" surfaces **s.22 Land Use Act** (Governor's Consent) and warns an "irrevocable" POA is not a substitute for a deed; registration warning cites ***Ojugbele v. Olasoji* (1982) SC 71** (unregistered registrable POA is inadmissible); plus stamp duty, Notary Public attestation, and that Nigeria is **not** on the Hague Apostille Convention so consular legalisation — not apostille — is the route. Registered in all six maps (TITLES, RENDERERS, COLLECTORS, APPLIERS, PAGES, renderAll) plus nav, printCurrent, shareDoc, saveDoc. **Two guards earned their keep:** the DOM suite's "7-tool-map regression guard" caught that printCurrent kept a *duplicated* renderer map — replaced with `RENDERERS[type]()`, removing the duplication the guard exists to catch; and index.html crossed the 135KB size guard, so rather than raise a ceiling I had written deliberately ("Do NOT raise past 135k"), the 37 state `<option>` tags are now built from a JS array → **134,913 bytes**. Added 20 DOM assertions for the POA tool; tool guards 9→10, routes 12→13. **QA green, DOM suite 85 checks / 0 failed.** | pushed `9f41acd` |
| 24 | 8 Oct 2026 | **Closed the last pay-path leaks and published the diaspora page.** Found two things the earlier pass missed. (1) **The seven national pages had no pay path at all** — `tenancy-agreement-nigeria`, `notice-to-quit-nigeria`, `tenant-rights-nigeria`, `caution-fee-nigeria`, `invoice-format-nigeria`, `rent-receipt-format-nigeria`, `shop-tenancy-agreement-nigeria`. These rank for the *head* terms and carry far more search volume than any state page, yet they had neither the sticky bar nor the pricing link the state pages got. Fixed: **coverage now 56/60 pages**, the four remaining being index (which *is* the app), privacy, terms and success — correctly excluded. (2) Those same pages listed "All DocOga tools" as **9** items, so the new POA tool was invisible site-wide. Added. Then published **`site/power-of-attorney-nigeria.html`** — the diaspora landing page. It was needed because the POA tool lives on a hash route (`#poa`) that search engines index poorly, so the highest-value product in the business had no page that could rank. Content is sourced with an explicit Sources-and-confidence box and a "what we could not confirm" list: POA is not a conveyance (needs a deed of assignment + Governor's Consent, **s.22 Land Use Act**); ***Ojugbele v. Olasoji* (1982) SC 71** (unregistered registrable POA inadmissible; Lagos Registrar requirement; irrevocable void unregistered); illiterate/blind grantor attestation; stamp duty before admissibility; **Nigeria is not a party to the Hague Apostille Convention** so consular legalisation (notary → MFA Abuja → embassy) is the only route; indicative costs (~₦50,000 registration) flagged as practitioner figures not statute; and diaspora fraud patterns (fake titles, double sales, land that does not exist, family who "help" until the money goes). FAQPage JSON-LD, canonical, sticky CTA, sitemap (59 URLs). **QA green 0 errors; DOM 85/85; worker suite green.** | pushed `41101d2` |
| 25 | 8 Oct 2026 | **Business tier shipped; two live bugs on the money page fixed.** Asked "what next", I sequenced on one criterion — *least blocked*. SEO pays off in months and I still cannot forecast it without traffic data; the diaspora/USD play is gated on Flutterwave international approval. **B2B is blocked by nothing I don't control**: no new product needed (the 10 tools exist), no traffic needed (50 conversations beat 50,000 visitors), no international payments needed (businesses pay by transfer), and one estate agency is worth ~1,000× a ₦2,000 pass. There was no B2B entry point anywhere — no page, no link, no price. Added as a third pricing card with a WhatsApp quote link. **Deliberately not priced**: Rule Zero, I have no data that justifies a B2B number, so it says "Custom" and opens a conversation — inventing an anchor is worse than not having one. **Also fixed two live bugs on the page that takes money:** the pricing section told customers we had *fewer* tools than we ship — Free said "All four tools", Oga Pass said "All 9 tools", and **Power of Attorney was named on neither tier**. The conversion surface was underselling the product to everyone who reached it. **Page-weight guard now measures the right thing.** The old 60–135KB *raw* window was a proxy that punishes adding tools without tracking load time; its own comment invited this ("Do NOT raise past 135k without new gzip math"). New math: 135,856 raw → **38,217 gzipped (28.1%)** = 37.3KB over the wire, up from 33.3KB at the 9-tool baseline, ~7.5% of the 500KB Nigerian-mobile guidance. Now gates on gzip (48KB ceiling) with raw kept purely as a corruption tripwire; reasoning recorded in the comment. **12 new DOM tests** guard pricing as a revenue surface — 3 tiers, no stale tool-count copy, real RENDERERS count stated, POA named on the paid tier, Business link uses the configured number, buy button wired. Adding tool 11 without updating the copy now fails the suite. **QA green, DOM 97/97.** | pushed `c8b19c8` |
| 26 | 9 Oct 2026 | **The payment worker is deployed and the site is live again. Both had been silently broken.** **docoga-pass:** `WORKER_URL` in `site/index.html` was never wrong — that worker simply did not exist. Getting it deployed took four API tokens. A token fingerprint (sha256[:16], logged from CI) proved which token was actually in the secret: attempt 2 changed it but perms were unchanged, attempt 3 changed nothing at all. `GET /zones` then handed over the token's own permission list, showing **zone/DNS permissions only** — no Workers, no KV — twice in a row. It succeeded on the fourth token with `Account → Workers Scripts → Write` and `Account → Workers KV Storage → Write`. Deployed: `https://docoga-pass.johnazani.workers.dev`, version `f6370c2d-853d`, KV `docoga-kv` bound, cron `0 7 * * *`. `/activate` and `/verify` both answer correctly where they previously 404'd. **Also fixed a latent deploy bug:** `wrangler deploy` run from `worker/` was picking up the *root* `wrangler.jsonc` and deploying to **docoga-git** (the site) instead of docoga-pass — plausibly how the payment worker got clobbered. Now passes `--config wrangler.toml` explicitly. **The site:** Workers Builds has been failing since session 25 with no error text, so the site silently stopped updating — sessions 24–25 were merged but never live. `docoga-git` is a **Worker with static assets**, not Pages, so `wrangler deploy` at the root works and the working token can run it: `deploy-site-now.yml` now does that, gated on `[deploy-site]`, and **Workers Builds is no longer a blocker**. `docoga.com.ng` is attached as a Workers custom domain pointing at docoga-git (no Worker routes; DNS holds only `AAAA -> 100::`, Cloudflare's placeholder for hostnames it answers itself). **The 404 that was really a cache:** after deploying, the POA page served fine on the workers.dev host but still 404'd on docoga.com.ng from the same worker — a 404 cached at the edge before the file existed. `purge_cache` fixed it instantly and is now a permanent deploy step. Verified live: the POA generator and all three pricing tiers including **Business (Custom, annual, per team)**. **Also fixed a CI regression I had introduced:** `QA + repo integrity` was failing. `test_title_carries_the_shorts_suffix_and_topic_does_not` asserted a hardcoded topic from a **date-seeded rotation** — a time bomb that broke on 9 Oct. Worse, its mock patched `generate_video`, but `youtube_short_daily.main()` **discards** that return value and uses `script["title"]`; production is identical because `generate_video` returns `script["title"]`, so the mock was decorative and the assertion only ever held by coincidence. The test now asserts the real contract date-independently and adds the "topic must not contain #Shorts" check its name promised. (The `09-10-2026` stderr line is a deliberate passing test, not a bug.) All 48 tests, pre_push_verify and qa.py green. **Still blocking revenue:** the fresh Worker has **zero secrets** — `FLW_CLIENT_ID`/`FLW_CLIENT_SECRET` (or `FLW_SECRET_KEY`), `ISSUE_SECRET`, and an email key — so `/issue` 401s and codes cannot be delivered. These are live payment credentials: they belong in the Cloudflare dashboard, never in chat or git. The offline batch is unaffected (hardcoded FNV-1a hashes, not ISSUE_SECRET). | pushed `28b9fd9` |
| 27 | 9 Oct 2026 | Corrected deploy handover and revenue sequence; added v3/webhook tests and all-10-tools email copy; `[deploy-pass]` run `37890401771` deployed version `2ddb599e`, but Wrangler exposed remote dashboard vars in its log. PR #11 comment redacted; log deletion 403. Owner must rotate/restore credentials as Worker Secrets before any purchase. | `d1a3cfe` |
| 28 | 9 Oct 2026 | Hardened both Cloudflare deploy workflows to preserve dashboard vars and redact raw Wrangler logs; added regression tests and the redaction helper. No new deploy triggered pending credential rotation/recovery. | `3f72d0a` |
| 29 | 9 Oct 2026 | Owner-reported qualifying purchase returned/activated a pass; root showed a recent valid-signature webhook timestamp. Brevo marked the message `Sent`, but inbox delivery failed. Added safe provider-status checks/logging in Worker code; diagnose recipient/delivery status without another charge. | `44ac1e5` |
| 30 | 9 Oct 2026 | Owner confirmed the earlier 11-day pass chip was in the purchase browser; found `syncPass()` kept an invalid cached code visible. Site now clears cached state on explicit Worker `invalid code` or `expired`; this does not restore days and awaits a safe site deploy. | `805f8a4` |
| 31 | 9 Oct 2026 | Brevo event confirms sender rejection for the default `noreply@docoga.com.ng` identity (0% delivered); added a fail-closed, rate-limited, no-charge resend endpoint/button for the existing active pass plus tests. Sender authentication and security gates remain before enable/deploy. | `2cbda5f` |
| 32 | 9 Oct 2026 | **Continuation on the Arena-fixed branch `arena/47d148f1-docoga`:** recovered the reset local pointer by fast-forward to `5cc840e` (the full `arena/b9e4e9d2-docoga` work; old remote branch untouched; no branch switch, no force-push). Re-verified app-side: `c5283e1` absent (`git cat-file`); §11 deployment gate present at head; resend contract confirmed in code + tests (fail-closed unless `RESEND_EMAIL_ENABLED` is exactly `true`, stored-email-only, follows renewals to the newest active code, never returns the code, 60s + 3-per-UTC-day per-pass throttle shared across aliases); the flag is not set anywhere in the repo; the success-page button posts references only; the cache-clear fix is in place. All gates re-run green locally: worker suite (incl. 6 resend tests), DOM 97/97, Python 52/52, qa.py 0 errors, pre_push_verify ✅; CI at `5cc840e`: Verify + build check ✅, both deploys skipped. **No deploy, no resend, no payment, no change to the pass link or price.** Owner-side gates unchanged: run `37890401771` log cleanup, Worker secrets + webhook-hash confirmation, Brevo sender/domain authentication (DNS-only, CNAME flattening off, preserve the single DMARC record). | pushed `arena/47d148f1-docoga` |
| 33 | 9 Oct 2026 | Historical research summary is in Last Session and `B2B_DISCOVERY.md` at `fca8025`; a prior reply reported this table row but it was absent at the measured remote head. Recorded here without inventing a missing commit. Competitor/vendor claims remain listed prices or hypotheses, not validated DocOga buyer willingness to pay; Business remains Custom. | `fca8025` |
| 34 | 9 Oct 2026 | Official-source click guide with classic/new Brevo UI, private Secret inspection, live webhook confirmation, DNS-only DKIM, single preserved DMARC, sender/recipient checks, best-effort log cleanup and STOP-before-release. Corrected flattening semantics, needless Secret overwrites, unsafe ISSUE_SECRET change, green-run/dry_run deploy assumptions, and unmeasurable GA success funnel. No deploy/resend/payment/account action. | session branch |
| 35 | 10 Oct 2026 | **Brevo domain `docoga.com.ng` authenticated + sender verified** (owner clicks, guided one record at a time): TXT `@` brevo-code + CNAME `brevo1._domainkey` + CNAME `brevo2._domainkey` (both DNS only) + TXT `_dmarc` (`p=none`, Brevo-generated rua) added to the existing Cloudflare zone; both Worker `100::` records untouched; Brevo verify returned "Your domain has been authenticated". Added sender `DocOga <noreply@docoga.com.ng>` → shows **Verified**; old Gmail sender left untouched (compliance banner expected for gmail From). **Owner also locked the working method (see "How We Work" above): screenshot → exact next taps → next screenshot, one screen at a time; future sessions must never claim they cannot read screenshots.** Remaining gates: Actions log cleanup, secrets, webhook hash, recipient comparison, resend flag, workflow-defect fixes; no deploy/resend/payment. | session branch |
| 36 | 10 Oct 2026 | Recipient match observed across owner screenshots (no private data copied); production Secrets and LIVE webhook URL/hash owner-confirmed; log cleanup option unavailable. Repaired Worker deploy exit/dry-run safety, stripped unsafe diagnostics, changed live probe to no-code activation, hardened raw-log cleanup for both marker workflows. Python 57/57, Worker/DOM green, local Worker dry-run passed. ISSUE_SECRET only gates the separate manual/third-party bridge; owner use still to confirm. No release, resend, payment or flag enablement. | session branch |
| 37 | 10 Oct 2026 | Prepared and pushed consent-first GA4 manager, privacy/transfer docs, generator coverage, and WhatsApp `shareDoc` static-copy protections; `ANALYTICS_RELEASE_ENABLED` remains `false`. `npm test` passed (Worker, DOM 97/97, consent); Python 71 tests, QA 0 errors/1 secret-scan warning, pre-push verification passed. GitHub Verify and Wrangler dry-run passed; deploy workflows skipped. External `Workers Builds: docoga-git` failed with dashboard-only detail unavailable; no successful production deploy, Analytics request, main merge, or schedule. | pushed `6128fe2` |
| 20 | 8 Oct 2026 | **Rule Zero enforced on the build: the verified law is now wired into the pages.** `tools/state_law_data.py` (6 jurisdictions, 20 open questions) drives `tools/gen_state_pages.py`. Three live factual errors fixed: (1) the hard-coded notice table printed "Half-yearly — 3 months" on all 48 pages when that is Lagos s.13(1)(d) and essentially nowhere else — the FCT Act, Cross River s.15 and Kwara s.17 have no half-yearly tier; (2) the four Edo pages said "Magistrates' Courts in Edo State" and "recovery-of-premises legislation" when s.4 of the Edict establishes **Rent Tribunals** and s.41(2) repealed the Recovery of Premises Law for residential accommodation; (3) every page now carries a Sources-and-confidence box with its tier and a "What we could not confirm" list. Rivers added at tier B on the strength of Cap. 109 s.7 (quit notice must expire on the **eve of the anniversary**, the opposite of Lagos s.13(4)) and Landlord & Tenant Law Cap. 75 s.75(1) (rent payable **in arrears**) | PR #11 |
| 19 | 8 Oct 2026 | **Research before building: measured the state pages and found they fail Google's doorway-page test — median 94.2% similarity between same-tool state pages, median 3 unique words each (worst pairs 99.6%).** So "expand 12 states to 37" was the wrong next move. Wrote `docs/STATE_TENANCY_RESEARCH.md`: verified statute names, sections and sources for 17 of 37 jurisdictions, tiered A-E, with everything unverified listed and three pending bills flagged as NOT law. Added `tools/audit_state_pages.py` to measure and later enforce (80% / 250 unique words / 500 body words) | PR #12 |
| 18 | 8 Oct 2026 | **Gave the armed Shorts pipeline a memory and an alarm:** publish ledger (`tools/youtube_ledger.py`) + duplicate guard, a secrets preflight that names what is missing, a `YT_PRIVACY` repo-variable switch, a run summary, and a labelled issue opened on any failed run. Verified by simulating all nine scenarios locally (the token cannot dispatch), which caught a real bug: `force=true` exited 3 and failed the run instead of publishing. 48 tests green | PR #11 |
| 17 | 8 Oct 2026 | Merged PR #9 to `main` (`72ec955`) — the pipeline plus the brand fix; PR #8 auto-merged. **This armed the YouTube scheduler: next public upload attempt Friday 9 Oct, 18:00 WAT, and the old empty-queue safety no longer applies** | `72ec955` |

---

## What's Next (Pending)

### 🔴 11 Oct 2026 — the live blockers, in order

**A. Telegram: one run will answer the last open question — and only the owner
can trigger it.** The escaping bug is fixed, but a second failure was hiding
behind it: the logs show the *plain-text retry* being rejected too (its reason
was thrown away by the old code). The new preflight distinguishes the three
possible causes — dead token (`getMe`), unreachable/moved chat (`getChat`), or
**bot silently demoted so it may no longer post** (`getChatMember` →
`can_post_messages`) — and the new failure issue carries Telegram's exact words.
**Next step:** merge this branch, then either wait for the 08:00 UTC run or
click **DocOga Telegram Auto-Post → Run workflow**. If it fails, issue #13+
names the cause in one line. If the bot was demoted, the fix is channel-side:
channel → *Administrators* → re-add the bot with **Post messages** permission.

**B. YouTube: owner-only, Google Cloud.** Recreate the OAuth client (the old one
is gone — `invalid_client`) and replace **all three** secrets together:
`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`. Then click **YouTube
Shorts Auto-Generate and Publish → Run workflow** to confirm before the next
Friday cron. The channel is currently at zero published Shorts from this
pipeline; `logs/youtube_published.json` is still empty.

**C. Two branches hold the only unmerged work — decide, don't drift.**
`arena/47d148f1-docoga` (`main` + 86 commits: analytics live path, B2B discovery
docs, deploy-log redaction, Cloudflare token verification) is a clean
fast-forward, but its own session record gates a `main` merge on explicit owner
approval. `arena/b9e4e9d2-docoga` is contained inside it. **Recommendation:**
review `docs/B2B_DISCOVERY.md`, `docs/OWNER_CLICK_GUIDE.md` and the analytics
setup docs on that branch, then approve one merge — 86 commits of finished,
tested work sitting on a branch is the project's biggest piece of invisible
progress. The seven other `arena/*` branches have nothing unique and can be
deleted whenever convenient.

**D. Then, the real growth work (unchanged):** earn the 48 existing state pages
before adding more (item 11), and the B2B path from `docs/B2B_DISCOVERY.md`.

### Analytics access — live report path confirmed; zero-row result (10 Oct 2026)

1. **Repository variables:** the 18:20 WAT screenshot shows all three expected rows. `GA_PROPERTY_ID` is fully readable; long service-account/provider values are clipped, though their visible prefixes match the instructed values. The agent cannot read variables through the REST API (403); do not retry that path.
2. **First-live attempt 38071879234** (`f3fec02`) passed `Authenticate to Google (Workload Identity Federation)` but failed at `Write snapshot (live, read-only)`. Owner's 18:34 screenshot shows the exact message: `Google Analytics response is missing a valid rowCount.` Commit-back was skipped; latest remains the placeholder from run `38058018325`. No Analytics data was committed.
3. Research of Google's `RunReportResponse` proto (`row_count` is a proto3 `int32`; response `kind` is fixed) indicates the newly created property may return an empty report with the zero-valued count omitted. Hardened `tools/analytics_snapshot.py` to infer zero only when `kind` is `analyticsData#runReport` and rows are empty; other missing/malformed counts still fail closed. Eight targeted tests and the full suite (71/71) pass; `tools/qa.py` is green with two environment-only warnings, and `git diff --check` passes.
4. After the fix/docs pushes (`801a1ea`, `29eff4e`), the owner approved exactly one retry. Trigger commit `4062832` ran `38073371592`; WIF, `runReport`, and commit-back succeeded. Bot commit `bbde8dd` wrote `latest.json` and `2026-10-10.json` with `mode: live`, an empty row list, and a seven-day window of 2–8 Oct 2026. `row_count_source` is `implicit_empty_response`; property timezone/currency are `Africa/Lagos` / `NGN`.
5. The retry approval is exercised; no further GA4 request without fresh explicit approval. The empty report does not prove no site traffic. A consent-first source patch is prepared locally, but is not deployed; the last verified deployed tag was the legacy one. Full durability acceptance still needs fresh-session readback and an owner-side aggregate comparison; with zero rows, the comparison is not yet possible. No production site deploy, `main` merge, schedule, or broader trust is authorized.
6. Keep `ANALYTICS_RELEASE_ENABLED = false` until owner-side evidence documents the NDPA transfer basis/safeguards and applicable Google terms, property sharing/links, retention/redaction, and Enhanced Measurement. The client sends explicit safe page views; GA4 may also generate built-in session/engagement events, which must be included in that review. Before activation, disable Enhanced Measurement history pageviews, outbound clicks, scrolls, and forms unless separately reviewed. Production deployment remains independently blocked by Worker-secret cleanup/confirmation; never add `[deploy-site]` before that gate clears.

### Current revenue priority — 10 Oct 2026

1. **Owner checks completed, without another purchase:** Brevo domain Authenticated
   and default sender Verified; log cleanup attempted (delete option unavailable,
   not confirmed deleted); production three Secrets encrypted/current by owner
   confirmation; LIVE webhook URL/hash matched by owner; checkout/old-event
   recipient matched from screenshots. No values/recipients copied into docs.
2. **Get release approval.** Owner confirms Flutterwave only, no other issuing
   tool currently used. Leave ISSUE_SECRET absent and /issue disabled. Workflow
   bugs repaired/tested; Verify/build succeeded at `0f258c8`, deploy jobs skipped.
   Next ask permission for Worker-first/site-second release with resend still
   disabled. No release markers before explicit approval; no payment needed.
3. **Later gated release and ONE existing-pass resend.** Worker first, site second,
   enable RESEND_EMAIL_ENABLED intentionally, owner uses saved purchase page once.
   No log/dashboard resend or reopening a success URL for pre-gate inspection.
   Acceptance is not inbox proof: inspect NEW Brevo event and actual receipt.
4. **Investigate the 11-day rollover without charging again.** Same browser is
   confirmed. The Worker carries remaining time only if the old code exists and is
   valid in KV; the old local chip could have been stale. The client now clears
   explicit invalid/expired cached codes, pending a safe site deploy. The cache fix
   cannot restore days; do not repurchase.
5. **B2B discovery/outreach.** The Business tier is live and deliberately unpriced.
   Collect requirements and willingness-to-pay evidence; do not invent or publish a
   number. Research kit: `docs/B2B_DISCOVERY.md`; vendor prices are not buyer WTP.
6. **Diaspora USD pricing.** Research Flutterwave international approval, settlement
   and buyer willingness-to-pay before selecting a price. The `$20` in
   `docs/REVENUE.md` remains an illustrative calculation only.
7. **Analytics baseline and release gate.** Last verified deployed code used legacy GA `G-GO8VZB3R28`; local source now removes that unconditional loader and stages the dedicated property `G-BQ1YTR0ZZJ` behind the closed consent/release gate. No site deploy occurred; no success-page tag or verified-purchase event exists. The live aggregate snapshot for 2–8 Oct 2026 (run `38073371592`) is empty; do not infer zero traffic or report a conversion funnel/revenue from it. No further Analytics request without fresh approval.
8. **Owner-side checklist is written down and sourced** — `DEPLOY_STATUS.md` §12:
   Brevo manual authentication (preserves the existing DMARC; 3–4 records; up to
   48 h), Cloudflare DNS-only + flattening off for the DKIM CNAMEs, Flutterwave
   secret hash (Settings → Webhooks; live and test differ), Worker secret names to
   confirm, run `37890401771` log cleanup. Nothing app-side can substitute for these.

9. **Use `OWNER_CLICK_GUIDE.md` for the precise clicks and STOP points.** No
   unnecessary Secret re-entry or Deploy during inspection; fix/test Worker workflow
   exit-code and dry_run contracts locally before release. Account gates remain.

### Historical backlog

1. ~~**Merge PR #5 with "Create a merge commit"**~~ — **✅ DONE 7 Oct 2026**
   (`bfa555b`, merge commit, not squash). `main` is whole again: 138 commits,
   179 files. Do not force-push either direction.

2. **`youtube_queue.json` is deliberately empty (`[]`).** It was emptied
   because merging arms `youtube_scheduled.yml` (cron `0 17 * * 2,5`, UTC),
   which would otherwise have auto-published the first queued item at
   `privacy: public` with nobody watching. All four of its steps are guarded by
   `if: steps.check.outputs.count != '0'`, so an empty queue skips cleanly
   rather than failing. **As of 7 Oct the manual `youtube_queue.yml` skips
   cleanly too** — it previously had no guard and failed red on an empty queue,
   which is what the 6 Oct "YouTube Upload from Queue" failure was.

   The two entries are preserved in **`youtube_queue.pending.json`**. To arm
   an upload, copy an entry back:
   ```bash
   python3 - <<'EOF'
   import json
   q = json.load(open('youtube_queue.json'))
   p = json.load(open('youtube_queue.pending.json'))
   q.append(p.pop(0))
   json.dump(q, open('youtube_queue.json','w'), indent=2)
   json.dump(p, open('youtube_queue.pending.json','w'), indent=2)
   EOF
   ```
   Then either click **YouTube Upload from Queue** (manual, one click) or let
   the Tue/Fri scheduler take it.

3. ~~**Confirm YouTube secrets exist**~~ — **✅ ANSWERED 11 Oct 2026, and the
   answer is not the one we were looking for.** The three secrets *are* present
   (the preflight passed on the 9 Oct run and on the two queue runs). The
   failure is that the OAuth **client itself no longer exists**:

   ```
   ❌ Token refresh failed: 401 — {"error": "invalid_client",
      "error_description": "The OAuth client was not found."}
   ```

   So `YT_CLIENT_ID` / `YT_CLIENT_SECRET` point at a deleted client — nothing
   in the repo can fix that, and re-issuing `YT_REFRESH_TOKEN` alone will not
   help. **Owner action, Google Cloud console:** create a new OAuth client
   (Desktop app), run the one-time consent flow, then replace **all three**
   secrets together in repo → *Settings* → *Secrets and variables* → *Actions*.
   The workflow now mints a token in its preflight, so a bad client fails in
   ~20 seconds instead of after a full render, and the failure issue quotes the
   API verbatim.

4. **Branch protection on `main`** — **still NOT set.** The API returns
   `403 Resource not accessible by integration` for the agent's token despite
   the account holding repo admin, so this cannot be done from a session.
   **Owner action, UI only:** repo → *Settings* → *Branches* →
   *Add branch protection rule* → branch name pattern `main` → tick
   **"Do not allow force pushes"** and **"Do not allow deletions"** (and
   *"Do not allow bypassing the above settings"* so it applies to admins too).
   **Do NOT tick "Require a pull request before merging"** — the automation
   workflows (`youtube_scheduled.yml`, `telegram_autopost.yml`) commit and push
   to `main` with `GITHUB_TOKEN`, and that rule would block every one of them.

5. **The Cloudflare Workers build fails on every non-`main` branch**
   (pre-existing; it succeeds on `main`). PRs therefore get no Workers signal.

   **Diagnosed 8 Oct 2026 — and the obvious theory was wrong.** Workers Builds
   derives a preview URL from the branch name, so the `/` in
   `arena/b51ecc68-docoga` was the prime suspect (a slash cannot appear in a
   hostname). Tested against the check-runs API: `main` ✅ success,
   `arena/b51ecc68-docoga` ❌, **`Zip` ❌ — and `Zip` has no slash.** So the
   branch name is not the cause. What is left is the only remaining difference:
   `main` is a *production* deployment, every other branch a *preview* one. The
   deploy target is byte-identical in all three cases (`wrangler.jsonc`
   publishes `./site`; no bindings, no secrets, no build command), so nothing in
   the repo can make a preview deploy succeed — it is the account's preview
   configuration.

   **Owner fix, dashboard only:** Workers & Pages → `docoga-git` → Settings →
   Builds → production branch `main`, and turn **off** non-production branch
   builds. That is the right setting here anyway: every non-`main` branch is a
   throwaway, there is one deployable target, and no preview URL is ever
   shared. Full write-up in `GITHUB-CLOUDFLARE.md`. The failure is cosmetic —
   `main` deploys fine and the repo's own `Verify` gate is authoritative.

6. **Token limits worth knowing before the next session:** the agent's token
   cannot read or list secrets, cannot set branch protection, and cannot
   dispatch workflows (`workflow_dispatch` → 403). Verification runs must be
   clicked by the owner, or waited for on the cron.

7. ~~**Two PRs are stacked, and merging is a one-decision job.**~~ — **✅ DONE
   8 Oct 2026.** PR #9 was merged to `main` as merge commit **`72ec955`**
   (merge commit, not squash), carrying the Shorts pipeline *and* the
   brand-rule fix. PR #8 was auto-marked merged two seconds later, because its
   head commit `42e4031` is now an ancestor of `main` — nothing was lost and no
   separate merge was needed. Verified on the merged tree: 12/12 automation
   tests, `qa.py` 🏆, `pre_push_verify.sh` ✅, and the CI `Verify` run on the
   merge push (`37738312570`, 06:34 UTC) green.

8. **Three legacy MP4s are still committed with the banned logo on them:**
   `assets/videos/docoga_short_20261003_*.mp4` (3 Oct, ~3.4 MB total). They were
   rendered by the old generator **before** this session's fix, so they carry
   the logo chip and the CTA collision. No workflow references or posts them —
   `.github/workflows/telegram_autopost.yml` is text-only, and
   `post_telegram_video.py` regenerates rather than reusing them — so nothing
   will publish them by accident. They are left in place rather than deleted
   silently, because they are published content and that is the owner's call.
   **Owner decision:** safe to delete, or leave as historical samples. Future
   renders no longer get committed (`assets/videos/` is gitignored).

9. **⚠️ YouTube is ARMED — it will try to publish publicly on Friday
   9 Oct at 18:00 WAT (17:00 UTC).** This is the single most important thing
   to know before then, because the merge **removed the safety that was
   deliberately in place.** `youtube_scheduled.yml` on `main` now:
   - runs cron `0 17 * * 2,5` (Tue + Fri),
   - renders a fresh Short on every run and uploads it with `--privacy public`,
   - and **no longer reads `youtube_queue.json` at all.**

   That last point is the change nobody should miss: the old protection was
   that the queue had been deliberately emptied, so the scheduler had nothing
   to publish. **That protection is gone by design.** This pipeline always
   generates content and always uploads. It does not need arming — it is armed
   the moment it lands on `main`, which it now has. `.gitignore` keeps renders
   out of the repo, so there is no queue to inspect either.

   **Three honest outcomes on the next run:**
   - **If `YT_REFRESH_TOKEN` / `YT_CLIENT_ID` / `YT_CLIENT_SECRET` are missing
     or stale**, the run fails red and **nothing is published**. Harmless, and
     the fastest possible way to finally answer item 3.
   - **If they are valid**, a Short goes live **public, unattended** — which is
     the documented intent ("system must work autonomously without user
     intervention after setup", and this is the platform that was left dark).
     The brand defect that would have made that embarrassing is fixed and
     guarded, so this is now a *safe* first unattended publish.
   - **YouTube may hold API uploads private** until the Google Cloud project
     passes its audit. That is a YouTube-side restriction nothing in this repo
     can change.

   **To hold it back** until you have watched one land: disable **YouTube
   Shorts Auto-Generate and Publish** in the Actions tab — no code change and
   no queue to clear — or ask for `--privacy unlisted` for the first few.

   **Updated 8 Oct (second session) — the run is now safe either way.**
   `youtube_scheduled.yml` gained: a preflight that names the missing secret
   and stops before rendering; a duplicate guard backed by
   `logs/youtube_published.json` so a re-run cannot publish the same Short
   twice (a skip is green, and `force=true` overrides); a job summary; a
   `YT_PRIVACY` repository variable for owner-side privacy control; and a
   labelled issue opened (or commented on) whenever a run fails. A successful
   publish is committed back to the repo, so the channel's history is readable
   without opening YouTube. Full detail in `YOUTUBE_AUTOMATION.md`.

   **Outcome, 11 Oct 2026: the first unattended run failed, safely.** The
   Friday 9 Oct run rendered the Short and died at the upload with
   `401 invalid_client — The OAuth client was not found`; nothing was
   published, and the workflow opened issue #12. That is the hardening doing
   its job: a red run nobody could explain became a named cause in one line.
   The fix is owner-side — see item 3.

10. **`tools/verify_live.py` cannot run from the sandbox** (unchanged): it
    reaches `docoga.com.ng` over the network and fails with
    `URLError: TLS/SSL connection has been closed (EOF)`. The 1 Oct question
    (*is the live build the v2 pass model?*) is still unanswered and needs the
    owner's machine.

11. **State SEO pages stand at 12 of 37** (36 states + FCT), 48 pages — and
    **they were measured before anything was added to them** (8 Oct 2026). The
    result is in `docs/STATE_TENANCY_RESEARCH.md` §1: same-tool state pages are
    a median of **94.2% identical**, with a median of **3 unique words** per
    page; the worst pairs (Enugu/Oyo/Kano) are 99.6% identical. That is
    Google's doorway-page pattern almost verbatim ("pages targeted at specific
    regions or cities that funnel users to one page"), and the failure mode is
    deindexing, not a ranking slip.

    **So expanding to 37 is not the next step — earning the existing 48 is.**
    Adding ~100 more pages like these would have been the single most damaging
    thing available to do to the site's search traffic.

    The research that replaces the guesswork is done (`STATE_TENANCY_RESEARCH.md`):
    17 of 37 jurisdictions now have a named, sourced statute or an honest
    negative finding (Lagos and Edo down to section level from primary state
    sources; Cross River and Kwara from official state law portals; Rivers has
    \*two\* statutes and its Landlord & Tenant Law Cap 75 s.75(1) makes rent
    payable **in arrears** by default — the reverse of the national assumption).
    Three pending bills must stay labelled as bills. One state we already
    publish four pages for (Ogun) has nothing verifiable behind it.

    `tools/audit_state_pages.py` measures it and will enforce it (≤80%
    similarity, ≥250 unique words, ≥500 body words) — **deliberately not wired
    into `qa.py` yet**, because a gate that fails all 48 pages gets deleted
    rather than obeyed. It gets wired the moment the enrichment lands.

    **Where it actually stands after session 20 — measured, not estimated:**

    | pair type | similarity | vs target (≤80%) |
    |---|---|---|
    | both pages for a verified state | **44–46%** | inside |
    | one verified, one not | 49–54% | inside |
    | both pages for an unverified state | **93%** | outside |
    | **overall median** | **53%** (was 94.2%) | — |

    The method works. The doorway risk is now **co-located with the eight
    states that have not been researched**: anambra, delta, enugu, kaduna,
    kano, ogun, oyo, plateau. Two of them — **ogun and plateau** — have
    nothing verified behind them at all and, per the publication rule in
    `docs/STATE_TENANCY_RESEARCH.md` §10, arguably should not have four-tool
    pages.

    One target is still missed even by the verified pages: **unique words per
    page runs 72–211 against a target of 250** (Lagos is highest at ~200).
    Closing that needs more genuinely local content per state — courts, areas,
    LGAs, zones, local practice — which means more research per state, not more
    template.

---

*This file is the contract between sessions. Update it at the end of EVERY session. If you're reading this, you have everything you need. Continue naturally.*
**Read-only authentication result — 10 Oct:** run `38044854641` on `caefff4`
succeeded with publish/probe skipped: user endpoint HTTP401/API1000, account
endpoint HTTP200/active, deployment account read HTTP200. Account-token endpoint
mismatch confirmed for this credential; no credential change. Authorized Worker
retry starting with corrected validation; site still blocked pending actual
deploy exit and harmless probe. Resend remains disabled.

**Worker release succeeded — 10 Oct:** `79dbe42`, run `38044892137`,
actual `deploy_exit=0`, version `44552c88-d7d0-4df6-bbfc-c47f55263eae`.
Live missing-code /activate probe passed (400/code required, no issuance/email).
Dashboard vars preserved via --keep-vars. Authorized site release starting next;
site result pending. Resend remains disabled; no email/payment test performed.

**Release complete — 10 Oct 2026:** site `1335863`, run `38044933960`,
actual `deploy_exit=0`, version `8817b0c7-5863-49b6-becc-00f284ea411a`.
Only ./site uploaded; index.html and success.html updated, 63 assets unchanged.
Cache purge API success=true. Verify/build succeeded; Worker job skipped on
site marker. Worker-first/site-second release complete. Public browser rendering
not independently checked from restricted sandbox. Resend still disabled; no
new payment, issuance or email. Next owner-guided step requires separate explicit
resend enablement and ONE existing-pass resend approval, then NEW Brevo event
and actual receipt. Never use logs/dashboard Resend or /verify as a test.

**Resend enabled and verified — 10 Oct 2026 (owner-performed, screenshot evidence):**
Owner added Production Text variable `RESEND_EMAIL_ENABLED=true` in the dashboard
(Secret unticked, Previews unticked); Cloudflare deployment `b70c569e` ("Add
variable") became Active at 100%, above Worker release `44552c88`. Dashboard
secrets/vars survived. Owner reopened the saved success page for the EXISTING
qualifying purchase and tapped Resend ONCE (battery-low phone, so the on-page
status line was not screenshotted). At about 12:00 the pass email arrived in the
owner's **Primary** inbox from DocOga with the pass subject line (screenshot).
Receipt confirms sender authentication works end-to-end. No new payment, no
Brevo-log Resend, no repeat attempt; no code/recipient/reference stored. The NEW
Brevo event was not separately inspected; receipt was the decisive proof. Flag
stays enabled; endpoint limit is 60s spacing/3 attempts per UTC day per pass,
not globally atomic. Old Brevo failure is historical.

## B2B research continuation — 10 Oct 2026

Owner requested very deep B2B groundwork before any USD pricing. Completed desk
research and repository capability audit in `docs/B2B_OUTREACH_GROUNDWORK.md`,
with `docs/B2B_DISCOVERY_WORKBOOK.md` and three empty CSV templates. Earlier
`B2B_DISCOVERY.md` is marked historical/superseded for execution. Official
WhatsApp policy covers App and Platform and requires opt-in; NDPC GAID Article
18(1)(a) requires consent for direct marketing. Public directory numbers are NOT
permission. Use introductions with prior recipient agreement, authorised channel
invitations or inbound. No messages/registrations/purchases/pilots sent or created.
Seven buyer research candidates and four channel/expert candidates; all
uncontacted, need/budget/authority/consent unknown. NIESV Abuja branch direct fetch
failed (indexed only); no current registration independently verified.

Important repository findings: Business card promises annual shared-team access,
logos, invoice/transfer and named-human support; no complete implementation was
established. Privacy page understates pass/email/reference processing; terms
activation wording and non-transferability need reconciliation with runtime/team
claims. Flagged as sales/pilot readiness prerequisites, NOT edited or deployed.
No nationwide legal correctness or replace-lawyer claims. Prefer routine-document
workflow discovery; synthetic receipt test only if interviews identify that pain.
Business pricing unset, retail price/payment link unchanged, no USD work.

Next: present findings and ask only whether owner has a warm property-operator
relationship or an allowed channel introduction (no private contact values).
Review ONE exact invitation before sending. First five interviews test problem;
up to 12 purposive organisation interviews, raw counts/contrary evidence, no
market extrapolation. Conditional pilot/commercial gates in dossier. Zero B2B
interviews or revenue established by research. No new code tests needed for docs;
CSV parse and git diff checks run. Continue screenshot→one next action method.

**B2B paused — owner instruction, 10 Oct 2026:** owner said "Level the b2b
for now", understood in context as leave/pause B2B for now. Research and workbook
are preserved; do not proceed with recruitment, messages, interviews, pilots or
pricing unless owner resumes. No B2B outreach has been sent. No new task selected.

**Owner interaction constraint — 10 Oct 2026:** owner said "I don't want to
meet anyone". Do not require in-person meetings or assume willingness for calls
or live interviews. B2B remains paused. If owner explicitly resumes, propose
permissioned written/asynchronous options instead; this statement does not
authorise outreach, automation, lead scraping or pricing changes.

**Analytics access request — 10 Oct 2026:** owner wants agent access rather than
repeated report screenshots. Connector lookup `google_analytics` returned
unsupported; no direct GA connection exists. Sandbox cannot reach Google API
hosts. Proposed read-only GA4 Data API reporter executed in GitHub Actions,
prefer keyless Workload Identity Federation with a dedicated service account
and Viewer permission on DocOga property only; never invent an agent email or
request passwords/keys in chat. Official Google Data API quickstart and WIF
deployment-pipeline docs researched. No reporter/identity/access created yet.
Next owner screenshot: Google Cloud console current project-selector screen;
no billing/free-trial activation or broad IAM roles. Verify zero-cost path and
GitHub OIDC/secure aggregate-report retrieval before account setup. B2B paused.

**Analytics durable-access research completed + environment verified — 10 Oct 2026:**
see `docs/ANALYTICS_ACCESS_RESEARCH.md` (rewritten with direct test results). Key
corrections from live testing: (1) agent CANNOT trigger workflows — `gh workflow
run` returns HTTP 403 Resource-not-accessible-by-integration on the dispatches
endpoint; (2) agent CANNOT read run logs — job logs redirect to
results-receiver.actions.githubusercontent.com / productionresultssa*.blob.core.
windows.net, outside the sandbox allowlist (EOF); (3) agent CANNOT download
artifacts (same blocked host); (4) agent CAN read AND write repo contents
(permissions admin/maintain/push/triage; pushes trigger Verify). Therefore any
design whose result is read from a run log or artifact is UNUSABLE; the report
must be committed into the repository. Confirmed cost gate: GitHub Free, cycle
included usage $2.96 (docoga $1.97), no payment due, Actions budget Stop
usage=Yes budget=$0 (hard stop). Confirmed runners have unrestricted egress
(existing net-probe.yml egress-bridge) while the sandbox does not. Confirmed
existing YouTube OAuth client/refresh token in repo secrets, but reusing it is
rejected (7-day Testing expiry + sensitive-scope verification; shared blast
radius). Recommended design = repo-committed GA4 snapshot: property-only Viewer
service account, GitHub OIDC->WIF->scoped analytics.readonly token, SHA-pinned
google-github-actions/auth, small aggregate script, commit analytics/reports/
latest.json with [skip ci]; refresh triggered by pushing a request file (push
works) and/or workflow_dispatch (owner taps) and/or schedule (default branch
only, delayed/dropped, needs approved merge to main). Official Google Analytics
MCP exists but is experimental and not attached/usable here.

Still unresolved: numeric GA4 property id, existing Cloud project suitability,
owner Analytics admin access, WIF/OIDC policy, Actions workflow permissions
policy (may govern whether GITHUB_TOKEN may push report commits), and any real
authenticated runReport. NO identity, IAM, API enablement, workflow, budget
change or deployment performed. No secrets requested. Next owner step remains a
Google Cloud console project-selector screenshot; no billing/trial yet. All work
stays on session branch arena/47d148f1-docoga. B2B paused.

**Google Cloud selector screenshot — 10 Oct 2026, 13:14 local:** owner opened
project selector; **Recent** tab is selected, not All. Checked current project:
`My First Project`, ID `apt-trainer-367908`. Other fully visible entries:
`tagemeonline` (ID `tagemeonline`), `My First Project` IDs
`feisty-delight-366811`, `inbound-rock-367406`, and `mystical-being-367405`.
Another row is partially visible; this is NOT a complete project inventory.
Earlier claim that the generic project name identifies the YouTube/Gemini
project was an inference, not evidence; no project association or suitability
has been verified. No project selected/created or settings changed in this
step. Next single action: tap **All** in the selector, send that screen, do not
select/create anything yet. Continue saved screenshot progress one screen at a
time; no billing/trial/IAM action authorised by this screenshot.

**Google Cloud credentials screenshot — 10 Oct 2026, 13:21 local:** owner is
now on APIs & Services → Credentials (not the requested All-projects list).
Visible: project display name My First Project; an API key entry named Game
with Gemini API restriction text; OAuth client named DocOga, web application,
created 25 Sep 2026; Service Accounts table says no service accounts to display.
No secret values copied. This supports an existing DocOga-related client but
does NOT prove its match to GitHub secrets, active use, Analytics permission,
or the selected project's ID (not visible). Do not infer the ID from previous
selector because navigation may have changed it. Yellow OAuth verification
banner is not a reason to edit the existing client/consent screen for the
proposed service-account approach. Next single action: tap current My First
Project chip and screenshot the checked project row to confirm exact ID; no
credential details or secret values needed, no creation/permission changes yet.

**Project confirmed by screenshot — 10 Oct 2026, 13:24 local:** selector opened
above the same Credentials page, checked My First Project row has ID
`apt-trainer-367908`. Thus this is the project displaying the DocOga OAuth
client and Game API-key entry. This does not establish GA property access or
current GitHub credential use. Next: open project-scoped Service Accounts list
https://console.cloud.google.com/iam-admin/serviceaccounts?project=apt-trainer-367908
and screenshot; inspection only, do not create keys/accounts or change billing.
No need to repeat project identification or inventory all unrelated projects.

**Service Accounts navigation — 10 Oct 2026, 13:29 local screenshot:** IAM &
Admin → Service Accounts opened but says "To view this page, select a project";
project-scoped link did not retain selection. Recent-project top-left card is
My First Project with explicit ID apt-trainer-367908. Next single action: tap
that top-left card and screenshot loaded Service Accounts page. Do not create
project/account/key, enable billing, or infer absent accounts from this unscoped
page. Confirmed project ID remains apt-trainer-367908; no new identification
loop needed.

**Commit-back mechanism VERIFIED — 10 Oct 2026, 13:33 local:** on screenshot
owner selected My First Project (apt-trainer-367908); Service Accounts empty
("No rows to display"). Agent then built branch-only reporter scaffold:
`.github/workflows/analytics-snapshot.yml`, `tools/analytics_snapshot.py`,
`analytics/refresh-request.json`. Push 1889753 triggered run 38052387346;
ALL steps success, including "Commit snapshot back to the repository". Bot
commit f12c5b6 wrote analytics/reports/latest.json + 2026-10-10.json. Agent
fetched and read BOTH via git pull and `gh api .../contents/...` — proof that
push-trigger -> runner -> commit-back -> agent-read works despite dispatch/log
restrictions. Snapshot mode=placeholder, property_id=null, rows=[]; NO Google
call, real data or secret involved. Live script exists but not enabled (auth
step is TODO; once vars set, must add SHA-pinned WIF auth + live fetch step).
Mechanism remaining risk resolved; numeric GA4 property id, Viewer grant, WIF,
API enablement and actual authenticated report still pending. Next owner step:
tap **Create service account** at top of current Service Accounts page; show
creation form BEFORE filling/submitting. Intended name docoga-analytics-reader;
no project IAM role (Analytics Viewer is assigned separately in GA). No billing
or OAuth-client change. Do not generate a key. B2B paused.

**Service-account creation form — 10 Oct 2026, 13:36 local screenshot:** form
open in apt-trainer-367908 (email preview confirms project). Name, ID and
description empty; optional Permissions and Principals with access sections
collapsed. Buttons Create and continue / Create and close visible. Next owner
instructions: name and ID `docoga-analytics-reader`; description `Read-only
DocOga GA4 reporting from GitHub Actions.`; leave both optional sections empty
and tap **Create and close**, then screenshot returned list. This creates only
the reporting identity, not GA access. Do not assign Cloud Viewer/Editor/Owner,
generate a key, alter OAuth client or enable billing. Creation is NOT yet
confirmed; verify resulting row/generated email before property permission grant.

**Service account CREATED — 10 Oct 2026, 13:39 local screenshot:** toast says
"Service account created"; list shows docoga-analytics-reader, Enabled, email
`docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com`.
Screenshot confirms identity creation, NOT GA Viewer access, key absence or
project IAM bindings (not independently inspected). No authenticated GA report.
Next single action: open https://analytics.google.com/ in another tab, send
landing screen with account/property name visible; hide personal details. Need
confirm DocOga property and numeric ID before property-level Viewer grant to
this now-observed service-account email. No need to revisit Cloud creation;
no keys/OAuth/billing changes. WIF and API enablement remain pending.

**Analytics landing screenshot — 10 Oct 2026, 13:43 local:** currently selected
property label `reel-31bcb`, breadcrumb truncated `Default Account for Fire...`.
Not yet confirmed DocOga property. Home shows zero active users and collection
setup prompt, but do NOT use these numbers as DocOga traffic baseline. Blue
Benchmarking popover visible. Next action: tap property dropdown `reel-31bcb`
at top beside Analytics logo, send account/property selector. No permission
changes until correct property verified; no need to change collection settings.

**GA selector screenshot — 10 Oct 2026, 13:47 local:** All tab selected,
visible account Default Account for Firebase; visible property names reel-241ea,
reel-31bcb, tageme-2d59b, tagemeonline, tagme-c07c2. No DocOga-named property
visible; do not infer deletion/nonexistence or grant Viewer to a guessed
property. Next: tap Google profile avatar A at upper right to inspect signed-in
account/switcher, redact full personal emails in screenshot but retain account
labels/initials. Need locate Google login used to set up DocOga Analytics. Do
not create a new property or change existing tracking. Cloud service-account
project need not use same Google login as Analytics property administration.

**Owner account decision — 10 Oct 2026:** owner says "The current account is
what I want". Keep current Google Analytics login; do not continue requesting
account switch. Property names alone do not establish which web stream matches
DocOga. Next inspect Admin on current property (dismiss selector, bottom-left
gear) then Data streams, comparing website URL and measurement ID to repository
tracking ID before any Viewer grant. No new property/retagging authorised.

**Analytics Admin screenshot — 10 Oct 2026, 13:51 local:** owner kept current
login; Admin open for reel-31bcb. Visible Data streams under Data collection
and modification; next single action tap Data streams and screenshot list.
Do not tap account/property access management yet: stream website and tracking
ID must establish DocOga relationship first. No property/access/tracking edits.

**Data streams screenshot — 10 Oct 2026, 13:54 local:** reel-31bcb lists REEL
iOS, REEL Android, Tagme Android, Tagme iOS and REEL Web. Each visible row
states no data received in past 48 hours; not evidence about DocOga. Only
visible web stream REEL Web, stream ID 3880430747; website and measurement
ID not shown. Next single action open REEL Web row and screenshot details to
compare URL and measurement ID with site tracking tag G-GO8VZB3R28. Do not
rename/add/delete streams or alter measurement before this comparison.

**REEL Web mismatch — 10 Oct 2026, 13:56 local screenshot:** existing REEL Web
stream details measurement ID differs from DocOga's repository tag
G-GO8VZB3R28; stream URL field shows no visible value. Do not use this stream
as DocOga baseline or grant reporting access on that assumption. Additional
repo check found site/index.html comment AND earlier SESSION_CONTEXT record
GA property name `inductive-seer-372707`, web stream docoga.com.ng. Historical
configuration clue, NOT independently verified property ownership/current
setup; numeric property ID still unknown. Next single screen: phone Back once
to Data streams, open property selector and search `inductive-seer-372707`.
Stay on owner's chosen Google login; do not create property or replace tag.
If no result, report the search result and resolve explicitly with owner,
not silently switch login or invent property. Reader service account remains
created; Viewer/WIF/API/report access pending.

**Owner authorised dedicated property — 10 Oct 2026:** owner explicitly chose
"new dedicated DocOga property in this account" after explanation that current
REEL Web tag differs, mixing REEL/Tagme data is undesirable, and history will
not migrate. Keep current Google Analytics login and current Analytics account;
create separate property named DocOga, not a new account. Continue one screen
at a time: close stream details to Admin/Data streams, tap upper-left Create
then Property, screenshot creation form before entering/submitting. Proposed
property settings: DocOga, Nigeria reporting timezone, NGN currency; confirm
form labels first. No property created yet, no retagging/deployment done. New
web stream/tag and Viewer grant/WIF/report auth still pending. Owner choice
establishes direction, not proof of completed GA setup or production deployment.

**Dedicated GA property form — 10 Oct 2026, 14:03 local screenshot:** step 1
Property creation open; name empty, defaults United States / Los Angeles time
and US Dollar. Next instructions: name DocOga; country Nigeria; timezone
GMT+01:00 Nigeria/Lagos (label may vary); currency Nigerian Naira (NGN); tap
Next, screenshot Business details. Property not created yet. Do not retain US
defaults; no deployment/stream/tag changes. Owner phone battery 12%, keep
instructions short and one screen at a time.

**Business details form — 10 Oct 2026, 14:07 local screenshot:** step 2 open;
industry category required dropdown says Select one, choices not visible;
business size required radio choices Small 1–10, Medium 11–100, Large 101–500,
Very Large 501+. Neither selected. Step 1 progressed but entered name/timezone/
currency not visible here, so not independently verified. Next single action
open Industry category dropdown and send choices; choose closest accurate
category, do not invent a menu label or classify product as a law firm.
Business size must reflect actual team, not traffic/revenue. Property not yet
confirmed created; no data stream, tracking deployment or GA Viewer access.

**Industry options screenshots — 10 Oct 2026, 14:11–14:13 local:** dropdown
choices include Law & Government, Business & Industrial, Computers &
Electronics, Real Estate, Reference and Other Business Activity. Latest screen
has Small 1–10 employees selected; industry still blank with required-field
error. Recommend Law & Government as closest subject category for legal
information/document templates, not a claim of law-firm status. Next: select
Law & Government (search Law), retain Small, tap Next and screenshot Business
objectives. No need for further category screenshots. Phone battery 7%; progress
saved if owner pauses. Property creation not yet confirmed.

**Business objectives screenshot — 10 Oct 2026, 14:16 local:** step 3 open,
all boxes empty. Options Generate leads, Drive sales, Understand web and/or
app traffic, View user engagement & retention, Other business objectives.
Recommend Understand web and/or app traffic + Drive sales, then Create and
screenshot result (data collection or terms). Objective selection does not
install purchase tracking or establish sales data. Property not yet confirmed
created; phone battery 5%, progress saved. No website changes/deployment.

**GA data collection screen — 10 Oct 2026, 14:18 local:** step 4 Start
collecting data displayed; previous property/business/objective steps have
checkmarks, supporting completed property-creation wizard stage. Property
name/numeric ID not shown yet. Platform buttons Web, Android app, iOS app;
next action tap Web, send stream setup form before submission. Stream not
created, new measurement ID unknown, website tag unchanged; Viewer/WIF/report
access pending. Phone battery 4%; progress saved for pause/recharge.

**Web stream setup form — 10 Oct 2026, 14:19 local:** Set up data stream open;
Website URL field shows protocol selector plus placeholder www.mywebsite.com,
Stream name placeholder My Website, Enhanced measurement toggled on with Page
views, Scrolls, Outbound clicks, +4 more. Next instructions: set protocol
https, Website URL docoga.com.ng, Stream name DocOga Web, leave enhanced
measurement on, tap Create and continue, screenshot result showing measurement
ID. Do NOT paste a URL with credentials/path; no site deployment yet. New tag
will still need to replace ANALYTICS_ID in site code and be deployed before
data flows. Phone battery 4%.

**DocOga web stream CREATED — 10 Oct 2026, 14:22 local screenshots:** stream
name DocOga Web, STREAM URL https://docoga.com.ng, STREAM ID 16101599953,
MEASUREMENT ID G-BQ1YTR0ZZJ, enhanced measurement on. Banner still says data
collection not active / No data received, expected because site still uses old
tag G-GO8VZB3R28. Measurement ID is public (page source) so recording it is
safe. NOT yet done: property-level Viewer grant to
docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com; numeric
GA4 PROPERTY ID still unread; Analytics Data API enablement; WIF; repo vars;
live fetch; site tag change + deploy; real report. Next owner action (battery
~3%, may charge first): Admin (bottom-left gear) -> Property -> Property access
management -> Add users, paste the service-account email, role Viewer, uncheck
notify-by-email, then screenshot. Do not grant Editor/Administrator. Site code
change and any deployment remain separate, owner-approved steps.

**Property access management screenshot — 10 Oct 2026, 14:51 local:** DocOga
property access list shows exactly 1 row, the owner's own Google account as
Administrator. Owner's personal email intentionally NOT recorded here (privacy);
do not commit it. Confirms DocOga property exists under the owner's current
Analytics account. Service account not yet added. Next: tap Add users, enter
docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com, role
Viewer, uncheck notify-by-email, Add, then screenshot the 2-row list. Do not
grant Editor/Administrator. Numeric GA4 property ID still unread; API
enablement/WIF/repo vars/live fetch/site tag change still pending.

**Add roles dialog — 10 Oct 2026, 14:54 local:** DocOga property; email field
empty; Notify new users by email still CHECKED; Viewer already selected; data
restrictions (No Cost Metrics / No Revenue Metrics) unchecked. Next: type
service-account email, uncheck notify, keep Viewer, tap Add top-right, then
screenshot 2-row access list. Owner personal email visible in background but
deliberately NOT stored. No Editor/Administrator. Remaining: numeric property
ID, Analytics Data API enablement, WIF, repo variables, live fetch, site tag
change and deploy, real authenticated report.

**GA Viewer grant CONFIRMED — 10 Oct 2026, 14:56 local:** DocOga property access
list now 2 rows; docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com
has role Viewer; owner remains Administrator. Read-only Analytics access for the
reporting identity now granted (screenshot-confirmed). Next single action: Admin
-> Property -> Property details, screenshot to capture numeric PROPERTY ID.
Remaining after that: enable Analytics Data API in apt-trainer-367908; create WIF
pool/provider and bind service account (roles/iam.workloadIdentityUser to
principalSet for repository_id 1376068242 restricted to the analytics workflow);
set repo variables GA_PROPERTY_ID / GCP_WORKLOAD_IDENTITY_PROVIDER /
GCP_SERVICE_ACCOUNT; add SHA-pinned google-github-actions/auth + live fetch to
analytics-snapshot.yml; separately update site ANALYTICS_ID to G-BQ1YTR0ZZJ and
deploy; then verify a real authenticated report. No site change/deploy yet.

**GA property details CONFIRMED — 10 Oct 2026, 14:58 local screenshot:**
NUMERIC GA4 PROPERTY ID = 558370565. Property name DocOga; timezone Nigeria
(GMT+01:00) Nigeria Time; currency Nigerian Naira; industry Law & Government;
business size Small 1–10 employees; objectives listed as Drive sales,
Understand web and/or app traffic, View user engagement & retention (three
shown; harmless, not re-edited). Web stream measurement ID G-BQ1YTR0ZZJ.
Viewer grant to service account already confirmed. NEXT: choose auth path for
the workflow. Options under consideration: (A) WIF (no long-lived secret, more
mobile screens/APIs: sts + iamcredentials + WIF pool/provider/binding), or
(B) service-account JSON key stored ONLY as an encrypted GitHub Actions secret
(fewer steps, long-lived, needs rotation; repo already stores other long-lived
secrets). Must still enable Analytics Data API in apt-trainer-367908 either way.
No key created, no API enabled, no repo variables set, no site tag change yet.

**WIF workflow + runbook committed — 10 Oct 2026:** rewrote
`.github/workflows/analytics-snapshot.yml` with pinned
`google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093` (v3.0.0,
latest release), `token_format: access_token`, explicit
`access_token_scopes: .../analytics.readonly`, gated live step using
vars.GA_PROPERTY_ID/GCP_WORKLOAD_IDENTITY_PROVIDER/GCP_SERVICE_ACCOUNT, plus
placeholder fallback. Added `docs/ANALYTICS_SETUP.md` owner runbook. Validated:
pre_push + qa green; push 7bd8adb then 5e1f974 (refresh request) triggered
analytics-snapshot run 38058018325 = SUCCESS (placeholder mode, vars unset), so
the new YAML/auth-step structure parses and the push->refresh path works.
Still not done: enable analyticsdata/sts/iamcredentials APIs, create WIF
pool+provider, bind workloadIdentityUser to repository_id 1376068242, set 3 repo
variables, then live run; and separately the site tag change to G-BQ1YTR0ZZJ +
deploy. Owner next: Cloud Shell script (step 1) then repo variables (step 2).
No secrets involved in variables. Property ID 558370565; stream G-BQ1YTR0ZZJ.

**Owner location — 10 Oct 2026, 17:06 local screenshot:** still on Analytics
→ DocOga Property details, ID 558370565, Nigeria time/NGN confirmed again.
This is NOT Google Cloud; no evidence owner ran Cloud Shell script or enabled
APIs/WIF. Next single action: open Cloud console dashboard in existing Cloud
tab or https://console.cloud.google.com/home/dashboard?project=apt-trainer-367908
and send screen before activating Cloud Shell. Do not repeat GA setup or
request secrets. Keep screenshot-by-screenshot guidance, not a multi-step dump.

Workspace Git checkpoint on resumption: local HEAD is base 7ee8d79 with prior
session files restored as modified/untracked; remote session branch is
 df74bf2ee94b28442b2550a9487b3337bfd706e3. Preserve all files; reconcile local
Git history with verified remote before any commit/push. No reset/force push.

**Owner requests Cloud project display-name change — 10 Oct 2026, 17:09:**
owner dislikes My First Project and asks to change it. Dashboard screenshot
confirms project ID apt-trainer-367908 and project number 635194176409.
Recommend display name DocOga; this is not a project-ID change and does not
change the existing service-account email. Next single action: tap Go to
project settings at bottom of Project info card (upper-left) and screenshot
before editing. Rename not yet performed; Analytics property already DocOga.
WIF/API setup paused at this screen; no billing/resource deletion. Local Git
history reconciliation remains pending; preserve restored changes.

**Cloud project Settings screenshot — 10 Oct 2026, 17:13 local:** Project
name editable field shows My First Project with Save at right of same field.
Project ID apt-trainer-367908 and number 635194176409 shown unchanged. Next:
replace only Project name with DocOga, tap Save at right, screenshot result.
Do not touch Migrate, Shut down, or Manage billing. Rename not yet confirmed;
no impact to identifier/email intended, WIF/API setup still pending.

**Cloud project rename CONFIRMED — 10 Oct 2026, 17:15 local:** owner says
Saved; screenshot Project name and top project chip both show DocOga. Project
ID apt-trainer-367908 and project number 635194176409 unchanged. Do not repeat
rename steps. Next single action: dismiss keyboard, tap Cloud Shell terminal
icon (>_) in top toolbar between gift icon and circled 1, send startup/prompt
screen. No script run/API enablement/WIF setup confirmed yet. Do not request
keys or activate billing/trial; inspect first startup prompt before proceeding.

**Cloud Shell first-use prompt — 10 Oct 2026, 17:17 local screenshot:**
Cloud Shell panel open beneath DocOga project Settings. Intro dialog explicitly
states "Cloud Shell is free for all users" and offers Cancel / Continue.
Next single action: tap Continue, wait for terminal or next prompt, screenshot;
do not paste setup script yet. This initializes Cloud Shell only, not Analytics
API/WIF configuration and not proof of billing status of any commands run later.
No credentials requested. Project name DocOga/ID apt-trainer-367908 remains.

**Cloud Shell READY — 10 Oct 2026, 17:23 local screenshot:** terminal welcome
explicitly confirms active project apt-trainer-367908 and idle shell prompt.
Cloud project display name DocOga. No API/WIF commands yet evidenced. Revised
next action is ONE explicit-project API enable command, not the old all-at-once
script: `gcloud services enable analyticsdata.googleapis.com iam.googleapis.com
 iamcredentials.googleapis.com sts.googleapis.com --project=apt-trainer-367908`.
Send output or authorization prompt; stop if billing/trial is requested. Adding
IAM API explicitly supports subsequent WIF pool/provider operations. Do not
run old runbook's unbounded `|| true` block; review and tighten provider trust
(workflow/ref/events + numeric repo/owner IDs) before owner executes WIF setup.
No keys, broad resource roles or production/tag changes in this step. APIs
not confirmed enabled until actual success output. Local/remote history must
still be reconciled safely before commit/push; no force push or lost work.

**Required APIs enabled — 10 Oct 2026, 17:25 local screenshot:** terminal
shows explicit-project enable command for analyticsdata, iam, iamcredentials,
sts and "finished successfully", then idle prompt. Owner-executed success;
no authenticated GA report yet. Next single command create WIF pool
`github-actions` in global location/project apt-trainer-367908 with display
name `DocOga Analytics via GitHub`. This creates pool only, not provider/trust
or service-account impersonation binding. If already exists or permission error,
inspect output instead of `|| true`/blind retry. Provider condition must later
restrict repo/owner numeric IDs + workflow + authorised branch/events. Do not
run previous all-at-once runbook. No keys/billing/site changes in this step.

**WIF pool CREATED — 10 Oct 2026, 17:27 local screenshot:** terminal says
Created workload identity pool [github-actions]. Next command creates provider
`github` in that pool with explicit repo ID 1376068242, owner ID 120726541,
ref refs/heads/arena/47d148f1-docoga, exact workflow_ref for analytics-snapshot.yml,
events push/workflow_dispatch only. Official GitHub OIDC reference confirms
workflow_ref is the current workflow claim (job_workflow_ref is for reusable
workflows). Daily schedule/main intentionally NOT trusted until approved rollout.
Provider and service-account binding not yet created/confirmed; no live report.
Old all-in-one runbook removed/replaced with staged restricted commands in
ANALYTICS_SETUP.md; no masked errors/|| true. Script metadata hardening still
pending; no claim current scaffold preserves all sampling/data-loss/timezone.

Git history reconciliation completed safely this reply: compared EVERY remote
tracked file to restored workspace (only SESSION_CONTEXT differed); saved full
workspace in git stash plus context backup outside repo, fast-forwarded existing
session branch to df74bf2, restored added context notes. No branch switch, reset,
force push or dropped files. New session notes now can be committed normally.

**Cloud Shell reconnected — 10 Oct 2026, 17:31–17:32 screenshots:** first
screen said Establishing connection; latest shows idle prompt with previous
API enable success and pool creation success. No provider-create command or
output visible. Do not assume it ran or retry blindly if owner says already
executed. Next paste previously supplied restricted create-oidc github command
at ready prompt and screenshot result. No changes to confirmed pool/API steps.

**Provider command incomplete — 10 Oct 2026, 17:34 screenshot:** only base
`gcloud iam workload-identity-pools providers create-oidc github` was executed;
CLI reports required attribute-mapping/issuer-uri missing and usage text. No
provider created by this failed validation; existing pool/APIs unaffected.
Next give FULL provider command as ONE LINE to avoid phone multiline copying
error; retain exact repo/owner IDs, working ref/workflow_ref and push/dispatch
condition. Screenshot result before binding. No need to repeat pool creation.

**WIF provider creation output — 10 Oct 2026, 17:36 screenshot:** visible
"Created workload identity pool provider [github]" after full create command.
Terminal also has repeated/highlighted command fragments below that output;
do not assume saved condition exactly matches intended scope without readback.
Next ONE read-only `gcloud iam workload-identity-pools providers describe github`
with explicit project/location/pool and formatted name/state/issuer/mapping/
condition. Verify exact repo/owner IDs, branch/workflow_ref and push/dispatch
before adding service-account impersonation binding. Do not create provider
again. Binding, repo vars and live GA call still pending. No secret/token needed.

**Cloud Shell ready again — 10 Oct 2026, 17:39 screenshot:** owner confirms
reconnection; screenshot still shows provider creation success and idle prompts,
not describe output. Next repeat the COMPLETE single-line read-only provider
describe command, not creation. Need saved attributeCondition/mapping/issuer
readback before service-account binding; no inference from shell command text.

**Provider readback VERIFIED — 10 Oct 2026, 17:42 screenshot:** describe output
shows state ACTIVE; issuer https://token.actions.githubusercontent.com; provider
projects/635194176409/locations/global/workloadIdentityPools/github-actions/providers/github.
Saved attributeCondition matches repository_id 1376068242, repository_owner_id
120726541, ref refs/heads/arena/47d148f1-docoga, exact
johnAzani/docoga/.github/workflows/analytics-snapshot.yml@refs/heads/arena/47d148f1-docoga,
events push/workflow_dispatch. Mappings for google.subject and repo/owner/ref/
workflow_ref/event_name present. Next single-line command adds
roles/iam.workloadIdentityUser on docoga-analytics-reader service account only,
member principalSet://iam.googleapis.com/projects/635194176409/locations/global/workloadIdentityPools/github-actions/attribute.repository_id/1376068242.
This binding relies on verified provider condition; no broad project resource
roles, keys, billing or website change. Binding success NOT yet confirmed.
After binding output, configure three GitHub repo variables and verify real
scoped GA call. Schedule/main remain outside allowed trust until approved.

**Service-account WIF binding CONFIRMED — 10 Oct 2026, 17:45 screenshot:**
Cloud Shell reports Updated IAM policy for docoga-analytics-reader at
apt-trainer-367908; output shows roles/iam.workloadIdentityUser with member
principalSet://iam.googleapis.com/projects/635194176409/locations/global/workloadIdentityPools/github-actions/attribute.repository_id/1376068242.
Verified provider condition from prior readback remains required to narrow
repo member to exact workflow/ref/events. No key created or site change.
Google-side planned setup now screenshot-confirmed; actual WIF token exchange
and authenticated GA report still untested. Next single screen: GitHub repo
Settings -> Secrets and variables -> Actions -> Variables, direct URL
https://github.com/johnAzani/docoga/settings/variables/actions ; screenshot
before adding GA_PROPERTY_ID / GCP_SERVICE_ACCOUNT / GCP_WORKLOAD_IDENTITY_PROVIDER.
These are non-secret config values, not a credential upload. Do not re-run Cloud
commands or claim connected until actual report retrieved. Phone battery 11%.

**GitHub Variables screen — 10 Oct 2026, 17:47 screenshot:** correct DocOga
Actions secrets and variables page, Variables tab selected; repository has no
variables. New repository variable button visible. Next tap that button to open
form; first intended name GA_PROPERTY_ID, value 558370565. No variables added
yet; do not use Environment variables or Secrets for these non-secret config.
Continue one screen at a time; WIF binding confirmed, authenticated GA call
still pending. Phone battery 9%, saved progress available if paused.

**First repository-variable form — 10 Oct 2026, 17:49 screenshot:** Actions
variables / New variable with empty Name and Value fields, Add variable button.
Next enter Name GA_PROPERTY_ID and Value 558370565, click Add variable, send
resulting list. No variable confirmed saved yet; this is numeric GA property
ID, not stream ID/measurement ID. Remaining two config values follow separately.

**GA_PROPERTY_ID saved; reporter hardened — after the 17:53 WAT screenshot,
10 Oct 2026:** the latest Variables-page screenshot now shows repository variable
`GA_PROPERTY_ID` with exact value `558370565`; this is owner screenshot evidence.
The installed `gh` lacks the `variable` subcommand, and GitHub's Actions
variables REST endpoint returned 403 `Resource not accessible by integration`,
so the agent did not set or read repo variables. `GCP_SERVICE_ACCOUNT` and
`GCP_WORKLOAD_IDENTITY_PROVIDER` remain pending via the UI, one variable at a
time. Do not repeat the failed agent API path.

Hardened `tools/analytics_snapshot.py`: date windows now use the property-local
Africa/Lagos calendar and end two days ago; the query remains only aggregate
sessions/users/engagement by session default channel group; the response is
paginated with row-count/completeness checks; timezone/currency provenance and
thresholding, sampling, schema-restriction, and `(other)`-row data-loss flags
are preserved. HTTP errors are bounded and token-redacted; the access token is
never written to report output. Added six offline unit tests for query schema,
window, pagination, metadata, timezone, and redaction. All six pass; after
installing CI's test dependencies in an ignored local venv, the full Python
suite passed 69/69. `tools/qa.py` is green with two environment warnings (no
`.worker-secrets.env`; jsdom not installed); Python compilation and
`git diff --check` pass. No live API call, real-data commit,
site tag change, deploy or main merge occurred. Next one screen: add
`GCP_SERVICE_ACCOUNT` with value
docoga-analytics-reader@apt-trainer-367908.iam.gserviceaccount.com and send the
saved-variable screenshot. After all three exist, get explicit approval before
the first real aggregate report commit.

**Analytics hardening commit/push verified — 10 Oct 2026:** implementation,
unit tests and refreshed runbooks were committed as `1643e57` and pushed only
to `arena/47d148f1-docoga`. Local and remote branch heads matched. GitHub Verify
run `38070462480` and Cloudflare build check `38070462453` succeeded; site and
Worker deploy workflows were skipped. The build check reported only platform
Node 20/Ubuntu migration notices. `analytics/reports/latest.json` is still the
placeholder from run `38058018325` (`mode: placeholder`); this docs/code push
did not touch `analytics/refresh-request.json`, so no Analytics run or real-
data commit was triggered. Working tree was clean before this final log entry.

**All three repository variables listed — 10 Oct 2026, 18:20 WAT screenshot:**
GitHub Variables page now shows `GA_PROPERTY_ID`, `GCP_SERVICE_ACCOUNT`, and a
third row labelled `GCP_WORKLOAD_IDENTITY_P...`; the service-account value
preview begins `docoga-analytics-reader@apt...`, and the provider value begins
`projects/635194176409/locati...`. The first variable's complete value is
visible and correct. Long names/values are clipped in the list, so the screenshot
confirms rows/prefixes but not every character; do not claim an independent
readback. Agent API access remains 403. No workflow was triggered and no live
Analytics data has been committed. Next gate: explicitly ask whether the owner
approves one first live, read-only aggregate snapshot being committed to
`analytics/reports/latest.json` plus a dated report on the session branch. This
does NOT authorize a site tag change/deploy, default-branch merge, or schedule.

**First-live-snapshot approval received — 10 Oct 2026, after 18:20 WAT:** the
owner selected **Approve first snapshot** in the explicit approval prompt. Scope:
one live, read-only, seven-day aggregate fetch and commit of its sanitized JSON
to the session branch. No approval for site retag/deploy, main merge, schedule,
or broader WIF trust. Updated `analytics/refresh-request.json` locally with the
owner-approved request at `2026-10-10T17:27:05Z`; it has not yet been pushed at
this log point, so no live workflow or report commit has happened yet. Next:
commit and push this trigger path only with the session-context update, then
inspect the repository snapshot (not run logs) for `mode: live`.

**First live Analytics workflow attempt failed — 10 Oct 2026, 18:28 WAT:**
commit `f3fec02` on `arena/47d148f1-docoga` triggered run `38071879234`. The
configuration check and **Authenticate to Google (Workload Identity
Federation)** step succeeded, proving GitHub-to-Google WIF token exchange. The
**Write snapshot (live, read-only)** step failed; placeholder and commit-back
steps were skipped. `analytics/reports/latest.json` remains `mode: placeholder`
from run `38058018325`; there is no real-data commit. The agent can read run/step
status via GitHub API, but detailed logs redirect to blocked hosts, so the exact
GA4 API error was unavailable at this first inspection. The next owner action
at that time was to screenshot the failed step; the owner later shared the
message, documented below. No retry occurred at this stage.

**Live failure detail and parser fix — 10 Oct 2026, 18:34 WAT screenshot:**
owner opened run `38071879234` and its failed step. Visible error:
`analytics snapshot failed: Google Analytics response is missing a valid rowCount.`
The WIF exchange succeeded; failure is in our response parser, not proven to be
an IAM/API permission denial. Checked Google's official `RunReportResponse`
proto: `row_count` is proto3 `int32`, and `kind` is fixed
`analyticsData#runReport` ([schema](https://github.com/googleapis/googleapis/blob/master/google/analytics/data/v1beta/data.proto)). A new property with no collected traffic may return no rows and omit zero-valued `rowCount`; this is the likely cause, not yet confirmed from raw response. Updated parser to infer zero only for recognized RunReport responses with an empty rows list; otherwise it still fails closed. Added tests for valid empty and malformed/nonempty missing-count responses. Targeted suite 8/8 and full suite 71/71 pass; `tools/qa.py` is green with two environment-only warnings. `git diff --check` and `tools/pre_push_verify.sh` pass. Code/docs commit `801a1ea` was pushed to `arena/47d148f1-docoga`; at that point latest workflow remained the failed run `38071879234`, and no retry or data commit had occurred. The owner later authorized one retry; its successful result is recorded below.

**One approved Analytics retry succeeded — 10 Oct 2026, 18:51 WAT:** after
parser fix `801a1ea` and docs `29eff4e`, the owner explicitly approved one retry.
Trigger commit `4062832` started workflow `38073371592`; WIF, `Write snapshot
(live, read-only)`, and commit-back all succeeded. Bot commit `bbde8dd` added
`analytics/reports/latest.json` and `analytics/reports/2026-10-10.json` with
`mode: live`. The report covers 2–8 Oct 2026 in `Africa/Lagos`, has `NGN`
currency and zero rows (`row_count: 0`, `row_count_source:
implicit_empty_response`). This confirms the keyless read-only Analytics path,
not site traffic or purchases; the dedicated site tag is not deployed. The
retry approval is exercised. No further Analytics request, site retag/deploy,
`main` merge, schedule, or broader trust is authorized without separate owner
approval.
