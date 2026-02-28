# 00 — Architecture Overview
**Version:** 1.0
**Date:** 2026-02-28
**Status:** Draft

---

## 1. Goal

Define the high-level architecture for SystemSTT — a system-wide speech-to-text application for macOS that provides real-time dictation into any text field via a global hotkey. The architecture must satisfy all P0 and P1 requirements from the MRD while maintaining a clean separation that enables a future Windows port (NFR-008).

**MRD requirements addressed by this document:** All (FR-001 through FR-013, NFR-001 through NFR-008).

---

## 2. Technology Stack Decision

### 2.1 Language: Python 3.11+

**Rationale:**
- Native ecosystem for Whisper (OpenAI's `whisper` and `faster-whisper` packages are Python-first)
- Excellent async support (`asyncio`) for concurrent audio capture, transcription, and UI updates
- PyObjC provides full access to macOS Objective-C APIs (Accessibility, Carbon hotkeys, NSStatusItem, Keychain)
- Single language for the entire stack — no polyglot complexity for a solo developer
- The MRD notes no stack preference; Python is the natural fit for ML + audio

### 2.2 UI Framework: Qt 6 via PySide6

**Rationale:**
- Cross-platform (macOS + Windows in v2) with a single codebase — directly supports NFR-008
- Qt supports custom-drawn widgets, translucency, frameless windows — necessary for the design spec's custom dark theme, floating pill, and custom settings window
- QSystemTrayIcon provides menu bar / system tray integration on both platforms
- QSS (Qt Style Sheets) enables the design spec's token-based color system
- PySide6 is the official Qt for Python binding (LGPL, no licensing issues)
- Alternative considered: native SwiftUI/AppKit — rejected because it blocks the Windows port and forces a rewrite

### 2.3 Audio: sounddevice + numpy

**Rationale:**
- `sounddevice` wraps PortAudio — cross-platform, low-latency audio capture
- Direct access to raw PCM frames as numpy arrays, which Whisper expects
- Device enumeration API for FR-013 (audio input device selection)
- Callback-based streaming for real-time capture

### 2.4 Local STT: faster-whisper

**Rationale:**
- CTranslate2-based Whisper implementation — 4x faster than OpenAI's reference implementation on CPU
- Critical for the Intel i9 target (no GPU) — makes `small` and `medium` models viable for near-real-time use
- Same model quality as OpenAI Whisper, same model files
- Supports streaming/chunked transcription

### 2.5 Cloud STT: OpenAI Whisper API (via httpx)

**Rationale:**
- `httpx` is a modern async HTTP client — fits the async-first design principle
- OpenAI Whisper API supports the required languages (Hebrew + English)
- Streaming responses for low latency (NFR-002: < 1 second)

### 2.6 macOS Platform Integration: PyObjC

**Rationale:**
- Full access to all macOS frameworks from Python: Accessibility (AXUIElement), Carbon (hotkeys), Security (Keychain), AppKit (NSStatusItem, NSPanel), UserNotifications
- Avoids a native Swift/ObjC companion process — keeps the architecture as a single Python process
- Well-maintained, covers the entire macOS API surface

### 2.7 Summary Table

| Concern | Technology | License |
|---------|-----------|---------|
| Language | Python 3.11+ | -- |
| UI framework | PySide6 (Qt 6) | LGPL |
| Audio capture | sounddevice (PortAudio) | MIT |
| Audio processing | numpy | BSD |
| Local STT | faster-whisper (CTranslate2) | MIT |
| Cloud STT client | httpx | BSD |
| macOS integration | PyObjC | MIT |
| Settings persistence | JSON (pathlib + pydantic) | -- |
| Secure storage | macOS Keychain (via PyObjC Security) | -- |
| Packaging | PyInstaller or py2app | -- |
| Testing | pytest + pytest-asyncio + pytest-qt | MIT |

---

## 3. High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        SystemSTT Application                     │
│                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐  │
│  │   UI Layer    │   │  App Core    │   │  Platform Layer      │  │
│  │              │   │  (Orchestrator│   │                      │  │
│  │  Menu Bar    │   │  + State     │   │  HotkeyManager       │  │
│  │  Dropdown    │◄──┤  Machine)    ├──►│  TextInjector        │  │
│  │  Floating    │   │              │   │  KeychainStore       │  │
│  │   Pill       │   │              │   │  PermissionsChecker  │  │
│  │  Settings    │   │              │   │  NotificationSender  │  │
│  │  Window      │   └──────┬───────┘   └──────────────────────┘  │
│  └──────────────┘          │                                      │
│                            │                                      │
│           ┌────────────────┼────────────────┐                    │
│           │                │                │                    │
│           ▼                ▼                ▼                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ Audio Capture │ │  STT Engine  │ │ Voice Command│            │
│  │   Layer      │ │  Layer       │ │  Processor   │            │
│  │              │ │              │ │              │            │
│  │ AudioRecorder│ │ <<interface>>│ │ CommandParser│            │
│  │ DeviceEnum   │ │ STTEngine    │ │ CommandExec  │            │
│  │ LevelMeter   │ │   │         │ │              │            │
│  └──────────────┘ │   ├─Local   │ └──────────────┘            │
│                   │   │ Whisper  │                              │
│                   │   │         │                              │
│                   │   └─Cloud   │                              │
│                   │     API     │                              │
│                   └──────────────┘                              │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                  Configuration Layer                      │    │
│  │  SettingsModel (pydantic) │ SettingsStore │ SecureStore   │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Component Responsibilities

### 4.1 App Core (Orchestrator)

The central coordinator. Owns the dictation state machine, routes events between components, and manages the application lifecycle.

- **State machine:** IDLE <-> ACTIVE (with sub-states: ACTIVE+ERROR, ACTIVE+COMMAND)
- **Dictation flow:** Receives hotkey events -> starts/stops audio capture -> feeds audio to STT engine -> receives transcription -> routes to text injection or voice command processor
- **Event bus:** Qt signals/slots for loose coupling between components

### 4.2 Audio Capture Layer

Captures raw audio from the microphone and streams it to the STT engine.

- **AudioRecorder:** Manages the audio stream (start, stop, pause). Produces audio chunks as numpy arrays.
- **DeviceEnumerator:** Lists available input devices, detects device changes.
- **LevelMeter:** Computes RMS/peak levels for the UI level meter in Settings.

### 4.3 STT Engine Layer

Abstract interface with two implementations. Consumes audio chunks, produces transcription text.

- **STTEngine (ABC):** `transcribe(audio_chunk) -> TranscriptionResult` — the contract all engines implement
- **LocalWhisperEngine:** Uses `faster-whisper` for on-device transcription. Manages model loading/downloading.
- **CloudAPIEngine:** Uses `httpx` to stream audio to OpenAI's Whisper API and receive transcription.
- **TranscriptionResult:** Contains text, detected language, confidence, timing metadata.

### 4.4 Voice Command Processor

Intercepts transcription text before injection, detects command phrases, and executes actions.

- **CommandParser:** Pattern-matches transcription text against the command registry.
- **CommandExecutor:** Maps recognized commands to system actions (keystrokes, text manipulation).
- **CommandRegistry:** Static list of built-in commands (v1). Extensible for custom commands (v2).

### 4.5 Text Injection (Platform Layer)

Injects transcribed text into the focused application at the cursor position.

- **TextInjector (ABC):** `inject(text: str) -> None` — platform-abstracted interface.
- **MacOSTextInjector:** Uses macOS Accessibility API (AXUIElement) to set text at the cursor.
- Future: **WindowsTextInjector** using SendInput / UI Automation.

### 4.6 Hotkey Manager (Platform Layer)

Registers and listens for the global keyboard shortcut.

- **HotkeyManager (ABC):** `register(shortcut, callback)`, `unregister()`
- **MacOSHotkeyManager:** Uses Carbon `RegisterEventHotKey` via PyObjC.
- Emits events consumed by the App Core to toggle dictation.

### 4.7 UI Layer

All visual components, built with PySide6, styled to match the design spec.

- **MenuBarWidget:** NSStatusItem-backed (via Qt) menu bar icon with language label.
- **DropdownMenu:** Custom-painted popup matching the design spec (not native NSMenu).
- **FloatingPill:** QWidget-based floating panel — status, preview, error display.
- **SettingsWindow:** Tabbed settings dialog (General, Engine, Audio, Commands).
- All UI components observe the app state and update reactively via Qt signals.

### 4.8 Configuration Layer

Manages user preferences — load, save, validate, and provide defaults.

- **SettingsModel (pydantic):** Strongly typed settings with defaults and validation.
- **SettingsStore:** JSON file persistence (`~/.config/systemstt/settings.json`).
- **SecureStore:** macOS Keychain wrapper for API key storage (via PyObjC Security framework).

---

## 5. Data Flow: Dictation Session

```
User presses ⌥Space
        │
        ▼
┌─ HotkeyManager ─┐    Signal: hotkey_pressed
│  detects keypress ├──────────────────────────────┐
└──────────────────┘                               │
                                                    ▼
                                          ┌─ App Core ──────────┐
                                          │  State: IDLE→ACTIVE  │
                                          │  1. Start AudioRec   │
                                          │  2. Signal UI: active│
                                          └──────────┬───────────┘
                                                     │
              ┌──────────────────────────────────────┘
              │
              ▼
┌─ AudioRecorder ──┐    Audio chunks (numpy arrays)
│  captures PCM    ├──────────────────────────────┐
│  16kHz mono      │                               │
└──────────────────┘                               │
                                                    ▼
                                          ┌─ STT Engine ────────┐
                                          │  (Local or Cloud)    │
                                          │  transcribes audio   │
                                          └──────────┬───────────┘
                                                     │
                                          TranscriptionResult
                                          (text, language, ...)
                                                     │
                                                     ▼
                                          ┌─ App Core ──────────┐
                                          │  receives text       │
                                          └──────────┬───────────┘
                                                     │
                                    ┌────────────────┼────────────────┐
                                    │                                  │
                                    ▼                                  ▼
                          ┌─ Voice Command ──┐              ┌─ Text Injector ──┐
                          │  Parser           │              │  injects into    │
                          │  "delete last     │              │  focused app at  │
                          │   word" detected? │              │  cursor position │
                          └──────┬────────────┘              └──────────────────┘
                                 │
                          Yes: execute action
                          No: pass text to TextInjector
```

---

## 6. Data Flow: Audio Chunking Strategy

The audio capture and STT engine coordinate via a chunking strategy optimized for perceived latency:

```
Audio Stream (continuous 16kHz PCM)
        │
        ├── Chunk every ~500ms (for streaming/partial results)
        │       │
        │       ▼
        │   STT Engine: partial transcription → UI preview
        │
        ├── On silence detection (~800ms pause): flush buffer
        │       │
        │       ▼
        │   STT Engine: final transcription → Text Injector
        │
        └── On hotkey press (stop): flush remaining → final transcription
```

- **Streaming mode (Cloud API):** Audio is streamed continuously; partial results update the pill preview.
- **Chunked mode (Local Whisper):** Audio is buffered in ~3-5 second chunks (configurable based on model size) and sent to the model. Partial results are shown as each chunk completes.
- **Voice Activity Detection (VAD):** Simple energy-based silence detection to segment utterances. No external VAD library needed for v1 given the controlled mic environment.

---

## 7. Threading and Concurrency Model

```
┌──────────────────────────────────────────────────────────┐
│                    Main Thread (Qt Event Loop)            │
│                                                           │
│  - All UI rendering and updates                          │
│  - Qt signal/slot dispatch                               │
│  - Settings window interaction                           │
│  - Menu bar and dropdown                                 │
└──────────────────────┬───────────────────────────────────┘
                       │ Qt signals
                       │
┌──────────────────────┼───────────────────────────────────┐
│                Audio Thread (dedicated)                    │
│                                                           │
│  - sounddevice callback runs on PortAudio's thread       │
│  - Pushes audio chunks to a thread-safe queue            │
│  - Level meter computation                               │
└──────────────────────┬───────────────────────────────────┘
                       │ queue.Queue
                       │
┌──────────────────────┼───────────────────────────────────┐
│             Transcription Thread (dedicated)               │
│                                                           │
│  - Pulls audio chunks from queue                         │
│  - Runs STT engine (local model inference or API call)   │
│  - Emits Qt signals with transcription results           │
│  - For cloud: uses asyncio event loop in this thread     │
└──────────────────────┬───────────────────────────────────┘
                       │ Qt signal (thread-safe)
                       │
┌──────────────────────┼───────────────────────────────────┐
│                    Main Thread                            │
│                                                           │
│  - Receives transcription results                        │
│  - Routes to voice command parser or text injector       │
│  - Updates UI (pill, menu bar)                           │
└──────────────────────────────────────────────────────────┘
```

**Key design decisions:**
- The Qt main thread is NEVER blocked by audio capture or transcription.
- `queue.Queue` bridges the audio thread and transcription thread (thread-safe, bounded).
- Qt signals (which are thread-safe) bridge the transcription thread back to the main thread.
- Local Whisper inference runs on the transcription thread — it is CPU-bound and must not block UI.
- Cloud API calls use `httpx` async within the transcription thread's own asyncio loop.

---

## 8. Error Handling Strategy

### 8.1 Error Hierarchy

```
SystemSTTError (base)
├── AudioError
│   ├── DeviceNotFoundError
│   ├── DeviceDisconnectedError
│   └── AudioCaptureError
├── STTEngineError
│   ├── ModelLoadError
│   ├── ModelDownloadError
│   ├── TranscriptionError
│   └── CloudAPIError
│       ├── APIAuthenticationError
│       ├── APITimeoutError
│       ├── APIRateLimitError
│       └── APIUnavailableError
├── TextInjectionError
│   ├── AccessibilityPermissionError
│   └── InjectionFailedError
├── HotkeyError
│   └── HotkeyRegistrationError
└── ConfigurationError
    ├── SettingsLoadError
    └── KeychainAccessError
```

### 8.2 Error Routing

| Error Type | During Dictation | While Idle |
|------------|-----------------|------------|
| DeviceDisconnectedError | Pill: inline error, stop dictation | macOS notification |
| APITimeoutError | Pill: "API timeout — retrying..." with retry | Logged |
| APIUnavailableError | Pill: "Cloud API unavailable. Switch to local?" | macOS notification |
| AccessibilityPermissionError | Pill: inline error, prompt to fix | First-launch dialog |
| ModelLoadError | Pill: inline error | macOS notification |

---

## 9. Security Considerations

| Concern | Approach | MRD Ref |
|---------|---------|---------|
| API key storage | macOS Keychain via Security framework (PyObjC). Never stored in plaintext config. | NFR-006 |
| API key in memory | Loaded into memory only when needed; not logged, not included in error messages. | -- |
| Audio data | Processed in memory only. Not persisted to disk. Local model processes on-device. Cloud API sends over HTTPS. | MRD Section 7 |
| Accessibility permissions | Requested explicitly. Graceful degradation if denied. | MRD Section 9 |

---

## 10. Cross-Platform Strategy (NFR-008)

The architecture isolates platform-specific code behind abstract interfaces:

```
Core (platform-agnostic)          Platform (macOS v1, Windows v2)
─────────────────────────         ──────────────────────────────
AudioRecorder                     (uses sounddevice — cross-platform)
STTEngine (ABC)                   (pure Python — cross-platform)
VoiceCommandProcessor             (pure Python — cross-platform)
SettingsModel                     (pure Python — cross-platform)
SettingsStore                     (pure Python — cross-platform)
UI Layer (PySide6)                (cross-platform with minor tweaks)

TextInjector (ABC)          →     MacOSTextInjector / WindowsTextInjector
HotkeyManager (ABC)         →     MacOSHotkeyManager / WindowsHotkeyManager
SecureStore (ABC)            →     MacOSKeychainStore / WindowsCredentialStore
PermissionsChecker (ABC)     →     MacOSPermissions / WindowsPermissions
NotificationSender (ABC)     →     MacOSNotifications / WindowsToastNotifications
```

Platform implementations are selected at startup via a factory based on `sys.platform`. All business logic depends only on the abstract interfaces.

---

## 11. Implementation Order

The developer should implement components in this order, each building on the previous:

| Phase | Component | Spec | Depends On |
|-------|-----------|------|------------|
| 1 | Project setup, skeleton, config | 01-project-setup | -- |
| 2 | Configuration and persistence | 08-configuration | Phase 1 |
| 3 | Audio capture | 02-audio-capture | Phase 1 |
| 4 | STT engine abstraction + Cloud API | 03-stt-engine | Phase 3 |
| 5 | STT engine: Local Whisper | 03-stt-engine | Phase 3 |
| 6 | Voice command processor | 04-voice-commands | Phase 4 |
| 7 | Text injection (macOS) | 05-text-injection | Phase 1 |
| 8 | Hotkey manager (macOS) | 06-hotkey-lifecycle | Phase 1 |
| 9 | App core / orchestrator | 06-hotkey-lifecycle | Phase 2-8 |
| 10 | UI: Menu bar + dropdown | 07-ui-layer | Phase 9 |
| 11 | UI: Floating pill | 07-ui-layer | Phase 9 |
| 12 | UI: Settings window | 07-ui-layer | Phase 9 |
| 13 | Integration testing + polish | -- | All |

**Rationale:** Start with core infrastructure (config, audio, STT), then platform integration (text injection, hotkeys), then the orchestrator that wires everything together, and finally the UI that observes and drives the orchestrator.

---

## 12. Key Architectural Decisions Record

| # | Decision | Alternatives Considered | Rationale |
|---|----------|------------------------|-----------|
| ADR-01 | Python for the entire stack | Swift (native, macOS-only), Electron (heavy), Rust (no ML ecosystem) | Best Whisper ecosystem, PyObjC for macOS APIs, single language |
| ADR-02 | PySide6 for UI | SwiftUI (no Windows), Tkinter (limited), Electron (heavy) | Cross-platform, custom-drawn widgets, translucency support |
| ADR-03 | faster-whisper over openai-whisper | openai-whisper (reference, 4x slower on CPU) | Intel i9 has no GPU; faster-whisper is essential for usable local inference |
| ADR-04 | Dedicated threads for audio/transcription | asyncio-only (GIL issues with CPU-bound whisper), multiprocessing (complex IPC) | Clean separation, Qt-friendly, bounded complexity |
| ADR-05 | Qt signals for inter-thread communication | raw callbacks (thread-unsafe), asyncio queues (doesn't integrate with Qt loop) | Thread-safe, native to Qt, automatic main-thread dispatch |
| ADR-06 | JSON config + Keychain for secrets | SQLite (overkill), plaintext (insecure), plist (macOS-only) | Simple, human-readable config; OS-level secret storage |
| ADR-07 | Abstract interfaces for all platform code | Direct macOS calls everywhere | Enables Windows port (NFR-008) without refactoring core logic |
