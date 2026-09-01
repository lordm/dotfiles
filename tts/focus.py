"""Decide whether an event came from the pane the user is actually looking at.

Terminal window focus is deliberately not consulted. GNOME under Wayland has no
reliable unprivileged query for it, and the point of narration is to reach
someone who has walked away from the screen.
"""

from __future__ import annotations

import subprocess
from typing import Callable

_FORMAT = "#{pane_active},#{window_active},#{session_attached}"

PaneQuery = Callable[[str], "str | None"]


def tmux_query(pane_id: str) -> str | None:
    """Ask tmux about a pane. Returns None if tmux or the pane is gone."""
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "-t", pane_id, _FORMAT],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def is_focused(pane_id: str | None, query: PaneQuery = tmux_query) -> bool:
    """True when this pane should speak.

    No pane id means the agent is not running under tmux at all — the desktop
    app, an editor integration, a bare terminal. Those always speak, because
    staying silent there would look like the feature is broken.
    """
    if not pane_id:
        return True

    response = query(pane_id)
    if not response:
        return False

    parts = response.split(",")
    if len(parts) != 3:
        return False

    try:
        pane_active, window_active, session_attached = (int(p) for p in parts)
    except ValueError:
        return False

    return bool(pane_active) and bool(window_active) and session_attached >= 1
