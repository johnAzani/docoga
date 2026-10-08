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

To pause future uploads, disable **YouTube Shorts Auto-Generate and Publish**
in the repository's Actions tab. No queue needs to be cleared.
