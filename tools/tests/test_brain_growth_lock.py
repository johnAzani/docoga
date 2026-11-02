"""🔒 THE BRAIN GETS SMARTER — locked by the owner on 2 Nov 2026: "I want you to always improve on the
brain. I want it to always get smarter. Lock it in."

The lock is three things and this file pins all of them:
  * the charter (docs/BRAIN_GROWTH.md) with its measures, its learning loops and a dated changelog;
  * the first loop — the Brain carries the lessons of its own refusals into every drafting prompt;
  * the measurement — the Monday scorecard's "Brain IQ" block.
Never edit this file to let something through; revert the change that trips it.
"""
import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import brain  # noqa: E402
import brain_scorecard as sc  # noqa: E402

CHARTER = ROOT / "docs" / "BRAIN_GROWTH.md"


class CharterLock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CHARTER.read_text(encoding="utf-8")

    def test_the_charter_exists_and_carries_the_order(self):
        self.assertIn("always get smarter", self.text)
        self.assertIn("Lock it in", self.text)
        self.assertIn("Gemini only", self.text)
        self.assertIn("₦0", self.text)

    def test_the_measures_and_the_loops_never_drop(self):
        for needle in ("First-pass rate", "Deep-Dive drafts", "Answer page", "Law shelf", "Lessons carried",
                       "Days since last improvement", "Lessons from its own refusals", "Monday feedback",
                       "The ears", "The newsdesk", "Nothing twice", "The verifier", "every 14 days"):
            self.assertIn(needle, self.text, needle)

    def test_the_changelog_is_dated_newest_first_and_the_scorecard_can_read_it(self):
        rows = re.findall(r"^- \*\*(\d{4}-\d{2}-\d{2})\*\* — (.+)$", self.text, flags=re.M)
        self.assertGreaterEqual(len(rows), 3)
        dates = [r[0] for r in rows]
        self.assertEqual(dates, sorted(dates, reverse=True), "newest first")
        day, title = sc.last_brain_improvement()
        self.assertEqual(day, dates[0])
        self.assertTrue(title)


class LessonsLoop(unittest.TestCase):
    def test_refusal_families_become_counted_lessons_in_every_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            refused = Path(tmp) / "refused.json"
            dd = Path(tmp) / "dd.json"
            now = datetime(2026, 11, 2, 5, 0, tzinfo=timezone.utc)
            refused.write_text(json.dumps([
                {"date": "2026-11-04", "at": "2026-11-02T01:35:30+01:00",
                 "problems": ["a body line is 184 characters; max 110: 'For Lagos'",
                              "news_hook is not one of this week's NEWSDESK headlines — x"]},
                {"date": "2026-10-30", "at": "2026-10-28T01:35:30+01:00",
                 "problems": ["news_hook is not one of this week's NEWSDESK headlines — y",
                              "verifier: legal statement not on the shelf — 'A landlord can'"]},
                {"date": "2026-09-01", "at": "2026-09-01T01:00:00+01:00",
                 "problems": ["price ₦500,000 is neither ours nor in a cited fact"]},      # too old
            ]))
            dd.write_text(json.dumps({"attempts": [
                {"at": "2026-11-02T01:37:34+01:00", "outcome": "refused",
                 "problems": ["verifier: claim [lagos:protections:5] not supported — z"]},
                {"at": "2026-10-28T07:11:55+01:00", "outcome": "written", "problems": []},
            ]}))
            items = brain.lessons(now=now, refused_path=refused, deepdive_path=dd)
        families = [(i["family"], i["count"]) for i in items]
        self.assertEqual(families[0], ("news_hook", 2))
        self.assertIn(("line_length", 1), families)
        self.assertIn(("not_on_shelf", 1), families)
        self.assertIn(("claim_overreach", 1), families)
        self.assertNotIn("price", [f for f, _ in families], "a 30-day memory, not a grudge")
        block = brain.lessons_block(items)
        self.assertIn("LESSONS FROM YOUR OWN REFUSALS", block)
        self.assertIn("(2×) news_hook is copied word for word", block)
        self.assertEqual(brain.lessons_block([]), "")
        self.assertLessEqual(len(items), brain.LESSON_TOP)

    def test_every_family_has_a_plain_lesson_and_the_known_refusals_all_map(self):
        for key, rx, lesson in brain.LESSON_FAMILIES:
            self.assertTrue(key and lesson.endswith("."), key)
        for problem in ("a body line is 142 characters; max 110: 'For a yearly tenant",
                        "verifier: legal statement not on the shelf — 'S.5(1) of the",
                        "verifier: claim [rivers:rent_in_arrears:1] not supported — T",
                        "statistic '20%' is not in a cited fact — DocOga publishes no",
                        "a cited post names the section number (e.g. s.5) in its copy",
                        "short.title: 1-64 characters", "headline is 79 characters; max 70",
                        "claim cites unknown fact id '2026-10-27'", "36-48 beats (got 19)"):
            self.assertIsNotNone(brain._lesson_family(problem)[0], problem)

    def test_the_lessons_ride_in_the_pack_prompt_and_the_deepdive_prompt(self):
        src = (ROOT / "tools" / "brain.py").read_text(encoding="utf-8")
        self.assertIn('retry = lessons_block(ctx["lessons"] if "lessons" in ctx else lessons())', src)
        self.assertIn("retry = lessons_block(lessons())", src)
        from datetime import date
        ctx = brain.day_context(date(2026, 11, 5), said=[])
        ctx["lessons"] = [{"family": "news_hook", "count": 3, "lesson": "news_hook is copied word for word."}]
        prompt = brain.prompt_for(ctx)
        self.assertIn("LESSONS FROM YOUR OWN REFUSALS", prompt)
        self.assertLess(prompt.index("LESSONS FROM YOUR OWN REFUSALS"), len(prompt), "at the end, next to the retry block")
        again = brain.prompt_for(ctx, problems=["headline is 79 characters; max 70"])
        self.assertLess(again.index("LESSONS FROM YOUR OWN REFUSALS"), again.index("YOUR PREVIOUS DRAFT WAS REFUSED"))
        ctx["lessons"] = []
        self.assertNotIn("LESSONS FROM YOUR OWN REFUSALS", brain.prompt_for(ctx), "nothing to learn from = nothing said")
        self.assertIn("(3×) news_hook is copied word for word.", prompt)


class BrainIQ(unittest.TestCase):
    def test_the_monday_scorecard_measures_the_brain_against_last_week(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            now = datetime(2026, 11, 2, 5, 40, tzinfo=timezone.utc)
            (tmp / "said.json").write_text(json.dumps([{"date": "2026-10-28"}, {"date": "2026-10-30"}, {"date": "2026-10-22"}]))
            (tmp / "refused.json").write_text(json.dumps([
                {"date": "2026-10-29", "at": "2026-10-27T01:30:00+01:00", "problems": ["a body line is 140 characters; max 110: x"]},
                {"date": "2026-10-21", "at": "2026-10-19T01:30:00+01:00", "problems": ["news_hook is not one of this week's NEWSDESK headlines"]},
                {"date": "2026-10-20", "at": "2026-10-19T01:40:00+01:00", "problems": ["news_hook is not one of this week's NEWSDESK headlines"]},
            ]))
            (tmp / "dd.json").write_text(json.dumps({"attempts": [
                {"at": "2026-10-28T07:11:55+01:00", "outcome": "written", "problems": []},
                {"at": "2026-10-28T01:35:06+01:00", "outcome": "refused", "problems": ["36-48 beats (got 19)"]}]}))
            (tmp / "answers").mkdir()
            (tmp / "answers" / "2026-10-26.json").write_text("{}")
            doc = tmp / "GROWTH.md"
            doc.write_text("# x\n\n- **2026-10-10** — an old one\n- **2026-10-29** — the newest\n")
            iq = sc.brain_iq(now=now, said_path=tmp / "said.json", refused_path=tmp / "refused.json",
                             deepdive_path=tmp / "dd.json", answers_dir=tmp / "answers", doc=doc)
        self.assertEqual(iq["this_week"], {"packs_approved": 2, "nights_refused": 1, "first_pass_rate": 0.67,
                                           "deepdive_attempts": 2, "deepdive_written": 1, "answer_pages": 1})
        self.assertEqual((iq["last_week"]["packs_approved"], iq["last_week"]["nights_refused"], iq["last_week"]["first_pass_rate"]),
                         (1, 2, 0.33))
        self.assertEqual((iq["last_improvement"], iq["days_since_improvement"], iq["stale"]), ("2026-10-29", 4, False))
        self.assertEqual([l["family"] for l in iq["lessons"]][:2], ["news_hook", "beats"])
        lines = "\n".join(sc.iq_lines(iq))
        self.assertIn("67% ▲ (last week 33%)", lines)
        self.assertIn("answer page this week: yes", lines)
        self.assertIn("the newest", lines)
        stale = dict(iq, days_since_improvement=20, stale=True)
        self.assertIn("owed an improvement", "\n".join(sc.iq_lines(stale)))

    def test_the_block_is_in_the_summary_and_never_costs_the_scorecard(self):
        snap = {"week": "2026-W45", "taken_at": "2026-11-02T05:40:00", "kpis": {"brain_iq": sc.brain_iq()}, "grades": [], "orders": []}
        md = sc.summary_md(snap)
        self.assertIn("### Brain IQ — is the editor getting smarter?", md)
        self.assertIn("law shelf:", md)
        src = (ROOT / "tools" / "brain_scorecard.py").read_text(encoding="utf-8")
        self.assertIn('k["brain_iq"] = brain_iq(now=now)', src)


if __name__ == "__main__":
    unittest.main()
