#!/usr/bin/env python3
"""snippet_audit.py — the words Google shows for us, checked by a machine (🔒 docs/GROWTH.md, 12 Nov 2026).

Why. The 9 Nov Search Console pull put eleven of our pages on page one with impressions and almost no
clicks: /notice-to-quit-edo at position 6.3 (55 impressions, 1 click), /power-of-attorney-nigeria at
4.7 (57, 1), /notice-to-quit-kaduna at 7.0 (15, 0), /notice-to-quit-kano at 4.4 (12, 0). The ranking
is earned; the *snippet* loses the tap. Reading the pages showed why: 59 of 97 titles ran past 60
characters (the state pages at 64–84 — "… — Free Generator (2026)" is cut off the end in results),
and all twelve notice-to-quit state pages carried one identical description with no number in it,
while the searcher's question is a number ("how many months").

What this does, with no hands:
  * `audit(site)` — every public page: title ≤ TITLE_MAX characters, description within
    DESC_MIN..DESC_MAX, no two pages sharing a title or a description, and a title that does not end
    in an ellipsis. Returns problems as "page: what".
  * `underperformers(data)` — from the Search Console pull: pages with ≥ MIN_IMPR impressions at an
    average position ≤ 10 whose click-through rate is below a floor for that position. The floor is a
    *working assumption* of this tool (roughly a third of what a page-one result typically earns),
    not a measured DocOga figure — it exists to rank the pages worth a snippet review, nothing more.
  * `scorecard_lines()` — the Monday block: the worst snippets, so the week's dive starts there.

    python3 tools/snippet_audit.py            # print the audit and the underperformers
    python3 tools/snippet_audit.py --check    # exit 1 when a page breaks a rule (qa.py 11d-ter)

Rules of the house that this respects: no page is written or renamed here — the generators own the
words (tools/gen_state_pages.py, tools/sample_docs.py, tools/guides_build.py); this only measures.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SEARCH = ROOT / "logs" / "search_console.json"

TITLE_MAX = 60          # what a desktop result shows before the cut, in characters (≈ 600 px)
DESC_MIN, DESC_MAX = 70, 160
MIN_IMPR = 10
SKIP = {"admin.html", "success.html", "tiktok-connect.html", "privacy.html", "terms.html", "support.html"}

# Floor click-through rate by average position (working assumption, see the docstring).
CTR_FLOOR = {1: 0.08, 2: 0.05, 3: 0.04, 4: 0.03, 5: 0.025, 6: 0.02, 7: 0.015, 8: 0.012, 9: 0.01, 10: 0.01}

TITLE = re.compile(r"<title>(.*?)</title>", re.S)
DESC = re.compile(r'<meta\s+name="description"\s+content="(.*?)"', re.S)


def pages(site: Path = SITE):
    out = []
    for p in sorted(list(site.glob("*.html")) + list((site / "guides").glob("*.html"))):
        if p.name in SKIP or p.parent.name == "admin":
            continue
        out.append(p)
    return out


def meta(page: Path):
    text = page.read_text(encoding="utf-8", errors="replace")
    t = TITLE.search(text)
    d = DESC.search(text)
    return (html.unescape(t.group(1).strip()) if t else "", html.unescape(d.group(1).strip()) if d else "")


def audit(site: Path = SITE):
    """Problems as 'relative/page.html: reason' — empty when every snippet is within the rules."""
    problems, titles, descs = [], {}, {}
    for p in pages(site):
        rel = str(p.relative_to(site))
        title, desc = meta(p)
        if not title:
            problems.append("%s: no <title>" % rel)
            continue
        if len(title) > TITLE_MAX:
            problems.append("%s: title %d chars (max %d): %s" % (rel, len(title), TITLE_MAX, title))
        if title.endswith(("…", "...")):
            problems.append("%s: title ends in an ellipsis: %s" % (rel, title))
        if not desc:
            problems.append("%s: no meta description" % rel)
        elif not DESC_MIN <= len(desc) <= DESC_MAX:
            problems.append("%s: description %d chars (want %d–%d)" % (rel, len(desc), DESC_MIN, DESC_MAX))
        if title.lower() in titles:
            problems.append("%s: same title as %s" % (rel, titles[title.lower()]))
        titles.setdefault(title.lower(), rel)
        if desc:
            if desc.lower() in descs:
                problems.append("%s: same description as %s" % (rel, descs[desc.lower()]))
            descs.setdefault(desc.lower(), rel)
    return problems


def _path(page):
    return re.sub(r"^https?://[^/]+", "", str(page or "")) or "/"


def floor_for(position: float) -> float:
    return CTR_FLOOR[min(10, max(1, int(round(position))))]


def underperformers(data=None, min_impr: int = MIN_IMPR):
    """Pages on page one whose click-through rate sits under the floor for their position — worst first."""
    data = data if data is not None else load()
    rows = []
    for p in (data or {}).get("top_pages") or []:
        if not isinstance(p, dict):
            continue
        impr, clicks, pos = int(p.get("impressions") or 0), int(p.get("clicks") or 0), float(p.get("position") or 99)
        if impr < min_impr or pos > 10:
            continue
        ctr = clicks / impr
        floor = floor_for(pos)
        if ctr < floor:
            rows.append({"page": _path(p.get("page")), "impressions": impr, "clicks": clicks, "position": round(pos, 1),
                         "ctr": round(ctr, 3), "floor": floor, "gap": round((floor - ctr) * impr, 1)})
    return sorted(rows, key=lambda r: -r["gap"])


def load(path=None):
    try:
        data = json.loads(Path(path or SEARCH).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def scorecard_lines(path=None, site: Path = SITE):
    """The Monday block. Never raises."""
    lines = []
    try:
        problems = audit(site)
        lines.append("- snippets in the rules: %s" % ("yes — every title ≤ %d chars, every description unique" % TITLE_MAX
                                                      if not problems else "no — %d problem(s); first: %s" % (len(problems), problems[0])))
        rows = underperformers(load(path))
        if rows:
            lines.append("- snippets losing the tap (page one, under the floor): %s"
                         % "; ".join("%s pos %s %d/%d" % (r["page"], r["position"], r["clicks"], r["impressions"]) for r in rows[:4]))
        else:
            lines.append("- snippets losing the tap: none in the pull (or no pull yet)")
    except Exception as exc:  # the scorecard must print whatever happens
        lines.append("- snippet audit: not read (%s)" % exc)
    return lines


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    problems = audit()
    if "--check" in argv:
        for p in problems:
            print("  ❌ " + p)
        print("snippet_audit: %s" % ("ok — %d pages" % len(pages()) if not problems else "%d problem(s)" % len(problems)))
        return 1 if problems else 0
    for line in scorecard_lines():
        print(line)
    for p in problems:
        print("  - " + p)
    for r in underperformers():
        print("  %s  pos %s  %d clicks / %d impressions  (ctr %.1f%% < floor %.1f%%)"
              % (r["page"], r["position"], r["clicks"], r["impressions"], r["ctr"] * 100, r["floor"] * 100))
    return 0


if __name__ == "__main__":
    sys.exit(main())
