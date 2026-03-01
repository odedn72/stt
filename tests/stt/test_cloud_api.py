# TDD: Written from spec 03-stt-engine.md
"""
Tests for CloudAPIEngine — cloud STT using OpenAI Whisper API.

All httpx calls are mocked. Tests verify:
- Configuration (API key, base URL, timeout, retries)
- Engine lifecycle (initialize, shutdown, state transitions)
- Transcription (WAV conversion, request format, response parsing)
- Error handling (authentication, timeout, rate limit, unavailable)
- Retry logic (exponential backoff per spec)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import numpy as np
import pytest

from systemstt.errors import (
    APIAuthenticationError,
    APIRateLimitError,
    APITimeoutError,
    APIUnavailableError,
    CloudAPIError,
    STTEngineError,
)
from systemstt.stt.base import (
    DetectedLanguage,
    EngineState,
    EngineType,
    TranscriptionResult,
)
from systemstt.stt.cloud_api import CloudAPIConfig, CloudAPIEngine

# ---------------------------------------------------------------------------
# CloudAPIConfig tests
# ---------------------------------------------------------------------------


class TestCloudAPIConfig:
    """Tests for CloudAPIConfig dataclass."""

    def test_default_base_url(self) -> None:
        config = CloudAPIConfig(api_key="test-key")
        assert config.api_base_url == "https://api.openai.com/v1"

    def test_default_model(self) -> None:
        config = CloudAPIConfig(api_key="test-key")
        assert config.model == "whisper-1"

    def test_default_timeout(self) -> None:
        config = CloudAPIConfig(api_key="test-key")
        assert config.timeout_seconds == 10.0

    def test_default_max_retries(self) -> None:
        config = CloudAPIConfig(api_key="test-key")
        assert config.max_retries == 3

    def test_default_retry_delay(self) -> None:
        config = CloudAPIConfig(api_key="test-key")
        assert config.retry_delay_seconds == 1.0

    def test_custom_config(self) -> None:
        config = CloudAPIConfig(
            api_key="sk-custom",
            api_base_url="https://custom.api.com/v1",
            model="whisper-2",
            timeout_seconds=30.0,
            max_retries=5,
        )
        assert config.api_key == "sk-custom"
        assert config.api_base_url == "https://custom.api.com/v1"


# ---------------------------------------------------------------------------
# CloudAPIEngine lifecycle tests
# ---------------------------------------------------------------------------


class TestCloudAPIEngineLifecycle:
    """Tests for engine initialization and shutdown."""

    def test_engine_type_is_cloud_api(self) -> None:
        config = CloudAPIConfig(api_key="test-key")
        engine = CloudAPIEngine(config)
        assert engine.engine_type == EngineType.CLOUD_API

    def test_initial_state_is_uninitialized(self) -> None:
        config = CloudAPIConfig(api_key="test-key")
        engine = CloudAPIEngine(config)
        assert engine.state == EngineState.UNINITIALIZED

    @pytest.mark.asyncio
    async def test_initialize_sets_ready_state(self) -> None:
        config = CloudAPIConfig(api_key="test-key")
        engine = CloudAPIEngine(config)
        await engine.initialize()
        assert engine.state == EngineState.READY

    @pytest.mark.asyncio
    async def test_shutdown_returns_to_uninitialized(self) -> None:
        config = CloudAPIConfig(api_key="test-key")
        engine = CloudAPIEngine(config)
        await engine.initialize()
        await engine.shutdown()
        assert engine.state == EngineState.UNINITIALIZED

    @pytest.mark.asyncio
    async def test_shutdown_when_uninitialized_is_safe(self) -> None:
        config = CloudAPIConfig(api_key="test-key")
        engine = CloudAPIEngine(config)
        await engine.shutdown()  # Should not raise

    def test_is_available_true_with_api_key(self) -> None:
        config = CloudAPIConfig(api_key="sk-valid")
        engine = CloudAPIEngine(config)
        assert engine.is_available() is True

    def test_is_available_false_with_empty_api_key(self) -> None:
        config = CloudAPIConfig(api_key="")
        engine = CloudAPIEngine(config)
        assert engine.is_available() is False


# ---------------------------------------------------------------------------
# CloudAPIEngine transcription tests
# ---------------------------------------------------------------------------


class TestCloudAPIEngineTranscribe:
    """Tests for cloud API transcription."""

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_transcribe_returns_transcription_result(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "Hello world",
            "language": "en",
            "segments": [{"text": "Hello world", "start": 0.0, "end": 1.5, "avg_logprob": -0.2}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test")
        engine = CloudAPIEngine(config)
        await engine.initialize()
        result = await engine.transcribe(sine_wave_chunk)

        assert isinstance(result, TranscriptionResult)
        assert "Hello world" in result.full_text

    @pytest.mark.asyncio
    async def test_transcribe_when_not_initialized_raises_error(
        self, sine_wave_chunk: np.ndarray
    ) -> None:
        config = CloudAPIConfig(api_key="sk-test")
        engine = CloudAPIEngine(config)
        with pytest.raises(STTEngineError):
            await engine.transcribe(sine_wave_chunk)

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_transcribe_authentication_error(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-invalid")
        engine = CloudAPIEngine(config)
        await engine.initialize()

        with pytest.raises(APIAuthenticationError):
            await engine.transcribe(sine_wave_chunk)

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_transcribe_timeout_error(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("request timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test", max_retries=1)
        engine = CloudAPIEngine(config)
        await engine.initialize()

        with pytest.raises(APITimeoutError):
            await engine.transcribe(sine_wave_chunk)

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_transcribe_rate_limit_error(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test", max_retries=1)
        engine = CloudAPIEngine(config)
        await engine.initialize()

        with pytest.raises(APIRateLimitError):
            await engine.transcribe(sine_wave_chunk)

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_transcribe_server_error_raises_api_unavailable(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test", max_retries=1)
        engine = CloudAPIEngine(config)
        await engine.initialize()

        with pytest.raises(APIUnavailableError):
            await engine.transcribe(sine_wave_chunk)

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_transcribe_hebrew_text(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd",
            "language": "he",
            "segments": [
                {
                    "text": "\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd",
                    "start": 0.0,
                    "end": 1.2,
                    "avg_logprob": -0.3,
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test")
        engine = CloudAPIEngine(config)
        await engine.initialize()
        result = await engine.transcribe(sine_wave_chunk)

        assert result.primary_language == DetectedLanguage.HEBREW
        assert "\u05e9\u05dc\u05d5\u05dd" in result.full_text


# ---------------------------------------------------------------------------
# CloudAPIEngine API key validation tests
# ---------------------------------------------------------------------------


class TestCloudAPIEngineValidation:
    """Tests for API key validation."""

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_validate_api_key_returns_true_for_valid_key(
        self, mock_client_cls: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-valid")
        engine = CloudAPIEngine(config)
        result = await engine.validate_api_key()
        assert result is True

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_validate_api_key_returns_false_for_invalid_key(
        self, mock_client_cls: MagicMock
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-invalid")
        engine = CloudAPIEngine(config)
        result = await engine.validate_api_key()
        assert result is False


# ---------------------------------------------------------------------------
# CloudAPIEngine retry logic tests
# ---------------------------------------------------------------------------


class TestCloudAPIEngineRetry:
    """Tests for retry behavior per spec section 5.3."""

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_retries_on_timeout_up_to_max_retries(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(
            api_key="sk-test",
            max_retries=3,
            retry_delay_seconds=0.01,  # Short delay for tests
        )
        engine = CloudAPIEngine(config)
        await engine.initialize()

        with pytest.raises(APITimeoutError):
            await engine.transcribe(sine_wave_chunk)

        # Should have attempted max_retries times
        assert mock_client.post.call_count >= 3

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_succeeds_on_retry_after_transient_failure(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {
            "text": "success",
            "language": "en",
            "segments": [{"text": "success", "start": 0.0, "end": 1.0, "avg_logprob": -0.1}],
        }
        mock_response_ok.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        # First call times out, second succeeds
        mock_client.post.side_effect = [
            httpx.TimeoutException("timeout"),
            mock_response_ok,
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test", max_retries=3, retry_delay_seconds=0.01)
        engine = CloudAPIEngine(config)
        await engine.initialize()

        result = await engine.transcribe(sine_wave_chunk)
        assert result.full_text == "success"


# ---------------------------------------------------------------------------
# CloudAPIEngine edge case tests
# ---------------------------------------------------------------------------


class TestCloudAPIEngineEdgeCases:
    """Edge case tests for the cloud API engine."""

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_transcribe_response_without_segments_uses_full_text(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """When API returns text but no segments, a single segment should be created."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "No segments here",
            "language": "en",
            # No "segments" key at all
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test")
        engine = CloudAPIEngine(config)
        await engine.initialize()
        result = await engine.transcribe(sine_wave_chunk)

        assert result.full_text == "No segments here"
        assert len(result.segments) == 1
        assert result.segments[0].text == "No segments here"

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_transcribe_empty_text_response(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """When API returns empty text and no segments, result should be empty."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "",
            "language": "en",
            "segments": [],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test")
        engine = CloudAPIEngine(config)
        await engine.initialize()
        result = await engine.transcribe(sine_wave_chunk)

        assert result.full_text == ""
        assert len(result.segments) == 0

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_transcribe_state_returns_to_ready_after_success(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """Engine state should return to READY after successful transcription."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "test",
            "language": "en",
            "segments": [{"text": "test", "start": 0.0, "end": 1.0, "avg_logprob": -0.1}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test")
        engine = CloudAPIEngine(config)
        await engine.initialize()
        await engine.transcribe(sine_wave_chunk)

        assert engine.state == EngineState.READY

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_transcribe_state_returns_to_ready_after_non_retryable_error(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """Engine state should return to READY after an auth error (non-retryable)."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-invalid")
        engine = CloudAPIEngine(config)
        await engine.initialize()

        with pytest.raises(APIAuthenticationError):
            await engine.transcribe(sine_wave_chunk)

        assert engine.state == EngineState.READY

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_transcribe_unknown_http_error_raises_cloud_api_error(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """HTTP 403 (not 401/429/5xx) should raise generic CloudAPIError."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test", max_retries=1)
        engine = CloudAPIEngine(config)
        await engine.initialize()

        with pytest.raises(CloudAPIError):
            await engine.transcribe(sine_wave_chunk)

    def test_parse_language_unknown_returns_unknown(self) -> None:
        """Unknown language strings should map to DetectedLanguage.UNKNOWN."""
        from systemstt.stt.cloud_api import _parse_language

        assert _parse_language("fr") == DetectedLanguage.UNKNOWN
        assert _parse_language("unknown") == DetectedLanguage.UNKNOWN
        assert _parse_language("") == DetectedLanguage.UNKNOWN

    def test_parse_language_english_variants(self) -> None:
        """Both 'en' and 'english' should map to ENGLISH."""
        from systemstt.stt.cloud_api import _parse_language

        assert _parse_language("en") == DetectedLanguage.ENGLISH
        assert _parse_language("English") == DetectedLanguage.ENGLISH
        assert _parse_language("EN") == DetectedLanguage.ENGLISH

    def test_parse_language_hebrew_variants(self) -> None:
        """Both 'he' and 'hebrew' should map to HEBREW."""
        from systemstt.stt.cloud_api import _parse_language

        assert _parse_language("he") == DetectedLanguage.HEBREW
        assert _parse_language("Hebrew") == DetectedLanguage.HEBREW
        assert _parse_language("HE") == DetectedLanguage.HEBREW

    def test_audio_to_wav_bytes_produces_valid_wav_header(self) -> None:
        """The WAV conversion should produce valid RIFF/WAVE header."""
        from systemstt.stt.cloud_api import _audio_to_wav_bytes

        audio = np.zeros(160, dtype=np.float32)
        wav = _audio_to_wav_bytes(audio, sample_rate=16000)
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"
        assert wav[12:16] == b"fmt "
        assert wav[36:40] == b"data"

    def test_audio_to_wav_bytes_length_is_correct(self) -> None:
        """WAV file size should be 44 (header) + num_samples * 2 (int16)."""
        from systemstt.stt.cloud_api import _audio_to_wav_bytes

        num_samples = 1000
        audio = np.zeros(num_samples, dtype=np.float32)
        wav = _audio_to_wav_bytes(audio)
        expected_len = 44 + num_samples * 2
        assert len(wav) == expected_len


# ---------------------------------------------------------------------------
# CloudAPIEngine accuracy parameter tests
# ---------------------------------------------------------------------------


class TestCloudAPIEngineAccuracyParams:
    """Tests for temperature and other accuracy parameters."""

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_temperature_zero_in_request(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """Temperature should be included in the API request data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "test",
            "language": "en",
            "segments": [{"text": "test", "start": 0.0, "end": 1.0, "avg_logprob": -0.1}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test")
        engine = CloudAPIEngine(config)
        await engine.initialize()
        await engine.transcribe(sine_wave_chunk)

        # Check the data dict passed to post()
        call_kwargs = mock_client.post.call_args
        data = call_kwargs[1]["data"] if "data" in call_kwargs[1] else call_kwargs.kwargs["data"]
        assert data["temperature"] == "0"

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_default_prompt_without_context(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """Without context_prompt, the default bilingual prompt is used."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "test",
            "language": "en",
            "segments": [{"text": "test", "start": 0.0, "end": 1.0, "avg_logprob": -0.1}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test")
        engine = CloudAPIEngine(config)
        await engine.initialize()
        await engine.transcribe(sine_wave_chunk)

        call_kwargs = mock_client.post.call_args
        data = call_kwargs[1]["data"] if "data" in call_kwargs[1] else call_kwargs.kwargs["data"]
        assert data["prompt"] == engine._DEFAULT_PROMPT

    @pytest.mark.asyncio
    @patch("systemstt.stt.cloud_api.httpx.AsyncClient")
    async def test_context_prompt_used_in_request(
        self, mock_client_cls: MagicMock, sine_wave_chunk: np.ndarray
    ) -> None:
        """When context_prompt is provided, it replaces the default prompt."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "continued text",
            "language": "en",
            "segments": [{"text": "continued text", "start": 0.0, "end": 1.0, "avg_logprob": -0.1}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        config = CloudAPIConfig(api_key="sk-test")
        engine = CloudAPIEngine(config)
        await engine.initialize()
        await engine.transcribe(sine_wave_chunk, context_prompt="previous text here")

        call_kwargs = mock_client.post.call_args
        data = call_kwargs[1]["data"] if "data" in call_kwargs[1] else call_kwargs.kwargs["data"]
        assert data["prompt"] == "previous text here"
