"""
Abstract interfaces for all platform-specific services.

These ABCs define the contracts that macOS (v1) and Windows (v2)
implementations must fulfill. All business logic depends only on
these interfaces, never on concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence


# ---------------------------------------------------------------------------
# Key enums (shared by all platforms)
# ---------------------------------------------------------------------------

class KeyModifier(str, Enum):
    """Keyboard modifier keys."""

    COMMAND = "command"
    OPTION = "option"
    SHIFT = "shift"
    CONTROL = "control"


class SpecialKey(str, Enum):
    """Special (non-character) keys."""

    RETURN = "return"
    BACKSPACE = "backspace"
    DELETE = "delete"
    TAB = "tab"
    ESCAPE = "escape"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    HOME = "home"
    END = "end"


# ---------------------------------------------------------------------------
# HotkeyBinding — data model for a keyboard shortcut
# ---------------------------------------------------------------------------

# macOS symbol mappings for display (module-level to avoid frozen dataclass issues)
_MODIFIER_SYMBOLS: dict[str, str] = {
    "command": "\u2318",
    "option": "\u2325",
    "shift": "\u21e7",
    "control": "\u2303",
}

_KEY_SYMBOLS: dict[str, str] = {
    "space": "Space",
    "return": "\u21a9",
    "backspace": "\u232b",
    "delete": "\u2326",
    "tab": "\u21e5",
    "escape": "\u238b",
    "left": "\u2190",
    "right": "\u2192",
    "up": "\u2191",
    "down": "\u2193",
}


@dataclass(frozen=True)
class HotkeyBinding:
    """Represents a keyboard shortcut binding."""

    key: str
    modifiers: frozenset[str]

    def display_string(self) -> str:
        """Return a human-readable display string (e.g., '\u2325Space')."""
        # Sort modifiers in standard macOS order: control, option, shift, command
        mod_order = ["control", "option", "shift", "command"]
        sorted_mods = sorted(
            self.modifiers,
            key=lambda m: mod_order.index(m) if m in mod_order else 99,
        )
        symbols = [_MODIFIER_SYMBOLS.get(m, m) for m in sorted_mods]
        key_display = _KEY_SYMBOLS.get(self.key, self.key.upper())
        return "".join(symbols) + key_display

    @classmethod
    def from_display_string(cls, display: str) -> HotkeyBinding:
        """Parse a display string back to a HotkeyBinding."""
        # Reverse lookup for modifier symbols
        symbol_to_mod = {v: k for k, v in _MODIFIER_SYMBOLS.items()}
        # Reverse lookup for key symbols
        symbol_to_key = {v: k for k, v in _KEY_SYMBOLS.items()}

        modifiers: set[str] = set()
        remaining = display

        # Extract modifier symbols from the beginning
        while remaining:
            found = False
            for symbol, mod in symbol_to_mod.items():
                if remaining.startswith(symbol):
                    modifiers.add(mod)
                    remaining = remaining[len(symbol):]
                    found = True
                    break
            if not found:
                break

        # Remaining is the key
        key = symbol_to_key.get(remaining, remaining.lower())

        return cls(key=key, modifiers=frozenset(modifiers))


# Default hotkey binding: Option+Space
DEFAULT_HOTKEY = HotkeyBinding(key="space", modifiers=frozenset({"option"}))


# ---------------------------------------------------------------------------
# TextInjector ABC
# ---------------------------------------------------------------------------

class TextInjector(ABC):
    """Abstract interface for injecting text into the focused application."""

    @abstractmethod
    async def inject_text(self, text: str) -> None:
        """Inject text at the cursor position in the focused application."""
        ...

    @abstractmethod
    async def send_keystroke(
        self,
        key: SpecialKey | str,
        modifiers: Sequence[KeyModifier] | None = None,
    ) -> None:
        """Simulate a keystroke, optionally with modifier keys."""
        ...

    @abstractmethod
    def has_accessibility_permission(self) -> bool:
        """Check if the app has Accessibility permission."""
        ...

    @abstractmethod
    def request_accessibility_permission(self) -> None:
        """Prompt the user to grant Accessibility permission."""
        ...


# ---------------------------------------------------------------------------
# HotkeyManager ABC
# ---------------------------------------------------------------------------

class HotkeyManager(ABC):
    """Abstract interface for global hotkey registration."""

    @abstractmethod
    def register(self, binding: HotkeyBinding, callback: Callable[[], None]) -> None:
        """Register a global hotkey with the given binding and callback."""
        ...

    @abstractmethod
    def unregister(self) -> None:
        """Unregister the current hotkey."""
        ...

    @abstractmethod
    def update_binding(self, binding: HotkeyBinding) -> None:
        """Change the hotkey binding. Must be registered first."""
        ...

    @property
    @abstractmethod
    def is_registered(self) -> bool:
        """Return True if a hotkey is currently registered."""
        ...

    @property
    @abstractmethod
    def current_binding(self) -> HotkeyBinding | None:
        """Return the current hotkey binding, or None if not registered."""
        ...
