"""Static contract tests for the automation workflows.

Why these exist
---------------
The Shorts workflow runs unattended, twice a week, and the token in a coding
session cannot dispatch it. So a mistake inside `youtube_scheduled.yml` — a
typo'd step id, a dropped permission — does not fail in CI, does not fail in a
test, and does not fail loudly on Friday. It fails as an empty string: GitHub
substitutes an unknown `steps.<id>.outputs.<key>` with `""`, the upload runs
with no title, and the ledger records nothing.

These tests cannot prove the YAML runs correctly (nothing can, short of
running it), but they catch the failure mode that is silent: references that
point at something that isn't there.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - the CI job installs it
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
STEP_REF = re.compile(r"steps\.([\w-]+)\.outputs\.([\w-]+)")


@unittest.skipIf(yaml is None, "PyYAML is required for the workflow contract tests")
class WorkflowReferenceTests(unittest.TestCase):
    def _jobs(self, path):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        return doc.get("jobs", {})

    def test_every_step_reference_points_at_a_step_that_comes_before_it(self):
        """An unknown step id silently becomes "" — the classic silent failure."""
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for job_name, job in self._jobs(path).items():
                steps = job.get("steps") or []
                seen_ids = []
                for step in steps:
                    if step.get("id"):
                        seen_ids.append(step["id"])
                    blob = "\n".join(str(step.get(k, "")) for k in ("if", "run", "with"))
                    if isinstance(step.get("env"), dict):
                        blob += "\n" + "\n".join(str(v) for v in step["env"].values())
                    for step_id, key in STEP_REF.findall(blob):
                        with self.subTest(workflow=path.name, job=job_name, step=step.get("name"), ref=step_id):
                            self.assertIn(
                                step_id,
                                seen_ids,
                                "%s: ${{ steps.%s.outputs.%s }} — no such step id in this job "
                                "(it would resolve to an empty string at run time)"
                                % (path.name, step_id, key),
                            )

    def test_every_workflow_parser_reference_is_a_real_parser(self):
        """steps.X.outputs for steps that use an action have a documented output."""
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for job in self._jobs(path).values():
                for step in job.get("steps") or []:
                    if not step.get("id") or "uses" not in step:
                        continue
                    # actions/checkout and setup-python publish no job outputs;
                    # guard against someone reading outputs.<key> off one.
                    for other in job.get("steps") or []:
                        blob = str(other.get("run", "")) + str(other.get("if", ""))
                        if str(other.get("env", "")):
                            blob += str(other["env"])
                        for step_id, key in STEP_REF.findall(blob):
                            if step_id != step.get("id"):
                                continue
                            with self.subTest(workflow=path.name, step=step_id):
                                self.assertFalse(
                                    step["uses"].startswith(("actions/checkout@", "actions/setup-python@")),
                                    "%s: %s is an action with no outputs.%s" % (path.name, step["uses"], key),
                                )


class DeployLogRedactionTests(unittest.TestCase):
    """Remote Wrangler config diffs must never publish dashboard secret values."""

    def test_secret_like_values_are_redacted_but_public_config_survives(self):
        # Same opaque value under a sensitive name and a harmless name proves
        # redaction is driven by the key, not by a recognizable value pattern.
        opaque_hash = "N7!q4L#z2vP8_x"
        sample = (
            '  - BREVO_API_KEY: "fake-brevo-secret"\n'
            f'  - FLW_WEBHOOK_HASH: "{opaque_hash}"\n'
            '  - FLW_SECRET_KEY:\n'
            '    fake-flutterwave-secret\n'
            '  - SITE_URL: "https://docoga.com.ng"\n'
            f'  - PUBLIC_NOTE: "{opaque_hash}"\n'
        )
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "redact_deploy_log.py")],
            input=sample, text=True, capture_output=True, check=True,
        )
        self.assertNotIn("fake-brevo-secret", result.stdout)
        self.assertNotIn("fake-flutterwave-secret", result.stdout)
        self.assertIn("BREVO_API_KEY: [REDACTED]", result.stdout)
        self.assertIn("FLW_WEBHOOK_HASH: [REDACTED]", result.stdout)
        self.assertIn("FLW_SECRET_KEY: [REDACTED]", result.stdout)
        self.assertIn('SITE_URL: "https://docoga.com.ng"', result.stdout)
        self.assertIn(f'PUBLIC_NOTE: "{opaque_hash}"', result.stdout)
        self.assertEqual(result.stdout.count(opaque_hash), 1)


class PassCacheContractTests(unittest.TestCase):
    def test_server_rejection_clears_a_cached_pass(self):
        source = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn("/(expired|invalid code)/i.test(j.error)", source)
        self.assertIn("store.removeItem('docoga_pass'); pass=null;", source)


@unittest.skipIf(yaml is None, "PyYAML is required for the workflow contract tests")
class CloudflareDeploySafetyTests(unittest.TestCase):
    def test_worker_deploy_preserves_vars_and_sanitizes_raw_wrangler_output(self):
        doc = yaml.safe_load((WORKFLOWS / "deploy-pass-now.yml").read_text(encoding="utf-8"))
        job = doc["jobs"]["deploy"]
        deploy = next(step for step in job["steps"] if step.get("name") == "Deploy worker/ as docoga-pass")
        self.assertIn("--keep-vars", deploy["run"])
        self.assertIn('>"$RAW_WRANGLER_LOG" 2>&1', deploy["run"])
        self.assertIn("tools/redact_deploy_log.py", deploy["run"])
        self.assertNotIn('> >(tee -a "$DEPLOY_LOG")', deploy["run"])
        self.assertEqual(doc["permissions"].get("pull-requests"), "write")

    def test_site_deploy_preserves_vars_and_sanitizes_raw_wrangler_output(self):
        doc = yaml.safe_load((WORKFLOWS / "deploy-site-now.yml").read_text(encoding="utf-8"))
        job = doc["jobs"]["deploy-site"]
        deploy = next(step for step in job["steps"] if step.get("name") == "Deploy docoga-git from ./site")
        self.assertIn("--keep-vars", deploy["run"])
        self.assertIn('>"$RAW_WRANGLER_LOG" 2>&1', deploy["run"])
        self.assertIn("tools/redact_deploy_log.py", deploy["run"])
        self.assertEqual(job["permissions"].get("pull-requests"), "write")


@unittest.skipIf(yaml is None, "PyYAML is required for the workflow contract tests")
class DeployExecutionSafetyTests(unittest.TestCase):
    """Execute actual workflow shell scripts with stubs: never contact providers."""

    def steps(self, workflow, job):
        doc = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))
        return {s.get("name"): s for s in doc["jobs"][job]["steps"]}

    def run_shell(self, step, exit_code=0, fail_redactor=False):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            (temp / "worker").mkdir()
            (temp / "tools").mkdir()
            (temp / "tools" / "redact_deploy_log.py").write_text(
                (ROOT / "tools" / "redact_deploy_log.py").read_text())
            stub = temp / "npx"
            stub.write_text(
                '#!/bin/bash\n'
                'printf "%s\\n" "$*" >> "$CALLS"\n'
                "echo 'FLW_SECRET_KEY: \"fake-private-value\"'\n"
                'echo "fake wrangler status"\n'
                f'exit {exit_code}\n'
            )
            stub.chmod(0o755)
            # A redaction failure must not be hidden by tee's successful exit.
            if fail_redactor:
                py = temp / "python3"
                py.write_text('#!/bin/bash\nexit 23\n')
                py.chmod(0o755)
            env = dict(os.environ, PATH=f"{temp}:{os.environ['PATH']}",
                       RUNNER_TEMP=td, DEPLOY_LOG=str(temp / "deploy.log"),
                       GITHUB_ENV=str(temp / "github-env"), CALLS=str(temp / "calls"))
            result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step["run"]],
                                    cwd=temp, env=env, capture_output=True, text=True)
            calls = (temp / "calls").read_text() if (temp / "calls").exists() else ""
            raw_logs = list(temp.glob("*.raw.log"))
            return result, calls, raw_logs

    def test_auth_diagnostic_marker_never_publishes_or_probes(self):
        doc = yaml.safe_load((WORKFLOWS / "deploy-pass-now.yml").read_text())
        self.assertIn("[check-pass-auth]", doc["jobs"]["deploy"]["if"])
        steps = self.steps("deploy-pass-now.yml", "deploy")
        for name in ("Deploy worker/ as docoga-pass", "Probe the live worker"):
            self.assertIn("!contains(github.event.head_commit.message, '[check-pass-auth]')", steps[name]["if"])
        token = steps["Verify the token against Cloudflare"]
        self.assertIn("tools/verify_cloudflare_token.py | tee", token["run"])
        self.assertIn("CF_ACCOUNT", token["env"])
        self.assertNotIn("curl", token["run"])
        self.assertNotIn("set -x", token["run"])

    def test_worker_dry_run_is_isolated_from_all_production_steps(self):
        steps = self.steps("deploy-pass-now.yml", "deploy")
        dry = steps["Validate worker only (manual dry-run)"]
        self.assertEqual(dry["if"], "${{ github.event_name == 'workflow_dispatch' && inputs.dry_run }}")
        self.assertNotIn("env", dry)  # no provider credentials
        for name, step in steps.items():
            if name in (None, "Validate worker only (manual dry-run)"):
                continue  # checkout and setup-node have no network side effects at providers
            with self.subTest(step=name):
                self.assertIn("github.event_name != 'workflow_dispatch' || !inputs.dry_run", step["if"])
        result, calls, _ = self.run_shell(dry)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls.splitlines()), 1)
        self.assertIn("--dry-run", calls)
        self.assertIn("--config wrangler.toml", calls)
        self.assertNotIn("curl", dry["run"])

    def test_worker_dry_run_build_failure_is_not_hidden(self):
        dry = self.steps("deploy-pass-now.yml", "deploy")["Validate worker only (manual dry-run)"]
        result, _, _ = self.run_shell(dry, exit_code=42)
        self.assertEqual(result.returncode, 42)

    def test_both_deploys_propagate_failure_and_delete_private_logs(self):
        for workflow, job, name, config in (
            ("deploy-pass-now.yml", "deploy", "Deploy worker/ as docoga-pass", "wrangler.toml"),
            ("deploy-site-now.yml", "deploy-site", "Deploy docoga-git from ./site", "wrangler.jsonc"),
        ):
            step = self.steps(workflow, job)[name]
            for exit_code in (0, 42):
                with self.subTest(workflow=workflow, exit_code=exit_code):
                    result, calls, raw_logs = self.run_shell(step, exit_code)
                    self.assertEqual(result.returncode, exit_code, result.stderr)
                    self.assertEqual(raw_logs, [])
                    self.assertNotIn("fake-private-value", result.stdout + result.stderr)
                    self.assertIn("[REDACTED]", result.stdout)
                    self.assertIn(f"deploy_exit={exit_code}", result.stdout)
                    self.assertEqual(len(calls.splitlines()), 1)
                    self.assertIn(f"--config {config} --keep-vars", calls)
            with self.subTest(workflow=workflow, sanitizer_failure=True):
                result, _, raw_logs = self.run_shell(step, fail_redactor=True)
                self.assertEqual(result.returncode, 23)
                self.assertEqual(raw_logs, [])
                self.assertNotIn("fake-private-value", result.stdout + result.stderr)

    def test_live_probe_cannot_verify_or_issue_a_payment(self):
        steps = self.steps("deploy-pass-now.yml", "deploy")
        probe = steps["Probe the live worker"]["run"]
        self.assertIn('$WORKER/activate"', probe)
        self.assertNotIn("?code=", probe)
        self.assertNotRegex(probe, r"\$WORKER/(verify|issue|flw-webhook|resend-email)")
        self.assertIn('test "$STATUS" = 400', probe)
        self.assertIn('d.get("error") == "code required"', probe)

    def test_reporting_after_failure_does_not_publish_dry_run_results(self):
        steps = self.steps("deploy-pass-now.yml", "deploy")
        self.assertEqual(steps["Post result where the agent can read it"]["if"],
                         "${{ always() && (github.event_name != 'workflow_dispatch' || !inputs.dry_run) }}")
        for name in ("Verify the token against Cloudflare", "Deploy worker/ as docoga-pass", "Probe the live worker"):
            self.assertIn("env.RESULT == 'SECRETS_PRESENT'", steps[name]["if"])


@unittest.skipIf(yaml is None, "PyYAML is required for the workflow contract tests")
class ScheduledShortsWorkflowTests(unittest.TestCase):
    """Invariants specific to the unattended Shorts pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.doc = yaml.safe_load((WORKFLOWS / "youtube_scheduled.yml").read_text(encoding="utf-8"))
        cls.job = cls.doc["jobs"]["generate-and-publish"]
        cls.steps = cls.job["steps"]
        cls.by_name = {s.get("name"): s for s in cls.steps}
        cls.by_id = {s.get("id"): s for s in cls.steps if s.get("id")}

    def blob(self, name):
        step = self.by_name[name]
        return "\n".join([str(step.get("run", "")), str(step.get("if", "")), str(step.get("env", ""))])

    def test_it_runs_on_the_weekday_schedule(self):
        crons = [entry["cron"] for entry in (self.doc[True] if True in self.doc else self.doc["on"])["schedule"]]
        self.assertEqual(crons, ["0 17 * * 1-5"], "the 18:00 WAT slot, every weekday (Mon + Thu added 17 Oct 2026), must not drift")

    def test_every_upload_gets_its_playlist_and_first_comment(self):
        step = self.by_name["Playlist + first comment (never fails the publish)"]
        self.assertTrue(step.get("continue-on-error"), "a boost must never turn a publish red")
        self.assertIn("yt_boost.py plan", step["run"])
        self.assertIn("yt_boost.py run", step["run"])
        self.assertIn("--parent-comment", step["run"])
        for key in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "SOCIAL_TOKEN_KEY", "PINNED_COMMENT"):
            self.assertIn(key, step["env"])
        self.assertIn("logs/youtube_boosts.json", self.by_name["Commit the publish ledger"]["run"])

    def test_the_short_also_goes_to_telegram_as_a_native_video(self):
        step = self.by_name["Post the Short to the Telegram channel"]
        self.assertTrue(step.get("continue-on-error"), "a Telegram refusal must not redden a successful YouTube upload")
        self.assertIn("tools/telegram_video.py", step["run"])
        self.assertIn("steps.upload.outputs.video_id != ''", step["if"])
        self.assertIn("TELEGRAM_BOT_TOKEN", step["env"])

    def test_it_can_write_the_ledger_and_open_an_issue(self):
        permissions = self.doc.get("permissions") or {}
        self.assertEqual(permissions.get("contents"), "write")
        self.assertEqual(permissions.get("issues"), "write")

    def test_overlapping_runs_cannot_race_each_other(self):
        """Two runs at once would both pass the duplicate guard and publish twice."""
        group = (self.doc.get("concurrency") or self.job.get("concurrency") or {}).get("group")
        self.assertEqual(group, "youtube-shorts-scheduled")

    def test_the_duplicate_guard_runs_before_the_upload(self):
        names = [s.get("name") for s in self.steps]
        self.assertLess(names.index("Duplicate guard (publish ledger)"), names.index("Upload to YouTube"))

    def test_the_upload_is_skipped_when_the_guard_says_skip(self):
        for name in ("Upload to YouTube", "Record the publish in the ledger", "Commit the publish ledger"):
            with self.subTest(step=name):
                condition = self.by_name[name].get("if") or ""
                self.assertIn("steps.guard.outputs.skip != 'yes'", condition,
                              "a re-run of a duplicate must still be refused")
        # Recording is gated on *an id existing*, not on the upload step being green: a video
        # YouTube stored as private is on the channel, and an unrecorded id is a duplicate waiting
        # for the next run.
        record = self.by_name["Record the publish in the ledger"].get("if") or ""
        self.assertIn("always()", record)
        self.assertIn("steps.upload.outputs.video_id != ''", record)

    def test_the_guard_treats_force_true_as_clear_to_publish(self):
        """Regression: the first draft exited 3 (the duplicate code) when force
        was requested, so forcing a re-publish failed the run instead."""
        guard = self.blob("Duplicate guard (publish ledger)")
        self.assertIn('"$FORCE" = "true"', guard)
        self.assertNotIn('"$FORCE" != "true"', guard)

    def test_the_upload_step_carries_the_uploaders_verdict(self):
        """The step parses YT_* markers into outputs; the ledger, the summary and the issue body
        all read them, so a cause cannot be lost between the uploader and the human."""
        upload = self.blob("Upload to YouTube")
        for marker in ("YT_UPLOAD_RESULT", "YT_PRIVACY", "YT_FAIL_KIND", "YT_FAIL_REASON",
                       "YT_UPLOAD_STATE", "YT_NOTE"):
            with self.subTest(marker=marker):
                self.assertIn(marker, upload)
        self.assertIn("code=${PIPESTATUS[0]}", upload,
                      "tee swallows the uploader's exit code, which is the whole diagnosis")
        self.assertIn('exit "$code"', upload, "and the step must still fail the run with it")
        for output in ("result", "privacy_seen", "fail_kind", "fail_reason", "note"):
            with self.subTest(output=output):
                self.assertIn('echo "%s=' % output, upload)

    def test_the_failure_issue_says_whether_a_video_exists(self):
        """'Nothing may have been published' sends a person to check the channel first; the id
        already knows the answer, so the issue must state it."""
        issue = self.blob("Open a visible issue if the run failed")
        self.assertIn("Nothing was published by this run", issue)
        self.assertIn("Do NOT re-run before deciding", issue)
        self.assertIn("In testing", issue, "the 7-day refresh-token expiry is the cause this lane kept missing")
        self.assertNotIn("Nothing may have been published", issue)

    def test_a_probe_only_run_uploads_nothing_and_renders_nothing(self):
        doc = self.doc
        probe = doc["jobs"]["probe"]
        self.assertEqual(probe.get("if"), "github.event.inputs.probe_only == 'true'")
        names = [s.get("name") for s in probe["steps"]]
        self.assertNotIn("Generate today's Short", names)
        self.assertTrue(any("--probe" in (s.get("run") or "") for s in probe["steps"]))
        publish = doc["jobs"]["generate-and-publish"]
        self.assertIn("github.event.inputs.probe_only != 'true'", publish.get("if") or "")
        self.assertIn("github.event_name == 'schedule'", publish.get("if") or "",
                      "the schedule must never be silenced by an input it does not have")

    def test_the_preflight_proves_more_than_presence(self):
        preflight = self.blob("Preflight — are the YouTube secrets present and usable?")
        self.assertIn("--probe", preflight,
                      "presence proved nothing on 9 Oct: the step was green with a dead token")

    def test_ledger_bookkeeping_does_not_retrigger_ci(self):
        commit = self.blob("Commit the publish ledger")
        self.assertIn("[skip ci]", commit,
                      "a ledger push that fires Verify burns the free plan's minutes")

    def test_the_uploader_video_id_is_captured_or_the_run_fails(self):
        """yt_publish.py prints VIDEO_ID=; without it the ledger entry is blank."""
        upload = self.blob("Upload to YouTube")
        self.assertIn("VIDEO_ID", upload)
        self.assertIn("No video id", upload)

    def test_a_failed_run_leaves_a_visible_issue(self):
        step = self.by_name["Open a visible issue if the run failed"]
        self.assertEqual(step.get("if"), "failure()")
        self.assertIn("GH_TOKEN", str(step.get("env")))
        self.assertIn("gh issue create", step["run"])

    def test_the_privacy_switch_is_owner_controllable_without_a_code_change(self):
        settings = self.blob("Resolve the settings for this run")
        self.assertIn("vars.YT_PRIVACY", settings)
        # A typo in that variable must fail loudly, not publish at the wrong privacy.
        self.assertIn("Bad privacy setting", settings)

    def test_the_ledger_steps_use_the_same_default_ledger_path(self):
        """check and record silently disagreeing about the file would make the
        duplicate guard read one file and the recorder write another."""
        for name in ("Duplicate guard (publish ledger)", "Record the publish in the ledger"):
            with self.subTest(step=name):
                self.assertIn("tools/youtube_ledger.py", self.blob(name))
                self.assertNotIn("--ledger ", self.blob(name))

    def test_ledger_bookkeeping_never_turns_a_successful_publish_red(self):
        self.assertTrue(self.by_name["Commit the publish ledger"].get("continue-on-error"))

    def test_the_summary_runs_even_when_everything_else_fails(self):
        self.assertEqual(self.by_name["Write the run summary"].get("if"), "always()")

    def test_every_step_that_runs_gh_declares_a_token(self):
        for step in self.steps:
            if "gh " in str(step.get("run", "")):
                with self.subTest(step=step.get("name")):
                    self.assertIn("GH_TOKEN", str(step.get("env", "")))


@unittest.skipIf(yaml is None, "PyYAML is required for the workflow contract tests")
class FailureIssueHygieneTests(unittest.TestCase):
    """The three lanes file issues; this pins *how*, because a noisy inbox is a dead lane.

    Two rules the launch sequence depends on, both easy to lose in a later edit:

      * one issue per cause, not per day — a lane failing for the same reason every morning
        comments on its open issue instead of filing a new one (the Shorts lane used to file
        eight issues a month for one un-published OAuth consent screen); and
      * "never configured" is titled `setup`, not `run`, so a secret the boss has not set yet
        does not read like an outage.

    The telegram and facebook classifiers are *executed* here rather than grepped: they are
    shell, and shell that only looks right in a review is how a workflow ships broken.
    """

    STEP = "Open a visible issue if the run failed"
    LANES = {"telegram_autopost.yml": "telegram-automation",
             "facebook_autopost.yml": "facebook-automation",
             "youtube_scheduled.yml": "youtube-automation",
             # The Meta lanes join the same contract on the day they are written, not "later":
             # every rule in this class exists because a lane without one hid a failure for days.
             "threads_autopost.yml": "threads-automation",
             "instagram_autopost.yml": "instagram-automation",
             "linkedin_autopost.yml": "linkedin-automation"}

    @classmethod
    def setUpClass(cls):
        cls.steps = {}
        for name in cls.LANES:
            doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
            found = [s for job in doc["jobs"].values() for s in job.get("steps", [])
                     if s.get("name") == cls.STEP]
            assert len(found) == 1, "%s: expected exactly one %r step" % (name, cls.STEP)
            step = found[0]
            # if/env/run as one blob: what a step *does* includes what it is handed.
            blob = "\n".join([str(step.get("if", "")), str(step.get("run", ""))]
                             + ["%s: %s" % kv for kv in (step.get("env") or {}).items()])
            cls.steps[name] = blob

    def classify(self, workflow, log_text):
        """Run the workflow's own classifier with a log body and report the cause it chose."""
        # Only the `case` itself: the real step reads `TAIL=$(cat …)`, and replaying that line
        # here would blank the log the test is trying to classify.
        block = re.search(r"case .\$TAIL. in.*?\n\s*esac", self.steps[workflow], re.S)
        self.assertIsNotNone(block, "the lane has no log classifier to test")
        quote = chr(39)  # a single quote, so the fixture text stays readable
        # An apostrophe in a Telegram error message ("can't parse entities") is the reason this
        # needs escaping and not just quoting.
        log_text = log_text.replace(quote, quote + chr(92) + quote + quote)
        script = "TAIL=" + quote + log_text + quote + chr(10) + block.group(0) + chr(10) + "printf %s " + chr(34) + chr(36) + "CAUSE" + chr(34)
        done = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def test_a_missing_secret_is_setup_and_not_an_outage(self):
        self.assertEqual(self.classify("telegram_autopost.yml",
                                       "ERROR: Telegram secrets missing — set TELEGRAM_CHAT_ID"), "setup")
        self.assertEqual(self.classify("facebook_autopost.yml",
                                       "The page access token is not configured on this repository"), "setup")

    def test_a_dead_credential_is_named_as_one(self):
        self.assertEqual(self.classify("telegram_autopost.yml", "getMe failed: Unauthorized"), "credentials")
        self.assertEqual(self.classify("facebook_autopost.yml",
                                       "Error validating access token: the session has been invalidated"),
                         "credentials")

    def test_a_wrong_channel_and_a_refused_right_are_told_apart(self):
        self.assertEqual(self.classify("telegram_autopost.yml",
                                       "Forbidden: bot is not a member of the channel chat"), "chat")
        self.assertEqual(self.classify("telegram_autopost.yml",
                                       "Bad Request: have no rights to send a message"), "rights")

    def test_an_unrecognised_failure_still_becomes_a_run_never_an_empty_title(self):
        self.assertEqual(self.classify("telegram_autopost.yml",
                                       "can't find end of entities"), "run")
        self.assertEqual(self.classify("facebook_autopost.yml", "something nobody has seen yet"), "run")

    def test_the_shorts_lane_borrows_the_uploaders_kind(self):
        """The uploader classifies; the workflow must not re-guess it."""
        text = self.steps["youtube_scheduled.yml"]
        self.assertIn('CAUSE="${FAIL_KIND:-run}"', text)
        self.assertIn("FAIL_KIND: ${{ steps.upload.outputs.fail_kind }}", text)
        self.assertIn('CAUSE=run', text)
        block = re.search(r"CAUSE=.*?CAUSE=run", text, re.S).group(0)
        for value, expected in (("quota", "quota"), ("", "run"), ("none", "run")):
            with self.subTest(FAIL_KIND=value):
                script = "FAIL_KIND=%s\n%s\nprintf %%s \"$CAUSE\"" % (value, block)
                done = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
                self.assertEqual(done.stdout.strip(), expected)

    def test_the_cause_tag_is_both_the_title_and_the_dedupe_key(self):
        for name in self.LANES:
            with self.subTest(workflow=name):
                text = self.steps[name]
                self.assertIn('CAUSE_TAG="[$CAUSE]"', text)
                self.assertIn("contains(", text)
                self.assertIn("$ENV.CAUSE_TAG", text)
                self.assertIn("[$CAUSE]", text, "the tag has to be in the title to be found again")
                self.assertIn("--state open", text, "a closed issue must not absorb a new failure")

    @unittest.skipIf(subprocess.run(["bash", "-c", "command -v jq"], capture_output=True).returncode != 0,
                     "jq is not installed")
    def test_the_real_filter_selects_the_real_titles(self):
        """The selector is *read out of the workflow* and run, not re-typed here.

        A test that copies the jq filter is a test of the copy: it stays green while the
        workflow drifts. So this lifts the filter text, unescapes it the way bash would, and
        feeds it the titles the lane has actually filed — including `#16` and `#12`, which were
        filed before a cause lived in the title and must be folded in rather than doubled.
        """
        text = self.steps["telegram_autopost.yml"]
        # The filter contains its own escaped quotes, so a non-greedy `"(.*?)"` stops inside
        # `contains("[\")`. Take it by its ends instead: after `--jq "`, up to the closing of the
        # selector — and fail loudly if that shape ever changes, rather than testing a truncation.
        head = "--jq " + chr(34)
        tail = "max // empty" + chr(34) + ")"
        self.assertIn(head, text, "the selector's --jq argument is gone")
        self.assertIn(tail, text, "the selector no longer ends where this test reads it from")
        start = text.index(head) + len(head)
        filter_ = text[start:text.index(tail, start) + len("max // empty")]
        filter_ = filter_.replace(chr(92) + chr(34), chr(34)).replace(chr(92) + chr(36), chr(36))
        self.assertIn("CAUSE_TAG", filter_)

        def issue(number, title):
            return '{"number": %d, "title": %s}' % (number, chr(34) + title + chr(34))

        def json_array(*entries):
            return chr(91) + ",".join(entries) + chr(93)

        legacy_issue = issue(16, "Telegram post failed — 2026-10-11")
        tagged_issue = issue(21, "Telegram post failed — 2026-10-14 [setup]")
        other_cause = issue(22, "Telegram post failed — 2026-10-14 [chat]")
        tag_only = issue(9, "Some other title carrying [setup]")

        # The fold-in rule, stated once so the cases below are about behaviour and not syntax:
        # an issue filed *before* causes lived in the title has no cause to disagree about, so
        # today's failure comments on it; once titles carry causes, a new cause is a new issue.
        cases = [
            ("both a legacy and a tagged issue are open", json_array(legacy_issue, tagged_issue),
             "[setup]", "21"),
            ("a legacy issue absorbs a failure of any cause", json_array(legacy_issue),
             "[chat]", "16"),
            ("a new cause opens its own issue", json_array(other_cause), "[setup]", ""),
            # The title is not enough to identify a lane's issue — the *label* is, and the
            # `gh issue list --label` scoping upstream of this filter is what makes it safe for
            # the filter to trust a bare `[setup]`. Asserted so nobody "tightens" the filter and
            # simultaneously loosens the label, which would break one of the two.
            ("an issue that matches only by tag is still ours, because the label is the scope",
             json_array(tag_only), "[setup]", "9"),
        ]
        for name, issues, tag, expected in cases:
            with self.subTest(case=name):
                script = ("echo " + chr(39) + issues + chr(39)
                          + " | CAUSE_TAG=" + chr(34) + tag + chr(34)
                          + " LEGACY_PREFIX=" + chr(34) + "Telegram post failed — " + chr(34)
                          + " jq -r " + chr(39) + filter_ + chr(39))
                done = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(done.stdout.strip(), expected)

    def test_commenting_and_filing_can_never_make_a_run_more_broken_than_it_already_is(self):
        for name in self.LANES:
            with self.subTest(workflow=name):
                text = self.steps[name]
                self.assertIn('gh issue comment "$EXISTING" --body-file /tmp/issue_body.md || true', text)
                create = text[text.index("gh issue create"):]
                self.assertTrue('|| echo "::warning' in create or "|| true" in create,
                                "an issue that cannot be filed is a warning, not a second failure")

    def test_a_jq_env_needle_is_never_an_unexported_shell_variable(self):
        """`$ENV.X` reads the *environment*; `X=…` on its own line is a shell variable.

        This is how `main`'s Telegram dedupe has been matching nothing since it was written:
        `RUN_DATE="$(date +%F)"` then `contains($ENV.RUN_DATE)` — jq receives an empty string,
        `contains("")` is true for every issue, and the lane comments on whatever happens to be
        open instead of deduping by day. The fix is one word (`X=v command`) or `export`, and the
        test is here so the next person does not have to read an annotation to find it.
        """
        needle = re.compile(r"\$ENV\.([A-Z_][A-Z0-9_]*)")
        offenders = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            lines = path.read_text(encoding="utf-8").split("\n")
            for number, line in enumerate(lines):
                for name in needle.findall(line):
                    window = "\n".join(lines[max(0, number - 4):number + 1])
                    supplied = re.search(r"(?m)^\s*(export\s+)?" + name + "=", window) \
                        or re.search(name + "=\"?[^\n]*\\?\s*$", window) \
                        or (name + "=" in window and "gh " in window)
                    if not supplied:
                        offenders.append("%s:%d $ENV.%s" % (path.name, number + 1, name))
        self.assertEqual(offenders, [],
                         "these jq needles can never see their value — put VAR=x on the same "
                         "command as `gh`, or export it: " + "; ".join(offenders))

    def test_the_heartbeat_still_finds_each_lane_by_its_create_line(self):
        """`tools/automation_heartbeat.py` discovers a lane's label by reading the
        `gh issue create --label …` line out of the workflow, so re-wording that line edits
        the monitor's data classification. Asserted, not assumed."""
        hb = (ROOT / "tools" / "automation_heartbeat.py").read_text(encoding="utf-8")
        self.assertRegex(hb, r"_ISSUE_LABEL\s*=\s*re\.compile")
        for name, label in self.LANES.items():
            with self.subTest(workflow=name):
                found = re.search(r"gh issue create.*?--label (\S+)", self.steps[name], re.S)
                self.assertEqual(found.group(1).rstrip("\\").strip(), label)


if __name__ == "__main__":
    unittest.main()


# ── rules that apply to every workflow ──────────────────────────────────────
INPUT_REF = re.compile(r"\$\{\{\s*inputs\.[\w.]+\s*\}\}")
SECRETISH = re.compile(r"(TOKEN|SECRET|PASSWORD|PASSPHRASE|APP_SECRET|API_KEY|KEY)\b")
ENV_DEFAULT = re.compile(r"""environ\.get\(\s*["']([A-Z0-9_]+)["']\s*,\s*["']([^"']{8,})["']""")
FLAG = re.compile(r"(?<![\w-])(--[\w-]+)(?![\w-])")


# ── rules that apply to every workflow ──────────────────────────────────────
INPUT_REF = re.compile(r"\$\{\{\s*inputs\.[\w.]+\s*\}\}")
SECRETISH = re.compile(r"(TOKEN|SECRET|PASSWORD|PASSPHRASE|APP_SECRET|API_KEY|KEY)\b")
ENV_DEFAULT = re.compile(r"""environ\.get\(\s*["']([A-Z0-9_]+)["']\s*,\s*["']([^"']{8,})["']""")
FLAG = re.compile(r"(?<![\w-])(--[\w-]+)(?![\w-])")


@unittest.skipIf(yaml is None, "PyYAML is required for the workflow contract tests")
class EveryWorkflowTests(unittest.TestCase):
    """The two bug classes that broke the Facebook and Instagram workflows.

    Both were "valid YAML, never ran": a `run:` block with broken quoting fails
    only at run time, and an input interpolated straight into a shell command is
    an injection hole that only bites the day someone types a quote.
    """

    def _workflows(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            yield path, yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_an_exit_code_captured_from_pipestatus_is_captured_with_errexit_off(self):
        """GitHub runs every `run:` under `bash -eo pipefail`. A step that pipes a tool into
        `tee` and then reads `${PIPESTATUS[0]}` only reaches that line when the tool exits 0 —
        the one case where nobody needs the code. When the tool exits 1 on purpose (the
        heartbeat judging a lane silent, a publisher refusing to post), `-e` ends the step at
        the pipe, the outputs are never written, and the next step sees an empty signature or
        result. That is how the heartbeat went red four nights running (13–16 Oct 2026)
        without ever filing its issue. Rule: errexit must be off (`set +e`) at the line that
        reads PIPESTATUS, and `set -o pipefail` alone does not switch it off."""
        flag = re.compile(r"\bset ([+-][a-zA-Z]+)")
        for path, doc in self._workflows():
            for job in (doc.get("jobs") or {}).values():
                for step in job.get("steps") or []:
                    run = step.get("run") or ""
                    if "PIPESTATUS" not in run:
                        continue
                    lines = run.split("\n")
                    for index, line in enumerate(lines):
                        if "PIPESTATUS" not in line or line.strip().startswith("#") or "=" not in line:
                            continue
                        errexit = True
                        code = "\n".join(l for l in lines[:index] if not l.strip().startswith("#"))
                        for flags in flag.findall(code):
                            if "e" in flags[1:]:
                                errexit = flags[0] == "-"
                        self.assertFalse(errexit,
                                         "%s step %r reads PIPESTATUS with errexit on: the tool's "
                                         "non-zero exit kills the step before this line, so the "
                                         "outputs after it are never written. Put `set +e` before "
                                         "the pipeline and `set -e` after the capture."
                                         % (path.name, step.get("name")))

    def test_a_step_excluded_for_an_inputs_default_is_also_excluded_on_schedule(self):
        """`inputs.mode != 'daily'` reads as "manual modes only" — but on a *scheduled* run every
        input is empty, '' != 'daily' is true, and the manual step runs with no message. That is
        how the Facebook lane posted correctly on 15 and 16 Oct 2026 and still went red twice.
        Rule: a step gated on `inputs.X != <the default of X>` must also be gated on
        `github.event_name`, because a schedule behaves as the defaults."""
        import re
        pattern = re.compile(r"inputs\.([a-z_]+)\s*!=\s*'([^']*)'")
        for path, doc in self._workflows():
            on = doc.get(True) or doc.get("on") or {}
            if not isinstance(on, dict) or "schedule" not in on:
                continue
            dispatch = on.get("workflow_dispatch") or {}
            inputs = (dispatch.get("inputs") or {}) if isinstance(dispatch, dict) else {}
            for job_name, job in (doc.get("jobs") or {}).items():
                for step in job.get("steps") or []:
                    cond = str(step.get("if") or "")
                    for name, value in pattern.findall(cond):
                        default = (inputs.get(name) or {}).get("default")
                        if str(default) != value:
                            continue
                        with self.subTest(workflow=path.name, step=step.get("name")):
                            self.assertIn("github.event_name", cond,
                                          "%s step %r is gated on inputs.%s != %r (its default) — "
                                          "on a scheduled run that input is empty and the step runs; "
                                          "add `github.event_name == 'workflow_dispatch'`"
                                          % (path.name, step.get("name"), name, value))

    def test_a_job_that_files_issues_holds_the_issues_grant(self):
        """`gh issue create` with a GITHUB_TOKEN that has no `issues: write` is a 403, and the
        step's `|| echo` turned that into "Issue not created: bookkeeping failed" — which is how
        the Instagram and Threads lanes went from launch to 16 Oct 2026 unable to report a
        failure anywhere but a run log nobody opens. The grant is checked at the workflow level
        or on the job, whichever the file uses."""
        for path, doc in self._workflows():
            top = (doc.get("permissions") or {}) if isinstance(doc.get("permissions"), dict) else {}
            for job_name, job in (doc.get("jobs") or {}).items():
                text = "\n".join(str(step.get("run") or "") for step in job.get("steps") or [])
                if "gh issue create" not in text and "gh issue comment" not in text:
                    continue
                job_perms = job.get("permissions") if isinstance(job.get("permissions"), dict) else None
                effective = job_perms if job_perms is not None else top
                with self.subTest(workflow=path.name, job=job_name):
                    self.assertEqual(effective.get("issues"), "write",
                                     "%s/%s files issues but has no `issues: write` — every "
                                     "failure would end in 'Issue not created'" % (path.name, job_name))

    def test_card_rendering_jobs_install_the_brand_font_through_the_one_script(self):
        """Inter is the brand face. Jobs that draw a card (tools/social_card.py) install it
        through tools/install_brand_fonts.sh — the apt-only line each job used to carry
        swallowed its own failure, and the Instagram job had no line at all."""
        drawers = ("instagram_autopost.yml", "facebook_autopost.yml",
                   "facebook_story_afternoon.yml", "telegram_autopost.yml")
        for name in drawers:
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertIn("tools/install_brand_fonts.sh", text)
                self.assertNotIn("apt-get install -y -qq fonts-inter", text,
                                 "the swallowed apt line is what the script replaces")

    def test_no_workflow_has_a_duplicate_mapping_key(self):
        """PyYAML silently keeps the last duplicate; GitHub rejects the whole file.

        16 Oct 2026: `instagram_autopost.yml` had two `env:` blocks on one step. Locally it
        parsed, every test passed, and on GitHub the workflow showed as a bare file path
        with no "Run workflow" button — a lane that could never be started, for days,
        while the owner set up tokens for it. This loader refuses what GitHub refuses.
        """
        class Dup(Exception):
            pass

        class Strict(yaml.SafeLoader):
            pass

        def construct(loader, node, deep=False):
            seen = set()
            for key_node, _ in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in seen:
                    raise Dup("duplicate key %r at line %d" % (key, key_node.start_mark.line + 1))
                seen.add(key)
            return yaml.SafeLoader.construct_mapping(loader, node, deep)

        Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct)
        for path in sorted(WORKFLOWS.glob("*.yml")):
            with self.subTest(workflow=path.name):
                try:
                    yaml.load(path.read_text(encoding="utf-8"), Loader=Strict)
                except Dup as exc:
                    self.fail("%s: %s — GitHub will refuse this file and hide the Run button" % (path.name, exc))

    def test_every_expression_in_every_workflow_is_one_github_can_evaluate(self):
        """`${{ … }}` inside ANY string value is evaluated by GitHub — comments included.

        16 Oct 2026, second cause of the invisible Instagram lane: a bash comment inside a
        `run:` block read "`${{ … }}` stays out of the command line". YAML saw a string,
        `bash -n` saw a comment, GitHub saw an expression with an unexpected symbol and
        refused the whole file. This walks every string in every workflow and checks each
        expression is built only from GitHub's named values, functions, literals and
        operators. (YAML `#` comments are stripped before GitHub parses, so they are not
        walked here — and `yaml.safe_load` drops them for us.)
        """
        import re
        named = {"github", "env", "vars", "job", "jobs", "steps", "runner", "secrets",
                 "strategy", "matrix", "needs", "inputs", "true", "false", "null", "infinity", "nan"}
        functions = {"contains", "startswith", "endswith", "format", "join", "tojson",
                     "fromjson", "hashfiles", "success", "always", "cancelled", "failure"}
        token = re.compile(r"""\s+|'(?:[^']|'')*'|-?\d+(?:\.\d+)?(?:e-?\d+)?|[A-Za-z_][\w-]*|&&|\|\||==|!=|<=|>=|\*|\.|\[|\]|\(|\)|,|!|<|>""")

        def check(expr):
            pos = 0
            prev = ""
            while pos < len(expr):
                m = token.match(expr, pos)
                if not m:
                    return "unexpected symbol %r" % expr[pos]
                t = m.group(0)
                pos = m.end()
                if t.strip() == "":
                    continue
                if re.match(r"[A-Za-z_]", t):
                    low = t.lower()
                    if prev == ".":
                        pass  # property name — anything goes
                    elif low in functions:
                        pass
                    elif low not in named:
                        return "unknown named value %r" % t
                prev = t
            return None

        def strings(node):
            if isinstance(node, str):
                yield node
            elif isinstance(node, dict):
                for value in node.values():
                    yield from strings(value)
            elif isinstance(node, list):
                for value in node:
                    yield from strings(value)

        for path, doc in self._workflows():
            for text in strings(doc):
                for m in re.finditer(r"\$\{\{(.*?)\}\}", text, re.S):
                    with self.subTest(workflow=path.name, expression=m.group(0)[:80]):
                        problem = check(m.group(1))
                        self.assertIsNone(
                            problem,
                            "%s: %s in %s — GitHub refuses the whole file and hides the Run button"
                            % (path.name, problem, m.group(0)[:80]),
                        )

    def test_every_lane_that_seals_a_token_is_given_the_vault_key(self):
        """Secrets reach a step only through `env:`. 16 Oct 2026: both Meta lanes called
        `token_vault.py seal`, printed "SOCIAL_TOKEN_KEY is not set" on every run, and the
        owner added the secret before anyone noticed no workflow ever passed it."""
        for path, doc in self._workflows():
            uses_vault = False
            for job in (doc.get("jobs") or {}).values():
                for step in job.get("steps") or []:
                    script = str(step.get("run") or "")
                    if "token_vault.py seal" in script or "token_vault.py open" in script:
                        uses_vault = True
            if not uses_vault:
                continue
            with self.subTest(workflow=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("SOCIAL_TOKEN_KEY: ${{ secrets.SOCIAL_TOKEN_KEY }}", text,
                              "%s runs token_vault.py but never maps the key from secrets" % path.name)

    def test_every_lane_that_generates_copy_installs_pillow(self):
        """scripts/generate_telegram_content.py imports tools/social_card.py, which imports
        PIL at module level — so every lane that runs it (or the Threads generator that
        imports it) needs pillow installed, whether or not it draws anything. Threads run #4,
        16 Oct 2026: `ModuleNotFoundError: No module named 'PIL'` on the first real post."""
        needs = ("generate_telegram_content.py", "generate_threads_content.py", "social_card.py")
        for path, doc in self._workflows():
            scripts = " ".join(str(step.get("run") or "")
                               for job in (doc.get("jobs") or {}).values()
                               for step in job.get("steps") or [])
            if not any(name in scripts for name in needs):
                continue
            with self.subTest(workflow=path.name):
                self.assertRegex(scripts.lower(), r"pip install[^\n]*pillow",
                                 "%s runs a copy generator but never installs pillow" % path.name)

    def test_runners_are_pinned_and_actions_run_on_node_24(self):
        """GitHub moves `ubuntu-latest` to Ubuntu 26 on 19 Oct 2026 and retires Node 20
        actions after that. A lane that installs ffmpeg and fonts is exactly what an OS jump
        breaks, so every job names its image; and every first-party action is on a major that
        runs on Node 24 (checked against each tag's action.yml `runs.using` on 16 Oct 2026)."""
        node20_majors = ("actions/checkout@v4", "actions/setup-python@v5", "actions/upload-artifact@v4",
                         "actions/upload-artifact@v5", "actions/download-artifact@v4",
                         "actions/download-artifact@v5", "actions/download-artifact@v6",
                         "actions/setup-node@v4", "actions/github-script@v7", "actions/cache@v4",
                         "actions/cache/save@v4", "actions/cache/restore@v4", "actions/setup-java@v4",
                         "cloudflare/wrangler-action@v3")
        for path, doc in self._workflows():
            with self.subTest(workflow=path.name):
                for job_name, job in (doc.get("jobs") or {}).items():
                    runs_on = job.get("runs-on")
                    if runs_on is not None:
                        self.assertNotIn("latest", str(runs_on),
                                         "%s job %s floats on %r" % (path.name, job_name, runs_on))
                    for step in job.get("steps") or []:
                        uses = str(step.get("uses") or "")
                        self.assertNotIn(uses.split(" ")[0], node20_majors,
                                         "%s step %r is on a Node 20 action major" % (path.name, uses))

    def test_every_run_block_is_valid_bash(self):
        """`bash -n` on each script: YAML cannot tell you a quote is unbalanced."""
        import subprocess
        import tempfile
        for path, doc in self._workflows():
            for job_name, job in (doc.get("jobs") or {}).items():
                for step in job.get("steps") or []:
                    script = step.get("run")
                    if not script:
                        continue
                    with self.subTest(workflow=path.name, job=job_name, step=step.get("name")):
                        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False,
                                                        encoding="utf-8") as handle:
                            handle.write(script)
                            name = handle.name
                        try:
                            check = subprocess.run(["bash", "-n", name], capture_output=True, text=True)
                        finally:
                            os.unlink(name)
                        self.assertEqual(check.returncode, 0,
                                         "%s / %s: run block is not valid bash\n%s"
                                         % (path.name, step.get("name"), check.stderr.strip()[:400]))

    def test_no_git_add_names_two_paths_at_once(self):
        """`git add a b c` adds NOTHING when one path matches no file ("fatal: pathspec did
        not match") — and `2>/dev/null || true` hides it. 22 Oct 2026: that one line kept
        every brain decision off main since 17 Oct (brain/answers exists on Mondays only)
        and lost the TikTok drafts, the Threads hand-over record and an Instagram Reel from
        the Shorts lane (logs/telegram_owner.json never existed). One path per `git add`,
        each behind `[ -e "$path" ]`."""
        import re
        import shlex
        for path, doc in self._workflows():
            for job_name, job in (doc.get("jobs") or {}).items():
                for step in job.get("steps") or []:
                    script = step.get("run") or ""
                    for line in script.splitlines():
                        line = line.split("#", 1)[0].strip()
                        if "git add" not in line:
                            continue
                        for cmd in re.split(r"&&|\|\||;", line):
                            cmd = cmd.strip()
                            if not cmd.startswith("git add"):
                                continue
                            try:
                                words = shlex.split(cmd)
                            except ValueError:
                                words = cmd.split()
                            paths = [w for w in words[2:] if not w.startswith("-") and not re.match(r"^\d*[<>]", w)
                                     and not (words[words.index(w) - 1].endswith(">") or words[words.index(w) - 1] in ("2>", ">"))]
                            with self.subTest(workflow=path.name, job=job_name, step=step.get("name"), line=line):
                                self.assertLessEqual(len(paths), 1,
                                                     "%s / %s: `%s` names %d paths in one `git add` — one missing path voids them all; loop with [ -e \"$path\" ]"
                                                     % (path.name, step.get("name"), cmd, len(paths)))

    def test_no_dispatch_input_is_interpolated_into_a_shell_command(self):
        """`${{ inputs.x }}` inside `run:` is code execution, with secrets in scope.

        A manual input must be exported through the step's `env:` and referenced
        as a quoted shell variable. GitHub substitutes the expression before bash
        ever sees it, so a value containing `"` or `$(…)` breaks out.
        """
        for path, doc in self._workflows():
            for job_name, job in (doc.get("jobs") or {}).items():
                for step in job.get("steps") or []:
                    script = str(step.get("run") or "")
                    if not script:
                        continue
                    with self.subTest(workflow=path.name, job=job_name, step=step.get("name")):
                        for match in INPUT_REF.finditer(script):
                            self.fail(
                                "%s / %s interpolates %s into a shell command. Pass it through the "
                                "step's env: and use \"$VARIABLE\" instead — that is what "
                                "facebook_autopost.yml does, and the class of bug that made the "
                                "original one unsafe to hand a sentence with an apostrophe."
                                % (path.name, step.get("name"), match.group(0))
                            )

    def test_no_secret_shaped_default_in_automation_tools(self):
        """A credential with a literal fallback lives in git forever.

        tools/fb_publish.py used to default META_APP_SECRET, so the app secret
        was in every clone and in history. Removing the line is not enough — the
        secret has to be rotated (FACEBOOK_AUTOMATION.md) — but a default coming
        back must fail CI rather than be found by an audit.
        """
        for rel in ("tools/fb_publish.py", "tools/ig_publish.py", "tools/yt_publish.py",
                    "tools/fb_preflight.py", "tools/telegram_preflight.py",
                    "scripts/post_facebook.py", "scripts/post_telegram.py"):
            path = ROOT / rel
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for name, value in ENV_DEFAULT.findall(text):
                with self.subTest(file=rel, name=name):
                    self.assertFalse(
                        SECRETISH.search(name) and not re.search(r"(?i)example|placeholder|REPLACE", value),
                        "%s: %s defaults to %r. Secrets come from the environment or the run stops."
                        % (rel, name, value[:12] + "…"),
                    )

    def test_every_flag_a_workflow_passes_exists_in_the_script(self):
        """An unknown flag is argparse usage text on stderr and no post.

        The Instagram workflow once nearly shipped `--image-urls` against a
        script that only had `--carousel`; had that been the flag for a daily
        post, the run would have been red for a week before anyone read it.
        """
        for path, doc in self._workflows():
            for job in (doc.get("jobs") or {}).values():
                for step in job.get("steps") or []:
                    script = str(step.get("run") or "")
                    for match in re.finditer(r"python3?\s+(\S+\.py)([^\n]*)", script):
                        rel, args = match.group(1), match.group(2)
                        rel = rel.strip("'\"")
                        target = ROOT / rel
                        if not target.exists() or "--help" in args or "-m " in rel:
                            continue
                        declared = set(FLAG.findall(target.read_text(encoding="utf-8")))
                        used = {flag for flag in FLAG.findall(args) if flag not in ("--force", "--quiet")}
                        for flag in sorted(used & {"--text", "--photo-url", "--photo-file", "--video-url",
                                                   "--dry-run", "--force", "--no-guard", "--refresh-token",
                                                   "--title", "--description", "--date", "--print",
                                                   "--image-url", "--image-urls", "--carousel", "--caption",
                                                   "--reel", "--photo", "--cover"}):
                            with self.subTest(workflow=path.name, script=rel, flag=flag):
                                self.assertIn(flag, declared,
                                              "%s passes %s to %s, which does not declare it"
                                              % (path.name, flag, rel))


@unittest.skipIf(yaml is None, "PyYAML is required for the workflow contract tests")
class FacebookAutopostTests(unittest.TestCase):
    """The owner-facing invariants of the daily Facebook post.

    Written the day the workflow stopped being a button: it had `dispatch` and
    nothing else, and `gh run list` returned zero rows for it — an automation
    that has never run is a feature request with a YAML file attached.
    """

    @classmethod
    def setUpClass(cls):
        cls.path = WORKFLOWS / "facebook_autopost.yml"
        cls.doc = yaml.safe_load(cls.path.read_text(encoding="utf-8"))
        cls.on = cls.doc[True] if True in cls.doc else cls.doc["on"]
        cls.job = cls.doc["jobs"]["publish"]
        cls.steps = cls.job["steps"]
        cls.names = [s.get("name") for s in cls.steps]
        cls.by_name = {s.get("name"): s for s in cls.steps}

    def blob(self, name):
        step = self.by_name[name]
        return "\n".join([str(step.get("run", "")), str(step.get("if", "")), str(step.get("env", ""))])

    def test_it_is_on_a_schedule_not_only_a_button(self):
        crons = [entry["cron"] for entry in self.on.get("schedule") or []]
        self.assertEqual(crons, ["30 8 * * *"], "09:30 in Lagos; the daily post must not be manual")

    def test_it_does_not_collide_with_the_telegram_minute(self):
        """Same minute, same brand: the two runs would race for the same runner
        and publish two near-identical posts a minute apart."""
        tg = yaml.safe_load((WORKFLOWS / "telegram_autopost.yml").read_text(encoding="utf-8"))
        tg_on = tg[True] if True in tg else tg["on"]
        tg_crons = [e["cron"] for e in tg_on.get("schedule") or []]
        mine = [e["cron"] for e in self.on.get("schedule") or []]
        for other in tg_crons:
            for here in mine:
                self.assertNotEqual(other.split()[0], here.split()[0],
                                    "Telegram runs at %r; pick a different minute" % other)

    def test_credentials_are_checked_before_anything_is_generated_or_posted(self):
        self.assertLess(self.names.index("Preflight — can this token reach the Page?"),
                        self.names.index("Generate today's copy"))
        self.assertLess(self.names.index("Preflight — can this token reach the Page?"),
                        self.names.index("Daily post"))

    def test_the_preflight_runs_before_the_dependency_install(self):
        """It is stdlib-only so a dead token costs seconds, not a pip install."""
        self.assertLess(self.names.index("Preflight — can this token reach the Page?"),
                        self.names.index("Install dependencies"))

    def test_the_copy_is_generated_before_it_is_posted(self):
        self.assertLess(self.names.index("Generate today's copy"), self.names.index("Daily post"))

    def test_a_dry_run_publishes_nothing(self):
        dispatch = (self.on.get("workflow_dispatch") or {}).get("inputs") or {}
        self.assertIn("dry_run", dispatch,
                      "without a dry-run switch, the only way to test credentials is to publish")
        for name in ("Daily post", "Manual post (text / photo / video / reel)"):
            with self.subTest(step=name):
                self.assertIn("!inputs.dry_run", str(self.by_name[name].get("if")))

    def test_the_daily_run_cannot_publish_twice_on_one_day(self):
        """`--force` is opt-in, so the schedule path must not carry it."""
        daily = self.blob("Daily post")
        env = self.by_name["Daily post"].get("env") or {}
        self.assertEqual(env.get("IN_FORCE"), "${{ inputs.force }}",
                         "force must come from the dispatch input, through env, and nothing else")
        self.assertIn('[ "$IN_FORCE" = "true" ] && FORCE="--force"', daily,
                      "the flag must be conditional")
        self.assertIn("post_facebook.py $FORCE", daily, "and the only way the flag reaches the script")

    def test_manual_posts_bypass_the_guard_because_a_person_asked_for_it(self):
        self.assertIn("--force", self.blob("Manual post (text / photo / video / reel)"))

    def test_the_reel_ledger_is_written_after_every_step_that_can_publish_a_reel(self):
        """Run #9 (15 Oct 2026, mode: reel): the ledger step sat above the manual
        post step, ran first because `inputs.mode == 'reel'`, found no
        /tmp/fb_reel_post.log and killed the job before the Reel was attempted."""
        for writer in ("Reels — publish", "Manual post (text / photo / video / reel)"):
            for reader in ("Reels — record it in the ledger", "Reels — commit the ledger"):
                with self.subTest(writer=writer, reader=reader):
                    self.assertLess(self.names.index(writer), self.names.index(reader))
        record = self.blob("Reels — record it in the ledger")
        self.assertIn("[ ! -f /tmp/fb_reel_post.log ]", record,
                      "a missing publish log is 'nothing to record', never a red run")

    def test_the_graph_api_version_is_current_and_comes_from_one_constant(self):
        """Meta sunsets a version roughly every two years: v21.0 goes on 21 Jan
        2027, v26.0 has been current since 29 Jul 2026. So the number lives in one
        named constant per surface, is overridable from a repository variable, and
        no call builds its URL from a literal version nobody will find later."""
        text = self.path.read_text(encoding="utf-8")
        # The floor lives in the workflow's `||` fallback, which is the value a
        # run gets until the owner sets META_GRAPH_VERSION in repository variables.
        pinned = re.search(r"META_GRAPH_VERSION:.*\|\|\s*'v(\d+)\.0'", text)
        self.assertIsNotNone(pinned, "the workflow should carry a default version in its env block")
        self.assertGreaterEqual(int(pinned.group(1)), 24,
                                "v%s is at or past Meta's sunset horizon" % pinned.group(1))
        self.assertIn("vars.META_GRAPH_VERSION", text,
                      "the version must be movable from repository variables, not only by a commit")
        for rel in ("tools/fb_publish.py", "tools/fb_preflight.py", "tools/ig_publish.py",
                    "tools/ig_connect.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            code = "\n".join(line for line in src.splitlines() if not line.strip().startswith("#"))
            literals = re.findall(r"graph\.facebook\.com/v\d+\.\d+|rupload\.facebook\.com/\w+/v\d+\.\d+", code)
            with self.subTest(file=rel):
                self.assertFalse(
                    literals,
                    "%s hard-codes the API version in %s — build the URL from API_VERSION so a "
                    "Meta sunset is one edit, not a hunt" % (rel, literals[:2]),
                )

    def test_a_failed_run_leaves_a_visible_issue(self):
        step = self.by_name["Open a visible issue if the run failed"]
        self.assertEqual(step.get("if"), "failure()")
        self.assertIn("gh issue create", step["run"])
        self.assertIn("facebook-automation", step["run"])
        self.assertIn("GH_TOKEN", str(step.get("env")))
        self.assertEqual((self.doc.get("permissions") or {}).get("issues"), "write")

    def test_the_issue_names_the_error_codes_that_actually_happen(self):
        """Triage from the issue alone — the run log is the thing people do not
        have open at 09:30 on a Tuesday."""
        body = self.blob("Open a visible issue if the run failed")
        for marker in ("190", "pages_manage_posts", "FB_PAGE_ACCESS_TOKEN", "META_GRAPH_VERSION"):
            with self.subTest(marker=marker):
                self.assertIn(marker, body)

    def test_a_red_tick_and_a_skipped_day_are_not_the_same_thing(self):
        """The summary step is `always()` and the poster's skip is exit 0, so a
        duplicate-guard skip does not open an issue."""
        self.assertEqual(self.by_name["Record what this run did"].get("if"), "always()")
        poster = (ROOT / "scripts" / "post_facebook.py").read_text(encoding="utf-8")
        self.assertIn("return 0", poster.split("already has a post today")[1][:400],
                      "skipping a day that is already posted is success, not failure")

    def test_the_summary_never_prints_a_token(self):
        step = self.blob("Record what this run did")
        self.assertIn("FB_PAGE_ACCESS_TOKEN", step, "it should report whether the secret is set")
        self.assertNotIn('echo "$FB_PAGE_ACCESS_TOKEN"', step, "report presence, never the value")
        self.assertNotIn('echo "${FB_PAGE_ACCESS_TOKEN}"', step)

    def test_two_runs_cannot_interleave(self):
        group = (self.doc.get("concurrency") or {}).get("group")
        self.assertEqual(group, "facebook-autopost")
        self.assertIs((self.doc.get("concurrency") or {}).get("cancel-in-progress"), False,
                      "cancelling mid-publish leaves a post on the Page and a red run")

    def test_every_step_that_runs_gh_declares_a_token(self):
        for step in self.steps:
            if "gh " in str(step.get("run", "")):
                with self.subTest(step=step.get("name")):
                    self.assertIn("GH_TOKEN", str(step.get("env", "")))

    def test_the_publisher_is_documented_where_the_owner_would_look(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "FACEBOOK_AUTOMATION.md").exists(),
                        "an automation nobody can configure is not finished")
        self.assertIn("FACEBOOK_AUTOMATION.md", readme, "the repo map must lead to it")


class FacebookReelsContractTests(unittest.TestCase):
    """The Reels lane's wiring, asserted where YAML mistakes actually happen.

    `test_post_facebook_reels.py` proves the protocol speaks Graph API correctly;
    this proves the *job* is buildable around it: that the cheap decision runs
    before anything expensive, that nothing renders while the lane is only
    probing, that a published reel is recorded somewhere the next run can read,
    and that `contents: write` — which this job did not need before the reel
    ledger — is spent on exactly one path.

    The ordering rules matter more here than anywhere else in the repo: a job that
    renders for two minutes and *then* discovers it should have skipped is a job
    that burns the month's free runner minutes on skips.
    """

    @classmethod
    def setUpClass(cls):
        cls.path = WORKFLOWS / "facebook_autopost.yml"
        cls.text = cls.path.read_text(encoding="utf-8")
        cls.doc = yaml.safe_load(cls.text)
        cls.job = cls.doc["jobs"]["publish"]
        cls.steps = cls.job["steps"]
        cls.names = [st.get("name") for st in cls.steps]
        cls.by_name = {st.get("name"): st for st in cls.steps}

    def cond(self, name):
        return str(self.by_name[name].get("if", ""))

    def blob(self, name):
        step = self.by_name[name]
        return "\n".join([str(step.get("run", "")), str(step.get("if", "")),
                           str(step.get("env", ""))])

    def index(self, name):
        self.assertIn(name, self.names, "the Reels lane lost a step: %s" % name)
        return self.names.index(name)

    def test_the_reel_steps_run_in_the_only_order_that_works(self):
        order = ["Reels — decide (cheap; renders nothing)",
                 "Reels — install the renderer",
                 "Reels — guard against a recycled frame",
                 "Reels — render",
                 "Reels — publish",
                 "Reels — record it in the ledger",
                 "Reels — commit the ledger"]
        indices = [self.index(name) for name in order]
        self.assertEqual(indices, sorted(indices),
                         "each step consumes the previous one's output; a reorder is a silent no-op")

    def test_the_installer_waits_for_the_decision(self):
        """`apt-get install ffmpeg` + moviepy is ~40 s and only ever needed for a
        render. Gating it on the decision — not on the cron — is why a probe-only
        day and an `off` day stay cheap."""
        install = self.by_name["Reels — install the renderer"]
        self.assertIn("steps.reel_plan.outputs.reel_today", str(install.get("if")))
        self.assertLess(self.index("Reels — decide (cheap; renders nothing)"),
                        self.index("Reels — install the renderer"),
                        "an `if:` that reads a step output cannot precede that step — "
                        "it would evaluate to empty and the renderer would never install")

    def test_probe_mode_never_renders_or_publishes(self):
        probe = self.cond("Reels — probe the grant (nothing is published)")
        self.assertIn("steps.reel_plan.outputs.mode == 'probe'", probe)
        guard = self.cond("Reels — guard against a recycled frame")
        self.assertIn("steps.reel_plan.outputs.mode == 'on'", guard)
        self.assertNotIn("rupload", self.by_name["Reels — probe the grant (nothing is published)"]["run"])
        self.assertIn("--probe-reels", self.by_name["Reels — probe the grant (nothing is published)"]["run"])

    def test_the_publish_goes_through_the_poster_not_the_raw_tool(self):
        """`scripts/post_facebook.py` owns the guards. A workflow that calls
        `tools/fb_publish.py --reel` directly publishes without asking the Page
        whether today's frame already went out."""
        run = self.by_name["Reels — publish"]["run"]
        self.assertIn("scripts/post_facebook.py --reel=", run)
        self.assertNotIn("tools/fb_publish.py --reel ", run)

    def test_a_published_reel_is_recorded_in_a_file_the_next_run_can_read(self):
        """`video_reels` cannot be read back, so the ledger is the only memory this
        lane has — and a ledger in a gitignored directory is a ledger nobody reads.
        (assets/ is ignored in this repo; that is not a hypothetical.)"""
        record = self.blob("Reels — record it in the ledger")
        self.assertIn("--ledger logs/facebook_reels.json", record)
        self.assertIn("tools/youtube_ledger.py", record,
                      "one ledger implementation, two files — a fork drifts")
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("logs/", [line.strip() for line in gitignore.splitlines()],
                         "the ledger must be committable, or the 30-day window is a myth")

    def test_the_window_is_the_frame_law_not_an_arbitrary_number(self):
        """docs/GROWTH_ENGINE.md §4: never reuse a frame that has been live in the
        last 30 days. The number in the YAML is that law, not a guess."""
        self.assertIn("--window-days 30", self.blob("Reels — guard against a recycled frame"))

    def test_the_guard_can_be_overridden_only_by_a_human(self):
        step = self.by_name["Reels — guard against a recycled frame"]
        # Read the parsed mapping, not the YAML text: `blob()` stringifies a dict,
        # and asserting against that representation is how an assertion starts
        # passing for the wrong reason.
        self.assertEqual((step.get("env") or {}).get("IN_FORCE"), "${{ inputs.force }}",
                         "force must arrive from the dispatch input through env:, never "
                         "interpolated into the shell line")
        self.assertIn('"$IN_FORCE" = "true"', str(step["run"]))
        self.assertIn("skip=yes", str(step["run"]),
                      "a skip must be a step output, so the render step can stand down")

    def test_the_mode_is_a_variable_whose_default_publishes_nothing(self):
        env = self.job.get("env") or self.doc.get("env") or {}
        self.assertEqual(env.get("REELS_MODE"), "${{ vars.FB_REELS || 'probe' }}",
                         "on by default would mean the first-ever reel is published by an "
                         "unattended run, on a spelling of upload_phase nobody has probed yet")
        script = (ROOT / "scripts" / "facebook_reel_daily.py").read_text(encoding="utf-8")
        self.assertIn('"probe"', script, "the script's default must match the workflow's")

    def test_contents_write_is_spent_on_exactly_one_path(self):
        self.assertEqual((self.doc.get("permissions") or {}).get("contents"), "write")
        added = re.findall(r"git add (\S+)", self.text)
        # Two ledgers since 16 Oct 2026: the Instagram Reel rides this lane (same render, same
        # Page token, Meta's resumable upload) and records itself in Instagram's ledger.
        # Three since 29 Oct 2026: the footage ledger (which clips/photos were shown) rides every
        # rendering lane so the same clip is not behind every video.
        self.assertEqual(sorted(set(added)), ["logs/facebook_reels.json", "logs/footage_used.json", "logs/instagram_sent.json"],
                         "write access that touches anything else is a bigger question than a ledger")

    def test_the_instagram_reel_follows_facebooks_bookkeeping_and_the_readiness_probe(self):
        """The Instagram Reel is published from this lane by resumable upload (no host, ₦0).
        Three things keep it honest: it is gated on a reads-only probe that runs every day,
        it sits *below* the Facebook ledger commit (a red step above it would skip that record
        and the next run would publish the Facebook Reel twice), and a failure is a failure."""
        names = [step.get("name", "") for step in self.job["steps"]]
        probe = next(i for i, n in enumerate(names) if n.startswith("Instagram Reels — is the Page token ready"))
        ig_reel = next(i for i, n in enumerate(names) if n.startswith("Instagram Reel — the same render"))
        fb_ledger = next(i for i, n in enumerate(names) if n == "Reels — commit the ledger")
        fb_post = next(i for i, n in enumerate(names) if n == "Daily post")
        self.assertLess(probe, fb_post, "readiness is known before anything is posted")
        self.assertLess(fb_ledger, ig_reel, "Facebook's ledger is committed before Instagram can fail the run")
        probe_step = self.job["steps"][probe]
        self.assertTrue(probe_step.get("continue-on-error"), "a probe that cannot run must not cost the post")
        self.assertIn("--probe-reels", probe_step["run"])
        self.assertIn("IG_API_PATH=facebook-login", probe_step["run"])
        # Two doors since 16 Oct 2026: the Page token, or — when the Page↔Instagram link is
        # refused — the Instagram lane's own token. A merge step picks; the upload reads it.
        probe2 = next(i for i, n in enumerate(names) if n.startswith("Instagram Reels — second door"))
        door = next(i for i, n in enumerate(names) if n == "Instagram Reels — which door")
        self.assertLess(probe, probe2)
        self.assertLess(probe2, door)
        self.assertLess(door, fb_post, "the door is known before anything is posted")
        probe2_step = self.job["steps"][probe2]
        self.assertTrue(probe2_step.get("continue-on-error"))
        self.assertIn("steps.ig_reels_probe.outputs.ready != 'yes'", probe2_step["if"],
                      "the second door is only tried when the first is shut")
        self.assertIn("IG_API_PATH=instagram-login", probe2_step["run"])
        self.assertIn("token_vault.py open --name IG_ACCESS_TOKEN", probe2_step["run"])
        self.assertIn("umask 077", probe2_step["run"], "the token lands as a private file")
        self.assertIn("cryptography", self.blob("Install dependencies"), "token_vault needs it")
        reel_step = self.job["steps"][ig_reel]
        self.assertIn("steps.ig_door.outputs.ready == 'yes'", reel_step["if"])
        self.assertFalse(reel_step.get("continue-on-error"), "a failed Instagram Reel is a red run and an issue")
        self.assertIn("--video-file", reel_step["run"])
        self.assertIn('IG_API_PATH="$API_PATH"', reel_step["run"])
        self.assertIn("instagram-login|hosted)", reel_step["run"],
                      "both Instagram-Login doors use the lane's own token on graph.instagram.com")
        self.assertIn("/tmp/ig_login_token", reel_step["run"])
        self.assertIn("--window-days 30", reel_step["run"])
        self.assertNotIn("site/social", reel_step["run"], "no render is committed for a Reel")
        self.assertNotIn("video_url", reel_step["run"], "nothing hard-codes a URL into the container call")
        self.assertIn("IG_REELS", self.text)
        self.assertIn("ig_reel_post.log", self.blob("Open a visible issue if the run failed"))
        self.assertIn("ig_reel_post.log", self.blob("Record what this run did"))
        story = next(i for i, n in enumerate(names) if n.startswith("Instagram Story — the Reel in the tray"))
        self.assertLess(ig_reel, story)
        story_step = self.job["steps"][story]
        self.assertTrue(story_step.get("continue-on-error"), "a Story is a window, not the record")
        self.assertIn("steps.ig_reel.outcome == 'success'", story_step["if"])
        self.assertIn("--video-story", story_step["run"])

    def test_the_third_door_hosts_the_reel_for_meta_when_neither_token_door_is_open(self):
        """18 Oct 2026: Facebook refused the Page link a second time (no date) and Meta refuses
        a resumable session on the Instagram-Login token — so the lane must not depend on either.
        The `hosted` door: tools/media_host.py puts the render in the worker's KV with the same
        two Cloudflare secrets the dashboard feed uses, Meta fetches it by `video_url`, the
        Story reuses the URL, then the keys are removed. Door order is kept: it is the third."""
        names = [s.get("name") for s in self.job["steps"]]
        probe2 = self.job["steps"][names.index("Instagram Reels — second door, the Instagram-Login token (one unpublished container)")]
        door = self.job["steps"][names.index("Instagram Reels — which door")]
        reel = self.job["steps"][names.index("Instagram Reel — the same render (resumable upload, or by URL through the third door)")]
        story = self.job["steps"][names.index("Instagram Story — the Reel in the tray too")]
        self.assertIn("IG_REELS_HOSTED=", probe2["run"])
        self.assertIn('echo "hosted=${HOSTED:-no}" >> "$GITHUB_OUTPUT"', probe2["run"])
        self.assertIn("steps.ig_reels_probe2.outputs.hosted", str(door["env"]))
        self.assertIn("secrets.CLOUDFLARE_API_TOKEN != ''", str(door["env"]),
                      "the door is only offered when the hosting half can run")
        run = door["run"]
        self.assertLess(run.index("DOOR=facebook-login"), run.index("DOOR=instagram-login"))
        self.assertLess(run.index("DOOR=instagram-login"), run.index("DOOR=hosted"),
                        "the Page token and the resumable session stay ahead of hosting")
        self.assertIn('[ "${P2_HOSTED:-no}" = "yes" ] && [ -n "${P2_ID:-}" ] && [ "${HAVE_CF:-false}" = "true" ]', run)
        for step in (reel, story):
            env = step.get("env") or {}
            self.assertEqual(env.get("CLOUDFLARE_API_TOKEN"), "${{ secrets.CLOUDFLARE_API_TOKEN }}", step["name"])
            self.assertEqual(env.get("CLOUDFLARE_ACCOUNT_ID"), "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}", step["name"])
        self.assertIn('python3 tools/media_host.py put "$FILE" --ttl-hours 48 --verify-seconds 180', reel["run"])
        self.assertIn('--video-url "$MEDIA_URL"', reel["run"])
        self.assertIn("--wait-url", reel["run"], "KV propagates in under a minute; the publisher waits for the URL")
        self.assertIn("/tmp/ig_media.env", reel["run"])
        self.assertIn("IG_CAUSE=media-host", reel["run"], "a hosting failure is named, not a mystery")
        self.assertIn('--story-video-url "$MEDIA_URL"', story["run"])
        self.assertIn('python3 tools/media_host.py delete "$MEDIA_NAME"', story["run"])
        self.assertLess(story["run"].index("--story-video-url"), story["run"].index("media_host.py delete"),
                        "the file is removed only after both the Reel and the Story have it")
        self.assertNotIn("secrets.CLOUDFLARE_API_TOKEN", str(reel["run"]) + str(story["run"]),
                         "the secret arrives as env, never interpolated into a script")

    def test_the_reel_logs_reach_the_summary_and_the_issue(self):
        summary = self.blob("Record what this run did")
        for log in ("fb_reel_plan.log", "fb_reel_probe.log", "fb_reel_render.log", "fb_reel_post.log"):
            with self.subTest(log=log):
                self.assertIn(log, summary)
        issue = self.blob("Open a visible issue if the run failed")
        self.assertIn("fb_reel_post.log", issue)
        self.assertIn("--reel-finish", issue,
                      "an accepted-but-unpublished reel is recoverable; the issue must say how")

    def test_the_manual_reel_mode_exists_and_bypasses_the_day_rule(self):
        on = self.doc[True] if True in self.doc else self.doc["on"]
        options = on["workflow_dispatch"]["inputs"]["mode"]["options"]
        self.assertIn("reel", options)
        blob = self.blob("Manual post (text / photo / video / reel)")
        self.assertIn("--render --mode on", blob, "a person asked for one today, weekday rule aside")
        self.assertIn("--force", blob, "and the 30-day window is theirs to override, not ours to enforce")

    def test_the_job_has_room_for_a_render(self):
        self.assertGreaterEqual(self.job.get("timeout-minutes", 0), 25,
                                "a timeout after a publish is red *and* live — the worst outcome "
                                "an unattended lane can have")


class StepReferenceTests(unittest.TestCase):
    """`steps.<id>` may only be read from a step that runs *after* the one that
    wrote it, and only for an id that exists.

    This rule exists because the Facebook Reels installer step was first written
    *above* the decision step whose output its `if:` tested. The YAML parsed, the
    `if:` was simply false forever, and the only symptom would have been "the
    renderer was never installed" on the days it was needed. GitHub does not warn
    about a reference to a step that has not run yet — it hands you an empty
    string, which is exactly how a pipeline ends up quietly doing nothing.
    """

    def test_every_reference_resolves_to_an_earlier_declared_step(self):
        reference = re.compile(r"steps\.([A-Za-z0-9_-]+)\.")
        for path in sorted(WORKFLOWS.glob("*.yml")):
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            jobs = (doc or {}).get("jobs") or {}
            for job_name, job in jobs.items():
                steps = job.get("steps") or []
                ids = [step.get("id") for step in steps]
                position = {sid: index for index, sid in enumerate(ids) if sid}
                for index, step in enumerate(steps):
                    text = "\n".join([str(step.get("if", "")), str(step.get("env", "")),
                                      str(step.get("run", "")), str(step.get("with", ""))])
                    for target in reference.findall(text):
                        with self.subTest(workflow=path.name, job=job_name,
                                         step=step.get("name"), refers_to=target):
                            self.assertIn(target, position,
                                          "`steps.%s.…` names a step with no id: %s" % (target, path.name))
                            self.assertLess(position[target], index,
                                            "`steps.%s` is read by %r, which runs at index %d — "
                                            "the writer is at index %d, so this evaluates to empty"
                                            % (target, step.get("name"), index, position[target]))
