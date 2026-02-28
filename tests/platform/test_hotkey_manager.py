# TDD: Written from spec 06-hotkey-lifecycle.md
"""
Tests for HotkeyManager ABC, MacOSHotkeyManager, and HotkeyBinding.

All Carbon/CGEvent APIs are mocked. Tests verify:
- HotkeyBinding data model (display strings, from_display_string)
- HotkeyManager registration, unregistration, binding updates
- Error handling for registration failures
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from systemstt.platform.base import HotkeyManager, HotkeyBinding, DEFAULT_HOTKEY
from systemstt.platform.macos.hotkey_manager import MacOSHotkeyManager
from systemstt.errors import HotkeyRegistrationError


# ---------------------------------------------------------------------------
# HotkeyBinding tests
# ---------------------------------------------------------------------------

class TestHotkeyBinding:
    """Tests for the HotkeyBinding data model."""

    def test_default_hotkey_is_option_space(self) -> None:
        assert DEFAULT_HOTKEY.key == "space"
        assert "option" in DEFAULT_HOTKEY.modifiers

    def test_hotkey_binding_fields(self) -> None:
        binding = HotkeyBinding(
            key="space",
            modifiers=frozenset({"option"}),
        )
        assert binding.key == "space"
        assert binding.modifiers == frozenset({"option"})

    def test_display_string_option_space(self) -> None:
        binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        display = binding.display_string()
        assert "\u2325" in display or "Space" in display or "space" in display.lower()

    def test_display_string_command_shift_a(self) -> None:
        binding = HotkeyBinding(key="a", modifiers=frozenset({"command", "shift"}))
        display = binding.display_string()
        assert isinstance(display, str)
        assert len(display) > 0

    def test_from_display_string_roundtrip(self) -> None:
        original = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        display = original.display_string()
        parsed = HotkeyBinding.from_display_string(display)
        assert parsed.key == original.key
        assert parsed.modifiers == original.modifiers

    def test_hotkey_binding_is_frozen(self) -> None:
        binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        with pytest.raises(AttributeError):
            binding.key = "a"  # type: ignore[misc]

    def test_hotkey_binding_equality(self) -> None:
        a = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        b = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        assert a == b

    def test_hotkey_binding_inequality(self) -> None:
        a = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        b = HotkeyBinding(key="a", modifiers=frozenset({"command"}))
        assert a != b


# ---------------------------------------------------------------------------
# HotkeyManager ABC tests
# ---------------------------------------------------------------------------

class TestHotkeyManagerABC:
    """Tests that HotkeyManager cannot be instantiated directly."""

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            HotkeyManager()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# MacOSHotkeyManager tests
# ---------------------------------------------------------------------------

class TestMacOSHotkeyManagerRegistration:
    """Tests for hotkey registration."""

    @patch("systemstt.platform.macos.hotkey_manager.CarbonEvt")
    def test_register_hotkey(self, mock_carbon: MagicMock) -> None:
        manager = MacOSHotkeyManager()
        callback = MagicMock()
        binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        manager.register(binding, callback)
        assert manager.is_registered is True

    @patch("systemstt.platform.macos.hotkey_manager.CarbonEvt")
    def test_current_binding_after_register(self, mock_carbon: MagicMock) -> None:
        manager = MacOSHotkeyManager()
        callback = MagicMock()
        binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        manager.register(binding, callback)
        assert manager.current_binding == binding

    @patch("systemstt.platform.macos.hotkey_manager.CarbonEvt")
    def test_is_registered_false_initially(self, mock_carbon: MagicMock) -> None:
        manager = MacOSHotkeyManager()
        assert manager.is_registered is False

    @patch("systemstt.platform.macos.hotkey_manager.CarbonEvt")
    def test_current_binding_none_initially(self, mock_carbon: MagicMock) -> None:
        manager = MacOSHotkeyManager()
        assert manager.current_binding is None


class TestMacOSHotkeyManagerUnregistration:
    """Tests for hotkey unregistration."""

    @patch("systemstt.platform.macos.hotkey_manager.CarbonEvt")
    def test_unregister_after_register(self, mock_carbon: MagicMock) -> None:
        manager = MacOSHotkeyManager()
        callback = MagicMock()
        binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        manager.register(binding, callback)
        manager.unregister()
        assert manager.is_registered is False
        assert manager.current_binding is None

    @patch("systemstt.platform.macos.hotkey_manager.CarbonEvt")
    def test_unregister_when_not_registered_is_safe(self, mock_carbon: MagicMock) -> None:
        manager = MacOSHotkeyManager()
        manager.unregister()  # Should not raise


class TestMacOSHotkeyManagerUpdateBinding:
    """Tests for changing the hotkey binding."""

    @patch("systemstt.platform.macos.hotkey_manager.CarbonEvt")
    def test_update_binding_changes_key(self, mock_carbon: MagicMock) -> None:
        manager = MacOSHotkeyManager()
        callback = MagicMock()
        binding1 = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        manager.register(binding1, callback)

        binding2 = HotkeyBinding(key="f5", modifiers=frozenset({"command"}))
        manager.update_binding(binding2)
        assert manager.current_binding == binding2
        assert manager.is_registered is True

    @patch("systemstt.platform.macos.hotkey_manager.CarbonEvt")
    def test_update_binding_failure_raises_error(self, mock_carbon: MagicMock) -> None:
        manager = MacOSHotkeyManager()
        callback = MagicMock()
        binding1 = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        manager.register(binding1, callback)

        # Simulate registration failure
        mock_carbon.RegisterEventHotKey.side_effect = Exception("hotkey in use")
        binding2 = HotkeyBinding(key="a", modifiers=frozenset({"command", "shift"}))
        with pytest.raises(HotkeyRegistrationError):
            manager.update_binding(binding2)


class TestMacOSHotkeyManagerErrors:
    """Tests for hotkey registration error handling."""

    @patch("systemstt.platform.macos.hotkey_manager.CarbonEvt")
    def test_register_failure_raises_hotkey_registration_error(
        self, mock_carbon: MagicMock
    ) -> None:
        mock_carbon.RegisterEventHotKey.side_effect = Exception("in use")
        manager = MacOSHotkeyManager()
        callback = MagicMock()
        binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
        with pytest.raises(HotkeyRegistrationError):
            manager.register(binding, callback)
