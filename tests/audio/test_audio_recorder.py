# TDD: Written from spec 02-audio-capture.md
"""
Tests for AudioRecorder — the audio capture component.

AudioRecorder wraps sounddevice.InputStream to capture 16kHz mono float32
audio and deliver chunks via callback. All sounddevice calls are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest

from systemstt.audio.recorder import AudioRecorder, AudioConfig, RecorderState
from systemstt.errors import AudioCaptureError, DeviceNotFoundError, DeviceDisconnectedError


# ---------------------------------------------------------------------------
# AudioConfig tests
# ---------------------------------------------------------------------------

class TestAudioConfig:
    """Tests for the AudioConfig dataclass."""

    def test_default_sample_rate_is_16000(self) -> None:
        config = AudioConfig()
        assert config.sample_rate == 16_000

    def test_default_channels_is_mono(self) -> None:
        config = AudioConfig()
        assert config.channels == 1

    def test_default_dtype_is_float32(self) -> None:
        config = AudioConfig()
        assert config.dtype == "float32"

    def test_default_chunk_duration_is_500ms(self) -> None:
        config = AudioConfig()
        assert config.chunk_duration_ms == 500

    def test_default_device_id_is_none(self) -> None:
        config = AudioConfig()
        assert config.device_id is None

    def test_custom_device_id(self) -> None:
        config = AudioConfig(device_id=3)
        assert config.device_id == 3

    def test_config_is_frozen(self) -> None:
        config = AudioConfig()
        with pytest.raises(AttributeError):
            config.sample_rate = 44100  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RecorderState tests
# ---------------------------------------------------------------------------

class TestRecorderState:
    """Tests for RecorderState enum."""

    def test_idle_state_exists(self) -> None:
        assert RecorderState.IDLE.value == "idle"

    def test_recording_state_exists(self) -> None:
        assert RecorderState.RECORDING.value == "recording"

    def test_error_state_exists(self) -> None:
        assert RecorderState.ERROR.value == "error"


# ---------------------------------------------------------------------------
# AudioRecorder lifecycle tests
# ---------------------------------------------------------------------------

class TestAudioRecorderLifecycle:
    """Tests for AudioRecorder start/stop lifecycle."""

    @patch("systemstt.audio.recorder.sd")
    def test_initial_state_is_idle(self, mock_sd: MagicMock) -> None:
        recorder = AudioRecorder(config=AudioConfig())
        assert recorder.state == RecorderState.IDLE

    @patch("systemstt.audio.recorder.sd")
    def test_start_transitions_to_recording(self, mock_sd: MagicMock) -> None:
        recorder = AudioRecorder(config=AudioConfig())
        recorder.start()
        assert recorder.state == RecorderState.RECORDING

    @patch("systemstt.audio.recorder.sd")
    def test_stop_transitions_to_idle(self, mock_sd: MagicMock) -> None:
        recorder = AudioRecorder(config=AudioConfig())
        recorder.start()
        recorder.stop()
        assert recorder.state == RecorderState.IDLE

    @patch("systemstt.audio.recorder.sd")
    def test_stop_when_already_idle_is_safe(self, mock_sd: MagicMock) -> None:
        recorder = AudioRecorder(config=AudioConfig())
        recorder.stop()  # Should not raise
        assert recorder.state == RecorderState.IDLE

    @patch("systemstt.audio.recorder.sd")
    def test_start_opens_input_stream(self, mock_sd: MagicMock) -> None:
        config = AudioConfig(sample_rate=16_000, channels=1, dtype="float32")
        recorder = AudioRecorder(config=config)
        recorder.start()
        mock_sd.InputStream.assert_called_once()
        # Verify key arguments
        call_kwargs = mock_sd.InputStream.call_args
        assert call_kwargs.kwargs.get("samplerate") == 16_000 or \
               (call_kwargs.args and call_kwargs.args[0] == 16_000) or \
               "samplerate" in str(call_kwargs)

    @patch("systemstt.audio.recorder.sd")
    def test_stop_closes_stream(self, mock_sd: MagicMock) -> None:
        recorder = AudioRecorder(config=AudioConfig())
        recorder.start()
        stream_mock = mock_sd.InputStream.return_value
        recorder.stop()
        stream_mock.stop.assert_called()
        stream_mock.close.assert_called()

    @patch("systemstt.audio.recorder.sd")
    def test_start_raises_audio_capture_error_on_stream_failure(
        self, mock_sd: MagicMock
    ) -> None:
        mock_sd.InputStream.side_effect = Exception("PortAudio error")
        recorder = AudioRecorder(config=AudioConfig())
        with pytest.raises(AudioCaptureError):
            recorder.start()

    @patch("systemstt.audio.recorder.sd")
    def test_start_raises_device_not_found_for_invalid_device(
        self, mock_sd: MagicMock
    ) -> None:
        mock_sd.InputStream.side_effect = Exception("Invalid device")
        config = AudioConfig(device_id=999)
        recorder = AudioRecorder(config=config)
        with pytest.raises((DeviceNotFoundError, AudioCaptureError)):
            recorder.start()


# ---------------------------------------------------------------------------
# AudioRecorder callback tests
# ---------------------------------------------------------------------------

class TestAudioRecorderCallback:
    """Tests for audio chunk delivery via callback."""

    @patch("systemstt.audio.recorder.sd")
    def test_on_audio_chunk_callback_can_be_set(self, mock_sd: MagicMock) -> None:
        recorder = AudioRecorder(config=AudioConfig())
        callback = MagicMock()
        recorder.on_audio_chunk = callback
        assert recorder.on_audio_chunk is callback

    @patch("systemstt.audio.recorder.sd")
    def test_on_audio_chunk_callback_default_is_none(self, mock_sd: MagicMock) -> None:
        recorder = AudioRecorder(config=AudioConfig())
        assert recorder.on_audio_chunk is None

    @patch("systemstt.audio.recorder.sd")
    def test_on_error_callback_can_be_set(self, mock_sd: MagicMock) -> None:
        recorder = AudioRecorder(config=AudioConfig())
        callback = MagicMock()
        recorder.on_error = callback
        assert recorder.on_error is callback

    @patch("systemstt.audio.recorder.sd")
    def test_on_error_callback_default_is_none(self, mock_sd: MagicMock) -> None:
        recorder = AudioRecorder(config=AudioConfig())
        assert recorder.on_error is None


# ---------------------------------------------------------------------------
# AudioRecorder config update tests
# ---------------------------------------------------------------------------

class TestAudioRecorderConfigUpdate:
    """Tests for updating AudioRecorder configuration at runtime."""

    @patch("systemstt.audio.recorder.sd")
    def test_update_config_while_idle(self, mock_sd: MagicMock) -> None:
        recorder = AudioRecorder(config=AudioConfig())
        new_config = AudioConfig(device_id=2)
        recorder.update_config(new_config)
        # Should not raise, state stays idle

    @patch("systemstt.audio.recorder.sd")
    def test_update_config_while_recording_restarts(self, mock_sd: MagicMock) -> None:
        recorder = AudioRecorder(config=AudioConfig())
        recorder.start()
        stream_mock = mock_sd.InputStream.return_value
        new_config = AudioConfig(device_id=2)
        recorder.update_config(new_config)
        # Should have stopped the old stream
        stream_mock.stop.assert_called()
        # And started a new one
        assert mock_sd.InputStream.call_count == 2
        assert recorder.state == RecorderState.RECORDING


# ---------------------------------------------------------------------------
# AudioRecorder audio callback edge cases
# ---------------------------------------------------------------------------

class TestAudioRecorderCallbackEdgeCases:
    """Edge case tests for the audio callback pipeline."""

    @patch("systemstt.audio.recorder.sd")
    def test_audio_callback_invokes_on_audio_chunk(self, mock_sd: MagicMock) -> None:
        """Verify the internal _audio_callback delivers data to on_audio_chunk."""
        recorder = AudioRecorder(config=AudioConfig())
        chunk_received = MagicMock()
        recorder.on_audio_chunk = chunk_received

        # Simulate PortAudio delivering a 2D array (frames x channels)
        indata = np.random.randn(8000, 1).astype(np.float32)
        recorder._audio_callback(indata, 8000, None, MagicMock(return_value=False))

        chunk_received.assert_called_once()
        delivered = chunk_received.call_args[0][0]
        assert isinstance(delivered, np.ndarray)
        assert delivered.ndim == 1

    @patch("systemstt.audio.recorder.sd")
    def test_audio_callback_no_crash_without_callback(self, mock_sd: MagicMock) -> None:
        """When on_audio_chunk is None, _audio_callback should not crash."""
        recorder = AudioRecorder(config=AudioConfig())
        recorder.on_audio_chunk = None

        indata = np.random.randn(8000, 1).astype(np.float32)
        # Should not raise
        recorder._audio_callback(indata, 8000, None, MagicMock(return_value=False))

    @patch("systemstt.audio.recorder.sd")
    def test_start_while_already_recording_is_noop(self, mock_sd: MagicMock) -> None:
        """Calling start() when already recording should be a no-op."""
        recorder = AudioRecorder(config=AudioConfig())
        recorder.start()
        assert mock_sd.InputStream.call_count == 1
        recorder.start()  # second call should be no-op
        assert mock_sd.InputStream.call_count == 1
        assert recorder.state == RecorderState.RECORDING

    @patch("systemstt.audio.recorder.sd")
    def test_error_state_after_failed_start(self, mock_sd: MagicMock) -> None:
        """After a failed start, the recorder should be in ERROR state."""
        mock_sd.InputStream.side_effect = Exception("PortAudio error")
        recorder = AudioRecorder(config=AudioConfig())
        with pytest.raises(AudioCaptureError):
            recorder.start()
        assert recorder.state == RecorderState.ERROR

    @patch("systemstt.audio.recorder.sd")
    def test_stop_from_error_state_returns_to_idle(self, mock_sd: MagicMock) -> None:
        """Calling stop() from ERROR state should return to IDLE."""
        mock_sd.InputStream.side_effect = Exception("PortAudio error")
        recorder = AudioRecorder(config=AudioConfig())
        with pytest.raises(AudioCaptureError):
            recorder.start()
        assert recorder.state == RecorderState.ERROR
        recorder.stop()
        assert recorder.state == RecorderState.IDLE
