#!/usr/bin/env python3
"""gemini_text.py — the brain's one door to Gemini text generation, free tier only.

What the research of 16 Oct 2026 established, and what this module does about it:

  * Google no longer publishes a free-tier limit table; the live number is per
    project and has been as low as **20 requests/day** for the Flash models since
    December 2025 (Flash-Lite reportedly higher). So the editor is designed to need
    **two or three calls a day in total**, and this client treats every 429 as
    information (tools/gemini_quota.parse_refusal): a per-minute refusal is a short
    wait, a per-day refusal moves to the next model in the chain — the daily
    buckets are **per model**, so `gemini-2.5-flash-lite` still answers after
    `gemini-2.5-flash` is spent, and neither touches the narrator's TTS bucket.
  * JSON is requested with `responseMimeType: application/json`; the schema is
    stated in the prompt and enforced by the caller's own validation, because the
    two schema dialects (`responseSchema` / `responseJsonSchema`) have moved under
    developers twice this year and a rejected request costs a day's call.
  * Search grounding is not used: on the free tier it is either unavailable or a
    separate quota depending on the month. The law the brain cites comes from the
    repo (tools/law_index.py), not from the web.
  * Image models have no free tier at all (pricing page, October 2026): the brain
    never asks Gemini for a picture.

API: generate_json(prompt, system=None, models=None, http=None, sleep=None) → dict
Raises Exhausted when every model refused for the day, GeminiError otherwise.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import gemini_quota  # noqa: E402

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# The ladder, 17 Oct 2026. Since 18 Sep 2026 Google serves the 2.5 text models only to projects
# that used them before that date and points new projects at 3.8 Flash / 3.5 Flash-Lite; 2.5 Pro
# joined the free tier; 2.0 Flash is retired. Every rung is free of charge. A rung the key is not
# served answers 404/403 and costs nothing — the chain simply steps down. Flash-class rungs hold
# ~20 requests/day each, the Lite rungs ~500/day: the editor's two or three calls fit many times.
DEFAULT_MODELS = ("gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.5-flash",
                  "gemini-3.5-flash-lite", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite",
                  "gemini-flash-lite-latest")
# The replies lane talks more often and needs less brain: Lite rungs first, the 500/day buckets.
LITE_FIRST_MODELS = ("gemini-3.5-flash-lite", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite",
                     "gemini-flash-lite-latest", "gemini-3.8-flash", "gemini-2.5-flash")
MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200"

# 🔒 THE BRAIN IS LOCKED (owner, 17 Oct 2026: "use only Gemini and plan with it — lock it in").
# Every model the brain, the replies lane, the forum answer and the Deep-Dive writer may call is a
# Google Gemini model on this one host. There is no second provider and no fallback to one: when
# every Gemini rung is spent the night ends with exit 6 (a pause, not a failure), the lanes post
# from the rotation, and the brain tries again the next night. tools/qa.py and
# tools/tests/test_brain_lock.py refuse any change that names another provider.
LOCKED_HOST = "generativelanguage.googleapis.com"
LOCKED_MODEL_PREFIXES = ("gemini-", "gemma-")


def assert_locked(model):
    """Raise unless `model` is a Gemini-family name — called before every request."""
    name = str(model or "").strip().lower()
    if not name.startswith(LOCKED_MODEL_PREFIXES):
        raise GeminiError("THE BRAIN IS LOCKED to Gemini — refused to call %r" % model)
    return model
THINKING_MODELS = re.compile(r"gemini-(2\.5|3)")   # models whose output budget also pays for "thoughts"
MINUTE_WAIT_CAP_S = 75          # a per-minute refusal is waited out once, never longer than this
TIMEOUT_S = 120
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.S)


class GeminiError(RuntimeError):
    pass


class Exhausted(GeminiError):
    """Every model in the chain refused for the day; carries the next reset instant."""

    def __init__(self, message, resumes_at=None):
        super().__init__(message)
        self.resumes_at = resumes_at


def models():
    env = os.environ.get("BRAIN_MODELS", "").strip()
    if env:
        return tuple(assert_locked(m.strip()) for m in env.split(",") if m.strip())
    return DEFAULT_MODELS


def api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    env_path = ROOT / ".worker-secrets.env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise GeminiError("GEMINI_API_KEY is not set")


def _http(url, payload, key):
    """POST JSON; returns (status, body_text). Network errors become status 0."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, str(exc)


def _text_of(body):
    data = json.loads(body)
    cands = data.get("candidates") or []
    if not cands:
        reason = (data.get("promptFeedback") or {}).get("blockReason") or "no candidates"
        raise GeminiError("empty answer: %s" % reason)
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    if not text.strip():
        raise GeminiError("empty answer: finishReason=%s" % cands[0].get("finishReason"))
    return text


def parse_json(text):
    """Model output → dict. Tolerates a code fence and prose around one JSON object."""
    stripped = FENCE.sub("", text.strip())
    try:
        return json.loads(stripped)
    except ValueError:
        pass
    start, end = stripped.find("{"), stripped.rfind("}")
    if start >= 0 and end > start:
        return json.loads(stripped[start:end + 1])
    raise GeminiError("the answer was not JSON: %s" % stripped[:160])


def payload_for(model, prompt, system, temperature, max_output_tokens, thinking_budget):
    """The request body — thinking capped on the models that bill thoughts against the output budget.

    On Gemini 2.5/3 the `maxOutputTokens` ceiling covers the hidden reasoning as well as the
    JSON, so an uncapped think can leave no room for the answer (finishReason MAX_TOKENS, an
    unparseable half-object, a wasted daily request). `thinkingBudget` keeps a little reasoning
    and guarantees the answer fits. Older models reject the field, so they do not get it."""
    config = {"temperature": temperature, "maxOutputTokens": max_output_tokens,
              "responseMimeType": "application/json"}
    if thinking_budget is not None and THINKING_MODELS.search(model) and "lite" not in model:
        config["thinkingConfig"] = {"thinkingBudget": int(thinking_budget)}
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": config}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    return payload


def generate_json(prompt, system=None, models_chain=None, http=None, sleep=None, temperature=0.8,
                  max_output_tokens=8192, log=print, lane="brain", thinking_budget=1024):
    """One structured answer from the first model in the chain that will give it."""
    http = http or _http
    sleep = sleep or time.sleep
    key = api_key() if http is _http else os.environ.get("GEMINI_API_KEY", "test")
    chain = tuple(models_chain or models())
    last_error, exhausted = None, []
    for model in chain:
        assert_locked(model)
        payload = payload_for(model, prompt, system, temperature, max_output_tokens, thinking_budget)
        waited_minute = False
        while True:
            status, body = http(API.format(model=model), payload, key)
            if status == 200:
                try:
                    text = _text_of(body)
                    gemini_quota.note_request(model, "ok", lane=lane)
                    return parse_json(text)
                except (ValueError, GeminiError) as exc:
                    gemini_quota.note_request(model, "fail", lane=lane)
                    last_error = "%s: %s" % (model, exc)
                    log("brain: %s" % last_error)
                    break
            if status == 429:
                refusal = gemini_quota.parse_refusal(body)
                if refusal["scope"] == "minute" and not waited_minute:
                    wait = min(MINUTE_WAIT_CAP_S, max(5.0, float(refusal.get("retry_s") or 30)))
                    log("brain: %s per-minute refusal — waiting %.0fs once" % (model, wait))
                    sleep(wait)
                    waited_minute = True
                    continue
                gemini_quota.note_request(model, "exhausted", refusal=refusal, lane=lane)
                exhausted.append(model)
                log("brain: %s refused for the day (%s) — next model" % (model, refusal.get("quota_id") or "quota"))
                break
            if (status in (404, 400) and ("not found" in body.lower() or "not supported" in body.lower())) \
                    or (status == 403 and "quota" not in body.lower()):
                # 404: no such model for this key. 403 without a quota word: Google is not serving
                # this model to this project (the 2.5 rule since Sep 2026). Neither costs a request.
                last_error = "%s: unavailable (%d)" % (model, status)
                log("brain: " + last_error)
                break
            gemini_quota.note_request(model, "fail", lane=lane)
            last_error = "%s: HTTP %s %s" % (model, status, body[:200].replace("\n", " "))
            log("brain: " + last_error)
            break
    if exhausted and len(exhausted) == len(chain):
        raise Exhausted("every model refused for the day: %s" % ", ".join(exhausted),
                        resumes_at=gemini_quota.next_reset())
    raise GeminiError(last_error or "no model answered")


# ───────────────────────────── probe: which rungs does this key get? ─────────────────────────────
def _get(url, key):
    req = urllib.request.Request(url, headers={"x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, str(exc)


def served_models(http_get=None, key=None):
    """The model names Google lists for this key (ListModels costs no generation quota)."""
    status, body = (http_get or _get)(MODELS_URL, key or api_key())
    if status != 200:
        raise GeminiError("ListModels answered HTTP %s: %s" % (status, body[:200]))
    names = []
    for m in (json.loads(body).get("models") or []):
        name = str(m.get("name") or "").split("/")[-1]
        if name and "generateContent" in (m.get("supportedGenerationMethods") or []):
            names.append(name)
    return names


def probe(chain=None, http_get=None, key=None, log=print):
    """Print the ladder against the key's served list. Returns (served_rungs, missing_rungs).

    Machine line: GEMINI_SERVED=<comma list of chain models the key is served> and
    GEMINI_LADDER=ok|thin|empty — `empty` means no rung answers and tonight's plan will fall
    back to the rotation; that is the one case worth an issue."""
    chain = tuple(chain or models())
    names = set(served_models(http_get=http_get, key=key))
    served = [m for m in chain if m in names or m.endswith("-latest")]
    missing = [m for m in chain if m not in served]
    for m in chain:
        log("  %s %s" % ("✅" if m in served else "—", m))
    verdict = "empty" if not served else ("thin" if len(served) < 2 else "ok")
    log("GEMINI_SERVED=%s" % ",".join(served))
    log("GEMINI_LADDER=%s" % verdict)
    return served, missing


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "probe":
        try:
            served, _missing = probe()
        except GeminiError as exc:
            print("GEMINI_LADDER=unknown")
            print("::warning title=Gemini probe::%s" % exc)
            sys.exit(0)
        sys.exit(0 if served else 1)
    print(__doc__)
