"""
ToggleSwitch — custom-painted animated toggle switch.

A 40×22px pill-shaped toggle that animates its thumb position
between off (left) and on (right) using QPropertyAnimation.

Design spec reference: Section 2.1 (widget tokens), Section 6 (settings).
"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import QWidget

from systemstt.ui.theme import TOKENS

# Toggle geometry
_THUMB_SIZE = 16
_THUMB_MARGIN = 3  # (22 - 16) / 2 = 3
_THUMB_OFF_X = _THUMB_MARGIN
_THUMB_ON_X = TOKENS.toggle_width - _THUMB_SIZE - _THUMB_MARGIN
_TRACK_RADIUS = TOKENS.toggle_height // 2  # 11px pill shape


class ToggleSwitch(QWidget):
    """Animated toggle switch widget.

    Signals:
        toggled(bool): Emitted when the checked state changes.
    """

    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(TOKENS.toggle_width, TOKENS.toggle_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._checked = False
        self._thumb_x = float(_THUMB_OFF_X)
        self._animation: QPropertyAnimation | None = None

    # --- Qt property for animation ---

    def _get_thumb_position(self) -> float:
        return self._thumb_x

    def _set_thumb_position(self, x: float) -> None:
        self._thumb_x = x
        self.update()

    thumb_position = Property(
        float,
        _get_thumb_position,
        _set_thumb_position,
    )

    # --- Public API ---

    def is_checked(self) -> bool:
        """Return whether the toggle is in the on state."""
        return self._checked

    def set_checked(self, checked: bool) -> None:
        """Set the toggle state, emitting toggled if changed."""
        if checked == self._checked:
            return
        self._checked = checked
        self._animate_thumb()
        self.toggled.emit(checked)

    # --- Event handling ---

    def mousePressEvent(self, event: object) -> None:  # noqa: N802
        if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)  # type: ignore[arg-type]

    def _on_click(self) -> None:
        """Handle a click: toggle the checked state."""
        self.set_checked(not self._checked)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        """Paint the track and thumb."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track color: bg_active (off) -> accent (on)
        # Interpolate based on thumb position for smooth color transition
        progress = (self._thumb_x - _THUMB_OFF_X) / (_THUMB_ON_X - _THUMB_OFF_X)
        off_color = QColor(TOKENS.bg_active)
        on_color = QColor(TOKENS.accent)
        track_color = QColor(
            int(off_color.red() + (on_color.red() - off_color.red()) * progress),
            int(off_color.green() + (on_color.green() - off_color.green()) * progress),
            int(off_color.blue() + (on_color.blue() - off_color.blue()) * progress),
        )

        # Draw track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(
            QRect(0, 0, self.width(), self.height()),
            _TRACK_RADIUS,
            _TRACK_RADIUS,
        )

        # Draw thumb (white circle)
        painter.setBrush(QColor("#FFFFFF"))
        thumb_y = _THUMB_MARGIN
        painter.drawEllipse(
            int(self._thumb_x),
            thumb_y,
            _THUMB_SIZE,
            _THUMB_SIZE,
        )

        painter.end()

    # --- Animation ---

    def _animate_thumb(self) -> None:
        """Animate the thumb to its target position."""
        if self._animation is not None:
            self._animation.stop()

        target = float(_THUMB_ON_X if self._checked else _THUMB_OFF_X)

        self._animation = QPropertyAnimation(self, b"thumb_position")
        self._animation.setDuration(TOKENS.animation_fast)
        self._animation.setStartValue(self._thumb_x)
        self._animation.setEndValue(target)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.start()
