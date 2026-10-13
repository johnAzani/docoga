#!/usr/bin/env python3
"""Redact values for secret-like config keys in Wrangler output.

Wrangler can include remote variable values in its config-diff warning. Deploy
workflows must pipe raw output through this filter before printing or commenting.
The key names stay visible for diagnosis; values do not.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SENSITIVE_NAME = re.compile(
    r"\b[A-Z0-9_]*(?:SECRET|TOKEN|API_KEY|_KEY|_HASH|PASSWORD|PASSWD|CLIENT_ID|AUTH|CREDENTIAL)[A-Z0-9_]*\b",
    re.IGNORECASE,
)


def redact_lines(lines):
    pending_indent = None
    for line in lines:
        indent = len(line) - len(line.lstrip())
        if pending_indent is not None:
            if not line.strip():
                yield line
                continue
            if indent > pending_indent:
                yield " " * indent + "[REDACTED]\n"
                continue
            pending_indent = None

        match = SENSITIVE_NAME.search(line)
        if not match:
            yield line
            continue

        # Find the assignment separator after the sensitive key, not a colon in
        # an earlier timestamp or log prefix.
        separator = line.find(":", match.end())
        if separator < 0:
            yield line[: match.end()] + " [REDACTED]\n"
            pending_indent = indent
            continue

        yield line[: separator + 1] + " [REDACTED]\n"
        if not line[separator + 1 :].strip():
            pending_indent = indent


def main() -> int:
    if len(sys.argv) > 2:
        print(f"usage: {Path(sys.argv[0]).name} [raw-log-file]", file=sys.stderr)
        return 2
    if len(sys.argv) == 2:
        with open(sys.argv[1], encoding="utf-8", errors="replace") as stream:
            sys.stdout.writelines(redact_lines(stream))
    else:
        sys.stdout.writelines(redact_lines(sys.stdin))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
