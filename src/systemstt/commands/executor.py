"""
CommandExecutor — executes voice command actions.

Maps recognized command actions to platform operations (keystrokes,
text manipulation) via the TextInjector interface.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from systemstt.commands.registry import CommandAction
from systemstt.platform.base import KeyModifier, SpecialKey

logger = logging.getLogger(__name__)


class CommandExecutor:
    """Executes voice command actions via the TextInjector."""

    def __init__(
        self,
        text_injector: Any,  # noqa: ANN401
        stop_dictation_callback: Callable[[], None],
    ) -> None:
        self._injector = text_injector
        self._stop_callback = stop_dictation_callback

    async def execute(self, action: CommandAction) -> None:
        """Execute a command action.

        Raises TextInjectionError if the injector fails.
        """
        logger.info("Executing command: %s", action.value)

        if action == CommandAction.DELETE_LAST_WORD:
            await self._delete_last_word()
        elif action == CommandAction.DELETE_LAST_SENTENCE:
            await self._delete_last_sentence()
        elif action == CommandAction.UNDO:
            await self._undo()
        elif action == CommandAction.NEW_LINE:
            await self._new_line()
        elif action == CommandAction.NEW_PARAGRAPH:
            await self._new_paragraph()
        elif action == CommandAction.SELECT_ALL:
            await self._select_all()
        elif action == CommandAction.COPY:
            await self._copy()
        elif action == CommandAction.PASTE:
            await self._paste()
        elif action == CommandAction.STOP_DICTATION:
            self._stop_callback()
        else:
            logger.warning("Unknown command action: %s", action)

    async def _delete_last_word(self) -> None:
        """Delete the last word: Option+Backspace on macOS."""
        await self._injector.send_keystroke(SpecialKey.BACKSPACE, modifiers=[KeyModifier.OPTION])

    async def _delete_last_sentence(self) -> None:
        """Delete the last sentence.

        Uses Cmd+Z (undo) to reverse the last text injection, which
        in practice removes the last dictated chunk — the closest
        approximation to "delete last sentence" without clipboard
        introspection.
        """
        await self._injector.send_keystroke("z", modifiers=[KeyModifier.COMMAND])

    async def _undo(self) -> None:
        """Undo: Cmd+Z on macOS."""
        await self._injector.send_keystroke("z", modifiers=[KeyModifier.COMMAND])

    async def _new_line(self) -> None:
        """Insert a new line: Return key."""
        await self._injector.send_keystroke(SpecialKey.RETURN)

    async def _new_paragraph(self) -> None:
        """Insert a new paragraph: Return twice."""
        await self._injector.send_keystroke(SpecialKey.RETURN)
        await self._injector.send_keystroke(SpecialKey.RETURN)

    async def _select_all(self) -> None:
        """Select all: Cmd+A on macOS."""
        await self._injector.send_keystroke("a", modifiers=[KeyModifier.COMMAND])

    async def _copy(self) -> None:
        """Copy: Cmd+C on macOS."""
        await self._injector.send_keystroke("c", modifiers=[KeyModifier.COMMAND])

    async def _paste(self) -> None:
        """Paste: Cmd+V on macOS."""
        await self._injector.send_keystroke("v", modifiers=[KeyModifier.COMMAND])
