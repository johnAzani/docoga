"""Shelf recall (3 Nov 2026, docs/BRAIN_GROWTH.md): 60 "not on the shelf" refusals in 30 days were read
back — twelve of them were Lagos s.5(2) receipt lines that ARE on the shelf (lagos:receipts:2–6); the
writer had not declared the id. The verifier now sees the rest of the state's shelf, names the fact,
and the claim is adopted with its id. What is still off the shelf is still refused — and the Monday
scorecard sorts those into "recall" and "research target" by state and topic."""
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import brain  # noqa: E402
import brain_scorecard as sc  # noqa: E402
import law_index  # noqa: E402

FACTS = law_index.by_id()
PACK = {"state": "lagos", "theme": "receipt-lines",
        "claims": [{"text": "A landlord who fails to issue the receipt is liable to a ₦100,000 fine.", "fact_id": "lagos:receipts:7"}],
        "post": {"headline": "Your receipt must say five things", "lines": [
            "The receipt must state the names and addresses of the landlord and the tenant.",
            "A landlord who fails to issue the receipt is liable to a ₦100,000 fine.",
            "A bank alert is never a receipt in any state of Nigeria."], "cta": "Make yours at DocOga.", "hashtags": []},
        "threads": {"text": "Your receipt must say five things."}}


def verdict_with_recall():
    return {"verdicts": [{"fact_id": "lagos:receipts:7", "claim": "fine", "supported": True, "reason": "same"}],
            "recalled": [{"statement": "The receipt must state the names and addresses of the landlord and the tenant.",
                          "fact_id": "lagos:receipts:3"},
                         {"statement": "made up", "fact_id": "lagos:nothing:9"}],
            "unsupported_statements": ["The receipt must state the names and addresses of the landlord and the tenant.",
                                       "A bank alert is never a receipt in any state of Nigeria."]}


class Prompt(unittest.TestCase):
    def test_the_verifier_sees_the_rest_of_the_shelf_only_when_given_one(self):
        cited = {"lagos:receipts:7": FACTS["lagos:receipts:7"]}
        plain = brain.verify_prompt(PACK, cited)
        self.assertNotIn("THE REST OF THE SHELF", plain)
        self.assertNotIn('"recalled"', plain)
        rest = {k: v for k, v in FACTS.items() if k.startswith("lagos:") and k not in cited}
        full = brain.verify_prompt(PACK, cited, shelf=rest)
        self.assertIn("THE REST OF THE SHELF (verified facts the writer did not cite)", full)
        self.assertIn("lagos:receipts:3 |", full)
        self.assertIn('"recalled": [', full)
        self.assertIn("and not in the rest of the shelf", full)
        self.assertLess(full.index("FACTS (the only law"), full.index("THE REST OF THE SHELF"))


class Verify(unittest.TestCase):
    def test_a_recalled_statement_becomes_a_cited_claim_and_the_rest_stays_refused(self):
        pack = json.loads(json.dumps(PACK))
        ctx = {"facts_by_id": {k: v for k, v in FACTS.items() if k.startswith("lagos:")}}
        seen = {}

        def fake_generate(prompt, **kw):
            seen["prompt"] = prompt
            return verdict_with_recall()

        with mock.patch.object(brain.gemini_text, "generate_json", fake_generate):
            problems = brain.verify(pack, ctx, log=lambda *a: None)
        self.assertIn("THE REST OF THE SHELF", seen["prompt"])
        self.assertEqual(problems, ["verifier: legal statement not on the shelf — 'A bank alert is never a receipt in any state of Nigeria.'"])
        ids = [c["fact_id"] for c in pack["claims"]]
        self.assertEqual(ids, ["lagos:receipts:7", "lagos:receipts:3"], "the recalled fact is adopted; the invented id is not")
        self.assertTrue(pack["claims"][1].get("recalled"))
        self.assertEqual(pack["recalled"], ["lagos:receipts:3"])

    def test_the_deep_dive_verifier_recalls_the_same_way(self):
        ep = {"title": "Receipts", "claims": [{"text": "fine", "fact_id": "lagos:receipts:7"}],
              "sections": [{"n": 1, "title": "Names", "narration": "The receipt must state the names and addresses of the landlord and the tenant."}]}
        facts_by_id = {k: v for k, v in FACTS.items() if k.startswith("lagos:")}
        with mock.patch.object(brain.gemini_text, "generate_json", lambda prompt, **kw: verdict_with_recall()):
            out = brain.deepdive_verify(ep, facts_by_id, log=lambda *a: None)
        self.assertEqual(len(out), 1)
        self.assertIn("bank alert", out[0])
        self.assertEqual([c["fact_id"] for c in ep["claims"]], ["lagos:receipts:7", "lagos:receipts:3"])

    def test_nothing_recalled_means_nothing_changes(self):
        pack = json.loads(json.dumps(PACK))
        ctx = {"facts_by_id": {k: v for k, v in FACTS.items() if k.startswith("lagos:")}}
        with mock.patch.object(brain.gemini_text, "generate_json",
                               lambda prompt, **kw: {"verdicts": [], "unsupported_statements": ["off the shelf"]}):
            problems = brain.verify(pack, ctx, log=lambda *a: None)
        self.assertEqual(problems, ["verifier: legal statement not on the shelf — 'off the shelf'"])
        self.assertEqual(len(pack["claims"]), 1)
        self.assertNotIn("recalled", pack)

    def test_the_approved_pack_and_the_said_ledger_carry_the_recall_count(self):
        src = (ROOT / "tools" / "brain.py").read_text(encoding="utf-8")
        self.assertIn('"recalled": list(pack.get("recalled") or []),', src)
        self.assertIn('"recalled": len(approved.get("recalled") or []),', src)
        self.assertIn('remember_refusal(day, problems, state=ctx.get("state"))', src)


class Gaps(unittest.TestCase):
    def test_refusals_are_sorted_into_recall_research_and_unclear(self):
        with tempfile.TemporaryDirectory() as tmp:
            refused = Path(tmp) / "refused.json"
            rows = [{"date": "2026-11-01", "at": "2026-11-01T01:00:00+01:00", "state": "lagos", "problems": [
                        "verifier: legal statement not on the shelf — 'In Lagos the receipt must state the amount of rent paid.'",
                        "verifier: legal statement not on the shelf — 'In Lagos the receipt must name the premises.'"]},
                    {"date": "2026-10-30", "at": "2026-10-30T01:00:00+01:00", "problems": [
                        "verifier: legal statement not on the shelf — 'In Rivers a receipt signed by the agent is required by law.'"]},
                    {"date": "2026-10-29", "at": "2026-10-29T01:00:00+01:00", "problems": [
                        "verifier: legal statement not on the shelf — 'Possession is protected from the very first day.'",
                        "a body line is 140 characters; max 110"]},
                    {"date": "2026-01-01", "at": "2026-01-01T01:00:00+01:00", "state": "lagos", "problems": [
                        "verifier: legal statement not on the shelf — 'old: the receipt must state the date.'"]}]
            refused.write_text(json.dumps(rows), encoding="utf-8")
            dd = Path(tmp) / "dd.json"
            dd.write_text(json.dumps({"attempts": [{"at": "2026-11-02T03:00:00+01:00", "problems": [
                "verifier: legal statement not on the shelf — 'In Lagos the receipt must state the period it covers.'"]}]}), encoding="utf-8")
            gaps = brain.shelf_gaps(now=datetime(2026, 11, 3, tzinfo=timezone.utc), days=60, refused_path=refused, deepdive_path=dd)
        by = {(g["state"], g["topic"]): g for g in gaps}
        self.assertEqual(by[("lagos", "receipts")]["count"], 3, "two from the pack log plus one from the Deep-Dive ledger; January is outside the window")
        self.assertEqual(by[("lagos", "receipts")]["kind"], "recall")
        self.assertGreaterEqual(by[("lagos", "receipts")]["shelf_facts"], 5)
        self.assertEqual(by[("rivers", "receipts")]["kind"], "research", "Rivers holds only a 'not verified' placeholder")
        protections = [g for g in gaps if g["topic"] == "protections"][0]
        self.assertIn(protections["kind"], ("recall", "research"), "a row with no state falls back to that date's rotation state")
        self.assertNotEqual(protections["state"], "unknown")
        lines = brain.shelf_gap_lines(gaps)
        self.assertTrue(any("RESEARCH TARGET" in l and "rivers:receipts" in l for l in lines))
        self.assertTrue(any("recall, not research" in l and "lagos:receipts" in l for l in lines))
        self.assertEqual(brain.shelf_gap_lines([]), ["- no refused legal sentences in the window — the shelf covered everything asked of it"])

    def test_a_refusal_now_remembers_its_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.json"
            brain.remember_refusal(date(2026, 11, 3), ["x"], path=path, state="kwara")
            brain.remember_refusal(date(2026, 11, 4), ["y"], path=path)
            rows = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(rows[1]["state"], "kwara")
            self.assertEqual(rows[0]["state"], brain.state_for(date(2026, 11, 4)))

    def test_brain_iq_counts_recalls_and_names_the_research_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            said = Path(tmp) / "said.json"
            said.write_text(json.dumps([{"date": "2026-11-02", "recalled": 2}, {"date": "2026-11-01", "recalled": 1},
                                        {"date": "2026-10-25", "recalled": 4}]), encoding="utf-8")
            refused = Path(tmp) / "refused.json"
            refused.write_text(json.dumps([{"date": "2026-11-01", "at": "2026-11-01T01:00:00+01:00", "problems": [
                "verifier: legal statement not on the shelf — 'In Rivers a receipt signed by the agent is required by law.'"]}]), encoding="utf-8")
            iq = sc.brain_iq(now=datetime(2026, 11, 3, tzinfo=timezone.utc), said_path=said, refused_path=refused,
                             deepdive_path=Path(tmp) / "none.json", answers_dir=Path(tmp) / "none")
        self.assertEqual(iq["shelf_recalls"], {"this_week": 3, "last_week": 4})
        self.assertNotIn("shelf_recalls", iq["this_week"], "the Brain Growth lock pins the week dicts; the new measure sits beside them")
        self.assertEqual([(g["state"], g["topic"], g["kind"]) for g in iq["shelf_gaps"]], [("rivers", "receipts", "research")])
        lines = sc.iq_lines(iq)
        self.assertTrue(any(l.startswith("- shelf recall: 3 legal sentence(s)") and "(last week 4)" in l for l in lines))
        self.assertTrue(any("research targets: rivers:receipts ×1" in l for l in lines))


if __name__ == "__main__":
    unittest.main()
