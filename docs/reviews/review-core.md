# Core Code Review: SystemSTT
**Reviewer:** Senior Code Reviewer (automated)
**Date:** 2026-02-28
**Scope:** errors.py, audio/*, stt/*, commands/*, platform/*, config/*, app.py
**Reference:** MRD v1.0, Specs 00-08

---

## Critical (Must Fix)

### C-01: SettingsStore atomic write leaks file descriptor before writing content
**File:** `/src/systemstt/config/store.py`, lines 74-94

`tempfile.mkstemp` returns an open file descriptor (`fd`). The code then calls `tmp_path.write_text()` which opens a **second** file handle to the same path, writing via a new descriptor. The original `fd` from `mkstemp` is closed in `finally`, but on some operating systems (and in edge cases on macOS) this can cause the `write_text` call to fail or produce a zero-byte file because `fd` is still open when `write_text` tries to write. More critically, if `tmp_path.write_text()` succeeds but `tmp_path.replace()` fails, the `fd` is closed in `finally` **after** the temp file has already been unlinked in the `except` block, potentially producing an `OSError`.

The spec (08-configuration.md, section 6.3) shows the intended pattern: use `os.fdopen(fd, "w")` to write through the original descriptor.

**Fix:** Use `os.fdopen(fd, "w")` to write through the mkstemp descriptor, or close `fd` immediately before calling `write_text`:

```python
import os
os.close(fd)  # close immediately, then write via Path
tmp_path.write_text(json_str, encoding="utf-8")
```

### C-02: `transcribe_stream` not implemented -- missing from STTEngine ABC and both engines
**Files:** `/src/systemstt/stt/base.py`, `cloud_api.py`, `local_whisper.py`

The spec (03-stt-engine.md, section 2.1) defines `transcribe_stream()` as an abstract method on `STTEngine`. Neither the ABC nor either implementation includes this method. This is the mechanism for streaming/partial transcription results (FR-002 real-time transcription, spec 00 section 6 Audio Chunking Strategy).

Without streaming, users must wait for an entire audio chunk to be transcribed before seeing any text -- violating the < 1 second latency target (NFR-002) for the cloud API and degrading the experience for FR-002.

**Impact:** FR-002 (real-time transcription) and NFR-002 (cloud latency < 1s) cannot be met for interactive use.

**Fix:** Add `transcribe_stream` to the ABC and implement chunked streaming in both engines, or document its deferral with a clear tracking mechanism.

### C-03: CloudAPIEngine `send_keystroke` missing error handling in `MacOSTextInjector`
**File:** `/src/systemstt/platform/macos/text_injector.py`, lines 121-150

`send_keystroke()` has no try/except block. If `CGEventCreateKeyboardEvent` returns `None` (which it does when accessibility permission is denied or the event source is invalid), `CGEventSetFlags(None, flags)` and `CGEventPost(kCGHIDEventTap, None)` will crash with a segfault or an unhandled `TypeError`.

By contrast, `inject_text()` wraps its logic in a try/except and checks `AXIsProcessTrusted`. This inconsistency means voice commands (which use `send_keystroke`) will crash the application on permission issues, while text injection will not.

**Fix:** Add the same try/except and `AXIsProcessTrusted` check to `send_keystroke`.

### C-04: MacOSHotkeyManager `_on_hotkey_pressed` is never connected to the Carbon event handler
**File:** `/src/systemstt/platform/macos/hotkey_manager.py`, lines 161-184

`_register_carbon_hotkey` calls `CarbonEvt.RegisterEventHotKey` but never installs a Carbon event handler (via `InstallEventHandler`) that invokes `_on_hotkey_pressed`. Without an event handler, the hotkey is registered with the system but pressing it will never trigger the callback. The `_handler_ref` field exists but is never set.

The spec (06-hotkey-lifecycle.md, section 6.1) shows the pattern: "Install a Carbon event handler for kEventHotKeyPressed."

**Impact:** FR-001 (global keyboard shortcut) is completely non-functional.

**Fix:** Install a Carbon event handler in `_register_carbon_hotkey` that calls `_on_hotkey_pressed`. Store the handler reference in `_handler_ref` and clean it up in `_unregister_carbon_hotkey`.

---

## Warnings (Should Fix)

### W-01: `asyncio.get_event_loop()` is deprecated for this use case
**Files:** `/src/systemstt/stt/local_whisper.py` lines 97, 150, 246; `/src/systemstt/stt/cloud_api.py` (no occurrence, but related)

`asyncio.get_event_loop()` is deprecated in Python 3.10+ for getting the running loop from within a coroutine. The recommended replacement is `asyncio.get_running_loop()`. Using `get_event_loop()` will emit a `DeprecationWarning` in Python 3.12+ and may raise an error in future versions.

**Fix:** Replace all `asyncio.get_event_loop()` with `asyncio.get_running_loop()`.

### W-02: Duplicate `EngineType` and `WhisperModelSize` enums across modules
**Files:** `/src/systemstt/config/models.py` (lines 18-23, 25-33) vs `/src/systemstt/stt/base.py` (lines 26-30) and `/src/systemstt/stt/local_whisper.py` (lines 42-49)

`EngineType` is defined in both `config/models.py` and `stt/base.py`. `WhisperModelSize` is defined in both `config/models.py` and `stt/local_whisper.py`. These are separate classes that happen to have the same values. Code that passes values from config to STT will silently work due to string comparison on `str, Enum` subclasses, but `isinstance` checks and `is` comparisons will fail. This is a maintenance hazard that will eventually cause a subtle bug.

**Fix:** Define these enums in one place (e.g., keep them in `stt/base.py` and `stt/local_whisper.py`, import into `config/models.py`), or create a shared `types.py` module.

### W-03: No text length validation or throttling in `inject_text`
**File:** `/src/systemstt/platform/macos/text_injector.py`, lines 91-119

The spec (05-text-injection.md, section 6.5) recommends: "Use CGEvent character-by-character for text up to 100 characters. Use clipboard-paste for longer text." The current implementation sends every character individually via CGEvent with no pacing or length threshold. For long transcriptions (FR-006 long-form dictation, 5+ minutes), this could overwhelm the target application with rapid keystroke events, causing dropped characters or lag.

**Fix:** Add a length check. For text > ~100 characters, fall back to clipboard-paste injection as the spec recommends. At minimum, add a small async sleep between batches of characters.

### W-04: `MacOSHotkeyManager.update_binding` rollback is broken
**File:** `/src/systemstt/platform/macos/hotkey_manager.py`, lines 111-149

On failure, the rollback code restores `self._binding`, `self._hotkey_ref`, and `self._handler_ref` to their old values. However, `_unregister_carbon_hotkey` was already called, which set `self._hotkey_ref = None` (line 176). So `old_hotkey_ref` was captured before the unregister, but the actual Carbon resource pointed to by that reference has been unregistered and is invalid. Restoring it means `self._hotkey_ref` now points to an unregistered hotkey. The next call to `unregister()` will attempt to unregister an invalid reference, likely causing a crash.

**Fix:** In the rollback path, actually re-register the old binding rather than just restoring stale references.

### W-05: `CloudAPIEngine` state can become stuck at `TRANSCRIBING`
**File:** `/src/systemstt/stt/cloud_api.py`, lines 145-164

If `_transcribe_with_retry` raises `APIAuthenticationError` (a non-retryable error), it is re-raised from `_do_transcribe`. The `finally` block at line 163 only resets state if `self._state == EngineState.TRANSCRIBING`. This works correctly in the current code. However, if the engine's `_state` is mutated by another coroutine between the `try` and `finally` (e.g., via `shutdown()` called from another task), the `finally` block won't reset state correctly. Both `CloudAPIEngine` and `LocalWhisperEngine` share this pattern.

This is a latent issue: the engines are not thread-safe (per spec 03, section 6.6) but they are used with `asyncio`, where concurrent tasks can interleave. A concurrent `shutdown()` call during transcription could leave state inconsistent.

**Fix:** Use a lock or document/enforce single-caller semantics for transcribe/shutdown interactions.

### W-06: `MacOSKeychainStore.exists()` fetches the full secret data just to check existence
**File:** `/src/systemstt/platform/macos/keychain.py`, lines 139-149

The `exists()` method queries with `kSecReturnData = True`, which causes the Keychain to decrypt and return the full secret. This is unnecessary for an existence check and is slightly wasteful. More importantly, it silently swallows ALL exceptions, including `KeychainAccessError` subclasses.

**Fix:** Remove `kSecReturnData` from the existence check query (just check the status code). Consider whether swallowing all exceptions in `exists()` is appropriate.

### W-07: No VAD (Voice Activity Detection) in audio pipeline
**Files:** `/src/systemstt/audio/recorder.py`, `/src/systemstt/stt/local_whisper.py`

The spec (03-stt-engine.md, section 6.1) recommends `vad_filter=True` with `vad_parameters=dict(min_silence_duration_ms=500)` for faster-whisper. The architecture overview (spec 00, section 6) describes silence detection (~800ms pause) to trigger buffer flush. Neither is implemented. The `_do_transcribe` method does not pass `vad_filter=True` to `model.transcribe()`.

Without VAD, the system must wait for fixed-size chunk boundaries before transcribing, adding unnecessary latency and sending silence to the STT engine (wasting compute).

**Fix:** Pass `vad_filter=True` to `model.transcribe()` in `LocalWhisperEngine._do_transcribe`.

### W-08: `SettingsModel.hotkey_modifiers` default is a mutable list literal
**File:** `/src/systemstt/config/models.py`, line 49

```python
hotkey_modifiers: list[str] = ["option"]
```

In Pydantic v2, mutable default values on `BaseModel` fields are technically safe (Pydantic deep-copies them). However, this deviates from the spec's recommended pattern (08-configuration.md uses `Field(default_factory=lambda: ["option"])`). Using the `Field` approach is more explicit and conventional.

**Fix:** Use `Field(default_factory=lambda: ["option"])` for clarity and spec compliance.

---

## Suggestions (Nice to Have)

### S-01: Add `__repr__` to error classes with context
Error classes in `errors.py` are all bare -- they only inherit from their parent and add docstrings. For debugging, it would be helpful for errors like `DeviceNotFoundError` or `APIRateLimitError` to carry structured context (e.g., device_id, HTTP status code) as attributes, not just embedded in the message string.

### S-02: `DeviceEnumerator` queries all devices for every method call
`get_device_by_id` and `get_default_device` both call `list_input_devices()`, which queries PortAudio every time. A short-lived cache (< 1 second) would reduce overhead if these are called frequently (e.g., during UI rendering).

### S-03: `CommandParser` could pre-build a lookup structure
The parser iterates over all commands and all trigger phrases on every `parse()` call. With 9 commands and ~2 phrases each, this is fine for v1. If custom commands are added (FR-021), consider building a trie or suffix map at construction time.

### S-04: `_parse_language` is duplicated in both `cloud_api.py` and `local_whisper.py`
Two identical functions with identical logic. Should be in a shared location (e.g., `stt/base.py` or a utility module).

### S-05: `AudioRecorder.on_audio_chunk` and `on_error` are public mutable attributes
These are plain attributes set directly on the instance (lines 53-54). Making them proper properties with setters would allow validation (e.g., rejecting callbacks during RECORDING state) and match the spec's property-style interface (02-audio-capture.md, section 2.1).

### S-06: Consider adding `EngineManager` to `stt/__init__.py` exports
The `EngineManager` class is not listed in the spec's directory structure (01-project-setup.md) as a separate file -- it is part of the STT engine layer but lives in its own file. This is fine, but the `stt/__init__.py` should re-export it for clean imports.

### S-07: `DictationStateMachine` uses `ValueError` for invalid transitions
The spec defines `SystemSTTError` as the root exception. Invalid state transitions currently raise `ValueError`, which callers cannot catch alongside other SystemSTT errors. Consider a custom `InvalidTransitionError(SystemSTTError)`.

### S-08: Spec mentions `SettingsManager` and `AppLifecycle` -- neither is implemented
The specs (08-configuration.md section 2.5 and 06-hotkey-lifecycle.md section 2.4) define `SettingsManager` (coordinates stores, change notifications) and `AppLifecycle` (startup/shutdown, dock, login items). Neither appears in the codebase. The `app.py` only contains the `DictationStateMachine`. This may be intentional (not yet implemented), but it means there is no orchestrator wiring components together.

---

## MRD Compliance

### Functional Requirements

| ID | Requirement | Status | Notes |
|----|-------------|--------|-------|
| FR-001 | Global keyboard shortcut | **BLOCKED** | `MacOSHotkeyManager` registers the hotkey but never installs the Carbon event handler (C-04). The hotkey will not fire. |
| FR-002 | Real-time transcription | **PARTIAL** | Audio capture and transcription work. `transcribe_stream` is missing (C-02), so partial/streaming results are unavailable. Latency for batch transcription depends on chunk size. |
| FR-003 | Text injection at cursor | **PASS** | `MacOSTextInjector.inject_text` uses CGEvent correctly. Hebrew/Unicode is supported via `CGEventKeyboardSetUnicodeString`. `send_keystroke` lacks error handling (C-03). |
| FR-004 | Hebrew and English support | **PASS** | `DetectedLanguage` enum includes ENGLISH and HEBREW. Both engines support auto-detection. Unicode text injection works for Hebrew. |
| FR-005 | Auto language detection | **PASS** | Whisper auto-detects language. `TranscriptionResult.primary_language` propagates detection. No manual toggle required. |
| FR-006 | Long-form dictation | **PARTIAL** | No inherent session time limit. However, no VAD/silence detection (W-07) means long sessions may have suboptimal chunking. No text length throttling (W-03) could cause issues with very long injections. |
| FR-007 | Voice commands | **PASS** | All 9 commands from the MRD are registered. Parser implements suffix matching and standalone-only logic correctly. `CommandExecutor` maps all actions to correct keystrokes. |
| FR-008 | Configurable STT engine | **PASS** | `EngineManager` supports hot-swapping between local and cloud engines without restart. |
| FR-009 | Persistent settings | **PASS** | `SettingsStore` saves to JSON with atomic writes. `SettingsModel` has correct defaults. Loads gracefully on corruption/missing file. |
| FR-010 | macOS support | **PASS** | Uses PyObjC for macOS APIs. Platform abstraction via ABCs supports future Windows port. |

### Non-Functional Requirements

| ID | Requirement | Target | Status | Notes |
|----|-------------|--------|--------|-------|
| NFR-001 | Local transcription latency | < 2s | **UNKNOWN** | Depends on model size and hardware. No benchmark in code. `run_in_executor` correctly offloads blocking inference. |
| NFR-002 | Cloud transcription latency | < 1s | **AT RISK** | No streaming (C-02). Batch transcription with 10s timeout. Latency depends on audio chunk size and network. |
| NFR-003 | Memory usage | < 2GB RAM | **UNKNOWN** | Model loaded in memory. No memory monitoring or limits in code. Medium int8 model is typically ~1.5GB. |
| NFR-004 | Idle CPU usage | < 1% | **PASS** | No audio capture or processing when idle. Recorder has IDLE state. No polling loops. |
| NFR-005 | Stability | No crashes | **AT RISK** | `send_keystroke` can crash on permission issues (C-03). Stale hotkey refs in rollback path (W-04). Missing Carbon event handler (C-04). |
| NFR-006 | API key security | OS keychain | **PASS** | API keys stored in macOS Keychain via `MacOSKeychainStore`. Not in config files. `CloudAPIConfig.api_key` is in memory only when needed. Note: API key appears in `Authorization` header in log at INFO level (line 117 of cloud_api.py logs `api_base_url` but not the key -- OK). |
| NFR-007 | Minimal setup | Sensible defaults | **PASS** | All `SettingsModel` defaults match the design spec. Cloud API is the default engine. Option+Space default hotkey. |
| NFR-008 | Cross-platform architecture | Core/platform separation | **PASS** | ABCs for `TextInjector`, `HotkeyManager`, `SecureStore`. Platform-specific code isolated in `platform/macos/`. Core logic is pure Python. |

---

## Verdict: **NEEDS CHANGES**

There are 4 critical issues that must be addressed before the core is production-ready:

1. **C-01** (SettingsStore FD leak) can cause data loss
2. **C-02** (missing `transcribe_stream`) blocks real-time transcription
3. **C-03** (no error handling in `send_keystroke`) can crash the app
4. **C-04** (hotkey handler never connected) makes FR-001 non-functional

The 8 warnings represent significant quality issues that should be addressed before release. The code is well-structured with clean abstractions, correct error hierarchies, and good spec alignment overall -- the issues identified are specific and fixable.
