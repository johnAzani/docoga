"""Nothing twice (24 Oct 2026, owner: "make sure you are not repeating or recycling contents").

tools/fresh.py is the memory; this file pins what every lane does with it:
  * the Shorts rotation walks past a script YouTube carried inside FRESH_DAYS, and when all six
    are spent the lane asks the brain once more and then SKIPS the day (exit 7) — never a repeat;
  * the Threads morning never replays a hook the profile carried inside FRESH_DAYS;
  * the Telegram fallback shares the Facebook replay guard, seeded per channel, ledger-aware;
  * the Threads and Instagram publishers refuse a repeat the live list missed;
  * the brain refuses a statistic it cannot source and heals a six-line reflow instead of refusing it.
"""
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "tools", ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import fresh  # noqa: E402

MON = date(2026, 10, 26)


def _ledger(path, rows):
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


class KeyTests(unittest.TestCase):
    def test_the_key_is_the_opening_words_without_links_tags_or_prefixes(self):
        self.assertEqual(fresh.key("Pay the wrong agent. Lose the flat."), "pay the wrong agent lose the")
        self.assertEqual(fresh.key("Reel · Pay the wrong agent. Lose the flat."), fresh.key("Pay the wrong agent. Lose the flat."))
        self.assertEqual(fresh.key("#RentReceiptLaw #Shorts\nYou pay rent in cash, the landlord says thank you"),
                         "you pay rent in cash the")
        self.assertEqual(fresh.key("See https://docoga.com.ng/x now — Most people sign a tenancy agreement"),
                         "see now most people sign a")
        self.assertEqual(fresh.key(""), "")

    def test_a_truncated_ledger_title_drops_its_cut_word(self):
        title = "Most people sign a tenancy agreement in the agent's office i"
        self.assertEqual(len(title), 60)
        self.assertEqual(fresh._untruncated(title), "Most people sign a tenancy agreement in the agent's office")
        self.assertEqual(fresh._untruncated("Short title."), "Short title.")


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        env = patch.dict(os.environ, {"DOCOGA_FRESH": "on"})
        env.start()
        self.addCleanup(env.stop)

    def test_youtube_history_keys_the_script_title_and_keeps_the_latest_date(self):
        path = _ledger(self.dir / "yt.json", [
            {"date": "2026-10-22", "topic": "Skip the photos. Pay for old damage.", "title": "Moving in: skip the photos #Shorts"},
            {"date": "2026-10-16", "topic": "Skip the photos. Pay for old damage.", "title": "Skip the photos. #Shorts"},
            {"date": "2026-10-21", "topic": "Pay the wrong agent. Lose the flat."},
            {"topic": "no date — ignored"},
        ])
        hist = fresh.history("youtube", path)
        self.assertEqual(hist[fresh.key("Skip the photos. Pay for old damage.")], date(2026, 10, 22))
        self.assertEqual(hist[fresh.key("Pay the wrong agent. Lose the flat.")], date(2026, 10, 21))
        self.assertEqual(len(hist), 2)

    def test_threads_history_reads_the_truncated_title_and_prefers_the_note(self):
        path = _ledger(self.dir / "th.json", [
            {"date": "2026-10-18", "title": "Most people sign a tenancy agreement in the agent's office i"},
            {"date": "2026-10-19", "title": "telegram promo 8fba6fdad7", "note": "Caution fee is a deposit, not a gift. It is refundable"},
            {"date": "2026-10-20", "title": "telegram promo 11aa22bb33"},
        ])
        hist = fresh.history("threads", path)
        self.assertEqual(fresh.last_seen("Most people sign a tenancy agreement in the agent's office in under a minute.", hist), date(2026, 10, 18))
        self.assertEqual(fresh.last_seen("Caution fee is a deposit, not a gift.", hist), date(2026, 10, 19))
        self.assertIsNone(fresh.last_seen("telegram promo 11aa22bb33", hist), "a hash is not words")

    def test_the_switch_empties_the_memory(self):
        path = _ledger(self.dir / "yt.json", [{"date": "2026-10-22", "topic": "Skip the photos. Pay for old damage."}])
        with patch.dict(os.environ, {"DOCOGA_FRESH": "off"}):
            self.assertEqual(fresh.history("youtube", path), {})

    def test_fresh_means_not_inside_the_window_and_a_same_day_record_is_a_rerun(self):
        hist = {fresh.key("A line."): date(2026, 10, 20)}
        self.assertFalse(fresh.is_fresh("A line.", hist, date(2026, 10, 26)))
        self.assertTrue(fresh.is_fresh("A line.", hist, date(2026, 10, 20) + timedelta(days=fresh.FRESH_DAYS)))
        self.assertTrue(fresh.is_fresh("A line.", hist, date(2026, 10, 20)), "the day's own record")
        self.assertTrue(fresh.is_fresh("Never said.", hist, date(2026, 10, 26)))
        self.assertEqual(fresh.FRESH_DAYS, 28)


class RotationPickTests(unittest.TestCase):
    SCRIPTS = [{"title": "A one."}, {"title": "B two."}, {"title": "C three."}]

    def test_an_empty_memory_is_the_old_ordinal_walk(self):
        for n in range(6):
            day = MON + timedelta(days=n)
            pick = fresh.pick_rotation(day, self.SCRIPTS, {})
            self.assertIs(pick["script"], self.SCRIPTS[(day.toordinal() - 1) % 3])
            self.assertFalse(pick["stale"])

    def test_a_stale_script_is_walked_past_to_the_next_fresh_one(self):
        i0 = (MON.toordinal() - 1) % 3
        hist = {fresh.key(self.SCRIPTS[i0]["title"]): MON - timedelta(days=5)}
        pick = fresh.pick_rotation(MON, self.SCRIPTS, hist)
        self.assertIs(pick["script"], self.SCRIPTS[(i0 + 1) % 3])
        self.assertFalse(pick["stale"])

    def test_when_everything_is_stale_the_oldest_comes_back_flagged(self):
        hist = {fresh.key("A one."): MON - timedelta(days=3), fresh.key("B two."): MON - timedelta(days=9),
                fresh.key("C three."): MON - timedelta(days=6)}
        pick = fresh.pick_rotation(MON, self.SCRIPTS, hist)
        self.assertTrue(pick["stale"])
        self.assertEqual(pick["script"]["title"], "B two.")
        self.assertEqual(pick["last_seen"], MON - timedelta(days=9))

    def test_name_chooses_the_words_that_identify_a_script(self):
        scripts = [{"title": "T1", "hook": "hello world one two three four"}, {"title": "T2", "hook": "other words here now please ok"}]
        i0 = (MON.toordinal() - 1) % 2
        hist = {fresh.key(scripts[i0]["hook"]): MON - timedelta(days=1)}
        pick = fresh.pick_rotation(MON, scripts, hist, name=lambda s: s["hook"])
        self.assertIs(pick["script"], scripts[1 - i0])


class ShortsLaneTests(unittest.TestCase):
    """scripts/generate_short_video.rotation_for and scripts/youtube_short_daily.fresh_or_nothing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / "drafts").mkdir()
        env = patch.dict(os.environ, {"DOCOGA_FRESH": "on", "DOCOGA_BRAIN": "on", "SHORTS_SERIES_WEEK": "off",
                                      "DOCOGA_BRAIN_DRAFTS": str(self.dir / "drafts"), "GEMINI_API_KEY": "test"})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("GITHUB_OUTPUT", None)

    def _yt(self, rows):
        path = _ledger(self.dir / "yt.json", rows)
        p = patch.dict(fresh.LEDGERS, {"youtube": path})
        p.start()
        self.addCleanup(p.stop)

    def test_the_rotation_walks_past_what_the_channel_carried_this_month(self):
        import generate_short_video as words
        ordinal = words.VIDEO_SCRIPTS[(MON.toordinal() - 1) % len(words.VIDEO_SCRIPTS)]
        nxt = words.VIDEO_SCRIPTS[MON.toordinal() % len(words.VIDEO_SCRIPTS)]
        self._yt([{"date": (MON - timedelta(days=6)).isoformat(), "topic": ordinal["title"]}])
        picked = words.script_for_date(MON)
        self.assertEqual(picked["title"], nxt["title"])
        self.assertNotIn("stale", picked)
        self._yt([])
        self.assertIs(words.script_for_date(MON), ordinal, "an empty memory is the rotation exactly as before")

    def test_six_stale_scripts_come_back_flagged_never_silently(self):
        import generate_short_video as words
        rows = [{"date": (MON - timedelta(days=2 + i)).isoformat(), "topic": s["title"]} for i, s in enumerate(words.VIDEO_SCRIPTS)]
        self._yt(rows)
        picked = words.script_for_date(MON)
        self.assertTrue(picked.get("stale"))
        self.assertEqual(picked["last_published"], (MON - timedelta(days=2 + len(words.VIDEO_SCRIPTS) - 1)).isoformat())
        self.assertEqual(picked["title"], words.VIDEO_SCRIPTS[-1]["title"], "the least recently published")

    def test_a_stale_day_asks_the_brain_and_takes_its_short(self):
        import youtube_short_daily as lane
        stale = dict(lane.shorts_reel.topic_for(MON), stale=True, last_published="2026-10-20")
        brain_script = {"title": "Six lines every receipt needs.", "brain": MON.isoformat(), "slides": []}
        calls = []

        def think(day):
            calls.append(day)
            return {"approved": [{"theme": "x"}], "refused": {}, "quota": None}
        with patch.object(lane.shorts_reel, "topic_for", return_value=brain_script), redirect_stdout(io.StringIO()) as out:
            got = lane.fresh_or_nothing(stale, MON, think=think)
        self.assertEqual(calls, [MON])
        self.assertEqual(got["title"], "Six lines every receipt needs.")
        self.assertIn("The brain wrote today's Short at the slot", out.getvalue())

    def test_a_stale_day_the_brain_refuses_is_skipped_with_the_reason_in_the_outputs(self):
        import youtube_short_daily as lane
        stale = dict(lane.shorts_reel.topic_for(MON), stale=True, last_published="2026-10-20")

        def think(day):
            return {"approved": [], "refused": {day.isoformat(): ["a body line is 144 characters; max 110"]}, "quota": None}
        with redirect_stdout(io.StringIO()) as out:
            got = lane.fresh_or_nothing(stale, MON, think=think)
        text = out.getvalue()
        self.assertIsNone(got)
        self.assertIn("paused=yes", text)
        self.assertIn("stale=yes", text)
        self.assertIn("stale_reason=No new Short today: brain refused: a body line is 144 characters", text)
        self.assertIn("::error title=No fresh Short — the day is skipped, not repeated::", text)
        self.assertIn("last published 2026-10-20", text)
        self.assertEqual(lane.STALE_EXIT, 7)

    def test_the_brain_switch_and_a_thinking_failure_still_skip_cleanly(self):
        import youtube_short_daily as lane
        stale = dict(lane.shorts_reel.topic_for(MON), stale=True)
        with patch.dict(os.environ, {"DOCOGA_BRAIN": "off"}), redirect_stdout(io.StringIO()) as out:
            self.assertIsNone(lane.fresh_or_nothing(stale, MON, think=lambda d: self.fail("must not think")))
        self.assertIn("brain switched off", out.getvalue())

        def boom(day):
            raise RuntimeError("no network")
        with redirect_stdout(io.StringIO()) as out:
            self.assertIsNone(lane.fresh_or_nothing(stale, MON, think=boom))
        self.assertIn("brain failed: no network", out.getvalue())

    def test_main_returns_seven_on_a_stale_day(self):
        import youtube_short_daily as lane
        stale = dict(lane.shorts_reel.topic_for(MON), stale=True)
        with patch.object(lane.shorts_reel, "topic_for", return_value=stale), \
                patch.object(lane, "fresh_or_nothing", return_value=None) as fon, \
                patch.dict(os.environ, {"RUN_FOR_DATE": MON.isoformat()}), redirect_stdout(io.StringIO()):
            self.assertEqual(lane.main(), 7)
        fon.assert_called_once()

    def test_the_workflow_reads_seven_as_a_skip_tells_the_owner_and_commits_the_brains_pack(self):
        text = (ROOT / ".github" / "workflows" / "youtube_scheduled.yml").read_text(encoding="utf-8")
        self.assertIn('if [ "$code" -eq 7 ]; then', text)
        self.assertIn("Tell the owner the day was skipped, not repeated", text)
        self.assertIn("if: steps.short.outputs.stale == 'yes'", text)
        self.assertIn("tools/owner_dm.py send --text", text)
        self.assertIn("STALE_REASON: ${{ steps.short.outputs.stale_reason }}", text)
        self.assertIn('if [ "$STALE" = "yes" ]; then', text)
        commit = text[text.index("Commit the publish ledger"):]
        self.assertIn("brain/drafts logs/brain_said.json logs/brain_refused.json; do", commit)


class ThreadsMorningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / "drafts").mkdir()
        env = patch.dict(os.environ, {"DOCOGA_FRESH": "on", "DOCOGA_BRAIN": "on", "SHORTS_SERIES_WEEK": "off",
                                      "DOCOGA_BRAIN_DRAFTS": str(self.dir / "drafts")})
        env.start()
        self.addCleanup(env.stop)
        yt = _ledger(self.dir / "yt.json", [])
        self.th = _ledger(self.dir / "th.json", [])
        p = patch.dict(fresh.LEDGERS, {"youtube": yt, "threads": self.th})
        p.start()
        self.addCleanup(p.stop)

    def _pack(self, day, short=None):
        pack = {"version": 1, "status": "approved", "date": day.isoformat(), "theme": "t",
                "post": {"headline": "Headline here.", "lines": ["First line.", "Second line, the brain's own words."], "cta": "c", "hashtags": ["#DocOga"]},
                "threads": {"text": "t", "hashtags": []}, "visual": {}, "tool": "rent-receipt", "short": short}
        (self.dir / "drafts" / ("%s.json" % day.isoformat())).write_text(json.dumps(pack), encoding="utf-8")
        return pack

    def test_a_weekend_pack_without_a_short_lends_its_second_line(self):
        import generate_threads_content as th
        sat = date(2026, 10, 24)
        pack = self._pack(sat)
        hook, source = th.morning_hook(sat, pack)
        self.assertEqual(hook, "Second line, the brain's own words.")
        self.assertIn("second line", source)

    def test_a_rotation_hook_the_profile_carried_this_month_is_passed_over(self):
        import generate_threads_content as th
        import generate_short_video as words
        sat = date(2026, 10, 24)
        todays = words.script_for_date(sat)
        said = todays["slides"][0]["say"]
        _ledger(self.th, [{"date": (sat - timedelta(days=6)).isoformat(), "title": said[:60], "topic": "threads"}])
        hook, source = th.morning_hook(sat, None)
        self.assertNotEqual(hook, " ".join(said.split()))
        self.assertTrue(hook)
        self.assertIn("was on this profile recently", source)

    def test_when_every_hook_is_spent_the_question_stands_alone(self):
        import generate_threads_content as th
        import generate_short_video as words
        sat = date(2026, 10, 24)
        rows = [{"date": (sat - timedelta(days=3)).isoformat(), "title": s["slides"][0]["say"][:60]} for s in words.VIDEO_SCRIPTS]
        _ledger(self.th, rows)
        hook, source = th.morning_hook(sat, None)
        self.assertEqual(hook, "")
        self.assertIn("question only", source)
        with redirect_stdout(io.StringIO()):
            content = th.generate(sat, write=False, slot="morning")
        self.assertTrue(content["text"].strip().endswith("?"))
        self.assertNotIn("\n\n\n", content["text"])

    def test_a_brain_short_day_still_teases_the_short(self):
        import generate_threads_content as th
        tips = [{"text": "Tip %d" % i, "sub": "sub", "say": "say " * 20} for i in range(1, 5)]
        pack = self._pack(MON, short={"title": "Six lines every receipt needs.", "hook_sub": "sub", "hook_say": "The spoken hook of the brain's Short today.",
                                      "hook_text": "SIX LINES", "tips": tips})
        hook, source = th.morning_hook(MON, pack)
        self.assertEqual(hook, "The spoken hook of the brain's Short today.")
        self.assertIn("brain's Short", source)


class TemplateRotationTests(unittest.TestCase):
    def test_telegram_and_facebook_walk_from_different_seeds_and_telegram_uses_the_guard(self):
        import generate_facebook_content as fb
        import generate_telegram_content as tg
        days = [date(2026, 10, 19) + timedelta(days=n) for n in range(60)]
        same = sum(fb.raw_pick(d)[1] == fb.raw_pick(d, "telegram")[1] for d in days)
        self.assertLess(same, len(days) // 2, "two channels, two walks")
        for d in days:
            self.assertNotEqual(fb.pick(d, "telegram", hist={})[1], fb.pick(d - timedelta(days=1), "telegram", hist={})[1])
        src = (ROOT / "scripts" / "generate_telegram_content.py").read_text(encoding="utf-8")
        self.assertIn('fb.pick(today.date(), channel="telegram")', src)
        self.assertNotIn("random.choice(TEMPLATES[post_type])", src)
        self.assertTrue(all(isinstance(v, list) and v for v in tg.TEMPLATES.values()))

    def test_the_channels_own_ledger_passes_a_template_over(self):
        import generate_facebook_content as fb
        from telegram_mdv2 import to_plain
        day = date(2026, 10, 27)
        post_type, chosen = fb.pick(day, "telegram", hist={})
        hist = {fresh.key(to_plain(chosen)): day - timedelta(days=4)}
        again = fb.pick(day, "telegram", hist=hist)
        self.assertEqual(again[0], post_type)
        self.assertNotEqual(again[1], chosen)
        # the default reads the ledger for the channel; an unknown channel has none and still works
        self.assertEqual(len(fb.pick(day, "nowhere")), 2)

    def test_the_telegram_ledger_now_keeps_the_opening_words(self):
        import post_telegram
        self.assertEqual(post_telegram._opening("*Hello* there\\. Line two"), "Hello there. Line two")
        self.assertEqual(len(post_telegram._opening("x" * 300)), 120)
        src = (ROOT / "scripts" / "post_telegram.py").read_text(encoding="utf-8")
        self.assertIn("note=_opening(message),", src)


class PublisherGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"DOCOGA_FRESH": "on"})
        env.start()
        self.addCleanup(env.stop)

    def test_threads_and_instagram_refuse_the_opening_words_the_ledger_remembers(self):
        import threads_publish
        import ig_publish
        day = date(2026, 10, 24)
        th = _ledger(Path(self.tmp.name) / "th.json", [{"date": "2026-10-18", "title": "Most people sign a tenancy agreement in the agent's office i"}])
        ig = _ledger(Path(self.tmp.name) / "ig.json", [{"date": "2026-10-19", "title": "Caution fee is a deposit, not a gift.\n\nIt is refundable when"}])
        with patch.dict(fresh.LEDGERS, {"threads": th, "instagram": ig}):
            self.assertEqual(threads_publish.find_recent_repeat("Most people sign a tenancy agreement in the agent's office in under a minute.", day), date(2026, 10, 18))
            self.assertIsNone(threads_publish.find_recent_repeat("Something new under the sun today.", day))
            self.assertIsNone(threads_publish.find_recent_repeat("Most people sign a tenancy agreement in the agent's office.", date(2026, 10, 18)), "the day's own record is a re-run")
            self.assertIsNone(threads_publish.find_recent_repeat("Most people sign a tenancy agreement in the agent's office.", date(2026, 11, 20)), "four weeks on it may return")
            self.assertEqual(ig_publish.find_recent_repeat("Caution fee is a deposit, not a gift. It is refundable when you leave.", day), date(2026, 10, 19))
        for name in ("threads_publish.py", "ig_publish.py"):
            src = (ROOT / "tools" / name).read_text(encoding="utf-8")
            self.assertIn("refused-a-repeat", src)
            self.assertIn("find_recent_repeat(", src)


class BrainGateTests(unittest.TestCase):
    def test_an_unsourced_statistic_is_refused_and_a_shelf_number_is_not(self):
        import brain
        pack = {"post": {"headline": "Over 70% of Nigerian tenants pay rent without paper.", "lines": ["This week's reports show many still pay cash."]},
                "threads": {"text": "1 in 3 tenants never get a receipt. Do you?"}, "short": {"hook_say": "About 14.9 million people rent in Lagos."}}
        problems = brain.statistic_problems(pack, "")
        self.assertEqual(len(problems), 3, problems)
        self.assertTrue(any("'70%'" in p for p in problems))
        self.assertTrue(any("'1 in 3'" in p for p in problems))
        self.assertTrue(any("'14.9 million'" in p for p in problems))
        ok = {"post": {"headline": "Six months' notice for a yearly tenant.", "lines": ["The fine is ₦100,000 — s.5(3)."]}, "threads": {"text": "Did you get six months?"}}
        self.assertEqual(brain.statistic_problems(ok, "six months' notice; fine of ₦100,000"), [])
        self.assertEqual(brain.statistic_problems({"post": {"headline": "Up to 10% of rent", "lines": []}}, "a caution fee of up to 10% of the annual rent"), [])
        for phrase in ("reports show", "studies show", "experts say", "it is estimated"):
            self.assertIn(phrase, brain.BANNED)
        self.assertIn("No statistics: no percentage", (ROOT / "tools" / "brain.py").read_text(encoding="utf-8"), "the prompt says it too")

    def test_the_statistic_gate_sits_inside_lint(self):
        src = (ROOT / "tools" / "brain.py").read_text(encoding="utf-8")
        lint = src[src.index("def lint("):src.index("def _spoken_corpus(")]
        self.assertIn("p.extend(statistic_problems(pack, fact_texts))", lint)

    def test_a_six_line_reflow_is_healed_by_joining_short_neighbours(self):
        import brain
        long_line = "No more paying cash without paper. Insist on a dated receipt that shows the amount, the period it covers and the landlord's name, every single time you pay."
        pack = {"post": {"headline": "h", "lines": ["Short one.", "Short two.", long_line, "Short four.", "Short five."]}}
        self.assertGreater(len(long_line), brain.LINE_MAX)
        healed = brain.tidy(pack)["post"]["lines"]
        self.assertLessEqual(len(healed), 5)
        self.assertGreaterEqual(len(healed), 2)
        self.assertTrue(all(len(ln) <= brain.LINE_MAX for ln in healed))
        self.assertEqual(" ".join(healed).split(), " ".join(["Short one.", "Short two.", long_line, "Short four.", "Short five."]).split(),
                         "layout only — never a word")

    def test_the_withdrawn_sunday_pack_is_no_longer_a_draft(self):
        import brain_drafts
        pack = json.loads((ROOT / "brain" / "drafts" / "2026-10-25.json").read_text(encoding="utf-8"))
        self.assertEqual(pack["status"], "withdrawn")
        self.assertIn("70%", pack["post"]["headline"], "the unsourced statistic that withdrew it")
        env = dict(os.environ, DOCOGA_BRAIN="on")
        env.pop("DOCOGA_BRAIN_DRAFTS", None)
        with patch.dict(os.environ, env, clear=True):
            self.assertIsNone(brain_drafts.draft_for(date(2026, 10, 25)), "the brain rewrites the day")


class SearchPhraseTests(unittest.TestCase):
    def test_screen_and_caption_say_the_same_search_phrase(self):
        import reel_caption as rc
        import shorts_reel
        self.assertEqual(rc.fit_phrase("Tenancy agreement sample Nigeria"), "Tenancy agreement Nigeria")
        self.assertEqual(rc.fit_phrase("Rent receipt format Nigeria (Lagos)"), "Rent receipt Nigeria (Lagos)")
        self.assertEqual(rc.fit_phrase("Notice to quit Nigeria (Lagos)"), "Notice to quit Nigeria (Lagos)")
        self.assertEqual(rc.fit_phrase("Shop tenancy agreement Nigeria"), "")
        day = date(2026, 10, 24)
        pack = {"tool": "tenancy-agreement", "state": None, "post": {"headline": "x", "lines": []}, "visual": {}}
        phrase = rc.tiktok_keyword(day, pack)
        self.assertEqual(phrase, "Tenancy agreement Nigeria")
        with patch.dict(os.environ, {"SHORTS_SEARCH_KICKER": ""}), patch.object(rc, "pack_for", return_value=pack):
            kicker = shorts_reel.search_kicker(day=day)
        self.assertTrue(kicker.startswith(phrase.upper()), kicker)
        self.assertEqual(rc.PHRASE_MAX, 26)


if __name__ == "__main__":
    unittest.main()
