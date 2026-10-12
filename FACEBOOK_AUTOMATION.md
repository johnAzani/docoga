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
  └─ scripts/post_facebook.py                  photo post if the image works, else text
```

| piece | file | role |
|---|---|---|
| API layer | `tools/fb_publish.py` | every Graph call: feed, photos, videos, the write probe, the duplicate guard |
| preflight | `tools/fb_preflight.py` | names which credential is wrong before anything is attempted |
| content | `scripts/generate_facebook_content.py` | de-escapes Telegram's templates, picks a Facebook-legible image, deterministic per date |
| poster | `scripts/post_facebook.py` | the day's post, the fallback chain, the exit codes |
| schedule | `.github/workflows/facebook_autopost.yml` | the above in order, plus a labelled issue on failure |
| behaviour tests | `tools/tests/test_post_facebook.py` | 23 tests against a fake Graph API |
| contract tests | `tools/tests/test_workflow_contract.py` | 35 tests over every workflow in the repo |

Nothing here is a server, a queue, or a paid service. A GitHub runner is the cron.

## 2. One-time setup — the only manual thing (10 minutes)

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

## 4. What the daily post actually looks like

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
* **`brand/official-logo-white.png` is never chosen.** It is Telegram's hero image
  because Telegram is dark; on a white feed it is a blank card. The Facebook list
  is separate on purpose (`FB_PHOTO_IMAGES`).
* **No `link` field is ever sent.** With a link attachment present, Facebook
  renders the link card and **drops the message text** — the URL lives in the
  copy instead. This is the one Graph-API quirk that makes a "successful" API
  call produce an empty-looking post.

Photos are uploaded as `source` multipart bytes, not fetched by URL: `brand/` is
not deployed (only `site/` is), so a URL-based photo post would depend on a second
system being up. And ~6 days in 7 get a photo, chosen deterministically.

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

* **Reels / Shorts cross-post.** `video_reels` needs three phases
  (`start` → `rupload.facebook.com` bytes → `finish`) and the rendered file lives
  in `assets/videos/`, which is gitignored build output. To post a Reel, the
  render must happen **in the same run** as the upload — i.e. merge
  `scripts/generate_short_video.py` into the Facebook job. `--video-url` exists
  on the manual dispatch for a clip that is already public; the daily path never
  touches video, rather than half-implement a second upload protocol.
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

## 9. Changing it

| to change | edit |
|---|---|
| the time | `cron` in the workflow (keep the minute off Telegram's `0 8 * * *`) |
| the copy | `TEMPLATES` / `HASHTAGS` in `scripts/generate_telegram_content.py` — **both channels read it**, then run `python3 scripts/generate_facebook_content.py --print` |
| which images | `FB_PHOTO_IMAGES` in the generator (must exist and fit the 4 MB cap — a test enforces both) |
| photo frequency | `PHOTO_ODDS` |
| API version | repository variable `META_GRAPH_VERSION`, then the default in `tools/fb_publish.py` |
| one-off post today | Actions → *Facebook Page Autopost* → Run workflow → `mode=text` (manual modes bypass the once-a-day guard, because a human asked) |

Before pushing any of it: `python3 -m unittest discover -s tools/tests -p 'test_*.py'`
and `python3 tools/qa.py` (§14 is the social-automation gate).
