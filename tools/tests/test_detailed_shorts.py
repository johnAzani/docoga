#!/usr/bin/env python3
"""A Short is detailed, not points — like the long form (owner, 17 Oct 2026).

Each slide carries `say`, the explanation the locked narrator reads; the scene stretches
to the read and is captioned sentence by sentence (MotionStudio kind 'caption'), exactly
as a Deep-Dive is. The rotation's six scripts carry says, the brain must write them, and
the five says together stay under the word budget that keeps a Facebook Reel under 90 s.
"""
import datetime
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import motionstudio as ms  # noqa: E402
    import shorts_reel  # noqa: E402
    import shorts_sound  # noqa: E402
    import generate_short_video as words  # noqa: E402
    import brain  # noqa: E402
    import brain_drafts  # noqa: E402
    IMPORT_OK = True
except Exception:  # PIL/numpy missing
    IMPORT_OK = False


@unittest.skipUnless(IMPORT_OK, "video modules not importable (PIL/numpy)")
class Words(unittest.TestCase):
    def test_every_rotation_slide_has_a_detailed_say_inside_the_budget(self):
        for script in words.VIDEO_SCRIPTS:
            says = [sl.get("say", "") for sl in script["slides"][:-1]]
            self.assertEqual(len(says), 5, script["title"])
            for say in says:
                n = len(say.split())
                self.assertTrue(brain.SAY_WORDS[0] <= n <= brain.SAY_WORDS[1], (script["title"], n, say))
                self.assertNotIn("http", say)
                self.assertTrue(say.rstrip().endswith((".", "!", "?")), say)
            total = sum(len(s.split()) for s in says)
            self.assertLessEqual(total, brain.SAY_TOTAL_MAX, (script["title"], total))
            self.assertEqual(brain.short_problems({"title": script["title"], "hook_sub": "x", "hook_say": says[0],
                                                   "tips": [{"text": "A b c", "sub": "", "say": s} for s in says[1:]]}), [])

    def test_spoken_and_sentences(self):
        self.assertEqual(shorts_sound.spoken("  Keep it on docoga.com.ng · always "),
                         "Keep it on Doc Oga dot com dot N G, always.")
        self.assertEqual(shorts_sound.sentences("One here. Two there! Three? Yes."), ["One here.", "Two there!", "Three?", "Yes."])
        self.assertEqual(shorts_sound.sentences("Rent is ₦50,000. Keep the receipt."), ["Rent is ₦50,000.", "Keep the receipt."])
        self.assertEqual(shorts_sound.sentences(""), [])

    def test_narration_reads_the_say_and_marks_the_scene_detailed(self):
        topic = shorts_reel.topic_for(datetime.date(2026, 10, 20))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/_d.mp4")
        lines = shorts_sound.narration_for(reel, topic)
        self.assertEqual([l["role"] for l in lines], ["hook", "tip", "tip", "tip", "tip", "conclusion"])
        for l in lines[:-1]:
            self.assertTrue(l["detailed"], l)
            self.assertEqual(l["text"], shorts_sound.spoken(next(sl["say"] for sl in topic["slides"] if shorts_sound.spoken(sl.get("say")) == l["text"])))
            self.assertGreaterEqual(len(l["sentences"]), 2, "an explanation, not a point")
        self.assertFalse(lines[-1]["detailed"])

    def test_without_a_say_the_old_read_stands(self):
        topic = {"title": "Pay without a receipt. Pay twice.", "slides": [
            {"text": "PAY WITHOUT A RECEIPT.\nPAY TWICE.", "sub": "cash leaves no trail"},
            {"text": "TAKE THE RECEIPT", "sub": "on the day"}, {"text": "B", "sub": ""}, {"text": "C", "sub": ""},
            {"text": "D", "sub": ""}, {"text": "GENERAL INFO ONLY", "sub": "x"}]}
        reel = shorts_reel.reel_from_topic(topic, "/tmp/_d.mp4")
        lines = shorts_sound.narration_for(reel, topic)
        self.assertEqual(lines[1]["text"], "Take the receipt. On the day.")
        self.assertFalse(lines[1]["detailed"])

    def test_the_brain_must_write_the_says_and_stay_under_the_budget(self):
        short = {"title": "T", "hook_sub": "x", "hook_say": " ".join(["word"] * 30),
                 "tips": [{"text": "A b", "sub": "", "say": " ".join(["word"] * 30)} for _ in range(4)]}
        self.assertEqual(brain.short_problems(short), [])
        missing = {**short, "tips": [{"text": "A b", "sub": ""}] + short["tips"][1:]}
        self.assertTrue(any("say is required" in p for p in brain.short_problems(missing)))
        self.assertTrue(any("hook_say is required" in p for p in brain.short_problems({**short, "hook_say": ""})))
        fat = {**short, "tips": [{"text": "A b", "sub": "", "say": " ".join(["word"] * 45)} for _ in range(4)]}
        self.assertTrue(any("at most %d" % brain.SAY_TOTAL_MAX in p for p in brain.short_problems(fat)))
        linked = {**short, "tips": [{"text": "A b", "sub": "", "say": "Go to docoga.com.ng " + " ".join(["now"] * 12)}] + short["tips"][1:]}
        self.assertTrue(any("no link" in p for p in brain.short_problems(linked)))
        self.assertIn('"hook_say"', brain.PLAN_PROMPT if hasattr(brain, "PLAN_PROMPT") else (ROOT / "tools/brain.py").read_text(encoding="utf-8"))

    def test_the_brains_short_carries_its_says_into_the_slides(self):
        pack = {"date": "2026-10-20", "short": {"title": "T", "hook_sub": "h", "hook_say": "Hook say here.",
                                                 "tips": [{"text": "A", "sub": "a", "say": "Say %d." % i} for i in range(4)]}}
        topic = brain_drafts.short_topic(pack)
        self.assertEqual(topic["slides"][0]["say"], "Hook say here.")
        self.assertEqual([s["say"] for s in topic["slides"][1:5]], ["Say 0.", "Say 1.", "Say 2.", "Say 3."])


@unittest.skipUnless(IMPORT_OK, "video modules not importable (PIL/numpy)")
class Captions(unittest.TestCase):
    def reel_and_clips(self, seconds=7.0):
        topic = shorts_reel.topic_for(datetime.date(2026, 10, 20))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/_d.mp4")
        lines = shorts_sound.narration_for(reel, topic)
        clips = [{**l, "seconds": seconds if l["role"] != "conclusion" else 3.0} for l in lines]
        return reel, clips

    def test_each_sentence_becomes_a_timed_caption_and_the_sub_line_makes_way(self):
        reel, clips = self.reel_and_clips()
        shorts_sound.fit_scenes(reel, clips)
        n = shorts_sound.caption_beats(reel, clips, ms=ms)
        self.assertEqual(n, sum(len(c["sentences"]) for c in clips if c["detailed"]))
        for sc, c in zip(reel["scenes"][:-1], clips[:-1]):
            caps = [b for b in sc["beats"] if b["kind"] == "caption"]
            self.assertEqual([b["text"] for b in caps], c["sentences"])
            self.assertFalse([b for b in sc["beats"] if b["kind"] == "support"], "the captions ARE the explanation")
            self.assertEqual(caps[0]["t0"], shorts_sound.VOICE_LEAD_S)
            for a, b in zip(caps, caps[1:]):
                self.assertEqual(a["t1"], b["t0"], "captions hand over without a gap")
            self.assertLessEqual(caps[-1]["t1"], sc["dur"] - 0.05)
            self.assertAlmostEqual(caps[-1]["t1"], shorts_sound.VOICE_LEAD_S + c["seconds"], places=1)
            for b in caps:
                self.assertTrue(b["exempt"], "a caption never retimes the scene — the voice already did")
        last = reel["scenes"][-1]
        self.assertFalse([b for b in last["beats"] if b["kind"] == "caption"], "the end card is not captioned")
        self.assertTrue([b for b in last["beats"] if b["kind"] == "support"])

    def test_no_voice_no_captions(self):
        reel, _ = self.reel_and_clips()
        before = [len(sc["beats"]) for sc in reel["scenes"]]
        self.assertEqual(shorts_sound.caption_beats(reel, [], ms=ms), 0)
        self.assertEqual([len(sc["beats"]) for sc in reel["scenes"]], before)

    def test_the_hard_cap_holds_a_whole_detailed_read(self):
        """160 words at a slow 2.2 words/s is ~73 s of voice; with leads, tails and the end card the
        reel must still clear fit_scenes — a refusal here would be a Short that never ships."""
        reel, clips = self.reel_and_clips(seconds=73.0 / 5)
        total = shorts_sound.fit_scenes(reel, clips)
        self.assertLess(total, shorts_sound.HARD_CAP_S)
        self.assertLessEqual(shorts_sound.HARD_CAP_S, 90.0, "Facebook Reels stop at 90 s")

    def test_motionstudio_knows_the_caption_kind(self):
        self.assertIn("caption", ms.RENDER)
        self.assertEqual(ms.weight_of({"kind": "caption"}), "Medium")
        self.assertEqual(ms.entrance_dur({"kind": "caption"}), ms.CAPTION_FADE)
        for kinds in (ms.SETTLE_KINDS, ms.READ_KINDS, ms.BOX_KINDS):
            self.assertNotIn("caption", kinds, "a timed subtitle is judged by its own events, not the settle/overlap rules")
        reel = {"scenes": [dict(id="A", role="tip", dur=6.0, punch=0.03, trans="whip", beats=[
            ms.Beat("caption", "caption", "One.", t0=0.3, t1=2.0, exempt=True, color=ms.WHITE),
            ms.Beat("caption", "caption", "Two.", t0=2.0, t1=5.5, exempt=True, color=ms.WHITE)])]}
        labels = [e[2] for e in ms.events_of(reel)]
        self.assertEqual(labels.count("caption in"), 2)
        self.assertEqual(labels.count("caption out"), 2)
        self.assertLess(ms.CAPTION_Y, ms.SAFE["bottom"])

    def test_the_bridge_captions_after_the_voice_fits_the_scenes(self):
        body = (ROOT / "tools/shorts_reel.py").read_text(encoding="utf-8")
        self.assertLess(body.index("shorts_sound.fit_scenes("), body.index("shorts_sound.caption_beats("))
        self.assertLess(body.index("shorts_sound.caption_beats("), body.index("ms.build("))

    @unittest.skipUnless(IMPORT_OK and ms.find_font_template(), "Inter is not installed")
    def test_a_caption_frame_draws_the_sentence_inside_the_safe_zone(self):
        import numpy as np
        from PIL import Image
        sc = dict(id="B", role="tip", dur=6.0, punch=0.03, trans="whip", beats=[
            ms.Beat("badge", "emphasis", shape="check", color=ms.GREEN, cy=500, r=52),
            ms.Beat("cascade", "emphasis", "TAKE THE RECEIPT", size=140, y=610, color=ms.WHITE),
            ms.Beat("caption", "caption", "It should show the date, the amount, the months it covers, the address, and the landlord's name.",
                    t0=0.3, t1=5.0, exempt=True, color=ms.WHITE)])
        reel = dict(scenes=[sc], cap=90.0)
        ms.solve_sizes(reel)
        ms.solve_layout(reel)
        ms.schedule(reel)
        cap = sc["beats"][-1]
        content = Image.new("RGBA", (ms.W, ms.H), (0, 0, 0, 0))
        from PIL import ImageDraw
        d = ImageDraw.Draw(content)
        cap["_scene"] = sc
        ms.r_caption(d, content, cap, 2.5)
        y, size, lines = ms.caption_layout(sc, cap)
        self.assertGreaterEqual(len(lines), 2)
        self.assertLessEqual(y + 24 + len(lines) * (size + 20), ms.SAFE["bottom"] + 40)
        alpha = np.asarray(content.getchannel("A"))
        ys, xs = np.nonzero(alpha > 40)
        self.assertTrue(len(ys))
        self.assertGreaterEqual(ys.min(), ms.CAPTION_Y - 2)
        self.assertLessEqual(ys.max(), ms.SAFE["bottom"] + 2)
        self.assertGreaterEqual(xs.min(), ms.SAFE["left"] - 2)
        self.assertLessEqual(xs.max(), ms.SAFE["right"] + 2)
        blank = Image.new("RGBA", (ms.W, ms.H), (0, 0, 0, 0))
        ms.r_caption(ImageDraw.Draw(blank), blank, cap, 5.5)
        self.assertEqual(int(np.asarray(blank.getchannel("A")).max()), 0, "gone after t1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
