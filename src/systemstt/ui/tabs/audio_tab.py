"""
AudioTab — audio input settings tab.

Displays input device selection and a live audio level meter.

Design spec reference: Section 6 (audio settings).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QLabel, QScrollArea, QVBoxLayout, QWidget

from systemstt.ui.theme import TOKENS
from systemstt.ui.widgets import LevelMeter, SectionHeader, SettingRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from systemstt.audio.level_meter import LevelReading
    from systemstt.config.models import SettingsModel

logger = logging.getLogger(__name__)


class AudioTab(QWidget):
    """Audio input settings tab.

    Displays:
    - Input device combo box
    - Live audio level meter
    - Helper text

    Signals:
        settings_changed(str, object): Emitted when audio device changes.
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

        # --- INPUT section ---
        layout.addWidget(SectionHeader("Input", is_first=True))

        self._device_combo = QComboBox()
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        layout.addWidget(SettingRow("Input Device", self._device_combo))

        self._level_meter = LevelMeter()
        layout.addWidget(SettingRow("Input Level", self._level_meter))

        helper = QLabel("The level meter is live when this tab is open.")
        helper.setStyleSheet(
            f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_xs}px;"
            " background: transparent;"
        )
        layout.addWidget(helper)

        layout.addStretch()

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    # --- Signal handlers ---

    def _on_device_changed(self, index: int) -> None:
        if self._updating:
            return
        device_id = self._device_combo.itemData(index)
        if device_id is not None:
            self.settings_changed.emit("audio_device_id", device_id)

    # --- Public API ---

    def update_from_settings(self, settings: SettingsModel) -> None:
        """Refresh controls from the settings model."""
        self._updating = True
        try:
            self._settings = settings
            # Select the device matching settings
            for i in range(self._device_combo.count()):
                if self._device_combo.itemData(i) == settings.audio_device_id:
                    self._device_combo.setCurrentIndex(i)
                    break
        finally:
            self._updating = False

    def update_audio_devices(self, devices: Sequence[object]) -> None:
        """Refresh the audio device dropdown list."""
        self._updating = True
        try:
            self._device_combo.clear()
            for dev in devices:
                label: str = dev.name  # type: ignore[attr-defined]
                if dev.is_default:  # type: ignore[attr-defined]
                    label = f"{label} (Default)"
                self._device_combo.addItem(label, dev.device_id)  # type: ignore[attr-defined]
            # Select the device matching current settings
            for i in range(self._device_combo.count()):
                if self._device_combo.itemData(i) == self._settings.audio_device_id:
                    self._device_combo.setCurrentIndex(i)
                    break
        finally:
            self._updating = False

    def update_audio_level(self, level: LevelReading) -> None:
        """Update the live audio level meter."""
        self._level_meter.set_level(
            rms_db=level.rms_db,
            peak_db=level.peak_db,
        )
        if hasattr(level, "level"):
            self._level_meter.set_status(str(level.level))
