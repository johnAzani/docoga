"""Tests for the unattended Shorts content rotation and safety footer."""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = TOOLS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import generate_short_video as shorts  # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageStat  # noqa: E402

# Rendered frames are cached: each is 1080x1920 (~6 MB) and rendering is slow.
_RENDER_CACHE = {}


class DailyShortScheduleTests(unittest.TestCase):
    def test_topic_rotation_is_deterministic_and_covers_every_template(self):
        first_day = date(2026, 1, 1)
        titles = {
            shorts.script_for_date(first_day + timedelta(days=offset))["title"]
            for offset in range(len(shorts.VIDEO_SCRIPTS))
        }

        self.assertEqual(titles, {script["title"] for script in shorts.VIDEO_SCRIPTS})
        self.assertEqual(
            shorts.script_for_date(first_day),
            shorts.script_for_date(first_day),
        )

    def test_every_short_has_a_location_and_agreement_caveat(self):
        for script in shorts.VIDEO_SCRIPTS:
            with self.subTest(title=script["title"]):
                footer = script["slides"][-1]
                self.assertEqual(footer["text"], "GENERAL INFO ONLY")
                self.assertIn("Rules vary", footer["sub"])
                duration = sum(slide.get("duration", 3) for slide in script["slides"])
                self.assertGreaterEqual(duration, 20)
                self.assertLess(duration, 60)

    def test_templates_do_not_repeat_removed_unsupported_claims(self):
        all_copy = "\n".join(
            slide.get("text", "") + " " + slide.get("sub", "")
            for script in shorts.VIDEO_SCRIPTS
            for slide in script["slides"]
        ).lower()
        for unsupported_claim in ("80% of tenants", "minimum 6 months", "zero protection", "illegal!"):
            self.assertNotIn(unsupported_claim.lower(), all_copy)

    def test_all_slide_copy_fits_mobile_safe_width(self):
        draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        max_width = shorts.WIDTH - 2 * shorts.SAFE_MARGIN
        for script in shorts.VIDEO_SCRIPTS:
            for slide in script["slides"]:
                for field, size, min_size in (("text", 72, 32), ("sub", 42, 26)):
                    for line in slide.get(field, "").split("\n"):
                        font = shorts.fit_font(draw, line, size, max_width, min_size)
                        box = draw.textbbox((0, 0), line, font=font)
                        with self.subTest(title=script["title"], field=field, line=line):
                            self.assertLessEqual(box[2] - box[0], max_width)


def parse_github_output(text):
    """Read GITHUB_OUTPUT the way the runner does: `key=value` lines plus the
    `key<<DELIM … DELIM` heredoc form that multi-line values (the description,
    once it carries the parent Deep-Dive link) must use."""
    out, lines, i = {}, text.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if "<<" in line and "=" not in line.split("<<", 1)[0]:
            key, delim = line.split("<<", 1)
            body = []
            i += 1
            while i < len(lines) and lines[i] != delim:
                body.append(lines[i])
                i += 1
            out[key] = "\n".join(body)
        elif "=" in line:
            key, value = line.split("=", 1)
            out[key] = value
        i += 1
    return out


def render_slide(slide):
    """Render a slide once and reuse it — a full frame is 1080x1920 (~6 MB)."""
    key = (slide.get("text"), slide.get("sub"), slide.get("bg"), slide.get("color"))
    if key not in _RENDER_CACHE:
        _RENDER_CACHE[key] = shorts.create_slide_image(slide)
    return _RENDER_CACHE[key]


class LockedBrandRuleTests(unittest.TestCase):
    """The official logo is never stamped on video — owner direction 21 Sep 2026.

    docs/DESIGN_SYSTEM.md §1: "the logo is NOT stamped on social posts."
    docs/SESSION_CONTEXT.md: "NEVER stamp the logo on reels or videos. Logo
    goes on static images only (carousels, status posts). NEVER on video."

    These tests exist because the rule was broken: a previous revision of
    generate_short_video.py composited the official logo onto every slide,
    where it also collided with the CTA bar. Nothing tested it, so nothing
    caught it. The rule now has teeth.
    """

    def setUp(self):
        self.source = (SCRIPTS_DIR / "generate_short_video.py").read_text(encoding="utf-8")

    def test_video_module_never_reads_a_brand_logo_file(self):
        # No logo file may be named anywhere, comment or code.
        self.assertNotIn("official-logo", self.source)
        # And the sanctioned compositor must never be called from video code.
        self.assertNotIn("add_logo(", self.source)
        self.assertNotIn("LOGO_PATH", self.source)

    # The removed chip was a SOLID near-white rounded block ~281px wide with
    # rounded corners, sitting above/behind the CTA bar. Type glyphs put white
    # pixels down too, but only in thin strokes, so the discriminator is a long
    # contiguous run of near-white pixels — a solid block, not lettering.
    SOLID_RUN_PX = 150
    NEAR_WHITE = 240

    @staticmethod
    def _longest_bright_run(row_pixels):
        longest = run = 0
        for value in row_pixels:
            if value >= LockedBrandRuleTests.NEAR_WHITE:
                run += 1
                longest = max(longest, run)
            else:
                run = 0
        return longest

    def test_no_logo_chip_appears_in_the_cta_area_of_any_slide(self):
        for script in shorts.VIDEO_SCRIPTS:
            for slide in script["slides"]:
                frame = render_slide(slide)
                # The band the old chip occupied, stopping at the CTA bar top.
                band = frame.crop(
                    (0, shorts.HEIGHT - shorts.CTA_BAR_H - 300, shorts.WIDTH, shorts.HEIGHT - shorts.CTA_BAR_H)
                ).convert("L")
                widest = 0
                for y in range(0, band.height, 8):
                    run = self._longest_bright_run(
                        [band.getpixel((x, y)) for x in range(band.width)]
                    )
                    widest = max(widest, run)
                with self.subTest(title=script["title"], text=slide["text"]):
                    self.assertLess(
                        widest,
                        self.SOLID_RUN_PX,
                        "solid near-white block above the CTA bar — logo chip regression?",
                    )

    def test_frames_do_not_depend_on_the_brand_directory(self):
        """No frame may read brand/ — the logo files must be irrelevant.

        Film grain is random per render, so identical layouts differ by ~2.5
        grey levels on average. A logo chip would move whole regions by 100+,
        so a small tolerance separates "same layout" from "logo came back".
        """
        slides = [script["slides"][0] for script in shorts.VIDEO_SCRIPTS]
        before = [shorts.create_slide_image(slide) for slide in slides]

        with patch.object(shorts, "BRAND_DIR", Path("/nonexistent-brand-dir")):
            after = [shorts.create_slide_image(slide) for slide in slides]

        for slide, img_a, img_b in zip(slides, before, after):
            difference = ImageChops.difference(img_a, img_b)
            mean_delta = sum(ImageStat.Stat(difference).mean) / 3
            with self.subTest(text=slide["text"]):
                self.assertLess(
                    mean_delta,
                    10,
                    f"frame changed when brand/ was absent ({mean_delta:.1f}) — it reads a logo file",
                )

        # The sample really is a spread of different layouts, not one slide twice.
        signature = {img.convert("L").resize((16, 16)).tobytes() for img in before}
        self.assertEqual(len(signature), len(before))


class BrandTextureTests(unittest.TestCase):
    """BRAND_STYLE.md §3: film grain is 'always present' on every finished piece."""

    def test_film_grain_is_present_and_on_brand(self):
        slide = shorts.VIDEO_SCRIPTS[0]["slides"][1]
        frame = render_slide(slide)

        # Sample a flat background region well clear of type.
        region = frame.convert("L").crop((100, 200, 500, 500))
        pixels = list(region.getdata())
        mean = sum(pixels) / len(pixels)
        spread = max(pixels) - min(pixels)

        self.assertGreater(spread, 1, "frame is flat — film grain is missing")
        # σ≈2.2 grain stays tightly around the background value.
        self.assertLess(spread, 40, "grain is far too strong for σ≈2.2")
        self.assertGreater(mean, 5)

    def test_grain_is_applied_to_the_real_dark_background(self):
        """DARK slides (10,15,30) must carry grain too, not only the navy ones."""
        dark_slides = [s for s in shorts.VIDEO_SCRIPTS[0]["slides"] if s["bg"] == shorts.DARK]
        self.assertTrue(dark_slides, "expected at least one DARK slide in the rotation")
        frame = render_slide(dark_slides[0])
        region = frame.convert("L").crop((200, 250, 880, 450))
        pixels = list(region.getdata())
        self.assertGreater(max(pixels) - min(pixels), 1, "no grain on a DARK slide")


class LayoutTests(unittest.TestCase):
    def test_type_block_sits_in_the_upper_content_area(self):
        """Type must be centred above the CTA bar, never behind it."""
        for script in shorts.VIDEO_SCRIPTS:
            for slide in script["slides"]:
                frame = render_slide(slide)
                content = frame.crop((0, 0, shorts.WIDTH, shorts.HEIGHT - shorts.CTA_BAR_H))
                # Ignore grain: look for pixels clearly brighter than the bg.
                grey = content.convert("L").point(lambda v: 255 if v > 120 else 0)
                bbox = grey.getbbox()
                with self.subTest(title=script["title"], text=slide["text"]):
                    self.assertIsNotNone(bbox, "slide rendered no visible type")
                    self.assertGreaterEqual(bbox[1], shorts.SAFE_MARGIN)
                    self.assertLessEqual(bbox[3], shorts.HEIGHT - shorts.CTA_BAR_H)


class DailyShortOutputTests(unittest.TestCase):
    """`youtube_short_daily.py` feeds the scheduled job — and the ledger.

    Every value the workflow reads comes from GITHUB_OUTPUT. A missing key
    becomes an empty string in the workflow, which is silent: the upload
    would still run, but the ledger entry would be blank. These tests pin the
    contract.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output_file = Path(self.tmp.name) / "github_output"
        self.output_file.write_text("", encoding="utf-8")
        self.video = Path(self.tmp.name) / "docoga_short_20260101.mp4"
        self.video.write_bytes(b"0" * 20_000)

    def _run_daily(self):
        import youtube_short_daily as daily

        # The lane renders through the MotionStudio bridge (tools/shorts_reel.py), never
        # the retired card renderer in this module — so that is what gets mocked. A real
        # render is ~3 minutes of CPU and belongs in the lane, not in a unit test.
        # DOCOGA_FRESH=off: these tests pin the output contract of a *rendered* day. With the
        # real ledgers, the whole rotation ages inside FRESH_DAYS by late October and the lane
        # rightly pauses (no GEMINI key here) — a different contract, pinned in test_fresh.
        with patch.object(daily.shorts_reel, "render_topic", return_value=self.video):
            with patch.dict(os.environ, {"GITHUB_OUTPUT": str(self.output_file), "DOCOGA_FRESH": "off"}):
                daily.main()
        return parse_github_output(self.output_file.read_text(encoding="utf-8"))

    def test_every_value_the_scheduled_workflow_reads_is_written(self):
        outputs = self._run_daily()
        for key in ("video_path", "title", "topic", "description", "tags"):
            self.assertIn(key, outputs, "the workflow reads this from GITHUB_OUTPUT")
            self.assertTrue(outputs[key].strip(), "%s must never be empty" % key)

    def test_title_carries_the_shorts_suffix_and_topic_does_not(self):
        # Deliberately does NOT assert a fixed topic string. The topic is chosen
        # by a date-seeded rotation, so any hardcoded value is a time bomb: it
        # passes only on the days the rotation happens to land on it. This test
        # used to hardcode "Keep a Rent Paper Trail" and broke CI on 2026-10-09
        # when the rotation moved to "Before You Pay an Agent".
        #
        # The mock in _run_daily() only stands in for the render; the topic is
        # whatever the rotation says today, which is exactly why no fixed string
        # can be asserted here.
        outputs = self._run_daily()
        self.assertTrue(outputs["title"].endswith("#Shorts"))
        # The test name promises this; the original never actually checked it.
        self.assertNotIn("#Shorts", outputs["topic"])
        self.assertTrue(outputs["topic"].strip(), "topic must never be empty")
        # 18 Oct 2026: the title leads with the searchable subject and keeps the hook after it
        # ("Rent receipt in Nigeria: pay without a receipt, pay twice #Shorts"), so it is no
        # longer the topic verbatim — but the topic's first sentence is always in it.
        hook = outputs["topic"].split(". ")[0].rstrip(".").lower()
        self.assertIn(hook, outputs["title"].lower())
        self.assertLessEqual(len(outputs["title"]), 100)

    def test_description_points_at_docoga_and_disclaims_legal_advice(self):
        outputs = self._run_daily()
        self.assertIn("https://docoga.com.ng", outputs["description"])
        self.assertIn("not legal advice", outputs["description"].lower())

    def test_the_lane_renders_with_motionstudio_not_the_retired_card_renderer(self):
        """Owner direction 14 Oct 2026 ("I want my quality shorts back"): the Short
        that reaches YouTube is a MotionStudio render. The lane may import this
        module's *words* through the bridge, but never its `generate_video`."""
        source = (SCRIPTS_DIR / "youtube_short_daily.py").read_text(encoding="utf-8")
        self.assertIn("import shorts_reel", source)
        self.assertIn("shorts_reel.render_topic(", source)
        self.assertNotIn("generate_video(", source)
        self.assertNotIn("import generate_short_video", source)


if __name__ == "__main__":
    unittest.main()
