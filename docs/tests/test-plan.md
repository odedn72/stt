# SystemSTT Test Plan
**Version:** 1.0
**Date:** 2026-02-28
**Author:** QA Engineer (TDD Mode 1)
**Status:** Tests Written, Awaiting Implementation

---

## 1. Overview

This document summarizes the test coverage plan for SystemSTT. All tests were written BEFORE implementation (TDD Mode 1) based on the specifications in `docs/specs/`. Tests are designed to fail until the corresponding implementation code is written.

### 1.1 Testing Framework

| Tool | Purpose |
|------|---------|
| pytest >= 8.0 | Test runner |
| pytest-asyncio >= 0.23 | Async test support |
| pytest-qt >= 4.3 | Qt widget testing |
| pytest-cov >= 4.1 | Coverage reporting |

### 1.2 Testing Principles

- Every test function tests ONE behavior
- Descriptive names: `test_[unit]_[scenario]_[expected_result]`
- No real external API calls -- all external dependencies are mocked
- Shared fixtures in `tests/conftest.py`
- Target: >80% code coverage

---

## 2. Test File Structure

```
tests/
    conftest.py                      # Shared fixtures (audio chunks, settings, mocks)
    test_errors.py                   # Error hierarchy (spec 00)
    test_app.py                      # State machine + orchestrator (spec 06)
    audio/
        __init__.py
        test_audio_recorder.py       # AudioRecorder (spec 02)
        test_device_enumerator.py    # DeviceEnumerator (spec 02)
        test_level_meter.py          # LevelMeter (spec 02)
    stt/
        __init__.py
        test_engine_abc.py           # STTEngine ABC + data models (spec 03)
        test_local_whisper.py        # LocalWhisperEngine (spec 03)
        test_cloud_api.py            # CloudAPIEngine (spec 03)
        test_engine_manager.py       # EngineManager (spec 03)
    commands/
        __init__.py
        test_command_registry.py     # CommandRegistry (spec 04)
        test_command_parser.py       # CommandParser (spec 04)
        test_command_executor.py     # CommandExecutor (spec 04)
    platform/
        __init__.py
        test_text_injector.py        # TextInjector ABC + MacOSTextInjector (spec 05)
        test_hotkey_manager.py       # HotkeyManager ABC + MacOSHotkeyManager (spec 06)
    config/
        __init__.py
        test_settings_model.py       # SettingsModel pydantic (spec 08)
        test_settings_store.py       # SettingsStore JSON persistence (spec 08)
        test_secure_store.py         # SecureStore ABC + MacOSKeychainStore (spec 08)
    ui/
        __init__.py
        test_menu_bar.py             # MenuBarWidget (spec 07)
        test_floating_pill.py        # FloatingPill (spec 07)
        test_settings_window.py      # SettingsWindow (spec 07)
```

---

## 3. Test Coverage by Component

### 3.1 Error Hierarchy (`test_errors.py`) -- Spec 00

| Category | Tests | Coverage |
|----------|-------|----------|
| Inheritance chain | 15 tests | Every exception inherits from the correct parent |
| Message propagation | 5 tests | Error messages are preserved |
| Catch-as-base | 6 tests | Subclass errors caught via base class |

**Total: ~26 tests**

### 3.2 Audio Capture Layer -- Spec 02

#### AudioRecorder (`test_audio_recorder.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| AudioConfig defaults | 6 tests | sample_rate, channels, dtype, chunk_duration, device_id |
| RecorderState enum | 3 tests | IDLE, RECORDING, ERROR values |
| Lifecycle (start/stop) | 7 tests | State transitions, stream open/close |
| Callbacks | 4 tests | on_audio_chunk, on_error setters |
| Config update | 2 tests | While idle, while recording (restart) |
| Error handling | 2 tests | AudioCaptureError, DeviceNotFoundError |

**Total: ~24 tests**

#### DeviceEnumerator (`test_device_enumerator.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| AudioDevice model | 2 tests | Fields, frozen |
| List input devices | 4 tests | Filtering, empty list, default marking |
| Get specific device | 4 tests | By ID, default, not found, output-only |
| Refresh | 1 test | Updated device list |

**Total: ~11 tests**

#### LevelMeter (`test_level_meter.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| AudioLevel enum | 5 tests | All 5 values |
| LevelReading model | 2 tests | Fields, frozen |
| Silence detection | 2 tests | Classification, dBFS range |
| Quiet audio | 2 tests | Classification, dBFS range |
| Normal audio | 2 tests | Classification, dBFS range |
| Loud audio | 1 test | Classification |
| Clipping detection | 2 tests | Classification, peak dBFS |
| Edge cases | 4 tests | Empty chunk, single sample, peak >= rms, return type |

**Total: ~20 tests**

### 3.3 STT Engine Layer -- Spec 03

#### Engine ABC & Data Models (`test_engine_abc.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| DetectedLanguage enum | 3 tests | EN, HE, UNKNOWN |
| EngineType enum | 2 tests | LOCAL_WHISPER, CLOUD_API |
| EngineState enum | 5 tests | All 5 states |
| TranscriptionSegment | 5 tests | Fields, frozen, Hebrew, partial, confidence |
| TranscriptionResult | 4 tests | Fields, multiple segments, frozen, empty |
| ABC instantiation | 1 test | Cannot instantiate abstract class |

**Total: ~20 tests**

#### LocalWhisperEngine (`test_local_whisper.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| WhisperModelSize enum | 1 test | All 5 sizes |
| LocalWhisperConfig | 6 tests | Defaults (model, device, compute, beam, workers, custom) |
| Lifecycle | 5 tests | Engine type, init state, initialize, failure, shutdown |
| Transcription | 5 tests | Success, language hint, not-init error, failure, empty |
| Model management | 4 tests | is_available, is_model_downloaded, get_model_info, download |

**Total: ~21 tests**

#### CloudAPIEngine (`test_cloud_api.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| CloudAPIConfig | 6 tests | All defaults and custom values |
| Lifecycle | 5 tests | Engine type, init state, initialize, shutdown, availability |
| Transcription success | 2 tests | English, Hebrew |
| Transcription errors | 5 tests | Auth (401), timeout, rate limit (429), server (500), not-init |
| API key validation | 2 tests | Valid key, invalid key |
| Retry logic | 2 tests | Max retries, success after retry |

**Total: ~22 tests**

#### EngineManager (`test_engine_manager.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| Initialization | 2 tests | Initial state (no active engine) |
| Activation | 4 tests | Cloud, local, switching (shutdown prev), failure |
| Shutdown | 2 tests | Active engine, no engine |
| Config update | 2 tests | Local config, cloud config |

**Total: ~10 tests**

### 3.4 Voice Command Processor -- Spec 04

#### CommandRegistry (`test_command_registry.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| CommandAction enum | 1 test | All 9 actions |
| VoiceCommand model | 2 tests | Fields, frozen |
| Registry completeness | 9 tests | One per built-in command |
| Registry queries | 2 tests | get_command_by_action |
| Command data quality | 3 tests | Trigger phrases, display names, confirmation text |
| Specific trigger phrases | 3 tests | DELETE_LAST_WORD, UNDO, STOP_DICTATION phrases |

**Total: ~20 tests**

#### CommandParser (`test_command_parser.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| Basic matching | 4 tests | Standalone, no match, suffix, text_before |
| Case insensitivity | 3 tests | Uppercase, mixed case, title case |
| Punctuation handling | 4 tests | Period, comma, exclamation, question mark |
| Whitespace normalization | 3 tests | Extra spaces, leading/trailing, tabs |
| Standalone vs suffix | 5 tests | Copy standalone, embedded, undo, multi-word suffix |
| Boundary detection | 2 tests | Command in middle (should not match) |
| All trigger phrases | 17 parametrized tests | Every trigger phrase from spec |
| Enabled/disabled toggle | 3 tests | Default, disabled, re-enabled |
| ParseResult model | 2 tests | No command, with text_before |
| Edge cases | 5 tests | Empty, whitespace, very long, special chars, Hebrew prefix |

**Total: ~48 tests**

#### CommandExecutor (`test_command_executor.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| Per-action execution | 8 tests | One per action (keystrokes sent) |
| STOP_DICTATION special | 2 tests | Calls callback, no text injector |
| Error handling | 1 test | TextInjectionError propagation |

**Total: ~11 tests**

### 3.5 Platform Layer -- Specs 05, 06

#### TextInjector (`test_text_injector.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| ABC | 1 test | Cannot instantiate |
| KeyModifier enum | 4 tests | All 4 values |
| SpecialKey enum | 1 test | All 11 values |
| inject_text | 6 tests | English, Hebrew, mixed, empty, failure, special chars |
| send_keystroke | 5 tests | Return, backspace, with modifiers, multiple modifiers, none |
| Permissions | 4 tests | Granted, denied, request, inject without permission |

**Total: ~21 tests**

#### HotkeyManager (`test_hotkey_manager.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| HotkeyBinding model | 7 tests | Default, fields, display, roundtrip, frozen, equality |
| ABC | 1 test | Cannot instantiate |
| Registration | 4 tests | Register, current_binding, initial state |
| Unregistration | 2 tests | After register, when not registered |
| Update binding | 2 tests | Success, failure |
| Error handling | 1 test | Registration failure |

**Total: ~17 tests**

### 3.6 Configuration Layer -- Spec 08

#### SettingsModel (`test_settings_model.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| Default values | 16 tests | Every field matches design spec |
| Enum fields | 5 tests | EngineType, WhisperModelSize, from-string |
| Serialization | 4 tests | JSON roundtrip, dict roundtrip, custom, format |
| Forward compatibility | 3 tests | Unknown keys, missing keys, partial dict |
| Validation | 5 tests | Invalid engine, invalid model, pill positions, modifiers |

**Total: ~33 tests**

#### SettingsStore (`test_settings_store.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| Load | 6 tests | Nonexistent, valid, corrupted, partial, unknown keys, empty |
| Save | 5 tests | Create file, create dirs, valid JSON, roundtrip, overwrite |
| File path | 2 tests | Configured path, default path |
| Atomic write | 2 tests | No temp files left, readable after write |

**Total: ~15 tests**

#### SecureStore (`test_secure_store.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| ABC | 1 test | Cannot instantiate |
| Service name | 1 test | "systemstt" |
| set() | 3 tests | Store new, update existing, failure |
| get() | 3 tests | Found, not found, failure |
| delete() | 2 tests | Existing, nonexistent |
| exists() | 2 tests | Found, not found |

**Total: ~12 tests**

### 3.7 UI Layer -- Spec 07

#### MenuBarWidget (`test_menu_bar.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| States | 4 tests | Idle, active, error, language update |
| Language label | 2 tests | Default EN, update to HE |
| Dropdown status | 2 tests | Active, idle |

**Total: ~8 tests**

#### FloatingPill (`test_floating_pill.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| Lifecycle | 2 tests | Show, hide |
| Language | 2 tests | EN, HE |
| Elapsed time | 3 tests | Zero, short, long |
| Preview text | 5 tests | English, Hebrew, mixed BiDi, hide, empty |
| Errors/warnings | 3 tests | Error, warning, default |
| Command confirmation | 2 tests | Single, all 9 confirmations |
| Expansion | 1 test | Clear expansion |
| Position | 2 tests | Set, reset |

**Total: ~20 tests**

#### SettingsWindow (`test_settings_window.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| Creation | 1 test | Window creates without error |
| Tab switching | 4 tests | All 4 tabs |
| Settings population | 2 tests | Custom settings, defaults |
| Status indicators | 6 tests | API status (3), model status (2), download progress |
| Audio devices | 2 tests | Device list, empty list |
| Audio level | 1 test | Level meter update |

**Total: ~16 tests**

### 3.8 App Core / State Machine -- Spec 06

#### DictationStateMachine (`test_app.py`)

| Category | Tests | Coverage |
|----------|-------|----------|
| DictationState enum | 5 tests | All 5 states |
| StateTransition model | 3 tests | Fields, with error, frozen |
| Initialization | 3 tests | Initial state, callback default, callback setter |
| Valid transitions | 8 tests | All valid from/to pairs per spec |
| Invalid transitions | 10 tests | All major invalid transitions |
| can_transition_to | 7 tests | Various state queries |
| Callbacks | 5 tests | Invoked, receives transition, error, not on invalid, count |
| Full lifecycle | 4 tests | Happy path, error recovery, active error, multiple sessions |

**Total: ~45 tests**

---

## 4. Coverage Summary

| Component | Test File | Approx. Tests |
|-----------|-----------|---------------|
| Error hierarchy | test_errors.py | 26 |
| AudioRecorder | audio/test_audio_recorder.py | 24 |
| DeviceEnumerator | audio/test_device_enumerator.py | 11 |
| LevelMeter | audio/test_level_meter.py | 20 |
| STTEngine ABC | stt/test_engine_abc.py | 20 |
| LocalWhisperEngine | stt/test_local_whisper.py | 21 |
| CloudAPIEngine | stt/test_cloud_api.py | 22 |
| EngineManager | stt/test_engine_manager.py | 10 |
| CommandRegistry | commands/test_command_registry.py | 20 |
| CommandParser | commands/test_command_parser.py | 48 |
| CommandExecutor | commands/test_command_executor.py | 11 |
| TextInjector | platform/test_text_injector.py | 21 |
| HotkeyManager | platform/test_hotkey_manager.py | 17 |
| SettingsModel | config/test_settings_model.py | 33 |
| SettingsStore | config/test_settings_store.py | 15 |
| SecureStore | config/test_secure_store.py | 12 |
| MenuBarWidget | ui/test_menu_bar.py | 8 |
| FloatingPill | ui/test_floating_pill.py | 20 |
| SettingsWindow | ui/test_settings_window.py | 16 |
| State Machine | test_app.py | 45 |
| **TOTAL** | **20 test files** | **~420 tests** |

---

## 5. Mocking Strategy

| External Dependency | Mock Target | Used In |
|---------------------|------------|---------|
| sounddevice | `systemstt.audio.recorder.sd` | test_audio_recorder, test_device_enumerator |
| faster-whisper | `systemstt.stt.local_whisper.WhisperModel` | test_local_whisper |
| httpx | `systemstt.stt.cloud_api.httpx.AsyncClient` | test_cloud_api |
| Quartz (CGEvent*) | `systemstt.platform.macos.text_injector.CGEvent*` | test_text_injector |
| Carbon (CarbonEvt) | `systemstt.platform.macos.hotkey_manager.CarbonEvt` | test_hotkey_manager |
| Security (SecItem*) | `systemstt.platform.macos.keychain.SecItem*` | test_secure_store |
| AXIsProcessTrusted | `systemstt.platform.macos.text_injector.AXIsProcessTrusted` | test_text_injector |
| PySide6 | Various `QWidget`, `QSystemTrayIcon`, `QApplication` | UI tests |

---

## 6. Running the Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=systemstt --cov-report=term-missing

# Specific module
pytest tests/stt/test_cloud_api.py

# Specific test class
pytest tests/test_app.py::TestDictationStateMachineValidTransitions

# Verbose output
pytest -v
```

---

## 7. Notes

- All tests are written in TDD Mode 1 (before implementation)
- All tests will FAIL until the corresponding source code is implemented
- Tests import from the public interfaces defined in the specs
- The developer should implement each component, run its tests, and iterate until all pass
- After all components are implemented, run the full test suite for integration verification
