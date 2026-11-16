"""The YouTube search lane — the brief is only useful if it obeys three rules.

Owner, 16 Nov 2026: "Do all". The channel had eight Deep-Dives titled like essays
("Caution Fee in Nigeria: The Only 4 Deductions a Landlord Can Make") and 279
impressions in 90 days across the whole site. A video is worth making only when
somebody already searched for it — so the lane reads the site's own Search Console
rows, drops the fragments, refuses to duplicate a published episode, and writes the
title in the shape people type.

These tests are offline: every fixture is a dict, no network, no YouTube.
"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "tools", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import yt_search_lane as lane  # noqa: E402


def row(query, impressions=1, position=10.0, page="https://docoga.com.ng/notice-to-quit-edo.html"):
    return {"query": query, "impressions": impressions, "position": position, "page": page}


class FragmentsTests(unittest.TestCase):
    """Search Console returns rows that are not queries a video can be titled after."""

    def test_a_bare_place_is_not_a_query(self):
        for fragment in ("kano", "portharcourt", "lagos"):
            with self.subTest(fragment=fragment):
                self.assertFalse(lane.usable(fragment))

    def test_a_continuation_row_is_not_a_query(self):
        self.assertFalse(lane.usable("in plateau state"))

    def test_a_real_phrase_survives(self):
        for query in ("edo state tenancy law", "power of attorney", "shop tenancy agreement"):
            with self.subTest(query=query):
                self.assertTrue(lane.usable(query))

    def test_fragments_never_reach_the_brief(self):
        found = lane.candidates(rows=[row("kano", page="https://docoga.com.ng/notice-to-quit-kano.html"),
                                      row("in plateau state", page="https://docoga.com.ng/"),
                                      row("edo state tenancy law", 6, 10.0)],
                                covered=set())
        self.assertEqual([c["query"] for c in found], ["edo state tenancy law"])


class TitleShapeTests(unittest.TestCase):
    """YouTube matches the first words. A title that does not start with the query is
    a title that cannot be found by the query."""

    def test_the_query_opens_the_title(self):
        title = lane.title_for("shop tenancy agreement",
                               "https://docoga.com.ng/shop-tenancy-agreement-nigeria.html", year=2026)
        self.assertTrue(title.lower().startswith("shop tenancy agreement"), title)

    def test_the_page_heading_supplies_the_hook(self):
        title = lane.title_for("shop tenancy agreement",
                               "https://docoga.com.ng/shop-tenancy-agreement-nigeria.html", year=2026)
        self.assertIn("commercial tenancy", title, title)

    def test_the_year_is_always_there(self):
        self.assertIn("(2026)", lane.title_for("power of attorney", "", year=2026))

    def test_a_long_hook_is_dropped_rather_than_truncated(self):
        title = lane.title_for("how many days does a tenant have to give notice",
                               "https://docoga.com.ng/tenant-rights-nigeria.html", year=2026)
        self.assertLessEqual(len(title), lane.MAX_TITLE, title)
        self.assertNotIn("…", title)

    def test_no_title_exceeds_the_ceiling(self):
        for query in ("quit notice from landlord to tenant",
                      "how many days does a tenant have to give notice",
                      "shop tenancy agreement"):
            with self.subTest(query=query):
                self.assertLessEqual(len(lane.title_for(query, "", year=2026)), lane.MAX_TITLE)

    def test_shouty_page_copy_is_lowered_but_place_names_survive(self):
        self.assertEqual(lane.sentence_case("How Many Months in Edo State, Nigeria"),
                         "How many months in Edo state, Nigeria")


class RankingTests(unittest.TestCase):
    def test_proven_demand_outranks_a_fluke(self):
        found = lane.candidates(rows=[row("quiet query", 1, 40.0, "https://docoga.com.ng/a.html"),
                                      row("proven query", 6, 10.0, "https://docoga.com.ng/b.html")],
                                covered=set())
        self.assertEqual(found[0]["query"], "proven query")

    def test_a_near_miss_is_marked_as_one(self):
        found = lane.candidates(rows=[row("near miss", 1, 9.3, "https://docoga.com.ng/a.html")], covered=set())
        self.assertTrue(found[0]["near_miss"])
        far = lane.candidates(rows=[row("head term", 1, 76.0, "https://docoga.com.ng/b.html")], covered=set())
        self.assertFalse(far[0]["near_miss"])

    def test_the_why_line_carries_the_evidence(self):
        found = lane.candidates(rows=[row("edo state tenancy law", 6, 10.0)], covered=set())
        self.assertIn("6 impressions", found[0]["why"])
        self.assertIn("position 10.0", found[0]["why"])


class NoDuplicatesTests(unittest.TestCase):
    def test_a_query_already_covered_by_an_episode_is_skipped(self):
        found = lane.candidates(rows=[row("caution fee nigeria", 3, 8.0, "https://docoga.com.ng/c.html")],
                                covered={lane._norm("Caution Fee in Nigeria: The Only 4 Deductions "
                                                    "a Landlord Can Make (Deep-Dive 2)")},
                                root=ROOT)
        self.assertEqual(found, [])

    def test_the_place_word_does_not_hide_a_covered_topic(self):
        covered = {lane._norm("Quit Notice in Nigeria: The Seven-Day Letter")}
        self.assertTrue(lane.covered_by("quit notice in nigeria", covered))

    def test_an_uncovered_topic_is_not_swallowed(self):
        covered = {lane._norm("Caution Fee in Nigeria: The Only 4 Deductions")}
        self.assertFalse(lane.covered_by("power of attorney", covered))

    def test_one_video_per_page(self):
        page = "https://docoga.com.ng/notice-to-quit-edo.html"
        found = lane.candidates(rows=[row("edo state tenancy law", 6, 10.0, page),
                                      row("tenancy law in edo state", 3, 9.3, page)],
                                covered=set())
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["query"], "edo state tenancy law")


class CheckModeTests(unittest.TestCase):
    """`--check` is what CI runs: it must fail on the essay shape that started this."""

    def write(self, payload):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(payload, handle, ensure_ascii=False)
        handle.close()
        return handle.name

    def test_a_good_brief_passes(self):
        path = self.write({"candidates": [
            {"query": "edo state tenancy law", "title": "Edo state tenancy law: how many months (2026)"}]})
        self.assertEqual(lane.check(path), [])

    def test_an_essay_title_fails_because_the_query_is_not_first(self):
        path = self.write({"candidates": [
            {"query": "caution fee", "title": "The Only 4 Deductions a Landlord Can Make (2026)"}]})
        self.assertTrue(any("does not contain its query" in p for p in lane.check(path)))

    def test_a_title_without_a_year_fails(self):
        path = self.write({"candidates": [
            {"query": "caution fee", "title": "Caution fee: the refund war"}]})
        self.assertTrue(any("no year" in p for p in lane.check(path)))

    def test_a_title_over_the_ceiling_fails(self):
        path = self.write({"candidates": [
            {"query": "quit notice", "title": "Quit notice " + "and " * 20 + "(2026)"}]})
        self.assertTrue(any("characters" in p for p in lane.check(path)))

    def test_two_candidates_cannot_share_a_title(self):
        one = {"query": "caution fee", "title": "Caution fee in Nigeria (2026)"}
        path = self.write({"candidates": [one, dict(one)]})
        self.assertTrue(any("share a title" in p for p in lane.check(path)))

    def test_an_empty_brief_is_not_a_failure(self):
        """Every measured query having an episode is a good day, not a red build."""
        self.assertEqual(lane.check(self.write({"candidates": []})), [])

    def test_a_missing_file_is_reported_not_raised(self):
        self.assertTrue(lane.check("/nonexistent/yt_search_lane.json"))


class TheCommittedBriefTests(unittest.TestCase):
    def test_the_repo_brief_is_valid_and_bigger_than_one_idea(self):
        problems = lane.check(ROOT / "logs" / "yt_search_lane.json")
        self.assertEqual(problems, [])
        data = json.loads((ROOT / "logs" / "yt_search_lane.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["candidates"]), lane.MIN_CANDIDATES,
                                "the whole point is a queue, not one video")

    def test_printing_is_quiet_on_stdout_only(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = lane.main(["--json", str(ROOT / "logs" / "yt_search_lane.json")])
        self.assertEqual(code, 0)
        self.assertIn("worth making", out.getvalue())


if __name__ == "__main__":
    unittest.main()
