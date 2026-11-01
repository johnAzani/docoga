"""Round 10 (18 Oct 2026, evening): rotation-day Instagram carousels and the numbered Shorts kicker.

Owner, fourth repeat of the same two asks: a Shorts thumbnail "no one can resist" and more
beautiful, better Facebook / Instagram / Threads / Telegram content. What landed:

* `social_card.rotation_slides` — the rotation copy's own structure becomes a carousel (hook,
  one numbered slide per marked line, close) so the days the brain is idle post Instagram's
  highest-save format too, not only the brain's Tue/Thu packs.
* `render(..., progress=(i, n))` — segmented progress bar + swipe cue on every slide but the last.
* `shorts_reel.series_kicker` — `DOCOGA · TENANT TIPS · No. N` from the YouTube ledger.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

import social_card  # noqa: E402
import shorts_reel  # noqa: E402
import generate_telegram_content as tg  # noqa: E402
from telegram_mdv2 import to_plain  # noqa: E402

RECEIPT = to_plain(tg.TEMPLATES["educational"][3])      # "Your rent receipt needs these 6 things."


class RotationSlides(unittest.TestCase):
    def test_numbered_list_becomes_hook_points_close(self):
        slides = social_card.rotation_slides(RECEIPT)
        self.assertEqual(len(slides), 8)                          # hook + 6 points + close
        labels = [s[0] for s in slides]
        self.assertEqual(labels[0], "swipe \u2192")
        self.assertEqual(labels[1:7], ["%d of 6" % i for i in range(1, 7)])
        self.assertTrue(labels[-1].startswith("free"))
        self.assertEqual([s[2] for s in slides[1:7]], [str(i) for i in range(1, 7)])
        self.assertIn("Date of payment", slides[1][1])
        self.assertIn("receipt", slides[-1][1].lower())            # the copy's own close, not the standing one

    def test_cross_lines_become_never_slides_and_options_keep_letters(self):
        slides = social_card.rotation_slides(to_plain(tg.TEMPLATES["promo"][4]))
        kinds = [s[0] for s in slides]
        self.assertIn("never", kinds)
        never = slides[kinds.index("never")][1]
        self.assertTrue(never.startswith("Never."))
        self.assertIn("\u274c", never)
        poll = social_card.rotation_slides(to_plain(tg.TEMPLATES["engagement"][0]))
        self.assertEqual([s[2] for s in poll[1:5]], ["A", "B", "C", "D"])

    def test_short_copy_is_not_a_carousel(self):
        self.assertEqual(social_card.rotation_slides("Pay without a receipt. Pay twice.\n\nSave this."), [])
        self.assertEqual(social_card.rotation_slides(""), [])

    def test_never_more_than_instagram_allows(self):
        many = "Ten things.\n\n" + "\n".join("%d. Point number %d" % (i, i) for i in range(1, 15)) + "\n\nWhich one?"
        slides = social_card.rotation_slides(many)
        self.assertLessEqual(len(slides), 10)
        self.assertEqual(slides[0][1].split("\n")[0], "Ten things.")

    def test_most_rotation_templates_qualify(self):
        total = sum(len(v) for v in tg.TEMPLATES.values())
        eligible = sum(1 for v in tg.TEMPLATES.values() for t in v if social_card.rotation_slides(to_plain(t)))
        self.assertGreaterEqual(eligible, total // 3)


class SlidesCommand(unittest.TestCase):
    def test_slides_fall_back_to_rotation_copy_when_no_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            blob = Path(tmp) / "threads.json"
            blob.write_text(json.dumps({"text": RECEIPT, "post_type": "educational"}), encoding="utf-8")
            out = Path(tmp) / "slide.jpg"
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = social_card.main(["--slides", "--brief", "1999-01-01", "--from-json", str(blob),
                                       "--out", str(out), "--base-url", "https://docoga.com.ng"])
            self.assertEqual(rc, 0)
            text = buf.getvalue()
            self.assertIn("CARD_SLIDES=8", text)
            self.assertIn("CARD_SLIDES_SOURCE=rotation", text)
            urls = [l for l in text.splitlines() if l.startswith("CARD_URLS=")][0].split("=", 1)[1].split()
            self.assertEqual(len(urls), 8)
            self.assertTrue(all((Path(tmp) / ("slide-%d.jpg" % i)).exists() for i in range(1, 9)))

    def test_manual_days_keep_the_single_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            blob = Path(tmp) / "threads.json"
            blob.write_text(json.dumps({"text": RECEIPT, "post_type": "manual"}), encoding="utf-8")
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                social_card.main(["--slides", "--brief", "1999-01-01", "--from-json", str(blob),
                                  "--out", str(Path(tmp) / "s.jpg")])
            self.assertIn("CARD_SLIDES=0", buf.getvalue())

    def test_progress_bar_marks_the_current_slide(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "p.jpg"
            social_card.render("Date of payment", str(out), kicker="2 of 6", layout="stat", big="2", progress=(2, 6))
            img = Image.open(out).convert("RGB")
            W, H = img.size
            # Scan the bottom 260 px for a row with exactly one bright run (the current segment).
            found = False
            for yy in range(H - 260, H - 10):
                row = [img.getpixel((x, yy)) for x in range(0, W, 4)]
                bright = [i for i, (r, g, b) in enumerate(row) if r > 200 and g > 200 and b > 200]
                if bright:
                    runs = 1 + sum(1 for a, b in zip(bright, bright[1:]) if b - a > 1)
                    if runs == 1 and 20 <= len(bright) <= 60:
                        found = True
                        break
            self.assertTrue(found, "no single white progress segment near the bottom edge")


class SeriesKicker(unittest.TestCase):
    def test_counts_distinct_published_shorts_plus_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "yt.json"
            ledger.write_text(json.dumps([
                {"video_id": "a", "state": "published"},
                {"video_id": "a", "state": "listed"},          # same video twice in the ledger
                {"video_id": "b", "state": "scheduled"},
                {"video_id": "c", "state": "deleted"},
                {"video_id": "", "state": "published"},
            ]), encoding="utf-8")
            self.assertEqual(shorts_reel.series_kicker(ledger=ledger, env={}), "DOCOGA \u00b7 TENANT TIPS \u00b7 No. 3")
            self.assertEqual(shorts_reel.series_kicker(ledger=ledger, env={"SHORTS_SERIES_NO": "off"}), shorts_reel.SERIES_KICKER)
            self.assertEqual(shorts_reel.series_kicker(ledger=ledger, env={"SHORTS_SERIES_NO": "41"}), "DOCOGA \u00b7 TENANT TIPS \u00b7 No. 41")
        self.assertEqual(shorts_reel.series_kicker(ledger="/nonexistent/yt.json", env={}), shorts_reel.SERIES_KICKER)

    def test_live_ledger_gives_a_number(self):
        self.assertRegex(shorts_reel.series_kicker(env={}), r"^DOCOGA \u00b7 TENANT TIPS \u00b7 No\. \d+$")

    def test_cover_kicker_carries_the_number(self):
        import short_cover
        topic = shorts_reel.topic_for(__import__("datetime").date(2026, 10, 19))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/_r10.mp4")
        kicker = short_cover.hook_parts(reel)[0]
        self.assertIn("No.", kicker)


class PhotoCover(unittest.TestCase):
    """1 Nov 2026: the carousel's first slide is the photograph, the hook is ≤8 words on it."""

    def _photo(self):
        from PIL import Image
        img = Image.new("RGB", (1600, 1200))
        px = img.load()
        for x in range(0, 1600, 8):
            for y in range(0, 1200, 8):
                for dx in range(8):
                    for dy in range(8):
                        px[x + dx, y + dy] = (180 + (x // 8) % 60, 120 + (y // 8) % 90, 60 + (x // 16) % 100)
        return img

    def test_the_hook_is_eight_words_or_fewer_and_prefers_the_question(self):
        ch = social_card.cover_hook
        self.assertEqual(ch("Did you know that in Cross River State, your landlord can only demand three months' rent "
                            "in advance? This law protects tenants from huge upfront demands. How many months' rent did you pay?"),
                         "How many months' rent did you pay?")
        self.assertEqual(ch("Pay without a receipt. Pay twice.\n\n\u2705 Date"), "Pay without a receipt. Pay twice.")
        clipped = ch("Your landlord cannot lock you out without a court order, even when the rent is late by a year.")
        self.assertTrue(clipped.endswith("\u2026") and not clipped.rstrip("\u2026").endswith((" a", " the", " without")), clipped)
        for text in [RECEIPT, "Did you know that in Lagos, a yearly tenant is owed six months' written notice before "
                              "any eviction can begin? Many landlords skip it."]:
            self.assertLessEqual(len(ch(text).split()), social_card.COVER_MAX_WORDS, ch(text))
        self.assertEqual(ch(""), "")

    def test_the_cover_is_a_photograph_with_the_hook_inside_the_frame(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "cover.jpg"
            r = social_card.render_cover(self._photo(), "No rent receipt in Kano? You could pay twice.", str(out),
                                         kicker="DocOga \u00b7 demand paper", progress=(1, 7))
            self.assertEqual((r["width"], r["height"]), (1080, 1350))
            self.assertLessEqual(r["lines"], 3)
            plan = social_card.LAST_COVER
            self.assertGreater(plan["rule_y"], 1350 * 0.40, "the hook sits in the lower half, on the scrim")
            img = Image.open(out).convert("RGB")
            top = img.crop((0, 200, 1080, 480)).resize((1, 1)).getpixel((0, 0))
            self.assertGreater(sum(top), 3 * 90, "the upper half is the photograph in its own colours, not navy")
            self.assertGreater(top[0], top[2], "the warm test photograph survives (no duotone on the cover)")
            self.assertLess(r["bytes"], 900 * 1024)
        with self.assertRaises(ValueError):
            social_card.render_cover(self._photo(), "   ", str(Path(tmp) / "x.jpg"))

    def test_the_carousel_puts_the_photograph_first_and_the_hook_slide_second(self):
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        import shot_match
        photo = self._photo()

        def fake_photo_for(text, hint=None, size=None, treat=None, **kw):
            return (treat or (lambda i, s: i))(photo, size), {"door": "test"}

        with tempfile.TemporaryDirectory() as tmp:
            blob = Path(tmp) / "threads.json"
            blob.write_text(json.dumps({"text": RECEIPT, "post_type": "educational"}), encoding="utf-8")
            for switch, want_cover, want_n in (("on", "photo", 9), ("off", "none", 8)):
                buf = io.StringIO()
                with mock.patch.object(shot_match, "photo_for", fake_photo_for), \
                        mock.patch.dict(os.environ, {"IG_PHOTO_COVER": switch}), redirect_stdout(buf):
                    rc = social_card.main(["--slides", "--brief", "1999-01-01", "--from-json", str(blob),
                                           "--out", str(Path(tmp) / ("%s-slide.jpg" % switch)), "--base-url", "https://docoga.com.ng"])
                self.assertEqual(rc, 0)
                text = buf.getvalue()
                self.assertIn("CARD_COVER=%s" % want_cover, text)
                self.assertIn("CARD_SLIDES=%d" % want_n, text)
            self.assertIn("CARD_SLIDE=1 ", text)
            from PIL import Image
            cover = Image.open(Path(tmp) / "on-slide-1.jpg").convert("RGB")
            second = Image.open(Path(tmp) / "on-slide-2.jpg").convert("RGB")
            c = cover.crop((0, 200, 1080, 480)).resize((1, 1)).getpixel((0, 0))
            s = second.crop((0, 200, 1080, 480)).resize((1, 1)).getpixel((0, 0))
            self.assertGreater(sum(c), sum(s) + 60, "slide 1 is the photograph; slide 2 is the navy-treated plate")

    def test_ten_slides_is_the_ceiling_even_with_the_cover(self):
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        import shot_match
        photo = self._photo()
        copy = "Your rent receipt needs these 9 things.\n\n" + "\n".join("%d. Item number %d on the receipt" % (i, i) for i in range(1, 10))
        with tempfile.TemporaryDirectory() as tmp:
            blob = Path(tmp) / "threads.json"
            blob.write_text(json.dumps({"text": copy, "post_type": "educational"}), encoding="utf-8")
            buf = io.StringIO()
            with mock.patch.object(shot_match, "photo_for", lambda text, hint=None, size=None, treat=None, **kw:
                                   ((treat or (lambda i, s: i))(photo, size), {})), redirect_stdout(buf):
                social_card.main(["--slides", "--brief", "1999-01-01", "--from-json", str(blob), "--out", str(Path(tmp) / "s.jpg")])
            self.assertIn("CARD_SLIDES=10", buf.getvalue())
            self.assertIn("CARD_COVER=photo", buf.getvalue())

    def test_no_photograph_means_the_carousel_it_always_was(self):
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as tmp:
            blob = Path(tmp) / "threads.json"
            blob.write_text(json.dumps({"text": RECEIPT, "post_type": "educational"}), encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                social_card.main(["--slides", "--brief", "1999-01-01", "--from-json", str(blob), "--out", str(Path(tmp) / "s.jpg")])
            self.assertIn("CARD_COVER=none", buf.getvalue())
            self.assertIn("CARD_SLIDES=8", buf.getvalue())


class Workflow(unittest.TestCase):
    def test_instagram_carousel_runs_every_day_from_rotation_copy(self):
        y = (ROOT / ".github/workflows/instagram_autopost.yml").read_text(encoding="utf-8")
        self.assertIn("IG_PHOTO_COVER: ${{ vars.IG_PHOTO_COVER }}", y)
        self.assertIn("CARD_COVER=", y)

    def test_instagram_carousel_runs_every_weekday_from_rotation_copy(self):
        y = (ROOT / ".github/workflows/instagram_autopost.yml").read_text(encoding="utf-8")
        self.assertIn('${IG_CAROUSEL_DAYS:-1,2,3,4,5,6,7}', y)       # every day since 1 Nov 2026
        self.assertIn('--slides --brief "$DAY" --from-json assets/threads/threads_content_latest.json', y)


if __name__ == "__main__":
    unittest.main()
