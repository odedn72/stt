# 06 — Hotkey Manager and Application Lifecycle
**Version:** 1.0
**Date:** 2026-02-28
**Status:** Draft

---

## 1. Goal

Register a global keyboard shortcut that toggles dictation from any application. Manage the application lifecycle including startup, shutdown, the dictation state machine, and login item registration.

**MRD requirements:**
- FR-001: Global keyboard shortcut — configurable system-wide hotkey to start/stop dictation
- FR-009: Persistent settings (hotkey configuration saved between sessions)
- FR-010: macOS support
- NFR-004: CPU usage during idle < 1%
- NFR-005: Application stability — no crashes, graceful error handling

**Design spec references:**
- Section 9: Keyboard shortcuts (default `Option+Space`, configurable)
- Section 10: Dock behavior (hidden by default, toggleable)
- Section 14: State machine (IDLE <-> ACTIVE with sub-states)

---

## 2. Interface

### 2.1 HotkeyManager (Abstract Base Class)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from collections.abc import Callable


@dataclass(frozen=True)
class HotkeyBinding:
    """A keyboard shortcut binding."""
    key: str                            # Key name ("space", "a", "f1", etc.)
    modifiers: frozenset[str]           # Modifier names ("option", "command", "shift", "control")

    def display_string(self) -> str:
        """Human-readable shortcut string, e.g., '⌥Space'."""
        ...

    @classmethod
    def from_display_string(cls, s: str) -> "HotkeyBinding":
        """Parse a display string back to a HotkeyBinding."""
        ...


# Default hotkey: Option+Space
DEFAULT_HOTKEY = HotkeyBinding(key="space", modifiers=frozenset({"option"}))


class HotkeyManager(ABC):
    """
    Abstract interface for global hotkey registration.

    The hotkey works system-wide — it fires regardless of which
    application is focused.
    """

    @abstractmethod
    def register(
        self,
        binding: HotkeyBinding,
        callback: Callable[[], None],
    ) -> None:
        """
        Register a global hotkey.

        Args:
            binding: The key combination to listen for.
            callback: Function to call when the hotkey is pressed.
                     Called on the main thread.

        Raises:
            HotkeyRegistrationError: If the hotkey cannot be registered
                                     (e.g., already in use by another app).
        """
        ...

    @abstractmethod
    def unregister(self) -> None:
        """
        Unregister the current hotkey. Safe to call when no hotkey is registered.
        """
        ...

    @abstractmethod
    def update_binding(self, binding: HotkeyBinding) -> None:
        """
        Change the hotkey binding. Unregisters the old binding and
        registers the new one.

        Raises:
            HotkeyRegistrationError: If the new binding cannot be registered.
        """
        ...

    @property
    @abstractmethod
    def current_binding(self) -> HotkeyBinding | None:
        """Return the currently registered binding, or None."""
        ...

    @property
    @abstractmethod
    def is_registered(self) -> bool:
        """Whether a hotkey is currently registered."""
        ...
```

### 2.2 MacOSHotkeyManager

```python
class MacOSHotkeyManager(HotkeyManager):
    """
    macOS global hotkey using Carbon RegisterEventHotKey via PyObjC.

    Note: Carbon hotkey APIs are deprecated but remain the most reliable
    method for global hotkeys on macOS. There is no modern replacement
    that works from Python. CGEvent taps are an alternative but require
    accessibility permissions.
    """

    def register(
        self,
        binding: HotkeyBinding,
        callback: Callable[[], None],
    ) -> None:
        """
        Register using Carbon RegisterEventHotKey.

        Maps the HotkeyBinding to a Carbon virtual key code and modifier mask,
        then installs a Carbon event handler.
        """
        ...

    # ... implements all HotkeyManager abstract methods ...
```

### 2.3 DictationStateMachine

```python
from enum import Enum, auto
from dataclasses import dataclass
from typing import Any


class DictationState(Enum):
    IDLE = auto()
    STARTING = auto()       # Transitioning to active (initializing audio, engine)
    ACTIVE = auto()         # Actively recording and transcribing
    STOPPING = auto()       # Transitioning to idle (flushing buffers)
    ERROR = auto()          # Error occurred; may auto-recover or need user action


@dataclass(frozen=True)
class StateTransition:
    """Record of a state transition."""
    from_state: DictationState
    to_state: DictationState
    trigger: str                # What caused the transition
    error: Exception | None = None  # Attached error, if transitioning to ERROR


class DictationStateMachine:
    """
    Manages the dictation state and validates transitions.

    Valid transitions:
        IDLE -> STARTING        (hotkey pressed)
        STARTING -> ACTIVE      (audio + engine ready)
        STARTING -> ERROR       (initialization failed)
        ACTIVE -> STOPPING      (hotkey pressed, or "stop dictation" command)
        ACTIVE -> ERROR         (runtime error: mic disconnected, API failure)
        STOPPING -> IDLE        (buffers flushed, cleanup complete)
        ERROR -> IDLE           (user acknowledged error, or auto-recovered)
        ERROR -> STARTING       (retry)
    """

    def __init__(self) -> None: ...

    @property
    def state(self) -> DictationState:
        """Current state."""
        ...

    @property
    def on_state_changed(self) -> Callable[[StateTransition], None] | None:
        """Callback invoked on every state change."""
        ...

    @on_state_changed.setter
    def on_state_changed(self, callback: Callable[[StateTransition], None] | None) -> None: ...

    def transition_to(self, new_state: DictationState, trigger: str, error: Exception | None = None) -> None:
        """
        Attempt a state transition.

        Args:
            new_state: The target state.
            trigger: Description of what caused the transition.
            error: Attached error for ERROR transitions.

        Raises:
            ValueError: If the transition is not valid from the current state.
        """
        ...

    def can_transition_to(self, new_state: DictationState) -> bool:
        """Check if a transition to the given state is valid from the current state."""
        ...
```

### 2.4 AppLifecycle

```python
class AppLifecycle:
    """
    Manages application-level lifecycle events:
    - Startup initialization
    - Login item registration (Start on Login)
    - Dock visibility (Show in Dock)
    - Graceful shutdown
    """

    def __init__(self, settings: "SettingsModel") -> None: ...

    def set_login_item(self, enabled: bool) -> None:
        """
        Add or remove the app from macOS login items.
        Uses SMAppService (macOS 13+) or LSSharedFileListInsertItemURL (older).
        """
        ...

    def set_dock_visibility(self, visible: bool) -> None:
        """
        Show or hide the dock icon.
        Manipulates NSApp.setActivationPolicy() between
        .regular (visible) and .accessory (hidden).
        """
        ...

    async def startup(self) -> None:
        """
        Full startup sequence:
        1. Load configuration
        2. Check accessibility permissions
        3. Initialize platform services (hotkey, text injector)
        4. Initialize the default STT engine (but don't load model yet)
        5. Register the global hotkey
        6. Set dock visibility from settings
        7. Show the menu bar icon
        """
        ...

    async def shutdown(self) -> None:
        """
        Graceful shutdown:
        1. Stop dictation if active
        2. Unregister hotkey
        3. Save settings
        4. Shut down STT engine (unload model)
        5. Exit the Qt event loop
        """
        ...
```

---

## 3. Data Models

### 3.1 HotkeyBinding

| Field | Type | Description |
|-------|------|-------------|
| key | str | The key name (lowercase). Values: "space", "a"-"z", "0"-"9", "f1"-"f12" |
| modifiers | frozenset[str] | Set of modifier names. Values: "option", "command", "shift", "control" |

### 3.2 Hotkey Display Mapping

| Modifier | macOS Symbol | Display |
|----------|-------------|---------|
| command | Cmd | `⌘` |
| option | Option | `⌥` |
| shift | Shift | `⇧` |
| control | Control | `⌃` |

Example: `HotkeyBinding(key="space", modifiers=frozenset({"option"}))` displays as `⌥Space`.

### 3.3 State Transition Table

| From | To | Trigger | Notes |
|------|----|---------|-------|
| IDLE | STARTING | Hotkey pressed | Begin initialization |
| STARTING | ACTIVE | Init complete | Audio capture + engine ready |
| STARTING | ERROR | Init failed | Show error in pill/notification |
| ACTIVE | STOPPING | Hotkey pressed / "stop dictation" | Begin teardown |
| ACTIVE | ERROR | Runtime error | Mic disconnected, API failure, etc. |
| STOPPING | IDLE | Teardown complete | All buffers flushed |
| ERROR | IDLE | Auto-recovery / user dismiss | Error resolved |
| ERROR | STARTING | Retry | User retried or auto-retry |

---

## 4. Dependencies

| Dependency | Usage |
|-----------|-------|
| PyObjC (pyobjc-framework-Cocoa) | Carbon hotkey APIs, NSApp activation policy, login items |
| PyObjC (pyobjc-framework-Quartz) | CGEvent for alternative hotkey approach |

**Internal dependencies:**
- `systemstt.config.models` — `SettingsModel` for hotkey binding and startup preferences
- `systemstt.errors` — `HotkeyRegistrationError`
- `systemstt.audio.recorder` — `AudioRecorder` (started/stopped by state machine)
- `systemstt.stt.base` — `EngineManager` (activated/deactivated by state machine)

---

## 5. Error Handling

| Error | Condition | Behavior |
|-------|-----------|----------|
| `HotkeyRegistrationError` | Hotkey conflicts with another app or is invalid | Show notification: "Could not register hotkey ⌥Space. It may be in use by another app. Change it in Settings." Fall back to no hotkey; user can still toggle dictation from the dropdown menu. |
| Initialization failure (STARTING -> ERROR) | Audio device not found, engine not available | Pill/notification shows the specific error. State machine transitions to ERROR. User can retry from the dropdown menu. |
| Runtime error (ACTIVE -> ERROR) | Mic disconnected, API timeout after retries | Pill shows inline error. Dictation pauses. Auto-retry for transient errors (API timeout). Permanent errors (mic disconnected) require user action. |

---

## 6. Notes for Developer

### 6.1 Carbon Hotkey Registration

```python
# Conceptual PyObjC usage for Carbon global hotkeys
from Carbon import CarbonEvt
import objc

# Key code mapping
KEY_CODES = {
    "space": 49,
    "a": 0, "b": 11, "c": 8,
    # ... full mapping needed
}

# Modifier mapping
MODIFIER_FLAGS = {
    "command": 0x0100,   # cmdKey
    "option": 0x0800,    # optionKey
    "shift": 0x0200,     # shiftKey
    "control": 0x1000,   # controlKey
}

def register_hotkey(key_code: int, modifiers: int, handler_callback):
    """
    Register a global hotkey using Carbon.

    1. Create a EventHotKeyID
    2. Call RegisterEventHotKey
    3. Install a Carbon event handler for kEventHotKeyPressed
    """
    ...
```

**Important:** Carbon hotkey APIs are deprecated since macOS 10.15 but continue to work through at least macOS 15. They remain the standard approach for Python-based global hotkeys on macOS. If they are removed in a future macOS version, the fallback is to use CGEvent taps (which require accessibility permissions).

### 6.2 Alternative: CGEvent Tap for Hotkey

An alternative to Carbon hotkeys that requires accessibility permissions:

```python
# CGEvent tap intercepts all keyboard events system-wide
from Quartz import (
    CGEventTapCreate,
    kCGSessionEventTap,
    kCGHeadInsertEventTap,
    kCGEventKeyDown,
    CGEventGetIntegerValueField,
    kCGKeyboardEventKeycode,
    CGEventGetFlags,
)
```

This approach can be used as a fallback if Carbon APIs are ever removed. It requires accessibility permissions, which the app already requests for text injection.

### 6.3 Dock Visibility

```python
from AppKit import NSApp, NSApplicationActivationPolicyRegular, NSApplicationActivationPolicyAccessory

def set_dock_visible(visible: bool) -> None:
    if visible:
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    else:
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
```

**Note:** Changing activation policy at runtime works but may briefly show/hide the dock icon with a bounce animation. This is acceptable for a settings toggle.

### 6.4 Login Item Registration

For macOS 13+, use `SMAppService`:
```python
# Conceptual
from ServiceManagement import SMAppService

service = SMAppService.mainApp()
if enable:
    service.register()
else:
    service.unregister()
```

For older macOS versions (if support is needed), use `LSSharedFileListInsertItemURL`. For v1, targeting macOS 13+ is acceptable.

### 6.5 State Machine Integration with App Core

The `DictationStateMachine` is owned by the App Core (`app.py`). The App Core listens to state changes and coordinates all other components:

```python
# In App Core (conceptual)
class AppCore:
    def __init__(self):
        self.state_machine = DictationStateMachine()
        self.state_machine.on_state_changed = self._handle_state_change

    def _handle_state_change(self, transition: StateTransition) -> None:
        match transition.to_state:
            case DictationState.STARTING:
                self._begin_dictation()
            case DictationState.ACTIVE:
                self._ui.show_active_state()
            case DictationState.STOPPING:
                self._end_dictation()
            case DictationState.IDLE:
                self._ui.show_idle_state()
            case DictationState.ERROR:
                self._handle_error(transition.error)

    def on_hotkey_pressed(self) -> None:
        if self.state_machine.state == DictationState.IDLE:
            self.state_machine.transition_to(DictationState.STARTING, "hotkey")
        elif self.state_machine.state == DictationState.ACTIVE:
            self.state_machine.transition_to(DictationState.STOPPING, "hotkey")
```

### 6.6 Startup Sequence Timing

The startup sequence should be fast. Target: app visible in menu bar within 1 second of launch.

1. Load config from disk (fast, < 50ms)
2. Create Qt application and show menu bar icon (fast, < 100ms)
3. Check accessibility permissions (fast, < 10ms)
4. Register hotkey (fast, < 10ms)
5. Initialize STT engine in background (slow for local model — can take seconds)
   - The engine initializes lazily: it is not loaded until the first dictation session starts.
   - This avoids blocking startup and respects NFR-004 (negligible idle CPU).

### 6.7 Graceful Shutdown

On `Cmd+Q` or system shutdown:
1. If dictation is active, flush the current audio buffer and wait for the final transcription (with a 2-second timeout).
2. Unregister the hotkey.
3. Save any pending settings changes.
4. Shut down the STT engine (unload model to free memory).
5. Exit the process.

### 6.8 Testing

- **State machine tests:** Test all valid transitions and verify invalid transitions raise ValueError. Test that callbacks are invoked correctly.
- **HotkeyManager tests:** Mock Carbon/CGEvent APIs. Test registration, unregistration, binding changes. Test handling of registration failures.
- **AppLifecycle tests:** Mock all platform calls. Test the startup sequence, shutdown sequence, dock visibility toggle, login item toggle.
- **Integration:** With a real hotkey registered, press it and verify the callback fires. (This requires the app to actually be running — suitable for manual testing.)
