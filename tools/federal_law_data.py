"""federal_law_data.py — the federal shelf: law that applies to a tenant in every state.

Same shape as one entry of `state_law_data.STATE_LAW`, so `law_index` flattens it the same way
(ids `nigeria:<topic>:<n>`). It is *not* a state: `law_index.states()` never lists it, the
state-page generator never renders it, the brain never "picks" it. Every state's shelf simply
carries these facts after its own, and a claim may cite them from any state.

Verified 27 Oct 2026 (Strategy Office analysis #1, docs/RENT_RELIEF.md): the Act's text as
quoted by TheCable and Legit.ng (1 Aug 2025); Forvis Mazars Nigeria (21 Apr 2026); PwC Tax
Summaries Nigeria (29 May 2026) and KPMG Flash Alert 2025-168 for the bands; NRS (Olufemi
Olarinde) in BusinessDay 22 Jan 2026 and Daily Trust 16 Feb 2026 for timing; the University of
Lagos staff circular (3 Feb 2026) for what evidence an employer asks for.
"""

# SOURCES ADDED 28 Oct 2026: Joint Revenue Board of Nigeria, "Personal Income Tax Guidelines,
# 2026" (jrb.gov.ng, dated 24 Feb 2026; Forvis Mazars 21 Apr 2026 cites its issue on 7 Apr 2026)
# — Part III para 9: 9.1 20% / ₦500,000; 9.2 accurate declaration; 9.3 shared tenancy, each up to
# ₦500,000 on their portion; 9.4 actual-year basis; 9.5 multi-year rent apportioned (example:
# ₦2,000,000 over 24 months → ₦1,000,000 attributable to 2026); 9.6 minimum information —
# legal tenant's name; actual rent paid and period covered; landlord's full name and one of
# mobile number, Tax ID or NIN; property address. SeamlessHR support FAQ (Jan 2026): admins may
# require staff to upload "valid rent certificates or any proof of rent paid" before the relief
# is applied — the payroll system holds the number, the tenant must still bring the paper.
FEDERAL_LAW = {
    "nigeria": dict(
        slug="nigeria",
        name="Nigeria (federal)",
        place="Nigeria",
        full="the Federal Republic of Nigeria",
        tier="A",
        statutes=[
            dict(title="Nigeria Tax Act 2025",
                 citation="Nigeria Tax Act 2025 (assented 26 June 2025; in force 1 January 2026)",
                 source="https://www.thecable.ng/full-text-the-nigeria-tax-act-2025/"),
        ],
        rent_relief=dict(
            cite="s.30(2)(a)(vi)",
            text=(
                "s.30(2)(a)(vi) Nigeria Tax Act 2025 (in force 1 January 2026): in computing the taxable "
                "income of an individual, a <b>rent relief of 20% of the annual rent paid, subject to a "
                "maximum of ₦500,000</b>, is deducted — provided the individual accurately declares the "
                "actual amount of rent paid and other relevant information the relevant tax authority "
                "prescribes."
            ),
            replaces=(
                "Rent relief replaces the Consolidated Relief Allowance of the Personal Income Tax Act from "
                "the 2026 year of assessment; a person who pays no rent has no rent relief."
            ),
            not_automatic=(
                "The relief is claimed, not given: with no declaration the deduction is ₦0. An employee "
                "declares to the employer, who applies it through PAYE from the month the evidence is "
                "submitted; a self-employed person or anyone outside PAYE claims it in the annual return "
                "to the State tax authority (the Nigeria Revenue Service for FCT residents and others "
                "it assesses)."
            ),
            evidence=(
                "Joint Revenue Board PIT Guidelines 2026, para 9.6 — minimum information for rent relief: "
                "(i) the legal tenant's name; (ii) actual rent paid and the period covered; (iii) the "
                "landlord's full name and one of mobile number, Tax ID or NIN; (iv) the property address. "
                "A receipt in the tenant's own name with all four, the signed agreement and proof of "
                "payment is what HR and tax offices ask for."
            ),
            deadlines=(
                "Employer's annual PAYE return for the 2026 year: 31 January 2027. Individual annual "
                "return for 2026: 31 March 2027. Rent that straddles two years is apportioned to each."
            ),
            arithmetic=(
                "Worked figures: ₦1,200,000 rent → ₦240,000 relief; ₦1,500,000 → ₦300,000; ₦2,500,000 or "
                "more → the ₦500,000 cap. The relief reduces taxable income, not the tax bill: the naira "
                "saved is the relief multiplied by the person's top rate."
            ),
            bands=(
                "Fourth Schedule, Nigeria Tax Act 2025 — rates on taxable income from 2026: 0% on the first "
                "₦800,000; 15% on the next ₦2,200,000; 18% on the next ₦9,000,000; 21% on the next "
                "₦13,000,000; 23% on the next ₦25,000,000; 25% above ₦50,000,000."
            ),
            shared=(
                "Joint Revenue Board PIT Guidelines 2026, paras 9.3–9.5: in a shared tenancy each tenant "
                "claims up to ₦500,000 on the portion of rent they bear; the relief is on an actual-year "
                "basis (rent paid in 2026 relieves 2026); rent spanning years is apportioned — the "
                "Board's own example: ₦2,000,000 for 24 months counts ₦1,000,000 for 2026, relief "
                "₦200,000."
            ),
        ),
    ),
}
