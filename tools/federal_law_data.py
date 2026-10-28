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
                "Evidence the tax authorities and employers ask for in practice (NRS guidance, January "
                "2026; employer circulars, February 2026): a rent receipt in the tenant's own name showing "
                "the date, amount, property and period; the signed tenancy agreement; proof of payment "
                "(transfer or teller); and the landlord's name with TIN or NIN. Records are kept for six "
                "years."
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
        ),
    ),
}
