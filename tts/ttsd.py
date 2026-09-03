"""The speaking daemon.

Holds the model warm, because loading it costs seconds and an alert that
arrives seconds late has already been overtaken by looking at the screen.
Synthesis runs sentence by sentence on a worker thread and is streamed into a
paplay subprocess, so audio begins after the first sentence and interruption is
just killing that subprocess.

Three threads meet here. The socket thread accepts messages and must always
return promptly: a full AF_UNIX backlog makes the next connect() block rather
than fail, so an accept loop parked in a subprocess reaches all the way back
into the agent whose hook is trying to connect. It therefore does nothing but
bookkeeping — commands are applied in place, since they only set flags and
kill a subprocess, and an utterance goes onto the intake queue. The intake
thread decides what becomes of that utterance: both the tmux focus query and
the desktop notification fork a subprocess, and neither may be waited on by
the accept loop. The worker thread does the rest — synthesis (hundreds of
milliseconds), writing into paplay (which blocks in real time once the pipe
fills), and waiting for the audio to drain at the end of an utterance. None of
that may happen under a lock, so the lock protects only the bookkeeping: the
generation counter, the installed and retiring players, and the speaking flag.
See _claim_playback for the one subtle consequence.
"""

from __future__ import annotations

import json
import queue
import socket
import subprocess
import sys
import threading
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from tts.engine import SAMPLE_RATE, Engine, KokoroEngine
from tts.focus import is_focused
from tts.paths import share_dir as _share_dir, socket_path
from tts.speech import clean_for_speech, prepare, split_sentences

DEFAULT_CONFIG = Path.home() / ".config/tts/config.toml"

# How long a connected client may stay silent before the daemon hangs up. The
# accept loop is single-threaded on purpose — handling a message really is
# microseconds of bookkeeping, now that the focus query and the notification
# happen on the intake thread — so an idle client is the one thing that could
# stall it.
CLIENT_TIMEOUT = 1.0

# How many utterances may be waiting on the intake thread. Reaching this means
# something upstream is wedged (a hung tmux, a stalled notification daemon) and
# the right answer is to drop narration rather than let a hostile or broken
# client grow the daemon's memory a megabyte at a time.
INTAKE_BACKLOG = 64

# Once a client has been served, how long to wait for a follow-up message on
# the same connection before hanging up. Long enough not to truncate a client
# that batches, short enough that a client which forgets to close costs the
# next hook nothing worth noticing.
IDLE_TIMEOUT = 0.05

# Forty-five seconds of speech is roughly 120 words, so this is more than an
# order of magnitude of headroom. The point is only to bound the worker: an
# unpunctuated wall of text survives prepare() as a single "sentence", and
# handing that to Kokoro whole would tie up synthesis for minutes, during which
# an interruption cannot take effect because the generation is only rechecked
# once synthesis returns.
MAX_TEXT_CHARS = 20_000

# A message is one line of JSON. Anything past this is a client malfunctioning
# or a hostile one, and either way must not grow the daemon's memory.
MAX_MESSAGE_BYTES = 1 << 20

# How long to wait for paplay to exit once its stdin has been closed. Reaching
# this means the sink is wedged, not that the audio was long: at retirement the
# only sound left is what the pipe and PulseAudio still hold, a couple of
# seconds at most. The bound exists so a stuck sink cannot park the worker
# thread forever.
DRAIN_TIMEOUT = 30.0

# Wakeup interval for the accept loop, so serve() can notice a shutdown request.
_ACCEPT_POLL = 0.5

# Private sentinel: putting it on the queue retires the worker thread. Only
# tests use it; the real daemon runs until the process dies.
_STOP = object()

# Which [events] flag in config.toml governs each (source, kind) pair the hook
# adapters can send. The names are the harness's own event names rather than
# this daemon's vocabulary, because that is what the user is turning off: the
# Claude Stop hook, the Claude Notification hook, and Codex's two. A pair with
# no flag here is not configurable and always speaks.
EVENT_FLAGS = {
    ("claude", "response"): "claude_stop",
    ("claude", "permission"): "claude_notification",
    ("codex", "response"): "codex_stop",
    ("codex", "permission"): "codex_permission",
}


def _warn(message: str) -> None:
    print(f"ttsd: {message}", file=sys.stderr, flush=True)


@dataclass
class Config:
    voice: str = "af_heart"
    speed: float = 1.15
    max_seconds: float = 45.0
    wpm: int = 160
    muted_flag: Path = field(default_factory=lambda: _share_dir() / "muted")
    events: dict | None = None


def _as_voice(value) -> str:
    # str() would happily turn 3 into "3", which Kokoro then rejects on every
    # single sentence. Better to notice the mistake once, at startup.
    if not isinstance(value, str) or not value.strip():
        raise ValueError(value)
    return value


def _coerce(data: dict, key: str, cast, default):
    """Read one config key, falling back to the default if it is unusable.

    A typo in config.toml should cost the user that one setting, not the whole
    daemon: this is read at startup, and a daemon that refuses to boot is a
    much worse failure than one that speaks at the default speed.
    """
    if key not in data:
        return default
    try:
        return cast(data[key])
    except (TypeError, ValueError):
        _warn(f"ignoring invalid {key!r} in config; using {default!r}")
        return default


def load_config(path: Path | None = None) -> Config:
    path = path or DEFAULT_CONFIG
    data: dict = {}
    try:
        if path.exists():
            with path.open("rb") as fh:
                data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        _warn(f"could not read {path}: {exc}; using defaults")
        data = {}
    if not isinstance(data, dict):
        data = {}

    events = data.get("events", {})
    if not isinstance(events, dict):
        _warn("ignoring invalid [events] table in config")
        events = {}
    # Only booleans mean anything here, and a flag that is silently ignored is
    # worse than one that is loudly rejected: the user turns an event off, the
    # daemon keeps speaking, and nothing says why. Rejected once at startup
    # rather than per message.
    for name in [k for k, v in events.items() if not isinstance(v, bool)]:
        _warn(f"ignoring non-boolean {name!r} in [events]; expected true or false")
        del events[name]
    for name in [k for k in events if k not in EVENT_FLAGS.values()]:
        _warn(f"ignoring unknown {name!r} in [events]")
        del events[name]

    return Config(
        voice=_coerce(data, "voice", _as_voice, "af_heart"),
        speed=_coerce(data, "speed", float, 1.15),
        max_seconds=_coerce(data, "max_seconds", float, 45.0),
        wpm=_coerce(data, "wpm", int, 160),
        muted_flag=_share_dir() / "muted",
        events=events,
    )


def notify(title: str, body: str) -> None:
    """Desktop fallback for sessions that are not in view.

    Spawned and forgotten. Nothing here reads notify-send's output or cares
    whether it succeeded, and waiting on it only creates a way for a wedged
    notification daemon to stall the thread that called this — which is the
    exact scenario this feature invites, with several unfocused agents all
    routed here at once. Nothing pipes its output either: an unread pipe fills
    and blocks the very process this refuses to wait for.
    """
    try:
        subprocess.Popen(
            ["notify-send", "-u", "normal", "-i", "audio-speakers", "-a", title, title, body],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        pass


class PaplayPlayer:
    """A single paplay subprocess consuming raw PCM until killed."""

    def __init__(self) -> None:
        self._proc = subprocess.Popen(
            ["paplay", "--raw", f"--rate={SAMPLE_RATE}", "--format=s16le", "--channels=1"],
            stdin=subprocess.PIPE,
        )

    def write(self, samples: np.ndarray, rate: int) -> None:
        if self._proc.stdin is None:
            return
        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
        try:
            self._proc.stdin.write(pcm)
            self._proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            pass  # killed mid-write by an interruption; expected
        # Any other OSError is a player failing for a reason of its own, and
        # is deliberately not caught: swallowing it loses the rest of the
        # utterance in silence, where letting it out retires the broken player
        # and says so.

    def close(self) -> None:
        """Retire at the end of an utterance: stop feeding, then let it finish.

        write() returns as soon as the pipe accepts the bytes, so paplay is
        still playing when the last sentence has been handed over. Closing
        stdin is its EOF, and wait() blocks until it has played what it holds
        -- which is exactly why this runs on the worker thread and never under
        the lock. kill() is the opposite path: immediate, and lossy on purpose.
        """
        try:
            if self._proc.stdin:
                self._proc.stdin.close()  # write() flushes, so this cannot block
        except (OSError, ValueError):
            pass  # already dead, or already closed
        try:
            self._proc.wait(timeout=DRAIN_TIMEOUT)
        except subprocess.TimeoutExpired:
            _warn("paplay did not exit after its input closed; killing it")
            self.kill()
        except (OSError, ValueError):
            pass

    def kill(self) -> None:
        # Kill before closing stdin, not after. close() flushes, and flushing a
        # pipe that paplay has not drained yet blocks — which would make an
        # interruption wait for the audio it is trying to cut short. Killing
        # first guarantees the flush fails fast with a broken pipe instead.
        try:
            self._proc.kill()
        except (OSError, ValueError):
            pass
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
        except (OSError, ValueError):
            pass


class _Playback:
    """One player instance, bound to the utterance that created it.

    There are two ways out and the difference is the whole point. kill() is
    terminal and never blocks: the socket thread calls it while the worker may
    be parked inside write(), and killing paplay is precisely what unblocks
    that write. retire() is the end-of-utterance path and does block, on the
    worker thread, until the sound already handed to paplay has finished.

    Either way `done` is set before the process is touched, so a write that
    arrives afterwards is dropped rather than delivered — a superseded
    utterance cannot become audible even if the worker had already decided to
    write it. kill() stays available after retire() has started, because an
    interruption landing mid-drain must still cut the audio short, and killing
    the process is what ends the wait inside retire().
    """

    __slots__ = ("player", "generation", "done", "killed")

    def __init__(self, player, generation: int) -> None:
        self.player = player
        self.generation = generation
        self.done = False  # no further writes may reach the player
        self.killed = False  # kill() has already run

    def write(self, samples, rate) -> None:
        if self.done:
            return
        self.player.write(samples, rate)

    def kill(self) -> None:
        self.done = True
        if self.killed:
            return
        self.killed = True
        self.player.kill()

    def retire(self) -> None:
        if self.done:
            return  # already killed; there is nothing left to drain
        self.done = True
        self.player.close()


class Daemon:
    def __init__(
        self,
        engine: Engine,
        config: Config,
        focus_check=is_focused,
        player_factory=PaplayPlayer,
        notifier=notify,
    ) -> None:
        self.engine = engine
        self.config = config
        self._focus_check = focus_check
        self._player_factory = player_factory
        self._notify = notifier
        self._work: queue.Queue = queue.Queue()
        self._intake: queue.Queue = queue.Queue(maxsize=INTAKE_BACKLOG)
        self._playback: _Playback | None = None
        self._retiring: _Playback | None = None
        self._speaking = False
        self._generation = 0
        # Bumped only by an explicit stop/mute, never by "newest utterance
        # wins". An utterance that was already in flight when the user asked
        # for silence checks this before it queues any audio.
        self._stop_epoch = 0
        self._lock = threading.Lock()
        self._server: socket.socket | None = None
        self._stop_serving = threading.Event()
        self._player_broken = False

    # ---- state -------------------------------------------------------

    @property
    def muted(self) -> bool:
        try:
            return self.config.muted_flag.exists()
        except OSError:
            return False

    def _set_muted(self, value: bool) -> None:
        try:
            self.config.muted_flag.parent.mkdir(parents=True, exist_ok=True)
            if value:
                self.config.muted_flag.touch()
            else:
                self.config.muted_flag.unlink(missing_ok=True)
        except OSError as exc:
            _warn(f"could not update {self.config.muted_flag}: {exc}")

    def status(self) -> dict:
        with self._lock:
            speaking = self._speaking
        return {
            "muted": self.muted,
            "speaking": speaking,
            "voice": self.config.voice,
            "queued": self._work.qsize() + self._intake.qsize(),
        }

    # ---- message handling --------------------------------------------

    def _event_enabled(self, source, kind) -> bool:
        """Is this (source, kind) turned on in config.toml's [events] table?

        Enabled unless the file says otherwise: an absent flag, an absent
        table, and a pair that has no flag at all all mean "speak". Turning
        something off is the deliberate act, and it should not be possible to
        lose narration by mistyping a key -- load_config discards anything it
        does not recognise, so an unknown name never silences an event.
        """
        if not isinstance(source, str) or not isinstance(kind, str):
            return True  # unattributed message: not something the table covers
        flag = EVENT_FLAGS.get((source, kind))
        if flag is None:
            return True
        return (self.config.events or {}).get(flag, True)

    def handle(self, message: dict) -> None:
        if not isinstance(message, dict):
            return  # arrived over a socket: assume nothing about its shape

        cmd = message.get("cmd")
        if cmd == "stop":
            self._cancel_pending()
            self.stop_speaking()
            return
        if cmd == "toggle":
            self._set_muted(not self.muted)
            if self.muted:
                self._cancel_pending()
                self.stop_speaking()
            return
        if cmd == "status":
            return
        if cmd is not None:
            return  # unknown command: ignore rather than crash the daemon

        text = message.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return
        if not self._event_enabled(message.get("source"), message.get("kind")):
            return  # turned off in config.toml: no speech, and no notification
        if self.muted:
            return

        # Snapshot before the focus check, which forks tmux and can take
        # seconds if tmux is wedged. A stop landing inside that window has to
        # win: this message reached the daemon first, but the user asked for
        # silence second, and the later instruction is the one they meant.
        with self._lock:
            epoch = self._stop_epoch

        pane = message.get("pane")
        if pane is not None and not isinstance(pane, str):
            pane = str(pane)
        if not self._focus_check(pane):
            source = message.get("source") or "agent"
            # Cleaned, not raw. A notification body is read, but it is read at
            # a glance from the corner of a screen, and raw markdown spends
            # that glance on backticks, fences and absolute paths. The same
            # transforms that make this speakable make it skimmable, and they
            # are pure functions sitting right here.
            body = clean_for_speech(text[:MAX_TEXT_CHARS]).strip()
            self._notify(str(source).capitalize(), body[:200] or text.strip()[:200])
            return

        spoken = prepare(text[:MAX_TEXT_CHARS], self.config.max_seconds, self.config.wpm)
        if not spoken:
            return

        self.stop_speaking()  # newest utterance wins
        with self._lock:
            if epoch != self._stop_epoch:
                return  # silenced while we were deciding; queue nothing
            self._generation += 1
            generation = self._generation
        for sentence in split_sentences(spoken):
            self._work.put((generation, sentence))

    def stop_speaking(self) -> None:
        # Bumping the generation first is what makes this safe: any worker that
        # has not yet committed a player will fail its commit check and clean
        # up after itself, so no player can outlive this call.
        with self._lock:
            self._generation += 1
            playback, self._playback = self._playback, None
            retiring, self._retiring = self._retiring, None
            self._speaking = False
        self._drop_queued()
        # Outside the lock; kill must never wait on one. The retiring player is
        # killed too: an interruption that arrives while the tail of the last
        # utterance is still draining has to cut it off, and this is also what
        # releases the worker from the wait inside _retire_playback.
        for victim in (playback, retiring):
            if victim is not None:
                victim.kill()

    def _drop_queued(self) -> None:
        while True:
            try:
                item = self._work.get_nowait()
            except queue.Empty:
                return
            if item is _STOP:
                self._work.put(_STOP)  # a shutdown request is not stale work
                return

    def _cancel_pending(self) -> None:
        """Drop utterances that have been accepted but not yet turned into audio.

        Only an explicit `tts stop` or a mute calls this -- never the
        "newest utterance wins" path, which must leave messages queued behind
        it alone precisely because they are newer than the one arriving.

        Moving handle() off the accept loop put a queue between the socket and
        the decision to speak, and a queue is somewhere a stop can be overtaken:
        the accept thread answers the stop immediately while the intake thread
        is still parked in a focus check for a message that arrived first, and
        that message would then start talking after the user asked for silence.
        Bumping the epoch closes the in-flight case, draining closes the queued
        one. `tts stop` is specified as "silence immediately, drop pending", and
        these are the pending.
        """
        with self._lock:
            self._stop_epoch += 1
        while True:
            try:
                item = self._intake.get_nowait()
            except queue.Empty:
                return
            if item is _STOP:
                self._intake.put(_STOP)  # a shutdown request is not stale work
                return

    # ---- synthesis ---------------------------------------------------

    def _claim_playback(self, generation: int) -> _Playback | None:
        """Return the player this utterance may write to, or None if superseded.

        The player is created outside the lock and only then committed under
        it. Creating it under the lock would be simpler, but spawning paplay is
        not instant and stop_speaking() would have to queue behind it — and a
        stop that waits is a stop the user hears as lag. Creating it outside
        means a stop can land mid-spawn, which is exactly why the commit
        re-checks the generation and kills the loser.
        """
        with self._lock:
            if generation != self._generation:
                return None
            if self._playback is not None:
                self._speaking = True
                return self._playback

        try:
            candidate = _Playback(self._player_factory(), generation)
        except (OSError, subprocess.SubprocessError) as exc:
            if not self._player_broken:
                self._player_broken = True
                _warn(f"cannot start audio playback: {exc}")
            return None

        result = None
        loser = None
        with self._lock:
            if generation != self._generation:
                loser = candidate  # superseded while we were spawning
            elif self._playback is None:
                self._playback = candidate
                self._speaking = True
                result = candidate
            else:
                loser = candidate  # somebody else installed one first
                result = self._playback
                self._speaking = True
        if loser is not None:
            loser.kill()
        return result

    def _discard_playback(self, generation: int) -> None:
        """Retire a player that failed mid-utterance, if it is still current."""
        with self._lock:
            playback = self._playback
            if playback is None or playback.generation != generation:
                return
            self._playback = None
            self._speaking = False
        playback.kill()

    def _retire_playback(self) -> None:
        """Let the current player finish its audio and exit, then forget it.

        Called from the worker thread when the queue drains. Without this the
        paplay process installed by the first utterance lives forever: nothing
        else clears self._playback, so it holds the output sink open — and an
        open sink is a device that never suspends and a laptop that never stops
        drawing power for it.

        Killing here would be wrong. write() returns as soon as the pipe
        accepts the bytes, so audio is still playing when the queue empties;
        cutting it off would truncate the tail of every utterance. So this
        closes stdin and waits, which is slow by definition and therefore never
        runs under the lock. The player moves to _retiring first, where
        stop_speaking() can still find and kill it: an interruption must stay
        instant even while the previous utterance is draining.
        """
        with self._lock:
            playback, self._playback = self._playback, None
            if playback is None:
                self._speaking = False
                return
            self._retiring = playback
        try:
            playback.retire()
        finally:
            with self._lock:
                if self._retiring is playback:
                    self._retiring = None
                    self._speaking = False

    def _speak_one(self, generation: int, sentence: str) -> None:
        with self._lock:
            if generation != self._generation:
                return  # superseded while queued
        samples, rate = self.engine.synthesize(sentence)  # slow: never under the lock
        playback = self._claim_playback(generation)
        if playback is None:
            return  # superseded during synthesis, or playback is unavailable
        playback.write(samples, rate)  # blocks in real time: also never under the lock

    def _speak_one_safely(self, generation: int, sentence: str) -> None:
        try:
            self._speak_one(generation, sentence)
        except Exception as exc:  # noqa: BLE001 - one bad sentence must not end the daemon
            _warn(f"failed to speak {sentence!r}: {exc}")
            self._discard_playback(generation)

    def drain(self) -> None:
        """Process everything queued. Used by tests; run_worker is the real path.

        Deliberately does not retire the player the way run_worker does: this
        is the synchronous path, and several tests interrupt playback after
        draining, which needs a player still installed to interrupt. Retirement
        is a property of the worker loop's idle transition and is tested there,
        on a real thread.
        """
        while True:
            try:
                item = self._work.get_nowait()
            except queue.Empty:
                break
            if item is _STOP:
                continue
            self._speak_one_safely(*item)
        with self._lock:
            self._speaking = False

    def run_intake(self) -> None:
        """Turn accepted messages into queued speech, off the accept loop.

        handle() forks tmux to ask whether the pane is in view and forks
        notify-send when it is not, and the accept loop may not wait on either.
        It gets its own thread rather than being folded into the worker: the
        worker spends most of an utterance blocked inside paplay, so a new
        message reaching it would only be examined once the previous utterance
        had finished playing — and "newest utterance wins" would stop meaning
        anything.
        """
        while True:
            message = self._intake.get()
            if message is _STOP:
                return
            try:
                self.handle(message)
            except Exception as exc:  # noqa: BLE001 - one bad message, not the daemon
                _warn(f"failed to handle message: {exc}")

    def run_worker(self) -> None:
        while True:
            item = self._work.get()
            if item is _STOP:
                # Shutting down: cut the audio rather than drain it, so a
                # stopping daemon never leaves a paplay behind it.
                self.stop_speaking()
                return
            self._speak_one_safely(*item)
            if self._work.empty():
                self._retire_playback()

    # ---- socket ------------------------------------------------------

    def _bind(self, path: Path) -> socket.socket:
        if path.exists():
            if _socket_is_live(path):
                raise RuntimeError(f"another ttsd is already listening on {path}")
            path.unlink()  # stale socket from a daemon that died
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        path.chmod(0o600)
        server.listen(16)
        server.settimeout(_ACCEPT_POLL)
        return server

    def serve(self, path: Path) -> None:
        server = self._bind(path)
        self._server = server
        worker = threading.Thread(target=self.run_worker, daemon=True)
        worker.start()
        intake = threading.Thread(target=self.run_intake, daemon=True)
        intake.start()
        try:
            while not self._stop_serving.is_set():
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue  # poll so shutdown is noticed
                except OSError as exc:
                    _warn(f"accept failed: {exc}")
                    break
                with conn:
                    self._serve_connection(conn)
        finally:
            self._stop_serving.set()
            try:
                self._intake.put_nowait(_STOP)
            except queue.Full:
                pass  # wedged intake; it is a daemon thread and dies with us
            self._work.put(_STOP)
            server.close()
            self._server = None
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def _serve_connection(self, conn: socket.socket) -> None:
        """Read newline-delimited JSON from one client.

        recv boundaries have nothing to do with message boundaries, so this
        buffers until a newline rather than trusting a single read. The accept
        loop serves one client at a time, so both timeouts matter: a client
        that connects and says nothing gets a second, and one that has already
        been served gets only long enough to send a follow-up before we hang up
        on it.
        """
        conn.settimeout(CLIENT_TIMEOUT)
        buffer = b""
        handled = False
        try:
            while True:
                try:
                    chunk = conn.recv(65536)
                except (socket.timeout, OSError):
                    return
                if not chunk:
                    break  # client closed; anything left is a partial message
                buffer += chunk
                if len(buffer) > MAX_MESSAGE_BYTES:
                    _warn("dropping oversized message")
                    buffer = b""  # so the flush below does not speak it anyway
                    return
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        self._dispatch(conn, line)
                        handled = True
                if handled:
                    conn.settimeout(IDLE_TIMEOUT)
        finally:
            # A client that closed without a trailing newline still meant it.
            if not handled and buffer.strip():
                self._dispatch(conn, buffer)

    def _dispatch(self, conn: socket.socket, raw: bytes) -> None:
        try:
            message = json.loads(raw.decode("utf-8", "replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        if not isinstance(message, dict):
            return
        if message.get("cmd") == "status":
            try:
                conn.sendall((json.dumps(self.status()) + "\n").encode())
            except OSError:
                pass  # client hung up before reading; not our problem
            return
        if message.get("cmd") is not None:
            # Commands stay on this thread. stop and toggle are flag writes and
            # a kill(), which is the whole point of them: `tts stop` queued
            # behind an utterance would not be a stop.
            try:
                self.handle(message)
            except Exception as exc:  # noqa: BLE001 - a bad message, not the daemon
                _warn(f"failed to handle message: {exc}")
            return
        # An utterance. Deciding what to do with it means forking tmux and
        # possibly notify-send, and this thread is the one every hook's
        # connect() is waiting behind, so it only hands the message over.
        try:
            self._intake.put_nowait(message)
        except queue.Full:
            _warn("intake backlog full; dropping an utterance")


def _socket_is_live(path: Path) -> bool:
    """True if something is already accepting on this socket."""
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.settimeout(0.5)
    try:
        probe.connect(str(path))
    except OSError:
        return False
    finally:
        probe.close()
    return True


def main() -> int:
    config = load_config()
    try:
        engine = KokoroEngine(voice=config.voice, speed=config.speed)
    except FileNotFoundError as exc:
        _warn(str(exc))
        return 1
    try:
        Daemon(engine, config).serve(socket_path())
    except (RuntimeError, OSError) as exc:
        _warn(str(exc))
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
