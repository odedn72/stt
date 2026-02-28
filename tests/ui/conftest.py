"""
Shared fixtures for UI tests.

Ensures a QApplication exists in offscreen mode so that QWidget
subclasses can be instantiated without a display.
"""

from __future__ import annotations

import os

import pytest

# Force offscreen rendering before any Qt import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def qapp() -> QApplication:
    """Provide a QApplication instance for the entire test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
