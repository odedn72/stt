# 07 — UI Layer
**Version:** 1.0
**Date:** 2026-02-28
**Status:** Draft

---

## 1. Goal

Implement all visual components of SystemSTT using PySide6 (Qt 6): the menu bar icon with language label, the custom dropdown menu, the floating status pill, and the tabbed settings window. All visuals must match the design spec exactly (colors, typography, spacing, animations).

**MRD requirements:**
- FR-001: Global hotkey indicator (menu bar shows state)
- FR-008: Configurable STT engine (settings UI)
- FR-009: Persistent settings (settings UI + save/load)
- FR-011: Configurable model size (settings UI)
- FR-012: Visual dictation indicator (menu bar + floating pill)
- FR-013: Audio input device selection (settings UI)

**Design spec references:** Sections 2-15 (this spec covers the entire design spec).

---

## 2. Interface

### 2.1 Theme (Design Tokens)

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class DesignTokens:
    """
    All design tokens from the design spec, section 2.
    These are the single source of truth for colors, sizes, and typography.
    """
    # Colors
    bg_solid: str = "#1A1A2E"
    bg_translucent: str = "rgba(26, 26, 46, 178)"  # 70% opacity
    bg_elevated: str = "#252540"
    bg_hover: str = "#2E2E4A"
    bg_active: str = "#3A3A5C"
    text_primary: str = "#F0F0F5"
    text_secondary: str = "#9999B0"
    text_disabled: str = "#55556A"
    accent: str = "#8B5CF6"
    accent_hover: str = "#7C4FE0"
    accent_glow: str = "rgba(139, 92, 246, 102)"  # 40% opacity
    error: str = "#EF4444"
    error_bg: str = "rgba(239, 68, 68, 38)"  # 15% opacity
    warning: str = "#F59E0B"
    success: str = "#10B981"
    border: str = "#2E2E4A"

    # Typography sizes (px)
    text_xs: int = 10
    text_sm: int = 12
    text_base: int = 13
    text_md: int = 14
    text_lg: int = 16
    text_xl: int = 20

    # Backdrop blur
    blur_radius: int = 20

    # Shared dimensions
    border_radius_sm: int = 6
    border_radius_md: int = 10
    border_radius_lg: int = 12
    border_radius_pill: int = 18


TOKENS = DesignTokens()


def generate_qss() -> str:
    """
    Generate the complete Qt Style Sheet from design tokens.
    Returns a QSS string that should be applied to the QApplication.
    """
    ...
```

### 2.2 MenuBarWidget

```python
from PySide6.QtWidgets import QSystemTrayIcon
from PySide6.QtCore import Signal


class MenuBarWidget:
    """
    Menu bar integration: icon + language label.

    Uses QSystemTrayIcon as the base for cross-platform compatibility,
    but with a custom icon that includes the language label rendered
    into the icon image itself (since QSystemTrayIcon doesn't support
    text labels natively).

    Design spec reference: Section 4.
    """

    # Signals
    dictation_toggle_requested = Signal()
    preview_toggle_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: "QApplication") -> None: ...

    def set_state_idle(self, language: str = "EN") -> None:
        """
        Set menu bar to idle state.
        Icon: outlined mic, dimmed. Language label: dimmed.
        """
        ...

    def set_state_active(self, language: str = "EN") -> None:
        """
        Set menu bar to active state.
        Icon: filled mic, accent color. Language label: bright.
        """
        ...

    def set_state_error(self, language: str = "EN") -> None:
        """
        Set menu bar to error state.
        Icon: warning triangle, warning color. Reverts after 5 seconds.
        """
        ...

    def update_language(self, language: str) -> None:
        """Update the language label (e.g., "EN" -> "HE") in real time."""
        ...

    def update_dropdown_status(
        self,
        is_active: bool,
        language: str,
        engine: str,
        is_preview_on: bool,
    ) -> None:
        """Update dynamic content in the dropdown menu."""
        ...
```

### 2.3 DropdownMenu

```python
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


class DropdownMenu(QWidget):
    """
    Custom-drawn dropdown menu matching design spec section 4.3.

    This is NOT a native QMenu — it is a custom frameless QWidget with
    translucent background, backdrop blur, and custom styling.

    Properties:
    - Width: 240px
    - Background: translucent with 20px backdrop blur
    - Corner radius: 10px
    - Shadow: 0 8px 32px rgba(0,0,0,0.4)
    """

    # Signals
    start_stop_clicked = Signal()
    show_hide_preview_clicked = Signal()
    settings_clicked = Signal()
    quit_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None: ...

    def update_state(
        self,
        is_active: bool,
        language: str,
        engine: str,
        is_preview_on: bool,
    ) -> None:
        """Update all dynamic content based on current app state."""
        ...

    def show_at(self, x: int, y: int) -> None:
        """Show the dropdown at a specific screen position (below the menu bar icon)."""
        ...
```

### 2.4 FloatingPill

```python
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, QPoint, QPropertyAnimation


class FloatingPill(QWidget):
    """
    Floating status pill shown during active dictation.

    Design spec reference: Section 5.

    Features:
    - Translucent background with backdrop blur
    - Pulsing recording dot (accent color)
    - Language label, engine indicator, elapsed time
    - Expandable: live transcription preview, error messages, command confirmations
    - Draggable to any screen position, position remembered
    - Appear/disappear animations
    """

    position_changed = Signal(int, int)  # x, y — for saving to settings

    def __init__(self, parent: QWidget | None = None) -> None: ...

    def show_active(
        self,
        language: str = "EN",
        engine: str = "Cloud",
    ) -> None:
        """Show the pill with active dictation state. Animates in."""
        ...

    def hide_pill(self) -> None:
        """Hide the pill. Animates out."""
        ...

    def update_language(self, language: str) -> None:
        """Update the language label in real time."""
        ...

    def update_elapsed_time(self, seconds: int) -> None:
        """Update the elapsed time display (e.g., "0:12")."""
        ...

    def show_preview_text(self, text: str) -> None:
        """
        Show or update the live transcription preview area.
        Text direction (LTR/RTL) is auto-detected.
        """
        ...

    def hide_preview(self) -> None:
        """Hide the transcription preview area."""
        ...

    def show_error(self, message: str, is_warning: bool = False) -> None:
        """
        Show an inline error/warning in the expansion area.
        Dot changes to error/warning color.
        """
        ...

    def show_command_confirmation(self, message: str) -> None:
        """
        Show a voice command confirmation (e.g., "Deleted last word").
        Auto-dismisses after 2 seconds.
        """
        ...

    def clear_expansion(self) -> None:
        """Collapse the expansion area, returning to the compact pill."""
        ...

    def set_position(self, x: int, y: int) -> None:
        """Set the pill position on screen."""
        ...

    def reset_position(self) -> None:
        """Reset to default position: top-center, 48px below menu bar."""
        ...
```

### 2.5 SettingsWindow

```python
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


class SettingsWindow(QWidget):
    """
    Tabbed settings window matching design spec section 6.

    Properties:
    - Fixed size: 480x420px
    - Custom title bar (no native decorations)
    - Four tabs: General, Engine, Audio, Commands
    - Background: solid dark (#1A1A2E)
    - Centered on screen when opened
    """

    # Signals emitted when settings change
    settings_changed = Signal(str, object)  # (setting_key, new_value)
    hotkey_changed = Signal(object)         # HotkeyBinding
    engine_changed = Signal(str)            # "cloud_api" or "local_whisper"
    api_key_changed = Signal(str)           # New API key
    model_download_requested = Signal(str)  # Model size to download

    def __init__(self, settings: "SettingsModel", parent: QWidget | None = None) -> None: ...

    def show_tab(self, tab_name: str) -> None:
        """Show a specific tab ("general", "engine", "audio", "commands")."""
        ...

    def update_from_settings(self, settings: "SettingsModel") -> None:
        """Refresh all controls from the settings model."""
        ...

    def update_api_status(self, status: str) -> None:
        """Update the API status indicator ("Connected", "Invalid key", "Unreachable")."""
        ...

    def update_model_status(self, status: str) -> None:
        """Update the model status indicator ("Loaded (medium)", "Not downloaded")."""
        ...

    def update_model_download_progress(self, progress: float) -> None:
        """Update the model download progress bar (0.0 to 1.0)."""
        ...

    def update_audio_devices(self, devices: list["AudioDevice"]) -> None:
        """Refresh the audio device dropdown list."""
        ...

    def update_audio_level(self, level: "LevelReading") -> None:
        """Update the live audio level meter."""
        ...
```

---

## 3. Data Models

### 3.1 UI State (Observable)

The UI observes a shared state object that the App Core updates. The UI never modifies this state directly — it only reads it and emits signals when the user interacts with controls.

```python
from dataclasses import dataclass, field
from PySide6.QtCore import QObject, Signal


class UIState(QObject):
    """
    Observable UI state. Updated by the App Core.
    UI components connect to signals and update when state changes.
    """

    # Signals
    dictation_state_changed = Signal(str)    # "idle", "active", "error"
    language_changed = Signal(str)           # "EN", "HE"
    engine_changed = Signal(str)             # "Cloud", "Local"
    elapsed_time_changed = Signal(int)       # seconds
    preview_text_changed = Signal(str)
    error_changed = Signal(str)              # error message or empty
    command_confirmed = Signal(str)          # confirmation text

    def __init__(self) -> None:
        super().__init__()
        self.dictation_state: str = "idle"
        self.language: str = "EN"
        self.engine: str = "Cloud"
        self.elapsed_seconds: int = 0
        self.preview_text: str = ""
        self.error_message: str = ""
        self.is_preview_visible: bool = False
```

---

## 4. Dependencies

| Dependency | Usage |
|-----------|-------|
| PySide6 | All widgets, signals/slots, QSS styling, system tray |

**Internal dependencies:**
- `systemstt.config.models` — `SettingsModel` for populating settings controls
- `systemstt.audio.devices` — `AudioDevice` for device dropdown
- `systemstt.audio.level_meter` — `LevelReading` for level meter display
- `systemstt.ui.theme` — `DesignTokens`, `generate_qss()` for styling

---

## 5. Error Handling

| Scenario | UI Behavior |
|----------|-------------|
| Dictation error during active state | Pill: expansion with error message, dot changes color |
| API key missing when starting dictation | Pill: "No API key configured. Open Settings?" |
| Model not downloaded | Settings: "Not downloaded" status, Download button enabled |
| Audio device disconnected | Pill: "Microphone disconnected" (during dictation) |
| Hotkey registration failed | Notification: "Could not register hotkey" |

The UI layer does NOT handle errors itself — it only displays what the App Core tells it via the UIState. Error recovery decisions are made by the App Core.

---

## 6. Notes for Developer

### 6.1 Menu Bar Implementation

PySide6's `QSystemTrayIcon` provides basic system tray functionality but has limitations:
- No native support for text labels next to the icon.
- The icon is a single image (no separate text rendering).

**Approach:** Render the icon + language label into a single `QImage` and set it as the tray icon. When the language changes, re-render the image and update the icon.

```python
from PySide6.QtGui import QImage, QPainter, QFont, QColor, QPixmap
from PySide6.QtWidgets import QSystemTrayIcon

def create_menu_bar_icon(
    mic_icon: QPixmap,
    language: str,
    is_active: bool,
    is_error: bool,
) -> QPixmap:
    """
    Render the menu bar icon: mic icon + language label as a single image.

    For macOS retina, render at 2x and set devicePixelRatio.
    """
    ...
```

For the dropdown, DO NOT use `QSystemTrayIcon.setContextMenu()` with a `QMenu` — it renders as a native menu which doesn't match the design spec. Instead:
1. Connect to `QSystemTrayIcon.activated` signal.
2. On click, get the icon geometry via `QSystemTrayIcon.geometry()`.
3. Show the custom `DropdownMenu` widget positioned below the icon.

### 6.2 Floating Pill Implementation

The floating pill is a frameless, translucent, always-on-top window:

```python
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt

class FloatingPill(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # No taskbar/dock entry
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # For macOS vibrancy/blur, use QMacCocoaViewContainer or
        # native NSVisualEffectView via PyObjC
```

**Backdrop blur on macOS:** Qt does not natively support macOS vibrancy for custom widgets. Options:
1. **PyObjC approach:** Access the underlying `NSView` of the QWidget and add an `NSVisualEffectView` as a background layer.
2. **Simulated blur:** Use a semi-transparent solid color without actual blur. This is simpler and may be acceptable for v1.
3. **Recommended:** Start with option 2 (simulated translucency) and upgrade to option 1 if the visual quality is insufficient.

### 6.3 Dragging the Pill

```python
# Implement drag in the FloatingPill class
def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
        self._drag_start_pos = event.globalPosition().toPoint()
        self._window_start_pos = self.pos()

def mouseMoveEvent(self, event):
    if self._drag_start_pos is not None:
        delta = event.globalPosition().toPoint() - self._drag_start_pos
        self.move(self._window_start_pos + delta)

def mouseReleaseEvent(self, event):
    if self._drag_start_pos is not None:
        self._drag_start_pos = None
        # Emit position_changed signal to save position
        self.position_changed.emit(self.x(), self.y())
```

### 6.4 Recording Dot Animation

Use `QPropertyAnimation` for the pulsing effect:

```python
from PySide6.QtCore import QPropertyAnimation, QEasingCurve

# Animate scale and opacity of the recording dot
animation = QPropertyAnimation(self._recording_dot, b"scale")
animation.setDuration(1500)
animation.setStartValue(1.0)
animation.setEndValue(1.3)
animation.setEasingCurve(QEasingCurve.Type.InOutSine)
animation.setLoopCount(-1)  # Infinite loop
```

For the dot itself, subclass QWidget and implement custom `paintEvent` that draws a circle with the accent color and glow.

### 6.5 Settings Window: Custom Title Bar

The settings window uses a custom title bar (no native decorations):

```python
self.setWindowFlags(
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.Window
)
```

Implement a custom title bar widget with:
- Window title text ("SystemSTT Settings")
- Close button (circular, top-right)
- Draggable area (the entire title bar)

### 6.6 Settings Window: Tab Content

Each tab is a separate widget class in `systemstt.ui.tabs.*`. The settings window creates all four tab widgets and shows/hides them based on the active tab.

Use `QStackedWidget` for tab content:
```python
from PySide6.QtWidgets import QStackedWidget

self.tab_stack = QStackedWidget()
self.tab_stack.addWidget(GeneralTab(self.settings))
self.tab_stack.addWidget(EngineTab(self.settings))
self.tab_stack.addWidget(AudioTab(self.settings))
self.tab_stack.addWidget(CommandsTab(self.settings))
```

### 6.7 Bidirectional Text in Preview

The transcription preview area must handle mixed Hebrew/English text:

```python
# Qt handles BiDi automatically if text alignment is set correctly
from PySide6.QtCore import Qt

preview_label = QLabel()
preview_label.setAlignment(Qt.AlignmentFlag.AlignLeading)  # Follows text direction
preview_label.setTextFormat(Qt.TextFormat.PlainText)
# Qt's text layout engine handles Unicode BiDi algorithm automatically
```

### 6.8 Reduced Motion Support

Per design spec section 12, respect the system's reduced motion preference:

```python
from PySide6.QtWidgets import QApplication

def prefers_reduced_motion() -> bool:
    """Check if the user has enabled reduced motion in system settings."""
    # On macOS, check NSWorkspace.accessibilityDisplayShouldReduceMotion
    # This can be accessed via PyObjC
    ...
```

When reduced motion is enabled: disable the recording dot pulse animation, use instant transitions instead of animated ones.

### 6.9 Audio Level Meter Widget

The level meter in the Audio tab is a custom-painted widget:

```python
class LevelMeterWidget(QWidget):
    """
    Horizontal level meter with colored segments.
    Green (normal) -> Yellow (loud) -> Red (clipping).
    """

    def set_level(self, rms_db: float, peak_db: float) -> None:
        """Update the meter display. Called from a timer when Audio tab is visible."""
        ...

    def paintEvent(self, event) -> None:
        """
        Draw the meter as a horizontal bar:
        - Background: --bg-elevated
        - Fill: gradient from green to yellow to red based on level
        - Peak indicator: thin line at peak position
        """
        ...
```

### 6.10 Signal/Slot Wiring

The UI layer communicates with the App Core exclusively through Qt signals:

**UI -> App Core (user actions):**
- `settings_changed(key, value)` — user changed a setting
- `dictation_toggle_requested()` — user clicked Start/Stop in dropdown
- `hotkey_changed(binding)` — user changed the hotkey
- `engine_changed(type)` — user switched engine

**App Core -> UI (state updates):**
- `UIState.dictation_state_changed(state)` — pill show/hide, menu bar update
- `UIState.language_changed(lang)` — pill and menu bar language label
- `UIState.preview_text_changed(text)` — pill preview area
- `UIState.error_changed(msg)` — pill error display

This ensures the UI is purely reactive — it never decides what to do, only how to display it.

### 6.11 Testing

- **Widget tests (pytest-qt):** Test that widgets render without errors, respond to signal emissions, and update their visual state correctly.
- **Theme tests:** Verify that `generate_qss()` produces valid QSS containing all design token values.
- **Snapshot tests (optional):** Capture widget screenshots and compare against baselines for visual regression.
- **Integration:** Show the settings window, change values, verify `settings_changed` signal is emitted with correct keys and values.
