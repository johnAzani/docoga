# Instagram + Threads — the two Meta lanes

Written 13 Oct 2026, after reading the current API surface rather than this repo's older
notes. Where this page contradicts `FACEBOOK_AUTOMATION.md` or the first draft of
`docs/LAUNCH_SEQUENCE.md`, **this page is the correction**, and the sentence it corrects is
quoted so you can see what changed and why.

---

## The one-sentence version

**Threads can be fully unattended the day two secrets exist. Instagram can be too — Reels
included, since 16 Oct 2026, by Meta's resumable upload through the Facebook lane (see
"Reels" below): no public video file, no host, ₦0.**

That is the whole asymmetry, and it comes from one design fact on Meta's side: a Threads post
can be *text*, while every Instagram container (photo, carousel, Reel, Story) is a **URL that
Meta's servers download**. Instagram has no multipart upload. So Instagram needs a public file
host and Threads needs nothing — and since DocOga already runs a public file host (the deployed
`site/`, on Cloudflare, for ₦0), the honest answer is that neither lane is blocked on
permissions any more.

---

## The correction: this was never blocked on App Review

`docs/LAUNCH_SEQUENCE.md` used to say, about Instagram:

> its media container path needs a Meta app with `instagram_content_publish` approved — which
> is a business-verification conversation, not a code task.

The second half was wrong, and it was the half that kept the lane switched off for weeks.

| what the internet tells you | what is actually true in 2026 | why it matters here |
|---|---|---|
| "Publishing via the Instagram API requires App Review + Business Verification" | Those gates are for **Advanced Access** — an app publishing on accounts it does **not** own or manage. **Standard Access** is granted automatically and covers accounts owned by someone with a role on the app (admin / developer / tester). | DocOga publishes to DocOga's own profile from an app DocOga owns. That is the Standard Access case: **no review, no verification, no queue.** |
| "You need `instagram_content_publish`" | The scope names changed on **27 Jan 2025**. On the Instagram-Login path it is `instagram_business_basic` + `instagram_business_content_publish` (host `graph.instagram.com`, no Facebook Page needed). `instagram_content_publish` is the *Facebook-Login* name (host `graph.facebook.com`, Page required). | A 2023 tutorial asks for a deprecated scope and the app never gets the permission it actually calls with. |
| "Reels work for Business and Creator accounts" | Content publishing works for both; **Reels are reported to be Business-only**, and the aspect/duration rules are stricter (9:16, 5–90 s). | If the profile is Creator, a Reel container can be created and still not publish. Photo/carousel is unaffected. |
| "Meta's Basic Display API can post for personal accounts" | Basic Display is **dead** (sunset completed 2024–2025) and was read-only anyway. A **personal** Instagram account has **no publishing API at all** — switch it to Business or Creator in the app first. | The preflight checks `account_type` and refuses early with that sentence, so you find out in 3 seconds instead of at 09:00 UTC with a red run and no explanation. |

Also worth naming, because it is a real limit and not a scare: **a 60-day token**. Both lanes
run on user tokens that Meta expires after 60 days unless they are refreshed, and — this is the
part that decides the architecture — **a GitHub Actions job cannot write its own repository
secrets**: the secrets API needs the `secrets` permission, which the `GITHUB_TOKEN` minted for a
workflow does not carry (GitHub staff, community discussion #160560, 10 Jun 2024). So a lane that
successfully refreshes its token has nowhere to *keep* the new one… unless we give it one. That
is what `tools/token_vault.py` is for, below.

---

## Requirement matrix (the recommended column is what the code assumes)

| requirement | Threads | Instagram | recommended | why |
|---|---|---|---|---|
| Account type | public professional profile | a **professional account** — Business or Creator | **switch the IG account to Business** | a personal account has no publishing API at all; Creator blocks Reels, Business is free and reversible |
| Meta app | one app, Threads use case | one app, Instagram product | **same app for both** | one OAuth client, one secrets set, one review-free path |
| Scopes | `threads_basic`, `threads_content_publish` | `instagram_business_basic`, `instagram_business_content_publish` | both, in one consent | re-consenting costs an hour; doing it twice costs two |
| App Review | not needed (own account) | not needed (own account) | **skip it** | Standard Access covers us; see the correction above |
| Media host | none (text) | public URL, JPEG, ≤8 MB, 4:5…1.91:1 | **`site/social/` on the deployed site** | ₦0, no new account, nothing third-party holding our content |
| Scheduler | GitHub Actions cron | same | **Actions** (there is no Meta-side scheduling API) | Threads documents that an app offering scheduling enforces its own limits; ours does, in `logs/` |
| Token lifetime | 60 days, refresh `grant_type=th_refresh_token` | 60 days, refresh `grant_type=ig_refresh_token` | **vault + daily refresh** | the only design that satisfies "no manual intervention after setup" |
| Daily volume | 1 post (limit 250/24 h) | 1 card (limit 100/24 h) | 1 each | headroom means a manual re-run can never exhaust the lane |
| Cost | ₦0 | 0 | — | no paid tier on either API; Cloudflare free tier already covers the site |

**Pre-selected option:** do Threads first (2 secrets, 10 minutes, nothing to host), then
Instagram (same app, one more consent, one card renderer already written). Both lanes are
already merged-ready in this branch; the setup below is the only thing between "dispatch-only"
and "posting daily".

---

## What is already built (so you do not rebuild it)

| piece | what it does |
|---|---|
| `.github/workflows/threads_autopost.yml` | 08:45 UTC daily. preflight → ledger → **read the profile for the exact wording** → publish → wind the token → record → commit. `dry_run` / `probe_only` / `force` / `text` on dispatch. |
| `.github/workflows/instagram_autopost.yml` | 09:00 UTC daily. preflight → caption → render card → **commit it to `site/social/`** → ledger → wait for the URL to be public → container → publish → read back → record → wind the token → prune. The prune keeps 60 dated renders, by **filename**: `site/social/` is inside the deployed tree, and retention keyed on mtime would never fire, because a fresh checkout stamps every file with today. |
| `scripts/generate_threads_content.py` | today's post, de-escaped, fitted to 500 **bytes-weighted** characters, ≤5 links, deterministic for the day. It writes `assets/threads/threads_content_latest.json` and **that file's `text` field is what gets published**; `--print` is a human preview with a frame and trim notes around the same text, so its byte count is not the number the API judges (730 bytes of preview box around a 271-byte post — measured 13 Oct, and it will look like an over-length bug if you read the wrong output). |
| `tools/threads_publish.py` | stdlib-only Threads publisher. `--probe`, `--dry-run`, `--refresh`, exit code per cause. |
| `tools/ig_publish.py` | Instagram publisher, rewritten: an exit code for every outcome, a JPEG header gate, `--wait-url` for the deploy race, redaction before any print. |
| `tools/social_card.py` | 1080×1350 brand card from the same copy; strips the emoji the runner's fonts cannot draw (the caption keeps them). |
| `tools/token_vault.py` | AES-256-GCM box in `logs/`, key in Actions. Refuses to run without `cryptography` rather than storing plaintext; refuses to write into `site/`. |
| `tools/lane_status.py` | `python3 tools/lane_status.py --lane threads` → the failing step, what never ran, and the annotations. No log bytes, so it works from a sandbox. |

---

## Setup, tap by tap (Threads first)

### T1 — Create the app (2 minutes, one browser)

1. <https://developers.facebook.com> → **My Apps → Create app**. *[If Meta asks you to
   "Register" as a developer first: personal, 2FA on the Meta account, free.]*
2. Use case: **Other** → add the **Threads** product (and **Instagram** when you do T4).
3. **App settings → Basic**: note the **App ID** and **App secret**. *[You will need the secret
   only if you ever switch Instagram to the Facebook-Login path; for `ig_refresh_token` you do
   not.]*

**Expected screen:** an app with a "Development" badge. That is fine and permanent for our use:
Development mode + Standard Access is exactly what lets us publish to our own accounts.

### T2 — Authorise once, from your own machine (5 minutes)

```bash
# 1. build the consent URL (redirect_uri must be registered under Threads → Auth & Security)
open "https://threads.net/oauth/authorize?client_id=<APP_ID>&redirect_uri=<YOUR_REDIRECT>&response_type=code&scope=threads_basic,threads_content_publish"
# 2. exchange the code for a short-lived token, then for the 60-day one
curl -s -X POST "https://graph.threads.net/oauth/access_token" \
  -d "client_id=<APP_ID>&client_secret=<APP_SECRET>&grant_type=authorization_code&redirect_uri=<YOUR_REDIRECT>&code=<CODE>"
curl -s "https://graph.threads.net/v1.0/oauth/refresh_token?grant_type=th_refresh_token&access_token=<SHORT_LIVED>"
```

**What you should see:** JSON with `access_token` and `expires_in: 5184000` (60 days).

> If `expires_in` is 3600, you are holding the **short**-lived token. The exchange above is the
> only step with a real gotcha, so check the number rather than hoping.

### T3 — Two secrets, then one tap that removes all future taps

```bash
gh secret set THREADS_USER_ID  --repo johnAzani/docoga --body '<the numeric user id from T2>'
gh secret set THREADS_ACCESS_TOKEN --repo johnAzani/docoga --body '<the 60-day token>'
gh secret set SOCIAL_TOKEN_KEY --repo johnAzani/docoga --body "$(openssl rand -hex 32)"
```

* Expected: `✓ Set secret …` for each. No output is normal; secret **names** are not even
  listable from an Actions token.
* **Meta allows one refresh per 24 hours.** So the run you do the same day you set the secret
  will be told `Cannot refresh a token that is less than 24 hours old`, and the lane answers with
  a **warning** and a green tick — correctly, because there is nothing to fix. The box appears the
  next morning. Both publishers deliberately keep that message off the red channel and off stdout
  (stdout is the pipe into `token_vault.py seal`, which must never be handed a sentence), so if
  the warning body ever comes back empty, the tool is printing to the wrong stream again.
* **`SOCIAL_TOKEN_KEY` is the one that buys "never again".** With it, every run refreshes the
  token and seals the new value into `logs/threads_token.box`; without it, the refreshed value
  dies with the run and the lane expires at day 60. `THREADS_USER_ID` is optional (the publisher
  will learn it from `/me`) but setting it removes a call.
* The vault key cannot be rotated from CI by design. If you ever change it, re-seal once:
  `python3 tools/token_vault.py seal --name THREADS_TOKEN --stdin < /tmp/token.txt` locally with
  the new key exported.

### T4 — Instagram, same app (10 minutes)

1. Instagram app: **switch the account to Professional** (Business) — Instagram → Settings →
   Account type. *[Personal accounts have no publishing API, full stop.]*
2. In the Meta app: **Add product → Instagram → Instagram API with Instagram Login**. Set the
   OAuth redirect, request `instagram_business_basic` + `instagram_business_content_publish`.
3. Consent at `https://www.instagram.com/oauth/authorize?client_id=<APP_ID>&redirect_uri=<…>&response_type=code&scope=instagram_business_basic,instagram_business_content_publish`,
   exchange for a short-lived token, then:
   `GET graph.instagram.com/<API_VERSION>/access_token?grant_type=ig_exchange_token&client_secret=<APP_SECRET>&access_token=<SHORT>`
   → long-lived (60 days).
4. `gh secret set IG_ACCESS_TOKEN --repo johnAzani/docoga --body '<…>'`
   *(set `IG_USER_ID` too if you have it; `/me` will supply it otherwise)*.
5. Prove it without touching the feed:
   ```bash
   gh workflow run instagram_autopost.yml -f probe_only=true
   python3 tools/lane_status.py --lane instagram --limit 1
   ```
   **Expected:** `token authorises @docogadaily (id …, path instagram-login, profile BUSINESS)`,
   `probe: @docogadaily — N media on the account, quota 0/100 used`, and the run says
   *Probe mode — nothing was rendered and no container was created.*

`gh workflow run` needs a token that can dispatch workflows — from an agent it returns `403`, so
this particular tap is yours, or run it from the Actions page (button **Run workflow**).

### T5 — Next morning: three checks

The one thing that will confuse you here: on a **branch** whose copy of a workflow differs from
`main`'s, Actions files runs with `conclusion=failure` and **no jobs** — nothing executed, nothing
posted, nothing wrong. `python3 tools/lane_status.py --lane instagram` now says so in words
("the runner executed none of them … Nothing was posted and nothing failed; merge the file")
instead of showing you a posting failure that never happened. That sentence is load-bearing: it is
how this lane was briefly believed broken on 13 Oct 2026, an hour after it was finished.

```bash
gh run list --limit 8                    # threads + instagram green?
git show main:logs/threads_sent.json     # a real entry, with a threads.net permalink?
git show main:logs/instagram_sent.json   # and an instagram.com/p/… permalink?
python3 tools/lane_status.py --lane threads --limit 2   # if not: the cause, without the log
```

Also look for `TOKEN_EXPIRES_IN_DAYS=` in either run summary. **After the first successful run
it should be ~59–60.** If it is missing entirely, the vault is not being written (usually
`SOCIAL_TOKEN_KEY`), and that is a tap to make today, not a surprise in December.

---

## Failure table — every state, and the check that names it

| what the run says | what it means | what to do |
|---|---|---|
| `THREADS_RESULT=refused THREADS_CAUSE=setup` (exit 2) | no credential in this repo | T2/T3. Not an outage; nothing was attempted. |
| `invalid oauth access token` / `code 190` | the 60-day token expired or was revoked | re-consent once, then set `SOCIAL_TOKEN_KEY` so it never happens again |
| `(#200) … permission` / `not approved` | the app is missing the scope, or the account is not professional | App settings → the scope must be listed; for Instagram check the `profile …` value in the probe line (`account_type`) |
| `THREADS_PUBLISHING_LIMIT_EXCEEDED` / `code 32` | 250 posts in 24 h — one post a day cannot do this alone | find the other publisher using this token; `GET /{user}/threads_publishing_limit` shows usage |
| `LINK_LIMIT_EXCEEDED` / `too long` | the copy, not the platform: >5 links or >500 bytes | `generate_threads_content.py` should have caught it — that is a bug report, open one |
| `transport failure` | the runner could not reach `graph.threads.net` | check `.github/workflows/net-probe.yml`; the next scheduled run is unaffected |
| `refused-duplicate` (exit **0**) | this exact wording is already on the profile | correct behaviour, nothing to fix; the run prints the permalink it found |
| `duplicate guard unavailable` (a warning) | the profile list could not be read, so the post went out on the ledger's word alone | fine once; repeated days mean the read is blocked — check the token's `threads_basic` |
| `green run, no ledger entry` | `green-but-quiet` — a step skipped upstream | the summary names which; the heartbeat files this deliberately |
| Instagram `Unsupported URL request` / `IG_CAUSE=media` | the JPEG was not public when Meta looked | three causes, in order of likelihood: site deploy still running (the lane waits 15 min), the render `git push` failed, or the URL was built with a `/site/` prefix (it must be `https://docoga.com.ng/social/…`) |
| Instagram `not-jpeg` / `no-SOF` | the file is not a JPEG | `social_card.py` writes JPEG; a manual `--image-url` pointing at a PNG is the usual culprit |
| Instagram `1080x2400 is 0.450:1` | outside 4:5…1.91:1 | re-render; the API's own answer to this is unreadable, which is why we check locally first |
| Instagram `account_type` is `PERSONAL` | no API for personal accounts | switch to Business in the app; there is no code path around it |

---

## The token vault, in one paragraph you can audit

`logs/threads_token.box` and `logs/ig_access_token.box` are AES-256-GCM ciphertext, committed to
the repo, whose key lives only in the Actions secret `SOCIAL_TOKEN_KEY`. The secret *name* is
additional authenticated data, so a box copied between lanes refuses to open instead of handing a
Threads token to Instagram. `seal` writes atomically and never echoes the value; `open` refuses to
print to stdout; the tool **exits 6 rather than falling back to plaintext** if `cryptography` is
missing; and it refuses any path under `site/`, because `site/` is served to the whole internet.
Threads has **no refresh token to keep**: the long-lived access token is exchanged for a new
long-lived access token (`grant_type=th_refresh_token`, and the current answer from Meta's API is
that nothing else comes back), which is why exactly one value is sealed per lane and why there is
no `THREADS_REFRESH_TOKEN` to set. If Meta ever starts rotating it, the fix is one more
`--name` on the seal step, not a redesign.

**The box holds exactly one secret: the bare access token.** Not Meta's response body —
`open --out` writes the box's contents into the file the publisher sends as its bearer token, so a
JSON envelope in the box is an `Invalid OAuth access token` on the *second* run and a green first
one (the bootstrap secret is a bare token). That was the shape until 13 Oct 2026, it passed every
single-verb test in the repo, and it is now pinned twice: cross-process in
`tools/tests/test_meta_lanes.py::VaultPipeline`, and in `tools/qa.py` so it stays pinned on a
machine where those tests skip for want of `cryptography`. `expires_in` becomes an `expires_at`
*beside* the ciphertext — metadata next to the box is not encrypted, which is also why a second
secret would get its own box rather than a second key in this one.

What this does *not* do is protect you from someone who can read Actions secrets — they already
have the bootstrap token. Its whole job is to make the refresh chain survivable, so that "no
manual intervention after setup" is a true statement about a Meta lane instead of a promise that
expires in eight weeks.

---

## Reels — researched to the thin details, then built the documented way (16 Oct 2026)

**The question was "what is the best way at ₦0?", and the honest answer is: no host at all.**

### Why not a URL

A URL-based Reel container (`video_url`) makes Meta's servers fetch the file, and since 2025
that URL must be a direct `200` with the right `Content-Type` — no redirects, no tokens, no
HTML wrappers (Google-Drive-style links now fail with "Media download has failed"). Every ₦0
host was checked against that and against "no card, no new account, no bloat":

| Candidate | Card needed | Direct 200, no redirect | What bites |
|---|---|---|---|
| docoga.com.ng itself (Workers static assets) | no | yes | 25 MiB per file; a deploy race with every other push; CDN terms say video belongs on the paid Developer Platform products (grey, low volume) |
| Cloudflare R2 | **yes**, even for the free 10 GB | yes | the card |
| Backblaze B2 public bucket | yes (private + presigned link: no) | yes | a new vendor, 1 GB/day |
| GitHub Releases | no | **no** (302) | rejected by Meta's rule |
| commit the MP4 to `site/social/` | no | yes | history grows by ~1 GB a year for a file fetched once |
| Telegram file URL | no | yes | the bot token is in the URL Meta fetches |
| Internet Archive | no | **no** (302) | — |
| Cloudinary / Supabase | no | yes | a third vendor and three more secrets for no gain |

### What Meta documents instead

"Upload Video to Meta Servers" (developers.facebook.com → Instagram Platform → Content
Publishing → Resumable uploads, updated Mar 2026): create the container with
`upload_type=resumable` and `media_type=REELS` (or `STORIES`), POST the bytes to
`https://rupload.facebook.com/ig-api-upload/<version>/<container>` with headers
`Authorization: OAuth <token>`, `offset: 0`, `file_size: <bytes>`, poll
`GET /<container>?fields=status_code,video_status` (the `uploading_phase.bytes_transferred`
field is the resume point after a dropped connection), then `media_publish`. Ceiling 1 GB /
15 minutes; a 45-second MotionStudio render is a few MB.

The one condition: it is **"available only for apps that have implemented Facebook Login for
Business"** — the `graph.facebook.com` path, with a **Page token** whose Page has the Instagram
professional account linked, carrying `instagram_basic` + `instagram_content_publish`. That is
the token the Facebook lane already holds (`FB_PAGE_ACCESS_TOKEN`), which is why the Instagram
Reel is published by `facebook_autopost.yml`, not by the Instagram lane whose token lives on
`graph.instagram.com` (no upload endpoint there, by Meta's design).

### How it runs

* **Every daily Facebook run** (09:30 Lagos) starts with `tools/ig_publish.py --probe-reels` (both doors; see "Two doors") —
  three reads, nothing created: is @docoga.ng linked to the Page
  (`GET /{page}?fields=instagram_business_account,connected_instagram_account` — either field
  is a link; a Page linked the Accounts-Center way often fills only the second), which scopes the Page token carries
  (`/debug_token` with the app token), and does the Instagram node answer a publishing read
  (`content_publishing_limit`). It prints `IG_REELS_READY=yes|no`, `IG_REELS_MISSING=…`, and the
  exact fix in one sentence. Not ready = a yellow warning on a green run, never a failure.
* **Mon + Thu**, after the Facebook Reel is published *and recorded*, the step "Instagram Reel —
  the same render, by resumable upload" sends the identical MP4 (`--video-file`) with the day's
  copy as caption, `share_to_feed=true`, and the frame at 1.5 s — the navy title card — as the
  cover (`thumb_offset`). Guards: Instagram's 30-day frame window in `logs/instagram_sent.json`
  (`Reel · <title>`), then the account's own caption duplicate guard inside the publisher. The
  resumable upload retries from `bytes_transferred` on a transport failure; a refused upload is
  `IG_RESULT=failed` with the container id, no publish, a red run, and an issue that names the
  cause. The Facebook ledger is committed *before* this step so a red Instagram step can never
  make the next run publish the Facebook Reel twice.
* **The Reel in the Story tray too:** right after it, the same bytes go out as
  `media_type=STORIES` (`--video-story`), `continue-on-error`, recorded as `instagram-story` —
  the mirror of what the Facebook lane does with its own Reel. `FB_STORIES=off` switches both.
* **Switch:** repository variable `IG_REELS` — `on` (default) or `off`.
* **Manual:** Actions → DocOga Facebook Auto-Post → Run workflow → `mode: reel` publishes the
  rotation's Reel to both surfaces now (the narrator-resume workflow uses the same path).

### Two doors (since 16 Oct 2026, evening)

The Page-token door needs the Page↔Instagram link, and on 16 Oct 2026 Facebook refused to
make it: *"You're temporarily restricted from taking this action to protect your profile."*
That message is Facebook's **profile-level rate limit** on sensitive account actions — not a
policy strike, not a problem with the Page or with @docoga.ng. It fires after a burst of
account-security actions (that afternoon: three OAuth consents across three apps, two tokens
minted, an app product added, a Page switch, all from a phone on 4G), and Meta's own help text
says it cannot be lifted early; it clears on its own, typically in 24–72 hours, and **retrying
extends it**. Owners report the same message on exactly this screen going back to 2023, and
two things reported to make the link succeed afterwards: two-factor authentication turned on
for the personal profile, and both accounts present in the same Accounts Center.

So the lane now has a **second door**: the Instagram-Login token the daily cards use needs no
Page at all. Meta documents resumable upload for the Facebook-Login host only; 2026 field
reports show the identical `upload_type=resumable` call working on `graph.instagram.com`.
Rather than argue, the lane asks every morning the first door is shut: `--probe-reels` on
`IG_API_PATH=instagram-login` creates **one** resumable REELS container (never published,
invisible, expires in 24 h) and reads whether Meta returned an upload `uri`. A "which door"
step then picks `facebook-login`, `instagram-login`, or `none`, and the Reel/Story upload
steps use that door's token. The run summary names the door.

### The one-time step, if the probe says "no"

The probe's own line tells you which of these two it is:

1. **`page-link`** — link the Instagram account to the Page: on the Page, facebook.com →
   DocOga Page → Settings → *Linked accounts* → Instagram → **Connect account**; or Instagram
   app → Settings → *Business tools and controls* → *Connect a Facebook Page* → DocOga. (Since
   16 Oct 2026 the probe reads both `instagram_business_account` and
   `connected_instagram_account`, so a link made either way counts.)
2. **`instagram_basic` / `instagram_content_publish`** — regenerate the Page token in Graph API
   Explorer with those two boxes ticked in addition to the existing Page ones, Debugger →
   *Extend* → "Expires: Never", then paste it into the `FB_PAGE_ACCESS_TOKEN` secret (select-all
   first — a half-replaced paste is the preflight's exit 4). The next 09:30 run prints
   `IG_REELS_READY=yes` and Monday's Reel goes out on both surfaces.

Nothing else: no bucket, no domain, no card, no new secret.

---

## What is still not possible, stated rather than quietly dropped

* ~~Instagram Reels~~ — **wired 16 Oct 2026, ₦0, no host.** See the "Reels" section below for
  the research, the mechanism, and the one-time token step it needs.
* ~~Facebook Reels~~ — live since 15 Oct 2026 (`FACEBOOK_AUTOMATION.md`), by the same kind of
  byte upload.
* ~~Instagram Stories~~ — **live since 16 Oct 2026.** The daily run renders the same copy as a
  9:16 frame (`site/social/<DAY>-instagram-story.jpg`, `tools/social_card.py --story`) in the same
  commit as the card, posts the feed card first, then the Story (`tools/ig_publish.py --story-url`,
  `media_type=STORIES`, no caption, no duplicate guard — a Story has no caption to be a duplicate
  of). The Story step is `continue-on-error`: it cannot cost the feed post. Both land in
  `logs/instagram_sent.json` (`instagram-card` / `instagram-story`). Dispatch `content_type=story`
  posts only the Story.
* **Hashtag count**: one 2026 source claims Threads allows exactly one hashtag per post. I could
  not find it in Meta's docs, so the generator keeps **two** and the API will tell us loudly if
  that is wrong (a rejected post is a red run with a cause, never a silence). If it ever rejects,
  change `HASHTAG_KEEP` in `scripts/generate_threads_content.py` — one constant, and the test for
  it is `test_generated_copy_always_fits`.
* **Quota figures disagree across sources** for Instagram (100 vs 25 posts per 24 h). The code
  does not care: it *reads* `content_publishing_limit` rather than counting locally, and at one
  post a day neither number can be the reason for anything.

---

## Cadence, for the record

| lane | when (UTC) | Lagos |
|---|---|---|
| Telegram | 08:00 daily | 09:00 |
| Facebook | 08:30 daily | 09:30 |
| **Threads** | **12:10 daily** | **13:10** (lunch — reply velocity) |
| YouTube Shorts | 17:00 Tue & Fri | 18:00 |
| Heartbeat | 18:00 daily | 19:00 |
| **Instagram** | **18:10 daily** | **19:10** (the 7–9 pm peak) |
| Facebook evening Story | 18:40 daily | 19:40 |

Slots moved on 17 Oct 2026 to the windows the 2026 Nigeria data names (`brain/strategy.md`);
no two lanes share a minute, so a shared cause (a dead runner, a Meta outage) stays guessable.
