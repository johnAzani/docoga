"""DocOga Live — the always-on stream (tools/yt_live.py, youtube_live.yml), 26 Oct 2026.

Owner: "go — I want live stream to always be on for life, pulling in watch time, subscribers
etc." Then, the same morning: "I don't want to run it on GitHub, I don't want to take that risk.
Let's do it in Oracle." What these pin: the loop is built from the channel's own banked
episodes and nothing else; every clip is normalised to one profile so the VM copies bytes
instead of encoding; Actions prepares, keeps the broadcast and checks the air but NEVER
streams; the VM's serve loop follows loop.json and restarts a dead push; the broadcast never
auto-stops; the title says pre-recorded; the key is masked before it can be printed; and the
install script keeps the key at 0600 and the service on Restart=always.
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
DEPLOY = ROOT / "deploy" / "live"


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
            if "mine" in params and "broadcastStatus" in params:
                return FakeResponse(400, {"error": {"code": 400, "message": "Incompatible parameters specified in the request: mine, broadcastStatus",
                                                    "errors": [{"reason": "incompatibleParameters", "domain": "youtube.parameter"}]}})
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


def existing_stream(sid="stream-1", pushing=False):
    return {"id": sid, "snippet": {"title": yt_live.STREAM_TITLE},
            "status": {"streamStatus": "active" if pushing else "inactive"},
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
        http = FakeHttp(streams=[existing_stream(pushing=True)],
                        active=[{"id": "bc-other", "snippet": {"title": "Owner testing from phone"},
                                 "status": {"lifeCycleStatus": "live"}, "contentDetails": {}}])
        info = yt_live.ensure(http, log=lambda *_: None)
        self.assertEqual(info["broadcast_id"], "bc-new")
        self.assertTrue(info["created"])

    def test_from_nothing_it_makes_the_key_and_waits_for_data_before_any_broadcast(self):
        """26–27 Oct: with no machine pushing, a broadcast would sit public as 'waiting' for
        days. The key is made so a host can be set up; the broadcast waits for data."""
        http = FakeHttp()
        info = yt_live.ensure(http, log=lambda *_: None)
        self.assertTrue(info["created_stream"] and info["waiting"])
        self.assertFalse(info["created"])
        self.assertEqual(info["stream_id"], "stream-new")
        self.assertEqual(info["stream_key"], "secret-key")
        self.assertEqual(info["broadcast_id"], "")
        self.assertFalse(any(path == "liveBroadcasts" and m == "POST" for m, path, _ in http.calls))

    def test_once_data_arrives_it_makes_the_broadcast_binds_it_and_takes_it_live(self):
        http = FakeHttp(streams=[existing_stream(pushing=True)])
        info = yt_live.ensure(http, log=lambda *_: None)
        self.assertTrue(info["created"] and not info["waiting"])
        bind = [p for _, path, p in http.calls if path == "liveBroadcasts/bind"]
        self.assertEqual(bind[0]["streamId"], "stream-1")
        trans = [p for _, path, p in http.calls if path == "liveBroadcasts/transition"]
        self.assertEqual(trans[0]["broadcastStatus"], "live")
        self.assertEqual(info["status"], "live")
        self.assertEqual(info["watch_url"], "https://www.youtube.com/watch?v=bc-new")

    def test_broadcast_lookups_never_pair_mine_with_broadcast_status(self):
        """The exact 400 every control run died of, 26–27 Oct 2026."""
        http = FakeHttp(streams=[existing_stream(pushing=True)])
        yt_live.ensure(http, log=lambda *_: None)
        yt_live.end_all(http, log=lambda *_: None)
        for _, path, params in http.calls:
            if path == "liveBroadcasts":
                self.assertFalse("mine" in params and "broadcastStatus" in params, params)

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


class PrepareTests(unittest.TestCase):
    def test_a_banked_segment_is_kept_a_new_clip_is_normalised_and_the_manifest_is_banked(self):
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

            manifest = yt_live.prepare(rows, lib, download, uploaded.append, log=lambda *_: None, run=run,
                                       now=datetime(2026, 10, 26, 18, 5, tzinfo=timezone.utc))
            self.assertEqual([s["key"] for s in manifest["segments"]], [rows[0]["key"], banked])
            self.assertEqual(len([c for c in ran if "-c:v" in c]), 1, "only the Short was encoded")
            self.assertEqual([p.name for p in uploaded], [rows[0]["key"], "loop.json"])
            self.assertEqual(manifest["generated_at"], "2026-10-26T18:05:00Z")
            self.assertTrue(manifest["segments"][0]["url"].startswith("https://github.com/johnAzani/docoga/releases/download/live-library/norm-"))
            self.assertEqual(manifest["ingest_url"], "rtmps://a.rtmps.youtube.com/live2")
            on_disk = json.loads((lib / "loop.json").read_text())
            self.assertEqual(on_disk, manifest)

    def test_a_segment_that_could_not_be_banked_is_left_out_of_the_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            rows = yt_live.plan([asset("deepdive-dd3", "dd3-episode.mp4"), asset("deepdive-dd2", "dd2-episode.mp4")])

            def download(release, name, dest):
                if name.startswith("norm-"):
                    raise FileNotFoundError(name)
                (Path(dest) / name).write_bytes(b"src")

            class R:
                returncode = 0

            def run(cmd):
                Path(cmd[-1]).write_bytes(b"out"); return R()

            def upload(path):
                if "dd2" in path.name:
                    raise RuntimeError("release refused")
            manifest = yt_live.prepare(rows, d, download, upload, log=lambda *_: None, run=run)
            self.assertEqual([s["name"] for s in manifest["segments"]], ["dd3-episode.mp4"],
                             "the VM must never be told to fetch a file that is not on the release")

    def test_no_clip_at_all_is_an_error_not_an_empty_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            def download(*_):
                raise FileNotFoundError("gone")
            with self.assertRaises(RuntimeError):
                yt_live.prepare(yt_live.plan([asset("deepdive-dd3", "dd3-episode.mp4")]), d,
                                download, lambda p: None, log=lambda *_: None, run=lambda cmd: None)


class FakeProc:
    def __init__(self, exits_after_polls=None):
        self.polls = 0
        self.exits_after_polls = exits_after_polls
        self.terminated = False
        self.returncode = None

    def poll(self):
        self.polls += 1
        if self.terminated:
            return 0
        if self.exits_after_polls is not None and self.polls > self.exits_after_polls:
            self.returncode = 1
            return 1
        return None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.terminated = True


class FakeGet:
    """requests.get for the VM: the manifest by URL, segments as streamed bytes."""

    def __init__(self, manifests):
        self.manifests = list(manifests)      # one per call to the manifest URL, last one repeats
        self.calls = []

    def __call__(self, url, **kw):
        self.calls.append(url)
        get = self

        class R:
            status_code = 200

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def json(self_inner):
                m = get.manifests.pop(0) if len(get.manifests) > 1 else get.manifests[0]
                return m

            def iter_content(self_inner, n):
                yield b"segment-bytes"
        return R()


def manifest(stamp, keys):
    return {"generated_at": stamp, "ingest_url": yt_live.INGEST_URL,
            "segments": [{"key": k, "kind": "short", "name": k, "url": "https://x/" + k} for k in keys]}


class ServeTests(unittest.TestCase):
    def run_serve(self, manifests, procs, cycles, lib):
        spawned = []
        it = iter(procs)

        def popen(cmd):
            spawned.append(cmd)
            return next(it)

        class R:
            returncode = 0

        def run(cmd):
            Path(cmd[-1]).write_bytes(b"reel"); return R()
        key = Path(lib) / "key"
        key.write_text("s3cret\n")
        get = FakeGet(manifests)
        code = yt_live.serve(key, lib, manifest_url="https://x/loop.json", popen=popen, sleep=lambda s: None,
                             log=lambda *_: None, get=get, run=run, max_cycles=cycles)
        return code, spawned, get

    def test_first_cycle_fetches_the_loop_builds_the_reel_and_starts_the_push(self):
        with tempfile.TemporaryDirectory() as d:
            code, spawned, get = self.run_serve([manifest("t1", ["norm-a.mp4"])], [FakeProc()], 1, d)
            self.assertEqual(code, 0)
            self.assertEqual(len(spawned), 1)
            self.assertTrue((Path(d) / "norm-a.mp4").is_file())
            self.assertTrue((Path(d) / "reel.mp4").is_file())
            self.assertEqual(spawned[0][-1], yt_live.INGEST_URL + "/s3cret")
            self.assertIn("copy", spawned[0])

    def test_an_unchanged_manifest_leaves_the_push_alone(self):
        with tempfile.TemporaryDirectory() as d:
            p = FakeProc()
            code, spawned, get = self.run_serve([manifest("t1", ["norm-a.mp4"])], [p], 3, d)
            self.assertEqual(len(spawned), 1)
            self.assertFalse(p.terminated)

    def test_a_changed_manifest_rebuilds_the_reel_and_restarts_the_push(self):
        with tempfile.TemporaryDirectory() as d:
            p1, p2 = FakeProc(), FakeProc()
            code, spawned, get = self.run_serve([manifest("t1", ["norm-a.mp4"]), manifest("t2", ["norm-b.mp4", "norm-a.mp4"])],
                                                [p1, p2], 2, d)
            self.assertEqual(len(spawned), 2)
            self.assertTrue(p1.terminated)
            self.assertTrue((Path(d) / "norm-b.mp4").is_file())

    def test_a_segment_no_longer_in_the_loop_is_deleted_from_the_small_disk(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "norm-old.mp4").write_bytes(b"x")
            self.run_serve([manifest("t1", ["norm-a.mp4"])], [FakeProc()], 1, d)
            self.assertFalse((Path(d) / "norm-old.mp4").exists())

    def test_a_dead_push_is_started_again(self):
        with tempfile.TemporaryDirectory() as d:
            code, spawned, get = self.run_serve([manifest("t1", ["norm-a.mp4"])], [FakeProc(exits_after_polls=0), FakeProc()], 1, d)
            self.assertEqual(len(spawned), 2)

    def test_an_unreadable_manifest_keeps_the_old_reel_playing(self):
        with tempfile.TemporaryDirectory() as d:
            p = FakeProc()
            spawned = []

            def popen(cmd):
                spawned.append(cmd); return p

            class R:
                returncode = 0

            def run(cmd):
                Path(cmd[-1]).write_bytes(b"reel"); return R()
            (Path(d) / "key").write_text("k")
            calls = {"n": 0}
            good = manifest("t1", ["norm-a.mp4"])

            def get(url, **kw):
                calls["n"] += 1
                if calls["n"] > 2:
                    raise ConnectionError("github down")
                return FakeGet([good])(url, **kw)
            yt_live.serve(Path(d) / "key", d, manifest_url="https://x/loop.json", popen=popen, sleep=lambda s: None,
                          log=lambda *_: None, get=get, run=run, max_cycles=3)
            self.assertEqual(len(spawned), 1)
            self.assertFalse(p.terminated)

    def test_without_a_key_nothing_is_pushed(self):
        with tempfile.TemporaryDirectory() as d:
            spawned = []

            class R:
                returncode = 0

            def run(cmd):
                Path(cmd[-1]).write_bytes(b"reel"); return R()
            yt_live.serve(Path(d) / "missing-key", d, manifest_url="https://x/loop.json", popen=lambda c: spawned.append(c),
                          sleep=lambda s: None, log=lambda *_: None, get=FakeGet([manifest("t1", ["norm-a.mp4"])]), run=run,
                          max_cycles=1)
            self.assertEqual(spawned, [])


class HealthTests(unittest.TestCase):
    def test_active_is_on_air_and_anything_else_is_not(self):
        on = FakeHttp(streams=[dict(existing_stream(), status={"streamStatus": "active", "healthStatus": {"status": "good"}})])
        self.assertTrue(yt_live.health(on, log=lambda *_: None)[0])
        off = FakeHttp(streams=[dict(existing_stream(), status={"streamStatus": "inactive"})])
        ok, text = yt_live.health(off, log=lambda *_: None)
        self.assertFalse(ok)
        self.assertIn("inactive", text)
        self.assertFalse(yt_live.health(FakeHttp(), log=lambda *_: None)[0])

    def test_the_owner_message_names_the_one_tap_and_no_particular_host(self):
        self.assertIn("Start", yt_live.OWNER_DM)
        self.assertNotIn("Oracle", yt_live.OWNER_DM)       # the box can be any Ubuntu host now

    def test_nobody_is_nagged_before_a_broadcast_has_ever_existed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "live.json"
            self.assertFalse(yt_live.has_been_on_air(path))
            path.write_text("[]")
            self.assertFalse(yt_live.has_been_on_air(path))
            yt_live.record({"broadcast_id": "bc-1", "watch_url": "u"}, path=path)
            self.assertTrue(yt_live.has_been_on_air(path))


class DeployTests(unittest.TestCase):
    def test_the_installer_keeps_the_key_private_and_installs_the_service(self):
        text = (DEPLOY / "install.sh").read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", text)
        self.assertIn("umask 077", text)
        self.assertIn('chmod 600 "$ETC/stream_key"', text)
        self.assertIn("apt-get install", text)
        for pkg in ("ffmpeg", "python3-requests", "git"):
            self.assertIn(pkg, text)
        self.assertIn("systemctl enable docoga-live", text)
        self.assertNotIn("echo \"$KEY\"", text, "the key is never echoed")

    def test_the_service_restarts_forever_and_runs_serve(self):
        unit = (DEPLOY / "docoga-live.service").read_text(encoding="utf-8")
        self.assertIn("Restart=always", unit)
        self.assertIn("StartLimitIntervalSec=0", unit)
        self.assertIn("tools/yt_live.py serve --key-file /etc/docoga-live/stream_key", unit)
        self.assertIn("ReadWritePaths=/var/lib/docoga-live", unit)
        timer = (DEPLOY / "docoga-live-pull.timer").read_text(encoding="utf-8")
        self.assertIn("OnUnitActiveSec=1h", timer)

    def test_the_cloud_init_fetches_main_and_carries_a_placeholder_not_a_key(self):
        text = (DEPLOY / "cloud-init.sh").read_text(encoding="utf-8")
        self.assertIn("raw.githubusercontent.com/johnAzani/docoga/main/deploy/live/install.sh", text)
        self.assertIn("PASTE_STREAM_KEY_HERE", text)


@unittest.skipIf(yaml is None, "PyYAML is required for the workflow contract tests")
class WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wf = yaml.safe_load(LIVE_YML.read_text(encoding="utf-8"))
        cls.job = cls.wf["jobs"]["control"]
        cls.steps = cls.job["steps"]
        cls.by_name = {s.get("name"): s for s in cls.steps}
        cls.shorts = yaml.safe_load(SHORTS_YML.read_text(encoding="utf-8"))

    def test_actions_never_streams(self):
        """Owner, 26 Oct 2026: "I don't want to run it on GitHub, I don't want to take that risk." """
        text = LIVE_YML.read_text(encoding="utf-8")
        self.assertNotIn("yt_live.py stream", text)
        self.assertNotIn("yt_live.py serve", text)
        self.assertNotIn("Queue the next window", text)
        self.assertNotIn("actions: write", text)
        self.assertLessEqual(self.job["timeout-minutes"], 60, "a control run is minutes, never a window")
        self.assertEqual(self.wf["concurrency"]["group"], "docoga-live")

    def test_the_control_run_prepares_keeps_and_checks(self):
        names = [s.get("name") for s in self.steps]
        for name in ("Read the library", "Prepare the loop (normalise what is new, bank the segments and loop.json)",
                     "Keep the broadcast", "Check the air (DM the owner if the streaming machine has gone quiet)"):
            self.assertIn(name, names)
        self.assertIn("yt_live.py prepare", self.by_name["Prepare the loop (normalise what is new, bank the segments and loop.json)"]["run"])
        self.assertIn("yt_live.py health", self.by_name["Check the air (DM the owner if the streaming machine has gone quiet)"]["run"])
        self.assertIn("TELEGRAM_BOT_TOKEN", str(self.by_name["Check the air (DM the owner if the streaming machine has gone quiet)"]["env"]))

    def test_the_kill_switch_ends_the_broadcast_and_gates_every_step(self):
        switch = self.by_name["Honour the kill switch"]
        self.assertIn("vars.DOCOGA_LIVE", str(switch["env"]))
        self.assertIn("yt_live.py off", switch["run"])
        for name in ("Read the library", "Keep the broadcast", "Check the air (DM the owner if the streaming machine has gone quiet)"):
            self.assertIn("steps.switch.outputs.on == 'yes'", str(self.by_name[name].get("if", "")), name)

    def test_the_stream_key_is_masked_and_the_ingest_file_deleted(self):
        ensure = self.by_name["Keep the broadcast"]
        self.assertIn("::add-mask::", ensure["run"])
        self.assertIn("rm -f /tmp/live.json", ensure["run"])

    def test_every_step_that_runs_gh_declares_a_token(self):
        for step in self.steps:
            if "gh " in str(step.get("run", "")):
                with self.subTest(step=step.get("name")):
                    self.assertIn("GH_TOKEN", str(step.get("env", "")))

    def test_the_clock_can_dispatch_it_and_the_control_runs_are_six_hourly(self):
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
