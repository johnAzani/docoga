#!/usr/bin/env python3
"""
tools/shorts_handoff.py — the Short handed to the Threads evening slot (owner, 21 Oct 2026:
"Threads has never posted videos"). Hermetic: the KV fake from test_media_host answers.
"""
import io
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import shorts_handoff as sh  # noqa: E402
from test_media_host import FakeHttp  # noqa: E402

ENV = {"CLOUDFLARE_API_TOKEN": "cf-token-for-tests", "CLOUDFLARE_ACCOUNT_ID": "acct"}
NOW = datetime(2026, 10, 21, 17, 24, tzinfo=timezone.utc)   # 6:24pm Lagos, the Short just uploaded


class Handoff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.video = os.path.join(self.tmp, "docoga_short_20261021.mp4")
        with open(self.video, "wb") as fh:
            fh.write(b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 300)
        self.ledger = Path(self.tmp) / "shorts_media.json"

    def test_host_writes_the_url_and_today_finds_it_until_it_expires(self):
        fake = FakeHttp(size=76824)
        out = io.StringIO()
        with redirect_stdout(out):
            rec = sh.host(self.video, "Np1VY20sxRQ", "Rent receipt: the 7 lines #Shorts", ledger=self.ledger,
                          env=ENV, http=fake, sleeper=lambda s: None, now=NOW, ttl_hours=30)
        self.assertTrue(rec["url"].endswith(".mp4"))
        self.assertEqual(rec["date"], "2026-10-21", "Lagos day, not UTC")
        self.assertIn("HANDOFF_URL=%s" % rec["url"], out.getvalue())
        kv_puts = [c for c in fake.calls if c[0] == "PUT"]
        self.assertTrue(kv_puts, "the file went to KV")
        for _m, url, _h in kv_puts:
            self.assertIn("expiration_ttl=108000", url, "30 hours — gone by itself, no clean-up job")
        data = json.loads(self.ledger.read_text())
        self.assertEqual(data["latest"]["video_id"], "Np1VY20sxRQ")
        self.assertEqual(len(data["history"]), 1)
        # 8:10pm the same evening: the Threads lane finds it.
        evening = NOW + timedelta(hours=1, minutes=46)
        self.assertEqual(sh.today(ledger=self.ledger, now=evening)["url"], rec["url"])
        # The next evening it is still hosted, but it is yesterday's Short — not tonight's post.
        self.assertIsNone(sh.today(ledger=self.ledger, now=evening + timedelta(days=1)))
        # And a record whose hosting ends in the next 20 minutes is not offered either.
        self.assertIsNone(sh.today(ledger=self.ledger, now=NOW + timedelta(hours=29, minutes=50)))

    def test_hosting_twice_in_a_day_keeps_one_record_per_day(self):
        fake = FakeHttp(size=76824)
        with redirect_stdout(io.StringIO()):
            sh.host(self.video, "aaaaaaaaaaa", "first", ledger=self.ledger, env=ENV, http=fake,
                    sleeper=lambda s: None, now=NOW)
            sh.host(self.video, "bbbbbbbbbbb", "second", ledger=self.ledger, env=ENV, http=fake,
                    sleeper=lambda s: None, now=NOW + timedelta(minutes=5))
            sh.host(self.video, "ccccccccccc", "tomorrow", ledger=self.ledger, env=ENV, http=fake,
                    sleeper=lambda s: None, now=NOW + timedelta(days=1))
        data = json.loads(self.ledger.read_text())
        self.assertEqual([r["video_id"] for r in data["history"]], ["bbbbbbbbbbb", "ccccccccccc"])
        self.assertEqual(sh.today(ledger=self.ledger, now=NOW + timedelta(hours=2))["video_id"], "bbbbbbbbbbb")

    def test_cli_today_prints_the_machine_lines_and_never_fails(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = sh.main(["today", "--ledger", str(self.ledger)])
        self.assertEqual(code, 0)
        self.assertIn("THREADS_VIDEO_URL=\n", out.getvalue(), "an empty URL line, so the workflow's sed reads nothing")
        fake = FakeHttp(size=76824)
        with redirect_stdout(io.StringIO()):
            sh.host(self.video, "Np1VY20sxRQ", "Rent  receipt:\nthe 7 lines", ledger=self.ledger, env=ENV, http=fake,
                    sleeper=lambda s: None, now=datetime.now(timezone.utc))
        out = io.StringIO()
        with redirect_stdout(out):
            code = sh.main(["today", "--ledger", str(self.ledger)])
        self.assertEqual(code, 0)
        self.assertRegex(out.getvalue(), r"THREADS_VIDEO_URL=https://\S+\.mp4\n")
        self.assertIn("THREADS_VIDEO_TITLE=Rent receipt: the 7 lines\n", out.getvalue(), "one line, whitespace folded")

    def test_cli_host_without_the_secrets_is_a_warning_and_exit_2(self):
        out = io.StringIO()
        with redirect_stdout(out), unittest.mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "", "CLOUDFLARE_ACCOUNT_ID": ""}):
            code = sh.main(["host", "--video", self.video, "--video-id", "Np1VY20sxRQ", "--ledger", str(self.ledger)])
        self.assertEqual(code, 2)
        self.assertIn("::warning title=Short not handed to Threads::", out.getvalue())
        self.assertIn("HANDOFF_URL=\n", out.getvalue())
        self.assertFalse(self.ledger.exists(), "nothing is recorded that was not hosted")


if __name__ == "__main__":
    unittest.main()
