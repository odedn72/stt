# TDD: Written from spec 00-architecture-overview.md
"""
Tests for the SystemSTT error hierarchy.

The error hierarchy is defined in spec 00, section 8.1:
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

import pytest

from systemstt.errors import (
    SystemSTTError,
    AudioError,
    DeviceNotFoundError,
    DeviceDisconnectedError,
    AudioCaptureError,
    STTEngineError,
    ModelLoadError,
    ModelDownloadError,
    TranscriptionError,
    CloudAPIError,
    APIAuthenticationError,
    APITimeoutError,
    APIRateLimitError,
    APIUnavailableError,
    TextInjectionError,
    AccessibilityPermissionError,
    InjectionFailedError,
    HotkeyError,
    HotkeyRegistrationError,
    ConfigurationError,
    SettingsLoadError,
    KeychainAccessError,
)


# ---------------------------------------------------------------------------
# Base error
# ---------------------------------------------------------------------------

class TestSystemSTTError:
    """Tests for the root exception class."""

    def test_systemstt_error_inherits_from_exception(self) -> None:
        assert issubclass(SystemSTTError, Exception)

    def test_systemstt_error_can_be_instantiated_with_message(self) -> None:
        err = SystemSTTError("something went wrong")
        assert str(err) == "something went wrong"

    def test_systemstt_error_can_be_raised_and_caught(self) -> None:
        with pytest.raises(SystemSTTError):
            raise SystemSTTError("test")


# ---------------------------------------------------------------------------
# Audio errors
# ---------------------------------------------------------------------------

class TestAudioErrors:
    """Tests for audio-related exceptions."""

    def test_audio_error_inherits_from_base(self) -> None:
        assert issubclass(AudioError, SystemSTTError)

    def test_device_not_found_error_inherits_from_audio_error(self) -> None:
        assert issubclass(DeviceNotFoundError, AudioError)

    def test_device_disconnected_error_inherits_from_audio_error(self) -> None:
        assert issubclass(DeviceDisconnectedError, AudioError)

    def test_audio_capture_error_inherits_from_audio_error(self) -> None:
        assert issubclass(AudioCaptureError, AudioError)

    def test_device_not_found_error_caught_as_system_stt_error(self) -> None:
        with pytest.raises(SystemSTTError):
            raise DeviceNotFoundError("device 5 not found")

    def test_device_not_found_error_caught_as_audio_error(self) -> None:
        with pytest.raises(AudioError):
            raise DeviceNotFoundError("device 5 not found")

    def test_device_disconnected_error_message(self) -> None:
        err = DeviceDisconnectedError("USB Mic disconnected")
        assert "USB Mic disconnected" in str(err)

    def test_audio_capture_error_message(self) -> None:
        err = AudioCaptureError("PortAudio stream failed")
        assert "PortAudio stream failed" in str(err)


# ---------------------------------------------------------------------------
# STT Engine errors
# ---------------------------------------------------------------------------

class TestSTTEngineErrors:
    """Tests for STT engine exceptions."""

    def test_stt_engine_error_inherits_from_base(self) -> None:
        assert issubclass(STTEngineError, SystemSTTError)

    def test_model_load_error_inherits_from_stt_engine_error(self) -> None:
        assert issubclass(ModelLoadError, STTEngineError)

    def test_model_download_error_inherits_from_stt_engine_error(self) -> None:
        assert issubclass(ModelDownloadError, STTEngineError)

    def test_transcription_error_inherits_from_stt_engine_error(self) -> None:
        assert issubclass(TranscriptionError, STTEngineError)

    def test_cloud_api_error_inherits_from_stt_engine_error(self) -> None:
        assert issubclass(CloudAPIError, STTEngineError)

    def test_api_authentication_error_inherits_from_cloud_api_error(self) -> None:
        assert issubclass(APIAuthenticationError, CloudAPIError)

    def test_api_timeout_error_inherits_from_cloud_api_error(self) -> None:
        assert issubclass(APITimeoutError, CloudAPIError)

    def test_api_rate_limit_error_inherits_from_cloud_api_error(self) -> None:
        assert issubclass(APIRateLimitError, CloudAPIError)

    def test_api_unavailable_error_inherits_from_cloud_api_error(self) -> None:
        assert issubclass(APIUnavailableError, CloudAPIError)

    def test_cloud_api_error_caught_as_base(self) -> None:
        with pytest.raises(SystemSTTError):
            raise APITimeoutError("request timed out")

    def test_api_errors_caught_as_cloud_api_error(self) -> None:
        for error_cls in [
            APIAuthenticationError,
            APITimeoutError,
            APIRateLimitError,
            APIUnavailableError,
        ]:
            with pytest.raises(CloudAPIError):
                raise error_cls("test")


# ---------------------------------------------------------------------------
# Text injection errors
# ---------------------------------------------------------------------------

class TestTextInjectionErrors:
    """Tests for text injection exceptions."""

    def test_text_injection_error_inherits_from_base(self) -> None:
        assert issubclass(TextInjectionError, SystemSTTError)

    def test_accessibility_permission_error_inherits_from_text_injection_error(self) -> None:
        assert issubclass(AccessibilityPermissionError, TextInjectionError)

    def test_injection_failed_error_inherits_from_text_injection_error(self) -> None:
        assert issubclass(InjectionFailedError, TextInjectionError)

    def test_accessibility_error_caught_as_base(self) -> None:
        with pytest.raises(SystemSTTError):
            raise AccessibilityPermissionError("permission denied")


# ---------------------------------------------------------------------------
# Hotkey errors
# ---------------------------------------------------------------------------

class TestHotkeyErrors:
    """Tests for hotkey exceptions."""

    def test_hotkey_error_inherits_from_base(self) -> None:
        assert issubclass(HotkeyError, SystemSTTError)

    def test_hotkey_registration_error_inherits_from_hotkey_error(self) -> None:
        assert issubclass(HotkeyRegistrationError, HotkeyError)

    def test_hotkey_registration_error_message(self) -> None:
        err = HotkeyRegistrationError("Option+Space already in use")
        assert "Option+Space" in str(err)


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------

class TestConfigurationErrors:
    """Tests for configuration exceptions."""

    def test_configuration_error_inherits_from_base(self) -> None:
        assert issubclass(ConfigurationError, SystemSTTError)

    def test_settings_load_error_inherits_from_configuration_error(self) -> None:
        assert issubclass(SettingsLoadError, ConfigurationError)

    def test_keychain_access_error_inherits_from_configuration_error(self) -> None:
        assert issubclass(KeychainAccessError, ConfigurationError)

    def test_settings_load_error_caught_as_base(self) -> None:
        with pytest.raises(SystemSTTError):
            raise SettingsLoadError("corrupted JSON")

    def test_keychain_access_error_caught_as_base(self) -> None:
        with pytest.raises(SystemSTTError):
            raise KeychainAccessError("keychain locked")
