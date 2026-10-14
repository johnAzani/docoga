"""The Deep-Dive long-form lane: episode contract, renderer brand rules, publish wiring.

No audio, no Gemini, no frame rendering here. The expensive stages are exercised
by the workflow; what a unit test can pin is the contract between the writer and
the renderer (every trigger phrase is spoken, in order), the brand rules (palette
from the engine, Inter, disclaimer on the end card), the plates every beat points
at, and the workflow's bank/publish wiring.
"""

import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

try:
    import deepdive as dd  # noqa: E402
    import motionstudio as ms  # noqa: E402
    ENGINE_OK = True
except ImportError as exc:  # pragma: no cover — PIL/numpy absent
    ENGINE_OK = False
    ENGINE_ERR = str(exc)

EPISODE_DIRS = sorted(p for p in (ROOT / "episodes").iterdir()
                      if p.is_dir() and (p / "episode.json").is_file())
WORKFLOW = ROOT / ".github" / "workflows" / "deepdive.yml"


def episodes():
    return [dd.Episode(p.name) for p in EPISODE_DIRS]


@unittest.skipUnless(ENGINE_OK, "deepdive engine not importable (PIL/numpy)")
class EpisodeContractTests(unittest.TestCase):
    def test_there_is_at_least_one_episode(self):
        self.assertTrue(EPISODE_DIRS, "episodes/<id>/episode.json + script.txt")

    def test_every_trigger_phrase_is_spoken_in_order(self):
        for ep in episodes():
            with self.subTest(episode=ep.id):
                self.assertEqual(dd.check_triggers(ep, verbose=False), [])

    def test_nine_sections_and_a_closing_endcard(self):
        for ep in episodes():
            with self.subTest(episode=ep.id):
                self.assertEqual(ep.n, 9, "the Deep-Dive grammar is nine scenes (BRAND_STYLE)")
                beats = ep.beats()
                self.assertTrue(beats[-1]["endcard"], "the last beat is the DOCOGA end card")
                self.assertEqual({b["sec"] for b in beats}, set(range(1, 10)), "every section has beats")
                for s in range(1, 10):
                    first = ep.beats(s)[0]
                    self.assertIsNone(first["trig"], "section %d must open with an untriggered title beat" % s)

    def test_script_length_is_a_deep_dive_not_a_short(self):
        for ep in episodes():
            words = sum(len(dd.norm_tokens(t)) for t in ep.sections)
            with self.subTest(episode=ep.id, words=words):
                self.assertGreaterEqual(words, 900)    # ≈ 6 min at narration pace
                self.assertLessEqual(words, 2400)      # ≈ 16 min

    def test_every_plate_a_beat_names_exists_or_is_aliased(self):
        aliases_path = dd.ASSETS / "aliases.json"
        aliases = json.loads(aliases_path.read_text(encoding="utf-8")) if aliases_path.is_file() else {}
        for ep in episodes():
            for b in ep.beats():
                if not b["img"]:
                    continue
                name = b["img"]
                target = name if (dd.ASSETS / ("%s.jpg" % name)).is_file() else aliases.get(name)
                with self.subTest(episode=ep.id, plate=name):
                    self.assertTrue(target and (dd.ASSETS / ("%s.jpg" % target)).is_file(),
                                    "plate '%s' missing and not aliased" % name)
            cover_img = ep.meta["cover"].get("img", "kiosk")
            self.assertTrue((dd.ASSETS / ("%s.jpg" % cover_img)).is_file()
                            or cover_img in aliases, "cover plate missing")

    def test_plates_are_committed_at_a_sane_size(self):
        for p in dd.ASSETS.glob("*.jpg"):
            with self.subTest(plate=p.name):
                self.assertLess(p.stat().st_size, 600_000, "downscale to ≤1600 px, q≈86 before committing")

    def test_youtube_metadata_carries_the_disclaimer_and_the_link(self):
        for ep in episodes():
            yt = ep.meta["youtube"]
            with self.subTest(episode=ep.id):
                self.assertIn("docoga.com.ng", yt["description"])
                self.assertIn("not legal advice", yt["description"].lower())
                self.assertLessEqual(len(yt["title"]), 100, "YouTube's title limit")
                self.assertIn("GENERAL INFORMATION", ep.meta.get("disclaimer", "GENERAL INFORMATION"))

    def test_script_avoids_the_claims_the_shorts_lane_already_banned(self):
        banned = ("80% of tenants", "minimum 6 months", "zero protection", "illegal!")
        for ep in episodes():
            text = " ".join(ep.sections).lower()
            for claim in banned:
                self.assertNotIn(claim.lower(), text)

    def test_synthetic_timings_cover_every_word_and_are_flagged(self):
        ep = episodes()[0]
        d = dd.synthetic_words(ep)
        self.assertTrue(d["synthetic"])
        self.assertEqual(len(d["words"]), sum(len(dd.norm_tokens(t)) for t in ep.sections))
        self.assertEqual(len(d["sections"]), ep.n)
        self.assertTrue(all("d" in w for w in d["words"]), "captions need the display token")

    def test_display_and_match_tokens_stay_in_step(self):
        for ep in episodes():
            for text in ep.sections:
                self.assertEqual([w.lower() for w in dd.display_tokens(text)], dd.norm_tokens(text))


@unittest.skipUnless(ENGINE_OK, "deepdive engine not importable (PIL/numpy)")
class AlignmentTests(unittest.TestCase):
    def test_align_section_maps_heard_words_and_interpolates_the_rest(self):
        text = "Two hundred thousand naira. That is the caution fee."
        rec = [("two", 0.0, 0.3), ("hundred", 0.3, 0.7), ("thousand", 0.7, 1.2), ("naira", 1.2, 1.6),
               ("that", 1.9, 2.1), ("caution", 2.6, 3.0), ("fee", 3.0, 3.3)]
        words = dd.align_section(1, text, rec)
        self.assertEqual([w["w"] for w in words], dd.norm_tokens(text))
        by = {w["w"]: w for w in words}
        self.assertEqual(by["two"]["t0"], 0.0)
        self.assertEqual(by["fee"]["t1"], 3.3)
        # "is the" were not heard: they are spread between "that" and "caution"
        self.assertGreater(by["is"]["t0"], by["that"]["t1"] - 0.01)
        self.assertLess(by["the"]["t1"], by["caution"]["t0"] + 0.01)

    def test_chunk_verdict_catches_a_leaked_instruction(self):
        ep = episodes()[0]
        leaked = [("narrate", 0, 0.4), ("this", 0.4, 0.6), ("two", 1.0, 1.2), ("hundred", 1.2, 1.5)]
        ok, why = dd.chunk_verdict(ep, 1, leaked)
        self.assertFalse(ok)
        self.assertIn("preamble", why)
        clean = [("two", 0.0, 0.3), ("hundred", 0.3, 0.6), ("thousand", 0.6, 1.0)]
        self.assertTrue(dd.chunk_verdict(ep, 1, clean)[0])

    def test_quota_retry_seconds_are_read_from_the_429_body(self):
        self.assertEqual(dd.parse_retry_seconds('{"error":{"message":"Please retry in 1832.5s."}}'), 1832.5)
        self.assertEqual(dd.parse_retry_seconds('"retryDelay": "42s"'), 42.0)
        self.assertIsNone(dd.parse_retry_seconds("nothing useful"))


@unittest.skipUnless(ENGINE_OK, "deepdive engine not importable (PIL/numpy)")
class BrandRuleTests(unittest.TestCase):
    def test_the_engine_takes_its_palette_and_type_from_motionstudio(self):
        src = (TOOLS_DIR / "deepdive.py").read_text(encoding="utf-8")
        self.assertIn("import motionstudio as ms", src)
        self.assertEqual((dd.NAVY, dd.YELLOW, dd.WHITE), (ms.NAVY, ms.YELLOW, ms.WHITE))
        self.assertIn("ms.F.format(weight)", src, "Inter resolved by the engine")
        self.assertNotIn("DejaVu", src)
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{6}\b", src.split('"""', 2)[2]))

    def test_beats_only_use_palette_accents(self):
        palette = {ms.NAVY, ms.NAVY2, ms.PANEL, ms.WHITE, ms.MUTED, ms.FAINT, ms.BLUE, ms.YELLOW, ms.RED, ms.GREEN}
        for ep in episodes():
            for b in ep.beats():
                if b.get("accent"):
                    self.assertIn(tuple(b["accent"]), palette)

    def test_endcard_carries_url_and_disclaimer(self):
        src = (TOOLS_DIR / "deepdive.py").read_text(encoding="utf-8")
        body = src.split("def endcard_layer", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("docoga.com.ng", body)
        self.assertIn("disclaimer", body)
        self.assertIn("NOT LEGAL ADVICE", body)

    def test_master_refuses_synthetic_timings_without_the_override(self):
        src = (TOOLS_DIR / "deepdive.py").read_text(encoding="utf-8")
        body = src.split("def stage_master", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('d.get("synthetic") and not args.allow_synthetic', body)


class ThumbnailTests(unittest.TestCase):
    def test_a_403_is_explained_not_raised(self):
        import yt_thumbnail

        class R:
            status_code = 403
            text = '{"error":{"errors":[{"reason":"forbidden"}]}}'

        class FakeHttp:
            token = "t"

            def request(self, *a, **k):
                return R()

        img = ROOT / "episodes" / "assets" / "kiosk.jpg"
        with patch.object(yt_thumbnail.yt_publish, "authorize", return_value=(FakeHttp(), {})):
            ok, msg = yt_thumbnail.set_thumbnail("abc", img)
        self.assertFalse(ok)
        self.assertIn("verified channel", msg)

    def test_a_missing_file_never_calls_youtube(self):
        import yt_thumbnail
        ok, msg = yt_thumbnail.set_thumbnail("abc", "/nonexistent.jpg")
        self.assertFalse(ok)
        self.assertIn("missing", msg)


class WorkflowWiringTests(unittest.TestCase):
    def setUp(self):
        self.src = WORKFLOW.read_text(encoding="utf-8")

    def test_every_expensive_intermediate_is_banked_on_a_release(self):
        self.assertIn("gh release upload \"$RELEASE_TAG\" \"/tmp/$EPISODE-voice.tar.gz\"", self.src)
        self.assertIn("$EPISODE-episode.mp4", self.src)
        self.assertIn("gh release download \"$RELEASE_TAG\"", self.src)

    def test_quota_exhaustion_is_named_and_banked_not_silent(self):
        self.assertIn('"$code" -eq 5', self.src)
        self.assertIn("Bank the voice on the release", self.src)
        self.assertIn("if: always()", self.src.split("Bank the voice on the release", 1)[1][:200])

    def test_render_refuses_synthetic_timings(self):
        self.assertIn("Synthetic timings", self.src)

    def test_publish_uses_its_own_ledger_and_the_shared_uploader(self):
        self.assertIn("--ledger logs/youtube_longform.json check", self.src)
        self.assertIn("--ledger logs/youtube_longform.json record", self.src)
        self.assertIn("tools/yt_publish.py --video", self.src)
        self.assertIn("tools/yt_thumbnail.py", self.src)
        self.assertIn("continue-on-error: true", self.src.split("Set the thumbnail", 1)[1][:200])

    def test_default_privacy_is_not_public(self):
        import yaml
        wf = yaml.safe_load(self.src)
        priv = wf[True]["workflow_dispatch"]["inputs"]["privacy"] if True in wf else \
            wf["on"]["workflow_dispatch"]["inputs"]["privacy"]
        self.assertEqual(priv["default"], "unlisted", "a long-form goes public only when the owner says so")

    def test_scenes_render_as_a_nine_way_matrix(self):
        self.assertIn("scene: [1, 2, 3, 4, 5, 6, 7, 8, 9]", self.src)


if __name__ == "__main__":
    unittest.main()


# ───────────────────────── the sound kit and the free-plan resilience ─────────────────────────
@unittest.skipUnless(ENGINE_OK, "deepdive engine not importable (PIL/numpy)")
class SoundKitTests(unittest.TestCase):
    """Synthesized bed + SFX, cued from the beats. Nothing is downloaded; nothing is licensed."""

    def setUp(self):
        import soundkit
        self.sk = soundkit

    def test_every_effect_synthesizes_clean_and_peak_normalised(self):
        import numpy as np
        rng = np.random.default_rng(1)
        for kind in ("riser", "hit", "whoosh", "tick", "stinger"):
            y = self.sk.sfx(kind, rng)
            with self.subTest(kind=kind):
                self.assertTrue(np.all(np.isfinite(y)))
                self.assertAlmostEqual(float(np.max(np.abs(y))), 1.0, places=3)
                self.assertEqual(y.dtype, np.float32)

    def test_the_kit_is_deterministic(self):
        import numpy as np
        a = self.sk.sfx("whoosh", np.random.default_rng(7))
        b = self.sk.sfx("whoosh", np.random.default_rng(7))
        self.assertTrue(np.array_equal(a, b), "same seed, same sound, same video on every render")

    def test_bed_changes_chord_per_section_and_never_clips(self):
        import numpy as np
        y = self.sk.bed(12.0, [0.0, 4.0, 8.0], 72, 7)
        self.assertEqual(len(y), 12 * self.sk.SR)
        self.assertLessEqual(float(np.max(np.abs(y))), 1.0)
        # spectral centroid differs between the first and second chord (F below A)
        def centroid(seg):
            spec = np.abs(np.fft.rfft(seg)); f = np.fft.rfftfreq(len(seg), 1 / self.sk.SR)
            return float((spec * f).sum() / spec.sum())
        self.assertNotAlmostEqual(centroid(y[int(1 * self.sk.SR):int(3 * self.sk.SR)]),
                                  centroid(y[int(5 * self.sk.SR):int(7 * self.sk.SR)]), delta=3.0)

    def test_cue_sheet_puts_a_hit_on_every_title_a_riser_before_it_and_a_stinger_on_the_card(self):
        cfg = dict(self.sk.DEFAULTS)
        b1 = {"head": "ONE", "endcard": False}; b2 = {"head": "TWO", "endcard": False}
        b3 = {"head": "THREE", "endcard": False, "rows": ["a", "b"]}; card = {"head": "END", "endcard": True}
        spans = [(1, b1, 0.0), (1, b2, 5.0), (2, b3, 30.0), (2, card, 40.0)]
        cues = self.sk.cue_sheet(spans, {id(b3): [31.0, None, 33.0]}, [0.0, 30.0], 45.0, cfg)
        kinds = [(c["t"], c["kind"]) for c in cues]
        self.assertEqual(kinds, [(0.0, "hit"), (4.92, "whoosh"), (28.8, "riser"), (30.0, "hit"),
                                 (31.0, "tick"), (33.0, "tick"), (40.0, "stinger")])
        self.assertTrue(all(c["t"] == round(c["t"], 3) for c in cues), "millisecond precision, no drift")
        self.assertTrue(all(c["db"] <= -13 for c in cues), "nothing in the kit is louder than the voice")

    def test_no_riser_when_the_episode_opens_cold(self):
        cfg = dict(self.sk.DEFAULTS)
        cues = self.sk.cue_sheet([(1, {"head": "A", "endcard": False}, 0.4)], {}, [0.0], 10.0, cfg)
        self.assertEqual([c["kind"] for c in cues], ["hit"])

    def test_the_sheet_follows_the_renderer_timings(self):
        """plan_cues and render_scene share scene_timing — one source of truth for picture + sound."""
        ep = episodes()[0]
        d = dd.synthetic_words(ep, [20.0] * ep.n)
        cues, cfg, starts = dd.plan_cues(ep, d)
        self.assertEqual(starts, [s["start"] for s in d["sections"]])
        hits = [c for c in cues if c["kind"] == "hit"]
        self.assertEqual([h["t"] for h in hits], [round(s, 3) for s in starts], "a hit on every section title")
        self.assertEqual(sum(1 for c in cues if c["kind"] == "stinger"), 1)
        self.assertEqual(sum(1 for c in cues if c["kind"] == "tick"),
                         sum(len(b["rows"]) for b in ep.beats()), "one tick per numbered row")

    def test_speech_mask_ducks_under_speech_and_releases_in_gaps(self):
        import numpy as np
        sr = self.sk.SR
        v = np.zeros(6 * sr, dtype=np.float32)
        v[1 * sr:3 * sr] = np.random.default_rng(0).standard_normal(2 * sr).astype(np.float32) * 0.2
        mask, gate = self.sk.speech_mask(v, 0.1, 0.5)
        self.assertLess(float(mask[int(0.5 * sr)]), 0.05)
        self.assertGreater(float(mask[int(2.5 * sr)]), 0.95)
        self.assertLess(float(mask[int(5.5 * sr)]), 0.05)

    def test_qa_threshold_is_the_one_the_mixer_defaults_clear(self):
        self.assertGreaterEqual(-self.sk.DEFAULTS["bed_speech_db"], dd.MIN_BED_SEPARATION_DB + 6,
                                "defaults must clear the QA gate with margin, or every master fails")

    def test_episode_audio_plan_is_explicit_and_quiet(self):
        for ep in episodes():
            a = ep.meta.get("audio", {})
            with self.subTest(episode=ep.id):
                self.assertIn("bed", a, "the sound plan lives in episode.json, not in someone's head")
                self.assertLessEqual(a.get("bed_speech_db", -27), -24)
                self.assertLessEqual(a.get("sfx_db", -16), -12)

    def test_master_uses_the_kit_and_qa_reads_the_report(self):
        src = (TOOLS_DIR / "deepdive.py").read_text(encoding="utf-8")
        self.assertIn("soundkit.render_mix", src)
        self.assertIn("mix_report.json", src.split("def stage_qa", 1)[1])
        self.assertIn("bed_separation_db", src.split("def stage_qa", 1)[1])


class FreePlanResilienceTests(unittest.TestCase):
    def setUp(self):
        self.src = WORKFLOW.read_text(encoding="utf-8")

    def test_a_nightly_tick_resumes_the_queue(self):
        import yaml
        wf = yaml.safe_load(self.src)
        on = wf[True] if True in wf else wf["on"]
        self.assertEqual(on["schedule"][0]["cron"], "0 2 * * *", "03:00 WAT")
        self.assertIn("deepdive_queue.py next", self.src)

    def test_quota_is_a_pause_not_a_failure(self):
        voice = self.src.split("  voice:", 1)[1].split("\n  render:", 1)[0]
        self.assertIn('"$code" -eq 5', voice)
        self.assertIn("complete=false", voice)
        self.assertIn("steps.tts.outputs.code != '0' && steps.tts.outputs.code != '5'", voice,
                      "only a non-quota exit turns the job red")
        self.assertIn("--max-requests 12", voice, "a hard cap per run, whatever the key's plan")

    def test_nothing_banked_is_redone(self):
        self.assertIn("has_master != 'true'", self.src, "a banked master skips voice and render")
        self.assertIn("$EPISODE-status.json", self.src)

    def test_concurrency_serialises_nightly_and_manual_runs(self):
        self.assertIn("group: deepdive\n", self.src)

    def test_engine_caps_requests_inside_the_retry_loop(self):
        src = (TOOLS_DIR / "deepdive.py").read_text(encoding="utf-8")
        tts = src.split("def stage_tts", 1)[1].split("\ndef ", 1)[0]
        self.assertEqual(tts.count("requests_made >= args.max_requests"), 2,
                         "the cap is checked before every request, not only per chunk")
        self.assertIn('default=12', src.split('"--max-requests"', 1)[1][:80])

    def test_queue_tool_skips_published_titles(self):
        import tempfile, json as _json
        import deepdive_queue as q
        with tempfile.TemporaryDirectory() as td:
            queue = Path(td) / "queue.json"; ledger = Path(td) / "ledger.json"
            queue.write_text(_json.dumps({"queue": ["dd2", "nope"]}), encoding="utf-8")
            title = _json.loads((ROOT / "episodes" / "dd2" / "episode.json").read_text(encoding="utf-8"))["youtube"]["title"]
            ledger.write_text("[]", encoding="utf-8")
            self.assertEqual([r[1] for r in q.entries(queue, ledger)], ["pending", "missing"])
            ledger.write_text(_json.dumps([{"title": title}]), encoding="utf-8")
            self.assertEqual(q.entries(queue, ledger)[0][1], "published")

    def test_dd2_is_queued(self):
        import json as _json
        self.assertIn("dd2", _json.loads((ROOT / "episodes" / "queue.json").read_text(encoding="utf-8"))["queue"])
