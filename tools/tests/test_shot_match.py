#!/usr/bin/env python3
"""The photograph behind the words must MATCH the words (owner, 17 Oct 2026).

tools/shot_match.py is the one place every renderer asks "what do I show behind this?", so
the contract is pinned here: the glossary reads the sentence for its THING, every Openverse
result is scored against the query, nothing is fetched unless a lane says DOCOGA_SHOTS=on,
and each renderer (Deep-Dive beat, Short scene, social card) falls back to its old look when
no matching picture exists — a post or a video is never late because of a photo.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

from PIL import Image  # noqa: E402

import shot_match  # noqa: E402
import brain_visual  # noqa: E402


def _jpeg(size=(1600, 1200), color=(120, 90, 60)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def fake_http(results):
    """An Openverse that answers `results` for any search and a JPEG for any image URL."""
    calls = []

    def http(url, accept="application/json"):
        calls.append(url)
        if url.startswith(brain_visual.OPENVERSE):
            return json.dumps({"results": results}).encode(), "application/json"
        return _jpeg(), "image/jpeg"
    http.calls = calls
    return http


class Glossary(unittest.TestCase):
    def test_the_thing_said_beats_the_place_and_the_role(self):
        self.assertEqual(shot_match.subject_for("The landlord must give you a receipt — Lagos Tenancy Law s.5"), "paper receipt")
        self.assertEqual(shot_match.subject_for("Your landlord cannot lock you out without a court order"), "padlocked door")
        self.assertEqual(shot_match.subject_for("Caution fee: ₦50,000 refundable"), "naira banknotes")
        self.assertEqual(shot_match.subject_for("Six months' notice for a yearly tenant"), "wall calendar")
        self.assertEqual(shot_match.subject_for("Send this to a friend in Port Harcourt"), "port harcourt waterfront")
        self.assertEqual(shot_match.subject_for("Rent is due. Where is your agreement?"), "contract signature pen")

    def test_whole_words_only(self):
        self.assertEqual(shot_match.subject_for("It is possible to pay by POS"), "pos terminal card")
        self.assertIsNone(shot_match.subject_for("It is possible."), "'pos' must not fire inside 'possible'")
        self.assertEqual(shot_match.subject_for("Keep your receipts"), "paper receipt")

    def test_no_subject_is_a_person(self):
        import brain
        for _, subject, _ in shot_match.GLOSSARY:
            for word in subject.split():
                self.assertNotIn(word, brain.PLATE_BANNED, subject)
                self.assertNotIn(word, brain_visual.EXCLUDE, subject)

    def test_the_chain_is_hint_then_subject_then_setting_and_never_empty(self):
        self.assertEqual(shot_match.query_chain("Keep your receipt", hint="Handwritten Receipt"),
                         ["handwritten receipt", "paper receipt", "lagos street nigeria"])
        self.assertEqual(shot_match.query_chain("FREE. Two minutes."), ["lagos street nigeria"])
        self.assertEqual(shot_match.query_chain("x", hint="one two three four five six"), ["lagos street nigeria"],
                         "an over-long hint is not a query")


class Relevance(unittest.TestCase):
    def test_a_result_must_share_a_word_with_the_query(self):
        self.assertTrue(shot_match.relevant({"title": "Old paper receipts on a desk", "tags_text": ""}, "paper receipt"))
        self.assertTrue(shot_match.relevant({"title": "IMG_2041", "tags_text": "receipt paper"}, "paper receipt"))
        self.assertFalse(shot_match.relevant({"title": "IMG_2041", "tags_text": "sunset beach"}, "paper receipt"))
        self.assertFalse(shot_match.relevant({"title": "", "tags_text": ""}, "paper receipt"))

    def test_pick_skips_the_pretty_but_wrong_result(self):
        results = [{"id": "a", "url": "https://x/a.jpg", "title": "Golden sunset", "width": 2000, "height": 1500,
                    "tags": [{"name": "sky"}]},
                   {"id": "b", "url": "https://x/b.jpg", "title": "Receipt book", "width": 2000, "height": 1500,
                    "tags": [{"name": "paper"}]}]
        with mock.patch.dict(os.environ, {"BRAIN_PLATES": "on"}):
            cand, note = shot_match.pick("paper receipt", http=fake_http(results), sleeper=lambda: None)
        self.assertEqual(cand["id"], "b", note)

    def test_pick_returns_none_when_nothing_matches(self):
        results = [{"id": "a", "url": "https://x/a.jpg", "title": "Golden sunset", "width": 2000, "height": 1500}]
        with mock.patch.dict(os.environ, {"BRAIN_PLATES": "on"}):
            cand, note = shot_match.pick("paper receipt", http=fake_http(results), sleeper=lambda: None)
        self.assertIsNone(cand)
        self.assertIn("no relevant result", note)


class Fetching(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_nothing_is_fetched_unless_a_lane_says_so(self):
        http = fake_http([])
        with mock.patch.dict(os.environ, {"BRAIN_PLATES": "on"}, clear=False):
            os.environ.pop("DOCOGA_SHOTS", None)
            self.assertFalse(shot_match.enabled())
            img, note = shot_match.photo_for("Keep your receipt", http=http)
        self.assertIsNone(img)
        self.assertEqual(note, "shots off")
        self.assertEqual(http.calls, [], "tests, qa.py and laptops never reach Openverse by accident")

    def test_the_chain_walks_to_the_setting_and_the_picture_is_treated_and_cached(self):
        results = [{"id": "s", "url": "https://x/s.jpg", "title": "Lagos street market", "width": 2000, "height": 1500,
                    "tags": [{"name": "nigeria"}]}]
        http = fake_http(results)
        with mock.patch.dict(os.environ, {"BRAIN_PLATES": "on", "DOCOGA_SHOTS": "on", "STOCK_MEDIA": "off", "BRAIN_PLATE_CACHE": self.tmp}):
            img, prov = shot_match.photo_for("Keep your receipt", size=(1080, 1350), http=http, sleeper=lambda: None)
            self.assertIsNotNone(img)
            self.assertEqual(img.size, (1080, 1350))
            self.assertEqual(prov["query"], "lagos street nigeria", "'paper receipt' found nothing relevant → the setting")
            searches = [u for u in http.calls if u.startswith(brain_visual.OPENVERSE)]
            self.assertEqual(len(searches), 2)
            downloads = [u for u in http.calls if u == "https://x/s.jpg"]
            self.assertEqual(downloads, ["https://x/s.jpg"])
            # second ask, same picture: served from the cache, no download
            shot_match.photo_for("Walk the street", size=(1080, 1350), http=http, sleeper=lambda: None)
            self.assertEqual([u for u in http.calls if u == "https://x/s.jpg"], ["https://x/s.jpg"])
        self.assertTrue(any(p.suffix == ".json" for p in Path(self.tmp).iterdir()), "provenance (licence, creator) is kept")

    def test_openverse_empty_falls_to_the_stock_doors_photographs_only_and_no_people(self):
        """1 Nov 2026: the text-only card was the post Instagram showed to nobody. When Openverse has
        nothing, the card asks the keyed stock doors (photo kind only) and still refuses people."""
        class FakeHTTP:   # the stock doors' (url, headers, accept, max_bytes) shape
            def __init__(self, routes):
                self.routes, self.calls = routes, []

            def __call__(self, url, headers=None, accept="application/json", max_bytes=0):
                self.calls.append((url, dict(headers or {})))
                for prefix, body in self.routes.items():
                    if url.startswith(prefix):
                        return (json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body), "application/json"
                raise OSError("no route for " + url)
        stock_jpeg = _jpeg
        pixabay = {"hits": [
            {"id": 7, "pageURL": "https://pixabay.com/photos/woman-receipt-7/", "tags": "woman, receipt, shop",
             "largeImageURL": "https://cdn.pixabay.com/p/7.jpg", "imageWidth": 1280, "imageHeight": 1920, "user": "a"},
            {"id": 201, "pageURL": "https://pixabay.com/photos/paper-receipt-201/", "tags": "paper, receipt, bill",
             "largeImageURL": "https://cdn.pixabay.com/p/201.jpg", "imageWidth": 1280, "imageHeight": 1920, "user": "a"}]}
        stock = FakeHTTP({"https://pixabay.com/api/": pixabay, "https://cdn.pixabay.com/": stock_jpeg()})
        openverse = fake_http([])
        with mock.patch.dict(os.environ, {"BRAIN_PLATES": "on", "DOCOGA_SHOTS": "on", "STOCK_MEDIA": "on", "BRAIN_PLATE_CACHE": self.tmp,
                                          "STOCK_MEDIA_CACHE": self.tmp, "PIXABAY_API_KEY": "pk", "PEXELS_API_KEY": "", "FLICKR_API_KEY": "",
                                          "UNSPLASH_ACCESS_KEY": ""}):
            import footage_ledger
            import stock_media
            stock_media._CACHE.clear()
            with mock.patch.object(footage_ledger, "LEDGER", Path(self.tmp) / "ledger.json"):
                img, prov = shot_match.photo_for("Keep your receipt", size=(1080, 1350), http=openverse, sleeper=lambda *a: None, stock_http=stock)
        self.assertIsNotNone(img, prov)
        self.assertEqual(img.size, (1080, 1350))
        self.assertEqual((prov["door"], prov["id"]), ("pixabay", "pixabay:201"), "the picture with a woman in it is passed over")
        self.assertTrue(all("/videos/" not in u for u, _ in stock.calls), "a card never asks for a clip")
        with mock.patch.dict(os.environ, {"BRAIN_PLATES": "on", "DOCOGA_SHOTS": "on", "STOCK_MEDIA": "off", "BRAIN_PLATE_CACHE": self.tmp}):
            img, note = shot_match.photo_for("Keep your receipt", size=(1080, 1350), http=openverse, sleeper=lambda *a: None, stock_http=stock)
        self.assertIsNone(img)
        self.assertEqual(note, "nothing matched", "STOCK_MEDIA=off keeps the old behaviour exactly")

    def test_errors_never_escape(self):
        def http(url, accept=None):
            raise RuntimeError("boom")
        with mock.patch.dict(os.environ, {"BRAIN_PLATES": "on", "DOCOGA_SHOTS": "on", "STOCK_MEDIA": "off", "BRAIN_PLATE_CACHE": self.tmp}):
            img, note = shot_match.photo_for("Keep your receipt", http=http, sleeper=lambda: None)
        self.assertIsNone(img)


class DeepDiveBeats(unittest.TestCase):
    def test_a_beat_gets_the_matching_photo_else_its_named_plate(self):
        import deepdive
        beat = {"head": "KEEP THE RECEIPT", "sub": "Section 5 says so", "img": "pen", "shot": None}
        fake = Image.new("RGB", (1600, 1200), (90, 120, 150))
        with mock.patch.dict(os.environ, {"DOCOGA_SHOTS": "on", "STOCK_MEDIA": "off"}), \
             mock.patch.object(shot_match, "photo_for", return_value=(fake, {"query": "paper receipt", "license": "cc0"})) as pf:
            im = deepdive.plate_for_beat(beat)
            self.assertEqual(im.size, (2400, 1350))
            self.assertEqual(pf.call_args.kwargs.get("hint"), None)
            self.assertIn("RECEIPT", pf.call_args.args[0])
            self.assertIs(deepdive.plate_for_beat(beat), im, "cached per beat — a 30 fps scene asks once")
        beat2 = {"head": "KEEP THE RECEIPT", "sub": "", "img": "pen", "shot": "handwritten receipt"}
        with mock.patch.dict(os.environ, {"DOCOGA_SHOTS": "on", "STOCK_MEDIA": "off"}), \
             mock.patch.object(shot_match, "photo_for", return_value=(None, "nothing matched")) as pf, \
             mock.patch.object(deepdive, "plate", return_value="PLATE") as named:
            self.assertEqual(deepdive.plate_for_beat(beat2), "PLATE")
            self.assertEqual(pf.call_args.kwargs.get("hint"), "handwritten receipt", "the brain's shot is the first query")
            named.assert_called_once_with("pen")

    def test_shots_off_means_the_fixed_plates_without_a_lookup(self):
        import deepdive
        beat = {"head": "KEEP THE RECEIPT", "sub": "", "img": "pen"}
        with mock.patch.dict(os.environ, {}, clear=False), \
             mock.patch.object(shot_match, "photo_for") as pf, \
             mock.patch.object(deepdive, "plate", return_value="PLATE"):
            os.environ.pop("DOCOGA_SHOTS", None)
            self.assertEqual(deepdive.plate_for_beat(beat), "PLATE")
            pf.assert_not_called()

    def test_the_brain_validates_and_keeps_the_shot(self):
        src = (ROOT / "tools/brain.py").read_text(encoding="utf-8")
        self.assertIn('"shot": "2-4 plain words naming the photograph that shows what this beat SAYS', src)
        self.assertIn('"shot": (str(b.get("shot") or "").strip().lower() or None)', src, "episode.json carries the shot")
        self.assertIn("shot is 2-4 plain words, no people, no signs", src)


class ShortScenes(unittest.TestCase):
    def test_each_hook_and_tip_scene_is_asked_for_in_the_narrators_words(self):
        import shorts_reel
        topic = shorts_reel.topic_for(__import__("datetime").date(2026, 10, 20))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/x.mp4")
        shots = shorts_reel.shots_for(reel, topic)
        roles = [sc["role"] for sc, _, _ in shots]
        self.assertEqual(roles, ["hook", "tip", "tip", "tip", "tip"], "the conclusion stays on the brand navy")
        for sc, said, chain in shots:
            self.assertTrue(said.strip())
            self.assertEqual(chain[-1], "lagos street nigeria")

    def test_attach_puts_a_treated_frame_behind_the_scene_or_leaves_the_navy(self):
        import shorts_reel
        import motionstudio as ms
        topic = shorts_reel.topic_for(__import__("datetime").date(2026, 10, 20))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/x.mp4")
        frame = Image.new("RGB", (ms.W, ms.H), (20, 30, 40))
        answers = iter([(frame, {"query": "paper receipt", "license": "cc0"}), (None, "nothing matched")] + [(frame, {"query": "x"})] * 9)
        with mock.patch.dict(os.environ, {"DOCOGA_SHOTS": "on", "STOCK_MEDIA": "off"}), \
             mock.patch.object(shot_match, "photo_for", side_effect=lambda *a, **k: next(answers)):
            hits = shorts_reel.attach_shots(reel, topic)
        self.assertEqual(hits, 4)
        self.assertIs(ms.scene_bg(reel["scenes"][0]), frame)
        self.assertIs(ms.scene_bg(reel["scenes"][1]), ms.BASE, "no match → the navy, not a wrong picture")
        self.assertIs(ms.scene_bg(reel["scenes"][-1]), ms.BASE, "the conclusion is never photographed")
        self.assertEqual(reel["scenes"][0]["shot"], shot_match.query_chain(shorts_reel.shots_for(reel, topic)[0][1])[0])

    def test_shots_off_attaches_nothing(self):
        import shorts_reel
        topic = shorts_reel.topic_for(__import__("datetime").date(2026, 10, 20))
        reel = shorts_reel.reel_from_topic(topic, "/tmp/x.mp4")
        with mock.patch.dict(os.environ, {}, clear=False), mock.patch.object(shot_match, "photo_for") as pf:
            os.environ.pop("DOCOGA_SHOTS", None)
            self.assertEqual(shorts_reel.attach_shots(reel, topic), 0)
            pf.assert_not_called()

    def test_motionstudio_qa_measures_content_against_the_scenes_own_background(self):
        """A photograph behind the words is not 'content outside the safe zone': the settle-frame
        mask subtracts the scene's background, and render and QA share one zoom definition."""
        import motionstudio as ms
        src = (ROOT / "tools/motionstudio.py").read_text(encoding="utf-8")
        self.assertIn("mask = np.abs(arr - bg_arr).sum(axis=2) > 60", src)
        self.assertNotIn("mask = np.abs(arr - NAVY).sum(axis=2) > 60", src)
        # v5: render and QA share camera_bg (the shot on its camera path + the scene zoom)
        self.assertIn("bg = BASE if flat else camera_bg(sc, lt, last)", src)   # v6: QA's second look lays the type on the plain navy
        self.assertIn("bg_arr = np.asarray(camera_bg(sc, idx / FPS - off, si == len(scenes) - 1)", src)
        sc = {"punch": 0.05, "dur": 3.2}
        self.assertEqual(ms.scale_at(sc, 1.0, False), (1.0, 0.0))
        s, fade = ms.scale_at(sc, 3.2 - 0.01, False)
        self.assertGreater(s, 1.0)
        self.assertGreater(fade, 0.9)
        self.assertIs(ms.scene_bg({"_bg": Image.new("RGB", (10, 10))}), ms.BASE, "a wrong-sized picture is refused")


class Cards(unittest.TestCase):
    def test_a_rotation_card_asks_for_a_photo_matching_its_copy(self):
        import social_card
        with mock.patch.object(shot_match, "photo_for", return_value=(None, "shots off")) as pf:
            kicker, background, layout, big = social_card._brief({}, "tip", (1080, 1350), said="Keep every rent receipt.")
        self.assertIsNone(background)
        self.assertEqual(pf.call_args.args[0], "Keep every rent receipt.")
        self.assertIsNone(pf.call_args.kwargs.get("hint"))

    def test_the_brains_plate_is_the_hint_and_the_copy_is_the_judge(self):
        import social_card
        with mock.patch.object(shot_match, "photo_for", return_value=(None, "x")) as pf:
            social_card._brief({"plate": "lagos rooftops dusk"}, "tip", (1080, 1350), said="Keep every rent receipt.")
        self.assertEqual(pf.call_args.args[0], "Keep every rent receipt.")
        self.assertEqual(pf.call_args.kwargs.get("hint"), "lagos rooftops dusk")

    def test_every_publishing_lane_turns_shots_on_and_the_test_lane_does_not(self):
        for name in ("deepdive", "facebook_autopost", "facebook_story_afternoon", "instagram_autopost",
                     "telegram_autopost", "threads_autopost", "youtube_scheduled"):
            text = (ROOT / ".github/workflows" / ("%s.yml" % name)).read_text(encoding="utf-8")
            self.assertIn("DOCOGA_SHOTS: ${{ vars.DOCOGA_SHOTS || 'on' }}", text, name)
        self.assertNotIn("DOCOGA_SHOTS", (ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
