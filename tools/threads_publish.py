#!/usr/bin/env python3
"""
tools/threads_publish.py — publish one text post to Threads, and prove it landed
================================================================================

Why a text-first lane exists when Instagram needs pixels

--------------------------------------------------------
Threads is the only Meta surface where a post is *words*. Instagram's content
publishing API requires media at a public URL Meta can fetch; Threads' TEXT container
needs nothing but a string. That removes the whole class of infrastructure that made the
Instagram lane unshippable on its own — no CDN, no upload, no wait for a deploy — so the
lane can be genuinely unattended the day two secrets exist. It is also where DocOga's
copy reads best: a 500-character legal explanation is the natural unit.

The rules this file obeys are the ones every DocOga lane now shares, and they are the
reason it is safe to hand to a cron with nobody watching:

  * **A refusal is not a failure.** If the exact wording is already on the profile, print
    the permalink, exit 0, publish nothing. Duplicate = the message's own words, never
    "similar": two paraphrases of the same caution-fee rule are two posts, and Threads is
    a conversation where the second one is allowed to exist.
  * **The guard is asked of the platform, not remembered locally.** `GET
    /{user}/threads?fields=text` is the truth about what is on the profile; the ledger in
    `logs/threads_sent.json` is only what this repo remembers. The ledger is read by the
    workflow *first* (free, offline, survives a dead API); this file's check is the last
    thing before sending. If the profile list cannot be read, the post goes out anyway and
    the run says so — an unverifiable page must never block a legitimate post.
  * **Failure is loud, classified, and never silent-green.** Every path prints
    `THREADS_RESULT=`/`THREADS_CAUSE=` and returns a non-zero exit code on failure. The
    sibling Instagram publisher used to `return None` on a failed publish, which exited 0:
    a red lane wearing a green tick. That mistake is not repeated here, and there is a
    test named after it.
  * **A token is never printed.** Only a 10-character fingerprint of its SHA-256 goes
    into logs, so a failure can say *which* credential was rejected without leaking it.

Endpoints (host `graph.threads.net`, version `v1.0` — not `graph.facebook.com`, which is
the single most common mistake in Threads integrations):

    GET  /{user-id}/threads?fields=text,permalink,created_time&limit=N   the duplicate guard
    GET  /{user-id}/threads_publishing_limit?fields=config,quota_usage    the 250-post clock
    POST /{user-id}/threads          {text, link_attachment, reply_control} → {id}  container
    POST /{user-id}/threads_publish  {creation_id}                        → {id}    the post
    GET  /{media-id}?fields=permalink,text                                 read-back
    GET  /{user-id}/refresh_access_token?grant_type=th_refresh_token        the 60-day clock

Stdlib only: no `requests`, no install step, nothing to go wrong on a runner at 08:45
UTC while nobody is awake.

Exit codes
    0  published · refused a duplicate · probe fine · dry run
    2  config missing (THREADS_USER_ID / a token from anywhere)
    3  token rejected or expired (credentials)
    4  publishing quota used up
    5  our copy is not sendable (over 500, over 5 links) or bad usage — a bug, not an outage
    6  API failure we do not recognise (the raw message is printed, redacted)
    7  published but the read-back disagrees (verification)

Usage
    python3 tools/threads_publish.py --probe
    python3 tools/threads_publish.py --from-json assets/threads/threads_content_latest.json
    python3 tools/threads_publish.py --text "one-off" --dry-run
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_HOST = os.environ.get("THREADS_API_HOST", "https://graph.threads.net/v1.0")
USER_AGENT = "DocOgaGrowthEngine/1.0 (unattended publisher)"

MAX_COST = 500
LINK_LIMIT = 5

# Meta's own machine-readable strings, matched in order. Anything unclassified still
# prints the raw (redacted) response body, because the way a new failure mode gets
# fixed is by being readable — a classifier that swallows the message is how the
# Telegram lane stayed down for five days.
CAUSES = (
    ("credentials", ("invalid oauth access token", "error code 190", "error subcode 460",
                     "expired", "please login again", "supports-callers-with-valid-authorization")),
    ("permission", ("permission", "requires authorization", "not approved", "(#200)",
                    "app is not authorized", "available in development mode")),
    ("quota", ("THREADS_PUBLISHING_LIMIT_EXCEEDED", "publishing limit", "rate limit",
               "too many requests", "error code 613", "error code 32")),
    ("account", ("professional account", "private account", "not eligible",
                 "must be a public", "account type")),
    ("copy", ("LINK_LIMIT_EXCEEDED", "too long", "character", "INVALID_ASPEC_RATIO",
              "invalid media")),
    ("state", ("THREADS_MEDIA_CONTAINER_ID_INVALID", "container has expired", "not found",
               "cannot be published", "IN_PROGRESS")),
)

REDACTIONS = (
    (re.compile(r"(access_token=)[^&\s\"]+"), r"\1[redacted]"),
    (re.compile(r"(\"access_token\"\s*:\s*\")[^\"]+"), r"\1[redacted]"),
    (re.compile(r"\bEAA[A-Za-z0-9_-]{20,}"), "[redacted-token]"),
    (re.compile(r"\b\d{6,16}:[A-Za-z0-9_-]{20,}"), "[redacted-bot-token]"),
    (re.compile(r"\b(gh[pousr]_)[A-Za-z0-9]{16,}"), r"\1[redacted]"),
    (re.compile(r"\bya29\.[A-Za-z0-9_-]{10,}"), "[redacted-oauth]"),
)


def redact(text):
    out = str(text)
    for pattern, repl in REDACTIONS:
        out = pattern.sub(repl, out)
    return out


def fingerprint(secret):
    """10 hex characters that identify a credential without being it."""
    return hashlib.sha256(str(secret).encode("utf-8")).hexdigest()[:10]


def cost(text):
    """What Threads charges for a string: ASCII 1, everything else its UTF-8 byte length."""
    total = 0
    for char in text:
        total += 1 if ord(char) < 0x80 else max(1, len(char.encode("utf-8")))
    return total


class ApiError(Exception):
    def __init__(self, status, body):
        self.status = status
        self.body = body or ""
        super().__init__("HTTP %s: %s" % (status, self.blurb))

    @property
    def blurb(self):
        return redact(self.body)[:600]

    @property
    def cause(self):
        hay = self.body.lower()
        for cause, needles in CAUSES:
            if any(needle.lower() in hay for needle in needles):
                return cause
        return "run"


def _request(method, url, params=None, timeout=30):
    query = urllib.parse.urlencode(params or {}, doseq=True)
    if method == "GET":
        target = "%s?%s" % (url, query) if query else url
        data = None
    else:
        target = url
        data = query.encode("utf-8")
    request = urllib.request.Request(target, data=data, method=method,
                                      headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # A network that is merely angry is not an outage of the lane: the caller decides,
        # and `transport` is a cause the heartbeat can distinguish from `credentials`.
        raise ApiError(0, "transport failure: %s" % (exc,))


def api(method, path, token, params=None):
    payload = dict(params or {})
    payload["access_token"] = token
    status, body = _request(method, "%s%s" % (API_HOST, path), payload)
    try:
        parsed = json.loads(body) if body.strip().startswith(("{", "[")) else {}
    except json.JSONDecodeError:
        parsed = {}
    if status >= 400 or (isinstance(parsed, dict) and parsed.get("error")):
        raise ApiError(status, body or json.dumps(parsed))
    return parsed


def whoami(token, user_id=None):
    """'Who does this token actually authorise?' — asked before anything else, always."""
    who = api("GET", "/me" if not user_id else "/%s" % user_id, token,
              {"fields": "id,username,name,is_eligible_for_apis,threads_profile"})
    return who


def publishing_limit(token, user_id):
    """The 250-posts-per-24h clock, read from Meta rather than counted locally."""
    try:
        data = api("GET", "/%s/threads_publishing_limit" % user_id, token,
                   {"fields": "config,quota_usage"})
    except ApiError as exc:
        print("::warning title=Publishing quota unreadable::%s — assuming there is room, "
              "because refusing a legitimate post on an unreadable counter is the worse "
              "failure" % exc.blurb[:160])
        return None
    # The limit endpoint answers flat on `/me`-style calls and wrapped in `data` on the
    # documented one; read whichever shape arrived instead of guessing which Meta sent.
    row = data
    if isinstance(data.get("data"), list) and data["data"]:
        row = data["data"][0]
    config = row.get("config") or {}
    return {"usage": int(row.get("quota_usage") or 0),
            "total": int(config.get("quota_total") or 250)}


def recent_posts(token, user_id, limit=25):
    return api("GET", "/%s/threads" % user_id, token,
                {"fields": "text,permalink,created_time", "limit": min(int(limit), 50)}
                ).get("data", [])


def normalize(text):
    """Whitespace and case folded; *nothing else*. The guard is exact-wording by design."""
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def find_duplicate(posts, text):
    needle = normalize(text)
    if not needle:
        return None
    for post in posts or []:
        if normalize(post.get("text")) == needle:
            return post.get("permalink") or "(posted, permalink not returned)"
    return None


def create_text_container(token, user_id, text, link_attachment=None, reply_control=None):
    params = {"text": text}
    if link_attachment:
        params["link_attachment"] = link_attachment
    if reply_control:
        params["reply_control"] = reply_control
    return api("POST", "/%s/threads" % user_id, token, params)["id"]


def wait_container(token, container_id, tries=6, delay=5, sleeper=time.sleep):
    """Text containers are usually ready at once; this is the polite version of 'assume'.

    Meta documents that a TEXT post needs no polling, and that a failure such as
    FAILED_PROCESSING_VIDEO only ever surfaces on this status call. So: look once, and if
    it is still IN_PROGRESS wait a little — never the 10-minute default that makes a
    one-second post look like a hung job.
    """
    state = None
    for attempt in range(tries):
        data = api("GET", "/%s" % container_id, token, {"fields": "status"})
        state = (data.get("status") or "").upper()
        if state in ("OK", "PUBLISHED"):
            return True, state
        if state in ("FAILED", "EXPIRED"):
            return False, state
        if attempt < tries - 1:
            sleeper(delay)
    return False, state or "unknown"


def publish_container(token, user_id, container_id):
    return api("POST", "/%s/threads_publish" % user_id, token, {"creation_id": container_id})["id"]


def read_back(token, post_id):
    return api("GET", "/%s" % post_id, token, {"fields": "permalink,text"})


def refresh_token(token, user_id):
    """The 60-day clock, wound forward. `grant_type` is a literal, not a secret."""
    data = api("GET", "/%s/refresh_access_token" % user_id, token,
               {"grant_type": "th_refresh_token"})
    if not data.get("access_token"):
        raise ApiError(200, json.dumps(data))
    return data


def check_copy(text):
    problems = []
    if not text.strip():
        problems.append("the post is empty")
    if cost(text) > MAX_COST:
        problems.append("%d characters is over the %d Threads limit" % (cost(text), MAX_COST))
    links = len(set(re.findall(r"https?://\S+", text)))
    if links > LINK_LIMIT:
        problems.append("%d links is over the %d-link Threads cap" % (links, LINK_LIMIT))
    return problems


def load_config(args):
    token = None
    if args.token_file:
        try:
            with open(args.token_file, encoding="utf-8") as handle:  # closed: a leaked fd in a
                token = handle.read().strip()                        # lane is a ResourceWarning
                                                                     # that hides the next one
        except OSError as exc:
            print("::error title=token file unreadable::%s: %s" % (args.token_file, exc))
            return None, None, 2
    if not token:
        token = (os.environ.get("THREADS_ACCESS_TOKEN") or "").strip()
    user_id = (os.environ.get("THREADS_USER_ID") or "").strip() or (token and "")
    who_id = None
    if not token:
        print("::error title=Threads secrets missing::no THREADS_ACCESS_TOKEN (and no "
              "--token-file). This is a setup step, not an outage.")
        return None, None, 2
    if not user_id:
        # /me works with the token alone and answers the id question, so a missing
        # THREADS_USER_ID is a warning and a lookup, not a red run.
        try:
            who_id = str(whoami(token).get("id") or "")
        except ApiError as exc:
            print("::error title=Threads credentials::/me failed before the user id could be "
                  "learned: %s" % exc.blurb)
            return token, None, 3
        if not who_id:
            print("::error title=Threads user id unknown::/me returned no id")
            return token, None, 2
        print("THREADS_USER_ID not set — using %s from /me" % who_id)
    return token, (user_id or who_id), 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Publish one text post to Threads")
    parser.add_argument("--text", help="the post body (≤500 characters)")
    parser.add_argument("--from-json", dest="from_json",
                        help="read .text from a generate_threads_content.py JSON file")
    parser.add_argument("--link-attachment", help="URL for the link preview card")
    parser.add_argument("--reply-control", choices=["all", "followed_users", "mentioned_users"])
    parser.add_argument("--probe", action="store_true",
                        help="ask Meta who the token authorises and what quota is left; "
                             "creates nothing")
    parser.add_argument("--dry-run", action="store_true", help="validate the copy, send nothing")
    parser.add_argument("--refresh", action="store_true",
                        help="wound the 60-day clock and print the JSON to stdout for the vault")
    parser.add_argument("--no-guard", action="store_true",
                        help="skip the read-the-profile duplicate check (a dispatch flag only)")
    parser.add_argument("--force", action="store_true", help="publish even if it is a duplicate")
    parser.add_argument("--token-file", help="0600 file holding the token (preferred over env)")
    parser.add_argument("--skip-pages", type=int, default=25, help="recent posts to compare")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    token, user_id, code = load_config(args)
    if code:
        return code

    if args.refresh:
        try:
            payload = refresh_token(token, user_id)
        except ApiError as exc:
            # stderr, and no `::error`. Two reasons, both load-bearing:
            #   * stdout is the pipe into `token_vault.py seal --json`, which must never be handed
            #     anything that is not the JSON it expects;
            #   * the caller decides severity. Both workflows downgrade this to a warning, because
            #     Meta allows one refresh per 24 h and setup day trips that rule for real. A tool
            #     that files a red annotation for a deliberate warning is a lane that looks broken
            #     the morning after a correct setup.
            print("threads refresh failed (%s): %s" % (exc.cause, redact(exc.blurb)),
                  file=sys.stderr)
            print("THREADS_RESULT=refresh-failed", file=sys.stderr)
            print("THREADS_CAUSE=%s" % exc.cause, file=sys.stderr)
            return 3 if exc.cause == "credentials" else 6
        # The value goes to stdout *only* so the caller can pipe it into
        # `token_vault.py seal`. Nothing here prints it to the log: the workflow that
        # forgets to redirect is the workflow that puts a token in a run summary.
        print(json.dumps(payload))
        return 0

    try:
        who = whoami(token, None)
    except ApiError as exc:
        print("::error title=Threads credentials::the token was rejected before anything was "
              "attempted (fingerprint %s): %s" % (fingerprint(token), exc.blurb))
        print("THREADS_RESULT=refused")
        print("THREADS_CAUSE=%s" % exc.cause)
        return 3 if exc.cause in ("credentials", "permission") else 6
    username = who.get("username") or "?"
    print("token authorises @%s (id %s)" % (username, who.get("id")))

    if args.probe:
        limit = publishing_limit(token, user_id or who.get("id"))
        where = ("quota %s/%s used" % (limit["usage"], limit["total"])) if limit else "quota unknown"
        print("probe: @%s — publishing allowed, %s" % (username, where))
        print("THREADS_PROBE=%s" % ("ok" if limit else "quota-unreadable"))
        print("THREADS_RESULT=probed")
        return 0

    text = args.text or ""
    if args.from_json:
        try:
            with open(args.from_json, encoding="utf-8") as handle:
                blob = json.loads(handle.read())
        except (OSError, ValueError) as exc:
            print("::error title=content file unreadable::%s: %s" % (args.from_json, exc))
            return 5
        text = blob.get("text") or ""
        if blob.get("trimmed"):
            print("content was trimmed: %s" % "; ".join(blob["trimmed"]))
    text = text.strip()

    problems = check_copy(text)
    if problems:
        for problem in problems:
            print("::error title=copy rejected::%s" % problem)
        print("THREADS_RESULT=refused")
        print("THREADS_CAUSE=copy")
        return 5
    print("post: %d/%d characters, %d link(s)"
          % (cost(text), MAX_COST, len(set(re.findall(r"https?://\S+", text)))))

    if args.dry_run:
        print("THREADS_RESULT=dry-run")
        print("Dry run — the copy is valid and the token works; nothing was published.")
        return 0

    target = user_id or who.get("id")

    if not args.no_guard:
        try:
            posts = recent_posts(token, target, args.skip_pages)
        except ApiError as exc:
            # Fail-open with a name on it. The alternative — refusing to post because the
            # profile could not be read — is how a lane stays silent for a week.
            print("::warning title=duplicate guard unavailable::the profile list could not be "
                  "read (%s), so this post goes out on the ledger's word alone" % exc.blurb[:160])
            posts = None
            guard = "unavailable"
        else:
            guard = "live"
            hit = find_duplicate(posts, text)
            if hit and not args.force:
                print("refused-a-duplicate: this exact wording is already on @%s — %s"
                      % (username, hit))
                print("THREADS_RESULT=refused-duplicate")
                print("THREADS_PERMALINK=%s" % hit)
                return 0
        if guard == "live":
            print("duplicate guard: live — %d recent post(s) on @%s checked for this wording"
                  % (len(posts or []), username))
    else:
        print("::warning title=duplicate guard skipped::--no-guard was passed, so only the "
              "ledger stood between this post and a repeat")

    limit = publishing_limit(token, target)
    if limit and limit["usage"] >= limit["total"]:
        print("::error title=Threads publishing quota used up::%s/%s in the last 24 hours. "
              "Tomorrow's run is unaffected." % (limit["usage"], limit["total"]))
        print("THREADS_RESULT=refused")
        print("THREADS_CAUSE=quota")
        return 4

    try:
        container_id = create_text_container(token, target, text, args.link_attachment,
                                             args.reply_control)
        ready, state = wait_container(token, container_id)
        if not ready:
            print("::error title=Threads container did not finish::status=%s for container %s "
                  "(containers die after 24h, so this run must not be retried blindly)"
                  % (state, container_id))
            print("THREADS_RESULT=refused")
            print("THREADS_CAUSE=state")
            return 6
        post_id = publish_container(token, target, container_id)
        seen = read_back(token, post_id)
    except ApiError as exc:
        print("::error title=Threads publish failed (%s)::%s" % (exc.cause, exc.blurb))
        print("THREADS_RESULT=failed")
        print("THREADS_CAUSE=%s" % exc.cause)
        return {"credentials": 3, "permission": 3, "quota": 4, "copy": 5}.get(exc.cause, 6)

    permalink = seen.get("permalink") or "https://www.threads.net/@%s/post/%s" % (username, post_id)
    if normalize(seen.get("text")) != normalize(text):
        # The read-back is the difference between "Meta returned an id" and "your readers
        # got this". If they disagree, say so and leave the run red.
        print("::error title=Threads read-back mismatch::post %s exists but its text does not "
              "match what was sent. Check it by eye: %s" % (post_id, permalink))
        print("THREADS_RESULT=mismatch")
        print("THREADS_CAUSE=verification")
        print("THREADS_PERMALINK=%s" % permalink)
        return 7
    print("✅ published to @%s: %s" % (username, permalink))
    print("THREADS_RESULT=sent")
    print("THREADS_POST_ID=%s" % post_id)
    print("THREADS_PERMALINK=%s" % permalink)
    return 0


if __name__ == "__main__":
    sys.exit(main())
