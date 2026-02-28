# TDD: Written from spec 04-voice-commands.md
"""
Tests for CommandParser — detects voice commands in transcription text.

Tests verify:
- Trigger phrase matching (suffix matching for multi-word, standalone for short)
- Case insensitivity
- Punctuation stripping
- Whitespace normalization
- Boundary detection (commands at end, not in middle)
- Enabled/disabled toggle
- ParseResult fields (has_command, command, text_before, text_after, matched_phrase)
"""

from __future__ import annotations

import pytest

from systemstt.commands.parser import CommandParser, ParseResult
from systemstt.commands.registry import CommandRegistry, CommandAction


@pytest.fixture
def parser() -> CommandParser:
    """Create a CommandParser with the default registry."""
    registry = CommandRegistry()
    return CommandParser(registry)


# ---------------------------------------------------------------------------
# Basic matching tests
# ---------------------------------------------------------------------------

class TestCommandParserBasicMatching:
    """Tests for basic command matching."""

    def test_standalone_command_detected(self, parser: CommandParser) -> None:
        result = parser.parse("delete last word")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.DELETE_LAST_WORD

    def test_no_command_returns_has_command_false(self, parser: CommandParser) -> None:
        result = parser.parse("Hello world this is a normal sentence")
        assert result.has_command is False
        assert result.command is None

    def test_suffix_command_detected(self, parser: CommandParser) -> None:
        """Command at end of text: 'text before delete last word'."""
        result = parser.parse("the quick brown fox delete last word")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.DELETE_LAST_WORD
        assert "the quick brown fox" in result.text_before

    def test_text_before_preserved(self, parser: CommandParser) -> None:
        result = parser.parse("Hello world new line")
        assert result.has_command is True
        assert "Hello world" in result.text_before

    def test_matched_phrase_recorded(self, parser: CommandParser) -> None:
        result = parser.parse("delete the last word")
        assert result.has_command is True
        assert result.matched_phrase == "delete the last word"


# ---------------------------------------------------------------------------
# Case insensitivity tests
# ---------------------------------------------------------------------------

class TestCommandParserCaseInsensitivity:
    """Tests for case-insensitive matching."""

    def test_uppercase_command_matches(self, parser: CommandParser) -> None:
        result = parser.parse("DELETE LAST WORD")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.DELETE_LAST_WORD

    def test_mixed_case_command_matches(self, parser: CommandParser) -> None:
        result = parser.parse("Delete Last Word")
        assert result.has_command is True

    def test_title_case_new_line(self, parser: CommandParser) -> None:
        result = parser.parse("New Line")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.NEW_LINE


# ---------------------------------------------------------------------------
# Punctuation handling tests
# ---------------------------------------------------------------------------

class TestCommandParserPunctuation:
    """Tests for punctuation stripping."""

    def test_trailing_period_stripped(self, parser: CommandParser) -> None:
        result = parser.parse("delete last word.")
        assert result.has_command is True

    def test_trailing_comma_stripped(self, parser: CommandParser) -> None:
        result = parser.parse("new line,")
        assert result.has_command is True

    def test_trailing_exclamation_stripped(self, parser: CommandParser) -> None:
        result = parser.parse("undo!")
        assert result.has_command is True

    def test_trailing_question_mark_stripped(self, parser: CommandParser) -> None:
        result = parser.parse("undo?")
        assert result.has_command is True


# ---------------------------------------------------------------------------
# Whitespace normalization tests
# ---------------------------------------------------------------------------

class TestCommandParserWhitespace:
    """Tests for whitespace normalization."""

    def test_extra_spaces_normalized(self, parser: CommandParser) -> None:
        result = parser.parse("delete  last   word")
        assert result.has_command is True

    def test_leading_trailing_whitespace_stripped(self, parser: CommandParser) -> None:
        result = parser.parse("  new line  ")
        assert result.has_command is True

    def test_tab_characters_normalized(self, parser: CommandParser) -> None:
        result = parser.parse("new\tline")
        assert result.has_command is True


# ---------------------------------------------------------------------------
# Standalone vs suffix matching tests
# ---------------------------------------------------------------------------

class TestCommandParserStandaloneVsSuffix:
    """Tests for standalone vs suffix matching per spec section 6.2.

    Short ambiguous commands (copy, paste, undo) should only match as
    standalone utterances to avoid false positives. Multi-word commands
    are safe for suffix matching.
    """

    def test_copy_as_standalone_matches(self, parser: CommandParser) -> None:
        result = parser.parse("copy")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.COPY

    def test_paste_as_standalone_matches(self, parser: CommandParser) -> None:
        result = parser.parse("paste")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.PASTE

    def test_copy_embedded_in_sentence_does_not_match(self, parser: CommandParser) -> None:
        """'copy' in a normal sentence should NOT trigger the command."""
        result = parser.parse("Please copy the file to the server")
        assert result.has_command is False

    def test_paste_embedded_in_sentence_does_not_match(self, parser: CommandParser) -> None:
        result = parser.parse("You can paste the link in the browser")
        assert result.has_command is False

    def test_undo_as_standalone_matches(self, parser: CommandParser) -> None:
        result = parser.parse("undo")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.UNDO

    def test_multi_word_command_at_end_matches(self, parser: CommandParser) -> None:
        result = parser.parse("and then select all")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.SELECT_ALL

    def test_delete_last_sentence_at_end_matches(self, parser: CommandParser) -> None:
        result = parser.parse("I made a mistake delete last sentence")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.DELETE_LAST_SENTENCE


# ---------------------------------------------------------------------------
# Command NOT in the middle of text
# ---------------------------------------------------------------------------

class TestCommandParserBoundaryDetection:
    """Commands in the middle of text should not match."""

    def test_command_in_middle_does_not_match(self, parser: CommandParser) -> None:
        result = parser.parse("the new line is ready for testing")
        # 'new line' is in the middle, not at the end
        assert result.has_command is False

    def test_stop_dictation_in_middle_does_not_match(self, parser: CommandParser) -> None:
        result = parser.parse("please stop dictation mode and restart it")
        # 'stop dictation' is not at the end
        assert result.has_command is False


# ---------------------------------------------------------------------------
# All built-in commands matching tests
# ---------------------------------------------------------------------------

class TestCommandParserAllCommands:
    """Test that every built-in command trigger phrase is recognized."""

    @pytest.mark.parametrize(
        "phrase,expected_action",
        [
            ("delete last word", CommandAction.DELETE_LAST_WORD),
            ("delete the last word", CommandAction.DELETE_LAST_WORD),
            ("delete last sentence", CommandAction.DELETE_LAST_SENTENCE),
            ("delete the last sentence", CommandAction.DELETE_LAST_SENTENCE),
            ("undo", CommandAction.UNDO),
            ("undo that", CommandAction.UNDO),
            ("new line", CommandAction.NEW_LINE),
            ("newline", CommandAction.NEW_LINE),
            ("new paragraph", CommandAction.NEW_PARAGRAPH),
            ("select all", CommandAction.SELECT_ALL),
            ("select everything", CommandAction.SELECT_ALL),
            ("copy", CommandAction.COPY),
            ("copy that", CommandAction.COPY),
            ("paste", CommandAction.PASTE),
            ("paste that", CommandAction.PASTE),
            ("stop dictation", CommandAction.STOP_DICTATION),
            ("stop listening", CommandAction.STOP_DICTATION),
        ],
    )
    def test_trigger_phrase_matches(
        self, parser: CommandParser, phrase: str, expected_action: CommandAction
    ) -> None:
        result = parser.parse(phrase)
        assert result.has_command is True, f"'{phrase}' should match"
        assert result.command is not None
        assert result.command.action == expected_action


# ---------------------------------------------------------------------------
# Enabled/disabled toggle tests
# ---------------------------------------------------------------------------

class TestCommandParserEnabledToggle:
    """Tests for the enabled/disabled toggle."""

    def test_parser_enabled_by_default(self, parser: CommandParser) -> None:
        assert parser.enabled is True

    def test_disable_parser_returns_no_commands(self, parser: CommandParser) -> None:
        parser.enabled = False
        result = parser.parse("delete last word")
        assert result.has_command is False

    def test_reenable_parser_resumes_matching(self, parser: CommandParser) -> None:
        parser.enabled = False
        parser.enabled = True
        result = parser.parse("delete last word")
        assert result.has_command is True


# ---------------------------------------------------------------------------
# ParseResult data model tests
# ---------------------------------------------------------------------------

class TestParseResult:
    """Tests for the ParseResult dataclass."""

    def test_parse_result_no_command(self, parser: CommandParser) -> None:
        result = parser.parse("just regular text")
        assert result.has_command is False
        assert result.command is None
        assert result.text_before == ""
        assert result.text_after == ""
        assert result.matched_phrase == ""

    def test_parse_result_with_text_before(self, parser: CommandParser) -> None:
        result = parser.parse("hello world new paragraph")
        assert result.has_command is True
        assert result.text_before.strip() != ""
        assert result.command is not None
        assert result.command.action == CommandAction.NEW_PARAGRAPH


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestCommandParserEdgeCases:
    """Edge case tests for the parser."""

    def test_empty_string(self, parser: CommandParser) -> None:
        result = parser.parse("")
        assert result.has_command is False

    def test_whitespace_only(self, parser: CommandParser) -> None:
        result = parser.parse("   ")
        assert result.has_command is False

    def test_very_long_text_with_command_at_end(self, parser: CommandParser) -> None:
        long_text = "word " * 1000 + "delete last word"
        result = parser.parse(long_text)
        assert result.has_command is True

    def test_special_characters_in_text(self, parser: CommandParser) -> None:
        result = parser.parse("testing @#$%^& symbols delete last word")
        assert result.has_command is True

    def test_hebrew_text_before_english_command(self, parser: CommandParser) -> None:
        """Hebrew text followed by English voice command."""
        result = parser.parse("\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd delete last word")
        assert result.has_command is True
        assert "\u05e9\u05dc\u05d5\u05dd" in result.text_before

    def test_punctuation_only_input(self, parser: CommandParser) -> None:
        """Input of only punctuation should not match any command."""
        result = parser.parse("...!!??")
        assert result.has_command is False

    def test_newline_characters_in_input(self, parser: CommandParser) -> None:
        """Newlines in input should be treated as whitespace."""
        result = parser.parse("some text\nnew line")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.NEW_LINE

    def test_longer_phrase_wins_over_shorter(self, parser: CommandParser) -> None:
        """'delete the last word' should match over 'delete last word'
        when both could match (longer phrase takes priority)."""
        result = parser.parse("delete the last word")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.DELETE_LAST_WORD
        # The matched phrase should be the longer variant
        assert "the" in result.matched_phrase

    def test_undo_that_as_standalone_matches(self, parser: CommandParser) -> None:
        """'undo that' should match as standalone (undo is standalone_only)."""
        result = parser.parse("undo that")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.UNDO

    def test_undo_at_end_of_sentence_does_not_match(self, parser: CommandParser) -> None:
        """'undo' embedded at end of sentence should NOT match (standalone_only)."""
        result = parser.parse("I need to undo")
        assert result.has_command is False

    def test_copy_that_as_standalone_matches(self, parser: CommandParser) -> None:
        """'copy that' should match as standalone."""
        result = parser.parse("copy that")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.COPY

    def test_multiple_trailing_punctuation_stripped(self, parser: CommandParser) -> None:
        """Multiple trailing punctuation marks should all be stripped."""
        result = parser.parse("new line...")
        assert result.has_command is True
        assert result.command is not None
        assert result.command.action == CommandAction.NEW_LINE
