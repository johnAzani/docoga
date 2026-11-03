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
                        "verifier: legal statement not on the shelf — 'In Rivers a receipt signed by the agent is required by law.'",
                        "verifier: legal statement not on the shelf — 'In Rivers the caution deposit is capped by law.'"]},
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
        self.assertEqual(by[("rivers", "receipts")]["kind"], "settled", "read 3 Nov 2026: a dated verified negative is an answer, not a target")
        self.assertEqual(by[("rivers", "receipts")]["read"], "3 Nov 2026")
        self.assertEqual(by[("rivers", "caution_fee")]["kind"], "research", "an undated 'not verified' placeholder is still a target")
        protections = [g for g in gaps if g["topic"] == "protections"][0]
        self.assertIn(protections["kind"], ("recall", "research"), "a row with no state falls back to that date's rotation state")
        self.assertNotEqual(protections["state"], "unknown")
        lines = brain.shelf_gap_lines(gaps)
        self.assertTrue(any("RESEARCH TARGET" in l and "rivers:caution_fee" in l for l in lines))
        self.assertTrue(any("recall the negative, not research" in l and "rivers:receipts" in l and "3 Nov 2026" in l for l in lines))
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
                "verifier: legal statement not on the shelf — 'In Rivers a receipt signed by the agent is required by law.'",
                "verifier: legal statement not on the shelf — 'In Rivers the caution deposit is capped by law.'"]}]), encoding="utf-8")
            iq = sc.brain_iq(now=datetime(2026, 11, 3, tzinfo=timezone.utc), said_path=said, refused_path=refused,
                             deepdive_path=Path(tmp) / "none.json", answers_dir=Path(tmp) / "none")
        self.assertEqual(iq["shelf_recalls"], {"this_week": 3, "last_week": 4})
        self.assertNotIn("shelf_recalls", iq["this_week"], "the Brain Growth lock pins the week dicts; the new measure sits beside them")
        self.assertEqual(sorted((g["state"], g["topic"], g["kind"]) for g in iq["shelf_gaps"]),
                         [("rivers", "caution_fee", "research"), ("rivers", "receipts", "settled")])
        lines = sc.iq_lines(iq)
        self.assertTrue(any(l.startswith("- shelf recall: 3 legal sentence(s)") and "(last week 4)" in l for l in lines))
        self.assertTrue(any("research targets: rivers:caution_fee ×1; settled by research: rivers:receipts (read 3 Nov 2026)" in l for l in lines))


if __name__ == "__main__":
    unittest.main()


class RiversShelfTests(unittest.TestCase):
    """3 Nov 2026: the first research target (`rivers:receipts`) was read — the shelf must carry it."""

    def test_the_rivers_shelf_carries_the_dive_and_the_receipt_entry_reasons_its_negative(self):
        import law_index
        own = [f for f in law_index.facts_for("rivers") if f["slug"] == "rivers"]
        self.assertGreaterEqual(len(own), 25)
        by = {f["id"]: f for f in own}
        self.assertIn("rivers:who_is_a_tenant:1", by)
        self.assertIn("s.29", by["rivers:who_is_a_tenant:1"]["cite"])
        receipts = by["rivers:receipts:1"]["text"]
        self.assertIn("none is claimed", receipts)
        self.assertIn("ss.5–8", receipts)
        texts = " ".join(f["text"] for f in own)
        for needle in ("Form B", "Form E", "s.6(1)(a)", "Anyaehie v. Ongolo", "ss.20–22"):
            self.assertIn(needle, texts)
        self.assertIn("rivers:who_is_a_tenant:1", law_index.by_id())


class EnuguShelfTests(unittest.TestCase):
    """3 Nov 2026: the second research target (Enugu) was read — and a wrong national sentence came off
    the shelf. Enugu's Landlord and Tenant (Amendment) Law 2008 (s.3(b), replacing s.109 of Cap. 101)
    caps a rent review at 15% after every second anniversary (docs/STATE_TENANCY_RESEARCH.md §14)."""

    def test_enugu_is_on_the_shelf_with_the_2008_cap_and_its_worked_example(self):
        import law_index
        import state_law_data as S
        self.assertIn("enugu", S.STATE_LAW)
        self.assertEqual(S.LAW_REVIEWED["enugu"], "2026-11-03")
        self.assertNotIn("enugu", S.NEEDS_CONFIRMATION, "a state on the shelf is not also 'awaiting confirmation'")
        own = [f for f in law_index.facts_for("enugu") if f["slug"] == "enugu"]
        self.assertGreaterEqual(len(own), 20)
        by = {f["id"]: f for f in own}
        cap = by["enugu:increase_challenge:1"]
        self.assertIn("15%", cap["text"])
        self.assertIn("second anniversary", cap["text"])
        self.assertIn("s.3(b)", cap["cite"])
        texts = " ".join(f["text"] for f in own)
        for needle in ("₦460,000", "27 August 1991", "Chicason", "Jovinco", "13 August 2008"):
            self.assertIn(needle, texts)

    def test_the_bill_is_written_as_a_bill_and_the_negatives_carry_a_read_mark(self):
        import law_index
        by = {f["id"]: f for f in law_index.facts_for("enugu") if f["slug"] == "enugu"}
        bill = " ".join(by[k]["text"] for k in by if k.startswith("enugu:caution_fee:"))
        self.assertIn("not law", bill)
        self.assertIn("26 October 2026", bill)
        for key in ("enugu:receipts:1", "enugu:advance_rent:1", "enugu:caution_fee:1"):
            self.assertRegex(by[key]["text"], brain.READ_MARK, key)
        self.assertIn("Lagos s.5", by["enugu:receipts:1"]["text"], "the ₦100,000 receipt penalty is Lagos law, not Enugu")

    def test_no_shelf_entry_still_claims_there_is_no_cap_anywhere_in_nigeria(self):
        import law_index
        for f in law_index.all_facts():
            low = f["text"].lower()
            if "percentage cap" in low and "anywhere" in low:
                self.assertIn("enugu has one", low, f["id"])   # only the correction note may say it, in the past tense

    def test_a_refused_enugu_receipt_sentence_is_settled_not_a_research_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            refused = Path(tmp) / "refused.json"
            refused.write_text(json.dumps([{"date": "2026-11-02", "at": "2026-11-02T01:00:00+01:00", "state": "enugu", "problems": [
                "verifier: legal statement not on the shelf — 'In Enugu the landlord must issue a receipt or pay ₦100,000.'",
                "verifier: legal statement not on the shelf — 'In Enugu rent cannot be increased by more than 15%.'"]}]), encoding="utf-8")
            dd = Path(tmp) / "dd.json"
            dd.write_text(json.dumps({"attempts": []}), encoding="utf-8")
            gaps = brain.shelf_gaps(now=datetime(2026, 11, 3, tzinfo=timezone.utc), days=30, refused_path=refused, deepdive_path=dd)
        by = {(g["state"], g["topic"]): g for g in gaps}
        self.assertEqual(by[("enugu", "receipts")]["kind"], "settled")
        self.assertEqual(by[("enugu", "receipts")]["read"], "3 Nov 2026")
        self.assertEqual(by[("enugu", "increase_challenge")]["kind"], "recall", "the 15% cap is on the shelf — recall it")

    def test_the_enugu_pages_lead_with_the_statute_and_every_state_page_shows_rent_increases(self):
        site = ROOT / "site"
        law = (site / "tenancy-law-enugu.html").read_text(encoding="utf-8")
        self.assertIn("What the law actually says in Enugu", law)
        self.assertIn("Cap. 101, Revised Laws of Enugu State 2004", law)
        self.assertIn(">Rent increases</h3>", law)
        self.assertIn("15% of the existing rent", law)
        self.assertIn("law shelf reviewed 3 November 2026", law)
        caution = (site / "caution-fee-enugu.html").read_text(encoding="utf-8")
        self.assertIn("A bill would change this", caution)
        self.assertIn("Agents&rsquo; and legal fees", caution)
        lagos = (site / "tenancy-law-lagos.html").read_text(encoding="utf-8")
        self.assertIn(">Rent increases</h3>", lagos)
        self.assertNotIn("anywhere else in Nigeria", lagos)
        rights = (site / "tenant-rights-nigeria.html").read_text(encoding="utf-8")
        self.assertIn('href="https://docoga.com.ng/tenancy-law-enugu"', rights)
        self.assertNotIn("Lagos or anywhere in Nigeria", rights)
