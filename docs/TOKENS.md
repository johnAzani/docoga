# Tokens — mint once, with everything, never again

*Owner's rule (17 Oct 2026): "make sure all permissions are granted, even feature permissions —
I will not want to re-mint it." This page is the one list. `tools/token_scopes.py` is the same
list in code; the Monday scorecard runs `audit` and prints, per token, **complete** or the exact
names missing. If every line says complete, nothing on this page ever needs doing again
(except the 60-day Instagram/Threads refresh, which the lanes do themselves through the vault).*

Print the list any time: `python3 tools/token_scopes.py list` · check live tokens: `python3 tools/token_scopes.py audit`.

Everything below is **standard access on assets you own** — your Page, your Instagram, your
Threads, your channel. None of it needs App Review. Over-asking costs nothing; under-asking costs
a re-mint.

---

## 1 · Facebook Page token → secret `FB_PAGE_ACCESS_TOKEN`

Where: developers.facebook.com → **Tools → Graph API Explorer** (phone: request desktop site).

1. **Meta App** → the Business app (`931364932955308`).
2. **User or Page** → **Get Page Access Token** → choose the **DocOga** Page.
3. **Permissions** → **Add a permission** → tick **every one of these 15**:

| tick | why it is on the list |
|---|---|
| `pages_show_list` | the Explorer needs it to offer the Page |
| `pages_read_engagement` | comments, reactions — replies lane, scorecard |
| `pages_read_user_content` | visitor posts and mentions |
| `pages_manage_posts` | posts, photos, videos, Reels, Stories |
| `pages_manage_metadata` | Page settings, webhooks, the refresh step |
| `pages_manage_engagement` | **reply to comments** (community manager) |
| `pages_messaging` | **comment → DM** on Messenger |
| `read_insights` | reach, follows — the scorecard |
| `publish_video` | video/Live publishing as the Page |
| `business_management` | the Page↔Instagram link, the Business assets |
| `instagram_basic` | the linked Instagram profile and media |
| `instagram_content_publish` | Reels, carousels, Stories via the Page token |
| `instagram_manage_comments` | Instagram comments (Facebook-Login path) |
| `instagram_manage_insights` | Instagram insights incl. online hours (slot plan) |
| `instagram_manage_messages` | Instagram private replies (Facebook-Login path) |

4. **Generate Access Token** → in the pop-up, when Meta asks which Pages/Instagram accounts, choose **all** (not "opt in to current only") → Done.
5. Make it never-expire: with the token in the Explorer, **Access Token Tool** (debug) → **Extend Access Token** → copy. (A Page token derived from a long-lived user token does not expire.)
6. GitHub → the repo → **Settings → Secrets and variables → Actions** → `FB_PAGE_ACCESS_TOKEN` → **Update** → paste → Save.

App *features* (Dashboard → App Review → Permissions and Features): "Page Public Content Access", "Business Asset User Profile Access", "Live Video API" — these matter only for **other people's** Pages. For ours, standard access is already on. Nothing to tick.

## 2 · Instagram token (Instagram Login) → secret `IG_ACCESS_TOKEN`

Where: developers.facebook.com → the app → **Use cases → Instagram → Customize → User token generator** → the `docoga.ng` account → **Generate token**.

Before Generate, under **Permissions** make sure all **5** are on:

`instagram_business_basic` · `instagram_business_content_publish` · `instagram_business_manage_comments` · `instagram_business_manage_messages` · `instagram_business_manage_insights`

In the Instagram login pop-up, **allow everything** it lists (messages, insights, comments). Paste into `IG_ACCESS_TOKEN`. The lane refreshes it every run (60-day clock) through the vault — you never touch it again.

## 3 · Threads token → secret `THREADS_ACCESS_TOKEN`

Where: the app → **Use cases → Threads API → Customize → User token generator** → **Generate token**. Tick all **10** permissions first:

`threads_basic` · `threads_content_publish` · `threads_manage_replies` · `threads_read_replies` · `threads_manage_insights` · `threads_keyword_search` · `threads_manage_mentions` · `threads_delete` · `threads_location_tagging` · `threads_profile_discovery`

Paste into `THREADS_ACCESS_TOKEN`. Refreshed by the lane; never again.

## 4 · Google (YouTube + Analytics + Search Console) → the vault (`logs/yt_refresh_token.box`)

One consent, **all 7 scopes**, one refresh token — minted **from the phone**, and the client
secret never leaves GitHub (17 Oct 2026: the phone layout of the Cloud console does not show it).

```
https://www.googleapis.com/auth/youtube
https://www.googleapis.com/auth/youtube.force-ssl
https://www.googleapis.com/auth/youtube.upload
https://www.googleapis.com/auth/youtube.readonly
https://www.googleapis.com/auth/yt-analytics.readonly
https://www.googleapis.com/auth/yt-analytics-monetary.readonly
https://www.googleapis.com/auth/webmasters.readonly
```

Done once in Google Cloud (17 Oct 2026, project DocOga): consent screen **In production**;
the 7 scopes declared under **Data Access**; APIs enabled — YouTube Data API v3, YouTube
Analytics API, Google Search Console API; the client (Web application) carries the redirect
`https://developers.google.com/oauthplayground`.

The mint, three taps (**DONE 17 Oct 2026 10:06 WAT — 7 of 7, `SCOPES_GOOGLE=complete`, box committed `3557f1f`**):
1. The consent link (Actions masks the client id as `***` in the run summary because
   `YT_CLIENT_ID` is stored as a secret — an OAuth client id is a public identifier, so it is
   written here; `python3 tools/google_consent.py url` rebuilds it):
   `https://accounts.google.com/o/oauth2/v2/auth?client_id=635194176409-ppu1quhcgjkrjkdh1ab3b37f40njnsah.apps.googleusercontent.com&redirect_uri=https%3A%2F%2Fdevelopers.google.com%2Foauthplayground&response_type=code&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube.force-ssl+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube.upload+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube.readonly+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyt-analytics.readonly+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyt-analytics-monetary.readonly+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fwebmasters.readonly&access_type=offline&prompt=consent&include_granted_scopes=true`
2. Open the link, pick the DocOga Google account, then — **Google shows a second list: the personal channel and the DocOga brand channel. Pick DocOga** (19 Oct 2026: the 17 Oct mint picked the personal channel `Millionaire_money1`; every YouTube lane then saw an empty channel; the exchange now refuses a token whose channel is not `YT_CHANNEL_ID` — `GOOGLE_CONSENT=wrong_channel`, exit 6, old token kept) — **tick every box**, Continue. It lands on
   `developers.google.com/oauthplayground/?code=4/0A…` — copy that whole address.
3. Actions → **Google consent — seal the YouTube token (phone path)** → Run workflow → paste the address (or the code from the Playground's "Authorization code" box) into **code**. The job exchanges it with
   `YT_CLIENT_ID`/`YT_CLIENT_SECRET`, checks all 7 scopes are on the token (**a short token is
   refused and the old one stays** — tick every box), seals it under `SOCIAL_TOKEN_KEY` into
   `logs/yt_refresh_token.box`, commits, and prints `SCOPES_GOOGLE=complete`.

Every Google-facing lane (`yt_publish.authorize`, used by Shorts, Deep-Dive upload, manage,
captions, stats, Search Console; and the Monday scope audit) reads the vault first and the
`YT_REFRESH_TOKEN` secret only when there is no box. The secret is never edited again.
Machine lines: `GOOGLE_CONSENT=ok|partial|refused|failed`, `GOOGLE_SCOPES_MISSING=`.

## 5 · LinkedIn → secret `LINKEDIN_ACCESS_TOKEN` (+ `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` so the audit can read it)

Products: **Sign In with LinkedIn using OpenID Connect** + **Share on LinkedIn**. Scopes: `openid profile email w_member_social`. (Company-Page scopes need a verified Page product; add later only if we ever post as a Page.)

## 6 · TikTok → secret `TIKTOK_REFRESH_TOKEN`

Scopes on the app: `user.info.basic user.info.profile user.info.stats video.list video.upload video.publish` (all three products: Login Kit, Content Posting API, Display API). Mint from the phone: sign in to the dashboard, open `https://docoga.com.ng/tiktok-connect.html`, tap **Connect TikTok** — the connect workflow seals the refresh token into `logs/tiktok_refresh_token.box`; no secret to paste (`docs/TIKTOK_AUTOMATION.md`). Fallback: `python3 tools/tiktok_draft.py auth --code … --redirect-uri https://docoga.com.ng/tiktok-connect.html`.

## 7 · Telegram — the bot's admin rights in @docogadaily (no token change)

Telegram app → channel → **Administrators → @docoga_daily_bot** → turn on **all**: Post messages · Edit messages of others · Delete messages of others · Post stories · Edit stories · Delete stories · Manage live streams · Add subscribers · Invite users via link. Save.

---

## 8 · GitHub — the clock's doorbell token → secret `GH_DISPATCH_TOKEN`

Why: GitHub's own schedules in private repositories arrive hours late or not at all since
26 Aug 2026; a Cloudflare Worker (`workers/clock`, ₦0) now rings every lane on time through
`workflow_dispatch`, and that needs a token GitHub will not let the repository mint for itself
(`docs/CLOCK.md`).

`github.com/settings/personal-access-tokens/new` → name **docoga-clock** → **Expiration: No
expiration** → **Only select repositories → johnAzani/docoga** → Repository permissions:
**Actions RW · Contents RW · Issues RW · Pull requests RW · Secrets RW · Variables RW ·
Workflows RW** (Metadata read is automatic) → Account permissions: **Plan: Read-only** →
Generate → copy → `github.com/johnAzani/docoga/settings/secrets/actions/new` → Name
**GH_DISPATCH_TOKEN** → paste → Add secret. The clock needs only *Actions: write*; the rest is
the superset so this token is never minted twice (Secrets/Variables RW let future lanes
rotate their own keys; Plan read lets the heartbeat read the Actions-minutes budget).

---

## 9 · Footage doors (Shorts/Reels b-roll) → secrets `PIXABAY_API_KEY`, `UNSPLASH_ACCESS_KEY`, `FLICKR_API_KEY`, `PEXELS_API_KEY`

Why: since 20 Oct 2026 every spoken sentence of a Short gets a free video clip (or a photograph)
behind it (`docs/SHORTS_MOTION.md` §5b). Two doors are keyless (Wikimedia Commons, Openverse) and
work today; each key below opens a bigger catalogue. All free, all one-time, none expire.

**Pixabay** ✅ *secret `PIXABAY_API_KEY` added by the owner 20 Oct 2026, 5:08pm — door open.* (the big clip library — do this one first): `pixabay.com` → Join → confirm the email →
sign in → open `https://pixabay.com/api/docs/` → scroll to **Parameters → key** — your key is
printed there in green → copy → `github.com/johnAzani/docoga/settings/secrets/actions/new` →
Name **PIXABAY_API_KEY** → paste → Add secret.

**Unsplash** ✅ *secret `UNSPLASH_ACCESS_KEY` added by the owner 20 Oct 2026, 5:33pm — door open (app "Docoga", Demo tier 50 req/h, Public access only; do NOT apply for production — it needs attribution screenshots and we print no credits).* (photographs): `unsplash.com/developers` → Register as a developer → **New
Application** → tick the guidelines → Application name **DocOga** · Description **Free tenant
documents for Nigeria — b-roll behind educational Shorts** → Create → copy **Access Key** →
secret **UNSPLASH_ACCESS_KEY**.

**Flickr** ⏸ *PAID-ONLY since 2026 — do not ask the owner again.* On 20 Oct 2026, 5:50pm the App Garden said "API key creation is currently disabled for free accounts … available to all Flickr PRO subscribers". PRO costs money → ₦0 rule → skipped; the door stays `nokey` and the pipeline is unaffected (Pixabay + Unsplash + Commons + Openverse cover every sentence). If Flickr ever reopens free keys: (photographs taken *in Nigeria* — the door is geofenced) `flickr.com/services/apps/create/apply`
→ **Apply for a non-commercial key** → App name **DocOga Shorts** · What are you building **Public-domain
b-roll behind free tenant-rights videos** → tick both → Submit → copy **Key** → secret **FLICKR_API_KEY**.

**Pexels**: new API keys are **paused** (pexels.com/api, since 30 Sep 2026). Nothing to do; when
they reopen, `pexels.com/api/new` → secret **PEXELS_API_KEY**.

---

## 10 · The repository is PUBLIC (20 Oct 2026) — what was rotated and why

**What happened, 7:05pm:** GitHub stopped every lane — *"The job was not started because recent
account payments have failed or your spending limit needs to be increased."* The billing page
showed the cause: a **private** repo gets 2,000 free Actions minutes a month and October's were
gone on the 20th ($15.99 of $15.99; docoga ≈ 1,410 min, three older repos of the owner's ≈ 590 min).
The ₦0 fix is a **public** repository — unlimited free minutes, forever. The owner chose it at
9:45pm ("Let's start it now").

**What a public history exposes (audited that night, all 529 commits):** two things, nothing else.

| Found in history | Risk once public | Closed by |
|---|---|---|
| `send_test_post.sh` carried a live Telegram **bot token** | anyone could post to @docogadaily | owner revokes it in @BotFather and pastes the new one into `TELEGRAM_BOT_TOKEN` |
| `tools/tests/test_tiktok_draft.py` carried the **real `SOCIAL_TOKEN_KEY`**, and the four `logs/*.box` files it opens | the YouTube, Instagram, Threads and TikTok tokens become readable | **vault key rotated** (new 32 random bytes; the owner pastes it into `SOCIAL_TOKEN_KEY`); the YouTube and TikTok boxes were **re-sealed under the new key with the same tokens** (those are useless to a stranger once the *client secrets* rotate — see below); the Instagram and Threads boxes were **deleted** (bare tokens, so they are re-minted) |

No Google/Meta/Cloudflare/payment key, no customer record and no passphrase was ever committed.
History rewriting was **not** used: on GitHub, old commits stay reachable through pull-request refs,
so rotation is the only honest fix — and it is what GitHub's own guidance says.

**The owner's taps, in order (the flip to Public is last — irreversible, so nothing leaks before
the old values are dead):**

1. **Telegram** — @BotFather → `/mybots` → @docoga_daily_bot → API Token → **Revoke current token**
   → copy the new one → secret `TELEGRAM_BOT_TOKEN` (update, not new).
2. **Google client secret** — `console.cloud.google.com/apis/credentials` → the DocOga OAuth client →
   Client secrets → **Add secret** → copy → **Disable** (then delete) the old one → secret
   `YT_CLIENT_SECRET` (update). The sealed refresh token stays valid for *this* client; a stranger
   holding the old box cannot refresh without the new client secret. **No 7-scope re-consent.**
3. **TikTok client secret** — developers.tiktok.com → the app → Credentials → **regenerate** the
   client secret → secret `TIKTOK_CLIENT_SECRET` (update). Same logic: the sealed refresh token is
   useless without it. No re-connect.
4. **Instagram** — instagram.com → Settings → **Apps and websites** → Active → the DocOga app →
   **Remove** (kills the old token). Then §2 above: **Generate token** → secret `IG_ACCESS_TOKEN`
   (update). The lane seals it under the new key on its next run.
5. **Threads** — Threads → Settings → Account → **Apps and websites** → the DocOga app → Remove.
   Then §3 above: **Generate token** → secret `THREADS_ACCESS_TOKEN` (update).
6. **Vault key** — secret `SOCIAL_TOKEN_KEY` (update) with the new value the agent handed over in
   the private chat. Never into a file, never into a test.
7. **Flip** — `github.com/johnAzani/docoga/settings` → Danger Zone → **Change visibility → Make
   public** → type the repository name → confirm. Actions resume within the minute.
8. The hygiene PR merges (its CI can only run after the flip), then the first lane proves each
   credential on its own run summary.

**The guard that makes this the last time:** `tools/secret_scan.py` runs inside `tools/qa.py` and
in CI; it refuses any tracked file carrying a token/key *shape* (BotFather, Google, Meta, GitHub,
TikTok, Flutterwave/Paystack, private-key blocks, a 64-hex vault key outside an obvious fake).
Test fixtures use `"0f" * 32`. Ciphertext boxes are skipped by design — the vault's threat model
(`tools/token_vault.py`) always assumed the box could be read; only the key was ever the secret.

**Free extra, any day:** the three older repos (`YouTube-automation`, `Vertualworld`,
`Autonomous_youtube_automation`) still run scheduled workflows. Settings → Actions → **Disable
actions** on each returns ~590 min/month to the account. Irrelevant once docoga is public, but
free.

---

## How you know it is done
Monday's "📊 Weekly scorecard" issue carries a block **"Token permissions — minted once, complete?"** with one line per token. ✅ on every line = this page is finished forever. ⚠️ names the exact permissions and the lane each one starves — mint that one token once with its full list above.
