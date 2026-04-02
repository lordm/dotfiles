#!/usr/bin/env bash
#
# guitar-session.sh — Start a low-latency guitar practice session
# with Neural DSP plugins in REAPER via PipeWire JACK
#
# Usage:
#   guitar-session.sh              Launch REAPER (default)
#   guitar-session.sh standalone   Launch Nolly standalone (requires Wine 11.x)
#   guitar-session.sh standalone petrucci  Launch Petrucci standalone
#

set -euo pipefail

REAPER_BIN="$HOME/opt/REAPER/reaper"
WINEPREFIX="$HOME/.wine-neuraldsp"
export WINEPREFIX

NOLLY_EXE="$WINEPREFIX/drive_c/Program Files/Neural DSP/Archetype Nolly X/Archetype Nolly X.exe"
PETRUCCI_EXE="$WINEPREFIX/drive_c/Program Files/Neural DSP/Archetype Petrucci X/Archetype Petrucci X.exe"

echo "=== Guitar Practice Session ==="
echo ""

# 1. Verify Scarlett Solo is connected
if ! pw-cli list-objects Node 2>/dev/null | grep -q "Scarlett Solo"; then
    echo "ERROR: Scarlett Solo 4th Gen not detected!"
    echo "  - Check USB connection"
    echo "  - Run: pw-cli list-objects Node | grep Scarlett"
    exit 1
fi
echo "[OK] Scarlett Solo 4th Gen detected"

# 2. Set CPU governor to performance (reduces latency spikes from frequency scaling)
if [ -w /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
    echo performance | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null 2>&1
    echo "[OK] CPU governor: performance"
elif command -v cpupower &>/dev/null; then
    sudo cpupower frequency-set -g performance > /dev/null 2>&1 && echo "[OK] CPU governor: performance" || echo "[!!] Could not set CPU governor (needs sudo)"
else
    echo "[!!] CPU governor unchanged (install cpupower or run as root)"
fi

# 4. Verify PipeWire quantum
QUANTUM=$(pw-metadata -n settings 0 2>/dev/null | grep "key:'clock.quantum'" | grep -oP "value:'\K[0-9]+" || echo "default")
echo "[OK] PipeWire quantum: ${QUANTUM} samples at 48000Hz"

# 5. Set Scarlett as default audio device
SCARLETT_SINK=$(pw-cli list-objects Node 2>/dev/null | grep -B5 "Scarlett Solo" | grep -B5 "Audio/Sink" | grep -oP 'id \K[0-9]+' | head -1 || true)
SCARLETT_SOURCE=$(pw-cli list-objects Node 2>/dev/null | grep -B5 "Scarlett Solo" | grep -B5 "Audio/Source" | grep -oP 'id \K[0-9]+' | head -1 || true)

[ -n "$SCARLETT_SINK" ] && wpctl set-default "$SCARLETT_SINK" 2>/dev/null || true
[ -n "$SCARLETT_SOURCE" ] && wpctl set-default "$SCARLETT_SOURCE" 2>/dev/null || true
echo "[OK] Scarlett Solo set as default input/output"

echo ""
echo "=== Scarlett Solo Routing Reminder ==="
echo "  Input 1 (XLR/TTS): Guitar (use INST mode on the Scarlett)"
echo "  Output:             Headphones or monitors"
echo "======================================="
echo ""

if [ "${1:-}" = "standalone" ]; then
    PLUGIN="${2:-nolly}"
    if [ "$PLUGIN" = "petrucci" ] || [ "$PLUGIN" = "p" ]; then
        echo "[..] Launching Archetype Petrucci X (standalone)..."
        wine explorer /desktop=NeuralDSP,1920x1080 "$PETRUCCI_EXE" > /dev/null 2>&1 &
    else
        echo "[..] Launching Archetype Nolly X (standalone)..."
        wine explorer /desktop=NeuralDSP,1920x1080 "$NOLLY_EXE" > /dev/null 2>&1 &
    fi
    disown
    echo "  Audio driver: Windows Audio (WASAPI)"
else
    echo "[..] Launching REAPER (via pw-jack)..."
    echo "  Audio system: JACK"
    echo "  Add FX -> VST3 -> Neural DSP -> Archetype Nolly/Petrucci"
    pw-jack "$REAPER_BIN" > /dev/null 2>&1 &
    disown
fi

echo ""
echo "Happy playing!"
