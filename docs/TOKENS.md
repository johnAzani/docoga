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

## 4 · Google (YouTube + Analytics + Search Console) → secret `YT_REFRESH_TOKEN`

One consent screen, **all 7 scopes**, one refresh token. In Google Cloud → **APIs & Services → OAuth consent screen → Data access → Add or remove scopes**, make sure these are added; then run the consent once with all of them (`docs/BRAIN.md` → "The one Google re-consent" has the taps):

```
https://www.googleapis.com/auth/youtube
https://www.googleapis.com/auth/youtube.force-ssl
https://www.googleapis.com/auth/youtube.upload
https://www.googleapis.com/auth/youtube.readonly
https://www.googleapis.com/auth/yt-analytics.readonly
https://www.googleapis.com/auth/yt-analytics-monetary.readonly
https://www.googleapis.com/auth/webmasters.readonly
```

Also enable the APIs once: **YouTube Data API v3**, **YouTube Analytics API**, **Google Search Console API**. On the consent page tick **every** box (Google shows them as checkboxes — an unticked one is a scope missing from the token, and that is the only way this token can come out short).

## 5 · LinkedIn → secret `LINKEDIN_ACCESS_TOKEN` (+ `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` so the audit can read it)

Products: **Sign In with LinkedIn using OpenID Connect** + **Share on LinkedIn**. Scopes: `openid profile email w_member_social`. (Company-Page scopes need a verified Page product; add later only if we ever post as a Page.)

## 6 · TikTok → secret `TIKTOK_REFRESH_TOKEN`

Scopes on the app: `user.info.basic user.info.profile user.info.stats video.list video.upload video.publish`. Mint with `python3 tools/tiktok_draft.py auth --code … --redirect-uri https://docoga.com.ng/`.

## 7 · Telegram — the bot's admin rights in @docogadaily (no token change)

Telegram app → channel → **Administrators → @docoga_daily_bot** → turn on **all**: Post messages · Edit messages of others · Delete messages of others · Post stories · Edit stories · Delete stories · Manage live streams · Add subscribers · Invite users via link. Save.

---

## How you know it is done
Monday's "📊 Weekly scorecard" issue carries a block **"Token permissions — minted once, complete?"** with one line per token. ✅ on every line = this page is finished forever. ⚠️ names the exact permissions and the lane each one starves — mint that one token once with its full list above.
