"""The static card's design system and the rotation copy it draws (18 Oct 2026).

The card shares the Short cover's language (docs/SHORT_COVER.md): headline on stepped yellow
slabs with a flat royal offset block, body lines with the brand's marks, the outlined chip, a
tonal glyph when there is no photograph — and the rotation templates are written in the shape
the card and the 2026 feed data want (a sub-50-character headline, structured lines, a question).
"""

import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
for p in (TOOLS, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import social_card  # noqa: E402
from telegram_mdv2 import to_plain, validate  # noqa: E402
import generate_telegram_content as tg  # noqa: E402
import generate_facebook_content as fb  # noqa: E402

FONTS_OK = social_card._font_path("Black") is not None and "Inter" in social_card._font_path("Black")


def _pixels(path):
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB")).astype(int)


def _mask(a, colour, tol=40):
    import numpy as np
    return np.abs(a - np.array(colour)).sum(axis=2) < tol


@unittest.skipUnless(FONTS_OK, "Inter is not installed — run tools/install_brand_fonts.sh")
class CardDesignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_short_headline_sits_on_yellow_slabs_inside_the_grid_square(self):
        r = social_card.render("Pay without a receipt? Pay twice.\n\nCash leaves no trail. Paper does.",
                               self.out / "a.jpg", kicker="DocOga · tenant tip")
        self.assertEqual(r["mode"], "slab")
        a = _pixels(self.out / "a.jpg")
        yellow = _mask(a, social_card.ACCENT)
        royal = _mask(a, social_card.PANEL, 30)
        self.assertGreater(int(yellow.sum()), 40000, "the slabs are there")
        self.assertGreater(int(royal.sum()), 3000, "the flat offset block is there")
        rows = yellow.any(axis=1).nonzero()[0]
        self.assertGreaterEqual(int(rows.min()), social_card.GRID_SAFE)
        self.assertLessEqual(int(rows.max()), social_card.CARD_H - social_card.GRID_SAFE)
        # Yellow once: the slab stack is one contiguous block (no second yellow element).
        gaps = [b - a for a, b in zip(rows[:-1], rows[1:]) if b - a > social_card.SLAB_GAP + 2]
        self.assertEqual(gaps, [], "yellow appears in more than one place")

    def test_the_slab_headline_out_weighs_the_body(self):
        r = social_card.render("5 lines every tenancy agreement must have.\n\n1. Names\n2. Address\n3. Rent and period\n4. Duration\n5. Notice",
                               self.out / "b.jpg", kicker="DocOga · know your rights")
        self.assertEqual(r["mode"], "slab")
        self.assertGreaterEqual(r["headline_size"], 1.6 * r["body_size"])
        self.assertGreaterEqual(r["body_size"], 40, "body type is readable on a phone")

    def test_a_long_headline_goes_white_and_the_body_is_never_lost(self):
        text = ("Most people sign a tenancy agreement in the agent's office in under a minute, then live "
                "under it for a year. Read it slowly before you sign. These four parts matter most.\n\n"
                "What would you have done differently?")
        r = social_card.render(text, self.out / "c.jpg", kicker="DocOga · tenant tip")
        self.assertEqual(r["mode"], "white")
        a = _pixels(self.out / "c.jpg")
        self.assertEqual(int(_mask(a, social_card.ACCENT).sum()), 0, "no stray yellow on a white-headline card")
        self.assertGreater(r["body_size"], 0)

    def test_the_marks_are_drawn_green_check_red_x_royal_numerals(self):
        text = "Before you pay, read these.\n\n\u2705 Rent and period\n\u2705 Notice\n\u274c \"Cash only, no receipt\"\n\n1. First"
        social_card.render(text, self.out / "d.jpg", kicker="DocOga")
        a = _pixels(self.out / "d.jpg")
        self.assertGreater(int(_mask(a, social_card.GREEN).sum()), 400)
        self.assertGreater(int(_mask(a, social_card.RED).sum()), 200)
        self.assertLess(int(_mask(a, social_card.RED).sum()), 0.004 * a.shape[0] * a.shape[1], "red is a mark, not a field")
        plain = social_card.render("Before you pay, read these.\n\nRent and period. Notice.", self.out / "e.jpg")
        b = _pixels(self.out / "e.jpg")
        self.assertEqual(int(_mask(b, social_card.GREEN).sum()) + int(_mask(b, social_card.RED).sum()), 0)
        self.assertEqual(plain["layout"], "poster")

    def test_structure_reads_markers_before_the_emoji_are_stripped(self):
        headline, body = social_card.structure(
            "Headline here\n\n\u2705 Yes line\n\u274c No line\nA) Option\n3. Third\n\u2022 Dot\nhttps://docoga.com.ng\n\U0001f449 Try it: https://docoga.com.ng")
        self.assertEqual(headline, "Headline here")
        kinds = [k for k, _, _ in body]
        self.assertEqual(kinds, ["check", "x", "option", "num", "bullet"])
        self.assertEqual(body[2][1], "A")
        self.assertEqual(body[3][1], "3")

    def test_a_stat_card_puts_the_figure_on_the_slab_and_the_headline_in_white(self):
        r = social_card.render("Save on legal fees.\n\nOne lawyer, one agreement, one invoice.", self.out / "f.jpg",
                               kicker="DocOga", layout="stat", big="\u20a650,000")
        self.assertEqual(r["mode"], "stat")
        a = _pixels(self.out / "f.jpg")
        self.assertGreater(int(_mask(a, social_card.ACCENT).sum()), 40000)

    def test_a_carousel_counter_sits_top_right_and_the_kicker_says_docoga(self):
        r = social_card.render("Seven lines of proof.", self.out / "g.jpg", kicker="2 of 6", footer="")
        self.assertIn(r["mode"], ("slab", "white"))
        a = _pixels(self.out / "g.jpg")
        top_right = a[150:260, 880:1000]
        self.assertGreater(int((top_right.sum(axis=2) > 300).sum()), 50, "the 2 / 6 counter is drawn top-right")

    def test_the_squint_test_at_grid_tile_size(self):
        import numpy as np
        from PIL import Image
        social_card.render("No receipt is not a favour. It is a risk.\n\nPaid cash with no paper? Today you have a debt with no proof.",
                           self.out / "h.jpg", kicker="DocOga · know your rights")
        with Image.open(self.out / "h.jpg") as im:
            tile = im.crop((0, social_card.GRID_SAFE, 1080, 1080 + social_card.GRID_SAFE)).resize((200, 200), Image.LANCZOS)
            a = np.asarray(tile).astype(int)
        yellow = _mask(a, social_card.ACCENT, 60).mean()
        self.assertGreater(float(yellow), 0.06, "the slabs are a real share of the grid tile (%.3f)" % float(yellow))

    def test_the_renderer_stays_flat_no_blur_gradient_or_tilt(self):
        src = (TOOLS / "social_card.py").read_text(encoding="utf-8")
        for banned in ("GaussianBlur", "ImageFilter", "linear_gradient", "rotate("):
            self.assertNotIn(banned, src)


class RotationCopyTests(unittest.TestCase):
    def test_every_template_has_a_sub_50_character_headline_and_valid_markdown(self):
        for post_type, templates in tg.TEMPLATES.items():
            self.assertGreaterEqual(len(templates), 4, post_type)
            for template in templates:
                self.assertEqual(validate(template), [], template[:60])
                plain = to_plain(template)
                headline = plain.split("\n\n")[0]
                self.assertLessEqual(len(headline), 50, headline)
                self.assertNotIn("\n", headline)
                self.assertRegex(plain.strip().split("\n")[-1], r"^https://docoga\.com\.ng", "the link is its own last line")

    def test_no_invented_customers_speak_for_the_brand(self):
        attribution = re.compile(r"\u2014\s*[A-Z][a-z]+,\s*(?:Lagos|Abuja|Port Harcourt|Estate Agent)")
        for templates in tg.TEMPLATES.values():
            for template in templates:
                self.assertIsNone(attribution.search(to_plain(template)), template[:80])
        for template in tg.TEMPLATES["testimonial_style"]:
            self.assertTrue(to_plain(template).startswith("Picture this:"), template[:60])
        self.assertEqual(social_card.KICKER_NAMES["testimonial_style"], "picture this")

    def test_the_legal_lines_name_their_section(self):
        joined = " ".join(to_plain(t) for ts in tg.TEMPLATES.values() for t in ts)
        self.assertIn("s.13(1)", joined)
        self.assertIn("s.5", joined)
        self.assertIn("s.4", joined)
        self.assertNotIn("14.9 million", joined, "no statistic this repo has not verified")

    def test_facebook_never_repeats_yesterday_and_threads_lunch_says_the_same_thing(self):
        import generate_threads_content as th
        start = date(2026, 10, 19)
        seen_repeat = False
        for n in range(90):
            day = start + timedelta(days=n)
            _, today = fb.pick(day)
            _, yesterday = fb.pick(day - timedelta(days=1))
            self.assertNotEqual(today, yesterday, day)
            if fb.raw_pick(day)[1] == fb.raw_pick(day - timedelta(days=1))[1]:
                seen_repeat = True
        self.assertTrue(seen_repeat, "the seeded rotation does repeat sometimes — that is what the guard is for")
        day = date(2026, 10, 20)
        with redirect_stdout(io.StringIO()):
            post_type, text, _, _ = th.build(day, None, "lunch")
        self.assertEqual(post_type, fb.pick(day)[0])
        self.assertTrue(text.startswith(to_plain(fb.pick(day)[1]).split("\n\n")[0]))

    def test_a_template_does_not_come_round_again_until_its_pool_is_spent(self):
        """21 Oct 2026: Instagram refuses an exact repeat of a caption already on the profile, so
        the rotation's fortnightly repeats left the feed silent behind green runs. Replaying the
        picks from the epoch, a template waits until every other one of its type has had a turn."""
        import generate_telegram_content as tg
        start = date(2026, 10, 1)
        last_seen = {}
        for n in range(120):
            day = start + timedelta(days=n)
            post_type, template = fb.pick(day)
            pool = tg.TEMPLATES[post_type]
            key = (post_type, template)
            if key in last_seen:
                picks_between = sum(1 for m in range(last_seen[key] + 1, n) if fb.pick(start + timedelta(days=m))[0] == post_type)
                self.assertGreaterEqual(picks_between, len(pool) - 1, (day, post_type))
            last_seen[key] = n
        # deterministic: the same day always gives the same words
        self.assertEqual(fb.pick(date(2026, 10, 27)), fb.pick(date(2026, 10, 27)))

    def test_the_instagram_caption_closes_by_asking_for_a_save_and_a_send(self):
        import generate_threads_content as th
        with redirect_stdout(io.StringIO()):
            content = th.generate(date(2026, 10, 21), write=False)
        self.assertTrue(content["ig_caption"].rstrip().endswith(th.IG_CLOSE))
        self.assertLessEqual(len(content["ig_caption"]), 2200)


if __name__ == "__main__":
    unittest.main()
