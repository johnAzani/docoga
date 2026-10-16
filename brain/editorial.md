# Editorial policy — how the brain decides what today says

*Read by tools/brain.py on every run, together with business.md, the law shelf,
the said-ledger and feedback.md. Change the policy here, not in the code.*

## The daily decision, in order
1. **What has not been said lately?** The said-ledger lists every theme and
   headline of the last 60 days. A theme used in the last 21 days is off the
   table; a headline that is 60% the same words as any recent one is a repeat.
2. **What is the day?** Weekday rhythm (below), the Nigerian calendar in
   business.md, and whether a Short is rendered this day (Mon/Thu Facebook +
   Instagram Reel, Tue/Fri YouTube Short) — on those days the pack carries a
   Short topic that matches the post's theme, so the feed and the video agree.
3. **Which state?** Rotate through the shelf's states so Lagos is not every
   post: Lagos, Abuja, Edo, Kwara, Cross River, Rivers, Anambra, Kano (Kano is
   the "there is no statute — your agreement governs" lesson).
4. **What does the shelf allow?** Every legal sentence must come from a fact on
   the shelf for that state and name its fact id. If the shelf does not support a
   claim, the claim is not made. A post with no legal claim at all is fine
   (promo, engagement, pidgin, testimonial-style) — it just has no citations.
5. **What did the numbers say?** feedback.md ranks recent themes and hook types
   by views and engagement. Tilt toward what worked; never copy it verbatim.

## Weekday rhythm (post type suggestions; the brain may deviate with a reason)
| Day | Lead type | Why |
|---|---|---|
| Monday | know-your-rights (educational, cited) | start of the week, people act |
| Tuesday | state spotlight (one state, one rule) | search traffic on state pages |
| Wednesday | pidgin or plain-talk explainer | mid-week, lighter voice |
| Thursday | story-style scenario ("a tenant in Ikeja paid cash for three years…") | saves and shares |
| Friday | promo / product (one tool, one job, free to start) | weekend moves |
| Saturday | checklist (5 lines a document must have) | save-worthy |
| Sunday | engagement question (ask, don't tell) | comments |

## Hook archetypes (one per asset; rotate them)
STAT · QUESTION · CLAIM · STAKES · CURIOSITY · HOWTO · STORY

## Shape rules the gates enforce
- Headline first, then body. Headline ≤ 70 characters, no trailing full stop
  needed, no ALL CAPS sentences (the card sets type; shouting is not a style).
- Body in short lines; each line ≤ 110 characters; 2–5 lines.
- One link, always `https://docoga.com.ng`. Threads/Instagram may carry it at
  the end; the card never shows the link twice.
- Legal posts end with: `General information, not legal advice.`
- Hashtags: a separate line, 3–5 on Telegram/Facebook, 1–2 on Threads; always
  include #DocOga.
- No markdown, no asterisks, no emoji in Short/Reel lines or card headlines.
  Emoji in Telegram/Facebook body lines: at most one, or none.
- Pidgin posts are pidgin all through, not one pidgin word in an English post.

## Visual brief (what the brain hands the renderer)
- `kicker`: 2–4 words naming the post's job ("know your rights", "state
  spotlight: Edo", "oya, make we talk").
- `layout`: `poster` (headline + body), `stat` (one big number or short phrase
  + a line under it), `checklist` (headline + numbered lines).
- `big`: the number or 1–3-word phrase for the `stat` layout ("6 MONTHS",
  "₦100,000", "s.5").
- `plate`: 2–4 plain English words for a background photograph with no people's
  faces and no readable signs ("lagos rooftops dusk", "naira notes table",
  "keys wooden door"). The renderer treats it in navy duotone; it may also decide
  not to use a plate — the brief is a wish, the card is the contract.

## Short topic (only on render days)
- `title`: two sentences that split into a STAKES hook ("Pay without a receipt.
  Pay twice.") or one sentence for the other archetypes.
- `hook_sub`: ≤ 9 words.
- `tips`: exactly four `{text ≤ 5 words, sub ≤ 9 words}`; the voice reads
  `text` then `sub` as sentences, so they must read aloud naturally.
- The disclaimer slide is added by the engine; the brain does not write it.

## Deep-Dive episode (weekly)
- Nine sections, each 120–200 words of narration, Nigerian English, one idea
  per section, the Hook first and "The Law, and DocOga" last.
- 36–48 beats: `{sec, trig: 2–4 consecutive words copied exactly from that
  section's narration (lowercase, no punctuation), head ≤ 28 characters, sub ≤
  60 characters, img: a plate name from episodes/assets}`. The first beat of a
  section has `trig: null`. Triggers must appear in the section text in beat
  order — the engine checks and refuses otherwise.
- Every statute mentioned in the narration must be on the shelf for the state
  named in the same sentence.
