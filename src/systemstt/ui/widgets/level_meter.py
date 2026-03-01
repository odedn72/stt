"""
LevelMeter — horizontal audio level bar for the audio settings tab.

A custom-painted read-only meter that shows RMS level with color
transitions (green → yellow → red) and a status label.

Design spec reference: Section 6 (audio settings tab).
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from systemstt.ui.theme import TOKENS

# dB range: -60 (silence) to 0 (clipping)
_MIN_DB = -60.0
_MAX_DB = 0.0

# Color thresholds (normalized 0..1)
_YELLOW_THRESHOLD = 0.7  # -18 dB
_RED_THRESHOLD = 0.9  # -6 dB

_BAR_HEIGHT = 8
_BAR_RADIUS = 4


class _LevelBar(QWidget):
    """Custom-painted horizontal level bar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(_BAR_HEIGHT + 8)  # padding
        self._level = 0.0  # normalized 0..1

    def set_level(self, normalized: float) -> None:
        """Set the level as a normalized 0..1 value."""
        self._level = max(0.0, min(1.0, normalized))
        self.update()

    def paintEvent(self, event: object) -> None:  # type: ignore[override]  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Bar area
        bar_y = (self.height() - _BAR_HEIGHT) // 2
        bar_width = self.width()
        bar_rect = QRect(0, bar_y, bar_width, _BAR_HEIGHT)

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(TOKENS.bg_active))
        painter.drawRoundedRect(bar_rect, _BAR_RADIUS, _BAR_RADIUS)

        # Filled portion
        if self._level > 0.0:
            fill_width = max(1, int(bar_width * self._level))
            fill_rect = QRect(0, bar_y, fill_width, _BAR_HEIGHT)

            # Color based on level
            if self._level >= _RED_THRESHOLD:
                color = QColor(TOKENS.error)
            elif self._level >= _YELLOW_THRESHOLD:
                color = QColor(TOKENS.warning)
            else:
                color = QColor(TOKENS.success)

            painter.setBrush(color)
            painter.drawRoundedRect(fill_rect, _BAR_RADIUS, _BAR_RADIUS)

        painter.end()


class LevelMeter(QWidget):
    """Horizontal audio level meter with status label.

    Read-only widget — no user interaction.

    Attributes:
        rms_db: Current RMS level in dB.
        peak_db: Current peak level in dB.
        status_text: Current status string.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.rms_db: float = _MIN_DB
        self.peak_db: float = _MIN_DB
        self.status_text: str = ""

        self._bar = _LevelBar()
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_xs}px;"
            " background: transparent;",
        )
        self._status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self._status_label.setFixedWidth(80)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._bar, stretch=1)
        layout.addWidget(self._status_label)

    def set_level(self, rms_db: float, peak_db: float) -> None:
        """Update the displayed audio level.

        Values are clamped to [-60, 0] dB range.
        """
        self.rms_db = max(_MIN_DB, min(_MAX_DB, rms_db))
        self.peak_db = max(_MIN_DB, min(_MAX_DB, peak_db))

        # Normalize RMS to 0..1
        normalized = (self.rms_db - _MIN_DB) / (_MAX_DB - _MIN_DB)
        self._bar.set_level(normalized)

    def set_status(self, text: str) -> None:
        """Update the status label text (e.g., 'OK', 'Too quiet', 'Too loud')."""
        self.status_text = text
        self._status_label.setText(text)
