# Strategy — the plan the editor is held to

*Written 17 Oct 2026 from a research pass over the 2026 platform rules and
Nigerian audience data (sources at the end). Read by `tools/brain.py` on every
run. The scorecard (`tools/brain_scorecard.py`) measures every goal here each
Monday and writes orders into `brain/feedback.md`. Change the plan here, not in
the code; change the numbers in `brain/goals.json`.*

## The one goal
Money in the bank: **Oga Pass sales (₦2,000 / 30 days)** and, behind them,
business licences. Every channel exists to move a Nigerian with a rent, a
tenant or an invoice problem from a scroll to `docoga.com.ng` and a paid pass.
Followers, views and shares are instruments, not the goal; they are measured
because they lead sales by two to four weeks.

## The funnel the posts are built for
1. **Stop the thumb** — a hook in the first line / first 2 seconds that names a
   loss or a number the reader did not know (six months, not three; ₦50,000
   lawyer vs ₦2,000; "paid cash for three years, no paper").
2. **Earn the send** — the post is written so that one reader sends it to one
   named person ("send this to the friend whose rent is due in January").
   Sends and forwards are the strongest distribution signal on every Meta
   surface and the only one on Telegram.
3. **Earn the reply** — a question the reader can answer in five words
   (Threads and Sunday posts live on this; Facebook weights comments of five
   words or more).
4. **Point at one paper** — every post names the document the reader can make
   right now, free to start, and the link.
5. **Convert** — the site does the selling; the posts never discount, never
   invent a price, never promise a court outcome.

## What each platform rewards in 2026 (and how we comply)
| Platform | What the ranking actually measures | Our move |
|---|---|---|
| **Instagram** (cards, Stories, Reels) | watch time, **sends per reach**, likes per reach; original content only (reposters lose recommendations since 30 Apr 2026); Reels ≤ 3 min recommended to non-followers | one send-worthy line in every caption; Reels stay 24–45 s; checklist cards for saves; never repost |
| **Facebook Page** | meaningful comments (5+ words), private shares to Messenger/WhatsApp, Reels watch time; same-day Reels get a freshness boost; Page organic reach is 2–5% so Reels and shares are the only way out | Reel posted the day it is rendered; a question or "tell us your state" line; share-to-WhatsApp CTA |
| **Threads** | **reply velocity in the first 90 minutes**, conversation depth, reposts; "reply more than you post" (Mosseri); connected reach weighs more since Nov 2024 | every Threads post ends with a question people can answer in five words; post at lunch when people are idle |
| **YouTube Shorts** | viewed-vs-swiped (hook in 2 s), average % viewed (≥70% for ≤30 s), loops, shares; views now count any play so completion decides distribution | STAKES/number hooks in the first line, payoff before second 3, tips with a rhythm, 24 s length |
| **Telegram** | no algorithm: **forwards** and the view/subscriber ratio; growth comes from cross-promotion and forwardable posts | a forward line on every post; checklists and templates; weekly "forward this to one person" ask |
| **LinkedIn** (owner profile, Mon/Wed/Fri) | dwell time and comments in the first hour; hashtags count for little in 2026; links out are tolerated in the post but a card holds the eye | the payslip/invoice/tenancy angle for the 25–34 professional (7.7 M Nigerians); morning slot; no hashtags; the deep link rides as the article card |
| **TikTok** (inbox drafts riding the Short) | completion and rewatch in the first hour; the caption and first frame; sounds | the same 22–45 s Short with the locked voice; the owner posts from the inbox with the caption the run prints |
| **Deep-Dive (YouTube long-form)** | click-through on the cover + first 30 s retention; search traffic on state + topic | title names state + rule + number; Hook section names the loss in the first sentence |

> 21 Oct 2026 — every weekday Short now also goes out as a Facebook Reel and an Instagram
> Trial Reel from the 6:00pm lane (`docs/ALGORITHM_PLAYBOOK.md` §3): Reels are the
> recommendation surface on both Meta apps and the file already exists. Captions come
> from `tools/reel_caption.py` — hook sentence, tip keywords, one named-receiver send line.

## Posting windows — Nigeria (WAT), from the 2026 data
Nigerians are online 5.84 days a week (highest of 54 countries) and ~3 h 20 m a
day; traffic peaks **7–9 pm** when home Wi-Fi and night bundles take over, with
secondary windows at **lunch 12:30–2 pm** and **6–8 am**. Facebook also
responds in the **9–11 am** weekday window; Threads and Instagram prefer lunch
and evening.

| Lane | Slot (WAT) | Why |
|---|---|---|
| LinkedIn | 08:30 Mon/Wed/Fri | the desk reader before the first meeting; LinkedIn's weekday-morning peak |
| Telegram | 09:00 | read like the morning paper; forwards happen all day |
| Facebook post (+Reel Mon/Thu) | 09:30 | the Facebook morning window; same-day Reel |
| Threads | 13:10 | lunch idle time → reply velocity in the first 90 min |
| YouTube Short (+ TikTok inbox draft) | 18:00 Tue/Fri | the evening ramp; the owner posts the TikTok draft in the 7–9 pm peak |
| Instagram card + Story | 19:10 | the 7–9 pm peak for the visual platform |
| Facebook evening Story | 19:40 | the 7–9 pm peak; Stories sit at the top of the app |
| Deep-Dive | 03:00 render, public when the owner taps | search-driven, time-insensitive |

GitHub's scheduler can run late by hours; a morning slot that slips lands in
the afternoon (fine), an evening slot that slips lands near midnight (not
fine), so evening crons sit at :10/:40 past the hour where the queue is
shortest. The scorecard records the hour each post actually went out and the
engagement it earned, and Instagram's `online_followers` curve, so the slots
can be corrected from evidence rather than articles.

## Content mix (per week)
- 4 cited know-your-rights / state / checklist posts (the trust engine; these
  get the sends and saves)
- 1 story-style scenario (shares and comments)
- 1 promo (one tool, one job, free to start — never two promos in a row)
- 1 engagement question (Sunday; comments and replies)
- Pidgin on Wednesdays or when the theme is a market/agent story
- 2 Shorts/Reels, 1 Deep-Dive; Stories every day

## The Nigerian calendar that moves the numbers
- **Peak rental seasons: January–March and August–October** (corporate moves,
  school calendar; Abuja's August influx pushes renewals 10–25% up). More
  notice, agreement and advance-rent posts; more "renewal is not a new
  tenancy" explainers.
- **Payday rhythm: 25th to month-end** — the pass is bought when there is
  money; promo and "make it today" posts land in that window, not on the 12th.
- **November–December**: "pack out before Christmas", end-of-year notices.
- **Rent-relief season: December → 31 March (every year from 2026).** Nigeria Tax Act
  2025 s.30(2)(a)(vi): tenants deduct 20% of rent paid, max ₦500,000, *only* with a
  rent receipt in their name, a tenancy agreement and the landlord's details; employers
  apply it through payroll on receipt (annual return 31 Jan), individuals file by 31 Mar.
  Payroll desks ask for evidence from December. Posts: "the ₦500,000 you are leaving on
  the table", "what HR will ask you for", "landlord TIN on the receipt", joint tenants,
  rent that straddles two years. Deep link: `rent-relief-nigeria.html` (calculator +
  free declaration letter), then `/#receipt`. Facts and sources: docs/RENT_RELIEF.md.
  The shelf carries it: cite `nigeria:rent_relief:1` (the section and the two numbers),
  `:3` (what the evidence is), `:4` (what HR asks for), `:5` (the two deadlines), `:6`
  (worked figures) — federal facts may be cited from any state's day. Never call it
  automatic; never promise a naira amount saved without `:6`/`:7`.
- **Rent-increase anger** is the standing national mood (Lagos rents +25–40%
  in H1 2026; renters spending 50–70% of income): posts about what a landlord
  may and may not demand are the most forwarded genre.
- **Lagos Tenancy Bill (2026)** — proposed, *not law*: "3 months' rent cap",
  "5% agency fee". Never state a bill as law; a post may say "the law today
  says X (section); a bill proposes Y".

## Goals (90 days from 20 Oct 2026; weekly rates in `brain/goals.json`)
| Measure | Now (16 Oct) | 90-day target | Weekly rate |
|---|---|---|---|
| Oga Pass sales | baseline from the dashboard | 10/week by week 13 | +1 sale/week each week |
| Telegram members | from `getChatMemberCount` | ×3 | +9%/week |
| Facebook followers | from the Page | ×2 | +5.5%/week |
| Instagram followers | from the account | ×2 | +5.5%/week |
| Threads followers | from the account | ×2.5 | +7%/week |
| YouTube subscribers | 49 | 250 | +13/week |
| Sends/shares per post (FB+IG) | — | ≥ 1.5% of reach | measured weekly |
| Threads replies per post | — | ≥ 3 | measured weekly |
| Shorts viewed-vs-swiped | — | ≥ 70% | when Analytics scope is granted |

A goal behind for two weeks running changes the orders (below), not the goal.

## Orders the scorecard may issue (deterministic, from the numbers)
- *Sends low* → STAKES and STAT hooks, one named-person send line, checklist layouts.
- *Threads replies low* → end with a five-word-answer question; one opinion post a week.
- *Facebook comments low* → ask for the reader's state or a yes/no; reply-worthy scenarios.
- *Telegram view ratio < 40%* → shorter posts, a forward line, one poll-style question a week.
- *Shorts views flat* → change the hook archetype for two weeks; numbers in the first line.
- *Sales flat while reach grows* → promo moves to the payday window; posts name the exact
  document and "two minutes, free to start" in the last line; one testimonial-style scenario.
- *Everything up* → do not change the mix; rotate states and hooks only.
- *Learning loop (from 17 Oct 2026)* → every post is joined to the pack the brain wrote that
  day (`logs/brain_said.json`), so the scorecard knows what each **hook type, post type and
  reader** actually earned, and what brain days earned against rotation days. With two or
  more posts per hook and a 1.5× gap, the order names the winner ("use STAKES on two of the
  four cited days; rest QUESTION for two weeks") and the reader to write to again. One post
  is not evidence; the order waits.

## Answer every comment within ninety minutes (the lever the numbers point at)
Threads ranks a post on replies in its first 30–90 minutes and on how deep the conversation
goes; Facebook ranks on back-and-forth comments of five words or more; Instagram ranks on
the conversation under a post as much as on sends. A Page that posts and leaves is a
billboard. So `brain_replies.yml` runs **11:40 / 14:40 / 20:40 WAT** — about ninety minutes
after the Facebook, Threads and Instagram slots — reads every new top-level comment under
our last three days of posts, and answers the real ones: the general rule with its section
(only facts the post itself was built on, only for that state), the document that fixes it,
the **deep link** to that tool's page for that state, and "which state?" when the state is
unknown. Praise gets one warm line and a question back; abuse and bait get nothing.
One Gemini call per run; every reply passes the same gates as a post (≤280 characters, no
price but ours, no "stop paying rent", no court promises, no link but ours). Ledger:
`logs/brain_replied.json`. A missing permission is named in the run summary, never a red run.

## Deep links (one tap less between the post and the paper)
Every pack names its `tool`; `brain_drafts.link_for` turns tool + state into the exact page
— `docoga.com.ng/notice-to-quit-lagos.html` — falling back to the national guide
(`*-nigeria.html`) and then the homepage, and never to a page that does not exist. Posts,
Threads and replies all use it. Facebook penalises links out, so there the link stays in the
last line and the body carries the value.

## The reach layer (fourth research pass, 17 Oct 2026)
Where Nigerians actually are (DataReportal Oct 2026, 18+ ad reach): TikTok **47.8 M (+43 %)**,
Facebook 38.0 M, YouTube 30.5 M, **LinkedIn 13–14 M** (25–34 = 7.7 M), Instagram 10.0 M
(−6 %), X 6.95 M (−11 %, 74 % male, API no longer free → skipped). Monthly use: WhatsApp
96.5 %, TikTok 89.7 %, Facebook/Instagram 89.2 %, Telegram 79.2 %, Threads 15.5 %. Moves:
a dated newsdesk so every post can open on this week's rent story; Threads topic tags
(more views) + polls (a tap, not a sentence) + cross-share to Instagram; Instagram Trial
Reels (non-followers first, graduate on performance); a Tuesday Telegram quiz (polls lift
engagement past 50 %); the LinkedIn lane; TikTok inbox drafts. Rent seasonality the brain
leans into: Jan–Mar and Aug–Oct peaks, payday 25th–month-end.

## The money layer (fifth research pass, 17 Oct 2026)
The question this pass answers: **which channel pays, and what does each platform need from
us before it pays us.** Moves: channel tags on every link (`?s=`) + first-touch source on the
site + checkout/sale counters in the worker → the scorecard's "Money follows X" order; Google
Search Console demand in the brain's prompt (answer a position-9 query in the first line and
it becomes page one); Facebook's link in the first comment (body reach 0.20 % → 0.80 %);
a second Threads post at 20:10 WAT as an image with the link in our reply (Threads' Nigeria
peak is 7–9 pm; images earn ~1.6× text); Instagram captions that open with the search phrase
+ alt text (Google indexes them); a Wednesday Short and the same Short as a native Telegram
video; and **milestones** — Facebook Stars at 500 followers for 30 days, YouTube fan funding
at 500 subscribers, Instagram/Telegram at 1,000 — graded weekly on pace, so the plan is
always "this many a week, by this date". Seasonality unchanged: Jan–Mar, Aug–Oct, payday.

## The conversion layer (sixth research pass, 17 Oct 2026)
The question this pass answers: **what turns a reader who already stopped into a visit, a
forward and a sale — and what stops the machine itself from failing quietly.** Moves:
**inline buttons under every Telegram post** ("Open the free tool" → the exact page, `?s=tg`;
"Share on WhatsApp" pre-filled with the headline and a `?s=wa` link — WhatsApp is on 96.5 %
of Nigerian phones; "Forward on Telegram"); the buttons step aside by themselves if the
channel ever gains a discussion group, because comments outrank buttons. **Instagram
carousels on Tuesday and Thursday** (the pack's lines, one slide each: 0.55 % ER vs 0.37 %
for a single image, nine times the saves — Socialinsider/Metricool 2026). **Comment → DM**:
a reader who comments "link", "send", "template" gets the exact page in the inbox — one
private reply per comment, template text, no Gemini, tagged link (open rates 85–92 %, clicks
18–35 % for comment-to-DM in 2026); dormant until the two messaging scopes are on the tokens,
and the lane says which. **The hour is chosen by the numbers**: the Instagram lane fires in
all three Nigerian windows (07:10, 13:10, 19:10 WAT) and a slot gate lets exactly one post —
the one `brain/slots.json` names, rewritten every Monday from what our posts earned by hour,
else from the audience's online curve. **The hook is a bandit, not a rota**: each hook
archetype is an arm scored by what it earned; the plan picks by UCB (best average plus an
exploration bonus), never repeats the last two days' hooks, and once two hooks have three
measured posts the lint holds the model to the chosen hook. **A pinned newsdesk** carries the
hand-dated October stories (the viral landlord video, the Q4 rent-pressure report, the state
tenancy reforms, the Abuja poll) ahead of the RSS pull, each expiring on its own date. And the
monitor is fixed: the heartbeat had been red four nights running without filing its issue,
because the workflow's default `bash -e` ended the step at the one command that is allowed
to exit 1 — a contract test now forbids that shape in every workflow.

## Sources (Oct 2026 research pass)
DataReportal Digital 2026 (Nigeria 5.84 days/week; 3 h 18–27 m/day); Kreste Digital 2026
Nigeria report (47.8 M social identities; WhatsApp 96.5%, Facebook 38 M, Instagram 10 M);
Socialchamp / Rooli / Nivedigital / Tasklet (Nigeria windows: 7–9 pm, lunch, 9–11 am FB);
Buffer 2026 (Facebook Thu 9 am; Instagram 3–5 posts/week + 1–2 Stories/day); Mosseri Jan
2025 / Sep 2026 (watch time, likes per reach, sends per reach; originality, recency, small
creators); Instagram 30 Apr 2026 originality rule; Meta Jan 2026 UTIS Reels survey model,
Mar 2026 original-content policy; Mosseri on Threads ("reply more than you post"); Metricool
2026 Shorts study (avg watch 16 s), creator analyses of viewed-vs-swiped ≥ 70%; Telegram
2026 growth playbooks (view rate 40–60%, forward rate ≥ 2%); Guardian/NIESV H1 2026 rents;
Tribune Jul 2026 Abuja August influx; WithinNigeria Sep 2026 Lagos Tenancy Bill (proposed).
