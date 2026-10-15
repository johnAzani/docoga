# DocOga Facebook automation — as built, 12 Oct 2026

The Page: **facebook.com/docoga.com.ng** (id `102466208923830`; the vanity username
was taken 26 Sep 2026). The app is a use-case app ("Content Management / Growth"),
so publishing needs no review and costs ₦0 forever.

> **Read this first, because the record was wrong.** `docs/GROWTH_ENGINE.md` said
> "Facebook publishing … live 26 Sep — photos + videos" and "Facebook Page — DONE".
> It was not live. `.github/workflows/facebook_autopost.yml` had **zero runs in its
> history** (`gh run list --workflow 'Facebook Page Autopost'` → empty), it had no
> `schedule:` at all — only a button nobody pressed — and its publisher had never
> been called. The claim came from *credentials existing*, not from a post landing.
> That is exactly the failure the PRE-FLIGHT LAW was written to prevent, so the law
> is applied here in order: research → requirement matrix → failure enumeration →
> programmatic verification → tap-by-tap.

---

## 1. What runs, and when

```
09:30 Lagos, every day (08:30 UTC — thirty minutes after Telegram, deliberately)
  ├─ tools/fb_preflight.py                     stdlib only, no pip, no network assumptions
  ├─ scripts/generate_facebook_content.py      today's copy (shared with Telegram's templates)
  ├─ scripts/post_facebook.py                  photo post if the image works, else text
  └─ Reels lane, Mondays + Thursdays (see §9)
     ├─ scripts/facebook_reel_daily.py         decide → (render)  the same file the Shorts lane renders
     ├─ tools/youtube_ledger.py                30-day frame window, on logs/facebook_reels.json
     └─ scripts/post_facebook.py --reel        three-phase publish, then read it back
```

| piece | file | role |
|---|---|---|
| API layer | `tools/fb_publish.py` | every Graph call: feed, photos, videos, the write probe, the duplicate guard |
| preflight | `tools/fb_preflight.py` | names which credential is wrong before anything is attempted |
| content | `scripts/generate_facebook_content.py` | de-escapes Telegram's templates, picks a Facebook-legible image, deterministic per date |
| poster | `scripts/post_facebook.py` | the day's post, the fallback chain, the exit codes |
| schedule | `.github/workflows/facebook_autopost.yml` | the above in order, plus a labelled issue on failure |
| reel decider | `scripts/facebook_reel_daily.py` | the day rule, the topic (from the shared rotation), the render |
| reel ledger | `logs/facebook_reels.json` | written with `tools/youtube_ledger.py` — because `video_reels` cannot be read back |
| behaviour tests | `tools/tests/test_post_facebook.py` | 23 tests against a fake Graph API |
| reel tests | `tools/tests/test_post_facebook_reels.py` | 45 tests: the spec gate, the three phases, the probe |
| contract tests | `tools/tests/test_workflow_contract.py` | 35 tests over every workflow in the repo |

Nothing here is a server, a queue, or a paid service. A GitHub runner is the cron.

## 2. One-time setup — the only manual thing (10 minutes)

> **The order across all lanes is its own document:** `docs/LAUNCH_SEQUENCE.md` — the
> exact command or tap for every human step, the screen to expect, and what to check the
> next morning. Doing the steps out of order costs an issue titled `… [setup]`, not a post.

### 2a. Mint the Page token

1. <https://developers.facebook.com/tools/explorer/> → app picker → **the DocOga use-case app**.
   *Expected screen:* "Graph API Explorer" with `v26.0` in the version box.
2. **Get Token → Get User Access Token** → tick `pages_show_list`,
   `pages_read_engagement`, `pages_manage_posts` → **Generate Access Token** → copy it.
   *Expected:* a token beginning `EAAB…`, expiring in ~1–2 hours.
3. Exchange it for a 60-day user token (the terminal, not the browser):

   ```bash
   curl -s "https://graph.facebook.com/v26.0/oauth/access_token?grant_type=fb_exchange_token\
   &client_id=$APP_ID&client_secret=$APP_SECRET&fb_exchange_token=$SHORT_TOKEN"
   ```
   *Expected:* JSON with `"token_type":"bearer"` and **no** `expires_in` on… a
   number near 5,184,000 (60 days).
4. Ask for the Page token with that long-lived user token:

   ```bash
   curl -s "https://graph.facebook.com/v26.0/me/accounts?access_token=$LONG_USER_TOKEN"
   ```
   *Expected:* `data` containing your Page id and an `access_token` with **no
   `expires_in` field** — that absence is what "non-expiring" means. *That* token
   is `FB_PAGE_ACCESS_TOKEN`. Do not store the user token anywhere.

If step 4 returns an empty `data`, the app has no page grant: Business Suite →
**Settings → Business Settings → Accounts → Pages → DocOga → People → add the app**
(admin), then repeat.

### 2b. Store it, then verify — do not skip the verification

```bash
gh secret set FB_PAGE_ID --body '102466208923830'
gh secret set FB_PAGE_ACCESS_TOKEN --body '<the page token>'

gh workflow run 'Facebook Page Autopost' -f mode=daily -f dry_run=true
gh run watch    # or: gh run list --workflow 'Facebook Page Autopost'
```

The dry run is the whole proof: it resolves the Page, reads the feed, and
**creates an unpublished post and deletes it** — that is the only way to know
`pages_manage_posts` is live without publishing to 0 followers' timelines. Green
dry run ⇒ the 09:30 post will work. (`docs/GROWTH_ENGINE.md`'s mistake was
skipping this line.)

Optional, only for the expiry read and the refresh path — and **never** with a
literal default in any file:

```bash
gh secret set META_APP_ID --body '<app id>'        # these two are secrets:
gh secret set META_APP_SECRET --body '<app secret>' # they were in git until 12 Oct — rotate first
```

## 3. ⚠️ Rotate the app secret before anything else

Until 12 Oct 2026, `tools/fb_publish.py` carried

```python
app_secret = os.environ.get("META_APP_SECRET", "7dbde4fe…")   # deleted
```

The literal is gone from the file, `tools/qa.py` §14 and
`test_no_secret_shaped_default_in_automation_tools` fail if one returns — but the
value is in git history, so **treat it as public**: Meta developer dashboard →
your app → Settings → Advanced → **App Secret → Reset**. Then
`gh secret set META_APP_SECRET`. (Same rule as `unlock-codes.txt` and the
payment keys: this repo is private, not *rewritable*.)

## 4. What the daily post looks like (§9 covers what the Reel looks like)

The copy is Telegram's, converted — one source of truth for the message, one
conversion for the medium:

```
📋 9 Document Tools, 1 Platform

Tenancy Agreement • Notice to Quit • Rent Receipt • Invoice • Employment
Contract • Caution Fee Receipt • Letter of Demand and more.

All free at https://docoga.com.ng

#DocOga #NigerianLandlords #TenancyAgreement #RentReceipt #NoLawyerNeeded
```

Four conversions that matter, each with a test:

* **MarkdownV2 is stripped.** The templates literally contain `\.` and `*bold*`
  for Telegram. Facebook publishes what it is given, so an unstripped backslash
  is *on the Page*. `tools/telegram_mdv2.to_plain()` is the single stripper.
* **Hashtags stay raw** (`#` needs no escape outside MarkdownV2).
* **The photo is the brand card, never a `brand/` file.** The day's copy is
  rendered by `tools/social_card.py` (1080×1350, navy ground, Inter, `DOCOGA ·
  <post type>` kicker, `docoga.com.ng` footer) to
  `assets/facebook/facebook_card_<date>.jpg` — the same card the Instagram lane
  ships. The first live post (15 Oct 2026) went out with `brand/comparison.png`, a
  logo-exploration sheet, and the owner's verdict was "this is not my brand
  style". `social_card.BANNED_PHOTO_PREFIXES` now bans `brand/` and
  `post_facebook.py` refuses such a path even when passed by hand (the words still
  post as text). Every daily run — dry runs too — uploads the card as the
  `facebook-card` artifact (Summary → Artifacts), so a design change can be looked
  at on a phone before it is published.
* **No `link` field is ever sent.** With a link attachment present, Facebook
  renders the link card and **drops the message text** — the URL lives in the
  copy instead. This is the one Graph-API quirk that makes a "successful" API
  call produce an empty-looking post.

Photos are uploaded as `source` multipart bytes, not fetched by URL: `assets/` is
not deployed (only `site/` is), so a URL-based photo post would depend on a second
system being up. Every day gets the card; the lane only drops to a text post if
the render itself fails (missing Pillow, a font regression) — the day is never lost
to the picture.

## 5. The four rules the failure handling obeys

Inherited from the Telegram rewrite (four silent failed days, 7–10 Oct 2026):

1. **A run that posted nothing exits non-zero** — so a red tick means a missing post, nothing else.
2. **A skipped day exits 0** — "already posted today" is success. Otherwise every
   re-run would open an issue and the signal would be noise within a week.
3. **A rejected photo still produces the text post**, with both API errors logged.
   A bad image must not cost the Page its day.
4. **The duplicate guard asks Facebook, not the filesystem.** A runner's disk does
   not survive between runs, so a marker file would forget, and a retried job
   would publish the same sentence twice. `GET /{page}/feed` answers "is today
   taken?" and its dates are compared in **Africa/Lagos** — 23:30 UTC is
   tomorrow in Lagos, and a raw UTC compare would let a second post through for
   an hour every day (there is a test for exactly that).

## 6. Failure matrix — read this before touching anything

| what you see | what it means | what to do |
|---|---|---|
| `Facebook secrets missing` (exit 2) | a secret was never set, or a deploy wiped it | `gh secret set FB_PAGE_ID` / `FB_PAGE_ACCESS_TOKEN`. There is **no fallback Page id in the code on purpose** — a compiled-in default posts your product to whoever owns that id |
| `Facebook token rejected`, `code 190`/`102` | token revoked, expired, or the app lost its grant | re-mint (§2a step 4). Page tokens are non-expiring, so a 190 is nearly always a role/app change, not time |
| `Page not reachable with this token` | `FB_PAGE_ID` names a Page this token cannot manage | fix the id. Never "try the other one" — a valid token for a *different* Page publishes to that Page |
| `Page feed not readable` | `pages_read_engagement` missing; the guard is blind too | re-grant both scopes; the dry run will show whether the probe passes |
| `code 200` / `(#200) Permission failed`, subcode `534` | the token can read but not publish | the app needs `pages_manage_posts`, and the human must hold Page **admin** (not editor) |
| `code 4`, `code 613`, `rate` | app/Page rate limit | wait; the next scheduled run is unaffected |
| `spec refused — aspect ratio is …` | the render is not 9:16, or not 3–90 s, or not H.264 | **good news**: the gate stopped a file Meta would have accepted and then not published. Fix the words in `scripts/generate_short_video.py` (the picture is MotionStudio's, via `tools/shorts_reel.py`) |
| `start refused` while the feed probe passed | the token can post to the feed but cannot open a Reels session | keep `FB_REELS` at `probe`/`off`; the app needs the Reels-capable grant before the lane can be switched on |
| `publish refused after the upload was accepted` | the bytes are on Meta's side, unpublished | finish it once: `python3 tools/fb_publish.py --reel-finish <video_id>` (the id is in the log). Do **not** re-render and re-upload first |
| `rupload stored N of M bytes` | a truncated transfer | usually transient; re-run the same day with `force=true`. The Page-side guard still protects every other post |
| `reel is still processing` (a warning, run stays green) | Meta is still rendering it | nothing. It lands on the Page when done; check `/reel/<id>` if it never does |
| `Unsupported get request` / `(#100) unexpected field` | **Meta sunset the API version** | set repository *variable* `META_GRAPH_VERSION = v<new>.0` — no commit needed; then update the default in `tools/fb_publish.py` |
| photo refused, then `falling back to a text post` | working as designed | nothing. The words went out |
| run green, Page empty | the guard skipped today (already posted) | check `Record what this run did` in the summary; `--force` for a second deliberate post |

## 7. Graph API version clock

| version | released | expires |
|---|---|---|
| v26.0 | 29 Jul 2026 | (this is the pinned default) |
| v25.0 | 18 Feb 2026 | 29 Jul 2028 |
| v24.0 | 8 Oct 2025 | 18 Feb 2028 |
| v21.0 | 2 Oct 2024 | **21 Jan 2027** — what this repo pinned until 12 Oct 2026 |

Meta ships 3–4 versions a year and each lives ~2 years; the v26.0 behaviour
changes extend to every supported version on **27 Oct 2026**, so staying behind
buys months, not immunity. `API_VERSION` / `META_GRAPH_VERSION` are the only
places the number appears; `test_the_graph_api_version_is_current_and_comes_from_one_constant`
fails if a literal `vNN.0` reappears in a URL in `tools/*.py`.

## 8. What is deliberately **not** automated (and why)

* **Reels cross-posted to Instagram.** `is_crosspost_video=true` on the finish
  phase is the one-liner, and it is *not* one-line operationally: it makes a
  Facebook publish depend on an Instagram account being linked, and when that link
  breaks the reel fails on a lane that was working. This file's §9
  publishes to Facebook only; cross-posting gets its own decision when the IG
  lane (`instagram_autopost.yml`) has a schedule it can honour.
* **Feed video that is not a Reel.** `--video-url` (mode `video`) exists for a clip
  that is already public, and the render is deliberately not uploaded to
  `/{page}/videos` as well — a plain Page video post on a Page this size reaches
  almost nobody, which is §9's whole argument for the Reels surface.
* **2–3 Stories/day.** Stories need `photo_stories`/`video_stories` on an
  unpublished media id and expire in 24 h — a separate cadence, a separate
  failure surface. Not silently folded into one post.
* **Comment replies.** Phase ⓷ in `docs/GROWTH_ENGINE.md`, still unbuilt. It needs
  a webhook or a poller plus `pages_manage_engagement`; a reply that misfires on
  a real customer is a support incident, so it gets its own design doc first.
* **Instagram.** `instagram_autopost.yml` is dispatch-only **on purpose**: the
  Reels API requires a *public* media URL, so an unattended run would fail more
  often than not. It got the same hardening (env-passed inputs, one version
  constant, a real argv array for carousels) but not a schedule it cannot honour.
* **No auto-refresh of the Page token.** A runner cannot write its own secrets, so
  a refresh that silently succeeds would still lose the token. Page tokens do not
  expire; if you ever use a user token instead, the 60-day clock is a calendar
  reminder, not a background job.

## 9. Reels — Mondays and Thursdays, defaulted to *probe*

**Why this lane exists at all**: a plain Page video post (`POST /{page}/videos`)
reaches roughly the Page's follower count, and DocOga's Page has almost none. A
Reel goes into the Reels surface, which distributes to non-followers. Same file,
same render, a completely different ceiling — which is why this is a Reels lane
and not a "post the Short to Facebook too" lane.

### The protocol, and the three properties that shaped the code

```
1  POST /{page_id}/video_reels   upload_phase=start                → video_id, upload_url
2  POST https://rupload.facebook.com/video-upload/{VER}/{video_id}
        Authorization: OAuth <page token>     ← a header, not a body field
        offset: "0"   file_size: "<bytes>"   Content-Type: application/octet-stream
        body: the raw bytes   (or `file_url: https://…` instead of a body)
3  POST /{page_id}/video_reels   upload_phase=finish, video_state=PUBLISHED
```

1. **`video_reels` cannot be read, updated or deleted.** So "did it go out?" is
   answered two ways: the *video object*
   (`GET /{video_id}?fields=status,permalink_url`) for what just happened, and the
   ledger for what happened last week. That asymmetry is the whole reason
   `logs/facebook_reels.json` exists and the job holds `contents: write` — which
   it spends on that one path, and nothing else.
2. **A file outside spec is accepted, then quietly never published.** Meta's
   surface wants 9:16, 3–90 s, 1080×1920 recommended, 24–60 fps, H.264/H.265, MP4.
   So `reel_spec_ok()` measures the file with `ffprobe` and refuses it locally,
   before a single byte is uploaded. If `ffprobe` is missing (a laptop, a minimal
   image) that is a warning rather than a block: the runner installs ffmpeg, and a
   lane nobody can inspect locally is a lane nobody runs.
3. **Meta's enum table says `START`/`FINISH`; every working example sends
   lowercase.** A green run must not depend on which spelling Meta tightens next,
   so a rejection that mentions `upload_phase` re-sends once in uppercase and says
   so in the log. Tested, both the fallback and the pair being remembered between
   phases.

### The default: `probe`

`vars.FB_REELS` selects the mode, and `probe` is the default deliberately:

| mode | what happens on a Reel day | cost |
|---|---|---|
| `probe` | open an upload session, then delete/abandon it, print the verdict | one call, nothing published |
| `on` | render, spec-gate, upload, publish, poll until `ready`, record in the ledger | ~2–4 runner minutes |
| `off` | nothing at all; the summary says so | nothing |

The first reel this pipeline publishes should go out *after* the probe has gone
green in a real run — the probe is the only Reels check that cannot touch the
Page, because unlike `/feed` there is no "create it unpublished, then delete it":
the edge does not delete. Switching the lane on is one line in
Settings → Actions → **Variables** (`FB_REELS = on`), reversible the same way.
`python3 tools/fb_publish.py --reel-probe` runs the same check from a terminal.

### The cadence, and the law behind it

Mondays and Thursdays, from the same `scripts/generate_short_video.py` rotation (rendered by MotionStudio through `tools/shorts_reel.py`) the
Shorts lane uses. Not Tue/Fri, which is `youtube_scheduled.yml`'s: the rotation is
indexed by date, so **the same weekday on both lanes means the same topic on both
platforms on the same day**, which the 30-day frame law in `docs/GROWTH_ENGINE.md`
§4 forbids. Different day ⇒ different index ⇒ a different frame, for free.

Six frames in the rotation at two reels a week means a frame returns after 21
days, inside the window ⇒ the ledger **skips** that slot and the summary reads
`⏭ frame "…" is inside the 30-day window — nothing rendered`. A skip is exit 0 (no
issue) and it is loud, because silence is what cost October. When that starts to
bother you, the fix is more frames in the rotation, not a shorter window.

A manual `mode: reel` dispatch renders and publishes today regardless of weekday
or window — with `--force`, because a person asked — and still records itself.

### What "published" is allowed to mean

`finish` returning `success` is not the end. The job polls the video object up to
6 times, 20 s apart, reading `status.video_status` and `publishing_phase`:

* `ready` → ✅, and the ledger gets `permalink_url` (a `/reel/<id>` link).
* `error` → ❌ exit 5 with the reason — the class of failure that used to be silent.
* still `processing` → ⚠️ **green**, because the reel *was* accepted and will appear.
  Failing a run for Meta's queue is how you teach people to ignore red runs.

Three exit codes on purpose: **4** = the file was not fit (operator), **3** = Meta
refused a call (credential/API), **5** = Meta took the bytes and then would not
publish (this lane's own class, recoverable with `--reel-finish <video_id>`).

### Verifying it without publishing anything

```bash
gh workflow run facebook_autopost.yml --ref <branch> -f dry_run=true    # feed + reels probe
gh workflow run facebook_autopost.yml --ref <branch> -f mode=reel       # publishes one reel NOW
python3 scripts/facebook_reel_daily.py --date 2026-10-12 --mode on      # the decision, locally
python3 tools/fb_publish.py --reel-probe                                # grant only
```

The local decision needs Pillow (the rotation lives in the module that imports
PIL); `--render` needs `pip install -r requirements-youtube.txt` and ffmpeg. The
decision step deliberately does **not** import the renderer, so a machine that
cannot render can still answer "is today a reel day?" — with a warning naming the
topic it could not read, instead of a traceback.

## 10. Changing it

| to change | edit |
|---|---|
| the time | `cron` in the workflow (keep the minute off Telegram's `0 8 * * *`) |
| the copy | `TEMPLATES` / `HASHTAGS` in `scripts/generate_telegram_content.py` — **both channels read it**, then run `python3 scripts/generate_facebook_content.py --print` |
| the card's look | `tools/social_card.py` (palette, type, kicker names in `KICKER_NAMES`) — it is shared with Instagram and Telegram, so a change there changes all three; preview with `python3 scripts/generate_facebook_content.py --print` and open `assets/facebook/facebook_card_<date>.jpg` |
| photo frequency | every day is a card; there is no odds knob any more |
| whether Reels publish at all | repository **variable** `FB_REELS` = `probe` (default) / `on` / `off` |
| which days get a Reel | `REEL_WEEKDAYS` in `scripts/facebook_reel_daily.py` (keep it off YouTube's Tue/Fri — the collision rule is in that file's header) |
| the reel's words | `VIDEO_SCRIPTS` in `scripts/generate_short_video.py` — both the 3–90 s window and the 30-day window apply |
| the reel's look | `tools/shorts_reel.py` (spec) → `tools/motionstudio.py` (engine) — the locked brand style; `tools/qa.py` §15 refuses any other renderer |
| API version | repository variable `META_GRAPH_VERSION`, then the default in `tools/fb_publish.py` |
| one-off post today | Actions → *Facebook Page Autopost* → Run workflow → `mode=text` (manual modes bypass the once-a-day guard, because a human asked) |

Before pushing any of it: `python3 -m unittest discover -s tools/tests -p 'test_*.py'` (175 tests as this was written)
and `python3 tools/qa.py` (§14 is the social-automation gate).
