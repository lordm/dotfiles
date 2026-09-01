"""Filesystem paths shared by the daemon, the CLI client, and hook adapters.

Deliberately stdlib-only. tts/client.py -- imported by the CLI and by both
hook adapters, all of which run under the ambient system interpreter rather
than the isolated venv scripts/setup-tts.sh builds -- needs socket_path()
without pulling in tts.ttsd, which imports tts.engine, which imports numpy
at module scope. numpy lives only in the venv; an ambient interpreter that
lacks it must still be able to resolve the socket path and fail silently
past that point, not crash on an unrelated import.
"""

from __future__ import annotations

import os
from pathlib import Path


def share_dir() -> Path:
    """Where per-user state lives.

    Mirrors tts.engine._compute_model_dir() and scripts/setup-tts.sh so the
    bootstrap, the engine and the daemon never disagree about $XDG_DATA_HOME.
    The `or` (rather than a dict default) matters: XDG_DATA_HOME set to an
    empty string is common in stripped environments, and Path("") is ".".
    """
    return Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local/share")) / "tts"


def socket_path() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime) / "tts.sock"
