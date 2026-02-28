"""
SettingsWindow — tabbed settings dialog.

A fixed-size QWidget with custom title bar and four tabs:
General, Engine, Audio, Commands. Displays and allows editing
of all application settings.

Design spec reference: Section 6.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QMouseEvent
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from systemstt.config.models import SettingsModel
from systemstt.ui.theme import TOKENS

logger = logging.getLogger(__name__)

# Tab names
TAB_GENERAL = "general"
TAB_ENGINE = "engine"
TAB_AUDIO = "audio"
TAB_COMMANDS = "commands"

_VALID_TABS = {TAB_GENERAL, TAB_ENGINE, TAB_AUDIO, TAB_COMMANDS}
_TAB_INDEX = {TAB_GENERAL: 0, TAB_ENGINE: 1, TAB_AUDIO: 2, TAB_COMMANDS: 3}
_TAB_LABELS = ["General", "Engine", "Audio", "Commands"]


class _TitleBar(QWidget):
    """Custom title bar with title text, close button, and drag support."""

    close_requested = Signal()

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(40)
        self._drag_start = None
        self._window_start = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {TOKENS.text_primary}; font-size: {TOKENS.text_lg}px;"
            f" font-weight: 600; background: transparent;"
        )
        layout.addWidget(title_label)
        layout.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {TOKENS.text_secondary};"
            f"  border: none;"
            f"  border-radius: 12px;"
            f"  font-size: 14px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {TOKENS.error};"
            f"  color: #FFFFFF;"
            f"}}"
        )
        close_btn.clicked.connect(self.close_requested)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event: object) -> None:  # type: ignore[override]
        if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            win = self.window()
            if win is not None:
                self._window_start = win.pos()
        super().mousePressEvent(event)  # type: ignore[arg-type]

    def mouseMoveEvent(self, event: object) -> None:  # type: ignore[override]
        if (
            isinstance(event, QMouseEvent)
            and self._drag_start is not None
            and self._window_start is not None
        ):
            delta = event.globalPosition().toPoint() - self._drag_start
            win = self.window()
            if win is not None:
                win.move(self._window_start + delta)
        super().mouseMoveEvent(event)  # type: ignore[arg-type]

    def mouseReleaseEvent(self, event: object) -> None:  # type: ignore[override]
        self._drag_start = None
        self._window_start = None
        super().mouseReleaseEvent(event)  # type: ignore[arg-type]


class _TabButton(QPushButton):
    """A styled tab button."""

    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setFixedHeight(TOKENS.tab_height)
        self._update_style()

    def _update_style(self) -> None:
        if self.isChecked():
            self.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {TOKENS.bg_elevated};"
                f"  color: {TOKENS.accent};"
                f"  border: none;"
                f"  border-bottom: 2px solid {TOKENS.accent};"
                f"  font-size: {TOKENS.text_md}px;"
                f"  font-weight: 500;"
                f"  padding: 0 16px;"
                f"}}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: transparent;"
                f"  color: {TOKENS.text_secondary};"
                f"  border: none;"
                f"  border-bottom: 2px solid transparent;"
                f"  font-size: {TOKENS.text_md}px;"
                f"  font-weight: 500;"
                f"  padding: 0 16px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  color: {TOKENS.text_primary};"
                f"  background-color: {TOKENS.bg_hover};"
                f"}}"
            )

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        super().setChecked(checked)
        self._update_style()


class _TabContent(QWidget):
    """Placeholder tab content widget with a label."""

    def __init__(self, tab_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {TOKENS.bg_elevated};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        label = QLabel(f"{tab_name.capitalize()} Tab")
        label.setStyleSheet(
            f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_md}px;"
            " background: transparent;"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addStretch()


class SettingsWindow(QWidget):
    """Tabbed settings window matching design spec section 6.

    Properties:
    - Fixed size: 480x420px
    - Custom title bar (no native decorations)
    - Four tabs: General, Engine, Audio, Commands
    - Background: solid dark (#1A1A2E)
    - Centered on screen when opened

    Signals:
        settings_changed(str, object): Emitted when any setting changes.
        hotkey_changed(object): Emitted when the hotkey binding changes.
        engine_changed(str): Emitted when the engine type changes.
        api_key_changed(str): Emitted when the API key changes.
        model_download_requested(str): Emitted when model download is requested.
    """

    # Signals emitted when settings change
    settings_changed = Signal(str, object)
    hotkey_changed = Signal(object)
    engine_changed = Signal(str)
    api_key_changed = Signal(str)
    model_download_requested = Signal(str)

    def __init__(
        self,
        settings: SettingsModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
        )
        self.setFixedSize(TOKENS.settings_width, TOKENS.settings_height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._settings = settings
        self._current_tab: str = TAB_GENERAL
        self._api_status: str = ""
        self._model_status: str = ""
        self._model_download_progress: float = 0.0
        self._audio_devices: list[Any] = []
        self._audio_level: Any = None

        self._setup_ui()
        self._apply_shadow()

    def _setup_ui(self) -> None:
        """Build the settings window layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Custom title bar
        self._title_bar = _TitleBar("SystemSTT Settings")
        self._title_bar.close_requested.connect(self.close)
        main_layout.addWidget(self._title_bar)

        # Tab bar
        tab_bar_widget = QWidget()
        tab_bar_widget.setStyleSheet("background: transparent;")
        tab_bar_layout = QHBoxLayout(tab_bar_widget)
        tab_bar_layout.setContentsMargins(0, 0, 0, 0)
        tab_bar_layout.setSpacing(0)

        self._tab_buttons: list[_TabButton] = []
        for i, label in enumerate(_TAB_LABELS):
            btn = _TabButton(label)
            btn.clicked.connect(lambda checked, idx=i: self._on_tab_clicked(idx))
            tab_bar_layout.addWidget(btn)
            self._tab_buttons.append(btn)

        main_layout.addWidget(tab_bar_widget)

        # Tab content stack
        self._stack = QStackedWidget()
        for tab_name in [TAB_GENERAL, TAB_ENGINE, TAB_AUDIO, TAB_COMMANDS]:
            self._stack.addWidget(_TabContent(tab_name))
        main_layout.addWidget(self._stack)

        # Select the first tab
        self._select_tab(0)

    def _apply_shadow(self) -> None:
        """Apply drop shadow."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 102))
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event: object) -> None:  # type: ignore[override]
        """Paint the solid dark background with rounded corners."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(
            0.0, 0.0, float(self.width()), float(self.height()),
            TOKENS.border_radius_lg, TOKENS.border_radius_lg,
        )
        painter.fillPath(path, QColor(TOKENS.bg_solid))
        painter.end()

    def showEvent(self, event: object) -> None:  # type: ignore[override]
        """Center the window on screen when shown."""
        screen = self.screen()
        if screen is not None:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)
        super().showEvent(event)  # type: ignore[arg-type]

    def _on_tab_clicked(self, index: int) -> None:
        """Handle tab button click."""
        self._select_tab(index)

    def _select_tab(self, index: int) -> None:
        """Switch to the tab at the given index."""
        for i, btn in enumerate(self._tab_buttons):
            btn.setChecked(i == index)
        self._stack.setCurrentIndex(index)
        tab_names = list(_TAB_INDEX.keys())
        if 0 <= index < len(tab_names):
            self._current_tab = tab_names[index]

    # --- Public API ---

    def show_tab(self, tab_name: str) -> None:
        """Show a specific tab ("general", "engine", "audio", "commands")."""
        if tab_name not in _VALID_TABS:
            logger.warning("Unknown tab: %s", tab_name)
            return
        self._current_tab = tab_name
        index = _TAB_INDEX[tab_name]
        self._select_tab(index)
        logger.debug("Settings window tab: %s", tab_name)

    def update_from_settings(self, settings: SettingsModel) -> None:
        """Refresh all controls from the settings model."""
        self._settings = settings
        logger.debug("Settings window updated from model")

    def update_api_status(self, status: str) -> None:
        """Update the API status indicator ("Connected", "Invalid key", "Unreachable")."""
        self._api_status = status
        logger.debug("API status: %s", status)

    def update_model_status(self, status: str) -> None:
        """Update the model status indicator ("Loaded (medium)", "Not downloaded")."""
        self._model_status = status
        logger.debug("Model status: %s", status)

    def update_model_download_progress(self, progress: float) -> None:
        """Update the model download progress bar (0.0 to 1.0)."""
        self._model_download_progress = max(0.0, min(1.0, progress))
        logger.debug("Model download progress: %.1f%%", progress * 100)

    def update_audio_devices(self, devices: Sequence[Any]) -> None:
        """Refresh the audio device dropdown list."""
        self._audio_devices = list(devices)
        logger.debug("Audio devices updated: %d devices", len(devices))

    def update_audio_level(self, level: Any) -> None:
        """Update the live audio level meter."""
        self._audio_level = level
        logger.debug("Audio level updated")
