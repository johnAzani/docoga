"""Rent relief (NTA 2025 s.30(2)(a)(vi)) — the page, the calculator, the letter, the receipt
fields. Owner's "Go" of 27 Oct 2026 on Strategy Office analysis #1.

The arithmetic is checked by running the page's own JavaScript in node (the same function the
visitor's phone runs), not by re-implementing it in Python.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
PAGE = SITE / "rent-relief-nigeria.html"
INDEX = SITE / "index.html"
GEN = ROOT / "tools" / "gen_guide_pages.py"
NODE = shutil.which("node")
HAS_JSDOM = NODE and (ROOT / "node_modules" / "jsdom").is_dir()


def _page():
    return PAGE.read_text(encoding="utf-8")


class PageTests(unittest.TestCase):
    def test_the_page_exists_cites_the_section_and_the_two_numbers(self):
        t = _page()
        self.assertIn("30(2)(a)(vi)", t)
        self.assertIn("Nigeria Tax Act 2025", t)
        self.assertIn("20%", t)
        self.assertIn("₦500,000", t)
        self.assertIn("1 January 2026", t)
        self.assertIn("31 March 2027", t)
        self.assertIn("31 January 2027", t)

    def test_it_never_calls_the_relief_automatic_and_disclaims_advice(self):
        t = _page()
        self.assertRegex(t, re.compile(r"not automatic|is not automatic", re.I))
        self.assertIn("not tax advice", t)
        self.assertIn("not legal advice", t)

    def test_seo_contract_canonical_schema_and_sitemap(self):
        t = _page()
        self.assertIn('<link rel="canonical" href="https://docoga.com.ng/rent-relief-nigeria.html">', t)
        ld = re.search(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', t, re.S).group(1)
        data = json.loads(ld)
        self.assertEqual(data["@type"], "FAQPage")
        self.assertGreaterEqual(len(data["mainEntity"]), 4)
        smap = (SITE / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("https://docoga.com.ng/rent-relief-nigeria.html", smap)
        self.assertEqual(smap.count("rent-relief-nigeria.html"), 1)

    def test_the_homepage_links_the_guides_not_the_states_twice(self):
        idx = INDEX.read_text(encoding="utf-8")
        i = idx.index("Free guides — the questions Nigerians ask first")
        block = idx[i:idx.index("</div>", i)]
        self.assertIn('href="rent-relief-nigeria.html"', block)
        self.assertIn('href="notice-to-quit-nigeria.html"', block)
        self.assertNotIn('href="tenancy-agreement-lagos.html"', block)   # that is the State guides block's job

    def test_the_letter_and_calculator_widgets_are_on_the_page(self):
        t = _page()
        for el in ("rr_rent", "rr_months", "rr_income", "rr_out", "rr_name", "rr_lltin", "rr_sheet", "rrPrint"):
            self.assertIn(el, t)
        self.assertIn("rent_relief_letter", t)                 # the GA4 event the stop/continue rule reads
        self.assertIn("Made free with DocOga", t)

    def test_the_print_rules_are_scoped_to_this_page_only(self):
        """The letter prints alone — but the other seven guides must still print whole."""
        other = (SITE / "tenancy-agreement-nigeria.html").read_text(encoding="utf-8")
        self.assertNotIn(".box:not(.printme)", other)
        self.assertIn(".box:not(.printme)", _page())

    def test_the_generator_is_the_source_of_truth(self):
        gen = GEN.read_text(encoding="utf-8")
        self.assertIn('PAGES["rent-relief-nigeria.html"]', gen)
        self.assertIn("WIDGET_RENT_RELIEF", gen)
        # the receipt fine everywhere in the generator is the gazetted figure
        self.assertNotIn("₦10,000 fine", gen.replace("the ₦10,000 figure", ""))
        self.assertIn("₦100,000", gen)


class ReceiptFieldTests(unittest.TestCase):
    def test_the_receipt_gained_the_two_tax_fields_and_keeps_its_canonical(self):
        idx = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="r_from_addr"', idx)
        self.assertIn('id="r_tin"', idx)
        self.assertIn("r_from_addr:$('r_from_addr').value, r_tin:$('r_tin').value", idx)
        self.assertIn("['r_from_addr','r_from_addr']", idx)
        self.assertIn("['r_tin','r_tin']", idx)
        self.assertIn("TIN/NIN: '+esc(d.r_tin)", idx)
        self.assertIn('href="rent-relief-nigeria.html"', idx)
        # the ledger fingerprint must not change shape: still the six fixed fields
        self.assertIn("return ['v1',n(f.date),amt,n(f.from),n(f.issuer),n(f.property),n(f.period)].join('|');", idx)


class BrainTests(unittest.TestCase):
    def test_the_editor_knows_the_season_and_the_pinned_story_is_sourced(self):
        strat = (ROOT / "brain" / "strategy.md").read_text(encoding="utf-8")
        self.assertIn("Rent-relief season", strat)
        self.assertIn("s.30(2)(a)(vi)", strat)
        rows = json.loads((ROOT / "brain" / "newsdesk_pinned.json").read_text(encoding="utf-8"))
        items = rows["items"] if isinstance(rows, dict) else rows
        hit = [r for r in items if "Rent relief" in r.get("title", "")]
        self.assertEqual(len(hit), 1)
        self.assertIn("docoga.com.ng/rent-relief-nigeria.html", hit[0]["link"])
        self.assertIn("never call it automatic", hit[0]["note"].lower())


@unittest.skipUnless(HAS_JSDOM, "node + jsdom (npm install) needed to run the page's own script")
class ArithmeticTests(unittest.TestCase):
    SCRIPT = r"""
const {JSDOM}=require('jsdom');const fs=require('fs');
const dom=new JSDOM(fs.readFileSync(process.argv[1],'utf8'),{runScripts:'dangerously'});
const w=dom.window,d=w.document,R=w.DocOgaRentRelief;
d.getElementById('rr_rent').value='1500000';d.getElementById('rr_income').value='6000000';
d.getElementById('rr_rent').dispatchEvent(new w.Event('input'));
d.getElementById('rr_name').value='Chinedu Okafor';d.getElementById('rr_name').dispatchEvent(new w.Event('input'));
console.log(JSON.stringify({
  r15:R.relief(1500000), r40:R.relief(4000000), r24h:R.relief(2400000,6), r0:R.relief(0),
  t6m:R.tax(6000000), t800k:R.tax(800000), t3m:R.tax(3000000), t60m:R.tax(60000000),
  out:d.getElementById('rr_out').textContent, sheet:d.getElementById('rr_sheet').textContent}));
"""

    def test_the_formula_and_the_bands_in_the_visitors_own_javascript(self):
        r = subprocess.run([NODE, "-e", self.SCRIPT, str(PAGE)], capture_output=True, text=True, cwd=ROOT, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        got = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(got["r15"], 300000)          # 20% of 1.5m
        self.assertEqual(got["r40"], 500000)          # cap
        self.assertEqual(got["r24h"], 240000)         # 2.4m, six months in the year → 1.2m × 20%
        self.assertEqual(got["r0"], 0)
        self.assertEqual(got["t800k"], 0)             # first ₦800k at 0%
        self.assertEqual(got["t3m"], 330000)          # + 2.2m at 15%
        self.assertEqual(got["t6m"], 870000)          # + 3m at 18%
        # 0 + 330k + 1.62m + 2.73m + 5.75m + 10m×25%
        self.assertEqual(got["t60m"], 330000 + 1620000 + 2730000 + 5750000 + 2500000)
        self.assertIn("₦300,000", got["out"])
        self.assertIn("₦54,000", got["out"])          # 300k deduction at the 18% band
        self.assertIn("Chinedu Okafor", got["sheet"])
        self.assertIn("section 30(2)(a)(vi)", got["sheet"])


if __name__ == "__main__":
    unittest.main()
