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
| `qa.py` | Pre-push QA gate (8 checks) |
| `rebuild_ep1.py` | Unattended Episode-1 rebuild |
| `gemini_tts.py` | Gemini TTS (voiceover) |
| `motionstudio.py` | MotionStudio v4 |
| `dd2_shorts.py` | DD2 Shorts A/B/C |
| `generate_short_video.py` | Short-form video — no logo, film grain σ≈2.2, CTA bar (tests enforce) |
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
| `facebook_autopost.yml` | manual | `tools/fb_publish.py` |
| `instagram_autopost.yml` | manual | `tools/ig_publish.py` |

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
- **Google Analytics 4:** `G-GO8VZB3R28` (property: "inductive-seer-372707")
- **Microsoft Clarity:** `ym9fd3sxq5` (heatmaps, session recordings, rage clicks)

### Facebook Page:
- **Page ID:** `102466208923830`
- **Page Name:** `DocOga`
- **App ID:** `4401202890209558`
- **Status:** ✅ Active, posts already live
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
- `docs/dd1/` — 66 Years of Tenancy Law (48 slides)
- `docs/dd2/` — Caution Fee (47 beats)
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

## Last Session (LIVING — Update This Every Time)

### Current session — 10 Oct 2026 (Brevo domain AUTHENTICATED ✅)

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

**Still open before any release/resend:** sender identity check in Brevo → Senders
(`MAIL_FROM` default is `DocOga <noreply@docoga.com.ng>`; authenticated-domain
senders should verify automatically, but presence/status is unconfirmed);
best-effort Actions log cleanup for run `37890401771`; production Secret
bindings/current values; live Flutterwave webhook-hash match; private
checkout-vs-event recipient comparison; `RESEND_EMAIL_ENABLED` still unset;
workflow defects (DEXIT not propagated; manual dry_run still deploys) still
unfixed — do not dispatch. No deploy, no resend, no payment, no price/link change.

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

**The armed pipeline had no memory and no alarm. It now has both.**

Item 9 below says it plainly: from Friday 9 Oct the Shorts workflow renders and
uploads **public, twice a week, with nobody watching**. Reading it end to end
raised three questions the pipeline could not answer, and none of them was
fixable by a human on the day:

1. *If the run fails, who finds out?* Nobody. It was a red dot in a repo
   nobody opens.
2. *If a re-run, a GitHub retry or two dispatches land on the same day, what
   stops a duplicate Short?* Nothing. The rotation is deterministic and
   date-seeded, so the same topic would be rendered and uploaded again.
3. *What did we actually publish?* Nothing in the repo said. You had to open
   YouTube and read the channel.

**What shipped:**

- **`tools/youtube_ledger.py`** (new) — `logs/youtube_published.json`, a
  publish ledger: title, topic, video id, URL, privacy, WAT date, run id, size.
  Sub-commands `check` / `record` / `show`. stdlib only; a missing or corrupt
  ledger never blocks publishing (a damaged file is backed up as
  `.corrupt-<timestamp>`, not overwritten); newest first and capped at 200
  entries so a file we push to twice a week cannot grow forever.
- **Duplicate guard** in the workflow: `check` exits 3 inside a 7-day window.
  Six topics x two runs a week means a title returns after ~3 weeks — that
  repeat is intended and is *not* blocked; a same-day re-run is. A skipped run
  is **green** with a notice. `force=true` overrides, deliberately.
- **Preflight step** — the three secrets are checked in the first 30 seconds
  and the error names the missing one. Previously the failure appeared after a
  ten-minute render, from inside the uploader, without saying which secret.
- **Failure visibility** — a failed run opens an issue labelled
  `youtube-automation` (or comments on the one already open for that date)
  with the run link and a 4-step triage list: secrets → revoked token →
  YouTube audit → quota.
- **Owner-side privacy switch** — repository **variable** `YT_PRIVACY`
  (`unlisted`/`private`) changes every future run with no code change, for
  anyone who wants to watch the first ones land before they go public. An
  invalid value fails loudly rather than publishing at the wrong privacy.
  Manual dispatch also takes `privacy` and `force`.
- **Run summary** on every run — topic, title, privacy, result, link, size.
- `tools/yt_publish.py` now prints `VIDEO_ID=<id>`, and the workflow refuses to
  record a publish when that line is missing (an unverified ledger entry is
  worse than a red run). `scripts/youtube_short_daily.py` gained a `topic`
  output so the ledger reads as plain English.

**Verification — the workflow was run, not just read.** The token cannot
dispatch workflows (403), so the job was simulated on this machine: the real
step scripts from the YAML, through `bash -e`, with the same `GITHUB_OUTPUT`
plumbing, against a real git remote (the ledger commit is a real pull --rebase
+ push), a fake `gh`, and stubs only for ffmpeg and the YouTube network. The
logic under test was never stubbed. **Nine scenarios:**

| # | Scenario | Result |
|---|---|---|
| 1 | Happy path, empty ledger, secrets present | GREEN — published, recorded, ledger committed and pushed |
| 2 | Secrets missing | FAILED at preflight, nothing rendered, issue opened |
| 3 | Same title already in the ledger | GREEN, skipped with a notice, ledger untouched |
| 4 | Duplicate + `force=true` | GREEN, published anyway, ledger 2 entries |
| 5 | `YT_PRIVACY=unlisted` | `--privacy unlisted` reached the uploader |
| 6 | Typo in `YT_PRIVACY` | FAILED at settings, nothing published |
| 7 | Upload exits 0 but prints no `VIDEO_ID` | FAILED, **no** ledger entry recorded |
| 8 | Upload rejected by YouTube | FAILED, no ledger entry, issue opened |
| 9 | Second failure the same day | Commented on the open issue instead of opening a second |

**One real bug was caught by simulating it, and it would have shipped.** The
`force` path in the duplicate guard was written as
`if code == 3 && FORCE != "true" { skip } elif code != 0 { exit code }`, so
asking to force a re-publish took the `elif` and **exited 3 — failing the run
instead of publishing**. Reading the YAML does not show this; only running it
does. Fixed, and pinned by a regression test.

**Tests:** 48 pass (was 30). New `tools/tests/test_youtube_ledger.py` (17) and
`tools/tests/test_workflow_contract.py` (18), which statically checks every
`steps.<id>.outputs.<key>` reference in every workflow points at a real,
preceding step — an unknown id resolves to `""` at run time, which is the
silent failure mode this repo keeps getting bitten by. `PyYAML` added to the
CI test dependencies. `qa.py` 🏆 and `pre_push_verify.sh` ✅ green.

**What's next:** the Friday 18:00 WAT run is still the open question, but it is
now a *safe* one to let happen: a missing secret fails in 30 seconds with a
named cause and an issue, and a successful publish is recorded in the repo. See
item 9.

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
| 35 | 10 Oct 2026 | **Brevo domain `docoga.com.ng` authenticated** (owner clicks, guided one record at a time): TXT `@` brevo-code + CNAME `brevo1._domainkey` + CNAME `brevo2._domainkey` (both DNS only) + TXT `_dmarc` (`p=none`, Brevo-generated rua) added to the existing Cloudflare zone; both Worker `100::` records untouched; Brevo verify returned "Your domain has been authenticated". Sender status, secrets, webhook hash, log cleanup, recipient comparison and resend flag still open; no deploy/resend/payment. | session branch |
| 20 | 8 Oct 2026 | **Rule Zero enforced on the build: the verified law is now wired into the pages.** `tools/state_law_data.py` (6 jurisdictions, 20 open questions) drives `tools/gen_state_pages.py`. Three live factual errors fixed: (1) the hard-coded notice table printed "Half-yearly — 3 months" on all 48 pages when that is Lagos s.13(1)(d) and essentially nowhere else — the FCT Act, Cross River s.15 and Kwara s.17 have no half-yearly tier; (2) the four Edo pages said "Magistrates' Courts in Edo State" and "recovery-of-premises legislation" when s.4 of the Edict establishes **Rent Tribunals** and s.41(2) repealed the Recovery of Premises Law for residential accommodation; (3) every page now carries a Sources-and-confidence box with its tier and a "What we could not confirm" list. Rivers added at tier B on the strength of Cap. 109 s.7 (quit notice must expire on the **eve of the anniversary**, the opposite of Lagos s.13(4)) and Landlord & Tenant Law Cap. 75 s.75(1) (rent payable **in arrears**) | PR #11 |
| 19 | 8 Oct 2026 | **Research before building: measured the state pages and found they fail Google's doorway-page test — median 94.2% similarity between same-tool state pages, median 3 unique words each (worst pairs 99.6%).** So "expand 12 states to 37" was the wrong next move. Wrote `docs/STATE_TENANCY_RESEARCH.md`: verified statute names, sections and sources for 17 of 37 jurisdictions, tiered A-E, with everything unverified listed and three pending bills flagged as NOT law. Added `tools/audit_state_pages.py` to measure and later enforce (80% / 250 unique words / 500 body words) | PR #12 |
| 18 | 8 Oct 2026 | **Gave the armed Shorts pipeline a memory and an alarm:** publish ledger (`tools/youtube_ledger.py`) + duplicate guard, a secrets preflight that names what is missing, a `YT_PRIVACY` repo-variable switch, a run summary, and a labelled issue opened on any failed run. Verified by simulating all nine scenarios locally (the token cannot dispatch), which caught a real bug: `force=true` exited 3 and failed the run instead of publishing. 48 tests green | PR #11 |
| 17 | 8 Oct 2026 | Merged PR #9 to `main` (`72ec955`) — the pipeline plus the brand fix; PR #8 auto-merged. **This armed the YouTube scheduler: next public upload attempt Friday 9 Oct, 18:00 WAT, and the old empty-queue safety no longer applies** | `72ec955` |

---

## What's Next (Pending)

### Current revenue priority — 9 Oct 2026

1. **Authenticate the sender in Brevo; no second purchase.** Brevo's detailed log
   shows 0% delivered and an `Error` rejecting `noreply@docoga.com.ng` as an invalid
   sender. Authenticate `docoga.com.ng` in Brevo, or select a sender Brevo already
   verifies. In Brevo, copy the exact DNS records it supplies into Cloudflare DNS;
   do not guess record names/values. Wait for Brevo to mark the domain/sender
   authenticated. The event recipient has not been compared with checkout; do not
   share either address or any key. Brevo/Cloudflare access is unavailable to this
   session, so the owner must perform this account-side step.
2. **Enable and deliberately resend the existing pass only after authentication.**
   Local code adds `POST /resend-email` and a button on the success page. It targets
   only the email stored with the active purchased pass, does not issue a code or
   return one in the HTTP response, and throttles per pass (60 seconds, three per
   UTC day). It fails closed until the Cloudflare Worker runtime variable
   `RESEND_EMAIL_ENABLED` is exactly `true`. If choosing a different verified
   sender, configure `MAIL_FROM` to that exact identity. Do not use the button until
   sender authentication is complete.
3. **Honor deployment security gates.** Before any deploy, the owner must attempt
   the best-effort deletion of run `37890401771` and confirm the production Worker
   secrets are in place; the agent cannot independently verify either. Then use
   only the hardened, marker-gated workflow. Do not deploy this branch before both
   conditions are met. No additional payment is required or permitted for this
   email investigation.
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
7. **Read GA baseline** (`G-GO8VZB3R28`) in parallel; the agent cannot access it.
   Corrected pull list: `OWNER_CLICK_GUIDE.md` (Parallel). No success-page GA tag
   or verified-purchase event exists; do not report a conversion funnel as measurable.
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

3. **Confirm YouTube secrets exist** — `YT_REFRESH_TOKEN`, `YT_CLIENT_ID`,
   `YT_CLIENT_SECRET`. `tools/yt_publish.py:29` exits immediately if any are
   missing. This is the one cause of the two failed `YouTube Upload from
   Queue` runs that was never ruled out. The other cause is fixed: those runs
   used `head_sha 85097d7`, where the queue pointed at
   `social/reel-stakes-final.mp4` but that commit did not contain it.

   **Owner action, UI only:** repo → *Settings* → *Secrets and variables* →
   *Actions* → the three names must be listed. The agent's token cannot read
   them (`HTTP 403`), so this cannot be checked from a session.

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