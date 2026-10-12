#!/usr/bin/env python3
"""
IG CONNECT — the moment the user pastes his Meta credentials, this:
  1. exchanges the short-lived token for a 60-day long-lived token
  2. discovers his Instagram Business user id (via his Facebook Page)
  3. validates the publish permissions
  4. checks the content-publishing quota
  5. prints a readiness report (and the exact lines to append to .worker-secrets.env)

Usage:
  1. Create /tmp/ig_creds.txt with:
     APP_ID=your_facebook_app_id
     APP_SECRET=your_facebook_app_secret
     SHORT_TOKEN=your_short_lived_user_access_token

  2. Run: python3 tools/ig_connect.py
"""
import json, sys, urllib.parse, urllib.request

# Same rule as tools/ig_publish.py: one place to move the Graph API version.
API_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH = f"https://graph.facebook.com/{API_VERSION}"


def get(url, params):
    u = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(u, headers={"User-Agent": "DocOga-connect/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": {"message": f"HTTP {e.code}"}}


def main():
    creds = {}
    creds_path = "/tmp/ig_creds.txt"
    try:
        for line in open(creds_path):
            if "=" in line:
                k, v = line.strip().split("=", 1)
                creds[k.strip()] = v.strip()
    except FileNotFoundError:
        print(f"❌ {creds_path} not found")
        print("Create it with: APP_ID=... / APP_SECRET=... / SHORT_TOKEN=...")
        sys.exit(1)

    app_id = creds.get("APP_ID", "")
    app_secret = creds.get("APP_SECRET", "")
    short = creds.get("SHORT_TOKEN", "")

    if not (app_id and app_secret and short):
        print("❌ /tmp/ig_creds.txt needs APP_ID=, APP_SECRET=, SHORT_TOKEN=")
        sys.exit(1)

    # 1. Exchange for 60-day long-lived token
    print("── 1. exchange for 60-day long-lived token ──")
    r = get(f"{GRAPH}/oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short,
    })
    if "access_token" not in r:
        print("❌ exchange failed:", json.dumps(r)[:300])
        sys.exit(1)
    token = r["access_token"]
    expires = r.get("expires_in", "?")
    print(f"✅ long-lived token (valid {expires}s ≈ {int(expires)//86400} days)")

    # 2. Find the Instagram Business account
    print("\n── 2. find the Instagram Business account ──")
    pages = get(f"{GRAPH}/me/accounts", {
        "fields": "name,instagram_business_account{id,username,followers_count,media_count}",
        "access_token": token,
    })
    if "data" not in pages or not pages["data"]:
        print("❌ no Facebook Pages found — was the Page created and the IG account linked?")
        print(json.dumps(pages)[:300])
        sys.exit(1)

    ig = None
    for p in pages["data"]:
        if p.get("instagram_business_account"):
            ig = p["instagram_business_account"]
            ig["page"] = p["name"]
            break
    if not ig:
        print("❌ Pages exist but none has a linked Instagram account:")
        print(json.dumps(pages)[:300])
        sys.exit(1)
    print(f"✅ @{ig['username']} — followers {ig.get('followers_count')} "
          f'— page "{ig["page"]}" — IG ID {ig["id"]}')

    # 3. Verify permissions on the token
    print("\n── 3. verify permissions on the token ──")
    perms = get(f"{GRAPH}/me/permissions",
                {"access_token": token})
    have = {p["permission"] for p in perms.get("data", [])
            if p.get("status") == "granted"}
    print("granted:", ", ".join(sorted(have)) or "(none)")
    need_any = [p for p in ("instagram_content_publish",
                            "instagram_business_content_publish")
                if p in have]
    if not need_any:
        print("❌ publishing permission NOT granted "
              "— regenerate the token with the instagram permissions ticked")
        sys.exit(1)
    print(f"✅ publishing permission: {need_any[0]}")

    # 4. Publishing quota
    print("\n── 4. publishing quota ──")
    q = get(f"{GRAPH}/{ig['id']}/content_publishing_limit",
            {"fields": "config,quota_usage", "access_token": token})
    print(json.dumps(q, indent=2))

    # 5. Readiness report
    print("\n═══════════════════════════════════════════════════════")
    print("READY — append to .worker-secrets.env (and Pages secrets)")
    print("═══════════════════════════════════════════════════════")
    print(f"IG_APP_ID={app_id}")
    print(f"IG_APP_SECRET={app_secret[:6]}…(full in file)")
    print(f"IG_TOKEN={token[:12]}…(full in file)")
    print(f"IG_USER_ID={ig['id']}")
    print()
    print("These are the lines to add to your .worker-secrets.env:")
    print(f'  IG_APP_ID={app_id}')
    print(f'  IG_APP_SECRET={app_secret}')
    print(f'  IG_TOKEN={token}')
    print(f'  IG_USER_ID={ig["id"]}')


if __name__ == "__main__":
    main()