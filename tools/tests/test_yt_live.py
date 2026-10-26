"""DocOga Live — the always-on stream (tools/yt_live.py, youtube_live.yml), 26 Oct 2026.

Owner: "go — I want live stream to always be on for life, pulling in watch time, subscribers
etc." What these pin: the loop is built from the channel's own banked episodes and nothing
else; every clip is normalised to one profile so the stream copies bytes instead of
encoding; the broadcast never auto-stops (the hand-over lives inside it); the title says
pre-recorded; the key is masked before it can be printed; and the chain queues its
successor, honours the kill switch and cannot run two windows at once.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import yt_live  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

LIVE_YML = ROOT / ".github" / "workflows" / "youtube_live.yml"
SHORTS_YML = ROOT / ".github" / "workflows" / "youtube_scheduled.yml"


def asset(release, name, size=1):
    return {"release": release, "name": name, "size": size}


class PlanTests(unittest.TestCase):
    def test_only_masters_and_banked_shorts_are_clips(self):
        rows = yt_live.plan([
            asset("deepdive-dd3", "dd3-episode.mp4"), asset("deepdive-dd3", "dd3-cover.jpg"),
            asset("deepdive-dd3", "dd3-voice.tar.gz"), asset("live-library", "short-2026-10-26.mp4"),
            asset("live-library", "norm-short-2026-10-26-abc.mp4"), asset("v1.0", "docoga.apk"),
        ])
        self.assertEqual([r["name"] for r in rows], ["short-2026-10-26.mp4", "dd3-episode.mp4"])

    def test_the_newest_short_opens_the_loop_and_shorts_interleave_with_episodes(self):
        rows = yt_live.plan([
            asset("deepdive-dd2", "dd2-episode.mp4"), asset("deepdive-dd4", "dd4-episode.mp4"),
            asset("deepdive-dd3", "dd3-episode.mp4"),
            asset("live-library", "short-2026-10-26.mp4"), asset("live-library", "short-2026-10-27.mp4"),
        ])
        self.assertEqual([r["name"] for r in rows],
                         ["short-2026-10-27.mp4", "dd4-episode.mp4", "short-2026-10-26.mp4",
                          "dd3-episode.mp4", "dd2-episode.mp4"])
        self.assertEqual([r["kind"] for r in rows][:2], ["short", "episode"])

    def test_the_segment_key_changes_only_when_the_source_changes(self):
        a = yt_live.plan([asset("deepdive-dd3", "dd3-episode.mp4", 10)])[0]["key"]
        b = yt_live.plan([asset("deepdive-dd3", "dd3-episode.mp4", 10)])[0]["key"]
        c = yt_live.plan([asset("deepdive-dd3", "dd3-episode.mp4", 11)])[0]["key"]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(a.startswith("norm-dd3-episode-") and a.endswith(".mp4"))

    def test_a_deep_dive_whose_saturday_has_not_come_stays_out_of_the_loop(self):
        rows = [{"title": "Advance Rent (Deep-Dive 4)", "publish_at": "2026-10-31T18:00:00Z"},
                {"title": "Rent Receipt (Deep-Dive 3)", "publish_at": "2026-10-24T18:00:00Z"},
                {"title": "Caution Fee (Deep-Dive 2)", "publish_at": None}]
        now = datetime(2026, 10, 26, 6, 0, tzinfo=timezone.utc)
        self.assertEqual(yt_live.hidden_episodes(rows, now), {"dd4"})
        self.assertEqual(yt_live.hidden_episodes(rows, datetime(2026, 10, 31, 18, 0, 1, tzinfo=timezone.utc)), set())
        plan = yt_live.plan([asset("deepdive-dd4", "dd4-episode.mp4"), asset("deepdive-dd3", "dd3-episode.mp4")],
                            hidden={"dd4"})
        self.assertEqual([r["name"] for r in plan], ["dd3-episode.mp4"])

    def test_an_empty_library_is_an_empty_plan(self):
        self.assertEqual(yt_live.plan([]), [])
        self.assertEqual(yt_live.plan(None), [])


class FfmpegTests(unittest.TestCase):
    def test_every_clip_is_normalised_to_the_one_streamable_profile(self):
        for kind in ("short", "episode"):
            cmd = yt_live.normalise_cmd("in.mp4", "out.mp4", kind, backdrop="bd.jpg")
            joined = " ".join(cmd)
            self.assertIn("-c:v libx264", joined)
            self.assertIn("-g %d -keyint_min %d -sc_threshold 0" % (yt_live.GOP, yt_live.GOP), joined)
            self.assertIn("-c:a aac", joined)
            self.assertIn("-ar 44100 -ac 2", joined)
            self.assertIn("fps=%d" % yt_live.FPS, joined)
            self.assertIn("format=yuv420p", joined)
            self.assertEqual(cmd[-1], "out.mp4")
        self.assertLessEqual(yt_live.GOP, 4 * yt_live.FPS, "YouTube ingest wants a keyframe at most every 4 s")

    def test_a_short_stands_on_the_brand_backdrop_and_an_episode_is_fitted(self):
        short = " ".join(yt_live.normalise_cmd("s.mp4", "o.mp4", "short", backdrop="bd.jpg"))
        episode = " ".join(yt_live.normalise_cmd("e.mp4", "o.mp4", "episode", backdrop="bd.jpg"))
        self.assertIn("overlay=", short)
        self.assertIn("bd.jpg", short)
        self.assertIn("scale=-2:1080", short)
        self.assertIn("force_original_aspect_ratio=decrease", episode)
        self.assertIn("pad=1920:1080", episode)
        self.assertNotIn("overlay", episode)

    def test_without_a_backdrop_a_short_is_padded_rather_than_dropped(self):
        cmd = " ".join(yt_live.normalise_cmd("s.mp4", "o.mp4", "short", backdrop=None))
        self.assertIn("pad=1920:1080", cmd)

    def test_the_stream_copies_bytes_in_a_loop_at_real_time(self):
        cmd = yt_live.stream_cmd("reel.mp4", "rtmps://a.rtmps.youtube.com/live2/", "k3y")
        self.assertEqual(cmd[-1], "rtmps://a.rtmps.youtube.com/live2/k3y")
        self.assertIn("-re", cmd)
        self.assertEqual(cmd[cmd.index("-stream_loop") + 1], "-1")
        self.assertEqual(cmd[cmd.index("-c") + 1], "copy")
        self.assertNotIn("libx264", cmd)
        self.assertEqual(cmd[cmd.index("-f") + 1], "flv")
        self.assertIn("-nostdin", cmd)

    def test_the_concat_list_quotes_its_paths(self):
        text = yt_live.concat_list([Path("/tmp/a b.mp4"), Path("/tmp/it's.mp4")])
        self.assertEqual(text.splitlines()[0], "file '/tmp/a b.mp4'")
        self.assertIn(r"it'\''s.mp4", text)
        cmd = yt_live.concat_cmd("reel.txt", "reel.mp4")
        self.assertIn("concat", cmd)
        self.assertEqual(cmd[cmd.index("-c") + 1], "copy")


class BroadcastTests(unittest.TestCase):
    def test_the_broadcast_is_public_auto_starts_and_never_auto_stops(self):
        body = yt_live.broadcast_body(datetime(2026, 10, 26, 6, 0, tzinfo=timezone.utc))
        self.assertEqual(body["status"]["privacyStatus"], "public")
        self.assertIs(body["status"]["selfDeclaredMadeForKids"], False)
        self.assertIs(body["contentDetails"]["enableAutoStart"], True)
        self.assertIs(body["contentDetails"]["enableAutoStop"], False)
        self.assertIs(body["contentDetails"]["monitorStream"]["enableMonitorStream"], False)
        self.assertEqual(body["snippet"]["scheduledStartTime"], "2026-10-26T06:00:00Z")

    def test_the_title_and_description_say_it_is_pre_recorded(self):
        self.assertLessEqual(len(yt_live.TITLE), 100)
        self.assertIn("pre-recorded", yt_live.TITLE.lower())
        self.assertIn("not a live presenter", yt_live.DESCRIPTION)
        self.assertIn("docoga.com.ng", yt_live.DESCRIPTION)

    def test_the_stream_is_reusable_rtmp(self):
        body = yt_live.stream_body()
        self.assertIs(body["contentDetails"]["isReusable"], True)
        self.assertEqual(body["cdn"]["ingestionType"], "rtmp")


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self):
        return json.loads(self.text)


class FakeHttp:
    """Scripted YouTube: liveStreams / liveBroadcasts list, insert, bind, transition."""

    def __init__(self, streams=(), active=(), upcoming=()):
        self.streams = list(streams)
        self.active = list(active)
        self.upcoming = list(upcoming)
        self.calls = []

    def request(self, method, url, headers=None, data=None, params=None, files=None):
        params = params or {}
        self.calls.append((method, url.rsplit("/v3/", 1)[1], params))
        if url.endswith("/liveStreams") and method == "GET":
            return FakeResponse(200, {"items": self.streams})
        if url.endswith("/liveStreams") and method == "POST":
            s = {"id": "stream-new", "snippet": json.loads(data)["snippet"],
                 "cdn": {"ingestionInfo": {"rtmpsIngestionAddress": "rtmps://a.rtmps.youtube.com/live2",
                                           "ingestionAddress": "rtmp://a.rtmp.youtube.com/live2",
                                           "streamName": "secret-key"}}}
            self.streams.append(s)
            return FakeResponse(200, s)
        if url.endswith("/liveBroadcasts") and method == "GET":
            return FakeResponse(200, {"items": self.active if params.get("broadcastStatus") == "active" else self.upcoming})
        if url.endswith("/liveBroadcasts") and method == "POST":
            b = {"id": "bc-new", "snippet": json.loads(data)["snippet"], "status": {"lifeCycleStatus": "ready"},
                 "contentDetails": {}}
            return FakeResponse(200, b)
        if url.endswith("/liveBroadcasts/bind"):
            return FakeResponse(200, {"id": params["id"], "contentDetails": {"boundStreamId": params["streamId"]},
                                      "status": {"lifeCycleStatus": "ready"}})
        if url.endswith("/liveBroadcasts/transition"):
            return FakeResponse(200, {"id": params["id"], "status": {"lifeCycleStatus": params["broadcastStatus"]}})
        return FakeResponse(404, {"error": "unscripted %s %s" % (method, url)})


def existing_stream(sid="stream-1"):
    return {"id": sid, "snippet": {"title": yt_live.STREAM_TITLE},
            "cdn": {"ingestionInfo": {"rtmpsIngestionAddress": "rtmps://a.rtmps.youtube.com/live2",
                                      "streamName": "old-key"}}}


class EnsureTests(unittest.TestCase):
    def test_a_live_broadcast_of_ours_is_reused_not_duplicated(self):
        http = FakeHttp(streams=[existing_stream()],
                        active=[{"id": "bc-live", "snippet": {"title": yt_live.TITLE},
                                 "status": {"lifeCycleStatus": "live"}, "contentDetails": {"boundStreamId": "stream-1"}}])
        info = yt_live.ensure(http, log=lambda *_: None)
        self.assertEqual(info["broadcast_id"], "bc-live")
        self.assertFalse(info["created"])
        self.assertEqual(info["stream_key"], "old-key")
        self.assertTrue(info["ingest_url"].startswith("rtmps://"))
        self.assertFalse(any(path == "liveBroadcasts" and m == "POST" for m, path, _ in http.calls))
        self.assertFalse(any(path == "liveBroadcasts/bind" for _, path, _ in http.calls))

    def test_someone_elses_live_video_is_not_mistaken_for_ours(self):
        http = FakeHttp(streams=[existing_stream()],
                        active=[{"id": "bc-other", "snippet": {"title": "Owner testing from phone"},
                                 "status": {"lifeCycleStatus": "live"}, "contentDetails": {}}])
        info = yt_live.ensure(http, log=lambda *_: None)
        self.assertEqual(info["broadcast_id"], "bc-new")
        self.assertTrue(info["created"])

    def test_from_nothing_it_makes_the_stream_the_broadcast_and_binds_them(self):
        http = FakeHttp()
        info = yt_live.ensure(http, log=lambda *_: None)
        self.assertTrue(info["created"] and info["created_stream"])
        self.assertEqual(info["stream_id"], "stream-new")
        bind = [p for _, path, p in http.calls if path == "liveBroadcasts/bind"]
        self.assertEqual(bind[0]["streamId"], "stream-new")
        self.assertEqual(info["watch_url"], "https://www.youtube.com/watch?v=bc-new")

    def test_off_ends_only_our_broadcasts(self):
        http = FakeHttp(active=[{"id": "ours", "snippet": {"title": yt_live.TITLE}},
                               {"id": "theirs", "snippet": {"title": "something else"}}])
        self.assertEqual(yt_live.end_all(http, log=lambda *_: None), ["ours"])

    def test_the_ledger_records_a_broadcast_once(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "live.json"
            yt_live.record({"broadcast_id": "bc-1", "watch_url": "u"}, path=path)
            rows = yt_live.record({"broadcast_id": "bc-1", "watch_url": "u"}, path=path)
            self.assertEqual(len(rows), 1)
            rows = yt_live.record({"broadcast_id": "bc-2", "watch_url": "v"}, path=path)
            self.assertEqual([r["broadcast_id"] for r in rows], ["bc-2", "bc-1"])


class FakeProc:
    def __init__(self, lives_for, clock):
        self.clock = clock
        self.ends_at = clock() + lives_for
        self.terminated = False

    def poll(self):
        return 1 if self.clock() >= self.ends_at and not self.terminated else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


class StreamLoopTests(unittest.TestCase):
    def setUp(self):
        self.t = [0.0]
        self.spawned = []

    def clock(self):
        return self.t[0]

    def sleep(self, s):
        self.t[0] += s

    def popen_factory(self, lives):
        it = iter(lives)

        def popen(cmd):
            self.spawned.append(cmd)
            return FakeProc(next(it, 10 ** 9), self.clock)
        return popen

    def test_a_window_that_runs_to_its_deadline_exits_clean(self):
        code = yt_live.stream("reel.mp4", "rtmps://x/live2", "k", minutes=1, popen=self.popen_factory([10 ** 9]),
                              clock=self.clock, sleep=self.sleep, log=lambda *_: None)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.spawned), 1)

    def test_a_push_that_drops_is_reconnected(self):
        code = yt_live.stream("reel.mp4", "rtmps://x/live2", "k", minutes=10,
                              popen=self.popen_factory([120, 90, 10 ** 9]),
                              clock=self.clock, sleep=self.sleep, log=lambda *_: None)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.spawned), 3)

    def test_five_quick_deaths_in_a_row_are_a_visible_failure(self):
        code = yt_live.stream("reel.mp4", "rtmps://x/live2", "k", minutes=60,
                              popen=self.popen_factory([5, 5, 5, 5, 5, 10 ** 9]),
                              clock=self.clock, sleep=self.sleep, log=lambda *_: None)
        self.assertEqual(code, 3)
        self.assertEqual(len(self.spawned), 5)

    def test_a_long_run_resets_the_quick_death_count(self):
        code = yt_live.stream("reel.mp4", "rtmps://x/live2", "k", minutes=60,
                              popen=self.popen_factory([5, 5, 5, 5, 600, 5, 5, 10 ** 9]),
                              clock=self.clock, sleep=self.sleep, log=lambda *_: None)
        self.assertEqual(code, 0)


class BuildTests(unittest.TestCase):
    def test_a_banked_segment_is_downloaded_and_a_new_clip_is_normalised_then_banked(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Path(d) / "lib"
            rows = yt_live.plan([asset("deepdive-dd3", "dd3-episode.mp4"), asset("live-library", "short-2026-10-26.mp4")])
            banked = rows[1]["key"]                      # the episode's normalised copy is already on the release
            ran, uploaded = [], []

            def download(release, name, dest):
                if name == banked:
                    (Path(dest) / name).write_bytes(b"seg")
                elif name.startswith("norm-"):
                    raise FileNotFoundError(name)
                else:
                    (Path(dest) / name).write_bytes(b"src")

            class R:
                returncode = 0

            def run(cmd):
                ran.append(cmd)
                Path(cmd[-1]).write_bytes(b"out")
                return R()

            segs = yt_live.build(rows, lib, Path(d) / "reel.mp4", download, uploaded.append, log=lambda *_: None, run=run)
            self.assertEqual([s.name for s in segs], [rows[0]["key"], banked])
            self.assertEqual(len([c for c in ran if "-c:v" in c]), 1, "only the Short was encoded")
            self.assertEqual([p.name for p in uploaded], [rows[0]["key"]])
            self.assertTrue((Path(d) / "reel.mp4").is_file())

    def test_no_clip_at_all_is_an_error_not_a_silent_black_stream(self):
        with tempfile.TemporaryDirectory() as d:
            def download(*_):
                raise FileNotFoundError("gone")
            with self.assertRaises(RuntimeError):
                yt_live.build(yt_live.plan([asset("deepdive-dd3", "dd3-episode.mp4")]), d, Path(d) / "reel.mp4",
                              download, lambda p: None, log=lambda *_: None, run=lambda cmd: None)


@unittest.skipIf(yaml is None, "PyYAML is required for the workflow contract tests")
class WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wf = yaml.safe_load(LIVE_YML.read_text(encoding="utf-8"))
        cls.job = cls.wf["jobs"]["live"]
        cls.steps = cls.job["steps"]
        cls.by_name = {s.get("name"): s for s in cls.steps}
        cls.shorts = yaml.safe_load(SHORTS_YML.read_text(encoding="utf-8"))

    def test_two_windows_can_never_stream_at_once(self):
        self.assertEqual(self.wf["concurrency"]["group"], "docoga-live")
        self.assertIs(self.wf["concurrency"]["cancel-in-progress"], False)

    def test_the_window_fits_inside_the_six_hour_job_limit(self):
        self.assertLessEqual(self.job["timeout-minutes"], 360)
        self.assertGreater(self.job["timeout-minutes"], yt_live.LIVE_MINUTES)

    def test_each_window_queues_its_successor_and_may_do_so(self):
        step = self.by_name["Queue the next window"]
        self.assertIn("gh workflow run youtube_live.yml", step["run"])
        self.assertEqual(self.wf["permissions"]["actions"], "write")
        self.assertIs(step.get("continue-on-error"), True)

    def test_the_kill_switch_ends_the_broadcast_and_gates_every_streaming_step(self):
        switch = self.by_name["Honour the kill switch"]
        self.assertIn("vars.DOCOGA_LIVE", str(switch["env"]))
        self.assertIn("yt_live.py off", switch["run"])
        for name in ("Queue the next window", "Read the library", "Find or create the broadcast", "Stream this window"):
            self.assertIn("steps.switch.outputs.on == 'yes'", str(self.by_name[name].get("if", "")), name)

    def test_the_stream_key_is_masked_before_the_stream_starts(self):
        names = [s.get("name") for s in self.steps]
        ensure = self.by_name["Find or create the broadcast"]
        self.assertIn("::add-mask::", ensure["run"])
        self.assertLess(names.index("Find or create the broadcast"), names.index("Stream this window"))

    def test_every_step_that_runs_gh_declares_a_token(self):
        for step in self.steps:
            if "gh " in str(step.get("run", "")):
                with self.subTest(step=step.get("name")):
                    self.assertIn("GH_TOKEN", str(step.get("env", "")))

    def test_the_clock_can_dispatch_it_and_the_backstop_is_six_hourly(self):
        on = self.wf[True]
        self.assertIn("workflow_dispatch", on)
        self.assertEqual([c["cron"] for c in on["schedule"]], ["5 0 * * *", "5 6 * * *", "5 12 * * *", "5 18 * * *"])

    def test_the_ledger_commit_uses_the_existence_checked_add(self):
        step = self.by_name["Commit the broadcast ledger"]
        self.assertIn('if [ -e "$path" ]; then git add "$path"; fi', step["run"])
        self.assertIn("[skip ci]", step["run"])

    def test_the_shorts_lane_banks_every_published_short_for_the_loop(self):
        steps = self.shorts["jobs"]["generate-and-publish"]["steps"]
        bank = next(s for s in steps if s.get("name") == "Bank the Short for DocOga Live")
        self.assertIn("steps.upload.outputs.video_id != ''", bank["if"])
        self.assertIn("vars.DOCOGA_LIVE", bank["if"])
        self.assertIs(bank.get("continue-on-error"), True)
        self.assertIn("GH_TOKEN", str(bank["env"]))
        self.assertIn("gh release upload", bank["run"])
        self.assertIn("short-$RUN_DATE.mp4", bank["run"])
        self.assertIn("live-library", bank["run"])


if __name__ == "__main__":
    unittest.main()
