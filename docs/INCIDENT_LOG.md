# Incident log — automation issues and how each was closed

The lanes open a GitHub issue when a post fails. This log records the resolution so a
closed issue is never a mystery. Newest first.

| Issue | Lane · date | Cause | Fix | Closed |
|---|---|---|---|---|
| — | Every scheduled lane · 13–17 Oct 2026 | GitHub `schedule` events dropped/late in private repos since 26 Aug 2026: Threads, Instagram and replies ran 1× a day instead of 3×, Shorts 1 weekday in 4, boost never, Telegram 4–7 h late | The DocOga clock: Cloudflare Worker rings every lane via `workflow_dispatch` on the minute (`docs/CLOCK.md`); heartbeat counts dispatches; Verify/build-check trimmed to protect the 2,000 min/month | 17 Oct 2026 (pending the owner's one-time `GH_DISPATCH_TOKEN`) |
| #52 | YouTube Manage · 16 Oct 2026 | Plan not applied: the Google token carried only `youtube.force-ssl` | Monday token audit now lists the 7 required Google scopes (`docs/TOKENS.md`); the lane fails soft until the owner re-consents once | 17 Oct 2026 |
| #32 | Facebook · 14 Oct 2026 (run) | Post text / escaping path at run time | #54 — lane green daily since 15 Oct | 17 Oct 2026 |
| #29 | Facebook · 14 Oct 2026 (setup) | Page token of the wrong shape | #54/#55 — Page-token probe prints the exact cause on the run summary | 17 Oct 2026 |
| #26 | Deep-Dive dd2 · 14 Oct 2026 | A free-tier quota pause was treated as a failure | #37 — empty bucket is exit 5 (pause); Narrator warm-up resumes at the reset; episodes publish since | 17 Oct 2026 |
| #16 | Telegram · 11 Oct 2026 | MarkdownV2 escaping swallowed the links | #54 — links tagged before `escape()`; lane green daily | 17 Oct 2026 |
| #12 | YouTube Shorts · 9 Oct 2026 | Pre-MotionStudio renderer | #22 onward — MotionStudio + `SHORTS_VOICE=required`; Shorts publish Tue/Wed/Fri | 17 Oct 2026 |
