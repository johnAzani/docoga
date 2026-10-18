# TikTok lane — every Short into your TikTok inbox, ₦0, no audit

`tools/tiktok_draft.py`, hooked into `.github/workflows/youtube_scheduled.yml` right after
the YouTube upload (Tue & Fri 18:00 Lagos). 17 Oct 2026.

## Why
TikTok's ad reach in Nigeria is **47.8M adults, +43 % in a year** (DataReportal, Oct 2026) —
the biggest audience any lane in this repo can touch, and the one every other feed is
losing minutes to. The Short already exists: vertical, voiced by the locked narrator,
22–45 s, on-brand. The only question was how to get it onto TikTok without a card or a
months-long audit.

## What TikTok allows an unaudited app (the honest version)
| route | what you get | verdict |
|---|---|---|
| Direct Post (`video.publish`) | forced `SELF_ONLY` (private) until the app passes TikTok's audit — error `unaudited_client_can_only_post_to_private_accounts` | useless for reach |
| **Inbox upload** (`video.upload`, `POST /v2/post/publish/inbox/video/init/`) | the video lands in **your TikTok inbox as a draft notification**; you open the app, write the caption, tap Post | **this lane** — no audit, ≤5 pending per 24 h |

The one tap we could not remove is the one TikTok reserves for a human. The run summary
prints the caption to paste.

## Setting it up, from the phone (once) — 18 Oct 2026

Two halves: TikTok's developer portal (where the app lives) and one tap on
`https://docoga.com.ng/tiktok-connect.html`. No laptop, no terminal, no token pasted anywhere
by a human.

**A. The app (developers.tiktok.com, phone browser, desktop-site mode helps)**
1. Log in with your TikTok → **Manage apps** → **Connect an app** → name `DocOga`, category
   *Productivity*, description "Posts DocOga's legal-explainer Shorts to the DocOga TikTok",
   icon `brand/favicon-512.png`, Terms `https://docoga.com.ng/terms.html`, Privacy
   `https://docoga.com.ng/privacy.html`, platform **Web** → URL `https://docoga.com.ng`.
2. **Add products**: **Login Kit**, **Content Posting API**, **Display API** (the last one is
   what lets the Monday scorecard read your follower/like/view counts).
3. Login Kit → **Redirect URI (Web)**: `https://docoga.com.ng/tiktok-connect.html` — exactly.
4. Scopes: tick everything the three products offer — `user.info.basic`, `user.info.profile`,
   `user.info.stats`, `video.list`, `video.upload`, `video.publish`. One consent, never again.
5. Do **not** submit for review. Open **Sandbox** → *Create sandbox* (clone the app's config)
   → **Target users** → add your own TikTok username. Sandbox needs no review for target
   users and no URL verification; the inbox upload works there. (If TikTok still asks you to
   verify `docoga.com.ng`, pick **Domain → DNS record** and add the TXT it shows in
   Cloudflare → DNS; the file route is unnecessary.)
6. Copy the **sandbox's** Client key and Client secret (each sandbox has its own pair) →
   GitHub → Settings → Secrets → Actions: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`.

**B. The tap**
7. Sign in to `https://docoga.com.ng/admin` on the phone (the connect page uses that session).
8. Open `https://docoga.com.ng/tiktok-connect.html`, paste the Client key (public; it is
   remembered on the phone), tap **Connect TikTok** → TikTok's consent screen → **Authorize**.
9. You land back on the page. It sends the code to the worker (`POST /admin/tiktok/connect`),
   which dispatches `.github/workflows/tiktok_connect.yml`; that job exchanges the code,
   seals the refresh token into `logs/tiktok_refresh_token.box` (vault key `SOCIAL_TOKEN_KEY`,
   same as Instagram/Threads) and commits the box. No token is printed anywhere; the code is
   masked and single-use. The dashboard → Social → machinery row reads **TikTok: connected**
   within two minutes (via the dashboard feed).
10. Not signed in, or the session expired? The page shows the code with a **Copy** button and
    a link to *Actions → TikTok — connect → Run workflow*: paste it there. Codes die in
    minutes; just tap Connect again if one does.

From then on the lane runs on the sealed box; the refresh call rotates it and the lane reseals.
`TIKTOK_REFRESH_TOKEN` as a repository secret is only a fallback and is not needed.

## Testing it now, from the phone — "TikTok — send a test draft now"

`.github/workflows/tiktok_test.yml` (18 Oct 2026) is the owner's "does it work?" button. On
the phone: github.com → the repo → **Actions** → **TikTok — send a test draft now** → **Run
workflow** → **Run workflow** (leave the two fields alone). About four minutes later the run
summary shows the result and, on success, the exact caption to paste.

What it does, in order: `tiktok_draft.py status` then `probe` (the token must mint *before*
anything is rendered — a dead refresh token fails in 20 seconds, by name); renders the day's
rotation Short with the real pipeline (locked narrator, MotionStudio, sounds; a different
date via `for_date`); `tiktok_draft.py send`; commits `logs/tiktok_drafts.json` and the
rotated `logs/tiktok_refresh_token.box` back to main **whatever happened after the probe**;
keeps the MP4 as a 7-day artifact. It never touches YouTube, Telegram, or their ledgers, and
it shares the Shorts run's concurrency group so it can never race the 6:00pm run.

If the summary says the Short was not rendered because the narrator's bucket is empty, TikTok
itself is fine (the token minted) — tap Run workflow again after the time the summary names.
`duplicate` means those exact bytes were already sent (tick **force** to send anyway);
`skipped` means five drafts are already waiting in the inbox — post or discard them first.

## After the first draft — the three corrections (18 Oct 2026)
The first draft posted. The owner saw three things; here is what each was and what changed.

**1. "No thumbnail."** TikTok's inbox upload has no cover field (only the audited Direct Post
API has `video_cover_timestamp_ms`), so TikTok shows **frame 0**. MotionStudio's frame 0 was the
empty navy an instant before the words animate in. Now `tools/motionstudio.py` draws the opening
card *settled* as frame 0 (`poster_frame`) — the scene then opens with its flash and build as
before — and writes the same picture as `<master>.cover.jpg`. That file is also the Short's
**YouTube custom thumbnail** (`tools/yt_thumbnail.py`, new step in `youtube_scheduled.yml`) and
the **Telegram** video thumbnail (`telegram_video.py --cover`).

**2. "No images behind the cards."** The photographs were there but treated at `darken=0.36`:
the brightest pixel was ≈ 86/255 and a phone showed navy. `tools/shorts_reel.py` now passes
`SHOT_DARKEN = 0.68` (cards: `brain_visual.treat` default 0.58). Each render prints
`SHOTS_HITS=<matched>/<scenes>` (`::notice` + summary row), and the lane pushes a labelled
**contact sheet + cover** to the `review` branch (`tools/contact_sheet.py`,
`tools/review_push.sh`; folder `<date>_tiktok-test_<run id>` / `<date>_short_<run id>`) —
readable through the contents API even where run artifacts cannot be downloaded. A frame whose
margins average ≥ 35 luminance is photographed; navy is ≈ 22.

**3. "I had to paste the caption."** That one is TikTok's rule, not ours: the inbox API carries
no caption; the only caption-bearing API is Direct Post, which an **unaudited** app may use on
**private** accounts only. Until the audit, the caption comes to the phone instead: when a draft
lands, `tools/owner_dm.py` DMs it from **@docoga_daily_bot** as a tap-to-copy block with the
taps that follow. One-time setup — open Telegram → **@docoga_daily_bot** → **Start** → send the
word **owner**. The next run adopts that chat (`logs/telegram_owner.json`, committed with the
ledger) and texts every caption after that. The run summary says `📲 sent` or shows the setup
line. Removing the paste itself needs the **Content Posting API audit** (free): in the TikTok
developer portal, the app's Content Posting API product → *Apply for audit* → Terms of Service
URL `https://docoga.com.ng/terms.html`, Privacy Policy URL `https://docoga.com.ng/privacy.html`,
and a short screen recording of the posting flow (creator-info call, privacy picker with no
default, the commercial-content toggle, a preview). After approval `tiktok_draft.py` can switch to
Direct Post with `post_info.title` + `video_cover_timestamp_ms`, and the tap disappears.

## Guard rails
- Dormant (notice, exit 0) until the two app secrets and the sealed box (or the fallback secret)
  exist; never fails the YouTube publish it rides on (`continue-on-error`).
- `python3 tools/tiktok_draft.py status` → `TIKTOK_CONNECTED=yes|no` from the box header, no
  network; the dashboard feed carries the same fact (`feed.tiktok`).
- Duplicate guard by file SHA in `logs/tiktok_drafts.json`.
- Stops at five pending inbox uploads in 24 h (TikTok's wall) with a warning to post or
  discard them in the app.
- Chunks: one chunk ≤64 MB, else 10 MB chunks (TikTok: 5–64 MB, last may be larger).
- Polls `/v2/post/publish/status/fetch/` until `SEND_TO_USER_INBOX` / `FAILED`.

## Machine lines
`TIKTOK_RESULT=inbox|duplicate|skipped|dormant|dry-run|probed|failed`, `TIKTOK_CAUSE=…`,
`TIKTOK_PUBLISH_ID=…`, `TIKTOK_STATUS=…`, `TIKTOK_VAULT=sealed`; render: `SHOTS_HITS=n/m`,
`COVER=<path>`; review: `SHEET=…`, `SHEET_BRIGHTNESS=…`, `SHEET_PHOTO_FRAMES=n/m`, `REVIEW_URL=…`;
owner DM: `OWNER_DM=sent|unknown|skipped|failed`, `OWNER_CHAT=…`; from `connect`:
`TIKTOK_CONNECT=ok|refused|failed`, `TIKTOK_OPEN_ID=…`, `TIKTOK_SCOPES=…`, `TIKTOK_USER=@…`;
from `status`: `TIKTOK_CONNECTED=yes|no`, `TIKTOK_BOX=sealed <date>|absent`.

## Later, if wanted
A Direct Post audit (so the tap disappears) needs a demo video of the app's UI showing the
creator-info call, the privacy picker with no default, the commercial-content toggle and a
preview — a web page, not a cron. Not ₦0 in hours; parked.
