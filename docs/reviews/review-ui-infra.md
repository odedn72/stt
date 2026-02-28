# Code Review: UI & Infrastructure Components
**Reviewer:** Senior Code Reviewer (automated)
**Date:** 2026-02-28
**Scope:** UI layer (menu_bar, floating_pill, settings_window), infrastructure (logging, shutdown, __main__, CI, build, config)
**Reference Docs:** design-spec.md, mrd.md, 07-ui-layer.md

---

## Critical (Must Fix)

### C-01: UI widgets are plain Python objects, not QWidget subclasses — no actual rendering

**Files:** `src/systemstt/ui/menu_bar.py`, `src/systemstt/ui/floating_pill.py`, `src/systemstt/ui/settings_window.py`

All three UI classes are implemented as plain Python objects that store state in instance variables but never actually render anything. They do not subclass `QWidget`, `QSystemTrayIcon`, or any Qt class. The spec (`07-ui-layer.md` sections 2.2-2.5) explicitly requires:

- `MenuBarWidget` to use `QSystemTrayIcon` with composite icon rendering
- `FloatingPill` to subclass `QWidget` with `FramelessWindowHint | WindowStaysOnTopHint | Tool` flags and `WA_TranslucentBackground`
- `SettingsWindow` to subclass `QWidget` with `FramelessWindowHint | Window` flags

As currently written, these are data-holder stubs that cannot display anything on screen. This is the most significant gap in the reviewed code.

### C-02: Missing `theme.py` — no design tokens or QSS generation

**Expected at:** `src/systemstt/ui/theme.py`

The spec (`07-ui-layer.md` section 2.1) defines `DesignTokens` dataclass and `generate_qss()` function as the single source of truth for all colors, typography, and spacing. This file does not exist. Without it:

- No design tokens are enforced in code
- No QSS stylesheet can be generated for the QApplication
- All design spec compliance is impossible to verify programmatically

### C-03: Missing `DropdownMenu` component

**Expected at:** `src/systemstt/ui/dropdown_menu.py` (or similar)

The spec (`07-ui-layer.md` section 2.3) defines a `DropdownMenu(QWidget)` class that is a custom-drawn translucent dropdown (explicitly NOT a native QMenu). The design spec (section 4.3) provides detailed layout, dimensions, and behavior. This component is entirely absent.

### C-04: Missing Qt Signals on all UI widgets

**Files:** `src/systemstt/ui/menu_bar.py`, `src/systemstt/ui/floating_pill.py`, `src/systemstt/ui/settings_window.py`

The spec defines the following required signals that are missing from the implementations:

- `MenuBarWidget`: `dictation_toggle_requested`, `preview_toggle_requested`, `settings_requested`, `quit_requested`
- `FloatingPill`: `position_changed(int, int)`
- `SettingsWindow`: `settings_changed(str, object)`, `hotkey_changed(object)`, `engine_changed(str)`, `api_key_changed(str)`, `model_download_requested(str)`

Without these signals, the UI cannot communicate user actions to the App Core, breaking the reactive signal/slot architecture described in section 6.10 of the UI spec.

### C-05: `SensitiveDataFilter._redact()` only redacts formatted log messages, not `args`

**File:** `src/systemstt/logging_config.py`, line 57-65

The filter checks `record.msg` (the format string) but does not inspect `record.args` (the values interpolated into the format string). If a caller writes:

```python
logger.info("Connecting with key %s", api_key_value)
```

The format string `"Connecting with key %s"` does not contain any sensitive pattern, so the filter passes it through unredacted. The actual secret is in `record.args`, which is never checked. The filter should also scan the fully formatted message (via `record.getMessage()`).

### C-06: Version hardcoded in three places — will drift

**Files:** `src/systemstt/__init__.py` (line 3), `systemstt.spec` (lines 132-133), `pyproject.toml` (line 3)

The version string `"0.1.0"` is hardcoded in three separate locations:
- `__init__.py`: `__version__ = "0.1.0"`
- `systemstt.spec`: `CFBundleVersion` and `CFBundleShortVersionString`
- `pyproject.toml`: `version = "0.1.0"`

These will inevitably diverge. The `.spec` file should read the version from `__init__.py` or `pyproject.toml` dynamically (e.g., `importlib.metadata` or by reading the file). The `build_app.sh` script already tries to read the version dynamically (line 21), which would give the correct value for its context, but the spec file does not.

---

## Warnings (Should Fix)

### W-01: `build_app.sh` continues building after test failure

**File:** `scripts/build_app.sh`, lines 117-119

```bash
if ! pytest --quiet --tb=short 2>/dev/null; then
    warn "  Tests failed — building anyway (use 'make test' to see details)"
fi
```

The script intentionally proceeds with the build even when tests fail. While the comment suggests this is deliberate, it defeats the purpose of "fail fast" pre-build checks stated on line 104. A build from code with failing tests should not be distributed. At minimum, this should be a flag (e.g., `--force`) rather than the default behavior.

### W-02: `build_app.sh` suppresses pytest stderr

**File:** `scripts/build_app.sh`, line 117

`pytest --quiet --tb=short 2>/dev/null` redirects stderr to `/dev/null`. If pytest crashes or has import errors, the diagnostic output is lost. This makes debugging build failures unnecessarily difficult.

### W-03: Signal handler calls `sys.exit(0)` after `shutdown()` — may conflict with Qt event loop

**File:** `src/systemstt/shutdown.py`, lines 113-117

```python
def _signal_handler(signum: int, _frame: object) -> None:
    sig_name = signal.Signals(signum).name
    logger.info("Received %s — initiating graceful shutdown", sig_name)
    self.shutdown()
    sys.exit(0)
```

When the Qt event loop is running, calling `sys.exit(0)` from a signal handler can bypass Qt's cleanup (e.g., `QApplication.aboutToQuit` signal). The `__main__.py` comments (lines 79-80) show the planned pattern is `app.aboutToQuit.connect(shutdown_manager.shutdown)` followed by `sys.exit(app.exec())`. The signal handler should call `QApplication.quit()` instead of `sys.exit(0)` when a Qt app is running, to ensure the event loop shuts down cleanly.

### W-04: `__main__.py` registers a no-op lambda for final log flush

**File:** `src/systemstt/__main__.py`, lines 62-66

```python
shutdown_manager.register(
    lambda: None,  # _flush_logs is called automatically by shutdown()
    priority=99,
    name="final-log-flush",
)
```

This registers a lambda that does nothing. The comment explains `_flush_logs` is called automatically, but this is misleading. If someone later changes `ShutdownManager.shutdown()` to not call `_flush_logs`, this task silently does nothing. Either remove this dead registration or register the actual `_flush_logs` method.

### W-05: `numpy` upper bound `<2.0` may be too restrictive

**File:** `pyproject.toml`, line 9

```toml
"numpy>=1.24,<2.0",
```

NumPy 2.0 has been released and is widely adopted. Pinning `<2.0` may cause dependency conflicts with `faster-whisper`, `sounddevice`, or other libraries that have already upgraded. This constraint should be tested and relaxed if possible.

### W-06: No `UIState` observable class implemented

**Expected as defined in:** `07-ui-layer.md` section 3.1

The spec defines a `UIState(QObject)` class with signals for `dictation_state_changed`, `language_changed`, `engine_changed`, etc. This is the bridge between the App Core and the UI layer. It is not implemented anywhere in the reviewed files. Without it, there is no mechanism for the App Core to push state updates to the UI reactively.

### W-07: CI uses only Python 3.11 — no matrix testing

**File:** `.github/workflows/ci.yml`, line 22

```yaml
env:
  PYTHON_VERSION: "3.11"
```

`pyproject.toml` specifies `requires-python = ">=3.11"`, meaning 3.12 and 3.13 are also valid targets. The CI should test on at least 3.11 and the latest stable Python to catch compatibility issues early.

### W-08: `create-dmg` `--volicon` error suppressed silently

**File:** `scripts/build_app.sh`, line 152

```bash
--volicon "${PROJECT_ROOT}/assets/icons/app-icon.icns" 2>/dev/null || true \
```

The `2>/dev/null || true` on the `--volicon` line suppresses errors if the icon file doesn't exist, but because this is a continuation of a multi-line command, the `|| true` may apply to the entire `create-dmg` invocation or just that argument, depending on how the shell parses the continuation. This is fragile and confusing. The icon existence check should happen before calling `create-dmg`.

---

## Suggestions (Nice to Have)

### S-01: Add `py.typed` marker file for PEP 561 compliance

**Expected at:** `src/systemstt/py.typed`

Since the project uses `mypy --strict` and exports typed public APIs, adding a `py.typed` marker file signals to downstream consumers (and mypy itself) that this package supports type checking.

### S-02: Pre-commit hook mypy version lags behind pyproject.toml

**Files:** `.pre-commit-config.yaml` (line 49: `v1.14.1`), `pyproject.toml` (line 27: `mypy>=1.8`)

The pre-commit mirror is pinned to `v1.14.1` while `pyproject.toml` specifies `>=1.8`. These are compatible, but the pre-commit version should be kept in sync with what CI uses. Consider using `local` hooks that run from the venv instead of the mirror to avoid version mismatches.

### S-03: Consider adding a `--strict-build` flag to `build_app.sh`

To address W-01 without changing default behavior for development builds, add a `--strict` flag that makes test failures fatal. CI should use `--strict`.

### S-04: Makefile `clean` target uses `find` with `|| true` — consider explicit error handling

**File:** `Makefile`, line 147

```make
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
```

This is a common pattern but the `|| true` masks real errors. Since this is a cleanup target, the risk is low, but using `find ... -prune` or `-depth` would be more robust.

### S-05: `SettingsWindow` uses `list[Any]` and `Any` for audio types

**File:** `src/systemstt/ui/settings_window.py`, lines 53-54

```python
self._audio_devices: list[Any] = []
self._audio_level: Any = None
```

The spec (`07-ui-layer.md` section 2.5) defines typed signatures: `devices: list["AudioDevice"]` and `level: "LevelReading"`. Using `Any` loses type safety. These should use the proper types from the audio module, even if behind `TYPE_CHECKING` guards.

### S-06: `ShutdownManager` could benefit from a timeout per task

**File:** `src/systemstt/shutdown.py`

If a shutdown callback hangs (e.g., waiting for a network response), the entire shutdown process blocks indefinitely. Consider adding an optional per-task timeout (e.g., 5 seconds default) using `threading.Timer` or `signal.alarm`.

### S-07: `logging_config.py` imports `re` inside `_redact` method

**File:** `src/systemstt/logging_config.py`, line 73

The `import re` is inside the `_redact` static method, which means it's re-imported on every call. While Python caches imports, moving it to the module level is cleaner and avoids the (negligible) lookup overhead on every log record that triggers redaction.

---

## Design Spec Compliance

| Design Spec Requirement | Status | Notes |
|------------------------|--------|-------|
| Color system (Section 2) | NOT IMPLEMENTED | No `theme.py` with `DesignTokens`; no QSS generation |
| Typography (Section 3) | NOT IMPLEMENTED | No font configuration anywhere |
| Menu bar icon + label (Section 4.1) | STUB ONLY | Class exists but no rendering, no composite icon generation |
| Menu bar dropdown (Section 4.3) | MISSING | `DropdownMenu` class not implemented |
| Floating pill layout (Section 5.1-5.2) | STUB ONLY | Class exists but no QWidget, no rendering |
| Recording dot animation (Section 5.3) | MISSING | No `QPropertyAnimation`, no pulse logic |
| Pill dragging (Section 5.6) | MISSING | No mouse event handlers |
| Pill animations (Section 5.6) | MISSING | No appear/disappear animations |
| Inline error behavior (Section 5.7) | MISSING | No error display, no auto-dismiss timers |
| Settings window layout (Section 6.1) | STUB ONLY | Class exists but no QWidget, no custom title bar |
| Settings tabs (Section 6.2-6.6) | MISSING | No tab widgets (`GeneralTab`, `EngineTab`, etc.) |
| Form controls (Section 6.7) | MISSING | No toggle switches, dropdowns, radio buttons |
| Notifications (Section 7) | MISSING | Not in scope of reviewed files but no infrastructure for it |
| Keyboard shortcuts (Section 9) | NOT IMPLEMENTED | No shortcut registration |
| Animations (Section 11) | MISSING | No animation code anywhere |
| Accessibility (Section 12) | MISSING | No keyboard nav, focus indicators, reduced motion |

The current UI code consists of structural stubs that define the correct API surface (method names and signatures match the spec) but contain zero visual implementation. This is expected for an early phase of development but means the design spec is 0% implemented in terms of actual rendering.

---

## Infrastructure Assessment

| Component | Status | Notes |
|-----------|--------|-------|
| `logging_config.py` | GOOD with one critical fix needed | Rotating handlers, crash log, sensitive filter (but filter has bypass — see C-05) |
| `shutdown.py` | GOOD with one warning | Priority-based teardown, idempotent, error isolation per task. Signal handler needs Qt awareness (W-03) |
| `__main__.py` | GOOD | Clean startup sequence, env var override for log level, proper CLI arg parsing |
| `ci.yml` | GOOD | Covers lint, typecheck, test, build. Proper caching, artifact upload. Add matrix testing (W-07) |
| `Makefile` | GOOD | Comprehensive targets, mirrors CI. Well-organized |
| `build_app.sh` | GOOD with warnings | Pre-flight checks, error handling, DMG fallback. Fix test-failure policy (W-01) and stderr suppression (W-02) |
| `.pre-commit-config.yaml` | GOOD | Covers hygiene, ruff, mypy. Versions slightly behind |
| `pyproject.toml` | GOOD | Dependencies well-specified with bounds, proper tool config |
| `systemstt.spec` | GOOD with one fix needed | Correct hidden imports, proper excludes, good Info.plist. Fix hardcoded version (C-06) |

---

## Security

- **No hardcoded secrets found** in any reviewed file.
- **API key storage:** Design spec (NFR-006) requires OS keychain. `constants.py` defines `KEYCHAIN_SERVICE_NAME = "systemstt"`, indicating the keychain approach is planned. No API keys appear in config files or code.
- **Sensitive data logging:** Filter exists but has a bypass path (C-05). The filter is a defense-in-depth measure; the primary defense (documented in code) is not logging secrets in the first place.
- **Build artifacts:** The `.spec` file properly excludes test/dev dependencies from the bundle. No credentials are bundled.
- **CI pipeline:** No secrets are hardcoded in `ci.yml`. No deployment steps that could leak credentials.

---

## Verdict: NEEDS CHANGES

The infrastructure layer (logging, shutdown, CI, build) is solid and well-engineered. The main issues are the sensitive data filter bypass (C-05) and the version duplication (C-06).

The UI layer requires substantial implementation work. The current code provides correct API stubs that match the spec's method signatures, but every class is a plain Python object with no Qt integration and no rendering capability. The missing `theme.py` (C-02), missing `DropdownMenu` (C-03), and missing Qt signals (C-04) are the most impactful gaps.

**Before merging to main, at minimum fix:**
1. C-05 (sensitive data filter bypass)
2. C-06 (version source-of-truth)
3. W-03 (signal handler Qt compatibility)

**Before the UI can be considered functional, implement:**
1. C-01 (QWidget subclasses with actual rendering)
2. C-02 (theme.py with design tokens)
3. C-03 (DropdownMenu component)
4. C-04 (Qt signals for all UI widgets)
