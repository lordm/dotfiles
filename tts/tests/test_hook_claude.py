import json
import sys

from tts.hooks.claude import last_assistant_text, message_from_payload


def write_transcript(tmp_path, entries):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries))
    return str(p)


def assistant(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


class TestTranscriptExtraction:
    def test_reads_last_assistant_text(self, tmp_path):
        path = write_transcript(tmp_path, [
            assistant("older"),
            {"type": "user", "message": {"content": "hi"}},
            assistant("newest"),
        ])
        assert last_assistant_text(path) == "newest"

    def test_joins_multiple_text_blocks(self, tmp_path):
        path = write_transcript(tmp_path, [{
            "type": "assistant",
            "message": {"content": [
                {"type": "text", "text": "one"},
                {"type": "thinking", "thinking": "ignored"},
                {"type": "text", "text": "two"},
            ]},
        }])
        assert last_assistant_text(path) == "one two"

    def test_tool_only_turn_yields_empty(self, tmp_path):
        path = write_transcript(tmp_path, [{
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]},
        }])
        assert last_assistant_text(path) == ""

    def test_missing_file_yields_empty(self):
        assert last_assistant_text("/nonexistent/x.jsonl") == ""

    def test_malformed_line_is_skipped(self, tmp_path):
        p = tmp_path / "t.jsonl"
        p.write_text("not json\n" + json.dumps(assistant("good")))
        assert last_assistant_text(str(p)) == "good"


class TestPayloadRouting:
    def test_stop_reads_transcript(self, tmp_path):
        path = write_transcript(tmp_path, [assistant("done here")])
        m = message_from_payload({"hook_event_name": "Stop", "transcript_path": path})
        assert m["text"] == "done here"
        assert m["kind"] == "response"
        assert m["source"] == "claude"

    def test_notification_uses_message_field(self):
        m = message_from_payload({
            "hook_event_name": "Notification",
            "message": "Claude needs your permission to use Bash",
        })
        assert m["text"] == "Claude needs your permission to use Bash"
        assert m["kind"] == "permission"

    def test_unhandled_event_returns_none(self):
        assert message_from_payload({"hook_event_name": "PreToolUse"}) is None

    def test_stop_with_empty_transcript_returns_none(self, tmp_path):
        path = write_transcript(tmp_path, [])
        assert message_from_payload({"hook_event_name": "Stop", "transcript_path": path}) is None


class TestTranscriptExtractionHardening:
    """Shapes that shouldn't occur in real transcripts (per the six-transcript,
    145-entry sample this task's brief cites) but must not crash if they do."""

    def test_directory_as_transcript_path_yields_empty(self, tmp_path):
        assert last_assistant_text(str(tmp_path)) == ""

    def test_dangling_symlink_yields_empty(self, tmp_path):
        link = tmp_path / "dangling.jsonl"
        link.symlink_to(tmp_path / "does-not-exist.jsonl")
        assert last_assistant_text(str(link)) == ""

    def test_non_string_path_yields_empty(self):
        assert last_assistant_text(None) == ""  # type: ignore[arg-type]
        assert last_assistant_text(123) == ""  # type: ignore[arg-type]

    def test_empty_string_path_yields_empty(self):
        assert last_assistant_text("") == ""

    def test_line_that_is_valid_json_but_not_an_object_is_skipped(self, tmp_path):
        p = tmp_path / "t.jsonl"
        p.write_text("\n".join([
            json.dumps([1, 2, 3]),
            json.dumps("just a string"),
            json.dumps(42),
            json.dumps(None),
            json.dumps(assistant("good")),
        ]))
        assert last_assistant_text(str(p)) == "good"

    def test_null_message_field_is_skipped(self, tmp_path):
        p = tmp_path / "t.jsonl"
        p.write_text("\n".join([
            json.dumps({"type": "assistant", "message": None}),
            json.dumps(assistant("good")),
        ]))
        assert last_assistant_text(str(p)) == "good"

    def test_bare_string_message_field_is_skipped(self, tmp_path):
        p = tmp_path / "t.jsonl"
        p.write_text("\n".join([
            json.dumps({"type": "assistant", "message": "not a dict"}),
            json.dumps(assistant("good")),
        ]))
        assert last_assistant_text(str(p)) == "good"

    def test_bare_string_content_is_skipped(self, tmp_path):
        p = tmp_path / "t.jsonl"
        p.write_text("\n".join([
            json.dumps({"type": "assistant", "message": {"content": "plain text"}}),
            json.dumps(assistant("good")),
        ]))
        assert last_assistant_text(str(p)) == "good"

    def test_non_string_text_field_is_skipped(self, tmp_path):
        path = write_transcript(tmp_path, [{
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": 12345}]},
        }])
        assert last_assistant_text(path) == ""

    def test_huge_last_turn_is_returned_intact_and_fast(self, tmp_path):
        big = "word " * 200_000  # ~1MB of text, one enormous assistant turn
        path = write_transcript(tmp_path, [assistant(big)])
        import time
        start = time.monotonic()
        result = last_assistant_text(path)
        elapsed = time.monotonic() - start
        assert result == big.strip()
        assert elapsed < 1.0


class TestPayloadRoutingHardening:
    def test_non_dict_payload_returns_none(self):
        assert message_from_payload([1, 2, 3]) is None  # type: ignore[arg-type]
        assert message_from_payload("Stop") is None  # type: ignore[arg-type]
        assert message_from_payload(None) is None  # type: ignore[arg-type]
        assert message_from_payload(42) is None  # type: ignore[arg-type]

    def test_notification_with_empty_message_returns_none(self):
        assert message_from_payload({
            "hook_event_name": "Notification",
            "message": "",
        }) is None

    def test_notification_with_whitespace_message_returns_none(self):
        assert message_from_payload({
            "hook_event_name": "Notification",
            "message": "   \n\t  ",
        }) is None

    def test_notification_missing_message_returns_none(self):
        assert message_from_payload({"hook_event_name": "Notification"}) is None

    def test_notification_with_non_string_message_returns_none(self):
        assert message_from_payload({
            "hook_event_name": "Notification",
            "message": ["not", "a", "string"],
        }) is None
        assert message_from_payload({
            "hook_event_name": "Notification",
            "message": 12345,
        }) is None

    def test_stop_with_non_string_transcript_path_returns_none(self):
        assert message_from_payload({
            "hook_event_name": "Stop",
            "transcript_path": None,
        }) is None
        assert message_from_payload({
            "hook_event_name": "Stop",
            "transcript_path": 123,
        }) is None

    def test_stop_missing_transcript_path_returns_none(self):
        assert message_from_payload({"hook_event_name": "Stop"}) is None

    def test_stop_with_directory_transcript_path_returns_none(self, tmp_path):
        assert message_from_payload({
            "hook_event_name": "Stop",
            "transcript_path": str(tmp_path),
        }) is None

    def test_carries_session_and_cwd_through(self, tmp_path):
        path = write_transcript(tmp_path, [assistant("hello")])
        m = message_from_payload({
            "hook_event_name": "Stop",
            "transcript_path": path,
            "session_id": "abc-123",
            "cwd": "/home/marwan/workspace/dotfiles",
        })
        assert m["session"] == "abc-123"
        assert m["cwd"] == "/home/marwan/workspace/dotfiles"

    def test_missing_session_and_cwd_are_none(self, tmp_path):
        path = write_transcript(tmp_path, [assistant("hello")])
        m = message_from_payload({"hook_event_name": "Stop", "transcript_path": path})
        assert m["session"] is None
        assert m["cwd"] is None


class TestMainNeverRaises:
    def test_main_exits_zero_on_garbage_stdin(self, monkeypatch, capsys):
        import io
        from tts.hooks import claude as claude_mod

        monkeypatch.setattr(sys, "stdin", io.StringIO("not json at all"))
        assert claude_mod.main() == 0

    def test_main_exits_zero_on_valid_json_non_object(self, monkeypatch):
        import io
        from tts.hooks import claude as claude_mod

        monkeypatch.setattr(sys, "stdin", io.StringIO("[1, 2, 3]"))
        assert claude_mod.main() == 0

    def test_main_exits_zero_when_helper_raises(self, monkeypatch):
        """Defense in depth: even if a future change reintroduces a bug in
        message_from_payload, main() must still exit 0 rather than crash."""
        import io
        from tts.hooks import claude as claude_mod

        def boom(_payload):
            raise RuntimeError("unexpected shape")

        monkeypatch.setattr(claude_mod, "message_from_payload", boom)
        monkeypatch.setattr(sys, "stdin", io.StringIO('{"hook_event_name": "Stop"}'))
        assert claude_mod.main() == 0

    def test_main_does_not_send_when_daemon_unreachable(self, monkeypatch, tmp_path):
        """send() failing (no daemon, no systemd) must not raise out of main()."""
        import io
        from tts.hooks import claude as claude_mod

        path = write_transcript(tmp_path, [assistant("hello there")])
        payload = json.dumps({"hook_event_name": "Stop", "transcript_path": path})
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        monkeypatch.setattr(claude_mod, "send", lambda *a, **k: (_ for _ in ()).throw(OSError("no daemon")))
        # send() itself never raises in practice (client.py swallows OSError),
        # but main()'s own try/except must still hold even if that changes.
        assert claude_mod.main() == 0
