"""
Error hierarchy for SystemSTT.

All custom exceptions are rooted at SystemSTTError. The hierarchy
mirrors the component structure of the application, allowing callers
to catch at any level of granularity.

Hierarchy:
    SystemSTTError (base)
    +-- AudioError
    |   +-- DeviceNotFoundError
    |   +-- DeviceDisconnectedError
    |   +-- AudioCaptureError
    +-- STTEngineError
    |   +-- ModelLoadError
    |   +-- ModelDownloadError
    |   +-- TranscriptionError
    |   +-- CloudAPIError
    |       +-- APIAuthenticationError
    |       +-- APITimeoutError
    |       +-- APIRateLimitError
    |       +-- APIUnavailableError
    +-- TextInjectionError
    |   +-- AccessibilityPermissionError
    |   +-- InjectionFailedError
    +-- HotkeyError
    |   +-- HotkeyRegistrationError
    +-- ConfigurationError
        +-- SettingsLoadError
        +-- KeychainAccessError
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Base error
# ---------------------------------------------------------------------------


class SystemSTTError(Exception):
    """Root exception for all SystemSTT errors."""


# ---------------------------------------------------------------------------
# Audio errors
# ---------------------------------------------------------------------------


class AudioError(SystemSTTError):
    """Base exception for audio capture errors."""


class DeviceNotFoundError(AudioError):
    """Raised when the requested audio device cannot be found."""


class DeviceDisconnectedError(AudioError):
    """Raised when an audio device is disconnected during capture."""


class AudioCaptureError(AudioError):
    """Raised when audio capture fails for any reason."""


# ---------------------------------------------------------------------------
# STT Engine errors
# ---------------------------------------------------------------------------


class STTEngineError(SystemSTTError):
    """Base exception for STT engine errors."""


class ModelLoadError(STTEngineError):
    """Raised when a local Whisper model fails to load."""


class ModelDownloadError(STTEngineError):
    """Raised when a model download fails."""


class TranscriptionError(STTEngineError):
    """Raised when transcription fails."""


class CloudAPIError(STTEngineError):
    """Base exception for cloud API errors."""


class APIAuthenticationError(CloudAPIError):
    """Raised when the API key is invalid or expired (HTTP 401)."""


class APITimeoutError(CloudAPIError):
    """Raised when the API request times out."""


class APIRateLimitError(CloudAPIError):
    """Raised when the API rate limit is exceeded (HTTP 429)."""


class APIUnavailableError(CloudAPIError):
    """Raised when the API is unavailable (HTTP 5xx)."""


# ---------------------------------------------------------------------------
# Text injection errors
# ---------------------------------------------------------------------------


class TextInjectionError(SystemSTTError):
    """Base exception for text injection errors."""


class AccessibilityPermissionError(TextInjectionError):
    """Raised when macOS Accessibility permission is not granted."""


class InjectionFailedError(TextInjectionError):
    """Raised when text injection into the focused app fails."""


# ---------------------------------------------------------------------------
# Hotkey errors
# ---------------------------------------------------------------------------


class HotkeyError(SystemSTTError):
    """Base exception for hotkey errors."""


class HotkeyRegistrationError(HotkeyError):
    """Raised when hotkey registration fails (e.g., already in use)."""


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------


class ConfigurationError(SystemSTTError):
    """Base exception for configuration errors."""


class SettingsLoadError(ConfigurationError):
    """Raised when settings file loading fails."""


class KeychainAccessError(ConfigurationError):
    """Raised when macOS Keychain access fails."""
