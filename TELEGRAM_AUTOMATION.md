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

## 🧾 13 Oct 2026 — one publish per content, and the ledger that proves it

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

### What is owed by a human, once

`gh secret set` and `gh variable set` are **not** runnable from the agent sandbox (the
Actions token gets `403 Resource not accessible by integration` on those endpoints, and
this `gh` build has no `variable` subcommand), and values are write-only everywhere. So:

1. GitHub → **Settings → Secrets and variables → Actions → Repository secrets →
   `TELEGRAM_CHAT_ID`** → set it to `@docogadaily` (or the `-100…` numeric id).
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
  the unreadable file beside itself as `*.corrupt-<timestamp>`.

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
