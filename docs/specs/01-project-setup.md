# 01 — Project Setup
**Version:** 1.0
**Date:** 2026-02-28
**Status:** Draft

---

## 1. Goal

Define the project directory structure, dependency list, configuration files, and development workflow for SystemSTT. This is the first thing the developer implements — the skeleton that all other components are built into.

**MRD requirements:** NFR-007 (sensible defaults), NFR-008 (cross-platform architecture), FR-010 (macOS support).

---

## 2. Python Version

**Python 3.11+** is required. Rationale:
- `TaskGroup` and `ExceptionGroup` for structured concurrency
- Performance improvements over 3.10 (10-60% faster CPython)
- `tomllib` in stdlib for pyproject.toml parsing
- All key dependencies (PySide6, faster-whisper, PyObjC) support 3.11+

---

## 3. Directory Structure

```
systemstt/
├── pyproject.toml              # Project metadata, dependencies, tool config
├── README.md                   # Developer setup instructions
├── CLAUDE.md                   # Project conventions (already exists at repo root)
├── docs/
│   ├── mrd/
│   │   └── mrd.md
│   ├── design/
│   │   └── design-spec.md
│   └── specs/
│       ├── 00-architecture-overview.md
│       ├── 01-project-setup.md
│       ├── ...
│       └── 08-configuration.md
├── src/
│   └── systemstt/
│       ├── __init__.py          # Package init, version
│       ├── __main__.py          # Entry point: `python -m systemstt`
│       ├── app.py               # App Core / Orchestrator
│       ├── constants.py         # App-wide constants (app name, defaults)
│       ├── errors.py            # Error hierarchy (all custom exceptions)
│       │
│       ├── audio/
│       │   ├── __init__.py
│       │   ├── recorder.py      # AudioRecorder: capture audio stream
│       │   ├── devices.py       # DeviceEnumerator: list/monitor input devices
│       │   └── level_meter.py   # LevelMeter: RMS/peak computation
│       │
│       ├── stt/
│       │   ├── __init__.py
│       │   ├── base.py          # STTEngine ABC, TranscriptionResult model
│       │   ├── local_whisper.py # LocalWhisperEngine implementation
│       │   └── cloud_api.py     # CloudAPIEngine implementation
│       │
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── parser.py        # CommandParser: detect commands in text
│       │   ├── executor.py      # CommandExecutor: execute recognized commands
│       │   └── registry.py      # CommandRegistry: built-in command definitions
│       │
│       ├── platform/
│       │   ├── __init__.py
│       │   ├── base.py          # Abstract interfaces for all platform services
│       │   ├── factory.py       # Platform factory: returns correct implementation
│       │   └── macos/
│       │       ├── __init__.py
│       │       ├── text_injector.py   # macOS Accessibility-based text injection
│       │       ├── hotkey_manager.py  # macOS Carbon hotkey registration
│       │       ├── keychain.py        # macOS Keychain wrapper
│       │       ├── permissions.py     # macOS Accessibility permission checker
│       │       └── notifications.py   # macOS UserNotifications wrapper
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   ├── models.py        # SettingsModel (pydantic) — all app settings
│       │   ├── store.py         # SettingsStore: JSON load/save
│       │   └── secure.py        # SecureStore ABC + platform dispatch
│       │
│       └── ui/
│           ├── __init__.py
│           ├── menu_bar.py      # Menu bar icon + language label
│           ├── dropdown.py      # Custom dropdown menu
│           ├── floating_pill.py # Floating status pill widget
│           ├── settings_window.py  # Settings window (tabbed)
│           ├── tabs/
│           │   ├── __init__.py
│           │   ├── general.py   # General settings tab
│           │   ├── engine.py    # Engine settings tab
│           │   ├── audio.py     # Audio settings tab
│           │   └── commands.py  # Commands settings tab
│           ├── widgets/         # Reusable styled widgets
│           │   ├── __init__.py
│           │   ├── toggle.py    # Custom toggle switch
│           │   ├── dropdown.py  # Custom styled dropdown
│           │   ├── radio.py     # Custom radio buttons
│           │   └── button.py    # Styled primary/secondary buttons
│           └── theme.py         # Design tokens, QSS generation, colors
│
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── test_app.py              # Orchestrator tests
│   ├── audio/
│   │   ├── test_recorder.py
│   │   ├── test_devices.py
│   │   └── test_level_meter.py
│   ├── stt/
│   │   ├── test_local_whisper.py
│   │   └── test_cloud_api.py
│   ├── commands/
│   │   ├── test_parser.py
│   │   └── test_executor.py
│   ├── platform/
│   │   └── macos/
│   │       ├── test_text_injector.py
│   │       ├── test_hotkey_manager.py
│   │       └── test_keychain.py
│   ├── config/
│   │   ├── test_models.py
│   │   └── test_store.py
│   └── ui/
│       ├── test_floating_pill.py
│       └── test_settings_window.py
│
└── assets/
    ├── icons/
    │   ├── mic-outlined.svg
    │   ├── mic-filled.svg
    │   ├── warning.svg
    │   ├── cloud.svg
    │   ├── local.svg
    │   ├── checkmark.svg
    │   └── app-icon.icns
    └── resources.qrc            # Qt resource file
```

---

## 4. Dependencies

### 4.1 pyproject.toml

```toml
[project]
name = "systemstt"
version = "0.1.0"
description = "System-wide speech-to-text for macOS"
requires-python = ">=3.11"
dependencies = [
    "PySide6>=6.6,<7.0",
    "sounddevice>=0.4.6",
    "numpy>=1.24,<2.0",
    "faster-whisper>=1.0.0",
    "httpx>=0.27",
    "pydantic>=2.5,<3.0",
    "pyobjc-core>=10.0",
    "pyobjc-framework-Cocoa>=10.0",
    "pyobjc-framework-Quartz>=10.0",
    "pyobjc-framework-Security>=10.0",
    "pyobjc-framework-UserNotifications>=10.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-qt>=4.3",
    "pytest-cov>=4.1",
    "ruff>=0.3",
    "mypy>=1.8",
]

[project.scripts]
systemstt = "systemstt.__main__:main"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "ANN", "B", "A", "SIM", "TCH"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

### 4.2 Dependency Justification

| Package | Purpose | Why This One |
|---------|---------|-------------|
| PySide6 | UI framework | Cross-platform, custom widgets, LGPL license |
| sounddevice | Audio capture | PortAudio wrapper, device enumeration, callback API |
| numpy | Audio data handling | PCM arrays, RMS computation, Whisper expects numpy |
| faster-whisper | Local STT | 4x faster than reference on CPU (critical for Intel i9) |
| httpx | HTTP client | Async support, streaming, modern Python HTTP client |
| pydantic | Settings validation | Type-safe config models with defaults and serialization |
| pyobjc-* | macOS APIs | Accessibility, Keychain, hotkeys, notifications |

### 4.3 Dev Dependencies

| Package | Purpose |
|---------|---------|
| pytest | Test runner |
| pytest-asyncio | Async test support |
| pytest-qt | Qt widget testing |
| pytest-cov | Coverage reporting |
| ruff | Linting + formatting (replaces black + isort + flake8) |
| mypy | Static type checking |

---

## 5. Development Environment Setup

### 5.1 Initial Setup

```bash
# Clone the repository
cd ~/projects/stt

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify installation
python -m systemstt --version
```

### 5.2 Running

```bash
# Run the application
python -m systemstt

# Run with debug logging
SYSTEMSTT_LOG_LEVEL=DEBUG python -m systemstt
```

### 5.3 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=systemstt --cov-report=term-missing

# Run specific test module
pytest tests/stt/test_cloud_api.py

# Type checking
mypy src/systemstt

# Linting
ruff check src/ tests/
ruff format src/ tests/
```

---

## 6. Configuration Files and Paths

| Item | Path | Notes |
|------|------|-------|
| User settings | `~/.config/systemstt/settings.json` | Created on first launch with defaults |
| API key | macOS Keychain, service: "systemstt", account: "openai_api_key" | Never in a file |
| Whisper models | `~/.cache/systemstt/models/` | Downloaded on demand by faster-whisper |
| Log file | `~/.local/share/systemstt/systemstt.log` | Rotating, 5MB max, 3 backups |
| Pill position | Inside settings.json (`pill_x`, `pill_y`) | Persisted between sessions |

---

## 7. Entry Point

The application entry point is `src/systemstt/__main__.py`:

```python
"""
Entry point for SystemSTT.

Responsibilities:
1. Parse CLI arguments (--version, --log-level)
2. Configure logging
3. Initialize the Qt application
4. Create the platform factory (detect macOS/Windows)
5. Load configuration
6. Create and start the App Core (orchestrator)
7. Enter the Qt event loop
"""
```

The `__main__.py` file should be kept minimal — it wires dependencies together and starts the event loop. All business logic lives in `app.py` and the component modules.

---

## 8. Logging Strategy

- Use Python's `logging` module with a custom formatter
- Default level: `INFO`
- Configurable via `SYSTEMSTT_LOG_LEVEL` environment variable
- Log to file (`~/.local/share/systemstt/systemstt.log`) and stderr
- **Never log API keys, audio data, or transcription content at INFO level.** Transcription content may be logged at DEBUG level for troubleshooting.
- Structured log format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

---

## 9. Notes for Developer

1. **Start with the skeleton:** Create all directories, `__init__.py` files, and `pyproject.toml` first. Verify the project installs and `python -m systemstt` prints a version string.

2. **TDD from the start:** Per CLAUDE.md conventions, write tests before implementation. Each component spec includes testable interfaces.

3. **Use `src/` layout:** The `src/systemstt/` layout prevents accidental imports from the working directory. Always import as `from systemstt.audio.recorder import AudioRecorder`.

4. **Type hints everywhere:** The project uses `mypy --strict`. Every function signature must have full type annotations.

5. **PySide6, not PyQt6:** They are API-compatible but PySide6 is the official Qt binding with LGPL licensing. Never mix PySide6 and PyQt6 imports.
