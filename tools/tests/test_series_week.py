"""Series weeks (23 Oct 2026): five weekday Shorts on one law, numbered, each end card naming
tomorrow's part. The spine is deterministic from the date (tools/series_week.py); the brain
writes to the day's angle; a rotation script wears the series only when it honestly fits; the
cover, the title, the description, the captions and the dashboard all read the same frame."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "tools", ROOT / "scripts", ROOT / "tools" / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import brain_drafts  # noqa: E402
import series_week as sw  # noqa: E402

MON = date(2026, 10, 26)   # the first series Monday: Rent receipt law
TUE = date(2026, 10, 27)
FRI = date(2026, 10, 30)
SAT = date(2026, 10, 31)
MON2 = date(2026, 11, 2)   # week two: Tenancy agreement


class SpineTests(unittest.TestCase):
    def test_six_themes_five_parts_each_and_every_label_fits_the_screen(self):
        self.assertGreaterEqual(len(sw.SERIES), 6)
        self.assertEqual(len({s["slug"] for s in sw.SERIES}), len(sw.SERIES))
        for s in sw.SERIES:
            with self.subTest(series=s["slug"]):
                self.assertEqual(len(s["parts"]), sw.TOTAL)
                self.assertIn(s["tool"], brain_drafts.TOOLS, "the deep link must be a real tool page")
                self.assertTrue(s["words"])
                self.assertLessEqual(len(sw.masthead(dict(name=s["name"], part=5, total=5))), sw.LABEL_MAX)
                for part in s["parts"]:
                    self.assertLessEqual(len(part["label"]), 26, part["label"])
                    self.assertGreater(len(part["angle"]), 30, "the angle is a brief, not a label")

    def test_the_week_is_read_from_the_date(self):
        s = sw.series_for(MON)
        self.assertEqual((s["slug"], s["part"], s["total"]), ("rent-receipt-law", 1, 5))
        self.assertEqual(s["next_label"], "What a receipt must show")
        self.assertEqual(s["prev_label"], "")
        self.assertEqual(sw.series_for(FRI)["part"], 5)
        self.assertEqual(sw.series_for(FRI)["next_label"], "")
        self.assertEqual(sw.series_for(MON2)["slug"], "tenancy-agreement")
        self.assertIsNone(sw.series_for(SAT), "no Short on Saturday, no part")
        self.assertIsNone(sw.series_for(date(2026, 10, 23)), "before the first series Monday: plain Shorts")
        self.assertIsNone(sw.series_for(MON, env={"SHORTS_SERIES_WEEK": "off"}), "the kill switch")
        self.assertEqual(sw.series_for("2026-10-27")["part"], 2)

    def test_masthead_pointer_and_sentence(self):
        s = sw.series_for(TUE)
        self.assertEqual(sw.masthead(s), "RENT RECEIPT LAW · 2 OF 5")
        self.assertEqual(sw.pointer(s), "PART 3 TOMORROW · PAID, NO RECEIPT. NOW WHAT")
        self.assertEqual(sw.pointer(s, "Paid cash, no paper?"), "PART 3 TOMORROW · PAID CASH, NO PAPER?")
        self.assertEqual(sw.pointer(s, "You paid. No receipt. Do this today, not next week."),
                         "PART 3 TOMORROW · PAID, NO RECEIPT. NOW WHAT", "a title too long for one glance line → the plan's label")
        self.assertLessEqual(len(sw.pointer(s, "a very long brain title that would never fit on one glance line at all")), 44)
        self.assertEqual(sw.pointer(sw.series_for(FRI)), "SERIES COMPLETE · ALL 5 ON THE CHANNEL")
        self.assertEqual(sw.sentence(s), "Part 2 of 5 in this week's series on the rent receipt law. Tomorrow: Paid, no receipt. Now what.")
        self.assertTrue(sw.sentence(sw.series_for(FRI)).endswith("All five parts are on the channel."))

    def test_a_rotation_script_wears_the_series_only_when_it_fits(self):
        import generate_short_video as words
        receipt = next(s for s in words.VIDEO_SCRIPTS if "receipt" in s["title"].lower())
        photos = next(s for s in words.VIDEO_SCRIPTS if "photos" in s["title"].lower())
        s = sw.series_for(MON)
        self.assertTrue(sw.fits(s, receipt))
        self.assertFalse(sw.fits(s, photos))
        self.assertIn("series", sw.attach(receipt, MON))
        self.assertNotIn("series", sw.attach(photos, MON))
        self.assertNotIn("series", sw.attach(receipt, SAT))
        # a brain Short written to the part wears it; one written to another week's part does not
        brain_short = {"title": "x", "brain": "2026-10-26", "slides": []}
        self.assertIn("series", sw.attach(brain_short, MON, pack_series={"slug": "rent-receipt-law", "part": 1}))
        self.assertNotIn("series", sw.attach(brain_short, MON, pack_series={"slug": "notice-to-quit", "part": 1}))
        self.assertNotIn("series", sw.attach(brain_short, MON))

    def test_the_brief_the_brain_reads(self):
        text = sw.brief(sw.series_for(TUE))
        self.assertIn("RENT RECEIPT LAW (part 2 of 5 today)", text)
        self.assertIn('Today\'s part: "What a receipt must show"', text)
        self.assertIn('Yesterday\'s part was "Why the receipt is law"', text)
        self.assertIn('Tomorrow\'s part is "Paid, no receipt. Now what"', text)
        self.assertIn("`rent-receipt`", text)
        self.assertEqual(sw.brief(None), "")


class LaneTests(unittest.TestCase):
    """The Short's words, picture, title, description and captions on a series day."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.drafts = Path(self.tmp.name) / "drafts"
        self.drafts.mkdir()
        env = patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": str(self.drafts), "DOCOGA_BRAIN": "on", "DOCOGA_FRESH": "off",
                                      "SHORTS_SEARCH_KICKER": "", "SHORTS_SERIES_WEEK": "on"})
        env.start()
        self.addCleanup(env.stop)

    def pack(self, day, title, part, slug="rent-receipt-law"):
        tips = [{"text": "Tip %d" % i, "sub": "sub", "say": "say " * 20} for i in range(1, 5)]
        pack = {"version": 1, "status": "approved", "date": day.isoformat(), "theme": "t-%d" % part,
                "post": {"headline": "h", "lines": ["l"], "cta": "c", "hashtags": ["#DocOga"]},
                "threads": {"text": "t", "hashtags": []}, "visual": {}, "tool": "rent-receipt",
                "short": {"title": title, "hook_sub": "sub", "hook_say": "say " * 22, "hook_text": title.upper(),
                          "tips": tips, "series": {"slug": slug, "name": "Rent receipt law", "part": part, "total": 5}}}
        (self.drafts / ("%s.json" % day.isoformat())).write_text(json.dumps(pack), encoding="utf-8")
        return pack

    def test_the_rotation_monday_is_part_one_and_a_non_fitting_tuesday_stays_plain(self):
        import generate_short_video as words
        mon = words.script_for_date(MON)
        self.assertIn("receipt", mon["title"].lower())
        self.assertEqual(mon["series"]["part"], 1)
        self.assertEqual(words.yt_title(mon), "Rent receipt in Nigeria: pay without a receipt, pay twice (part 1 of 5) #Shorts")
        tue = words.script_for_date(TUE)
        self.assertNotIn("series", tue, "the agent script does not pretend to be receipt law")
        self.assertNotIn("part", words.yt_title(tue))
        self.assertIn(words.script_for_date(date(2026, 1, 5)), words.VIDEO_SCRIPTS, "before START the rotation is untouched")

    def test_a_brain_short_wears_the_part_and_names_tomorrows_by_its_real_title(self):
        import generate_short_video as words
        self.pack(TUE, "Six lines every receipt needs.", 2)
        self.pack(date(2026, 10, 28), "Paid cash, no paper?", 3)
        topic = words.script_for_date(TUE)
        self.assertEqual(topic["brain"], TUE.isoformat())
        self.assertEqual(topic["series"]["part"], 2)
        self.assertEqual(topic["series"]["next_title"], "Paid cash, no paper?")
        self.assertEqual(words.yt_title(topic), "Six lines every receipt needs (part 2 of 5) #Shorts")
        self.assertEqual(sw.pointer(topic["series"], topic["series"]["next_title"]),
                         "PART 3 TOMORROW · PAID CASH, NO PAPER?")

    def test_the_reel_carries_the_masthead_and_the_pointer_and_a_plain_day_does_not(self):
        import generate_short_video as words
        import shorts_reel
        reel = shorts_reel.reel_from_topic(words.script_for_date(MON), Path(self.tmp.name) / "s.mp4")
        kickers = [b["text"] for b in reel["scenes"][0]["beats"] if b["kind"] == "kicker"]
        self.assertEqual(kickers, ["RENT RECEIPT LAW · 1 OF 5"])
        end = [b for b in reel["scenes"][-1]["beats"] if b["kind"] == "kicker"]
        self.assertEqual(end[0]["text"], "PART 2 TOMORROW · WHAT A RECEIPT MUST SHOW")
        self.assertEqual(end[0]["color"], shorts_reel.ms.YELLOW)
        self.assertLess(end[0]["y"], end[1]["y"], "the pointer sits above the disclaimer and the follow line")
        plain = shorts_reel.reel_from_topic(words.script_for_date(TUE), Path(self.tmp.name) / "p.mp4")
        self.assertFalse([b for b in plain["scenes"][-1]["beats"] if "TOMORROW" in str(b.get("text"))])
        self.assertNotIn("OF 5", [b["text"] for b in plain["scenes"][0]["beats"] if b["kind"] == "kicker"][0])

    def test_an_explicit_search_kicker_still_wins_on_the_screen(self):
        import generate_short_video as words
        import shorts_reel
        with patch.dict(os.environ, {"SHORTS_SEARCH_KICKER": "rent receipt format"}):
            reel = shorts_reel.reel_from_topic(words.script_for_date(MON), Path(self.tmp.name) / "k.mp4")
        self.assertEqual([b["text"] for b in reel["scenes"][0]["beats"] if b["kind"] == "kicker"], ["RENT RECEIPT FORMAT"])

    def test_description_and_captions_say_which_part_and_what_tomorrow_is(self):
        import generate_short_video as words
        import reel_caption
        import youtube_short_daily as lane
        topic = words.script_for_date(MON)
        description = lane.describe(topic)
        self.assertIn("Part 1 of 5 in this week's series on the rent receipt law. Tomorrow: What a receipt must show.", description)
        self.assertLess(description.index("Part 1 of 5"), description.index("In this Short:"))
        for platform in ("facebook", "instagram"):
            text = reel_caption.caption(platform, topic["title"], description, MON)
            self.assertIn("Part 1 of 5 in this week's series on the rent receipt law.", text, platform)
        tiktok = reel_caption.caption("tiktok", topic["title"], description, MON)
        self.assertTrue(tiktok.startswith("Rent receipt law Nigeria:"), tiktok)
        self.assertIn("Part 1 of 5 · Rent receipt law · tomorrow: What a receipt must show", tiktok)
        self.assertLessEqual(len(tiktok), reel_caption.TIKTOK_MAX)
        plain = lane.describe(words.script_for_date(TUE))
        self.assertNotIn("this week's series", plain)
        self.assertEqual(reel_caption.series_from(plain), "")
        self.assertIsNone(reel_caption.series_parts(plain))

    def test_the_dashboard_plan_names_the_part(self):
        import dashboard_feed
        self.pack(TUE, "Six lines every receipt needs.", 2)
        root = Path(self.tmp.name)
        (root / "brain").mkdir()
        (root / "brain" / "drafts").symlink_to(self.drafts)
        rows = dashboard_feed.plan(datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc), root=root, days=1)
        self.assertEqual(rows[0]["series"], "Rent receipt law · part 2 of 5")
        self.assertIn("d.series", (ROOT / "site" / "admin.html").read_text(encoding="utf-8"))


class BrainTests(unittest.TestCase):
    """The brain writes to the day's angle and stamps the part on the Short it approves."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        env = patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": str(root / "drafts"), "DOCOGA_BRAIN": "on", "DOCOGA_FRESH": "off",
                                      "BRAIN_PLATES": "off", "GEMINI_API_KEY": "test-key"})
        env.start()
        self.addCleanup(env.stop)
        import brain
        import gemini_quota
        import newsdesk
        import listening
        self.brain = brain
        for target, name, value in ((brain, "SAID", root / "said.json"), (brain, "REFUSED", root / "refused.json"),
                                    (brain, "FEEDBACK", root / "feedback.md"), (newsdesk, "PINNED", root / "nd_p.json"),
                                    (newsdesk, "OUT", root / "nd.json"), (listening, "OUT", root / "li.json"),
                                    (gemini_quota, "LEDGER", root / "quota.json")):
            p = patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_the_prompt_carries_the_part_and_the_approved_short_is_stamped(self):
        from test_brain import good_pack
        ctx = self.brain.day_context(TUE, said=[])
        self.assertEqual(ctx["series"]["part"], 2)
        prompt = self.brain.prompt_for(ctx)
        self.assertIn("THIS WEEK'S SHORTS SERIES — RENT RECEIPT LAW (part 2 of 5 today)", prompt)
        self.assertIn("WORD BUDGET", prompt)
        self.assertIn("28 + 4 x 32 = 156 fits", prompt)
        ctx["facts_by_id"] = {f["id"]: f for f in ctx["facts"]}
        approved = self.brain.approve(good_pack(TUE), ctx)
        self.assertEqual(approved["short"]["series"], {"slug": "rent-receipt-law", "name": "Rent receipt law",
                                                       "part": 2, "total": 5, "label": "What a receipt must show"})
        topic = brain_drafts.short_topic(approved)
        self.assertEqual(topic["pack_series"]["part"], 2)
        weekend = self.brain.day_context(SAT, said=[])
        self.assertIsNone(weekend["series"])
        self.assertNotIn("SHORTS SERIES", self.brain.prompt_for(weekend))
        self.assertIsNone(self.brain.approve(good_pack(SAT, short=None), weekend)["short"])

    def test_refusals_are_remembered_newest_first_and_capped(self):
        path = Path(self.tmp.name) / "refused.json"
        for i in range(45):
            self.brain.remember_refusal(date(2026, 10, 1) + __import__("datetime").timedelta(days=i), ["short.tips: exactly four", "x" * 300],
                                        path=path, now=datetime(2026, 10, 23, 7, 0, tzinfo=timezone.utc))
        rows = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), self.brain.REFUSED_KEEP)
        self.assertEqual(rows[0]["date"], "2026-11-14")
        self.assertEqual(len(rows[0]["problems"][1]), 200)
        self.assertIn("short_day", rows[0])
        wf = (ROOT / ".github" / "workflows" / "brain.yml").read_text(encoding="utf-8")
        self.assertIn("logs/brain_refused.json", wf, "the ledger reaches main with the packs")


if __name__ == "__main__":
    unittest.main()


class ChainTests(unittest.TestCase):
    """The chain (23 Oct 2026, evening): every part points at the others on every platform —
    YouTube playlist + hashtag + first comment, Telegram caption, Threads video post + topic,
    Instagram first comment."""

    ROWS = [{"date": "2026-10-26", "title": "Rent receipt in Nigeria: a (part 1 of 5) #Shorts", "video_id": "AAA", "state": "published"},
            {"date": "2026-10-27", "title": "b (part 2 of 5) #Shorts", "video_id": "BBB", "state": "scheduled"},
            {"date": "2026-10-20", "title": "last week (part 2 of 5) #Shorts", "video_id": "OLD", "state": "published"},
            {"date": "2026-10-26", "title": "no number #Shorts", "video_id": "NON", "state": "published"}]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": str(Path(self.tmp.name) / "none"), "SHORTS_SEARCH_KICKER": "", "DOCOGA_FRESH": "off"})
        env.start()
        self.addCleanup(env.stop)

    def test_previous_parts_come_only_from_this_week_and_only_numbered_titles(self):
        wed = sw.series_for(date(2026, 10, 28))
        self.assertEqual(sw.previous_parts(wed, date(2026, 10, 28), self.ROWS), [(1, "AAA"), (2, "BBB")])
        self.assertEqual(sw.previous_parts(sw.series_for(MON), MON, self.ROWS), [], "Monday has nothing before it")
        lines = sw.chain_lines(wed, [(1, "AAA"), (2, "BBB")])
        self.assertEqual(lines, ["Part 3 of 5 · Rent receipt law.", "Part 1: https://youtube.com/shorts/AAA",
                                 "Part 2: https://youtube.com/shorts/BBB", "Part 4 tomorrow, 7:00pm."])
        self.assertNotIn("tomorrow", " ".join(sw.chain_lines(sw.series_for(FRI), [])))
        self.assertEqual(sw.hashtag(wed), "#RentReceiptLaw")
        self.assertEqual(sw.topic_tag(sw.series_for(MON2)), "Tenancy agreement")
        self.assertEqual(sw.line(wed), "Part 3 of 5 · Rent receipt law")
        pl = sw.playlist(wed)
        self.assertEqual(pl["title"], "Rent receipt law in Nigeria — the 5-part series (DocOga Shorts)")
        self.assertIn("docoga.com.ng", pl["description"])

    def test_the_youtube_lane_hands_the_chain_to_every_other_lane(self):
        import generate_short_video as words
        import youtube_short_daily as lane
        ledger = Path(self.tmp.name) / "published.json"
        ledger.write_text(json.dumps(self.ROWS), encoding="utf-8")
        topic = words.script_for_date(MON)
        description = lane.describe(topic)
        self.assertTrue(description.rstrip().endswith("#RentReceiptLaw #Shorts #TenantTips #NigeriaRent"),
                        "the series hashtag first — YouTube shows the first three above the title")
        out = lane.series_outputs(topic, MON, ledger=ledger)
        self.assertEqual(json.loads(out["series_json"])["slug"], "rent-receipt-law")
        self.assertEqual(out["series_line"], "Part 1 of 5 · Rent receipt law")
        self.assertEqual(out["series_topic"], "Rent receipt law")
        self.assertEqual(out["series_chain"], "Part 1 of 5 · Rent receipt law.\nPart 2 tomorrow, 7:00pm.")
        # a Wednesday brain Short: the earlier parts by link
        wed = dict(topic, series=sw.series_for(date(2026, 10, 28)))
        out = lane.series_outputs(wed, date(2026, 10, 28), ledger=ledger)
        self.assertIn("Part 1: https://youtube.com/shorts/AAA\nPart 2: https://youtube.com/shorts/BBB", out["series_chain"])
        plain = lane.series_outputs(words.script_for_date(TUE), TUE, ledger=ledger)
        self.assertEqual(plain, {"series_json": "", "series_line": "", "series_topic": "", "series_chain": ""})
        wf = (ROOT / ".github" / "workflows" / "youtube_scheduled.yml").read_text(encoding="utf-8")
        for needle in ('--series "$SERIES_JSON"', '--series-chain "$SERIES_CHAIN"', '--series "$SERIES_LINE" --series-topic "$SERIES_TOPIC"',
                       "steps.short.outputs.series_json", "steps.short.outputs.series_chain", "steps.short.outputs.series_line",
                       "--first-comment --description-file /tmp/short_description.txt"):
            self.assertIn(needle, wf, needle)
        th = (ROOT / ".github" / "workflows" / "threads_autopost.yml").read_text(encoding="utf-8")
        self.assertIn('--video-series "$THREADS_VIDEO_SERIES"', th)
        self.assertIn('--video-topic "$THREADS_VIDEO_TOPIC"', th)
        self.assertIn("THREADS_VIDEO_(URL|TITLE|ID|SERIES|TOPIC)", th)

    def test_telegram_caption_threads_video_text_and_instagram_comment_carry_the_part(self):
        import reel_caption
        import telegram_video
        import threads_publish
        chain = "Part 3 of 5 · Rent receipt law.\nPart 1: https://youtube.com/shorts/AAA\nPart 4 tomorrow, 7:00pm."
        cap = telegram_video.caption_for("Six lines (part 3 of 5) #Shorts", "https://youtu.be/CCC", series_chain=chain)
        self.assertIn(chain, cap)
        self.assertLess(cap.index(chain), cap.index("Free Nigerian tenancy documents"))
        self.assertNotIn("Part", telegram_video.caption_for("Plain #Shorts", "https://youtu.be/x"))
        framed = threads_publish.series_video_text("The day's words.", "Part 3 of 5 · Rent receipt law")
        self.assertEqual(framed, "The day's words.\n\n▶ Part 3 of 5 · Rent receipt law")
        self.assertEqual(threads_publish.series_video_text("x" * 495, "Part 3 of 5 · Rent receipt law"), "x" * 495, "never over 500")
        self.assertEqual(threads_publish.series_video_text("plain", ""), "plain")
        d = "hook\n\nPart 3 of 5 in this week's series on the rent receipt law. Tomorrow: X.\n\nIn this Short:\n• a"
        first = reel_caption.first_comment(date(2026, 10, 28), None, d)
        self.assertTrue(first.startswith("Part 3 of 5 · Rent receipt law. The earlier parts are the Reels before this one on our profile. Part 4 lands tomorrow at 7:00pm."), first)
        d1 = "hook\n\nPart 1 of 5 in this week's series on the rent receipt law. Tomorrow: X.\n\n"
        self.assertNotIn("earlier parts", reel_caption.first_comment(MON, None, d1))
        d5 = "hook\n\nPart 5 of 5 in this week's series on the rent receipt law. All five parts are on the channel.\n\n"
        self.assertNotIn("tomorrow", reel_caption.first_comment(FRI, None, d5))
        self.assertNotIn("Part", reel_caption.first_comment(MON, None, "hook\n\nIn this Short:\n• a"))

    def test_shorts_handoff_records_the_frame_for_the_threads_evening_post(self):
        import shorts_handoff
        ledger = Path(self.tmp.name) / "media.json"
        ledger.write_text(json.dumps({"latest": {}, "history": []}), encoding="utf-8")
        from datetime import datetime as dt, timezone as tz
        now = dt(2026, 10, 27, 17, 5, tzinfo=tz.utc)
        with patch.object(shorts_handoff.media_host, "put", lambda *a, **k: {"url": "https://m/x.mp4", "name": "x.mp4", "bytes": 10, "ttl": 108000, "live": True}):
            shorts_handoff.host("v.mp4", "BBB", "b (part 2 of 5) #Shorts", date="2026-10-27", ledger=ledger, now=now, log=lambda *a: None,
                                series="Part 2 of 5 · Rent receipt law", series_topic="Rent receipt law")
        out = io.StringIO()
        with patch.object(shorts_handoff, "datetime") as fake:
            fake.now.return_value = now.replace(hour=19)
            fake.fromisoformat = dt.fromisoformat
            with redirect_stdout(out):
                shorts_handoff.main(["today", "--date", "2026-10-27", "--ledger", str(ledger)])
        self.assertIn("THREADS_VIDEO_SERIES=Part 2 of 5 · Rent receipt law\n", out.getvalue())
        self.assertIn("THREADS_VIDEO_TOPIC=Rent receipt law\n", out.getvalue())

    def test_yt_boost_adds_the_series_playlist_once_and_keeps_the_shorts_one(self):
        import yt_boost
        from test_yt_boost import Google, run
        ledger = Path(self.tmp.name) / "boosts.json"
        with patch.object(yt_boost, "LEDGER", ledger):
            g = Google()
            series = json.dumps({"slug": "rent-receipt-law", "name": "Rent receipt law", "part": 1, "total": 5, "week_start": "2026-10-26"})
            code, _ = run(["plan", "--video-id", "AAA", "--kind", "short", "--title", "Pay without a receipt", "--series", series], g, ledger)
            self.assertEqual(code, 0)
            code, out = run(["run", "--no-import"], g, ledger)
            self.assertEqual(code, 0)
            titles = {t: pid for t, pid in g.playlists.items()}
            self.assertIn(yt_boost.PLAYLISTS["short"]["title"], titles)
            self.assertIn("Rent receipt law in Nigeria — the 5-part series (DocOga Shorts)", titles)
            self.assertEqual(g.items[titles["Rent receipt law in Nigeria — the 5-part series (DocOga Shorts)"]], {"AAA"})
            self.assertIn("series playlist", out)
            rows = yt_boost.load(ledger)
            self.assertTrue(rows[0]["series_item_id"] and rows[0]["playlist_item_id"] and rows[0]["comment_id"])
            self.assertEqual(yt_boost.pending(rows), [])
            # part 2 joins the same playlist; nothing is created twice; a plain Short wants none
            run(["plan", "--video-id", "BBB", "--kind", "short", "--title", "Part two", "--series", series.replace('"part": 1', '"part": 2')], g, ledger)
            run(["plan", "--video-id", "PLAIN", "--kind", "short", "--title", "Plain day"], g, ledger)
            run(["run", "--no-import"], g, ledger)
            self.assertEqual(sum(1 for r, _, _ in g.calls if r == ("POST", "playlists")), 2)
            self.assertEqual(g.items[titles["Rent receipt law in Nigeria — the 5-part series (DocOga Shorts)"]], {"AAA", "BBB"})
            rows = {r["video_id"]: r for r in yt_boost.load(ledger)}
            self.assertNotIn("series", rows["PLAIN"])
            self.assertFalse(yt_boost.wants_series(rows["PLAIN"]))
            code, out = run(["plan", "--video-id", "BAD", "--series", "{not json"], g, ledger)
            self.assertEqual(code, 0)
