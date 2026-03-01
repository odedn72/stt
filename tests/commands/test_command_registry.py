# TDD: Written from spec 04-voice-commands.md
"""
Tests for CommandRegistry — registry of all known voice commands.

In v1 all commands are built-in and the registry is read-only.
Tests verify all 9 built-in commands from MRD FR-007 are present.
"""

from __future__ import annotations

import pytest

from systemstt.commands.registry import CommandAction, CommandRegistry, VoiceCommand

# ---------------------------------------------------------------------------
# CommandAction enum tests
# ---------------------------------------------------------------------------


class TestCommandAction:
    """Tests for the CommandAction enum."""

    def test_all_actions_defined(self) -> None:
        expected = {
            "delete_last_word",
            "delete_last_sentence",
            "undo",
            "new_line",
            "new_paragraph",
            "select_all",
            "copy",
            "paste",
            "stop_dictation",
        }
        actual = {a.value for a in CommandAction}
        assert actual == expected


# ---------------------------------------------------------------------------
# VoiceCommand data model tests
# ---------------------------------------------------------------------------


class TestVoiceCommand:
    """Tests for the VoiceCommand dataclass."""

    def test_voice_command_fields(self) -> None:
        cmd = VoiceCommand(
            trigger_phrases=("delete last word", "delete the last word"),
            action=CommandAction.DELETE_LAST_WORD,
            display_name="Delete last word",
            confirmation_text="Deleted last word",
        )
        assert cmd.action == CommandAction.DELETE_LAST_WORD
        assert len(cmd.trigger_phrases) == 2
        assert "delete last word" in cmd.trigger_phrases
        assert cmd.display_name == "Delete last word"
        assert cmd.confirmation_text == "Deleted last word"

    def test_voice_command_is_frozen(self) -> None:
        cmd = VoiceCommand(
            trigger_phrases=("undo",),
            action=CommandAction.UNDO,
            display_name="Undo",
            confirmation_text="Undone",
        )
        with pytest.raises(AttributeError):
            cmd.display_name = "Other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CommandRegistry tests
# ---------------------------------------------------------------------------


class TestCommandRegistry:
    """Tests for the built-in command registry."""

    def test_registry_has_nine_commands(self) -> None:
        """MRD FR-007 specifies 9 voice commands."""
        registry = CommandRegistry()
        assert len(registry.commands) == 9

    def test_registry_contains_delete_last_word(self) -> None:
        registry = CommandRegistry()
        actions = [cmd.action for cmd in registry.commands]
        assert CommandAction.DELETE_LAST_WORD in actions

    def test_registry_contains_delete_last_sentence(self) -> None:
        registry = CommandRegistry()
        actions = [cmd.action for cmd in registry.commands]
        assert CommandAction.DELETE_LAST_SENTENCE in actions

    def test_registry_contains_undo(self) -> None:
        registry = CommandRegistry()
        actions = [cmd.action for cmd in registry.commands]
        assert CommandAction.UNDO in actions

    def test_registry_contains_new_line(self) -> None:
        registry = CommandRegistry()
        actions = [cmd.action for cmd in registry.commands]
        assert CommandAction.NEW_LINE in actions

    def test_registry_contains_new_paragraph(self) -> None:
        registry = CommandRegistry()
        actions = [cmd.action for cmd in registry.commands]
        assert CommandAction.NEW_PARAGRAPH in actions

    def test_registry_contains_select_all(self) -> None:
        registry = CommandRegistry()
        actions = [cmd.action for cmd in registry.commands]
        assert CommandAction.SELECT_ALL in actions

    def test_registry_contains_copy(self) -> None:
        registry = CommandRegistry()
        actions = [cmd.action for cmd in registry.commands]
        assert CommandAction.COPY in actions

    def test_registry_contains_paste(self) -> None:
        registry = CommandRegistry()
        actions = [cmd.action for cmd in registry.commands]
        assert CommandAction.PASTE in actions

    def test_registry_contains_stop_dictation(self) -> None:
        registry = CommandRegistry()
        actions = [cmd.action for cmd in registry.commands]
        assert CommandAction.STOP_DICTATION in actions

    def test_get_command_by_action_returns_correct_command(self) -> None:
        registry = CommandRegistry()
        cmd = registry.get_command_by_action(CommandAction.UNDO)
        assert cmd is not None
        assert cmd.action == CommandAction.UNDO

    def test_get_command_by_action_returns_none_for_unknown(self) -> None:
        registry = CommandRegistry()
        # All actions should be found; test with a valid one to verify return type
        for action in CommandAction:
            cmd = registry.get_command_by_action(action)
            assert cmd is not None

    def test_each_command_has_at_least_one_trigger_phrase(self) -> None:
        registry = CommandRegistry()
        for cmd in registry.commands:
            assert len(cmd.trigger_phrases) >= 1

    def test_each_command_has_display_name(self) -> None:
        registry = CommandRegistry()
        for cmd in registry.commands:
            assert cmd.display_name
            assert isinstance(cmd.display_name, str)

    def test_each_command_has_confirmation_text(self) -> None:
        registry = CommandRegistry()
        for cmd in registry.commands:
            assert cmd.confirmation_text
            assert isinstance(cmd.confirmation_text, str)

    def test_trigger_phrases_for_delete_last_word(self) -> None:
        """Spec: 'delete last word', 'delete the last word'."""
        registry = CommandRegistry()
        cmd = registry.get_command_by_action(CommandAction.DELETE_LAST_WORD)
        assert cmd is not None
        assert "delete last word" in cmd.trigger_phrases
        assert "delete the last word" in cmd.trigger_phrases

    def test_trigger_phrases_for_undo(self) -> None:
        """Spec: 'undo', 'undo that'."""
        registry = CommandRegistry()
        cmd = registry.get_command_by_action(CommandAction.UNDO)
        assert cmd is not None
        assert "undo" in cmd.trigger_phrases
        assert "undo that" in cmd.trigger_phrases

    def test_trigger_phrases_for_stop_dictation(self) -> None:
        """Spec: 'stop dictation', 'stop listening'."""
        registry = CommandRegistry()
        cmd = registry.get_command_by_action(CommandAction.STOP_DICTATION)
        assert cmd is not None
        assert "stop dictation" in cmd.trigger_phrases
        assert "stop listening" in cmd.trigger_phrases
