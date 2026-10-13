"""The poster's side of the live duplicate guard: policy, ordering, and fail-open.

`tools/telegram_preview.py` knows how to read a channel page; this file is about the four
decisions the poster makes with it, all of which were written down after the 3 Oct 2026
shape — the same caution-fee paragraph on the channel four times in four hours, with a
ledger that had no idea, because the ledger is only as good as the last commit it survived:

  * the guard runs **after** the ledger and **before** anything is sent (the ledger is free
    and offline; a duplicate it already knows about must not cost an HTTP request);
  * a "match" is a refusal that exits **green** with a `SKIPPED` marker — it is the lane
    working, not a failure, and it names the permalink as evidence;
  * an unreadable page is a **warning and a send**: the guard may never be the reason the
    channel goes quiet;
  * `--force` overrides it, loudly, and nothing about the page is ever logged or sent with
    the bot token.
"""

import copy
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

# Same guard as the other poster tests: whichever module imports the social scripts first
# binds LOG_FILE / LEDGER_FILE for the whole run, so this file sets them too.
_TMP = tempfile.mkdtemp(prefix="docoga-telegram-guard-")
os.environ.setdefault("TELEGRAM_LOG_FILE", os.path.join(_TMP, "social_media.log"))
os.environ.setdefault("TELEGRAM_LEDGER", os.path.join(_TMP, "telegram_sent.json"))
os.environ.setdefault("DOCOGA_LOG_DIR", tempfile.mkdtemp(prefix="docoga-social-log-"))

import post_telegram  # noqa: E402
import telegram_preview  # noqa: E402
import youtube_ledger as ledger  # noqa: E402

# Our daily content, in the shape the generator writes it: MarkdownV2, escaped punctuation.
CAUTION = (r"Your landlord is holding your caution fee\? It is a \*\*security deposit\*\* — "
            r"not a gift\. Get a receipt for every payment: \[docoga\.com\.ng\]\(https://docoga\.com\.ng\)")
FRESH = ("Service charges in Lekki Phase One are audited every year, and a tenant can demand "
         "the ledger before paying a kobo of them.")

CAUTION_ON_CHANNEL = (
    '<div class="tgme_widget_message" data-post="docogadaily/41">'
    '<div class="tgme_widget_message_text js-message_text" dir="auto">Your landlord is holding '
    "your caution fee? It is a <strong>security deposit</strong> — not a gift. Get a receipt for "
    'every payment: <a href="https://docoga.com.ng">docoga.com.ng</a></div>'
    '<div class="tgme_widget_message_link_preview">Caution Fee in Nigeria: Rules, Refunds &amp; '
    "Receipts (2026 Guide) — a template worth reading before you sign</div></div>"
)
UNRELATED_ON_CHANNEL = (
    '<div class="tgme_widget_message" data-post="docogadaily/42">'
    '<div class="tgme_widget_message_text">Notice to quit in Lagos: what a tenant must know about '
    "the six month rule and the court order that actually removes a person from a home.</div></div>"
)


def channel_page(*blocks):
    return "<html><body>%s</body></html>" % "".join(blocks)


class Response:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


def telegram_ok(message_id):
    """What api.telegram.org answers a successful sendMessage.

    A module-level helper on purpose: the fake `requests.post` below takes a `json=` keyword,
    which shadows the module inside it, and a shadowed import in a test is a mystery to debug
    at midnight.
    """
    return type("Sent", (), {
        "status_code": 200,
        "text": json.dumps({"ok": True, "result": {"message_id": message_id}}),
        "json": lambda self: {"ok": True, "result": {"message_id": message_id}},
    })()


class GuardTestCase(unittest.TestCase):
    """The poster with a scripted channel and a scripted Telegram."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="guard-")
        self.ledger_path = Path(self.dir) / "telegram_sent.json"
        patchers = [
            patch.object(post_telegram, "LEDGER_FILE", self.ledger_path),
            patch.object(post_telegram, "LOG_FILE", Path(self.dir) / "social_media.log"),
            patch.object(post_telegram, "TELEGRAM_BOT_TOKEN", "123456:AA-test-token"),
            patch.object(post_telegram, "TELEGRAM_CHAT_ID", "@docogadaily"),
            patch.object(post_telegram, "FORCE", False),
            patch.object(post_telegram, "load_content",
                         lambda: [copy.deepcopy(self.post) for _ in range(self.repeat)]),
            # The guard reads the *environment* (that is where the deployment keeps the chat),
            # so the rig sets it here as well as patching the module constant.
            patch.dict(os.environ, {"GITHUB_RUN_ID": "99",
                                    "TELEGRAM_CHAT_ID": "@docogadaily",
                                    "TELEGRAM_CHANNEL_USERNAME": "",
                                    "TELEGRAM_SKIP_CHANNEL_CHECK": ""}),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.post = {"message": CAUTION, "post_type": "tip", "send_photo": False,
                     "photo_path": None}
        self.repeat = 1
        self.sent = []          # what the poster tried to put on Telegram
        self.preview_urls = []  # what the guard asked the channel for

        def send(url, json=None, data=None, files=None, timeout=None):
            self.sent.append(json if json is not None else data)
            return telegram_ok(500 + len(self.sent))

        send_patcher = patch.object(post_telegram.requests, "post", side_effect=send)
        send_patcher.start()
        self.addCleanup(send_patcher.stop)
        self.channel_page = channel_page(CAUTION_ON_CHANNEL, UNRELATED_ON_CHANNEL)
        self.preview_error = None
        # One patcher, stopped by its own cleanup. Building a *second* patch object out of the
        # already-patched attribute is how this file used to leave the fake installed for every
        # test module that ran after it — the leak `unittest discover` finds and a single-file
        # run never does.
        preview_patcher = patch.object(telegram_preview, "fetch_preview", self.fetch_preview)
        preview_patcher.start()
        self.addCleanup(preview_patcher.stop)

    def fetch_preview(self, url):
        self.preview_urls.append(url)
        if self.preview_error:
            raise self.preview_error
        return Response(self.channel_page)

    def run_poster(self):
        out = StringIO()
        with redirect_stdout(out):
            result = post_telegram.post_to_telegram()
        return result, out.getvalue()

    def entries(self):
        return ledger.load(str(self.ledger_path))


class Policy(GuardTestCase):
    def test_a_duplicate_of_the_channel_is_a_match_naming_the_permalink(self):
        state, detail = post_telegram.channel_duplicate(CAUTION)
        self.assertEqual(state, "match")
        self.assertIn("t.me/docogadaily/41", detail)

    def test_fresh_wording_is_clear(self):
        state, detail = post_telegram.channel_duplicate(FRESH)
        self.assertEqual(state, "clear")
        self.assertIn("2 recent channel post(s)", detail)

    def test_an_unreadable_page_is_unavailable_not_safe(self):
        self.preview_error = OSError("connection reset")
        state, detail = post_telegram.channel_duplicate(CAUTION)
        self.assertEqual(state, "unavailable")
        self.assertIn("OSError", detail)

    def test_a_page_of_no_messages_is_unavailable(self):
        self.channel_page = "<html><body>redirected to t.me/docogadaily</body></html>"
        state, detail = post_telegram.channel_duplicate(CAUTION)
        self.assertEqual(state, "unavailable")
        self.assertIn("no messages", detail)

    def test_a_numeric_chat_has_nothing_to_read_and_says_so(self):
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "-1001234567890"}):
            state, detail = post_telegram.channel_duplicate(CAUTION)
        self.assertEqual(state, "skipped")
        self.assertIn("numeric", detail)
        self.assertEqual(self.preview_urls, [], "no request should even be attempted")

    def test_a_two_word_message_is_not_compared(self):
        state, detail = post_telegram.channel_duplicate("ok thanks")
        self.assertEqual(state, "skipped")
        self.assertIn("too short", detail)
        self.assertEqual(self.preview_urls, [])

    def test_the_kill_switch_disables_it_without_touching_the_ledger(self):
        with patch.object(post_telegram, "CHANNEL_GUARD_ENABLED", False):
            state, detail = post_telegram.channel_duplicate(CAUTION)
        self.assertEqual(state, "skipped")
        self.assertIn("TELEGRAM_SKIP_CHANNEL_CHECK", detail)
        self.assertEqual(self.preview_urls, [])


class Wiring(GuardTestCase):
    def test_a_duplicate_on_the_channel_is_not_sent_and_the_run_stays_green(self):
        result, out = self.run_poster()
        self.assertEqual(self.sent, [], "the guard runs before anything reaches Telegram")
        self.assertEqual(result, 0)
        self.assertIn("TELEGRAM_SENT=0", out)
        self.assertIn("TELEGRAM_SKIPPED=1", out)
        self.assertIn("TELEGRAM_CHANNEL_GUARD=refused-a-duplicate", out)
        self.assertIn("t.me/docogadaily/41", out, "the refusal has to name its evidence")
        self.assertEqual(self.entries(), [], "a refusal writes nothing to the ledger")

    def test_the_ledger_is_consulted_first_and_saves_the_request(self):
        """Already recorded ⇒ not on the channel: the ledger answers and no HTTP runs."""
        key = post_telegram.content_key("tip", CAUTION)
        # `record(existing_entries, path=…, **fields)` — the fields are keyword arguments, and
        # an entry without a `video_id` is dropped as "the same row", so seeding through a list
        # of dicts silently records nothing. Both facts are the ledger's own API.
        ledger.record([], path=str(self.ledger_path), id=key, title=key,
                      date=post_telegram.run_date().isoformat(),
                      url="https://t.me/docogadaily/40", privacy="channel", run_id="98")
        self.channel_page = "<html>unreachable</html>"  # would report "unavailable" if asked
        result, out = self.run_poster()
        self.assertEqual(self.preview_urls, [], "the free check runs first, always")
        self.assertIn("TELEGRAM_SKIPPED=1", out)
        self.assertIn("already in the ledger", out)

    def test_an_unreadable_channel_posts_anyway_and_says_the_ledger_is_alone(self):
        self.preview_error = OSError("timed out")
        result, out = self.run_poster()
        self.assertEqual(len(self.sent), 1, "a fetch failure must never cost the channel its post")
        self.assertEqual(result, 1)
        self.assertIn("live channel guard unavailable", out)
        self.assertIn("The ledger is guarding this run", out)
        self.assertIn("TELEGRAM_CHANNEL_GUARD=unavailable", out)
        self.assertEqual(len(self.entries()), 1, "the post is still recorded")

    def test_a_clear_channel_posts_records_and_reports_live(self):
        self.post = {"message": FRESH, "post_type": "tip", "send_photo": False,
                     "photo_path": None}
        result, out = self.run_poster()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(result, 1)
        self.assertIn("TELEGRAM_CHANNEL_GUARD=live", out)
        self.assertEqual(len(self.entries()), 1)

    def test_force_overrides_the_live_guard_loudly(self):
        with patch.object(post_telegram, "FORCE", True):
            result, out = self.run_poster()
        self.assertEqual(len(self.sent), 1, "--force is the escape hatch for a wrong guard")
        self.assertIn("force is on: re-posting text the channel already carries", out)

    def test_two_identical_entries_in_one_file_are_one_post(self):
        """Within a run, the first send records the key and the second entry is refused by
        the ledger before the guard is even asked."""
        self.repeat = 2
        result, out = self.run_poster()
        self.assertEqual(len(self.sent), 0, "the only copy on the channel is the one we refused")
        self.assertIn("TELEGRAM_SKIPPED=", out)

    def test_a_photo_post_is_compared_on_its_caption(self):
        self.post = {"message": CAUTION, "post_type": "tip", "send_photo": True,
                     "photo_path": "/nonexistent/card.png"}
        result, out = self.run_poster()
        self.assertEqual(self.sent, [], "a caption already on the channel is a duplicate")
        self.assertIn("TELEGRAM_SKIPPED=1", out)

    def test_the_channel_request_never_carries_the_token(self):
        self.assertEqual(post_telegram.channel_duplicate(FRESH)[0], "clear")
        self.assertEqual(len(self.preview_urls), 1)
        url = self.preview_urls[0]
        self.assertIn("t.me/s/docogadaily", url)
        for secret in ("123456:AA-test-token", "AA-test-token"):
            self.assertNotIn(secret, url)
        self.assertNotIn("api.telegram.org", url)

    def test_the_page_itself_is_never_printed(self):
        _result, out = self.run_poster()
        self.assertNotIn("tgme_widget_message", out)
        self.assertNotIn("<div", out, "channel HTML in a run log is a wall of noise, not a diagnostic")


class PreflightReport(unittest.TestCase):
    def test_preview_mode_exits_zero_only_when_the_channel_is_readable(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import telegram_preflight as preflight
        with patch.object(telegram_preview, "fetch_preview",
                          lambda url: Response(channel_page(UNRELATED_ON_CHANNEL))):
            self.assertEqual(preflight.main(["--preview", "@docogadaily"]), 0)
        with patch.object(telegram_preview, "fetch_preview",
                          lambda url: Response("", status_code=503)):
            self.assertEqual(preflight.main(["--preview", "@docogadaily"]), 1)

    def test_preview_mode_needs_no_secrets(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import telegram_preflight as preflight
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(telegram_preview, "fetch_preview",
                             lambda url: Response(channel_page(UNRELATED_ON_CHANNEL))):
            self.assertEqual(preflight.main(["--preview", "@docogadaily"]), 0)


if __name__ == "__main__":
    unittest.main()
