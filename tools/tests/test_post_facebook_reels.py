"""The Facebook Reels lane — the three-phase protocol, and the gate in front of it.

`video_reels` is the one publishing edge on this Page that **cannot be read back
through the edge that created it**, and whose worst failure is silent: a file that
is not 9:16, or is longer than 90 seconds, is accepted by the upload and then fails
to publish with no clear error. So the behaviour that matters is not "did the HTTP
call succeed" but:

  * the local spec gate refuses a bad file **before any bytes leave the runner**;
  * phase 2 goes to a different host, with the token in an `Authorization: OAuth`
    header and `offset` / `file_size` as header *strings* — not in the body;
  * nothing is finished during a probe, so a dry run cannot publish a reel;
  * "accepted then unpublished" is reported as its own failure, with its own exit
    code, and can be finished by hand afterwards;
  * the day rule and the ledger guard decide before ~2 minutes of CPU are spent.

The fake below records full requests (headers included, unlike the feed tests in
`test_post_facebook.py`, where body and files were the only interesting parts).
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for rel in ("tools", "scripts"):
    if str(ROOT / rel) not in sys.path:
        sys.path.insert(0, str(ROOT / rel))

import fb_publish  # noqa: E402
import facebook_reel_daily  # noqa: E402
import post_facebook  # noqa: E402

TOKEN = "EAAB" + "y" * 60
PAGE = "102466208923830"
GOOD = {
    "format": {"duration": "23.000000"},
    "streams": [{"width": 1080, "height": 1920, "codec_name": "h264", "avg_frame_rate": "24/1"}],
}


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload) if payload is not None else ""

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON")
        return self._payload


def api_error(code, message, status=400, **extra):
    return FakeResponse({"error": dict(message=message, type="OAuthException", code=code,
                                       **extra)}, status)


class Graph:
    """Answers every call from `responder(call)` and remembers the request."""

    def __init__(self, responder):
        self.calls = []
        self.responder = responder

    def request(self, method, url, **kwargs):
        call = {"method": method, "url": url}
        call.update(kwargs)
        self.calls.append(call)
        reply = self.responder(call)
        return reply if reply is not None else FakeResponse({}, 200)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)


def reel_responder(**overrides):
    """A healthy Meta: session, bytes accepted, publish ok, then ready."""
    answers = {
        "start": FakeResponse({"video_id": "987654321", "upload_url": "https://rupload.facebook.com/x"}),
        "rupload": FakeResponse({"success": True, "start_offset": 0}),
        "finish": FakeResponse({"success": True, "video_id": "987654321"}),
        "status": FakeResponse({"status": {"video_status": "ready",
                                           "publishing_phase": {"status": "complete"}},
                                "permalink_url": "https://www.facebook.com/reel/987654321/"}),
        "videos": FakeResponse({"data": []}),
        "feed": FakeResponse({"data": []}),
    }
    answers.update(overrides)

    def responder(call):
        url = call["url"]
        if "rupload" in url:
            return answers["rupload"]
        if "/video_reels" in url:
            phase = str((call.get("data") or {}).get("upload_phase", "")).lower()
            return answers["finish"] if phase == "finish" else answers["start"]
        if call["method"] == "DELETE":
            return FakeResponse({"success": True})
        if url.endswith("/feed"):
            return answers["feed"]
        if url.endswith("/videos"):
            return answers["videos"]
        if call["method"] == "GET":
            return answers["status"]        # the video object read
        return FakeResponse({})

    return responder


def phases_of(graph):
    out = []
    for call in graph.calls:
        url = call["url"]
        if "rupload" in url:
            out.append("upload")
        elif "/video_reels" in url:
            data = call.get("data") or {}
            phase = str(data.get("upload_phase", "")).lower()
            out.append("finish" if phase == "finish" else "start")
        elif call["method"] == "DELETE":
            out.append("delete")
        else:
            out.append("read")
    return out


def write_reel_bytes(tmp, name="reel.mp4", size=5000):
    path = Path(tmp) / name
    path.write_bytes(b"\x00" * size)
    return path


class SpecGateTests(unittest.TestCase):
    """`reel_spec_ok` — the refusal that must happen before any bytes move."""

    def setUp(self):
        # A real file, because the gate checks existence and size before it ever
        # reaches ffprobe — a test pointing at a path that does not exist proves
        # the existence check and nothing else.
        self.tmp = os.path.join("/tmp", "docoga-reel-spec")
        os.makedirs(self.tmp, exist_ok=True)
        self.mp4 = write_reel_bytes(self.tmp, name="clip.mp4", size=4096)

    def tearDown(self):
        os.remove(self.mp4)

    def probe(self, payload, returncode=0):
        def run(*a, **k):
            class R:
                pass
            r = R()
            r.returncode = returncode
            r.stdout = json.dumps(payload)
            r.stderr = ""
            return r
        return patch.object(fb_publish.subprocess, "run", run)

    def test_missing_file_is_refused(self):
        ok, reason, _info = fb_publish.reel_spec_ok("/nonexistent/reel.mp4")
        self.assertFalse(ok)
        self.assertIn("not found", reason)

    def test_empty_file_is_read_as_an_incomplete_render(self):
        with self.subTest("empty file"):
            with patch("os.path.getsize", return_value=0):
                ok, reason, _ = fb_publish.reel_spec_ok(__file__)
            self.assertFalse(ok)
            self.assertIn("render did not finish", reason)

    def test_a_non_mp4_container_is_refused(self):
        ok, reason, _ = fb_publish.reel_spec_ok(__file__)      # this file: .py
        self.assertFalse(ok)
        self.assertIn(".mp4", reason)

    def test_the_memory_cap_is_stated_as_a_cap(self):
        with patch("os.path.getsize", return_value=fb_publish.REEL_MEMORY_LIMIT + 1):
            ok, reason, _ = fb_publish.reel_spec_ok(__file__)
        self.assertFalse(ok)
        self.assertIn("buffers", reason)

    def test_a_missing_ffprobe_blocks_a_strict_call_only(self):
        def raise_oserror(*a, **k):
            raise OSError("No such file or directory: 'ffprobe'")
        with patch.object(fb_publish.subprocess, "run", raise_oserror):
            strict = fb_publish.reel_spec_ok(str(self.mp4), strict=True)
            lenient = fb_publish.reel_spec_ok(str(self.mp4), strict=False)
        self.assertFalse(strict[0])
        self.assertTrue(lenient[0])
        self.assertIn("not spec-checked", lenient[1])

    def test_a_square_video_is_refused_because_meta_would_fail_quietly(self):
        with self.probe({"format": {"duration": "23.0"},
                         "streams": [{"width": 1080, "height": 1080, "codec_name": "h264"}]}):
            ok, reason, info = fb_publish.reel_spec_ok(str(self.mp4))
        self.assertFalse(ok)
        self.assertIn("9:16", reason)
        # The message must explain the *silent* part, or the next engineer removes
        # the gate because "the API accepted it fine".
        self.assertIn("accepts the upload", reason)
        self.assertEqual(info["width"], 1080)

    def test_duration_outside_the_reels_window_is_refused(self):
        for seconds, want in ((150.0, "publishes as an ordinary video post"), (1.0, "3-90")):
            with self.subTest(seconds=seconds):
                with self.probe({"format": {"duration": str(seconds)},
                                 "streams": [{"width": 1080, "height": 1920, "codec_name": "h264"}]}):
                    ok, reason, _ = fb_publish.reel_spec_ok(str(self.mp4))
                self.assertFalse(ok)
                self.assertIn(want, reason)

    def test_the_wrong_codec_is_refused(self):
        with self.probe({"format": {"duration": "23.0"},
                         "streams": [{"width": 1080, "height": 1920, "codec_name": "vp9"}]}):
            ok, reason, _ = fb_publish.reel_spec_ok(str(self.mp4))
        self.assertFalse(ok)
        self.assertIn("H.264", reason)

    def test_a_reel_shaped_file_passes_and_reports_what_it_measured(self):
        with self.probe(GOOD):
            ok, reason, info = fb_publish.reel_spec_ok(str(self.mp4))
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "ok")
        self.assertEqual((info["width"], info["height"]), (1080, 1920))
        self.assertAlmostEqual(info["seconds"], 23.0)

    def test_the_rotation_frames_fit_the_reels_window(self):
        """Not a mock: the shipped slide durations must be inside 3–90 s.

        A slide edit that adds four 4-second frames is a content change; it should
        fail here, where the message says which knob to turn, and not silently
        publish as a plain video post on the day the lane is switched on.
        """
        import generate_short_video as shorts
        for script in shorts.VIDEO_SCRIPTS:
            seconds = sum(int(slide.get("duration", 3)) for slide in script["slides"])
            with self.subTest(title=script["title"]):
                self.assertGreaterEqual(seconds, facebook_reel_daily.REEL_MIN_SECONDS)
                self.assertLessEqual(seconds, facebook_reel_daily.REEL_MAX_SECONDS)


class ReelProtocolTests(unittest.TestCase):
    """The three phases, in order, with the fields Meta actually reads."""

    def setUp(self):
        self._phases = dict(fb_publish._PHASES)
        self.tmp = os.path.join("/tmp", "docoga-reel-tests")
        os.makedirs(self.tmp, exist_ok=True)
        self.path = write_reel_bytes(self.tmp)
        self.size = self.path.stat().st_size

    def tearDown(self):
        fb_publish._PHASES.clear()
        fb_publish._PHASES.update(self._phases)
        os.remove(self.path)

    def publish(self, graph, **kwargs):
        good = {"format": {"duration": "23.0"},
                "streams": [{"width": 1080, "height": 1920, "codec_name": "h264"}]}

        def run(*a, **k):
            class R:
                pass
            r = R()
            r.returncode, r.stdout, r.stderr = 0, json.dumps(good), ""
            return r
        kwargs.setdefault("sleeper", lambda _s: None)
        with patch("requests.request", graph.request), \
                patch("requests.get", graph.get), patch("requests.post", graph.post), \
                patch("requests.delete", graph.delete), \
                patch.object(fb_publish.subprocess, "run", run):
            return fb_publish.post_reel(TOKEN, PAGE, str(self.path), title="Rent Receipt",
                                        description="Today's reel copy", **kwargs)

    def test_the_three_phases_happen_in_order(self):
        graph = Graph(reel_responder())
        ok, detail = self.publish(graph)
        self.assertTrue(ok, detail)
        self.assertEqual(phases_of(graph)[:3], ["start", "upload", "finish"])
        self.assertEqual(detail["video_id"], "987654321")
        self.assertIn("facebook.com/reel/", detail["permalink"])

    def test_start_carries_the_caption_and_title(self):
        graph = Graph(reel_responder())
        self.publish(graph)
        start = [c for c in graph.calls if "/video_reels" in c["url"]][0]
        self.assertEqual(start["data"]["description"], "Today's reel copy")
        self.assertEqual(start["data"]["title"], "Rent Receipt")
        self.assertNotIn("is_ai_generated", start["data"])  # no generative model in the render

    def test_phase_two_uses_the_rupload_host_with_the_version_in_the_path(self):
        graph = Graph(reel_responder())
        self.publish(graph)
        upload = [c for c in graph.calls if "rupload" in c["url"]][0]
        self.assertIn("rupload.facebook.com/video-upload/%s/987654321" % fb_publish.API_VERSION,
                      upload["url"])

    def test_phase_two_sends_headers_not_body_fields(self):
        graph = Graph(reel_responder())
        self.publish(graph)
        upload = [c for c in graph.calls if "rupload" in c["url"]][0]
        headers = upload["headers"]
        self.assertEqual(headers["Authorization"], "OAuth %s" % TOKEN)
        self.assertEqual(headers["offset"], "0")          # a string, as documented
        self.assertEqual(headers["file_size"], str(self.size))
        self.assertEqual(headers["Content-Type"], "application/octet-stream")
        self.assertEqual(upload["data"], b"\x00" * self.size)   # raw bytes, not multipart
        self.assertNotIn("files", upload)
        self.assertNotIn(b"access_token", upload["data"])       # the token is a header here

    def test_a_short_transfer_is_not_finished(self):
        """Meta reports the bytes it stored; a truncated one must never be published."""
        graph = Graph(reel_responder(rupload=FakeResponse({"success": True, "end_offset": 10})))
        ok, detail = self.publish(graph)
        self.assertFalse(ok)
        self.assertIn("incomplete", str(detail))
        self.assertNotIn("finish", phases_of(graph))

    def test_finish_publishes_rather_than_drafts(self):
        graph = Graph(reel_responder())
        self.publish(graph)
        finish = [c for c in graph.calls if "/video_reels" in c["url"] and
                  "finish" in str((c.get("data") or {}).get("upload_phase", ""))][0]
        self.assertEqual(finish["data"]["video_state"], "PUBLISHED")
        self.assertEqual(finish["data"]["video_id"], "987654321")

    def test_draft_mode_never_polls_and_never_claims_a_permalink(self):
        graph = Graph(reel_responder())
        ok, detail = self.publish(graph, draft=True)
        self.assertTrue(ok)
        self.assertEqual(detail["state"], "DRAFT")
        self.assertEqual(detail["permalink"], "")
        self.assertNotIn("read", phases_of(graph))   # no status GET for a draft

    def test_scheduling_is_rejected_before_any_call_when_the_time_is_too_soon(self):
        graph = Graph(reel_responder())
        import time as _t
        ok, detail = self.publish(graph, scheduled_publish_time=int(_t.time()) + 30)
        self.assertFalse(ok)
        self.assertIn("600", str(detail))
        self.assertEqual(graph.calls, [])            # nothing was sent at all
        # Exit 4, not 5: nobody's API is broken, a caller asked for an impossible
        # time. The distinction is what makes the issue text actionable.

    def test_scheduling_is_rejected_beyond_twenty_nine_days(self):
        graph = Graph(reel_responder())
        import time as _t
        ok, detail = self.publish(graph, scheduled_publish_time=int(_t.time()) + 40 * 86400)
        self.assertFalse(ok)
        self.assertIn("29 days", str(detail))

    def test_the_probe_opens_a_session_and_never_finishes_it(self):
        graph = Graph(reel_responder())
        with patch("requests.post", graph.post), patch("requests.delete", graph.delete):
            ok, detail = fb_publish.reel_probe(TOKEN, PAGE)
        self.assertTrue(ok, detail)
        self.assertEqual(phases_of(graph), ["start", "delete"])
        self.assertNotIn("finish", str(graph.calls))

    def test_a_publish_refusal_names_the_way_to_finish_it_by_hand(self):
        graph = Graph(reel_responder(finish=api_error(100, "Unsupported post request")))
        ok, detail = self.publish(graph)
        self.assertFalse(ok)
        self.assertIn("publish refused after the upload was accepted", detail)
        self.assertIn("--reel-finish 987654321", detail)   # recoverable, and told so
        self.assertEqual(fb_publish.reel_exit_code(detail), 5)

    def test_processing_failure_is_its_own_class_of_bad_news(self):
        graph = Graph(reel_responder(status=FakeResponse(
            {"status": {"video_status": "error",
                        "processing_phase": {"error_subcode": 39001}}})))
        ok, detail = self.publish(graph)
        self.assertFalse(ok)
        self.assertTrue(detail.startswith("processing failed"))
        self.assertEqual(fb_publish.reel_exit_code(detail), 5)

    def test_still_processing_is_a_warning_not_a_failure(self):
        graph = Graph(reel_responder(status=FakeResponse(
            {"status": {"video_status": "processing"}, "permalink_url": ""})))
        slept = []
        ok, detail = self.publish(graph, verify=True, sleeper=slept.append)
        self.assertTrue(ok, detail)
        self.assertEqual(detail["verdict"], "processing")
        self.assertEqual(len(slept), fb_publish.REEL_POLL_TRIES - 1)  # polled, then gave up

    def test_the_upload_phase_spelling_falls_back_once(self):
        """Meta's table prints START/FINISH; the examples send lowercase. If a future
        version tightens that, the run must adapt and say so, not die."""
        calls = {"n": 0}

        def responder(call):
            if "/video_reels" in call["url"]:
                calls["n"] += 1
                phase = str((call.get("data") or {}).get("upload_phase", "")).lower()
                if phase == "finish":
                    return FakeResponse({"success": True})
                if fb_publish._PHASES["start"] == "start":
                    return api_error(100, "Invalid parameter: upload_phase must be one of START, FINISH")
                return FakeResponse({"video_id": "555", "upload_url": ""})
            if "rupload" in call["url"]:
                return FakeResponse({"success": True})
            if call["method"] == "GET":
                return FakeResponse({"status": {"video_status": "ready"}})
            return FakeResponse({})

        graph = Graph(responder)
        ok, detail = self.publish(graph)
        self.assertTrue(ok, detail)
        self.assertEqual(fb_publish._PHASES["start"], "START")   # remembered for finish
        sent = [str((c.get("data") or {}).get("upload_phase")) for c in graph.calls
                if "/video_reels" in c["url"]]
        self.assertEqual(sent, ["start", "START", "FINISH"])
        self.assertGreaterEqual(calls["n"], 2)


class ExitCodeContractTests(unittest.TestCase):
    def test_each_failure_stage_has_its_own_code(self):
        cases = {
            "spec refused — aspect ratio is 1:1": 4,
            "start refused — (#200) Permission failed": 3,
            "upload refused after the session opened": 3,
            "publish refused after the upload was accepted": 5,
            "processing failed — video_status error": 5,
            "something nobody predicted": 3,
        }
        for message, code in cases.items():
            with self.subTest(message=message):
                self.assertEqual(fb_publish.reel_exit_code(message), code)


class ReelDayRuleTests(unittest.TestCase):
    """The decision that keeps this lane from spending runner minutes on a skip."""

    def test_monday_and_thursday_are_the_reel_days(self):
        self.assertEqual(facebook_reel_daily.REEL_WEEKDAYS, (0, 3))
        self.assertTrue(facebook_reel_daily.is_reel_day(date(2026, 10, 12)))   # Mon
        self.assertTrue(facebook_reel_daily.is_reel_day(date(2026, 10, 15)))   # Thu

    def test_the_lane_never_shares_a_day_with_the_shorts_schedule(self):
        """Tue(1) + Fri(4) belong to `youtube_scheduled.yml`. Same weekday would mean
        the same rotation index, i.e. the same frame on both platforms on one day,
        which docs/GROWTH_ENGINE.md §4 forbids for 30 days."""
        shorts_days = {1, 4}
        self.assertEqual(set(facebook_reel_daily.REEL_WEEKDAYS) & shorts_days, set())

    def test_a_non_reel_day_stands_down_as_success_without_rendering(self):
        decided = facebook_reel_daily.plan(date(2026, 10, 13), "on")   # Tue
        self.assertEqual(decided["reel_today"], "no")
        self.assertEqual(decided["exit"], 0)
        self.assertIn("not a reel day", decided["reason"])

    def test_off_is_a_switch_and_says_which_variable_to_turn(self):
        decided = facebook_reel_daily.plan(date(2026, 10, 12), "off")
        self.assertEqual(decided["reel_today"], "no")
        self.assertIn("FB_REELS", decided["reason"])

    def test_an_unreadable_mode_fails_loudly_instead_of_silently_doing_nothing(self):
        """A typo in a repository variable is exactly the class of bug that makes a
        lane look alive for weeks while it publishes nothing."""
        decided = facebook_reel_daily.plan(date(2026, 10, 12), "yes-please")
        self.assertEqual(decided["exit"], 4)
        self.assertIn("REELS_MODE", decided["reason"])

    def test_probe_mode_is_the_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(facebook_reel_daily.mode_from_env(), "probe")

    def test_the_topic_is_the_shared_rotation_not_a_second_calendar(self):
        import generate_short_video as shorts
        day = date(2026, 10, 12)
        self.assertEqual(facebook_reel_daily.reel_topic(day), shorts.script_for_date(day)["title"])

    def test_plan_emits_every_output_the_workflow_greps_for(self):
        out = io.StringIO()
        with patch.dict(os.environ, {"GITHUB_OUTPUT": ""}, clear=False), \
                redirect_stdout(out):
            code = facebook_reel_daily.main(["--date", "2026-10-12", "--mode", "on"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        for key in ("reel_today", "mode", "topic", "title", "run_date"):
            self.assertIn("%s=" % key, text)
        self.assertIn("reel_today=yes", text)

    def test_a_render_without_the_renderer_names_the_missing_piece(self):
        """On a machine with no moviepy (a laptop; a future base image), the lane must
        say what is missing and be *non-zero*. `render()` returning a falsy value that
        the CLI swallows is the October Telegram bug in a new costume, so the exit
        code is asserted through main(), not just the helper."""
        with patch.dict(sys.modules, {"generate_short_video": None}):
            ok, reason, _info = facebook_reel_daily.render(date(2026, 10, 12))
            self.assertFalse(ok)
            self.assertIn("could not be imported", reason)
            out = io.StringIO()
            with patch.dict(os.environ, {"GITHUB_OUTPUT": ""}, clear=False), \
                    redirect_stdout(out):
                code = facebook_reel_daily.main(
                    ["--date", "2026-10-12", "--mode", "on", "--render"])
        self.assertEqual(code, 3)
        self.assertIn("renderer", out.getvalue())

    def test_the_outputs_are_on_stdout_as_well_as_in_github_output(self):
        """CI always has `$GITHUB_OUTPUT` set, so an either/or here means the manual
        reel path and the ledger's title fallback grep a log that never contained
        those lines. Both surfaces must carry them."""
        out = io.StringIO()
        with tempfile.NamedTemporaryFile("w+", suffix=".env", delete=False) as handle:
            env_file = handle.name
        try:
            with patch.dict(os.environ, {"GITHUB_OUTPUT": env_file}, clear=False), \
                    redirect_stdout(out):
                facebook_reel_daily.emit({"video_path": "/tmp/x.mp4", "title": "Rent Receipt"})
            written = open(env_file, encoding="utf-8").read()
        finally:
            os.unlink(env_file)
        self.assertIn("video_path=/tmp/x.mp4", written)
        self.assertIn("video_path=/tmp/x.mp4", out.getvalue())
        self.assertIn("title=Rent Receipt", out.getvalue())

    def test_a_broken_renderer_never_stops_the_cheap_decision(self):
        """The plan step runs on every scheduled day, in every mode. If importing the
        renderer is what answers "what is today's topic?", then a machine without
        moviepy turns a 0-second decision into a red run for a lane that is switched
        to `probe` — the pipeline would break where it is supposed to be cheapest.
        """
        with patch.dict(sys.modules, {"generate_short_video": None}):
            decided = facebook_reel_daily.plan(date(2026, 10, 12), "probe")
            self.assertEqual(decided["reel_today"], "yes")
            self.assertEqual(decided["topic"], "")
            self.assertIn("None in sys.modules", decided["topic_error"])
            out = io.StringIO()
            with patch.dict(os.environ, {"GITHUB_OUTPUT": ""}, clear=False), \
                    redirect_stdout(out):
                code = facebook_reel_daily.main(["--date", "2026-10-12", "--mode", "probe"])
        self.assertEqual(code, 0)
        self.assertIn("rotation could not be read", out.getvalue())


class PosterCliTests(unittest.TestCase):
    """`scripts/post_facebook.py --reel …` — the step the workflow actually runs."""

    def setUp(self):
        self._phases = dict(fb_publish._PHASES)
        self.tmp = os.path.join("/tmp", "docoga-reel-cli")
        os.makedirs(self.tmp, exist_ok=True)
        self.path = write_reel_bytes(self.tmp)
        good = {"format": {"duration": "23.0"},
                "streams": [{"width": 1080, "height": 1920, "codec_name": "h264"}]}

        def run(*a, **k):
            class R:
                pass
            r = R()
            r.returncode, r.stdout, r.stderr = 0, json.dumps(good), ""
            return r
        self.probe_patch = patch.object(fb_publish.subprocess, "run", run)
        self.probe_patch.start()

    def tearDown(self):
        self.probe_patch.stop()
        fb_publish._PHASES.clear()
        fb_publish._PHASES.update(self._phases)
        os.remove(self.path)

    def drive(self, argv, responder):
        graph = Graph(responder)
        out = io.StringIO()
        # The status poll's real 20 s delay must not be paid 6× per test; the
        # delay itself is asserted where the polling is the subject under test.
        with patch.dict(os.environ, {"FB_PAGE_ACCESS_TOKEN": TOKEN, "FB_PAGE_ID": PAGE}), \
                patch("requests.post", graph.post), patch("requests.get", graph.get), \
                patch("requests.delete", graph.delete), \
                patch.object(fb_publish.time, "sleep", lambda _s: None), \
                redirect_stdout(out):
            code = post_facebook.main(argv)
        return code, out.getvalue(), graph

    def test_the_reel_publish_prints_the_machine_readable_ledger_lines(self):
        code, text, graph = self.drive(
            ["--reel", str(self.path), "--title", "Rent Receipt", "--force",
             "--description", "copy"], reel_responder())
        self.assertEqual(code, 0, text)
        self.assertIn("REEL_VIDEO_ID=987654321", text)
        self.assertIn("REEL_URL=https://www.facebook.com/reel/987654321/", text)
        self.assertEqual(phases_of(graph)[:3], ["start", "upload", "finish"])

    def test_the_page_guard_asks_the_videos_edge_not_the_feed(self):
        """A text post went out ten minutes ago in the same job; matching on `/feed`
        would skip the reel for the wrong reason."""
        reads = []

        def responder(call):
            if "rupload" in call["url"]:
                return FakeResponse({"success": True})
            if "/video_reels" in call["url"]:
                phase = str((call.get("data") or {}).get("upload_phase", "")).lower()
                return FakeResponse({"data": []}) if phase == "finish" \
                    else FakeResponse({"video_id": "1", "upload_url": ""})
            if call["method"] == "GET":
                reads.append(call["url"])
                if call["url"].endswith("/videos"):
                    return FakeResponse({"data": []})
                return FakeResponse({"status": {"video_status": "ready"}})
            return FakeResponse({})

        self.drive(["--reel", str(self.path), "--title", "Rent Receipt"], responder)
        self.assertTrue([u for u in reads if u.endswith("/videos")], reads)
        self.assertFalse([u for u in reads if u.endswith("/feed")], reads)

    def test_a_reel_already_on_the_page_today_is_a_skip_not_a_failure(self):
        today = (datetime.now(timezone.utc) + timedelta(hours=1)).date()   # Lagos

        def responder(call):
            if call["method"] == "GET" and call["url"].endswith("/videos"):
                return FakeResponse({"data": [{"id": "%s_1" % PAGE, "title": "Rent Receipt",
                                               "created_time": "%sT07:30:00+0000" % today}]})
            return FakeResponse({"data": []})

        code, text, graph = self.drive(["--reel", str(self.path), "--title", "Rent Receipt"],
                                        responder)
        self.assertEqual(code, 0, text)
        self.assertIn("skipped", text)
        self.assertEqual(graph.calls[0]["method"], "GET")   # nothing was posted
        self.assertNotIn("rupload", str(graph.calls))

    def test_a_probe_flag_never_publishes_even_when_told_to(self):
        code, text, graph = self.drive(["--probe-reels"], reel_responder())
        self.assertEqual(code, 0, text)
        self.assertEqual(phases_of(graph), ["start", "delete"])

    def test_a_refused_publish_exits_with_the_stage_it_failed_at(self):
        code, text, graph = self.drive(
            ["--reel", str(self.path), "--title", "T", "--force"],
            reel_responder(finish=api_error(100, "video_state invalid")))
        self.assertEqual(code, 5)
        self.assertIn("publish refused", text)

    def test_the_token_never_appears_in_reel_output(self):
        """Requests legitimately carry the token; *output* may not, not even when Meta
        echoes the value back inside its own error message."""
        code, text, graph = self.drive(
            ["--reel", str(self.path), "--title", "T", "--force"],
            reel_responder(start=api_error(190, "Invalid token %s provided" % TOKEN)))
        self.assertEqual(code, 3)
        self.assertIn("[token redacted]", text)
        self.assertNotIn(TOKEN, text)


class SourceHygieneTests(unittest.TestCase):
    def test_phase_two_has_exactly_one_url_builder(self):
        """The rupload host appears as a constant and is used once. Two call sites
        building their own URL is how a version bump fixes one path and silently
        breaks the other."""
        src = (ROOT / "tools" / "fb_publish.py").read_text(encoding="utf-8")
        self.assertIn('RUPLOAD = "https://rupload.facebook.com/video-upload"', src)
        self.assertEqual(src.count("% (RUPLOAD, API_VERSION, video_id)"), 1)
        self.assertNotIn('requests.post("https://rupload', src)

    def test_the_reel_code_never_prints_the_token(self):
        src = (ROOT / "tools" / "fb_publish.py").read_text(encoding="utf-8")
        reel_block = src.split("# ── Reels")[1].split("# ── ")[0] if "# ── Reels" in src else src
        for banned in ("print(token", "print(\"%s\" % token", "token[:"):
            self.assertNotIn(banned, reel_block)

    def test_the_reels_mode_is_a_variable_not_only_a_constant(self):
        wf = (ROOT / ".github" / "workflows" / "facebook_autopost.yml").read_text(encoding="utf-8")
        self.assertIn("vars.FB_REELS", wf)
        self.assertIn("probe", wf)

    def test_the_reel_ledger_reuses_the_existing_ledger_tool(self):
        """One ledger implementation, two files. A fork would drift the first time
        someone fixes a race in the other one."""
        wf = (ROOT / ".github" / "workflows" / "facebook_autopost.yml").read_text(encoding="utf-8")
        self.assertIn("tools/youtube_ledger.py --ledger logs/facebook_reels.json", wf)
        self.assertIn("--window-days 30", wf)


if __name__ == "__main__":
    unittest.main(verbosity=2)
