# DocOga — owner click-by-click guide

Researched 9 Oct 2026 against the official documentation linked below and the
repository at `fca8025`. This guide does not claim access to or verification of
Brevo, Cloudflare, Flutterwave, or GA account settings.

## Rules before clicking

- No new payment, repurchase, test purchase, or blind resend.
- Do not send secret values, recipient addresses, pass codes, transaction
  identifiers, or success-page URLs in chat/screenshots. Report statuses only.
- Do not change the public pass link or ₦2,000 price.
- Do not click GitHub **Re-run jobs**, **Run workflow**, or Cloudflare **Deploy**
  during the inspection steps below.
- `RESEND_EMAIL_ENABLED` stays unset/false until the intentional gated release.
- Cloudflare DNS changes take effect when saved. Add only Brevo-generated records,
  preserve existing services, and stop on any conflict.

## 1. GitHub — best-effort cleanup of the exposed log

Direct run link: https://github.com/johnAzani/docoga/actions/runs/37890401771

1. Open the direct link while signed in as the repository owner.
2. Check the run number in the URL is **37890401771** and the workflow is
   **Deploy docoga-pass (gated)**. Do not open/copy the exposed log content.
3. In the upper-right of the run summary, click **⋯**.
4. Click **Delete all logs**.
5. Read and confirm the deletion prompt.
6. GitHub says the **Delete all logs** option disappears after deletion.

If the run is already gone, or the option is missing, do not assume why: report
“already unavailable” or “deletion option unavailable.” If permission is denied,
report that you attempted cleanup and the result. This gate requires a best-effort
attempt; it does not require pretending deletion succeeded. Do not download the
log archive or rerun this old commit. Deletion does not revoke credentials or
remove copies someone may already have made. The owner-reported credential
rotation still needs confirmation.

Official steps: https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs#deleting-logs

## 2. Cloudflare — inspect production Worker secret names (read-only)

Dashboard: https://dash.cloudflare.com/

1. Select the account containing DocOga.
2. Open **Workers & Pages** (use dashboard navigation/search if the category has
   moved).
3. Select **docoga-pass** — NOT **docoga-git** (which serves the site).
4. Open **Settings**.
5. Find **Variables and Secrets**.
6. Inspect the names and binding types. Payment credentials must be **Secret**,
   not unencrypted Text/JSON variables.

Expected configuration:

| Name | Required for |
| --- | --- |
| `FLW_SECRET_KEY` | Flutterwave v3 verification; use a current LIVE secret key, not a public/encryption/test key |
| OR `FLW_CLIENT_ID` + `FLW_CLIENT_SECRET` | Flutterwave v4 verification; do not introduce a second credential path just for this check |
| `FLW_WEBHOOK_HASH` | Validate live Flutterwave webhook signatures |
| `BREVO_API_KEY` | Brevo API mail delivery; not an SMTP password |
| `ISSUE_SECRET` | Authenticated `/issue` bridge; if that bridge is used, its configured value must match |

Also inspect non-secret configuration: `PROVIDER=flw`,
`SITE_URL=https://docoga.com.ng`, and `MAIL_FROM` if present.
The repository's default sender when `MAIL_FROM` is absent is
`DocOga <noreply@docoga.com.ng>`. A configured `MAIL_FROM` may be a bare sender
address or `DocOga <the verified sender address>`; the Worker parses both.

**Presence is not proof of correctness.** Cloudflare hides saved Secret values.
If you already rotated and saved them, confirm from your own completed setup
that they are the current credentials. Do not overwrite them needlessly.
Do not replace `ISSUE_SECRET` with an arbitrary new value: that can break its
bridge until the other end is updated.

If any required value is missing/uncertain, stop and report its NAME only.
Remediation must be coordinated: Cloudflare's documented path is **Add → Type:
Secret → Variable name → Value → Deploy**, and **Deploy applies production
changes**. It is not a read-only confirmation button. Do not click it casually
or use it to publish local app changes outside the agreed release.

Official docs: https://developers.cloudflare.com/workers/configuration/secrets/

## 3. Flutterwave — confirm the LIVE webhook configuration

Official direct live-settings link:
https://app.flutterwave.com/dashboard/settings/webhooks/live

1. Open that link and sign in. Select the correct business account if prompted.
2. Confirm you are viewing **Live**, not **Test**, settings.
3. Manual navigation if needed: **Settings → Developers → Webhooks**.
4. Inspect the webhook URL:
   `https://docoga-pass.johnazani.workers.dev/flw-webhook`
5. Inspect the **Secret hash** field privately.
6. Confirm that this is the same current value you saved as the production
   Worker's `FLW_WEBHOOK_HASH` during rotation.

Flutterwave permits separate live/test hashes. This is a webhook shared secret,
not an API key, public key, or encryption key. Cloudflare cannot show you its
saved Secret value, so do not claim an on-screen comparison if it is hidden.
If uncertain, report uncertainty; we will coordinate a matched update on both
sides rather than change one side alone. Do not click a webhook replay/retry or
make a payment to test this inspection.

Official source: https://flutterwave.com/eg/support/integrations/what-is-a-secret-hash

## 4. Brevo — obtain the account-specific DNS records

Direct page: https://app.brevo.com/senders/domain/list

1. Sign in. Alternatively use the account dropdown → **Settings → Senders,
   Domains, IPs → Domains**.
2. If `docoga.com.ng` exists, click **Authenticate** beside it. Do not create a
   duplicate. If absent: **Add a domain → docoga.com.ng → Add domain/Continue**.
   Enter the domain only—no `https://`, `www`, path, or sender address.
3. In the classic interface, choose **Authenticate the domain yourself**, then
   **Continue**.
4. In the newer interface, use **Individual DNS records → Manual → Continue**
   when those choices appear. For a root domain, Individual DNS records may be
   selected automatically. On shared IPs, branded-subdomain setup is optional;
   it is not needed for this sender-authentication repair. Do not buy a dedicated
   IP, delegate root DNS, change nameservers, or introduce optional branding.
5. Leave the DNS-records page open. Use its **Copy** buttons, not values from an
   article, this guide, or another account.

Classic authentication commonly gives:
- Brevo code: TXT.
- DKIM: two CNAMEs OR one TXT. Use the type your account actually displays.
- DMARC: TXT, subject to preserving an existing record (step 5).

The newer flow can show more records depending on selected optional features.
If it requests additional service changes or conflicts with an existing setup,
stop rather than guess. We have not verified which interface your account has.

Official classic flow:
https://help.brevo.com/hc/en-us/articles/12163873383186
Official new flow:
https://help.brevo.com/hc/en-us/articles/35337929909778

## 5. Cloudflare — add only the required DNS records

Use a second tab: https://dash.cloudflare.com/

1. Select **docoga.com.ng** from the domains list.
2. Left menu: **DNS → Records**.
3. Before adding anything, inspect the existing record names. Do not delete or
   modify website `A`/`AAAA` records, MX, SPF, nameservers, unrelated DKIM selectors,
   or Worker custom domains. Save a private DNS export if you want a backup.
4. Search for `_dmarc`. Count only TXT records at `_dmarc.docoga.com.ng` whose
   content starts `v=DMARC1`. Apply the DMARC rules below.

### A. Brevo code (TXT)

Click **Add record**:

| Cloudflare field | What to enter |
| --- | --- |
| Type | `TXT` |
| Name | Copy the Brevo code's Name/Hostname from Brevo |
| Content | Copy the Brevo code's Content/Value from Brevo |
| TTL | Leave default/Auto unless Brevo explicitly requires otherwise |

Click **Save**. If the exact record already exists with matching content, leave
it rather than duplicating it. Only use `@` if Brevo identifies the record as
apex/root. After saving, ensure the displayed hostname has not acquired the
`docoga.com.ng` suffix twice.

### B. DKIM if Brevo displays two CNAME records

For **DKIM 1**, click **Add record**:
- **Type:** CNAME.
- **Name:** Copy DKIM 1 Name from Brevo.
- **Target:** Copy DKIM 1 Content/Value from Brevo (a hostname, not a URL).
- **Proxy status:** Click the orange cloud/toggle until it says **DNS only**
  (grey cloud).
- **Flatten:** If a per-record control appears, leave it OFF.
- **TTL:** Default/Auto; click **Save**.

Repeat separately for **DKIM 2** using DKIM 2's own Name and Target.

Then check **DNS → Settings**. If **CNAME flattening for all CNAME records** exists,
it must be OFF for these verification CNAMEs to be returned. All-CNAME and
per-record flattening controls are paid-zone options. On Free, they may be absent;
absence is not a fault and is not a reason to upgrade. Default apex flattening
is separate: do not alter your website configuration trying to disable it.
If changing a zone-wide setting might affect another service, stop for review.

Technical correction: Cloudflare flattening returns final IP addresses instead of
the CNAME. It does not convert the record into TXT. The CNAME itself disappearing
from the answer is why third-party verification can fail.

### C. DKIM if Brevo displays one TXT record

Click **Add record → Type: TXT**. Copy its **Name** and **Content** from Brevo,
leave TTL default, then **Save**. There is no proxy toggle for TXT. Do not convert
this record into CNAME or add imaginary DKIM 1/2 selectors.

If the selector is already used by another mail provider with different content,
stop. Do not replace that provider's DKIM key. Ask Brevo support about a conflict.

### D. DMARC — preserve the current policy

- **No existing DMARC:** Add the exact TXT Name/Content Brevo generated.
- **One existing valid DMARC:** Keep it; do not add a second and do not weaken
  `p=reject`/`p=quarantine` to `p=none` just to copy an example.
- **Brevo reports missing `rua`:** Review its account-generated reporting tag.
  If adding one is needed, use **Edit** on the existing TXT record and preserve
  all existing policy/alignment tags. Do not replace an existing `rua`, add a
  second `rua` tag, or create a second record. Reporting destinations receive
  aggregate email metadata; choose deliberately. Do not use a generic value from
  this guide in place of the account's instructions.
- **More than one or malformed/conflicting DMARC:** Stop. Do not guess which to
  delete; resolve the policy conflict before saving.

Do not change SPF/MX for basic authentication. Brevo's classic FAQ says those
records are not required (it supplies them for dedicated-IP setup). If your
account-specific flow requires something different, stop and review first.

Official Cloudflare sources:
https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/
https://developers.cloudflare.com/dns/manage-dns-records/troubleshooting/cname-domain-verification/
https://developers.cloudflare.com/dns/cname-flattening/set-up-cname-flattening/
https://developers.cloudflare.com/dns/cname-flattening/

## 6. Brevo — authenticate and register the actual sender

1. Return to the open Brevo records tab.
2. Click **Authenticate this email domain** (classic) or **Authenticate domain**
   (new flow), at the bottom.
3. Required result: `docoga.com.ng` → **Authenticated**. “DNS records saved” is
   not the same result.
4. If not authenticated yet, retry the authentication check later; Brevo allows
   up to 48 hours for propagation. Do not repeatedly alter correct records.
5. If still failing after 48 hours, use Brevo's record-level errors/troubleshooting
   and support; do not send a pass to test it.
6. Open https://app.brevo.com/senders or navigate **Settings → Senders, Domains,
   IPs → Senders**.
7. Find the address in the Worker's actual `MAIL_FROM`, or the repository default
   if absent. Domain authentication alone is not proof the Worker is configured
   to send as the address you intend.
8. If missing: **Add a sender → From name: DocOga → From email: the actual sender
   address → Save**. Brevo says senders on an authenticated domain are
   automatically verified.
9. Check sender verification and DKIM/DMARC status. If a six-digit verification
   prompt appears, stop to confirm you used the authenticated domain; do not send
   verification to an unmonitored default address or paste its code in chat.

Do not use Brevo's log **Resend** button or send a test pass. Authentication is not
an inbox-delivery guarantee; keep the DNS records once verified.

Official sender docs: https://help.brevo.com/hc/en-us/articles/208836149
Troubleshooting: https://help.brevo.com/hc/en-us/articles/16045394674066

## 7. Private recipient check and STOP for gate confirmation

Before a deliberate resend, compare the earlier event recipient privately with
the checkout email for the existing qualifying purchase:
- Flutterwave **Transactions**: open the existing purchase, not a new payment.
- Brevo **Transactional → Logs → eye icon → Details**: inspect that message's
  recipient privately. Never click the log's Resend control.

If they differ, stop. The resend endpoint uses the stored active-pass email, not
an email typed into the request; sender repair cannot correct a wrong recipient.
The logged recipient has not yet been independently compared with checkout.

Send ONLY these statuses:
- Log cleanup: deleted / already unavailable / attempted but blocked.
- Production secret names/types: present and current / missing or uncertain NAME.
- LIVE webhook URL/hash: matched from completed setup / uncertain.
- Brevo domain: Authenticated / not authenticated / exact non-sensitive error.
- Actual sender: verified/compliant / warning present.
- Checkout/event recipient: matches / differs / not yet compared.
- Resend flag: still unset/false.

STOP HERE. No release marker, workflow rerun, Worker Deploy, or pass resend until
these gates are explicitly confirmed. Account/DNS status remains owner-reported.

## 8. Intentional release and one existing-pass resend — LATER ONLY

The agent owns app-side code/test/release work:
1. Use the hardened marker-gated Worker workflow with `[deploy-pass]`.
2. Verify its actual deploy exit/result, not merely a green run summary. The
   current Worker workflow logs `deploy_exit` but does not propagate a nonzero
   deploy exit as a failed step; the manual `dry_run` input also does not prevent
   its deployment step. Those contracts need repair/test before release.
3. Only after Worker success, use `[deploy-site]` for the site and verify it.
4. Enable the flag only as part of that intentional release. Dashboard path if
   agreed: **Workers & Pages → docoga-pass → Settings → Variables and Secrets →
   Add/Edit → Type: Text → Name: RESEND_EMAIL_ENABLED → Value: true → Deploy**.
   This is a live configuration deployment, not a read-only action.
5. After both releases, use the saved success-page URL for the EXISTING purchase
   privately and click **Email didn’t arrive? Resend pass email** ONCE.
   Do not invent identifiers or reconstruct a URL using an uncertain transaction.
   Reopening the page calls `/verify`, which can issue a pass/email for an unknown
   but verified purchase, so it is not a harmless inspection before the gates.
6. The endpoint's acceptance message is provider handoff, not inbox proof.
   Its KV-based throttle is designed for 60s spacing/three attempts per UTC day;
   this is not an atomic global guarantee against simultaneous requests. Stop
   after one attempt whether it succeeds or fails; do not exhaust the quota.
7. Inspect the NEW Brevo message: **Transactional → Logs → eye icon → History**.
   Correlate its timestamp with the deliberate attempt, not the old failed event.
   Report statuses/error category only. `Delivered` means recipient-server
   acceptance, not guaranteed inbox placement. Confirm actual receipt privately.
   `Error` has multiple possible causes; read its reason, do not assume all errors
   are sender authentication. `Blocked` is Brevo blocklisting, not necessarily a
   recipient-server rejection. No blind retry.

Official report docs: https://help.brevo.com/hc/en-us/articles/208858829
Official delivered-status explanation:
https://help.brevo.com/hc/en-us/articles/35699922048146

## Parallel: GA baseline (read-only, not a payment-conversion proof)

Sign in at https://analytics.google.com/ and choose the DocOga property using the
web stream's measurement ID `G-GO8VZB3R28` to verify identity. Set a completed date
range, e.g. 1 Sep–8 Oct 2026; today's totals are partial.

- **Reports → Acquisition → Traffic acquisition**: sessions and channels.
- **Reports → Engagement → Landing page**: top entry pages by sessions (NOT the
  Pages and screens report, which measures viewed pages).
- **Reports → Engagement → Pages and screens**: content views/active users.
- If a report is absent, navigation may use another collection; use search or
  ask an Editor to restore it, not an upgrade.

Repository inspection found the homepage GA configuration but NO GA tag/purchase
confirmation event in `site/success.html`. A success-page URL view would not prove
verified payment even if tagged. Do not fabricate a page_view → outbound click →
success-page conversion funnel or divide success views by sessions and call it
free-to-paid conversion. Outbound click collection depends on Enhanced Measurement
settings, which this session has not verified. Proper privacy-safe verified-
payment measurement is an app-side follow-up, not an owner click that can create
historical data. Do not share reports exposing query strings containing pass codes
or references.

Official Landing page report: https://support.google.com/analytics/answer/12931766
