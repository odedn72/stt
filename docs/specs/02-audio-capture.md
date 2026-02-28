# 02 — Audio Capture Layer
**Version:** 1.0
**Date:** 2026-02-28
**Status:** Draft

---

## 1. Goal

Capture raw audio from the user's microphone and stream it to the STT engine as numpy arrays. Provide device enumeration and real-time level metering for the UI.

**MRD requirements:**
- FR-002: Real-time transcription (requires low-latency audio capture)
- FR-006: Long-form dictation (continuous capture without cutoff)
- FR-013: Audio input device selection
- NFR-001/002: Transcription latency (audio layer must not add measurable latency)
- NFR-004: CPU usage during idle (no capture when not dictating)

---

## 2. Interface

### 2.1 AudioRecorder

```python
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import numpy as np
import numpy.typing as npt

AudioChunk = npt.NDArray[np.float32]  # Shape: (num_samples,), mono, 16kHz
AudioCallback = Callable[[AudioChunk], None]


class RecorderState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    ERROR = "error"


@dataclass(frozen=True)
class AudioConfig:
    """Configuration for audio capture."""
    sample_rate: int = 16_000       # 16kHz — Whisper's native rate
    channels: int = 1               # Mono
    dtype: str = "float32"          # 32-bit float PCM
    chunk_duration_ms: int = 500    # Callback interval: 500ms chunks
    device_id: int | None = None    # None = system default


class AudioRecorder:
    """
    Captures audio from the microphone and delivers chunks via callback.

    Usage:
        recorder = AudioRecorder(config=AudioConfig())
        recorder.on_audio_chunk = my_callback  # receives AudioChunk
        recorder.start()
        ...
        recorder.stop()
    """

    def __init__(self, config: AudioConfig) -> None: ...

    @property
    def state(self) -> RecorderState: ...

    @property
    def on_audio_chunk(self) -> AudioCallback | None: ...
    @on_audio_chunk.setter
    def on_audio_chunk(self, callback: AudioCallback | None) -> None: ...

    @property
    def on_error(self) -> Callable[[Exception], None] | None: ...
    @on_error.setter
    def on_error(self, callback: Callable[[Exception], None] | None) -> None: ...

    def start(self) -> None:
        """Start audio capture. Raises AudioCaptureError if device unavailable."""
        ...

    def stop(self) -> None:
        """Stop audio capture. Safe to call when already stopped."""
        ...

    def update_config(self, config: AudioConfig) -> None:
        """
        Update audio configuration. If currently recording, stops and
        restarts with the new config.
        """
        ...
```

### 2.2 DeviceEnumerator

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AudioDevice:
    """Represents an audio input device."""
    device_id: int
    name: str
    is_default: bool
    max_input_channels: int
    sample_rate: float


class DeviceEnumerator:
    """
    Lists and monitors available audio input devices.

    Usage:
        enum = DeviceEnumerator()
        devices = enum.list_input_devices()
        default = enum.get_default_device()
    """

    def list_input_devices(self) -> list[AudioDevice]:
        """Return all available audio input devices."""
        ...

    def get_default_device(self) -> AudioDevice | None:
        """Return the system's default input device, or None if none available."""
        ...

    def get_device_by_id(self, device_id: int) -> AudioDevice | None:
        """Return a specific device by ID, or None if not found."""
        ...

    def refresh(self) -> list[AudioDevice]:
        """Re-scan for devices. Returns updated list."""
        ...
```

### 2.3 LevelMeter

```python
from dataclasses import dataclass
from enum import Enum
import numpy as np
import numpy.typing as npt


class AudioLevel(Enum):
    SILENT = "silent"        # No signal
    TOO_QUIET = "too_quiet"  # Below usable threshold
    OK = "ok"                # Normal speaking level
    LOUD = "loud"            # Approaching clipping
    CLIPPING = "clipping"    # At or above 0dBFS


@dataclass(frozen=True)
class LevelReading:
    """A single level meter reading."""
    rms_db: float         # RMS level in dBFS (0 = full scale, negative = quieter)
    peak_db: float        # Peak level in dBFS
    level: AudioLevel     # Categorized level


class LevelMeter:
    """
    Computes audio level from PCM samples.

    Usage:
        meter = LevelMeter()
        reading = meter.compute(audio_chunk)
    """

    def compute(self, chunk: npt.NDArray[np.float32]) -> LevelReading:
        """Compute RMS and peak levels from an audio chunk."""
        ...
```

---

## 3. Data Models

### 3.1 AudioChunk

- Type: `numpy.ndarray` with dtype `float32`
- Shape: `(num_samples,)` — 1D array, mono
- Sample rate: 16,000 Hz (Whisper's native rate)
- Value range: [-1.0, 1.0]
- Chunk size: `sample_rate * chunk_duration_ms / 1000` = 8,000 samples per 500ms chunk

### 3.2 Audio Format Requirements

| Property | Value | Rationale |
|----------|-------|-----------|
| Sample rate | 16,000 Hz | Whisper models expect 16kHz. Resampling is unnecessary if we capture at this rate. |
| Channels | 1 (mono) | Whisper expects mono. No need for stereo from a desk microphone. |
| Bit depth | 32-bit float | sounddevice's native format. Maps directly to numpy float32. |
| Chunk duration | 500ms | Balance between latency (smaller = lower latency) and overhead (smaller = more callbacks). 500ms is a good default. |

---

## 4. Dependencies

| Dependency | Usage |
|-----------|-------|
| sounddevice | PortAudio wrapper for audio capture and device enumeration |
| numpy | Audio data as arrays, RMS/peak computation |

**Internal dependencies:**
- `systemstt.errors` — `AudioCaptureError`, `DeviceNotFoundError`, `DeviceDisconnectedError`

---

## 5. Error Handling

| Error | Condition | Behavior |
|-------|-----------|----------|
| `DeviceNotFoundError` | Configured device_id not found in system | Raised on `start()`. Caller should fall back to default device or show error. |
| `DeviceDisconnectedError` | Device disconnects during recording | Delivered via `on_error` callback. Recorder transitions to ERROR state. |
| `AudioCaptureError` | PortAudio stream fails to open or produces errors | Raised on `start()` or delivered via `on_error` during recording. |

**Recovery strategy:**
1. On `DeviceDisconnectedError` during recording: App Core stops dictation, notifies user via pill/notification.
2. The recorder does NOT automatically retry or switch devices. The App Core decides the recovery strategy.

---

## 6. Notes for Developer

1. **sounddevice callback threading:** The `sounddevice.InputStream` callback runs on PortAudio's own thread. The callback must be fast — copy the data into a `queue.Queue` or invoke the `on_audio_chunk` callback. Do NOT do any heavy processing in the callback.

2. **Queue bridge to transcription thread:** The `on_audio_chunk` callback will typically push the chunk into a `queue.Queue` that the transcription thread consumes. This decouples audio capture from transcription speed.

3. **Device hot-plug detection:** For v1, `DeviceEnumerator.refresh()` is called manually (e.g., when the Audio settings tab is opened). Real-time hot-plug detection via polling or OS notifications can be added later.

4. **Level meter is a pure function:** `LevelMeter.compute()` takes a chunk and returns a reading. It has no state. The UI calls it on each chunk when the Audio tab is visible. When the Audio tab is not visible, the level meter is not invoked (per design spec: "level meter runs only when the Audio tab is open").

5. **Resampling:** If the user's device doesn't support 16kHz natively, `sounddevice` will use PortAudio's built-in resampling. This is transparent. No additional resampling code is needed.

6. **dBFS calculation:**
   - RMS: `20 * log10(rms_value)` where rms_value is `sqrt(mean(samples^2))`
   - Peak: `20 * log10(max(abs(samples)))`
   - Thresholds for AudioLevel classification (approximate):
     - SILENT: rms_db < -60
     - TOO_QUIET: -60 <= rms_db < -40
     - OK: -40 <= rms_db < -6
     - LOUD: -6 <= rms_db < -1
     - CLIPPING: rms_db >= -1 or peak_db >= -0.5

7. **Testing:** Mock `sounddevice.InputStream` in tests. Create synthetic audio chunks (sine waves, silence, noise) as numpy arrays for testing the level meter and downstream processing.
