#!/usr/bin/env python3
"""
Telegram preflight — name the problem before spending the run on it.
====================================================================

The daily Telegram post failed every day from 7 Oct 2026 and the run log said
only "Telegram auto-posting failed!". Nobody could tell from it whether the
token was revoked, the channel was unreachable, or the bot had lost permission
to post — so the outage lasted four days.

This runs first, before content generation, and answers those questions in
order with the Telegram API's own words:

  1. are both secrets present?
  2. is the bot token still valid?          (`getMe`)
  3. can the chat be reached at all?        (`getChat`)
  4. may the bot actually post there?       (`getChatMember` → can_post_messages)

Standard library only (`urllib`), so it also works before `pip install`.

Exit codes
  0  everything checked out
  2  TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing
  3  the token was rejected — revoked or mistyped
  4  the chat could not be resolved from TELEGRAM_CHAT_ID
  5  the bot cannot post to that chat (not an admin / posting not permitted)

Usage:
  python3 tools/telegram_preflight.py            # exit status only
  python3 tools/telegram_preflight.py --quiet    # only problems
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.telegram.org"
TIMEOUT = 20


def annotate(level, title, message):
    """Emit a GitHub Actions annotation when running in Actions."""
    if os.getenv("GITHUB_ACTIONS") == "true":
        print(f"::{level} title={title}::{message}")
    else:
        print(f"{level.upper()}: {title} — {message}")


def call(method, token, **params):
    """Call a Bot API method. Returns (ok, payload_or_error_description)."""
    url = f"{API}/bot{token}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            return False, f"HTTP {e.code} {e.reason}"
    except Exception as e:  # network/DNS/TLS
        return False, f"{type(e).__name__}: {e}"

    if body.get("ok"):
        return True, body.get("result")
    return False, body.get("description") or "unknown Telegram error"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    quiet = "--quiet" in argv

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    missing = []
    if not token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not chat_id:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        annotate(
            "error",
            "Telegram secrets missing",
            "Set these repository secrets: %s — nothing was generated and "
            "nothing was posted." % ", ".join(missing),
        )
        return 2

    # 2. token
    ok, bot = call("getMe", token)
    if not ok:
        annotate(
            "error",
            "Telegram bot token rejected",
            f"getMe failed: {bot}. The token in TELEGRAM_BOT_TOKEN is revoked or "
            "wrong — reissue it with @BotFather (the channel itself is fine).",
        )
        return 3
    if not quiet:
        print(
            "✅ Token valid — bot @%s (id %s)"
            % (bot.get("username"), bot.get("id"))
        )

    # 3. chat
    ok, chat = call("getChat", token, chat_id=chat_id)
    if not ok:
        annotate(
            "error",
            "Telegram chat not reachable",
            f"getChat({chat_id}) failed: {chat}. Either TELEGRAM_CHAT_ID is wrong "
            "or the bot is no longer a member of that channel.",
        )
        return 4
    if not quiet:
        print(
            "✅ Chat reachable — %s (%s) id %s"
            % (chat.get("title") or chat.get("username"), chat.get("type"), chat.get("id"))
        )

    # 4. posting rights
    ok, member = call(
        "getChatMember", token, chat_id=chat_id, user_id=bot.get("id")
    )
    if not ok:
        # Not fatal: a brand-new bot in a group can legitimately fail here, and
        # the poster itself will report the real error if posting then fails.
        annotate(
            "warning",
            "Could not verify posting rights",
            f"getChatMember failed: {member}. Continuing — the post itself will "
            "report the reason if it cannot be delivered.",
        )
        return 0

    status = member.get("status")
    if status not in ("administrator", "creator"):
        annotate(
            "error",
            "Bot cannot post to the channel",
            f"The bot's status in the chat is '{status}', not administrator. "
            "Add the bot as an administrator of the channel with 'Post messages' "
            "permission, or it can never publish.",
        )
        return 5

    if member.get("can_post_messages") is False:
        annotate(
            "error",
            "Bot may not post messages",
            "The bot is an administrator but 'can_post_messages' is false — "
            "re-grant the 'Post messages' permission in the channel's admin "
            "settings. Every post would be rejected until this is fixed.",
        )
        return 5

    if not quiet:
        print(f"✅ Posting rights confirmed (status: {status})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
