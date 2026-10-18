"""Shorts trail Deep-Dives, and hooks follow the pattern the numbers reward.

First YouTube stats snapshot (14 Oct 2026, docs/YOUTUBE_PERFORMANCE.md): the
STAKES hook "Change the lock. Become the defendant." took 108 views; every
QUESTION hook sat at 2–16; the long-form episodes sat at 0–2 because nothing
pointed a Short viewer at them. These tests keep both decisions in force.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "scripts", ROOT / "tools", ROOT / "tools" / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import deepdive_links
import deepdive_promo  # noqa: E402
import generate_short_video as words  # noqa: E402
import shorts_reel  # noqa: E402
from test_youtube_short_generation import parse_github_output  # noqa: E402


class HookPatternTests(unittest.TestCase):
    def test_every_rotation_hook_is_a_two_beat_consequence_line(self):
        for topic in words.VIDEO_SCRIPTS:
            hook = topic["slides"][0]["text"]
            with self.subTest(title=topic["title"]):
                setup, consequence = shorts_reel.split_hook(hook)
                self.assertTrue(consequence, "hook must be 'careless act. consequence.'")
                self.assertNotIn("?", hook, "QUESTION hooks lost to STAKES hooks 2–16 vs 108")
                self.assertTrue(setup.endswith("."), setup)
                self.assertLessEqual(len(setup.split()), 4)
                self.assertLessEqual(len(consequence.split()), 4)

    def test_the_title_is_the_hook_line(self):
        """The Shorts feed shows the title under the frame; it must carry the stakes too."""
        for topic in words.VIDEO_SCRIPTS:
            with self.subTest(title=topic["title"]):
                self.assertEqual(" ".join(topic["title"].upper().split()),
                                 " ".join(topic["slides"][0]["text"].upper().split()))
                self.assertNotIn("?", topic["title"])

    def test_a_stakes_hook_renders_as_two_cascades_consequence_in_yellow(self):
        reel = shorts_reel.reel_from_topic(words.VIDEO_SCRIPTS[0], "/tmp/_t.mp4")
        cascades = [b for b in reel["scenes"][0]["beats"] if b["kind"] == "cascade"]
        self.assertEqual(len(cascades), 2)
        self.assertEqual(cascades[1]["color"], shorts_reel.ms.YELLOW)
        self.assertLess(cascades[0]["y"], cascades[1]["y"])

    def test_single_sentence_hooks_still_render_whole(self):
        self.assertEqual(shorts_reel.split_hook("BEFORE YOU PAY"), ("BEFORE YOU PAY", None))
        self.assertEqual(shorts_reel.split_hook("Pay late. Pay more."), ("PAY LATE.", "PAY MORE."))


class ParentLinkTests(unittest.TestCase):
    def test_every_rotation_topic_names_a_resolvable_parent(self):
        for topic in words.VIDEO_SCRIPTS:
            with self.subTest(title=topic["title"]):
                self.assertTrue(topic.get("parent"), "every Short trails a Deep-Dive")
                # Raises for an unknown episode folder or a malformed yt: id.
                deepdive_links.parent_link(topic["parent"])

    def test_a_published_episode_resolves_through_the_longform_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            eps = Path(tmp) / "episodes"
            (eps / "ddx").mkdir(parents=True)
            (eps / "ddx" / "episode.json").write_text(json.dumps(
                {"id": "ddx", "youtube": {"title": "Episode X"}}), encoding="utf-8")
            ledger = Path(tmp) / "ledger.json"
            self.assertIsNone(deepdive_links.parent_link("ddx", ledger=ledger, episodes_dir=eps))
            ledger.write_text(json.dumps([
                {"title": "Episode X", "video_id": "NEWnewNEW01", "state": "uploaded"},
                {"title": "Episode X", "video_id": "OLDoldOLD01", "state": "uploaded"},
            ]), encoding="utf-8")
            title, url = deepdive_links.parent_link("ddx", ledger=ledger, episodes_dir=eps)
            self.assertEqual(title, "Episode X")
            self.assertEqual(url, "https://www.youtube.com/watch?v=NEWnewNEW01",
                             "the newest copy wins — a re-published episode replaces the old id")

    def test_legacy_longforms_resolve_by_video_id(self):
        title, url = deepdive_links.parent_link("yt:08wCJ0EmTkU")
        self.assertEqual(url, "https://www.youtube.com/watch?v=08wCJ0EmTkU")
        self.assertIn("Tenancy Agreement", title)
        with self.assertRaises(ValueError):
            deepdive_links.parent_link("yt:short")
        with self.assertRaises(ValueError):
            deepdive_links.parent_link("dd999")

    def test_dd2_resolves_to_the_live_episode(self):
        title, url = deepdive_links.parent_link("dd2")
        self.assertIn("Deep-Dive 2", title)
        self.assertTrue(url.startswith("https://www.youtube.com/watch?v="))


class DailyOutputTests(unittest.TestCase):
    """The description leads with the parent link; GITHUB_OUTPUT stays parseable."""

    def _run(self, topic):
        import youtube_short_daily as daily
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "gh"
            out.write_text("", encoding="utf-8")
            video = Path(tmp) / "s.mp4"
            video.write_bytes(b"0" * 20_000)
            with patch.object(daily.shorts_reel, "render_topic", return_value=video), \
                 patch.object(daily.shorts_reel, "topic_for", return_value=topic), \
                 patch.dict(os.environ, {"GITHUB_OUTPUT": str(out)}):
                daily.main()
            return parse_github_output(out.read_text(encoding="utf-8"))

    def test_published_parent_leads_the_description_and_offers_a_pinned_comment(self):
        topic = next(t for t in words.VIDEO_SCRIPTS if t["parent"] == "dd2")
        outputs = self._run(topic)
        self.assertTrue(outputs["description"].startswith("Watch the full Deep-Dive — "))
        self.assertIn("https://www.youtube.com/watch?v=", outputs["description"].splitlines()[1])
        self.assertIn("not legal advice", outputs["description"].lower())
        self.assertIn("https://docoga.com.ng", outputs["description"])
        self.assertTrue(outputs["pinned_comment"].startswith("Full episode"))
        self.assertEqual(outputs["parent_url"], deepdive_links.parent_link("dd2")[1])

    def test_description_carries_the_words_search_can_read(self):
        """17 Oct 2026: the spoken hook, the tip headlines, three hashtags, the Telegram channel."""
        topic = dict(words.VIDEO_SCRIPTS[0], parent="dd3")
        with patch.object(deepdive_links, "parent_link", return_value=None), \
                patch.object(deepdive_promo, "latest_link", return_value=None):
            outputs = self._run(topic)
        desc = outputs["description"]
        self.assertTrue(desc.startswith(topic["slides"][0]["say"][:40]), desc[:80])
        self.assertIn("In this Short:", desc)
        self.assertIn("• Take the receipt", desc)
        self.assertNotIn("GENERAL INFO ONLY", desc)              # the disclaimer slide is not a tip
        self.assertIn("https://t.me/docogadaily", desc)
        self.assertEqual(desc.count("#"), 3)
        self.assertTrue(desc.rstrip().endswith("#NigeriaRent"))
        self.assertLess(len(desc), 4900)

    def test_a_short_without_a_published_parent_trails_the_latest_episode(self):
        """17 Oct 2026 (owner: promote the Deep-Dives everywhere): a brain Short, or one whose
        parent is still in the queue, carries the latest watchable episode instead."""
        topic = dict(words.VIDEO_SCRIPTS[0], parent="brain")
        with patch.object(deepdive_promo, "latest_link",
                          return_value=("Caution Fee: The Refund War", "https://www.youtube.com/watch?v=pl5Z8ueg1ZI")):
            outputs = self._run(topic)
        self.assertTrue(outputs["description"].startswith("Watch the full Deep-Dive — Caution Fee"))
        self.assertEqual(outputs["parent_url"], "https://www.youtube.com/watch?v=pl5Z8ueg1ZI")
        self.assertTrue(outputs["pinned_comment"].startswith("Full episode"))

    def test_unpublished_parent_leaves_a_clean_description(self):
        topic = dict(words.VIDEO_SCRIPTS[0], parent="dd3")
        with patch.object(deepdive_links, "parent_link", return_value=None), \
                patch.object(deepdive_promo, "latest_link", return_value=None):
            outputs = self._run(topic)
        self.assertFalse(outputs["description"].startswith("Watch the full Deep-Dive"))
        self.assertIn("Practical document-keeping", outputs["description"])
        self.assertEqual(outputs["pinned_comment"], "")
        self.assertEqual(outputs["parent_url"], "")
        self.assertEqual(outputs["title"], words.yt_title(topic))
        self.assertTrue(outputs["title"].endswith(" #Shorts"))


if __name__ == "__main__":
    unittest.main()
