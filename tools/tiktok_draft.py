#!/usr/bin/env python3
"""tiktok_draft.py — put the day's Short into the owner's TikTok inbox as a draft, ₦0.

Why TikTok (research, 17 Oct 2026): 47.8M Nigerian adults in TikTok's ad reach, up 43 % in a
year — the biggest audience of any platform this repo can touch, and the one every other
channel is losing minutes to. The Short already exists (vertical, voiced, 22–45 s, on-brand).
The only question was how to get it there without a card or an audit.

What TikTok's Content Posting API allows an *unaudited* app (the honest version):
  * Direct Post → forced `SELF_ONLY` (private) until the app passes audit. Useless for reach.
  * **Inbox upload** (`video.upload`, `POST /v2/post/publish/inbox/video/init/`) → the video
    lands in the creator's own TikTok inbox as a notification; the owner opens the app, writes
    the caption, taps Post. No audit. At most five pending inbox uploads per 24 hours; we
    send two a week. The one tap we could not remove is the one TikTok reserves for a human.
  * Tokens: access 24 h, refresh 365 days, and the refresh call may rotate the refresh token —
    so the rotated one is sealed into `logs/tiktok_refresh_token.box` with tools/token_vault.py
    when `SOCIAL_TOKEN_KEY` is set (same box the Threads and Instagram lanes use).

Usage
    python3 tools/tiktok_draft.py auth --code <code> --redirect-uri <uri>   # once, prints the refresh token
    python3 tools/tiktok_draft.py probe
    python3 tools/tiktok_draft.py send --video out/short.mp4 --caption "…" [--dry-run]
Secrets: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN (bootstrap).
Exit 0 inbox/dormant/duplicate, 3 credentials, 4 file, 6 API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

API = "https://open.tiktokapis.com"
LEDGER = Path(os.environ.get("DOCOGA_TIKTOK_LEDGER") or (ROOT / "logs" / "tiktok_drafts.json"))
BOX_NAME = "TIKTOK_REFRESH_TOKEN"
CHUNK = 10 * 1024 * 1024          # TikTok: 5–64 MB per chunk; a single chunk may be the whole file
SINGLE_MAX = 64 * 1024 * 1024
PENDING_PER_DAY = 5
TERMINAL = ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE", "FAILED")
KEEP = 200


class ApiError(Exception):
    def __init__(self, status, body, cause):
        super().__init__("%s %s" % (status, cause))
        self.status, self.body, self.cause = status, body, cause

    @property
    def blurb(self):
        try:
            err = json.loads(self.body).get("error") or {}
            return ("%s: %s" % (err.get("code"), err.get("message")))[:200]
        except (ValueError, AttributeError):
            return str(self.body)[:200]


def _http(method, url, headers=None, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers or {})
    except (urllib.error.URLError, OSError) as e:
        raise ApiError(0, str(e), "transport")


http = _http
sleeper = time.sleep


def classify(status, body):
    low = (body or "").lower()
    if status == 401 or "access_token_invalid" in low or "invalid_grant" in low or "token" in low and "expired" in low:
        return "credentials"
    if "scope_not_authorized" in low or "scope" in low and "unauthorized" in low:
        return "permission"
    if "spam_risk" in low or "rate_limit" in low or status == 429:
        return "quota"
    if "unaudited_client" in low:
        return "audit"
    return "api"


def _json_call(method, url, token, body=None):
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=UTF-8"}
    status, resp, _ = http(method, url, headers, json.dumps(body).encode("utf-8") if body is not None else None)
    try:
        data = json.loads(resp) if resp else {}
    except ValueError:
        data = {}
    err = (data.get("error") or {})
    if status >= 400 or (err.get("code") and err.get("code") != "ok"):
        raise ApiError(status, resp, classify(status, resp))
    return data.get("data") or {}


# ───────────────────────────── tokens ─────────────────────────────
def _vault():
    try:
        import token_vault
        return token_vault
    except Exception:
        return None


def refresh_token_value():
    """The newest refresh token we hold: the sealed box first, then the bootstrap secret."""
    vault = _vault()
    if vault and os.environ.get("SOCIAL_TOKEN_KEY"):
        try:
            value, payload = vault.open_box(BOX_NAME)
            if value:
                return value.strip(), "vault (sealed %s)" % payload.get("minted_at", "?")[:10]
        except Exception:
            pass
    return (os.environ.get("TIKTOK_REFRESH_TOKEN") or "").strip(), "secret"


def exchange(grant, **fields):
    key, secret = os.environ.get("TIKTOK_CLIENT_KEY", ""), os.environ.get("TIKTOK_CLIENT_SECRET", "")
    form = {"client_key": key, "client_secret": secret, "grant_type": grant}
    form.update(fields)
    status, resp, _ = http("POST", API + "/v2/oauth/token/",
                           {"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
                           urllib.parse.urlencode(form).encode("utf-8"))
    try:
        data = json.loads(resp)
    except ValueError:
        data = {}
    if status >= 400 or not data.get("access_token"):
        raise ApiError(status, resp, classify(status, resp) if status != 400 else "credentials")
    return data


def access_token():
    """Refresh → (access token, open_id). Seals a rotated refresh token when it can."""
    refresh, where = refresh_token_value()
    if not refresh:
        return None, None, where
    data = exchange("refresh_token", refresh_token=refresh)
    print("token: refreshed from the %s; scopes %s" % (where, data.get("scope", "?")))
    new_refresh = (data.get("refresh_token") or "").strip()
    vault = _vault()
    if new_refresh and vault and os.environ.get("SOCIAL_TOKEN_KEY"):
        days = int(data.get("refresh_expires_in") or 0) // 86400
        expires = (datetime.now(timezone.utc) + timedelta(seconds=int(data.get("refresh_expires_in") or 0))).date().isoformat() if days else None
        try:
            vault.seal(BOX_NAME, new_refresh, expires_at=expires, out=sys.stderr)
            print("TIKTOK_VAULT=sealed")
        except Exception as exc:  # the lane still posts on the bootstrap secret
            print("::warning title=TikTok refresh token not sealed::%s" % str(exc)[:120])
    elif new_refresh and new_refresh != refresh:
        print("::warning title=TikTok rotated its refresh token::set SOCIAL_TOKEN_KEY so the lane can keep it; "
              "until then the bootstrap secret is used and will stop working when TikTok retires it")
    return data["access_token"], data.get("open_id"), where


# ───────────────────────────── ledger ─────────────────────────────
def load_ledger(path=None):
    try:
        data = json.loads(Path(path or LEDGER).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"entries": []}
    except (OSError, ValueError):
        return {"entries": []}


def save_ledger(data, path=None):
    path = Path(path or LEDGER)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["entries"] = data.get("entries", [])[-KEEP:]
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def file_key(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def pending_last_day(ledger, now=None):
    now = now or datetime.now(timezone.utc)
    count = 0
    for e in ledger.get("entries", []):
        try:
            when = datetime.fromisoformat(e.get("recorded_at", ""))
        except ValueError:
            continue
        if (now - when) < timedelta(hours=24) and e.get("status") in ("SEND_TO_USER_INBOX", "PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD"):
            count += 1
    return count


# ───────────────────────────── upload ─────────────────────────────
def plan_chunks(size):
    if size <= SINGLE_MAX:
        return size, 1
    count = size // CHUNK
    return CHUNK, max(1, count)   # the last chunk carries the remainder (TikTok allows up to 128 MB there)


def upload(token, video, caption=""):
    size = os.path.getsize(video)
    chunk_size, count = plan_chunks(size)
    init = _json_call("POST", API + "/v2/post/publish/inbox/video/init/", token,
                      {"source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                       "chunk_size": chunk_size, "total_chunk_count": count}})
    publish_id, upload_url = init.get("publish_id"), init.get("upload_url")
    if not (publish_id and upload_url):
        raise ApiError(200, json.dumps(init), "api")
    print("inbox init: publish_id %s, %d byte(s) in %d chunk(s)" % (publish_id, size, count))
    with open(video, "rb") as fh:
        for index in range(count):
            start = index * chunk_size
            end = size - 1 if index == count - 1 else start + chunk_size - 1
            fh.seek(start)
            blob = fh.read(end - start + 1)
            status, body, _ = http("PUT", upload_url,
                                   {"Content-Type": "video/mp4", "Content-Length": str(len(blob)),
                                    "Content-Range": "bytes %d-%d/%d" % (start, end, size)}, blob, timeout=300)
            if status not in (200, 201, 206):
                raise ApiError(status, body, classify(status, body))
    return publish_id


def wait_for(token, publish_id, attempts=8, pause=5):
    status, reason = "UNKNOWN", ""
    for _ in range(attempts):
        data = _json_call("POST", API + "/v2/post/publish/status/fetch/", token, {"publish_id": publish_id})
        status, reason = data.get("status") or "UNKNOWN", data.get("fail_reason") or ""
        if status in TERMINAL:
            break
        sleeper(pause)
    return status, reason


# ───────────────────────────── main ─────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(description="TikTok inbox drafts for the day's Short")
    sub = ap.add_subparsers(dest="verb", required=True)
    au = sub.add_parser("auth", help="exchange the one-time code for tokens (prints the refresh token once)")
    au.add_argument("--code", required=True)
    au.add_argument("--redirect-uri", required=True)
    sub.add_parser("probe", help="refresh the token and stop")
    se = sub.add_parser("send")
    se.add_argument("--video", required=True)
    se.add_argument("--caption", default="")
    se.add_argument("--dry-run", action="store_true")
    se.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    if a.verb == "auth":
        try:
            data = exchange("authorization_code", code=a.code, redirect_uri=a.redirect_uri)
        except ApiError as exc:
            print("::error title=TikTok code exchange failed::%s" % exc.blurb)
            return 3
        print("open_id: %s\nscopes: %s\nrefresh token (paste into the TIKTOK_REFRESH_TOKEN secret, then forget it):\n%s"
              % (data.get("open_id"), data.get("scope"), data.get("refresh_token")))
        return 0

    if not (os.environ.get("TIKTOK_CLIENT_KEY") and os.environ.get("TIKTOK_CLIENT_SECRET")) or not refresh_token_value()[0]:
        print("::notice title=TikTok lane dormant::set TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET and TIKTOK_REFRESH_TOKEN "
              "(docs/TIKTOK_AUTOMATION.md) and every Short also lands in your TikTok inbox")
        print("TIKTOK_RESULT=dormant")
        return 0

    try:
        token, open_id, _ = access_token()
    except ApiError as exc:
        if exc.cause == "credentials":
            print("::error title=TikTok refresh token dead::%s — authorise once more (docs/TIKTOK_AUTOMATION.md) "
                  "and paste the new refresh token into TIKTOK_REFRESH_TOKEN" % exc.blurb)
        else:
            print("::error title=TikTok unreachable (%s)::%s" % (exc.cause, exc.blurb))
        print("TIKTOK_RESULT=failed")
        print("TIKTOK_CAUSE=%s" % exc.cause)
        return 3 if exc.cause == "credentials" else 6
    print("authorised as open_id %s" % (open_id or "?"))
    if a.verb == "probe":
        print("TIKTOK_RESULT=probed")
        return 0

    if not os.path.isfile(a.video):
        print("::error title=No video to send::%s does not exist" % a.video)
        print("TIKTOK_RESULT=failed")
        print("TIKTOK_CAUSE=file")
        return 4
    ledger = load_ledger()
    key = file_key(a.video)
    dup = next((e for e in ledger.get("entries", []) if e.get("key") == key), None)
    if dup and not a.force:
        print("refused-a-duplicate: these bytes went to the inbox on %s (publish_id %s)" % (dup.get("recorded_at", "?")[:10], dup.get("publish_id")))
        print("TIKTOK_RESULT=duplicate")
        return 0
    pending = pending_last_day(ledger)
    if pending >= PENDING_PER_DAY and not a.force:
        print("::warning title=TikTok inbox full::%d uploads are already waiting in the inbox from the last 24 h (TikTok allows %d) — "
              "open the TikTok app and post or discard them" % (pending, PENDING_PER_DAY))
        print("TIKTOK_RESULT=skipped")
        return 0
    if a.dry_run:
        print("dry run: would send %s (%d bytes) to the inbox with caption %r" % (a.video, os.path.getsize(a.video), a.caption[:80]))
        print("TIKTOK_RESULT=dry-run")
        return 0
    try:
        publish_id = upload(token, a.video, a.caption)
        status, reason = wait_for(token, publish_id)
    except ApiError as exc:
        print("::error title=TikTok inbox upload failed (%s)::%s" % (exc.cause, exc.blurb))
        print("TIKTOK_RESULT=failed")
        print("TIKTOK_CAUSE=%s" % exc.cause)
        return {"credentials": 3, "permission": 3}.get(exc.cause, 6)
    ledger.setdefault("entries", []).append({"recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "key": key,
                                             "publish_id": publish_id, "status": status, "caption": a.caption[:150],
                                             "video": os.path.basename(a.video), "run_id": os.environ.get("GITHUB_RUN_ID", "")})
    save_ledger(ledger)
    if status == "FAILED":
        print("::error title=TikTok rejected the video::%s" % (reason or "no reason given"))
        print("TIKTOK_RESULT=failed")
        print("TIKTOK_CAUSE=video")
        return 6
    print("✅ in the inbox: publish_id %s, status %s" % (publish_id, status))
    print("Caption to paste in the TikTok app:\n%s" % a.caption)
    print("TIKTOK_RESULT=inbox")
    print("TIKTOK_PUBLISH_ID=%s" % publish_id)
    print("TIKTOK_STATUS=%s" % status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
