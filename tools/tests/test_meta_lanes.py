#!/usr/bin/env python3
"""
Tests for the Meta lanes: Threads, Instagram, the card renderer, and the token vault.
====================================================================================

Hermetic by construction: `tools/threads_publish.py` and `tools/ig_publish.py` are driven
through their own HTTP seams (`_request` and `http`), so no test reaches graph.threads.net or
graph.instagram.com, no real token exists, and nothing can be published by accident. The
workflow shell is *executed* here rather than grepped, because the bug this file exists to keep
out — an Actions boolean arriving as the string "false" — is invisible to `assertIn` and
obvious to `subprocess.run`.

Where a test guards a mistake that was actually made in this repo, it says which one, because a
test nobody can make fail is decoration.
"""

import contextlib
import datetime
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_threads_content as gc  # noqa: E402
import threads_publish as tp  # noqa: E402
import ig_publish as ig  # noqa: E402
import social_card  # noqa: E402

WORKFLOWS = ROOT / ".github" / "workflows"
HAS_PIL = importlib.util.find_spec("PIL") is not None
CRED_KEYS = ("THREADS_ACCESS_TOKEN", "THREADS_USER_ID", "IG_ACCESS_TOKEN", "IG_USER_ID",
             "IG_API_PATH", "META_APP_ID", "META_APP_SECRET", "SOCIAL_TOKEN_KEY",
             "THREADS_API_HOST", "META_GRAPH_VERSION")


def run_publisher(module, argv, env):
    """Call a publisher's main() with captured output and an environment of exactly `env`.

    The environment is cleared rather than merged: this sandbox exports credentials of its own,
    and a test that inherits one is a test that could publish for real.

    `SystemExit` is folded into the returned code because `ig_publish.get_config()` and argparse
    both exit that way: the exit code *is* the contract the workflow depends on, so a test that
    let the exception fly would be asserting nothing about the thing it exists to pin.
    """
    import warnings
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with mock.patch.dict(os.environ, {}, clear=True):
        os.environ.update(env)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # an unrelated DeprecationWarning is not a
                try:                            # lane's diagnosis, and it corrupts the JSON
                    code = module.main(argv)    # capture the refresh tests parse
                except SystemExit as exc:
                    code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue() + err.getvalue()


class FakeHttp:
    """Scripted answers keyed on an optional verb plus a substring of the URL or its query.

    Two properties matter. A route may be prefixed `POST ` because both platforms answer
    `GET /{id}/media` (recent posts — the duplicate guard) and `POST /{id}/media` (create a
    container) on the *same path*: a fake that cannot tell them apart hands the poster a list of
    old posts as its new container id, and the test passes while the lane fails. And the longest
    needle wins, because `/42/threads` is a prefix of `/42/threads_publishing_limit` — first-match
    by insertion order answers a quota call with the recent-posts payload.
    """

    VERBS = ("GET", "POST", "PUT", "DELETE")

    def __init__(self, routes, shape=2):
        self.routes = routes
        self.calls = []
        # `threads_publish` seams return (status, body); `ig_publish` adds headers because it has
        # to read Content-Length. One fake, two arities — the difference is the publishers'.
        self.shape = shape

    @classmethod
    def _matches(cls, needle, method, url, query):
        verb, _, rest = needle.partition(" ")
        if verb in cls.VERBS and rest:
            return verb == method and (rest in url or rest in query)
        return needle in url or needle in query

    def __call__(self, method, url, params=None, data=None, timeout=45, headers=None):
        query = urllib.parse.urlencode({**(params or {}), **(data or {})})
        self.calls.append((method, url, query))
        for needle in sorted(self.routes, key=len, reverse=True):
            if self._matches(needle, method, url, query):
                answer = self.routes[needle]
                if callable(answer):
                    answer = answer(method, url, query)
                if self.shape == 3 and len(answer) == 2:
                    return answer[0], answer[1], {}
                return answer
        raise AssertionError("no route scripted for %s %s" % (method, url))

    def __init_subclass__(cls, **kwargs):  # pragma: no cover - guards accidental subclass drift
        super().__init_subclass__(**kwargs)

    @property
    def posts(self):
        return [call for call in self.calls if call[0] == "POST"]

    def wrote_anything(self):
        return bool(self.posts)


def ok(body):
    return (200, json.dumps(body))


def threads_env(tmp, token="THREADSTOKENabc123"):
    """A 0600-style token file plus the env the publisher needs. Returns (env, token_path)."""
    path = Path(tmp) / "token"
    path.write_text(token, encoding="utf-8")
    return {"THREADS_ACCESS_TOKEN": token, "THREADS_USER_ID": "42"}, str(path)


class ThreadsCopy(unittest.TestCase):
    """The 500-character rule, measured in the units the platform charges in."""

    def test_emoji_are_charged_by_bytes_not_characters(self):
        self.assertEqual(tp.cost("abc"), 3)
        self.assertEqual(tp.cost("\U0001f4f8"), 4, "an emoji is 1 character and 4 bytes to Threads")
        self.assertNotEqual(tp.cost("\U0001f4f8"), len("\U0001f4f8"),
                            "if len() were the measure, this lane lies about every post it trims")

    def test_generated_copy_always_fits(self):
        for offset in range(1, 40):
            day = datetime.date(2026, 10, 1) + datetime.timedelta(days=offset)
            content = gc.generate(day, write=False)
            with self.subTest(day=day.isoformat()):
                self.assertLessEqual(content["cost"], gc.MAX_COST)
                self.assertLessEqual(tp.cost(content["text"]), tp.MAX_COST)

    def test_the_day_is_reproducible(self):
        day = datetime.date(2026, 10, 13)
        self.assertEqual(gc.generate(day, write=False)["text"],
                         gc.generate(day, write=False)["text"],
                         "a re-run must produce the same post, or the duplicate guard cannot "
                         "recognise its own yesterday")

    def test_different_days_are_different_posts(self):
        self.assertNotEqual(gc.generate(datetime.date(2026, 10, 13), write=False)["text"],
                            gc.generate(datetime.date(2026, 10, 14), write=False)["text"])

    def test_a_monster_template_is_trimmed_and_says_so(self):
        monster = "Stamp duty applies to tenancy agreements in Lagos. " * 60
        # No patch of `gc.random.Random`: patching a module attribute with a lambda that calls
        # the same attribute is infinite recursion, and I wrote it here believing it was a stub.
        with mock.patch.object(gc.tg, "TEMPLATES", {"promo": [monster]}), \
                mock.patch.object(gc.tg, "HASHTAGS", {"promo": "#DocOga #Nigeria #Lagos"}), \
                mock.patch.object(gc.tg, "WEEKLY_SCHEDULE",
                                  {day: ["promo"] for day in range(7)}):
            _type, text, notes = gc.build(datetime.date(2026, 10, 13),
                                           __import__("random").Random("x"))
        self.assertLessEqual(gc.threads_cost(text), gc.MAX_COST)
        self.assertTrue(any("hashtag" in note for note in notes),
                        "the tags are the first thing to go, and the only way to go quietly")
        self.assertTrue(any("trim" in note for note in notes),
                        "silently shortening copy is how a lane starts meaning something "
                        "narrower than anyone wrote: %s" % notes)

    def test_the_link_cap_is_enforced_before_the_api_refuses(self):
        body = " ".join("see https://docoga.com.ng/x%d" % n for n in range(8))
        text, notes = gc.fit(body, "")
        self.assertLessEqual(gc.link_count(text), gc.LINK_LIMIT)
        self.assertTrue(any("link" in note for note in notes), notes)

    def test_a_trim_never_splits_a_grapheme(self):
        # Cutting at an index can leave half of 👨‍‍👧 (three code points, no space inside) at the
        # end of a public post. Trimming by words makes that unrepresentable.
        family = "\U0001f468\u200d\U0001f469\u200d\U0001f467"
        text, _notes = gc.fit(("word " * 200) + family, "")
        self.assertLessEqual(gc.threads_cost(text), gc.MAX_COST)
        self.assertFalse(text.rstrip("…").endswith("\u200d"),
                         "an ellipsis glued to a zero-width joiner is a broken emoji")

    def test_no_markup_reaches_the_platform(self):
        for parts in ((2026, 10, 13), (2026, 11, 3), (2026, 12, 24)):
            content = gc.generate(datetime.date(*parts), write=False)
            for marker in ("\\", "*", "||"):
                self.assertNotIn(marker, content["text"],
                                 "Telegram markup published literally to Threads: %r" % marker)

    def test_a_template_that_de_escapes_to_nothing_is_a_failure_not_an_empty_post(self):
        with mock.patch.object(gc.tg, "TEMPLATES", {"promo": ["**  **"]}), \
                mock.patch.object(gc.tg, "HASHTAGS", {"promo": "#DocOga"}), \
                mock.patch.object(gc.tg, "WEEKLY_SCHEDULE", {day: ["promo"] for day in range(7)}):
            with self.assertRaises(ValueError):
                gc.build(datetime.date(2026, 10, 13), __import__("random").Random("x"))


class ThreadsPublisher(unittest.TestCase):
    TEXT = "Stamp duty in Lagos is 0.78% of the rent, and it is a government tax."

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _routes(self, recent=None, publish=None, extra=None):
        routes = {
            "GET /me": ok({"id": "42", "username": "docogadaily"}),
            "GET /42/threads_publishing_limit": ok({"data": [{"quota_usage": 3,
                                                              "config": {"quota_total": 250}}]}),
            "GET /42/threads": ok({"data": recent or []}),
            "POST /42/threads": ok({"id": "181"}),
            # One URL answers both the container-status poll and the read-back, which is exactly
            # why the body carries `status` *and* `text`: a publisher that reads a field it was
            # not promised should fail here rather than at 08:45 UTC.
            "GET /181": ok({"status": "OK",
                            "permalink": "https://www.threads.net/@docogadaily/post/181",
                            "text": self.TEXT}),
            "POST /42/threads_publish": publish or ok({"id": "181"}),
        }
        routes.update(extra or {})
        return routes

    def _publish(self, routes, argv=None, env_extra=None):
        fake = FakeHttp(routes)
        env, token_path = threads_env(self.tmp)
        if env_extra:
            env.update(env_extra)
        argv = argv if argv is not None else ["--text", self.TEXT, "--token-file", token_path]
        with mock.patch.object(tp, "_request", fake):
            code, out = run_publisher(tp, argv, env)
        return code, out, fake

    def test_a_successful_post_exits_zero_and_shows_the_permalink(self):
        code, out, fake = self._publish(self._routes())
        self.assertEqual(code, 0, out)
        self.assertIn("THREADS_RESULT=sent", out)
        self.assertIn("threads.net/@docogadaily/post/181", out)
        self.assertEqual(len(fake.posts), 2, "container then publish, nothing else: %s" % out)

    def test_a_read_back_mismatch_is_not_a_success(self):
        routes = self._routes(extra={"GET /181": ok({"status": "OK", "permalink": "https://x/1",
                                                     "text": "something else landed"})})
        code, out, _fake = self._publish(routes)
        self.assertEqual(code, 7)
        self.assertIn("read-back mismatch", out)

    def test_the_exact_words_already_on_the_profile_are_refused_without_writing(self):
        routes = self._routes(recent=[{"text": self.TEXT.upper() + "  ",
                                      "permalink": "https://www.threads.net/@docogadaily/post/9"}])
        code, out, fake = self._publish(routes)
        self.assertEqual(code, 0, "a refusal is a success: %s" % out)
        self.assertIn("refused-duplicate", out)
        self.assertIn("post/9", out, "print the permalink that was found, or the reader cannot "
                                     "check the guard's judgement")
        self.assertFalse(fake.wrote_anything(), "a duplicate must not even create a container")

    def test_similar_is_not_a_duplicate(self):
        # The standing rule: a duplicate is this message's own wording, never "close enough".
        routes = self._routes(recent=[{"text": "Stamp duty in Lagos is 0.78% of the rent.",
                                      "permalink": "https://x/1"}])
        code, out, fake = self._publish(routes)
        self.assertEqual(code, 0, out)
        self.assertIn("THREADS_RESULT=sent", out)
        self.assertTrue(fake.wrote_anything())

    def test_an_unreadable_profile_warns_and_posts(self):
        def boom(method, url, query):
            raise tp.ApiError(0, "transport failure: connection reset")
        routes = self._routes(extra={"GET /42/threads": boom})
        code, out, fake = self._publish(routes)
        self.assertEqual(code, 0, out)
        self.assertIn("duplicate guard unavailable", out)
        self.assertTrue(fake.wrote_anything(),
                        "an unverifiable page must never block a legitimate post")

    def test_copy_over_the_limit_is_refused_before_the_platform_sees_it(self):
        env, token_path = threads_env(self.tmp)
        code, out, _fake = self._publish(self._routes(),
                                        ["--text", "x" * 600, "--token-file", token_path])
        self.assertEqual(code, 5)
        self.assertIn("THREADS_CAUSE=copy", out)

    def test_quota_spent_refuses_without_creating_a_container(self):
        routes = self._routes(extra={"GET /42/threads_publishing_limit": ok(
            {"data": [{"quota_usage": 250, "config": {"quota_total": 250}}]})})
        code, out, fake = self._publish(routes)
        self.assertEqual(code, 4)
        self.assertIn("THREADS_CAUSE=quota", out)
        self.assertFalse(fake.wrote_anything())

    def test_a_permission_error_is_classified_as_permission(self):
        routes = self._routes(extra={"POST /42/threads_publish": (400, json.dumps(
            {"error": {"message": "(#200) This app is not approved for this operation",
                      "code": 200}}))})
        code, out, _fake = self._publish(routes)
        self.assertEqual(code, 3)
        self.assertIn("THREADS_CAUSE=permission", out)

    def test_the_token_never_appears_in_output_even_when_meta_echoes_it(self):
        secret = "EAAIlonglivedthreadsaccesstokenvalue123456"

        def boom(method, url, query):
            raise tp.ApiError(400, json.dumps({"error": {
                "message": "Invalid OAuth access token - Cannot parse: %s" % secret, "code": 190}}))
        fake = FakeHttp({"GET /me": boom})
        env, token_path = threads_env(self.tmp, token=secret)
        with mock.patch.object(tp, "_request", fake):
            code, out = run_publisher(tp, ["--probe", "--token-file", token_path], env)
        self.assertNotIn(secret, out, "the error text quoted the credential it was handed")
        self.assertIn("[redacted", out, "the secret is replaced by a marker, and the marker's "
                                        "exact spelling is what the assertion should track")
        self.assertEqual(code, 3)

    def test_probe_writes_nothing(self):
        fake = FakeHttp(self._routes())
        env, token_path = threads_env(self.tmp)
        with mock.patch.object(tp, "_request", fake):
            code, out = run_publisher(tp, ["--probe", "--token-file", token_path], env)
        self.assertEqual(code, 0, out)
        self.assertIn("THREADS_PROBE=ok", out)
        self.assertFalse(fake.wrote_anything())

    def test_no_credential_is_setup_not_an_outage(self):
        code, out = run_publisher(tp, ["--probe"], {})
        self.assertEqual(code, 2)
        self.assertIn("secrets missing", out)

    def test_dry_run_validates_and_sends_nothing(self):
        fake = FakeHttp(self._routes())
        env, token_path = threads_env(self.tmp)
        with mock.patch.object(tp, "_request", fake):
            code, out = run_publisher(tp, ["--text", self.TEXT, "--dry-run",
                                          "--token-file", token_path], env)
        self.assertEqual(code, 0, out)
        self.assertIn("THREADS_RESULT=dry-run", out)
        self.assertFalse(fake.wrote_anything())

    def test_a_refused_refresh_is_the_callers_severity_not_the_tools(self):
        """Meta allows one refresh per 24 h, so the morning after setup the answer is "no".

        That is not a red run, and stdout is the pipe into `token_vault.py seal`: a `::error` or a
        machine line landing in that file would either scare the owner into re-consenting or make
        the seal parse a sentence as JSON. So the failure is reported on stderr only.
        """
        _env, token_path = threads_env(self.tmp)
        routes = self._routes(extra={"GET /42/refresh_access_token": (400, json.dumps(
            {"error": {"message": "Cannot refresh a token that is less than 24 hours old",
                       "code": 100, "type": "OAuthException"}}))})
        code, out, _fake = self._publish(routes, argv=["--refresh", "--token-file", token_path])
        self.assertNotEqual(code, 0, "a refused refresh is still a non-zero tool, so the "
                                    "workflow's `if !` branch runs and prints its warning")
        self.assertNotIn("::error", out, "the severity belongs to the caller, which chose warning")
        self.assertIn("24 hours", out, "the reason has to survive into the warning body, which is "
                                       "the tail of stderr — an empty warning is a worse lie than "
                                       "a red one")

    def test_refresh_hands_json_to_the_caller_and_nothing_else(self):
        routes = self._routes(extra={"GET /42/refresh_access_token": ok(
            {"access_token": "NEWtok", "expires_in": 5184000})})
        fake = FakeHttp(routes)
        env, token_path = threads_env(self.tmp)
        with mock.patch.object(tp, "_request", fake):
            code, out = run_publisher(tp, ["--refresh", "--token-file", token_path], env)
        self.assertEqual(code, 0, out)
        # stdout is piped into `token_vault.py seal`, so it must be *only* JSON: a log line in
        # front of it breaks the seal, and the seal failing quietly is how a lane dies in 60 days.
        self.assertEqual(json.loads(out.strip())["access_token"], "NEWtok")
        self.assertFalse(fake.wrote_anything(), "a refresh is a GET in Meta's design")


class TokenVault(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec("cryptography") is None:
            raise unittest.SkipTest("cryptography is not installed (the lanes pip-install it)")
        import token_vault  # noqa: F401

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.key = "11" * 32
        self.box = str(Path(self.tmp) / "logs" / "threads_token.box")

    def _seal(self, value="tok-value-123", key=None, name="THREADS_TOKEN", cipher=None):
        import token_vault
        env = {"SOCIAL_TOKEN_KEY": key or self.key}
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env, clear=False):
            patches = [contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)]
            with patches[0], patches[1]:
                if cipher is not None:
                    with mock.patch.object(token_vault, "_cipher", cipher):
                        code = token_vault.seal(name, value, expires_at="2099-01-01T00:00:00+00:00",
                                                path=self.box, out=out)
                else:
                    code = token_vault.seal(name, value, expires_at="2099-01-01T00:00:00+00:00",
                                            path=self.box, out=out)
        return code, out.getvalue() + err.getvalue()

    def test_seal_then_open_round_trips(self):
        code, out = self._seal()
        self.assertEqual(code, 0, out)
        import token_vault
        with mock.patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": self.key}):
            plaintext, payload = token_vault.open_box("THREADS_TOKEN", self.box)
        self.assertEqual(plaintext, "tok-value-123")
        self.assertEqual(payload["expires_at"], "2099-01-01T00:00:00+00:00")
        self.assertNotIn("tok-value-123", out, "seal must not echo the value it was handed")

    def test_the_ciphertext_is_not_the_token(self):
        self._seal(value="SUPERSECRETTOKEN")
        text = Path(self.box).read_text(encoding="utf-8")
        self.assertNotIn("SUPERSECRETTOKEN", text)
        self.assertEqual(json.loads(text)["alg"], "A256GCM")
        import base64
        raw = base64.b64decode(json.loads(text)["ciphertext"])
        self.assertNotIn(b"SUPERSECRETTOKEN", raw, "base64 of a token is not a vault")

    def test_a_box_sealed_for_one_lane_does_not_open_as_another(self):
        self._seal(name="THREADS_TOKEN")
        import token_vault
        with mock.patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": self.key}):
            with self.assertRaises(ValueError):
                token_vault.open_box("IG_ACCESS_TOKEN", self.box)

    def test_no_key_is_a_refusal_not_a_plaintext(self):
        import token_vault
        out = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True):
            with contextlib.redirect_stderr(io.StringIO()):
                code = token_vault.seal("THREADS_TOKEN", "tok", path=self.box, out=out)
        self.assertEqual(code, 2)
        self.assertFalse(Path(self.box).exists(),
                         "the one fallback that must never exist is writing the value out raw")

    def test_a_missing_crypto_library_refuses_instead_of_encoding(self):
        code, out = self._seal(cipher=lambda: None)
        self.assertEqual(code, 6)
        self.assertFalse(Path(self.box).exists())
        self.assertIn("refusing", out)

    def test_the_public_directory_is_refused(self):
        import token_vault
        with mock.patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": self.key}):
            with contextlib.redirect_stdout(io.StringIO()):
                code = token_vault.seal("THREADS_TOKEN", "tok", path="site/social/token.box")
        self.assertEqual(code, 5)

    def test_status_counts_down_without_revealing_anything(self):
        self._seal(value="SECRETISH")
        import token_vault
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": self.key}):
            code = token_vault.status("THREADS_TOKEN", self.box, out=out)
        text = out.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("TOKEN_EXPIRES_IN_DAYS=", text)
        self.assertNotIn("SECRETISH", text)

    def test_an_expired_vault_is_an_error_not_a_shrug(self):
        self._seal(value="tok")
        import token_vault
        payload = json.loads(Path(self.box).read_text(encoding="utf-8"))
        payload["expires_at"] = "2020-01-01T00:00:00+00:00"
        Path(self.box).write_text(json.dumps(payload), encoding="utf-8")
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": self.key}):
            code = token_vault.status("THREADS_TOKEN", self.box, out=out)
        self.assertEqual(code, 4)
        self.assertIn("expired", out.getvalue())

    def test_a_seal_from_a_refresh_response_carries_the_new_expiry(self):
        import token_vault
        path = Path(self.tmp) / "refresh.json"
        path.write_text(json.dumps({"access_token": "T", "expires_in": 5184000}), encoding="utf-8")
        args = mock.Mock(stdin=False, json=str(path), expires_at=None)
        with mock.patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": self.key}), \
                mock.patch.object(sys, "stdin", io.StringIO()), \
                mock.patch.object(token_vault, "_read_plaintext", lambda a: json.dumps(
                    {"access_token": "T", "expires_in": 5184000})):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = token_vault.seal("THREADS_TOKEN", json.dumps({"access_token": "T"}),
                                       expires_at=None, path=self.box, out=out)
        self.assertEqual(code, 0)
        self.assertIn("A256GCM", Path(self.box).read_text(encoding="utf-8"))


@unittest.skipUnless(HAS_PIL, "Pillow is what draws the card")
class CardRenderer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def render(self, text, name="card.jpg"):
        out = Path(self.tmp) / "site" / "social" / name
        result = social_card.render(text, out, kicker="promo")
        return result, out

    def test_the_card_is_exactly_the_ratio_the_api_takes(self):
        _result, out = self.render("Stamp duty in Lagos is 0.78% of the rent.")
        spec = ig.jpeg_spec(out.read_bytes())
        self.assertEqual(spec, (1080, 1350, "jpeg"))
        ratio = spec[0] / float(spec[1])
        self.assertGreaterEqual(ratio, ig.ASPECT_MIN - 1e-6)
        self.assertLessEqual(ratio, ig.ASPECT_MAX + 1e-6)

    def test_renderer_and_gate_agree_by_construction(self):
        # If someone changes the canvas without the gate (or the reverse), this fails here rather
        # than in a 09:00 UTC run whose only symptom is "Unsupported URL request".
        result, out = self.render("A" * 400, "long.jpg")
        self.assertLess(result["bytes"], ig.MAX_IMAGE_BYTES)
        width, height, fmt = ig.jpeg_spec(out.read_bytes())
        self.assertEqual(fmt, "jpeg")
        self.assertTrue(ig.ASPECT_MIN <= width / float(height) <= ig.ASPECT_MAX)

    def test_emoji_are_stripped_from_the_picture_and_kept_in_the_caption(self):
        drawn = social_card.plain_for_card("\U0001f3db️ Stamp Duty on Tenancy \U0001f4c4")
        self.assertNotIn("\U0001f3db", drawn)
        self.assertIn("Stamp Duty", drawn)

    def test_hashtags_are_furniture_for_the_caption_not_the_card(self):
        dropped = social_card._drop_hashtags("Rent is due on the first.\n\n#DocOga #Nigeria")
        self.assertNotIn("#DocOga", dropped)
        self.assertIn("Rent is due", dropped)
        # And the render keeps the whole sentence: dropping tags must not drop the point.
        _result, out = self.render("Rent is due on the first.\n\n#DocOga #Nigeria")
        self.assertTrue(out.exists())

    def test_a_header_without_sof_is_reported_not_guessed(self):
        self.assertEqual(ig.jpeg_spec(b"GIF89a" + b"\x00" * 100), (None, None, "not-jpeg"))


def jpeg_bytes(width=1080, height=1350):
    """A media file Instagram's rules can be checked against, with no file and no network.

    SOI + JFIF + SOF0 carrying the dimensions, which is all `jpeg_spec` reads.
    """
    return (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xc0\x00\x11\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big")
            + b"\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01")


class InstagramPublisher(unittest.TestCase):
    CAPTION = "Stamp duty in Lagos is 0.78% of the rent, a government tax."

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = {"IG_ACCESS_TOKEN": "IGTOKabc123", "IG_USER_ID": "1784",
                    "IG_API_PATH": "instagram-login"}
        # `media_spec_ok` reads the media with plain urllib, so faking `http` does NOT cover it.
        # That gap cost a day: this sandbox cannot resolve docoga.com.ng, so a test that reached
        # for the real URL passed here and failed on a runner that can — where the real 404 made
        # the lane refuse before publishing. The default now raises instead: forgetting the seam
        # fails in every environment, which is the only kind of test worth having.
        patcher = mock.patch.object(ig, "raw_head", side_effect=AssertionError(
            "a test asked the internet for a media file: call self.public_media() first"))
        # `.start()` returns the mock; `patch.object(...)` returns the *patcher*, and a patcher
        # happily accepts `patcher.side_effect = None` without touching the mock — which is how
        # this file managed to configure a stub that was never in effect.
        self.head = patcher.start()
        self.addCleanup(patcher.stop)
        self.public_media()

    def public_media(self, width=1080, height=1350, status=200):
        """What the media server says about the card, injected rather than fetched."""
        body = jpeg_bytes(width, height)
        self.head.side_effect = None
        self.head.return_value = (status, {"Content-Length": str(len(body))}, body)

    def _base_routes(self, extra=None):
        routes = {
            "GET /me": (200, json.dumps({"user_id": "1784", "username": "docogadaily",
                                         "profile_type": "BUSINESS", "media_count": 12})),
            "GET /1784/content_publishing_limit": (200, json.dumps(
                {"data": [{"quota_usage": 2, "config": {"quota_total": 100}}]})),
            "GET /1784/media": (200, json.dumps({"data": []})),
            "POST /1784/media": (200, json.dumps({"id": "CONT"})),
            "GET /CONT": (200, json.dumps({"status_code": "FINISHED"})),
            "POST /1784/media_publish": (200, json.dumps({"id": "MEDIA9"})),
            "GET /MEDIA9": (200, json.dumps({"permalink": "https://www.instagram.com/p/MEDIA9/"})),
        }
        routes.update(extra or {})
        return routes

    def _publish(self, routes, argv, env_extra=None):
        fake = FakeHttp(routes, shape=3)
        env = dict(self.env)
        env.update(env_extra or {})
        with mock.patch.object(ig, "http", fake):
            code, out = run_publisher(ig, argv, env)
        return code, out, fake

    def test_a_successful_card_exits_zero_with_a_permalink(self):
        code, out, fake = self._publish(self._base_routes(),
                                       ["--image-url", "https://docoga.com.ng/social/x.jpg",
                                        "--caption", self.CAPTION, "--allow-unknown-specs"])
        self.assertEqual(code, 0, out)
        self.assertIn("IG_RESULT=sent", out)
        self.assertIn("instagram.com/p/MEDIA9/", out)
        self.assertEqual(len(fake.posts), 2)

    def test_a_failed_publish_is_a_failed_run(self):
        """The bug this file was rewritten for: `return None` from main() exited 0."""
        routes = self._base_routes({"POST /1784/media_publish": (400, json.dumps(
            {"error": {"message": "(#90) Missing permissions", "code": 200}}))})
        code, out, _fake = self._publish(routes,
                                        ["--image-url", "https://x/y.jpg", "--caption",
                                         self.CAPTION, "--allow-unknown-specs"])
        self.assertNotEqual(code, 0, "a red day must not wear a green tick")
        self.assertIn("IG_RESULT=failed", out)
        self.assertIn("IG_CAUSE=permission", out)

    def test_media_rejected_before_the_container_exists(self):
        # The *file* is what is wrong here, so the fake says "a 1080x2400 JPEG" and the real
        # media_spec_ok does the judging. Stubbing the judgement would only test the stub.
        self.public_media(width=1080, height=2400)
        code, out, fake = self._publish(self._base_routes(),
                                       ["--image-url", "https://x/y.jpg",
                                        "--caption", self.CAPTION])
        self.assertEqual(code, 5, out)
        self.assertIn("media", out)
        self.assertIn("0.450:1", out, "the refusal should quote the ratio a human can verify")
        self.assertFalse(fake.wrote_anything(),
                         "the API must never see a URL we already know is bad; Meta's answer to "
                         "a bad media URL is a sentence about permissions")

    def test_an_exact_caption_already_on_the_account_is_refused_without_writing(self):
        routes = self._base_routes({"GET /1784/media": (200, json.dumps({"data": [
            {"id": "1", "caption": self.CAPTION + "  ",
             "permalink": "https://www.instagram.com/p/OLD/"}]}))})
        code, out, fake = self._publish(routes, ["--image-url", "https://x/y.jpg",
                                                "--caption", self.CAPTION,
                                                "--allow-unknown-specs"])
        self.assertEqual(code, 0)
        self.assertIn("refused-duplicate", out)
        self.assertIn("instagram.com/p/OLD/", out)
        self.assertFalse(fake.wrote_anything())

    def test_a_personal_account_is_refused_with_the_real_reason(self):
        routes = self._base_routes({"GET /me": (200, json.dumps(
            {"user_id": "1784", "username": "me", "profile_type": "PERSONAL"}))})
        code, out, _fake = self._publish(routes, ["--probe"])
        self.assertEqual(code, 3)
        self.assertIn("professional", out.lower())

    def test_refresh_never_prints_the_credential_it_used(self):
        routes = self._base_routes({"GET /access_token": (200, json.dumps(
            {"access_token": "NEwTOKENvalue", "expires_in": 5184000}))})
        code, out, _fake = self._publish(routes, ["--refresh-token"])
        self.assertEqual(code, 0, out)
        self.assertNotIn("IGTOKabc123", out, "the old code printed the first 20 characters of the "
                                            "current token into the run log")
        self.assertNotIn("New token: NEwTOKENvalue", out)
        self.assertIn("fingerprint", out)

    def test_a_url_that_404s_is_media_and_not_permissions(self):
        """Meta says "Unsupported URL request"; a 404 is a file *we* did not deploy.

        Reading a missing file as a scope problem is how this lane got abandoned once, so the
        cause has to survive from media_spec_ok all the way to the run summary.
        """
        self.public_media(status=404)
        code, out, fake = self._publish(self._base_routes(),
                                       ["--image-url", "https://docoga.com.ng/social/x.jpg",
                                        "--caption", self.CAPTION])
        self.assertEqual(code, 5, out)
        self.assertIn("IG_CAUSE=media", out)
        self.assertNotIn("permission", out.lower(), "a 404 must not be dressed up as a scope problem")
        self.assertFalse(fake.wrote_anything())

    def test_the_url_is_waited_for_because_git_is_ahead_of_the_web(self):
        statuses = iter([404, 404, 200])
        lived, waited = ig.wait_until_live("https://docoga.com.ng/social/x.jpg",
                                          deadline_seconds=90, delay=15,
                                          sleeper=lambda s: None, opener=lambda url: next(statuses))
        self.assertTrue(lived)
        self.assertEqual(waited, 30)
        dead, waited = ig.wait_until_live("https://docoga.com.ng/social/x.jpg", deadline_seconds=30,
                                         delay=15, sleeper=lambda s: None, opener=lambda u: 404)
        self.assertFalse(dead, "a deadline that never expires is a hung job, not a wait")

    def test_jpeg_spec_reads_the_header_the_standard_way(self):
        header = (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
                  b"\xff\xc0\x00\x11\x08" + (1350).to_bytes(2, "big") + (1080).to_bytes(2, "big")
                  + b"\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01")
        self.assertEqual(ig.jpeg_spec(header), (1080, 1350, "jpeg"))
        self.assertEqual(ig.jpeg_spec(b"\xff\xd8\xff\xda" + b"\x00" * 40), (None, None, "no-SOF"))

    def test_the_two_login_paths_use_two_hosts_and_two_refresh_grants(self):
        self.assertTrue(ig.GRAPH_INSTAGRAM.startswith("https://graph.instagram.com/"))
        with mock.patch.dict(os.environ, {"IG_API_PATH": "facebook-login"}):
            self.assertEqual(ig.base_url(), ig.GRAPH_FACEBOOK)
        with mock.patch.dict(os.environ, {"IG_API_PATH": "instagram-login"}):
            self.assertEqual(ig.base_url(), ig.GRAPH_INSTAGRAM)

    def test_a_local_file_is_refused_rather_than_mimed(self):
        """`--reel social/x.mp4` cannot work: the API fetches URLs. Say so in one line."""
        code, out, fake = self._publish(self._base_routes(),
                                       ["--reel", "social/x.mp4", "--caption", self.CAPTION])
        self.assertEqual(code, 5)
        self.assertIn("public URL", out)
        self.assertFalse(fake.wrote_anything())

    def test_no_credential_is_setup(self):
        code, out = run_publisher(ig, ["--probe"], {})
        self.assertEqual(code, 2, "setup is exit 2, not a red API failure the owner misreads")
        self.assertIn("secrets missing", out)
        self.assertIn("IG_CAUSE=setup", out)


class LaneShell(unittest.TestCase):
    """The workflow shell is executed, not grepped."""

    def _truth_snippet(self):
        text = (WORKFLOWS / "threads_autopost.yml").read_text(encoding="utf-8")
        start = text.index('FORCE_ON=""')
        end = text.index("esac", start) + len("esac")
        return text[start:end]

    def _evaluate(self, value):
        script = self._truth_snippet() + '\nprintf "%s" "${FORCE_ON:-}"\n'
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                              env={**os.environ, "THREADS_FORCE": value})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def test_actions_booleans_are_strings_and_false_is_not_true(self):
        for truthy in ("true", "True", "yes", "1", "on"):
            with self.subTest(value=truthy):
                self.assertEqual(self._evaluate(truthy), "1")
        for falsey in ("false", "False", "", "no"):
            with self.subTest(value=falsey):
                self.assertEqual(self._evaluate(falsey), "",
                                 '`-n "false"` is true, which turns a skip-guard into a '
                                 "duplicate-posting guard")

    def test_every_workflow_step_is_valid_bash(self):
        import yaml
        problems = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            for job in (doc or {}).get("jobs", {}).values():
                for step in job.get("steps", []) or []:
                    run = step.get("run")
                    if not run:
                        continue
                    substituted = re.sub(r"\$\{\{[^}]*\}\}", "SAFEVALUE", run)
                    proc = subprocess.run(["bash", "-n"], input=substituted,
                                          capture_output=True, text=True)
                    if proc.returncode:
                        problems.append("%s/%s: %s" % (path.name, step.get("name", "?"),
                                                        proc.stderr.strip()[:120]))
        self.assertEqual(problems, [], "a syntax error in one step costs the day's post, and the "
                                       "Actions UI points at the last heredoc, not the mistake: %s"
                         % "; ".join(problems[:3]))

    def test_no_input_is_interpolated_into_a_shell_test(self):
        offenders = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r'\[\s-[nz]\s*"\$\{\{[^}]*\}\}"', text):
                offenders.append("%s: %s" % (path.name, match.group(0)))
        self.assertEqual(offenders, [], "an input inside [ -n … ] is shell code with secrets in "
                                       "scope; pass it through the step's env")

    def test_the_lanes_ask_before_they_write(self):
        """Order is the invariant: ledger (offline) first, then the platform, then the send."""
        for name, ledger in (("threads_autopost.yml", "logs/threads_sent.json"),
                             ("instagram_autopost.yml", "logs/instagram_sent.json")):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            with self.subTest(lane=name):
                # Step *names*, not first mention of a filename: these workflows' headers discuss
                # both tools, and prose has no execution order.
                self.assertLess(text.index("name: Ledger"), text.index("name: Publish to "),
                                "the ledger is read first because it is free and still works when "
                                "the platform does not")
                self.assertIn(ledger, text[text.index("name: Ledger"):text.index("name: Publish to ")])

    def test_the_lane_pipes_the_refresh_into_the_vault_and_erases_the_plaintext(self):
        for name, refresh, box in (("threads_autopost.yml", "/tmp/threads_refresh.json",
                                    "logs/threads_token.box"),
                                   ("instagram_autopost.yml", "/tmp/ig_refresh.json",
                                    "logs/ig_access_token.box")):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            with self.subTest(lane=name):
                self.assertIn("> " + refresh, text, "stdout must be redirected, or the new token "
                                                    "is printed into the run log")
                self.assertIn("rm -f " + refresh, text, "and the plaintext has to go, in both the "
                                                         "success and the failure branch")
                self.assertIn(box, text)


class LaneRegistration(unittest.TestCase):
    def test_lane_status_can_read_both_new_lanes(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import lane_status
        self.assertEqual(lane_status.LANES["threads"], "threads_autopost.yml")
        self.assertEqual(lane_status.LANES["instagram"], "instagram_autopost.yml")

    def test_the_handbook_exists_and_states_the_four_things_a_tutorial_gets_wrong(self):
        doc = ROOT / "docs" / "INSTAGRAM_THREADS_AUTOMATION.md"
        self.assertTrue(doc.exists(), "an owner-facing lane without a handbook is a lane that gets "
                                      "set up wrong once and then silently")
        if not doc.exists():
            return
        text = doc.read_text(encoding="utf-8").lower()
        for fact in ("standard access", "60-day", "site/social", "professional account",
                    "graph.threads.net"):
            self.assertIn(fact, text, "the handbook has to state the thing that is commonly wrong")

    def test_the_runbook_no_longer_says_instagram_cannot_run(self):
        text = (ROOT / "docs" / "LAUNCH_SEQUENCE.md").read_text(encoding="utf-8")
        self.assertNotIn("never (dispatch only)", text,
                         "step 1's table still promises Instagram will do nothing")
        self.assertIn("threads", text.lower(), "the launch sequence must include the new lane")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class VaultPipeline(unittest.TestCase):
    """seal → open → the bytes the next run authenticates with, across real processes.

    Every test in this file before it was written exercised *one verb* in one process, and the
    vault had a bug that only exists between two of them: `seal --json` stored Meta's whole
    response body, `open --out` wrote that body into the token file, and the publisher sent it as
    a bearer token. Day 1 posts (the bootstrap secret is a bare token), day 2 is red with
    `code 190 Invalid OAuth access token`, forever alternating — invisible to any single-call test
    and to any in-process test, because nothing in one process has to agree with anything.
    """

    VAULT = ROOT / "tools" / "token_vault.py"

    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec("cryptography") is None:
            raise unittest.SkipTest("cryptography is not installed (the lanes pip-install it)")

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.key = "ab" * 32
        self.box = self.tmp / "logs" / "threads_token.box"

    def _run(self, argv):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "SOCIAL_TOKEN_KEY": self.key}
        done = subprocess.run([sys.executable, str(self.VAULT)] + argv, capture_output=True,
                              text=True, env=env, cwd=str(ROOT), timeout=60,
                              # A `--stdin` verb with an inherited stdin is a test that
                              # hangs the suite until CI kills the job.
                              stdin=subprocess.DEVNULL)
        return done.returncode, done.stdout, done.stderr

    def test_seal_json_then_open_yields_the_bare_token_and_nothing_else(self):
        refresh = self.tmp / "refresh.json"
        refresh.write_text(json.dumps({"access_token": "AAA-fresh-token",
                                       "token_type": "bearer", "expires_in": 5184000}),
                           encoding="utf-8")
        code, out, err = self._run(["seal", "--name", "THREADS_TOKEN", "--json", str(refresh),
                                    "--in", str(self.box)])
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("refresh token was dropped", err, "nothing was dropped from this response")

        token_file = self.tmp / "next_run_token"
        code, out, err = self._run(["open", "--name", "THREADS_TOKEN", "--in", str(self.box),
                                    "--out", str(token_file)])
        self.assertEqual(code, 0, out + err)
        raw = token_file.read_text(encoding="utf-8")
        self.assertEqual(raw, "AAA-fresh-token",
                         "this exact string is what the lane sends as its bearer token")
        self.assertNotIn("{", raw, "a JSON body here is a 401 on the next run, not a style "
                                   "preference")
        self.assertNotIn("AAA-fresh-token", out + err, "opening a vault must not print the token")

    def test_the_expiry_reaches_the_summary_from_a_json_seal(self):
        """Without this the lane says nothing about the 60-day clock it is supposed to be winding."""
        refresh = self.tmp / "refresh.json"
        refresh.write_text(json.dumps({"access_token": "AAA", "expires_in": 5184000}),
                           encoding="utf-8")
        self._run(["seal", "--name", "THREADS_TOKEN", "--json", str(refresh), "--in", str(self.box)])
        code, out, _err = self._run(["status", "--name", "THREADS_TOKEN", "--in", str(self.box)])
        self.assertEqual(code, 0, out)
        self.assertIn("TOKEN_EXPIRES_IN_DAYS=59", out, "60 days minus the day it was sealed")

    def test_a_box_sealed_as_a_json_body_still_opens(self):
        """Tolerance for the shape the previous version wrote, so a lane self-heals."""
        import token_vault
        legacy_box = self.tmp / "legacy.box"
        with mock.patch.dict(os.environ, {"SOCIAL_TOKEN_KEY": self.key}):
            token_vault.seal("THREADS_TOKEN", json.dumps({"access_token": "LEGACY-token",
                                                          "refresh_token": None,
                                                          "expires_in": 5184000}),
                             path=str(legacy_box), out=io.StringIO())
        token_file = self.tmp / "tok"
        code, _out, err = self._run(["open", "--name", "THREADS_TOKEN", "--in", str(legacy_box),
                                     "--out", str(token_file)])
        self.assertEqual(code, 0, err)
        self.assertEqual(token_file.read_text(encoding="utf-8"), "LEGACY-token")
        self.assertIn("unwrapped", err, "and it says what it did, rather than silently patching "
                                        "over a box nobody will ever re-seal")

    def test_a_dropped_refresh_token_is_announced(self):
        refresh = self.tmp / "refresh.json"
        refresh.write_text(json.dumps({"access_token": "AAA", "refresh_token": "RRR",
                                       "expires_in": 5184000}), encoding="utf-8")
        code, _out, err = self._run(["seal", "--name", "THREADS_TOKEN", "--json", str(refresh),
                                     "--in", str(self.box)])
        self.assertEqual(code, 0, err)
        self.assertIn("refresh token was dropped", err, "the vault keeps one secret on purpose; "
                                                         "if the platform ever needs two, that has "
                                                         "to be a message and not a 401")

    def test_an_empty_stdin_is_refused_rather_than_sealed(self):
        """A `$(…)` that came back empty used to become a perfectly valid box of nothing."""
        code, _out, err = self._run(["seal", "--name", "THREADS_TOKEN", "--stdin",
                                     "--in", str(self.box)])
        self.assertEqual(code, 5, err)
        self.assertIn("empty", err)
        self.assertFalse(self.box.exists(), "a box of nothing is worse than no box: it wins the "
                                            "fallback race against the bootstrap secret")


class RenderRetention(unittest.TestCase):
    """`site/social/` is inside the deployed tree, so the lane has to bound it.

    The interesting property is not "old files go" — it is that *old* is decided by filename,
    because a CI checkout gives every file today's mtime and a `find -mtime` step would pass every
    test here and never delete anything on a runner.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _make(self, *names):
        for name in names:
            (self.tmp / name).write_bytes(jpeg_bytes())
        return self.tmp

    def test_the_newest_by_name_survive_and_the_rest_go(self):
        d = self._make(*["2026-09-%02d-instagram.jpg" % day for day in range(1, 12)],
                       "2026-10-01-instagram.jpg", "2026-10-02-instagram.jpg")
        deleted, kept = social_card.prune(d, keep=3)
        self.assertEqual(sorted(kept), ["2026-09-11-instagram.jpg", "2026-10-01-instagram.jpg",
                                        "2026-10-02-instagram.jpg"])
        # Thirteen dated renders in, three kept, so ten gone. The `kept` names above and this
        # count are the same fact stated twice, which is the only reason a wrong expectation on
        # either end gets caught rather than agreed with.
        self.assertEqual(len(deleted), 10)
        self.assertFalse((d / "2026-09-01-instagram.jpg").exists())

    def test_a_checkout_that_resets_every_mtime_does_not_fool_it(self):
        """The whole reason this is not `find -mtime +60`."""
        d = self._make(*["2020-01-%02d-instagram.jpg" % day for day in range(1, 6)])
        now = time.time()
        for path in d.iterdir():
            os.utime(path, (now, now))          # what `actions/checkout` effectively does
        deleted, kept = social_card.prune(d, keep=2)
        self.assertEqual(len(deleted), 3, "the dates are 2020; a mtime rule would keep all five")
        self.assertEqual(len(kept), 2)

    def test_files_the_lane_did_not_name_are_left_alone(self):
        d = self._make(*["2026-09-%02d-instagram.jpg" % day for day in range(1, 6)])
        (d / "brand-mark.jpg").write_bytes(jpeg_bytes())
        (d / "2026-09-30-threads.jpg").write_bytes(jpeg_bytes())
        deleted, _kept = social_card.prune(d, keep=1)
        self.assertNotIn("brand-mark.jpg", deleted)
        self.assertNotIn("2026-09-30-threads.jpg", deleted,
                         "another lane's render is not this lane's to delete")
        self.assertTrue((d / "brand-mark.jpg").exists())

    def test_todays_own_card_cannot_be_pruned(self):
        """`keep` is floored at 1: pruning the file about to be handed to Meta is a 404 that
        reads like a permissions problem."""
        d = self._make("2026-10-13-instagram.jpg")
        deleted, kept = social_card.prune(d, keep=0)
        self.assertEqual(deleted, [])
        self.assertEqual(len(kept), 1)

    def test_the_lanes_step_runs_the_pruner_and_skips_ci_for_housekeeping(self):
        text = (ROOT / ".github/workflows/instagram_autopost.yml").read_text(encoding="utf-8")
        self.assertIn("python3 tools/social_card.py --prune site/social --keep 60", text)
        head = text.split("Auto: prune Instagram renders", 1)
        self.assertEqual(len(head), 2, "the prune commit has to say what it is")
        self.assertIn("[skip ci]", head[1][:60], "a deletion nobody is waiting for must not spend "
                                                 "a site deploy")
        self.assertLess(text.index("- name: Prune old renders"),
                        text.index("- name: Open a visible issue"),
                        "pruning is housekeeping on a good day: it must not run before the "
                        "publish it is cleaning up after, or a failed publish loses the file that "
                        "would have explained it")
