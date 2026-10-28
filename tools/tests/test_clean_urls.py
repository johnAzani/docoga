"""Clean URLs (28 Oct 2026). Cloudflare Workers assets answer /x.html with 307 → /x, so every
canonical, og:url, sitemap <loc> and JSON-LD url must be the bare URL — a canonical that redirects
away from itself got the same page indexed twice ("quit notice": .html at position 1.0 with 48
impressions AND the bare URL at 1.4 with 8). The generators must keep producing bare URLs."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import clean_urls as cu  # noqa: E402

SITE = ROOT / "site"


class RuleTests(unittest.TestCase):
    def test_absolute_html_urls_lose_the_extension_and_keep_hash_and_query(self):
        src = ('<link rel="canonical" href="https://docoga.com.ng/notice-to-quit-nigeria.html">'
               '<a href="https://docoga.com.ng/index.html#pricing">x</a>'
               '<a href="https://docoga.com.ng/guides/index.html">g</a>'
               '"url": "https://docoga.com.ng/videos/dd4.html?utm=1"')
        out = cu.clean_text(src, relative=False)
        self.assertIn('href="https://docoga.com.ng/notice-to-quit-nigeria"', out)
        self.assertIn('href="https://docoga.com.ng/#pricing"', out)
        self.assertIn('href="https://docoga.com.ng/guides/"', out)
        self.assertIn('"url": "https://docoga.com.ng/videos/dd4?utm=1"', out)
        self.assertNotIn(".html", out)

    def test_relative_links_become_root_relative_only_when_asked(self):
        src = '<a href="rent-relief-nigeria.html">r</a> <a href="index.html#team">t</a> <a href="index.html">h</a>'
        self.assertEqual(cu.clean_text(src, relative=False), src)
        out = cu.clean_text(src, relative=True)
        self.assertIn('href="/rent-relief-nigeria"', out)
        self.assertIn('href="/#team"', out)
        self.assertIn('href="/"', out)

    def test_other_hosts_scripts_and_the_receipt_canonical_are_untouched(self):
        src = '<a href="https://example.com/a.html">a</a> <script>const f="x.html";</script> receiptCanonical()'
        self.assertEqual(cu.clean_text(src, relative=True), src)

    def test_rewrite_is_idempotent_on_the_live_site(self):
        for p in cu.targets():
            text = p.read_text(encoding="utf-8")
            self.assertEqual(cu.clean_text(text, relative=(p.parent == SITE)), text, p.name)


class LiveSiteTests(unittest.TestCase):
    def test_no_canonical_og_url_or_sitemap_loc_ends_in_html(self):
        self.assertEqual(cu.offenders(), [])

    def test_the_quit_notice_page_has_one_bare_canonical_matching_its_og_url(self):
        t = (SITE / "notice-to-quit-nigeria.html").read_text(encoding="utf-8")
        self.assertIn('<link rel="canonical" href="https://docoga.com.ng/notice-to-quit-nigeria">', t)
        self.assertIn('<meta property="og:url" content="https://docoga.com.ng/notice-to-quit-nigeria">', t)
        self.assertEqual(t.count('rel="canonical"'), 1)

    def test_every_sitemap_loc_is_served_by_cloudflare_html_handling(self):
        smap = (SITE / "sitemap.xml").read_text(encoding="utf-8")
        locs = re.findall(r"<loc>https://docoga\.com\.ng/([^<]*)</loc>", smap)
        self.assertGreater(len(locs), 60)
        for l in locs:
            if not l:
                continue
            self.assertFalse(l.endswith(".html"), l)
            served = (SITE / (l + ".html")).is_file() or (SITE / l.rstrip("/") / "index.html").is_file() or (SITE / l).is_file()
            self.assertTrue(served, l)

    def test_the_payment_pages_are_left_alone(self):
        names = {p.name for p in cu.targets()}
        self.assertNotIn("success.html", names)
        self.assertNotIn("admin.html", names)
        self.assertNotIn("tiktok-connect.html", names)

    def test_the_generators_emit_bare_urls(self):
        for name, needle in (("gen_guide_pages.py", "clean_text(html, relative=True)"),
                             ("gen_state_pages.py", "clean_text(html, relative=True)"),
                             ("guides_build.py", 'url = "%s/%s/%s" % (HOST, GUIDES_DIRNAME, slug)'),
                             ("video_pages.py", 'url = "%s/%s/%s" % (HOST, DIRNAME, eid)')):
            self.assertIn(needle, (ROOT / "tools" / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
