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
        self.assertIn("nigeria:rent_relief:1", hit[0]["note"])


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


class JrbGuidelinesTests(unittest.TestCase):
    """28 Oct 2026: the Joint Revenue Board's PIT Guidelines 2026 para 9.6 name the four particulars a
    rent-relief claim needs. The page quotes them; the receipt tool checks for them and says so in print;
    the shelf carries them (nigeria:rent_relief:4) and the shared-tenancy / actual-year rule (:8)."""

    def test_the_page_quotes_paragraph_9_6_and_the_shared_tenancy_rule(self):
        t = PAGE.read_text(encoding="utf-8")
        self.assertIn("Personal Income Tax Guidelines, 2026", t)
        self.assertIn("9.6 Minimum information", t)
        self.assertIn("one of</b> mobile number, Tax ID or NIN", t)
        self.assertIn("9.3 Shared tenancy", t)
        self.assertIn("₦1,000,000 for 2026, relief ₦200,000", t)

    def test_the_receipt_tool_checks_the_four_particulars_without_touching_the_canonical(self):
        idx = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="rr-check"', idx)
        self.assertIn("function rentReliefMissing(d)", idx)
        self.assertIn("rentReliefLine(d)+\nreceiptVerifyLine(d)+", idx)
        self.assertIn("para 9.6 of the Joint Revenue Board", idx)
        # the ledger fingerprint reads the same six fields as before (workers/ledger/index.js mirrors it)
        self.assertIn("function receiptFields(d){ return {date:d.r_date,amount:d.r_amt,from:d.r_from,issuer:d.r_issuer,property:d.r_prop,period:d.r_period}; }", idx)

    def test_the_shelf_carries_the_four_particulars_and_the_shared_tenancy_rule(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import law_index
        by = {f["id"]: f["text"] for f in law_index.federal_facts()}
        self.assertIn("para 9.6", by["nigeria:rent_relief:4"])
        for piece in ("legal tenant's name", "period covered", "mobile number, Tax ID or NIN", "property address",
                      "what HR and tax offices ask for"):
            self.assertIn(piece, by["nigeria:rent_relief:4"], piece)
        self.assertIn("each tenant", by["nigeria:rent_relief:8"])
        self.assertIn("₦1,000,000 for 2026", by["nigeria:rent_relief:8"])


@unittest.skipUnless(HAS_JSDOM, "node + jsdom (npm install) needed to run the page's own script")
class ReceiptRentReliefDomTests(unittest.TestCase):
    SCRIPT = r"""
const {JSDOM}=require('jsdom');const fs=require('fs');
const dom=new JSDOM(fs.readFileSync(process.argv[1],'utf8'),{runScripts:'dangerously',url:'https://docoga.com.ng/'});
const w=dom.window,d=w.document;
const set=(id,v)=>{const e=d.getElementById(id);e.value=v;};
set('r_from','Chinedu Okafor');set('r_amt','1200000');set('r_period','Jan 2026 – Dec 2026');set('r_issuer','Mrs A. Bello');
const before=w.renderReceipt();
const chk1=d.getElementById('rr-check').textContent;
set('r_prop','12 Allen Avenue, Ikeja, Lagos');set('r_phone','08012345678');
const after=w.renderReceipt();
console.log(JSON.stringify({chk1:chk1,chk2:d.getElementById('rr-check').textContent,
  before:before.includes('para 9.6'),after:after.includes('para 9.6'),
  canon:w.receiptCanonical(w.receiptFields(w.collectReceipt()))}));
"""

    def test_the_check_names_what_is_missing_and_the_print_line_appears_only_when_complete(self):
        r = subprocess.run([NODE, "-e", self.SCRIPT, str(ROOT / "site" / "index.html")],
                           capture_output=True, text=True, cwd=ROOT, timeout=90)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        got = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertIn("Not yet", got["chk1"])
        self.assertIn("property address", got["chk1"])
        self.assertIn("landlord's name + phone, TIN or NIN", got["chk1"])
        self.assertFalse(got["before"])
        self.assertIn("Rent-relief ready", got["chk2"])
        self.assertTrue(got["after"])
        self.assertNotIn("9.6", got["canon"])


if __name__ == "__main__":
    unittest.main()


class FederalShelfTests(unittest.TestCase):
    """The brain refused its first rent-relief post on 28 Oct 1:32am ('price ₦500,000 is neither ours nor
    in a cited fact', 'statistic 20% is not in a cited fact', 'claim cites unknown fact id 2026-10-27')
    because the law lived in strategy.md and the newsdesk, not on the shelf. Now it is a federal fact
    every state's shelf carries, citable from any state."""

    def test_the_federal_facts_carry_the_numbers_the_gates_look_for(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import law_index
        fed = {f["id"]: f for f in law_index.federal_facts()}
        one = fed["nigeria:rent_relief:1"]
        self.assertEqual(one["cite"], "s.30(2)(a)(vi)")
        self.assertEqual(one["statute"], "Nigeria Tax Act 2025")
        for needle in ("20%", "₦500,000", "accurately declares"):
            self.assertIn(needle, one["text"])
        texts = " ".join(f["text"] for f in fed.values())
        for needle in ("31 January 2027", "31 March 2027", "Tax ID or NIN", "₦240,000", "₦800,000", "25% above ₦50,000,000", "₦0"):
            self.assertIn(needle, texts)
        self.assertFalse(any(len(f["text"]) >= law_index.MAX_TEXT for f in fed.values()), "a clipped fact loses its numbers")

    def test_every_state_shelf_ends_with_the_federal_facts_and_the_rotation_never_picks_nigeria(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import law_index
        lagos = law_index.facts_for("lagos")
        self.assertEqual(lagos[-1]["id"], "nigeria:rent_relief:8")
        self.assertTrue(all(f["slug"] == "lagos" for f in lagos[:-8]))
        self.assertEqual(law_index.facts_for("nigeria"), law_index.federal_facts())
        self.assertNotIn("nigeria", [s for s, _, _ in law_index.states()])
        ids = [f["id"] for f in law_index.all_facts()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(law_index.is_federal(lagos[-1]) and not law_index.is_federal(lagos[0]))

    def test_a_federal_claim_passes_the_state_and_number_gates_from_any_state(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import law_index, brain
        sys.path.insert(0, str(ROOT / "tools" / "tests"))
        import test_brain
        from datetime import date
        pack = test_brain.good_pack()
        ctx = brain.day_context(date(2026, 10, 26), said=[])
        ctx["facts_by_id"] = {f["id"]: f for f in ctx["facts"]}
        pack["state"] = ctx["state"]
        state = ctx["state"]
        pack["claims"] = [{"fact_id": "nigeria:rent_relief:1", "text": "20% of rent, max ₦500,000"}]
        pack["post"]["lines"] = ["Under s.30 of the Nigeria Tax Act 2025 you deduct 20% of the rent you paid, up to ₦500,000.",
                                 "It is claimed, not automatic: your receipt and agreement are the evidence."]
        pack["post"]["headline"] = "Your rent cuts your tax from 2026"
        problems = brain.lint(pack, ctx, [])
        bad = [p for p in problems if "cited fact" in p or "belongs to" in p or "unknown fact id" in p or "name the state" in p]
        self.assertEqual(bad, [])


class NewsHookTests(unittest.TestCase):
    """11 of the brain's first 20 refusals were 'news_hook is not one of this week's NEWSDESK headlines'
    — honest shortenings of a 200-character headline, each one a day's post lost."""

    NEWS = [{"title": "Rent relief season: from 2026 tenants deduct 20% of rent (max ₦500,000) — only with a receipt in their name"},
            {"title": "Viral video: Lagos landlord reportedly punched by tenant after proposing a ₦200k → ₦350k rent jump on renewal"}]

    def test_exact_opening_clause_and_most_words_match_but_invented_stories_do_not(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import brain
        m = lambda h: brain.news_hook_matches(h, self.NEWS)  # noqa: E731
        self.assertTrue(m(self.NEWS[0]["title"]))
        self.assertTrue(m("Rent relief season: from 2026 tenants deduct 20% of rent (max ₦500,000)"))
        self.assertTrue(m("Viral video: Lagos landlord reportedly punched by tenant after proposing a rent jump"))
        self.assertTrue(m("Lagos landlord punched by tenant after proposing ₦200k to ₦350k rent jump on renewal"))
        self.assertFalse(m("Senate passes rent control act"))
        self.assertFalse(m("Lagos"))
        self.assertFalse(m(""))

    def test_the_pinned_story_is_headline_length_and_its_note_reaches_the_prompt(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import newsdesk
        rows = json.loads((ROOT / "brain" / "newsdesk_pinned.json").read_text(encoding="utf-8"))
        items = rows["items"] if isinstance(rows, dict) else rows
        hit = [r for r in items if r["title"].startswith("Rent relief season")][0]
        self.assertLessEqual(len(hit["title"]), 120)
        block = newsdesk.prompt_block([hit])
        self.assertIn("note: Nigeria Tax Act 2025", block)
        self.assertIn("MUST cite nigeria:rent_relief:1", block)
