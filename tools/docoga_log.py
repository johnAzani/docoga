#!/usr/bin/env python3
"""Where the social lane's scratch files live — one answer for four scripts.

Every publisher in `scripts/` used to write `Path("logs/social_media.log")`: relative to
the current directory, which is the repository root in CI and is whatever a human last
`cd`'d to everywhere else. The practical consequence showed up on 13 Oct 2026 — the
test suite imported the poster, the poster opened the path, and 1,468 lines of
"✅ Photo message sent (id=3)" accumulated in the one file a person might later read as
evidence that something published.

Two rules follow:

  1. paths are absolute and rooted at the repo, so a stray `logs/` never appears in a
     home directory and a run from elsewhere writes the same file CI writes;
  2. `DOCOGA_LOG_DIR` moves the whole family in one place, which is what a test suite
     needs. A per-script knob would have to be remembered by every new script; this one
     is honoured by whoever imports it.

The log stays gitignored scratch. Anything that must survive as *proof* belongs in a
committed ledger (see `tools/youtube_ledger.py`), not here.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def log_dir():
    """The directory for scratch files: `DOCOGA_LOG_DIR`, else `<repo>/logs`."""
    override = os.environ.get("DOCOGA_LOG_DIR")
    return Path(override) if override else REPO_ROOT / "logs"


def log_file(name):
    """One file inside the log dir, created on demand."""
    directory = log_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        # A read-only checkout is a reason not to write a log; it is never a reason to
        # skip a publish. Callers also guard their own writes.
        pass
    return directory / name


def append(path, line):
    """Write one line, swallowing any failure. Returns True if it landed."""
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
        return True
    except OSError:
        return False
