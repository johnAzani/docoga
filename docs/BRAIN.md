# The Brain — DocOga's standing editor

*Built 16–17 Oct 2026 on the owner's instruction: "I don't want a bank. I want a
brain that can think like you, understands content creation and my business, so
that it works autonomously — everything automated. It only handles the social
media."*

## 🔒 THE BRAIN IS LOCKED — Gemini only (owner, 17 Oct 2026)
*"I don't want the gpt-oss. Use only Gemini and plan with it. Lock it in."*
Every model the brain, the replies lane, the weekly forum answer and the Deep-Dive
writer may call is a **Google Gemini model** (`gemini-*`, or Google's own `gemma-*`)
on the one host `generativelanguage.googleapis.com` — the same key, the same free
tier, the same quota ledger as the locked narrator voice. There is **no second
provider and no fallback to one**: when every Gemini rung is spent the night ends
with exit 6 (a pause, not a failure), the lanes post from the hand-written rotation,
and the brain tries again the next night. `tools/gemini_text.assert_locked` refuses
any other model name before a request leaves; `tools/qa.py` and
`tools/tests/test_brain_lock.py` refuse any change that names another provider or
hands the brain workflows another key. Never edit the lock; revert the change.

## What it is, in one paragraph
Every night at **01:30 Lagos**, before any posting lane wakes, `tools/brain.py`
reads the business memory, the editorial policy, the section-cited law shelf,
what it has said in the last 60 days and what the numbers said last Monday. It
asks Gemini (free tier) for **one pack per day** for the next three days — the
Telegram/Facebook post, the Threads/Instagram version, a visual brief for the
card, and on render days a Short/Reel topic — and publishes a pack only if it
passes five gates. The posting lanes read the pack at post time; when there is
none they fall back to the hand-written rotation. On Sundays it also drafts the
next Deep-Dive episode and queues it for the long-form lane. Nobody is pinged.


## Night one (17 Oct 2026, 05:48 Lagos — the scheduler was 4 h late)
`GEMINI_LADDER=ok`, all eight rungs served. Two of three days approved
(`kwara-rent-book-rule`, `advance-rent-cap-lagos`); 17 Oct fell to rotation after one
refusal for a 117-character line and one honest verifier refusal ("legal statement not
on the shelf" — the gate doing its job). Three of five attempts that night were refused
only for body lines of 115–125 characters, so the brain now carries **the editor's
pencil**: `tidy()` re-breaks an over-long line at a sentence or clause boundary before the
gates run — layout only, never a word. Guides showed `0 written` because pages are
written on the day a pack posts, not the night it is planned.
## Files
| Path | What |
|---|---|
| `brain/strategy.md` | **The plan** (17 Oct 2026): the one goal (Oga Pass sales), the funnel each post is built for, what every platform ranks on in 2026 and our move, the Nigeria posting windows, the content mix, the calendar, the 90-day goals and the orders the scorecard may issue. |
| `brain/audience.md` | **Five named readers** (Ngozi, Tunde, Mr Okafor, Amaka, Dayo): pains, hours online, who they send posts to, when they buy. Every pack names its `reader`. |
| `brain/goals.json` | The weekly rates and ratio floors the scorecard grades (edit numbers here, reasons in strategy.md). |
| `logs/scorecard.json` | One snapshot a week from `tools/brain_scorecard.py`: followers, views, sends, replies, hours, sales, grades, orders. |
| `brain/business.md` | **Owner-editable memory**: products, prices, audience, voice, words never used, the Nigerian calendar. |
| `brain/editorial.md` | **Owner-editable policy**: how a day is decided, weekday rhythm, hook archetypes, shape rules, visual brief, Short and Deep-Dive specs. |
| `brain/feedback.md` | Written every Monday by `brain.py feedback` from `logs/youtube_stats.json` and the said-ledger. |
| `brain/drafts/YYYY-MM-DD.json` | Approved packs (committed; pruned after 10 days). |
| `logs/brain_said.json` | The said-ledger: theme, headline, state, hook, fact ids per day (180 days). |
| `tools/brain.py` | The editor: `plan`, `status`, `feedback`, `deepdive`, `prune`. |
| `tools/brain_drafts.py` | How the lanes read a pack (stdlib only). `DOCOGA_BRAIN=off` is the kill switch. |
| `tools/brain_visual.py` | The photograph behind a card: Openverse CC0/public-domain, navy duotone, ₦0. |
| `tools/law_index.py` | `tools/state_law_data.py` flattened into citable facts with ids (`lagos:receipts:7`). |
| `tools/gemini_text.py` | The one door to Gemini text: model chain, 429 handling, JSON. |
| `.github/workflows/brain.yml` | The nightly lane. |

## The plan, the scorecard and the orders (17 Oct 2026)
The brain is held to `brain/strategy.md`. Every Monday 06:40 WAT `brain_scorecard.yml`
reads what the repo can read — Facebook Page insights (the Page token carries
`read_insights`), Instagram and Threads insights (the vault tokens), the Telegram
member count, the YouTube snapshot, and, when the owner adds the dashboard passphrase
as the repo secret **`DOCOGA_ADMIN_PASSPHRASE`**, passes sold and ₦ revenue from the
owner dashboard (`/admin/login` → `/admin/data` → `/admin/logout`, one session a
week). It grades each number against `brain/goals.json` (growth per week, ratio
floors), escalates anything behind two weeks running, and writes **orders** —
deterministic sentences from the rules in strategy.md ("sends under 1.5%: STAKES
hooks and a named-person send line in every post"). `brain.py feedback` folds the
scorecard into `brain/feedback.md`; the nightly prompt carries the strategy, the
audience and the orders under "obey the orders".

Two shape rules came with the plan, enforced by the lint: every pack has a
`post.cta` — a send/forward/reply line naming a receiver or asking a five-word
question (sends are what 2026 feeds rank on; forwards are all Telegram has) — and
every Threads post ends with a question (replies are what Threads ranks on). The
2026 metric names are used throughout (`page_total_media_view_unique`,
`post_media_view`, `views`/`reach`/`saved`/`shares`); `impressions` and `page_fans`
are gone from the API.

Posting slots moved to the windows the Nigeria data names: Threads 13:10 WAT
(lunch), Instagram 19:10, Facebook evening Story 19:40; Telegram 09:00 and the
Facebook post 09:30 stay. The scorecard records the hour each post went out, its
engagement by hour, and Instagram's `online_followers` curve, so the slots are
corrected from evidence.

## Special days (23 Oct 2026)
`tools/events_calendar.py` feeds `calendar_notes(day)`: Christmas, Independence Day, Children's
Day, Democracy Day, the Eids, Easter, New Year, Workers' Day, World Habitat/Tenants' Day — each
with a tenancy angle, a lead-in window and the rule "one greeting line at most; the post still
teaches one rule with a fact id". The card renderer reads the same table for the flag ribbon
(national days) and the masthead greeting; the dashboard lists the next ones. `docs/SPECIAL_DAYS.md`.

## The community manager, the learning loop and the deep links (17 Oct 2026)
**Replies.** `tools/brain_replies.py` + `.github/workflows/brain_replies.yml` (8:00am,
11:40am, 2:40pm, 7:40pm and 8:40pm WAT — within 30–45 minutes of every posting slot, since
22 Oct 2026). Lists our last three days of
posts on Threads (`/me/threads` → `/{id}/replies`), Instagram (`/me/media` →
`/{id}/comments`) and the Facebook Page (`/{page}/posts` → `/{id}/comments?filter=toplevel`);
drops our own comments, already-answered ones (ledger `logs/brain_replied.json` *and* the
platform's own reply list), emoji-only and abusive ones; asks Gemini once for all pending
replies with each post's text, the pack of that day (state, reader, the facts it cited) and
the deep link; gates every reply (`lint_reply`: ≤280 chars, sections must be on that
state's shelf, no price but ₦2,000/free, no "stop paying"/"you will win"/"guarantee", only
docoga.com.ng links, no markdown/hashtags, no "as an AI"); publishes — Threads as a
container with `reply_to_id` then `threads_publish`, Instagram `POST /{comment}/replies`,
Facebook `POST /{comment}/comments`. Capability detection: a permission error (OAuth code
10/200/190, HTTP 401/403, "permission" in the message) stops that platform for the run and
the summary names the scope — `threads_read_replies`, `instagram_business_manage_comments`,
`pages_manage_engagement` — so the owner knows exactly which token to re-mint. Exit 6 when
Gemini's quota is spent (replies wait for the next slot). Kill switch `DOCOGA_BRAIN=off`;
dispatch inputs `dry_run`, `platform`.

**Learning loop.** `brain_scorecard.learning` joins each Facebook/Instagram/Threads post to
the pack the brain wrote for that Lagos date (`logs/brain_said.json`, env
`DOCOGA_BRAIN_SAID`) and averages the channel's engagement score by `hook_type`,
`post_type`, `reader` and source (brain vs rotation). The summary carries the table; the
orders name the best hook and reader once there are two or more posts per label and a 1.5×
gap. `kpis["learning"]` is in `logs/scorecard.json`, so next week's comparison is free.

**Weekly issue.** The scorecard keeps **one** open issue titled "📊 Weekly scorecard"
(label `brain-scorecard`): body replaced with the latest summary, one comment added so the
owner's phone gets one notification a week. `issues: write` was added to that workflow for
this alone; nothing else opens issues.

**Deep links.** Pack schema gained `tool` (one of `brain_drafts.TOOLS` or null; the lint
refuses anything else). `brain_drafts.link_for(pack)` → `https://docoga.com.ng/<tool>-<state>.html`
when that page exists in `site/`, else the national `<tool>-nigeria.html`, else the homepage.
`post_text`, `threads_text` and every reply use it.

## The reach layer (17 Oct 2026, fourth round)
Seven changes from the "every platform signal, every Nigeria number" research, all ₦0:

**Newsdesk.** `tools/newsdesk.py` + `brain/newsdesk.json`: a hand-kept shelf of dated rent
and tenancy news hooks (the Lagos ₦200k→₦350k hike, Abuja +40–120 %, the Lagos Tenancy
Bill still not law, Enugu's 10 % agency cap bill…). The brain's prompt carries the
freshest live hook for the day's state; the lint refuses a hook that has gone stale or
that the shelf does not know. Nothing is invented: a hook is a line the owner (or a PR)
wrote with a date and a source. Env `DOCOGA_NEWSDESK` points tests at a fixture.

**Threads upgrade.** Pack gains `threads.topic` (one topic tag from
`brain_drafts.TOPIC_TAGS`, 1–50 chars, no `#`/`.`/`&`) and `threads.poll` (2–4 options,
1–25 chars each, text posts only). `tools/threads_publish.py` sends `topic_tag`,
`poll_attachment` and `crossreshare_to_ig` and **falls back** one extra at a time when
Threads refuses one (`THREADS_EXTRAS_DROPPED=…`), so the words always post. Cross-sharing
to Instagram needs the Threads token re-minted with `threads_share_to_instagram`; the
summary prints `THREADS_SHARE_TO_IG=<status>`. Variable `THREADS_SHARE_TO_IG` (default
`on`).

**Instagram Trial Reels.** `tools/ig_publish.py --trial` adds
`trial_params={"graduation_strategy":"SS_PERFORMANCE"}` to Reel containers: Instagram
shows the Reel to non-followers first and graduates it to followers when it performs —
the free way to buy reach for a new account. Refused → plain Reel (`IG_TRIAL=refused`).
Variable `IG_TRIAL_REELS` (default `on`).

**Telegram quiz.** Tuesdays the pack carries `quiz{question, options, correct,
explanation, fact_id}`; the lint demands the fact be on the shelf and the explanation
carry its citation. `scripts/post_telegram.py send_quiz` sends a native quiz poll after
the post (`sendPoll type=quiz`, ≤200-char explanation that reveals the section);
`TELEGRAM_QUIZ=sent|failed`, never fatal. Research: polls lift Telegram engagement past
50 % and a quiz answer is a tap from a reader who would not type.

**LinkedIn lane.** `tools/linkedin_publish.py` / `linkedin_autopost.yml`, Mon/Wed/Fri
08:30 Lagos, the brain's pack in little-text format to the owner's profile. 60-day token
clock with a day-50 warning. Handbook: `docs/LINKEDIN_AUTOMATION.md`.

**TikTok inbox drafts.** `tools/tiktok_draft.py` rides the Shorts lane: the same Short
into the owner's TikTok inbox (the only unaudited route that is not forced-private); the
owner pastes the caption and posts. Handbook: `docs/TIKTOK_AUTOMATION.md`.

**Template fix.** The Telegram templates said "3 months' notice" for a yearly tenant in
Lagos; s.13(1)(e) says six months. Fixed — the brain's lint would have refused it from a
model; the hand-written rotation needed a human to read it.

## The money layer (17 Oct 2026, fifth round — "which channel pays, and what each platform needs before it pays")
Seven changes, all ₦0; the payment flow is untouched (attribution is counters, never checkout).

**Channel → revenue attribution.** Every link the lanes post carries a channel tag
(`brain_drafts.tag_links`: `?s=tg|fb|ig|th|li|tt|yt|wa`; hand-written Telegram templates go
through `tag_links_mdv2` so MarkdownV2 stays valid). `site/index.html` remembers the first
`?s=` / `utm_source` / Google referrer for 30 days (`localStorage.docoga_src`); the Buy
button fires `POST /tap {kind:checkout, src}` (keepalive) and `success.html` appends `&src=`
to the verify call. The worker counts `src:<checkout|sale>:<channel>:<ISO week>` in KV (60-day
TTL) and exposes `sources{checkout,sale}` in `/admin/data`. The scorecard turns that into
`sales.by_source_28d/7d`, `sales.checkouts_by_source_28d` and the order **"Money follows
X"**. Site traffic by channel comes from Cloudflare Web Analytics (`tools/site_analytics.py`,
GraphQL `rumPageloadEventsAdaptiveGroups`; secrets `CLOUDFLARE_ACCOUNT_ID` +
`CF_ANALYTICS_TOKEN` (live since 17 Oct 2026); the site tag is discovered from the account's site list or the beacon on the live page, var `CF_WEB_ANALYTICS_SITE_TAG` only overrides it; `SITE_ANALYTICS=ok|not-connected`). Prove it any time: Actions → *Site analytics — is Cloudflare connected?* → Run workflow.

**Search demand.** `tools/search_console.py` rides the Monday stats lane with the YouTube
OAuth client: 28 days of Google queries for docoga.com.ng, Nigeria first, written to
`logs/search_console.json` (`clicks, impressions, ctr, top_queries, striking_distance (pos
5–20, ≥20 impressions), top_pages`). The brain's prompt gets **"what Nigerians type into
Google before they find us"** when the file is ≤21 days old; the scorecard grades
`google.clicks_28d`. Needs the `webmasters.readonly` scope on the same refresh token — one
re-consent (below). Without it: `SEARCH_CONSOLE=missing-scope`, a notice, never red.

**Facebook link in the first comment.** `scripts/post_facebook.py` posts the words
link-free and puts the link in the first comment (`POST /{post_id}/comments`); when the Page
token cannot comment (`pages_manage_engagement` missing) it edits the post to carry the link
instead, so no day loses it. `FB_LINK=comment|body`; variable `FB_LINK_IN_COMMENT=off`
restores the old shape. Research: a link in the body reaches ~0.20 % of followers, a native
post ~0.80 %.

**Threads evening slot.** `threads_autopost.yml` runs twice: 13:10 WAT and **20:10 WAT**
(`generate_threads_content.py --slot evening`): the evening post is link-free words
(`threads.evening` in the pack, else headline + first line + send line) with the link in
**our own reply** (`reply_to_id`). Reply refused → warning. `THREADS_REPLY=sent|failed`.

**A Short is detailed, not points (17 Oct 2026).** Owner: "like the long form video". Every
slide carries `say` — the explanation the locked narrator reads (hook 20–35 words, tips
25–40, the five together ≤ 160 = `brain.SAY_TOTAL_MAX`, so a Reel stays under 90 s). The
brain must write `short.hook_say` and `tips[].say` (`short_problems` refuses a Short
without them or over budget; the verifier sees them with the rest of the Short); the six
rotation scripts in `scripts/generate_short_video.py` carry their own. `shorts_sound.
narration_for` reads the `say`, `fit_scenes` stretches the scene to the clip, and
`caption_beats` captions the scene like a Deep-Dive: one MotionStudio **`caption`** beat
per sentence, timed by its share of the clip, fading in and out under the headline inside
the safe zone (the sub-line beat makes way — the captions are the explanation). Render
and QA share the caption's events, so the motion engine still passes. `HARD_CAP_S` = 90.
A slide without `say` (older packs) reads headline + sub-line as before.

**The picture matches the words (17 Oct 2026).** Owner: "You can use free images and video
clips in video … behind the cards — make sure it matches what is being said."
`tools/shot_match.py` is the one place every renderer asks what to show behind a line:
the brain's hint (`beats[].shot`, 2–4 words, validated like `visual.plate`) → the glossary
read of the words themselves (the THING said beats the place beats the role: "the landlord
must give you a receipt" → `paper receipt`, "lock you out without a court order" →
`padlocked door`) → the Nigerian street. Openverse CC0/public-domain only (₦0, no key, no
attribution debt); every result is scored against the query (title + tags must share a
word) and a pretty-but-wrong picture is refused; nothing matched → the renderer's old look
(Deep-Dive named plate, Short navy, card navy). Wired into **Deep-Dive beats**
(`deepdive.plate_for_beat`, brand duotone via `treat_plate`), **Short scenes**
(`shorts_reel.attach_shots` → `scene._bg`; MotionStudio QA now measures content against
the scene's own background), and **every card** (`social_card._brief(said=…)`, rotation
cards included). Searches are paced (~20/min) and cached under `assets/plates/` with
provenance. **Explicitly on**: each publishing workflow passes
`DOCOGA_SHOTS: ${{ vars.DOCOGA_SHOTS || 'on' }}`; unset (tests, qa.py, laptops) = off, so
nothing reaches Openverse by accident; repo variable `DOCOGA_SHOTS=off` is the kill switch.
*Video clips*: Pexels has paused new keys, Openverse indexes no video and Pixabay's free
video API needs a key — clips are the next step once a key exists; stills with camera drift
carry the motion today.

**Every Threads post carries a card (17 Oct 2026).** Owner: "the Thread is only text it
uploads." The evening image used to borrow the Instagram lane's card, which exists only on
days that lane rendered; Threads went out as words. Now the lane draws its **own** card each
slot (`site/social/<day>-threads.jpg`, `<day>-threads-evening.jpg`; `card_path`/`image_url`
in the content JSON), commits and pushes it to the default branch (the push deploys the
site; no skip-CI marker), and `threads_publish.py wait_until_live` polls the URL until it
answers 200 (`--image-wait`, default 600 s) before creating the IMAGE container with
`alt_text`. Not live / refused → the words post as TEXT (`THREADS_IMAGE=dropped`), never a
red run. A poll cannot sit beside an image, so on poll days the card wins and the poll is
asked in our own reply (`THREADS_POLL_REPLY=sent|failed`). `social_card.prune` recognises
the Threads renders, so the 60-day window still holds.
(Also fixed: `approve()` now carries `threads.topic` and `threads.poll` into the pack — the
fourth round wrote them but dropped them on the way to the lanes.)

**Instagram SEO.** Caption opens with the search phrase (`brain_drafts.seo_line`: "Rent
receipt format Nigeria (Lagos)"), the link carries `?s=ig`, and the card gets alt text
(`brain_drafts.alt_text`, ≤1,000 chars) via `ig_publish.py --alt-text` on photos and carousel
items. Google indexes professional accounts' posts since 10 Jul 2025.

**Weekday Shorts + Telegram native video.** `youtube_scheduled.yml` runs every weekday 18:00
WAT (Mon + Thu added 17 Oct 2026 — the Reels lane narrates the same topic that morning and the
voice comes back from the shared cache, so the extra Shorts cost the narrator nothing; brain
`SHORT_DAYS` is Mon–Fri). After every YouTube upload, `tools/telegram_video.py`
posts the same MP4 to the Telegram channel with `sendVideo` (≤50 MB, caption with the
tagged link and the YouTube URL); refused or oversized → the link as text.
`TELEGRAM_VIDEO=sent|link|skipped|failed`, never fatal.

**Milestones and slot advice.** `brain/goals.json` → `milestones`: Facebook 500 followers
(Stars, 30 straight days), YouTube 500 subscribers (fan funding), Instagram and Telegram
1,000. The scorecard measures the four-week pace, prints weeks-to-go and needed-per-week, and
issues orders when a milestone is behind its date or reached. `slot_advice` compares
Instagram's `online_followers` peak with our 19:10 WAT slot and says when to move it.

### The one Google re-consent (adds Search Console + YouTube Analytics)

*17 Oct 2026: done from the phone through `google_consent.yml` — `docs/TOKENS.md` § 4 has the three taps; the token lives in the vault, not the secret.*

*The complete scope list for this consent — and for every other token — is `docs/TOKENS.md` (code: `tools/token_scopes.py`). Mint with all of it once; the Monday scorecard audits and says what, if anything, is missing.*
On the phone: Google Cloud console → APIs & Services → **Library** → enable "Google Search
Console API" and "YouTube Analytics API" → **OAuth consent screen → Data access → Add or
remove scopes** → tick `…/auth/youtube.force-ssl`, `…/auth/yt-analytics.readonly`,
`…/auth/webmasters.readonly` → Save. Then redo the consent exactly as in
`docs/LAUNCH_SEQUENCE.md` Step 3 (same client id/secret) and paste the new refresh token into
the `YT_REFRESH_TOKEN` secret. Next Monday 06:00 WAT the stats lane prints `SEARCH_CONSOLE=ok`.

## The conversion layer (17 Oct 2026, sixth round — "the tap, the forward and the inbox")

| piece | where | what it does | machine line |
|---|---|---|---|
| Telegram inline buttons | `brain_drafts.telegram_buttons`, `scripts/post_telegram.py` | row 1 "📄 Open the free tool" → the pack's exact page `?s=tg`; row 2 "💬 Share on WhatsApp" (`wa.me/?text=` headline + `?s=wa` link) and "↗️ Forward on Telegram" (`t.me/share/url`). `buttons_allowed` asks `getChat`: a linked discussion group means no buttons (comments outrank them); `TELEGRAM_BUTTONS=off|force` | `TELEGRAM_BUTTONS=sent|off|skipped-comments|unchecked` |
| Instagram carousel | `brain_drafts.carousel_slides`, `social_card.py --slides --brief DAY`, `instagram_autopost.yml` | every weekday (`IG_CAROUSEL_DAYS`, ISO weekdays, default `1,2,3,4,5`; was Tue/Thu until 18 Oct 2026): hook slide, one slide per pack line, close slide — from the brain pack, else from the rotation copy (`social_card.rotation_slides`, `CARD_SLIDES_SOURCE=`); `CARD_URLS` → `ig_publish --image-urls`; `CARD_SLIDES=0` falls back to the single card. The pruner keeps 60 *days* of renders (card + story + slides). `IG_CAROUSEL=off` | `CARD_SLIDES=<n>` |
| Comment → DM | `brain_replies.py` (`wants_link`, `dm_text`, `send_dms`, `Instagram.private_reply`, `Facebook.private_reply`) | a comment that asks ("link", "send", "template", "how do I get", "abeg", "interested"…) gets one private reply with the tool name and the channel-tagged deep link — template text, no quota. IG: `POST /{ig-user}/messages {recipient:{comment_id}}` needs `instagram_business_manage_messages` (`instagram_manage_messages` on the Facebook-Login path); FB: `POST /{page}/messages` needs `pages_messaging`. A permission refusal parks the lane for the run and the summary names the scope. Recorded in `logs/replied.json` as `dm_id` even when Gemini's quota is spent, so a comment is never messaged twice. `BRAIN_DM=off` | `REPLIES_DM=instagram=ok|missing,facebook=…` |
| Slot gate | `brain_scorecard.slot_plan/slot_hour`, `brain/slots.json`, `instagram_autopost.yml` job `slot` | the lane fires 06:10/12:10/18:10 UTC; the `slot` job prints `SLOT_HOUR_WAT` and only the chosen hour (±1 h for scheduler lag) runs `publish`. Monday's scorecard rewrites the plan: our own engagement by posting hour when two windows have ≥3 posts and the better one leads by ≥25 %, else Instagram's `online_followers` peak when it is ≥2 h from the current slot and within 1 h of a window; otherwise the slot stays. Dispatches always post | `IG_SLOT=go|skipped hour=H chosen=W` |
| Hook bandit | `brain.hook_order` | UCB1 over the seven hook archetypes using the scorecard's `learning.hook_type` (n, avg); excludes the last two days' hooks; before the numbers exist (two hooks with n ≥ 3) it is advice and the least-used hook in 28 days; after, `lint` refuses a pack whose `hook_type` is not the chosen one | prompt line "Hook for today: …" |
| Pinned newsdesk | `brain/newsdesk_pinned.json`, `newsdesk.pinned_items` | hand-dated, sourced headlines merged ahead of the RSS pull; each expires 21 days after `published`; `_note` says what the brain may and may not claim | — |
| Heartbeat fix | `automation-heartbeat.yml`, `linkedin_autopost.yml`, `test_workflow_contract` | the judge step ran under GitHub's default `bash -e`; the tool's deliberate exit 1 ended the step before `signature=` was written, so the filing step saw nothing and refused to file — four red nights, no issue. `set +e` around the pipeline; a contract test forbids reading `PIPESTATUS` with errexit on, in every workflow | — |

## The seventh round (17 Oct 2026 — "every channel growing, the account getting fat, ₦0")

**Listening (`tools/listening.py`).** The newsdesk hears the papers; this hears the
people. Every night the brain GETs the thread titles on Nairaland's Properties,
Family and Politics boards and r/Nigeria (no API, no login, no posting), scores
them (problem words up, question words up, adverts down) and keeps the top 12 in
`brain/listening.json`. The prompt carries them as **WHAT NIGERIANS ASKED THIS
WEEK**, so a day's post opens by answering a real question in the reader's words.

**The forum answer (Mondays).** `tools/listening.py answer` drafts ONE reply to the
best open thread from the law shelf, gated exactly like a post (every legal
sentence cites a shelf fact and appears verbatim; the DocOga link and the
"not legal advice" line are mandatory), writes `brain/answers/YYYY-MM-DD.md`, and
the Monday scorecard issue carries it under **✍️ Forum answer — paste this**. The
owner pastes it by hand — Nairaland has no posting API and an automated account
there is a ban, not a channel. One thread is never answered twice. Dispatch
`forum_answer=true` to draft one on any day.

**Guides (`tools/guides_build.py`).** Every approved pack dated today or earlier
becomes a cited page at `docoga.com.ng/guides/<theme>-<state>.html` — headline,
the post's lines, "The law behind it" (section + statute from the shelf), the
Tuesday quiz as a FAQ with `FAQPage` schema, the tool link for the post's state
(`?s=g` so the scorecard sees it), the standing footer — plus `guides/index.html`,
`guides/guides.json` and new `<url>` entries in `sitemap.xml`. Nothing is generated
here: a page is a faithful re-layout of a pack that already passed the gates; a
pack with no cited law is not a page. The brain's own commit publishes it (the
site is static files on Cloudflare — ₦0). The only part of the brain that touches
the website: it writes under `site/guides/`, the sitemap and the IndexNow key
file, never a tool page, never the payment flow. **Variable `BRAIN_GUIDES=off`
turns it off.** Optional: set variable `INDEXNOW_KEY` (8–128 letters/digits) and
the builder commits `site/<key>.txt` and pings IndexNow (Bing/Yandex/Naver, free)
after each build; Google reads the sitemap.

**Captions (`tools/yt_captions.py`).** After a Deep-Dive uploads, its own Vosk
word timings (`words.json`) become an SRT (≤2 lines × 42 characters, 1–6 s cues,
broken at sentences) and go up as the "English (DocOga)" track — `captions.insert`,
400 quota units a week, `youtube.force-ssl` (already held). YouTube indexes caption
text for search; phones watch muted. Never fails the publish. Synthetic timings
are refused.

**The description funnel.** YouTube's Shorts→long-form "Related video" is a Studio
tap with no API (the Shorts run summary names the one tap). So the Deep-Dive
description now ends with "60-second versions (Shorts)" and "Earlier Deep-Dives" —
the latest *public* ones from the ledgers — and the viewer who finished one has the
next in reach.

**Instagram collaborators.** Variable `IG_COLLABORATORS` (up to 3 public usernames,
comma-separated) is sent as `collaborators` on photo, carousel and Reel containers
(never Stories, never carousel children). Each account gets an invite once; when
they accept, the post sits on both profiles. Borrowed audience for ₦0. Blank = off.

**approve() now saves what it linted.** `tool`, `reader`, `post.cta`, `quiz` and
`news_hook` were checked by the gates but dropped from the saved pack — so every
deep link fell to the homepage, no Tuesday quiz ever reached Telegram, the money
line never rendered and the reader-learning column stayed "unnamed". Fixed and
tested (`tools/tests/test_round7.py`).

## The gates (why a legal-documents brand can let a model write)
1. **Citation** — every legal claim names a fact id on the shelf for the state
   the post names. The shelf is `tools/state_law_data.py`, the same verified,
   section-cited data the state pages are built from. No id, no claim.
2. **Verification** — a second model call, strict temperature, reads the facts
   and the finished post and must find every claim supported and no legal
   statement that is not on the list. Disagreement refuses the pack.
3. **Brand lint** — lengths per channel (≤ 900 Telegram/Facebook, ≤ 480 Threads
   with link and disclaimer), banned phrases, no price other than ₦2,000 / the
   ₦50,000 lawyer anchor unless quoted from a cited fact, no markdown, no
   shouting, the section number named in cited posts, no emoji in the headline,
   kicker or Short, a plate brief with no faces or signs.
4. **Repetition** — a theme used in the last 21 days or a headline 60% the same
   as any in the last 60 days is refused.
5. **Shape** — a Short topic on Mon/Tue/Thu/Fri must be exactly the MotionStudio
   grammar (hook ≤ 64 chars, four tips ≤ 5 words each with a ≤ 9-word sub-line);
   a Deep-Dive must have nine sections of 120–200 words, 36–48 beats whose
   trigger words appear in order, known plates, and pass
   `python3 tools/deepdive.py ddN check` — the engine's own test.

A refused day is not an incident: the lane posts from the rotation and the run
summary says why the brain's draft was refused.

## Quota (free plan, forever)
Research of 16 Oct 2026: Google no longer publishes free-tier limits; projects
have seen the Flash daily bucket at **20 requests** since December 2025, and the
buckets are **per model**. The brain therefore spends **2–3 requests a night**
(one plan, one verify, at most one retry per day planned) on a chain
`gemini-3.8-flash → gemini-2.5-flash → gemini-2.5-pro → gemini-3.5-flash → gemini-3.5-flash-lite → gemini-2.5-flash-lite → gemini-3.1-flash-lite → gemini-flash-lite-latest`
(`BRAIN_MODELS` variable overrides; the replies lane runs the Lite rungs first — ~500/day each).
**Why the ladder changed (17 Oct 2026):** since 18 Sep 2026 Google serves the 2.5
text models only to projects that used them before that date and points new
projects at 3.8 Flash / 3.5 Flash-Lite; 2.5 Pro joined the free tier; 2.0 Flash is
retired. A rung the key is not served answers 403/404 and costs nothing — the chain
steps down. Every brain run starts with `python3 tools/gemini_text.py probe`
(ListModels, no quota): the summary lists ✅/— per rung and `GEMINI_LADDER=ok|thin|empty`;
`empty` is the one case that is an error line.
 A per-minute 429 is waited out once; a per-day
429 moves to the next model; when every model is spent the lane exits **6** — a
pause, not a failure, no issue opened — and tries again the next night. Thinking
is capped (`thinkingBudget`) so the JSON always fits the output ceiling. The
narrator's TTS bucket is untouched. Image models have **no** free tier, so the
brain never asks for a picture.

## Pictures
The brain is the art director, the renderer is the designer. The brief names a
`kicker`, a `layout` (`poster`, `stat` with a big figure, `checklist` with numbered
lines) and a `plate` (2–4 words). `tools/brain_visual.py` searches **Openverse**
anonymously (no key; CC0 / public domain only, so no attribution duty), rejects
titles with faces or signs, downloads one original, pushes it through the brand
duotone, darkens, grains and scrims it, and the card's type goes on top. If the
search fails, is slow, or returns nothing, the card is the flat navy card. The
Instagram lane passes `--brief "$DAY"` to `tools/social_card.py` so its card and
Story carry the same brief.

## Deep-Dive writer
Any night (since 21 Oct 2026; Sundays only before that) when `episodes/queue.json` has
nothing unpublished **and** the last long-form upload is four or more days old — one
episode a week is the cadence, the publishing calendar gives each its own Saturday — or
`workflow_dispatch` with `deepdive=true`: one call writes title, nine
sections, beats, cover brief and YouTube meta; the gates and a verification call
run; `episodes/ddN/` is written with the **locked voice block copied byte for
byte** from the previous episode and the sound plan; the id is appended to the
queue; `deepdive.py ddN check` runs. The nightly Deep-Dive lane then narrates,
renders and uploads it exactly as it does today. YouTube privacy stays whatever
`YT_PRIVACY` says — that is the owner's one look before the public sees it.

### Why the lane was idle 15–21 Oct 2026, and what changed
The writer existed but produced nothing on Sunday 18 Oct, and nothing it refused left a
trace in the repo (run logs are not reachable from everywhere). Three fixes:
- **Self-healing before the gates** (`brain.heal_deepdive`): a beat whose trigger words are
  not spoken is dropped (beats are overlays), an invented plate falls back to `letter`, an
  over-long sub is cut at a word, a shot naming people is dropped, tags/description/title are
  brought to shape. Narration, claims and the section count are never touched — those stay
  the writer's to get right and the verifier's to judge.
- **Three attempts** (`DD_ATTEMPTS`), each retry carrying the previous refusal.
- **A ledger of every attempt** — `logs/brain_deepdive.json` (`written` / `refused` /
  `engine-refused` / `quota`, with the reasons and what was healed) — plus a run annotation
  (`Deep-Dive written` / `Deep-Dive not written tonight: <why>` / `writer paused`) and the
  machine lines `BRAIN_DEEPDIVE=`, `BRAIN_DEEPDIVE_TITLE=`, `BRAIN_DEEPDIVE_WHY=`.

### 🗓 Scheduled, not dumped (owner, 17 Oct 2026: "scheduled in YouTube for the date intended to go public")
With `YT_PRIVACY=public`, no upload goes live the second it lands. `tools/yt_publish.py` sends
a public upload as **private + `status.publishAt`** — YouTube's own scheduler flips it to public
at that instant, and Studio shows it as *Scheduled* until then. The intended moment:
- **Shorts** (rendered every weekday 18:00 WAT): today at the slot hour — `YT_PUBLISH_HOUR_WAT`,
  default **19:00 WAT** (the measured Nigerian prime window 19:00–20:30). A late run (scheduler
  lag) schedules the next 5-minute mark at least 10 minutes out, never the past.
- **Deep-Dive** (produced 03:00 WAT): `episodes/<id>/episode.json → youtube.publish_at`
  (`YYYY-MM-DD` = that day at the slot hour, or an ISO instant, WAT) when set; else (21 Oct
  2026) the **next free Saturday at 7:00pm** from `tools/publish_calendar.py` — "free" read
  from both YouTube ledgers, so two episodes in one week take two Saturdays.
- **Queue** (`youtube_queue.json`): an item's `publish_at`, same formats.
`unlisted`/`private` are never scheduled. `YT_SCHEDULE=off` (repository variable) restores
publish-at-once. Read-back reports `YT_UPLOAD_RESULT=scheduled`, `YT_PUBLISH_AT=<UTC>`,
`YT_PUBLISH_AT_WAT=<Lagos>`; the ledger carries `publish_at`; `YT_PRIVACY=public` is the intended
state (`YT_PRIVACY_NOW=private` this minute) so cross-links and the scorecard count it as a
public video from the start.

## Running it by hand
```
python3 tools/brain.py status                 # the next 7 days: pack or rotation
python3 tools/brain.py plan --days 3          # needs GEMINI_API_KEY
python3 tools/brain.py plan --dry-run --date 2026-10-20
python3 tools/brain.py feedback
python3 tools/brain.py deepdive --dry-run
python3 tools/law_index.py lagos              # the shelf the brain sees
python3 tools/brain_scorecard.py pull --dry-run  # the Monday numbers, graded, nothing written
python3 tools/brain_scorecard.py summary      # the latest scorecard block
```
Edit `brain/business.md` or `brain/editorial.md` to change what the brain knows
or how it decides; nothing in the code needs to change for that.

## Visibility round (17 Oct 2026) — what the research changed

Owner: "research in depth to the thinnest details; improve visibility on all my platforms."
Sources: YouTube's 2026 Shorts data (Metricool 800K videos; 61 % of Shorts views from the Shorts
feed; channels under 10K subscribers +200 % Shorts views in a year; 3–5 a week), Mosseri's
2026 Instagram signals (watch time, likes per reach, **sends per reach**; captions over
hashtags), Meta's UTIS Reels model and original-content rule (Jan/Mar 2026), the Threads
studies (reply rate first; images +60 %; peak 7 am), and the Threads/YouTube API references.
Everything below is ₦0 and runs itself.

- **Five Shorts a week, not three.** `youtube_scheduled.yml` cron `0 17 * * 1-5`. Monday and
  Thursday reuse the Reels lane's narration from the `shorts-voice-v2-*` cache.
- **Every video joins its series playlist and gets the channel's first comment**
  (`tools/yt_boost.py`; Shorts lane, Deep-Dive lane, and the 19:20 WAT sweep
  `youtube_boost.yml` that posts the comment once a scheduled video is public and catches up
  older videos four a night). Playlists are YouTube's session signal and a search result of
  their own; the comment carries the Deep-Dive link a Short's player cannot and asks the
  question that starts the thread. Ledger `logs/youtube_boosts.json`.
- **Shorts descriptions YouTube search can read**: the spoken hook sentence, the tip headlines,
  three hashtags, the Telegram channel — after the parent Deep-Dive link, which stays first.
- **A transcript page for every Deep-Dive** on docoga.com.ng (`tools/video_pages.py` →
  `site/videos/<id>.html`, VideoObject JSON-LD with chapter clips, the player, the tool link,
  sitemap + IndexNow). Google indexes pages; it never indexed the MP4.
- **Threads morning slot, 07:20 WAT**: the day's Short hook as a question, image post, no link
  (`generate_threads_content.py --slot morning`). Three posts a day; the question rotates.

Known limit, written down so nobody chases it: replying to *other people's* Threads posts by
keyword (`/keyword_search`) only returns public posts after Meta App Review approves
`threads_keyword_search`; until then the endpoint searches our own posts. Not built.


## Deep-Dive promotion (17 Oct 2026) — every channel trails the episode

Owner, 17 Oct 2026: *"Also remember to promote deep dives in the other social media channels."*
Until now a Deep-Dive lived on YouTube alone (plus the Shorts' description link). `tools/deepdive_promo.py`
now rides the **existing** lanes — no new workflow, no new cron, no new token — and the week after an
episode goes public looks like this (P = the day the episode's YouTube slot passes, 19:00 WAT Monday):

| When | Channel | What goes out | Why this shape |
|---|---|---|---|
| P 20:10 WAT | Threads evening | **Launch** — "New Deep-Dive, just published: …", a question, link-free; the link rides in the reply | Threads ranks by replies and docks links in the body (+17% for links vs +60% for images); the card is the post's image |
| P+1 09:00 | Telegram | **Feature** — the episode card, hook, what you will learn, YouTube link + transcript page, the ▶ Deep-Dive button **first** | Telegram counts forwards; a photo post with a button is the forwardable unit |
| P+1 09:30 | Facebook | **Feature** — same words, YouTube link on its own line → `fb_publish.split_link` lifts it into the **first comment** | A Facebook post with a link in its body reaches 60–80% fewer people, and since Sep 2026 Pages get two body links a month |
| P+2 13:10 | Threads lunch + Instagram | **Recap** — "In case you missed it", the four things you learn; Instagram's caption says *link in bio* and names `docoga.com.ng/videos/<id>.html` in plain words (the API cannot place a link sticker) | Second touch two days later catches the people who were not online on Monday night |
| P+1 … P+14 | Telegram | **Footer** — every daily post appends a "▶ This week's Deep-Dive (9 min)" button row | Zero extra posts; the button is the only Telegram surface that is a real link |
| Mon–Fri 18:00 | YouTube Short, Telegram video | The Short's description and its Telegram caption carry the **parent** Deep-Dive link; a Short whose parent is not published yet trails the **latest watchable** episode instead | Research: ~5 Shorts/month lifts long-form views +46% when the Shorts link back |

Rules that keep the locks intact:

- The promo is **not** a Gemini call — the words are assembled from `episodes/<id>/episode.json` (title, hook, section titles) and `logs/youtube_longform.json`. The brain's Gemini-only lock, the voice lock and the quota ledger are untouched.
- `deepdive_promo.latest()` only returns an episode whose YouTube slot has passed (scheduled uploads count from `publish_at`), never one in `youtube_ledger.deleted_ids()` and never a failed/rejected upload. No watchable episode → `pack_for()` is `None` → every lane posts the ordinary rotation. **A promo can never block a post.**
- The card uses the `deepdive` kicker ("new deep-dive · 9 min") and the navy poster layout; the matching CC0 plate comes from the same `shot_match` path as every other card.
- Legal copy is the episode's own, already cited and verified when the Deep-Dive was written; the promo adds "General information, not legal advice." and nothing new about the law.
- Owner never acts: the week's schedule follows the ledger automatically. First live: Telegram footer button from the next 09:00 run (dd3); dd4 publishes Mon 19 Oct 19:00 → Threads launch 20:10, Telegram/Facebook feature Tue 20 Oct, Threads lunch + Instagram recap Wed 21 Oct.

`python3 tools/deepdive_promo.py show --day 2026-10-20` prints what each channel would say that day.

## The clock (17 Oct 2026) — why the plan now actually happens on time

All of the above assumed GitHub ran the crons. It did not: since 26 Aug 2026 GitHub's
`schedule` event in private repositories arrives hours late or never (measured here:
about a third of the slots, all in the dead afternoon). `workers/clock/` — a Cloudflare
Worker on the free plan — now rings every lane through `workflow_dispatch` on the minute,
from a table generated out of the workflows' own crons (`tools/clock_schedule.py`). The
brain's plan, the slot the scorecard chose, the 07:20 Threads question, the 18:00 Short,
the Deep-Dive promo week — all of it is only as good as the clock, and the clock is now
ours. Details, the measurements and the owner's one-time token: `docs/CLOCK.md`.
