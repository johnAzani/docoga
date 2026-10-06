# DocOga Session Context — THE SINGLE SOURCE OF TRUTH
*If you're reading this in a new session: start here. This is everything. Read this, then continue naturally.*

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

This ensures the next session feels like the same person continuing.

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
| `add_logo.py` | Logo compositor |
| `weekly_report.py` | Growth report assembler |
| `yt_suggest.py` | YouTube autocomplete research |
| `yt_upload_long.py` | Direct long-form YT upload |
| `qa.py` | Pre-push QA gate (8 checks) |
| `rebuild_ep1.py` | Unattended Episode-1 rebuild |
| `gemini_tts.py` | Gemini TTS (voiceover) |
| `motionstudio.py` | MotionStudio v4 |
| `dd2_shorts.py` | DD2 Shorts A/B/C |
| `generate_short_video.py` | Short-form video |
| `lead_magnets.py` | Lead magnets |
| `auto_caption.py` | Auto-caption |
| `reframe.py` | 9:16 → 1:1 reframe |
| `batch_render.py` | Batch render |

**52 tools total. All committed to main.**

---

## Documentation Suite (16 Documents)

All in `docs/`. All committed to `main`.

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

---

## GitHub Actions (Automation)

- `.github/workflows/telegram_autopost.yml` — Photo 9 AM + Video 6 PM
- Telegram credentials in GitHub Actions secrets (not locally accessible)
- User triggers workflows manually from GitHub

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

**Date:** 4 Oct 2026
**What was done:**
- Built complete content system (6 documents: CONTENT_SYSTEM, CONTENT_CALENDAR, CONTENT_ATOMIZATION, CONTENT_EMOTION_MAP, CONTENT_SCORING, SESSION_CONTEXT)
- Created STAKES hook reel (reel-stakes-caution.mp4, 14.4s, 5 scenes)
- Created professional SFX v2 (reel-stakes-final.mp4, 5-layer impacts, stereo)
- Created research-backed thumbnail (reel-stakes-thumb.jpg, 3 versions)
- Locked in status post template (status-oct3.jpg, asymmetric layout)
- Locked in brand style (docs/BRAND_STYLE.md)
- Locked in sound design (tools/make_sfx_v2.py)
- Added Microsoft Clarity (project `ym9fd3sxq5`) to site/index.html
- SESSION_CONTEXT.md made living document (always updated, session log)
- Built BUSINESS_DOMINANCE.md — 5-phase global expansion (Nigeria → Africa → World, $1B vision)
- 52 tools committed, 18 documents committed
- All pushed to main on johnAzani/docoga

**What's next:** Owner hasn't specified. Check conversation for latest request. If unclear, ask.

**Branch:** `arena/01a10172-docoga` (branched from main)
**Last commit:** `668ddfb` — Add Microsoft Clarity

---

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

---

## What's Next (Pending)

The owner hasn't specified. Check the conversation for the most recent request. If unclear, ask:

> "We've built the complete content system. What do you want to work on next? Options: (1) Create more content, (2) Set up automation, (3) Build new tools, (4) Something else?"

---

*This file is the contract between sessions. Update it at the end of EVERY session. If you're reading this, you have everything you need. Continue naturally.*