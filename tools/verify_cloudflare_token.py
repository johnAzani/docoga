#!/usr/bin/env python3
"""Read-only, fail-closed Cloudflare authentication diagnostic.

Never print credentials, account IDs, API bodies or upstream error messages.
Verification proves activity only; the account read checks account access, not
Workers edit permission. Wrangler must still succeed before release is claimed.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = "https://api.cloudflare.com/client/v4"


class CheckFailed(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a bearer credential to a redirect target.
        return None


def request(path, token):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=25) as response:
            return response.status, response.read(1024 * 1024)
    except urllib.error.HTTPError as error:
        try:
            return error.code, error.read(1024 * 1024)
        finally:
            error.close()
    except Exception:
        # Exception strings can include URLs/account IDs. Do not surface them.
        raise CheckFailed("Cloudflare request failed (network/transport).") from None


def check_response(label, code, body):
    print(f"{label}: HTTP {code if type(code) is int else 'unknown'}", flush=True)
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        raise CheckFailed("Cloudflare response was not valid JSON.") from None
    if not isinstance(data, dict):
        raise CheckFailed("Cloudflare response had an unexpected shape.")
    errors = data.get("errors")
    if isinstance(errors, list):
        codes = [str(e["code"]) for e in errors
                 if isinstance(e, dict) and type(e.get("code")) is int]
        if codes:
            print(f"{label}: API error codes {','.join(codes)}", flush=True)
    return data


def verify(token, account, fetch=request):
    if not token or any(c.isspace() for c in token) or not re.fullmatch(r"[a-fA-F0-9]{32}", account):
        raise CheckFailed("Required token/account configuration missing or malformed.")
    path = "user"
    code, body = fetch("/user/tokens/verify", token)
    data = check_response("user token check", code, body)
    # Only an explicit API client rejection can trigger compatibility
    # fallback. Network, throttling, server, malformed and inactive responses stop.
    errors = data.get("errors")
    auth_rejection = (
        code in (400, 401, 403, 404) and data.get("success") is False
        and isinstance(errors, list) and bool(errors)
        and all(isinstance(e, dict) and type(e.get("code")) is int for e in errors)
    )
    if auth_rejection:
        path = "account"
        code, body = fetch(f"/accounts/{account}/tokens/verify", token)
        data = check_response("account token check", code, body)
    result = data.get("result")
    if not (code == 200 and data.get("success") is True
            and isinstance(result, dict) and result.get("status") == "active"):
        raise CheckFailed("Cloudflare token verification did not confirm an active token.")
    print(f"Cloudflare token active; verification path={path}.", flush=True)
    code, body = fetch(f"/accounts/{account}/workers/scripts", token)
    data = check_response("deployment account read check", code, body)
    if not (code == 200 and data.get("success") is True and isinstance(data.get("result"), list)):
        raise CheckFailed("Cloudflare deployment account read check failed.")
    print("Deployment account accessible; edit permissions still require successful deploy.", flush=True)


def main():
    try:
        verify(os.environ.get("CF_TOKEN", ""), os.environ.get("CF_ACCOUNT", ""))
    except CheckFailed as error:
        print(f"::error::{error}", flush=True)
        return 1
    except Exception:
        print("::error::Unexpected authentication check failure (details withheld).", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
