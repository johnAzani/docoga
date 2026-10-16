#!/usr/bin/env python3
"""
Tests for tools/yt_manage.py — delete / unlist / public from a plan, idempotently.
==================================================================================

Hermetic: the transport is the same FakeGoogle used by test_yt_publish.py, routed by request
shape, so no test reaches Google and nothing can be deleted by accident. The things pinned
here are the ones that would hurt: a token without the write scope must stop *before* any
action (one sentence, not a 403 per line); a done line is never repeated; an update sends
the whole status object back so `embeddable`/`license` are not reset; a delete of a video
that is already gone is a success, not a red run.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import yt_manage  # noqa: E402
from test_yt_publish import FakeGoogle, Resp, CRED_ENV  # noqa: E402

FORCE_SSL = "https://www.googleapis.com/auth/youtube.force-ssl"
UPLOAD_ONLY = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"


class Google(FakeGoogle):
    ROUTES = (("POST", "oauth2.googleapis.com/token", "token"),
              ("GET", "tokeninfo", "tokeninfo"),
              ("GET", "/videos", "list"),
              ("PUT", "/videos", "update"),
              ("DELETE", "/videos", "delete"))


def video(video_id, privacy="public", title="Rent receipt in 60 seconds"):
    return Resp(200, {"items": [{"id": video_id, "snippet": {"title": title, "publishedAt": "2026-10-03T16:00:00Z"},
                                 "status": {"privacyStatus": privacy, "embeddable": True,
                                            "license": "youtube", "publicStatsViewable": True,
                                            "uploadStatus": "processed", "selfDeclaredMadeForKids": False}}]})


class PlanParsing(unittest.TestCase):
    def test_the_owners_message_shape_parses(self):
        plan = yt_manage.parse_plan("delete n45ufAFv5OM\nunlist 2ruPSaR8-M0 oBsWKR4AUNA  # tests")
        self.assertEqual(plan, [("delete", "n45ufAFv5OM", ""),
                                ("unlist", "2ruPSaR8-M0", "tests"),
                                ("unlist", "oBsWKR4AUNA", "tests")])

    def test_semicolons_and_comments(self):
        plan = yt_manage.parse_plan("# header\npublic abcdefghijk; private ABCDEFGHIJ_ # why\n\n")
        self.assertEqual([p[:2] for p in plan], [("public", "abcdefghijk"), ("private", "ABCDEFGHIJ_")])

    def test_bad_lines_are_named(self):
        with self.assertRaises(yt_manage.PlanError):
            yt_manage.parse_plan("remove n45ufAFv5OM")
        with self.assertRaises(yt_manage.PlanError):
            yt_manage.parse_plan("delete https://youtu.be/n45ufAFv5OM")
        with self.assertRaises(yt_manage.PlanError):
            yt_manage.parse_plan("delete")


class Manager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = os.path.join(self.tmp, "youtube_manage.json")
        self.fake = Google()
        self.fake.queue("token", [Resp(200, {"access_token": "ya29.t", "expires_in": 3599})])
        self.scopes(FORCE_SSL)

    def scopes(self, scope):
        self.fake.scripts["tokeninfo"] = [Resp(200, {"scope": scope, "expires_in": 3599})]

    def run_main(self, argv):
        out = io.StringIO()
        with patch.dict(os.environ, CRED_ENV, clear=False), redirect_stdout(out), redirect_stderr(out):
            code = yt_manage.main(argv + ["--ledger", self.ledger], http=self.fake)
        return code, out.getvalue()

    def test_a_token_without_the_write_scope_stops_before_touching_anything(self):
        self.scopes(UPLOAD_ONLY)
        code, out = self.run_main(["delete", "n45ufAFv5OM"])
        self.assertEqual(code, 2, out)
        self.assertIn("youtube.force-ssl", out)
        self.assertIn("OAuth Playground", out)
        self.assertEqual(self.fake.of("delete"), [], "no delete may be attempted on a token that cannot")
        self.assertEqual(self.fake.of("status"), [])

    def test_delete_then_unlist_two_recorded_and_not_repeated(self):
        self.fake.queue("status", [video("n45ufAFv5OM"), video("2ruPSaR8-M0"), video("oBsWKR4AUNA", "public")])
        self.fake.queue("delete", [Resp(204, "")])
        self.fake.queue("update", [Resp(200, {"status": {"privacyStatus": "unlisted"}})])
        code, out = self.run_main(["--plan-text", "delete n45ufAFv5OM; unlist 2ruPSaR8-M0 oBsWKR4AUNA"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.fake.of("delete")), 1)
        self.assertEqual(self.fake.of("delete")[0]["params"], {"id": "n45ufAFv5OM"})
        self.assertEqual(len(self.fake.of("update")), 2)
        ledger = json.loads(Path(self.ledger).read_text())
        self.assertEqual([(r["action"], r["video_id"], r["result"]) for r in ledger["done"]],
                         [("delete", "n45ufAFv5OM", "deleted"), ("unlist", "2ruPSaR8-M0", "unlisted"),
                          ("unlist", "oBsWKR4AUNA", "unlisted")])
        # Run it again: nothing is asked of Google at all.
        calls_before = len(self.fake.calls)
        code, out = self.run_main(["--plan-text", "delete n45ufAFv5OM; unlist 2ruPSaR8-M0 oBsWKR4AUNA"])
        self.assertEqual(code, 0, out)
        self.assertIn("Nothing to do", out)
        self.assertEqual(len(self.fake.calls), calls_before)

    def test_an_update_sends_the_whole_status_back_with_only_privacy_changed(self):
        self.fake.queue("status", [video("2ruPSaR8-M0", "public")])
        self.fake.queue("update", [Resp(200, {"status": {"privacyStatus": "unlisted"}})])
        code, out = self.run_main(["unlist", "2ruPSaR8-M0"])
        self.assertEqual(code, 0, out)
        call = self.fake.of("update")[0]
        self.assertEqual(call["params"], {"part": "status"})
        body = json.loads(call["data"])
        self.assertEqual(body["id"], "2ruPSaR8-M0")
        self.assertEqual(body["status"]["privacyStatus"], "unlisted")
        self.assertTrue(body["status"]["embeddable"], "omitting a mutable field resets it — send it back")
        self.assertEqual(body["status"]["license"], "youtube")
        self.assertNotIn("uploadStatus", body["status"], "read-only fields are not ours to send")

    def test_already_gone_and_already_unlisted_are_successes(self):
        self.fake.queue("status", [Resp(200, {"items": []}), video("2ruPSaR8-M0", "unlisted")])
        code, out = self.run_main(["--plan-text", "delete n45ufAFv5OM; unlist 2ruPSaR8-M0"])
        self.assertEqual(code, 0, out)
        self.assertEqual(self.fake.of("delete"), [])
        self.assertEqual(self.fake.of("update"), [])
        ledger = json.loads(Path(self.ledger).read_text())
        self.assertEqual([r["result"] for r in ledger["done"]], ["already-gone", "already-unlisted"])

    def test_a_refused_delete_is_exit_3_and_stays_pending(self):
        self.fake.queue("status", [video("n45ufAFv5OM")])
        self.fake.queue("delete", [Resp(403, {"error": {"code": 403, "message": "quota",
                                                        "errors": [{"reason": "quotaExceeded"}]}})])
        code, out = self.run_main(["delete", "n45ufAFv5OM"])
        self.assertEqual(code, 3, out)
        self.assertFalse(Path(self.ledger).exists() and json.loads(Path(self.ledger).read_text()).get("done"),
                         "a refused line must not be recorded as done")

    def test_dry_run_reads_and_changes_nothing(self):
        self.fake.queue("status", [video("n45ufAFv5OM")])
        code, out = self.run_main(["--dry-run", "delete", "n45ufAFv5OM"])
        self.assertEqual(code, 0, out)
        self.assertIn("would delete", out)
        self.assertEqual(self.fake.of("delete"), [])
        self.assertFalse(Path(self.ledger).exists())

    def test_scopes_flag_reports_the_verdict(self):
        code, out = self.run_main(["--scopes"])
        self.assertEqual(code, 0, out)
        self.assertIn("can delete", out)
        self.scopes(UPLOAD_ONLY)
        code, out = self.run_main(["--scopes"])
        self.assertEqual(code, 2, out)

    def test_malformed_plan_is_exit_4_without_a_token(self):
        code, out = self.run_main(["--plan-text", "remove n45ufAFv5OM"])
        self.assertEqual(code, 4, out)
        self.assertEqual(self.fake.calls, [])


class RepoPlan(unittest.TestCase):
    def test_the_committed_plan_parses(self):
        text = (ROOT / "logs" / "youtube_cleanup_plan.txt").read_text(encoding="utf-8")
        plan = yt_manage.parse_plan(text)
        self.assertTrue(plan, "the plan file exists to be run; an empty one is a mistake")


if __name__ == "__main__":
    unittest.main()
