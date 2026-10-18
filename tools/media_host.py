#!/usr/bin/env python3
"""Short-lived public media for Meta to fetch — the Instagram Reels "third door".

Instagram's publishing API has two ways to take a video: a *resumable upload* (bytes pushed
to rupload.facebook.com — needs the Facebook-Login path, i.e. a Page token and the
Page↔Instagram link) or a *public URL* that Meta cURLs itself ("it must be on a public
server"). The URL way works on the Instagram-Login token too, and that token needs no Page
link at all. On 16 and 18 Oct 2026 Facebook refused to make the Page link ("You're
temporarily restricted … to protect your profile", no date) — so the Reel goes out through
the door that does not depend on it.

Where the file lives for those few minutes: the `docoga-pass` worker's KV namespace, the
same one the dashboard feed is pushed into, with the same two repository secrets
(`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`). No new credential, no new service, ₦0.

    media:<name>        JSON {size, parts, part_size, type, file, put_at, ttl}
    media:<name>:<i>    raw bytes, i = 0..parts-1, each ≤ PART_BYTES (KV's ceiling is 25 MiB)

Every key carries the same `expiration_ttl`, so a Reel that was never deleted vanishes on its
own. The worker serves it at  GET /m/<name>.<ext>  (worker/index.js `handleMedia`): the name
is 32 URL-safe random characters, nothing lists the namespace, and the file is gone minutes
after Meta has it — a public URL in the HTTP sense, not in the "findable" sense.

Verbs
    put FILE [--ttl-hours 48] [--verify-seconds 180]   upload, then poll HEAD until live
    delete NAME                                         remove manifest + parts now
    check URL                                           one HEAD, prints status + length

Machine lines (the workflow reads these with sed)
    MEDIA_NAME=  MEDIA_URL=  MEDIA_BYTES=  MEDIA_PARTS=  MEDIA_LIVE=yes|no  MEDIA_DELETED=n

Exit codes
    0 done · 2 config missing (secrets / file) · 5 the file is not a sendable video
    6 the Cloudflare API or the worker refused (body printed, token never)
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PART_BYTES = 20 * 1024 * 1024          # KV takes 25 MiB per value; 20 keeps headroom for the API body
MAX_BYTES = 300 * 1024 * 1024          # Instagram's own Reel ceiling (IG User Media reference)
DEFAULT_TTL_HOURS = 48
MIN_TTL_SECONDS = 60                   # KV refuses a shorter expiration_ttl
DEFAULT_HOST = "https://docoga-pass.johnazani.workers.dev"
API = "https://api.cloudflare.com/client/v4"
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{16,80}$")
EXTENSIONS = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


class HostError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def namespace_id(root: Path = ROOT) -> str:
    text = (root / "worker" / "wrangler.toml").read_text(encoding="utf-8")
    m = re.search(r'\[\[kv_namespaces\]\][^\[]*?\bid\s*=\s*"([0-9a-f]{32})"', text, re.S)
    if not m:
        raise SystemExit("worker/wrangler.toml: no kv_namespaces id")
    return m.group(1)


def config(env=None, root: Path = ROOT):
    env = dict(os.environ) if env is None else env
    token = (env.get("CLOUDFLARE_API_TOKEN") or "").strip()
    account = (env.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    host = (env.get("MEDIA_HOST_URL") or DEFAULT_HOST).strip().rstrip("/")
    if not (token and account):
        return None
    return {"token": token, "account": account, "host": host, "namespace": namespace_id(root)}


def new_name() -> str:
    return secrets.token_urlsafe(24)  # 32 chars of [A-Za-z0-9_-]


def _send(req, http=None, timeout=120):
    sender = http or (lambda r: urllib.request.urlopen(r, timeout=timeout))
    try:
        with sender(req) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        try:
            detail = json.loads(body.decode("utf-8", "replace"))
            msg = "; ".join(str(x.get("message")) for x in (detail.get("errors") or [])) or str(e.code)
        except ValueError:
            msg = body[:200].decode("utf-8", "replace") or str(e.code)
        raise HostError(e.code, msg)
    except (urllib.error.URLError, OSError) as e:
        raise HostError(0, str(e))


def kv_url(cfg, key: str, ttl: int | None = None) -> str:
    url = "%s/accounts/%s/storage/kv/namespaces/%s/values/%s" % (
        API, cfg["account"], cfg["namespace"], urllib.parse.quote(key, safe=""))
    if ttl:
        url += "?expiration_ttl=%d" % ttl
    return url


def kv_put(cfg, key: str, body: bytes, ttl: int, http=None, content_type="application/octet-stream"):
    req = urllib.request.Request(kv_url(cfg, key, ttl), data=body, method="PUT",
                                 headers={"Authorization": "Bearer " + cfg["token"], "Content-Type": content_type})
    status, _, _ = _send(req, http)
    if status != 200:
        raise HostError(status, "KV PUT %s answered %s" % (key, status))


def kv_get(cfg, key: str, http=None):
    req = urllib.request.Request(kv_url(cfg, key), method="GET",
                                 headers={"Authorization": "Bearer " + cfg["token"]})
    try:
        _, _, body = _send(req, http)
    except HostError as e:
        if e.status == 404:
            return None
        raise
    return body


def kv_delete(cfg, key: str, http=None):
    req = urllib.request.Request(kv_url(cfg, key), method="DELETE",
                                 headers={"Authorization": "Bearer " + cfg["token"]})
    try:
        _send(req, http)
    except HostError as e:
        if e.status != 404:
            raise


def public_url(cfg, name: str, ext: str) -> str:
    return "%s/m/%s%s" % (cfg["host"], name, ext)


def head(url: str, http=None, timeout=30):
    """(status, content_length or None, content_type) from one HEAD — no body is pulled."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "DocOgaGrowthEngine/1.0"})
    try:
        status, headers, _ = _send(req, http, timeout=timeout)
    except HostError as e:
        return e.status, None, ""
    lower = {k.lower(): v for k, v in headers.items()}
    length = lower.get("content-length")
    return status, (int(length) if length and length.isdigit() else None), lower.get("content-type", "")


def wait_live(url: str, size: int, seconds: int, http=None, sleeper=time.sleep, delay=5):
    """KV is eventually consistent (up to ~60 s at the edge): poll HEAD until the worker
    answers 200 with the right length. Returns (live, waited_seconds, last_status)."""
    waited = 0
    status = None
    while True:
        status, length, _ = head(url, http)
        if status == 200 and (length is None or length == size):
            return True, waited, status
        if waited >= seconds:
            return False, waited, status
        sleeper(delay)
        waited += delay


def put(path: str, ttl_hours: float = DEFAULT_TTL_HOURS, verify_seconds: int = 180,
        env=None, root: Path = ROOT, http=None, sleeper=time.sleep, name: str | None = None):
    """Upload one file. Returns a dict with name/url/bytes/parts/live; raises HostError."""
    cfg = config(env, root)
    if cfg is None:
        raise HostError(2, "CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID not set")
    p = Path(path)
    if not p.is_file():
        raise HostError(2, "%s: no such file" % path)
    ext = p.suffix.lower()
    if ext not in EXTENSIONS:
        raise HostError(5, "%s: only %s can be hosted" % (p.name, ", ".join(sorted(EXTENSIONS))))
    size = p.stat().st_size
    if size == 0:
        raise HostError(5, "%s is empty" % p.name)
    if size > MAX_BYTES:
        raise HostError(5, "%s is %d bytes — over Instagram's %d MB Reel ceiling" % (p.name, size, MAX_BYTES // 1048576))
    if ext == ".mp4":
        with p.open("rb") as fh:
            headb = fh.read(12)
        if headb[4:8] != b"ftyp":
            raise HostError(5, "%s does not start with an MP4 ftyp box" % p.name)
    ttl = max(MIN_TTL_SECONDS, int(ttl_hours * 3600))
    name = name or new_name()
    if not NAME_RE.match(name):
        raise HostError(5, "bad media name")
    parts = 0
    with p.open("rb") as fh:
        while True:
            chunk = fh.read(PART_BYTES)
            if not chunk:
                break
            kv_put(cfg, "media:%s:%d" % (name, parts), chunk, ttl, http)
            parts += 1
    manifest = {"size": size, "parts": parts, "part_size": PART_BYTES, "type": EXTENSIONS[ext],
                "file": p.name, "put_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()), "ttl": ttl}
    kv_put(cfg, "media:" + name, json.dumps(manifest, separators=(",", ":")).encode("utf-8"), ttl, http,
           content_type="application/json")
    url = public_url(cfg, name, ext)
    live, waited, status = (False, 0, None)
    if verify_seconds > 0:
        live, waited, status = wait_live(url, size, verify_seconds, http, sleeper)
    return {"name": name, "url": url, "bytes": size, "parts": parts, "ttl": ttl,
            "live": live, "waited": waited, "status": status}


def delete(name: str, env=None, root: Path = ROOT, http=None) -> int:
    """Remove the manifest and every part. Returns the number of keys deleted (manifest included)."""
    cfg = config(env, root)
    if cfg is None:
        raise HostError(2, "CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID not set")
    if not NAME_RE.match(name or ""):
        raise HostError(5, "bad media name")
    parts = 0
    raw = kv_get(cfg, "media:" + name, http)
    if raw:
        try:
            parts = int(json.loads(raw.decode("utf-8", "replace")).get("parts") or 0)
        except (ValueError, AttributeError):
            parts = 0
    # The manifest first — the URL stops answering before any byte disappears.
    kv_delete(cfg, "media:" + name, http)
    n = 1
    for i in range(max(parts, 1)):
        kv_delete(cfg, "media:%s:%d" % (name, i), http)
        n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description="short-lived public media for Meta to fetch (worker KV)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("put", help="upload a file, print MEDIA_URL=")
    a.add_argument("file")
    a.add_argument("--ttl-hours", type=float, default=DEFAULT_TTL_HOURS)
    a.add_argument("--verify-seconds", type=int, default=180, help="poll HEAD until live; 0 = don't")
    d = sub.add_parser("delete", help="remove it now (it would expire on its own anyway)")
    d.add_argument("name")
    c = sub.add_parser("check", help="one HEAD against a URL")
    c.add_argument("url")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "put":
            r = put(args.file, args.ttl_hours, args.verify_seconds)
            print("hosted: %s (%d bytes in %d part%s, expires in %dh)" % (
                Path(args.file).name, r["bytes"], r["parts"], "" if r["parts"] == 1 else "s", r["ttl"] // 3600))
            if r["live"]:
                print("live: the worker answers 200 with the full length%s" % (
                    " after %ds" % r["waited"] if r["waited"] else ""))
            elif args.verify_seconds > 0:
                print("::warning title=media not live yet::%s answered %s after %ds — KV propagation "
                      "can lag; the publisher will wait for it too" % (r["url"], r["status"], r["waited"]))
            print("MEDIA_NAME=%s" % r["name"])
            print("MEDIA_URL=%s" % r["url"])
            print("MEDIA_BYTES=%d" % r["bytes"])
            print("MEDIA_PARTS=%d" % r["parts"])
            print("MEDIA_LIVE=%s" % ("yes" if r["live"] else "no"))
            return 0
        if args.cmd == "delete":
            n = delete(args.name)
            print("MEDIA_DELETED=%d" % n)
            return 0
        status, length, ctype = head(args.url)
        print("status=%s length=%s type=%s" % (status, length, ctype))
        return 0 if status == 200 else 6
    except HostError as e:
        print("::error title=media host::%s" % e.message)
        if args.cmd == "put":
            print("MEDIA_LIVE=no")
        return 2 if e.status == 2 else 5 if e.status == 5 else 6


if __name__ == "__main__":
    sys.exit(main())
