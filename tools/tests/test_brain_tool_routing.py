import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import brain_drafts as drafts  # noqa: E402


class ToolRoutingTests(unittest.TestCase):
    """6 Nov 2026 (🔒 docs/BRAIN_GROWTH.md): the link follows the law the post cites. Before this,
    15 published packs used 4 of 12 tools, the demand letter and the rent-increase page had no
    route at all, and a Lagos post citing increase_challenge pointed at the agreement page."""

    def test_the_two_money_pages_are_reachable(self):
        self.assertIn("rent-review", drafts.TOOLS)
        self.assertTrue(drafts.link_for({"tool": "rent-review", "state": "lagos"}).endswith("/rent-increase-notice-nigeria"))
        self.assertTrue(drafts.link_for({"tool": "letter-of-demand"}).endswith("/demand-letter-rent-arrears-nigeria"))
        for tool in ("rent-review", "letter-of-demand"):
            self.assertTrue((ROOT / "site" / drafts.NATIONAL_PAGE[tool]).is_file(), tool)
            self.assertIn(tool, drafts.TOPIC_TAGS)
            self.assertIn(tool, drafts.SEO_PHRASES)
        for tool, page in drafts.NATIONAL_PAGE.items():
            self.assertTrue((ROOT / "site" / page).is_file(), "%s -> %s is a 404" % (tool, page))
        self.assertTrue(set(drafts.FACT_ROUTES.values()) <= set(drafts.TOOLS))

    def test_a_rent_increase_post_lands_on_the_rent_increase_page_whatever_the_model_chose(self):
        pack = {"tool": "tenancy-agreement", "claims": [{"fact_id": "lagos:increase_challenge:1"},
                                                        {"fact_id": "lagos:increase_challenge:2"},
                                                        {"fact_id": "lagos:receipts:1"}]}
        self.assertEqual(drafts.route_tool(pack), ("rent-review", True))

    def test_the_fact_key_chooses_only_when_the_model_named_no_tool(self):
        self.assertEqual(drafts.route_tool({"tool": None, "claims": [{"fact_id": "kano:receipts:1"}]}), ("rent-receipt", True))
        self.assertEqual(drafts.route_tool({"tool": "tenancy-agreement", "claims": [{"fact_id": "kano:receipts:1"}]}),
                         ("tenancy-agreement", False))
        self.assertEqual(drafts.route_tool({"tool": "nonsense", "claims": [{"fact_id": "kano:receipts:1"}]}), ("rent-receipt", True))

    def test_a_tie_or_an_unmapped_key_routes_nowhere(self):
        self.assertEqual(drafts.dominant_key({"claims": [{"fact_id": "abuja:advance_rent:1"}, {"fact_id": "nigeria:rent_relief:1"}]}), "")
        self.assertEqual(drafts.route_tool({"tool": None, "claims": [{"fact_id": "abuja:pending_bill.hb2839:1"}]}), (None, False))
        self.assertEqual(drafts.route_tool({"tool": None, "claims": []}), (None, False))
        self.assertEqual(drafts.dominant_key({"claims": [{"fact_id": "lagos:notice_ladder:1"}, {"fact_id": "lagos:notice_ladder:2"},
                                                         {"fact_id": "lagos:receipts:1"}]}), "notice_ladder")

    def test_the_editor_saves_the_routed_tool_and_tells_the_prompt(self):
        src = (ROOT / "tools" / "brain.py").read_text(encoding="utf-8")
        self.assertIn("routed_tool, routed = drafts.route_tool(pack)", src)
        self.assertIn('"tool": routed_tool,', src)
        self.assertIn('"tool_routed": routed,', src)
        self.assertIn('"tool_routed": bool(approved.get("tool_routed"))', src, "the memory keeps the signal for the scorecard")
        self.assertIn('`tool`: "rent-review" when the post is about a rent increase', src)
        replies = (ROOT / "tools" / "brain_replies.py").read_text(encoding="utf-8")
        self.assertIn('"rent-review":', replies, "the DM lane can name the tool it sends")


if __name__ == "__main__":
    unittest.main()
