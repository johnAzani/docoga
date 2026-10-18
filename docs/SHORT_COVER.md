# The Short's cover — research and the design it produced (18 Oct 2026)

Owner, 18 Oct 2026: *"improve on the Shorts thumbnail design that no one can resist."*
This is the research, the conclusions that survived contact with the brand lock
(`docs/BRAND_STYLE.md`) and ₦0, and the design `tools/short_cover.py` draws from them.

## 1. Where a Short's cover is actually seen
| Surface | What is shown | Crop of the 1080×1920 cover |
|---|---|---|
| YouTube Shorts feed | the video, autoplaying — **no cover** | — |
| YouTube channel *Shorts* tab, search, suggested | the cover, 2:3 card | ≈150 px off top **and** bottom |
| YouTube *custom* Shorts thumbnail | Partner Program, desktop, rolling out — **not ours yet** | so frame 0 **is** the cover |
| TikTok profile grid, TikTok search | the cover, 3:4 → 1:1 | **y 420–1500 only**; caption's first line printed over the bottom ~270 px; view count bottom-left |
| TikTok inbox draft, Telegram, Facebook, Instagram | frame 0 (or `thumb_offset`) | full, with UI over the bottom third |

A 500-Short / 50-channel / ~1 M-impression test: Shorts reached through **search** with a
readable custom cover had **+85 % CTR**; Shorts reached through the **feed** showed **0 %**
difference. The cover is a search-and-grid instrument. Design for the grid.

**Rule 1 — the band.** Everything that matters sits in **y 460–1480**, full width
(grids never crop the sides). Nothing important in the bottom 270 px.

## 2. What moves click-through (the findings that agree with each other)
| Finding | Evidence | What we do |
|---|---|---|
| **Contrast is the strongest lever.** ≥ 7:1 → 6.5 % CTR vs 4.7 % below 4:1 (+38 %), in every niche | CTRpilot, 3,200 covers, 8 niches | navy on brand yellow (11:1), white on navy (16.9:1) |
| **Yellow + black is the top colour pair** (8.2 % avg) | NoteLM, 1,247 videos | the verdict is **navy text on yellow slabs** |
| **3–5 words, huge.** 7 → 4 words lifted CTR 34 %; 6+ words −31 %; dense text underperforms in browse | NoteLM; TubeAnalytics 2026 (≥10 k impressions) | the **consequence line alone** is the hero: "PAY TWICE.", "LOSE THE FLAT." |
| **One focal point** | vidIQ, 500 breakout thumbnails (89 % face *or* high contrast) | one slab stack; the photo is context, never a second subject |
| **Strong sentiment in the image** beats neutral — intensity matters more than direction; **numbers and question titles do not help** | Journal of Business Research 2024, 16,215 covers; 300 k-video title study (numbers −11 % views) | the STAKES hook's consequence *is* the sentiment; no "5 tips", no "?" |
| **Curiosity gap**: show the result, not the process | Loewenstein; Think Media 2026 | set-up (white, smaller) + verdict (yellow, huge); the *how* stays inside the video |
| **A face** lifts CTR 25–47 % | vidIQ, TubeBuddy | **not available**: no owner on camera, and the CC0 photo filter excludes faces (brand rule: no AI-detectable people). We take the next lever — contrast + a real photograph |
| **Photograph vs flat colour**: bright/saturated backgrounds +8–14 % | TubeAnalytics | the matched CC0 photo, treated at 0.80 (brighter than the video's 0.68) |
| **Text outline / plate** +23 % legibility lift | NoteLM | flat navy band behind the stack (alpha adapts to the photo's brightness) — no shadows, brand §1 |
| **Brand consistency** earns a small lift with returning viewers | TubeAnalytics | same kicker, same chip, Inter only, film grain σ 2.2 |
| **CTR noise**: under ~5,000 impressions a 4 % vs 6 % reading is inside the margin of error | thumblore 2026 | judge covers on the weekly `youtube_stats` numbers over weeks, not per video |

## 3. The design (tools/short_cover.py)
```
┌──────────────────────────────┐  y 0
│   (photo, navy scrim)        │
│                              │  y 460  ── band starts (TikTok 1:1 crop)
│      DOCOGA · TENANT TIPS    │  kicker, faint, tracked
│      PAY WITHOUT             │  set-up, white, Inter Black, ≤ hero/1.35
│      A RECEIPT.              │
│      ▌PAY▐                   │  verdict: navy on yellow slabs, Inter Black,
│      ▌TWICE.▐                │  as big as the words allow (118–250 px)
│   cash leaves no trail…      │  sub-line, muted, one line
│      (FREE · docoga.com.ng)  │  outlined chip, y ≈ 1384–1464
│                              │  y 1480 ── band ends; TikTok caption overlay below
└──────────────────────────────┘  y 1920
```
* **Hero** = the hook's consequence (the yellow cascade in the opening scene). One line when
  one line can be ≥ 150 px; otherwise two balanced lines, each on its own slab, the slabs set
  6 px apart as one stepped block (editorial "highlighted headline", not loose stickers).
* **Depth without a shadow**: a flat royal (`#0F3D7C`) block offset 16 px behind the slab
  stack — the brand's offset-pill idiom; layer stacking is what pro thumbnails use for depth,
  and the brand forbids soft shadows and gradients, so the offset is hard-edged and flat.
* **The one symbol**: a red ✗ badge after the set-up ("PAY THE WRONG AGENT. ✗") — the brand's
  rejection mark (BRAND_STYLE §5, "₦50,000 ✗"). A symbol is read before a word at tile size,
  and it is the only "directional element" on the piece (one is the recommended maximum).
* **No photograph?** The verdict's first letter as the giant tonal glyph (`#0D2A4F` on navy),
  bleeding off the bottom-right — BRAND_STYLE §4's depth device, so a navy cover is never flat.
* **Set-up** = the white cascade, never larger than hero ÷ 1.35, ≤ 2 lines.
* **Yellow** appears once (the slabs) — BRAND_STYLE §1 "one per slide". Flat, no shadow, no tilt.
* **Background** = the opening scene's matched photograph (`_bg_raw`, treated at 0.80) or navy.
  A flat navy band (alpha 92 / 140 / 188 by the photo's brightness) sits behind the stack.
* **Chip** = "FREE · docoga.com.ng": the brand's outlined CTA pill, the one promise a Nigerian
  tenant stops for, inside the 1:1 crop and above the caption overlay.
* **Frame 0** of the master is this cover (`motionstudio.poster_frame` honours
  `reel["cover_fn"]`), so TikTok, Telegram, Facebook and Instagram (`thumb_offset=0`) show it;
  `<master>.cover.jpg` is the YouTube custom-thumbnail file (`tools/yt_thumbnail.py`).

### Second pass (same day): the world-class checklist
Pro thumbnail designers' published rules, checked one by one against the piece:
| Rule | Status |
|---|---|
| One focal point; 2–3 elements max | ✅ slab stack (1), set-up + badge (2), chip (3) |
| Primary text 2–3× the secondary | ✅ hero ≥ 1.35× set-up by solver; typically 1.6× |
| ≤ 12 characters / 1–3 words on the hero | ✅ "PAY TWICE.", "LOSE THE FLAT." |
| Text adds information the title lacks | ✅ the sub-line ("verify before money moves") |
| Layer stacking for depth | ✅ photo → navy band → royal offset block → yellow slabs → navy type |
| Heavy sans ≥ weight 700, solid block behind text | ✅ Inter Black on yellow; white on the navy band |
| 60-30-10 colour split | ✅ navy ≈ 60, yellow ≈ 30, white + red ≈ 10 |
| Negative tracking on display type | ✗ skipped on purpose: per-glyph drawing would lose Inter's kerning pairs |
| One directional symbol max | ✅ the red ✗ |
| Test at 1/4 size / squint test | ✅ automated: `test_the_squint_test_at_grid_tile_size` (200 px 1:1 tile; slabs ≥ 8 % of it, cap height ≥ 20 px) |
| Rule-of-thirds subject placement | ✗ centred on purpose: the 1:1 grid crop punishes anything off-centre vertically |

## 4. Measuring it
YouTube Studio reports thumbnail impressions and CTR for Shorts since 2026; the Monday
`youtube_stats` lane pulls the channel numbers. Read the Shorts-tab/search CTR across weeks
(≥ 5,000 impressions before believing a difference). TikTok: profile views → follows ratio.

## 5. What is deliberately not done
* No faces, no AI people, no stock "shocked" expression — brand rule one ("I must not detect
  AI by any means"), and the CC0 filter excludes people.
* No arrows, circles, emoji, red X stickers, drop shadows, gradients, tilted tape — brand §4.
* No numbers-for-numbers'-sake ("5 TIPS"), no question marks — the evidence is against both.
* No per-platform variants: one cover, designed for the tightest crop, works on all of them.

Sources read 18 Oct 2026: vidIQ thumbnail design tips & Shorts custom thumbnails; TubeAnalytics
"Thumbnail CTR Patterns Study 2026"; CTRpilot colour study (3,200 covers); NoteLM "15 thumbnail
tips (2026 data)"; thumblore "What is a good CTR" (noise table); shortgenius Shorts thumbnail
placement test; BYSO / thumbcrafted / fixphotolab / socialrails TikTok cover crop and overlay
measurements; Cui, Chung, Peng & Wang, *Journal of Business Research* 2024 (16,215 covers).
