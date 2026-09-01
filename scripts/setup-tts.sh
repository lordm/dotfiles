#!/usr/bin/env bash
# Build the isolated TTS environment: venv, model files, systemd unit, and the
# harness hooks that actually make anything speak.
# Idempotent and safe to re-run. Not called by install.sh -- this pulls
# ~353MB and installs a user service, so it stays a deliberate one-time step.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}/tts"
VENV="$SHARE/venv"
MODELS="$SHARE/models"
RELEASE="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"

# ---------------------------------------------------------------------------
# Hook merging.
#
# ~/.claude/settings.json and ~/.codex/config.toml hold live, machine-specific
# state -- on this machine including work paths that must never enter a public
# repo -- so the repo cannot own them as symlinks. The canonical fragments live
# in tts/ and are merged in here instead. Both merges key on something stable
# (the hook command for JSON, a marked block for TOML) so re-running this is a
# no-op rather than a second copy of every hook, both back the file up before
# touching it, and both parse the result before it is allowed to land.
# ---------------------------------------------------------------------------

# Adds one fragment event's hooks to whatever is already configured. A hook is
# identified by its command string: if that command is already present under
# the event, nothing is added, which is what makes re-running safe. An earlier
# version of this merge deduplicated one array and not the other, and grew a
# second Notification hook on every run. Existing entries are only ever
# appended to, never replaced.
JQ_MERGE_HOOKS='
def commands: [ .[]? | .hooks[]? | .command? | select(. != null) ];
def add_group($g):
  . as $cur
  | ($cur | commands) as $have
  | [ $g.hooks[]? | . as $h | select(($have | index($h.command)) == null) ] as $new
  | if ($new | length) == 0 then $cur
    else
      ([ $cur | to_entries[] | select((.value.matcher // "") == ($g.matcher // "")) ]
       | first) as $slot
      | if $slot == null then $cur + [ $g | .hooks = $new ]
        else $cur | .[$slot.key].hooks = ((.[$slot.key].hooks // []) + $new)
        end
    end;
$frag[0] as $f
| .hooks = (
    reduce ($f | keys_unsorted[]) as $event ((.hooks // {});
      .[$event] = ((.[$event] // []) | reduce $f[$event][] as $g (.; add_group($g)))))
'

# Every hook command in the file, in one flat list. Used to prove the merge
# added what it promised and dropped nothing that was already there.
JQ_ALL_COMMANDS='[ (.hooks // {}) | .[][]? | .hooks[]? | .command ] | length'

backup_file() {
    local file="$1" stamp
    stamp="$(date +%Y%m%d-%H%M%S)"
    cp -p "$file" "$file.bak-$stamp"
    echo "    backup: $file.bak-$stamp"
}

merge_claude_hooks() {
    local settings="$HOME/.claude/settings.json"
    local fragment="$REPO/tts/claude-hooks.json"
    local tmp="$settings.tts-merge.$$"
    local created=0

    mkdir -p "$(dirname "$settings")"
    if [ ! -f "$settings" ]; then
        echo '{}' >"$settings"
        created=1  # nothing to back up: there was no file a moment ago
    fi
    if ! jq -e 'type == "object"' "$settings" >/dev/null 2>&1; then
        echo "    SKIPPED: $settings is not a JSON object; fix it and re-run"
        return 0
    fi

    if ! jq --slurpfile frag "$fragment" "$JQ_MERGE_HOOKS" "$settings" >"$tmp"; then
        echo "    SKIPPED: could not merge $fragment; $settings left untouched"
        rm -f "$tmp"
        return 0
    fi

    # Land nothing that cannot be read back, that lost a hook the user already
    # had, or that somehow does not contain the hooks this was supposed to add.
    local before after
    before="$(jq "$JQ_ALL_COMMANDS" "$settings")"
    after="$(jq "$JQ_ALL_COMMANDS" "$tmp" 2>/dev/null || echo -1)"
    if [ "$after" -lt "$before" ]; then
        echo "    SKIPPED: merge would have dropped a hook; $settings left untouched"
        rm -f "$tmp"
        return 0
    fi
    if ! jq -e --slurpfile frag "$fragment" '
            . as $merged
            | all($frag[0] | to_entries[];
                  . as $event
                  | all($event.value[]?.hooks[]?.command;
                        . as $cmd
                        | ([ $merged.hooks[$event.key][]?.hooks[]?.command ]
                           | index($cmd)) != null))' "$tmp" >/dev/null 2>&1; then
        echo "    SKIPPED: merged settings did not contain the TTS hooks; $settings left untouched"
        rm -f "$tmp"
        return 0
    fi

    if cmp -s "$settings" "$tmp"; then
        rm -f "$tmp"
        echo "    ~/.claude/settings.json already has the TTS hooks; unchanged"
        return 0
    fi
    [ "$created" -eq 1 ] || backup_file "$settings"
    mv "$tmp" "$settings"
    if [ "$created" -eq 1 ]; then
        echo "    created ~/.claude/settings.json from tts/claude-hooks.json"
    else
        echo "    merged tts/claude-hooks.json into ~/.claude/settings.json"
    fi
}

merge_codex_hooks() {
    mkdir -p "$HOME/.codex"
    python3 - "$HOME/.codex/config.toml" "$REPO/tts/codex-hooks.toml" <<'PY'
"""Append (or refresh) the marked agent-tts block in ~/.codex/config.toml.

A marked block rather than a structural merge: TOML has no merge that
preserves comments and ordering, and the block's own markers make replacing a
previous copy exact. Nothing outside the markers is ever touched, so a hook
the user configured themselves survives untouched.
"""
import pathlib
import shutil
import sys
import time
import tomllib

config, fragment = (pathlib.Path(p) for p in sys.argv[1:3])
START, END = "# >>> agent-tts >>>", "# <<< agent-tts <<<"

block = fragment.read_text().strip("\n")
original = config.read_text() if config.exists() else ""


def fail(message):
    print(f"    SKIPPED: {message}; {config} left untouched")
    sys.exit(0)


def hook_counts(text):
    """How many hooks are configured per event, so a merge cannot lose one."""
    parsed = tomllib.loads(text)
    hooks = parsed.get("hooks")
    if not isinstance(hooks, dict):
        return {}
    return {k: len(v) for k, v in hooks.items() if isinstance(v, list)}


if original.strip():
    try:
        before = hook_counts(original)
    except tomllib.TOMLDecodeError as exc:
        fail(f"{config} does not parse ({exc})")
else:
    before = {}

if START in original and END in original:
    head, _, rest = original.partition(START)
    _, _, tail = rest.partition(END)
    candidate = f"{head}{block}{tail}"
else:
    separator = "" if not original or original.endswith("\n\n") else \
        ("\n" if original.endswith("\n") else "\n\n")
    candidate = f"{original}{separator}{block}\n"

try:
    after = hook_counts(candidate)
except tomllib.TOMLDecodeError as exc:
    fail(f"the merged config would not parse ({exc})")

for event, count in before.items():
    if after.get(event, 0) < count:
        fail(f"the merge would have dropped a {event} hook")

if candidate == original:
    print("    ~/.codex/config.toml already has the TTS hooks; unchanged")
    sys.exit(0)

if config.exists():
    backup = config.with_name(f"{config.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(config, backup)
    print(f"    backup: {backup}")
config.write_text(candidate)
verb = "refreshed" if START in original else "appended"
print(f"    {verb} the agent-tts block in ~/.codex/config.toml")
PY
}

# Sourcing with TTS_SETUP_LIB=1 defines the helpers above and stops, so the
# hook merges can be exercised against copies of real configs in a scratch
# HOME without building a venv or downloading 353MB of model.
if [ "${TTS_SETUP_LIB:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/"; exit 1; }
command -v paplay >/dev/null || { echo "paplay is required (pulseaudio-utils)"; exit 1; }
command -v jq >/dev/null || { echo "jq is required (apt install jq)"; exit 1; }

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

echo "==> Installing systemd user service"
mkdir -p "$HOME/.config/systemd/user"
ln -fs "$REPO/tts/tts.service" "$HOME/.config/systemd/user/tts.service"
systemctl --user daemon-reload
systemctl --user enable --now tts.service

echo "==> Wiring the agent hooks"
if [ "$REPO" != "$HOME/workspace/dotfiles" ]; then
    echo "    WARNING: this checkout is at $REPO, but the hook fragments and"
    echo "    tts/tts.service both hardcode ~/workspace/dotfiles. Nothing will"
    echo "    fire until those paths are corrected."
fi
merge_claude_hooks
merge_codex_hooks

echo "==> Waiting for the socket"
for _ in $(seq 1 30); do
  [ -S "${XDG_RUNTIME_DIR:-/run/user/$UID}/tts.sock" ] && break
  sleep 1
done

echo
echo "Done. Try:  tts say \"text to speech is working\""
echo "If Codex hooks were added, approve them once via /hooks in the Codex TUI."
