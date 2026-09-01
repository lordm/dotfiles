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

from tts.ttsd import socket_path

# How long a single connect/send/recv attempt may take before it counts as
# failed. UNIX domain socket connects don't really "hang" -- they fail
# immediately if nothing is listening -- so this mostly bounds the status
# path's wait for a reply.
_SEND_TIMEOUT = 3.0

# How long to keep retrying the socket after a successful autostart request,
# and how often. Importing kokoro_onnx and building the ONNX session costs a
# couple of seconds on its own (see tts/engine.py), so the daemon's socket
# is not necessarily bound by the time `systemctl start` returns -- that call
# only waits for the process to fork, not for it to finish initializing. This
# window is paid at most once per cold start: once the daemon is up, every
# later send() connects on the first try and returns immediately.
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
    """Ask systemd to start the daemon.

    Returns whether the request was accepted, not whether the daemon is
    actually up yet -- send() polls the socket separately for that. A
    missing `systemctl`, a missing unit, or a unit stuck failed/start-limited
    all report False here so the caller does not waste time polling a socket
    that has no prospect of appearing.
    """
    try:
        result = subprocess.run(
            ["systemctl", "--user", "start", "tts.service"],
            timeout=10,
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


def send(message: dict, path: Path | None = None, autostart: bool = True) -> str | None:
    path = path or socket_path()
    ok, reply = _try_send(message, path)
    if ok:
        return reply
    if not autostart:
        return None
    if not _autostart():
        return None  # systemd or the unit itself is unavailable; nothing to wait for
    deadline = time.monotonic() + _AUTOSTART_WAIT
    while time.monotonic() < deadline:
        time.sleep(_AUTOSTART_POLL)
        ok, reply = _try_send(message, path)
        if ok:
            return reply
    return None
