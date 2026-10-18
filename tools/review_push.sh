#!/usr/bin/env bash
# review_push.sh — put small review files (a contact sheet, a cover, a text report) on the
# `review` branch, where anyone with repository read access can look at them through the
# contents API, even from a sandbox that cannot download run artifacts or logs.
#
#   REVIEW_LABEL=2026-10-19_tiktok-test_123 bash tools/review_push.sh sheet.jpg cover.jpg report.txt
#
# Files land under <REVIEW_LABEL>/ on `review` (created orphan if absent). Folders whose names
# start with a date older than KEEP_DAYS (14) are pruned, so the branch stays a few MB. Never
# fails the caller: a push that cannot happen is a warning, the lane's work is already done.
# Runs inside an actions/checkout clone (its credentials are reused through a worktree).
set -uo pipefail

LABEL="${REVIEW_LABEL:-$(date -u +%F)_review_${GITHUB_RUN_ID:-local}}"
KEEP_DAYS="${KEEP_DAYS:-14}"
BRANCH="review"
[ "$#" -gt 0 ] || { echo "review_push: nothing to push"; exit 0; }

git config user.name  >/dev/null 2>&1 || git config user.name  "github-actions[bot]"
git config user.email >/dev/null 2>&1 || git config user.email "github-actions[bot]@users.noreply.github.com"

tmp="$(mktemp -d)"
cleanup() { git worktree remove --force "$tmp" >/dev/null 2>&1 || rm -rf "$tmp"; }
trap cleanup EXIT

if git fetch -q origin "$BRANCH" 2>/dev/null; then
  git worktree add -q --detach "$tmp" "origin/$BRANCH" || { echo "::warning title=Review not pushed::could not open the $BRANCH branch"; exit 0; }
  ( cd "$tmp" && git checkout -q -B "$BRANCH" )
else
  git worktree add -q --detach "$tmp" HEAD || { echo "::warning title=Review not pushed::could not create a worktree"; exit 0; }
  ( cd "$tmp" && git checkout -q --orphan "$BRANCH" && git rm -rfq --cached . && find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + )
fi

mkdir -p "$tmp/$LABEL"
for f in "$@"; do
  [ -f "$f" ] && cp -f "$f" "$tmp/$LABEL/"
done
cutoff="$(date -u -d "-${KEEP_DAYS} days" +%F 2>/dev/null || date -u +%F)"
for d in "$tmp"/20??-??-??_*; do
  [ -d "$d" ] || continue
  day="$(basename "$d" | cut -c1-10)"
  [[ "$day" < "$cutoff" ]] && rm -rf "$d"
done
(
  cd "$tmp"
  printf '# review\n\nSmall review files the lanes leave behind (contact sheets, covers, reports). One folder per run, pruned after %s days.\n' "$KEEP_DAYS" > README.md
  git add -A
  if git diff --staged --quiet; then echo "review_push: nothing new"; exit 0; fi
  git commit -q -m "review: $LABEL [skip ci]"
  if git push -q origin "HEAD:$BRANCH" 2>/dev/null || git push -q --force-with-lease origin "HEAD:$BRANCH" 2>/dev/null; then
    echo "review: pushed $LABEL to the $BRANCH branch"
    echo "REVIEW_URL=https://github.com/${GITHUB_REPOSITORY:-johnAzani/docoga}/tree/$BRANCH/$LABEL"
  else
    echo "::warning title=Review not pushed::the $BRANCH branch did not accept the push (the run's work is unaffected)"
  fi
)
exit 0
