#!/usr/bin/env bash
# Put Inter — the brand's only typeface (docs/BRAND_STYLE.md §2) — where
# tools/social_card.py looks for it, on a GitHub runner or a laptop, in ~10 s.
#
# Why a script and not one apt line: the Instagram and Threads jobs never installed
# a font at all, so every card they drew up to 16 Oct 2026 came out in DejaVu Sans —
# legible, and not ours. The Facebook jobs tried `apt-get install fonts-inter` and
# swallowed the failure. This is the one place that knows the two sources
# (apt first, then the Inter release zip from GitHub, same as
# tools/install_motionstudio_deps.sh) and *proves* the result by asking the card
# renderer which face it will use, so a fallback is a named warning in the log,
# never a silent DejaVu on a public post.
#
# Usage: bash tools/install_brand_fonts.sh     (exit 0 always; prints BRAND_FONT=…)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FONT_DIR="${BRAND_FONT_DIR:-$HOME/.local/share/fonts/inter}"
WEIGHTS=(Black SemiBold Regular Bold Medium Light)
INTER_VERSION="${INTER_VERSION:-4.1}"

face() {
  python3 - "$ROOT" <<'PY' 2>/dev/null || echo "unknown"
import os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "tools"))
try:
    import social_card
    print(os.path.basename(social_card._font_path("Black") or "none"))
except Exception as exc:  # Pillow missing, most likely — the caller installs it
    print("unknown (%s)" % type(exc).__name__)
PY
}

is_inter() { case "$(face)" in Inter-*) return 0 ;; *) return 1 ;; esac; }

if ! is_inter && command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -qq >/dev/null 2>&1 || true
  sudo apt-get install -y -qq fonts-inter >/dev/null 2>&1 || true
fi

if ! is_inter; then
  echo "fonts-inter not usable — fetching the Inter ${INTER_VERSION} release from GitHub"
  mkdir -p "$FONT_DIR"
  tmp="$(mktemp -d)"
  if curl -fsSL --retry 3 -o "$tmp/inter.zip" \
       "https://github.com/rsms/inter/releases/download/v${INTER_VERSION}/Inter-${INTER_VERSION}.zip"; then
    (cd "$tmp" && unzip -q -o inter.zip) || true
    for w in "${WEIGHTS[@]}"; do
      f="$(find "$tmp" \( -name "Inter-$w.otf" -o -name "Inter-$w.ttf" \) | head -1 || true)"
      [ -n "$f" ] && cp "$f" "$FONT_DIR/"
    done
  else
    echo "::warning title=Inter download failed::github.com/rsms/inter release ${INTER_VERSION} unreachable"
  fi
  rm -rf "$tmp"
fi

FACE="$(face)"
echo "BRAND_FONT=$FACE"
if is_inter; then
  echo "brand font ready: $FACE"
else
  echo "::warning title=Inter not installed::the card renders in $FACE this run — legible, but not the brand face (docs/BRAND_STYLE.md §2)"
fi
exit 0
