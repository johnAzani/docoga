#!/usr/bin/env bash
# DocOga deploy kit — 11 Oct 2026 (Phase 0 card + production-worker port
# + Phase 1 team core + Phase 2 money path: configurator, team creation,
# Flutterwave VA/card charges, webhook activation)
#
# OWNER runs this from a machine with Cloudflare auth (wrangler login).
# The Arena sandbox has no Cloudflare egress and no CF credentials, so the
# publish step cannot execute there — everything else (build, tests, QA) is
# done and green on this branch before this script is ever needed.
#
# Known quirk (10 Oct): the first `wrangler deploy` attempt can hit a
# token-validation error — just retry; the retry publishes.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1/2 · payment worker (docoga-pass) — strict forward superset of the live worker =="
echo "     adds: POST /business/waitlist (Phase 0) + /business/login, /business/team* (Phase 1)"
(cd worker && npx wrangler deploy)

echo "== 2/2 · site (docoga-git) — Business card live, team sign-in, branded rendering =="
npx wrangler deploy   # root wrangler.jsonc publishes ./site (never change assets.directory)

echo ""
echo "== VERIFY the new worker is live (owner, any shell) =="
echo "  curl -s -o /dev/null -w '%{http_code}\n' -X POST https://docoga-pass.johnazani.workers.dev/resend-email \\"
echo "    -H 'content-type: application/json' -d '{\"ids\":[]}'"
echo "    → expect 503  (the OLD worker returned 404 here — 503 proves the new one is live)"
echo "  curl -s -X POST https://docoga-pass.johnazani.workers.dev/business/waitlist \\"
echo "    -H 'content-type: application/json' -d '{\"email\":\"bad\"}'"
echo "    → expect 400 {\"ok\":false,\"error\":\"valid email required\"}  (no KV write, no email)"
echo "  curl -s 'https://docoga-pass.johnazani.workers.dev/activate?code=NOTACODE' | head -c 80"
echo "    → expect 404 code_not_found  (activation regression intact)"
echo "  curl -s https://docoga.com.ng | grep -c 'biz-waitlist'"
echo "    → expect ≥1  (new Business card + form live)"
echo "  curl -s -X POST https://docoga-pass.johnazani.workers.dev/business/teams \\"
echo "    -H 'content-type: application/json' -d '{\"name\":\"x\"}'"
echo "    → expect 400 {\"ok\":false,\"error\":\"valid email required\"}  (Phase 2 team-creation route live; no record created)"
echo "  curl -s -X POST https://docoga-pass.johnazani.workers.dev/business/team/renew"
echo "    → expect 401 {\"ok\":false,\"error\":\"sign_in_required\"}  (Phase 4 renewal route live; unauthed, nothing created)"
echo ""
echo "== WORKER SECRET SETUP (ONE-TIME, do BEFORE the first deploy after 11 Oct — the live 10-Oct worker only has the retail-pass variables) =="
echo "  Cloudflare dashboard → Workers → docoga-pass → Settings → Variables:"
echo "  1. TEAM_AUTH_SECRET (secret) = any long random string"
echo "     → required for /business/login* + /business/team*; without it they fail closed 503"
echo "  2. FLW_SECRET_KEY (secret) = Flutterwave dashboard → Settings → API keys → SECRET KEY"
echo "     → required for ALL Business payments (creates the VA / card charge, and verifies the card redirect)"
echo "  3. FLW_WEBHOOK_HASH (secret) = Flutterwave dashboard → Webhooks → hash for the endpoint posted to the worker's /flw-webhook"
echo "     → BANK TRANSFER (VA) confirmation arrives only by signed webhook: without this the team"
echo "       stays 'waiting for payment' after the customer transfers. Card payments work without it"
echo "       (redirect + API verify), bank transfer does NOT."
echo "  Email: nothing to set — Business mail reuses the already-verified sender (MAIL_FROM)."
echo "  business@ itself is a mailbox-side setup (docs/support/AUTO_REPLY.md), see the runbook step 3."
echo ""
