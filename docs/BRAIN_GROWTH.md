# The Brain gets smarter — a standing order

**Locked by the owner, Mon 2 Nov 2026, 5:10am: "I want you to always improve on the brain. I want
it to always get smarter. Lock it in."**

This file is the charter and the ledger. The Brain (`tools/brain.py` and its lanes — `docs/BRAIN.md`)
is DocOga's editor: it plans every post, drafts every Short, Deep-Dive and answer page, and is held
to the law shelf by gates and a verifier. The owner's order is that it never stands still. 🔒 The
Brain stays **Gemini only, ₦0** (`tools/tests/test_brain_lock.py`); getting smarter never means a
second provider, a paid tier or a hand on the owner's side.

## 1. What "smarter" means (measured, not felt)

Every Monday 6:40am the scorecard prints **"Brain IQ — is the editor getting smarter?"**
(`brain_scorecard.brain_iq`, kept in `logs/scorecard.json` so the trend survives). The numbers
are the ones the Brain itself controls:

| Number | Smarter means | Source |
|---|---|---|
| First-pass rate | more nights whose pack passes lint + verifier without a refusal | `logs/brain_said.json` vs `logs/brain_refused.json` |
| Deep-Dive drafts | more episodes written per attempt | `logs/brain_deepdive.json` |
| Answer page | the week's page written (Mon, else Tue/Wed) | `brain/answers/` |
| Law shelf | more verified facts, more states | `tools/law_index.py` |
| Lessons carried | fewer, and smaller, refusal families over 30 days | `brain.lessons()` |
| What its choices earned | hook / post type / reader scores rising | scorecard "What the brain's choices earned" |
| Days since last improvement | never past 14 | the changelog below |

A falling first-pass rate two Mondays running, or a changelog older than 14 days, is a finding the
scorecard flags (⚠️) and I act on in the next brief — without being asked.

## 2. The learning loops (how it gets smarter by itself)

1. **Lessons from its own refusals (2 Nov 2026).** Every refusal is one of a known family
   (`brain.LESSON_FAMILIES`: law not on the shelf, claim overreach, long lines, a news hook the
   desk did not print, invented prices, statistics, section numbers in copy, Short shape, word
   budget, beat count, unknown fact ids, style words, repeats). The families of the last 30 days,
   counted, ride in **every** drafting prompt — packs and Deep-Dives — as
   `LESSONS FROM YOUR OWN REFUSALS`. Until now a refusal taught the model for one retry and was
   forgotten by the next night.
2. **Monday feedback** (`brain/feedback.md`): the scorecard's numbers and what each hook type,
   post type and reader earned, read by the planner before it plans.
3. **The ears** (`tools/listening.py`): what tenants actually asked this week chooses the
   answer page's topic; a refused page is re-asked once with the gate's words; Tue/Wed retry.
4. **The newsdesk** (`brain/newsdesk.json`): only a headline the papers printed can be a hook.
5. **Nothing twice** (`logs/brain_said.json`, `logs/footage_used.json`): themes, headlines,
   photographs and clips on cooldown so the next angle is always the new one.
6. **The verifier** (Gemini, second pass): every legal claim checked against the shelf fact it
   cites; disagreement = refusal = a lesson.

## 3. The human loop (what I owe the owner)

- **One real Brain improvement at least every 14 days**, logged below with its PR. "Real" means
  a measurable number in §1 should move, or a new learning loop exists — not a reworded prompt.
- Research first (`docs/STRATEGY_OFFICE.md` §3): prompt and gate changes follow evidence — the
  refusal log, the scorecard, what the platforms say ranks — never taste.
- Every improvement is tested (`tools/tests/test_brain*.py`), documented in `docs/BRAIN.md`,
  and named in the Founder's brief. Nothing asks the owner to do anything.
- The locks stay: Gemini only; voice Orus; no fabricated statistics, testimonials or law.

## 4. Changelog (newest first — the scorecard reads the top date)

- **2026-11-03** — Shelf recall: the 60 "not on the shelf" refusals of the last 30 days were read back
  and sorted by state and topic — the biggest family (Lagos s.5(2) receipt lines, ×12) was *on* the
  shelf, uncited. The verifier now sees the rest of the state's shelf and names the fact instead of
  refusing; the claim is adopted with its id (`brain.recall`), so every published line is still cited.
  Measures on the Monday scorecard: *shelf recall* (sentences saved per week), *shelf gaps* sorted
  into recall vs **research target** (`brain.shelf_gaps`; first target: `rivers:receipts`); refusals
  now record their state. Expected: first-pass rate up from 50%, `not_on_shelf` lessons down.
  Same day the first research target was read (`docs/STATE_TENANCY_RESEARCH.md`, Rivers): the shelf
  gains the Law's dates, s.5 forms, s.6(1)(a), s.8, s.29 and ss.20–22, and the receipt entry becomes
  a reasoned negative — Rivers shelf 20 → 25 facts.
- **2026-11-02** — The field: the Brain plans knowing what competitors published this week
  (`tools/competitor_watch.py`, verified map `brain/competitors.json`, public feeds at ₦0, THE
  FIELD block in every pack prompt, "Competitor watch" on the Monday scorecard). Owner's dominance
  mandate, `docs/STRATEGY_OFFICE.md` §11. Measure: the scorecard shows the field's items and
  DocOga's sends/saves per reach the same week.
- **2026-11-02** — Lessons: the Brain learns from its own refusals across nights (top families of
  the last 30 days in every prompt); Brain IQ block on the Monday scorecard; this charter locked
  (`test_brain_growth_lock.py`).
- **2026-11-02** — Answer page: a refused draft is re-asked once with the gate's words; the
  outcome is logged; Tuesday and Wednesday retry while the week has no page (#178).
- **2026-11-01** — The week's question becomes a self-publishing cited page (`brain/answers/`
  → `site/guides/`); the ears choose the topic (#173).
- **2026-10-31** — Listening scorer matches whole words; the Monday opener (#171).
- **2026-10-29** — Rent Monitor facts enter the shelf as `monitor:*`; statistics gate (#165).
- **2026-10-27** — Law shelf: Tier A states with section-level facts; verifier holds every
  claim to a fact id.
