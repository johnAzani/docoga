#!/usr/bin/env bash
# Install the word-sync engine the Shorts/Reels lanes use for kinetic captions and
# per-sentence shots (tools/wordsync.py): the Vosk runtime + the small English model the
# Deep-Dive already aligns with (tools/deepdive.py, VOSK_MODEL_DIR). ~40 MB, cached in /tmp.
#
# Best effort by design: if the model cannot be fetched the lane still ships — wordsync
# falls back to its letter-weighted estimate and prints WORDSYNC=estimate, which the run
# summary surfaces. A Short is never late because a model mirror blinked.
# Usage: bash tools/install_wordsync_deps.sh
set -uo pipefail

MODEL_DIR="${VOSK_MODEL_DIR:-/tmp/vosk/vosk-model-small-en-us-0.15}"
MODEL_URL="https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"

python3 -m pip install --quiet vosk || echo "::warning title=wordsync::pip install vosk failed — captions will use estimated word times"
if [ ! -d "$MODEL_DIR" ]; then
  mkdir -p "$(dirname "$MODEL_DIR")"
  if curl -fsSL --retry 2 -o "$(dirname "$MODEL_DIR")/model.zip" "$MODEL_URL"; then
    (cd "$(dirname "$MODEL_DIR")" && unzip -q -o model.zip && rm -f model.zip)
  else
    echo "::warning title=wordsync::Vosk model download failed — captions will use estimated word times"
  fi
fi
if python3 -c "import vosk" 2>/dev/null && [ -d "$MODEL_DIR" ]; then
  echo "wordsync: Vosk ready at $MODEL_DIR"
else
  echo "wordsync: running on estimated word times"
fi
exit 0
