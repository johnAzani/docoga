# DOCOGA BRAND STYLE — LOCKED IN
*Owner-confirmed. Every piece of content follows this or it doesn't ship.*
*Locked: 3 Oct 2026 · Updated only on explicit owner direction.*

---

## THE ONE RULE
**"I must not detect AI by any means."** — Owner, 21 Sep 2026. This governs everything below.

---

## 1. COLORS — Flat Only (no gradients, no glows, no shadows)

| Role | Hex | Where |
|------|-----|-------|
| Canvas / background | `#061A33` (navy) | Every slide, every frame, every video |
| Watermark / depth | `#0D2A4F` | Tonals, glyph watermarks bleeding off-canvas |
| Royal panel | `#0F3D7C` | Color blocks, frames, outlined chips |
| Text (primary) | `#FFFFFF` (white) | Headlines, display type, key numbers |
| Text (body) | `#8FA8C9` (muted) | Sub-lines, descriptions, supporting copy |
| Text (faint) | `#6080AA` | Kickers, marginalia, labels |
| Accent (blue) | `#4A8CFF` | Links, CTAs, progress bars, borders |
| Accent (yellow) | `#FFC93C` | One per slide — underline sweep, price highlight, badges |
| Accent (red) | `#FF5A5F` | Strike-through ONLY — never for anything else |
| Nigerian flag green | `#008751` | Event frames only (Independence, Democracy Day) |

**LOCKED:** These 10 colors. No others. No mixing. No "close enough."

---

## 2. TYPOGRAPHY — Inter Only

| Role | Weight | Scale | Tracking | Usage |
|------|--------|-------|----------|-------|
| Display (hero) | **Inter Black** | 96–190px | 0 | One massive word per beat. Auto-fit to grid. |
| Body (copy) | **Inter Light** | 42–58px | 0 | Sub-lines, descriptions. Heavy+light = premium. |
| Labels / kickers | **Inter SemiBold** | 22–36px | +6–9px | "DOCOGA · DEEP-DIVE", corner labels, footer |
| Captions | **Inter Medium** | 40px | 0 | Video subtitles, phrase-grouped |

**LOCKED RULES:**
- Inter is the ONLY font. No substitutes.
- RAQM layout engine = true kerning + ligatures.
- Auto-fit: display text NEVER overflows. Algorithm shrinks until it fits.
- Heavy-vs-light contrast is the premium signal — never use Black for body.

---

## 3. GRID — 1080×1080 (feed) / 1080×1350 (4:5) / 1080×1920 (stories/reels)

### Feed (1080×1080)
- Margins: **84px**
- Header band: y 92–130 (kicker + stylized flag + corner label)
- Hairline: y 158
- Footer marginalia: y 982
- Safe content zone: 84px → 996px horizontal

### Portrait (1080×1350, 4:5)
- Same margins, same header system
- Extra 270px vertical for extended copy

### Vertical (1080×1920, 9:16 stories/reels)
- Safe zones: top 270px, bottom 660px, sides 65px
- Content band: y 300–1240

---

## 4. CRAFT MOVES (the DocOga visual language)

### Always present:
- 🎞️ **Film grain** — σ≈2.2 luminance noise on EVERY finished piece (matte print feel)
- 🔤 **Giant tonal glyph** — watermark bleeding off-canvas (subtle, depth)
- 📐 **Color-blocked panels** — outlined chips, offset-shadow CTA pill
- 🔴 **Red strike** — on EXTERNAL prices only (lawyer's ₦50K)
- 🟡 **Yellow underline sweep** — on OUR price (₦2,000) or key claim

### Never:
- ❌ Slide numbers
- ❌ Gradients
- ❌ Emoji
- ❌ Floating props
- ❌ Drop-shadow stickers
- ❌ Logo stamped on social posts (owner direction, 21 Sep 2026)

---

## 5. NARRATIVE DEVICE RULES (one device = one meaning)

| Device | Meaning | Rule |
|--------|---------|------|
| **Red strike-through** | Rejection of EXTERNAL price | Struck text dims to muted (dead). NEVER strike our own price. |
| **Yellow underline sweep** | Ownership / confidence | Our price stays alive/white. The number is ALIVE. |
| **Green check badge** | Validation | "2 minutes ✓", "works on phone ✓" |
| **Red X badge** | Rejection | "₦50,000 ✗ TOO MUCH" |
| **Odometer count-up** | Price shock | Numbers roll from 0 to target. Whose: theirs or ours declared. |
| **FREE.** | What it means | End card: "FREE. — to start. No signup. No card." Two scales, one sentence. |

**LOCKED:** Strike own price = violation = auto-unstrike. QA enforces.

---

## 6. IMAGE DISCIPLINE (the AI detection kill chain)

### Style 1: Editorial Illustration (preferred)
- Premium flat illustration (mid-century modern)
- Stylized geometric art — NOT photorealism
- Hands, skin, eyes are where AI gets caught → avoid them
- **Every image passes the blend pipeline:**
  1. Crop to grid region
  2. Duotone into brand ramp (generator palette dies)
  3. Feathered edge paste (grows from canvas, never a sticker)
  4. Shared film grain (image + type = one texture)

### Style 2: Photorealism (when needed)
- Film-stock aesthetic MANDATORY (35mm/faded grade + heavy grain + vignette + soft focus)
- Faces: distant / three-quarter / rear — NEVER studio stare
- NEVER: hero close-up of eyes or hands
- NEVER: readable signage (AI gibberish text = instant giveaway)
- Integration: full-bleed magazine layouts with navy scrim/fade
- All via `filmify()` + `scrim()` in `tools/blend_image.py`

### Prompt discipline (every image prompt):
- ✅ "limited palette, no text, no letters, no numbers"
- ❌ Never include text in image prompts

### Owner's eye is the final gate.
Any trace of AI → asset is dead. Regenerated + re-treated instantly.

---

## 7. VOICE & TONE

### Written copy:
- **Direct.** Short sentences. No filler.
- **Authoritative.** Cite the law. Name the section number.
- **Nigerian.** Not pidgin (that's for TikTok), but Nigerian English rhythm.
- **Empowering.** "You have the right." Not "you should know."
- **Zero jargon.** If a tenant can't understand it in 2 seconds, rewrite it.

### Hook rules (first 1.3s of Reels / 2.1s of Shorts):
- 7 archetypes: STAT · QUESTION · CLAIM · STAKES · CURIOSITY · HOWTO · STORY
- One hook per asset. Tagged in HOOK-LEDGER.md.
- Target: VVSA 70–90% (viewers watched / saw)
- Thumbnail must promise exactly what the hook delivers

### TTS voice:
- **Gemini Orus** — natural Nigerian English accent
- Instruction: "Narrate this in a natural Nigerian English accent, like a confident Lagos radio presenter"
- Every chunk ASR-verified clean (no preamble leaks)

---

## 8. CONTENT FORMATS

### Feed Carousel (1080×1350, 4:5)
- 5–8 slides
- Save-worthy checklist format (highest saves in Nigerian market)
- Header: kicker + flag + corner label
- Footer: CTA pill + docoga.com.ng
- Film grain on every slide
- Tools: `design_slides.py`, `gen_feed_5docs.py`

### Feed Single (1080×1350, 4:5)
- Type hero + blended illustration
- Header system + footer CTA
- Film grain shared over image + type
- Tools: `make_scenario_post.py`, `make_journal_post.py`

### Reels (1080×1920, 30fps)
- Kinetic typography — 100% code-rendered
- Camera: punch-in 4.5% / accelerate-out + fade
- 90ms flash cuts between scenes
- Impact shake on key beats
- Odometer count-ups, per-char cascades, tracked kickers
- Tools: `make_reels.py`, `motionstudio.py`

### Deep-Dive Videos (1920×1080, 16:9)
- 9 scenes per episode, word-synced to ASR
- Left gradient + navy canvas + film grain
- Rows layer for numbered lists
- Progress bar at bottom
- End card: DOCOGA + docoga.com.ng
- Tools: `make_longform*.py`

### Shorts (1080×1920, vertical)
- Cut from Deep-Dive episodes
- Kinetic typography, ASR word-sync
- Embedded cover card (2.6s PAD)
- Loudnorm -16 LUFS
- Tools: `dd2_shorts.py`

### Stories (1080×1920)
- 2–3 fresh frames/day
- Always one funnel frame ("FREE documents — link in bio")
- Tools: `make_reel_story.py`, `design_d6.py`

### WhatsApp Forward (1080×1350)
- One clean forwardable image
- Numbered list, navy/white/yellow
- CTA to docoga.com.ng
- Tool: `whatsapp_forward.py`

---

## 9. THE AUDIT CHECKLIST (every piece, no exceptions)

- [ ] Colors: only from the locked palette
- [ ] Font: Inter only, correct weights
- [ ] Film grain: present on finished piece
- [ ] Strike-through: EXTERNAL prices only
- [ ] Own price: yellow underline, never struck
- [ ] FREE: "to start. No signup. No card."
- [ ] Logo: NOT on social posts
- [ ] AI detection: zero trace
- [ ] Spelling: typed text, cannot glitch
- [ ] Grid: margins respected, safe zones clear
- [ ] CTA: docoga.com.ng present
- [ ] Frame Ledger: not live in last 30 days

---

## 10. WHAT CHANGES (and what doesn't)

**Never changes without explicit owner direction:**
- Palette (10 colors)
- Typography (Inter only)
- Grid (84px margins)
- Film grain (σ≈2.2)
- Narrative device rules (strike = external only)
- Logo rule (not on social posts)
- AI detection rule (zero trace)

**Evolves with data:**
- Hook archetypes (ranked after 10 tagged reels)
- Content calendar (re-cut weekly from insights)
- Winning formats (replicated from 50%+ non-follower reach)

---

*This document is the contract between the brand and every piece of content it produces.*
*If it's not in here, it doesn't exist.*
*If it contradicts this, it doesn't ship.*