"""
MenuBarWidget — menu bar icon with language label.

Uses QSystemTrayIcon as the base for system tray integration.
The icon is rendered as a composite image containing both the mic
icon and the language label (since QSystemTrayIcon doesn't support
text labels natively).

Design spec reference: Section 4.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, QSize, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from systemstt.ui.theme import TOKENS

logger = logging.getLogger(__name__)


def _create_menu_bar_icon(
    language: str,
    is_active: bool,
    is_error: bool,
) -> QIcon:
    """Render the menu bar icon: mic indicator + language label as a single image.

    For macOS retina, renders at 2x and sets devicePixelRatio.
    """
    # Render at 2x for retina
    scale = 2
    width = 44 * scale
    height = 22 * scale
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    image.setDevicePixelRatio(scale)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Determine colors
    if is_error:
        dot_color = QColor(TOKENS.warning)
        text_color = QColor(TOKENS.text_secondary)
    elif is_active:
        dot_color = QColor(TOKENS.accent)
        text_color = QColor(TOKENS.text_primary)
    else:
        dot_color = QColor(TOKENS.text_secondary)
        text_color = QColor(TOKENS.text_secondary)

    # Draw mic indicator dot/circle
    dot_x = 6.0
    dot_y = 7.0
    dot_radius = 4.0
    if is_active:
        painter.setBrush(dot_color)
        painter.setPen(dot_color)
        painter.drawEllipse(int(dot_x), int(dot_y), int(dot_radius * 2), int(dot_radius * 2))
    else:
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.setPen(dot_color)
        painter.drawEllipse(int(dot_x), int(dot_y), int(dot_radius * 2), int(dot_radius * 2))

    # Draw language label
    font = QFont()
    font.setPixelSize(TOKENS.text_sm)
    font.setWeight(QFont.Weight.Medium)
    painter.setFont(font)
    painter.setPen(text_color)
    painter.drawText(18, 3, 24, 16, 0, language)

    painter.end()

    pixmap = QPixmap.fromImage(image)
    return QIcon(pixmap)


class MenuBarWidget(QObject):
    """Menu bar integration: icon + language label.

    Uses QSystemTrayIcon for system tray placement. The icon image is
    a composite containing the mic indicator and the language label.

    Signals:
        dictation_toggle_requested: User clicked Start/Stop dictation.
        preview_toggle_requested: User toggled live preview.
        settings_requested: User clicked Settings.
        quit_requested: User clicked Quit.
    """

    # Signals for communicating user actions to the App Core
    dictation_toggle_requested = Signal()
    preview_toggle_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: Optional[QApplication] = None) -> None:
        super().__init__(parent)
        self._app = parent
        self._language: str = "EN"
        self._state: str = "idle"
        self._is_active: bool = False
        self._is_preview_on: bool = False
        self._engine: str = "Cloud"

        # Create the system tray icon
        self._tray = QSystemTrayIcon(self)
        self._update_icon()
        self._tray.activated.connect(self._on_tray_activated)

        # Timer for reverting error state after 5 seconds
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.timeout.connect(self._revert_from_error)

        # Dropdown menu (lazy-created when first needed)
        self._dropdown: Optional[object] = None

    def show(self) -> None:
        """Show the tray icon."""
        self._tray.show()

    def hide(self) -> None:
        """Hide the tray icon."""
        self._tray.hide()

    def set_state_idle(self, language: str = "EN") -> None:
        """Set menu bar to idle state.

        Icon: outlined mic, dimmed. Language label: dimmed.
        """
        self._state = "idle"
        self._language = language
        self._is_active = False
        self._error_timer.stop()
        self._update_icon()
        logger.debug("Menu bar state: idle, language=%s", language)

    def set_state_active(self, language: str = "EN") -> None:
        """Set menu bar to active state.

        Icon: filled mic, accent color. Language label: bright.
        """
        self._state = "active"
        self._language = language
        self._is_active = True
        self._error_timer.stop()
        self._update_icon()
        logger.debug("Menu bar state: active, language=%s", language)

    def set_state_error(self, language: str = "EN") -> None:
        """Set menu bar to error state.

        Icon: warning triangle, warning color. Reverts after 5 seconds.
        """
        self._state = "error"
        self._language = language
        self._update_icon()
        self._error_timer.start(5000)
        logger.debug("Menu bar state: error, language=%s", language)

    def update_language(self, language: str) -> None:
        """Update the language label (e.g., "EN" -> "HE") in real time."""
        self._language = language
        self._update_icon()
        logger.debug("Menu bar language updated: %s", language)

    def update_dropdown_status(
        self,
        is_active: bool,
        language: str,
        engine: str,
        is_preview_on: bool,
    ) -> None:
        """Update dynamic content in the dropdown menu."""
        self._is_active = is_active
        self._language = language
        self._engine = engine
        self._is_preview_on = is_preview_on
        self._update_icon()
        logger.debug(
            "Dropdown status: active=%s, language=%s, engine=%s, preview=%s",
            is_active,
            language,
            engine,
            is_preview_on,
        )

    def _update_icon(self) -> None:
        """Re-render and set the tray icon based on current state."""
        icon = _create_menu_bar_icon(
            language=self._language,
            is_active=(self._state == "active"),
            is_error=(self._state == "error"),
        )
        self._tray.setIcon(icon)
        tooltip = f"SystemSTT — {self._language}"
        if self._is_active:
            tooltip += " (Active)"
        self._tray.setToolTip(tooltip)

    def _revert_from_error(self) -> None:
        """Revert from error state to idle after the timer expires."""
        if self._state == "error":
            self.set_state_idle(self._language)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation (click)."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_dropdown()

    def _show_dropdown(self) -> None:
        """Show the custom dropdown menu below the tray icon."""
        from systemstt.ui.dropdown_menu import DropdownMenu

        if self._dropdown is None:
            dropdown = DropdownMenu()
            dropdown.start_stop_clicked.connect(self.dictation_toggle_requested)
            dropdown.show_hide_preview_clicked.connect(self.preview_toggle_requested)
            dropdown.settings_clicked.connect(self.settings_requested)
            dropdown.quit_clicked.connect(self.quit_requested)
            self._dropdown = dropdown

        dropdown = self._dropdown
        assert isinstance(dropdown, DropdownMenu)
        dropdown.update_state(
            is_active=self._is_active,
            language=self._language,
            engine=self._engine,
            is_preview_on=self._is_preview_on,
        )

        # Position below the tray icon
        geo = self._tray.geometry()
        if geo.isValid():
            x = geo.x() - TOKENS.dropdown_menu_width // 2 + geo.width() // 2
            y = geo.y() + geo.height()
            dropdown.show_at(x, y)
        else:
            # Fallback: show near top-right of screen
            dropdown.show_at(100, 30)
