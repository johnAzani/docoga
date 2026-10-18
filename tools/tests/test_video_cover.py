"""The first TikTok draft (18 Oct 2026) opened on an empty navy frame, its photographs were too
dark to see, and the caption had to be found on GitHub. These pin the three corrections:

1. MotionStudio's frame 0 is the settled opening card (every platform's default cover) and a
   `.cover.jpg` sits beside each master for the thumbnail calls.
2. The photograph treatment leaves a photograph visible (brightest pixel well above navy).
3. The caption reaches the owner's phone (tools/owner_dm.py) and the Telegram video carries
   the cover as its thumbnail.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

try:
    import motionstudio as ms  # noqa: E402
    from PIL import Image  # noqa: E402
    PIL_OK = True
except Exception:  # pragma: no cover
    PIL_OK = False

FONTS_OK = PIL_OK and ms.find_font_template() is not None


@unittest.skipUnless(PIL_OK, "Pillow/numpy are not installed")
class PosterFrameTests(unittest.TestCase):
    """The cover: the opening scene drawn settled, as frame 0 and as a JPEG."""

    def _reel(self):
        import copy
        reel = copy.deepcopy(ms.REEL1)
        ms.solve_sizes(reel)
        ms.solve_layout(reel)
        ms.schedule(reel)
        return reel

    @unittest.skipUnless(FONTS_OK, "Inter is not installed — run tools/install_motionstudio_deps.sh")
    def test_the_poster_frame_is_not_the_empty_background(self):
        import numpy as np
        reel = self._reel()
        poster = ms.poster_frame(reel)
        self.assertEqual(poster.size, (ms.W, ms.H))
        a = np.asarray(poster.convert("RGB")).astype(int)
        base = np.asarray(ms.BASE.convert("RGB")).astype(int)
        changed = int((np.abs(a - base).sum(axis=2) > 60).sum())
        self.assertGreater(changed, 20_000, "a settled title card differs from the navy in tens of thousands of pixels")

    @unittest.skipUnless(FONTS_OK, "Inter is not installed — run tools/install_motionstudio_deps.sh")
    def test_frame_zero_of_a_render_is_the_poster_and_the_second_frame_is_the_opening(self):
        """render_reel writes the settled card as f_0000 and the normal (near-empty) opening as f_0001."""
        import numpy as np
        reel = self._reel()
        reel["scenes"] = reel["scenes"][:1]
        reel["scenes"][0]["dur"] = 0.6
        reel["total"] = 0.6
        fd, n = ms.render_reel(reel, "testposter")
        try:
            f0 = np.asarray(Image.open(f"{fd}/f_0000.png").convert("RGB")).astype(int)
            f1 = np.asarray(Image.open(f"{fd}/f_0001.png").convert("RGB")).astype(int)
            poster = np.asarray(ms.poster_frame(reel).convert("RGB")).astype(int)
            self.assertLess(int(np.abs(f0 - poster).max()), 2, "frame 0 is the poster, pixel for pixel")
            self.assertGreater(int(np.abs(f1 - f0).max()), 60, "frame 1 is the real opening (flash + beats arriving), not a held poster")
        finally:
            subprocess.run(["rm", "-rf", fd])

    def test_settle_time_stays_inside_the_scene(self):
        sc = {"dur": 1.0, "beats": [{"kind": "kicker", "t0": 5.0, "text": "x"}]}
        self.assertLessEqual(ms.settle_time(sc), 1.0 - ms.EXIT)
        self.assertGreaterEqual(ms.settle_time(sc), 0.0)

    def test_a_reel_may_opt_out_of_the_poster(self):
        """`poster: False` keeps the old behaviour for an engine caller that wants it."""
        src = (TOOLS / "motionstudio.py").read_text(encoding="utf-8")
        self.assertIn("reel.get('poster', True)", src)

    def test_cover_path_sits_beside_the_master(self):
        self.assertEqual(ms.cover_path_for("/x/y/docoga_short_20261019.mp4"), "/x/y/docoga_short_20261019.cover.jpg")

    def test_the_short_lane_surfaces_the_cover_and_the_shot_count(self):
        bridge = (TOOLS / "shorts_reel.py").read_text(encoding="utf-8")
        self.assertIn('print("SHOTS_HITS=%d/%d"', bridge)
        self.assertIn('print("COVER=%s"', bridge)
        daily = (ROOT / "scripts" / "youtube_short_daily.py").read_text(encoding="utf-8")
        self.assertIn('"cover_path"', daily)


@unittest.skipUnless(PIL_OK, "Pillow/numpy are not installed")
class PhotographVisibilityTests(unittest.TestCase):
    """0.36 read as plain navy on the phone; the treatment must leave a photograph visible."""

    def _photo(self):
        import numpy as np
        rng = np.random.default_rng(3)
        a = rng.integers(40, 230, size=(1200, 900, 3), dtype=np.uint8)
        return Image.fromarray(a, "RGB")

    def test_the_shorts_treatment_is_plainly_brighter_than_the_navy(self):
        import numpy as np
        import brain_visual
        import shorts_reel
        self.assertGreaterEqual(shorts_reel.SHOT_DARKEN, 0.6, "the Shorts keep at least 60 % of the duotone photograph")
        out = brain_visual.treat(self._photo(), (540, 960), darken=shorts_reel.SHOT_DARKEN)
        a = np.asarray(out).astype(int)
        mid = a[int(960 * 0.3):int(960 * 0.7)]      # the band the words sit in, under both scrims
        self.assertGreater(int(mid.max()), 120, "a treated photograph has highlights a phone can see (0.36 capped near 86)")
        self.assertGreater(float(mid.mean()), 35.0, "the band behind the words is not navy any more")

    def test_the_card_default_is_brighter_than_the_october_17_value(self):
        import inspect
        import brain_visual
        self.assertGreaterEqual(inspect.signature(brain_visual.treat).parameters["darken"].default, 0.55)


@unittest.skipUnless(PIL_OK, "Pillow/numpy are not installed")
class ContactSheetTests(unittest.TestCase):
    def test_brightness_tells_navy_from_a_photograph(self):
        import contact_sheet as cs
        navy = Image.new("RGB", (108, 192), (6, 26, 51))
        self.assertLess(cs.brightness(navy), 35)
        photo = Image.new("RGB", (108, 192), (60, 90, 140))
        self.assertGreaterEqual(cs.brightness(photo), 35)

    def test_the_sheet_is_small_and_labelled(self):
        """A real (tiny) video through ffmpeg when one is reachable; otherwise skip."""
        import contact_sheet as cs
        ff = cs.find_ffmpeg()
        if not ff:
            self.skipTest("ffmpeg is not installed here")
        tmp = tempfile.mkdtemp()
        video = Path(tmp) / "v.mp4"
        r = subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x061a33:s=108x192:d=1.2:r=10",
                            "-pix_fmt", "yuv420p", str(video)], capture_output=True)
        if r.returncode != 0 or not video.is_file():
            self.skipTest("this ffmpeg cannot synthesise a test clip")
        out, brights, dur = cs.build(video, Path(tmp) / "sheet.jpg", frames=4, ff=ff)
        self.assertTrue(out.is_file())
        self.assertLess(out.stat().st_size, 400 * 1024)
        self.assertEqual(len(brights), 4)
        self.assertTrue(all(b < 35 for b in brights), brights)


class R(object):
    def __init__(self, status, body):
        self.status_code, self._b = status, body
        self.content = json.dumps(body).encode()

    def json(self):
        return self._b


class OwnerDmTests(unittest.TestCase):
    def setUp(self):
        import owner_dm
        self.od = owner_dm
        self.tmp = tempfile.mkdtemp()
        self.record = Path(self.tmp) / "telegram_owner.json"
        os.environ["OWNER_DM_RECORD"] = str(self.record)

    def tearDown(self):
        os.environ.pop("OWNER_DM_RECORD", None)

    def _updates(self, *msgs):
        return [{"update_id": i, "message": m} for i, m in enumerate(msgs)]

    def test_only_the_handshake_word_from_a_private_chat_is_adopted(self):
        upd = self._updates(
            {"chat": {"id": -100, "type": "channel"}, "text": "owner"},
            {"chat": {"id": 555, "type": "private", "first_name": "Stranger"}, "from": {"first_name": "Stranger"}, "text": "/start"},
            {"chat": {"id": 777, "type": "private", "first_name": "John"}, "from": {"first_name": "John", "username": "john"}, "text": "Owner"},
        )
        rec, note = self.od.discover("T", get=lambda url, params=None, timeout=None: R(200, {"ok": True, "result": upd}))
        self.assertEqual(note, "adopted")
        self.assertEqual(rec["chat_id"], "777")
        self.assertEqual(rec["username"], "john")
        self.assertTrue(self.record.is_file(), "the adoption is recorded for the lanes to commit")
        rec2, note2 = self.od.discover("T", get=lambda *a, **k: self.fail("a known owner is never looked up again"))
        self.assertEqual((rec2["chat_id"], note2), ("777", "known"))

    def test_nobody_yet_is_a_notice_and_exit_zero(self):
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "T"}), \
                mock.patch.object(self.od.requests, "get", lambda url, params=None, timeout=None: R(200, {"ok": True, "result": []})), \
                redirect_stdout(buf):
            code = self.od.main(["tiktok", "--caption", "Sign it unread #DocOga"])
        self.assertEqual(code, 0)
        self.assertIn("OWNER_DM=unknown", buf.getvalue())
        self.assertIn("send the word 'owner'", buf.getvalue())

    def test_the_tiktok_message_is_a_tap_to_copy_block_sent_as_html(self):
        self.record.write_text(json.dumps({"chat_id": "777", "first_name": "John"}))
        calls = []

        def post(url, data=None, timeout=None):
            calls.append((url.rsplit("/", 1)[-1], data))
            return R(200, {"ok": True, "result": {"message_id": 9}})
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "T"}), mock.patch.object(self.od.requests, "post", post), redirect_stdout(buf):
            code = self.od.main(["tiktok", "--caption", "Rent <receipt> #DocOga #Nigeria", "--title", "Rent receipt"])
        self.assertEqual(code, 0)
        self.assertIn("OWNER_DM=sent", buf.getvalue())
        method, data = calls[0]
        self.assertEqual(method, "sendMessage")
        self.assertEqual(data["chat_id"], "777")
        self.assertEqual(data["parse_mode"], "HTML")
        self.assertIn("<code>Rent &lt;receipt&gt; #DocOga #Nigeria</code>", data["text"], "the caption is escaped and copyable")
        self.assertIn("Inbox", data["text"])

    def test_no_token_skips_quietly(self):
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""}), redirect_stdout(buf):
            self.assertEqual(self.od.main(["discover"]), 0)
        self.assertIn("OWNER_DM=skipped", buf.getvalue())


@unittest.skipUnless(PIL_OK, "Pillow is not installed")
class TelegramCoverTests(unittest.TestCase):
    def test_the_cover_rides_as_a_small_jpeg_thumbnail(self):
        import telegram_video as tv
        tmp = tempfile.mkdtemp()
        cover = Path(tmp) / "short.cover.jpg"
        Image.new("RGB", (1080, 1920), (6, 26, 51)).save(cover, quality=92)
        video = Path(tmp) / "short.mp4"
        video.write_bytes(b"\x00" * 2048)
        seen = {}

        def post(url, data=None, files=None, timeout=None):
            seen.update(files or {})
            return R(200, {"ok": True, "result": {"message_id": 1}})
        state, _ = tv.send("T", "@c", str(video), "t", "https://youtube.com/shorts/x", post=post, cover=str(cover))
        self.assertEqual(state, "sent")
        self.assertIn("thumbnail", seen)
        name, data, mime = seen["thumbnail"]
        self.assertEqual(mime, "image/jpeg")
        self.assertLessEqual(len(data), 200 * 1024)
        im = Image.open(io.BytesIO(data))
        self.assertLessEqual(max(im.size), 320)

    def test_no_cover_means_no_thumbnail_field(self):
        import telegram_video as tv
        self.assertIsNone(tv.thumbnail_bytes(""))
        self.assertIsNone(tv.thumbnail_bytes("/nonexistent/cover.jpg"))


class LaneWiringTests(unittest.TestCase):
    """The three corrections are wired into both the test button and the scheduled lane."""

    def _wf(self, name):
        return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_both_tiktok_lanes_text_the_caption_and_picture_the_render(self):
        for name in ("tiktok_test.yml", "youtube_scheduled.yml"):
            src = self._wf(name)
            self.assertIn("tools/owner_dm.py tiktok --caption", src, name)
            self.assertIn("tools/contact_sheet.py --video", src, name)
            self.assertIn("tools/review_push.sh", src, name)
            self.assertIn("SHOTS_HITS=", src, name)
            self.assertIn("logs/telegram_owner.json", src, "%s commits the adopted chat" % name)

    def test_the_scheduled_lane_sets_the_youtube_thumbnail_and_the_telegram_cover(self):
        src = self._wf("youtube_scheduled.yml")
        self.assertIn("tools/yt_thumbnail.py --video-id", src)
        self.assertIn('--cover "$COVER_PATH"', src)
        self.assertIn("steps.short.outputs.cover_path", src)

    def test_review_push_never_fails_the_caller_and_prunes(self):
        sh = (TOOLS / "review_push.sh").read_text(encoding="utf-8")
        self.assertNotIn("set -euo", sh, "the pusher must not take the lane down with it")
        self.assertIn("set -uo pipefail", sh)
        self.assertIn("KEEP_DAYS", sh)
        self.assertIn("exit 0", sh)
        self.assertIn("[skip ci]", sh, "a review commit must not trigger the lanes")


@unittest.skipUnless(PIL_OK, "Pillow/numpy are not installed")
class DesignedCoverTests(unittest.TestCase):
    """tools/short_cover.py — the verdict on yellow slabs, inside the grid-safe band (docs/SHORT_COVER.md)."""

    def _reel(self, day=None):
        import datetime
        import shorts_reel
        day = day or datetime.date(2026, 10, 20)   # "Pay without a receipt. Pay twice."
        reel = shorts_reel.reel_from_topic(shorts_reel.topic_for(day), "/tmp/_cover_test.mp4")
        ms.solve_sizes(reel)
        ms.solve_layout(reel)
        ms.schedule(reel)
        return reel

    def test_the_hero_is_the_consequence_and_the_setup_stays_smaller(self):
        import short_cover
        reel = self._reel()
        kicker, setup, consequence, sub = short_cover.hook_parts(reel)
        self.assertEqual(consequence, "PAY TWICE.")
        self.assertEqual(setup, "PAY WITHOUT A RECEIPT.")
        self.assertTrue(kicker)
        L = short_cover.layout(reel)
        self.assertLessEqual(len(" ".join(L["hero"][1]).split()), 5, "three to five words, huge")
        self.assertGreaterEqual(L["hero"][0], short_cover.HERO_MIN)
        self.assertLessEqual(L["setup"][0], int(L["hero"][0] / 1.35) + 4)

    @unittest.skipUnless(FONTS_OK, "Inter is not installed — run tools/install_motionstudio_deps.sh")
    def test_everything_that_matters_sits_inside_the_grid_safe_band(self):
        """TikTok's grid keeps y 420–1500 of the cover: the yellow slabs and the white set-up must
        be there, and nothing but the photograph outside it."""
        import numpy as np
        import short_cover
        img = short_cover.render(self._reel())
        self.assertEqual(img.size, (ms.W, ms.H))
        a = np.asarray(img).astype(int)
        yellow = (np.abs(a - np.array(ms.YELLOW)).sum(axis=2) < 40)
        ys = np.nonzero(yellow.any(axis=1))[0]
        self.assertGreater(len(ys), 100, "the yellow slabs are there")
        self.assertGreaterEqual(int(ys.min()), 420)
        self.assertLessEqual(int(ys.max()), 1500)
        white = (a.min(axis=2) > 235)
        wy = np.nonzero(white.sum(axis=1) > 20)[0]
        self.assertGreater(len(wy), 50, "the white set-up is there")
        self.assertGreaterEqual(int(wy.min()), 420)
        self.assertLessEqual(int(wy.max()), 1500)
        outside = yellow[:420].sum() + yellow[1500:].sum()
        self.assertEqual(int(outside), 0, "no yellow outside the band — one device, in the crop")

    @unittest.skipUnless(FONTS_OK, "Inter is not installed — run tools/install_motionstudio_deps.sh")
    def test_the_cover_uses_only_brand_colours_and_clears_7_to_1(self):
        import numpy as np
        import short_cover
        img = short_cover.render(self._reel())
        a = np.asarray(img).astype(int)
        # Navy on yellow (the verdict) and white on navy (the set-up): both far above 7:1.
        self.assertGreater(ms.contrast_ratio(ms.YELLOW), 7.0)
        self.assertGreater(ms.contrast_ratio(ms.WHITE), 7.0)
        # Red appears once, as the small rejection badge after the set-up (BRAND §5) — never as
        # text or a block; no green, no off-palette saturated colour anywhere on the piece.
        red = (np.abs(a - np.array(ms.RED)).sum(axis=2) < 40)
        green = (np.abs(a - np.array(ms.GREEN)).sum(axis=2) < 40).sum()
        self.assertEqual(int(green), 0)
        self.assertGreater(int(red.sum()), 500, "the ✗ badge is there")
        self.assertLess(int(red.sum()), int(0.004 * ms.W * ms.H), "…and it is a mark, not a colour field")
        rys = np.nonzero(red.any(axis=1))[0]
        self.assertGreaterEqual(int(rys.min()), 420)
        self.assertLessEqual(int(rys.max()), 1500)

    @unittest.skipUnless(FONTS_OK, "Inter is not installed — run tools/install_motionstudio_deps.sh")
    def test_the_squint_test_at_grid_tile_size(self):
        """Shrunk to a TikTok grid tile (the 1:1 crop at ~200 px), the verdict still dominates:
        the yellow block covers a real share of the tile and its type is tall enough to read."""
        import numpy as np
        import short_cover
        reel = self._reel()
        img = short_cover.render(reel)
        tile = img.crop((0, 420, ms.W, 1500)).resize((200, 200), Image.LANCZOS)
        a = np.asarray(tile).astype(int)
        yellow = (np.abs(a - np.array(ms.YELLOW)).sum(axis=2) < 60).mean()
        self.assertGreater(float(yellow), 0.08, "the slabs are at least 8 %% of the grid tile (%.3f)" % float(yellow))
        hero_px = short_cover.layout(reel)["hero"][0] * 200 / 1080
        self.assertGreaterEqual(hero_px, 20, "verdict cap height ≥ 20 px on a 200 px tile")

    @unittest.skipUnless(FONTS_OK, "Inter is not installed — run tools/install_motionstudio_deps.sh")
    def test_depth_comes_from_the_flat_royal_offset_block_not_a_shadow(self):
        import numpy as np
        import short_cover
        img = short_cover.render(self._reel())
        a = np.asarray(img).astype(int)
        royal = (np.abs(a - np.array(ms.PANEL)).sum(axis=2) < 30)
        self.assertGreater(int(royal.sum()), 5000, "the offset block is there")
        src = (TOOLS / "short_cover.py").read_text(encoding="utf-8")
        for banned in ("GaussianBlur", "ImageFilter", "gradient", "rotate("):
            self.assertNotIn(banned, src, "no soft shadows, gradients or tilt (BRAND_STYLE §1/§4)")

    @unittest.skipUnless(FONTS_OK, "Inter is not installed — run tools/install_motionstudio_deps.sh")
    def test_frame_zero_honours_the_lane_cover(self):
        """motionstudio.poster_frame uses reel['cover_fn'] when the lane provides one."""
        import numpy as np
        import short_cover
        reel = self._reel()
        designed = short_cover.render(reel)
        reel["cover_fn"] = lambda: designed
        poster = ms.poster_frame(reel)
        self.assertLess(int(np.abs(np.asarray(poster).astype(int) - np.asarray(designed).astype(int)).max()), 2)

    def test_a_broken_cover_fn_falls_back_to_the_settled_card(self):
        reel = {"scenes": [{"id": "A", "role": "hook", "dur": 1.0, "trans": "flash", "punch": 0,
                            "beats": [{"kind": "kicker", "t0": 0.02, "text": "X", "size": 30, "y": 500, "color": ms.FAINT,
                                       "exempt": False, "why": "", "lines": None, "role": "kicker"}]}],
                "cover_fn": lambda: (_ for _ in ()).throw(RuntimeError("boom"))}
        if not FONTS_OK:
            self.skipTest("Inter is not installed")
        img = ms.poster_frame(reel)
        self.assertEqual(img.size, (ms.W, ms.H))

    def test_the_bridge_installs_the_designed_cover_and_keeps_the_raw_photo(self):
        src = (TOOLS / "shorts_reel.py").read_text(encoding="utf-8")
        self.assertIn('reel["cover_fn"] = lambda: short_cover.render(reel)', src)
        self.assertIn('sc["_bg_raw"]', src)

    def test_reels_take_frame_zero_as_their_cover(self):
        wf = (ROOT / ".github" / "workflows" / "facebook_autopost.yml").read_text(encoding="utf-8")
        self.assertNotIn("--thumb-offset-ms 1500", wf)
        self.assertIn("--thumb-offset-ms 0", wf)


if __name__ == "__main__":
    unittest.main()
