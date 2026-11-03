# 🔒 Growth — research how to make more, as often as possible, at ₦0 (locked 3 Nov 2026)

Owner, 3 Nov 2026, 12:10pm, after handing the company over to be run ("manage it to greatness"):

> "The same way I want you to always always research as frequently as possible very very in-depth
> to the thinnest details on how to make more success more than what we are making now, and make
> sure it can be fully automated, and remember the ₦0."

This is the third lock beside Brain Growth (`docs/BRAIN_GROWTH.md`) and Dominance
(`docs/DOMINANCE.md`). Those two keep the editor smarter and the field watched; this one keeps the
*business* growing — visits, documents made, passes sold — and makes the research that finds the
next naira a weekly habit, not a mood. Pinned by `tools/tests/test_growth_lock.py`, which is never
edited to let something through.

## 1. The order (measured, not felt)

"More success than what we are making now" is three numbers, graded every Monday 6:40am on the
scorecard beside the other locks:

| Number | Now (3 Nov 2026) | Where it is read |
|---|---|---|
| **Money** — passes sold, naira net | lifetime ≈ ₦2,058 net, owner pay ₦0 | dashboard (`DOCOGA_ADMIN_PASSPHRASE`) |
| **Documents made** — receipts, agreements, invoices | ledger counts (`/api/stats`) | `tools/rent_monitor.py` |
| **Money-page share of Google impressions** — the share of search impressions landing on pages that make the paid documents | **15% (102 of 672)** | `tools/growth.py` from `logs/search_console.json` |

Rule: every growth dive names the number it will move and by how much, and the next dive reads
whether it moved. A dive that moves nothing is written down as such.

## 2. Cadence — as frequently as possible, with a floor

- A **growth dive every 7 days at most** (the floor; weekly beside the Monday scorecard is the
  habit). The scorecard flags ⚠️ when the top ledger date is older than 7 days
  (`growth.DIVE_STALE_DAYS`). "As frequently as possible" means every session that has the room
  opens with the numbers and asks *where is the next naira*.
- Every dive is a dated row in §5 — findings with sources, then DO NOW / TEST NEXT / LATER / REJECT,
  then what shipped (PR numbers).
- Every DO NOW must be **fully automated end to end** (no owner tap on a schedule) and **₦0**
  (no paid APIs, ads, tools, or minutes). A one-time token the owner mints is allowed; a weekly
  paste is not.

## 3. The machine (₦0, no hands)

- `tools/growth.py` reads the weekly Search Console pull and prints the Monday scorecard block
  **"### Growth — where the next naira is (🔒 docs/GROWTH.md)"**: money-page share against the 40%
  target, zero-click top spots (positions 1–3 with impressions and no clicks), striking distance
  (positions 4–10), and *this week's order* — the one leak to fix.
- Why those three: in 2026 ranking and traffic have decoupled. Pew Research (68,879 real searches,
  July 2025) found 8% of searches click any site when an AI summary shows, against 15% without;
  Ahrefs (300,000 keywords, February 2026) measured position-one CTR down 58% with an Overview;
  informational queries lose most, transactional queries under 10%. So a page at position 1 on an
  informational query can earn nothing — and ours does ("quit notice", position 1.0, 48
  impressions, 0 clicks). The money is in transactional intent: *sample · template · pdf ·
  download · make it*.
- The research discipline is the Dominance one: verified facts over assumptions, sources named,
  competitors never invented, nothing scraped behind a login, no second model (Gemini only), the
  owner is never the sensor.

## 4. What is never done in its name

No paid traffic, no paid tools, no bought lists; no unofficial WhatsApp or channel automation
(ban risk, ₦0); no price change without the owner's word; no touching `worker/index.js` or the
payment flow; no fabricated numbers, testimonials or demand claims; no recycling content across
platforms; nothing the owner must do on a schedule.

## 5. Growth ledger (newest first — the scorecard reads the top date)

- **2026-11-03** — **Second dive (same day, owner: "research very very in-depth … what next"): the
  shape of the page that wins the transactional query.** Read Google's own guidance for AI
  features in Search (May 2025, as reported Aug–Sep 2026): AI Overviews draw from the ordinary
  index — no AI index, no `llms.txt`, no special markup; what gets lifted is a self-contained
  passage that answers first, under real headings, with lists or tables, on a page that is
  indexable and matches its structured data; E-E-A-T (named sources, visible freshness) is the
  nearest thing to a stated factor. Citation studies agree: most lifted passages come from the top
  third of a page; pages with tables or lists are cited several times more often than prose.
  **PDF vs HTML (ighenatt.es Jul 2026, aamax.co Aug 2026, bangaree.com Oct 2026):** Google indexes
  PDFs, but HTML is the destination for anything with a conversion path; where both exist, pick one
  — a PDF that ranks instead of the page is a dead end with no generator on it. So: the sample
  lives *on the page*, the PDF is a download, and `site/_headers` marks `/samples/*` noindex.
  **Who ranks for the sample queries:** receipts — Wonder.Legal ("FREE basic template, Word and
  PDF"), two Scribd uploads (7K and 4K views: an Abia landlord's receipt, a Lagos consultant's
  form), Genie AI's generic "Nigeria-compliant" list, a 2022 Word-template blog; quit notice —
  infoguidenigeria (2016, a sample that insults the tenant), nigerianlawguru (a solicitor's PDF),
  levi.ng (court heading + ₦90 fee), Wonder.Legal's form, woodwill.i.ng (2020). None cites a
  section beyond "s.13"; none is state-aware; none offers the generator next to the sample.
  **Shipped (this PR):** `tools/sample_docs.py` — one source renders the HTML sample and a
  dependency-free text PDF (₦0, no Pillow, deterministic); new page
  `tenancy-agreement-sample-nigeria` (full 13-clause sample above the fold, clause notes, s.4 cap,
  notice table, FAQ, free PDF, generator one tap away); download blocks on
  `rent-receipt-format-nigeria` (shared sample, s.5(2) fields) and `notice-to-quit-nigeria`;
  internal links from the pages that already rank and the home guides block; sitemap + OG card;
  `tools/tests/test_sample_docs.py` pins that the sample wording is the generator's wording.
  Follow-through the same afternoon: the 36 state pages of the three sampled tools (12 states ×
  tenancy agreement, rent receipt, notice to quit) offer "see one first" — the sample page and the
  PDF — beside their generator button (`gen_state_pages.SAMPLE_FOR`), which also gives the new
  sample page 36 internal links from pages Google already ranks for state queries.
  **Measure:** money-page share 15% → 25% by 1 Dec; the sample page's first impressions for
  "tenancy agreement sample" within 3 weeks (Search Console pull). **TEST NEXT:** a
  state-by-state sample variant only if the national page earns impressions (no thin
  duplicates — Google's guidance is explicit). **REJECT:** indexable PDFs; sample pages with
  invented names. Sources: stackmatix.com (20 Aug 2026) and agentixly.com (23 Sep 2026) on the
  Search Central guidance; proxiumdigital.com (12 Aug 2026); searchengineinfo.org (24 Jul 2026);
  ighenatt.es (31 Jul 2026); aamax.co (25 Aug 2026); bangaree.com (16 Oct 2026); wonder.legal/ng
  rent-receipt-ng and notice-quit; scribd.com 689119774 and 513920349; genieai.co en-ng;
  newslodge.com.ng (16 Feb 2022); infoguidenigeria.com (7 Nov 2016); nigerianlawguru.com PDF
  (Jun 2024); levi.ng (28 Jun 2023); woodwill.i.ng (14 Feb 2020).
- **2026-11-03** — **First dive: where does the next naira come from?** Read the 28-day Search
  Console pull (2–30 Oct: 20 clicks / 659 impressions / CTR 3.0%; 19 of 20 clicks from Nigeria).
  **Finding 1 — the footprint is one cluster.** All 27 distinct queries we rank for are the
  quit-notice family ("quit notice" 57 impressions, "notice to quit" 43, "quit notice letter from
  landlord to tenant in nigeria" 22, state tenancy-law queries) plus "shop (tenancy) agreement".
  Not one query names a rent receipt template, a tenancy agreement sample or a pass — the pages
  that sell. Money-page share of impressions: **15% (102 of 672)**. **Finding 2 — we win
  positions that no longer pay.** "quit notice" position 1.0, 48 impressions, 0 clicks; "quite
  notice" 1.0 ×5; "how to write quit notice" 1.0 ×2. That is the AI-Overview signature on
  informational queries (Pew Jul 2025; Ahrefs Feb 2026; First Page Sage 2026: position-one CTR
  22.6% without an Overview, 3.6% with one), not a bad title — the title already says "Sample
  Letter, Format, How Many Months". **Finding 3 — the transactional demand is real and served by
  weaker pages.** "tenancy agreement sample in nigeria pdf free download" is answered by Scribd
  uploads of private agreements (13K views on one) and by Wonder.Legal's "FREE basic template,
  Word and PDF" page; nobody offers a *state-aware* sample with the law cited. The same shape
  holds for receipts (Wonder.Legal free basic receipt). **Finding 4 — the channels that look free
  are not automatable.** WhatsApp Channels have no API in 2026 (posts are manual; insights hidden
  under 100 followers); the "channel APIs" on offer are unofficial gateways (Whapi, $29/month
  after a 5-day trial) — REJECT on ₦0 and ban risk, consistent with the Nairaland decision.
  **DO NOW (shipped this PR):** this lock, `tools/growth.py`, the scorecard block, the 40%
  money-page target. **DO NEXT (silence = go):** sample-and-download pages — one indexable
  page per paid document (*tenancy agreement sample Nigeria*, *rent receipt sample Nigeria*,
  *quit notice letter sample*) carrying the full sample text on the page, a real text PDF to
  download, the state law cited from the shelf, and the generator one tap away; linked from the
  quit-notice pages that already hold position 1–7 so their audience is turned into
  document-makers. Measure: money-page share 15% → 25% by 1 Dec, 40% by 1 Jan. **TEST NEXT:** a
  "copy the wording" block on the quit-notice page above the fold (serves the zero-click
  searcher *and* shows the generator). **LATER:** week-over-week growth history once the
  scorecard's commit list is widened. **REJECT:** WhatsApp Channel automation, Whapi-type
  gateways, any paid "traffic". Sources: Search Console pull `logs/search_console.json`
  (2026-11-02); Pew Research via bosio.digital (9 Jun 2026); Ahrefs Feb 2026 and First Page Sage
  2026 via blckalpaca.at (17 Oct 2026) and seo-kreativ.de (6 Sep 2026); thestacc.com zero-click
  statistics (18 May 2026); wonder.legal/ng residential tenancy agreement (10 Jul 2026);
  getkanal.com WhatsApp Channels guide (23 Oct 2026); whapi.cloud pricing.
