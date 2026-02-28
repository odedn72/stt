"""
FloatingPill — floating status indicator during dictation.

A frameless, translucent, always-on-top QWidget that shows dictation
status including language label, elapsed time, live transcription
preview, error messages, and command confirmations.

Design spec reference: Section 5.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import (
    QPoint,
    QPropertyAnimation,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from systemstt.ui.theme import TOKENS

logger = logging.getLogger(__name__)

# Default position: top-center, 48px below menu bar
_DEFAULT_X = -1  # Will be calculated based on screen width
_DEFAULT_Y = 48


class _RecordingDot(QWidget):
    """Pulsing recording dot indicator."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor(TOKENS.accent)
        self._pulse_scale = 1.0
        self._animation: Optional[QPropertyAnimation] = None

    def set_color(self, color: str) -> None:
        """Set the dot color."""
        self._color = QColor(color)
        self.update()

    def start_pulse(self) -> None:
        """Start the pulsing animation."""
        if self._animation is not None:
            self._animation.stop()

        self._animation = QPropertyAnimation(self, b"maximumWidth")
        self._animation.setDuration(TOKENS.animation_pulse)
        self._animation.setStartValue(12)
        self._animation.setEndValue(15)
        self._animation.setLoopCount(-1)
        self._animation.start()

    def stop_pulse(self) -> None:
        """Stop the pulsing animation."""
        if self._animation is not None:
            self._animation.stop()
            self._animation = None
        self.setFixedSize(12, 12)
        self.update()

    def paintEvent(self, event: object) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        size = min(self.width(), self.height())
        x = (self.width() - size) // 2
        y = (self.height() - size) // 2
        painter.drawEllipse(x, y, size, size)
        painter.end()


class FloatingPill(QWidget):
    """Floating status pill shown during active dictation.

    Features:
    - Translucent background with backdrop blur
    - Pulsing recording dot (accent color)
    - Language label, engine indicator, elapsed time
    - Expandable: live transcription preview, error messages, command confirmations
    - Draggable to any screen position, position remembered
    - Appear/disappear animations

    Signals:
        position_changed(int, int): Emitted when the pill is dragged to a new position.
    """

    position_changed = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(TOKENS.pill_min_width)
        self.setMaximumWidth(TOKENS.pill_max_width)

        self._is_visible: bool = False
        self._language: str = "EN"
        self._engine: str = "Cloud"
        self._elapsed_seconds: int = 0
        self._preview_text: str = ""
        self._error_message: str = ""
        self._is_warning: bool = False
        self._command_confirmation: str = ""
        self._position_x: int = _DEFAULT_X
        self._position_y: int = _DEFAULT_Y
        self._has_expansion: bool = False

        # Drag state
        self._drag_start_pos: Optional[QPoint] = None
        self._window_start_pos: Optional[QPoint] = None

        # Command confirmation auto-dismiss timer
        self._confirmation_timer = QTimer(self)
        self._confirmation_timer.setSingleShot(True)
        self._confirmation_timer.timeout.connect(self._dismiss_confirmation)

        self._setup_ui()
        self._apply_shadow()

    def _setup_ui(self) -> None:
        """Build the pill layout."""
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Status bar (always visible when pill is shown)
        self._status_bar = QWidget()
        self._status_bar.setFixedHeight(TOKENS.pill_collapsed_height)
        self._status_bar.setStyleSheet("background: transparent;")
        status_layout = QHBoxLayout(self._status_bar)
        status_layout.setContentsMargins(14, 8, 14, 8)
        status_layout.setSpacing(8)

        # Recording dot
        self._dot = _RecordingDot()
        status_layout.addWidget(self._dot)

        # Language label
        self._language_label = QLabel("EN")
        self._language_label.setStyleSheet(
            f"color: {TOKENS.text_primary}; font-size: {TOKENS.text_lg}px;"
            f" font-weight: 600; background: transparent;"
        )
        status_layout.addWidget(self._language_label)

        # Separator
        sep1 = QWidget()
        sep1.setFixedWidth(1)
        sep1.setFixedHeight(int(TOKENS.pill_collapsed_height * 0.6))
        sep1.setStyleSheet(f"background-color: {TOKENS.border};")
        status_layout.addWidget(sep1)

        # Engine indicator
        self._engine_label = QLabel("Cloud")
        self._engine_label.setStyleSheet(
            f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_xs}px;"
            " background: transparent;"
        )
        status_layout.addWidget(self._engine_label)

        # Separator
        sep2 = QWidget()
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(int(TOKENS.pill_collapsed_height * 0.6))
        sep2.setStyleSheet(f"background-color: {TOKENS.border};")
        status_layout.addWidget(sep2)

        # Elapsed time
        self._time_label = QLabel("0:00")
        self._time_label.setStyleSheet(
            f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_xs}px;"
            " background: transparent;"
        )
        status_layout.addWidget(self._time_label)

        status_layout.addStretch()
        self._main_layout.addWidget(self._status_bar)

        # Expansion area (preview / error / command)
        self._expansion_widget = QWidget()
        self._expansion_widget.setStyleSheet("background: transparent;")
        expansion_layout = QVBoxLayout(self._expansion_widget)
        expansion_layout.setContentsMargins(14, 0, 14, 8)
        expansion_layout.setSpacing(0)

        # Expansion divider
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {TOKENS.border};")
        expansion_layout.addWidget(divider)

        # Expansion text label
        self._expansion_label = QLabel("")
        self._expansion_label.setWordWrap(True)
        self._expansion_label.setMaximumHeight(80)
        self._expansion_label.setAlignment(
            Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignTop
        )
        mono_font = QFont()
        mono_font.setFamily("SF Mono")
        mono_font.setPixelSize(TOKENS.text_sm)
        self._expansion_label.setFont(mono_font)
        self._expansion_label.setStyleSheet(
            f"color: {TOKENS.text_primary}; background: transparent;"
            " padding-top: 8px;"
        )
        expansion_layout.addWidget(self._expansion_label)

        self._expansion_widget.setVisible(False)
        self._main_layout.addWidget(self._expansion_widget)

    def _apply_shadow(self) -> None:
        """Apply drop shadow to the pill."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 77))
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event: object) -> None:  # type: ignore[override]
        """Paint the translucent rounded background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        radius = float(TOKENS.border_radius_pill if not self._has_expansion
                        else TOKENS.border_radius_lg)
        path.addRoundedRect(
            0.0, 0.0, float(self.width()), float(self.height()),
            radius, radius,
        )
        painter.fillPath(path, QColor(26, 26, 46, 178))
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.drawPath(path)
        painter.end()

    # --- Public API ---

    def show_active(
        self,
        language: str = "EN",
        engine: str = "Cloud",
    ) -> None:
        """Show the pill with active dictation state. Animates in."""
        self._is_visible = True
        self._language = language
        self._engine = engine
        self._elapsed_seconds = 0
        self._error_message = ""
        self._command_confirmation = ""
        self._has_expansion = False

        self._language_label.setText(language)
        self._engine_label.setText(f"\u2601 {engine}" if engine == "Cloud" else f"\u2699 {engine}")
        self._time_label.setText("0:00")
        self._dot.set_color(TOKENS.accent)
        self._dot.start_pulse()
        self._expansion_widget.setVisible(False)

        self._position_to_default_if_needed()
        self.show()
        self.raise_()
        logger.debug("Floating pill shown: language=%s, engine=%s", language, engine)

    def hide_pill(self) -> None:
        """Hide the pill. Animates out."""
        self._is_visible = False
        self._has_expansion = False
        self._dot.stop_pulse()
        self.hide()
        logger.debug("Floating pill hidden")

    def update_language(self, language: str) -> None:
        """Update the language label in real time."""
        self._language = language
        self._language_label.setText(language)
        logger.debug("Pill language updated: %s", language)

    def update_elapsed_time(self, seconds: int) -> None:
        """Update the elapsed time display (e.g., "0:12")."""
        self._elapsed_seconds = seconds
        self._time_label.setText(self._format_time(seconds))
        logger.debug("Pill elapsed time: %s", self._format_time(seconds))

    def show_preview_text(self, text: str) -> None:
        """Show or update the live transcription preview area.

        Text direction (LTR/RTL) is auto-detected by Qt.
        """
        self._preview_text = text
        if text:
            self._has_expansion = True
            self._expansion_label.setText(text)
            self._expansion_widget.setVisible(True)
            self.update()
        logger.debug("Pill preview text: %s", text[:50] if text else "(empty)")

    def hide_preview(self) -> None:
        """Hide the transcription preview area."""
        self._preview_text = ""
        if not self._error_message and not self._command_confirmation:
            self._has_expansion = False
            self._expansion_widget.setVisible(False)
            self.update()
        logger.debug("Pill preview hidden")

    def show_error(self, message: str, is_warning: bool = False) -> None:
        """Show an inline error/warning in the expansion area.

        Dot changes to error/warning color.
        """
        self._error_message = message
        self._is_warning = is_warning
        self._has_expansion = True

        color = TOKENS.warning if is_warning else TOKENS.error
        self._dot.set_color(color)
        self._dot.stop_pulse()
        self._expansion_label.setStyleSheet(
            f"color: {color}; background: transparent; padding-top: 8px;"
        )
        self._expansion_label.setText(message)
        self._expansion_widget.setVisible(True)
        self.update()

        level = "warning" if is_warning else "error"
        logger.debug("Pill %s: %s", level, message)

    def show_command_confirmation(self, message: str) -> None:
        """Show a voice command confirmation (e.g., "Deleted last word").

        Auto-dismisses after 2 seconds.
        """
        self._command_confirmation = message
        self._has_expansion = True

        self._expansion_label.setStyleSheet(
            f"color: {TOKENS.success}; background: transparent; padding-top: 8px;"
        )
        self._expansion_label.setText(f"\u2713 {message}")
        self._expansion_widget.setVisible(True)
        self.update()

        self._confirmation_timer.start(2000)
        logger.debug("Pill command confirmation: %s", message)

    def clear_expansion(self) -> None:
        """Collapse the expansion area, returning to the compact pill."""
        self._preview_text = ""
        self._error_message = ""
        self._command_confirmation = ""
        self._has_expansion = False
        self._expansion_widget.setVisible(False)

        # Reset dot to accent color
        self._dot.set_color(TOKENS.accent)
        if self._is_visible:
            self._dot.start_pulse()

        # Reset expansion label style
        self._expansion_label.setStyleSheet(
            f"color: {TOKENS.text_primary}; background: transparent; padding-top: 8px;"
        )
        self.update()
        logger.debug("Pill expansion cleared")

    def set_position(self, x: int, y: int) -> None:
        """Set the pill position on screen."""
        self._position_x = x
        self._position_y = y
        self.move(x, y)
        logger.debug("Pill position set: (%d, %d)", x, y)

    def reset_position(self) -> None:
        """Reset to default position: top-center, 48px below menu bar."""
        self._position_x = _DEFAULT_X
        self._position_y = _DEFAULT_Y
        self._position_to_default_if_needed()
        logger.debug("Pill position reset to default")

    # --- Drag support ---

    def mousePressEvent(self, event: object) -> None:  # type: ignore[override]
        from PySide6.QtGui import QMouseEvent

        if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
            self._window_start_pos = self.pos()
        super().mousePressEvent(event)  # type: ignore[arg-type]

    def mouseMoveEvent(self, event: object) -> None:  # type: ignore[override]
        from PySide6.QtGui import QMouseEvent

        if (
            isinstance(event, QMouseEvent)
            and self._drag_start_pos is not None
            and self._window_start_pos is not None
        ):
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            self.move(self._window_start_pos + delta)
        super().mouseMoveEvent(event)  # type: ignore[arg-type]

    def mouseReleaseEvent(self, event: object) -> None:  # type: ignore[override]
        from PySide6.QtGui import QMouseEvent

        if isinstance(event, QMouseEvent) and self._drag_start_pos is not None:
            self._drag_start_pos = None
            self._window_start_pos = None
            self._position_x = self.x()
            self._position_y = self.y()
            self.position_changed.emit(self.x(), self.y())
        super().mouseReleaseEvent(event)  # type: ignore[arg-type]

    # --- Internal helpers ---

    def _position_to_default_if_needed(self) -> None:
        """Move the pill to the default or saved position."""
        if self._position_x == _DEFAULT_X:
            screen = self.screen()
            if screen is not None:
                screen_geo = screen.availableGeometry()
                x = screen_geo.x() + (screen_geo.width() - self.width()) // 2
                y = screen_geo.y() + _DEFAULT_Y
                self.move(x, y)
            else:
                self.move(200, _DEFAULT_Y)
        else:
            self.move(self._position_x, self._position_y)

    def _dismiss_confirmation(self) -> None:
        """Auto-dismiss the command confirmation expansion."""
        if self._command_confirmation:
            self._command_confirmation = ""
            if not self._preview_text and not self._error_message:
                self.clear_expansion()

    @staticmethod
    def _format_time(seconds: int) -> str:
        """Format seconds as elapsed time string."""
        if seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}:{secs:02d}"
        hours = seconds // 3600
        remainder = seconds % 3600
        minutes = remainder // 60
        secs = remainder % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
