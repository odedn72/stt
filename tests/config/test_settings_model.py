# TDD: Written from spec 08-configuration.md
"""
Tests for SettingsModel — pydantic model for all app settings.

Tests verify:
- Default values match design spec section 8.2
- Serialization round-trip (model -> JSON -> model)
- Validation (invalid values rejected)
- Forward compatibility (unknown keys ignored, missing keys use defaults)
- Enum values for engine and model size
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from systemstt.config.models import SettingsModel, EngineType, WhisperModelSize


# ---------------------------------------------------------------------------
# Default values tests (design spec section 8.2)
# ---------------------------------------------------------------------------

class TestSettingsModelDefaults:
    """Tests that default values match the design spec."""

    def test_default_engine_is_cloud_api(self) -> None:
        settings = SettingsModel()
        assert settings.engine == EngineType.CLOUD_API

    def test_default_hotkey_key_is_space(self) -> None:
        settings = SettingsModel()
        assert settings.hotkey_key == "space"

    def test_default_hotkey_modifiers_is_option(self) -> None:
        settings = SettingsModel()
        assert settings.hotkey_modifiers == ["option"]

    def test_default_start_on_login_is_false(self) -> None:
        settings = SettingsModel()
        assert settings.start_on_login is False

    def test_default_show_in_dock_is_false(self) -> None:
        settings = SettingsModel()
        assert settings.show_in_dock is False

    def test_default_show_status_pill_is_true(self) -> None:
        settings = SettingsModel()
        assert settings.show_status_pill is True

    def test_default_show_live_preview_is_false(self) -> None:
        settings = SettingsModel()
        assert settings.show_live_preview is False

    def test_default_pill_position_is_none(self) -> None:
        settings = SettingsModel()
        assert settings.pill_position_x is None
        assert settings.pill_position_y is None

    def test_default_cloud_api_provider_is_openai(self) -> None:
        settings = SettingsModel()
        assert settings.cloud_api_provider == "openai"

    def test_default_cloud_api_base_url(self) -> None:
        settings = SettingsModel()
        assert settings.cloud_api_base_url == "https://api.openai.com/v1"

    def test_default_cloud_api_model_is_whisper1(self) -> None:
        settings = SettingsModel()
        assert settings.cloud_api_model == "whisper-1"

    def test_default_local_model_size_is_medium(self) -> None:
        settings = SettingsModel()
        assert settings.local_model_size == WhisperModelSize.MEDIUM

    def test_default_local_compute_type_is_int8(self) -> None:
        settings = SettingsModel()
        assert settings.local_compute_type == "int8"

    def test_default_audio_device_id_is_none(self) -> None:
        settings = SettingsModel()
        assert settings.audio_device_id is None

    def test_default_voice_commands_enabled_is_true(self) -> None:
        settings = SettingsModel()
        assert settings.voice_commands_enabled is True

    def test_default_check_for_updates_is_false(self) -> None:
        settings = SettingsModel()
        assert settings.check_for_updates is False


# ---------------------------------------------------------------------------
# Enum value tests
# ---------------------------------------------------------------------------

class TestSettingsModelEnums:
    """Tests for enum fields."""

    def test_engine_type_cloud_api(self) -> None:
        settings = SettingsModel(engine=EngineType.CLOUD_API)
        assert settings.engine == EngineType.CLOUD_API

    def test_engine_type_local_whisper(self) -> None:
        settings = SettingsModel(engine=EngineType.LOCAL_WHISPER)
        assert settings.engine == EngineType.LOCAL_WHISPER

    def test_engine_type_from_string(self) -> None:
        settings = SettingsModel(engine="cloud_api")
        assert settings.engine == EngineType.CLOUD_API

    def test_model_size_all_values(self) -> None:
        for size in WhisperModelSize:
            settings = SettingsModel(local_model_size=size)
            assert settings.local_model_size == size

    def test_model_size_from_string(self) -> None:
        settings = SettingsModel(local_model_size="small")
        assert settings.local_model_size == WhisperModelSize.SMALL


# ---------------------------------------------------------------------------
# Serialization round-trip tests
# ---------------------------------------------------------------------------

class TestSettingsModelSerialization:
    """Tests for JSON serialization and deserialization."""

    def test_model_to_json_roundtrip(self) -> None:
        original = SettingsModel()
        json_str = original.model_dump_json(indent=2)
        restored = SettingsModel.model_validate_json(json_str)
        assert restored == original

    def test_model_to_dict_roundtrip(self) -> None:
        original = SettingsModel()
        data = original.model_dump()
        restored = SettingsModel(**data)
        assert restored == original

    def test_custom_values_roundtrip(self) -> None:
        original = SettingsModel(
            engine=EngineType.LOCAL_WHISPER,
            local_model_size=WhisperModelSize.SMALL,
            hotkey_key="f5",
            hotkey_modifiers=["command", "shift"],
            show_live_preview=True,
            audio_device_id=3,
            audio_device_name="USB Mic",
        )
        json_str = original.model_dump_json()
        restored = SettingsModel.model_validate_json(json_str)
        assert restored.engine == EngineType.LOCAL_WHISPER
        assert restored.local_model_size == WhisperModelSize.SMALL
        assert restored.hotkey_key == "f5"
        assert restored.audio_device_id == 3

    def test_json_output_matches_expected_format(
        self, default_settings_dict: dict[str, Any]
    ) -> None:
        """Verify JSON matches the format from spec section 3.1."""
        settings = SettingsModel()
        data = settings.model_dump()
        # Check key fields match
        assert data["hotkey_key"] == "space"
        assert data["engine"] in ("cloud_api", EngineType.CLOUD_API)
        assert data["voice_commands_enabled"] is True


# ---------------------------------------------------------------------------
# Forward compatibility tests
# ---------------------------------------------------------------------------

class TestSettingsModelForwardCompatibility:
    """Tests for handling unknown/missing keys (spec section 6.5)."""

    def test_unknown_keys_ignored(self) -> None:
        """Unknown keys in the JSON should be silently ignored."""
        data = {
            "engine": "cloud_api",
            "unknown_future_field": True,
            "another_new_field": 42,
        }
        settings = SettingsModel(**data)
        assert settings.engine == EngineType.CLOUD_API

    def test_missing_keys_use_defaults(self) -> None:
        """Missing keys should use default values."""
        data = {"engine": "local_whisper"}
        settings = SettingsModel(**data)
        assert settings.engine == EngineType.LOCAL_WHISPER
        assert settings.hotkey_key == "space"  # default
        assert settings.show_status_pill is True  # default

    def test_partial_settings_dict(
        self, partial_settings_dict: dict[str, Any]
    ) -> None:
        settings = SettingsModel(**partial_settings_dict)
        assert settings.engine == EngineType.LOCAL_WHISPER
        assert settings.local_model_size == WhisperModelSize.SMALL
        # All other fields should be defaults
        assert settings.show_status_pill is True


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestSettingsModelValidation:
    """Tests for input validation."""

    def test_invalid_engine_type_rejected(self) -> None:
        with pytest.raises(Exception):  # pydantic ValidationError
            SettingsModel(engine="invalid_engine")

    def test_invalid_model_size_rejected(self) -> None:
        with pytest.raises(Exception):
            SettingsModel(local_model_size="super_large")

    def test_pill_position_accepts_integers(self) -> None:
        settings = SettingsModel(pill_position_x=100, pill_position_y=200)
        assert settings.pill_position_x == 100
        assert settings.pill_position_y == 200

    def test_pill_position_accepts_none(self) -> None:
        settings = SettingsModel(pill_position_x=None, pill_position_y=None)
        assert settings.pill_position_x is None

    def test_hotkey_modifiers_is_list_of_strings(self) -> None:
        settings = SettingsModel(hotkey_modifiers=["command", "shift"])
        assert settings.hotkey_modifiers == ["command", "shift"]
