"""The standing editor (tools/brain.py) and everything it touches.

What these tests pin, in the owner's words (16 Oct 2026): "a brain that can think
like you, understands content creation and my business, works autonomously". The
thinking is Gemini's and is faked here; what is tested is everything around it —
the law shelf it may cite, the gates that refuse a wrong or repeated post, the
quota discipline, how the lanes consume an approved pack and fall back to the
rotation when there is none, the card's new layouts, and the Deep-Dive writer's
contract with the engine.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "tools", ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import brain  # noqa: E402
import brain_drafts  # noqa: E402
import gemini_quota  # noqa: E402
import gemini_text  # noqa: E402
import law_index  # noqa: E402
import newsdesk  # noqa: E402
import listening  # noqa: E402

MONDAY = date(2026, 10, 19)      # a Reel day: the pack must carry a Short
SUNDAY = date(2026, 10, 18)      # no Short rendered


def good_pack(day=MONDAY, **over):
    """A pack that passes every deterministic gate for the Lagos shelf."""
    facts = law_index.facts_for("lagos")
    six_months = next(f for f in facts if "Yearly tenant" in f["text"])
    pack = {
        "theme": "yearly-tenant-six-months-lagos",
        "post_type": "educational",
        "hook_type": "STAT",
        "state": "lagos",
        "claims": [{"text": "In Lagos a yearly tenant is entitled to six months' notice to quit.",
                    "fact_id": six_months["id"]}],
        "post": {"headline": "Yearly tenant in Lagos? Six months' notice, not three",
                 "lines": ["In Lagos a yearly tenant is entitled to six months' notice to quit.",
                           "That is s.13(1)(e) of the Tenancy Law 2011 — count the months on your notice.",
                           "A dated, written notice is the paper that decides it. Make yours in two minutes."],
                 "cta": "Send this to the friend whose rent is due in January.",
                 "hashtags": ["#DocOga", "#TenantRights", "#Lagos", "#NoticeToQuit"]},
        "reader": "ngozi",
        "tool": "notice-to-quit",
        "threads": {"text": "Yearly tenant in Lagos? The law gives you six months' notice, not three. "
                            "s.13(1)(e), Tenancy Law 2011. Count the months on the paper before you pack. "
                            "How many months did your last notice give you?",
                    "hashtags": ["#DocOga", "#Lagos"]},
        "visual": {"kicker": "know your rights", "layout": "stat", "big": "6 MONTHS", "plate": "lagos rooftops dusk"},
        "short": {"title": "Three months' notice? Check the law.", "hook_sub": "yearly tenants in Lagos get six",
                  "tips": [{"text": "Read your agreement", "sub": "the notice clause comes first"},
                           {"text": "Count the months", "sub": "six for a yearly tenant"},
                           {"text": "Insist on writing", "sub": "a dated notice, not a phone call"},
                           {"text": "Keep every receipt", "sub": "paper beats memory in court"}]},
        "why": "Monday is know-your-rights and the notice ladder is the most-searched Lagos rule.",
    }
    pack.update(over)
    return pack


class FakeGemini:
    """Answers generate_json calls in order; records every prompt it saw."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, url, payload, key):
        self.prompts.append(payload["contents"][0]["parts"][0]["text"])
        if not self.answers:
            raise AssertionError("the brain asked Gemini more times than the test allowed")
        answer = self.answers.pop(0)
        if isinstance(answer, tuple):
            return answer
        return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]})


def refusal(scope="day", model="gemini-2.5-flash"):
    quota = "GenerateRequestsPerDayPerProjectPerModel-FreeTier" if scope == "day" else \
        "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
    return 429, json.dumps({"error": {"code": 429, "message": "You exceeded your current quota. Please retry in 7s.",
                                      "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                                                   "violations": [{"quotaId": quota, "quotaValue": "20",
                                                                   "quotaDimensions": {"model": model}}]}]}})


class Sandbox(unittest.TestCase):
    """Every test writes drafts, the said-ledger and the quota ledger under a temp dir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.drafts = root / "drafts"
        self.env = patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": str(self.drafts), "DOCOGA_BRAIN": "on",
                                           "BRAIN_PLATES": "off", "GEMINI_API_KEY": "test-key"})
        self.env.start()
        self.addCleanup(self.env.stop)
        import brain_scorecard
        for target, name, value in ((brain, "SAID", root / "said.json"),
                                    (brain, "FEEDBACK", root / "feedback.md"),
                                    (brain_scorecard, "LEDGER", root / "scorecard.json"),
                                    (newsdesk, "PINNED", root / "newsdesk_pinned.json"),
                                    (newsdesk, "OUT", root / "newsdesk.json"),
                                    (listening, "OUT", root / "listening.json"),
                                    (gemini_quota, "LEDGER", root / "quota.json")):
            p = patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.out = io.StringIO()

    def ctx(self, day=MONDAY):
        ctx = brain.day_context(day, said=brain.load_said())
        ctx["facts_by_id"] = {f["id"]: f for f in ctx["facts"]}
        return ctx


class LawShelfTests(unittest.TestCase):
    def test_every_publishable_state_has_a_shelf_with_ids_and_cites(self):
        for slug, name, tier in law_index.states():
            facts = law_index.facts_for(slug)
            self.assertTrue(facts, slug)
            for f in facts:
                self.assertTrue(f["id"].startswith(slug + ":"), f["id"])
                self.assertTrue(f["text"])
                self.assertNotIn("<b>", f["text"], "HTML must not reach the prompt")

    def test_the_lagos_notice_ladder_is_on_the_shelf_with_its_section(self):
        facts = law_index.facts_for("lagos")
        yearly = [f for f in facts if "Yearly tenant" in f["text"]]
        self.assertEqual(len(yearly), 1)
        self.assertEqual(yearly[0]["cite"], "s.13(1)(e)")
        self.assertIn("six months", yearly[0]["text"])

    def test_ids_are_unique_across_states(self):
        ids = [f["id"] for f in law_index.all_facts()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_state_rotation_covers_every_state(self):
        slugs = {brain.state_for(date(2026, 10, 1 + i)) for i in range(8)}
        self.assertEqual(slugs, {s for s, _, _ in law_index.states()})


class GeminiTextTests(Sandbox):
    def test_a_daily_refusal_moves_to_the_next_model_in_the_chain(self):
        fake = FakeGemini([refusal("day"), {"ok": 1}])
        out = gemini_text.generate_json("hi", http=fake, sleep=lambda s: None, log=lambda *a: None,
                                        models_chain=("gemini-2.5-flash", "gemini-2.5-flash-lite"))
        self.assertEqual(out, {"ok": 1})
        self.assertEqual(len(fake.prompts), 2)

    def test_a_minute_refusal_is_waited_out_once(self):
        waits = []
        fake = FakeGemini([refusal("minute"), {"ok": 2}])
        out = gemini_text.generate_json("hi", http=fake, sleep=waits.append, log=lambda *a: None,
                                        models_chain=("gemini-2.5-flash",))
        self.assertEqual(out, {"ok": 2})
        self.assertEqual(len(waits), 1)
        self.assertLessEqual(waits[0], gemini_text.MINUTE_WAIT_CAP_S)

    def test_every_model_spent_raises_exhausted_with_the_reset_instant(self):
        fake = FakeGemini([refusal("day", "gemini-a"), refusal("day", "gemini-b")])
        with self.assertRaises(gemini_text.Exhausted) as cm:
            gemini_text.generate_json("hi", http=fake, sleep=lambda s: None, log=lambda *a: None,
                                      models_chain=("gemini-a", "gemini-b"))
        self.assertIsNotNone(cm.exception.resumes_at)

    def test_json_is_parsed_through_a_code_fence(self):
        self.assertEqual(gemini_text.parse_json("```json\n{\"a\": 1}\n```"), {"a": 1})
        self.assertEqual(gemini_text.parse_json("Sure! {\"a\": [1,2]} done"), {"a": [1, 2]})

    def test_the_request_asks_for_json_and_never_a_search_tool(self):
        seen = {}

        def http(url, payload, key):
            seen.update(payload)
            return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})
        gemini_text.generate_json("hi", http=http, log=lambda *a: None, models_chain=("gemini-m",))
        self.assertEqual(seen["generationConfig"]["responseMimeType"], "application/json")
        self.assertNotIn("tools", seen, "search grounding is not free-tier; the shelf is the law")


class GateTests(Sandbox):
    def test_a_good_pack_passes_every_deterministic_gate(self):
        self.assertEqual(brain.lint(good_pack(), self.ctx(), []), [])

    def test_a_post_without_a_send_line_or_with_a_slogan_is_refused(self):
        """17 Oct 2026: sends/forwards/replies are what every 2026 feed ranks on — the line is not optional."""
        post = dict(good_pack()["post"])
        post.pop("cta")
        self.assertTrue(any("post.cta is missing" in p for p in brain.lint(good_pack(post=post), self.ctx(), [])))
        post["cta"] = "DocOga, Nigeria's document engine."
        self.assertTrue(any("not a slogan" in p for p in brain.lint(good_pack(post=post), self.ctx(), [])))
        post["cta"] = "Forward this to your landlord group: https://docoga.com.ng"
        self.assertTrue(any("must not carry the link" in p for p in brain.lint(good_pack(post=post), self.ctx(), [])))
        post["cta"] = "Tag the friend who paid cash with no receipt."
        self.assertEqual(brain.lint(good_pack(post=post), self.ctx(), []), [])
        self.assertIn("Tag the friend who paid cash with no receipt.", brain_drafts.post_text(good_pack(post=post)),
                      "the send line is in the copy the lanes post and the card renders")

    def test_the_post_links_to_the_state_page_for_its_tool_and_never_to_a_404(self):
        """17 Oct 2026: one tap less between the post and the paper."""
        self.assertTrue(brain_drafts.post_text(good_pack()).endswith("https://docoga.com.ng/notice-to-quit-lagos.html"))
        self.assertIn("notice-to-quit-lagos.html", brain_drafts.threads_text(good_pack()))
        self.assertTrue(brain_drafts.post_text(good_pack(state="kwara")).endswith("notice-to-quit-nigeria.html"),
                        "no Kwara page → the national guide")
        self.assertTrue(brain_drafts.post_text(good_pack(tool="payslip")).endswith("https://docoga.com.ng"),
                        "no payslip page → the homepage")
        self.assertTrue(brain_drafts.post_text(good_pack(tool=None)).endswith("https://docoga.com.ng"))
        self.assertTrue(any("tool must be one of" in p for p in brain.lint(good_pack(tool="lease"), self.ctx(), [])))
        self.assertEqual(brain.lint(good_pack(tool=None), self.ctx(), []), [])

    def test_a_news_hook_must_be_a_headline_the_papers_printed(self):
        """17 Oct 2026: the brain reads the morning papers; it may not write them."""
        newsdesk.OUT.write_text(json.dumps({"fetched": datetime.now(timezone.utc).isoformat(),
                                            "items": [{"title": "Lagos landlord punched over 75% rent hike", "source": "The Trumpet",
                                                       "published": "2026-10-15T09:00:00+00:00", "score": 9}]}), encoding="utf-8")
        ctx = self.ctx()
        self.assertIn("Lagos landlord punched over 75% rent hike", brain.prompt_for(ctx))
        self.assertEqual(brain.lint(good_pack(news_hook="Lagos landlord punched over 75% rent hike"), ctx, []), [])
        self.assertEqual(brain.lint(good_pack(news_hook=None), ctx, []), [])
        self.assertTrue(any("NEWSDESK" in p for p in brain.lint(good_pack(news_hook="Senate passes rent control act"), ctx, [])))

    def test_stale_news_is_not_offered(self):
        newsdesk.OUT.write_text(json.dumps({"fetched": "2026-09-01T00:00:00+00:00",
                                            "items": [{"title": "Old story", "source": "Punch"}]}), encoding="utf-8")
        self.assertIn("no fresh stories", brain.prompt_for(self.ctx()))

    def test_threads_topic_tag_and_poll_travel_with_the_pack(self):
        """17 Oct 2026: a topic tag is the subject label people browse; a poll is replies without a link."""
        self.assertEqual(brain_drafts.threads_topic(good_pack()), "Tenant Rights Nigeria")
        self.assertEqual(brain_drafts.threads_topic(good_pack(tool="payslip")), "Nigerian Workplace")
        self.assertEqual(brain_drafts.threads_topic(good_pack(tool=None)), brain_drafts.DEFAULT_TOPIC)
        pack = good_pack()
        pack["threads"]["poll"] = {"option_a": "Six months", "option_b": "Three months", "option_c": "One month"}
        self.assertEqual(brain_drafts.threads_poll(pack), {"option_a": "Six months", "option_b": "Three months", "option_c": "One month"})
        self.assertNotIn("http", brain_drafts.threads_text(pack), "a poll post carries no link — Threads refuses the pair")
        self.assertIn("http", brain_drafts.threads_text(good_pack()))
        self.assertEqual(brain.lint(pack, self.ctx(), []), [])
        bad = good_pack(); bad["threads"]["poll"] = {"option_a": "x" * 26, "option_b": "y"}
        self.assertTrue(any("at most 25" in p for p in brain.lint(bad, self.ctx(), [])))
        bad = good_pack(); bad["threads"]["poll"] = {"option_a": "only one"}
        self.assertTrue(any("option_a and option_b" in p for p in brain.lint(bad, self.ctx(), [])))
        self.assertIsNone(brain_drafts.threads_poll(bad))
        bad = good_pack(); bad["threads"]["topic"] = "Rent & Law."
        self.assertTrue(any("threads.topic" in p for p in brain.lint(bad, self.ctx(), [])))

    def test_a_telegram_quiz_is_a_cited_claim_or_nothing(self):
        """17 Oct 2026: a quiz gets a tap from a reader who would not type; the explanation is the law."""
        quiz = {"question": "A yearly tenant in Lagos: how much notice to quit?", "options": ["One month", "Three months", "Six months"],
                "correct": 2, "explanation": "Six months — s.13(1)(e), Lagos Tenancy Law 2011.", "fact_id": "lagos:notice_ladder:5"}
        self.assertEqual(brain.lint(good_pack(quiz=quiz), self.ctx(), []), [])
        self.assertEqual(brain_drafts.quiz(good_pack(quiz=quiz))["correct"], 2)
        self.assertIsNone(brain_drafts.quiz(good_pack(quiz=None)))
        self.assertTrue(any("quiz.fact_id" in p for p in brain.lint(good_pack(quiz={**quiz, "fact_id": "made:up"}), self.ctx(), [])))
        self.assertTrue(any("section of its fact" in p for p in brain.lint(good_pack(quiz={**quiz, "explanation": "Six months."}), self.ctx(), [])))
        self.assertTrue(any("quiz must be null" in p for p in brain.lint(good_pack(quiz={**quiz, "correct": 7}), self.ctx(), [])))
        self.assertTrue(any("quiz must be null" in p for p in brain.lint(good_pack(quiz={**quiz, "options": ["only"]}), self.ctx(), [])))

    def test_a_threads_post_that_does_not_end_with_a_question_is_refused(self):
        pack = good_pack(threads={"text": "Yearly tenant in Lagos? Six months' notice, not three. Count the months.",
                                  "hashtags": ["#DocOga"]})
        self.assertEqual(brain.lint(pack, self.ctx(), []), [], "a question anywhere in the closing stretch counts")
        pack = good_pack(threads={"text": "Yearly tenants in Lagos get six months' notice, not three. Count the months before you pack.",
                                  "hashtags": ["#DocOga"]})
        self.assertTrue(any("end with a question" in p for p in brain.lint(pack, self.ctx(), [])))

    def test_a_claim_with_an_unknown_fact_id_is_refused(self):
        pack = good_pack(claims=[{"text": "x", "fact_id": "lagos:made_up:9"}])
        self.assertTrue(any("unknown fact id" in p for p in brain.lint(pack, self.ctx(), [])))

    def test_a_fact_from_another_state_is_refused(self):
        edo = law_index.facts_for("edo")[0]["id"]
        pack = good_pack(claims=[{"text": "x", "fact_id": edo}])
        self.assertTrue(any("belongs to edo" in p for p in brain.lint(pack, self.ctx(), [])))

    def test_a_price_that_is_neither_ours_nor_quoted_is_refused(self):
        pack = good_pack()
        pack["post"]["lines"][2] = "Our pass is ₦3,500 this week only."
        problems = brain.lint(pack, self.ctx(), [])
        self.assertTrue(any("₦3,500" in p for p in problems), problems)

    def test_a_statutory_fine_quoted_from_a_cited_fact_is_allowed(self):
        facts = law_index.facts_for("lagos")
        fine = next(f for f in facts if "₦100,000" in f["text"] and "receipt" in f["text"].lower())
        pack = good_pack(claims=[{"text": "A Lagos landlord who refuses a receipt risks a ₦100,000 fine.",
                                  "fact_id": fine["id"]}])
        pack["post"]["lines"][0] = "A Lagos landlord who refuses a receipt risks a ₦100,000 fine under s.5(3)."
        self.assertEqual([p for p in brain.lint(pack, self.ctx(), []) if "price" in p], [])

    def test_banned_phrases_markdown_and_shouting_are_refused(self):
        pack = good_pack()
        pack["post"]["headline"] = "UNLOCK YOUR RIGHTS TODAY WITH THIS GAME-CHANGER"
        pack["post"]["lines"][0] = "**Bold** claims in Lagos s.13(1)(e)."
        problems = brain.lint(pack, self.ctx(), [])
        self.assertTrue(any("banned phrase" in p for p in problems))
        self.assertTrue(any("shouting" in p for p in problems))
        self.assertTrue(any("markdown" in p for p in problems))

    def test_a_short_is_required_on_a_render_day_and_refused_on_sunday_if_malformed(self):
        pack = good_pack(short=None)
        self.assertTrue(any("Short is rendered today" in p for p in brain.lint(pack, self.ctx(MONDAY), [])))
        pack = good_pack(short={"title": "x", "tips": [{"text": "only one"}]}, state=None, claims=[])
        self.assertTrue(any("exactly four" in p for p in brain.lint(pack, self.ctx(SUNDAY), [])))

    def test_a_tip_longer_than_the_grammar_renders_is_refused(self):
        pack = good_pack()
        pack["short"]["tips"][1]["text"] = "Count the months on the notice carefully"
        self.assertTrue(any("tips[2].text" in p for p in brain.lint(pack, self.ctx(), [])))

    def test_repetition_is_refused_by_theme_cooldown_and_headline_similarity(self):
        said = [{"date": "2026-10-10", "theme": "yearly-tenant-six-months-lagos", "headline": "something else"},
                {"date": "2026-09-01", "theme": "other", "headline": "Yearly tenant in Lagos? Six months notice not three"}]
        problems = brain.lint(good_pack(), self.ctx(), said)
        self.assertTrue(any("cooldown" in p for p in problems), problems)
        self.assertTrue(any("the same as" in p for p in problems), problems)
        old = [{"date": "2026-08-01", "theme": "yearly-tenant-six-months-lagos", "headline": "x"}]
        self.assertEqual([p for p in brain.lint(good_pack(), self.ctx(), old) if "cooldown" in p], [])

    def test_a_plate_that_asks_for_faces_or_signs_is_refused(self):
        pack = good_pack(visual={"kicker": "know your rights", "layout": "poster", "big": "", "plate": "woman reading sign"})
        self.assertTrue(any("plate" in p for p in brain.lint(pack, self.ctx(), [])))

    def test_the_link_and_disclaimer_are_the_renderers_not_the_writers(self):
        pack = good_pack()
        pack["post"]["lines"].append("General information, not legal advice. https://docoga.com.ng")
        problems = brain.lint(pack, self.ctx(), [])
        self.assertTrue(any("link is added" in p for p in problems))
        self.assertTrue(any("disclaimer is added" in p for p in problems))


class HookBanditTests(Sandbox):
    """17 Oct 2026: the opening hook is chosen by what hooks earned, not by a rota."""

    def history(self, **arms):
        return [{"kpis": {"learning": {"hook_type": {h: {"n": n, "avg": avg, "total": n * avg} for h, (n, avg) in arms.items()}}}}]

    def test_without_numbers_the_order_is_advice_and_spreads_the_bets(self):
        said = [{"date": "2026-10-15", "hook_type": "STAT"}, {"date": "2026-10-16", "hook_type": "STAT"},
                {"date": "2026-10-17", "hook_type": "QUESTION"}]
        hook, why, binding = brain.hook_order(MONDAY, said, history=[])
        self.assertFalse(binding)
        self.assertNotIn(hook, ("STAT", "QUESTION"), "the last two days' hooks are excluded")
        self.assertIn("numbers have not spoken", why)
        ctx = self.ctx()
        self.assertEqual(brain.lint(good_pack(hook_type="STORY"), ctx, []), [], "advice, not a gate, until the numbers exist")

    def test_with_numbers_the_best_earning_hook_wins_and_the_lint_holds_the_model_to_it(self):
        history = self.history(STAT=(6, 40.0), QUESTION=(5, 12.0), CLAIM=(4, 9.0), STAKES=(3, 30.0),
                               CURIOSITY=(3, 8.0), HOWTO=(3, 10.0), STORY=(3, 11.0))
        hook, why, binding = brain.hook_order(MONDAY, [], history=history)
        self.assertTrue(binding)
        self.assertEqual(hook, "STAT")
        self.assertIn("earned 40 per post over 6 posts", why)
        ctx = self.ctx()
        ctx.update(hook=hook, hook_why=why, hook_binding=binding)
        self.assertEqual(brain.lint(good_pack(hook_type="STAT"), ctx, []), [])
        problems = brain.lint(good_pack(hook_type="CLAIM"), ctx, [])
        self.assertTrue(any("hook_type must be STAT today" in p for p in problems), problems)

    def test_an_untried_hook_is_explored_before_a_mediocre_one_is_repeated_forever(self):
        """UCB: five hooks measured and poor, two never tried — the exploration bonus sends the
        brain to an untried arm instead of grinding the best of a bad bunch."""
        history = self.history(STAT=(8, 5.0), QUESTION=(8, 4.0), CLAIM=(8, 4.5), STAKES=(8, 5.5), CURIOSITY=(8, 3.0))
        hook, why, _ = brain.hook_order(MONDAY, [], history=history)
        self.assertIn(hook, ("HOWTO", "STORY"))
        self.assertIn("explore", why)

    def test_yesterdays_hook_is_never_todays_even_when_it_is_the_best(self):
        history = self.history(STAT=(9, 80.0), QUESTION=(5, 10.0), CLAIM=(5, 10.0))
        said = [{"date": "2026-10-18", "hook_type": "STAT"}]
        hook, _, _ = brain.hook_order(MONDAY, said, history=history)
        self.assertNotEqual(hook, "STAT")

    def test_the_prompt_carries_the_hook_order_and_the_keyword_money_line(self):
        prompt = brain.prompt_for(self.ctx())
        self.assertIn("Hook for today:", prompt)
        self.assertIn("Comment LINK", prompt)


class PlanTests(Sandbox):
    def verdict(self, supported=True, extra=None):
        return {"verdicts": [{"fact_id": good_pack()["claims"][0]["fact_id"], "claim": "x", "supported": supported,
                              "reason": "fact says six months"}],
                "unsupported_statements": extra or []}

    def test_a_day_is_planned_gated_verified_written_and_remembered(self):
        fake = FakeGemini([good_pack(), self.verdict()])
        with redirect_stdout(self.out):
            result = brain.plan(days=1, start=MONDAY, http=fake, sleep=lambda s: None, log=print)
        self.assertEqual(len(result["approved"]), 1)
        pack = brain_drafts.draft_for(MONDAY)
        self.assertIsNotNone(pack, "the lanes must find the approved pack")
        self.assertEqual(pack["status"], "approved")
        self.assertEqual(pack["short"]["hook_text"], "THREE MONTHS' NOTICE?\nCHECK THE LAW.")
        said = brain.load_said()
        self.assertEqual(said[0]["theme"], "yearly-tenant-six-months-lagos")
        self.assertIn("THE LAW SHELF FOR LAGOS", fake.prompts[0])
        self.assertIn("lagos:notice_ladder:5", fake.prompts[0])
        self.assertIn("FACTS (the only law", fake.prompts[1])

    def test_a_verifier_disagreement_refuses_the_pack_and_the_retry_hears_why(self):
        fake = FakeGemini([good_pack(), self.verdict(False), good_pack(), self.verdict(True, ["a stray rule"])])
        with redirect_stdout(self.out):
            result = brain.plan(days=1, start=MONDAY, http=fake, sleep=lambda s: None, log=print)
        self.assertEqual(result["approved"], [])
        self.assertIsNone(brain_drafts.draft_for(MONDAY))
        self.assertIn("PREVIOUS DRAFT WAS REFUSED", fake.prompts[2])
        self.assertIn("not supported", fake.prompts[2])
        self.assertTrue(any("not on the shelf" in p for p in result["refused"][MONDAY.isoformat()]))

    def test_a_pack_without_claims_needs_no_verifier_call(self):
        pack = good_pack(state=None, claims=[], post_type="engagement")
        pack["post"]["lines"] = ["Which document do you wish you had signed before you paid? Tell us below.",
                                 "We will turn the top answer into next week's explainer."]
        fake = FakeGemini([pack])
        with redirect_stdout(self.out):
            result = brain.plan(days=1, start=SUNDAY, http=fake, sleep=lambda s: None, log=print)
        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(len(fake.prompts), 1)

    def test_quota_exhaustion_stops_the_night_quietly_and_keeps_what_was_approved(self):
        fake = FakeGemini([good_pack(), self.verdict()] + [refusal("day", m) for m in gemini_text.models()])
        with redirect_stdout(self.out):
            result = brain.plan(days=2, start=MONDAY, http=fake, sleep=lambda s: None, log=print)
        self.assertEqual(len(result["approved"]), 1)
        self.assertIsNotNone(result["quota"])
        self.assertIsNotNone(brain_drafts.draft_for(MONDAY))

    def test_an_already_approved_day_costs_no_request(self):
        fake = FakeGemini([good_pack(), self.verdict()])
        with redirect_stdout(self.out):
            brain.plan(days=1, start=MONDAY, http=fake, sleep=lambda s: None, log=print)
            brain.plan(days=1, start=MONDAY, http=FakeGemini([]), sleep=lambda s: None, log=print)

    def test_the_cli_exit_codes_mean_what_the_workflow_reads(self):
        with patch.object(brain, "plan", return_value={"approved": [], "refused": {}, "quota": object(), "skipped": []}):
            with redirect_stdout(self.out):
                self.assertEqual(brain.main(["plan"]), 6)
        with patch.object(brain, "plan", return_value={"approved": [], "refused": {"d": ["x"]}, "quota": None, "skipped": []}):
            with redirect_stdout(self.out):
                self.assertEqual(brain.main(["plan"]), 3)
        with patch.object(brain, "plan", return_value={"approved": [], "refused": {}, "quota": None, "skipped": ["d"]}):
            with redirect_stdout(self.out):
                self.assertEqual(brain.main(["plan"]), 0)

    def test_feedback_reads_the_stats_ledger_and_the_said_ledger(self):
        stats = [{"taken_at": "2026-10-14T18:00:00+01:00", "channel": {"subscribers": 49, "views": 142, "videos": 13},
                  "videos": [{"kind": "short", "topic": "Keep a Rent Paper Trail", "views": 57},
                             {"kind": "short", "topic": "Change the lock", "views": 108}]}]
        said = [{"date": "2026-10-15", "post_type": "educational", "hook_type": "STAT", "state": "lagos"}]
        text = brain.feedback_text(stats=stats, said=said, today=date(2026, 10, 16))
        self.assertIn("'Change the lock' 108 views", text)
        self.assertIn("educational ×1", text)


class LaneConsumptionTests(Sandbox):
    def approve_monday(self):
        ctx = self.ctx(MONDAY)
        approved = brain.approve(good_pack(), ctx)
        brain.write_draft(approved)
        return approved

    def test_facebook_and_telegram_copy_come_from_the_pack_with_disclaimer_link_and_tags(self):
        self.approve_monday()
        import generate_facebook_content as fb
        with redirect_stdout(self.out):
            content = fb.generate(MONDAY, write=False)
        self.assertTrue(content["message"].startswith("Yearly tenant in Lagos? Six months' notice, not three"))
        self.assertIn(brain_drafts.DISCLAIMER, content["message"])
        self.assertIn("https://docoga.com.ng", content["message"])
        self.assertIn("#DocOga", content["message"])
        self.assertEqual(content["post_type"], "educational")
        self.assertEqual(content["brain"], "yearly-tenant-six-months-lagos")

    def test_without_a_pack_the_rotation_still_answers(self):
        import generate_facebook_content as fb
        import generate_telegram_content as tg
        with redirect_stdout(self.out):
            content = fb.generate(MONDAY, write=False)
        self.assertIsNone(content["brain"])
        self.assertTrue(any(tg.to_plain(t).strip().split("\n")[0] in content["message"]
                            for t in tg.TEMPLATES[content["post_type"]]))

    def test_the_kill_switch_ignores_every_pack(self):
        self.approve_monday()
        with patch.dict(os.environ, {"DOCOGA_BRAIN": "off"}):
            self.assertIsNone(brain_drafts.draft_for(MONDAY))

    def test_threads_copy_is_the_short_version_and_fits_metas_limit(self):
        self.approve_monday()
        import generate_threads_content as th
        import random
        post_type, text, notes, extras = th.build(MONDAY, random.Random(1))
        self.assertEqual(post_type, "educational")
        self.assertIn("six months' notice", text)
        self.assertIn("https://docoga.com.ng", text)
        self.assertLessEqual(th.threads_cost(text), th.MAX_COST)
        self.assertTrue(notes and notes[0].startswith("brain:"))

    def test_the_short_topic_is_what_the_motionstudio_grammar_renders(self):
        self.approve_monday()
        import generate_short_video as words
        import shorts_reel
        topic = words.script_for_date(MONDAY)
        self.assertEqual(topic["title"], "Three months' notice? Check the law.")
        hook, tips, disclaimer = shorts_reel.split_topic(topic)
        self.assertEqual(len(tips), 4)
        self.assertEqual(shorts_reel.split_hook(hook["text"]), ("THREE MONTHS' NOTICE?", "CHECK THE LAW."))
        self.assertIn("GENERAL INFO", disclaimer["text"])
        # a day without a pack is the rotation, exactly as before
        self.assertIn(words.script_for_date(date(2026, 10, 13)), words.VIDEO_SCRIPTS)

    def test_a_pack_for_another_day_or_an_unapproved_one_is_ignored(self):
        approved = self.approve_monday()
        self.assertIsNone(brain_drafts.draft_for(SUNDAY))
        approved["status"] = "draft"
        brain.write_draft(approved)
        self.assertIsNone(brain_drafts.draft_for(MONDAY))


class CardTests(Sandbox):
    def test_stat_checklist_and_plate_layouts_render(self):
        import social_card
        from PIL import Image
        out = Path(self.tmp.name) / "card.jpg"
        text = "Six months, not three\n\nRead the notice clause.\nCount the months.\nKeep the paper."
        r = social_card.render(text, out, kicker="DocOga · know your rights", layout="stat", big="6 MONTHS")
        self.assertEqual((r["layout"], r["plate"]), ("stat", False))
        self.assertGreater(out.stat().st_size, 8 * 1024)
        r = social_card.render(text, out, layout="checklist")
        self.assertEqual(r["layout"], "checklist")
        plate = Image.new("RGB", (1080, 1350), (90, 60, 30))
        r = social_card.render(text, out, layout="poster", background=plate)
        self.assertTrue(r["plate"])
        self.assertEqual(social_card._numbered("Read it.\nSign it."), "1. Read it.\n2. Sign it.")

    def test_the_card_for_post_takes_the_brief_and_plates_stay_off_in_tests(self):
        import social_card
        rel = social_card.card_for_post("Hello\n\nWorld", MONDAY.isoformat(), "educational", "facebook",
                                        out_dir=self.tmp.name,
                                        visual={"kicker": "state spotlight", "layout": "poster", "plate": "lagos dusk"})
        self.assertTrue(Path(rel).is_file())

    def test_the_plate_fetcher_filters_openverse_to_public_domain_and_never_raises(self):
        import brain_visual
        calls = []

        def http(url, accept="application/json"):
            calls.append(url)
            if "api.openverse.org" in url:
                self.assertIn("license=cc0%2Cpdm", url)
                return json.dumps({"results": [{"id": "1", "url": "https://x/face.jpg", "title": "woman portrait",
                                                "width": 2000, "height": 1500},
                                               {"id": "2", "url": "https://x/roof.jpg", "title": "rooftops",
                                                "width": 2000, "height": 1500}]}).encode(), "application/json"
            raise OSError("no network in tests")
        with patch.dict(os.environ, {"BRAIN_PLATES": "on", "BRAIN_PLATE_CACHE": self.tmp.name}):
            cands, _ = brain_visual.search("rooftops", http=http)
            self.assertEqual([c["id"] for c in cands], ["2"], "a face is filtered before download")
            self.assertIsNone(brain_visual.background_for("rooftops", (1080, 1350), http=http))


class DeepDiveWriterTests(Sandbox):
    def episode(self):
        facts = law_index.facts_for("lagos")
        fid = next(f for f in facts if "Yearly tenant" in f["text"])["id"]
        base = ("Show me the paper. In Lagos a yearly tenant is entitled to six months notice and the "
                "landlord who forgets that loses the case before it starts. ") * 1
        filler = " ".join(["Here is the part most people miss, and it decides who stays in the flat."] * 8)
        sections = []
        for n in range(1, 10):
            sections.append({"n": n, "title": "The Hook" if n == 1 else ("The Law, and DocOga" if n == 9 else "Section %d" % n),
                             "narration": base + filler})
        beats = []
        for n in range(1, 10):
            beats += [{"sec": n, "trig": None, "head": "SHOW ME THE PAPER", "sub": "six months, in writing", "img": "letter"},
                      {"sec": n, "trig": ["six", "months", "notice"], "head": "SIX MONTHS", "sub": "s.13(1)(e)", "img": "calendar"},
                      {"sec": n, "trig": ["loses", "the", "case"], "head": "LOSES THE CASE", "sub": "before it starts", "img": "court"},
                      {"sec": n, "trig": ["most", "people", "miss"], "head": "THE PART MISSED", "sub": "who stays", "img": "door"}]
        return {"title": "The Notice Ladder: Six Months Nobody Counts", "theme": "notice-ladder-lagos",
                "claims": [{"text": "a yearly tenant is entitled to six months notice", "fact_id": fid}],
                "sections": sections, "beats": beats,
                "cover": {"img": "calendar", "kicker": "Count the months", "line1": "Six months", "highlight": "six",
                          "label": "Notice ladder", "line2": "Nobody counts them", "line3": "The Lagos notice rule", "sub": "paper beats memory"},
                "youtube": {"title": "Notice to Quit in Lagos: The Six Months Nobody Counts (Deep-Dive 4)",
                            "description": "A yearly tenant in Lagos is owed six months notice under s.13(1)(e) of the Tenancy Law 2011. "
                                           "This Deep-Dive walks the ladder from tenant at will to yearly tenant, the anniversary exception, "
                                           "and what to do when the notice is short. Make yours in two minutes at https://docoga.com.ng "
                                           "General information, not legal advice.",
                            "tags": ["DocOga", "notice to quit", "Lagos", "tenancy law", "tenant rights", "landlord", "Nigeria", "rent"]}}

    def test_a_well_formed_episode_passes_and_a_misordered_trigger_fails(self):
        facts_by_id = law_index.by_id(law_index.facts_for("lagos"))
        ep = self.episode()
        self.assertEqual(brain.deepdive_problems(ep, facts_by_id), [])
        ep["beats"][1], ep["beats"][2] = ep["beats"][2], ep["beats"][1]
        problems = brain.deepdive_problems(ep, facts_by_id)
        self.assertTrue(any("not found in section 1" in p for p in problems), problems)

    def test_the_episode_is_written_in_the_engines_shape_queued_and_checked_by_the_engine(self):
        import shutil
        episodes = Path(self.tmp.name) / "episodes"
        (episodes / "assets").mkdir(parents=True)
        for name in ("letter", "calendar", "court", "door"):
            shutil.copy(ROOT / "episodes" / "assets" / (name + ".jpg"), episodes / "assets" / (name + ".jpg"))
        shutil.copytree(ROOT / "episodes" / "dd3", episodes / "dd3")
        (episodes / "queue.json").write_text(json.dumps({"queue": ["dd3"]}))
        with patch.object(brain, "EPISODES", episodes):
            self.assertEqual(brain.next_episode_number(), 4)
            template = brain.existing_episodes()[-1]
            folder = brain.write_episode(self.episode(), 4, template)
            meta = json.loads((folder / "episode.json").read_text())
            self.assertEqual(meta["voice"], template["voice"], "the locked voice is copied byte for byte")
            self.assertEqual(meta["kicker"], "DOCOGA — DEEP-DIVE · EPISODE 4")
            self.assertEqual(len(meta["sections"]), 9)
            self.assertEqual(json.loads((episodes / "queue.json").read_text())["queue"], ["dd3", "dd4"])
            script = (folder / "script.txt").read_text()
            self.assertEqual(script.count("--- C"), 9)
            import deepdive
            with patch.object(deepdive, "EPISODES", episodes):
                self.assertEqual(deepdive.check_triggers(deepdive.Episode("dd4"), verbose=False), [])

    def test_the_writer_runs_generation_verification_and_writes_only_on_agreement(self):
        import shutil
        episodes = Path(self.tmp.name) / "episodes"
        (episodes / "assets").mkdir(parents=True)
        for name in ("letter", "calendar", "court", "door"):
            shutil.copy(ROOT / "episodes" / "assets" / (name + ".jpg"), episodes / "assets" / (name + ".jpg"))
        shutil.copytree(ROOT / "episodes" / "dd3", episodes / "dd3")
        (episodes / "queue.json").write_text(json.dumps({"queue": ["dd3"]}))
        ep = self.episode()
        verdict = {"verdicts": [{"fact_id": ep["claims"][0]["fact_id"], "supported": True}], "unsupported_statements": []}
        fake = FakeGemini([ep, verdict])
        with patch.object(brain, "EPISODES", episodes), patch.object(brain, "engine_check", return_value=[]):
            with redirect_stdout(self.out):
                out, problems = brain.deepdive_draft(http=fake, sleep=lambda s: None, log=print, states=["lagos"])
        self.assertEqual(problems, [])
        self.assertTrue((episodes / "dd4" / "episode.json").is_file())
        self.assertIn("PLATES AVAILABLE", fake.prompts[0])
        self.assertIn("THE EPISODE NARRATION", fake.prompts[1])


class WorkflowContractTests(unittest.TestCase):
    def setUp(self):
        self.wf = (ROOT / ".github" / "workflows" / "brain.yml").read_text(encoding="utf-8")

    def test_it_is_scheduled_before_the_lanes_and_commits_only_its_own_files(self):
        self.assertIn("cron: '30 0 * * *'", self.wf)
        self.assertIn("contents: write", self.wf)
        self.assertIn("issues: write", self.wf)
        self.assertIn("cancel-in-progress: false", self.wf)
        self.assertIn("git add -A brain/drafts brain/feedback.md brain/newsdesk.json brain/listening.json brain/answers logs/brain_said.json episodes site/guides site/sitemap.xml", self.wf)
        self.assertIn("gh issue create", self.wf)
        self.assertIn("brain-automation", self.wf)

    def test_inputs_reach_the_shell_through_env_only(self):
        leaked = [ln for ln in self.wf.splitlines() if "${{ inputs." in ln and not ln.strip().startswith("#")
                  and not ln.strip().split(":")[0].replace("_", "").isalpha()]
        self.assertEqual(leaked, [])

    def test_quota_is_a_pause_not_a_failure(self):
        self.assertIn('[ "$CODE" != "6" ]', self.wf)
        self.assertIn("does not open this issue", self.wf)

    def test_the_posting_lanes_install_numpy_for_the_plates_and_instagram_passes_the_brief(self):
        for name in ("instagram_autopost.yml", "facebook_autopost.yml", "telegram_autopost.yml"):
            self.assertIn("numpy", (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"), name)
        ig = (ROOT / ".github" / "workflows" / "instagram_autopost.yml").read_text(encoding="utf-8")
        self.assertEqual(ig.count('--brief "$DAY"'), 3, "the card, the Story and the carousel slides all read the brief")



class SearchDemandTests(unittest.TestCase):
    """17 Oct 2026: Google's own queries, in the prompt, when the pull is fresh."""

    def test_striking_distance_queries_lead_and_a_stale_pull_is_silence(self):
        import json
        import tempfile
        from datetime import datetime, timedelta, timezone
        sys.path.insert(0, str(ROOT / "tools"))
        import brain
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sc.json"
            fresh = datetime.now(timezone.utc).isoformat(timespec="seconds")
            p.write_text(json.dumps({"taken_at": fresh,
                                     "top_queries": [{"query": "tenancy agreement sample nigeria", "clicks": 60, "impressions": 2000, "position": 4.2, "page": "https://docoga.com.ng/tenancy-agreement-nigeria.html"}],
                                     "striking_distance": [{"query": "notice to quit lagos", "clicks": 3, "impressions": 800, "position": 9.1, "page": "https://docoga.com.ng/notice-to-quit-lagos.html"}]}))
            rows = brain.search_demand(p)
            self.assertEqual([r["query"] for r in rows], ["notice to quit lagos", "tenancy agreement sample nigeria"])
            block = brain.search_block(rows)
            self.assertIn('"notice to quit lagos" — almost page one, position 9.1', block)
            self.assertIn("→ /notice-to-quit-lagos.html", block)
            stale = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat(timespec="seconds")
            p.write_text(json.dumps({"taken_at": stale, "top_queries": [{"query": "x", "clicks": 1}]}))
            self.assertEqual(brain.search_demand(p), [])
            self.assertIn("no Search Console pull yet", brain.search_block([]))


class LinkTagTests(unittest.TestCase):
    """17 Oct 2026: every link we post says which channel it came from (?s=tg|fb|…) so the worker's
    checkout/sale counters can tell the brain which channel moves money."""

    def test_links_carry_the_channel_tag_once_and_only_ours(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import brain_drafts as bd
        text = "Start here: https://docoga.com.ng/rent-receipt-lagos.html and https://docoga.com.ng — not https://lagos.gov.ng/x"
        out = bd.tag_links(text, "telegram")
        self.assertIn("https://docoga.com.ng/rent-receipt-lagos.html?s=tg", out)
        self.assertIn("https://docoga.com.ng/?s=tg", out, "the bare domain gets a slash so the query parses")
        self.assertIn("https://lagos.gov.ng/x", out)
        self.assertEqual(bd.tag_links(out, "telegram"), out, "tagging twice adds nothing")
        self.assertEqual(bd.tag_links("https://docoga.com.ng/x.html?utm=1", "facebook"), "https://docoga.com.ng/x.html?utm=1")
        self.assertEqual(bd.tag_links(text, "unknown-channel"), text)
        for channel, tag in (("facebook", "fb"), ("instagram", "ig"), ("threads", "th"), ("linkedin", "li"), ("youtube", "yt"), ("tiktok", "tt")):
            self.assertIn("?s=%s" % tag, bd.tag_links("https://docoga.com.ng/a.html", channel))

    def test_pre_escaped_telegram_templates_are_tagged_without_breaking_markdownv2(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import brain_drafts as bd
        out = bd.tag_links_mdv2("👉 Try am: https://docoga\\.com\\.ng\n\nRead https://docoga\\.com\\.ng/notice\\-to\\-quit\\.html\\. Now")
        self.assertEqual(out, "👉 Try am: https://docoga\\.com\\.ng/?s\\=tg\n\nRead https://docoga\\.com\\.ng/notice\\-to\\-quit\\.html?s\\=tg\\. Now")
        import telegram_mdv2
        self.assertEqual(telegram_mdv2.escape("https://docoga.com.ng/?s=tg"), "https://docoga\\.com\\.ng/?s\\=tg", "`=` is reserved, `?` is not")

if __name__ == "__main__":
    unittest.main()
