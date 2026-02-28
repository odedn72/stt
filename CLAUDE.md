# SystemSTT

## Overview

SystemSTT is a system-wide speech-to-text desktop application for macOS (Windows planned for v2). It allows dictation into any text field via a global hotkey, with Hebrew/English bilingual support, voice commands, and configurable STT engines (local Whisper or cloud API).

See `docs/mrd/mrd.md` for full product requirements.
See `docs/design/design-spec.md` for UI/UX specifications.
See `docs/specs/` for architecture and component specifications.

## Tech Stack

| Concern | Technology | Version |
|---------|-----------|---------|
| Language | Python | 3.11+ |
| UI Framework | PySide6 (Qt 6) | >=6.6 |
| Audio Capture | sounddevice (PortAudio) | >=0.4.6 |
| Audio Processing | numpy | >=1.24 |
| Local STT | faster-whisper (CTranslate2) | >=1.0.0 |
| Cloud STT Client | httpx | >=0.27 |
| Settings Validation | pydantic | >=2.5 |
| macOS Integration | PyObjC | >=10.0 |
| Testing | pytest + pytest-asyncio + pytest-qt + pytest-cov | >=8.0 |
| Linting/Formatting | ruff | >=0.3 |
| Type Checking | mypy (strict mode) | >=1.8 |
| Build/Package | PyInstaller | >=6.0 |
| Pre-commit | pre-commit | >=3.6 |

## Project Structure

```
src/systemstt/
    __init__.py             # Package init, version from importlib.metadata
    __main__.py             # Entry point: python -m systemstt
    app.py                  # App Core / Orchestrator + state machine
    constants.py            # App-wide constants (paths, audio defaults, keychain)
    errors.py               # Error hierarchy (all custom exceptions)
    logging_config.py       # Structured logging: rotating file, crash log, sensitive data filter
    shutdown.py             # Graceful shutdown manager with priority-ordered cleanup
    audio/
        __init__.py
        devices.py          # Device enumeration (input devices list)
        level_meter.py      # Real-time audio level meter (RMS/peak)
        recorder.py         # Audio capture (sounddevice) with start/stop/buffer
    stt/
        __init__.py
        base.py             # STT engine ABC (STTEngine interface)
        cloud_api.py        # Cloud API engine (OpenAI Whisper API via httpx)
        local_whisper.py    # Local Whisper engine (faster-whisper / CTranslate2)
        engine_manager.py   # Engine lifecycle: load, switch, health check
    commands/
        __init__.py
        parser.py           # Voice command parser (Hebrew + English patterns)
        executor.py         # Command executor (maps parsed commands to actions)
        registry.py         # Command registry (built-in + extensible command set)
    platform/
        __init__.py
        base.py             # Abstract interfaces (hotkey, text injection, keychain, etc.)
        macos/
            __init__.py
            hotkey_manager.py  # macOS global hotkey (CGEvent tap)
            text_injector.py   # macOS text injection (CGEvent / accessibility API)
            keychain.py        # macOS Keychain integration (Security framework)
    config/
        __init__.py
        models.py           # Settings model (pydantic BaseModel with validation)
        store.py            # JSON persistence (load/save ~/.config/systemstt/settings.json)
        secure.py           # Secure store adapter (delegates to platform keychain)
    ui/
        __init__.py
        theme.py            # Design tokens + QSS stylesheet generation
        menu_bar.py         # macOS menu bar (system tray) icon + menu
        dropdown_menu.py    # Dropdown menu from tray icon (status, settings, quit)
        floating_pill.py    # Floating dictation indicator pill (recording/processing states)
        settings_window.py  # Settings window with tabbed interface
        tabs/
            __init__.py     # Settings tab widgets (general, audio, STT, shortcuts)
        widgets/
            __init__.py     # Reusable styled widgets (toggle, dropdown, radio, button)

scripts/
    build_app.sh            # Build script: .app bundle + optional DMG creation

.github/
    workflows/
        ci.yml              # GitHub Actions CI: lint -> typecheck -> test (3.11+3.12) -> build

docs/
    mrd/mrd.md              # Market Requirements Document
    design/design-spec.md   # UI/UX design specification
    deployment.md           # Deployment and distribution guide
    specs/                  # Component architecture specs (00-08)
    reviews/                # Code review reports (review-core.md, review-ui-infra.md)
    bugs/                   # Bug reports (bug-001.md)
    tests/test-plan.md      # Test plan and strategy

tests/                      # 521 tests — mirrors src/ structure
    conftest.py             # Shared fixtures (mock platform services, settings, etc.)
    test_app.py             # App orchestrator / state machine tests
    test_errors.py          # Error hierarchy tests
    audio/
        test_audio_recorder.py
        test_device_enumerator.py
        test_level_meter.py
    stt/
        test_engine_abc.py
        test_cloud_api.py
        test_local_whisper.py
        test_engine_manager.py
    commands/
        test_command_parser.py
        test_command_executor.py
        test_command_registry.py
    platform/
        test_hotkey_manager.py
        test_text_injector.py
    config/
        test_settings_model.py
        test_settings_store.py
        test_secure_store.py
    ui/
        conftest.py         # Qt test fixtures (QApplication, widget helpers)
        test_theme.py
        test_menu_bar.py
        test_dropdown_menu.py
        test_floating_pill.py
        test_settings_window.py
```

## Commands

```bash
# --- Setup ---
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Or use the Makefile (recommended):
make install              # Create venv + install with dev + build deps
make dev                  # Full dev setup (install + pre-commit hooks)

# --- Run ---
make run                  # Run the application
make run-debug            # Run with SYSTEMSTT_LOG_LEVEL=DEBUG
python -m systemstt       # Direct invocation

# --- Test ---
make test                 # Run all 521 tests with coverage
make test-quick           # Fast run without coverage (stops on first failure)
make test-verbose         # Full output + HTML coverage report
pytest                    # Direct pytest invocation
pytest tests/stt/test_cloud_api.py   # Run a specific test module

# --- Code Quality ---
make lint                 # Run ruff linter
make format               # Auto-format with ruff
make format-check         # Check formatting without modifying
make typecheck            # Run mypy --strict
make check                # All checks: lint + format-check + typecheck + test (mirrors CI)

# --- Pre-commit Hooks ---
make pre-commit-install   # Install git pre-commit hooks
make pre-commit-run       # Run hooks on all files manually

# --- Build & Distribution ---
make build                # Build macOS .app bundle (dist/SystemSTT.app)
make dmg                  # Build .app + create DMG installer
make build-clean          # Clean previous build, then rebuild
./scripts/build_app.sh --help    # Build script usage

# --- Cleanup ---
make clean                # Remove build artifacts, caches, coverage
make clean-all            # Remove everything including .venv

# --- Type check (direct) ---
mypy src/systemstt
```

## Conventions

- **TDD: Tests are written BEFORE implementation code**
- Type hints / strong typing everywhere — project uses `mypy --strict`
- Async/non-blocking I/O for all external calls
- All external integrations behind abstract interfaces (ABCs)
- Configuration via `~/.config/systemstt/settings.json` (pydantic model)
- Secrets (API keys) in macOS Keychain — never in config files, env vars, or logs
- All user input validated at boundaries (pydantic at config, type checks at interfaces)
- Comprehensive error handling — custom error hierarchy rooted at `SystemSTTError`
- Tests mock all external dependencies (sounddevice, faster-whisper, httpx, PyObjC)
- PySide6 only — never import PyQt6
- Qt signals/slots for all inter-component communication
- UI is purely reactive — reads UIState, emits user action signals, never decides behavior
- Main thread is never blocked by audio capture or transcription (dedicated threads)
- All file paths use `pathlib.Path`
- Logging uses structured format with sensitive data filtering (API keys redacted)
- Graceful shutdown via `ShutdownManager` with priority-ordered cleanup callbacks
- Pre-commit hooks enforce lint, format, and type checks before every commit

## Key Configuration Paths

| Path | Purpose |
|------|---------|
| `~/.config/systemstt/settings.json` | User settings (persisted) |
| `~/.cache/systemstt/models/` | Downloaded Whisper models |
| `~/.local/share/systemstt/systemstt.log` | Application log (rotating, 5 MB x 3) |
| `~/.local/share/systemstt/crash.log` | Crash log (ERROR+ only) |

## CI Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to `main`/`develop`:

1. **Lint** — `ruff check` + `ruff format --check`
2. **Type Check** — `mypy --strict`
3. **Test** — `pytest` with coverage on Python 3.11 and 3.12 (matrix)
4. **Build Validation** — `python -m build` + `pyinstaller` (gated on 1-3 passing)
