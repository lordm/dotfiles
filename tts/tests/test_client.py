import json
import socket
import threading
import pytest
from tts.client import send, build_message


class TestMessageBuilding:
    def test_say_builds_response_message(self, monkeypatch):
        monkeypatch.setenv("TMUX_PANE", "%7")
        m = build_message("say", "hello there")
        assert m["text"] == "hello there"
        assert m["pane"] == "%7"
        assert m["kind"] == "response"

    def test_pane_absent_outside_tmux(self, monkeypatch):
        monkeypatch.delenv("TMUX_PANE", raising=False)
        assert build_message("say", "hi")["pane"] is None

    def test_stop_builds_command(self):
        assert build_message("stop", None) == {"cmd": "stop"}

    def test_toggle_builds_command(self):
        assert build_message("toggle", None) == {"cmd": "toggle"}


class TestSend:
    def test_send_delivers_json_line(self, tmp_path):
        sock_path = tmp_path / "t.sock"
        received = []
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock_path))
        server.listen(1)

        def accept_one():
            conn, _ = server.accept()
            with conn:
                received.append(conn.recv(65536).decode())

        t = threading.Thread(target=accept_one)
        t.start()
        send({"text": "hi", "pane": None}, path=sock_path, autostart=False)
        t.join(timeout=3)
        server.close()
        assert json.loads(received[0].strip())["text"] == "hi"

    def test_send_to_missing_socket_is_silent(self, tmp_path):
        # A dead daemon must never make an agent's hook fail.
        send({"text": "hi"}, path=tmp_path / "nope.sock", autostart=False)
