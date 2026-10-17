#!/usr/bin/env python3
"""
tools/shorts_sound.py — the Shorts / Reels soundtrack
=====================================================

Owner, 15 Oct 2026, after the first silent Reel went live: the old Reels "have
the voice-over, the sound effects, the background sounds". These tests pin the
four promises the fix makes:

  1. the narrator is the LOCKED Deep-Dive voice, imported — never restated;
  2. timing is voice-first (scenes stretch to the read, under a hard cap);
  3. no key / no quota → music + SFX, all-or-nothing on the voice, never silent;
  4. both lanes carry the key and the clip cache, and refuse to ship silence.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT = TOOLS_DIR.parent
for _p in (TOOLS_DIR, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    import numpy as np  # noqa: F401
    import shorts_sound  # noqa: E402
    import shorts_reel  # noqa: E402
    import motionstudio as ms  # noqa: E402
    import soundkit  # noqa: E402
    import deepdive  # noqa: E402
    IMPORT_OK = True
except Exception as exc:  # pragma: no cover
    IMPORT_OK = False
    IMPORT_ERR = exc

try:
    import yaml  # noqa: E402
    YAML_OK = True
except Exception:  # pragma: no cover
    YAML_OK = False

FFMPEG = shutil.which("ffmpeg") or os.environ.get("FFMPEG_BIN")
if not FFMPEG:
    try:
        import imageio_ffmpeg
        FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG = None

TOPIC = {
    "title": "Pay without a receipt. Pay twice.",
    "parent": "dd3",
    "slides": [
        {"text": "PAY WITHOUT A RECEIPT.\nPAY TWICE.", "sub": "cash leaves no trail — paper does"},
        {"text": "TAKE THE RECEIPT", "sub": "on the day — not \"later\""},
        {"text": "KEEP THE TRANSFER RECORD", "sub": "date · amount · reference"},
        {"text": "SAY WHAT IT WAS FOR", "sub": "keep the reply"},
        {"text": "ONE FOLDER. TWO PLACES.", "sub": "phone plus cloud"},
        {"text": "GENERAL INFO ONLY", "sub": "Rules vary by state and agreement"},
    ],
}


def quiet(fn, *a, **kw):
    with redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def fake_tts_factory(seconds_per_word=0.33, log=None):
    """A stand-in for deepdive.gemini_tts that writes a speech-shaped mp3."""
    def fake(text, voice, instruction, out):
        if log is not None:
            log.append((text, voice, instruction))
        secs = seconds_per_word * len(text.split()) + 0.4
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi",
                        "-i", "anoisesrc=c=pink:r=24000:a=0.5:d=%.2f" % secs,
                        "-af", "bandpass=f=400:w=600,tremolo=f=4:d=0.9,volume=3",
                        "-c:a", "libmp3lame", str(out)], check=True)
        return "ok", 0
    return fake


@unittest.skipUnless(IMPORT_OK, "soundtrack modules not importable (PIL/numpy)")
class WordsTests(unittest.TestCase):
    def test_shouted_slide_text_becomes_a_sentence(self):
        self.assertEqual(shorts_sound.sentence("TAKE THE RECEIPT"), "Take the receipt.")
        self.assertEqual(shorts_sound.sentence("ONE FOLDER. TWO PLACES."), "One folder. Two places.")
        self.assertEqual(shorts_sound.sentence("date · amount · reference"), "Date, amount, reference.")
        self.assertEqual(shorts_sound.sentence("cash leaves no trail — paper does"),
                         "Cash leaves no trail — paper does.")
        self.assertEqual(shorts_sound.sentence(""), "")

    def test_the_brand_is_spelled_for_the_ear(self):
        self.assertIn("Doc Oga dot com dot N G", shorts_sound.sentence("visit docoga.com.ng"))

    def test_one_line_per_scene_in_scene_order(self):
        reel = shorts_reel.reel_from_topic(TOPIC, "/tmp/_t.mp4")
        lines = shorts_sound.narration_for(reel, TOPIC)
        self.assertEqual([l["scene"] for l in lines], [sc["id"] for sc in reel["scenes"]])
        self.assertEqual(lines[0]["role"], "hook")
        self.assertTrue(lines[0]["text"].startswith("Pay without a receipt. Pay twice."))
        self.assertEqual([l["role"] for l in lines[1:-1]], ["tip"] * 4)
        self.assertEqual(lines[1]["text"], "Take the receipt. On the day — not \"later\".")
        self.assertEqual(lines[-1]["role"], "conclusion")
        self.assertIn("Doc Oga dot com dot N G", lines[-1]["text"])
        self.assertIn("General information only", lines[-1]["text"])
        for l in lines:
            self.assertNotIn("·", l["text"], "a middle dot is read as nothing or as 'dot'")


@unittest.skipUnless(IMPORT_OK, "soundtrack modules not importable (PIL/numpy)")
class LockedVoiceTests(unittest.TestCase):
    """The narrator is defined once, in tools/deepdive.py, behind a fingerprint."""

    def test_this_module_never_restates_the_voice(self):
        source = (TOOLS_DIR / "shorts_sound.py").read_text(encoding="utf-8")
        self.assertNotIn("Narrate this", source)
        self.assertNotIn("voiceName", source)
        self.assertNotIn("prebuiltVoiceConfig", source)
        self.assertNotIn("generativelanguage", source)
        self.assertIn("locked_voice()", source)
        self.assertIn("gemini_tts", source)

    @unittest.skipUnless(FFMPEG, "ffmpeg not available")
    def test_every_request_goes_out_with_the_locked_narrator(self):
        reel = shorts_reel.reel_from_topic(TOPIC, "/tmp/_t.mp4")
        lines = shorts_sound.narration_for(reel, TOPIC)
        calls = []
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(shorts_sound, "VOICE_CACHE_DIR", Path(tmp)), \
             patch.object(shorts_sound.gemini_quota, "LEDGER", Path(tmp) / "quota.json"), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            clips, dropped = quiet(shorts_sound.narrate, lines, tts=fake_tts_factory(log=calls))
        self.assertEqual(dropped, "")
        self.assertEqual(len(clips), len(lines))
        voice, instruction = deepdive.locked_voice()
        for text, v, ins in calls:
            self.assertEqual(v, voice)
            self.assertEqual(ins, instruction)


@unittest.skipUnless(IMPORT_OK, "soundtrack modules not importable (PIL/numpy)")
@unittest.skipUnless(FFMPEG, "ffmpeg not available")
class NarrateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = patch.object(shorts_sound, "VOICE_CACHE_DIR", Path(self.tmp.name))
        self.cache.start()
        self.addCleanup(self.cache.stop)
        self.ledger = patch.object(shorts_sound.gemini_quota, "LEDGER", Path(self.tmp.name) / "quota.json")
        self.ledger.start()
        self.addCleanup(self.ledger.stop)
        self.reel = shorts_reel.reel_from_topic(TOPIC, "/tmp/_t.mp4")
        self.lines = shorts_sound.narration_for(self.reel, TOPIC)

    def exhausted_ledger(self, minutes_ahead):
        """Write a ledger that says: daily bucket empty, refills in N minutes."""
        q = shorts_sound.gemini_quota
        now = q.now_utc()
        from datetime import timedelta
        q.save({"pacific_day": q.pacific_day(now), "requests": {"m": {"ok": 10, "exhausted": 1, "fail": 0, "by_lane": {}}},
                "limit": {"m": 10}, "updated": now.isoformat(),
                "exhausted": {"m": {"at": now.isoformat(), "resumes_at": (now + timedelta(minutes=minutes_ahead)).isoformat()}}})

    def test_no_key_means_music_only_with_a_reason(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}), \
             patch.object(deepdive, "gemini_key", return_value=""):
            clips, dropped = quiet(shorts_sound.narrate, self.lines, tts=fake_tts_factory())
        self.assertEqual(clips, [])
        self.assertIn("no GEMINI_API_KEY", dropped)

    def test_clips_are_cached_so_the_rotation_costs_quota_once(self):
        calls = []
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k"}):
            quiet(shorts_sound.narrate, self.lines, tts=fake_tts_factory(log=calls))
            n_first = len(calls)
            clips, _ = quiet(shorts_sound.narrate, self.lines, tts=fake_tts_factory(log=calls))
        self.assertEqual(n_first, len(self.lines))
        self.assertEqual(len(calls), n_first, "the second run must be served from the cache")
        self.assertTrue(all(c["cached"] for c in clips))

    def test_quota_beyond_the_budget_drops_the_voice_whole(self):
        """All-or-nothing: scene A banked, scene B says 'wait an hour' → no voice this run,
        but A's clip stays cached for next time."""
        state = {"n": 0}
        real = fake_tts_factory()

        def tts(text, voice, instruction, out):
            state["n"] += 1
            if state["n"] == 2:
                return "wait", 3600.0
            return real(text, voice, instruction, out)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k", "SHORTS_TTS_WAIT_MIN": "1", "SHORTS_VOICE": "optional"}):
            clips, dropped = quiet(shorts_sound.narrate, self.lines, tts=tts)
        self.assertEqual(clips, [])
        self.assertIn("daily bucket ran out", dropped)
        self.assertIn("refills at", dropped)
        self.assertIn("WAT", dropped, "the reason names the reset in the owner's clock")
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.mp3"))), 1, "scene A stays banked")

    def test_a_bucket_known_to_be_empty_is_not_even_asked(self):
        """The ledger remembers the last daily refusal: no request goes out, the reason names the time."""
        self.exhausted_ledger(minutes_ahead=600)
        calls = []
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k"}):
            clips, dropped = quiet(shorts_sound.narrate, self.lines, tts=fake_tts_factory(log=calls))
        self.assertEqual(clips, [])
        self.assertEqual(calls, [])
        self.assertIn("daily bucket is empty", dropped)
        self.assertIn("10 of 10 used", dropped)
        self.assertIn("refills at", dropped)

    def test_required_policy_waits_in_run_when_the_reset_is_near_then_continues(self):
        self.exhausted_ledger(minutes_ahead=15)
        slept = []
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k", "SHORTS_VOICE": "required"}):
            clips, dropped = quiet(shorts_sound.narrate, self.lines, tts=fake_tts_factory(), sleep=slept.append)
        self.assertEqual(dropped, "")
        self.assertEqual(len(clips), len(self.lines))
        self.assertTrue(slept and 14 * 60 < slept[0] < 17 * 60, "slept until the reset (+ a margin): %r" % slept)

    def test_the_in_run_wait_fits_the_lane_jobs_timeout(self):
        self.assertLessEqual(shorts_sound.VOICE_RESUME_WINDOW_MIN, 20, "youtube/facebook jobs time out at 30 min")

    def test_a_far_reset_is_not_waited_for_in_run(self):
        self.exhausted_ledger(minutes_ahead=14 * 60)
        slept = []
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k", "SHORTS_VOICE": "required"}):
            clips, dropped = quiet(shorts_sound.narrate, self.lines, tts=fake_tts_factory(), sleep=slept.append)
        self.assertEqual(clips, [])
        self.assertEqual(slept, [])
        self.assertRegex(dropped, r"in 1[34] h")

    def test_required_policy_raises_with_the_resume_time(self):
        self.exhausted_ledger(minutes_ahead=14 * 60)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k", "SHORTS_VOICE": "required"}):
            clips, dropped = quiet(shorts_sound.narrate, self.lines, tts=fake_tts_factory())
            with self.assertRaises(shorts_sound.VoiceUnavailable) as ctx:
                quiet(shorts_sound.require_voice, clips, dropped)
        self.assertIsNotNone(ctx.exception.resumes_at)
        self.assertIn("refills at", ctx.exception.reason)

    def test_optional_policy_lets_music_only_through(self):
        self.exhausted_ledger(minutes_ahead=14 * 60)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k", "SHORTS_VOICE": "optional"}):
            clips, dropped = quiet(shorts_sound.narrate, self.lines, tts=fake_tts_factory())
            quiet(shorts_sound.require_voice, clips, dropped)   # no raise
        self.assertEqual(clips, [])

    def test_the_default_policy_is_required(self):
        with patch.dict(os.environ, {"SHORTS_VOICE": ""}):
            os.environ.pop("SHORTS_VOICE")
            self.assertEqual(shorts_sound.voice_policy(), "required")

    def test_warm_caches_the_days_lines_without_rendering(self):
        from datetime import date
        calls = []
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k"}):
            clips, dropped = quiet(shorts_sound.warm, date(2026, 10, 16), tts=fake_tts_factory(log=calls))
        self.assertEqual(dropped, "")
        self.assertEqual(len(calls), len(clips))
        self.assertGreater(len(list(Path(self.tmp.name).glob("*.mp3"))), 0)

    def test_a_short_wait_is_waited_out(self):
        state = {"n": 0}
        real = fake_tts_factory()

        def tts(text, voice, instruction, out):
            state["n"] += 1
            if state["n"] == 1:
                return "wait", 0.0
            return real(text, voice, instruction, out)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k"}), patch.object(shorts_sound.time, "sleep"):
            clips, dropped = quiet(shorts_sound.narrate, self.lines, tts=tts)
        self.assertEqual(dropped, "")
        self.assertEqual(len(clips), len(self.lines))

    def test_a_read_far_too_long_for_its_words_is_a_preamble_and_is_refused(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k"}):
            clips, dropped = quiet(shorts_sound.narrate, self.lines, tts=fake_tts_factory(seconds_per_word=2.5))
        self.assertEqual(clips, [])
        self.assertIn("preamble", dropped)
        self.assertEqual(list(Path(self.tmp.name).glob("*.mp3")), [], "a bad read must not be cached")

    def test_a_hard_failure_never_raises_it_degrades(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k"}), patch.object(shorts_sound.time, "sleep"):
            clips, dropped = quiet(shorts_sound.narrate, self.lines, tts=lambda *a: ("fail", 0))
        self.assertEqual(clips, [])
        self.assertIn("failed", dropped)


@unittest.skipUnless(IMPORT_OK, "soundtrack modules not importable (PIL/numpy)")
class TimingTests(unittest.TestCase):
    def reel(self):
        return shorts_reel.reel_from_topic(TOPIC, "/tmp/_t.mp4")

    def test_scenes_stretch_to_the_read_and_the_cap_is_lifted(self):
        reel = self.reel()
        before = [sc["dur"] for sc in reel["scenes"]]
        clips = [{"scene": sc["id"], "seconds": 6.0} for sc in reel["scenes"][:2]]
        total = shorts_sound.fit_scenes(reel, clips)
        after = [sc["dur"] for sc in reel["scenes"]]
        need = shorts_sound.VOICE_LEAD_S + 6.0 + shorts_sound.VOICE_TAIL_S
        self.assertAlmostEqual(after[0], need, places=2)
        self.assertAlmostEqual(after[1], need, places=2)
        self.assertEqual(after[2:], before[2:], "scenes without a longer read keep their timing")
        self.assertAlmostEqual(total, sum(after), places=2)
        self.assertEqual(reel["cap"], shorts_sound.HARD_CAP_S)

    def test_a_short_read_never_shortens_a_scene(self):
        reel = self.reel()
        before = [sc["dur"] for sc in reel["scenes"]]
        shorts_sound.fit_scenes(reel, [{"scene": sc["id"], "seconds": 0.5} for sc in reel["scenes"]])
        self.assertEqual([sc["dur"] for sc in reel["scenes"]], before)

    def test_the_hard_cap_is_a_refusal_not_a_trim(self):
        reel = self.reel()
        with self.assertRaises(RuntimeError):
            shorts_sound.fit_scenes(reel, [{"scene": sc["id"], "seconds": 20.0} for sc in reel["scenes"]])

    def test_the_engine_does_not_trim_the_stretched_scenes_back(self):
        """schedule() trims to reading time when over cap; with narration the cap is lifted."""
        if not ms.find_font_template():
            self.skipTest("Inter is not installed — run tools/install_motionstudio_deps.sh")
        reel = self.reel()
        clips = [{"scene": sc["id"], "seconds": 5.0} for sc in reel["scenes"]]
        shorts_sound.fit_scenes(reel, clips)
        stretched = [sc["dur"] for sc in reel["scenes"]]
        ms.solve_sizes(reel)
        ms.solve_layout(reel)
        quiet(ms.schedule, reel)
        for want, sc in zip(stretched, reel["scenes"]):
            self.assertGreaterEqual(sc["dur"] + 1e-6, want, "scene %s lost narration room" % sc["id"])

    def test_the_cue_sheet_scores_every_scene(self):
        reel = self.reel()
        cues = shorts_sound.cue_sheet(reel)
        kinds = [c["kind"] for c in cues]
        starts, total = shorts_sound.scene_starts(reel)
        self.assertEqual(kinds[0], "hit", "the hook lands on a hit")
        self.assertEqual(kinds.count("whoosh"), 4)
        self.assertEqual(kinds.count("tick"), 4)
        self.assertEqual(kinds.count("riser"), 1)
        self.assertEqual(kinds.count("stinger"), 1)
        self.assertEqual([c["t"] for c in cues], sorted(c["t"] for c in cues))
        self.assertTrue(all(0 <= c["t"] < total for c in cues))
        stinger = next(c for c in cues if c["kind"] == "stinger")
        self.assertAlmostEqual(stinger["t"], starts[-1] + 0.05, places=2)


@unittest.skipUnless(IMPORT_OK, "soundtrack modules not importable (PIL/numpy)")
@unittest.skipUnless(FFMPEG, "ffmpeg not available")
class ScoreTests(unittest.TestCase):
    """A real mux on a tiny rendered placeholder — the picture is a colour, the sound is real."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.reel = shorts_reel.reel_from_topic(TOPIC, "/tmp/_t.mp4")
        for sc in self.reel["scenes"]:
            sc["dur"] = 1.0  # 6 s total keeps the test fast
        _, self.total = shorts_sound.scene_starts(self.reel)
        self.video = Path(self.tmp.name) / "clip.mp4"
        subprocess.run([FFMPEG, "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "color=c=0x061A33:s=108x192:r=30:d=%.2f" % self.total,
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                        str(self.video)], check=True)
        self.ff = patch.object(deepdive, "ffmpeg", return_value=FFMPEG)
        self.ff.start()
        self.addCleanup(self.ff.stop)

    def test_the_rendered_placeholder_is_silent_and_is_refused_as_is(self):
        with self.assertRaises(RuntimeError):
            shorts_sound.assert_not_silent(FFMPEG, self.video)

    def test_music_only_is_not_silent_and_writes_the_report(self):
        report = quiet(shorts_sound.score, self.reel, [], self.video, dropped_reason="no key")
        self.assertEqual(report["mode"], "music_only")
        self.assertTrue(report["voice_dropped"])
        self.assertEqual(report["voice_dropped_reason"], "no key")
        self.assertGreater(report["track_level_dbfs"], shorts_sound.SILENCE_FLOOR_DBFS)
        self.assertTrue(self.video.with_suffix(".audio.json").is_file())
        level = shorts_sound.assert_not_silent(FFMPEG, self.video)
        self.assertGreater(level, -30, "loudnorm should land a phone-ready level")
        self.assertIn("music + SFX, no voice", shorts_sound.summary_line(self.video))

    def test_voice_mix_keeps_the_bed_under_the_narrator(self):
        lines = shorts_sound.narration_for(self.reel, TOPIC)
        with patch.object(shorts_sound, "VOICE_CACHE_DIR", Path(self.tmp.name) / "vc"), \
             patch.object(shorts_sound.gemini_quota, "LEDGER", Path(self.tmp.name) / "quota.json"), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "k"}):
            clips, dropped = quiet(shorts_sound.narrate, lines, tts=fake_tts_factory(seconds_per_word=0.05))
        self.assertEqual(dropped, "")
        report = quiet(shorts_sound.score, self.reel, clips, self.video)
        self.assertEqual(report["mode"], "voice")
        self.assertEqual(report["voice"], deepdive.LOCKED_VOICE_NAME)
        self.assertEqual(len(report["lines"]), len(lines))
        self.assertGreaterEqual(report["bed_separation_db"], 10.0, "the bed must sit clearly under speech")
        self.assertLessEqual(report["bed_separation_db"], 24.0, "…but still be audible on a phone")
        self.assertIn("voice Orus", shorts_sound.summary_line(self.video))


@unittest.skipUnless(IMPORT_OK, "soundtrack modules not importable (PIL/numpy)")
class BridgeTests(unittest.TestCase):
    def test_render_topic_scores_after_the_build_and_fits_before_it(self):
        source = (TOOLS_DIR / "shorts_reel.py").read_text(encoding="utf-8")
        body = source.split("def render_topic(", 1)[1]
        self.assertLess(body.index("shorts_sound.narrate("), body.index("ms.build("))
        self.assertLess(body.index("shorts_sound.fit_scenes("), body.index("ms.build("))
        self.assertLess(body.index("ms.build("), body.index("shorts_sound.score("))

    def test_sound_is_on_unless_explicitly_switched_off(self):
        with patch.dict(os.environ, {"SHORTS_SOUND": ""}):
            self.assertTrue(shorts_reel.sound_enabled())
        with patch.dict(os.environ, {"SHORTS_SOUND": "off"}):
            self.assertFalse(shorts_reel.sound_enabled())

    def test_both_lanes_report_the_soundtrack(self):
        for name in ("youtube_short_daily.py", "facebook_reel_daily.py"):
            with self.subTest(script=name):
                self.assertIn("shorts_sound.summary_line(", (ROOT / "scripts" / name).read_text(encoding="utf-8"))


@unittest.skipUnless(YAML_OK, "PyYAML not installed")
class WorkflowTests(unittest.TestCase):
    """The key reaches the render, and the narrator's cache survives between runs."""

    def steps(self, name):
        doc = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
        out = []
        for job in doc["jobs"].values():
            out += job.get("steps") or []
        return {s.get("name"): s for s in out if s.get("name")}

    def test_youtube_render_step_has_the_key_and_a_cache(self):
        steps = self.steps("youtube_scheduled.yml")
        env = steps["Generate today's Short"].get("env") or {}
        self.assertEqual(env.get("GEMINI_API_KEY"), "${{ secrets.GEMINI_API_KEY }}")
        cache = steps["Restore the narrator's cached clips"]
        self.assertTrue(cache["uses"].startswith("actions/cache/restore@"))
        self.assertEqual(cache["with"]["path"], "assets/shorts_voice")
        save = steps["Save the narrator's cached clips and the quota ledger"]
        self.assertTrue(save["uses"].startswith("actions/cache/save@"))
        self.assertEqual(save["if"], "always()", "what was synthesised is kept even when the run pauses")

    def test_facebook_render_steps_have_the_key_and_a_cache(self):
        steps = self.steps("facebook_autopost.yml")
        for name in ("Reels — render", "Manual post (text / photo / video / reel)"):
            with self.subTest(step=name):
                env = steps[name].get("env") or {}
                self.assertEqual(env.get("GEMINI_API_KEY"), "${{ secrets.GEMINI_API_KEY }}")
        cache = steps["Reels — restore the narrator's cached clips"]
        self.assertTrue(cache["uses"].startswith("actions/cache/restore@"))
        self.assertEqual(cache["with"]["path"], "assets/shorts_voice")
        names = list(steps)
        self.assertGreater(names.index("Reels — save the narrator's cached clips and the quota ledger"),
                           names.index("Manual post (text / photo / video / reel)"),
                           "the save sits below both render paths")

    def test_every_lane_shares_one_cache_prefix(self):
        """Shorts, Reels, Deep-Dive and the resumer restore the newest entry under one prefix
        and save their own — that is how the clips and the quota ledger travel between lanes."""
        yt = self.steps("youtube_scheduled.yml")["Restore the narrator's cached clips"]["with"]
        fb = self.steps("facebook_autopost.yml")["Reels — restore the narrator's cached clips"]["with"]
        dd = self.steps("deepdive.yml")["Restore the narrator's quota ledger"]["with"]
        rs = self.steps("narrator_resume.yml")["Restore the narrator's cached clips and the quota ledger"]["with"]
        for w in (yt, fb, dd, rs):
            self.assertEqual(w["restore-keys"], "shorts-voice-v2-")
            self.assertEqual(w["key"], "shorts-voice-v2-${{ github.run_id }}", "a fresh key per run → always saved")

    def test_voice_is_required_on_both_scheduled_lanes(self):
        yt = self.steps("youtube_scheduled.yml")["Generate today's Short"]
        fb = self.steps("facebook_autopost.yml")["Reels — render"]
        for step in (yt, fb):
            self.assertEqual(step["env"]["SHORTS_VOICE"], "${{ vars.SHORTS_VOICE || 'required' }}")
            self.assertIn('-eq 6', step["run"], "exit 6 = paused, handled by name")
            self.assertIn("paused=yes", step["run"])

    def test_a_paused_short_never_reaches_the_upload(self):
        steps = self.steps("youtube_scheduled.yml")
        for name in ("Duplicate guard (publish ledger)", "Upload to YouTube", "Commit the publish ledger"):
            self.assertIn("steps.short.outputs.paused != 'yes'", steps[name]["if"], name)
        summary = steps["Write the run summary"]["run"]
        self.assertIn("Paused — no voice, no Short", summary)
        self.assertIn("| Soundtrack |", summary)
        self.assertIn("| Narrator |", summary)

    def test_a_paused_reel_never_reaches_the_publish(self):
        steps = self.steps("facebook_autopost.yml")
        self.assertIn("steps.reel_render.outputs.paused != 'yes'", steps["Reels — publish"]["if"])
        record = steps["Record what this run did"]["run"]
        self.assertIn("paused — no voice, no Reel", record)
        manual = steps["Manual post (text / photo / video / reel)"]["run"]
        self.assertIn("-eq 6", manual)
        self.assertIn("SHORTS_VOICE=optional", manual, "the manual path tells a person how to ship music-only on purpose")


if __name__ == "__main__":
    unittest.main()
