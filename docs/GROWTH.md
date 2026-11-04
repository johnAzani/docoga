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

- **2026-11-04** — **Facebook pass (owner, 6:35am: "research very very very in-depth … more
  guaranteed results on Facebook … automated … ₦0").** Where the Page stands: 1 follower, 2–14
  views a post, the first-comment link the only "comment" on most days; yet facebook sent 69 of
  the site's 85 visits last week. Findings, Meta's own words: every video on Facebook is a Reel of
  any length or orientation since 17 Jun 2025 (the "plain video post reaches only followers"
  reasoning in our docs predates it); original video watch time doubled in H2 2025 (13 Mar 2026);
  same-day Reels get 50 % more recommendation slots (Oct 2025); "Your algorithm" (13 Oct 2026)
  lets people name topics, so every post must say its topic in words; back-and-forth comments and
  private shares are the heaviest Feed signals; Pages reach ~2–5 % of followers; the Reels API
  still refuses anything not 9:16 / 3–90 s. **DO NOW (shipped):** the Deep-Dive uploaded natively on
  P+1 from the repo's own release (`/videos`, cover thumbnail, link-free words with one question,
  YouTube + transcript in the first comment, card fallback, `FB_NATIVE_VIDEO`); the Page likes every
  comment it answers. **TEST NEXT:** Sun 8 Nov's dd5 post views against the 1 Nov card's 8; a
  text-only question post as a third daily shape if the native video's comments beat the cards.
  **LATER:** topic words as the first line of every Facebook caption for "Your algorithm".
  **REJECT:** a Facebook Group (no API — owner's taps), Live (parked), buying reach. Sources:
  about.fb.com 17 Jun 2025 (TechCrunch, Engadget same day), 13 Mar 2026; Meta Newsroom 13 Oct 2026;
  developers.facebook.com Reels Publishing API (video specifications, error 1363128);
  `logs/scorecard.json` W45 facebook posts.
- **2026-11-03** — **Sixth pass (same evening, same order): the news the pages did not know.**
  Finding: the FCT Advance Rent Regulation and Tenants' Protection Bill (HB.2839) passed first
  reading on 22 Oct 2026 and ran in five papers 26 Oct–1 Nov; "Abuja rent bill" is this fortnight's
  query and our five Abuja pages said nothing about it.
  Shipped: dated `pending_bill` blocks on all 20 Abuja/Lagos/Anambra/Enugu pages (stage, what it
  would change, what it does not, "what that means today"), 19 Brain facts, and `tools/law_watch.py`
  so the sentence "a bill, not law, as at 3 November 2026" cannot quietly rot: Thursdays, ₦0 news
  RSS, an issue on a passage headline, never a page edit (`docs/STATE_TENANCY_RESEARCH.md` §15).
  Beats the field because no competitor page in the 2 Nov map dates its bill claims or re-checks
  them; measure on the 9 Nov and 16 Nov scorecards: Abuja-page impressions and any "rent bill" /
  "new rent law" query entering the GSC top 50.
- **2026-11-03** — **Third pass (same afternoon, owner: "research very very very in-depth to the
  thinnest details … continue"): the signals the page sends, and the messenger.** Three findings.
  **(1) "quit notice" is a news query.** The bare query we hold at position 1.0 with 48 impressions
  and 0 clicks is, in Nigeria, dominated by government quit notices — Lagos Taskforce's 72-hour
  notice to Alaba Rago traders (Vanguard, Daily Post, 24 Jun 2026), FAAN's quit notice to freight
  forwarders at MMA (Jan 2026). Those searchers are reading news, not ending a tenancy; the
  impression is worthless and the rule in §1 stands: **never chase the bare "quit notice"**; the
  transactional phrasings ("quit notice letter", "notice to quit sample") are the ones to hold.
  **(2) Rich results and dates.** Google retired FAQ rich results for every site on 7 May 2026
  (Search Console FAQ report gone June, API August — quattr.com 8 Jul 2026, axiobyte 5 Aug 2026);
  HowTo has no surface left. Google's first official guide to generative AI features (Search
  Central, 15 May 2026) says plainly: same index, no special markup, no `llms.txt`, do not rewrite
  headings as questions, do not spin a page per query variation — and it keeps structured data
  "valuable for rich results" with the one standing condition that it **match the visible page**.
  What still earns a rich result and a freshness signal is Article (headline, dateModified, author,
  publisher) and BreadcrumbList. Our 60 state pages carried **no structured data and no date**;
  the guide pages carried only FAQPage. **(3) The messenger never spoke.** The site has had an
  IndexNow routine since 17 Oct, but it ran only for the Brain's guide pages, only with a repository
  variable set, and the key file that proves ownership (`site/<key>.txt`) had never reached main —
  so every ping was refused. IndexNow is free, takes 10,000 URLs a POST, and feeds Bing, which is
  what Copilot, DuckDuckGo, Yahoo and in part ChatGPT search read (7insider Aug 2026: Copilot 3.5%
  of AI referrals, ChatGPT 74.8%; indexnowtool.com Apr 2026: key 8–128 chars, same URL at most
  once a day). Google does not take IndexNow; for Google the equivalent is a sitemap `<lastmod>`
  that is actually true. **Shipped:** `tools/freshness.py` — every generated page (60 state + 10
  guide) now carries one visible line under its title ("Updated 3 November 2026 · law shelf
  reviewed 8 October 2026 · DocOga"), an Article JSON-LD whose `dateModified` is that same date,
  `author`/`publisher` DocOga, the canonical as `mainEntityOfPage`, the OG card as `image`,
  `inLanguage` en-NG, the primary-source URLs as `citation` and the statute as `about`
  (Legislation + jurisdiction) — only where the shelf is verified; a BreadcrumbList (Home → national
  guide → page); and a sitemap `<lastmod>` equal to the page's date. **The date is honest by
  construction:** a rebuild compares the new page with the one on disk (dates masked) and keeps
  the old date unless the words changed — sixty pages rebuilt with nothing changed keep sixty old
  dates; the test `test_freshness_indexnow` forbids any page whose three dates disagree or whose
  date is in the future. `LAW_REVIEWED` in the law shelf prints when each state was last checked
  against its sources (dossier 8 Oct 2026; Rivers re-read 3 Nov 2026) and moves only after a real
  re-verification. **IndexNow fixed:** the key is public by design (the engines read it at the site
  root), so it is committed as `site/<key>.txt` and `guides_build.DEFAULT_KEY`; a new lane
  `.github/workflows/indexnow.yml` runs on every push to main that touches `site/**`, waits 150 s
  for Cloudflare's build, diffs the push and submits exactly the changed sitemap URLs (new pages
  included; `/admin`, `/success`, the noindex PDFs can never be submitted because only sitemap
  URLs qualify); run by hand it submits the whole sitemap. The Brain's own guide ping now works
  too. **Measure:** Bing Webmaster is not connected (₦0, no owner tap wanted) — so the measure is
  the lane's step summary (HTTP 200/202 per push) and, in Search Console, whether the state
  pages' rich-result eligibility and the "Updated" line change CTR on the state queries by 1 Dec.
  **Decisions.** DO NOW: shipped above. TEST NEXT: Sitelinks-search-box/Organization on the home
  page once the state pages' breadcrumbs show in results; a `datePublished` for state pages if a
  trustworthy first-publish date can be recovered (not invented). LATER: WebSite + Organization
  `sameAs` to the verified social profiles. REJECT: rewriting headings as questions (Google says
  no); FAQ blocks added for markup's sake; any dateModified that is not the day the words changed;
  Bing Webmaster connection that needs the owner's hands. Sources: vanguardngr.com 24 Jun 2026,
  dailypost.ng 24 Jun 2026, justnetnews.com 30 Jan 2026, quattr.com 8 Jul 2026, axiobyte.online
  5 Aug 2026, yositeup.com 30 May 2026, launchcodex.com 6 Aug 2026, swotdigital.com 19 May 2026,
  withsurface.com 10 Jun 2026, marwickmarketing.co.uk 22 May 2026, indexnowtool.com 27 Apr 2026,
  7insider.com 6 Aug 2026, rankcart.io 22 Jul 2026.
  **Follow-through (same afternoon, fourth pass — entity and hierarchy).** Read Google's site-name
  and Organization rules as reported Jul–Oct 2026 (patrickstox.com 18 Jul, hirebalzac.ai 7 Oct,
  dev.to 16 Oct, palai.media 14 Oct, clickforest.com 28 Oct, nadiamohamed.me 2 Oct): the bolded
  site name over a home-page result comes from one `WebSite` block on the home page (`name` +
  `url`, `alternateName` list ending with the lowercase domain, consistent with `og:site_name` and
  the `<title>`); the owner entity is one `Organization` block on the home page with `logo` ≥112×112
  crawlable and `sameAs` to the real profiles; the sitelinks search box has been gone since 29 Nov
  2024 so no `potentialAction`; breadcrumbs show (desktop only since 22 Jan 2025) only for a trail
  the page actually carries, and the standing rule is that markup describes what the reader sees.
  Favicon: square, ≥8 px, >48 px recommended — ours is a 64 px PNG linked from the home page, fine.
  Shipped: `WebSite` + `Organization` + `og:site_name` on the home page — the five `sameAs` are the
  profiles the machine itself has posted to (Instagram handle and Facebook Page id as returned by
  the Graph API in `logs/scorecard.json`, the Threads permalink in `logs/threads_sent.json`, the
  YouTube channel the video pages publish, the Telegram channel), nothing from memory; a **visible
  breadcrumb trail** above the title of all 70 generated pages (Home › Notice to quit in Nigeria ›
  Edo) whose names and URLs are byte-equal to the `BreadcrumbList`; the Article publisher logo
  moved to the 180×180 square icon. Side effect worth having: 60 more internal links from state
  pages up to the four national guides. REJECT: `@id` fragments on the home page (the SPA lint
  reads `#org` as a route) — the publisher is inlined instead; any `sameAs` to LinkedIn, TikTok or
  X, which the machine cannot vouch for.
  **Follow-through (same evening, fifth pass — the content itself).** The only state query Search
  Console shows us ranking for is "enugu" (position 2, `notice-to-quit-enugu`, 0 clicks) — and the
  Enugu pages were the thin, unverified version. Researched Enugu to the primary texts available
  (`docs/STATE_TENANCY_RESEARCH.md` §14: the 2025 bill PDF, the Assembly's 13 Aug 2008 announcement,
  a 2021 practitioner quoting s.3(b) of the 2008 amendment, Punch 11 Mar 2025, ICIR 15 Dec 2025, The
  Advocate 26 Oct 2026). Finding that no rival page carries correctly: Enugu is the one Nigerian state
  with a statutory cap on rent increases (15%, review only after every second anniversary) — and our
  own pages had been saying "no cap anywhere in Nigeria". Corrected on `tenant-rights-nigeria` and on
  five states' shelf entries; Enugu's five pages now lead with its own statute, a worked ₦400,000 →
  ₦460,000 example, a dated status of the caution-fee bill (executive bill announced 26 Oct 2026,
  governor's four-week pledge — still not law) and dated verified negatives. "Rent increases" now
  renders on all 60 state pages (it had been shelf-only). This is the paragraph-level specificity the
  15 May 2026 AI guidance rewards, on the page that already has the impressions.

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
  Follow-through the same afternoon: the 36 state pages of the three sampled tools (12 states × The live probe (five times a day) now also fails if the sample PDF is missing, is not a PDF, or is served without `X-Robots-Tag: noindex` — the one header the "HTML page ranks, PDF downloads" decision depends on; a Cloudflare `_headers` regression would file an issue by itself instead of being found in Search Console weeks later.
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
