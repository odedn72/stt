"""
CloudAPIEngine — cloud STT using OpenAI Whisper API via httpx.

Sends audio as WAV to the API and parses the response into a
TranscriptionResult. Supports retry with exponential backoff.
"""

from __future__ import annotations

import asyncio
import io
import logging
import math
import struct
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import httpx
import numpy as np

from systemstt.errors import (
    APIAuthenticationError,
    APIRateLimitError,
    APITimeoutError,
    APIUnavailableError,
    CloudAPIError,
    STTEngineError,
    TranscriptionError,
)
from systemstt.stt.base import (
    DetectedLanguage,
    EngineState,
    EngineType,
    STTEngine,
    TranscriptionResult,
    TranscriptionSegment,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloudAPIConfig:
    """Configuration for the cloud API engine."""

    api_key: str
    api_base_url: str = "https://api.openai.com/v1"
    model: str = "whisper-1"
    timeout_seconds: float = 10.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0


def _audio_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16_000) -> bytes:  # type: ignore[type-arg]
    """Convert a float32 numpy array to WAV bytes in memory."""
    buf = io.BytesIO()
    # Convert float32 [-1.0, 1.0] to int16
    audio_int16 = (audio * 32767).astype(np.int16)
    num_samples = len(audio_int16)
    data_size = num_samples * 2  # 2 bytes per int16 sample

    # Write WAV header
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))  # chunk size
    buf.write(struct.pack("<H", 1))  # PCM format
    buf.write(struct.pack("<H", 1))  # mono
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * 2))  # byte rate
    buf.write(struct.pack("<H", 2))  # block align
    buf.write(struct.pack("<H", 16))  # bits per sample
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(audio_int16.tobytes())

    return buf.getvalue()


def _parse_language(lang_str: str) -> DetectedLanguage:
    """Parse a language string into DetectedLanguage enum."""
    lang_lower = lang_str.lower()
    if lang_lower in ("en", "english"):
        return DetectedLanguage.ENGLISH
    if lang_lower in ("he", "hebrew"):
        return DetectedLanguage.HEBREW
    return DetectedLanguage.UNKNOWN


class CloudAPIEngine(STTEngine):
    """Cloud STT engine using OpenAI Whisper API."""

    def __init__(self, config: CloudAPIConfig) -> None:
        self._config = config
        self._state = EngineState.UNINITIALIZED
        self._client: httpx.AsyncClient | None = None

    @property
    def engine_type(self) -> EngineType:
        return EngineType.CLOUD_API

    @property
    def state(self) -> EngineState:
        return self._state

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._config.timeout_seconds),
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
            },
        )
        self._state = EngineState.READY
        logger.info("CloudAPIEngine initialized (base_url=%s)", self._config.api_base_url)

    async def shutdown(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._state = EngineState.UNINITIALIZED

    def is_available(self) -> bool:
        """Return True if an API key is configured."""
        return bool(self._config.api_key)

    async def validate_api_key(self) -> bool:
        """Validate the API key by making a lightweight API call.

        Returns True if the key is valid, False otherwise.
        """
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._config.timeout_seconds),
                headers={"Authorization": f"Bearer {self._config.api_key}"},
            ) as client:
                response = await client.get(f"{self._config.api_base_url}/models")
                return response.status_code == 200
        except Exception:
            return False

    # Default buffer: accumulate ~3 seconds of audio at 16kHz before transcribing
    _STREAM_BUFFER_SAMPLES: int = 16_000 * 3

    async def transcribe(
        self,
        audio: np.ndarray,  # type: ignore[type-arg]
        language_hint: DetectedLanguage | None = None,
        context_prompt: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio using the cloud API with retry logic."""
        if self._state != EngineState.READY:
            raise STTEngineError("CloudAPIEngine is not initialized. Call initialize() first.")

        self._state = EngineState.TRANSCRIBING

        try:
            result = await self._transcribe_with_retry(
                audio,
                language_hint,
                context_prompt,
            )
            return result
        finally:
            if self._state == EngineState.TRANSCRIBING:
                self._state = EngineState.READY

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[np.ndarray],  # type: ignore[type-arg]
        *,
        language_hint: DetectedLanguage | None = None,
    ) -> AsyncIterator[TranscriptionResult]:
        """Stream-transcribe audio by buffering chunks and transcribing periodically.

        Accumulates audio from the async iterator. When the buffer reaches
        the threshold (~3 seconds at 16kHz), transcribes the accumulated
        buffer and yields the result. Any remaining audio in the buffer
        is transcribed when the stream ends.

        Args:
            audio_stream: Async iterator of audio chunks (PCM float32, 16kHz mono).
            language_hint: Optional language hint to bias the model.

        Yields:
            TranscriptionResult for each transcribed buffer.

        Raises:
            TranscriptionError: If transcription fails.
            STTEngineError: If the engine is not in READY state.
        """
        if self._state != EngineState.READY:
            raise STTEngineError("CloudAPIEngine is not initialized. Call initialize() first.")

        buffer_chunks: list[np.ndarray] = []  # type: ignore[type-arg]
        buffered_samples = 0

        async for chunk in audio_stream:
            buffer_chunks.append(chunk)
            buffered_samples += len(chunk)

            if buffered_samples >= self._STREAM_BUFFER_SAMPLES:
                combined = np.concatenate(buffer_chunks)
                buffer_chunks = []
                buffered_samples = 0
                result = await self.transcribe(combined, language_hint=language_hint)
                # Mark segments as partial since more audio may follow
                partial_segments = [
                    TranscriptionSegment(
                        text=seg.text,
                        language=seg.language,
                        start_time=seg.start_time,
                        end_time=seg.end_time,
                        confidence=seg.confidence,
                        is_partial=True,
                    )
                    for seg in result.segments
                ]
                yield TranscriptionResult(
                    segments=partial_segments,
                    full_text=result.full_text,
                    primary_language=result.primary_language,
                    processing_time_ms=result.processing_time_ms,
                )

        # Flush any remaining audio in the buffer
        if buffer_chunks:
            combined = np.concatenate(buffer_chunks)
            result = await self.transcribe(combined, language_hint=language_hint)
            yield result

    async def _transcribe_with_retry(
        self,
        audio: np.ndarray,  # type: ignore[type-arg]
        language_hint: DetectedLanguage | None = None,
        context_prompt: str | None = None,
    ) -> TranscriptionResult:
        """Attempt transcription with retry logic."""
        last_exception: Exception | None = None
        start_time = time.monotonic()

        for attempt in range(self._config.max_retries):
            try:
                return await self._do_transcribe(
                    audio,
                    language_hint,
                    start_time,
                    context_prompt,
                )
            except (APITimeoutError, APIRateLimitError, APIUnavailableError) as exc:
                last_exception = exc
                if attempt < self._config.max_retries - 1:
                    delay = self._config.retry_delay_seconds * (2**attempt)
                    logger.warning(
                        "Transcription attempt %d failed: %s. Retrying in %.1fs",
                        attempt + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
            except Exception as exc:
                raise exc

        if last_exception is not None:
            raise last_exception
        raise TranscriptionError("Transcription failed after all retries")

    _DEFAULT_PROMPT = "Transcribe in English or Hebrew (עברית)."

    async def _do_transcribe(
        self,
        audio: np.ndarray,  # type: ignore[type-arg]
        language_hint: DetectedLanguage | None,
        start_time: float,
        context_prompt: str | None = None,
    ) -> TranscriptionResult:
        """Perform a single transcription attempt."""
        wav_bytes = _audio_to_wav_bytes(audio)

        files = {
            "file": ("audio.wav", wav_bytes, "audio/wav"),
        }
        data: dict[str, str] = {
            "model": self._config.model,
            "response_format": "verbose_json",
            "prompt": context_prompt if context_prompt else self._DEFAULT_PROMPT,
            "temperature": "0",
        }
        if language_hint is not None and language_hint != DetectedLanguage.UNKNOWN:
            data["language"] = language_hint.value

        url = f"{self._config.api_base_url}/audio/transcriptions"

        try:
            assert self._client is not None
            response = await self._client.post(url, files=files, data=data)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APITimeoutError(f"API request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 401:
                raise APIAuthenticationError(
                    f"API authentication failed (HTTP 401): {exc}"
                ) from exc
            if status_code == 429:
                raise APIRateLimitError(f"API rate limit exceeded (HTTP 429): {exc}") from exc
            if status_code >= 500:
                raise APIUnavailableError(f"API unavailable (HTTP {status_code}): {exc}") from exc
            raise CloudAPIError(f"API request failed (HTTP {status_code}): {exc}") from exc

        return self._parse_response(response.json(), start_time)

    def _parse_response(
        self,
        response_data: dict[str, object],
        start_time: float,
    ) -> TranscriptionResult:
        """Parse the API response into a TranscriptionResult."""
        full_text = str(response_data.get("text", ""))
        language = _parse_language(str(response_data.get("language", "unknown")))
        processing_time_ms = (time.monotonic() - start_time) * 1000

        segments_data = response_data.get("segments", [])
        segments: list[TranscriptionSegment] = []

        if isinstance(segments_data, list):
            for seg in segments_data:
                if isinstance(seg, dict):
                    avg_logprob = float(seg.get("avg_logprob", -1.0))
                    # Convert log probability to a 0-1 confidence score
                    confidence = min(1.0, max(0.0, math.exp(avg_logprob)))

                    segments.append(
                        TranscriptionSegment(
                            text=str(seg.get("text", "")),
                            language=language,
                            start_time=float(seg.get("start", 0.0)),
                            end_time=float(seg.get("end", 0.0)),
                            confidence=confidence,
                            is_partial=False,
                        )
                    )

        if not segments and full_text:
            segments = [
                TranscriptionSegment(
                    text=full_text,
                    language=language,
                    start_time=0.0,
                    end_time=0.0,
                    confidence=0.0,
                    is_partial=False,
                )
            ]

        return TranscriptionResult(
            segments=segments,
            full_text=full_text,
            primary_language=language,
            processing_time_ms=processing_time_ms,
        )
