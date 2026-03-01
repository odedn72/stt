# TDD: Tests written before implementation
"""
Tests for CommandsTab — voice commands settings tab.

Design spec reference: Section 6 (commands settings).

Tests verify:
- Widget creation and structure
- Enable toggle presence and behavior
- Table with 9 rows and 2 columns
- Table is read-only
- Table dimming when commands disabled
- settings_changed signal emission
- update_from_settings populates controls
- Signal guard during programmatic updates
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTableWidget, QWidget

from systemstt.config.models import SettingsModel
from systemstt.ui.tabs.commands_tab import CommandsTab
from systemstt.ui.widgets import SectionHeader, ToggleSwitch

# ---------------------------------------------------------------------------
# Creation tests
# ---------------------------------------------------------------------------


class TestCommandsTabCreation:
    """Tests for CommandsTab widget creation."""

    def test_creates_without_error(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        assert tab is not None

    def test_is_qwidget(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        assert isinstance(tab, QWidget)


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


class TestCommandsTabStructure:
    """Tests for CommandsTab internal widget structure."""

    def test_has_voice_commands_section_header(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        headers = tab.findChildren(SectionHeader)
        assert any("voice commands" in h.text().lower() for h in headers)

    def test_has_enable_toggle(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        assert isinstance(tab._enable_toggle, ToggleSwitch)

    def test_has_command_table(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        assert isinstance(tab._table, QTableWidget)

    def test_has_note_label(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        labels = tab.findChildren(QLabel)
        assert any("english-only" in lbl.text().lower() for lbl in labels)


# ---------------------------------------------------------------------------
# Table tests
# ---------------------------------------------------------------------------


class TestCommandsTabTable:
    """Tests for the voice commands table."""

    def test_table_has_9_rows(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        assert tab._table.rowCount() == 9

    def test_table_has_2_columns(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        assert tab._table.columnCount() == 2

    def test_table_headers(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        assert tab._table.horizontalHeaderItem(0).text() == "Trigger Phrase"
        assert tab._table.horizontalHeaderItem(1).text() == "Action"

    def test_table_is_read_only(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        for row in range(tab._table.rowCount()):
            for col in range(tab._table.columnCount()):
                item = tab._table.item(row, col)
                assert item is not None
                assert not (item.flags() & Qt.ItemFlag.ItemIsEditable)

    def test_table_first_row_has_content(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        # First command: "delete last word"
        trigger = tab._table.item(0, 0)
        action = tab._table.item(0, 1)
        assert trigger is not None
        assert action is not None
        assert len(trigger.text()) > 0
        assert len(action.text()) > 0


# ---------------------------------------------------------------------------
# Toggle behavior tests
# ---------------------------------------------------------------------------


class TestCommandsTabToggle:
    """Tests for the enable/disable toggle."""

    def test_default_enabled(self) -> None:
        settings = SettingsModel(voice_commands_enabled=True)
        tab = CommandsTab(settings=settings)
        assert tab._enable_toggle.is_checked() is True

    def test_disabled_state(self) -> None:
        settings = SettingsModel(voice_commands_enabled=False)
        tab = CommandsTab(settings=settings)
        assert tab._enable_toggle.is_checked() is False

    def test_disable_dims_table(self) -> None:
        settings = SettingsModel(voice_commands_enabled=True)
        tab = CommandsTab(settings=settings)
        tab._enable_toggle.set_checked(False)
        assert not tab._table.isEnabled()

    def test_enable_undims_table(self) -> None:
        settings = SettingsModel(voice_commands_enabled=False)
        tab = CommandsTab(settings=settings)
        tab._enable_toggle.set_checked(True)
        assert tab._table.isEnabled()


# ---------------------------------------------------------------------------
# Settings population tests
# ---------------------------------------------------------------------------


class TestCommandsTabSettings:
    """Tests for update_from_settings."""

    def test_update_from_settings_enables(self) -> None:
        settings = SettingsModel(voice_commands_enabled=False)
        tab = CommandsTab(settings=settings)
        new_settings = SettingsModel(voice_commands_enabled=True)
        tab.update_from_settings(new_settings)
        assert tab._enable_toggle.is_checked() is True

    def test_update_from_settings_disables(self) -> None:
        settings = SettingsModel(voice_commands_enabled=True)
        tab = CommandsTab(settings=settings)
        new_settings = SettingsModel(voice_commands_enabled=False)
        tab.update_from_settings(new_settings)
        assert tab._enable_toggle.is_checked() is False

    def test_update_from_settings_no_signal(self) -> None:
        settings = SettingsModel(voice_commands_enabled=True)
        tab = CommandsTab(settings=settings)
        results: list[tuple[str, object]] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        new_settings = SettingsModel(voice_commands_enabled=False)
        tab.update_from_settings(new_settings)
        assert results == []


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------


class TestCommandsTabSignals:
    """Tests for signal emission."""

    def test_toggle_emits_settings_changed(self) -> None:
        settings = SettingsModel(voice_commands_enabled=True)
        tab = CommandsTab(settings=settings)
        results: list[tuple[str, object]] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        tab._enable_toggle.set_checked(False)
        assert len(results) == 1
        assert results[0] == ("voice_commands_enabled", False)

    def test_has_settings_changed_signal(self) -> None:
        settings = SettingsModel()
        tab = CommandsTab(settings=settings)
        assert hasattr(tab, "settings_changed")
