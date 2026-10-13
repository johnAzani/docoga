# LAUNCH SEQUENCE — the steps a human owes, in the order that makes them safe

**Read this before you tap anything.** Every step here is one command or a few taps. The order
matters because merging starts the clocks — and because one of the two repairs below, done first,
would let an *old* unguarded poster start publishing to your readers tonight. **Step 1 is the merge**, steps 2 and 3 are the two
repairs it exposes (Telegram's chat id, Google's consent screen), step 4 is how you know it
worked, step 5 is the decision that is not urgent.

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
| `automation-heartbeat.yml` | 18:00 UTC daily | judge each lane from run history **and** the ledgers; file/update/close one issue |
| `instagram_autopost.yml` | never (dispatch only) | nothing. Decide its fate in step 5. |

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

## Step 5 — Instagram: decide, don't drift

`instagram_autopost.yml` is `workflow_dispatch`-only and its media container path needs a Meta
app with `instagram_content_publish` approved — which is a business-verification conversation,
not a code task. Two honest options: give it credentials and a schedule when that approval
exists, or leave it dispatch-only and let the heartbeat stop treating it as a lane. What is not
honest is a workflow that looks maintained and cannot run. Say which and I will do it.

---

## What this page is not

Not a status page: the current truth is `gh run list` and the ledgers. Not a substitute for the
per-lane handbooks — `TELEGRAM_AUTOMATION.md`, `FACEBOOK_AUTOMATION.md`, `YOUTUBE_AUTOMATION.md`
hold the structure research, the failure tables and the reasoning; this page holds only the order.
