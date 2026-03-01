"""
SectionHeader — uppercase section label for settings panels.

A styled QLabel that renders as an uppercase section divider with
appropriate spacing above and below.

Design spec reference: Section 2.1 (typography), Section 6 (settings layout).
"""

from __future__ import annotations

from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from systemstt.ui.theme import TOKENS


class SectionHeader(QLabel):
    """Uppercase section label for grouping settings.

    Args:
        text: The section title text.
        is_first: If True, uses reduced top margin (16px instead of 24px).
        parent: Optional parent widget.
    """

    def __init__(
        self,
        text: str,
        is_first: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)

        # Typography: text_xs, weight 600
        font = QFont()
        font.setPixelSize(TOKENS.text_xs)
        font.setWeight(QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        font.setCapitalization(QFont.Capitalization.AllUppercase)
        self.setFont(font)

        # Color
        self.setStyleSheet(f"color: {TOKENS.text_secondary}; background: transparent;")

        # Alignment
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Margins: 24px top (or 16px if first), 8px bottom
        top_margin = 16 if is_first else 24
        self.setContentsMargins(QMargins(0, top_margin, 0, 8))
