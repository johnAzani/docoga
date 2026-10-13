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
        self.assertEqual(added, ["logs/facebook_reels.json"],
                         "write access that touches anything else is a bigger question than a ledger")

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
