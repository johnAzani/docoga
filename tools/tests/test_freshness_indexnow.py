"""3 Nov 2026 (docs/GROWTH.md, dive 2 follow-through): every generated page is plainly dated and
plainly owned, the date is honest by construction, and Bing hears about every change by IndexNow.

Research behind it: FAQ rich results were retired for every site on 7 May 2026; Google's own
15 May 2026 guide says no special AI markup is needed — Article/BreadcrumbList with real dates
remain the markup that earns rich results, and structured data must match what the page shows.
The IndexNow key file had never reached main, so no ping since 17 Oct had been accepted."""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT / "tools"))
import freshness  # noqa: E402
import guides_build  # noqa: E402
import indexnow_push  # noqa: E402
from state_law_data import LAW_REVIEWED  # noqa: E402

LD = re.compile(r'<script type="application/ld\+json">\n(.*?)\n</script>', re.S)
import gen_state_pages  # noqa: E402

STATE_PAGES = {"%s-%s.html" % (t, s): s for s in gen_state_pages.STATES for t in gen_state_pages.TOOLS}
GEN_STATE = sorted(SITE / f for f in STATE_PAGES)
GUIDES = ["tenancy-agreement-nigeria.html", "tenancy-agreement-sample-nigeria.html", "notice-to-quit-nigeria.html",
          "caution-fee-nigeria.html", "rent-receipt-format-nigeria.html", "tenant-rights-nigeria.html",
          "shop-tenancy-agreement-nigeria.html", "invoice-format-nigeria.html", "rent-relief-nigeria.html",
          "rent-index-nigeria.html"]


def blocks(html):
    return [json.loads(b) for b in LD.findall(html)]


class StampTests(unittest.TestCase):
    def test_an_unchanged_rebuild_keeps_its_date_and_a_real_change_moves_it(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.html"
            page = "<p>law</p>" + freshness.updated_line("2026-10-08") + freshness.jsonld(
                freshness.article(url="u", headline="h", description="d", image="i"))
            out, iso, changed = freshness.stamp(p, page, today="2026-11-03")
            self.assertEqual((iso, changed), ("2026-11-03", True))
            self.assertIn('data-updated="2026-11-03"', out)
            self.assertIn('<time datetime="2026-11-03">3 November 2026</time>', out)
            self.assertIn('"dateModified": "2026-11-03"', out)
            self.assertNotIn("@@", out)
            p.write_text(out, encoding="utf-8")
            out2, iso2, changed2 = freshness.stamp(p, page, today="2026-12-25")
            self.assertEqual((iso2, changed2), ("2026-11-03", False), "nothing changed → the date must not move")
            self.assertEqual(out2, out)
            out3, iso3, changed3 = freshness.stamp(p, page.replace("<p>law</p>", "<p>law, corrected</p>"), today="2026-12-25")
            self.assertEqual((iso3, changed3), ("2026-12-25", True))

    def test_the_reviewed_date_is_separate_from_the_updated_date(self):
        line = freshness.updated_line("2026-10-08")
        self.assertIn("law shelf reviewed 8 October 2026", line)
        self.assertEqual(freshness.updated_line(None).count("reviewed"), 0)

    def test_sitemap_lastmod_is_inserted_then_replaced_and_leaves_strangers_alone(self):
        xml = ("<urlset>\n  <url>\n    <loc>https://docoga.com.ng/a</loc>\n    <priority>0.7</priority>\n  </url>\n"
               "  <url>\n    <loc>https://docoga.com.ng/ab</loc>\n    <priority>0.7</priority>\n  </url>\n</urlset>")
        one = freshness.sitemap_lastmod(xml, "https://docoga.com.ng/a", "2026-11-03")
        self.assertEqual(one.count("<lastmod>"), 1)
        self.assertIn("<loc>https://docoga.com.ng/a</loc>\n    <lastmod>2026-11-03</lastmod>", one)
        two = freshness.sitemap_lastmod(one, "https://docoga.com.ng/a", "2026-12-01")
        self.assertEqual(two.count("<lastmod>"), 1)
        self.assertIn("<lastmod>2026-12-01</lastmod>", two)
        self.assertEqual(freshness.sitemap_lastmod(xml, "https://docoga.com.ng/zzz", "2026-11-03"), xml)


class GeneratedPagesTests(unittest.TestCase):
    def test_there_are_sixty_state_pages_and_ten_guides(self):
        self.assertEqual(len(GEN_STATE), 60, [p.name for p in GEN_STATE][:5])
        for p in GEN_STATE:
            self.assertTrue(p.is_file(), p.name)
        for g in GUIDES:
            self.assertTrue((SITE / g).is_file(), g)

    def test_every_generated_page_is_dated_once_and_the_three_dates_agree(self):
        smap = (SITE / "sitemap.xml").read_text(encoding="utf-8")
        for p in GEN_STATE + [SITE / g for g in GUIDES]:
            html = p.read_text(encoding="utf-8")
            vis = re.findall(r'data-updated="(\d{4}-\d{2}-\d{2})"', html)
            times = re.findall(r'<time datetime="(\d{4}-\d{2}-\d{2})">([^<]+)</time>', html)
            arts = [b for b in blocks(html) if b.get("@type") == "Article"]
            crumbs = [b for b in blocks(html) if b.get("@type") == "BreadcrumbList"]
            self.assertEqual(len(vis), 1, p.name)
            self.assertEqual(len(times), 1, p.name)
            self.assertEqual(len(arts), 1, p.name)
            self.assertEqual(len(crumbs), 1, p.name)
            iso = vis[0]
            self.assertEqual(times[0][0], iso, p.name)
            self.assertEqual(times[0][1], freshness.human(iso), p.name)
            self.assertEqual(arts[0]["dateModified"], iso, "%s: structured data must match the visible date" % p.name)
            self.assertNotIn("@@", html, p.name)
            dt.date.fromisoformat(iso)
            self.assertLessEqual(iso, freshness.today_iso(), "%s is dated in the future" % p.name)
            loc = "https://docoga.com.ng/%s" % p.name[:-5]
            m = re.search(r"<loc>%s</loc>\s*<lastmod>(\d{4}-\d{2}-\d{2})</lastmod>" % re.escape(loc), smap)
            self.assertIsNotNone(m, "%s: sitemap entry has no lastmod right after its loc" % p.name)
            self.assertEqual(m.group(1), iso, "%s: sitemap lastmod must be the page's own date" % p.name)

    def test_the_article_names_the_owner_the_canonical_and_the_card(self):
        for p in GEN_STATE + [SITE / g for g in GUIDES]:
            html = p.read_text(encoding="utf-8")
            art = [b for b in blocks(html) if b.get("@type") == "Article"][0]
            url = "https://docoga.com.ng/%s" % p.name[:-5]
            self.assertEqual(art["mainEntityOfPage"]["@id"], url, p.name)
            self.assertEqual(art["author"]["name"], "DocOga")
            self.assertEqual(art["publisher"]["logo"]["url"], "https://docoga.com.ng/logo-mark.png")
            self.assertTrue((SITE / "logo-mark.png").is_file())
            self.assertEqual(art["inLanguage"], "en-NG")
            self.assertLessEqual(len(art["headline"]), 110, p.name)
            og = art["image"].replace("https://docoga.com.ng/", "")
            self.assertTrue((SITE / og).is_file(), "%s: Article image %s is not on disk" % (p.name, og))
            self.assertIn('rel="canonical" href="%s"' % url, html, p.name)
            for c in art.get("citation", []):
                self.assertTrue(c.startswith("http"), (p.name, c))

    def test_breadcrumbs_only_point_at_pages_that_exist(self):
        for p in GEN_STATE + [SITE / g for g in GUIDES]:
            crumbs = [b for b in blocks(p.read_text(encoding="utf-8")) if b.get("@type") == "BreadcrumbList"][0]
            items = crumbs["itemListElement"]
            self.assertEqual(items[0]["item"], "https://docoga.com.ng/")
            self.assertEqual(items[-1]["item"], "https://docoga.com.ng/%s" % p.name[:-5])
            self.assertEqual([i["position"] for i in items], list(range(1, len(items) + 1)))
            for i in items[1:-1]:
                rel = i["item"].replace("https://docoga.com.ng/", "")
                self.assertTrue((SITE / (rel + ".html")).is_file(), (p.name, i["item"]))
        edo = (SITE / "notice-to-quit-edo.html").read_text(encoding="utf-8")
        mid = [b for b in blocks(edo) if b.get("@type") == "BreadcrumbList"][0]["itemListElement"][1]
        self.assertEqual(mid["item"], "https://docoga.com.ng/notice-to-quit-nigeria")

    def test_state_pages_say_when_the_law_shelf_was_reviewed_and_cite_the_primary_text(self):
        for p in GEN_STATE:
            slug = STATE_PAGES[p.name]
            html = p.read_text(encoding="utf-8")
            self.assertIn("law shelf reviewed", html, p.name)
            iso = LAW_REVIEWED.get(slug)
            self.assertIsNotNone(iso, "%s: no LAW_REVIEWED date for %r" % (p.name, slug))
            self.assertIn("law shelf reviewed %s" % freshness.human(iso), html, p.name)
        edo = [b for b in blocks((SITE / "notice-to-quit-edo.html").read_text(encoding="utf-8")) if b.get("@type") == "Article"][0]
        self.assertEqual(edo["about"]["@type"], "Legislation")
        self.assertIn("edojudiciary.gov.ng", " ".join(edo["citation"]))
        ogun = [b for b in blocks((SITE / "notice-to-quit-ogun.html").read_text(encoding="utf-8")) if b.get("@type") == "Article"][0]
        self.assertNotIn("about", ogun, "a state with no verified statute must not claim one")
        self.assertNotIn("citation", ogun)

    def test_the_sample_page_carries_its_publication_date_and_sits_under_the_pillar(self):
        html = (SITE / "tenancy-agreement-sample-nigeria.html").read_text(encoding="utf-8")
        art = [b for b in blocks(html) if b.get("@type") == "Article"][0]
        self.assertEqual(art["datePublished"], "2026-11-03")
        crumbs = [b for b in blocks(html) if b.get("@type") == "BreadcrumbList"][0]["itemListElement"]
        self.assertEqual(crumbs[1]["item"], "https://docoga.com.ng/tenancy-agreement-nigeria")
        self.assertEqual([b["@type"] for b in blocks(html)], ["FAQPage", "Article", "BreadcrumbList"])

    def test_rivers_was_re_read_after_the_dossier(self):
        self.assertEqual(LAW_REVIEWED["rivers"], "2026-11-03")
        self.assertEqual(LAW_REVIEWED["lagos"], "2026-10-08")
        for iso in LAW_REVIEWED.values():
            dt.date.fromisoformat(iso)


class IndexNowTests(unittest.TestCase):
    def test_the_key_is_public_committed_and_what_the_code_uses(self):
        key = guides_build.DEFAULT_KEY
        self.assertRegex(key, r"^[A-Za-z0-9-]{8,128}$")
        f = SITE / ("%s.txt" % key)
        self.assertTrue(f.is_file(), "site/<key>.txt must be committed — engines verify ownership by fetching it")
        self.assertEqual(f.read_text(encoding="utf-8").strip(), key)
        old = os.environ.pop("INDEXNOW_KEY", None)
        try:
            self.assertEqual(guides_build.indexnow_key(), key)
            os.environ["INDEXNOW_KEY"] = "not valid!"
            self.assertEqual(guides_build.indexnow_key(), key, "a malformed variable must not break the ping")
            os.environ["INDEXNOW_KEY"] = "abcdefgh12345678"
            self.assertEqual(guides_build.indexnow_key(), "abcdefgh12345678")
            os.environ["INDEXNOW_KEY"] = "off"
            self.assertEqual(guides_build.indexnow_key(), "", "INDEXNOW_KEY=off is the kill switch")
            self.assertFalse(guides_build.ping(["https://docoga.com.ng/"], http=lambda r: self.fail("off must not post"), log=lambda *a: None))
        finally:
            os.environ.pop("INDEXNOW_KEY", None)
            if old is not None:
                os.environ["INDEXNOW_KEY"] = old

    def test_ping_posts_the_default_key_and_the_sitemap_host(self):
        seen = {}

        def http(req):
            seen["body"] = json.loads(req.data.decode())
            seen["url"] = req.full_url
            return 202
        old = os.environ.pop("INDEXNOW_KEY", None)
        try:
            ok = guides_build.ping(["https://docoga.com.ng/notice-to-quit-edo"], http=http, log=lambda *a: None)
        finally:
            if old is not None:
                os.environ["INDEXNOW_KEY"] = old
        self.assertTrue(ok)
        self.assertEqual(seen["body"]["key"], guides_build.DEFAULT_KEY)
        self.assertEqual(seen["body"]["host"], "docoga.com.ng")
        self.assertEqual(seen["body"]["keyLocation"], "https://docoga.com.ng/%s.txt" % guides_build.DEFAULT_KEY)
        self.assertEqual(seen["url"], "https://api.indexnow.org/indexnow")

    def test_clean_urls(self):
        self.assertEqual(indexnow_push.clean_url("site/index.html"), "https://docoga.com.ng/")
        self.assertEqual(indexnow_push.clean_url("site/notice-to-quit-edo.html"), "https://docoga.com.ng/notice-to-quit-edo")
        self.assertEqual(indexnow_push.clean_url("site/guides/abuja-quit-notice-checklist.html"),
                         "https://docoga.com.ng/guides/abuja-quit-notice-checklist")

    def test_only_sitemap_pages_that_the_push_changed_are_submitted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "site").mkdir()

            def git(*a):
                subprocess.run(["git", *a], cwd=d, check=True, capture_output=True,
                               env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                                    "GIT_COMMITTER_EMAIL": "t@t"})

            def smap(*locs):
                return "<urlset>" + "".join("<url><loc>https://docoga.com.ng/%s</loc></url>" % l for l in locs) + "</urlset>"
            git("init", "-q")
            (root / "site" / "sitemap.xml").write_text(smap("", "a", "b"))
            for n in ("index", "a", "b", "admin", "success"):
                (root / "site" / (n + ".html")).write_text("v1")
            git("add", "-A"); git("commit", "-qm", "one")
            before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=d, capture_output=True, text=True).stdout.strip()
            (root / "site" / "a.html").write_text("v2")          # changed, public
            (root / "site" / "admin.html").write_text("v2")      # changed, NOT in the sitemap
            (root / "site" / "c.html").write_text("new")         # new page, added to the sitemap
            (root / "site" / "sitemap.xml").write_text(smap("", "a", "b", "c"))
            git("add", "-A"); git("commit", "-qm", "two")
            urls = indexnow_push.changed_urls(before, "HEAD", root)
            self.assertEqual(urls, ["https://docoga.com.ng/a", "https://docoga.com.ng/c"])
            self.assertIsNone(indexnow_push.changed_urls("0" * 40, "HEAD", root), "an unknown parent → the caller submits everything")
            self.assertIsNone(indexnow_push.changed_urls("deadbeef", "HEAD", root))
            self.assertEqual(indexnow_push.all_urls(root), ["https://docoga.com.ng/", "https://docoga.com.ng/a",
                                                            "https://docoga.com.ng/b", "https://docoga.com.ng/c"])

    def test_the_real_sitemap_never_lists_what_must_stay_private(self):
        urls = indexnow_push.all_urls(ROOT)
        self.assertGreater(len(urls), 60)
        for u in urls:
            self.assertNotIn("/admin", u)
            self.assertNotIn("/samples/", u)
            self.assertNotIn("/success", u)
            self.assertFalse(u.endswith(".html"), u)

    def test_the_lane_runs_on_every_site_change_to_main_and_only_reads(self):
        wf = yaml.safe_load((ROOT / ".github" / "workflows" / "indexnow.yml").read_text(encoding="utf-8"))
        on = wf[True]
        self.assertEqual(on["push"]["branches"], ["main"])
        self.assertIn("site/**", on["push"]["paths"])
        self.assertIn("!site/samples/**", on["push"]["paths"])
        self.assertIn("workflow_dispatch", on)
        self.assertEqual(wf["permissions"], {"contents": "read"})
        text = (ROOT / ".github" / "workflows" / "indexnow.yml").read_text(encoding="utf-8")
        self.assertIn("tools/indexnow_push.py", text)
        self.assertIn("github.event.before", text)
        self.assertIn("fetch-depth", text)
        for forbidden in ("git push", "git commit", "secrets."):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
