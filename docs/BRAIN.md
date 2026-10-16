# The Brain — DocOga's standing editor

*Built 16–17 Oct 2026 on the owner's instruction: "I don't want a bank. I want a
brain that can think like you, understands content creation and my business, so
that it works autonomously — everything automated. It only handles the social
media."*

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
`gemini-2.5-flash → gemini-2.5-flash-lite → gemini-flash-lite-latest → gemini-2.0-flash`
(`BRAIN_MODELS` variable overrides). A per-minute 429 is waited out once; a per-day
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
Sundays (or `workflow_dispatch` with `deepdive=true`), only when
`episodes/queue.json` has nothing unpublished: one call writes title, nine
sections, beats, cover brief and YouTube meta; the gates and a verification call
run; `episodes/ddN/` is written with the **locked voice block copied byte for
byte** from the previous episode and the sound plan; the id is appended to the
queue; `deepdive.py ddN check` runs. The nightly Deep-Dive lane then narrates,
renders and uploads it exactly as it does today. YouTube privacy stays whatever
`YT_PRIVACY` says — that is the owner's one look before the public sees it.

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
