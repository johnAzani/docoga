# brain/

The standing editor's memory. Read `docs/BRAIN.md` first.

- `business.md` — what DocOga is, who it serves, how it speaks. Edit freely; the brain reads it every night.
- `editorial.md` — how a day is decided and what a post must look like. Edit freely.
- `feedback.md` — written by the brain each Monday from the channel numbers. Do not edit; it is overwritten.
- `drafts/` — approved packs, one JSON per day, consumed by the posting lanes. Pruned after 10 days.

Kill switch for every lane at once: repository variable `DOCOGA_BRAIN=off` (the hand-written rotation posts instead).
