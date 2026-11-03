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

- **2026-11-03** — Refusal audit: every "not on the shelf" sentence of the last 60 days read against
  the law shelf by state and topic. Finding: `lagos:receipts` ×12 refused yet present on the shelf
  (s.5(2) contents, facts 2–6) → a recall problem, not a law gap; `rivers:receipts` the one true
  research target (shelf holds only a "not verified" placeholder — the Rivers State Recovery of
  Premises Law's receipt position is next to read). Shipped as shelf recall + shelf gaps on the
  scorecard. Also: first competitor-watch pull audited — 17 of 18 items were sitemap noise; filters
  tightened (#184).
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
