#!/usr/bin/env bash
# Install what tools/motionstudio.py needs on a GitHub runner (or a fresh laptop):
# ffmpeg + the six Inter weights, then prove it with `motionstudio.py --check`.
#
# Inter is the brand's only typeface (docs/BRAND_STYLE.md §2). Three sources, in
# order, because a font package is the kind of dependency that quietly disappears
# from a distro and leaves the lane rendering in a fallback face nobody approved:
#   1. apt `fonts-inter`
#   2. the Inter release zip from GitHub (extras/otf)
#   3. the woff2 files from the Inter repo, converted with fontTools
# Usage: bash tools/install_motionstudio_deps.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FONT_DIR="${MOTIONSTUDIO_FONT_DIR:-$HOME/.local/share/fonts/inter}"
WEIGHTS=(Black Bold SemiBold Medium Regular Light)
INTER_VERSION="${INTER_VERSION:-4.1}"

have_fonts() { python3 "$ROOT/tools/motionstudio.py" --check >/dev/null 2>&1; }

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -qq || true
  sudo apt-get install -y -qq ffmpeg fonts-inter libfribidi0 || \
    sudo apt-get install -y -qq ffmpeg || true
fi
python3 -m pip install --quiet "numpy>=1.24,<3" "Pillow>=10,<13"

if ! have_fonts; then
  echo "fonts-inter not usable — fetching the Inter ${INTER_VERSION} release"
  mkdir -p "$FONT_DIR"
  tmp="$(mktemp -d)"
  if curl -fsSL -o "$tmp/inter.zip" \
       "https://github.com/rsms/inter/releases/download/v${INTER_VERSION}/Inter-${INTER_VERSION}.zip"; then
    (cd "$tmp" && unzip -q -o inter.zip) || true
    for w in "${WEIGHTS[@]}"; do
      f="$(find "$tmp" -name "Inter-$w.otf" -o -name "Inter-$w.ttf" | head -1 || true)"
      [ -n "$f" ] && cp "$f" "$FONT_DIR/"
    done
  fi
fi

if ! MOTIONSTUDIO_FONT_DIR="$FONT_DIR" have_fonts; then
  echo "release zip not usable — converting the woff2 files from the Inter repo"
  python3 -m pip install --quiet "fonttools>=4.40" brotli
  mkdir -p "$FONT_DIR"
  for w in "${WEIGHTS[@]}"; do
    curl -fsSL -o "/tmp/Inter-$w.woff2" \
      "https://raw.githubusercontent.com/rsms/inter/master/docs/font-files/Inter-$w.woff2"
    python3 - "$w" "$FONT_DIR" <<'PY'
import sys
from fontTools.ttLib import TTFont
w, out = sys.argv[1], sys.argv[2]
f = TTFont(f"/tmp/Inter-{w}.woff2"); f.flavor = None
f.save(f"{out}/Inter-{w}.otf")
PY
  done
fi

if [ -d "$FONT_DIR" ] && [ -n "$(ls -A "$FONT_DIR" 2>/dev/null)" ]; then
  echo "MOTIONSTUDIO_FONT_DIR=$FONT_DIR" >> "${GITHUB_ENV:-/dev/null}"
  export MOTIONSTUDIO_FONT_DIR="$FONT_DIR"
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not on PATH — using the imageio-ffmpeg wheel"
  python3 -m pip install --quiet imageio-ffmpeg
fi

python3 "$ROOT/tools/motionstudio.py" --check
