"""site/_redirects — a 301 for every /x.html (10 Nov 2026, Growth dive)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import redirects_build as rb  # noqa: E402


class RedirectsTests(unittest.TestCase):
    def test_every_public_page_gets_a_permanent_line_and_the_functional_pages_do_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            for name in ("index.html", "notice-to-quit-nigeria.html", "admin.html", "success.html", "tiktok-connect.html"):
                (site / name).write_text("<html></html>", encoding="utf-8")
            (site / "guides").mkdir()
            (site / "guides" / "index.html").write_text("x", encoding="utf-8")
            (site / "guides" / "abuja-quit-notice-checklist.html").write_text("x", encoding="utf-8")
            (site / "admin").mkdir()
            (site / "admin" / "panel.html").write_text("x", encoding="utf-8")
            self.assertEqual(rb.pairs(site), [
                ("/guides/abuja-quit-notice-checklist.html", "/guides/abuja-quit-notice-checklist"),
                ("/guides/index.html", "/guides/"),
                ("/index.html", "/"),
                ("/notice-to-quit-nigeria.html", "/notice-to-quit-nigeria"),
            ])
            text = rb.render(site)
            self.assertIn("/notice-to-quit-nigeria.html /notice-to-quit-nigeria 301\n", text)
            self.assertNotIn("admin", text)
            self.assertNotIn("302", text)
            self.assertTrue(rb.build(site=site), "first write")
            self.assertFalse(rb.build(site=site), "idempotent")
            self.assertEqual(rb.check(site=site), "")
            (site / "new-page.html").write_text("x", encoding="utf-8")
            self.assertIn("stale", rb.check(site=site))
            (site / "_redirects").unlink()
            self.assertIn("missing", rb.check(site=site))

    def test_the_real_file_is_current_covers_the_sitemap_and_stays_static(self):
        self.assertEqual(rb.check(), "", "run python3 tools/redirects_build.py")
        lines = [l for l in (ROOT / "site" / "_redirects").read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
        self.assertLess(len(lines), 2000, "Cloudflare's static-redirect limit")
        self.assertTrue(all(l.endswith(" 301") and "*" not in l and ":" not in l for l in lines), "static 301 lines only")
        import re
        sitemap = (ROOT / "site" / "sitemap.xml").read_text(encoding="utf-8")
        dests = {dst for _, dst in rb.pairs()}
        for loc in re.findall(r"<loc>https://docoga\.com\.ng(/[^<]*)</loc>", sitemap):
            self.assertIn(loc, dests, "%s is in the sitemap but has no /x.html → /x line" % loc)
        for split in ("/notice-to-quit-nigeria", "/notice-to-quit-kano", "/notice-to-quit-enugu", "/rent-receipt-lagos"):
            self.assertIn("%s.html %s 301" % (split, split), "\n".join(lines), "the pages Search Console counted twice on 9 Nov 2026")

    def test_the_guides_lane_refreshes_it_and_the_brain_commits_it(self):
        gb = (ROOT / "tools" / "guides_build.py").read_text(encoding="utf-8")
        self.assertIn("redirects_build.build(site=site)", gb)
        wf = (ROOT / ".github" / "workflows" / "brain.yml").read_text(encoding="utf-8")
        self.assertIn("site/sitemap.xml site/_redirects; do", wf)
        qa = (ROOT / "tools" / "qa.py").read_text(encoding="utf-8")
        self.assertIn('"redirects_build.py"), "--check"', qa)
        wrangler = (ROOT / "wrangler.jsonc").read_text(encoding="utf-8")
        self.assertNotIn('"main"', wrangler, "assets-only worker — _redirects applies to every request")


class InstagramCatchUpTests(unittest.TestCase):
    def test_a_later_scheduled_run_carries_a_card_the_chosen_slot_lost(self):
        wf = (ROOT / ".github" / "workflows" / "instagram_autopost.yml").read_text(encoding="utf-8")
        gate = wf.split("DONE=$(python3 tools/posted_today.py", 1)[1]
        self.assertLess(gate.index('"${DONE:-0}" != "0"'), gate.index("IG_SLOT=catchup"), "the same-day ledger guard comes first")
        self.assertIn('elif [ "$NOW" -gt "$WANT" ] && [ "$NOW" -le 21 ]; then', gate)
        self.assertIn("IG_SLOT=catchup", gate)


if __name__ == "__main__":
    unittest.main()
