"""Talk to the daemon. Used by the CLI and by both hook adapters.

Every failure path here is silent by design: a broken TTS setup must never
make an agent's hook fail or slow a turn down.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path

from tts.paths import socket_path

# How long a single connect/send/recv attempt may take before it counts as
# failed. UNIX domain socket connects don't really "hang" -- they fail
# immediately if nothing is listening -- so this mostly bounds the status
# path's wait for a reply.
_SEND_TIMEOUT = 3.0

# Backstop for the `systemctl start --no-block` call itself. --no-block means
# systemctl enqueues the start job and returns without waiting for it to
# finish, so this normally resolves in milliseconds; the timeout only guards
# against a wedged systemd/dbus, not against a slow-starting daemon.
_AUTOSTART_TIMEOUT = 3.0

# How long send(..., wait=True) may poll for the socket after a successful
# autostart request, and how often. Importing kokoro_onnx and building the
# ONNX session costs a couple of seconds on its own (see tts/engine.py), so
# the daemon's socket is not necessarily bound by the time `systemctl start
# --no-block` returns -- that call doesn't wait for the daemon to finish
# initializing, only for the job to be enqueued. wait=True exists only for
# the interactive CLI (tts/tts); hook adapters must never pass it, because a
# turn cannot afford to be blocked for this long.
_AUTOSTART_WAIT = 5.0
_AUTOSTART_POLL = 0.2


def build_message(verb: str, text: str | None, source: str = "cli",
                  kind: str = "response") -> dict:
    if verb in ("stop", "toggle", "status"):
        return {"cmd": verb}
    return {
        "text": text or "",
        "pane": os.environ.get("TMUX_PANE") or None,
        "source": source,
        "kind": kind,
    }


def _autostart() -> bool:
    """Ask systemd to start the daemon, without waiting for it to come up.

    `--no-block` makes this return as soon as the start job is enqueued,
    not once the daemon has finished loading the model and bound its
    socket -- that would defeat the point of a non-blocking default. The
    return value is whether the request was accepted, not whether the
    daemon is actually up yet. A missing `systemctl`, a missing unit, or a
    unit stuck failed/start-limited all report False here so the caller
    does not bother retrying a socket that has no prospect of appearing.
    """
    try:
        result = subprocess.run(
            ["systemctl", "--user", "start", "--no-block", "tts.service"],
            timeout=_AUTOSTART_TIMEOUT,
            capture_output=True,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _try_send(message: dict, path: Path) -> tuple[bool, str | None]:
    """One connection attempt. Returns (delivered, reply)."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(_SEND_TIMEOUT)
            s.connect(str(path))
            s.sendall((json.dumps(message) + "\n").encode())
            if message.get("cmd") == "status":
                try:
                    # We have nothing further to send; telling the daemon so
                    # lets its read loop notice EOF instead of waiting out
                    # its idle timeout, so it frees the connection promptly.
                    s.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                return True, s.recv(65536).decode().strip()
            return True, None
    except (OSError, socket.timeout):
        return False, None


def send(message: dict, path: Path | None = None, autostart: bool = True,
         wait: bool = False) -> str | None:
    """Deliver one message to the daemon.

    Non-blocking by default: on a cold daemon this requests autostart and
    retries exactly once, immediately, then gives up. That is the only mode
    hook adapters may use -- a hook cannot afford to sit through the couple
    of seconds a cold start takes, and losing one narration on a cold start
    (which only happens on first install or after a crash; the daemon is
    otherwise a systemd service already running by login) is the correct
    trade against ever stalling a turn.

    wait=True additionally polls for up to _AUTOSTART_WAIT seconds after a
    successful autostart request, so the interactive CLI can actually wait
    out a cold start instead of silently dropping the first command. Pass it
    only from tts/tts, never from a hook adapter.
    """
    path = path or socket_path()
    ok, reply = _try_send(message, path)
    if ok:
        return reply
    if not autostart:
        return None
    if not _autostart():
        return None  # systemd or the unit itself is unavailable; nothing to wait for

    ok, reply = _try_send(message, path)
    if ok:
        return reply
    if not wait:
        return None

    deadline = time.monotonic() + _AUTOSTART_WAIT
    while time.monotonic() < deadline:
        time.sleep(_AUTOSTART_POLL)
        ok, reply = _try_send(message, path)
        if ok:
            return reply
    return None
