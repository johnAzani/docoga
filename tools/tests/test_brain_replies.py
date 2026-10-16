"""tools/brain_replies.py — the community manager answers from the facts, within the gates,
and names the exact permission when a token cannot."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("GEMINI_QUOTA_LEDGER", os.path.join(tempfile.gettempdir(), "docoga-test-quota.json"))

import brain_replies as br  # noqa: E402
import gemini_text  # noqa: E402

NOW = datetime(2026, 10, 17, 10, 40, tzinfo=timezone.utc)
ENV = {"THREADS_ACCESS_TOKEN": "t-threads", "IG_ACCESS_TOKEN": "t-ig", "FB_PAGE_ACCESS_TOKEN": "t-fb", "FB_PAGE_ID": "102466208923830"}

PACKS = {"2026-10-17": {"date": "2026-10-17", "state": "lagos", "reader": "ngozi", "tool": "notice-to-quit", "hook_type": "STAKES",
                        "claims": [{"text": "yearly tenancy: six months' notice", "fact_id": "lagos:notice_ladder:5"}]}}


class FakeNet:
    """Routes by (method, substring). Records every POST so tests can see what went out."""

    def __init__(self, routes):
        self.routes, self.posts = routes, []

    def __call__(self, method, url, params=None, data=None, timeout=30):
        if method == "POST":
            self.posts.append((url, dict(data or params or {})))
        for (m, needle), resp in self.routes:
            if m == method and needle in url:
                return resp() if callable(resp) else resp
        return 404, {"error": {"message": "no route for %s %s" % (method, url), "code": 803}}


def gemini(replies):
    """A Gemini that answers with the given list for whatever it is asked; records the prompt."""
    seen = []

    def http(url, payload, timeout=120):
        seen.append(payload["contents"][0]["parts"][0]["text"])
        body = {"candidates": [{"content": {"parts": [{"text": json.dumps({"replies": replies})}]}}]}
        return 200, json.dumps(body)
    http.seen = seen
    return http


def threads_routes(replies=None, reply_status=200):
    replies = replies if replies is not None else [
        {"id": "r1", "text": "Abeg how many months notice for yearly rent in Lagos?", "username": "tunde_o", "timestamp": "2026-10-17T12:30:00+0000"},
        {"id": "r2", "text": "🔥🔥🔥", "username": "amaka", "timestamp": "2026-10-17T12:31:00+0000"},
        {"id": "r3", "text": "this is my own reply", "username": "docoga", "timestamp": "2026-10-17T12:32:00+0000", "is_reply_owned_by_me": True},
        {"id": "r4", "text": "una be scam, mumu people", "username": "troll", "timestamp": "2026-10-17T12:33:00+0000"},
    ]
    return [
        (("GET", "/me/threads"), (200, {"data": [{"id": "p1", "text": "Yearly tenant in Lagos? Six months' notice — s.13(1)(e).", "timestamp": "2026-10-17T12:10:00+0000"},
                                                  {"id": "old", "text": "ancient", "timestamp": "2026-10-01T12:10:00+0000"}]})),
        (("GET", "/p1/replies"), (reply_status, {"data": replies} if reply_status == 200 else
                                  {"error": {"message": "(#10) Application does not have permission for this action", "code": 10}})),
        (("GET", "/r1/replies"), (200, {"data": []})),
        (("POST", "/me/threads_publish"), (200, {"id": "pub-1"})),
        (("POST", "/me/threads"), (200, {"id": "container-1"})),
    ]


class CollectTests(unittest.TestCase):
    def test_only_real_questions_from_other_people_are_queued(self):
        net = FakeNet(threads_routes())
        pf = br.Threads(net, ENV, NOW, lambda *_: None)
        pending, skipped = br.collect([pf], [], lambda *_: None)
        self.assertEqual([c["comment_id"] for c in pending], ["r1"], "emoji-only, our own, and abuse are not conversations")
        self.assertEqual(skipped["empty_or_abuse"], 2)
        self.assertEqual(pf.capability, "ok")

    def test_a_comment_in_the_ledger_is_never_answered_twice(self):
        net = FakeNet(threads_routes())
        pf = br.Threads(net, ENV, NOW, lambda *_: None)
        pending, _ = br.collect([pf], [{"platform": "threads", "comment_id": "r1"}], lambda *_: None)
        self.assertEqual(pending, [])

    def test_posts_older_than_the_lookback_are_not_read(self):
        net = FakeNet(threads_routes())
        br.collect([br.Threads(net, ENV, NOW, lambda *_: None)], [], lambda *_: None)
        self.assertFalse(any("/old/replies" in u for u, _ in net.posts))

    def test_missing_read_permission_names_the_scope_and_does_not_crash(self):
        logs = []
        net = FakeNet(threads_routes(reply_status=400))
        pf = br.Threads(net, ENV, NOW, logs.append)
        pending, _ = br.collect([pf], [], logs.append)
        self.assertEqual(pending, [])
        self.assertEqual(pf.capability, "missing: threads_read_replies")
        self.assertTrue(any("threads_read_replies" in l for l in logs))

    def test_no_token_means_skipped_not_failed(self):
        pf = br.Facebook(FakeNet([]), {}, NOW, lambda *_: None)
        pending, _ = br.collect([pf], [], lambda *_: None)
        self.assertEqual((pending, pf.capability), ([], "no token"))


class LintTests(unittest.TestCase):
    ctx = {"state": "lagos", "facts": [{"id": "lagos-notice-yearly", "cite": "s.13(1)(e)", "text": "A yearly tenant gets six months' notice."}]}

    def test_a_good_reply_passes(self):
        self.assertEqual(br.lint_reply("For a yearly tenancy in Lagos it is six months' written notice — s.13(1)(e). "
                                       "Make the notice here: https://docoga.com.ng/notice-to-quit-lagos.html", self.ctx), [])

    def test_the_gates(self):
        self.assertTrue(any("not on the shelf" in p for p in br.lint_reply("Section 47 says six months.", self.ctx)))
        self.assertTrue(any("not ours" in p for p in br.lint_reply("It costs ₦5,000 at the court.", self.ctx)))
        self.assertEqual(br.lint_reply("The Oga Pass is ₦2,000 a year.", self.ctx), [])
        self.assertTrue(any("forbidden" in p for p in br.lint_reply("Stop paying rent until he fixes it.", self.ctx)))
        self.assertTrue(any("forbidden" in p for p in br.lint_reply("Take him to court, you will win.", self.ctx)))
        self.assertTrue(any("link" in p for p in br.lint_reply("See https://example.com/notice", self.ctx)))
        self.assertTrue(any("banned" in p for p in br.lint_reply("As an AI I cannot say.", self.ctx)))
        self.assertTrue(any("characters" in p for p in br.lint_reply("x" * 281, self.ctx)))
        self.assertEqual(br.lint_reply("", self.ctx), ["empty"])


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "replied.json"
        self._old = br.LEDGER
        br.LEDGER = self.ledger

    def tearDown(self):
        br.LEDGER = self._old
        self.tmp.cleanup()

    def run_threads(self, replies, dry_run=False, routes=None):
        net = FakeNet(routes or threads_routes())
        g = gemini(replies)
        result = br.run(http=net, gemini_http=g, env=ENV, now=NOW, dry_run=dry_run, only="threads",
                        log=lambda *_: None, sleep=lambda *_: None, ledger=[], packs=PACKS)
        return net, g, result

    def test_a_question_gets_a_cited_answer_published_as_a_threads_reply(self):
        text = "Yearly tenancy in Lagos: six months' written notice — s.13(1)(e). Draft it here: https://docoga.com.ng/notice-to-quit-lagos.html"
        net, g, result = self.run_threads([{"n": 1, "comment_id": "r1", "skip": False, "text": text, "why": "asked the rule"}])
        self.assertEqual((result["answered"], result["refused"]), (1, 0))
        create = next(d for u, d in net.posts if u.endswith("/me/threads"))
        self.assertEqual((create["media_type"], create["reply_to_id"], create["text"]), ("TEXT", "r1", text))
        self.assertTrue(any(u.endswith("/me/threads_publish") and d["creation_id"] == "container-1" for u, d in net.posts))
        ledger = json.loads(self.ledger.read_text())
        self.assertEqual((ledger[0]["comment_id"], ledger[0]["reply_id"]), ("r1", "pub-1"))
        prompt = g.seen[0]
        self.assertIn("lagos:notice_ladder:5", prompt, "the model sees the facts the post was built on")
        self.assertIn("notice-to-quit-lagos.html", prompt, "and the deep link it may give")
        self.assertIn("Abeg how many months", prompt)

    def test_a_reply_that_breaks_a_gate_is_refused_not_published(self):
        net, _, result = self.run_threads([{"n": 1, "comment_id": "r1", "skip": False, "text": "Stop paying rent, you will win in court. Section 99."}])
        self.assertEqual((result["answered"], result["refused"]), (0, 1))
        self.assertFalse(net.posts, "nothing went to Threads")
        self.assertFalse(self.ledger.exists())

    def test_dry_run_publishes_nothing_and_writes_no_ledger(self):
        net, _, result = self.run_threads([{"n": 1, "comment_id": "r1", "skip": False, "text": "Six months' notice — s.13(1)(e)."}], dry_run=True)
        self.assertEqual(result["answered"], 1)
        self.assertFalse(net.posts)
        self.assertFalse(self.ledger.exists())
        self.assertIn("Six months", br.summary_md(result))

    def test_missing_write_permission_is_reported_with_the_scope(self):
        routes = [r for r in threads_routes() if r[0] != ("POST", "/me/threads")]
        routes.append((("POST", "/me/threads"), (403, {"error": {"message": "(#200) Requires threads_content_publish permission", "code": 200}})))
        _, _, result = self.run_threads([{"n": 1, "comment_id": "r1", "skip": False, "text": "Six months' notice — s.13(1)(e)."}], routes=routes)
        self.assertEqual(result["answered"], 0)
        self.assertEqual(result["capabilities"]["threads"], "missing: threads_content_publish")
        self.assertIn("re-mint that token with this permission", br.summary_md(result))

    def test_gemini_quota_spent_means_wait_not_crash(self):
        def exhausted(url, payload, timeout=120):
            return 429, json.dumps({"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota"}})
        net = FakeNet(threads_routes())
        result = br.run(http=net, gemini_http=exhausted, env=ENV, now=NOW, only="threads", log=lambda *_: None,
                        sleep=lambda *_: None, ledger=[], packs=PACKS)
        self.assertTrue(result["quota"])
        self.assertEqual(result["answered"], 0)
        self.assertIn("wait for the next slot", br.summary_md(result))


class FacebookInstagramShapeTests(unittest.TestCase):
    def test_facebook_reads_toplevel_comments_skips_the_page_and_replies_under_the_comment(self):
        page = ENV["FB_PAGE_ID"]
        net = FakeNet([
            (("GET", "/%s/posts" % page), (200, {"data": [{"id": "fbp1", "message": "Rent receipt — s.5", "created_time": "2026-10-17T08:31:00+0000",
                                                             "comments": {"summary": {"total_count": 2}}}]})),
            (("GET", "/fbp1/comments"), (200, {"data": [
                {"id": "c1", "from": {"id": "u9", "name": "Ngozi"}, "message": "Does the receipt need a stamp?", "created_time": "2026-10-17T09:00:00+0000"},
                {"id": "c2", "from": {"id": page, "name": "DocOga"}, "message": "ours", "created_time": "2026-10-17T09:01:00+0000"},
                {"id": "c3", "from": {"id": "u3", "name": "Dayo"}, "message": "already answered one", "created_time": "2026-10-17T09:02:00+0000",
                 "comments": {"data": [{"from": {"id": page}}]}},
            ]})),
            (("POST", "/c1/comments"), (200, {"id": "c1_reply"})),
        ])
        pf = br.Facebook(net, ENV, NOW, lambda *_: None)
        pending, skipped = br.collect([pf], [], lambda *_: None)
        self.assertEqual([c["comment_id"] for c in pending], ["c1"])
        self.assertEqual(skipped["ours_or_answered"], 1, "the Page's own comment is dropped on read; Dayo's already-answered one is counted")
        self.assertEqual(pf.reply(pending[0], "No stamp needed."), "c1_reply")
        self.assertEqual(net.posts[-1][1]["message"], "No stamp needed.")

    def test_facebook_without_pages_manage_engagement_says_so(self):
        net = FakeNet([(("POST", "/c1/comments"), (403, {"error": {"message": "(#200) Requires pages_manage_engagement", "code": 200}}))])
        pf = br.Facebook(net, ENV, NOW, lambda *_: None)
        self.assertIsNone(pf.reply({"id": "c1"}, "hi"))
        self.assertEqual(pf.capability, "missing: pages_manage_engagement")

    def test_instagram_uses_the_instagram_login_host_and_the_replies_edge(self):
        net = FakeNet([
            (("GET", "graph.instagram.com/v26.0/me/media"), (200, {"data": [{"id": "m1", "caption": "cap", "timestamp": "2026-10-17T18:11:00+0000", "comments_count": 1}]})),
            (("GET", "/m1/comments"), (200, {"data": [{"id": "ic1", "text": "Which state law is this?", "username": "okafor", "timestamp": "2026-10-17T18:30:00+0000",
                                                        "replies": {"data": [{"username": "someone_else"}]}}]})),
            (("POST", "graph.instagram.com/v26.0/ic1/replies"), (200, {"id": "ic1_r"})),
        ])
        pf = br.Instagram(net, dict(ENV, META_GRAPH_VERSION="v26.0"), NOW, lambda *_: None)
        pending, _ = br.collect([pf], [], lambda *_: None)
        self.assertEqual([c["comment_id"] for c in pending], ["ic1"])
        self.assertEqual(pf.reply(pending[0], "Lagos — which state are you in?"), "ic1_r")

    def test_instagram_missing_manage_comments_names_the_instagram_login_scope(self):
        net = FakeNet([
            (("GET", "/me/media"), (200, {"data": [{"id": "m1", "caption": "cap", "timestamp": "2026-10-17T18:11:00+0000", "comments_count": 3}]})),
            (("GET", "/m1/comments"), (400, {"error": {"message": "(#10) Application does not have permission for this action", "code": 10}})),
        ])
        pf = br.Instagram(net, ENV, NOW, lambda *_: None)
        br.collect([pf], [], lambda *_: None)
        self.assertEqual(pf.capability, "missing: instagram_business_manage_comments")


class ContextTests(unittest.TestCase):
    def test_the_context_carries_the_cited_facts_and_the_deep_link(self):
        ctx = br.context_for({"post_at": "2026-10-17T12:10:00+0000"}, PACKS)
        self.assertEqual(ctx["state"], "lagos")
        self.assertEqual([f["id"] for f in ctx["facts"]], ["lagos:notice_ladder:5"])
        self.assertEqual(ctx["link"], "https://docoga.com.ng/notice-to-quit-lagos.html")

    def test_a_rotation_day_has_no_pack_and_no_legal_shelf(self):
        ctx = br.context_for({"post_at": "2026-10-01T12:10:00+0000"}, PACKS)
        self.assertEqual((ctx["pack"], ctx["facts"], ctx["link"]), (None, [], "https://docoga.com.ng"))
        self.assertIn("answer without any legal claim", br.prompt_for([{"platform": "threads", "comment_id": "x", "post_text": "p", "post_at": "2026-10-01",
                                                                       "author": "a", "text": "t"}], [ctx]))


class WorkflowContractTests(unittest.TestCase):
    def test_the_replies_workflow_runs_after_each_posting_slot_with_write_only_to_contents(self):
        import yaml
        wf = yaml.safe_load((ROOT / ".github" / "workflows" / "brain_replies.yml").read_text(encoding="utf-8"))
        crons = sorted(c["cron"] for c in wf[True]["schedule"])
        self.assertEqual(crons, ["40 10 * * *", "40 13 * * *", "40 19 * * *"],
                         "11:40 / 14:40 / 20:40 WAT — 90 minutes after Facebook, Threads and Instagram post")
        self.assertEqual(wf["permissions"], {"contents": "write"})
        self.assertEqual(wf["concurrency"]["group"], "docoga-brain")
        text = (ROOT / ".github" / "workflows" / "brain_replies.yml").read_text(encoding="utf-8")
        self.assertIn("tools/brain_replies.py run", text)
        self.assertIn("logs/brain_replied.json", text)
        self.assertIn("[skip ci]", text)
        self.assertIn("token_vault.py", text, "Instagram/Threads tokens come out of the vault like every other lane")


if __name__ == "__main__":
    unittest.main()
