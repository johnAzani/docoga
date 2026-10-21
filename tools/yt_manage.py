#!/usr/bin/env python3
"""
DocOga YouTube manager — delete, unlist, make public/private, from a plan file
==============================================================================

Owner, 16 Oct 2026: "delete n45ufAFv5OM, unlist 2ruPSaR8-M0 and oBsWKR4AUNA — I want you to
be able to delete it." Until now every YouTube write the automation could do was an upload;
anything after the fact (a wrong Short left public, a test upload nobody wants in the grid)
meant the owner in the Studio app. This file closes that gap the same way every other lane
works: a plan in the repo, a workflow that runs it, a ledger that makes it idempotent.

How it is driven
----------------
    logs/youtube_cleanup_plan.txt      one line per action: `delete <id>` / `unlist <id>` /
                                       `public <id>` / `private <id>`, `#` comments allowed
    logs/youtube_manage.json           what has been done, so a line is never applied twice
    .github/workflows/youtube_manage.yml  runs the plan when it changes on main, or on dispatch

    python3 tools/yt_manage.py --scopes                       what this token may do
    python3 tools/yt_manage.py --plan logs/youtube_cleanup_plan.txt [--dry-run]
    python3 tools/yt_manage.py --plan-text "delete abc; unlist def ghi"
    python3 tools/yt_manage.py show <id>

The scope question, answered before anything is touched
--------------------------------------------------------
`videos.delete` and `videos.update` need `https://www.googleapis.com/auth/youtube.force-ssl`
(or `…/auth/youtube`). The refresh token minted on setup day asked for `youtube.upload` +
`youtube.readonly` only, which is enough to publish and to read back — and answers
`insufficientPermissions` to a delete. So the first thing this file does is read the token's
scopes from Google's tokeninfo endpoint and, if the write scope is missing, stop with exit 2
and the exact re-consent line (OAuth Playground, one scope: `youtube.force-ssl`, which is a
superset — the Shorts and Deep-Dive uploads keep working on it). Nothing is attempted on a
token that cannot do it, so the failure is one sentence and not a 403 per line.

Every action reads the video first: a delete of a video that is already gone, or an unlist of
one that is already unlisted, is recorded as done and costs nothing. `videos.update` is sent
with the *whole* status object read back from the video, with only `privacyStatus` changed —
the API deletes any mutable field the request omits, and `embeddable`/`license` are not ours
to reset by accident.

Exit codes
    0  every line done (or nothing to do) · dry run
    2  setup: credentials missing, or the token lacks the write scope (the fix is printed)
    3  YouTube refused an action (quota, a video that is not ours, a strike)
    4  the plan itself is malformed
"""

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yt_publish  # noqa: E402  — the OAuth refresh, the transport, the error classifier
import publish_calendar  # noqa: E402  — the 12-hour wording of a publish instant

API_URL = yt_publish.API_URL
TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
WRITE_SCOPES = ("https://www.googleapis.com/auth/youtube.force-ssl",
                "https://www.googleapis.com/auth/youtube")
RECONSENT = ("Re-mint YT_REFRESH_TOKEN once with the single scope "
             "https://www.googleapis.com/auth/youtube.force-ssl (OAuth Playground, gear → your "
             "own client, Step 1 → Input your own scopes → Authorize → Step 2 → Exchange; see "
             "YOUTUBE_AUTOMATION.md). It is a superset of upload+readonly, so the Shorts and "
             "Deep-Dive lanes keep working; only the one secret changes.")

ACTIONS = ("delete", "unlist", "public", "private", "schedule")
PRIVACY_FOR = {"unlist": "unlisted", "public": "public", "private": "private"}
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
# `schedule 2026-10-24T19:00 <ids>` — Lagos time, naive ISO (what yt_publish.parse_publish_at
# reads as WAT). Owner, 21 Oct 2026: the unlisted Deep-Dives must go public on a scheduled
# date like everything else. YouTube's contract: privacyStatus=private + status.publishAt;
# the video flips public by itself at that instant and subscribers are notified then.
WHEN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$")

EXIT_OK, EXIT_SETUP, EXIT_REFUSED, EXIT_PLAN = 0, 2, 3, 4


class PlanError(ValueError):
    pass


def parse_plan(text):
    """[(action, video_id, comment)] from the plan text; `;` and newlines both separate.

    One action word may be followed by several ids (`unlist A B`), because the owner's
    message came in exactly that shape and a format that makes him retype it is a bad format.
    """
    plan = []
    for raw_line in (text or "").splitlines():
        line, _, comment = raw_line.partition("#")  # comments first, so a `;` inside one is prose
        for raw in line.split(";"):
            words = raw.split()
            if not words:
                continue
            plan.extend(_parse_words(words, raw, comment.strip()))
    return plan


def _parse_words(words, raw, comment):
    action, ids = words[0].lower(), words[1:]
    if action not in ACTIONS:
        raise PlanError("unknown action %r in %r — use one of %s" % (action, raw.strip(), ", ".join(ACTIONS)))
    when = ""
    if action == "schedule":
        if not ids or not WHEN.match(ids[0]):
            raise PlanError("schedule needs a Lagos time first, e.g. `schedule 2026-10-24T19:00 <video id>` — got %r" % raw.strip())
        when, ids = ids[0], ids[1:]
        action = "schedule %s" % when   # the time is part of the act: a new time is a new line
    if not ids:
        raise PlanError("no video id after %r" % action)
    for vid in ids:
        if not VIDEO_ID.match(vid):
            raise PlanError("%r is not a YouTube video id (11 characters of A-Z a-z 0-9 _ -)" % vid)
    return [(action, vid, comment) for vid in ids]


def load_ledger(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"done": []}


def save_ledger(path, ledger):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def already_done(ledger, action, video_id):
    return any(row.get("action") == action and row.get("video_id") == video_id
               for row in ledger.get("done", []))


def record(ledger, action, video_id, result, title=""):
    ledger.setdefault("done", []).append({
        "action": action, "video_id": video_id, "result": result, "title": title,
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
    })


def transport(http):
    """Accept a bare session (tests, or any requests-like object) or a yt_publish.Http."""
    if http is not None and not isinstance(http, yt_publish.Http):
        return yt_publish.Http(session=http)
    return http


def token_scopes(http):
    """The scopes behind the access token on `http`, via tokeninfo. [] if unreadable."""
    # The same transport without the bearer header: tokeninfo takes the token as a parameter.
    bare = yt_publish.Http(session=http._session)
    r = bare.request("GET", TOKENINFO_URL, params={"access_token": http.token})
    if r.status_code != 200:
        return None
    try:
        return (r.json() or {}).get("scope", "").split()
    except ValueError:
        return None


def can_write(scopes):
    return scopes is None or any(s in scopes for s in WRITE_SCOPES)


def refusal(r, what):
    kind, reason, _what, action, _ = yt_publish.classify(r.status_code, r.text)
    if r.status_code in (401, 403) and ("insufficient" in (r.text or "").lower()
                                        or "forbidden" in (reason or "").lower()):
        return yt_publish.Problem("credentials", reason or "insufficientPermissions",
                                  "%s: HTTP %s — the token may not do this" % (what, r.status_code),
                                  RECONSENT, EXIT_SETUP)
    return yt_publish.Problem(kind or "forbidden", reason or "refused",
                              "%s: HTTP %s — %s" % (what, r.status_code, (r.text or "")[:300]),
                              action or "See the reason above; the plan line stays pending.")


def fetch(http, video_id):
    """(snippet, status) of a video, or (None, None) when YouTube has no such video for us."""
    r = http.request("GET", "%s/videos" % API_URL, params={"part": "snippet,status", "id": video_id})
    if r.status_code != 200:
        raise refusal(r, "videos.list %s" % video_id)
    items = (r.json() or {}).get("items") or []
    if not items:
        return None, None
    return items[0].get("snippet") or {}, items[0].get("status") or {}


MUTABLE_STATUS = ("privacyStatus", "embeddable", "license", "publicStatsViewable",
                  "selfDeclaredMadeForKids", "publishAt", "containsSyntheticMedia")


def set_privacy(http, video_id, status, privacy, publish_at=None):
    body = {"id": video_id, "status": {k: v for k, v in status.items() if k in MUTABLE_STATUS}}
    body["status"]["privacyStatus"] = privacy
    if privacy != "private":
        body["status"].pop("publishAt", None)  # a schedule only means something on a private video
    elif publish_at is not None:
        body["status"]["publishAt"] = yt_publish.rfc3339_utc(publish_at)
    else:
        body["status"].pop("publishAt", None)  # plain `private` means private, not "still scheduled"
    r = http.request("PUT", "%s/videos" % API_URL, params={"part": "status"},
                     headers={"Content-Type": "application/json"}, data=json.dumps(body))
    if r.status_code != 200:
        raise refusal(r, "videos.update %s → %s" % (video_id, privacy))
    return ((r.json() or {}).get("status") or {}).get("privacyStatus")


def delete(http, video_id):
    r = http.request("DELETE", "%s/videos" % API_URL, params={"id": video_id})
    if r.status_code not in (200, 204):
        raise refusal(r, "videos.delete %s" % video_id)


def apply_line(http, action, video_id, dry_run=False, log=print):
    """Do one plan line. Returns (result, title); raises Problem when YouTube refuses."""
    snippet, status = fetch(http, video_id)
    title = (snippet or {}).get("title", "")
    if snippet is None:
        if action == "delete":
            log("  %s: already gone — nothing to delete" % video_id)
            return "already-gone", ""
        raise yt_publish.Problem("forbidden", "notFound",
                                 "%s: YouTube has no such video on this channel" % video_id,
                                 "Check the id; a video on another channel cannot be changed from here.")
    current = (status or {}).get("privacyStatus", "?")
    if action.startswith("schedule "):
        when = yt_publish.parse_publish_at(action.split(" ", 1)[1])
        want_at = yt_publish.rfc3339_utc(when)
        if current == "private" and (status or {}).get("publishAt", "").startswith(want_at[:16]):
            log("  %s: already scheduled for %s — %r" % (video_id, publish_calendar.human(when), title))
            return "already-scheduled", title
        if current == "public":
            # 21 Oct 2026, first run: dd2 had been tapped public by the owner before the plan
            # line landed. Scheduling it would have HIDDEN a live video, so the line is refused —
            # but recorded, because a line that is refused forever keeps the lane red forever.
            # Hiding a live video on purpose is `private` first, then `schedule`.
            log("  %s: already public — left as it is (a schedule would hide a live video) — %r" % (video_id, title))
            log("::warning title=YouTube schedule %s skipped::%s is already public; the schedule for %s was not "
                "applied. To really hide and re-release it, write `private %s` on a line above the schedule."
                % (video_id, video_id, publish_calendar.human(when), video_id))
            return "already-public", title
        if dry_run:
            log("  would schedule %s (%s) → public at %s — %r" % (video_id, current, publish_calendar.human(when), title))
            return "dry-run", title
        set_privacy(http, video_id, status, "private", publish_at=when)
        log("  🗓 %s %s → private, public at %s — %r" % (video_id, current, publish_calendar.human(when), title))
        return "scheduled %s" % want_at, title
    if action == "delete":
        if dry_run:
            log("  would delete %s — %r (currently %s)" % (video_id, title, current))
            return "dry-run", title
        delete(http, video_id)
        log("  🗑 deleted %s — %r" % (video_id, title))
        return "deleted", title
    want = PRIVACY_FOR[action]
    if current == want:
        log("  %s: already %s — %r" % (video_id, want, title))
        return "already-%s" % want, title
    if dry_run:
        log("  would set %s %s → %s — %r" % (video_id, current, want, title))
        return "dry-run", title
    got = set_privacy(http, video_id, status, want)
    log("  ✅ %s %s → %s — %r" % (video_id, current, got or want, title))
    return got or want, title


def run_plan(plan, ledger_path, dry_run=False, http=None, log=print):
    pending = [(a, v, c) for a, v, c in plan if not already_done(load_ledger(ledger_path), a, v)]
    skipped = len(plan) - len(pending)
    if skipped:
        log("%d line(s) already in %s — not repeated" % (skipped, ledger_path))
    if not pending:
        log("Nothing to do.")
        return EXIT_OK
    http, _payload = yt_publish.authorize(transport(http))
    scopes = token_scopes(http)
    if scopes is None:
        log("⚠️  token scopes unreadable — proceeding; a 403 below means the scope is missing")
    else:
        log("token scopes: %s" % ", ".join(s.rsplit("/", 1)[-1] for s in scopes))
    if not can_write(scopes):
        print(yt_publish.Problem("credentials", "scope_missing",
                                 "This token can upload and read but not delete or update "
                                 "(no youtube.force-ssl / youtube scope).", RECONSENT).report())
        yt_publish.emit("error", "YouTube token cannot delete or unlist", RECONSENT)
        return EXIT_SETUP
    ledger = load_ledger(ledger_path)
    code = EXIT_OK
    for action, video_id, comment in pending:
        log("%s %s%s" % (action, video_id, (" — " + comment) if comment else ""))
        try:
            result, title = apply_line(http, action, video_id, dry_run=dry_run, log=log)
        except yt_publish.Problem as problem:
            print(problem.report())
            yt_publish.emit("error", "YouTube %s %s refused" % (action, video_id), problem.what)
            if problem.kind == "credentials":
                code = EXIT_SETUP
                break  # the same scope is missing for every remaining line
            code = EXIT_REFUSED
            if problem.kind == "quota":
                break  # and the same empty bucket refuses every remaining line today
            continue
        if not dry_run:
            record(ledger, action, video_id, result, title)
            save_ledger(ledger_path, ledger)
    return code


def show_scopes(http=None, log=print):
    http, _payload = yt_publish.authorize(transport(http))
    scopes = token_scopes(http)
    if scopes is None:
        log("token scopes: unreadable (tokeninfo did not answer)")
        return EXIT_REFUSED
    for scope in scopes:
        log("  %s" % scope)
    if can_write(scopes):
        log("✅ this token can delete, unlist and re-publish videos")
        return EXIT_OK
    log("⏸ upload/read only — %s" % RECONSENT)
    return EXIT_SETUP


def main(argv=None, http=None):
    parser = argparse.ArgumentParser(description="DocOga YouTube manager")
    parser.add_argument("--plan", help="plan file (default logs/youtube_cleanup_plan.txt)")
    parser.add_argument("--plan-text", help="plan given inline, `;`-separated")
    parser.add_argument("--ledger", default="logs/youtube_manage.json")
    parser.add_argument("--dry-run", action="store_true", help="read and report; change nothing")
    parser.add_argument("--scopes", action="store_true", help="print what the token may do and stop")
    parser.add_argument("words", nargs="*", help="`show <id>` or `<action> <id>…` inline")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    try:
        if args.scopes:
            return show_scopes(http)
        if args.words and args.words[0] == "show":
            h, _ = yt_publish.authorize(transport(http))
            for video_id in args.words[1:]:
                snippet, status = fetch(h, video_id)
                if snippet is None:
                    print("%s: no such video on this channel" % video_id)
                else:
                    print("%s: %r — %s, uploaded %s" % (video_id, snippet.get("title"),
                                                        (status or {}).get("privacyStatus"),
                                                        snippet.get("publishedAt")))
            return EXIT_OK
        if args.words:
            text = " ".join(args.words)
        elif args.plan_text:
            text = args.plan_text
        else:
            path = Path(args.plan or "logs/youtube_cleanup_plan.txt")
            if not path.exists():
                print("no plan: %s does not exist — nothing to do" % path)
                return EXIT_OK
            text = path.read_text(encoding="utf-8")
        try:
            plan = parse_plan(text)
        except PlanError as exc:
            print("::error title=YouTube plan malformed::%s" % exc)
            return EXIT_PLAN
        if not plan:
            print("The plan is empty — nothing to do.")
            return EXIT_OK
        return run_plan(plan, args.ledger, dry_run=args.dry_run, http=http)
    except yt_publish.Problem as problem:
        print(problem.report())
        return EXIT_SETUP if problem.kind == "credentials" else EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
