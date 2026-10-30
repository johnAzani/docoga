#!/usr/bin/env python3
"""kv_backup.py — the nightly copy of everything the business cannot re-create (₦0).

Why this exists (30 Oct 2026)
-----------------------------
One Cloudflare KV namespace (`f3a5afebe7d04bb0a6018c0d7d355253`, bound as `KV` in both
worker/wrangler.toml and workers/ledger/wrangler.toml) holds every record of value:

    code:*      every pass ever paid for — the email it went to, the Flutterwave ref,
                when it expires, which devices used it (a customer's proof of purchase)
    ref:*       payment reference → code (how a webhook replay is recognised)
    team:* inv:* invref:* seatidx:* brand:*   DocOga Business teams, seats, invoices
    ledger:r:*  ledger:fp:*   the anonymised rent receipts the Rent Monitor is built on
                (≥30 per cell before a number is published; months of accumulation)
    adm:*       the owner dashboard's snapshot and recent-activity cache

Nothing backed it up. A namespace deleted by a mis-click in the dashboard, an account
compromise, a wrangler command with the wrong id, or a Cloudflare-side fault would end
every live pass and reset the Rent Monitor to zero — and there would be no way to tell
a paying customer "yes, you paid". Cloudflare KV has no built-in backups on any plan.

What it does
    1. Lists every key with the account-level REST API (GET …/keys, 1,000 per page, with
       expiration + metadata) and fetches values 100 at a time (POST …/bulk/get).
    2. Skips keys that are binary by construction (`media:<name>:<n>` video chunks,
       `asset:*` images) and the owner's dashboard sessions (`adm:sess:*`) — those are
       re-creatable or short-lived and the bulk endpoint rejects binary values anyway.
    3. Writes ONE file: logs/backup/kv-latest.box — JSON, gzip, then AES-256-GCM under the
       same SOCIAL_TOKEN_KEY the token vault uses (name "KV_BACKUP" as authenticated data),
       so the ciphertext is safe in a public repository and useless without the Actions
       secret. On Sundays it also keeps a dated weekly copy and prunes to the last eight.
    4. Prints a per-prefix count table (no key, no value, no email ever reaches a log).

Permissions: the Cloudflare token needs **Workers KV Storage: Read** on the account. If
it lacks it the API answers 403/10000 and this tool exits 3 with the one-tap fix spelled
out — the lane goes red once, it does not pretend.

    python3 tools/kv_backup.py backup   [--out logs/backup/kv-latest.box] [--weekly]
    python3 tools/kv_backup.py verify   [--file logs/backup/kv-latest.box]      # opens, counts
    python3 tools/kv_backup.py restore  --file F --confirm RESTORE [--prefix code:] [--dry-run]

Machine lines: KV_BACKUP=ok|missing-permission|missing-key|error · KV_BACKUP_KEYS=<n> · KV_BACKUP_BYTES=<n>
Exit: 0 ok · 2 config (no account/token/key) · 3 token lacks KV read · 4 API error · 5 nothing listed
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import token_vault  # noqa: E402  the key, the cipher, the "never print it" discipline

NAMESPACE_ID = "f3a5afebe7d04bb0a6018c0d7d355253"
BOX_NAME = "KV_BACKUP"
OUT = ROOT / "logs" / "backup" / "kv-latest.box"
WEEKLY_KEEP = 8
API = "https://api.cloudflare.com/client/v4"
LIST_LIMIT = 1000
BULK_GET = 100
BULK_PUT = 1000
TIMEOUT = 60
SKIP = (
    re.compile(r"^media:.+:\d+$"),   # video/image chunks stored as bytes
    re.compile(r"^asset:"),          # brand images stored as bytes
    re.compile(r"^adm:sess:"),       # dashboard sessions — minutes long, re-created on login
    re.compile(r"^adm:snap:lock$"),
)
PREFIX_RE = re.compile(r"^([a-z0-9]+(?::[a-z]+)?):")


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__("%s %s %s" % (status, code, message))
        self.status, self.code, self.message = status, code, message


def _call(method, path, token, body=None, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer %s" % token, "Content-Type": "application/json",
                                          "User-Agent": "DocOga-kv-backup/1"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read()
                ctype = (r.headers.get("Content-Type") or "").lower()
                if "application/json" in ctype:
                    try:
                        return json.loads(raw.decode("utf-8"))
                    except ValueError:
                        pass
                return raw.decode("utf-8", "replace")   # GET …/values/{key} answers with the bare value
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                err = json.loads(raw).get("errors") or [{}]
            except Exception:
                err = [{"code": 0, "message": raw[:200]}]
            code = int(err[0].get("code") or 0)
            if e.code == 429 or e.code >= 500:
                if attempt < 3:
                    time.sleep(2 ** attempt * 3)
                    continue
            raise ApiError(e.code, code, str(err[0].get("message") or "")[:200])
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 3:
                time.sleep(2 ** attempt * 3)
                continue
            raise ApiError(0, 0, str(e)[:200])


def list_keys(account, token, call=None):
    call = call or _call
    cursor = None
    out = []
    while True:
        params = {"limit": LIST_LIMIT}
        if cursor:
            params["cursor"] = cursor
        res = call("GET", "/accounts/%s/storage/kv/namespaces/%s/keys" % (account, NAMESPACE_ID), token, params=params)
        out.extend(res.get("result") or [])
        info = res.get("result_info") or {}
        cursor = info.get("cursor")
        if not cursor or info.get("list_complete") is True:
            break
    return out


def skip(name):
    return any(p.search(name) for p in SKIP)


def fetch_values(account, token, names, call=None):
    call = call or _call
    values = {}
    path = "/accounts/%s/storage/kv/namespaces/%s/bulk/get" % (account, NAMESPACE_ID)
    for i in range(0, len(names), BULK_GET):
        chunk = names[i:i + BULK_GET]
        try:
            res = call("POST", path, token, body={"keys": chunk, "type": "text", "withMetadata": True})
            got = (res.get("result") or {}).get("values") or {}
            for k in chunk:
                v = got.get(k)
                if v is None:
                    continue
                values[k] = v if isinstance(v, dict) and "value" in v else {"value": v}
        except ApiError as e:
            if e.status in (401, 403):
                raise
            # One binary or oversize key spoils the whole batch: fall back to one GET per key.
            for k in chunk:
                try:
                    res = call("GET", "/accounts/%s/storage/kv/namespaces/%s/values/%s"
                               % (account, NAMESPACE_ID, urllib.parse.quote(k, safe="")), token)
                    if isinstance(res, str):
                        values[k] = {"value": res}
                    else:                       # a JSON value came back parsed — keep it as text
                        values[k] = {"value": json.dumps(res, ensure_ascii=False)}
                except ApiError as e2:
                    if e2.status in (401, 403):
                        raise
                    values[k] = {"skipped": e2.message[:80]}
                except Exception:
                    values[k] = {"skipped": "unreadable"}
    return values


def prefix_table(records):
    c = Counter()
    for name in records:
        m = PREFIX_RE.match(name)
        c[m.group(1) + ":" if m else "(other)"] += 1
    return c


def seal_bytes(plaintext: bytes, out: Path, meta: dict):
    key = token_vault._load_key()
    AESGCM = token_vault._cipher()
    if AESGCM is None:
        raise RuntimeError("cryptography module missing")
    if key is None:
        raise PermissionError("SOCIAL_TOKEN_KEY is not set")
    if key is False:
        raise PermissionError("SOCIAL_TOKEN_KEY is not 32 bytes")
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, BOX_NAME.encode("utf-8"))
    payload = {"v": 1, "alg": "A256GCM", "name": BOX_NAME, "enc": "gzip+json",
               "nonce": base64.b64encode(nonce).decode("ascii"),
               "ciphertext": base64.b64encode(ct).decode("ascii"),
               "minted_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    payload.update(meta)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    return len(ct)


def open_bytes(path: Path) -> tuple[dict, dict]:
    key = token_vault._load_key()
    AESGCM = token_vault._cipher()
    if key is None or key is False:
        raise PermissionError("SOCIAL_TOKEN_KEY is not set or not 32 bytes")
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("name") != BOX_NAME:
        raise ValueError("not a KV backup box")
    pt = AESGCM(key).decrypt(base64.b64decode(payload["nonce"]), base64.b64decode(payload["ciphertext"]),
                             BOX_NAME.encode("utf-8"))
    return json.loads(gzip.decompress(pt).decode("utf-8")), payload


def snapshot(account, token, call=None, log=print):
    call = call or _call
    keys = list_keys(account, token, call)
    if not keys:
        return None, keys
    wanted = [k["name"] for k in keys if not skip(k["name"])]
    values = fetch_values(account, token, wanted, call)
    records = {}
    for k in keys:
        name = k["name"]
        if name not in values:
            continue
        rec = dict(values[name])
        if k.get("expiration"):
            rec["expiration"] = k["expiration"]
        if k.get("metadata") is not None and "metadata" not in rec:
            rec["metadata"] = k["metadata"]
        records[name] = rec
    doc = {"taken_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "namespace_id": NAMESPACE_ID, "listed": len(keys), "skipped": len(keys) - len(wanted),
           "records": records}
    return doc, keys


def cmd_backup(a):
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not account or not token:
        print("kv_backup: CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN not set")
        print("KV_BACKUP=missing-config")
        return 2
    if token_vault._load_key() in (None, False):
        print("kv_backup: SOCIAL_TOKEN_KEY missing or not 32 bytes — refusing to write customer data unencrypted")
        print("KV_BACKUP=missing-key")
        return 2
    try:
        doc, keys = snapshot(account, token)
    except ApiError as e:
        if e.status in (401, 403) or e.code in (10000, 9109, 10001):
            print("kv_backup: the Cloudflare token cannot read KV (%s). One tap: dash.cloudflare.com → My Profile → "
                  "API Tokens → the token behind CLOUDFLARE_API_TOKEN → Edit → add permission "
                  "'Account · Workers KV Storage · Read' → Continue → Save." % e)
            print("KV_BACKUP=missing-permission")
            return 3
        print("kv_backup: Cloudflare API error: %s" % e)
        print("KV_BACKUP=error")
        return 4
    if doc is None:
        print("kv_backup: the namespace listed zero keys — not overwriting the last good backup")
        print("KV_BACKUP=empty")
        return 5
    plain = gzip.compress(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    table = prefix_table(doc["records"])
    out = Path(a.out)
    ct_len = seal_bytes(plain, out, {"keys": len(doc["records"]), "listed": doc["listed"], "skipped": doc["skipped"]})
    # Sunday: a dated copy as well, so a bad write on Monday does not erase the only copy.
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=1)))
    if a.weekly or today.weekday() == 6:
        weekly = out.with_name("kv-weekly-%s.box" % today.strftime("%Y-%m-%d"))
        weekly.write_bytes(out.read_bytes())
        olds = sorted(out.parent.glob("kv-weekly-*.box"))
        for old in olds[:-WEEKLY_KEEP]:
            old.unlink()
    print("| prefix | keys |\n|---|---|")
    for p, n in sorted(table.items(), key=lambda x: -x[1]):
        print("| %s | %d |" % (p, n))
    print("kv_backup: %d keys listed, %d skipped (binary/session), %d saved → %s (%d bytes ciphertext)"
          % (doc["listed"], doc["skipped"], len(doc["records"]), out, ct_len))
    print("KV_BACKUP=ok")
    print("KV_BACKUP_KEYS=%d" % len(doc["records"]))
    print("KV_BACKUP_BYTES=%d" % ct_len)
    return 0


def cmd_verify(a):
    try:
        doc, payload = open_bytes(Path(a.file))
    except Exception as e:
        print("kv_backup: cannot open %s: %s" % (a.file, e.__class__.__name__))
        print("KV_BACKUP_VERIFY=fail")
        return 4
    table = prefix_table(doc["records"])
    age_h = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(doc["taken_at"])).total_seconds() / 3600
    print("kv_backup: %s opens — taken %s (%.1f h ago), %d keys: %s"
          % (a.file, doc["taken_at"], age_h, len(doc["records"]),
             ", ".join("%s %d" % (p, n) for p, n in sorted(table.items(), key=lambda x: -x[1]))))
    print("KV_BACKUP_VERIFY=ok")
    print("KV_BACKUP_VERIFY_KEYS=%d" % len(doc["records"]))
    return 0


def restore_pairs(doc, prefix="", now=None):
    now = now or time.time()
    pairs = []
    for name, rec in doc["records"].items():
        if prefix and not name.startswith(prefix):
            continue
        if "value" not in rec:
            continue
        exp = rec.get("expiration")
        if exp and exp <= now + 60:
            continue                      # already expired — Cloudflare would refuse it
        item = {"key": name, "value": rec["value"] if isinstance(rec["value"], str) else json.dumps(rec["value"])}
        if exp:
            item["expiration"] = int(exp)
        if rec.get("metadata") is not None:
            item["metadata"] = rec["metadata"]
        pairs.append(item)
    return pairs


def cmd_restore(a):
    if a.confirm != "RESTORE":
        print("kv_backup: restore writes over the live namespace. Re-run with --confirm RESTORE (and --dry-run first).")
        return 2
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    doc, payload = open_bytes(Path(a.file))
    pairs = restore_pairs(doc, a.prefix)
    print("kv_backup: %d pair(s) to write from %s (taken %s)%s" % (len(pairs), a.file, doc["taken_at"],
                                                                   " — DRY RUN" if a.dry_run else ""))
    if a.dry_run:
        return 0
    if not account or not token:
        print("kv_backup: CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN not set")
        return 2
    for i in range(0, len(pairs), BULK_PUT):
        _call("PUT", "/accounts/%s/storage/kv/namespaces/%s/bulk" % (account, NAMESPACE_ID), token, body=pairs[i:i + BULK_PUT])
        print("  wrote %d/%d" % (min(i + BULK_PUT, len(pairs)), len(pairs)))
    print("KV_RESTORE=ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="encrypted nightly copy of the DocOga KV namespace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--out", default=str(OUT))
    b.add_argument("--weekly", action="store_true", help="also write the dated weekly copy today")
    v = sub.add_parser("verify")
    v.add_argument("--file", default=str(OUT))
    r = sub.add_parser("restore")
    r.add_argument("--file", required=True)
    r.add_argument("--confirm", default="")
    r.add_argument("--prefix", default="")
    r.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    return {"backup": cmd_backup, "verify": cmd_verify, "restore": cmd_restore}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
