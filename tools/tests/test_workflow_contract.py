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
        for name in ("Daily post", "Manual post (text / photo / video)"):
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
        self.assertIn("--force", self.blob("Manual post (text / photo / video)"))

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
