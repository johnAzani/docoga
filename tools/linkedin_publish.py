#!/usr/bin/env python3
"""linkedin_publish.py — one post to the owner's LinkedIn profile, three mornings a week, ₦0.

Why LinkedIn (research, 17 Oct 2026): 14.0M Nigerians, the largest group aged 25–34 (7.7M) —
Tunde the HR officer who needs payslips, Amaka the freelancer who needs invoices, Okafor the
landlord who needs a tenancy agreement that holds. No other channel the repo posts to reaches
that reader at work, in the morning, in a reading mood.

What is free and what is not (checked against LinkedIn's docs):
  * "Share on LinkedIn" is a self-serve product — add it in the Developer Portal, no review —
    and grants `w_member_social`: post to the authorizing member's OWN profile. Company Pages
    need the vetted Community Management API; we do not need it.
  * Access tokens live 60 days. Ordinary apps get NO refresh token; the member re-authorizes.
    So this lane keeps the date it first saw each token and warns from day 50, and on a 401 it
    says exactly what to do. A dead token is the one tap the owner cannot be spared.
  * Rate limit 150 requests per member per day. We make three a week.

The post is the brain's pack for the day (headline, lines, the send line, the deep link) in
LinkedIn's "little text" format (reserved characters escaped), or the hand-written rotation
when there is no pack. Hashtags are dropped: LinkedIn 2026 ranks dwell time and comments,
not tags, and an escaped hashtag reads as noise.

Usage
    python3 tools/linkedin_publish.py --probe
    python3 tools/linkedin_publish.py --day 2026-10-20 [--dry-run] [--force]
    python3 tools/linkedin_publish.py --text "…" [--link https://docoga.com.ng/…]
Exit 0 sent/duplicate/dormant, 3 credentials (token dead or missing scope), 5 copy, 6 API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))

import brain_drafts  # noqa: E402

API = "https://api.linkedin.com"
VERSION = os.environ.get("LINKEDIN_VERSION", "202609")
LEDGER = Path(os.environ.get("DOCOGA_LINKEDIN_LEDGER") or (ROOT / "logs" / "linkedin_posts.json"))
TOKEN_DAYS = 60
WARN_DAYS = 50
COMMENTARY_MAX = 3000
RESERVED = r"\|{}@[]()<>#*_~"
KEEP = 400


class ApiError(Exception):
    def __init__(self, status, body, cause):
        super().__init__("%s %s" % (status, cause))
        self.status, self.body, self.cause = status, body, cause

    @property
    def blurb(self):
        try:
            data = json.loads(self.body)
            return str(data.get("message") or data.get("error_description") or data.get("error") or self.body)[:200]
        except ValueError:
            return str(self.body)[:200]


def _http(method, url, token, body=None, timeout=45):
    headers = {"Authorization": "Bearer " + token, "LinkedIn-Version": VERSION,
               "X-Restli-Protocol-Version": "2.0.0", "User-Agent": "DocOga-linkedin/1.0 (+https://docoga.com.ng)"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers or {})
    except (urllib.error.URLError, OSError) as e:
        raise ApiError(0, str(e), "transport")


http = _http


def classify(status, body):
    low = (body or "").lower()
    if status in (401, 403) or "expired" in low or "revoked" in low or "invalid access token" in low:
        return "credentials"
    if "permission" in low or "not enough permissions" in low or "access_denied" in low:
        return "credentials"
    if status == 429:
        return "quota"
    if status == 422 or status == 400:
        return "copy"
    return "api"


def fingerprint(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()[:10]


# ───────────────────────────── copy ─────────────────────────────
def escape(text):
    """LinkedIn's little text format: reserved characters must be backslash-escaped or the
    post is rejected (or renders with holes). URLs are left alone — they are detected as links."""
    out = []
    for token in re.split(r"(https?://\S+)", text or ""):
        if token.startswith("http"):
            out.append(token)
        else:
            out.append("".join("\\" + ch if ch in RESERVED else ch for ch in token))
    return "".join(out)


def strip_hashtags(text):
    lines = [re.sub(r"(^|\s)#\w+", "", ln).rstrip() for ln in (text or "").splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def copy_for(day):
    """(plain text, link, source) for the day: the brain's pack, else the rotation."""
    pack = brain_drafts.draft_for(day)
    if pack:
        return (brain_drafts.tag_links(strip_hashtags(brain_drafts.post_text(pack)), "linkedin"),
                brain_drafts.tag_links(brain_drafts.link_for(pack), "linkedin"), "brain:%s" % pack.get("theme"))
    import random
    from telegram_mdv2 import to_plain
    import generate_telegram_content as tg
    rng = random.Random("docoga-linkedin-%s" % day.isoformat())
    post_type = rng.choice([t for t in tg.WEEKLY_SCHEDULE.get(day.weekday(), ["promo"])])
    plain = strip_hashtags(to_plain(rng.choice(tg.TEMPLATES[post_type])).strip())
    link = next(iter(re.findall(r"https?://\S+", plain)), "https://docoga.com.ng")
    return plain, link, "rotation:%s" % post_type


def check_copy(text):
    problems = []
    if not (text or "").strip():
        problems.append("the post is empty")
    if len(text or "") > COMMENTARY_MAX:
        problems.append("%d characters is over LinkedIn's %d" % (len(text), COMMENTARY_MAX))
    for url in re.findall(r"https?://\S+", text or ""):
        if "docoga.com.ng" not in url:
            problems.append("link %s is not ours" % url[:40])
    return problems


# ───────────────────────────── ledger ─────────────────────────────
def load_ledger(path=None):
    try:
        data = json.loads(Path(path or LEDGER).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"entries": [], "tokens": {}}
    except (OSError, ValueError):
        return {"entries": [], "tokens": {}}


def save_ledger(data, path=None):
    path = Path(path or LEDGER)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["entries"] = data.get("entries", [])[-KEEP:]
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def token_age_days(ledger, token, now=None):
    """Days since this token was first seen here — the only clock we have for a 60-day token."""
    now = now or datetime.now(timezone.utc)
    fp = fingerprint(token)
    tokens = ledger.setdefault("tokens", {})
    first = tokens.get(fp)
    if not first:
        tokens[fp] = now.isoformat(timespec="seconds")
        return 0
    try:
        return (now - datetime.fromisoformat(first)).days
    except ValueError:
        return 0


def key_for(text):
    return hashlib.sha256(re.sub(r"\s+", " ", (text or "").strip().lower()).encode("utf-8")).hexdigest()[:16]


# ───────────────────────────── api ─────────────────────────────
def me(token):
    status, body, _ = http("GET", API + "/v2/userinfo", token)
    if status != 200:
        raise ApiError(status, body, classify(status, body))
    data = json.loads(body)
    return {"sub": data.get("sub"), "name": data.get("name") or "", "urn": "urn:li:person:%s" % data.get("sub")}


def create_post(token, author_urn, text, link=None, title=None):
    body = {"author": author_urn, "commentary": escape(text), "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
    if link:
        body["content"] = {"article": {"source": link, "title": (title or "DocOga — Nigeria's document engine")[:400]}}
    status, resp, headers = http("POST", API + "/rest/posts", token, body)
    if status in (400, 422) and "content" in body:
        # The article card is a bonus; the words are the post. Retry without the card.
        print("::notice title=LinkedIn article card refused::%s — posting the text alone" % resp[:160])
        body.pop("content", None)
        status, resp, headers = http("POST", API + "/rest/posts", token, body)
    if status not in (200, 201):
        raise ApiError(status, resp, classify(status, resp))
    urn = headers.get("x-restli-id") or headers.get("X-RestLi-Id") or headers.get("x-linkedin-id") or ""
    return urn


def permalink(urn):
    return "https://www.linkedin.com/feed/update/%s/" % urn if urn else "https://www.linkedin.com/in/me/recent-activity/all/"


# ───────────────────────────── main ─────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(description="post to the owner's LinkedIn profile")
    ap.add_argument("--probe", action="store_true", help="who is the token? how old? nothing posted")
    ap.add_argument("--day", help="YYYY-MM-DD (default: today in Lagos)")
    ap.add_argument("--text")
    ap.add_argument("--link")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--token-file")
    a = ap.parse_args(argv)

    token = ""
    if a.token_file:
        try:
            token = Path(a.token_file).read_text(encoding="utf-8").strip()
        except OSError:
            token = ""
    token = token or (os.environ.get("LINKEDIN_ACCESS_TOKEN") or "").strip()
    if not token:
        print("::notice title=LinkedIn lane dormant::LINKEDIN_ACCESS_TOKEN is not set — add the secret from the "
              "Developer Portal (Share on LinkedIn → w_member_social) and this lane wakes up")
        print("LINKEDIN_RESULT=dormant")
        return 0

    ledger = load_ledger()
    age = token_age_days(ledger, token)
    print("token: fingerprint %s, first seen %d day(s) ago" % (fingerprint(token), age))
    if age >= WARN_DAYS:
        print("::warning title=LinkedIn token is %d days old::it dies at %d — re-authorize in the Developer Portal "
              "(Auth tab → OAuth 2.0 tools → generate token with w_member_social) and update LINKEDIN_ACCESS_TOKEN" % (age, TOKEN_DAYS))
    print("LINKEDIN_TOKEN_AGE=%d" % age)

    try:
        who = {"name": "dry run", "urn": "urn:li:person:dry-run"} if (a.dry_run and not a.probe) else me(token)
    except ApiError as exc:
        if exc.cause == "credentials":
            print("::error title=LinkedIn token dead::%s — LinkedIn tokens live 60 days and self-serve apps get no refresh token. "
                  "Re-authorize (Developer Portal → your app → Auth → OAuth 2.0 tools → w_member_social) and paste the new token "
                  "into the LINKEDIN_ACCESS_TOKEN secret" % exc.blurb)
        else:
            print("::error title=LinkedIn unreachable (%s)::%s" % (exc.cause, exc.blurb))
        print("LINKEDIN_RESULT=failed")
        print("LINKEDIN_CAUSE=%s" % exc.cause)
        save_ledger(ledger)
        return 3 if exc.cause == "credentials" else 6
    print("posting as %s (%s)" % (who["name"] or "member", who["urn"]))
    if a.probe:
        print("LINKEDIN_RESULT=probed")
        save_ledger(ledger)
        return 0

    if a.text:
        text, link, source = a.text.strip(), a.link, "cli"
    else:
        day = date.fromisoformat(a.day) if a.day else datetime.now(timezone(timedelta(hours=1))).date()
        text, link, source = copy_for(day)
    problems = check_copy(text)
    if problems:
        for p in problems:
            print("::error title=copy rejected::%s" % p)
        print("LINKEDIN_RESULT=refused")
        print("LINKEDIN_CAUSE=copy")
        return 5
    key = key_for(text)
    print("copy: %s, %d characters, key %s" % (source, len(text), key))
    dup = next((e for e in ledger.get("entries", []) if e.get("key") == key), None)
    if dup and not a.force:
        print("refused-a-duplicate: this text went out on %s — %s" % (dup.get("recorded_at", "?")[:10], dup.get("url", "")))
        print("LINKEDIN_RESULT=duplicate")
        save_ledger(ledger)
        return 0
    if a.dry_run:
        print("--- dry run — the post that would go out ---")
        print(text)
        print("LINKEDIN_RESULT=dry-run")
        return 0
    try:
        urn = create_post(token, who["urn"], text, link=link, title=text.splitlines()[0][:120] if text else None)
    except ApiError as exc:
        print("::error title=LinkedIn post failed (%s)::%s" % (exc.cause, exc.blurb))
        print("LINKEDIN_RESULT=failed")
        print("LINKEDIN_CAUSE=%s" % exc.cause)
        return {"credentials": 3, "copy": 5}.get(exc.cause, 6)
    url = permalink(urn)
    ledger.setdefault("entries", []).append({"recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "key": key,
                                             "urn": urn, "url": url, "source": source, "characters": len(text),
                                             "run_id": os.environ.get("GITHUB_RUN_ID", "")})
    save_ledger(ledger)
    print("✅ posted: %s" % url)
    print("LINKEDIN_RESULT=sent")
    print("LINKEDIN_URL=%s" % url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
