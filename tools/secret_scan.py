#!/usr/bin/env python3
"""
tools/secret_scan.py — the gate that keeps a public repository public-safe
==========================================================================

Why this exists (20 Oct 2026, 9:50pm WAT): the free Actions allowance of a *private* repo ran dry
(2,000 min/month) and every lane stopped. The ₦0 fix is a public repository — unlimited Actions
minutes — which is only safe if nothing secret is in the tree. The audit that night found two
things that had been committed as if the repo would stay private forever: a live Telegram bot
token in a stray test script, and the real vault key pasted into a unit-test fixture. Both were
rotated. This scan is the promise that it never happens a third time: it runs inside
`tools/qa.py` (so a PR cannot go green with a credential in it) and it is a one-liner to run by
hand.

What it looks for — *shapes*, not names, because a secret never announces itself:

    Telegram bot token        123456789:AA…(35)          — the only shape BotFather issues
    Google API key            AIza…(35)
    Google OAuth refresh/code 1//0…  ·  4/0A…
    Google access token       ya29.…
    Meta user/page token      EAA…(60+)   ·  IGAA… / IGQ…(40+)   ·  Threads TH…(40+)
    GitHub tokens             ghp_… · github_pat_… · gho_… · ghs_…
    TikTok tokens             act.… · rft.…
    Flutterwave / Paystack    FLWSECK- · FLWPUBK- · sk_live_ · sk_test_ · pk_live_
    Private keys              -----BEGIN … PRIVATE KEY-----
    A 64-hex vault key        anywhere outside `tools/token_vault.py`'s own docs — the real
                              SOCIAL_TOKEN_KEY is 32 random bytes as hex; test fixtures must use
                              an obviously fake pattern ("0f" * 32) so the scan can tell them apart.

What it deliberately ignores: `*.box` files (ciphertext, useless without the key — that is the
vault's whole design), lock files and minified bundles (sha512 integrity strings), SVG/fonts, and
the git objects themselves. It scans **tracked files only** (`git ls-files`), because an untracked
scratch file is not a leak; a committed one is.

Exit 0 = clean. Exit 1 = findings, each printed as `path:line: <shape> <first 6 chars>…` — the
value is never echoed in full, so the scan's own output can be pasted into an issue.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SHAPES = [
    ("telegram bot token", re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("google refresh token / auth code", re.compile(r"\b1//0[0-9A-Za-z_-]{30,}|\b4/0A[0-9A-Za-z_-]{30,}")),
    ("google access token", re.compile(r"\bya29\.[0-9A-Za-z_-]{30,}")),
    ("meta access token", re.compile(r"\bEAA[0-9A-Za-z]{60,}|\bIG(?:AA|Q)[0-9A-Za-z_-]{40,}|\bTH[A-Z]{2}[0-9A-Za-z_-]{40,}")),
    ("github token", re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("tiktok token", re.compile(r"\b(?:act|rft)\.[A-Za-z0-9!_-]{30,}")),
    ("payment key", re.compile(r"\bFLW(?:SECK|PUBK)(?:_TEST)?-[A-Za-z0-9-]{20,}|\b[sp]k_(?:live|test)_[A-Za-z0-9]{20,}")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----")),
    ("64-hex vault key", re.compile(r"(?<![0-9a-fA-F])[0-9a-f]{64}(?![0-9a-fA-F])")),
]

# Paths the scan never reads: ciphertext, lockfiles, binaries, vendored bundles.
SKIP_SUFFIX = {".box", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".mp3", ".mp4", ".wav",
               ".ogg", ".ttf", ".otf", ".woff", ".woff2", ".svg", ".pdf", ".zip", ".jar", ".keystore"}
SKIP_NAME = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "gradle-wrapper.jar"}
SKIP_DIRS = ("node_modules/", ".git/")

# Values that look like a shape but are known fakes used by tests/docs. Keep this list short and
# obviously fake; a real value must never be allow-listed — rotate it instead.
ALLOW = {
    "123456789:AAH4k-testtokenvalueaaaaaaaaaaaaaaa",
    "0f" * 32, "00" * 32, "ab" * 32, "11" * 32, "0123456789abcdef" * 4,
}
# A 64-hex string is also what a git commit SHA-256 or a sha256 digest looks like; those live in
# lines that say so. Skip lines that name a hash explicitly.
HASH_LINE = re.compile(r"sha-?256|sha256sum|_sha\b|\bsha\b|integrity|digest|commit|checksum|hash|fingerprint", re.I)


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True)
    return [p for p in out.stdout.split("\0") if p]


def scan_text(path, text):
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, rx in SHAPES:
            for m in rx.finditer(line):
                value = m.group(0)
                if value in ALLOW:
                    continue
                if label == "64-hex vault key" and HASH_LINE.search(line):
                    continue
                if label == "64-hex vault key" and len(set(value)) <= 2:
                    continue  # "0000…" / "ffff…" style placeholders
                findings.append((path, lineno, label, value[:6] + "…"))
    return findings


def scan(paths=None):
    findings = []
    for rel in (paths if paths is not None else tracked_files()):
        if any(rel.startswith(d) or ("/" + d) in rel for d in SKIP_DIRS):
            continue
        p = Path(rel)
        if p.suffix.lower() in SKIP_SUFFIX or p.name in SKIP_NAME:
            continue
        full = ROOT / rel
        if not full.is_file():
            continue
        try:
            text = full.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(scan_text(rel, text))
    return findings


def main(argv):
    findings = scan(argv[1:] or None)
    for path, lineno, label, head in findings:
        print("%s:%d: %s %s" % (path, lineno, label, head))
    if findings:
        print("secret_scan: %d finding(s) — rotate the value, then remove it; never allow-list a real one"
              % len(findings), file=sys.stderr)
        return 1
    print("secret_scan: clean (%d tracked files)" % len(tracked_files()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
