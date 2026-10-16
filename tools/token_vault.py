#!/usr/bin/env python3
"""
tools/token_vault.py — how an unattended lane survives a 60-day token
======================================================================

The problem this exists for, stated precisely, because the shape of the fix follows from it:

* Meta's user access tokens for Threads and Instagram live **60 days** and are only
  extended by *calling the refresh endpoint with the current token*. A lane that refreshes
  and then loses the new value has not extended anything — it has just reset a clock it
  cannot read.
* The refreshed value has to be written somewhere the *next* run can read.
* A GitHub Actions job **cannot** write its own repository secrets: the secrets API needs
  the `secrets` permission, and the `GITHUB_TOKEN` minted for a workflow does not carry it
  (confirmed by GitHub staff in community discussion #160560, 10 Jun 2024). `gh secret set`
  from inside a lane is therefore not an option — and that is the end of the obvious design.

So the vault is: **the ciphertext lives in the repo, the key lives in Actions.**

    logs/threads_token.box   committed by the lane, readable by anyone with repo access,
                             and useless without the key
    SOCIAL_TOKEN_KEY         a GitHub Actions secret, 32 random bytes, set once by a human
                             and never rotated by a machine (rotating it means re-sealing)

AES-256-GCM with the secret *name* as additional authenticated data, so a `.box` copied
from another lane, or a `THREADS_TOKEN` blob renamed to `IG_ACCESS_TOKEN`, fails to open
rather than silently handing the wrong credential to the wrong API.

Threat model, honestly:

* Against anyone without `SOCIAL_TOKEN_KEY` — including a reader of this private repo's
  history, a leaked `logs/` tree, or a fork — the token is not recoverable.
* Against an attacker who can read Actions secrets, this buys nothing: they can read the
  token you already stored there. It was never a defence against that, and anyone who
  sells it as one is selling the wrong thing.
* Against the *platform clock* it buys everything: the lane refreshes the token before
  expiry, seals the new pair back into `logs/`, and the next run reads it. That is what
  makes "no manual intervention after setup" true for a Meta lane instead of true for
  eight weeks.

If `cryptography` is not importable this tool **refuses to run**. It does not fall back to
plaintext, and it does not fall back to base64 — a security tool that degrades quietly
into an exfiltration tool is worse than no tool. On a runner that means one
`pip install cryptography` line, which the workflows already have a step for.

Usage
-----
    python3 tools/token_vault.py seal  --name THREADS_TOKEN --json /tmp/refresh.json
    python3 tools/token_vault.py open  --name THREADS_TOKEN --out /tmp/threads_token
    python3 tools/token_vault.py status --name THREADS_TOKEN      # expiry only, never a value

Exit codes: 0 ok · 2 no key · 3 no vault file (bootstrap: use the secret) ·
4 vault unreadable (key rotated? file damaged?) · 5 usage error · 6 crypto library missing
"""

import argparse
import base64
import binascii
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VAULT_DIR = Path("logs")
KEY_ENV = "SOCIAL_TOKEN_KEY"
EXPIRES_WARN_DAYS = 21  # long enough to re-consent in one sitting, short enough to matter


def _fail(message, code):
    print("token_vault: %s" % message, file=sys.stderr)
    return code


def _vault_path(name):
    return VAULT_DIR / ("%s.box" % name.lower())


def _load_key():
    """32 raw bytes from SOCIAL_TOKEN_KEY, accepted as hex or base64, and never printed."""
    raw = (os.environ.get(KEY_ENV) or "").strip()
    if not raw:
        return None
    for decode in (bytes.fromhex, lambda s: base64.b64decode(s, validate=True)):
        try:
            key = decode(raw)
        except (ValueError, binascii.Error):
            continue
        if len(key) == 32:
            return key
    return False  # present but the wrong shape — a different answer from "missing"


def _cipher():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        return None
    return AESGCM


def seal(name, plaintext, expires_at=None, path=None, out=sys.stdout):
    """Encrypt `plaintext` under the vault key and write the box. Returns 0 or an exit code."""
    AESGCM = _cipher()
    if AESGCM is None:
        return _fail("the cryptography module is not installed; refusing to store a token "
                     "without it (no plaintext fallback)", 6)
    key = _load_key()
    if key is None:
        return _fail("%s is not set. One human tap: "
                     "gh secret set %s --body \"$(openssl rand -hex 32)\"" % (KEY_ENV, KEY_ENV), 2)
    if key is False:
        return _fail("%s must decode to exactly 32 bytes (hex or base64); got something else"
                     % KEY_ENV, 2)

    box = VAULT_DIR / ("%s.box" % name.lower()) if path is None else Path(path)
    # A vault file placed under site/ would be published to the whole internet by the
    # Pages deploy, ciphertext or not — and a plaintext token left beside it would be a
    # leak with no second act. Refuse the directory outright.
    if str(box).startswith("site/") or str(box).startswith("./site/"):
        return _fail("refusing to write a vault file inside site/ — that directory is "
                     "publicly deployed", 5)

    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), name.encode("utf-8"))
    payload = {
        "v": 1,
        "alg": "A256GCM",
        "name": name,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ct).decode("ascii"),
        "minted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if expires_at:
        payload["expires_at"] = expires_at

    box.parent.mkdir(parents=True, exist_ok=True)
    tmp = box.with_suffix(box.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, box)  # atomic: a run killed mid-write must not leave a half box
    print("token_vault: sealed %s into %s (%d bytes of ciphertext)" % (name, box, len(ct)),
          file=out)
    return 0


def open_box(name, path=None):
    """Return (plaintext, payload) or raise ValueError with a reason. Never prints either."""
    AESGCM = _cipher()
    if AESGCM is None:
        raise RuntimeError("cryptography module missing")
    box = _vault_path(name) if path is None else Path(path)
    key = _load_key()
    if key is None:
        raise PermissionError("%s is not set" % KEY_ENV)
    if key is False:
        raise PermissionError("%s is not 32 bytes" % KEY_ENV)
    payload = json.loads(box.read_text(encoding="utf-8"))
    if payload.get("name") != name:
        raise ValueError("vault file is for %r, not %r" % (payload.get("name"), name))
    plaintext = AESGCM(key).decrypt(
        base64.b64decode(payload["nonce"]),
        base64.b64decode(payload["ciphertext"]),
        name.encode("utf-8"),
    )
    return plaintext.decode("utf-8"), payload


def status(name, path=None, out=sys.stdout):
    """Say how long the stored credential has left. This is the only thing a lane prints."""
    box = _vault_path(name) if path is None else Path(path)
    if not box.exists():
        print("TOKEN_VAULT=%s absent — the lane will use the bootstrap secret" % box, file=out)
        return 3
    try:
        payload = json.loads(box.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        print("::warning title=Token vault unreadable::%s could not be parsed (%s)" % (box, exc),
              file=out)
        return 4
    expires = payload.get("expires_at")
    print("TOKEN_VAULT=%s sealed_at=%s expires_at=%s"
          % (box, payload.get("minted_at", "?"), expires or "unknown"), file=out)
    if not expires:
        print("::warning title=Token vault has no expiry recorded::nothing is counting down, "
              "so a 60-day Meta token will expire without a warning", file=out)
        return 0
    try:
        when = datetime.fromisoformat(expires)
    except ValueError:
        print("::warning title=Token vault expiry is unparsable::%r" % expires, file=out)
        return 0
    days = (when - datetime.now(timezone.utc)).days
    print("TOKEN_EXPIRES_IN_DAYS=%d" % days, file=out)
    if days < 0:
        print("::error title=Stored token is expired::the refresh chain broke %d days ago; a "
              "human must re-consent once, then the lane keeps it alive again" % abs(days), file=out)
        return 4
    if days <= EXPIRES_WARN_DAYS:
        print("::warning title=Token expires in %d days::the lane is still refreshing; this is "
              "a heads-up that the refresh chain has been failing quietly" % days, file=out)
    return 0


def read_refresh_response(path):
    """`(access_token, expires_at, saw_a_refresh_token)` from a Meta refresh response.

    The box holds **one** secret: the bare access token. Threads and Instagram both roll the
    access token itself (`grant_type=th_refresh_token` / `ig_refresh_token` exchange a long-lived
    token for a new long-lived token), so nothing else needs keeping — and the metadata that
    travels *beside* the ciphertext in the box file is not encrypted, so a second secret belongs in
    a box of its own, never there.
    """
    text = Path(path).read_text(encoding="utf-8")
    try:
        blob = json.loads(text)
    except json.JSONDecodeError:
        # A refresh helper that chats on stdout corrupts its own JSON. Take the last line that
        # is an object rather than failing — and name the real problem if there is none.
        blob = None
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    blob = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        if blob is None:
            raise SystemExit(_fail("%s is not JSON (the refresh helper printed something else "
                                   "on stdout) — refusing to seal" % path, 5))
    if not isinstance(blob, dict):
        raise SystemExit(_fail("%s is not a JSON object" % path, 5))
    token = blob.get("access_token") or blob.get("token")
    if not token:
        raise SystemExit(_fail("%s has no access_token key — refusing to seal a value no reader "
                               "will accept" % path, 5))
    expires_at = None
    if blob.get("expires_in"):
        expires_at = (datetime.now(timezone.utc)
                      + timedelta(seconds=int(blob["expires_in"]))).isoformat(timespec="seconds")
    return str(token), expires_at, bool(blob.get("refresh_token"))


def _read_plaintext(args):
    """The exact bytes the next run will authenticate with — see the note in main().

    `open --out` writes whatever this returns into the file the lane passes to `--token-file`,
    and the publisher sends that file's contents as its bearer token. Which is why sealing
    Meta's whole JSON response is fatal rather than untidy: it worked here on day 1 (the
    bootstrap secret is a bare token) and every day after that would have authenticated with
    `{"access_token": "AAA", "refresh_token": null, …}` and been answered `code 190 Invalid
    OAuth access token`. Pinned cross-process by
    tools/tests/test_meta_lanes.py::VaultPipeline, because every in-process test of one verb at a
    time was green while the lane was dead.
    """
    if args.stdin:
        value = sys.stdin.read().strip()
        if not value:
            raise SystemExit(_fail("stdin was empty — refusing to seal an empty token", 5))
        return value
    if args.json:
        return read_refresh_response(args.json)[0]
    raise SystemExit(_fail("seal needs --stdin or --json", 5))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Keep a rolling platform token alive without a human")
    parser.add_argument("verb", choices=["seal", "open", "status"])
    parser.add_argument("--name", required=True, help="the Actions secret this box stands for")
    parser.add_argument("--out", help="open: file to write the plaintext to (0600, /tmp recommended)")
    parser.add_argument("--in", dest="path", help="vault file to read/write (default logs/<name>.box)")
    parser.add_argument("--json", help="seal: a Meta refresh response to take access_token from")
    parser.add_argument("--stdin", action="store_true", help="seal: read the value from stdin")
    parser.add_argument("--expires-at", help="seal: ISO date the new token dies, if you know it")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.verb == "status":
        return status(args.name, args.path)

    if args.verb == "seal":
        expires = args.expires_at
        dropped_refresh = False
        if args.json:
            plaintext, derived, dropped_refresh = read_refresh_response(args.json)
            if not expires:
                expires = derived
        else:
            plaintext = _read_plaintext(args)
        rc = seal(args.name, plaintext, expires_at=expires, path=args.path)
        if rc == 0 and dropped_refresh:
            # Loud, because the day Meta starts rotating refresh tokens is the day this lane
            # starts dying again — and "we chose not to store it" is not something to discover
            # from a 401 sixty days later.
            print("::warning title=a refresh token was dropped::the response carried "
                  "`refresh_token`, which this vault does not store (Threads and Instagram roll "
                  "the access token, so there is normally nothing to keep). If Meta has changed "
                  "shape, the fix is one more box: seal --name <LANE>_REFRESH_TOKEN.",
                  file=sys.stderr)
        return rc

    # open
    try:
        plaintext, _payload = open_box(args.name, args.path)
    except FileNotFoundError:
        print("token_vault: no vault file for %s — the bootstrap secret is the source" % args.name,
              file=sys.stderr)
        return 3
    except PermissionError as exc:
        return _fail(str(exc), 2)
    except Exception as exc:  # a damaged box must read as "unreadable", never as "no token"
        return _fail("vault for %s could not be opened (%s). The key rotated, or the file is "
                     "damaged. The lane will fall back to the bootstrap secret." % (args.name, exc), 4)
    if not args.out:
        return _fail("open needs --out: a token is not something to print into a run log", 5)
    # A box sealed by the version above that stored the whole JSON response still has to open:
    # unwrapping three lines here beats a lane that dies on whichever commit happened to seal it.
    stripped = (plaintext or "").strip()
    if stripped.startswith("{") and '"access_token"' in stripped:
        try:
            inner = json.loads(stripped).get("access_token")
        except ValueError:
            inner = None
        if inner:
            print("token_vault: note — the box held a JSON response, not a token; unwrapped it. "
                  "Re-seal once so the next run reads a plain value.", file=sys.stderr)
            plaintext = str(inner)
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(plaintext)
    print("token_vault: wrote %s (0600, contents never printed)" % target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
