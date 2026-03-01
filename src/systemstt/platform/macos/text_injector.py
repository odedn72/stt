"""
MacOSTextInjector — macOS Accessibility-based text injection.

Uses CGEvent APIs via PyObjC to inject text into the focused application
at the cursor position. Supports Unicode text (including Hebrew/RTL) and
keystroke simulation with modifier keys.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from systemstt.errors import AccessibilityPermissionError, InjectionFailedError
from systemstt.platform.base import KeyModifier, SpecialKey, TextInjector

logger = logging.getLogger(__name__)

# Import macOS APIs - these are mocked in tests
# Quartz and ApplicationServices are imported separately so that a missing
# ApplicationServices package doesn't prevent the CGEvent functions from loading.
try:
    from Quartz import (  # type: ignore[import-untyped]
        CGEventCreateKeyboardEvent,
        CGEventKeyboardSetUnicodeString,
        CGEventPost,
        CGEventSetFlags,
        kCGEventFlagMaskAlternate,
        kCGEventFlagMaskCommand,
        kCGEventFlagMaskControl,
        kCGEventFlagMaskShift,
        kCGEventKeyDown,
        kCGEventKeyUp,
        kCGHIDEventTap,
    )
except ImportError:
    # Allow importing on non-macOS for testing with mocks
    CGEventPost = None
    CGEventCreateKeyboardEvent = None
    CGEventKeyboardSetUnicodeString = None
    CGEventSetFlags = None
    kCGHIDEventTap = 0  # noqa: N816
    kCGEventKeyDown = 10  # noqa: N816
    kCGEventKeyUp = 11  # noqa: N816
    kCGEventFlagMaskCommand = 1 << 20  # noqa: N816
    kCGEventFlagMaskAlternate = 1 << 19  # noqa: N816
    kCGEventFlagMaskShift = 1 << 17  # noqa: N816
    kCGEventFlagMaskControl = 1 << 18  # noqa: N816

try:
    from ApplicationServices import (  # type: ignore[import-untyped]
        AXIsProcessTrusted,
        AXIsProcessTrustedWithOptions,
    )
except ImportError:
    AXIsProcessTrusted = None
    AXIsProcessTrustedWithOptions = None

# Virtual key codes for special keys
_SPECIAL_KEY_CODES: dict[str, int] = {
    "return": 0x24,
    "backspace": 0x33,
    "delete": 0x75,
    "tab": 0x30,
    "escape": 0x35,
    "left": 0x7B,
    "right": 0x7C,
    "up": 0x7E,
    "down": 0x7D,
    "home": 0x73,
    "end": 0x77,
}

# Virtual key codes for letter keys
_LETTER_KEY_CODES: dict[str, int] = {
    "a": 0x00,
    "b": 0x0B,
    "c": 0x08,
    "d": 0x02,
    "e": 0x0E,
    "f": 0x03,
    "g": 0x05,
    "h": 0x04,
    "i": 0x22,
    "j": 0x26,
    "k": 0x28,
    "l": 0x25,
    "m": 0x2E,
    "n": 0x2D,
    "o": 0x1F,
    "p": 0x23,
    "q": 0x0C,
    "r": 0x0F,
    "s": 0x01,
    "t": 0x11,
    "u": 0x20,
    "v": 0x09,
    "w": 0x0D,
    "x": 0x07,
    "y": 0x10,
    "z": 0x06,
}

# Modifier flag mapping
_MODIFIER_FLAGS: dict[str, int] = {
    "command": kCGEventFlagMaskCommand,
    "option": kCGEventFlagMaskAlternate,
    "shift": kCGEventFlagMaskShift,
    "control": kCGEventFlagMaskControl,
}


class MacOSTextInjector(TextInjector):
    """macOS implementation of TextInjector using CGEvent APIs."""

    async def inject_text(self, text: str) -> None:
        """Inject text using CGEvent keyboard events with Unicode strings.

        Each character is sent as a key-down/key-up pair with the Unicode
        string set on the event. This works for all Unicode characters
        including Hebrew and other non-ASCII scripts.
        """
        if not text:
            return

        try:
            for char in text:
                # Create key-down event
                event_down = CGEventCreateKeyboardEvent(None, 0, True)
                CGEventKeyboardSetUnicodeString(event_down, len(char), char)
                CGEventPost(kCGHIDEventTap, event_down)

                # Create key-up event
                event_up = CGEventCreateKeyboardEvent(None, 0, False)
                CGEventKeyboardSetUnicodeString(event_up, len(char), char)
                CGEventPost(kCGHIDEventTap, event_up)
        except Exception as exc:
            if AXIsProcessTrusted is not None and not AXIsProcessTrusted():
                raise AccessibilityPermissionError(
                    "Accessibility permission not granted. Cannot inject text."
                ) from exc
            raise InjectionFailedError(f"Failed to inject text: {exc}") from exc

    async def send_keystroke(
        self,
        key: SpecialKey | str,
        modifiers: Sequence[KeyModifier] | None = None,
    ) -> None:
        """Simulate a keystroke with optional modifier keys.

        Raises:
            AccessibilityPermissionError: If accessibility permission is denied.
            InjectionFailedError: If the keystroke cannot be sent.
        """
        # Resolve the virtual key code
        if isinstance(key, SpecialKey):
            key_code = _SPECIAL_KEY_CODES.get(key.value, 0)
        else:
            key_code = _LETTER_KEY_CODES.get(key.lower(), 0)

        # Calculate modifier flags
        flags = 0
        if modifiers:
            for mod in modifiers:
                mod_value = mod.value if isinstance(mod, KeyModifier) else str(mod)
                flags |= _MODIFIER_FLAGS.get(mod_value, 0)

        try:
            # Create and post key-down event
            event_down = CGEventCreateKeyboardEvent(None, key_code, True)
            if event_down is None:
                raise InjectionFailedError(
                    f"Failed to create key-down event for key code {key_code}"
                )
            if flags:
                CGEventSetFlags(event_down, flags)
            CGEventPost(kCGHIDEventTap, event_down)

            # Create and post key-up event
            event_up = CGEventCreateKeyboardEvent(None, key_code, False)
            if event_up is None:
                raise InjectionFailedError(f"Failed to create key-up event for key code {key_code}")
            if flags:
                CGEventSetFlags(event_up, flags)
            CGEventPost(kCGHIDEventTap, event_up)
        except (AccessibilityPermissionError, InjectionFailedError):
            raise
        except Exception as exc:
            if AXIsProcessTrusted is not None and not AXIsProcessTrusted():
                raise AccessibilityPermissionError(
                    "Accessibility permission not granted. Cannot send keystroke."
                ) from exc
            raise InjectionFailedError(f"Failed to send keystroke: {exc}") from exc

    def has_accessibility_permission(self) -> bool:
        """Check if the app has Accessibility permission."""
        return bool(AXIsProcessTrusted())

    def request_accessibility_permission(self) -> None:
        """Prompt the user to grant Accessibility permission."""
        options = {
            "AXTrustedCheckOptionPrompt": True,
        }
        AXIsProcessTrustedWithOptions(options)
