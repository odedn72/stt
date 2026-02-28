"""
STT engine abstract base class and shared data models.

Defines the contract all STT engines must implement, plus the
data models for transcription results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

import numpy as np


class DetectedLanguage(str, Enum):
    """Detected language of transcribed text."""

    ENGLISH = "en"
    HEBREW = "he"
    UNKNOWN = "unknown"


class EngineType(str, Enum):
    """Type of STT engine."""

    LOCAL_WHISPER = "local_whisper"
    CLOUD_API = "cloud_api"


class EngineState(str, Enum):
    """State of an STT engine."""

    UNINITIALIZED = "uninitialized"
    LOADING = "loading"
    READY = "ready"
    TRANSCRIBING = "transcribing"
    ERROR = "error"


@dataclass(frozen=True)
class TranscriptionSegment:
    """A single segment of transcription output."""

    text: str
    language: DetectedLanguage
    start_time: float
    end_time: float
    confidence: float
    is_partial: bool


@dataclass(frozen=True)
class TranscriptionResult:
    """Complete result of a transcription operation."""

    segments: Sequence[TranscriptionSegment]
    full_text: str
    primary_language: DetectedLanguage
    processing_time_ms: float


class STTEngine(ABC):
    """Abstract base class for STT engines."""

    @property
    @abstractmethod
    def engine_type(self) -> EngineType:
        """Return the type of this engine."""
        ...

    @property
    @abstractmethod
    def state(self) -> EngineState:
        """Return the current engine state."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the engine (load model, create client, etc.)."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Shut down the engine and release resources."""
        ...

    @abstractmethod
    async def transcribe(
        self,
        audio: np.ndarray,
        language_hint: Optional[DetectedLanguage] = None,
    ) -> TranscriptionResult:
        """Transcribe audio data to text."""
        ...

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[np.ndarray],
        *,
        language_hint: Optional[DetectedLanguage] = None,
    ) -> AsyncIterator[TranscriptionResult]:
        """Stream-transcribe audio, yielding partial results as they become available.

        Accumulates audio from the async iterator and transcribes when a
        silence boundary or time threshold is reached, yielding results
        as each chunk completes.

        Args:
            audio_stream: Async iterator of audio chunks (PCM float32, 16kHz mono).
            language_hint: Optional language hint to bias the model.

        Yields:
            TranscriptionResult objects. Segments with is_partial=True may be revised.

        Raises:
            TranscriptionError: If transcription fails.
        """
        ...
        # This yield is needed to make this an abstract async generator.
        # Implementations must override with their own yield logic.
        yield  # type: ignore[misc]

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the engine is available for transcription."""
        ...
