from tts.hooks.codex import message_from_payload


class TestStop:
    def test_stop_speaks_last_assistant_message(self):
        m = message_from_payload({
            "hook_event_name": "Stop",
            "last_assistant_message": "Refactored the parser.",
            "session_id": "abc",
        })
        assert m["text"] == "Refactored the parser."
        assert m["kind"] == "response"
        assert m["source"] == "codex"

    def test_stop_without_message_returns_none(self):
        assert message_from_payload({"hook_event_name": "Stop"}) is None

    def test_stop_with_blank_message_returns_none(self):
        assert message_from_payload(
            {"hook_event_name": "Stop", "last_assistant_message": "   "}
        ) is None


class TestPermissionRequest:
    def test_permission_is_announced(self):
        m = message_from_payload({
            "hook_event_name": "PermissionRequest",
            "reason": "run rm -rf build",
        })
        assert m["kind"] == "permission"
        assert "permission" in m["text"].lower()
        assert "rm" in m["text"]

    def test_permission_without_reason_still_speaks(self):
        m = message_from_payload({"hook_event_name": "PermissionRequest"})
        assert m["kind"] == "permission"
        assert m["text"]


class TestOtherEvents:
    def test_unhandled_event_returns_none(self):
        assert message_from_payload({"hook_event_name": "SessionStart"}) is None

    def test_missing_event_name_returns_none(self):
        assert message_from_payload({}) is None


class TestPayloadShapeHardening:
    """Codex's real payload shape was never observed live (Step 1 of the
    brief -- interactive TUI trust-by-hash -- isn't executable here). The
    only confirmed evidence is a list of field-name strings pulled from the
    codex-cli binary, with no confirmation of nesting. These tests cover
    shapes the supplied tests don't: a payload that's valid JSON but not an
    object, fields present but null or the wrong type, giant text, and
    unexpected event-name casing -- all of which must degrade to None/silence
    rather than raise.
    """

    def test_non_dict_payload_returns_none(self):
        assert message_from_payload([1, 2, 3]) is None  # type: ignore[arg-type]
        assert message_from_payload("Stop") is None  # type: ignore[arg-type]
        assert message_from_payload(None) is None  # type: ignore[arg-type]
        assert message_from_payload(42) is None  # type: ignore[arg-type]

    def test_stop_with_null_last_assistant_message_returns_none(self):
        assert message_from_payload({
            "hook_event_name": "Stop",
            "last_assistant_message": None,
        }) is None

    def test_stop_with_non_string_last_assistant_message_returns_none(self):
        assert message_from_payload({
            "hook_event_name": "Stop",
            "last_assistant_message": ["not", "a", "string"],
        }) is None
        assert message_from_payload({
            "hook_event_name": "Stop",
            "last_assistant_message": 12345,
        }) is None

    def test_permission_with_null_reason_still_speaks_generic(self):
        m = message_from_payload({
            "hook_event_name": "PermissionRequest",
            "reason": None,
        })
        assert m["kind"] == "permission"
        assert m["text"] == "Codex needs permission."

    def test_permission_with_non_string_reason_still_speaks_generic(self):
        m = message_from_payload({
            "hook_event_name": "PermissionRequest",
            "reason": ["run", "rm"],
        })
        assert m["text"] == "Codex needs permission."

    def test_permission_with_whitespace_reason_still_speaks_generic(self):
        m = message_from_payload({
            "hook_event_name": "PermissionRequest",
            "reason": "   \n\t  ",
        })
        assert m["text"] == "Codex needs permission."

    def test_event_name_non_string_returns_none(self):
        assert message_from_payload({"hook_event_name": 123}) is None
        assert message_from_payload({"hook_event_name": ["Stop"]}) is None
        assert message_from_payload({"hook_event_name": None}) is None

    def test_lowercase_event_name_is_not_recognized(self):
        """The event names confirmed present in the codex-cli binary are
        PascalCase ("Stop", "PermissionRequest", ...), matching a Rust enum
        serialized as-is. A differently-cased string is therefore an
        unrecognized event, not a variant to normalize -- 'prefer being
        silent over being wrong' means we don't guess at case-folding."""
        assert message_from_payload({
            "hook_event_name": "stop",
            "last_assistant_message": "hi",
        }) is None

    def test_uppercase_event_name_is_not_recognized(self):
        assert message_from_payload({
            "hook_event_name": "STOP",
            "last_assistant_message": "hi",
        }) is None
        assert message_from_payload({
            "hook_event_name": "PERMISSIONREQUEST",
            "reason": "x",
        }) is None

    def test_huge_reason_does_not_crash(self):
        big = "word " * 200_000  # ~1MB
        m = message_from_payload({
            "hook_event_name": "PermissionRequest",
            "reason": big,
        })
        assert m is not None
        assert m["kind"] == "permission"
        assert big.strip() in m["text"]

    def test_huge_last_assistant_message_does_not_crash(self):
        big = "word " * 200_000
        m = message_from_payload({
            "hook_event_name": "Stop",
            "last_assistant_message": big,
        })
        assert m["text"] == big.strip()

    def test_field_nested_one_level_deep_is_still_found(self):
        """Step 1's live capture couldn't run, so the payload's nesting is
        unconfirmed. If Codex wraps the fields this adapter expects inside
        some sub-object rather than putting them at the payload root, this
        adapter should still find them one level down rather than silently
        dropping every event."""
        m = message_from_payload({
            "wrapper": {
                "hook_event_name": "Stop",
                "last_assistant_message": "nested text",
                "session_id": "nested-session",
            }
        })
        assert m is not None
        assert m["text"] == "nested text"
        assert m["session"] == "nested-session"

    def test_field_nested_one_level_deep_for_permission_request(self):
        m = message_from_payload({
            "data": {
                "hook_event_name": "PermissionRequest",
                "reason": "run rm -rf build",
            }
        })
        assert m is not None
        assert m["kind"] == "permission"
        assert "rm" in m["text"]

    def test_root_field_takes_precedence_over_nested(self):
        m = message_from_payload({
            "hook_event_name": "Stop",
            "last_assistant_message": "root wins",
            "nested": {"last_assistant_message": "nested loses"},
        })
        assert m["text"] == "root wins"

    def test_carries_session_and_cwd_through(self):
        m = message_from_payload({
            "hook_event_name": "Stop",
            "last_assistant_message": "hello",
            "session_id": "abc-123",
            "cwd": "/home/marwan/workspace/dotfiles",
        })
        assert m["session"] == "abc-123"
        assert m["cwd"] == "/home/marwan/workspace/dotfiles"

    def test_missing_session_and_cwd_are_none(self):
        m = message_from_payload({
            "hook_event_name": "Stop",
            "last_assistant_message": "hello",
        })
        assert m["session"] is None
        assert m["cwd"] is None


class TestRealPayloadShape:
    """codex-cli 0.151.0's own JSON Schema fixtures (fetched from the
    openai/codex repo at tag rust-v0.151.0, matching `codex --version` on
    this machine exactly) are authoritative for this version: both
    stop.command.input.schema.json and permission-request.command.input.schema.json
    set `additionalProperties: false` and list every key below as
    `required`. These tests use the exact real field sets rather than the
    brief's assumed shape, and in particular confirm the PermissionRequest
    handling that matters in practice: there is no `reason` field on the
    real payload, so the message must be built from `tool_name` instead."""

    def test_stop_with_full_real_field_set(self):
        m = message_from_payload({
            "session_id": "0199-real-session",
            "turn_id": "turn-7",
            "cwd": "/home/marwan/workspace/dotfiles",
            "hook_event_name": "Stop",
            "model": "gpt-5.6-terra",
            "permission_mode": "default",
            "stop_hook_active": False,
            "transcript_path": "/home/marwan/.codex/sessions/2026/09/01/rollout.jsonl",
            "last_assistant_message": "Refactored the parser.",
        })
        assert m["text"] == "Refactored the parser."
        assert m["kind"] == "response"
        assert m["source"] == "codex"
        assert m["session"] == "0199-real-session"
        assert m["cwd"] == "/home/marwan/workspace/dotfiles"

    def test_permission_request_with_full_real_field_set_has_no_reason_key(self):
        """The real schema has no "reason" property at all -- this payload
        omits it entirely (not null, not empty: absent), matching what
        codex-cli 0.151.0 actually sends."""
        m = message_from_payload({
            "session_id": "0199-real-session",
            "turn_id": "turn-7",
            "cwd": "/home/marwan/workspace/dotfiles",
            "hook_event_name": "PermissionRequest",
            "model": "gpt-5.6-terra",
            "permission_mode": "default",
            "tool_name": "shell",
            "tool_input": {"command": ["bash", "-lc", "rm -rf build"]},
            "transcript_path": "/home/marwan/.codex/sessions/2026/09/01/rollout.jsonl",
        })
        assert m is not None
        assert m["kind"] == "permission"
        assert m["text"] == "Codex needs permission to use shell."

    def test_permission_prefers_reason_when_both_reason_and_tool_name_present(self):
        """reason is not part of the real schema, but if some future/other
        version does send both, an explicit reason should still win over the
        generic tool_name phrasing -- it's the more specific signal."""
        m = message_from_payload({
            "hook_event_name": "PermissionRequest",
            "reason": "run rm -rf build",
            "tool_name": "shell",
        })
        assert m["text"] == "Codex needs permission: run rm -rf build"

    def test_permission_falls_back_to_tool_name_when_reason_absent(self):
        m = message_from_payload({
            "hook_event_name": "PermissionRequest",
            "tool_name": "apply_patch",
        })
        assert m["text"] == "Codex needs permission to use apply_patch."

    def test_permission_with_non_string_tool_name_falls_back_to_generic(self):
        m = message_from_payload({
            "hook_event_name": "PermissionRequest",
            "tool_name": 12345,
        })
        assert m["text"] == "Codex needs permission."

    def test_permission_with_blank_tool_name_falls_back_to_generic(self):
        m = message_from_payload({
            "hook_event_name": "PermissionRequest",
            "tool_name": "   ",
        })
        assert m["text"] == "Codex needs permission."


class TestMainNeverRaises:
    def test_main_exits_zero_on_garbage_stdin(self, monkeypatch):
        import io
        import sys
        from tts.hooks import codex as codex_mod

        monkeypatch.setattr(sys, "stdin", io.StringIO("not json at all"))
        assert codex_mod.main() == 0

    def test_main_exits_zero_on_valid_json_non_object(self, monkeypatch):
        import io
        import sys
        from tts.hooks import codex as codex_mod

        monkeypatch.setattr(sys, "stdin", io.StringIO("[1, 2, 3]"))
        assert codex_mod.main() == 0

    def test_main_exits_zero_when_stdin_read_raises_oserror(self, monkeypatch):
        """json.load(sys.stdin) calls sys.stdin.read() internally, so a
        stdin that raises OSError (broken pipe, bad fd, EIO -- all plausible
        if a dispatcher tears down the hook's stdin mid-read) must not
        escape main() as an uncaught exception. Task 6 found and fixed this
        exact gap in the Claude adapter; this adapter must not reproduce
        it."""
        import sys
        from tts.hooks import codex as codex_mod

        class ExplodingStdin:
            def read(self, *a, **k):
                raise OSError("broken pipe")

        monkeypatch.setattr(sys, "stdin", ExplodingStdin())
        assert codex_mod.main() == 0

    def test_main_exits_zero_when_helper_raises(self, monkeypatch):
        """Defense in depth: even if a future change reintroduces a bug in
        message_from_payload, main() must still exit 0 rather than crash."""
        import io
        import sys
        from tts.hooks import codex as codex_mod

        def boom(_payload):
            raise RuntimeError("unexpected shape")

        monkeypatch.setattr(codex_mod, "message_from_payload", boom)
        monkeypatch.setattr(sys, "stdin", io.StringIO('{"hook_event_name": "Stop"}'))
        assert codex_mod.main() == 0

    def test_main_does_not_send_when_daemon_unreachable(self, monkeypatch):
        """send() failing (no daemon, no systemd) must not raise out of
        main()."""
        import io
        import json
        import sys
        from tts.hooks import codex as codex_mod

        payload = json.dumps({
            "hook_event_name": "Stop",
            "last_assistant_message": "hello there",
        })
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        monkeypatch.setattr(
            codex_mod, "send",
            lambda *a, **k: (_ for _ in ()).throw(OSError("no daemon")),
        )
        # send() itself never raises in practice (client.py swallows
        # OSError), but main()'s own try/except must still hold even if
        # that changes.
        assert codex_mod.main() == 0
