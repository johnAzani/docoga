# DocOga Owner — the Android app

`mobile/` is a **Capacitor 8 shell**: a signed Android package whose only job is to
open `https://docoga.com.ng/admin` full-screen, with a navy splash, a real launcher
icon, no browser chrome, and no address bar. It is not a second copy of the
dashboard.

```
your phone  ──▶  DocOga Owner.apk  ──▶  WebView  ──▶  https://docoga.com.ng/admin
                                                │                    │
                                                │                    └─ Cloudflare Pages (this repo, site/)
                                                └── fetch() ──▶ https://docoga-pass.johnazani.workers.dev/admin/* (Worker)
```

## Why the APK loads a URL instead of bundling the page

| | bundled assets | remote URL (this design) |
|---|---|---|
| a dashboard bug fix reaches the phone | rebuild + reinstall | next pull-to-refresh |
| an APK floating around | frozen copy of the UI and its data shape | an empty shell forever |
| what a lost phone leaks | the app itself (still no secrets) | nothing new |
| review/rollback | APK per version | one page, one deploy |

The shell holds **no passphrase, no token, no key, no customer data**. The session
is a bearer token in the WebView's own `localStorage`, minted by the Worker after
the passphrase is checked, revocable server-side in one call. So the app never
needs reinstalling to change how the dashboard behaves, and an APK in the wrong
hands is a browser pointing at a login screen.

This is the same reason `site/admin.html` is public and inert.

## Layout

| path | what it is |
|---|---|
| `capacitor.config.json` | the whole product decision: `server.url` → `/admin`, `cleartext: false`, navy background, `errorPath` |
| `www/error.html` | the only screen the app owns: shown when the Worker/site is unreachable or offline |
| `www/index.html` | a placeholder. Never loaded while `server.url` is set |
| `android/` | the real Gradle project — committed, and edited by hand where it matters (below) |
| `tools/make-icons.mjs` | regenerates every launcher icon + splash frame from `brand/official-logo-transparent.png` |
| `package.json` | pins `@capacitor/core`, `@capacitor/android`, `@capacitor/cli` at **8.5.3** |

### Hand-edited parts of `android/` (do not lose them in a re-scaffold)

* **`app/build.gradle`** — release signing reads `-PdocogaKeystoreFile` /
  `…Password` / `…Alias` / `…AliasPassword`. With no properties it produces an
  **unsigned** release (Android will refuse to install it). That failure is the
  point: the release key is never in git. Also reads `-PdocogaVersionCode` /
  `-PdocogaVersionName`.
* **`app/src/main/AndroidManifest.xml`** — `allowBackup="false"` +
  `dataExtractionRules` (the session token must not ride along in a cloud backup
  or a device transfer), `usesCleartextTraffic="false"`, `adjustResize` (so the
  keyboard cannot bury the passphrase field), `enableOnBackInvokedCallback`, and
  **INTERNET as the only permission**.
* **`MainActivity.java`** — the back gesture. At `targetSdk 36` `onBackPressed`
  is no longer delivered, so the gesture is claimed through
  `OnBackInvokedDispatcher` (API 33+) with a legacy path below it; both delegate
  to the WebView and then background the task. Capacitor itself implements
  neither, which is why this file exists.
* **`res/values/styles.xml` + `colors.xml` + all `mipmap-*`/`drawable-*` art** —
  navy `#0B1B3F` splash and glyph-only launcher icons, so the cold start is one
  colour instead of a white flash and Capacitor's rocket.

> Never replace Capacitor's `WebViewClient`. The interceptor that guards
> `/_capacitor_http_interceptor_/` is the fix for **CVE-2026-103922** (the
> navigation guard trusted host+scheme but not path). `qa.py` fails the build if
> `@capacitor/*` drops below 8.5.1, and this project pins 8.5.3.

## Build it — the normal way (CI, ₦0)

`.github/workflows/android-apk.yml` runs on every push to `main` that touches
`site/admin.html`, `worker/index.js`, `mobile/**` or the workflow itself. It
uploads two artifacts:

* `docoga-owner-debug.apk` — debug-signed, install immediately, for testing.
* `docoga-owner-release.apk` — signed with *your* keystore, the one to keep.

No `android-actions/setup-android` step: the `ubuntu-24.04` runner already ships
SDK platform 36 and build-tools 36.0.0, which is what Capacitor 8 needs.

A cold run is ~3 minutes; the release step is skipped, not failed, while no
keystore is configured. Proven green on PR #19 (run 38293473770, 2m47s,
`docoga-owner-debug-apk`).

When a build breaks, the diagnosis is in two places a browser is not needed
for: the job's annotations (the first lines Gradle printed that contained
`error:` / `What went wrong`) and the `gradle-build-log` artifact, which the
workflow uploads only on failure:

```bash
gh run list --workflow 'Android APK (DocOga Owner)'
gh api repos/johnAzani/docoga/check-runs/<job-id>/annotations --jq '.[].message'
gh run download <run-id> --name gradle-build-log
```

## Sign it — one time, ten minutes

```bash
keytool -genkeypair -v -keystore docoga-owner.jks -alias docoga-owner \
  -keyalg RSA -keysize 2048 -validity 10000

gh secret set DOCOGA_APK_KEYSTORE_B64 < <(base64 -w0 docoga-owner.jks)
gh secret set DOCOGA_APK_KEYSTORE_PASSWORD --body '<store pass>'
gh secret set DOCOGA_APK_KEY_ALIAS --body 'docoga-owner'
gh secret set DOCOGA_APK_KEY_PASSWORD --body '<key pass>'

rm docoga-owner.jks    # or better: keep it on a drive you would not lose
```

Missing any of those is fine and expected: CI still produces the debug APK and
marks the release step skipped. **Lose the keystore and you cannot push an update
to an installed app** — you would ship a new package beside it. It is a ₦0
sideload app, so that is a re-download, not a disaster — but keep the file.

## Build it locally (only if you want to hack on the shell)

Needs Node ≥ 22, JDK 21, Android SDK 36 + build-tools 36.0.0 (`ANDROID_HOME`).

```bash
cd mobile
npm ci --ignore-scripts          # --ignore-scripts: sharp/png postinstall cannot reach its CDN here
npx cap sync android
cd android && ./gradlew assembleDebug        # → app/build/outputs/apk/debug/
# release, with the keystore OUTSIDE the repo:
./gradlew assembleRelease \
  -PdocogaKeystoreFile=/secure/path/docoga-owner.jks \
  -PdocogaKeystorePassword=… -PdocogaKeystoreAlias=docoga-owner -PdocogaKeystoreAliasPassword=…
```

`npm install` without `--ignore-scripts` is a known dead end in a locked-down
sandbox: `@capacitor/assets` pulls `sharp`, whose postinstall downloads libvips
from a GitHub release and dies on TLS. Icons are committed instead — regenerate
them with `node tools/make-icons.mjs` (needs `pngjs` only) after any logo change.

## Install on the phone

1. Download the `.apk` from the Actions run (signed in with GitHub).
2. Copy it to the phone, tap it, allow "install unknown apps" for that one app.
3. Open **DocOga Owner** → passphrase → you are in. Nothing to configure.

The phone needs internet at every launch (the page is *fetched*). Offline the app
shows the honest `error.html` — no stale revenue dressed up as current.

## Pointing the app somewhere else

`capacitor.config.json → server.url` is the only switch. It must be
`https://docoga.com.ng/admin`: the Pages host, **not**
`https://docoga-pass.johnazani.workers.dev/admin` — the Worker serves the API and
has no HTML route, so that URL is a 404. `qa.py` §13 asserts the host of
`server.url` matches `WORKER_URL`'s site and that no `http://` appears in the
mobile config.

## What is deliberately *not* here

* **No push notifications.** A ₦0 push channel for one user does not exist that
  does not need a token in this app or on the Worker; the dashboard's 60-second
  poll is the notification, and `stat:*` counters do the rest.
* **No F-Droid / Play listing.** Sideload is the install path; a Play listing would
  force a bundle id, a review process and a signing key managed by Google.
* **No iOS target.** `cap add ios` needs a Mac and an Apple account (₦11k/yr);
  the phone's Safari "Add to Home Screen" on `/admin` already gives the same
  full-screen experience for free.
