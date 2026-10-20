# Shorts motion grammar — camera + word-sync (MotionStudio v5)

*20 Oct 2026. Owner: "text motion graphics over the image as the voice-over speaks, smooth camera
movements, images that explain what the voice-over is saying per time, I want people to watch to
the end, quality beyond After Effects grade."*

Everything below is rendered by `tools/motionstudio.py` through the one bridge `tools/shorts_reel.py`
and shipped by the same lanes as before (YouTube Short, Facebook/Instagram Reel, Telegram, TikTok draft).
Nothing here is a new dependency the Short cannot live without.

## 1. What the viewer sees

| Second | What happens |
|---|---|
| 0.0 | The hook card (frame 0 = the designed cover). Photograph 1 behind it starts a slow **push**. |
| 0.3 | The narrator starts. The first **phrase card** snaps in under the headline — three or four words on a navy glass card, Inter Black. |
| each word | The word being said turns **brand yellow** with a 180 ms spring pop, **80 ms before** the ear hears it (reading is faster than listening). Words already said stay white; words to come wait at 55%. |
| each sentence | The **photograph changes** to one matching that sentence (`tools/shot_match.py`, Openverse CC0, brand duotone) — a 0.4 s cross-dissolve, and the new shot takes the next camera move in the cycle: push → pan-right → pull → tilt-up → pan-left. |
| each tip | `TIP 1 OF 4`, `TIP 2 OF 4`… above the green check; the fourth says `LAST TIP · 4 OF 4` — the viewer always knows how much is left, and that the payoff is next. |
| end | FREE. · docoga.com.ng · disclaimer. Unchanged. |

## 2. The camera (`camera_bg`, `camera_box`, `shot_frame`)

- A shot travels **10%** (`CAM_TRAVEL`) over its whole sentence — never faster. Push: 100% → 110%.
  Pull: the reverse. Pan/tilt: at 110%, edge to edge.
- The curve is **smoother-step** (`smoother`, Perlin's 6t⁵−15t⁴+10t³): zero velocity *and* zero
  acceleration at both ends. The camera never starts with a jolt or stops with a bump.
- Sampling is **sub-pixel**: `Image.transform(EXTENT)` on float coordinates (bilinear — at ≤10% rescale it is indistinguishable from bicubic and 2.5× faster). An integer crop steps
  one pixel at a time and judders at 30 fps; this does not. (`test_the_move_is_sub_pixel_smooth…`)
- Shots **cross-dissolve** over `XFADE` = 0.40 s; the outgoing shot keeps moving while it fades.
- The type does **not** ride the camera. Words stay pinned and sharp; only the world behind them moves.
- The scene's punch-in (hook) and exit zoom still apply on top, exactly as in v4.
- No photograph → the navy BASE, still. A wrong-sized picture is refused, not stretched.

## 3. The words (`tools/wordsync.py`)

- `words_for(clip, text, seconds)` → `[{d, t0, t1}]` per **display** word (punctuation kept —
  the card shows `₦50,000,`).
- Engines: **vosk** (the Deep-Dive's forced alignment; `tools/install_wordsync_deps.sh` puts the
  40 MB model under `/tmp/vosk` on the four render lanes) and **estimate** (letters + a pause after
  punctuation, digits slow; the clip's measured seconds shared out). The lane prints `WORDSYNC=vosk|estimate`.
- `chunk()` cuts phrases at the pauses (`, ; : — .`), balances anything over 4 words / 24 letters,
  and never ends a card on *the / your / and* when the next card can open with it.
- `shorts_sound.sync_words(clips)` runs after `fit_scenes` and before `caption_beats`; the caption
  beats then carry `words` in scene seconds. Without words (tests, a clip that failed to align)
  the caption is the plain timed sentence of v4 — nothing breaks.

## 4. Kinetic caption card (`r_kinetic`, `caption_chunks`, `kinetic_layout`)

- Placed under the scene's lowest type (≥ `CAPTION_Y` = 980), inside the grid-safe band
  (`SAFE.bottom` = 1240). One line; size 62 → 40 until the widest phrase fits.
- `WORD_LEAD` = 0.08 s, `WORD_POP` = 0.18 s. The lit word is *the latest word whose led time has
  come* — the only colour changes are at word times, so every change is a scheduled event.
- Yellow on a caption means one thing: this is the word the voice is on. (BRAND_STYLE §5.)

## 5. QA — it judges the type and forgives the camera

The v4 animation rule ("no more than 900 pixels may change outside a scheduled event") would
fail every frame of a moving photograph. v5 subtracts the expected background (`camera_bg` is one
function for render *and* QA): pixels that are pure background in both frames belong to the camera
and are ignored; the rest — the type — is judged. The judgment has hysteresis, because the soft
edge of a letter and the 20% of photograph that shows through a caption card drift by a few levels
as the camera moves: a pixel counts as moved only if it goes from plainly type (>40 levels from the
background) to plainly not (≤12), or changes by >40 while plainly type. Frame and expected
background are both box-reduced to half size before the comparison (the same way, so they still
match exactly), which keeps the per-frame pass at ~3 min for 2,000 frames. The typography check
(safe zone at settle) uses the same background at full size. Proven by
`test_qa_forgives_the_camera_and_still_catches_moving_type` (36 rendered frames; a kicker nudged
40 px on one frame is still caught), and by a full 2,000-frame build of the 20 Oct 2026 topic.

Events the engine registers: one `caption phrase` per card, one `caption word` per word (0.26 s
window), one `caption out`, and one `shot dissolve` per photograph change (the XFADE window — the
one moment the world behind the type changes faster than its soft edges can hide).

## 6. Cost and limits

- ₦0: Openverse is keyless, Vosk is Apache-2.0 and offline, Gemini stays on the free tier.
- Openverse pace stays 3.2 s per search; a 14-sentence Short asks ~14 times (≈45 s).
- A sentence whose picture is not found **keeps the shot before it** (the camera keeps running);
  a scene with no picture at all stays navy. `SHOTS_HITS` (scenes) and `SHOTS_TOTAL` (photographs)
  are the machine lines.
- Render cost: ~2,000 frames for a 66 s Short — ~0.18 s a frame to draw (scratch PNGs are written
  at `compress_level=1`; the default level alone cost 0.5 s a frame on a photograph), ~3 min of QA,
  ~10–12 min end to end on a 2-core runner, inside every lane's 30-minute timeout.

## 7. Files

`tools/wordsync.py` · `tools/install_wordsync_deps.sh` · `tools/motionstudio.py` (v5 block) ·
`tools/shorts_sound.py` (`sync_words`, `_sentence_times`) · `tools/shorts_reel.py` (`shot_plan`,
`attach_shots`, `tip_counter`) · tests `tools/tests/test_motion_v5.py` (25).
