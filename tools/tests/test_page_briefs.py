"""Page briefs — the field writes the research list (7 Nov 2026, 🔒 docs/BRAIN_GROWTH.md)."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import page_briefs as pb  # noqa: E402
import gemini_text  # noqa: E402

NOW = datetime(2026, 11, 7, 1, 30, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 14, 1, 30, tzinfo=timezone.utc)
ITEMS_1 = [{"competitor": "Rival A", "title": "House for rent captions nigeria", "published": "2026-11-05", "link": "https://a.ng/1"},
           {"competitor": "Rival A", "title": "How much can landlord increase rent nigeria", "published": "2026-11-05", "link": "https://a.ng/2"},
           {"competitor": "Rival A", "title": "Upgrading of 20 primary health centres across fct abuja", "published": "2026-11-05", "link": "https://a.ng/3"}]
ITEMS_2 = [{"competitor": "Rival B", "title": "How to advertise your house for rent in Lagos", "published": "2026-11-12", "link": "https://b.ng/1"},
           {"competitor": "Rival A", "title": "House for rent captions nigeria", "published": "2026-11-05", "link": "https://a.ng/1"}]
GOOD = {"verdict": "build", "reason": "a landlord question with a legal edge nobody states",
        "working_title": "Advertising a house for rent in Nigeria: what the agent and the law require",
        "the_question": "How does a landlord advertise a flat lawfully and find a tenant without an agent's trouble?",
        "who_asks": "landlord", "angle": "The listing is the first document of the tenancy; the law on agents and fees starts there.",
        "verify": ["LASRERA registration duty for agents in Lagos", "agency fee position in the Lagos Tenancy Law 2011",
                   "what the Lagos Bill proposes for agents", "advertising standards for property listings"],
        "tool": "tenancy-agreement", "extend_page": ""}
FACTS = [{"id": "lagos:agency_fee:1", "key": "agency_fee", "cite": "s.X", "state": "Lagos", "text": "agent commission on a letting"},
         {"id": "lagos:caution_fee:1", "key": "caution_fee", "cite": "s.10", "state": "Lagos", "text": "caution deposit refund"}]
PAGES = [("tenancy-agreement-nigeria", {"tenancy", "agreement"}), ("rent-receipt-format-nigeria", {"rent", "receipt", "format"}),
         ("caution-fee-nigeria", {"caution", "fee"})]


def gemini_ok(answer):
    def http(url, payload, key):
        return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]})
    return http


def gemini_quota(url, payload, key):
    return 429, json.dumps({"error": {"message": "Quota exceeded", "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                                                                                 "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}})


class QuestionTests(unittest.TestCase):
    def test_two_titles_on_the_same_question_match_and_different_ones_do_not(self):
        self.assertTrue(pb.same_question("House for rent captions nigeria", "How to advertise house for rent nigeria"))
        self.assertTrue(pb.same_question("Caution fee refund in Lagos", "How to get your caution fee back"))
        self.assertFalse(pb.same_question("Rent receipt format", "Rent increase letter"), "one shared common word is not a question")
        self.assertFalse(pb.same_question("Notice to quit", ""))
        self.assertEqual(pb.words("How much can a landlord increase rent in Nigeria 2026?"), ["landlord", "increase", "rent"])
        self.assertEqual(pb.key_for("House for rent captions nigeria"), "house-rent-caption")


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.site = ROOT / "site"

    def test_sightings_are_kept_across_pulls_deduped_and_a_brief_is_due_the_second_time(self):
        data = pb.observe(ITEMS_1, data={"briefs": []}, now=NOW)
        self.assertEqual([e["question"] for e in data["briefs"]], ["House for rent captions nigeria"],
                         "the rent-increase title collides with our page and the tender is not a question")
        self.assertEqual(pb.due(data), [], "seen once — watching, not briefed")
        data = pb.observe(ITEMS_1, data=data, now=NOW)
        self.assertEqual(len(data["briefs"][0]["sightings"]), 1, "the same pull twice adds nothing")
        data = pb.observe(ITEMS_2, data=data, now=LATER)
        entry = data["briefs"][0]
        self.assertEqual(len(data["briefs"]), 1, "a second rival's title on the same question joins the entry")
        self.assertEqual([s["competitor"] for s in entry["sightings"]], ["Rival A", "Rival B"])
        self.assertEqual((entry["first_seen"], entry["last_seen"]), ("2026-11-07", "2026-11-14"))
        self.assertEqual([e["id"] for e in pb.due(data)], ["house-rent-caption"])

    def test_a_declined_question_is_not_briefed_again_unless_a_new_source_asks(self):
        """10 Nov 2026: #214 was declined at dawn and the same run opened #216 on the same two Mushrooms
        titles, because observe() only matched undecided entries. A decline keeps its sightings; a new
        rival asking the question reopens it to watching (the 'asked a third time' rule of GROWTH.md)."""
        data = pb.observe(ITEMS_1, data={"briefs": []}, now=NOW)
        data = pb.observe(ITEMS_2, data=data, now=LATER)
        entry = data["briefs"][0]
        entry["status"] = "declined"
        entry["decision"] = {"by": "editor", "date": "2026-11-14", "reason": "no document behind it"}
        again = pb.observe(ITEMS_1, data=data, now=LATER)
        again = pb.observe(ITEMS_2, data=again, now=LATER)
        self.assertEqual(len(again["briefs"]), 1, "the same two sources again: no fresh entry, no second brief")
        self.assertEqual(again["briefs"][0]["status"], "declined")
        self.assertEqual(pb.due(again), [])
        third = pb.observe([{"competitor": "Rival C", "title": "How to advertise house for rent nigeria",
                             "published": "2026-11-20", "kind": "post", "url": "https://c.example/ad"}], data=again, now=LATER)
        self.assertEqual(len(third["briefs"]), 1)
        self.assertEqual((third["briefs"][0]["status"], third["briefs"][0]["reopened"]), ("watching", "2026-11-14"),
                         "a third source asking reopens the question; the old decision stays as history")
        self.assertEqual(third["briefs"][0]["decision"]["reason"], "no document behind it")
        self.assertEqual([e["id"] for e in pb.due(third)], ["house-rent-caption"])

    def test_the_shelf_and_the_closest_page_are_read_from_what_we_have(self):
        self.assertEqual([h["id"] for h in pb.shelf_hits("Caution fee refund when the tenant leaves", facts=FACTS)], ["lagos:caution_fee:1"])
        self.assertEqual(pb.shelf_hits("How to advertise house for rent", facts=FACTS), [], "'rent' alone proves nothing")
        self.assertEqual(pb.closest_page("Caution fee refund when the tenant leaves", pages=PAGES), ("caution-fee-nigeria", ["caution", "fee"]))
        self.assertEqual(pb.closest_page("Advertising a house", pages=PAGES), ("", []))
        real = pb.site_pages()
        self.assertGreater(len(real), 50)
        self.assertIn("rent-increase-notice-nigeria", [slug for slug, _ in real])

    def test_the_closest_page_is_the_telling_page_not_the_first_page_that_says_rent(self):
        """12 Nov 2026 (🔒 Brain Growth): the matcher counted shared words, so 'house for rent captions'
        was sent to the rent-receipt page through the one word 'rent'. Twelve questions the field and
        the ledger have actually asked, against the real sitemap — rarity-weighted, place-aware, honest
        about having nothing."""
        pages = pb.site_pages()
        expect = {
            "House for rent captions nigeria": "",                                   # no page; say so
            "How to advertise house for rent": "",
            "Why your firm\u2019s year-end party should leave something on the wall": "",
            "City Engineering Nigeria Ltd v. Federal Housing Authority (1997)": "",
            "landlord changed my lock in abuja": "",                                 # the Enugu lockout guide is another state's
            "can landlord increase rent in enugu": "rent-increase-notice-nigeria",   # 'increase' outweighs 'enugu'
            "how many months notice for a yearly tenant in Lagos": "notice-to-quit-lagos",
            "rent receipt sample": "rent-receipt-format-nigeria",                    # 'sample' is a kind of page, not a subject
            "caution fee refund": "caution-fee-nigeria",                             # placeless question: the national page
            "quit notice in rivers state": "notice-to-quit-rivers",
            "query letter for lateness": "query-letter-sample-nigeria",
            "employment contract for a driver": "employment-contract-sample-nigeria",
        }
        got = {q: pb.closest_page(q, pages=pages)[0] for q in expect}
        self.assertEqual(got, expect)
        # a shared place name alone, or a shared FORM word alone, never makes a page the closest page
        self.assertEqual(pb.closest_page("anything in kano", pages=pages), ("", []))
        self.assertEqual(pb.closest_page("free pdf sample", pages=pages), ("", []))


class DraftTests(unittest.TestCase):
    def entry(self):
        return {"id": "house-rent-caption", "question": "House for rent captions nigeria", "status": "watching",
                "first_seen": "2026-11-07", "last_seen": "2026-11-14", "brief": None,
                "sightings": [{"competitor": "Rival A", "title": "House for rent captions nigeria", "published": "2026-11-05", "seen": "2026-11-07"},
                              {"competitor": "Rival B", "title": "How to advertise your house for rent in Lagos", "published": "2026-11-12", "seen": "2026-11-14"}]}

    def test_the_brief_is_gated_no_rival_no_figure_a_real_tool_and_a_verdict(self):
        tools = ["tenancy-agreement", "rent-receipt"]
        rivals = ["Mushrooms.ng", "NigeriaBuildingCost"]
        self.assertEqual(pb.lint(GOOD, tools, rivals), [])
        bad = dict(GOOD, angle="Unlike Mushrooms.ng we cite the section", verify=["one"], tool="magic")
        problems = pb.lint(bad, tools, rivals)
        self.assertTrue(any("names a rival" in p for p in problems), problems)
        self.assertTrue(any("3 to 6" in p for p in problems), problems)
        self.assertTrue(any("tool" in p for p in problems), problems)
        self.assertEqual(pb.lint(dict(GOOD, angle="Rents rose 50% last year"), tools, rivals), ["a figure or statistic in a brief — list it under verify instead"])
        self.assertEqual(pb.lint(dict(GOOD, verdict="extend"), tools, rivals), ["extend needs the page slug"])
        self.assertEqual(pb.lint({"verdict": "decline", "reason": "listing marketing, not a document"}, tools, rivals), [])
        self.assertIn("verdict must be", pb.lint({"verdict": "maybe"}, tools, rivals)[0])

    def test_rival_names_carry_the_brands_and_never_our_own_words(self):
        names = pb.rival_names()
        self.assertIn("NigeriaBuildingCost", names)
        self.assertIn("mushrooms", names)
        for ours in ("tenancy agreement generator", "tenancy", "legal", "blog", "tiktok", "youtube"):
            self.assertNotIn(ours, [n.lower() for n in names], ours)

    def test_gemini_writes_the_angle_and_a_refused_answer_is_asked_again(self):
        calls = []
        bad = dict(GOOD, angle="Mushrooms.ng misses the section")

        def http(url, payload, key):
            calls.append(json.loads(payload)["contents"][0]["parts"][0]["text"] if isinstance(payload, (bytes, str)) else payload)
            answer = bad if len(calls) == 1 else GOOD
            return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]})
        with mock.patch.dict(os.environ, {"GEMINI_QUOTA_LEDGER": str(Path(tempfile.mkdtemp()) / "q.json")}):
            brief, by = pb.draft(self.entry(), http=http, sleep=lambda s: None, log=lambda *a: None, facts=FACTS, pages=PAGES,
                                 field=[{"name": "Mushrooms.ng blog", "url": "https://mushrooms.ng", "kind": "content", "feeds": [], "note": ""}])
        self.assertEqual((by, brief["verdict"], brief["tool"]), ("gemini", "build", "tenancy-agreement"))
        self.assertEqual(len(calls), 2)
        self.assertEqual(brief["shelf"], [])
        self.assertIn("never name a rival", str(calls[0]))
        self.assertIn("Mushrooms.ng", str(calls[0]), "the prompt tells the model which names are banned")

    def test_when_every_model_is_refused_the_brief_is_still_written_from_rules(self):
        with mock.patch.dict(os.environ, {"GEMINI_QUOTA_LEDGER": str(Path(tempfile.mkdtemp()) / "q.json")}):
            brief, by = pb.draft(self.entry(), http=gemini_quota, sleep=lambda s: None, log=lambda *a: None, facts=FACTS, pages=PAGES, field=[])
        self.assertEqual(by, "rules")
        self.assertEqual(brief["verdict"], "build")
        self.assertEqual(brief["working_title"], "House for rent captions nigeria")
        self.assertIn("tenancy-agreement", brief["tool"])
        self.assertGreaterEqual(len(brief["verify"]), 3)
        caution = dict(self.entry(), question="Caution fee refund when the tenant leaves")
        with mock.patch.dict(os.environ, {"GEMINI_QUOTA_LEDGER": str(Path(tempfile.mkdtemp()) / "q.json")}):
            brief, _ = pb.draft(caution, http=gemini_quota, sleep=lambda s: None, log=lambda *a: None, facts=FACTS, pages=PAGES, field=[])
        self.assertEqual((brief["verdict"], brief["extend_page"], brief["tool"]), ("extend", "caution-fee-nigeria", "caution-fee"))
        self.assertEqual([h["id"] for h in brief["shelf"]], ["lagos:caution_fee:1"])

    def test_run_writes_the_markdown_the_ledger_and_the_scorecard_and_a_decline_writes_no_file(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"GEMINI_QUOTA_LEDGER": str(Path(tmp) / "q.json")}), \
                mock.patch.object(pb, "LEDGER", Path(tmp) / "page_briefs.json"), \
                mock.patch.object(pb, "BRIEF_DIR", Path(tmp) / "briefs"):
            data, written = pb.run(items=ITEMS_1, now=NOW, http=gemini_ok(GOOD), log=lambda *a: None, facts=FACTS, pages=PAGES, field=[])
            self.assertEqual(written, [], "seen once: nothing drafted, nothing asked of Gemini")
            data, written = pb.run(items=ITEMS_2, now=LATER, http=gemini_ok(GOOD), log=lambda *a: None, facts=FACTS, pages=PAGES, field=[])
            self.assertEqual([p.name for p in written], ["house-rent-caption.md"])
            text = written[0].read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Page brief: Advertising a house for rent in Nigeria"))
            self.assertIn("- [ ] LASRERA registration duty for agents in Lagos", text)
            self.assertIn("What the field wrote (titles only — never copied)", text)
            self.assertIn("research order, not a page", text)
            saved = json.loads((Path(tmp) / "page_briefs.json").read_text(encoding="utf-8"))
            self.assertEqual((saved["briefs"][0]["status"], saved["briefs"][0]["drafted_by"]), ("briefed", "gemini"))
            lines = pb.scorecard_lines(saved)
            self.assertTrue(lines[0].startswith("- 📝 page brief: Advertising a house for rent in Nigeria"), lines)
            self.assertIn("brain/briefs/house-rent-caption.md", lines[0])
            # a third sighting of the same question changes nothing — it is briefed
            data, written = pb.run(items=ITEMS_2, now=LATER, http=gemini_ok(GOOD), log=lambda *a: None, facts=FACTS, pages=PAGES, field=[])
            self.assertEqual(written, [])
            # a decline is remembered and writes no file
            decline = {"verdict": "decline", "reason": "listing marketing, not a document or a law question"}
            items = [{"competitor": "R", "title": "Best estate agent slogans", "published": "2026-11-12", "link": "https://r/1"},
                     {"competitor": "S", "title": "Estate agent slogans that sell", "published": "2026-11-13", "link": "https://s/1"}]
            data, written = pb.run(items=items, now=LATER, http=gemini_ok(decline), log=lambda *a: None, facts=FACTS, pages=PAGES, field=[])
            self.assertEqual(written, [])
            self.assertEqual([e["status"] for e in data["briefs"]], ["briefed", "declined"])
            self.assertTrue(any(l.startswith("- declined: ") for l in pb.scorecard_lines(data)))
        self.assertEqual(pb.scorecard_lines({"briefs": []}), ["- no uncovered field question seen twice yet — nothing to brief"])


class WiringTests(unittest.TestCase):
    def test_the_brain_workflow_folds_the_field_in_files_the_issue_and_commits_the_ledger(self):
        wf = (ROOT / ".github" / "workflows" / "brain.yml").read_text(encoding="utf-8")
        self.assertIn("python3 tools/page_briefs.py observe", wf)
        self.assertLess(wf.index("tools/competitor_watch.py pull"), wf.index("tools/page_briefs.py observe"), "the pull comes first")
        self.assertIn("gh issue create --title \"$TITLE\" --label page-brief --body-file \"$FILE\"", wf)
        self.assertIn("brain/page_briefs.json brain/briefs", wf, "the ledger and the briefs reach main")
        sc = (ROOT / "tools" / "brain_scorecard.py").read_text(encoding="utf-8")
        self.assertIn("page_briefs.scorecard_lines()", sc)
        self.assertEqual(pb.MAX_BRIEFS_PER_RUN, 1, "one model call a night at most — the planner's quota comes first")
        self.assertEqual(pb.TWICE, 2)

    def test_a_decided_brief_closes_its_own_issue_from_the_workflow(self):
        data = {"briefs": [{"id": "a", "question": "q", "status": "declined", "sightings": [{}], "brief": {"working_title": "T"},
                            "decision": {"reason": "no document\nbehind it"}},
                           {"id": "b", "question": "q2", "status": "declined", "sightings": [{}], "brief": {"verdict": "decline"}},
                           {"id": "c", "question": "q3", "status": "briefed", "sightings": [{}], "brief": {"working_title": "U"}}]}
        self.assertEqual(pb.decisions(data), ["Page brief: T\tdeclined\tno document behind it"],
                         "a model decline has no issue to close; an open brief is not decided")
        wf = (ROOT / ".github" / "workflows" / "brain.yml").read_text(encoding="utf-8")
        self.assertIn("python3 tools/page_briefs.py decisions", wf)
        self.assertIn('gh issue close "$NUM" --reason "not planned"', wf)
        real = pb.decisions()
        self.assertTrue(any(l.startswith("Page brief: How to Advertise a House for Rent in Nigeria") and "\tdeclined\t" in l for l in real),
                        "10 Nov 2026: the first brief was declined by the editor — no document behind a listing page")

    def test_the_real_ledger_if_present_is_well_formed(self):
        data = pb.load()
        for e in data["briefs"]:
            self.assertIn(e["status"], ("watching", "briefed", "built", "declined"))
            self.assertTrue(e["id"] and e["question"] and e["sightings"])
            if e["status"] == "briefed":
                self.assertTrue((ROOT / "brain" / "briefs" / (e["id"] + ".md")).exists(), e["id"])


if __name__ == "__main__":
    unittest.main()
