"""The law shelf speaks in full sentences, and the verifier sees the statute's name.

25–27 Oct 2026: the editor's Short on the Lagos receipt law was refused six times in three days
and Monday 27 Oct had no Short. The verifier was right every time — the shelf showed s.5(2)'s
contents as five headless fragments ("the amount of rent paid") and the fact lines carried no
statute name, so "under the Lagos Tenancy Law 2011 the receipt must state the amount" matched
nothing. The shelf is the source of truth; it must be checkable as written.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import law_index  # noqa: E402
import brain  # noqa: E402


class ShelfSentences(unittest.TestCase):
    def test_list_items_under_an_opening_clause_carry_the_clause(self):
        facts = {f["id"]: f for f in law_index.facts_for("lagos")}
        for n, tail in ((2, "the date on which the rent was received"), (3, "the names and addresses of the landlord and the tenant"),
                        (4, "the description and location of the premises"), (5, "the amount of rent paid"),
                        (6, "the period to which the payment relates")):
            f = facts["lagos:receipts:%d" % n]
            self.assertEqual(f["text"], "s.5(2): the receipt must state %s." % tail)
            self.assertEqual(f["cite"], "s.5(2)")
        self.assertIn("₦100,000", facts["lagos:receipts:7"]["text"])     # the penalty line untouched

    def test_ids_are_stable_and_the_stem_touches_nothing_else(self):
        ids = [f["id"] for f in law_index.all_facts()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("lagos:notice_ladder:1", ids)
        stemmed = [f for f in law_index.all_facts() if f["text"].startswith("s.5(2): the receipt must state ")]
        self.assertEqual(sorted(f["id"] for f in stemmed), ["lagos:receipts:%d" % n for n in range(2, 7)])

    def test_stem_helper(self):
        self.assertEqual(law_index._stem("Lagos prescribes it. s.5(2): the receipt must state —"), "s.5(2): the receipt must state")
        self.assertEqual(law_index._stem("A full sentence."), "")
        self.assertEqual(law_index._stem(""), "")

    def test_shelf_and_verifier_lines_name_the_statute(self):
        line = law_index.shelf_text("lagos").splitlines()[0]
        self.assertIn(" | Tenancy Law of Lagos State 2011 s.", line)
        facts = {f["id"]: f for f in law_index.facts_for("lagos") if f["id"].startswith("lagos:receipts")}
        pack = {"claims": [{"fact_id": "lagos:receipts:5", "text": "x"}], "post": {"headline": "H", "body": ["b"], "cta": "c"}, "threads": {"text": "t"}}
        prompt = brain.verify_prompt(pack, facts)
        self.assertIn("lagos:receipts:5 | Tenancy Law of Lagos State 2011 s.5(2) | s.5(2): the receipt must state the amount of rent paid.", prompt)
        self.assertIn("statute name and section shown", brain.VERIFY_SYSTEM)
        self.assertIn("same number, period or amount", brain.VERIFY_SYSTEM)   # strictness on numbers stays


if __name__ == "__main__":
    unittest.main()
