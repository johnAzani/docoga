"""Seventh research round (17 Oct 2026) — the Gemini ladder, listening, guides, captions,
collaborators, and the approve() fields that were linted but never saved.

Run: GEMINI_QUOTA_LEDGER=/tmp/q.json python3 -m unittest tools.tests.test_round7 -v
"""
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "tests"))

import brain  # noqa: E402
import brain_drafts  # noqa: E402
import brain_replies  # noqa: E402
import deepdive  # noqa: E402
import gemini_text  # noqa: E402
import guides_build  # noqa: E402
import ig_publish  # noqa: E402
import law_index  # noqa: E402
import listening  # noqa: E402
import og_images  # noqa: E402
import yt_captions  # noqa: E402
from test_brain import MONDAY, Sandbox, good_pack  # noqa: E402

WF = ROOT / ".github" / "workflows"


# ───────────────────────────── the Gemini ladder ─────────────────────────────
class LadderTests(unittest.TestCase):
    def test_the_ladder_starts_on_what_google_serves_new_projects_and_keeps_the_lite_buckets(self):
        chain = gemini_text.DEFAULT_MODELS
        self.assertEqual(chain[0], "gemini-3.8-flash")
        for rung in ("gemini-2.5-pro", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-3.1-flash-lite"):
            self.assertIn(rung, chain)
        self.assertNotIn("gemini-2.0-flash", chain, "retired — a dead rung wastes a night")
        self.assertEqual(brain_replies.MODELS[0], "gemini-3.5-flash-lite", "replies talk often: the 500/day rung first")
        self.assertTrue(all(m in gemini_text.LITE_FIRST_MODELS for m in ("gemini-3.8-flash", "gemini-2.5-flash-lite")))

    def test_a_403_without_a_quota_word_is_not_served_and_the_chain_steps_down(self):
        seen = []

        def http(url, payload, key):
            seen.append(url)
            if "gemini-2.5-flash:" in url:
                return 403, json.dumps({"error": {"code": 403, "status": "PERMISSION_DENIED",
                                                  "message": "This model is not available for this project."}})
            return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]})

        with patch.dict(os.environ, {"GEMINI_QUOTA_LEDGER": os.environ.get("GEMINI_QUOTA_LEDGER", "/tmp/q.json")}):
            out = gemini_text.generate_json("hi", models_chain=("gemini-2.5-flash", "gemini-3.5-flash-lite"), http=http,
                                            sleep=lambda s: None, log=lambda *a: None)
        self.assertEqual(out, {"ok": True})
        self.assertEqual(len(seen), 2)

    def test_probe_names_the_rungs_the_key_is_served_and_the_verdict(self):
        body = {"models": [{"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]},
                           {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                           {"name": "models/gemini-embedding-2", "supportedGenerationMethods": ["embedContent"]}]}
        lines = []
        served, missing = gemini_text.probe(chain=("gemini-3.8-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"),
                                            http_get=lambda url, key: (200, json.dumps(body)), key="k", log=lines.append)
        self.assertEqual(served, ["gemini-3.8-flash", "gemini-3.5-flash-lite"])
        self.assertEqual(missing, ["gemini-2.5-flash"])
        self.assertIn("GEMINI_SERVED=gemini-3.8-flash,gemini-3.5-flash-lite", lines)
        self.assertIn("GEMINI_LADDER=ok", lines)
        lines.clear()
        served, _ = gemini_text.probe(chain=("gemini-2.5-flash",), http_get=lambda u, k: (200, json.dumps(body)), key="k",
                                      log=lines.append)
        self.assertEqual(served, [])
        self.assertIn("GEMINI_LADDER=empty", lines)

    def test_the_narrator_has_a_free_tier_fallback_rung(self):
        self.assertEqual(deepdive.GEMINI_MODELS[0], "gemini-2.5-flash-preview-tts", "the lock's rung stays first")
        self.assertIn("gemini-3.8-flash-lite-tts", deepdive.GEMINI_MODELS)


# ───────────────────────────── approve() keeps what the lanes read ─────────────────────────────
class ApproveKeepsTheFieldsTests(Sandbox):
    def test_tool_reader_cta_quiz_and_news_hook_survive_into_the_saved_pack(self):
        quiz = {"question": "How many months for a yearly tenant?", "options": ["Three", "Six"], "correct": 1,
                "explanation": "Six — s.13(1)(e).", "fact_id": good_pack()["claims"][0]["fact_id"]}
        approved = brain.approve(good_pack(quiz=quiz, news_hook="Lagos rent up 20% — Punch"), self.ctx())
        self.assertEqual(approved["tool"], "notice-to-quit")
        self.assertEqual(approved["reader"], "ngozi")
        self.assertEqual(approved["post"]["cta"], "Send this to the friend whose rent is due in January.")
        self.assertEqual(approved["quiz"]["question"], quiz["question"])
        self.assertEqual(approved["news_hook"], "Lagos rent up 20% — Punch")
        self.assertTrue(brain_drafts.link_for(approved).endswith("/notice-to-quit-lagos"),
                        "the deep link needs `tool` on the saved pack — it used to fall to the homepage")
        self.assertIn("Send this to the friend", brain_drafts.post_text(approved))

    def test_the_prompt_carries_what_nigerians_asked(self):
        listening.OUT.write_text(json.dumps({"pulled_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                             "items": [{"title": "Landlord Increased My Rent By 100%, Is This Legal?",
                                                        "url": "https://www.nairaland.com/1/x", "board": "properties", "score": 9}]}))
        prompt = brain.prompt_for(brain.context(MONDAY, []) if hasattr(brain, "context") else self.ctx())
        self.assertIn("WHAT NIGERIANS ASKED THIS WEEK", prompt)


# ───────────────────────────── listening ─────────────────────────────
NAIRALAND = """<td class="w pd10"><b><a href="/8763042/renting-managing-property-lagos">Renting And Managing Property In Lagos</a></b>
<a href="/8790001/my-landlord-wants-throw-me">My Landlord Wants To Throw Me Out After 3 Months, What Are My Rights?</a>
<a href="/8790002/4-bedroom-duplex-sale-lekki">4 Bedroom Duplex For Sale In Lekki Phase 1 (₦250 Million)</a>
<a href="/8790003/landlord-increased-rent-100">Landlord Increased My Rent By 100%, Is This Legal? Please Advise</a>
<a href="/8790003/landlord-increased-rent-100/2#1234">2</a>
<a href="/8790004/no-receipt">Paid Rent Without Receipt, Agent Now Denying &amp; Help</a>"""


class ListeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for target, name, value in ((listening, "OUT", root / "listening.json"), (listening, "ANSWERS", root / "answers")):
            p = patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_questions_rise_adverts_sink_and_duplicates_collapse(self):
        items = listening.parse_nairaland(NAIRALAND, "properties")
        self.assertEqual(len(items), 5)
        chosen = listening.select(items)
        titles = [c["title"] for c in chosen]
        self.assertEqual(titles[0], "Landlord Increased My Rent By 100%, Is This Legal? Please Advise")
        self.assertNotIn("4 Bedroom Duplex For Sale In Lekki Phase 1 (₦250 Million)", titles)
        self.assertNotIn("Renting And Managing Property In Lagos", titles, "a firm's headline, not a person's question")
        self.assertIn("Paid Rent Without Receipt, Agent Now Denying & Help", titles)

    def test_pull_survives_a_dead_source_and_writes_what_it_heard(self):
        def http(url):
            if "reddit" in url:
                raise OSError("blocked")
            if "properties" in url:
                return 200, NAIRALAND.encode()
            return 503, b""
        log = []
        data = listening.pull(http=http, log=log.append)
        self.assertEqual(len(data["items"]), 3)
        self.assertTrue(any("r/Nigeria — blocked" in line for line in log))
        self.assertEqual(listening.prompt_block(data["items"]).count("\n"), 2)

    def test_reddit_json_parses_and_comment_count_lifts(self):
        raw = json.dumps({"data": {"children": [{"data": {"title": "My landlord locked my door over rent, what can I do?",
                                                           "permalink": "/r/Nigeria/comments/abc/x/", "created_utc": 1760000000,
                                                           "num_comments": 40}}]}}).encode()
        items = listening.parse_reddit(raw, "r/Nigeria")
        self.assertEqual(items[0]["url"], "https://www.reddit.com/r/Nigeria/comments/abc/x/")
        self.assertGreaterEqual(listening.score(items[0]), 9)

    def test_the_answer_is_gated_like_a_post_and_then_written_once(self):
        facts = law_index.facts_for("lagos")
        fact = next(f for f in facts if "Yearly tenant" in f["text"])
        now = dt.datetime(2026, 10, 19, 1, 30, tzinfo=dt.timezone.utc)
        listening.OUT.parent.mkdir(parents=True, exist_ok=True)
        listening.OUT.write_text(json.dumps({"pulled_at": now.isoformat(), "items": [
            {"title": "Lagos landlord gave me one month notice after a year, is it legal?", "url": "https://www.nairaland.com/9/x",
             "board": "properties", "score": 11}]}))
        claim = "In Lagos a yearly tenant is entitled to six months' notice to quit."
        good = {"answer": ("You paid for a year and got one month's notice.\n\n" + claim + " (s.13(1)(e), Tenancy Law of Lagos "
                           "State 2011). Count the months on the paper — one month is not it.\n\nReply in writing, keep the "
                           "notice and your receipt, and do not pack on a phone call.\n\nGeneral information, not legal advice.\n"
                           + listening.LINK),
                "claims": [{"text": claim, "fact_id": fact["id"]}], "state": "Lagos", "why": "most asked this week"}
        bad = dict(good, claims=[{"text": "You get six months free rent.", "fact_id": "lagos:nope"}])
        answers = iter([bad, good])
        gen = lambda prompt, system: next(answers)  # noqa: E731
        path, why = listening.answer(generate=gen, now=now, log=lambda *a: None)
        self.assertIsNone(path)
        self.assertIn("unknown fact", why)
        path, result = listening.answer(generate=gen, now=now, log=lambda *a: None)
        self.assertTrue(path and path.is_file())
        body = path.read_text()
        self.assertIn("https://www.nairaland.com/9/x", body)
        self.assertIn(listening.LINK, body)
        self.assertEqual(listening.load()["answered"][0]["url"], "https://www.nairaland.com/9/x")
        self.assertIsNone(listening.latest_answer(now=now), "a reply draft (.md) is a library result, never the week's page")
        # the same thread is never answered twice
        self.assertEqual(listening.answer(generate=gen, now=now, log=lambda *a: None), (None, "no open question this week"))

    def test_rent_is_a_whole_word_not_the_tail_of_parent(self):
        self.assertEqual(listening.score({"title": "Your Baby's Crying Has Patterns: What Different Crying Behaviors Can Tell Parent"}), 0)
        self.assertEqual(listening.score({"title": "Nigerian Parents: What If My Life Is Meant To Be Different"}), 0)
        self.assertGreaterEqual(listening.score({"title": "Landlord Increased My Rent By 100%, Is This Legal? Please Advise"}), 9)
        self.assertGreater(listening.score({"title": "My rent is due, can the landlord lock my door?"}), 0)

    def _page_draft(self, slug, topic, facts):
        f1, f2, f3 = facts[0], facts[1], facts[2]
        claims = [{"text": f["text"].strip().rstrip(".") + ".", "fact_id": f["id"]} for f in (f1, f2, f3)]
        points = "\n\n".join("%d. %s (%s)" % (i + 1, c["text"], f["cite"] or "the Law") for i, (c, f) in enumerate(zip(claims, (f1, f2, f3))))
        body = ("Plenty of rent wahala in %s starts with nobody checking what the law already settled. Here it is, section by "
                "section, so you can check it yourself before you pay or before you pack.\n\n%s\n\nThe one thing to do next: "
                "write, keep every paper, and count the months on the notice before you move anything." % (f1["state"], points))
        body += ("\n\nKeep your receipts; a receipt is the paper that settles most of these quarrels before they start. Count the "
                 "months from the day the notice reaches you, not the day it was written.") * 2
        return {"subject": "Before You Sign In %s: What The Tenancy Law Says On Notice" % f1["state"].split(" (")[0],
                "question": "How many months notice must a landlord give in %s?" % f1["state"].split(" (")[0],
                "short_answer": "A yearly tenant gets six months notice and a monthly tenant one month, counted in full months (s.8).",
                "body": body, "claims": claims, "state": f1["state"], "why": "asked this week"}

    def test_the_ears_choose_the_week_and_the_hand_made_lagos_opener_is_not_repeated(self):
        answered = [{"date": "2026-10-30", "url": "https://www.nairaland.com/8774812/x", "kind": "thread_opener",
                     "state_slug": "lagos", "topic": "receipts"}]
        asked = [{"title": "Landlord gave me 1 month quit notice in Abuja, is it legal? Please advise", "score": 11},
                 {"title": "Your Baby's Crying Has Patterns: What Different Crying Behaviors Can Tell Parent", "score": 0}]
        self.assertEqual(listening.topic_hint(asked)[:2], ("abuja", "notice_ladder"))
        slug, topic, facts = listening.opener_choice(answered, items=asked)
        self.assertEqual((slug, topic), ("abuja", "notice_ladder"), "what someone asked this week wins")
        self.assertGreaterEqual(len(facts), 3)
        slug2, topic2, _ = listening.opener_choice(answered, items=[])
        self.assertNotEqual((slug2, topic2), ("lagos", "receipts"), "the hand-made Lagos opener is not repeated")
        self.assertNotEqual(slug2, "lagos", "other Tier A states get their turn before Lagos comes round again")
        self.assertIsNone(listening.topic_hint([{"title": "3 bedroom flat for rent in Lekki, receipt on request", "score": 2}]),
                          "an advert is not a question")

    def test_the_week_s_answer_is_a_page_the_machine_publishes_not_a_paste_for_the_owner(self):
        now = dt.datetime(2026, 11, 2, 0, 30, tzinfo=dt.timezone.utc)
        listening.OUT.parent.mkdir(parents=True, exist_ok=True)
        asked = [{"title": "Landlord gave me 1 month quit notice in Abuja, is it legal? Please advise", "score": 11,
                  "url": "https://www.nairaland.com/1/x", "board": "properties", "seen_at": now.isoformat()}]
        listening.OUT.write_text(json.dumps({"pulled_at": now.isoformat(), "items": asked, "answered": [
            {"date": "2026-10-30", "url": "https://www.nairaland.com/8774812/x", "kind": "thread_opener",
             "state_slug": "lagos", "topic": "receipts"}]}))
        slug, topic, facts = listening.opener_choice(listening.load()["answered"], items=asked)
        facts_by_id = {f["id"]: f for f in law_index.facts_for(slug)}
        good = self._page_draft(slug, topic, facts)
        self.assertEqual(listening.opener_gate(good, facts_by_id), [])
        for broken, needle in (
                (dict(good, body=good["body"].replace("wahala", "WAHALA EVERYWHERE")), "ALL CAPS"),
                (dict(good, subject="Before You Pay Rent In Lagos: 5 Things The Tenancy Law Actually Says (With Section Numbers)"), "subject length"),
                (dict(good, claims=good["claims"][:2]), "fewer than 3"),
                (dict(good, body=good["body"] + "\n\nMore at https://docoga.com.ng"), "carries a link"),
                (dict(good, question="Notice in Abuja"), "end with ?"),
                (dict(good, short_answer="Six months."), "short_answer length")):
            self.assertTrue(any(needle in p for p in listening.opener_gate(broken, facts_by_id)), needle)
        drafts = iter([dict(good, claims=good["claims"][:2]), good])
        gen = lambda prompt, system: next(drafts)  # noqa: E731
        prompts = []
        path, why = listening.opener(generate=lambda p, s: (prompts.append(p), next(drafts))[1], now=now, log=lambda *a: None)
        self.assertIsNone(path, why)
        self.assertIn("WHAT SOMEONE ASKED THIS WEEK", prompts[0], "the question heard is in the prompt")
        self.assertNotIn("https://www.nairaland.com", prompts[0], "the asker is not named or linked")
        path, pack = listening.opener(generate=gen, now=now, log=lambda *a: None)
        self.assertTrue(path and path.is_file() and path.suffix == ".json")
        self.assertEqual((pack["status"], pack["kind"], pack["state"], pack["topic"], pack["tool"]),
                         ("approved", "answer_page", slug, topic, "notice-to-quit"))
        self.assertEqual(pack["post"]["headline"], good["subject"])
        self.assertGreaterEqual(len(pack["post"]["lines"]), 5, "paragraphs, not one blob")
        self.assertEqual(pack["quiz"]["question"], good["question"])
        self.assertTrue(pack["url"].startswith("https://docoga.com.ng/guides/") and slug in pack["url"])
        rec = listening.load()["answered"][-1]
        self.assertEqual((rec["kind"], rec["state_slug"], rec["topic"], rec["url"]), ("answer_page", slug, topic, pack["url"]))
        self.assertEqual(listening.latest_answer(now=now), path)
        self.assertEqual(listening.answer_url(path), pack["url"])
        nxt = listening.opener_choice(listening.load()["answered"], items=asked)
        self.assertNotEqual((nxt[0], nxt[1]), (slug, topic), "the same state/topic is never opened twice")
        # the guides builder turns the pack into the page, the sitemap entry and the index — same run, no hands
        site = Path(self.tmp.name) / "site"
        site.mkdir()
        (site / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="x">\n</urlset>\n')
        with patch.object(og_images, "OG_DIR", Path(self.tmp.name) / "og"):
            written = guides_build.build(day=now.date(), site=site, drafts_dir=Path(self.tmp.name) / "no-drafts",
                                         answers_dir=listening.ANSWERS, log=lambda *a: None)
        self.assertEqual(written, [pack["url"]])
        page = (site / "guides" / (pack["theme"] + ".html")).read_text()
        self.assertIn("<h1>%s</h1>" % good["subject"], page)
        self.assertIn("FAQPage", page)
        self.assertIn(good["question"], page)
        self.assertIn("notice-to-quit", page)
        self.assertIn("not legal advice", page)
        self.assertIn(pack["url"], (site / "sitemap.xml").read_text())
        self.assertIn(pack["url"], (site / "guides" / "index.html").read_text())
        for text in ((WF / "brain.yml").read_text(), (WF / "brain_scorecard.yml").read_text()):
            self.assertNotIn("paste", text.lower().replace("pastel", ""), "nothing asks the owner to paste")
        self.assertIn("LISTENING_URL", (WF / "brain_scorecard.yml").read_text())

    def test_state_is_read_from_the_title_when_it_is_there(self):
        self.assertEqual(listening.state_for({"title": "Abuja landlord quit notice question"}), "abuja")
        self.assertEqual(listening.state_for({"title": "landlord wahala"}), "lagos")


# ───────────────────────────── Instagram collaborators ─────────────────────────────
class CollaboratorTests(unittest.TestCase):
    def test_up_to_three_clean_handles_on_the_kinds_meta_allows(self):
        self.assertEqual(json.loads(ig_publish.collaborators_param("@lagoslawyer, propertyng  @lagoslawyer, x.y_z, fourth", "reel")),
                         ["lagoslawyer", "propertyng", "x.y_z"])
        self.assertIsNone(ig_publish.collaborators_param("@lagoslawyer", "story"), "Stories cannot carry collaborators")
        self.assertIsNone(ig_publish.collaborators_param("", "photo"))
        self.assertIsNone(ig_publish.collaborators_param("handle!", "carousel"))
        with patch.dict(os.environ, {"IG_COLLABORATORS": "partner_page"}):
            self.assertEqual(ig_publish.collaborators_param(kind="carousel"), '["partner_page"]')

    def test_both_instagram_workflows_pass_the_variable(self):
        for wf in ("instagram_autopost.yml", "facebook_autopost.yml"):
            self.assertIn("IG_COLLABORATORS: ${{ vars.IG_COLLABORATORS }}", (WF / wf).read_text(), wf)


# ───────────────────────────── captions ─────────────────────────────
class CaptionTests(unittest.TestCase):
    def words(self):
        words, t = [], 0.0
        text = ("Your landlord gave you one month to leave after a full year of rent. Here is what the Lagos Tenancy Law "
                "says. A yearly tenant gets six months notice, not one. That is section thirteen. Keep your receipt safe.")
        for w in text.split():
            words.append({"d": w, "w": w.lower(), "t0": round(t, 3), "t1": round(t + 0.3, 3)})
            t += 0.35 + (0.9 if w.endswith(".") else 0)
        return words

    def test_cues_obey_two_lines_of_42_and_break_at_sentences(self):
        srt = yt_captions.srt_text(self.words())
        blocks = [b for b in srt.strip().split("\n\n") if b]
        self.assertGreaterEqual(len(blocks), 4)
        for b in blocks:
            lines = b.split("\n")[2:]
            self.assertLessEqual(len(lines), 2, b)
            self.assertTrue(all(len(x) <= 42 for x in lines), b)
        self.assertIn("00:00:00,000 -->", srt)
        self.assertTrue(blocks[0].endswith("after a full year of rent."))

    def test_synthetic_timings_are_refused_and_the_upload_is_one_multipart_call(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "words.json"
            p.write_text(json.dumps({"words": self.words(), "synthetic": True}))
            with self.assertRaises(ValueError):
                yt_captions.srt_from_words_file(p)
            p.write_text(json.dumps({"words": self.words(), "synthetic": False}))
            srt, n = yt_captions.srt_from_words_file(p)
            self.assertEqual(n, len(self.words()))
        calls = []

        class Resp:
            status_code = 200
            text = "{}"

            def json(self):
                return {"id": "cap1"}

        class Http:
            token = "t"

            def request(self, method, url, headers=None, data=None, params=None, files=None):
                calls.append((method, url, headers, data, params))
                return Resp()

        with patch.object(yt_captions, "upload", wraps=yt_captions.upload):
            import yt_publish
            with patch.object(yt_publish, "authorize", lambda http=None: (http, {})):
                ok, msg = yt_captions.upload("vid123", srt, http=Http(), name="English (DocOga)")
        self.assertTrue(ok, msg)
        method, url, headers, data, params = calls[0]
        self.assertEqual((method, params["part"], params["uploadType"]), ("POST", "snippet", "multipart"))
        self.assertIn(b'"videoId": "vid123"', data)
        self.assertIn(b"00:00:00,000 -->", data)
        self.assertIn("multipart/related", headers["Content-Type"])

    def test_the_deepdive_workflow_uploads_captions_without_ever_failing_the_publish(self):
        text = (WF / "deepdive.yml").read_text()
        i = text.index("name: Upload captions (never fails the publish)")
        step = text[i:i + 700]
        self.assertIn("continue-on-error: true", step)
        self.assertIn("tools/yt_captions.py --video-id", step)
        self.assertLess(text.index("name: Set the thumbnail"), i)
        self.assertLess(i, text.index("name: Record in the long-form ledger"))


# ───────────────────────────── guides ─────────────────────────────
class GuidesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.site = self.root / "site"
        self.site.mkdir()
        (self.site / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="x">\n</urlset>\n')
        self.drafts = self.root / "drafts"
        self.drafts.mkdir()

    def pack(self, day="2026-10-17", **over):
        p = dict(good_pack(), version=1, status="approved", date=day)
        p.update(over)
        return p

    def write(self, pack):
        (self.drafts / ("%s.json" % pack["date"])).write_text(json.dumps(pack))

    def test_an_approved_pack_becomes_a_cited_page_with_schema_tool_link_and_sitemap_entry(self):
        quiz = {"question": "How many months for a yearly tenant?", "explanation": "Six — s.13(1)(e)."}
        self.write(self.pack(quiz=quiz))
        written = guides_build.build(day=dt.date(2026, 10, 17), site=self.site, drafts_dir=self.drafts, log=lambda *a: None)
        self.assertEqual(written, ["https://docoga.com.ng/guides/yearly-tenant-six-months-lagos"])  # clean URL: Cloudflare 307s /x.html → /x
        html = (self.site / "guides" / "yearly-tenant-six-months-lagos.html").read_text()
        self.assertIn("<h1>Yearly tenant in Lagos? Six months&#x27; notice, not three</h1>", html)
        self.assertIn("s.13(1)(e)", html)
        self.assertIn("Tenancy Law of Lagos State 2011", html)
        self.assertIn('"@type": "FAQPage"', html)
        self.assertIn("notice-to-quit-lagos?s=g", html)
        self.assertNotIn(".html?s=g", html)
        self.assertIn("not legal advice", html)
        self.assertNotIn("Send this to the friend", html.split("<h1>")[1].split("</h1>")[0])
        sitemap = (self.site / "sitemap.xml").read_text()
        self.assertIn("<loc>https://docoga.com.ng/guides/</loc>", sitemap)
        self.assertIn("<loc>https://docoga.com.ng/guides/yearly-tenant-six-months-lagos</loc>", sitemap)
        index = (self.site / "guides" / "index.html").read_text()
        self.assertIn('href="https://docoga.com.ng/guides/yearly-tenant-six-months-lagos"', index)  # clean URL
        self.assertEqual(json.loads((self.site / "guides" / "guides.json").read_text())[0]["state"], "Lagos")

    def test_rebuilding_is_idempotent_and_a_pack_without_law_is_not_a_page(self):
        self.write(self.pack())
        self.write(self.pack(day="2026-10-16", theme="just-an-opinion", claims=[]))
        guides_build.build(day=dt.date(2026, 10, 17), site=self.site, drafts_dir=self.drafts, log=lambda *a: None)
        again = guides_build.build(day=dt.date(2026, 10, 17), site=self.site, drafts_dir=self.drafts, log=lambda *a: None)
        self.assertEqual(again, [])
        self.assertEqual((self.site / "sitemap.xml").read_text().count("<loc>"), 2)
        self.assertFalse(list((self.site / "guides").glob("just-an-opinion*")))

    def test_future_packs_wait_for_their_day(self):
        self.write(self.pack(day="2026-10-20"))
        self.assertEqual(guides_build.build(day=dt.date(2026, 10, 17), site=self.site, drafts_dir=self.drafts, log=lambda *a: None), [])

    def test_off_switch_and_indexnow_need_a_key(self):
        with patch.dict(os.environ, {"BRAIN_GUIDES": "off"}):
            out = io.StringIO()
            with redirect_stdout(out):
                guides_build.main(["build", "--site", str(self.site)])
            self.assertIn("GUIDES_WRITTEN=0", out.getvalue())
        with patch.dict(os.environ, {"INDEXNOW_KEY": ""}):
            self.assertFalse(guides_build.ping(["https://docoga.com.ng/guides/x.html"], log=lambda *a: None))
        sent = []
        self.assertTrue(guides_build.ping(["https://docoga.com.ng/guides/x.html"], key="abcdef123456",
                                          http=lambda req: sent.append(json.loads(req.data)) or 202, log=lambda *a: None))
        self.assertEqual(sent[0]["keyLocation"], "https://docoga.com.ng/abcdef123456.txt")
        self.assertEqual(guides_build.ensure_key_file(self.site, "abcdef123456").read_text().strip(), "abcdef123456")

    def test_the_brain_workflow_builds_guides_and_commits_them(self):
        text = (WF / "brain.yml").read_text()
        self.assertIn("tools/guides_build.py build", text)
        self.assertIn("BRAIN_GUIDES: ${{ vars.BRAIN_GUIDES }}", text)
        self.assertIn("site/guides site/og site/sitemap.xml", text)
        self.assertIn("tools/listening.py pull", text)
        self.assertIn("tools/listening.py answer", text)
        self.assertIn("tools/gemini_text.py probe", text)
        self.assertIn("brain/listening.json brain/answers", text)
        self.assertIn("tools/listening.py latest", (WF / "brain_scorecard.yml").read_text())


# ───────────────────────────── the Deep-Dive description funnel ─────────────────────────────
class CrosslinkTests(unittest.TestCase):
    def test_public_shorts_and_episodes_are_named_newest_first_and_private_ones_are_not(self):
        with tempfile.TemporaryDirectory() as d:
            logs = Path(d) / "logs"
            logs.mkdir()
            (logs / "youtube_published.json").write_text(json.dumps([
                {"topic": "Old one", "url": "https://youtu.be/a", "privacy": "public", "date": "2026-10-01"},
                {"topic": "Newest #Shorts", "url": "https://youtu.be/b", "privacy": "public", "date": "2026-10-16"},
                {"topic": "Hidden", "url": "https://youtu.be/c", "privacy": "private", "date": "2026-10-17"}]))
            (logs / "youtube_longform.json").write_text(json.dumps([
                {"title": "Deep-Dive 2", "url": "https://youtu.be/d", "privacy": "unlisted", "date": "2026-10-10"}]))
            text = deepdive.crosslinks_text(root=d)
        self.assertTrue(text.startswith("60-second versions (Shorts):\nNewest — https://youtu.be/b"))
        self.assertNotIn("Hidden", text)
        self.assertNotIn("Deep-Dive 2", text, "unlisted episodes are not advertised")

    def test_the_shorts_summary_names_the_one_studio_tap(self):
        self.assertIn("Related video", (WF / "youtube_scheduled.yml").read_text())


if __name__ == "__main__":
    unittest.main()



class SitemapDedupeTests(unittest.TestCase):
    """30 Oct 2026: two guides sat in the sitemap twice. One <url> per <loc>, newest block wins."""

    def test_duplicate_locs_collapse_to_the_latest_block(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import guides_build as gb
        block = "  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.6</priority>\n  </url>\n"
        text = ('<?xml version="1.0"?>\n<urlset>\n' + block % ("https://docoga.com.ng/a", "2026-10-24")
                + block % ("https://docoga.com.ng/b", "2026-10-25") + block % ("https://docoga.com.ng/a", "2026-10-29") + "</urlset>\n")
        out, dropped = gb.dedupe_sitemap(text)
        self.assertEqual(dropped, 1)
        self.assertEqual(out.count("<loc>https://docoga.com.ng/a</loc>"), 1)
        self.assertIn("2026-10-29", out)
        self.assertNotIn("2026-10-24", out)
        self.assertEqual(gb.dedupe_sitemap(out), (out, 0))

    def test_the_committed_sitemap_has_no_duplicate_loc(self):
        import re
        locs = re.findall(r"<loc>([^<]+)</loc>", (ROOT / "site" / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertEqual(len(locs), len(set(locs)), sorted({l for l in locs if locs.count(l) > 1}))
