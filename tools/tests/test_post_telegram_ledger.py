"""The publish ledger: Telegram's proof of work, and the duplicate-post fix.

Two facts about the channel, both from 13 Oct 2026:

  * `t.me/s/docogadaily` carried the *same* caution-fee paragraph four times inside
    four hours on 3 Oct, because five runs (one scheduled, four dispatches) each
    started with zero knowledge of what the channel already had;
  * the lane's only record of publishing was `logs/social_media.log`, which is
    gitignored, unreadable from CI, and — as of this week — mostly test noise, so the
    heartbeat could say "9.4 days since anything succeeded" while the channel had a
    post six days ago, and nobody could tell which sentence was the true one.

So the poster now writes a committed ledger, keyed on the *content* rather than the
date, through the same `tools/youtube_ledger.py` the Shorts and Reels lanes use. These
tests are the four properties that make that worth trusting:

  * a repeat of identical text is skipped, and a different text is not;
  * a skipped day is green (nothing is wrong) and an empty content file is red;
  * nothing is recorded unless Telegram actually accepted the message;
  * and `--force` overrides, loudly, because the override is the escape hatch for the
    day the ledger is the thing that is wrong.
"""

import copy
import json
import tempfile
import os
import sys
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

# Same guard as test_post_telegram.py: whichever module imports the poster first binds
# LOG_FILE / LEDGER_FILE for the whole run, so both files set them.
_TMP = tempfile.mkdtemp(prefix="docoga-telegram-ledger-")
os.environ.setdefault("TELEGRAM_LOG_FILE", os.path.join(_TMP, "social_media.log"))
os.environ.setdefault("TELEGRAM_LEDGER", os.path.join(_TMP, "telegram_sent.json"))

# The social scripts append to `logs/social_media.log`, and importing them binds that
# path. Redirected before the import so the repo's real log stays a record of publishes
# rather than a record of tests — see tools/docoga_log.py.
os.environ.setdefault("DOCOGA_LOG_DIR", tempfile.mkdtemp(prefix="docoga-social-log-"))

import post_telegram  # noqa: E402
import telegram_preview  # noqa: E402  the live guard the poster consults
import youtube_ledger as ledger  # noqa: E402


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def ok(message_id=7):
    return FakeResponse({"ok": True, "result": {"message_id": message_id}})


def error(description="Bad Request: chat not found", status_code=400):
    return FakeResponse({"ok": False, "description": description}, status_code)


class LedgerTestCase(unittest.TestCase):
    """Shared rig: an isolated ledger + log, a stubbed HTTP layer, one content file."""

    POSTS = [{"message": "Always get a written receipt for every rent payment.",
              "post_type": "tip", "send_photo": False, "photo_path": None}]

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ledger-")
        self.ledger_path = Path(self.dir) / "telegram_sent.json"
        self.log_path = Path(self.dir) / "social_media.log"
        patchers = [
            patch.object(post_telegram, "LEDGER_FILE", self.ledger_path),
            patch.object(post_telegram, "LOG_FILE", self.log_path),
            patch.object(post_telegram, "TELEGRAM_BOT_TOKEN", "test-token"),
            patch.object(post_telegram, "TELEGRAM_CHAT_ID", "@docogadaily"),
            patch.object(post_telegram, "FORCE", False),
            patch.object(post_telegram, "load_content", lambda: copy.deepcopy(self.POSTS)),
            # No test here reaches the network. The rig pins the channel preview to one
            # unrelated post, so the guard answers "clear" from a fixture and the *behaviour*
            # under test stays the ledger's. The guard's own branches are tested in
            # test_post_telegram_channel_guard.py.
            patch.object(telegram_preview, "fetch_preview",
                         lambda url: FakeResponse(
                             '<div class="tgme_widget_message" data-post="docogadaily/1">'
                             '<div class="tgme_widget_message_text">An unrelated post about '
                             'the six month notice period in Lagos.</div></div>')),
            patch.dict(os.environ, {"TELEGRAM_SKIP_CHANNEL_CHECK": ""}),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.calls = []
        self.responses = [ok()]

        def recorder(url, json=None, data=None, files=None, timeout=None):
            self.calls.append({"url": url, "json": copy.deepcopy(json)})
            return self.responses.pop(0)

        http = patch.object(post_telegram.requests, "post", side_effect=recorder)
        http.start()
        self.addCleanup(http.stop)
        env = patch.dict(os.environ, {"TELEGRAM_CHANNEL_USERNAME": "docogadaily",
                                      "GITHUB_RUN_ID": "424242"})
        env.start()
        self.addCleanup(env.stop)

    def run_poster(self, argv=()):
        out = StringIO()
        with patch.object(sys, "argv", ["post_telegram.py"] + list(argv)), \
                redirect_stdout(out):
            result = post_telegram.post_to_telegram()
        return result, out.getvalue()

    def entries(self):
        return ledger.load(str(self.ledger_path))


class ContentKeyTests(unittest.TestCase):
    def test_the_key_is_the_text_not_the_date(self):
        a = post_telegram.content_key("tip", "Receipts are proof of payment.")
        b = post_telegram.content_key("tip", "Receipts are proof of payment.")
        c = post_telegram.content_key("tip", "Receipts are proof of payment!")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c, "one character is a different post; the ledger must not "
                                  "treat a new sentence as a repeat")
        self.assertTrue(a.startswith("telegram tip "), a)

    def test_post_types_do_not_collide(self):
        text = "Same words, different slot."
        self.assertNotEqual(post_telegram.content_key("tip", text),
                            post_telegram.content_key("engagement", text))

    def test_the_key_survives_whitespace(self):
        self.assertEqual(post_telegram.content_key("tip", "  padded \n"),
                         post_telegram.content_key("tip", "padded"))


class LedgerWriteTests(LedgerTestCase):
    def test_a_successful_post_is_recorded_with_a_permalink(self):
        sent, out = self.run_poster()
        self.assertEqual(sent, 1)
        self.assertIn("TELEGRAM_SENT=1", out)
        entries = self.entries()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["url"], "https://t.me/docogadaily/7",
                         "the message id is the only proof that survives the run log")
        self.assertEqual(entry["date"], post_telegram.run_date().isoformat())
        self.assertEqual(entry["run_id"], "424242")
        self.assertEqual(entry["privacy"], "channel")
        self.assertIn("telegram tip ", entry["title"])

    def test_the_second_run_of_the_same_text_posts_nothing_and_stays_green(self):
        """The Oct 3 shape, four times over: separate runs, identical file. The channel
        must not be spammed, and the run must not be red — a skipped duplicate is the
        ledger working, not a failure to publish."""
        self.assertEqual(self.run_poster()[0], 1)
        self.responses = [ok(message_id=8)]
        sent, out = self.run_poster()
        self.assertEqual(sent, 0)
        self.assertIn("TELEGRAM_SKIPPED=1", out)
        self.assertIn("already in the ledger", out)
        self.assertEqual(len(self.calls), 1, "no second HTTP call, in any form")
        self.assertEqual(len(self.entries()), 1)

    def test_force_reposts_and_says_so(self):
        self.assertEqual(self.run_poster()[0], 1)
        self.responses = [ok(message_id=9)]
        sent, out = self.run_poster(argv=["--force"])
        self.assertEqual(sent, 1)
        self.assertIn("force is on", out)
        self.assertEqual(len(self.calls), 2)

    def test_force_via_environment_too(self):
        self.assertEqual(self.run_poster()[0], 1)
        self.responses = [ok(message_id=9)]
        with patch.dict(os.environ, {"TELEGRAM_FORCE": "1"}):
            post_telegram.FORCE = os.getenv("TELEGRAM_FORCE") in ("1", "true", "yes")
            sent, _ = self.run_poster()
        self.assertEqual(sent, 1)

    def test_two_different_posts_on_one_day_are_two_entries(self):
        """Regression: the ledger de-duplicates by id, and keying that id on (date,
        index) made the second post overwrite the first. The count of entries is the
        count of publishes, or the file is worthless as evidence."""
        self.POSTS = [{"message": "First tip.", "post_type": "tip",
                       "send_photo": False, "photo_path": None},
                      {"message": "Second guide.", "post_type": "guide",
                       "send_photo": False, "photo_path": None}]
        self.responses = [ok(message_id=21), ok(message_id=22)]
        sent, out = self.run_poster()
        self.assertEqual(sent, 2)
        entries = self.entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(sorted(e["url"] for e in entries),
                         ["https://t.me/docogadaily/21", "https://t.me/docogadaily/22"])
        self.assertIn("TELEGRAM_SENT=2", out)


    def test_different_content_is_not_blocked_by_a_full_ledger(self):
        self.run_poster()
        self.POSTS = [{"message": "A brand new tip about the 6-month notice period.",
                       "post_type": "guide", "send_photo": False, "photo_path": None}]
        self.responses = [ok(message_id=11)]
        sent, _ = self.run_poster()
        self.assertEqual(sent, 1)
        self.assertEqual(len(self.entries()), 2)

    def test_a_refused_send_records_nothing(self):
        """A ledger entry means Telegram accepted the message. Recording the *intent*
        would turn the file into a wish, and the heartbeat would read a publish that
        never happened."""
        self.responses = [error()]
        sent, out = self.run_poster()
        self.assertEqual(sent, -1)
        self.assertIn("TELEGRAM_SENT=0", out)
        self.assertFalse(self.ledger_path.exists())


class WorkflowContractTests(unittest.TestCase):
    """The poster and the workflow agree on one filename, or the whole point is lost.

    A ledger nobody commits is invisible to CI, and an empty ledger is read by the
    heartbeat as "nothing published" — which is the false accusation this lane spent six
    days under. So the two sides are pinned to each other here, not by whoever edits
    next remembering both places.
    """

    def setUp(self):
        self.wf = (ROOT / ".github" / "workflows" / "telegram_autopost.yml").read_text(encoding="utf-8")

    def test_the_workflow_commits_the_file_the_poster_writes(self):
        self.assertIn("logs/" + post_telegram.LEDGER_FILE.name, self.wf,
                      "the poster writes %s; the commit step must add that path"
                      % post_telegram.LEDGER_FILE.name)

    def test_the_commit_step_is_guarded_and_idempotent(self):
        block = self.wf.split("Commit the publish ledger")[1]
        self.assertIn("continue-on-error: true", block,
                      "a bookkeeping push must never turn a successful publish red")
        self.assertIn("if [ ! -f logs/telegram_sent.json ]", block)
        self.assertIn('git status --porcelain -- logs/telegram_sent.json', block,
                      "an unchanged ledger must not produce an empty commit")
        self.assertIn("[skip ci]", block.split("- name:")[0],
                      "a ledger push that fires Verify burns the free plan's minutes")

    def test_the_poster_writes_no_entry_when_nothing_was_accepted(self):
        block = (ROOT / "scripts" / "post_telegram.py").read_text(encoding="utf-8")
        body = block.split("def post_to_telegram(")[1].split("\ndef ")[0]
        self.assertLess(body.index("if ok:"), body.index("ledger.record("),
                        "recording intent would turn the ledger into a wish")
        self.assertLess(body.index("already_sent("), body.index("send_text_message("),
                        "the duplicate check has to happen before the send, not after")


class LedgerFailureTests(LedgerTestCase):
    def test_a_corrupt_ledger_never_blocks_the_channel(self):
        """Bookkeeping must not be able to silence a lane. The tool backs the file up
        and starts empty; the poster must publish, not refuse to guess."""
        self.ledger_path.write_text("{ not json", encoding="utf-8")
        self.responses = [ok(message_id=12)]
        sent, _ = self.run_poster()
        self.assertEqual(sent, 1)
        self.assertEqual(len(self.entries()), 1)

    def test_a_missing_ledger_is_an_empty_history_not_an_error(self):
        self.responses = [ok(message_id=13)]
        sent, out = self.run_poster()
        self.assertEqual(sent, 1)
        self.assertIn("ledger: empty", out)

    def test_no_credentials_is_a_failure_not_a_skip(self):
        with patch.object(post_telegram, "TELEGRAM_BOT_TOKEN", None):
            sent, out = self.run_poster()
        self.assertEqual(sent, -1, "-1 is the exit-1 path; 0 would read as \"already sent\"")
        self.assertIn("missing credentials", out)

    def test_an_empty_content_file_is_a_failure(self):
        with patch.object(post_telegram, "load_content", lambda: []):
            sent, out = self.run_poster()
        self.assertEqual(sent, -1)
        self.assertIn("No content to post", out)


class LedgerDateTests(unittest.TestCase):
    def test_the_ledger_day_is_lagos_not_utc(self):
        """A 23:30Z post is tomorrow's publish in the clock the channel runs on. Get
        this wrong and a lane that posts at 00:20 Lagos is recorded yesterday, which
        makes a same-day re-run look legal."""
        self.assertEqual(post_telegram.WAT, timedelta(hours=1))
        late = datetime(2026, 10, 13, 23, 30) + post_telegram.WAT
        self.assertEqual(late.date(), date(2026, 10, 14))
        self.assertEqual(post_telegram.run_date(),
                         (datetime.utcnow() + post_telegram.WAT).date())

    def test_the_window_is_a_week_and_is_overridable(self):
        """A week is the number that blocks the accident (retries, re-dispatches) and
        still lets the rotation return; it is also an env var, because the day the
        window is wrong the fix must not need a commit."""
        self.assertEqual(post_telegram.DUPLICATE_WINDOW_DAYS, 7)
        source = (ROOT / "scripts" / "post_telegram.py").read_text(encoding="utf-8")
        self.assertIn("TELEGRAM_DUP_WINDOW_DAYS", source)

    def test_an_undated_entry_counts_as_recent(self):
        """Inherited from the ledger tool and worth pinning here: an entry we cannot
        place in time must block a re-post rather than permit one."""
        key = post_telegram.content_key("tip", "x")
        self.assertIsNotNone(post_telegram.already_sent([{"title": key, "date": ""}],
                                                        key, date(2026, 10, 13)))


class TestSuiteHygieneTests(unittest.TestCase):
    """1,468 lines of test chatter ended up in the repo's real `logs/social_media.log`,
    because the poster opens that path at import time and nothing redirected it. A log
    the tests scribble on is not evidence for anyone, and a ledger the tests scribble on
    is a lane that refuses to publish for real.

    So the knobs are the contract, and this tests the knobs — not the accident. An
    assertion that "the repo's file was untouched" would depend on which test module
    unittest imports first, which is not a property anyone can keep.
    """

    def test_the_paths_are_configurable_for_a_test_run(self):
        with patch.dict(os.environ, {"TELEGRAM_LOG_FILE": "/tmp/a/log",
                                     "TELEGRAM_LEDGER": "/tmp/a/ledger.json"}):
            module = self.reload()
        try:
            self.assertEqual(str(module.LOG_FILE), "/tmp/a/log")
            self.assertEqual(str(module.LEDGER_FILE), "/tmp/a/ledger.json")
        finally:
            self.reload()

    def test_the_defaults_are_absolute_and_inside_the_repo(self):
        """No env at all — including the suite's own `DOCOGA_LOG_DIR`, which is what
        keeps the repo's log clean. A human running the poster from ~ must still write
        the repo's ledger, not `./logs/` in their home directory."""
        mine = ("TELEGRAM_LOG_FILE", "TELEGRAM_LEDGER", "DOCOGA_LOG_DIR")
        clean = {key: value for key, value in os.environ.items() if key not in mine}
        with patch.dict(os.environ, clean, clear=True):
            module = self.reload()
        try:
            self.assertTrue(module.LOG_FILE.is_absolute(), str(module.LOG_FILE))
            self.assertTrue(module.LEDGER_FILE.is_absolute(), str(module.LEDGER_FILE))
            self.assertEqual(module.LOG_FILE, ROOT / "logs" / "social_media.log")
            self.assertEqual(module.LEDGER_FILE, ROOT / "logs" / "telegram_sent.json")
        finally:
            self.reload()

    def test_an_unwritable_log_does_not_cost_the_channel_its_post(self):
        """`log()` swallows OSError deliberately: a bookkeeping file that cannot be
        opened — read-only checkout, full disk, a directory nobody made — must never be
        the reason a day is missing from the channel."""
        with tempfile.TemporaryDirectory() as tmp:
            blocked = Path(tmp) / "nope" / "social_media.log"
            with patch.object(post_telegram, "LOG_FILE", blocked):
                out = StringIO()
                with redirect_stdout(out):
                    post_telegram.log("the post still matters more than the log")
        self.assertIn("the post still matters more than the log", out.getvalue())
        self.assertFalse(blocked.parent.exists(), "log() must not create directories at send time")

    @staticmethod
    def reload():
        import importlib
        return importlib.reload(post_telegram)


if __name__ == "__main__":
    unittest.main(verbosity=2)
