"""
GeneralTab — general application settings tab.

Displays startup, floating indicator, and application settings
with hotkey selection, toggle switches, and reset button.

Design spec reference: Section 6 (general settings).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QPushButton, QVBoxLayout, QWidget

from systemstt.ui.theme import TOKENS
from systemstt.ui.widgets import SectionHeader, SettingRow, ToggleSwitch

if TYPE_CHECKING:
    from systemstt.config.models import SettingsModel

logger = logging.getLogger(__name__)

# Hotkey options: (display_text, key, modifiers)
_HOTKEY_OPTIONS: list[tuple[str, str, list[str]]] = [
    ("\u2325Space", "space", ["option"]),
    ("\u2303Space", "space", ["control"]),
    ("\u2318\u21e7Space", "space", ["command", "shift"]),
    ("\u2325\u21e7S", "s", ["option", "shift"]),
]


class GeneralTab(QWidget):
    """General application settings tab.

    Displays:
    - Startup: hotkey, start on login, show in dock
    - Floating Indicator: show pill, show preview, reset position
    - Application: check for updates

    Signals:
        settings_changed(str, object): Emitted when a toggle setting changes.
        hotkey_changed(object): Emitted when the hotkey binding changes.
        pill_position_reset(): Emitted when reset pill position is clicked.
    """

    settings_changed = Signal(str, object)
    hotkey_changed = Signal(object)
    pill_position_reset = Signal()

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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 16)
        layout.setSpacing(0)

        self.setStyleSheet(f"background-color: {TOKENS.bg_elevated};")

        # --- STARTUP section ---
        layout.addWidget(SectionHeader("Startup", is_first=True))

        self._hotkey_combo = QComboBox()
        for display_text, _key, _mods in _HOTKEY_OPTIONS:
            self._hotkey_combo.addItem(display_text)
        self._hotkey_combo.currentIndexChanged.connect(self._on_hotkey_changed)
        layout.addWidget(SettingRow("Global Hotkey", self._hotkey_combo))

        self._start_on_login_toggle = ToggleSwitch()
        self._start_on_login_toggle.toggled.connect(lambda v: self._on_toggle("start_on_login", v))
        layout.addWidget(SettingRow("Start on Login", self._start_on_login_toggle))

        self._show_in_dock_toggle = ToggleSwitch()
        self._show_in_dock_toggle.toggled.connect(lambda v: self._on_toggle("show_in_dock", v))
        layout.addWidget(SettingRow("Show in Dock", self._show_in_dock_toggle))

        # --- FLOATING INDICATOR section ---
        layout.addWidget(SectionHeader("Floating Indicator"))

        self._show_pill_toggle = ToggleSwitch()
        self._show_pill_toggle.toggled.connect(lambda v: self._on_toggle("show_status_pill", v))
        layout.addWidget(SettingRow("Show status pill", self._show_pill_toggle))

        self._show_preview_toggle = ToggleSwitch()
        self._show_preview_toggle.toggled.connect(lambda v: self._on_toggle("show_live_preview", v))
        layout.addWidget(SettingRow("Show live preview", self._show_preview_toggle))

        self._reset_pill_btn = QPushButton("Reset pill position")
        self._reset_pill_btn.setProperty("class", "secondary")
        self._reset_pill_btn.clicked.connect(self.pill_position_reset)
        layout.addWidget(self._reset_pill_btn)

        # --- APPLICATION section ---
        layout.addWidget(SectionHeader("Application"))

        self._check_updates_toggle = ToggleSwitch()
        self._check_updates_toggle.toggled.connect(
            lambda v: self._on_toggle("check_for_updates", v)
        )
        layout.addWidget(SettingRow("Check for updates", self._check_updates_toggle))

        layout.addStretch()

    def _apply_initial_state(self) -> None:
        """Set initial control values without emitting signals."""
        self._updating = True
        try:
            self._set_hotkey_from_settings(self._settings)
            self._start_on_login_toggle.set_checked(self._settings.start_on_login)
            self._show_in_dock_toggle.set_checked(self._settings.show_in_dock)
            self._show_pill_toggle.set_checked(self._settings.show_status_pill)
            self._show_preview_toggle.set_checked(self._settings.show_live_preview)
            self._check_updates_toggle.set_checked(self._settings.check_for_updates)
        finally:
            self._updating = False

    def _set_hotkey_from_settings(self, settings: SettingsModel) -> None:
        """Select the hotkey combo item matching the settings."""
        for i, (_display, key, mods) in enumerate(_HOTKEY_OPTIONS):
            if key == settings.hotkey_key and mods == settings.hotkey_modifiers:
                self._hotkey_combo.setCurrentIndex(i)
                return
        # Fallback to first option if no match
        self._hotkey_combo.setCurrentIndex(0)

    # --- Signal handlers ---

    def _on_toggle(self, key: str, value: bool) -> None:
        if not self._updating:
            self.settings_changed.emit(key, value)

    def _on_hotkey_changed(self, index: int) -> None:
        if self._updating:
            return
        if 0 <= index < len(_HOTKEY_OPTIONS):
            _display, key, mods = _HOTKEY_OPTIONS[index]
            self.hotkey_changed.emit({"key": key, "modifiers": mods})

    # --- Public API ---

    def update_from_settings(self, settings: SettingsModel) -> None:
        """Refresh all controls from the settings model."""
        self._updating = True
        try:
            self._settings = settings
            self._set_hotkey_from_settings(settings)
            self._start_on_login_toggle.set_checked(settings.start_on_login)
            self._show_in_dock_toggle.set_checked(settings.show_in_dock)
            self._show_pill_toggle.set_checked(settings.show_status_pill)
            self._show_preview_toggle.set_checked(settings.show_live_preview)
            self._check_updates_toggle.set_checked(settings.check_for_updates)
        finally:
            self._updating = False
