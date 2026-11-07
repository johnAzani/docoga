# 🔒 Research deep, stay ahead, dominate — a standing order

**Locked by the owner, Mon 2 Nov 2026, 7:40am and again at 8:05am: "I want you to always research
very very in-depth to the thinnest details on things around my business, always keep me way ahead
of my competitors — even in the social media space. I want to dominate. Lock it in."**

This file is the charter and the ledger. `docs/STRATEGY_OFFICE.md` §11 carries the order inside the
Strategy Office; `tools/tests/test_dominance_lock.py` pins this charter, the machine and the
measurement — never edit that test to let something through; revert the change that trips it.
🔒 The locks underneath stand: **Gemini only, ₦0, nothing the owner must do by hand on a schedule,
no fabricated competitors, statistics, testimonials or law.**

## 1. What "dominate" means (measured, not felt)

Dominance is not posting more. It is being the one the platforms rank and the one people quote, on
every question a Nigerian tenant or landlord asks. The Monday scorecard measures it on the
platforms' own signals, this week against last:

| Where | The signal that decides reach | Where it is read |
|---|---|---|
| Instagram | sends and saves per reach, watch time (Mosseri, Jan 2025) | Insights API, `instagram.*_per_reach` |
| Facebook | shares and comments per post | Page insights |
| Threads | replies and reposts | Threads insights |
| YouTube | watch time, subscribers, Shorts views | Analytics API (`youtube_stats`) |
| Google | impressions, clicks, average position for tenancy queries | Search Console, every two weeks |
| The field | what the competition published this week, and whether DocOga answered it better the same week | `logs/competitor_watch.json` |

"Ahead" = those rising while the field's output is known and answered, with the section they did not
cite, the same week.

## 2. The machine (₦0, no hands)

- **The field map** — `brain/competitors.json`: who else sells tenancy documents to Nigerians (tools),
  who else ranks for the questions (content), who else teaches the law on the feeds (creators). Every
  row from a page that was read; `verified` carries the date; public facts only
  (`docs/COMPETITOR_WATCH.md`).
- **The watch** — `tools/competitor_watch.py` runs on every Brain run: public RSS, sitemap `lastmod`
  and YouTube channel feeds, topic-filtered, last 14 days → `logs/competitor_watch.json`. TikTok and
  Instagram publish no feed at ₦0; their rows are reported **unwatchable**, never guessed.
  A row may also carry a `paths` list (a marketplace sitemap is watched on its `/blog/` paths only)
  and a `prices` block — the one public pricing page a rival has, with the figures the map has
  `seen`; the pull re-reads it and the scorecard flags ⚠️ any naira figure the map does not know
  (added 4 Nov 2026 after a rival's new ₦500 pass went unseen for days).
- **The prompt** — every pack prompt carries THE FIELD: titles only, with the rule *say it better,
  cite the section they did not, take the angle they missed; never copy a headline; never name a rival
  or a rival's price in copy.*
- **The scorecard** — Monday 6:40am prints "Competitor watch — the field this week" and the research
  freshness lines of §3; stale research is flagged ⚠️ in the owner's brief.

## 3. The research discipline

- **Research before build, every time.** No feature, post series, price word or platform change is
  proposed without a dated dive: what was read, what is fact, estimate or hypothesis, and what DocOga
  does about it (`docs/STRATEGY_OFFICE.md` §3).
- **Depth, not breadth.** A dive goes to the thinnest detail that changes a decision: the exact section
  of the law, the exact ranking signal, the exact rival price and what it buys, the exact status of a
  Bill (reading, committee, assent).
- **Cadence that is measured.** A new dated dive lands in the ledger below at least **every 14 days**;
  the field map is re-verified at least **every 45 days**; the watch pulls on every Brain run. The
  scorecard counts the days and prints ⚠️ when any of the three is late.
- **Verified or labelled.** A competitor, a number or a trend that was not read is not written. What
  was seen by hand (TikTok, Instagram) is labelled as seen by hand.
- **The owner is never the sensor.** He is never asked to watch a rival, paste a stat or check a
  trend on a schedule; the machine reads, the brief tells him.

## 4. What is never done in its name

No paid intelligence tools; no scraping behind logins; no second model; no copying a rival's headline,
hook or copy; no naming a rival in public copy; no made-up comparison tables; no "we are the best"
without the signal that says so.

## 5. Research ledger (newest first — the scorecard reads the top date)

- **2026-11-07** — All 14 rows re-verified by hand (map `verified` 2026-11-07) and this week's rival
  content read against the rent-increase page shipped on 5 Nov. **The collision:** the strongest
  content rival (Mushrooms.ng) published *"How much can a landlord increase rent in Nigeria"* on
  **the same day** as our page, and its 20 Oct rent-increase-letter post — which the 4 Nov row
  called "a letter to copy" — is in fact a **two-sided generator** (landlord's notice / tenant's
  reply, rent compared by city for 16 cities, PDF and WhatsApp output, blank Word/PDF templates, no
  sign-up, free). That is the closest thing to the Rent Review tool on the field and the 4 Nov ledger
  under-read it; corrected here. What it still lacks, checked line by line: no state-aware legal
  paragraph (Lagos s.37 is explained in prose, every other state is "check your law"), **no Enugu
  15% / second-anniversary rule and no refusal of an unlawful figure**, no Kwara s.7, sample letters
  with invented names, and press statistics quoted as fact. Wonder.Legal has a generic NG "Change of
  Rent Notice" (rev. 18 Aug 2026) that tells a disagreeing tenant to "be ready to vacate" — no s.37,
  no notice ladder. Rently gives quit, breach and demand notices free on its ₦0 plan (Premium
  ₦5,000/month, Enterprise ₦15,000/month); SabiLaw ₦3,200 per template and DIYLaw ₦3,500 per
  agreement unchanged and now on the price sentinel; NBC (₦4,000/₦500), Legalnaija, Homz, Lexpraxis
  (corporate; no tenancy post), Olamide Oyetayo (property-purchase posts) unchanged; AALAWSNG and the
  three TikTok creators as before (no public feed at ₦0). The wider field this week: Abuja residents
  backing HB.2839 (2 Nov), the ₦20m-fine headline after second reading (6 Nov), and the 20%-cap belief
  repeated as law in three explainers. **Watch fault found and fixed:** four NigeriaBuildingCost
  construction tenders ("solar caution lights", "breeder bull housing", "gwagwalada abuja", "health
  centres… fct") passed the topic filter on 5 Nov — the tender regex grows and a map row can now
  `skip_paths` a whole folder. **Shipped:** a **collision sensor** in the watch — every rival title is
  read against the nine money pages (`COVERAGE`); a hit becomes "⚔️ collision … ↔ /our-page" on the
  Monday scorecard and a COLLISIONS block in the Brain's prompt that names the page and sets the tool,
  so a rival's post on a question we answer turns into a routed DocOga post the same week; a miss
  becomes "◻ uncovered" — the Growth lane's candidate list written by the field. On the page and in
  the tool: the Lagos row now carries the four excluded areas (s.1(3)) and the s.4 advance-rent bundle;
  the "not more than 20%" answer (House motion of 23 Oct 2025 — a resolution, not a law) as an FAQ, a
  bullet and a federal shelf fact (`nigeria:increase_motion`, routed to rent-review) so a Brain reply
  can say it with the date; a comparables note for s.37 (what the court measures against); and both
  generated letters and both samples print a **"Received by … Signature … Date"** acknowledgment
  line. **Beats rivals because** the only other free generator writes one legal paragraph for the
  whole country; ours writes the state's, refuses the Enugu figure, prints the proof of service, and
  the machine now notices the day a rival steps onto one of our questions. Next field re-verification
  due by 22 Dec 2026 (≤45 d); next dive ≤21 Nov 2026.
- **2026-11-04** — Field re-verified (map `verified` 2026-11-04) and the fortnight read. **What moved:**
  the closest tool rival (NigeriaBuildingCost) now sells a **₦500 seven-day pass** under its ₦4,000
  ninety-day one, opened a 48-document sample library on 30 Oct with a filled-in sample tenancy
  agreement at the top (preview free, download behind a free account — 122 downloads by 4 Nov), and
  writes agency 10% / legal 10% into its default agreement; its blog stays construction (survey plans,
  rebar, wiring — 26 Oct). The strongest content rival (Mushrooms.ng) published about fifteen
  tenancy-law explainers in three days (20–22 Oct: quit notice and rent increases step by step, Lagos
  tenant rights, agency fee and the 5% bill, subletting with a consent letter to copy, a rent-increase
  letter) and the watch missed every one — its `/feed/` is 404 and the sitemap items it did pass were
  TikTok listing noise. AALAWSNG's channel id confirmed from its own Posts tab; its last tenancy video
  is from 2022 (2026 output is wills, consent, company law). Legalnaija's one fortnight post is a
  governance colloquium; SabiLaw's two and Lexpraxis's two were filtered as off-topic by title.
  LawDepot NG, Genie AI (en-ng, "free to generate via subscription") and Wonder.Legal unchanged.
  **Shipped:** `paths` filter (Mushrooms watched on `/blog/` only, dead feed dropped) and a **price
  sentinel** — `prices{url, seen}` on a map row, re-read every Brain run, ⚠️ on the Monday scorecard
  when a figure appears or vanishes (`tools/competitor_watch.py`, tests). **Beats rivals because** the
  machine now sees a price move and a blog burst the week they happen, while DocOga's answer to both
  already stands: samples with no account and no invented names (3 Nov), a demand letter nobody else
  has state-aware (4 Nov), and every clause cited to the section. Pricing itself is the owner's call;
  the brief carries the figure, the copy never does.
- **2026-11-03** — Refusal audit: every "not on the shelf" sentence of the last 60 days read against
  the law shelf by state and topic. Finding: `lagos:receipts` ×12 refused yet present on the shelf
  (s.5(2) contents, facts 2–6) → a recall problem, not a law gap; `rivers:receipts` the one true
  research target (shelf holds only a "not verified" placeholder — the Rivers State Recovery of
  Premises Law's receipt position is next to read). Shipped as shelf recall + shelf gaps on the
  scorecard. Also: first competitor-watch pull audited — 17 of 18 items were sitemap noise; filters
  tightened (#184). **Same day, the target was read:** Rivers Recovery of Premises Law = No. 16 of
  1991, in force 2 Jan 1992, Cap. 109 of 1999 (Court of Appeal, *Anyaehie v. Ongolo* 2022); s.5 Forms
  B/C/D, s.6(1)(a) one week, s.8 Form E, s.29 "tenant" includes a rent-free occupier, ss.20–22 court
  order or nothing. No receipt duty in any section map → the shelf keeps an honest negative and the
  Rivers shelf grows 20 → 25 facts (`tools/state_law_data.py`; pages regenerated). Beats rivals
  because no template site publishes Rivers at section level at all.
- **2026-11-02** — The field: 7 document tools (prices, free tiers, watermarks), 3 content rivals,
  4 creators; Lagos Tenancy and Recovery of Premises Bill status (second reading, committee, not law
  as of Aug 2026; 5% fee caps, LASRERA, ≤1 year advance rent, mandatory receipts). Shipped as the
  competitor watch (#180). Sources in `docs/COMPETITOR_WATCH.md`.
- **2026-11-01** — Instagram carousel craft (hook on slide 1, slide 2 re-served to non-swipers,
  5–8 slides, save-worthy penultimate, music → Reels tab) and ranking signals (watch time, likes and
  sends per reach; 5-hashtag cap; low-res/watermarked/majority-text penalised). Shipped as the
  photo-first carousel (#175) and photos behind every card (#174).
- **2026-10-29** — SERP shape for "notice to quit Nigeria", "rent receipt law", "caution fee":
  tenant-rights framing wins; opener questions; template prices ₦5,000–₦8,500. Shipped as the quit-notice
  opener and tenant-rights pages (#156, #157), rent index (#162).
