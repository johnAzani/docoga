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

- **2026-11-12** — **The brief names the right page, or none.** Read back: the first page brief (the
  field's "house for rent captions", 10 Nov) told the editor the closest page we have was
  `rent-receipt-format-nigeria` — because the matcher counted shared slug words and the one word
  "rent" sits in 23 of our 104 slugs; ties ("can landlord increase rent in enugu": rent-receipt-enugu
  vs the rent-increase page, two words each) went to whichever came first in the sitemap, and a
  question that named a state could not find that state's page because state names were stop words.
  A wrong "closest page" is worse than none: the brief then tells a person to extend the wrong page,
  and the Growth lock's "extend, do not duplicate" is applied to the wrong thing. Now
  `page_briefs.closest_page` weighs every shared word by its rarity across our pages
  (log((N+1)/(df+1))), counts place names and never offers another state's page, treats words that
  name a kind of page (sample, format, template, pdf) as a third of a word, demands at least one
  *telling* shared word — not a place, not a form word, not one that more than a sixth of our pages
  carry unless the page is the question's own state's — and otherwise answers "no page stands close";
  a daily guide yields to a top-level page that scores the same. **Measure:** twelve questions the
  field and the ledger have actually asked, run against the real sitemap in
  `test_page_briefs.test_the_closest_page_is_the_telling_page_not_the_first_page_that_says_rent` —
  before: 7 of 12 right (three "none" questions found a page through "rent" or "landlord"; the
  Enugu increase went to a receipt page; the Lagos notice went to the national page); after: 12 of 12.
  The next brief the field triggers will carry the page the editor should actually open. Next ≤ 26 Nov
  2026.

- **2026-11-07** — **The field writes the research list.** Read back: the competitor watch's new
  "◻ uncovered" line (this morning's Dominance dive) named two rival titles with no DocOga page behind
  them and then waited for a person to notice — the same shape as every gap before it. Now
  `tools/page_briefs.py` keeps every uncovered title across pulls (`brain/page_briefs.json`; two
  titles are one question when they share two content words and half of the smaller set), and the
  **second** time the field writes on a question — a second rival, a second title, a second week —
  the Brain drafts a **page brief**: the question, who asks, what the law shelf already holds on it
  (fact ids by word match, the two common words "rent" and "tenant" never counting), the closest page
  we have, the tool the page would link, three to six things to verify before a word is written, and
  a verdict — *build*, *extend* (the Growth lock forbids thin duplicates, so a near page is extended,
  not copied) or *decline* (outside the business). Gemini writes the angle (🔒 Gemini only, the shared
  quota ledger, one call a night at most, after the planner); the brief is gated — no rival name, no
  figure or percentage, a real tool, a real verdict — and when every model is refused for the day the
  brief is still written from rules and says so. It lands as `brain/briefs/<id>.md` on main, a
  GitHub issue labelled `page-brief` (the workflow already holds `issues: write`), and a Monday
  scorecard block; a declined question is remembered so it is never asked again. Nothing is published
  from a brief — it is a research order, and the research is still a person reading the law.
  **Measure:** briefs drafted, by verdict and by `drafted_by`, on the scorecard; the first one is due
  tonight (the field asked "house for rent captions / how to advertise" twice on 5 Nov); the test of
  the loop is whether a brief becomes a page that earns Search Console impressions within 30 days of
  its issue — the GSC pull will show it against the issue date. Next ≤ 21 Nov 2026.
- **2026-11-06** — **The link follows the law the post cites.** Read back: in the 15 packs published
  since 24 Oct the model chose 4 of 12 tools (agreement 6, receipt 5, quit notice 3, tenant rights 1);
  the demand letter had no page route at all and the rent-increase page (5 Nov) was unknown to it, so
  every post on arrears or a rent increase sent the reader to the homepage — the 4 Nov Lagos post
  cited `lagos:increase_challenge:1-2` and linked the agreement page. Now `brain_drafts.FACT_ROUTES`
  maps the shelf's fact keys to tools (`increase_challenge`/`anniversary_rule`/`rent_control` →
  rent-review; `receipts`/`rent_book` → rent receipt; `rent_in_arrears`/`distress` → letter of demand;
  the notice keys → quit notice; `caution_fee`/`premium` → caution fee; …). `route_tool()` applies it
  in the editor: when the model names no tool the dominant fact key chooses one; a post whose claims
  are mostly about a rent increase always lands on the rent-increase page (the notice, the tenant's
  reply and the section it quoted are there); a tie or an unmapped key changes nothing. The prompt
  now describes the two new tools; the reply lane can name "rent review notice" in a DM; every
  `NATIONAL_PAGE` target is tested to exist. **Measure:** `tool_routed` is saved on every pack and in
  `logs/brain_said.json` — the scorecard can count how many posts the shelf re-aimed, and the
  Search Console pull will show whether social clicks reach the two money pages (both counted by
  `growth.MONEY_PAGE`). `test_brain_tool_routing` (5 tests).
- **2026-11-04** — Two habits corrected at the source. **(1) The reply lane knows the bills.** The
  commonest wrong belief under our posts is that a rent bill is already law ("Lagos don ban yearly
  rent"); the shelf has carried dated `pending_bill` facts since 3 Nov but the reply lane only saw the
  facts the day's post cited. `brain_replies.bill_facts` — a comment that talks of a bill, a "new law",
  a passage, a signing or a ban now brings that state's `pending_bill` facts (and any other state the
  comment names that carries one) into the prompt, with a house rule to answer "a bill, not law, as at
  <date>", and `lint_reply` refuses a reply that promotes the bill to law. Rivers, with no bill on the
  shelf, gets nothing invented. **(2) Inline fact ids are a refusal, not a silent clean.** The 4/5/6 Nov
  packs carried `(lagos:receipts:1)` inside the copy; `tidy()` erased them and the model never heard.
  `brain.inline_fact_ids(raw)` reads the leak before the pencil, the gate names it ("fact id typed into
  the copy: …"), and a new lesson family `fact_id_in_copy` rides in every drafting prompt once it
  recurs. Measure: `fact_id_in_copy` refusals per week on the Brain IQ block (expect >0 then 0), and
  bill-talk replies answered rather than skipped. Tests: `test_brain_replies.BillTalkTests`,
  `test_brain_tidy`.
- **2026-11-03** — The shelf learns the bills, and a machine keeps them honest: `pending_bill`
  blocks for Abuja (HB.2839 — first reading 22 Oct 2026, the FCT advance-rent bill our pages did not
  know about), Lagos (second reading 10 Jul 2025, committee), Anambra (announced 26 Mar / 21 Jun 2026)
  and Enugu (executive bill 26 Oct 2026) — 19 new dated facts (`<state>:pending_bill:n`, 317 total),
  every one opening "a bill, not law, as at 3 November 2026", so a pack can answer "is the new rent law
  out?" with the stage and the date instead of refusing. `tools/law_watch.py` (Thursdays 11:15 am,
  ₦0 news RSS) reads the news for each bill and files a `law-watch` issue on a passage headline; it
  never edits a page (`docs/STATE_TENANCY_RESEARCH.md` §15). Measure: `pending_bill` facts cited when
  a reader asks about "the new law"; zero days between a passage report and the issue.
- **2026-11-03** — Second research target read, and a wrong fact removed from the shelf: Enugu
  (`docs/STATE_TENANCY_RESEARCH.md` §14). The shelf said "no percentage cap on rent increases exists
  anywhere in Nigeria" in five states' entries; Enugu's Landlord and Tenant (Amendment) Law 2008
  (s.3(b), replacing s.109 of Cap. 101) caps a review at 15% and allows one only after every second
  anniversary — two independent sources. Enugu joins the shelf at tier B (25 facts: the 2008 rule with a
  worked example, the Court of Appeal's dating of Cap. 101, *Chicason v. Otero*, *Jovinco v. Ibeozimako*,
  dated verified negatives on receipts, advance rent and caution fees, and the 2025/2026 amendment bill
  written up as a bill with its timeline to 26 Oct 2026). The state rotation is now nine states, so
  Enugu gets its own pack nights; `increase_challenge` facts now also render on every state page.
  Measure: `enugu:*` claims cited in packs; no refusal may ever again quote "anywhere in Nigeria" on caps.
- **2026-11-03** — Shelf recall: the 60 "not on the shelf" refusals of the last 30 days were read back
  and sorted by state and topic — the biggest family (Lagos s.5(2) receipt lines, ×12) was *on* the
  shelf, uncited. The verifier now sees the rest of the state's shelf and names the fact instead of
  refusing; the claim is adopted with its id (`brain.recall`), so every published line is still cited.
  Measures on the Monday scorecard: *shelf recall* (sentences saved per week), *shelf gaps* sorted
  into recall vs **research target** (`brain.shelf_gaps`; first target: `rivers:receipts`); refusals
  now record their state. Expected: first-pass rate up from 50%, `not_on_shelf` lessons down.
  Same day the first research target was read (`docs/STATE_TENANCY_RESEARCH.md`, Rivers): the shelf
  gains the Law's dates, s.5 forms, s.6(1)(a), s.8, s.29 and ss.20–22, and the receipt entry becomes
  a reasoned negative — Rivers shelf 20 → 25 facts. The loop closes itself: a target whose shelf entry
  carries a dated read ("Read so far (3 Nov 2026)") is *settled* (`brain.shelf_gaps` kind
  `settled`, `read` date) — recalled as a verified negative, listed on the scorecard as "settled by
  research", never re-queued; undated placeholders stay targets.
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
