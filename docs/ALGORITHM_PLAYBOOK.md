# The algorithm playbook — what each platform ranks on in 2026, and what DocOga does about it

Owner, 21 Oct 2026: *"Improve more on all my social media. I want you to be able to beat
the algorithm — I want the platforms to think they have been hacked to get the amount of
result."*

Straight answer first. Nothing here hacks anything, and nothing here buys, fakes or
pods engagement — every one of those gets an account demoted or removed, and the owner's
accounts are the business. What *does* look like a hack from the outside is a small
account whose every post hits the exact signals the ranking model is built to reward,
on every surface, every day, without a miss. That is what this document specifies. The
sources are the platforms' own statements, dated; where a number is a third party's
estimate it says so.

## 1. What the platforms have said, on the record

| Platform | The ranking signals they named | Source |
| --- | --- | --- |
| **Instagram** (Feed, Reels, Explore) | **Watch time**, **likes per reach**, **sends per reach** — sends weigh more for reaching non-followers. Since 30 Apr 2026 accounts that mostly post unoriginal photos/carousels/Reels lose recommendations; eligibility returns when most posts in a rolling 30 days are original. Smaller accounts' originals are now tested on non-followers. | Mosseri, 22 Jan 2025; Instagram creators blog, 30 Apr 2026; Mosseri ranking videos, 24 Sep 2026 |
| **Facebook** (Feed, Reels) | Original content preferred; Reels views and time spent on *original* Reels roughly doubled in H2 2025; duplicates and minor edits of others' posts deprioritised; low-effort reaction/stitch content demoted. | about.fb.com, 14 Jul 2025 and 13 Mar 2026 |
| **YouTube Shorts** | The feed is a swipe test: **viewed vs. swiped away** is the first filter, then **average percentage viewed**, then genuine rewatches; a Short stops when its seed audience does not respond. A view counts from the first frame (31 Mar 2025); "engaged views" is the stricter metric. Mass-produced, templated content is "inauthentic" (15 Jul 2025) — AI narration itself is not disqualifying, a fixed formula is. | Todd Sherman / Creator Insider; YouTube Help, Shorts views; YouTube monetisation policies |
| **Threads** | Replies are the currency: "the sum of your replies is about as valuable as the sum of your posts"; longer replies count more; one **topic tag** per post places it in a topic feed; connected reach (followers) was re-weighted up in Nov 2024; engagement bait is penalised; explicit topic preferences ("Dear Algo", Feb 2026; "Your Algo", Jun 2026) make niche consistency matter. | Mosseri (Platformer); Meta Transparency Center |
| **TikTok** | Completion and rewatch, then shares; unaudited apps can only post to the owner's inbox as a draft, so the owner's one tap stays. | TikTok Content Posting API docs |
| **Telegram** | No ranking model: forwards and the views-to-subscribers ratio. | — |

Third-party estimates worth knowing but not citing as fact: a swipe-through above ~70 %
is the top band for Shorts (Galloway, 3.3bn Shorts); sends "3–5× a like" is a guess no
platform has confirmed.

## 2. What DocOga already does for each signal

* **Hook in the first two seconds** — the settled hook card is frame 0, the cover and the
  first spoken line (`tools/shorts_reel.py`, `docs/SHORT_COVER.md`).
* **Watch time / completion** — word-synced captions with the lit word, a clip or
  photograph per sentence, a change every 2–4 s, ≤ 90 s (`docs/SHORTS_MOTION.md`).
* **Sends per reach** — every brain post carries one send line that names a receiver
  (`brain/strategy.md`, `tools/brain.py` `cta`).
* **Originality** — our words, our voice, our motion, free footage transformed with
  text, graphics and narration that add information; no watermarks, no reposts.
* **Replies on Threads** — the replies lane answers three times a day
  (`brain_replies.yml`); polls in our own reply; one topic tag per post.
* **Timing** — Instagram posts at the hour the numbers chose (`brain/slots.json`);
  Threads at 7:20am, 1:10pm, 8:10pm; Shorts go public at 7:00pm.
* **Search text** — titles, descriptions and alt text carry the words ("rent receipt",
  "agency fee", "notice to quit") that captions burned into pixels do not.
* **First comment** on every Short with the parent Deep-Dive (`tools/yt_boost.py`).

## 3. Shipped 21 Oct 2026 — the Short becomes a Reel everywhere

The single largest unused lever was **distribution of a file that already exists**.
Reels are the recommendation surface on both Meta apps; the Short is original, 9:16 and
≤ 90 s (Reel-spec by construction, `tools/shorts_sound.py HARD_CAP_S`); yet it travelled
only to YouTube, TikTok's inbox, Telegram and Threads. Now, in the 6:00pm lane
(`.github/workflows/youtube_scheduled.yml`), after the hand-over to Threads:

1. **Facebook Reel — the same Short on the Page**: `scripts/post_facebook.py --reel`
   (three-phase `video_reels` upload) with a caption from `tools/reel_caption.py`; the
   30-day title ledger `logs/facebook_reels.json` stops a topic repeating (Mon/Thu keep
   their morning Reel — different title, so the Page's same-day guard lets both through).
2. **Instagram Reel — the same Short on @docoga.ng**: the third door
   (`tools/ig_publish.py --video-url`) fetching the **same 30-hour URL** the Threads
   hand-over parked on the worker, as a **Trial Reel** (non-followers first; falls back to
   an ordinary Reel where Meta refuses), recorded as `Reel · <topic>` in
   `logs/instagram_sent.json` with the same 30-day window.

Both steps are `continue-on-error`, switch off with the repository variable
`SHORT_REELS=off`, and are reported in the run summary and on the admin dashboard's
"plan in plain words" row for 6:00pm. Net effect: **five extra Reels a week on Facebook
and five on Instagram, ₦0, no new render, no new token.**

### The Reel caption (`tools/reel_caption.py`)

Built from the Short's own words, deterministic per date: the spoken hook sentence first
(≤ 125 characters — what shows before "more"; what search indexes), the tip headlines as
plain lines, **one send line that names a receiver** (the brain's `post.cta` when the day
has an approved pack, else a rotation of eight), the templates line (link on the Page,
"link in bio" on Instagram), four on-topic hashtags. Tests: `tools/tests/test_reel_caption.py`.

## 4. Shipped 22 Oct 2026 — the first hour

Every platform above weights what happens in a post's first hour: Instagram's ranked
"two-way conversation" (Mar 2026), Threads' replies-count-as-posts, YouTube's seed test on
the first few hundred views. Three changes, all ₦0, all on the account's own posts:

1. **The account's own first comment** (`tools/reel_caption.py --first-comment`,
   `tools/ig_publish.py --first-comment`). The moment the 7:10pm feed post or the 6:00pm
   Reel is live, @docoga.ng leaves one answerable question under it ("Which state are you
   renting in?") and the templates line. Eight questions rotate by day; the brain's `cta`
   wins when it is a question. It never fails the publish; the run prints
   `IG_FIRST_COMMENT=posted|refused`. No "like if", no "follow for" — bait is penalised.
2. **The Short in both Stories trays** (`youtube_scheduled.yml` → `fb_story`, `ig_story`).
   Stories sit at the top of the app through the 7–9pm peak and are the one surface where
   a tap goes straight to the video. Same `SHORT_REELS` switch, warnings never red.
3. **Replies within 30–45 minutes of every slot** (`brain_replies.yml`: 8:00am, 11:40am,
   2:40pm, 7:40pm, 8:40pm WAT — was 3 runs, 90 minutes behind). Replies to the first
   comments decide a post's second wave of distribution.

Measurement for all three is already in place — `tools/yt_stats.py` pulls average
percentage viewed and shares per Short; `tools/brain_scorecard.py` reads saves and shares
per Instagram media and ranks hook types; both land in the Monday scorecard once the brain
commits (fixed 22 Oct, PR #126).

## 5. Shipped 22 Oct 2026, night — TikTok search captions and reply depth

**TikTok is a search engine first.** TikTok indexes spoken words, on-screen text and the
caption; the caption's opening characters are weighted most and are all a viewer sees
before "more"; three to five hashtags, five being the in-app ceiling since Aug 2025; 150–300
characters is the search sweet spot, 2,200 the limit (metricool Aug 2026, rapidtags Sep 2026,
usefastlane Sep 2026). The old draft caption was the topic plus four tags. Now
`tools/reel_caption.py --platform tiktok` writes: *search phrase* ("Rent in Nigeria",
"Lagos tenancy law", … or the brain's SEO line for the day) → the spoken hook → two tips →
a save line → "link in bio" → five tags. **Why the owner saw no captions:** TikTok's inbox
API accepts none (only audited Direct Post does), and the Telegram DM that carries it waits
for a one-time handshake he has not done. So the full caption is now recorded in
`logs/tiktok_drafts.json` and shown on the admin dashboard (Social → *TikTok caption*) with
a **Copy** button; the run warns when it could not text it.

**Reply depth.** Threads weighs replies of eight-plus words; Facebook ranks on back-and-forth
of five-plus words. `tools/brain_replies.py` now refuses any reply under eight words or that
is only thanks (`REPLY_MIN_WORDS`, `THIN`), and the prompt asks for one fact or one question
back in every reply.

## 6. Shipped 23 Oct 2026 — the search phrase on screen

TikTok weights **on-screen text in the first three seconds** next to the spoken words, above
the caption; YouTube indexes the thumbnail frame the same way. The Short's opening masthead
— for three seconds and on the cover both platforms index — now reads the day's **search
phrase plus the episode number**: `RENT IN NIGERIA · No. 9`, `LAGOS TENANCY LAW · No. 10`,
`NOTICE TO QUIT NIGERIA · No. 11` (`tools/shorts_reel.py search_kicker`). It is the same
phrase the TikTok caption leads with (`tools/reel_caption.py tiktok_keyword`) — screen,
caption and query agree — and the brain's SEO line for the day wins when a pack exists. The
brand stays in the CTA chip, the handle scene and every caption. `SHORTS_SEARCH_KICKER=off`
restores `DOCOGA · TENANT TIPS · No. N`. Already there, checked and not rebuilt: the YouTube
first comment + series playlists (`tools/yt_boost.py`, every Short since 14 Oct has both), the
Threads topic tag, the Instagram first comment (§4).

## 7. Shipped 23 Oct 2026 — series weeks

From **Mon 26 Oct 2026** the weekday Shorts are a **five-part series on one law a week**
(`tools/series_week.py`): Rent receipt law → Tenancy agreement → Notice to quit → Caution
fee → Agent and landlord → Repairs and moving in, then round again. The spine is deterministic
from the date, so every lane agrees without talking: the cover and opening masthead read
`RENT RECEIPT LAW · 2 OF 5`; the end card carries a yellow pointer, `PART 3 TOMORROW · PAID,
NO RECEIPT. NOW WHAT` (tomorrow's *real* title once the brain has written it, the plan's label
until then; Friday: `SERIES COMPLETE · ALL 5 ON THE CHANNEL`); the YouTube title ends `(part 2
of 5) #Shorts`; the description and the Facebook/Instagram captions carry "Part 2 of 5 in this
week's series on the rent receipt law. Tomorrow: …"; the TikTok caption leads with the series'
own search phrase (`Rent receipt law Nigeria`). The brain writes each part to that day's angle
(its prompt gets the week's brief: today's part, yesterday's, tomorrow's, the tool page) and
stamps the part on the Short it approves; a day without a pack falls to the hand-written
rotation and wears the series **only when its own words fit the theme** — a photos Short never
pretends to be receipt law. Why it should move numbers: a numbered part is the cheapest binge
(a viewer who lands on 3 looks for 1 and 2 — session time), tomorrow has a name so the follow
has a reason, and five uploads that say they belong together are treated as one subject by
search. The dashboard plan shows the part. `SHORTS_SERIES_WEEK=off` is the switch.

Also fixed the same day: the brain's Short word budget. The prompt asked for 20–35 + 4 × 25–40
spoken words but refused anything over 160 in total — the arithmetic could not meet itself, and
weekday packs were being refused while weekend ones (no Short) passed. The prompt now says
20–28 + 4 × 25–32 with the budget spelled out, and every refusal is written to
`logs/brain_refused.json` (newest first, last 40) so a rotation day can be explained afterwards.

## 8. Next levers, in order of expected effect (Founder's brief items)

1. **A playlist per series week** — `yt_boost.py` keeps one Shorts playlist; a playlist per
   five-part run makes "Up next" play part 2 after part 1.
2. **Hook bans from the swipe test** — once two Monday pulls have filled
   `averageViewPercentage`, the bottom quartile's hook types go to the brain as "do not open
   like this" (`docs/HOOK_LEDGER.md`).

## 9. What we will not do, and why

Engagement pods, bought followers/likes/views, comment bots, follow/unfollow, mass DMs,
reposting other creators' videos, watermark-stripped reuploads, "like if you agree" bait.
Each is named in the platforms' own policies above; each gets reach removed or the
account closed, and the owner's accounts are the asset. The result that looks like a hack
is built the slow, legal way: every signal, every post, every day.
