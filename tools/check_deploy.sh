#!/bin/bash
# ============================================================================
# DocOga — is production actually wired to Git?
#
# Usage:  tools/check_deploy.sh [commit-sha]     (default: latest commit on main)
#
# WHY THIS EXISTS (3 Oct 2026): the Cloudflare Pages project existed and
# docoga.com.ng pointed at Cloudflare, but the project had been hand-uploaded
# instead of Git-connected. Every push to GitHub succeeded and nothing reached
# production, while Netlify — retired — kept building the repo. Nothing in the
# repo or on the site reveals that. A commit status does.
#
# A Git-connected Pages project posts a `cloudflare/pages` status on every
# branch commit, preview builds included. So one API call answers the question.
#
# Needs: gh, authenticated (gh auth status). No Cloudflare credentials.
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

REPO="johnAzani/docoga"
SHA="${1:-}"

if [ -z "$SHA" ]; then
  SHA=$(git ls-remote origin refs/heads/main 2>/dev/null | cut -f1)
  [ -n "$SHA" ] || SHA=$(git rev-parse HEAD)
  echo "checking main tip: ${SHA:0:7}"
else
  echo "checking ${SHA:0:7}"
fi
echo

if ! command -v gh >/dev/null 2>&1; then
  echo "❌ gh (GitHub CLI) not installed — cannot query commit statuses"
  exit 2
fi

STATUSES=$(gh api "repos/$REPO/commits/$SHA/status" --jq '[.statuses[].context] | join(" ")' 2>/dev/null)
APPS=$(gh api "repos/$REPO/commits/$SHA/check-runs" --jq '[.check_runs[].app.slug] | unique | join(" ")' 2>/dev/null)

echo "  status contexts : ${STATUSES:-<none>}"
echo "  check-run apps  : ${APPS:-<none>}"
echo

VERDICT=0

if echo "$STATUSES" | grep -q "cloudflare"; then
  echo "✅ CLOUDFLARE PAGES IS CONNECTED — it reported a build on this commit."
  TARGET=$(gh api "repos/$REPO/commits/$SHA/status" \
    --jq '[.statuses[] | select(.context|test("cloudflare")) | .target_url] | .[0]')
  STATE=$(gh api "repos/$REPO/commits/$SHA/status" \
    --jq '[.statuses[] | select(.context|test("cloudflare")) | .state] | .[0]')
  echo "   ${STATE} → ${TARGET}"
  [ "$STATE" = "success" ] || { echo "   ⚠️  but the build state is '${STATE}', not success — open the URL above"; VERDICT=1; }
else
  echo "❌ NO CLOUDFLARE BUILD ON THIS COMMIT — the Pages project is not"
  echo "   Git-connected (or the GitHub App was not granted this repo)."
  echo "   A Direct Upload project cannot be converted; create a new one via"
  echo "   Workers & Pages → Create → Pages → Connect to Git. See GITHUB-CLOUDFLARE.md."
  VERDICT=1
fi

if echo "$STATUSES $APPS" | grep -q "netlify"; then
  echo
  echo "⚠️  NETLIFY IS STILL BUILDING THIS REPO. It was retired 3 Oct 2026."
  echo "   Disconnect it: Netlify site settings → delete site, then GitHub repo"
  echo "   Settings → GitHub Apps → remove Netlify's access to $REPO."
  VERDICT=1
fi

echo
[ "$VERDICT" = 0 ] && echo "🟢 DEPLOY WIRING OK" || echo "🔴 DEPLOY WIRING NEEDS WORK (see above)"
exit $VERDICT
