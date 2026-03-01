"""
Post-processing filters for transcription output.

Removes common Whisper hallucination artifacts such as "Thank you for
watching", music symbols, and highly repetitive output.
"""

from __future__ import annotations

import re

# Patterns that indicate the entire text is a hallucination.
# Matched case-insensitively against the stripped text.
_FULL_TEXT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^thank you for watching[.!]?$", re.IGNORECASE),
    re.compile(r"^thanks for watching[.!]?$", re.IGNORECASE),
    re.compile(r"^please subscribe[^.]*[.!]?$", re.IGNORECASE),
    re.compile(r"^תודה על הצפייה[.!]?$"),
    re.compile(r"^[♪♫\s]+$"),
    re.compile(r"^\[music\]$", re.IGNORECASE),
    re.compile(r"^\.{2,}$"),
    re.compile(r"^you[.!]?$", re.IGNORECASE),
]

# Patterns to strip from the end of otherwise valid text.
_SUFFIX_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\s*thank you for watching[.!]?$", re.IGNORECASE),
    re.compile(r"\s*thanks for watching[.!]?$", re.IGNORECASE),
    re.compile(r"\s*please subscribe[^.]*[.!]?$", re.IGNORECASE),
    re.compile(r"\s*תודה על הצפייה[.!]?$"),
    re.compile(r"\s*[♪♫]+\s*$"),
    re.compile(r"\.{3,}$"),
]

# Minimum ratio of identical sentences to total for repetition filtering.
_REPETITION_THRESHOLD = 0.7


def filter_hallucinations(text: str) -> str:
    """Remove Whisper hallucination artifacts from transcribed text.

    Returns cleaned text, or empty string if the entire text is an artifact.
    """
    stripped = text.strip()
    if not stripped:
        return ""

    # Check full-text hallucination patterns
    for pattern in _FULL_TEXT_PATTERNS:
        if pattern.match(stripped):
            return ""

    # Check for highly repetitive output
    if _is_repetitive(stripped):
        return ""

    # Strip trailing artifacts from otherwise valid text
    result = stripped
    for pattern in _SUFFIX_PATTERNS:
        result = pattern.sub("", result)

    return result.strip()


def _is_repetitive(text: str) -> bool:
    """Return True if the text is dominated by a single repeated phrase."""
    # Split into sentences on period/exclamation/question boundaries
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if len(sentences) < 3:
        return False

    # Count occurrences of the most common sentence
    from collections import Counter

    counts = Counter(s.lower() for s in sentences)
    most_common_count = counts.most_common(1)[0][1]

    return most_common_count / len(sentences) > _REPETITION_THRESHOLD
