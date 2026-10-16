"""tools/telegram_token.py — the bot-token reader that survives a phone paste.

Background: 15–16 Oct 2026, `getMe failed: Not Found` (404 = wrong shape, not revoked) the day
after the secret was re-pasted. The reader must find the token inside the common bad pastes,
refuse anything that is not one, and describe the problem without ever printing the value.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import telegram_token as tt  # noqa: E402

TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"


class NormalizeTests(unittest.TestCase):
    def test_clean_token_is_unchanged_and_unremarked(self):
        self.assertEqual(tt.normalize(TOKEN), (TOKEN, ""))

    def test_bot_prefix_url_quotes_and_whitespace_still_yield_the_token(self):
        for raw in ("bot" + TOKEN, " BOT" + TOKEN + " ", "https://api.telegram.org/bot%s/getMe" % TOKEN,
                    '"%s"' % TOKEN, "'%s'\n" % TOKEN, TOKEN + "\r\n", "\t" + TOKEN):
            with self.subTest(raw=raw):
                token, note = tt.normalize(raw)
                self.assertEqual(token, TOKEN)
                self.assertTrue(note, "an untidy paste must be remarked on")

    def test_the_note_names_the_problem_not_the_value(self):
        token, note = tt.normalize("https://api.telegram.org/bot%s/getMe" % TOKEN)
        self.assertIn("bot prefix", note)
        self.assertIn("extra character", note)
        self.assertNotIn("AAHdq", note)

    def test_values_that_are_not_tokens_are_refused_with_a_shape(self):
        cases = {
            "-1001234567890": "chat id",
            "123456789:AAHdqTcv": "truncated",
            "abcdefghij:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw": "not all digits",
            "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw": "no colon",
            "": "empty",
        }
        for raw, expect in cases.items():
            with self.subTest(raw=raw):
                token, note = tt.normalize(raw)
                self.assertIsNone(token)
                self.assertIn(expect, note)
                self.assertNotIn("AAHdqTcvCH1vGWJ", note)

    def test_unset_is_unset(self):
        self.assertEqual(tt.normalize(None), (None, "unset"))
        self.assertEqual(tt.from_env({}), (None, "unset"))

    def test_from_env_reads_the_lane_variable(self):
        self.assertEqual(tt.from_env({"TELEGRAM_BOT_TOKEN": "bot" + TOKEN})[0], TOKEN)

    def test_describe_never_echoes_the_value(self):
        for raw in ("bot123:secret/with/slashes", "https://x.y/z", "a b c"):
            self.assertNotIn(raw, tt.describe(raw))


class RejectionTests(unittest.TestCase):
    def test_404_is_a_paste_problem_401_is_revocation(self):
        self.assertIn("paste problem", tt.explain_rejection("Not Found"))
        self.assertIn("revoked", tt.explain_rejection("Unauthorized"))
        self.assertIn("BotFather", tt.explain_rejection("something else"))


if __name__ == "__main__":
    unittest.main()
