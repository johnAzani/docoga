#!/bin/bash
# DocOga Pre-Push Verification
# Run this BEFORE every push to main
# Usage: bash tools/pre_push_verify.sh

set -e

echo "🔍 DocOga Pre-Push Verification"
echo "================================"

ERRORS=0

# Check workflows
echo ""
echo "📁 Checking .github/workflows/"
for f in facebook_autopost.yml instagram_autopost.yml telegram_autopost.yml youtube_autopost.yml youtube_queue.yml youtube_scheduled.yml; do
    if git ls-tree HEAD ".github/workflows/$f" > /dev/null 2>&1; then
        echo "  ✅ $f"
    else
        echo "  ❌ MISSING: $f"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check tools
echo ""
echo "🔧 Checking tools/"
for f in yt_publish.py fb_publish.py ig_publish.py; do
    if git ls-tree HEAD "tools/$f" > /dev/null 2>&1; then
        echo "  ✅ $f"
    else
        echo "  ❌ MISSING: $f"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check docs
echo ""
echo "📄 Checking docs/"
for f in SESSION_CONTEXT.md; do
    if git ls-tree HEAD "docs/$f" > /dev/null 2>&1; then
        echo "  ✅ $f"
    else
        echo "  ❌ MISSING: $f"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check queue
echo ""
echo "📋 Checking queue"
if git ls-tree HEAD "youtube_queue.json" > /dev/null 2>&1; then
    echo "  ✅ youtube_queue.json"
else
    echo "  ❌ MISSING: youtube_queue.json"
    ERRORS=$((ERRORS + 1))
fi

# Check social/ videos
echo ""
echo "📹 Checking social/"
for f in reel-stakes-final.mp4 reel-stakes-caution.mp4; do
    if git ls-tree HEAD "social/$f" > /dev/null 2>&1; then
        echo "  ✅ $f"
    else
        echo "  ❌ MISSING: $f"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check for untracked files that should be committed
echo ""
echo "🔎 Checking for untracked files..."
UNTRACKED=$(git status --porcelain | grep "^??" | grep -E "\.(py|yml|json|md)$" | head -10)
if [ -n "$UNTRACKED" ]; then
    echo "  ⚠️  Untracked files found:"
    echo "$UNTRACKED"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "================================"
if [ $ERRORS -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED — Safe to push!"
    exit 0
else
    echo "❌ $ERRORS ISSUES FOUND — DO NOT PUSH!"
    echo ""
    echo "Fix: git add -f <missing-file> && git commit -m 'Add missing files' && run this script again"
    exit 1
fi