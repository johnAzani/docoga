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
