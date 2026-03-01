"""
DropdownMenu — custom dropdown for the menu bar icon.

A custom-drawn translucent dropdown (NOT a native QMenu) that shows
dictation status, controls, and app actions. Positioned below the
menu bar icon when clicked.

Design spec reference: Section 4.3.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from systemstt.ui.theme import TOKENS

logger = logging.getLogger(__name__)


class _MenuItemWidget(QWidget):
    """A single clickable item in the dropdown menu."""

    clicked = Signal()

    def __init__(
        self,
        label: str,
        shortcut: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        self._label = QLabel(label)
        self._label.setStyleSheet(
            f"color: {TOKENS.text_primary}; font-size: {TOKENS.text_base}px;"
            " background: transparent;"
        )
        layout.addWidget(self._label)

        layout.addStretch()

        self._shortcut_label: QLabel | None = None
        if shortcut:
            self._shortcut_label = QLabel(shortcut)
            self._shortcut_label.setStyleSheet(
                f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_sm}px;"
                " background: transparent;"
            )
            layout.addWidget(self._shortcut_label)

    def set_label(self, text: str) -> None:
        """Update the item label text."""
        self._label.setText(text)

    def enterEvent(self, event: object) -> None:  # noqa: N802
        self._hovered = True
        self.setStyleSheet(f"background-color: {TOKENS.bg_hover};")
        super().enterEvent(event)  # type: ignore[arg-type]

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        self._hovered = False
        self.setStyleSheet("background-color: transparent;")
        super().leaveEvent(event)  # type: ignore[arg-type]

    def mousePressEvent(self, event: object) -> None:  # noqa: N802
        self.clicked.emit()
        super().mousePressEvent(event)  # type: ignore[arg-type]


class _DividerWidget(QWidget):
    """A horizontal divider line."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(9)  # 4px margin top + 1px line + 4px margin bottom

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        y = self.height() // 2
        painter.drawLine(0, y, self.width(), y)
        painter.end()


class DropdownMenu(QWidget):
    """Custom-drawn dropdown menu matching design spec section 4.3.

    This is NOT a native QMenu -- it is a custom frameless QWidget with
    translucent background, custom styling, and shadow.

    Properties:
    - Width: 240px
    - Background: translucent dark
    - Corner radius: 10px
    - Shadow: 0 8px 32px rgba(0,0,0,0.4)
    """

    # Signals
    start_stop_clicked = Signal()
    show_hide_preview_clicked = Signal()
    settings_clicked = Signal()
    quit_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Popup
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(TOKENS.dropdown_menu_width)

        self._is_active = False
        self._language = "EN"
        self._engine = "Cloud"
        self._is_preview_on = False

        self._setup_ui()
        self._apply_shadow()

    def _setup_ui(self) -> None:
        """Build the dropdown menu layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)

        # App title
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(12, 4, 12, 4)
        self._title_label = QLabel("SystemSTT")
        self._title_label.setStyleSheet(
            f"color: {TOKENS.text_primary}; font-size: {TOKENS.text_md}px;"
            f" font-weight: 500; background: transparent;"
        )
        title_layout.addWidget(self._title_label)
        layout.addWidget(title_container)

        layout.addWidget(_DividerWidget())

        # Status section
        status_container = QWidget()
        status_container.setStyleSheet("background: transparent;")
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(12, 4, 12, 4)
        status_layout.setSpacing(2)

        self._status_label = QLabel("Dictation Inactive")
        self._status_label.setStyleSheet(
            f"color: {TOKENS.text_disabled}; font-size: {TOKENS.text_base}px;"
            " background: transparent;"
        )
        status_layout.addWidget(self._status_label)

        self._language_label = QLabel("Language: English")
        self._language_label.setStyleSheet(
            f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_sm}px;"
            " background: transparent;"
        )
        status_layout.addWidget(self._language_label)

        self._engine_label = QLabel("Engine: Cloud API")
        self._engine_label.setStyleSheet(
            f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_sm}px;"
            " background: transparent;"
        )
        status_layout.addWidget(self._engine_label)

        layout.addWidget(status_container)
        layout.addWidget(_DividerWidget())

        # Action items
        self._start_stop_item = _MenuItemWidget("Start Dictation", "\u2325Space")
        self._start_stop_item.clicked.connect(self._on_start_stop)
        layout.addWidget(self._start_stop_item)

        self._preview_item = _MenuItemWidget("Show Preview", "\u2325P")
        self._preview_item.clicked.connect(self._on_preview_toggle)
        layout.addWidget(self._preview_item)

        layout.addWidget(_DividerWidget())

        settings_item = _MenuItemWidget("Settings...", "\u2318,")
        settings_item.clicked.connect(self._on_settings)
        layout.addWidget(settings_item)

        quit_item = _MenuItemWidget("Quit SystemSTT", "\u2318Q")
        quit_item.clicked.connect(self._on_quit)
        layout.addWidget(quit_item)

    def _apply_shadow(self) -> None:
        """Apply drop shadow effect to the menu."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 102))
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        """Paint the translucent rounded background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        path = QPainterPath()
        path.addRoundedRect(
            0.0,
            0.0,
            float(self.width()),
            float(self.height()),
            TOKENS.border_radius_md,
            TOKENS.border_radius_md,
        )
        painter.fillPath(path, QColor(26, 26, 46, 178))

        # Border
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.drawPath(path)
        painter.end()

    def update_state(
        self,
        is_active: bool,
        language: str,
        engine: str,
        is_preview_on: bool,
    ) -> None:
        """Update all dynamic content based on current app state."""
        self._is_active = is_active
        self._language = language
        self._engine = engine
        self._is_preview_on = is_preview_on

        if is_active:
            self._status_label.setText("Dictation Active")
            self._status_label.setStyleSheet(
                f"color: {TOKENS.accent}; font-size: {TOKENS.text_base}px; background: transparent;"
            )
            self._start_stop_item.set_label("Stop Dictation")
        else:
            self._status_label.setText("Dictation Inactive")
            self._status_label.setStyleSheet(
                f"color: {TOKENS.text_disabled}; font-size: {TOKENS.text_base}px;"
                " background: transparent;"
            )
            self._start_stop_item.set_label("Start Dictation")

        lang_name = "Hebrew" if language == "HE" else "English"
        self._language_label.setText(f"Language: {lang_name}")
        self._engine_label.setText(f"Engine: {engine}")

        if is_preview_on:
            self._preview_item.set_label("Hide Preview")
        else:
            self._preview_item.set_label("Show Preview")

    def show_at(self, x: int, y: int) -> None:
        """Show the dropdown at a specific screen position."""
        self.move(x, y)
        self.show()
        self.raise_()

    def _on_start_stop(self) -> None:
        self.hide()
        self.start_stop_clicked.emit()

    def _on_preview_toggle(self) -> None:
        self.hide()
        self.show_hide_preview_clicked.emit()

    def _on_settings(self) -> None:
        self.hide()
        self.settings_clicked.emit()

    def _on_quit(self) -> None:
        self.hide()
        self.quit_clicked.emit()
