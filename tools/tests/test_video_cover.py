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


if __name__ == "__main__":
    unittest.main()
