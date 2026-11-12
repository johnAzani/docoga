"""The snippet rule (🔒 docs/GROWTH.md, 12 Nov 2026): every title fits a result, every description is
unique and carries the number, and the Monday scorecard names the page-one pages losing the tap."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import snippet_audit as sa  # noqa: E402
import gen_state_pages as gsp  # noqa: E402
import guides_build as gb  # noqa: E402


def page(title, desc):
    return '<!DOCTYPE html><html><head><title>%s</title><meta name="description" content="%s"></head><body></body></html>' % (title, desc)


class Rules(unittest.TestCase):
    def test_the_four_rules_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            (site / "guides").mkdir()
            (site / "a.html").write_text(page("Short title", "x" * 100), encoding="utf-8")
            (site / "b.html").write_text(page("T" * 61, "y" * 100), encoding="utf-8")
            (site / "c.html").write_text(page("Cut title…", "z" * 50), encoding="utf-8")
            (site / "d.html").write_text(page("Short title", "x" * 100), encoding="utf-8")
            (site / "admin.html").write_text(page("A" * 90, ""), encoding="utf-8")
            (site / "guides" / "g.html").write_text(page("Guide", "w" * 161), encoding="utf-8")
            problems = sa.audit(site)
        joined = "\n".join(problems)
        self.assertIn("b.html: title 61 chars (max 60)", joined)
        self.assertIn("c.html: title ends in an ellipsis", joined)
        self.assertIn("c.html: description 50 chars", joined)
        self.assertIn("d.html: same title as a.html", joined)
        self.assertIn("d.html: same description as a.html", joined)
        self.assertIn("guides/g.html: description 161 chars", joined)
        self.assertNotIn("admin.html", joined, "the owner's pages are not search snippets")
        self.assertEqual(len(problems), 6)

    def test_the_real_site_passes(self):
        self.assertEqual(sa.audit(), [], "a page broke the snippet rule — fix the generator, not the test")

    def test_underperformers_rank_page_one_pages_under_the_floor_by_lost_clicks(self):
        data = {"top_pages": [
            {"page": "https://docoga.com.ng/edo", "clicks": 1, "impressions": 55, "position": 6.3},
            {"page": "https://docoga.com.ng/poa", "clicks": 1, "impressions": 57, "position": 4.7},
            {"page": "https://docoga.com.ng/fine", "clicks": 5, "impressions": 38, "position": 3.4},
            {"page": "https://docoga.com.ng/few", "clicks": 0, "impressions": 4, "position": 2.0},
            {"page": "https://docoga.com.ng/deep", "clicks": 0, "impressions": 40, "position": 14.6}]}
        rows = sa.underperformers(data)
        self.assertEqual([r["page"] for r in rows], ["/poa", "/edo"], "page one, enough impressions, under the floor; worst gap first")
        self.assertEqual(sa.underperformers({}), [])
        self.assertEqual(sa.underperformers(None), sa.underperformers(sa.load()) if sa.load() else [])

    def test_the_scorecard_block_never_raises_and_names_the_rule(self):
        lines = sa.scorecard_lines(path="/nonexistent/search_console.json")
        self.assertTrue(lines[0].startswith("- snippets in the rules: "))
        self.assertTrue(any(l.startswith("- snippets losing the tap") for l in lines))
        src = (ROOT / "tools" / "brain_scorecard.py").read_text(encoding="utf-8")
        self.assertIn("snippet_audit.scorecard_lines()", src, "the Monday scorecard prints the block")
        qa = (ROOT / "tools" / "qa.py").read_text(encoding="utf-8")
        self.assertIn('"snippet_audit.py"), "--check"', qa, "qa fails when a page breaks the rule")


class StatePages(unittest.TestCase):
    def test_every_state_page_title_fits_and_the_description_carries_its_own_numbers(self):
        seen = set()
        for slug, st in gsp.STATES.items():
            for tslug, t in gsp.TOOLS.items():
                title, desc = gsp.snippet_for(slug, tslug, t, st)
                self.assertLessEqual(len(title), 60, title)
                self.assertTrue(70 <= len(desc) <= 160, (len(desc), desc))
                self.assertNotIn(desc, seen, "twelve state pages shared one description before 12 Nov 2026")
                seen.add(desc)
                if tslug in ("notice-to-quit", "tenancy-law"):
                    monthly, yearly = gsp.ladder_brief(slug)
                    self.assertIn(monthly, desc)
                    self.assertIn(yearly, desc)
                self.assertFalse(desc.endswith((" and.", " or.", " 2.", " as.", "we.")), "a description cut mid-phrase: " + desc)

    def test_the_ladder_is_read_from_the_shelf_not_typed(self):
        self.assertEqual(gsp.ladder_brief("lagos"), ("1 month", "6 months"))
        self.assertEqual(gsp.ladder_brief("abuja"), ("1 month", "6 months"), "'one calendar month' and 'half a year (six calendar months)' normalise")
        self.assertEqual(gsp.short_place(gsp.STATES["rivers"]), "Rivers (Port Harcourt)", "the city stays — people search it")
        self.assertEqual(gsp.law_place("abuja", gsp.STATES["abuja"]), "FCT Abuja")
        self.assertEqual(gsp.fit_title("Base", [" + a very long tail that cannot fit in sixty characters at all, surely", " + ok"]), "Base + ok")

    def test_the_verified_state_names_its_statute_and_the_unverified_one_says_so(self):
        t = gsp.TOOLS["notice-to-quit"]
        self.assertIn("under the Tenancy Law of Lagos State 2011", gsp.snippet_for("lagos", "notice-to-quit", t, gsp.STATES["lagos"])[1])
        self.assertIn("(the general Nigerian rule)", gsp.snippet_for("kaduna", "notice-to-quit", t, gsp.STATES["kaduna"])[1])
        law = gsp.TOOLS["tenancy-law"]
        self.assertTrue(gsp.snippet_for("kaduna", "tenancy-law", law, gsp.STATES["kaduna"])[1].startswith("Kaduna State tenancy law: no statute verified yet"))
        html = (ROOT / "site" / "notice-to-quit-edo.html").read_text(encoding="utf-8")
        self.assertIn("<h1>Notice to Quit in Edo State (Benin City): How Many Months</h1>", html, "the heading keeps the word State")
        self.assertIn("<title>Notice to Quit in Edo (Benin City): How Many Months</title>", html)


class GuideTitles(unittest.TestCase):
    def test_the_guide_title_cuts_at_a_clause_or_a_word_never_with_an_ellipsis_or_a_split_name(self):
        f = gb.title_tag_for
        self.assertEqual(f("Abuja quit notice checklist: 4 rules your landlord must meet", "Abuja (FCT)"),
                         "Abuja quit notice checklist: 4 rules your landlord must meet", "no ' | DocOga' — the site name prints on its own line")
        self.assertEqual(f("Transfer alert to an agent is not a rent receipt", "Rivers"), "Transfer alert to an agent is not a rent receipt — Rivers")
        self.assertEqual(f("How many months' rent can your landlord demand in Cross River?", "Cross River"),
                         "How many months' rent can your landlord demand — Cross River")
        self.assertEqual(f("Cross River Tenancy Law: How Much Notice Must You Give (Or Get)?", "Cross River"),
                         "Cross River Tenancy Law: How Much Notice")
        for h in ("A" * 80, "word " * 30, "Your Lagos rent receipt is worth up to ₦500,000 in tax relief from 2026"):
            t = f(h, "Lagos")
            self.assertLessEqual(len(t), 60)
            self.assertFalse(t.endswith("…"))

    def test_retitle_reaches_pages_whose_draft_was_pruned_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            (site / "guides").mkdir()
            long = "Abuja quit notice checklist: 4 rules your landlord must meet — Abuja (FCT) | DocOga"
            (site / "guides" / "x.html").write_text(
                '<title>%s</title><meta property="og:title" content="%s"><meta property="og:image:alt" content="%s">'
                '<script type="application/ld+json">{"headline": "Abuja quit notice checklist: 4 rules your landlord must meet"}</script>'
                % (long, long, long), encoding="utf-8")
            (site / "guides" / "ok.html").write_text("<title>Fits</title>", encoding="utf-8")
            changed = gb.retitle(site=site, log=lambda *a: None)
            self.assertEqual(changed, ["x.html"])
            out = (site / "guides" / "x.html").read_text(encoding="utf-8")
            self.assertEqual(out.count("Abuja quit notice checklist: 4 rules your landlord must meet"), 4)
            self.assertNotIn("| DocOga", out)
            self.assertEqual(gb.retitle(site=site, log=lambda *a: None), [])
        src = (ROOT / "tools" / "guides_build.py").read_text(encoding="utf-8")
        self.assertIn("retitle(site=site, log=log)", src.split("def build(", 1)[1], "the nightly build runs it")


if __name__ == "__main__":
    unittest.main()
