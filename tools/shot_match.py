#!/usr/bin/env python3
"""shot_match.py — the photograph behind the words, chosen to MATCH the words.

Owner, 17 Oct 2026: "You can use free images and video clips in video … behind the cards —
make sure it matches what is being said." Until now a Deep-Dive beat picked one of eighteen
fixed plates in episodes/assets/, a Short sat on the plain navy, and a card only had a photo
when the brain asked for one. This module is the single place where *what is being said*
becomes *what is shown*, for every renderer:

    query_for(text, hint)        → "paper receipt handwriting"   (what to look for)
    relevant(candidate, query)   → True/False                    (does the result match?)
    photo_for(text, hint, size)  → PIL image or None             (fetched, matched, cached)

Where the pictures come from — ₦0, no key, no attribution debt:
  * Openverse (api.openverse.org) filtered to CC0 / public-domain, via tools/brain_visual.py,
    which already knows the exclusions (no faces, no signs, no logos). Anonymous access is
    ~20 requests a minute, so searches are spaced (`PACE_S`) and cached per query under
    assets/plates/ — a 40-beat episode asks for far fewer than 40 distinct pictures.
  * Video clips: Pexels has paused new keys, Openverse indexes no video, and Pixabay's free
    video API needs a key the owner has not minted — so clips are documented as the next
    step (docs/BRAIN.md) and stills with camera drift carry the motion today.

How "matches what is being said" is enforced, not hoped for:
  1. The brain (Gemini, locked) may name a `shot` for each beat — 2–4 plain words describing
     the photograph the sentence calls for. That is the first query.
  2. Without a hint, `query_for` reads the words themselves: a DocOga-domain glossary maps the
     nouns a tenant hears (receipt, caution fee, quit notice, court, landlord, danfo …) to a
     concrete, photographable subject — the THING said beats the place, the place beats the
     role. Rotation posts and paused-brain days therefore still get a matching picture, never
     a random one.
  3. Every Openverse result is scored against the query's content words (title + tags). A
     result that shares no word with the query is rejected, however pretty. Two misses →
     the next, broader query in the chain (subject → setting → None).
  4. None is an answer. The renderer keeps its navy/plate fallback; a post is never late and
     never wrong because of a picture.

    DOCOGA_SHOTS=on     the lanes set this (repo variable DOCOGA_SHOTS=off is the kill switch);
                        unset = off, so a unit test or an air-gapped run never touches the network
    BRAIN_PLATES=off    (brain_visual) never fetch at all
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

PACE_S = 3.2            # Openverse anonymous: ~20 searches/minute
_last_search = [0.0]

# The glossary: what a tenant hears → what a camera can show. Three tiers, because a sentence
# usually names a THING, a SETTING and a ROLE at once ("the landlord must give you a receipt in
# Lagos") and the thing is what the picture should show: objects (3) beat places (2) beat roles
# and generic nouns (1); within a tier the longer phrase wins ("caution fee" over "fee"), then
# the earlier mention. Every subject is a thing or a place, never a person (brain_visual.EXCLUDE
# and brain.PLATE_BANNED keep faces out of the frame).
_OBJECTS = [
    ("quit notice", "padlocked door"), ("notice to quit", "padlocked door"), ("eviction", "padlocked door"),
    ("caution fee", "naira banknotes"), ("caution deposit", "naira banknotes"), ("security deposit", "naira banknotes"),
    ("agency fee", "naira banknotes"), ("agent fee", "naira banknotes"), ("legal fee", "naira banknotes"),
    ("service charge", "electricity meter"), ("stamp duty", "rubber stamp document"),
    ("tenancy agreement", "contract signature pen"), ("lease agreement", "contract signature pen"),
    ("agreement", "contract signature pen"), ("contract", "contract signature pen"),
    ("rent receipt", "paper receipt"), ("receipt", "paper receipt"), ("invoice", "invoice paper calculator"),
    ("payslip", "payslip calculator desk"), ("affidavit", "courthouse columns"),
    ("witness", "pen signature paper"), ("signature", "pen signature paper"), ("sign", "pen signature paper"),
    ("whatsapp", "smartphone hand message"), ("sms", "smartphone hand message"), ("text message", "smartphone hand message"),
    ("phone", "smartphone hand message"), ("email", "laptop keyboard"), ("transfer", "atm card bank"),
    ("pos", "pos terminal card"), ("cash", "naira banknotes"), ("naira", "naira banknotes"), ("money", "naira banknotes"),
    ("deposit", "naira banknotes"), ("refund", "naira banknotes"), ("salary", "naira banknotes"), ("wages", "naira banknotes"),
    ("key", "house keys"), ("keys", "house keys"), ("lock", "padlocked door"), ("locked", "padlocked door"),
    ("lockout", "padlocked door"), ("padlock", "padlocked door"),
    ("roof", "roof rain sheets"), ("leak", "roof rain sheets"), ("repair", "hand tools repair"),
    ("plumber", "water pipe tap"), ("water", "water tap"), ("borehole", "water tap"),
    ("electricity", "electricity meter"), ("nepa", "electricity meter"), ("meter", "electricity meter"),
    ("generator", "petrol generator"), ("fuel", "petrol generator"),
    ("calendar", "wall calendar"), ("deadline", "wall calendar"), ("six months", "wall calendar"),
    ("letter", "envelope letter paper"), ("document", "paper documents stack"), ("photocopy", "paper documents stack"),
    ("gavel", "wooden gavel"), ("judge", "wooden gavel"), ("lawyer", "law books shelf"),
    ("ankara", "ankara fabric pattern"), ("sewing", "sewing machine fabric"), ("tailor", "sewing machine fabric"),
    ("danfo", "yellow bus lagos"), ("keke", "tricycle street"), ("okada", "motorcycle street"),
    ("wedding", "wedding rings"), ("celebrat", "confetti celebration"), ("party", "confetti celebration"),
]
_PLACES = [
    ("magistrate", "courthouse columns"), ("tribunal", "courthouse columns"), ("court", "courthouse columns"),
    ("police", "police station building"), ("bank", "bank building atm"), ("market", "market stall nigeria"),
    ("shop", "shop kiosk street"), ("kiosk", "shop kiosk street"), ("workshop", "workshop tools"),
    ("estate", "housing estate street"), ("compound", "house gate compound"), ("flat", "apartment building balcony"),
    ("apartment", "apartment building balcony"), ("self contain", "empty room window"), ("room", "empty room window"),
    ("house", "house gate compound"), ("door", "wooden door"), ("school", "school classroom desks"),
    ("hospital", "hospital corridor"), ("church", "church building"), ("mosque", "mosque minaret"),
    ("port harcourt", "port harcourt waterfront"), ("rivers state", "port harcourt waterfront"),
    ("lagos", "lagos skyline bridge"), ("abuja", "abuja city skyline"), ("kano", "kano city wall"),
    ("ibadan", "ibadan rooftops"), ("enugu", "enugu hills"), ("bridge", "lagos skyline bridge"),
    ("traffic", "lagos traffic road"), ("road", "lagos traffic road"), ("street", "lagos street nigeria"),
    ("night", "city lights dusk"), ("dusk", "city lights dusk"), ("morning", "sunrise rooftops"),
]
_ROLES = [
    ("landlord", "house gate compound"), ("landlady", "house gate compound"), ("caretaker", "house gate compound"),
    ("agent", "housing estate street"), ("tenant", "apartment building balcony"), ("rent", "apartment building balcony"),
    ("trader", "market stall nigeria"), ("artisan", "workshop tools"), ("mechanic", "workshop tools"),
    ("pay", "naira banknotes"), ("month", "wall calendar"), ("year", "wall calendar"), ("january", "wall calendar"),
    ("date", "wall calendar"), ("paper", "paper documents stack"), ("file", "paper documents stack"),
    ("record", "paper documents stack"), ("law", "law books shelf"), ("section", "law books shelf"),
    ("right", "law books shelf"), ("nigeria", "lagos street nigeria"), ("bus", "yellow bus lagos"),
]
GLOSSARY = ([(k, v, 3) for k, v in _OBJECTS] + [(k, v, 2) for k, v in _PLACES] + [(k, v, 1) for k, v in _ROLES])

SETTING = "lagos street nigeria"     # the broad fallback: still Nigeria, never a stock desk in Ohio

STOP = set("""a an the and or of to in on at for by with from as is are was were be been it its this that
these those your you we our us they them their he she his her i me my not no yes do does did
have has had will would can could should may might must than then there here what which who
when where why how all any each every some more most other such only own same so too very
just also into over under again further once up down out off about above below between
through during before after while because until against both few nor""".split())

STEM_CUT = ("ings", "ing", "ers", "ies", "es", "s", "ed", "er")


def _words(text):
    return [w for w in re.findall(r"[a-z0-9]+", str(text or "").lower()) if w not in STOP and len(w) > 2]


def _stem(w):
    for cut in STEM_CUT:
        if w.endswith(cut) and len(w) - len(cut) >= 3:
            return w[: -len(cut)]
    return w


def enabled():
    """Explicitly on, never implicitly: every publishing workflow passes DOCOGA_SHOTS
    (`vars.DOCOGA_SHOTS || 'on'`); nothing else — tests, `qa.py`, a laptop — reaches Openverse."""
    return os.environ.get("DOCOGA_SHOTS", "").strip().lower() in ("on", "1", "true", "yes")


def subject_for(text):
    """The glossary subject the words call for, or None. Longest phrase wins; first hit by
    position breaks ties between phrases of equal specificity ("receipt … court" → receipt)."""
    low = " " + re.sub(r"[^a-z0-9₦ ]+", " ", str(text or "").lower()) + " "
    low = re.sub(r"\s+", " ", low)
    if "₦" in str(text or ""):
        low += " naira "
    best = None
    for phrase, subject, weight in GLOSSARY:
        # Whole words — " pos" must not fire on "possible". Phrases of seven letters or more may
        # take a plural/verb tail (receipts, agreements, celebrating), short ones are exact.
        tail = "" if len(phrase) >= 7 else "(?![a-z0-9])"
        m = re.search(r"(?<![a-z0-9])%s%s" % (re.escape(phrase), tail), low)
        if not m:
            continue
        rank = (weight, len(phrase), -m.start())
        if best is None or rank > best[0]:
            best = (rank, subject)
    return best[1] if best else None


def query_chain(text, hint=None):
    """Queries to try in order: the brain's hint, the glossary subject, the setting. Deduplicated,
    never empty — the last entry is always the Nigerian street, so the chain ends somewhere real."""
    chain = []
    hint = " ".join(str(hint or "").split()).lower()
    if hint and len(hint.split()) <= 5:
        chain.append(hint)
    subject = subject_for(text)
    if subject:
        chain.append(subject)
    chain.append(SETTING)
    out = []
    for q in chain:
        if q not in out:
            out.append(q)
    return out


def query_for(text, hint=None):
    return query_chain(text, hint)[0]


def relevant(candidate, query):
    """Does this Openverse result show what the query asked for? Title + tags must share at least
    one content word (stemmed) with the query. 'IMG_2041.jpg' with no tags is a no."""
    have = {_stem(w) for w in _words(" ".join([str(candidate.get("title") or ""),
                                                 str(candidate.get("tags_text") or "")]))}
    want = {_stem(w) for w in _words(query)}
    return bool(have & want)


def _pace():
    wait = PACE_S - (time.monotonic() - _last_search[0])
    if wait > 0:
        time.sleep(wait)
    _last_search[0] = time.monotonic()


def pick(query, http=None, sleeper=None):
    """(candidate, note): the first RELEVANT Openverse candidate for `query`, or (None, why)."""
    import brain_visual
    if not brain_visual.enabled():
        return None, "plates off"
    (sleeper or _pace)()
    candidates, note = brain_visual.search(query, http=http)
    kept = [c for c in candidates if relevant(c, query)]
    if not kept:
        return None, "no relevant result for %r (%s)" % (query, note)
    return kept[0], "%d relevant of %s" % (len(kept), note)


def photo_for(text, hint=None, size=None, http=None, sleeper=None, treat=None):
    """The matched photograph for what is being said: a PIL RGB image (treated with `treat(img,
    size)` when given, else brain_visual.treat) or None. Never raises."""
    if not enabled():
        return None, "shots off"
    try:
        import brain_visual
        for query in query_chain(text, hint):
            cand, note = pick(query, http=http, sleeper=sleeper)
            if cand is None:
                continue
            img, prov = brain_visual.fetch_candidate(cand, query, http=http)
            if img is None:
                continue
            if size:
                img = (treat or brain_visual.treat)(img, size)
            return img, {"query": query, **(prov or {})}
        return None, "nothing matched"
    except Exception as exc:  # a picture must never cost the video
        return None, "error: %s" % exc


if __name__ == "__main__":
    for line in sys.argv[1:] or ["The landlord must give you a receipt — Lagos Tenancy Law s.5"]:
        print("%-60s → %s" % (line[:60], " | ".join(query_chain(line))))
