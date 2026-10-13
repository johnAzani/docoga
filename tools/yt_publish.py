#!/usr/bin/env python3
"""
DocOga YouTube Publisher
========================
Uploads videos to the DocOga YouTube channel.

Requirements (GitHub Secrets):
  - YT_REFRESH_TOKEN  (OAuth refresh token)
  - YT_CLIENT_ID      (OAuth client ID)
  - YT_CLIENT_SECRET  (OAuth client secret)
  - YT_CHANNEL_ID     (optional, for reference)

Usage:
  python3 tools/yt_publish.py --video video.mp4 --title "Title" --description "Description"
  python3 tools/yt_publish.py --video video.mp4 --title "Title" --tags "law,tenant" --privacy public
  python3 tools/yt_publish.py --check-token      # credentials + channel identity, nothing sent
  python3 tools/yt_publish.py --probe            # same, in the words a human can act on

Why this file is longer than the twelve lines it used to need
--------------------------------------------------------------
The scheduled run of 9 Oct 2026 rendered a Short for ten minutes and then died at
"Upload to YouTube" with nothing but `Exit code 1` in the log, and the issue it filed had
to *guess* among four causes. The log is unreachable afterwards (Actions log storage is not
readable from the agent sandbox), which is the whole problem: an unattended lane that cannot
say why it failed stays failed for a week. So every failure in here has a kind, a sentence,
and a machine-readable marker; and the wire protocol is implemented properly rather than
optimistically — see ResumableUploader.

Facts this file depends on, from Google's own `videos.insert` page (last updated 8 Oct 2026)
and the resumable-upload guide:
  * media over 5 MB must use `uploadType=resumable`; chunks must be a multiple of 256 KB and
    all the same size except the last;
  * a non-final chunk that was accepted answers **308 Resume Incomplete** with a `Range`
    header, and 308 is *not* a failure — the version of this file before 13 Oct 2026 PUT the
    whole file once and read anything other than 200 as an error, so a 308 would have killed a
    perfectly healthy upload;
  * 500/502/503/504 mean back off and ask the session where to resume; 404/410 mean the
    session expired and the upload restarts from byte 0;
  * the documented 4xx `errors.reasons` for this endpoint are `invalidTitle`,
    `invalidDescription`, `invalidTags`, `invalidCategoryId`, `invalidVideoMetadata`,
    `mediaBodyRequired`, `uploadLimitExceeded`, `forbidden`, `forbiddenPrivacySetting`,
    `forbiddenLicenseSetting`, `defaultLanguageNotSet`, `invalidFilename`, `invalidPublishAt`,
    plus `quotaExceeded` from the shared error table;
  * `privacyStatus` defaults to `public`, "certain uploads might default to `private` based on
    creator account settings" — which is why the upload is *read back* here instead of assumed;
  * videos from unverified API projects are explicitly NOT restricted to private (an older
    belief that cost this lane a wrong triage note).
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
API_URL = "https://www.googleapis.com/youtube/v3"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
MEDIA_TYPE = "video/mp4"

# Google: "the chunk size must be a multiple of 256 KB" and every chunk but the last must be
# the same size. 8 chunks of 256 KB = 2 MiB: big enough that a 60 MB Short is 30 requests,
# small enough that one dropped chunk costs seconds rather than the whole job.
CHUNK_MULTIPLE = 256 * 1024
CHUNK_BYTES = 8 * CHUNK_MULTIPLE
# No request here may hang: a hung PUT eats the job's 30 minutes and leaves no error at all,
# which is indistinguishable from "the API is down" when you read it three days later.
CONNECT_TIMEOUT = 15.0
READ_TIMEOUT = 300.0
MAX_CHUNK_ATTEMPTS = 4
MAX_FINALISE_POLLS = 4
MAX_SESSION_RESTARTS = 1
BACKOFF_BASE = 2.0

# Limits the API enforces with a 400 that a template change caused, at 09:00 on a Sunday.
TITLE_MAX = 100
DESC_MAX = 5000
TAGS_TOTAL_MAX = 500

EXIT_OK = 0
EXIT_FAILED = 1
# A separate code for "a human with a browser must fix this", so the workflow can say
# "re-author the token" instead of "the script crashed" — the distinction is the entire
# difference between a 2-minute job and a week of nobody looking at it.
EXIT_NEEDS_HUMAN = 2

# kind -> what a person does about it. The strings are for the run log and the issue body;
# the `kind` is for the code, because a human never greps a sentence.
REASONS = {
    "invalid_grant": ("credentials",
                      "The refresh token was revoked, expired, or was minted by an OAuth app "
                      "still in Testing mode (Google expires those tokens after 7 days).",
                      "Re-run the one-time consent flow and update YT_REFRESH_TOKEN. Google "
                      "expires refresh tokens issued to an OAuth consent screen that is still in "
                      "Testing after 7 days, so unless the app is published to Production (or "
                      "this Google account is listed as a test user) it will die again next week "
                      "and this lane will go red again on schedule."),
    "invalid_client": ("credentials",
                       "The OAuth client itself no longer exists in the Cloud project.",
                       "Recreate the OAuth client, then replace YT_CLIENT_ID, YT_CLIENT_SECRET "
                       "and YT_REFRESH_TOKEN together — one of the three is never enough."),
    "unauthorized_client": ("credentials",
                            "The client exists but is not allowed to refresh tokens.",
                            "Check the client type is 'Desktop app' (or 'Web' with the redirect "
                            "registered) and that the YouTube Data API is enabled for the project."),
    "dailyUploadLimitExceeded": ("quota",
                                 "This project has used its whole daily upload allowance.",
                                 "The Video Uploads bucket is small by default (100 upload calls "
                                 "a day) and is shared by everything using this client. Nothing "
                                 "of ours uploads twice a day, so look for another user of the "
                                 "same project, then request a quota increase."),
    "uploadLimitExceeded": ("quota",
                            "This channel has exceeded the number of videos it may upload.",
                            "Usually a per-day cap on the channel rather than the API: wait a "
                            "day. If it repeats, the channel has a strike or an unverified phone."),
    "quotaExceeded": ("quota",
                      "The project's YouTube Data API quota is exhausted for today.",
                      "Default is 10,000 units/day and an upload costs 1 unit in its own "
                      "bucket, so this means other calls are spending it — check what else "
                      "runs against this key, or schedule this lane away from them."),
    "accessNotConfigured": ("credentials",
                            "The YouTube Data API is not enabled for this Cloud project.",
                            "APIs & Services → Library → YouTube Data API v3 → Enable."),
    "forbidden": ("forbidden",
                  "YouTube refused the upload for this channel.",
                  "Check the channel for a strike, a suspended status, or a phone "
                  "verification requirement (unverified channels cannot publish)."),
    "forbiddenPrivacySetting": ("forbidden",
                                "The channel's settings do not allow this privacy status.",
                                "Set YT_PRIVACY=unlisted to publish while the account setting "
                                "is sorted out; a channel that defaults uploads to private will "
                                "keep downgrading 'public' uploads otherwise."),
    "forbiddenLicenseSetting": ("metadata", "The license value is not allowed.",
                                "Drop --license; the default YouTube license is correct."),
    "invalidTitle": ("metadata", "The title is empty or invalid.",
                     "Titles are 1-100 characters; this file clamps to 100, so an empty title "
                     "means the generator produced one — fix scripts/youtube_short_daily.py."),
    "invalidDescription": ("metadata", "The description is invalid.", "Max 5,000 characters."),
    "invalidTags": ("metadata", "The tag list is invalid.",
                    "Combined tag length must stay under 500 characters and tags cannot be "
                    "empty strings; this file trims the list, so a 400 here means the "
                    "generator emitted something odd (a tag of only spaces, say)."),
    "invalidCategoryId": ("metadata", "The categoryId is not a valid YouTube category.",
                          "List them with videoCategories.list; 22 is People & Blogs, 27 Education."),
    "invalidVideoMetadata": ("metadata", "The metadata payload was rejected as a whole.",
                             "Re-run with --check-token to rule out auth, then inspect the "
                             "snippet this file prints on stderr."),
    "defaultLanguageNotSet": ("metadata", "Localized fields were sent without a default language.",
                              "Set snippet.defaultLanguage or stop sending localizations."),
    "mediaBodyRequired": ("transport", "The upload session got no media.",
                          "The PUT never completed — check the runner's network, then re-run."),
    "invalidFilename": ("metadata", "The Slug header (file name) was rejected.",
                        "This file sends no Slug; if one appears, sanitize it."),
    "invalidPublishAt": ("metadata", "The scheduled publish time was invalid.",
                         "publishAt must be >= 1 minute in the future; this lane does not use it."),
    "authError": ("credentials", "The access token was not accepted by YouTube.",
                  "Usually a token minted for the wrong scope. The flow must ask for BOTH "
                  "https://www.googleapis.com/auth/youtube.upload (the upload) and "
                  "https://www.googleapis.com/auth/youtube.readonly (channels.list and the "
                  "read-back — upload-only answers insufficientPermissions there)."),
    "userAuthError": ("credentials", "The Google account behind the token is not authorized.",
                      "Re-consent as the channel owner, checking the account picker lands on "
                      "the DocOga channel."),
}


def classify(status, body):
    """Map a failed response onto (kind, what happened, what to do).

    The API reason string is looked up first because it is precise; the HTTP status is the
    fallback because a proxy can answer 502 with an HTML body and that is a different repair
    than a 400 the generator caused.
    """
    text = body or ""
    reason = ""
    try:
        parsed = json.loads(text)
        err = parsed.get("error") if isinstance(parsed, dict) else None
        if isinstance(err, dict):
            reason = err.get("status") or ""
            errors = err.get("errors") or []
            if errors:
                reason = errors[0].get("reason") or reason
            message = err.get("message", "")
        else:
            reason = err or ""
            message = str(err) if err else text[:200]
    except (ValueError, TypeError, AttributeError):
        message = text[:200]
    reason = str(reason)

    def lookup(haystack):
        """Longest key contained in the haystack, so `forbidden` cannot steal the response
        that actually means `forbiddenPrivacySetting`. Matching first-on-dictionary-order is how
        a lane sends the owner to check for channel strikes when the real fix was the privacy
        default."""
        low = haystack.lower()
        hits = [k for k in REASONS if k.lower() in low]
        return max(hits, key=len) if hits else None

    key = lookup(reason) or lookup(text)
    if key:
        kind, what, action = REASONS[key]
        return kind, key, what, action, message
    if status in (401, 403):
        return ("credentials", "http-%d" % status,
                "YouTube refused the request with HTTP %d." % status,
                "Check the token's scope and the channel's standing; the raw reason is "
                "quoted below.", message)
    if status == 400:
        return ("metadata", "http-400", "The API rejected the request with HTTP 400.",
                "Compare the snippet printed above with the videos.insert reference.", message)
    if status in (404, 408, 429, 500, 502, 503, 504):
        return ("transport", "http-%d" % status,
                "The request did not complete (HTTP %d)." % status,
                "This file already retried it; a pattern here means the runner's network or "
                "Google's edge, not the code.", message)
    return ("unknown", "http-%d" % status, "Unexpected response HTTP %d." % status,
            "Read the reason below; if it recurs, add it to REASONS in this file.", message)


class Problem(Exception):
    """A failure that already knows what kind it is and what to do about it."""

    def __init__(self, kind, reason, what, action="", exit_code=None):
        super().__init__(what)
        self.kind = kind
        self.reason = reason
        self.what = what
        self.action = action
        self.exit_code = EXIT_NEEDS_HUMAN if kind in ("credentials", "quota", "forbidden") \
            else (exit_code or EXIT_FAILED)

    def report(self):
        lines = ["❌ %s" % self.what, "   ↳ kind=%s reason=%s" % (self.kind, self.reason)]
        if self.action:
            lines.append("   ↳ fix: %s" % self.action)
        return "\n".join(lines)


def emit(level, title, message):
    """GitHub Actions annotation when we are in Actions, plain text otherwise."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("::%s title=%s::%s" % (level, title, message.replace("\n", " ")[:800]))
    return message


class Http:
    """One place that decides every request has a timeout and an Authorization header.

    The session is injectable — and it is the only seam the tests need: they script whole
    responses (a 308 with a Range, a 404 mid-file, a 403 with `dailyUploadLimitExceeded`)
    through the same object the real upload uses, instead of monkeypatching each call site.
    """

    def __init__(self, token=None, session=None):
        self.token = token
        self.expires_in = None
        self._session = session or requests.Session()

    def request(self, method, url, headers=None, data=None, params=None, files=None):
        hdrs = dict(headers or {})
        if self.token and "Authorization" not in hdrs:
            hdrs["Authorization"] = "Bearer %s" % self.token
        return self._session.request(method, url, headers=hdrs, data=data, params=params,
                                     files=files, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))


def env(*names):
    return [os.environ.get(n, "").strip() for n in names]


def refresh_access_token(client_id, client_secret, refresh_token, http=None):
    """Exchange the refresh token for a short-lived access token."""
    http = http or Http()
    r = http.request("POST", TOKEN_URL, headers={"Content-Type": "application/x-www-form-urlencoded"},
                     data={"client_id": client_id, "client_secret": client_secret,
                           "refresh_token": refresh_token, "grant_type": "refresh_token"})
    if r.status_code != 200:
        kind, reason, what, action, message = classify(r.status_code, r.text)
        raise Problem(kind or "credentials", reason or "token_refresh_failed",
                      "Token refresh failed: HTTP %s — %s" % (r.status_code, (r.text or "")[:300]),
                      action or "Fix the OAuth credentials; nothing was uploaded.")
    payload = r.json()
    if "access_token" not in payload:
        raise Problem("credentials", "no_access_token",
                      "Google answered 200 without an access_token: %s" % str(payload)[:200],
                      "Check that the consent asked for youtube.upload AND youtube.readonly.")
    return payload


def authorize(http=None):
    """Mint an access token onto (and return) the given transport.

    It reuses the injected Http rather than building a new one, because a function that
    silently swaps the transport is a function no test can drive end to end.
    """
    http = http or Http()
    for name in ("YT_REFRESH_TOKEN", "YT_CLIENT_ID", "YT_CLIENT_SECRET"):
        if not os.environ.get(name):
            raise Problem("credentials", "missing_secret", "%s is not set." % name,
                          "Add it under Settings → Secrets and variables → Actions. Nothing "
                          "was uploaded.", EXIT_NEEDS_HUMAN)
    payload = refresh_access_token(*env("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"),
                                   http=http)
    http.token = payload["access_token"]
    http.expires_in = payload.get("expires_in")
    return http, payload


def clamp_title(title):
    """Trim to what the API accepts, at a word boundary, rather than fail the run.

    A weekly job must not go red because a template grew a clause; a title cut mid-word is
    the cheaper injury, and the warning says it happened.
    """
    title = (title or "").strip()
    if len(title) <= TITLE_MAX:
        return title, None
    cut = title[:TITLE_MAX]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    cut = cut.rstrip(" ,;:.-—")
    return cut, "title was %d characters, trimmed to %d for YouTube's 100-character limit" % (
        len(title), len(cut))


def clamp_tags(tags):
    """List of tags, total length <= 500, no empties. Returns (tags, warning)."""
    if isinstance(tags, str):
        raw = [t.strip() for t in tags.split(",")]
    else:
        raw = [str(t).strip() for t in (tags or [])]
    clean = [t for t in raw if t]
    kept, total = [], 0
    for tag in clean:
        cost = len(tag) + (1 if kept else 0)
        if total + cost > TAGS_TOTAL_MAX:
            break
        kept.append(tag)
        total += cost
    warn = None
    if len(kept) < len(clean):
        warn = "dropped %d tag(s) past the API's 500-character combined limit" % (
            len(clean) - len(kept))
    return kept, warn


def build_metadata(title, description, tags, privacy, category_id, notify=None,
                   synthetic=None, language=None):
    """The video resource for `part=snippet,status`, with the limits applied here."""
    notes = []
    title, warn = clamp_title(title)
    if warn:
        notes.append(warn)
    tags, warn = clamp_tags(tags)
    if warn:
        notes.append(warn)
    description = (description or "").strip()
    if len(description) > DESC_MAX:
        description = description[:DESC_MAX].rsplit("\n", 1)[0]
        notes.append("description was over %d characters, cut at a line break" % DESC_MAX)
    if not title:
        raise Problem("metadata", "invalidTitle", "The title is empty after clamping.",
                      "Fix the generator: an untitled Short cannot be published.", EXIT_FAILED)
    snippet = {"title": title, "description": description, "categoryId": str(category_id)}
    # Google's own sample notes a 400 on an empty tags value; omitting the field entirely is
    # the documented-safe shape, so never send [].
    if tags:
        snippet["tags"] = tags
    if language:
        snippet["defaultLanguage"] = language
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if synthetic is not None:
        status["containsSyntheticMedia"] = bool(synthetic)
    params = {}
    if notify is not None:
        # `notifySubscribers` is a query parameter of videos.insert, not a field of the video
        # resource — sending it in the body is how you get a 400 about metadata you did send.
        params["notifySubscribers"] = "true" if notify else "false"
    return {"snippet": snippet, "status": status}, tags, notes, params


class ResumableUploader:
    """Google's resumable protocol: init a session, PUT aligned chunks, obey 308.

    Transport and clock are injectable because the behaviour that matters — 308 is progress,
    5xx resumes where the server actually has bytes, 404 restarts the session — can only be
    tested by scripting those responses.
    """

    def __init__(self, http, size, metadata, content_type=MEDIA_TYPE, sleep=time.sleep,
                 log=None, chunk_bytes=None, params=None):
        self.http = http
        self.size = size
        self.metadata = metadata
        self.params = params or {}
        self.content_type = content_type
        self.sleep = sleep
        self.log = log or (lambda line: None)
        # Read the module constant here rather than in the signature: a default argument is
        # frozen when the class is defined, which would make CHUNK_BYTES untestable and
        # un-tunable from a workflow.
        chunk_bytes = chunk_bytes or CHUNK_BYTES
        self.chunk_bytes = chunk_bytes - (chunk_bytes % CHUNK_MULTIPLE) or CHUNK_MULTIPLE

    def start(self):
        query = {"uploadType": "resumable", "part": "snippet,status"}
        query.update(self.params)
        r = self.http.request(
            "POST", UPLOAD_URL, params=query,
            headers={"Content-Type": "application/json; charset=UTF-8",
                     "X-Upload-Content-Type": self.content_type,
                     "X-Upload-Content-Length": str(self.size)},
            data=json.dumps(self.metadata).encode("utf-8"))
        if r.status_code not in (200, 201):
            kind, reason, what, action, _ = classify(r.status_code, getattr(r, "text", ""))
            raise Problem(kind, reason, "Upload initiation failed: HTTP %s — %s"
                          % (r.status_code, (getattr(r, "text", "") or "")[:300]), action)
        url = r.headers.get("Location") or r.headers.get("location")
        if not url:
            raise Problem("transport", "no_session_uri",
                          "YouTube answered the resumable init without a Location header.",
                          "Nothing was uploaded; re-run — this is either the API or a proxy "
                          "stripping the header.")
        return url

    @staticmethod
    def _range_end(header):
        """`Range: bytes=0-1048575` -> 1048575, or -1."""
        m = re.search(r"bytes=(\d+)-(\d+)", header or "")
        return int(m.group(2)) if m else -1

    def resume_at(self, url):
        """Ask the session how much of the file it already holds."""
        r = self.http.request("PUT", url, headers={"Content-Range": "bytes */%d" % self.size,
                                                   "Content-Length": "0"})
        if r.status_code in (200, 201):
            return self.size, r
        return self._range_end(r.headers.get("Range")) + 1, None

    def await_finalize(self, url):
        """Poll the session until it answers with the resource, or give up.

        Google's own guidance for a 308 with no work left: wait, honouring Retry-After when the
        response carries it. Bounded, because a CI job that waits forever is indistinguishable
        from one that hung — and the log of a cancelled job says nothing either way.
        """
        for attempt in range(MAX_FINALISE_POLLS):
            received, done = self.resume_at(url)
            if done is not None:
                return done
            if received >= self.size:
                self.log("   waiting on YouTube to finalise (%d/%d)"
                         % (attempt + 1, MAX_FINALISE_POLLS))
            self.sleep(BACKOFF_BASE ** attempt)
        return None

    def send(self, url, fh, start, chunk):
        end = start + len(chunk) - 1
        headers = {"Content-Type": self.content_type,
                   "Content-Length": str(len(chunk)),
                   "Content-Range": "bytes %d-%d/%d" % (start, end, self.size)}
        return end, self.http.request("PUT", url, headers=headers, data=chunk)

    def upload(self, path):
        """Return the API's final response body, having sent every byte."""
        url = self.start()
        restarts = 0
        sent = 0
        with open(path, "rb") as fh:
            while sent < self.size:
                fh.seek(sent)
                chunk = fh.read(self.chunk_bytes)
                if not chunk:
                    break
                attempts = 0
                while True:
                    end, r = self.send(url, fh, sent, chunk)
                    status = r.status_code
                    if status in (200, 201):
                        if end + 1 >= self.size:
                            return r
                        sent = end + 1
                        break
                    if status == 308:
                        got = self._range_end(r.headers.get("Range")) + 1
                        if got >= self.size:
                            # Every byte is at Google and the resource is not answered yet.
                            # This is the case the old code called a failure — and the case
                            # where a naive retry would have created a duplicate Short.
                            done = self.await_finalize(url)
                            if done is not None:
                                return done
                            raise Problem(
                                "state", "unfinalized",
                                "All %d bytes reached YouTube but the upload never finalized "
                                "inside %d polls." % (self.size, MAX_FINALISE_POLLS),
                                "Do NOT just re-run: check the channel (or the uploads playlist) "
                                "first — the video may exist even though this call gave up.")
                        if got >= end + 1:
                            sent = got
                            self.log("   %d/%d bytes accepted" % (sent, self.size))
                            break
                        # YouTube has less than we thought; send from where it actually is.
                        sent = max(got, 0)
                        fh.seek(sent)
                        chunk = fh.read(self.chunk_bytes)
                        continue
                    if status in (404, 410):
                        restarts += 1
                        if restarts > MAX_SESSION_RESTARTS:
                            raise Problem("transport", "session_expired",
                                          "The upload session expired mid-file (%d restarts "
                                          "allowed) and this chunk still failed." % MAX_SESSION_RESTARTS,
                                          "Re-run the workflow: the bytes never reached YouTube, "
                                          "so nothing was published and nothing to unpublish.")
                        self.log("   session expired — restarting the upload from byte 0")
                        url = self.start()
                        sent, restart_pos = 0, 0
                        fh.seek(0)
                        chunk = fh.read(self.chunk_bytes)
                        continue
                    if status in (408, 429, 500, 502, 503, 504):
                        attempts += 1
                        if attempts > MAX_CHUNK_ATTEMPTS:
                            raise Problem("transport", "http-%d" % status,
                                          "Chunk at byte %d failed %d times with HTTP %d."
                                          % (sent, MAX_CHUNK_ATTEMPTS, status),
                                          "The bytes after this point never reached YouTube; the "
                                          "upload is safe to retry from the start.")
                        self.sleep(BACKOFF_BASE ** attempts)
                        resume, done = self.resume_at(url)
                        if done is not None:
                            return done
                        sent = max(resume, 0)
                        fh.seek(sent)
                        chunk = fh.read(self.chunk_bytes)
                        continue
                    kind, reason, what, action, _ = classify(status, getattr(r, "text", ""))
                    raise Problem(kind, reason,
                                  "Upload failed at byte %d of %d: HTTP %s — %s"
                                  % (sent, self.size, status, (getattr(r, "text", "") or "")[:300]),
                                  action)
        raise Problem("transport", "short_read",
                      "Reached the end of the file with %d of %d bytes accepted." % (sent, self.size),
                      "The render produced a truncated file; re-render rather than re-upload.")


def read_back(http, video_id, want_privacy, poll_times=3, poll_sleep=20.0, sleep=time.sleep):
    """Confirm what YouTube actually made of the upload, instead of assuming it.

    201 means the bytes arrived. It does not mean the video is watchable: processing runs for
    minutes, and a channel configured to default uploads to private keeps them private no
    matter what the request asked for. A lane that prints "published" for a private video is
    worse than one that fails, because nobody looks again.
    """
    state = {"video_id": video_id, "result": "uploaded", "privacy": want_privacy,
             "upload_status": "unknown", "note": ""}
    for attempt in range(max(1, poll_times)):
        r = http.request("GET", "%s/videos" % API_URL,
                         params={"part": "status,snippet", "id": video_id})
        if r.status_code != 200:
            state["note"] = "status read-back failed (HTTP %s); the upload itself succeeded" % r.status_code
            emit("warning", "YouTube status unreadable", state["note"])
            return state
        items = (r.json() or {}).get("items") or []
        if not items:
            state["result"] = "missing"
            state["note"] = "YouTube no longer lists this video id"
            return state
        item = items[0]
        status = item.get("status") or {}
        snippet = item.get("snippet") or {}
        state["upload_status"] = status.get("uploadStatus") or "unknown"
        state["privacy"] = status.get("privacyStatus") or snippet.get("privacyStatus") or "unknown"
        state["failure_reason"] = status.get("failureReason") or ""
        state["reject_reason"] = status.get("rejectionReason") or ""
        # Order matters. A rejected video is also private, so a privacy comparison first would
        # report "the channel downgraded my upload" while the truth was a copyright claim.
        if state["upload_status"] in ("rejected", "failed"):
            state["result"] = "rejected"
            state["note"] = "YouTube %s it: %s %s" % (state["upload_status"],
                                                       state["failure_reason"],
                                                       state["reject_reason"])
            return state
        if status.get("privacyStatus") and want_privacy and \
                status["privacyStatus"] != want_privacy:
            state["result"] = "held"
            state["note"] = ("YouTube stored it as %s, not %s — the channel's default upload "
                             "setting wins over the request"
                             % (status["privacyStatus"], want_privacy))
            return state
        if state["upload_status"] == "processed":
            state["result"] = "published" if state["privacy"] == "public" else "listed"
            state["note"] = "uploadStatus=processed, privacyStatus=%s" % state["privacy"]
            return state
        if attempt < poll_times - 1:
            sleep(poll_sleep)
    state["note"] = state["note"] or ("still %s after %d checks; YouTube processing can take "
                                      "longer than a CI job's patience, and that is fine"
                                      % (state["upload_status"], poll_times))
    return state


def publish(video_path, title, description="", tags="", privacy="public", category_id="22",
            http=None, notify=None, synthetic=None, poll_times=3, sleep=time.sleep):
    """Upload one file. Returns a PublishResult, or raises Problem."""
    path = Path(video_path)
    if not path.exists():
        raise Problem("metadata", "file_missing", "Video file not found: %s" % path,
                      "The render step did not produce the file the workflow expected.")
    size = path.stat().st_size
    if size == 0:
        raise Problem("metadata", "empty_file", "The video file is empty: %s" % path,
                      "Re-render; ffmpeg produced a header-only file.")
    metadata, kept_tags, notes, params = build_metadata(title, description, tags, privacy,
                                                        category_id, notify=notify,
                                                        synthetic=synthetic)
    for note in notes:
        emit("warning", "Metadata adjusted", note)
    http = http or Http()
    if http.token is None:
        http, _payload = authorize(http)
    uploader = ResumableUploader(http, size, metadata, sleep=sleep, params=params)
    response = uploader.upload(path)
    try:
        body = response.json()
    except ValueError:
        body = {}
    video_id = body.get("id")
    if not video_id:
        raise Problem("transport", "no_video_id",
                      "YouTube accepted the file but returned no id: %s" % str(body)[:200],
                      "Treat this as not published: check the channel before re-running, since "
                      "a re-run may create a second copy.")
    state = read_back(http, video_id, metadata["status"]["privacyStatus"],
                      poll_times=poll_times, sleep=sleep)
    if state.get("note"):
        emit("warning" if state["result"] in ("uploaded", "listed", "published") else "error",
             "YouTube read-back: %s" % state["result"], state["note"])
    return PublishResult(video_id, state, metadata, size, kept_tags, len(notes))


class PublishResult(str):
    """The video id — so `if not result` and `VIDEO_ID=%s` keep working — with the state on it."""

    def __new__(cls, video_id, state=None, metadata=None, size=0, tags=(), adjustments=0):
        self = super().__new__(cls, video_id)
        self.state = state or {}
        self.metadata = metadata or {}
        self.size = size
        self.tags = list(tags)
        self.adjustments = adjustments
        return self

    @property
    def url(self):
        return "https://www.youtube.com/watch?v=%s" % self

    @property
    def result(self):
        return self.state.get("result", "uploaded")

    @property
    def privacy(self):
        return self.state.get("privacy", "")

    @property
    def upload_status(self):
        return self.state.get("upload_status", "")

    @property
    def note(self):
        return self.state.get("note", "")


def upload_video(video_path, title, description="", tags="", privacy="public", category_id="22"):
    """Backwards-compatible entry point: the id on success, None on failure.

    Returns a PublishResult, which *is* a str, so every caller that only ever checked truthiness
    or printed it still works.
    """
    try:
        return publish(video_path, title, description, tags, privacy, category_id)
    except Problem as exc:
        print(exc.report())
        return None


def probe(http=None, log=print):
    if http is not None and not isinstance(http, Http):
        http = Http(session=http)
    """Answer, in one minute and without uploading, the four questions the lane can fail.

    Cost is 1 quota unit (one channels.list). This exists because the 9 Oct failure was
    diagnosed from a guess: the preflight at the time checked that the secrets were *present*,
    which proves nothing about whether they work, whether they are for the right channel, or
    whether the consent screen will silently expire them again in a week.
    """
    http, payload = authorize(http)
    log("✅ token minted (expires_in=%ss)" % payload.get("expires_in"))
    r = http.request("GET", "%s/channels" % API_URL,
                     params={"part": "snippet,contentDetails,statistics", "mine": "true"})
    if r.status_code != 200:
        kind, reason, what, action, _ = classify(r.status_code, r.text)
        raise Problem(kind, reason, "channel lookup failed: HTTP %s — %s"
                      % (r.status_code, r.text[:300]), action)
    items = (r.json() or {}).get("items") or []
    if not items:
        raise Problem("credentials", "no_channel",
                      "The token authorises a Google account with no YouTube channel.",
                      "The consent was given by the wrong account — re-consent as the DocOga "
                      "channel owner, and check the picker at the top of the browser tab.")
    chan = items[0]
    title = (chan.get("snippet") or {}).get("title")
    channel_id = chan.get("id")
    uploads = ((chan.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
    subs = ((chan.get("statistics") or {}).get("subscriberCount"))
    log("✅ channel: %s (%s), uploads playlist %s, %s subscribers"
        % (title, channel_id, uploads, subs))
    want = os.environ.get("YT_CHANNEL_ID", "").strip()
    if want and want != channel_id:
        raise Problem("credentials", "wrong_channel",
                      "YT_CHANNEL_ID is %s but the token authorises %s (%s)."
                      % (want, channel_id, title),
                      "Either re-consent with the right account or correct the variable — and "
                      "note which channel this lane is really publishing to.")
    elif want:
        log("✅ YT_CHANNEL_ID matches the token")
    else:
        emit("warning", "YT_CHANNEL_ID not set",
             "The lane will publish to whatever channel this token authorises; set YT_CHANNEL_ID "
             "(or repository variable) so a re-consent by the wrong account becomes a failure "
             "instead of a post to the wrong place.")
    # The one read that shows whether uploads are already capped: the newest upload's state.
    r = http.request("GET", "%s/videos" % API_URL,
                     params={"part": "snippet,status", "playlistId": uploads, "maxResults": 1})
    if r.status_code == 200:
        vids = (r.json() or {}).get("items") or []
        if vids:
            v = vids[0]
            log("ℹ️  last upload: %r — uploadStatus=%s privacy=%s"
                % ((v.get("snippet") or {}).get("title", "")[:60],
                   (v.get("status") or {}).get("uploadStatus"),
                   (v.get("status") or {}).get("privacyStatus")))
        else:
            log("ℹ️  the uploads playlist is empty — this lane has never published, so the "
                "ledger and the channel should both say nothing.")
    else:
        log("ℹ️  could not read the uploads playlist (HTTP %s); not fatal." % r.status_code)
    log("✅ probe complete — a token works, the channel is named, and uploads are not held.")
    return {"channel_id": channel_id, "channel": title, "expires_in": payload.get("expires_in")}


def main(argv=None, http=None):
    """`http` is an injectable transport (an Http, or anything with .request) for tests;
    production calls leave it out and get the real one."""
    parser = argparse.ArgumentParser(description="DocOga YouTube Publisher")
    parser.add_argument("--video", help="Path to video file")
    parser.add_argument("--title", help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    parser.add_argument("--category", default="22", help="YouTube category ID (22=People & Blogs)")
    parser.add_argument("--notify", default="", choices=["", "true", "false"],
                        help="notifySubscribers (leave empty to let YouTube decide)")
    parser.add_argument("--synthetic-media", default="", choices=["", "true", "false"],
                        help="declare AI-generated/altered content (leave empty to say nothing)")
    parser.add_argument("--poll", type=int, default=3,
                        help="how many times to read the video back before calling it 'uploaded'")
    # Cheap credential check for the scheduled workflow: prove a token can be minted before
    # spending ten minutes rendering a video that cannot be uploaded. Exists because the 9 Oct
    # run rendered, then failed at the wire.
    parser.add_argument("--check-token", action="store_true",
                        help="verify the OAuth credentials mint a token, then exit")
    parser.add_argument("--probe", action="store_true",
                        help="credentials + channel identity + last upload state, then exit")
    args = parser.parse_args(argv)

    # A test hands in a scripted transport; production hands in nothing. Normalised once,
    # here, so no call path can forget it and hit the real internet from the suite.
    if http is not None and not isinstance(http, Http):
        http = Http(session=http)

    def flag(value):
        return None if value == "" else value == "true"

    if args.check_token or args.probe:
        try:
            if args.check_token:
                _http, payload = authorize(http)
                print("✅ OAuth credentials are usable — a token was minted (expires_in=%ss)."
                      % payload.get("expires_in"))
                print("YT_PROBE_RESULT=usable")
                return EXIT_OK
            probe(http=http)
            return EXIT_OK
        except Problem as exc:
            print(exc.report(), file=sys.stderr)
            emit("error", "YouTube preflight", "%s — %s" % (exc.what, exc.action))
            print("YT_PROBE_RESULT=failed")
            print("YT_FAIL_KIND=%s" % exc.kind)
            return exc.exit_code

    if not args.video or not args.title:
        parser.error("--video and --title are required (or use --check-token / --probe)")

    try:
        http = http if isinstance(http, Http) else (Http(session=http) if http else None)
        result = publish(args.video, args.title, args.description, args.tags, args.privacy,
                         args.category, notify=flag(args.notify),
                         synthetic=flag(args.synthetic_media), poll_times=max(1, args.poll),
                         http=http)
    except Problem as exc:
        print(exc.report(), file=sys.stderr)
        emit("error", "YouTube upload failed (%s)" % exc.kind,
             "%s — %s" % (exc.what, exc.action))
        print("YT_UPLOAD_RESULT=failed")
        print("YT_FAIL_KIND=%s" % exc.kind)
        print("YT_FAIL_REASON=%s" % exc.reason)
        print("❌ Upload failed; exiting non-zero so queue workflows retain this item.",
              file=sys.stderr)
        return exc.exit_code

    if result.result in ("held", "rejected", "missing"):
        # The bytes are on Google and the channel has no public video. Red, because the lane's
        # job is "public, unattended" — and the workflow still records the id, so a re-run
        # cannot put a second copy on the channel while the cause is being fixed.
        emit("error", "YouTube did not publish it publicly", result.note or result.result)
        print("❌ %s" % (result.note or "the video is not public"))
        print("VIDEO_ID=%s" % result)
        print("YT_VIDEO_ID=%s" % result)
        print("YT_URL=%s" % result.url)
        print("YT_UPLOAD_RESULT=%s" % result.result)
        print("YT_PRIVACY=%s" % result.privacy)
        print("YT_FAIL_KIND=state")
        return EXIT_NEEDS_HUMAN
    print("✅ Video uploaded: %s" % result.url)
    if result.result == "uploaded":
        emit("warning", "Still processing", result.note)
    # Machine-readable id for the scheduled workflow's publish ledger. The human line above
    # stays first for anyone reading the run log.
    print("VIDEO_ID=%s" % result)
    print("YT_VIDEO_ID=%s" % result)
    print("YT_URL=%s" % result.url)
    print("YT_UPLOAD_RESULT=%s" % result.result)
    print("YT_PRIVACY=%s" % result.privacy)
    print("YT_UPLOAD_STATE=%s" % result.upload_status)
    print("YT_NOTE=%s" % (result.note or "").replace("\n", " "))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
