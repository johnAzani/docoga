# Incident log — automation issues and how each was closed

The lanes open a GitHub issue when a post fails. This log records the resolution so a
closed issue is never a mystery. Newest first.

| Issue | Lane · date | Cause | Fix | Closed |
|---|---|---|---|---|
| — | Every lane · 20 Oct 2026, 7:05pm onward | GitHub refused to start any job: the **private-repo free allowance (2,000 Actions min/month)** was spent on day 20 (docoga ≈ 1,410 min, three older repos ≈ 590 min; the new footage renders ≈ 24 min each and CI on every PR push were the big drinkers). The evening Short (`Np1VY20sxRQ`) had already uploaded at 6:24pm; Instagram 7:10pm, Facebook Story 7:40pm, Threads 8:10pm, replies, the 9:00pm heartbeat and a late second Shorts fire all died unstarted | Owner's decision 9:45pm: **make the repository public** (unlimited free minutes). Pre-flip audit of all 529 commits found a live Telegram bot token in `send_test_post.sh` and the real vault key in a test fixture → both rotated (`docs/TOKENS.md` §10), IG/Threads boxes deleted and tokens re-minted, YT/TikTok boxes re-sealed under the new key with client secrets rotated; `tools/secret_scan.py` now gates QA/CI | 20 Oct 2026 (pending the owner's taps) |
| — | YouTube (stats, Shorts, deep-dive, boost) · 17–19 Oct 2026 | The 17 Oct re-consent picked the account's **personal channel** (`Millionaire_money1`, 0 videos) on Google's second chooser, not the DocOga brand channel; the Monday stats snapshot recorded that channel's zeros, and the next Shorts upload would have been refused (`wrong_channel`) or, with `YT_CHANNEL_ID` unset, gone to the wrong channel | Consent exchange now reads `channels?mine=true` and refuses a mismatch before sealing (`GOOGLE_CONSENT=wrong_channel`); `yt_stats` refuses to record a stranger's numbers; owner re-consents once, picking DocOga | open — awaiting the re-consent |
| — | Threads · 17–18 Oct 2026 (every slot) | Words-only posts: the IMAGE container was asked for with `crossreshare_to_ig=true`, Threads refused that one flag (code 10, the Page↔Instagram link is blocked) and the lane dropped the whole card; the 18 Oct lunch post then died on `threads_publish` with "Media Not Found" (4279009) a second after its container read FINISHED | Image ladder: full ask → without cross-share → without topic tag → bare image (`create_image_container_with_fallbacks`); publish forgives 4279009 three times, ten seconds apart | 18 Oct 2026 |
| #84 | Instagram · 17 Oct 2026, 7:10pm (first clock-driven run) | The card push to `main` was rejected as non-fast-forward: PR #83 merged while the lane was rendering, and the render step pushed once with no rebase — then waited 15 min for a URL that could never go live (`cause=media`) | #85 — the render step rebases onto the branch and pushes up to three times (the Threads lane already did) | 17 Oct 2026 |
| — | Every scheduled lane · 13–17 Oct 2026 | GitHub `schedule` events dropped/late in private repos since 26 Aug 2026: Threads, Instagram and replies ran 1× a day instead of 3×, Shorts 1 weekday in 4, boost never, Telegram 4–7 h late | The DocOga clock: Cloudflare Worker rings every lane via `workflow_dispatch` on the minute (`docs/CLOCK.md`); heartbeat counts dispatches; Verify/build-check trimmed to protect the 2,000 min/month | 17 Oct 2026 (pending the owner's one-time `GH_DISPATCH_TOKEN`) |
| #52 | YouTube Manage · 16 Oct 2026 | Plan not applied: the Google token carried only `youtube.force-ssl` | Monday token audit now lists the 7 required Google scopes (`docs/TOKENS.md`); the lane fails soft until the owner re-consents once | 17 Oct 2026 |
| #32 | Facebook · 14 Oct 2026 (run) | Post text / escaping path at run time | #54 — lane green daily since 15 Oct | 17 Oct 2026 |
| #29 | Facebook · 14 Oct 2026 (setup) | Page token of the wrong shape | #54/#55 — Page-token probe prints the exact cause on the run summary | 17 Oct 2026 |
| #26 | Deep-Dive dd2 · 14 Oct 2026 | A free-tier quota pause was treated as a failure | #37 — empty bucket is exit 5 (pause); Narrator warm-up resumes at the reset; episodes publish since | 17 Oct 2026 |
| #16 | Telegram · 11 Oct 2026 | MarkdownV2 escaping swallowed the links | #54 — links tagged before `escape()`; lane green daily | 17 Oct 2026 |
| #12 | YouTube Shorts · 9 Oct 2026 | Pre-MotionStudio renderer | #22 onward — MotionStudio + `SHORTS_VOICE=required`; Shorts publish Tue/Wed/Fri | 17 Oct 2026 |

## 22 Oct 2026 — one `git add` line kept every brain decision off main for five nights

**Seen:** the dashboard's new "plan in plain words" row showed the 1:30am Brain as *not
recorded* two nights running, and Threads' 8:10pm slot carried a card, not the Short, on
the first night Threads videos were live. `logs/shorts_media.json` and
`logs/brain_deepdive.json` did not exist on `main`; no "Auto: brain …" commit had landed
since 17 Oct; the TikTok drafts ledger stopped on 18 Oct; last night's Instagram Reel
(`Dew7X5tlVdH`, published by the 6:00pm lane) was unrecorded.

**Cause:** `git add path1 path2 path3 2>/dev/null || true`. When ONE pathspec matches no
file, git prints `fatal: pathspec '…' did not match any files` and adds **nothing** — the
other paths included. `brain/answers` exists on Mondays only; `logs/telegram_owner.json`
has never existed (the owner has not sent the bot the word "owner"). The `|| true` kept the
step green. Every pack the brain approved, the newsdesk, the feedback file, the Deep-Dive
attempts ledger, the Threads hand-over record, the TikTok draft ids and the Instagram Reel
record were written on the runner and thrown away with it — which is also why every lane
posted "from the rotation" and the Shorts rotation (six scripts) repeated a topic within a
week (15 → 21 Oct).

**Fix (PR #126):** every multi-path `git add` in every workflow is now a loop — `for path
in …; do if [ -e "$path" ]; then git add "$path"; fi; done` — and
`test_workflow_contract.test_no_git_add_names_two_paths_at_once` forbids the old shape.
The Instagram Reel record was backfilled by hand. Two Deep-Dive gate slips from the same
nights (a 104-word section against a 105 floor; the style word "game-changer") are healed
rather than refused.

**Lesson:** a green step that commits is not a commit. The dashboard's evidence rows found
in a day what three weeks of green runs hid — keep judging by ledgers, never by conclusions.
