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

To change the privacy for *every* future run without touching code: create a
repository **variable** (Settings → Secrets and variables → Actions →
Variables) named `YT_PRIVACY` set to `unlisted` or `private`. Useful for
watching the first few land before they go public. An invalid value fails the
run loudly instead of publishing at the wrong privacy.

## One-time requirements

Create these as **repository Actions secrets** (not merely as environment
secrets, because this job does not select a GitHub environment):

- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`

The Google Cloud project must have YouTube Data API v3 enabled and the refresh
token must include YouTube upload scope. YouTube may keep API uploads private
until the API project satisfies its verification/audit requirements; this is a
YouTube-side restriction, not a GitHub setting.

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
- `test_yt_publish.py` — upload exit status and the `VIDEO_ID=` line the
  workflow parses;
- `test_workflow_contract.py` — static checks on the YAML: every
  `steps.<id>.outputs.<key>` reference points at a step that exists, the guard
  runs before the upload, and the permissions, concurrency group and failure
  issue are all still wired.
