"""The status reader, tested against scripted GitHub answers.

`tools/lane_status.py` exists because a run's *log bytes* are unreachable from a sandbox
(`results-receiver.actions.githubusercontent.com` is not on the allowlist) while its job
conclusions, step conclusions and check-run annotations are ordinary REST. That asymmetry is the
whole design: read what is answerable, and say "could not read" rather than guessing about the
rest — which is how `chat not found` was found on 13 Oct 2026, four days into an outage nobody had
been told about.

Every test here injects a fake `run`, so no test needs a token, a network, or a green CI job to
know what the real endpoints look like.
"""

import json
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import lane_status  # noqa: E402


class Result:
    def __init__(self, payload, returncode=0, stderr=""):
        self.stdout = payload if isinstance(payload, str) else json.dumps(payload)
        self.returncode = returncode
        self.stderr = stderr


class FakeGh:
    """Answers `gh api <endpoint>` from a dict, and records what was asked."""

    def __init__(self, answers, error_on=None):
        self.answers = answers
        self.calls = []
        self.error_on = error_on or {}

    @staticmethod
    def _matches(needle, endpoint):
        """A trailing `$` means "the endpoint ends here".

        Needed because `…/actions/workflows/100/runs?per_page=1` contains *every* prefix of the
        workflow-list endpoint, so plain substring keys answer a run query with the workflow list —
        which then reports "this lane has never run". Anchoring the ambiguous key is honest; a
        cleverer matcher would be a trap for whoever edits this next.
        """
        if needle.endswith("$"):
            return endpoint.endswith(needle[:-1])
        return needle in endpoint

    def __call__(self, argv, capture_output=None, text=None, timeout=None):
        assert argv[:2] == ["gh", "api"], argv
        endpoint = argv[2]
        self.calls.append(endpoint)
        for needle, message in self.error_on.items():
            if self._matches(needle, endpoint):
                return Result("", returncode=1, stderr=message)
        for needle in sorted(self.answers, key=len, reverse=True):
            if self._matches(needle, endpoint):
                return Result(self.answers[needle])
        return Result("", returncode=1, stderr="no answer scripted for " + endpoint)


def workflows_payload(*paths):
    return {"workflows": [{"id": 100 + index, "name": Path(p).stem, "path": p, "state": "active"}
                          for index, p in enumerate(paths)]}


def runs_payload(*conclusions, **extra):
    runs = [{"id": 900 + index, "created_at": "2026-10-%02dT08:00:00Z" % (13 - index),
             "event": "schedule", "status": "completed", "conclusion": conclusion,
             "head_branch": "main"}
            for index, conclusion in enumerate(conclusions)]
    runs[0].update(extra)
    return {"workflow_runs": runs}


def jobs_payload(failed_steps=(), annotations_job=None, skipped=("Post to Telegram",)):
    return {"jobs": [{
        "id": 77,
        "name": "Generate Content & Post to Telegram",
        "conclusion": "failure",
        "steps": ([{"name": "Preflight — may the bot post to the channel?", "conclusion": "failure"}]
                  + [{"name": n, "conclusion": "failure"} for n in failed_steps]
                  + [{"name": n, "conclusion": "skipped"} for n in skipped]
                  + [{"name": "Set up job", "conclusion": "success"},
                     {"name": "Post Checkout repository", "conclusion": "success"}]),
    }], "annotations": annotations_job}


ANNOTATIONS = [
    {"annotation_level": "failure", "path": ".github", "start_line": 17,
     "message": "getChat(-1001234567890) failed: Bad Request: chat not found"},
    {"annotation_level": "failure", "path": ".github", "start_line": 66,
     "message": "Process completed with exit code 1."},
    {"annotation_level": "notice", "path": ".github", "start_line": 1,
     "message": "ubuntu-latest will migrate to Ubuntu 26"},
]


def fake(**kw):
    answers = {
        "actions/workflows$": workflows_payload(".github/workflows/telegram_autopost.yml"),
        "/runs?per_page": runs_payload("failure", "failure", "success"),
        "/jobs": jobs_payload(),
        "/annotations": ANNOTATIONS,
    }
    answers.update(kw)
    return FakeGh(answers)


class Reporting(unittest.TestCase):
    def test_a_failing_lane_reports_the_failing_step_and_the_annotation(self):
        gh = fake()
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            code = lane_status.main(["--lane", "telegram"], run=gh)
        text = out.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("Preflight — may the bot post to the channel?", text)
        self.assertIn("chat not found", text)
        self.assertIn("telegram_autopost.yml — active", text)

    def test_steps_that_never_ran_are_listed_because_they_are_the_diagnosis(self):
        gh = fake()
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            lane_status.main(["--lane", "telegram"], run=gh)
        self.assertIn("never ran: Post to Telegram", out.getvalue())

    def test_bookkeeping_steps_are_not_reported_as_failures_twice(self):
        """The exclusion is by *mirror*, not by prefix — `Post to Telegram` is a real step."""
        gh = fake(**{"/jobs": {"jobs": [{
            "id": 77, "name": "j", "conclusion": "failure",
            "steps": [{"name": "Set up job", "conclusion": "failure"},
                      {"name": "Checkout repository", "conclusion": "success"},
                      {"name": "Post Checkout repository", "conclusion": "failure"},
                      {"name": "Complete job", "conclusion": "failure"},
                      {"name": "Post to Telegram", "conclusion": "failure"}]}]}})
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            lane_status.main(["--lane", "telegram"], run=gh)
        text = out.getvalue()
        self.assertIn("Post to Telegram", text)
        self.assertNotIn("Set up job", text)
        self.assertNotIn("Post Checkout repository", text,
                         "the runner's cleanup line for a step that succeeded is not a failure")

    def test_a_repeated_conclusion_is_called_a_pattern(self):
        gh = fake()
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            lane_status.main(["--lane", "telegram"], run=gh)
        self.assertIn("2 consecutive runs with conclusion=failure", out.getvalue())

    def test_green_reads_green(self):
        gh = fake(**{"/runs?per_page": runs_payload("success")})
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            code = lane_status.main(["--lane", "telegram"], run=gh)
        self.assertEqual(code, 0)


class JsonMode(unittest.TestCase):
    def test_json_carries_the_history_and_the_detail(self):
        gh = fake()
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            lane_status.main(["--lane", "telegram", "--json"], run=gh)
        report = json.loads(out.getvalue())
        self.assertEqual(report["workflow"], "telegram_autopost.yml")
        self.assertEqual(report["conclusion"], "failure")
        self.assertEqual(len(report["history"]), 3)
        self.assertEqual(report["detail"][0]["failed_steps"][0]["step"],
                         "Preflight — may the bot post to the channel?")
        self.assertIn("chat not found", report["detail"][0]["annotations"][0]["message"])


class Safety(unittest.TestCase):
    def test_secrets_are_never_printed_even_when_an_annotation_quotes_them(self):
        leaked = {
            "/annotations": [{
                "annotation_level": "failure", "path": ".github", "start_line": 1,
                "message": ("TELEGRAM_BOT_TOKEN=123456789:AAH4k-testtokenvalueaaaaaaaaaaaaaaa "
                           "ghp_SECRETVALUESECRETVALUE1234 ya29.sometokenvalue_sometokenvalue "
                           "chat_id=-1001234567890")}]
        }
        gh = FakeGh({
            "actions/workflows$": workflows_payload(".github/workflows/telegram_autopost.yml"),
            "runs?per_page": runs_payload("failure"),
            "jobs": jobs_payload(),
            "/annotations": leaked["/annotations"],
        })
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            lane_status.main(["--lane", "telegram"], run=gh)
        text = out.getvalue()
        for needle in ("123456789:AAH4k", "ghp_SECRET", "ya29.sometoken", "-1001234567890"):
            self.assertNotIn(needle, text)
        self.assertIn("[redacted]", text)

    def test_it_never_asks_for_the_log_bytes_it_cannot_read(self):
        gh = fake()
        self.assertTrue(all("logs" not in call and "attempts" not in call for call in gh.calls),
                        gh.calls)

    def test_it_is_read_only(self):
        source = (ROOT / "tools" / "lane_status.py").read_text(encoding="utf-8")
        for verb in ("-X POST", "--method", "gh api -X", "gh run cancel", "gh workflow run",
                     "gh issue create", "gh secret"):
            self.assertNotIn(verb, source, verb)
        # The endpoints it may call, and nothing else: no `/logs`, no `/actions/runs/<id>/attempt`,
        # no `--method`. A status tool that can write is a status tool that can break a launch.
        allowed = re.findall(r'gh_api\("([^"]+)"', source)
        for endpoint in allowed:
            self.assertNotIn("logs", endpoint, endpoint)


class FailureModes(unittest.TestCase):
    def test_an_unknown_lane_names_the_lanes_that_exist(self):
        gh = fake()
        import io as _io
        from contextlib import redirect_stderr
        err = _io.StringIO()
        with redirect_stderr(err):
            code = lane_status.main(["--lane", "nosuch"], run=gh)
        self.assertEqual(code, 2)
        self.assertIn("known lanes", err.getvalue())

    def test_a_workflow_that_has_never_run_says_so_rather_than_lying_green(self):
        gh = FakeGh({
            "actions/workflows$": workflows_payload(".github/workflows/automation-heartbeat.yml"),
            "/runs?per_page": {"workflow_runs": []},
        })
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            code = lane_status.main(["--lane", "heartbeat"], run=gh)
        self.assertEqual(code, 2)
        self.assertIn("has never run", out.getvalue())

    def test_a_gh_failure_is_a_2_not_a_traceback(self):
        gh = FakeGh({}, error_on={"actions/workflows$": "gh: Resource not accessible (HTTP 403)"})
        import io as _io
        from contextlib import redirect_stderr
        err = _io.StringIO()
        with redirect_stderr(err):
            code = lane_status.main(["--lane", "telegram"], run=gh)
        self.assertEqual(code, 2)
        self.assertIn("could not read", err.getvalue())
        self.assertIn("403", err.getvalue())

    def test_annotations_are_optional_but_their_absence_is_said(self):
        gh = fake(**{"/annotations": {}})
        gh.error_on = {"annotations": "HTTP 404"}
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            code = lane_status.main(["--lane", "telegram"], run=gh)
        self.assertEqual(code, 1, "the run is still failing even without annotations")
        self.assertIn("annotations unreadable", out.getvalue())

    def test_the_alias_maps_to_the_scheduled_youtube_file_not_the_legacy_one(self):
        """Both `youtube_autopost.yml` and `youtube_scheduled.yml` exist; only one uploads."""
        self.assertEqual(lane_status.LANES["youtube"], "youtube_scheduled.yml")
        self.assertEqual(lane_status.LANES["youtube-legacy"], "youtube_autopost.yml")


class Integration(unittest.TestCase):
    def test_the_runbook_tells_the_boss_to_use_this(self):
        text = (ROOT / "docs" / "LAUNCH_SEQUENCE.md").read_text(encoding="utf-8")
        self.assertIn("lane_status", text,
                      "the tool that answers 'why is the lane red' in one command has to be the "
                      "command the sequence hands over, not a secret of this file's docstring")

    def test_the_environment_does_not_have_to_be_gh_free_for_the_help_text(self):
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        try:
            with redirect_stdout(out):
                lane_status.main(["--help"])
        except SystemExit as exc:
            self.assertEqual(exc.code, 0)
        self.assertIn("--lane", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class UnexecutedRuns(unittest.TestCase):
    """A run the runner never executed is not a lane outcome.

    These are the runs Actions files when a `push` touches a workflow file whose copy on the
    default branch differs from the pushed one: `conclusion=failure`, zero jobs, no annotations.
    Before this class existed, `--lane instagram` printed one of those as the lane's verdict and it
    read exactly like "the Instagram lane is broken", which is a sentence that has ended more than
    one automation project.
    """

    def test_the_newest_executed_run_is_the_one_reported(self):
        gh = FakeGh({
            "actions/workflows$": workflows_payload(".github/workflows/instagram_autopost.yml"),
            "/runs?per_page": runs_payload("failure", "failure", "success"),
            "/runs/900/jobs": {"jobs": [], "total_count": 0},   # filed, never executed
            "/runs/901/jobs": {"jobs": [], "total_count": 0},
            "/jobs": jobs_payload(),
            "/annotations": ANNOTATIONS,
        })
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            lane_status.main(["--lane", "instagram"], run=gh)
        text = out.getvalue()
        self.assertIn("2 run(s) with no jobs ignored", text,
                      "both artefacts are counted, so the number the owner reads is the number "
                      "of runs they can stop worrying about")
        self.assertIn("Preflight", text, "the run the runner really executed is the diagnosis")
        self.assertNotIn("3 consecutive", text, "an artefact must not inflate a failure streak")

    def test_the_streak_survives_the_filter(self):
        """The artefacts go; the pattern they were hiding does not.

        Filtering to the requested `--limit` would leave one run in the history and print no streak
        on a lane failing five days running, which is the opposite of what this tool is for.
        """
        gh = FakeGh({
            "actions/workflows$": workflows_payload(".github/workflows/instagram_autopost.yml"),
            "/runs?per_page": runs_payload("failure", "failure", "failure"),
            "/runs/900/jobs": {"jobs": [], "total_count": 0},
            "/jobs": jobs_payload(),
            "/annotations": [],
        })
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            lane_status.main(["--lane", "instagram", "--limit", "3"], run=gh)
        text = out.getvalue()
        self.assertIn("2 consecutive runs with conclusion=failure", text)
        self.assertIn("1 run(s) with no jobs ignored", text)

    def test_a_lane_that_has_only_ever_been_filed_says_so_and_lies_about_neither(self):
        gh = FakeGh({
            "actions/workflows$": workflows_payload(".github/workflows/instagram_autopost.yml"),
            "/runs?per_page": runs_payload("failure", "failure"),
            "/jobs": {"jobs": [], "total_count": 0},
        })
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            code = lane_status.main(["--lane", "instagram"], run=gh)
        text = out.getvalue()
        self.assertEqual(code, 2, "neither green nor red: the tool cannot tell you about the lane")
        self.assertIn("executed none of them", text)
        self.assertIn("Nothing was posted and nothing failed", text)

    def test_json_carries_the_count_because_a_gate_reads_it(self):
        gh = FakeGh({
            "actions/workflows$": workflows_payload(".github/workflows/instagram_autopost.yml"),
            "/runs?per_page": runs_payload("failure", "success"),
            "/runs/900/jobs": {"jobs": [], "total_count": 0},
            "/jobs": jobs_payload(),
            "/annotations": [],
        })
        import io as _io
        import json as _json
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            lane_status.main(["--lane", "instagram", "--json"], run=gh)
        report = _json.loads(out.getvalue())
        self.assertEqual(report["unexecuted_runs_ignored"], 1)

    def test_a_run_still_in_progress_is_not_mistaken_for_an_artefact(self):
        """In-progress runs have no jobs *yet*; calling that "never executed" would hide a live
        run from the one command that exists to answer "did today's post go out?".
        """
        gh = FakeGh({
            "actions/workflows$": workflows_payload(".github/workflows/instagram_autopost.yml"),
            "/runs?per_page": runs_payload("neutral", status="in_progress"),
            "/jobs": jobs_payload(),
            "/annotations": [],
        })
        import io as _io
        from contextlib import redirect_stdout
        out = _io.StringIO()
        with redirect_stdout(out):
            code = lane_status.main(["--lane", "instagram"], run=gh)
        self.assertNotIn("no jobs ignored", out.getvalue())
        self.assertIn("in_progress", out.getvalue())
