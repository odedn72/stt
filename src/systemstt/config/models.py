"""
Settings model for SystemSTT.

Pydantic model that defines all configurable settings with defaults
matching the design spec section 8.2. Supports forward/backward
compatibility by ignoring unknown fields and using defaults for
missing fields.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class EngineType(StrEnum):
    """STT engine type selection."""

    CLOUD_API = "cloud_api"
    LOCAL_WHISPER = "local_whisper"


class WhisperModelSize(StrEnum):
    """Local Whisper model sizes."""

    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class SettingsModel(BaseModel):
    """All user-configurable settings for SystemSTT.

    Default values match the design spec section 8.2.
    Unknown keys are silently ignored for forward compatibility.
    """

    model_config = ConfigDict(
        extra="ignore",
        use_enum_values=False,
    )

    # Hotkey settings
    hotkey_key: str = "space"
    hotkey_modifiers: list[str] = ["option"]

    # Application behavior
    start_on_login: bool = False
    show_in_dock: bool = False
    show_status_pill: bool = True
    show_live_preview: bool = False

    # Pill position (None = default position)
    pill_position_x: int | None = None
    pill_position_y: int | None = None

    # Engine selection
    engine: EngineType = EngineType.CLOUD_API

    # Cloud API settings
    cloud_api_provider: str = "openai"
    cloud_api_base_url: str = "https://api.openai.com/v1"
    cloud_api_model: str = "whisper-1"

    # Local engine settings
    local_model_size: WhisperModelSize = WhisperModelSize.MEDIUM
    local_compute_type: str = "int8"

    # Audio settings
    audio_device_id: int | None = None
    audio_device_name: str | None = None

    # Voice commands
    voice_commands_enabled: bool = True

    # Updates
    check_for_updates: bool = False
