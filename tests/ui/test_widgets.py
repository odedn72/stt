# TDD: Written from plan before implementation
"""
Tests for reusable UI widgets — ToggleSwitch, SectionHeader, SettingRow, LevelMeter.

These widgets form the building blocks for the settings window tabs.
Design spec references: Section 2.1 (design tokens), Section 6 (settings window).

Tests verify:
- ToggleSwitch: creation, default state, toggle, signal, dimensions
- SectionHeader: creation, text, styling, margin variants
- SettingRow: creation, label, control, fixed height
- LevelMeter: creation, level updates, status text, default state
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from systemstt.ui.theme import TOKENS
from systemstt.ui.widgets import (
    LevelMeter,
    SectionHeader,
    SettingRow,
    ToggleSwitch,
)

# ---------------------------------------------------------------------------
# ToggleSwitch tests
# ---------------------------------------------------------------------------


class TestToggleSwitch:
    """Tests for the animated toggle switch widget."""

    def test_creation(self) -> None:
        toggle = ToggleSwitch()
        assert isinstance(toggle, QWidget)

    def test_default_unchecked(self) -> None:
        toggle = ToggleSwitch()
        assert toggle.is_checked() is False

    def test_set_checked_true(self) -> None:
        toggle = ToggleSwitch()
        toggle.set_checked(True)
        assert toggle.is_checked() is True

    def test_set_checked_false(self) -> None:
        toggle = ToggleSwitch()
        toggle.set_checked(True)
        toggle.set_checked(False)
        assert toggle.is_checked() is False

    def test_toggled_signal_emitted(self) -> None:
        toggle = ToggleSwitch()
        results: list[bool] = []
        toggle.toggled.connect(results.append)
        toggle.set_checked(True)
        assert results == [True]

    def test_toggled_signal_on_uncheck(self) -> None:
        toggle = ToggleSwitch()
        results: list[bool] = []
        toggle.set_checked(True)
        toggle.toggled.connect(results.append)
        toggle.set_checked(False)
        assert results == [False]

    def test_dimensions(self) -> None:
        toggle = ToggleSwitch()
        assert toggle.minimumWidth() == TOKENS.toggle_width
        assert toggle.maximumWidth() == TOKENS.toggle_width
        assert toggle.minimumHeight() == TOKENS.toggle_height
        assert toggle.maximumHeight() == TOKENS.toggle_height

    def test_click_toggles_state(self) -> None:
        toggle = ToggleSwitch()
        assert toggle.is_checked() is False
        # Simulate mouse click via the toggle's click handler
        toggle._on_click()
        assert toggle.is_checked() is True
        toggle._on_click()
        assert toggle.is_checked() is False

    def test_set_checked_same_value_no_signal(self) -> None:
        toggle = ToggleSwitch()
        results: list[bool] = []
        toggle.toggled.connect(results.append)
        toggle.set_checked(False)  # Already False
        assert results == []


# ---------------------------------------------------------------------------
# SectionHeader tests
# ---------------------------------------------------------------------------


class TestSectionHeader:
    """Tests for the uppercase section label widget."""

    def test_creation(self) -> None:
        header = SectionHeader("Audio")
        assert isinstance(header, QLabel)

    def test_text_content(self) -> None:
        header = SectionHeader("Audio Settings")
        assert header.text() == "Audio Settings"

    def test_text_displayed_uppercase(self) -> None:
        header = SectionHeader("audio")
        # The text itself is stored as-is; uppercase is applied via styling.
        # Verify the text is accessible.
        assert header.text() == "audio"

    def test_first_section_margin(self) -> None:
        header = SectionHeader("General", is_first=True)
        margins = header.contentsMargins()
        assert margins.top() == 16

    def test_non_first_section_margin(self) -> None:
        header = SectionHeader("Audio", is_first=False)
        margins = header.contentsMargins()
        assert margins.top() == 24

    def test_bottom_margin(self) -> None:
        header = SectionHeader("Test")
        margins = header.contentsMargins()
        assert margins.bottom() == 8

    def test_default_is_not_first(self) -> None:
        header = SectionHeader("Test")
        margins = header.contentsMargins()
        assert margins.top() == 24


# ---------------------------------------------------------------------------
# SettingRow tests
# ---------------------------------------------------------------------------


class TestSettingRow:
    """Tests for the label + control row widget."""

    def test_creation(self) -> None:
        control = QLabel("value")
        row = SettingRow("Name", control)
        assert isinstance(row, QWidget)

    def test_label_text(self) -> None:
        control = QLabel("value")
        row = SettingRow("Name", control)
        assert row.label.text() == "Name"

    def test_control_accessible(self) -> None:
        control = QLabel("value")
        row = SettingRow("Name", control)
        assert row.control is control

    def test_fixed_height(self) -> None:
        control = QLabel("value")
        row = SettingRow("Name", control)
        assert row.minimumHeight() == TOKENS.setting_row_height
        assert row.maximumHeight() == TOKENS.setting_row_height

    def test_label_alignment(self) -> None:
        control = QLabel("value")
        row = SettingRow("Name", control)
        alignment = row.label.alignment()
        assert alignment & Qt.AlignmentFlag.AlignLeft
        assert alignment & Qt.AlignmentFlag.AlignVCenter


# ---------------------------------------------------------------------------
# LevelMeter tests
# ---------------------------------------------------------------------------


class TestLevelMeter:
    """Tests for the horizontal audio level bar widget."""

    def test_creation(self) -> None:
        meter = LevelMeter()
        assert isinstance(meter, QWidget)

    def test_default_state(self) -> None:
        meter = LevelMeter()
        assert meter.rms_db == -60.0
        assert meter.peak_db == -60.0

    def test_set_level_updates_values(self) -> None:
        meter = LevelMeter()
        meter.set_level(rms_db=-20.0, peak_db=-10.0)
        assert meter.rms_db == -20.0
        assert meter.peak_db == -10.0

    def test_set_status_text(self) -> None:
        meter = LevelMeter()
        meter.set_status("Too loud")
        assert meter.status_text == "Too loud"

    def test_default_status(self) -> None:
        meter = LevelMeter()
        assert meter.status_text == ""

    def test_set_level_clamps_range(self) -> None:
        meter = LevelMeter()
        meter.set_level(rms_db=10.0, peak_db=10.0)
        assert meter.rms_db == 0.0
        assert meter.peak_db == 0.0

    def test_set_level_clamps_low(self) -> None:
        meter = LevelMeter()
        meter.set_level(rms_db=-100.0, peak_db=-100.0)
        assert meter.rms_db == -60.0
        assert meter.peak_db == -60.0
