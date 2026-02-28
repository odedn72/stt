"""
CommandParser — detects voice commands in transcription text.

Matches trigger phrases from the CommandRegistry against the end of
the transcription text. Supports suffix matching for multi-word
commands and standalone-only matching for short ambiguous commands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from systemstt.commands.registry import CommandRegistry, VoiceCommand


@dataclass(frozen=True)
class ParseResult:
    """Result of parsing text for a voice command."""

    has_command: bool
    command: Optional[VoiceCommand]
    text_before: str
    text_after: str
    matched_phrase: str


class CommandParser:
    """Parses transcription text to detect voice commands."""

    def __init__(self, registry: CommandRegistry) -> None:
        self._registry = registry
        self.enabled: bool = True

    def parse(self, text: str) -> ParseResult:
        """Parse text for a voice command.

        Commands are matched at the end of the text (suffix matching).
        Standalone-only commands only match if the entire text is the command.

        Returns a ParseResult indicating whether a command was found.
        """
        if not self.enabled:
            return ParseResult(
                has_command=False,
                command=None,
                text_before="",
                text_after="",
                matched_phrase="",
            )

        # Clean text: collapse whitespace but preserve original case
        cleaned = self._clean(text)
        # Normalized (lowercased) for matching
        normalized = cleaned.lower()

        if not normalized:
            return ParseResult(
                has_command=False,
                command=None,
                text_before="",
                text_after="",
                matched_phrase="",
            )

        # Try to match commands
        best_match: Optional[tuple[VoiceCommand, str, int]] = None
        best_phrase_len = 0

        for cmd in self._registry.commands:
            for phrase in cmd.trigger_phrases:
                norm_phrase = self._normalize_phrase(phrase)
                if not norm_phrase:
                    continue

                if cmd.standalone_only:
                    # Standalone-only: entire text must be the command
                    if normalized == norm_phrase:
                        if len(norm_phrase) > best_phrase_len:
                            # match_start = index where command starts in cleaned text
                            best_match = (cmd, phrase, 0)
                            best_phrase_len = len(norm_phrase)
                    continue

                # Suffix matching: command at end of text
                if normalized == norm_phrase:
                    if len(norm_phrase) > best_phrase_len:
                        best_match = (cmd, phrase, 0)
                        best_phrase_len = len(norm_phrase)
                elif normalized.endswith(" " + norm_phrase):
                    start_idx = len(cleaned) - len(norm_phrase)
                    if len(norm_phrase) > best_phrase_len:
                        best_match = (cmd, phrase, start_idx)
                        best_phrase_len = len(norm_phrase)

        if best_match is not None:
            cmd, matched_phrase_orig, match_start = best_match
            if match_start > 0:
                # Extract text before the command from the cleaned (case-preserved) text
                text_before = cleaned[:match_start].rstrip()
                matched = cleaned[match_start:]
            else:
                text_before = ""
                matched = cleaned

            return ParseResult(
                has_command=True,
                command=cmd,
                text_before=text_before,
                text_after="",
                matched_phrase=matched.lower(),
            )

        return ParseResult(
            has_command=False,
            command=None,
            text_before="",
            text_after="",
            matched_phrase="",
        )

    def _clean(self, text: str) -> str:
        """Clean text: strip, collapse whitespace, strip trailing punctuation.

        Preserves original case.
        """
        result = re.sub(r"\s+", " ", text.strip())
        result = result.rstrip(".,!?;:")
        return result.strip()

    def _normalize_phrase(self, phrase: str) -> str:
        """Normalize a phrase for matching: clean + lowercase."""
        return self._clean(phrase).lower()
