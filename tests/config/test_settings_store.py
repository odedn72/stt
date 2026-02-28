# TDD: Written from spec 08-configuration.md
"""
Tests for SettingsStore — JSON file persistence for settings.

Uses a temp directory for all file operations. Tests verify:
- Load from nonexistent file (returns defaults)
- Load from valid file
- Load from corrupted file (returns defaults)
- Save + load round-trip
- Atomic writes (temp file + rename)
- Parent directory creation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from systemstt.config.store import SettingsStore
from systemstt.config.models import SettingsModel, EngineType, WhisperModelSize
from systemstt.errors import SettingsLoadError


# ---------------------------------------------------------------------------
# Load tests
# ---------------------------------------------------------------------------

class TestSettingsStoreLoad:
    """Tests for loading settings from disk."""

    def test_load_nonexistent_file_returns_defaults(
        self, tmp_settings_path: Path
    ) -> None:
        store = SettingsStore(path=tmp_settings_path)
        settings = store.load()
        assert isinstance(settings, SettingsModel)
        assert settings.engine == EngineType.CLOUD_API  # default

    def test_load_valid_file(
        self, tmp_settings_path: Path, settings_json: str
    ) -> None:
        tmp_settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_settings_path.write_text(settings_json)
        store = SettingsStore(path=tmp_settings_path)
        settings = store.load()
        assert settings.engine == EngineType.CLOUD_API
        assert settings.hotkey_key == "space"

    def test_load_corrupted_file_returns_defaults(
        self, tmp_settings_path: Path, corrupted_settings_json: str
    ) -> None:
        tmp_settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_settings_path.write_text(corrupted_settings_json)
        store = SettingsStore(path=tmp_settings_path)
        settings = store.load()
        # Should return defaults instead of crashing
        assert isinstance(settings, SettingsModel)
        assert settings.engine == EngineType.CLOUD_API

    def test_load_partial_json_uses_defaults_for_missing(
        self, tmp_settings_path: Path
    ) -> None:
        tmp_settings_path.parent.mkdir(parents=True, exist_ok=True)
        partial = {"engine": "local_whisper", "local_model_size": "small"}
        tmp_settings_path.write_text(json.dumps(partial))
        store = SettingsStore(path=tmp_settings_path)
        settings = store.load()
        assert settings.engine == EngineType.LOCAL_WHISPER
        assert settings.local_model_size == WhisperModelSize.SMALL
        assert settings.hotkey_key == "space"  # default for missing field

    def test_load_file_with_unknown_keys_ignores_them(
        self, tmp_settings_path: Path
    ) -> None:
        tmp_settings_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"engine": "cloud_api", "future_field": "value"}
        tmp_settings_path.write_text(json.dumps(data))
        store = SettingsStore(path=tmp_settings_path)
        settings = store.load()
        assert settings.engine == EngineType.CLOUD_API

    def test_load_empty_json_object_returns_defaults(
        self, tmp_settings_path: Path
    ) -> None:
        tmp_settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_settings_path.write_text("{}")
        store = SettingsStore(path=tmp_settings_path)
        settings = store.load()
        assert settings.engine == EngineType.CLOUD_API


# ---------------------------------------------------------------------------
# Save tests
# ---------------------------------------------------------------------------

class TestSettingsStoreSave:
    """Tests for saving settings to disk."""

    def test_save_creates_file(self, tmp_settings_path: Path) -> None:
        store = SettingsStore(path=tmp_settings_path)
        settings = SettingsModel()
        store.save(settings)
        assert tmp_settings_path.exists()

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "a" / "b" / "c" / "settings.json"
        store = SettingsStore(path=deep_path)
        settings = SettingsModel()
        store.save(settings)
        assert deep_path.exists()

    def test_save_writes_valid_json(self, tmp_settings_path: Path) -> None:
        store = SettingsStore(path=tmp_settings_path)
        settings = SettingsModel(engine=EngineType.LOCAL_WHISPER)
        store.save(settings)
        data = json.loads(tmp_settings_path.read_text())
        assert data["engine"] in ("local_whisper", EngineType.LOCAL_WHISPER)

    def test_save_load_roundtrip(self, tmp_settings_path: Path) -> None:
        store = SettingsStore(path=tmp_settings_path)
        original = SettingsModel(
            engine=EngineType.LOCAL_WHISPER,
            local_model_size=WhisperModelSize.SMALL,
            hotkey_key="f5",
            show_live_preview=True,
        )
        store.save(original)
        loaded = store.load()
        assert loaded.engine == EngineType.LOCAL_WHISPER
        assert loaded.local_model_size == WhisperModelSize.SMALL
        assert loaded.hotkey_key == "f5"
        assert loaded.show_live_preview is True

    def test_save_overwrites_existing_file(self, tmp_settings_path: Path) -> None:
        store = SettingsStore(path=tmp_settings_path)
        settings1 = SettingsModel(engine=EngineType.CLOUD_API)
        store.save(settings1)
        settings2 = SettingsModel(engine=EngineType.LOCAL_WHISPER)
        store.save(settings2)
        loaded = store.load()
        assert loaded.engine == EngineType.LOCAL_WHISPER


# ---------------------------------------------------------------------------
# File path property test
# ---------------------------------------------------------------------------

class TestSettingsStoreFilePath:
    """Tests for the file_path property."""

    def test_file_path_returns_configured_path(
        self, tmp_settings_path: Path
    ) -> None:
        store = SettingsStore(path=tmp_settings_path)
        assert store.file_path == tmp_settings_path

    def test_default_path_is_in_home_config(self) -> None:
        store = SettingsStore()
        expected = Path.home() / ".config" / "systemstt" / "settings.json"
        assert store.file_path == expected


# ---------------------------------------------------------------------------
# Atomic write tests
# ---------------------------------------------------------------------------

class TestSettingsStoreAtomicWrite:
    """Tests for atomic file writing behavior."""

    def test_save_does_not_leave_temp_files(self, tmp_settings_path: Path) -> None:
        store = SettingsStore(path=tmp_settings_path)
        settings = SettingsModel()
        store.save(settings)
        # No .tmp files should remain in the directory
        parent = tmp_settings_path.parent
        temp_files = list(parent.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_save_file_is_readable_after_write(self, tmp_settings_path: Path) -> None:
        store = SettingsStore(path=tmp_settings_path)
        settings = SettingsModel()
        store.save(settings)
        content = tmp_settings_path.read_text()
        data = json.loads(content)
        assert "engine" in data


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestSettingsStoreEdgeCases:
    """Edge case tests for settings store."""

    def test_load_json_array_returns_defaults(
        self, tmp_settings_path: Path
    ) -> None:
        """A valid JSON file that is an array (not object) should return defaults."""
        tmp_settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_settings_path.write_text("[1, 2, 3]")
        store = SettingsStore(path=tmp_settings_path)
        settings = store.load()
        # Should gracefully handle and return defaults
        assert isinstance(settings, SettingsModel)

    def test_load_json_null_returns_defaults(
        self, tmp_settings_path: Path
    ) -> None:
        """A JSON null value should return defaults."""
        tmp_settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_settings_path.write_text("null")
        store = SettingsStore(path=tmp_settings_path)
        settings = store.load()
        assert isinstance(settings, SettingsModel)

    def test_save_preserves_unicode_in_json(
        self, tmp_settings_path: Path
    ) -> None:
        """Settings with unicode values should be preserved after save."""
        store = SettingsStore(path=tmp_settings_path)
        settings = SettingsModel(audio_device_name="מיקרופון מובנה")
        store.save(settings)
        loaded = store.load()
        assert loaded.audio_device_name == "מיקרופון מובנה"

    def test_multiple_saves_all_succeed(
        self, tmp_settings_path: Path
    ) -> None:
        """Multiple consecutive saves should all succeed."""
        store = SettingsStore(path=tmp_settings_path)
        for i in range(5):
            settings = SettingsModel(hotkey_key=f"f{i+1}")
            store.save(settings)
        loaded = store.load()
        assert loaded.hotkey_key == "f5"
