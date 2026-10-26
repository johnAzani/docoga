# DocOga Live — the always-on stream

Owner, 26 Oct 2026, 4:20am: *"go — I want live stream to always be on for life, pulling in
watch time, subscribers etc."* This is that lane. It costs ₦0, touches no upload lane, and
runs by itself.

## What a viewer sees

A public live video on the channel, 24 hours a day: **"DocOga Live 24/7 — Nigerian rent &
tenancy law, explained (pre-recorded loop)"**. The loop is the channel's own episodes —
every Saturday Deep-Dive and every weekday Short, newest Short first, Shorts and Deep-Dives
turn about. A Short stands on the right of a brand card that says *You're watching DocOga
Live · LIVE 24/7 · PRE-RECORDED*; a Deep-Dive fills the frame. DVR is on, so a viewer can
scrub back. The description says plainly that this is not a live presenter.

## How it stays up for life on free runners

A GitHub Actions job may run six hours. So the stream is a chain of windows:

1. A window starts, **queues the next window first** (`gh workflow run youtube_live.yml`),
   and installs ffmpeg.
2. It reads the library from the releases (`deepdive-<ep>` masters, `live-library` Shorts),
   downloads the already-normalised segments, normalises only what is new (one 1080p30
   profile, keyframe every 2 s) and banks those back on `live-library`, then concatenates
   the reel.
3. It finds the broadcast that is already live (or makes one, public, auto-start on,
   **auto-stop off**), binds the one reusable stream key, masks the key in the log, and
   pushes the reel on a loop with `ffmpeg -re -stream_loop -1 -c copy` for **5 hours 45
   minutes**.
4. It exits. The queued window has been waiting in the `docoga-live` concurrency group and
   starts within seconds; the broadcast shows "reconnecting" for about a minute, then
   carries on — same video, same URL, same chat.

The clock (`workers/clock`) also dispatches the lane at **1:05am, 7:05am, 1:05pm and
7:05pm** as a backstop, so a window that died at setup is replaced within the hour. Two
pending windows collapse into one; two cannot run at once.

**The Shorts lane feeds it.** After every successful 7:00pm Short, the published file is
banked as `short-<date>.mp4` on the `live-library` release and joins the loop in the next
window — nothing is re-rendered.

## Switches and files

| Thing | Where |
|---|---|
| Kill switch | repository variable `DOCOGA_LIVE=off` → the next window ends the broadcast, queues nothing; the Shorts lane stops banking |
| Window length | `tools/yt_live.py` `LIVE_MINUTES = 345`; a dispatch may pass `minutes` for a short test window |
| The broadcast ledger | `logs/youtube_live.json` (newest first: broadcast id, watch URL, created time) — written only when a new broadcast is made |
| The library | GitHub release `live-library` (`short-<date>.mp4`, `norm-*.mp4`) + `deepdive-<ep>` releases (`<ep>-episode.mp4`) |
| Token | the sealed Google refresh token already carries `youtube` + `youtube.force-ssl` — nothing new to mint |
| Failure | one open issue "DocOga Live: a window could not stream" (comments, never a second issue); the chain keeps trying |

## What YouTube says, and what we do about it

- **Eligibility** — live streaming must be enabled once in Studio (phone verification; up to
  24 h). Done: the Live Control Room was open on 26 Oct. Encoder/API streams have no
  subscriber minimum (the 50-subscriber rule is the phone app).
- **No archive past 12 hours** — a stream longer than 12 hours is not kept as a video. We
  want the live window, not the VOD; the episodes already exist as videos.
- **Honesty** — the title says *pre-recorded loop*, the description says *not a live
  presenter*, the card says *PRE-RECORDED*. Nothing claims to be happening in real time.
- **Reused content** — a loop of one's own episodes is allowed; the "repetitive content"
  rule is a monetisation rule, and this channel is not monetised yet. When it is, the
  live's watch hours count toward the 4,000 — and the reused-content review will look at
  the channel as a whole, where the originals are.

## What this is not

Not Facebook Live (needs a Page with ≥100 followers and ≥60 days, and a pre-recorded
label — later, when the Page qualifies), not Instagram or TikTok Live (≥1,000 followers and
no API), not LinkedIn (forbids pre-recorded). YouTube is the one platform where this is
allowed, free and automatable today.
