#!/usr/bin/env python3
"""The one place a Telegram bot token is read from the environment.

Why this exists: on 15 and 16 Oct 2026 the Telegram lane failed with
`getMe failed: Not Found`. Telegram answers **404 Not Found** when the *path* does not parse
as `/bot<digits>:<secret>/<method>` — a token pasted with its `bot` prefix, as the whole
`https://api.telegram.org/bot…` URL, wrapped in quotes, or with a stray character; a
*revoked* token gets **401 Unauthorized** instead. The lane had worked the day before, so the
secret had been re-pasted from a phone, and three scripts then built three URLs from the raw
value and got the same 404 three times. One normaliser, used by the preflight and both
posters, means a paste that still *contains* the token works, and a paste that does not is
described precisely (shape only — never the value) so the next fix is one re-paste, not a
guessing game.

    >>> normalize("  bot123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw  ")
    ('123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw', 'had a bot prefix; had whitespace')
"""

import os
import re

# Bot ids are 8–12 digits today; the secret part is 35 characters of [A-Za-z0-9_-] but
# has been both 34 and 35 over the years, so be generous either side.
TOKEN_RE = re.compile(r"(?<![0-9])([0-9]{6,14}):([A-Za-z0-9_-]{30,60})(?![A-Za-z0-9_-])")

ENV = "TELEGRAM_BOT_TOKEN"


def normalize(raw):
    """Return (token_or_None, note). `note` lists what was wrong with the paste ('' if clean).

    Accepts the bare token, `bot<token>`, the full API URL, and quoted / whitespace-padded
    variants. Returns None when nothing shaped like a token is inside the value.
    """
    if raw is None:
        return None, "unset"
    text = str(raw)
    notes = []
    stripped = text.strip().strip("\"'").strip()
    if stripped != text:
        notes.append("had whitespace" if stripped == text.strip() else "had quotes or whitespace")
    m = TOKEN_RE.search(stripped)
    if not m:
        return None, describe(stripped) if stripped else "empty"
    token = "%s:%s" % (m.group(1), m.group(2))
    before = stripped[: m.start()]
    after = stripped[m.end():]
    if before.lower().endswith("bot"):
        notes.append("had a bot prefix")
        before = before[:-3]
    if before:
        notes.append("had %d extra character%s in front" % (len(before), "" if len(before) == 1 else "s"))
    if after:
        notes.append("had %d extra character%s after it" % (len(after), "" if len(after) == 1 else "s"))
    return token, "; ".join(notes)


def describe(value):
    """A redacted description of a value that is NOT a bot token — for the annotation.

    Says what shape it has, never what it is: length, where the colon is, whether it is all
    digits (a chat id pasted into the wrong field), whether it looks like a URL.
    """
    value = value or ""
    bits = ["length %d" % len(value)]
    if not value:
        return "empty"
    if value.lstrip("-").isdigit():
        bits.append("all digits — looks like a chat id, not a bot token")
        return ", ".join(bits)
    if "://" in value:
        bits.append("looks like a URL")
    colon = value.find(":")
    if colon < 0:
        bits.append("no colon — a bot token is <digits>:<35 characters>")
    else:
        head, tail = value[:colon], value[colon + 1:]
        bits.append("colon at %d" % colon)
        if not head.isdigit():
            bits.append("the part before the colon is not all digits")
        if len(tail) < 30:
            bits.append("only %d characters after the colon — truncated paste" % len(tail))
    bad = sorted(set(ch for ch in value if not (ch.isalnum() or ch in ":_-")))
    if bad:
        bits.append("contains %s" % ", ".join(repr(ch) for ch in bad[:4]))
    return ", ".join(bits)


def from_env(env=None):
    """(token_or_None, note) for TELEGRAM_BOT_TOKEN as set — the only reader the lane uses."""
    env = os.environ if env is None else env
    return normalize(env.get(ENV))


def explain_rejection(description):
    """Turn Telegram's getMe error into the one thing to do next."""
    text = (description or "").lower()
    if "not found" in text:
        return ("Telegram does not recognise the shape of this token (404). It is a paste "
                "problem, not a revoked bot: open @BotFather → /mybots → the bot → API Token, "
                "copy it, and set TELEGRAM_BOT_TOKEN to exactly that — digits, a colon, 35 characters.")
    if "unauthorized" in text:
        return ("Telegram rejected the token outright (401): it was revoked or regenerated. "
                "Open @BotFather → /mybots → the bot → API Token → Revoke current token, then set "
                "TELEGRAM_BOT_TOKEN to the new one.")
    return "Re-check TELEGRAM_BOT_TOKEN with @BotFather (/mybots → API Token)."
