# State tenancy law in Nigeria — research dossier

*Compiled 8 October 2026 for DocOga's state SEO pages.*
*Companion to `PLAN.md` §3 rung 1 ("state-specific content, 36 states + FCT") and
§4 (SEO keyword cluster).*

---

## 0. Why this file exists

Before writing a single new state page, I measured the state pages we already
ship. Then I read Google's spam policy. Then I did the legal research. The
measurement is in §1, the rule it forces us to satisfy is in §2, the law is in
§4–§8, and what we still do not know is in §9.

**House rule (unchanged, from `DOCOGA-RISK-LOG.md`):** publish only what was
checked, and frame anything unverified as general practice plus "confirm with a
lawyer". Nothing here is published to the site until it has passed that test.

---

## 1. The measurement that changed the plan

Every same-tool state page pair in `site/` was compared by Jaccard similarity of
its visible word set (12 states × 4 tools = 48 pages, 264 pairs):

| Tool | Median words/page | Median unique words vs siblings | Median pairwise similarity |
|---|---|---|---|
| tenancy-agreement | 524 | **3** | 94.2% |
| notice-to-quit | 544 | **3** | 94.9% |
| rent-receipt | 449 | **3** | 93.5% |
| caution-fee | 470 | **3** | 94.2% |

**Overall: 94.2% similar, with a median of three unique words per page.** Those
three words are essentially the state name, the capital and one city.

Reproduce it:

```bash
python3 - <<'EOF'
import re, itertools, statistics
from pathlib import Path
def words(p):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", Path(p).read_text(), flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return set(w.lower() for w in re.findall(r"[A-Za-z0-9]+", t))
states = ["lagos","abuja","rivers","oyo","kano","enugu","delta","kaduna","ogun","anambra","edo","plateau"]
for tool in ["tenancy-agreement","notice-to-quit","rent-receipt","caution-fee"]:
    s = {f"{tool}-{x}": words(f"site/{tool}-{x}.html") for x in states}
    ov = [len(s[a]&s[b])/len(s[a]|s[b]) for a,b in itertools.combinations(s,2)]
    print(tool, f"{statistics.median(ov)*100:.1f}% similar")
EOF
```

---

## 2. The rule this has to satisfy

Google's spam policy on **doorway abuse** names, almost verbatim, what we have
built:

> "having multiple domain names or pages targeted at specific regions or cities
> that funnel users to one page" and "creating substantially similar pages that
> are closer to search results than a clearly defined, browseable hierarchy".

The operative test used by practitioners: **would these pages be
indistinguishable from each other if the place name were removed?** For our 48
pages the answer is yes.

Three further points that matter for how we fix it:

- **The failure mode is deindexing, not a ranking penalty.** The earliest signal
  is a cluster of pages sitting in *Crawled — currently not indexed* in Search
  Console. It shows up before traffic falls. ([SEO Handbook][seohb])
- **There is no page-count threshold — the test is content-based.** Sites with
  genuine per-location data have published thousands safely; sites with thin
  near-identical pages have taken manual action on as few as **30–40 pages**. We
  ship 48. ([Search Foundry][sf])
- **The usual working target is the 80/20 rule**: a shared skeleton is fine, but
  ~20% of each page must be genuinely dynamic content a user in that location
  could not get from any other page on the site. Pages under ~400–500 words of
  indexable text are frequently not indexed at all — our median is 449–544
  **including** boilerplate. ([Search Foundry][sf], [Grow With BA][gwba])

**Consequence: expanding 12 states → 37 with the current template is the wrong
move.** It would take a 48-page cluster that already fails the test to ~148
pages. The priority is to make the existing pages earn their place, then add
states only where each one has real, citable, state-specific content.

[seohb]: https://seohandbook.co.uk/local-seo/local-landing-pages/
[sf]: https://searchfoundry.co.uk/blog/programmatic-seo-on-a-budget-scaling-local-landing-pages-without-spam-penalties
[gwba]: https://growwithba.com/blog/local-landing-pages-at-scale

---

## 3. What is genuinely common to all 37 jurisdictions

Verified consistently across the sources below. Safe boilerplate — this is the
*shared* 80%, and it should be labelled as shared, not dressed up as state law.

1. **Every state has its own landlord/tenant or recovery-of-premises law.**
   "Each state in Nigeria has her rent control law … for residential
   accommodation." ([Agbonika & Idachaba][cuab]) Judicial writing is blunter:
   "Every State in Nigeria now has its own law on recovery of premises."
   ([Starlion Legal][sl])
2. **The notice ladder** where the agreement is silent: week (tenant at will) →
   1 month (monthly) → 3 months (quarterly) → 6 months (yearly). *Lagos adds a
   half-yearly tier at 3 months; the Abuja Act does not.* ([cjokoyelawview][cjk],
   [lexpraxis][lex])
3. **The 7-day notice** of the owner's intention to apply to recover possession,
   served after the quit notice expires. Lagos Form TL4/TL5; Abuja Form E.
4. **Self-help is forbidden.** "Where a landlord takes over his property
   forcefully from a tenant without an order of court, he will be deemed to have
   resorted to self help and renders himself liable in trespass." (*Iheanacho v.
   Uzochukwu*, cited in [cjokoyelawview][cjk])
5. **The statutory periods are floors, not ceilings, and the agreement
   governs** where it says something different: "the provisions of the rent
   control and recovery of premises law on length of notice will apply" only
   where there is no agreement. ([tandfonline][tandf])
6. **Compensation for improvements** made with the landlord's **written**
   consent. (Lagos Tenancy Law s.7/s.8; Cross River Cap R3 s.14 equivalent.)

[cuab]: https://cuab.edu.ng/wp-content/uploads/2023/09/6.-Agbonika-and-Idachaba-Landlod-and-Tenant-in-Lagos-State.pdf
[sl]: https://starlionlegal.com/2020/02/07/recovery-of-premises-an-assessment-of-landlord-tenant-law-in-nigeria/
[cjk]: https://cjokoyelawview.com/civil-litigation/week-18-recovery-of-possession-of-premises
[lex]: https://lexpraxisng.com/how-to-recover-property-from-your-tenant-in-nigeria/
[tandf]: https://www.tandfonline.com/doi/abs/10.1080/03050718.2020.1714456

---

## 4. A real dividing line: which property statute applies

Not tenancy law, but it *is* state-specific, verifiable and genuinely useful —
it decides which property statute governs the transaction.

| Family | States |
|---|---|
| **Property and Conveyancing Law 1959** (old Western Region + Mid-West) | Lagos, Ogun, Ondo, Oyo, Osun, Ekiti, Edo, Delta |
| **Conveyancing Act 1881** (old Eastern & Northern Regions) | Rivers, Bayelsa, Cross River, Akwa Ibom, Ebonyi, Abia, Imo, Enugu, Anambra, Kano, Kaduna, Borno, Sokoto, Adamawa |

Sources: [Lexology In-Depth: Real Estate Law, Nigeria][lexology];
[cjokoyelawview property framework][cjk2]. The lists are given as "former
region" memberships and the two sources agree on membership; Ekiti/Osun/Ebonyi
appear in the regional descriptions rather than in both lists — treat those
three as high-confidence-by-inference rather than directly cited.

[lexology]: https://www.gelias.com/images/Papers/Lexology_In-Depth_-_Real_Estate_Law_-_Real_Estate_Law__Nigeria.pdf
[cjk2]: https://cjokoyelawview.com/property-law-practice/week-3-general-overview-and-legal-framework

---

## 5. Per-jurisdiction findings (verified)

Confidence key: **A** = primary text or official state source · **B** = peer-reviewed /
practitioner writing citing the section · **C** = single secondary source, needs confirmation.

### Lagos — the deepest record (A)
Two statutes coexist, and this trips people up:

- **Tenancy Law of Lagos State 2011 (Law No. 14 of 2011)** — the one that
  governs most landlord/tenant relationships today. Verified from the Act text:
  - **s.4 advance rent**: unlawful to demand/receive from a **sitting tenant**
    more than six months (monthly) or one year (yearly); from a **new or
    would-be tenant**, more than **one year** — note the cap is one year flat
    for incoming tenants, with no six-month branch. Offence: **₦100,000 fine or
    three months' imprisonment**. ([Tenancy Law text PDF][lagoslaw])
  - **s.7 tenant obligations** (7 items, incl. keep in good tenantable repair,
    no alterations or subletting without written consent) and **s.8 landlord
    obligations** (5 items: quiet enjoyment; rates and charges; keep insured;
    do not terminate or restrict a common facility or service; do not seize or
    interfere with the tenant's property). ([same][lagoslaw])
  - **s.13(1)** notice ladder incl. the half-yearly tier; **s.13(2)–(3)** arrears
    lapse rules; **s.15** abandoned premises (7-day Form TL4 **pasted** on the
    premises); **s.16** the 7-day notice; **s.24–27** proceedings; Forms TL1–TL8.
  - **s.37**: a sitting tenant may apply **in Form TL11** for an order declaring a
    rent increase **unreasonable**; the court weighs the general level of rents in
    the locality and witness evidence (Form TL12 hearing notice). **There is no
    percentage cap on increases** — s.37 is the remedy. ([same][lagoslaw];
    [Mushrooms][mush])
- **Rent Control and Recovery of Residential Premises Law, Cap R6, Laws of Lagos
  State 1997** — still in force for rent-control machinery. Its s.4 is
  *stricter*: incoming tenant 6 months (categories 11–12) / 12 months (13–18);
  **sitting tenant 3 months**; offence ₦50,000 or six months. It also provides
  rent receipts (s.29) and establishes the **Rent Tribunals**.
  ([LawGlobal Hub][lgr], [LawGlobal s.4][lgr4], [aolegal FAQ][aolegal],
  [Lawyard FAQ][lawyard])
- **Rent Tribunal** — a specialised forum for residential landlord/tenant
  disputes: excess advance rent, failure to give receipts, unlawful eviction,
  service-charge disputes, repairs, overcharging. ([Ownkey][ownkey] — C)
- **Pending, NOT law**: the Lagos State Tenancy and Recovery of Premises Bill
  (2025/2026) would cut the monthly-tenant advance cap to **three months** and
  raise the penalty to ₦1,000,000 / three months' imprisonment. ([Mondaq][mondaq],
  [Mushrooms][mush2])

### Federal Capital Territory, Abuja (B)
- **Recovery of Premises Act, Cap 544, Laws of the Federation of Nigeria 1990**
  is the governing statute. s.7 quit notice; s.8 the notice ladder (**no
  half-yearly tier**); s.9 timing; s.10 application to court. ([omaplex][omp],
  [Starlion][sl])
- **Eve-of-the-anniversary rule**: an Abuja quit notice must expire on the eve
  of the anniversary of the tenancy. Lagos changed this — a Lagos notice is valid
  if it terminates **on or after** the expiry date. This is one of the sharpest
  practical differences between the two regimes. ([cjokoyelawview][cjk],
  [TheNigeriaLawyer][tnl])
- **Jurisdiction by annual rental value**: District Court where the value is
  ₦5 million or below; the FCT High Court above that. ([omaplex][omp] — C, single
  source, 2024)

### Rivers (B, two named statutes)
- **Recovery of Premises Law, Cap 109, Laws of Rivers State 1999** — s.6(1)(d)
  notice length (six months for a yearly tenant); **s.7**: the notice must
  terminate on **the eve of the anniversary** of the current term.
  ([BarristerNG][bng], [Wigwe, RSUST][wigwe])
- **Landlord & Tenant Law, Cap 75, Laws of Rivers State** — **s.75(1): rent is
  payable in arrears, at the end of the term, unless the parties agree
  otherwise.** This is the single most counter-intuitive, most useful state
  detail found in this whole dossier: the national assumption ("rent is paid in
  advance") is *reversed by default* in Rivers. ([BarristerNG][bng])
- "In Rivers State and most other states, **except Lagos State**, Notice to Quit
  must terminate on … the Eve of the Anniversary of the current term."
  ([BarristerNG][bng])

### Edo (A — primary text from the state judiciary)
**Rent Control and Recovery of Residential Premises Edict 1977** (Edict No. 4,
Cap. 74; the text still reads "State" means **Bendel State**, Edo's predecessor):
- **s.33 Rent Books**: landlords must issue **prescribed Rent Books in addition
  to receipts**, and the Rent Book "shall be in the custody of the tenant".
- **No premium**: unlawful for anyone, in consideration of the grant, continuance,
  surrender or giving up of a tenancy, to require or receive **any loan or
  premium**; any such payment is **recoverable by the tenant and deductible from
  rent**.
- **Standard rent**: a tribunal may fix the standard rent, and once fixed it
  **supersedes the agreed rent** and binds landlord, tenant and mortgagee; where
  the agreed rent is lower, the landlord may only apply to vary it after six
  months.
- "Court" includes the High Court, magistrates' courts **and customary courts**;
  service by **pasting** on a conspicuous part of the premises is good service
  where the tenant cannot be found; **Form B** is the notice to quit signed by the
  landlord himself.
- It **repealed** the Recovery of Premises Law as it relates to residential
  accommodation, and the Magistrates' Court Law provisions on landlord/tenant
  actions.
- Academic assessment: Edo's framework is "outdated" beside Lagos 2011, with far
  less ADR. ([Edo State Judiciary PDF][edo], [ABUAD Law Journal][abuad])

### Cross River (A — official state laws PDF)
**Rent Control and Recovery of Premises Law, Chapter R3, Laws of Cross River
State 2004** (original commencement 12 August 1985) — the most distinctive
regime found:
- **s.1 Maximum rent chargeable** and a system of **prescribed rent** (s.5–7),
  including prescribed rent for **furnished** accommodation.
- **s.2–3 Rent Control Courts**, whose jurisdiction on tenancy matters sits in
  the state magistracy, presided over by Magistrates; **s.4** the court obtains
  expert opinion from the **Department of Lands**.
- **s.54 Application**: applies to all residential accommodation in the state
  **except maisonettes**; the state is divided into **zones A1, A2, B, C, D, E
  and F** for fixing rents by accommodation category (Schedule 1).
- **s.34 Rent book and receipts**; s.29–31 warrant of possession (**in force three
  months**, and it justifies entry); s.33 distress for rent; s.36 returns;
  s.37 protection of court members.
- **Rent Tribunals no longer operate in Cross River** — they existed under the
  1977 law, repealed by s.56 of the current one. ([Cross River State IRS/CRSIDA
  PDF][crs], [tandfonline][tandf])

### Delta (B)
**Rent Control and Recovery of Residential Premises Law, Cap R5, Laws of Delta
State (2006)** — cited alongside Lagos and Cross River as one of the state
regimes with near-identical notice and recovery provisions. ([tandfonline][tandf],
[RSIS][rsis])

### Kwara (A — official state laws portal)
**Rent Control and Recovery of Residential Premises Law, Chapter R2** (1995;
commencement 21 September 1995):
- **s.3 Rent Tribunals**, each constituted of a **chairman who has practised as a
  legal practitioner in Nigeria for not less than five years** plus two other
  persons of probity representing landlords and tenants, appointed by the
  Governor, and assigned to **zones** (e.g. the Omu-Aran Zone, covering Ekiti,
  Irepodun, Ifelodun, Edu and Oyun LGAs).
- **s.5 Standard rent**; s.4 agreement as to rents; **s.8 distress for rent only
  in execution of a court judgment** and in accordance with the Sheriffs and
  Civil Process Law; s.7 a transfer of any landlord burden to the tenant is
  treated as an alteration of rent.
- Applies to **all residential accommodation throughout Kwara State**, and the
  earlier Recovery of Premises Law is repealed to that extent.
  ([kwaralaws.ng][kwara])

### Oyo (B)
- **Recovery of Premises Law, Cap 144, Vol. V, Laws of Oyo State 2000** — s.2(1)
  definition of rent; s.7 the quit notice.
- **Rent (Increase Restriction) Law, Cap 145, Vol. V, Laws of Oyo State 2000** —
  a dedicated statute on rent increases, cited as the state's answer to
  "arbitrary rent increases … especially in urban areas".
- **Limitation Law of Oyo State 1978, s.17** — a maximum of **six years** for a
  landlord to apply to recover arrears of rent (*Ihekwoaba v. Oyedeji*).
  ([TO Legal Group, Ibadan study][oyo]; [RSIS][rsis] lists "Cap 71, Laws of Oyo
  State 2000" among the state landlord/tenant laws — note the two different caps
  cited for Oyo; unresolved, see §9)

### Enugu (A for the bill, B for the principal law)
- A **Landlord and Tenant Law, Cap. 101, Laws of Enugu State** is the principal
  law — the amending bill's own text cites it as "**Cap. 101, Laws of Enugu State,
  2004**", while press reports of the same bill say **2024**. The bill PDF is the
  better source; the discrepancy is unresolved.
- **Pending, NOT law**: the Bill for a Law to Amend the Landlord and Tenant Law
  (first reading 25 February 2025, sponsor Hon. Okey Mbah, Nkanu East) would
  cap **agency fees at 10% of rent**, cap **legal fees at 10%** (payable only to
  a qualified legal practitioner), **abolish caution fees**, set eviction
  timelines, require agents to be certified by the **Enugu State Housing
  Development Corporation**, and punish breaches with a **₦500,000 fine, six
  months' imprisonment, or both**.
- **As of December 2025 it had not been passed.** ICIR: "a bill aimed at
  regulating these exploitative practices was introduced … it has yet to be
  passed, leaving tenants vulnerable." No evidence of passage since.
  ([bill PDF][enugubill], [Punch][punch], [ICIR][icir], [Guardian][guardian])

### Imo, Osun, Ondo, Akwa Ibom, Bauchi (C — one academic footnote each)
A single comparative paper lists, among "the law of landlord and tenant
applicable in the various States of Nigeria": **Imo State Tenancy and Rent Tax
Law 2013**; **Law of Landlord and Tenant, Cap 65, Laws of Osun State 2002**;
**Cap L4, Laws of Kwara State 2007**; **Cap 75, Laws of Ondo State 2006**;
**Cap 71, Laws of Akwa Ibom State 2000**; **Cap 79, Laws of Bauchi State 2006**;
**Cap 71, Laws of Oyo State 2000**.
Useful, but each rests on one source — flagged for confirmation before it goes on
a page. ([RSIS IJRISS][rsis])

### Kaduna (C)
**Kaduna State Landlord and Tenant Law, 2018** — stated purpose: regulate rights
and obligations under tenancy agreements, including **procedure for rent
control**, recovery of premises and connected purposes. A modern, post-2010
enactment, i.e. closer in vintage to Lagos 2011 than to the 1970s edicts.
([PolicyVault Africa][pv])

### Kano — the honest "we found nothing" (C)
"We reviewed **Kano State's official laws portal and found no published rent
control legislation** applicable to private residential rentals … Kano does not
have official rent control or caps on annual increases, so landlords can freely
reprice at lease renewal." ([The African Vestor, January 2026][kano])
This is a *negative* finding, and it is usable — but as "no rent-control
legislation was found", never as "there is no law".

### Anambra — no rent control in force, a bill in motion (B)
- "**There are no rent control laws to regulate rents charged by landlords**" —
  Chairman, Landlords/Tenants Association, Onitsha branch (Punch, June 2026).
- The **Anambra State House of Assembly is set to enact a law** curbing rising
  rents and exploitative practice, especially in **student communities**
  (Vanguard, March 2026, after NANS protests).
- The proposed **Anambra Rent and Tenancy Law** is backed by a rights group
  (CEHRAWS, July 2026).
  ([Punch][punch2], [Vanguard][vg], [The News Chronicle][tnc])

[lagoslaw]: https://eleniyancares.com/wp-content/uploads/2016/08/Tenancy-Law.pdf
[lgr]: https://www.lawglobalhub.com/rent-control-and-recovery-of-residential-premises-law/
[lgr4]: https://www.lawglobalhub.com/section-4-rent-control-and-recovery-of-residential-premises-law/
[aolegal]: https://www.aolegal.net/wp-content/uploads/2020/07/FREQUENTLY-ASKED-QUESTIONS-ON-LANDLORD-AND-TENANT-2.pdf
[lawyard]: https://www.lawyard.org/opinions/faqs-on-the-rent-control-and-recovery-of-residential-premises-law-of-lagos-state-by-olubunmi-solaja/
[ownkey]: https://ownkey.com/ng/blog/tenant-rights-nigeria
[mush]: https://mushrooms.ng/blog/quit-notice-rent-increase-rights-nigeria
[mush2]: https://mushrooms.ng/blog/lagos-tenancy-bill-2026-explained
[mondaq]: https://www.mondaq.com/nigeria/landlord-tenant-leases/1759858/why-tenancy-law-matters-in-lagos-state-the-key-provisions-of-the-new-lagos-state-tenancy-and-recovery-of-premises-bill-2025
[omp]: https://omaplex.com.ng/an-overview-of-the-legal-framework-for-recovery-of-premises-in-nigeria/
[tnl]: https://thenigerialawyer.com/tenancy-crisis-part-two-how-to-calculate-notice-to-quit-the-procedure-for-recovery-of-property/
[bng]: https://barristerng.com/expiration-of-rent-does-not-determine-a-tenancy-relationship-c-s-onyimah-esq/
[wigwe]: https://www.researchgate.net/profile/Dr-Christian-Wigwe/publication/274377789_RECOVERY_OF_PREMISES_IN_NIGERIA_AN_ASSESSMENT_OF_THE_RELATIONSHIP_OF_LANDLORD_AND_TENANT_LAW/links/551d07310cf20d5fbde56474/RECOVERY-OF-PREMISES-IN-NIGERIA-AN-ASSESSMENT-OF-THE-RELATIONSHIP-OF-LANDLORD-AND-TENANT-LAW.pdf
[edo]: https://edojudiciary.gov.ng/wp-content/uploads/2016/10/Rent-Control-And-Recovery-Of-residential-Premises-Edict-1977.pdf
[abuad]: https://journals.abuad.edu.ng/alj/article/view/1791
[crs]: https://crsida.crossriverstate.gov.ng/CRS%20Laws%202004%20Vol%206_120056.pdf
[kwara]: https://kwaralaws.ng/product/r2rent-control-and-recovery-of-residential-premises-law/
[oyo]: https://tolegalgroup.com/wp-content/uploads/2020/05/AN-EVALUATION-OF-CONFLICT-IN-LANDLORD-AND-TENANT-RELATIONSHIP-ON-RESIDENTIAL-PROPERTY-IN-IBADAN-OYO-STATE.pdf
[rsis]: https://rsisinternational.org/journals/ijriss/Digital-Library/volume-3-issue-1/262-269.pdf
[enugubill]: https://thenigerialawyer.com/wp-content/uploads/2025/02/A-bill-to-amend-Landlord-and-Tenant-Law-of-Enugu-State.pdf
[punch]: https://punchng.com/enugu-assembly-moves-to-regulate-tenancy-fees-landlord-charges/
[icir]: https://www.icirnigeria.org/in-enugu-cut-throat-fees-by-agents-lawyers-landlords-deepen-housing-crisis/
[guardian]: https://guardian.ng/news/enugu-moves-to-cap-house-rent-fees-abolish-caution-fee/
[pv]: https://www.policyvault.africa/policy/kaduna-state-landlord-and-tenant-law-2018/
[kano]: https://theafricanvestor.com/blogs/news/kano-buy-rent-out
[punch2]: https://punchng.com/anambra-residents-seek-soludos-intervention-over-soaring-rent/
[vg]: https://www.vanguardngr.com/2026/03/anambra-assembly-to-enact-law-on-house-rents/
[tnc]: https://thenews-chronicle.com/rights-group-backs-proposed-anambra-rent-law-urges-protection-for-both-tenants-and-landlords/

---

## 6. Bills that are NOT law — must never be published as current rules

| Bill | Status | Trap |
|---|---|---|
| Enugu Landlord & Tenant (Amendment) Bill, 2025 | First reading Feb 2025; **not passed** as of Dec 2025 | Would abolish caution fees — publishing it as law would tell Enugu tenants their caution fee is banned. It is not. |
| Anambra Rent and Tenancy Law | Legislative process begun March 2026; backed July 2026 | Anambra has **no** rent control in force today. |
| Lagos Tenancy and Recovery of Premises Bill, 2025/2026 | Pending | Would cut the monthly advance cap 6 → 3 months. Current law is still 6 (sitting) / 12 (new). |

---

## 7. National claims that are FALSE and must not creep in

- "Rent increases are capped at X%." **No state or federal law fixes a
  percentage.** Lagos gives a *court* remedy (s.37, Form TL11) instead.
- "Rent must always be paid in advance." **Rivers law defaults to rent in
  arrears** (Cap 75, s.75(1)) unless agreed otherwise.
- "A quit notice always needs six months." Depends on the tenancy type, and on
  the agreement.
- "All states cap advance rent at one year." That is **Lagos 2011 s.4** (and
  Lagos's own 1997 law differs again). Most states have no such cap.

---

## 8. Where the evidence stands: 37 jurisdictions

| Tier | Jurisdictions | What we have |
|---|---|---|
| **A — named statute + sections, primary or official source** | Lagos, FCT, Edo, Cross River, Kwara | Full state box, citable sections |
| **B — named statute, practitioner/academic source** | Rivers, Delta, Oyo, Enugu | State box, with source attribution |
| **C — statute name from a single source** | Imo, Osun, Ondo, Akwa Ibom, Bauchi, Kaduna | Confirm before publishing specifics |
| **D — negative finding (usable, carefully worded)** | Kano (no rent-control legislation found), Anambra (none in force; bill pending) | "We could not verify…" box |
| **E — nothing verified** | Abia, Adamawa, Bayelsa, Benue, Borno, Ebonyi, Ekiti, Gombe, Jigawa, Katsina, Kebbi, Kogi, Nasarawa, Niger, Ogun, Plateau, Sokoto, Taraba, Yobe, Zamfara | No state-specific page until something is verified |

**Tier E is 20 of 37 — including Ogun, which we already publish four pages for.**
That is the honest state of the evidence after this research, and it is the
reason the expansion has to be gated rather than generated in bulk.

*Caveat on method:* several search results for Nigerian state law were Kenyan,
Indian and US statutes (Rent Restriction Act Cap 296, Model Tenancy Act, Nevada
NRS 118A, Florida Statutes 83, Iowa Code 562A). Those were discarded. Some
Nigerian results are law-firm marketing pages of uneven quality; where a claim
rests only on one of those it is marked C.

---

## 9. What would close each gap

For any Tier E state, one of these is enough to promote it:

1. The state's revised laws PDF or official laws portal (as found for Cross
   River, Kwara, Edo) → gives chapter, title and sections.
2. A state judiciary or House of Assembly publication of the statute.
3. A court judgment naming the statute ("…the Recovery of Premises Law, Cap X,
   Laws of Y State 20ZZ").
4. A reported, dated bill at second reading or beyond (gives a *pending* box,
   clearly labelled as not law).

What is **not** enough: a tenancy-agreement template on a document site
mentioning "the Tenancy Law of X State" (that is how the Ogun gap stands
today — a Scribd template, nothing more).

---

## 10. Publication rule adopted from this research

1. **No state page ships without a state-specific block** naming either the
   statute (with citation) or an explicit "we could not verify a state-specific
   statute here, and here is what to check locally".
2. **Every state block carries its sources** on the page, and the confidence
   tier.
3. **Bills are labelled as bills**, in the same sentence as the current rule.
4. **Uniqueness gate**: no two same-tool state pages may exceed **80%** pairwise
   similarity, and every page must carry **≥ 250 words of body text that appears
   on no other state page**. Enforced in `qa.py` (step 13) once the pages pass;
   measured by `tools/audit_state_pages.py` until then.
5. **Tier E states do not get four tool pages.** They get nothing until verified
   (or, if the owner prefers coverage over depth, one clearly-labelled hub page
   per state — never four near-duplicates).
6. **Expansion follows the evidence, not the map.** 12 → 37 is the ambition;
   the next states to add are the ones in tiers B and C as each is confirmed.

---

*Researcher's note: this dossier is the evidence, not the copy. Nothing in it
should be pasted onto a page without the house rule applied — verified facts as
facts, everything else as practice plus "confirm with a lawyer".*

---

## 11. Corrections forced by the deeper pass (8 Oct 2026)

Rule Zero sent me back to primary sources. It found **errors in §5 and §8 of
this dossier**. They are recorded here rather than silently amended, because
the earlier versions are what an earlier session would have built from.

### 11.1 Lagos has no Rent Tribunal — the earlier note was wrong

The dossier listed "Lagos Rent Tribunal" as the forum. It is not.

- s.48 of the Tenancy Law 2011 repeals the **Rent Tribunals (Abolition and
  Transfer of Functions) Law 2007**.
- The tribunals had already been abolished and their functions transferred to
  the Magistrates' Courts (*Commonwealth Law Bulletin* 46(1), n.65).
- s.47 defines "Court" as the High Court and Magistrates' Court of Lagos State
  and **expressly excludes the Customary Court**.
- s.2(4): proceedings go to the High Court where the rental value exceeds the
  Magistrates' Court jurisdiction under the Magistrates' Courts Law.
- The "₦250,000 tribunal cap" was already flagged as dated; it is in fact
  moot, because there is no tribunal to have a cap.

### 11.2 Edo is a tribunal state — and the live Edo pages are wrong

The generator currently describes Edo with "recovery-of-premises legislation"
and "the Magistrates' Courts in Edo State". Both are wrong.

- s.4 establishes **Rent Tribunals**: a chairman of ≥5 years' standing plus
  two persons of probity; quorum is chairman + one.
- **s.41(2) repealed the Recovery of Premises Law** to the extent it relates to
  accommodation in residential premises, and s.41(3) repealed the Magistrates'
  Court Law landlord/tenant provisions.
- s.2: "court" **includes customary courts**.

This is a live factual error on four published pages, not merely thin copy.

### 11.3 The Lagos 1997 Rent Control law's status is genuinely disputed

§5 presented Cap R6 as "separate, surviving". That is one side of a live
argument and must be published as one side.

- s.48 of the 2011 Law repeals **only** the Rent Tribunals (Abolition and
  Transfer of Functions) Law 2007 — it does not expressly repeal the 1997 law.
  Practitioners relying on that say the 1997 law still governs the four areas
  excluded by s.1(3).
- Other practitioner and academic sources say flatly it is repealed and "no
  longer applicable".
- Even among those who apply it, the advance-rent figures are reported
  inconsistently and **do not reconcile** (half a year / three months in one
  account; 6/12/3 months by category, ₦50,000 or six months, in another).

**We therefore publish neither figure as fact.** Both views of the survival
question go on the page.

### 11.4 The advance-rent picture is far more varied than "Lagos-only"

§5 said an enforceable cap is "essentially Lagos-only". Now that Cross River
and Kwara have been read, that is wrong:

| Jurisdiction | Cap in advance | Cite |
|---|---|---|
| **Lagos** (2011 Law) | 6 months (sitting, monthly) / 1 year (sitting, yearly) / **1 year (new tenant, no six-month branch)** | s.4(1)–(4) |
| **Cross River** | **3 months** from individual tenants; 12 months from tenants other than individuals | s.6(6) |
| **Kwara** | s.4(6): 1 year individual / 2 years commercial · s.35(6): **3 months** individual / 12 months commercial — **the statute contradicts itself** | s.4(6), s.35(6) |
| **FCT** | **No cap at all** — a genuine, verified gap | — |

Cross River is the strictest jurisdiction verified: **three months for an
individual**, a quarter of what Lagos allows a new tenant.

### 11.5 Arrears triggers vary by a factor of two

| Jurisdiction | Monthly tenant in arrears → tenancy determines | Cite |
|---|---|---|
| Lagos | **6 months** | s.13(2) |
| Lagos (quarterly/half-yearly) | 1 year | s.13(3) |
| Cross River | **3 months** | s.15 proviso |
| Kwara | **3 months** | s.17 proviso |
| FCT | **no shortcut — serve the notice** | — |

### 11.6 Notice ladders differ in a way that is easy to get wrong

Lagos s.13(1)(d) provides a **half-yearly tier (three months)**. The FCT Act
(Cap. 544 s.8), Cross River (s.15) and Kwara (s.17) **do not** — they run
week / month / quarter / half-year. A page that prints "half-yearly: 3 months"
as if it were national law is wrong for three of the five jurisdictions here.

Two further divergences:

- **Kwara, Chapter L4:** a **tenant at will is entitled to no notice period at
  all** — against a week everywhere else, including Kwara's own s.17(1)(a).
  The reconciliation is unknown to us and is recorded as an open question.
- **Edo, s.18 proviso:** where rent is payable in advance for a monthly or
  quarterly tenancy, the landlord may not give notice to quit or recover
  possession during the **first six months** of the tenancy, except on the
  tribunal's order or with the tenant's consent.

### 11.7 Alternative accommodation: Kwara requires it, Edo may dispense with it

Kwara s.26(1): no possession order unless the tribunal or court considers it
reasonable **and** either it has power under the Second Schedule **or** it is
satisfied **suitable alternative accommodation is available** — suitability
being judged by proximity to place of work, the tenant's means, and extent and
character. Edo's tribunal may order possession **without proof of alternative
accommodation** where it considers it reasonable.

### 11.8 Cross River's rent figures are simply not published

The 2004 revised edition (Vol. 6) carries an editorial note that **Schedule 1
(Zones) and Schedule 2 (Prescribed rents) have been omitted** and "will be
included in subsequent updates". s.54(2) tells us seven zones exist — A1, A2,
B, C, D, E, F — but the rents themselves are unavailable. **We publish the
zones, because s.54(2) states them; we do not publish rents, because we
cannot.**

---

## 12. Where the research stands

Five jurisdictions have reached tier A with section-level citations. All five
are now written up in `tools/state_law_data.py`, the data layer that will drive
the generator. **15 open questions are recorded** and none of them is guessed
at — where the primary text was not captured, the page says nothing rather
than filling the gap.

Two states we publish four pages each for (**Ogun, Plateau**) still have
**nothing** verified behind them. Per the publication rule in §10 they should
not have four-tool pages at all.

Cross River and Kwara are tier A but are **not** among the 12 states we
currently publish. They are the two states we could add honestly, today.

---

## 13. Corrections from the Kano / Anambra pass (8 Oct 2026)

### 13.1 Anambra was wrong in §8 — it was tier D, and it is not

§8 recorded Anambra as "none in force, bill pending". **That was wrong.**

The Court of Appeal in *Amah v. Ozouli* (CA/E/298/2006) [2010] NGCA 6 identifies
the **Landlord and Tenant Law, Cap. 76, Laws of Anambra State** as the law
governing recovery of possession, and quotes from it:

- **s.172** — limitation of orders and judgments.
- **s.173** — no order for recovery of possession or ejectment unless the court
  is satisfied that **suitable alternative accommodation is available for the
  tenant**.
- **s.173(2)** — the court may order possession **without** proof of alternative
  accommodation where it considers it reasonable, if a circumstance in **s.174**
  is proved.
- **s.144** (from Wigwe) — channels matters to the Magistrate Court where it can
  hear them, on the Abuja pattern. Wigwe notes the limit: wholly excluding the
  High Court would offend **s.272 of the 1999 Constitution**.

That is the **same architecture as Kwara s.26 and its Second Schedule** — now
confirmed in two of our jurisdictions.

What is pending in Anambra is a **new** Rent and Tenancy Law. There was already
one. Our page previously said otherwise.

### 13.2 A by-product: Enugu's citation is now resolved

The same judgment holds that the law applicable in Enugu is the **Landlord and
Tenant Law, Cap. 101, Revised Laws of Enugu State, which came into operation on
27 August 1991**. Our notes carried both "Cap. 101 of 2004" and other dates.
The 1991 date is commencement; 2004 is the revised edition. Both were right
about different things.

### 13.3 Kano: the negative survived a second pass, and that is the finding

A second targeted search for Kano returned **no Nigerian authority at all** —
the results were Kenyan (Cap. 296), Indian (Model Tenancy Act 2021) and US
state law. On the published sources there is **no Kano rent-control statute**,
hence no Kano standard rent, no identifiable Kano rent tribunal, and no
advance-rent cap.

The honest inference is separate from that, and is labelled as inference:
Kano was carved from the **Northern Region**, whose recovery law is cited as
the **Recovery of Premises Law, Laws of Northern Nigeria 1963** — given as
**Cap. 113 Vol. 3** by Wigwe and as **Cap. 115** by a practitioner list. Those
citations conflict and are not resolved.

### 13.4 A bug the pass exposed

Unverified states were still asserting specific forums and statutes — the
Ogun page said "Disputes go to the Magistrates' Courts in Ogun State" directly
above its own tier-E disclaimer. The overlay now replaces those strings with
an explicit "not yet verified" for any state whose law we cannot cite.
