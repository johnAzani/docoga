#!/bin/bash
# DocOga Pre-Push Verification
# Run this BEFORE every push to main
# Usage: bash tools/pre_push_verify.sh
#
# FIX HISTORY (2026-10-06):
#   The previous version tested file existence with:
#       if git ls-tree HEAD "<path>" > /dev/null 2>&1; then
#   `git ls-tree` exits 0 even when the path does NOT exist (it just prints
#   nothing), so every check evaluated true and the script could never fail.
#   It reported "ALL CHECKS PASSED" on a tree missing 12 of the 12 files it
#   checks. Existence is now tested with `git cat-file -e`, which exits
#   non-zero for a missing path.

set -u

REF="${REF:-HEAD}"

echo "🔍 DocOga Pre-Push Verification"
echo "================================"
echo "   Checking ref: $REF ($(git rev-parse --short "$REF" 2>/dev/null || echo '??'))"

ERRORS=0
WARNINGS=0

# path_exists <git-path> -> true only if the object really exists at $REF
path_exists() {
    git cat-file -e "$REF:$1" 2>/dev/null
}

check_file() {
    local path="$1"
    local required="${2:-required}"
    if path_exists "$path"; then
        echo "  ✅ $path"
    elif [ "$required" = "optional" ]; then
        echo "  ⚠️  MISSING (optional): $path"
        WARNINGS=$((WARNINGS + 1))
    else
        echo "  ❌ MISSING: $path"
        ERRORS=$((ERRORS + 1))
    fi
}

# ---------------------------------------------------------------- workflows
echo ""
echo "📁 Checking .github/workflows/"
for f in facebook_autopost.yml instagram_autopost.yml telegram_autopost.yml \
         youtube_autopost.yml youtube_queue.yml youtube_scheduled.yml; do
    check_file ".github/workflows/$f"
done

# ------------------------------------------------------------------- tools
echo ""
echo "🔧 Checking tools/"
for f in yt_publish.py fb_publish.py fb_preflight.py ig_publish.py telegram_mdv2.py telegram_preflight.py; do
    check_file "tools/$f"
done

# -------------------------------------------------------------------- docs
echo ""
echo "📄 Checking docs/"
check_file "docs/PRIVATE_DOCS.md"   # the strategy docs moved to the private companion repo (21 Oct 2026)

# ------------------------------------------------------------------- queue
echo ""
echo "📋 Checking queue"
check_file "youtube_queue.json"

# ------------------------------------------------------------------ social
echo ""
echo "📹 Checking social/"
for f in reel-stakes-final.mp4 reel-stakes-caution.mp4; do
    check_file "social/$f"
done

# ------------------------------------------------- untracked working files
echo ""
echo "🔎 Checking for untracked files..."
UNTRACKED=$(git status --porcelain | grep "^??" | grep -E "\.(py|yml|json|md)$" | head -10)
if [ -n "$UNTRACKED" ]; then
    echo "  ⚠️  Untracked files found:"
    echo "$UNTRACKED"
    WARNINGS=$((WARNINGS + 1))
else
    echo "  ✅ no untracked source files"
fi

# --------------------------------------- history-safety check for main push
# Guards against the failure mode that prompted this rewrite: force-pushing a
# branch whose history is unrelated to main, which silently deletes files that
# exist only on main.
echo ""
echo "🛡️  Checking history safety vs origin/main..."
if git rev-parse --verify --quiet origin/main >/dev/null; then
    if git merge-base origin/main "$REF" >/dev/null 2>&1; then
        echo "  ✅ shares history with origin/main"
        BEHIND=$(git rev-list --count "$REF..origin/main" 2>/dev/null || echo 0)
        if [ "$BEHIND" -gt 0 ]; then
            echo "  ⚠️  $REF is $BEHIND commit(s) behind origin/main"
            WARNINGS=$((WARNINGS + 1))
        fi
    else
        echo "  ❌ NO common ancestor with origin/main (unrelated histories)."
        echo "     A force-push here would REPLACE main and delete files that"
        echo "     exist only on main. Do not force-push this ref to main."
        ERRORS=$((ERRORS + 1))
    fi

    echo ""
    echo "  Files present on origin/main but ABSENT from $REF"
    echo "  (these would be DELETED by a force-push to main):"
    LOST=$(comm -13 \
        <(git ls-tree -r --name-only "$REF" | sort) \
        <(git ls-tree -r --name-only origin/main | sort))
    # A deletion is allowed only when it is declared, path by path, in
    # tools/intended_deletions.txt on the branch itself — an auditable manifest that a
    # reviewer sees in the diff. Anything missing from the branch and not declared there
    # is still treated as an accident.
    if [ -n "$LOST" ] && git cat-file -e "$REF:tools/intended_deletions.txt" 2>/dev/null; then
        DECLARED=$(git show "$REF:tools/intended_deletions.txt" | sed 's/#.*//' | sed 's/[[:space:]]*$//' | grep -v '^$' | sort -u)
        ALLOWED=$(comm -12 <(echo "$LOST" | sort) <(echo "$DECLARED"))
        if [ -n "$ALLOWED" ]; then
            echo "  declared in tools/intended_deletions.txt (allowed):"
            echo "$ALLOWED" | sed 's/^/    ~ /'
            LOST=$(comm -23 <(echo "$LOST" | sort) <(echo "$ALLOWED"))
        fi
    fi
    if [ -n "$LOST" ]; then
        echo "$LOST" | sed 's/^/    - /'
        echo "  ❌ $REF would delete $(echo "$LOST" | wc -l | tr -d ' ') file(s) from main."
        ERRORS=$((ERRORS + 1))
    else
        echo "    (none)"
    fi
else
    echo "  ⚠️  origin/main not found locally; run 'git fetch origin' first."
    WARNINGS=$((WARNINGS + 1))
fi

# ------------------------------------------------------------------ verdict
echo ""
echo "================================"
if [ "$ERRORS" -eq 0 ]; then
    if [ "$WARNINGS" -gt 0 ]; then
        echo "✅ Required checks passed ($WARNINGS warning(s)) — review before pushing."
    else
        echo "✅ ALL CHECKS PASSED — Safe to push!"
    fi
    exit 0
else
    echo "❌ $ERRORS ISSUE(S) FOUND — DO NOT PUSH!"
    [ "$WARNINGS" -gt 0 ] && echo "   plus $WARNINGS warning(s)"
    echo ""
    echo "Fix: create/commit the missing files, then run this script again."
    echo "     Never force-push an unrelated-history branch onto main."
    exit 1
fi
