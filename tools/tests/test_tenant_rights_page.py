"""site/tenant-rights-nigeria.html (rewritten 29 Oct 2026): the 'what your landlord cannot do' page
answers with section numbers that match tools/state_law_data.py (read from the enrolled Lagos
text) — and never the two mis-citations the old page carried (quiet enjoyment as s.7, pay-into-court
as s.28) nor the foreign rules rivals copy (24-48h entry notice as law, a percentage cap on rent)."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
PAGE = ROOT / "site" / "tenant-rights-nigeria.html"


class TenantRightsPageTests(unittest.TestCase):
    def setUp(self):
        self.t = PAGE.read_text(encoding="utf-8")

    def test_title_and_description_fit_a_phone_result(self):
        title = re.search(r"<title>(.*?)</title>", self.t).group(1)
        desc = re.search(r'<meta name="description" content="(.*?)">', self.t).group(1)
        self.assertEqual(title, "Tenant Rights in Nigeria 2026: What Your Landlord Cannot Do")
        self.assertLessEqual(len(title), 60)
        self.assertLessEqual(len(desc), 165)
        self.assertIn("cannot do", desc)

    def test_every_section_number_matches_the_verified_lagos_data(self):
        import state_law_data as S
        L = S.LAGOS
        self.assertIn("s.44(1)", self.t)                   # offences — L["protections"]
        self.assertIn("₦250,000", self.t)
        self.assertIn("s.6 gives you quiet and peaceable enjoyment", self.t)
        self.assertEqual(L["repairs"]["cite"], "s.7(3), s.8(vi)")
        self.assertIn("s.8(vi)", self.t)
        self.assertIn("s.7(3)", self.t)
        self.assertEqual(L["receipts"]["cite"], "s.5")
        self.assertIn("s.5(3)", self.t)
        self.assertEqual(L["advance_rent"]["cite"], "s.4")
        self.assertIn("s.4(5)", self.t)
        self.assertEqual(L["increase_challenge"]["cite"], "s.37")
        self.assertIn("s.37(4)", self.t)
        self.assertIn("Form TL11", self.t)
        self.assertIn("(s.29)", self.t)                     # pay rent into the Court Registry
        self.assertIn("s.13(1)(a)–(e)", self.t)
        self.assertIn("s.1(3)", self.t)

    def test_the_old_mis_citations_and_the_copied_foreign_rules_are_gone(self):
        self.assertNotIn("access to it (s.7)", self.t)
        self.assertNotIn("(s.28)", self.t)
        self.assertNotIn("registry if the landlord refuses to accept it (s.28)", self.t)
        self.assertIn("no percentage cap", self.t.lower())
        self.assertIn("No \"24–48 hours' notice before entry\" rule", self.t)

    def test_the_faq_schema_carries_the_questions_people_search(self):
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', self.t, re.S)
        names = [q["name"] for q in json.loads(m.group(1))["mainEntity"]]
        for needle in ("lock me out", "enter my flat without notice", "increase my rent",
                       "How many months' notice", "caution fee or deposit refundable"):
            self.assertTrue(any(needle in n for n in names), needle)
        self.assertEqual(len(names), 8)

    def test_links_to_the_sister_pages_are_clean_urls(self):
        self.assertIn('href="https://docoga.com.ng/notice-to-quit-nigeria"', self.t)
        self.assertIn('href="https://docoga.com.ng/caution-fee-nigeria"', self.t)
        self.assertNotIn('nigeria.html"', self.t.split("<body")[1].split("More guides")[0])


if __name__ == "__main__":
    unittest.main()
