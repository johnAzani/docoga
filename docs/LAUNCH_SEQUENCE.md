# LAUNCH SEQUENCE — the steps a human owes, in the order that makes them safe

**Read this before you tap anything.** Every step here is one command or a few taps. The order
matters because merging starts the clocks — and because one of the two repairs below, done first,
would let an *old* unguarded poster start publishing to your readers tonight. **Step 1 is the merge**, steps 2 and 3 are the two
repairs it exposes (Telegram's chat id, Google's consent screen), step 4 is how you know it
worked, step 5 turns on the two Meta lanes.

The order below is not the order the steps were written in. It is the order that is safe, and it
comes from reading `main` rather than trusting this document's first draft (see the table under
"Today's facts"): **the merge has to come before the Telegram fix**, because the Telegram workflow
is already scheduled on `main` and a corrected chat id starts posting through the *old* unguarded
poster the next morning.

Everything verifiable from the agent side was verified before this page was written: the full
python suite, `tools/qa.py`, `tools/pre_push_verify.sh`, both npm DOM suites, and CI on the branch
head. `python3 tools/lane_status.py --lane <lane>` is the one command for all of it on the GitHub
side. What
is *not* verifiable from the sandbox is named in each step: no `gh secret` write (`403` — not even
a *list* of names), no workflow dispatch (`403`), no `t.me`, no Google. What **is** readable from
here, and is how every step below gets checked: run history, job/step conclusions, check-run
annotations, and the contents of `main`.

> **If you do the steps out of order, nothing breaks** — in the *new* code. Since 13 Oct 2026 a
> lane that cannot post files **one** issue per cause (`[setup]`, `[chat]`, `[credentials]`…) and
> comments on it each day instead of filing a fresh one.

### Today's facts, read off `main` rather than assumed (13 Oct, ~10:15 UTC)

| what | evidence |
|---|---|
| `TELEGRAM_CHAT_ID` **is set** — and Telegram rejects the value | the 12 Oct 17:31 UTC scheduled run's annotations: `getChat(***) failed: Bad Request: chat not found`, preflight exit 4, every later step `skipped` |
| the Telegram lane has been down since at least **8 Oct** | five consecutive `schedule` runs on `main`, all `failure`: 08, 09, 10, 11, 12 Oct |
| and it has been down **quietly** | exactly one issue exists for it (#16, filed 11 Oct, **zero comments**). The 12 Oct failure tried to comment on #16, the comment call exited 1, and nothing was recorded |
| the day-dedupe that routed it there has never worked | `RUN_DATE="$(date +%F)"` is a shell variable, never exported, and the filter asks jq for `$ENV.RUN_DATE` → an empty needle → `contains("")` is true for *every* open issue. Now pinned by a test in `tools/tests/test_workflow_contract.py` |
| Facebook is **not** posting from `main` | `git show main:.github/workflows/facebook_autopost.yml` is `workflow_dispatch`-only; the 08:30 UTC cron arrives with the merge, not before |
| **the Shorts lane runs tonight at 17:00 UTC from `main`'s old code** | `cron: '0 17 * * 2,5'` is on `main` already and today is Tuesday |

Two consequences for the order, both of them the opposite of the obvious guess:

1. **Fixing `TELEGRAM_CHAT_ID` starts posting *today*, with the old unguarded poster** — main's
   version has no ledger and no channel check, which is precisely the setup that put the same
   paragraph on the channel four times on 3 Oct. So merge **before** you fix the id, not after.
2. **Merging before 17:00 UTC tonight buys the YouTube diagnosis for free.** The lane runs either
   way; the difference is that the new code prints a *classified* cause (`kind=…`, a `fix:`
   sentence, and a probe that names the channel the token actually authorises), while main's old
   code repeats the 9 Oct shape — a red step and no explanation.

So the sequence is: **merge → fix the chat id → the consent screen → tomorrow's three checks.**

---

## Step 1 — Merge: this is the switch, and it should go first

```bash
gh pr merge 19
```

`gh pr merge` is deliberately **not** run by the agent: merging starts posting to your audience
daily, and that is your call with your name on it. Nothing else in this repository ships anything
to a reader.

**Do it before step 2, and before 17:00 UTC today if you can.** Two reasons, both from the table
above: the Shorts lane runs on `main` tonight either way, and after the merge that run prints a
classified cause instead of `Exit code 1`; and Telegram is scheduled on `main` *now*, so fixing its
chat id first would put the next post through the old poster with no ledger and no channel check —
the exact configuration that posted one paragraph four times on 3 Oct.

What the merge turns on, exactly:

| workflow | fires | on a fresh merge it will |
|---|---|---|
| `telegram_autopost.yml` | 08:00 UTC daily (09:00 WAT) | post one text/tip card to `@docogadaily`, record it in `logs/telegram_sent.json`, and cross-check the channel page first |
| `facebook_autopost.yml` | 08:30 UTC daily | post to the Page, and to Reels when a render exists; asks Graph API before repeating itself |
| `youtube_scheduled.yml` | 17:00 UTC Tue & Fri | render → upload → read back → record `logs/youtube_published.json` |
| `automation-heartbeat.yml` | 20:00 UTC daily | judge each lane from run history **and** the ledgers; file/update/close one issue |
| `threads_autopost.yml` | 08:45 UTC daily | needs two secrets (step 5). Until they exist it files **one** `[setup]` issue and stops — it does not pretend. |
| `instagram_autopost.yml` | 09:00 UTC daily | same contract: `[setup]` issue until `IG_ACCESS_TOKEN` exists, then a card on the profile with the render committed under `site/social/`. |

The three ledgers are **absent from `main` today** — no lane has ever recorded a publish there.
After the first successful run of each, `git show main:logs/telegram_sent.json` should exist.
That is the difference between "the workflow ran" and "readers got something".

Failure behaviour you can rely on after this: a lane that cannot post goes **red + one issue per
cause** (`[setup]`, `[credentials]`, `[chat]`, `[rights]`, `[quota]`…), each later failure a
comment on the same issue with its own run link; a lane that posts a duplicate refuses it and
stays **green** with `refused-a-duplicate` in the summary.

**Panic button** (no commit, no discussion, takes effect immediately):

```bash
gh workflow disable telegram_autopost.yml   # per lane, repeat as needed
```

---

## Step 2 — Telegram: correct the chat id (this is what actually starts posting)

The secret exists; its **value** is what `getChat` rejects. `gh secret set` overwrites, so the
fix is one command — and the preflight in the merged branch now prints the ids the bot *can*
see, so you are not guessing a value in the dark:

```bash
gh workflow run telegram_autopost.yml -f dry_run=true   # what the lane can actually reach
gh secret set TELEGRAM_CHAT_ID --repo johnAzani/docoga --body '@docogadaily'
```

**Expected from the dry run:** the preflight step ends red on `chat not found`, and the *next*
lines list the channels the bot belongs to with their ids — `@docogadaily` among them means the
bot is still in the channel and the stored value is simply wrong; an absent channel means the bot
was removed (add it back as admin with *Post messages*, then set the id).

One caveat on that list: it comes from `getUpdates`, which returns nothing while a **webhook** is
registered for the bot. If the preflight says it could not list the bot's chats, that is the
webhook, not a removed bot — and the preflight only *suggests* deleting it, it never does, because
deleting a webhook breaks whatever registered it.

**Expected from `gh secret set`:** `✓ Set secret TELEGRAM_CHAT_ID for johnAzani/docoga`. No output
is normal — the *names* of secrets are not even listable from an Actions token (`gh secret list`
returns `403`), which is why the dry run above is the check, not a read-back.

Then prove it to yourself without posting anything:

```bash
gh workflow run telegram_autopost.yml -f dry_run=true
gh run watch                                      # or the Actions tab
```

**Expected screen** — the `Preflight — may the bot post to the channel?` step ending with:

```
✅ Token valid — bot @<yourbot> (id …)
✅ Chat reachable — DocOga Daily (channel) id -100…
✅ Posting rights confirmed (status: administrator)
✅ live duplicate guard: readable — 20 post(s) visible at t.me/s/docogadaily (ids 1-20, newest 20)
```

and the run summary saying `Dry run — nothing was generated and nothing was posted.`

| if the screen says | it means | do this |
|---|---|---|
| `Telegram chat not reachable` + a list of chats | the id/username is wrong | copy the id the preflight printed and re-set the secret — it names the fix |
| `Posting rights … can_post_messages is false` | admin without "Post messages" | channel → Manage → Administrators → re-tick **Post messages** |
| `live duplicate guard: … no messages / unavailable` | the channel is private, or `@docogadaily` is not its public name | Channel → Public type: set a public link. Otherwise the ledger is the only guard and that is a decision, not a bug |
| `Unauthorized` | the bot token was revoked | @BotFather → `/revoke` → `gh secret set TELEGRAM_BOT_TOKEN` |

**Also on your machine** (the one check the sandbox cannot run — `t.me` is blocked here):

```bash
python3 tools/telegram_preflight.py --preview @docogadaily
```

Exit 0 = the live duplicate guard will run on every post. This needs **no token at all**, so it
answers "is the guard armed?" without touching secrets.

---

## Step 3 — YouTube: publish the consent screen, then re-consent once

The lane died on 9 Oct with a green preflight and a red upload. The leading explanation is
documented in `YOUTUBE_AUTOMATION.md`: **while an OAuth consent screen is "In testing", Google
expires refresh tokens after 7 days** — which fits "worked 6 Oct, dead 9 Oct" exactly. So the fix
is not the code, it is the app's status.

Google moved this screen: "OAuth consent screen" now *redirects* to the **Google Auth Platform**,
whose settings are split into **Branding / Audience / Data Access / Clients**, and the publish
button is on **Audience** — not on the page the old menu lands you on. Full reasoning and the
fallbacks are in `YOUTUBE_AUTOMATION.md`; the taps are:

1. Open `console.cloud.google.com/auth/audience?project=<PROJECT_ID>` and check the project picker
   first (not "My Project"). *[Audience: `User type: External`,
   `Publishing status: In testing`.]*
2. **Publish app** → *"Push to production?"* → **Confirm**. *[Status flips to **In production** —
   that one change is what stops the 7-day token expiry.]* A **Needs verification** notice is not a
   blocker for your own channel.
3. Only if you would rather stay in Testing: **Audience → + Add users** → the DocOga Google address.
   A bridge, not a fix — tokens still die weekly.
4. **Clients** → this lane's client → confirm *Desktop app*, no redirect URIs. Do not rotate it
   unless it was deleted.
5. Re-mint the refresh token on your machine (the consent flow is the only place a browser is
   needed), then:

```bash
gh secret set YT_REFRESH_TOKEN --repo johnAzani/docoga --body '<ya29.…>'
# if — and only if — the client itself changed, replace all three together:
gh secret set YT_CLIENT_ID … ; gh secret set YT_CLIENT_SECRET …
```

Then ask the lane what it can actually see — **1 quota unit, no upload, nothing rendered**:

```bash
gh workflow run youtube_scheduled.yml -f probe_only=true
python3 tools/lane_status.py --lane youtube             # what the run said, without the log
```

`gh run view --log` is *not* the check: the log bytes live on a host a sandbox (or a locked-down
runner) often cannot reach. `tools/lane_status.py` reads the job, the step conclusions and the
annotations — the same text the preflight wrote with `::error` — over ordinary REST.

**Expected screen:**

```
probe: channel @DocOga (UC…0 chars) — uploads allowed, quota unit spent
YT_PROBE_RESULT=ok
```

| if it says | it means |
|---|---|
| `kind=credentials` | the token is still the old one, or the consent screen is still in testing. Step 3 is not finished. |
| `kind=quota` | something else on the client spent the bucket — `videos.insert` costs 1 unit of 100/day, so this lane alone cannot be the reason |
| `kind=forbidden` | YouTube refuses the channel (strike, or no verified phone number) |

Re-render + upload happens on the next scheduled run (Tue & Fri 17:00 UTC) or with
`gh workflow run youtube_scheduled.yml`. It reads the upload back before calling it published, so
`state: held` in the log means "your channel defaults uploads to private", not "the code failed".

---

## Step 4 — The next morning: three checks, five minutes

```bash
gh run list --limit 6                                      # every lane green?
git fetch && git show main:logs/telegram_sent.json         # a real entry, with a t.me URL?
gh issue list --label automation-heartbeat                 # and it is *closed*?
```

| what you see | verdict |
|---|---|
| run green + a ledger entry with a permalink + heartbeat issue closed | the engine is running. **Close #16 and #12** with the run link: until they are closed, a new failure folds its comment into them instead of opening a tagged issue, because an issue filed before 13 Oct has no cause in its title to match on. |
| you want the *cause* of a red run without opening the log | `python3 tools/lane_status.py --lane telegram --limit 3` — one command, read-only, exit code usable as a gate. It prints the failing steps, what never ran, and the annotations; a repeated conclusion is called a pattern. Without the repo checked out: `gh api repos/johnAzani/docoga/actions/runs/<id>/jobs --jq '.jobs[0].id'` then `gh api repos/johnAzani/docoga/check-runs/<job_id>/annotations` — that is how `chat not found` was found on 13 Oct, four days into an outage nobody had been told about |
| run green, no ledger entry | `green-but-quiet` — the heartbeat files this on purpose; read the summary line that says which step skipped and why |
| run red with `[setup]` | a secret from step 2 or 3 is missing or unreadable — the issue body names which |
| run red with `[credentials]` on YouTube | the consent screen is still in testing. Step 3, taps 1–5. |

Also worth one look: the run summary line `duplicate guard: live` (Telegram). `unavailable` there
is not an error; it is the lane telling you it posted on the ledger's word alone.

---

## Step 5 — the two Meta lanes: 20 minutes, then they are unattended

This step used to read *"Instagram needs App Review and business verification, so it stays
dispatch-only"*. That was wrong, and the correction is the reason the lane is schedulable now:
**Standard Access** covers an app publishing to accounts its own owner manages — no review, no
verification, no queue. Full research, the requirement matrix, the tap list and the failure table
are in `INSTAGRAM_THREADS_AUTOMATION.md`; what is here is the shortest honest path.

```bash
gh secret set THREADS_USER_ID     --repo johnAzani/docoga --body '<numeric id>'
gh secret set THREADS_ACCESS_TOKEN --repo johnAzani/docoga --body '<60-day token>'
gh secret set SOCIAL_TOKEN_KEY    --repo johnAzani/docoga --body "$(openssl rand -hex 32)"
gh workflow run threads_autopost.yml -f dry_run=true    # expects: exit 3 + a chat-free reason
gh workflow run threads_autopost.yml                    # the real post
```

`SOCIAL_TOKEN_KEY` is the tap people skip, and it is the one that decides whether you are back
here in sixty days: with it, each run refreshes the Meta token and seals the new value into
`logs/*_token.box` in the repo (keyed on a secret a workflow cannot write — that is why the key
has to be set by a human exactly once); without it, the lane still posts and silently loses every
refresh. The workflow says which state you are in rather than letting you discover it in
December.

| check | expected |
|---|---|
| `gh run list --limit 4` | `Threads autopost` success, `Instagram autopost` success or one open `[setup]` issue |
| `git show main:logs/threads_sent.json` | an entry with a `threads.net` permalink |
| the run summary | `THREADS_RESULT=published`, `TOKEN_EXPIRES_IN_DAYS=59` (60 after a refresh) |
| `lane_status --lane threads` **before** the merge | `threads_autopost.yml exists in this checkout but GitHub has never listed it — it is not on the default branch yet`. Correct, not a fault: Actions only arms a `cron:` it can see on the default branch. Ask again the morning after the merge |
| a **warning** reading `Threads token not refreshed … less than 24 hours old` | expected on the run you do the same day you set the secret: Meta allows one refresh per 24 h. It is a warning and a green tick because there is nothing to fix; the sealed box shows up the next morning |
| `python3 tools/lane_status.py --lane threads` | exit 0 and no failing step |

**Instagram's extra step is the file, not the token**: the card is rendered into `site/social/`,
committed, and the lane waits for the deployed URL to answer before creating the container
(`--wait-url`), because Meta downloads the image rather than receiving it. Reels remain refused
for the same reason — no public video host yet — and that refusal is one line in the log with
`IG_CAUSE=media`, not a timeout.

## Step 6 — the reach layer (17 Oct 2026): four optional taps, each one switches on a lane

Everything below is already live and **dormant until its secret exists**; nothing goes red
while you decide.

| tap | where | what wakes up |
|---|---|---|
| Re-mint the Threads token with `threads_share_to_instagram` ticked | Meta app → Threads use case → User Token Generator → update `THREADS_ACCESS_TOKEN` | every Threads post also lands on Instagram (`THREADS_SHARE_TO_IG=SUCCESS` in the summary) |
| Secret `LINKEDIN_ACCESS_TOKEN` | `docs/LINKEDIN_AUTOMATION.md`, five taps | Mon/Wed/Fri 08:30 post to your LinkedIn profile; re-mint every ~58 days when the lane warns |
| Secrets `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN` | `docs/TIKTOK_AUTOMATION.md`, once | every Short also lands in your TikTok inbox; you paste the caption and tap Post |
| (nothing) | — | Threads topic tags + polls, Instagram Trial Reels, the Tuesday Telegram quiz and the newsdesk run on the tokens you already have |

Opt-outs are variables: `THREADS_SHARE_TO_IG=off`, `IG_TRIAL_REELS=off`.

## Step 7 — the money layer (17 Oct 2026): three optional taps

Already live; each tap switches one more number on. Nothing goes red while you decide.

| tap | where (phone) | what wakes up |
|---|---|---|
| ✅ **Done 17 Oct 2026 (6:57pm).** Cloudflare Web Analytics was already on for `docoga.com.ng` (Automatic setup); the owner minted a read-only *Read analytics and logs* token → secret `CF_ANALYTICS_TOKEN`. The site tag is discovered automatically (site list, then the beacon on the live page) — `CF_WEB_ANALYTICS_SITE_TAG` is only needed if that ever fails. Proof: the **Site analytics — is Cloudflare connected?** workflow (runs on demand and whenever the puller changes) | GitHub → Actions | first live pull: 52 visits / 70 page views in 7 days — direct 33, Google 13, Facebook 6; Monday scorecard shows `SITE_ANALYTICS=ok` |
| Google re-consent once with the two extra scopes (`docs/BRAIN.md` → "The one Google re-consent") → paste the new `YT_REFRESH_TOKEN` | Google Cloud console → OAuth consent → Data access | Search Console queries in the brain's prompt + `google.clicks_28d` on the scorecard (`SEARCH_CONSOLE=ok`); YouTube Analytics metrics |
| Facebook: Page → Professional dashboard → **Monetisation** → "Express interest" (Stars unlocks at 500 followers for 30 days — the scorecard counts the weeks) | Facebook app | nothing in the repo; Meta knows you want in the day you qualify |
| (nothing) | — | link tags, checkout/sale counters, first-comment links, the 20:10 Threads image post, Instagram alt text, the Wednesday Short and the Telegram video all run on what you already have |

Opt-outs: `FB_LINK_IN_COMMENT=off`. The checkout counters are counters only — the payment link, the webhook and the pass code are untouched.

---

## Step 8 — the conversion layer (17 Oct 2026): two optional taps, both token re-mints

Everything else in this round runs on what you already have (Telegram buttons, Tuesday/Thursday
carousels, the slot gate, the hook bandit, the pinned newsdesk, the heartbeat fix). The two taps
below open the inbox: a reader who comments "link" gets the page by private message.

**Mint with the FULL list, once — `docs/TOKENS.md`.** It carries every permission each token can
hold (15 for the Page token, 5 for Instagram, 10 for Threads, 7 Google scopes), so no later
feature ever asks for a re-mint. The Monday scorecard audits every token and prints ✅ complete
or the exact names missing.

| tap | where (phone) | what wakes up |
|---|---|---|
| Instagram token re-mint with **all five** scopes (`docs/TOKENS.md` § 2): developers.facebook.com → the app → **Instagram** use case → **User token generator** → every permission on → Generate → paste the new `IG_ACCESS_TOKEN` | GitHub → Settings → Secrets and variables → Actions | the replies lane's run summary stops saying "comment→DM is waiting on `instagram_business_manage_messages`" and starts showing 📩 DM lines |
| Facebook Page token re-mint with **all fifteen** permissions (`docs/TOKENS.md` § 1): Graph API Explorer → the Business app → Page token → tick the whole list → Generate → extend → paste `FB_PAGE_ACCESS_TOKEN` | same | Facebook comments that ask for the link get the Messenger private reply |

Opt-outs: repo vars `TELEGRAM_BUTTONS=off`, `IG_CAROUSEL=off`, `BRAIN_DM=off`. The slot gate has no switch — a dispatch always posts, and `brain/slots.json` can be edited by hand (`"hour_wat": 19`).

One thing to know before Sunday: if you ever link a discussion group to @docogadaily, the poster notices (`getChat.linked_chat_id`) and drops the buttons so the "Leave a comment" button survives; the links stay in the caption. `TELEGRAM_BUTTONS=force` overrides.

---

## What this page is not

Not a status page: the current truth is `gh run list` and the ledgers. Not a substitute for the
per-lane handbooks — `TELEGRAM_AUTOMATION.md`, `FACEBOOK_AUTOMATION.md`, `YOUTUBE_AUTOMATION.md`,
`INSTAGRAM_THREADS_AUTOMATION.md` hold the structure research, the failure tables and the
reasoning; this page holds only the order.
