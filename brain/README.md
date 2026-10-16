# brain/

The standing editor's memory. Read `docs/BRAIN.md` first.

- `strategy.md` — the plan the editor is held to: goal, funnel, platform rules, posting windows, calendar, 90-day targets, the orders the scorecard may issue. Edit freely.
- `audience.md` — the five named readers every post is written to. Edit freely.
- `goals.json` — the weekly rates the Monday scorecard grades. Edit the numbers; reasons live in strategy.md.
- `business.md` — what DocOga is, who it serves, how it speaks. Edit freely; the brain reads it every night.
- `editorial.md` — how a day is decided and what a post must look like. Edit freely.
- `feedback.md` — written by the brain each Monday from the channel numbers. Do not edit; it is overwritten.
- `drafts/` — approved packs, one JSON per day, consumed by the posting lanes. Pruned after 10 days.

Kill switch for every lane at once: repository variable `DOCOGA_BRAIN=off` (the hand-written rotation posts instead).
