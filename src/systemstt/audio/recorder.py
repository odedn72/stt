"""
AudioRecorder — captures audio from the microphone using sounddevice.

Produces 16kHz mono float32 audio chunks delivered via callback.
All audio capture runs on PortAudio's dedicated thread.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import sounddevice as sd  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy as np

from systemstt.errors import AudioCaptureError, DeviceNotFoundError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioConfig:
    """Configuration for the audio recorder."""

    sample_rate: int = 16_000
    channels: int = 1
    dtype: str = "float32"
    chunk_duration_ms: int = 500
    device_id: int | None = None


class RecorderState(StrEnum):
    """State of the audio recorder."""

    IDLE = "idle"
    RECORDING = "recording"
    ERROR = "error"


class AudioRecorder:
    """Captures audio from an input device and delivers chunks via callback.

    Uses sounddevice.InputStream for real-time audio capture. Chunks are
    delivered as numpy arrays to the on_audio_chunk callback.
    """

    def __init__(self, config: AudioConfig) -> None:
        self._config = config
        self._state = RecorderState.IDLE
        self._stream: sd.InputStream | None = None
        self.on_audio_chunk: Callable[[np.ndarray], None] | None = None  # type: ignore[type-arg]
        self.on_error: Callable[[Exception], None] | None = None

    @property
    def state(self) -> RecorderState:
        """Return the current recorder state."""
        return self._state

    def _audio_callback(
        self,
        indata: np.ndarray,  # type: ignore[type-arg]
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback invoked by PortAudio on its thread."""
        if status:
            logger.warning("Audio callback status: %s", status)
        if self.on_audio_chunk is not None:
            # Copy the data since the buffer is reused by PortAudio
            chunk = indata[:, 0].copy() if indata.ndim > 1 else indata.copy().flatten()
            self.on_audio_chunk(chunk)

    def start(self) -> None:
        """Start audio capture.

        Opens a sounddevice InputStream and transitions to RECORDING state.
        Raises AudioCaptureError or DeviceNotFoundError on failure.
        """
        if self._state == RecorderState.RECORDING:
            return

        blocksize = int(self._config.sample_rate * self._config.chunk_duration_ms / 1000)

        try:
            self._stream = sd.InputStream(
                samplerate=self._config.sample_rate,
                channels=self._config.channels,
                dtype=self._config.dtype,
                blocksize=blocksize,
                device=self._config.device_id,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._state = RecorderState.RECORDING
            logger.info(
                "Audio recording started (device=%s, rate=%d)",
                self._config.device_id,
                self._config.sample_rate,
            )
        except Exception as exc:
            self._state = RecorderState.ERROR
            error_msg = str(exc).lower()
            if self._config.device_id is not None and "invalid" in error_msg:
                raise DeviceNotFoundError(
                    f"Audio device {self._config.device_id} not found: {exc}"
                ) from exc
            raise AudioCaptureError(f"Failed to start audio capture: {exc}") from exc

    def stop(self) -> None:
        """Stop audio capture and return to IDLE state."""
        if self._state == RecorderState.IDLE:
            return

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                logger.warning("Error stopping audio stream: %s", exc)
            finally:
                self._stream = None

        self._state = RecorderState.IDLE
        logger.info("Audio recording stopped")

    def update_config(self, config: AudioConfig) -> None:
        """Update the audio configuration.

        If currently recording, restarts the stream with the new config.
        """
        was_recording = self._state == RecorderState.RECORDING
        if was_recording:
            self.stop()

        self._config = config

        if was_recording:
            self.start()
