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

import telegram_preview  # the same reader the poster guards with
import telegram_token  # one reader for the bot token — tolerant of phone pastes
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


def describe_chats(token):
    """The chats this bot can see *right now*, read out of `getUpdates`.

    A last resort for the one failure that costs the most days: the chat id is wrong,
    every run dies at `chat not found`, and the operator has no idea what the right
    value is. `getUpdates` is read-only and free, and Telegram keeps a short window of
    updates — so this is a hint, not a census. It can legitimately come back empty (no
    recent activity, or a webhook is registered), and the caller must say so rather
    than conclude the bot has no chats.
    """
    ok, updates = call("getUpdates", token, limit=100)
    if not ok:
        return None, updates          # None = "I could not ask", [] = "nothing recent"
    found, order = {}, []
    for item in updates or []:
        if not isinstance(item, dict):
            continue
        for key in ("channel_post", "message", "my_chat_member", "chat_member"):
            entry = item.get(key)
            chat = entry.get("chat") if isinstance(entry, dict) else None
            if not isinstance(chat, dict) or chat.get("id") is None:
                continue
            chat_id = str(chat["id"])
            if chat_id not in found:
                order.append(chat_id)
            found[chat_id] = {
                "id": chat_id,
                "type": chat.get("type") or "?",
                "username": chat.get("username"),
                "title": chat.get("title"),
            }
    return [found[key] for key in order], None


def chat_hint(chat_id, chats, error):
    """What to type, given what the bot can actually see."""
    lines = []
    visible = [chat for chat in (chats or []) if chat.get("id") != chat_id]
    if not chats:
        lines.append("getUpdates returned nothing, which is normal when a webhook is "
                     "registered or the channel has had no recent traffic — it does not "
                     "mean the bot has no chats. The numeric id is visible in the channel's "
                     "admin log, or by adding the bot, posting once, and calling getUpdates "
                     "with the webhook deleted.")
        return "\n".join(lines)
    if "chat not found" in (error or "").lower() and str(chat_id).startswith("@"):
        wanted = str(chat_id).lstrip("@").lower()
        near = [chat for chat in visible
                if (chat.get("username") or "").lower().startswith(wanted)
                or (chat.get("title") or "").lower().replace(" ", "").startswith(wanted.replace(" ", ""))]
        if near:
            lines.append("`%s` does not exist; the closest chat the bot can see is **@%s** "
                         "(%s). A public channel works by username, but the exact spelling wins:"
                         % (chat_id, near[0].get("username") or "?", near[0].get("id")))
            lines.append("  gh secret set TELEGRAM_CHAT_ID --body '@%s'   # or --body '%s'"
                         % (near[0].get("username"), near[0].get("id")))
            return "\n".join(lines)
    lines.append("Chats this bot can see (from its last %d updates):" % len(chats))
    for chat in visible[:8]:
        lines.append("  %-16s %-11s %s%s" % (chat["id"], chat["type"], chat.get("title") or "—",
                                             "  @" + chat["username"] if chat.get("username") else ""))
    if len(visible) == 1:
        lines.append("One candidate — set it and re-run:")
        lines.append("  gh secret set TELEGRAM_CHAT_ID --body '%s'" % visible[0]["id"])
    else:
        lines.append("Pick the channel's id from the list and set it:")
        lines.append("  gh secret set TELEGRAM_CHAT_ID --body '-100…'")
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    quiet = "--quiet" in argv

    # `--preview [@name]` answers one question with no token and no secrets at all: is the
    # channel's public preview readable, i.e. can the poster's live duplicate guard work?
    # It is here because the guard is worthless if nobody can check it.
    if "--preview" in argv:
        positional = [a for a in argv if not a.startswith("--")]
        handle = (positional[0].lstrip("@") if positional
                  else telegram_preview.channel_handle(chat_id=os.getenv("TELEGRAM_CHAT_ID")))
        state, detail = telegram_preview.describe(handle=handle)
        if not quiet:
            print("%s channel preview: %s" % ("✅" if state == "readable" else "⚠️", detail))
        return 0 if state == "readable" else 1

    raw_token = os.getenv("TELEGRAM_BOT_TOKEN")
    token, token_note = telegram_token.from_env()
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    missing = []
    if not raw_token:
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

    # 2. token — shape first (offline, exact, redacted), then Telegram's verdict.
    if token is None:
        annotate(
            "error",
            "Telegram bot token is not a token",
            "TELEGRAM_BOT_TOKEN does not contain anything shaped like a bot token "
            f"({token_note}). A bot token is <digits>:<35 characters>, e.g. 123456789:AAH… — "
            "open @BotFather → /mybots → the bot → API Token and paste exactly that. "
            "Nothing was generated and nothing was posted; the channel itself is fine.",
        )
        return 3
    if token_note:
        annotate(
            "warning",
            "Telegram bot token was pasted untidily",
            f"TELEGRAM_BOT_TOKEN {token_note}; the token inside it is being used, so this run "
            "continues. Re-paste the bare token when convenient.",
        )
    ok, bot = call("getMe", token)
    if not ok:
        annotate(
            "error",
            "Telegram bot token rejected",
            f"getMe failed: {bot}. {telegram_token.explain_rejection(str(bot))} "
            "(The channel itself is fine.)",
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
        # The four-day outage ended at exactly this line, and the run log stopped
        # there: it said the chat was unreachable and left the operator to go find the
        # right id by hand. So the preflight finishes the job it started.
        chats, probe_error = describe_chats(token)
        if chats is None:
            annotate("warning", "Could not list the bot's chats",
                     "getUpdates failed: %s — the id has to be found another way." % probe_error)
        hint = chat_hint(chat_id, chats, chat)
        if hint:
            print(hint)
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
        # Say whether the duplicate guard can see the channel, because "green preflight" and
        # "the guard is watching" are different claims and the operator is told both.
        state, detail = telegram_preview.describe(chat_id=chat_id)
        print("%s live duplicate guard: %s"
              % ("✅" if state == "readable" else "ℹ️", detail))
    return 0


if __name__ == "__main__":
    sys.exit(main())
