#!/usr/bin/env python3
"""sample_docs.py — the sample documents people search for, as text they can read and a PDF they
can download, from the product's own wording (🔒 docs/GROWTH.md, first dive, 3 Nov 2026).

Why this exists: Search Console shows DocOga ranking only for the informational quit-notice
cluster, while the demand that sells — "tenancy agreement sample in nigeria pdf free download",
"rent receipt sample nigeria", "quit notice letter sample" — is served by Scribd uploads of
strangers' private agreements and by generic template farms. Google's own guidance (Search
Central, May 2025) and the 2026 citation studies agree on the shape that wins: the answer first,
real headings, lists and tables, the full sample visible on the HTML page, sources named, and a PDF
only as a download (HTML is the search destination; the PDFs are `noindex` in site/_headers).

Nothing here is invented. The agreement clauses are the thirteen the DocOga generator writes
(site/index.html, renderAgreement); the receipt fields are the five Lagos s.5(2) requires plus the
reference and signature every good receipt carries; the quit-notice wording is the generator's.
Placeholders are shown in square brackets — a sample, not a stranger's private contract.

    python3 tools/sample_docs.py          # write site/samples/*.pdf (idempotent, deterministic)
    python3 tools/sample_docs.py --check  # exit 1 if a PDF is missing or stale

The PDF writer below is deliberately dependency-free (PDF 1.4, Helvetica, WinAnsi) so the build
runs anywhere at ₦0 — Pillow is not needed and no font file is read.
"""
from __future__ import annotations

import sys
import textwrap
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "samples"
DOMAIN = "https://docoga.com.ng"
FOOTER = "Free sample from DocOga — make yours in 2 minutes at docoga.com.ng. General information, not legal advice."

# ----------------------------------------------------------------------------- the samples
# Each sample is a list of blocks: ("h", heading) | ("p", paragraph) | ("c", number, title, text)
# | ("kv", label, value) | ("sig", [labels]) | ("gap",). The HTML and the PDF are rendered from the
# same blocks so the page never says something the download does not.

AGREEMENT_CLAUSES = [
    ("TERM", "The Landlord agrees to let and the Tenant agrees to take the Demised Premises for a term of "
             "[12] months certain, commencing on [1 January 2027] and ending on [31 December 2027], renewable by "
             "mutual agreement of the parties."),
    ("RENT", "The Tenant shall pay to the Landlord a rent of [₦850,000 (Eight Hundred and Fifty Thousand Naira)] "
             "per annum, payable in advance, without deduction except as may be permitted by law."),
    ("CAUTION FEE / DEPOSIT", "The Tenant has paid a caution fee (security deposit) of [₦100,000 (One Hundred "
             "Thousand Naira)], refundable at the expiration or earlier termination of the tenancy, subject to "
             "deductions for any damage to the Demised Premises beyond normal wear and tear."),
    ("USE OF PREMISES", "The Tenant shall use the Demised Premises for residential purposes only and shall not use "
             "the Premises or permit it to be used for any illegal, immoral or hazardous purpose."),
    ("NO ASSIGNMENT OR SUBLETTING", "The Tenant shall not assign, sublet, or part with possession of the Demised "
             "Premises or any part thereof without the prior written consent of the Landlord."),
    ("REPAIRS AND MAINTENANCE", "The Landlord shall keep the roof and external walls of the Demised Premises in good "
             "structural repair. The Tenant shall keep the interior, sanitary fittings and installations in good and "
             "tenantable condition, and shall be liable for any damage caused by the negligence of the Tenant, his "
             "guests or invitees."),
    ("UTILITIES", "The Tenant shall pay all charges for electricity, water, waste disposal and other utilities consumed "
             "on the Demised Premises during the tenancy."),
    ("QUIET ENJOYMENT", "The Landlord covenants that the Tenant, upon paying the rent and observing the covenants "
             "herein, shall peacefully hold and enjoy the Demised Premises during the tenancy without any interruption "
             "by the Landlord or any person lawfully claiming under him."),
    ("ALTERATIONS", "The Tenant shall not make any structural alteration or addition to the Demised Premises without "
             "the prior written consent of the Landlord."),
    ("INSPECTION", "The Landlord or his authorised agent may enter the Demised Premises to inspect its condition upon "
             "giving the Tenant reasonable prior notice."),
    ("NOTICE TO QUIT", "Either party may terminate this tenancy by serving on the other party written notice to quit "
             "of [six months], in accordance with the Tenancy Law applicable in [Lagos] State."),
    ("RENEWAL AND RENT REVIEW", "The parties may renew this tenancy upon terms to be agreed, and the rent may be "
             "reviewed upon renewal by mutual agreement."),
    ("GOVERNING LAW AND JURISDICTION", "This agreement shall be governed by the laws of the Federal Republic of "
             "Nigeria and the tenancy law applicable in [Lagos] State, and the parties submit to the jurisdiction of "
             "the courts of that state."),
]

TENANCY_AGREEMENT = [
    ("h", "RESIDENTIAL TENANCY AGREEMENT"),
    ("p", "Made this [1st] day of [January 2027]"),
    ("p", "THIS TENANCY AGREEMENT is made between"),
    ("p", "[LANDLORD'S FULL NAME] of [landlord's address] (Tel: [phone]) (hereinafter called \"the Landlord\", "
          "which expression shall where the context so admits include the Landlord's heirs, successors-in-title "
          "and assigns)"),
    ("p", "AND"),
    ("p", "[TENANT'S FULL NAME] of [tenant's address] (Tel: [phone]) (hereinafter called \"the Tenant\")."),
    ("p", "WHEREAS the Landlord is the owner or is lawfully entitled to grant a tenancy of all that property known, "
          "described and situate at [2-bedroom flat, first floor], [12 Example Street, Surulere], [Lagos] State "
          "(hereinafter called \"the Demised Premises\")."),
    ("p", "NOW THIS AGREEMENT WITNESSES as follows:"),
] + [("c", i + 1, t, body) for i, (t, body) in enumerate(AGREEMENT_CLAUSES)] + [
    ("p", "IN WITNESS WHEREOF the parties have executed this agreement on the date first above written."),
    ("sig", ["LANDLORD — Signature / Date", "TENANT — Signature / Date", "WITNESS 1 — Name / Signature / Date",
             "WITNESS 2 — Name / Signature / Date"]),
]

RENT_RECEIPT = [
    ("h", "RENT RECEIPT — No. [0142]"),
    ("kv", "Date received", "[1 October 2026]"),
    ("kv", "Received from (tenant)", "[Tenant's full name], [tenant's address]"),
    ("kv", "By (landlord / agent)", "[Landlord's full name], [landlord's address]"),
    ("kv", "For the premises", "[2-bedroom flat, first floor, 12 Example Street, Surulere, Lagos]"),
    ("kv", "Amount received", "[₦850,000] ([Eight Hundred and Fifty Thousand Naira] only)"),
    ("kv", "Period covered", "[1 October 2026 to 30 September 2027] (12 months)"),
    ("kv", "Being", "Rent — caution fee and service charge are receipted separately"),
    ("kv", "Payment method", "[Bank transfer, reference 000123456789]"),
    ("kv", "Balance outstanding", "[Nil]"),
    ("sig", ["Received by — Signature / Name / Date"]),
    ("p", "Lagos Tenancy Law 2011, s.5(2): a rent receipt states the date, the names and addresses of landlord and "
          "tenant, the description and location of the premises, the amount paid and the period it covers. "
          "Failure to issue one is an offence — fine of ₦100,000 on conviction (s.5(3))."),
]

QUIT_NOTICE = [
    ("h", "NOTICE TO QUIT"),
    ("p", "[Date of service]"),
    ("p", "To: [Tenant's full name], [flat / shop / house and full address of the premises]"),
    ("p", "I, [Landlord's full name], the landlord of the premises you occupy as a yearly tenant at [address of "
          "the premises], hereby give you six months' notice to quit and deliver up possession of the said "
          "premises to me on or before [expiry date]."),
    ("p", "Take notice that if you remain in possession after that date, I shall serve on you the seven days' "
          "notice of owner's intention to recover possession and apply to the court for an order of possession, "
          "together with any arrears of rent and mesne profits."),
    ("p", "Dated this ____ day of ______________ 20____."),
    ("sig", ["[Landlord's name, signature and phone number]  -  or: [Agent / solicitor's name], for the landlord, "
             "under written authority dated [date before this notice]"]),
    ("p", "For a yearly tenant in Lagos where the agreement is silent (six months). Change the tenancy type and "
          "the period for a monthly (one month) or quarterly (three months) tenant; a weekly tenant or tenant at "
          "will gets one week (Lagos Tenancy Law 2011, s.13(1)). The notice written into a tenancy agreement "
          "governs instead."),
]

# 4 Nov 2026 (🔒 docs/GROWTH.md, fourth dive): the demand letter the generator writes (renderDemand),
# shown for its commonest Nigerian use — rent that fell due and was not paid. Every sentence below is
# the generator's sentence; the brackets are the user's details.
DEMAND_SENTENCES = [
    "We refer to [the rent of ₦425,000 for the period 1 July 2026 to 30 June 2027 in respect of the "
    "two-bedroom flat at 12 Example Street, Surulere, Lagos], which fell due on [1 July 2026]. Despite "
    "the passage of time, the said sum remains wholly unpaid.",
    "DEMAND is hereby made for the immediate payment of the sum of [Four Hundred and Twenty-Five Thousand "
    "(₦425,000) Naira Only], being the amount outstanding and owed to us.",
    "TAKE NOTICE that if the said sum is not paid within [14] days of the date of this letter, we shall, "
    "without further reference to you, instruct our solicitors to commence legal proceedings for the "
    "recovery of the debt, plus interest and costs, to the full extent permitted by law.",
    "We look forward to your prompt settlement.",
]

DEMAND_LETTER = [
    ("h", "DEMAND LETTER — UNPAID RENT"),
    ("p", "[LANDLORD'S FULL NAME], [landlord's address]"),
    ("p", "[Date]"),
    ("p", "[TENANT'S FULL NAME], [the flat / shop / house and full address of the premises]"),
    ("p", "Dear Sir/Madam,"),
    ("p", "RE: DEMAND FOR PAYMENT OF [FOUR HUNDRED AND TWENTY-FIVE THOUSAND (₦425,000) NAIRA ONLY]"),
] + [("p", t) for t in DEMAND_SENTENCES] + [
    ("p", "Yours faithfully,"),
    ("sig", ["[Landlord's full name, signature and phone number]  -  or: [Agent / solicitor's name], for the "
             "landlord"]),
    ("p", "A demand letter is the written record that the rent was asked for before anything else was done. "
          "It is not a notice to quit: ending the tenancy still takes the notice your agreement or your "
          "state's law requires, then the seven days' notice of the owner's intention to recover possession, "
          "then the court. Keep a copy and proof of delivery."),
]

# 5 Nov 2026 (🔒 docs/GROWTH.md, fifth dive): the notice of rent review the generator writes
# (renderRentReview). A rent increase is an offer for the next term, not an order for this one; the
# notice says so and carries the chosen state's section. Shown for Lagos. Every sentence below is the
# generator's sentence; the brackets are the user's details.
RENT_REVIEW_SENTENCES = [
    "Your current [yearly] tenancy of the above premises runs to [31 December 2026] at a rent of "
    "[Eight Hundred and Fifty Thousand (₦850,000) Naira Only] [per annum].",
    "This is written notice that, if you wish to continue in the premises after that date, the rent from "
    "[1 January 2027] will be [Nine Hundred and Fifty Thousand (₦950,000) Naira Only] [per annum], a change of "
    "[₦100,000 (11.8%)].",
    "This is a proposal for the next term and not a demand for the present one: the rent you agreed stands "
    "until [31 December 2026], and the new rent takes effect only on your written acceptance.",
    "Please let me have your answer in writing by [30 November 2026]. If we do not agree a rent, the tenancy "
    "is not thereby ended; it continues on its present terms until it is lawfully determined by the notice "
    "your agreement or the law requires.",
    "Nothing in this notice takes away your right under section 37 of the Lagos State Tenancy Law 2011 to "
    "apply to the court for an order declaring an increase unreasonable; by section 37(4) no tenant may be "
    "ejected while that application is pending.",
]

RENT_REVIEW_NOTICE = [
    ("h", "NOTICE OF RENT REVIEW"),
    ("p", "[LANDLORD'S FULL NAME], [landlord's address]"),
    ("p", "[Date]"),
    ("p", "[TENANT'S FULL NAME], [the flat / shop / house and full address of the premises]"),
    ("p", "Dear [Tenant's name],"),
    ("p", "RE: NOTICE OF RENT REVIEW — [2-BEDROOM FLAT, FIRST FLOOR, 12 EXAMPLE STREET, SURULERE, LAGOS]"),
] + [("p", t) for t in RENT_REVIEW_SENTENCES] + [
    ("p", "Yours faithfully,"),
    ("sig", ["[Landlord's full name, signature and phone number]  -  Landlord / for the Landlord"]),
    ("p", "Received by: ____________________ (tenant)   Signature: __________   Date: __________"),
    ("p", "For a yearly tenant in Lagos. The generator swaps the last paragraph for the chosen state: in Enugu "
          "it cites s.3(b) of the Landlord and Tenant (Amendment) Law 2008 (review only after every second "
          "anniversary, not more than 15%) and refuses to call a figure above the cap lawful; in the FCT and "
          "the other states it says the tenancy agreement governs. No state we have read fixes a notice period "
          "for a rent review — the quit-notice periods are a different question."),
]

# 5 Nov 2026 evening (owner: "build"): the tenant's reply the same tool writes (renderRentReply,
# "Who is writing? — the tenant"). Shown for Lagos with a counter-offer; the generator also writes a
# plain decline and an acceptance. The sample lives on the rent-increase page beside the notice — a
# second output of one tool, not a second page (the Growth lock forbids thin duplicates).
RENT_REPLY_SENTENCES = [
    "I refer to your notice dated [1 November 2026] proposing that the rent of the above premises, which is "
    "[Eight Hundred and Fifty Thousand (₦850,000) Naira Only] [per annum] under my [yearly] tenancy running to "
    "[31 December 2026], should be [Nine Hundred and Fifty Thousand (₦950,000) Naira Only] [per annum] from "
    "[1 January 2027], a change of [₦100,000 (11.8%)].",
    "I do not accept the proposed rent, but I wish to remain in the premises and I am willing to agree a rent of "
    "[Nine Hundred Thousand (₦900,000) Naira Only] [per annum] from [1 January 2027], a change on the present rent of "
    "[₦50,000 (5.9%)]; please confirm in writing whether you agree.",
    "Until a rent is agreed in writing, the tenancy continues on its present terms, and I will go on paying the "
    "current rent on the day it falls due. Nothing in this letter is a notice to quit or a surrender of the tenancy.",
    "I reserve my right under section 37 of the Lagos State Tenancy Law 2011 to apply to the court for an order "
    "declaring the proposed increase unreasonable, and I note that by section 37(4) no tenant may be ejected while "
    "such an application is pending.",
]

RENT_REPLY_LETTER = [
    ("h", "REPLY TO A NOTICE OF RENT REVIEW"),
    ("p", "[TENANT'S FULL NAME], [the flat / shop / house and full address of the premises]"),
    ("p", "[Date]"),
    ("p", "[LANDLORD'S FULL NAME], [landlord's address]"),
    ("p", "Dear [Landlord's name],"),
    ("p", "RE: YOUR NOTICE OF RENT REVIEW — [2-BEDROOM FLAT, FIRST FLOOR, 12 EXAMPLE STREET, SURULERE, LAGOS]"),
] + [("p", t) for t in RENT_REPLY_SENTENCES] + [
    ("p", "Yours faithfully,"),
    ("sig", ["[Tenant's full name, signature and phone number]  -  Tenant"]),
    ("p", "Received by: ____________________ (landlord or agent)   Signature: __________   Date: __________"),
    ("p", "A counter-offer from a yearly tenant in Lagos. The generator also writes a plain decline (renew at "
          "the current rent) and an acceptance, and swaps the last paragraph for the chosen state: in Enugu it "
          "cites s.3(b) of the Landlord and Tenant (Amendment) Law 2008 and, where the landlord's figure is more "
          "than 15% above the present rent, says so and declines it; in the FCT and the other states it asks that "
          "the review follow the tenancy agreement. Refusing an increase is not arrears — keep paying the current "
          "rent on the day it falls due and keep the receipts."),
]

# 12 Nov 2026 (owner: "let's do it" — money-only builds): the employment contract the generator writes
# (site/index.html, renderEmployment), as the sample people type "employment contract sample nigeria pdf"
# for. Eight clauses, the same order; the floors in brackets come from the Labour Act, Cap L1 LFN 2004,
# read from the enrolled text (ss.7, 9, 11, 15, 16, 18). A small shop hiring a sales assistant; no names.
EMPLOYMENT_CONTRACT = [
    ("h", "EMPLOYMENT CONTRACT"),
    ("p", "Private & Confidential"),
    ("p", "BETWEEN: [EMPLOYER'S BUSINESS NAME], of [business address, Lagos] (“the Employer”) of the one part;"),
    ("p", "AND: [EMPLOYEE'S FULL NAME], of [employee's address] (“the Employee”) of the other part."),
    ("c", 1, "POSITION AND DUTIES", "The Employer hereby employs the Employee as [Sales Assistant], and the Employee accepts such "
     "employment. The Employee shall: [attend to customers, keep the shop floor stocked and tidy, record each day's sales "
     "and bank the takings], and shall perform such other duties as the Employer may reasonably assign."),
    ("c", 2, "COMMENCEMENT AND PROBATION", "Employment commences on [1 December 2026]. The first [3] months constitute a "
     "period of probation, during which either party may terminate this contract with [one week's] written notice. "
     "Confirmation of employment will be communicated in writing on satisfactory completion of probation."),
    ("c", 3, "REMUNERATION", "The Employer shall pay the Employee a salary of [One Hundred and Twenty Thousand (₦120,000) "
     "Naira Only] per month, payable not later than the 28th day of each month, subject to statutory deductions "
     "(including PAYE tax and the Employee's pension contribution where applicable)."),
    ("c", 4, "HOURS AND PLACE OF WORK", "The normal working hours shall be [Monday to Saturday, 8:00am to 5:00pm, with one "
     "hour's break]. The principal place of work shall be [the shop at 12 Example Street, Surulere, Lagos], and the "
     "Employee may be required to work at such other place as the Employer's business reasonably requires."),
    ("c", 5, "ANNUAL LEAVE AND SICK LEAVE", "The Employee shall be entitled to [15] working days of annual leave for each "
     "completed year of service, to be taken at times approved by the Employer. The Employee shall further be entitled "
     "to paid sick leave of up to twelve working days in any calendar year, on the certificate of a registered "
     "medical practitioner."),
    ("c", 6, "CONFIDENTIALITY", "The Employee shall not, during or after the termination of this employment, disclose to "
     "any person any confidential information relating to the business, affairs, customers or finances of the Employer, "
     "except as required by law."),
    ("c", 7, "TERMINATION AND NOTICE", "After probation, either party may terminate this employment by giving [one "
     "month's] written notice (or payment in lieu). The Employer may terminate summarily for gross misconduct. All "
     "Employer property shall be returned on the last day of employment."),
    ("c", 8, "GOVERNING LAW", "This contract shall be governed by the laws of the Federal Republic of Nigeria."),
    ("p", "IN WITNESS WHEREOF the parties have executed this contract on the date first written above."),
    ("sig", ["For: [Employer's business name] — Employer — signature & date",
             "[Employee's full name] — Employee — signature & date"]),
    ("p", "The floors behind the brackets (Labour Act, Cap L1 LFN 2004, for a 'worker' as s.91 defines one): a written "
          "statement of terms within three months of engagement (s.7); notice after probation of at least one day, one week, "
          "two weeks or one month by length of service (s.11(2)) — the contract's one month is above that floor; wages at "
          "intervals of not more than one month (s.15); paid sick leave of up to twelve working days a year (s.16); at least "
          "six working days' holiday after twelve months (s.18). The salary shown is above the national minimum wage of "
          "₦70,000 a month (National Minimum Wage (Amendment) Act 2024)."),
]


# 12 Nov 2026 (second money-only build): the warning tool's two letters and the reply people search for.
# "Query" is Nigeria's name for the step before a warning — the employer asks for a written explanation
# within a stated time, and the warning (or nothing) follows the reply. Every letter mirrors what
# renderQueryLetter / renderWarning in site/index.html write. The law quoted is the Labour Act, Cap L1
# LFN 2004, read from the enrolled text: s.5(1) no fines or deductions for misconduct without a labour
# officer's written consent, s.5(7) deductions capped at one-third of a month's wages, s.11(5) summary
# dismissal kept for conduct that justifies it. No names; a shop and a sales assistant, as on the
# employment page.
QUERY_LETTER = [
    ("h", "QUERY"),
    ("p", "[EMPLOYER'S BUSINESS NAME]"),
    ("p", "[Business address, Lagos]"),
    ("p", "[14 November 2026]"),
    ("p", "To: [Employee's full name], [Sales Assistant]"),
    ("p", "RE: QUERY"),
    ("p", "Dear [Employee's first name],"),
    ("p", "It has been reported that [you resumed work at 9:40am on Monday 10 November and 10:05am on Wednesday "
          "12 November 2026 without prior notice or permission, leaving the shop unopened past the 8:00am "
          "resumption time] (date(s): [10 and 12 November 2026]), which, if established, is contrary to the terms "
          "of your employment and company policy."),
    ("p", "You are required to explain in writing why disciplinary action should not be taken against you in "
          "respect of the above, and to submit your explanation to the undersigned on or before [Monday 17 "
          "November 2026]."),
    ("p", "Your explanation will be considered before any decision is taken. Failure to respond within the time "
          "given may result in a decision being taken on the information available, in accordance with your "
          "employment contract and applicable labour laws."),
    ("p", "Yours faithfully,"),
    ("sig", ["[Manager's name, title] — for [Employer's business name] — signature & date",
             "[Employee's full name] — received — signature & date"]),
    ("p", "ACKNOWLEDGEMENT: I, [Employee's full name], acknowledge receipt of this query. Receipt does not "
          "indicate agreement with its contents."),
]

QUERY_REPLY = [
    ("h", "REPLY TO QUERY"),
    ("p", "[Employee's full name], [Sales Assistant]"),
    ("p", "[15 November 2026]"),
    ("p", "To: [Manager's name, title], [Employer's business name]"),
    ("p", "RE: REPLY TO QUERY DATED [14 NOVEMBER 2026]"),
    ("p", "Dear [Sir/Madam],"),
    ("p", "I acknowledge receipt of your query dated [14 November 2026] concerning [my late resumption on 10 and 12 "
          "November 2026]."),
    ("p", "[On both mornings the bus I take from Ikorodu was held in traffic on Ikorodu Road after an accident at "
          "Ketu; I called the shop line at 8:10am on the 10th and sent a message on the 12th, and I reported to "
          "work as soon as I arrived. I accept that I should have informed you directly before 8:00am.]"),
    ("p", "I sincerely apologise for the lateness and for any inconvenience to the business. [I have now arranged "
          "to leave home 45 minutes earlier and will call the manager directly before 7:45am on any day I "
          "expect to be late.] I assure you that this will not happen again."),
    ("p", "I remain committed to my work and respectfully ask that this explanation be taken into account."),
    ("p", "Yours faithfully,"),
    ("sig", ["[Employee's full name] — signature & date"]),
]

WARNING_LETTER = [
    ("h", "FIRST WRITTEN WARNING"),
    ("p", "[EMPLOYER'S BUSINESS NAME]"),
    ("p", "[Business address, Lagos]"),
    ("p", "[18 November 2026]"),
    ("p", "To: [Employee's full name], [Sales Assistant]"),
    ("p", "RE: FIRST WRITTEN WARNING"),
    ("p", "Dear [Employee's first name],"),
    ("p", "This letter serves as your first written warning in respect of [late resumption on 10 and 12 November "
          "2026 without prior notice, leaving the shop unopened past the 8:00am resumption time] (incident "
          "date(s): [10 and 12 November 2026]), which is contrary to the terms of your employment and company "
          "policy."),
    ("p", "Reference is made to [the query dated 14 November 2026 and your reply dated 15 November 2026, which "
          "has been considered]."),
    ("p", "EXPECTED IMPROVEMENT: You are required to [resume work by 8:00am daily and to inform the manager by "
          "phone before 7:45am on any day you expect to be late] on or before [19 November 2026]."),
    ("p", "Be advised that failure to show the required improvement may result in further disciplinary action, "
          "up to and including the termination of your employment, in accordance with your employment contract "
          "and applicable labour laws."),
    ("p", "Yours faithfully,"),
    ("sig", ["[Manager's name, title] — for [Employer's business name] — signature & date",
             "[Employee's full name] — received — signature & date"]),
    ("p", "ACKNOWLEDGEMENT: I, [Employee's full name], acknowledge receipt of this letter. Receipt does not "
          "necessarily indicate agreement with its contents."),
    ("p", "What the warning may not do (Labour Act, Cap L1 LFN 2004): impose a fine or a deduction from wages for "
          "the misconduct — s.5(1) forbids both unless a law permits them or an authorised labour officer consents "
          "in writing to a reasonable deduction for loss the worker's wilful misconduct caused — and in any month "
          "deductions of every kind may not exceed one-third of wages (s.5(7)). Summary dismissal without notice "
          "remains open only for conduct that justifies it (s.11(5)); a documented query, reply and warning are "
          "what show, later, that it did."),
]


SAMPLES = {
    "tenancy-agreement-sample-nigeria": ("Tenancy Agreement — sample (Nigeria)", TENANCY_AGREEMENT),
    "rent-receipt-sample-nigeria": ("Rent Receipt — sample (Nigeria)", RENT_RECEIPT),
    "quit-notice-letter-sample-nigeria": ("Notice to Quit — sample letter (Nigeria)", QUIT_NOTICE),
    "demand-letter-rent-arrears-nigeria": ("Demand Letter for Unpaid Rent — sample (Nigeria)", DEMAND_LETTER),
    "rent-increase-notice-nigeria": ("Notice of Rent Review — sample (Nigeria)", RENT_REVIEW_NOTICE),
    "rent-increase-reply-nigeria": ("Reply to a Notice of Rent Review — tenant's sample (Nigeria)", RENT_REPLY_LETTER),
    "employment-contract-sample-nigeria": ("Employment Contract — sample (Nigeria)", EMPLOYMENT_CONTRACT),
    "query-letter-sample-nigeria": ("Query Letter — sample (Nigeria)", QUERY_LETTER),
    "query-letter-reply-nigeria": ("Reply to a Query — employee's sample (Nigeria)", QUERY_REPLY),
    "warning-letter-sample-nigeria": ("Warning Letter — sample (Nigeria)", WARNING_LETTER),
}


# ----------------------------------------------------------------------------- HTML
def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def html_sample(slug):
    """The sample as a <pre class="sample"> block the guide pages print above the fold."""
    _, blocks = SAMPLES[slug]
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "h":
            out.append(_esc(b[1]))
            out.append("")
        elif kind == "p":
            out.append(textwrap.fill(_esc(b[1]), 78))
            out.append("")
        elif kind == "c":
            out.append(textwrap.fill("%d. %s. %s" % (b[1], _esc(b[2]), _esc(b[3])), 78))
            out.append("")
        elif kind == "kv":
            out.append("%-24s %s" % (_esc(b[1]) + ":", _esc(b[2])))
        elif kind == "sig":
            out.append("")
            for label in b[1]:
                out.append("______________________________")
                out.append(_esc(label))
                out.append("")
    return '<pre class="sample">' + "\n".join(out).rstrip() + "</pre>"


# ----------------------------------------------------------------------------- PDF
PAGE_W, PAGE_H, MARGIN, LEADING, SIZE = 595, 842, 56, 14.5, 10.5
CHARS = 92   # Helvetica 10.5pt across 483pt: ~92 average characters


def _pdf_text(s):
    s = str(s).replace("₦", "NGN ").replace("—", "-").replace("–", "-")
    return s.encode("cp1252", "replace").decode("cp1252")


def _lines(blocks, title):
    """(font, text) pairs, already wrapped; 'B' = bold."""
    lines = [("B", _pdf_text(title)), ("R", "")]
    for b in blocks:
        kind = b[0]
        if kind == "h":
            lines += [("B", _pdf_text(b[1])), ("R", "")]
        elif kind == "p":
            lines += [("R", l) for l in textwrap.wrap(_pdf_text(b[1]), CHARS)] + [("R", "")]
        elif kind == "c":
            lines += [("B", _pdf_text("%d. %s" % (b[1], b[2])))]
            lines += [("R", l) for l in textwrap.wrap(_pdf_text(b[3]), CHARS)] + [("R", "")]
        elif kind == "kv":
            lines += [("R", l) for l in textwrap.wrap(_pdf_text("%s: %s" % (b[1], b[2])), CHARS, subsequent_indent="    ")]
        elif kind == "sig":
            lines.append(("R", ""))
            for label in b[1]:
                lines += [("R", "_" * 34), ("R", _pdf_text(label)), ("R", "")]
    return lines


def _escape_pdf(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_pdf(slug):
    """The sample as PDF bytes — PDF 1.4, two standard fonts, deterministic (no dates, no ids)."""
    title, blocks = SAMPLES[slug]
    lines = _lines(blocks, title)
    per_page = int((PAGE_H - 2 * MARGIN - 2 * LEADING) // LEADING)
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[]]
    objs = []  # list of bytes; object n = index + 1

    def add(body):
        objs.append(body)
        return len(objs)

    font_r = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font_b = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    pages_id = len(objs) + 1 + 2 * len(pages)   # the Pages object comes after all page+content pairs
    page_ids = []
    for n, page in enumerate(pages, 1):
        parts = ["BT", "/F1 %s Tf" % SIZE, "%d %d Td" % (MARGIN, PAGE_H - MARGIN), "%s TL" % LEADING]
        for font, text in page:
            parts.append("/%s %s Tf" % ("F2" if font == "B" else "F1", SIZE))
            parts.append("(%s) Tj T*" % _escape_pdf(text))
        parts.append("ET")
        foot = "%s  -  page %d of %d" % (_pdf_text(FOOTER), n, len(pages))
        parts += ["BT", "/F1 8 Tf", "%d %d Td" % (MARGIN, MARGIN - 20), "(%s) Tj" % _escape_pdf(foot), "ET"]
        stream = zlib.compress("\n".join(parts).encode("cp1252", "replace"))
        content = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_id = add(("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> "
                       "/Contents %d 0 R >>" % (pages_id, PAGE_W, PAGE_H, font_r, font_b, content)).encode())
        page_ids.append(page_id)
    real_pages = add(("<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join("%d 0 R" % p for p in page_ids), len(page_ids))).encode())
    assert real_pages == pages_id
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    info = add(("<< /Title (%s) /Author (DocOga) /Subject (Free sample - docoga.com.ng) >>" % _escape_pdf(_pdf_text(title))).encode("cp1252", "replace"))

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, catalog, info, xref)
    return bytes(out)


def pdf_url(slug):
    return "%s/samples/%s.pdf" % (DOMAIN, slug)


def write_all(out_dir=None):
    out_dir = Path(out_dir or OUT)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for slug in SAMPLES:
        data = render_pdf(slug)
        path = out_dir / ("%s.pdf" % slug)
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)
            written.append(path.name)
    return written


def check(out_dir=None):
    out_dir = Path(out_dir or OUT)
    stale = [slug for slug in SAMPLES if not (out_dir / ("%s.pdf" % slug)).is_file()
             or (out_dir / ("%s.pdf" % slug)).read_bytes() != render_pdf(slug)]
    return stale


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        stale = check()
        print("sample_docs: %s" % ("current" if not stale else "STALE " + ", ".join(stale)))
        return 1 if stale else 0
    written = write_all()
    print("sample_docs: wrote %d PDF(s)%s" % (len(written), (" — " + ", ".join(written)) if written else " (all current)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
