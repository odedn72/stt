"""
Tests for the hallucination filter post-processor.

Verifies that common Whisper artifacts are filtered while normal
transcription text passes through unchanged.
"""

from __future__ import annotations

import pytest

from systemstt.stt.postprocess import filter_hallucinations


# ---------------------------------------------------------------------------
# Normal text — should pass through unchanged
# ---------------------------------------------------------------------------


class TestNormalTextPassthrough:
    """Normal transcription text should not be filtered."""

    def test_english_sentence(self) -> None:
        assert filter_hallucinations("Hello, how are you doing today?") == "Hello, how are you doing today?"

    def test_hebrew_sentence(self) -> None:
        text = "שלום, מה שלומך היום?"
        assert filter_hallucinations(text) == text

    def test_mixed_language(self) -> None:
        text = "I need to go to the שוק today"
        assert filter_hallucinations(text) == text

    def test_short_valid_text(self) -> None:
        assert filter_hallucinations("Yes") == "Yes"

    def test_empty_string(self) -> None:
        assert filter_hallucinations("") == ""

    def test_whitespace_only(self) -> None:
        assert filter_hallucinations("   ") == ""


# ---------------------------------------------------------------------------
# Full-text hallucination patterns — should be discarded entirely
# ---------------------------------------------------------------------------


class TestFullTextHallucinations:
    """Known Whisper hallucination patterns should be removed entirely."""

    def test_thank_you_for_watching(self) -> None:
        assert filter_hallucinations("Thank you for watching.") == ""

    def test_thank_you_for_watching_case_insensitive(self) -> None:
        assert filter_hallucinations("thank you for watching!") == ""

    def test_please_subscribe(self) -> None:
        assert filter_hallucinations("Please subscribe and like.") == ""

    def test_hebrew_thanks_for_watching(self) -> None:
        assert filter_hallucinations("תודה על הצפייה") == ""

    def test_music_symbol(self) -> None:
        assert filter_hallucinations("♪") == ""

    def test_music_symbol_with_spaces(self) -> None:
        assert filter_hallucinations(" ♪ ♪ ") == ""

    def test_music_tag(self) -> None:
        assert filter_hallucinations("[Music]") == ""

    def test_ellipsis_only(self) -> None:
        assert filter_hallucinations("...") == ""

    def test_lone_you(self) -> None:
        assert filter_hallucinations("you") == ""

    def test_lone_you_with_period(self) -> None:
        assert filter_hallucinations("You.") == ""


# ---------------------------------------------------------------------------
# Repetition detection
# ---------------------------------------------------------------------------


class TestRepetitionDetection:
    """Highly repetitive output should be discarded."""

    def test_same_phrase_repeated(self) -> None:
        """Same phrase repeated many times should be filtered."""
        text = "Thank you. " * 10
        assert filter_hallucinations(text.strip()) == ""

    def test_non_repetitive_text_passes(self) -> None:
        """Text with varied sentences should not be filtered."""
        text = "First sentence. Second sentence. Third sentence."
        assert filter_hallucinations(text) == text


# ---------------------------------------------------------------------------
# Suffix stripping — trailing artifacts on otherwise valid text
# ---------------------------------------------------------------------------


class TestSuffixStripping:
    """Trailing hallucination artifacts should be stripped from valid text."""

    def test_trailing_thank_you_stripped(self) -> None:
        result = filter_hallucinations("Meeting at 3pm. Thank you for watching.")
        assert result == "Meeting at 3pm."

    def test_trailing_subscribe_stripped(self) -> None:
        result = filter_hallucinations("The report is ready. Please subscribe and like.")
        assert result == "The report is ready."

    def test_trailing_music_stripped(self) -> None:
        result = filter_hallucinations("Send the email now. ♪")
        assert result == "Send the email now."

    def test_trailing_ellipsis_stripped(self) -> None:
        result = filter_hallucinations("Take notes please...")
        assert result == "Take notes please"
