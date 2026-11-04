"""The end-card kicker that killed a Short (3 Nov 2026).

"PART 3 TOMORROW · CLAUSES THE LAW OVERRIDES" passed the typography solver at 26px — measured
untracked at 688px — and failed the QA engine's safe-zone check twice at 937px, because kickers
settle with 6px of tracking between glyphs and the auto-fix only ever resized cascades. The 6pm
Short for 3 Nov never published. The solver now measures the tracked width and shrinks kickers to
the 24px floor (then trims words); the series pointer is chosen against the same measure."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import series_week as sw  # noqa: E402

try:
    import motionstudio as ms  # noqa: E402
    FONTS = not ms.check_environment()
except Exception:  # noqa: BLE001 — no PIL/numpy here
    ms, FONTS = None, False

POINTER = "PART 3 TOMORROW · CLAUSES THE LAW OVERRIDES"


class PointerBudget(unittest.TestCase):
    def test_the_pointer_never_exceeds_the_budget_and_prefers_the_day_word(self):
        series = {"part": 2, "total": 5, "name": "Tenancy agreement", "next_label": "Clauses the law overrides"}
        text = sw.pointer(series)
        self.assertLessEqual(len(text), sw.POINTER_MAX)
        self.assertTrue(text.startswith("PART 3"))
        self.assertTrue(text.endswith("CLAUSES THE LAW OVERRIDES"))
        long_series = dict(series, next_label="A label so long that no kicker could ever carry it on one glance line")
        self.assertLessEqual(len(sw.pointer(long_series)), sw.POINTER_MAX)

    def test_the_solver_measures_kickers_tracked_and_the_autofix_knows_kickers(self):
        src = (ROOT / "tools" / "motionstudio.py").read_text(encoding="utf-8")
        self.assertIn("def kicker_w(", src)
        self.assertIn("def fit_kicker(", src)
        self.assertIn("if b['kind'] == 'kicker':\n                line = fit_kicker(b)", src)
        self.assertIn("elif b['kind'] == 'kicker' and b['text'] and kicker_w(", src)


@unittest.skipUnless(FONTS, "Inter is not installed here; the runner has it")
class MeasuredWithTheFont(unittest.TestCase):
    def test_the_killer_kicker_is_wider_tracked_than_untracked_and_fits_after_the_solver(self):
        self.assertGreater(ms.kicker_w(POINTER, 26), ms.SAFE_W, "the bug: tracked width over the band")
        self.assertLessEqual(ms.tw(POINTER, "SemiBold", 26), ms.SAFE_W, "the solver's old, untracked view")
        beat = ms.Beat("kicker", "kicker", POINTER, size=26, y=1085, color=ms.YELLOW)
        line = ms.fit_kicker(beat)
        self.assertEqual(beat["size"], ms.KICKER_FLOOR)
        self.assertEqual(beat["text"], POINTER, "shrinking was enough; no word was lost")
        self.assertIn("24px", line)
        self.assertLessEqual(ms.kicker_w(beat["text"], beat["size"]), ms.SAFE_W)

    def test_a_kicker_too_wide_even_at_the_floor_loses_words_not_the_frame(self):
        text = "PART 3 TOMORROW · " + " ".join(["OVERRIDES"] * 6)
        beat = ms.Beat("kicker", "kicker", text, size=26, y=1085, color=ms.YELLOW)
        line = ms.fit_kicker(beat)
        self.assertIn("TRIMMED", line)
        self.assertTrue(beat["text"].startswith("PART 3 TOMORROW"))
        self.assertLessEqual(ms.kicker_w(beat["text"], beat["size"]), ms.SAFE_W)
        self.assertGreaterEqual(beat["size"], ms.KICKER_FLOOR)

    def test_the_series_pointer_is_chosen_against_the_same_measure(self):
        series = {"part": 2, "total": 5, "name": "Tenancy agreement", "next_label": "Clauses the law overrides"}
        self.assertTrue(sw.kicker_fits(sw.pointer(series)))
        self.assertEqual(sw.pointer(series), POINTER, "fits at the floor, so the day word stays")


if __name__ == "__main__":
    unittest.main()
