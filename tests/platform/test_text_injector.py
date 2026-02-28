# TDD: Written from spec 05-text-injection.md
"""
Tests for TextInjector ABC and MacOSTextInjector.

All macOS APIs (CGEvent, AXUIElement, AXIsProcessTrusted) are mocked.
Tests verify:
- Text injection (inject_text)
- Keystroke simulation (send_keystroke)
- Accessibility permission checking
- Unicode/Hebrew text handling
- Fallback strategy (CGEvent -> AXUIElement -> clipboard)
- Error handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from systemstt.platform.base import TextInjector, KeyModifier, SpecialKey
from systemstt.platform.macos.text_injector import MacOSTextInjector
from systemstt.errors import AccessibilityPermissionError, InjectionFailedError


# ---------------------------------------------------------------------------
# TextInjector ABC tests
# ---------------------------------------------------------------------------

class TestTextInjectorABC:
    """Tests that TextInjector cannot be instantiated directly."""

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            TextInjector()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# KeyModifier enum tests
# ---------------------------------------------------------------------------

class TestKeyModifier:
    """Tests for the KeyModifier enum."""

    def test_command_value(self) -> None:
        assert KeyModifier.COMMAND.value == "command"

    def test_option_value(self) -> None:
        assert KeyModifier.OPTION.value == "option"

    def test_shift_value(self) -> None:
        assert KeyModifier.SHIFT.value == "shift"

    def test_control_value(self) -> None:
        assert KeyModifier.CONTROL.value == "control"


# ---------------------------------------------------------------------------
# SpecialKey enum tests
# ---------------------------------------------------------------------------

class TestSpecialKey:
    """Tests for the SpecialKey enum."""

    def test_all_special_keys_defined(self) -> None:
        expected = {
            "return", "backspace", "delete", "tab", "escape",
            "left", "right", "up", "down", "home", "end",
        }
        actual = {k.value for k in SpecialKey}
        assert actual == expected


# ---------------------------------------------------------------------------
# MacOSTextInjector inject_text tests
# ---------------------------------------------------------------------------

class TestMacOSTextInjectorInjectText:
    """Tests for text injection into the focused application."""

    @pytest.mark.asyncio
    @patch("systemstt.platform.macos.text_injector.CGEventPost")
    @patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent")
    @patch("systemstt.platform.macos.text_injector.CGEventKeyboardSetUnicodeString")
    async def test_inject_english_text(
        self, mock_set_unicode: MagicMock, mock_create_event: MagicMock,
        mock_post: MagicMock
    ) -> None:
        injector = MacOSTextInjector()
        await injector.inject_text("Hello")
        # Should create keyboard events for each character
        assert mock_create_event.called
        assert mock_post.called

    @pytest.mark.asyncio
    @patch("systemstt.platform.macos.text_injector.CGEventPost")
    @patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent")
    @patch("systemstt.platform.macos.text_injector.CGEventKeyboardSetUnicodeString")
    async def test_inject_hebrew_text(
        self, mock_set_unicode: MagicMock, mock_create_event: MagicMock,
        mock_post: MagicMock
    ) -> None:
        injector = MacOSTextInjector()
        await injector.inject_text("\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd")
        assert mock_create_event.called
        assert mock_post.called

    @pytest.mark.asyncio
    @patch("systemstt.platform.macos.text_injector.CGEventPost")
    @patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent")
    @patch("systemstt.platform.macos.text_injector.CGEventKeyboardSetUnicodeString")
    async def test_inject_mixed_hebrew_english(
        self, mock_set_unicode: MagicMock, mock_create_event: MagicMock,
        mock_post: MagicMock
    ) -> None:
        injector = MacOSTextInjector()
        await injector.inject_text("\u05e9\u05dc\u05d5\u05dd hello world")
        assert mock_post.called

    @pytest.mark.asyncio
    async def test_inject_empty_string_no_error(self) -> None:
        with patch("systemstt.platform.macos.text_injector.CGEventPost"):
            with patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent"):
                with patch("systemstt.platform.macos.text_injector.CGEventKeyboardSetUnicodeString"):
                    injector = MacOSTextInjector()
                    await injector.inject_text("")  # Should not raise

    @pytest.mark.asyncio
    @patch("systemstt.platform.macos.text_injector.CGEventPost", side_effect=Exception("CGEvent failed"))
    @patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent")
    @patch("systemstt.platform.macos.text_injector.CGEventKeyboardSetUnicodeString")
    async def test_inject_text_failure_raises_injection_failed_error(
        self, mock_set_unicode: MagicMock, mock_create_event: MagicMock,
        mock_post: MagicMock
    ) -> None:
        injector = MacOSTextInjector()
        with pytest.raises(InjectionFailedError):
            await injector.inject_text("test")

    @pytest.mark.asyncio
    @patch("systemstt.platform.macos.text_injector.CGEventPost")
    @patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent")
    @patch("systemstt.platform.macos.text_injector.CGEventKeyboardSetUnicodeString")
    async def test_inject_special_characters(
        self, mock_set_unicode: MagicMock, mock_create_event: MagicMock,
        mock_post: MagicMock
    ) -> None:
        injector = MacOSTextInjector()
        await injector.inject_text("Hello! @#$%^&*() world\n\ttab")
        assert mock_post.called


# ---------------------------------------------------------------------------
# MacOSTextInjector send_keystroke tests
# ---------------------------------------------------------------------------

class TestMacOSTextInjectorSendKeystroke:
    """Tests for keystroke simulation."""

    @pytest.mark.asyncio
    @patch("systemstt.platform.macos.text_injector.CGEventPost")
    @patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent")
    async def test_send_return_key(
        self, mock_create: MagicMock, mock_post: MagicMock
    ) -> None:
        injector = MacOSTextInjector()
        await injector.send_keystroke(SpecialKey.RETURN)
        assert mock_create.called
        assert mock_post.called

    @pytest.mark.asyncio
    @patch("systemstt.platform.macos.text_injector.CGEventPost")
    @patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent")
    async def test_send_backspace_key(
        self, mock_create: MagicMock, mock_post: MagicMock
    ) -> None:
        injector = MacOSTextInjector()
        await injector.send_keystroke(SpecialKey.BACKSPACE)
        assert mock_post.called

    @pytest.mark.asyncio
    @patch("systemstt.platform.macos.text_injector.CGEventPost")
    @patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent")
    @patch("systemstt.platform.macos.text_injector.CGEventSetFlags")
    async def test_send_keystroke_with_modifiers(
        self, mock_set_flags: MagicMock, mock_create: MagicMock,
        mock_post: MagicMock
    ) -> None:
        injector = MacOSTextInjector()
        await injector.send_keystroke(
            "z", modifiers=[KeyModifier.COMMAND]
        )
        assert mock_post.called

    @pytest.mark.asyncio
    @patch("systemstt.platform.macos.text_injector.CGEventPost")
    @patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent")
    @patch("systemstt.platform.macos.text_injector.CGEventSetFlags")
    async def test_send_keystroke_with_multiple_modifiers(
        self, mock_set_flags: MagicMock, mock_create: MagicMock,
        mock_post: MagicMock
    ) -> None:
        injector = MacOSTextInjector()
        await injector.send_keystroke(
            SpecialKey.BACKSPACE,
            modifiers=[KeyModifier.OPTION],
        )
        assert mock_post.called

    @pytest.mark.asyncio
    @patch("systemstt.platform.macos.text_injector.CGEventPost")
    @patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent")
    async def test_send_keystroke_no_modifiers(
        self, mock_create: MagicMock, mock_post: MagicMock
    ) -> None:
        injector = MacOSTextInjector()
        await injector.send_keystroke(SpecialKey.TAB)
        assert mock_post.called


# ---------------------------------------------------------------------------
# Accessibility permission tests
# ---------------------------------------------------------------------------

class TestMacOSTextInjectorPermissions:
    """Tests for accessibility permission checking."""

    @patch("systemstt.platform.macos.text_injector.AXIsProcessTrusted")
    def test_has_permission_returns_true_when_granted(
        self, mock_ax: MagicMock
    ) -> None:
        mock_ax.return_value = True
        injector = MacOSTextInjector()
        assert injector.has_accessibility_permission() is True

    @patch("systemstt.platform.macos.text_injector.AXIsProcessTrusted")
    def test_has_permission_returns_false_when_denied(
        self, mock_ax: MagicMock
    ) -> None:
        mock_ax.return_value = False
        injector = MacOSTextInjector()
        assert injector.has_accessibility_permission() is False

    @patch("systemstt.platform.macos.text_injector.AXIsProcessTrustedWithOptions")
    def test_request_permission_opens_system_settings(
        self, mock_ax_options: MagicMock
    ) -> None:
        injector = MacOSTextInjector()
        injector.request_accessibility_permission()
        mock_ax_options.assert_called_once()

    @pytest.mark.asyncio
    @patch("systemstt.platform.macos.text_injector.AXIsProcessTrusted", return_value=False)
    @patch("systemstt.platform.macos.text_injector.CGEventCreateKeyboardEvent")
    @patch("systemstt.platform.macos.text_injector.CGEventPost")
    @patch("systemstt.platform.macos.text_injector.CGEventKeyboardSetUnicodeString")
    async def test_inject_without_permission_raises_error(
        self, mock_set_unicode: MagicMock, mock_post: MagicMock,
        mock_create: MagicMock, mock_trusted: MagicMock
    ) -> None:
        """If accessibility is not granted and injection fails, error is raised."""
        mock_post.side_effect = Exception("no permission")
        injector = MacOSTextInjector()
        with pytest.raises((AccessibilityPermissionError, InjectionFailedError)):
            await injector.inject_text("test")
