"""🔒 THE BRAIN IS LOCKED to Gemini (owner, 17 Oct 2026: "I don't want the gpt-oss — use only Gemini
and plan with it, lock it in"). One host, Gemini-family model names, no second provider, no fallback.
Never edit this file to let something through; revert the change that trips it.
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import brain_replies  # noqa: E402
import deepdive  # noqa: E402
import gemini_text  # noqa: E402

BRAIN_FILES = ("gemini_text.py", "brain.py", "brain_replies.py", "listening.py", "deepdive.py", "gemini_tts.py",
               "gemini_quota.py", "guides_build.py")
FOREIGN = ("api.groq.com", "openrouter.ai", "/ai/v1/chat/completions", "api.openai.com", "api.mistral.ai",
           "integrate.api.nvidia.com", "api.cerebras.ai", "huggingface.co", "models.github.ai", "api.together.xyz",
           "api.sambanova.ai", "gpt-oss", "@cf/", "llama-3", "anthropic.com", "cloudflare_json", "cf_ai")


class BrainLockTests(unittest.TestCase):
    def test_every_ladder_is_gemini_and_the_lock_names_the_one_host(self):
        for chain in (gemini_text.DEFAULT_MODELS, gemini_text.LITE_FIRST_MODELS, brain_replies.MODELS, deepdive.GEMINI_MODELS):
            for m in chain:
                self.assertTrue(m.startswith(gemini_text.LOCKED_MODEL_PREFIXES), m)
        self.assertEqual(gemini_text.LOCKED_HOST, "generativelanguage.googleapis.com")
        self.assertIn(gemini_text.LOCKED_HOST, gemini_text.API)
        self.assertIn(gemini_text.LOCKED_HOST, gemini_text.MODELS_URL)
        self.assertIn(gemini_text.LOCKED_HOST, deepdive.GEMINI_API)

    def test_a_non_gemini_model_is_refused_before_any_request_leaves(self):
        calls = []

        def http(url, payload, key):
            calls.append(url)
            return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})
        with self.assertRaises(gemini_text.GeminiError):
            gemini_text.generate_json("hi", http=http, log=lambda *a: None, models_chain=("gpt-oss-120b",))
        self.assertEqual(calls, [])
        with patch.dict(os.environ, {"BRAIN_MODELS": "gemini-3.8-flash, llama-3.3-70b"}):
            with self.assertRaises(gemini_text.GeminiError):
                gemini_text.models()
        with patch.dict(os.environ, {"BRAIN_MODELS": "gemini-3.8-flash,gemma-4-31b-it"}):
            self.assertEqual(gemini_text.models(), ("gemini-3.8-flash", "gemma-4-31b-it"))

    def test_when_every_gemini_rung_is_spent_the_night_pauses_and_nothing_else_is_called(self):
        urls = []

        def http(url, payload, key):
            urls.append(url)
            return 429, json.dumps({"error": {"code": 429, "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                                    "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                                                    "quotaDimensions": {"model": "gemini-x"}}]}]}})
        with self.assertRaises(gemini_text.Exhausted):
            gemini_text.generate_json("hi", http=http, sleep=lambda s: None, log=lambda *a: None,
                                      models_chain=("gemini-x", "gemini-y"))
        self.assertEqual(len(urls), 2)
        self.assertTrue(all(gemini_text.LOCKED_HOST in u for u in urls))

    def test_no_brain_file_names_another_provider_and_gemini_text_has_two_urls_only(self):
        hits = []
        for name in BRAIN_FILES:
            p = ROOT / "tools" / name
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8").lower()
            hits += ["%s: %s" % (name, w) for w in FOREIGN if w in text]
        self.assertEqual(hits, [])
        gt = (ROOT / "tools" / "gemini_text.py").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"https?://", gt)), 2, "generateContent and ListModels — nothing else")

    def test_the_brain_workflows_hold_only_the_gemini_key_for_models(self):
        for wf in ("brain.yml", "brain_replies.yml"):
            text = (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")
            self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", text)
            for bad in ("CF_AI_", "GROQ_", "OPENROUTER_", "OPENAI_API_KEY", "MISTRAL_", "NVIDIA_", "CLOUDFLARE_API_TOKEN"):
                self.assertNotIn(bad, text, "%s carries %s" % (wf, bad))

    def test_qa_carries_the_lock_and_the_docs_say_it(self):
        qa = (ROOT / "tools" / "qa.py").read_text(encoding="utf-8")
        self.assertIn("THE BRAIN IS LOCKED to Gemini", qa)
        self.assertIn("never edit this check", qa)
        self.assertIn("THE BRAIN IS LOCKED", (ROOT / "docs" / "BRAIN.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
