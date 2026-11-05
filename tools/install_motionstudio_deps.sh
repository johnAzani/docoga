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
#
# 5 Nov 2026: every network step is bounded. The 6:00pm Short that day died in this script —
# the install step ran 30 minutes and the job was cancelled at its ceiling before a frame was
# drawn (run 42070315143). apt and curl had no clocks, so one stalled mirror consumed the whole
# lane. Now a stalled door closes in minutes and the next door opens; the install as a whole
# cannot take more than ~12 minutes before `--check` says yes or no.
set -euo pipefail

CLOCK="${INSTALL_STEP_TIMEOUT:-240}"     # seconds any one download / package step may take
CURL=(curl -fsSL --connect-timeout 20 --max-time "$CLOCK" --retry 2 --retry-delay 5)

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FONT_DIR="${MOTIONSTUDIO_FONT_DIR:-$HOME/.local/share/fonts/inter}"
WEIGHTS=(Black Bold SemiBold Medium Regular Light)
INTER_VERSION="${INTER_VERSION:-4.1}"

have_fonts() { python3 "$ROOT/tools/motionstudio.py" --check >/dev/null 2>&1; }

if command -v apt-get >/dev/null 2>&1; then
  timeout "$CLOCK" sudo apt-get update -qq || echo "apt-get update did not finish in ${CLOCK}s — carrying on"
  timeout "$CLOCK" sudo apt-get install -y -qq ffmpeg fonts-inter libfribidi0 || \
    timeout "$CLOCK" sudo apt-get install -y -qq ffmpeg || echo "apt-get install did not finish — the wheel and the zip will do"
fi
timeout "$CLOCK" python3 -m pip install --quiet --timeout 60 --retries 2 "numpy>=1.24,<3" "Pillow>=10,<13"

if ! have_fonts; then
  echo "fonts-inter not usable — fetching the Inter ${INTER_VERSION} release"
  mkdir -p "$FONT_DIR"
  tmp="$(mktemp -d)"
  if "${CURL[@]}" -o "$tmp/inter.zip" \
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
  timeout "$CLOCK" python3 -m pip install --quiet --timeout 60 --retries 2 "fonttools>=4.40" brotli
  mkdir -p "$FONT_DIR"
  for w in "${WEIGHTS[@]}"; do
    "${CURL[@]}" -o "/tmp/Inter-$w.woff2" \
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
  timeout "$CLOCK" python3 -m pip install --quiet --timeout 60 --retries 2 imageio-ffmpeg
fi

python3 "$ROOT/tools/motionstudio.py" --check
