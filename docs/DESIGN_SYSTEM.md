# DOCOGA DESIGN SYSTEM — Social & Brand Graphics
*Single source of truth. Every graphic follows this or it doesn't ship.*

## 1. Brand carriers
- **Wordmark:** "DOCOGA" set in Inter (typed text — never drawn as artwork).
- **Tagline:** "Your Documents. Our Priority." — set small, tracked, low-emphasis.
- **Official logo files** live in `brand/` → reserved for the website and email. **Owner direction (21 Sep 2026): the logo is NOT stamped on social posts.** It may return only on his explicit request.

## 2. Palette (flat — no gradients, no glows)
| Role | Hex |
|---|---|
| Canvas navy | `#061A33` |
| Watermark ink (1 step lighter) | `#0D2A4F` |
| Royal panel / color block | `#0F3D7C` |
| White | `#FFFFFF` |
| Muted body | `#8FA8C9` |
| Marginalia / faint | `#6080AA` |
| Royal blue accent | `#4A8CFF` |
| Yellow accent (one per slide) | `#FFC93C` |
| Red (strike-through only) | `#FF5A5F` |

## 3. Typography — Inter
- **Display:** Inter Black, extreme scale, auto-fit to grid (can never overflow).
- **Body:** Inter Light (heavy-vs-light contrast is the premium signal).
- **Labels/kickers:** Inter SemiBold, tracked +6–9px, small caps feel.
- **Engine:** RAQM layout = true kerning + ligatures.

## 4. Grid (1080×1080)
- Margins 84px · header band y 92–130 (kicker + stylized flag + corner label) · hairline y 158 · footer marginalia y 982.
- Craft moves: giant tonal glyph watermark bleeding off-canvas · color-blocked panels · outlined chips · offset-shadow CTA pill · red strike · yellow underline sweep.
- **Film grain:** σ≈2.2 luminance noise on every finished slide (matte print feel).
- **Never:** slide numbers, gradients, emoji, floating props, drop-shadow stickers.

## 5. IMAGE DISCIPLINE PROTOCOL v2 ⚠️ (owner-mandated)
*Owner grants full creative freedom — images, people, characters, anything — on one condition: "I must not detect AI by any means."*
1. **Style selection kills detection first.** People/characters appear as premium flat editorial illustration (mid-century modern), NOT photorealism — hands, skin and eyes are where AI gets caught; stylized geometric art is indistinguishable from human work.
2. **Every generated image passes the blend pipeline** (`tools/blend_image.py`): crop to grid region → **duotone into the brand ramp** (whatever palette the generator returned dies; the image exits speaking DocOga colors) → **feathered edge paste** (grows out of the canvas, never a sticker) → **shared film grain** over the final canvas so image and type have one texture.
3. **Prompt discipline:** limited palette enforced, "no text, no letters, no numbers" in every image prompt (AI gibberish text = instant detection).
4. **Type stays the hero.** Imagery is grid-anchored (framed region or panel), never floating, never full-bleed behind body copy.
5. **Photorealism rules (ultra-realistic imagery):** film-stock aesthetic is mandatory (35mm/faded grade + heavy grain + vignette + soft focus — clean photos are what get AI caught). Composition: faces distant / three-quarter / rear — never a studio stare or hero close-up of eyes or hands. No readable signage (AI gibberish text = instant giveaway). Integration: full-bleed magazine layouts with navy scrim/fade — never a pasted rectangle. All via `filmify()` + `scrim()` in `tools/blend_image.py`.
6. **Owner's eye is the final gate.** Any trace of AI → asset is dead, regenerated + re-treated instantly.

## 6. Asset library (`social/assets/`)
icon-receipt · icon-agreement · icon-seal · icon-house · icon-clock · icon-shield · icon-coin (+ preview-sheet.jpg). Transparent PNGs, 480px, blue-structure/white-detail/yellow-accent stroke system.

## 7. Pipeline
```
python3 tools/design_slides.py     → social/carousel-1..6.jpg + montage (kerned, grained, audited)
python3 tools/vector_kit.py        → icon set + preview sheet
```
Audit standard: rendered-pixel gutter check (no bright pixels in margins), auto-fit width assertions, montage for owner QC. Spelling is typed — cannot glitch.

## §6 MOTION SYSTEM (MotionStudio, tools/motionstudio.py)
Typography motion for Reels is a system, not effects. Six layers, in order:
1. **Content analysis** — purpose/audience/tone/peak/hierarchy declared per reel before any pixel.
2. **Typography solver** — every string measured in font metrics; REJECTED if wider than the 920px safe width (auto-resize); same-role display text HARMONIZED to one size; vertical rhythm chain enforces ≥18px gaps (RESPACE), clamped to safe band y300–1240.
3. **Motion grammar** — role→animation, one reason each: hook=odometer slam + 5% punch · emphasis=per-char cascade / strike slam + ring + shake · support=controlled whole-line rise (never fights the headline) · kicker=tracking-in 18→6 · proof=spin-settle cadence · cta=rise+persistent pulse (only element allowed to loop) · conclusion=stillness · transition=90ms flash + punch.
4. **Scheduler** — reading time = words/2.8wps + 0.5s buffer, capped per role (kicker 1.0s · support 1.25s · emphasis 1.3s). Every text beat guaranteed settle→pre-exit reading window; auto-shifts, retimes scenes, trims hold slack to hold the reel ≤15.6s.
5. **Render engine** — camera: punch-in per scene role, accelerate-out+fade 0.22s, 90ms flash cuts, ±6px impact shake on strikes. Filmic base: radial gradient + 72px dot grid + vignette. Encode: 1080×1920 30fps H.264 crf20 + encode-time grain (noise=alls=4:allf=t).
6. **Video QA engine** — audits rendered frames in 5 categories (typography/cut-off, animation/unscheduled-motion via frame-diff vs event registry, timing/pre-exit presence, composition/safe-zone, consistency/hierarchy). Auto-fixes and re-renders; refuses to encode if unfixable. A reel ships only at 0 violations.
Cadence elements (icon grid, name cycler) are exempt from reading windows — the rhythm IS the message; exemptions must carry a logged reason.

### §6.1 MOTIONSTUDIO v4 — After-Effects-grade layer (23 Sep)
- **Physics**: matter (text/icons/badges) moves on analytic damped springs (k=180 ζ=0.68; icons ζ=0.55); the camera moves on clean cubics. Never mix.
- **Motion blur**: ghost trails on every fast element (cascade chars, wordpop scale, odometer roll, strike slam edge, whip smear). 30fps + blur = film feel.
- **Impact language**: strike = 0.10s slam + horizontal edge blur + target recoil (scale bump ~4% decaying) + camera shake (content layer only) + expanding ring. Struck text then DIMS to muted — color carries the verdict.
- **Odometer**: rolling-counter ghost (previous value ghosted above) during count-up.
- **Kickers**: mask-reveal wipe + tracking-in (18→6).
- **CTA**: breathing scale (1.012 sinus) + pulse outline — only element allowed to loop.
- **Transitions (reasoned)**: flash = reset · whip (0.20s smear pan) = momentum into good news · dissolve (0.30s) = resolution into stillness. An element entering with a transition settles only when the transition completes (QA enforces).
- **Parallax**: bg zooms at 0.35× content zoom during camera moves — depth without decoration.
- **QA additions**: WCAG contrast table vs brightest bg region (≥3:1 large / 4.5:1 small), 24px legibility floor, line-break solver (2-line balanced split when min size can't fit), pairwise co-visible collision, transition-aware settle windows. Engine still refuses to encode on unfixable violations.

### §6.2 NARRATIVE SEMANTICS (user-caught, 23 Sep)
One device = one meaning, enforced by QA:
- **Strike = rejection of an EXTERNAL price only.** Struck text dims to muted (dead). NEVER strike our own price — it reads as "our price is also bad" and devalues the offer.
- **Own price = yellow underline sweep** (ownership, confidence; number stays alive/white).
- **FREE must say what it means:** end card reads "FREE. — to start. No signup. No card." (one sentence, two scales).
- QA consistency gate: `struck own price → violation → auto-unstrike`. Odometers declare `whose: theirs|ours`.