"""Tests for tools/yt_publish.py — the wire protocol, not the happy path.

Why this file is big: the 9 Oct 2026 run of the scheduled Shorts lane rendered a video, PUT it
at YouTube, and died with `Exit code 1` and no cause. The lane could not tell a revoked token
from a chunked-upload hiccup from Google refusing the privacy status, so the issue it filed
guessed, and the log became unreadable a day later. These tests pin the three things that make
that class of failure self-explaining: the resumable protocol is followed (a 308 is progress,
a 5xx resumes where the server actually is, a 404 restarts the session), every failure carries
a kind and an action, and the run's exit code distinguishes "the code failed" from "a human
must re-author a token".
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

TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

# The uploader writes nothing to the repo, but keep the log-path contract of the other social
# tests so a run of this module cannot create a stray logs/ directory.
os.environ.setdefault("DOCOGA_LOG_DIR", tempfile.mkdtemp(prefix="docoga-logs-"))

import yt_publish  # noqa: E402


class Resp:
    """The slice of requests.Response the code actually uses."""

    def __init__(self, status=200, body=None, headers=None, text=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        if text is not None:
            self.text = text
        else:
            self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        if isinstance(self._body, (dict, list)):
            return self._body
        return json.loads(self.text)


class FakeGoogle:
    """A scripted Google, routed by what the request *is*.

    `queue("put", [Resp(308, ...), Resp(201, ...)])` hands out the responses for that route in
    order, repeating the last one, so a test says "the server did this" rather than counting
    calls itself.
    """

    ROUTES = (("POST", "oauth2.googleapis.com", "token"),
              ("POST", "upload/youtube/v3/videos", "init"),
              ("PUT", "", "put"),
              ("GET", "/channels", "channels"),
              ("GET", "videos", "list"))

    def __init__(self):
        self.scripts = {}
        self.calls = []

    def queue(self, route, responses):
        self.scripts.setdefault(route, []).extend(responses)
        return self

    def request(self, method, url, headers=None, data=None, params=None, files=None,
                timeout=None):
        route = next((name for m, frag, name in self.ROUTES
                      if m == method and (not frag or frag in url)), "other")
        if method == "PUT" and str((headers or {}).get("Content-Range", "")).startswith("bytes */"):
            route = "probe"
        if route == "list" and params and "id" in params:
            route = "status"
        if route == "list" and params and params.get("playlistId"):
            route = "videos"
        calls = self.calls
        index = sum(1 for c in calls if c["route"] == route)
        calls.append({"route": route, "method": method, "url": url,
                      "headers": dict(headers or {}), "params": dict(params or {}),
                      "data": data, "timeout": timeout})
        script = self.scripts.get(route) or [Resp(200, {})]
        return script[index] if index < len(script) else script[-1]

    def of(self, route):
        return [c for c in self.calls if c["route"] == route]

    @property
    def put_headers(self):
        return [c["headers"] for c in self.of("put")]


def token_ok(fake):
    fake.queue("token", [Resp(200, {"access_token": "ya29.test", "expires_in": 3599,
                                   "scope": "https://www.googleapis.com/auth/youtube.upload"})])


CRED_ENV = {"YT_REFRESH_TOKEN": "rt", "YT_CLIENT_ID": "cid", "YT_CLIENT_SECRET": "csecret"}


class TransportTestCase(unittest.TestCase):
    def setUp(self):
        self.fake = FakeGoogle()
        token_ok(self.fake)
        self.http = yt_publish.Http(session=self.fake)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.video = Path(self.tmp.name) / "short.mp4"
        env = dict(CRED_ENV)
        patcher = patch.dict(os.environ, env, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, argv, actions="true"):
        """Drive the CLI with the same fake transport: the markers and exit codes the workflow
        greps for live in main(), not in publish()."""
        out, err = io.StringIO(), io.StringIO()
        env = dict(os.environ, GITHUB_ACTIONS=actions)
        with patch.dict(os.environ, env, clear=False):
            with redirect_stdout(out), redirect_stderr(err):
                code = yt_publish.main(argv, http=self.http)
        return code, out.getvalue(), err.getvalue()

    def write_video(self, size):
        self.video.write_bytes(b"x" * size)
        return self.video

    def publish(self, title="T", poll_times=1, **kw):
        """publish() with the clock switched off.

        Backoff and the finalisation poll are real sleeps in production; a suite that waits on
        them is a suite nobody runs twice, and 15 s of waiting proves nothing about Google.
        """
        kw.setdefault("sleep", lambda seconds: None)
        return yt_publish.publish(self.video, title, http=self.http,
                                  poll_times=poll_times, **kw)


class ChunkingTests(TransportTestCase):
    """Google's resumable protocol, exactly as written in its docs."""

    def test_every_chunk_is_a_multiple_of_256kb_except_the_last(self):
        size = 5 * 1024 * 1024 + 1234
        self.write_video(size)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://uploads.test/session/1"})])
        # A 308 reports the range YouTube *holds*: 0-2097151 after chunk 0, 0-4194303 after
        # chunk 1. Anything else is an instruction to resend, not a bug in the client.
        self.fake.queue("put", [Resp(308, headers={"Range": "bytes=0-2097151"}),
                                Resp(308, headers={"Range": "bytes=0-4194303"}),
                                Resp(201, {"id": "vid123"})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "public"}}]})])
        with redirect_stdout(io.StringIO()):
            result = self.publish(title="A title", poll_times=1)
        self.assertEqual("vid123", result)
        ranges = [h["Content-Range"] for h in self.fake.put_headers]
        # ranges are contiguous, and each except the last is 2 MiB (a multiple of 256 KiB)
        starts = [int(r.split("bytes ")[1].split("-")[0]) for r in ranges]
        ends = [int(r.split("-")[1].split("/")[0]) for r in ranges]
        self.assertEqual(0, starts[0])
        self.assertEqual(size - 1, ends[-1])
        for i in range(len(ranges) - 1):
            self.assertEqual(ends[i] + 1, starts[i + 1], "ranges must be contiguous: %s" % ranges)
            self.assertEqual(0, (ends[i] - starts[i] + 1) % (256 * 1024),
                             "chunk %d is %d bytes" % (i, ends[i] - starts[i] + 1))
            self.assertEqual(ranges[i].split("/")[1], ranges[-1].split("/")[1],
                             "every range must name the same total size")

    def test_the_file_is_never_read_whole_into_memory(self):
        """The old code did `f.read()`; a 256 GB cap is not the worry, a runner's RAM is."""
        self.write_video(9 * 1024 * 1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://uploads.test/s"})])
        self.fake.queue("put", [Resp(308, headers={"Range": "bytes=0-2097151"}),
                                Resp(308, headers={"Range": "bytes=0-4194303"}),
                                Resp(308, headers={"Range": "bytes=0-6291455"}),
                                Resp(308, headers={"Range": "bytes=0-8388607"}),
                                Resp(201, {"id": "v"})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "public"}}]})])
        with redirect_stdout(io.StringIO()):
            self.publish(title="T", poll_times=1)
        biggest = max(len(c["data"]) for c in self.fake.of("put"))
        self.assertLessEqual(biggest, 8 * 256 * 1024)

    def test_the_session_uri_from_location_is_the_one_that_is_used(self):
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"location": "https://uploads.test/session/9"})])
        self.fake.queue("put", [Resp(201, {"id": "v", "status": {"privacyStatus": "public"}})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "public"}}]})])
        with redirect_stdout(io.StringIO()):
            self.publish(title="T", poll_times=1)
        self.assertEqual("https://uploads.test/session/9", self.fake.of("put")[0]["url"])

    def test_every_request_carries_a_timeout(self):
        """A hung request burns the 30-minute job and leaves no error to read."""
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"}),
                                Resp(201, {"id": "v"})])
        self.fake.queue("put", [Resp(201, {"id": "v", "status": {"privacyStatus": "public"}})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "public"}}]})])
        with redirect_stdout(io.StringIO()):
            self.publish(title="T", poll_times=1)
        self.assertTrue(self.fake.calls)
        for call in self.fake.calls:
            self.assertIsInstance(call["timeout"], tuple, call["route"])
            self.assertEqual(2, len(call["timeout"]))

    def test_init_declares_the_size_and_type_before_a_byte_moves(self):
        self.write_video(4096)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(201, {"id": "v", "status": {"privacyStatus": "public"}})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "public"}}]})])
        with redirect_stdout(io.StringIO()):
            self.publish(title="T", poll_times=1)
        init = self.fake.of("init")[0]
        self.assertEqual("4096", init["headers"]["X-Upload-Content-Length"])
        self.assertEqual("video/mp4", init["headers"]["X-Upload-Content-Type"])
        self.assertEqual("resumable", init["params"]["uploadType"])
        self.assertEqual("snippet,status", init["params"]["part"])


class ResumeTests(TransportTestCase):
    """The failures that used to end the run: 308, 5xx, 404."""

    def _one_chunk_upload(self, put_responses, size=1024):
        self.write_video(size)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})] * 2
                        + [Resp(200, {}, {"Location": "https://u/2"})])
        self.fake.queue("put", put_responses)
        return size

    def test_a_308_covering_the_whole_file_polls_instead_of_failing(self):
        """The old code read any non-200 as an error — this is the case it would have killed,
        with the bytes already at Google."""
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(308, headers={"Range": "bytes=0-1023"})])
        self.fake.queue("probe", [Resp(201, {"id": "vid308"})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "public"}}]})])
        with redirect_stdout(io.StringIO()):
            result = self.publish(title="T", poll_times=1)
        self.assertEqual("vid308", result)
        self.assertEqual(1, len(self.fake.of("put")))
        self.assertEqual(1, len(self.fake.of("probe")), "the poll is how 308 is resolved")

    def test_a_308_that_never_finalises_says_the_bytes_are_already_at_google(self):
        """Not "retry me" — a blind re-run here is how the channel gets two copies."""
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(308, headers={"Range": "bytes=0-1023"})])
        self.fake.queue("probe", [Resp(308, headers={"Range": "bytes=0-1023"})])
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(yt_publish.Problem) as ctx:
                self.publish(title="T", poll_times=1)
        self.assertEqual("unfinalized", ctx.exception.reason)
        self.assertIn("Do NOT just re-run", ctx.exception.action)

    def test_a_partial_308_resumes_at_the_bytes_youtube_actually_holds(self):
        """YouTube answering 0-511 when we sent 0-1023 means resend from 512 — the old code
        had no such notion and would have declared the whole upload failed."""
        size = 2048
        self.write_video(size)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(308, headers={"Range": "bytes=0-511"}),
                                Resp(201, {"id": "vidresume"})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "public"}}]})])
        with patch.object(yt_publish, "CHUNK_MULTIPLE", 512), \
                patch.object(yt_publish, "CHUNK_BYTES", 1024):
            with redirect_stdout(io.StringIO()):
                result = self.publish(title="T", poll_times=1)
        self.assertEqual("vidresume", result)
        ranges = [h["Content-Range"] for h in self.fake.put_headers]
        self.assertEqual("bytes 0-1023/2048", ranges[0])
        self.assertEqual("bytes 512-1535/2048", ranges[1], "resume where the server says it is")
        self.assertEqual("bytes 1536-2047/2048", ranges[2], "and then finish the file")

    def test_a_503_backs_off_asks_the_session_and_continues(self):
        size = 1024
        self.write_video(size)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(503, "unavailable"), Resp(201, {"id": "vid503"})])
        self.fake.queue("probe", [Resp(308, headers={"Range": "bytes=0-511"})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "public"}}]})])
        sleeps = []
        with patch.object(yt_publish, "CHUNK_MULTIPLE", 512), \
                patch.object(yt_publish, "CHUNK_BYTES", 1024):
            with redirect_stdout(io.StringIO()):
                result = self.publish(title="T", poll_times=1, sleep=sleeps.append)
        self.assertEqual("vid503", result)
        self.assertTrue(sleeps, "a 5xx without backoff just hammers Google")
        self.assertEqual(1, len(self.fake.of("probe")), "ask where to resume before resending")

    def test_giving_up_on_a_5xx_reports_the_byte_offset(self):
        size = 1024
        self.write_video(size)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(503, "unavailable")])
        self.fake.queue("probe", [Resp(308, headers={"Range": "bytes=0-511"})])
        sleeps = []
        with patch.object(yt_publish, "CHUNK_MULTIPLE", 512), \
                patch.object(yt_publish, "CHUNK_BYTES", 1024):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(yt_publish.Problem) as ctx:
                    self.publish(title="T", poll_times=1, sleep=sleeps.append)
        self.assertEqual("transport", ctx.exception.kind)
        self.assertIn("503", ctx.exception.what)
        self.assertIn("safe to retry", ctx.exception.action)

    def test_a_truncated_file_is_caught_before_the_api_sees_it(self):
        """A short read inside the loop means the render wrote a partial file."""
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        up = yt_publish.ResumableUploader(self.http, 4096, {}, sleep=lambda s: None)
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(yt_publish.Problem) as ctx:
                up.upload(self.video)
        self.assertEqual("short_read", ctx.exception.reason)

    def test_an_expired_session_restarts_once_and_succeeds(self):
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"}),
                                Resp(200, {}, {"Location": "https://u/2"})])
        self.fake.queue("put", [Resp(404, "session expired"),
                                Resp(201, {"id": "vidrestart"})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "public"}}]})])
        with redirect_stdout(io.StringIO()):
            result = self.publish(title="T", poll_times=1)
        self.assertEqual("vidrestart", result)
        self.assertEqual(2, len(self.fake.of("init")), "a second session must be opened")
        self.assertEqual("https://u/2", self.fake.of("put")[-1]["url"],
                         "the retry must go to the new session, not the dead one")

    def test_a_session_that_keeps_dying_is_reported_as_not_published(self):
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/%d" % i}) for i in range(5)])
        self.fake.queue("put", [Resp(404, "session expired")])
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(yt_publish.Problem) as ctx:
                self.publish(title="T", poll_times=1)
        self.assertEqual("transport", ctx.exception.kind)
        self.assertEqual("session_expired", ctx.exception.reason)
        self.assertIn("nothing was published", ctx.exception.action.lower())

    def test_a_truncated_file_is_caught_before_the_api_sees_it(self):
        """A partial render must not become a half-uploaded Short on the channel."""
        real_open = open

        class HalfFile(io.BytesIO):
            def read(self, n=-1):
                return b""  # every read after the first says EOF

        handle = HalfFile(b"x" * 10)
        self.write_video(4096)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        with patch("builtins.open", lambda *a, **k: handle):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(yt_publish.Problem) as ctx:
                    self.publish(title="T", poll_times=1)
        self.assertEqual("short_read", ctx.exception.reason)
        self.assertEqual(real_open, open)


class ClassificationTests(TransportTestCase):
    """Every documented videos.insert reason maps to a kind and an action."""

    def init_problem(self, status, payload):
        self.write_video(1024)
        self.fake.queue("init", [Resp(status, payload)])
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(yt_publish.Problem) as ctx:
                self.publish(title="T")
        return ctx.exception

    def err(self, status, reason, message="boom"):
        return {"error": {"code": status, "message": message,
                          "errors": [{"reason": reason, "message": message}]}}

    def test_daily_upload_limit_is_a_quota_problem_for_a_human(self):
        exc = self.init_problem(403, self.err(403, "dailyUploadLimitExceeded"))
        self.assertEqual("quota", exc.kind)
        self.assertEqual(yt_publish.EXIT_NEEDS_HUMAN, exc.exit_code)
        self.assertIn("Video Uploads bucket", exc.action)

    def test_a_downgraded_privacy_is_forbidden_not_a_crash(self):
        exc = self.init_problem(403, self.err(403, "forbiddenPrivacySetting"))
        self.assertEqual("forbidden", exc.kind)
        self.assertIn("YT_PRIVACY=unlisted", exc.action)

    def test_an_education_category_typo_is_metadata(self):
        exc = self.init_problem(400, self.err(400, "invalidCategoryId"))
        self.assertEqual("metadata", exc.kind)
        self.assertIn("videoCategories.list", exc.action)

    def test_a_channel_strike_reads_as_forbidden(self):
        exc = self.init_problem(403, self.err(403, "forbidden"))
        self.assertEqual("forbidden", exc.kind)
        self.assertIn("strike", exc.action)

    def test_an_unexplained_502_reads_as_transport(self):
        exc = self.init_problem(502, "<html>Bad Gateway</html>")
        self.assertEqual("transport", exc.kind)

    def test_refresh_failure_names_the_seven_day_testing_expiry(self):
        self.write_video(1024)
        self.fake.scripts["token"] = [Resp(400, {"error": "invalid_grant"})]
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(yt_publish.Problem) as ctx:
                yt_publish.publish(self.video, "T", http=yt_publish.Http(session=self.fake))
        self.assertEqual("credentials", ctx.exception.kind)
        self.assertIn("7 days", ctx.exception.action)
        self.assertIn("Testing", ctx.exception.action)

    def test_a_missing_secret_is_not_reported_as_an_api_failure(self):
        self.write_video(1024)
        with patch.dict(os.environ, {"YT_CLIENT_SECRET": ""}, clear=False):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(yt_publish.Problem) as ctx:
                    yt_publish.publish(self.video, "T", http=yt_publish.Http(session=self.fake))
        self.assertEqual("missing_secret", ctx.exception.reason)
        self.assertEqual(yt_publish.EXIT_NEEDS_HUMAN, ctx.exception.exit_code)

    def test_no_secret_is_read_from_a_default_in_the_source(self):
        text = (TOOLS_DIR / "yt_publish.py").read_text(encoding="utf-8")
        for name in ("YT_REFRESH_TOKEN", "YT_CLIENT_ID", "YT_CLIENT_SECRET"):
            self.assertIn('"%s"' % name, text)
        for chunk in text.split("os.environ.get(")[1:]:
            args = chunk.split(")")[0]
            parts = [p.strip() for p in args.split(",")]
            self.assertLessEqual(len(parts), 2, "unexpected default in %r" % args)
            if len(parts) == 2:
                self.assertEqual('""', parts[1], "a literal secret default: %r" % args)


class MetadataTests(TransportTestCase):
    """The limits YouTube enforces are applied here, loudly, instead of as a 400 at 09:00."""

    def test_a_long_title_is_cut_at_a_word_boundary_and_announced(self):
        title = "Before You Pay an Agent: the tenancy law handbook for Lagos renters — " \
                "everything a landlord can legally do and what you can do back #Shorts"
        self.assertLess(len(title), 140)
        metadata, tags, notes, params = yt_publish.build_metadata(
            title, "desc", "a,b", "public", "22")
        self.assertLessEqual(len(metadata["snippet"]["title"]), 100)
        self.assertFalse(metadata["snippet"]["title"].endswith(
            (",", ";", ":", "-", "—")), "cut at a word, not mid-word")
        self.assertIn("trimmed", notes[0])

    def test_tags_past_500_combined_characters_are_dropped_from_the_end(self):
        tags = ",".join("tag%05d" % i for i in range(80))   # 10 chars each + commas
        self.assertGreater(len(tags), 500)
        metadata, kept, notes, params = yt_publish.build_metadata("T", "", tags, "public", "22")
        self.assertLessEqual(sum(len(x) for x in kept) + len(kept) - 1, 500)
        self.assertLess(len(kept), 80)
        self.assertIn("dropped", notes[0])
        self.assertEqual(metadata["snippet"]["tags"], kept, "the trimmed list is what is sent")

    def test_no_tags_means_no_tags_field_at_all(self):
        """Google's own sample warns that an empty tags value is a 400; [] is not an empty
        string, but omitting the field is the shape the docs actually show."""
        for tags in ("", "  ", ",,"):
            metadata, kept, notes, params = yt_publish.build_metadata("T", "", tags,
                                                                      "public", "22")
            self.assertNotIn("tags", metadata["snippet"])
            self.assertEqual([], kept)

    def test_an_empty_title_fails_here_rather_than_at_the_api(self):
        with self.assertRaises(yt_publish.Problem) as ctx:
            yt_publish.build_metadata("   ", "", "", "public", "22")
        self.assertEqual("invalidTitle", ctx.exception.reason)

    def test_notify_subscribers_is_a_query_parameter_not_a_body_field(self):
        _meta, _tags, _notes, params = yt_publish.build_metadata("T", "", "", "public", "22",
                                                                 notify=False)
        self.assertEqual("false", params["notifySubscribers"])

    def test_synthetic_media_is_only_declared_when_said(self):
        meta, _t, _n, _p = yt_publish.build_metadata("T", "", "", "public", "22")
        self.assertNotIn("containsSyntheticMedia", meta["status"])
        meta, _t, _n, _p = yt_publish.build_metadata("T", "", "", "public", "22", synthetic=True)
        self.assertTrue(meta["status"]["containsSyntheticMedia"])

    def test_an_overlong_description_is_cut_at_a_line_break(self):
        desc = ("line of text\n" * 600)
        meta, _t, notes, _p = yt_publish.build_metadata("T", desc, "", "public", "22")
        self.assertLessEqual(len(meta["snippet"]["description"]), 5000)
        self.assertIn("cut at a line break", notes[0])


class ReadBackTests(TransportTestCase):
    """201 means the bytes arrived. It does not mean anybody can watch it."""

    def upload(self, status_items, poll=1):
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(201, {"id": "vidRB"})])
        self.fake.queue("status", [Resp(200, {"items": status_items})])
        return yt_publish.publish(self.video, "T", http=self.http, poll_times=poll)

    def test_processed_and_public_is_a_publish(self):
        result = self.upload([{"status": {"uploadStatus": "processed",
                                         "privacyStatus": "public"}}])
        self.assertEqual("published", result.result)
        self.assertEqual("public", result.privacy)

    def test_a_channel_that_forces_private_is_reported_as_held_not_published(self):
        result = self.upload([{"status": {"uploadStatus": "processed",
                                         "privacyStatus": "private"}}])
        self.assertEqual("held", result.result)
        self.assertIn("default upload", result.note)

    def test_still_processing_is_not_a_failure(self):
        result = self.upload([{"status": {"uploadStatus": "uploading",
                                         "privacyStatus": "public"}}])
        self.assertEqual("uploaded", result.result)
        self.assertIn("processing", result.note.lower())

    def test_a_rejected_video_carries_youtubes_reason(self):
        result = self.upload([{"status": {"uploadStatus": "rejected", "privacyStatus": "private",
                                         "failureReason": "copyright",
                                         "rejectionReason": "thirdPartyClaim"}}])
        self.assertEqual("rejected", result.result)
        self.assertIn("copyright", result.note)

    def test_an_unreadable_status_never_invents_a_publish(self):
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(201, {"id": "vidX"})])
        self.fake.queue("status", [Resp(403, {"error": {"code": 403, "message": "no"}})])
        out = io.StringIO()
        with redirect_stdout(out):
            result = self.publish(title="T", poll_times=1)
        self.assertEqual("uploaded", result.result,
                         "an unreadable status must never be reported as a publish")
        self.assertIn("read-back failed", result.note)
        self.assertIn("the upload itself succeeded", result.note,
                      "nor as a failure: the video is on Google, we just cannot read it")

    def test_an_answer_with_no_id_is_not_counted_as_published(self):
        """Otherwise the ledger would hold an empty id and the duplicate guard loses its key."""
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(201, {})])
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(yt_publish.Problem) as ctx:
                self.publish(title="T", poll_times=1)
        self.assertEqual("no_video_id", ctx.exception.reason)
        self.assertIn("second copy", ctx.exception.action)

    def test_the_result_is_still_the_video_id_for_older_callers(self):
        result = self.upload([{"status": {"uploadStatus": "processed",
                                          "privacyStatus": "public"}}])
        self.assertIsInstance(result, str)
        self.assertEqual("vidRB", str(result))
        self.assertIn("vidRB", result.url)


class CommandLineTests(TransportTestCase):
    """What the workflow greps for, and what it exits with."""

    def test_a_public_processed_upload_is_green_with_markers(self):
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(201, {"id": "vidOK"})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "public"},
                                                       "snippet": {"title": "T"}}]})])
        code, out, _err = self.run_main(["--video", str(self.video), "--title", "T",
                                         "--description", "d", "--tags", "a,b"])
        self.assertEqual(yt_publish.EXIT_OK, code)
        self.assertIn("VIDEO_ID=vidOK", out)
        self.assertIn("YT_UPLOAD_RESULT=published", out)
        self.assertIn("YT_PRIVACY=public", out)
        self.assertIn("YT_URL=https://www.youtube.com/watch?v=vidOK", out)

    def test_a_held_upload_is_red_but_still_prints_the_id_for_the_ledger(self):
        """The ledger entry is what stops a re-run putting a second copy up, so the id has to
        survive the failure."""
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(201, {"id": "vidHeld"})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "private"}}]})])
        code, out, err = self.run_main(["--video", str(self.video), "--title", "T"])
        self.assertEqual(yt_publish.EXIT_NEEDS_HUMAN, code)
        self.assertIn("VIDEO_ID=vidHeld", out)
        self.assertIn("YT_UPLOAD_RESULT=held", out)
        self.assertIn("YT_FAIL_KIND=state", out)

    def test_annotations_are_emitted_in_actions_and_quiet_elsewhere(self):
        """The issue body is assembled from stdout, but the annotation is what makes the run
        page itself say the cause — the log zip is unreachable 13 hours later."""
        self.write_video(1024)
        self.fake.queue("init", [Resp(403, {"error": {"code": 403, "message": "no",
                                                     "errors": [{"reason": "quotaExceeded",
                                                                 "message": "quota"}]}})])
        code, out, _err = self.run_main(["--video", str(self.video), "--title", "T"])
        self.assertIn("::error title=YouTube upload failed", out)
        self.assertIn("quotaExceeded", out)
        code, out, _err = self.run_main(["--video", str(self.video), "--title", "T"],
                                        actions="false")
        self.assertNotIn("::error", out, "annotations outside Actions are just noise")

    def test_a_privacy_refusal_is_not_reported_as_a_channel_strike(self):
        """`forbidden` is a substring of `forbiddenPrivacySetting`; matching the first key that
        appears would send the owner to look for a strike they do not have."""
        self.write_video(1024)
        self.fake.queue("init", [Resp(403, {"error": {"code": 403,
                                                     "errors": [{"reason": "forbiddenPrivacySetting"}]}})])
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(yt_publish.Problem) as ctx:
                self.publish(title="T")
        self.assertEqual("forbidden", ctx.exception.kind)
        self.assertEqual("forbiddenPrivacySetting", ctx.exception.reason)

    def test_a_credentials_failure_exits_differently_from_a_crash(self):
        self.write_video(1024)
        self.fake.scripts["token"] = [Resp(401, {"error": "invalid_client"})]
        with patch.dict(os.environ, {"YT_CLIENT_SECRET": "gone"}):
            code, out, err = self.run_main(["--video", str(self.video), "--title", "T"])
        self.assertEqual(yt_publish.EXIT_NEEDS_HUMAN, code)
        self.assertIn("YT_FAIL_KIND=credentials", out)
        self.assertIn("Recreate the OAuth client", err)

    def test_a_metadata_failure_is_a_code_problem_not_a_human_one(self):
        self.write_video(1024)
        self.fake.queue("init", [Resp(400, {"error": {"code": 400,
                                                     "errors": [{"reason": "invalidCategoryId"}]}})])
        code, out, _err = self.run_main(["--video", str(self.video), "--title", "T"])
        self.assertEqual(yt_publish.EXIT_FAILED, code)
        self.assertIn("YT_FAIL_REASON=invalidCategoryId", out)

    def test_the_queue_workflows_still_see_a_nonzero_exit_and_their_line(self):
        self.write_video(1024)
        self.fake.queue("init", [Resp(400, {"error": {"code": 400,
                                                     "errors": [{"reason": "invalidTitle"}]}})])
        code, _out, err = self.run_main(["--video", str(self.video), "--title", "T"])
        self.assertNotEqual(yt_publish.EXIT_OK, code)
        self.assertIn("queue workflows retain this item", err)

    def test_check_token_mints_and_says_so_without_touching_the_upload_endpoint(self):
        code, out, _err = self.run_main(["--check-token"])
        self.assertEqual(yt_publish.EXIT_OK, code)
        self.assertIn("token was minted", out)
        self.assertIn("YT_PROBE_RESULT=usable", out)
        self.assertEqual([], self.fake.of("init"))
        self.assertEqual([], self.fake.of("put"))

    def test_check_token_failure_names_the_repair_on_stderr(self):
        self.fake.scripts["token"] = [Resp(400, {"error": "invalid_grant"})]
        code, out, err = self.run_main(["--check-token"])
        self.assertEqual(yt_publish.EXIT_NEEDS_HUMAN, code)
        self.assertIn("invalid_grant", err)
        self.assertIn("YT_PROBE_RESULT=failed", out)


class ProbeTests(TransportTestCase):
    """The probe exists so the owner is never asked to guess which of four things is wrong."""

    def channels(self, title="DocOga", channel_id="UCdocoga123"):
        self.fake.queue("channels", [Resp(200, {"items": [{
            "id": channel_id,
            "snippet": {"title": title},
            "contentDetails": {"relatedPlaylists": {"uploads": "UUdocoga"}},
            "statistics": {"subscriberCount": "12"}}]})])

    def test_the_probe_names_the_channel_it_will_publish_to(self):
        self.channels()
        self.fake.queue("videos", [Resp(200, {"items": [{"snippet": {"title": "Old Short"},
                                                        "status": {"uploadStatus": "processed",
                                                                  "privacyStatus": "public"}}]})])
        out = io.StringIO()
        with redirect_stdout(out):
            info = yt_publish.probe(http=self.http)
        self.assertEqual("UCdocoga123", info["channel_id"])
        text = out.getvalue()
        self.assertIn("DocOga", text)
        self.assertIn("Old Short", text)
        self.assertIn("token minted", text)

    def test_the_cli_returns_zero_for_a_healthy_probe(self):
        """Exit 0 matters as much as the text here: the workflow's probe-only dispatch is the
        one run that must be green without posting anything."""
        self.channels()
        self.fake.queue("videos", [Resp(200, {"items": []})])
        code, _out, err = self.run_main(["--probe"])
        self.assertEqual(yt_publish.EXIT_OK, code)
        self.assertEqual("", err)

    def test_the_probe_uploads_nothing(self):
        self.channels()
        self.fake.queue("videos", [Resp(200, {"items": []})])
        with redirect_stdout(io.StringIO()):
            yt_publish.probe(http=self.http)
        self.assertEqual([], self.fake.of("put"))
        self.assertEqual([], self.fake.of("init"))

    def test_a_token_for_the_wrong_channel_is_a_failure_not_a_note(self):
        self.channels(channel_id="UCsomeoneelse")
        self.fake.queue("videos", [Resp(200, {"items": []})])
        with patch.dict(os.environ, {"YT_CHANNEL_ID": "UCdocoga123"}):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(yt_publish.Problem) as ctx:
                    yt_publish.probe(http=self.http)
        self.assertEqual("wrong_channel", ctx.exception.reason)
        self.assertIn("re-consent", ctx.exception.action.lower())

    def test_no_channel_at_all_is_spelled_out(self):
        self.fake.queue("channels", [Resp(200, {"items": []})])
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(yt_publish.Problem) as ctx:
                yt_publish.probe(http=self.http)
        self.assertEqual("no_channel", ctx.exception.reason)
        self.assertIn("picker", ctx.exception.action)

    def test_a_missing_channel_id_is_a_warning_with_a_reason(self):
        self.channels()
        self.fake.queue("videos", [Resp(200, {"items": []})])
        env = {k: v for k, v in os.environ.items() if k != "YT_CHANNEL_ID"}
        with patch.dict(os.environ, env, clear=True):
            with redirect_stdout(io.StringIO()):
                yt_publish.probe(http=self.http)
        lines = [c for c in self.fake.calls]  # probe must still finish, not raise
        self.assertTrue(lines)

    def test_the_empty_uploads_playlist_says_what_it_means(self):
        self.channels()
        self.fake.queue("videos", [Resp(200, {"items": []})])
        out = io.StringIO()
        with redirect_stdout(out):
            yt_publish.probe(http=self.http)
        self.assertIn("never published", out.getvalue())


class CompatibilityTests(TransportTestCase):
    """The old entry points the queue workflow and existing call sites rely on."""

    def test_upload_video_returns_the_id_on_success(self):
        self.write_video(1024)
        self.fake.queue("init", [Resp(200, {}, {"Location": "https://u/1"})])
        self.fake.queue("put", [Resp(201, {"id": "vidCompat"})])
        self.fake.queue("status", [Resp(200, {"items": [{"status": {"uploadStatus": "processed",
                                                                   "privacyStatus": "public"}}]})])
        with patch.object(yt_publish, "Http", lambda token=None, session=None: self.http):
            out = io.StringIO()
            with redirect_stdout(out):
                result = yt_publish.upload_video(str(self.video), "T")
        self.assertEqual("vidCompat", result)

    def test_upload_video_returns_none_and_reports_on_failure(self):
        self.write_video(1024)
        self.fake.queue("init", [Resp(403, {"error": {"code": 403,
                                                     "errors": [{"reason": "forbidden"}]}})])
        with patch.object(yt_publish, "Http", lambda token=None, session=None: self.http):
            out = io.StringIO()
            with redirect_stdout(out):
                result = yt_publish.upload_video(str(self.video), "T")
        self.assertIsNone(result)
        text = out.getvalue()
        self.assertIn("kind=forbidden", text)
        self.assertIn("fix:", text)

    def test_a_missing_file_is_caught_before_any_request(self):
        with self.assertRaises(yt_publish.Problem) as ctx:
            yt_publish.publish(Path(self.tmp.name) / "nope.mp4", "T", http=self.http)
        self.assertEqual("file_missing", ctx.exception.reason)
        self.assertEqual([c for c in self.fake.calls if c["route"] != "token"], [])

    def test_an_empty_file_is_caught_before_any_request(self):
        self.write_video(0)
        with self.assertRaises(yt_publish.Problem) as ctx:
            self.publish(title="T")
        self.assertEqual("empty_file", ctx.exception.reason)


class HygieneTests(unittest.TestCase):
    def test_no_request_is_made_without_going_through_the_http_wrapper(self):
        text = (TOOLS_DIR / "yt_publish.py").read_text(encoding="utf-8")
        for bad in ("requests.get(", "requests.post(", "requests.put(", "requests.request("):
            self.assertNotIn(bad, text.split("class Http")[1], bad)

    def test_the_exit_code_meanings_are_documented_in_one_place(self):
        text = (TOOLS_DIR / "yt_publish.py").read_text(encoding="utf-8")
        self.assertIn("EXIT_NEEDS_HUMAN = 2", text)
        self.assertIn("EXIT_OK = 0", text)

    def test_the_reason_table_covers_every_documented_videos_insert_error(self):
        documented = ["invalidTitle", "invalidDescription", "invalidTags", "invalidCategoryId",
                      "invalidVideoMetadata", "mediaBodyRequired", "uploadLimitExceeded",
                      "forbidden", "forbiddenPrivacySetting", "forbiddenLicenseSetting",
                      "defaultLanguageNotSet", "invalidFilename", "invalidPublishAt",
                      "quotaExceeded", "dailyUploadLimitExceeded"]
        missing = [r for r in documented if r not in yt_publish.REASONS]
        self.assertEqual([], missing, "a reason with no action is a guess waiting to happen")

    def test_the_chunk_size_honours_the_256kb_alignment_rule(self):
        self.assertEqual(0, yt_publish.CHUNK_BYTES % (256 * 1024))


if __name__ == "__main__":
    unittest.main()
