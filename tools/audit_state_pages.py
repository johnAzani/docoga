#!/usr/bin/env python3
"""Measure how different DocOga's state pages actually are from each other.

WHY THIS EXISTS
---------------
The state pages are generated from one template with the state name swapped in.
That is exactly the pattern Google's spam policy describes as **doorway abuse**:
"having multiple domain names or pages targeted at specific regions or cities
that funnel users to one page" and "creating substantially similar pages".
The practical test is: *would these pages be indistinguishable from each other
if the place name were removed?*

Measured 8 Oct 2026 on the 48 pages then shipping (12 states x 4 tools):

    median pairwise similarity ....... 94.2%
    median unique words per page ..... 3
    median body words per page ....... 449-544

Three unique words is the state name, the capital and a city. The pages fail
the test. This script makes that number visible and, once the pages are fixed,
keeps them fixed.

TARGETS (from the research in docs/STATE_TENANCY_RESEARCH.md §2):
  * --max-similarity 0.80  — no two same-tool state pages may be more alike
  * --min-unique-words 250 — words appearing on no other sibling state page
  * --min-body-words 500   — indexable body text, excluding boilerplate

USAGE
    python3 tools/audit_state_pages.py               # report
    python3 tools/audit_state_pages.py --strict      # exit 1 if targets are missed
    python3 tools/audit_state_pages.py --show-top 5  # worst offenders

--strict is NOT wired into tools/qa.py yet: the pages would fail it today by a
wide margin, and a gate that fails everything gets deleted rather than obeyed.
It gets wired in the moment the enrichment in the research dossier lands and
the numbers are actually under target.
"""
import argparse
import itertools
import json
import os
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

DEFAULT_MAX_SIMILARITY = 0.80
DEFAULT_MIN_UNIQUE_WORDS = 250
DEFAULT_MIN_BODY_WORDS = 500

STRIP = re.compile(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", re.S)
TAGS = re.compile(r"<[^>]+>")
WORD = re.compile(r"[A-Za-z0-9₦%’']+")


def body_words(path):
    """Visible, indexable words on a page — nav/head/footer included.

    Deliberately conservative: if anything, this over-counts how much real
    content a page has, so the target is not flattered.
    """
    html = STRIP.sub(" ", Path(path).read_text(encoding="utf-8"))
    text = TAGS.sub(" ", html)
    text = text.replace("&nbsp;", " ").replace("&amp;", " ")
    return [w.lower() for w in WORD.findall(text)]


def discover_state_pages():
    """Group site/<tool>-<state>.html by tool, using the sitemap as the index.

    The sitemap is the authority on what we publish; a page not in it is not
    shipped and should not be measured.
    """
    sitemap = (SITE / "sitemap.xml").read_text(encoding="utf-8")
    locs = re.findall(r"<loc>https://docoga\.com\.ng/([^<]+)</loc>", sitemap)
    by_tool = {}
    for name in locs:
        if not name.endswith(".html"):
            continue
        for tool in ("tenancy-agreement", "notice-to-quit", "rent-receipt", "caution-fee"):
            if name.startswith(tool + "-") and name != "tenancy-agreement-nigeria.html":
                if not name.endswith("-nigeria.html"):
                    by_tool.setdefault(tool, []).append(name)
    return by_tool


def audit(max_similarity, min_unique, min_body, show_top):
    by_tool = discover_state_pages()
    if not by_tool:
        print("No state pages found in the sitemap.")
        return 1

    failures = []
    print("DocOga — state page uniqueness audit")
    print("Targets: similarity <= %.2f · unique words >= %d · body words >= %d"
          % (max_similarity, min_unique, min_body))
    print("=" * 72)

    for tool, names in sorted(by_tool.items()):
        words = {}
        for name in names:
            path = SITE / name
            if path.exists():
                words[name] = body_words(path)
        if len(words) < 2:
            continue

        pairs = []
        for a, b in itertools.combinations(sorted(words), 2):
            sa, sb = set(words[a]), set(words[b])
            pairs.append((len(sa & sb) / len(sa | sb), a, b))

        unique = {}
        for name in words:
            others = set().union(*[set(v) for k, v in words.items() if k != name])
            unique[name] = len(set(words[name]) - others)

        lengths = {name: len(v) for name, v in words.items()}
        worst_pairs = sorted(pairs, reverse=True)[:show_top]
        med_sim = statistics.median(p for p, _, _ in pairs)
        med_uniq = statistics.median(unique.values())
        med_len = statistics.median(lengths.values())

        bad_sim = [p for p in pairs if p[0] > max_similarity]
        bad_uniq = [(n, u) for n, u in unique.items() if u < min_unique]
        bad_len = [(n, l) for n, l in lengths.items() if l < min_body]

        print("\n%s (%d pages)" % (tool, len(words)))
        print("  median similarity .... %5.1f%%   %s" % (med_sim * 100, "OK" if not bad_sim else "OVER TARGET"))
        print("  median unique words .. %5d     %s" % (med_uniq, "OK" if not bad_uniq else "UNDER TARGET"))
        print("  median body words .... %5d     %s" % (med_len, "OK" if not bad_len else "UNDER TARGET"))
        print("  most similar pairs:")
        for sim, a, b in worst_pairs:
            flag = "  <-- over target" if sim > max_similarity else ""
            print("     %5.1f%%  %s / %s%s" % (sim * 100, a, b, flag))

        for sim, a, b in bad_sim:
            failures.append("%s: %s and %s are %.1f%% identical (target <= %.0f%%)"
                            % (tool, a, b, sim * 100, max_similarity * 100))
        for name, count in bad_uniq:
            failures.append("%s: only %d unique words (target >= %d)" % (name, count, min_unique))
        for name, count in bad_len:
            failures.append("%s: only %d body words (target >= %d)" % (name, count, min_body))

    print("\n" + "=" * 72)
    if failures:
        print("%d target(s) missed:" % len(failures))
        for f in failures[:25]:
            print("  - %s" % f)
        if len(failures) > 25:
            print("  ... and %d more" % (len(failures) - 25))
        print("\nThese pages are the doorway-page pattern: swap the place name")
        print("and they would be indistinguishable. See docs/STATE_TENANCY_RESEARCH.md.")
    else:
        print("All state pages are inside the uniqueness targets.")
    return 1 if failures else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit state page uniqueness (doorway-page risk)")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero when any target is missed (report-only by default)")
    parser.add_argument("--max-similarity", type=float, default=DEFAULT_MAX_SIMILARITY)
    parser.add_argument("--min-unique-words", type=int, default=DEFAULT_MIN_UNIQUE_WORDS)
    parser.add_argument("--min-body-words", type=int, default=DEFAULT_MIN_BODY_WORDS)
    parser.add_argument("--show-top", type=int, default=3)
    parser.add_argument("--json", action="store_true", help="machine-readable summary")
    args = parser.parse_args(argv)

    code = audit(args.max_similarity, args.min_unique_words, args.min_body_words, args.show_top)
    return code if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
