"""tools/yt_boost.py — the series playlist and the first comment, after every publish.

Hermetic: a scripted Google routed by method + path; no network, no credentials. The ledger is
a temp file. What is pinned:
  * a planned video gets the playlist (created once, found afterwards) and, once public, the comment;
  * a scheduled (private) video gets the playlist now and the comment waits — nothing is lost;
  * the publish ledgers feed the plan, so videos from before the tool existed are caught up;
  * the sweep is idempotent and bounded (`--max`), and no failure escapes as a non-zero exit.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import yt_boost  # noqa: E402
import yt_publish  # noqa: E402


class Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class Google:
    """Routes: videos.list → 'status'; playlists GET/POST; playlistItems GET/POST; commentThreads POST."""

    def __init__(self, privacy="public", playlists=()):
        self.privacy = privacy
        self.playlists = {t: "PL%d" % i for i, t in enumerate(playlists)}
        self.items = {}         # playlist_id -> {video_id}
        self.comments = []      # (video_id, text)
        self.calls = []
        self.fail = {}          # route -> Resp

    def request(self, method, url, headers=None, data=None, params=None, files=None):
        params = params or {}
        body = json.loads(data) if data else {}
        route = (method, url.rsplit("/", 1)[-1])
        self.calls.append((route, params, body))
        if route in self.fail:
            return self.fail[route]
        if route == ("GET", "videos"):
            return Resp(200, {"items": [{"id": params["id"], "snippet": {"title": "T"},
                                         "status": {"privacyStatus": self.privacy, "uploadStatus": "processed"}}]})
        if route == ("GET", "playlists"):
            return Resp(200, {"items": [{"id": pid, "snippet": {"title": t}} for t, pid in self.playlists.items()]})
        if route == ("POST", "playlists"):
            pid = "PLNEW%d" % len(self.playlists)
            self.playlists[body["snippet"]["title"]] = pid
            return Resp(200, {"id": pid})
        if route == ("GET", "playlistItems"):
            have = params["videoId"] in self.items.get(params["playlistId"], set())
            return Resp(200, {"items": [{"id": "PI-old"}] if have else []})
        if route == ("POST", "playlistItems"):
            pid, vid = body["snippet"]["playlistId"], body["snippet"]["resourceId"]["videoId"]
            self.items.setdefault(pid, set()).add(vid)
            return Resp(200, {"id": "PI-%s" % vid})
        if route == ("POST", "commentThreads"):
            self.comments.append((body["snippet"]["videoId"], body["snippet"]["topLevelComment"]["snippet"]["textOriginal"]))
            return Resp(200, {"id": "C-%s" % body["snippet"]["videoId"]})
        return Resp(404, {"error": {"message": "no route"}})


def run(argv, google, ledger):
    out = io.StringIO()
    with mock.patch.object(yt_publish, "authorize", lambda http=None: (google, {})), redirect_stdout(out):
        code = yt_boost.main(argv + ["--ledger", str(ledger)] if argv[0] != "show" else argv, http=google)
    return code, out.getvalue()


class Boosts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "boosts.json"
        self._env = mock.patch.dict(os.environ, {"YT_BOOST_LEDGER": str(self.ledger)})
        self._env.start()
        yt_boost.LEDGER = self.ledger

    def tearDown(self):
        self._env.stop()
        self.tmp.cleanup()

    def test_public_short_gets_the_playlist_and_the_first_comment(self):
        g = Google()
        code, out = run(["plan", "--video-id", "abc", "--kind", "short", "--title", "Pay without a receipt",
                         "--parent-comment", "Full episode (free, 9 minutes): Rent receipts — https://youtu.be/dd3"], g, self.ledger)
        self.assertEqual(code, 0)
        code, out = run(["run", "--no-import"], g, self.ledger)
        self.assertEqual(code, 0)
        self.assertIn("YT_BOOST_RESULT=swept", out)
        self.assertEqual(len(g.comments), 1)
        vid, text = g.comments[0]
        self.assertEqual(vid, "abc")
        self.assertTrue(text.startswith("Full episode"))
        self.assertIn("docoga.com.ng/?s=yt", text)
        self.assertIn("?", text)                           # a question, not a billboard
        self.assertEqual(g.items["PLNEW0"], {"abc"})       # the Shorts playlist was created, public
        created = [b for r, p, b in g.calls if r == ("POST", "playlists")]
        self.assertEqual(created[0]["status"]["privacyStatus"], "public")
        self.assertIn("Nigeria", created[0]["snippet"]["title"])
        rows = yt_boost.load(self.ledger)
        self.assertEqual(rows[0]["comment_id"], "C-abc")
        self.assertEqual(rows[0]["playlist_item_id"], "PI-abc")
        self.assertIn("YT_BOOST_PENDING=0", out)

    def test_private_scheduled_video_gets_the_playlist_now_and_the_comment_later(self):
        g = Google(privacy="private")
        run(["plan", "--video-id", "sch", "--kind", "deepdive", "--title", "Caution fee"], g, self.ledger)
        code, out = run(["run", "--no-import"], g, self.ledger)
        self.assertEqual(code, 0)
        self.assertEqual(g.comments, [])
        self.assertEqual(g.items["PLNEW0"], {"sch"})
        self.assertIn("waits for the public slot", out)
        self.assertIn("YT_BOOST_PENDING=1", out)
        g.privacy = "public"                                # the slot came
        run(["run", "--no-import"], g, self.ledger)
        self.assertEqual([v for v, _ in g.comments], ["sch"])
        # the second sweep did not add it to the playlist twice
        self.assertEqual(sum(1 for r, _, _ in g.calls if r == ("POST", "playlistItems")), 1)
        self.assertEqual(len(yt_boost.load(self.ledger)), 1)

    def test_existing_playlist_is_found_not_duplicated(self):
        g = Google(playlists=(yt_boost.PLAYLISTS["short"]["title"],))
        run(["plan", "--video-id", "v1", "--kind", "short"], g, self.ledger)
        run(["run", "--no-import"], g, self.ledger)
        self.assertFalse([1 for r, _, _ in g.calls if r == ("POST", "playlists")])
        self.assertEqual(g.items["PL0"], {"v1"})

    def test_publish_ledgers_feed_the_plan_and_the_sweep_is_bounded(self):
        shorts = Path(self.tmp.name) / "shorts.json"
        longform = Path(self.tmp.name) / "long.json"
        shorts.write_text(json.dumps([{"video_id": "s%d" % i, "topic": "T%d" % i, "state": "published",
                                       "date": "2026-10-0%d" % (i + 1)} for i in range(5)]
                                     + [{"video_id": "bad", "state": "rejected"}]), encoding="utf-8")
        longform.write_text(json.dumps([{"video_id": "L1", "topic": "Deep", "state": "scheduled"}]), encoding="utf-8")
        rows = []
        added = yt_boost.import_publish_ledgers(rows, shorts=shorts, longform=longform)
        self.assertEqual(added, 6)
        self.assertEqual({r["kind"] for r in rows}, {"short", "deepdive"})
        self.assertNotIn("bad", [r["video_id"] for r in rows])
        self.assertEqual(yt_boost.import_publish_ledgers(rows, shorts=shorts, longform=longform), 0)
        yt_boost.save(rows, self.ledger)
        g = Google()
        code, out = run(["run", "--no-import", "--max", "2"], g, self.ledger)
        self.assertEqual(code, 0)
        self.assertEqual(len(g.comments), 2)
        self.assertIn("YT_BOOST_PENDING=4", out)

    def test_api_refusals_are_warnings_not_failures(self):
        g = Google()
        g.fail[("POST", "commentThreads")] = Resp(403, {"error": {"errors": [{"reason": "commentsDisabled"}]}})
        run(["plan", "--video-id", "nc", "--kind", "short"], g, self.ledger)
        code, out = run(["run", "--no-import"], g, self.ledger)
        self.assertEqual(code, 0)
        self.assertIn("::warning", out)
        rows = yt_boost.load(self.ledger)
        self.assertTrue(rows[0]["gave_up"])
        self.assertEqual(rows[0]["playlist_item_id"], "PI-nc")   # the playlist still happened
        code, out = run(["run", "--no-import"], g, self.ledger)
        self.assertIn("nothing-pending", out)

    def test_no_credentials_is_a_warning_and_the_plan_survives(self):
        run(["plan", "--video-id", "p", "--kind", "short"], Google(), self.ledger)
        out = io.StringIO()

        def boom(http=None):
            raise yt_publish.Problem("credentials", "missing_secret", "YT_CLIENT_ID is not set.", "Add it.")
        with mock.patch.object(yt_publish, "authorize", boom), redirect_stdout(out):
            code = yt_boost.main(["run", "--no-import", "--ledger", str(self.ledger)])
        self.assertEqual(code, 0)
        self.assertIn("YT_BOOST_RESULT=no-credentials", out.getvalue())
        self.assertEqual(len(yt_boost.pending(yt_boost.load(self.ledger))), 1)

    def test_default_comment_reads_as_a_person(self):
        text = yt_boost.default_comment("deepdive", "Caution fee")
        self.assertIn("?", text)
        self.assertNotIn("http", text.split("\n")[0])      # question first, link last
        self.assertLessEqual(len(text), yt_boost.MAX_COMMENT)


if __name__ == "__main__":
    unittest.main()
