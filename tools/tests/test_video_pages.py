"""tools/video_pages.py — a transcript page per published Deep-Dive (17 Oct 2026).

Pinned: the page is built from the episode folder + the long-form ledger only; it carries the
full transcript by chapter, the nocookie embed, VideoObject JSON-LD (with Clip chapters when
the aligned words exist), the tool link tagged ?s=yt; deleted uploads are skipped; the sitemap
gains each URL once; rebuilding without changes writes nothing.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import video_pages  # noqa: E402
import youtube_ledger  # noqa: E402

ROOT = TOOLS.parent


class VideoPages(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.site = self.tmp / "site"
        self.site.mkdir()
        (self.site / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n</urlset>\n',
            encoding="utf-8")
        self.episodes = self.tmp / "episodes"
        shutil.copytree(ROOT / "episodes" / "dd3", self.episodes / "dd3")
        meta = json.loads((self.episodes / "dd3" / "episode.json").read_text(encoding="utf-8"))
        self.yt_title = meta["youtube"]["title"]
        self.ledger = self.tmp / "longform.json"
        self.ledger.write_text(json.dumps([
            {"video_id": "GONE123", "title": self.yt_title, "privacy": "unlisted", "state": "uploaded", "date": "2026-10-14"},
            {"video_id": "LIVE456", "title": self.yt_title, "privacy": "public", "state": "scheduled", "date": "2026-10-19"},
        ]), encoding="utf-8")
        self.build = self.tmp / "build"
        (self.build / "dd3").mkdir(parents=True)
        (self.build / "dd3" / "words.json").write_text(json.dumps({
            "sections": [{"title": "The Hook", "start": 0, "end": 60}, {"title": "What a Receipt Is", "start": 60, "end": 130}],
            "words": [{"w": "show", "t0": 0, "t1": 0.4}, {"w": "receipts", "t0": 540, "t1": 541.2}]}), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self):
        with mock.patch.object(youtube_ledger, "deleted_ids", lambda path=None: {"GONE123"}):
            return video_pages.build(site=self.site, ledger=self.ledger, episodes=self.episodes,
                                     build_dir=self.build, log=lambda *a: None)

    def test_page_carries_transcript_player_schema_and_tool_link(self):
        written, urls = self._build()
        self.assertEqual(urls, ["https://docoga.com.ng/videos/dd3"])  # clean URL: Cloudflare 307s /x.html → /x
        self.assertIn("https://docoga.com.ng/videos/", written)
        page = (self.site / "videos" / "dd3.html").read_text(encoding="utf-8")
        self.assertIn("youtube-nocookie.com/embed/LIVE456", page, "the public upload, not the deleted one")
        self.assertNotIn("GONE123", page)
        self.assertIn("Show me your receipts. Four words.", page)             # the transcript
        self.assertGreaterEqual(page.count("<h3>"), 9)                        # one heading a chapter
        self.assertIn('<a class="cta" href="https://docoga.com.ng/?s=yt">', page)
        self.assertIn("General information", page)
        blob = page.split('<script type="application/ld+json">')[1].split("</script>")[0]
        schema = json.loads(blob)
        self.assertEqual(schema["@type"], "VideoObject")
        self.assertEqual(schema["uploadDate"], "2026-10-19")
        self.assertEqual(schema["duration"], "PT2M10S")
        self.assertEqual(schema["hasPart"][1]["startOffset"], 60)
        self.assertIn("rent receipt", schema["keywords"])
        self.assertTrue(schema["transcript"].startswith("Show me your receipts"))
        self.assertIn("1:00</span>What a Receipt Is", page)                 # chapter link with the stamp
        sitemap = (self.site / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(sitemap.count("<loc>https://docoga.com.ng/videos/dd3</loc>"), 1)
        self.assertIn("<loc>https://docoga.com.ng/videos/</loc>", sitemap)
        index = (self.site / "videos" / "index.html").read_text(encoding="utf-8")
        self.assertIn(self.yt_title, index)

    def test_rebuild_is_a_no_op_and_sitemap_is_not_duplicated(self):
        self._build()
        written, urls = self._build()
        self.assertEqual(written, [])
        self.assertEqual(len(urls), 1)
        sitemap = (self.site / "sitemap.xml").read_text(encoding="utf-8")
        self.assertEqual(sitemap.count("videos/dd3<"), 1)

    def test_without_aligned_words_the_page_still_builds(self):
        shutil.rmtree(self.build)
        written, urls = self._build()
        page = (self.site / "videos" / "dd3.html").read_text(encoding="utf-8")
        self.assertIn("<li>The Hook</li>", page)
        self.assertNotIn('"duration"', page)

    def test_no_published_episode_writes_nothing(self):
        self.ledger.write_text("[]", encoding="utf-8")
        written, urls = self._build()
        self.assertEqual((written, urls), ([], []))
        self.assertFalse((self.site / "videos").exists())

    def test_every_published_episode_has_its_page_in_the_repo(self):
        """site/videos/ is committed (the lane rewrites it with chapter times after each publish)."""
        for meta, row in video_pages.published_episodes():
            page = ROOT / "site" / "videos" / ("%s.html" % meta["id"])
            self.assertTrue(page.is_file(), page)
            self.assertIn(row["video_id"], page.read_text(encoding="utf-8"))
        self.assertIn("<loc>https://docoga.com.ng/videos/</loc>", (ROOT / "site" / "sitemap.xml").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
