#!/usr/bin/env bash
# Build the isolated TTS environment: venv, model files, systemd unit.
# Idempotent and safe to re-run. Not called by install.sh -- this pulls
# ~353MB and installs a user service, so it stays a deliberate one-time step.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}/tts"
VENV="$SHARE/venv"
MODELS="$SHARE/models"
RELEASE="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"

command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/"; exit 1; }
command -v paplay >/dev/null || { echo "paplay is required (pulseaudio-utils)"; exit 1; }

mkdir -p "$MODELS"

echo "==> Creating venv at $VENV"
# --allow-existing: a bare `uv venv` errors out if the directory is already a
# venv, which breaks re-running this script (e.g. after a prior run got this
# far and failed later, such as during the model download below).
uv venv --python 3.12 --allow-existing "$VENV"
VIRTUAL_ENV="$VENV" uv pip install --python "$VENV/bin/python" kokoro-onnx soundfile numpy

echo "==> Fetching model files (~353MB, skipped if present)"
# Fetch to a .part sidecar and only move it into place after curl exits
# successfully, so a run that dies mid-download never leaves a truncated
# file sitting under the final name -- which "-s" (exists and non-empty)
# would otherwise mistake for complete on the next run, silently skipping
# the download and leaving a broken model in place.
fetch() {
    local dest="$1" url="$2" tmp="$1.part"
    if [ -s "$dest" ]; then
        return 0
    fi
    rm -f "$tmp"
    curl -fL --progress-bar -o "$tmp" "$url"
    mv -f "$tmp" "$dest"
}
fetch "$MODELS/kokoro-v1.0.onnx" "$RELEASE/kokoro-v1.0.onnx"
fetch "$MODELS/voices-v1.0.bin"  "$RELEASE/voices-v1.0.bin"

echo "==> Smoke test"
"$VENV/bin/python" - <<PY
from kokoro_onnx import Kokoro
k = Kokoro("$MODELS/kokoro-v1.0.onnx", "$MODELS/voices-v1.0.bin")
samples, rate = k.create("Text to speech is working.", voice="af_heart", speed=1.15, lang="en-us")
print(f"synthesized {len(samples)/rate:.1f}s at {rate}Hz")
PY

echo
echo "Environment ready."
