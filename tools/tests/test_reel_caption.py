"""reel_caption — the Short's caption when it travels as a Reel (21 Oct 2026), and the
6:00pm lane's two new Reel steps (Facebook Page + @docoga.ng) that ride on the same file."""
import json
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import reel_caption as rc  # noqa: E402

DESCRIPTION = """Watch the full Deep-Dive — Rent Receipt in Nigeria: The 7 Lines:
https://www.youtube.com/watch?v=JJhRcCgAxyQ

You paid your rent in cash, your landlord smiled, and nobody wrote anything down. In Lagos, that smile is not a receipt.

In this Short:
• Section 5 makes the receipt mandatory
• Seven lines every receipt must carry
• What to do when the landlord refuses
• A fourth tip that must not make the caption

Practical document-keeping tips for Nigerian tenants and landlords. General information only. More free document tools: https://docoga.com.ng

Daily tips on Telegram: https://t.me/docogadaily

#Shorts #TenantTips #NigeriaRent"""


class Caption(unittest.TestCase):
    def test_the_hook_sentence_leads_and_fits_before_more(self):
        text = rc.caption("instagram", "Pay without a receipt. Pay twice.", DESCRIPTION, date(2026, 10, 21))
        first = text.split("\n")[0]
        self.assertTrue(first.startswith("You paid your rent in cash"), first)
        self.assertLessEqual(len(first), rc.HOOK_MAX)
        self.assertNotIn("Watch the full Deep-Dive", text, "the link block is YouTube's, not the Reel's")
        self.assertNotIn("#Shorts", text)

    def test_tips_become_search_keywords_three_at_most(self):
        text = rc.caption("facebook", "x", DESCRIPTION, date(2026, 10, 21))
        self.assertIn("→ Section 5 makes the receipt mandatory", text)
        self.assertIn("→ What to do when the landlord refuses", text)
        self.assertNotIn("fourth tip", text)

    def test_one_send_line_that_names_a_receiver_and_rotates_by_day(self):
        days = [date(2026, 10, 20 + i) for i in range(8)]
        lines = [[l for l in rc.caption("instagram", "x", DESCRIPTION, d).split("\n") if re.match(r"(Send|Forward)", l)] for d in days]
        self.assertTrue(all(len(l) == 1 for l in lines), lines)
        self.assertEqual(len({l[0] for l in lines}), 8, "eight days, eight different receivers")
        self.assertEqual(rc.caption("instagram", "x", DESCRIPTION, days[0]), rc.caption("instagram", "x", DESCRIPTION, days[0]), "deterministic for a date")

    def test_the_brains_own_send_line_wins_when_the_pack_has_one(self):
        pack = {"status": "approved", "post": {"cta": "Send this to the friend renewing in January."}}
        text = rc.caption("facebook", "x", DESCRIPTION, date(2026, 10, 21), pack)
        self.assertIn("Send this to the friend renewing in January.", text)
        other = {"status": "approved", "post": {"cta": "Which state are you renting in? Tell us below."}}
        text2 = rc.caption("facebook", "x", DESCRIPTION, date(2026, 10, 21), other)
        self.assertTrue(any(l in text2 for l in rc.SEND_LINES), "a question is not a send line — the rotation supplies one")

    def test_facebook_carries_the_link_and_instagram_points_to_the_bio(self):
        fb = rc.caption("facebook", "x", DESCRIPTION, date(2026, 10, 21))
        ig = rc.caption("instagram", "x", DESCRIPTION, date(2026, 10, 21))
        self.assertIn("https://docoga.com.ng", fb)
        self.assertNotIn("https://", ig)
        self.assertIn("link in bio", ig)
        for text in (fb, ig):
            self.assertEqual(len(re.findall(r"#\w+", text)), 4)
            self.assertLessEqual(len(text), rc.CAPTION_MAX)

    def test_no_description_falls_back_to_the_topic(self):
        text = rc.caption("instagram", "Pay without a receipt. Pay twice.", "", date(2026, 10, 21))
        self.assertTrue(text.startswith("Pay without a receipt. Pay twice."))

    def test_pack_for_reads_only_approved_packs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "brain" / "drafts").mkdir(parents=True)
            (root / "brain" / "drafts" / "2026-10-21.json").write_text(json.dumps({"status": "draft", "post": {"cta": "Send this."}}))
            self.assertIsNone(rc.pack_for(date(2026, 10, 21), root))
            (root / "brain" / "drafts" / "2026-10-21.json").write_text(json.dumps({"status": "approved", "post": {"cta": "Send this."}}))
            self.assertEqual(rc.pack_for(date(2026, 10, 21), root)["post"]["cta"], "Send this.")

    def test_cli(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc.main(["--platform", "facebook", "--topic", "T", "--description", DESCRIPTION, "--date", "2026-10-21"])
        self.assertIn("https://docoga.com.ng", buf.getvalue())


class SixPmLane(unittest.TestCase):
    """youtube_scheduled.yml: the Short becomes a Facebook Reel and an Instagram Reel."""
    WF = (ROOT / ".github" / "workflows" / "youtube_scheduled.yml").read_text(encoding="utf-8")

    def step(self, name):
        start = self.WF.index("- name: %s" % name)
        nxt = self.WF.find("\n      - name: ", start + 1)
        return self.WF[start: nxt if nxt > 0 else None]

    def test_both_reel_steps_exist_never_fail_the_publish_and_have_a_switch(self):
        for name in ("Facebook Reel — the same Short on the Page", "Instagram Reel — the same Short on @docoga.ng"):
            body = self.step(name)
            self.assertIn("continue-on-error: true", body, name)
            self.assertIn("(vars.SHORT_REELS || 'on') != 'off'", body, name)
            self.assertIn("steps.upload.outputs.video_id != ''", body, name)
            self.assertIn("steps.short.outputs.paused != 'yes'", body, name)
            self.assertIn("tools/reel_caption.py", body, name)
            self.assertIn("--window-days 30", body, "the 30-day frame law, in the platform's own ledger")

    def test_facebook_reel_dedupes_by_topic_and_records_the_page_ledger(self):
        body = self.step("Facebook Reel — the same Short on the Page")
        self.assertIn("--ledger logs/facebook_reels.json check --title \"$VIDEO_TOPIC\"", body)
        self.assertIn("scripts/post_facebook.py --reel=\"$VIDEO_PATH\" --title=\"$VIDEO_TOPIC\"", body, "the title is what the Page's same-day guard matches — Mon/Thu's morning Reel has another")
        self.assertIn("--ledger logs/facebook_reels.json record", body)
        self.assertIn("secrets.FB_PAGE_ACCESS_TOKEN", body)

    def test_instagram_reel_uses_the_parked_url_the_vault_token_and_trial_reels(self):
        body = self.step("Instagram Reel — the same Short on @docoga.ng")
        self.assertIn("HANDOFF_URL: ${{ steps.handoff.outputs.url }}", body, "the file is already on the worker for Threads — Meta fetches the same URL")
        self.assertIn("--video-url \"$HANDOFF_URL\"", body)
        self.assertIn("token_vault.py open --name IG_ACCESS_TOKEN", body)
        self.assertIn("--ledger logs/instagram_sent.json check --title \"Reel · $VIDEO_TOPIC\"", body)
        self.assertIn('TRIAL="--trial"', body)
        self.assertIn("IG_API_PATH=instagram-login", body)
        self.assertIn('if [ "$RESULT" != "sent" ]', body, "only a sent Reel is recorded")

    def test_the_commit_step_carries_both_ledgers_and_the_summary_reports_both(self):
        commit = self.step("Commit the publish ledger")
        self.assertIn("logs/facebook_reels.json logs/instagram_sent.json", commit)
        summary = self.step("Write the run summary")
        self.assertIn("| Facebook Reel |", summary)
        self.assertIn("| Instagram Reel |", summary)
        self.assertIn("steps.fb_reel.outputs.result", summary)
        self.assertIn("steps.ig_reel.outputs.result", summary)

    def test_the_reel_steps_come_after_the_hand_over_and_before_the_commit(self):
        i_hand = self.WF.index("- name: Hand the Short to the Threads evening slot")
        i_fb = self.WF.index("- name: Facebook Reel — the same Short on the Page")
        i_ig = self.WF.index("- name: Instagram Reel — the same Short on @docoga.ng")
        i_commit = self.WF.index("- name: Commit the publish ledger")
        self.assertTrue(i_hand < i_fb < i_ig < i_commit)


if __name__ == "__main__":
    unittest.main()
