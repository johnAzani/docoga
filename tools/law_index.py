#!/usr/bin/env python3
"""law_index.py — the brain's law shelf: every verified statement in
`tools/state_law_data.py`, flattened into numbered facts the editor may cite.

Why a separate module
---------------------
`state_law_data.py` is written for the state pages: nested dicts, HTML in the
text, one shape per topic. The editor (tools/brain.py) needs the opposite — a
flat list where every entry has an id, a state, a section cite and one plain
sentence, so that

  * the prompt can show the model exactly what it is allowed to say, and
  * the citation gate can check a draft's claims against ids that exist,
    without string-matching section numbers written five different ways.

A fact id looks like `lagos:notice_ladder:4`. The rule the gate enforces: a
legal claim in a post is published only if it names a fact id that exists for
the state it talks about, and the verifier agrees the fact supports the claim.

    python3 tools/law_index.py                 # counts per state
    python3 tools/law_index.py lagos           # the Lagos shelf, one line per fact
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import state_law_data as law  # noqa: E402

TAG = re.compile(r"<[^>]+>")
CITE_IN_TEXT = re.compile(r"^\s*(s\.\s*[0-9][0-9A-Za-z().,–\- ]{0,40}?)\s*[—:\-–]\s*", re.U)
# Topics that are notes about the file itself, not law a post may lean on.
SKIP_KEYS = {"slug", "name", "place", "full", "tier", "tier_note", "sources", "open_questions",
             "statutes", "source", "citation", "signed_by", "commenced", "how_to_read",
             "schedules_omitted", "stale_warning", "status", "_comment"}
MAX_TEXT = 420


def plain(text):
    """HTML → one plain line, entities decoded, whitespace collapsed."""
    t = html.unescape(TAG.sub("", str(text or "")))
    return " ".join(t.split())


def _clip(text):
    text = plain(text)
    if len(text) <= MAX_TEXT:
        return text
    cut = text[:MAX_TEXT].rsplit(". ", 1)[0]
    return (cut if len(cut) > 120 else text[:MAX_TEXT]).rstrip(".") + "."


def _facts_from(value, slug, key, cite, out):
    """Walk one topic of a state's dict and append facts to `out`."""
    if isinstance(value, dict):
        own_cite = value.get("cite") or cite
        text = value.get("text")
        if text:
            out.append(dict(key=key, cite=plain(own_cite or ""), text=_clip(text)))
        for sub, item in value.items():
            if sub in ("cite", "text") or sub in SKIP_KEYS:
                continue
            _facts_from(item, slug, "%s.%s" % (key, sub), own_cite, out)
    elif isinstance(value, list):
        if value and all(isinstance(row, (list, tuple)) for row in value):
            for row in value:
                cells = [plain(c) for c in row]
                row_cite = cells[-1] if cells and cells[-1].lower().startswith("s.") else plain(cite or "")
                body = cells[:-1] if row_cite and cells and cells[-1] == row_cite else cells
                out.append(dict(key=key, cite=row_cite, text=_clip(": ".join(b for b in body if b))))
        else:
            for item in value:
                if isinstance(item, str):
                    text = plain(item)
                    m = CITE_IN_TEXT.match(text)
                    out.append(dict(key=key, cite=plain(m.group(1)) if m else plain(cite or ""),
                                    text=_clip(text)))
                else:
                    _facts_from(item, slug, key, cite, out)
    elif isinstance(value, str) and key.split(".")[-1] not in SKIP_KEYS:
        text = plain(value)
        if len(text) > 24:
            out.append(dict(key=key, cite=plain(cite or ""), text=_clip(text)))


def facts_for(slug):
    """[{id, state, slug, tier, statute, key, cite, text}] for one state."""
    state = law.STATE_LAW[slug]
    statute = (state.get("statutes") or [{}])[0].get("title", "")
    raw = []
    for key, value in state.items():
        if key in SKIP_KEYS:
            continue
        _facts_from(value, slug, key, None, raw)
    facts, seen, counter = [], set(), {}
    for fact in raw:
        sig = fact["text"].lower()
        if not fact["text"] or sig in seen:
            continue
        seen.add(sig)
        topic = fact["key"].split(".")[0]
        counter[topic] = counter.get(topic, 0) + 1
        facts.append(dict(id="%s:%s:%d" % (slug, topic, counter[topic]), state=state["name"],
                          slug=slug, tier=state.get("tier", ""), statute=statute,
                          key=fact["key"], cite=fact["cite"], text=fact["text"]))
    return facts


def all_facts():
    out = []
    for slug in law.STATE_LAW:
        out.extend(facts_for(slug))
    return out


def by_id(facts=None):
    return {f["id"]: f for f in (facts or all_facts())}


def states():
    """[(slug, name, tier)] — publishable states, Tier A first."""
    rows = [(slug, st["name"], st.get("tier", "")) for slug, st in law.STATE_LAW.items()]
    return sorted(rows, key=lambda r: (r[2], r[1]))


def shelf_text(slug, limit=None):
    """The prompt-ready shelf for one state: `id | cite | text` lines."""
    lines = []
    for fact in facts_for(slug)[: limit or None]:
        lines.append("%s | %s | %s" % (fact["id"], fact["cite"] or "(no section)", fact["text"]))
    return "\n".join(lines)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print(shelf_text(argv[0]))
        return 0
    for slug, name, tier in states():
        print("%-12s tier %s  %3d facts" % (slug, tier, len(facts_for(slug))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
