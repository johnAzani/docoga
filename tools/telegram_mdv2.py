#!/usr/bin/env python3
"""
Telegram MarkdownV2 — escaping, validation and plain-text fallback.
==================================================================

Why this file exists
--------------------
The daily Telegram post has been failing since 7 Oct 2026 with:

    Bad Request: can't parse entities: Character '#' is reserved and must be
    escaped with the preceding '\\'

The message templates in `scripts/generate_telegram_content.py` are hand-escaped
for MarkdownV2 (every `.` and `!` written as `\\.` and `\\!`), but the hashtag
block — `#DocOga #NigerianLandlords …` — is appended raw. In MarkdownV2 `#` is a
reserved character, so Telegram rejects the whole message before it is ever
delivered. Every template was one typo away from the same fate; nothing checked.

So escaping is now a function, not a habit:

  * `escape()`   — escape arbitrary text (hashtags, dynamic values) for MarkdownV2
  * `validate()` — return the list of reasons Telegram would reject a message
  * `to_plain()` — strip markup for the plain-text fallback path

`tools/tests/test_telegram_mdv2.py` runs `validate()` over every template in
every post type, so an unescaped character fails CI instead of a 9 AM post.

MarkdownV2 reference (Telegram Bot API, "Formatting options"):
https://core.telegram.org/bots/api#markdownv2-style

Inside `code` and `pre` entities only `` ` `` and `\\` are special; everywhere
else the reserved set is:

    _ * [ ] ( ) ~ ` > # + - = | { } . !
"""

# Reserved characters that must be backslash-escaped in MarkdownV2 normal text.
SPECIALS = "_*[]()~`>#+-=|{}.!"

# Markup that opens/closes symmetric entities. `||` is handled before `|`.
_ENTITY_MARKERS = ("_", "*", "~", "`", "||")


def escape(text: str) -> str:
    """Escape every MarkdownV2 reserved character in `text`.

    Use this for anything dynamic — hashtags, titles, user or file names — and
    never hand-escape. Already-escaped input is safe to pass through: a literal
    backslash becomes `\\\\`.
    """
    if text is None:
        return ""
    out = []
    for ch in str(text):
        if ch == "\\":
            out.append("\\\\")
        elif ch in SPECIALS:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def unescape(text: str) -> str:
    """Remove MarkdownV2 escapes: `\\\\.` -> `.`."""
    out = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            out.append(text[i + 1])
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def to_plain(text: str) -> str:
    """Strip MarkdownV2 markup so the message reads cleanly as plain text.

    This is what the fallback path sends when Telegram refuses to parse the
    formatted message. It must remove *all* markup, not just asterisks: an
    earlier version left `_` and `` ` `` behind, so the channel showed literal
    `_**🔍**_` in front of every post.
    """
    if not text:
        return ""
    stripped = unescape(text)
    for marker in ("||", "*", "_", "~", "`"):
        stripped = stripped.replace(marker, "")
    return stripped


def validate(text: str) -> list:
    """Return the reasons Telegram would reject `text` as MarkdownV2.

    An empty list means the message should parse. This is a static check of the
    documented rules — the same rules that produced the 7 Oct failure — so it
    catches the bug class before the message reaches Telegram.

    Known limitation: it validates structure, not whether Telegram accepts the
    content of a `[text](url)` link.
    """
    problems = []
    if not text:
        return ["message is empty — Telegram rejects empty text"]

    open_entities = []   # markers waiting to be closed, innermost last
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        if ch == "\\":
            if i + 1 >= length:
                problems.append("trailing backslash at position %d" % i)
                break
            i += 2  # the escaped character is literal; it cannot open markup
            continue

        # pre / code spans: only ` and \ are special inside them
        if text.startswith("```", i):
            end = text.find("```", i + 3)
            if end == -1:
                problems.append("unclosed pre block at position %d" % i)
                break
            i = end + 3
            continue
        if ch == "`":
            end = text.find("`", i + 1)
            if end == -1:
                problems.append("unclosed code span at position %d" % i)
                break
            i = end + 1
            continue

        if ch == "[":
            close = text.find("]", i + 1)
            if close == -1 or text[close + 1:close + 2] != "(":
                problems.append(
                    "link-like '[' at position %d is not escaped and has no "
                    "'[text](url)' form" % i
                )
            else:
                end = text.find(")", close + 1)
                if end == -1:
                    problems.append("unclosed link at position %d" % i)
                    break
                i = end + 1
                continue

        # spoiler || (checked before the single | character)
        if text.startswith("||", i):
            if open_entities and open_entities[-1] == "||":
                open_entities.pop()
            else:
                open_entities.append("||")
            i += 2
            continue

        if ch in "*_~":
            if ch == "_" and text.startswith("__", i):
                if open_entities and open_entities[-1] == "__":
                    open_entities.pop()
                else:
                    open_entities.append("__")
                i += 2
                continue
            if open_entities and open_entities[-1] == ch:
                open_entities.pop()
            else:
                open_entities.append(ch)
            i += 1
            continue

        if ch in SPECIALS:
            problems.append(
                "character '%s' at position %d is reserved and must be escaped "
                "with a preceding '\\'" % (ch, i)
            )

        i += 1

    for marker in open_entities:
        problems.append("unclosed '%s' entity" % marker)

    return problems


def assert_valid(text: str, label: str = "message") -> None:
    """Raise ValueError naming every problem — used by the tests."""
    problems = validate(text)
    if problems:
        raise ValueError(
            "%s is not valid Telegram MarkdownV2:\n  - %s"
            % (label, "\n  - ".join(problems))
        )


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    import sys

    for arg in sys.argv[1:]:
        print("— %s" % arg)
        for problem in validate(arg):
            print("   ❌ %s" % problem)
