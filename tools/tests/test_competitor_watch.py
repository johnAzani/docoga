"""The field (2 Nov 2026): what competitors published, read from public feeds at ₦0, handed to the
brain and the Monday scorecard. Owner: "keep me way ahead of my competitors — I want to dominate." """
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import competitor_watch as cw  # noqa: E402

NOW = datetime(2026, 11, 2, 6, 0, tzinfo=timezone.utc)

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Lagos Tenancy Bill 2026: what changes for tenants</title><link>https://rival.ng/bill</link>
<pubDate>Fri, 30 Oct 2026 09:00:00 +0000</pubDate><description>agents and fees</description></item>
<item><title>Our office party photos</title><link>https://rival.ng/party</link>
<pubDate>Fri, 30 Oct 2026 10:00:00 +0000</pubDate><description>fun</description></item>
<item><title>Quit notice periods explained</title><link>https://rival.ng/old</link>
<pubDate>Mon, 01 Sep 2026 09:00:00 +0000</pubDate><description>old</description></item>
</channel></rss>"""

INDEX = b"""<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://tool.ng/listing-sitemap.xml</loc></sitemap>
<sitemap><loc>https://tool.ng/post-sitemap.xml</loc></sitemap></sitemapindex>"""
URLSET = b"""<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://tool.ng/free-rent-receipt-generator-nigeria</loc><lastmod>2026-10-28</lastmod></url>
<url><loc>https://tool.ng/rent</loc><lastmod>2026-10-28</lastmod></url>
<url><loc>https://tool.ng/propertypro-1qlct-rent-flat-lekki</loc><lastmod>2026-10-28</lastmod></url>
<url><loc>https://tool.ng/bill-of-quantities-template-excel</loc><lastmod>2026-10-28</lastmod></url>
<url><loc>https://tool.ng/about-us</loc><lastmod>2026-10-28</lastmod></url>
<url><loc>https://tool.ng/tenancy-agreement</loc><lastmod>2026-06-01</lastmod></url></urlset>"""
YT_PAGE = (b'<html><meta itemprop="channelId" content="UCabcdefghijklmnop1234">...'
           b'"channelId":"UCrelatedvideo000000000"...</html>')
YT_FEED = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Landlord locked me out: the law</title>
<link href="https://www.youtube.com/watch?v=abc"/><published>2026-10-29T10:00:00+00:00</published></entry></feed>"""


def fake_http(url, timeout=0):
    routes = {"https://rival.ng/feed/": RSS, "https://tool.ng/sitemap.xml": INDEX, "https://tool.ng/post-sitemap.xml": URLSET,
              "https://www.youtube.com/@lawyer": YT_PAGE,
              "https://www.youtube.com/feeds/videos.xml?channel_id=UCabcdefghijklmnop1234": YT_FEED}
    if url in routes:
        return 200, routes[url]
    if url == "https://down.ng/feed/":
        raise OSError("timed out")
    return 404, b""


FIELD = [
    {"name": "Rival blog", "kind": "content", "url": "https://rival.ng", "feeds": ["https://rival.ng/feed/"], "note": "x"},
    {"name": "Tool", "kind": "tool", "url": "https://tool.ng", "feeds": ["https://tool.ng/sitemap.xml"], "note": "x"},
    {"name": "Lawyer on YouTube", "kind": "creator", "url": "https://www.youtube.com/@lawyer", "feeds": [], "note": "x"},
    {"name": "TikTok lawyer", "kind": "creator", "url": "https://www.tiktok.com/@x", "feeds": [], "note": "no feed"},
    {"name": "Down", "kind": "content", "url": "https://down.ng", "feeds": ["https://down.ng/feed/"], "note": "x"},
]


class Pull(unittest.TestCase):
    def test_rss_sitemaps_and_youtube_pages_are_read_filtered_to_the_business_and_dated(self):
        data = cw.pull(http=fake_http, now=NOW, days=14, log=lambda *a: None, field=FIELD)
        titles = {(it["competitor"], it["title"]) for it in data["items"]}
        self.assertIn(("Rival blog", "Lagos Tenancy Bill 2026: what changes for tenants"), titles)
        self.assertNotIn(("Rival blog", "Our office party photos"), titles, "off-topic is not the field")
        self.assertNotIn(("Rival blog", "Quit notice periods explained"), titles, "September is outside the window")
        self.assertIn(("Tool", "Free rent receipt generator nigeria"), titles, "a sitemap index is followed; lastmod inside the window")
        self.assertNotIn(("Tool", "About us"), titles)
        self.assertNotIn(("Tool", "Rent"), titles, "a menu page is not a publication")
        self.assertFalse(any("1qlct" in t for _, t in titles), "a listing id is not a publication")
        self.assertNotIn(("Tool", "Bill of quantities template excel"), titles, "not tenancy")
        self.assertFalse(any("listing-sitemap" in s for s in data["sources"]), "an index with a post sitemap skips the listing one")
        self.assertNotIn(("Tool", "Tenancy agreement"), titles, "June lastmod is old")
        self.assertIn(("Lawyer on YouTube", "Landlord locked me out: the law"), titles, "channel id read from the page → Atom feed")
        self.assertEqual(cw.youtube_feed_for("https://www.youtube.com/@lawyer", http=fake_http),
                         "https://www.youtube.com/feeds/videos.xml?channel_id=UCabcdefghijklmnop1234",
                         "the page's own channel (itemprop), not the first related video's")
        self.assertEqual(data["unwatchable"], ["TikTok lawyer"])
        self.assertTrue(any("unreachable" in s for s in data["sources"]), "a dead feed is reported, never fatal")
        self.assertEqual(data["items"][0]["published"][:10], "2026-10-30", "newest first")

    def test_the_prompt_block_and_the_scorecard_read_the_pull_and_age_it_out(self):
        data = cw.pull(http=fake_http, now=NOW, days=14, log=lambda *a: None, field=FIELD)
        items = cw.fresh_items(data, now=NOW)
        self.assertEqual(len(items), 3)
        self.assertEqual(cw.fresh_items(data, now=datetime(2026, 11, 20, tzinfo=timezone.utc)), [], "a stale pull misleads — dropped")
        block = cw.prompt_block(items, field=FIELD)
        self.assertIn("THE FIELD", block)
        self.assertIn("never name a rival", block)
        self.assertIn("Rival blog: Lagos Tenancy Bill 2026", block)
        self.assertIn("1 document tools", block)
        self.assertIn("lead, do not follow", cw.prompt_block([], field=FIELD))
        lines = cw.scorecard_lines(data, now=NOW)
        self.assertTrue(lines[0].startswith("- last deep research:"), lines[0])
        self.assertIn("3 item(s) from 3 competitor(s)", lines[2])
        self.assertIn("TikTok lawyer", lines[2])
        self.assertTrue(any("Rival blog" in l for l in lines))
        self.assertEqual(cw.scorecard_lines({"items": []}, now=NOW)[2][:16], "- not pulled yet")

    def test_the_cli_writes_the_file_and_the_real_field_map_is_well_formed(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(cw, "_http", fake_http), \
                mock.patch.object(cw, "load_field", lambda path=None: FIELD):
            out = Path(tmp) / "field.json"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cw.main(["pull", "--out", str(out)])
            self.assertEqual(rc, 0)
            self.assertIn("FIELD_ITEMS=3", buf.getvalue())
            self.assertEqual(len(json.loads(out.read_text())["items"]), 3)
        rows = cw.load_field()
        self.assertGreaterEqual(len(rows), 8)
        self.assertTrue(all(r["url"].startswith("https://") for r in rows))
        self.assertTrue(any(r["kind"] == "tool" for r in rows) and any(r["kind"] == "creator" for r in rows))

    def test_the_brain_and_the_workflow_carry_the_field(self):
        src = (ROOT / "tools" / "brain.py").read_text(encoding="utf-8")
        self.assertIn("field=competitor_watch.fresh_items()", src)
        self.assertIn("{competitor_watch.prompt_block(ctx.get('field') or [])}", src)
        wf = (ROOT / ".github" / "workflows" / "brain.yml").read_text(encoding="utf-8")
        self.assertIn("python3 tools/competitor_watch.py pull", wf)
        self.assertIn("logs/competitor_watch.json", wf.split("Commit what the brain decided", 1)[1])
        sc = (ROOT / "tools" / "brain_scorecard.py").read_text(encoding="utf-8")
        self.assertIn("### Competitor watch — the field this week (🔒 docs/DOMINANCE.md)", sc)


if __name__ == "__main__":
    unittest.main()
