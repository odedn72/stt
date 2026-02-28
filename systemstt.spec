# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for SystemSTT.

Builds a macOS .app bundle from the Python source. The resulting bundle
is a standalone application that includes Python, all dependencies, and
the faster-whisper runtime (models are downloaded on demand at runtime).

Usage:
    pyinstaller systemstt.spec --noconfirm

The output is placed in dist/SystemSTT.app
"""

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

block_cipher = None

# Project root (where this .spec file lives)
PROJECT_ROOT = Path(SPECPATH)
SRC_DIR = PROJECT_ROOT / "src"

# Read version from pyproject.toml — the single source of truth
with open(PROJECT_ROOT / "pyproject.toml", "rb") as _f:
    _pyproject = tomllib.load(_f)
APP_VERSION = _pyproject["project"]["version"]

# Collect data files
datas = []

# Include assets if the directory exists (icons, resources)
assets_dir = PROJECT_ROOT / "assets"
if assets_dir.exists():
    datas.append((str(assets_dir), "assets"))

# Hidden imports that PyInstaller may not detect automatically.
# PyObjC frameworks are loaded dynamically and need explicit listing.
hiddenimports = [
    "objc",
    "Cocoa",
    "Quartz",
    "Security",
    "UserNotifications",
    "Foundation",
    "AppKit",
    "CoreFoundation",
    # PySide6 modules
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    # faster-whisper and its backend
    "faster_whisper",
    "ctranslate2",
    # Audio
    "sounddevice",
    "_sounddevice_data",
    # Data validation
    "pydantic",
    "pydantic.deprecated.decorator",
    # HTTP client
    "httpx",
    "httpcore",
    "h11",
    "certifi",
    "anyio",
    "sniffio",
]

a = Analysis(
    [str(SRC_DIR / "systemstt" / "__main__.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test/dev dependencies from the bundle
        "pytest",
        "pytest_asyncio",
        "pytest_qt",
        "pytest_cov",
        "ruff",
        "mypy",
        "coverage",
        # Exclude unused large packages
        "tkinter",
        "matplotlib",
        "PIL",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SystemSTT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # No terminal window — this is a GUI app
    target_arch=None,  # Build for the current architecture
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SystemSTT",
)

app = BUNDLE(
    coll,
    name="SystemSTT.app",
    icon=str(assets_dir / "icons" / "app-icon.icns") if (assets_dir / "icons" / "app-icon.icns").exists() else None,
    bundle_identifier="com.systemstt.app",
    info_plist={
        "CFBundleName": "SystemSTT",
        "CFBundleDisplayName": "SystemSTT",
        "CFBundleIdentifier": "com.systemstt.app",
        "CFBundleVersion": APP_VERSION,
        "CFBundleShortVersionString": APP_VERSION,
        "NSMicrophoneUsageDescription": "SystemSTT needs microphone access for speech-to-text dictation.",
        "NSAccessibilityUsageDescription": "SystemSTT needs accessibility access to inject dictated text into other applications.",
        "LSUIElement": True,  # Hide from Dock by default (menu bar app)
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        "NSSupportsAutomaticGraphicsSwitching": True,
    },
)
