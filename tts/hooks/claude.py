#!/usr/bin/env python3
"""Claude Code hook adapter.

Reads the hook payload on stdin, extracts what should be spoken, hands it to
the daemon and exits. Never blocks, never fails loudly: a hook that errors
would surface as noise in every single turn.

Every parsing step below assumes nothing about the shape of its input: the
payload comes from Claude Code's hook machinery and the transcript is a
JSONL file written by a separate process, so either can in principle be
malformed, truncated, or simply not what today's Claude Code happens to
emit. Each helper degrades to "" / None on a shape it doesn't recognize
rather than raising, and main() adds one more layer of defense on top of
that so a bug in a helper still can't turn into a nonzero exit or a
traceback on stderr.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tts.client import build_message, send


def last_assistant_text(transcript_path: str) -> str:
    """Pull the final assistant text turn out of a Claude Code transcript.

    transcript_path is attacker/bug-shaped input in principle (it comes
    straight from the hook payload), so this never assumes it's even a
    string before handing it to Path() -- Path(None) or Path(123) raise
    TypeError, not OSError, and that would otherwise escape the except
    below.
    """
    if not isinstance(transcript_path, str) or not transcript_path:
        return ""

    try:
        lines = Path(transcript_path).read_text(errors="replace").splitlines()
    except OSError:
        return ""

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue  # a line can be valid JSON without being a JSON object
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue  # message: null / a bare string / etc. -- not a turn we understand
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        blocks = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        text = " ".join(t for t in blocks if isinstance(t, str) and t.strip()).strip()
        if text:
            return text
    return ""


def message_from_payload(payload: dict) -> dict | None:
    if not isinstance(payload, dict):
        return None

    event = payload.get("hook_event_name")

    if event == "Stop":
        text = last_assistant_text(payload.get("transcript_path", ""))
        kind = "response"
    elif event == "Notification":
        raw = payload.get("message")
        text = raw.strip() if isinstance(raw, str) else ""
        kind = "permission"
    else:
        return None

    if not text:
        return None

    message = build_message("say", text, source="claude", kind=kind)
    message["session"] = payload.get("session_id")
    message["cwd"] = payload.get("cwd")
    return message


def main() -> int:
    # One try around the whole body, not one around json.load() and a second
    # around the rest: json.load() calls sys.stdin.read() internally, and
    # that can raise OSError (broken pipe, bad fd, EIO) just as easily as
    # json.JSONDecodeError -- a narrower catch here would let a dispatcher
    # tearing down the hook's stdin mid-read escape as an uncaught exception,
    # exactly the "exit 0 on every failure path" promise this module makes.
    try:
        payload = json.load(sys.stdin)
        message = message_from_payload(payload)
        if message:
            send(message)
    except Exception:  # noqa: BLE001 - a hook must exit 0 even on a bug we didn't anticipate
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
