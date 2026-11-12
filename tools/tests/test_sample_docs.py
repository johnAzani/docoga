"""The sample documents (🔒 docs/GROWTH.md, first dive, 3 Nov 2026): one source renders the HTML sample on
the guide page and the PDF people download; the HTML page is the search destination and the PDFs are
noindex; nothing in a sample is wording the generator does not produce."""
import re
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import sample_docs  # noqa: E402

SITE = ROOT / "site"


def pdf_text(data):
    """The text drawn by every content stream (enough to prove the words are in the file)."""
    out = []
    for m in re.finditer(rb"stream\n(.*?)\nendstream", data, flags=re.S):
        try:
            out.append(zlib.decompress(m.group(1)).decode("cp1252", "replace"))
        except zlib.error:
            pass
    return "\n".join(out)


class PdfTests(unittest.TestCase):
    def test_every_sample_renders_a_valid_deterministic_pdf_with_its_words_inside(self):
        for slug, (title, _) in sample_docs.SAMPLES.items():
            data = sample_docs.render_pdf(slug)
            self.assertTrue(data.startswith(b"%PDF-1.4"), slug)
            self.assertTrue(data.rstrip().endswith(b"%%EOF"), slug)
            self.assertEqual(data, sample_docs.render_pdf(slug), "deterministic — the build never churns the file")
            text = pdf_text(data)
            self.assertIn("docoga.com.ng", text)
            self.assertIn("not legal advice", text)
            self.assertNotIn("₦", text, "WinAnsi has no naira sign; the writer spells NGN")
            self.assertEqual(data.count(b"/Type /Page "), data.count(b"/Type /Page\n") + data.count(b"/Type /Page "))
            self.assertLess(len(data), 20_000, "a sample is a few KB, not a brochure")

    def test_the_agreement_pdf_carries_all_thirteen_clauses_and_the_receipt_the_five_lagos_fields(self):
        agreement = pdf_text(sample_docs.render_pdf("tenancy-agreement-sample-nigeria"))
        for i, (name, _) in enumerate(sample_docs.AGREEMENT_CLAUSES, 1):
            self.assertIn("%d. %s" % (i, name), agreement)
        self.assertEqual(len(sample_docs.AGREEMENT_CLAUSES), 13)
        receipt = pdf_text(sample_docs.render_pdf("rent-receipt-sample-nigeria"))
        for field in ("Date received", "Received from", "For the premises", "Amount received", "Period covered", "s.5\\(2\\)"):
            self.assertIn(field, receipt)

    def test_the_committed_pdfs_are_current_and_the_check_catches_a_stale_one(self):
        self.assertEqual(sample_docs.check(), [], "run python3 tools/sample_docs.py")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(sorted(sample_docs.write_all(tmp)), sorted("%s.pdf" % s for s in sample_docs.SAMPLES))
            self.assertEqual(sample_docs.write_all(tmp), [], "second run writes nothing")
            (Path(tmp) / "rent-receipt-sample-nigeria.pdf").write_bytes(b"old")
            self.assertEqual(sample_docs.check(tmp), ["rent-receipt-sample-nigeria"])


class PageTests(unittest.TestCase):
    def test_the_sample_page_is_answer_first_with_the_full_sample_the_download_and_the_generator(self):
        html = (SITE / "tenancy-agreement-sample-nigeria.html").read_text(encoding="utf-8")
        self.assertIn("<title>Tenancy Agreement Sample in Nigeria: Full Text + Free PDF</title>", html)
        self.assertLess(html.index("RESIDENTIAL TENANCY AGREEMENT"), html.index("What each clause does"),
                        "the sample comes before the explanation — answer first")
        self.assertIn("13. GOVERNING LAW AND JURISDICTION", html)
        self.assertIn('href="https://docoga.com.ng/samples/tenancy-agreement-sample-nigeria.pdf" download', html)
        self.assertIn('href="https://docoga.com.ng/#agreement"', html)
        self.assertIn('rel="canonical" href="https://docoga.com.ng/tenancy-agreement-sample-nigeria"', html)
        self.assertIn("Section 4 of the Lagos Tenancy Law 2011", html)
        self.assertNotIn("Chinedu", html, "placeholders in brackets, never a named stranger")

    def test_the_receipt_and_quit_notice_pages_carry_their_downloads_and_say_what_the_pdf_says(self):
        receipt = (SITE / "rent-receipt-format-nigeria.html").read_text(encoding="utf-8")
        self.assertIn("samples/rent-receipt-sample-nigeria.pdf", receipt)
        self.assertIn("Period covered:", receipt)
        self.assertIn("fine of ₦100,000 on conviction (s.5(3))", receipt)
        notice = (SITE / "notice-to-quit-nigeria.html").read_text(encoding="utf-8")
        self.assertIn("samples/quit-notice-letter-sample-nigeria.pdf", notice)
        pdf = pdf_text(sample_docs.render_pdf("quit-notice-letter-sample-nigeria"))
        self.assertIn("hereby give you six months' notice to quit and deliver up", pdf)
        self.assertIn("hereby give you <b>six months' notice</b> to quit and deliver up", notice)

    def test_the_html_page_is_the_search_destination_and_the_pdfs_are_not(self):
        headers = (SITE / "_headers").read_text(encoding="utf-8")
        block = headers.split("/samples/*", 1)[1]
        self.assertIn("X-Robots-Tag: noindex", block)
        sitemap = (SITE / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("<loc>https://docoga.com.ng/tenancy-agreement-sample-nigeria</loc>", sitemap)
        self.assertNotIn("/samples/", sitemap)
        self.assertTrue((SITE / "og" / "tenancy-agreement-sample-nigeria.jpg").is_file())
        for slug in sample_docs.SAMPLES:
            self.assertTrue((SITE / "samples" / ("%s.pdf" % slug)).is_file(), slug)

    def test_the_sample_page_is_linked_from_the_pages_that_already_rank(self):
        for page in ("index.html", "tenancy-agreement-nigeria.html", "notice-to-quit-nigeria.html", "rent-receipt-format-nigeria.html"):
            self.assertIn("/tenancy-agreement-sample-nigeria", (SITE / page).read_text(encoding="utf-8"), page)

    def test_every_state_page_of_a_sampled_tool_offers_the_sample_and_the_pdf(self):
        """36 state pages already rank for state queries ('edo state tenancy law'); each now puts the
        sample and the download one tap away. Tools without a sample stay untouched."""
        import gen_state_pages as gsp
        for tool, (page, pdf, _) in gsp.SAMPLE_FOR.items():
            pages = sorted(SITE.glob("%s-*.html" % tool))
            pages = [p for p in pages if p.name not in ("%s-nigeria.html" % tool, "%s-sample-nigeria.html" % tool)]
            self.assertGreaterEqual(len(pages), 12, tool)
            for sp in pages:
                html = sp.read_text(encoding="utf-8")
                self.assertIn("https://docoga.com.ng/%s" % page, html, sp.name)
                self.assertIn("/samples/%s.pdf" % pdf, html, sp.name)
        for sp in SITE.glob("caution-fee-*.html"):
            self.assertNotIn("/samples/", sp.read_text(encoding="utf-8"), sp.name)

    def test_the_demand_letter_page_is_answer_first_state_aware_and_the_generators_words(self):
        """4 Nov 2026 (🔒 docs/GROWTH.md fourth dive): the generator wrote demand letters with no page."""
        html = (SITE / "demand-letter-rent-arrears-nigeria.html").read_text(encoding="utf-8")
        self.assertIn("Demand Letter for Unpaid Rent in Nigeria: Sample + Free PDF", html)
        self.assertLess(html.index("DEMAND LETTER — UNPAID RENT"), html.index("What each line of the letter is for"),
                        "the letter comes before the explanation — answer first")
        self.assertIn('href="https://docoga.com.ng/samples/demand-letter-rent-arrears-nigeria.pdf" download', html)
        self.assertIn('href="https://docoga.com.ng/#demand"', html)
        self.assertIn('rel="canonical" href="https://docoga.com.ng/demand-letter-rent-arrears-nigeria"', html)
        for needle in ("s.13(2), s.13(3)", "No arrears shortcut", "s.15 proviso", "s.17 proviso", "s.75(1)", "s.44"):
            self.assertIn(needle, html, needle)
        self.assertNotIn("Chinedu", html)
        index = re.sub(r"<[^>]+>", "", (SITE / "index.html").read_text(encoding="utf-8"))   # renderDemand bolds words
        for sentence in sample_docs.DEMAND_SENTENCES:
            # the generator's sentence, minus the bracketed details and the sentence that carries them
            for piece in re.split(r"\[[^\]]*\]", sentence):
                piece = piece.strip(" .,")
                if len(piece) > 25:
                    self.assertIn(piece, index, piece)
        pdf = pdf_text(sample_docs.render_pdf("demand-letter-rent-arrears-nigeria"))
        self.assertIn("DEMAND is hereby made", pdf)
        for page in ("index.html", "notice-to-quit-nigeria.html", "rent-receipt-format-nigeria.html"):
            self.assertIn("/demand-letter-rent-arrears-nigeria", (SITE / page).read_text(encoding="utf-8"), page)
        self.assertIn("<loc>https://docoga.com.ng/demand-letter-rent-arrears-nigeria</loc>",
                      (SITE / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertTrue((SITE / "og" / "demand-letter-rent-arrears-nigeria.jpg").is_file())
        import growth
        self.assertTrue(growth.MONEY_PAGE.search("https://docoga.com.ng/demand-letter-rent-arrears-nigeria"),
                        "a page with a generator on it is a money page")

    def test_the_rent_increase_page_is_state_aware_honest_and_the_generators_words(self):
        """5 Nov 2026 (🔒 docs/GROWTH.md fifth dive): the 11th tool, and the page only because the tool writes it."""
        html = (SITE / "rent-increase-notice-nigeria.html").read_text(encoding="utf-8")
        self.assertIn("Rent Increase Notice Nigeria: Sample + Tenant\u2019s Reply (PDF)", html)
        self.assertLess(html.index("NOTICE OF RENT REVIEW"), html.index("What the law actually says, state by state"),
                        "the notice comes before the explanation — answer first")
        self.assertIn('href="https://docoga.com.ng/samples/rent-increase-notice-nigeria.pdf" download', html)
        self.assertIn('href="https://docoga.com.ng/#rentreview"', html)
        self.assertIn('rel="canonical" href="https://docoga.com.ng/rent-increase-notice-nigeria"', html)
        for needle in ("s.37(4)", "Landlord and Tenant (Amendment) Law 2008, s.3(b)", "every second anniversary",
                       "No state statute we have read fixes a notice period for a rent increase",
                       "offer for the next term, not an order for this one", "Jovinco", "s.44"):
            self.assertIn(needle, html, needle)
        self.assertNotIn("Chinedu", html)
        index_html = (SITE / "index.html").read_text(encoding="utf-8")
        index = re.sub(r"<[^>]+>", "", index_html)                                   # renderRentReview bolds words
        for sentence in sample_docs.RENT_REVIEW_SENTENCES:
            for piece in re.split(r"\[[^\]]*\]", sentence):
                piece = piece.strip(" .,")
                if len(piece) > 25:
                    self.assertIn(piece, index, piece)
        # the generator itself: an 11th tool with the Enugu cap wired in, not a page pretending to one
        for needle in ('id="page-rentreview"', "function renderRentReview", "function rrLawText", "function rrCap",
                       "exceeds that limit and must be reduced to not more than", "All 11 tools"):
            self.assertIn(needle, index_html, needle)
        pdf = pdf_text(sample_docs.render_pdf("rent-increase-notice-nigeria"))
        self.assertIn("NOTICE OF RENT REVIEW", pdf)
        self.assertIn("not a demand for the present one", pdf)
        # 5 Nov evening: the tenant's reply — a second output of the same tool, on the same page
        self.assertIn('href="https://docoga.com.ng/samples/rent-increase-reply-nigeria.pdf" download', html)
        self.assertLess(html.index("NOTICE OF RENT REVIEW"), html.index("REPLY TO A NOTICE OF RENT REVIEW"))
        self.assertFalse((SITE / "rent-increase-reply-nigeria.html").exists(), "one page, two outputs — no thin duplicate")
        for sentence in sample_docs.RENT_REPLY_SENTENCES:
            for piece in re.split(r"\[[^\]]*\]", sentence):
                piece = piece.strip(" .,;")
                if len(piece) > 25:
                    self.assertIn(piece, index, piece)
        for needle in ('id="v_role"', 'id="v_answer"', 'id="v_offer"', "function renderRentReply", "function rrReplyLawText",
                       "I reserve my right under section 37", "Nothing in this letter is a notice to quit",
                       "the figure you propose exceeds that limit and I am not able to agree to it",
                       "the most that section 3(b) of the Landlord and Tenant (Amendment) Law 2008 permits"):
            self.assertIn(needle, index_html, needle)
        reply_pdf = pdf_text(sample_docs.render_pdf("rent-increase-reply-nigeria"))
        self.assertIn("REPLY TO A NOTICE OF RENT REVIEW", reply_pdf)
        self.assertIn("I reserve my right under section 37", reply_pdf)
        for page in ("index.html", "tenant-rights-nigeria.html", "notice-to-quit-nigeria.html",
                     "demand-letter-rent-arrears-nigeria.html"):
            self.assertIn("/rent-increase-notice-nigeria", (SITE / page).read_text(encoding="utf-8"), page)
        self.assertIn("<loc>https://docoga.com.ng/rent-increase-notice-nigeria</loc>",
                      (SITE / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertTrue((SITE / "og" / "rent-increase-notice-nigeria.jpg").is_file())
        import growth
        self.assertTrue(growth.MONEY_PAGE.search("https://docoga.com.ng/rent-increase-notice-nigeria"))
        for sp in SITE.glob("*.html"):
            self.assertNotIn("all 10 tools", sp.read_text(encoding="utf-8"), sp.name)

    def test_the_employment_contract_page_is_the_generators_contract_on_the_labour_act_floors(self):
        """12 Nov 2026 (money-only build, docs/GROWTH.md §4): a free sample in front of the paid employment
        tool; every floor read from the enrolled Labour Act, Cap L1 LFN 2004 — not from a blog."""
        html = (SITE / "employment-contract-sample-nigeria.html").read_text(encoding="utf-8")
        self.assertIn("<title>Employment Contract Sample Nigeria: Free PDF + Template</title>", html)
        self.assertLess(html.index("EMPLOYMENT CONTRACT"), html.index("The Labour Act floors, clause by clause"),
                        "the contract comes before the explanation — answer first")
        self.assertIn('href="https://docoga.com.ng/samples/employment-contract-sample-nigeria.pdf" download', html)
        self.assertIn('href="https://docoga.com.ng/#employment"', html)
        self.assertIn('rel="canonical" href="https://docoga.com.ng/employment-contract-sample-nigeria"', html)
        for needle in ("s.7(1)", "s.9(3)", "s.11(2)", "s.13(1)", "s.15", "s.16", "s.18(1)", "s.91(1)",
                       "six working days", "twelve working days", "one day", "one week", "two weeks", "one month",
                       "\u20a670,000 a month", "not legal advice"):
            self.assertIn(needle, html, needle)
        for invented in ("Chinedu", "Adebayo", "Mr ", "Mrs "):
            self.assertNotIn(invented, html, "no invented names in a sample")
        # the sample is the generator's contract: same eight clause headings, same order
        index_html = (SITE / "index.html").read_text(encoding="utf-8")
        heads = ["POSITION AND DUTIES", "COMMENCEMENT AND PROBATION", "REMUNERATION", "HOURS AND PLACE OF WORK",
                 "ANNUAL LEAVE AND SICK LEAVE", "CONFIDENTIALITY", "TERMINATION AND NOTICE", "GOVERNING LAW"]
        for n, h in enumerate(heads, 1):
            self.assertIn("<b>%d. %s</b>" % (n, h), index_html, h)
            self.assertIn("%d. %s" % (n, h), html, h)
        positions = [html.index("%d. %s" % (n, h)) for n, h in enumerate(heads, 1)]
        self.assertEqual(positions, sorted(positions), "same order as the generator")
        # the generator now writes the s.7(1)(g) sick-pay term with the s.16 floor
        self.assertIn("paid sick leave of up to twelve working days in any calendar year", index_html)
        pdf = pdf_text(sample_docs.render_pdf("employment-contract-sample-nigeria"))
        self.assertIn("EMPLOYMENT CONTRACT", pdf)
        self.assertIn("5. ANNUAL LEAVE AND SICK LEAVE", pdf)
        self.assertNotIn("\\\"", pdf)
        for page in ("index.html", "invoice-format-nigeria.html", "shop-tenancy-agreement-nigeria.html"):
            self.assertIn("/employment-contract-sample-nigeria", (SITE / page).read_text(encoding="utf-8"), page)
        self.assertIn("<loc>https://docoga.com.ng/employment-contract-sample-nigeria</loc>",
                      (SITE / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertTrue((SITE / "og" / "employment-contract-sample-nigeria.jpg").is_file())
        self.assertIn("/employment-contract-sample-nigeria.html /employment-contract-sample-nigeria 301",
                      (SITE / "_redirects").read_text(encoding="utf-8"))
        import growth
        self.assertTrue(growth.MONEY_PAGE.search("https://docoga.com.ng/employment-contract-sample-nigeria"),
                        "a page with a generator on it is a money page")

    def test_the_query_letter_page_carries_all_three_letters_and_the_tool_now_writes_the_query(self):
        """12 Nov 2026 (second money-only build): query → reply → warning on one page; the warning tool gains
        the query stage; every rule quoted is Labour Act s.5 / s.11, read from the enrolled text."""
        html = (SITE / "query-letter-sample-nigeria.html").read_text(encoding="utf-8")
        self.assertIn("<title>Query Letter Sample Nigeria: Warning Letter + Reply (PDF)</title>", html)
        order = [html.index("RE: QUERY"), html.index("REPLY TO QUERY"), html.index("FIRST WRITTEN WARNING"),
                 html.index("The five steps and the law under each")]
        self.assertEqual(order, sorted(order), "query, reply, warning, then the explanation — answer first")
        for slug in ("query-letter-sample-nigeria", "query-letter-reply-nigeria", "warning-letter-sample-nigeria"):
            self.assertIn('href="https://docoga.com.ng/samples/%s.pdf" download' % slug, html, slug)
            self.assertFalse((SITE / (slug + ".html")).exists() and slug != "query-letter-sample-nigeria",
                             "one page, three outputs — no thin duplicates")
        self.assertIn('href="https://docoga.com.ng/#warning"', html)
        self.assertIn('rel="canonical" href="https://docoga.com.ng/query-letter-sample-nigeria"', html)
        for needle in ("s.5(1)", "s.5(7)", "s.11(2)", "s.11(5)", "s.11(6)", "s.11(7)", "one-third",
                       "in respect of any fines", "authorised labour officer", "not legal advice"):
            self.assertIn(needle, html, needle)
        for invented in ("Chidi", "Bisi", "Mr ", "Mrs "):
            self.assertNotIn(invented, html, "no invented names in a sample")
        # the generator: a Query stage that writes the query, and the warning branch untouched
        index_html = (SITE / "index.html").read_text(encoding="utf-8")
        for needle in ("<option>Query (explain in writing)</option>", "function renderQueryLetter",
                       "const isQuery=/^Query/.test(count);", "<b>RE: QUERY</b>",
                       "<b>You are required to explain in writing</b> why disciplinary action should not be taken",
                       "within 48 hours of receiving this letter", "Your explanation will be considered before any decision is taken",
                       "This letter serves as your <b>'+count.toLowerCase()+'</b>"):
            self.assertIn(needle, index_html, needle)
        # the sample letters say what the generator says
        index = re.sub(r"<[^>]+>", "", index_html)
        flat = re.sub(r"\s+", " ", html)                                              # the <pre> wraps at 78 columns
        for sentence in ("which, if established, is contrary to the terms of your employment and company policy",
                         "why disciplinary action should not be taken against you in respect of the above",
                         "which is contrary to the terms of your employment and company policy",
                         "failure to show the required improvement may result in further disciplinary action"):
            self.assertIn(sentence, index, sentence)
            self.assertIn(sentence, flat, sentence)
        for slug, head in (("query-letter-sample-nigeria", "QUERY"), ("query-letter-reply-nigeria", "REPLY TO QUERY"),
                           ("warning-letter-sample-nigeria", "FIRST WRITTEN WARNING")):
            self.assertIn(head, pdf_text(sample_docs.render_pdf(slug)), slug)
        for page in ("index.html", "employment-contract-sample-nigeria.html"):
            self.assertIn("/query-letter-sample-nigeria", (SITE / page).read_text(encoding="utf-8"), page)
        self.assertIn("<loc>https://docoga.com.ng/query-letter-sample-nigeria</loc>",
                      (SITE / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertTrue((SITE / "og" / "query-letter-sample-nigeria.jpg").is_file())
        import growth
        self.assertTrue(growth.MONEY_PAGE.search("https://docoga.com.ng/query-letter-sample-nigeria"))

    def test_the_payslip_page_shows_computed_figures_and_the_2026_rules_with_their_sections(self):
        """12 Nov 2026 (third money-only build): the last tool with no page. The figures are arithmetic the
        reader can check; NHF is voluntary for private-sector staff since the 2023 Act, not the 2025 one."""
        html = (SITE / "payslip-format-nigeria.html").read_text(encoding="utf-8")
        self.assertIn("<title>Payslip Format Nigeria: Free Sample + PDF (2026 PAYE)</title>", html)
        self.assertLess(html.index("PAYSLIP"), html.index("The rule behind each statutory line"), "answer first")
        self.assertIn('href="https://docoga.com.ng/samples/payslip-sample-nigeria.pdf" download', html)
        self.assertIn('href="https://docoga.com.ng/#payslip"', html)
        # the arithmetic: 120,000 gross → 9,600 pension → 1,324,800 chargeable → 78,720 a year → 6,560 a month → 103,840 net
        for figure in ("\u20a69,600", "\u20a61,324,800", "\u20a678,720", "\u20a66,560", "\u20a6103,840", "\u20a65,560"):
            self.assertIn(figure, html, figure)
        self.assertEqual(round((1_440_000 - 115_200 - 800_000) * 0.15 / 12), 6_560)
        self.assertEqual(120_000 - 9_600 - 6_560, 103_840)
        for needle in ("Fourth Schedule", "s.163", "Pension Reform Act 2014, s.4(1)", "Business Facilitation", "s.45",
                       "Employees\u2019 Compensation Act 2010 s.33(1)", "s.5(7)", "s.15", "first \u20a6800,000 at 0%",
                       "voluntary for private-sector employees", "one-third", "not advice"):
            self.assertIn(needle, html, needle)
        self.assertNotIn("GTBank", html)
        for invented in ("Chidi", "Bisi", "Mr ", "Mrs "):
            self.assertNotIn(invented, html)
        pdf = pdf_text(sample_docs.render_pdf("payslip-sample-nigeria"))
        self.assertIn("PAYSLIP", pdf)
        self.assertIn("NET PAY", pdf)
        index_html = (SITE / "index.html").read_text(encoding="utf-8")
        for line in ("Basic salary", "Housing allowance", "Transport allowance", "Other allowances", "GROSS PAY",
                     "PAYE (income tax)", "Pension (employee)", "National Housing Fund", "Other deductions", "TOTAL DEDUCTIONS", "NET PAY"):
            self.assertIn(line, index_html, line)          # the sample's lines are the generator's lines
            self.assertIn(line, html, line)
        for page in ("index.html", "employment-contract-sample-nigeria.html", "query-letter-sample-nigeria.html"):
            self.assertIn("/payslip-format-nigeria", (SITE / page).read_text(encoding="utf-8"), page)
        self.assertIn("<loc>https://docoga.com.ng/payslip-format-nigeria</loc>", (SITE / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertTrue((SITE / "og" / "payslip-format-nigeria.jpg").is_file())
        import growth
        self.assertTrue(growth.MONEY_PAGE.search("https://docoga.com.ng/payslip-format-nigeria"))
        # every one of the eleven tools now has a page in front of it
        for h in ("agreement", "notice", "receipt", "invoice", "employment", "caution", "demand", "rentreview", "payslip", "warning", "poa"):
            hits = [p for p in SITE.glob("*.html") if p.name != "index.html"
                    and 'href="https://docoga.com.ng/#%s"' % h in p.read_text(encoding="utf-8")
                    and '<a class="cta" href="https://docoga.com.ng/#%s"' % h in p.read_text(encoding="utf-8")]
            self.assertTrue(hits, "no page carries the %s tool as its own call to action" % h)

    def test_the_sample_wording_is_the_generators_wording(self):
        """Every clause body in the sample appears, placeholders aside, in site/index.html's renderAgreement."""
        index = (SITE / "index.html").read_text(encoding="utf-8")
        for name, body in sample_docs.AGREEMENT_CLAUSES:
            self.assertIn(name, index, name)
            # brackets are the user's details; "per annum" is the generator's period word
            longest = max(re.split(r"\[[^\]]*\]| per annum", body), key=len).strip()
            self.assertGreater(len(longest), 40, name)
            self.assertIn(longest, index, "%s: %r" % (name, longest))


if __name__ == "__main__":
    unittest.main()
