"""
MacOSHotkeyManager — macOS global hotkey using CGEventTap.

Uses a CGEventTap (from Quartz/CoreGraphics) to listen for keyboard
events at the session level and filter for the registered hotkey
combination.  The tap runs on a background thread with its own
CFRunLoop so the main (Qt) thread is never blocked.

Requires Accessibility (or Input Monitoring) permission.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from systemstt.errors import HotkeyRegistrationError

if TYPE_CHECKING:
    from collections.abc import Callable
from systemstt.platform.base import HotkeyBinding, HotkeyManager

logger = logging.getLogger(__name__)

# Import Quartz APIs — these are mocked in tests
try:
    from Quartz import (  # type: ignore[import-untyped]
        CFMachPortCreateRunLoopSource,
        CFMachPortInvalidate,
        CFRunLoopAddSource,
        CFRunLoopGetCurrent,
        CFRunLoopRun,
        CFRunLoopStop,
        CGEventGetFlags,
        CGEventGetIntegerValueField,
        CGEventMaskBit,
        CGEventTapCreate,
        CGEventTapEnable,
        kCFRunLoopCommonModes,
        kCGEventKeyDown,
        kCGHeadInsertEventTap,
        kCGKeyboardEventKeycode,
        kCGSessionEventTap,
    )

    _QUARTZ_AVAILABLE = True
except ImportError:
    _QUARTZ_AVAILABLE = False

# Virtual key code mapping (same codes used by both Carbon and CGEvent)
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

# CGEvent modifier flag mapping
_MODIFIER_FLAGS: dict[str, int] = {
    "command": 0x10_0000,   # kCGEventFlagMaskCommand
    "option": 0x8_0000,     # kCGEventFlagMaskAlternate
    "shift": 0x2_0000,      # kCGEventFlagMaskShift
    "control": 0x4_0000,    # kCGEventFlagMaskControl
}

# Mask of all modifier bits we care about (ignore caps lock, fn, etc.)
_ALL_MODIFIER_MASK = (
    _MODIFIER_FLAGS["command"]
    | _MODIFIER_FLAGS["option"]
    | _MODIFIER_FLAGS["shift"]
    | _MODIFIER_FLAGS["control"]
)

# Use listen-only so we observe but don't block events
_TAP_OPTION_LISTEN_ONLY = 0x00000001  # kCGEventTapOptionListenOnly


class MacOSHotkeyManager(HotkeyManager):
    """macOS implementation of HotkeyManager using a CGEventTap."""

    def __init__(self) -> None:
        self._binding: HotkeyBinding | None = None
        self._callback: Callable[[], None] | None = None
        self._target_key_code: int = 0
        self._target_modifier_mask: int = 0

        # CGEventTap resources (managed on the background thread)
        self._tap_ref: object = None
        self._run_loop_ref: object = None
        self._thread: threading.Thread | None = None
        self._thread_ready = threading.Event()

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def register(self, binding: HotkeyBinding, callback: Callable[[], None]) -> None:
        """Register a global hotkey.

        Raises HotkeyRegistrationError if the event tap cannot be created
        (typically because Accessibility permission is not granted).
        """
        try:
            # Tear down previous tap if any
            self._stop_tap()

            self._callback = callback
            self._target_key_code = _KEY_CODES.get(binding.key.lower(), 0)
            self._target_modifier_mask = 0
            for mod in binding.modifiers:
                self._target_modifier_mask |= _MODIFIER_FLAGS.get(mod, 0)

            self._start_tap()
            self._binding = binding
            logger.info("Registered hotkey: %s", binding.display_string())

        except HotkeyRegistrationError:
            raise
        except Exception as exc:
            raise HotkeyRegistrationError(
                f"Failed to register hotkey {binding.display_string()}: {exc}"
            ) from exc

    def unregister(self) -> None:
        """Unregister the current hotkey. Safe to call when not registered."""
        self._stop_tap()
        self._binding = None
        self._callback = None

    def update_binding(self, binding: HotkeyBinding) -> None:
        """Change the hotkey binding. Must be registered first."""
        if self._callback is None:
            raise HotkeyRegistrationError(
                "Cannot update binding: no hotkey is currently registered."
            )

        old_binding = self._binding
        saved_callback = self._callback

        try:
            self._stop_tap()

            self._callback = saved_callback
            self._target_key_code = _KEY_CODES.get(binding.key.lower(), 0)
            self._target_modifier_mask = 0
            for mod in binding.modifiers:
                self._target_modifier_mask |= _MODIFIER_FLAGS.get(mod, 0)

            self._start_tap()
            self._binding = binding
            logger.info("Updated hotkey to: %s", binding.display_string())

        except Exception as exc:
            self._binding = old_binding
            raise HotkeyRegistrationError(
                f"Failed to update hotkey to {binding.display_string()}: {exc}"
            ) from exc

    @property
    def is_registered(self) -> bool:
        return self._binding is not None

    @property
    def current_binding(self) -> HotkeyBinding | None:
        return self._binding

    # -----------------------------------------------------------------
    # CGEventTap internals
    # -----------------------------------------------------------------

    def _start_tap(self) -> None:
        """Create the CGEventTap and start the background CFRunLoop thread."""
        if not _QUARTZ_AVAILABLE:
            raise HotkeyRegistrationError("Quartz framework not available")

        # Create the event tap (listen-only for key-down events)
        mask = CGEventMaskBit(kCGEventKeyDown)
        tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            _TAP_OPTION_LISTEN_ONLY,
            mask,
            self._tap_callback,
            None,
        )
        if tap is None:
            raise HotkeyRegistrationError(
                "Failed to create CGEventTap. "
                "Grant Accessibility permission in System Settings > "
                "Privacy & Security > Accessibility."
            )

        self._tap_ref = tap
        CGEventTapEnable(tap, True)

        # Start background thread to run the CFRunLoop
        self._thread_ready.clear()
        self._thread = threading.Thread(
            target=self._run_loop_thread,
            args=(tap,),
            daemon=True,
            name="hotkey-cgeventtap",
        )
        self._thread.start()
        self._thread_ready.wait(timeout=2.0)

    def _stop_tap(self) -> None:
        """Tear down the event tap and stop the background thread."""
        if self._tap_ref is not None:
            try:
                CGEventTapEnable(self._tap_ref, False)
                CFMachPortInvalidate(self._tap_ref)
            except Exception:
                logger.debug("Error disabling event tap", exc_info=True)
            self._tap_ref = None

        if self._run_loop_ref is not None:
            try:
                CFRunLoopStop(self._run_loop_ref)
            except Exception:
                logger.debug("Error stopping run loop", exc_info=True)
            self._run_loop_ref = None

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run_loop_thread(self, tap: object) -> None:
        """Background thread: adds the tap source to a CFRunLoop and runs it."""
        try:
            source = CFMachPortCreateRunLoopSource(None, tap, 0)
            loop = CFRunLoopGetCurrent()
            CFRunLoopAddSource(loop, source, kCFRunLoopCommonModes)

            self._run_loop_ref = loop
            self._thread_ready.set()

            CFRunLoopRun()  # blocks until CFRunLoopStop is called
        except Exception:
            logger.error("CGEventTap run-loop thread error", exc_info=True)
        finally:
            self._thread_ready.set()  # unblock if we failed early

    def _tap_callback(
        self,
        proxy: object,
        event_type: int,
        event: object,
        refcon: object,
    ) -> object:
        """CGEventTap callback — called for every key-down event.

        Compares the event's key code and modifier flags against the
        registered binding. If they match, invokes the hotkey callback.

        Must return the event (or None to suppress, but we're listen-only).
        """
        try:
            key_code = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            flags = CGEventGetFlags(event) & _ALL_MODIFIER_MASK

            if key_code == self._target_key_code and flags == self._target_modifier_mask:
                self._on_hotkey_pressed()
        except Exception:
            logger.error("Error in hotkey tap callback", exc_info=True)

        return event

    def _on_hotkey_pressed(self) -> None:
        """Dispatch the hotkey callback."""
        if self._callback is not None:
            try:
                self._callback()
            except Exception:
                logger.error("Error in hotkey callback", exc_info=True)
