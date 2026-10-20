#!/usr/bin/env python3
"""
WORDSYNC — when does the narrator say each word of a Short?

The owner (20 Oct 2026): "text motion graphics over the image as the voice-over speaks …
images that explain what the voice-over is saying per time". Both need the time of every
word, and Gemini TTS returns audio only. Two engines, one shape:

  vosk      the Deep-Dive's forced alignment (tools/deepdive.py: Kaldi small-English model,
            SequenceMatcher against the script) — the real timings, used on the publish lanes
            where tools/install_wordsync_deps.sh put the model under /tmp/vosk.
  estimate  the script alone: each word weighs its letters (+ a pause after punctuation), the
            clip's measured seconds are shared out in proportion. Honest to within ~150 ms on
            a 12-word sentence — what a laptop without the model, and the tests, get.

Output per clip: [{"d": "receipt,", "t0": 1.23, "t1": 1.58}, …] in clip seconds, one entry per
DISPLAY word (whitespace-split, punctuation kept — the caption shows "₦50,000," not "50 000").
`sentence_spans` then cuts that list where tools/shorts_sound.sentences() cuts the text, so each
caption sentence owns its words and the shot behind it knows when it starts.

Never raises on the publish path: a failed alignment falls back to the estimate and says so
(`engine`), and the lane prints WORDSYNC=<engine> for the run summary.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAUSE_AFTER = {",": 0.9, ";": 1.1, ":": 1.1, ".": 1.6, "!": 1.6, "?": 1.6, "—": 1.0, "–": 1.0}
LEAD_S = 0.08          # a word lights 80 ms before it is heard — reading is faster than listening
MIN_WORD_S = 0.12


# ───────────────────────────── tokens ─────────────────────────────
def display_words(text):
    """Whitespace words with their punctuation, the way the caption prints them."""
    return [w for w in str(text or "").split() if w]


def norm_tokens(text):
    """The alignable tokens of a text — same rule as tools/deepdive.norm_tokens."""
    t = str(text or "").lower().replace("\u2014", " ").replace("\u2013", " ").replace("-", " ")
    t = re.sub(r"[^a-z0-9' ]", " ", t)
    return [w for w in t.split() if w]


def _weight(word):
    """How long a word takes to say, in letters: letters + a pause for the punctuation it ends on."""
    letters = len(re.sub(r"[^A-Za-z0-9₦]", "", word))
    if letters == 0:
        return 0.6
    digits = sum(ch.isdigit() for ch in word)
    w = letters + 0.9 + 1.4 * digits          # "50,000" is read as five words; digits are slow
    for ch in reversed(word):
        if ch in PAUSE_AFTER:
            w += PAUSE_AFTER[ch] * 2.2
            break
        if ch.isalnum():
            break
    return w


# ───────────────────────────── engines ─────────────────────────────
def estimate(text, seconds, lead_in=0.06, tail=0.10):
    """Word times from pace alone: the clip's seconds shared by letter weight. Monotonic, inside
    [lead_in, seconds - tail], every word at least MIN_WORD_S."""
    words = display_words(text)
    if not words:
        return []
    seconds = max(float(seconds or 0.0), MIN_WORD_S * len(words) + lead_in + tail)
    span = seconds - lead_in - tail
    weights = [_weight(w) for w in words]
    total = sum(weights) or 1.0
    out, t = [], lead_in
    for w, wt in zip(words, weights):
        d = max(MIN_WORD_S, span * wt / total)
        out.append({"d": w, "t0": round(t, 3), "t1": round(min(seconds - tail, t + d * 0.88), 3)})
        t += d
    return out


def _vosk_ready():
    try:
        import deepdive
        return deepdive.vosk_available()
    except Exception:
        return False


def align(clip_path, text):
    """Real word times through the Deep-Dive's Vosk alignment, mapped back onto display words.
    Returns None when Vosk is not here or heard nothing usable."""
    if not _vosk_ready():
        return None
    import deepdive
    try:
        heard = deepdive.asr_words(clip_path)
    except Exception:
        return None
    if len(heard) < 2:
        return None
    toks = deepdive.align_section(0, text, heard)     # one entry per norm token, in script order
    if not toks:
        return None
    times = [(float(t["t0"]), float(t["t1"])) for t in toks]
    out, i = [], 0
    for w in display_words(text):
        n = len(norm_tokens(w))
        if n == 0:                                     # "—" alone: ride on the previous word
            if out:
                out.append({"d": w, "t0": out[-1]["t0"], "t1": out[-1]["t1"]})
            continue
        seg = times[i:i + n] or [times[-1]]
        i += n
        out.append({"d": w, "t0": round(seg[0][0], 3), "t1": round(max(seg[-1][1], seg[0][0] + MIN_WORD_S), 3)})
    # monotonic, no overlaps — ASR can hand back a word that starts before the previous ended
    for a, b in zip(out, out[1:]):
        if b["t0"] < a["t1"]:
            mid = round((a["t1"] + b["t0"]) / 2, 3)
            a["t1"], b["t0"] = mid, mid
    return out


def words_for(clip_path, text, seconds):
    """(words, engine) for one narration clip — Vosk when it is installed, else the estimate."""
    words = align(clip_path, text) if clip_path else None
    if words and len(words) == len(display_words(text)):
        return words, "vosk"
    return estimate(text, seconds), "estimate"


# ───────────────────────────── sentences ─────────────────────────────
def sentence_spans(words, sentences):
    """Cut `words` into one list per sentence (the sentences come from shorts_sound.sentences()
    on the same text, so their display words concatenate to the clip's). Returns [[word…], …]."""
    out, i = [], 0
    for s in sentences:
        n = len(display_words(s))
        out.append(words[i:i + n])
        i += n
    if i < len(words) and out:          # a split that disagreed by a word: the last sentence keeps it
        out[-1] += words[i:]
    return out


_PHRASE_END = (",", ";", ":", "—", "–", ".", "!", "?")


def _phrases(words):
    """Split at the punctuation the narrator pauses on — a phrase is what the ear hears as one."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if w["d"].rstrip("'\")”") [-1:] in _PHRASE_END:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _balanced(phrase, max_words, max_chars):
    """A phrase too long for one card, cut into near-equal pieces (never a lone dangling word)."""
    def fits(p):
        return len(p) <= max_words and sum(len(w["d"]) for w in p) + len(p) - 1 <= max_chars
    if fits(phrase):
        return [phrase]
    n = len(phrase)
    for pieces in range(2, n + 1):
        size = -(-n // pieces)
        if size == 1 and n > 2:
            continue
        cut = [phrase[i:i + size] for i in range(0, n, size)]
        if len(cut[-1]) == 1 and len(cut) > 1 and len(cut[-2]) < size + 2:
            cut[-2] += cut.pop()
        if all(fits(p) for p in cut) or pieces == n:
            return cut
    return [phrase]


FUNCTION_WORDS = set("a an the and or but of to in on at for by with from as your you it its this that is are "
                     "be was were not no if so than then when who what".split())


def _no_dangling(chunks, max_words, max_chars):
    """A phrase should not end on 'the' / 'your' / 'and' when the next phrase can open with it —
    the eye reads "Collect the receipt" / "the day you pay", never "receipt the" / "day you pay"."""
    def fits(p):
        return len(p) <= max_words and sum(len(w["d"]) for w in p) + len(p) - 1 <= max_chars
    for i in range(len(chunks) - 1):
        a, b = chunks[i], chunks[i + 1]
        while len(a) > 1 and a[-1]["d"].lower().strip(".,;:!?") in FUNCTION_WORDS and fits([a[-1]] + b):
            b.insert(0, a.pop())
    return chunks


def chunk(words, max_words=4, max_chars=24):
    """Group a sentence's words into the short phrases a caption shows at once: cut first at
    the punctuation the voice pauses on, then balance anything longer than `max_words` (or
    `max_chars` letters) into equal pieces — the eye reads a phrase, the ear hears it, both
    finish together. Never a lone dangling word when it can join its neighbour."""
    chunks = []
    for ph in _phrases(words):
        chunks += _balanced(ph, max_words, max_chars)
    chunks = _no_dangling(chunks, max_words, max_chars)
    merged = []
    for c in chunks:
        if merged and len(c) == 1 and len(merged[-1]) + 1 <= max_words \
                and sum(len(w["d"]) for w in merged[-1] + c) + len(merged[-1]) <= max_chars:
            merged[-1] = merged[-1] + c
        else:
            merged.append(c)
    return merged


if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) or "Pay without a receipt, and you pay twice. Keep the paper."
    for w in estimate(text, 4.0):
        print("%5.2f–%5.2f  %s" % (w["t0"], w["t1"], w["d"]))
    print([[w["d"] for w in c] for c in chunk(estimate(text, 4.0))])
