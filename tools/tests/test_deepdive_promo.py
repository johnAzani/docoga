"""tools/deepdive_promo.py — every channel promotes the Deep-Dive (owner, 17 Oct 2026).

Pinned: which episode counts as "latest watchable" (scheduled uploads only once their slot has
passed; deleted ones never); the week's schedule per channel; the shape of each channel's words
(Facebook's link on its own line so it travels to the first comment; Threads link-free with the
link in the reply; Instagram with no URL but the bio pointer; Telegram valid MarkdownV2 once
escaped); and that the four generators actually pick the promo up on their day.
"""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "scripts"))

import deepdive_promo as dp  # noqa: E402
import fb_publish  # noqa: E402
import youtube_ledger  # noqa: E402
from telegram_mdv2 import escape, validate  # noqa: E402

LAGOS = dp.LAGOS


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.episodes = self.tmp / "episodes"
        shutil.copytree(ROOT / "episodes" / "dd3", self.episodes / "dd3")
        shutil.copytree(ROOT / "episodes" / "dd2", self.episodes / "dd2")
        self.t3 = json.loads((self.episodes / "dd3" / "episode.json").read_text(encoding="utf-8"))["youtube"]["title"]
        self.t2 = json.loads((self.episodes / "dd2" / "episode.json").read_text(encoding="utf-8"))["youtube"]["title"]
        self.ledger = self.tmp / "longform.json"
        self._gone = mock.patch.object(youtube_ledger, "deleted_ids", lambda path=None: {"DELETED"})
        self._gone.start()

    def tearDown(self):
        self._gone.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rows):
        self.ledger.write_text(json.dumps(rows), encoding="utf-8")

    def latest(self, now):
        return dp.latest(now=now, ledger=self.ledger, episodes_dir=self.episodes)


class Latest(Fixture):
    def test_a_scheduled_episode_counts_only_once_its_slot_has_passed(self):
        self.write([
            {"video_id": "NEW", "title": self.t3, "privacy": "private", "state": "scheduled",
             "publish_at": "2026-10-19T18:00:00Z", "date": "2026-10-19"},                       # 19:00 WAT Monday
            {"video_id": "OLD", "title": self.t2, "privacy": "unlisted", "state": "uploaded", "date": "2026-10-14"},
        ])
        before = self.latest(dt.datetime(2026, 10, 19, 18, 30, tzinfo=LAGOS))
        self.assertEqual(before["id"], "dd2", "before the slot the previous episode is still the latest")
        after = self.latest(dt.datetime(2026, 10, 19, 19, 5, tzinfo=LAGOS))
        self.assertEqual(after["id"], "dd3")
        self.assertEqual(after["published_on"], dt.date(2026, 10, 19))
        self.assertEqual(after["url"], "https://www.youtube.com/watch?v=NEW")
        self.assertEqual(after["page"], "https://docoga.com.ng/videos/dd3.html")
        self.assertEqual(after["learn"][:2], ["What a Receipt Is", "Seven Lines of Proof"])
        self.assertTrue(after["hook"].startswith("Show me your receipts."))
        self.assertLessEqual(len(after["hook"]), dp.HOOK_MAX)

    def test_deleted_and_failed_uploads_never_win(self):
        self.write([
            {"video_id": "DELETED", "title": self.t3, "privacy": "public", "state": "published", "date": "2026-10-16"},
            {"video_id": "BAD", "title": self.t3, "privacy": "public", "state": "failed", "date": "2026-10-16"},
            {"video_id": "OK2", "title": self.t2, "privacy": "unlisted", "state": "uploaded", "date": "2026-10-14"},
        ])
        ep = self.latest(dt.datetime(2026, 10, 17, 12, 0, tzinfo=LAGOS))
        self.assertEqual((ep["id"], ep["video_id"]), ("dd2", "OK2"))

    def test_no_watchable_episode_is_none_everywhere(self):
        self.write([])
        now = dt.datetime(2026, 10, 17, 12, 0, tzinfo=LAGOS)
        self.assertIsNone(self.latest(now))
        self.assertIsNone(dp.pack_for(now.date(), "telegram", ep=None))
        self.assertIsNone(dp.latest_link(now=now, ledger=self.ledger, episodes_dir=self.episodes))


class Schedule(Fixture):
    def setUp(self):
        super().setUp()
        self.write([{"video_id": "NEW", "title": self.t3, "privacy": "public", "state": "published",
                     "publish_at": "2026-10-19T18:00:00Z", "date": "2026-10-19"}])
        self.ep = self.latest(dt.datetime(2026, 10, 25, tzinfo=LAGOS))
        self.P = dt.date(2026, 10, 19)

    def stage(self, offset, channel):
        pack = dp.pack_for(self.P + dt.timedelta(days=offset), channel, ep=self.ep)
        return pack["stage"] if pack else None

    def test_the_week_after_an_episode(self):
        self.assertEqual(self.stage(0, "threads_evening"), "launch")
        self.assertIsNone(self.stage(0, "telegram"), "Monday's Telegram post went out at 09:00, before the slot")
        self.assertEqual(self.stage(1, "telegram"), "feature")
        self.assertEqual(self.stage(1, "facebook"), "feature")
        self.assertEqual(self.stage(2, "threads"), "recap")
        self.assertEqual(self.stage(2, "instagram"), "recap")
        self.assertIsNone(self.stage(2, "facebook"))
        self.assertIsNone(self.stage(1, "threads_evening"))
        for offset in range(3, 15):
            self.assertEqual(self.stage(offset, "telegram"), "footer", offset)
            self.assertIsNone(self.stage(offset, "facebook"), offset)
        self.assertIsNone(self.stage(15, "telegram"))
        self.assertIsNone(self.stage(-1, "telegram"))

    def test_facebook_words_put_the_youtube_link_on_its_own_line_for_the_first_comment(self):
        text = dp.pack_for(self.P + dt.timedelta(days=1), "facebook", ep=self.ep)["text"]
        body, link = fb_publish.split_link(text)
        self.assertEqual(link, "https://www.youtube.com/watch?v=NEW")
        self.assertNotIn("http", body, "no link survives in the body — Facebook's reach rule")
        self.assertIn("What you will learn:", body)
        self.assertIn("Send this to someone", body)
        self.assertLessEqual(text.count("#"), 4)
        self.assertEqual(fb_publish.link_line(link), "▶ The full episode, free (9 minutes): https://www.youtube.com/watch?v=NEW")
        self.assertEqual(fb_publish.link_line("https://docoga.com.ng/?s=fb"), "The page, free to start: https://docoga.com.ng/?s=fb")

    def test_telegram_words_escape_to_valid_markdownv2_with_both_links_and_the_button(self):
        pack = dp.pack_for(self.P + dt.timedelta(days=1), "telegram", ep=self.ep)
        self.assertIn("▶ Watch on YouTube: https://www.youtube.com/watch?v=NEW", pack["text"])
        self.assertIn("https://docoga.com.ng/videos/dd3.html?s=tg", pack["text"])
        self.assertEqual(validate(escape(pack["text"])), [])
        self.assertLessEqual(len(pack["text"]), 1000, "a photo caption is capped at 1,024")
        self.assertEqual(pack["buttons"][0][0]["url"], "https://www.youtube.com/watch?v=NEW")
        self.assertTrue(pack["card_text"].startswith("The Rent Receipt"))
        self.assertIn("Seven Lines of Proof", pack["card_text"])
        footer = dp.pack_for(self.P + dt.timedelta(days=5), "telegram", ep=self.ep)
        self.assertEqual(footer["stage"], "footer")
        self.assertEqual(footer["text"], "")
        self.assertEqual(footer["buttons"], pack["buttons"])

    def test_threads_launch_and_recap_are_link_free_with_the_link_in_the_reply(self):
        launch = dp.pack_for(self.P, "threads_evening", ep=self.ep)
        recap = dp.pack_for(self.P + dt.timedelta(days=2), "threads", ep=self.ep)
        for pack in (launch, recap):
            self.assertNotIn("http", pack["text"])
            self.assertLessEqual(len(pack["text"]), 500)
            self.assertIn("https://www.youtube.com/watch?v=NEW", pack["reply_text"])
            self.assertIn("?s=th", pack["reply_text"])
        self.assertTrue(launch["text"].startswith("New Deep-Dive, just published:"))
        self.assertIn("?", launch["text"], "a question — Threads ranks by replies")
        self.assertTrue(recap["text"].startswith("In case you missed it:"))
        self.assertNotEqual(launch["text"], recap["text"])

    def test_instagram_caption_names_the_bio_and_the_transcript_without_a_url(self):
        caption = dp.pack_for(self.P + dt.timedelta(days=2), "threads", ep=self.ep)["ig_caption"]
        self.assertIn("link in bio", caption)
        self.assertIn("docoga.com.ng/videos/dd3.html", caption)
        self.assertNotIn("http", caption)
        self.assertLessEqual(caption.count("#"), 5, "Instagram caps hashtags at five (Dec 2025)")
        self.assertLessEqual(len(caption), 2200)


def _feature(channel):
    return {"stage": "feature", "post_type": "deepdive", "episode": "dd3", "title": "T", "url": "https://www.youtube.com/watch?v=NEW",
            "text": "🎬 New Deep-Dive (9 minutes): T\n\nHook.\n\nWatch the full episode on YouTube:\nhttps://www.youtube.com/watch?v=NEW\n\nGeneral information, not legal advice. #DocOga",
            "card_text": "T\n• a", "reply_text": "▶ https://www.youtube.com/watch?v=NEW",
            "buttons": [[{"text": "▶ This week's Deep-Dive (9 min)", "url": "https://www.youtube.com/watch?v=NEW"}]]}


class Generators(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": os.path.join(self.tmp, "none")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_facebook_generator_posts_the_episode_on_its_day(self):
        import generate_facebook_content as fb
        with mock.patch.object(dp, "pack_for", lambda day, channel, **k: _feature(channel) if channel == "facebook" else None):
            content = fb.generate(dt.date(2026, 10, 20), write=False)
        self.assertEqual(content["post_type"], "deepdive")
        body, link = fb_publish.split_link(content["message"])
        self.assertEqual(link, "https://www.youtube.com/watch?v=NEW")

    def test_telegram_generator_leads_with_the_episode_button_on_its_day_and_appends_it_after(self):
        import generate_telegram_content as tg
        with mock.patch.object(dp, "pack_for", lambda day, channel, **k: _feature(channel)), \
                mock.patch.object(tg, "render_card", lambda *a, **k: None):
            content = tg.generate_daily_content()
        self.assertEqual(content["post_type"], "deepdive")
        self.assertEqual(content["buttons"][0][0]["text"], "▶ This week's Deep-Dive (9 min)")
        self.assertGreaterEqual(len(content["buttons"]), 2, "the usual rows still follow")
        self.assertEqual(validate(content["message"]), [])
        footer = dict(_feature("telegram"), stage="footer", text="")
        with mock.patch.object(dp, "pack_for", lambda day, channel, **k: footer), \
                mock.patch.object(tg, "render_card", lambda *a, **k: None):
            content = tg.generate_daily_content()
        self.assertNotEqual(content["post_type"], "deepdive")
        self.assertEqual(content["buttons"][-1][0]["url"], "https://www.youtube.com/watch?v=NEW")

    def test_threads_generator_launch_night_and_recap_day(self):
        import generate_threads_content as th
        launch = dict(_feature("threads"), stage="launch", text="New Deep-Dive, just published: T\n\nWhich part first?")
        with mock.patch.object(dp, "pack_for", lambda day, channel, **k: launch if channel == "threads_evening" else None):
            content = th.generate(dt.date(2026, 10, 19), write=False, slot="evening")
            lunch = th.generate(dt.date(2026, 10, 19), write=False, slot="lunch")
        self.assertEqual(content["post_type"], "deepdive")
        self.assertEqual(content["reply_text"], "▶ https://www.youtube.com/watch?v=NEW")
        self.assertEqual(content["card_text"], "T\n• a")
        self.assertIsNone(content["poll"])
        self.assertNotEqual(lunch["post_type"], "deepdive", "launch night touches the evening slot only")
        recap = dict(_feature("threads"), stage="recap", text="In case you missed it: T", ig_caption="IG words (link in bio)")
        with mock.patch.object(dp, "pack_for", lambda day, channel, **k: recap if channel == "threads" else None):
            content = th.generate(dt.date(2026, 10, 21), write=False, slot="lunch")
        self.assertEqual(content["post_type"], "deepdive")
        self.assertEqual(content["ig_caption"], "IG words (link in bio)")
        self.assertEqual(content["reply_text"], "▶ https://www.youtube.com/watch?v=NEW")

    def test_a_normal_day_is_untouched(self):
        import generate_facebook_content as fb
        with mock.patch.object(dp, "pack_for", lambda *a, **k: None):
            content = fb.generate(dt.date(2026, 10, 20), write=False)
        self.assertNotEqual(content["post_type"], "deepdive")


if __name__ == "__main__":
    unittest.main()
