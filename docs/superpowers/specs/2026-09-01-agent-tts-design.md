# Agent TTS — Design

**Date:** 2026-09-01
**Status:** Approved, pending implementation plan

## Purpose

Speak Claude Code and Codex output aloud so work can continue away from the
terminal. Two things get narrated: the agent's full response when a turn ends,
and approval prompts when an agent is blocked waiting for permission.

Only the session being worked in speaks. Every other session falls back to the
existing `notify-send` desktop notification, so a background agent still reaches
the user without two agents talking over each other.

## Non-goals

- Speech input. This is output only.
- Narrating subagent completions. With agent teams enabled this would be
  constant chatter.
- LLM-generated spoken summaries. Text cleanup is deterministic and offline.
- Cloud TTS. Nothing narrated leaves the machine.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Engine | Kokoro (82M) | Best open-weights prosody; quality matters when narrating paragraphs, not just alerts |
| Runtime | `kokoro-onnx` + `onnxruntime` on CPU | Same weights as the PyTorch package with none of the 2.5 GB CUDA stack, and no VRAM held on a 6 GB card used for other work |
| Topology | Warm daemon, thin hook clients | Model load is seconds; paying it per utterance would make alerts arrive after they were useful |
| Latency hiding | Sentence-level streaming | i7-9750H synthesizes at roughly 0.3–0.5x realtime, so first audio lands well under a second even though a full response takes longer |
| Concurrency | Focused session only | Chosen over queueing and over newest-wins interruption |
| Text prep | Deterministic transforms + length cap | No model call, no latency, no API key |

Rejected: one-shot synthesis per event (4–8 s lag before every utterance);
PyTorch Kokoro on the GPU (heaviest dependency in the repo, permanent VRAM cost,
version-matching maintenance on driver upgrades, no perceptible gain once
streaming hides latency).

## Architecture

```
Claude Code ──Stop/Notification──┐
                                 ├─► hook adapter ─► $XDG_RUNTIME_DIR/tts.sock ─► ttsd ─► paplay
Codex ──Stop/PermissionRequest───┘   (exits in ms)                                 │
                                                                                   └─► notify-send (unfocused)
```

Hooks never block the agent: an adapter reads its stdin payload, extracts text,
writes one JSON line to the socket, and exits. All synthesis, queueing, playback,
and focus arbitration happen in the daemon.

### Repository layout

New top-level `tts/`, matching the existing per-tool convention (`nvim/`,
`ghostty/`, `pipewire/`).

| Path | Role |
|---|---|
| `tts/ttsd.py` | Daemon: model, playback queue, socket server |
| `tts/speech.py` | Response text to speakable text. Pure functions |
| `tts/focus.py` | tmux focus arbitration. Pure functions |
| `tts/tts` | CLI client: `say`, `stop`, `toggle`, `status` |
| `tts/hooks/claude.py` | Claude Code stdin-JSON adapter |
| `tts/hooks/codex.py` | Codex stdin-JSON adapter |
| `tts/claude-hooks.json` | Version-controlled Claude settings fragment |
| `tts/codex-hooks.toml` | Version-controlled Codex config fragment |
| `tts/config.toml` | Voice, speed, length cap, per-event enable flags |
| `tts/tests/` | pytest suite |
| `scripts/setup-tts.sh` | venv, model download, systemd unit. Idempotent |

Runtime state lives outside the repo in `~/.local/share/tts/`: `venv/`,
`models/kokoro-v1.0.onnx`, `models/voices-v1.0.bin`, and `muted` (a flag file).

The daemon reads `~/.config/tts/config.toml`, which `install.sh` symlinks from
`tts/config.toml` in the repo. Defaults: voice `af_heart`, speed `1.15`, length
cap 45 s, all wired events enabled. Every value is overridable there without
touching code, and the file is version-controlled like the rest of the repo.

## Daemon

Listens on a Unix socket at `$XDG_RUNTIME_DIR/tts.sock`, falling back to
`/run/user/$UID/tts.sock`. Protocol is newline-delimited JSON, one message per
line, no response body expected.

Utterance message:

```json
{"text": "...", "source": "claude|codex", "kind": "response|permission",
 "pane": "%12", "session": "<id>", "cwd": "/home/marwan/..."}
```

Command messages: `{"cmd": "stop"}`, `{"cmd": "toggle"}`, `{"cmd": "status"}`.

Two threads. The synthesis thread splits cleaned text into sentences, runs each
through Kokoro, and pushes PCM chunks onto a queue. The playback thread streams
that queue into a `paplay --raw --rate=24000 --format=s16le --channels=1`
subprocess. Interruption is killing the subprocess and draining the queue —
this is what makes `tts stop` instant regardless of how much text is pending.

A new utterance cancels any in-flight one. Because only the focused session
speaks, this arises between consecutive turns rather than between sessions.

Lifecycle is a systemd user service with `Restart=on-failure`, started at login.
The CLI client starts it via `systemctl --user start tts.service` if the socket
is absent. Idle cost is roughly 600 MB resident and zero CPU; the model is not
unloaded when idle.

## Event wiring

### Claude Code (`~/.claude/settings.json`)

| Event | Behavior |
|---|---|
| `Stop` | Narrate the final assistant response |
| `Notification` | Speak the payload's `message` field; covers permission requests and idle prompts |
| `SubagentStop` | Not wired — deliberate |

The `Stop` payload provides `transcript_path`. The adapter reads the last
assistant message from that JSONL, taking `.message.content[]` entries of type
`text`. This extraction was verified against real transcripts in
`~/.claude/projects/`.

The existing `notify-send` Notification hook stays in place alongside the new one.

### Codex (`~/.codex/config.toml`)

| Event | Behavior |
|---|---|
| `[[hooks.Stop]]` | Narrate `last_assistant_message` from the payload |
| `[[hooks.PermissionRequest]]` | Speak the approval request |

Codex supplies `last_assistant_message` directly in the hook payload, so no
transcript parsing is needed on this side. Both event names were confirmed
present in the codex-cli 0.151.0 binary, alongside `session_id`,
`transcript_path`, `hook_event_name`, and `permission_mode`.

Codex requires trusting hooks by content hash. After install, the hooks must be
approved once via `/hooks` in the Codex TUI before they fire.

## Focus arbitration

Speak when the originating pane is the active pane of an attached tmux client;
otherwise emit `notify-send` and stay silent.

The hook adapter reads `$TMUX_PANE`, inherited from the agent process, and passes
it to the daemon. The daemon evaluates:

```
tmux display-message -p -t "$pane" '#{pane_active},#{window_active},#{session_attached}'
```

Speak iff `pane_active == 1 && window_active == 1 && session_attached >= 1`.

When `$TMUX_PANE` is absent — agent started outside tmux, desktop app, editor
integration — treat the session as focused and speak. This keeps behavior
predictable rather than silently swallowing output in non-tmux contexts.

**Deliberate limitation.** Terminal window focus is not checked. GNOME under
Wayland offers no reliable unprivileged query for which window has focus, and
the primary use case is walking away from the machine entirely. Consequence:
alt-tabbing from Ghostty to a browser leaves the tmux pane active, so narration
continues. This is intended.

## Text pipeline

Ordered transforms in `speech.py`, each a pure function over a string:

1. Fenced code blocks → `"code block, N lines"`
2. Inline code → contents if ≤3 words, else `"snippet"`
3. Markdown links `[text](url)` → `text`; bare URLs → `"a link"`
4. Filesystem paths → basename (`/home/marwan/workspace/dotfiles/scripts/foo.sh` → `foo.sh`)
5. Heading markers stripped
6. Emphasis markers (`**`, `*`, `_`) stripped
7. Tables → `"a table with N rows"`
8. List markers dropped, items joined with sentence pauses
9. Whitespace collapsed

Then a length cap. Duration is estimated by word count at roughly 160 wpm — no
trial synthesis — and text is truncated at the last sentence boundary under
~45 s (about 120 words), closing with `"continues on screen"`.

## Control surface

| Command | Effect |
|---|---|
| `tts stop` | Silence immediately, drop pending |
| `tts toggle` | Persistent mute, survives restarts via the flag file |
| `tts say "..."` | Manual synthesis, for testing |
| `tts status` | Daemon running, muted state, queue depth |

`install.sh` symlinks `tts/tts` to `~/.local/bin/tts`, which is already on
PATH. It is additionally bound to a tmux prefix key, so silencing never
requires leaving the current pane.

## Install

`scripts/setup-tts.sh` is idempotent and safe to re-run. It creates the `uv`
venv, installs `kokoro-onnx` and `soundfile`, downloads the model and voice
files (~350 MB) into `~/.local/share/tts/models/`, and installs plus enables the
systemd user unit.

`install.sh` only symlinks `tts/` to `~/.config/tts` and exposes the setup
script. It does not run it — following the `setup-hibernate.sh` precedent, since
this is a large download and a one-time system change.

`~/.claude/settings.json` and `~/.codex/config.toml` hold live, machine-specific
state and are poor symlink targets. `setup-tts.sh` instead merges the repo's
fragments into them — `jq` for the JSON, an idempotent marked-block append for
the TOML — backing up each file first. The canonical fragments stay
version-controlled in the repo without the repo owning those files.

espeak-ng, already installed system-wide, provides Kokoro's phoneme fallback for
out-of-vocabulary words. No additional system package is required.

## Testing

`speech.py` and `focus.py` are pure functions and are developed test-first, with
table-driven cases per transform: code blocks of varying length, nested inline
code, paths with and without spaces, malformed markdown, text at and just over
the length cap, and empty or whitespace-only responses.

The daemon is tested through an integration harness that substitutes a stub
synthesizer recording utterances instead of producing audio, covering
interruption, mute, unfocused fallback, and socket reconnection after a restart.

Hook adapters are tested by piping recorded payload fixtures — one per event,
per harness — through them and asserting the socket message produced.

Manual smoke test after install: `tts say "hello"`.

## Open risks

**`$TMUX_PANE` propagation — RESOLVED 2026-09-01.** Verified empirically in a
throwaway detached tmux session: the variable survives two levels of subprocess
nesting (pane shell to agent to hook), so the primary focus mechanism stands and
no `list-panes` correlation fallback is needed.

The same investigation surfaced a case the design had treated as marginal: this
machine also runs Claude Code under `claude-desktop`, entirely outside tmux.
That is a routine path, not an edge case. The specified behavior (absent
`$TMUX_PANE` means treat as focused and speak) covers it correctly, but it
means desktop-app sessions always narrate regardless of what tmux is doing.

**Model artifacts — VERIFIED.** `kokoro-v1.0.onnx` (325 MB) and
`voices-v1.0.bin` (28 MB) both resolve HTTP 200 from the kokoro-onnx
`model-files-v1.0` release. `kokoro-onnx` 0.6.1 supports Python >=3.10,<3.14 and
`onnxruntime` 1.29.0 requires >=3.11; the system Python is 3.12.9, so both are
satisfied.

**Synthesis throughput.** The 0.3–0.5x realtime estimate for this CPU is from
published benchmarks, not measured here. If actual throughput is worse, sentence
streaming still delivers fast first audio but long responses could fall behind.
Mitigation if needed: lower the length cap, or reduce onnxruntime thread count
contention.

**Codex hook payload field names.** Confirmed present as strings in the binary,
but exact nesting is unverified. Adapters will be built against a recorded live
payload rather than assumption.
