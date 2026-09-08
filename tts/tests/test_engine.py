import numpy as np
import pytest

from tts.engine import StubEngine, SAMPLE_RATE, _compute_model_dir


class TestStubEngine:
    def test_records_calls_in_order(self):
        e = StubEngine()
        e.synthesize("one")
        e.synthesize("two")
        assert e.calls == ["one", "two"]

    def test_returns_silence_at_engine_sample_rate(self):
        samples, rate = StubEngine().synthesize("hello")
        assert rate == SAMPLE_RATE
        assert isinstance(samples, np.ndarray)
        assert samples.dtype == np.float32

    def test_duration_scales_with_text_length(self):
        short, _ = StubEngine().synthesize("hi")
        long, _ = StubEngine().synthesize("hi there friend how are you")
        assert len(long) > len(short)

    def test_returns_mono_1d_array(self):
        # KokoroEngine.synthesize returns a 1D mono array (see Step 6/8 smoke
        # tests). Task 4's playback path is written against that shape, so the
        # stub must match it exactly or a mismatch only surfaces as broken
        # audio much later.
        samples, _ = StubEngine().synthesize("hello there")
        assert samples.ndim == 1


class TestKokoroEngineMissingModel:
    def test_missing_model_raises_file_not_found(self, tmp_path):
        # This must not require kokoro-onnx to be importable: the check for
        # the model file has to happen before the lazy `import kokoro_onnx`,
        # both so the error message is reachable in this system-Python test
        # environment (kokoro-onnx only lives in the tts venv) and so a
        # missing model fails fast in production without paying the ~2s
        # import cost first.
        from tts.engine import KokoroEngine

        with pytest.raises(FileNotFoundError):
            KokoroEngine(
                model_path=tmp_path / "missing.onnx",
                voices_path=tmp_path / "missing-voices.bin",
            )

    def test_a_missing_voices_file_is_reported_the_same_way(self, tmp_path):
        """The two files are downloaded separately, so either can be the gap.

        Checking only the model left a missing or truncated voices file to
        surface as a kokoro_onnx traceback from inside the library, when what
        the user needs to be told is which file is missing and which script
        fetches it.
        """
        from tts.engine import KokoroEngine

        model = tmp_path / "kokoro-v1.0.onnx"
        model.write_bytes(b"not really a model, but present")

        with pytest.raises(FileNotFoundError) as raised:
            KokoroEngine(model_path=model, voices_path=tmp_path / "voices-v1.0.bin")

        assert "voices" in str(raised.value)
        assert "setup-tts.sh" in str(raised.value)


class TestModelDirResolution:
    """MODEL_DIR/MODEL_PATH/VOICES_PATH are computed once at import time, so
    these tests exercise the resolution function directly against a patched
    environment rather than the module-level constants (which would not
    observe env changes made after import).
    """

    def test_honors_xdg_data_home(self, tmp_path, monkeypatch):
        # scripts/setup-tts.sh and tts/ttsd.py both derive their share
        # directory from $XDG_DATA_HOME; engine.py must resolve to the same
        # place or a clean bootstrap silently installs into a directory the
        # daemon never looks in.
        monkeypatch.delenv("TTS_MODEL_DIR", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

        model_dir = _compute_model_dir()

        assert model_dir == tmp_path / "tts" / "models"

    def test_tts_model_dir_overrides_xdg_data_home(self, tmp_path, monkeypatch):
        override = tmp_path / "custom-models"
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "unused-xdg"))
        monkeypatch.setenv("TTS_MODEL_DIR", str(override))

        assert _compute_model_dir() == override

    def test_defaults_to_home_local_share_without_xdg_data_home(self, monkeypatch):
        from pathlib import Path

        monkeypatch.delenv("TTS_MODEL_DIR", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)

        assert _compute_model_dir() == Path.home() / ".local/share" / "tts" / "models"
