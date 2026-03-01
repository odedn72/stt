# TDD: Tests written before implementation
"""
Tests for EngineTab — STT engine settings tab.

Design spec reference: Section 6 (engine settings).

Tests verify:
- Widget creation and structure
- Radio button engine selection
- Cloud API section: provider, API key, status
- Local Whisper section: model size, status, download
- Section dimming for inactive engine
- API key masking and reveal
- Signal emission for engine, API key, model download, settings
- update_api_status, update_model_status, update_model_download_progress
- update_from_settings populates all controls
- Signal guard during programmatic updates
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QWidget,
)

from systemstt.config.models import EngineType, SettingsModel, WhisperModelSize
from systemstt.ui.tabs.engine_tab import EngineTab
from systemstt.ui.widgets import SectionHeader

# ---------------------------------------------------------------------------
# Creation tests
# ---------------------------------------------------------------------------


class TestEngineTabCreation:
    """Tests for EngineTab widget creation."""

    def test_creates_without_error(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert tab is not None

    def test_is_qwidget(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert isinstance(tab, QWidget)


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------


class TestEngineTabStructure:
    """Tests for EngineTab internal widget structure."""

    def test_has_stt_engine_section_header(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        headers = tab.findChildren(SectionHeader)
        assert any("stt engine" in h.text().lower() for h in headers)

    def test_has_cloud_api_section_header(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        headers = tab.findChildren(SectionHeader)
        assert any("cloud api" in h.text().lower() for h in headers)

    def test_has_local_whisper_section_header(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        headers = tab.findChildren(SectionHeader)
        assert any("local whisper" in h.text().lower() for h in headers)

    def test_has_cloud_radio(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert isinstance(tab._cloud_radio, QRadioButton)

    def test_has_local_radio(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert isinstance(tab._local_radio, QRadioButton)

    def test_has_provider_combo(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert isinstance(tab._provider_combo, QComboBox)

    def test_has_api_key_edit(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert isinstance(tab._api_key_edit, QLineEdit)

    def test_has_api_status_label(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert isinstance(tab._api_status_label, QLabel)

    def test_has_model_size_combo(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert isinstance(tab._model_size_combo, QComboBox)

    def test_has_model_status_label(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert isinstance(tab._model_status_label, QLabel)

    def test_has_download_button(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert isinstance(tab._download_btn, QPushButton)

    def test_has_progress_bar(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert isinstance(tab._progress_bar, QProgressBar)

    def test_has_reveal_button(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert isinstance(tab._reveal_btn, QPushButton)


# ---------------------------------------------------------------------------
# Radio button tests
# ---------------------------------------------------------------------------


class TestEngineTabRadio:
    """Tests for engine radio button selection."""

    def test_default_cloud_api_selected(self) -> None:
        settings = SettingsModel(engine=EngineType.CLOUD_API)
        tab = EngineTab(settings=settings)
        assert tab._cloud_radio.isChecked()
        assert not tab._local_radio.isChecked()

    def test_local_whisper_selected(self) -> None:
        settings = SettingsModel(engine=EngineType.LOCAL_WHISPER)
        tab = EngineTab(settings=settings)
        assert not tab._cloud_radio.isChecked()
        assert tab._local_radio.isChecked()

    def test_switch_to_local_dims_cloud_section(self) -> None:
        settings = SettingsModel(engine=EngineType.CLOUD_API)
        tab = EngineTab(settings=settings)
        tab._local_radio.setChecked(True)
        assert not tab._cloud_section.isEnabled()
        assert tab._local_section.isEnabled()

    def test_switch_to_cloud_dims_local_section(self) -> None:
        settings = SettingsModel(engine=EngineType.LOCAL_WHISPER)
        tab = EngineTab(settings=settings)
        tab._cloud_radio.setChecked(True)
        assert tab._cloud_section.isEnabled()
        assert not tab._local_section.isEnabled()


# ---------------------------------------------------------------------------
# API key tests
# ---------------------------------------------------------------------------


class TestEngineTabApiKey:
    """Tests for the API key field."""

    def test_api_key_masked_by_default(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert tab._api_key_edit.echoMode() == QLineEdit.EchoMode.Password

    def test_reveal_button_toggles_echo_mode(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        tab._reveal_btn.click()
        assert tab._api_key_edit.echoMode() == QLineEdit.EchoMode.Normal
        tab._reveal_btn.click()
        assert tab._api_key_edit.echoMode() == QLineEdit.EchoMode.Password


# ---------------------------------------------------------------------------
# Status update tests
# ---------------------------------------------------------------------------


class TestEngineTabStatus:
    """Tests for status indicator updates."""

    def test_update_api_status(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        tab.update_api_status("Connected")
        assert "Connected" in tab._api_status_label.text()

    def test_update_api_status_invalid(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        tab.update_api_status("Invalid key")
        assert "Invalid key" in tab._api_status_label.text()

    def test_update_model_status(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        tab.update_model_status("Loaded (medium)")
        assert "Loaded (medium)" in tab._model_status_label.text()

    def test_update_model_download_progress_zero(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        tab.update_model_download_progress(0.0)
        assert tab._progress_bar.value() == 0

    def test_update_model_download_progress_half(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        tab.update_model_download_progress(0.5)
        assert tab._progress_bar.value() == 50

    def test_update_model_download_progress_full(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        tab.update_model_download_progress(1.0)
        assert tab._progress_bar.value() == 100

    def test_update_model_download_progress_clamps(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        tab.update_model_download_progress(1.5)
        assert tab._progress_bar.value() == 100


# ---------------------------------------------------------------------------
# Settings population tests
# ---------------------------------------------------------------------------


class TestEngineTabSettings:
    """Tests for update_from_settings."""

    def test_update_from_settings_switches_to_local(self) -> None:
        settings = SettingsModel(engine=EngineType.CLOUD_API)
        tab = EngineTab(settings=settings)
        new_settings = SettingsModel(engine=EngineType.LOCAL_WHISPER)
        tab.update_from_settings(new_settings)
        assert tab._local_radio.isChecked()

    def test_update_from_settings_model_size(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        new_settings = SettingsModel(local_model_size=WhisperModelSize.SMALL)
        tab.update_from_settings(new_settings)
        assert tab._model_size_combo.currentText().lower() == "small"

    def test_update_from_settings_no_signal(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        results: list[object] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        tab.engine_changed.connect(results.append)
        new_settings = SettingsModel(
            engine=EngineType.LOCAL_WHISPER,
            local_model_size=WhisperModelSize.TINY,
        )
        tab.update_from_settings(new_settings)
        assert results == []


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------


class TestEngineTabSignals:
    """Tests for signal emission."""

    def test_engine_change_emits_engine_changed(self) -> None:
        settings = SettingsModel(engine=EngineType.CLOUD_API)
        tab = EngineTab(settings=settings)
        results: list[str] = []
        tab.engine_changed.connect(results.append)
        tab._local_radio.setChecked(True)
        assert results == ["local_whisper"]

    def test_api_key_change_emits_api_key_changed(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        results: list[str] = []
        tab.api_key_changed.connect(results.append)
        tab._api_key_edit.setText("sk-test-key")
        # editingFinished is emitted on focus out / return, not on every keystroke.
        # We test that the signal mechanism is wired by calling the handler directly.
        tab._on_api_key_finished()
        assert len(results) == 1
        assert results[0] == "sk-test-key"

    def test_download_emits_model_download_requested(self) -> None:
        settings = SettingsModel(
            engine=EngineType.LOCAL_WHISPER,
            local_model_size=WhisperModelSize.MEDIUM,
        )
        tab = EngineTab(settings=settings)
        results: list[str] = []
        tab.model_download_requested.connect(results.append)
        tab._download_btn.click()
        assert len(results) == 1
        assert results[0] == "medium"

    def test_model_size_change_emits_settings_changed(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        results: list[tuple[str, object]] = []
        tab.settings_changed.connect(lambda k, v: results.append((k, v)))
        # Change to a different model size
        tab._model_size_combo.setCurrentIndex(0)  # tiny
        assert any(r[0] == "local_model_size" for r in results)

    def test_has_settings_changed_signal(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert hasattr(tab, "settings_changed")

    def test_has_engine_changed_signal(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert hasattr(tab, "engine_changed")

    def test_has_api_key_changed_signal(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert hasattr(tab, "api_key_changed")

    def test_has_model_download_requested_signal(self) -> None:
        settings = SettingsModel()
        tab = EngineTab(settings=settings)
        assert hasattr(tab, "model_download_requested")
