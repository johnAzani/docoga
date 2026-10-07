# DocOga Growth Journal
*The unfiltered record of building a Nigerian legal-tech company from zero.*

> This document is the living memory of DocOga. Every milestone, every setback,
> every lesson — recorded honestly. Updated as the story unfolds. The goal is
> that anyone reading this 5 years from now can trace exactly how ₦0 became
> something real.

---

## Chapter 0 — The Spark (18 Sep 2026)

**Location:** Abuja, Nigeria
**Status:** Idea + research
**Money spent:** ₦0

John Azani looked at the Nigerian rental market and saw what 15 million Lagos renters see every year: landlords charging ₦50,000–₦180,000 for a tenancy agreement that a machine could generate in 2 minutes. The research was clear:

- Lawyers charge 5–10% of annual rent for documents
- Wonder.legal and LawDepot charge ₦7,500–₦8,500 per document
- 70% of Lagos tenants face deposit disputes (LASRERA)
- Only 10–15% of tenancy agreements come from real lawyers — the market already runs on templates

**The decision:** Build DocOga — a Nigeria-focused document engine. Free watermarked versions win search traffic. The ₦2,000 Oga Pass (30 days, unlimited) delivers clean documents. Unit economics: ~100% gross margin. Break-even: ONE pass covers the domain name.

**Key research findings:**
- 14.9M housing deficit + 15.2M substandard homes (Federal Ministry of Housing)
- Lagos: 3.4M-unit deficit, 15M+ renters, rents rising ~18%/year
- Nigeria e-payments: ₦1.08 quadrillion in 2024 (+80% YoY)
- Capturing 0.1% of Lagos renters = 3,000 passes = ₦6M/yr

**Moat ladder defined:**
1. Speed & niche depth (now)
2. SEO authority (months 1–9)
3. Accounts + data lock-in (v2)
4. Two-sided network (v3)
5. Rent collection rails (v4)

---

## Chapter 1 — The Build (18–21 Sep 2026)

**Days:** 3
**Money spent:** ~₦1,500 (domain)
**Status:** Product shipped, payment rails operational

### What happened:
- Built the entire document engine as a single-file static app (zero server cost)
- 4 tools at launch: Tenancy Agreement, Notice to Quit, Rent Receipt, Invoice
- Mobile-first UX tuned for Nigerian phones
- Privacy-first: data stays on device, zero signup
- Flutterwave Individual KYC approved 21 Sep 2026
- **First sale collected: ₦2,000** — full money loop closed (sale → bank withdrawal)

### Honest scorecard:
| Factor | Status |
|--------|--------|
| Product | ✅ Built |
| Payment | ✅ Operational |
| Distribution | ❌ 0 visitors |
| Conversion | ✅ Designed |

**The rule learned:** the code was 20% of the work. The market is the other 80%.

---

## Chapter 2 — The Machine Awakens (22–25 Sep 2026)

**Days:** 4
**Status:** AI content engine operational
**Platforms live:** Instagram, Telegram, YouTube, Facebook

### What happened:
- Instagram API connected — 60-day long-lived token, full publish permissions
- Telegram channel launched (@docogadaily) — daily tips, ₦0 forever
- YouTube channel live — resumable uploads via Data API
- Facebook Page live (facebook.com/docoga.com.ng) — vanity username taken 26 Sep
- Comments machine operational — same-day replies
- Feed posts + reels via API — full automation
- **Mandate from the boss:** NO manual posting, NO screenshotting — the machine runs everything

### Content shipped:
- 5 story frames (rs-1..rs-5) — first organic content
- Feed post-1 (launch post)
- Feed post-2 (Rent Day scenario)
- Feed post-3 (5 Documents carousel)
- Reel-1 ("THE PRICE" — 15s kinetic typography)
- Reel-2 ("EVERY DOCUMENT" — 13s)
- Reel-3 ("CAUTION FEE" — 38s voiceover)
- DocOga Journal Issue 01

### Key insight:
> Stories drive reel views — 25% of views came from story support frames. Never skip story support around a reel.

---

## Chapter 3 — The Content Factory (25–28 Sep 2026)

**Days:** 4
**Tools built:** 30+
**Status:** Full production studio operational

### What happened:
- Built the entire content production pipeline — 30+ tools covering:
  - Design system (editorial carousel, blend pipeline, vector icons)
  - Video production (Deep-Dive long-form, DD2 Shorts, kinetic-typography reels)
  - Voice pipeline (Gemini TTS, ASR word-sync, preamble trimming, audio mux)
  - SEO (24 state pages, deep research, YouTube autocomplete)
  - Publishing (Telegram autopost, YouTube upload, Instagram API)
  - Analytics (meter pull, weekly report, meta lab)
  - QA (pre-push gate, post-deploy verification)
- Deep-Dive #1 ("Notice to Quit: The Legal Timeline") — 9 scenes, 10+ minutes
- DD2 ("Caution Fee: The Refund War") — 9 scenes, 47 beats
- DD3 ("The Tenancy Agreement: 8 Clauses") — 9 scenes, 49 beats
- DD4 ("The Rent Receipt") — 9 scenes, 43 beats
- Reel-4 ("66 YEARS. 6 RIGHTS.") — Independence Day special, ASR word-synced
- Hook Lab established — 7 archetypes, scoring formula, first entries
- Growth Engine Operating Charter written
- Design System documented
- QA Protocol born (from the 19 Sep incident)

### The 19 Sep Incident (never forget):
A single stripped `//` comment in WORKER_URL config → SyntaxError → every button on the live site dead for 20 minutes. Caught by the boss testing on phone, not by any automated check.

**Prevention now in place:** qa.py (full JS parse) + verify_live.py (parse LIVE script) + ship.sh pipeline + pre-push hook.

### Key lesson:
> Every error becomes a permanent rule. The QA Protocol was born from a one-character bug.

---

## Chapter 4 — Independence Day (28 Sep – 1 Oct 2026)

**Days:** 4
**Status:** First cultural moment leveraged
**Event:** Nigeria @66 Independence Day

### What happened:
- Built "NIGERIA AT 66" carousel (5 slides, tenant rights timeline 1960→today)
- Reel-4 "66 YEARS. 6 RIGHTS." queued for 30 Sep
- Teaser story frame queued for 29 Sep
- Independence angle: "your rights since 1960" story frames
- WhatsApp forward pack: "10 Rights Every Nigerian Tenant Has"
- All content funnels to tenant-rights SEO pillar

### Events Law established:
1. Events are seasoning, not the meal
2. Never partisan, never political
3. Timing: 1–3 days BEFORE the event
4. If event clashes with niche moment, niche wins
5. Green-white-green flag accents allowed

---

## Chapter 5 — The Documentation (3 Oct 2026)

**Days:** 1 (this session)
**Status:** 51 artifacts committed
**Branch:** arena/01a10172-docoga

### What happened:
- Saved and committed the entire tool suite to the repository
- 51 tools + documentation pushed to main
- Every tool from the full production pipeline now lives in the repo
- Documentation suite complete:
  - Business Plan (market data, competitor pricing, revenue scenarios)
  - Growth Engine Charter (North Star, KPIs, calendar, Hook Lab)
  - Design System (palette, type, grid, image discipline, motion system)
  - Hook Ledger (7 archetypes, scoring, entries, rotation)
  - QA Protocol (non-negotiable rules, born from incident)

### The full pipeline now in code:
```
Research (yt_suggest, deep_research, meta_lab)
  → Script (dd1/2/3/4-script.txt)
  → TTS (gemini_tts, tts_batch, tts_harvest)
  → ASR Trim (trim_dd1)
  → Alignment (dd2/3/4_align, align_r4)
  → Video (make_longform*, dd2_shorts, make_reels, motionstudio)
  → Audio (mux_dd2/3)
  → Design (design_slides, blend_image, vector_kit, make_*_post)
  → QA (audit_reels, qa.py)
  → Upload (yt_upload_long)
  → Publish (post_telegram, post_telegram_video, IG API)
  → Measure (meter_pull, weekly_report)
  → Verify (verify_live)
```

---

## The Numbers (updated as data arrives)

| Date | Followers | Reel Views | Sales | Notes |
|------|-----------|------------|-------|-------|
| 18 Sep | 0 | 0 | ₦0 | Idea stage |
| 21 Sep | 0 | 0 | ₦2,000 | First sale (Flutterwave) |
| 22 Sep | ~5 | 30 | ₦2,000 | First organic post |
| 24 Sep | ~10 | 41 | ₦2,000 | First reels live |
| 25 Sep | ~15 | 47 | ₦2,000 | Autopost operational |
| 26 Sep | ~20 | 47 | ₦2,000 | Facebook live |
| 27 Sep | ~25 | 47 | ₦2,000 | First carousel, Threads live |
| 28 Sep | — | — | ₦2,000 | Deep-Dive #1 premiere |
| 1 Oct | — | — | — | Independence Day drop |
| 2 Oct | 30 target | 2,000 target | — | 7-day checkpoint |
| 9 Oct | 100 target | 8,000 target | — | 14-day checkpoint |
| 25 Oct | 300 target | 25,000 target | ₦6,000 target | 30-day checkpoint |

---

## The North Star

> Every naira of rent paid in Nigeria passes through a DocOga document.

**Phase 0 (HERE):** 1,000 paying Nigerians, consistent weekly revenue
**Phase 1 (6–18mo):** Landlord SaaS live, ₦50–100M/yr
**Phase 2 (yr 2–3):** ₦1B+/yr volume, seed round
**Phase 3 (yr 3–5):** Series A/B, 4+ countries
**Phase 4 (yr 5–10):** Emerging markets beyond Africa

---

## Lessons Learned (running list)

1. **The code is 20%. The market is 80%.** — Distribution decides everything.
2. **One character can kill a site.** — QA is not optional.
3. **Stories drive reel views.** — Never skip story support.
4. **Organic growth compounds nonlinearly.** — Nothing for days, then a curve-bend.
5. **Every error becomes a permanent rule.** — Document it, automate the check.
6. **The boss is never the guinea pig.** — Research first, verify, then guide.
7. **AI is a feature, not a rival.** — Sell workflow + trust, never raw capability.
8. **₦0 is a feature, not a bug.** — Zero fixed costs = unlimited runway.
9. **The real competitor is informality.** — No document at all, or a friend's PDF.
10. **Daily income is earned through distribution.** — Ship daily until the catch.

---

## What's Next

- [ ] First 10 tagged reels → rank Hook Lab archetypes
- [ ] First 50 followers → unlock collab research
- [ ] First ₦10K revenue → CAC Business Name registration
- [ ] 3,000 monthly visitors → start v2 planning
- [ ] First ₦50K/month → Supabase backend, automated checkout
- [ ] Keep shipping. Daily.

---

*This journal is updated as the story unfolds. Every chapter is written in real time.*
*The honest truth: most startups fail. The ones that don't ship every single day.*
*We ship.*