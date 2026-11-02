"""🔒 RESEARCH DEEP, STAY AHEAD, DOMINATE — locked by the owner on 2 Nov 2026: "I want you to always
research very very in-depth to the thinnest details on things around my business, always keep me way
ahead of my competitors — even in the social media space. I want to dominate. Lock it in."

The lock is three things and this file pins all of them:
  * the charter (docs/DOMINANCE.md) with its measures, its research discipline and a dated ledger;
  * the machine — a verified field map, the ₦0 watch on every Brain run, THE FIELD in every pack prompt;
  * the measurement — the Monday scorecard's competitor-watch block with research-freshness ⚠️ flags.
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
import competitor_watch as cw  # noqa: E402

CHARTER = ROOT / "docs" / "DOMINANCE.md"


class CharterLock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CHARTER.read_text(encoding="utf-8")

    def test_the_charter_exists_and_carries_the_order(self):
        for needle in ("thinnest details", "keep me way ahead", "social media space", "I want to dominate",
                       "Lock it in", "Gemini only", "₦0", "no fabricated competitors"):
            self.assertIn(needle, self.text, needle)

    def test_the_measures_the_machine_and_the_discipline_never_drop(self):
        for needle in ("sends and saves per reach", "shares and comments per post", "replies and reposts",
                       "watch time, subscribers", "impressions, clicks, average position",
                       "brain/competitors.json", "tools/competitor_watch.py", "logs/competitor_watch.json",
                       "unwatchable", "never copy a headline", "Research before build", "every 14 days",
                       "every 45 days", "The owner is never the sensor", "no scraping behind logins",
                       "no second model"):
            self.assertIn(needle, self.text, needle)

    def test_the_ledger_is_dated_newest_first_and_names_what_shipped(self):
        rows = re.findall(r"^- \*\*(\d{4}-\d{2}-\d{2})\*\*\s*—", self.text, flags=re.M)
        self.assertGreaterEqual(len(rows), 3)
        self.assertEqual(rows, sorted(rows, reverse=True), "newest first — the scorecard reads the top date")
        self.assertGreaterEqual(rows[0], "2026-11-02")
        self.assertIn("#180", self.text)

    def test_the_strategy_office_and_the_brain_docs_point_at_the_lock(self):
        office = (ROOT / "docs" / "STRATEGY_OFFICE.md").read_text(encoding="utf-8")
        self.assertIn("## 11. The dominance mandate", office)
        self.assertIn("docs/DOMINANCE.md", office)
        brain_doc = (ROOT / "docs" / "BRAIN.md").read_text(encoding="utf-8")
        self.assertIn("docs/DOMINANCE.md", brain_doc)
        self.assertIn("test_dominance_lock.py", brain_doc)


class MachineLock(unittest.TestCase):
    def test_the_field_map_is_verified_public_and_typed(self):
        data = json.loads((ROOT / "brain" / "competitors.json").read_text(encoding="utf-8"))
        self.assertRegex(str(data.get("verified")), r"^\d{4}-\d{2}-\d{2}$")
        rows = data["competitors"]
        kinds = {r["kind"] for r in rows}
        self.assertEqual(kinds, {"tool", "content", "creator"})
        self.assertGreaterEqual(len([r for r in rows if r["kind"] == "tool"]), 5)
        for r in rows:
            self.assertTrue(r["url"].startswith("https://"), r)
            self.assertTrue(r["note"].strip(), r)
            self.assertIsInstance(r["feeds"], list)
        self.assertTrue(any(r["feeds"] for r in rows), "a map nobody can watch is a list, not a watch")

    def test_the_brain_plans_knowing_the_field_every_run(self):
        src = (ROOT / "tools" / "brain.py").read_text(encoding="utf-8")
        self.assertIn("import competitor_watch", src)
        self.assertIn("field=competitor_watch.fresh_items()", src)
        self.assertIn("{competitor_watch.prompt_block(ctx.get('field') or [])}", src)
        wf = (ROOT / ".github" / "workflows" / "brain.yml").read_text(encoding="utf-8")
        self.assertIn("python3 tools/competitor_watch.py pull", wf)
        self.assertLess(wf.index("python3 tools/competitor_watch.py pull"), wf.index("- name: Plan the next days"),
                        "the field is read before the plan is made")
        self.assertIn("logs/competitor_watch.json", wf.split("Commit what the brain decided", 1)[1])

    def test_the_prompt_rule_never_softens(self):
        block = cw.prompt_block([{"competitor": "X", "title": "Y", "published": "2026-11-01"}], field=[])
        for needle in ("say it better", "cite the section they did not", "take the angle they missed",
                       "Never copy a headline", "never name a rival"):
            self.assertIn(needle, block, needle)

    def test_the_watch_costs_nothing_and_never_pretends(self):
        src = (ROOT / "tools" / "competitor_watch.py").read_text(encoding="utf-8")
        for forbidden in ("import requests", "selenium", "playwright", "api_key", "Authorization", "openai", "anthropic"):
            self.assertNotIn(forbidden, src, forbidden)
        self.assertIn("unwatchable", src)
        self.assertEqual(cw.TIMEOUT, 20)


class MeasurementLock(unittest.TestCase):
    def test_the_scorecard_prints_the_block_and_the_thresholds_hold(self):
        sc = (ROOT / "tools" / "brain_scorecard.py").read_text(encoding="utf-8")
        self.assertIn("### Competitor watch — the field this week (🔒 docs/DOMINANCE.md)", sc)
        self.assertIn("competitor_watch.scorecard_lines()", sc)
        self.assertEqual(cw.DIVE_STALE_DAYS, 14)
        self.assertEqual(cw.MAP_STALE_DAYS, 45)

    def test_stale_research_is_flagged_and_fresh_research_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "DOMINANCE.md"
            doc.write_text("## 5. Research ledger\n\n- **2026-10-01** — old dive\n- **2026-11-02** — new dive (#180)\n", encoding="utf-8")
            field = Path(tmp) / "competitors.json"
            field.write_text(json.dumps({"verified": "2026-11-02", "competitors": []}), encoding="utf-8")
            fresh = cw.research_status(now=datetime(2026, 11, 9, tzinfo=timezone.utc), doc=doc, field_path=field)
            self.assertEqual(fresh["last_dive"], "2026-11-02")
            self.assertEqual(fresh["dive_days"], 7)
            self.assertFalse(fresh["dive_stale"])
            self.assertFalse(fresh["map_stale"])
            self.assertFalse(any("⚠️" in l for l in cw.research_lines(fresh)))
            late = cw.research_status(now=datetime(2026, 12, 20, tzinfo=timezone.utc), doc=doc, field_path=field)
            self.assertTrue(late["dive_stale"] and late["map_stale"])
            lines = cw.research_lines(late)
            self.assertIn("a new dive is owed", lines[0])
            self.assertIn("re-verify every rival", lines[1])
            none = cw.research_status(now=datetime(2026, 11, 9, tzinfo=timezone.utc), doc=Path(tmp) / "missing.md", field_path=field)
            self.assertTrue(none["dive_stale"])
            self.assertIn("none on the ledger ⚠️", cw.research_lines(none)[0])

    def test_the_real_ledger_is_in_date_today_or_the_scorecard_would_shout(self):
        status = cw.research_status(now=datetime(2026, 11, 2, 12, tzinfo=timezone.utc))
        self.assertFalse(status["dive_stale"] or status["map_stale"], status)


if __name__ == "__main__":
    unittest.main()
