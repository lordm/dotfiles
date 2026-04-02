#!/usr/bin/env bash
#
# setup-neuraldsp.sh — Install Wine, yabridge, and configure the system
# for Neural DSP Archetype plugins on Ubuntu 24.04
#
# Usage: ./setup-neuraldsp.sh
# Requires: sudo access, internet connection
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

WINEPREFIX="$HOME/.wine-neuraldsp"
YABRIDGE_DIR="$HOME/.local/share/yabridge"
LOCAL_BIN="$HOME/.local/bin"

# ─── Step 1: Install wine-staging ───────────────────────────────────────────

step "Step 1: Installing wine-staging"

sudo dpkg --add-architecture i386
log "Enabled i386 architecture"

sudo mkdir -pm755 /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
log "Added WineHQ signing key"

# Check if Noble sources exist, add if not
if [ ! -f /etc/apt/sources.list.d/winehq-noble.sources ]; then
    sudo wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources
    log "Added WineHQ Noble repository"
else
    log "WineHQ Noble repository already configured"
fi

sudo apt update
sudo apt install --install-recommends -y winehq-staging
log "wine-staging installed: $(wine --version)"

# Install winetricks
if ! command -v winetricks &>/dev/null; then
    sudo apt install -y winetricks
    log "winetricks installed"
else
    log "winetricks already installed"
fi

# ─── Step 2: Configure Wine prefix ─────────────────────────────────────────

step "Step 2: Configuring Wine prefix at $WINEPREFIX"

export WINEPREFIX
export WINEARCH=win64

if [ ! -d "$WINEPREFIX" ]; then
    wineboot --init
    log "Created win64 prefix"
else
    log "Wine prefix already exists"
fi

# Install required components
winetricks -q vcrun2019
log "Installed vcrun2019 (Visual C++ runtime)"

winetricks -q corefonts
log "Installed corefonts"

winetricks -q d3dcompiler_47
log "Installed d3dcompiler_47 (DirectX shader compiler)"

winetricks -q gdiplus
log "Installed gdiplus"

winetricks win10
log "Set Windows version to Windows 10"

# ─── Step 3: Install yabridge ──────────────────────────────────────────────

step "Step 3: Installing yabridge + yabridgectl"

mkdir -p "$YABRIDGE_DIR" "$LOCAL_BIN"

YABRIDGE_VERSION=$(curl -s https://api.github.com/repos/robbert-vdh/yabridge/releases/latest | grep -Po '"tag_name": "\K[^"]*')

if [ -z "$YABRIDGE_VERSION" ]; then
    err "Failed to fetch latest yabridge version from GitHub API"
    err "Check your internet connection or try again later"
    exit 1
fi

log "Latest yabridge version: $YABRIDGE_VERSION"

cd /tmp

# Download yabridge (yabridgectl is bundled inside the same tarball)
if [ ! -f "yabridge-${YABRIDGE_VERSION}.tar.gz" ]; then
    wget "https://github.com/robbert-vdh/yabridge/releases/download/${YABRIDGE_VERSION}/yabridge-${YABRIDGE_VERSION}.tar.gz"
fi

# Extract all yabridge files
tar -xzf "yabridge-${YABRIDGE_VERSION}.tar.gz" -C "$YABRIDGE_DIR" --strip-components=1
log "Extracted yabridge to $YABRIDGE_DIR"

# Copy yabridgectl to ~/.local/bin
cp "$YABRIDGE_DIR/yabridgectl" "$LOCAL_BIN/yabridgectl"
chmod +x "$LOCAL_BIN/yabridgectl"
log "Installed yabridgectl to $LOCAL_BIN"

# Ensure ~/.local/bin is in PATH for this session
export PATH="$LOCAL_BIN:$PATH"

# Configure yabridgectl (auto-detects ~/.local/share/yabridge, no set --path needed)
mkdir -p "$WINEPREFIX/drive_c/Program Files/Common Files/VST3"
yabridgectl add "$WINEPREFIX/drive_c/Program Files/Common Files/VST3"
log "Added Neural DSP VST3 directory to yabridge"

log "yabridgectl version: $(yabridgectl --version)"

# ─── Step 4: Verify ────────────────────────────────────────────────────────

step "Step 4: Verification"

echo "  Wine:        $(wine --version)"
echo "  Winetricks:  $(winetricks --version 2>&1 | head -1)"
echo "  yabridgectl: $(yabridgectl --version)"
echo "  Prefix:      $WINEPREFIX"
echo "  Prefix arch: win64"

# ─── Step 5: PATH reminder ─────────────────────────────────────────────────

step "Step 5: PATH check"

if ! grep -q '\.local/bin' ~/.zshrc 2>/dev/null; then
    warn "~/.local/bin is NOT in your zshrc PATH"
    warn "Add this line to your ~/.zshrc (or run the dotfiles install):"
    echo '  export PATH="$HOME/.local/bin:$PATH"'
else
    log "~/.local/bin already in zshrc PATH"
fi

# ─── Done ───────────────────────────────────────────────────────────────────

step "Setup complete!"
echo ""
echo "Next steps (manual):"
echo "  1. Install Neural DSP plugins — see instructions printed by guitar-session setup"
echo "  2. Activate licenses inside Wine (GUI)"
echo "  3. Run: yabridgectl sync"
echo "  4. Add ~/.vst3/yabridge to REAPER's VST scan paths"
echo ""
