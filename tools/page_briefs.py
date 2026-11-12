#!/usr/bin/env python3
"""Page briefs — the field writes the research list (7 Nov 2026, 🔒 docs/BRAIN_GROWTH.md).

The competitor watch marks a rival title "◻ uncovered" when no DocOga money page answers it
(`competitor_watch.gaps`). Until today that line sat on the Monday scorecard and waited for a human
to notice. Now the Brain keeps the sightings across pulls (`brain/page_briefs.json`); the **second**
time the field writes on the same question — a second rival, a second title, a second week — it
drafts a **page brief** for the owner to research: the question, who is asking, what the law shelf
already holds on it, the closest page we have (extend it, or build new — the Growth lock forbids
thin duplicates), the tool the page would link, what must be verified before a word is written, and
a verdict. The brief is written to `brain/briefs/<id>.md`, the workflow opens a GitHub issue from
it, the scorecard lists it. Nothing is published from a brief: a brief is a research order, and the
research is still done by a person reading the law.

Gemini writes the angle (🔒 Gemini only, free tier, the shared quota ledger); when every model is
refused for the day the brief is still written from rules — question, sightings, shelf hits,
closest page — and marked so. Either way ₦0, and nothing on a schedule for the owner.

CLI: `python3 tools/page_briefs.py observe` (read the pull, keep sightings, draft what is due) ·
`show` · `scorecard`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import competitor_watch  # noqa: E402
import gemini_text  # noqa: E402 — 🔒 Gemini only; the shared quota ledger

LEDGER = Path(os.environ.get("DOCOGA_PAGE_BRIEFS") or (ROOT / "brain" / "page_briefs.json"))
BRIEF_DIR = Path(os.environ.get("DOCOGA_BRIEF_DIR") or (ROOT / "brain" / "briefs"))
SITEMAP = ROOT / "site" / "sitemap.xml"
SITE_URL = "https://docoga.com.ng"
TWICE = 2                 # sightings before a brief is drafted
MAX_BRIEFS_PER_RUN = 1    # one Gemini call a night at most — the planner's quota comes first
MAX_SIGHTINGS = 12
VERDICTS = ("build", "extend", "decline")

# Words that say nothing about the question. "nigeria", "lagos", "abuja" are where, not what.
STOP = set("""a an and the of to in on for with by from at as is are be how what when why which who do does much
can your my our you i it its this that these those vs or not no yes new best top guide tips step steps
things know need should must will all about into than then there here 2024 2025 2026 2027 nigeria nigerian
lagos abuja fct state states every any one get make use using without within ng""".split())


def now_utc():
    return datetime.now(timezone.utc)


def words(title):
    """Content words of a title, lightly stemmed, order kept, no duplicates."""
    out = []
    for w in re.findall(r"[a-z0-9']+", str(title or "").lower()):
        w = w.replace("'", "")
        if len(w) < 3 or w in STOP:
            continue
        for suf in ("ings", "ing", "ies", "ers", "er", "ed", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 4:
                w = w[: -len(suf)] + ("y" if suf == "ies" else "")
                break
        if w not in out:
            out.append(w)
    return out


def same_question(a, b):
    """Two titles ask the same question when they share at least two content words and half of
    the smaller set — "house for rent captions" and "how to advertise house for rent" do."""
    sa, sb = set(words(a)), set(words(b))
    if not sa or not sb:
        return False
    shared = sa & sb
    return len(shared) >= 2 and len(shared) >= 0.5 * min(len(sa), len(sb))


def key_for(title):
    return "-".join(words(title)[:4]) or "untitled"


# ── the ledger ─────────────────────────────────────────────────────────────────────────────────────
def load(path=None):
    p = Path(path or LEDGER)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("_comment", "Uncovered field questions kept across pulls; a brief is drafted the second time "
                                "one is seen (tools/page_briefs.py). Status: watching → briefed → built | declined.")
    data.setdefault("briefs", [])
    return data


def save(data, path=None):
    p = Path(path or LEDGER)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def observe(items=None, data=None, now=None):
    """Fold this pull's uncovered titles into the ledger. Returns the ledger; new sightings are
    counted only once per (competitor, title)."""
    now = now or now_utc()
    today = now.date().isoformat()
    data = data if data is not None else load()
    gaps = competitor_watch.gaps(items if items is not None else competitor_watch.load().get("items") or [])
    for g in gaps:
        title = g["title"].strip()
        if not words(title):
            continue
        # Every status matches — a declined question keeps absorbing its sightings instead of
        # becoming a fresh entry that is briefed again (10 Nov 2026: #214 declined at dawn, #216 opened
        # by the same run). A decline is revisited only when a *new* source asks the question.
        entry = next((e for e in data["briefs"] if
                      same_question(e["question"], title) or any(same_question(s["title"], title) for s in e["sightings"])), None)
        if entry is None:
            entry = {"id": key_for(title), "question": title, "status": "watching", "first_seen": today, "last_seen": today,
                     "sightings": [], "brief": None}
            if any(e["id"] == entry["id"] for e in data["briefs"]):
                entry["id"] += "-" + today.replace("-", "")[2:]
            data["briefs"].append(entry)
        seen = {(s["competitor"], s["title"].lower()) for s in entry["sightings"]}
        if (g["competitor"], title.lower()) not in seen and len(entry["sightings"]) < MAX_SIGHTINGS:
            entry["sightings"].append({"competitor": g["competitor"], "title": title, "published": g.get("published", ""), "seen": today})
            entry["last_seen"] = today
            if entry["status"] == "declined" and g["competitor"] not in {s["competitor"] for s in entry["sightings"][:-1]}:
                # asked again by a source that had not asked before: the question goes back to watching
                # and is briefed afresh at the next due() — the old decision stays on the entry as history.
                entry["status"] = "watching"
                entry["reopened"] = today
    return data


def due(data):
    """Entries seen at least twice that have no brief yet — oldest first."""
    rows = [e for e in data["briefs"] if e["status"] == "watching" and len(e["sightings"]) >= TWICE]
    return sorted(rows, key=lambda e: (e["first_seen"], e["id"]))


# ── what we already have: the shelf and the pages ──────────────────────────────────────────────────
PLACES = set("""lagos abuja fct rivers enugu kano oyo edo delta kaduna ogun plateau anambra kwara cross river
imo abia akwa ibom ondo osun ekiti kogi benue niger bauchi borno sokoto kebbi gombe jigawa katsina zamfara
yobe adamawa taraba nasarawa ebonyi bayelsa ibadan port harcourt benin kaduna ilorin jos uyo calabar owerri
asaba awka abeokuta warri onitsha aba""".split())


def page_words(text):
    """Content words for the closest-page test: words() plus the place names words() drops as stop
    words — "notice in Lagos" must be able to find notice-to-quit-lagos, not only the national page."""
    out = set(words(text))
    out |= {w for w in re.findall(r"[a-z]+", str(text or "").lower()) if w in PLACES}
    return out


def site_pages(sitemap=None):
    """[(slug, words)] for every page in the sitemap — the closest-page test reads the slug."""
    try:
        text = Path(sitemap or SITEMAP).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for loc in re.findall(r"<loc>\s*(\S+?)\s*</loc>", text):
        slug = loc.replace(SITE_URL, "").strip("/")
        if slug and not slug.endswith((".pdf", ".xml")):
            out.append((slug, page_words(re.sub(r"^guides/", "", slug).replace("-", " ").replace("/", " "))))
    return out


FORM = {"sample", "format", "template", "pdf", "free", "download", "guid", "guide", "index", "page"}


def closest_page(question, pages=None):
    """(slug, shared words) of the page that shares the most *telling* words with the question —
    ('', []) when no page stands close.

    12 Nov 2026 (🔒 Brain Growth): the first version counted shared words, so "house for rent
    captions nigeria" landed on rent-receipt-format-nigeria through the one word "rent" (shared by
    forty slugs) and "can landlord increase rent in enugu" tied rent-receipt-enugu with the rent-increase
    page and took the first in the sitemap. Now: each shared word is worth its rarity across our pages
    (log((N+1)/(df+1)) — "nigeria", "rent" and "tenancy" weigh little, "increase" and "caution" a lot);
    words that name a *kind* of page rather than a subject (FORM: sample, format, template …) weigh a
    third; place names count (page_words) and a page about another state is never the closest page;
    the best page must share at least one telling word — not a FORM word, not a place, not one that
    more than a sixth of our pages carry (unless the page is the question's own state's) — otherwise the honest answer is "no page stands close"; and a daily
    guide under guides/ yields to a top-level page that scores the same (the Growth lock says extend the
    page that ranks, not the day's note)."""
    import math
    pages = list(pages if pages is not None else site_pages())
    if not pages:
        return "", []
    qw = page_words(question)
    q_places = qw & PLACES
    n = len(pages)
    df = {}
    for _, pw in pages:
        for w in pw:
            df[w] = df.get(w, 0) + 1
    idf = {w: math.log((n + 1) / (c + 1)) for w, c in df.items()}
    common = max(2.0, n / 6.0)                 # a word more than one page in six carries proves nothing
    best, best_shared, best_score = "", [], 0.0
    for slug, pw in pages:
        shared = qw & pw
        if not shared:
            continue
        p_places = pw & PLACES
        if q_places and p_places and not (q_places & p_places):
            continue                                            # another state's page is never closest
        same_place = bool(q_places & p_places)
        telling = [w for w in shared if w not in FORM and w not in PLACES and (df[w] <= common or same_place)]
        if not telling:
            continue
        score = sum(idf[w] * (0.3 if w in FORM else 1.0) for w in shared)
        if slug.startswith("guides/"):
            score *= 0.85
        if p_places and not q_places:
            score *= 0.9                                        # a placeless question: the national page first
        if score > best_score + 1e-9 or (abs(score - best_score) <= 1e-9 and best and len(slug) < len(best)):
            best, best_shared, best_score = slug, sorted(shared), score
    return best, best_shared


COMMON = {"rent", "tenant", "landlord", "tenancy", "law", "notice", "agreement", "premise", "house", "pay", "year", "month"}


def shelf_hits(question, facts=None, top=6):
    """Shelf facts whose key or text carries the question's words — ids with cites, best first."""
    if facts is None:
        import law_index
        facts = law_index.all_facts()
    qw = set(words(question))
    scored = []
    for f in facts:
        fw = set(words(f.get("key", "").replace("_", " ") + " " + re.sub(r"<[^>]+>", " ", f.get("text", ""))))
        shared = qw & fw
        telling = shared - COMMON   # "rent" and "tenant" are on every fact; they prove nothing
        if len(telling) >= 2 or (telling and len(shared) >= 3):
            scored.append((len(shared), f["id"], f.get("cite", ""), f.get("state", "")))
    scored.sort(key=lambda r: (-r[0], r[1]))
    return [{"id": i, "cite": c, "state": s} for _, i, c, s in scored[:top]]


# ── the brief ──────────────────────────────────────────────────────────────────────────────────────
SYSTEM = ("You are DocOga's standing editor writing a RESEARCH BRIEF, not a page. DocOga (docoga.com.ng) makes "
          "Nigerian tenancy and workplace documents and every page cites the section of the state's law. "
          "Answer in JSON only.")


def brief_prompt(entry, hits, page, shared, tools, rivals):
    sightings = "\n".join("- %s (%s)" % (s["title"], s.get("published") or s["seen"]) for s in entry["sightings"])
    return (
        "The competition has written on a question DocOga has no page for — twice:\n%s\n\n"
        "What DocOga already holds on it: shelf facts %s; closest existing page: %s (shares the words %s).\n"
        "Tools a page can link (choose one): %s.\n\n"
        "Write the brief the owner will research from. Rules: never name a rival site, person or price "
        "(the names on the field are: %s); never state a figure, percentage or statistic — list what must be "
        "VERIFIED instead; a page that would repeat an existing page is not built — say \"extend\" and name it; "
        "a question outside tenancy, rent, landlords, tenants, agents or workplace documents is \"decline\". "
        "Return exactly: {\"verdict\": \"build\"|\"extend\"|\"decline\", \"reason\": one sentence, "
        "\"working_title\": ≤ 90 characters, a question or a promise in Nigerian English, "
        "\"the_question\": what the searcher is really asking, one sentence, "
        "\"who_asks\": \"tenant\"|\"landlord\"|\"agent\"|\"employer\"|\"employee\"|\"other\", "
        "\"angle\": the thing the rival titles cannot say, one or two sentences, "
        "\"verify\": 3 to 6 strings — each a specific law, section, form, fee or practice to read before writing, "
        "\"tool\": one of the tools, \"extend_page\": the slug to extend or \"\"}"
        % (sightings, ", ".join(h["id"] for h in hits) or "none", page or "none", ", ".join(shared) or "none",
           ", ".join(tools), ", ".join(rivals) or "none")
    )


GENERIC = {"blog", "templates", "solutions", "legal", "tenancy", "nigeria", "lawyer", "estate", "real", "the",
           "youtube", "tiktok", "youtube.com", "tiktok.com"}


def rival_names(field=None):
    """The brands a brief must never carry — the map's names and hosts, not the generic words
    after the dash ("tenancy agreement generator" is also what DocOga sells)."""
    names = []
    for comp in field if field is not None else competitor_watch.load_field():
        brand = re.split(r"[—–]", str(comp.get("name") or ""))[0].split(" (")[0].strip()
        first = brand.split()[0] if brand.split() else ""
        host = re.sub(r"^https?://(www\.)?", "", str(comp.get("url") or "")).split("/")[0]
        for n in (brand, first, host, host.split(".")[0] if host else ""):
            if len(n) >= 5 and n.lower() not in GENERIC:
                names.append(n)
    return sorted(set(names), key=len, reverse=True)


def lint(brief, tools, rivals):
    """Why a model's brief is refused — empty when it stands."""
    problems = []
    if not isinstance(brief, dict):
        return ["not an object"]
    if brief.get("verdict") not in VERDICTS:
        problems.append("verdict must be build, extend or decline")
    title = str(brief.get("working_title") or "").strip()
    if brief.get("verdict") != "decline" and not (8 <= len(title) <= 90):
        problems.append("working_title missing or over 90 characters")
    verify = brief.get("verify")
    if brief.get("verdict") != "decline" and not (isinstance(verify, list) and 3 <= len([v for v in verify if str(v).strip()]) <= 6):
        problems.append("verify must list 3 to 6 things to read")
    if brief.get("verdict") != "decline" and brief.get("tool") not in tools:
        problems.append("tool must be one of the generator's tools")
    if brief.get("verdict") == "extend" and not str(brief.get("extend_page") or "").strip():
        problems.append("extend needs the page slug")
    corpus = " ".join(str(brief.get(k) or "") for k in ("working_title", "the_question", "angle", "reason")) + " " + \
        " ".join(str(v) for v in (verify or []) if isinstance(verify, list))
    low = corpus.lower()
    for name in rivals:
        if name.lower() in low:
            problems.append("names a rival: %s" % name)
            break
    if re.search(r"\d+(\.\d+)?\s?%|₦\s?\d|\b\d{1,3}(,\d{3})+\b|\bper ?cent\b", corpus):
        problems.append("a figure or statistic in a brief — list it under verify instead")
    return problems


def rules_brief(entry, hits, page, shared, tools):
    """The brief when no model answers: honest, from what the ledger and the shelf know."""
    qw = words(entry["question"])
    tool = "tenancy-agreement"
    for needle, t in (("receipt", "rent-receipt"), ("quit", "notice-to-quit"), ("evict", "notice-to-quit"),
                      ("caution", "caution-fee"), ("deposit", "caution-fee"), ("arrear", "letter-of-demand"),
                      ("demand", "letter-of-demand"), ("increase", "rent-review"), ("review", "rent-review"),
                      ("right", "tenant-rights"), ("salary", "payslip"), ("payslip", "payslip"),
                      ("employ", "employment-contract"), ("invoice", "invoice"), ("warning", "warning-letter"),
                      ("attorney", "power-of-attorney")):
        if any(needle in w for w in qw) and t in tools:
            tool = t
            break
    verdict = "extend" if len(shared) >= 2 else "build"
    return {"verdict": verdict,
            "reason": "drafted from rules — no model answered today; the field asked this %d times" % len(entry["sightings"]),
            "working_title": entry["question"][:90],
            "the_question": entry["question"],
            "who_asks": "other",
            "angle": "Answer it with the section of the state's law, which the titles on the field do not cite.",
            "verify": ["which state law governs the question, by section", "whether any pending bill touches it",
                       "what the closest DocOga page already says", "what a reader can lawfully do about it today"],
            "tool": tool, "extend_page": page if verdict == "extend" else ""}


def draft(entry, http=None, sleep=None, log=print, facts=None, pages=None, field=None, tools=None):
    """Draft one brief: shelf hits and closest page from rules, the angle from Gemini, gates on top.
    Returns (brief, drafted_by)."""
    import brain_drafts
    tools = list(tools or brain_drafts.TOOLS)
    rivals = rival_names(field)
    hits = shelf_hits(entry["question"], facts=facts)
    page, shared = closest_page(entry["question"], pages=pages)
    brief, by = None, "rules"
    try:
        for attempt in (1, 2):
            raw = gemini_text.generate_json(brief_prompt(entry, hits, page, shared, tools, rivals), system=SYSTEM,
                                            http=http, sleep=sleep, log=log, lane="briefs", temperature=0.6,
                                            max_output_tokens=2048)
            problems = lint(raw, tools, rivals)
            if not problems:
                brief, by = raw, "gemini"
                break
            log("briefs: attempt %d refused — %s" % (attempt, "; ".join(problems)))
    except gemini_text.Exhausted as exc:
        log("briefs: quota — %s; writing the brief from rules" % exc)
    except Exception as exc:  # noqa: BLE001 — a brief must never stop the night
        log("briefs: model failed (%s); writing the brief from rules" % str(exc)[:120])
    if brief is None:
        brief = rules_brief(entry, hits, page, shared, tools)
    brief = {k: brief.get(k) for k in ("verdict", "reason", "working_title", "the_question", "who_asks", "angle",
                                       "verify", "tool", "extend_page")}
    brief["shelf"] = hits
    brief["closest_page"] = page
    return brief, by


def render(entry):
    """The markdown the owner reads (brain/briefs/<id>.md and the issue body)."""
    b = entry["brief"] or {}
    lines = ["# Page brief: %s" % (b.get("working_title") or entry["question"]),
             "",
             "**Verdict:** %s — %s" % (b.get("verdict", "?"), b.get("reason", "")),
             "**Drafted:** %s by %s · first seen %s · seen %d time(s) on the field" % (
                 entry.get("briefed_at", "")[:10], entry.get("drafted_by", "rules"), entry["first_seen"], len(entry["sightings"])),
             "",
             "## The question", b.get("the_question") or entry["question"], "",
             "**Who asks:** %s · **Tool the page links:** `%s`" % (b.get("who_asks", "other"), b.get("tool", "")),
             "",
             "## The angle the field cannot take", b.get("angle") or "", ""]
    if b.get("verdict") == "extend" and b.get("extend_page"):
        lines += ["## Extend, do not duplicate", "`%s/%s` already stands closest — add the answer there (🔒 Growth lock: no thin duplicates)." % (SITE_URL, b["extend_page"]), ""]
    elif b.get("closest_page"):
        lines += ["## Closest page we have", "`%s/%s` — check it before building." % (SITE_URL, b["closest_page"]), ""]
    lines += ["## Verify before writing a word"] + ["- [ ] %s" % v for v in (b.get("verify") or [])] + [""]
    if b.get("shelf"):
        lines += ["## Already on the law shelf"] + ["- `%s` — %s (%s)" % (h["id"], h["cite"], h["state"]) for h in b["shelf"]] + [""]
    lines += ["## What the field wrote (titles only — never copied)"] + \
             ["- %s (%s)" % (s["title"], s.get("published") or s["seen"]) for s in entry["sightings"]] + \
             ["", "_A brief is a research order, not a page. Nothing is published from it until the law is read._"]
    return "\n".join(lines) + "\n"


def run(items=None, data=None, now=None, http=None, sleep=None, log=print, out_dir=None, facts=None,
        pages=None, field=None, max_briefs=MAX_BRIEFS_PER_RUN, dry_run=False):
    """observe → draft what is due → write files. Returns (ledger, [paths written])."""
    now = now or now_utc()
    data = observe(items=items, data=data, now=now)
    written = []
    for entry in due(data)[:max_briefs]:
        brief, by = draft(entry, http=http, sleep=sleep, log=log, facts=facts, pages=pages, field=field)
        entry["brief"], entry["drafted_by"], entry["briefed_at"] = brief, by, now.isoformat(timespec="seconds")
        entry["status"] = "declined" if brief.get("verdict") == "decline" else "briefed"
        log("briefs: %s → %s (%s): %s" % (entry["id"], brief.get("verdict"), by, brief.get("working_title")))
        if entry["status"] == "briefed" and not dry_run:
            path = Path(out_dir or BRIEF_DIR) / (entry["id"] + ".md")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(entry), encoding="utf-8")
            written.append(path)
    if not dry_run:
        save(data)
    return data, written


# ── reading it back ────────────────────────────────────────────────────────────────────────────────
def scorecard_lines(data=None):
    data = data if data is not None else load()
    rows = data.get("briefs") or []
    if not rows:
        return ["- no uncovered field question seen twice yet — nothing to brief"]
    lines = []
    for e in rows:
        if e["status"] == "briefed":
            lines.append("- 📝 page brief: %s — %s; seen %d× on the field; brain/briefs/%s.md"
                         % ((e["brief"] or {}).get("working_title") or e["question"], (e["brief"] or {}).get("verdict"), len(e["sightings"]), e["id"]))
        elif e["status"] == "built":
            lines.append("- ✅ built: %s" % ((e["brief"] or {}).get("working_title") or e["question"]))
    for e in rows:
        if e["status"] == "watching":
            lines.append("- watching: \"%s\" — seen %d× (brief at %d)" % (e["question"][:70], len(e["sightings"]), TWICE))
    declined = [e for e in rows if e["status"] == "declined"]
    if declined:
        lines.append("- declined: %s" % "; ".join("\"%s\"" % e["question"][:50] for e in declined[:4]))
    return lines


def decisions(data=None):
    """Briefed questions the editor has since decided (status declined or built, with a `decision`):
    the workflow closes their issues with the reason. One tab-separated line each: title, status, reason."""
    data = data if data is not None else load()
    out = []
    for e in data.get("briefs") or []:
        dec = e.get("decision") or {}
        if e.get("status") in ("declined", "built") and dec.get("reason") and e.get("brief"):
            title = "Page brief: %s" % ((e["brief"] or {}).get("working_title") or e["question"])
            out.append("%s\t%s\t%s" % (title, e["status"], " ".join(str(dec["reason"]).split())))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Page briefs — the field writes the research list")
    sub = ap.add_subparsers(dest="cmd")
    o = sub.add_parser("observe")
    o.add_argument("--dry-run", action="store_true")
    sub.add_parser("show")
    sub.add_parser("scorecard")
    sub.add_parser("decisions")
    args = ap.parse_args(argv)
    if args.cmd == "decisions":
        for line in decisions():
            print(line)
        return 0
    if args.cmd == "observe":
        data, written = run(dry_run=args.dry_run)
        print("PAGE_BRIEFS_NEW=%d" % len(written))
        for p in written:
            print("brief: %s" % p)
        return 0
    if args.cmd in ("show", "scorecard"):
        print("\n".join(scorecard_lines()))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
