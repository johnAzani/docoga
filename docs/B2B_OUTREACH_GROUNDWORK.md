# DocOga B2B outreach groundwork
## Evidence-led discovery before Business pricing or diaspora USD pricing

**Research date: 10 October 2026 · Owner: John Azani · Status: desk research and proposed operating plan; NOT outreach authorization.**

**Commercial scoreboard:** no B2B interviews, qualified opportunities, pilots, purchases or renewals established by this research. The owner's successful pass-email resend is operational evidence, not B2B demand. No messages sent, accounts created, money collected, pricing changed or production code deployed in this research.

This dossier supersedes the outreach, pricing hypotheses and unsupported comparisons in `B2B_DISCOVERY.md`. That earlier file remains historical, with a correction notice. Read this document with `B2B_DISCOVERY_WORKBOOK.md` and the empty CSV templates in `docs/templates/`.

## Executive decision

Start with **permissioned discovery among hands-on rental/property administrators**, preferably reachable through an existing relationship in Abuja. Run a small Lagos comparison sample rather than assuming Abuja represents Nigeria. Lead with the work, not the product: reconstruct the last receipt, renewal or agreement preparation task, its approvals, errors, elapsed time and who actually pays.

The initial hypothesis is narrow: **a person repeatedly preparing routine documents may value a faster draft-to-reviewed-output workflow without migrating their property records into another system.** This is a hypothesis, not established demand or a defensible moat.

Do not lead with eviction notices, powers of attorney, replacing lawyers, rent recovery guarantees, nationwide compliance or an annual team subscription. The initial observed task should be a **synthetic rent receipt** if interview evidence identifies receipt preparation as painful. A receipt is not risk-free: wrong amounts, dates, rent periods, payer details or payment status can cause harm.

### Six decisions that must come from discovery

1. Which role has a frequent, consequential document task?
2. Is the bottleneck drafting, collecting facts, approval, signature, retrieval or payment reconciliation?
3. Does DocOga solve that bottleneck better than their existing method?
4. Can the person approve a purchase, or who must approve it?
5. What scope can be delivered honestly, securely and with low support effort?
6. What commercial commitment follows successful use? Price discovery comes AFTER these answers; diaspora USD work remains a separate later gate.

## 1. Evidence standard and research limitations

- **Primary-regulator/platform:** official directive or platform policy. Establishes what that source says, not a legal opinion about every situation.
- **Primary-organisation:** official organisation website. Evidence of advertised services or displayed prices, not independent proof of registration, customers, performance or operational maturity.
- **Repository-observed:** code/document inspection at `c51ce63` on the session branch; no browser/network security certification.
- **Method guidance:** experienced-practitioner advice; useful design input, not proof of Nigerian buyer behaviour.
- **Hypothesis/proposal:** this report's judgement, sampling target or threshold. Not a market statistic.
- **Unknown:** must remain blank or explicitly unknown, not filled by inference.

Search and targeted page retrieval covered official Meta/WhatsApp policy, NDPC GAID, NIESV/AEAN, company service pages, competitor pages and YC interview guidance. Selected GAID passages were read, including Articles 17–19; the entire 117-page directive was NOT reviewed. The retrieval tool parses only the first 30 PDF pages. This is not a complete Nigerian legal compliance audit.

No customer conversations were conducted; company websites may be stale or promotional. No prospect's legal registration or buying authority was independently confirmed. We did not test competitor products or check out paid plans. No market-size extrapolation is justified. Recheck prices and contact routes before use.

## 2. Corrections to the earlier research

| Earlier claim/assumption | Correction and operational consequence |
|---|---|
| B2B needs no new product | Discovery needs no new product; fulfillment might. Ten document generators do not constitute team administration, branding or procurement readiness. |
| WhatsApp-first from listing numbers | Permission-first. A directory is a research source, not a consent database. Do not scrape, buy or broadcast numbers. |
| 50 conversations beat 50,000 visitors | Unsupported rhetorical comparison. Measure both costs and outcomes rather than treating it as evidence. |
| We do not compete with property suites | We compete with them whenever bundled receipts/leases solve the same job. Integration-free use is only a hypothesis. |
| State correctness is a differentiator | Not yet established: state-law dossier records unresolved jurisdictions; a state landing page is not verified generator logic. |
| ₦2,000 is 1–2% of a flat-fee lawyer agreement | Arithmetic was wrong for the cited ₦15k–₦30k range: it is about 6.7–13.3%. Legal review and a self-help draft are not equivalent products anyway. |
| 40–75% less than all named templates | At ₦2k vs ₦2k, saving is zero; vs ₦8.5k, about 76.5%. Remove the blanket claim, not merely adjust the percentage. |
| Lawyer fees/agency caps validate savings | Exact current legal basis and comparable service scope were not established. Do not use fee caps or replace-lawyer savings in recruitment. |
| ₦5k–₦50k monthly Business band | Withdraw as an anchor. Adjacent products do not establish DocOga willingness to pay. |
| 500 businesses × ₦2m monthly | An arithmetic scenario, not a market model. No evidence those accounts would pay that amount for this product. |
| 30-day team pass versus annual site card | Billing period is unresolved; neither should be promised during discovery. |
| Businesses will pay by transfer | Ask about the last software purchase and procurement steps. Bank transfer preference is not a verified automatic issuance workflow. |
| LTR is an Abuja operating channel because registered at CAC Abuja | CAC registration location does not prove local operating presence. Treat it as a national thematic channel; confirm access/location. |
| Brevo authentication and delivery still blocked | Resolved by owner-guided production enablement and actual inbox receipt on 10 Oct. Separate from B2B validation. |

Keep competitors' prices internal to the interviewer until the participant's existing spend and price exposure have been recorded. Do not prime answers with DocOga's target revenue.

## 3. What we can honestly demonstrate today

### Repository inspection

| Area | What was observed | Restriction before B2B promises |
|---|---|---|
| Document creation | `site/index.html` implements browser-side forms/rendering for property and SME documents. | Demonstrate the exact output, not an abstract claim of legal sufficiency. |
| Drafts | `saveDraft`, `loadDrafts`, `saveProfile` use browser storage. | Local drafts are not a central archive, team sync, backup, audit trail or access-control system. Shared-device exposure matters. |
| Pass | Worker issues codes with expiry/reference/email data; email resend now received by owner. | A reusable bearer code is not a user account, seat licence, role or employee offboarding mechanism. |
| Business card | Advertises annual/per-team, firm's logo, shared pass, invoice/transfer, named human. | No end-to-end team/branding/procurement implementation established in inspected paths. Treat these as unvalidated promises requiring correction before sales use. |
| Logo | No customer-logo upload/rendering flow found in the main generator inspection. | Firm-name fields in some templates are not a logo feature across all documents. |
| Payments | Flutterwave pass path exists; separate `/issue` bridge intentionally disabled. | Do not collect an ad hoc transfer or turn on the bridge to satisfy a prospect. |
| Privacy policy | Says payment information is handled entirely by provider; 'essentially no personal data'. | Worker does process/store purchaser email/reference/code data and uses mail providers. Policy requires a factual update before procurement claims. |
| Terms | Pass described as 30 days from activation; codes non-transferable. | Online expiry logic and annual/shared-team promise need reconciliation. Do not use a shared personal pass as a substitute for agreed team terms. |
| Support | Business card promises named human and one-working-day quote. | Not autonomous fulfillment; measure owner time. Do not promise guaranteed response capacity. |
| Legal claims | Existing copy includes broad validity and lawyer-cost assertions. | Flag for content/legal review; do not repeat in outreach. |

**No product edits were made here.** Interviews about workflows can proceed after permission. Product-led recruitment, paid team pilots and large-account demos need an accurate capability sheet and resolution of misleading public promises. These are scoped prerequisites, not permission to start an enterprise rebuild.

### Data-flow explanation for prospects

Separate document content, licensing data and communication data. Inspection shows document drafts saved in the browser; the Worker handles purchase/pass records and sends email. This is NOT a basis to say 'no data ever leaves your device': analytics, payments, licensing, email and user-initiated sharing have separate flows. Verify network behaviour and third-party scripts before making a stronger claim.

Do not ask interviewees to upload tenant agreements, IDs, bank statements, staff payroll or pass codes. Use synthetic examples; where a participant describes a real event, collect workflow facts rather than client identities. A processor agreement, controller/processor analysis, retention policy, access controls and security responses may be needed depending on eventual deployment; do not claim certification or NDPC registration not verified.

## 4. Buyer segmentation: role before company size

**Recommended first cohort (proposal):** operator-led agencies/property managers with repeated rental administration, an accessible decision-maker and willingness to discuss a recent task. Do not infer headcount or portfolio size from a professional website.

| Segment | User / likely approver to validate | Potential job | Why test / why exclude |
|---|---|---|---|
| Hands-on rental agency | Admin/letting officer; owner/principal | Receipts, tenancy facts, renewals | Direct observation possible; exclude if exclusively property sales or no recurring admin. |
| Established surveying/management practice | Property administrator; branch/practice head; counsel | Review handoffs, consistent output | Valuable workflow comparison; may require existing templates and approval controls. |
| Multi-branch manager | Operations lead; procurement/IT/legal | Standardisation, permissions, reporting | Learn requirements, but not first sale: product gaps and longer approvals are hypotheses to test. |
| Landlord with a portfolio | Landlord or assistant | Occasional records | Useful contrast; seasonality may defeat monthly subscription. |
| SME HR/payroll admin | HR/generalist; proprietor/finance | Employment/payslips | Separate later cohort; don't mix its economics with property. No automatic tax-compliance claims. |
| Associations / advisers | Secretariat, education lead, lawyer | Recruitment access or practitioner critique | Channels/expert interviews, NOT counted as buyers. |

**Geography:** Abuja-first is an access/logistics hypothesis because the owner is there, not evidence of stronger demand. Prefer warm permissioned access wherever it exists. Include Lagos in the comparison without paid travel. No assumptions that tenancy rules, approval structures or payment schedules transfer between states.

**Proposed first 12 organisation-level interviews:** 6 hands-on rental agencies/managers, 2 established practices, 2 portfolio landlords, 2 property administrators using an existing suite. Aim for 8 Abuja/FCT and 4 Lagos if permissioned access permits. Expert/channel calls are additional, not part of the 12. Count two employees from the same business as one organisation when evaluating demand. At least half should not be close friends/relatives; report referral-source concentration.

This is purposive qualitative sampling, NOT representative market research. If only five agree, report five; never manufacture the quota or convert it to market share.

## 5. Alternatives and competitive pressure

| Alternative | Evidence available 10 Oct | Discovery implication |
|---|---|---|
| Existing Word/Excel files, receipt books, typists | Not measured in this cohort; candidate baseline | Ask to reconstruct last task; zero incremental software spend can still mean time cost, but no pain means no sale. |
| LawBridge | Public tenancy template ₦2k–₦3k; Client Pro ₦5k/month incl. two templates and discounted review. Vendor claim. [1](https://www.lawbridge.com.ng/pricing) | Compare self-help generation separately from lawyer review; do not assume clients use it. |
| LawDepot NG | Public single-document licence ₦8,500. Vendor claim, no checkout verification. [1](https://www.lawdepot.com/ng/real-estate/residential-tenancy-agreement/) | An alternative price, not evidence of buyer volume or DocOga WTP. |
| OurProperty NG | Official page advertises tenant/lease management, branches/staff, branding and free start. [1](https://ourproperty.ng/) | Core competitive substitute; don't say document functionality is absent. Full business pricing not verified here. |
| MyTenant | Advertises lease generation/e-signing, accounting, owner statements and free start with paid extras. [3](https://www.mytenant.ng/) | Ask why a standalone tool would coexist. Features not tested; no adoption or uptime claims endorsed. |
| RentDesk (rentdeskapp.com) | Page displays ₦5k/₦15k/₦35k monthly tiers and explicitly solicits EARLY ACCESS. [4](https://www.rentdeskapp.com/) | Price visibility does not prove mature production service or paying customers. Ignore marketing time-saving percentages. |
| RentalDesk (rentaldesk.co.ke) | Kenya-focused page advertises M-Pesa and KES plans. [10](https://rentaldesk.co.ke/) | Different product from RentDesk; not a Nigerian willingness-to-pay anchor. |
| Existing lawyer | Scope and bill require interview evidence | A review relationship may be essential, not a cost to eliminate. Seek practitioner collaboration, not displacement. |

Do not use a vendor's customer count, testimonials, alleged compliance, ROI or 'number one' badge as independent evidence. Do not use rich-result schema prices where visible page text disagrees. No competitor purchase or account creation was necessary for this research.

### Candidate differentiation — experiments, not advertising claims

- **No migration:** can an operator produce an acceptable draft without importing a portfolio? Test against their template baseline.
- **Phone usability:** can the actual user complete and export it on their own phone without assistance? Owner receipt of an email does not prove this.
- **Less retyping:** measure actual changes, corrections and handoffs, not just form-entry time.
- **Simple occasional use:** does a time-limited pass fit seasonal work better than monthly/annual subscriptions? Ask after workflow evidence.
- **Lawyer-compatible handoff:** does the reviewer accept the format and clauses? Do not promise DOCX export, custom templates or e-signatures until demonstrated.

## 6. Research shortlist — not a contact list and not qualified leads

All entries below are **uncontacted; consent unknown; buying need, budget, authority, team size and volume unknown**. Service descriptions come from organisation pages or indexed excerpts. No personal phones/emails are reproduced. The question column is a hypothesis tailored to the service, not a claim about their problems.

| ID | Organisation / evidence route | Why research it | Interview role / tailored question | Priority and verification limit |
|---|---|---|---|---|
| P01 | JMJ Properties — [10](https://jmjglobalservices.com/) | Advertises Abuja tenant management, rent collection, reporting and renewals. Full service page read. | Rental operations: 'After a rent payment is confirmed, who prepares, checks and sends the receipt?' | Early candidate if permission obtained; ignore 'voted #1' and testimonial claims. |
| P02 | Aadum & Company — [2](https://aadumandcompany.com/) | Abuja office; property/facility management advertised. Full page read. | Property administrator: 'How does tenancy information move from your team to the person preparing documents?' | Practice comparison; NIESV/ESVARBON status is self-claimed, not independently checked. |
| P03 | Bankole Adelugba & Co. — [4](https://bankoleadelugba.com/) | Abuja estate-services page advertises sourcing, rent collection and maintenance. Full page read. | Management lead: 'Which recurring document, if any, needs rework before it can leave the office?' | Early candidate; confirm management activity/volume rather than infer from valuation services. |
| P04 | Bello & Company — [3](https://bellovaluers.com/who-we-are/) | Abuja profile advertises property/facilities management. Detailed indexed profile reviewed. | Admin/management: 'Who approves documents and retrieves earlier versions when there is a correction?' | Established-practice comparison; named historical projects are not proof of current portfolio. |
| P05 | Ngwoke–Ngwoke & Co. — [7](http://ngwoke.com.ng/) | Advertises estate management and multiple locations. Indexed official content reviewed. | Operations: 'Do branches use their own files or centrally approved versions?' | Later comparator; confirm actual Abuja access and current workflow. |
| P06 | Odudu & Co. — [8](https://www.oduduandco.com/contact) | Advertises Abuja among regional offices and facility-management service. Official indexed contact page reviewed. | Branch operations: 'Is routine rental paperwork handled here or elsewhere?' | Screening first; valuation-heavy scope may make this poor fit. Do not use a valuation request form deceptively. |
| P07 | Diya, Fatimilehin & Co. — [1](https://diyafatimilehin.net/) | Lagos/multi-office service site advertises lease/facility management. Full relevant service content read. | Property administrator: 'Where does preparation end and legal/manager approval begin?' | Larger comparator, not first enterprise pitch; no current branch-volume assumption. |
| C01 | NIESV national — [1](https://www.niesv.org.ng/) | Official professional body with property-management remit and membership resources. | Secretariat/education contact: ask about a permitted volunteer interview invitation. | Channel, not buyer. No endorsement, partnership or member-data access implied. |
| C02 | NIESV Abuja branch candidate — [3](https://abujaniesvapp.org.ng/) | Indexed branch site describes Unity branch. | Ask national body to confirm current branch contact/route. | HOLD: direct fetch failed; indexed membership figures not used as current market size. |
| C03 | AEAN — [1](https://aean.org.ng/membership/) | Official membership page outlines estate-agent professionalisation/training. | Secretariat: permission for voluntary recruitment, not member phone list. | Channel; no paid membership required or authorised. Old category/fee pages conflict with newer page; do not use them. |
| C04 | Landlords & Tenants' Rights Initiative — [1](https://landlordsandtenants.org/) | Official site describes rights education and ADR for both sides. Full page read. | Practitioner: 'Which information omissions repeatedly create avoidable disputes?' | Expert/channel, not legal endorsement or assumed Abuja operating office. |

**How to expand without scraping:** use NIESV's corporate directory to identify organisations; check their own service pages; record public organisation URL and date; then seek a permitted introduction. For Lagos, government guidance recommends checking LASRERA registration before property transactions; directory presence does not validate product demand. [1](https://lagosstate.gov.ng/news/all/view/685588c05e4c9d6cecaa165a)

Do not message all eleven. Start with two genuine permissioned introductions plus one channel invitation route. Public contact pages may be intended for service enquiries, not supplier marketing: never pretend to be buying a property, applying for a job or filing a complaint to reach someone. No paid lead databases, private group exports or employee enrichment.

## 7. Outreach permission and privacy rules

### Primary findings

The current WhatsApp Business Messaging Policy explicitly covers BOTH Business App and Platform, requires supplied contact details plus opt-in, and requires honoring opt-outs. Template/24-hour service-window rules are in the Platform-specific section; don't incorrectly impose those API rules on manual Business App conversations. [1](https://whatsappbusiness.com/policy/)

Meta developer guidance states consent may be general rather than specifically WhatsApp-only, subject to local law, but must identify the business and permission to communicate. Our conservative operating choice is to explicitly name **DocOga, WhatsApp, research purpose and follow-up scope**. This is clearer than relying on a vague historic opt-in. [2](https://developers.facebook.com/documentation/business-messaging/whatsapp/getting-opt-in)

NDPC GAID Article 18(1)(a) states consent is required for direct marketing; Article 17 requires accountability for consent and easy withdrawal. Article 19 addresses cookies/tracking. A business person's named email/mobile can still be personal data. Do not use 'B2B' or 'research' to disguise a sales solicitation. [1](https://ndpc.gov.ng/wp-content/uploads/2025/07/NDP-ACT-GAID-2025-MARCH-20TH.pdf) [3](https://iclg.com/practice-areas/data-protection-laws-and-regulations/nigeria/)

This plan does not declare every unsolicited corporate email unlawful, nor assert that a generic inbox guarantees an exemption. Where the lawful route is unclear, use inbound or an authorised channel rather than making the owner a test case.

### Approved operating design (still requires owner review before sending)

1. Warm introducer asks the prospect whether they WANT an introduction; does not hand over numbers first.
2. Alternatively, an association administrator permits an invitation on a channel where that content is allowed; interested people initiate contact voluntarily.
3. Alternatively, owner publishes an honest invitation on their own business profile/status. Viewing it is NOT permission to direct-message the viewer.
4. An inbound participant agrees to the interview, note-taking and any limited follow-up. Record exact scope/time privately.
5. Separate permission for calls, a later demo, future marketing and testimonial use. Interview participation is not blanket marketing consent.
6. One agreed follow-up after 3–5 working days at most; no reply means close recruitment for now. No cross-channel chasing. Stop immediately after refusal/opt-out.

**Not allowed:** first cold WhatsApp message merely to ask for WhatsApp consent; mass broadcasts; group-member scraping; purchased lists; automatic outreach extensions; importing payment-customer emails into marketing; bulk messages through Brevo transactional credentials; sending as an association or claiming approval without it.

### Minimal research-data practice

Explain: 'John/DocOga will use your answers to understand document workflows and decide what to improve. Please leave out client identities. Notes are optional; recording is off. You can skip a question or stop. This does not add you to a marketing list.' Give the existing verified support route privately for questions/withdrawal.

Private record: organisation/contact mapping, source of permission, exact permission scope, date, follow-up permission and suppression status. Repository: only anonymous/coarsened observations and aggregate counts. Even a pseudonym can be identifiable when joined with a named firm; don't commit identifiable quotes or commercially sensitive spend.

**Proposed retention, not a statutory schedule:** review raw interview notes after 30 days; delete or de-identify by 90 days unless a documented active pilot/legal need requires otherwise. Keep only the minimal protected suppression record necessary to avoid contacting opt-outs; do not put it in Git. No audio/video recording by default. Any recording needs separate permission and agreed deletion. Do not collect documents containing other people's data just because the interviewee agreed.

A free spreadsheet/note app already controlled by the owner can suffice; sharing must remain private. Free tooling does not eliminate data-protection duties, transport costs, mobile data costs or human effort. No new paid services are required for this plan.

## 8. Discovery interview: 20 minutes, problem first

Method: YC advises asking about current behaviour, observing tasks where possible, deferring the product pitch and avoiding hypothetical feature approval. Apply that guidance; do not import generic cold-outreach tactics without Nigerian consent safeguards. [1](https://www.ycombinator.com/library/Iq-how-to-talk-to-users)

### A. Permission and context — 2 minutes

Confirm role, geography actually served, and responsibility for documents. Ask permission for brief notes, not recording. Explain commercial affiliation honestly. 'No purchase is required and I am not offering legal advice.'

### B. Last real task — 6 minutes

Ask ONE question at a time:

1. 'Tell me about the last rental document you helped prepare. What triggered it?'
2. 'What happened first, then next, until it was sent or signed?'
3. 'Where did the information come from?'
4. 'Who checked it? What changed during that check?'
5. 'Which part, if any, caused difficulty?'
6. 'What happened because of that difficulty?'

Capture preparation time separately from waiting time. Ask about the most recent correction, not 'Would fewer mistakes help?' If they say everything works well, record that rather than inventing pain. A typed number remembered vaguely is self-report, not measured evidence.

### C. Frequency, alternative and cost — 5 minutes

- 'How many of that document did your team finish in the last 30 days? Is that typical?'
- 'What about the last three months and your busiest period?'
- 'How many were new documents versus small edits/copies?'
- 'What do you use today? When did you last change that method, and why?'
- 'What do you pay specifically for preparing/checking it, if anything?'
- 'Who bears that cost: your agency, landlord, tenant or another party?'
- 'Is the payment for drafting alone, legal review, negotiation, service or something else?'

Units managed are NOT documents/month. Annual rent collection can make receipt demand seasonal. A fee billed onward is not automatically an avoidable cost to the agency.

### D. Decision path and constraints — 4 minutes

- 'Who decided on the last tool you adopted? How did approval and payment work?'
- 'Who would need to approve a change to this workflow?'
- 'Which document format and review process must stay the same?'
- 'Do staff work on shared devices? How do you remove access when someone leaves?'
- 'What data could never be uploaded or shared with a supplier?'
- 'Do you have a next occurrence of this task? When?'

Record whether the interviewee is user, champion, payer, approver or blocker; one person may occupy several roles. Don't demand procurement paperwork during a first chat.

### E. Close — 3 minutes

Summarise neutrally: 'I heard X happens Y times and Z is the difficult part. What did I get wrong?' Ask for permission to invite them to a synthetic task test only if relevant. Agree exact next action, owner and date. No demo automatically follows an interview; consent and suitability still matter.

### Questions to avoid

'Would you use this?', 'Would ₦X be cheap?', 'How much for unlimited everything?', 'Don't agents waste time?', 'Would you like logos/AI/a dashboard?' and 'Can you introduce ten friends?' These encourage politeness, anchors and solution invention. If a participant volunteers a price, record it as hypothetical with scope and prior price exposure, not validated revenue.

## 9. Evidence collection and synthesis

Use separate fields for **quote**, **observation**, **interpretation** and **next test**. Never turn 'we manage many properties' into a number. Use unknown, zero, not applicable and declined as different values.

Evidence ladder:

0. Courtesy reply / like / 'great idea'.
1. Specific recent problem self-reported.
2. Workflow observed with synthetic or safely redacted example and concrete consequence.
3. Existing effort/spend established; approver and next task identified.
4. Participant schedules and completes a task test.
5. Repeat unaided use and documented request to continue.
6. Authorized commercial offer accepted and actual payment verified.
7. Renewal/repeat payment after initial value and support measured.

A letter of intent is not payment; payment is not retention; a single buyer is not product-market fit. Never count a channel partnership conversation as multiple customers.

**Interview quality screen:** recent actual task + clear workflow + actual alternative + known role + consented notes. If one is missing, mark partial, not completed-qualified. Warm introductions can bias answers; split reporting by recruitment source and existing relationship.

**Weekly synthesis:** group by document job and segment, not requested features. Show numerator/denominator: '4 of 7 interviewed rental agencies described correction delays', not '57% of Nigerian agencies struggle'. Include no-pain and disqualified cases. Deduplicate parent firm/branches and report contradictions.

## 10. Pilot design — only after workflow evidence and honest product scope

### Stage 1: synthetic usability test, no payment or pass issuance

One operator, one device, one existing supported task, no tenant identities. Use their normal method first on a fictional scenario, then DocOga on a comparable scenario; reverse order for some participants to reduce learning effects. Do not time only typing: include input gathering, corrections, preview, export/print and review. Let the user drive; count help requests. No claim that an exported PDF is approved for legal use.

Measure: completion/failure, active minutes, elapsed minutes, number/severity of errors, reviewer acceptance, help requests, output format, whether a second task can be completed unaided. The existing free mode is sufficient for early tests; disclose watermark/limits. Do not unlock passes, alter prices or create fake payments to make the demo work.

### Stage 2: bounded operational pilot proposal

Requires separate owner approval, buyer permission, corrected capability/privacy/terms statements and agreed safe scope. Define operator, document type, geography, start/end, review responsibility, data handling, supported outputs, support allowance and stop conditions. No custom branding or annual team entitlement unless actually implemented/tested and agreed.

Pilot length should cover a real recurring task, not an arbitrary 7-day trial that ends before the next annual renewal. A 2–4 week observation window is a proposal, adjustable to cadence. If no next task is due, do not score inactivity as product rejection; schedule later or choose another participant.

**Stop immediately** for wrong financial facts, unsafe legal claims, confidential data exposure, mistaken entitlement, inability to export accurately, or dependency on unbuilt capabilities. Route disputes, eviction, powers of attorney and tax/legal interpretation to qualified professionals; don't improvise advice in a sales conversation.

### Stage 3: commercial validation

Only after value observed: present a specific deliverable scope and clearly separated pricing experiment, with owner-approved naira terms. No USD. No fake invoices, scarcity or promises. Verify payment independently through the authorized payment process, not a transfer screenshot alone. Existing ₦2k retail purchase proves willingness for retail access only, not willingness for a team premium.

## 11. Economics without inventing a price

Let:

- N = relevant documents per month (actual, not total properties).
- T0/T1 = active minutes per document before/after, including corrections.
- R = credible fully loaded hourly staff cost, if available.
- C = genuinely avoidable external drafting expense, excluding necessary legal review.
- O = new monthly onboarding/amortised training/support effort cost to the buyer.

**Estimated capacity value = N × (T0 − T1) / 60 × R.**
**Estimated economic benefit = capacity value + C − O.**

Do not present staff time as cash savings unless the buyer can actually reduce paid cost; often it is capacity. Avoid double-counting review savings in both T and C. Do not monetise litigation avoidance without credible causal evidence. If R is unknown, report minutes and tasks, not naira.

Illustration ONLY: 20 tasks × 12 minutes saved = 240 minutes = four hours monthly. At 2 tasks/month it is 24 minutes. Same software, very different opportunity. These are not customer measurements or recommended prices.

**Seller contribution per account** = collected revenue minus payment fees, refunds, marginal service costs, onboarding amortisation and support labour. ₦0 hosting does not imply zero cost. Record sales/research minutes separately from recurring support. Annual upfront cash is not monthly recurring revenue; recognised revenue/refund obligations must be handled appropriately.

**Willingness-to-pay sequence:** current spend → who pays → measurable benefit → approver → precise scope → budget discussion → approved offer → verified payment → repeat use/renewal. Do not average price guesses from unrelated segments. Small convenience samples do not support Van Westendorp/Gabor–Granger curves or a statistically 'optimal price'.

**Existing retail anchor:** the public ₦2,000 pass cannot be hidden. Record whether participants saw it before the interview. If the retail product fully solves a business's needs, do not manufacture a premium team tier. Discover whether extra value is genuinely needed and deliverable.

**USD gate:** Nigerian demand does not establish diaspora demand, foreign procurement needs or willingness to pay in USD. Revisit only after local job/segment/value evidence, actual usage and commercial scope are established, followed by separate international-payment and legal/account checks. No automatic FX conversion of a naira package.

## 12. Proposed operating thresholds — decision rules, not forecasts

### First sprint: permission and recruitment

Prepare this pack, choose two reachable introductions and one approved channel route. Log access, not 'leads generated'. Owner reviews exact recipient/context/message before any send. If no access exists, build an opt-in invitation rather than buy or scrape a list.

### First five qualified organisation interviews

Review for task similarity, frequency, severity, alternative satisfaction and approver access. Do not wait for 50 interviews to fix a plainly false hypothesis. If all five are satisfied with current tools, stop that positioning and investigate why.

### Up to twelve qualified interviews

Proposed gate to a narrowly scoped prototype/pilot: at least five independent organisations describe the SAME recurring problem with a recent example; at least three of those can identify a near-term task and agree to a synthetic test; at least two tests complete successfully with plausible advantage over baseline. Report raw counts, dissent and recruitment bias. These thresholds reduce arbitrary building; they do not prove market size or product-market fit.

If the main pain is collections, central records or approvals rather than drafting, do not label that as validation of DocOga. Either narrow the segment, test a standalone subtask, or make a separately approved product decision. Do not secretly build a property-management suite.

### After tests

Continue only when output quality is acceptable, repeat use plausible, legal/privacy scope clear and support effort manageable. Later ask for an owner-approved commercial pilot. No Business price publishes from these interviews alone.

### Scheduling and automation

Start when permissioned participants are available; two interviews/day is an owner-capacity ceiling proposal, not quota. Prefer their working hours in WAT; ask rather than assume. No paid travel/events/software. Discovery is deliberately human and time-bounded, while longer-term fulfillment should become low-touch. Automated outreach is NOT a shortcut to the owner's autonomy goal. Automate anonymised summaries/metrics later, not consent or buyer judgement.

## 13. Risks and next-action register

| Priority | Risk | Required action / owner of action |
|---|---|---|
| P0 before sending | No consent for named recipient/channel | Owner approves legitimate recruitment context; agent drafts; recipient opts in. |
| P0 before product-led sales | Business card promises unverified branding/team service | Agent prepares narrow correction proposal; no deployment without scope approval. |
| P0 before pilot | Privacy/terms don't fully describe pass data/expiry/team rights | Factual code-to-policy reconciliation; legal judgement where required. |
| P0 | Legal output used as advice or payment proof | Synthetic initial tasks, qualified review, no false receipts, no legal validity guarantees. |
| P1 | Directory/professional status overstated | Confirm organisation/service/contact and relevant registration; no endorsement claims. |
| P1 | Interview politeness mistaken for demand | Last-event questions, contrary evidence, observed tasks, actual commitments. |
| P1 | Monthly assumptions conflict with seasonal use | Record last 30/90 days and next task; test usage cadence before billing cadence. |
| P1 | Shared pass creates team security/control problem | Explicitly document current limitations; no workarounds sold as seat management. |
| P1 | Free tools conceal support costs | Track owner time and per-account contribution. |
| P1 | Research data leaks through Git or chat | Private operational register; synthetic templates only in repo; redact identities. |
| P2 | Channel dependence | Report source mix; do not depend on one association gatekeeper. |

### What remains unknown

Actual buyer pain/frequency, current workflow spend, willingness to change, purchasing authority, affordable delivery cost, price, sample access, verified firm registration, real branch activity and market size. Enterprise requirements, NDPC registration obligations for DocOga's precise processing, legal review of templates, and a complete analytics/privacy compliance audit also remain unresolved. Desk research cannot answer these by adding more competitor screenshots.

### Immediate next move

Owner chooses whether there is an existing relationship with a property operator or a permitted association/community introduction. Ask for relationship/role only, not phone numbers or client documents. Then prepare ONE context-specific invitation for review. If no such relationship exists, begin with an opt-in public invitation and verified channel enquiry, not cold WhatsApp.

## Source register and audit notes

Sources were accessed/searched 10 Oct 2026. Link citations above identify claim-specific sources; numeric IDs are search-result IDs and may repeat across searches. Full URLs disambiguate.

- Official WhatsApp policy, updated 23 Sep 2026: policy URL redirects to `whatsappbusiness.com/policy/`; relevant App/Platform/consent sections read. Broader restricted-vertical sections not needed for this campaign scope.
- Official Meta opt-in guidance: current indexed text explicitly distinguishes general opt-in from the older WhatsApp-specific requirement. Where vendor blogs conflict, use Meta plus stricter local-law safeguards.
- NDPC GAID primary PDF: Articles 17–19 directly retrieved; targeted passages, not entire document. ICLG Nigeria 2026 used as secondary legal interpretation, not substitute for the regulator text.
- YC current library article `Iq-how-to-talk-to-users` includes transcript; relevant interview guidance read. An older guessed `6g` URL returned 404 and was not used as evidence.
- NIESV national current site retrieved; branch candidate fetch failed although indexed. Old directory addresses differ from current national page: verify route before any visit, never send owner to an unconfirmed office.
- AEAN newer membership page differs from legacy fee/category pages. No membership purchase or assumption of free event access.
- LTR official site describes rights education/ADR; registration in Abuja is not operating-address evidence.
- Prospect company service pages provide existence/service hypotheses only. Avoid third-party employee enrichment, testimonials and 'best agency' rankings.
- RentDesk visible early-access pricing overrides structured-data ambiguity; RentalDesk Kenya is a different entity. Competitor performance/compliance/adoption claims not independently verified.
- Local primary evidence: `site/index.html`, `site/privacy.html`, `site/terms.html`, `worker/index.js`, `docs/STATE_TENANCY_RESEARCH.md`, `DOCOGA-RISK-LOG.md`, `docs/MANDATE.md`, `docs/DEPLOY_STATUS.md`. No production modifications during research.
