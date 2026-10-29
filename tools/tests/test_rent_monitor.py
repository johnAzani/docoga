"""Rent Monitor → Brain (29 Oct 2026): Friday's live receipt counts enter the prompt as citable
facts (monitor:*), never as free prose; off Fridays, unset, or with the ledger down → nothing."""
import datetime as dt
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import brain  # noqa: E402
import brain_drafts  # noqa: E402
import rent_monitor as rm  # noqa: E402

STATS = {"total": 7, "by_state": {"Lagos": 4, "Rivers": 2, "Edo": 1},
         "cells": {"Lagos|rent|2026-10": 3, "Rivers|rent|2026-10": 2, "Edo|rent|2026-09": 1}, "publish_at": 30}
FRIDAY = dt.date(2026, 10, 30)
THURSDAY = dt.date(2026, 10, 29)


class FactTests(unittest.TestCase):
    def test_the_counts_become_three_facts_with_ids_the_verifier_can_hold_the_post_to(self):
        facts = rm.facts(STATS, FRIDAY)
        self.assertEqual([f["id"] for f in facts], ["monitor:total", "monitor:rule", "monitor:closest"])
        self.assertIn("7 rent receipts", facts[0]["text"])
        self.assertIn("from 3 states", facts[0]["text"])
        self.assertIn("30 verified receipts", facts[1]["text"])
        self.assertIn("Lagos: 3 of 30 rent receipts for October 2026", facts[2]["text"])
        for f in facts:
            self.assertEqual(f["cite"], "docoga.com.ng/rent-index-nigeria")
            self.assertEqual(f["statute"], "DocOga Rent Monitor")

    def test_the_statistic_gate_accepts_a_figure_that_sits_in_a_monitor_fact_and_refuses_one_that_does_not(self):
        texts = " ".join(f["text"] for f in rm.facts(STATS, FRIDAY))
        ok = {"post": {"headline": "Lagos is 3 of 30", "lines": ["Seven receipts so far"], "cta": "x"}}
        self.assertEqual(brain.statistic_problems(ok, texts), [])
        bad = {"post": {"headline": "Lagos is 9 of 30", "lines": [], "cta": "x"}}
        self.assertTrue(brain.statistic_problems(bad, texts))

    def test_no_stats_no_facts_and_a_missing_cell_block_is_fine(self):
        self.assertEqual(rm.facts(None), [])
        self.assertEqual(len(rm.facts({"total": 0, "by_state": {}, "cells": {}}, FRIDAY)), 2)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.saved = os.environ.pop("DOCOGA_MONITOR", None)

    def tearDown(self):
        os.environ.pop("DOCOGA_MONITOR", None)
        if self.saved is not None:
            os.environ["DOCOGA_MONITOR"] = self.saved

    def test_unset_means_no_network_and_no_facts(self):
        calls = []
        self.assertEqual(rm.context(FRIDAY, http=lambda u: calls.append(u) or json.dumps(STATS)), [])
        self.assertEqual(calls, [])

    def test_friday_only_and_a_dead_ledger_is_silent(self):
        os.environ["DOCOGA_MONITOR"] = "on"
        self.assertEqual(rm.context(THURSDAY, http=lambda u: json.dumps(STATS)), [])
        self.assertEqual(len(rm.context(FRIDAY, http=lambda u: json.dumps(STATS), log=lambda *a: None)), 3)
        self.assertEqual(rm.context(FRIDAY, http=lambda u: (_ for _ in ()).throw(OSError("down")), log=lambda *a: None), [])
        self.assertEqual(rm.context(FRIDAY, http=lambda u: "not json", log=lambda *a: None), [])

    def test_the_ledger_url_is_the_one_the_site_uses(self):
        idx = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('const LEDGER_URL="%s"' % rm.LEDGER_URL, idx)


class WiringTests(unittest.TestCase):
    def test_the_prompt_carries_the_block_only_when_there_are_monitor_facts(self):
        ctx = dict(day=FRIDAY, weekday="Friday", lead="promo", state="lagos", state_name="Lagos", facts=[],
                   short_day=False, calendar=[], series=None, recent=[], feedback="", strategy="", audience="",
                   news=[], search=[], asked=[], hook=None, hook_why="", hook_binding=False, monitor=[])
        self.assertNotIn("RENT MONITOR DAY", brain.prompt_for(ctx))
        ctx["monitor"] = rm.facts(STATS, FRIDAY)
        ctx["facts"] = list(ctx["monitor"])
        prompt = brain.prompt_for(ctx)
        self.assertIn("RENT MONITOR DAY", prompt)
        self.assertIn("monitor:closest", prompt)
        self.assertIn('Set `tool` to "rent-index"', prompt)
        self.assertIn("rent-index", prompt.split("\"tool\": one of")[1][:400], "the OUTPUT schema offers the tool")

    def test_rent_index_is_a_tool_with_a_page_a_topic_and_a_search_phrase(self):
        self.assertIn("rent-index", brain_drafts.TOOLS)
        self.assertTrue(brain_drafts.link_for({"tool": "rent-index"}).endswith("/rent-index-nigeria"))
        self.assertEqual(brain_drafts.TOPIC_TAGS["rent-index"], "Rent in Nigeria")
        self.assertIn("rent-index", brain_drafts.SEO_PHRASES)

    def test_the_brain_lane_sets_the_switch_and_the_strategy_names_the_friday_slot(self):
        wf = (ROOT / ".github" / "workflows" / "brain.yml").read_text(encoding="utf-8")
        self.assertIn("DOCOGA_MONITOR: ${{ vars.DOCOGA_MONITOR || 'on' }}", wf)
        self.assertIn("Rent Monitor", (ROOT / "brain" / "strategy.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
