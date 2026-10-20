#!/usr/bin/env python3
"""v6 footage (owner, 20 Oct 2026, evening): "free video clip per spoken sentence; where there is
no video clip use image per spoken sentence; as many free platforms as possible; it must match
what is being said and have the Nigerian feel." Every door is exercised against a recorded-shape
reply, nothing here touches the network, and the bake is proven on a synthetic clip."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from PIL import Image  # noqa: E402

import stock_media as sm  # noqa: E402


def _ffmpeg():
    import motionstudio
    try:
        return motionstudio.find_ffmpeg()
    except Exception:
        return None


FF = _ffmpeg()


class FakeHTTP:
    """url-prefix → JSON body (or bytes). Every call is logged."""
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url, headers=None, accept="application/json", max_bytes=0):
        self.calls.append((url, dict(headers or {})))
        for prefix, body in self.routes.items():
            if url.startswith(prefix):
                if isinstance(body, Exception):
                    raise body
                return (json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body), "application/json"
        raise OSError("no route for " + url)


PIXABAY_VIDEO = {"hits": [
    {"id": 101, "pageURL": "https://pixabay.com/videos/lagos-market-street-nigeria-101/", "duration": 14,
     "tags": "lagos, market, street, nigeria", "user": "ade",
     "videos": {"large": {"url": "https://cdn.pixabay.com/v/101_large.mp4", "width": 2160, "height": 3840, "size": 200_000_000},
                "medium": {"url": "https://cdn.pixabay.com/v/101_medium.mp4", "width": 1080, "height": 1920, "size": 9_000_000},
                "small": {"url": "https://cdn.pixabay.com/v/101_small.mp4", "width": 540, "height": 960, "size": 2_000_000}}},
    {"id": 102, "pageURL": "https://pixabay.com/videos/market-stall-paris-102/", "duration": 20,
     "tags": "market, stall, paris, france", "user": "jean",
     "videos": {"large": {"url": "", "width": 0, "height": 0, "size": 0},
                "medium": {"url": "https://cdn.pixabay.com/v/102_medium.mp4", "width": 1920, "height": 1080, "size": 12_000_000},
                "small": {"url": "https://cdn.pixabay.com/v/102_small.mp4", "width": 1280, "height": 720, "size": 3_000_000}}},
    {"id": 103, "pageURL": "https://pixabay.com/videos/woman-portrait-face-103/", "duration": 9,
     "tags": "woman, portrait, face, market", "user": "x",
     "videos": {"medium": {"url": "https://cdn.pixabay.com/v/103_medium.mp4", "width": 1080, "height": 1920, "size": 5_000_000}}},
]}
PIXABAY_PHOTO = {"hits": [{"id": 201, "pageURL": "https://pixabay.com/photos/paper-receipt-201/", "tags": "paper, receipt, bill",
                           "largeImageURL": "https://cdn.pixabay.com/p/201.jpg", "imageWidth": 1280, "imageHeight": 1920, "user": "a"}]}
PEXELS_VIDEO = {"videos": [{"id": 301, "url": "https://www.pexels.com/video/yellow-danfo-bus-in-lagos-traffic-301/", "duration": 11,
                            "width": 1080, "height": 1920, "user": {"name": "Tunde"},
                            "video_files": [{"link": "https://v.pexels.com/301_sd.mp4", "width": 540, "height": 960, "file_type": "video/mp4", "size": 1},
                                            {"link": "https://v.pexels.com/301_uhd.mp4", "width": 2160, "height": 3840, "file_type": "video/mp4", "size": 90},
                                            {"link": "https://v.pexels.com/301_hd.mp4", "width": 1080, "height": 1920, "file_type": "video/mp4", "size": 9}]}]}
COMMONS_VIDEO = {"query": {"pages": [
    {"pageid": 401, "title": "File:Balogun market Lagos street scene.webm",
     "imageinfo": [{"url": "https://upload.wikimedia.org/x/Balogun.webm", "width": 1920, "height": 1080, "mime": "video/webm",
                    "duration": 25.0, "descriptionurl": "https://commons.wikimedia.org/wiki/File:Balogun.webm",
                    "extmetadata": {"LicenseShortName": {"value": "CC0"}, "Categories": {"value": "Markets in Lagos|Videos of Nigeria"},
                                    "Artist": {"value": "<a href='x'>Someone</a>"}}}]},
    {"pageid": 402, "title": "File:Market in Lagos (restricted).webm",
     "imageinfo": [{"url": "https://upload.wikimedia.org/x/R.webm", "width": 1920, "height": 1080, "mime": "video/webm",
                    "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "Categories": {"value": "Lagos"}}}]},
]}}
FLICKR = {"photos": {"photo": [{"id": "501", "owner": "9@N0", "title": "Receipt book, Ikeja", "tags": "receipt paper ikeja lagos",
                                 "license": "9", "url_l": "https://live.staticflickr.com/501_b.jpg", "width_l": 1024, "height_l": 1536}]}}
UNSPLASH = {"results": [{"id": "u1", "alt_description": "white paper receipt on table", "description": None, "width": 3000, "height": 4500,
                         "urls": {"raw": "https://images.unsplash.com/u1?ixid=1", "regular": "https://images.unsplash.com/u1?w=1080"},
                         "links": {"html": "https://unsplash.com/photos/u1", "download_location": "https://api.unsplash.com/photos/u1/download"},
                         "user": {"name": "Ola"}, "tags": [{"title": "receipt"}]}]}


def _jpeg_bytes(size=(1200, 1800), color=(90, 120, 150)):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "JPEG")
    return b.getvalue()


class Gates(unittest.TestCase):
    def test_off_unless_the_lane_says_on(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DOCOGA_SHOTS", None)
            self.assertFalse(sm.enabled())
            cand, note = sm.media_for("Keep the receipt.")
            self.assertIsNone(cand)
            self.assertEqual(note, "stock off")
        with mock.patch.dict(os.environ, {"DOCOGA_SHOTS": "on", "STOCK_MEDIA": "off"}):
            self.assertFalse(sm.enabled(), "the module has its own kill switch")
        with mock.patch.dict(os.environ, {"DOCOGA_SHOTS": "on"}):
            os.environ.pop("STOCK_MEDIA", None)
            self.assertTrue(sm.enabled())

    def test_doors_follow_the_keys_and_commons_is_always_open(self):
        with mock.patch.dict(os.environ, {"PIXABAY_API_KEY": "", "PEXELS_API_KEY": "", "FLICKR_API_KEY": "", "UNSPLASH_ACCESS_KEY": ""}):
            self.assertEqual(sm.doors("video"), ["commons"])
            self.assertEqual(sm.doors("photo"), ["commons"])
            self.assertIn("pixabay:nokey", sm.door_status())
            self.assertIn("commons:on", sm.door_status())
        with mock.patch.dict(os.environ, {"PIXABAY_API_KEY": "k", "PEXELS_API_KEY": "p", "FLICKR_API_KEY": "f", "UNSPLASH_ACCESS_KEY": "u"}):
            self.assertEqual(sm.doors("video"), ["pixabay", "pexels", "commons"])
            self.assertEqual(sm.doors("photo"), ["pixabay", "pexels", "flickr", "unsplash", "commons"])
            self.assertEqual(sm.door_status(), "pixabay:on,pexels:on,flickr:on,unsplash:on,commons:on,openverse:on")


class Words(unittest.TestCase):
    def test_queries_ask_nigeria_first_then_plain_then_the_setting(self):
        qs = sm.queries_for("The landlord must give you a receipt.")
        self.assertEqual(qs[0], ("paper receipt nigeria", True))
        self.assertEqual(qs[1], ("paper receipt", False))
        self.assertEqual(qs[-1], ("lagos street nigeria", True))
        self.assertLessEqual(len(qs), 5)
        self.assertEqual(len({q for q, _ in qs}), len(qs), "no query twice")

    def test_nigerian_feel_is_a_number(self):
        self.assertEqual(sm.nigeria_bonus("yellow danfo bus lagos traffic"), 3)
        self.assertEqual(sm.nigeria_bonus("busy african market"), 2)
        self.assertEqual(sm.nigeria_bonus("paris market stall"), 0)

    def test_scoring_prefers_the_nigerian_portrait_clip_that_fits_the_sentence(self):
        q = "market stall nigeria"
        a = {"kind": "video", "title": "lagos market street nigeria", "tags_text": "", "width": 1080, "height": 1920, "duration": 14}
        b = {"kind": "video", "title": "market stall paris", "tags_text": "", "width": 1920, "height": 1080, "duration": 20}
        c = {"kind": "video", "title": "market nigeria", "tags_text": "", "width": 1080, "height": 1920, "duration": 2}
        self.assertGreater(sm.score(a, q, 6.0), sm.score(b, q, 6.0))
        self.assertGreater(sm.score(a, q, 6.0), sm.score(c, q, 6.0), "a two-second clip under a six-second sentence loses")

    def test_no_close_faces_and_nothing_irrelevant(self):
        self.assertTrue(sm.excluded("woman portrait face market"))
        self.assertFalse(sm.excluded("lagos market street crowd"))
        cands = [{"id": "x", "url": "u", "title": "sunset beach", "tags_text": "", "kind": "video"},
                 {"id": "y", "url": "u", "title": "woman portrait market", "tags_text": "", "kind": "video"}]
        self.assertIsNone(sm.choose(cands, "market stall", 4.0))


class Doors(unittest.TestCase):
    def setUp(self):
        sm._CACHE.clear()
        self.tmp = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"DOCOGA_SHOTS": "on", "STOCK_MEDIA": "on", "STOCK_MEDIA_CACHE": self.tmp,
                                                "PIXABAY_API_KEY": "pk", "PEXELS_API_KEY": "xk", "FLICKR_API_KEY": "fk",
                                                "UNSPLASH_ACCESS_KEY": "uk"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pixabay_video_picks_the_full_hd_file_and_skips_the_face(self):
        http = FakeHTTP({"https://pixabay.com/api/videos/": PIXABAY_VIDEO})
        out = sm.search("pixabay", "market stall nigeria", "video", http=http, sleeper=lambda s: None)
        self.assertEqual([c["id"] for c in out], ["pixabay:101", "pixabay:102", "pixabay:103"])
        self.assertEqual(out[0]["url"], "https://cdn.pixabay.com/v/101_medium.mp4", "4K at 200 MB is skipped for the 1080×1920 file")
        self.assertEqual(out[0]["height"], 1920)
        best = sm.choose(out, "market stall nigeria", 6.0)
        self.assertEqual(best["id"], "pixabay:101", "Lagos beats Paris; the portrait face is excluded")
        self.assertIn("key=pk", http.calls[0][0])
        self.assertIn("video_type=film", http.calls[0][0])

    def test_pexels_video_reads_the_slug_and_takes_the_smallest_hd_file(self):
        http = FakeHTTP({"https://api.pexels.com/videos/search": PEXELS_VIDEO})
        out = sm.search("pexels", "yellow bus lagos", "video", http=http, sleeper=lambda s: None)
        self.assertEqual(out[0]["title"], "yellow danfo bus in lagos traffic")
        self.assertEqual(out[0]["url"], "https://v.pexels.com/301_hd.mp4")
        self.assertEqual(http.calls[0][1].get("Authorization"), "xk")
        self.assertIn("orientation=portrait", http.calls[0][0])

    def test_commons_video_is_public_domain_or_nothing(self):
        http = FakeHTTP({"https://commons.wikimedia.org/w/api.php": COMMONS_VIDEO})
        out = sm.search("commons", "market stall nigeria", "video", http=http, sleeper=lambda s: None)
        self.assertEqual([c["id"] for c in out], ["commons:401"], "CC BY-SA needs attribution we do not print — refused")
        self.assertIn("markets in lagos", out[0]["tags_text"])
        self.assertIn("filetype%3Avideo", http.calls[0][0])
        self.assertEqual(sm.nigeria_bonus(out[0]["title"] + " " + out[0]["tags_text"]), 3)

    def test_flickr_is_geofenced_to_nigeria_and_free_licences_only(self):
        http = FakeHTTP({"https://api.flickr.com/services/rest/": FLICKR})
        out = sm.search("flickr", "paper receipt", "photo", http=http, sleeper=lambda s: None)
        self.assertEqual(out[0]["id"], "flickr:501")
        self.assertEqual(out[0]["nigeria"], 3)
        url = http.calls[0][0]
        self.assertIn("bbox=2.67%2C4.27%2C14.68%2C13.89", url)
        self.assertIn("license=7%2C9%2C10", url)
        self.assertEqual(sm.search("flickr", "x", "video", http=http, sleeper=lambda s: None), [], "Flickr has no clips door")

    def test_unsplash_and_pixabay_photos(self):
        http = FakeHTTP({"https://api.unsplash.com/search/photos": UNSPLASH, "https://pixabay.com/api/?": PIXABAY_PHOTO})
        u = sm.search("unsplash", "paper receipt", "photo", http=http, sleeper=lambda s: None)
        self.assertEqual(u[0]["id"], "unsplash:u1")
        self.assertTrue(u[0]["url"].startswith("https://images.unsplash.com/u1?ixid=1&w=1600"))
        self.assertEqual(http.calls[0][1].get("Authorization"), "Client-ID uk")
        p = sm.search("pixabay", "paper receipt", "photo", http=http, sleeper=lambda s: None)
        self.assertEqual(p[0]["id"], "pixabay:201")
        self.assertIn("orientation=vertical", http.calls[1][0])

    def test_a_door_that_is_down_is_a_door_that_is_closed(self):
        http = FakeHTTP({"https://pixabay.com/api/videos/": OSError("boom")})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(sm.search("pixabay", "q", "video", http=http, sleeper=lambda s: None), [])
        self.assertEqual(sm.search("pixabay", "q", "video", http=http, sleeper=lambda s: None), [], "cached: not asked twice")
        self.assertEqual(len(http.calls), 1)

    def test_media_for_takes_the_clip_first_then_the_photo_and_never_the_same_file_twice(self):
        http = FakeHTTP({"https://pixabay.com/api/videos/": PIXABAY_VIDEO,
                         "https://api.pexels.com/videos/search": {"videos": []},
                         "https://commons.wikimedia.org/w/api.php": {"query": {"pages": []}},
                         "https://pixabay.com/api/?": PIXABAY_PHOTO,
                         "https://api.pexels.com/v1/search": {"photos": []},
                         "https://api.flickr.com/services/rest/": {"photos": {"photo": []}},
                         "https://api.unsplash.com/search/photos": {"results": []},
                         "https://cdn.pixabay.com/v/101_medium.mp4": b"\x00" * 2048,
                         "https://cdn.pixabay.com/v/102_medium.mp4": b"\x00" * 2048,
                         "https://cdn.pixabay.com/p/201.jpg": _jpeg_bytes()})
        used = set()
        with redirect_stdout(io.StringIO()):
            first, note = sm.media_for("Traders at the market keep every receipt.", need_s=5.0, used=used, http=http, sleeper=lambda s: None)
            self.assertEqual((first["kind"], first["id"]), ("video", "pixabay:101"))
            self.assertTrue(Path(first["path"]).is_file())
            self.assertEqual(note, "pixabay video")
            second, _ = sm.media_for("The market again.", need_s=5.0, used=used, http=http, sleeper=lambda s: None)
            self.assertEqual(second["id"], "pixabay:102", "the Lagos clip is already in the Short — the next relevant one")
            third, note3 = sm.media_for("Sign the receipt.", need_s=5.0, used=used, http=http, sleeper=lambda s: None)
        self.assertEqual((third["kind"], third["id"]), ("photo", "pixabay:201"), "no clip for a receipt → a photograph")
        self.assertEqual(note3, "pixabay photo")
        self.assertEqual(used, {"pixabay:101", "pixabay:102", "pixabay:201"})
        searches = [u for u, _ in http.calls if "cdn.pixabay" not in u]
        self.assertLessEqual(len(searches), 16, "per-query caching keeps the API budget: %d searches" % len(searches))


@unittest.skipUnless(FF, "ffmpeg not available")
class Bake(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.clip = str(Path(cls.tmp) / "clip.mp4")
        subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", cls.clip], check=True, timeout=120)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_a_clip_becomes_brand_frames_held_past_its_end_with_living_grain(self):
        import numpy as np
        out = sm.bake_clip(self.clip, 3.0, Path(self.tmp) / "bake", duration=2.0, ffmpeg=FF)
        self.assertEqual(out["n"], 90, "3.0 s at 30 fps, even from a 2 s 25 fps clip")
        f1 = Image.open(Path(out["frames"]) / "f_0001.jpg")
        self.assertEqual(f1.size, (1080, 1920))
        a = np.asarray(f1.convert("RGB")).astype(int)
        self.assertLess(a[..., 0].mean(), a[..., 2].mean(), "navy duotone: blue over red")
        self.assertLess(a.max(), 200, "darkened for type like a photograph")
        held1 = np.asarray(Image.open(Path(out["frames"]) / "f_0080.jpg")).astype(int)
        held2 = np.asarray(Image.open(Path(out["frames"]) / "f_0090.jpg")).astype(int)
        d = np.abs(held1 - held2).mean()
        self.assertGreater(d, 0.05, "held frames still breathe (grain is temporal)")
        self.assertLess(d, 3.0, "…but the picture itself is held")
        self.assertTrue((Path(out["frames"]) / "duotone.cube").is_file())

    def test_the_lut_is_the_brand_ramp_times_darken_after_the_photo_stretch(self):
        lut = sm.duotone_lut(20, 220, 0.68)
        self.assertEqual(len(lut), 256)
        self.assertEqual(lut[0], lut[20], "below the 1 % point everything is canvas navy")
        self.assertEqual(lut[220], lut[255])
        r, g, b = lut[255]
        self.assertAlmostEqual(r * 255, 226 * 0.68, delta=1.0)
        self.assertAlmostEqual(b * 255, 250 * 0.68, delta=1.0)

    def test_the_camera_rides_the_clip_frames_and_qa_sees_the_same_background(self):
        import motionstudio as ms
        out = sm.bake_clip(self.clip, 2.0, Path(self.tmp) / "bake2", duration=2.0, ffmpeg=FF)
        first = Image.open(Path(out["frames"]) / "f_0001.jpg").convert("RGB")
        sc = {"id": "T", "dur": 2.0, "punch": 0.0, "beats": [],
              "_shots": [dict(t0=0.0, t1=2.0, img=first, frames=out["frames"], n=out["n"], move="pan-right")]}
        a = ms.camera_bg(sc, 0.5, False)
        b = ms.camera_bg(sc, 0.5, False)
        self.assertEqual(list(a.getdata())[::9973], list(b.getdata())[::9973], "deterministic: render and QA agree")
        import numpy as np
        later = ms.camera_bg(sc, 1.5, False)
        self.assertGreater(np.abs(np.asarray(a).astype(int) - np.asarray(later).astype(int)).mean(), 0.5,
                           "the clip plays under the camera (a still would only drift 10 %)")
        self.assertIs(ms.clip_frame({"img": first}, 0.3), first, "a photo shot is untouched")


class Bridge(unittest.TestCase):
    def test_attach_shots_asks_for_a_clip_first_and_bakes_it(self):
        import datetime
        import shorts_reel
        import motionstudio as ms
        topic = shorts_reel.topic_for(datetime.date(2026, 10, 20))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/_v6.mp4")
        tmp = tempfile.mkdtemp()
        frames = Path(tmp) / "frames"
        frames.mkdir()
        Image.new("RGB", (ms.W, ms.H), (10, 20, 60)).save(frames / "f_0001.jpg")
        photo = Path(tmp) / "p.jpg"
        Image.new("RGB", (1200, 1800), (80, 90, 100)).save(photo)
        answers = [({"kind": "video", "path": "/x/clip.mp4", "door": "pixabay", "id": "pixabay:1", "duration": 12.0, "query": "lagos"}, "pixabay video"),
                   ({"kind": "photo", "path": str(photo), "door": "flickr", "id": "flickr:1", "query": "paper receipt"}, "flickr photo"),
                   (None, "no door had video/photo")]
        calls = {"bake": []}

        def fake_media(text, hint=None, need_s=4.0, used=None, kinds=("video", "photo"), **kw):
            ans = answers.pop(0) if answers else (None, "no door had video/photo")
            if ans[0] is not None:
                used.add(ans[0]["id"])
            return ans

        def fake_bake(path, need_s, out_dir, darken=0.68, duration=None, **kw):
            calls["bake"].append((path, round(need_s, 2), duration, darken))
            return {"frames": str(frames), "n": 1}
        try:
            with mock.patch.dict(os.environ, {"DOCOGA_SHOTS": "on"}), \
                 mock.patch.object(sm, "media_for", side_effect=fake_media), \
                 mock.patch.object(sm, "bake_clip", side_effect=fake_bake), \
                 mock.patch("shot_match.photo_for", return_value=(None, "nothing matched")), \
                 redirect_stdout(io.StringIO()) as out:
                hits = shorts_reel.attach_shots(reel, topic)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertGreaterEqual(hits, 1)
        shots = [s for sc in reel["scenes"] for s in sc.get("_shots", [])]
        self.assertEqual(len(shots), 2)
        self.assertEqual(shots[0]["kind"], "video")
        self.assertEqual((shots[0]["frames"], shots[0]["n"], shots[0]["source"]), (str(frames), 1, "pixabay"))
        self.assertEqual(shots[0]["t0"], 0.0)
        self.assertEqual(calls["bake"][0][0], "/x/clip.mp4")
        self.assertEqual(calls["bake"][0][3], shorts_reel.SHOT_DARKEN)
        self.assertGreater(calls["bake"][0][1], ms.XFADE, "baked long enough to play through the dissolve")
        self.assertEqual(shots[1]["kind"], "photo")
        self.assertEqual(shots[1]["source"], "flickr")
        self.assertEqual(shots[1]["img"].size, (ms.W, ms.H), "a photograph is treated like before")
        text = out.getvalue()
        self.assertIn("SHOTS_VIDEO=1", text)
        self.assertIn("SHOTS_PHOTO=1", text)
        self.assertIn("SHOTS_DOORS=", text)
        self.assertIn("🎬 scene A", text)
        self.assertIn("SHOTS_TOTAL=2", text)

    def test_render_lanes_pass_the_keys_and_the_cards_never_change(self):
        for wf in ("youtube_scheduled.yml", "facebook_autopost.yml", "tiktok_test.yml"):   # the three lanes that render
            src = (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")
            with self.subTest(workflow=wf):
                for key in ("PIXABAY_API_KEY", "PEXELS_API_KEY", "FLICKR_API_KEY", "UNSPLASH_ACCESS_KEY"):
                    self.assertIn("%s: ${{ secrets.%s }}" % (key, key), src)
        body = (ROOT / "tools/shorts_reel.py").read_text(encoding="utf-8")
        self.assertIn("stock_media.media_for(text, hint=sc.get(\"shot\"), need_s=need_s, used=used)", body)
        self.assertIn("stock_media.bake_clip(cand[\"path\"], need_s,", body)
        self.assertIn("kinds=(\"photo\",)", body, "a clip that will not bake falls back to a photograph, never to navy")
        self.assertIn("shot_match.photo_for(text, hint=sc.get(\"shot\"), size=(ms.W, ms.H), treat=_treat)", body,
                      "the 17 Oct Openverse door is still the last door")
        self.assertNotIn("stock_media", (ROOT / "tools/social_card.py").read_text(encoding="utf-8"),
                         "cards keep shot_match's stricter no-people photographs")


if __name__ == "__main__":
    unittest.main()
