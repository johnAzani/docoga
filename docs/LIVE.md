# DocOga Live — the always-on stream (one small machine = mouth, GitHub Actions = brain)

Owner, 26 Oct 2026, 4:20am: *"go — I want live stream to always be on for life, pulling in
watch time, subscribers etc."* Same morning, after the research: *"I don't want to run it on
GitHub, I don't want to take that risk. Let's do it in Oracle."* This is that lane. ₦0,
touches no upload lane, runs by itself.

**Host status — 27 Oct 2026, 11:20am: PARKED (owner's choice A).** The owner could not get
through Oracle's signup gate (*"I could not use Oracle"*, 27 Oct) and chose to park the stream
rather than pay for a box: *"A"*. What that means in practice: the control runs keep going at
₦0 (the loop stays banked and current, the reusable key stays ready), the public broadcast is
**not** created until data arrives on that key, and nobody is Telegrammed. Un-parking is not a
code change: install `deploy/live/install.sh` on any Ubuntu 24.04 machine with the key, and the
next control run makes the broadcast and takes it live. Candidate boxes and their prices are in
"Choosing the machine" below; the first spend waits for the app's own fund, on the owner's word.

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
| **GitHub Actions** (`youtube_live.yml`) | `prepare` — read the library from the releases, normalise what is new to one 1080p30 profile (keyframe every 2 s), bank the segments and `loop.json` on the `live-library` release · `ensure` — keep the one reusable stream key; once data is arriving on it, keep one public broadcast alive (auto-start on, **auto-stop off**, DVR, bound to that key; the first run after data arrives creates it, binds it, takes it live and sets the cover — see `_broadcasts`: `broadcastStatus` is never paired with `mine`, the HTTP 400 that killed every control run 26–27 Oct) · `health` — is data arriving? If not, and a broadcast has ever existed, Telegram the owner the one tap (no nagging before any machine exists) | 1:05am · 7:05am · 1:05pm · 7:05pm (the clock), minutes each |
| **Shorts lane** | after every published 7:00pm Short, bank the file as `short-<date>.mp4` on `live-library` | weekdays |
| **The host machine** (`deploy/live/`; Oracle Always Free when it can be had, else the cheapest paid box the fund allows) | `serve` — pull `loop.json` from the public release, fetch the segments it lacks, concatenate the reel, push it with `ffmpeg -re -stream_loop -1 -c copy` to `rtmps://a.rtmps.youtube.com/live2`; re-read the manifest every half hour, rebuild and restart the push when the loop changed, restart a dead push after 5 s | always |

The VM never re-encodes, so Oracle's smallest free machine (VM.Standard.E2.1.Micro: 1/8 OCPU,
1 GB, 50 Mbps out) carries a 4.6 Mbps stream with room to spare. Data: ~50 GB/day, ~1.5 TB a
month, inside Oracle's 10 TB/month free egress.

## Choosing the machine (researched 26–27 Oct 2026)

Need: always on, ~1.5 TB/month out at 1080p30 (~260 GB even at 480p), no expiry. What fits:

| Host | Cost | Traffic | Notes |
|---|---|---|---|
| Oracle Always Free (E2.1.Micro) | ₦0 | 10 TB/mo | the only free-for-life fit; signup gate rejected the owner 26 Oct |
| Oracle Pay-As-You-Go, same tenancy | ₦0 inside the free limits | 10 TB/mo | no idle reclaim; needs a card that passes the same gate |
| RackNerd annual KVM (2 TB plan) | ≈ $11–18 a year, fixed for life | 2 TB/mo | the cheapest paid ticket; same `install.sh` |
| Hetzner CAX11/CX23 (EU) | ≈ €6/mo + €0.50 IPv4 | 20 TB/mo | boring and reliable; prices rose twice in 2026 |

Ruled out, with the number that rules them out: Render (5 GB/mo), Koyeb (100 GB, closed to
new free users), Back4App (60-minute containers), Fly (no free tier), GCP e2-micro (1 GB/mo
free egress), the 24/7-restream SaaS tiers (24 h *per month* free), and Cloudflare Durable
Objects on the Free plan (10 ms CPU per invocation — a socket can be held but 50 GB/day cannot
be framed through it; the Paid plan could, at $5/mo, and would still be harder than a VM).

## The machine, exactly (Oracle wording; any Ubuntu 24.04 box is the same from "Stream key" on)

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
