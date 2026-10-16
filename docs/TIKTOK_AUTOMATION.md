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

## Setting it up, from the phone (once)
1. developers.tiktok.com → Log in with your TikTok → **Manage apps** → *Connect an app* →
   name `DocOga`, category *Productivity*, description "Posts DocOga's legal-explainer
   Shorts to the DocOga TikTok", icon `brand/favicon-512.png`, Terms
   `https://docoga.com.ng/terms.html`, Privacy `https://docoga.com.ng/privacy.html`,
   platform *Web* → URL `https://docoga.com.ng`.
2. **Add products** → *Login Kit* and *Content Posting API*. In Login Kit → Redirect URI:
   `https://docoga.com.ng/` (verify the domain when asked: TikTok gives a small file to
   upload — put it in `site/` and push; Pages deploys it).
3. Scopes: tick `user.info.basic` and **`video.upload`** (not `video.publish`).
4. Leave the app in **Sandbox** and add **your own TikTok account as a target user**
   (Sandbox → *Target users*). Sandbox needs no review for the target users; that is enough.
5. Copy **Client key** and **Client secret** → GitHub secrets `TIKTOK_CLIENT_KEY`,
   `TIKTOK_CLIENT_SECRET`.
6. Authorise once: open in the phone browser
   `https://www.tiktok.com/v2/auth/authorize/?client_key=<KEY>&scope=user.info.basic,video.upload&response_type=code&redirect_uri=https://docoga.com.ng/&state=docoga`
   → Allow → you land on docoga.com.ng with `?code=…` in the address bar. Copy the `code`
   (everything between `code=` and `&`, URL-decoded).
7. Exchange it (from any machine with Python, or a Codespace):
   `TIKTOK_CLIENT_KEY=… TIKTOK_CLIENT_SECRET=… python3 tools/tiktok_draft.py auth --code <code> --redirect-uri https://docoga.com.ng/`
   → it prints the **refresh token** → GitHub secret `TIKTOK_REFRESH_TOKEN`.
8. Done. The next Short (Tue/Fri) also appears in your TikTok inbox.

Refresh tokens live 365 days; the refresh call may rotate them, and the rotated value is
sealed into `logs/tiktok_refresh_token.box` with `tools/token_vault.py` (needs
`SOCIAL_TOKEN_KEY`, already set). Without the vault key the lane warns and keeps using the
bootstrap secret.

## Guard rails
- Dormant (notice, exit 0) until all three secrets exist; never fails the YouTube publish it
  rides on (`continue-on-error`).
- Duplicate guard by file SHA in `logs/tiktok_drafts.json`.
- Stops at five pending inbox uploads in 24 h (TikTok's wall) with a warning to post or
  discard them in the app.
- Chunks: one chunk ≤64 MB, else 10 MB chunks (TikTok: 5–64 MB, last may be larger).
- Polls `/v2/post/publish/status/fetch/` until `SEND_TO_USER_INBOX` / `FAILED`.

## Machine lines
`TIKTOK_RESULT=inbox|duplicate|skipped|dormant|dry-run|probed|failed`, `TIKTOK_CAUSE=…`,
`TIKTOK_PUBLISH_ID=…`, `TIKTOK_STATUS=…`, `TIKTOK_VAULT=sealed`.

## Later, if wanted
A Direct Post audit (so the tap disappears) needs a demo video of the app's UI showing the
creator-info call, the privacy picker with no default, the commercial-content toggle and a
preview — a web page, not a cron. Not ₦0 in hours; parked.
