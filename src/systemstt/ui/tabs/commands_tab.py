"""
CommandsTab — voice commands settings tab.

Displays enable toggle and a read-only table of all voice commands
populated from CommandRegistry.

Design spec reference: Section 6 (commands settings).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from systemstt.commands.registry import CommandRegistry
from systemstt.ui.theme import TOKENS
from systemstt.ui.widgets import SectionHeader, SettingRow, ToggleSwitch

if TYPE_CHECKING:
    from systemstt.config.models import SettingsModel

logger = logging.getLogger(__name__)


class CommandsTab(QWidget):
    """Voice commands settings tab.

    Displays:
    - Enable/disable toggle
    - Read-only table of 9 built-in voice commands
    - Note about English-only in v1

    Signals:
        settings_changed(str, object): Emitted when voice commands toggle changes.
    """

    settings_changed = Signal(str, object)

    def __init__(
        self,
        settings: SettingsModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._updating = False

        self._setup_ui()
        self._apply_initial_state()

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {TOKENS.bg_elevated}; border: none; }}"
        )

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 0, 16, 16)
        layout.setSpacing(0)

        content.setStyleSheet(f"background-color: {TOKENS.bg_elevated};")

        # --- VOICE COMMANDS section ---
        layout.addWidget(SectionHeader("Voice Commands", is_first=True))

        self._enable_toggle = ToggleSwitch()
        self._enable_toggle.toggled.connect(self._on_enable_toggled)
        layout.addWidget(SettingRow("Enable voice commands", self._enable_toggle))

        # --- Command table ---
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Trigger Phrase", "Action"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        registry = CommandRegistry()
        commands = registry.commands
        self._table.setRowCount(len(commands))

        for row, cmd in enumerate(commands):
            trigger_item = QTableWidgetItem(", ".join(cmd.trigger_phrases))
            trigger_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, 0, trigger_item)

            action_item = QTableWidgetItem(cmd.display_name)
            action_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._table.setItem(row, 1, action_item)

        layout.addWidget(self._table)

        # --- Note ---
        note = QLabel("Voice commands are English-only in v1.")
        note.setStyleSheet(
            f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_xs}px;"
            " background: transparent;"
        )
        layout.addWidget(note)

        layout.addStretch()

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    def _apply_initial_state(self) -> None:
        """Set initial toggle state without emitting signals."""
        self._updating = True
        try:
            self._enable_toggle.set_checked(self._settings.voice_commands_enabled)
            self._update_table_enabled(self._settings.voice_commands_enabled)
        finally:
            self._updating = False

    def _on_enable_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        self._update_table_enabled(checked)
        self.settings_changed.emit("voice_commands_enabled", checked)

    def _update_table_enabled(self, enabled: bool) -> None:
        """Enable or disable the table, dimming text when disabled."""
        self._table.setEnabled(enabled)
        color = TOKENS.text_primary if enabled else TOKENS.text_disabled
        self._table.setStyleSheet(f"color: {color};")

    # --- Public API ---

    def update_from_settings(self, settings: SettingsModel) -> None:
        """Refresh controls from the settings model."""
        self._updating = True
        try:
            self._settings = settings
            self._enable_toggle.set_checked(settings.voice_commands_enabled)
            self._update_table_enabled(settings.voice_commands_enabled)
        finally:
            self._updating = False
