"""29 Oct 2026 — owner: "I am seeing the same image or video clips behind the card of all the
videos." The chooser took position 0 / the single top score for a query every day, and the
`used` set lived for one render. The footage ledger + the day's draw end that."""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import footage_ledger as fl  # noqa: E402
import shot_match  # noqa: E402
import stock_media  # noqa: E402

CANDS = [{"id": "pixabay:%d" % i, "url": "https://x/%d.mp4" % i, "kind": "video", "title": "paper receipt hand",
          "tags_text": "paper receipt hand", "width": 1080, "height": 1920, "duration": 12} for i in range(6)]


class Scratch(unittest.TestCase):
    def setUp(self):
        self.path = Path("/tmp/docoga_footage_test_%d.json" % os.getpid())
        if self.path.exists():
            self.path.unlink()
        os.environ["FOOTAGE_LEDGER"] = str(self.path)
        fl.load(force=True)

    def tearDown(self):
        os.environ.pop("FOOTAGE_LEDGER", None)
        if self.path.exists():
            self.path.unlink()
        fl.load(force=True)


class ChoiceTests(Scratch):
    def test_the_same_query_on_different_days_does_not_land_on_the_same_clip(self):
        days = ["2026-11-%02d" % d for d in range(1, 15)]
        picks = [stock_media.choose(CANDS, "paper receipt", 4.0, day=d)["id"] for d in days]
        self.assertGreater(len(set(picks)), 1, picks)
        self.assertNotEqual(picks[0], picks[1])

    def test_a_clip_shown_this_month_goes_to_the_back_of_the_queue(self):
        first = stock_media.choose(CANDS, "paper receipt", 4.0, day="2026-11-01")
        fl.record(first["id"], "paper receipt", "pixabay", day="2026-11-01")
        for d in range(2, 20):
            again = stock_media.choose(CANDS, "paper receipt", 4.0, day="2026-11-%02d" % d)
            self.assertNotEqual(again["id"], first["id"], "shown on the 1st, shown again on the %dth" % d)
        # ...and, with every candidate recently shown, the pick is still a pick (never None)
        for c in CANDS:
            fl.record(c["id"], "paper receipt", "pixabay", day="2026-11-10")
        self.assertIsNotNone(stock_media.choose(CANDS, "paper receipt", 4.0, day="2026-11-11"))

    def test_six_days_of_shorts_use_at_least_four_different_clips(self):
        seen = set()
        for d in range(1, 7):
            day = "2026-11-%02d" % d
            c = stock_media.choose(CANDS, "paper receipt", 4.0, day=day)
            fl.record(c["id"], "paper receipt", "pixabay", day=day)
            seen.add(c["id"])
        self.assertGreaterEqual(len(seen), 4, seen)

    def test_relevance_still_beats_rotation(self):
        off = dict(CANDS[0], id="pixabay:off", title="gavel court", tags_text="gavel court")
        for d in range(1, 8):
            c = stock_media.choose([off] + CANDS[:2], "paper receipt", 4.0, day="2026-11-%02d" % d)
            self.assertNotEqual(c["id"], "pixabay:off")

    def test_the_photo_door_no_longer_takes_position_zero(self):
        kept = [{"id": i, "url": "u%d" % i, "title": "lagos street", "tags_text": "lagos street"} for i in range(5)]

        class FakeBV:
            @staticmethod
            def enabled():
                return True

            @staticmethod
            def search(q, http=None):
                return kept, "fake"

        sys.modules["brain_visual"], saved = FakeBV, sys.modules.get("brain_visual")
        try:
            picks = set()
            for d in range(1, 10):
                os.environ["RUN_DATE"] = "2026-11-%02d" % d
                cand, _ = shot_match.pick("lagos street nigeria", sleeper=lambda: None)
                picks.add(cand["id"])
        finally:
            os.environ.pop("RUN_DATE", None)
            if saved is not None:
                sys.modules["brain_visual"] = saved
            else:
                sys.modules.pop("brain_visual", None)
        self.assertGreater(len(picks), 1)


class LedgerTests(Scratch):
    def test_record_writes_through_prunes_and_survives_a_bad_file(self):
        fl.record("pixabay:1", "paper receipt", "pixabay", day="2026-11-01")
        fl.record("pixabay:2", "court", "pixabay", day="2026-01-01")     # ancient
        os.environ["RUN_DATE"] = "2026-11-02"
        try:
            fl.save()
            data = json.loads(self.path.read_text())
            self.assertIn("pixabay:1", data["used"])
            self.assertNotIn("pixabay:2", data["used"], "older than MEMORY_DAYS is forgotten")
            self.assertEqual(fl.penalty("pixabay:1"), fl.RECENT_PENALTY)
            self.path.write_text("{not json")
            fl.load(force=True)
            self.assertEqual(fl.status()["entries"], 0)
        finally:
            os.environ.pop("RUN_DATE", None)

    def test_under_unittest_without_an_override_the_committed_ledger_is_never_touched(self):
        os.environ.pop("FOOTAGE_LEDGER", None)
        self.assertNotEqual(fl.path(), fl.LEDGER)
        self.assertTrue(str(fl.path()).startswith("/tmp/"))

    def test_the_rendering_lanes_commit_the_ledger(self):
        for wf in ("youtube_scheduled", "deepdive", "instagram_autopost", "threads_autopost",
                   "facebook_autopost", "telegram_autopost"):
            text = (ROOT / ".github" / "workflows" / ("%s.yml" % wf)).read_text(encoding="utf-8")
            self.assertIn("logs/footage_used.json", text, wf)
        self.assertTrue((ROOT / "logs" / "footage_used.json").is_file())


if __name__ == "__main__":
    unittest.main()
