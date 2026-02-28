# 03 — STT Engine Layer
**Version:** 1.0
**Date:** 2026-02-28
**Status:** Draft

---

## 1. Goal

Provide an abstract interface for speech-to-text engines with two implementations: a local engine using `faster-whisper` and a cloud engine using the OpenAI Whisper API. The interface enables hot-swapping engines without restarting the application.

**MRD requirements:**
- FR-002: Real-time transcription
- FR-004: Hebrew and English support
- FR-005: Auto language detection (including mid-sentence switching)
- FR-006: Long-form dictation
- FR-008: Configurable STT engine (local/cloud, no restart required)
- FR-011: Configurable Whisper model size
- NFR-001: Transcription latency < 2s (local)
- NFR-002: Transcription latency < 1s (cloud)
- NFR-003: Memory usage < 2GB RAM (local model loaded)

---

## 2. Interface

### 2.1 STTEngine (Abstract Base Class)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator
import numpy as np
import numpy.typing as npt


class DetectedLanguage(Enum):
    ENGLISH = "en"
    HEBREW = "he"
    UNKNOWN = "unknown"


class EngineType(Enum):
    LOCAL_WHISPER = "local_whisper"
    CLOUD_API = "cloud_api"


class EngineState(Enum):
    UNINITIALIZED = "uninitialized"
    LOADING = "loading"        # Model loading or API connection establishing
    READY = "ready"
    TRANSCRIBING = "transcribing"
    ERROR = "error"


@dataclass(frozen=True)
class TranscriptionSegment:
    """A single segment of transcribed text."""
    text: str
    language: DetectedLanguage
    start_time: float          # Seconds from start of audio
    end_time: float            # Seconds from start of audio
    confidence: float          # 0.0 to 1.0
    is_partial: bool           # True if this may be revised by a later segment


@dataclass(frozen=True)
class TranscriptionResult:
    """Complete result from a transcription request."""
    segments: list[TranscriptionSegment]
    full_text: str                          # Concatenated text from all segments
    primary_language: DetectedLanguage       # Dominant language in this result
    processing_time_ms: float               # Time taken to transcribe


class STTEngine(ABC):
    """
    Abstract base class for speech-to-text engines.

    All engines must implement this interface. The App Core interacts only
    with this interface, never with implementation details.
    """

    @property
    @abstractmethod
    def engine_type(self) -> EngineType:
        """Return the type of this engine."""
        ...

    @property
    @abstractmethod
    def state(self) -> EngineState:
        """Return the current state of the engine."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the engine (load model, validate API key, etc.).
        Raises STTEngineError on failure.
        """
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Release resources (unload model, close connections).
        Safe to call when already shut down.
        """
        ...

    @abstractmethod
    async def transcribe(
        self,
        audio: npt.NDArray[np.float32],
        *,
        language_hint: DetectedLanguage | None = None,
    ) -> TranscriptionResult:
        """
        Transcribe a chunk of audio.

        Args:
            audio: PCM audio data, mono, 16kHz, float32, values in [-1, 1].
            language_hint: Optional hint from previous detection to bias the model.

        Returns:
            TranscriptionResult with text, language, timing, and confidence.

        Raises:
            TranscriptionError: If transcription fails.
            STTEngineError: If the engine is not in READY or TRANSCRIBING state.
        """
        ...

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[npt.NDArray[np.float32]],
        *,
        language_hint: DetectedLanguage | None = None,
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Stream-transcribe audio, yielding partial results as they become available.

        Args:
            audio_stream: Async iterator of audio chunks.
            language_hint: Optional language hint.

        Yields:
            TranscriptionResult objects. Segments with is_partial=True may be revised.

        Raises:
            TranscriptionError: If transcription fails.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the engine can be used (model exists, API key valid, etc.).
        Does not perform network calls — uses cached state.
        """
        ...
```

### 2.2 LocalWhisperEngine

```python
from dataclasses import dataclass


class WhisperModelSize(Enum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


@dataclass(frozen=True)
class LocalWhisperConfig:
    """Configuration for the local Whisper engine."""
    model_size: WhisperModelSize = WhisperModelSize.MEDIUM
    device: str = "cpu"               # "cpu" for Intel Mac; "cuda" for future GPU
    compute_type: str = "int8"        # int8 quantization for faster CPU inference
    num_workers: int = 1              # Transcription worker threads
    beam_size: int = 5                # Beam search width
    model_cache_dir: str = "~/.cache/systemstt/models"


class LocalWhisperEngine(STTEngine):
    """
    Local speech-to-text using faster-whisper (CTranslate2).

    Manages model loading, downloading, and inference.
    """

    def __init__(self, config: LocalWhisperConfig) -> None: ...

    @property
    def engine_type(self) -> EngineType:
        return EngineType.LOCAL_WHISPER

    # ... implements all STTEngine abstract methods ...

    async def download_model(
        self,
        on_progress: Callable[[float], None] | None = None,
    ) -> None:
        """
        Download the configured model if not already cached.

        Args:
            on_progress: Callback with progress as float 0.0-1.0.

        Raises:
            ModelDownloadError: If download fails.
        """
        ...

    def is_model_downloaded(self) -> bool:
        """Check if the configured model is already cached locally."""
        ...

    def get_model_info(self) -> dict[str, str]:
        """Return info about the loaded model (size, path, quantization)."""
        ...
```

### 2.3 CloudAPIEngine

```python
@dataclass(frozen=True)
class CloudAPIConfig:
    """Configuration for the cloud Whisper API engine."""
    api_key: str                          # Loaded from Keychain at runtime
    api_base_url: str = "https://api.openai.com/v1"
    model: str = "whisper-1"
    timeout_seconds: float = 10.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0


class CloudAPIEngine(STTEngine):
    """
    Cloud-based speech-to-text using the OpenAI Whisper API.

    Sends audio over HTTPS, receives transcription. Supports retries
    and timeout handling.
    """

    def __init__(self, config: CloudAPIConfig) -> None: ...

    @property
    def engine_type(self) -> EngineType:
        return EngineType.CLOUD_API

    # ... implements all STTEngine abstract methods ...

    async def validate_api_key(self) -> bool:
        """
        Validate the API key by making a lightweight API call.
        Returns True if valid, False if invalid.
        """
        ...
```

### 2.4 EngineManager

```python
class EngineManager:
    """
    Manages STT engine lifecycle and hot-swapping.

    The App Core uses EngineManager rather than interacting with
    engines directly. This encapsulates initialization, switching,
    and fallback logic.
    """

    def __init__(
        self,
        local_config: LocalWhisperConfig,
        cloud_config: CloudAPIConfig,
    ) -> None: ...

    @property
    def active_engine(self) -> STTEngine | None:
        """Return the currently active engine, or None if not initialized."""
        ...

    @property
    def active_engine_type(self) -> EngineType | None:
        """Return the type of the active engine."""
        ...

    async def activate_engine(self, engine_type: EngineType) -> None:
        """
        Switch to the specified engine. Shuts down the current engine
        and initializes the new one.

        Raises:
            STTEngineError: If the target engine fails to initialize.
        """
        ...

    async def shutdown(self) -> None:
        """Shut down the active engine and release all resources."""
        ...

    def update_local_config(self, config: LocalWhisperConfig) -> None:
        """Update local engine config. Takes effect on next activation."""
        ...

    def update_cloud_config(self, config: CloudAPIConfig) -> None:
        """Update cloud engine config. Takes effect on next activation."""
        ...
```

---

## 3. Data Models

### 3.1 TranscriptionResult

The primary data structure flowing from the STT layer to the App Core:

| Field | Type | Description |
|-------|------|-------------|
| segments | list[TranscriptionSegment] | Individual segments with language and timing |
| full_text | str | Concatenated text for injection |
| primary_language | DetectedLanguage | Dominant language for UI display |
| processing_time_ms | float | For latency monitoring |

### 3.2 TranscriptionSegment

| Field | Type | Description |
|-------|------|-------------|
| text | str | The transcribed text for this segment |
| language | DetectedLanguage | Detected language for this segment |
| start_time | float | Start time in seconds (relative to chunk start) |
| end_time | float | End time in seconds |
| confidence | float | Model confidence (0.0-1.0) |
| is_partial | bool | If True, this segment may be updated by a later result |

### 3.3 Language Detection

Whisper natively detects the language of each segment. For mixed Hebrew/English (FR-005):
- Each `TranscriptionSegment` carries its own detected language.
- `TranscriptionResult.primary_language` is the language of the longest segment by duration.
- The UI displays `primary_language` in the menu bar and pill.

---

## 4. Dependencies

| Dependency | Usage |
|-----------|-------|
| faster-whisper | Local Whisper model inference (CTranslate2 backend) |
| httpx | Async HTTP client for OpenAI API |
| numpy | Audio data format (float32 arrays) |

**Internal dependencies:**
- `systemstt.errors` — `STTEngineError`, `ModelLoadError`, `ModelDownloadError`, `TranscriptionError`, `CloudAPIError` and subtypes
- `systemstt.config.models` — `SettingsModel` for reading engine configuration
- `systemstt.config.secure` — `SecureStore` for API key retrieval

---

## 5. Error Handling

### 5.1 Local Whisper Errors

| Error | Condition | Recovery |
|-------|-----------|----------|
| `ModelLoadError` | Model file corrupted or incompatible | Notify user; offer re-download |
| `ModelDownloadError` | Network failure during model download | Retry with exponential backoff; notify user |
| `TranscriptionError` | Inference failure (unexpected input, OOM) | Log error; skip chunk; continue dictation |

### 5.2 Cloud API Errors

| Error | Condition | Recovery |
|-------|-----------|----------|
| `APIAuthenticationError` | Invalid or expired API key | Stop dictation; notify user to check Settings |
| `APITimeoutError` | Request exceeds timeout_seconds | Retry up to max_retries; pill shows "retrying..." |
| `APIRateLimitError` | HTTP 429 from API | Exponential backoff; pill shows warning |
| `APIUnavailableError` | HTTP 5xx or network failure | Retry; if persistent, offer to switch to local engine |

### 5.3 Retry Strategy (Cloud)

```
Attempt 1: immediate
Attempt 2: wait 1.0s
Attempt 3: wait 2.0s
After 3 failures: raise APIUnavailableError
```

---

## 6. Notes for Developer

### 6.1 faster-whisper Usage

```python
# Initialization (simplified — actual implementation should be in a thread)
from faster_whisper import WhisperModel

model = WhisperModel(
    model_size_or_path="medium",
    device="cpu",
    compute_type="int8",  # Critical for Intel i9 performance
)

# Transcription
segments, info = model.transcribe(
    audio_array,            # numpy float32, 16kHz
    beam_size=5,
    language=None,          # None = auto-detect
    task="transcribe",
    vad_filter=True,        # Use Silero VAD to skip silence
    vad_parameters=dict(
        min_silence_duration_ms=500,
    ),
)

for segment in segments:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
    # segment.language gives detected language
```

### 6.2 Cloud API Usage

```python
# Simplified — actual implementation uses httpx async
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"file": ("audio.wav", wav_bytes, "audio/wav")},
        data={
            "model": "whisper-1",
            "response_format": "verbose_json",  # Includes word-level timestamps
            "language": None,  # Auto-detect
        },
        timeout=10.0,
    )
```

**Important:** The cloud API expects audio as a file upload (WAV, MP3, etc.), not raw PCM. The implementation must convert the numpy array to WAV bytes in memory before sending.

### 6.3 Model Loading Performance

Model loading is slow (several seconds for medium). Strategy:
- Load the model once at startup or when the engine is first activated.
- Keep the model in memory while the engine is active.
- Unload only when switching to a different engine or shutting down.
- Show a loading indicator in the UI during model load.

### 6.4 int8 Quantization

Using `compute_type="int8"` is critical for acceptable performance on the Intel i9 without GPU:
- `medium` model with int8: ~3-5x real-time on i9 (usable for near-real-time)
- `medium` model with float32: ~1-2x real-time (too slow for comfortable use)
- `small` model with int8: ~8-12x real-time (very responsive)

### 6.5 Streaming Strategy

**Local engine streaming:** faster-whisper does not natively support streaming. The strategy is:
1. Buffer audio in 3-5 second chunks.
2. Transcribe each chunk as a "final" result.
3. Use VAD (Voice Activity Detection) to find natural utterance boundaries.
4. Yield results as each chunk completes.

**Cloud API streaming:** The OpenAI Whisper API does not currently support real-time streaming either. The same chunking strategy applies, but with lower latency per chunk since the cloud hardware is faster.

For both engines, the `transcribe_stream()` method is an async generator that:
1. Accumulates audio from the async iterator.
2. When a silence boundary or time threshold is reached, transcribes the accumulated buffer.
3. Yields the result.
4. Continues with the next buffer.

### 6.6 Thread Safety

- `STTEngine` instances are NOT thread-safe. They must be accessed from a single thread (the transcription thread).
- The `EngineManager` is accessed from the main thread to switch engines. It must coordinate with the transcription thread via the App Core's event system.
- When switching engines: the App Core stops dictation, signals the transcription thread to shut down the old engine, initializes the new engine, and then allows dictation to restart.

### 6.7 Testing

- **Local engine tests:** Mock `faster_whisper.WhisperModel`. Test that audio is passed correctly, results are mapped to `TranscriptionResult`, errors are handled.
- **Cloud engine tests:** Mock `httpx.AsyncClient`. Test request format (WAV conversion), response parsing, retry logic, error mapping.
- **EngineManager tests:** Test engine switching, double-init prevention, shutdown cleanup.
- **Integration test (optional):** With the actual `faster-whisper` tiny model and a known audio file, verify end-to-end transcription. Mark as slow test.
