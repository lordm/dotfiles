import contextlib
import io
import json
import os
import shutil
import socket
import stat
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from tts import engine, ttsd
from tts.engine import StubEngine
from tts.ttsd import MAX_MESSAGE_BYTES, Config, Daemon, load_config, socket_path


@pytest.fixture(autouse=True)
def isolate_runtime_state(tmp_path_factory, monkeypatch):
    """Keep the suite out of the real runtime dir, and off the real tmux.

    Config resolves speaking_flag and pid_file through ttsd._runtime_dir at
    construction time, so pointing that at a scratch directory keeps every
    Daemon built by these tests from writing into $XDG_RUNTIME_DIR, where a
    live daemon's own flags are sitting. poke_status_line is stubbed for the
    same reason in the other direction: a transition would otherwise fork
    `tmux refresh-client` against whatever server the developer is running in.
    """
    scratch = tmp_path_factory.mktemp("runtime")
    monkeypatch.setattr(ttsd, "_runtime_dir", lambda: scratch)
    monkeypatch.setattr(ttsd, "poke_status_line", lambda: None)
    return scratch


class RecordingPlayer:
    """Stands in for the paplay subprocess."""
    def __init__(self):
        self.written = []
        self.killed = 0
        self.closed = 0
    def write(self, samples, rate):
        self.written.append(len(samples))
    def kill(self):
        self.killed += 1
    def close(self):
        self.closed += 1


@pytest.fixture
def daemon(tmp_path):
    player = RecordingPlayer()
    cfg = Config(voice="af_heart", speed=1.15, max_seconds=45.0, wpm=160,
                 muted_flag=tmp_path / "muted")
    d = Daemon(engine=StubEngine(), config=cfg,
               focus_check=lambda pane, query=None: True,
               player_factory=lambda: player)
    return d, player


class TestSpeaking:
    def test_focused_response_is_synthesized(self, daemon):
        d, player = daemon
        d.handle({"text": "All tests pass.", "pane": "%4", "kind": "response"})
        d.drain()
        assert d.engine.calls == ["All tests pass."]
        assert player.written

    def test_text_is_cleaned_before_synthesis(self, daemon):
        d, _ = daemon
        d.handle({"text": "Edited /home/x/y/foo.sh now.", "pane": "%4", "kind": "response"})
        d.drain()
        assert d.engine.calls == ["Edited foo.sh now."]

    def test_long_text_split_into_sentence_chunks(self, daemon):
        d, _ = daemon
        d.handle({"text": "One. Two. Three.", "pane": "%4", "kind": "response"})
        d.drain()
        assert d.engine.calls == ["One.", "Two.", "Three."]

    def test_empty_text_is_dropped(self, daemon):
        d, _ = daemon
        d.handle({"text": "   ", "pane": "%4", "kind": "response"})
        d.drain()
        assert d.engine.calls == []


class TestFocus:
    def test_unfocused_session_does_not_speak(self, tmp_path):
        player = RecordingPlayer()
        cfg = Config("af_heart", 1.15, 45.0, 160, tmp_path / "muted")
        d = Daemon(StubEngine(), cfg,
                   focus_check=lambda pane, query=None: False,
                   player_factory=lambda: player)
        d.handle({"text": "Background work done.", "pane": "%2", "kind": "response"})
        d.drain()
        assert d.engine.calls == []

    def test_unfocused_session_reports_notification(self, tmp_path):
        sent = []
        cfg = Config("af_heart", 1.15, 45.0, 160, tmp_path / "muted")
        d = Daemon(StubEngine(), cfg,
                   focus_check=lambda pane, query=None: False,
                   player_factory=RecordingPlayer,
                   notifier=lambda title, body: sent.append((title, body)))
        d.handle({"text": "Background done.", "pane": "%2", "kind": "response",
                  "source": "codex"})
        d.drain()
        assert len(sent) == 1
        assert "codex" in sent[0][0].lower()

    def test_the_notification_body_is_cleaned_like_speech(self, tmp_path):
        """An unfocused session should not be the one that gets raw markdown.

        The body is read at a glance from the corner of a screen; spending
        that glance on fences and absolute paths is worse than spending it on
        the prose the focused session would have heard.
        """
        sent = []
        cfg = Config("af_heart", 1.15, 45.0, 160, tmp_path / "muted")
        d = Daemon(StubEngine(), cfg,
                   focus_check=lambda pane, query=None: False,
                   player_factory=RecordingPlayer,
                   notifier=lambda title, body: sent.append(body))
        d.handle({"text": "Edited `/home/x/y/foo.sh` and **fixed** it.\n\n"
                          "```py\nprint(1)\nprint(2)\n```\n\n"
                          "See [the docs](https://x.com/y).",
                  "pane": "%2", "kind": "response", "source": "claude"})
        d.drain()
        assert sent == ["Edited foo.sh and fixed it. code block, 2 lines. See the docs."]

    def test_a_notification_body_is_capped(self, tmp_path):
        sent = []
        cfg = Config("af_heart", 1.15, 45.0, 160, tmp_path / "muted")
        d = Daemon(StubEngine(), cfg,
                   focus_check=lambda pane, query=None: False,
                   player_factory=RecordingPlayer,
                   notifier=lambda title, body: sent.append(body))
        d.handle({"text": "word " * 5000, "pane": "%2", "kind": "response"})
        d.drain()
        assert len(sent[0]) <= 200


class TestMute:
    def test_muted_daemon_stays_silent(self, daemon):
        d, _ = daemon
        d.handle({"cmd": "toggle"})
        d.handle({"text": "Hello.", "pane": "%4", "kind": "response"})
        d.drain()
        assert d.engine.calls == []

    def test_toggle_twice_speaks_again(self, daemon):
        d, _ = daemon
        d.handle({"cmd": "toggle"})
        d.handle({"cmd": "toggle"})
        d.handle({"text": "Hello.", "pane": "%4", "kind": "response"})
        d.drain()
        assert d.engine.calls == ["Hello."]

    def test_mute_survives_restart(self, tmp_path):
        cfg = Config("af_heart", 1.15, 45.0, 160, tmp_path / "muted")
        first = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
                       player_factory=RecordingPlayer)
        first.handle({"cmd": "toggle"})
        second = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
                        player_factory=RecordingPlayer)
        assert second.status()["muted"] is True


class TestInterruption:
    def test_superseded_sentences_are_never_spoken(self, daemon):
        d, _ = daemon
        d.handle({"text": "First. Second. Third.", "pane": "%4", "kind": "response"})
        d.handle({"text": "Newer.", "pane": "%4", "kind": "response"})
        d.drain()
        # The three queued sentences belong to a stale generation and are dropped.
        assert d.engine.calls == ["Newer."]

    def test_interrupting_active_playback_kills_the_player(self, daemon):
        d, player = daemon
        d.handle({"text": "First.", "pane": "%4", "kind": "response"})
        d.drain()  # a player now exists, so there is something to interrupt
        d.handle({"text": "Newer.", "pane": "%4", "kind": "response"})
        assert player.killed >= 1

    def test_stop_command_kills_playback(self, daemon):
        d, player = daemon
        d.handle({"text": "Long one.", "pane": "%4", "kind": "response"})
        d.drain()
        d.handle({"cmd": "stop"})
        assert player.killed >= 1

    def test_stop_when_idle_is_harmless(self, daemon):
        d, _ = daemon
        d.handle({"cmd": "stop"})
        assert d.status()["speaking"] is False


class TestEventFlags:
    """config.toml's [events] table, which the spec promises actually works.

    "Every value is overridable there without touching code" -- so a flag that
    parses, validates and then does nothing is the one outcome that must not
    ship. A disabled event produces no speech *and* no notification: turning it
    off means being left alone, not being nagged by the desktop instead.
    """

    def _daemon(self, tmp_path, events, focused=True):
        self.notifications = []
        cfg = Config("af_heart", 1.15, 45.0, 160, tmp_path / "muted", events=events)
        return Daemon(StubEngine(), cfg,
                      focus_check=lambda p, query=None: focused,
                      player_factory=RecordingPlayer,
                      notifier=lambda title, body: self.notifications.append(body))

    @pytest.mark.parametrize("source,kind,flag", [
        ("claude", "response", "claude_stop"),
        ("claude", "permission", "claude_notification"),
        ("codex", "response", "codex_stop"),
        ("codex", "permission", "codex_permission"),
    ])
    def test_a_disabled_event_is_silent(self, tmp_path, source, kind, flag):
        d = self._daemon(tmp_path, {flag: False})
        d.handle({"text": "Something happened.", "pane": "%4",
                  "source": source, "kind": kind})
        d.drain()
        assert d.engine.calls == []

    @pytest.mark.parametrize("source,kind,flag", [
        ("claude", "response", "claude_stop"),
        ("claude", "permission", "claude_notification"),
        ("codex", "response", "codex_stop"),
        ("codex", "permission", "codex_permission"),
    ])
    def test_an_enabled_event_still_speaks(self, tmp_path, source, kind, flag):
        d = self._daemon(tmp_path, {flag: True})
        d.handle({"text": "Something happened.", "pane": "%4",
                  "source": source, "kind": kind})
        d.drain()
        assert d.engine.calls == ["Something happened."]

    def _say(self, daemon, text, source, kind):
        # Drained one at a time: a later utterance supersedes an earlier one,
        # which would hide the flag under the interruption rule.
        daemon.handle({"text": text, "pane": "%4", "source": source, "kind": kind})
        daemon.drain()

    def test_disabling_one_event_leaves_the_others_alone(self, tmp_path):
        d = self._daemon(tmp_path, {"claude_notification": False})
        self._say(d, "Turn finished.", "claude", "response")
        self._say(d, "Permission needed.", "claude", "permission")
        self._say(d, "Codex asks.", "codex", "permission")
        assert d.engine.calls == ["Turn finished.", "Codex asks."]

    def test_a_disabled_event_does_not_fall_back_to_a_notification(self, tmp_path):
        d = self._daemon(tmp_path, {"codex_stop": False}, focused=False)
        d.handle({"text": "Background turn.", "pane": "%9",
                  "source": "codex", "kind": "response"})
        d.drain()
        assert self.notifications == []
        assert d.engine.calls == []

    @pytest.mark.parametrize("events", [None, {}, {"codex_stop": False}])
    def test_absent_flags_default_to_enabled(self, tmp_path, events):
        d = self._daemon(tmp_path, events)
        d.handle({"text": "Turn finished.", "pane": "%4",
                  "source": "claude", "kind": "response"})
        d.drain()
        assert d.engine.calls == ["Turn finished."]

    def test_an_unrecognised_pairing_is_not_silenced(self, tmp_path):
        """Only the four wired events are configurable; anything else speaks."""
        d = self._daemon(tmp_path, {"claude_stop": False})
        d.handle({"text": "From the CLI.", "pane": "%4"})
        d.drain()
        self._say(d, "Some other harness.", "aider", "response")
        self._say(d, "Odd shape.", ["claude"], "response")
        assert d.engine.calls == ["From the CLI.", "Some other harness.", "Odd shape."]


class TestStatus:
    def test_status_reports_shape(self, daemon):
        d, _ = daemon
        s = d.status()
        assert set(s) >= {"muted", "speaking", "voice"}
        assert s["voice"] == "af_heart"


class TestMalformedInput:
    def test_unknown_command_is_ignored(self, daemon):
        d, _ = daemon
        d.handle({"cmd": "explode"})
        assert d.status()["speaking"] is False

    def test_message_without_text_or_cmd_is_ignored(self, daemon):
        d, _ = daemon
        d.handle({"pane": "%4"})
        d.drain()
        assert d.engine.calls == []


# ---------------------------------------------------------------------------
# Concurrency: these drive run_worker() on a real thread rather than calling
# drain() synchronously, which is the only way the player-lifecycle race is
# reachable at all.
# ---------------------------------------------------------------------------


class SignallingPlayer:
    """A player that reports what happened to it, and when.

    ``writes_after_kill`` counts writes *entered* after kill() returned, which
    is the thing that must never happen: a write already in flight when the
    kill lands is fine, because killing the paplay process is exactly what
    unblocks it.
    """

    def __init__(self, block_write=False, block_close=False):
        self.written = []
        self.killed = 0
        self.closed = 0
        self.writes_after_kill = 0
        self.wrote = threading.Event()
        self.entered_write = threading.Event()
        self.entered_close = threading.Event()
        self._block_write = block_write
        self._release_write = threading.Event()
        self._block_close = block_close
        self.release_close = threading.Event()

    def write(self, samples, rate):
        if self.killed:
            self.writes_after_kill += 1
        self.entered_write.set()
        if self._block_write:
            # A real paplay write blocks once the pipe fills; kill() unblocks it.
            self._release_write.wait(5)
        self.written.append(len(samples))
        self.wrote.set()

    def kill(self):
        self.killed += 1
        self._release_write.set()  # a killed paplay never blocks a writer again
        self.release_close.set()  # ...and never keeps a retirement waiting either

    def close(self):
        # A real close() blocks until paplay has played out what it already
        # holds, which is why retirement runs on the worker thread.
        self.entered_close.set()
        if self._block_close:
            self.release_close.wait(5)
        self.closed += 1


class BlockingFactory:
    """A player_factory that can be paused mid-construction.

    Spawning paplay is not instantaneous, so this stands in for a stop that
    arrives while the player is being created.
    """

    def __init__(self, player):
        self.player = player
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def __call__(self):
        self.calls += 1
        self.entered.set()
        assert self.release.wait(5), "factory was never released"
        return self.player


def _wait_for(predicate, timeout=2.0):
    """Poll until predicate() is truthy. Returns the final result."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.005)
    return predicate()


def _worker(daemon):
    thread = threading.Thread(target=daemon.run_worker, daemon=True)
    thread.start()
    return thread


def _config(tmp_path):
    return Config("af_heart", 1.15, 45.0, 160, tmp_path / "muted")


class TestConcurrentPlayerLifecycle:
    def test_stop_during_player_creation_produces_no_audio(self, tmp_path):
        """A stop that lands while the player is being spawned must win.

        The worker has already passed its generation check and is inside the
        factory. If the player lifecycle is unguarded, the worker installs the
        player it was handed and speaks an utterance the user has silenced.
        """
        player = SignallingPlayer()
        factory = BlockingFactory(player)
        d = Daemon(StubEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True,
                   player_factory=factory)
        _worker(d)

        d.handle({"text": "Silence me.", "pane": "%4", "kind": "response"})
        assert factory.entered.wait(2), "worker never reached player creation"

        d.stop_speaking()
        factory.release.set()

        assert not player.wrote.wait(0.5), "audio for a stopped utterance was played"
        assert player.killed == 1, "the orphaned player was not cleaned up"
        assert d.status()["speaking"] is False

    def test_new_utterance_mid_playback_silences_the_old_one(self, tmp_path):
        players = []

        def factory():
            player = SignallingPlayer(block_write=not players)
            players.append(player)
            return player

        d = Daemon(StubEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True,
                   player_factory=factory)
        _worker(d)

        d.handle({"text": "First.", "pane": "%4", "kind": "response"})
        assert _wait_for(lambda: players), "no player was ever created"
        assert players[0].entered_write.wait(2), "playback never started"

        d.handle({"text": "Newer.", "pane": "%4", "kind": "response"})
        assert players[0].killed >= 1, "the interrupted player was not killed"

        assert _wait_for(lambda: len(players) == 2), \
            "the new utterance never got its own player"
        assert players[1].wrote.wait(2), "the new utterance was never played"
        assert players[0].writes_after_kill == 0
        assert d.engine.calls == ["First.", "Newer."]

    def test_stop_while_idle_is_harmless_with_a_running_worker(self, tmp_path):
        players = []

        def factory():
            players.append(SignallingPlayer())
            return players[-1]

        d = Daemon(StubEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True,
                   player_factory=factory)
        _worker(d)

        d.stop_speaking()
        d.handle({"cmd": "stop"})
        assert players == []
        assert d.status()["speaking"] is False

        d.handle({"text": "Still working.", "pane": "%4", "kind": "response"})
        assert _wait_for(lambda: players), "the daemon stopped speaking entirely"
        assert players[0].wrote.wait(2)
        assert d.engine.calls == ["Still working."]

    def test_rapid_interruptions_leave_one_live_player(self, tmp_path):
        players = []

        def factory():
            players.append(SignallingPlayer())
            return players[-1]

        d = Daemon(StubEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True,
                   player_factory=factory)
        _worker(d)

        for i in range(40):
            d.handle({"text": f"Message number {i}.", "pane": "%4", "kind": "response"})
            time.sleep(0.001)

        _wait_for(lambda: d.status()["queued"] == 0, timeout=3)
        time.sleep(0.2)

        assert d.engine.calls[-1] == "Message number 39."

        # A player is still able to make sound unless it was killed by an
        # interruption or retired at the end of its utterance. Counting kills
        # alone left room for the leak this now rules out: a paplay installed
        # forever is "not killed" and was passing as the one legitimate
        # survivor. Once everything has settled, none of them is sounding.
        def still_sounding():
            return [p for p in players if not (p.killed or p.closed)]

        assert len(still_sounding()) <= 1, "more than one player left running"
        assert _wait_for(lambda: not still_sounding(), timeout=3), \
            f"{len(still_sounding())} players left running"


class TestPlayerRetirement:
    """paplay must not outlive the utterance that spawned it.

    A player left installed keeps the output sink open forever: on this machine
    that was one paplay alive for minutes with nothing to say, holding an audio
    interface in RUNNING while every other sink on the box was SUSPENDED.
    """

    def _daemon(self, tmp_path, **player_kwargs):
        players = []

        def factory():
            players.append(SignallingPlayer(**player_kwargs))
            return players[-1]

        d = Daemon(StubEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True,
                   player_factory=factory)
        _worker(d)
        return d, players

    def test_player_is_retired_when_the_queue_drains(self, tmp_path):
        d, players = self._daemon(tmp_path)

        d.handle({"text": "One. Two. Three.", "pane": "%4", "kind": "response"})
        assert _wait_for(lambda: players), "no player was ever created"
        assert _wait_for(lambda: players[0].closed == 1, timeout=3), \
            "the player was still installed after everything had been spoken"
        assert players[0].killed == 0, \
            "a finished utterance was cut short instead of being drained"
        assert len(players[0].written) == 3
        assert d.status()["speaking"] is False

    def test_a_later_utterance_gets_its_own_player(self, tmp_path):
        """The retired player must be forgotten, not reused.

        A closed paplay cannot accept audio, so reinstalling it would lose the
        next utterance entirely.
        """
        d, players = self._daemon(tmp_path)

        d.handle({"text": "First.", "pane": "%4", "kind": "response"})
        assert _wait_for(lambda: players and players[0].closed == 1, timeout=3)

        d.handle({"text": "Second.", "pane": "%4", "kind": "response"})
        assert _wait_for(lambda: len(players) == 2, timeout=3), \
            "the second utterance reused a retired player"
        assert players[1].wrote.wait(2)
        assert _wait_for(lambda: players[1].closed == 1, timeout=3)

    def test_speaking_stays_true_until_the_audio_has_drained(self, tmp_path):
        """status() must not claim silence while paplay is still playing."""
        d, players = self._daemon(tmp_path, block_close=True)

        d.handle({"text": "Still playing.", "pane": "%4", "kind": "response"})
        assert _wait_for(lambda: players), "no player was ever created"
        assert players[0].entered_close.wait(2), "the player was never retired"
        assert d.status()["speaking"] is True, \
            "reported silence while the audio was still draining"

        players[0].release_close.set()
        assert _wait_for(lambda: d.status()["speaking"] is False), \
            "still reported speaking after the audio had drained"

    def test_stop_during_the_drain_stays_instant(self, tmp_path):
        """An interruption must not queue behind the tail of the last utterance."""
        d, players = self._daemon(tmp_path, block_close=True)

        d.handle({"text": "Cut me off.", "pane": "%4", "kind": "response"})
        assert _wait_for(lambda: players), "no player was ever created"
        assert players[0].entered_close.wait(2), "the player was never retired"

        started = time.monotonic()
        d.stop_speaking()
        elapsed = time.monotonic() - started

        assert elapsed < 0.5, f"stop waited {elapsed:.2f}s on draining audio"
        assert players[0].killed == 1, "the retiring player was not killed"
        assert d.status()["speaking"] is False


# ---------------------------------------------------------------------------
# The socket. None of the behaviour below is reachable through handle(): it is
# all in serve(), which the brief's tests never start.
# ---------------------------------------------------------------------------


@pytest.fixture
def served():
    """A real daemon on a real Unix socket, under a short /tmp path.

    Short because AF_UNIX paths are capped at ~108 bytes and pytest's tmp_path
    is not built with that in mind.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="ttsd-test-"))
    path = tmpdir / "s.sock"
    player = RecordingPlayer()
    cfg = Config("af_heart", 1.15, 45.0, 160, tmpdir / "muted")
    d = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
               player_factory=lambda: player)
    thread = threading.Thread(target=d.serve, args=(path,), daemon=True)
    thread.start()
    # Wait for something to be *accepting*, not merely for the path to appear:
    # bind() creates the file and listen() comes after it, so a connect landing
    # in between is refused. That window is narrow enough to pass hundreds of
    # runs and then fail once under load.
    assert _wait_for(lambda: ttsd._socket_is_live(path)), \
        "daemon never listened on its socket"
    try:
        yield d, path
    finally:
        d._stop_serving.set()
        thread.join(timeout=5)
        shutil.rmtree(tmpdir, ignore_errors=True)


def _connect(path):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(5)
    client.connect(str(path))
    return client


def _send(path, payload: bytes) -> None:
    with _connect(path) as client:
        client.sendall(payload)


def _speak_request(text: str) -> bytes:
    return json.dumps({"text": text, "pane": "%4", "kind": "response"}).encode() + b"\n"


def _status(path) -> dict:
    with _connect(path) as client:
        client.sendall(b'{"cmd": "status"}\n')
        return json.loads(client.recv(65536).decode())


@contextlib.contextmanager
def _serving(**kwargs):
    """A served daemon with the collaborators a test wants to control."""
    tmpdir = Path(tempfile.mkdtemp(prefix="ttsd-test-"))
    path = tmpdir / "s.sock"
    kwargs.setdefault("focus_check", lambda pane, query=None: True)
    kwargs.setdefault("player_factory", RecordingPlayer)
    d = Daemon(StubEngine(), Config("af_heart", 1.15, 45.0, 160, tmpdir / "muted"),
               **kwargs)
    thread = threading.Thread(target=d.serve, args=(path,), daemon=True)
    thread.start()
    assert _wait_for(lambda: ttsd._socket_is_live(path)), \
        "daemon never listened on its socket"
    try:
        yield d, path
    finally:
        d._stop_serving.set()
        thread.join(timeout=5)
        shutil.rmtree(tmpdir, ignore_errors=True)


class TestSocketProtocol:
    def test_a_message_is_spoken(self, served):
        d, path = served
        _send(path, _speak_request("Hello there."))
        assert _wait_for(lambda: d.engine.calls == ["Hello there."]), d.engine.calls

    def test_message_split_across_recv_boundaries(self, served):
        d, path = served
        with _connect(path) as client:
            client.sendall(b'{"text": "Split across ')
            time.sleep(0.05)
            client.sendall(b'two packets.", "pane": "%4"}\n')
        assert _wait_for(lambda: d.engine.calls == ["Split across two packets."]), \
            d.engine.calls

    def test_message_without_trailing_newline_is_still_read(self, served):
        d, path = served
        _send(path, json.dumps({"text": "No newline.", "pane": "%4"}).encode())
        assert _wait_for(lambda: d.engine.calls == ["No newline."]), d.engine.calls

    def test_client_disconnecting_mid_message_is_survived(self, served):
        d, path = served
        _send(path, b'{"text": "Truncated mid')
        _send(path, _speak_request("Still alive."))
        assert _wait_for(lambda: d.engine.calls == ["Still alive."]), d.engine.calls

    def test_garbage_is_ignored_and_the_daemon_lives(self, served):
        d, path = served
        for payload in (b"not json at all\n", b"[1, 2, 3]\n", b'"just a string"\n',
                        b"null\n", b"\n\n\n", b"\xff\xfe\x00\n"):
            _send(path, payload)
        _send(path, _speak_request("Survived."))
        assert _wait_for(lambda: d.engine.calls == ["Survived."]), d.engine.calls

    def test_several_messages_in_one_packet_are_all_read(self, served):
        d, path = served
        _send(path, b"garbage\n" + _speak_request("Second line."))
        assert _wait_for(lambda: d.engine.calls == ["Second line."]), d.engine.calls

    def test_status_request_gets_a_reply(self, served):
        d, path = served
        with _connect(path) as client:
            client.sendall(b'{"cmd": "status"}\n')
            reply = client.recv(65536)
        parsed = json.loads(reply.decode())
        assert parsed["voice"] == "af_heart"
        assert parsed["muted"] is False
        assert parsed["speaking"] is False

    def test_consecutive_clients_are_all_served(self, served):
        d, path = served
        for i in range(5):
            _send(path, _speak_request(f"Message {i}."))
            assert _wait_for(lambda i=i: d.engine.calls[-1:] == [f"Message {i}."]), \
                d.engine.calls

    def test_a_client_that_connects_and_says_nothing_cannot_wedge_the_daemon(self, served):
        d, path = served
        idle = _connect(path)  # deliberately never sends, never closes
        try:
            _send(path, _speak_request("Not blocked."))
            assert _wait_for(lambda: d.engine.calls == ["Not blocked."], timeout=4), \
                "an idle client stalled the accept loop"
        finally:
            idle.close()

    def test_an_oversized_message_is_dropped_not_buffered(self, served):
        d, path = served
        with _connect(path) as client:
            try:
                client.sendall(b'{"text": "' + b"x" * (MAX_MESSAGE_BYTES + 1024) + b'"}\n')
            except OSError:
                pass  # daemon hung up on us, which is the point
        _send(path, _speak_request("Still here."))
        assert _wait_for(lambda: d.engine.calls == ["Still here."]), d.engine.calls

    def test_socket_is_private_to_the_user(self, served):
        _, path = served
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_socket_file_is_removed_on_shutdown(self, served):
        d, path = served
        d._stop_serving.set()
        assert _wait_for(lambda: not path.exists(), timeout=3), "socket file left behind"

    def test_a_stale_socket_file_is_replaced(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="ttsd-test-"))
        try:
            path = tmpdir / "s.sock"
            path.touch()  # left behind by a daemon that was killed
            cfg = Config("af_heart", 1.15, 45.0, 160, tmpdir / "muted")
            d = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
                       player_factory=RecordingPlayer)
            thread = threading.Thread(target=d.serve, args=(path,), daemon=True)
            thread.start()
            try:
                assert _wait_for(lambda: d._server is not None), "never bound"
                _send(path, _speak_request("Bound anyway."))
                assert _wait_for(lambda: d.engine.calls == ["Bound anyway."])
            finally:
                d._stop_serving.set()
                thread.join(timeout=5)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_a_second_daemon_refuses_a_live_socket(self, served):
        _, path = served
        cfg = Config("af_heart", 1.15, 45.0, 160, path.parent / "muted2")
        other = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
                       player_factory=RecordingPlayer)
        with pytest.raises(RuntimeError, match="already listening"):
            other.serve(path)


# ---------------------------------------------------------------------------
# Playback that cannot start, or fails part-way.
# ---------------------------------------------------------------------------


class TestAcceptLoopNeverBlocks:
    """The accept loop may not wait on a subprocess. Ever.

    A hook adapter must never slow a turn down, and the thing that makes that
    fragile is AF_UNIX: connect() to a full backlog *blocks* rather than being
    refused, and tts/client.py allows three seconds before giving up. So an
    accept loop parked in a stalled tmux or notify-send reaches back through
    the backlog and into the agent. The scenario is this feature's own design
    goal -- several unfocused background agents, all routed to notify-send.

    listen(16), so these push more than sixteen connections through while the
    decision is wedged: with the focus query on the accept thread they queue
    behind it, and the sender is the one that pays.
    """

    def _wedge(self):
        entered, release = threading.Event(), threading.Event()

        def blocked(*args, **kwargs):
            entered.set()
            release.wait(10)
            return True

        return entered, release, blocked

    def test_a_wedged_focus_query_does_not_reach_the_accept_loop(self):
        entered, release, hung_focus = self._wedge()
        with _serving(focus_check=hung_focus) as (d, path):
            _send(path, _speak_request("First."))
            assert entered.wait(2), "the focus check never ran"
            try:
                started = time.monotonic()
                for i in range(24):
                    _send(path, _speak_request(f"Message {i}."))
                reply = _status(path)
                elapsed = time.monotonic() - started
            finally:
                release.set()

        assert elapsed < 2.0, f"24 hooks waited {elapsed:.2f}s on a wedged tmux"
        assert reply["voice"] == "af_heart", "status was not served during the stall"

    def test_a_wedged_notification_does_not_reach_the_accept_loop(self):
        entered, release, hung_notify = self._wedge()
        with _serving(focus_check=lambda pane, query=None: False,
                      notifier=hung_notify) as (d, path):
            _send(path, _speak_request("Background turn."))
            assert entered.wait(2), "the notifier never ran"
            try:
                started = time.monotonic()
                for i in range(24):
                    _send(path, _speak_request(f"Message {i}."))
                reply = _status(path)
                elapsed = time.monotonic() - started
            finally:
                release.set()

        assert elapsed < 2.0, f"24 hooks waited {elapsed:.2f}s on a wedged notify-send"
        assert reply["voice"] == "af_heart", "status was not served during the stall"

    def test_stop_is_still_instant_while_intake_is_wedged(self):
        """`tts stop` must not queue behind a decision that cannot finish."""
        entered, release, hung_focus = self._wedge()
        with _serving(focus_check=hung_focus) as (d, path):
            _send(path, _speak_request("First."))
            assert entered.wait(2), "the focus check never ran"
            try:
                started = time.monotonic()
                _send(path, b'{"cmd": "stop"}\n')
                reply = _status(path)
                elapsed = time.monotonic() - started
            finally:
                release.set()

        assert elapsed < 1.0, f"stop waited {elapsed:.2f}s"
        assert reply["speaking"] is False

    def test_a_flood_is_dropped_rather_than_buffered_forever(self):
        entered, release, hung_focus = self._wedge()
        with _serving(focus_check=hung_focus) as (d, path):
            _send(path, _speak_request("First."))
            assert entered.wait(2), "the focus check never ran"
            try:
                for i in range(ttsd.INTAKE_BACKLOG + 20):
                    _send(path, _speak_request(f"Message {i}."))
                    time.sleep(0.002)  # 16-deep listen backlog, not a flood test
                assert _wait_for(
                    lambda: _status(path)["queued"] == ttsd.INTAKE_BACKLOG), \
                    "the intake backlog was not bounded"
            finally:
                release.set()

    def test_notify_does_not_wait_for_notify_send(self, monkeypatch):
        """The desktop fallback is spawned and forgotten, output included."""
        seen = {}

        class FakeProc:
            def wait(self, timeout=None):
                raise AssertionError("notify() waited for notify-send")

            def communicate(self, *a, **k):
                raise AssertionError("notify() read notify-send's output")

        def fake_popen(argv, **kwargs):
            seen["argv"] = argv
            seen["kwargs"] = kwargs
            return FakeProc()

        monkeypatch.setattr(ttsd.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(ttsd.subprocess, "run", lambda *a, **k:
                            (_ for _ in ()).throw(AssertionError("notify() used run()")))

        ttsd.notify("Claude", "a background turn finished")

        assert seen["argv"][0] == "notify-send"
        assert seen["argv"][-1] == "a background turn finished"
        # An unread pipe fills and blocks the process we refuse to wait for.
        assert seen["kwargs"]["stdout"] is ttsd.subprocess.DEVNULL
        assert seen["kwargs"]["stderr"] is ttsd.subprocess.DEVNULL


class TestStopBeatsPendingWork:
    """`tts stop` is specified as "silence immediately, drop pending".

    Handling messages on the intake thread put a queue between the socket and
    the decision to speak, and a queue is somewhere a stop can be overtaken:
    the accept thread answers the stop at once while the intake thread is still
    parked in a focus check for a message that arrived first. That message must
    not start talking afterwards -- it reached the daemon first, but the user
    asked for silence second, and the later instruction is the one they meant.
    """

    def _wedge(self):
        entered, release = threading.Event(), threading.Event()

        def blocked(*args, **kwargs):
            entered.set()
            release.wait(10)
            return True

        return entered, release, blocked

    def test_a_stop_cancels_the_utterance_being_decided(self):
        entered, release, hung_focus = self._wedge()
        with _serving(focus_check=hung_focus) as (d, path):
            _send(path, _speak_request("First."))
            assert entered.wait(2), "the focus check never ran"
            _send(path, b'{"cmd": "stop"}\n')
            _status(path)  # barrier: the accept loop is FIFO, so the stop ran
            release.set()
            assert not _wait_for(lambda: d.engine.calls, timeout=1.0), \
                f"spoke after a stop: {d.engine.calls}"

    def test_a_stop_drops_an_utterance_waiting_in_intake(self):
        entered, release, hung_focus = self._wedge()
        with _serving(focus_check=hung_focus) as (d, path):
            _send(path, _speak_request("First."))
            assert entered.wait(2), "the focus check never ran"
            _send(path, _speak_request("Second."))
            assert _wait_for(lambda: _status(path)["queued"] >= 1), \
                "the second utterance never reached the intake queue"
            _send(path, b'{"cmd": "stop"}\n')
            _status(path)  # barrier: the accept loop is FIFO, so the stop ran
            release.set()
            assert not _wait_for(lambda: d.engine.calls, timeout=1.0), \
                f"spoke after a stop: {d.engine.calls}"

    def test_muting_cancels_an_utterance_being_decided(self):
        entered, release, hung_focus = self._wedge()
        with _serving(focus_check=hung_focus) as (d, path):
            _send(path, _speak_request("First."))
            assert entered.wait(2), "the focus check never ran"
            _send(path, b'{"cmd": "toggle"}\n')
            _status(path)  # barrier: the accept loop is FIFO, so the mute ran
            release.set()
            assert not _wait_for(lambda: d.engine.calls, timeout=1.0), \
                f"spoke after being muted: {d.engine.calls}"

    def test_a_new_utterance_leaves_the_ones_behind_it_alone(self):
        """Only an explicit stop cancels; "newest wins" must not over-reach.

        The guard against fixing the race by simply draining intake whenever
        anything supersedes anything: the messages queued behind an utterance
        are *newer* than it, and dropping them would lose the very turn the
        user is waiting to hear.
        """
        entered, release, hung_focus = self._wedge()
        with _serving(focus_check=hung_focus) as (d, path):
            _send(path, _speak_request("First."))
            assert entered.wait(2), "the focus check never ran"
            _send(path, _speak_request("Second."))
            assert _wait_for(lambda: _status(path)["queued"] >= 1), \
                "the second utterance never reached the intake queue"
            release.set()
            assert _wait_for(lambda: "Second." in d.engine.calls), \
                f"a queued utterance was lost: {d.engine.calls}"


class TestPlaybackFailure:
    def test_missing_paplay_does_not_raise(self, tmp_path):
        def factory():
            raise FileNotFoundError(2, "No such file or directory", "paplay")

        d = Daemon(StubEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True, player_factory=factory)
        d.handle({"text": "Nobody can hear this.", "pane": "%4"})
        d.drain()
        assert d.engine.calls == ["Nobody can hear this."]
        assert d.status()["speaking"] is False

    def test_worker_survives_a_player_that_cannot_start(self, tmp_path):
        def factory():
            raise OSError("no audio device")

        d = Daemon(StubEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True, player_factory=factory)
        thread = _worker(d)
        d.handle({"text": "First.", "pane": "%4"})
        assert _wait_for(lambda: d.engine.calls == ["First."])
        d.handle({"text": "Second.", "pane": "%4"})
        assert _wait_for(lambda: d.engine.calls == ["First.", "Second."])
        assert thread.is_alive(), "the worker thread died on a playback failure"

    def test_worker_survives_a_player_that_fails_mid_utterance(self, tmp_path):
        class ExplodingPlayer:
            killed = 0

            def write(self, samples, rate):
                raise BrokenPipeError("paplay went away")

            def kill(self):
                type(self).killed += 1

        d = Daemon(StubEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True,
                   player_factory=ExplodingPlayer)
        thread = _worker(d)
        d.handle({"text": "One. Two.", "pane": "%4"})
        assert _wait_for(lambda: d.engine.calls == ["One.", "Two."])
        assert thread.is_alive()
        # The broken player is retired rather than reused for the next sentence.
        assert ExplodingPlayer.killed >= 1

    def test_worker_survives_a_synthesis_failure(self, tmp_path):
        class BrokenEngine:
            calls = []

            def synthesize(self, text):
                self.calls.append(text)
                raise RuntimeError("model exploded")

        player = RecordingPlayer()
        d = Daemon(BrokenEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True,
                   player_factory=lambda: player)
        thread = _worker(d)
        d.handle({"text": "One. Two.", "pane": "%4"})
        assert _wait_for(lambda: d.engine.calls == ["One.", "Two."])
        assert thread.is_alive()


class TestPaplayPlayer:
    def test_spawns_paplay_with_the_engine_sample_rate(self, monkeypatch):
        seen = {}

        class FakeProc:
            def __init__(self):
                self.stdin = io.BytesIO()
                self.killed = False

            def kill(self):
                self.killed = True

        def fake_popen(argv, **kwargs):
            seen["argv"] = argv
            seen["kwargs"] = kwargs
            return FakeProc()

        monkeypatch.setattr(ttsd.subprocess, "Popen", fake_popen)
        player = ttsd.PaplayPlayer()
        assert seen["argv"] == ["paplay", "--raw", "--rate=24000",
                                "--format=s16le", "--channels=1"]
        player.write(np.array([0.0, 1.0, -1.0], dtype=np.float32), 24000)
        assert player._proc.stdin.getvalue() == b"\x00\x00\xff\x7f\x01\x80"

    def test_kill_kills_before_closing_stdin(self, monkeypatch):
        """Closing first would flush, and flushing a full pipe blocks."""
        order = []

        class RecordingStdin:
            def write(self, data):
                pass

            def flush(self):
                pass

            def close(self):
                order.append("close")

        class FakeProc:
            def __init__(self):
                self.stdin = RecordingStdin()

            def kill(self):
                order.append("kill")

        monkeypatch.setattr(ttsd.subprocess, "Popen", lambda *a, **k: FakeProc())
        player = ttsd.PaplayPlayer()
        player.kill()
        assert order == ["kill", "close"]

    def test_kill_tolerates_a_process_that_is_already_gone(self, monkeypatch):
        class FakeProc:
            stdin = None

            def kill(self):
                raise ProcessLookupError()

        monkeypatch.setattr(ttsd.subprocess, "Popen", lambda *a, **k: FakeProc())
        ttsd.PaplayPlayer().kill()  # must not raise

    def test_write_swallows_only_what_an_interruption_produces(self, monkeypatch):
        """A player dying for its own reason must not vanish into a `pass`.

        BrokenPipeError and ValueError are what killing paplay mid-write looks
        like and are expected. Anything else is a real failure, and letting it
        out is what retires the broken player instead of losing the rest of the
        utterance in silence.
        """
        class FailingStdin:
            def __init__(self, error):
                self.error = error

            def write(self, data):
                raise self.error

            def flush(self):
                pass

        class FakeProc:
            def __init__(self, error):
                self.stdin = FailingStdin(error)

        samples = np.zeros(4, dtype=np.float32)

        for expected in (BrokenPipeError(), ValueError()):
            monkeypatch.setattr(ttsd.subprocess, "Popen",
                                lambda *a, e=expected, **k: FakeProc(e))
            ttsd.PaplayPlayer().write(samples, 24000)  # must not raise

        monkeypatch.setattr(ttsd.subprocess, "Popen",
                            lambda *a, **k: FakeProc(OSError(5, "Input/output error")))
        with pytest.raises(OSError):
            ttsd.PaplayPlayer().write(samples, 24000)

    def test_close_closes_stdin_and_then_waits_for_the_audio(self, monkeypatch):
        """The retirement path: paplay is still playing when the queue empties."""
        order = []

        class RecordingStdin:
            def close(self):
                order.append("close")

        class FakeProc:
            stdin = RecordingStdin()

            def wait(self, timeout=None):
                order.append(("wait", timeout))

            def kill(self):
                order.append("kill")

        monkeypatch.setattr(ttsd.subprocess, "Popen", lambda *a, **k: FakeProc())
        ttsd.PaplayPlayer().close()
        assert order == ["close", ("wait", ttsd.DRAIN_TIMEOUT)]

    def test_close_kills_a_paplay_that_never_exits(self, monkeypatch):
        """A wedged sink must not park the worker thread forever."""
        order = []

        class FakeProc:
            stdin = None

            def wait(self, timeout=None):
                order.append("wait")
                raise ttsd.subprocess.TimeoutExpired("paplay", timeout)

            def kill(self):
                order.append("kill")

        monkeypatch.setattr(ttsd.subprocess, "Popen", lambda *a, **k: FakeProc())
        ttsd.PaplayPlayer().close()
        assert order == ["wait", "kill"]

    def test_close_tolerates_a_process_that_is_already_gone(self, monkeypatch):
        class DeadStdin:
            def close(self):
                raise BrokenPipeError()

        class FakeProc:
            stdin = DeadStdin()

            def wait(self, timeout=None):
                return -9

            def kill(self):
                pass

        monkeypatch.setattr(ttsd.subprocess, "Popen", lambda *a, **k: FakeProc())
        ttsd.PaplayPlayer().close()  # must not raise


# ---------------------------------------------------------------------------
# Configuration and paths.
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_missing_file_yields_defaults(self, tmp_path):
        cfg = load_config(tmp_path / "absent.toml")
        assert (cfg.voice, cfg.speed, cfg.max_seconds, cfg.wpm) == \
            ("af_heart", 1.15, 45.0, 160)

    def test_values_are_read(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('voice = "am_michael"\nspeed = 1.4\n'
                        'max_seconds = 20.0\nwpm = 180\n'
                        '[events]\nclaude_stop = false\n')
        cfg = load_config(path)
        assert cfg.voice == "am_michael"
        assert cfg.speed == 1.4
        assert cfg.max_seconds == 20.0
        assert cfg.wpm == 180
        assert cfg.events == {"claude_stop": False}

    def test_malformed_toml_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('voice = "unterminated\nspeed = = 3\n')
        cfg = load_config(path)
        assert cfg.voice == "af_heart"
        assert cfg.speed == 1.15

    def test_wrongly_typed_value_falls_back_for_that_key_only(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('voice = "am_michael"\nspeed = "quick"\n')
        cfg = load_config(path)
        assert cfg.speed == 1.15
        assert cfg.voice == "am_michael"

    def test_non_table_events_is_ignored(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('events = "yes"\n')
        assert load_config(path).events == {}

    def test_non_boolean_and_unknown_flags_are_rejected_at_startup(self, tmp_path, capsys):
        """A flag that is silently ignored is worse than one that is refused.

        `codex_permission = "no"` reads as off and is truthy; a typo'd key
        reads as off and matches nothing. Either would leave the user thinking
        they had silenced an event while the daemon kept speaking.
        """
        path = tmp_path / "config.toml"
        path.write_text('[events]\ncodex_permission = "no"\n'
                        'claude_stopp = false\nclaude_stop = false\n')
        cfg = load_config(path)
        assert cfg.events == {"claude_stop": False}
        warnings = capsys.readouterr().err
        assert "codex_permission" in warnings
        assert "claude_stopp" in warnings

    def test_the_shipped_config_only_names_flags_the_daemon_knows(self):
        """tts/config.toml is the documentation for this table."""
        shipped = load_config(Path(__file__).resolve().parents[2] / "tts/config.toml")
        assert set(shipped.events) == set(ttsd.EVENT_FLAGS.values())

    def test_muted_flag_follows_xdg_data_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
        cfg = load_config(tmp_path / "absent.toml")
        assert cfg.muted_flag == tmp_path / "share" / "tts" / "muted"

    def test_empty_xdg_data_home_falls_back_to_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", "")
        cfg = load_config(tmp_path / "absent.toml")
        assert cfg.muted_flag == Path.home() / ".local/share/tts/muted"

    def test_share_dir_agrees_with_the_engine(self, tmp_path, monkeypatch):
        """Both modules must resolve the same XDG root, or state splits in two."""
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
        monkeypatch.delenv("TTS_MODEL_DIR", raising=False)
        assert engine._compute_model_dir().parent == ttsd._share_dir()

    def test_default_config_object_is_constructible_positionally(self, tmp_path):
        # Task 5's tests build Config positionally; the field order is a contract.
        cfg = Config("v", 1.0, 2.0, 3, tmp_path / "m")
        assert (cfg.voice, cfg.speed, cfg.max_seconds, cfg.wpm, cfg.muted_flag) == \
            ("v", 1.0, 2.0, 3, tmp_path / "m")
        assert cfg.events is None


class TestSocketPath:
    def test_uses_xdg_runtime_dir(self, monkeypatch):
        monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/4242")
        assert socket_path() == Path("/run/user/4242/tts.sock")

    def test_falls_back_when_unset(self, monkeypatch):
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        assert socket_path() == Path(f"/run/user/{os.getuid()}/tts.sock")

    def test_falls_back_when_empty(self, monkeypatch):
        monkeypatch.setenv("XDG_RUNTIME_DIR", "")
        assert socket_path() == Path(f"/run/user/{os.getuid()}/tts.sock")


class TestMuteFlagFilesystem:
    def test_toggle_creates_a_missing_parent_directory(self, tmp_path):
        flag = tmp_path / "nested" / "deeper" / "muted"
        cfg = Config("af_heart", 1.15, 45.0, 160, flag)
        d = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
                   player_factory=RecordingPlayer)
        d.handle({"cmd": "toggle"})
        assert flag.exists()
        assert d.status()["muted"] is True

    def test_the_flag_file_is_the_only_source_of_truth(self, tmp_path):
        """Deleting the flag by hand unmutes; the daemon holds no cached copy.

        This is what makes the mute state shared between the daemon and any
        other daemon or shell that looks at the file, so removing it behind our
        back must neither raise nor be overridden.
        """
        flag = tmp_path / "muted"
        cfg = Config("af_heart", 1.15, 45.0, 160, flag)
        d = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
                   player_factory=RecordingPlayer)
        d._set_muted(False)  # unmuting when there is nothing to remove
        assert d.status()["muted"] is False

        d.handle({"cmd": "toggle"})
        assert d.status()["muted"] is True
        flag.unlink()
        assert d.status()["muted"] is False
        d.handle({"cmd": "toggle"})  # inverts what is on disk now, so mutes again
        assert d.status()["muted"] is True
        assert flag.exists()

    def test_an_unwritable_flag_directory_does_not_crash_the_daemon(self, tmp_path):
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")
        cfg = Config("af_heart", 1.15, 45.0, 160, blocker / "muted")
        d = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
                   player_factory=RecordingPlayer)
        d.handle({"cmd": "toggle"})  # must not raise
        assert d.status()["muted"] is False


class TestSpeakingFlagFile:
    """The speaking flag exists for the tmux status line.

    It is read by scripts/tmux-tts-status.sh with shell builtins rather than by
    asking the daemon, because that script runs on every status tick and may
    not fork a Python interpreter to do it. So the file has to be an honest
    mirror of status()["speaking"], including at the two moments that are easy
    to get wrong: while the audio is still draining, and after a crash.
    """

    def _daemon(self, tmp_path, **player_kwargs):
        players = []

        def factory():
            players.append(SignallingPlayer(**player_kwargs))
            return players[-1]

        d = Daemon(StubEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True,
                   player_factory=factory)
        _worker(d)
        return d, players

    def test_the_flag_tracks_an_utterance_from_start_to_drain(self, tmp_path):
        d, players = self._daemon(tmp_path, block_close=True)
        flag = d.config.speaking_flag

        assert not flag.exists(), "flagged as speaking before anything was said"
        d.handle({"text": "Still playing.", "pane": "%4", "kind": "response"})
        assert _wait_for(lambda: flag.exists()), "no flag while speaking"
        assert players[0].entered_close.wait(2), "the player was never retired"
        assert flag.exists(), \
            "the flag was cleared while the audio was still draining"

        players[0].release_close.set()
        assert _wait_for(lambda: not flag.exists()), \
            "the flag outlived the audio it was describing"

    def test_a_stop_clears_the_flag_immediately(self, tmp_path):
        """The icon must go out when the user asks for silence, not after it."""
        d, players = self._daemon(tmp_path, block_close=True)
        flag = d.config.speaking_flag

        d.handle({"text": "Cut me off.", "pane": "%4", "kind": "response"})
        assert _wait_for(lambda: flag.exists()), "no flag while speaking"

        d.handle({"cmd": "stop"})
        assert not flag.exists(), "the flag survived a stop"

    def test_the_flag_mirrors_the_reported_speaking_state(self, tmp_path):
        d, players = self._daemon(tmp_path, block_close=True)
        flag = d.config.speaking_flag

        d.handle({"text": "Mirror me.", "pane": "%4", "kind": "response"})
        assert _wait_for(lambda: flag.exists())
        assert d.status()["speaking"] is True and flag.exists()

        players[0].release_close.set()
        assert _wait_for(lambda: d.status()["speaking"] is False)
        assert _wait_for(lambda: not flag.exists()), \
            "status() and the flag file disagreed"

    def test_serve_clears_a_flag_left_by_a_killed_daemon(self, tmp_path):
        """SIGTERM is unhandled, so the flag can only be cleaned up on startup.

        `systemctl stop` bypasses serve()'s finally entirely, which means a
        daemon that was speaking when it was stopped leaves the flag behind. If
        startup did not clear it, the status line would show a stuck speaking
        icon until the next utterance happened to end.
        """
        tmpdir = Path(tempfile.mkdtemp(prefix="ttsd-test-"))
        try:
            cfg = Config("af_heart", 1.15, 45.0, 160, tmpdir / "muted")
            cfg.speaking_flag.write_text("")  # the corpse of a previous daemon
            assert cfg.speaking_flag.exists()

            d = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
                       player_factory=RecordingPlayer)
            thread = threading.Thread(target=d.serve, args=(tmpdir / "s.sock",),
                                      daemon=True)
            thread.start()
            try:
                assert _wait_for(lambda: not cfg.speaking_flag.exists()), \
                    "a stale speaking flag survived a daemon restart"
            finally:
                d._stop_serving.set()
                thread.join(timeout=3)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_an_unwritable_flag_directory_does_not_crash_the_daemon(self, tmp_path):
        """Same contract as the mute flag: a broken path costs the icon, not speech."""
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")
        cfg = _config(tmp_path)
        cfg.speaking_flag = blocker / "speaking"
        player = RecordingPlayer()
        d = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
                   player_factory=lambda: player)

        d.handle({"text": "Speak anyway.", "pane": "%4", "kind": "response"})
        d.drain()  # must not raise

        assert player.written, "a broken flag path silenced the utterance"

    def test_transitions_poke_the_status_line(self, tmp_path):
        """Without the poke the icon is only as fresh as tmux's 5s tick."""
        pokes = []
        player = RecordingPlayer()
        d = Daemon(StubEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True,
                   player_factory=lambda: player,
                   status_poke=lambda: pokes.append(1))

        d.handle({"text": "Poke.", "pane": "%4", "kind": "response"})
        d.drain()

        assert pokes, "tmux was never told the speaking state had changed"


class TestPidFile:
    """Liveness for the status line, which cannot use the socket for it.

    An AF_UNIX socket file outlives the process that bound it and the daemon
    installs no SIGTERM handler, so after `systemctl stop` the socket is still
    sitting on disk. Only a pid can be checked against /proc.
    """

    def test_serve_publishes_our_pid(self):
        tmpdir = Path(tempfile.mkdtemp(prefix="ttsd-test-"))
        try:
            cfg = Config("af_heart", 1.15, 45.0, 160, tmpdir / "muted")
            d = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
                       player_factory=RecordingPlayer)
            thread = threading.Thread(target=d.serve, args=(tmpdir / "s.sock",),
                                      daemon=True)
            thread.start()
            try:
                assert _wait_for(lambda: cfg.pid_file.exists()), "no pid file"
                assert cfg.pid_file.read_text().strip() == str(os.getpid())
            finally:
                d._stop_serving.set()
                thread.join(timeout=3)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_an_unwritable_pid_path_does_not_stop_the_daemon(self, tmp_path):
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")
        cfg = _config(tmp_path)
        cfg.pid_file = blocker / "tts.pid"
        d = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: True,
                   player_factory=RecordingPlayer)

        d._write_pid_file()  # must not raise
        assert not cfg.pid_file.exists()


class TestOddMessages:
    def test_non_dict_message_is_ignored(self, daemon):
        d, _ = daemon
        for message in ([1, 2], "text", 7, None):
            d.handle(message)
        d.drain()
        assert d.engine.calls == []

    def test_non_string_text_is_ignored(self, daemon):
        d, _ = daemon
        d.handle({"text": 42, "pane": "%4"})
        d.drain()
        assert d.engine.calls == []

    def test_non_string_pane_is_coerced(self, tmp_path):
        seen = []
        cfg = _config(tmp_path)
        d = Daemon(StubEngine(), cfg,
                   focus_check=lambda pane, query=None: seen.append(pane) or True,
                   player_factory=RecordingPlayer)
        d.handle({"text": "Hello.", "pane": 4})
        assert seen == ["4"]

    def test_non_string_source_does_not_crash_the_notifier(self, tmp_path):
        sent = []
        cfg = _config(tmp_path)
        d = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: False,
                   player_factory=RecordingPlayer,
                   notifier=lambda title, body: sent.append((title, body)))
        d.handle({"text": "Hello.", "pane": "%2", "source": 3})
        assert sent == [("3", "Hello.")]

    def test_notification_body_is_truncated(self, tmp_path):
        sent = []
        cfg = _config(tmp_path)
        d = Daemon(StubEngine(), cfg, focus_check=lambda p, query=None: False,
                   player_factory=RecordingPlayer,
                   notifier=lambda title, body: sent.append((title, body)))
        d.handle({"text": "x" * 500, "pane": "%2"})
        assert len(sent[0][1]) == 200

    def test_non_string_voice_falls_back(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text("voice = 3\n")
        assert load_config(path).voice == "af_heart"

    def test_empty_voice_falls_back(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('voice = "   "\n')
        assert load_config(path).voice == "af_heart"


class TestUnboundedInput:
    def test_a_wall_of_text_does_not_become_one_giant_synthesis(self, tmp_path):
        """An unpunctuated response must not tie up the worker for minutes."""
        d = Daemon(StubEngine(), _config(tmp_path),
                   focus_check=lambda p, query=None: True,
                   player_factory=RecordingPlayer)
        d.handle({"text": "word " * 200_000, "pane": "%4"})
        d.drain()
        assert d.engine.calls
        # The bound applies to the input; prepare() then adds its short
        # "continues on screen" notice on top.
        assert max(len(c) for c in d.engine.calls) <= ttsd.MAX_TEXT_CHARS + 100

    def test_a_normal_response_is_untouched_by_the_bound(self, daemon):
        d, _ = daemon
        text = "The refactor is done. " * 40  # ~60s of speech, 880 chars
        d.handle({"text": text, "pane": "%4"})
        d.drain()
        assert d.engine.calls[0] == "The refactor is done."
        # Capped by the 45-second budget, not by the input bound.
        assert d.engine.calls[-1] == "continues on screen."
        assert len(d.engine.calls) == 31
