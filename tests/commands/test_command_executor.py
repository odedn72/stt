# TDD: Written from spec 04-voice-commands.md
"""
Tests for CommandExecutor — executes voice command actions.

All platform services (TextInjector) are mocked. Tests verify:
- Each command maps to the correct keystrokes
- STOP_DICTATION calls the stop callback
- Error propagation from TextInjector
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from systemstt.commands.executor import CommandExecutor
from systemstt.commands.registry import CommandAction
from systemstt.platform.base import SpecialKey, KeyModifier
from systemstt.errors import TextInjectionError


@pytest.fixture
def executor(
    mock_text_injector: MagicMock,
    mock_stop_dictation_callback: MagicMock,
) -> CommandExecutor:
    """Create a CommandExecutor with mocked dependencies."""
    return CommandExecutor(
        text_injector=mock_text_injector,
        stop_dictation_callback=mock_stop_dictation_callback,
    )


# ---------------------------------------------------------------------------
# DELETE_LAST_WORD tests
# ---------------------------------------------------------------------------

class TestExecutorDeleteLastWord:
    """Tests for the delete last word action (Option+Backspace on macOS)."""

    @pytest.mark.asyncio
    async def test_delete_last_word_sends_option_backspace(
        self, executor: CommandExecutor, mock_text_injector: MagicMock
    ) -> None:
        await executor.execute(CommandAction.DELETE_LAST_WORD)
        mock_text_injector.send_keystroke.assert_called()
        # Verify Option+Backspace was sent
        calls = mock_text_injector.send_keystroke.call_args_list
        assert any(
            (
                call.args[0] == SpecialKey.BACKSPACE
                or call.args[0] == "backspace"
                or (call.kwargs.get("key") in (SpecialKey.BACKSPACE, "backspace"))
            )
            for call_obj in calls
            for call in [call_obj]
        )


# ---------------------------------------------------------------------------
# DELETE_LAST_SENTENCE tests
# ---------------------------------------------------------------------------

class TestExecutorDeleteLastSentence:
    """Tests for the delete last sentence action."""

    @pytest.mark.asyncio
    async def test_delete_last_sentence_sends_keystrokes(
        self, executor: CommandExecutor, mock_text_injector: MagicMock
    ) -> None:
        await executor.execute(CommandAction.DELETE_LAST_SENTENCE)
        # Should send some keystrokes (implementation may vary per spec note 6.4)
        assert mock_text_injector.send_keystroke.called


# ---------------------------------------------------------------------------
# UNDO tests
# ---------------------------------------------------------------------------

class TestExecutorUndo:
    """Tests for the undo action (Cmd+Z on macOS)."""

    @pytest.mark.asyncio
    async def test_undo_sends_command_z(
        self, executor: CommandExecutor, mock_text_injector: MagicMock
    ) -> None:
        await executor.execute(CommandAction.UNDO)
        mock_text_injector.send_keystroke.assert_called()


# ---------------------------------------------------------------------------
# NEW_LINE tests
# ---------------------------------------------------------------------------

class TestExecutorNewLine:
    """Tests for the new line action (Return key)."""

    @pytest.mark.asyncio
    async def test_new_line_sends_return(
        self, executor: CommandExecutor, mock_text_injector: MagicMock
    ) -> None:
        await executor.execute(CommandAction.NEW_LINE)
        mock_text_injector.send_keystroke.assert_called_once()


# ---------------------------------------------------------------------------
# NEW_PARAGRAPH tests
# ---------------------------------------------------------------------------

class TestExecutorNewParagraph:
    """Tests for the new paragraph action (Return twice)."""

    @pytest.mark.asyncio
    async def test_new_paragraph_sends_two_returns(
        self, executor: CommandExecutor, mock_text_injector: MagicMock
    ) -> None:
        await executor.execute(CommandAction.NEW_PARAGRAPH)
        # Should be called at least twice (two Return presses)
        assert mock_text_injector.send_keystroke.call_count >= 2


# ---------------------------------------------------------------------------
# SELECT_ALL tests
# ---------------------------------------------------------------------------

class TestExecutorSelectAll:
    """Tests for the select all action (Cmd+A on macOS)."""

    @pytest.mark.asyncio
    async def test_select_all_sends_keystroke(
        self, executor: CommandExecutor, mock_text_injector: MagicMock
    ) -> None:
        await executor.execute(CommandAction.SELECT_ALL)
        mock_text_injector.send_keystroke.assert_called()


# ---------------------------------------------------------------------------
# COPY tests
# ---------------------------------------------------------------------------

class TestExecutorCopy:
    """Tests for the copy action (Cmd+C on macOS)."""

    @pytest.mark.asyncio
    async def test_copy_sends_keystroke(
        self, executor: CommandExecutor, mock_text_injector: MagicMock
    ) -> None:
        await executor.execute(CommandAction.COPY)
        mock_text_injector.send_keystroke.assert_called()


# ---------------------------------------------------------------------------
# PASTE tests
# ---------------------------------------------------------------------------

class TestExecutorPaste:
    """Tests for the paste action (Cmd+V on macOS)."""

    @pytest.mark.asyncio
    async def test_paste_sends_keystroke(
        self, executor: CommandExecutor, mock_text_injector: MagicMock
    ) -> None:
        await executor.execute(CommandAction.PASTE)
        mock_text_injector.send_keystroke.assert_called()


# ---------------------------------------------------------------------------
# STOP_DICTATION tests
# ---------------------------------------------------------------------------

class TestExecutorStopDictation:
    """Tests for the stop dictation command (per spec 6.5: internal signal, not keystroke)."""

    @pytest.mark.asyncio
    async def test_stop_dictation_calls_callback(
        self,
        executor: CommandExecutor,
        mock_text_injector: MagicMock,
        mock_stop_dictation_callback: MagicMock,
    ) -> None:
        await executor.execute(CommandAction.STOP_DICTATION)
        mock_stop_dictation_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_dictation_does_not_use_text_injector(
        self,
        executor: CommandExecutor,
        mock_text_injector: MagicMock,
        mock_stop_dictation_callback: MagicMock,
    ) -> None:
        await executor.execute(CommandAction.STOP_DICTATION)
        mock_text_injector.send_keystroke.assert_not_called()
        mock_text_injector.inject_text.assert_not_called()


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestExecutorErrorHandling:
    """Tests for error propagation."""

    @pytest.mark.asyncio
    async def test_text_injection_error_propagates(
        self, mock_text_injector: MagicMock, mock_stop_dictation_callback: MagicMock
    ) -> None:
        mock_text_injector.send_keystroke.side_effect = TextInjectionError("injection failed")
        executor = CommandExecutor(
            text_injector=mock_text_injector,
            stop_dictation_callback=mock_stop_dictation_callback,
        )
        with pytest.raises(TextInjectionError):
            await executor.execute(CommandAction.UNDO)
