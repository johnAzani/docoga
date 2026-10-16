# LinkedIn lane — the ₦0 profile post, Mon/Wed/Fri 08:30 Lagos

`tools/linkedin_publish.py` + `.github/workflows/linkedin_autopost.yml` (17 Oct 2026).

## Why this lane exists
Research (DataReportal / Vanguard, Oct 2026): LinkedIn reaches **14.0M Nigerians**, and its
largest group is **25–34 (7.7M)** — the HR officer who needs payslips, the freelancer who
needs invoices, the landlord who needs a tenancy agreement that holds. No other lane
reaches that reader at a desk, in the morning, in a reading mood. And it is free:
"Share on LinkedIn" is a self-serve product in the Developer Portal — no review — and
grants `w_member_social`, posting to the authorising member's **own profile**. (Company
Pages need the vetted Community Management API; we do not need it.)

## The two facts that shape it
1. **Tokens live 60 days and self-serve apps get no refresh token.** The lane keeps the day
   it first saw each token in `logs/linkedin_posts.json` (`tokens` → fingerprint → date),
   prints `LINKEDIN_TOKEN_AGE=<days>`, warns from day 50, and on a 401 (`65600` expired /
   `65601` revoked) goes red once with the exact taps. This is the **one tap every two
   months** that cannot be removed.
2. **No secret = dormant, not red.** Without `LINKEDIN_ACCESS_TOKEN` the lane prints a
   notice and `LINKEDIN_RESULT=dormant` and exits 0. It wakes the morning after the secret
   exists.

## Setting it up, from the phone (once)
1. linkedin.com/developers → **Create app** — name `DocOga`, LinkedIn Page: pick the DocOga
   Page (or your own profile's company if none), logo: `brand/favicon-512.png`, tick the
   legal agreement → Create.
2. **Products** tab → *Share on LinkedIn* → **Request access** (instant). Also add
   *Sign In with LinkedIn using OpenID Connect* (instant) — it is what lets `/v2/userinfo`
   say who the token is.
3. **Auth** tab → *OAuth 2.0 tools* (right side) → **Create token** → tick `openid`,
   `profile`, `w_member_social` → Request access token → sign in → **copy the token**.
4. GitHub → repo → Settings → Secrets → **New repository secret** →
   name `LINKEDIN_ACCESS_TOKEN`, value = the token → Add secret.
5. Optional check: Actions → *DocOga LinkedIn Auto-Post* → Run workflow → `probe_only` ✓.
   The summary says "token is alive" and its age.

Every ~58 days the heartbeat and the lane's own warning say "re-authorize": repeat **step 3
and 4** only.

## What a post looks like
The brain's pack for the day (`tools/brain_drafts.py`: headline, lines, the send line, the
cited-claims disclaimer, the deep link) with hashtags removed — LinkedIn 2026 ranks dwell
time and comments, not tags — and LinkedIn's "little text" reserved characters
(`\ | { } @ [ ] ( ) < > # * _ ~`) escaped so `s.13(1)(e)` arrives intact. With no pack the
hand-written rotation is used. The link rides as an article card
(`content.article.source`); if LinkedIn refuses the card the text posts alone.

## Guard rails
- Duplicate guard: SHA of the normalised text in `logs/linkedin_posts.json`; `--force`
  overrides.
- Copy gate: non-empty, ≤3,000 chars, only `docoga.com.ng` links.
- Rate: 150 requests/member/day on LinkedIn's side; we make four a week.
- Failure issues: label `linkedin-automation`, one per cause (`setup`, `credentials`,
  `permission`, `copy`, `quota`, `transport`, `run`), later failures comment.

## Machine lines
`LINKEDIN_RESULT=sent|duplicate|dormant|dry-run|probed|refused|failed`,
`LINKEDIN_CAUSE=…`, `LINKEDIN_TOKEN_AGE=<days>`, `LINKEDIN_URL=…`.

## Not done, on purpose
- Company-Page posting (needs Community Management review — a form, not a tap).
- Follower counts in the scorecard (member analytics are not exposed to self-serve apps).
- Images/video on LinkedIn (needs the Images/Videos API upload dance; words first, the card
  carries the link preview).
