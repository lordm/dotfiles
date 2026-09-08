#!/usr/bin/env bash
#
# setup-hibernate.sh — Hibernate instead of suspend when running on battery,
# so a power cut doesn't cost you the session.
#
# Plain suspend keeps RAM powered; during an outage the battery drains and the
# machine dies mid-S3, coming back as a cold boot. UPower's stock
# CriticalPowerAction=HybridSleep has the same problem: it writes a hibernation
# image *and* stays in S3, so it still bleeds charge until it loses power.
# Hibernating outright powers the machine off, so an outage of any length is
# survivable.
#
# Usage: ./setup-hibernate.sh
# Requires: sudo access, a swap device large enough for the hibernation image
#

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[!!]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*"; }
step() { echo -e "\n${YELLOW}=== $* ===${NC}"; }

UPOWER_CONF=/etc/UPower/UPower.conf
GSD_POWER=org.gnome.settings-daemon.plugins.power

if [ "${EUID}" -eq 0 ]; then
    err "Run this as your normal user, not root — it needs your dconf profile."
    exit 1
fi

# ─── Step 1: Verify the machine can actually hibernate ──────────────────────

step "Step 1: Checking hibernation support"

if ! grep -qw disk /sys/power/state; then
    err "Kernel does not offer the 'disk' sleep state. Hibernation is unavailable."
    exit 1
fi
log "Kernel supports the 'disk' sleep state"

if [ "$(cat /sys/power/resume)" = "0:0" ]; then
    err "No resume device configured — the image would be written but never read back."
    err "On Ubuntu, initramfs-tools normally auto-detects the largest swap partition."
    err "Fix with: echo RESUME=UUID=\$(blkid -s UUID -o value <swap-dev>) | sudo tee /etc/initramfs-tools/conf.d/resume"
    err "then: sudo update-initramfs -u"
    exit 1
fi
log "Resume device set ($(cat /sys/power/resume))"

if [ "$(swapon --noheadings --show=NAME | wc -l)" -eq 0 ]; then
    err "No swap is active. Hibernation needs somewhere to put the image."
    exit 1
fi

# The kernel caps the image at /sys/power/image_size (2/5 of RAM by default),
# so swap only has to cover that, not all of RAM. Warn rather than fail —
# it works until you genuinely have more than that much in use.
swap_bytes=$(( $(free -b | awk '/^Swap:/ {print $2}') ))
image_cap=$(cat /sys/power/image_size)
ram_bytes=$(( $(free -b | awk '/^Mem:/ {print $2}') ))

printf '     swap %s | image cap %s | RAM %s\n' \
    "$(numfmt --to=iec "$swap_bytes")" \
    "$(numfmt --to=iec "$image_cap")" \
    "$(numfmt --to=iec "$ram_bytes")"

if [ "$swap_bytes" -lt "$image_cap" ]; then
    warn "Swap is smaller than the image cap — hibernation will fail under memory pressure."
elif [ "$swap_bytes" -lt "$ram_bytes" ]; then
    warn "Swap is smaller than RAM. Fine for typical use (the kernel caps the image),"
    warn "but hibernation fails if active memory ever exceeds the cap above."
else
    log "Swap comfortably covers RAM"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
    if grep -rqs NVreg_PreserveVideoMemoryAllocations=1 /etc/modprobe.d/ /lib/modprobe.d/; then
        log "NVIDIA VRAM preservation enabled (required for a clean resume)"
    else
        warn "NVIDIA driver present but NVreg_PreserveVideoMemoryAllocations=1 is not set."
        warn "Resume may come back to a corrupted display."
    fi
fi

# ─── Step 2: Point UPower's critical-battery action at hibernate ────────────

step "Step 2: Configuring UPower critical-battery action"

if [ ! -f "$UPOWER_CONF" ]; then
    err "$UPOWER_CONF not found — is upower installed?"
    exit 1
fi

# Keep one pristine copy of whatever was there before this script first ran.
if [ ! -f "${UPOWER_CONF}.dotfiles-bak" ]; then
    sudo cp -a "$UPOWER_CONF" "${UPOWER_CONF}.dotfiles-bak"
    log "Backed up original to ${UPOWER_CONF}.dotfiles-bak"
fi

# Keys may be present, commented out, or absent entirely depending on the
# distro's shipped file, so handle all three.
set_upower_key() {
    local key="$1" val="$2"
    if grep -qE "^${key}=" "$UPOWER_CONF"; then
        sudo sed -i "s|^${key}=.*|${key}=${val}|" "$UPOWER_CONF"
    else
        sudo sed -i "0,/^\[UPower\]/s||[UPower]\n${key}=${val}|" "$UPOWER_CONF"
    fi
}

set_upower_key CriticalPowerAction Hibernate

# upower requires Low > Critical > Action. The stock 2% action threshold is thin
# margin for a multi-second image write on an ageing battery, so leave headroom.
set_upower_key UsePercentageForPolicy true
set_upower_key PercentageLow 20
set_upower_key PercentageCritical 10
set_upower_key PercentageAction 5

sudo systemctl restart upower
log "Restarted upower"

# Ask the daemon, not the file — this is what actually governs behaviour.
live_action=$(gdbus call --system --dest org.freedesktop.UPower \
    --object-path /org/freedesktop/UPower \
    --method org.freedesktop.UPower.GetCriticalAction 2>/dev/null || echo "")
if [[ "$live_action" == *Hibernate* ]]; then
    log "UPower reports critical action: Hibernate"
else
    err "UPower still reports: ${live_action:-<unavailable>}"
    err "Hibernate may be unavailable; upower falls back to HybridSleep/PowerOff."
    exit 1
fi

# ─── Step 3: Make the lid hibernate on battery ──────────────────────────────

step "Step 3: Configuring GNOME lid-close behaviour"

# GNOME's gsd-power holds the logind handle-lid-switch inhibitor, so
# /etc/systemd/logind.conf is inert here — gsettings is the effective knob.
# Its enum has no suspend-then-hibernate, and systemd 255 lacks
# HibernateOnACPower= to scope that to battery, so this is immediate hibernate.
if command -v gsettings >/dev/null 2>&1 && gsettings writable "$GSD_POWER" lid-close-battery-action >/dev/null 2>&1; then
    gsettings set "$GSD_POWER" lid-close-battery-action 'hibernate'
    log "Lid close on battery -> $(gsettings get "$GSD_POWER" lid-close-battery-action)"
    log "Lid close on AC      -> $(gsettings get "$GSD_POWER" lid-close-ac-action) (left alone)"
else
    warn "gsettings schema $GSD_POWER unavailable — skipping lid config (not a GNOME session?)"
fi

echo
log "Done. Test with: systemctl hibernate"
warn "Reverting: sudo cp ${UPOWER_CONF}.dotfiles-bak $UPOWER_CONF && sudo systemctl restart upower"
warn "           gsettings reset $GSD_POWER lid-close-battery-action"
