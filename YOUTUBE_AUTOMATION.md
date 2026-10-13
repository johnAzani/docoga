# YouTube Shorts automation

The scheduled workflow creates a new branded vertical Short from the reviewed,
non-legal-advice content templates and uploads it to YouTube. It is designed to
run without a person clicking **Run workflow** or maintaining the upload queue.

## Schedule and behavior

- **Tuesday and Friday, 6:00 PM West Africa Time** (`17:00 UTC`).
- GitHub Actions runs the workflow from the repository's default branch.
- Each run picks a repeatable topic for the Lagos calendar date, renders a
  1080x1920 MP4, and uploads it as **public** with `#Shorts` metadata.
- The scheduled workflow does not read or edit `youtube_queue.json` and does
  not commit generated MP4s to the repository.
- Missing dependencies, a failed render, missing credentials, or a rejected
  upload fail the run. The uploader exits non-zero unless YouTube returns a
  video ID.
- No Arena workflow-dispatch permission is needed for scheduled runs. That
  permission is only needed to start a one-off manual run through the API.

## The three safeguards (added 8 Oct 2026)

The job is never watched by a human, so it is built to fail loudly and to
remember what it did.

### 1. Preflight, before the render

The three secrets are checked in the first 30 seconds. If any is missing the
run stops with an error naming it, and **nothing is rendered or uploaded**.
Previously the failure surfaced only after a ten-minute render, from inside the
uploader, without saying which secret was absent.

Since 13 Oct 2026 the preflight runs `tools/yt_publish.py --probe` rather than
a presence test, because presence proved nothing: the 9 Oct scheduled run had a
**green** preflight and a dead token. The probe mints a token, reads
`channels?mine=true`, prints the channel name and id it would publish to, compares
them with `YT_CHANNEL_ID`, and prints the newest upload's `uploadStatus` and
privacy. Cost: 1 quota unit of 10,000 a day.

### 2. A publish ledger — `logs/youtube_published.json`

Every successful upload is recorded in the repo: title, topic, video id, URL,
privacy, WAT date, run id and file size. It answers "what did we publish, and
where is it?" without opening YouTube, and it powers the duplicate guard.

```bash
python3 tools/youtube_ledger.py show            # recent publishes
python3 tools/youtube_ledger.py show --limit 50
```

The topic rotation holds six topics and the job runs twice a week, so a title
naturally returns after about three weeks — that is intended, and the guard's
7-day window does not block it. What it *does* block is the accident: a
re-run, a GitHub retry, or two dispatches on the same day putting the same
Short on the channel twice. A skipped run is **green**, with a notice naming
the title.

The file is committed back to the default branch by the job itself
(`contents: write`). Bookkeeping never turns a successful publish red: if the
commit cannot land, the step emits a warning and the job stays green — the
Short is already live.

A missing or corrupt ledger never blocks publishing; a damaged file is backed
up as `logs/youtube_published.json.corrupt-<timestamp>` rather than
overwritten.

### 3. A visible issue on failure

Any failed run opens an issue labelled `youtube-automation` — or, if one is
already open for that date, comments on it — with a link to the run and a
four-step triage list (secrets → revoked token → YouTube audit → quota). A red
dot in a repo nobody opens is the same as silence; this puts it where it will
be seen.

## Running it by hand

**Actions tab → YouTube Shorts Auto-Generate and Publish → Run workflow:**

| Input | Default | Meaning |
|---|---|---|
| `privacy` | `public` | Override for this run only. |
| `force` | `false` | Publish even if the ledger already has this title inside the 7-day window. |
| `probe_only` | `false` | Run the diagnosis and stop: no render, no upload, no ledger write. The first thing to reach for when a run is red. |

To change the privacy for *every* future run without touching code: create a
repository **variable** (Settings → Secrets and variables → Actions →
Variables) named `YT_PRIVACY` set to `unlisted` or `private`. Useful for
watching the first few land before they go public. An invalid value fails the
run loudly instead of publishing at the wrong privacy.

## One-time requirements

> **The order across all lanes is its own document:** `docs/LAUNCH_SEQUENCE.md` — the
> exact command or tap for every human step, the screen to expect, and what to check the
> next morning. Doing the steps out of order costs an issue titled `… [setup]`, not a post.

Create these as **repository Actions secrets** (not merely as environment
secrets, because this job does not select a GitHub environment):

- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`

The Google Cloud project must have YouTube Data API v3 enabled and the refresh
token must include the `youtube.upload` scope.

Two corrections to this section, checked against Google's own reference on
8 Oct 2026 rather than remembered:

* **Unverified API projects do *not* have their uploads forced private.** The
  `videos.insert` page states the opposite in one line: "Videos uploaded from
  unverified API projects are not restricted to private viewing mode." An audit
  is about *quota* and about publishing the OAuth app, not about whether today's
  Short is watchable. If a video of ours lands private, the cause is the channel's
  own upload defaults, and `tools/yt_publish.py` now says so out loud instead of
  letting the run go green.
* **What *does* expire is the token.** While the OAuth consent screen is set to
  "In testing", Google issues refresh tokens that die after **7 days**, and only
  listed test users may use the app at all. A lane that uploads on Tuesday and
  Friday walks into that wall every week.

The one-time repair, tap by tap (the expected screen in brackets):

1. console.cloud.google.com → pick the DocOga project → **APIs & Services →
   OAuth consent screen** *[a page with a "Publish app" button and a status of
   "In testing" or "In production"]*.
2. If the status is **In testing**, click **Publish app** *[a confirmation
   saying the app will be available to all users; for an internal upload bot that
   asks for nothing but `youtube.upload`, that is the intent]*. Until it is
   published, add the DocOga Google account under **Test users** instead — a
   working stopgap that still expires tokens weekly.
3. **Credentials → OAuth client ID → the client this lane uses** — confirm the
   type is *Desktop app* and that no redirect URIs are needed *[the client list
   shows the client and its type]*.
4. Re-run the consent flow to mint a fresh refresh token, then
   `gh secret set YT_REFRESH_TOKEN --body '<token>'` *(and, if the client changed,
   `YT_CLIENT_ID` and `YT_CLIENT_SECRET` too — three secrets, replaced together;
   replacing one of three is how the 9 Oct run stayed red for a week.)*
5. Prove it without uploading anything:

   ```bash
   gh workflow run youtube_scheduled.yml -f probe_only=true
   ```

   *[Actions → the run → "Diagnose the YouTube lane" → "Probe credentials,
   channel and last upload": the log ends with* `✅ probe complete — a token
   works, the channel is named, and uploads are not held.` *If it instead prints*
   `↳ fix:`, *do what that line says — it was written for this exact failure.]*

## Content safeguards

The automatic content is deliberately limited to general document-keeping
checklists. It avoids fixed notice periods, blanket statements about tenant
rights, and unsupported statistics. Each Short includes a reminder that rules
vary by state and agreement and that the content is general information, not
legal advice.

## Brand rules applied to every frame

These are locked rules from `docs/DESIGN_SYSTEM.md` and
`docs/SESSION_CONTEXT.md`, and each one is enforced by a test so a future edit
cannot quietly undo it:

- **No logo on video.** Owner direction 21 Sep 2026: the logo is not stamped
  on social posts, and `docs/SESSION_CONTEXT.md` is explicit that it is never
  used on reels or videos. The real logo file is only ever composited onto
  *static* images, by `tools/add_logo.py`. An earlier revision of
  `scripts/generate_short_video.py` broke this — it composited the official
  logo onto every slide, where it also collided with the CTA bar.
- **Film grain, σ≈2.2** — `BRAND_STYLE.md` §3 lists grain as always present on
  every finished piece, video included.
- **CTA present** — `DOCOGA.COM.NG` on every slide, in the locked `BRAND_BLUE`.
- **Safe areas** — type is centred above the CTA bar with an 84px margin, so
  nothing is clipped on mobile or hidden behind the platform UI.

`tests` covering these live in
`tools/tests/test_youtube_short_generation.py` and run on every push and pull
request via `.github/workflows/verify.yml`.

To pause future uploads, disable **YouTube Shorts Auto-Generate and Publish**
in the repository's Actions tab. No queue needs to be cleared.

## Testing it

The pipeline's logic is covered by `tools/tests/`:

- `test_youtube_short_generation.py` — content rotation, brand rules, the
  outputs the workflow reads for a run;
- `test_youtube_ledger.py` — the duplicate guard in both directions, corrupt
  and wrong-shaped ledger files, and the size cap;
- `test_yt_publish.py` — 59 tests against a scripted Google: 256 KB chunk
  alignment, a 308 treated as progress, a partial 308 resumed at the server's
  range, 5xx backoff with a resume probe, one session restart on 404, every
  documented `videos.insert` error mapped to a kind and a repair, the metadata
  clamps, the privacy read-back, the exit-code split between "the code failed"
  and "a human must re-author a token", and the `VIDEO_ID=` line the workflow
  parses;
- `test_workflow_contract.py` — static checks on the YAML: every
  `steps.<id>.outputs.<key>` reference points at a step that exists, the guard
  runs before the upload, and the permissions, concurrency group and failure
  issue are all still wired.

## 13 Oct 2026 — the protocol, the read-back, and a probe

The lane had a green preflight, a clean render, a working duplicate guard, and a
red upload step whose only output was `Exit code 1`. The failure issue that ran off
to fetch had to *guess* among four causes, and the log that would have settled it is
not readable afterwards from the agent sandbox (Actions log storage lives on a host
outside its allowlist). So the whole lane was rebuilt around one rule: **a failure
has to arrive already diagnosed.**

### The wire protocol, done properly

`tools/yt_publish.py` now speaks Google's resumable protocol instead of approximating
it: `X-Upload-Content-Length`/`X-Upload-Content-Type` on the session POST, then
2 MiB chunks — a multiple of the required 256 KiB, all the same size except the last —
each with its own `Content-Range`.

* **308 is progress, not failure.** Google answers a 308 with the byte range it
  *holds*; the client resumes from there. The previous code sent the whole file in one
  PUT and treated anything but 200 as an error, which would have killed a perfectly
  healthy upload. A 308 that already covers the whole file means "still finalising":
  the code polls the session (bounded) rather than declaring defeat.
* **5xx backs off and asks.** 408/429/5xx → exponential backoff, then an empty
  `Content-Range: bytes */total` PUT to learn where to resume, then continue. The
  retries are counted; giving up prints the byte offset.
* **404/410 restarts the session once.** Google does not publish the session lifetime;
  an expired session is a restart, not a failure — and if it dies twice, the message
  says *the bytes never reached YouTube, so a re-run is safe*, which is the one thing a
  reader needs to know.
* **Nothing may hang.** Every request goes through one `Http` wrapper that attaches a
  `(15 s, 300 s)` timeout, so there is no call site that can forget it. A hung PUT is
  the worst failure mode in an unattended job: it eats the 30-minute ceiling and leaves
  no error at all.

### The upload is read back before anything says "published"

`201` means the bytes arrived. It does not mean anybody can watch the video. The
uploader now GETs `videos?part=status,snippet` and reports what it finds:
`published` (processed + public), `listed` (processed, not public), `uploaded`
(still processing — normal, and green), `held` (YouTube stored a different privacy
than requested — the channel's upload defaults winning over the request), or
`rejected` (with Google's own `failureReason`). `held`/`rejected` are red, on
purpose: this lane's contract is *public*. The id is printed even then, so the ledger
still records the video and a re-run cannot put a second copy on the channel.

### Exit codes carry a decision, not just a status

`0` published · `1` the code or the network failed (re-run is safe, no id) · `2` a
human with a browser must fix it. `2` is the number that matters: it turns "the
upload step is red again" into "this is a Google-account conversation, here is the
sentence to follow", and the uploader has already printed that sentence — every
documented `videos.insert` error (`invalidTitle`, `invalidTags`, `invalidCategoryId`,
`forbiddenPrivacySetting`, `dailyUploadLimitExceeded`, …) plus `invalid_grant` and
`invalid_client` maps to a *kind* and a *repair* in one `REASONS` table, used by the
log, the `::error` annotation, the run summary and the issue body alike.

### Deliberately not done

* no `google-api-python-client` dependency — the whole lane is a dozen requests, and a
  vendored client library is one more thing that silently breaks on a version bump;
* no auto-retry of a red run, and no re-minting of the refresh token: consent is a
  browser interaction, and an agent that can fake it can also lose the channel;
* no silent `unlisted` fallback when a channel refuses `public` — the lane says
  `held` and names the fix, because quietly changing the audience is worse than red;
* no `containsSyntheticMedia` declaration by default. The flag exists
  (`--synthetic-media true|false`) because the renders are AI-assembled and YouTube
  expects self-declaration for realistic synthetic media; flipping it on is a content
  policy decision for the owner, not a bug fix to slip into an infrastructure commit;
* no `--license`, `--publishAt`, localizations, or scheduling: one Short, twice a
  week, public, now.
