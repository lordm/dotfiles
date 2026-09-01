import numpy as np
import pytest

from tts.engine import StubEngine, SAMPLE_RATE


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
