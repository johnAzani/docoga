#!/usr/bin/env python3
"""MotionStudio v5 — the camera and the kinetic captions (owner, 20 Oct 2026).

"Text motion graphics over the image as the voice-over speaks, smooth camera movements,
images that explain what the voice-over is saying per time, people watch to the end."

  tools/wordsync.py      when each word is said (Vosk on the lanes, the estimate elsewhere)
  tools/shorts_sound.py  sync_words + caption beats that carry their words
  tools/motionstudio.py  camera_bg (one shot per sentence, smoother-step moves, cross-dissolve),
                         r_kinetic (phrase cards, the said word lit), QA that judges the type
                         and forgives the camera
  tools/shorts_reel.py   shot_plan / attach_shots per sentence, the TIP n OF 4 counter
"""
import datetime
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

import wordsync  # noqa: E402

try:
    import numpy as np  # noqa: E402
    from PIL import Image, ImageDraw  # noqa: E402
    import motionstudio as ms  # noqa: E402
    import shorts_reel  # noqa: E402
    import shorts_sound  # noqa: E402
    import shot_match  # noqa: E402
    IMPORT_OK = True
except Exception:  # PIL/numpy missing
    IMPORT_OK = False

SENT = "Collect the receipt the day you pay, not later."


class WordSync(unittest.TestCase):
    def test_the_estimate_is_monotonic_inside_the_clip_and_one_entry_per_display_word(self):
        words = wordsync.estimate(SENT, 3.4)
        self.assertEqual([w["d"] for w in words], SENT.split())
        self.assertGreaterEqual(words[0]["t0"], 0.0)
        self.assertLessEqual(words[-1]["t1"], 3.4)
        for a, b in zip(words, words[1:]):
            self.assertLess(a["t0"], a["t1"])
            self.assertLessEqual(a["t1"], b["t0"])
        self.assertTrue(all(w["t1"] - w["t0"] >= wordsync.MIN_WORD_S * 0.8 for w in words))

    def test_punctuation_buys_a_pause_and_digits_are_slow(self):
        a = wordsync.estimate("Keep the receipt, always.", 3.0)
        self.assertGreater(a[2]["t1"] - a[2]["t0"], a[1]["t1"] - a[1]["t0"], "'receipt,' outlasts 'the'")
        self.assertGreater(wordsync._weight("₦50,000"), wordsync._weight("fifty"))

    def test_a_too_short_clip_is_stretched_rather_than_overlapped(self):
        words = wordsync.estimate("one two three four five six", 0.1)
        for a, b in zip(words, words[1:]):
            self.assertLessEqual(a["t1"], b["t0"])

    def test_phrases_cut_at_the_voices_pauses_and_never_dangle_a_function_word(self):
        w = wordsync.estimate(SENT, 3.4)
        self.assertEqual([" ".join(x["d"] for x in c) for c in wordsync.chunk(w)],
                         ["Collect the receipt", "the day you pay,", "not later."])
        long = "Under the Lagos Tenancy Law your landlord must give you a written receipt for every payment you make."
        chunks = wordsync.chunk(wordsync.estimate(long, 7.0))
        self.assertTrue(all(1 <= len(c) <= 4 for c in chunks), [len(c) for c in chunks])
        self.assertEqual(sum(len(c) for c in chunks), len(long.split()), "every word shown once")
        self.assertTrue(all(len(" ".join(x["d"] for x in c)) <= 24 or len(c) == 1 for c in chunks))

    def test_sentence_spans_follow_the_caption_sentences(self):
        import re
        text = "Rent is ₦50,000. Keep the receipt."
        sents = [p for p in re.split(r"(?<=[.!?])\s+", text) if p]
        spans = wordsync.sentence_spans(wordsync.estimate(text, 3.0), sents)
        self.assertEqual([[w["d"] for w in s] for s in spans], [["Rent", "is", "₦50,000."], ["Keep", "the", "receipt."]])

    def test_without_vosk_words_for_says_so_and_never_raises(self):
        with mock.patch.object(wordsync, "_vosk_ready", return_value=False):
            words, engine = wordsync.words_for("/nonexistent.mp3", SENT, 3.4)
        self.assertEqual(engine, "estimate")
        self.assertEqual(len(words), len(SENT.split()))
        with mock.patch.object(wordsync, "align", return_value=None):
            self.assertEqual(wordsync.words_for(None, SENT, 3.4)[1], "estimate")

    def test_vosk_times_are_mapped_back_onto_display_words(self):
        """The aligner returns one entry per norm token ('50', '000'); the caption shows '₦50,000.'"""
        fake = mock.Mock()
        fake.vosk_available.return_value = True
        fake.asr_words.return_value = [("rent", 0.1, 0.3), ("is", 0.3, 0.4), ("fifty", 0.5, 0.8), ("thousand", 0.8, 1.2)]
        fake.align_section.return_value = [{"t0": 0.1, "t1": 0.3}, {"t0": 0.3, "t1": 0.4}, {"t0": 0.5, "t1": 0.8}, {"t0": 0.8, "t1": 1.2}]
        with mock.patch.dict(sys.modules, {"deepdive": fake}):
            words = wordsync.align("/x.mp3", "Rent is ₦50,000.")
        self.assertEqual([w["d"] for w in words], ["Rent", "is", "₦50,000."])
        self.assertEqual((words[2]["t0"], words[2]["t1"]), (0.5, 1.2))


@unittest.skipUnless(IMPORT_OK, "video modules not importable (PIL/numpy)")
class Captions(unittest.TestCase):
    def reel_and_clips(self):
        topic = shorts_reel.topic_for(datetime.date(2026, 10, 20))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/_v5.mp4")
        lines = shorts_sound.narration_for(reel, topic)
        clips = [{**l, "path": None, "seconds": round(0.36 * len(l["text"].split()) + 0.4, 2)} for l in lines]
        shorts_sound.fit_scenes(reel, clips)
        return reel, topic, clips

    def test_sync_words_times_every_clip_and_prints_the_machine_line(self):
        reel, topic, clips = self.reel_and_clips()
        out = io.StringIO()
        with redirect_stdout(out):
            engine = shorts_sound.sync_words(clips)
        self.assertEqual(engine, "estimate")
        self.assertIn("WORDSYNC=estimate", out.getvalue())
        for c in clips:
            self.assertEqual(len(c["words"]), len(c["text"].split()))
            self.assertLessEqual(c["words"][-1]["t1"], c["seconds"] + 1e-6)

    def test_caption_beats_carry_their_words_in_scene_seconds_and_still_hand_over_without_a_gap(self):
        reel, topic, clips = self.reel_and_clips()
        with redirect_stdout(io.StringIO()):
            shorts_sound.sync_words(clips)
        n = shorts_sound.caption_beats(reel, clips, ms=ms)
        self.assertGreater(n, 5)
        for sc, c in zip(reel["scenes"][:-1], clips[:-1]):
            caps = [b for b in sc["beats"] if b["kind"] == "caption"]
            self.assertEqual([b["text"] for b in caps], c["sentences"])
            self.assertEqual(caps[0]["t0"], shorts_sound.VOICE_LEAD_S)
            for a, b in zip(caps, caps[1:]):
                self.assertEqual(a["t1"], b["t0"])
            self.assertAlmostEqual(caps[-1]["t1"], shorts_sound.VOICE_LEAD_S + c["seconds"], places=1)
            for b in caps:
                self.assertTrue(b["words"], "a timed read gives every caption its words")
                self.assertEqual(" ".join(w["d"] for w in b["words"]), b["text"])
                self.assertGreaterEqual(b["words"][0]["t0"], b["t0"] - 1e-6, "words live inside their sentence")
                self.assertGreaterEqual(b["words"][0]["t0"], shorts_sound.VOICE_LEAD_S, "scene seconds, not clip seconds")

    def test_untimed_clips_keep_the_plain_sentence_captions(self):
        reel, topic, clips = self.reel_and_clips()
        shorts_sound.caption_beats(reel, clips, ms=ms)
        caps = [b for sc in reel["scenes"] for b in sc["beats"] if b["kind"] == "caption"]
        self.assertTrue(caps)
        self.assertTrue(all(not b.get("words") for b in caps))

    def test_the_engine_schedules_a_phrase_and_a_word_event_for_each(self):
        words = [{"d": w["d"], "t0": round(w["t0"] + 0.3, 3), "t1": round(w["t1"] + 0.3, 3)} for w in wordsync.estimate(SENT, 3.0)]
        b = ms.Beat("caption", "caption", SENT, t0=0.3, t1=3.4, exempt=True, color=ms.WHITE, words=words)
        reel = {"scenes": [dict(id="A", role="tip", dur=4.0, punch=0.03, trans="whip", beats=[b])]}
        labels = [e[2] for e in ms.events_of(reel)]
        self.assertEqual(labels.count("caption word"), len(words))
        self.assertEqual(labels.count("caption phrase"), 3)
        self.assertEqual(labels.count("caption out"), 1)
        chunks = ms.caption_chunks(b)
        self.assertEqual(chunks[0]["t0"], 0.3)
        self.assertEqual(chunks[-1]["t1"], 3.4)
        for a, nxt in zip(chunks, chunks[1:]):
            self.assertEqual(a["t1"], nxt["t0"], "phrases hand over without a gap")

    @unittest.skipUnless(IMPORT_OK and ms.find_font_template(), "Inter is not installed")
    def test_the_said_word_is_yellow_the_rest_white_inside_the_safe_zone(self):
        words = [{"d": w["d"], "t0": round(w["t0"] + 0.3, 3), "t1": round(w["t1"] + 0.3, 3)} for w in wordsync.estimate(SENT, 3.0)]
        cap = ms.Beat("caption", "caption", SENT, t0=0.3, t1=3.4, exempt=True, color=ms.WHITE, words=words)
        sc = dict(id="B", role="tip", dur=4.0, punch=0.03, trans="whip", beats=[
            ms.Beat("kicker", "kicker", "TIP 1 OF 4", size=28, y=392, color=ms.FAINT),
            ms.Beat("badge", "emphasis", shape="check", color=ms.GREEN, cy=500, r=52),
            ms.Beat("cascade", "emphasis", "TAKE THE RECEIPT", size=140, y=610, color=ms.WHITE), cap])
        reel = dict(scenes=[sc], cap=90.0)
        ms.solve_sizes(reel); ms.solve_layout(reel); ms.schedule(reel)
        cap["_scene"] = sc
        # mid second word: "the" is being said → yellow pixels present; before the first word none
        t_mid = (words[1]["t0"] + words[1]["t1"]) / 2
        img = Image.new("RGBA", (ms.W, ms.H), (0, 0, 0, 0))
        ms.r_caption(ImageDraw.Draw(img), img, cap, t_mid)
        arr = np.asarray(img.convert("RGB")).astype(int)
        alpha = np.asarray(img.getchannel("A"))
        yellow = (np.abs(arr - np.array(ms.YELLOW)).sum(axis=2) < 60) & (alpha > 200)
        white = (np.abs(arr - np.array(ms.WHITE)).sum(axis=2) < 60) & (alpha > 200)
        self.assertGreater(int(yellow.sum()), 150, "the word being said is lit in brand yellow")
        self.assertGreater(int(white.sum()), 150, "the words already said stay white")
        ys, xs = np.nonzero(alpha > 40)
        self.assertGreaterEqual(ys.min(), ms.CAPTION_Y - 2)
        self.assertLessEqual(ys.max(), ms.SAFE["bottom"] + 2)
        self.assertGreaterEqual(xs.min(), ms.SAFE["left"] - 2)
        self.assertLessEqual(xs.max(), ms.SAFE["right"] + 2)
        y, size = ms.kinetic_layout(sc, cap)
        self.assertGreaterEqual(size, 40)
        gone = Image.new("RGBA", (ms.W, ms.H), (0, 0, 0, 0))
        ms.r_caption(ImageDraw.Draw(gone), gone, cap, 3.6)
        self.assertEqual(int(np.asarray(gone.getchannel("A")).max()), 0, "gone after t1")


def _photo(seed=3):
    """A structured 'photograph' at W×H so a camera move changes pixels."""
    im = Image.new("RGB", (ms.W, ms.H), (20, 40, 80))
    d = ImageDraw.Draw(im)
    for i in range(0, ms.H, 48):
        d.rectangle([0, i, ms.W, i + 12], fill=(90 + (i * 7 + seed) % 120, 60, 40))
    for i in range(0, ms.W, 64):
        d.rectangle([i, 0, i + 10, ms.H], fill=(30, 120 + (i + seed) % 100, 90))
    return im


@unittest.skipUnless(IMPORT_OK, "video modules not importable (PIL/numpy)")
class Camera(unittest.TestCase):
    def test_smoother_step_starts_and_stops_dead_still(self):
        self.assertEqual(ms.smoother(0), 0.0)
        self.assertEqual(ms.smoother(1), 1.0)
        self.assertAlmostEqual(ms.smoother(0.5), 0.5)
        self.assertLess(ms.smoother(0.02) - ms.smoother(0.0), 0.0005, "no jolt at the start")
        self.assertLess(ms.smoother(1.0) - ms.smoother(0.98), 0.0005, "no bump at the end")
        self.assertEqual(ms.smoother(-1), 0.0)
        self.assertEqual(ms.smoother(2), 1.0)

    def test_every_move_travels_ten_percent_and_stays_inside_the_picture(self):
        for move in ms.CAM_MOVES + ("tilt-down",):
            with self.subTest(move=move):
                for p in (0.0, 0.25, 0.5, 0.75, 1.0):
                    x0, y0, x1, y1 = ms.camera_box(move, p)
                    self.assertGreaterEqual(x0, -1e-6); self.assertGreaterEqual(y0, -1e-6)
                    self.assertLessEqual(x1, ms.W + 1e-6); self.assertLessEqual(y1, ms.H + 1e-6)
                    self.assertAlmostEqual((x1 - x0) / (y1 - y0), ms.W / ms.H, places=6, msg="aspect kept")
        self.assertEqual(ms.camera_box("push", 0.0), (0.0, 0.0, ms.W, ms.H), "a push starts on the full picture")
        x0, _, x1, _ = ms.camera_box("push", 1.0)
        self.assertAlmostEqual((x1 - x0) / ms.W, 1 / (1 + ms.CAM_TRAVEL), places=6)
        self.assertAlmostEqual(ms.camera_box("pan-right", 0.0)[0], 0.0)
        self.assertAlmostEqual(ms.camera_box("pan-right", 1.0)[2], ms.W)
        self.assertAlmostEqual(ms.camera_box("pan-left", 0.0)[2], ms.W)
        self.assertAlmostEqual(ms.camera_box("tilt-up", 0.0)[3], ms.H)

    def test_the_move_is_sub_pixel_smooth_frame_to_frame(self):
        shot = dict(img=_photo(), move="pan-right", t0=0.0, t1=4.0)
        steps = []
        prev = None
        for i in range(0, 121, 1):
            fr = np.asarray(ms.shot_frame(shot, i / 120)).astype(int)
            if prev is not None:
                steps.append(np.abs(fr - prev).mean())
            prev = fr
        self.assertGreater(max(steps), 0.0, "the camera moves")
        mid = steps[55:65]
        self.assertLess(max(mid) / (min(mid) + 1e-9), 1.6, "no judder: neighbouring frames change by about the same amount")
        self.assertLess(steps[0], steps[60] * 0.5, "it eases in")
        self.assertLess(steps[-1], steps[60] * 0.5, "and eases out")

    def test_camera_bg_is_deterministic_cross_dissolves_and_falls_back_to_the_navy(self):
        a, b = _photo(1), _photo(9)
        sc = dict(id="B", role="tip", dur=6.0, punch=0.0, trans="whip", beats=[],
                  _shots=[dict(t0=0.0, t1=3.0, img=a, move="push"), dict(t0=3.0, t1=6.0, img=b, move="pull")])
        f1 = np.asarray(ms.camera_bg(sc, 1.0, False)).astype(int)
        f2 = np.asarray(ms.camera_bg(sc, 1.0, False)).astype(int)
        self.assertEqual(int(np.abs(f1 - f2).max()), 0, "render and QA must see the same background")
        at_cut = np.asarray(ms.camera_bg(sc, 3.0, False)).astype(int)
        after = np.asarray(ms.camera_bg(sc, 3.0 + ms.XFADE + 0.1, False)).astype(int)
        mid = np.asarray(ms.camera_bg(sc, 3.0 + ms.XFADE / 2, False)).astype(int)
        self.assertLess(np.abs(at_cut - np.asarray(ms.shot_frame(sc["_shots"][0], 1.0)).astype(int)).mean(), 2.0,
                        "at the cut the old shot is still fully there — the dissolve starts, it does not jump")
        self.assertLess(np.abs(after - np.asarray(ms.shot_frame(sc["_shots"][1], (ms.XFADE + 0.1) / 3.0)).astype(int)).mean(), 2.0)
        self.assertGreater(np.abs(mid - at_cut).mean(), 0.3, "halfway through the dissolve it is neither shot")
        self.assertGreater(np.abs(mid - after).mean(), 0.3)
        navy = dict(id="F", role="conclusion", dur=4.0, punch=0.0, trans="dissolve", beats=[])
        self.assertEqual(int(np.abs(np.asarray(ms.camera_bg(navy, 1.0, True)).astype(int) - np.asarray(ms.BASE).astype(int)).max()), 0)
        single = dict(id="C", role="tip", dur=4.0, punch=0.0, trans="flash", beats=[], _bg=a)
        self.assertEqual(ms.scene_shots(single)[0]["t1"], 4.0, "a single _bg is one shot for the whole scene")
        self.assertIs(ms.scene_bg(single), a)
        wrong = dict(id="D", role="tip", dur=4.0, punch=0.0, trans="flash", beats=[], _shots=[dict(t0=0, t1=4, img=Image.new("RGB", (10, 10)))])
        self.assertEqual(ms.scene_shots(wrong), [], "a wrong-sized picture is refused")

    def test_shots_alternate_their_moves_when_the_lane_names_none(self):
        shots = [dict(t0=i * 1.0, t1=i * 1.0 + 1.0, img=_photo(i)) for i in range(4)]
        sc = dict(id="B", role="tip", dur=4.0, punch=0.0, trans="whip", beats=[], _shots=shots)
        moves = [s["move"] for s in ms.scene_shots(sc)]
        self.assertEqual(moves, list(ms.CAM_MOVES[:4]))
        self.assertGreater(len(set(moves)), 2)

    @unittest.skipUnless(IMPORT_OK and ms.find_font_template(), "Inter is not installed")
    def test_qa_forgives_the_camera_and_still_catches_moving_type(self):
        """36 frames of a moving photograph under a still kicker: zero animation violations.
        The same frames with the kicker nudged on one frame: a violation. The QA judges type."""
        sc = dict(id="B", role="tip", dur=1.2, punch=0.0, trans="flash",
                  beats=[ms.Beat("kicker", "kicker", "TIP 1 OF 4", size=28, y=392, color=ms.FAINT, t0=0.0)],
                  _shots=[dict(t0=0.0, t1=1.2, img=_photo(), move="pan-right")])
        reel = dict(name="qa", scenes=[sc], cap=90.0, poster=False, out="/tmp/_qa.mp4")
        ms.solve_sizes(reel); ms.solve_layout(reel); ms.schedule(reel)
        sc["dur"] = 1.2; reel["total"] = 1.2
        ms.events_of(reel)
        fd, n = ms.render_reel(reel, "v5qa")
        anim = [m for cat, m in ms.qa_reel(reel, fd, n) if cat == "animation"]
        self.assertEqual(anim, [])
        # nudge the type on one late frame and the engine must notice
        i = n - 3
        fr = Image.open(f"{fd}/f_{i:04d}.png").convert("RGB")
        bg = ms.camera_bg(sc, i / ms.FPS, True)
        moved = bg.copy()
        from PIL import ImageChops
        moved.paste(ImageChops.offset(fr, 0, 40))
        moved.save(f"{fd}/f_{i:04d}.png")
        anim = [m for cat, m in ms.qa_reel(reel, fd, n) if cat == "animation"]
        self.assertTrue(anim, "type that moves outside an event is still a violation")


@unittest.skipUnless(IMPORT_OK, "video modules not importable (PIL/numpy)")
class Bridge(unittest.TestCase):
    def test_tip_scenes_count_themselves_and_announce_the_last(self):
        self.assertEqual(shorts_reel.tip_counter(0, 4), "TIP 1 OF 4")
        self.assertEqual(shorts_reel.tip_counter(3, 4), "LAST TIP · 4 OF 4")
        topic = shorts_reel.topic_for(datetime.date(2026, 10, 20))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/_v5.mp4")
        tips = [sc for sc in reel["scenes"] if sc["role"] == "tip"]
        kick = [[b["text"] for b in sc["beats"] if b["kind"] == "kicker"][0] for sc in tips]
        self.assertEqual(kick, ["TIP 1 OF 4", "TIP 2 OF 4", "TIP 3 OF 4", "LAST TIP · 4 OF 4"])
        ms.solve_sizes(reel); ms.solve_layout(reel); ms.schedule(reel)
        for sc in tips:
            boxes = sorted(ms.beat_box(b) for b in sc["beats"] if b["kind"] in ms.BOX_KINDS)
            for (a0, a1), (b0, b1) in zip(boxes, boxes[1:]):
                self.assertLessEqual(a1, b0 + 6, "the counter sits clear of the badge")

    def test_shot_plan_follows_the_sentences_once_the_voice_has_timed_them(self):
        topic = shorts_reel.topic_for(datetime.date(2026, 10, 20))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/_v5.mp4")
        before = shorts_reel.shot_plan(reel, topic)
        self.assertTrue(all(len(spans) == 1 and spans[0][0] == 0.0 for _, spans in before), "no voice: one shot per scene")
        lines = shorts_sound.narration_for(reel, topic)
        clips = [{**l, "path": None, "seconds": round(0.36 * len(l["text"].split()) + 0.4, 2)} for l in lines]
        shorts_sound.fit_scenes(reel, clips)
        with redirect_stdout(io.StringIO()):
            shorts_sound.sync_words(clips)
        shorts_sound.caption_beats(reel, clips, ms=ms)
        plan = shorts_reel.shot_plan(reel, topic)
        self.assertEqual([sc["role"] for sc, _ in plan], ["hook", "tip", "tip", "tip", "tip"])
        for sc, spans in plan:
            caps = [b["text"] for b in sc["beats"] if b["kind"] == "caption"]
            self.assertEqual([t for _, _, t in spans], caps, "one shot per spoken sentence")
            for (a0, a1, _), (b0, b1, _) in zip(spans, spans[1:]):
                self.assertEqual(a1, b0)

    def test_attach_shots_gives_each_sentence_its_picture_and_a_camera_move(self):
        topic = shorts_reel.topic_for(datetime.date(2026, 10, 20))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/_v5.mp4")
        lines = shorts_sound.narration_for(reel, topic)
        clips = [{**l, "path": None, "seconds": round(0.36 * len(l["text"].split()) + 0.4, 2)} for l in lines]
        shorts_sound.fit_scenes(reel, clips)
        with redirect_stdout(io.StringIO()):
            shorts_sound.sync_words(clips)
        shorts_sound.caption_beats(reel, clips, ms=ms)
        plan = shorts_reel.shot_plan(reel, topic)
        n_sent = sum(len(spans) for _, spans in plan)
        frame = Image.new("RGB", (ms.W, ms.H), (20, 30, 40))
        calls = []

        def fake_photo(text, hint=None, size=None, treat=None, **k):
            calls.append(text)
            if len(calls) == 2:
                return None, "nothing matched"
            return frame, {"query": "q%d" % len(calls), "license": "cc0"}
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"DOCOGA_SHOTS": "on"}), \
             mock.patch.object(shot_match, "photo_for", side_effect=fake_photo), \
             mock.patch.object(shot_match, "query_chain", side_effect=lambda t, hint=None: [t[:12], "lagos street nigeria"]), \
             redirect_stdout(out):
            hits = shorts_reel.attach_shots(reel, topic)
        self.assertEqual(hits, 5, "every hook/tip scene got at least one picture")
        self.assertEqual(len(calls), n_sent, "one lookup per sentence, in the narrator's words")
        shots = [s for sc in reel["scenes"] for s in sc.get("_shots", [])]
        self.assertEqual(len(shots), n_sent - 1, "the sentence with no picture kept the shot before it")
        self.assertIn("SHOTS_TOTAL=%d" % (n_sent - 1), out.getvalue())
        first = reel["scenes"][0]
        self.assertIs(first["_bg"], first["_shots"][0]["img"], "the cover still takes the scene's first picture")
        self.assertEqual(first["_shots"][0]["t0"], 0.0)
        self.assertEqual(first["_shots"][-1]["t1"], [b for b in first["beats"] if b["kind"] == "caption"][-1]["t1"])
        moves = [s["move"] for s in shots]
        self.assertTrue(all(m in ms.CAM_MOVES for m in moves))
        self.assertNotEqual(moves[0], moves[1], "the camera changes its move from shot to shot")
        self.assertIs(ms.scene_bg(reel["scenes"][-1]), ms.BASE, "the conclusion is never photographed")

    def test_the_same_subject_twice_running_keeps_one_picture_and_lets_the_camera_run(self):
        topic = shorts_reel.topic_for(datetime.date(2026, 10, 20))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/_v5.mp4")
        sc = reel["scenes"][1]
        sc["beats"] += [ms.Beat("caption", "caption", "Keep the receipt.", t0=0.3, t1=2.0, exempt=True, color=ms.WHITE),
                        ms.Beat("caption", "caption", "The receipt again.", t0=2.0, t1=4.0, exempt=True, color=ms.WHITE)]
        frame = Image.new("RGB", (ms.W, ms.H), (20, 30, 40))
        with mock.patch.dict(os.environ, {"DOCOGA_SHOTS": "on"}), \
             mock.patch.object(shot_match, "photo_for", return_value=(frame, {"query": "paper receipt"})), \
             mock.patch.object(shot_match, "query_chain", return_value=["paper receipt", "lagos street nigeria"]), \
             redirect_stdout(io.StringIO()):
            shorts_reel.attach_shots(reel, topic)
        self.assertEqual(len(sc["_shots"]), 1)
        self.assertEqual((sc["_shots"][0]["t0"], sc["_shots"][0]["t1"]), (0.0, 4.0))

    def test_render_topic_syncs_words_between_the_fit_and_the_captions(self):
        body = (ROOT / "tools/shorts_reel.py").read_text(encoding="utf-8")
        self.assertLess(body.index("shorts_sound.fit_scenes("), body.index("shorts_sound.sync_words("))
        self.assertLess(body.index("shorts_sound.sync_words("), body.index("shorts_sound.caption_beats("))
        self.assertLess(body.index("shorts_sound.caption_beats("), body.index("hits = attach_shots(reel, topic)"))


class Lanes(unittest.TestCase):
    def test_every_render_lane_installs_the_word_sync_engine_best_effort(self):
        for wf in ("youtube_scheduled.yml", "facebook_autopost.yml", "narrator_resume.yml", "tiktok_test.yml"):
            src = (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")
            with self.subTest(workflow=wf):
                self.assertIn("tools/install_wordsync_deps.sh", src)
                self.assertLess(src.index("tools/install_motionstudio_deps.sh"), src.index("tools/install_wordsync_deps.sh"))
        script = (ROOT / "tools/install_wordsync_deps.sh").read_text(encoding="utf-8")
        self.assertIn("vosk-model-small-en-us-0.15", script)
        self.assertNotIn("set -e", script, "a model mirror that blinks must not cost the Short")
        self.assertTrue(script.rstrip().endswith("exit 0"))
        self.assertIn("WORDSYNC", (ROOT / ".github/workflows/youtube_scheduled.yml").read_text(encoding="utf-8"))

    def test_the_design_is_written_down(self):
        doc = (ROOT / "docs/SHORTS_MOTION.md").read_text(encoding="utf-8")
        for needle in ("camera_bg", "wordsync", "WORD_LEAD", "XFADE", "TIP 1 OF 4", "smoother"):
            self.assertIn(needle, doc)
        self.assertIn("SHORTS_MOTION.md", (ROOT / "docs/BRAND_STYLE.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
