"""MarkdownV2 escaping, validation, and the outage that made it necessary.

On 7 Oct 2026 the daily Telegram post started failing with:

    Bad Request: can't parse entities: Character '#' is reserved and must be
    escaped with the preceding '\\'

and kept failing every day until the cause was read out of a run log on 11 Oct.
All 39 message templates in `scripts/generate_telegram_content.py` were invalid
MarkdownV2 — the templates were hand-escaped, but the hashtag block appended to
every one of them (`#DocOga #NigerianLandlords …`) was not.

These tests are the gate that was missing: every template, in every post type,
rendered exactly as the generator renders it, must be valid MarkdownV2.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import telegram_mdv2  # noqa: E402


def _load_generator():
    """Load scripts/generate_telegram_content.py without importing scripts as a package."""
    spec = importlib.util.spec_from_file_location(
        "docoga_telegram_content", ROOT / "scripts" / "generate_telegram_content.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EscapeTests(unittest.TestCase):
    def test_every_reserved_character_is_escaped(self):
        for ch in telegram_mdv2.SPECIALS:
            with self.subTest(character=ch):
                self.assertEqual(telegram_mdv2.escape(ch), "\\" + ch)

    def test_hashtag_block_is_escaped(self):
        # The exact string that broke the pipeline.
        escaped = telegram_mdv2.escape("#DocOga #NigerianLandlords")
        self.assertEqual(escaped, "\\#DocOga \\#NigerianLandlords")
        self.assertEqual(telegram_mdv2.validate(escaped), [])

    def test_none_and_plain_text_survive(self):
        self.assertEqual(telegram_mdv2.escape(None), "")
        self.assertEqual(telegram_mdv2.escape("emojis 🔍 and letters only"), "emojis 🔍 and letters only")

    def test_escape_then_unescape_is_identity(self):
        text = "Rent is ₦2,000 (10%) — pay by 5th. Visit https://docoga.com.ng!"
        self.assertEqual(telegram_mdv2.unescape(telegram_mdv2.escape(text)), text)


class PlainTextFallbackTests(unittest.TestCase):
    def test_markup_is_fully_stripped(self):
        # The old fallback only removed '\\' and '*', so the channel displayed
        # literal `_**🔍**_` in front of every post.
        message = "_**🔍**_ Caution Fee in Nigeria:\n\nIt depends on your agreement\\!"
        plain = telegram_mdv2.to_plain(message)
        self.assertEqual(plain, "🔍 Caution Fee in Nigeria:\n\nIt depends on your agreement!")
        for marker in ("_", "*", "~", "`"):
            self.assertNotIn(marker, plain)

    def test_escapes_are_removed_but_content_is_kept(self):
        self.assertEqual(
            telegram_mdv2.to_plain("DocOga generates: https://docoga\\.com\\.ng"),
            "DocOga generates: https://docoga.com.ng",
        )


class ValidateTests(unittest.TestCase):
    def test_escaped_text_is_valid(self):
        self.assertEqual(telegram_mdv2.validate("Use DocOga\\. It is free\\!"), [])

    def test_raw_hash_is_rejected(self):
        problems = telegram_mdv2.validate("Tag: #DocOga")
        self.assertEqual(len(problems), 1)
        self.assertIn("'#'", problems[0])

    def test_unbalanced_bold_is_rejected(self):
        problems = telegram_mdv2.validate("*Bold without a close\\.")
        self.assertTrue(any("unclosed" in p for p in problems), problems)

    def test_code_span_may_contain_reserved_characters(self):
        self.assertEqual(telegram_mdv2.validate("`#DocOga #free`"), [])

    def test_trailing_backslash_is_rejected(self):
        self.assertTrue(telegram_mdv2.validate("oops \\"))

    def test_empty_message_is_rejected(self):
        self.assertTrue(telegram_mdv2.validate(""))


class TemplateRegressionTests(unittest.TestCase):
    """The test that would have caught the 7 Oct outage before it shipped."""

    @classmethod
    def setUpClass(cls):
        cls.gen = _load_generator()

    def _rendered_messages(self):
        for post_type, templates in self.gen.TEMPLATES.items():
            hashtags = self.gen.HASHTAGS.get(post_type, "")
            for index, template in enumerate(templates):
                # Exactly how generate_daily_content() builds it.
                yield (
                    "%s[%d]" % (post_type, index),
                    "%s\n\n%s" % (template, telegram_mdv2.escape(hashtags)),
                )

    def test_every_template_renders_as_valid_markdownv2(self):
        checked = 0
        for label, message in self._rendered_messages():
            checked += 1
            with self.subTest(template=label):
                problems = telegram_mdv2.validate(message)
                self.assertEqual(
                    problems,
                    [],
                    "%s would be rejected by Telegram: %s" % (label, "; ".join(problems)),
                )
        self.assertGreater(checked, 30, "template corpus shrank unexpectedly")

    def test_every_template_fits_a_photo_caption(self):
        # Telegram's caption limit is 1024 characters; anything longer can never
        # be a photo post, only a text post.
        for label, message in self._rendered_messages():
            with self.subTest(template=label):
                self.assertLessEqual(len(message), 1024)

    def test_hashtags_are_escaped_exactly_once(self):
        # Double-escaping would show a visible backslash on the channel.
        for label, message in self._rendered_messages():
            with self.subTest(template=label):
                self.assertNotIn("\\\\#", message)
                self.assertNotIn("\\\\\\.", message)


if __name__ == "__main__":
    unittest.main()
