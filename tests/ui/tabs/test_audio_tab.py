# TDD: Tests written before implementation
"""
Tests for AudioTab — audio input settings tab.

Design spec reference: Section 6 (audio settings).

Tests verify:
- Widget creation and structure
- Input device combo box
- Level meter integration
- Helper text presence
- update_audio_devices populates combo
- update_audio_level forwards to meter
- update_from_settings selects correct device
- Signal emission on device change
- Signal guard during programmatic updates
"""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QComboBox, QLabel, QWidget

from systemstt.config.models import SettingsModel
from systemstt.ui.tabs.audio_tab import AudioTab
from systemstt.ui.widgets import LevelMeter, SectionHeader


def _mock_device(device_id: int, name: str, *, is_default: bool) -> MagicMock:
    """Create a mock AudioDevice. MagicMock(name=...) is special, so set after."""
    dev = MagicMock()
    dev.device_id = device_id
    dev.name = name
    dev.is_default = is_default
    return dev


# ---------------------------------------------------------------------------
# Creation tests
# ---------------------------------------------------------------------------


class TestAudioTabCreation:
    """Tests for AudioTab widget creation."""

    def test_creates_without_error(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        assert tab is not None

    def test_is_qwidget(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        assert isinstance(tab, QWidget)


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


class TestAudioTabStructure:
    """Tests for AudioTab internal widget structure."""

    def test_has_input_section_header(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        headers = tab.findChildren(SectionHeader)
        assert any(h.text() == "Input" for h in headers)

    def test_has_device_combo(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        assert isinstance(tab._device_combo, QComboBox)

    def test_has_level_meter(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        assert isinstance(tab._level_meter, LevelMeter)

    def test_has_helper_text(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        labels = tab.findChildren(QLabel)
        assert any("level meter is live" in lbl.text().lower() for lbl in labels)


# ---------------------------------------------------------------------------
# Audio device tests
# ---------------------------------------------------------------------------


class TestAudioTabDevices:
    """Tests for audio device list management."""

    def test_update_audio_devices_populates_combo(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        devices = [
            _mock_device(0, "Built-in Mic", is_default=True),
            _mock_device(1, "USB Mic", is_default=False),
        ]
        tab.update_audio_devices(devices)
        assert tab._device_combo.count() == 2
        assert "Built-in Mic" in tab._device_combo.itemText(0)
        assert "USB Mic" in tab._device_combo.itemText(1)

    def test_update_audio_devices_empty_list(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        tab.update_audio_devices([])
        assert tab._device_combo.count() == 0

    def test_update_audio_devices_marks_default(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        devices = [
            _mock_device(0, "Built-in Mic", is_default=True),
            _mock_device(1, "USB Mic", is_default=False),
        ]
        tab.update_audio_devices(devices)
        assert "(default)" in tab._device_combo.itemText(0).lower()

    def test_update_audio_devices_preserves_selection_by_id(self) -> None:
        settings = SettingsModel(audio_device_id=1)
        tab = AudioTab(settings=settings)
        devices = [
            _mock_device(0, "Built-in Mic", is_default=True),
            _mock_device(1, "USB Mic", is_default=False),
        ]
        tab.update_audio_devices(devices)
        assert tab._device_combo.currentIndex() == 1


# ---------------------------------------------------------------------------
# Audio level tests
# ---------------------------------------------------------------------------


class TestAudioTabLevel:
    """Tests for live audio level updates."""

    def test_update_audio_level(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        level = MagicMock(rms_db=-20.0, peak_db=-15.0, level="ok")
        tab.update_audio_level(level)
        assert tab._level_meter.rms_db == -20.0
        assert tab._level_meter.peak_db == -15.0


# ---------------------------------------------------------------------------
# Settings population tests
# ---------------------------------------------------------------------------


class TestAudioTabSettings:
    """Tests for update_from_settings."""

    def test_update_from_settings_selects_device(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        devices = [
            _mock_device(0, "Built-in Mic", is_default=True),
            _mock_device(1, "USB Mic", is_default=False),
        ]
        tab.update_audio_devices(devices)
        new_settings = SettingsModel(audio_device_id=1)
        tab.update_from_settings(new_settings)
        assert tab._device_combo.currentIndex() == 1

    def test_update_from_settings_no_signal(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        devices = [
            _mock_device(0, "Built-in Mic", is_default=True),
            _mock_device(1, "USB Mic", is_default=False),
        ]
        tab.update_audio_devices(devices)
        results: list[tuple[str, object]] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        new_settings = SettingsModel(audio_device_id=1)
        tab.update_from_settings(new_settings)
        assert results == []


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------


class TestAudioTabSignals:
    """Tests for signal emission."""

    def test_device_change_emits_settings_changed(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        devices = [
            _mock_device(0, "Built-in Mic", is_default=True),
            _mock_device(1, "USB Mic", is_default=False),
        ]
        tab.update_audio_devices(devices)
        results: list[tuple[str, object]] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        tab._device_combo.setCurrentIndex(1)
        assert len(results) == 1
        assert results[0][0] == "audio_device_id"
        assert results[0][1] == 1

    def test_has_settings_changed_signal(self) -> None:
        settings = SettingsModel()
        tab = AudioTab(settings=settings)
        assert hasattr(tab, "settings_changed")
