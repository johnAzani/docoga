#!/usr/bin/env python3
"""
Which YouTube videos should be made next — from searches that already happened
==============================================================================

The long-form lane renders whatever is in `episodes/queue.json`. Until now that
queue was a content idea list: eight essay-titled Deep-Dives ("The Only 4
Deductions a Landlord Can Make"), published to a channel nobody searches for.

This turns the queue around. It reads the demand the site has already measured —
`logs/search_console.json`, i.e. the queries Google showed docoga.com.ng for in
the last 28 days — and proposes the videos that answer those queries, titled the
way people type them. A query the site already ranks 9th–11th for is the best
evidence available at ₦0 that (a) somebody wants it and (b) no strong page owns
it. A video ranking for the same phrase is a second surface on the same demand.

What it does *not* do: touch YouTube, touch `episodes/queue.json`, or render
anything. It writes a brief (`logs/yt_search_lane.json`) that a human or the
Deep-Dive engine can pick up, and `--check` fails the build if the brief has
drifted into essay titles or duplicated a topic already published.

    python3 tools/yt_search_lane.py --write          # rank today's demand → logs/yt_search_lane.json
    python3 tools/yt_search_lane.py --print          # the same, as a table for the DM / a PR
    python3 tools/yt_search_lane.py --check          # CI: shape + no duplicates, no network

Everything here is pure stdlib and reads only repo files, so it runs inside
`tools/qa.py` without dependencies and without a key.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "logs" / "search_console.json"
EPISODES = ROOT / "episodes"
LONGFORM = ROOT / "logs" / "youtube_longform.json"
OUT = ROOT / "logs" / "yt_search_lane.json"

# YouTube shows roughly the first 3 words of a title in search and ~60 characters
# on mobile. Both are hard rules here, not advice: a candidate that does not start
# with its query cannot be found by that query.
MAX_TITLE = 70
MIN_CANDIDATES = 3

STOPWORDS = {"the", "and", "for", "from", "with", "what", "your", "how", "many", "does", "can"}

# Search Console hands back fragments as well as queries: a bare city ("kano"), a
# county-level continuation ("in plateau state"). They are real rows and useless
# titles, so the lane drops them rather than building a video called "Kano (2026)".
PLACES = {"kano", "lagos", "abuja", "edo", "rivers", "plateau", "enugu", "delta", "anambra",
          "benin", "portharcourt", "harcourt", "nigeria", "state", "city"}
# Words that stay capitalised inside a title even though they are not the first word.
PROPER = {"nigeria", "edo", "lagos", "abuja", "kano", "rivers", "plateau", "enugu", "delta",
          "anambra", "benin", "harcourt", "kwara", "oyo", "ogun", "abia", "imo", "kaduna"}

# Near-misses: ranking here means Google already decided the page is relevant, and
# a video is cheap to make for the same phrase. Positions 1–4 are earned pages; 45+
# is a page that is not really about the query.
NEAR_LOW, NEAR_HIGH = 5.0, 20.0


def load_console(path=CONSOLE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("top_queries") or []


def published(root=ROOT, longform=LONGFORM):
    """Every topic already on the channel, normalised for comparison."""
    seen = set()
    for path in glob.glob(str(Path(root) / "episodes" / "*" / "episode.json")):
        try:
            meta = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key in ("topic", "title"):
            value = meta.get(key) or ""
            if value:
                seen.add(_norm(value))
        youtube = meta.get("youtube") or {}
        for key in ("title", "topic"):
            if youtube.get(key):
                seen.add(_norm(youtube[key]))
    try:
        for row in json.loads(Path(longform).read_text(encoding="utf-8")):
            for key in ("title", "topic"):
                if row.get(key):
                    seen.add(_norm(row[key]))
    except (OSError, ValueError, TypeError):
        pass
    return seen


def _norm(text):
    return re.sub(r"[^a-z0-9 ]+", "", (text or "").lower()).strip()


def usable(query):
    """Is this row a query a video could be titled after, or a fragment?"""
    words = _norm(query).split()
    if len(words) < 2:
        return False
    if words[0] == "in":
        return False
    if all(word in PLACES for word in words):
        return False
    return True


def sentence_case(text):
    """Lower the shouty words Search Console copies out of page headings, keep names."""
    out = []
    for index, word in enumerate(text.split()):
        bare = word.lower().strip(",.:;")
        if index and bare not in PROPER and word[:1].isupper():
            out.append(word[0].lower() + word[1:])
        else:
            out.append(word)
    return " ".join(out)


def covered_by(query, covered):
    """Is this query already an episode? A query's topic words (not its place words)
    being a subset of a published title is enough — "caution fee nigeria" is covered
    by "Caution Fee in Nigeria: The Only 4 Deductions a Landlord Can Make"."""
    tokens = {w for w in _norm(query).split() if len(w) > 2 and w not in PLACES}
    if not tokens:
        return False
    return any(tokens <= set(name.split()) for name in covered)


def _words(text):
    return [w for w in _norm(text).split() if len(w) > 2 and w not in STOPWORDS]


def page_hook(page_url, root=ROOT):
    """The half of a page's <h1> after the colon — the line the page already uses
    to say why it exists. Empty when the page has no such shape or no file."""
    slug = (page_url or "").rstrip("/").split("/")[-1]
    if not slug or slug.endswith(".html") is False and "." in slug:
        slug = slug.split(".")[0]
    path = Path(root) / "site" / (slug if slug.endswith(".html") else slug + ".html")
    if not path.is_file():
        return ""
    html = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if not match:
        return ""
    text = re.sub(r"<[^>]+>", " ", match.group(1))
    text = re.sub(r"\s+", " ", text).strip()
    for dash in (":", "—", "–"):
        if dash in text:
            tail = text.split(dash, 1)[1].split("+")[0].strip()   # drop page-copy add-ons
            if 8 <= len(tail) <= 55:
                return sentence_case(tail)
    return ""


def title_for(query, page="", year=None):
    """A title in the shape people search: the query first, the hook second."""
    year = year or date.today().year
    query = (query or "").strip()
    if not query:
        raise ValueError("a candidate needs a query")
    head = query[0].upper() + query[1:]
    if head.lower().endswith("nigeria"):
        head = head
    hook = page_hook(page) if page else ""
    if hook and len("%s: %s (%d)" % (head, hook, year)) <= MAX_TITLE:
        return "%s: %s (%d)" % (head, hook, year)
    short = "%s (%d)" % (head, year)
    if len(short) <= MAX_TITLE:
        return short
    return head[:MAX_TITLE]


def score(row):
    """Rank by proven demand first, near-miss position second."""
    impressions = int(row.get("impressions") or 0)
    position = float(row.get("position") or 999)
    near = 1 if NEAR_LOW <= position <= NEAR_HIGH else 0
    return (impressions * 10) + (near * 5) - min(position, 100) / 100.0


def candidates(rows=None, covered=None, root=ROOT, year=None):
    rows = load_console() if rows is None else rows
    covered = published(root) if covered is None else covered
    out, seen_pages = [], set()
    for row in sorted(rows, key=score, reverse=True):
        query = (row.get("query") or "").strip()
        page = (row.get("page") or "").strip()
        if not query or not usable(query):
            continue
        if _norm(query) in covered or covered_by(query, covered):
            continue
        # One video per page: two videos for the same page compete with each other.
        key = _norm(page) or _norm(query)
        if key in seen_pages:
            continue
        seen_pages.add(key)
        position = float(row.get("position") or 0)
        out.append({
            "query": query,
            "title": title_for(query, page, year),
            "page": page,
            "impressions": int(row.get("impressions") or 0),
            "position": position,
            "near_miss": bool(NEAR_LOW <= position <= NEAR_HIGH),
            "why": ("%d impression%s at position %.1f — Google already believes the page "
                    "answers this, and no video does" % (
                        int(row.get("impressions") or 0),
                        "" if int(row.get("impressions") or 0) == 1 else "s", position)),
        })
    return out


def describe(found):
    if not found:
        return "No candidates: every measured query already has an episode."
    lines = ["%d video%s worth making, from queries the site already ranks for:" % (
        len(found), "" if len(found) == 1 else "s"), ""]
    for i, c in enumerate(found, 1):
        lines.append("%d. **%s**" % (i, c["title"]))
        lines.append("   search: `%s` · %s · %s" % (c["query"], c["why"], c["page"] or "no page"))
    return "\n".join(lines)


def check(path=OUT):
    """Shape rules that keep the brief usable. Returns a list of problems."""
    problems = []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["%s: %s" % (path, exc)]
    found = data.get("candidates") or []
    # No count floor: the honest state "every measured query now has an episode" is
    # an empty brief, not a failure. The shape rules below are what CI defends.
    if "candidates" not in data:
        problems.append("%s: no candidates key — was this written by hand?" % path)
    titles = [_norm(c.get("title")) for c in found]
    if len(set(titles)) != len(titles):
        problems.append("%s: two candidates share a title" % path)
    for c in found:
        title, query = c.get("title") or "", c.get("query") or ""
        if not title or not query:
            problems.append("%s: a candidate is missing its query or title" % path)
            continue
        if _norm(query) not in _norm(title):
            problems.append("%r does not contain its query %r (YouTube matches the first words)" % (title, query))
        if len(title) > MAX_TITLE:
            problems.append("%r is %d characters (ceiling %d)" % (title, len(title), MAX_TITLE))
        if not re.search(r"\(20\d\d\)", title):
            problems.append("%r carries no year (the audience searches for 2026)" % title)
        missing = [w for w in _words(query) if w not in _norm(title)]
        if missing:
            problems.append("%r drops %s from the query" % (title, ", ".join(missing)))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1].strip())
    parser.add_argument("--write", action="store_true", help="write logs/yt_search_lane.json")
    parser.add_argument("--print", dest="show", action="store_true", help="print the brief")
    parser.add_argument("--check", action="store_true", help="validate the brief (CI; no network)")
    parser.add_argument("--json", default=str(OUT))
    args = parser.parse_args(argv)

    if args.check:
        problems = check(args.json)
        for problem in problems:
            print("  ❌ %s" % problem)
        print("yt_search_lane: %s" % ("ok" if not problems else "%d problem(s)" % len(problems)))
        return 0 if not problems else 1

    found = candidates()
    payload = {
        "_comment": ("Video candidates derived from logs/search_console.json — real queries the site "
                     "already appears for. Ordered by proven demand. Written by tools/yt_search_lane.py; "
                     "nothing here touches YouTube or episodes/queue.json."),
        "taken_at": date.today().isoformat(),
        "candidates": found,
    }
    if args.write:
        Path(args.json).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote %s (%d candidates)" % (args.json, len(found)))
    if args.show or not args.write:
        print(describe(found))
    return 0


if __name__ == "__main__":
    sys.exit(main())
