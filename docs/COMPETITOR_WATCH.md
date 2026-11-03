# Competitor watch — the field DocOga plays on

Owner's order, Mon 2 Nov 2026, 7:40am: *"always research very very in-depth to the thinnest details
on things around my business, always keep me way ahead of my competitors — even in the social media
space. I want to dominate."* Charter: `docs/STRATEGY_OFFICE.md` §11. Machine: `tools/competitor_watch.py`
(every Brain run, ₦0) → `logs/competitor_watch.json` → THE FIELD block in the Brain's prompt → Monday
scorecard "Competitor watch". Map: `brain/competitors.json` (every row below was read on the date in
`verified`; a rival that was not read is not on the map).

This file is public (the repo is public). It names what is public about each rival and nothing else.
DocOga's own money, pricing reasoning and plans stay in `docoga-private`.

## 1. Document tools — who else sells the paper

| Who | What they sell | Price (public, 2 Nov 2026) | Watchable feed |
|---|---|---|---|
| NigeriaBuildingCost — tenancy agreement generator | Free generator, all 36 states + FCT, state notice clauses, agency/legal fee fields (10%/10% defaults); printout watermarked | ₦4,000 one-time 90-day pass removes the watermark on all 6 tools; a 7-day pass exists | sitemap |
| Wonder.Legal Nigeria | 14 housing documents (rent receipt, notice to quit, late-rent notice, deposit-return letter, rent-change notice, sublet request…); basic rent receipt free, customised paid | per document | sitemap |
| DIYLaw | Lawyer-drafted documents, paid per document, account needed | per document | RSS + sitemap |
| SabiLaw Solutions | One-time Word template of a tenancy agreement | per template | sitemap |
| Legalnaija templates | Customise-and-download tenancy agreement (Q&A form) | not public | RSS |
| Rently.ng | Landlord SaaS: PDF receipts in one click, agreement generator + e-sign (Premium), tenant portal, WhatsApp/SMS reminders; free tier ≤3 properties/3 tenants | subscription | sitemap |
| Homz.ng | Property-management dashboard with agreements, quit notices, receipts | subscription | sitemap |

**Where DocOga is already different (facts, not claims):** every clause and every post cites the state's
own section from the law shelf (317 facts, 9 states as of 3 Nov 2026, Tier A: Abuja, Cross River, Edo, Kwara, Lagos);
Nigerian English; no watermark; no account; one price for 30 days; a verified receipt ledger and a
paid-rent index nobody else publishes. Nobody on this table writes to tenants *and* landlords every day
on five platforms with a cited law behind each post.

## 2. Content rivals — who else ranks for the questions

| Who | Why they matter | Feed |
|---|---|---|
| Mushrooms.ng blog | Strong Lagos-renting SEO ("true cost of renting in Lagos — budget 130–150% of rent", "Lagos Tenancy Bill 2026 explained") | RSS + sitemap |
| Lexpraxis Solicitors | Law-firm explainer on the Lagos Tenancy and Recovery of Premises Bill (27 Aug 2026) | RSS |
| Olamide Oyetayo Legal | Eviction-process explainers (29 Apr 2026) | RSS |

Also seen (not on the map until read twice): oal.law (10 Jan 2026 Bill note), Legal 500 (26 Aug 2026 —
Bill is 45 clauses in 4 parts, covers commercial premises and premium areas), crm.africa "7 best Nigeria
template sources" (24 Nov 2025) — the list buyers read before they choose.

## 3. Creators — who else teaches tenancy law on the feeds

| Who | Platform | What works for them | Feed |
|---|---|---|---|
| AALAWSNG — Adeola Kolawole | YouTube | Long explainers ("Nigerian Tenancy Law: Notice to Quit", 2022) | YouTube Atom (channel id read from the page) |
| @legalfriendng — "Real Estate Lawyer" | TikTok | Reacts to viral tenant stories citing the Lagos Tenancy Law (ss.6–7 improvements need written consent; Oct 2026) | none at ₦0 |
| @talk360law — KING, ESQ. (Benin) | TikTok | Short rulings on landlord/tenant fights; hundreds of comments per post | none at ₦0 |
| @theonlybusayoadesanya | TikTok | Quit-notice timing explainers (covered by Legit.ng, 8 Sep 2025) | none at ₦0 |

TikTok and Instagram publish no public feed without an API key or a login, and scraping them would
break their terms. The watch lists these rows as **unwatchable** instead of inventing what they post;
the Monday brief carries what was seen by hand, labelled as such.

## 4. The thing that moves the whole field — the Lagos Bill

**Lagos State Tenancy and Recovery of Premises Bill.** Passed second reading; at the Housing Committee
stage (Commissioner Moruf Akinderu-Fatai, May 2026); **not law** as of Aug 2026 — no third reading, no
assent. The Tenancy Law 2011 (Cap. T1, 2015) and the Rent Control and Recovery of Residential Premises
Law 1997 still govern. What the Bill proposes: agency and agreement fees capped at 5% each (today 10%
and 10%); mandatory LASRERA registration, unregistered agents up to 2 years / ₦1m; advance rent ≤1 year
for new tenants and ≤3 months for sitting tenants; a right to challenge rent increases in court;
mandatory rent receipts; agent remittance within 7 working days; weekend and public-holiday tenancy
court sittings; tenants who sue must show rent receipts and utility bills; applies everywhere in Lagos,
commercial and premium areas included. Every rival above has written about it once. DocOga's edge is
to write about it *correctly every week*: "proposed", never "now law", until the Governor signs — the
Brain's shelf gate already refuses the overreach.

## 5. How "ahead" is measured

Not volume. The platforms' own ranking signals, on the Monday scorecard: sends and saves per reach
(Instagram), shares and comments per post (Facebook), replies and reposts (Threads), watch time and
subscribers (YouTube), impressions, clicks and position (Google, pulled every two weeks). The field's
items sit on the same page so the two can be read together.

## 6. Rules the watch keeps

- **Only what they published.** The first real pull (Tue 3 Nov 2026, 1:30am) brought back 18 items of
  which 17 were listing pages ("Propertypro 1qlct"), menu pages ("Rent", "List a property") and a
  bill-of-quantities template — pages a sitemap dates, not things a rival said. Since then a sitemap
  entry counts only if its slug has four or more words, carries no listing token, and uses a tenancy
  word (rent, tenant, landlord, lease, quit, eviction, agent, caution, deposit, receipt, agreement,
  premises, housing, apartment, Lagos, Abuja, LASRERA); a sitemap index is followed into its
  post/blog/news children only; four items per rival at most.

- ₦0: stdlib only, public feeds, one request per feed, 20 s each, never fatal to the Brain run.
- Never copy a headline; never name a rival or a rival's price in copy (the prompt says so every run).
- Never scrape behind a login; never a second model; the owner is never asked to watch a rival by hand.
- A row joins `brain/competitors.json` only after its page was read; `verified` carries the date.
