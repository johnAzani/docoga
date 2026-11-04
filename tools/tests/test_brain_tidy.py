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

    def test_when_the_reflow_passes_five_lines_short_neighbours_are_joined(self):
        # 24 Oct 2026: a 144-character line in a five-line post was refused twice and the day fell
        # back to the rotation. The reflow makes six lines; the two shortest neighbours are joined.
        pack = brain.tidy({"post": {"headline": "h", "lines": ["a b", "c d", "e f", "g h", LONG]}})
        lines = pack["post"]["lines"]
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0], "a b c d")
        self.assertEqual(" ".join(lines).split(), "a b c d e f g h".split() + LONG.split(), "layout only")
        self.assertFalse(any("a body line is" in p for p in brain.lint(pack, CTX, [])))

    def test_a_sixth_line_is_the_reflows_one_line_of_slack(self):
        # 26 Oct 2026, 1:31am: four wide lines, one of 157 characters — six after the re-break,
        # no neighbours short enough to join. Six is accepted; the model is still asked for five.
        wide = "w" * 100
        pack = brain.tidy({"post": {"headline": "h", "lines": [wide, wide, wide, LONG]}})
        self.assertEqual(len(pack["post"]["lines"]), 5)
        pack = brain.tidy({"post": {"headline": "h", "lines": [wide, wide, wide, wide, LONG]}})
        self.assertEqual(len(pack["post"]["lines"]), 6)
        self.assertFalse(any("a body line is" in p or "post.lines must be" in p for p in brain.lint(pack, CTX, [])))
        self.assertEqual(brain.LINES_MAX, 6)

    def test_when_the_reflow_passes_six_lines_lint_still_refuses(self):
        wide = "w" * 100
        pack = brain.tidy({"post": {"headline": "h", "lines": [wide, wide, wide, wide, wide, LONG]}})
        self.assertEqual(len(pack["post"]["lines"]), 6, "left for lint, untouched")
        self.assertTrue(any("a body line is" in p for p in brain.lint(pack, CTX, [])))

    def test_a_line_with_no_boundary_is_not_cut_mid_word(self):
        pack = brain.tidy({"post": {"headline": "h", "lines": ["a b", "x" * 130]}})
        self.assertEqual(pack["post"]["lines"][1], "x" * 130)

    def test_plan_day_runs_the_pencil_before_the_gates(self):
        src = Path(brain.__file__).read_text(encoding="utf-8")
        self.assertIn("raw = gemini_text.generate_json(", src)
        self.assertIn("leaked = inline_fact_ids(raw)", src)
        self.assertIn("pack = tidy(raw)", src)
        self.assertLess(src.index("leaked = inline_fact_ids(raw)"), src.index("pack = tidy(raw)"),
                        "the leak is read before the pencil erases it")
        self.assertLess(src.index("pack = tidy(raw)"), src.index("problems = lint(pack, ctx, said)"))

    def test_a_fact_id_typed_into_the_copy_is_a_refusal_and_a_lesson_not_a_silent_clean(self):
        """4 Nov 2026 (🔒 docs/BRAIN_GROWTH.md): the 4/5/6 Nov packs carried ids inline; tidy cleaned
        them and the model never heard. Now the gate names them and the lessons loop counts them."""
        raw = {"post": {"headline": "Ask for the receipt (lagos:receipts:1)",
                        "lines": ["It is the law (lagos:receipts:2; lagos:receipts:3).", "Clean line."]},
               "threads": {"text": "fine"},
               "claims": [{"text": "x", "fact_id": "lagos:receipts:1"}]}
        leaked = brain.inline_fact_ids(raw)
        self.assertEqual(sorted(set(leaked)), ["lagos:receipts:1", "lagos:receipts:2; lagos:receipts:3"])
        self.assertEqual(brain.inline_fact_ids({"post": {"lines": ["no ids here"]}, "claims": [{"fact_id": "lagos:receipts:1"}]}), [],
                         "ids in `claims` are where they belong")
        pack = brain.tidy(raw)
        self.assertNotIn("lagos:", pack["post"]["headline"] + " ".join(pack["post"]["lines"]), "still cleaned for the reader")
        src = Path(brain.__file__).read_text(encoding="utf-8")
        self.assertIn('"fact id typed into the copy: %s', src)
        self.assertIn("fact_id_in_copy", [k for k, _, _ in brain.LESSON_FAMILIES])
        family, lesson = brain._lesson_family("fact id typed into the copy: lagos:receipts:1 — ids live only in `claims`")
        self.assertEqual(family, "fact_id_in_copy")
        self.assertIn("claims[].fact_id", lesson)


if __name__ == "__main__":
    unittest.main()
