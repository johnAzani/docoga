"""tools/brain_scorecard.py — the Monday numbers, graded against brain/goals.json.

Why these tests exist: the scorecard is what turns "I want to see the channels
growing and my bank account getting fat" into something the editor is held to.
A scorecard that silently reads zero, grades against itself, or crashes on one
missing token would feed the brain wrong orders every week. So: a fake Graph /
Threads / Telegram / worker answers every call, and the tests check what is
measured, what is graded, what is ordered, and what happens when a source is
missing or refuses.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import brain_scorecard as sc  # noqa: E402

NOW = datetime(2026, 10, 19, 5, 40, tzinfo=timezone.utc)   # a Monday


def series(name, values):
    return {"name": name, "period": "day", "values": [{"value": v} for v in values]}


def total(name, value):
    return {"name": name, "period": "day", "total_value": {"value": value}}


class FakeNet:
    """Routes by substring of the URL (+ method). Records every call."""

    def __init__(self, routes, fail=()):
        self.routes = routes
        self.fail = set(fail)
        self.calls = []

    def __call__(self, method, url, params=None, body=None, headers=None, timeout=30):
        self.calls.append((method, url, dict(params or {}), body))
        for key in self.fail:
            if key in url:
                return 400, {"error": {"message": "(#100) %s is not valid" % key, "code": 100}}
        for key, reply in self.routes:
            if key in url and (not isinstance(reply, tuple) or reply[0] == method):
                return (200, reply[1]) if isinstance(reply, tuple) else (200, reply)
        return 404, {"error": {"message": "no route for " + url, "code": 404}}


def full_routes():
    fb_posts = {"data": [
        {"id": "P1", "created_time": "2026-10-15T08:31:00+0000", "message": "Pay the wrong agent. Lose the flat.",
         "shares": {"count": 12}, "comments": {"summary": {"total_count": 5}}, "reactions": {"summary": {"total_count": 40}}},
        {"id": "P2", "created_time": "2026-10-16T18:40:00+0000", "message": "Which state are you renting in?",
         "shares": {"count": 2}, "comments": {"summary": {"total_count": 9}}, "reactions": {"summary": {"total_count": 20}}},
    ]}
    ig_media = {"data": [
        {"id": "M1", "caption": "Six months, not three", "timestamp": "2026-10-15T18:10:00+0000", "media_type": "IMAGE",
         "like_count": 30, "comments_count": 3},
        {"id": "M2", "caption": "old one", "timestamp": "2026-09-01T18:10:00+0000", "media_type": "IMAGE",
         "like_count": 300, "comments_count": 30},
    ]}
    th_posts = {"data": [
        {"id": "T1", "text": "Did your last receipt carry a date?", "timestamp": "2026-10-16T12:10:00+0000"},
    ]}
    return [
        ("/102466208923830/insights", {"data": [series("page_total_media_view_unique", [100, 120, 90, 80, 110, 130, 70]),
                                               series("page_post_engagements", [10, 12, 9, 8, 11, 13, 7]),
                                               series("page_daily_follows_unique", [1, 0, 2, 1, 0, 3, 1]),
                                               series("page_video_views", [50, 60, 0, 0, 70, 0, 0])]}),
        ("/102466208923830/posts", fb_posts),
        ("/102466208923830", {"followers_count": 410, "name": "DocOga"}),
        ("/P1/insights", {"data": [series("post_clicks", [8]), series("post_media_view", [600])]}),
        ("/P2/insights", {"data": [series("post_clicks", [3]), series("post_media_view", [400])]}),
        ("graph.instagram.com/v26.0/me/insights", {"data": [total("views", 900), total("reach", 700), total("accounts_engaged", 60),
                                                             total("total_interactions", 80),
                                                             {"name": "online_followers", "period": "lifetime",
                                                              "values": [{"value": {"18": 40, "19": 55, "20": 50, "8": 10}}]}]}),
        ("graph.instagram.com/v26.0/me/media", ig_media),
        ("graph.instagram.com/v26.0/me", {"followers_count": 120, "media_count": 40, "username": "docoga.ng"}),
        ("/M1/insights", {"data": [total("views", 500), total("reach", 400), total("saved", 6), total("shares", 4)]}),
        ("/me/threads_insights", {"data": [series("views", [50, 60, 70, 40, 30, 80, 90]), total("likes", 30), total("replies", 12),
                                           total("reposts", 3), total("quotes", 1), total("followers_count", 85)]}),
        ("/me/threads?", th_posts), ("/me/threads", th_posts),
        ("/T1/insights", {"data": [total("views", 300), total("likes", 20), total("replies", 7), total("reposts", 2),
                                   total("quotes", 0), total("shares", 1)]}),
        ("api.telegram.org", {"ok": True, "result": 230}),
        ("/admin/login", ("POST", {"ok": True, "token": "sid.sig"})),
        ("/admin/logout", ("POST", {"ok": True})),
        ("/admin/data", {"ok": True, "date": "2026-10-19", "priceNGN": 2000,
                         "today": {"sold": 1, "rev": 2000, "offline": 0, "manual": 0, "bizpaid": 0, "bizrev": 0},
                         "snapshot": {"series": [{"date": (NOW - timedelta(days=i)).strftime("%Y-%m-%d"),
                                                  "sold": 1 if i % 3 == 0 else 0, "rev": 2000 if i % 3 == 0 else 0,
                                                  "offline": 0, "manual": 0, "bizpaid": 0, "bizrev": 0}
                                                 for i in range(1, 31)]}}),
    ]


ENV = {"FB_PAGE_ACCESS_TOKEN": "pt", "FB_PAGE_ID": "102466208923830", "IG_ACCESS_TOKEN": "igt",
       "THREADS_ACCESS_TOKEN": "tht", "TELEGRAM_BOT_TOKEN": "8852331279:x", "TELEGRAM_CHAT_ID": "@docogadaily",
       "DOCOGA_ADMIN_PASSPHRASE": "open-sesame", "DOCOGA_WORKER_URL": "https://docoga-pass.example.workers.dev"}


class PullTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stats = Path(self.tmp.name) / "yt.json"
        self.stats.write_text(json.dumps([{"taken_at": "2026-10-19T05:00:00", "channel": {"subscribers": 62, "views": 300, "videos": 14},
                                           "videos": [{"kind": "short", "topic": "Change the lock. Become the defendant.", "views": 120},
                                                      {"kind": "longform", "title": "DD3", "views": 5}]}]), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, routes=None, env=None, history=None, fail=()):
        net = FakeNet(routes or full_routes(), fail=fail)
        snap = sc.build(http=net, env=ENV if env is None else env, now=NOW, history=history or [],
                        goals=sc.load_goals(), stats_path=self.stats, said={})
        return snap, net

    def test_every_channel_is_measured_from_the_2026_metric_names(self):
        snap, net = self.build()
        k = snap["kpis"]
        self.assertEqual(k["facebook.followers"], 410)
        self.assertEqual(k["facebook.views_7d"], 700)
        self.assertEqual(k["facebook.follows_7d"], 8)
        self.assertEqual(k["facebook.posts_14d"], 2)
        self.assertAlmostEqual(k["facebook.share_rate"], 14 / 1000, places=4)
        self.assertEqual(k["facebook.comments_per_post"], 7.0)
        self.assertEqual(k["instagram.followers"], 120)
        self.assertEqual(k["instagram.reach_7d"], 700)
        self.assertEqual(k["instagram.posts_14d"], 1, "a post older than 14 days is not in the fortnight")
        self.assertAlmostEqual(k["instagram.send_rate"], 10 / 400, places=4)
        self.assertEqual(k["instagram.online_peak_hours_wat"], [20, 21, 19], "UTC hours become WAT (+1)")
        self.assertEqual(k["threads.followers"], 85)
        self.assertEqual(k["threads.views_7d"], 420)
        self.assertEqual(k["threads.replies_per_post"], 7.0)
        self.assertEqual(k["telegram.members"], 230)
        self.assertEqual(k["youtube.subscribers"], 62)
        self.assertEqual(k["sales.passes"], 1 + 2, "today + the two sold days in the last six")
        self.assertEqual(k["sales.revenue"], 6000)
        self.assertEqual(snap["problems"], [])
        # the metrics asked for are the ones that survive the Nov-2025/Jun-2026 deprecations
        asked = " ".join(c[2].get("metric", "") for c in net.calls)
        self.assertNotIn("page_impressions", asked)
        self.assertNotIn("page_fans", asked)
        self.assertIn("page_total_media_view_unique", asked)
        self.assertIn("post_media_view", asked)

    def test_posting_hour_is_recorded_in_lagos_time_and_ranked(self):
        snap, _ = self.build()
        posts = snap["channels"]["facebook"]["posts"]
        self.assertEqual([p["hour_wat"] for p in posts], [9, 19])
        self.assertEqual(posts[0]["weekday"], "Thu")
        by_hour = snap["kpis"]["facebook.by_hour"]
        self.assertIn("9", by_hour)
        self.assertIn("19", by_hour)
        best = snap["kpis"]["facebook.best_posts"][0]
        self.assertTrue(best["text"].startswith("Pay the wrong agent"))

    def test_a_missing_token_is_a_line_not_a_crash(self):
        env = {k: v for k, v in ENV.items() if not k.startswith(("FB_", "DOCOGA_ADMIN"))}
        snap, _ = self.build(env=env)
        self.assertIsNone(snap["channels"]["facebook"])
        self.assertIsNone(snap["channels"]["sales"])
        self.assertTrue(any("facebook" in p for p in snap["problems"]))
        self.assertTrue(any("DOCOGA_ADMIN_PASSPHRASE" in p for p in snap["problems"]))
        self.assertEqual(snap["kpis"]["telegram.members"], 230, "the other channels are still measured")

    def test_an_invalid_page_metric_falls_back_to_one_metric_at_a_time(self):
        routes = full_routes()
        # the combined call fails; the per-metric calls succeed except video views
        combined_fail = FakeNet(routes)
        calls = {"n": 0}

        def http(method, url, params=None, body=None, headers=None, timeout=30):
            if "/102466208923830/insights" in url:
                calls["n"] += 1
                metric = (params or {}).get("metric", "")
                if "," in metric:
                    return 400, {"error": {"message": "(#100) invalid metric", "code": 100}}
                if metric == "page_video_views":
                    return 400, {"error": {"message": "(#100) page_video_views is deprecated", "code": 100}}
            return combined_fail(method, url, params, body, headers, timeout)
        snap = sc.build(http=http, env=ENV, now=NOW, history=[], goals=sc.load_goals(), stats_path=self.stats)
        self.assertEqual(snap["kpis"]["facebook.views_7d"], 700)
        self.assertIsNone(snap["channels"]["facebook"]["video_views_7d"])
        self.assertTrue(any("page_video_views" in p for p in snap["problems"]))
        self.assertEqual(calls["n"], 5, "one combined try, then four singles")

    def test_an_insights_scope_the_token_lacks_is_named_so_the_owner_can_grant_it(self):
        snap, _ = self.build(fail=("me/threads_insights",))
        self.assertTrue(any("threads_manage_insights" in p for p in snap["problems"]))
        self.assertEqual(snap["kpis"]["threads.replies_per_post"], 7.0, "per-post insights still measured")

    def test_the_dashboard_session_is_opened_read_and_closed(self):
        snap, net = self.build()
        paths = [c[1].split("workers.dev")[-1] for c in net.calls if "workers.dev" in c[1]]
        self.assertEqual(paths, ["/admin/login", "/admin/data", "/admin/logout"])
        login = next(c for c in net.calls if c[1].endswith("/admin/login"))
        self.assertEqual(login[3], {"pass": "open-sesame"})
        self.assertEqual(snap["channels"]["sales"]["passes_28d"], 1 + 9)


class LearningTests(unittest.TestCase):
    """The brain is measured against its own choices and against the rotation it replaced."""

    def channels(self):
        return {"facebook": {"posts": [
            {"at": "2026-10-15T08:31:00+0000", "shares": 12, "comments": 5, "reactions": 40},   # Thu 15 → STAKES/ngozi
            {"at": "2026-10-16T08:31:00+0000", "shares": 1, "comments": 1, "reactions": 10},    # Fri 16 → QUESTION/okafor
            {"at": "2026-10-17T08:31:00+0000", "shares": 9, "comments": 4, "reactions": 30},    # Sat 17 → STAKES/ngozi
            {"at": "2026-10-18T08:31:00+0000", "shares": 0, "comments": 2, "reactions": 8},     # Sun 18 → QUESTION/okafor
            {"at": "2026-10-13T23:30:00+0000", "shares": 2, "comments": 0, "reactions": 5},     # 00:30 WAT on the 14th → rotation
        ]}}

    def said(self):
        return {"2026-10-15": {"hook_type": "STAKES", "post_type": "story", "reader": "ngozi"},
                "2026-10-16": {"hook_type": "QUESTION", "post_type": "promo", "reader": "okafor"},
                "2026-10-17": {"hook_type": "STAKES", "post_type": "checklist", "reader": "ngozi"},
                "2026-10-18": {"hook_type": "QUESTION", "post_type": "engagement", "reader": "okafor"}}

    def test_posts_are_joined_to_the_pack_of_their_lagos_date(self):
        learn = sc.learning(self.channels(), self.said())
        self.assertEqual(learn["hook_type"]["STAKES"]["n"], 2)
        self.assertEqual(learn["hook_type"]["STAKES"]["avg"], (86 + 65) / 2)
        self.assertEqual(learn["hook_type"]["QUESTION"]["avg"], (15 + 12) / 2)
        self.assertEqual(learn["source"]["rotation"]["n"], 1, "23:30 UTC on the 13th is the 14th in Lagos — no pack, so rotation")
        self.assertEqual(learn["reader"]["ngozi"]["n"], 2)

    def test_orders_name_the_hook_and_reader_that_earned_the_most(self):
        k = {"learning": sc.learning(self.channels(), self.said())}
        text = "\n".join(sc.orders(k, []))
        self.assertIn("use STAKES on two of the four cited days", text)
        self.assertIn("rest QUESTION", text)
        self.assertIn("write to Ngozi again", text)

    def test_one_post_per_hook_is_not_evidence(self):
        ch = {"facebook": {"posts": [{"at": "2026-10-15T08:31:00+0000", "shares": 12},
                                     {"at": "2026-10-16T08:31:00+0000", "shares": 0}]}}
        text = "\n".join(sc.orders({"learning": sc.learning(ch, self.said())}, []))
        self.assertNotIn("Hooks, by what they earned", text, "n=1 per hook says nothing; the order waits for two")


class GradeTests(unittest.TestCase):
    goals = sc.load_goals()

    def test_first_week_has_no_baseline_and_says_so(self):
        rows = sc.grade({"telegram.members": 230, "threads.replies_per_post": 7.0}, None, self.goals)
        by = {r["key"]: r for r in rows}
        self.assertEqual(by["telegram.members"]["status"], "no_baseline")
        self.assertEqual(by["threads.replies_per_post"]["status"], "on_track")
        self.assertEqual(by["facebook.followers"]["status"], "not_measured")

    def test_growth_goals_grade_against_last_week(self):
        prev = {"kpis": {"telegram.members": 200, "facebook.followers": 400, "youtube.subscribers": 49, "sales.passes": 2}}
        rows = sc.grade({"telegram.members": 230, "facebook.followers": 410, "youtube.subscribers": 62, "sales.passes": 2}, prev, self.goals)
        by = {r["key"]: r for r in rows}
        self.assertEqual(by["telegram.members"]["status"], "on_track", "200 → 230 is +15%, above +9%")
        self.assertEqual(by["facebook.followers"]["status"], "behind", "400 → 410 is +2.5%, below +5.5%")
        self.assertEqual(by["youtube.subscribers"]["status"], "on_track", "+13 exactly")
        self.assertEqual(by["sales.passes"]["status"], "behind", "2 → 2 is not +1")
        self.assertEqual(by["sales.passes"]["target"], 3.0)

    def test_the_previous_week_is_never_today(self):
        history = [{"taken_at": (NOW - timedelta(days=7)).isoformat(), "kpis": {"telegram.members": 200}},
                   {"taken_at": (NOW - timedelta(hours=2)).isoformat(), "kpis": {"telegram.members": 999}}]
        prev = sc.previous_week(history, NOW)
        self.assertEqual(prev["kpis"]["telegram.members"], 200, "a re-run this morning must not grade against itself")

    def test_orders_follow_the_strategy_rules(self):
        k = {"facebook.share_rate": 0.002, "threads.replies_per_post": 0.5, "sales.passes": 1, "facebook.followers": 500,
             "instagram.online_peak_hours_wat": [20, 21, 19]}
        grades = [{"key": "facebook.share_rate", "status": "behind"}, {"key": "threads.replies_per_post", "status": "behind"},
                  {"key": "sales.passes", "status": "behind"}, {"key": "facebook.followers", "status": "on_track"}]
        text = "\n".join(sc.orders(k, grades))
        self.assertIn("STAKES", text)
        self.assertIn("ends with a question", text)
        self.assertIn("payday window", text, "sales behind while reach grows → promo moves to payday")
        self.assertIn("20:00, 21:00, 19:00 WAT", text)
        self.assertNotIn("Every measured goal is on track", text)

    def test_all_green_means_do_not_touch_the_mix(self):
        text = "\n".join(sc.orders({}, [{"key": "telegram.members", "status": "on_track"}]))
        self.assertIn("do not change the mix", text)

    def test_two_weeks_behind_escalates(self):
        history = [{"grades": [{"key": "telegram.members", "status": "behind"}]}]
        grades = [{"key": "telegram.members", "status": "behind"}]
        strk = sc.streaks(history, grades)
        self.assertEqual(strk["telegram.members"], 2)
        text = "\n".join(sc.orders({}, grades, strk))
        self.assertIn("two weeks running", text)


class LedgerTests(unittest.TestCase):
    def test_pull_appends_and_summary_reads_back(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "scorecard.json"
            old_ledger, old_env = sc.LEDGER, dict(os.environ)
            sc.LEDGER = ledger
            try:
                os.environ.update({k: "" for k in ENV})   # nothing configured → nothing measured but YouTube
                sc._http = FakeNet([])   # no network in a test, ever
                code = sc.main(["pull"])
                self.assertEqual(code, 0, "YouTube stats alone count as measured")
                history = json.loads(ledger.read_text(encoding="utf-8"))
                self.assertEqual(len(history), 1)
                self.assertIn("orders", history[0])
                text = sc.feedback_section(history)
                self.assertIn("Scorecard", text)
                self.assertIn("not connected", text, "revenue line tells the owner the one secret that connects it")
                self.assertIn("Not measured (and why)", text)
            finally:
                sc.LEDGER = old_ledger
                os.environ.clear()
                os.environ.update(old_env)

    def test_summary_is_the_block_the_brain_reads(self):
        snap = {"taken_at": NOW.isoformat(), "week": "2026-W43", "channels": {"sales": {"passes_7d": 4, "revenue_7d": 8000, "passes_28d": 9, "revenue_28d": 18000}},
                "kpis": {"facebook.followers": 410, "threads.replies_per_post": 7.0}, "orders": ["Keep going."],
                "grades": [{"key": "sales.passes", "label": "Oga Pass sales per week", "actual": 4, "target": 3.0, "status": "on_track"}],
                "problems": []}
        text = sc.summary_md(snap)
        self.assertIn("4 passes / ₦8,000", text)
        self.assertIn("| Oga Pass sales per week | 4 | 3.0 | ✅ |", text)
        self.assertIn("- Keep going.", text)


class WorkflowContractTests(unittest.TestCase):
    def test_the_monday_lane_reads_only_and_commits_the_ledger(self):
        import yaml
        text = (ROOT / ".github" / "workflows" / "brain_scorecard.yml").read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        on = doc[True] if True in doc else doc["on"]
        self.assertEqual(on["schedule"][0]["cron"], "40 5 * * 1", "after youtube_stats (05:00 UTC Monday)")
        self.assertEqual(doc["permissions"], {"contents": "write", "issues": "write"},
                         "issues: write is for the ONE living '📊 Weekly scorecard' issue, never a new issue per week")
        text = (ROOT / ".github" / "workflows" / "brain_scorecard.yml").read_text(encoding="utf-8")
        self.assertIn("--label brain-scorecard", text)
        self.assertIn("gh issue edit", text, "an existing scorecard issue is updated in place")
        self.assertIn("gh issue comment", text, "and commented, so the owner's phone gets one notification a week")
        steps = " ".join(s.get("run", "") for s in doc["jobs"]["measure"]["steps"])
        self.assertIn("brain_scorecard.py pull", steps)
        self.assertIn("brain.py feedback", steps)
        self.assertIn("logs/scorecard.json brain/feedback.md", steps)
        self.assertNotIn("post_facebook", steps)
        self.assertIn("DOCOGA_ADMIN_PASSPHRASE", text)

    def test_the_brain_prompt_carries_strategy_audience_and_orders(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import brain
        from datetime import date
        ctx = brain.day_context(date(2026, 10, 27), said=[])
        prompt = brain.prompt_for(ctx)
        self.assertIn("STRATEGY — THE PLAN YOU ARE HELD TO", prompt)
        self.assertIn("Oga Pass", prompt)
        self.assertIn("AUDIENCE — WRITE TO ONE OF THESE FIVE", prompt)
        self.assertIn("Ngozi", prompt)
        self.assertIn("ORDERS", prompt)
        self.assertIn("Payday window", prompt, "the 27th is inside the payday window")
        self.assertIn('"cta"', prompt)
        self.assertIn("ENDS WITH A QUESTION", prompt)


if __name__ == "__main__":
    unittest.main()
