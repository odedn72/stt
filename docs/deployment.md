# SystemSTT — Deployment & Distribution Guide

**Version:** 1.0
**Date:** 2026-02-28

---

## 1. Overview

SystemSTT is a **native macOS desktop application** distributed as a standalone `.app` bundle inside a `.dmg` installer. It is not a web service — there are no Docker containers, health check endpoints, or server deployments.

**Distribution flow:**

```
Source code
    |
    v
CI pipeline (GitHub Actions)
    |-- lint (ruff)
    |-- type check (mypy --strict)
    |-- test (pytest + coverage)
    |-- build validation (PyInstaller)
    |
    v
Release build (manual or CI)
    |-- PyInstaller -> SystemSTT.app
    |-- (optional) code signing + notarization
    |-- create-dmg -> SystemSTT-x.y.z-macos.dmg
    |
    v
Distribution (GitHub Releases, direct download)
```

---

## 2. Development Setup

### 2.1 Prerequisites

- macOS 12.0+ (Monterey or later)
- Python 3.11+ (`brew install python@3.11`)
- Xcode Command Line Tools (`xcode-select --install`)

### 2.2 Quick Start

```bash
# Clone and enter the project
cd ~/projects/stt

# Full dev environment setup (venv, deps, pre-commit hooks)
make dev

# Or manually:
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,build]"
pre-commit install
```

### 2.3 Common Development Commands

```bash
make help          # Show all available commands
make test          # Run tests with coverage
make lint          # Run ruff linter
make format        # Auto-format code
make typecheck     # Run mypy --strict
make check         # Run ALL checks (lint + format + typecheck + test)
make run           # Run the application
make run-debug     # Run with DEBUG logging
```

---

## 3. CI/CD Pipeline

### 3.1 GitHub Actions Workflow

The CI pipeline (`.github/workflows/ci.yml`) runs on every push and PR to `main` and `develop` branches. It uses **macOS runners** because the project depends on macOS-specific packages (PyObjC).

**Jobs:**

| Job | What it does | Runner |
|-----|-------------|--------|
| `lint` | `ruff check` + `ruff format --check` | macOS-latest |
| `typecheck` | `mypy --strict src/systemstt` | macOS-latest |
| `test` | `pytest --cov` with coverage XML output | macOS-latest |
| `build` | Validate PyInstaller `.app` build | macOS-latest |

- `lint`, `typecheck`, and `test` run in parallel
- `build` runs only after all three pass
- Dependency caching uses `~/Library/Caches/pip` keyed on `pyproject.toml` hash
- Concurrency is set to cancel in-progress runs on the same branch

### 3.2 Build Artifacts

The CI `build` job uploads:
- `SystemSTT-macos-app` — the built `.app` bundle (retained 7 days)
- `coverage-report` — XML coverage data
- `test-results` — JUnit XML test results

---

## 4. Building the Application

### 4.1 PyInstaller Build

SystemSTT is packaged as a standalone macOS `.app` bundle using PyInstaller. The configuration is in `systemstt.spec` at the project root.

```bash
# Quick build
make build

# Build with clean (removes previous artifacts)
make build-clean

# Build + create DMG installer
make dmg
```

Or use the build script directly:

```bash
./scripts/build_app.sh           # Build .app only
./scripts/build_app.sh --dmg     # Build .app + DMG
./scripts/build_app.sh --clean   # Clean first, then build
```

### 4.2 What the Build Produces

```
dist/
├── SystemSTT.app/               # Standalone macOS application
│   └── Contents/
│       ├── Info.plist           # App metadata, permissions declarations
│       ├── MacOS/
│       │   └── SystemSTT        # Main executable
│       └── Resources/
│           └── ...              # Bundled Python, deps, assets
└── SystemSTT-0.1.0-macos.dmg   # (with --dmg flag) Installer disk image
```

### 4.3 Info.plist Permissions

The `.app` bundle declares these macOS permissions in `Info.plist`:

| Key | Purpose |
|-----|---------|
| `NSMicrophoneUsageDescription` | Microphone access for speech capture |
| `NSAccessibilityUsageDescription` | Accessibility API for text injection |
| `LSUIElement: true` | Menu bar app (hidden from Dock by default) |

The user grants these permissions on first launch through macOS system dialogs.

### 4.4 Build Configuration Details

The `systemstt.spec` file configures:

- **Entry point:** `src/systemstt/__main__.py`
- **Hidden imports:** PyObjC frameworks, PySide6, faster-whisper, CTranslate2
- **Excluded packages:** test runners, dev tools, tkinter, matplotlib
- **Console mode:** Disabled (GUI-only application)
- **Bundle ID:** `com.systemstt.app`

---

## 5. Code Signing and Notarization

> **Note:** Code signing is optional for personal use. It is required for distribution to other users (prevents "unidentified developer" warnings).

### 5.1 Code Signing

```bash
# Sign the .app bundle with your Developer ID
codesign --deep --force --verify --verbose \
    --sign "Developer ID Application: Your Name (TEAM_ID)" \
    --options runtime \
    dist/SystemSTT.app

# Verify the signature
codesign --verify --verbose=4 dist/SystemSTT.app
spctl --assess --verbose dist/SystemSTT.app
```

**Requirements:**
- Apple Developer Program membership ($99/year)
- Developer ID Application certificate in Keychain
- `--options runtime` enables the hardened runtime (required for notarization)

### 5.2 Notarization

Notarization is required for macOS Gatekeeper to accept the app without warnings.

```bash
# Create a ZIP for notarization
ditto -c -k --keepParent dist/SystemSTT.app SystemSTT.zip

# Submit for notarization
xcrun notarytool submit SystemSTT.zip \
    --apple-id "your@email.com" \
    --team-id "TEAM_ID" \
    --password "@keychain:AC_PASSWORD" \
    --wait

# Staple the notarization ticket to the app
xcrun stapler staple dist/SystemSTT.app

# Then re-create the DMG with the stapled app
```

### 5.3 Creating a Signed DMG

```bash
# After signing and notarizing the .app:
create-dmg \
    --volname "SystemSTT" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "SystemSTT.app" 150 185 \
    --hide-extension "SystemSTT.app" \
    --app-drop-link 450 185 \
    "dist/SystemSTT-0.1.0-macos.dmg" \
    "dist/SystemSTT.app"

# Sign the DMG too
codesign --sign "Developer ID Application: Your Name (TEAM_ID)" \
    dist/SystemSTT-0.1.0-macos.dmg
```

---

## 6. Release Process

### 6.1 Versioning

SystemSTT follows semantic versioning (`MAJOR.MINOR.PATCH`). The version is defined in one place:

- `src/systemstt/__init__.py` — `__version__ = "x.y.z"`
- `pyproject.toml` — `version = "x.y.z"`

Both must be updated together. A future improvement is to use `setuptools-scm` or a single source of truth.

### 6.2 Release Checklist

1. Update version in `__init__.py` and `pyproject.toml`
2. Update `CFBundleVersion` and `CFBundleShortVersionString` in `systemstt.spec`
3. Ensure all checks pass: `make check`
4. Create a git tag: `git tag -a v0.1.0 -m "Release v0.1.0"`
5. Build the app: `make dmg`
6. (Optional) Sign and notarize
7. Create a GitHub Release with the DMG attached
8. Push the tag: `git push origin v0.1.0`

### 6.3 GitHub Releases

For distribution, create a GitHub Release and attach the DMG:

```bash
gh release create v0.1.0 \
    --title "SystemSTT v0.1.0" \
    --notes "Initial release. See CHANGELOG.md for details." \
    dist/SystemSTT-0.1.0-macos.dmg
```

---

## 7. Auto-Update Considerations

> **Status:** Not implemented in v1. Documented here for future implementation.

### 7.1 Options for macOS Desktop Apps

| Approach | Pros | Cons |
|----------|------|------|
| **Sparkle framework** | Industry standard for macOS apps, supports delta updates, code-signed appcast | Requires Objective-C bridge (PyObjC), needs hosting for appcast XML |
| **GitHub Releases polling** | Simple to implement, no extra infrastructure | No delta updates, manual restart required |
| **Custom HTTP check** | Full control | More work to implement, reinventing the wheel |

### 7.2 Recommended Approach: Sparkle via PyObjC

[Sparkle](https://sparkle-project.org/) is the standard auto-update framework for macOS applications. It can be integrated via PyObjC:

1. Bundle the Sparkle framework in the `.app`
2. Add an appcast URL to `Info.plist`
3. Host an appcast XML file (can be on GitHub Pages or S3)
4. On startup, check the appcast for new versions
5. If available, download and install the update with user confirmation

### 7.3 Minimum Viable Auto-Update

For v1, a simpler approach is sufficient:

1. On startup, make an HTTP GET to the GitHub Releases API
2. Compare the latest release tag with the current version
3. If a newer version exists, show a macOS notification with a download link
4. The user downloads and replaces the app manually

This can be implemented with ~50 lines of code using `httpx` (already a dependency) and requires no additional frameworks.

```python
# Pseudocode for version check
async def check_for_updates() -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.github.com/repos/OWNER/REPO/releases/latest"
        )
        latest = resp.json()["tag_name"].lstrip("v")
        if latest > __version__:
            # Show notification: "SystemSTT vX.Y.Z available — click to download"
            pass
```

---

## 8. Logging and Diagnostics

### 8.1 Log Files

| File | Location | Purpose |
|------|----------|---------|
| Application log | `~/.local/share/systemstt/systemstt.log` | All log messages (rotating, 5 MB, 3 backups) |
| Crash log | `~/.local/share/systemstt/crash.log` | ERROR+ messages and unhandled exceptions only |

### 8.2 Log Levels

Set via `--log-level` argument or `SYSTEMSTT_LOG_LEVEL` environment variable:

```bash
# Normal use
python -m systemstt

# Debug logging (verbose — includes transcription content)
SYSTEMSTT_LOG_LEVEL=DEBUG python -m systemstt

# Or via Makefile
make run-debug
```

### 8.3 Sensitive Data

Logs automatically filter patterns matching API keys, passwords, and tokens. The primary defense is the code convention (from `CLAUDE.md`): never log API keys, audio data, or transcription content at INFO level.

### 8.4 Crash Reports

Unhandled exceptions are captured by the global exception handler and written to `crash.log`. This file survives application restarts and is useful for post-mortem debugging.

---

## 9. Application Data Locations

| Data | Path | Notes |
|------|------|-------|
| Settings | `~/.config/systemstt/settings.json` | Created on first launch |
| API keys | macOS Keychain | Service: `systemstt` |
| Whisper models | `~/.cache/systemstt/models/` | Downloaded on demand |
| Application log | `~/.local/share/systemstt/systemstt.log` | Rotating |
| Crash log | `~/.local/share/systemstt/crash.log` | Rotating |

### 9.1 Complete Uninstall

To fully remove SystemSTT and all its data:

```bash
# Remove the application
rm -rf /Applications/SystemSTT.app

# Remove configuration
rm -rf ~/.config/systemstt

# Remove cached models (can be large)
rm -rf ~/.cache/systemstt

# Remove logs
rm -rf ~/.local/share/systemstt

# Remove Keychain entry (via Keychain Access app or:)
security delete-generic-password -s systemstt
```

---

## 10. Troubleshooting

### 10.1 App Crashes on Launch

1. Check `~/.local/share/systemstt/crash.log` for the exception traceback
2. Ensure macOS 12.0+ is installed
3. Try launching from Terminal to see stderr output:
   ```bash
   /Applications/SystemSTT.app/Contents/MacOS/SystemSTT
   ```

### 10.2 Microphone Not Working

1. Check System Settings > Privacy & Security > Microphone — SystemSTT must be listed and enabled
2. Check the audio device selection in SystemSTT settings
3. Run with debug logging to see device enumeration output

### 10.3 Text Not Injecting

1. Check System Settings > Privacy & Security > Accessibility — SystemSTT must be listed and enabled
2. Some applications (sandboxed or custom-rendered) may not support accessibility-based text injection
3. Check the application log for `TextInjectionError` entries

### 10.4 "Unidentified Developer" Warning

The app is not code-signed. Either:
- Right-click the app and select "Open" (bypasses Gatekeeper once)
- Or sign the app with a Developer ID certificate (see Section 5)
