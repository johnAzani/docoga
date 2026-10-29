"""rent-index-nigeria (29 Oct 2026): the Rent Monitor page — counts live from docoga-ledger /api/stats,
no rent level before 30 receipts per cell (docs/RECEIPT_LEDGER.md §5), no person in the data."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import gen_guide_pages as gg  # noqa: E402

PAGE = ROOT / "site" / "rent-index-nigeria.html"


class RentIndexPageTests(unittest.TestCase):
    def setUp(self):
        self.t = PAGE.read_text(encoding="utf-8")

    def test_page_exists_with_clean_canonical_sitemap_entry_and_homepage_link(self):
        self.assertIn('<link rel="canonical" href="https://docoga.com.ng/rent-index-nigeria">', self.t)
        smap = (ROOT / "site" / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(smap.count("<loc>https://docoga.com.ng/rent-index-nigeria</loc>"), 1)
        idx = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<a href="/rent-index-nigeria">Rent Monitor: rent actually paid, by state</a>', idx)

    def test_the_widget_reads_the_same_public_ledger_the_dashboard_reads_and_publishes_counts_only(self):
        idx = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        url = re.search(r'const LEDGER_URL="([^"]+)"', idx).group(1)
        self.assertIn('var LEDGER_URL="%s"' % url, self.t)
        self.assertIn('fetch(LEDGER_URL+"/api/stats"', self.t)
        self.assertNotIn("/api/register", self.t)
        for word in ("30 receipts", "median", "inter-quartile", "never an average", "No name, address, phone number"):
            self.assertIn(word, self.t, word)
        self.assertNotIn("average rent in Lagos is", self.t.lower())
        self.assertIn("Nigeria Data Protection Act 2023 (s.65)", self.t)
        self.assertIn("s.24(1)(c)", self.t)

    def test_no_invented_statistics_in_the_prose(self):
        body = self.t.split("<body>", 1)[1]
        body = re.sub(r"<script>.*?</script>|<style>.*?</style>", "", body, flags=re.S)
        prose = re.sub(r"<[^>]+>", " ", body)
        self.assertNotRegex(prose, r"\d\s?%", "no percentage claims on a page with no published level")
        self.assertNotRegex(prose, r"average rent (in|of) \w+ is", "no listing-derived averages restated as fact")

    def test_script_is_syntactically_valid_javascript(self):
        import shutil
        import subprocess
        import tempfile
        if not shutil.which("node"):
            self.skipTest("node not installed")
        src = re.search(r"<script>(.*?)</script>", self.t, re.S).group(1)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(src)
        self.assertEqual(subprocess.run(["node", "--check", f.name], capture_output=True).returncode, 0)

    def test_generator_has_the_page_and_the_nav_title(self):
        self.assertIn("rent-index-nigeria.html", gg.PAGES)
        self.assertEqual(gg.PAGES["rent-index-nigeria.html"]["cta"][0], "receipt")
        self.assertIn('"rent-index-nigeria.html": "Rent Monitor: rent actually paid, by state"',
                      (ROOT / "tools" / "gen_guide_pages.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
