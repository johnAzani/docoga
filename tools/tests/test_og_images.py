"""og_images (29 Oct 2026): every public page has a brand link-preview image. Before this no page
had an og:image — every link shared on WhatsApp/Facebook/Threads was a text-only box."""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import og_images as og  # noqa: E402

SITE = ROOT / "site"


class CoverageTests(unittest.TestCase):
    def test_check_passes_on_the_committed_site(self):
        self.assertEqual(og.check(log=lambda *a: None), 0)

    def test_every_sitemap_page_has_its_own_image_file_at_1200_by_630_under_the_whatsapp_limit(self):
        from PIL import Image
        smap = (SITE / "sitemap.xml").read_text(encoding="utf-8")
        locs = sorted(set(re.findall(r"<loc>https://docoga\.com\.ng/([^<]*)</loc>", smap)))
        seen = set()
        for loc in locs:
            if loc.startswith("videos/") or loc.startswith("v/"):
                continue
            page = SITE / "index.html" if loc in ("", "/") else (SITE / (loc.rstrip("/") + ".html") if not loc.endswith("/") else SITE / loc / "index.html")
            if not page.is_file():
                continue
            text = page.read_text(encoding="utf-8")
            m = re.search(r'<meta property="og:image" content="https://docoga\.com\.ng/og/([^"]+)\.jpg">', text)
            self.assertIsNotNone(m, loc)
            f = SITE / "og" / ("%s.jpg" % m.group(1))
            self.assertTrue(f.is_file(), loc)
            self.assertNotIn(f.name, seen, "two pages share one preview: %s" % loc)
            seen.add(f.name)
            self.assertEqual(Image.open(f).size, (og.W, og.H), loc)
            self.assertLess(f.stat().st_size, og.OG_MAX_KB * 1024, loc)
            self.assertIn('<meta name="twitter:card" content="summary_large_image">', text, loc)

    def test_the_generators_emit_the_tags_themselves_so_regeneration_keeps_them(self):
        for src in ("gen_guide_pages.py", "gen_state_pages.py", "guides_build.py"):
            text = (ROOT / "tools" / src).read_text(encoding="utf-8")
            self.assertIn('og:image', text, src)
            self.assertIn('twitter:card', text, src)
        self.assertIn("og_images.render(", (ROOT / "tools" / "guides_build.py").read_text(encoding="utf-8"),
                      "the Brain's daily guide draws its own preview when it is written")
        wf = (ROOT / ".github" / "workflows" / "brain.yml").read_text(encoding="utf-8")
        self.assertIn("site/og", wf)

    def test_running_the_tool_twice_changes_nothing(self):
        before = {p: p.read_bytes() for p in og.pages()}
        og.run(log=lambda *a: None)
        after = {p: p.read_bytes() for p in og.pages()}
        self.assertEqual(before, after)


class UnitTests(unittest.TestCase):
    def test_titles_are_cleaned_for_the_card(self):
        self.assertEqual(og.clean_title("Rent Receipt in Lagos — Free Generator (2026)"), "Rent Receipt in Lagos")
        self.assertEqual(og.clean_title("Tenancy agreement format | DocOga"), "Tenancy agreement format")
        self.assertEqual(og.clean_title("A &amp; B | Nigeria"), "A & B")

    def test_inject_is_idempotent_and_falls_back_to_the_canonical_line(self):
        page = '<head>\n<title>T</title>\n<meta property="og:description" content="d">\n</head>'
        once = og.inject(page, "x", "T")
        self.assertIn('og:image" content="https://docoga.com.ng/og/x.jpg"', once)
        self.assertEqual(og.inject(once, "x", "T"), once)
        nodesc = '<head><title>T</title><link rel="canonical" href="https://docoga.com.ng/y"><style></style></head>'
        out = og.inject(nodesc, "y", "T")
        self.assertIn('/og/y.jpg', out)
        self.assertEqual(out.count("og:image\""), 1)

    def test_slugs_never_collide_between_top_level_and_guides(self):
        slugs = [og.slug_for(p) for p in og.pages()]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertEqual(og.slug_for(SITE / "index.html"), "home")
        self.assertEqual(og.slug_for(SITE / "guides" / "abc.html"), "guides-abc")


if __name__ == "__main__":
    unittest.main()
