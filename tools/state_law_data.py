#!/usr/bin/env python3
"""Verified, section-cited tenancy law per Nigerian state.

WHY THIS FILE EXISTS
--------------------
`tools/audit_state_pages.py` measured the 48 state pages we ship: a median of
**94.2% identical** to each other, with **3 unique words** per page. The cause
was upstream of the templates — the generator had no state-specific legal
content to work with, so ten of twelve states were described with the same
sentence: "recovery-of-premises legislation".

This file is the fix, and it is built under Rule Zero (see
docs/SESSION_CONTEXT.md): every statement below is traced to a named statute,
ideally section by section, ideally from the state's own judiciary or laws
portal. Where a source conflicts, the conflict is recorded rather than
resolved silently. Where nothing could be verified, it says so.

CONFIDENCE TIERS (published on the page, not hidden in a comment)
  A  named statute + sections, from a primary/official source
  B  named statute, from a practitioner or academic source
  C  statute name only, single source
  D  verified negative — we looked and there is nothing
  E  nothing verified — DO NOT PUBLISH A STATE PAGE

RULE: a state may only appear in `STATE_LAW` if it reaches tier A-D. Tier E
states get no four-tool pages. That rule is the whole point of the file.

Compiled 8 Oct 2026.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# LAGOS — Tier A. Full text of the Tenancy Law read section by section.
# ---------------------------------------------------------------------------
LAGOS = dict(
    slug="lagos",
    name="Lagos",
    place="Lagos",
    full="Lagos State",
    tier="A",
    tier_note="Read section by section from the enrolled text of the Law.",

    statutes=[
        dict(
            title="Tenancy Law of Lagos State 2011",
            citation="Law No. 14 of 2011, Laws of Lagos State",
            commenced="Assented at Ikeja 24 August 2011; in force 24 August 2011 (s.49)",
            signed_by="Babatunde Raji Fashola (SAN), Governor of Lagos State",
            source="https://nnamdiebolegal.wordpress.com/wp-content/uploads/2017/10/tenancy-law-no-14-2011-laws-of-lagos-state.pdf",
        ),
        dict(
            title="Rent Control and Recovery of Residential Premises Law 1997",
            citation="Edict No. 6 of 1997; also printed as Vol. 7, Laws of Lagos State 2003 and as Cap. R6",
            commenced="21 March 1997",
            status="DISPUTED — see `lagos_dispute` below. Do not state as settled law.",
            source="https://www.lawglobalhub.com/rent-control-and-recovery-of-residential-premises-law/",
        ),
        dict(
            title="Recovery of Premises Law",
            citation="Cap. 118, Laws of Lagos State 1973",
            status="Applies where the 2011 Law does not — see `excluded_areas`.",
            source="https://classic-attorneys.com/blog-2020-04-10-a-quick-guide-to-the-lagos-tenancy-law/",
        ),
    ],

    # -- The single most Lagos-specific fact, and the one no other state has.
    excluded_areas=dict(
        cite="s.1(3)",
        text=(
            "The 2011 Law does <b>not</b> apply in four areas: <b>Apapa, Ikeja GRA, "
            "Ikoyi and Victoria Island</b>. s.1(3) also lets the Governor exempt further "
            "areas by Order published in the State Official Gazette. Practitioners apply "
            "the older <i>Rent Control and Recovery of Residential Premises Law 1997</i> "
            "and/or the <i>Recovery of Premises Law, Cap. 118 (1973)</i> in these areas "
            "instead — which means the advance-rent cap in s.4 does <b>not</b> protect "
            "a tenant in Ikoyi the way it protects one in Yaba."
        ),
        also_excluded=[
            "residential premises owned or operated by an educational institution for its staff and students (s.1(2)(a))",
            "residential premises provided for emergency shelter (s.1(2)(b))",
            "residential premises in a care or hospice facility, or in a public or private hospital or mental health facility (s.1(2)(c))",
            "premises made available in the course of rehabilitative or therapeutic treatment (s.1(2)(d))",
        ],
    ),

    forum=dict(
        name="the Magistrates’ Courts and the High Court of Lagos State",
        text=(
            "There is <b>no Rent Tribunal in Lagos</b>. The tribunals were abolished and "
            "their functions transferred to the Magistrates’ Courts, and s.48 of the 2011 "
            "Law repealed the Rent Tribunals (Abolition and Transfer of Functions) Law 2007. "
            "s.47 defines “Court” as the High Court and Magistrates’ Court of Lagos State "
            "and <b>expressly excludes the Customary Court</b>. Under s.2(4) proceedings go "
            "to the High Court where the rental value exceeds the Magistrates’ Court "
            "jurisdiction under the Magistrates’ Courts Law."
        ),
        adr=(
            "s.2(3): agreeing to use the Lagos Multi-Door Courthouse or a Citizens Mediation "
            "Centre does not oust the Court’s jurisdiction. s.32: the Court must promote "
            "reconciliation and may refer a case to mediation <b>without the parties’ consent</b>; "
            "the mediator files the agreement for endorsement within 3 days."
        ),
    ),

    notice_ladder=[
        ("Tenant at will", "one week", "s.13(1)(a)"),
        ("Monthly tenant", "one month", "s.13(1)(b)"),
        ("Quarterly tenant", "three months", "s.13(1)(c)"),
        ("Half-yearly tenant", "three months", "s.13(1)(d)"),
        ("Yearly tenant", "six months", "s.13(1)(e)"),
    ],
    notice_extras=[
        "<b>s.13(4) — the Lagos anniversary exception.</b> Three- and six-month notices "
        "<i>need not</i> terminate on the anniversary of the tenancy; they may terminate "
        "on or after the date the tenancy expires. Most other states require expiry on the "
        "eve of the anniversary, so Lagos is the exception here.",
        "<b>s.13(2)</b> — a monthly tenant <b>six months</b> in arrears: the tenancy lapses and "
        "the Court makes an order for possession and arrears on proof. No quit notice needed.",
        "<b>s.13(3)</b> — a quarterly or half-yearly tenant <b>one year</b> in arrears: the same.",
        "<b>s.13(5)</b> — a fixed-term tenancy needs <b>no quit notice at all</b> once it "
        "determines by effluxion of time; the landlord serves a seven-day notice of intention "
        "to recover possession in <b>Form TL5</b>.",
        "<b>s.13(6)</b> — the nature of a tenancy is determined, absent contrary evidence, "
        "by reference to when rent is paid or demanded.",
    ],

    advance_rent=dict(
        cite="s.4",
        text=(
            "s.4 is the only enforceable advance-rent cap we have verified anywhere in Nigeria, "
            "and it is <b>asymmetric between sitting and new tenants</b>:"
        ),
        rows=[
            ("Sitting tenant — monthly", "may not be asked for, or pay, more than <b>6 months</b>", "s.4(1)–(2)"),
            ("Sitting tenant — yearly", "may not be asked for, or pay, more than <b>1 year</b>", "s.4(1)–(2)"),
            ("New or would-be tenant", "may not be asked for, or pay, more than <b>1 year</b> — there is no six-month branch for a new tenant", "s.4(3)–(4)"),
        ],
        penalty=(
            "<b>Both sides commit the offence.</b> s.4(5): any person who <i>receives or pays</i> "
            "rent in excess is liable on conviction to a fine of <b>₦100,000</b> or "
            "<b>3 months’ imprisonment</b>."
        ),
    ),

    receipts=dict(
        cite="s.5",
        text=(
            "Lagos is one of the few states that makes a rent receipt a statutory duty and "
            "prescribes what must be on it. s.5(1): every landlord <b>shall</b> issue a receipt "
            "on payment of rent. s.5(2): the receipt must state —"
        ),
        must_state=[
            "the date on which the rent was received",
            "the names and addresses of the landlord and the tenant",
            "the description and location of the premises",
            "the amount of rent paid",
            "the period to which the payment relates",
        ],
        penalty="s.5(3): a landlord who fails to issue the receipt is liable on conviction to a fine of <b>₦100,000</b>.",
        extra=(
            "<b>s.10 — deposits and service charges.</b> Where the landlord requires a security "
            "deposit, payment for services and facilities, or service charges in a block with "
            "common parts, the landlord or agent must issue a <b>separate receipt</b>, and the "
            "tenant is entitled to a <b>written account at least every six months</b> of how the "
            "money was disbursed."
        ),
    ),

    caution_fee=dict(
        cite="s.10, s.11",
        text=(
            "The 2011 Law does <b>not</b> use the words “caution fee”. What it regulates is "
            "the money taken <i>alongside</i> rent: a security deposit, charges for services and "
            "facilities, and service charges (s.10(a)–(c)). For each, the landlord owes the tenant "
            "a separate receipt and a six-monthly written account. Separately, <b>s.11</b> provides "
            "that the party who engages a professional pays that professional’s fee — so the "
            "practice of the tenant funding the landlord’s lawyer’s fee is not supported by the Law."
        ),
        warning=(
            "A <b>bill</b> before the Lagos State House of Assembly would go further and regulate "
            "agents’ commissions. It has not been passed and must not be described as current law."
        ),
    ),

    increase_challenge=dict(
        cite="s.37",
        text=(
            "s.37 gives a sitting tenant a real remedy. On <b>Form TL11</b> the tenant applies to "
            "the Court for an order declaring an increase unreasonable. The Court issues a hearing "
            "notice on <b>Form TL12</b> and weighs (a) the general level of rents in the locality "
            "or a similar locality, (b) evidence of witnesses, and (c) any special circumstances. "
            "If satisfied, it may order on <b>Form TL13</b> that the increase be changed to a "
            "specific amount."
        ),
        protection=(
            "<b>s.37(4): it is unlawful for a landlord to eject a tenant while that application "
            "is pending.</b>"
        ),
        false_claim=(
            "There is <b>no statutory percentage cap</b> on rent increases in Lagos or anywhere "
            "else in Nigeria. Any page or article claiming a fixed percentage limit is wrong."
        ),
    ),

    repairs=dict(
        cite="s.7(3), s.8(vi)",
        text=(
            "s.7(3): the tenant keeps the premises in good and tenantable repair, "
            "<i>reasonable wear and tear excepted</i>. s.8(vi): the landlord effects repairs and "
            "maintains the external and common parts. s.8 also requires the landlord to keep the "
            "premises insured, not to disturb quiet enjoyment, to pay all rates and charges "
            "stipulated by law, not to withdraw a common facility or service, and "
            "<b>not to seize any item or property of the tenant or interfere with the tenant’s "
            "access to it</b> — which is the statutory answer to lock-outs and seized belongings."
        ),
    ),

    protections=[
        "<b>s.6</b> — quiet and peaceable enjoyment includes privacy, freedom from unreasonable "
        "disturbance, exclusive possession (subject to the landlord’s restricted right of "
        "inspection) and use of common areas.",
        "<b>s.6(2)</b> — a tenant who made improvements with the landlord’s <i>previous written "
        "consent</i> may claim compensation for them on quitting.",
        "<b>s.29</b> — where a landlord refuses to accept rent, the tenant may apply to the Court "
        "to pay the rent into the Court Registry.",
        "<b>s.44(1)</b> — demolishing, altering or modifying a building to eject a tenant without "
        "the Court’s approval, forcibly ejecting or attempting to, or threatening or molesting a "
        "tenant, is an offence: <b>₦250,000 or 6 months’ imprisonment</b>.",
        "<b>s.41</b> — a warrant for possession runs for three months and may be renewed every "
        "three months, but <b>not more than three renewals</b>.",
        "<b>s.42</b> — no entry on a warrant may be made on a Sunday or public holiday.",
    ],

    lagos_dispute=dict(
        summary=(
            "Whether the 1997 Rent Control law survives is <b>genuinely contested</b>, and the "
            "page says so rather than picking a side."
        ),
        for_survival=(
            "s.48 of the 2011 Law repeals only the <i>Rent Tribunals (Abolition and Transfer of "
            "Functions) Law 2007</i>. It does not expressly repeal the 1997 law, and several "
            "practitioner analyses rely on that to say the 1997 law still governs the four "
            "excluded areas in s.1(3)."
        ),
        against=(
            "Other practitioner and academic sources state flatly that the 1997 Edict was "
            "repealed on the enactment of the Tenancy Law 2011 and is “no longer applicable”."
        ),
        secondary_conflict=(
            "Even among those who apply the 1997 law, the advance-rent figures are reported "
            "inconsistently — one account gives “half a year’s rent in excess” for a yearly "
            "tenancy and “three months in excess” for a six-month tenancy, while another cites "
            "s.4 as six months for incoming tenants in accommodation categories 11–12, twelve "
            "months for categories 13–18, and three months for a sitting tenant, with a penalty "
            "of ₦50,000 or six months. <b>These do not reconcile, so we state neither as fact.</b>"
        ),
    ),

    sources=[
        "Tenancy Law of Lagos State 2011 (No. 14 of 2011) — enrolled text, ss.1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 16, 17–19, 24–27, 29, 32, 37, 41–49 and Schedule Forms TL1–TL14",
        "https://classic-attorneys.com/blog-2020-04-10-a-quick-guide-to-the-lagos-tenancy-law/",
        "https://www.lawyard.org/opinions/faqs-on-the-rent-control-and-recovery-of-residential-premises-law-of-lagos-state-by-olubunmi-solaja/",
        "https://www.lawglobalhub.com/rent-control-and-recovery-of-residential-premises-law/",
        "https://motun911.wordpress.com/2019/09/13/civil-litigationrecovery-of-premises/",
    ],

    open_questions=[
        "Whether the 1997 Rent Control law is in force for the s.1(3) excluded areas — unresolved; the page presents both views.",
        "The correct advance-rent figures under the 1997 law, if it applies — sources conflict; not stated.",
    ],
)

# ---------------------------------------------------------------------------
# ABUJA / FCT — Tier A/B. A federal Act made for one territory, not a
# general federal law. The honest headline here is a gap, not a rule.
# ---------------------------------------------------------------------------
ABUJA = dict(
    slug="abuja",
    name="Abuja (FCT)",
    place="Abuja",
    full="the Federal Capital Territory",
    tier="A",
    tier_note="Statute and sections confirmed; monetary jurisdiction limit from a single source.",

    statutes=[
        dict(
            title="Recovery of Premises Act",
            citation="Cap. 544, Laws of the Federation of Nigeria (Abuja) 1990 — also cited as LFN 2004",
            commenced="1990",
            note=(
                "Although an Act of the National Assembly, <b>it is not a federal law of general "
                "application</b>. It was made specially for the Federal Capital Territory. There "
                "is no federal landlord-and-tenant statute for Nigeria as a whole."
            ),
            source="https://www.fcthighcourt.gov.ng/wp-content/uploads/2025/02/BARR.-JOHN-AWA-KALU-VS-HIS-WORSHIP-MUINAT-FOLASHADE-OYEKA-1-OR.pdf",
        ),
    ],

    forum=dict(
        name="the District Courts and the High Court of the FCT, Abuja",
        text=(
            "Recovery follows the Act through the FCT courts — Magistrates’/District Courts and "
            "the FCT High Court. One practitioner source puts the line at an annual rental value "
            "of <b>₦5,000,000</b> — District Court at or below, FCT High Court above. "
            "<b>This figure rests on a single source and is shown on the page as such (tier C).</b>"
        ),
    ),

    notice_ladder=[
        ("Tenant at will or weekly tenancy", "one week", "s.8"),
        ("Monthly tenancy", "one month — and it must be <b>one calendar month</b>", "s.8"),
        ("Quarterly tenancy", "a quarter (three months)", "s.8"),
        ("Yearly tenancy", "half a year (six calendar months)", "s.8"),
    ],
    notice_extras=[
        "<b>No half-yearly tier.</b> Unlike Lagos s.13(1)(d), the Act does not prescribe a "
        "separate period for a half-yearly tenant. A tenancy exceeding one year is treated as a "
        "yearly tenancy, for which six months’ notice is sufficient.",
        "<b>No arrears shortcut.</b> Lagos s.13(2)–(3) and the Cross River and Kwara provisos "
        "let a tenancy lapse on defined arrears with no quit notice. The FCT Act has no "
        "equivalent — serve the notice.",
        "<b>The date of service is what counts, not the date written on the notice.</b> The full "
        "statutory period must fall between service and the stated expiry; a month means one "
        "calendar month and a year means six calendar months, and no less.",
        "<b>s.7</b> — once the term has ended or been determined by a written notice to quit in "
        "<b>Form B, C or D</b>, the landlord serves written notice in <b>Form E</b> of intention "
        "to proceed to recover possession, dated <b>not less than seven days from the date of "
        "service</b>. That notice <b>cannot be served before the quit notice expires</b>.",
        "<b>s.31</b> attaches the Forms. <b>s.2</b> defines “agent” as a person usually "
        "employed by the landlord in letting or collecting rent, or specially authorised "
        "<i>in writing under the landlord’s hand</i> — so an agent or solicitor needs written "
        "authority before issuing a valid notice.",
    ],

    advance_rent=dict(
        cite="no provision",
        text=(
            "<b>This is a genuine gap in the law, and we say so.</b> The Recovery of Premises Act "
            "sets no limit on how much rent a landlord may demand in advance in the FCT, and "
            "attaches no penalty to demanding more than a year. Unlike a Lagos tenant, an Abuja "
            "tenant asked for two or three years’ rent up front has no statutory cap to point to. "
            "Whatever is agreed should be recorded in the tenancy agreement before money moves."
        ),
    ),

    receipts=dict(
        cite="no statutory receipt provision in the Act",
        text=(
            "The Recovery of Premises Act does not impose the Lagos-style duty to issue a receipt "
            "with prescribed contents. That does not leave an Abuja tenant without a remedy: a "
            "receipt remains the ordinary evidence that rent was paid, and where rent is paid in "
            "cash the burden of proving payment falls on whoever asserts it. Record the date, "
            "amount, period covered and the premises, and keep it."
        ),
    ),

    caution_fee=dict(
        cite="no provision",
        text=(
            "The Act does not regulate caution fees, deposits or agents’ commissions. There is no "
            "FCT equivalent of Lagos s.10 (separate receipt and six-monthly account) or s.11 "
            "(the party who engages the professional pays). Any deposit is therefore a matter of "
            "contract — which is precisely why it must be written down, with the refund conditions "
            "and the deadline stated."
        ),
    ),

    increase_challenge=dict(
        cite="no provision",
        text=(
            "There is no FCT equivalent of the Lagos s.37 application to have an increase declared "
            "unreasonable. A rent increase in the FCT is governed by the tenancy agreement; if it "
            "is silent, the landlord’s ability to raise the rent and the notice required are "
            "matters of negotiation and, ultimately, of the Court."
        ),
        false_claim="No percentage cap on rent increases exists in the FCT or anywhere in Nigeria.",
    ),

    service=dict(
        cite="s.28",
        text=(
            "Where the defendant cannot be found, his dwelling is unknown, or admission cannot be "
            "obtained for service, <b>posting a copy of the process on some conspicuous part of "
            "the premises is deemed good service</b>."
        ),
    ),

    protections=[
        "A landlord may not resort to self-help. Once the seven days expire the occupier becomes a "
        "<b>statutory tenant</b>, removable only by a lawful court order.",
        "<b>s.20</b> — the Court may issue a warrant for possession even where a counterclaim is "
        "undetermined or unsatisfied.",
        "A landlord who obtains an order for possession by intentionally providing false "
        "information commits an offence, and the Court may order reasonable compensation to the tenant.",
    ],

    sources=[
        "Recovery of Premises Act, Cap. 544 LFN (Abuja) 1990 — ss.2, 7, 8, 20, 28, 31 and Schedule Forms B–E",
        "FCT High Court judgment quoting s.7 verbatim: https://www.fcthighcourt.gov.ng/wp-content/uploads/2025/02/BARR.-JOHN-AWA-KALU-VS-HIS-WORSHIP-MUINAT-FOLASHADE-OYEKA-1-OR.pdf",
        "https://omaplex.com.ng/an-overview-of-the-legal-framework-for-recovery-of-premises-in-nigeria/",
        "https://motun911.wordpress.com/2019/09/13/civil-litigationrecovery-of-premises/",
        "https://starlionlegal.com/2020/02/07/recovery-of-premises-an-assessment-of-landlord-tenant-law-in-nigeria/",
    ],

    open_questions=[
        "The District Court / High Court monetary dividing line (₦5m) rests on one source — needs a primary court-rules citation.",
        "Whether any FCT subsidiary legislation regulates agents’ commissions — not found.",
    ],
)

# ---------------------------------------------------------------------------
# EDO — Tier A. Primary text read from the Edo State Judiciary's own PDF.
# NOTE: two Edo provisions remain unverified and are marked as such.
# ---------------------------------------------------------------------------
EDO = dict(
    slug="edo",
    name="Edo",
    place="Edo State (Benin City)",
    full="Edo State",
    tier="A",
    tier_note="Primary text from the Edo State Judiciary. Two provisions still unverified — see open_questions.",

    statutes=[
        dict(
            title="Rent Control and Recovery of Residential Premises Edict 1977",
            citation="Edict No. 4 of 1977, Bendel State of Nigeria — Cap. 74, Laws of Edo State",
            commenced="1 March 1977",
            signed_by="Commodore Husaini Abdullahi, Military Governor, Bendel State — dated at Benin City, 11 February 1977",
            note=(
                "The enactment still reads “Bendel State”: Bendel was split into Edo and "
                "Delta in 1991, and the Edict is received as Edo law. An academic paper cites it "
                "as “Cap R1”; the Judiciary’s own PDF carries “Cap. 74”. "
                "<b>We use Cap. 74 and note the alternative.</b>"
            ),
            source="https://edojudiciary.gov.ng/wp-content/uploads/2016/10/Rent-Control-And-Recovery-Of-residential-Premises-Edict-1977.pdf",
        ),
        dict(
            title="Rent Control (Standard and Maximum Rents) Order 1977",
            citation="B.S.L.M. 11 of 1977",
            commenced="1 March 1977",
            note="Sets standard rents by accommodation type S1–S7 and zone; see `zones`.",
            source="https://edojudiciary.gov.ng/wp-content/uploads/2016/10/Rent-Control-And-Recovery-Of-residential-Premises-Edict-1977.pdf",
        ),
        dict(
            title="Rent Control Maximum Rent Order 1996",
            citation="—",
            note="Listed on the Edo State Judiciary’s legislation archive. Contents not yet read.",
            source="http://edojudiciary.gov.ng/category/legislations-and-rules/",
        ),
    ],

    forum=dict(
        name="the Rent Tribunals of Edo State",
        text=(
            "<b>Edo is a tribunal state, not a magistrates’-court state.</b> s.4 establishes Rent Tribunals constituted of "
            "(a) a chairman who has been in practice as a legal practitioner in Nigeria for "
            "<b>not less than five years</b>, and (b) <b>two other persons of probity</b>, "
            "appointed by the Governor. The chairman plus one other member is a quorum (s.4(4)), "
            "and the tribunal may sit with assessors where it thinks it necessary (s.4(6))."
        ),
        important=(
            "<b>s.41(2) repealed the Recovery of Premises Law to the extent that it relates to "
            "accommodation in residential premises</b>, and s.41(3) repealed the Magistrates’ "
            "Court Law provisions on landlord-and-tenant actions over residential accommodation. "
            "s.2 defines “court” to include the High Court, magistrates’ courts <b>and "
            "customary courts</b> of the State."
        ),
    ),

    rent_control=dict(
        cite="s.5, s.6",
        text=(
            "Edo operates a <b>standard rent</b> regime. s.5(1)–(2): it is unlawful for a landlord "
            "to accept an agreed rent above the standard rent, and where the agreed rent is higher "
            "the tenant pays the <b>standard rent</b>. s.5(3): where the agreed rent is "
            "<i>lower</i>, the tenant continues to pay it — but after <b>six months</b> the "
            "landlord may apply to the tribunal to vary it."
        ),
        supersedes=(
            "<b>s.6(3)</b>: the standard rent fixed by the tribunal <i>supersedes</i> the agreed "
            "rent, and the order binds everyone including the landlord, the tenant and the "
            "<b>mortgagee</b> of the building."
        ),
    ),

    premium=dict(
        cite="s.6(4)",
        text=(
            "<b>“No premium” is black-letter law in Edo.</b> s.6(4): it is unlawful for anyone, "
            "in consideration of the grant, continuance, surrender or giving up of a tenancy, to "
            "<b>require or receive any loan or premium</b>. Any such payment is <b>recoverable by "
            "the tenant</b> and may, without prejudice to any other method of recovery, "
            "<b>be deducted from rent payable to the landlord at any time</b>."
        ),
        plain=(
            "That is the statutory basis for resisting a caution deposit or “commitment fee” "
            "demanded purely as the price of being granted or continuing the tenancy — and it "
            "gives the tenant a self-help remedy: deduct it from the next rent."
        ),
        exception=(
            "s.6(5): a <i>bona fide</i> contractor who invests in developing the property and "
            "takes a lease below the standard rent in consideration of that investment is not "
            "caught."
        ),
    ),

    security_of_tenancy=dict(
        cite="s.16",
        text=(
            "<b>Edo’s strongest tenant protection, and one of the strongest in the country.</b> "
            "s.16(1): once a tenant has applied to the tribunal, <b>any quit notice served "
            "afterwards is of no effect</b>, and no similar notice may be given before the "
            "tribunal’s decision. s.16(2): the tribunal may declare a quit notice <b>invalid and "
            "of no effect</b> if it was not issued <b>in good faith</b>, and its endorsement to "
            "that effect on the notice is sufficient evidence of the decision before any court."
        ),
        plain=(
            "A tenant who takes a genuine dispute to the tribunal cannot be punished for it with "
            "a retaliatory quit notice."
        ),
    ),

    first_six_months=dict(
        cite="s.18 proviso",
        text=(
            "<b>Where rent is payable in advance</b> for a monthly or quarterly tenancy, the "
            "landlord may <b>not</b> give notice to quit or recover possession during the "
            "<b>first six months of the tenancy</b> — except on the order of the tribunal or "
            "with the tenant’s consent. A new Edo tenant who has paid in advance has a "
            "six-month statutory breathing space."
        ),
    ),

    notice_ladder=[],
    notice_ladder_gap=(
        "<b>Not yet verified.</b> The Edict’s graduated notice periods sit in s.18, and the subsection text has not yet been read. We therefore do <b>not</b> publish a figure for Edo. "
        "What is verified is the rule of validity: a notice is ineffective where the time between "
        "the giving of the notice and the determination of the tenancy is less than the period "
        "prescribed in s.18."
    ),

    grounds_for_possession=[
        ("the rent lawfully due is in arrear for <b>one month</b> after it became due", "Edo — one month"),
        ("the tenant has breached a covenant or agreement of the tenancy", ""),
        ("the tenant gave notice to quit and, in consequence, the landlord contracted to sell or let the premises or otherwise took steps whereby he would be seriously prejudiced if he could not obtain possession", ""),
    ],
    grounds_note=(
        "The tribunal may order possession <b>without proof of suitable alternative "
        "accommodation</b> where it considers it reasonable to do so. Note the contrast: Edo’s "
        "arrears trigger is <b>one month</b>, Cross River’s is <b>three</b>, and Kwara requires "
        "<b>suitable alternative accommodation</b> (or a Second Schedule ground) before making "
        "any possession order at all."
    ),

    compulsory_acquisition=dict(
        cite="s.40",
        text=(
            "Where the tribunal finds that a landlord has violated the Edict <b>on two "
            "occasions</b>, the Governor may, on the tribunal’s recommendation, "
            "<b>acquire the landlord’s interest in the premises</b>, with compensation determined "
            "under the Public Lands Acquisition Law."
        ),
    ),

    forms=[
        "Form A — general title of proceedings (In the Rent Tribunals, … District)",
        "Form B — notice to quit signed by the landlord himself",
        "Form C — notice to quit given by an agent or legal practitioner",
        "Form D — notice by landlord to quit lodgings",
        "Form E — notice to tenant of owner’s intention to apply to recover possession (seven clear days from service)",
        "Form F — writ or plaint",
        "Form G — summons for recovery of possession",
        "Forms H and I — appointment and report of appraisers (for valuing improvements)",
        "Forms J, K, L, M — judgments",
        "Warrant for possession",
    ],
    subtenant_warning=(
        "Under Form G, a sub-tenant served with a summons who fails to notify his immediate "
        "landlord is liable to <b>forfeit three years’ rent</b> of the premises he holds."
    ),

    zones=dict(
        cite="Rent Control (Standard and Maximum Rents) Order 1977, B.S.L.M. 11 of 1977",
        detail=(
            "The Order fixes standard rents by accommodation type (S1–S7) and zone, with detailed "
            "building standards: a <b>standard room is not less than 14 square metres</b>; no "
            "adjustment where a room is within 2 square metres of the standard; a 50 kobo increase "
            "or decrease where a room exceeds 15.5 or falls below 12 square metres; a "
            "<b>standard flat</b> has terrazzo flooring in the sitting/dining room and kitchen "
            "with tiled bedroom floors. Areas are classified by location — including whether the "
            "road fronting the property is tarred."
        ),
        stale_warning=(
            "These are <b>1977 figures in kobo</b>. They are stated for what they show about the "
            "structure of Edo rent control, not as current rents — and the 1996 Maximum Rent "
            "Order has not yet been read."
        ),
    ),

    penalties=dict(
        cite="general penalty provision",
        text=(
            "Where no punishment is specifically provided, the general penalty on summary "
            "conviction is a fine of <b>₦50 or imprisonment for one month</b> — a figure that "
            "shows the Edict’s 1977 vintage and is quoted here for completeness, not as a "
            "deterrent."
        ),
    ),

    repeals=dict(
        cite="s.41",
        text=(
            "s.41 repeals the <b>Rent Control Edict 1970</b>, the <b>Recovery of Premises Law "
            "(Cap. 110)</b> to the extent that it relates to accommodation in residential "
            "premises, and the <b>Magistrates’ Court Law (Cap. 105)</b> provisions on actions "
            "between landlord and tenant over residential accommodation."
        ),
    ),

    sources=[
        "Rent Control and Recovery of Residential Premises Edict 1977 (No. 4 of 1977), Edo State Judiciary — ss.2, 3, 4, 5, 6, 16, 18, 40, 41, 42 and Schedule 1 Forms A–M",
        "https://edojudiciary.gov.ng/wp-content/uploads/2016/10/Rent-Control-And-Recovery-Of-residential-Premises-Edict-1977.pdf",
        "http://edojudiciary.gov.ng/category/legislations-and-rules/",
        "https://journals.abuad.edu.ng/alj/article/view/1791 (comparative Edo/Lagos study; cites the law as Cap R1)",
    ],

    open_questions=[
        "The graduated notice periods in s.18 have not yet been read from the primary text, so no figure is given here.",
        "Whether Edo imposes a rent-book duty has not been confirmed from the primary text, so none is stated here.",
        "The rent figures in the Rent Control Maximum Rent Order 1996 have not been read.",
        "Whether Delta State received the same Edict on the 1991 split — likely, but unverified.",
    ],
)

# ---------------------------------------------------------------------------
# CROSS RIVER — Tier A. Read from the State's own revised laws (2004, Vol. 6).
# ---------------------------------------------------------------------------
CROSS_RIVER = dict(
    slug="cross-river",
    name="Cross River",
    place="Cross River State (Calabar)",
    full="Cross River State",
    tier="A",
    tier_note="Read from the official Laws of Cross River State 2004, Vol. 6, Cap. R3.",

    statutes=[
        dict(
            title="Rent Control and Recovery of Premises Law",
            citation="Cap. R3, Laws of Cross River State 2004 (Vol. 6)",
            commenced="12 August 1985",
            note=(
                "Revised edition prepared by the Law Review Committee under the chairmanship of "
                "Eyo O. Ekpo, Attorney-General and Commissioner for Justice, Cross River State; "
                "in force on 31 October 2004."
            ),
            source="https://crsida.crossriverstate.gov.ng/CRS%20Laws%202004%20Vol%206_120056.pdf",
        ),
        dict(
            title="Rent Control and Recovery Law 1977",
            citation="—",
            status="Repealed by s.56 of Cap. R3.",
            source="https://crsida.crossriverstate.gov.ng/CRS%20Laws%202004%20Vol%206_120056.pdf",
        ),
    ],

    forum=dict(
        name="the Rent Control Courts of Cross River State",
        text=(
            "<b>Cross River abolished Rent Tribunals and replaced them with courts</b> — a "
            "structural difference from Edo and Kwara. s.2: the Governor, on the Chief Judge’s "
            "recommendation, divides the State into zones and establishes Rent Control Courts, "
            "with a Gazette notice naming the members. <b>s.3: the Court is an integral part of "
            "the Magistrates’ Court system</b>, presided over by a magistrate who is a qualified "
            "legal practitioner of <b>at least three years’</b> standing at appointment. "
            "s.41: references in any law to Rent Tribunals now read as references to these Courts."
        ),
        valuers=(
            "<b>s.4</b> — where a Court is in doubt on any question of value, it <b>shall obtain "
            "expert opinion from the Department of Lands</b>."
        ),
        procedure=(
            "<b>s.10</b> sets the method an estate valuer must use: inspect and measure the rooms "
            "and note the amenities; treat Schedule 2 rents as the standard; identify the zone "
            "(Schedule 1) and accommodation type (Schedule 2); adjust proportionately for size; "
            "then cost absent or excess amenities, take the annual equivalent, and add or deduct it."
        ),
        rules_committee=(
            "<b>s.49</b> — the Rent Control Courts Rules Committee consists of the Chief Judge, a "
            "magistrate appointed by the Chief Judge, a law officer nominated by the "
            "Attorney-General and appointed by the Chief Judge, and a legal practitioner appointed "
            "by the Chief Judge."
        ),
    ),

    application=dict(
        cite="s.54",
        text=(
            "<b>s.54(1): the Law applies to all residential accommodation throughout Cross River "
            "State, <i>except maisonettes</i>.</b> s.54(2) divides the State into seven zones — "
            "<b>A1, A2, B, C, D, E and F</b> — for fixing rents."
        ),
        why=(
            "The exclusion is deliberate, and the definitions show why. A “maisonette” "
            "under Cap. R3 is a two-storeyed permanent building designed for single-family "
            "occupation with living rooms downstairs and bedrooms upstairs, tiled bathroom, toilet "
            "and kitchen walls and floors, hot and cold water, electricity and an exclusive "
            "courtyard. It is at the top of the market — and it is outside rent control."
        ),
        definitions=(
            "The Law defines its building types precisely: a <b>permanent building</b> has stone, "
            "brick or cement block walls with cement screed and concrete floors and a roof of "
            "corrugated metal or asbestos; a <b>semi-permanent building</b> has mud-and-wattle, "
            "zinc or timber walls with a corrugated metal or asbestos roof; a <b>temporary "
            "building</b> has mud-and-wattle walls and a thatch roof. A <b>standard room</b> is "
            "13–15 square metres; a <b>standard sitting-room</b> at least 35 square metres; "
            "<b>usable floor space</b> excludes kitchen, bathroom, toilet, verandas and passages "
            "under 1.5m wide."
        ),
    ),

    rent_control=dict(
        cite="s.1, s.5, s.6, s.7",
        text=(
            "<b>s.1</b>: rents for residential accommodation in the zones must not exceed the "
            "maximum in Schedule 2. <b>s.5(1)–(2)</b>: a landlord may not accept an agreed rent "
            "above the prescribed rent, and where he does the tenant pays the prescribed rent. "
            "<b>s.5(3)</b>: where the agreed rent is <i>lower</i>, the tenant continues to pay it "
            "<b>unless the landlord by written notice requires the prescribed rent</b>."
        ),
        recovery_of_excess=(
            "<b>s.5(4) — the tenant’s remedy.</b> Where a landlord has received rent above the "
            "prescribed rent, or above a rent fixed by a Court or on appeal, "
            "<b>the tenant may recover the excess from the landlord</b>."
        ),
        supersedes=(
            "s.6(3): the rent prescribed by the Court supersedes the agreed rent and binds the "
            "landlord, the tenant and the mortgagee. <b>s.7</b>: the Court fixes rent for "
            "<b>furnished</b> accommodation too, having regard to the type, number, quality and "
            "cost of the furniture."
        ),
    ),

    premium=dict(
        cite="s.6(4)",
        text=(
            "As in Edo: it is not lawful for anyone, in consideration of the grant, continuance, "
            "surrender or giving up of a tenancy, to <b>require or receive any premium</b>. Any "
            "such payment is <b>recoverable by the tenant</b> and may <b>be deducted at the time "
            "of payment</b> from rent due to the landlord. s.6(5) preserves the <i>bona fide</i> "
            "contractor exception."
        ),
    ),

    advance_rent=dict(
        cite="s.6(6)",
        text=(
            "<b>Cross River is the strictest jurisdiction we have verified — stricter than "
            "Lagos.</b> s.6(6): a landlord may demand and receive the prescribed rent in advance "
            "for a period <b>not exceeding three months from tenants who are individuals</b>, and "
            "twelve months from tenants other than individuals."
        ),
        contrast=(
            "A landlord may lawfully take a year in advance from a company, but only three months "
            "from a person. Lagos’s cap is six months for a sitting monthly tenant and a year for "
            "a new tenant; Cross River allows an individual a quarter of that."
        ),
    ),

    notice_ladder=[
        ("Tenancy at will or weekly tenancy", "one week", "s.15(1)(a)"),
        ("Monthly tenancy", "one month", "s.15(1)(b)"),
        ("Quarterly tenancy", "a quarter", "s.15(1)(c)"),
        ("Yearly tenancy", "half a year", "s.15(1)(d)"),
    ],
    notice_extras=[
        "<b>s.15 proviso — the arrears trigger.</b> A monthly tenant in arrears of rent for "
        "<b>three months</b> after the commencement of the Law: the tenancy determines and the "
        "Court shall, on the landlord’s application, make an order for possession and arrears. "
        "(Lagos requires six months’ arrears; FCT has no such shortcut.)",
        "<b>s.15(2)</b> — the nature of the tenancy is determined, absent contrary evidence, by "
        "reference to when rent is paid or demanded.",
        "<b>s.16</b> — notice may be given at any time before the current term ends, but it is "
        "<b>ineffective</b> if the gap between the giving of the notice and the determination of "
        "the tenancy is shorter than the period in s.15.",
        "<b>s.17</b> — after a written notice to quit in <b>Form B, C or D</b>, the landlord "
        "serves <b>Form E</b>, signed by the landlord or his agent, of intention to proceed to "
        "recover possession, dated <b>not less than seven days from the date of service</b>.",
        "<b>s.18</b> — proceedings start by writ or plaint in <b>Form F</b> in the Court "
        "<b>of the area where the premises are</b>, and a summons issues in <b>Form G</b>.",
    ],

    repairs=dict(
        cite="s.11",
        text=(
            "A clean, quotable split: <b>the landlord is responsible for structural and external "
            "repairs; the tenant for internal and minor repairs.</b> Compare Lagos, where s.7(3) "
            "puts the tenant under a general duty of tenantable repair subject to fair wear and tear."
        ),
    ),

    improvements=dict(
        cite="s.13",
        text=(
            "A tenant who, with the landlord’s <b>prior consent in writing</b>, executes "
            "improvements is entitled to compensation for their <b>unexhausted value</b> at the "
            "end of the tenancy. “Improvement” is defined to include structural alteration, "
            "extension or addition — including pavements, fences, extra sanitary conveniences and "
            "additional fixtures and fittings — but <b>expressly excludes normal repairs</b>."
        ),
    ),

    grounds_for_possession=[
        ("rent lawfully due is in arrears for <b>three months</b> after it became due", "Schedule 3(a)"),
        ("breach of an express covenant or agreement of the tenancy", "Schedule 3(b)"),
        ("the tenant gave notice to quit and the landlord, in consequence, contracted to sell or let or took steps whereby he would be seriously prejudiced if he could not obtain possession", "Schedule 3(c)"),
        ("the premises are reasonably required <b>for a public purpose</b>", "Schedule 3(d)"),
        ("nuisance or annoyance to adjoining occupiers, use as a brothel, conviction for using or permitting illegal use of the premises, or failure to remove a sub-tenant or lodger", "Schedule 3(e)"),
        ("premises so overcrowded as to be dangerous or injurious to the health of the inmates, where the overcrowding could have been abated by removing a lodger or sub-tenant (not a parent or child of the tenant)", "Schedule 3(f)"),
        ("the premises require substantial repair or reconstruction — the Court may impose a condition for the tenant’s return when the work is finished", "Schedule 3"),
        ("the premises are reasonably required by the landlord for occupation by himself, his wife, any son or daughter over eighteen, or his father or mother", "Schedule 3"),
    ],

    service=dict(
        cite="s.32",
        text=(
            "Service follows the civil-process rules of the Magistrates’ Courts until the "
            "Rules Committee makes its own. Where the defendant cannot be found, his dwelling is "
            "unknown, or admission cannot be obtained, <b>posting a copy on some conspicuous part "
            "of the premises is deemed good service</b>."
        ),
    ),

    rent_book=dict(
        cite="s.34",
        text=(
            "s.34 provides for <b>rent books and receipts</b>, and Schedule 4 includes "
            "<b>Form P — “Form of notice to be printed or inserted in rent books "
            "(Information for tenant)\u201d</b>. Cross River therefore prescribes a document that "
            "carries tenant information inside the rent book itself."
        ),
        gap="<b>The full wording of s.34 has not been read</b> — the section heading and the Form P entry are verified; the duty’s precise wording is not, so it is not quoted.",
    ),

    schedules_omitted=dict(
        note=(
            "<b>An honesty note that matters.</b> The published 2004 revised edition carries an "
            "editorial note that <b>Schedule 1 (Zones) and Schedule 2 (Prescribed rents) have been "
            "omitted and “will be included in subsequent updates.”</b> The zones and the "
            "rent figures are therefore <b>not</b> in the publicly available statute, and we do "
            "not publish them. We can say that seven zones exist and are named, because s.54(2) "
            "says so; we cannot say what rent each zone commands."
        )
    ),

    protections=[
        "<b>s.21</b> — security of tenancy: a quit notice served after the tenant has applied to "
        "the Court is of no effect, and none may be given before the decision.",
        "<b>s.22</b> — restriction on contracting out: the Law voids agreements that purport to "
        "stop a tenant exercising its rights.",
        "<b>s.43</b> — offences and penalties, including for unlawful eviction.",
        "<b>s.52</b> — judgment must be delivered <b>not later than two months</b> from the date "
        "of service of the hearing notices — a statutory deadline most jurisdictions do not have.",
        "<b>s.53</b> — Schedule 2 is subject to <b>periodic review</b>.",
    ],

    sources=[
        "Rent Control and Recovery of Premises Law, Cap. R3, Laws of Cross River State 2004, Vol. 6 — ss.1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 32, 33, 34, 41, 43, 49, 52, 53, 54, 55, 56, 57; Schedules 3, 4, 5",
        "https://crsida.crossriverstate.gov.ng/CRS%20Laws%202004%20Vol%206_120056.pdf",
    ],

    open_questions=[
        "The full text of s.33 (distress for rent) and s.34 (rent book and receipts) has not been captured.",
        "Schedule 1 (Zones) and Schedule 2 (Prescribed rents) are omitted from the published revised edition; the rent figures are not available.",
        "Whether a Cross River Rent Control Court has in fact been established and gazetted for each zone.",
    ],
)

# ---------------------------------------------------------------------------
# KWARA — Tier A. Read from the State's own register of laws.
# Carries a genuine internal contradiction in the statute — recorded, not hidden.
# ---------------------------------------------------------------------------
KWARA = dict(
    slug="kwara",
    name="Kwara",
    place="Kwara State (Ilorin)",
    full="Kwara State",
    tier="A",
    tier_note="Read from the Kwara State register of laws. One internal contradiction recorded in kwara_conflict.",

    statutes=[
        dict(
            title="Rent Control and Recovery of Residential Premises Law 1995",
            citation="Chapter R2, Laws of Kwara State — No. 10 of 1995, as amended by No. 3 of 1998 and No. 4 of 2006",
            commenced="21 September 1995",
            source="https://kwaralaws.ng/product/r2rent-control-and-recovery-of-residential-premises-law/",
        ),
        dict(
            title="Landlord and Tenant Law",
            citation="Chapter L4, Laws of Kwara State",
            note="Governs the wider landlord-and-tenant relationship; see `tenant_at_will`.",
            source="https://kwaralaws.ng/product/chapter-l4-landlord-and-tenant-law/",
        ),
    ],
    repealed=[
        "The Recovery of Premises Law, to the extent that it relates to accommodation in residential premises (s.37(1))",
        "The Rent Control and Recovery of Residential Premises Law No. 2 of 1977 (s.37(2))",
        "The Rent Control and Recovery of Residential Premises (Amendment) Law No. 17 of 1984 (s.37(3))",
    ],

    forum=dict(
        name="the Rent Tribunals of Kwara State, by zone",
        text=(
            "s.3 establishes Rent Tribunals. Composition (s.3(1)): a chairman who has been in "
            "practice as a legal practitioner in Nigeria for <b>not less than five years</b>, plus "
            "<b>two other persons of probity appointed to represent the interests of the landlords "
            "and the tenants</b>. That express landlord/tenant balance is Kwara’s own touch — "
            "Edo’s two additional members are simply “persons of probity”."
        ),
        terms=(
            "s.3(2): a member serves <b>three years</b>, is eligible for re-appointment, and may "
            "<b>not serve more than two terms</b>. s.3(5): the chairman plus one other member is a "
            "quorum. s.3(7): the tribunal may sit with assessors drawn from a maintained list of "
            "persons experienced in <b>estate and property management, building, or as health "
            "inspectors</b>."
        ),
        zones=(
            "<b>s.3(10) divides the State into two zones:</b> the <b>Ilorin Zone</b> (Ilorin West, "
            "Ilorin East, Asa, Moro, Kaiama, Baruten and Offa Local Government Areas) and the "
            "<b>Omu-Aran Zone</b> (Ekiti, Irepodun, Ifelodun, Edu and Oyun Local Government "
            "Areas). s.3(11): a tribunal sits for its own zone, but may sit for another zone "
            "<b>where the Attorney-General of the State so directs</b>."
        ),
        procedure=(
            "s.6(1): proceedings may be commenced before a court of law of the State <b>or</b> a "
            "tribunal. s.6(3): a tribunal or court is bound by the practice and procedure in civil "
            "matters in the <b>district court</b>. s.9: proceedings are in public, are deemed "
            "judicial proceedings, and members are judicial officers, with power to examine on "
            "oath, summon witnesses and compel production of documents <b>including any document "
            "of title</b>."
        ),
    ),

    standard_rent=dict(
        cite="s.4, s.5",
        text=(
            "s.4(1)–(2): a landlord may not accept an agreed rent above the standard rent, and "
            "where he does the tenant pays the standard rent. s.5(3): the standard rent fixed by "
            "the tribunal or court <b>supersedes</b> the agreed rent and binds the landlord, the "
            "tenant and the <b>mortgagee</b>."
        ),
        anomaly=dict(
            summary=(
                "<b>A provision that does not read as intended — reported as written.</b>"
            ),
            detail=(
                "s.4(3) provides that <i>where the agreed rent is lower than the standard rent, the "
                "tenant shall pay the standard rent</i>. Read literally that raises a tenant’s "
                "bargained rent to the standard rent. Edo s.5(3) and Cross River s.5(3) both do "
                "the opposite — the tenant continues to pay the lower agreed rent. Kwara’s "
                "text looks like a transcription error in the revised edition, but it is what the "
                "State’s own register publishes, so we report it as written and flag it rather "
                "than quietly substituting the Edo formulation."
            ),
        ),
    ),

    premium=dict(
        cite="s.5(4), s.35(5)",
        text=(
            "s.5(4): it is unlawful for anyone, in consideration of the grant, continuance, "
            "surrender or giving up of a tenancy, to <b>require or receive any loan or premium</b>. "
            "Such a payment is recoverable by the tenant and may be deducted from rent."
        ),
        penalty=(
            "<b>s.35(5) is unusually punitive:</b> a person who receives a loan or premium "
            "contravening the Law — expressly including in relation to advance payment of rent — "
            "is liable on summary conviction to a fine of <b>twice the amount received</b>."
        ),
    ),

    advance_rent=dict(
        cite="s.4(6) and s.35(6) — <b>these two provisions disagree</b>",
        text=(
            "Kwara has a cap, but the statute states it twice with different numbers, and the "
            "page must say so."
        ),
        rows=[
            ("s.4(6) — the prohibition", "unlawful to demand or receive more than <b>one year</b> from individual tenants and <b>two years</b> from commercial or institutional tenants"),
            ("s.35(6) — the offence", "a landlord who demands or receives more than <b>three months</b> from an individual tenant, or <b>twelve months</b> from a commercial or institutional tenant, is guilty of an offence"),
            ("s.35(6) — the penalty", "a fine of <b>an amount equivalent to the excess</b> of rent received"),
        ],
        how_to_read=(
            "s.35(6) carries the later amendment marker (No. 4 of 2006), so it is likely the "
            "intended, stricter figure, and <b>three months for an individual tenant</b> is the "
            "number a Kwara tenant should work with. But the Law on its face contains both, and "
            "until the State harmonises them we publish both rather than pick one."
        ),
        grandfather=(
            "s.4(7): rent paid in advance <b>before</b> the Law commenced, in excess of the cap, "
            "is <b>not recoverable</b> by the tenant."
        ),
    ),

    tenant_at_will=dict(
        cite="Landlord and Tenant Law, Chapter L4",
        text=(
            "<b>The most striking Kwara-specific rule we found.</b> Under Chapter L4, a "
            "<b>tenant at will is not entitled to any period of notice to quit</b>, and owes none in "
            "return. A tenancy at will terminates on the death of either party, on the landlord’s "
            "demand for possession, on the tenant’s notice of intention to quit, or on any act of "
            "ownership by the landlord inconsistent with the tenancy."
        ),
        contrast=(
            "Everywhere else we have verified — Lagos s.13(1)(a), FCT s.8, Cross River s.15(1)(a), "
            "Kwara’s own s.17(1)(a) — a tenant at will gets <b>a week</b>. Under Chapter L4 the "
            "answer is <b>none</b>. The two provisions sit in different statutes, and how a Kwara "
            "court reconciles them is not something we can state from the sources we hold."
        ),
        arrears=(
            "Chapter L4 also provides that <b>rent may be demanded or recovered at any time after "
            "it is in arrear, but not until then</b> — Kwara, like Rivers, starts from rent in "
            "arrears rather than rent in advance."
        ),
    ),

    notice_ladder=[
        ("Tenancy at will or weekly tenancy", "one week", "s.17(1)(a)"),
        ("Monthly tenancy", "one month", "s.17(1)(b)"),
        ("Quarterly tenancy", "a quarter", "s.17(1)(c)"),
        ("Yearly tenancy", "half a year", "s.17(1)(d)"),
    ],
    notice_extras=[
        "<b>s.17 proviso — the shortest arrears trigger we verified.</b> A monthly tenant in "
        "arrears for <b>three months</b> after the commencement of the Law: the tenancy determines "
        "and the tribunal or court shall, on the landlord’s application, make an order for "
        "possession and arrears. (Lagos requires six months; the FCT has no shortcut.)",
        "<b>s.17(1) has no half-yearly tier</b> — Lagos s.13(1)(d) expressly provides three months "
        "for a half-yearly tenant; Kwara does not.",
        "<b>s.17(2)</b> — the nature of the tenancy is determined, absent contrary evidence, by "
        "reference to when rent is paid or demanded.",
        "<b>s.18</b> — notice may be given at any time before the current term ends, but is "
        "ineffective if the gap is shorter than the period in s.17.",
        "<b>s.16</b> — after determination, the landlord serves <b>Form E</b> of intention to "
        "proceed to recover possession, dated not less than seven days <b>from the date of "
        "service</b>. <b>s.19</b> — proceedings by writ or plaint in <b>Form F</b>, in the "
        "tribunal or court <b>for the zone in which the premises are</b>; summons in <b>Form G</b>.",
    ],

    suitable_alternative_accommodation=dict(
        cite="s.26",
        text=(
            "<b>Kwara is the only jurisdiction we verified where the Court must be satisfied "
            "about alternative accommodation.</b> s.26(1): no order for possession or ejectment "
            "may be made unless the tribunal or court considers it reasonable <b>and</b> either it "
            "has power under the <b>Second Schedule</b>, or it is satisfied that "
            "<b>suitable alternative accommodation is available for the tenant</b>."
        ),
        definition=(
            "s.26(2): accommodation is “suitable” where it is reasonably suitable to "
            "the needs of the tenant and his family <b>as regards proximity to place of work</b>, "
            "<b>to the means of the tenant</b>, and as to extent and character."
        ),
        contrast="Edo’s tribunal may dispense with proof of alternative accommodation where it considers it reasonable; Kwara may not.",
    ),

    distress=dict(
        cite="s.8",
        text=(
            "<b>Distraint is tightly controlled in Kwara.</b> s.8(1): a landlord shall not "
            "exercise the power of distress for rent <b>except in execution of the judgment of a "
            "court</b> and in accordance with the <b>Sheriffs and Civil Process Law (Cap. S5)</b> — "
            "but the tribunal or court may, if satisfied the tenant has defaulted on the standard "
            "rent it fixed, order that the tenant’s property be distrained until payment. "
            "s.8(2): ss.25–28 of the Sheriffs and Civil Process Law apply as they do to "
            "attachment in execution."
        ),
        plain="A landlord cannot simply seize a Kwara tenant’s belongings for rent. There must be a judgment, or a specific tribunal order.",
    ),

    rent_book=dict(
        cite="s.32",
        text=(
            "<b>Kwara is one of the few states with a rent book duty.</b> s.32(1): as from "
            "commencement, all landlords of premises <b>in the high density areas</b> to which the "
            "Law applies shall issue <b>prescribed rent books in addition to receipts</b>. "
            "s.32(2): <b>the rent book is kept in the tenant’s custody</b> and the landlord makes "
            "the entries in it when rent is paid."
        ),
        penalty=(
            "s.32(3): a landlord who fails to issue the prescribed rent book is guilty of an "
            "offence and liable on summary conviction to a fine of <b>₦2,000</b> or "
            "<b>imprisonment for up to three months</b>, or both."
        ),
        note="The duty is confined to high density areas — a narrower reach than a general receipt rule.",
    ),

    security_of_tenancy=dict(
        cite="s.15",
        text=(
            "s.15(1): once a tenant has applied to the tribunal or court, any quit notice served "
            "afterwards is of no effect and none may be given before the decision. s.15(2): the "
            "tribunal or court may declare a quit notice <b>invalid and of no effect</b> where it "
            "was not issued <b>in good faith</b>, and its endorsement on the notice is sufficient "
            "evidence of that before any court."
        ),
    ),

    contracting_out=dict(
        cite="s.13, s.14",
        text=(
            "<b>s.13</b>: any agreement is <b>void</b> in so far as it purports to stop a tenant "
            "making an application or exercising a right under the Law, or provides for "
            "termination, surrender, a penalty or a disability if he does. <b>s.14</b>: every "
            "court in the State, civil or criminal, must conform to the Law and "
            "<b>shall not recognise or enforce any arrangement intended or calculated to evade it</b>."
        ),
    ),

    grounds_and_forms=dict(
        improvements="s.23: a tenant who made improvements with the landlord’s previous written consent is entitled to compensation on quitting.",
        subtenants="s.12: sub-tenants are deemed tenants of the landlord where sub-letting is not expressly prohibited in writing. s.20: a sub-tenant served with a summons who fails to notify his immediate landlord is liable to forfeit <b>up to three years’ rent</b>.",
        transfer_of_liability="s.7: shifting a burden from the landlord to the tenant is treated as an <b>increase in rent</b>, whether or not the periodic sum changes.",
        warrant="s.29: a warrant runs three months. s.30: no entry on a warrant on a Sunday or public holiday, or outside 6am–6pm.",
        appeals="s.34: either party may appeal to the High Court of the State.",
    ),

    compulsory_acquisition=dict(
        cite="s.36",
        text=(
            "Where the tribunal or court finds that a landlord has violated the Law on "
            "<b>two occasions</b>, the Governor shall, on the tribunal’s or court’s "
            "recommendation, <b>acquire the landlord’s interest in the premises</b>, with "
            "compensation under the Land Use Act 1978, the Land Tenure Law or other written law."
        ),
    ),

    penalties=dict(
        cite="s.35",
        rows=[
            ("Demolishing, altering or modifying a building to eject a tenant, without the approval of the tribunal or court", "₦5,000 or 6 months", "s.35(1)"),
            ("Attempting to or forcibly ejecting a tenant; harassing or molesting a tenant to eject him; harassing a landlord; doing anything calculated to stultify the Law; failing to comply with an order", "₦5,000 or 6 months", "s.35(2)"),
            ("Contempt of a tribunal or court", "₦5,000 or 6 months", "s.35(4)"),
            ("Receiving a loan or premium in contravention of the Law, including on advance rent", "<b>a fine of twice the amount received</b>", "s.35(5)"),
            ("Demanding or receiving advance rent above the cap", "<b>a fine equivalent to the excess</b>", "s.35(6)"),
            ("Obstructing an officer serving process or executing a warrant", "₦5,000 or 12 months", "s.35(7)"),
            ("Retaking possession after being put out under a warrant", "₦5,000 or 12 months", "s.35(8)"),
        ],
        fraud="s.35(9)–(10): obtaining an order for possession by fraud, misrepresentation or concealment of a material fact is unlawful, and the tribunal or court shall order the landlord to pay <b>reasonable compensation</b> to the tenant.",
    ),

    kwara_conflict=dict(
        summary="The Law states the advance-rent cap twice with different numbers.",
        detail="s.4(6) prohibits more than one year (individuals) / two years (commercial). s.35(6), carrying the 2006 amendment marker, makes it an offence to take more than three months (individuals) / twelve months (commercial). Both are published; the page shows both.",
    ),

    sources=[
        "Rent Control and Recovery of Residential Premises Law 1995, Chapter R2, Laws of Kwara State — ss.2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17, 18, 19, 20, 23, 26, 29, 30, 31, 32, 34, 35, 36, 37; First, Second and Third Schedules",
        "https://kwaralaws.ng/product/r2rent-control-and-recovery-of-residential-premises-law/",
        "Landlord and Tenant Law, Chapter L4, Laws of Kwara State — tenancy at will, rent in arrears: https://kwaralaws.ng/product/chapter-l4-landlord-and-tenant-law/",
    ],

    open_questions=[
        "s.4(3) appears to be a drafting or transcription error — needs checking against the original 1995 gazette.",
        "s.4(6) vs s.35(6) advance-rent figures — the Law contradicts itself; needs the 2006 amendment text to resolve.",
        "How a Kwara court reconciles s.17(1)(a) (a week’s notice for a tenant at will under R2) with Chapter L4 (no notice at all).",
        "Which areas are designated “high density” for the s.32 rent book duty.",
    ],
)


# ---------------------------------------------------------------------------
# RIVERS — Tier B. Two named statutes with chapter citations, from a
# practitioner and an academic source. No primary text read yet, so the
# graduated ladder is given only where both sources agree on it.
# ---------------------------------------------------------------------------
RIVERS = dict(
    slug="rivers",
    name="Rivers",
    place="Rivers State (Port Harcourt)",
    full="Rivers State",
    tier="B",
    tier_note="Named statutes with chapter citations from a practitioner and an academic source. Primary text not yet read.",

    statutes=[
        dict(
            title="Recovery of Premises Law",
            citation="Cap. 109, Laws of Rivers State of Nigeria, 1999",
            commenced="1999",
            note="Governsquit notices and the procedure for recovering possession.",
            source="https://barristerng.com/expiration-of-rent-does-not-determine-a-tenancy-relationship-c-s-onyimah-esq/",
        ),
        dict(
            title="Landlord and Tenant Law",
            citation="Cap. 75, Laws of Rivers State",
            note="Governs the wider landlord-and-tenant relationship, including when rent falls due.",
            source="https://barristerng.com/expiration-of-rent-does-not-determine-a-tenancy-relationship-c-s-onyimah-esq/",
        ),
    ],

    forum=dict(
        name="the Magistrates’ Courts and the High Court of Rivers State",
        text=(
            "Recovery proceedings run through the courts of Rivers State — a notice to quit in "
            "practice issues in the name of the Magistrate Court of Rivers State, in the "
            "magisterial district where the premises sit (for example, the Port Harcourt "
            "Magisterial District). <b>We have not read the primary text establishing a Rivers "
            "Rent Tribunal</b>, and we do not assert that one exists."
        ),
    ),

    anniversary_rule=dict(
        cite="s.7",
        text=(
            "<b>This is the Rivers rule that most affects real cases, and it is the opposite of "
            "Lagos.</b> s.7: a notice to quit must terminate on the <b>eve of the anniversary</b> "
            "of the current term. The notice must end on the day before the next term would "
            "renew, and it must cover the full statutory length between the date of service and "
            "that eve."
        ),
        contrast=(
            "Lagos s.13(4) is the exception: three- and six-month notices there <i>need not</i> "
            "end on the anniversary, and may end on or after the term expires. In Rivers — "
            "and, on the practitioner account, <b>in most Nigerian states except Lagos</b> — "
            "the eve-of-anniversary rule applies. Get the date wrong and the notice is defective."
        ),
        worked=(
            "A yearly tenancy that began on 1 January 2025 runs to 31 December 2025. A valid "
            "six-month quit notice must expire on that 31 December — the eve of the "
            "anniversary — not a week either side of it."
        ),
    ),

    notice_ladder=[
        ("Yearly tenant", "six months", "s.6(1)(d)"),
    ],
    notice_ladder_note=(
        "<b>Only the yearly tier is published.</b> s.6(1)(d) giving a yearly tenant six months "
        "is stated by a Rivers practitioner and is consistent with the national pattern. We have "
        "not read the primary text, so we do not publish the weekly, monthly or quarterly tiers "
        "rather than assume them."
    ),
    notice_extras=[
        "<b>s.6(2)</b> — the nature of a tenancy is determined, absent contrary evidence, by "
        "reference to the <b>mode of payment and demand for rent</b>, not by what the agreement "
        "calls it.",
        "<b>Expiry of rent does not end the tenancy.</b> A tenancy is determined by a valid "
        "notice (or effluxion of a fixed term) — not by the rent running out. A landlord who "
        "treats the end of the paid period as the end of the tenancy and moves to eject is "
        "acting unlawfully.",
        "<b>After the quit notice expires</b>, the landlord serves a further written notice of "
        "the owner’s intention to apply to court to recover possession, of not less than "
        "<b>seven days</b>. That notice cannot be issued before the quit notice expires.",
        "<b>Seven clear days:</b> the day of service is excluded and the day of expiry included.",
    ],

    rent_in_arrears=dict(
        cite="Landlord and Tenant Law, Cap. 75, s.75(1)",
        text=(
            "<b>Rivers reverses the assumption most Nigerian tenants make.</b> s.75(1) of the "
            "Landlord and Tenant Law: rent is payable <b>in arrears</b> — at the end of the "
            "period — unless the parties agree otherwise."
        ),
        contrast=(
            "The national practice is rent in advance, and Lagos s.4 regulates how much advance "
            "may be taken. Kwara’s Chapter L4 is the same as Rivers: rent is recoverable "
            "only once it is in arrear. In Rivers, unless your agreement says otherwise, paying "
            "up front is a concession you are making, not a duty you owe."
        ),
    ),

    advance_rent=dict(
        cite="no cap verified",
        text=(
            "We have found <b>no Rivers equivalent of the Lagos s.4 advance-rent cap</b>. On the "
            "statutory starting point above, rent in Rivers is not even due until it is in "
            "arrear. Whatever advance is agreed should be written into the tenancy agreement "
            "before money moves — and note that a written advance term displaces the "
            "s.75(1) default."
        ),
    ),

    receipts=dict(
        cite="not verified",
        text=(
            "We have not verified a Rivers statutory duty to issue a rent receipt with prescribed "
            "contents, so none is claimed. The ordinary position still applies: a receipt is the "
            "evidence that rent was paid, and whoever asserts payment bears the burden of "
            "proving it."
        ),
    ),

    caution_fee=dict(
        cite="not verified",
        text=(
            "We have not verified a Rivers provision on premiums, caution fees or deposits of the "
            "kind found in Edo s.6(4), Cross River s.6(4) and Kwara s.5(4). Nothing here should "
            "be read as saying Rivers bans or permits them — we simply have not read the "
            "statute. Record the deposit and its refund terms in writing."
        ),
    ),

    increase_challenge=dict(
        cite="not verified",
        text=(
            "We have not verified a Rivers equivalent of the Lagos s.37 application to have an "
            "increase declared unreasonable."
        ),
        false_claim="No percentage cap on rent increases exists in Rivers or anywhere in Nigeria.",
    ),

    protections=[
        "A landlord may not resort to self-help — no lock-outs, no removal of goods, no "
        "disconnection. Unlawful eviction sounds in damages.",
        "A defect in the issue, content or service of a notice vitiates the whole proceeding.",
        "The date of <b>service</b> is the material date, not the date written on the notice.",
    ],

    sources=[
        "C.S. Onyimah, “Expiration of Rent does not Determine a Tenancy Relationship”, BarristerNG — Rivers State Recovery of Premises Law Cap. 109, ss.6(1)(d), 6(2), 7: https://barristerng.com/expiration-of-rent-does-not-determine-a-tenancy-relationship-c-s-onyimah-esq/",
        "Dr Chris Wigwe, “Recovery of Premises in Nigeria: An Assessment of the Relationship of Landlord and Tenant Law”, Journal of Commercial and Contemporary Law — section-by-section mapping of the Rivers Law (ss.6(2), 7, 8, 17, 18, 20–22) against the Abuja Act and the Lagos Rent Control Law: https://www.researchgate.net/profile/Dr-Christian-Wigwe/publication/274377789",
        "https://lawgivernigeria.blogspot.com/2016/07/recovery-of-premises-in-nigeria-drafts.html — Rivers Magistrate Court forms and procedure",
    ],

    open_questions=[
        "The graduated notice periods for weekly, monthly and quarterly tenancies under Cap. 109 — not published pending the primary text.",
        "Whether the proviso to s.6(1)(d) creates an arrears shortcut, and at what threshold.",
        "Whether Rivers has a Rent Tribunal in operation, and if so its composition and jurisdiction.",
        "The full wording of Landlord and Tenant Law Cap. 75 s.75(1).",
        "Whether Rivers has a rent-control or standard-rent regime in addition to the recovery law.",
    ],
)



# ---------------------------------------------------------------------------
# ANAMBRA — Tier B. Confirmed by a Court of Appeal judgment, which also
# corrects an error in this project's own earlier research.
# ---------------------------------------------------------------------------
ANAMBRA = dict(
    slug="anambra",
    name="Anambra",
    place="Anambra State (Onitsha / Awka)",
    full="Anambra State",
    tier="B",
    tier_note="Statute confirmed by a Court of Appeal judgment and an academic source. Section contents partly quoted by the Court, not yet read in full.",

    correction=dict(
        summary="<b>A correction to our own earlier research.</b>",
        detail=(
            "We previously recorded Anambra as having no tenancy legislation in force. "
            "<b>That was wrong.</b> The Court of Appeal in <i>Amah v. Ozouli</i> "
            "[2010] NGCA 6 (CA/E/298/2006) identifies the "
            "<b>Landlord and Tenant Law, Cap. 76, Laws of Anambra State</b> as the law "
            "governing recovery of possession, and quotes from it. What is pending in "
            "Anambra is a <i>new</i> Rent and Tenancy Law — not the first one."
        ),
    ),

    statutes=[
        dict(
            title="Landlord and Tenant Law",
            citation="Cap. 76, Laws of Anambra State",
            note=(
                "Identified by the Court of Appeal as the law governing recovery of "
                "possession of premises in Anambra State, and applied in the state from "
                "which Enugu was carved in 1991."
            ),
            source="https://nigerialii.org/akn/ng/judgment/ngca/2010/6/eng@2010-05-20",
        ),
        dict(
            title="Rent and Tenancy Law (proposed)",
            citation="—",
            status="A BILL, NOT LAW. Do not describe its contents as current rules.",
            note=(
                "A new Anambra Rent and Tenancy Law has been proposed, following protests "
                "over rents and agents' fees. It must not be confused with the Landlord and "
                "Tenant Law Cap. 76, which is in force."
            ),
            source="",
        ),
    ],

    forum=dict(
        name="the Magistrates’ Courts and the High Court of Anambra State",
        text=(
            "<b>s.144 of the Landlord and Tenant Law</b> follows the Abuja pattern: it "
            "discourages commencing an action in the High Court where the matter is one the "
            "Magistrate Court can entertain."
        ),
        important=(
            "Wigwe notes the constitutional limit on that: a provision purporting wholly to "
            "<b>exclude</b> the High Court’s jurisdiction would be inconsistent with "
            "<b>s.272 of the 1999 Constitution (as amended)</b>. So the High Court retains "
            "jurisdiction in Anambra; s.144 channels the ordinary case downward, it does not "
            "shut the High Court out."
        ),
    ),

    alternative_accommodation=dict(
        cite="s.173 (with s.172 and s.174)",
        text=(
            "<b>Anambra is the second jurisdiction we have found, after Kwara, where the court "
            "must be satisfied about alternative accommodation.</b> On the Court of Appeal’s "
            "quotation of the law: no order for recovery of possession or ejectment may be made "
            "unless the court is satisfied that <b>suitable alternative accommodation is "
            "available for the tenant</b>."
        ),
        exception=(
            "<b>s.173(2)</b>: where the court considers it reasonable to do so, it may make the "
            "order <b>without proof of suitable alternative accommodation</b> if one or more of "
            "the circumstances set out in <b>s.174</b> are proved to its satisfaction."
        ),
        contrast=(
            "This is the same architecture as Kwara s.26 and its Second Schedule, and the "
            "Eastern/Northern cousin of the Cross River Schedule 3 list. Edo, by contrast, lets "
            "the tribunal dispense with proof of alternative accommodation wherever it considers "
            "it reasonable. <b>The full text of s.174 has not been read, so the individual "
            "circumstances are not listed here.</b>"
        ),
    ),

    notice_ladder=[],
    notice_extras=[
        "<b>Expiry must fall on the eve of the anniversary.</b> A quit notice must terminate at "
        "midnight on the last day of the current term — for a yearly tenancy running "
        "1 January to 31 December, a six-month notice must expire on that 31 December, not "
        "before and not after. This is the general Nigerian rule (see "
        "<i>African Petroleum Ltd v. Owodunni</i>) and Lagos s.13(4) is the statutory exception.",
        "<b>The statutory periods are minimums.</b> A notice that is <i>longer</i> than the "
        "statutory minimum is valid; one that falls short by even a day is ineffective.",
        "<b>What the parties agree governs first.</b> Where the tenancy agreement fixes the "
        "notice, that period binds — even a week in a yearly tenancy. The statutory ladder "
        "applies only where the agreement is silent.",
        "<b>A month means a calendar month.</b> Under s.18 of the Interpretation Act a month is "
        "a calendar month reckoned by the Gregorian calendar.",
        "<b>After the quit notice expires</b>, the landlord serves a further written notice of "
        "the owner’s intention to apply to court, of not less than <b>seven clear days</b> "
        "— the day of service excluded, the day of expiry included. It cannot be issued "
        "before the quit notice expires.",
        "<b>Unlawful eviction sounds in damages</b> — see <i>Ihenacho v. Uzochukwu</i> "
        "(1997) 1 SCNJ 117.",
    ],

    advance_rent=dict(
        cite="not verified",
        text=(
            "We have not read Cap. 76 and have found <b>no Anambra advance-rent cap</b> of the "
            "Lagos s.4 kind. Nothing here should be read as saying one does or does not exist. "
            "Record whatever advance is agreed in the tenancy agreement before money moves."
        ),
        warning=(
            "The <b>proposed</b> Rent and Tenancy Law is reported to address advance rent and "
            "agents’ fees. It is not law and its contents are not stated here."
        ),
    ),

    receipts=dict(
        cite="not verified",
        text=(
            "No Anambra statutory receipt duty has been verified, so none is claimed. The "
            "ordinary evidential position applies: the receipt is the proof that rent was paid."
        ),
    ),

    caution_fee=dict(
        cite="not verified",
        text=(
            "We have not read Cap. 76 on premiums, caution fees or deposits, so no Anambra rule "
            "is stated. Note that neighbouring Edo (s.6(4)), Cross River (s.6(4)) and Kwara "
            "(s.5(4)) all ban premiums outright — but those are their statutes, not "
            "Anambra’s, and must not be attributed here."
        ),
    ),

    increase_challenge=dict(
        cite="not verified",
        text="We have not verified an Anambra equivalent of the Lagos s.37 unreasonable-increase application.",
        false_claim="No percentage cap on rent increases exists in Anambra or anywhere in Nigeria.",
    ),

    related=dict(
        enugu=(
            "<b>Enugu inherited this law.</b> The Court of Appeal in <i>Amah v. Ozouli</i> held "
            "that the law applicable in Enugu State is the <b>Landlord and Tenant Law, "
            "Cap. 101, Revised Laws of Enugu State, which came into operation on "
            "27 August 1991</b> — resolving the earlier conflict in our notes between "
            "“Cap. 101 of 2004” and other dates. The 1991 date is when it commenced; "
            "2004 is the revised edition."
        ),
    ),

    protections=[
        "A landlord may not resort to self-help. Unlawful eviction is actionable in damages.",
        "The High Court retains jurisdiction in Anambra notwithstanding s.144 — a "
        "provision wholly excluding it would offend s.272 of the 1999 Constitution.",
        "Improvements made with the landlord’s written consent may found a counterclaim "
        "for their unexhausted value.",
    ],

    sources=[
        "Court of Appeal, Amah v. Ozouli (CA/E/298/2006) [2010] NGCA 6 — identifies the Landlord and Tenant Law, Cap. 76, Laws of Anambra State and quotes ss.172–174: https://nigerialii.org/akn/ng/judgment/ngca/2010/6/eng@2010-05-20",
        "Dr Chris Wigwe, “Recovery of Premises in Nigeria”, Journal of Commercial and Contemporary Law — s.144 Landlord and Tenant Law (Anambra) on jurisdiction, and the constitutional limit under s.272: https://www.researchgate.net/profile/Dr-Christian-Wigwe/publication/274377789",
        "African Petroleum Ltd v. Owodunni (eve-of-anniversary rule); Ihenacho v. Uzochukwu (1997) 1 SCNJ 117 (unlawful eviction)",
    ],

    open_questions=[
        "The full text of Cap. 76 — not read. Section contents are known only from the Court of Appeal’s quotation of ss.172–174.",
        "The individual circumstances listed in s.174 (possession without proof of alternative accommodation).",
        "Whether Anambra has a separate rent-control or recovery-of-premises statute alongside the Landlord and Tenant Law.",
        "Whether the proposed Rent and Tenancy Law has been passed — treat as pending until confirmed.",
    ],
)

# ---------------------------------------------------------------------------
# KANO — Tier D for rent control (a verified negative, twice) with a
# reasoned but unconfirmed inheritance of the Northern Nigeria recovery law.
# ---------------------------------------------------------------------------
KANO = dict(
    slug="kano",
    name="Kano",
    place="Kano State",
    full="Kano State",
    tier="D",
    tier_note="Verified negative on rent control — two search passes found no Kano statute. A recovery law is inherited from Northern Nigeria by constitutional succession, but that is not confirmed for Kano.",

    verified_negative=dict(
        summary="<b>We looked properly, twice, and found nothing. That is the finding.</b>",
        detail=(
            "Two separate research passes for a Kano rent-control or tenancy statute returned "
            "<b>no Nigerian authority at all</b> — the results were Kenyan, Indian and "
            "United States landlord-and-tenant law. On the present state of published sources "
            "there is <b>no Kano rent-control statute we can cite</b>, which means there is no "
            "Kano standard-rent regime, no Kano rent tribunal we can identify, and no Kano "
            "advance-rent cap."
        ),
        why_it_matters=(
            "That absence is itself the useful information. A Kano tenant has no statutory "
            "figure to point to and no tribunal to apply to about the rent itself — so "
            "everything turns on the tenancy agreement. It also means any page or agent "
            "quoting a “Kano rent control law” is inventing it."
        ),
    ),

    inheritance=dict(
        title="What probably governs recovery of possession instead",
        text=(
            "Kano was created out of the former <b>Northern Region</b>. The peer-reviewed "
            "account of how Nigerian tenancy law travelled is that the regions each reproduced "
            "the original Recovery of Premises Ordinance, and that on the creation of twelve "
            "states in 1968 <b>each new state inherited all the existing laws of the region it "
            "was carved from</b> — later states inheriting in turn, mutatis mutandis, under "
            "the States Creation and Transitional Provisions Act."
        ),
        statute=(
            "The Northern Region’s recovery law is cited as the "
            "<b>Recovery of Premises Law, Laws of Northern Nigeria 1963</b> — given as "
            "<b>Cap. 113, Vol. 3</b> in one source and as <b>Cap. 115</b> in another. "
            "<b>Those citations conflict and we have not resolved them.</b>"
        ),
        caution=(
            "<b>This is inference, not confirmation.</b> It rests on the constitutional "
            "framework for the succession of regional laws, not on a Kano statute or a Kano "
            "judgment we have read. We publish it as the most likely starting point and say "
            "plainly that it is unconfirmed. Do not rely on it without local advice."
        ),
    ),

    notice_ladder=[],
    notice_extras=[
        "<b>Expiry must fall on the eve of the anniversary</b> — midnight on the last day "
        "of the current term. Lagos s.13(4) is the statutory exception to this general rule.",
        "<b>The statutory periods are minimums;</b> longer is valid, shorter by a day is not.",
        "<b>The agreement governs first.</b> Where it fixes the notice, that period binds; the "
        "statutory ladder applies only where it is silent.",
        "<b>After the quit notice expires</b>, a further written notice of the owner’s "
        "intention to apply to court, of not less than <b>seven clear days</b>, is required — "
        "and it cannot be issued before the quit notice expires.",
        "<b>A month means a calendar month</b> (Interpretation Act s.18).",
        "<b>Unlawful eviction is actionable in damages</b> — <i>Ihenacho v. Uzochukwu</i> "
        "(1997) 1 SCNJ 117.",
    ],

    advance_rent=dict(
        cite="no cap found",
        text=(
            "<b>No Kano advance-rent cap has been found, and no rent-control statute to put one "
            "in.</b> On the present state of the sources there is no statutory limit on what a "
            "Kano landlord may ask for in advance, and no penalty for asking. Whatever is "
            "agreed must therefore go into the tenancy agreement before money moves — "
            "that agreement is the only protection available."
        ),
    ),

    receipts=dict(
        cite="no statutory duty found",
        text=(
            "We have found no Kano statutory duty to issue a rent receipt with prescribed "
            "contents. Because there is also no rent-control regime to give a tenant a "
            "paper trail remedy, <b>the receipt matters more in Kano, not less</b>: with no "
            "statutory rent record and no tribunal, a tenant’s evidence that rent was paid "
            "is the receipt itself. Insist on one for every payment."
        ),
    ),

    caution_fee=dict(
        cite="no provision found",
        text=(
            "No Kano provision on premiums, caution fees or deposits has been found — "
            "so there is no statutory ban of the kind Edo, Cross River and Kwara have, and no "
            "statutory protection either. The deposit is purely a matter of contract, which is "
            "exactly why the amount, the purpose and the refund terms must be written down and "
            "receipted separately from rent."
        ),
    ),

    increase_challenge=dict(
        cite="no mechanism found",
        text=(
            "With no rent-control statute there is no Kano equivalent of the Lagos s.37 "
            "application to have an increase declared unreasonable, and no tribunal to apply "
            "to. Rent increases are governed entirely by the tenancy agreement."
        ),
        false_claim="No percentage cap on rent increases exists in Kano or anywhere in Nigeria.",
    ),

    protections=[
        "A landlord may not resort to self-help; unlawful eviction is actionable in damages.",
        "The High Court has jurisdiction to entertain recovery proceedings in every state, "
        "whatever the lower-court position.",
        "Improvements made with the landlord’s written consent may found a counterclaim for "
        "their unexhausted value.",
    ],

    sources=[
        "No Kano statute located — two independent research passes returned only non-Nigerian authority.",
        "Dr Chris Wigwe, “Recovery of Premises in Nigeria”, Journal of Commercial and Contemporary Law — regional succession of the Recovery of Premises Ordinance; Recovery of Premises Law, Laws of Northern Nigeria 1963 (Cap. 113 Vol. 3): https://www.researchgate.net/profile/Dr-Christian-Wigwe/publication/274377789",
        "https://lawgivernigeria.blogspot.com/2016/07/recovery-of-premises-in-nigeria-drafts.html — cites the same Northern law as Cap. 115 (conflict noted).",
        "Ihenacho v. Uzochukwu (1997) 1 SCNJ 117 (unlawful eviction).",
    ],

    open_questions=[
        "Whether Kano has enacted or re-enacted its own recovery-of-premises or rent-control law — not found.",
        "The correct chapter for the Northern Nigeria Recovery of Premises Law 1963 — Cap. 113 Vol. 3 or Cap. 115.",
        "Whether any Kano rent tribunal has ever been established.",
        "Whether Kano’s Sharia/Customary Court structure affects recovery proceedings — not researched.",
    ],
)


# ---------------------------------------------------------------------------
# Registry. A state appears here only if it reaches tier A-D.
# ---------------------------------------------------------------------------
STATE_LAW = {
    "lagos": LAGOS,
    "rivers": RIVERS,
    "anambra": ANAMBRA,
    "kano": KANO,
    "abuja": ABUJA,
    "edo": EDO,
    "cross-river": CROSS_RIVER,
    "kwara": KWARA,
}

# States we currently publish four pages each for, with NOTHING verified.
# Per the publication rule these get no four-tool pages until something is found.
TIER_E_PUBLISHED = ["ogun", "plateau"]

# States we publish that sit below tier A and still need primary confirmation.
NEEDS_CONFIRMATION = {
    "oyo": "B/C — Recovery of Premises Law Cap 144 and a Rent (Increase Restriction) Law; two sources disagree on the chapter number (Cap 144 vs Cap 71).",
    "enugu": "B — Landlord and Tenant Law, Cap. 101, Laws of Enugu State 2004. An amendment BILL would abolish caution fees; it has NOT passed (ICIR, Dec 2025).",
    "delta": "C — Rent Control and Recovery of Residential Premises Law, Cap. R5, Laws of Delta State. A 2026 Tenancy Bill is at second reading; not law.",
    "kaduna": "C — Landlord and Tenant Law 2018, single source.",
}


def stats():
    """Summary used by tools/audit_state_pages.py and by the QA report."""
    return {
        "jurisdictions_with_verified_law": len(STATE_LAW),
        "tier_a": sum(1 for s in STATE_LAW.values() if s["tier"] == "A"),
        "published_but_nothing_verified": TIER_E_PUBLISHED,
        "needs_confirmation": len(NEEDS_CONFIRMATION),
        "open_questions": sum(len(s.get("open_questions", [])) for s in STATE_LAW.values()),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(stats(), indent=2))
    for slug, s in STATE_LAW.items():
        print("\n%s — %s (tier %s)" % (slug, s["name"], s["tier"]))
        for st in s.get("statutes", []):
            print("   %s — %s" % (st["title"], st.get("citation", "")))
            print("      commenced: %s" % st.get("commenced", "—"))
        q = s.get("open_questions", [])
        if q:
            print("   OPEN (%d):" % len(q))
            for item in q:
                print("      - %s" % item)
