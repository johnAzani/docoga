"""Round 9 (18 Oct 2026, evening): the live card's lessons and the content levers.

The first live card read "PIDGIN" as its kicker; the engagement days asked A)–D) questions with
no poll to tap; Threads had posted words-only for two days; the Short's YouTube title echoed its
cover. Each has a test here.
"""

import io
import sys
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
for p in (TOOLS, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import social_card  # noqa: E402
import generate_telegram_content as tg  # noqa: E402
import generate_short_video as words  # noqa: E402
from telegram_mdv2 import to_plain  # noqa: E402


class KickerAndWrapTests(unittest.TestCase):
    def test_a_bare_post_type_key_becomes_the_brands_phrase(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            seen = {}
            real = social_card.render

            def spy(text, out, **kw):
                seen.update(kw)
                return real(text, out, **kw)
            with mock.patch.object(social_card, "render", spy), redirect_stdout(io.StringIO()):
                social_card.main(["--text", "Oga, no pay rent without receipt.\n\nPaper first.", "--kicker", "pidgin",
                                  "--out", str(Path(d) / "k.jpg")])
            self.assertEqual(seen["kicker"], "DocOga · oya, make we talk")
            with mock.patch.object(social_card, "render", spy), redirect_stdout(io.StringIO()):
                social_card.main(["--text", "x\n\ny", "--kicker", "DocOga · custom", "--out", str(Path(d) / "k2.jpg")])
            self.assertEqual(seen["kicker"], "DocOga · custom", "a phrase passes through untouched")

    def test_slab_lines_are_balanced_not_greedy(self):
        from PIL import Image, ImageDraw
        if not (social_card._font_path("Black") or "").endswith("Inter-Black.ttf") and "Inter" not in (social_card._font_path("Black") or ""):
            self.skipTest("Inter is not installed")
        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        font, _ = social_card.load_font("Black", 100)
        lines = social_card.balanced(draw, "No receipt is not a favour. It is a risk.", font, 820, 3)
        self.assertEqual(len(lines), 3)
        widths = [draw.textlength(ln, font=font) for ln in lines]
        greedy = social_card.wrap(draw, "No receipt is not a favour. It is a risk.", font, 820)
        gw = [draw.textlength(ln, font=font) for ln in greedy]
        self.assertLessEqual(max(widths) - min(widths), max(gw) - min(gw))

    def test_en_dash_and_arrow_are_drawable(self):
        self.assertEqual(social_card.plain_for_card("\u20a65,000 \u2013 \u20a615,000 \u2192 \u2713"), "\u20a65,000 \u2013 \u20a615,000 \u2192 \u2713")


class PollTests(unittest.TestCase):
    def test_an_a_to_d_question_becomes_a_poll_with_threads_sized_options(self):
        poll = tg.poll_from_text(to_plain(tg.TEMPLATES["engagement"][0]))
        self.assertEqual(poll["question"], "How much did your last agreement cost?")
        self.assertEqual(len(poll["options"]), 4)
        self.assertTrue(all(len(o) <= 25 for o in poll["options"]))
        self.assertIsNone(tg.poll_from_text("Headline.\n\nA) one\n\nno question mark"))
        self.assertIsNone(tg.poll_from_text("Why?\n\nA) same\nB) same"))

    def test_every_engagement_template_with_options_polls_on_telegram_and_threads(self):
        import generate_threads_content as th
        polled = [t for t in tg.TEMPLATES["engagement"] if tg.poll_from_text(to_plain(t))]
        self.assertGreaterEqual(len(polled), 2)
        # The Threads lunch post on a rotation day that drew a poll template carries it as option_a…
        with mock.patch.object(th.fb if hasattr(th, "fb") else __import__("generate_facebook_content"), "pick",
                               return_value=("engagement", tg.TEMPLATES["engagement"][0])), redirect_stdout(io.StringIO()):
            post_type, text, notes, extras = th.build(date(2026, 10, 22), None, "lunch")
        self.assertEqual(post_type, "engagement")
        self.assertEqual(extras["poll"]["option_a"], "Nothing")
        self.assertIn("option_d", extras["poll"])

    def test_the_telegram_poster_sends_a_regular_poll_under_a_poll_post(self):
        import post_telegram
        calls = []

        class R:
            status_code = 200

            def json(self):
                return {"ok": True, "result": {"message_id": 77}}
        with mock.patch.object(post_telegram.requests, "post", lambda url, data=None, timeout=30: calls.append((url, data)) or R()), \
                mock.patch.object(post_telegram, "TELEGRAM_BOT_TOKEN", "t"), mock.patch.object(post_telegram, "TELEGRAM_CHAT_ID", "@c"), \
                redirect_stdout(io.StringIO()):
            mid = post_telegram.send_poll({"question": "How much?", "options": ["A", "B"]})
        self.assertEqual(mid, 77)
        self.assertTrue(calls[0][0].endswith("/sendPoll"))
        self.assertEqual(calls[0][1]["type"], "regular")
        self.assertNotIn("correct_option_ids", calls[0][1])


class ShortTitleTests(unittest.TestCase):
    def test_the_youtube_title_leads_with_the_searchable_subject_and_keeps_the_hook(self):
        for n in range(6):
            script = words.VIDEO_SCRIPTS[n]
            title = words.yt_title(script)
            self.assertTrue(title.startswith(script["search"] + ": "), title)
            self.assertTrue(title.endswith(" #Shorts"))
            self.assertLessEqual(len(title), 100)
            self.assertIn(script["title"].split(". ")[0].rstrip(".").lower(), title.lower())
        self.assertEqual(words.yt_title({"title": "Brain hook."}), "Brain hook #Shorts")


if __name__ == "__main__":
    unittest.main()
