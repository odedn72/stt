"""
Shared test fixtures for SystemSTT.

Provides reusable fixtures for settings models, audio data, mock engines,
mock platform services, and Qt application setup.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Audio fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_rate() -> int:
    """Standard sample rate for Whisper."""
    return 16_000


@pytest.fixture
def chunk_duration_ms() -> int:
    """Default chunk duration in milliseconds."""
    return 500


@pytest.fixture
def silence_chunk(sample_rate: int, chunk_duration_ms: int) -> np.ndarray:
    """A 500ms chunk of silence (all zeros), mono, float32, 16kHz."""
    num_samples = sample_rate * chunk_duration_ms // 1000
    return np.zeros(num_samples, dtype=np.float32)


@pytest.fixture
def sine_wave_chunk(sample_rate: int, chunk_duration_ms: int) -> np.ndarray:
    """A 500ms chunk of a 440Hz sine wave at ~0.5 amplitude, mono, float32, 16kHz."""
    num_samples = sample_rate * chunk_duration_ms // 1000
    t = np.linspace(0, chunk_duration_ms / 1000, num_samples, endpoint=False, dtype=np.float32)
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def loud_chunk(sample_rate: int, chunk_duration_ms: int) -> np.ndarray:
    """A 500ms chunk of a loud sine wave near clipping (amplitude ~0.99)."""
    num_samples = sample_rate * chunk_duration_ms // 1000
    t = np.linspace(0, chunk_duration_ms / 1000, num_samples, endpoint=False, dtype=np.float32)
    return (0.99 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def clipping_chunk(sample_rate: int, chunk_duration_ms: int) -> np.ndarray:
    """A 500ms chunk at maximum amplitude (clipping)."""
    num_samples = sample_rate * chunk_duration_ms // 1000
    return np.ones(num_samples, dtype=np.float32)


@pytest.fixture
def quiet_chunk(sample_rate: int, chunk_duration_ms: int) -> np.ndarray:
    """A 500ms chunk of very quiet audio (amplitude ~0.005).

    RMS for a sine at amplitude 0.005: 0.005 / sqrt(2) ~ 0.00354
    dBFS: 20 * log10(0.00354) ~ -49 dBFS, which is in the TOO_QUIET range (-60 to -40).
    """
    num_samples = sample_rate * chunk_duration_ms // 1000
    t = np.linspace(0, chunk_duration_ms / 1000, num_samples, endpoint=False, dtype=np.float32)
    return (0.005 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def empty_chunk() -> np.ndarray:
    """An empty audio chunk (zero-length array)."""
    return np.array([], dtype=np.float32)


# ---------------------------------------------------------------------------
# Settings / Configuration fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_settings_dict() -> dict[str, Any]:
    """Default settings as a dictionary, matching design spec section 8.2."""
    return {
        "hotkey_key": "space",
        "hotkey_modifiers": ["option"],
        "start_on_login": False,
        "show_in_dock": False,
        "show_status_pill": True,
        "show_live_preview": False,
        "pill_position_x": None,
        "pill_position_y": None,
        "engine": "cloud_api",
        "cloud_api_provider": "openai",
        "cloud_api_base_url": "https://api.openai.com/v1",
        "cloud_api_model": "whisper-1",
        "local_model_size": "medium",
        "local_compute_type": "int8",
        "audio_device_id": None,
        "audio_device_name": None,
        "voice_commands_enabled": True,
        "check_for_updates": False,
    }


@pytest.fixture
def settings_json(default_settings_dict: dict[str, Any]) -> str:
    """Default settings as a JSON string."""
    return json.dumps(default_settings_dict, indent=2)


@pytest.fixture
def tmp_settings_path(tmp_path: Path) -> Path:
    """A temporary settings file path for testing SettingsStore."""
    return tmp_path / "systemstt" / "settings.json"


@pytest.fixture
def corrupted_settings_json() -> str:
    """Invalid JSON content to test corruption handling."""
    return "{this is not valid json!!!"


@pytest.fixture
def partial_settings_dict() -> dict[str, Any]:
    """Settings dict with only a subset of fields (tests forward compatibility)."""
    return {
        "engine": "local_whisper",
        "local_model_size": "small",
    }


# ---------------------------------------------------------------------------
# Mock platform services
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_text_injector() -> MagicMock:
    """A mock TextInjector with async methods."""
    injector = MagicMock()
    injector.inject_text = AsyncMock()
    injector.send_keystroke = AsyncMock()
    injector.has_accessibility_permission = MagicMock(return_value=True)
    injector.request_accessibility_permission = MagicMock()
    return injector


@pytest.fixture
def mock_hotkey_manager() -> MagicMock:
    """A mock HotkeyManager."""
    manager = MagicMock()
    manager.register = MagicMock()
    manager.unregister = MagicMock()
    manager.update_binding = MagicMock()
    manager.current_binding = None
    manager.is_registered = False
    return manager


@pytest.fixture
def mock_secure_store() -> MagicMock:
    """A mock SecureStore backed by a simple dict."""
    store = MagicMock()
    _data: dict[str, str] = {}

    def _get(key: str) -> str | None:
        return _data.get(key)

    def _set(key: str, value: str) -> None:
        _data[key] = value

    def _delete(key: str) -> None:
        _data.pop(key, None)

    def _exists(key: str) -> bool:
        return key in _data

    store.get = MagicMock(side_effect=_get)
    store.set = MagicMock(side_effect=_set)
    store.delete = MagicMock(side_effect=_delete)
    store.exists = MagicMock(side_effect=_exists)
    return store


# ---------------------------------------------------------------------------
# Mock audio device fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_audio_devices() -> list[dict[str, Any]]:
    """Mock sounddevice device info list."""
    return [
        {
            "name": "Built-in Microphone",
            "index": 0,
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
        },
        {
            "name": "USB Mic Pro",
            "index": 1,
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 48000.0,
        },
        {
            "name": "Speakers",
            "index": 2,
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 44100.0,
        },
    ]


# ---------------------------------------------------------------------------
# Mock STT engine fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_transcription_result() -> dict[str, Any]:
    """A mock TranscriptionResult as a dict for easy construction."""
    return {
        "segments": [
            {
                "text": "Hello world",
                "language": "en",
                "start_time": 0.0,
                "end_time": 1.5,
                "confidence": 0.95,
                "is_partial": False,
            }
        ],
        "full_text": "Hello world",
        "primary_language": "en",
        "processing_time_ms": 150.0,
    }


@pytest.fixture
def mock_hebrew_transcription_result() -> dict[str, Any]:
    """A mock TranscriptionResult with Hebrew text."""
    return {
        "segments": [
            {
                "text": "\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd",
                "language": "he",
                "start_time": 0.0,
                "end_time": 1.2,
                "confidence": 0.88,
                "is_partial": False,
            }
        ],
        "full_text": "\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd",
        "primary_language": "he",
        "processing_time_ms": 200.0,
    }


@pytest.fixture
def mock_mixed_language_result() -> dict[str, Any]:
    """A mock TranscriptionResult with mixed Hebrew and English."""
    return {
        "segments": [
            {
                "text": "\u05e9\u05dc\u05d5\u05dd, this is a test",
                "language": "he",
                "start_time": 0.0,
                "end_time": 0.8,
                "confidence": 0.85,
                "is_partial": False,
            },
            {
                "text": "of mixed language dictation",
                "language": "en",
                "start_time": 0.8,
                "end_time": 2.0,
                "confidence": 0.92,
                "is_partial": False,
            },
        ],
        "full_text": "\u05e9\u05dc\u05d5\u05dd, this is a test of mixed language dictation",
        "primary_language": "en",
        "processing_time_ms": 300.0,
    }


# ---------------------------------------------------------------------------
# Stop-dictation callback fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_stop_dictation_callback() -> MagicMock:
    """A mock callback for the stop dictation command."""
    return MagicMock()
