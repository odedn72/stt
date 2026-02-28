"""
MacOSHotkeyManager — macOS global hotkey using Carbon RegisterEventHotKey.

Uses Carbon event APIs via PyObjC to register system-wide hotkeys.
Carbon hotkey APIs are deprecated but remain the most reliable method
for global hotkeys on macOS from Python.
"""

from __future__ import annotations

import ctypes
import logging
from typing import Callable, Optional

from systemstt.errors import HotkeyRegistrationError
from systemstt.platform.base import HotkeyBinding, HotkeyManager

logger = logging.getLogger(__name__)

# Import Carbon APIs - these are mocked in tests
try:
    from Carbon import CarbonEvt  # type: ignore[import-untyped]
except ImportError:
    # Allow importing on non-macOS for testing with mocks
    CarbonEvt = None  # type: ignore[assignment]

# Virtual key code mapping for Carbon hotkeys
_KEY_CODES: dict[str, int] = {
    "space": 49,
    "a": 0, "b": 11, "c": 8, "d": 2, "e": 14,
    "f": 3, "g": 5, "h": 4, "i": 34, "j": 38,
    "k": 40, "l": 37, "m": 46, "n": 45, "o": 31,
    "p": 35, "q": 12, "r": 15, "s": 1, "t": 17,
    "u": 32, "v": 9, "w": 13, "x": 7, "y": 16,
    "z": 6,
    "0": 29, "1": 18, "2": 19, "3": 20, "4": 21,
    "5": 23, "6": 22, "7": 26, "8": 28, "9": 25,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118,
    "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "return": 36, "tab": 48, "escape": 53,
    "backspace": 51, "delete": 117,
}

# Carbon modifier flag mapping
_MODIFIER_FLAGS: dict[str, int] = {
    "command": 0x0100,   # cmdKey
    "option": 0x0800,    # optionKey
    "shift": 0x0200,     # shiftKey
    "control": 0x1000,   # controlKey
}

# Carbon event constants
_HOTKEY_SIGNATURE = b"SSTT"  # 4-char code for our app
_HOTKEY_ID = 1

# Carbon event class and kind for hotkey events
_K_EVENT_CLASS_KEYBOARD = int.from_bytes(b"kbrd", byteorder="big")
_K_EVENT_HOT_KEY_PRESSED = 5


class MacOSHotkeyManager(HotkeyManager):
    """macOS implementation of HotkeyManager using Carbon RegisterEventHotKey."""

    def __init__(self) -> None:
        self._binding: Optional[HotkeyBinding] = None
        self._callback: Optional[Callable[[], None]] = None
        self._hotkey_ref: object = None
        self._handler_ref: object = None

    def register(self, binding: HotkeyBinding, callback: Callable[[], None]) -> None:
        """Register a global hotkey with the given binding and callback.

        Raises:
            HotkeyRegistrationError: If the hotkey cannot be registered.
        """
        try:
            # Unregister existing hotkey if any
            if self._hotkey_ref is not None:
                self._unregister_carbon_hotkey()

            # Map binding to Carbon key code and modifiers
            key_code = _KEY_CODES.get(binding.key.lower(), 0)
            modifier_mask = 0
            for mod in binding.modifiers:
                modifier_mask |= _MODIFIER_FLAGS.get(mod, 0)

            # Store callback
            self._callback = callback

            # Register the Carbon hotkey
            self._register_carbon_hotkey(key_code, modifier_mask)
            self._binding = binding

            logger.info("Registered hotkey: %s", binding.display_string())

        except HotkeyRegistrationError:
            raise
        except Exception as exc:
            raise HotkeyRegistrationError(
                f"Failed to register hotkey {binding.display_string()}: {exc}"
            ) from exc

    def unregister(self) -> None:
        """Unregister the current hotkey. Safe to call when no hotkey is registered."""
        if self._hotkey_ref is not None:
            try:
                self._unregister_carbon_hotkey()
            except Exception:
                logger.warning("Error unregistering hotkey", exc_info=True)
        self._binding = None
        self._callback = None
        self._hotkey_ref = None
        self._handler_ref = None

    def update_binding(self, binding: HotkeyBinding) -> None:
        """Change the hotkey binding. Must be registered first.

        Raises:
            HotkeyRegistrationError: If the new binding cannot be registered.
        """
        if self._callback is None:
            raise HotkeyRegistrationError(
                "Cannot update binding: no hotkey is currently registered."
            )

        old_binding = self._binding
        old_hotkey_ref = self._hotkey_ref
        old_handler_ref = self._handler_ref

        try:
            # Unregister old hotkey
            if self._hotkey_ref is not None:
                self._unregister_carbon_hotkey()

            # Register new hotkey
            key_code = _KEY_CODES.get(binding.key.lower(), 0)
            modifier_mask = 0
            for mod in binding.modifiers:
                modifier_mask |= _MODIFIER_FLAGS.get(mod, 0)

            self._register_carbon_hotkey(key_code, modifier_mask)
            self._binding = binding

            logger.info("Updated hotkey to: %s", binding.display_string())

        except Exception as exc:
            # Attempt to restore previous binding
            self._binding = old_binding
            self._hotkey_ref = old_hotkey_ref
            self._handler_ref = old_handler_ref
            raise HotkeyRegistrationError(
                f"Failed to update hotkey to {binding.display_string()}: {exc}"
            ) from exc

    @property
    def is_registered(self) -> bool:
        """Return True if a hotkey is currently registered."""
        return self._binding is not None

    @property
    def current_binding(self) -> HotkeyBinding | None:
        """Return the current hotkey binding, or None if not registered."""
        return self._binding

    def _register_carbon_hotkey(self, key_code: int, modifier_mask: int) -> None:
        """Register the hotkey and install a Carbon event handler.

        Installs a Carbon event handler for kEventHotKeyPressed that
        dispatches to _on_hotkey_pressed when the registered hotkey is
        pressed. Stores both the hotkey ref and handler ref for cleanup.
        """
        # Install the Carbon event handler for hotkey events if not already installed
        if self._handler_ref is None:
            event_type_spec = (
                _K_EVENT_CLASS_KEYBOARD,
                _K_EVENT_HOT_KEY_PRESSED,
            )
            handler_ref = CarbonEvt.InstallApplicationEventHandler(
                self._carbon_event_callback,
                [event_type_spec],
            )
            self._handler_ref = handler_ref

        # Register the hotkey itself
        hotkey_ref = CarbonEvt.RegisterEventHotKey(
            key_code,
            modifier_mask,
            (_HOTKEY_SIGNATURE, _HOTKEY_ID),
            CarbonEvt.GetApplicationEventTarget(),
            0,
        )
        self._hotkey_ref = hotkey_ref

    def _carbon_event_callback(
        self,
        next_handler: object,
        event: object,
        user_data: object,
    ) -> int:
        """Carbon event handler callback for hotkey events.

        Called by the Carbon event system when a registered hotkey is pressed.
        Dispatches to _on_hotkey_pressed.

        Returns 0 (noErr) to indicate the event was handled.
        """
        self._on_hotkey_pressed()
        return 0  # noErr

    def _unregister_carbon_hotkey(self) -> None:
        """Unregister the current Carbon hotkey and remove the event handler."""
        if self._hotkey_ref is not None:
            CarbonEvt.UnregisterEventHotKey(self._hotkey_ref)
            self._hotkey_ref = None

        if self._handler_ref is not None:
            CarbonEvt.RemoveEventHandler(self._handler_ref)
            self._handler_ref = None

    def _on_hotkey_pressed(self) -> None:
        """Called when the registered hotkey is pressed."""
        if self._callback is not None:
            try:
                self._callback()
            except Exception:
                logger.error("Error in hotkey callback", exc_info=True)
