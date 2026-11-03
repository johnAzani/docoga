"""🔒 GROW — research how to make more, as often as possible, at ₦0. Locked by the owner on 3 Nov 2026,
on handing the company over to be run: "the same way I want you to always always research as
frequently as possible very very in-depth to the thinnest details on how to make more success more
than what we are making now, and make sure it can be fully automated, and remember the ₦0."
The lock is three things and this file pins all of them:
  * the charter (docs/GROWTH.md) with its three numbers, its 7-day cadence and a dated ledger;
  * the machine — tools/growth.py reading the Search Console pull at ₦0, no hands;
  * the measurement — the Monday scorecard's Growth block with the week's one order and a ⚠️ when the dive is stale.
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
import growth  # noqa: E402

CHARTER = ROOT / "docs" / "GROWTH.md"

PULL = {
    "taken_at": "2026-11-02T12:59:21+00:00", "window": {"start": "2026-10-02", "end": "2026-10-30", "days": 28},
    "clicks": 20, "impressions": 659,
    "top_queries": [
        {"query": "quit notice", "page": "https://docoga.com.ng/notice-to-quit-nigeria.html", "clicks": 0, "impressions": 48, "position": 1.0},
        {"query": "quit notice", "page": "https://docoga.com.ng/notice-to-quit-nigeria", "clicks": 0, "impressions": 9, "position": 10.6},
        {"query": "notice to quit", "page": "https://docoga.com.ng/notice-to-quit-nigeria", "clicks": 0, "impressions": 23, "position": 7.4},
        {"query": "quit notice letter from landlord to tenant in nigeria", "page": "https://docoga.com.ng/notice-to-quit-nigeria", "clicks": 0, "impressions": 19, "position": 6.3},
        {"query": "enugu", "page": "https://docoga.com.ng/notice-to-quit-enugu", "clicks": 0, "impressions": 3, "position": 2.0},
        {"query": "rental receipt", "page": "https://docoga.com.ng/rent-receipt-format-nigeria.html", "clicks": 1, "impressions": 1, "position": 9.0},
    ],
    "top_pages": [
        {"page": "https://docoga.com.ng/", "clicks": 3, "impressions": 24, "position": 5.3},
        {"page": "https://docoga.com.ng/notice-to-quit-nigeria.html", "clicks": 2, "impressions": 161, "position": 4.7},
        {"page": "https://docoga.com.ng/notice-to-quit-nigeria", "clicks": 1, "impressions": 145, "position": 6.4},
        {"page": "https://docoga.com.ng/rent-receipt-format-nigeria.html", "clicks": 1, "impressions": 27, "position": 6.7},
        {"page": "https://docoga.com.ng/shop-tenancy-agreement-nigeria.html", "clicks": 0, "impressions": 43, "position": 8.0},
    ],
}


class CharterLock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CHARTER.read_text(encoding="utf-8")

    def test_the_charter_exists_and_carries_the_order(self):
        for needle in ("as frequently as possible", "thinnest details", "more success more than what we are making now",
                       "fully automated", "remember the ₦0", "manage it to greatness"):
            self.assertIn(needle, self.text, needle)

    def test_the_numbers_the_cadence_and_the_discipline_never_drop(self):
        for needle in ("money-page share", "40%", "every 7 days at most", "DO NOW / TEST NEXT / LATER / REJECT",
                       "fully automated end to end", "tools/growth.py", "logs/search_console.json",
                       "zero-click top spots", "striking distance", "this week's order", "Gemini only",
                       "No paid traffic", "no price change without the owner's word", "worker/index.js",
                       "nothing the owner must do on a schedule", "never invented"):
            self.assertIn(needle, self.text, needle)

    def test_the_ledger_is_dated_newest_first_with_sources_and_a_decision_list(self):
        rows = re.findall(r"^- \*\*(\d{4}-\d{2}-\d{2})\*\*\s*—", self.text, flags=re.M)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows, sorted(rows, reverse=True), "newest first — the scorecard reads the top date")
        self.assertGreaterEqual(rows[0], "2026-11-03")
        ledger = self.text.split("## 5. Growth ledger", 1)[1]
        for needle in ("DO NOW", "TEST NEXT", "LATER", "REJECT", "Sources:"):
            self.assertIn(needle, ledger, needle)

    def test_the_strategy_office_and_the_brain_docs_point_at_the_lock(self):
        office = (ROOT / "docs" / "STRATEGY_OFFICE.md").read_text(encoding="utf-8")
        self.assertIn("## 12. The growth mandate", office)
        self.assertIn("docs/GROWTH.md", office)
        brain_doc = (ROOT / "docs" / "BRAIN.md").read_text(encoding="utf-8")
        self.assertIn("docs/GROWTH.md", brain_doc)
        self.assertIn("test_growth_lock.py", brain_doc)


class MachineLock(unittest.TestCase):
    def test_the_measures_read_the_pull_the_way_the_charter_says(self):
        m = growth.measures(PULL)
        self.assertEqual(m["page_impressions"], 400)
        self.assertEqual(m["money_impressions"], 94, "home + receipt + shop agreement are money pages; quit-notice pages are not")
        self.assertEqual(m["money_share"], 0.235)
        self.assertEqual([(r["query"], r["impressions"]) for r in m["zero_click"]], [("quit notice", 48)],
                         "position ≤3 with impressions and no clicks; 'enugu' ×3 is below the floor")
        self.assertEqual([r["query"] for r in m["striking"]], ["notice to quit", "quit notice letter from landlord to tenant in nigeria"])
        self.assertTrue(m["striking"][1]["transactional"])
        self.assertFalse(m["striking"][0]["transactional"])

    def test_the_order_is_the_biggest_leak_in_one_sentence(self):
        m = growth.measures(PULL)
        text = growth.order(m)
        self.assertIn("sample-and-download page", text)
        self.assertIn("'quit notice'", text)
        self.assertIn("24% against 40%", text)
        rich = dict(m, money_share=0.5, zero_click=[], striking=[])
        self.assertIn("grow the footprint", growth.order(rich))

    def test_the_thresholds_hold(self):
        self.assertEqual(growth.DIVE_STALE_DAYS, 7)
        self.assertEqual(growth.MONEY_SHARE_TARGET, 0.40)

    def test_the_machine_costs_nothing_and_never_raises(self):
        src = (ROOT / "tools" / "growth.py").read_text(encoding="utf-8")
        for forbidden in ("import requests", "urllib.request", "api_key", "Authorization", "openai", "anthropic", "selenium"):
            self.assertNotIn(forbidden, src, forbidden)
        self.assertEqual(growth.measures({}), growth.measures({"top_pages": "junk", "top_queries": None}))
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "none.json"
            lines = growth.scorecard_lines(path=missing, now=datetime(2026, 11, 3, tzinfo=timezone.utc))
            self.assertTrue(any("no Search Console pull" in l for l in lines))


class MeasurementLock(unittest.TestCase):
    def test_the_scorecard_prints_the_block(self):
        sc = (ROOT / "tools" / "brain_scorecard.py").read_text(encoding="utf-8")
        self.assertIn("### Growth — where the next naira is (🔒 docs/GROWTH.md)", sc)
        self.assertIn("growth.scorecard_lines()", sc)

    def test_the_block_names_the_share_the_leaks_the_order_and_a_stale_dive(self):
        with tempfile.TemporaryDirectory() as tmp:
            pull = Path(tmp) / "sc.json"
            pull.write_text(json.dumps(PULL), encoding="utf-8")
            fresh = "- **2026-11-03** — dive\n"
            lines = growth.scorecard_lines(path=pull, now=datetime(2026, 11, 5, tzinfo=timezone.utc), charter_text=fresh)
            self.assertTrue(lines[0].startswith("- last growth dive: 2026-11-03 (2 day(s) ago; limit 7)"))
            self.assertTrue(any("money-page share of Google impressions (2026-10-02 → 2026-10-30): 24% (94 of 400) — target 40% 🔻" in l for l in lines))
            self.assertTrue(any(l.startswith("- zero-click top spots") and "'quit notice' pos 1.0 ×48" in l for l in lines))
            self.assertTrue(any(l.startswith("- striking distance") and "(transactional)" in l for l in lines))
            self.assertTrue(any(l.startswith("- this week's order: ") for l in lines))
            stale = growth.scorecard_lines(path=pull, now=datetime(2026, 11, 11, tzinfo=timezone.utc), charter_text=fresh)
            self.assertIn("⚠️ the last growth dive is 8 days old (limit 7)", stale[0])
            self.assertIn("⚠️ no growth dive logged", growth.scorecard_lines(path=pull, charter_text="")[0])

    def test_the_real_ledger_is_fresh_enough_to_run_the_week(self):
        """The charter's own top date is read by the scorecard; it must parse and be a real date."""
        self.assertRegex(growth.dive_date() or "", r"^\d{4}-\d{2}-\d{2}$")


if __name__ == "__main__":
    unittest.main()
