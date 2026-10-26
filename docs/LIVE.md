# DocOga Live — the always-on stream (Oracle VM = mouth, GitHub Actions = brain)

Owner, 26 Oct 2026, 4:20am: *"go — I want live stream to always be on for life, pulling in
watch time, subscribers etc."* Same morning, after the research: *"I don't want to run it on
GitHub, I don't want to take that risk. Let's do it in Oracle."* This is that lane. ₦0,
touches no upload lane, runs by itself.

## What a viewer sees

A public live video on the channel, 24 hours a day: **"DocOga Live 24/7 — Nigerian rent &
tenancy law, explained (pre-recorded loop)"**. The loop is the channel's own episodes —
every Saturday Deep-Dive (once its Saturday has come) and every weekday Short, newest Short
first, Shorts and Deep-Dives turn about. A Short stands on the right of a brand card that
says *You're watching DocOga Live · LIVE 24/7 · PRE-RECORDED*; a Deep-Dive fills the frame.
DVR is on. The description says plainly that this is not a live presenter.

## Why not GitHub

GitHub's Actions terms (27 Aug 2026): Actions may only be used "to develop and test your
application(s)"; not as "a content delivery network"; on hosted runners, for nothing
"unrelated to the production, testing, deployment, or publication of the software project".
Misuse can end in suspension of the whole account — every lane, the site deploys, the clock.
A 24/7 RTMP relay is the textbook case. So **no video is ever pushed from Actions**.

## The split

| Where | What | How often |
|---|---|---|
| **GitHub Actions** (`youtube_live.yml`) | `prepare` — read the library from the releases, normalise what is new to one 1080p30 profile (keyframe every 2 s), bank the segments and `loop.json` on the `live-library` release · `ensure` — keep one public broadcast alive (auto-start on, **auto-stop off**, DVR, bound to the one reusable stream key; first run creates it and sets the cover) · `health` — is data arriving? If not, Telegram the owner the one tap | 1:05am · 7:05am · 1:05pm · 7:05pm (the clock), minutes each |
| **Shorts lane** | after every published 7:00pm Short, bank the file as `short-<date>.mp4` on `live-library` | weekdays |
| **Oracle Always Free VM** (`deploy/live/`) | `serve` — pull `loop.json` from the public release, fetch the segments it lacks, concatenate the reel, push it with `ffmpeg -re -stream_loop -1 -c copy` to `rtmps://a.rtmps.youtube.com/live2`; re-read the manifest every half hour, rebuild and restart the push when the loop changed, restart a dead push after 5 s | always |

The VM never re-encodes, so Oracle's smallest free machine (VM.Standard.E2.1.Micro: 1/8 OCPU,
1 GB, 50 Mbps out) carries a 4.6 Mbps stream with room to spare. Data: ~50 GB/day, ~1.5 TB a
month, inside Oracle's 10 TB/month free egress.

## The VM, exactly

- **Account:** Oracle Cloud Free Tier (oracle.com/cloud/free). The signup gate rejects
  prepaid/virtual cards and many debit cards; a Visa/Mastercard with international payments
  enabled, billing address exactly as the bank has it, no VPN. Home region is permanent and
  Always Free compute lives only there — choose by capacity, not distance (an RTMP push does
  not care about latency).
- **Instance:** Compute → Instances → Create. Name `docoga-live`. Image *Canonical Ubuntu
  24.04 Minimal*. Shape *VM.Standard.E2.1.Micro* (Always Free). Default VCN with a public
  IP. Advanced options → Management → Initialization script → paste `deploy/live/cloud-init.sh`
  with the stream key in place of `PASTE_STREAM_KEY_HERE`. Create. Nothing inbound is opened.
- **Stream key:** YouTube Studio → Go live → Manage → stream settings → *DocOga Live key
  (reusable)* → copy. It is the only secret on the machine: `/etc/docoga-live/stream_key`,
  root, 0600. Rotate: write the new key there, `systemctl restart docoga-live`.
- **Service:** `docoga-live.service` (Restart=always, StartLimitIntervalSec=0) runs
  `tools/yt_live.py serve`; `docoga-live-pull.timer` pulls `main` hourly and restarts the
  service when it moved, so a fix merged here reaches the VM without a visit.
- **Logs:** `journalctl -u docoga-live -f`. **Stop:** `systemctl stop docoga-live`.

## Oracle's traps, and what we do about each

| Trap | Fact | Our answer |
|---|---|---|
| Idle reclaim | an Always Free instance is "idle" when over 7 days CPU p95 < 20% **and** network < 20% (**and** memory < 20%, Arm only); Oracle emails, then *stops* it (volume kept) | a `-c copy` stream trips all three. The 7:05-type control runs `health`; if no data, the owner gets one Telegram: *tap Start*. Later, if reclaims happen: Oracle's own remedy is PAYG (₦0 within Always Free) or an OCI API restart from the control run |
| June 2026 halving | Arm allowance cut to 2 OCPU/12 GB without announcement; over-cap instances terminated from 18 Aug 2026 | we use the AMD micro, untouched by the cut and usually available |
| Terminations | free tenancies are sometimes closed by "the system" with no appeal | nothing lives only on the VM: the loop is on GitHub releases, the key is re-issuable, the install is one script — rebuild in an hour |
| Signup gate | "transaction could not be processed" is Oracle's fraud filter, not the card | see Account above |

## Switches and files

| Thing | Where |
|---|---|
| Kill switch (Actions side) | repository variable `DOCOGA_LIVE=off` → the next control run ends the broadcast; the Shorts lane stops banking |
| Kill switch (VM side) | `systemctl stop docoga-live` (or Stop the instance in the Oracle console) |
| The broadcast ledger | `logs/youtube_live.json` (newest first) — written only when a new broadcast is made |
| The library | release `live-library` (`short-<date>.mp4`, `norm-*.mp4`, `loop.json`) + `deepdive-<ep>` releases (`<ep>-episode.mp4`) |
| Token | the sealed Google refresh token already carries `youtube` + `youtube.force-ssl` — nothing new to mint; the VM holds none of it |
| Failure | one open issue "DocOga Live: a control run failed" (comments, never a second issue); the VM keeps playing the last loop it fetched |

## What YouTube says

Live must be enabled once in Studio (done 26 Oct); encoder streams have no subscriber
minimum. A stream longer than 12 hours is not kept as a video — we want the window, not the
VOD. Pre-recorded content streamed as live is allowed when it is original and not
misleading; the title, description and card all say pre-recorded. "Repetitive content" is a
monetisation rule judged on the channel as a whole, where the originals are.
