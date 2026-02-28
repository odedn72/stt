"""
CommandRegistry — registry of all known voice commands.

In v1, all commands are built-in. The registry is read-only and
contains the 9 commands from MRD FR-007.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence


class CommandAction(str, Enum):
    """Actions that voice commands can trigger."""

    DELETE_LAST_WORD = "delete_last_word"
    DELETE_LAST_SENTENCE = "delete_last_sentence"
    UNDO = "undo"
    NEW_LINE = "new_line"
    NEW_PARAGRAPH = "new_paragraph"
    SELECT_ALL = "select_all"
    COPY = "copy"
    PASTE = "paste"
    STOP_DICTATION = "stop_dictation"


@dataclass(frozen=True)
class VoiceCommand:
    """Definition of a single voice command."""

    trigger_phrases: tuple[str, ...]
    action: CommandAction
    display_name: str
    confirmation_text: str
    standalone_only: bool = False


# Built-in commands from MRD FR-007
_BUILTIN_COMMANDS: tuple[VoiceCommand, ...] = (
    VoiceCommand(
        trigger_phrases=("delete last word", "delete the last word"),
        action=CommandAction.DELETE_LAST_WORD,
        display_name="Delete last word",
        confirmation_text="Deleted last word",
    ),
    VoiceCommand(
        trigger_phrases=("delete last sentence", "delete the last sentence"),
        action=CommandAction.DELETE_LAST_SENTENCE,
        display_name="Delete last sentence",
        confirmation_text="Deleted last sentence",
    ),
    VoiceCommand(
        trigger_phrases=("undo", "undo that"),
        action=CommandAction.UNDO,
        display_name="Undo",
        confirmation_text="Undone",
        standalone_only=True,
    ),
    VoiceCommand(
        trigger_phrases=("new line", "newline"),
        action=CommandAction.NEW_LINE,
        display_name="New line",
        confirmation_text="New line",
    ),
    VoiceCommand(
        trigger_phrases=("new paragraph",),
        action=CommandAction.NEW_PARAGRAPH,
        display_name="New paragraph",
        confirmation_text="New paragraph",
    ),
    VoiceCommand(
        trigger_phrases=("select all", "select everything"),
        action=CommandAction.SELECT_ALL,
        display_name="Select all",
        confirmation_text="Selected all",
    ),
    VoiceCommand(
        trigger_phrases=("copy", "copy that"),
        action=CommandAction.COPY,
        display_name="Copy",
        confirmation_text="Copied",
        standalone_only=True,
    ),
    VoiceCommand(
        trigger_phrases=("paste", "paste that"),
        action=CommandAction.PASTE,
        display_name="Paste",
        confirmation_text="Pasted",
        standalone_only=True,
    ),
    VoiceCommand(
        trigger_phrases=("stop dictation", "stop listening"),
        action=CommandAction.STOP_DICTATION,
        display_name="Stop dictation",
        confirmation_text="Dictation stopped",
    ),
)


class CommandRegistry:
    """Registry of all known voice commands."""

    def __init__(self) -> None:
        self._commands: tuple[VoiceCommand, ...] = _BUILTIN_COMMANDS

    @property
    def commands(self) -> Sequence[VoiceCommand]:
        """Return all registered commands."""
        return self._commands

    def get_command_by_action(self, action: CommandAction) -> Optional[VoiceCommand]:
        """Find a command by its action. Returns None if not found."""
        for cmd in self._commands:
            if cmd.action == action:
                return cmd
        return None
