# TDD: Written from spec 03-stt-engine.md
"""
Tests for the STT engine abstract base class and shared data models.

Verifies:
- TranscriptionSegment and TranscriptionResult data models
- DetectedLanguage, EngineType, EngineState enums
- STTEngine ABC cannot be instantiated directly
"""

from __future__ import annotations

import numpy as np
import pytest

from systemstt.stt.base import (
    DetectedLanguage,
    EngineType,
    EngineState,
    TranscriptionSegment,
    TranscriptionResult,
    STTEngine,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestDetectedLanguage:
    """Tests for the DetectedLanguage enum."""

    def test_english_value(self) -> None:
        assert DetectedLanguage.ENGLISH.value == "en"

    def test_hebrew_value(self) -> None:
        assert DetectedLanguage.HEBREW.value == "he"

    def test_unknown_value(self) -> None:
        assert DetectedLanguage.UNKNOWN.value == "unknown"


class TestEngineType:
    """Tests for the EngineType enum."""

    def test_local_whisper_value(self) -> None:
        assert EngineType.LOCAL_WHISPER.value == "local_whisper"

    def test_cloud_api_value(self) -> None:
        assert EngineType.CLOUD_API.value == "cloud_api"


class TestEngineState:
    """Tests for the EngineState enum."""

    def test_uninitialized_value(self) -> None:
        assert EngineState.UNINITIALIZED.value == "uninitialized"

    def test_loading_value(self) -> None:
        assert EngineState.LOADING.value == "loading"

    def test_ready_value(self) -> None:
        assert EngineState.READY.value == "ready"

    def test_transcribing_value(self) -> None:
        assert EngineState.TRANSCRIBING.value == "transcribing"

    def test_error_value(self) -> None:
        assert EngineState.ERROR.value == "error"


# ---------------------------------------------------------------------------
# TranscriptionSegment tests
# ---------------------------------------------------------------------------

class TestTranscriptionSegment:
    """Tests for the TranscriptionSegment dataclass."""

    def test_segment_fields(self) -> None:
        segment = TranscriptionSegment(
            text="Hello world",
            language=DetectedLanguage.ENGLISH,
            start_time=0.0,
            end_time=1.5,
            confidence=0.95,
            is_partial=False,
        )
        assert segment.text == "Hello world"
        assert segment.language == DetectedLanguage.ENGLISH
        assert segment.start_time == 0.0
        assert segment.end_time == 1.5
        assert segment.confidence == 0.95
        assert segment.is_partial is False

    def test_segment_is_frozen(self) -> None:
        segment = TranscriptionSegment(
            text="test", language=DetectedLanguage.ENGLISH,
            start_time=0.0, end_time=1.0, confidence=0.9, is_partial=False,
        )
        with pytest.raises(AttributeError):
            segment.text = "modified"  # type: ignore[misc]

    def test_segment_with_hebrew_text(self) -> None:
        segment = TranscriptionSegment(
            text="\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd",
            language=DetectedLanguage.HEBREW,
            start_time=0.0, end_time=1.2, confidence=0.88, is_partial=False,
        )
        assert segment.language == DetectedLanguage.HEBREW
        assert "\u05e9\u05dc\u05d5\u05dd" in segment.text

    def test_segment_partial_flag(self) -> None:
        segment = TranscriptionSegment(
            text="partial result",
            language=DetectedLanguage.ENGLISH,
            start_time=0.0, end_time=0.5, confidence=0.6, is_partial=True,
        )
        assert segment.is_partial is True

    def test_segment_confidence_range(self) -> None:
        """Confidence should be 0.0 to 1.0."""
        segment = TranscriptionSegment(
            text="test", language=DetectedLanguage.ENGLISH,
            start_time=0.0, end_time=1.0, confidence=0.0, is_partial=False,
        )
        assert 0.0 <= segment.confidence <= 1.0


# ---------------------------------------------------------------------------
# TranscriptionResult tests
# ---------------------------------------------------------------------------

class TestTranscriptionResult:
    """Tests for the TranscriptionResult dataclass."""

    def test_result_fields(self) -> None:
        segment = TranscriptionSegment(
            text="Hello", language=DetectedLanguage.ENGLISH,
            start_time=0.0, end_time=1.0, confidence=0.95, is_partial=False,
        )
        result = TranscriptionResult(
            segments=[segment],
            full_text="Hello",
            primary_language=DetectedLanguage.ENGLISH,
            processing_time_ms=150.0,
        )
        assert len(result.segments) == 1
        assert result.full_text == "Hello"
        assert result.primary_language == DetectedLanguage.ENGLISH
        assert result.processing_time_ms == 150.0

    def test_result_with_multiple_segments(self) -> None:
        segments = [
            TranscriptionSegment(
                text="\u05e9\u05dc\u05d5\u05dd",
                language=DetectedLanguage.HEBREW,
                start_time=0.0, end_time=0.5, confidence=0.85, is_partial=False,
            ),
            TranscriptionSegment(
                text="world",
                language=DetectedLanguage.ENGLISH,
                start_time=0.5, end_time=1.0, confidence=0.92, is_partial=False,
            ),
        ]
        result = TranscriptionResult(
            segments=segments,
            full_text="\u05e9\u05dc\u05d5\u05dd world",
            primary_language=DetectedLanguage.ENGLISH,
            processing_time_ms=250.0,
        )
        assert len(result.segments) == 2
        assert result.primary_language == DetectedLanguage.ENGLISH

    def test_result_is_frozen(self) -> None:
        result = TranscriptionResult(
            segments=[], full_text="",
            primary_language=DetectedLanguage.UNKNOWN,
            processing_time_ms=0.0,
        )
        with pytest.raises(AttributeError):
            result.full_text = "changed"  # type: ignore[misc]

    def test_empty_result(self) -> None:
        result = TranscriptionResult(
            segments=[], full_text="",
            primary_language=DetectedLanguage.UNKNOWN,
            processing_time_ms=50.0,
        )
        assert result.full_text == ""
        assert result.segments == []


# ---------------------------------------------------------------------------
# STTEngine ABC tests
# ---------------------------------------------------------------------------

class TestSTTEngineABC:
    """Tests that STTEngine cannot be instantiated directly."""

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            STTEngine()  # type: ignore[abstract]
