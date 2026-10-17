# brain/

The standing editor's memory. Read `docs/BRAIN.md` first.

- `strategy.md` — the plan the editor is held to: goal, funnel, platform rules, posting windows, calendar, 90-day targets, the orders the scorecard may issue. Edit freely.
- `audience.md` — the five named readers every post is written to. Edit freely.
- `goals.json` — the weekly rates the Monday scorecard grades. Edit the numbers; reasons live in strategy.md.
- `business.md` — what DocOga is, who it serves, how it speaks. Edit freely; the brain reads it every night.
- `editorial.md` — how a day is decided and what a post must look like. Edit freely.
- `feedback.md` — written by the brain each Monday from the channel numbers. Do not edit; it is overwritten.
- `drafts/` — approved packs, one JSON per day, consumed by the posting lanes. Pruned after 10 days.
- `listening.json` — what Nigerians asked this week (Nairaland + r/Nigeria thread titles, scored). Written nightly by `tools/listening.py pull`; the prompt reads it.
- `answers/` — one cited forum reply a week (Mondays), for the owner to paste by hand; the scorecard issue carries it. Written by `tools/listening.py answer`.
- `../site/guides/` — every approved pack as a cited guide page (`tools/guides_build.py`); `BRAIN_GUIDES=off` stops it.

Kill switch for every lane at once: repository variable `DOCOGA_BRAIN=off` (the hand-written rotation posts instead).
- `../logs/brain_replied.json` — every comment the community manager answered (platform, comment, reply, why). Written by `brain_replies.yml`; delete a row and the comment is re-read, but the lane also checks the platform's own reply list before answering.
