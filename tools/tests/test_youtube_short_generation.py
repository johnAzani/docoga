"""Tests for the unattended Shorts content rotation and safety footer."""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = TOOLS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import generate_short_video as shorts  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402


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
        max_width = shorts.WIDTH - 120
        for script in shorts.VIDEO_SCRIPTS:
            for slide in script["slides"]:
                for field, size, min_size in (("text", 72, 32), ("sub", 42, 26)):
                    for line in slide.get(field, "").split("\n"):
                        font = shorts.fit_font(draw, line, size, max_width, min_size)
                        box = draw.textbbox((0, 0), line, font=font)
                        with self.subTest(title=script["title"], field=field, line=line):
                            self.assertLessEqual(box[2] - box[0], max_width)


if __name__ == "__main__":
    unittest.main()
