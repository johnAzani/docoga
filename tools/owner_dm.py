#!/usr/bin/env python3
"""owner_dm.py — a private Telegram message to the owner's phone, through the channel bot (₦0).

Why: TikTok's inbox-upload API (the only route an unaudited app has to a public account)
carries no caption — the owner must paste it in the app. He should not have to open GitHub to
find it (owner, 18 Oct 2026: "I had to paste the caption myself"). So the lane texts it to him
the moment the draft lands: a Telegram DM from @docoga_daily_bot with the caption in a
tap-to-copy block and the three taps that follow. The same channel can carry any one-line
"your tap is needed" note later.

Telegram bots cannot message a person first. One-time setup, from the phone:
    open Telegram → search @docoga_daily_bot → Start → send the word   owner
The next lane run finds that message with `getUpdates`, records the chat in
`logs/telegram_owner.json` (committed with the lane's ledger, like the TikTok box), and every
run after that DMs without looking again. Nobody else gets adopted: the word is the handshake.

    python3 tools/owner_dm.py discover            # adopt the owner's chat if he has said hello
    python3 tools/owner_dm.py send --text "…"     # DM (plain text); exit 0 always
    python3 tools/owner_dm.py tiktok --caption "…" [--title "…"]   # the TikTok paste message

Env: TELEGRAM_BOT_TOKEN. Machine lines: OWNER_DM=sent|unknown|skipped|failed, OWNER_CHAT=…
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.telegram.org/bot%s/%s"
TIMEOUT = (10, 30)
HANDSHAKE = "owner"
RECORD = ROOT / "logs" / "telegram_owner.json"


def record_path():
    return Path(os.environ.get("OWNER_DM_RECORD") or RECORD)


def load_record():
    p = record_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data, dict) and str(data.get("chat_id") or "").strip() else {}


def save_record(rec):
    p = record_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def said_hello(update):
    """The private chat behind an update whose text is the handshake word, else None."""
    msg = update.get("message") or update.get("edited_message") or {}
    chat = msg.get("chat") or {}
    if chat.get("type") != "private":
        return None
    text = " ".join(str(msg.get("text") or "").lower().split())
    if HANDSHAKE not in text.replace("/", " ").split():
        return None
    who = msg.get("from") or {}
    return {"chat_id": str(chat.get("id")), "first_name": who.get("first_name") or chat.get("first_name") or "",
            "username": who.get("username") or chat.get("username") or ""}


def discover(token, get=None):
    """→ (record or {}, note). Looks at the bot's recent private messages for the handshake."""
    rec = load_record()
    if rec:
        return rec, "known"
    get = get or requests.get
    try:
        r = get(API % (token, "getUpdates"), params={"allowed_updates": json.dumps(["message", "edited_message"]), "limit": 100}, timeout=TIMEOUT)
        body = r.json() if r.content else {}
    except (requests.RequestException, ValueError) as exc:
        return {}, "getUpdates failed: %s" % type(exc).__name__
    if not body.get("ok"):
        return {}, "getUpdates refused: %s" % str(body.get("description") or r.status_code)[:120]
    found = [h for h in (said_hello(u) for u in body.get("result") or []) if h]
    if not found:
        return {}, "nobody has sent the word '%s' to the bot yet" % HANDSHAKE
    rec = {**found[-1], "adopted_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    save_record(rec)
    return rec, "adopted"


def send(token, chat_id, text, post=None, html=False):
    post = post or requests.post
    data = {"chat_id": chat_id, "text": text[:4096], "disable_web_page_preview": "true"}
    if html:
        data["parse_mode"] = "HTML"
    try:
        r = post(API % (token, "sendMessage"), data=data, timeout=TIMEOUT)
        body = r.json() if r.content else {}
    except (requests.RequestException, ValueError) as exc:
        return False, "%s: %s" % (type(exc).__name__, str(exc)[:100])
    if r.status_code == 200 and body.get("ok"):
        return True, "message %s" % (body.get("result") or {}).get("message_id")
    return False, str(body.get("description") or r.status_code)[:160]


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tiktok_message(caption, title=""):
    """The paste message: tap the grey block once to copy, then Inbox → Post → paste → Post."""
    head = "🎬 TikTok draft ready" + ((": " + title.strip()) if title.strip() else "")
    return ("<b>%s</b>\n\n"
            "Caption — tap the grey text once to copy it:\n"
            "<code>%s</code>\n\n"
            "Then in TikTok: Inbox → <i>Your video from DocOga is ready</i> → Post → "
            "long-press the caption box → Paste → Post.\n"
            "The cover is already the title card." % (_esc(head), _esc(caption)))


def main(argv=None):
    ap = argparse.ArgumentParser(description="DM the owner through the channel bot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("discover")
    se = sub.add_parser("send")
    se.add_argument("--text", required=True)
    tk = sub.add_parser("tiktok")
    tk.add_argument("--caption", required=True)
    tk.add_argument("--title", default="")
    a = ap.parse_args(argv)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("OWNER_DM=skipped")
        print("TELEGRAM_BOT_TOKEN is not in this job — nothing to DM with.")
        return 0
    rec, note = discover(token)
    if not rec:
        print("::notice title=Owner's Telegram not linked yet::%s. One-time, from the phone: Telegram → @docoga_daily_bot → Start → send the word '%s'. "
              "The next run adopts that chat and texts the TikTok caption there." % (note, HANDSHAKE))
        print("OWNER_DM=unknown")
        return 0
    print("OWNER_CHAT=%s (%s%s)" % (rec["chat_id"], rec.get("first_name") or "owner", (" @" + rec["username"]) if rec.get("username") else ""))
    if note == "adopted":
        print("::notice title=Owner's Telegram linked::%s said '%s' to the bot — captions now go to that chat (logs/telegram_owner.json)."
              % (rec.get("first_name") or rec["chat_id"], HANDSHAKE))
    if a.cmd == "discover":
        print("OWNER_DM=%s" % ("linked" if note == "known" else "adopted"))
        return 0
    if a.cmd == "send":
        ok, detail = send(token, rec["chat_id"], a.text)
    else:
        ok, detail = send(token, rec["chat_id"], tiktok_message(a.caption, a.title), html=True)
        if not ok:   # HTML refused for some reason → plain text, never nothing
            ok, detail = send(token, rec["chat_id"], "TikTok draft ready. Caption:\n\n%s" % a.caption)
    if ok:
        print("DM: %s" % detail)
        print("OWNER_DM=sent")
    else:
        print("::warning title=Owner DM not delivered::%s" % detail.replace(token, "<token>"))
        print("OWNER_DM=failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
