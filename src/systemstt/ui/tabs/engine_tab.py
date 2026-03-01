"""
EngineTab — STT engine settings tab.

Displays engine selection radio buttons, cloud API settings,
and local Whisper settings with section dimming for the inactive engine.

Design spec reference: Section 6 (engine settings).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from systemstt.config.models import EngineType, WhisperModelSize
from systemstt.ui.theme import TOKENS
from systemstt.ui.widgets import SectionHeader, SettingRow

if TYPE_CHECKING:
    from systemstt.config.models import SettingsModel

logger = logging.getLogger(__name__)

_MODEL_SIZES = [size.value for size in WhisperModelSize]


class EngineTab(QWidget):
    """STT engine settings tab.

    Displays:
    - Engine selection: Cloud API / Local Whisper radio buttons
    - Cloud API settings: provider, API key (masked), status
    - Local Whisper settings: model size, status, download + progress

    Inactive engine section is dimmed and disabled.

    Signals:
        settings_changed(str, object): Emitted when a setting changes.
        engine_changed(str): Emitted when the engine type changes.
        api_key_changed(str): Emitted when the API key changes.
        model_download_requested(str): Emitted when model download is requested.
    """

    settings_changed = Signal(str, object)
    engine_changed = Signal(str)
    api_key_changed = Signal(str)
    model_download_requested = Signal(str)

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

        # --- STT ENGINE section ---
        layout.addWidget(SectionHeader("STT Engine", is_first=True))

        self._cloud_radio = QRadioButton("Cloud API")
        self._local_radio = QRadioButton("Local Whisper")
        self._cloud_radio.toggled.connect(self._on_engine_toggled)

        layout.addWidget(self._cloud_radio)
        layout.addWidget(self._local_radio)

        # --- CLOUD API SETTINGS section ---
        self._cloud_header = SectionHeader("Cloud API Settings")
        layout.addWidget(self._cloud_header)

        self._cloud_section = QWidget()
        cloud_layout = QVBoxLayout(self._cloud_section)
        cloud_layout.setContentsMargins(0, 0, 0, 0)
        cloud_layout.setSpacing(0)

        self._provider_combo = QComboBox()
        self._provider_combo.addItem("OpenAI")
        cloud_layout.addWidget(SettingRow("API Provider", self._provider_combo))

        # API key row: QLineEdit + reveal button in a container
        api_key_container = QWidget()
        api_key_container.setStyleSheet("background: transparent;")
        api_key_layout = QHBoxLayout(api_key_container)
        api_key_layout.setContentsMargins(0, 0, 0, 0)
        api_key_layout.setSpacing(4)

        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("sk-...")
        self._api_key_edit.editingFinished.connect(self._on_api_key_finished)
        api_key_layout.addWidget(self._api_key_edit)

        self._reveal_btn = QPushButton("\u25cf")
        self._reveal_btn.setFixedSize(28, 28)
        self._reveal_btn.setProperty("class", "secondary")
        self._reveal_btn.setToolTip("Show/hide API key")
        self._reveal_btn.clicked.connect(self._on_reveal_clicked)
        api_key_layout.addWidget(self._reveal_btn)

        cloud_layout.addWidget(SettingRow("API Key", api_key_container))

        self._api_status_label = QLabel("")
        self._api_status_label.setStyleSheet(
            f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_sm}px;"
            " background: transparent;"
        )
        cloud_layout.addWidget(SettingRow("Status", self._api_status_label))

        layout.addWidget(self._cloud_section)

        # --- LOCAL WHISPER SETTINGS section ---
        self._local_header = SectionHeader("Local Whisper Settings")
        layout.addWidget(self._local_header)

        self._local_section = QWidget()
        local_layout = QVBoxLayout(self._local_section)
        local_layout.setContentsMargins(0, 0, 0, 0)
        local_layout.setSpacing(0)

        self._model_size_combo = QComboBox()
        for size in _MODEL_SIZES:
            self._model_size_combo.addItem(size.capitalize(), size)
        self._model_size_combo.currentIndexChanged.connect(self._on_model_size_changed)
        local_layout.addWidget(SettingRow("Model Size", self._model_size_combo))

        perf_note = QLabel("Larger models are more accurate but require more RAM and CPU.")
        perf_note.setStyleSheet(
            f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_xs}px;"
            " background: transparent;"
        )
        perf_note.setWordWrap(True)
        local_layout.addWidget(perf_note)

        self._model_status_label = QLabel("")
        self._model_status_label.setStyleSheet(
            f"color: {TOKENS.text_secondary}; font-size: {TOKENS.text_sm}px;"
            " background: transparent;"
        )
        local_layout.addWidget(SettingRow("Model Status", self._model_status_label))

        self._download_btn = QPushButton("Download Model")
        self._download_btn.clicked.connect(self._on_download_clicked)
        local_layout.addWidget(self._download_btn)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        local_layout.addWidget(self._progress_bar)

        layout.addWidget(self._local_section)

        layout.addStretch()

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    def _apply_initial_state(self) -> None:
        """Set initial control values without emitting signals."""
        self._updating = True
        try:
            is_cloud = self._settings.engine == EngineType.CLOUD_API
            self._cloud_radio.setChecked(is_cloud)
            self._local_radio.setChecked(not is_cloud)
            self._update_section_enabled(is_cloud)
            self._set_model_size_from_settings(self._settings)
        finally:
            self._updating = False

    def _set_model_size_from_settings(self, settings: SettingsModel) -> None:
        """Select the model size combo item matching the settings."""
        target = settings.local_model_size.value
        for i in range(self._model_size_combo.count()):
            if self._model_size_combo.itemData(i) == target:
                self._model_size_combo.setCurrentIndex(i)
                return

    def _update_section_enabled(self, cloud_active: bool) -> None:
        """Enable/disable cloud and local sections based on active engine."""
        self._cloud_section.setEnabled(cloud_active)
        self._local_section.setEnabled(not cloud_active)

        cloud_color = TOKENS.text_primary if cloud_active else TOKENS.text_disabled
        local_color = TOKENS.text_primary if not cloud_active else TOKENS.text_disabled

        self._cloud_header.setStyleSheet(f"color: {cloud_color}; background: transparent;")
        self._local_header.setStyleSheet(f"color: {local_color}; background: transparent;")

    # --- Signal handlers ---

    def _on_engine_toggled(self, cloud_checked: bool) -> None:
        self._update_section_enabled(cloud_checked)
        if self._updating:
            return
        engine = EngineType.CLOUD_API if cloud_checked else EngineType.LOCAL_WHISPER
        self.engine_changed.emit(engine.value)

    def _on_api_key_finished(self) -> None:
        if not self._updating:
            self.api_key_changed.emit(self._api_key_edit.text())

    def _on_reveal_clicked(self) -> None:
        if self._api_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def _on_model_size_changed(self, index: int) -> None:
        if self._updating:
            return
        size = self._model_size_combo.itemData(index)
        if size is not None:
            self.settings_changed.emit("local_model_size", size)

    def _on_download_clicked(self) -> None:
        size = self._model_size_combo.currentData()
        if size is not None:
            self.model_download_requested.emit(str(size))

    # --- Public API ---

    def update_from_settings(self, settings: SettingsModel) -> None:
        """Refresh all controls from the settings model."""
        self._updating = True
        try:
            self._settings = settings
            is_cloud = settings.engine == EngineType.CLOUD_API
            self._cloud_radio.setChecked(is_cloud)
            self._local_radio.setChecked(not is_cloud)
            self._update_section_enabled(is_cloud)
            self._set_model_size_from_settings(settings)
        finally:
            self._updating = False

    def update_api_status(self, status: str) -> None:
        """Update the API connection status indicator."""
        self._api_status_label.setText(status)

    def update_model_status(self, status: str) -> None:
        """Update the local model status indicator."""
        self._model_status_label.setText(status)

    def update_model_download_progress(self, progress: float) -> None:
        """Update the model download progress bar (0.0 to 1.0)."""
        clamped = max(0.0, min(1.0, progress))
        self._progress_bar.setValue(int(clamped * 100))
