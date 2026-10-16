"""Poster fallback behaviour — the half of the 7 Oct outage that was invisible.

The message markup bug is covered in test_telegram_mdv2.py. What made the
outage expensive was that the poster *knew* why the retry failed and threw the
reason away:

    ❌ Telegram API error: Bad Request: can't parse entities: …
    ⚠️ Markdown parse failed, retrying as plain text...
    ❌ Failed to post engagement message          <- no reason given

So these tests pin the behaviour that makes a failure self-diagnosing:

  * the plain-text retry's own error is logged,
  * a photo that cannot be sent still produces a text post,
  * a caption too long for Telegram is trimmed, not rejected.
"""

import copy
import json
import tempfile
import os
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

# The poster opens its log at import time. Left alone, every run of this suite appends
# to the repo's real `logs/social_media.log` — 1,468 lines of "Photo message sent (id=3)"
# that a human would later read as publish evidence. Both telegram test modules set this
# before importing, because whichever imports first binds the module constants for the
# whole session.
_TMP = tempfile.mkdtemp(prefix="docoga-telegram-tests-")
os.environ.setdefault("TELEGRAM_LOG_FILE", os.path.join(_TMP, "social_media.log"))
os.environ.setdefault("TELEGRAM_LEDGER", os.path.join(_TMP, "telegram_sent.json"))

# The social scripts append to `logs/social_media.log`, and importing them binds that
# path. Redirected before the import so the repo's real log stays a record of publishes
# rather than a record of tests — see tools/docoga_log.py.
os.environ.setdefault("DOCOGA_LOG_DIR", tempfile.mkdtemp(prefix="docoga-social-log-"))

import post_telegram  # noqa: E402

PARSE_ERROR = (
    "Bad Request: can't parse entities: Character '#' is reserved and must be "
    "escaped with the preceding '\\'"
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def ok(message_id=1):
    return FakeResponse({"ok": True, "result": {"message_id": message_id}})


def error(description, status_code=400):
    return FakeResponse({"ok": False, "description": description}, status_code)


class PosterFallbackTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def recorder(url, json=None, data=None, files=None, timeout=None):
            # Snapshot the payloads: the poster mutates them in place between
            # attempts (it pops parse_mode), so holding a reference would make
            # every recorded call look like the last one.
            self.calls.append(
                {
                    "url": url,
                    "json": copy.deepcopy(json),
                    "data": copy.deepcopy(data),
                }
            )
            return self.responses.pop(0)

        self.responses = []
        self._patch = patch.object(post_telegram.requests, "post", side_effect=recorder)
        self._patch.start()
        self.addCleanup(self._patch.stop)

        env = patch.dict(
            post_telegram.os.environ,
            {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "@channel"},
        )
        env.start()
        self.addCleanup(env.stop)
        post_telegram.TELEGRAM_BOT_TOKEN = "test-token"
        post_telegram.TELEGRAM_CHAT_ID = "@channel"
        self.addCleanup(setattr, post_telegram, "TELEGRAM_BOT_TOKEN", None)
        self.addCleanup(setattr, post_telegram, "TELEGRAM_CHAT_ID", None)

    def _run(self, func, *args, **kwargs):
        out = StringIO()
        with redirect_stdout(out):
            result = func(*args, **kwargs)
        return result, out.getvalue()

    def test_parse_error_retries_as_plain_text_without_markup(self):
        self.responses = [error(PARSE_ERROR), ok()]
        result, output = self._run(
            post_telegram.send_text_message, "*Bold* text\\. #DocOga"
        )

        self.assertTrue(result)
        self.assertIn("plain text fallback", output)
        first, second = self.calls
        self.assertEqual(first["json"]["parse_mode"], "MarkdownV2")
        self.assertNotIn("parse_mode", second["json"])
        # Markup and escapes go; real characters (including '#' in plain text)
        # stay exactly as written.
        self.assertEqual(second["json"]["text"], "Bold text. #DocOga")

    def test_failed_retry_reports_why_it_failed(self):
        """The regression: the second error used to be discarded."""
        self.responses = [
            error(PARSE_ERROR),
            error("Bad Request: not enough rights to send text messages to the chat", 403),
        ]
        result, output = self._run(post_telegram.send_text_message, "hello #DocOga")

        self.assertFalse(result)
        self.assertIn("Plain-text retry also failed", output)
        self.assertIn("not enough rights", output)
        self.assertIn("HTTP 403", output)

    def test_unsendable_photo_falls_back_to_a_text_post(self):
        self.responses = [
            error("Bad Request: PHOTO_INVALID_DIMENSIONS", 400),
        ]
        # send_photo_message keeps a file handle open; a real file is needed.
        photo = Path(self.enterContext(_temp_png()))
        self.responses.append(ok())  # the text fallback
        result, output = self._run(
            post_telegram.send_photo_message, str(photo), "Caption with #hashtag"
        )

        self.assertTrue(result)
        self.assertIn("falling back to a text post", output)
        self.assertTrue(self.calls[0]["url"].endswith("/sendPhoto"))
        self.assertTrue(self.calls[1]["url"].endswith("/sendMessage"))

    def test_photo_parse_error_retries_the_caption_as_plain_text(self):
        photo = Path(self.enterContext(_temp_png()))
        self.responses = [error(PARSE_ERROR), ok(2)]
        result, output = self._run(
            post_telegram.send_photo_message, str(photo), "*Caption* with #hashtag"
        )

        self.assertTrue(result)
        self.assertIn("plain caption", output)
        self.assertNotIn("parse_mode", self.calls[1]["data"])

    def test_over_long_caption_is_trimmed_not_rejected(self):
        photo = Path(self.enterContext(_temp_png()))
        self.responses = [ok(3)]
        long_caption = "x" * 2000
        self._run(post_telegram.send_photo_message, str(photo), long_caption)
        self.assertEqual(len(self.calls[0]["data"]["caption"]), post_telegram.MAX_CAPTION_CHARS)

    def test_over_long_message_is_trimmed_not_rejected(self):
        self.responses = [ok(4)]
        self._run(post_telegram.send_text_message, "y" * 5000)
        self.assertEqual(len(self.calls[0]["json"]["text"]), post_telegram.MAX_MESSAGE_CHARS)


def _temp_png():
    """A context manager yielding a throwaway PNG path (content is never parsed)."""

    class _Temp:
        def __enter__(self):
            self._tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            self._tmp.write(b"\x89PNG\r\n\x1a\n fake")
            self._tmp.close()
            return self._tmp.name

        def __exit__(self, *exc):
            Path(self._tmp.name).unlink(missing_ok=True)

    return _Temp()


WELL_FORMED = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"  # the shape, not a real bot


class PreflightTests(unittest.TestCase):
    """The preflight must name a missing secret without touching the network."""

    def test_missing_secrets_exit_two(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import telegram_preflight

        with patch.dict(telegram_preflight.os.environ, {}, clear=True):
            out = StringIO()
            with redirect_stdout(out):
                code = telegram_preflight.main([])
        self.assertEqual(code, 2)
        self.assertIn("TELEGRAM_BOT_TOKEN", out.getvalue())

    def test_invalid_token_exits_three(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import telegram_preflight

        with patch.dict(
            telegram_preflight.os.environ,
            {"TELEGRAM_BOT_TOKEN": WELL_FORMED, "TELEGRAM_CHAT_ID": "@channel"},
            clear=True,
        ), patch.object(telegram_preflight, "call", return_value=(False, "Unauthorized")):
            out = StringIO()
            with redirect_stdout(out):
                code = telegram_preflight.main([])
        self.assertEqual(code, 3)
        self.assertIn("Unauthorized", out.getvalue())
        self.assertIn("revoked", out.getvalue())

    def test_a_404_is_called_a_paste_problem(self):
        """15–16 Oct 2026: `getMe failed: Not Found` was reported as "revoked or wrong" — the
        owner would have regenerated a perfectly good bot token. 404 means the shape."""
        sys.path.insert(0, str(ROOT / "tools"))
        import telegram_preflight

        with patch.dict(
            telegram_preflight.os.environ,
            {"TELEGRAM_BOT_TOKEN": WELL_FORMED, "TELEGRAM_CHAT_ID": "@channel"},
            clear=True,
        ), patch.object(telegram_preflight, "call", return_value=(False, "Not Found")):
            out = StringIO()
            with redirect_stdout(out):
                code = telegram_preflight.main([])
        self.assertEqual(code, 3)
        self.assertIn("paste problem", out.getvalue())
        self.assertNotIn("revoked or", out.getvalue())

    def test_a_malformed_token_is_refused_offline_with_its_shape(self):
        """Nothing shaped like a token inside the secret → exit 3 before any network call,
        with a redacted description of what is there instead."""
        sys.path.insert(0, str(ROOT / "tools"))
        import telegram_preflight

        with patch.dict(
            telegram_preflight.os.environ,
            {"TELEGRAM_BOT_TOKEN": "-1001234567890", "TELEGRAM_CHAT_ID": "@channel"},
            clear=True,
        ), patch.object(telegram_preflight, "call", side_effect=AssertionError("network")) :
            out = StringIO()
            with redirect_stdout(out):
                code = telegram_preflight.main([])
        self.assertEqual(code, 3)
        self.assertIn("chat id", out.getvalue())
        self.assertNotIn("1001234567890", out.getvalue())

    def test_a_token_pasted_with_its_bot_prefix_is_used_and_remarked_on(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import telegram_preflight

        seen = []
        responses = {
            "getMe": (True, {"id": 42, "username": "docoga_bot"}),
            "getChat": (True, {"id": -100, "type": "channel", "title": "DocOga Daily"}),
            "getChatMember": (True, {"status": "administrator", "can_post_messages": True}),
        }

        def fake_call(method, token, **kw):
            seen.append(token)
            return responses[method]

        with patch.dict(
            telegram_preflight.os.environ,
            {"TELEGRAM_BOT_TOKEN": "bot" + WELL_FORMED + "\n", "TELEGRAM_CHAT_ID": "@channel"},
            clear=True,
        ), patch.object(telegram_preflight, "call", side_effect=fake_call):
            out = StringIO()
            with redirect_stdout(out):
                code = telegram_preflight.main([])
        self.assertEqual(code, 0, out.getvalue())
        self.assertTrue(seen and all(t == WELL_FORMED for t in seen), seen)
        self.assertIn("pasted untidily", out.getvalue())

    def test_demoted_bot_exits_five(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import telegram_preflight

        responses = {
            "getMe": (True, {"id": 42, "username": "docoga_bot"}),
            "getChat": (True, {"id": -100, "type": "channel", "title": "DocOga Daily"}),
            "getChatMember": (True, {"status": "member"}),
        }
        with patch.dict(
            telegram_preflight.os.environ,
            {"TELEGRAM_BOT_TOKEN": WELL_FORMED, "TELEGRAM_CHAT_ID": "@channel"},
            clear=True,
        ), patch.object(telegram_preflight, "call", side_effect=lambda m, *a, **k: responses[m]):
            out = StringIO()
            with redirect_stdout(out):
                code = telegram_preflight.main([])
        self.assertEqual(code, 5)
        self.assertIn("administrator", out.getvalue())


try:
    import yaml
except ImportError:  # pragma: no cover - CI installs PyYAML
    yaml = None


@unittest.skipIf(yaml is None, "PyYAML is required for the workflow contract tests")
class DryRunContractTests(unittest.TestCase):
    """`dry_run=true` must be able to answer "can the bot post?" without posting.

    The question left open by the 7–10 Oct outage is whether the bot still has
    permission to post to the channel. The only way to ask Telegram is with the
    real token, and the only safe way to do that is a run that stops after the
    preflight. If a refactor ever removes those `if` guards, this fails.
    """

    @classmethod
    def setUpClass(cls):
        path = ROOT / ".github" / "workflows" / "telegram_autopost.yml"
        cls.workflow = yaml.safe_load(path.read_text(encoding="utf-8"))

    def _steps(self):
        return self.workflow["jobs"]["generate-and-post"]["steps"]

    def _by_name(self, fragment):
        return [s for s in self._steps() if fragment in (s.get("name") or "")]

    def test_posting_steps_are_skipped_on_a_dry_run(self):
        for fragment in ("Generate Telegram content", "Post to Telegram"):
            steps = self._by_name(fragment)
            self.assertEqual(len(steps), 1, "expected exactly one '%s' step" % fragment)
            condition = steps[0].get("if") or ""
            self.assertIn("inputs.dry_run", condition, "%s would post during a dry run" % fragment)

    def test_preflight_always_runs(self):
        preflight = self._by_name("Preflight")
        self.assertEqual(len(preflight), 1)
        self.assertIsNone(preflight[0].get("if"), "the preflight must run on every trigger")

    def test_dry_run_input_is_boolean_and_defaults_to_false(self):
        inputs = self.workflow[True]["workflow_dispatch"]["inputs"]
        self.assertEqual(inputs["dry_run"]["type"], "boolean")
        self.assertIs(inputs["dry_run"]["default"], False)


if __name__ == "__main__":
    unittest.main()
