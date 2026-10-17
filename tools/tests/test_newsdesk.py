"""tools/newsdesk.py — the brain reads the papers; only rent-and-paperwork stories, only fresh ones."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("GEMINI_QUOTA_LEDGER", os.path.join(tempfile.gettempdir(), "docoga-test-quota.json"))

import newsdesk  # noqa: E402

NOW = datetime(2026, 10, 17, 1, 30, tzinfo=timezone.utc)

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Punch</title>
<item><title>Lagos landlord punched over 75% rent hike as Nigerians call for rent regulation</title>
<link>https://punchng.com/a</link><pubDate>Thu, 15 Oct 2026 09:00:00 +0000</pubDate>
<description><![CDATA[<p>A reported incident in which a Lagos <b>landlord</b>&hellip;</p>]]></description></item>
<item><title>Super Eagles beat Benin 3-0</title><link>https://punchng.com/b</link>
<pubDate>Thu, 15 Oct 2026 10:00:00 +0000</pubDate><description>Tenants of the stadium cheered the rent-free win</description></item>
<item><title>Abuja tenants face rising rents and agency fees</title><link>https://punchng.com/c</link>
<pubDate>Wed, 16 Sep 2026 10:00:00 +0000</pubDate><description>Residents attributed the pressure to inflation</description></item>
<item><title>Naira gains against the dollar</title><link>https://punchng.com/d</link>
<pubDate>Fri, 16 Oct 2026 10:00:00 +0000</pubDate><description>Markets</description></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Cable</title>
<entry><title>Lagos tenancy bill: agency fee cap still not law</title><link href="https://thecable.ng/x"/>
<updated>2026-10-14T08:00:00Z</updated><summary>The bill remains at committee stage</summary></entry></feed>"""


class ParseTests(unittest.TestCase):
    def test_rss_and_atom_both_parse_with_clean_text(self):
        rows = newsdesk.parse_feed("Punch", RSS)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["summary"], "A reported incident in which a Lagos landlord…")
        self.assertEqual(rows[0]["published"], "2026-10-15T09:00:00+00:00")
        atom = newsdesk.parse_feed("TheCable", ATOM)
        self.assertEqual((atom[0]["link"], atom[0]["published"]), ("https://thecable.ng/x", "2026-10-14T08:00:00+00:00"))

    def test_garbage_is_an_empty_list_not_a_crash(self):
        self.assertEqual(newsdesk.parse_feed("X", b"<html>not a feed"), [])


class SelectTests(unittest.TestCase):
    def test_only_rent_stories_only_this_week_sport_never(self):
        rows = newsdesk.parse_feed("Punch", RSS) + newsdesk.parse_feed("TheCable", ATOM)
        picked = newsdesk.select(rows, now=NOW, days=7)
        titles = [p["title"] for p in picked]
        self.assertIn("Lagos landlord punched over 75% rent hike as Nigerians call for rent regulation", titles)
        self.assertIn("Lagos tenancy bill: agency fee cap still not law", titles)
        self.assertNotIn("Super Eagles beat Benin 3-0", titles, "sport is noise even when 'tenants' appears in the blurb")
        self.assertNotIn("Abuja tenants face rising rents and agency fees", titles, "a month old is not this week")
        self.assertNotIn("Naira gains against the dollar", titles)
        self.assertGreaterEqual(picked[0]["score"], picked[1]["score"], "the strongest story first")
        self.assertIn("landlord", next(p for p in picked if p["title"].startswith("Lagos landlord"))["matched"])


class PullTests(unittest.TestCase):
    def test_a_dead_paper_is_a_line_in_the_report_not_a_failure(self):
        def http(url, timeout=20):
            if "punch" in url:
                return 200, RSS
            if "cable" in url:
                return 200, ATOM
            raise OSError("timed out")
        logs = []
        data = newsdesk.pull(http=http, now=NOW, log=logs.append)
        self.assertEqual(len(data["items"]), 2)
        self.assertTrue(any("unreachable" in s for s in data["sources"]))
        self.assertTrue(all(len(it.get("summary", "")) <= 200 for it in data["items"]))

    def test_fresh_items_and_prompt_block(self):
        data = {"fetched": NOW.isoformat(), "items": [{"title": "T", "source": "Punch", "published": "2026-10-15T09:00:00+00:00"}]}
        self.assertEqual(len(newsdesk.fresh_items(data, now=NOW, pinned=[])), 1)
        self.assertEqual(newsdesk.fresh_items({"fetched": "2026-09-01T00:00:00+00:00", "items": data["items"]}, now=NOW, pinned=[]), [])
        self.assertIn("- T — Punch (2026-10-15)", newsdesk.prompt_block(data["items"]))
        self.assertIn("no fresh stories", newsdesk.prompt_block([]))


class PinnedShelfTests(unittest.TestCase):
    """17 Oct 2026: hand-dated stories ride ahead of the RSS pull and expire on their own date."""

    def test_pinned_stories_lead_expire_at_21_days_and_are_not_duplicated(self):
        import tempfile
        rows = [{"published": "2026-10-15", "source": "Trumpet", "title": "Landlord punched over rent hike"},
                {"published": "2026-09-20", "source": "Old", "title": "Stale story"},
                {"published": "", "source": "Nobody", "title": "Undated story"}]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "pinned.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            pins = newsdesk.pinned_items(path, now=NOW)
        self.assertEqual([p["title"] for p in pins], ["Landlord punched over rent hike"])
        self.assertTrue(pins[0]["pinned"])
        data = {"fetched": NOW.isoformat(), "items": [{"title": "Landlord punched over rent hike", "source": "Punch"},
                                                      {"title": "Other", "source": "Guardian"}]}
        merged = newsdesk.fresh_items(data, now=NOW, pinned=pins)
        self.assertEqual([m["title"] for m in merged], ["Landlord punched over rent hike", "Other"])
        self.assertEqual(newsdesk.fresh_items({"fetched": None, "items": []}, now=NOW, pinned=pins), pins,
                         "an empty RSS pull still leaves the pinned shelf")
        self.assertEqual(newsdesk.pinned_items(Path("/nonexistent/pinned.json"), now=NOW), [])

    def test_the_repo_shelf_is_valid_dated_and_sourced(self):
        path = Path(__file__).resolve().parents[2] / "brain" / "newsdesk_pinned.json"
        rows = json.loads(path.read_text(encoding="utf-8"))["items"]
        self.assertTrue(rows)
        for it in rows:
            self.assertRegex(it["published"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue(it["source"] and it["title"], it)


class WorkflowTests(unittest.TestCase):
    def test_the_brain_pulls_the_newsdesk_before_it_plans_and_commits_it(self):
        text = (ROOT / ".github" / "workflows" / "brain.yml").read_text(encoding="utf-8")
        self.assertLess(text.index("tools/newsdesk.py pull"), text.index("tools/brain.py \"${ARGS[@]}\""))
        self.assertIn("brain/newsdesk.json", text)


if __name__ == "__main__":
    unittest.main()
