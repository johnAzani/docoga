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
import sys
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
