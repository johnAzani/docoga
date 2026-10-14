#!/usr/bin/env python3
"""Which Deep-Dive episode should the nightly tick work on?

`next` prints the first id in episodes/queue.json whose YouTube title is not yet in the
long-form ledger — or nothing, when the queue is done. `status` lists them all. Pure
stdlib: the workflow calls this before any heavy dependency is installed.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "episodes" / "queue.json"
LEDGER = ROOT / "logs" / "youtube_longform.json"


def published_titles(ledger=LEDGER):
    if not Path(ledger).is_file():
        return set()
    try:
        return {e.get("title", "") for e in json.loads(Path(ledger).read_text(encoding="utf-8"))}
    except (ValueError, AttributeError):
        return set()


def entries(queue=QUEUE, ledger=LEDGER):
    ids = json.loads(Path(queue).read_text(encoding="utf-8")).get("queue", [])
    done = published_titles(ledger)
    out = []
    for ep in ids:
        meta_path = ROOT / "episodes" / ep / "episode.json"
        if not meta_path.is_file():
            out.append((ep, "missing", ""))
            continue
        title = json.loads(meta_path.read_text(encoding="utf-8")).get("youtube", {}).get("title", "")
        out.append((ep, "published" if title in done else "pending", title))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["next", "status"])
    ap.add_argument("--queue", default=str(QUEUE))
    ap.add_argument("--ledger", default=str(LEDGER))
    a = ap.parse_args(argv)
    rows = entries(a.queue, a.ledger)
    if a.cmd == "status":
        for ep, state, title in rows:
            print("%-6s %-10s %s" % (ep, state, title))
        return 0
    for ep, state, _ in rows:
        if state == "pending":
            print(ep)
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
