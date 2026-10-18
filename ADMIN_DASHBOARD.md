# DocOga Owner Dashboard — operator handbook

The one file that tells you how the owner surface is built, what it can honestly
claim, and how to turn it on. Written 12 Oct 2026, the day the ₦0 rebuild landed.

```
site/admin.html ──fetch──▶ worker/index.js /admin/*  ◀── mobile/ APK (a signed door onto the page)
       │                            │
       └── Cloudflare Pages         └── Cloudflare KV  (the same namespace the passes live in)
```

---

## 1. What it is

| | |
|---|---|
| The page | `https://docoga.com.ng/admin` — one file, `site/admin.html`, no framework, no build, no CDN |
| The API | `https://docoga-pass.johnazani.workers.dev/admin/*` — 12 routes inside the existing `docoga-pass` Worker |
| The app | `mobile/` — Capacitor 8.5.3 shell, `ng.com.docoga.owner`, loads the page above |
| Cost | ₦0. Pages + Worker on free tiers, KV on the free allowance, GitHub Actions free minutes |
| Manual work after setup | none. There is no cron to run, no cache to purge, no schema to migrate |

Six tabs: **Today · Passes · Business · Leads · Sell · Security.**

**The design rule the whole thing stands on:** the dashboard never guesses. Every
number carries the basis it was computed from, and anything it cannot prove it
says it cannot prove. That is why the page can be public: reading it is useless
without the passphrase, and being *in* it never shows a number that looks firmer
than the data underneath it.

---

## 2. Auth model

* `POST /admin/login {passphrase}` → `{token, expiresInSeconds: 43200}`.
  The token is `sid + "." + base64(HMAC-SHA256("ad_"+sid, ADMIN_AUTH_SECRET))`.
* The server reads `adm:sess:{sid}` on **every** admin call. Revocation is
  therefore instant — no TTL wait, no cache to invalidate.
* The session slides: when fewer than 6 hours are left, it is renewed to 12.
  Open it every morning and you never type the passphrase; leave it alone for two
  weeks and it is gone.
* `Authorization: Bearer …` only. No cookie, and that is not incidental: a WebView
  whose origin differs from the API's treats cookies as third-party and drops
  them. Bearer survives, so the APK works with zero cookie configuration.
* Fail-lock: `adm:fail:{ip}`, 5 wrong passphrases per 30 min → `429`. Rate limits
  are per IP because the login route is the only one reachable anonymously.
* Both `ADMIN_PASSPHRASE` and `ADMIN_AUTH_SECRET` must exist or **every** admin
  route answers `503 {admin_disabled}`. Checked before the 401 branch, so a
  misconfigured deployment cannot look like a wrong password. Fail closed, always.
* The page stores the token in `localStorage["docoga.admin.token"]` — the only
  write to storage anywhere in the file. The Security tab has
  **Sign out every other device**, which deletes the session record server-side.

No secret ever appears in `site/admin.html`, in the APK, or in any admin response
(`adminworkertest.mjs` asserts the last of those against four real key names).

---

## 3. One-time setup (5 minutes)

```bash
cd worker
# 1 · the passphrase you type into the page. Generate, never invent:
openssl rand -base64 18 | tr -d '=+/' | sed 's/\(.\{6\}\)/\1 /g'
wrangler secret put ADMIN_PASSPHRASE        # paste, enter
# 2 · the HMAC key for session tokens — a different secret, never reused:
openssl rand -hex 32
wrangler secret put ADMIN_AUTH_SECRET       # paste, enter
npx wrangler deploy                         # secrets land on the next deploy too
```

Verify it is on, from any shell:

```bash
curl -s -X POST https://docoga-pass.johnazani.workers.dev/admin/login \
     -H 'content-type: application/json' -d '{"passphrase":"wrong-on-purpose"}'
# 401 {"ok":false,"error":"bad_passphrase"}   → configured
# 503 {"ok":false,"error":"admin_disabled"}   → secret missing; do step 3 again
T=$(curl -s -X POST https://docoga-pass.johnazani.workers.dev/admin/login \
    -H 'content-type: application/json' -d "{\"passphrase\":\"<the real one>\"}" \
    | sed 's/.*"token":"\([^"]*\)".*/\1/')
curl -s -H "authorization: Bearer $T" https://docoga-pass.johnazani.workers.dev/admin/data | head -c 300
```

Rotate the passphrase by `wrangler secret put ADMIN_PASSPHRASE` again: every live
session dies on its own (the token HMAC is derived from `ADMIN_AUTH_SECRET`, so
**do not** rotate that one casually — it invalidates all sessions at once, which
is the right tool if a token ever leaks).

Change the dashboard's door: `site/robots.txt` (`Disallow: /admin`),
`site/_headers` (CSP `frame-ancestors 'none'`, `X-Frame-Options`, `Referrer-Policy`,
`X-Robots-Tag`), and `mobile/capacitor.config.json → server.url` if you move hosts.
The page itself also carries `<meta name="robots" content="noindex,nofollow">`,
because `_headers` covers asset responses only — a Worker-served copy of it would
not inherit them.

---

## 4. Where each number comes from — and what it is worth

| card | source | cost | honesty label on screen |
|---|---|---|---|
| sold today, ₦ today, offline, manual, revoked, waitlist, biz create/paid/revoked | `stat:{field}:{date}` — a **counter incremented at the write point** | 1 KV read | authoritative (append-only, never rebuilt) |
| 31-day charts, all totals | same ledger, read from the rollup | cached | authoritative |
| active passes | `adm:exp:{yyyy-mm-dd}` expiry index count | cached | `activeBasis:"index"` → "estimate from the expiry index" |
| expiring ≤ 14 days | index → **each `code:` record re-read** inside the rollup (cap 60) | 60 KV reads, every 6 h | verified rows only; revoked / renewed / expired / out-of-window rows are dropped here, not displayed |
| stored pass count | `list` scan, cap 400 keys | cached | `scanCapped` when 400 is hit |
| teams, invoices | `biz:*` records + `bizwait:*` | cached | record state, plus the last webhook the Worker actually saw |
| recent activity | `adm:recent` list, cap 40 | cached | event stream, not a ledger |
| last login | `adm:last` | 1 read | — |
| webhook health | `debug:last-webhook{,-ts}` (written by the payment webhook) | 1–2 reads | age, not a promise |
| drift | `codesStored` vs `sold+manual+offline` | — | `suspect` flag; the daily cron is what reconciles the two |

Two rules behind the table:

1. **Counters are never read-modify-written.** A `get`+`put` on `stat:day` would
   lose writes under concurrency and cost 2 ops per sale. `KV.incr` at each value
   path is one op and additive.
2. **The keyspace scan lives in the cron, not in a request.** The Worker's free
   tier is 10 ms CPU and ~1 000 KV reads per invocation; a live scan of the
   `code:` space on the request path is how dashboards get disabled at 3 AM.
   `/admin/data` is ≤ 20 reads and its only write is `adm:snap` when it has to
   build the rollup because none exists yet.

Rollup: `buildAdminSnapshot(env)` → `adm:snap` (TTL 7 days), rebuilt by the
`0 7 * * *` cron, on first admin load, and on `POST /admin/snapshot`
(429 with `retryInSec` while the `adm:lock` is held). A stale snapshot is served
immediately while `ctx.waitUntil(rebuildThrottled(env))` runs — the page never
waits on a scan. The page also polls every 60 s, paused while hidden.

---

## 5. The API

| route | what it does |
|---|---|
| `POST /admin/login` | passphrase → bearer token (401 wrong · 429 locked · 503 unconfigured) |
| `GET /admin/me` | session check + remaining TTL — the page shows a real countdown, not a guess |
| `POST /admin/logout` | deletes this session |
| `GET /admin/data` | everything on Today/Business/Leads/Security in one response |
| `POST /admin/snapshot` | force a rebuild, throttled by design |
| `GET /admin/codes?q=&deep=` | `exact` → `email` → `deep` list scan → `recent`; one mode per call, cheapest first |
| `POST /admin/issue` | mint + email a pass by hand (the only admin write path that creates value) |
| `POST /admin/revoke` / `/admin/extend` / `/admin/resend` | cancel · extend (+365 d, un-revokes from today) · re-send mail (502 `MAIL_NO_PROVIDER` rather than pretend) |
| `GET /admin/sessions` / `POST /admin/session` | list devices · kill one (`{sid}`) or all others (`{all:true}`) |
| `GET /admin/social` | **Social tab (17 Oct 2026).** Today's posting plan vs what GitHub Actions actually did, the last 7 days, and the clock's health — see §5a |
| `POST /admin/social/run` | `{workflow, inputs?}` — "Run now / Retry" a lane this minute; allow-listed to the plan, one ask per lane per 10 min (429 with `retryInSeconds`) |
| `GET /admin/site` | **Website tab.** Visits from Cloudflare Web Analytics: 7 + 28 days, by channel, country and page; cached 30 min |
| `GET /admin/feed` | **Content tab.** The repo's own records — brain plan for 3 days, last 40 posts with links, growth vs milestones, YouTube snapshot + scheduled queue — as pushed into KV by `dashboard_sync.yml`; one KV read, age in seconds |

Every response: `Cache-Control: no-store`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`. Raw webhook bodies are never echoed. Exported CSV
is built in the browser and prefixes `= + - @` with `'` so a spreadsheet cannot be
turned into a formula.

Hand-minting is capped at `ADMIN_ISSUE_CAP = 200/day` (`adm:issue:{date}`) — an
owner with a leaked token should not be able to print inventory forever; the cap
and the current count are both shown on the Sell tab.

### 5a. The Social tab — plan vs reality, honestly

The owner asked for it in one sentence: *"I want to see the social media upload plans
for the day, the ones that were successful, the ones that failed."* Three design rules:

1. **The plan shown is the plan that fires.** The worker reads the clock's own table
   (`GET https://docoga-clock.johnazani.workers.dev/` → `entries_table`, cached 30 min),
   not a copy. Every row is a cron the clock really rings, with the exact dispatch
   inputs. If the lanes' crons change, the clock redeploys and the board follows.
2. **Reality is GitHub's, not ours.** One `GET /actions/runs?created=<Lagos day>` with
   the same fine-grained token the clock holds (`GH_DISPATCH_TOKEN`, forwarded into
   the worker by `deploy-pass-now.yml`). Runs are matched to slots by workflow file
   and nearest start (10 min early to 6 h late — GitHub's own `schedule:` has been
   measured 4 h 32 min late at the median). A failed run's **reason** is the lane's own
   error annotation (`IG_CAUSE=…`, `THREADS_…`), fetched once and cached per run.
   Words on the board: **posted** (a reader-facing lane ran clean) · **done** (housekeeping
   ran) · **failed** (+ reason) · **running** · **upcoming** · **due now** (≤ 20 min past) ·
   **missed** (slot passed, nothing ran). Manual or re-runs that match no slot are listed
   under *Machinery* so nothing that ran is hidden.
3. **Retry is a request, not a bypass.** "Run now" is a `workflow_dispatch` with the
   slot's own inputs; the lane's ledger still refuses a duplicate. One ask per lane per
   10 minutes; every ask lands in the activity feed.

Budget: today's board is cached 45 s in KV; finished days are digested once (by the
first load after midnight or by the 8:00am cron) and kept 14 days as small records, so
the 7-day view is seven KV reads, never seven GitHub pages. Times on the page are
12-hour Lagos (`7:10pm`), per the owner's standing rule.

Fail-closed, legibly: no `GH_DISPATCH_TOKEN` in the worker → `{connected:false, reason}`
and the tab says exactly which deploy fixes it. Never a 500, never an empty table
dressed up as a quiet day.

### 5b. The Website tab

`GET /admin/site` runs the same GraphQL the Monday scorecard uses
(`rumPageloadEventsAdaptiveGroups`, see `tools/site_analytics.py`) with
`CF_ANALYTICS_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` (both forwarded by the deploy). The
site tag is read from the beacon the live page serves and cached a week; Nigeria is
counted by the ISO code (`NG`) Cloudflare really returns. Cached 30 min; a Cloudflare
hiccup shows the last good numbers with a "stale" note rather than a blank.

### 5c. The Content tab — what the brain planned, what went out, how the audience grows

The worker cannot read the repository (the dispatch PAT is Actions-only, by design),
and the records that answer "what did we post, what is planned, are we growing" live
in the repo: `brain/drafts/<date>.json`, the lane ledgers under `logs/`, the Monday
`logs/scorecard.json`, `logs/youtube_stats.json`, `brain/goals.json`. So the repo
pushes to the dashboard, not the other way round:

* `tools/dashboard_feed.py build` folds those files into one compact JSON (≈ 10 KB):
  `plan[3]` (approved pack per day or an honest "no approved pack"), `posted[≤40]`
  (newest first, UTC stamps, absolute links), `growth.rows` (value, previous week,
  milestone target/due/unlocks — `null` means *not measured yet*, never 0),
  `youtube.snapshot` + `youtube.scheduled`, `deepdive_next`, `brain_note`.
* `tools/dashboard_feed.py push` PUTs it to KV key `adm:feed` with the
  `CLOUDFLARE_API_TOKEN` the deploys already use (KV Storage Edit is part of the
  Edit-Workers template). No new secret.
* `.github/workflows/dashboard_sync.yml` runs it after every lane, the brain, the
  scorecard and the YouTube snapshot finish (`workflow_run`, which `[skip ci]`
  ledger commits cannot suppress), and on demand from the Actions tab.
* `GET /admin/feed` returns `{connected, ageSeconds, feed}`. The page shows
  "synced X ago" in the plan header and a warning when the feed is more than 36 hours
  old — a stale feed is a signal, not a quiet day.

Also on the Today tab: **Which channel brings the money** — the weekly
`src:checkout|sale:<ISO week>` counters the site keeps from the `?s=` tag on every
link the lanes post, five weeks, taps → sales → conversion per channel.

---

## 6. Tests — the dashboard is gated, not vibes

```bash
npm test                      # five suites, ~15 min
node tools/tests/adminworkertest.mjs   # 12 groups · ~97 route/semantics assertions
node tools/tests/admindomtest.mjs      # 48 checks · the REAL page in jsdom
python3 tools/qa.py                    # §13 = 34 admin/APK contract checks
```

`admindomtest.mjs` is the one that catches page rot: it renders `site/admin.html`
in jsdom against a stubbed Worker and asserts the login round-trip, the KPI
render, a search → **revoke** click, the CSV blob's contents, a hand-mint POST,
all six tabs, kill-others, and — the test that matters most — that the page
reacts to **server-side** revocation, and shows the 503 disabled state. Two real
bugs were caught by it (a `DATA.snapshot.expiring` mis-path and a glue-text
assertion); write assertions against elements, not `textContent` regexes.

---

## 7. The APK

See `mobile/README.md` for the full story. In one line: it is a signed WebView that
opens `https://docoga.com.ng/admin`, contains no secret and no bundled copy of the
dashboard, so **it never needs reinstalling** — updating the site updates the app.

```bash
gh run list --workflow 'Android APK (DocOga Owner)'      # artifacts: debug + signed release
```

Debug and release are signed by **different keys** — uninstall one before
installing the other. The phone needs internet at launch; offline it shows the
honest `www/error.html` rather than a cached number dressed up as current.

---

## 8. Limits and known gaps (deliberate, ₦0-driven)

* Up to **6 h** stale for index-derived cards (active, expiring, teams). Ledger
  cards are live. The page labels both.
* `expiring` is capped at 60 verified rows; beyond that, trust the count, not the list.
* **No activations counter.** The only available write point fires on every page
  load, which would blow the 1 000 KV writes/day allowance for a number that means
  "somebody opened a link". Say so rather than fake it.
* No refund/chargeback ledger (the payment provider has no ₦0 webhook for it here);
  revoked passes are counted, not reconciled against the provider.
* No per-tool funnel from the server: the Worker sees payments, not which tool
  generated a document. Google Analytics holds that truth; the dashboard links to it.
* One user, one passphrase, no roles. If a second owner ever needs access, the
  design point to revisit is per-session identity in `adm:sess:*` (the record is
  already per-device), not a second shared secret.

---

## 9. If it breaks

| symptom | cause · fix |
|---|---|
| `503 admin_disabled` on login | a secret vanished (a `wrangler deploy` from a config without them) → redo §3 |
| `429` and you know the password is right | fail-lock: `wrangler kv key delete --namespace-id f3a5afebe7d04bb0a6018c0d7d355253 "adm:fail:<your-ip>"` — or wait 30 min |
| every tab empty but login worked | snapshot build threw → `curl -X POST -H "authorization: Bearer $T" .../admin/snapshot` and read the error; the Worker tail will show it |
| numbers 6 h old | cron not firing (Settings → Triggers) — `POST /admin/snapshot` is the manual lever |
| page shows the login card forever | token expired (12 h idle) — sign in again; the page says so in the banner |
| dashboard lies after a product change | **SYNC LAW broken** — see §10 |
| CSV opens with `#REF!` or a formula warning | a new field can hold user text → add it to the CSV escape list |

---

## 10. THE SYNC LAW — keep this true or the dashboard becomes a liability

Verbatim user directive, 23 Sep 2026: the owner dashboard is **part of the
product**, and *every product change that creates, moves or renames value ships
with a matching dashboard update in the same commit.* A silently-wrong dashboard
is worse than no dashboard: decisions get made from it.

The write points to touch, by change type:

| you changed | update here, in the same commit |
|---|---|
| a new paid path or bundle | `STAT_FIELDS` + a `await statBump(env, …)` at the exact point the value moves, `buildAdminSnapshot` totals, the Today card, `tools/qa.py`'s `≥ 7 bumps` floor |
| a price | `PRICE_NGN` is read by the dashboard, not hardcoded — but `adminworkertest.mjs` seeds prices; check it |
| code record shape (`exp`, `source`, `prev/succ`, `amount`, `status`) | the rollup's classification **and** `admindomtest.mjs`'s fixture |
| expiry/renewal semantics | `expIndexAdd` (`adm:exp:{date}`) and the ≤14-day window (`ADMIN_EXP_WINDOW`) |
| email delivery of codes | `adminEmailIndex` (`adm:email:*`) or the Passes tab's email lookup goes blind |
| offline batches | the `OFFLINE_HASHES.has` hook — the ledger counts them, `issueCode` does not |
| business/teams (`bizwait:`, `handleInvoiceWebhook`) | the Business tab's classification + `site/admin.html`'s labels |
| devices / team `status`/`grace`/`rem*` | `buildAdminSnapshot`'s team block (it is what the grace column reads) |
| any key naming | `ADMIN_*` caps and the `no-store` cache rules that reference them |
| a new secret | as a **platform secret** only; documented in `worker/index.js`'s header, `worker/wrangler.toml` and `tools/deploy.sh` — never in dashboard or function source |

The law is enforced by `tools/qa.py` §13 (hooks present, value paths present,
routes present, ids resolve, no secret in the page, mobile host parity, version
floor, both admin suites green). **It is a floor, not a substitute for judgment:**
qa can prove a bump exists, not that it means what the card claims.
