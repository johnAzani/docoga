"""tenancy-law-<state> pages (29 Oct 2026) — the fifth state page type, led by the verified law block;
and the generator's two idempotency fixes (index 'State guides' regex anchored; sitemap append-only)."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import gen_state_pages as g  # noqa: E402
import state_law_data as S  # noqa: E402

SITE = ROOT / "site"


class LawPageTests(unittest.TestCase):
    def test_every_state_has_a_tenancy_law_page_in_the_sitemap_with_a_clean_canonical(self):
        smap = (SITE / "sitemap.xml").read_text(encoding="utf-8")
        for slug in g.STATES:
            page = SITE / ("tenancy-law-%s.html" % slug)
            self.assertTrue(page.is_file(), slug)
            t = page.read_text(encoding="utf-8")
            self.assertIn('<link rel="canonical" href="https://docoga.com.ng/tenancy-law-%s">' % slug, t)
            self.assertIn("<loc>https://docoga.com.ng/tenancy-law-%s</loc>" % slug, smap)
            self.assertEqual(smap.count("tenancy-law-%s<" % slug), 1)

    def test_a_verified_state_leads_with_its_statute_and_an_unverified_one_says_so(self):
        edo = (SITE / "tenancy-law-edo.html").read_text(encoding="utf-8")
        self.assertIn("What the law actually says in Edo", edo)
        self.assertIn(S.EDO["statutes"][0]["title"], edo)
        self.assertIn("What we could not confirm", edo)
        ogun = (SITE / "tenancy-law-ogun.html").read_text(encoding="utf-8")
        self.assertIn("we have not been able to verify a tenancy or rent-control statute for this state", ogun)
        self.assertNotIn("What the law actually says in Ogun", ogun)

    def test_titles_lead_with_the_phrase_people_type(self):
        for slug, st in g.STATES.items():
            t = (SITE / ("tenancy-law-%s.html" % slug)).read_text(encoding="utf-8")
            title = re.search(r"<title>(.*?)</title>", t).group(1)
            self.assertTrue(title.startswith("Tenancy Law in " + st["place"]), title)

    def test_the_tool_pages_link_to_the_law_page_as_tenancy_law_not_as_a_second_agreement(self):
        t = (SITE / "tenancy-agreement-edo.html").read_text(encoding="utf-8")
        self.assertIn('href="https://docoga.com.ng/tenancy-law-edo">Tenancy law — Edo</a>', t)
        self.assertEqual(t.count("Tenancy Agreement — Edo"), 0)


class GeneratorIdempotencyTests(unittest.TestCase):
    def test_the_index_state_guides_regex_is_anchored_to_that_block(self):
        src = (ROOT / "tools" / "gen_state_pages.py").read_text(encoding="utf-8")
        self.assertIn("head = s.find('State guides')", src)
        self.assertIn(".search(s, head)", src)
        idx = (SITE / "index.html").read_text(encoding="utf-8")
        guides = idx.split("Guides", 1)[1].split("</p>", 1)[0] if "Guides" in idx else ""
        self.assertIn("rent-relief-nigeria", idx)          # the national guides block survived a regeneration
        self.assertIn('href="/tenancy-agreement-plateau"', idx)   # and the state block lists all 12 states

    def test_the_sitemap_writer_appends_only_what_is_missing(self):
        src = (ROOT / "tools" / "gen_state_pages.py").read_text(encoding="utf-8")
        self.assertIn("missing = [f for f in sitemap_add if", src)
        self.assertNotIn("re.sub(pattern, '', s)", src)


if __name__ == "__main__":
    unittest.main()


class GuidesLaneBareUrlTests(unittest.TestCase):
    """29 Oct 2026: the Brain's 6:10am guide carried `rent-receipt-rivers.html?s=g` — link_for still
    said .html, so the clean-URL idempotency test went red on main. Both halves are pinned here."""

    def test_link_for_returns_bare_urls_for_state_and_national_pages(self):
        import brain_drafts as d
        self.assertEqual(d.link_for({"tool": "rent-receipt", "state": "rivers"}), d.LINK + "/rent-receipt-rivers")
        self.assertEqual(d.link_for({"tool": "tenant-rights"}), d.LINK + "/tenant-rights-nigeria")
        self.assertEqual(d.link_for({"tool": "nothing"}), d.LINK)

    def test_the_guides_lane_cleans_every_page_it_writes(self):
        src = (ROOT / "tools" / "guides_build.py").read_text(encoding="utf-8")
        self.assertIn("from clean_urls import clean_text", src)
        self.assertIn("page = clean_text(page_html(pack, facts_by_id, now=now), relative=False)", src)
        for p in (SITE / "guides").glob("*.html"):
            self.assertNotIn(".html?s=g", p.read_text(encoding="utf-8"), p.name)


class WhatsAppShareTests(unittest.TestCase):
    """29 Oct 2026: a 'Share on WhatsApp' row on every generated guide and state page — the ₦0
    distribution channel. Bare URL in the pre-filled text; GA4 `share` event with the page as item_id."""

    def _pages(self):
        import gen_guide_pages as gg
        return [SITE / f for f in gg.PAGES] + [SITE / ("%s-%s.html" % (t, s)) for t in g.TOOLS for s in g.STATES]

    def test_every_generated_page_carries_one_share_row_with_a_bare_url_and_a_ga_event(self):
        pages = self._pages()
        self.assertEqual(len(pages), 8 + 60)
        for p in pages:
            t = p.read_text(encoding="utf-8")
            self.assertEqual(t.count('<div class="share">'), 1, p.name)
            m = re.search(r'href="https://wa\.me/\?text=([^"]+)"', t)
            self.assertIsNotNone(m, p.name)
            from urllib.parse import unquote
            text = unquote(m.group(1))
            self.assertTrue(text.endswith("https://docoga.com.ng/" + p.name[:-5]), (p.name, text))
            self.assertNotIn(".html", text)
            self.assertNotIn("&amp;", text)
            self.assertIn("gtag('event','share',{method:'whatsapp',content_type:'page',item_id:'%s'})" % p.name[:-5], t)
            self.assertIn('target="_blank" rel="noopener"', t)

    def test_share_text_is_title_dash_url_fully_encoded(self):
        self.assertEqual(g.share_text("A &amp; B", "x-y"), "A%20%26%20B%20%E2%80%94%20https%3A%2F%2Fdocoga.com.ng%2Fx-y")
