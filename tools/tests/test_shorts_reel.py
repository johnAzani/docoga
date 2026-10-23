"""The Shorts/Reels bridge: rotation words → MotionStudio reel spec.

Owner direction, 14 Oct 2026: "check my brand style and quality … are you using
my exact motion studio tool?" / "I want my quality shorts back". These tests pin
the answer to *yes* — every publish lane renders through `tools/shorts_reel.py`
→ `tools/motionstudio.py`, the spec uses only the engine's palette and grammar,
and the retired static-card renderer is unreachable from any lane.

No frame is rendered here: the spec is solved (sizes, layout, schedule), which
takes milliseconds and exercises everything but the pixels.
"""

import re
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT = TOOLS_DIR.parent
for _p in (TOOLS_DIR, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    import shorts_reel  # noqa: E402
    import motionstudio as ms  # noqa: E402
    import generate_short_video as words  # noqa: E402
    BRIDGE_OK = True
except ImportError as exc:  # pragma: no cover — PIL/numpy absent on this machine
    BRIDGE_OK = False
    BRIDGE_ERR = str(exc)

FONTS_OK = BRIDGE_OK and ms.find_font_template() is not None

PALETTE = None
if BRIDGE_OK:
    PALETTE = {ms.NAVY, ms.NAVY2, ms.PANEL, ms.WHITE, ms.MUTED, ms.FAINT,
               ms.BLUE, ms.YELLOW, ms.RED, ms.GREEN}

# The grammar the bridge is allowed to speak. `icons` and `cycler` need PNGs that
# are not in the repo; `odometer` with `strike` is for an external price only.
ALLOWED_KINDS = {"kicker", "cascade", "support", "badge", "wordpop", "button"}

PUBLISH_LANES = (
    ROOT / "scripts" / "youtube_short_daily.py",
    ROOT / "scripts" / "facebook_reel_daily.py",
    ROOT / "scripts" / "post_telegram_video.py",
)


def _solved(topic):
    reel = shorts_reel.reel_from_topic(topic, "/tmp/_t.mp4")
    ms.solve_sizes(reel)
    ms.solve_layout(reel)
    ms.schedule(reel)
    return reel


@unittest.skipUnless(BRIDGE_OK, "MotionStudio bridge not importable (PIL/numpy)")
class ReelSpecTests(unittest.TestCase):
    def setUp(self):
        if not FONTS_OK:
            self.skipTest("Inter is not installed — run tools/install_motionstudio_deps.sh")

    def test_every_topic_builds_a_spec_the_engine_accepts(self):
        for topic in words.VIDEO_SCRIPTS:
            with self.subTest(title=topic["title"]):
                reel = _solved(topic)
                self.assertEqual(reel["scenes"][0]["role"], "hook")
                self.assertEqual(reel["scenes"][-1]["role"], "conclusion")
                self.assertEqual([sc["role"] for sc in reel["scenes"][1:-1]], ["tip"] * 4)
                self.assertGreater(reel["total"], 15)
                self.assertLessEqual(reel["total"], shorts_reel.SHORTS_CAP + 1.0)

    def test_the_spec_speaks_only_the_engine_palette(self):
        for topic in words.VIDEO_SCRIPTS:
            reel = shorts_reel.reel_from_topic(topic, "/tmp/_t.mp4")
            for sc in reel["scenes"]:
                for b in sc["beats"]:
                    for key in ("color", "underline"):
                        if b.get(key):
                            with self.subTest(title=topic["title"], beat=b["kind"], key=key):
                                self.assertIn(tuple(b[key]), PALETTE)

    def test_the_spec_uses_only_asset_free_grammar(self):
        for topic in words.VIDEO_SCRIPTS:
            reel = shorts_reel.reel_from_topic(topic, "/tmp/_t.mp4")
            kinds = {b["kind"] for sc in reel["scenes"] for b in sc["beats"]}
            with self.subTest(title=topic["title"]):
                self.assertTrue(kinds <= ALLOWED_KINDS, kinds - ALLOWED_KINDS)
                self.assertFalse(any(b.get("strike") for sc in reel["scenes"] for b in sc["beats"]))

    def test_display_text_stays_display_sized_and_inside_the_safe_area(self):
        """A four-word cascade must wrap, not shrink to body size (BRAND_STYLE §2:
        display 96–190). Every text beat ends inside the 920 px safe width."""
        for topic in words.VIDEO_SCRIPTS:
            reel = _solved(topic)
            for sc in reel["scenes"]:
                for b in sc["beats"]:
                    if b["kind"] == "cascade":
                        with self.subTest(title=topic["title"], text=b["text"]):
                            self.assertGreaterEqual(b["size"], 88)
                            for line in (b["lines"] or [b["text"]]):
                                self.assertLessEqual(ms.tw(line, "Black", b["size"]), ms.SAFE_W)
                    if b["kind"] in ("cascade", "support", "kicker", "wordpop"):
                        y0, y1 = ms.beat_box(b)
                        self.assertGreaterEqual(y0, ms.SAFE["top"])
                        self.assertLessEqual(y1, ms.SAFE["bottom"])

    def test_the_conclusion_carries_cta_and_disclaimer(self):
        reel = shorts_reel.reel_from_topic(words.VIDEO_SCRIPTS[0], "/tmp/_t.mp4")
        last = reel["scenes"][-1]
        texts = [b["text"] for b in last["beats"]]
        self.assertIn("docoga.com.ng", texts)
        self.assertIn("FREE.", texts)
        self.assertTrue(any("GENERAL INFO" in t and "VARY" in t for t in texts),
                        "the disclaimer kicker must survive every topic")
        self.assertEqual(last["trans"], "dissolve")

    def test_the_bridge_refuses_a_topic_without_the_disclaimer(self):
        bad = dict(words.VIDEO_SCRIPTS[0])
        bad["slides"] = bad["slides"][:-1]
        with self.assertRaises(ValueError):
            shorts_reel.reel_from_topic(bad, "/tmp/_t.mp4")

    def test_the_output_path_is_absolute_so_the_engine_cannot_redirect_it(self):
        reel = shorts_reel.reel_from_topic(words.VIDEO_SCRIPTS[0], "assets/videos/x.mp4")
        self.assertTrue(Path(reel["out"]).is_absolute())

    def test_topic_for_is_the_shared_rotation(self):
        day = date(2026, 10, 16)
        self.assertEqual(shorts_reel.topic_for(day), words.script_for_date(day))
        titles = {shorts_reel.topic_for(day + timedelta(days=i))["title"]
                  for i in range(len(words.VIDEO_SCRIPTS))}
        self.assertEqual(titles, {t["title"] for t in words.VIDEO_SCRIPTS})


class BrandGateTests(unittest.TestCase):
    """Source-level: no colour or font literal in the bridge, and no publish lane
    can reach the retired renderer. These need no PIL, so they always run."""

    def test_the_bridge_has_no_colour_or_font_literals(self):
        src = (TOOLS_DIR / "shorts_reel.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{6}\b", src.split('"""', 2)[2]),
                          "hex colours belong in motionstudio.py, not the bridge")
        self.assertIsNone(re.search(r"\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)", src),
                          "RGB tuples belong in motionstudio.py, not the bridge")
        self.assertNotIn("DejaVu", src)
        self.assertNotIn("truetype(", src)

    def test_no_publish_lane_reaches_the_retired_card_renderer(self):
        for lane in PUBLISH_LANES:
            src = lane.read_text(encoding="utf-8")
            with self.subTest(lane=lane.name):
                self.assertIn("shorts_reel", src)
                self.assertNotIn("generate_video(", src)
                self.assertNotIn("create_slide_image", src)

    def test_the_engine_resolves_fonts_and_ffmpeg_instead_of_hardcoding(self):
        src = (TOOLS_DIR / "motionstudio.py").read_text(encoding="utf-8")
        self.assertIn("MOTIONSTUDIO_FONT_DIR", src)
        self.assertIn("def find_ffmpeg", src)
        self.assertIn("def check_environment", src)
        self.assertIn("'--check'", src)

    def test_the_workflows_install_inter_through_the_shared_script(self):
        for wf in ("youtube_scheduled.yml", "facebook_autopost.yml"):
            src = (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")
            with self.subTest(workflow=wf):
                self.assertIn("tools/install_motionstudio_deps.sh", src)
                self.assertNotIn("fonts-dejavu-core", src)
        script = (TOOLS_DIR / "install_motionstudio_deps.sh").read_text(encoding="utf-8")
        self.assertIn("fonts-inter", script)
        self.assertIn("motionstudio.py\" --check", script)


if __name__ == "__main__":
    unittest.main()


class SearchKickerTests(unittest.TestCase):
    """23 Oct 2026: the opening masthead is a search phrase — TikTok and YouTube read burned-in
    text in the first three seconds, and the cover is the frame they index."""

    def test_the_masthead_is_the_days_search_phrase_plus_the_episode_number(self):
        import shorts_reel
        ledger = ROOT / "logs" / "youtube_published.json"
        text = shorts_reel.search_kicker(env={}, day=date(2026, 10, 23), ledger=ledger)
        self.assertRegex(text, r"^[A-Z ]+ · No\. \d+$", text)
        self.assertNotIn("DOCOGA", text, "the brand lives in the CTA chip; the masthead is for search")
        self.assertTrue("NIGERIA" in text or "LAGOS" in text, text)
        seen = {shorts_reel.search_kicker(env={}, day=date(2026, 10, 23) + timedelta(days=i), ledger="/nonexistent").split(" · ")[0] for i in range(7)}
        self.assertGreaterEqual(len(seen), 5, "a week of covers does not repeat one phrase")
        for phrase in seen:
            self.assertLessEqual(len(phrase), 26, phrase)
        self.assertEqual(shorts_reel.search_kicker(env={"SHORTS_SEARCH_KICKER": "off"}, ledger="/nonexistent"), shorts_reel.SERIES_KICKER)
        self.assertEqual(shorts_reel.search_kicker(env={"SHORTS_SEARCH_KICKER": "Lagos rent law"}, ledger="/nonexistent"), "LAGOS RENT LAW")
        self.assertEqual(shorts_reel.kicker_size("RENT IN NIGERIA · No. 9"), 30)
        self.assertEqual(shorts_reel.kicker_size("TENANCY AGREEMENT NIGERIA · No. 12"), 26)

    def test_the_hook_scene_opens_with_it_and_the_caption_leads_with_the_same_phrase(self):
        import shorts_reel
        import reel_caption
        sys.path.insert(0, str(ROOT / "scripts"))
        import generate_short_video as g
        import os
        os.environ["STOCK_MEDIA"] = "off"
        os.environ["SHORTS_SEARCH_KICKER"] = ""
        try:
            reel = shorts_reel.reel_from_topic(g.VIDEO_SCRIPTS[0], "/tmp/search_kicker_test.mp4")
        finally:
            os.environ.pop("SHORTS_SEARCH_KICKER", None)
        hook = reel["scenes"][0]
        kicker = next(b for b in hook["beats"] if b["kind"] == "kicker")
        self.assertRegex(kicker["text"], r"^[A-Z ]+ · No\. \d+$")
        phrase = kicker["text"].split(" · ")[0]
        from datetime import datetime, timezone
        today = datetime.now(timezone(timedelta(hours=1))).date()
        self.assertEqual(phrase, re.sub(r"\s*\(.*?\)", "", reel_caption.tiktok_keyword(today, reel_caption.pack_for(today))).upper(),
                         "screen and TikTok caption agree on the phrase")
        src = (ROOT / "tools" / "shorts_reel.py").read_text(encoding="utf-8")
        self.assertIn("masthead = search_kicker()", src)
        cover = (ROOT / "tools" / "short_cover.py").read_text(encoding="utf-8")
        self.assertIn("len(kicker) <= 30", cover, "a long search phrase steps the cover masthead down, never clips")
