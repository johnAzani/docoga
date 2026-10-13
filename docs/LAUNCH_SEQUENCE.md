# LAUNCH SEQUENCE — the four things a human owes, in the order that makes them safe

**Read this before you tap anything.** Every step here is one command or five taps. The order
matters for one reason only: merging starts the clocks, and a clock that fires into a missing
secret costs you a morning of reading issues. Steps 1 and 2 are setup; step 3 is the switch;
step 4 is how you know it worked.

Everything verifiable from the agent side was verified before this page was written — 418 python
tests, `tools/qa.py`, `tools/pre_push_verify.sh`, both npm DOM suites, CI on the branch head. What
is *not* verifiable from the sandbox is named in each step, because the sandbox cannot write
secrets (`403`), cannot dispatch workflows (`403`), and cannot reach `t.me` or Google.

> **If you do the steps out of order, nothing breaks.** Since 13 Oct 2026 a lane that was never
> configured files **one** issue titled `… [setup]` and adds a comment to it each day, instead of
> a fresh issue per run. It is a to-do list, not an outage.

---

## Step 1 — Telegram: one secret, then the live guard is armed

The lane posts to whatever `TELEGRAM_CHAT_ID` names. It is not set on the repository, which is
why nothing has posted since the pipeline was hardened.

```bash
gh secret set TELEGRAM_CHAT_ID --repo johnAzani/docoga --body '@docogadaily'
```

**Expected:** `✓ ✓ Set secret TELEGRAM_CHAT_ID for johnAzani/docoga`. No output is normal;
secrets are write-only, so never try to read it back.

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

## Step 2 — YouTube: publish the consent screen, then re-consent once

The lane died on 9 Oct with a green preflight and a red upload. The leading explanation is
documented in `YOUTUBE_AUTOMATION.md`: **while an OAuth consent screen is "In testing", Google
expires refresh tokens after 7 days** — which fits "worked 6 Oct, dead 9 Oct" exactly. So the fix
is not the code, it is the app's status.

Five taps, in Cloud Console (`console.cloud.google.com` → APIs & Services → OAuth consent screen):

1. top-right project picker → **the project that owns the YouTube client** (not "My Project").
2. **Audience** → User type: `External` → *Publish*. Expected: a banner that reads
   *"The app has been published to production."*
3. **Test users** → your Google account may stay listed; publishing is what removes the 7-day
   expiry, not the test user.
4. **Credentials** → your OAuth client → *Download JSON* if you want a copy. Do not rotate it
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
gh run view --log                                       # or the run's job log
```

**Expected screen:**

```
probe: channel @DocOga (UC…0 chars) — uploads allowed, quota unit spent
YT_PROBE_RESULT=ok
```

| if it says | it means |
|---|---|
| `kind=credentials` | the token is still the old one, or the consent screen is still in testing. Step 2 is not finished. |
| `kind=quota` | something else on the client spent the bucket — `videos.insert` costs 1 unit of 100/day, so this lane alone cannot be the reason |
| `kind=forbidden` | YouTube refuses the channel (strike, or no verified phone number) |

Re-render + upload happens on the next scheduled run (Tue & Fri 17:00 UTC) or with
`gh workflow run youtube_scheduled.yml`. It reads the upload back before calling it published, so
`state: held` in the log means "your channel defaults uploads to private", not "the code failed".

---

## Step 3 — Merge: this is the switch, not a deploy

```bash
gh pr merge 19
```

`gh pr merge` is deliberately **not** run by the agent: merging starts posting to your audience
daily, and that is your call with your name on it. Nothing else in this repository ships
anything to a reader.

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

## Step 4 — The next morning: three checks, five minutes

```bash
gh run list --limit 6                                      # every lane green?
git fetch && git show main:logs/telegram_sent.json         # a real entry, with a t.me URL?
gh issue list --label automation-heartbeat                 # and it is *closed*?
```

| what you see | verdict |
|---|---|
| run green + a ledger entry with a permalink + heartbeat issue closed | the engine is running. **Close #16 and #12** with the run link: until they are closed, a new failure folds its comment into them instead of opening a tagged issue, because an issue filed before 13 Oct has no cause in its title to match on. |
| run green, no ledger entry | `green-but-quiet` — the heartbeat files this on purpose; read the summary line that says which step skipped and why |
| run red with `[setup]` | a secret from step 1/2 is missing or unreadable — the issue body names which |
| run red with `[credentials]` on YouTube | the consent screen is still in testing. Step 2, taps 1–3. |

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
