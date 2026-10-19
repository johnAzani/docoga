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

## How you know it is done
Monday's "📊 Weekly scorecard" issue carries a block **"Token permissions — minted once, complete?"** with one line per token. ✅ on every line = this page is finished forever. ⚠️ names the exact permissions and the lane each one starves — mint that one token once with its full list above.
