#!/usr/bin/env python3
"""
Facebook Stories lane — tools/fb_publish.py (story_*) + scripts/facebook_story_daily.py
======================================================================================

Owner, 15 Oct 2026: "Hope you know you are to post stories as well."

A Page Story is a two-call protocol (unpublished media → the stories edge), it
expires in 24 h, and the tray is the only record. These tests pin the call
shapes, the tray-based once-a-day guard, the two daily slots (different copy),
the Reel-as-video-Story hand-off, and the workflow wiring.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT = TOOLS_DIR.parent
for _p in (TOOLS_DIR, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

os.environ.setdefault("DOCOGA_LOG_DIR", tempfile.mkdtemp(prefix="docoga-stories-log-"))

import fb_publish  # noqa: E402
import social_card  # noqa: E402
import facebook_story_daily as lane  # noqa: E402

try:
    import yaml  # noqa: E402
    YAML_OK = True
except Exception:  # pragma: no cover
    YAML_OK = False

TOKEN = "EAAB-test-token"
PAGE = "102466208923830"


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def ok(payload):
    return FakeResponse(payload)


def api_error(code, message, status=400):
    return FakeResponse({"error": {"message": message, "type": "OAuthException", "code": code}}, status)


class Graph:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = replies or {}

    def request(self, method, url, **kw):
        self.calls.append({"method": method, "url": url, "data": kw.get("data"), "files": kw.get("files"),
                           "params": kw.get("params"), "headers": kw.get("headers")})
        for key, reply in self.replies.items():
            if key in url:
                return reply(url, kw) if callable(reply) else reply
        return ok({"id": "x"})

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)

    def delete(self, url, **kw):
        return self.request("DELETE", url, **kw)

    def posts(self, tail):
        return [c for c in self.calls if c["method"] == "POST" and c["url"].endswith(tail)]


def patched(graph):
    return [patch.object(fb_publish.requests, "get", graph.get),
            patch.object(fb_publish.requests, "post", graph.post),
            patch.object(fb_publish.requests, "delete", graph.delete)]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"FB_PAGE_ACCESS_TOKEN": TOKEN, "FB_PAGE_ID": PAGE,
                                           "STORIES_MODE": "on"}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.assets = patch.object(lane, "ASSETS_DIR", Path(self.tmp.name))
        self.assets.start()
        self.addCleanup(self.assets.stop)

    def frame(self, name="f.jpg"):
        p = Path(self.tmp.name) / name
        with redirect_stdout(io.StringIO()):
            social_card.render("Rent Due Soon?\n\nHave the receipt ready.", p, kicker="t",
                               size=(social_card.STORY_W, social_card.STORY_H), safe=social_card.STORY_SAFE)
        return p

    def run_with(self, graph, fn, *a, **kw):
        ps = patched(graph)
        for p in ps:
            p.start()
        try:
            with redirect_stdout(io.StringIO()) as out:
                result = fn(*a, **kw)
        finally:
            for p in ps:
                p.stop()
        return result, out.getvalue()


class PhotoStoryProtocolTests(Base):
    def test_photo_story_is_unpublished_photo_then_photo_stories(self):
        graph = Graph({"/photos": ok({"id": "ph1"}), "/photo_stories": ok({"success": True, "post_id": "PAGE_s1"})})
        (okk, detail), _ = self.run_with(graph, fb_publish.story_photo, TOKEN, PAGE, str(self.frame()))
        self.assertTrue(okk, detail)
        self.assertEqual(detail, "PAGE_s1")
        photo = graph.posts("/photos")[0]
        self.assertEqual(photo["data"]["published"], "false", "the photo must not land in the feed")
        self.assertIn("source", photo["files"], "bytes, not a URL — assets/ is not deployed")
        story = graph.posts("/photo_stories")[0]
        self.assertEqual(story["data"]["photo_id"], "ph1")
        self.assertLess(graph.calls.index(photo), graph.calls.index(story))

    def test_a_refused_tray_call_is_legible_and_names_the_orphan_photo(self):
        graph = Graph({"/photos": ok({"id": "ph9"}), "/photo_stories": api_error(10, "Application does not have permission")})
        (okk, detail), _ = self.run_with(graph, fb_publish.story_photo, TOKEN, PAGE, str(self.frame()))
        self.assertFalse(okk)
        self.assertIn("ph9", detail)
        self.assertIn("permission", detail)

    def test_missing_file_and_oversize_are_refused_locally(self):
        okk, detail = fb_publish.story_photo(TOKEN, PAGE, "/nonexistent.jpg")
        self.assertFalse(okk)
        self.assertIn("not found", detail)
        big = Path(self.tmp.name) / "big.jpg"
        big.write_bytes(b"\0" * (fb_publish.STORY_PHOTO_MAX_BYTES + 1))
        okk, detail = fb_publish.story_photo(TOKEN, PAGE, str(big))
        self.assertFalse(okk)
        self.assertIn("4 MB", detail)


class VideoStoryProtocolTests(Base):
    def video(self, seconds=24.0):
        p = Path(self.tmp.name) / "reel.mp4"
        p.write_bytes(b"\0" * 5000)
        self.spec = patch.object(fb_publish, "reel_spec_ok",
                                 return_value=(True, "ok", {"seconds": seconds, "width": 1080, "height": 1920,
                                                            "codec": "h264", "bytes": 5000}))
        self.spec.start()
        self.addCleanup(self.spec.stop)
        return p

    def test_video_story_is_start_upload_finish_on_the_video_stories_edge(self):
        graph = Graph({"/video_stories": lambda url, kw: ok({"video_id": "v1", "upload_url": "u"})
                       if kw["data"].get("upload_phase") == "start" else ok({"success": True, "post_id": "PAGE_v1"}),
                       "rupload": ok({"success": True})})
        (okk, detail), _ = self.run_with(graph, fb_publish.story_video, TOKEN, PAGE, str(self.video()))
        self.assertTrue(okk, detail)
        self.assertEqual(detail["post_id"], "PAGE_v1")
        phases = [c["data"].get("upload_phase") for c in graph.posts("/video_stories")]
        self.assertEqual(phases, ["start", "finish"])
        up = [c for c in graph.calls if "rupload" in c["url"]][0]
        self.assertEqual(up["headers"]["Authorization"], "OAuth " + TOKEN)
        self.assertEqual(up["headers"]["file_size"], "5000")
        self.assertNotIn("/video_reels", " ".join(c["url"] for c in graph.calls))

    def test_a_reel_over_sixty_seconds_is_refused_before_any_call(self):
        graph = Graph()
        (okk, detail), _ = self.run_with(graph, fb_publish.story_video, TOKEN, PAGE, str(self.video(seconds=75.0)))
        self.assertFalse(okk)
        self.assertIn("3–60 s", detail)
        self.assertEqual(graph.calls, [])

    def test_the_probe_opens_and_abandons_a_video_stories_session(self):
        graph = Graph({"/video_stories": ok({"video_id": "v7", "upload_url": "u"})})
        (okk, detail), _ = self.run_with(graph, fb_publish.story_probe, TOKEN, PAGE)
        self.assertTrue(okk)
        self.assertIn("v7", detail)
        self.assertEqual([c["method"] for c in graph.calls], ["POST", "DELETE"])
        self.assertFalse(any(c["data"] and c["data"].get("upload_phase") == "finish" for c in graph.calls))


class TrayGuardTests(Base):
    def tray(self, items):
        return Graph({"/stories": ok({"data": items})})

    def test_the_tray_is_read_in_lagos_time(self):
        graph = self.tray([{"post_id": "a", "media_type": "photo", "creation_time": "2026-10-15T23:30:00+0000"},
                           {"post_id": "b", "media_type": "photo", "creation_time": "2026-10-15T08:40:00+0000"}])
        (okk, hits), _ = self.run_with(graph, fb_publish.stories_today, TOKEN, PAGE, when=date(2026, 10, 16))
        self.assertTrue(okk)
        self.assertEqual([h["post_id"] for h in hits], ["a"], "23:30Z is 00:30 the next day in Lagos")

    def tagged(self, items, alts):
        """A tray whose photo Stories answer GET /{media_id} with the given alt texts."""
        replies = {"/stories": ok({"data": items})}
        for media_id, alt in alts.items():
            replies["/%s" % media_id] = ok({"id": media_id, "alt_text_custom": alt})
        return replies

    def test_a_slot_already_in_the_tray_stands_down_by_its_tag(self):
        items = [{"post_id": "a", "media_id": "m1", "media_type": "photo", "creation_time": "2026-10-16T08:40:00+0000"}]
        graph = Graph(self.tagged(items, {"m1": "DocOga · don't wait · 2026-10-16 · morning"}))
        code, out = self.run_with(graph, lane.main, ["--slot", "morning", "--date", "2026-10-16"])
        self.assertEqual(code, 0)
        self.assertIn("already in today's tray", out)
        self.assertEqual(graph.posts("/photo_stories"), [])

    def test_the_other_slot_still_posts_and_carries_its_own_tag(self):
        items = [{"post_id": "a", "media_id": "m1", "media_type": "photo", "creation_time": "2026-10-16T08:40:00+0000"}]
        replies = self.tagged(items, {"m1": "DocOga · don't wait · 2026-10-16 · morning"})
        replies.update({"/photos": ok({"id": "ph2"}), "/photo_stories": ok({"success": True, "post_id": "PAGE_s2"})})
        graph = Graph(replies)
        code, out = self.run_with(graph, lane.main, ["--slot", "afternoon", "--date", "2026-10-16"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(graph.posts("/photo_stories")), 1)
        alt = graph.posts("/photos")[0]["data"]["alt_text_custom"]
        self.assertIn("2026-10-16 · afternoon", alt)
        self.assertTrue(alt.startswith("DocOga · "))

    def test_day_one_a_hand_run_afternoon_slot_is_not_repeated_by_the_cron(self):
        """15 Oct 2026: the afternoon slot was dispatched at 07:46; the 16:00 cron must see it."""
        items = [{"post_id": "a", "media_id": "m1", "media_type": "photo", "creation_time": "2026-10-15T06:46:00+0000"}]
        graph = Graph(self.tagged(items, {"m1": "DocOga · your turn · 2026-10-15 · afternoon"}))
        code, out = self.run_with(graph, lane.main, ["--slot", "afternoon", "--date", "2026-10-15"])
        self.assertEqual(code, 0)
        self.assertEqual(graph.posts("/photo_stories"), [])
        # …and the morning slot, never posted that day, is still free to post
        replies = self.tagged(items, {"m1": "DocOga · your turn · 2026-10-15 · afternoon"})
        replies.update({"/photos": ok({"id": "ph9"}), "/photo_stories": ok({"success": True, "post_id": "PAGE_s9"})})
        graph = Graph(replies)
        code, out = self.run_with(graph, lane.main, ["--slot", "morning", "--date", "2026-10-15"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(graph.posts("/photo_stories")), 1)

    def test_three_photo_stories_is_the_sanity_cap_even_without_tags(self):
        items = [{"post_id": p, "media_id": m, "media_type": "photo", "creation_time": "2026-10-16T08:40:00+0000"}
                 for p, m in (("a", "m1"), ("b", "m2"), ("c", "m3"))]
        graph = Graph(self.tagged(items, {"m1": "", "m2": "", "m3": ""}))
        code, out = self.run_with(graph, lane.main, ["--slot", "afternoon", "--date", "2026-10-16"])
        self.assertEqual(code, 0)
        self.assertIn("stands down", out)
        self.assertEqual(graph.posts("/photo_stories"), [])

    def test_force_posts_regardless(self):
        two = [{"post_id": "a", "media_type": "photo", "creation_time": "2026-10-16T08:40:00+0000"},
               {"post_id": "b", "media_type": "photo", "creation_time": "2026-10-16T15:05:00+0000"}]
        graph = Graph({"/stories": ok({"data": two}), "/photos": ok({"id": "ph3"}),
                       "/photo_stories": ok({"success": True, "post_id": "PAGE_s3"})})
        code, out = self.run_with(graph, lane.main, ["--slot", "afternoon", "--date", "2026-10-16", "--force"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(graph.posts("/photo_stories")), 1)
        self.assertFalse(any("/stories" in c["url"] for c in graph.calls if c["method"] == "GET"))

    def test_an_unreadable_tray_does_not_block_the_story(self):
        graph = Graph({"/stories": api_error(100, "nope"), "/photos": ok({"id": "ph4"}),
                       "/photo_stories": ok({"success": True, "post_id": "PAGE_s4"})})
        code, out = self.run_with(graph, lane.main, ["--slot", "morning", "--date", "2026-10-16"])
        self.assertEqual(code, 0, out)
        self.assertIn("could not read the tray", out)
        self.assertEqual(len(graph.posts("/photo_stories")), 1)


class SlotCopyTests(Base):
    def test_morning_is_the_posts_copy_and_afternoon_is_the_other_type(self):
        for day in range(12, 19):
            d = date(2026, 10, day)
            with redirect_stdout(io.StringIO()):
                m_msg, m_type = lane.copy_for(d, "morning")
                a_msg, a_type = lane.copy_for(d, "afternoon")
                post = lane.gen.generate(d, write=False)
            self.assertEqual((m_msg, m_type), (post["message"], post["post_type"]))
            self.assertNotEqual(a_type, m_type, "the tray must show two different cards (%s)" % d)
            self.assertNotEqual(a_msg, m_msg)
            self.assertEqual(lane.copy_for(d, "afternoon"), (a_msg, a_type), "deterministic per day")

    def test_the_frame_is_a_9_16_brand_card_with_type_out_of_the_chrome_bands(self):
        from PIL import Image
        with redirect_stdout(io.StringIO()):
            path, post_type = lane.render_story(date(2026, 10, 16), "morning")
        self.assertTrue(path.endswith("facebook_story_2026-10-16-morning.jpg"))
        self.assertFalse(social_card.is_banned_photo(path))
        with Image.open(path) as im:
            self.assertEqual(im.size, (1080, 1920))
            rgb = im.convert("RGB")
            # top and bottom 250 px are Facebook's chrome bands: pure ground, no type
            for y in (40, 120, 230, 1700, 1800, 1900):
                for x in range(96, 1080 - 96, 48):
                    r, g, b = rgb.getpixel((x, y))
                    self.assertLess(r + g + b, 120, "type found in the chrome band at (%d,%d)" % (x, y))
            bright = sum(1 for y in range(300, 1650, 6) for x in range(96, 984, 6)
                         if sum(rgb.getpixel((x, y))) > 400)
            self.assertGreater(bright, 300, "the frame is empty — nothing was drawn")


class ModeAndVideoSlotTests(Base):
    def test_off_switch_posts_nothing(self):
        graph = Graph()
        with patch.dict(os.environ, {"STORIES_MODE": "off"}):
            code, out = self.run_with(graph, lane.main, ["--slot", "morning", "--date", "2026-10-16"])
        self.assertEqual(code, 0)
        self.assertEqual(graph.calls, [])
        self.assertIn("disabled", out)

    def test_video_slot_posts_the_reel_once(self):
        video = Path(self.tmp.name) / "docoga_reel_20261016.mp4"
        video.write_bytes(b"\0" * 5000)
        with patch.object(fb_publish, "reel_spec_ok",
                          return_value=(True, "ok", {"seconds": 28.0, "bytes": 5000, "width": 1080, "height": 1920, "codec": "h264"})):
            graph = Graph({"/stories": ok({"data": []}),
                           "/video_stories": lambda url, kw: ok({"video_id": "v2", "upload_url": "u"})
                           if kw["data"].get("upload_phase") == "start" else ok({"success": True, "post_id": "PAGE_v2"}),
                           "rupload": ok({"success": True})})
            code, out = self.run_with(graph, lane.main, ["--slot", "video", "--video", str(video), "--date", "2026-10-16"])
            self.assertEqual(code, 0, out)
            self.assertEqual(len(graph.posts("/video_stories")), 2)
            graph = Graph({"/stories": ok({"data": [{"post_id": "v", "media_type": "video",
                                                     "creation_time": "2026-10-16T08:45:00+0000"}]})})
            code, out = self.run_with(graph, lane.main, ["--slot", "video", "--video", str(video), "--date", "2026-10-16"])
            self.assertEqual(code, 0)
            self.assertEqual(graph.posts("/video_stories"), [])

    def test_dry_run_renders_and_probes_but_publishes_nothing(self):
        graph = Graph({"/video_stories": ok({"video_id": "v9", "upload_url": "u"})})
        code, out = self.run_with(graph, lane.main, ["--slot", "morning", "--date", "2026-10-16", "--dry-run"])
        self.assertEqual(code, 0, out)
        self.assertTrue((Path(self.tmp.name) / "facebook_story_2026-10-16-morning.jpg").is_file())
        self.assertEqual(graph.posts("/photo_stories"), [])
        self.assertEqual(graph.posts("/photos"), [])
        self.assertEqual([c["method"] for c in graph.calls], ["POST", "DELETE"])


class AiLabelTests(Base):
    def test_a_voiced_reel_declares_the_ai_label_and_a_silent_one_does_not(self):
        video = Path(self.tmp.name) / "r.mp4"
        video.write_bytes(b"\0" * 10)
        self.assertFalse(fb_publish.ai_voice_in(video))
        video.with_suffix(".audio.json").write_text(json.dumps({"voice": None}), encoding="utf-8")
        self.assertFalse(fb_publish.ai_voice_in(video))
        video.with_suffix(".audio.json").write_text(json.dumps({"voice": "Orus"}), encoding="utf-8")
        self.assertTrue(fb_publish.ai_voice_in(video))

    def test_post_reel_passes_the_label_to_the_start_phase(self):
        video = Path(self.tmp.name) / "r.mp4"
        video.write_bytes(b"\0" * 5000)
        video.with_suffix(".audio.json").write_text(json.dumps({"voice": "Orus"}), encoding="utf-8")
        graph = Graph({"/video_reels": lambda url, kw: ok({"video_id": "v3", "upload_url": "u"})
                       if kw["data"].get("upload_phase") == "start" else ok({"success": True}),
                       "rupload": ok({"success": True})})
        with patch.object(fb_publish, "reel_spec_ok",
                          return_value=(True, "ok", {"seconds": 28.0, "bytes": 5000, "width": 1080, "height": 1920, "codec": "h264"})):
            (okk, detail), out = self.run_with(graph, fb_publish.post_reel, TOKEN, PAGE, str(video), verify=False)
        self.assertTrue(okk, detail)
        start = [c for c in graph.posts("/video_reels") if c["data"].get("upload_phase") == "start"][0]
        self.assertEqual(start["data"].get("is_ai_generated"), "true")


@unittest.skipUnless(YAML_OK, "PyYAML not installed")
class WorkflowTests(unittest.TestCase):
    def steps(self, name):
        doc = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
        out = []
        for job in doc["jobs"].values():
            out += job.get("steps") or []
        return doc, [s for s in out if s.get("name")]

    def test_morning_story_follows_the_daily_post_and_never_turns_it_red(self):
        _, steps = self.steps("facebook_autopost.yml")
        names = [s["name"] for s in steps]
        by = {s["name"]: s for s in steps}
        self.assertLess(names.index("Daily post"), names.index("Story — the day's card in the tray (morning slot)"))
        story = by["Story — the day's card in the tray (morning slot)"]
        self.assertTrue(story.get("continue-on-error"))
        self.assertIn("!inputs.dry_run", str(story.get("if")))
        self.assertIn("--slot morning", story["run"])

    def test_the_reel_becomes_a_video_story_only_after_it_published(self):
        _, steps = self.steps("facebook_autopost.yml")
        names = [s["name"] for s in steps]
        by = {s["name"]: s for s in steps}
        self.assertLess(names.index("Reels — publish"), names.index("Story — the Reel in the tray too"))
        self.assertIn("steps.reel_publish.outcome == 'success'", str(by["Story — the Reel in the tray too"].get("if")))
        self.assertIn("--slot video", by["Story — the Reel in the tray too"]["run"])

    def test_the_dry_run_probes_the_stories_grant(self):
        _, steps = self.steps("facebook_autopost.yml")
        by = {s["name"]: s for s in steps}
        self.assertIn("facebook_story_daily.py --slot morning --dry-run",
                      by["Dry run — credentials and posting rights, nothing published"]["run"])

    def test_the_switch_defaults_to_on(self):
        doc, _ = self.steps("facebook_autopost.yml")
        self.assertEqual(doc["env"]["STORIES_MODE"], "${{ vars.FB_STORIES || 'on' }}")
        doc, _ = self.steps("facebook_story_afternoon.yml")
        self.assertEqual(doc["env"]["STORIES_MODE"], "${{ vars.FB_STORIES || 'on' }}")

    def test_the_afternoon_workflow_is_its_own_small_lane(self):
        doc, steps = self.steps("facebook_story_afternoon.yml")
        on = doc.get("on") or doc.get(True)
        self.assertEqual(on["schedule"][0]["cron"], "40 18 * * *", "19:40 WAT — the evening peak (brain/strategy.md)")
        self.assertEqual(doc["concurrency"]["group"], "facebook-autopost", "one publisher at a time")
        self.assertEqual(doc["permissions"], {"contents": "read"})
        run = [s for s in steps if s["name"] == "Story — afternoon slot"][0]["run"]
        self.assertIn("--slot afternoon", run)
        self.assertNotIn("post_facebook.py", " ".join(s.get("run", "") for s in steps))
        self.assertNotIn("facebook_reel_daily.py", " ".join(s.get("run", "") for s in steps))


if __name__ == "__main__":
    unittest.main()
