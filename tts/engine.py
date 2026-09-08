"""Speech synthesis backends.

KokoroEngine loads the ONNX model once and is reused for the daemon's lifetime;
loading takes seconds, which is the entire reason the daemon exists. StubEngine
lets the daemon's queueing, interruption, and focus behavior be tested without
touching the model or the sound card.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

import numpy as np

SAMPLE_RATE = 24000


def _compute_model_dir() -> Path:
    """Resolve the models directory.

    $TTS_MODEL_DIR overrides everything. Otherwise this follows $XDG_DATA_HOME
    the same way scripts/setup-tts.sh and tts/ttsd.py do, so a bootstrap run
    and the daemon always agree on where the models live. Factored into a
    function (rather than inlined at module scope) so tests can exercise the
    resolution logic against a patched environment without needing to reload
    the module.
    """
    override = os.environ.get("TTS_MODEL_DIR")
    if override:
        return Path(override)
    share = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local/share"))
    return share / "tts" / "models"


MODEL_DIR = _compute_model_dir()
MODEL_PATH = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = MODEL_DIR / "voices-v1.0.bin"


class Engine(Protocol):
    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """Return (float32 mono samples in [-1, 1], sample rate)."""
        ...


class KokoroEngine:
    def __init__(
        self,
        voice: str = "af_heart",
        speed: float = 1.15,
        model_path: Path = MODEL_PATH,
        voices_path: Path = VOICES_PATH,
    ) -> None:
        # Checked before the lazy import below so a missing model fails fast
        # with an actionable message, without first paying the ~2s cost of
        # importing kokoro_onnx (and without requiring kokoro_onnx to be
        # installed at all just to report that the model is missing).
        # Both files, not just the model: a truncated or absent voices file
        # otherwise surfaces as a kokoro_onnx traceback from deep inside the
        # library, where what the user needs to be told is "run the setup
        # script". setup-tts.sh downloads them separately, so either one can be
        # the missing half.
        for name, path in (("model", model_path), ("voices file", voices_path)):
            if not path.exists():
                raise FileNotFoundError(
                    f"Kokoro {name} missing at {path}. Run scripts/setup-tts.sh."
                )

        from kokoro_onnx import Kokoro  # imported lazily: ~2s and only the daemon needs it

        self._kokoro = Kokoro(str(model_path), str(voices_path))
        self._voice = voice
        self._speed = speed

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        samples, rate = self._kokoro.create(
            text, voice=self._voice, speed=self._speed, lang="en-us"
        )
        return np.asarray(samples, dtype=np.float32), rate


class StubEngine:
    """Records what it was asked to say and returns proportional silence."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        self.calls.append(text)
        seconds = max(len(text.split()), 1) * 0.05
        return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.float32), SAMPLE_RATE
