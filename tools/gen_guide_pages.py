#!/usr/bin/env python3
"""Generate DocOga SEO guide pages — PLAN.md §4 keyword cluster.

The state pages (gen_state_pages.py) answer "how does this work in MY state".
These pages answer the *national* question people type first:
  tenancy agreement format Nigeria · notice to quit how many months ·
  is caution fee refundable · rent receipt format · tenant rights ·
  shop/tenancy agreement · invoice format + 7.5% VAT

FACTS VERIFIED 3 Oct 2026 (sources in each string below). The house rule from
the risk log applies: publish only what was checked, and frame anything
unverified as general practice + "confirm with a lawyer".

  * Lagos Tenancy Law 2011 s.13(1) notice minimums (1 week / 1 / 3 / 3 / 6 months)
    and s.14(7) of the draft 2025 Bill restating the 7-day notice of intention
    to recover possession; both also in Kleinfeld LP's overview of quit notices.
  * s.4 advance-rent cap: >1 year (yearly tenant) or >6 months (monthly tenant)
    is unlawful (Agbonika & Idachaba appraisal of the Lagos law).
  * s.13(2)-(3) arrears: monthly tenant 6 months in arrears / quarterly or
    half-yearly tenant 1 year in arrears loses the quit-notice entitlement.
  * s.1(3) the Law does NOT apply to Apapa, Ikeja GRA, Ikoyi, Victoria Island
    (Nigeria Property Centre, LawPàdí, Koriat Law, aolegal FAQ — 4 independent).
  * s.44 self-help is an offence: fine up to ₦250,000 or up to 6 months
    imprisonment (Nigeria Property Centre + aolegal FAQ + BusinessDay).
  * s.7 landlord obligations: do not terminate/restrict a common facility or
    service; do not seize or interfere with the tenant's personal property;
    repair and maintain the external and common parts.
  * Rent receipt: on payment of rent the landlord must issue a receipt stating
    the date, names and addresses of landlord and tenant, description and
    location of the premises, amount paid and period covered; failure attracts
    a ₦100,000 fine on conviction (s.5(3) — gazetted text, Lagos Ministry of
    Justice PDF; the ₦10,000 figure that circulates online is from a 2011
    newspaper summary of the draft). A separate receipt is required for a
    security deposit / services / service charge, and the tenant is entitled to
    a written account at least every 6 months of how the money was spent
    (text of the Law as reproduced by Nigeria Property Centre + cuab appraisal).
  * s.9 business premises: the landlord shall not inhibit access in a
    substantial manner, nor substantially alter or inhibit the flow of customers.
  * A tenant who improves the premises WITH the landlord's prior written
    consent may claim compensation for those improvements on quitting.
  * Caution fee: a refundable security deposit in principle; the 2011 Law has
    no explicit refund framework, and the 2026 Lagos Tenancy Bill (NOT yet law)
    would make the refund explicit. Market practice ~10% of annual rent or
    1-3 months (ventry.ng, mushrooms.ng fee guides).
  * VAT: 7.5% under the Nigeria Tax Act 2025, effective 1 Jan 2026 — unchanged
    by the reforms (Africa Report, Jan 2026). Zero-rated: basic food, medical
    supplies, books/educational materials, tuition, residential rent, exports.
    Small companies get 0% CIT and are relieved from charging VAT; the exact
    VAT registration threshold differs between 2026 advisories (₦25m vs ₦50m
    turnover), so the pages point at the NRS/accountant instead of a number.
    E-invoicing is rolling out in phases (large taxpayers first, Nov 2025).

Run: python3 tools/gen_guide_pages.py   (idempotent — safe to re-run)
"""
import io, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clean_urls import clean_text  # Cloudflare 307s /x.html → /x: canonicals, links and sitemap locs are bare

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE = os.path.join(ROOT, "site")
DOMAIN = "https://docoga.com.ng"
AS_AT = "October 2026"

# The 10 SPA tools, in homepage order — used for the "All DocOga tools" footer block.
TOOLS = [
    ("agreement", "Tenancy Agreement"), ("notice", "Notice to Quit"),
    ("receipt", "Rent Receipt"), ("invoice", "Invoice"),
    ("employment", "Employment Contract"), ("caution", "Caution Fee Receipt"),
    ("demand", "Letter of Demand"), ("payslip", "Payslip"),
    ("warning", "Warning Letter"), ("poa", "Power of Attorney"),
]

STATES = [("lagos", "Lagos"), ("abuja", "Abuja (FCT)"), ("rivers", "Rivers"),
          ("oyo", "Oyo"), ("kano", "Kano"), ("enugu", "Enugu")]

# ---------------------------------------------------------------- shared blocks
NOTICE_TABLE = '''<table>
<tr><th>Type of tenancy</th><th>Minimum notice to quit</th></tr>
<tr><td>Tenant at will / weekly</td><td>1 week</td></tr>
<tr><td>Monthly</td><td>1 month</td></tr>
<tr><td>Quarterly</td><td>3 months</td></tr>
<tr><td>Half-yearly</td><td>3 months</td></tr>
<tr><td>Yearly</td><td>6 months</td></tr>
</table>
<p class="law">These are the minimums <i>where the agreement is silent</i>. Where a written
agreement stipulates a notice period, that stipulation generally governs — so the notice you
actually want must be written into the agreement.</p>'''

SAMPLE_QUIT_NOTICE = '''<p>For a <b>yearly</b> tenant in Lagos where the agreement is silent (six months). Change the
tenancy type and the period for a monthly (1 month) or quarterly (3 months) tenant — the table below.</p>
<div style="background:#fff;border:1px solid #DCE4F0;border-radius:10px;padding:18px 20px;margin:10px 0;font-size:14.5px;line-height:1.75;color:#111">
<p style="text-align:right">[Date of service]</p>
<p>To: <b>[Tenant's full name]</b><br>[Flat / shop / house and full address of the premises]</p>
<p style="text-transform:uppercase;letter-spacing:.04em;font-weight:800;margin:10px 0">Notice to quit</p>
<p>I, <b>[Landlord's full name]</b>, the landlord of the premises you occupy as a <b>yearly tenant</b> at
<b>[address of the premises]</b>, hereby give you <b>six months' notice</b> to quit and deliver up
possession of the said premises to me on or before <b>[expiry date]</b>.</p>
<p>Take notice that if you remain in possession after that date, I shall serve on you the seven days'
notice of owner's intention to recover possession and apply to the court for an order of possession,
together with any arrears of rent and mesne profits.</p>
<p>Dated this ____ day of ______________ 20____.</p>
<p style="margin-top:18px">______________________________<br>[Landlord's name, signature and phone number]<br>
<span style="font-size:12.5px;color:#5B6B85">or: [Agent / solicitor's name], for the landlord, under written authority dated [date before this notice]</span></p>
</div>
<p class="law">Copy it, or let the generator fill the names, the period and the expiry date for you and give you a
clean PDF or a WhatsApp-ready copy — free. <a href="https://docoga.com.ng/#notice"><b>Make your quit notice free →</b></a></p>'''

LAGOS_SCOPE = ('<b>Where the Lagos law applies:</b> the Lagos Tenancy Law 2011 covers most of '
               'Lagos State, but <b>s.1(3) excludes four areas: Apapa, Ikeja GRA, Ikoyi and '
               'Victoria Island</b> (plus residential premises of educational institutions, '
               'emergency shelters, care/hospice, hospital and mental-health facilities, and '
               'rehabilitative or therapeutic treatment settings).')


def ul(items):
    return "<ul>\n" + "\n".join("<li>" + i + "</li>" for i in items) + "\n</ul>"


def faq_block(faq):
    return "\n".join("<details><summary>%s</summary><p>%s</p></details>" % (q, a) for q, a in faq)


def faq_jsonld(faq):
    """FAQPage rich-snippet schema. Built with json.dumps so it cannot be invalid."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faq
        ],
    }


# ------------------------------------------------------------------ the pages
PAGES = {}

# 1 ── PILLAR: tenancy agreement format Nigeria ---------------------------------
PAGES["tenancy-agreement-nigeria.html"] = dict(
    title="Tenancy Agreement in Nigeria (2026) — Format, Clauses &amp; Free Generator",
    h1="Tenancy Agreement in Nigeria: the 2026 format, clause by clause",
    desc="The standard Nigerian tenancy agreement format: parties, term, rent, the advance-rent limit, caution fee, notice period and covenants. Build one free in 2 minutes on your phone.",
    lead="A Nigerian tenancy agreement is the document that decides who pays what, for how long, "
         "and how either side ends the arrangement. Most disputes between Nigerian landlords and "
         "tenants are really arguments about a clause that was never written down. This page sets "
         "out the standard format and the rules that decide whether your agreement holds up — and "
         "DocOga will build the whole document for you in about two minutes, free, on your phone.",
    boxes=[
        ("The clauses a Nigerian tenancy agreement must contain", ul([
            "<b>The parties</b> — full legal names and addresses of the landlord and the tenant "
            "(and the agent, if one is collecting money).",
            "<b>The premises</b> — description and location, including the specific unit or flat.",
            "<b>The term</b> — start date and end date, or the period (monthly, quarterly, yearly).",
            "<b>The rent</b> — amount in figures <i>and</i> words, when it is payable, and how it is paid.",
            "<b>The advance</b> — how much is payable up front, within the legal limit (below).",
            "<b>The caution fee</b> — amount, that it is a refundable deposit, and the refund terms.",
            "<b>The notice period</b> — the notice each side must give to end the tenancy. This is "
            "the single most valuable clause in the document.",
            "<b>Covenants</b> — repairs, utilities and service charge, subletting, permitted use, "
            "alterations, and what happens at renewal.",
            "<b>Signatures and witnesses</b> — both parties, dated, each with a witness.",
        ])),
        ("The rules that decide whether it holds up",
         ul([
            "<b>The advance-rent cap.</b> Section 4 of the Lagos Tenancy Law 2011 makes it unlawful "
            "for a landlord or agent to demand or receive more than <b>one year's rent in advance</b> "
            "from a yearly tenant, or <b>six months</b> from a monthly tenant. Anything above that is "
            "unlawful — the tenant is at fault too if they pay it.",
            "<b>Notice is what you write.</b> The statutory minimums apply only <i>where there is no "
            "stipulation</i>. If you want three months' notice on a yearly tenancy, the agreement must "
            "say three months.",
            "<b>An oral tenancy still exists.</b> Under the Lagos law a tenancy is deemed to exist "
            "where premises are granted for value — express or implied, oral or written. But an oral "
            "tenancy leaves you with no agreed rent record and no caution-fee terms.",
            "<b>State law, not one national law.</b> Nigeria has no single national tenancy statute. "
            "Lagos runs the Tenancy Law 2011; the FCT runs the Recovery of Premises Act; other states "
            "run their own recovery-of-premises legislation.",
            "<b>Check the state page for your location.</b> " + LAGOS_SCOPE,
         ])),
        ("Notice-to-quit minimums where the agreement is silent", NOTICE_TABLE),
    ],
    faq=[
        ("Is a written tenancy agreement compulsory in Nigeria?",
         "No — a tenancy can exist without one. But without it you have no agreed rent record, no "
         "caution-fee terms, and the statutory notice defaults govern instead of the notice you "
         "actually wanted. A two-minute written agreement is cheaper than any dispute."),
        ("How much can a landlord ask for in advance?",
         "In Lagos, no more than one year's rent from a yearly tenant or six months from a monthly "
         "tenant — s.4 of the Tenancy Law 2011. Other states do not all have the same cap, so record "
         "whatever advance you agree clearly in the agreement before money moves."),
        ("Does the agreement override the notice periods in the law?",
         "Generally yes. The statutory minimums apply where the agreement is silent. Write the notice "
         "you want into the agreement and both sides are bound by it."),
        ("How much does a lawyer-drafted agreement cost?",
         "Commonly ₦20,000–₦50,000 in Nigerian cities, and agents often charge a separate "
         "\u201cagreement fee\u201d of around 10% of annual rent on top. The DocOga generator produces a "
         "standard agreement free (small watermark), or clean copies for ₦2,000 per 30 days."),
        ("Can I use one agreement for a shop or office?",
         "Commercial tenancies need extra clauses — permitted use, rent review, fixtures, reinstatement. "
         "See our guide to shop and business tenancy agreements before you sign."),
    ],
    cta=("agreement", "Create your tenancy agreement free →"),
    related=["notice-to-quit-nigeria.html", "caution-fee-nigeria.html",
             "rent-receipt-format-nigeria.html", "tenant-rights-nigeria.html",
             "shop-tenancy-agreement-nigeria.html"],
    priority="0.9",
)

# 2 ── notice to quit: how many months ------------------------------------------
PAGES["notice-to-quit-nigeria.html"] = dict(
    # Snippet rewritten 29 Oct 2026 from Search Console: #1 for "quit notice" (56 impressions,
    # 0 clicks) — Nigerians searching it want a SAMPLE letter and "how many months"; the title
    # now says both inside 60 characters and the page opens with the sample itself.
    title="Quit Notice Nigeria: Sample Letter, Format, How Many Months",
    h1="Quit notice in Nigeria — sample letter, how to write it, and how many months",
    desc="Quit notice sample letter (Nigeria): copy the wording or make yours free in 2 minutes — PDF or WhatsApp. How many months: 1 week, 1 month, 3 or 6 months, plus the 7-day notice.",
    lead="A notice to quit (quit notice) is the formal letter that starts a lawful end to a tenancy. "
         "Get the period wrong, or serve it on the wrong person, and the court will throw the case "
         "out — months wasted. Below: a sample you can copy, how many months each tenancy type "
         "requires in Nigeria, how to serve it, and a generator that produces a correctly-formatted "
         "notice in about two minutes.",
    boxes=[
        ("Sample quit notice letter (copy the wording)", SAMPLE_QUIT_NOTICE),
        ("How many months? The minimums", NOTICE_TABLE),
        ("How to write a quit notice — the six things it must carry", ul([
            "<b>Who is giving it</b> — the landlord by name, or an agent/solicitor who holds the "
            "landlord's <i>written</i> authority dated before the notice.",
            "<b>Who it is to and which premises</b> — the tenant's name and the exact flat, shop or "
            "house (the address as it appears on the rent receipt or agreement).",
            "<b>The type of tenancy</b> — weekly, monthly, quarterly, half-yearly or yearly, because "
            "that fixes the length of notice (table above).",
            "<b>The notice period and the expiry date</b> — \"six months' notice … to deliver up "
            "possession on or before [date]\". Where the written agreement fixes its own period, use "
            "that one.",
            "<b>Date and signature</b> — dated the day it is served and signed by the person giving it.",
            "<b>Plain language.</b> It is a notice, not a lawsuit: no insults, no threats beyond the "
            "lawful next step (the 7 days' notice and the court). Reasons are optional; the period "
            "and the date are not.",
        ]) + '<p class="law">Serving it in Lagos: hand it to the tenant; or leave it with an adult '
             'living in the premises; or send it by courier; or, where the tenant cannot be found, '
             'paste it on a conspicuous part of the premises and photograph it (Lagos Tenancy Law '
             '2011, ss.13–16). Keep a dated copy — proof of service wins or loses the case later.</p>'),
        ("The two notices every lawful eviction needs", ul([
            "<b>1. The notice to quit</b> — see the table. It must state the premises, the date the "
            "tenant is to give up possession, and be signed by the landlord or by an agent/solicitor "
            "with written authority dated <i>before</i> the notice is issued.",
            "<b>2. The 7 days' notice of the owner's intention to recover possession</b> — served "
            "<i>after</i> the notice to quit has expired and the tenant is still there. Only then can "
            "the landlord apply to court.",
            "<b>3. Court, not self-help.</b> Possession is recovered through the court. In Lagos that "
            "is the Magistrates' Court or the High Court, depending on the premises.",
        ])),
        ("When no notice to quit is needed at all",
         "<p>If the fixed term has already expired and the tenant is holding over, no notice to quit "
         "is required — the landlord serves only the 7 days' notice of intention to recover possession "
         "and proceeds to court. This surprises most landlords: the long notice applies to ending a "
         "tenancy that is still running, not to one that has already finished.</p>"),
        ("Arrears: when a tenant loses the right to a quit notice",
         "<p>Under <b>s.13(2)–(3) of the Lagos Tenancy Law 2011</b>, a <b>monthly</b> tenant who is "
         "six months in arrears loses the entitlement to a quit notice, and a <b>quarterly or "
         "half-yearly</b> tenant who is one year in arrears loses it too. The landlord can go to court "
         "on proof of the arrears. Never let arrears run — and landlords, follow the lawful process: "
         "self-help is a crime (below).</p>"),
        ("Self-help is a criminal offence in Lagos",
         "<p><b>Section 44</b> makes it an offence to demolish, alter or modify a building in order to "
         "eject a tenant without the court's approval, to attempt to forcibly eject a tenant, to "
         "threaten or molest a tenant with a view to ejecting them, or wilfully to damage the "
         "premises. The penalty is a fine of up to <b>₦250,000</b> or up to <b>six months' "
         "imprisonment</b>. Roof-removal, lock-changing and removing a tenant's doors all fall inside "
         "this section.</p>"),
    ],
    faq=[
        ("How do I write a quit notice in Nigeria?",
         "State who is giving it (the landlord, or an agent with written authority), the tenant's "
         "name and the exact premises, the type of tenancy, the length of notice and the date the "
         "tenant must give up possession, then date and sign it. Serve it personally, through an adult "
         "living there, by courier, or by pasting it on the premises — and keep a dated copy. The sample "
         "and the free generator on this page produce exactly that."),
        ("Can my landlord give me less than six months' notice?",
         "If your written agreement specifies a shorter (or longer) notice, that clause generally "
         "governs — the statutory minimums apply only where the agreement is silent. Read your "
         "agreement before you react to a notice."),
        ("How do I count the notice period?",
         "Traditionally the notice had to expire at the end of a complete period of the tenancy; the "
         "modern Lagos rule allows expiry on or after the current term ends. When you are the one "
         "giving notice, give more than the minimum — a generous notice is rarely challenged, a short "
         "one is."),
        ("Does a notice to quit mean I must leave immediately?",
         "No. It starts the process. If you stay past the expiry date the landlord must still serve "
         "the 7 days' notice and then obtain a court order. But you do owe rent (or mesne profits) for "
         "the period you remain."),
        ("What if the notice was signed by an agent?",
         "That is fine if the agent had written authority from the landlord dated before the notice was "
         "issued. An agent signing without authority is a common reason notices fail."),
        ("Can I be evicted without going to court?",
         "No. In Lagos, forcible ejection is an offence under s.44 — fine up to ₦250,000 or up to six "
         "months' imprisonment. Only the court can order possession."),
    ],
    cta=("notice", "Create your notice to quit free →"),
    related=["tenancy-agreement-nigeria.html", "tenant-rights-nigeria.html",
             "caution-fee-nigeria.html", "rent-receipt-format-nigeria.html"],
    priority="0.9",
)

# 3 ── caution fee: is it refundable --------------------------------------------
PAGES["caution-fee-nigeria.html"] = dict(
    title="Is the Caution Fee Refundable in Nigeria? (2026)",
    h1="Is the caution fee refundable in Nigeria? Yes — here is how to actually get it back",
    desc="A caution fee is a refundable security deposit, not a payment. What Nigerian law says, the clause to insist on, and how to claim the money back when you move out.",
    lead="The caution fee is the most disputed money in Nigerian renting. It is usually 10% of annual "
         "rent or one to three months' rent, paid on top of everything else — and too many tenants "
         "never see it again. The short answer is that it is refundable money. Whether <i>you</i> get "
         "it back depends almost entirely on what you wrote down before you moved in.",
    boxes=[
        ("The short answer",
         "<p><b>Yes — a caution fee is a refundable security deposit, not a payment for anything.</b> "
         "It is held against damage you cause beyond normal wear and tear, or bills you leave unpaid. "
         "At the end of the tenancy you are entitled to it back, minus the documented cost of genuine "
         "damage. If an agreement describes the caution fee as non-refundable, push back "
         "<i>before</i> you sign — that is a red flag, not a standard term.</p>"),
        ("What the law actually says", ul([
            "<b>Nigeria has no single national tenancy statute</b> — tenancy is regulated state by "
            "state, so there is no one refund rule that applies everywhere.",
            "<b>In Lagos the 2011 Law has no explicit refund framework.</b> It requires the landlord "
            "to issue a <i>separate receipt</i> for a security deposit (never lump it into the rent "
            "receipt) and entitles the tenant to a written account at least every six months of how "
            "money paid for deposits, services and service charges was spent. It does not itself spell "
            "out the refund.",
            "<b>That gap is exactly why the written clause matters.</b> Because the statute is quiet, "
            "your agreement and your receipt are the evidence a court will look at.",
            "<b>A 2026 Lagos Tenancy Bill would change this</b> — the draft entitles the tenant to a "
            "refund of the deposit at the end of the tenancy, minus documented repair costs. "
            "<b>It is a bill, not law yet.</b> Until it passes, the 2011 Law and your agreement are "
            "what count.",
        ])),
        ("Protect the deposit at move-in, not at move-out", ul([
            "<b>Receipt the deposit separately from rent</b> — a receipt that names it a caution fee, "
            "with the amount in figures and words.",
            "<b>Get the refund terms in writing</b> in the tenancy agreement. A clause that works: "
            "<i>\u201cThe Tenant shall pay a refundable caution deposit of ₦[amount]. On lawful "
            "termination of the tenancy and delivery of vacant possession, the Landlord shall refund "
            "the deposit within [14/21] days, less only the reasonable, documented cost of repairing "
            "damage caused by the Tenant beyond fair wear and tear. Any deduction shall be itemised in "
            "writing with supporting receipts.\u201d</i>",
            "<b>Record the property's condition on day one</b> — dated photos and a short checklist of "
            "every existing fault. This settles most arguments before they start.",
            "<b>Insist on itemised deductions.</b> A landlord who deducts \u201cfor repairs\u201d without a "
            "list and receipts has not made a lawful deduction.",
        ])),
        ("If the landlord simply refuses", ul([
            "<b>Send a written demand letter</b> with the receipt, the agreement clause, your move-in "
            "photos and the itemised breakdown you are disputing. Most refusals end here.",
            "<b>Keep every payment record.</b> Where the landlord refuses to accept rent at all, Lagos "
            "tenants can apply to pay it into the court's registry (s.28 of the Tenancy Law) — so "
            "\u201cthe landlord wouldn't take my money\u201d is not a dead end.",
            "<b>Then the court.</b> A money claim of this size is well within the small-claims "
            "procedure in Lagos; confirm the current monetary limit with the court or a lawyer.",
        ])),
    ],
    faq=[
        ("Is the caution fee the same as rent?",
         "No. It is a refundable deposit held against damage or unpaid charges — it is not the "
         "landlord's income, and it should never appear inside the rent figure on your receipt."),
        ("How much can a landlord charge as a caution fee?",
         "It is not fixed by statute in most states. Market practice in Lagos is roughly 10% of annual "
         "rent, or one to three months' rent. Whatever you agree must be written into the tenancy "
         "agreement and receipted separately."),
        ("Can a landlord deduct for 'wear and tear'?",
         "No. Fair wear and tear — faded paint, worn fittings from normal use — is the landlord's cost. "
         "Deductions are only for damage you actually caused, and they must be itemised with receipts."),
        ("What if I never got a receipt for the deposit?",
         "You can still claim — bank transfers, WhatsApp messages and the tenancy agreement all count "
         "as evidence. But this is precisely why the separate receipt matters; ask for one now, in "
         "writing, rather than at move-out."),
        ("How long does the landlord have to refund it?",
         "The statute does not set a deadline, which is why your agreement should. Fourteen to "
         "twenty-one days after delivery of vacant possession is the commonly agreed window."),
    ],
    cta=("caution", "Create your caution-fee receipt free →"),
    related=["tenancy-agreement-nigeria.html", "rent-receipt-format-nigeria.html",
             "tenant-rights-nigeria.html", "notice-to-quit-nigeria.html"],
    priority="0.8",
)

# 4 ── rent receipt format ------------------------------------------------------
PAGES["rent-receipt-format-nigeria.html"] = dict(
    title="Rent Receipt Format in Nigeria: How to Write One (2026)",
    h1="Rent receipt format in Nigeria — the five things the law requires",
    desc="The correct Nigerian rent receipt format: the five details Lagos law requires on every receipt, the ₦100,000 fine for refusing one, and a free generator that prints or saves as PDF.",
    lead="Nigerian rent is paid in advance, often a whole year in one transfer. That makes the receipt "
         "the single most important document a tenant holds — it is the proof of payment in any "
         "dispute, and the landlord's clean record too. In Lagos it is not optional: a landlord who "
         "refuses a receipt can be fined. Here is the exact format, and a generator that produces one "
         "in about two minutes.",
    boxes=[
        ("What the law requires on a rent receipt (Lagos)",
         "<p>The Lagos Tenancy Law 2011 obliges every landlord, on payment of rent, to issue a rent "
         "payment receipt to the tenant. The receipt must state:</p>" + ul([
            "<b>the date</b> the rent was received;",
            "<b>the names and addresses</b> of the landlord and the tenant;",
            "<b>the description and location of the premises</b> the payment relates to;",
            "<b>the amount of rent paid</b> — and put it in words as well as figures, so it cannot be "
            "altered;",
            "<b>the period the payment covers</b> (for example, one year from 1 October 2026).",
         ]) + "<p class=\"law\">A landlord who fails to issue a rent payment receipt is liable on "
              "conviction to a fine of <b>₦100,000</b> (s.5(3)).</p>"),
        ("A receipt that holds up looks like this",
         '<pre class="sample">RENT RECEIPT — No. 0142\n\nDate received:   1 October 2026\nReceived from:   Chinedu Okafor, 12 Bode Thomas St, Surulere, Lagos\nOf:              Landlord — Mrs A. Bello, 4 Adeola St, Ikeja, Lagos\nThe sum of:      One Million Five Hundred Thousand Naira only (₦1,500,000)\nBeing:           Rent for the self-contained apartment at Flat 2, 12 Bode\n                 Thomas Street, Surulere, Lagos\nPeriod covered:  1 October 2026 to 30 September 2027 (one year)\nPaid by:         Bank transfer — ref 90827364\n\nSigned:  ______________________   (landlord or authorised agent)\n         Mrs A. Bello</pre>'),
        ("Other money needs its own receipt", ul([
            "<b>Caution fee / security deposit</b> — a <i>separate</i> receipt, never folded into the "
            "rent figure. This is what makes the deposit refundable in practice.",
            "<b>Service charges and facility charges</b> — also receipted separately.",
            "<b>A written account every six months.</b> Where a landlord collects a deposit, service "
            "or facility charges, the tenant is entitled to a written account at least every six "
            "months of how that money was spent.",
            "<b>Agent collections</b> — whoever collects must receipt. Your agreement should name who "
            "is authorised to collect rent.",
        ])),
        ("Cash, transfer, and proof", ul([
            "<b>Bank transfer is the safest record</b> — but the transfer alone is not a receipt. Ask "
            "for the receipt anyway; the transfer reference belongs on it.",
            "<b>After any transfer</b>, send one WhatsApp message stating the amount, what it covers "
            "and the date. A read receipt creates a dated record.",
            "<b>Never pay cash without a signed receipt in your hand first.</b> Hand over the money "
            "and the receipt in the same moment.",
        ])),
    ],
    faq=[
        ("Is my landlord obliged to give me a receipt?",
         "In Lagos, yes — the Tenancy Law 2011 requires a rent payment receipt on payment of rent, and "
         "a landlord who refuses is liable on conviction to a ₦100,000 fine (s.5(3)). Even where a state's law is silent, a "
         "landlord who will not receipt a payment is a red flag no tenant should accept."),
        ("Can a rent receipt be handwritten?",
         "Yes — what matters is the content and the signature, not the printing. A clean printed "
         "receipt simply removes the arguments about what was written."),
        ("I paid an agent, not the landlord. Who issues the receipt?",
         "Whoever collects the money must receipt it. Your tenancy agreement should identify who is "
         "authorised to collect rent, and the agent should be collecting on the landlord's behalf."),
        ("Does a receipt need a stamp or seal?",
         "No stamp or seal is required for the receipt to be valid evidence. Some agreements and "
         "instruments attract stamp duty separately — that is a different tax, handled at state or "
         "federal level, and it does not make an unstamped receipt worthless."),
        ("What if my landlord refuses to issue one?",
         "Ask in writing (WhatsApp counts), quoting that the law requires it. If they still refuse, "
         "keep your transfer evidence and the messages — and in Lagos this is itself a breach you can "
         "raise with the Rent Tribunal or a lawyer."),
    ],
    cta=("receipt", "Create your rent receipt free →"),
    related=["caution-fee-nigeria.html", "tenancy-agreement-nigeria.html",
             "tenant-rights-nigeria.html", "invoice-format-nigeria.html"],
    priority="0.8",
)

# 5 ── tenant rights ------------------------------------------------------------
PAGES["tenant-rights-nigeria.html"] = dict(
    # Rewritten 29 Oct 2026 (Search Console: position 15, 21 impressions, 2 clicks). Page-one
    # rivals all run the "what your landlord cannot do" angle and most of them invent rules
    # (24–48h entry notice, deposit statutes, percentage caps). Ours answers the same question
    # with the section numbers — every one from tools/state_law_data.py, read from the enrolled
    # Lagos text — and says plainly what the law does NOT promise.
    title="Tenant Rights in Nigeria 2026: What Your Landlord Cannot Do",
    h1="Tenant rights in Nigeria — what your landlord cannot do, with the section of the law",
    desc="Tenant rights in Nigeria with the section numbers: 9 things your landlord cannot do, how many months' notice, rent increases — and what the law does not promise you.",
    lead="Most Nigerian tenants do not know what they are legally owed — which is why disputes get "
         "settled by whoever shouts loudest. Everything below carries the section it rests on, from "
         "the Lagos Tenancy Law 2011 (the most detailed state law) with the FCT and other states "
         "noted where they differ. Knowing the section changes how a conversation with your landlord "
         "goes.",
    boxes=[
        ("Nine things your landlord cannot do — with the section", ul([
            "<b>1. Put you out without a court order.</b> Forcibly ejecting you or attempting to, "
            "threatening or molesting you to make you leave, or demolishing, altering or modifying "
            "the building to eject you without the court's approval is a <b>criminal offence</b> in "
            "Lagos — fine of ₦250,000 or six months' imprisonment (s.44(1)). Removing the roof, "
            "changing the locks and taking off the doors all fall inside it.",
            "<b>2. Seize your property or block your access to it</b> — the landlord's statutory "
            "obligations include not seizing any item of the tenant's property or interfering with "
            "access to it (s.8). This is the answer to \"he has locked my things inside\".",
            "<b>3. Cut off a facility or service</b> the premises came with — light, water, the "
            "borehole, the common generator (s.8).",
            "<b>4. Disturb your quiet enjoyment.</b> s.6 gives you quiet and peaceable enjoyment: "
            "privacy, freedom from unreasonable disturbance, exclusive possession (subject only to "
            "the landlord's <i>restricted</i> right of inspection) and use of the common areas.",
            "<b>5. Refuse you a receipt.</b> Every rent payment must be receipted, and the receipt must "
            "show the date, both names and addresses, the premises, the amount and the period "
            "(s.5(1)–(2)); failing to issue it is a ₦100,000 fine (s.5(3)). Deposits and service "
            "charges get their own receipt and a written account at least every six months (s.10).",
            "<b>6. Demand more than a year's rent upfront.</b> A sitting yearly tenant may not be asked "
            "for more than one year, a sitting monthly tenant more than six months, a new tenant more "
            "than one year (s.4(1)–(4)). Both the landlord who collects it and the tenant who pays "
            "commit the offence — ₦100,000 or three months (s.4(5)).",
            "<b>7. Shorten your notice.</b> Where the agreement is silent: one week (tenant at will), "
            "one month (monthly), three months (quarterly and half-yearly), six months (yearly) "
            "(s.13(1)(a)–(e)) — then a further 7 days' notice of the owner's intention to recover "
            "possession before court. Full table and a free letter: "
            "<a href=\"https://docoga.com.ng/notice-to-quit-nigeria\">quit notice — how many months</a>.",
            "<b>8. Eject you while you are challenging a rent increase.</b> s.37 lets a sitting tenant "
            "ask the court (Form TL11) to declare an increase unreasonable; it is unlawful to eject the "
            "tenant while that application is pending (s.37(4)).",
            "<b>9. Refuse your rent and then call you a defaulter.</b> Where a landlord will not accept "
            "rent, the tenant may apply to the court to pay it into the Court Registry (s.29).",
        ])),
        ("How many months' notice before you can be asked to leave", NOTICE_TABLE +
         '<p class="law">Lagos s.13(1). Abuja (Recovery of Premises Act, Cap. 544, s.8) runs the same '
         'ladder without the half-yearly tier: a tenancy over one year is a yearly tenancy and six '
         'calendar months suffice. In both, the period counts from the <b>date of service</b>, not the '
         'date written on the letter. After the notice expires, a second notice — seven days, owner\'s '
         'intention to recover possession — and only then court. Arrears change this in Lagos: a '
         'monthly tenant six months behind, or a quarterly/half-yearly tenant a year behind, loses the '
         'right to a quit notice (s.13(2)–(3)).</p>'),
        ("Rent increase: what the law actually gives you", ul([
            "<b>There is no percentage cap</b> on rent increases in Lagos or anywhere in Nigeria. Any "
            "page that quotes one is wrong.",
            "<b>Mid-term, the agreement governs.</b> If the rent is fixed for the term, it cannot be "
            "raised before the term ends; an increase properly takes effect at renewal, on notice.",
            "<b>Your remedy is s.37.</b> Apply to the court on Form TL11 for an order that the increase "
            "is unreasonable. The court weighs the general level of rents in the locality, the "
            "witnesses and any special circumstances, and may fix the rent at a specific figure (Form "
            "TL13). You cannot be ejected while it is pending (s.37(4)).",
        ])),
        ("What the law does NOT promise you — the honest list", ul([
            "<b>No \"24–48 hours' notice before entry\" rule.</b> That figure is copied from foreign "
            "tenancy law. What Lagos gives you is privacy and exclusive possession under s.6, with the "
            "landlord's right of inspection <i>restricted</i> — so write the inspection notice period "
            "into your agreement.",
            "<b>No deposit statute.</b> The Lagos law does not use the words \"caution fee\". What it "
            "regulates is the receipt (s.10) and the six-monthly written account of how the money was "
            "spent; whether and how it is refunded is what your agreement says. "
            "<a href=\"https://docoga.com.ng/caution-fee-nigeria\">Caution fee: what to write in</a>.",
            "<b>No single national tenancy law.</b> The FCT's Recovery of Premises Act is not a federal "
            "law of general application; every state has its own. And the Lagos law itself does not "
            "apply in Apapa, Ikeja GRA, Ikoyi or Victoria Island (s.1(3)).",
            "<b>No right to withhold rent</b> because repairs are outstanding. The landlord must effect "
            "repairs and maintain the external and common parts (s.8(vi)); you keep the inside in good "
            "and tenantable repair, fair wear and tear excepted (s.7(3)). Withholding rent hands the "
            "landlord the arrears case — put the repair demand in writing instead.",
        ])),
        ("And the tenant's side (s.7)", ul([
            "Pay the rent at the time and in the manner agreed — arrears are the fastest route to "
            "losing the protection of a quit notice.",
            "Keep the premises in good and tenantable repair, fair wear and tear excepted (s.7(3)).",
            "Pay the rates and charges that are the tenant's responsibility under the agreement.",
            "Not to sublet, assign or alter the premises without the landlord's written consent "
            "(improvements made <i>with</i> written consent can be claimed for on quitting — s.6(2)).",
            "Not to use the premises for an illegal or immoral purpose.",
            "To give up possession lawfully at the end of the term.",
        ])),
        ("If your landlord breaks the rules", ul([
            "<b>Put everything in writing</b> — WhatsApp messages are admissible evidence and they are "
            "dated.",
            "<b>Self-help against a self-help landlord is still self-help.</b> Do not withhold rent "
            "unilaterally; if the landlord refuses to accept it, apply to pay it into the court's "
            "registry (s.29).",
            "<b>Forceful ejection is reportable.</b> It is a criminal offence in Lagos (s.44), not a "
            "civil disagreement — the police station and the Magistrates' Court, not a shouting match.",
            "<b>Where to go:</b> in Lagos the Magistrates' Court (the High Court for high-value "
            "premises); there is no Rent Tribunal in Lagos any more. The court may send the case to "
            "mediation (s.32); the Citizens Mediation Centre is free.",
            "<b>Document everything</b> — receipts, photos, the agreement, the notices you received.",
        ])),
    ],
    faq=[
        ("Can my landlord lock me out or remove my roof if I owe rent?",
         "No. Even in arrears, possession is recovered only through the court. In Lagos forcible "
         "ejection, threats to make you leave, or altering the building to eject you is an offence "
         "under s.44 — ₦250,000 or six months' imprisonment — and seizing your property or blocking "
         "your access to it breaches the landlord's obligations under s.8."),
        ("Can my landlord enter my flat without notice?",
         "Lagos law gives you privacy and exclusive possession (s.6) with the landlord's right of "
         "inspection restricted, but it does not fix a number of hours' notice — the 24–48 hours quoted "
         "online is foreign law. Put the inspection notice period in your tenancy agreement."),
        ("Can my landlord increase my rent at any time?",
         "Not mid-term if the agreement fixes the rent for the term; increases properly take effect "
         "at renewal, on notice. There is no statutory percentage cap, but a sitting tenant can ask the "
         "court under s.37 to declare an increase unreasonable, and cannot be ejected while that "
         "application is pending."),
        ("How many months' notice must my landlord give me?",
         "Where the agreement is silent: one week for a tenant at will, one month for a monthly tenant, "
         "three months for a quarterly or half-yearly tenant, six months for a yearly tenant (Lagos "
         "s.13(1); Abuja s.8 of the Recovery of Premises Act is the same without the half-yearly tier). "
         "Then a further seven days' notice before court."),
        ("Do I still pay rent during the notice period?",
         "Yes. A six-month notice is not six free months — rent continues to be due throughout, and "
         "after expiry the landlord can claim mesne profits for the period you remain."),
        ("I have no written agreement. Do I have any rights?",
         "Yes. Under the Lagos law a tenancy is deemed to exist where premises are granted for value, "
         "whether oral or written. The statutory notice minimums and protections still apply — you "
         "just have no agreed rent record, which is why you should write one now."),
        ("Is my caution fee or deposit refundable?",
         "The Lagos law does not legislate the refund; it requires a separate receipt for a deposit "
         "and a written account every six months of how it was spent (s.10). Refund terms are whatever "
         "the agreement says — so write them in before you pay."),
        ("Which law applies to me?",
         "State law. Lagos runs the Tenancy Law 2011 (which does not apply in Apapa, Ikeja GRA, Ikoyi "
         "or Victoria Island); the FCT runs the Recovery of Premises Act, Cap. 544; other states run "
         "their own recovery-of-premises legislation — see the state guides below."),
    ],
    cta=("agreement", "Put your tenancy in writing — free →"),
    related=["notice-to-quit-nigeria.html", "caution-fee-nigeria.html",
             "rent-receipt-format-nigeria.html", "tenancy-agreement-nigeria.html"],
    priority="0.8",
)

# 6 ── shop / commercial tenancy ------------------------------------------------
PAGES["shop-tenancy-agreement-nigeria.html"] = dict(
    title="Agreement Between Landlord and Tenant for a Shop in Nigeria (2026)",
    h1="Agreement between landlord and tenant for a shop: what a commercial tenancy needs",
    desc="Commercial tenancy in Nigeria — the clauses a shop or office agreement needs: permitted use, rent review, fixtures, signage, renewal and reinstatement. Free generator, 2 minutes.",
    lead="A shop tenancy is not a longer residential tenancy. The money at stake is a business, the "
         "term is usually longer, and the clauses that matter — permitted use, rent review, who owns "
         "the fittings, what has to be put back at the end — are the ones residential templates leave "
         "out. Here is what a Nigerian shop or office agreement must cover, and a generator that "
         "produces the document in about two minutes.",
    boxes=[
        ("How a shop tenancy differs from a residential one", ul([
            "<b>Longer terms, so more can go wrong.</b> Two- to five-year terms are common; a clause "
            "you skimmed on day one is still binding in year four.",
            "<b>The business depends on the location.</b> Access, footfall and signage are worth "
            "money — and Lagos law protects exactly those things for business premises (below).",
            "<b>You will spend money on the premises.</b> Shelving, counters, wiring, air-conditioning. "
            "Who owns those at the end, and who pays to remove them, must be written down.",
            "<b>Rent review is standard.</b> Agree the mechanism up front — a fixed percentage, or "
            "market rent with a cap — rather than negotiating it under pressure at renewal.",
            "<b>Longer leases are often stamped and registered.</b> Practice varies by state and term "
            "length; confirm with a lawyer before you rely on an unstamped long lease.",
        ])),
        ("Clauses your shop agreement must not leave out", ul([
            "<b>Permitted use</b> — precisely what business may be carried on. \u201cRetail sale of "
            "provisions\u201d protects you; \u201cas the tenant may determine\u201d does not.",
            "<b>The term and the renewal option</b> — including any break clause, and how much notice "
            "either side gives.",
            "<b>Rent, review and advance</b> — amount in figures and words, review mechanism, and how "
            "much is payable in advance.",
            "<b>Service charge and outgoings</b> — what is included, how it is calculated, and the "
            "tenant's right to a written account of how it was spent.",
            "<b>Fixtures, alterations and improvements</b> — what you may install, whether the "
            "landlord's consent is needed, and whether it must be removed at the end.",
            "<b>Reinstatement</b> — the condition the premises must be returned in. This is where "
            "deposits quietly disappear.",
            "<b>Signage</b> — what may be displayed and where, and who maintains it.",
            "<b>Assignment and subletting</b> — whether you can sell the business or bring in a "
            "partner without breaching.",
            "<b>Insurance and risk</b> — who insures the building, who insures stock, and who carries "
            "the loss if the premises become unusable.",
        ])),
        ("Lagos: extra protection for business premises",
         "<p><b>Section 9 of the Lagos Tenancy Law 2011</b> provides that, unless the agreement says "
         "otherwise, a business-premises agreement is taken to require that the landlord shall not "
         "<b>inhibit the tenant's access to the premises in any substantial manner</b>, and shall not "
         "<b>take any action that would substantially alter or inhibit the flow of customers, clients "
         "or other persons</b> using the business premises. For a shop, that is the clause that stops "
         "a landlord walling off your frontage or diverting the entrance to suit another tenant.</p>"),
        ("Fixtures and improvements — who owns them at the end?",
         "<p>Under the Lagos law, a tenant who improves the premises <b>with the landlord's prior "
         "written consent</b> may claim compensation for those improvements on quitting. That is a "
         "narrow right and it depends on the consent being in writing, so: get consent in writing "
         "before you spend, list the improvement and its cost in the agreement, and record what "
         "happens to it at the end of the term.</p>"),
    ],
    faq=[
        ("Can I use a residential tenancy agreement for my shop?",
         "You can, but you should not. It will be missing permitted use, rent review, fixtures, "
         "reinstatement and signage — the exact clauses commercial disputes turn on. Add them, or use "
         "a generator that includes them."),
        ("Can my landlord block the entrance to my shop?",
         "In Lagos, s.9 protects the tenant against the landlord inhibiting access in a substantial "
         "manner, or substantially altering or inhibiting the flow of customers. If your agreement is "
         "silent, the law implies that protection; if your agreement says otherwise, the agreement may "
         "override it — which is why the clause must be checked before you sign."),
        ("Do I get compensated for the fittings I installed?",
         "If you improved the premises with the landlord's prior written consent, Lagos law allows a "
         "claim for compensation on quitting. Without written consent you are relying on the agreement "
         "alone — so get the consent in writing before you spend."),
        ("How much advance rent can a landlord ask for on a shop?",
         "The Lagos advance-rent cap (one year for a yearly tenant, six months for a monthly tenant) "
         "is framed around tenancies generally; commercial deals are often negotiated differently and "
         "longer terms change the arithmetic. Record exactly what you agree, in the agreement, before "
         "money moves."),
        ("What notice ends a shop tenancy?",
         "The notice period in your agreement governs. Where the agreement is silent, the statutory "
         "minimums apply — six months for a yearly tenancy, for example — followed by the 7 days' "
         "notice of intention to recover possession if the tenant does not leave."),
    ],
    cta=("agreement", "Create your shop tenancy agreement free →"),
    related=["tenancy-agreement-nigeria.html", "notice-to-quit-nigeria.html",
             "invoice-format-nigeria.html", "tenant-rights-nigeria.html"],
    priority="0.8",
)

# 7 ── invoice format + VAT -----------------------------------------------------
PAGES["invoice-format-nigeria.html"] = dict(
    title="Invoice Format for Small Business in Nigeria (+7.5% VAT, 2026)",
    h1="Invoice format for small business in Nigeria — with 7.5% VAT done properly",
    desc="The Nigerian invoice format small businesses need: TIN, invoice number, VAT shown separately at 7.5%, totals in naira, payment terms. Free generator — print or PDF in 2 minutes.",
    lead="A Nigerian invoice that gets paid is specific: who you are, what was supplied, how much, "
         "and whether VAT applies. Since 1 January 2026 the Nigeria Tax Act 2025 governs the rules — "
         "the VAT rate itself did not change, but what you must show on the invoice, and who has to "
         "charge it, matters more than it used to. Here is the format, a worked VAT example, and a "
         "generator that produces a clean invoice in about two minutes.",
    boxes=[
        ("What a Nigerian invoice must carry", ul([
            "<b>Your business details</b> — name, address, and your <b>TIN</b> (Tax Identification "
            "Number). Clients increasingly refuse invoices without one.",
            "<b>The word \u201cInvoice\u201d</b>, a <b>sequential invoice number</b>, and the "
            "<b>invoice date</b>. Sequential numbering is part of what a VAT invoice requires.",
            "<b>The customer's details</b> — name and address (and their TIN for business customers).",
            "<b>Each item supplied</b> — description, quantity, unit price, and the line total.",
            "<b>The subtotal</b>, then <b>VAT shown separately</b> at the rate applied, then the "
            "<b>grand total in naira</b>.",
            "<b>Payment details and terms</b> — bank name, account name, account number, and the due "
            "date.",
            "<b>For a VAT invoice specifically:</b> the rate charged and the VAT amount, so the "
            "customer can see both. Never bury VAT inside a single lump sum.",
        ])),
        ("How to add 7.5% VAT — a worked example",
         '<table>\n'
         '<tr><th>Line</th><th>Amount (₦)</th></tr>\n'
         '<tr><td>Subtotal (goods or services supplied)</td><td>100,000.00</td></tr>\n'
         '<tr><td>VAT at 7.5%</td><td>7,500.00</td></tr>\n'
         '<tr><td><b>Total payable</b></td><td><b>107,500.00</b></td></tr>\n'
         '</table>\n'
         '<p class="law">VAT is added <i>on top</i> of your price, not extracted from it. If you quote '
         '₦100,000 "all-in" and you are VAT-registered, the VAT component of that figure is '
         '₦6,976.74 — you keep less than you think. Quote exclusive of VAT, or work the number '
         'backwards deliberately.</p>'),
        ("Who has to charge VAT in 2026", ul([
            "<b>The rate is 7.5%</b> — unchanged by the 2025 tax reforms, which took effect on "
            "1 January 2026.",
            "<b>Registration is turnover-based.</b> Once taxable supplies pass the statutory threshold "
            "you must register with the <b>Nigeria Revenue Service (NRS</b>, formerly FIRS<b>)</b>, "
            "charge 7.5% on taxable supplies and file monthly. 2026 advisories differ on the exact "
            "threshold figure, so confirm the current number with the NRS or your accountant rather "
            "than relying on a blog — including this one.",
            "<b>Small companies get relief.</b> Qualifying small companies (modest turnover and fixed "
            "assets below the statutory limit) pay 0% company income tax and are relieved from "
            "charging VAT under the small-company test. Professional-services firms are excluded from "
            "that relief.",
            "<b>Below the threshold, registration is voluntary</b> — and sometimes worth it, because "
            "bigger clients ask for VAT invoices.",
            "<b>What changed in 2026 for you:</b> input VAT is now recoverable on <b>services and "
            "capital assets</b>, not only on goods. Stop writing off the VAT on equipment, software "
            "and professional services by reflex.",
        ])),
        ("What is zero-rated or exempt", ul([
            "<b>Zero-rated at 0%</b> (input VAT still recoverable): basic food items, medical and "
            "pharmaceutical products, books and educational materials, tuition, <b>residential "
            "rent</b>, and exports.",
            "<b>Residential rent is zero-rated</b> — which is why a landlord issuing rent invoices "
            "should not be adding 7.5% to a residential tenant's rent.",
            "<b>Exempt supplies</b> (certain financial and government services) carry no VAT and no "
            "input recovery.",
        ])),
        ("E-invoicing is being rolled out",
         "<p>Nigeria is phasing in electronic (fiscal) invoicing through the NRS: large taxpayers "
         "first (from late 2025), then medium and smaller VAT-registered businesses over 2026 and "
         "2027. If you are VAT-registered, keep your invoice data clean and sequential now — "
         "converting later is painful. Confirm the timetable for your size band with the NRS or your "
         "accountant.</p>"),
    ],
    faq=[
        ("What is the VAT rate in Nigeria in 2026?",
         "7.5%. The Nigeria Tax Act 2025, effective 1 January 2026, kept the headline rate unchanged; "
         "what changed is that input VAT is now recoverable on services and capital assets too."),
        ("Do I have to charge VAT as a small business?",
         "Only once your taxable turnover passes the registration threshold, unless you qualify for the "
         "small-company relief. Below the threshold registration is voluntary. Confirm the current "
         "threshold with the NRS or your accountant — 2026 advisories quote different figures."),
        ("Is VAT added on top or taken out of my price?",
         "On top. Quote ₦100,000 plus 7.5% VAT = ₦107,000 total. If you quote an all-in price and you "
         "are registered, the VAT inside it comes out of your money."),
        ("Do I need a TIN on my invoice?",
         "You need one to be VAT-registered, and business customers increasingly insist on seeing it. "
         "A TIN is free and quick to obtain for a registered business — it also matters for withholding "
         "tax on payments to you."),
        ("Should my rent receipt include VAT?",
         "No. Residential rent is zero-rated, so a residential rent receipt or invoice should not carry "
         "7.5% VAT. Service charges on a residential building are a different question — ask your "
         "accountant before you add VAT to them."),
    ],
    cta=("invoice", "Create your invoice free →"),
    related=["rent-receipt-format-nigeria.html", "tenancy-agreement-nigeria.html",
             "shop-tenancy-agreement-nigeria.html"],
    priority="0.8",
)

# ------------------------------------------------------------------ rendering
WIDGET_RENT_RELIEF = r'''<style>
.calc{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.calc label{display:block;font-size:13px;font-weight:700;color:#37455E;margin-bottom:4px}
.calc input,.calc select{width:100%;padding:11px 12px;border:1px solid #C6D2E6;border-radius:10px;font-size:16px;font-family:inherit;color:#141F33;background:#fff}
.calc .full{grid-column:1/-1}
.result{background:#0B1B3F;color:#fff;border-radius:12px;padding:16px 18px;margin-top:12px}
.result b{font-size:24px;display:block;margin:2px 0 4px}
.result small{color:#C9D4EA;font-size:12.5px}
.letter{background:#fff;border:1px solid #DCE4F0;border-radius:10px;padding:22px 24px;margin-top:12px;font-size:14px;line-height:1.7;color:#111}
.letter h3{font-size:15px;text-transform:uppercase;letter-spacing:.04em;margin:0 0 10px}
.letter table{font-size:13px}
.letter .sig{margin-top:22px}
.letter .foot{margin-top:16px;font-size:11px;color:#555;border-top:1px solid #ddd;padding-top:6px}
.btnrow{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.btn2{display:inline-block;background:#0040E0;color:#fff;font-weight:800;border:0;border-radius:10px;padding:12px 18px;font-size:15px;cursor:pointer;text-decoration:none}
.btn2.alt{background:#E8EEFB;color:#0040E0}
@media (max-width:560px){.calc{grid-template-columns:1fr}}
@media print{.stickycta,.noprint,.brand,.lead,h1,.box:not(.printme),footer{display:none}.letter{border:0;padding:0}.wrap{padding:0}body{background:#fff}}
</style>
<div class="box noprint" id="calc">
<h2>Rent relief calculator (NTA 2025, s.30)</h2>
<div class="calc">
<div><label for="rr_rent">Annual rent you paid (₦)</label><input id="rr_rent" type="number" inputmode="numeric" min="0" placeholder="e.g. 1500000"></div>
<div><label for="rr_months">Months of that rent falling in this tax year</label><select id="rr_months"></select></div>
<div class="full"><label for="rr_income">Your annual gross income (₦, optional — for the tax-saved estimate)</label><input id="rr_income" type="number" inputmode="numeric" min="0" placeholder="e.g. 6000000"></div>
</div>
<div class="result" id="rr_out"><small>Enter your rent to see the deduction.</small></div>
<p class="law">Formula: the lower of 20% of the rent actually paid for the year and ₦500,000 (s.30(2)(a)(vi)). Rent that straddles two years counts only for the months in the year being assessed. The tax-saved figure is an estimate using the 2026 bands (0% to ₦800,000; 15%; 18%; 21%; 23%; 25% above ₦50m) and assumes no other deductions — your payroll or the tax office computes the exact amount.</p>
</div>

<div class="box noprint" id="letter">
<h2>Your rent-relief declaration letter — free</h2>
<p>This is the one-page evidence letter HR, payroll or the State Internal Revenue Service asks for. Fill it, attach your rent receipt and tenancy agreement, sign it, and hand it in. Nothing you type leaves your phone.</p>
<div class="calc">
<div class="full"><label for="rr_name">Your full name (as on your payslip / TIN)</label><input id="rr_name" placeholder="e.g. Chinedu Okafor"></div>
<div class="full"><label for="rr_addr">Address of the rented home</label><input id="rr_addr" placeholder="e.g. Flat 3, 12 Bode Thomas Street, Surulere, Lagos"></div>
<div><label for="rr_tin">Your TIN (or NIN)</label><input id="rr_tin" placeholder="optional"></div>
<div><label for="rr_to">Addressed to</label><select id="rr_to"><option>The Head of Human Resources / Payroll</option><option>The Executive Chairman, State Internal Revenue Service</option></select></div>
<div class="full"><label for="rr_org">Employer / tax office name</label><input id="rr_org" placeholder="e.g. Zenith Microfinance Bank Ltd  ·  Lagos State Internal Revenue Service"></div>
<div class="full"><label for="rr_ll">Landlord's full name</label><input id="rr_ll" placeholder="e.g. Mrs Aisha Bello"></div>
<div><label for="rr_lltin">Landlord's TIN / NIN</label><input id="rr_lltin" placeholder="optional, if the landlord gave it"></div>
<div><label for="rr_period">Period the rent covers</label><input id="rr_period" placeholder="e.g. 1 Jan 2026 – 31 Dec 2026"></div>
<div><label for="rr_paid">Date rent was paid</label><input id="rr_paid" type="date"></div>
<div><label for="rr_method">How you paid</label><select id="rr_method"><option>Bank transfer</option><option>Cash (receipted)</option><option>POS</option><option>USSD</option><option>Cheque</option></select></div>
<div><label for="rr_receipt">Rent receipt number(s)</label><input id="rr_receipt" placeholder="e.g. RCP-014"></div>
<div><label for="rr_date">Date of this letter</label><input id="rr_date" type="date"></div>
</div>
<div class="btnrow"><button class="btn2" type="button" onclick="rrPrint()">Print / Save PDF</button><a class="btn2 alt" href="https://docoga.com.ng/#receipt">Make the rent receipt first →</a></div>
</div>

<div class="box printme" id="rr_sheet"></div>

<script>
(function(){
var BANDS=[[800000,0],[2200000,0.15],[9000000,0.18],[13000000,0.21],[25000000,0.23],[Infinity,0.25]];
function tax(ci){var t=0,left=Math.max(0,ci);for(var i=0;i<BANDS.length&&left>0;i++){var w=Math.min(left,BANDS[i][0]);t+=w*BANDS[i][1];left-=w;}return t;}
function relief(rent,months){var m=(months==null?12:months);var eligible=Math.max(0,Number(rent)||0)*m/12;return Math.min(Math.round(eligible*0.2),500000);}
function fmt(n){return '₦'+Math.round(n).toLocaleString('en-NG');}
function $(id){return document.getElementById(id);}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function longDate(v){if(!v)return '____________';var d=new Date(v+'T12:00:00');if(isNaN(d))return esc(v);return d.toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric'});}
var sel=$('rr_months');for(var i=12;i>=1;i--){var o=document.createElement('option');o.value=i;o.textContent=i+(i===12?' (whole year)':'');sel.appendChild(o);}
function calc(){var rent=Number($('rr_rent').value)||0,months=Number($('rr_months').value)||12,inc=Number($('rr_income').value)||0;var out=$('rr_out');if(!rent){out.innerHTML='<small>Enter your rent to see the deduction.</small>';return;}var r=relief(rent,months);var capped=(rent*months/12*0.2)>500000;var html='<small>Your rent relief for the year</small><b>'+fmt(r)+'</b><small>'+(capped?'The ₦500,000 cap applies — 20% of your rent is higher.':'20% of '+fmt(rent*months/12)+' of rent counted for the year.')+'</small>';if(inc){var saved=tax(inc)-tax(inc-r);html+='<div style="margin-top:10px"><small>Estimated tax saved this year</small><b>'+fmt(Math.max(0,saved))+'</b><small>Estimate only — assumes no other deductions.</small></div>';}out.innerHTML=html;render();}
function render(){var rent=Number($('rr_rent').value)||0,months=Number($('rr_months').value)||12;var r=relief(rent,months);var rows=[['Tenant',esc($('rr_name').value)||'________________'],['Rented home',esc($('rr_addr').value)||'________________'],['Tenant TIN / NIN',esc($('rr_tin').value)||'—'],['Landlord',esc($('rr_ll').value)||'________________'],['Landlord TIN / NIN',esc($('rr_lltin').value)||'—'],['Annual rent paid',rent?fmt(rent):'₦______________'],['Period covered',esc($('rr_period').value)||'________________'],['Months in this tax year',String(months)],['Date paid · method',longDate($('rr_paid').value)+' · '+esc($('rr_method').value)],['Rent receipt no(s).',esc($('rr_receipt').value)||'________________'],['Rent relief claimed (20%, max ₦500,000)',rent?fmt(r):'₦______________']];var tbl='<table>'+rows.map(function(x){return '<tr><th style="width:42%">'+x[0]+'</th><td>'+x[1]+'</td></tr>';}).join('')+'</table>';$('rr_sheet').innerHTML='<div class="letter"><div style="text-align:right">'+longDate($('rr_date').value)+'</div><p>'+esc($('rr_to').value)+',<br>'+(esc($('rr_org').value)||'________________')+'</p><h3>Declaration of rent paid — claim for rent relief under section 30(2)(a)(vi), Nigeria Tax Act 2025</h3><p>I, <b>'+(esc($('rr_name').value)||'________________')+'</b>, declare that I occupy the residential premises below as a tenant and that I paid the rent stated for the period stated. I ask that the rent relief of 20% of the annual rent paid, subject to the maximum of ₦500,000, be applied in computing my chargeable income for the year of assessment.</p>'+tbl+'<p><b>Attached:</b> rent receipt(s) · tenancy agreement · proof of payment.</p><p>I declare that the information above is accurate, that the rent was actually paid by me, and that I do not occupy employer-provided accommodation. I understand the relief is granted only on rent actually paid and accurately declared.</p><div class="sig"><div style="border-bottom:1px solid #333;width:220px;height:34px"></div>Signature of tenant · '+longDate($('rr_date').value)+'</div><div class="foot">Made free with DocOga — docoga.com.ng · This letter is a declaration of facts you supply; it is not tax advice. Rent relief: Nigeria Tax Act 2025, s.30(2)(a)(vi).</div></div>';}
window.rrPrint=function(){render();try{if(window.gtag)window.gtag('event','rent_relief_letter',{});}catch(e){}window.print();};
['rr_rent','rr_months','rr_income'].forEach(function(id){$(id).addEventListener('input',calc);$(id).addEventListener('change',calc);});
['rr_name','rr_addr','rr_tin','rr_to','rr_org','rr_ll','rr_lltin','rr_period','rr_paid','rr_method','rr_receipt','rr_date'].forEach(function(id){$(id).addEventListener('input',render);$(id).addEventListener('change',render);});
if(!$('rr_date').value){var t=new Date();$('rr_date').value=t.getFullYear()+'-'+String(t.getMonth()+1).padStart(2,'0')+'-'+String(t.getDate()).padStart(2,'0');}
window.DocOgaRentRelief={relief:relief,tax:tax};
render();
})();
</script>'''

# 8 ── rent relief (NTA 2025) — the 2026 reason a tenant needs a receipt ----------
# FACTS VERIFIED 27 Oct 2026: Nigeria Tax Act 2025 s.30(2)(a)(vi) — rent relief of 20% of
# annual rent paid, maximum ₦500,000, from 1 Jan 2026, on accurate declaration (TheCable
# 1 Aug 2025 quoting the Act; Forvis Mazars 21 Apr 2026; PwC Tax Summaries 29 May 2026).
# Not automatic; employees via payroll on receipt, self-employed to the state IRS; employer
# annual return 31 Jan 2027, individual return 31 Mar 2027 (BusinessDay 22 Jan 2026 quoting
# the NRS's Olufemi Olarinde; Daily Trust 16 Feb 2026; taxngr.com Mar 2026). Evidence asked
# for in practice: receipts in the tenant's name, tenancy agreement, transfer proof, the
# landlord's name and TIN/NIN (FSC Professionals; infosteps.com.ng; UNILAG staff circular
# 3 Feb 2026 — "evidence of rent payment … must indicate the name and address of applicant").
# Joint tenants: each up to ₦500,000 on their own share; multi-year rent pro-rated to the
# year of assessment (Forvis Mazars). JRB "Personal Income Tax Guidelines, 2026" (jrb.gov.ng, 24 Feb
# 2026) Part III para 9.1–9.6 verified 28 Oct 2026 — the minimum information list. PIT bands 2026: 0% first ₦800k, 15%, 18%, 21%, 23%,
# 25% above ₦50m (PwC; KPMG Flash Alert 2025-168). Employer-provided accommodation: no relief.
PAGES["rent-relief-nigeria.html"] = dict(
    title="Rent Relief in Nigeria 2026: Claim the ₦500,000 Tax Deduction (Calculator + Free Letter)",
    h1="Rent relief in Nigeria — the 20% deduction every tenant can claim from 2026, and the papers you need",
    desc="Since 1 January 2026 tenants deduct 20% of rent paid (max ₦500,000) from taxable income — but only with a rent receipt and tenancy agreement. Calculator, deadlines, and a free declaration letter for HR or the tax office.",
    lead="The Nigeria Tax Act 2025 scrapped the old consolidated relief and gave tenants something "
         "better: a deduction of 20% of the rent you actually pay, up to ₦500,000 a year. It is not "
         "automatic. Nobody gets it without the paper — a rent receipt in your name, a tenancy "
         "agreement, and your landlord's details. Here is the law, the arithmetic, the deadlines, "
         "and a free letter that puts it all in front of your payroll desk.",
    widget=WIDGET_RENT_RELIEF,
    boxes=[
        ("What the law says",
         "<p>Section 30(2)(a)(vi) of the Nigeria Tax Act 2025 allows, in computing chargeable "
         "income, a <b>rent relief of 20% of annual rent paid, subject to a maximum of ₦500,000, "
         "whichever is lower</b> — \"provided that the individual accurately declares the actual "
         "amount of rent paid and other relevant information as may be prescribed by the relevant "
         "tax authority\". It applies from the <b>2026 year of assessment</b> (1 January 2026) to "
         "employees under PAYE and to the self-employed assessed directly.</p>" + ul([
            "<b>Only tenants.</b> Homeowners and people in employer-provided accommodation do not qualify.",
            "<b>Only rent actually paid.</b> Prepaid rent counts only to the extent it has been paid; "
            "rent that straddles two years is counted for the months in the year being assessed.",
            "<b>Joint tenants</b> each claim on their own share, each up to the ₦500,000 cap.",
            "<b>The cap bites at ₦2,500,000 of rent</b> — above that, more rent earns no more relief.",
         ])),
        ("What the tax authorities' own guidelines say",
         "<p>The Joint Revenue Board of Nigeria (the body of all State tax authorities and the NRS) "
         "issued <b>Personal Income Tax Guidelines, 2026</b> (dated 24 February 2026). Part III, "
         "paragraph 9 is the rent relief, and it settles the questions people argue about:</p>" + ul([
            "<b>9.1–9.2</b> — 20% of annual rent paid, maximum ₦500,000; the actual rent paid \"and other "
            "prescribed information must be accurately declared\".",
            "<b>9.3 Shared tenancy</b> — each tenant claims up to ₦500,000 on <i>their own portion</i> of "
            "the rent. Two flatmates on ₦3,000,000 each claim on ₦1,500,000 → ₦300,000 each.",
            "<b>9.4–9.5 Actual-year basis</b> — rent paid in 2026 relieves 2026; rent spanning years is "
            "apportioned. The Board's own example: ₦2,000,000 paid for 24 months counts ₦1,000,000 for "
            "2026, relief ₦200,000.",
            "<b>9.6 Minimum information</b> — (i) the legal tenant's name; (ii) actual rent paid and the "
            "period covered; (iii) the landlord's full name and <b>one of</b> mobile number, Tax ID or "
            "NIN; (iv) the property address.",
         ]) + "<p class=\"law\">That fourth paragraph is the test your receipt has to pass. A receipt that "
              "names the tenant, states the rent and the period, carries the landlord's name with a phone "
              "number, TIN or NIN, and gives the property address meets it. Payroll systems (SeamlessHR's "
              "own FAQ says so) hold the <i>number</i> you declare; the <i>paper</i> is still yours to "
              "bring, and HR may require it uploaded before the relief is applied.</p>"),
        ("The four papers that unlock it", ul([
            "<b>A rent receipt in your name</b> showing the amount, the period covered, the property "
            "address and the landlord's full name with a <b>phone number, TIN or NIN</b> — the four "
            "particulars the Joint Revenue Board's guidelines list (para 9.6, below). The DocOga receipt "
            "tells you when all four are on it.",
            "<b>A signed tenancy agreement</b> covering the year, naming you, the landlord, the "
            "premises and the rent.",
            "<b>Proof of payment</b> — the bank transfer or POS record. A transfer alone is not a "
            "receipt; the two together are unanswerable.",
            "<b>This declaration letter</b>, signed and dated, with the three above attached.",
         ]) + "<p class=\"law\">Nothing on this page needs a lawyer. The receipt and the agreement "
              "are both free on DocOga, in about two minutes each.</p>"),
        ("How and when to claim", ul([
            "<b>Employees (PAYE):</b> hand the letter and attachments to HR / payroll. The NRS has said "
            "that if you pay your rent in January and provide the receipt, the employer can apply the "
            "relief in your monthly tax immediately. Employers file their annual PAYE return by "
            "<b>31 January 2027</b>.",
            "<b>Self-employed, traders and artisans:</b> submit the receipts / agreement with your "
            "annual return to your <b>State Internal Revenue Service</b> by <b>31 March 2027</b> for "
            "the 2026 year.",
            "<b>Missed it in payroll?</b> You can still claim the balance in your own annual return "
            "by 31 March of the following year.",
            "<b>Keep everything six years.</b> Tax records must be retained; a receipt you can "
            "verify online (every DocOga receipt carries a code) is the easiest to defend.",
         ])),
        ("Worked examples (2026 bands)",
         '<table><tr><th>Annual rent</th><th>20% of rent</th><th>Relief allowed</th></tr>'
         '<tr><td>₦600,000</td><td>₦120,000</td><td>₦120,000</td></tr>'
         '<tr><td>₦1,500,000</td><td>₦300,000</td><td>₦300,000</td></tr>'
         '<tr><td>₦2,500,000</td><td>₦500,000</td><td>₦500,000</td></tr>'
         '<tr><td>₦4,000,000</td><td>₦800,000</td><td>₦500,000 (cap)</td></tr></table>'
         '<p class="law">What that is worth in tax depends on your band: a ₦300,000 deduction saves '
         '₦45,000 at 15%, ₦54,000 at 18%, ₦63,000 at 21%. If your taxable income is already under '
         '₦800,000 you pay no income tax, so the relief changes nothing for you.</p>'),
    ],
    faq=[
        ("Is rent relief automatic in my salary?",
         "No. Under s.30 of the Nigeria Tax Act 2025 the relief is granted only when you accurately "
         "declare the rent actually paid, with evidence. If you declare nothing, the relief is ₦0 — "
         "there is no fallback figure."),
        ("What documents do I need for rent relief?",
         "A rent receipt in your name carrying the four particulars in para 9.6 of the Joint Revenue "
         "Board's PIT Guidelines 2026 — your name, the rent and period covered, the landlord's full "
         "name with a phone number, TIN or NIN, and the property address — plus a signed tenancy "
         "agreement covering the year, proof of payment such as the bank transfer, and a signed "
         "declaration to your employer or tax office."),
        ("My landlord will not give me a receipt. Can I still claim?",
         "Insist, in writing — in Lagos a landlord who refuses a rent receipt commits an offence "
         "(Tenancy Law 2011, s.5(3), ₦100,000 fine). Practitioners report that a signed confirmation "
         "letter from the landlord plus your bank transfer evidence can stand in, but with no "
         "evidence at all there is no relief for that period."),
        ("I paid two years' rent in 2025. What can I claim in 2026?",
         "Relief is on an actual-year basis: only the part of the rent attributable to the 2026 "
         "year of assessment counts, and only if it was actually paid. Use the months selector in "
         "the calculator above."),
        ("Does the Oga Pass affect my claim?",
         "No. The free receipt and letter carry a small DocOga line; the ₦2,000 pass removes it and "
         "unlocks unlimited clean copies for 30 days. The tax office cares about the content, the "
         "signature and the proof of payment."),
    ],
    cta=("receipt", "Make your rent receipt free →"),
    related=["rent-receipt-format-nigeria.html", "tenancy-agreement-nigeria.html",
             "tenant-rights-nigeria.html", "caution-fee-nigeria.html"],
    priority="0.9",
)


CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;color:#141F33;background:#F5F7FB;line-height:1.6}
.wrap{max-width:760px;margin:0 auto;padding:20px 18px 110px}
.brand{display:inline-block;font-weight:900;font-size:20px;color:#0040E0;text-decoration:none;padding:10px 0}
h1{font-size:26px;line-height:1.25;margin:10px 0 14px}
.lead{font-size:16px;color:#37455E}
.box{background:#fff;border:1px solid #DCE4F0;border-radius:14px;padding:18px 20px;margin:20px 0}
h2{font-size:19px;margin-bottom:10px}
table{width:100%;border-collapse:collapse;font-size:14.5px;margin:8px 0}
th,td{padding:8px 10px;border:1px solid #DCE4F0;text-align:left}
th{background:#F0F4FA}
ul{padding-left:20px}
li{margin:8px 0;font-size:15px}
.law{font-size:13px;color:#5B6B85}
pre.sample{background:#F7F9FC;border:1px dashed #C6D2E6;border-radius:10px;padding:14px;font-size:12.5px;line-height:1.55;overflow-x:auto;white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.cta{display:inline-block;background:#0040E0;color:#fff;font-weight:800;text-decoration:none;border-radius:10px;padding:14px 24px;font-size:16px;margin:14px 0}
details{background:#fff;border:1px solid #DCE4F0;border-radius:12px;padding:14px 18px;margin:10px 0}
summary{font-weight:700;cursor:pointer}
p{margin:8px 0}
.links{font-size:14px}
.links a{color:#0040E0;text-decoration:none;font-weight:600;margin-right:12px;white-space:nowrap;display:inline-block}
footer{margin-top:34px;border-top:1px solid #DCE4F0;padding-top:16px;font-size:12.5px;color:#5B6B85}
.stickycta{position:fixed;left:0;right:0;bottom:0;z-index:60;background:#fff;border-top:1px solid #DCE4F0;box-shadow:0 -2px 14px rgba(20,31,51,.10);padding:10px 16px;display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap}
.stickycta span{font-size:13.5px;color:#141F33;font-weight:600}
.stickycta a{background:#0040E0;color:#fff;font-weight:800;text-decoration:none;border-radius:9px;padding:11px 18px;font-size:14.5px;white-space:nowrap}
@media print{.stickycta{display:none}}"""


def render(fname, p):
    boxes = "\n\n".join(
        '<div class="box">\n<h2>%s</h2>\n%s\n</div>' % (h, body) for h, body in p["boxes"]
    )
    related = "\n".join(
        '<a href="%s/%s">%s</a>' % (DOMAIN, r, PAGES[r]["navtitle"]) for r in p["related"]
    )
    state_links = "\n".join(
        '<a href="%s/tenancy-agreement-%s.html">%s</a>' % (DOMAIN, s, n) for s, n in STATES
    )
    tool_links = "\n".join(
        '<a href="%s/#%s">%s</a>' % (DOMAIN, h, n) for h, n in TOOLS
    )
    cta_hash, cta_label = p["cta"]
    ld = json.dumps(faq_jsonld(p["faq"]), ensure_ascii=False, indent=1)
    widget = ("\n" + p["widget"] + "\n") if p.get("widget") else ""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<link rel="canonical" href="%(domain)s/%(fname)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(domain)s/%(fname)s">
<meta property="og:type" content="article">
<script type="application/ld+json">
%(ld)s
</script>
<style>
%(css)s
</style>
</head>
<body>
<div class="wrap">
<a class="brand" href="%(domain)s/">DocOga</a>
<h1>%(h1)s</h1>
<p class="lead">%(lead)s</p>
%(widget)s
%(boxes)s

<div class="box">
<h2>Make it in 2 minutes \u2014 free</h2>
<p>DocOga works on your phone: answer simple questions, get a clean, standard Nigerian document you
can print, save as PDF or share on WhatsApp. The free version carries a small banner; the Oga Pass
(\u20a62,000/30 days) unlocks unlimited clean copies across all 10 tools.</p>
<a class="cta" href="%(domain)s/#%(cta_hash)s">%(cta_label)s</a>
</div>

<div class="box">
<h2>Questions people ask</h2>
%(faq)s
</div>

<div class="box links">
<h2>More guides</h2>
%(related)s
<h2 style="margin-top:14px">State guides</h2>
%(state_links)s
<h2 style="margin-top:14px">All DocOga tools \u2014 free</h2>
%(tool_links)s
</div>

<footer>
<b>DocOga</b> \u2014 free Nigerian document tools: tenancy agreement, notice to quit, rent receipt,
invoice, employment contract, caution fee receipt, letter of demand, payslip, warning letter,
and power of attorney.
<br><br>This page is general information about Nigerian law and practice, current as at %(as_at)s \u2014
it is not legal advice. Laws differ by state and change over time; confirm the current position for
your case with a qualified Nigerian lawyer or your accountant.
</footer>
</div>
<div class="stickycta">
<span><b>Oga Pass</b> — ₦2,000 · 30 days · all 10 tools · no banner</span>
<a href="%(domain)s/#pricing">Get the Pass</a>
</div>
<script src="/analytics-consent.js" data-track-page="true" defer></script>
</body>
</html>
""" % dict(title=p["title"], desc=p["desc"], h1=p["h1"], lead=p["lead"], boxes=boxes,
           faq=faq_block(p["faq"]), related=related, state_links=state_links,
           tool_links=tool_links, cta_hash=cta_hash, cta_label=cta_label,
           fname=fname, domain=DOMAIN, css=CSS, ld=ld, as_at=AS_AT, widget=widget)


def main():
    # short labels for the "More guides" block
    navtitles = {
        "tenancy-agreement-nigeria.html": "Tenancy agreement format",
        "notice-to-quit-nigeria.html": "Notice to quit: how many months",
        "caution-fee-nigeria.html": "Is the caution fee refundable?",
        "rent-receipt-format-nigeria.html": "Rent receipt format",
        "tenant-rights-nigeria.html": "Tenant rights &amp; landlord duties",
        "shop-tenancy-agreement-nigeria.html": "Shop &amp; business tenancy",
        "invoice-format-nigeria.html": "Invoice format + 7.5% VAT",
        "rent-relief-nigeria.html": "Rent relief: the ₦500,000 tax deduction",
    }
    for f, p in PAGES.items():
        p["navtitle"] = navtitles[f]

    made = []
    for fname, p in PAGES.items():
        html = render(fname, p)
        io.open(os.path.join(SITE, fname), "w", encoding="utf-8").write(clean_text(html, relative=True))
        made.append(fname)
    sizes = [os.path.getsize(os.path.join(SITE, f)) for f in made]
    print("generated %d guide pages" % len(made))
    for f, s in zip(made, sizes):
        print("  %-40s %5.1f KB" % (f, s / 1024))

    # --- sitemap (idempotent) -------------------------------------------------
    smap_path = os.path.join(SITE, "sitemap.xml")
    s = io.open(smap_path, encoding="utf-8").read()
    missing = [f for f in made if ("<loc>%s/%s</loc>" % (DOMAIN, f[:-5])) not in s]
    if missing:
        entries = "".join(
            '  <url>\n    <loc>%s/%s</loc>\n    <changefreq>monthly</changefreq>\n'
            '    <priority>%s</priority>\n  </url>\n' % (DOMAIN, f[:-5], PAGES[f]["priority"])
            for f in missing
        )
        assert "</urlset>" in s
        s = s.replace("</urlset>", entries + "</urlset>")
        io.open(smap_path, "w", encoding="utf-8").write(s)
        print("sitemap: +%d URLs (%d total)" % (len(missing), s.count("<loc>")))
    else:
        print("sitemap: already up to date")

    # --- homepage guides block (idempotent) -----------------------------------
    idx_path = os.path.join(SITE, "index.html")
    idx = io.open(idx_path, encoding="utf-8").read()
    anchor = '<h2>State guides \u2014 tenancy rules where you rent</h2>'
    assert idx.count(anchor) == 1, "state-guides anchor not found exactly once in index.html"
    if "Free guides \u2014 the questions Nigerians ask first" in idx:
        print("index: guides block already present")
    else:
        links = " \u00b7 ".join(
            '<a href="%s">%s</a>' % (f, navtitles[f]) for f in PAGES
        )
        block = ('<div class="seo-block">\n'
                 '    <h2>Free guides \u2014 the questions Nigerians ask first</h2>\n'
                 '    <p>Plain-English answers on Nigerian renting and small-business paperwork, '
                 'current for 2026:</p>\n'
                 '    <p style="line-height:2">%s</p>\n  </div>\n\n  ' % links)
        # insert immediately before the State guides block
        idx = idx.replace('<div class="seo-block">\n    ' + anchor, block + '<div class="seo-block">\n    ' + anchor, 1)
        io.open(idx_path, "w", encoding="utf-8").write(clean_text(idx, relative=True))
        print("index: guides block added (%+d bytes)" % (len(idx.encode()) - 0))

    print("done")


if __name__ == "__main__":
    sys.exit(main())
