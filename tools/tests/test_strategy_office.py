"""The Strategy Office charter (docs/STRATEGY_OFFICE.md) — locked by the owner on 27 Oct 2026.

These pins are the lock: the charter must keep its ten standing questions, the four buckets,
the ten-section analysis format, the ₦0 rule, the research-first rule, the no-invention rule
and the Monday cadence. Rewording is fine; dropping any of them is not.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHARTER = ROOT / "docs" / "STRATEGY_OFFICE.md"


class StrategyOfficeLock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CHARTER.read_text(encoding="utf-8")

    def test_the_charter_exists_and_names_the_role(self):
        self.assertIn("Chief Strategy, Innovation, Research and Growth Officer", self.text)
        self.assertIn("Lock it in", self.text)

    def test_the_ten_standing_questions_are_all_there(self):
        for q in ("What are we missing?", "What can we improve?",
                  "What new opportunities are emerging?",
                  "What problems are customers experiencing that we could solve?",
                  "What new products or features should we build?",
                  "What are competitors doing better than us?",
                  "What can we do that competitors have not thought of?",
                  "What new technologies could transform our business?",
                  "How can we generate more revenue without unnecessarily increasing costs?",
                  "What should we do today to make the company stronger in the future?"):
            self.assertIn(q, self.text)

    def test_the_four_buckets_and_the_ten_sections(self):
        for b in ("DO NOW", "TEST NEXT", "PLAN FOR LATER", "REJECT / AVOID"):
            self.assertIn(b, self.text)
        for s in ("Current position", "Important discoveries", "Opportunities", "Recommendation",
                  "Implementation plan", "Resources and costs", "Expected value", "Risks",
                  "Next action", "Additional insight"):
            self.assertIn(s, self.text)

    def test_the_rules_that_must_never_drop(self):
        self.assertIn("₦0", self.text)
        self.assertRegex(self.text, re.compile(r"Research .*before", re.I))
        self.assertRegex(self.text, re.compile(r"Never invent research", re.I))
        self.assertIn("Every Monday", self.text)
        self.assertIn("Strategy desk", self.text)
        self.assertIn("docoga-private", self.text)       # money/strategy writing lives privately
        self.assertIn("silence = go", self.text)          # the owner still charts direction


if __name__ == "__main__":
    unittest.main()
