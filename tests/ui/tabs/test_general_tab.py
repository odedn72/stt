# TDD: Tests written before implementation
"""
Tests for GeneralTab — general application settings tab.

Design spec reference: Section 6 (general settings).

Tests verify:
- Widget creation and structure
- Section headers (Startup, Floating Indicator, Application)
- Hotkey combo box
- Toggle switches for all boolean settings
- Reset pill position button
- Signal emission for settings, hotkey, and pill reset
- update_from_settings populates all controls
- Signal guard during programmatic updates
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QPushButton, QWidget

from systemstt.config.models import SettingsModel
from systemstt.ui.tabs.general_tab import GeneralTab
from systemstt.ui.widgets import SectionHeader, ToggleSwitch

# ---------------------------------------------------------------------------
# Creation tests
# ---------------------------------------------------------------------------


class TestGeneralTabCreation:
    """Tests for GeneralTab widget creation."""

    def test_creates_without_error(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert tab is not None

    def test_is_qwidget(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert isinstance(tab, QWidget)


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


class TestGeneralTabStructure:
    """Tests for GeneralTab internal widget structure."""

    def test_has_startup_section_header(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        headers = tab.findChildren(SectionHeader)
        assert any("startup" in h.text().lower() for h in headers)

    def test_has_floating_indicator_section_header(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        headers = tab.findChildren(SectionHeader)
        assert any("floating indicator" in h.text().lower() for h in headers)

    def test_has_application_section_header(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        headers = tab.findChildren(SectionHeader)
        assert any("application" in h.text().lower() for h in headers)

    def test_has_hotkey_combo(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert isinstance(tab._hotkey_combo, QComboBox)

    def test_has_start_on_login_toggle(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert isinstance(tab._start_on_login_toggle, ToggleSwitch)

    def test_has_show_in_dock_toggle(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert isinstance(tab._show_in_dock_toggle, ToggleSwitch)

    def test_has_show_pill_toggle(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert isinstance(tab._show_pill_toggle, ToggleSwitch)

    def test_has_show_preview_toggle(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert isinstance(tab._show_preview_toggle, ToggleSwitch)

    def test_has_check_updates_toggle(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert isinstance(tab._check_updates_toggle, ToggleSwitch)

    def test_has_reset_pill_button(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert isinstance(tab._reset_pill_btn, QPushButton)


# ---------------------------------------------------------------------------
# Initial state tests
# ---------------------------------------------------------------------------


class TestGeneralTabInitialState:
    """Tests for initial control values from settings."""

    def test_default_start_on_login(self) -> None:
        settings = SettingsModel(start_on_login=False)
        tab = GeneralTab(settings=settings)
        assert tab._start_on_login_toggle.is_checked() is False

    def test_enabled_start_on_login(self) -> None:
        settings = SettingsModel(start_on_login=True)
        tab = GeneralTab(settings=settings)
        assert tab._start_on_login_toggle.is_checked() is True

    def test_default_show_in_dock(self) -> None:
        settings = SettingsModel(show_in_dock=False)
        tab = GeneralTab(settings=settings)
        assert tab._show_in_dock_toggle.is_checked() is False

    def test_default_show_pill(self) -> None:
        settings = SettingsModel(show_status_pill=True)
        tab = GeneralTab(settings=settings)
        assert tab._show_pill_toggle.is_checked() is True

    def test_default_show_preview(self) -> None:
        settings = SettingsModel(show_live_preview=False)
        tab = GeneralTab(settings=settings)
        assert tab._show_preview_toggle.is_checked() is False

    def test_default_check_updates(self) -> None:
        settings = SettingsModel(check_for_updates=False)
        tab = GeneralTab(settings=settings)
        assert tab._check_updates_toggle.is_checked() is False

    def test_hotkey_combo_has_options(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert tab._hotkey_combo.count() > 0


# ---------------------------------------------------------------------------
# Settings population tests
# ---------------------------------------------------------------------------


class TestGeneralTabSettings:
    """Tests for update_from_settings."""

    def test_update_from_settings_toggles(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        new_settings = SettingsModel(
            start_on_login=True,
            show_in_dock=True,
            show_status_pill=False,
            show_live_preview=True,
            check_for_updates=True,
        )
        tab.update_from_settings(new_settings)
        assert tab._start_on_login_toggle.is_checked() is True
        assert tab._show_in_dock_toggle.is_checked() is True
        assert tab._show_pill_toggle.is_checked() is False
        assert tab._show_preview_toggle.is_checked() is True
        assert tab._check_updates_toggle.is_checked() is True

    def test_update_from_settings_no_signal(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        results: list[tuple[str, object]] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        new_settings = SettingsModel(start_on_login=True, show_in_dock=True)
        tab.update_from_settings(new_settings)
        assert results == []


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------


class TestGeneralTabSignals:
    """Tests for signal emission."""

    def test_start_on_login_emits_settings_changed(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        results: list[tuple[str, object]] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        tab._start_on_login_toggle.set_checked(True)
        assert len(results) == 1
        assert results[0] == ("start_on_login", True)

    def test_show_in_dock_emits_settings_changed(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        results: list[tuple[str, object]] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        tab._show_in_dock_toggle.set_checked(True)
        assert len(results) == 1
        assert results[0] == ("show_in_dock", True)

    def test_show_pill_emits_settings_changed(self) -> None:
        settings = SettingsModel(show_status_pill=True)
        tab = GeneralTab(settings=settings)
        results: list[tuple[str, object]] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        tab._show_pill_toggle.set_checked(False)
        assert len(results) == 1
        assert results[0] == ("show_status_pill", False)

    def test_show_preview_emits_settings_changed(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        results: list[tuple[str, object]] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        tab._show_preview_toggle.set_checked(True)
        assert len(results) == 1
        assert results[0] == ("show_live_preview", True)

    def test_check_updates_emits_settings_changed(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        results: list[tuple[str, object]] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        tab._check_updates_toggle.set_checked(True)
        assert len(results) == 1
        assert results[0] == ("check_for_updates", True)

    def test_hotkey_change_emits_hotkey_changed(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        results: list[object] = []
        tab.hotkey_changed.connect(results.append)
        # Change to a different hotkey option
        if tab._hotkey_combo.count() > 1:
            tab._hotkey_combo.setCurrentIndex(1)
            assert len(results) == 1

    def test_reset_pill_emits_signal(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        results: list[bool] = []
        tab.pill_position_reset.connect(lambda: results.append(True))
        tab._reset_pill_btn.click()
        assert len(results) == 1

    def test_has_settings_changed_signal(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert hasattr(tab, "settings_changed")

    def test_has_hotkey_changed_signal(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert hasattr(tab, "hotkey_changed")

    def test_has_pill_position_reset_signal(self) -> None:
        settings = SettingsModel()
        tab = GeneralTab(settings=settings)
        assert hasattr(tab, "pill_position_reset")
