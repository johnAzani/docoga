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

    def test_it_still_runs_on_the_tuesday_friday_schedule(self):
        crons = [entry["cron"] for entry in (self.doc[True] if True in self.doc else self.doc["on"])["schedule"]]
        self.assertEqual(crons, ["0 17 * * 2,5"], "the twice-weekly slot must not drift")

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
                self.assertEqual(self.by_name[name].get("if"), "steps.guard.outputs.skip != 'yes'")

    def test_the_guard_treats_force_true_as_clear_to_publish(self):
        """Regression: the first draft exited 3 (the duplicate code) when force
        was requested, so forcing a re-publish failed the run instead."""
        guard = self.blob("Duplicate guard (publish ledger)")
        self.assertIn('"$FORCE" = "true"', guard)
        self.assertNotIn('"$FORCE" != "true"', guard)

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


if __name__ == "__main__":
    unittest.main()
