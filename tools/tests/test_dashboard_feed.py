"""dashboard_feed — the repo's records become one honest JSON for the owner dashboard."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard_feed as df  # noqa: E402

NOW = datetime(2026, 10, 17, 19, 30, tzinfo=timezone.utc)   # 8:30pm Lagos, Saturday


def make_root(tmp, approved_today=True):
    root = Path(tmp)
    (root / "brain" / "drafts").mkdir(parents=True)
    (root / "logs").mkdir()
    (root / "worker").mkdir()
    (root / "tools").mkdir()
    (root / "tools" / "deepdive_queue.py").write_text("print('dd5 Service charge: what the law lets a landlord bill')\n")
    (root / "worker" / "wrangler.toml").write_text('name = "docoga-pass"\n[[kv_namespaces]]\nbinding = "KV"\nid = "f3a5afebe7d04bb0a6018c0d7d355253"\n')
    if approved_today:
        (root / "brain" / "drafts" / "2026-10-17.json").write_text(json.dumps({
            "version": 1, "status": "approved", "date": "2026-10-17", "theme": "rent-receipt", "reader": "tenants paying cash",
            "post": {"headline": "Pay rent without a receipt and you paid nothing — in court.", "lines": ["Section 5, Lagos Tenancy Law 2011", "Ask. Every time."]},
            "threads": {"text": "Your landlord refuses a receipt. What is your next move?", "evening": ""}, "short": {"title": "No receipt, no proof."},
            "why": "Payday week: most cash rent moves now.", "quiz": False, "generated_at": "2026-10-17T01:40:00+01:00"}))
    (root / "brain" / "drafts" / "2026-10-18.json").write_text(json.dumps({"status": "draft", "date": "2026-10-18", "post": {"headline": "x"}}))
    (root / "brain" / "goals.json").write_text(json.dumps({"milestones": {
        "facebook.followers": {"target": 500, "due": "2027-01-31", "unlocks": "Facebook Stars"},
        "youtube.subscribers": {"target": 500, "due": "2027-03-31", "unlocks": "YouTube fan funding"}}}))
    (root / "logs" / "instagram_sent.json").write_text(json.dumps([
        {"recorded_at": "2026-10-16T07:37:20+01:00", "title": "⏰ Don't Wait Until There's a Problem!\n\nMost disputes…", "topic": "instagram-card", "url": "https://www.instagram.com/p/Dei581lFjbL/", "privacy": "public", "state": "uploaded", "date": "2026-10-16"}]))
    (root / "logs" / "facebook_reels.json").write_text(json.dumps([
        {"recorded_at": "2026-10-15T06:23:07+01:00", "title": "Pay the wrong agent. Lose the flat.", "topic": "Pay the wrong agent. Lose the flat.", "url": "/reel/1086374460872192/", "privacy": "public", "date": "2026-10-15"}]))
    (root / "logs" / "youtube_published.json").write_text(json.dumps([
        {"recorded_at": "2026-10-14T04:54:00+01:00", "title": "Keep a Rent Paper Trail #Shorts", "topic": "Keep a Rent Paper Trail", "url": "https://www.youtube.com/watch?v=SgkOucdmHYM", "privacy": "public", "state": "published", "date": "2026-10-14"},
        {"recorded_at": "2026-10-17T18:02:00+01:00", "title": "Sign without asking #Shorts", "topic": "Sign without asking", "url": "https://www.youtube.com/watch?v=abc", "privacy": "private", "publish_at": "2026-10-19T18:00:00Z", "state": "scheduled", "date": "2026-10-17"}]))
    (root / "logs" / "tiktok_drafts.json").write_text(json.dumps({"entries": [
        {"recorded_at": "2026-10-16T17:05:00+00:00", "key": "abc", "publish_id": "v_inbox_file~v2.1", "status": "SEND_TO_USER_INBOX",
         "caption": "Sign without asking #DocOga #Nigeria", "video": "short.mp4"}]}))
    (root / "logs" / "youtube_stats.json").write_text(json.dumps([{"taken_at": "2026-10-14T18:07:26+01:00", "channel": {"subscribers": 49, "views": 142, "videos": 13},
                                                                   "videos": [{"id": "a", "title": "A", "views": 5, "kind": "short"}, {"id": "b", "title": "B", "views": 40, "kind": "longform"}]}]))
    (root / "logs" / "scorecard.json").write_text(json.dumps([
        {"taken_at": "2026-10-05T06:40:00+01:00", "week": "2026-W41", "kpis": {"facebook.followers": 400}},
        {"taken_at": "2026-10-12T06:40:00+01:00", "week": "2026-W42", "kpis": {"facebook.followers": 410, "telegram.members": 31}, "orders": ["post the Reel at 7pm"]}]))
    return root


class Build(unittest.TestCase):
    def test_the_plan_reports_approved_packs_and_honest_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed = df.build(NOW, make_root(tmp))
        plan = feed["plan"]
        self.assertEqual([p["date"] for p in plan], ["2026-10-17", "2026-10-18", "2026-10-19"])
        self.assertTrue(plan[0]["approved"])
        self.assertEqual(plan[0]["headline"], "Pay rent without a receipt and you paid nothing — in court.")
        self.assertEqual(plan[0]["short"], "No receipt, no proof.")
        self.assertIn("receipt", plan[0]["threads"])
        self.assertFalse(plan[1]["approved"], "a draft that is not approved is not a plan")
        self.assertFalse(plan[2]["approved"])
        self.assertIn("approved pack for today", feed["brain_note"])

    def test_no_pack_says_rotation_not_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed = df.build(NOW, make_root(tmp, approved_today=False))
        self.assertIn("post from the rotation", feed["brain_note"])

    def test_posted_merges_every_ledger_newest_first_with_absolute_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed = df.build(NOW, make_root(tmp))
        posted = feed["posted"]
        self.assertEqual([r["platform"] for r in posted], ["youtube", "tiktok", "instagram", "facebook", "youtube"])
        tk = posted[1]
        self.assertEqual((tk["kind"], tk["title"], tk["url"]), ("inbox draft", "Sign without asking #DocOga #Nigeria", ""))
        self.assertEqual(posted[0]["at"], "2026-10-17T17:02:00Z", "Lagos stamps are normalised to UTC")
        fb = [r for r in posted if r["platform"] == "facebook"][0]
        self.assertEqual(fb["url"], "https://www.facebook.com/reel/1086374460872192/")
        self.assertEqual(fb["kind"], "reel")
        ig = [r for r in posted if r["platform"] == "instagram"][0]
        self.assertEqual(ig["title"], "⏰ Don't Wait Until There's a Problem!", "first line only")

    def test_youtube_snapshot_top_videos_and_the_scheduled_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed = df.build(NOW, make_root(tmp))
        y = feed["youtube"]
        self.assertEqual(y["snapshot"]["subscribers"], 49)
        self.assertEqual(y["snapshot"]["top"][0]["title"], "B")
        self.assertEqual(len(y["scheduled"]), 1)
        self.assertEqual(y["scheduled"][0]["publish_at"], "2026-10-19T18:00:00Z")
        self.assertEqual(feed["deepdive_next"], "dd5 Service charge: what the law lets a landlord bill")

    def test_growth_uses_the_scorecard_and_falls_back_to_youtubes_own_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed = df.build(NOW, make_root(tmp))
        rows = {r["key"]: r for r in feed["growth"]["rows"]}
        self.assertEqual(rows["facebook.followers"]["value"], 410)
        self.assertEqual(rows["facebook.followers"]["previous"], 400)
        self.assertEqual(rows["facebook.followers"]["target"], 500)
        self.assertEqual(rows["youtube.subscribers"]["value"], 49)
        self.assertEqual(rows["youtube.subscribers"]["source"], "youtube_stats")
        self.assertIsNone(rows["instagram.followers"]["value"], "not measured is null, never 0")
        self.assertEqual(feed["growth"]["orders"], ["post the Reel at 7pm"])

    def test_tiktok_connection_is_read_from_the_box_header_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(tmp)
            self.assertEqual(df.build(NOW, root)["tiktok"], {"connected": False, "since": None, "expires": None})
            (root / "logs" / "tiktok_refresh_token.box").write_text(json.dumps(
                {"v": 1, "alg": "A256GCM", "name": "TIKTOK_REFRESH_TOKEN", "nonce": "n", "ciphertext": "SECRET-CT", "minted_at": "2026-10-18T09:00:00+00:00", "expires_at": "2027-10-18"}))
            feed = df.build(NOW, root)
        self.assertEqual(feed["tiktok"], {"connected": True, "since": "2026-10-18T09:00:00+00:00", "expires": "2027-10-18"})
        self.assertNotIn("SECRET-CT", json.dumps(feed), "ciphertext never travels to the dashboard")

    def test_the_live_repo_builds_without_error(self):
        feed = df.build(NOW)
        self.assertEqual(feed["version"], 1)
        self.assertIsInstance(feed["posted"], list)
        self.assertLess(len(json.dumps(feed)), 400_000)


class Push(unittest.TestCase):
    def test_push_puts_one_key_into_the_workers_namespace(self):
        seen = {}

        class Resp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def http(req):
            seen["url"] = req.full_url; seen["method"] = req.get_method(); seen["auth"] = req.get_header("Authorization"); seen["body"] = req.data
            return Resp()
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(tmp)
            status, problem = df.push({"version": 1}, env={"CLOUDFLARE_API_TOKEN": "cf", "CLOUDFLARE_ACCOUNT_ID": "acc"}, root=root, http=http)
        self.assertEqual((status, problem), (200, ""))
        self.assertEqual(seen["method"], "PUT")
        self.assertEqual(seen["url"], "https://api.cloudflare.com/client/v4/accounts/acc/storage/kv/namespaces/f3a5afebe7d04bb0a6018c0d7d355253/values/adm:feed")
        self.assertEqual(seen["auth"], "Bearer cf")

    def test_the_namespace_comes_from_the_real_wrangler_toml(self):
        self.assertRegex(df.namespace_id(), r"^[0-9a-f]{32}$")

    def test_missing_credentials_are_a_message_not_a_crash(self):
        status, problem = df.push({}, env={})
        self.assertEqual(status, 0)
        self.assertIn("CLOUDFLARE_API_TOKEN", problem)

    def test_cli_build_prints_machine_lines(self):
        err = io.StringIO()
        with redirect_stdout(io.StringIO()):
            old = sys.stderr; sys.stderr = err
            try:
                code = df.main(["build", "--out", str(Path(tempfile.mkdtemp()) / "f.json")])
            finally:
                sys.stderr = old
        self.assertEqual(code, 0)
        self.assertIn("FEED_POSTED=", err.getvalue())
        self.assertIn("FEED_PLAN=", err.getvalue())


if __name__ == "__main__":
    unittest.main()
