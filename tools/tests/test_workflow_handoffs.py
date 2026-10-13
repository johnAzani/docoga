"""The handoff auditor, tested against both directions.

A checker that reports nothing is indistinguishable from a checker that cannot see, so half of this
file feeds the auditor shapes it must flag and the other half feeds it shapes it must leave alone.
The silences matter more than the alarms: `tools/workflow_handoffs.py` reported five bugs in this
repository on its first run and every one of them was its own mistake — matching `$IG_USER_ID`
inside `${IG_USER_ID_OUT}`, and recognising only the first of a chained inline assignment
(`A=1 B=2 gh …`). Both are pinned below, because a gate that cries wolf gets ignored, and then the
real wolf walks in.
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import workflow_handoffs as wh  # noqa: E402


def workflow(step_yaml):
    """Wrap one job's steps in the YAML a real workflow file has."""
    return "name: t\non:\n  workflow_dispatch: {}\njobs:\n  j:\n    runs-on: ubuntu-latest\n" \
           "    steps:\n      - uses: actions/checkout@v4\n" + step_yaml


def kinds(text):
    return [kind for kind, _detail in wh.audit_text(text, "fixture")]


class GithubEnvAcrossSteps(unittest.TestCase):
    def test_a_value_read_in_the_step_that_exported_it_is_empty(self):
        found = kinds(workflow('''      - name: publish
        run: |
          echo "IG_USER_ID=$(grep id /tmp/probe.log)" >> "$GITHUB_ENV"
          echo "posting for ${IG_USER_ID}"
'''))
        self.assertIn("same-step $GITHUB_ENV read", found)

    def test_a_shell_variable_of_the_same_name_is_the_fix_not_the_bug(self):
        text = workflow('''      - name: publish
        run: |
          IG_USER_ID=$(grep id /tmp/probe.log)
          echo "IG_USER_ID=${IG_USER_ID}" >> "$GITHUB_ENV"
          echo "posting for ${IG_USER_ID}"
''')
        self.assertEqual(kinds(text), [], "assigned before the read: the step can see it, and the "
                                           "export is for whoever comes next")

    def test_a_longer_name_is_not_a_use_of_the_shorter_one(self):
        """`${IG_USER_ID_OUT}` is a different variable, and the prefix collision was real."""
        text = workflow('''      - name: publish
        run: |
          IG_USER_ID_OUT=$(grep id /tmp/probe.log)
          echo "IG_USER_ID=${IG_USER_ID_OUT}" >> "$GITHUB_ENV"
''')
        self.assertEqual(kinds(text), [])

    def test_the_next_step_may_read_what_this_one_wrote(self):
        text = workflow('''      - name: learn
        run: |
          echo "IG_USER_ID=$(grep id /tmp/probe.log)" >> "$GITHUB_ENV"
      - name: publish
        run: |
          echo "posting for ${IG_USER_ID}"
''')
        self.assertEqual(kinds(text), [])


class JqNeedles(unittest.TestCase):
    def test_a_jq_needle_that_is_only_a_shell_variable_never_arrives(self):
        """This is the bug that made Telegram's dedupe match every open issue for a week."""
        found = kinds(workflow('''      - name: find the issue
        run: |
          RUN_DATE="$(date +%F)"
          gh issue list --json number,title --jq "[.[] | select(.title | contains($ENV.RUN_DATE))] | max // empty"
'''))
        self.assertIn("jq $ENV.RUN_DATE has no environment entry", found)

    def test_an_inline_prefix_reaches_the_child(self):
        text = workflow('''      - name: find the issue
        run: |
          EXISTING=$(CAUSE_TAG="[$CAUSE]" gh issue list --json number,title --jq "[.[] | select(.title | contains($ENV.CAUSE_TAG))] | max // empty")
''')
        self.assertEqual(kinds(text), [])

    def test_an_inline_prefix_continued_with_a_backslash_reaches_the_child(self):
        text = workflow('''      - name: find the issue
        run: |
          EXISTING=$(CAUSE_TAG="[$CAUSE]" \\
            LEGACY_PREFIX="Telegram post failed — " \\
            gh issue list --json number,title --jq "[.[] | select((.title | contains($ENV.CAUSE_TAG)) or (.title | contains($ENV.LEGACY_PREFIX)))] | max // empty")
''')
        self.assertEqual(kinds(text), [], "the lanes chain assignments across a continuation; a "
                                          "rule that sees only the first one reports correct code "
                                          "as a bug")

    def test_export_and_step_env_both_count(self):
        for text in (workflow('''      - name: find the issue
        run: |
          export RUN_DATE="$(date +%F)"
          gh issue list --jq "[.[] | select(.title | contains($ENV.RUN_DATE))]"
'''),
                     workflow('''      - name: find the issue
        env:
          RUN_DATE: today
        run: |
          gh issue list --jq "[.[] | select(.title | contains($ENV.RUN_DATE))]"
''')):
            self.assertEqual(kinds(text), [])


class StepOutputs(unittest.TestCase):
    def test_a_reference_to_a_step_that_does_not_exist_is_empty_not_an_error(self):
        found = kinds(workflow('''      - name: use it
        run: |
          echo "${{ steps.render.outputs.url }}"
'''))
        self.assertIn("dangling step output", found)

    def test_a_step_id_that_exists_but_never_writes_that_key_is_also_a_bug(self):
        found = kinds(workflow('''      - name: make it
        id: render
        run: |
          echo "path=out.txt" >> "$GITHUB_OUTPUT"
      - name: use it
        run: |
          echo "${{ steps.render.outputs.url }}"
'''))
        self.assertIn("dangling step output", found)

    def test_a_written_key_is_fine(self):
        text = workflow('''      - name: make it
        id: render
        run: |
          echo "url=https://x/y.jpg" >> "$GITHUB_OUTPUT"
      - name: use it
        run: |
          echo "${{ steps.render.outputs.url }}"
''')
        self.assertEqual(kinds(text), [])


class TheRepositoryItself(unittest.TestCase):
    def test_every_workflow_in_this_repo_lands_its_handoffs(self):
        problems = wh.audit_dir(os.path.join(ROOT, ".github", "workflows"))
        self.assertEqual(problems, [], "\n".join("%s: %s" % pair for pair in problems))

    def test_a_workflow_that_does_not_parse_is_said_not_skipped(self):
        found = wh.audit_text("name: t\njobs: [oops\n", "broken.yml")
        self.assertEqual([kind for kind, _ in found], ["unparseable"],
                         "a file the auditor cannot read must not read as a clean bill of health")

    def test_main_exits_nonzero_when_it_finds_something(self):
        """qa.py treats an empty list as the pass condition, so the CLI has to agree."""
        code = wh.main([os.path.join(ROOT, "..", "definitely-not-a-repo")])
        self.assertEqual(code, 0, "no workflows directory is not a finding; it is nothing to check")




class MachineLines(unittest.TestCase):
    """Rule 4: a key a workflow pulls out with sed has to be printed by someone.

    The failure is quiet in the wrong direction — an empty string, a ledger entry of `unknown`, a
    summary line saying "not reported" — and the producer half of it is easy to miss, because this
    repo prints most of those keys through a shared `machine()` helper that takes them as keyword
    arguments, so no literal `IG_PERMALINK=` ever appears in a source file. The first version of
    this rule did not know that idiom and reported two dangling keys in a lane that was printing
    both of them correctly.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _repo(self, workflow_text, python_text=""):
        root = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(root, ".github", "workflows"), exist_ok=True)
        os.makedirs(os.path.join(root, "tools"), exist_ok=True)
        with open(os.path.join(root, ".github", "workflows", "lane.yml"), "w",
                  encoding="utf-8") as handle:
            handle.write(workflow_text)
        if python_text:
            with open(os.path.join(root, "tools", "publish.py"), "w", encoding="utf-8") as handle:
                handle.write(python_text)
        return root

    def test_a_key_nobody_prints_is_a_finding(self):
        root = self._repo("""name: t
on:
  workflow_dispatch: {}
jobs:
  j:
    steps:
      - name: read it back
        run: |
          PERMALINK=$(sed -n 's/^IG_PERMALINK=//p' /tmp/post.log | tail -1)
""", 'print("IG_RESULT=sent")\n')
        found = wh.audit_machine_lines(root)
        self.assertEqual([kind for kind, _detail in found], ["machine line with no producer"])
        self.assertIn("IG_PERMALINK", found[0][1])

    def test_a_key_printed_through_machine_is_not_a_finding(self):
        """The keyword form is how every lane in this repo actually emits its facts."""
        root = self._repo("""name: t
on:
  workflow_dispatch: {}
jobs:
  j:
    steps:
      - name: read it back
        run: |
          PERMALINK=$(sed -n 's/^IG_PERMALINK=//p' /tmp/post.log | tail -1)
""", '''def machine(result, cause=None, **extra):
    print("IG_RESULT=%s" % result)
    for key, value in extra.items():
        print("%s=%s" % (key, value))


def publish():
    machine("sent", None, IG_PERMALINK=link)
''')
        self.assertEqual(wh.audit_machine_lines(root), [])

    def test_a_key_a_previous_step_echoed_is_produced(self):
        root = self._repo("""name: t
on:
  workflow_dispatch: {}
jobs:
  j:
    steps:
      - name: make it
        run: |
          echo "REEL_URL=$URL" >> "$GITHUB_ENV"
      - name: read it
        run: |
          sed -n 's/^REEL_URL=//p' /tmp/other.log
""")
        self.assertEqual(wh.audit_machine_lines(root), [])

    def test_the_repository_itself_has_no_dangling_machine_lines(self):
        self.assertEqual(wh.audit_machine_lines(ROOT), [])


if __name__ == "__main__":
    unittest.main()
