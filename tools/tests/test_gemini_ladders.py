"""Both Gemini ladders step down on 'not served' answers and the nightly probe reports both
(29 Oct 2026). Google withdraws model names by 404, by 403-without-quota (the 2.5 rule since
Sep 2026) and by 400 'not found / not supported'; a ladder that only stepped down on 404 would
turn a renamed TTS model into a voiceless Short."""
import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import gemini_text as g  # noqa: E402

try:
    import deepdive as dd  # noqa: E402
    ENGINE_OK = True
except Exception:  # noqa: BLE001
    ENGINE_OK = False


def listing(*names):
    body = {"models": [{"name": "models/" + n, "supportedGenerationMethods": ["generateContent"]} for n in names]}
    return lambda url, key: (200, json.dumps(body))


class ProbeTests(unittest.TestCase):
    def test_the_probe_reports_the_narrator_ladder_beside_the_brains(self):
        logs = []
        with patch.dict(os.environ, {"GEMINI_TTS_MODEL": ""}):
            g.probe(http_get=listing("gemini-2.5-flash", "gemini-3.8-flash-lite-tts"), key="k", log=logs.append)
        self.assertIn("GEMINI_SERVED=gemini-2.5-flash,gemini-flash-lite-latest", logs)
        self.assertIn("GEMINI_TTS_SERVED=gemini-3.8-flash-lite-tts", logs)
        self.assertIn("GEMINI_TTS_LADDER=thin", logs)

    def test_no_tts_rung_is_the_empty_verdict_the_workflow_turns_into_an_error(self):
        logs = []
        with patch.dict(os.environ, {"GEMINI_TTS_MODEL": ""}):
            g.probe(http_get=listing("gemini-2.5-flash"), key="k", log=logs.append)
        self.assertIn("GEMINI_TTS_LADDER=empty", logs)
        wf = (ROOT / ".github" / "workflows" / "brain.yml").read_text(encoding="utf-8")
        self.assertIn("GEMINI_TTS_LADDER=empty", wf)
        self.assertIn("GEMINI_TTS_MODEL", wf)

    def test_the_tts_ladder_is_read_from_the_engine_and_the_variable_goes_first(self):
        with patch.dict(os.environ, {"GEMINI_TTS_MODEL": "gemini-9-flash-tts"}):
            chain = g.tts_models()
        self.assertEqual(chain[0], "gemini-9-flash-tts")
        self.assertIn("gemini-2.5-flash-preview-tts", chain)
        if ENGINE_OK:
            self.assertEqual(chain[1:], dd.GEMINI_MODELS)


@unittest.skipUnless(ENGINE_OK, "deepdive engine not importable (PIL/numpy)")
class NarratorLadderTests(unittest.TestCase):
    def test_not_served_covers_the_three_ways_google_withdraws_a_name(self):
        self.assertTrue(dd.not_served(404, "not found"))
        self.assertTrue(dd.not_served(403, '{"error":{"message":"Permission denied on resource project"}}'))
        self.assertTrue(dd.not_served(400, "models/x is not found for API version v1beta"))
        self.assertTrue(dd.not_served(400, "model not supported for generateContent"))
        self.assertFalse(dd.not_served(403, "Quota exceeded for this project"))
        self.assertFalse(dd.not_served(500, "internal"))
        self.assertFalse(dd.not_served(400, "invalid argument: contents"))

    def test_a_403_on_the_first_rung_walks_to_the_next_instead_of_failing(self):
        calls = []

        def fake_urlopen(req, timeout=0):
            calls.append(req.full_url)
            code = 403 if "2.5-flash-preview-tts" in req.full_url else 400
            raise urllib.error.HTTPError(req.full_url, code, "x", {}, io.BytesIO(b"model is not found"))

        with patch.object(dd, "gemini_key", lambda: "k"), patch.object(dd.urllib.request, "urlopen", fake_urlopen), \
                patch.object(dd.gemini_quota, "note_request", lambda *a, **k: None):
            voice, instruction = dd.locked_voice()
            out = dd.gemini_tts("hello", voice, instruction, "/tmp/never.mp3")
        self.assertEqual(out, ("fail", 0))
        self.assertEqual(len(calls), len(dd.GEMINI_MODELS), "every rung was tried")


if __name__ == "__main__":
    unittest.main()
