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

**Owner's decisions, 12 Nov 2026 (standing):** **no ₦500 single-document price** — the ₦2,000/30-day
pass stays the only product; **no agents** — the owner will not meet, message or be asked to meet
estate agents, and no plan may lean on him handing the link to anyone. Both were offered as his
decisions and declined; neither is raised again.

**Editor's decisions, 12 Nov 2026 (standing):** build hours go to money only — Google clicks, the
money-page share (15% → 40%) and the tap from free sample to clean copy; the social lanes keep running
at ₦0 but receive no further build work on cards, Reels, Shorts craft, hooks or thumbnails. Every
Founder's brief opens with two numbers: Google clicks (28 days) and passes sold (28 days).
**Checkpoint, end of February 2027:** 500 Google clicks in a month and 10 passes sold in a month —
met, we scale pages and states; missed, the owner is told to stop spending even attention on it and
the product is parked, sold or changed. The owner plans his money as if DocOga earns ₦0 until then.


- **2026-11-12** — **Seventh dive (owner, 7:55am: "Continue"): the snippet, not the ranking.** The 9 Nov
  pull (28 days to 6 Nov) read page by page: eleven pages sit on page one with impressions and almost
  no clicks — `/power-of-attorney-nigeria` position 4.7, 57 impressions, 1 click; `/notice-to-quit-edo`
  6.3, 55, 1; `/notice-to-quit-kaduna` 7.0, 15, 0; `/notice-to-quit-kano` 4.4, 12, 0; the Rivers page
  3.4, 38, 2. The ranking is earned; the words in the result lose the tap. Reading our own titles and
  descriptions showed why: **59 of 97 titles ran past 60 characters** (the state pages at 64–84 —
  "… — Free Generator (2026)" is what a result cuts off), the power-of-attorney title was 85 and its
  description 239, and **all twelve notice-to-quit state pages carried one identical description** with
  no number in it, while the question typed is a number ("how many months"). **DO NOW (shipped):**
  every title ≤ 60 characters with the query words first (`Notice to Quit in Edo (Benin City): How Many
  Months`; `Edo State Tenancy Law: Notice Months, Rent, Courts` — the exact shape of "edo state tenancy
  law", 12 impressions on the wrong page); a description per state built from the state's own ladder
  and statute (`1 month monthly, 6 months yearly under the Recovery of Premises Law, then the 7-day
  notice`), never typed by hand (`gen_state_pages.snippet_for`, `ladder_brief`); the twelve hand-written
  pages trimmed with their numbers kept (₦50,000, ₦100,000, ₦500,000, 7.5%, 15%); guide pages lose the
  " | DocOga" suffix (results print the site name on their own line) and cut at a clause, never with an
  ellipsis; 83 link-preview cards redrawn. The rule is now a machine: `tools/snippet_audit.py` (title
  ≤ 60, description 70–160, no two pages alike) fails `qa.py`, the nightly guides build re-titles pruned
  pages, and the Monday scorecard prints "snippets losing the tap" — page-one pages under a
  click-through floor for their position — so this reading never has to be done by hand again. The
  quit-notice title of 3 Nov is untouched (lock). **Measure:** CTR on the five pages above in the
  ~26 Nov and ~10 Dec pulls (today 0–5%); the goal is the Edo and power-of-attorney pages above 5% at
  their positions; "edo state tenancy law" landing on `/tenancy-law-edo`. **TEST NEXT:** if the Edo
  page moves but Kano/Kaduna do not, the unverified-state wording ("the general Nigerian rule") is the
  next suspect. **LATER:** a pixel-width measure instead of characters (Google cuts at ~600 px);
  descriptions that quote the state's section number. **REJECT:** changing the quit-notice title; a year
  in every title (it costs seven characters and dates the page); keyword-stuffed titles that read like
  a list; any invented click-through curve presented as a measured fact (the floor is a working
  assumption and the code says so).
  Sources: logs/search_console.json (taken 2026-11-09, window 2026-10-09→11-06, top_pages and
  top_queries); the 97 public pages' <title> and description read on 12 Nov 2026 (tools/snippet_audit.py
  --check before the change: 96 problems); tools/state_law_data.py ladders; the og cards redrawn with
  tools/og_images.py.
- **2026-11-10** — **Sixth dive (owner, 7:55am: "Continue"): the page Google counts twice.** The
  9 Nov Search Console pull (28 days to 6 Nov: 16 clicks / 448 impressions, CTR 3.6%) put "quit
  notice" at **position 1.0 with 0 clicks** — and the page URL it ranked was `/notice-to-quit-nigeria.html`,
  while `/notice-to-quit-nigeria` sat at 8.3 with 74 impressions of its own. The same split on
  `/notice-to-quit-kano` (1.5 / 4.4), `/notice-to-quit-enugu`, `/notice-to-quit-abuja`,
  `/rent-receipt-lagos`: two weeks after the clean canonicals of 28 Oct, Google still indexes both
  selves of a page, because Cloudflare's `/x.html → /x` is a **307 — temporary** — and Google treats it
  as one; the canonical hint alone did not fold them. **DO NOW (shipped):** `site/_redirects` — a
  **301** from every `/x.html` to its clean URL (102 static lines, `tools/redirects_build.py`; the
  assets-only worker reads `_redirects` before HTML handling, "always followed, regardless of whether
  or not an asset matches"); the guides lane refreshes it when it writes a page and the Brain commits
  it; `qa.py` fails when a page has no line. Also this dive: the first page brief (#214, "how to
  advertise a house for rent") read against the shelf and **declined** — the law that touches it
  (LASRERA registration, FCCPA Part XV misleading advertisements) is real but no DocOga document stands
  behind a listing page, and the 4 Nov rule holds (a page only where the tool writes the document);
  the Brain closes the issue with the reason from the ledger, and LATER names the document that would
  change the answer (a landlord's letter of authority to let). And the Instagram slot: on 9 Nov the
  chosen 7:10pm run died at GitHub's end with no jobs and the day lost its card — a later scheduled
  run before 10pm now carries a card the chosen slot never posted (once; the same-day ledger guard
  still comes first). **Measure:** in the next two Search Console pulls the `.html` rows vanish and the
  clean URL inherits their impressions — "quit notice" should show one row near position 1 with clicks;
  money-page share 15% → 25% by 1 Dec. **TEST NEXT:** the "quit notice" title once the rows merge —
  the position-1 snippet earned 0 clicks in 6 impressions, which is too few to judge until they merge.
  **LATER:** letter of authority to let (landlord → agent); employment-letter and warning-letter pages.
  **REJECT:** a `/*.html` splat rule (the docs show a splat only at the end of a path — one wrong line
  would 301 every page to nowhere); turning `html_handling` off (the worker is assets-only and
  `worker/index.js` is never touched); a page from brief #214 as written.
  Sources: logs/search_console.json (taken 2026-11-09, window 2026-10-09→11-06); Cloudflare docs —
  workers/static-assets/routing/advanced/html-handling (307 table) and workers/static-assets/redirects
  (`_redirects` semantics, 2,000 static lines, "redirects are always followed"), read from the
  cloudflare-docs repository 10 Nov 2026; brain/briefs/house-rent-caption.md; GitHub run 42671673688
  (9 Nov, zero jobs).
- **2026-11-05** — **Fifth dive (owner, 5:05pm: "go on to next build"): the page we refused to
  write until the tool could write it.** The 4 Nov rule said a rent-increase page only if a generator
  exists for it; this build is the generator — the **11th tool, Notice of Rent Review**
  (`site/index.html#rentreview`) — and then the page. **The field for "rent increase notice/letter
  Nigeria":** a marketplace blog's two templates (mushrooms.ng, 20 Oct 2026: "NOTICE OF RENT REVIEW"
  renewal-framed, "NOTICE OF NEW MONTHLY RENT"), a listings blog's effective-date letter (apartments.ng
  b1130), a paid 2-in-1 file on Selar, and law explainers that contradict each other on "how much
  notice" — six months (lexnuelinsights 30 Jun 2026; cabans.ng 16 May 2026; listproperty.ng, which
  also cites a repealed Act), three months once in 12 months (nigeriarealestateblog 16 Mar 2025),
  "1–6 months depending on state" (rightify.app 25 Apr 2026). All of them are reading the s.13 quit
  ladder into a different question; none cites the s.37 forms, none knows Enugu's 15%/second-anniversary
  cap, none admits no statute fixes a notice period for an increase. **DO NOW (shipped):** the
  generator — state select, period, current/new rent, term end, reply-by date, reason; sentences that
  make the increase an offer for the next term ("not a demand for the present one … takes effect only
  on your written acceptance"; "if we do not agree a rent, the tenancy is not thereby ended"); a law
  paragraph swapped per state from the shelf (Lagos s.37 + s.37(4); Enugu 2008 s.3(b) with the cap
  computed — `rrCap(400,000) = 460,000` — and an over-cap figure named as one that must come down before
  service; FCT/others: the agreement governs); live hints under the rent fields ("above the Enugu 15%
  cap — maximum ₦460,000"). Then `rent-increase-notice-nigeria.html`: the sample (Lagos, yearly, no
  names) + free PDF + the state table + "how much notice — the honest answer" + line-by-line + tenant
  section + comparison; linked from tenant-rights, quit-notice, agreement-sample, demand pages and the
  home guides block; `growth.MONEY_PAGE` counts it; footers now say 11 tools. **Measure:** first
  impressions for "rent increase"/"rent review"/"increment letter" queries within 3 weeks; money-page
  share (15% → 25% by 1 Dec); rentreview drafts in the Oga Pass funnel. **DO NOW (owner, 7:35pm:
  "build"; shipped the same evening):** the tenant's reply as a second output of the same tool — "Who is
  writing?" switch; accept / decline / counter-offer with the offer in words and percent; "the tenancy
  continues on its present terms … not a notice to quit"; Lagos s.37 + s.37(4) reserved; Enugu: an
  over-cap figure is declined by name, and the tool will not write an acceptance above the cap (it accepts
  the cap instead); FCT/others: the agreement governs. The reply sample + free PDF sit in the tenant
  section of the same page — one page, two outputs (no thin duplicate; `test_sample_docs` pins that no
  `rent-increase-reply-nigeria.html` exists). Why a tenant letter on a landlord page: the query
  "rent increase letter Nigeria" is typed by both sides and the ranking pages serve only the landlord.
  **TEST NEXT:** nothing new until the 3-week Search Console read. **LATER:** employment-letter and warning-letter pages, same rule. **REJECT:**
  a "notice period by state" table with invented months (the rivals' error); an Enugu notice that
  prints an over-cap figure as lawful; a Word template.
  Sources: tools/state_law_data.py (Lagos s.37, s.37(4), s.13(1), s.44; Enugu L&T (Amendment) Law
  2008 s.3(b); Kwara s.7; Jovinco v Ibeozimako (2014) LPELR-23599(CA); Cobra v Omole Estate (2000) 1
  NWLR (Pt.655) 1); mushrooms.ng rent-increase-letter-nigeria (20 Oct 2026); apartments.ng b1130;
  selar.com rent-increase sample (paid); rightify.app (25 Apr 2026); lexnuelinsights (30 Jun 2026);
  cabans.ng (16 May 2026); listproperty.ng (2024); nigeriarealestateblog (16 Mar 2025).
- **2026-11-04** — **Fourth dive (owner, 11:35am: "build the Growth dive"): the generator that had
  no door.** Read the generators against the pages: the app has written demand letters since launch
  (`renderDemand`) and had no page for them, while every other tenancy tool has a sample page that
  Google can rank. **The field for "demand letter for unpaid rent Nigeria":** Genie AI's auto-generated
  outlines (what a "letter for non-payment of rent" should contain; no letter, no section of any law),
  a US "demand letter to tenant" (justicedirect), a UK arrears letter (bindlegal, May 2026) and a Kenyan
  sample — nobody puts the Nigerian letter, a free PDF and the arrears rule of each state's law on one
  page. **Also read and rejected:** payslip pages (notchhr, anoorehr, finora, staffpay — HR-software
  blogs with their own generators; off the rent brand) and a rent-increase letter page (mushrooms.ng
  published a sound one on 20 Oct 2026 citing s.37; apartments.ng; no generator of ours behind it).
  **Shipped:** `demand-letter-rent-arrears-nigeria` — the generator's exact sentences as the sample
  (`sample_docs.DEMAND_LETTER`, pinned to `renderDemand` by test), free PDF, generator one tap away,
  and an arrears table from the Brain's shelf: Lagos s.13(2)–(3) (six months / one year, no quit
  notice), FCT (no shortcut, s.7 Form E), Cross River s.15 proviso, Kwara s.17 proviso and Ch. L4,
  Edo (one month), Rivers s.75(1) (rent in arrears unless agreed), the seven-clear-days notice for
  Anambra/Enugu/Kano; the ladder after the letter and the s.44 self-help offence; a tenant's section.
  Linked from the quit-notice and receipt pages and the home guides block; `growth.MONEY_PAGE` counts
  it. **Measure:** money-page share (15% → 25% by 1 Dec); first impressions for "demand letter" /
  "unpaid rent" / "rent arrears" queries within 3 weeks (Search Console pull). **TEST NEXT:** a
  rent-increase notice page only if a generator is built for it (the sample-page rule: nothing on a
  page the tool does not write). **LATER:** employment-letter and warning-letter pages, same rule.
  **REJECT:** an editable Word template of any paid document (it is the product); payslip SEO.
  Sources: genieai.co/en-ng letter-for-non-payment-of-rent; justicedirect.com (13 Mar 2025);
  bindlegal.com (25 May 2026); kenyanlaw.com (15 Jul 2021); mushrooms.ng rent-increase-letter-nigeria
  (20 Oct 2026); apartments.ng b1130; notchhr.io (9 Mar 2026); anoorehr.com (16 Jul 2026);
  finorabusiness.com (24 Jan 2025); smartsmssolutions.com (15 Jan 2026).
- **2026-11-04** — **Third Facebook pass (owner, 10:14am, the same order).** Found: Facebook's
  first comment was a bare link and the Reel had none (Instagram has had the question-first comment
  since 22 Oct); the first replies pass came 2 h 10 min after the 9:30am post; and this morning's
  card was lost — the narrator-resume made up the 3 Nov Short at 9:16am, its Reel counted as
  "today's post" and the 9:30am card stood down. **DO NOW (shipped):** question-first comment under
  the post and the Reel (`FB_FIRST_COMMENT=`), replies passes at 10:15am and 6:50pm, the card's
  guard looks past Reels. **TEST NEXT:** comments per Facebook post that are not our own, 9 and
  16 Nov. **DO NOW (shipped, same day):** the resumer's make-up Short waits for a 5:30pm WAT slot,
  public 6:00pm, instead of publishing at the 9am reset. **REJECT:** nothing new. Sources: Meta Transparency Center, Feed AI system (6 Oct 2026); Meta
  Newsroom 13 Oct 2026; `docs/ALGORITHM_PLAYBOOK.md` §4; run 41798288694 / 41800039608.
- **2026-11-04** — **Second Facebook pass (owner, 8:35am, the same order again).** Found: the Page
  never asked for a follow in five weeks; the site's 85 weekly visits met no visible channel link;
  nobody audits the Page profile; and the 4–6 Nov brain packs carried fact ids inline in the copy
  (caught 45 minutes before the 9:30am post). **DO NOW (shipped, #199):** `tools/fb_follow.py` —
  specific dated follow asks on every Facebook post, Reel and native video; the follow row in every
  page footer; `tools/fb_page_audit.py` in the preflight (fills About/website, names the taps,
  catches a renamed username); fact ids stripped on read and before the brain's gates.
  **TEST NEXT:** `followers_count` on 9 and 16 Nov; the `FB_PAGE_AUDIT=` line of the next run.
  **LATER:** a pinned post (no API — one tap, named only if the audit shows the profile otherwise
  complete). **REJECT:** invite-to-follow automation (no API; the owner's own tap, never a bot).
  Sources: audience.my 10 May 2026; krumzi 11 Sep 2026; orichi 12 Oct 2026; crescitaly 6 Jun 2026;
  rafflepress 28 Jul 2026; Graph API Page reference (fields, `pages_manage_metadata`).
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
