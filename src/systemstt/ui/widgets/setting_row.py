"""
SettingRow — horizontal label + control layout for settings panels.

A fixed-height row with a left-aligned label and a right-aligned control widget.

Design spec reference: Section 6 (settings layout).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from systemstt.ui.theme import TOKENS


class SettingRow(QWidget):
    """A single settings row: label on the left, control on the right.

    Attributes:
        label: The label widget (read-only access).
        control: The control widget passed at construction (read-only access).

    Args:
        label_text: Text for the left-side label.
        control: Any QWidget to place on the right side.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        label_text: str,
        control: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(TOKENS.setting_row_height)

        self.label = QLabel(label_text)
        self.label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        self.label.setStyleSheet(
            f"font-size: {TOKENS.text_base}px; background: transparent;",
        )

        self.control = control

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.control)
