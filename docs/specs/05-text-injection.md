# 05 — Text Injection
**Version:** 1.0
**Date:** 2026-02-28
**Status:** Draft

---

## 1. Goal

Inject transcribed text into the currently focused application at the cursor position. Also provide keystroke simulation for voice command execution. This is the primary platform-specific component and the critical path for the user's dictation experience.

**MRD requirements:**
- FR-003: Text injection at cursor — "text appears at the cursor position in browsers, editors, terminals, and other standard macOS apps"
- FR-007: Voice commands (keystroke simulation for command execution)
- MRD Section 9: Accessibility API permissions required; handle gracefully if denied
- MRD Section 9: Test with common apps (browsers, VS Code, Terminal, Notes)

**Design spec references:**
- Section 8.2: First-launch accessibility permission prompt
- Section 13.1: Text injection via AXUIElement on macOS

---

## 2. Interface

### 2.1 TextInjector (Abstract Base Class)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class KeyModifier(Enum):
    """Keyboard modifier keys."""
    COMMAND = "command"      # macOS: Cmd, Windows: Ctrl (future)
    OPTION = "option"        # macOS: Option, Windows: Alt (future)
    SHIFT = "shift"
    CONTROL = "control"      # macOS: Ctrl key (distinct from Cmd)


class SpecialKey(Enum):
    """Non-character keys."""
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


class TextInjector(ABC):
    """
    Abstract interface for injecting text and keystrokes into the
    focused application.

    Platform-specific implementations handle the actual system API calls.
    """

    @abstractmethod
    async def inject_text(self, text: str) -> None:
        """
        Inject text at the current cursor position in the focused app.

        Args:
            text: The text to inject. May contain Unicode (Hebrew, emoji, etc.).

        Raises:
            AccessibilityPermissionError: If the app lacks accessibility permissions.
            InjectionFailedError: If text injection fails for any reason.
        """
        ...

    @abstractmethod
    async def send_keystroke(
        self,
        key: str | SpecialKey,
        modifiers: list[KeyModifier] | None = None,
    ) -> None:
        """
        Simulate a keystroke in the focused app.

        Args:
            key: A character key ("a", "z", etc.) or a SpecialKey.
            modifiers: Optional list of modifier keys to hold.

        Raises:
            AccessibilityPermissionError: If the app lacks accessibility permissions.
            InjectionFailedError: If keystroke simulation fails.
        """
        ...

    @abstractmethod
    def has_accessibility_permission(self) -> bool:
        """
        Check if the application has the required accessibility permissions.
        Returns True if granted, False otherwise.
        """
        ...

    @abstractmethod
    def request_accessibility_permission(self) -> None:
        """
        Open the system settings to the accessibility permission page.
        This is a best-effort action — the OS handles the actual UI.
        """
        ...
```

### 2.2 MacOSTextInjector

```python
class MacOSTextInjector(TextInjector):
    """
    macOS implementation of text injection using a hybrid approach:
    1. Primary: CGEventPost for keystroke simulation (reliable across all apps)
    2. Fallback: Accessibility API (AXUIElement) for direct text value setting
    3. Clipboard-based: As a last resort for apps that reject both methods

    Strategy selection is automatic based on what works for the focused app.
    """

    async def inject_text(self, text: str) -> None:
        """
        Inject text into the focused application.

        Implementation strategy (in order of preference):
        1. Simulate keystrokes via CGEventPost for each character
           - Most compatible, works with virtually all apps
           - Handles Unicode correctly via CGEventKeyboardSetUnicodeString
        2. If CGEvent fails: Use AXUIElement to get the focused element
           and set its AXValue
        3. If both fail: Copy text to clipboard, simulate Cmd+V, restore clipboard
        """
        ...

    async def send_keystroke(
        self,
        key: str | SpecialKey,
        modifiers: list[KeyModifier] | None = None,
    ) -> None:
        """
        Simulate a keystroke using CGEventPost.

        Creates a CGEvent with the appropriate key code and modifier flags,
        then posts it to the focused application.
        """
        ...

    def has_accessibility_permission(self) -> bool:
        """
        Check using AXIsProcessTrusted().
        """
        ...

    def request_accessibility_permission(self) -> None:
        """
        Opens System Settings > Privacy & Security > Accessibility
        using AXIsProcessTrustedWithOptions with prompt=True.
        """
        ...
```

---

## 3. Data Models

### 3.1 Key Code Mapping

The macOS implementation needs a mapping from character/key names to macOS virtual key codes:

| Key | Virtual Key Code | Notes |
|-----|-----------------|-------|
| Return | 0x24 | |
| Backspace | 0x33 | Delete backward |
| Delete | 0x75 | Delete forward |
| Tab | 0x30 | |
| Escape | 0x35 | |
| Left Arrow | 0x7B | |
| Right Arrow | 0x7C | |
| Up Arrow | 0x7E | |
| Down Arrow | 0x7D | |
| Space | 0x31 | |

Modifier flags:
| Modifier | CGEvent Flag |
|----------|-------------|
| Command | kCGEventFlagMaskCommand |
| Option | kCGEventFlagMaskAlternate |
| Shift | kCGEventFlagMaskShift |
| Control | kCGEventFlagMaskControl |

---

## 4. Dependencies

| Dependency | Usage |
|-----------|-------|
| PyObjC (pyobjc-framework-Quartz) | CGEventPost, CGEventCreateKeyboardEvent, CGEventKeyboardSetUnicodeString |
| PyObjC (pyobjc-framework-Cocoa) | AXUIElement APIs, AXIsProcessTrusted |

**Internal dependencies:**
- `systemstt.errors` — `AccessibilityPermissionError`, `InjectionFailedError`

---

## 5. Error Handling

| Error | Condition | Behavior |
|-------|-----------|----------|
| `AccessibilityPermissionError` | `AXIsProcessTrusted()` returns False | On first launch: show permission dialog. During dictation: pill error + stop dictation. |
| `InjectionFailedError` | CGEvent creation or posting fails, and all fallback strategies fail | Log the error with details of which strategies were attempted. Pill shows "Text injection failed". Dictation continues (text is lost for this chunk, but the session stays active). |

**Graceful degradation:**
1. If CGEvent keystroke simulation fails for a character, try AXUIElement.
2. If AXUIElement fails, try clipboard-paste.
3. If all fail, raise `InjectionFailedError` with context about which methods were tried.

---

## 6. Notes for Developer

### 6.1 CGEvent-Based Text Injection (Primary Method)

This is the most reliable method for injecting text across macOS apps:

```python
# Conceptual PyObjC usage
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventKeyboardSetUnicodeString,
    CGEventPost,
    kCGHIDEventTap,
    kCGEventFlagMaskCommand,
)

def inject_unicode_string(text: str) -> None:
    """Inject a string by simulating keyboard events with Unicode."""
    for char in text:
        # Create a keydown event (key code 0 is fine for Unicode injection)
        event_down = CGEventCreateKeyboardEvent(None, 0, True)
        event_up = CGEventCreateKeyboardEvent(None, 0, False)

        # Set the Unicode string on the event
        CGEventKeyboardSetUnicodeString(event_down, len(char), char)
        CGEventKeyboardSetUnicodeString(event_up, len(char), char)

        # Post events
        CGEventPost(kCGHIDEventTap, event_down)
        CGEventPost(kCGHIDEventTap, event_up)
```

**Why CGEvent over AXUIElement for primary injection:**
- CGEvent works with ALL apps, including those that don't expose AXUIElement text fields (e.g., some Electron apps, games, terminal emulators).
- AXUIElement requires finding the focused element and setting its value, which is fragile across different app architectures.
- CGEvent supports full Unicode including Hebrew characters via `CGEventKeyboardSetUnicodeString`.

### 6.2 AXUIElement Fallback

```python
# Conceptual — for cases where CGEvent doesn't work
from ApplicationServices import (
    AXUIElementCreateSystemWide,
    AXUIElementCopyAttributeValue,
    AXUIElementSetAttributeValue,
)

def inject_via_accessibility(text: str) -> None:
    system_wide = AXUIElementCreateSystemWide()
    # Get focused element
    err, focused = AXUIElementCopyAttributeValue(
        system_wide, "AXFocusedUIElement"
    )
    # Get current value and cursor position
    err, current_value = AXUIElementCopyAttributeValue(focused, "AXValue")
    err, selected_range = AXUIElementCopyAttributeValue(
        focused, "AXSelectedTextRange"
    )
    # Insert text at cursor position
    # ... (manipulate string, set AXValue, update AXSelectedTextRange)
```

### 6.3 Clipboard-Based Fallback

As a last resort:
1. Save the current clipboard contents.
2. Set the clipboard to the text to inject.
3. Simulate `Cmd+V` (paste).
4. Restore the original clipboard contents (after a brief delay).

This is the least elegant method but works in virtually all apps. The delay before restoring the clipboard must account for the paste operation completing.

### 6.4 Hebrew Text (RTL) Considerations

- Hebrew text injection via CGEvent works correctly — the OS handles RTL rendering.
- Mixed Hebrew/English text: inject the full string as-is. The OS's Unicode BiDi algorithm handles rendering direction in the target app.
- No special handling is needed for RTL in the text injector. The complexity is in the target app's text rendering, which is outside our control.

### 6.5 Injection Speed and Pacing

Injecting characters one at a time via CGEvent is fast but may need pacing:
- For short text (< 50 chars): inject all at once with no delay.
- For longer text: batch characters and add a small delay (1-2ms) between batches to avoid overwhelming apps that process keystrokes slowly.
- Alternative for long text: use the clipboard-paste approach, which injects the entire string at once regardless of length.

**Recommended default:** Use CGEvent character-by-character for text up to 100 characters. Use clipboard-paste for longer text. Make the threshold configurable.

### 6.6 Thread Safety

- `inject_text()` and `send_keystroke()` are `async` but the actual CGEvent calls are synchronous and fast.
- These methods MUST be called from the main thread (CGEvent requires the main run loop).
- The App Core receives transcription results on the main thread (via Qt signals) and calls the injector from there.

### 6.7 Accessibility Permission Check

Call `has_accessibility_permission()` at app startup. If it returns False:
1. Show the first-launch permission dialog (per design spec section 8.2).
2. After the user grants permission and returns to the app, re-check.
3. If still not granted, the app remains functional (menu bar, settings) but dictation is disabled with a clear message.

The permission check uses `AXIsProcessTrusted()` which returns a boolean. During development, the app must be re-added to the Accessibility list each time it is rebuilt.

### 6.8 Testing

- **Mock CGEvent calls:** Create a mock layer over `Quartz.CGEventCreateKeyboardEvent` and `CGEventPost`. Verify that inject_text produces the expected sequence of keydown/keyup events with correct Unicode strings.
- **Mock AXUIElement calls:** Similarly mock the Accessibility API calls.
- **Permission check:** Mock `AXIsProcessTrusted()` to test both granted and denied states.
- **Manual testing:** Test with the specific apps mentioned in the MRD: Safari/Chrome (browser), VS Code (editor), Terminal, Notes. Verify Hebrew text, mixed text, and all voice command keystrokes.
