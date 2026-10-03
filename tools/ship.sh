#!/bin/bash
# ============================================================================
# DocOga SHIP PIPELINE — the ONLY safe way to ship changes to production.
#
# Usage:   GITHUB_TOKEN=github_pat_xxxxx tools/ship.sh "commit message"
#
# It runs, in order, and STOPS on any failure:
#   1. QA gate        (tools/qa.py — full pre-push checks on all local files)
#   2. Commit         (all changes, with the message you give)
#   3. Push           (token used, then stripped from the remote URL)
#   4. Deploy wait    (polls the live site until Cloudflare Pages serves the new build)
#   5. LIVE verify    (tools/verify_live.py — parses the REAL live JavaScript)
#
# If step 5 fails, the ship FAILED even if the push succeeded — fix forward.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

MSG="${1:?Usage: GITHUB_TOKEN=github_pat_xxx tools/ship.sh \"commit message\"}"
[ -n "${GITHUB_TOKEN:-}" ] || { echo "❌ GITHUB_TOKEN env var not set"; exit 1; }

echo "═══ 1/5 PRE-PUSH QA GATE ═══"
python3 tools/qa.py

echo ""
echo "═══ 2/5 COMMIT ═══"
git config user.name "DocOga"
git config user.email "docoga@users.noreply.github.com"
git add -A
if git diff --cached --quiet; then
  echo "(nothing new to commit — continuing with existing commits)"
else
  git commit -m "$MSG"
  echo "committed: $(git rev-parse --short HEAD)"
fi

echo ""
echo "═══ 3/5 PUSH ═══"
PRE_HASH=$(curl -s --max-time 20 https://docoga.com.ng | sha256sum | cut -c1-12)
git remote remove origin 2>/dev/null || true
git remote add origin "https://${GITHUB_TOKEN}@github.com/johnAzani/docoga.git"
git push origin main
git remote set-url origin https://github.com/johnAzani/docoga.git
echo "remote reset to clean URL ✅"

echo ""
echo "═══ 4/5 WAIT FOR CLOUDFLARE PAGES DEPLOY ═══"
SITE_CHANGED=$(git diff --name-only HEAD@{1} HEAD 2>/dev/null | grep -c "^site/" || true)
if [ "${SITE_CHANGED:-0}" = "0" ] && git diff --cached --quiet 2>/dev/null; then
  echo "(no site/ files changed — skipping deploy wait)"
else
  for i in $(seq 1 12); do
    sleep 15
    NEW_HASH=$(curl -s --max-time 20 https://docoga.com.ng | sha256sum | cut -c1-12)
    if [ "$NEW_HASH" != "$PRE_HASH" ]; then
      echo "✅ new build is LIVE (changed after $((i*15))s)"
      break
    fi
    [ "$i" = "12" ] && echo "⚠️  live content unchanged after 3 min (deploy may be slow or cache) — verifying anyway"
  done
fi

echo ""
echo "═══ 5/5 LIVE VERIFICATION ═══"
python3 tools/verify_live.py

echo ""
echo "🚢 SHIPPED AND VERIFIED. Production is healthy."
