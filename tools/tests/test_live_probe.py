"""live_probe (29 Oct 2026): the product is probed, not only the lanes. Offline — every HTTP
call is replaced by a fake, so the suite never touches the live site."""
import json
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import live_probe as lp  # noqa: E402

SMAP = b"<urlset>" + b"".join(b"<loc>https://docoga.com.ng/p%d</loc>" % i for i in range(25)) + b"</urlset>"


def healthy(url, follow=True, timeout=0):
    if url == lp.SITE + "/":
        return 200, url, {"Content-Type": "text/html"}, b'<title>x</title>DocOga <meta property="og:image" content="x">', 120
    if url.endswith("/sitemap.xml"):
        return 200, url, {"Content-Type": "application/xml"}, SMAP, 50
    if url.endswith("/robots.txt"):
        return 200, url, {"Content-Type": "text/plain"}, b"Sitemap: x", 50
    if url.endswith("/og/home.jpg"):
        return 200, url, {"Content-Type": "image/jpeg"}, b"\xff\xd8", 50
    if url.startswith(lp.SITE + "/p"):
        return 200, url, {}, b"<title>p</title>", 70
    if url == lp.PASS + "/":
        return 200, url, {}, json.dumps({"ok": True, "service": "docoga-pass", "priceNGN": 2000}).encode(), 90
    if url == lp.LEDGER + "/health":
        return 200, url, {}, b'{"ok":true}', 40
    if url == lp.LEDGER + "/api/stats":
        return 200, url, {}, b'{"total":31}', 40
    if url == lp.CLOCK + "/":
        return 200, url, {}, json.dumps({"ok": True, "token": "present", "paused": False, "entries": 30}).encode(), 40
    return 0, url, {}, b"unreachable", 1


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self._fetch, self._tls = lp.fetch, lp.check_tls
        lp.fetch = healthy
        lp.check_tls = lambda *a, **k: lp.Result("TLS certificate", "https://docoga.com.ng", True, 200, 5, "80 days left")
        self.calls = []

    def tearDown(self):
        lp.fetch, lp.check_tls = self._fetch, self._tls

    def run_tool(self, tmp):
        return lp.main(["--out", str(tmp / "lp.json"), "--markdown", str(tmp / "lp.md"), "--retry-wait", "0"])

    def test_a_healthy_site_is_exit_0_with_every_sitemap_page_checked(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_tool(Path(d)), 0)
            rep = json.loads((Path(d) / "lp.json").read_text())
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["failing"], [])
        names = [c["name"] for c in rep["checks"]]
        self.assertEqual(sum(1 for n in names if n.startswith("/p")), 25)
        for must in ("home page", "sitemap.xml", "robots.txt", "og/home.jpg", "docoga-pass (payments)",
                     "docoga-ledger /health", "docoga-ledger /api/stats (Rent Monitor)",
                     "docoga-clock (the schedule)", "TLS certificate"):
            self.assertIn(must, names)

    def test_a_dead_worker_is_exit_1_after_a_second_look(self):
        looks = []

        def broken(url, follow=True, timeout=0):
            if url == lp.PASS + "/":
                looks.append(url)
                return 500, url, {}, b"error 1101", 90
            return healthy(url, follow, timeout)
        lp.fetch = broken
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_tool(Path(d)), 1)
            rep = json.loads((Path(d) / "lp.json").read_text())
        self.assertEqual(len(looks), 2, "a failure must be confirmed by a retry before it counts")
        self.assertEqual([f["name"] for f in rep["failing"]], ["docoga-pass (payments)"])

    def test_a_blip_that_recovers_on_retry_is_not_an_alarm(self):
        state = {"n": 0}

        def flaky(url, follow=True, timeout=0):
            if url == lp.LEDGER + "/health":
                state["n"] += 1
                if state["n"] == 1:
                    return 0, url, {}, b"timed out", 20000
            return healthy(url, follow, timeout)
        lp.fetch = flaky
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_tool(Path(d)), 0)
            rep = json.loads((Path(d) / "lp.json").read_text())
        notes = {c["name"]: c["note"] for c in rep["checks"]}
        self.assertEqual(notes["docoga-ledger /health"], "recovered on retry")

    def test_a_price_change_a_paused_clock_and_a_html_landing_are_findings(self):
        def drifted(url, follow=True, timeout=0):
            if url == lp.PASS + "/":
                return 200, url, {}, json.dumps({"ok": True, "service": "docoga-pass", "priceNGN": 2500}).encode(), 90
            if url == lp.CLOCK + "/":
                return 200, url, {}, json.dumps({"ok": True, "token": "missing", "paused": True, "entries": 30}).encode(), 40
            if url == lp.SITE + "/p3":
                return 307, url, {"Location": "/p3.html"}, b"", 30
            if url == lp.SITE + "/p3.html":
                return 200, url, {}, b"<title>p</title>", 30
            return healthy(url, follow, timeout)
        lp.fetch = drifted
        results = lp.run_once()
        bad = {r.name: r.note for r in results if not r.ok}
        self.assertIn("priceNGN is 2500", bad["docoga-pass (payments)"])
        self.assertIn("dispatch token", bad["docoga-clock (the schedule)"])
        self.assertIn("paused", bad["docoga-clock (the schedule)"])
        self.assertIn("clean-URL regression", bad["/p3"])

    def test_the_signature_changes_only_when_the_failing_set_changes(self):
        a = [lp.Result("x", "u", False, 500, 1, "status 500")]
        b = [lp.Result("x", "u", False, 500, 2, "status 500")]
        c = [lp.Result("x", "u", False, 502, 2, "status 502")]
        self.assertEqual(lp.signature(a), lp.signature(b))
        self.assertNotEqual(lp.signature(a), lp.signature(c))


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / ".github" / "workflows" / "live_probe.yml"
        self.text = self.path.read_text(encoding="utf-8")
        self.doc = yaml.safe_load(self.text)

    def test_it_is_on_a_four_hour_schedule_between_the_posting_minutes(self):
        on = self.doc.get("on") or self.doc.get(True)
        crons = [e["cron"] for e in on["schedule"]]
        self.assertEqual(crons, ["25 0,4,8,12,16 * * *"])

    def test_it_reads_only_and_can_file_one_issue(self):
        self.assertEqual(self.doc["permissions"], {"contents": "read", "issues": "write"})
        self.assertIn("gh issue list --label live-probe", self.text)
        self.assertIn("gh issue create --label live-probe", self.text)
        self.assertIn("gh issue close", self.text)
        for forbidden in ("git push", "git commit", "/verify", "/activate", "/flw-webhook", "wrangler"):
            self.assertNotIn(forbidden, self.text, forbidden)

    def test_the_tool_itself_never_posts_or_pays(self):
        src = (ROOT / "tools" / "live_probe.py").read_text(encoding="utf-8")
        self.assertNotIn("/verify", src)
        self.assertNotIn("/activate", src)
        self.assertNotIn("/api/register", src)
        self.assertNotIn("method=\"POST\"", src)
        self.assertNotIn("data=", src.split("def fetch")[1].split("def _json")[0])

    def test_the_clock_knows_the_lane(self):
        sched = json.loads((ROOT / "workers" / "clock" / "schedule.json").read_text(encoding="utf-8"))
        self.assertIn("live_probe.yml", [e["workflow"] for e in sched["entries"]])


if __name__ == "__main__":
    unittest.main()
