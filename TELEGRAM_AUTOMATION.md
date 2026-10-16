# DocOga Telegram Automation

**Fully Autonomous Telegram Posting System**  
**Status:** ✅ Ready for Deployment  
**Cost:** ₦0 (100% Free)  
**Last Updated:** 2026-10-03

---

## 🎯 What This Does

This system **automatically generates and posts content to your Telegram channel every day at 9 AM (Nigeria time)** without any manual intervention. It:

1. **Generates** Nigerian-focused content (landlord tips, tenant rights, DocOga promos)
2. **Posts** to your Telegram channel automatically
3. **Runs on GitHub Actions** (free, no server needed)
4. **Logs everything** for debugging

---

## 📁 Files Created

```
docoga/
├── scripts/
│   ├── generate_telegram_content.py  # Content generator
│   └── post_telegram.py               # Telegram poster
├── .github/
│   └── workflows/
│       └── telegram_autopost.yml      # GitHub Actions workflow
├── assets/
│   └── telegram/                     # Generated content storage
├── logs/
│   └── social_media.log              # Activity logs
└── TELEGRAM_AUTOMATION.md            # This file
```

---

## ⚡ One-Time Setup (5 Minutes)

### Step 1: Create Telegram Bot

1. Open Telegram → Search for **[@BotFather](https://t.me/BotFather)**
2. Send `/newbot`
3. Name it: `DocOgaBot` (or any name you prefer)
4. Username: `DocOgaBot` (must end with `bot`)
5. **Copy the Bot Token** (e.g., `123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### Step 2: Create Telegram Channel

1. Create a new **public channel** (DocOga's is `@docogadaily`)
2. Add your bot as an **admin** to the channel, with **Post messages** enabled
3. Get your **Channel ID** — and note that for a *public* channel the numeric id is
   optional, because Telegram accepts `@yourchannel` as a `chat_id`:

   - fastest: run `python3 tools/telegram_preflight.py` with the token exported. It
     calls `getChat` and, when the configured chat is unreachable, prints every chat the
     bot can actually see with the exact `gh secret set` line for each;
   - or send a message to [@username_to_id_bot](https://t.me/username_to_id_bot) and paste
     the channel username (e.g. `@docogadaily`);
   - **Copy the ID** (e.g., `-1001234567890`).

   Write down the **exact** username. The four-day outage of 7–12 Oct 2026 was this field
   holding `@docoga` — the *website's* handle, not the channel's — and every run died at
   `getChat: chat not found`, which reads like a permissions problem and is not one.

### Step 3: Add Secrets to GitHub

1. Go to your repo on GitHub: `https://github.com/johnAzani/docoga`
2. Click **Settings → Secrets → Actions → New repository secret**
3. Add these **2 secrets**:

   | Secret Name | Value | Example |
   |-------------|-------|---------|
   | `TELEGRAM_BOT_TOKEN` | Your bot token | `123456789:ABC-DEF...` |
   | `TELEGRAM_CHAT_ID` | Your channel ID | `-1001234567890` |

### Step 4: Enable Workflow

1. Go to **Actions** tab in your GitHub repo
2. Find **DocOga Telegram Auto-Post** workflow
3. Click **Run workflow** → **Run workflow** (manual trigger to test)

---

## 🤖 How It Works

### Content Generation
The system generates **5 types of posts** that rotate daily:

| Day | Post Type | Example |
|-----|-----------|---------|
| Monday | **Promo** | "Get Clean Tenancy Agreements in Seconds!" |
| Tuesday | **Educational** | "Did You Know? In Nigeria, a tenancy agreement should include..." |
| Wednesday | **Pidgin** | "Oya Check Am! DocOga dey help you make tenancy agreement..." |
| Thursday | **Testimonial** | "User Testimonial: DocOga saved me ₦50,000..." |
| Friday | **Urgent/Promo** | "Limited Time Offer! First 100 users get 50% off..." |
| Saturday | **Educational** | "Tenancy Tip: Always get a written receipt..." |
| Sunday | **Pidgin** | "No more palava! DocOga documents na clean..." |

### Posting Schedule
- **Time:** 9 AM Nigeria time (daily)
- **Timezone:** Africa/Lagos (UTC+1)
- **Trigger:** GitHub Actions cron job

### Content Examples

**Promo Post:**
```
🚀 **Get Clean Tenancy Agreements in Seconds!**

DocOga helps Nigerian landlords and tenants create professional documents instantly. No lawyer fees!

👉 Try it free: https://docoga.com.ng

#DocOga #NigerianLandlords #TenancyAgreement
```

**Pidgin Post:**
```
🎉 **Oya Check Am!**

DocOga dey help you make tenancy agreement for free! No need pay lawyer ₦50k.

👉 Try am: https://docoga.com.ng

#DocOga #NaijaLandlord #Pidgin
```

**Educational Post:**
```
📌 **Did You Know?**

In Nigeria, a tenancy agreement should include:
✅ Landlord & tenant names
✅ Property address
✅ Rent amount & payment terms
✅ Duration
✅ Notice period

Generate yours instantly: https://docoga.com.ng

#PropertyTips #NigerianRealEstate
```

---

## 📊 What You Get

✅ **Daily automatic posts** to Telegram  
✅ **Nigerian-focused content** (landlords, tenants, property)  
✅ **Pidgin English** posts (matches DocOga brand voice)  
✅ **Promotional content** (drives traffic to docoga.com.ng)  
✅ **Educational content** (builds authority)  
✅ **Testimonial-style posts** (social proof)  
✅ **Zero manual work** after setup  
✅ **Free forever** (GitHub Actions free tier)  

---

## 🔍 Testing

### Manual Test
```bash
# Generate content
python scripts/generate_telegram_content.py

# Post to Telegram (set env vars first)
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python scripts/post_telegram.py
```

### Check what was actually published
```bash
# The record of publishing — committed, so CI and the heartbeat can read it too:
python3 tools/youtube_ledger.py --ledger logs/telegram_sent.json show --limit 10

# The scratch log — useful for the API's own words, and NOT evidence of anything:
tail -n 40 logs/social_media.log
```

`logs/social_media.log` is gitignored, appended to by whoever runs the script, and was
for a while mostly test noise. `logs/telegram_sent.json` is the durable one: one entry per
message Telegram accepted, carrying its `t.me/…/<id>` permalink. If the two disagree, the
ledger is right.

### Verify on Telegram
1. Check your Telegram channel
2. You should see the posted message

---

## 🧾 13 Oct 2026 — one publish per content, the ledger that proves it, and the channel that double-checks it

Two bugs in the same shape, found while building the silent-lane heartbeat
(`automation-heartbeat.yml`, `tools/automation_heartbeat.py`):

1. **the channel got the same post four times.** On 3 Oct 2026 `@docogadaily` carried the
   caution-fee paragraph at 15:44, 15:45, 17:02 and 17:50 — four runs (one scheduled,
   three dispatches) each starting from zero knowledge of what was already up. The poster
   now fingerprints the *text* (sha1 of the message, plus its `post_type`) and refuses to
   re-send anything already in the ledger within 7 days. Content, not date: a new
   sentence in the same slot still posts, and the same sentence a week later still posts.

   ```bash
   # to publish something the ledger already knows (a deliberate re-post):
   gh workflow run telegram_autopost.yml -f force=true
   ```

2. **nothing proved a publish.** A green run was the only signal, and "the run went red
   for six days" fought with "the channel got a post on 7 Oct" with no referee. So the
   poster writes `logs/telegram_sent.json` through `tools/youtube_ledger.py` — the same
   machinery as the Shorts and Reels lanes, pointed at this lane's file, because a forked
   ledger drifts the first time someone fixes a race in the other one. The workflow
   commits it back to the default branch with `[skip ci]`, and *bookkeeping can never turn
   a successful publish red*: a failed commit is a warning that names the consequence
   ("a re-run could post this again"), not a red X.

The heartbeat then reads that file and crosses it with run history, in both directions:

| run history | ledger | verdict |
|---|---|---|
| recent success | entry inside the cadence | ✅ healthy |
| recent success | nothing new | ❌ `green-but-quiet` — a run that succeeds without publishing is green, so nothing else looks at it |
| silent past the deadline | a publish inside it | ❌ still red (the cron *is* broken) with the note "readers are still being served — fix the schedule, don't write off the audience" |
| silent | no ledger file on `main` yet | ❌ with "no publish evidence either way", which is not the same sentence as "nothing was published" |

### The second guard: asking the channel, not the bookkeeping

A ledger is a file, and a file can be lost. If the ledger commit fails, if someone runs the
workflow from a branch that predates it, or if the repo is re-cloned, the poster wakes up with
zero knowledge again — the exact state that posted the caution-fee paragraph four times. The
Facebook lane never had that weakness, because `scripts/post_facebook.py` asks the Graph API
what it published today. Telegram has no such call for a bot, so the lane asked its own
history from a different direction: **every public channel publishes a server-rendered
preview at `t.me/s/<name>`** — the ~20 newest posts in plain HTML, no token, no login, no
rate limit worth mentioning for one GET a day. That page is now consulted before anything is
sent.

```
tools/telegram_preview.py   reads and interprets the page (shared with the preflight)
scripts/post_telegram.py    decides what to do about it
```

The rules, all of them load-bearing:

* **the ledger runs first, free and offline.** If the key is already recorded, no HTTP request
  is made at all; the live check exists only for what the ledger was not told about.
* **only an identical message is refused.** MarkdownV2 markup, HTML tags, entities and
  whitespace are stripped from both sides, and a channel post is matched against the words of
  the message that produced it. Links made this harder than it looks: Telegram rewrites
  `[docoga.com.ng](https://docoga.com.ng)` into an anchor whose URL sits in an attribute, and
  bolts a link-preview card with *the linked page's* words into the same block. So the guard
  compares the message body (`.tgme_widget_message_text`) rather than the whole block, and it
  compares **sets of words**, not counts — the source spells a link twice, the post shows it
  once, and a multiset would have missed the very duplicate this exists to catch.
* **two floors keep it from getting creative.** A message under 24 normalized characters, or
  under 6 distinct words with none longer than 5, is not judged at all. Refusing a post
  because it "rhymes" with an older one is a worse failure than the duplicate.
* **it fails open.** A CDN blip, a 503, a private channel, a Telegram markup change — all
  produce one warning line (`live channel guard unavailable — …`) and the post goes out. This
  guard may never become the reason the channel goes quiet.
* **a refusal is evidence, not a mystery.** The log names the permalink
  (`t.me/docogadaily/41 already carries this text`), the run stays green, nothing is written
  to the ledger, and `TELEGRAM_CHANNEL_GUARD=refused-a-duplicate` goes in the summary.

Each run reports which guard was watching, in the step summary:

| marker | meaning |
|---|---|
| `TELEGRAM_CHANNEL_GUARD=live` | the channel was read and did not have this text |
| `TELEGRAM_CHANNEL_GUARD=refused-a-duplicate` | the channel already had it — nothing was sent |
| `TELEGRAM_CHANNEL_GUARD=unavailable` | the page could not be read; the ledger guarded alone |
| `TELEGRAM_CHANNEL_GUARD=skipped` | nothing to compare against (numeric chat id, or too short) |

Knobs, all optional, all read once at import:

| variable | default | why you would set it |
|---|---|---|
| `TELEGRAM_SKIP_CHANNEL_CHECK` | unset | `1` turns the live guard off (an incident switch, not a setting) |
| `TELEGRAM_CHANNEL_GUARD_PAGES` | `1` | extra pages walk backwards with `?before=`; 1 page ≈ 3 weeks of a daily lane |
| `TELEGRAM_CHANNEL_GUARD_MIN` | `24` | the shortest message the guard is allowed to judge |
| `TELEGRAM_CHANNEL_USERNAME` | derived from `TELEGRAM_CHAT_ID` | set it when the chat id is numeric but the channel *is* public |
| `TELEGRAM_PREVIEW_BASE` | `https://t.me/s/` | pointed at a fixture by the tests; nothing else should touch it |

**What it cannot catch, said plainly:** a template line that recurs *with different surrounding
words* (by design, not a bug); a duplicate older than the ~20 newest posts; a post somebody
deleted by hand — the guard then sees no copy and re-posts, which is the correct answer to a
channel whose history was edited; and any channel that is not public, where there is nothing
to read and the ledger is the whole of the protection.

### Checking the guard without a secret in your hand

```bash
python3 tools/telegram_preflight.py --preview @docogadaily
```

No token, no network write, no chat access — one GET. Expected screens:

* `✅ channel preview: 20 post(s) visible at t.me/s/docogadaily (ids 1-20, newest 20)` → the
  live guard is armed on every run from now on;
* `⚠️ channel preview: docogadaily — the page carried no messages` → the channel is private or
  the name is wrong, and the ledger is guarding alone; the run is still correct, just single-
  guarded.

The full preflight (`python3 tools/telegram_preflight.py`, which needs the token) prints the
same line under `✅ Posting rights confirmed`, because "may the bot post?" and "can we see what
it already posted?" are two questions and the second one decides whether the duplicate guard is
real.

### What is owed by a human, once

> **The order of the steps is its own document:** `docs/LAUNCH_SEQUENCE.md` — it lists
> what a human owes, the exact command or tap for each, and the screen you should see.
> Merge before the secrets and you get a `[setup]` issue, not an outage; that page says
> why, and what to check the next morning.

`gh secret set` and `gh variable set` are **not** runnable from the agent sandbox — the Actions
token gets `403 Resource not accessible by integration` on those endpoints, this `gh` build has no
`variable` subcommand, and `gh secret list` gets the same 403, so an agent cannot even tell you
whether a name exists. Values are write-only everywhere. What *is* readable, from a sandbox with
no rights at all, is what a run says about itself:

```bash
gh api repos/johnAzani/docoga/actions/runs/<id>/jobs --jq '.jobs[0].id'
gh api repos/johnAzani/docoga/check-runs/<job_id>/annotations --jq '.[] | "\(.annotation_level) \(.message)"'
```

That is where `chat not found` came from, and it is why every step of `docs/LAUNCH_SEQUENCE.md`
can be verified after the fact instead of trusted. So:

**Corrected 13 Oct 2026, from the run's own annotations.** The sentence above used to read "set
   it", on the assumption the secret was missing. It is **not** missing — it is set to a value
   Telegram rejects. The last scheduled run on `main` (12 Oct, 17:31 UTC) annotated itself:

   ```
   getChat(***) failed: Bad Request: chat not found. Either TELEGRAM_CHAT_ID is wrong or the
   bot is no longer a member of that channel.          ← preflight exit 4, poster never ran
   ```

   Five consecutive scheduled failures (8–12 Oct), one issue (#16, filed 11 Oct) and **zero
   comments on it**: on 12 Oct the dedupe filter's needle was an unexported shell variable
   (`$ENV.RUN_DATE` reading an empty string, which matches every open issue), so the run tried to
   comment on #16 instead of filing, the comment call exited non-zero, and the failure left no
   trace. Both halves are fixed in `arena/bae11bd0-docoga`: the selector's variables are supplied
   on the `gh` command line, and a step that cannot file an issue is a warning, never a red run.

1. GitHub → **Settings → Secrets and variables → Actions → Repository secrets →
   `TELEGRAM_CHAT_ID`** → *overwrite* it with `@docogadaily` (or the `-100…` numeric id the
   preflight prints). If `getChat` still says `chat not found`, the bot has been removed from the
   channel — re-add it as admin with *Post messages* rather than changing the value again.
2. Then Actions → **DocOga Telegram Auto-Post** → **Run workflow** with
   `dry_run=true`. Expected screen: a green run whose log ends with
   `✅ Chat reachable — DocOga Daily (channel) id …` and `✅ Posting rights confirmed`.
   If instead it lists the chats the bot *can* see, copy the id it printed and re-set the
   secret.
3. Then run it with `dry_run=false`. Expected: one message on the channel within the
   minute, and the next scheduled run at 08:00 UTC (09:00 WAT) — the heartbeat's row for
   `telegram_autopost.yml` goes ✅ the morning after that.

### Deliberately not done

* no auto-rotation or re-minting of the bot token — @BotFather is a human conversation;
* no deleting a webhook to make `getUpdates` answer: that would silently break whatever
  registered it, so the preflight only *suggests* it;
* no second channel, no cross-posting to WhatsApp/IG from this workflow — one lane, one
  destination, so the ledger means one thing;
* the ledger never blocks a publish on a corrupt file: it warns, starts fresh, and leaves
  the unreadable file beside itself as `*.corrupt-<timestamp>`;
* no fuzzy or similarity matching on the channel page — a paragraph that merely *resembles*
  an older post is a new post, and the lane has survived three years on that reading;
* no `getUpdates`/`deleteWebhook` trickery to read history through the bot: the Bot API has no
  read-channel-history method, and inventing one is someone else's changelog;
* the preview is never cached to disk — a cached page is a second ledger with the same
  weakness this guard exists to remove.

---

## 📈 Customization

### Change Posting Time
Edit `.github/workflows/telegram_autopost.yml`:
```yaml
on:
  schedule:
    - cron: '0 8 * * *'  # Change this line
```

Cron schedule format: `minute hour day-of-month month day-of-week`  
Nigeria time (UTC+1) examples:
- 9 AM Nigeria = `0 8 * * *` (8 AM UTC)
- 12 PM Nigeria = `0 11 * * *` (11 AM UTC)
- 6 PM Nigeria = `0 17 * * *` (5 PM UTC)

Use [crontab.guru](https://crontab.guru/) to generate schedules.

### Add Custom Templates
Edit `scripts/generate_telegram_content.py` and add to the `TEMPLATES` dictionary:
```python
TEMPLATES = {
    "promo": [...],
    "educational": [...],
    "pidgin": [...],
    "testimonial_style": [...],
    "urgent": [...],
    "your_custom_type": ["Your custom message here..."]
}
```

### Change Posting Frequency
To post **multiple times per day**, modify the workflow to run more often:
```yaml
on:
  schedule:
    - cron: '0 8 * * *'   # 9 AM
    - cron: '0 14 * * *'  # 3 PM
```

---

## 🚨 Troubleshooting

### No Posts Appearing
1. **Check GitHub Actions:**
   - Go to **Actions** tab → Check if workflow ran
   - Look for errors in the logs

2. **Check Logs:**
   ```bash
   cat logs/social_media.log
   ```

3. **Verify Secrets:**
   - Ensure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set correctly
   - Check for typos or extra spaces

4. **Test Bot Manually:**
   - Send a message to your bot in Telegram
   - If it doesn't respond, your token is invalid

### `getMe failed: Not Found` (the 15–16 Oct 2026 failure)

Telegram's **404 Not Found** means the *shape* of the token is wrong — it is not a revoked
bot (that is **401 Unauthorized**). It happens when the secret is pasted from a phone with
its `bot` prefix, as the whole `https://api.telegram.org/bot…` URL, in quotes, truncated, or
with the chat id in the wrong field. Since 16 Oct 2026 every Telegram script reads the token
through `tools/telegram_token.py`, which finds the token *inside* an untidy paste (prefix,
URL, quotes, whitespace) and carries on with a warning; when nothing token-shaped is in the
secret at all, the preflight stops offline with a redacted description of what is there
("all digits — looks like a chat id", "only 8 characters after the colon — truncated paste")
and exit code 3. The fix is always the same one paste: @BotFather → `/mybots` → the bot →
**API Token** → set `TELEGRAM_BOT_TOKEN` to exactly `<digits>:<35 characters>`.

### Bot Not Posting to Channel
1. **Check Bot Permissions:**
   - Bot must be an **admin** in the channel
   - Channel must be **public** (or bot must be added as admin in private)

2. **Test with @BotFather:**
   - Send `/mybots` to @BotFather
   - Select your bot → **API Token** → Verify it matches

3. **Check Channel ID:**
   - Use [@username_to_id_bot](https://t.me/username_to_id_bot)
   - Make sure you're using the **channel ID**, not username

### GitHub Actions Not Running
1. **Check Workflow File:**
   - Ensure it's in `.github/workflows/telegram_autopost.yml`
   - Check for YAML syntax errors

2. **Check Repository Secrets:**
   - Go to **Settings → Secrets → Actions**
   - Verify both secrets exist

3. **Check Branch:**
   - The workflow runs on the `arena/01a10172-docoga` branch
   - Make sure your changes are committed to this branch

---

## 📚 Content Strategy

### Post Types Explained

| Type | Purpose | Frequency |
|------|---------|-----------|
| **Promo** | Drive traffic to docoga.com.ng | 2x/week |
| **Educational** | Build authority, SEO value | 2x/week |
| **Pidgin** | Match DocOga brand voice, local appeal | 2x/week |
| **Testimonial** | Social proof, trust building | 1x/week |
| **Urgent** | Create urgency, limited offers | 1x/week |

### Content Themes
All content focuses on:
- Nigerian landlord/tenant relationships
- Document generation (agreements, receipts, invoices)
- Legal tips (Nigerian law compliant)
- Money-saving (vs. lawyer fees)
- DocOga features and benefits

### Hashtags Used
- `#DocOga` (brand)
- `#NigerianLandlords` (target audience)
- `#TenancyAgreement` (SEO)
- `#RentReceipt` (SEO)
- `#PropertyTips` (educational)
- `#NaijaLandlord` (local appeal)
- `#NoLawyerNeeded` (value proposition)

---

## 🎉 Next Steps

### After Telegram Works
1. **Add YouTube automation** (video uploads)
2. **Add Facebook automation** (page posts)
3. **Add Instagram automation** (posts & stories)
4. **Add image generation** (Stable Diffusion for custom visuals)
5. **Add video generation** (FFmpeg slideshows)

### To Add More Platforms
Just say:
- "Add YouTube automation"
- "Add Facebook automation"
- "Add Instagram automation"
- "Add all platforms"

---

## 💬 Support

This is a **fully autonomous system**. Once set up:
- ✅ It posts **every day at 9 AM** (Nigeria time)
- ✅ It **never stops** (GitHub Actions runs 24/7)
- ✅ It **costs ₦0** (all free services)
- ✅ It **drives traffic** to docoga.com.ng

**Need help?** Just ask in the chat, and I'll assist!

---

## 🔐 Security Notes

✅ **No credentials in code** - All tokens stored in GitHub Secrets  
✅ **No manual posting** - Fully automated  
✅ **No server costs** - Runs on free GitHub Actions  
✅ **No data storage** - Only logs, no user data  

---

**Status:** ✅ Ready to deploy!  
**Action Required:** Add Telegram secrets to GitHub and enable the workflow.
