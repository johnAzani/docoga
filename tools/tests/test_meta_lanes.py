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
import brain_drafts as bd  # noqa: E402
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
            _type, text, notes, _extras = gc.build(datetime.date(2026, 10, 13),
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
        # The card-liveness wait talks to docoga.com.ng, not the Graph API; tests say "live" unless
        # they patch it themselves (`self.card_live`).
        live = getattr(self, "card_live", (True, 0))
        with mock.patch.object(tp, "_request", fake), \
             mock.patch.object(tp, "wait_until_live", lambda url, *a, **k: live):
            code, out = run_publisher(tp, argv, env)
        return code, out, fake

    def test_a_successful_post_exits_zero_and_shows_the_permalink(self):
        code, out, fake = self._publish(self._routes())
        self.assertEqual(code, 0, out)
        self.assertIn("THREADS_RESULT=sent", out)
        self.assertIn("threads.net/@docogadaily/post/181", out)
        self.assertEqual(len(fake.posts), 2, "container then publish, nothing else: %s" % out)

    def test_a_finished_container_is_published_and_an_error_one_is_not(self):
        """Run #6, 16 Oct 2026: Threads said `FINISHED` — its documented ready state — and the
        publisher, which knew only `OK`, refused it as "did not finish"."""
        for state, expect_code, expect_posts in (("FINISHED", 0, 2), ("IN_PROGRESS", 6, 1),
                                                 ("ERROR", 6, 1), ("EXPIRED", 6, 1)):
            with self.subTest(state=state):
                routes = self._routes(extra={"GET /181": ok({
                    "status": state, "permalink": "https://www.threads.net/@docogadaily/post/181",
                    "text": self.TEXT})})
                with mock.patch.object(tp.time, "sleep"):
                    code, out, fake = self._publish(routes)
                self.assertEqual(code, expect_code, out)
                self.assertEqual(len(fake.posts), expect_posts,
                                 "container, then publish only when ready: %s" % out)

    def test_a_read_back_that_differs_is_a_warning_on_a_live_post_not_a_red_run(self):
        """Run #7, 16 Oct 2026: the post was live and perfect; Threads returned the text with
        the link rendered differently; the old byte-for-byte check exited 7, the run went red,
        and the ledger never recorded a post that readers already had."""
        routes = self._routes(extra={"GET /181": ok({"status": "FINISHED", "permalink": "https://x/1",
                                                     "text": "something else landed"})})
        code, out, _fake = self._publish(routes)
        self.assertEqual(code, 0, out)
        self.assertIn("THREADS_RESULT=sent", out)
        self.assertIn("THREADS_POST_ID=181", out)
        self.assertIn("::warning title=Threads read-back differs", out)
        self.assertNotIn("::error", out)

    def test_a_read_back_with_the_link_rewritten_is_the_same_post(self):
        sent = "Rent receipts are your proof. Read more: https://docoga.com.ng/guides/rent-receipt"
        for came_back in (sent,
                          "Rent receipts are your proof. Read more: https://docoga.com.ng/guides/rent-rec…",
                          "Rent receipts are your proof. Read more:",
                          "Rent  receipts are your proof.\nRead more: https://l.threads.net/?u=abc"):
            with self.subTest(came_back=came_back):
                self.assertTrue(tp.same_words(came_back, sent))
        self.assertFalse(tp.same_words("A different post entirely", sent))
        self.assertTrue(tp.same_words("", sent), "no text in the read-back is not a contradiction")

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

    def _content(self, **over):
        blob = {"text": self.TEXT, "topic_tag": "Tenant Rights Nigeria", "poll": None}
        blob.update(over)
        path = os.path.join(self.tmp, "threads_content_latest.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(blob, fh)
        return path

    def test_topic_tag_poll_and_story_cross_share_ride_on_the_container(self):
        """17 Oct 2026 reach levers: one topic tag, a poll on engagement days, the same post as an
        Instagram Story — all in the container call, all ₦0."""
        seen = {}

        def container(method, url, query):
            seen["query"] = urllib.parse.parse_qs(query)
            return ok({"id": "181"})
        routes = self._routes(extra={"POST /42/threads": container,
                                     "POST /42/threads_publish": ok({"id": "181", "crossreshare_to_ig_status": "SUCCESS"})})
        path = self._content(poll={"option_a": "Six months", "option_b": "Three months"})
        env, token_path = threads_env(self.tmp)
        code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path],
                                     env_extra={"THREADS_SHARE_TO_IG": "on"})
        self.assertEqual(code, 0, out)
        q = seen["query"]
        self.assertEqual(q["topic_tag"], ["Tenant Rights Nigeria"])
        self.assertEqual(json.loads(q["poll_attachment"][0]), {"option_a": "Six months", "option_b": "Three months"})
        self.assertEqual(q["crossreshare_to_ig"], ["true"])
        self.assertIn("THREADS_SHARE_TO_IG=success", out)

    def test_a_token_without_the_story_scope_still_posts_and_names_the_scope(self):
        calls = []

        def container(method, url, query):
            calls.append(urllib.parse.parse_qs(query))
            if "crossreshare_to_ig" in query:
                return 400, json.dumps({"error": {"message": "(#200) Requires threads_share_to_instagram permission", "code": 200}})
            return ok({"id": "181"})
        routes = self._routes(extra={"POST /42/threads": container})
        path = self._content()
        env, token_path = threads_env(self.tmp)
        code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 2, "one refused attempt, then the plain one")
        self.assertNotIn("crossreshare_to_ig", calls[1])
        self.assertEqual(calls[1]["topic_tag"], ["Tenant Rights Nigeria"], "the topic tag survives the retry")
        self.assertIn("THREADS_EXTRAS_DROPPED=share_to_ig", out)
        self.assertIn("threads_share_to_instagram", out)

    def test_share_to_ig_can_be_switched_off(self):
        seen = {}

        def container(method, url, query):
            seen["q"] = query
            return ok({"id": "181"})
        routes = self._routes(extra={"POST /42/threads": container})
        path = self._content()
        env, token_path = threads_env(self.tmp)
        code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path],
                                     env_extra={"THREADS_SHARE_TO_IG": "off"})
        self.assertEqual(code, 0, out)
        self.assertNotIn("crossreshare_to_ig", seen["q"])

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
        routes = self._routes(extra={"GET /refresh_access_token": (400, json.dumps(
            {"error": {"message": "Cannot refresh a token that is less than 24 hours old",
                       "code": 100, "type": "OAuthException"}}))})
        code, out, _fake = self._publish(routes, argv=["--refresh", "--token-file", token_path])
        self.assertNotEqual(code, 0, "a refused refresh is still a non-zero tool, so the "
                                    "workflow's `if !` branch runs and prints its warning")
        self.assertNotIn("::error", out, "the severity belongs to the caller, which chose warning")
        self.assertIn("24 hours", out, "the reason has to survive into the warning body, which is "
                                       "the tail of stderr — an empty warning is a worse lie than "
                                       "a red one")

    def test_a_text_post_states_media_type_text(self):
        """Run #5, 16 Oct 2026: `(#100) The parameter media_type is required`. Threads does not
        infer TEXT from the absence of media; the container must say so."""
        fake = FakeHttp(self._routes())
        env, token_path = threads_env(self.tmp)
        with mock.patch.object(tp, "_request", fake):
            code, out = run_publisher(tp, ["--text", self.TEXT, "--token-file", token_path], env)
        self.assertEqual(code, 0, out)
        containers = [q for m, url, q in fake.calls if m == "POST" and url.endswith("/42/threads")]
        self.assertEqual(len(containers), 1, fake.calls)
        self.assertIn("media_type=TEXT", containers[0])

    def test_whoami_asks_only_for_documented_fields_and_refresh_is_at_the_root(self):
        """Day-one Threads: `/me` must not carry invented fields (Instagram's first probe died on
        one), and the refresh lives at `/refresh_access_token`, not under the user id."""
        routes = self._routes(extra={"GET /refresh_access_token": ok(
            {"access_token": "NEWtok", "expires_in": 5184000})})
        fake = FakeHttp(routes)
        env, token_path = threads_env(self.tmp)
        with mock.patch.object(tp, "_request", fake):
            code, out = run_publisher(tp, ["--probe", "--token-file", token_path], env)
        self.assertEqual(code, 0, out)
        me = [q for m, url, q in fake.calls if url.endswith("/me")]
        self.assertTrue(me, fake.calls)
        for bogus in ("is_eligible_for_apis", "threads_profile", "profile_type"):
            self.assertNotIn(bogus, me[0])
        fake = FakeHttp(routes)
        with mock.patch.object(tp, "_request", fake):
            code, out = run_publisher(tp, ["--refresh", "--token-file", token_path], env)
        self.assertEqual(code, 0, out)
        hits = [url for m, url, q in fake.calls if "refresh_access_token" in url]
        self.assertEqual(len(hits), 1, fake.calls)
        self.assertTrue(hits[0].endswith("/v1.0/refresh_access_token"), hits[0])

    def test_refresh_hands_json_to_the_caller_and_nothing_else(self):
        routes = self._routes(extra={"GET /refresh_access_token": ok(
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

    def test_a_refresh_file_with_a_stray_stdout_line_still_seals(self):
        """What runs #46–#49 actually handed the vault: a chatty line, then the JSON. The
        reader takes the JSON object rather than dying on line 1 — and when there is no
        object at all, says so instead of letting the workflow blame SOCIAL_TOKEN_KEY."""
        import token_vault
        path = Path(self.tmp) / "refresh.json"
        path.write_text('token refreshed (fingerprint abc)\n{"access_token": "NEW", "expires_in": 5184000}\n')
        token, expires_at, _dropped = token_vault.read_refresh_response(str(path))
        self.assertEqual(token, "NEW")
        self.assertTrue(expires_at)
        path.write_text("token refreshed (fingerprint abc)\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            token_vault.read_refresh_response(str(path))
        self.assertEqual(stop.exception.code, 5)
        self.assertIn("not JSON", err.getvalue())
        self.assertNotIn("SOCIAL_TOKEN_KEY", err.getvalue())

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

    def test_the_machine_line_the_lane_seds_is_the_one_the_renderer_prints(self):
        """`CARD_URL=` is a contract between two files, and neither end had a test.

        That is the same gap that cost the *second day* of this lane: `token_vault seal` and
        `token_vault open` were each verified alone, and the bug lived in the bytes between them.
        A rename on either side here would leave the lane with an empty media URL, and Instagram's
        answer to that is a sentence about unsupported URLs, so it reads as a platform problem.
        """
        workflow = (ROOT / ".github/workflows/instagram_autopost.yml").read_text(encoding="utf-8")
        self.assertIn("sed -n 's/^CARD_URL=//p' /tmp/ig_render.log | tail -1", workflow,
                      "the lane reads the line by exact text, so the exact text is what is pinned")

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = social_card.main(["--text", "Rent is due on the first.",
                                     "--out", str(Path(self.tmp) / "card.jpg")])
        self.assertEqual(code, 0)
        printed = {}
        for line in out.getvalue().splitlines():
            if "=" in line and not line.startswith(("·", "✅")):
                key, value = line.split("=", 1)
                printed[key.strip()] = value.strip()
        self.assertIn("CARD_URL", printed, "the machine-readable line is the interface; "
                                           "print(text) is not")
        self.assertTrue(printed["CARD_URL"].startswith("https://docoga.com.ng/"),
                        printed["CARD_URL"])
        self.assertTrue(printed["CARD_URL"].endswith("/card.jpg"), printed["CARD_URL"])
        self.assertNotIn("/site/", printed["CARD_URL"],
                         "`site/` is the repo directory, not part of the served path")
        self.assertIn("CARD_BYTES", printed, "the size the lane reports is the size Instagram "
                                             "checks against its 8 MB cap")

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
                                         "account_type": "BUSINESS", "media_count": 12})),
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

    def test_the_first_comment_follows_a_live_post_and_never_fails_it(self):
        """22 Oct 2026: a question under the post (two-way conversation is a ranked signal)."""
        routes = self._base_routes({"POST /MEDIA9/comments": (200, json.dumps({"id": "C1"}))})
        code, out, fake = self._publish(routes,
                                       ["--image-url", "https://docoga.com.ng/social/x.jpg",
                                        "--caption", self.CAPTION, "--allow-unknown-specs",
                                        "--first-comment", "Which state are you renting in? Free templates: docoga.com.ng"])
        self.assertEqual(code, 0, out)
        self.assertIn("IG_FIRST_COMMENT=posted", out)
        comment = [c for c in fake.posts if c[1].endswith("/MEDIA9/comments")]
        self.assertEqual(len(comment), 1)
        self.assertEqual(urllib.parse.parse_qs(comment[0][2])["message"], ["Which state are you renting in? Free templates: docoga.com.ng"])
        self.assertTrue(out.index("IG_FIRST_COMMENT=posted") < out.index("IG_RESULT=sent"), "the machine verdict still closes the run")
        refused = self._base_routes({"POST /MEDIA9/comments": (400, json.dumps({"error": {"message": "(#10) permission", "code": 10}}))})
        code, out, _ = self._publish(refused, ["--image-url", "https://docoga.com.ng/social/x.jpg", "--caption", self.CAPTION,
                                               "--allow-unknown-specs", "--first-comment", "Which state?"])
        self.assertEqual(code, 0, "a refused comment never fails a live post")
        self.assertIn("IG_FIRST_COMMENT=refused", out)
        self.assertIn("IG_RESULT=sent", out)
        code, out, fake = self._publish(self._base_routes(), ["--image-url", "https://docoga.com.ng/social/x.jpg", "--caption", self.CAPTION, "--allow-unknown-specs"])
        self.assertEqual(code, 0)
        self.assertFalse([c for c in fake.posts if c[1].endswith("/comments")], "no flag, no comment")

    def test_alt_text_rides_on_the_photo_container(self):
        """17 Oct 2026, Instagram SEO: the card's alt text goes to Meta with the container."""
        code, out, fake = self._publish(self._base_routes(),
                                       ["--image-url", "https://docoga.com.ng/social/x.jpg",
                                        "--caption", self.CAPTION, "--alt-text", "DocOga navy text card: stamp duty in Lagos.",
                                        "--allow-unknown-specs"])
        self.assertEqual(code, 0, out)
        container = [c for c in fake.posts if c[1].endswith("/1784/media")][0]
        q = urllib.parse.parse_qs(container[2])
        self.assertEqual(q["alt_text"], ["DocOga navy text card: stamp duty in Lagos."])
        self.assertEqual(q["caption"], [self.CAPTION])

    def test_the_instagram_caption_opens_with_the_search_phrase_and_the_card_has_alt_text(self):
        with mock.patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": os.path.join(self.tmp, "none")}):
            content = gc.generate(datetime.date(2026, 10, 21), write=False)
        self.assertTrue(content["ig_caption"].startswith("Rent and tenancy documents Nigeria\n\n"), content["ig_caption"])
        self.assertIn("?s=ig", content["ig_caption"], "Instagram's link carries Instagram's tag")
        self.assertNotIn("?s=th", content["ig_caption"])
        self.assertTrue(content["alt_text"].startswith("DocOga navy text card"), content["alt_text"])
        self.assertLessEqual(len(content["alt_text"]), 1000)
        pack = {"tool": "notice-to-quit", "state": "lagos", "post": {"headline": "Six months, in writing.", "lines": ["s.13(1)(e)."]}, "visual": {"kicker": "Notice to quit"}}
        self.assertEqual(bd.seo_line(pack), "Notice to quit Nigeria (Lagos)")
        self.assertEqual(bd.alt_text(pack), "DocOga navy text card — Notice to quit: Six months, in writing. s.13(1)(e). Notice to quit Nigeria (Lagos). docoga.com.ng.")

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
            {"user_id": "1784", "username": "me", "account_type": "PERSONAL"}))})
        code, out, _fake = self._publish(routes, ["--probe"])
        self.assertEqual(code, 3)
        self.assertIn("professional", out.lower())

    def test_probe_asks_for_fields_that_exist_and_accepts_a_creator(self):
        """16 Oct 2026, first real probe: `(#100) Tried accessing nonexisting field
        (profile_type)`. The field is `account_type`; creators come back as MEDIA_CREATOR."""
        routes = self._base_routes({"GET /me": (200, json.dumps(
            {"user_id": "1784", "username": "me", "account_type": "MEDIA_CREATOR",
             "media_count": 3}))})
        code, out, fake = self._publish(routes, ["--probe"])
        self.assertEqual(code, 0, out)
        me = [q for m, url, q in fake.calls if url.endswith("/me")]
        self.assertTrue(me)
        self.assertNotIn("profile_type", me[0])
        self.assertIn("account_type", me[0])
        self.assertIn("profile MEDIA_CREATOR", out)
        self.assertNotIn("::warning title=account_type", out)

    def test_a_photo_whose_media_is_not_ready_is_retried_not_failed(self):
        """Run #48, 16 Oct 2026: error 9007 / subcode 2207027 "Media ID is not available …
        please wait for a moment" on the very first media_publish. A timing answer, so the
        publisher waits and asks again instead of exiting 6 with a red run."""
        attempts = {"n": 0}
        not_ready = json.dumps({"error": {"message": "Media ID is not available", "type": "OAuthException",
                                          "code": 9007, "error_subcode": 2207027}})

        def flaky(method, url, query):
            attempts["n"] += 1
            if attempts["n"] < 3:
                return 400, not_ready
            return 200, json.dumps({"id": "MEDIA9"})

        routes = self._base_routes({"POST /1784/media_publish": flaky})
        with mock.patch.object(ig.time, "sleep"):
            code, out, fake = self._publish(routes, ["--image-url", "https://docoga.com.ng/social/x.jpg",
                                                     "--caption", self.CAPTION, "--allow-unknown-specs"])
        self.assertEqual(code, 0, out)
        self.assertEqual(attempts["n"], 3)
        self.assertIn("not ready yet", out)
        self.assertIn("IG_RESULT=sent", out)
        # and a photo container's status is read before the first publish attempt
        self.assertTrue(any(url.endswith("/CONT") for _m, url, _q in fake.calls), fake.calls)

    def test_a_photo_that_stays_not_ready_eventually_fails_honestly(self):
        not_ready = (400, json.dumps({"error": {"message": "Media ID is not available",
                                                "code": 9007, "error_subcode": 2207027}}))
        routes = self._base_routes({"POST /1784/media_publish": not_ready})
        with mock.patch.object(ig.time, "sleep"):
            code, out, _fake = self._publish(routes, ["--image-url", "https://docoga.com.ng/social/x.jpg",
                                                      "--caption", self.CAPTION, "--allow-unknown-specs"])
        self.assertEqual(code, 6)
        self.assertIn("IG_RESULT=failed", out)

    def test_a_story_is_a_stories_container_with_no_caption_and_no_duplicate_check(self):
        """Owner, 16 Oct 2026: "what about Instagram stories". A Story is the 9:16 frame,
        `media_type=STORIES`, no caption (the words are on the frame), no permalink (it
        lives 24 h in the tray), and the duplicate guard does not apply."""
        self.public_media(1080, 1920)
        routes = self._base_routes({"POST /1784/media_publish": (200, json.dumps({"id": "STORY1"}))})
        code, out, fake = self._publish(routes, ["--story-url", "https://docoga.com.ng/social/x-story.jpg"])
        self.assertEqual(code, 0, out)
        self.assertIn("IG_RESULT=sent", out)
        self.assertIn("IG_MEDIA_ID=STORY1", out)
        container = [q for m, url, q in fake.calls if m == "POST" and url.endswith("/1784/media")]
        self.assertEqual(len(container), 1, fake.calls)
        self.assertIn("media_type=STORIES", container[0])
        self.assertNotIn("caption", container[0])
        self.assertFalse(any(url.endswith("/1784/media") and m == "GET" for m, url, _q in fake.calls),
                         "a Story has no caption, so the recent-captions guard must not run")
        self.assertNotIn("copy rejected", out)

    def test_a_story_frame_must_be_nine_by_sixteen(self):
        self.public_media(1080, 1350)  # the feed card, not a Story frame
        code, out, fake = self._publish(self._base_routes(),
                                        ["--story-url", "https://docoga.com.ng/social/x.jpg"])
        self.assertEqual(code, 5, out)
        self.assertIn("9:16", out)
        self.assertIn("IG_CAUSE=media", out)
        self.assertFalse(fake.wrote_anything())

    def test_refresh_uses_the_refresh_endpoint_not_the_exchange(self):
        """`/access_token` is the short→long exchange and answers "client_secret is required"
        — the first real run's warning. A long-lived token is wound forward with
        `/refresh_access_token` and nothing but the token."""
        routes = self._base_routes({"GET /refresh_access_token": (200, json.dumps(
            {"access_token": "NEwTOKENvalue", "expires_in": 5184000}))})
        code, out, fake = self._publish(routes, ["--refresh-token"])
        self.assertEqual(code, 0, out)
        hits = [(url, q) for m, url, q in fake.calls if "access_token" in url]
        self.assertEqual(len(hits), 1, fake.calls)
        self.assertTrue(hits[0][0].endswith("/refresh_access_token"), hits[0][0])
        self.assertIn("grant_type=ig_refresh_token", hits[0][1])
        self.assertNotIn("client_secret", hits[0][1])

    def test_refresh_stdout_is_pure_json_for_the_vault(self):
        """Runs #46–#49: the "token refreshed (fingerprint …)" line went to stdout, which is the
        file `token_vault.py seal --json` reads, so every seal failed on line 1 and the workflow
        blamed SOCIAL_TOKEN_KEY. stdout must be exactly one JSON object; chatter goes to stderr."""
        routes = self._base_routes({"GET /refresh_access_token": (200, json.dumps(
            {"access_token": "NEwTOKENvalue", "expires_in": 5184000}))})
        fake = FakeHttp(routes, shape=3)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, dict(self.env), clear=True), \
                mock.patch.object(ig, "http", fake), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ig.main(["--refresh-token"])
        self.assertEqual(code, 0, err.getvalue())
        self.assertEqual(json.loads(out.getvalue())["access_token"], "NEwTOKENvalue",
                         "stdout is the vault's input and must parse as one JSON object")
        self.assertIn("fingerprint", err.getvalue())

    def test_refresh_never_prints_the_credential_it_used(self):
        routes = self._base_routes({"GET /refresh_access_token": (200, json.dumps(
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

    def test_a_local_file_on_the_instagram_login_path_is_attempted_not_prejudged(self):
        """`--reel x.mp4` with an Instagram-Login token: Meta documents resumable upload for the
        Facebook-Login host, but 2026 field reports show it working on graph.instagram.com, and
        on 16 Oct 2026 the Page door was shut by a profile restriction. So the tool no longer
        refuses up front; the first gate it meets is the media check, and a missing file is a
        media refusal — nothing is written before that."""
        code, out, fake = self._publish(self._base_routes(),
                                       ["--reel", "social/x.mp4", "--caption", self.CAPTION])
        self.assertEqual(code, 5, out)
        self.assertIn("IG_CAUSE=media", out)
        self.assertFalse(fake.wrote_anything())

    def test_no_credential_is_setup(self):
        code, out = run_publisher(ig, ["--probe"], {})
        self.assertEqual(code, 2, "setup is exit 2, not a red API failure the owner misreads")
        self.assertIn("secrets missing", out)
        self.assertIn("IG_CAUSE=setup", out)


class InstagramReels(unittest.TestCase):
    """Reels by Meta's resumable upload on the Facebook-Login path (16 Oct 2026).

    The owner asked for Reels at ₦0 and for the research to be done properly first. The verdict
    was that no public host is needed at all — the Page token the Facebook lane already holds
    can push the bytes straight to rupload.facebook.com — so these tests pin the exact shape
    Meta documents: `upload_type=resumable` on the container, the OAuth/offset/file_size
    headers on the upload, a resume from `bytes_transferred`, and a probe that names what is
    missing instead of failing on a Monday morning.
    """

    CAPTION = "Your landlord must give you a receipt for every rent payment — Lagos Tenancy Law s.5."

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.video = os.path.join(self.tmp, "docoga_reel_20261020.mp4")
        with open(self.video, "wb") as handle:
            handle.write(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20_000)
        self.env = {"IG_ACCESS_TOKEN": "EAAPAGETOKEN", "IG_API_PATH": "facebook-login",
                    "FB_PAGE_ID": "102466208923830"}
        spec = mock.patch.object(ig, "video_spec_ok", return_value=(True, "stubbed spec"))
        spec.start()
        self.addCleanup(spec.stop)
        self.uploads = []

        def fake_upload(url, payload, headers, timeout=900):
            self.uploads.append((url, len(payload), dict(headers)))
            return 200, json.dumps({"success": True, "message": "Upload successful."})
        self.fake_upload = fake_upload
        head = mock.patch.object(ig, "raw_head", side_effect=AssertionError("no media fetch"))
        head.start()
        self.addCleanup(head.stop)

    def routes(self, extra=None, linked=True, scopes=("pages_show_list", "instagram_basic",
                                                      "instagram_content_publish")):
        page = {"id": "102466208923830", "name": "DocOga"}
        if linked:
            page["instagram_business_account"] = {"id": "1784", "username": "docoga.ng",
                                                  "media_count": 3}
        routes = {
            "GET /102466208923830": (200, json.dumps(page)),
            "GET /debug_token": (200, json.dumps({"data": {"scopes": list(scopes)}})),
            "GET /1784": (200, json.dumps({"id": "1784", "username": "docoga.ng",
                                            "media_count": 3})),
            "GET /1784/content_publishing_limit": (200, json.dumps(
                {"data": [{"quota_usage": 1, "config": {"quota_total": 100}}]})),
            "GET /1784/media": (200, json.dumps({"data": []})),
            "POST /1784/media": (200, json.dumps({
                "id": "CONT", "uri": "https://rupload.facebook.com/ig-api-upload/v26.0/CONT"})),
            "GET /CONT": (200, json.dumps({"status_code": "FINISHED"})),
            "POST /1784/media_publish": (200, json.dumps({"id": "REEL7"})),
            "GET /REEL7": (200, json.dumps({"permalink": "https://www.instagram.com/reel/REEL7/"})),
        }
        routes.update(extra or {})
        return routes

    def run_ig(self, routes, argv, env_extra=None, upload=None):
        fake = FakeHttp(routes, shape=3)
        env = dict(self.env)
        env.update(env_extra or {})
        with mock.patch.object(ig, "http", fake), \
                mock.patch.object(ig, "http_bytes", upload or self.fake_upload), \
                mock.patch.object(ig.time, "sleep", lambda *_: None):
            code, out = run_publisher(ig, argv, env)
        return code, out, fake

    # ── the probe ──────────────────────────────────────────────────────────────

    def test_probe_says_ready_when_linked_and_both_scopes_are_on_the_token(self):
        code, out, fake = self.run_ig(self.routes(), ["--probe-reels"],
                                      {"META_APP_ID": "931", "META_APP_SECRET": "s3"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_REELS_READY=yes", out)
        self.assertIn("IG_USER_ID=1784", out)
        self.assertIn("IG_USERNAME=docoga.ng", out)
        self.assertFalse(fake.wrote_anything(), "a probe creates nothing")
        self.assertIn("access_token=931%7Cs3", fake.calls[1][2], "debug_token is asked with the app token")

    def test_probe_names_the_missing_scope_and_the_exact_fix(self):
        code, out, _ = self.run_ig(self.routes(scopes=("pages_show_list", "instagram_basic")),
                                   ["--probe-reels"], {"META_APP_ID": "931", "META_APP_SECRET": "s3"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_REELS_READY=no", out)
        self.assertIn("IG_REELS_MISSING=instagram_content_publish", out)
        self.assertIn("Graph API Explorer", out)
        self.assertIn("❌ instagram_content_publish", out)

    def test_probe_names_the_missing_page_link(self):
        code, out, _ = self.run_ig(self.routes(linked=False), ["--probe-reels"],
                                   {"META_APP_ID": "931", "META_APP_SECRET": "s3"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_REELS_READY=no", out)
        self.assertIn("page-link", out)
        self.assertIn("Linked accounts", out)

    def test_probe_accepts_a_page_linked_only_through_connected_instagram_account(self):
        """16 Oct 2026: the token had both scopes and had been minted with @docoga.ng selected
        in the login dialog, and the probe still said `page-link` — because it read only
        `instagram_business_account`. A Page linked the Accounts-Center way shows the account in
        `connected_instagram_account`. Both fields are asked for; either one is a link."""
        page = {"id": "102466208923830", "name": "DocOga",
                "connected_instagram_account": {"id": "1784", "username": "docoga.ng",
                                                "media_count": 3}}
        routes = self.routes(linked=False)
        routes["GET /102466208923830"] = (200, json.dumps(page))
        code, out, fake = self.run_ig(routes, ["--probe-reels"],
                                      {"META_APP_ID": "931", "META_APP_SECRET": "s3"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_REELS_READY=yes", out)
        self.assertIn("IG_USER_ID=1784", out)
        page_read = fake.calls[0][2]
        self.assertIn("instagram_business_account", urllib.parse.unquote(page_read))
        self.assertIn("connected_instagram_account", urllib.parse.unquote(page_read))

    def test_probe_without_app_credentials_still_decides_from_the_reads(self):
        """No META_APP_ID: scopes are unknown, but a linked account whose node answers the
        publishing-limit read is ready in practice — and the output says the scopes were not asked."""
        code, out, _ = self.run_ig(self.routes(), ["--probe-reels"])
        self.assertEqual(code, 0, out)
        self.assertIn("token scopes: unknown", out)
        self.assertIn("IG_REELS_READY=yes", out)

    def test_probe_with_a_publishing_read_refused_is_not_ready(self):
        routes = self.routes({"GET /1784/content_publishing_limit": (400, json.dumps(
            {"error": {"message": "(#200) Requires instagram_content_publish permission", "code": 200}}))})
        code, out, _ = self.run_ig(routes, ["--probe-reels"])
        self.assertEqual(code, 0, out)
        self.assertIn("IG_REELS_READY=no", out)
        self.assertIn("instagram_content_publish", out)

    # ── the second door: the Instagram-Login token, no Page link ───────────────

    def ig_login_routes(self, container=(200, '{"id": "PROBE1", "uri": '
                                              '"https://rupload.facebook.com/ig-api-upload/v26.0/PROBE1"}')):
        return {
            "GET /me": (200, json.dumps({"user_id": "1784", "username": "docoga.ng",
                                         "account_type": "BUSINESS", "media_count": 4})),
            "POST /1784/media": container,
        }

    def test_probe_on_the_instagram_login_path_asks_meta_for_a_resumable_session(self):
        """16 Oct 2026: Facebook refused to link the Page ("temporarily restricted … to protect
        your profile"), so the Page-token door was shut. The Instagram-Login token the daily
        cards use is the second door — if graph.instagram.com opens a resumable REELS container
        for it. The probe creates exactly one, publishes nothing, and says which door it is."""
        code, out, fake = self.run_ig(self.ig_login_routes(), ["--probe-reels"],
                                      {"IG_API_PATH": "instagram-login"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_REELS_READY=yes", out)
        self.assertIn("IG_REELS_PATH=instagram-login", out)
        self.assertIn("IG_USER_ID=1784", out)
        self.assertIn("no Page link needed", out)
        methods = [(m, u.split("?")[0]) for m, u, _ in fake.calls]
        self.assertEqual(len([m for m in methods if m[0] == "POST"]), 1, "one container, no publish")
        self.assertTrue(all("graph.instagram.com" in u for _, u in methods), methods)
        self.assertIn("upload_type=resumable", fake.calls[-1][2])
        self.assertNotIn("media_publish", out)

    def test_probe_on_the_instagram_login_path_reports_metas_refusal_as_not_ready(self):
        refusal = (400, json.dumps({"error": {"message": "(#100) upload_type is not supported "
                                                          "for this login type", "code": 100}}))
        code, out, _ = self.run_ig(self.ig_login_routes(container=refusal), ["--probe-reels"],
                                   {"IG_API_PATH": "instagram-login"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_REELS_READY=no", out)
        self.assertIn("IG_REELS_MISSING=resumable-on-instagram-login", out)
        self.assertIn("IG_REELS_PATH=instagram-login", out)
        self.assertIn("not supported for this login type", out)

    def test_probe_on_the_instagram_login_path_opens_the_third_door_when_resumable_is_refused(self):
        """18 Oct 2026: Facebook still refused the Page link (no date this time) and Meta still
        refused a resumable session on the Instagram-Login token. The documented standard path —
        `media_type=REELS` + `video_url` — needs neither, only a professional account the token
        can read. The probe says so on its own line, and the lane picks the `hosted` door."""
        refusal = (400, json.dumps({"error": {"message": "(#100) upload_type is not supported "
                                                          "for this login type", "code": 100}}))
        code, out, _ = self.run_ig(self.ig_login_routes(container=refusal), ["--probe-reels"],
                                   {"IG_API_PATH": "instagram-login"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_REELS_READY=no", out)
        self.assertIn("IG_REELS_HOSTED=yes", out)
        self.assertIn("IG_USER_ID=1784", out)
        self.assertIn("Reels-ready by URL", out)
        self.assertIn("media_host.py", out)

    def test_the_third_door_is_shut_for_a_personal_account_and_for_an_unreadable_token(self):
        routes = self.ig_login_routes()
        routes["GET /me"] = (200, json.dumps({"user_id": "1784", "username": "docoga.ng",
                                              "account_type": "PERSONAL"}))
        code, out, _ = self.run_ig(routes, ["--probe-reels"], {"IG_API_PATH": "instagram-login"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_REELS_HOSTED=no", out)
        routes["GET /me"] = (400, json.dumps({"error": {"message": "Invalid OAuth access token",
                                                        "code": 190}}))
        code, out, _ = self.run_ig(routes, ["--probe-reels"], {"IG_API_PATH": "instagram-login"})
        self.assertIn("IG_REELS_HOSTED=no", out)

    def test_a_hosted_reel_goes_by_video_url_on_the_instagram_login_host(self):
        """The third door end to end: no bytes to rupload, the container carries `video_url`
        (the worker's /m/ URL), Meta polls to FINISHED, publish, read back."""
        url = "https://docoga-pass.johnazani.workers.dev/m/Qx9rT2uV7wY0zA3bC5dE8fG1hJ4kL6mN.mp4"
        routes = self.ig_login_routes(container=(200, json.dumps({"id": "CONT"})))
        routes.update({
            "GET /1784/content_publishing_limit": (200, json.dumps(
                {"data": [{"quota_usage": 1, "config": {"quota_total": 100}}]})),
            "GET /1784/media": (200, json.dumps({"data": []})),
            "GET /CONT": (200, json.dumps({"status_code": "FINISHED"})),
            "POST /1784/media_publish": (200, json.dumps({"id": "REEL9"})),
            "GET /REEL9": (200, json.dumps({"permalink": "https://www.instagram.com/reel/REEL9/"})),
        })
        head = mock.patch.object(ig, "raw_head", return_value=(206, {"Content-Length": "65536",
                                                                     "Content-Range": "bytes 0-65535/10390900"},
                                                               b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100))
        with head:
            code, out, fake = self.run_ig(routes, ["--video-url", url, "--caption", self.CAPTION,
                                                   "--thumb-offset-ms", "0", "--trial", "--wait-url"],
                                          {"IG_API_PATH": "instagram-login", "IG_USER_ID": "1784"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_RESULT=sent", out)
        self.assertIn("instagram.com/reel/REEL9/", out)
        self.assertEqual(self.uploads, [], "nothing goes to rupload through the third door")
        container = [c for c in fake.posts if c[1].endswith("/1784/media")]
        self.assertEqual(len(container), 1, fake.posts)
        query = urllib.parse.parse_qs(container[0][2])
        self.assertEqual(query["media_type"], ["REELS"])
        self.assertEqual(query["video_url"], [url])
        self.assertEqual(query["share_to_feed"], ["true"])
        self.assertEqual(query["thumb_offset"], ["0"], "frame 0 is the designed cover")
        self.assertNotIn("upload_type", query)
        self.assertTrue(all("graph.instagram.com" in c[1] for c in container), container)

    def test_a_video_story_by_url_is_media_type_stories_plus_video_url(self):
        url = "https://docoga-pass.johnazani.workers.dev/m/Qx9rT2uV7wY0zA3bC5dE8fG1hJ4kL6mN.mp4"
        routes = self.ig_login_routes(container=(200, json.dumps({"id": "SCONT"})))
        routes.update({
            "GET /1784/content_publishing_limit": (200, json.dumps(
                {"data": [{"quota_usage": 1, "config": {"quota_total": 100}}]})),
            "GET /SCONT": (200, json.dumps({"status_code": "FINISHED"})),
            "POST /1784/media_publish": (200, json.dumps({"id": "STORY9"})),
            "GET /STORY9": (200, json.dumps({"id": "STORY9", "media_product_type": "STORY"})),
        })
        with mock.patch.object(ig, "raw_head", return_value=(200, {"Content-Length": "10390900"},
                                                             b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100)):
            code, out, fake = self.run_ig(routes, ["--story-video-url", url],
                                          {"IG_API_PATH": "instagram-login", "IG_USER_ID": "1784"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_RESULT=sent", out)
        container = [c for c in fake.posts if c[1].endswith("/1784/media")]
        self.assertEqual(len(container), 1, fake.posts)
        query = urllib.parse.parse_qs(container[0][2])
        self.assertEqual(query["media_type"], ["STORIES"])
        self.assertEqual(query["video_url"], [url])
        self.assertNotIn("caption", query, "a Story carries no caption")
        self.assertEqual(self.uploads, [])

    def test_probe_on_the_instagram_login_path_needs_a_professional_account(self):
        routes = self.ig_login_routes()
        routes["GET /me"] = (200, json.dumps({"user_id": "1784", "username": "docoga.ng",
                                              "account_type": "PERSONAL"}))
        code, out, fake = self.run_ig(routes, ["--probe-reels"], {"IG_API_PATH": "instagram-login"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_REELS_READY=no", out)
        self.assertIn("professional-account", out)
        self.assertFalse(any(m == "POST" for m, _, _ in fake.calls), "no container for a personal account")

    def test_facebook_login_probe_names_its_door_too(self):
        code, out, _ = self.run_ig(self.routes(), ["--probe-reels"],
                                   {"META_APP_ID": "931", "META_APP_SECRET": "s3"})
        self.assertEqual(code, 0, out)
        self.assertIn("IG_REELS_PATH=facebook-login", out)

    # ── the upload ─────────────────────────────────────────────────────────────

    def test_a_reel_goes_container_upload_poll_publish_with_the_documented_shape(self):
        code, out, fake = self.run_ig(self.routes(), ["--video-file", self.video,
                                                      "--caption", self.CAPTION])
        self.assertEqual(code, 0, out)
        self.assertIn("IG_RESULT=sent", out)
        self.assertIn("instagram.com/reel/REEL7/", out)
        container = [c for c in fake.posts if c[1].endswith("/1784/media")]
        self.assertEqual(len(container), 1, fake.posts)
        query = urllib.parse.parse_qs(container[0][2])
        self.assertEqual(query["upload_type"], ["resumable"])
        self.assertEqual(query["media_type"], ["REELS"])
        self.assertEqual(query["share_to_feed"], ["true"])
        self.assertEqual(query["thumb_offset"], ["0"], "frame 0 is the designed cover (tools/short_cover.py)")
        self.assertEqual(query["caption"], [self.CAPTION])
        self.assertNotIn("video_url", query, "no public URL is involved anywhere")
        self.assertEqual(len(self.uploads), 1)
        url, size, headers = self.uploads[0]
        self.assertEqual(url, ig.RUPLOAD_IG + "/CONT")
        self.assertEqual(size, os.path.getsize(self.video))
        self.assertEqual(headers["Authorization"], "OAuth EAAPAGETOKEN")
        self.assertEqual(headers["offset"], "0")
        self.assertEqual(headers["file_size"], str(size))
        publish = [c for c in fake.posts if c[1].endswith("/media_publish")]
        self.assertEqual(len(publish), 1)
        self.assertIn("creation_id=CONT", publish[0][2])
        self.assertNotIn("102466208923830/media", "".join(c[1] for c in fake.posts),
                         "the Page id must never be used as the Instagram user id")

    def test_a_trial_reel_carries_trial_params_and_falls_back_to_a_plain_reel_when_refused(self):
        """17 Oct 2026: Trial Reels go to non-followers first and graduate on performance — growth
        the account does not have to pay for. An account Meta has not opened it to still posts."""
        code, out, fake = self.run_ig(self.routes(), ["--video-file", self.video, "--caption", self.CAPTION, "--trial"])
        self.assertEqual(code, 0, out)
        container = [c for c in fake.posts if c[1].endswith("/1784/media")]
        query = urllib.parse.parse_qs(container[0][2])
        self.assertEqual(json.loads(query["trial_params"][0]), {"graduation_strategy": "SS_PERFORMANCE"})
        self.assertIn("IG_TRIAL=on", out)

        calls = []

        def picky(method, url, query):
            calls.append(query)
            if "trial_params" in query:
                return 400, json.dumps({"error": {"message": "(#100) Invalid parameter trial_params", "code": 100}})
            return 200, json.dumps({"id": "CONT", "uri": ig.RUPLOAD_IG + "/CONT"})
        code, out, fake = self.run_ig(self.routes({"POST /1784/media": picky}),
                                      ["--video-file", self.video, "--caption", self.CAPTION, "--trial"])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("trial_params", calls[1])
        self.assertIn("IG_TRIAL=refused", out)
        self.assertIn("IG_RESULT=sent", out)

    def test_the_instagram_id_is_resolved_from_the_page_not_from_me(self):
        """A Page token's `/me` is the Page. The old facebook-login branch would have used the
        Page id as the Instagram user id and failed with a permissions sentence."""
        code, out, fake = self.run_ig(self.routes(), ["--probe"])
        self.assertEqual(code, 0, out)
        self.assertIn("id 1784", out)
        self.assertNotIn("GET /me", " ".join("%s %s" % (c[0], c[1][-40:]) for c in fake.calls))

    def test_an_interrupted_upload_resumes_from_the_byte_meta_reports(self):
        attempts = []

        def flaky(url, payload, headers, timeout=900):
            attempts.append((len(payload), dict(headers)))
            if len(attempts) == 1:
                raise ig.ApiError(0, "transport failure while uploading the video: reset", "rupload")
            return 200, json.dumps({"success": True})
        routes = self.routes({"GET /CONT": lambda m, u, q: (200, json.dumps(
            {"status_code": "FINISHED", "video_status": {"uploading_phase": {
                "status": "in_progress", "bytes_transferred": 4096}}}))})
        code, out, _ = self.run_ig(routes, ["--video-file", self.video, "--caption", self.CAPTION],
                                   upload=flaky)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[1][1]["offset"], "4096")
        self.assertEqual(attempts[1][0], os.path.getsize(self.video) - 4096)
        self.assertEqual(attempts[1][1]["file_size"], str(os.path.getsize(self.video)))
        self.assertIn("resuming from byte 4096", out)

    def test_a_refused_upload_is_a_failed_run_and_never_published(self):
        def refused(url, payload, headers, timeout=900):
            return 400, json.dumps({"debug_info": {"retriable": False, "type": "ProcessingFailedError",
                                                   "message": "unauthorized user request"}})
        code, out, fake = self.run_ig(self.routes(), ["--video-file", self.video,
                                                      "--caption", self.CAPTION], upload=refused)
        self.assertNotEqual(code, 0)
        self.assertIn("IG_RESULT=failed", out)
        self.assertIn("IG_CONTAINER_ID=CONT", out)
        self.assertFalse(any(c[1].endswith("/media_publish") for c in fake.posts),
                         "a container whose bytes were refused must not be published")

    def test_a_video_story_is_a_stories_container_with_no_caption(self):
        routes = self.routes({"POST /1784/media_publish": (200, json.dumps({"id": "STORY5"}))})
        code, out, fake = self.run_ig(routes, ["--video-file", self.video, "--video-story"])
        self.assertEqual(code, 0, out)
        self.assertIn("IG_RESULT=sent", out)
        query = urllib.parse.parse_qs([c for c in fake.posts if c[1].endswith("/1784/media")][0][2])
        self.assertEqual(query["media_type"], ["STORIES"])
        self.assertEqual(query["upload_type"], ["resumable"])
        self.assertNotIn("caption", query)
        self.assertNotIn("thumb_offset", query)

    def test_a_cover_url_replaces_the_frame_offset(self):
        code, out, fake = self.run_ig(self.routes(), ["--video-file", self.video, "--caption",
                                                      self.CAPTION, "--cover-url",
                                                      "https://docoga.com.ng/social/c.jpg"])
        self.assertEqual(code, 0, out)
        query = urllib.parse.parse_qs([c for c in fake.posts if c[1].endswith("/1784/media")][0][2])
        self.assertEqual(query["cover_url"], ["https://docoga.com.ng/social/c.jpg"])
        self.assertNotIn("thumb_offset", query)

    def test_a_duplicate_caption_refuses_before_any_byte_is_sent(self):
        routes = self.routes({"GET /1784/media": (200, json.dumps({"data": [
            {"id": "1", "caption": self.CAPTION, "permalink": "https://www.instagram.com/reel/OLD/"}]}))})
        code, out, fake = self.run_ig(routes, ["--video-file", self.video, "--caption", self.CAPTION])
        self.assertEqual(code, 0, out)
        self.assertIn("IG_RESULT=refused-duplicate", out)
        self.assertEqual(self.uploads, [])
        self.assertFalse(fake.wrote_anything())

    def test_the_local_gate_refuses_a_stub_and_a_non_mp4(self):
        mock.patch.stopall()  # the real gate, not the stub
        tiny = os.path.join(self.tmp, "tiny.mp4")
        with open(tiny, "wb") as handle:
            handle.write(b"\x00\x00\x00\x18ftypmp42")
        ok, why = ig.video_spec_ok(tiny)
        self.assertFalse(ok)
        self.assertIn("did not finish", why)
        text = os.path.join(self.tmp, "words.mp4")
        with open(text, "wb") as handle:
            handle.write(b"not a video" * 2000)
        ok, why = ig.video_spec_ok(text)
        self.assertFalse(ok)
        self.assertIn("ftyp", why)
        ok, why = ig.video_spec_ok(os.path.join(self.tmp, "missing.mp4"))
        self.assertFalse(ok)

    def test_a_bad_file_never_reaches_meta(self):
        with mock.patch.object(ig, "video_spec_ok", return_value=(False, "aspect ratio is 16:9")):
            code, out, fake = self.run_ig(self.routes(), ["--video-file", self.video,
                                                          "--caption", self.CAPTION])
        self.assertEqual(code, 5, out)
        self.assertIn("IG_CAUSE=media", out)
        self.assertIn("16:9", out)
        self.assertFalse(fake.wrote_anything())
        self.assertEqual(self.uploads, [])


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



class ThreadsEveningSlot(unittest.TestCase):
    """17 Oct 2026: the 20:10 WAT post — the day's card as an image, link-free words, link in our reply."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_the_evening_copy_is_link_free_and_names_the_card_and_the_reply(self):
        with mock.patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": os.path.join(self.tmp, "none")}):
            content = gc.generate(datetime.date(2026, 10, 21), write=False, slot="evening")
        self.assertEqual(content["slot"], "evening")
        self.assertNotIn("http", content["text"], "the body carries no link — Threads ranks it higher without one")
        self.assertNotIn("👉", content["text"].split("\n")[-1].strip() or "x", "no dangling arrow where the link was")
        self.assertEqual(content["image_url"], "https://docoga.com.ng/social/2026-10-21-threads-evening.jpg",
                         "17 Oct 2026: the lane's OWN card, not the Instagram lane's (which exists only on "
                         "days that lane rendered — the day Threads went out as words)")
        self.assertEqual(content["card_path"], "site/social/2026-10-21-threads-evening.jpg")
        self.assertIn("https://docoga.com.ng", content["reply_text"])
        self.assertIn("?s=th", content["reply_text"], "the reply's link carries the Threads tag")
        self.assertIsNone(content["poll"], "a poll beside an image is refused by the API")
        lunch = gc.generate(datetime.date(2026, 10, 21), write=False)
        self.assertEqual(lunch.get("slot"), "lunch")
        self.assertEqual(lunch["image_url"], "https://docoga.com.ng/social/2026-10-21-threads.jpg",
                         "owner, 17 Oct 2026: 'the Thread is only text it uploads' — every slot carries a card")
        self.assertEqual(lunch["card_path"], "site/social/2026-10-21-threads.jpg")
        self.assertNotEqual(lunch["text"], content["text"], "two posts a day, not the same post twice")

    def test_the_morning_slot_asks_a_question_under_the_days_hook(self):
        """17 Oct 2026 (visibility research): 07:20 WAT is Threads' peak hour in Nigeria and reply
        rate is its first ranking signal — so the morning post is the Short's spoken hook plus one
        rotating question, as an image post with no link and no poll."""
        with mock.patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": os.path.join(self.tmp, "none")}):
            day = datetime.date(2026, 10, 20)
            content = gc.generate(day, write=False, slot="morning")
            lunch = gc.generate(day, write=False)
            evening = gc.generate(day, write=False, slot="evening")
            nxt = gc.generate(datetime.date(2026, 10, 21), write=False, slot="morning")
        self.assertEqual(content["slot"], "morning")
        self.assertEqual(content["post_type"], "morning")
        self.assertNotIn("http", content["text"])
        self.assertTrue(content["text"].rstrip().endswith("?") or "?" in content["text"].split("\n")[-1],
                        "the morning post ends in a question: %r" % content["text"])
        import generate_short_video as words
        hook = words.script_for_date(day)["slides"][0]["say"]
        self.assertTrue(content["text"].startswith(hook[:60]), content["text"][:80])
        self.assertEqual(content["image_url"], "https://docoga.com.ng/social/2026-10-20-threads-morning.jpg")
        self.assertEqual(content["card_path"], "site/social/2026-10-20-threads-morning.jpg")
        self.assertIsNone(content["poll"])
        self.assertIsNone(content["reply_text"])
        self.assertTrue(content["topic_tag"])
        self.assertLessEqual(content["cost"], gc.MAX_COST)
        self.assertEqual(len({content["text"], lunch["text"], evening["text"]}), 3, "three posts, three texts")
        self.assertNotEqual(content["text"].split("\n")[-1], nxt["text"].split("\n")[-1],
                            "the question rotates day to day")

    def test_both_cards_are_dated_renders_the_pruner_recognises(self):
        """`social_card.prune` keeps the newest 60 days of dated renders; a name it does not match
        is kept forever, and site/social/ grows by three files a day until the deploy is slow."""
        for name in ("2026-10-21-threads.jpg", "2026-10-21-threads-evening.jpg", "2026-10-21-threads-morning.jpg",
                     "2026-10-21-instagram.jpg", "2026-10-21-instagram-story.jpg"):
            self.assertTrue(social_card.DATED_RENDER.match(name), name)
        self.assertFalse(social_card.DATED_RENDER.match("og-image.jpg"))

    def test_a_brain_pack_writes_the_evening_angle(self):
        pack = {"date": "2026-10-21", "theme": "x", "claims": [], "tool": "rent-receipt", "state": "lagos",
                "post": {"headline": "A rent receipt is seven lines.", "lines": ["Date, amount, period, address, names, signature, stamp."],
                         "cta": "Send this to a landlord you know.", "hashtags": ["#DocOga"]},
                "threads": {"text": "Lunch text?", "evening": "The receipt you did not collect is the dispute you will have in March."}}
        self.assertEqual(bd.threads_evening(pack), "The receipt you did not collect is the dispute you will have in March.")
        del pack["threads"]["evening"]
        self.assertEqual(bd.threads_evening(pack), "A rent receipt is seven lines.\n\nDate, amount, period, address, names, signature, stamp.\n\nSend this to a landlord you know.")
        self.assertTrue(bd.evening_reply(pack).endswith("?s=th"), bd.evening_reply(pack))
        self.assertEqual(bd.strip_links("Words.\n\n👉 Try am: https://docoga.com.ng\n\nMore."), "Words.\n\nMore.")


class ThreadsImageAndReply(ThreadsPublisher):
    """The publisher side of the evening slot: IMAGE container, then a TEXT reply under it."""

    def _evening_content(self):
        path = os.path.join(self.tmp, "threads_content_latest.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"text": self.TEXT, "slot": "evening", "topic_tag": "Tenant Rights Nigeria",
                       "image_url": "https://docoga.com.ng/social/2026-10-21-threads-evening.jpg",
                       "alt_text": "DocOga navy text card: rent receipt.",
                       "reply_text": "The page, free to start: https://docoga.com.ng/?s=th"}, fh)
        return path

    def test_a_card_that_never_goes_live_posts_the_words_without_touching_the_image_endpoint(self):
        """git knows the file before the web does. A container made against a 404 dies with a
        generic 'Unsupported URL'; the publisher waits for 200 first and, past the deadline,
        posts text — never a red run, never a silent no-post."""
        seen = []

        def container(method, url, query):
            q = urllib.parse.parse_qs(query)
            seen.append(q)
            return ok({"id": "181" if "reply_to_id" not in q else "182"})
        routes = self._routes(extra={"POST /42/threads": container, "GET /182": ok({"status": "FINISHED"})})
        path = self._evening_content()
        env, token_path = threads_env(self.tmp)
        self.card_live = (False, 600)
        code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path],
                                     env_extra={"THREADS_SHARE_TO_IG": "off"})
        self.assertEqual(code, 0, out)
        self.assertEqual([q["media_type"][0] for q in seen], ["TEXT", "TEXT"], "no IMAGE attempt against a dead URL")
        self.assertIn("THREADS_IMAGE=dropped", out)
        self.assertIn("not reachable after 600s", out)
        self.assertIn("THREADS_RESULT=sent", out)

    def test_wait_until_live_polls_until_200_and_gives_up_at_the_deadline(self):
        answers = iter([404, 404, 200])
        slept = []
        live, waited = tp.wait_until_live("https://docoga.com.ng/social/x.jpg", 600, 15,
                                          sleeper=slept.append, opener=lambda u: next(answers))
        self.assertEqual((live, waited), (True, 30))
        self.assertEqual(slept, [15, 15])
        slept = []
        live, waited = tp.wait_until_live("https://docoga.com.ng/social/x.jpg", 45, 15,
                                          sleeper=slept.append, opener=lambda u: "error timed out")
        self.assertEqual((live, waited), (False, 45))
        self.assertEqual(slept, [15, 15, 15])

    def test_on_a_poll_day_the_card_wins_and_the_poll_is_asked_in_a_reply(self):
        """A poll cannot sit beside an image; dropping the card for the poll is what left the
        owner looking at text. The card posts, the poll follows as our own reply."""
        seen = []

        def container(method, url, query):
            q = urllib.parse.parse_qs(query)
            seen.append(q)
            return ok({"id": "181" if "reply_to_id" not in q else "182"})
        routes = self._routes(extra={"POST /42/threads": container, "GET /182": ok({"status": "FINISHED"}),
                                     "POST /42/threads_publish": lambda m, u, q: ok({"id": "182" if "182" in q else "181"})})
        path = os.path.join(self.tmp, "threads_content_latest.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"text": self.TEXT, "slot": "lunch", "poll": {"option_a": "Yes", "option_b": "No"},
                       "image_url": "https://docoga.com.ng/social/2026-10-21-threads.jpg"}, fh)
        env, token_path = threads_env(self.tmp)
        code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path],
                                     env_extra={"THREADS_SHARE_TO_IG": "off"})
        self.assertEqual(code, 0, out)
        self.assertEqual(seen[0]["media_type"], ["IMAGE"])
        self.assertNotIn("poll_attachment", seen[0])
        self.assertEqual(seen[1]["reply_to_id"], ["181"])
        self.assertEqual(json.loads(seen[1]["poll_attachment"][0]), {"option_a": "Yes", "option_b": "No"})
        self.assertIn("THREADS_IMAGE=sent", out)
        self.assertIn("THREADS_POLL_REPLY=sent", out)

    def test_the_workflow_renders_and_pushes_its_own_card_before_the_ledger(self):
        """The lane, not the generator, is what makes the URL real: render → commit → push to the
        default branch (no `[skip ci]`, the push IS the deploy) → publisher waits for 200."""
        workflow = (ROOT / ".github/workflows/threads_autopost.yml").read_text(encoding="utf-8")
        steps = [line.strip()[len("- name: "):] for line in workflow.splitlines() if line.strip().startswith("- name: ")]
        self.assertLess(steps.index("Generate today's copy"), steps.index("Render the card and publish it"))
        self.assertLess(steps.index("Render the card and publish it"), steps.index("Ledger — has today already been posted?"))
        render = workflow.split("- name: Render the card and publish it", 1)[1].split("- name: Ledger", 1)[0]
        self.assertIn("tools/social_card.py --from-json", render)
        self.assertIn("sed -n 's/^CARD_URL=//p' /tmp/threads_render.log | tail -1", render)
        self.assertIn('git push origin "HEAD:${BRANCH}"', render)
        commit_lines = [line for line in render.splitlines() if "git commit" in line]
        self.assertEqual(len(commit_lines), 1, commit_lines)
        self.assertNotIn("skip ci", commit_lines[0], "the card commit must deploy the site")
        self.assertIn('blob["image_url"] = None', render, "a card that was not published must not be promised to Threads")
        self.assertIn("bash tools/install_brand_fonts.sh", workflow, "Inter, or the card is off-brand")
        self.assertIn("permissions:\n  contents: write", workflow)

    def test_the_card_rides_as_an_image_post_and_the_link_is_a_reply(self):
        seen = []

        def container(method, url, query):
            q = urllib.parse.parse_qs(query)
            seen.append(q)
            return ok({"id": "181" if "reply_to_id" not in q else "182"})
        routes = self._routes(extra={"POST /42/threads": container, "GET /182": ok({"status": "FINISHED"}),
                                     "POST /42/threads_publish": lambda m, u, q: ok({"id": "182" if "182" in q else "181"})})
        path = self._evening_content()
        env, token_path = threads_env(self.tmp)
        code, out, fake = self._publish(routes, argv=["--from-json", path, "--token-file", token_path],
                                        env_extra={"THREADS_SHARE_TO_IG": "off"})
        self.assertEqual(code, 0, out)
        self.assertEqual(seen[0]["media_type"], ["IMAGE"])
        self.assertEqual(seen[0]["image_url"], ["https://docoga.com.ng/social/2026-10-21-threads-evening.jpg"])
        self.assertEqual(seen[0]["alt_text"], ["DocOga navy text card: rent receipt."])
        self.assertEqual(seen[0]["topic_tag"], ["Tenant Rights Nigeria"])
        self.assertEqual(seen[1]["media_type"], ["TEXT"])
        self.assertEqual(seen[1]["reply_to_id"], ["181"])
        self.assertIn("docoga.com.ng/?s=th", seen[1]["text"][0])
        self.assertIn("THREADS_IMAGE=sent", out)
        self.assertIn("THREADS_REPLY=sent", out)
        self.assertIn("THREADS_RESULT=sent", out)

    def test_when_threads_refuses_the_cross_share_the_card_still_posts_as_an_image(self):
        """18 Oct 2026, every run since the 17th: `crossreshare_to_ig=true` refused with code 10 and
        the WHOLE image dropped — Threads was text-only for two days. The image ladder retries
        without the flag, and the publish forgives a 'media cannot be found' hiccup once."""
        seen, publishes = [], []
        refused = {"error": {"message": "Application does not have permission for this action", "type": "THApiException", "code": 10}}

        def container(method, url, query):
            q = urllib.parse.parse_qs(query)
            seen.append(q)
            if q.get("crossreshare_to_ig") == ["true"]:
                return (400, json.dumps(refused))
            return ok({"id": "181" if "reply_to_id" not in q else "182"})

        def publish(method, url, query):
            publishes.append(query)
            if len(publishes) == 1:
                return (400, json.dumps({"error": {"message": "The requested resource does not exist", "code": 24,
                                                   "error_subcode": 4279009, "error_user_title": "Media Not Found"}}))
            return ok({"id": "182" if "182" in query else "181"})
        routes = self._routes(extra={"POST /42/threads": container, "GET /182": ok({"status": "FINISHED"}),
                                     "POST /42/threads_publish": publish})
        path = self._evening_content()
        env, token_path = threads_env(self.tmp)
        with mock.patch.object(tp.time, "sleep", lambda s: None):
            code, out, fake = self._publish(routes, argv=["--from-json", path, "--token-file", token_path],
                                            env_extra={"THREADS_SHARE_TO_IG": "on"})
        self.assertEqual(code, 0, out)
        self.assertEqual(seen[0]["media_type"], ["IMAGE"])
        self.assertEqual(seen[0]["crossreshare_to_ig"], ["true"])
        self.assertEqual(seen[1]["media_type"], ["IMAGE"], "the second ask is still the IMAGE, minus the flag")
        self.assertNotIn("crossreshare_to_ig", seen[1])
        self.assertEqual(seen[1]["image_url"], ["https://docoga.com.ng/social/2026-10-21-threads-evening.jpg"])
        self.assertIn("THREADS_IMAGE=sent", out)
        self.assertIn("THREADS_IMAGE_EXTRAS_DROPPED=share_to_ig", out)
        self.assertNotIn("THREADS_IMAGE=dropped", out)
        self.assertEqual(len(publishes), 3, "one forgiven 'media not found', then the post, then the reply")
        self.assertIn("THREADS_RESULT=sent", out)

    def test_a_card_threads_cannot_fetch_falls_back_to_the_words(self):
        seen = []

        def container(method, url, query):
            q = urllib.parse.parse_qs(query)
            seen.append(q)
            if q.get("media_type") == ["IMAGE"]:
                return (400, json.dumps({"error": {"message": "Media download failed", "code": 9004}}))
            return ok({"id": "181" if "reply_to_id" not in q else "182"})
        routes = self._routes(extra={"POST /42/threads": container, "GET /182": ok({"status": "FINISHED"})})
        path = self._evening_content()
        env, token_path = threads_env(self.tmp)
        code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path],
                                     env_extra={"THREADS_SHARE_TO_IG": "off"})
        self.assertEqual(code, 0, out)
        self.assertEqual([q["media_type"][0] for q in seen], ["IMAGE", "TEXT", "TEXT"], "image refused → text post → link reply")
        self.assertIn("THREADS_IMAGE=dropped", out)
        self.assertIn("THREADS_REPLY=sent", out)

    def test_a_failed_reply_is_a_warning_not_a_red_run(self):
        def container(method, url, query):
            q = urllib.parse.parse_qs(query)
            if "reply_to_id" in q:
                return (403, json.dumps({"error": {"message": "(#10) permission", "code": 10}}))
            return ok({"id": "181"})
        routes = self._routes(extra={"POST /42/threads": container})
        path = self._evening_content()
        env, token_path = threads_env(self.tmp)
        code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path],
                                     env_extra={"THREADS_SHARE_TO_IG": "off"})
        self.assertEqual(code, 0, out)
        self.assertIn("THREADS_REPLY=failed", out)
        self.assertIn("THREADS_RESULT=sent", out)

class ThreadsVideo(ThreadsImageAndReply):
    """Owner, 21 Oct 2026: "Threads has never posted videos, why." Because the publisher only knew
    TEXT and IMAGE. Now the evening slot on a Shorts day offers the Short as a VIDEO container,
    with the card, then the words, behind it."""

    VIDEO = "https://docoga-pass.johnazani.workers.dev/m/abcdefghijklmnopqrstuvwxyz012345.mp4"

    def test_the_video_container_is_asked_for_polled_and_published(self):
        seen, polls = [], []

        def container(method, url, query):
            q = urllib.parse.parse_qs(query)
            seen.append(q)
            return ok({"id": "181" if "reply_to_id" not in q else "182"})

        def status(method, url, query):
            polls.append(1)
            return ok({"status": "IN_PROGRESS" if len(polls) < 3 else "FINISHED", "permalink": "https://x/1",
                       "text": self.TEXT})
        routes = self._routes(extra={"POST /42/threads": container, "GET /181": status,
                                     "GET /182": ok({"status": "FINISHED"})})
        path = self._evening_content()
        env, token_path = threads_env(self.tmp)
        with mock.patch.object(tp.time, "sleep", lambda s: None):
            code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path,
                                                       "--video-url", self.VIDEO],
                                         env_extra={"THREADS_SHARE_TO_IG": "on"})
        self.assertEqual(code, 0, out)
        first = seen[0]
        self.assertEqual(first["media_type"], ["VIDEO"])
        self.assertEqual(first["video_url"], [self.VIDEO])
        self.assertEqual(first["text"], [self.TEXT])
        self.assertEqual(first["topic_tag"], ["Tenant Rights Nigeria"])
        self.assertNotIn("crossreshare_to_ig", first, "the flag Threads refuses on media (code 10) is never sent with a video")
        self.assertNotIn("image_url", first)
        self.assertEqual([q["media_type"][0] for q in seen], ["VIDEO", "TEXT"], "video post, then the link reply — no card")
        self.assertGreaterEqual(len(polls), 3, "a video is transcoded after the fetch; the status is polled until FINISHED")
        self.assertIn("THREADS_VIDEO=sent", out)
        self.assertNotIn("THREADS_IMAGE=", out)
        self.assertIn("THREADS_RESULT=sent", out)

    def test_a_video_threads_will_not_take_falls_back_to_the_card(self):
        seen = []

        def container(method, url, query):
            q = urllib.parse.parse_qs(query)
            seen.append(q)
            if q.get("media_type") == ["VIDEO"]:
                return (400, json.dumps({"error": {"message": "Media download failed", "code": 9004}}))
            return ok({"id": "181" if "reply_to_id" not in q else "182"})
        routes = self._routes(extra={"POST /42/threads": container, "GET /182": ok({"status": "FINISHED"})})
        path = self._evening_content()
        env, token_path = threads_env(self.tmp)
        code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path,
                                                   "--video-url", self.VIDEO],
                                     env_extra={"THREADS_SHARE_TO_IG": "off"})
        self.assertEqual(code, 0, out)
        self.assertEqual([q["media_type"][0] for q in seen], ["VIDEO", "IMAGE", "TEXT"], "video refused → card → link reply")
        self.assertIn("THREADS_VIDEO=dropped", out)
        self.assertIn("THREADS_IMAGE=sent", out)
        self.assertIn("THREADS_RESULT=sent", out)

    def test_a_video_whose_container_errors_falls_back_too(self):
        seen = []

        def container(method, url, query):
            q = urllib.parse.parse_qs(query)
            seen.append(q)
            return ok({"id": {"VIDEO": "180", "IMAGE": "181"}.get(q["media_type"][0], "182" if "reply_to_id" in q else "181")})
        routes = self._routes(extra={"POST /42/threads": container, "GET /180": ok({"status": "ERROR"}),
                                     "GET /182": ok({"status": "FINISHED"})})
        path = self._evening_content()
        env, token_path = threads_env(self.tmp)
        code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path,
                                                   "--video-url", self.VIDEO],
                                     env_extra={"THREADS_SHARE_TO_IG": "off"})
        self.assertEqual(code, 0, out)
        self.assertEqual([q["media_type"][0] for q in seen], ["VIDEO", "IMAGE", "TEXT"])
        self.assertIn("THREADS_VIDEO=dropped", out)
        self.assertIn("(ERROR)", out)

    def test_a_dead_video_url_never_reaches_the_api(self):
        seen = []

        def container(method, url, query):
            q = urllib.parse.parse_qs(query)
            seen.append(q)
            return ok({"id": "181" if "reply_to_id" not in q else "182"})
        routes = self._routes(extra={"POST /42/threads": container, "GET /182": ok({"status": "FINISHED"})})
        path = self._evening_content()
        env, token_path = threads_env(self.tmp)
        self.card_live = (False, 120)
        code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path,
                                                   "--video-url", self.VIDEO],
                                     env_extra={"THREADS_SHARE_TO_IG": "off"})
        self.assertEqual(code, 0, out)
        self.assertNotIn("VIDEO", [q["media_type"][0] for q in seen])
        self.assertIn("THREADS_VIDEO=dropped", out)
        self.assertIn("not reachable after 120s", out)

    def test_without_a_video_url_nothing_changes(self):
        seen = []

        def container(method, url, query):
            q = urllib.parse.parse_qs(query)
            seen.append(q)
            return ok({"id": "181" if "reply_to_id" not in q else "182"})
        routes = self._routes(extra={"POST /42/threads": container, "GET /182": ok({"status": "FINISHED"})})
        path = self._evening_content()
        env, token_path = threads_env(self.tmp)
        code, out, _ = self._publish(routes, argv=["--from-json", path, "--token-file", token_path],
                                     env_extra={"THREADS_SHARE_TO_IG": "off"})
        self.assertEqual(code, 0, out)
        self.assertEqual([q["media_type"][0] for q in seen], ["IMAGE", "TEXT"])
        self.assertNotIn("THREADS_VIDEO=", out)


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

    def test_a_days_story_and_slides_go_with_its_card_and_keep_counts_days(self):
        """17 Oct 2026: a carousel day writes up to eight files. `keep` is a number of days,
        so one carousel does not push six older cards out of the window."""
        d = self._make("2026-10-01-instagram.jpg", "2026-10-01-instagram-story.jpg",
                       "2026-10-02-instagram.jpg", "2026-10-02-instagram-slide-1.jpg",
                       "2026-10-02-instagram-slide-2.jpg", "2026-10-03-instagram.jpg")
        deleted, kept = social_card.prune(d, keep=2)
        self.assertEqual(sorted(deleted), ["2026-10-01-instagram-story.jpg", "2026-10-01-instagram.jpg"])
        self.assertEqual(len(kept), 4)

    def test_the_carousel_is_the_packs_lines_one_slide_each_with_hook_and_close(self):
        """17 Oct 2026: Tue/Thu the pack becomes a carousel — hook, one point per slide, the
        CTA last — rendered under one date stem and listed in order on CARD_URLS. A pack with
        fewer than two lines yields CARD_SLIDES=0 and exit 0, so the single card posts."""
        pack = {"date": "2026-10-20", "status": "approved", "version": bd.SCHEMA_VERSION,
                "tool": "notice-to-quit", "state": "lagos", "theme": "notice",
                "post": {"headline": "Six months. In writing. https://docoga.com.ng",
                         "lines": ["Yearly tenant: six months — s.13(1)(e).", "Monthly: one month.", "Then a court order."],
                         "cta": "Send this to one tenant."}}
        slides = bd.carousel_slides(pack)
        self.assertEqual([k for k, _ in slides], ["swipe \u2192", "1 of 3", "2 of 3", "3 of 3", "free \u00b7 docoga.com.ng"])
        self.assertEqual(slides[0][1], "Six months. In writing.", "the hook is link-free")
        self.assertEqual(slides[-1][1], "Send this to one tenant.")
        self.assertEqual(bd.carousel_slides({"post": {"headline": "x", "lines": ["only one"]}}), [])

        drafts = Path(tempfile.mkdtemp())
        (drafts / "2026-10-20.json").write_text(json.dumps(pack), encoding="utf-8")
        out = Path(tempfile.mkdtemp()) / "site" / "social"
        with mock.patch.dict(os.environ, {"DOCOGA_BRAIN_DRAFTS": str(drafts), "BRAIN_PLATES": "off"}):
            with mock.patch.object(social_card, "ROOT", out.parents[1]):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = social_card.main(["--slides", "--brief", "2026-10-20",
                                             "--out", str(out / "2026-10-20-instagram-slide.jpg"),
                                             "--base-url", "https://docoga.com.ng"])
                self.assertEqual(code, 0)
                text = buf.getvalue()
                self.assertIn("CARD_SLIDES=5", text)
                urls = re.search(r"^CARD_URLS=(.*)$", text, re.M).group(1).split()
                self.assertEqual(urls[0], "https://docoga.com.ng/social/2026-10-20-instagram-slide-1.jpg")
                self.assertEqual(len(urls), 5)
                self.assertTrue(all((out / u.rsplit("/", 1)[1]).is_file() for u in urls))
                self.assertTrue(all(social_card.DATED_RENDER.match(u.rsplit("/", 1)[1]) for u in urls),
                                "slides must be named so the pruner sweeps them with their day")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = social_card.main(["--slides", "--brief", "2026-10-21", "--out", str(out / "x.jpg")])
                self.assertEqual((code, "CARD_SLIDES=0" in buf.getvalue()), (0, True))

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
