"""Law watch (3 Nov 2026): the bills our pages call "a bill, not law, as at <date>" are read in the
news every week by a machine, at ₦0, and a passage headline becomes an issue — never a page edit."""
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import law_watch as lw  # noqa: E402
import state_law_data as law  # noqa: E402

NOW = datetime(2026, 11, 12, 10, 15, tzinfo=timezone.utc)

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Reps bill to cap FCT advance rent passes first reading - Premium Times</title>
<link>https://paper.ng/fct-first</link><pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate><description>HB.2839</description></item>
<item><title>Enugu Assembly passes landlord and tenant amendment bill - Vanguard</title>
<link>https://paper.ng/enugu-passes</link><pubDate>Tue, 10 Nov 2026 10:00:00 GMT</pubDate><description>agency fees capped</description></item>
<item><title>Mbah signs tenancy bill into law - Punch</title>
<link>https://paper.ng/enugu-signed</link><pubDate>Wed, 11 Nov 2026 10:00:00 GMT</pubDate><description>Enugu rent</description></item>
<item><title>Super Eagles pass to Lagos for friendly - Punch</title>
<link>https://paper.ng/ball</link><pubDate>Wed, 11 Nov 2026 10:00:00 GMT</pubDate><description>football</description></item>
<item><title>Lagos tenancy bill: committee holds public hearing - Guardian</title>
<link>https://paper.ng/lagos-hearing</link><pubDate>Tue, 01 Sep 2026 10:00:00 GMT</pubDate><description>old</description></item>
</channel></rss>"""


def fake_http(url):
    return 200, RSS


class ShelfCarriesTheBills(unittest.TestCase):
    def test_every_published_bill_is_dated_staged_sourced_and_called_a_bill(self):
        rows = law.pending_bills()
        self.assertEqual([slug for slug, _ in rows], ["abuja", "anambra", "enugu", "lagos"])
        for slug, bill in rows:
            w = bill.get("watch") or {}
            self.assertRegex(w.get("verified", ""), r"^\d{4}-\d{2}-\d{2}$", slug)
            self.assertTrue(w.get("stage"), slug)
            self.assertGreaterEqual(len(w.get("queries") or []), 2, slug)
            self.assertTrue(all(u.startswith("https://") for u in w.get("sources") or []), slug)
            self.assertTrue(bill.get("title"), slug)
            self.assertIn("not law", bill["text"].lower(), slug)
            self.assertIn("3 November 2026", bill["text"], slug)
            for key, value in bill.items():
                for text in (value if isinstance(value, list) else [value]):
                    if isinstance(text, str):
                        self.assertLessEqual(len(text), 420, "%s.%s is clipped by law_index" % (slug, key))

    def test_the_fct_bill_is_the_one_the_reps_read_on_22_october_2026(self):
        bill = dict(law.pending_bills())["abuja"]
        joined = " ".join([bill["text"], bill["stage"]] + bill["would"] + [bill["caution"]])
        for needle in ("HB.2839", "22 October 2026", "first reading", "Paul Nnamchi", "twelve months",
                       "₦500,000–₦5 million", "no rent ceiling", "not breaking any law"):
            self.assertIn(needle, joined)

    def test_the_brain_sees_the_bill_but_not_the_watch_handle(self):
        import law_index
        facts = [f for f in law_index.facts_for("abuja") if f["key"].startswith("pending_bill")]
        self.assertGreaterEqual(len(facts), 5)
        self.assertIn("not law", facts[0]["text"].lower())
        self.assertIn("HB.2839", facts[0]["cite"])
        self.assertFalse(any("watch." in f["key"] or f["key"].endswith(".title") for f in facts))
        self.assertFalse(any("premiumtimesng.com" in f["text"] for f in facts))

    def test_the_four_states_pages_print_the_block_and_the_others_do_not(self):
        for slug in ("abuja", "lagos", "anambra", "enugu"):
            html = (ROOT / "site" / ("tenancy-agreement-%s.html" % slug)).read_text(encoding="utf-8")
            self.assertIn("A bill that would change this &mdash; not law yet", html, slug)
            self.assertIn("Stage checked against the sources on 3 November 2026", html, slug)
        for slug in ("kano", "edo", "rivers", "ogun"):
            html = (ROOT / "site" / ("tenancy-agreement-%s.html" % slug)).read_text(encoding="utf-8")
            self.assertNotIn("A bill that would change this", html, slug)
        abuja = (ROOT / "site" / "tenancy-agreement-abuja.html").read_text(encoding="utf-8")
        self.assertIn("HB.2839", abuja)
        self.assertIn("22 October 2026", abuja)


class Classification(unittest.TestCase):
    def test_readings_move_assent_passes(self):
        self.assertEqual(lw.classify("Lagos tenancy bill passes second reading"), "moving")
        self.assertEqual(lw.classify("Reps bill on FCT rent passes first reading"), "moving")
        self.assertEqual(lw.classify("Sanwo-Olu assents to tenancy law"), "passed")
        self.assertEqual(lw.classify("Enugu Assembly passes landlord and tenant bill"), "passed")
        self.assertEqual(lw.classify("Mbah signs rent bill into law"), "passed")
        self.assertEqual(lw.classify("Agents lament rising rent in Lagos"), "mention")

    def test_relevance_needs_the_topic_and_the_place(self):
        self.assertTrue(lw.relevant("abuja", "Reps move to cap advance rent in FCT"))
        self.assertFalse(lw.relevant("abuja", "Reps move to cap fuel prices"))
        self.assertFalse(lw.relevant("lagos", "Enugu landlords protest new tenancy bill"))
        self.assertTrue(lw.relevant("enugu", "Enugu landlords protest new tenancy bill"))

    def test_google_news_source_suffix_goes_to_source_not_headline(self):
        title, paper = lw._strip_source("Mbah signs tenancy bill into law - Punch Newspapers")
        self.assertEqual((title, paper), ("Mbah signs tenancy bill into law", "Punch Newspapers"))


class Pull(unittest.TestCase):
    def test_a_passage_headline_newer_than_the_verified_date_is_an_alert_and_a_reading_is_not(self):
        data = lw.pull(http=fake_http, now=NOW, log=lambda *a: None, previous={})
        by = {b["slug"]: b for b in data["bills"]}
        self.assertEqual(by["enugu"]["signal"], "passed")
        self.assertEqual(by["enugu"]["alerts"], 2)
        self.assertEqual(by["enugu"]["items"][0]["title"], "Mbah signs tenancy bill into law")
        self.assertEqual(by["enugu"]["items"][0]["source"], "Punch")
        self.assertEqual(by["abuja"]["signal"], "moving")
        self.assertEqual(by["abuja"]["alerts"], 0)
        self.assertEqual(by["lagos"]["signal"], "quiet", "the September hearing is outside the 14-day window; football is not tenancy")
        self.assertEqual(data["alerts"], 2)
        self.assertEqual(len(lw.alert_lines(data)), 2)
        self.assertRegex(lw.signature(data), r"^[0-9a-f]{10}$")

    def test_a_passage_headline_older_than_the_verified_date_stops_shouting(self):
        watch = [("enugu", dict(law.STATE_LAW["enugu"]["pending_bill"],
                                watch=dict(law.STATE_LAW["enugu"]["pending_bill"]["watch"], verified="2026-11-12")))]
        data = lw.pull(http=fake_http, now=NOW, log=lambda *a: None, watch=watch, previous={})
        self.assertEqual(data["alerts"], 0)
        self.assertEqual(data["bills"][0]["signal"], "quiet")

    def test_the_ledger_has_the_heartbeat_shape_and_keeps_first_seen(self):
        first = lw.pull(http=fake_http, now=NOW, log=lambda *a: None, previous={})
        self.assertEqual(first["entries"][-1]["recorded_at"], NOW.isoformat(timespec="seconds"))
        later = NOW.replace(day=19)
        second = lw.pull(http=fake_http, now=later, log=lambda *a: None, previous=first)
        self.assertEqual(len(second["entries"]), 2)
        enugu = {b["slug"]: b for b in second["bills"]}["enugu"]
        self.assertEqual(enugu["items"][0]["first_seen"], NOW.isoformat(timespec="seconds"))

    def test_an_unreachable_index_is_a_line_not_a_crash(self):
        def dead(url):
            raise OSError("no network")
        data = lw.pull(http=dead, now=NOW, log=lambda *a: None, previous={})
        self.assertEqual(data["alerts"], 0)
        self.assertTrue(all(b["signal"] == "quiet" for b in data["bills"]))
        self.assertTrue(any("unreachable" in s for s in data["sources"]))

    def test_main_writes_the_ledger_and_prints_the_count_the_workflow_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "law_watch.json"
            md = Path(tmp) / "law_watch.md"
            buf = io.StringIO()
            with mock.patch.object(lw, "_http", fake_http), mock.patch.object(lw, "datetime") as dt:
                dt.now.return_value = NOW
                dt.fromisoformat = datetime.fromisoformat
                with redirect_stdout(buf):
                    lw.main(["pull", "--out", str(out), "--summary", str(md)])
            text = buf.getvalue()
            self.assertIn("LAW_WATCH_ALERTS=2", text)
            self.assertRegex(text, r"LAW_WATCH_SIGNATURE=[0-9a-f]{10}")
            self.assertIn("ALERT Enugu — Mbah signs tenancy bill into law", text)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["alerts"], 2)
            self.assertIn("### Law watch", md.read_text(encoding="utf-8"))

    def test_the_scorecard_block_names_each_bill_and_shouts_only_on_passage(self):
        data = lw.pull(http=fake_http, now=NOW, log=lambda *a: None, previous={})
        lines = "\n".join(lw.scorecard_lines(data, now=NOW))
        self.assertIn("4 bill(s) watched, 2 passage alert(s)", lines)
        self.assertIn("Enugu — 🔴 PASSAGE REPORTED", lines)
        self.assertIn("Abuja (FCT) — 🟡 moving", lines)
        self.assertIn("Lagos — quiet", lines)
        self.assertIn("not pulled yet", "\n".join(lw.scorecard_lines({}, now=NOW)))
        import brain_scorecard
        src = (ROOT / "tools" / "brain_scorecard.py").read_text(encoding="utf-8")
        self.assertIn("### Law watch — are the bills on our pages still bills", src)
        self.assertTrue(hasattr(brain_scorecard, "kpis"))


class Workflow(unittest.TestCase):
    TEXT = (ROOT / ".github" / "workflows" / "law_watch.yml").read_text(encoding="utf-8")

    def test_it_is_weekly_and_off_every_posting_minute(self):
        crons = re.findall(r"cron: '([^']+)'", self.TEXT)
        self.assertEqual(crons, ["15 10 * * 4"])
        minute, hour = crons[0].split()[:2]
        self.assertNotIn(minute, ("0", "10", "20", "30", "40"), "posting lanes own :00/:10/:20/:30/:40")
        self.assertEqual(hour, "10")

    def test_it_costs_nothing_and_writes_only_its_ledger(self):
        self.assertNotIn("pip install", self.TEXT, "stdlib only — nothing to install")
        self.assertIn("git add logs/law_watch.json", self.TEXT)
        self.assertNotIn("site/", self.TEXT, "the lane never commits a page")
        self.assertNotIn("sed -i", self.TEXT, "never edits the shelf")
        self.assertNotIn("git add tools/", self.TEXT, "never edits the shelf")
        self.assertIn("[skip ci]", self.TEXT)

    def test_it_files_one_labelled_issue_only_on_a_passage_headline(self):
        self.assertIn("issues: write", self.TEXT)
        self.assertIn("gh issue create --label law-watch", self.TEXT)
        self.assertIn("steps.pull.outputs.alerts != '0'", self.TEXT)
        self.assertIn("gh issue list --label law-watch --state open", self.TEXT)
        self.assertIn("LAW_WATCH_ALERTS", self.TEXT)
        self.assertIn("inputs.dry_run != true", self.TEXT)


if __name__ == "__main__":
    unittest.main()
