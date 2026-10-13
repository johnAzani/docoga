"""`tools/workflow_handoffs.py` — find values that cross a boundary and never arrive.

Every rule here is a bug this repository has actually had, in this exact shape: a value produced in
one place and consumed in another, where each half is correct and the pair is not. That family is
invisible to any test that exercises one half alone. It is how Telegram's day-dedupe matched
*every* open issue from the day it was written (`RUN_DATE=…` as a shell variable, `contains($ENV.RUN_DATE)`
in jq), and it is how the token vault on 13 Oct 2026 produced a box that `open` read perfectly and
the publisher then sent as a bearer token — a broken day 2, with every single-verb test green.

Three rules:

1. **A `$GITHUB_ENV` write read in the same step.** Actions assembles the environment *between*
   steps, so `echo "X=…" >> "$GITHUB_ENV"` followed by `$X` in the same `run:` block reads empty.
   Pass it as a shell variable, a file, or `$GITHUB_OUTPUT` instead.
2. **`$ENV.X` in a jq program with no environment entry for X.** jq reads the *process
   environment*; a plain `X=…` shell variable never arrives. An empty needle in `contains("")`
   matches every row, so the failure points in the safe-looking direction and nobody looks again.
   Correct shapes: `export X`, a step-level `env:` mapping, or an inline prefix
   (`X=v gh …`, including one continued with `\\`).
3. **`${{ steps.<id>.outputs.<name> }}` that no step writes.** A typo'd id or key becomes the empty
   string rather than an error, so the consumer sees "nothing" while the producer looks successful.

The checker's precision matters as much as its rules: matching `$X` inside `${X_OUT}`, or failing to
see an inline assignment continued across a backslash, fires on every lane at once and teaches
everyone to ignore the output. Both mistakes were made while writing this file and are pinned by
`tools/tests/test_workflow_handoffs.py`, which asserts the clean shapes as well as the broken ones.
"""

import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover - qa installs PyYAML, and so does CI
    yaml = None

ENV_WRITE = re.compile(r"([A-Z][A-Z0-9_]*)=[^\n]*?>>\s*[\"']?\$GITHUB_ENV")
OUTPUT_WRITE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=[^\n]*?>>\s*[\"']?\$GITHUB_OUTPUT")
JQ_ENV = re.compile(r"\$ENV\.([A-Z][A-Z0-9_]*)")
STEP_OUT = re.compile(r"\$\{\{\s*steps\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_-]+)\s*\}\}")
CALLER = re.compile(r"(?:^|[\s|;&(])(?:command\s+)?(?:gh|jq|python3?)\b")
# The machine lines the lanes read back. A producer is either a literal `print("KEY=…")` (or an
# echo/printf of one) or a keyword argument to the shared `machine()` helper — whose keys exist only
# at runtime. That second form is not optional knowledge: without it, rule 4 reported `IG_PERMALINK`
# and `IG_MEDIA_ID` as dangling in a lane that printed both correctly, and a checker that indicts
# working code is worse than one that misses a bug.
SED_READ = re.compile(r"""sed -n 's/\^([A-Z][A-Z0-9_]*)=""")
PRINTED = re.compile(r"""(?:print\(\s*f?["']|echo\s+(?:-[ne]+\s+)*["']|printf\s+(?:-n\s+)?["'])([A-Z][A-Z0-9_]*)=""")
MACHINE_CALL = re.compile(r"machine\(([^)\n]*)\)")
MACHINE_KW = re.compile(r"\b([A-Z][A-Z0-9_]+)=")


def _reference(name):
    """`$name` or `${name}`, but not the prefix of a longer name.

    `${IG_USER_ID_OUT}` is a different variable; a checker that reads it as a use of `IG_USER_ID`
    reports a bug in every lane that names one thing after another.
    """
    return re.compile(r"\$\{?%s\}?(?![A-Za-z0-9_])" % re.escape(name))


def _assigned_before(lines, name, before):
    """Was `name` given to this shell as a variable, before the read at `before`?"""
    pattern = re.compile(r"^\s*(?:export\s+)?%s=" % re.escape(name))
    return any(idx < before and pattern.search(line) for idx, line in enumerate(lines))


def _inlined_before(joined_line, name):
    """`NAME=value gh …` — an inline prefix, which *does* reach the child's environment.

    Checked against the whole logical line (backslash continuations joined) because that is how the
    lanes in this repository are written, and a checker that only looks at one physical line calls
    every correct one of them a bug.
    """
    call = CALLER.search(joined_line)
    if not call:
        return False
    prefix = joined_line[:call.start()]
    # `|`, `;`, `&`, `(` *and* whitespace: the lanes chain assignments (`A=1 B=2 gh …`), and a
    # rule that recognises only the first one calls a correct line a bug — which is exactly how
    # this checker behaved on its first run, flagging LEGACY_PREFIX while accepting CAUSE_TAG on
    # the same line of the same file.
    return re.search(r"(?:^|[|;&(\s])%s=" % re.escape(name), prefix) is not None


def _steps(doc):
    for _job_name, job in (doc.get("jobs") or {}).items():
        for step in (job.get("steps") or []):
            yield step


def audit_text(text, label=""):
    """`[(kind, detail)]` for one workflow's YAML text. Empty means every handoff lands."""
    if yaml is None:
        return [("unchecked", "PyYAML is not installed, so no workflow could be parsed")]
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [("unparseable", "%s: %s" % (label, exc))]
    if not isinstance(doc, dict):
        return []

    blocks = [(step, step["run"]) for step in _steps(doc) if step.get("run")]
    problems = []

    for step, run in blocks:
        lines = run.splitlines()
        joined = re.sub(r"\\\n\s*", " ", run)
        step_env = set((step.get("env") or {}).keys())

        for name in sorted({m.group(1) for m in ENV_WRITE.finditer(run)}):
            writer = re.compile(r"%s=" % re.escape(name))
            reads = [idx for idx, line in enumerate(lines)
                     if _reference(name).search(line)
                     and not (ENV_WRITE.search(line) and writer.search(line))]
            if not reads:
                continue
            if _assigned_before(lines, name, min(reads)) or name in step_env:
                continue
            problems.append(("same-step $GITHUB_ENV read",
                             "%s: `%s` is written to $GITHUB_ENV and read in the same step, where "
                             "Actions has not assembled the environment yet — use a shell "
                             "variable, a file, or $GITHUB_OUTPUT for the current step's own "
                             "reading" % (label or "workflow", name)))

        for name in sorted(set(JQ_ENV.findall(run))):
            if name in step_env:
                continue
            if re.search(r"^\s*export\s+%s\b" % re.escape(name), run, re.M):
                continue
            if any(_inlined_before(line, name) for line in joined.splitlines()):
                continue
            problems.append(("jq $ENV.%s has no environment entry" % name,
                             "%s: jq reads the process environment, so a plain `%s=…` shell "
                             "variable never reaches it — and `contains(\"\")` is true for every "
                             "row, which reads as a match rather than a bug"
                             % (label or "workflow", name)))

    writers = {}
    for step, run in blocks:
        if step.get("id"):
            writers.setdefault(step["id"], set()).update(m.group(1) for m in OUTPUT_WRITE.finditer(run))
    for step, run in blocks:
        for sid, key in STEP_OUT.findall(run):
            if key in writers.get(sid, set()):
                continue
            problems.append(("dangling step output",
                             "%s: `${{ steps.%s.outputs.%s }}` — %s" % (
                                 label or "workflow", sid, key,
                                 "no step in this job has that id, so the expression is the empty "
                                 "string and not an error" if sid not in writers
                                 else "step `%s` never writes `%s` to $GITHUB_OUTPUT" % (sid, key))))
    return problems


def _python_files(root):
    for sub in ("tools", "scripts"):
        directory = os.path.join(root, sub)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name.endswith(".py"):
                path = os.path.join(directory, name)
                with open(path, encoding="utf-8") as handle:
                    yield path, handle.read()


def audit_machine_lines(root):
    """Every `sed -n 's/^KEY=//p'` a workflow runs must have a producer.

    Exit codes and ids travel from a publisher to a workflow as one-line facts in its log. A key
    that nothing prints does not fail loudly: sed answers with an empty string, the ledger records
    `unknown`, the summary says "not reported", and a lane that worked is indistinguishable from one
    that half-worked — which is how a real signal gets dismissed a week later.
    """
    wf_dir = os.path.join(root, ".github", "workflows")
    if not os.path.isdir(wf_dir):
        return []
    read, produced = {}, set()
    for name in sorted(os.listdir(wf_dir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        with open(os.path.join(wf_dir, name), encoding="utf-8") as handle:
            text = handle.read()
        for key in SED_READ.findall(text):
            read.setdefault(key, set()).add(name)
        produced.update(PRINTED.findall(text))   # some keys are echoed by an earlier step
    for _path, text in _python_files(root):
        produced.update(PRINTED.findall(text))
        for call in MACHINE_CALL.findall(text):
            produced.update(MACHINE_KW.findall(call))
    return [("machine line with no producer",
             "%s read by %s with `sed -n 's/^%s=//p'` matches nothing any file prints — the read "
             "yields an empty string, so print it or pass it to `machine()`" % (
                 key, ", ".join(sorted(files)), key))
            for key, files in sorted(read.items()) if key not in produced]


def audit_file(path):
    with open(path, encoding="utf-8") as handle:
        return audit_text(handle.read(), os.path.basename(path))


def audit_dir(workflows_dir):
    found = []
    if not os.path.isdir(workflows_dir):
        return found
    for name in sorted(os.listdir(workflows_dir)):
        if name.endswith((".yml", ".yaml")):
            found.extend(audit_file(os.path.join(workflows_dir, name)))
    return found


def audit_repo(root):
    """Everything: the per-workflow rules, plus the machine lines across the repository."""
    return audit_dir(os.path.join(root, ".github", "workflows")) + audit_machine_lines(root)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = argv[0] if argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    problems = audit_repo(root)
    for _kind, detail in problems:
        print("%s: %s" % (_kind, detail), file=sys.stderr)
    print("workflow handoffs: %d suspect(s) in %s" % (len(problems), root))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
