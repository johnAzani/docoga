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
from urllib.parse import quote
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clean_urls import clean_text  # Cloudflare 307s /x.html → /x: canonicals, links and sitemap locs are bare
import sample_docs  # the sample documents (HTML + PDF from one source) — 🔒 docs/GROWTH.md, 3 Nov 2026
import freshness  # honest Updated dates, Article + BreadcrumbList, sitemap lastmod (docs/GROWTH.md, 3 Nov 2026)

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

def download_block(slug, make_hash, make_label):
    """Answer-first block under a sample: the PDF to download and the generator one tap away.
    HTML is the search destination (the PDFs are noindex in site/_headers); the PDF is the thing
    people asked for when they typed 'pdf' or 'download'."""
    return ('<p class="dl"><a class="cta" href="%s" download>Download this sample as PDF — free, no signup</a> '
            '<a class="cta alt" href="%s/#%s">%s</a></p>'
            % (sample_docs.pdf_url(slug), DOMAIN, make_hash, make_label))


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
clean PDF or a WhatsApp-ready copy — free. <a href="https://docoga.com.ng/#notice"><b>Make your quit notice free →</b></a></p>''' + download_block("quit-notice-letter-sample-nigeria", "notice", "Make yours with the dates filled in →")

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
    title="Tenancy Agreement in Nigeria: Format, Clauses + Free PDF",
    h1="Tenancy Agreement in Nigeria: the 2026 format, clause by clause",
    desc="The standard Nigerian tenancy agreement format: parties, term, rent, advance-rent limit, caution fee, notice period, covenants. Build one free in 2 minutes.",
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
    related=["tenancy-agreement-sample-nigeria.html", "notice-to-quit-nigeria.html", "caution-fee-nigeria.html",
             "rent-receipt-format-nigeria.html", "tenant-rights-nigeria.html",
             "shop-tenancy-agreement-nigeria.html"],
    priority="0.9",
)

# 1b ── tenancy agreement SAMPLE (3 Nov 2026, 🔒 docs/GROWTH.md first dive) ------------------
# Search Console: we rank only for the quit-notice cluster; "tenancy agreement sample in nigeria pdf
# free download" is served by Scribd uploads of private agreements and template farms. This page
# is the full sample, visible, with the state law beside it and the PDF one tap away. The clauses
# are the thirteen the generator writes — nothing on this page is wording the tool does not produce.
CLAUSE_NOTES = [
    ("Term", "the length of the tenancy and its start and end dates — a fixed term ends by itself; what follows is renewal, not holding over by default."),
    ("Rent", "the figure in numbers <i>and</i> words, the period it buys, and that it is paid in advance. In Lagos, s.4 of the Tenancy Law 2011 caps the advance at one year (yearly tenant) or six months (monthly tenant)."),
    ("Caution fee / deposit", "names the deposit as refundable and says what may be deducted — the clause that makes a refund arguable at the end."),
    ("Use of premises", "residential only; no illegal, immoral or hazardous use."),
    ("No assignment or subletting", "no handing the flat to someone else without the landlord's written consent."),
    ("Repairs and maintenance", "the usual split: landlord — roof and external walls; tenant — interior, fittings and damage by his own people."),
    ("Utilities", "who pays electricity, water and waste — the tenant, for what is consumed during the tenancy."),
    ("Quiet enjoyment", "the landlord's promise not to interfere while the tenant pays and keeps the covenants — the clause self-help breaches."),
    ("Alterations", "no structural changes without written consent."),
    ("Inspection", "the landlord may inspect on reasonable prior notice — not walk in."),
    ("Notice to quit", "the notice either side must give to end the tenancy. Where the agreement is silent the statutory minimums apply (table below); what you write here governs instead."),
    ("Renewal and rent review", "renewal and any new rent are by agreement — there is no automatic increase."),
    ("Governing law and jurisdiction", "the laws of Nigeria and the tenancy law of the state where the premises sit; disputes go to that state's courts."),
]

PAGES["tenancy-agreement-sample-nigeria.html"] = dict(
    published="2026-11-03", parent=("tenancy-agreement-nigeria.html", "Tenancy agreement in Nigeria"),
    title="Tenancy Agreement Sample in Nigeria: Full Text + Free PDF",
    h1="Tenancy agreement sample in Nigeria — the full text, clause by clause, free PDF",
    desc="A complete Nigerian tenancy agreement sample in full: 13 standard clauses, the state notice table, a free PDF (no signup), a generator that fills your names.",
    lead="This is a full residential tenancy agreement in the standard Nigerian form — the parties, the "
         "premises, thirteen covenants, signatures and witnesses — with square brackets where your details "
         "go. Read it here, download it as a PDF, or let the generator fill it in and give you a clean copy "
         "for any state in about two minutes. Below the sample: what each clause does, the rules that "
         "decide whether it holds up, and the notice periods the law applies when an agreement is silent.",
    widget=('<div class="box">\n<h2>The sample (residential, yearly tenant, Lagos wording)</h2>\n'
            + sample_docs.html_sample("tenancy-agreement-sample-nigeria")
            + download_block("tenancy-agreement-sample-nigeria", "agreement", "Fill it in free — any state →")
            + '\n</div>'),
    boxes=[
        ("What each clause does — and why it is there", ul([
            "<b>%s</b> — %s" % (name, note) for name, note in CLAUSE_NOTES
        ])),
        ("Before you sign: the three rules that decide whether it holds up", ul([
            "<b>The advance-rent cap.</b> Section 4 of the Lagos Tenancy Law 2011 makes it unlawful for a "
            "landlord or agent to demand or receive more than <b>one year's rent in advance</b> from a yearly "
            "tenant, or <b>six months</b> from a monthly tenant — and for the tenant to pay it.",
            "<b>Notice is what you write.</b> The statutory minimums apply only where the agreement is silent. "
            "If you want three months' notice on a yearly tenancy, clause 11 must say three months.",
            "<b>State law, not one national law.</b> Lagos runs the Tenancy Law 2011; the FCT the Recovery of "
            "Premises Act; Rivers, Edo, Kwara, Cross River, Kano and the rest their own recovery or rent-control "
            "laws. Clause 13 names the state; the state guides below give the sections. " + LAGOS_SCOPE,
        ])),
        ("Notice-to-quit minimums where the agreement is silent", NOTICE_TABLE),
        ("How this sample compares with what else is online", ul([
            "<b>Uploaded private agreements</b> (document-sharing sites) carry someone else's names, dates and "
            "terms — and often a clause that was wrong for <i>their</i> state. This sample is blank where it "
            "should be blank.",
            "<b>Generic \u201cNigeria-compliant\u201d templates</b> name no section of any law. Here the advance "
            "cap, the receipt duty and the notice ladder each carry their section, and the state guides carry "
            "the rest.",
            "<b>A lawyer-drafted agreement</b> (commonly \u20a620,000\u2013\u20a650,000) is the right choice for "
            "unusual terms, commercial premises or a dispute already brewing. For a standard flat, the standard "
            "form is what the lawyer would write.",
        ])),
    ],
    faq=[
        ("Is this tenancy agreement sample valid in Nigeria?",
         "A tenancy agreement becomes binding when it is properly filled, signed by both landlord and tenant, "
         "and witnessed. The sample follows standard Nigerian practice and names the state law in clause 13. "
         "DocOga is not a law firm and this is not legal advice."),
        ("Can I download the sample as a PDF for free?",
         "Yes — the PDF above is free and needs no signup. It carries the square brackets; the generator fills "
         "them in and gives you a clean copy, free with a small banner or without one on the Oga Pass."),
        ("Which state is the sample written for?",
         "The wording is the standard form used across Nigeria; the bracketed state is Lagos because the Lagos "
         "Tenancy Law 2011 is the most detailed. Change the state in clause 11 and clause 13 — or pick your state "
         "in the generator and it sets the notice period and the governing law for you."),
        ("Do I need a lawyer to use it?",
         "Not for a standard residential letting. Use a lawyer for commercial premises, unusual terms, a very "
         "high rent, or where a dispute is already under way."),
        ("Does the sample include a caution fee clause?",
         "Yes, clause 3 — it names the deposit as refundable and limits deductions to damage beyond normal wear "
         "and tear. Receipt the caution fee separately from the rent; the receipt guide explains why."),
    ],
    cta=("agreement", "Create your tenancy agreement free →"),
    related=["tenancy-agreement-nigeria.html", "notice-to-quit-nigeria.html",
             "rent-receipt-format-nigeria.html", "caution-fee-nigeria.html",
             "tenant-rights-nigeria.html", "rent-increase-notice-nigeria.html"],
    priority="0.9",
)

# 2 ── notice to quit: how many months ------------------------------------------
PAGES["notice-to-quit-nigeria.html"] = dict(
    # Snippet rewritten 29 Oct 2026 from Search Console: #1 for "quit notice" (56 impressions,
    # 0 clicks) — Nigerians searching it want a SAMPLE letter and "how many months"; the title
    # now says both inside 60 characters and the page opens with the sample itself.
    title="Quit Notice Nigeria: Sample Letter, Format, How Many Months",
    h1="Quit notice in Nigeria — sample letter, how to write it, and how many months",
    desc="Quit notice sample letter (Nigeria): copy the wording or make yours free in 2 minutes — PDF or WhatsApp. How many months: 1 week, 1, 3 or 6 months, then 7 days.",
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
    related=["demand-letter-rent-arrears-nigeria.html", "rent-increase-notice-nigeria.html",
             "tenancy-agreement-sample-nigeria.html", "tenancy-agreement-nigeria.html",
             "tenant-rights-nigeria.html", "caution-fee-nigeria.html"],
    priority="0.9",
)

# 3 ── caution fee: is it refundable --------------------------------------------
PAGES["caution-fee-nigeria.html"] = dict(
    title="Is the Caution Fee Refundable in Nigeria? (2026)",
    h1="Is the caution fee refundable in Nigeria? Yes — here is how to actually get it back",
    desc="A caution fee is a refundable security deposit, not a payment. What Nigerian law says, the clause to insist on, and how to claim the money back at move-out.",
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
    desc="The correct Nigerian rent receipt format: the five details Lagos law requires, the ₦100,000 fine for refusing a receipt, and a free generator — print or PDF.",
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
        ("A receipt that holds up looks like this (sample — download it as PDF)",
         sample_docs.html_sample("rent-receipt-sample-nigeria")
         + download_block("rent-receipt-sample-nigeria", "receipt", "Make yours with your details →")),
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
    related=["caution-fee-nigeria.html", "tenancy-agreement-sample-nigeria.html",
             "demand-letter-rent-arrears-nigeria.html", "tenant-rights-nigeria.html", "invoice-format-nigeria.html"],
    priority="0.8",
)

# 4b ── demand letter for unpaid rent (4 Nov 2026, 🔒 docs/GROWTH.md fourth dive) -----------------
# The generator has written demand letters since launch (renderDemand) and had no page. The Nigerian
# field for "demand letter for unpaid rent" is Genie AI's auto-generated outlines (no letter text, no
# section of any law) and foreign pages (US, UK, Kenya). Nobody puts the letter, the free PDF and the
# arrears rule of each state's law on one page. Every rule below is a cited fact on the Brain's shelf.
ARREARS_TABLE = '''<table>
<tr><th>State</th><th>What the law says about rent in arrears</th><th>Section</th></tr>
<tr><td><b>Lagos</b></td><td>A <b>monthly</b> tenant <b>six months</b> in arrears: the tenancy lapses and the court makes an order for possession and arrears on proof — <b>no quit notice needed</b>. A <b>quarterly or half-yearly</b> tenant <b>one year</b> in arrears: the same.</td><td>Tenancy Law 2011, s.13(2), s.13(3)</td></tr>
<tr><td><b>FCT Abuja</b></td><td><b>No arrears shortcut.</b> The Recovery of Premises Act has no equivalent of the Lagos rule — serve the notice to quit, then the seven-day Form E notice, then the court.</td><td>Recovery of Premises Act, s.7</td></tr>
<tr><td><b>Cross River</b></td><td>A <b>monthly</b> tenant <b>three months</b> in arrears: the tenancy determines and the court shall, on the landlord’s application, make an order for possession and arrears.</td><td>Rent Control and Recovery of Premises Law, s.15 proviso; Schedule 3(a)</td></tr>
<tr><td><b>Kwara</b></td><td>A <b>monthly</b> tenant <b>three months</b> in arrears: the same. And under Chapter L4, rent may be demanded or recovered <b>only once it is in arrear</b>.</td><td>Rent Control and Recovery of Residential Premises Law 1995, s.17 proviso; Landlord and Tenant Law, Ch. L4</td></tr>
<tr><td><b>Edo</b></td><td>Rent lawfully due and in arrear for <b>one month</b> after it became due is a ground on which the tribunal may order possession — the shortest trigger on the shelf.</td><td>Rent Control and Recovery of Residential Premises Edict 1977</td></tr>
<tr><td><b>Rivers</b></td><td>Rent is payable <b>in arrears</b> — at the end of the period — unless the parties agree otherwise. Advance rent is whatever the agreement says.</td><td>Landlord and Tenant Law, Cap. 75, s.75(1)</td></tr>
<tr><td><b>Anambra · Enugu · Kano</b></td><td>No arrears shortcut verified. After the quit notice expires, a further written notice of the owner’s intention to apply to court of <b>not less than seven clear days</b> — and it cannot be issued before the quit notice expires.</td><td>Landlord and Tenant Law (Anambra, Enugu); Kano recovery law</td></tr>
</table>
<p class="muted">Where a state is not in the table, the ordinary rule applies: the demand letter, then the notice to quit your agreement or the state law requires, then the seven-day notice, then the court. Every section here is on the <a href="%s/tenancy-law-lagos">state tenancy-law pages</a>, with the date it was checked.</p>''' % DOMAIN

PAGES["demand-letter-rent-arrears-nigeria.html"] = dict(
    published="2026-11-04", parent=("notice-to-quit-nigeria.html", "Notice to quit in Nigeria"),
    title="Demand Letter for Unpaid Rent in Nigeria: Sample + Free PDF",
    h1="Demand letter for unpaid rent in Nigeria \u2014 the sample letter, free PDF, and the arrears rule in your state",
    desc="Demand letter for rent arrears in Nigeria, in full and free to download: the sum in words, due date, days to pay, what follows — and your state\u2019s arrears rule.",
    lead="Before a quit notice, before a lawyer, before anything the court will look at, there is one "
         "letter: the written demand for the rent that fell due and was not paid. This is that letter in "
         "the standard Nigerian form \u2014 the sum in figures and words, the period it covers, the date it "
         "fell due, the days given to pay and what follows if it is ignored \u2014 with square brackets where "
         "your details go. Read it, download it, or let the generator fill it in and give you a clean copy "
         "in two minutes. Below the letter: what each line is for, the arrears rule in each state\u2019s law "
         "(some let a tenancy lapse on arrears with no quit notice at all; Abuja does not), and what a "
         "tenant who receives one should do.",
    widget=('<div class="box">\n<h2>The sample (landlord to tenant, rent in arrears, Lagos premises)</h2>\n'
            + sample_docs.html_sample("demand-letter-rent-arrears-nigeria")
            + download_block("demand-letter-rent-arrears-nigeria", "demand", "Fill it in free \u2014 any debt, any state \u2192")
            + '\n</div>'),
    boxes=[
        ("What each line of the letter is for", ul([
            "<b>The sum, in figures and in words.</b> A demand that names a different figure in the heading and "
            "the body is the first thing a tenant\u2019s lawyer attacks. The generator writes both from one number.",
            "<b>What the money is for and when it fell due.</b> \u201cThe rent of \u20a6\u2026 for the period \u2026 in respect of \u2026, "
            "which fell due on \u2026\u201d \u2014 the period and the due date are what turn a complaint into arrears that a "
            "court can count.",
            "<b>The demand itself.</b> One sentence, in capitals, asking for immediate payment of the amount "
            "outstanding \u2014 the sentence the court reads as the demand.",
            "<b>The days to pay.</b> Fourteen days is the usual figure; seven is common where the agreement says "
            "rent is due on a fixed day. The letter must give <i>a</i> period \u2014 a demand with no deadline is a "
            "reminder.",
            "<b>What follows.</b> Proceedings for the debt, interest and costs \u2014 the recovery of the <i>money</i>. "
            "Recovering the <i>premises</i> is a separate ladder: the notice to quit, the seven-day notice, the "
            "court order. The letter says so and promises nothing it cannot do.",
            "<b>Who signs.</b> The landlord, or an agent or solicitor <i>for</i> the landlord. Keep a copy and proof "
            "of delivery \u2014 a WhatsApp photo of the signed letter with the tenant\u2019s reply is proof.",
        ])),
        ("Rent in arrears, state by state \u2014 when the law lets a tenancy lapse without a quit notice", ARREARS_TABLE),
        ("The ladder after the letter (and the step that is an offence)", ul([
            "<b>1. The demand letter</b> \u2014 this page. It recovers the money, or it becomes the first exhibit.",
            "<b>2. The notice to quit</b> \u2014 the period your agreement names or, where it is silent, the state "
            "minimum (<a href=\"%s/notice-to-quit-nigeria\">one week to six months, by tenancy type</a>). In Lagos, "
            "Cross River and Kwara the arrears rules in the table skip this step once the arrears reach the "
            "statutory period; in the FCT they never do." % DOMAIN,
            "<b>3. The seven-day notice</b> of the owner\u2019s intention to apply to court to recover possession "
            "(Form E in the FCT, Edo, Cross River and Kwara; Form TL5 in Lagos) \u2014 and it cannot be served "
            "before the quit notice expires.",
            "<b>4. The court order.</b> A landlord may not resort to self-help: no changed locks, no removed roof, "
            "no thugs. In the FCT, once the seven days expire the occupier is a statutory tenant removable only "
            "by a lawful court order; in Lagos, forcible ejection is an offence under s.44 of the Tenancy Law "
            "2011 \u2014 fine up to \u20a6250,000 or up to six months\u2019 imprisonment.",
        ])),
        ("If you are the tenant who received one", ul([
            "<b>Check the figure against your receipts.</b> In a possession claim built on arrears, the tenant\u2019s "
            "receipts are the answer \u2014 in Lagos a landlord who did not issue one has committed an offence "
            "(s.5(3), fine \u20a6100,000). If you paid and have no receipt, your bank transfer narration and your "
            "messages are the next best evidence.",
            "<b>A demand letter is not an eviction.</b> It does not end the tenancy and it does not shorten the "
            "notice you are owed. Reply in writing \u2014 pay, propose dates, or dispute the figure \u2014 and keep "
            "the reply.",
            "<b>In Rivers and Kwara, check when rent is even due.</b> Rent is payable in arrears unless your "
            "agreement says otherwise; a demand for rent that is not yet due is not a demand for arrears.",
            "<b>Watch the statutory periods.</b> Six months\u2019 arrears for a monthly tenant in Lagos, three in "
            "Cross River and Kwara, one in Edo: at those points the law stops requiring a quit notice. Pay "
            "something, in writing, before you reach them.",
        ])),
        ("How this sample compares with what else is online", ul([
            "<b>Template catalogues</b> list what a \u201cletter for non-payment of rent\u201d should contain and "
            "sell the text. This page shows the whole letter and gives it away.",
            "<b>Foreign templates</b> (US \u201cpay or quit\u201d notices, UK arrears letters, Kenyan samples) cite "
            "laws that do not run here and periods no Nigerian court recognises. Every section on this page "
            "is a Nigerian section, with its state.",
            "<b>A solicitor\u2019s letter</b> carries the firm\u2019s letterhead and, in practice, more weight with a "
            "difficult tenant. For the first demand, the landlord\u2019s own letter in this form is what the "
            "solicitor would send \u2014 and it costs nothing.",
        ])),
    ],
    faq=[
        ("How do I write a demand letter for unpaid rent in Nigeria?",
         "Name the premises, the period the rent covers and the date it fell due; state the sum in figures and "
         "words; demand immediate payment; give a number of days (fourteen is usual); say that proceedings for "
         "the debt, interest and costs follow if it is not paid; sign and date it, and keep proof of delivery. "
         "The sample above is that letter; the generator fills it in free."),
        ("Is a demand letter the same as a notice to quit?",
         "No. A demand letter asks for money and records that it was asked for. A notice to quit ends the "
         "tenancy after the period your agreement or the state law requires. One can follow the other; neither "
         "replaces the other \u2014 except where a state\u2019s arrears rule (Lagos s.13(2)\u2013(3), the Cross River "
         "and Kwara provisos) lets the tenancy lapse on the arrears themselves."),
        ("How many days should I give the tenant to pay?",
         "The letter must give a period; fourteen days is the common figure and seven is used where the agreement "
         "fixes a rent day. The period in the letter does not shorten any notice period the tenancy itself "
         "requires."),
        ("Can I lock the tenant out if the demand is ignored?",
         "No. Self-help is unlawful in every state on this page \u2014 in Lagos it is an offence under s.44 of the "
         "Tenancy Law 2011. The route is the notice to quit (where still required), the seven-day notice, and a "
         "court order for possession and arrears."),
        ("Does a demand letter need a lawyer?",
         "Not for the first demand on a residential tenancy. A solicitor\u2019s letter adds weight and is the right "
         "step when the sum is large, the tenant disputes it, or the court is the next stop. DocOga is not a law "
         "firm and this page is general information, not legal advice."),
        ("Can I download the demand letter as a PDF for free?",
         "Yes \u2014 the PDF above is free and needs no signup. It carries the square brackets; the generator fills "
         "them in and gives you a clean copy, free with a small banner or without one on the Oga Pass."),
    ],
    cta=("demand", "Create your demand letter free \u2192"),
    related=["notice-to-quit-nigeria.html", "rent-receipt-format-nigeria.html", "tenancy-agreement-sample-nigeria.html",
             "tenant-rights-nigeria.html", "rent-increase-notice-nigeria.html"],
    priority="0.8",
)

# 4b ── rent increase notice (5 Nov 2026, 🔒 docs/GROWTH.md fifth dive) -----------------------
# The field for "rent increase notice/letter Nigeria" is a marketplace blog (mushrooms.ng, 20 Oct
# 2026), a listings blog (apartments.ng) and a paid Selar file; the law explainers that rank
# contradict each other ("six months' notice for an increase", "three months", "one month") and all
# are reading the quit-notice periods into a different question. Nobody has the generator, the
# sample and the sections on one page. Every section below is from tools/state_law_data.py.
INCREASE_TABLE = '''<table>
<tr><th>State</th><th>What the law actually says about a rent increase</th><th>Section</th></tr>
<tr><td><b>Lagos</b></td><td><b>No percentage cap and no fixed notice period for an increase.</b> A sitting tenant who thinks an increase unreasonable applies to the court on Form TL11; the court weighs the general level of rents in the locality, the evidence and any special circumstances, and may order the increase changed to a stated figure (Form TL13). It is <b>unlawful to eject the tenant while that application is pending</b>. If the tenant refuses and nothing is agreed, the landlord\u2019s only lawful route is the notice to quit the tenancy requires (yearly tenant: six months), the seven-day notice, then the court. <b>Two limits nobody prints:</b> the 2011 Law \u2014 and with it s.37 \u2014 does not apply in <b>Apapa, Ikeja GRA, Ikoyi and Victoria Island</b> (s.1(3)); and an increase that arrives bundled with a demand for two years upfront breaks s.4 \u2014 a sitting yearly tenant may not be asked for more than one year in advance (fine \u20a6100,000, s.4(5)), whatever the new figure.</td><td>Tenancy Law 2011, s.37, s.37(4); s.13(1); s.1(3); s.4</td></tr>
<tr><td><b>Enugu</b></td><td><b>The one verified statutory cap in Nigeria.</b> Rent \u201cmay be reviewed by the parties after every second anniversary of the tenancy \u2026 provided that the difference between the new and the existing rent shall not exceed 15% of the existing rent\u201d. Three conditions: by agreement (a unilateral increase is ineffective), not before the second anniversary, not more than 15%. \u20a6400,000 let from 1 January 2025 cannot be reviewed before 1 January 2027 and may not go above \u20a6460,000.</td><td>Landlord and Tenant (Amendment) Law 2008, s.3(b)</td></tr>
<tr><td><b>Abuja (FCT)</b></td><td>No FCT equivalent of the Lagos s.37 application and no percentage cap. The tenancy agreement governs; where it is silent, the notice required is a matter of negotiation and, ultimately, of the court. The 2026 FCT Advance Rent Bill (second reading 4 Nov 2026) proposes <b>no</b> rent ceiling and no limit on increases.</td><td>no provision; HB.2839 (a bill)</td></tr>
<tr><td><b>Kwara</b></td><td>Shifting a burden from the landlord to the tenant (a repair, a levy) is treated as an increase in rent whether or not the periodic sum changes.</td><td>s.7</td></tr>
<tr><td><b>Rivers \u00b7 Anambra \u00b7 Kano</b></td><td>No percentage cap; no verified equivalent of the Lagos s.37 application; no tribunal to apply to. Rent increases are governed by the tenancy agreement. Anambra\u2019s neighbour Enugu has a cap \u2014 that is Enugu\u2019s law, not Anambra\u2019s.</td><td>not verified / no mechanism found</td></tr>
</table>
<p class="muted">Everywhere: a rent increase is an <b>offer for the next term, not an order for this one</b> \u2014 \u201crent increment must be supported by an agreement\u201d (<i>Jovinco Nigeria Ltd v. Ibeozimako</i> (2014) LPELR-23599(CA); <i>Cobra Ltd v. Omole Estate</i> (2000) 1 NWLR (Pt. 655) 1). Refusing it is not arrears; the tenancy continues on its present terms until it is lawfully determined. Sections and the date each was checked are on the <a href="DOMAIN/tenancy-law-lagos">state tenancy-law pages</a>.</p>'''.replace("DOMAIN/", DOMAIN + "/")

PAGES["rent-increase-notice-nigeria.html"] = dict(
    published="2026-11-05", parent=("tenant-rights-nigeria.html", "Tenant rights in Nigeria"),
    title="Rent Increase Notice Nigeria: Sample + Tenant\u2019s Reply (PDF)",
    h1="Rent increase notice in Nigeria \u2014 the sample letter, free PDF, the generator, and the section of the law in your state",
    desc="Notice of rent review for Nigeria plus the tenant\u2019s reply (accept, decline, counter-offer), both free to download — Lagos s.37, the Enugu 15% cap, the FCT.",
    lead="A rent increase in Nigeria is an offer for the next term, not an order for this one. The letter "
         "that does it properly says the current rent stands until the term ends, names the new rent in "
         "figures and words, asks for an answer in writing, and \u2014 this is the part nobody else prints \u2014 "
         "says what the law of your state actually adds: in Lagos, the tenant\u2019s s.37 right to have the "
         "court call it unreasonable; in Enugu, the 15% cap and the two-year rule; in the FCT and most "
         "states, that the agreement governs. Read it, download it, or let the generator write it for "
         "your state in two minutes \u2014 it will not let an Enugu notice call a 50% rise lawful. The same tool "
         "writes the <b>tenant\u2019s reply</b>: accept, decline, or counter-offer, with the s.37 right reserved. "
         "Below: the state table, the honest answer on \u201chow much notice\u201d, and what a tenant who "
         "receives one should do \u2014 with the reply letter to send.",
    widget=('<div class="box">\n<h2>The sample (landlord to a yearly tenant, Lagos premises)</h2>\n'
            + sample_docs.html_sample("rent-increase-notice-nigeria")
            + download_block("rent-increase-notice-nigeria", "rentreview", "Write it for your state free \u2192")
            + '\n</div>'),
    boxes=[
        ("What the law actually says, state by state", INCREASE_TABLE),
        ("How much notice does a rent increase need? The honest answer", ul([
            "<b>No state statute we have read fixes a notice period for a rent increase.</b> The figures pages "
            "quote \u2014 one month, three months, six months \u2014 are the <a href=\"%s/notice-to-quit-nigeria\">notice-to-"
            "quit periods</a> (Lagos Tenancy Law 2011, s.13(1)), which answer a different question." % DOMAIN,
            "<b>Why those periods still matter.</b> If the tenant does not accept the new rent, the landlord cannot "
            "impose it; the only lawful route to a new rent with a new tenant is to determine the tenancy with "
            "the notice it requires \u2014 six months for a yearly tenant in Lagos \u2014 then the seven-day notice, then "
            "the court. A landlord who wants a higher rent from 1 January must therefore be talking by July.",
            "<b>The agreement comes first.</b> A rent-review clause (\u201cnot less than three months\u2019 written notice "
            "before the end of the term; by agreement\u201d) binds both sides. The <a href=\"%s/#agreement\">tenancy "
            "agreement generator</a> writes one." % DOMAIN,
            "<b>Enugu is the exception in the other direction:</b> not a notice period but a timing rule \u2014 no review "
            "before every second anniversary \u2014 and a ceiling of 15%.",
        ])),
        ("What each line of the notice does", ul([
            "<b>The current term and rent.</b> \u201cYour current yearly tenancy runs to [date] at a rent of \u20a6\u2026\u201d \u2014 "
            "it fixes what is not changing, which is the first thing a tenant\u2019s lawyer checks.",
            "<b>The proposal.</b> The new rent in figures and words, the date it would start (the day after the term "
            "ends), the change in naira and percent, and the reason if there is one.",
            "<b>The sentence that keeps it lawful.</b> \u201cThis is a proposal for the next term and not a demand for the "
            "present one \u2026 the new rent takes effect only on your written acceptance.\u201d A notice that says "
            "\u201ceffective immediately\u201d mid-term is the one the cases strike down.",
            "<b>The answer date, and what silence means.</b> No agreement does not end the tenancy; it continues on its "
            "present terms until lawfully determined. The notice says so instead of implying an eviction.",
            "<b>The state paragraph.</b> Lagos: s.37 and s.37(4). Enugu: s.3(b) and \u2014 if the figure is over the cap \u2014 "
            "a line saying it must come down before the notice is served. FCT and others: the agreement governs.",
        ])),
        ("If you are the tenant who received one \u2014 and the reply to send", '<p>Reply in writing, say what you '
         'will and will not agree, keep paying the current rent, and reserve the right your state gives you. The '
         'generator writes this letter when you choose <b>\u201cWho is writing? \u2014 the tenant\u201d</b>; it '
         'will not write an acceptance of an Enugu figure above the 15% cap.</p>'
         + sample_docs.html_sample("rent-increase-reply-nigeria")
         + download_block("rent-increase-reply-nigeria", "rentreview", "Write your reply for your state free \u2192")
         + ul([
            "<b>You do not have to accept it, and refusing is not arrears.</b> Keep paying the current rent on time, with "
            "receipts \u2014 in Lagos a landlord who refuses one commits an offence (s.5(3), \u20a6100,000).",
            "<b>Reply in writing.</b> Acknowledge, say whether you accept, counter-offer if you wish, and ask for the "
            "landlord\u2019s answer in writing. A WhatsApp message is writing; keep it.",
            "<b>In Lagos, the s.37 application</b> (Form TL11) asks the court to declare the increase unreasonable; no "
            "ejection is lawful while it is pending (s.37(4)). Bring your receipts and evidence of rents nearby \u2014 "
            "two or three comparable rents on your street, dated, is what the court measures the increase against. "
            "Not in Apapa, Ikeja GRA, Ikoyi or Victoria Island, where the 2011 Law does not apply (s.1(3)).",
            "<b>\u201cNot more than 20%\u201d is a motion, not a law.</b> The House of Representatives urged a 20% ceiling on "
            "23 October 2025; no statute followed. Do not quote it to a landlord \u2014 quote s.37 (Lagos) or s.3(b) (Enugu).",
            "<b>In Enugu, do the arithmetic.</b> Before the second anniversary, or more than 15% above the existing "
            "rent, the increase is unlawful and a court will not enforce the figure.",
            "<b>Self-help is an offence everywhere.</b> No locks changed, no roof removed, no thugs; in Lagos s.44 of "
            "the Tenancy Law 2011 \u2014 fine up to \u20a6250,000 or up to six months\u2019 imprisonment.",
        ])),
        ("How this compares with what else is online", ul([
            "<b>Marketplace and listings blogs</b> publish a copy-and-paste letter with \u201ceffective immediately\u201d or a "
            "notice period borrowed from the quit-notice table; none swaps the legal paragraph by state, and none "
            "stops you writing an unlawful Enugu figure.",
            "<b>Paid files</b> sell the same two paragraphs as a download. This page shows the whole notice, gives the "
            "PDF away, and the generator writes a clean copy.",
            "<b>Law explainers</b> that rank for the question disagree with each other on \u201chow much notice\u201d because the "
            "statutes do not say; this page says that, and cites the sections that do exist.",
            "<b>Letter makers</b> now exist elsewhere, and the good ones are free too. The difference is what the letter "
            "knows: ours changes its legal paragraph by state, refuses an Enugu figure above the cap, prints the \u201creceived "
            "by\u201d line a court asks for, and carries no sample names that were never real people.",
        ])),
    ],
    faq=[
        ("Can a landlord increase rent in the middle of a tenancy in Nigeria?",
         "Not unilaterally. A rent increase takes effect only by agreement \u2014 the cases call a unilateral increase "
         "ineffective \u2014 so an increase properly belongs to the next term, proposed in writing before the current one "
         "ends. A rent-review clause in the agreement can allow a review on notice during a longer term."),
        ("How much notice must a landlord give before increasing rent?",
         "No Nigerian state statute we have read fixes one. The agreement governs; the notice-to-quit periods (one "
         "month, three months, six months in Lagos by tenancy type) are what the landlord needs if the tenant refuses "
         "and the tenancy is to be ended instead. Giving the proposal several months before renewal is both practical "
         "and the only way a yearly tenancy can lawfully be re-let at a new rent on time."),
        ("Is there a percentage limit on rent increases in Nigeria?",
         "Only one that we have verified: Enugu State, where the Landlord and Tenant (Amendment) Law 2008 (s.3(b)) "
         "allows a review only after every second anniversary and caps the difference at 15% of the existing rent. "
         "Lagos has no cap but gives the tenant the s.37 application; the FCT, Rivers, Anambra and Kano have neither."),
        ("Is it true a landlord cannot increase rent by more than 20%?",
         "No. The 20% figure is a House of Representatives motion of 23 October 2025 urging that increases be kept "
         "within 20% of the existing rent \u2014 a resolution, not a law; it binds nobody. The FCT bill at second "
         "reading (HB.2839, 4 November 2026) caps advance rent at twelve months and proposes no limit on increases. "
         "Quote a section to your landlord, not a headline: in Lagos that is s.37; in Enugu, s.3(b)."),
        ("What should a Lagos tenant gather before challenging an increase under s.37?",
         "The court\u2019s first measure is the general level of rents for comparable premises in the locality, so "
         "note two or three current rents for similar flats on nearby streets (listings, neighbours, an agent\u2019s "
         "quote) with the date, keep every rent receipt, and keep the landlord\u2019s notice and your written reply. "
         "The DocOga <a href=\"%s/rent-index-nigeria\">Rent Monitor</a> shows the asking rents it counts each week, "
         "by city and bedroom count, which is a starting point \u2014 not evidence on its own." % DOMAIN),
        ("What happens if the tenant refuses the new rent?",
         "The tenancy continues on its present terms. The landlord may negotiate, or determine the tenancy with the "
         "notice it requires and the court process; the landlord may not treat the refusal as arrears or lock the "
         "tenant out."),
        ("Can I download the rent increase notice and the tenant\u2019s reply as PDFs for free?",
         "Yes \u2014 both PDFs above are free and need no signup. They carry the square brackets; the generator fills them "
         "in for your state and gives you a clean copy, free with a small banner or without one on the Oga Pass."),
        ("How should a tenant reply to a rent increase letter?",
         "In writing, before the date the landlord asked for: refer to the notice by its date, say whether you accept, "
         "decline or counter-offer (with your figure), state that the tenancy continues on its present terms until a "
         "rent is agreed and that the letter is not a notice to quit, and \u2014 in Lagos \u2014 reserve the s.37 right "
         "to ask the court to declare the increase unreasonable. Keep paying the current rent and keep the receipts."),
        ("Does the notice need a lawyer?",
         "Not for a residential renewal. A solicitor is the right step when the sum is large, the tenant disputes it, "
         "or a Lagos s.37 application is coming. DocOga is not a law firm and this page is general information, not "
         "legal advice."),
    ],
    cta=("rentreview", "Write your rent review notice free \u2192"),
    related=["tenant-rights-nigeria.html", "notice-to-quit-nigeria.html", "tenancy-agreement-sample-nigeria.html",
             "demand-letter-rent-arrears-nigeria.html"],
    priority="0.8",
)

# 4c ── employment contract sample (12 Nov 2026, money-only build; docs/GROWTH.md §4) --------------
# The employment generator is a paid tool with no search page in front of it. Every floor quoted
# below was read from the enrolled Labour Act, Cap L1 LFN 2004 (ss.7, 9, 11, 13, 15, 16, 18, 91);
# nothing here is from a blog. The sample is tools/sample_docs.EMPLOYMENT_CONTRACT — the same eight
# clauses, in the same order, that renderEmployment writes.
LABOUR_FLOORS = '''<table>
<tr><th>Term in the contract</th><th>The statutory floor (Labour Act, Cap L1 LFN 2004)</th><th>Section</th></tr>
<tr><td><b>Written terms</b></td><td>Within <b>three months</b> of engagement the employer gives the worker a written statement of: the employer\u2019s name; the worker\u2019s name and address and the place and date of engagement; the nature of the employment; the expiry date of a fixed-term contract; the notice period; wages and how and how often they are paid; hours of work; holidays and holiday pay; sickness and sick pay; and any special conditions. A signed contract that carries all of these is that statement.</td><td>s.7(1)</td></tr>
<tr><td><b>Age</b></td><td>No one under <b>16</b> may be employed under a contract of this kind.</td><td>s.9(3)</td></tr>
<tr><td><b>Notice</b></td><td>Either side may end the contract on notice of at least <b>one day</b> (up to three months\u2019 service), <b>one week</b> (over three months, under two years), <b>two weeks</b> (two to five years) or <b>one month</b> (five years and more). Notice of a week or more must be in writing; either side may pay wages in lieu instead. The contract may give longer notice \u2014 never shorter.</td><td>s.11(2), (3), (6)</td></tr>
<tr><td><b>Hours</b></td><td>Normal hours are fixed by the agreement, by collective bargaining or by a wages board \u2014 the Act does not itself set a weekly maximum, so the hours clause is the whole of the rule.</td><td>s.13(1)</td></tr>
<tr><td><b>Pay day</b></td><td>Wages are due at the end of each pay period, and a pay period may not be longer than <b>one month</b>.</td><td>s.15</td></tr>
<tr><td><b>Sick leave</b></td><td>Wages are payable for up to <b>twelve working days</b> of absence in a calendar year, on a registered medical practitioner\u2019s certificate.</td><td>s.16</td></tr>
<tr><td><b>Annual leave</b></td><td>After <b>twelve months\u2019</b> continuous service, at least <b>six working days</b> of holiday with full pay (twelve for a worker under sixteen). The holiday may not be bought out with cash while the contract runs.</td><td>s.18(1), (3)</td></tr>
<tr><td><b>Who the floors protect</b></td><td>The Act\u2019s \u201cworker\u201d excludes staff in administrative, executive, technical or professional roles, members of the employer\u2019s family and agents who work outside the employer\u2019s premises on commission. For them the contract governs \u2014 which is why it should be written, and written clearly.</td><td>s.91(1)</td></tr>
</table>
<p class="muted">Outside the Labour Act: the national minimum wage is <b>\u20a670,000 a month</b> (National Minimum Wage (Amendment) Act 2024; the Minimum Wage Act exempts establishments employing fewer than 25 people and part-time or commission work); PAYE is deducted from each salary and remitted to the tax authority of the state where the employee lives; where the Pension Reform Act 2014 applies, the employer contributes at least 10% and the employee 8% of monthly emoluments.</p>'''

PAGES["employment-contract-sample-nigeria.html"] = dict(
    published="2026-11-12", parent=("invoice-format-nigeria.html", "Small-business paperwork"),
    title="Employment Contract Sample Nigeria: Free PDF + Template",
    h1="Employment contract sample for Nigeria \u2014 the full contract, free PDF, and the Labour Act floors behind every clause",
    desc="Employment contract sample for Nigeria, in full and free to download: eight clauses \u2014 probation, notice, leave, pay \u2014 each checked against the Labour Act.",
    lead="A shop, a salon, a clinic, a small office: the first employee arrives and someone asks for \u201cthe "
         "contract\u201d. This is that contract in the standard Nigerian form \u2014 position and duties, start date and "
         "probation, salary and pay day, hours and place of work, leave and sick leave, confidentiality, notice, "
         "governing law \u2014 with square brackets where your details go. Read it, download the PDF, or let the "
         "generator fill it in and give you a clean copy in two minutes. Below the sample: what each clause is "
         "for, and the one thing the templates online leave out \u2014 the floors the Labour Act sets under a "
         "worker\u2019s notice, leave, sick pay and pay day, with the section for each.",
    widget=('<div class="box">\n<h2>The sample (a small business hiring a sales assistant, Lagos)</h2>\n'
            + sample_docs.html_sample("employment-contract-sample-nigeria")
            + download_block("employment-contract-sample-nigeria", "employment", "Fill it in free \u2014 any role, any state \u2192")
            + '\n</div>'),
    boxes=[
        ("What each clause is for", ul([
            "<b>1. Position and duties.</b> The job title and a short list of what the job is. Write the list: "
            "a dispute about \u201cthat is not my work\u201d is settled by this clause, and the Act requires the nature of "
            "the employment to be in writing (s.7(1)(c)).",
            "<b>2. Commencement and probation.</b> The start date fixes everything else \u2014 the notice ladder, the "
            "twelve months to the first holiday, the three months for the written statement. Probation is not in "
            "the Act; it is a contractual period with a shorter notice, and it must be confirmed in writing when it "
            "ends or it simply runs on.",
            "<b>3. Remuneration.</b> The salary in figures and words, the pay day, and the deductions \u2014 PAYE and, "
            "where the pension scheme applies, the employee\u2019s 8%. A pay period longer than a month needs the "
            "State Authority\u2019s consent (s.9(4)); the 28th of each month is inside the rule.",
            "<b>4. Hours and place of work.</b> The Act leaves normal hours to the agreement (s.13(1)), so the days "
            "and times in this clause are the rule for this job. The place of work is where the worker must report; "
            "the \u201cother place\u201d sentence covers a second branch without a new contract.",
            "<b>5. Annual leave and sick leave.</b> Fifteen working days is the common private-sector figure and "
            "sits above the Act\u2019s six (s.18). The sick-leave sentence is the one most templates omit \u2014 s.7(1)(g) "
            "requires the terms on sickness and sick pay to be stated, and s.16 sets the twelve-day floor.",
            "<b>6. Confidentiality.</b> Customer lists, prices, suppliers, takings. The clause survives the end of "
            "the employment; it is not a non-compete, which Nigerian courts read narrowly.",
            "<b>7. Termination and notice.</b> One month each way after probation \u2014 longer than any step of the "
            "s.11 ladder, so lawful for every length of service \u2014 with payment in lieu allowed (s.11(6)). Summary "
            "dismissal is reserved for gross misconduct; a poor sales month is not gross misconduct.",
            "<b>8. Governing law.</b> Nigerian law, which means the Labour Act, the National Industrial Court for "
            "disputes, and the state\u2019s PAYE authority.",
        ])),
        ("The Labour Act floors, clause by clause", LABOUR_FLOORS),
        ("Before the contract is signed \u2014 the employer\u2019s checklist", ul([
            "<b>Two copies, both signed,</b> one for each side. The Act wants the worker to have the written terms "
            "within three months (s.7(1)); handing over a signed copy on day one is the simplest proof.",
            "<b>Check the age.</b> Nobody under sixteen under a contract of this kind (s.9(3)); keep a copy of the "
            "ID you saw.",
            "<b>Register for PAYE</b> with the tax authority of the state where the employee lives, and keep the "
            "payslips \u2014 the deductions clause is only lawful if the money actually reaches the authority.",
            "<b>Decide the pension question early.</b> Under the Pension Reform Act 2014 the employer\u2019s share is "
            "at least 10% of monthly emoluments on top of salary; a salary quoted without it is a salary that "
            "will be renegotiated.",
            "<b>Keep the leave record.</b> Holiday may not be paid out in cash while the contract runs (s.18(3)), "
            "so an untaken year carries forward in the record rather than disappearing.",
        ])),
        ("If you are the employee signing it", ul([
            "<b>Count the notice both ways.</b> The notice you must give is the notice you are owed; a contract that "
            "asks you for a month and gives you a week is lopsided, and for a Labour Act worker the employer\u2019s "
            "week is only lawful for service under two years (s.11(2)).",
            "<b>Look for the leave and sick-leave sentences.</b> If they are missing, ask for them in writing before "
            "signing \u2014 the Act requires them to be stated (s.7(1)(g)).",
            "<b>Deductions must be named.</b> PAYE and pension are lawful; \u201cshortages\u201d, \u201cbreakages\u201d and "
            "unexplained fines are not deductions a contract can authorise in advance.",
            "<b>Keep your copy.</b> At the National Industrial Court, the signed contract is the first exhibit \u2014 "
            "for both sides.",
        ])),
        ("How this sample compares with what else is online", ul([
            "<b>Template catalogues</b> describe what an employment contract \u201cshould contain\u201d and sell the "
            "document. This page shows the whole contract and gives it away.",
            "<b>Foreign templates</b> (US at-will letters, UK statements of particulars, South African contracts) "
            "cite laws that do not run here. Every section on this page is a section of the Labour Act, Cap L1 "
            "LFN 2004, read from the enrolled text \u2014 not from a summary of it.",
            "<b>A lawyer\u2019s contract</b> adds restrictive covenants, intellectual-property clauses and a staff "
            "handbook, and is the right step for a senior or technical hire the Act\u2019s floors do not protect. For "
            "the first shop assistant, cashier or receptionist, this is the contract the lawyer would start from.",
        ])),
    ],
    faq=[
        ("How do I write an employment contract in Nigeria?",
         "Name the employer and the employee; state the position and duties, the start date and any probation, the "
         "salary in figures and words with the pay day and deductions, the hours and place of work, annual leave and "
         "sick leave, confidentiality, the notice each side must give, and the governing law; both sign, each keeps "
         "a copy. The sample above is that contract; the generator fills it in."),
        ("Is a written contract compulsory?",
         "For a worker the Labour Act covers, the employer must give a written statement of the main terms within "
         "three months of the start (s.7(1)). A signed contract that carries all of those terms satisfies the "
         "section. For staff the Act\u2019s definition of \u201cworker\u201d excludes \u2014 administrative, executive, technical "
         "and professional roles \u2014 the contract is not required by the Act, but it is the only thing that then "
         "governs the job."),
        ("What is the minimum notice period in Nigeria?",
         "Under s.11(2) of the Labour Act: one day for service up to three months, one week for over three months "
         "but under two years, two weeks for two to five years, and one month for five years or more \u2014 and notice "
         "of a week or more must be written. A contract may give longer notice; this sample gives one month either "
         "way after probation."),
        ("How many days of annual leave does the law give?",
         "At least six working days with full pay after twelve months\u2019 continuous service (s.18(1)); most private "
         "employers give more, and the sample gives fifteen. Sick leave is separate: up to twelve working days a "
         "year with a medical certificate (s.16)."),
        ("Can I put a three-month probation in the contract?",
         "Yes. Probation is a contractual term, not a statutory one; the sample uses three months with one week\u2019s "
         "notice during it. For a Labour Act worker in the first three months the statutory floor is one day, so "
         "a week is above it. Confirm the employee in writing when probation ends."),
        ("Can I download the employment contract as a PDF for free?",
         "Yes \u2014 the PDF above is free and needs no signup. It carries the square brackets; the generator fills "
         "them in and gives you a clean copy, free with a small banner or without one on the Oga Pass. DocOga is "
         "not a law firm and this page is general information, not legal advice."),
    ],
    cta=("employment", "Create your employment contract free \u2192"),
    related=["query-letter-sample-nigeria.html", "payslip-format-nigeria.html", "invoice-format-nigeria.html",
             "shop-tenancy-agreement-nigeria.html", "tenancy-agreement-sample-nigeria.html"],
    priority="0.8",
)

# 4d ── query letter + warning letter (12 Nov 2026, second money-only build; docs/GROWTH.md §4) -----
# "Query" is the Nigerian word for the letter that asks an employee to explain in writing before any
# warning; "how to reply a query" is what the employee searches. The warning tool now writes the
# query too (renderQueryLetter). The law quoted is the Labour Act, Cap L1 LFN 2004, read from the
# enrolled text — s.5(1), s.5(7), s.7(1)(h), s.11(2), s.11(5), s.11(6), s.11(7), s.91 — nothing else.
DISCIPLINE_TABLE = '''<table>
<tr><th>Step</th><th>What it is</th><th>What the Labour Act says</th></tr>
<tr><td><b>1. Query</b></td><td>A letter stating what is alleged, with dates, asking the employee to explain in writing by a stated time (24\u201372 hours is usual). It decides nothing.</td><td>Nothing in the Act requires a query; what the Act fixes is what the employer may <i>not</i> do instead \u2014 fine the worker or dock wages for the misconduct (s.5(1)).</td></tr>
<tr><td><b>2. Reply</b></td><td>The employee\u2019s written explanation: what happened, why, what changes. Short, factual, dated, a copy kept.</td><td>The Act is silent on the reply; a reply that is considered before the next step is what makes that step defensible if it is ever challenged.</td></tr>
<tr><td><b>3. Warning</b></td><td>First, second or final written warning: the conduct, the expected improvement, a deadline, and what follows if it is not met. Signed for receipt.</td><td>A warning may not carry a fine or a deduction (s.5(1)); whatever deductions the law does allow may not exceed one-third of a month\u2019s wages (s.5(7)). Special conditions of the job belong in the written terms (s.7(1)(h)).</td></tr>
<tr><td><b>4. Termination on notice</b></td><td>Where warnings have not worked: notice as the contract provides, or payment in lieu.</td><td>Notice of at least one day, one week, two weeks or one month by length of service (s.11(2)); payment in lieu allowed (s.11(6)); all wages due must be paid on or before the notice expires (s.11(7)).</td></tr>
<tr><td><b>5. Summary dismissal</b></td><td>Dismissal without notice for gross misconduct \u2014 theft, fraud, violence, wilful damage.</td><td>Kept open by s.11(5) for conduct that would have justified it at common law. The query and the reply are what show, later, that the conduct was established and the worker was heard.</td></tr>
</table>
<p class="muted">The Act\u2019s floors bind a \u201cworker\u201d as s.91 defines one \u2014 administrative, executive, technical and professional staff are governed by their contracts. For them, the steps above are still the practice the National Industrial Court expects to see on paper.</p>'''

PAGES["query-letter-sample-nigeria.html"] = dict(
    published="2026-11-12", parent=("employment-contract-sample-nigeria.html", "Employment contract sample"),
    title="Query Letter Sample Nigeria: Warning Letter + Reply (PDF)",
    h1="Query letter in Nigeria \u2014 the sample query, the employee\u2019s reply, the warning letter that follows, and the law under all three",
    desc="Query letter sample for Nigeria, free to download: the employer\u2019s query, the employee\u2019s reply, the warning that follows \u2014 and what the Labour Act forbids.",
    lead="An employee resumes late twice, or the till is short, or a customer complains. The first letter is "
         "not a warning \u2014 it is a <b>query</b>: a request to explain in writing, by a stated time, before any "
         "decision is taken. This page carries all three letters of a lawful disciplinary paper trail in the "
         "standard Nigerian form \u2014 the query, the employee\u2019s reply, and the first written warning \u2014 with "
         "square brackets where the details go. Read them, download the PDFs, or let the generator write the "
         "query or the warning with your facts in two minutes. Below the letters: what each step is for, what "
         "the Labour Act forbids at each one (fines and deductions, chiefly), and how an employee should answer.",
    widget=('<div class="box">\n<h2>1. The query (employer to employee)</h2>\n'
            + sample_docs.html_sample("query-letter-sample-nigeria")
            + download_block("query-letter-sample-nigeria", "warning", "Write a query with your facts \u2014 free \u2192")
            + '\n</div>\n<div class="box">\n<h2>2. The reply (employee to employer)</h2>\n'
            + sample_docs.html_sample("query-letter-reply-nigeria")
            + '<p class="dl"><a class="cta" href="%s" download>Download the reply as PDF \u2014 free, no signup</a></p>' % sample_docs.pdf_url("query-letter-reply-nigeria")
            + '\n</div>\n<div class="box">\n<h2>3. The warning letter (if the reply does not answer it)</h2>\n'
            + sample_docs.html_sample("warning-letter-sample-nigeria")
            + download_block("warning-letter-sample-nigeria", "warning", "Write the warning letter \u2014 free \u2192")
            + '\n</div>'),
    boxes=[
        ("What each letter is for", ul([
            "<b>The query</b> states the allegation and its dates and asks for a written explanation by a stated "
            "time. It must not announce the punishment \u2014 a query that says \u201cyou are hereby warned\u201d is a "
            "warning with the hearing skipped. Hand it over in person, have the employee sign for receipt, and keep "
            "the copy.",
            "<b>The reply</b> is the employee\u2019s hearing. It should say what happened, why, and what will change; "
            "it should not argue with the manager or accuse colleagues. Late, missing or evasive replies are "
            "themselves facts the employer may rely on.",
            "<b>The warning</b> records the conduct, refers to the query and the reply, states the expected "
            "improvement and a deadline, and says what follows if it is not met. \u201cFirst\u201d, \u201csecond\u201d and "
            "\u201cfinal\u201d are not in the Act; they are the ladder most Nigerian staff handbooks use, and the generator "
            "writes all three.",
            "<b>The acknowledgement</b> at the foot of the query and the warning is the proof of service. The words "
            "\u201creceipt does not indicate agreement\u201d are there so the employee has no reason to refuse to sign.",
        ])),
        ("The five steps and the law under each", DISCIPLINE_TABLE),
        ("What an employer may not do instead of a warning", ul([
            "<b>Fine the worker.</b> \u201cNo employer shall make any deduction \u2026 or any agreement or contract with a "
            "worker for any deduction \u2026 for or in respect of any fines\u201d (s.5(1)). A \u201clateness fine\u201d in a "
            "staff handbook is unenforceable against a Labour Act worker.",
            "<b>Dock wages for the loss.</b> A deduction for loss caused by the worker\u2019s wilful misconduct or "
            "neglect needs <i>the prior written consent of an authorised labour officer</i> and must be reasonable "
            "(s.5(1), proviso). Short till, broken stock, a lost phone \u2014 none may simply be taken from salary.",
            "<b>Exceed a third.</b> Whatever deductions the law does permit \u2014 PAYE, pension, union dues, an "
            "overpayment within the last three months (s.5(5)) \u2014 may not together exceed one-third of the month\u2019s "
            "wages (s.5(7)).",
            "<b>Suspend without pay indefinitely.</b> The Act does not provide for it; a suspension pending the reply "
            "should be short, in writing, and on pay unless the contract clearly says otherwise.",
            "<b>Dismiss summarily for an ordinary lapse.</b> Lateness, a missed target or a rude word are not the "
            "gross misconduct s.11(5) contemplates; they are query-and-warning matters. Summary dismissal is for "
            "theft, fraud, violence and the like \u2014 and even then the query first is what proves it later.",
        ])),
        ("If you are the employee who received a query", ul([
            "<b>Reply in writing, inside the time given.</b> Silence is read against you. If the time is too short to "
            "gather facts, say so in writing and ask for a day.",
            "<b>Facts, then responsibility, then the fix.</b> The sample reply above is the shape: what happened, "
            "what you did about it at the time, what you accept, what will change. One page.",
            "<b>Sign for receipt.</b> Signing the acknowledgement is not admitting the allegation \u2014 the letter says "
            "so. Refusing to sign only removes your proof of the date you received it.",
            "<b>Keep everything.</b> The query, your reply, the warning. If the matter ends in a dismissal you dispute, "
            "the National Industrial Court will ask whether you were heard; these are the papers that answer.",
            "<b>Check your payslip afterwards.</b> A fine or an unexplained deduction following a warning is itself "
            "unlawful for a Labour Act worker (s.5(1)) \u2014 raise it in writing.",
        ])),
        ("How this page compares with what else is online", ul([
            "<b>Template sites</b> show one query letter and one \u201chow to reply\u201d paragraph and sell the Word "
            "file. This page shows all three letters in full and gives them away.",
            "<b>Foreign HR templates</b> (US \u201cwrite-ups\u201d, UK disciplinary invitations) describe procedures under "
            "laws that do not run here. Every section on this page is a section of the Labour Act, Cap L1 LFN 2004, "
            "read from the enrolled text.",
            "<b>A lawyer</b> is the right call when the matter is heading for dismissal of a senior employee, or the "
            "employee has already written through counsel. For the query and the first warning, this is the paper "
            "the lawyer would want to find in the file.",
        ])),
    ],
    faq=[
        ("What is a query letter?",
         "In Nigerian workplaces, a query is the employer\u2019s letter asking an employee to explain in writing, by a "
         "stated time, why disciplinary action should not be taken over a stated allegation. It is not a warning "
         "and it decides nothing; the reply is considered before the next step. The sample above is that letter; "
         "the generator writes it with your facts."),
        ("How do I reply to a query letter?",
         "In writing, before the deadline, in one page: acknowledge the query and its date, state what happened and "
         "why, say what you did at the time, accept what is yours to accept, state what will change, and sign and "
         "date it. Keep a copy. The sample reply above is that letter."),
        ("Can my employer fine me or deduct from my salary after a query?",
         "Not for a Labour Act worker. Section 5(1) forbids deductions or agreements for deductions \u201cin respect of "
         "any fines\u201d; a deduction for loss caused by wilful misconduct needs an authorised labour officer\u2019s prior "
         "written consent and must be reasonable; and all deductions in a month are capped at one-third of wages "
         "(s.5(7))."),
        ("How many warnings before termination in Nigeria?",
         "The Labour Act sets no number. It fixes the notice a termination needs \u2014 one day to one month by length "
         "of service (s.11(2)) or payment in lieu (s.11(6)) \u2014 and keeps summary dismissal for conduct that "
         "justifies it (s.11(5)). The first-second-final ladder comes from staff handbooks and from what the "
         "National Industrial Court expects to see when a dismissal is challenged."),
        ("Must I sign the acknowledgement on a query or warning?",
         "Signing records receipt, not agreement \u2014 the letter says so. Refusing only deprives you of proof of the "
         "date you received it, which is the date your reply time runs from."),
        ("Can I download these letters as PDFs for free?",
         "Yes \u2014 all three PDFs above are free and need no signup. They carry the square brackets; the generator "
         "writes the query or the warning with your details, free with a small banner or without one on the Oga "
         "Pass. DocOga is not a law firm and this page is general information, not legal advice."),
    ],
    cta=("warning", "Write a query or warning letter free \u2192"),
    related=["employment-contract-sample-nigeria.html", "payslip-format-nigeria.html", "invoice-format-nigeria.html",
             "shop-tenancy-agreement-nigeria.html", "demand-letter-rent-arrears-nigeria.html"],
    priority="0.8",
)

# 4e ── payslip format (12 Nov 2026, third money-only build; docs/GROWTH.md §4) ----------------------
# The last of the eleven tools with no search page. The field (read 12 Nov: HR-software blogs, a free
# generator, a sixteen-country template farm) prints 2.5%-of-basic NHF as compulsory and dates its
# end to the wrong Act; nobody shows the PAYE arithmetic under the 2026 bands. Every rule below is
# tied to its section: Nigeria Tax Act 2025 (Fourth Schedule; s.163), Pension Reform Act 2014 s.4(1),
# Business Facilitation (Miscellaneous Provisions) Act 2023 s.45 (NHF Act s.4 as amended), Employees'
# Compensation Act 2010 s.33(1), Labour Act Cap L1 s.5(7) and s.15.
PAYSLIP_LINES = '''<table>
<tr><th>Line</th><th>The rule in 2026</th><th>Source</th></tr>
<tr><td><b>Gross pay</b></td><td>Basic + housing + transport + other allowances. Wages are due at the end of each pay period, and a pay period may not be longer than <b>one month</b>.</td><td>Labour Act, s.15</td></tr>
<tr><td><b>PAYE</b></td><td>On annual chargeable income (gross less pension and the other allowed deductions and reliefs): <b>first \u20a6800,000 at 0%</b>; next \u20a62,200,000 at 15%; next \u20a69,000,000 at 18%; next \u20a613,000,000 at 21%; next \u20a625,000,000 at 23%; above \u20a650,000,000 at 25%. Divide the year\u2019s tax by twelve for the monthly line. Rent relief: 20% of annual rent paid, up to \u20a6500,000, where the employee declares it. <b>An employee whose gross income from the job is the national minimum wage (\u20a670,000 a month) or less pays no PAYE at all.</b> Remitted to the internal revenue service of the state where the employee lives.</td><td>Nigeria Tax Act 2025, Fourth Schedule; s.163</td></tr>
<tr><td><b>Pension (employee)</b></td><td><b>Minimum 8%</b> of monthly emoluments \u2014 as the contract defines them, but never less than basic + housing + transport. The employer adds <b>at least 10%</b> on top; that share is a cost of the business and never appears as a deduction.</td><td>Pension Reform Act 2014, s.4(1)(a)\u2013(b)</td></tr>
<tr><td><b>National Housing Fund</b></td><td>2.5% of monthly income \u2014 <b>compulsory for public-sector staff and the self-employed, voluntary for private-sector employees</b> since February 2023, when s.45 of the Business Facilitation Act rewrote s.4 of the NHF Act. A private employer deducts it only for an employee who has chosen to contribute. (Most templates online still print it as compulsory, and several date its end to the 2025 tax law; both are wrong.)</td><td>Business Facilitation (Misc. Provisions) Act 2023, s.45</td></tr>
<tr><td><b>Other deductions</b></td><td>Only what a law permits or the employee has agreed to in writing \u2014 a salary advance, a cooperative, union dues. <b>No fines</b>, and a deduction for loss or damage only with an authorised labour officer\u2019s prior written consent. <b>Everything deducted in a month, added together, may not exceed one-third of that month\u2019s wages.</b></td><td>Labour Act, s.5(1), s.5(7)</td></tr>
<tr><td><b>Employer-only costs</b> (not on the payslip)</td><td>Employer pension \u2265 10%; Employees\u2019 Compensation Fund <b>1% of monthly payroll</b>; Industrial Training Fund 1% of annual payroll for employers of 25 or more.</td><td>PRA 2014 s.4(1)(a); Employees\u2019 Compensation Act 2010 s.33(1); ITF Act s.6 as amended 2023</td></tr>
</table>
<p class="muted">The payslip tool takes the PAYE, pension and NHF figures you enter; it does not compute tax for you. The worked example under the sample shows the arithmetic for one salary so you can check your own.</p>'''

PAGES["payslip-format-nigeria.html"] = dict(
    published="2026-11-12", parent=("employment-contract-sample-nigeria.html", "Employment contract sample"),
    title="Payslip Format Nigeria: Free Sample + PDF (2026 PAYE)",
    h1="Payslip format in Nigeria \u2014 the sample, the free PDF, and the 2026 rule behind every line",
    desc="Payslip format for Nigeria, free to download: earnings, PAYE under the 2026 bands, 8% pension, when NHF applies, the one-third cap \u2014 with the arithmetic shown.",
    lead="Every employee asks for one eventually \u2014 for a loan, a visa, a rent application, or to check what "
         "was taken out and why. This is the Nigerian payslip in its standard form: employer and employee, the "
         "pay period, earnings line by line, gross pay, the deductions the law allows, net pay in figures and "
         "words. The figures in the sample are computed, not invented \u2014 a \u20a6120,000 salary taken through "
         "the 2026 tax bands and the 8% pension, with the arithmetic printed under it \u2014 so you can check "
         "your own. Download the PDF, or let the generator lay yours out in two minutes. Below the sample: what "
         "each line is for, the rule behind each statutory line with its section, and what an employee should "
         "check before signing for a loan on the strength of it.",
    widget=('<div class="box">\n<h2>The sample (a \u20a6120,000 salary, November 2026)</h2>\n'
            + sample_docs.html_sample("payslip-sample-nigeria")
            + download_block("payslip-sample-nigeria", "payslip", "Lay out your payslip free \u2192")
            + '\n</div>'),
    boxes=[
        ("What each line is for", ul([
            "<b>Employer, employee, period, pay date.</b> The payslip is evidence \u2014 of employment, of income, of "
            "what was deducted. A bank or an embassy reads these four lines first; a payslip with no pay period "
            "proves nothing.",
            "<b>Basic, housing, transport.</b> The three components the pension law reads (the 8% and the 10% are "
            "calculated on at least their sum), which is why Nigerian salaries are split this way even when the "
            "employee never sees a difference.",
            "<b>Gross pay.</b> The whole of the month\u2019s earnings before anything is taken out \u2014 the figure a "
            "lender multiplies.",
            "<b>PAYE.</b> The employee\u2019s income tax, withheld by the employer and paid to the state where the "
            "employee lives. Under the 2026 bands a worker on \u20a6120,000 a month pays about \u20a66,560; a worker "
            "on \u20a670,000 pays nothing.",
            "<b>Pension, NHF, other deductions.</b> Each named, each with its rule in the table below. A line "
            "called \u201cdeductions\u201d with no breakdown is the first thing to query.",
            "<b>Net pay, in figures and in words.</b> What reached the account. The words are there for the same "
            "reason they are on a cheque \u2014 a figure can be altered; a sentence cannot be altered quietly.",
            "<b>\u201cComputer-generated, no signature required.\u201d</b> Standard, and lawful; what gives the "
            "document weight is that it matches the bank transfer and the employer\u2019s records.",
        ])),
        ("The rule behind each statutory line, with its section", PAYSLIP_LINES),
        ("The worked example, step by step", ul([
            "<b>Monthly:</b> basic \u20a670,000 + housing \u20a630,000 + transport \u20a620,000 = gross <b>\u20a6120,000</b>.",
            "<b>Pension (employee):</b> 8% \u00d7 \u20a6120,000 = <b>\u20a69,600</b>. (The employer separately pays "
            "10% \u00d7 \u20a6120,000 = \u20a612,000 into the same retirement savings account.)",
            "<b>Annual chargeable income:</b> gross \u20a61,440,000 \u2212 pension \u20a6115,200 = <b>\u20a61,324,800</b> "
            "(no NHF, no rent relief declared).",
            "<b>Tax for the year:</b> first \u20a6800,000 \u00d7 0% = \u20a60; remaining \u20a6524,800 \u00d7 15% = "
            "<b>\u20a678,720</b>.",
            "<b>PAYE on the payslip:</b> \u20a678,720 \u00f7 12 = <b>\u20a66,560</b> a month.",
            "<b>Net pay:</b> \u20a6120,000 \u2212 \u20a69,600 \u2212 \u20a66,560 = <b>\u20a6103,840</b>. Total deductions of "
            "\u20a616,160 are 13% of wages \u2014 well inside the one-third cap.",
            "<b>If the same employee declared rent of \u20a6400,000 a year:</b> relief of \u20a680,000 would bring "
            "chargeable income to \u20a61,244,800 and the year\u2019s tax to \u20a666,720 \u2014 \u20a65,560 a month. "
            "The declaration is the employee\u2019s to make, with the rent receipt as proof (see the rent-relief "
            "guide).",
        ])),
        ("If you are the employee reading yours", ul([
            "<b>Add the earnings and subtract the deductions yourself.</b> The net on the slip must equal the "
            "transfer in your bank; a difference is a question for payroll, in writing.",
            "<b>Check the PAYE against the bands.</b> On \u20a6120,000 a month the right figure is about "
            "\u20a66,560; a payslip still taking the old 7%-and-up rates on the first naira is taking too much.",
            "<b>Check the pension reached the account.</b> 8% from you and 10% from the employer should appear in "
            "your retirement savings account statement each month; the deduction on the slip is not the same as "
            "the remittance.",
            "<b>NHF: did you opt in?</b> If you are in the private sector and never chose to contribute, the 2.5% "
            "line should not be there.",
            "<b>Fines and \u201cshortages\u201d are not deductions.</b> A Labour Act worker may not be fined through "
            "the payslip (s.5(1)); raise it in writing, and keep the slip.",
            "<b>Keep twelve months of slips.</b> Lenders, landlords and embassies ask for three to six; the tax "
            "authority may ask for the year.",
        ])),
        ("How this page compares with what else is online", ul([
            "<b>HR-software blogs</b> print \u201cNHF 2.5% of basic\u201d as a compulsory line and, where they "
            "notice it is voluntary, credit the wrong Act. The rule changed in February 2023 (Business "
            "Facilitation Act, s.45), on monthly income, and only for private-sector employees; this page says so "
            "with the section.",
            "<b>Free generators</b> format whatever figures you type. So does ours \u2014 the difference is the "
            "worked example above, so you know whether the figures you type are right.",
            "<b>Foreign template farms</b> offer a \u201cNigeria payslip\u201d beside sixteen other countries, with "
            "the pay stub\u2019s layout and a tax column calculated who knows how. Every rule on this page is a "
            "Nigerian section, with its year.",
        ])),
    ],
    faq=[
        ("What should a payslip in Nigeria contain?",
         "Employer and employee details, the pay period and pay date, each earning line and the gross, each "
         "deduction by name \u2014 PAYE, pension, NHF where the employee contributes, anything else the employee "
         "agreed to in writing \u2014 the total deductions, and the net pay in figures and words. The sample above "
         "is that layout; the generator produces it."),
        ("How is PAYE calculated on a salary in 2026?",
         "Annual gross less pension (and NHF, NHIS and rent relief where they apply) gives chargeable income; the "
         "first \u20a6800,000 is taxed at 0%, the next \u20a62.2 million at 15%, the next \u20a69 million at 18%, "
         "then 21%, 23% and 25% above \u20a650 million (Nigeria Tax Act 2025, Fourth Schedule). The year\u2019s tax "
         "divided by twelve is the monthly PAYE. A worker earning the national minimum wage or less pays none "
         "(s.163)."),
        ("Is NHF compulsory for private-sector employees?",
         "No \u2014 not since February 2023. Section 45 of the Business Facilitation (Miscellaneous Provisions) Act "
         "2023 amended s.4 of the NHF Act: public-sector employees and the self-employed earning the minimum wage "
         "or more \u201cshall\u201d contribute 2.5% of monthly income; private-sector employees \u201cmay\u201d. An "
         "employer deducts it only for an employee who has opted in."),
        ("What is the pension deduction on a payslip?",
         "At least 8% of monthly emoluments from the employee, and at least 10% from the employer on top, both paid "
         "into the employee\u2019s retirement savings account (Pension Reform Act 2014, s.4(1)). Emoluments are as "
         "the contract defines them, but never less than basic + housing + transport."),
        ("Can an employer deduct fines or shortages on the payslip?",
         "Not from a Labour Act worker. Section 5(1) forbids deductions in respect of fines; a deduction for loss or "
         "damage caused by wilful misconduct needs an authorised labour officer\u2019s prior written consent; and "
         "all deductions in a month may not exceed one-third of wages (s.5(7))."),
        ("Can I download the payslip as a PDF for free?",
         "Yes \u2014 the PDF above is free and needs no signup. The generator lays out yours with your figures, free "
         "with a small banner or without one on the Oga Pass. It formats what you enter; it does not compute tax. "
         "DocOga is not a law firm or a tax adviser and this page is general information, not advice."),
    ],
    cta=("payslip", "Lay out your payslip free \u2192"),
    related=["employment-contract-sample-nigeria.html", "query-letter-sample-nigeria.html", "rent-relief-nigeria.html",
             "invoice-format-nigeria.html", "rent-receipt-format-nigeria.html"],
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
    desc="Tenant rights in Nigeria with section numbers: 9 things your landlord cannot do, how many months' notice, rent increases — and what the law does not promise.",
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
            "<b>There is no percentage cap</b> on rent increases in Lagos, the FCT or any other state we "
            "have verified except one: <b>Enugu</b>, where the Landlord and Tenant (Amendment) Law 2008 "
            "(s.3(b)) allows a review only after every second anniversary and caps it at 15% of the existing "
            "rent — see <a href=\"https://docoga.com.ng/tenancy-law-enugu\">tenancy law in Enugu</a>. A page "
            "that quotes a percentage for Lagos is wrong.",
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
         "at renewal, on notice. There is no statutory percentage cap in Lagos, but a sitting tenant can ask the "
         "court under s.37 to declare an increase unreasonable, and cannot be ejected while that "
         "application is pending. Enugu is the one state with a cap we have verified: 15%, and only after "
         "every second anniversary (Landlord and Tenant (Amendment) Law 2008, s.3(b))."),
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
    related=["notice-to-quit-nigeria.html", "rent-increase-notice-nigeria.html", "caution-fee-nigeria.html",
             "rent-receipt-format-nigeria.html", "tenancy-agreement-nigeria.html"],
    priority="0.8",
)

# 6 ── shop / commercial tenancy ------------------------------------------------
PAGES["shop-tenancy-agreement-nigeria.html"] = dict(
    title="Agreement Between Landlord and Tenant for a Shop in Nigeria",
    h1="Agreement between landlord and tenant for a shop: what a commercial tenancy needs",
    desc="Commercial tenancy in Nigeria — the clauses a shop or office agreement needs: permitted use, rent review, fixtures, signage, renewal. Free, 2 minutes.",
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
             "invoice-format-nigeria.html", "employment-contract-sample-nigeria.html", "tenant-rights-nigeria.html"],
    priority="0.8",
)

# 7 ── invoice format + VAT -----------------------------------------------------
PAGES["invoice-format-nigeria.html"] = dict(
    title="Invoice Format for Small Business in Nigeria (7.5% VAT)",
    h1="Invoice format for small business in Nigeria — with 7.5% VAT done properly",
    desc="The Nigerian invoice format small businesses need: TIN, invoice number, VAT shown separately at 7.5%, totals in naira, payment terms. Free — print or PDF.",
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
             "shop-tenancy-agreement-nigeria.html", "employment-contract-sample-nigeria.html"],
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
    title="Rent Relief Nigeria 2026: Claim the ₦500,000 Tax Deduction",
    h1="Rent relief in Nigeria — the 20% deduction every tenant can claim from 2026, and the papers you need",
    desc="Since 1 January 2026 tenants deduct 20% of rent paid (max ₦500,000) from taxable income — with a rent receipt and agreement. Calculator, deadlines, free letter.",
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
.updated{font-size:13px;color:#6B7A90;margin:-4px 0 12px}
.updated a{color:#6B7A90}
.crumbs{font-size:13px;color:#6B7A90;margin:0 0 10px}.crumbs a{color:#6B7A90}.crumbs span{color:#37455E}
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
.cta.alt{background:#fff;color:#0040E0;border:2px solid #0040E0}
.dl{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.dl .cta{margin:6px 0;font-size:15px;padding:12px 18px}
details{background:#fff;border:1px solid #DCE4F0;border-radius:12px;padding:14px 18px;margin:10px 0}
summary{font-weight:700;cursor:pointer}
p{margin:8px 0}
.links{font-size:14px}
.links a{color:#0040E0;text-decoration:none;font-weight:600;margin-right:12px;white-space:nowrap;display:inline-block}
footer{margin-top:34px;border-top:1px solid #DCE4F0;padding-top:16px;font-size:12.5px;color:#5B6B85}
.stickycta{position:fixed;left:0;right:0;bottom:0;z-index:60;background:#fff;border-top:1px solid #DCE4F0;box-shadow:0 -2px 14px rgba(20,31,51,.10);padding:10px 16px;display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap}
.stickycta span{font-size:13.5px;color:#141F33;font-weight:600}
.share{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;background:#E9FBEF;border:1px solid #BFE9CC;border-radius:12px;padding:12px 16px;margin:14px 0;font-size:14.5px}
.share a{background:#25D366;color:#fff;font-weight:800;text-decoration:none;border-radius:9px;padding:10px 16px;white-space:nowrap}
.stickycta a{background:#0040E0;color:#fff;font-weight:800;text-decoration:none;border-radius:9px;padding:11px 18px;font-size:14.5px;white-space:nowrap}
@media print{.stickycta{display:none}}"""


WIDGET_RENT_INDEX = r"""<style>
.mon{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:8px 0 12px}
.mon div{background:#0B1B3F;color:#fff;border-radius:12px;padding:14px 12px;text-align:center}
.mon b{display:block;font-size:26px;line-height:1.1}
.mon small{color:#C9D4EA;font-size:12px}
.bar{height:8px;background:#E8EEFB;border-radius:6px;overflow:hidden}
.bar i{display:block;height:100%;background:#0040E0}
#mon_states td:nth-child(2),#mon_states th:nth-child(2){text-align:right;white-space:nowrap}
@media (max-width:560px){.mon{grid-template-columns:1fr 1fr}}
</style>
<div class="box noprint" id="monitor">
<h2>The DocOga Rent Monitor &mdash; live counts</h2>
<p class="law">Read straight from the public receipt ledger (counts only &mdash; no names, no addresses, no amounts). A state publishes a rent level only when one of its cells reaches <b>30 receipts</b> in a calendar month.</p>
<div class="mon" id="mon_kpi"><div><b>&hellip;</b><small>receipts verified</small></div><div><b>&hellip;</b><small>states reporting</small></div><div><b>&hellip;</b><small>cells ready to publish</small></div></div>
<table id="mon_states"><tr><th>State</th><th>Receipts</th><th style="width:40%">Closest cell to 30</th></tr><tr><td colspan="3" class="law" id="mon_wait">Reading the ledger&hellip;</td></tr></table>
<p class="law" id="mon_note"></p>
</div>
<script>
(function(){
  var LEDGER_URL="https://docoga-ledger.johnazani.workers.dev";
  var M=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  function ym(s){return /^\d{4}-\d{2}$/.test(s||"")?M[Number(s.slice(5,7))-1]+" "+s.slice(0,4):s;}
  function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
  function fail(msg){var w=document.getElementById("mon_wait");if(w)w.textContent=msg;}
  var ctl=("AbortController" in window)?new AbortController():null;
  var tm=ctl?setTimeout(function(){ctl.abort();},6000):null;
  fetch(LEDGER_URL+"/api/stats",ctl?{signal:ctl.signal}:{}).then(function(r){if(tm)clearTimeout(tm);if(!r.ok)throw new Error(r.status);return r.json();}).then(function(d){
    var at=Number(d.publish_at||30),cells=d.cells||{},byState=d.by_state||{};
    var ready=0,best={};
    Object.keys(cells).forEach(function(k){var n=cells[k],st=k.split("|")[0];if(n>=at)ready+=1;if(!best[st]||n>best[st].n)best[st]={n:n,k:k};});
    var states=Object.keys(byState).filter(function(s){return s&&s!=="?";}).sort(function(a,b){return byState[b]-byState[a];});
    var k=document.getElementById("mon_kpi");
    k.innerHTML='<div><b>'+Number(d.total||0).toLocaleString("en-NG")+'</b><small>receipts verified</small></div><div><b>'+states.length+'</b><small>of 37 states reporting</small></div><div><b>'+ready+'</b><small>cells at '+at+' or more</small></div>';
    var t=document.getElementById("mon_states");
    var rows=states.slice(0,15).map(function(s){var b=best[s]||{n:0,k:"||"},parts=b.k.split("|"),pct=Math.min(100,Math.round(100*b.n/at));
      return '<tr><td>'+esc(s)+'</td><td>'+byState[s]+'</td><td><div class="bar"><i style="width:'+pct+'%"></i></div><small class="law">'+b.n+' of '+at+(parts[1]&&parts[2]?' &middot; '+esc(parts[1])+', '+esc(ym(parts[2])):'')+'</small></td></tr>';}).join("");
    t.innerHTML='<tr><th>State</th><th>Receipts</th><th style="width:40%">Closest cell to '+at+'</th></tr>'+(rows||'<tr><td colspan="3" class="law">No receipts registered yet &mdash; the first one can be yours.</td></tr>');
    var n=document.getElementById("mon_note");
    n.textContent=(d.latest_receipt_date?"Latest receipt dated "+d.latest_receipt_date+". ":"")+"Counts refresh hourly. No rent level is published until a cell reaches "+at+" receipts.";
  }).catch(function(){fail("The ledger could not be read just now. Counts refresh hourly \u2014 try again shortly.");});
})();
</script>"""


PAGES["rent-index-nigeria.html"] = dict(
    title="Rent Index Nigeria 2026: Rent Actually Paid, by State",
    h1="Nigeria\u2019s rent index \u2014 built from rent actually paid, not asking prices",
    desc="Nigeria has no official rent index. The DocOga Rent Monitor counts verified rent receipts by state, a median at 30 a month. Live counts, the method, join free.",
    lead="Nobody in Nigeria measures the rent people actually pay. The Bureau of Statistics publishes a "
         "national price index, not rents by state; the private \u201caverage rent\u201d figures come "
         "from listings \u2014 what landlords ask, not what tenants pay. DocOga\u2019s free rent receipt "
         "carries a verification code, and every verified receipt is one anonymous data point: state, "
         "kind, amount, period, date. Here is what has been counted so far, the rules we publish under, "
         "and how to add yours in two minutes.",
    widget=WIDGET_RENT_INDEX,
    boxes=[
        ("Why Nigeria has no rent index yet",
         "<p>Three things have to be true for a rent index to exist: the rent has to be written down, "
         "the paper has to be dated and placed, and somebody has to collect it at scale without "
         "collecting the tenant. In Nigeria the first step fails \u2014 most rent changes hands against "
         "a transfer alert or a handshake, so there is nothing to count.</p>" + ul([
            "<b>What exists:</b> the National Bureau of Statistics\u2019 Consumer Price Index, which "
            "has a housing component but is a national price index, not a rent series, and not by state.",
            "<b>What the \u201caverage rent in Lagos\u201d articles use:</b> asking prices scraped from "
            "property listings. Asking is not paid \u2014 listings over-represent the top of the market "
            "and vanish once a flat is let.",
            "<b>What a real index needs:</b> the amount actually paid, the period it covers, the state, "
            "the date \u2014 which is exactly what a lawful rent receipt carries (Lagos Tenancy Law "
            "2011, s.5(2)).",
         ])),
        ("How the DocOga Rent Monitor works",
         ul([
            "<b>One receipt, one observation.</b> When a landlord or agent prints a DocOga rent receipt "
            "with the free verification code, the ledger stores five fields: state, kind of payment, "
            "amount, period in months, date. Nothing else.",
            "<b>No person in the data.</b> No name, address, phone number, IP address or cookie is "
            "recorded \u2014 only a one-way fingerprint of the receipt\u2019s words, computed on the "
            "issuer\u2019s own phone, so the code can be checked later. Data that cannot be related to an "
            "individual is outside the Nigeria Data Protection Act 2023 (s.65), and the ledger is built "
            "to the Act\u2019s minimisation rule (s.24(1)(c)) regardless.",
            "<b>A cell is a state &times; kind &times; calendar month.</b> A cell publishes a rent level "
            "only at <b>30 receipts or more</b>; below that, counts only. Above it: the median and the "
            "inter-quartile range, never an average \u2014 rents are heavy-tailed and one penthouse "
            "would move a mean.",
            "<b>Annualised before comparison:</b> amount &divide; months &times; 12, so a six-month "
            "payment and a two-year payment sit on the same scale. Receipts without a period are counted "
            "but excluded from the level.",
            "<b>Published in the open.</b> The counts on this page come live from the same public "
            "endpoint the verification page uses; the method is written here before the first number, "
            "so nobody can accuse the first number of being chosen.",
         ])),
        ("Add your receipt \u2014 it takes two minutes and costs nothing",
         "<p>Issue the rent receipt on DocOga as usual. Pick the state, leave the <b>verification "
         "code</b> box ticked, print or save the PDF. The receipt carries a code and a QR anyone can "
         "check at docoga.com.ng/v/ &mdash; the tenant gets proof that survives a lost phone, the "
         "landlord gets a receipt that meets s.5 of the Lagos law, and the state gets one more receipt "
         "towards its first published rent level.</p>" + ul([
            "<b>Tenants:</b> ask for the DocOga receipt by name. The ₦500,000 rent-relief deduction "
            "under the Nigeria Tax Act 2025 (s.30(2)(a)(vi)) is claimed with a receipt and a tenancy "
            "agreement \u2014 see the rent relief guide below.",
            "<b>Landlords and agents:</b> the free version prints a small banner; the Oga Pass "
            "(₦2,000 for 30 days) removes it across all 11 tools. The verification code is free either way.",
            "<b>Prefer not to register a receipt?</b> Untick the box. The receipt still prints; it just "
            "carries no code.",
         ])),
        ("What happens when a state reaches 30",
         "<p>The first state to put 30 verified receipts of one kind into one month gets its median "
         "published here, with the sample size beside it, and a post on every DocOga channel the same "
         "day. On current traffic that is Lagos first. Until then this page shows counts, not levels, "
         "and says so.</p><p class=\"law\">Honest note: a rent index from receipts measures the rents "
         "of people who use receipts. In its early months it will lean towards tenants and landlords who "
         "already keep paper. That bias shrinks as the free receipt spreads; we will print the sample "
         "size beside every number so readers can judge it.</p>"),
    ],
    faq=[
        ("Is my rent amount visible to anyone?",
         "No. Amounts are never shown individually \u2014 only as a median across 30 or more receipts in "
         "a state, kind and month. The fingerprint that lets a code be checked is never published and "
         "cannot be reversed into names or addresses, which the ledger never had."),
        ("Does registering a receipt cost anything?",
         "No. The verification code, the QR and the check page are free on the free tier. The Oga Pass "
         "only removes the banner from the printed document."),
        ("What is the difference between asking rent and paid rent?",
         "Asking rent is the figure in a listing; paid rent is what the tenant actually handed over after "
         "negotiation, inclusive of any agreed discount or increase. Listing-based \u201caverage rent\u201d "
         "figures measure the first; a receipt measures the second."),
        ("When will the first rent level be published?",
         "When any state reaches 30 verified receipts of one kind in one calendar month. The live table "
         "above shows each state\u2019s closest cell and how far it is from 30."),
        ("Can a landlord be identified from the ledger?",
         "No. The ledger holds state, kind, amount, period, date and a one-way fingerprint. Even DocOga "
         "cannot tell whose receipt a code belongs to \u2014 only that a receipt with exactly those words "
         "was printed."),
    ],
    related=["rent-receipt-format-nigeria.html", "rent-relief-nigeria.html", "tenant-rights-nigeria.html"],
    cta=("receipt", "Issue a verified rent receipt free \u2192"),
    priority="0.8",
)


def render(fname, p):
    bare = fname[:-5] if fname.endswith(".html") else fname  # WhatsApp share carries the clean URL
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
    url = "%s/%s" % (DOMAIN, bare)
    blocks = [faq_jsonld(p["faq"]),
              freshness.article(url=url, headline=p["h1"].replace("&amp;", "&"), description=p["desc"].replace("&amp;", "&"),
                                image="%s/og/%s.jpg" % (DOMAIN, bare), date_published=p.get("published"))]
    crumbs = [("Home", DOMAIN + "/")]
    if p.get("parent"):
        crumbs.append((p["parent"][1], "%s/%s" % (DOMAIN, p["parent"][0][:-5])))
    crumbs.append((p["navtitle"].replace("&amp;", "&"), url))   # short, as shown on the page
    blocks.append(freshness.breadcrumbs(crumbs))
    crumbs_nav = freshness.breadcrumb_nav(crumbs)
    ld = "\n".join(json.dumps(b, ensure_ascii=False, indent=1) + "\n</script>\n<script type=\"application/ld+json\">" for b in blocks[:-1]) \
        + "\n" + json.dumps(blocks[-1], ensure_ascii=False, indent=1)
    updated = freshness.updated_line(None)
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
<meta property="og:image" content="%(domain)s/og/%(bare)s.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="%(title)s">
<meta name="twitter:card" content="summary_large_image">
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
%(crumbs)s
<h1>%(h1)s</h1>
%(updated)s
<p class="lead">%(lead)s</p>
%(widget)s
%(boxes)s

<div class="box">
<h2>Make it in 2 minutes \u2014 free</h2>
<p>DocOga works on your phone: answer simple questions, get a clean, standard Nigerian document you
can print, save as PDF or share on WhatsApp. The free version carries a small banner; the Oga Pass
(\u20a62,000/30 days) unlocks unlimited clean copies across all 11 tools.</p>
<a class="cta" href="%(domain)s/#%(cta_hash)s">%(cta_label)s</a>
</div>

<div class="share"><span>Someone you know needs this?</span> <a href="https://wa.me/?text=%(share_text)s" target="_blank" rel="noopener" onclick="window.gtag&amp;&amp;gtag('event','share',{method:'whatsapp',content_type:'page',item_id:'%(share_id)s'})">Share on WhatsApp \u2192</a></div>

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
<div class="follow" style="margin-top:12px">Follow DocOga for one rent rule a day: <a href="https://www.facebook.com/docoga.com.ng" target="_blank" rel="noopener">Facebook</a> · <a href="https://www.youtube.com/channel/UCeOzX7F7sYX-WchNJyBM2qA" target="_blank" rel="noopener">YouTube</a> · <a href="https://t.me/docogadaily" target="_blank" rel="noopener">Telegram</a> · <a href="https://www.instagram.com/docoga.ng/" target="_blank" rel="noopener">Instagram</a> · <a href="https://www.threads.com/@docoga.ng" target="_blank" rel="noopener">Threads</a></div>
</footer>
</div>
<div class="stickycta">
<span><b>Oga Pass</b> — ₦2,000 · 30 days · all 11 tools · no banner</span>
<a href="%(domain)s/#pricing">Get the Pass</a>
</div>
<script src="/analytics-consent.js" data-track-page="true" defer></script>
</body>
</html>
""" % dict(title=p["title"], desc=p["desc"], h1=p["h1"], lead=p["lead"], boxes=boxes,
           bare=bare, share_id=bare, share_text=quote("%s \u2014 %s/%s" % (p["title"].replace("&amp;", "&"), DOMAIN, bare), safe=""),
           faq=faq_block(p["faq"]), related=related, state_links=state_links,
           tool_links=tool_links, cta_hash=cta_hash, cta_label=cta_label,
           fname=fname, domain=DOMAIN, css=CSS, ld=ld, as_at=AS_AT, widget=widget, updated=updated, crumbs=crumbs_nav)


def main():
    # short labels for the "More guides" block
    navtitles = {
        "tenancy-agreement-nigeria.html": "Tenancy agreement format",
        "tenancy-agreement-sample-nigeria.html": "Tenancy agreement sample + free PDF",
        "notice-to-quit-nigeria.html": "Notice to quit: how many months",
        "caution-fee-nigeria.html": "Is the caution fee refundable?",
        "rent-receipt-format-nigeria.html": "Rent receipt format",
        "demand-letter-rent-arrears-nigeria.html": "Demand letter for unpaid rent + free PDF",
        "rent-increase-notice-nigeria.html": "Rent increase notice + the law by state",
        "employment-contract-sample-nigeria.html": "Employment contract sample + free PDF",
        "query-letter-sample-nigeria.html": "Query letter, reply &amp; warning letter + free PDFs",
        "payslip-format-nigeria.html": "Payslip format + 2026 PAYE worked example",
        "tenant-rights-nigeria.html": "Tenant rights &amp; landlord duties",
        "shop-tenancy-agreement-nigeria.html": "Shop &amp; business tenancy",
        "invoice-format-nigeria.html": "Invoice format + 7.5% VAT",
        "rent-relief-nigeria.html": "Rent relief: the ₦500,000 tax deduction",
        "rent-index-nigeria.html": "Rent Monitor: rent actually paid, by state",
    }
    for f, p in PAGES.items():
        p["navtitle"] = navtitles[f]

    made, dates = [], {}
    for fname, p in PAGES.items():
        html = render(fname, p)
        path = os.path.join(SITE, fname)
        html, dates[fname], _changed = freshness.stamp(path, clean_text(html, relative=True))
        io.open(path, "w", encoding="utf-8").write(html)
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
    # <lastmod> = each page's own honest date (freshness.stamp)
    for f in made:
        s = freshness.sitemap_lastmod(s, "%s/%s" % (DOMAIN, f[:-5]), dates[f])
    io.open(smap_path, "w", encoding="utf-8").write(s)
    print("sitemap: lastmod set on %d guide pages; newest %s" % (len(made), max(dates.values())))

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
