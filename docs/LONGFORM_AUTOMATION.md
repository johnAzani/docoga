# Long-form (Deep-Dive) automation — owner runbook

**Status (14 Oct 2026):** built, tested end-to-end with a synthetic voice in the sandbox; the owner added
`GEMINI_API_KEY`. The nightly tick now produces DD2 by itself; a manual run gets it sooner.

The owner said: *"I don't want to narrate it myself."* So the voice is Google's Gemini TTS
(free tier), the word-sync is Vosk (free, runs on the GitHub runner), the pictures are
committed stills under `episodes/assets/`, and the cost is **₦0**.

---

## What the lane does

```
episodes/dd2/script.txt  ──►  Gemini TTS (9 chunks)  ──►  Vosk word timings
episodes/dd2/episode.json ──►  9 scenes rendered in parallel (MotionStudio palette + Inter)
                          ──►  master (−16 LUFS, 1080p)  ──►  cover  ──►  QA
                          ──►  YouTube upload (unlisted by default) + thumbnail + ledger
```

Every intermediate is **banked** on a GitHub Release called `deepdive-<episode>`
(Releases tab → `deepdive-dd2`): the voice chunks, the word timings, the finished MP4 and the
cover. A re-run never pays twice, and nothing lives only on a runner. (That is how the voice of
DD1–DD4 was lost in September — it existed on one laptop.)

| Thing | Where |
|---|---|
| Engine (one file, all stages) | `tools/deepdive.py` |
| Workflow | `.github/workflows/deepdive.yml` |
| Episode inputs | `episodes/<id>/script.txt`, `episodes/<id>/episode.json` |
| Plates (16:9 stills, duotoned at render time) | `episodes/assets/*.jpg` (+ `aliases.json` for stand-ins) |
| Bank | GitHub Release `deepdive-<id>` |
| Long-form ledger | `logs/youtube_longform.json` |
| Thumbnail setter | `tools/yt_thumbnail.py` |
| Tests | `tools/tests/test_deepdive.py` (no rendering, no network) |

---

## One-time: add the Gemini key (phone, ~3 minutes)

1. Open **aistudio.google.com** in the browser, sign in with the DocOga Google account.
2. Tap the **☰ menu** (top-left) → **Get API key** → **Create API key** → choose
   *Create API key in new project* (or any project) → **Copy** the key.
3. Open **github.com/johnAzani/docoga** → tap **⋯** / the **Settings** tab (you may need to tap
   *Desktop site* in the browser menu to see it) → **Secrets and variables** → **Actions** →
   **New repository secret**.
4. Name: `GEMINI_API_KEY` — Secret: paste the key → **Add secret**.

That is the only new secret. The YouTube secrets the Shorts lane already uses
(`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`) are reused as they are.

> The free tier gives roughly 10 TTS requests a day. One episode is 9 chunks, so the voice of
> one episode usually fits in one day. If the bucket empties mid-run the job ends **green** with
> *"N/9 banked"* and the 03:00 WAT tick continues the next day. Nothing to press.

---

## The voice — 🔒 locked

Owner, 14 Oct 2026: *"Lock that voice in. On no occasion shall it change — not even by one
sentence or word, not even by mistake."*

**Gemini Orus**, instruction byte for byte:
`Narrate this in a natural Nigerian English accent, like a confident Lagos radio presenter:`

It is defined once, in `tools/deepdive.py` (`LOCKED_VOICE_*`), fingerprinted
(`697e3233c630…`), and checked before every TTS request. An episode file that says anything
different is refused; so is any request that reaches the API with another voice. The unit
tests and `tools/qa.py` pin the exact bytes, so a change cannot merge. Adding DD3, DD4 or
any later episode needs no voice setting at all — they inherit it.

## Free plan, forever — how the lane stays inside it

- **Hard cap:** the engine makes at most 12 Gemini requests per run (`--max-requests 12`),
  whatever plan the key is on. One episode is 9. There is no path that spends more.
- **Quota = pause, not failure.** When Google answers "quota", the chunks already minted are
  banked on the release, the run ends **green** with *"N/9 banked"*, and nothing is lost.
- **Nightly tick, 03:00 WAT.** The workflow also runs on a schedule. It reads
  `episodes/queue.json`, takes the first episode whose title is not yet in
  `logs/youtube_longform.json`, and continues from whatever the bank holds — more voice
  chunks, or straight to render/publish if the voice is complete. You press nothing twice.
- **Nothing banked is redone.** A banked master skips voice and render and goes straight
  to publish; a complete voice skips TTS entirely (zero requests).
- Google can't move a project onto a paid plan by itself — billing is something you would
  have to switch on in Cloud Console. Don't, and the key stays free.

## Music and sound effects — ₦0, owned, precise

No downloaded "free" tracks: a CC0 file can be re-licensed, its host can vanish, and a
Content ID claim on the channel costs a morning. The kit is **synthesized** by
`tools/soundkit.py` from sine waves and shaped noise, with a fixed seed, so it is ours
outright and identical on every render.

| Sound | When | Level vs. the voice |
|---|---|---|
| Bed — A-minor pad voiced A3–A4, plucked arpeggio on every beat (72 BPM), soft bass + sub pulse underneath, a faint shimmer on top | whole episode, fades out over the last 4 s | **16 dB(A) under speech, 8 dB(A) under in the gaps** — side-chain ducked from the narrator's own level, measured A-weighted (as ears hear it) |
| Riser (1.2 s) + hit | into / on every section title | −14 / −9 dB vs the voice peak |
| Whoosh (250 ms) | every other beat change | −12 dB |
| Tick | each numbered row as it appears | −16 dB |
| Stinger (A-major swell) | the end card | −9 dB |

> **Run #1 lesson (14 Oct 2026).** The first bed sat 27 dB under the voice by raw power and was
> voiced at 55–165 Hz. Phone speakers don't reproduce much below ~200 Hz, and raw power over-counts
> low notes — the gauge said "healthy", the owner heard nothing. Everything is now measured
> A-weighted and QA fails a master whose bed is **either** < 11 dB(A) under speech (masking) **or**
> > 22 dB(A) under (inaudible).

- The cue sheet is derived from the **same timings the renderer uses** (`scene_timing`), so a
  whoosh lands on the frame the headline appears — millisecond precision, no drift.
  See it: `python3 tools/deepdive.py dd2 cues` (≈70 cues for DD2). It is also banked as
  `dd2-cues.json` on the release.
- The plan is written in `episodes/<id>/episode.json` → `audio` (levels, BPM, seed, `bed: false`
  to go voice-only).
- QA refuses a master whose bed is less than 11 dB(A) under the voice (masking), more than
  22 dB(A) under (inaudible), or that clips. The mix report (`dd2-mix_report.json`) records the
  measured, A-weighted separation.
- Audition the kit by ear: `python3 -c "import sys;sys.path.insert(0,'tools');import soundkit;print(soundkit.export_kit('ffmpeg','/tmp/kit'))"`.

## Produce and publish an episode (phone)

1. **github.com/johnAzani/docoga → Actions → "Deep-Dive — produce and publish one long-form episode"**
   → **Run workflow**.
2. Leave `episode = dd2`, `stage = all`, `privacy = unlisted` → **Run workflow**.
3. Come back in ~45–60 minutes. The run page shows the blocks *Which episode*, *Voice*, *Render scene 1…9*,
   *Master + cover + QA*, *Publish to YouTube*. The **Summary** at the top has the title, the
   link, and six frames from the episode.
4. Watch it on YouTube (it is *unlisted* — only the link opens it). Happy? → YouTube Studio →
   that video → Visibility → **Public**. Or re-run with `privacy = public` next time.

**Stages, for when something needs redoing**

| `stage` | Does | When |
|---|---|---|
| `all` | voice → render → master → publish | the normal case |
| `voice` | TTS + word-sync only, banks them | harvesting quota over two days, or re-voicing after a script edit |
| `render` | render + master + QA from the banked voice, banks the MP4 — **no upload** | after a visual fix in `deepdive.py` or a plate swap |
| `publish` | uploads the banked MP4 | after a `render` run you have watched |

**Duplicate guard** — the title is looked up in `logs/youtube_longform.json`; a second run of
the same episode skips the upload and says so. `force = true` overrides.

**Custom thumbnail** — needs a *verified* channel (YouTube Studio → Settings → Channel →
Feature eligibility → Intermediate features → verify phone number). Until then the run logs a
warning and YouTube picks a frame; the publish still succeeds.

---

## Editing or adding an episode

- `script.txt` is the spoken word, nine sections separated by `--- C1 ---` … `--- C9 ---`.
  Say numbers the way they should be heard ("two hundred thousand naira", "nineteen ninety seven").
- `episode.json` holds the YouTube title/description/tags, the cover, and the **beats**: each
  beat is `{sec, trig, head, sub?, rows?, img, accent?, endcard?}`. `trig` is a phrase from
  that section's script; the beat fires the moment the narrator reaches it. Triggers must
  appear **in order** within a section — `python3 tools/deepdive.py dd2 check` proves it
  (CI runs the same check on every push).
- Plates: 16:9 JPEG, ≤1600 px, no text in the image (the duotone makes text illegible). Drop
  into `episodes/assets/<name>.jpg`, refer to `<name>` in `img`. A missing plate may point at a
  stand-in in `episodes/assets/aliases.json` so the episode still renders.
- DD3 (tenancy agreement) and DD4 (rent receipt): their beats are still in
  `tools/make_longform_dd3.py` / `_dd4.py`; port into `episodes/dd3/`, `episodes/dd4/` the same
  way DD2 was. The scripts need rewriting — the originals were never committed.

Local preview without Gemini or Vosk (sandbox or laptop):

```
python3 tools/deepdive.py dd2 check
python3 tools/deepdive.py dd2 align --synthetic           # pace-estimated timings
python3 tools/deepdive.py dd2 render 1                    # one scene (~2 min)
python3 tools/deepdive.py dd2 master --allow-synthetic    # silent preview, refused by CI
```

The workflow refuses synthetic timings on purpose — nothing pace-estimated reaches the channel.

---

## The numbers — pulled automatically

`tools/yt_stats.py` runs every **Monday 06:00 WAT** (`.github/workflows/youtube_stats.yml`) and on
demand (Actions → *YouTube stats — weekly snapshot* → Run workflow). Read-only; never touches a
video. It writes:

- `logs/youtube_stats.json` — append-only snapshots (the record);
- `docs/YOUTUBE_PERFORMANCE.md` — the latest numbers as a table with deltas since the previous
  snapshot: subscribers, views per video (Shorts and Deep-Dives, from both ledgers plus the
  channel's latest uploads), likes, comments, length, privacy — and the "best so far" lines that
  steer the next hook and the next episode.

Any session can read that file before deciding what to make next; that is the point of it.

**Deeper metrics (watch time, average % viewed, impressions → click-through, traffic sources)**
come from the YouTube *Analytics* API and need one more permission on the token:
`https://www.googleapis.com/auth/yt-analytics.readonly`. The job detects the missing scope and
says so in the report; everything above still lands. To add it: re-mint `YT_REFRESH_TOKEN` with
that scope ticked alongside `youtube.upload` + `youtube.readonly` (same consent flow as
`docs/LAUNCH_SEQUENCE.md` step 3), paste the new token into the secret. Nothing else changes.

## What is intentionally not done

- **No b-roll.** Stills with camera drift, grain, the left gradient and the caption line —
  the Deep-Dive grammar in `docs/BRAND_STYLE.md`.
- **No downloaded audio.** See the sound section: the kit is synthesized, not sourced.
- **The nightly tick publishes only what is queued.** `episodes/queue.json` is the gate; an
  episode folder that is not listed there is never touched by the schedule.
- **The legacy `make_longform*.py`, `tts_batch_dd2.py`, `dd2_align.py`, `mux_dd2.py`,
  `yt_upload_long.py`** are superseded by `tools/deepdive.py`; they are kept only for the
  DD3/DD4 beat lists.
