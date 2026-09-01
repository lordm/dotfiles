#!/usr/bin/env python3
"""Codex hook adapter.

Codex supplies the response text in the payload, so unlike the Claude
adapter this one never reads a transcript.

Codex's real payload shape could not be captured live for this adapter --
that requires interactive trust-by-hash approval in the Codex TUI, which
this environment cannot drive. Instead it was reconstructed from the
codex-cli 0.151.0 open-source tree (openai/codex, tag rust-v0.151.0, which
`codex --version` on this machine confirms matches the installed binary
exactly) and its machine-generated JSON Schema fixtures
(codex-rs/hooks/schema/generated/{stop,permission-request}.command.input.schema.json).
Those schemas set `additionalProperties: false` and list every field as
`required`, so for this exact version the payload is confirmed flat with no
optional/omitted keys:

  Stop:              cwd, hook_event_name, last_assistant_message, model,
                      permission_mode, session_id, stop_hook_active,
                      transcript_path, turn_id
  PermissionRequest:  cwd, hook_event_name, model, permission_mode,
                      session_id, tool_input, tool_name, transcript_path,
                      turn_id (+ optional agent_id/agent_type when running
                      inside a subagent)

Notably there is no "reason" field on PermissionRequest -- an earlier
"confirmed fields" list (pulled from strings embedded in the compiled
binary rather than from source) turned out to conflate this *input* schema
with the *output* schema hooks may optionally return on stdout (several of
those output structs do have a `reason` field, for a hook that wants to
block/deny). `tool_name` is what actually identifies the pending action and
is always present per the schema's `required` list, so this adapter treats
it as the primary signal. `reason` is checked only as a fallback for when
`tool_name` is absent -- e.g. a differently-shaped payload from some other
Codex build -- and never overrides a `tool_name` that's actually there.

Despite that confidence, a live payload was still never observed, so every
lookup goes through _field(), which also checks one level into any
dict-valued sibling before giving up, and main() never assumes the payload
is well-formed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tts.client import build_message, send


def _field(payload: dict, name: str):
    """Look up a field, tolerant of the payload nesting it one level deep.

    The common -- and, per the schema evidence in the module docstring,
    confirmed -- case is payload[name] directly. This also checks one level
    into any dict-valued sibling before giving up, as a hedge against a live
    payload turning out to disagree with that evidence in some way this
    adapter never got to observe directly, rather than dropping every event
    silently on a shape guess that turned out wrong.
    """
    if name in payload:
        return payload[name]
    for value in payload.values():
        if isinstance(value, dict) and name in value:
            return value[name]
    return None


def message_from_payload(payload: dict) -> dict | None:
    if not isinstance(payload, dict):
        return None

    event = _field(payload, "hook_event_name")
    if not isinstance(event, str):
        return None

    if event == "Stop":
        raw = _field(payload, "last_assistant_message")
        text = raw.strip() if isinstance(raw, str) else ""
        kind = "response"
    elif event == "PermissionRequest":
        # tool_name is the guaranteed field (see module docstring: it's
        # `required` in codex-cli 0.151.0's own JSON Schema, and "reason"
        # isn't a property of this payload at all), so it's the primary
        # signal. "reason" is only consulted as a fallback when tool_name
        # is absent -- e.g. a differently-shaped payload from some other
        # Codex build -- and never overrides a tool_name that's present.
        raw_tool = _field(payload, "tool_name")
        tool_name = raw_tool.strip() if isinstance(raw_tool, str) else ""
        if tool_name:
            text = f"Codex needs permission to use {tool_name}."
        else:
            raw_reason = _field(payload, "reason")
            reason = raw_reason.strip() if isinstance(raw_reason, str) else ""
            text = f"Codex needs permission: {reason}" if reason else "Codex needs permission."
        kind = "permission"
    else:
        return None

    if not text:
        return None

    message = build_message("say", text, source="codex", kind=kind)
    message["session"] = _field(payload, "session_id")
    message["cwd"] = _field(payload, "cwd")
    return message


def main() -> int:
    # One try around the whole body, not split across json.load() and the
    # rest: json.load() calls sys.stdin.read() internally, and that can
    # raise OSError (broken pipe, bad fd, EIO) just as easily as
    # json.JSONDecodeError -- a narrower catch here would let a dispatcher
    # tearing down the hook's stdin mid-read escape as an uncaught
    # exception, exactly the "exit 0 on every failure path" promise this
    # module makes (and the bug Task 6 found and fixed in the sibling
    # Claude adapter).
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
