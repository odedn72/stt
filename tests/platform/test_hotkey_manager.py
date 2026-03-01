# TDD: Written from spec 06-hotkey-lifecycle.md
"""
Tests for HotkeyManager ABC, MacOSHotkeyManager, and HotkeyBinding.

All Quartz CGEventTap APIs are mocked. Tests verify:
- HotkeyBinding data model (display strings, from_display_string)
- HotkeyManager registration, unregistration, binding updates
- Error handling for registration failures
- Hotkey matching via tap callback
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from systemstt.errors import HotkeyRegistrationError
from systemstt.platform.base import DEFAULT_HOTKEY, HotkeyBinding, HotkeyManager
from systemstt.platform.macos.hotkey_manager import (
    _KEY_CODES,
    _MODIFIER_FLAGS,
    MacOSHotkeyManager,
)

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
# Helpers for mocking the CGEventTap
# ---------------------------------------------------------------------------


class _QuartzMocks:
    """Container for mocked Quartz symbols, allowing tests to override."""

    def __init__(self) -> None:
        self.CGEventTapCreate = MagicMock(return_value=MagicMock())
        self.CGEventTapEnable = MagicMock()
        self.CGEventMaskBit = MagicMock(return_value=1)
        self.CFMachPortCreateRunLoopSource = MagicMock()
        self.CFRunLoopGetCurrent = MagicMock()
        self.CFRunLoopAddSource = MagicMock()
        self.CFRunLoopRun = MagicMock()
        self.CFRunLoopStop = MagicMock()
        self.CFMachPortInvalidate = MagicMock()
        self.CGEventGetIntegerValueField = MagicMock(return_value=0)
        self.CGEventGetFlags = MagicMock(return_value=0)


def _patch_quartz(mocks: _QuartzMocks | None = None) -> patch:  # type: ignore[type-arg]
    """Patch all Quartz symbols used by the hotkey manager."""
    m = mocks or _QuartzMocks()
    return patch.multiple(
        "systemstt.platform.macos.hotkey_manager",
        _QUARTZ_AVAILABLE=True,
        CGEventTapCreate=m.CGEventTapCreate,
        CGEventTapEnable=m.CGEventTapEnable,
        CGEventMaskBit=m.CGEventMaskBit,
        CFMachPortCreateRunLoopSource=m.CFMachPortCreateRunLoopSource,
        CFRunLoopGetCurrent=m.CFRunLoopGetCurrent,
        CFRunLoopAddSource=m.CFRunLoopAddSource,
        CFRunLoopRun=m.CFRunLoopRun,
        CFRunLoopStop=m.CFRunLoopStop,
        CFMachPortInvalidate=m.CFMachPortInvalidate,
        kCGSessionEventTap=0,
        kCGHeadInsertEventTap=0,
        kCGEventKeyDown=10,
        kCGKeyboardEventKeycode=9,
        kCFRunLoopCommonModes="kCFRunLoopCommonModes",
        CGEventGetIntegerValueField=m.CGEventGetIntegerValueField,
        CGEventGetFlags=m.CGEventGetFlags,
    )


# ---------------------------------------------------------------------------
# MacOSHotkeyManager tests
# ---------------------------------------------------------------------------


class TestMacOSHotkeyManagerRegistration:
    """Tests for hotkey registration."""

    def test_register_hotkey(self) -> None:
        with _patch_quartz():
            manager = MacOSHotkeyManager()
            callback = MagicMock()
            binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
            manager.register(binding, callback)
            assert manager.is_registered is True

    def test_current_binding_after_register(self) -> None:
        with _patch_quartz():
            manager = MacOSHotkeyManager()
            callback = MagicMock()
            binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
            manager.register(binding, callback)
            assert manager.current_binding == binding

    def test_is_registered_false_initially(self) -> None:
        manager = MacOSHotkeyManager()
        assert manager.is_registered is False

    def test_current_binding_none_initially(self) -> None:
        manager = MacOSHotkeyManager()
        assert manager.current_binding is None

    def test_register_sets_target_key_code(self) -> None:
        with _patch_quartz():
            manager = MacOSHotkeyManager()
            manager.register(
                HotkeyBinding(key="space", modifiers=frozenset({"option"})),
                MagicMock(),
            )
            assert manager._target_key_code == _KEY_CODES["space"]

    def test_register_sets_target_modifier_mask(self) -> None:
        with _patch_quartz():
            manager = MacOSHotkeyManager()
            manager.register(
                HotkeyBinding(key="space", modifiers=frozenset({"option"})),
                MagicMock(),
            )
            assert manager._target_modifier_mask == _MODIFIER_FLAGS["option"]

    def test_register_fails_when_tap_returns_none(self) -> None:
        m = _QuartzMocks()
        m.CGEventTapCreate.return_value = None
        with _patch_quartz(m):
            manager = MacOSHotkeyManager()
            with pytest.raises(HotkeyRegistrationError, match="CGEventTap"):
                manager.register(
                    HotkeyBinding(key="space", modifiers=frozenset({"option"})),
                    MagicMock(),
                )


class TestMacOSHotkeyManagerUnregistration:
    """Tests for hotkey unregistration."""

    def test_unregister_after_register(self) -> None:
        with _patch_quartz():
            manager = MacOSHotkeyManager()
            callback = MagicMock()
            binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
            manager.register(binding, callback)
            manager.unregister()
            assert manager.is_registered is False
            assert manager.current_binding is None

    def test_unregister_when_not_registered_is_safe(self) -> None:
        manager = MacOSHotkeyManager()
        manager.unregister()  # Should not raise


class TestMacOSHotkeyManagerUpdateBinding:
    """Tests for changing the hotkey binding."""

    def test_update_binding_changes_key(self) -> None:
        with _patch_quartz():
            manager = MacOSHotkeyManager()
            callback = MagicMock()
            binding1 = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
            manager.register(binding1, callback)

            binding2 = HotkeyBinding(key="f5", modifiers=frozenset({"command"}))
            manager.update_binding(binding2)
            assert manager.current_binding == binding2
            assert manager.is_registered is True

    def test_update_binding_without_register_raises_error(self) -> None:
        manager = MacOSHotkeyManager()
        binding = HotkeyBinding(key="a", modifiers=frozenset({"command", "shift"}))
        with pytest.raises(HotkeyRegistrationError):
            manager.update_binding(binding)

    def test_update_binding_failure_raises_error(self) -> None:
        m = _QuartzMocks()
        with _patch_quartz(m):
            manager = MacOSHotkeyManager()
            callback = MagicMock()
            binding1 = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
            manager.register(binding1, callback)

            # Simulate tap creation failure on the second register
            m.CGEventTapCreate.return_value = None
            binding2 = HotkeyBinding(key="a", modifiers=frozenset({"command", "shift"}))
            with pytest.raises(HotkeyRegistrationError):
                manager.update_binding(binding2)


class TestMacOSHotkeyManagerErrors:
    """Tests for hotkey registration error handling."""

    def test_register_failure_raises_hotkey_registration_error(self) -> None:
        m = _QuartzMocks()
        m.CGEventTapCreate.side_effect = Exception("tap failed")
        with _patch_quartz(m):
            manager = MacOSHotkeyManager()
            callback = MagicMock()
            binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
            with pytest.raises(HotkeyRegistrationError):
                manager.register(binding, callback)

    def test_quartz_not_available_raises_error(self) -> None:
        with patch.object(
            MacOSHotkeyManager,
            "_start_tap",
            side_effect=HotkeyRegistrationError("Quartz framework not available"),
        ):
            manager = MacOSHotkeyManager()
            with pytest.raises(HotkeyRegistrationError, match="Quartz"):
                manager.register(
                    HotkeyBinding(key="space", modifiers=frozenset({"option"})),
                    MagicMock(),
                )


class TestMacOSHotkeyManagerCallback:
    """Tests for hotkey matching in the tap callback."""

    def test_matching_keypress_invokes_callback(self) -> None:
        m = _QuartzMocks()
        with _patch_quartz(m):
            manager = MacOSHotkeyManager()
            callback = MagicMock()
            binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
            manager.register(binding, callback)

            # Simulate a matching key event
            m.CGEventGetIntegerValueField.return_value = _KEY_CODES["space"]
            m.CGEventGetFlags.return_value = _MODIFIER_FLAGS["option"]

            event = MagicMock()
            manager._tap_callback(None, 10, event, None)
            callback.assert_called_once()

    def test_non_matching_keypress_does_not_invoke_callback(self) -> None:
        m = _QuartzMocks()
        with _patch_quartz(m):
            manager = MacOSHotkeyManager()
            callback = MagicMock()
            binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
            manager.register(binding, callback)

            # Simulate a non-matching key event (wrong key)
            m.CGEventGetIntegerValueField.return_value = _KEY_CODES["a"]
            m.CGEventGetFlags.return_value = _MODIFIER_FLAGS["option"]

            event = MagicMock()
            manager._tap_callback(None, 10, event, None)
            callback.assert_not_called()

    def test_wrong_modifiers_does_not_invoke_callback(self) -> None:
        m = _QuartzMocks()
        with _patch_quartz(m):
            manager = MacOSHotkeyManager()
            callback = MagicMock()
            binding = HotkeyBinding(key="space", modifiers=frozenset({"option"}))
            manager.register(binding, callback)

            # Right key, wrong modifiers
            m.CGEventGetIntegerValueField.return_value = _KEY_CODES["space"]
            m.CGEventGetFlags.return_value = _MODIFIER_FLAGS["command"]

            event = MagicMock()
            manager._tap_callback(None, 10, event, None)
            callback.assert_not_called()

    def test_tap_callback_returns_event(self) -> None:
        m = _QuartzMocks()
        with _patch_quartz(m):
            manager = MacOSHotkeyManager()
            manager.register(
                HotkeyBinding(key="space", modifiers=frozenset({"option"})),
                MagicMock(),
            )
            m.CGEventGetIntegerValueField.return_value = 0
            m.CGEventGetFlags.return_value = 0

            event = MagicMock()
            result = manager._tap_callback(None, 10, event, None)
            assert result is event
