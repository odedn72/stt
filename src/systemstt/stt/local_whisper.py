"""
LocalWhisperEngine — local STT using faster-whisper (CTranslate2).

Loads a Whisper model locally and transcribes audio without sending
data to any server. Supports model download, availability checking,
and various model sizes.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

from faster_whisper import WhisperModel  # type: ignore[import-untyped]

from systemstt.errors import (
    ModelDownloadError,
    ModelLoadError,
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


class WhisperModelSize(str, Enum):
    """Available Whisper model sizes."""

    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


@dataclass(frozen=True)
class LocalWhisperConfig:
    """Configuration for the local Whisper engine."""

    model_size: WhisperModelSize = WhisperModelSize.MEDIUM
    device: str = "cpu"
    compute_type: str = "int8"
    beam_size: int = 5
    num_workers: int = 1


def _parse_language(lang_str: str) -> DetectedLanguage:
    """Parse a language string into DetectedLanguage enum."""
    lang_lower = lang_str.lower()
    if lang_lower in ("en", "english"):
        return DetectedLanguage.ENGLISH
    if lang_lower in ("he", "hebrew"):
        return DetectedLanguage.HEBREW
    return DetectedLanguage.UNKNOWN


class LocalWhisperEngine(STTEngine):
    """Local STT engine using faster-whisper."""

    def __init__(self, config: LocalWhisperConfig) -> None:
        self._config = config
        self._state = EngineState.UNINITIALIZED
        self._model: Optional[WhisperModel] = None

    @property
    def engine_type(self) -> EngineType:
        return EngineType.LOCAL_WHISPER

    @property
    def state(self) -> EngineState:
        return self._state

    async def initialize(self) -> None:
        """Load the Whisper model.

        Raises ModelLoadError if the model fails to load.
        """
        self._state = EngineState.LOADING
        try:
            # Run model loading in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            self._model = await loop.run_in_executor(
                None, self._load_model
            )
            self._state = EngineState.READY
            logger.info(
                "LocalWhisperEngine initialized (model=%s, compute=%s)",
                self._config.model_size.value,
                self._config.compute_type,
            )
        except Exception as exc:
            self._state = EngineState.ERROR
            raise ModelLoadError(
                f"Failed to load Whisper model '{self._config.model_size.value}': {exc}"
            ) from exc

    def _load_model(self) -> WhisperModel:
        """Load the Whisper model (runs in thread)."""
        return WhisperModel(
            self._config.model_size.value,
            device=self._config.device,
            compute_type=self._config.compute_type,
            num_workers=self._config.num_workers,
        )

    async def shutdown(self) -> None:
        """Unload the model and free resources."""
        self._model = None
        self._state = EngineState.UNINITIALIZED
        logger.info("LocalWhisperEngine shut down")

    def is_available(self) -> bool:
        """Return True if the model is loaded and ready."""
        return self._state == EngineState.READY and self._model is not None

    async def transcribe(
        self,
        audio: np.ndarray,
        language_hint: Optional[DetectedLanguage] = None,
    ) -> TranscriptionResult:
        """Transcribe audio using the local Whisper model.

        Raises STTEngineError if not initialized, TranscriptionError on failure.
        """
        if self._state != EngineState.READY or self._model is None:
            raise STTEngineError(
                "LocalWhisperEngine is not initialized. Call initialize() first."
            )

        self._state = EngineState.TRANSCRIBING
        start_time = time.monotonic()

        try:
            loop = asyncio.get_event_loop()
            segments_list, info = await loop.run_in_executor(
                None,
                lambda: self._do_transcribe(audio, language_hint),
            )

            processing_time_ms = (time.monotonic() - start_time) * 1000
            language = _parse_language(info.language)

            # If a language hint was provided, use it as primary language
            if language_hint is not None and language_hint != DetectedLanguage.UNKNOWN:
                primary_language = language_hint
            else:
                primary_language = language

            segments: list[TranscriptionSegment] = []
            full_text_parts: list[str] = []

            for seg in segments_list:
                avg_logprob = getattr(seg, "avg_logprob", -1.0)
                confidence = min(1.0, max(0.0, math.exp(avg_logprob)))
                segments.append(
                    TranscriptionSegment(
                        text=seg.text,
                        language=primary_language,
                        start_time=seg.start,
                        end_time=seg.end,
                        confidence=confidence,
                        is_partial=False,
                    )
                )
                full_text_parts.append(seg.text)

            full_text = "".join(full_text_parts).strip()

            return TranscriptionResult(
                segments=segments,
                full_text=full_text,
                primary_language=primary_language,
                processing_time_ms=processing_time_ms,
            )
        except (STTEngineError, TranscriptionError):
            raise
        except Exception as exc:
            raise TranscriptionError(
                f"Transcription failed: {exc}"
            ) from exc
        finally:
            if self._state == EngineState.TRANSCRIBING:
                self._state = EngineState.READY

    # Default buffer: accumulate ~5 seconds of audio at 16kHz before transcribing
    _STREAM_BUFFER_SAMPLES: int = 16_000 * 5

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[np.ndarray],
        *,
        language_hint: Optional[DetectedLanguage] = None,
    ) -> AsyncIterator[TranscriptionResult]:
        """Stream-transcribe audio by buffering chunks and transcribing periodically.

        Accumulates audio from the async iterator. When the buffer reaches
        the threshold (~5 seconds at 16kHz), transcribes the accumulated
        buffer and yields the result. Any remaining audio in the buffer
        is transcribed when the stream ends.

        Local Whisper uses a longer buffer than cloud since faster-whisper
        does not natively support streaming and benefits from more context.

        Args:
            audio_stream: Async iterator of audio chunks (PCM float32, 16kHz mono).
            language_hint: Optional language hint to bias the model.

        Yields:
            TranscriptionResult for each transcribed buffer.

        Raises:
            TranscriptionError: If transcription fails.
            STTEngineError: If the engine is not in READY state.
        """
        if self._state != EngineState.READY or self._model is None:
            raise STTEngineError(
                "LocalWhisperEngine is not initialized. Call initialize() first."
            )

        buffer_chunks: list[np.ndarray] = []
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

    def _do_transcribe(
        self,
        audio: np.ndarray,
        language_hint: Optional[DetectedLanguage],
    ) -> tuple[list[Any], Any]:
        """Run transcription synchronously (called in thread)."""
        assert self._model is not None

        kwargs: dict[str, Any] = {
            "beam_size": self._config.beam_size,
        }
        if language_hint is not None and language_hint != DetectedLanguage.UNKNOWN:
            kwargs["language"] = language_hint.value

        segments_gen, info = self._model.transcribe(audio, **kwargs)
        # Materialize the generator
        segments_list = list(segments_gen)
        return segments_list, info

    def is_model_downloaded(self) -> bool:
        """Check if the model is downloaded in the cache directory."""
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        # Simple check: look for any model directory matching the size
        model_name = f"*whisper*{self._config.model_size.value}*"
        return any(cache_dir.glob(model_name))

    def get_model_info(self) -> dict[str, str]:
        """Return information about the configured model."""
        return {
            "model_size": self._config.model_size.value,
            "device": self._config.device,
            "compute_type": self._config.compute_type,
            "beam_size": str(self._config.beam_size),
            "num_workers": str(self._config.num_workers),
        }

    async def download_model(
        self,
        on_progress: Optional[Callable[[float], None]] = None,
    ) -> None:
        """Download the Whisper model.

        Raises ModelDownloadError on failure.
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._download_model_sync(on_progress),
            )
        except Exception as exc:
            raise ModelDownloadError(
                f"Failed to download model '{self._config.model_size.value}': {exc}"
            ) from exc

    def _download_model_sync(
        self,
        on_progress: Optional[Callable[[float], None]],
    ) -> None:
        """Download model synchronously (runs in thread)."""
        # faster-whisper downloads the model on first use
        # Creating the model triggers the download
        WhisperModel(
            self._config.model_size.value,
            device=self._config.device,
            compute_type=self._config.compute_type,
        )
        if on_progress is not None:
            on_progress(1.0)
