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
