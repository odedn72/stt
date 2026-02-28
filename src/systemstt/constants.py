"""App-wide constants for SystemSTT."""

from __future__ import annotations

from pathlib import Path

# Application metadata
APP_NAME = "SystemSTT"
APP_BUNDLE_ID = "com.systemstt.app"

# Configuration paths
CONFIG_DIR = Path.home() / ".config" / "systemstt"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
CACHE_DIR = Path.home() / ".cache" / "systemstt"
MODELS_DIR = CACHE_DIR / "models"
LOG_DIR = Path.home() / ".local" / "share" / "systemstt"
LOG_FILE = LOG_DIR / "systemstt.log"

# Audio defaults
DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_CHANNELS = 1
DEFAULT_AUDIO_DTYPE = "float32"
DEFAULT_CHUNK_DURATION_MS = 500

# Keychain
KEYCHAIN_SERVICE_NAME = "systemstt"

# STT Engine defaults
DEFAULT_WHISPER_MODEL = "medium"
DEFAULT_COMPUTE_TYPE = "int8"
DEFAULT_CLOUD_API_BASE_URL = "https://api.openai.com/v1"
DEFAULT_CLOUD_API_MODEL = "whisper-1"
