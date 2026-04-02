# Neural DSP on Ubuntu 24.04 — Complete Setup Guide

Run Neural DSP Archetype plugins (Nolly, Petrucci, etc.) on Linux for low-latency guitar practice using Wine + Yabridge + REAPER, with a Focusrite Scarlett Solo over PipeWire.

**Tested on:** Ubuntu 24.04 LTS, NVIDIA GPU, Focusrite Scarlett Solo 4th Gen, PipeWire 1.0.5, April 2026.

---

## Audio Pipeline

```
                          GUITAR PRACTICE SIGNAL CHAIN
                          ============================

  Guitar
    |
    v
 [Scarlett Solo 4th Gen]  (USB, class-compliant, INST mode)
    |
    |  USB Audio (48000 Hz)
    v
 [ALSA Driver]
    |  period-size=512, period-num=2, disable-batch=true, headroom=128
    v
 [PipeWire]  (quantum=512, rate=48000, RT priority=95)
    |
    |--- JACK protocol (pw-jack) ---------> [REAPER]
    |                                           |
    |                                      [yabridge]  (Linux .so shim)
    |                                           |
    |                                      [Wine 9.21]  (yabridge-host.exe)
    |                                           |
    |                                      [Neural DSP VST3]
    |                                        Archetype Nolly X
    |                                        Archetype Petrucci X
    |                                           |
    |                                      (processed audio back
    |                                       through yabridge -> REAPER
    |                                       -> JACK -> PipeWire)
    |
    |--- PulseAudio compat ----------------> [Spotify, Browser, etc.]
    |
    |--- BlueZ A2DP -----------------------> [Bluetooth Headphones]
    |
    v
 [Scarlett Solo Output]  --> Headphones / Monitors
```

```
                          COMPONENT RESPONSIBILITIES
                          ==========================

  PipeWire          Central audio server, manages all routing + mixing
  WirePlumber       Session manager, applies ALSA tuning rules per-device
  pw-jack           Wrapper that connects REAPER to PipeWire's JACK server
  REAPER            DAW, hosts VST3 plugins, handles recording/playback
  yabridge          Bridges Windows VST3 (in Wine) to native Linux VST3
  Wine 9.21         Runs Windows plugin binaries (Neural DSP, iLok)
  ALSA              Kernel-level audio driver for Scarlett Solo USB
```

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Install Wine Staging 9.21](#install-wine-staging-921)
3. [Configure Wine Prefix](#configure-wine-prefix)
4. [Install iLok License Support](#install-ilok-license-support)
5. [Install Neural DSP Plugins](#install-neural-dsp-plugins)
6. [Activate Licenses](#activate-licenses)
7. [Install Yabridge](#install-yabridge)
8. [Install REAPER](#install-reaper)
9. [Configure PipeWire for Low Latency](#configure-pipewire-for-low-latency)
10. [Fix Real-Time Audio Priority](#fix-real-time-audio-priority)
11. [Configure REAPER](#configure-reaper)
12. [Guitar Session Script](#guitar-session-script)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Ubuntu 24.04 LTS (or Debian-based with PipeWire)
- A USB audio interface (this guide uses Focusrite Scarlett Solo 4th Gen, which is class-compliant — no drivers needed)
- Neural DSP plugin licenses (purchased from neuraldsp.com)
- An iLok account (Neural DSP switched to iLok licensing in 2024)

Verify your audio interface is detected:

```bash
pw-cli list-objects Node | grep -i "your-interface-name"
```

---

## Install Wine Staging 9.21

> **CRITICAL: You must use Wine Staging 9.21, not newer.**
> Wine 9.22+ and Wine 10/11 have a regression that breaks yabridge's GUI embedding — plugin windows render but are completely unresponsive to mouse input. This is tracked in [yabridge #409](https://github.com/robbert-vdh/yabridge/issues/409). Pin to 9.21 until yabridge releases a fix.
>
> **Note on standalone mode:** Wine 9.21 has a different issue where Neural DSP standalone `.exe` files crash with `Exception frame is not in stack limits`. Standalone mode requires Wine 11.x, but that breaks yabridge embedding. Since you can only use one Wine version at a time, **use Wine 9.21 with REAPER + yabridge** — this is the more versatile workflow (multiple plugins on separate tracks, recording, etc.).

```bash
# Enable 32-bit architecture
sudo dpkg --add-architecture i386

# Add WineHQ repository
sudo mkdir -pm755 /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
sudo wget -NP /etc/apt/sources.list.d/ \
  https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources

# Install Wine Staging 9.21 specifically
sudo apt update
sudo apt install --install-recommends \
  winehq-staging=9.21~noble-1 \
  wine-staging=9.21~noble-1 \
  wine-staging-amd64=9.21~noble-1 \
  wine-staging-i386:i386=9.21~noble-1

# Pin the version to prevent auto-upgrade
sudo apt-mark hold winehq-staging wine-staging wine-staging-amd64 wine-staging-i386

# Verify
wine --version
# Expected: wine-9.21 (Staging)
```

Install winetricks:

```bash
sudo apt install winetricks
```

> **Activation workaround:** You need Wine 11.x temporarily to activate licenses via the standalone (see [Activate Licenses](#activate-licenses)). After activation, downgrade back to 9.21. License data persists in the Wine prefix.

---

## Configure Wine Prefix

Create a dedicated Wine prefix for Neural DSP. This isolates it from other Wine applications.

```bash
export WINEPREFIX="$HOME/.wine-neuraldsp"
export WINEARCH=win64

# Initialize the prefix
wineboot --init

# Install required runtime components
winetricks -q vcrun2019       # Visual C++ runtime (Neural DSP dependency)
winetricks -q corefonts       # Fonts for GUI rendering
winetricks -q d3dcompiler_47  # DirectX shader compiler (plugin GUIs use D3D)
winetricks -q gdiplus         # GDI+ rendering support

# Set Windows version to Windows 10
winetricks win10

# Set audio to PulseAudio (routes through PipeWire)
winetricks sound=pulse
```

**Why these components:**
- `vcrun2019`: Neural DSP plugins link against the MSVC 2015-2019 runtime
- `d3dcompiler_47`: Plugin GUIs use Direct3D for rendering; without this you may get blank/black windows
- `win64`: Neural DSP Archetype plugins ship as 64-bit VST3 only

---

## Install iLok License Support

Neural DSP switched to iLok licensing in ~2024. The iLok License Manager must be installed in the Wine prefix before activating plugins.

1. Download the **Windows 64-bit** iLok License Support installer from [ilok.com](https://www.ilok.com/#!license-manager) (direct wget is blocked by their CDN — use a browser)

2. Extract and install:

```bash
cd /tmp
unzip ~/Downloads/LicenseSupportInstallerWin64.zip -d ilok_installer

export WINEPREFIX="$HOME/.wine-neuraldsp"
wine explorer /desktop=iLok,1280x720 \
  "/tmp/ilok_installer/LicenseSupportInstallerWin64_*/License Support Win64.exe"
```

3. Follow the installer wizard in the Wine virtual desktop window.

---

## Install Neural DSP Plugins

1. Download your plugin installers from [neuraldsp.com/my-plugins](https://neuraldsp.com/my-plugins) (e.g., `Archetype-Nolly-X-Installer.exe`, `Archetype-Petrucci-X-Installer.exe`)

2. Run each installer in the Wine prefix:

```bash
export WINEPREFIX="$HOME/.wine-neuraldsp"
wine ~/Downloads/Archetype-Nolly-X-Installer*.exe
wine ~/Downloads/Archetype-Petrucci-X-Installer*.exe
```

3. Keep the default install paths:
   - VST3 → `C:\Program Files\Common Files\VST3\`
   - Standalone → `C:\Program Files\Neural DSP\`

---

## Activate Licenses

Activation requires GUI interaction via the standalone `.exe`, which requires Wine 11.x. If you installed Wine 9.21 first, temporarily upgrade for activation:

```bash
# Temporarily unhold and upgrade Wine for activation
sudo apt-mark unhold winehq-staging wine-staging wine-staging-amd64 wine-staging-i386
sudo apt install --install-recommends winehq-staging
```

Launch each plugin's standalone in a Wine virtual desktop:

```bash
export WINEPREFIX="$HOME/.wine-neuraldsp"

# Activate Nolly
wine explorer /desktop=NeuralDSP,1920x1080 \
  "$HOME/.wine-neuraldsp/drive_c/Program Files/Neural DSP/Archetype Nolly X/Archetype Nolly X.exe"
```

- Log in with your iLok/Neural DSP account credentials in the activation dialog
- Once activated, close the plugin
- Repeat for each plugin

After activation, downgrade back to Wine 9.21:

```bash
sudo apt install --allow-downgrades \
  winehq-staging=9.21~noble-1 \
  wine-staging=9.21~noble-1 \
  wine-staging-amd64=9.21~noble-1 \
  wine-staging-i386:i386=9.21~noble-1
sudo apt-mark hold winehq-staging wine-staging wine-staging-amd64 wine-staging-i386
```

> **Note:** License data is stored in the Wine prefix and persists across Wine version changes. You only need to activate once.

> **Note:** If you see "Activation Error — License Support software not installed", the iLok License Support was not installed correctly. Repeat the [iLok installation step](#install-ilok-license-support).

---

## Install Yabridge

Yabridge bridges Windows VST plugins running in Wine to appear as native Linux VSTs. It is not in Ubuntu 24.04's apt repos — install from GitHub.

> **Architecture note:** Yabridge creates native Linux `.so` shims for each Windows `.vst3`. When your DAW loads the shim, yabridge spawns a Wine host process for the real plugin. Audio passes through your DAW's native audio path (PipeWire/JACK), NOT through Wine's audio. This means WineASIO is NOT needed for the DAW workflow.

```bash
# Get latest version
YABRIDGE_VERSION=$(curl -s https://api.github.com/repos/robbert-vdh/yabridge/releases/latest \
  | grep -Po '"tag_name": "\K[^"]*')

# Download (yabridgectl is bundled inside the same tarball — there is no separate download)
cd /tmp
wget "https://github.com/robbert-vdh/yabridge/releases/download/${YABRIDGE_VERSION}/yabridge-${YABRIDGE_VERSION}.tar.gz"

# Extract
mkdir -p ~/.local/share/yabridge ~/.local/bin
tar -xzf "yabridge-${YABRIDGE_VERSION}.tar.gz" -C ~/.local/share/yabridge --strip-components=1

# Install yabridgectl (bundled in the tarball)
cp ~/.local/share/yabridge/yabridgectl ~/.local/bin/yabridgectl
chmod +x ~/.local/bin/yabridgectl

# Add ~/.local/bin to PATH (add to your .zshrc or .bashrc)
export PATH="$HOME/.local/bin:$PATH"

# Verify
yabridgectl --version
```

Configure yabridge to find your plugins:

```bash
# Create the VST3 directory if it doesn't exist
mkdir -p "$HOME/.wine-neuraldsp/drive_c/Program Files/Common Files/VST3"

# Register the plugin directory (yabridge auto-detects ~/.local/share/yabridge — no set --path needed)
yabridgectl add "$HOME/.wine-neuraldsp/drive_c/Program Files/Common Files/VST3"

# Create Linux shims
yabridgectl sync
```

After sync, bridged plugins appear in `~/.vst3/yabridge/`.

---

## Install REAPER

Download the latest stable Linux x86_64 build from [reaper.fm](https://www.reaper.fm/download.php):

```bash
cd /tmp
wget https://www.reaper.fm/files/7.x/reaper752_linux_x86_64.tar.xz  # adjust version
tar -xf reaper*_linux_x86_64.tar.xz
cd reaper_linux_x86_64
./install-reaper.sh  # install to ~/opt/REAPER by default
```

---

## Configure PipeWire for Low Latency

Ubuntu 24.04 ships PipeWire with conservative defaults (~21ms latency). For guitar practice we target ~11.6ms, which is the stable sweet spot for USB interfaces with Wine/yabridge overhead.

### Important: Sample rate

Lock PipeWire to **48000 Hz**. This matches what Bluetooth A2DP and USB audio interfaces expect natively. Desktop audio apps like Spotify (which output 44100) are transparently resampled by PipeWire — this is inaudible for music playback.

Do NOT allow rate switching (`allowed-rates = [ 44100 48000 ]`) — PipeWire switching between rates during playback causes xruns and crackling.

### PipeWire quantum config

Create `~/.config/pipewire/pipewire.conf.d/99-low-latency.conf`:

```
# Low-latency configuration for guitar practice with Neural DSP
# Quantum 512 @ 48000 = ~10.7ms (stable with Scarlett Solo USB + Wine/yabridge)
#
# Adjust and restart: systemctl --user restart pipewire pipewire-pulse wireplumber

context.properties = {
    default.clock.rate          = 48000
    default.clock.allowed-rates = [ 48000 ]
    default.clock.quantum       = 512
    default.clock.min-quantum   = 32
    default.clock.max-quantum   = 8192
}
```

### WirePlumber ALSA tuning

USB audio interfaces need ALSA-level tuning to minimize latency. Create `~/.config/wireplumber/main.lua.d/51-scarlett-low-latency.lua`:

```lua
-- Low-latency ALSA config for Focusrite Scarlett Solo 4th Gen
-- Adjust the node.name match pattern for your interface
alsa_monitor.rules = {
  {
    matches = {
      {
        { "node.name", "matches", "alsa_output.*Scarlett*" },
      },
      {
        { "node.name", "matches", "alsa_input.*Scarlett*" },
      },
    },
    apply_properties = {
      ["api.alsa.disable-batch"] = true,
      ["api.alsa.headroom"]      = 128,
      ["api.alsa.period-size"]   = 512,
      ["api.alsa.period-num"]    = 2,
    },
  },
}
```

To find your interface's node name: `pw-cli list-objects Node | grep -i "your-interface"`

**Why these values:**
- `disable-batch = true`: Prevents ALSA from batching USB transfers, reducing latency
- `headroom = 128`: Safety buffer for USB scheduling jitter (0 causes xruns on USB)
- `period-size = 512`: Matches PipeWire quantum; smaller values (256) cause xruns on USB
- `period-num = 2`: Double-buffering (standard for low-latency)

Apply changes:

```bash
systemctl --user restart pipewire pipewire-pulse wireplumber
```

Verify:

```bash
pw-metadata -n settings 0 | grep clock.quantum
# Should show: value:'512'
```

### Monitoring for xruns

Use `pw-top` to monitor real-time performance. The `ERR` column shows xrun count — it should stay at 0 or very low during playing:

```bash
pw-top
```

---

## Fix Real-Time Audio Priority

Without real-time scheduling, Wine's audio thread gets preempted and you hear crackles at any buffer size. This is the single most important step for clean audio.

### The problem on Ubuntu 24.04

Ubuntu 24.04 ships `/etc/security/limits.d/25-pw-rlimits.conf` which grants RT priority to the `@pipewire` group:

```
@pipewire   - rtprio  95
@pipewire   - memlock unlimited
```

However:
1. The `pipewire` group **may not exist** by default
2. Your user is **not added** to it automatically
3. The legacy `audio` group config is **disabled** (`audio.conf.disabled`)
4. The PAM limits module must be loaded by the systemd user session

### The fix

```bash
# Create the pipewire group if it doesn't exist
sudo groupadd -f pipewire

# Add your user to it
sudo usermod -aG pipewire $USER

# CRITICAL: Verify /etc/pam.d/systemd-user includes pam_limits.so
# On Ubuntu 24.04, the default file at /usr/lib/pam.d/systemd-user already
# includes "session required pam_limits.so". If /etc/pam.d/systemd-user exists
# and is missing this line, restore the default:
sudo cp /usr/lib/pam.d/systemd-user /etc/pam.d/systemd-user

# Reboot (required — logout is not sufficient)
sudo reboot
```

### Verify after reboot

```bash
ulimit -r
# Must show: 95

ulimit -l
# Should show: unlimited

groups
# Should include: pipewire
```

### Why other approaches don't work

- **Adding user to `audio` group**: The file `audio.conf.disabled` means this group has no limits. You'd need to rename it to `audio.conf`, but the `pipewire` group is the modern correct way.
- **Adding `pam_limits.so` to `common-session`**: Only affects TTY/SSH sessions. Desktop sessions use `/etc/pam.d/systemd-user`.
- **systemd service overrides (`LimitRTPRIO=95`)**: Only applies to that specific service unit, not your shell or Wine processes.

> **WARNING:** Do NOT overwrite `/etc/pam.d/systemd-user` with just a `pam_limits.so` line. This file controls the entire systemd user session. If corrupted, PipeWire won't start and you'll lose all audio (no devices in sound settings, no output). Always restore from `/usr/lib/pam.d/systemd-user` if in doubt.

---

## Configure REAPER

### Audio settings

REAPER must be launched with `pw-jack` to connect to PipeWire's JACK server:

```bash
pw-jack ~/opt/REAPER/reaper
```

Then in REAPER: **Options → Preferences → Audio → Device**

| Setting | Value |
|---|---|
| Audio system | JACK |
| Input channels | 2 |
| Output channels | 2 |

The sample rate and buffer size are controlled by PipeWire (48000 Hz, quantum 512), not REAPER. REAPER inherits them from the JACK server.

> **Why JACK, not ALSA or PulseAudio:**
> - **ALSA direct** (`hw:Gen`): Lowest latency, but exclusively locks the Scarlett — no other app can use audio (no system sounds, no Spotify, no browser audio). Also conflicts with PipeWire.
> - **PulseAudio**: Works but adds an extra buffer layer, causing noticeable delay and crackling.
> - **JACK** (via `pw-jack`): Routes through PipeWire's built-in JACK server. Low latency, shared audio (Spotify works alongside REAPER), no device conflicts. **This is the recommended option.**

### VST3 plugin path

REAPER auto-scans `~/.vst3/` recursively, which includes `~/.vst3/yabridge/`. The Neural DSP plugins should appear automatically after `yabridgectl sync`.

If they don't:
1. **Options → Preferences → Plug-ins → VST**
2. Add path: `/home/youruser/.vst3/yabridge`
3. Click **Re-scan**

### Yabridge config (optional)

Create `~/.config/yabridge/yabridge.toml`:

```toml
# Enable drag-and-drop onto plugin GUIs in REAPER
["Archetype Nolly X.vst3"]
editor_force_dnd = true

["Archetype Petrucci X.vst3"]
editor_force_dnd = true
```

### Using a plugin in REAPER

1. Create a track
2. **Arm the track for recording** (click the red record button on the track)
3. Set input to your guitar channel (Input 1 mono or Stereo 1/2)
4. Click **FX** → search for "Archetype" → add the plugin
5. Enable input monitoring (speaker icon on the track)
6. Play!

---

## Guitar Session Script

Save as `~/scripts/guitar-session.sh`:

```bash
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

# 2. Verify PipeWire quantum
QUANTUM=$(pw-metadata -n settings 0 2>/dev/null \
  | grep "key:'clock.quantum'" | grep -oP "value:'\K[0-9]+" || echo "default")
echo "[OK] PipeWire quantum: ${QUANTUM} samples at 48000Hz"

# 3. Set Scarlett as default audio device
SCARLETT_SINK=$(pw-cli list-objects Node 2>/dev/null \
  | grep -B5 "Scarlett Solo" | grep -B5 "Audio/Sink" \
  | grep -oP 'id \K[0-9]+' | head -1 || true)
SCARLETT_SOURCE=$(pw-cli list-objects Node 2>/dev/null \
  | grep -B5 "Scarlett Solo" | grep -B5 "Audio/Source" \
  | grep -oP 'id \K[0-9]+' | head -1 || true)
[ -n "$SCARLETT_SINK" ] && wpctl set-default "$SCARLETT_SINK" 2>/dev/null || true
[ -n "$SCARLETT_SOURCE" ] && wpctl set-default "$SCARLETT_SOURCE" 2>/dev/null || true
echo "[OK] Scarlett Solo set as default I/O"

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
    echo "  NOTE: Standalone requires Wine 11.x (crashes on Wine 9.21)"
else
    echo "[..] Launching REAPER (via pw-jack)..."
    echo "  Audio system: JACK"
    echo "  Add FX -> VST3 -> Neural DSP -> Archetype Nolly/Petrucci"
    pw-jack "$REAPER_BIN" > /dev/null 2>&1 &
    disown
fi

echo ""
echo "Happy playing!"
```

```bash
chmod +x ~/scripts/guitar-session.sh
```

---

## Troubleshooting

### Plugin GUI renders but doesn't respond to mouse clicks

**Cause:** Wine 9.22+ broke X11 window embedding for yabridge. Tracked in [yabridge #409](https://github.com/robbert-vdh/yabridge/issues/409).
**Fix:** Downgrade to Wine Staging 9.21 (see [Install Wine](#install-wine-staging-921)).

### Standalone .exe crashes with "Exception frame is not in stack limits"

**Cause:** Wine 9.21 doesn't support Neural DSP standalone executables.
**Fix:** Standalone mode requires Wine 11.x. Use REAPER + yabridge on Wine 9.21 instead, or temporarily upgrade Wine for standalone use. You cannot use both workflows with the same Wine version.

### Crackles/pops at all buffer sizes

**Cause:** No real-time scheduling. Check `ulimit -r` — if it shows `0`, your audio threads are getting preempted.
**Fix:** Follow the [real-time priority fix](#fix-real-time-audio-priority). A full reboot is required.

### Crackles only in REAPER, not in Spotify

**Cause:** Sample rate mismatch between PipeWire and audio devices. If PipeWire allows rate switching (`allowed-rates = [ 44100 48000 ]`), it switches rates when different apps request different rates, causing xruns during transitions. Check with `pw-top` — look at the RATE column.
**Fix:** Lock PipeWire to 48000 Hz with `allowed-rates = [ 48000 ]`. Bluetooth and USB interfaces natively use 48000. Spotify (44100) is transparently resampled — inaudible for music playback.

### Crackles from everything (Spotify, REAPER, system sounds)

**Cause:** PipeWire quantum is too small for your USB interface. USB audio has inherent scheduling overhead.
**Fix:** Increase quantum to 512 or 1024 in `99-low-latency.conf` and increase `api.alsa.period-size` to match in the WirePlumber config. Restart PipeWire.

### No sound from REAPER with JACK audio

**Cause:** REAPER can't find the JACK server.
**Fix:** Launch REAPER with `pw-jack ~/opt/REAPER/reaper`. The `pw-jack` wrapper sets the library path so REAPER connects to PipeWire's built-in JACK server.

### No sound from REAPER with ALSA audio ("Error opening input device")

**Cause:** PipeWire has exclusive control of the audio interface. ALSA direct mode (`hw:Gen`) conflicts.
**Fix:** Use JACK audio instead of ALSA (see [Configure REAPER](#configure-reaper)).

### REAPER hangs when adding a Neural DSP plugin

**Cause:** Stale Wine processes from a previous session or standalone launch.
**Fix:** Kill all Wine processes before launching REAPER:
```bash
WINEPREFIX=~/.wine-neuraldsp wineserver -k9
# If that doesn't work:
pkill -9 -f wineserver; pkill -9 -f winedevice; pkill -9 -f explorer.exe; pkill -9 -f yabridge-host
```

### "Activation Error — License Support software not installed"

**Cause:** Neural DSP now requires iLok License Support.
**Fix:** Download and install [iLok License Manager](https://www.ilok.com/#!license-manager) (Windows 64-bit version) inside the Wine prefix.

### Plugin GUI is blank/black

**Cause:** Missing Direct3D shader compiler.
**Fix:** `WINEPREFIX=~/.wine-neuraldsp winetricks -q d3dcompiler_47`

### Plugins don't appear in REAPER after install

**Fix:**
```bash
yabridgectl sync
```
Then in REAPER: Options → Preferences → Plug-ins → VST → Re-scan.

### REAPER plugin scan shows plugins but they fail to load

**Cause:** Stale scan cache with failed entries.
**Fix:** Edit `~/.config/REAPER/reaper-vstplugins64.ini`, remove the `Archetype_*` lines under `[vstcache]`, then rescan.

### No audio devices in system settings after Wine install/downgrade

**Cause:** PipeWire not running, possibly due to corrupted `/etc/pam.d/systemd-user`.
**Fix:**
```bash
sudo cp /usr/lib/pam.d/systemd-user /etc/pam.d/systemd-user
sudo reboot
```

### Standalone plugin has echo/resonance artifacts

**Cause:** Using DirectSound audio driver in the plugin.
**Fix:** In the plugin's settings, change audio driver from DirectSound to **Windows Audio (WASAPI)**.

### PipeWire quantum not changing

**Verify config is loaded:**
```bash
pw-metadata -n settings 0 | grep clock.quantum
```
**Force at runtime (no restart needed):**
```bash
pw-metadata -n settings 0 clock.force-quantum 512
```
**Reset forced quantum back to config default:**
```bash
pw-metadata -n settings 0 clock.force-quantum 0
```

> **Warning:** Using `clock.force-quantum` can sometimes cause audio to stop entirely. If this happens, reset it to 0 and restart PipeWire: `systemctl --user restart pipewire pipewire-pulse wireplumber`

### Bluetooth audio crackling

**Cause:** PipeWire sample rate mismatch. Bluetooth A2DP natively uses 48000 Hz. If PipeWire runs at 44100 or allows rate switching, the Bluetooth stream is constantly resampled, causing audible artifacts.
**Fix:** Lock PipeWire to 48000 Hz with `allowed-rates = [ 48000 ]` in your PipeWire config. Restart PipeWire. If the Buds got stuck in headset (HFP) mode, disconnect and reconnect from Bluetooth settings to restore A2DP.

### Multi-monitor coordinate issues

NVIDIA with multiple monitors at different resolutions can cause Wine window coordinate mismatches. If plugin controls respond but at wrong positions, try moving REAPER to your primary monitor.

---

## Optional Performance Tuning

These are not required for the base setup but can improve stability under load.

### CPU governor

The default `powersave` governor causes the CPU to ramp up on demand, introducing micro-latency spikes. Set `performance` during audio sessions:

```bash
# Temporary (resets on reboot)
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Or install cpupower for persistent control
sudo apt install linux-tools-common linux-tools-$(uname -r)
sudo cpupower frequency-set -g performance
```

The guitar session script already handles this automatically.

### threadirqs boot parameter

Makes hardware interrupt handlers run as schedulable kernel threads, allowing USB audio IRQs to get RT priority:

```bash
sudo sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="\(.*\)"/GRUB_CMDLINE_LINUX_DEFAULT="\1 threadirqs"/' /etc/default/grub
sudo update-grub
sudo reboot
```

### Low-latency kernel

Ubuntu's `linux-lowlatency` package enables full kernel preemption and `threadirqs` by default:

```bash
sudo apt install linux-lowlatency
```

Select it in GRUB at boot. Not required at quantum 512 but helpful if you push to 256.

---

## Key Paths Reference

| Item | Path |
|---|---|
| Wine prefix | `~/.wine-neuraldsp` |
| Windows VST3 plugins | `~/.wine-neuraldsp/drive_c/Program Files/Common Files/VST3/` |
| Bridged Linux VST3 shims | `~/.vst3/yabridge/` |
| Yabridge binaries | `~/.local/share/yabridge/` |
| Yabridge config | `~/.config/yabridge/yabridge.toml` |
| Yabridgectl config | `~/.config/yabridgectl/config.toml` |
| PipeWire low-latency config | `~/.config/pipewire/pipewire.conf.d/99-low-latency.conf` |
| WirePlumber ALSA tuning | `~/.config/wireplumber/main.lua.d/51-scarlett-low-latency.lua` |
| RT priority limits | `/etc/security/limits.d/25-pw-rlimits.conf` |
| REAPER | `~/opt/REAPER/reaper` |
| REAPER plugin cache | `~/.config/REAPER/reaper-vstplugins64.ini` |
| Session script | `~/scripts/guitar-session.sh` |

---

## Version Reference

This guide was tested and verified with:

| Component | Version |
|---|---|
| Ubuntu | 24.04 LTS |
| Kernel | 6.17.0 |
| PipeWire | 1.0.5 |
| Wine | Staging 9.21 (pinned) |
| Yabridge | 5.1.1 |
| REAPER | 7.52 |
| iLok License Support | 5.10.4 |
| Audio interface | Focusrite Scarlett Solo 4th Gen (USB, class-compliant) |
| GPU | NVIDIA (driver 580) |

### Working audio config

| Setting | Value |
|---|---|
| Sample rate | 48000 Hz |
| PipeWire quantum | 512 (~10.7ms) |
| ALSA period size | 512, 2 periods |
| ALSA headroom | 128 |
| REAPER audio system | JACK (via `pw-jack`) |
| RT priority | 95 (`ulimit -r`) |

---

*Guide compiled from a real setup session involving extensive trial-and-error. If you find issues or improvements, contributions are welcome.*
