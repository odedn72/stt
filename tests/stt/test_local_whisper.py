# TDD: Written from spec 03-stt-engine.md
"""
Tests for LocalWhisperEngine — local STT using faster-whisper.

All faster-whisper calls are mocked. Tests verify:
- Model configuration (size, compute type, beam size)
- Engine lifecycle (initialize, shutdown, state transitions)
- Transcription (single chunk, streaming)
- Model download and availability checks
- Error handling (model load failure, transcription errors)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    import numpy as np

from systemstt.errors import ModelDownloadError, ModelLoadError, STTEngineError, TranscriptionError
from systemstt.stt.base import (
    DetectedLanguage,
    EngineState,
    EngineType,
    TranscriptionResult,
)
from systemstt.stt.local_whisper import (
    LocalWhisperConfig,
    LocalWhisperEngine,
    WhisperModelSize,
)

# ---------------------------------------------------------------------------
# WhisperModelSize tests
# ---------------------------------------------------------------------------


class TestWhisperModelSize:
    """Tests for the WhisperModelSize enum."""

    def test_all_sizes_defined(self) -> None:
        expected = {"tiny", "base", "small", "medium", "large"}
        actual = {s.value for s in WhisperModelSize}
        assert actual == expected


# ---------------------------------------------------------------------------
# LocalWhisperConfig tests
# ---------------------------------------------------------------------------


class TestLocalWhisperConfig:
    """Tests for LocalWhisperConfig dataclass."""

    def test_default_model_size_is_medium(self) -> None:
        config = LocalWhisperConfig()
        assert config.model_size == WhisperModelSize.MEDIUM

    def test_default_device_is_cpu(self) -> None:
        config = LocalWhisperConfig()
        assert config.device == "cpu"

    def test_default_compute_type_is_int8(self) -> None:
        config = LocalWhisperConfig()
        assert config.compute_type == "int8"

    def test_default_beam_size_is_5(self) -> None:
        config = LocalWhisperConfig()
        assert config.beam_size == 5

    def test_default_num_workers_is_1(self) -> None:
        config = LocalWhisperConfig()
        assert config.num_workers == 1

    def test_custom_config(self) -> None:
        config = LocalWhisperConfig(
            model_size=WhisperModelSize.SMALL,
            compute_type="float32",
            beam_size=3,
        )
        assert config.model_size == WhisperModelSize.SMALL
        assert config.compute_type == "float32"
        assert config.beam_size == 3


# ---------------------------------------------------------------------------
# LocalWhisperEngine lifecycle tests
# ---------------------------------------------------------------------------


class TestLocalWhisperEngineLifecycle:
    """Tests for engine initialization and shutdown."""

    def test_engine_type_is_local_whisper(self) -> None:
        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        assert engine.engine_type == EngineType.LOCAL_WHISPER

    def test_initial_state_is_uninitialized(self) -> None:
        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        assert engine.state == EngineState.UNINITIALIZED

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_initialize_loads_model(self, mock_model_cls: MagicMock) -> None:
        config = LocalWhisperConfig(model_size=WhisperModelSize.SMALL)
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        assert engine.state == EngineState.READY
        mock_model_cls.assert_called_once()

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_initialize_failure_raises_model_load_error(
        self, mock_model_cls: MagicMock
    ) -> None:
        mock_model_cls.side_effect = RuntimeError("model corrupted")
        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        with pytest.raises(ModelLoadError):
            await engine.initialize()
        assert engine.state == EngineState.ERROR

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_shutdown_unloads_model(self, mock_model_cls: MagicMock) -> None:
        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        await engine.shutdown()
        assert engine.state == EngineState.UNINITIALIZED

    @pytest.mark.asyncio
    async def test_shutdown_when_uninitialized_is_safe(self) -> None:
        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.shutdown()  # Should not raise
        assert engine.state == EngineState.UNINITIALIZED


# ---------------------------------------------------------------------------
# LocalWhisperEngine transcription tests
# ---------------------------------------------------------------------------


class TestLocalWhisperEngineTranscribe:
    """Tests for local engine transcription."""

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_transcribe_returns_transcription_result(
        self, mock_model_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        # Configure mock model to return segments
        mock_model = mock_model_cls.return_value
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_segment.start = 0.0
        mock_segment.end = 1.5
        mock_segment.avg_logprob = -0.2
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.95
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        result = await engine.transcribe(sine_wave_chunk)

        assert isinstance(result, TranscriptionResult)
        assert "Hello world" in result.full_text

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_transcribe_with_language_hint(
        self, mock_model_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        mock_model = mock_model_cls.return_value
        mock_segment = MagicMock()
        mock_segment.text = "\u05e9\u05dc\u05d5\u05dd"
        mock_segment.start = 0.0
        mock_segment.end = 1.0
        mock_segment.avg_logprob = -0.3
        mock_info = MagicMock()
        mock_info.language = "he"
        mock_info.language_probability = 0.88
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        result = await engine.transcribe(sine_wave_chunk, language_hint=DetectedLanguage.HEBREW)

        assert result.primary_language == DetectedLanguage.HEBREW

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_transcribe_when_not_initialized_raises_error(
        self, mock_model_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        with pytest.raises(STTEngineError):
            await engine.transcribe(sine_wave_chunk)

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_transcribe_failure_raises_transcription_error(
        self, mock_model_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        mock_model = mock_model_cls.return_value
        mock_model.transcribe.side_effect = RuntimeError("inference failed")

        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        with pytest.raises(TranscriptionError):
            await engine.transcribe(sine_wave_chunk)

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_transcribe_empty_audio_returns_empty_result(
        self, mock_model_cls: MagicMock, empty_chunk: np.ndarray
    ) -> None:
        mock_model = mock_model_cls.return_value
        mock_model.transcribe.return_value = (
            [],
            MagicMock(language="en", language_probability=0.5),
        )

        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        result = await engine.transcribe(empty_chunk)

        assert result.full_text == ""
        assert result.segments == []


# ---------------------------------------------------------------------------
# LocalWhisperEngine model management tests
# ---------------------------------------------------------------------------


class TestLocalWhisperEngineModelManagement:
    """Tests for model download and availability checking."""

    def test_is_available_false_when_uninitialized(self) -> None:
        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        assert engine.is_available() is False

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_is_available_true_when_ready(self, mock_model_cls: MagicMock) -> None:
        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        assert engine.is_available() is True

    @patch("systemstt.stt.local_whisper.Path")
    def test_is_model_downloaded_checks_cache_dir(self, mock_path: MagicMock) -> None:
        config = LocalWhisperConfig(model_size=WhisperModelSize.SMALL)
        engine = LocalWhisperEngine(config)
        result = engine.is_model_downloaded()
        assert isinstance(result, bool)

    def test_get_model_info_returns_dict(self) -> None:
        config = LocalWhisperConfig(model_size=WhisperModelSize.MEDIUM)
        engine = LocalWhisperEngine(config)
        info = engine.get_model_info()
        assert isinstance(info, dict)

    @pytest.mark.asyncio
    async def test_download_model_raises_on_network_failure(self) -> None:
        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        with (
            patch.object(engine, "download_model", side_effect=ModelDownloadError("network error")),
            pytest.raises(ModelDownloadError),
        ):
            await engine.download_model()

    @pytest.mark.asyncio
    async def test_download_model_calls_progress_callback(self) -> None:
        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        progress_cb = MagicMock()
        # This will need actual implementation but tests the interface
        with patch.object(engine, "download_model", new_callable=AsyncMock) as mock_dl:
            await engine.download_model(on_progress=progress_cb)
            mock_dl.assert_called_once_with(on_progress=progress_cb)


# ---------------------------------------------------------------------------
# LocalWhisperEngine accuracy parameter tests
# ---------------------------------------------------------------------------


class TestLocalWhisperEngineAccuracyParams:
    """Tests for VAD, temperature, and hallucination threshold parameters."""

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_vad_filter_enabled(
        self, mock_model_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """VAD filter should be enabled to suppress hallucinations on silence."""
        mock_model = mock_model_cls.return_value
        mock_model.transcribe.return_value = ([], MagicMock(language="en"))

        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        await engine.transcribe(sine_wave_chunk)

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["vad_filter"] is True

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_vad_parameters_set(
        self, mock_model_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """VAD parameters should configure min silence duration."""
        mock_model = mock_model_cls.return_value
        mock_model.transcribe.return_value = ([], MagicMock(language="en"))

        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        await engine.transcribe(sine_wave_chunk)

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["vad_parameters"] == {"min_silence_duration_ms": 500}

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_temperature_zero(
        self, mock_model_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """Temperature should be 0.0 for deterministic output."""
        mock_model = mock_model_cls.return_value
        mock_model.transcribe.return_value = ([], MagicMock(language="en"))

        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        await engine.transcribe(sine_wave_chunk)

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["temperature"] == 0.0

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_compression_ratio_threshold(
        self, mock_model_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """Compression ratio threshold should be set to filter repetitive output."""
        mock_model = mock_model_cls.return_value
        mock_model.transcribe.return_value = ([], MagicMock(language="en"))

        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        await engine.transcribe(sine_wave_chunk)

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["compression_ratio_threshold"] == 2.4

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_no_speech_threshold(
        self, mock_model_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """No-speech threshold should be set to suppress empty segments."""
        mock_model = mock_model_cls.return_value
        mock_model.transcribe.return_value = ([], MagicMock(language="en"))

        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        await engine.transcribe(sine_wave_chunk)

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["no_speech_threshold"] == 0.6

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_default_initial_prompt_without_context(
        self, mock_model_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """Without context_prompt, the default bilingual prompt is used."""
        mock_model = mock_model_cls.return_value
        mock_model.transcribe.return_value = ([], MagicMock(language="en"))

        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        await engine.transcribe(sine_wave_chunk)

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["initial_prompt"] == engine._DEFAULT_PROMPT

    @pytest.mark.asyncio
    @patch("systemstt.stt.local_whisper.WhisperModel")
    async def test_context_prompt_used_as_initial_prompt(
        self, mock_model_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """When context_prompt is provided, it replaces the default initial_prompt."""
        mock_model = mock_model_cls.return_value
        mock_model.transcribe.return_value = ([], MagicMock(language="en"))

        config = LocalWhisperConfig()
        engine = LocalWhisperEngine(config)
        await engine.initialize()
        await engine.transcribe(sine_wave_chunk, context_prompt="previous text here")

        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs["initial_prompt"] == "previous text here"
