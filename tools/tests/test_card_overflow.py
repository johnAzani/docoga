"""29 Oct 2026 — the owner's screenshot of the Threads lunch card: a one-paragraph post became a
70-word headline, headlines were fitted for width only, and the type ran under the chip and off
the frame. Guarantee: whatever the lanes hand the renderer, the planned piece fits the safe box."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import social_card as sc  # noqa: E402

TODAY = ("A tenant in Port Harcourt transferred rent to an agent. No paper receipt was issued. When the agent "
         "disappeared, the landlord sued for arrears. In Rivers State, the person who claims payment was made "
         "bears the legal burden of proving it with a receipt. A bank alert alone leaves you open to dispute. "
         "Did your last rent payment come with a signed receipt naming the property and the period?")

LONG = [
    TODAY,
    " ".join(["Rent paid without a receipt is rent you may pay twice because the law asks the payer to prove it."] * 12),
    " ".join(["word"] * 90),                                   # one endless "sentence", no full stop
    "Short line.\n\n" + " ".join(["A body line that goes on and on about the Lagos Tenancy Law 2011 section 5."] * 10),
    "\u20a6100,000 fine. " * 25,
    "Did you know? " + " ".join(["Every yearly tenant in Lagos is owed six months' written notice under s.13(1)(e)."] * 8),
]


class ParagraphHeadlineTests(unittest.TestCase):
    def test_a_one_paragraph_post_gets_a_one_sentence_headline_and_the_rest_is_body(self):
        head, body = sc.structure(TODAY)
        self.assertEqual(head, "A tenant in Port Harcourt transferred rent to an agent.")
        self.assertTrue(body and body[0][2].startswith("No paper receipt was issued."))
        self.assertLessEqual(len(head.split()), sc.HEADLINE_MAX_WORDS)

    def test_a_short_headline_with_its_own_body_is_left_alone(self):
        head, body = sc.structure("Pay without a receipt. Pay twice.\n\n\u2705 Date\n\u2705 Amount in words")
        self.assertEqual(head, "Pay without a receipt. Pay twice.")
        self.assertEqual([w for _, _, w in body], ["Date", "Amount in words"])

    def test_a_run_on_first_sentence_is_clipped_at_a_clause_not_mid_thought(self):
        first, after = sc._first_sentence("One two three four five six seven eight nine ten eleven twelve, "
                                          "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty.")
        self.assertTrue(first.endswith("\u2026"))
        self.assertLessEqual(len(first.split()), sc.HEADLINE_MAX_WORDS)
        self.assertIn("thirteen", after)


class FitGuaranteeTests(unittest.TestCase):
    def _render(self, text, **kw):
        out = Path("/tmp/docoga_card_overflow_test.jpg")
        sc.render(text, out, kicker="proof of payment", **kw)
        p = sc.LAST_PLAN
        return p, p["frame"]["ceiling"] - p["frame"]["top"]

    def test_every_long_text_fits_the_card_safe_box(self):
        for text in LONG:
            p, box = self._render(text)
            self.assertTrue(p["fits"], (text[:40], p["height"], box))
            self.assertLessEqual(p["height"], box)
            self.assertGreaterEqual(p.get("b_size") or 30, 30, "body never below its floor")
            self.assertGreaterEqual(p["h_size"] or 40, 40, "headline never below 40")

    def test_every_long_text_fits_the_story_safe_box_too(self):
        for text in LONG[:3]:
            p, box = self._render(text, size=(sc.STORY_W, sc.STORY_H), safe=sc.STORY_SAFE)
            self.assertTrue(p["fits"], (text[:40], p["height"], box))

    def test_the_bottom_of_the_type_stays_above_the_chip(self):
        from PIL import Image
        out = Path("/tmp/docoga_card_overflow_test.jpg")
        sc.render(TODAY, out, kicker="proof of payment")
        img = Image.open(out).convert("L")
        W, H = img.size
        # the chip sits in the bottom band; the rows just above it, inside the margins, must be
        # free of light (text) pixels — the overflow in the screenshot put glyphs exactly there
        ceiling = sc.LAST_PLAN["frame"]["ceiling"]        # the gap between the safe box and the chip
        band = img.crop((sc.MARGIN, ceiling + 4, W - sc.MARGIN, ceiling + 36))
        light = sum(1 for v in band.getdata() if v > 200)
        self.assertLess(light, 40, "type is running into the chip's band")


if __name__ == "__main__":
    unittest.main()
