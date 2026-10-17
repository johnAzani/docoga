"""Night one (17 Oct 2026): three of five brain attempts were refused for body lines of 115–125
characters. tidy() re-breaks such a line at a sentence/clause boundary before the gates — layout
only, never a word — so the second Gemini call is spent on substance, not spacing."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import brain  # noqa: E402

CTX = {"facts": [], "facts_by_id": {}, "short_day": False, "hook_binding": False}

LONG = ("If your landlord in Lagos asks for two years' rent upfront on a yearly tenancy, "
        "the Tenancy Law 2011 says that demand is unlawful; keep the receipt.")


class TidyTests(unittest.TestCase):
    def test_an_over_long_line_is_rebroken_at_a_clause_and_no_word_changes(self):
        self.assertGreater(len(LONG), brain.LINE_MAX)
        pack = brain.tidy({"post": {"headline": "h", "lines": ["Short one.", LONG]}})
        lines = pack["post"]["lines"]
        self.assertEqual(len(lines), 3)
        self.assertTrue(all(len(ln) <= brain.LINE_MAX for ln in lines))
        self.assertEqual(" ".join(lines[1:]), LONG)
        self.assertEqual(brain.lint(pack, CTX, [])
                         .count("a body line is"), 0)

    def test_a_line_that_fits_is_left_exactly_as_written(self):
        pack = brain.tidy({"post": {"headline": "h", "lines": ["One.", "Two  spaces stay."]}})
        self.assertEqual(pack["post"]["lines"], ["One.", "Two  spaces stay."])

    def test_when_the_reflow_would_pass_five_lines_lint_still_refuses(self):
        pack = brain.tidy({"post": {"headline": "h", "lines": ["a b", "c d", "e f", "g h", LONG]}})
        self.assertEqual(len(pack["post"]["lines"]), 5)
        self.assertTrue(any("a body line is" in p for p in brain.lint(pack, CTX, [])))

    def test_a_line_with_no_boundary_is_not_cut_mid_word(self):
        pack = brain.tidy({"post": {"headline": "h", "lines": ["a b", "x" * 130]}})
        self.assertEqual(pack["post"]["lines"][1], "x" * 130)

    def test_plan_day_runs_the_pencil_before_the_gates(self):
        src = Path(brain.__file__).read_text(encoding="utf-8")
        self.assertIn("pack = tidy(gemini_text.generate_json(", src)


if __name__ == "__main__":
    unittest.main()
