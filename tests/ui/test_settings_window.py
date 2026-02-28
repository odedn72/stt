# TDD: Written from spec 07-ui-layer.md
"""
Tests for SettingsWindow — tabbed settings dialog.

Design spec references: Section 6 (settings window layout and tabs).

Tests verify:
- Window properties (size, tabs)
- Tab switching
- Settings population from model
- Signal definitions
- Audio device list updates
- Audio level meter updates
- API status and model status updates
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from systemstt.ui.settings_window import SettingsWindow
from systemstt.config.models import SettingsModel, EngineType, WhisperModelSize


# ---------------------------------------------------------------------------
# Window creation tests
# ---------------------------------------------------------------------------

class TestSettingsWindowCreation:
    """Tests for settings window creation."""

    def test_window_creates_without_error(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        assert window is not None

    def test_window_is_qwidget(self) -> None:
        from PySide6.QtWidgets import QWidget
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        assert isinstance(window, QWidget)


# ---------------------------------------------------------------------------
# Tab management tests
# ---------------------------------------------------------------------------

class TestSettingsWindowTabs:
    """Tests for tab switching behavior."""

    def test_show_general_tab(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.show_tab("general")

    def test_show_engine_tab(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.show_tab("engine")

    def test_show_audio_tab(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.show_tab("audio")

    def test_show_commands_tab(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.show_tab("commands")


# ---------------------------------------------------------------------------
# Settings population tests
# ---------------------------------------------------------------------------

class TestSettingsWindowPopulation:
    """Tests for populating controls from the settings model."""

    def test_update_from_settings(self) -> None:
        settings = SettingsModel(
            engine=EngineType.LOCAL_WHISPER,
            local_model_size=WhisperModelSize.SMALL,
            show_live_preview=True,
        )
        window = SettingsWindow(settings=SettingsModel())
        window.update_from_settings(settings)
        # Should not raise

    def test_update_from_default_settings(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.update_from_settings(settings)


# ---------------------------------------------------------------------------
# Status indicator tests
# ---------------------------------------------------------------------------

class TestSettingsWindowStatusIndicators:
    """Tests for API and model status indicators."""

    def test_update_api_status_connected(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.update_api_status("Connected")

    def test_update_api_status_invalid_key(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.update_api_status("Invalid key")

    def test_update_api_status_unreachable(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.update_api_status("Unreachable")

    def test_update_model_status_loaded(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.update_model_status("Loaded (medium)")

    def test_update_model_status_not_downloaded(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.update_model_status("Not downloaded")

    def test_update_model_download_progress(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.update_model_download_progress(0.0)
        window.update_model_download_progress(0.5)
        window.update_model_download_progress(1.0)


# ---------------------------------------------------------------------------
# Audio device list tests
# ---------------------------------------------------------------------------

class TestSettingsWindowAudioDevices:
    """Tests for audio device dropdown updates."""

    def test_update_audio_devices_with_list(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        # Pass mock AudioDevice objects
        devices = [
            MagicMock(name="Built-in Mic", device_id=0, is_default=True),
            MagicMock(name="USB Mic", device_id=1, is_default=False),
        ]
        window.update_audio_devices(devices)

    def test_update_audio_devices_empty_list(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        window.update_audio_devices([])


# ---------------------------------------------------------------------------
# Audio level meter tests
# ---------------------------------------------------------------------------

class TestSettingsWindowAudioLevel:
    """Tests for the live audio level meter."""

    def test_update_audio_level(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        level = MagicMock(rms_db=-20.0, peak_db=-15.0, level="ok")
        window.update_audio_level(level)


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------

class TestSettingsWindowSignals:
    """Tests that required signals are defined."""

    def test_has_settings_changed_signal(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        assert hasattr(window, "settings_changed")

    def test_has_hotkey_changed_signal(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        assert hasattr(window, "hotkey_changed")

    def test_has_engine_changed_signal(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        assert hasattr(window, "engine_changed")

    def test_has_api_key_changed_signal(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        assert hasattr(window, "api_key_changed")

    def test_has_model_download_signal(self) -> None:
        settings = SettingsModel()
        window = SettingsWindow(settings=settings)
        assert hasattr(window, "model_download_requested")
