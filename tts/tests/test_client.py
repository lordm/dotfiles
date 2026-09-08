import json
import socket
import threading
import time
from unittest import mock

import pytest

from tts import client
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


class TestWireFormat:
    def test_message_is_newline_terminated_on_the_wire(self, tmp_path):
        # The daemon's read loop dispatches as soon as it sees a newline;
        # without one it waits out a client timeout. This locks the framing
        # in place at the byte level, not just via json.loads(...strip()),
        # which would tolerate a missing newline just as well.
        sock_path = tmp_path / "wire.sock"
        received = []
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock_path))
        server.listen(1)

        def accept_one():
            conn, _ = server.accept()
            with conn:
                received.append(conn.recv(65536))

        t = threading.Thread(target=accept_one)
        t.start()
        send({"text": "hi", "pane": None}, path=sock_path, autostart=False)
        t.join(timeout=3)
        server.close()
        assert received[0].endswith(b"\n")


class TestAutostart:
    def test_uses_no_block_so_the_request_returns_immediately(self):
        # --no-block is what makes _autostart() return as soon as the job is
        # enqueued rather than waiting for the daemon to finish starting --
        # the whole basis for send() being non-blocking by default.
        with mock.patch("tts.client.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0)
            assert client._autostart() is True
        args = run.call_args[0][0]
        assert "--no-block" in args

    def test_missing_systemctl_is_treated_as_unavailable(self):
        with mock.patch("tts.client.subprocess.run", side_effect=FileNotFoundError):
            assert client._autostart() is False

    def test_nonzero_exit_is_treated_as_unavailable(self):
        # A unit that doesn't exist, or is failed/start-limited, still lets
        # subprocess.run return normally -- just with a nonzero code. That
        # must count as "don't bother retrying", the same as a missing binary.
        with mock.patch("tts.client.subprocess.run",
                         return_value=mock.Mock(returncode=1)):
            assert client._autostart() is False

    def test_hung_systemctl_is_treated_as_unavailable(self):
        with mock.patch("tts.client.subprocess.run",
                         side_effect=client.subprocess.TimeoutExpired(cmd="systemctl", timeout=3)):
            assert client._autostart() is False


class TestSendIsNonBlockingByDefault:
    """Covers the regression that motivated this file: send()'s default path
    must never sit around waiting for a cold-starting daemon, because both
    hook adapters call through it on every turn.
    """

    def test_autostart_accepted_but_socket_never_appears_returns_promptly(self, tmp_path):
        # Simulates systemd accepting the start request while the daemon
        # itself never binds the socket (still loading the model, or it
        # crashed right after forking). This is exactly the scenario the
        # reviewer measured blocking for 5+ seconds pre-fix.
        sock_path = tmp_path / "never.sock"
        with mock.patch("tts.client._autostart", return_value=True):
            start = time.monotonic()
            result = send({"cmd": "status"}, path=sock_path)
            elapsed = time.monotonic() - start
        assert result is None
        assert elapsed < 1.0, f"send() blocked for {elapsed:.3f}s waiting on a socket that never appeared"

    def test_missing_systemctl_returns_promptly(self, tmp_path):
        sock_path = tmp_path / "never2.sock"
        with mock.patch("tts.client.subprocess.run", side_effect=FileNotFoundError):
            start = time.monotonic()
            result = send({"text": "hi"}, path=sock_path)
            elapsed = time.monotonic() - start
        assert result is None
        assert elapsed < 1.0

    def test_stale_socket_refusing_connections_returns_promptly(self, tmp_path):
        # A socket file exists (e.g. left behind by a daemon that crashed
        # without cleanup) but nothing is listening on it, so connect() gets
        # ECONNREFUSED rather than ENOENT.
        sock_path = tmp_path / "stale.sock"
        orphan = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        orphan.bind(str(sock_path))
        orphan.close()  # bound but never listen()ing
        with mock.patch("tts.client._autostart", return_value=True):
            start = time.monotonic()
            result = send({"text": "hi"}, path=sock_path)
            elapsed = time.monotonic() - start
        assert result is None
        assert elapsed < 1.0

    def test_default_does_not_poll_even_for_a_daemon_that_would_start_late(self, tmp_path):
        # Without wait=True, send() must give up before a late-arriving
        # daemon would have appeared -- proves the opt-in is required, not
        # merely available, for the non-blocking guarantee to hold.
        sock_path = tmp_path / "late.sock"
        started = threading.Event()

        def delayed_listener():
            time.sleep(0.5)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(sock_path))
            server.listen(1)
            server.settimeout(2)
            started.set()
            try:
                conn, _ = server.accept()
                conn.close()
            except socket.timeout:
                pass
            server.close()

        t = threading.Thread(target=delayed_listener)
        t.start()
        with mock.patch("tts.client._autostart", return_value=True):
            start = time.monotonic()
            result = send({"text": "hi"}, path=sock_path)  # wait defaults to False
            elapsed = time.monotonic() - start
        assert result is None
        assert elapsed < 1.0
        t.join(timeout=3)


class TestSendWaitOptIn:
    def test_wait_true_polls_for_a_daemon_that_starts_late(self, tmp_path):
        # This is the scenario wait=True exists for: a real cold start where
        # the socket takes a moment to appear after the autostart request.
        # Only the interactive CLI opts into this.
        sock_path = tmp_path / "late-ok.sock"
        received = []

        def delayed_listener():
            time.sleep(0.5)
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(sock_path))
            server.listen(1)
            conn, _ = server.accept()
            with conn:
                received.append(conn.recv(65536).decode())
                conn.sendall(b'{"muted": false}\n')
            server.close()

        t = threading.Thread(target=delayed_listener)
        t.start()
        with mock.patch("tts.client._autostart", return_value=True):
            result = send({"cmd": "status"}, path=sock_path, wait=True)
        t.join(timeout=3)
        assert result == '{"muted": false}'
