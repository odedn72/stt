"""
Settings store — JSON file persistence for settings.

Handles loading, saving, and atomic writes of the SettingsModel to
a JSON file on disk. Supports graceful degradation: corrupted or
missing files return default settings.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from systemstt.config.models import SettingsModel

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".config" / "systemstt" / "settings.json"


class SettingsStore:
    """JSON file persistence for the SettingsModel."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else _DEFAULT_PATH

    @property
    def file_path(self) -> Path:
        """Return the configured settings file path."""
        return self._path

    def load(self) -> SettingsModel:
        """Load settings from disk.

        Returns default settings if the file doesn't exist, is corrupted,
        or contains invalid data.
        """
        if not self._path.exists():
            logger.info("Settings file not found at %s, using defaults", self._path)
            return SettingsModel()

        try:
            text = self._path.read_text(encoding="utf-8")
            data = json.loads(text)
            return SettingsModel(**data)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning(
                "Failed to load settings from %s: %s. Using defaults.",
                self._path,
                exc,
            )
            return SettingsModel()
        except Exception as exc:
            logger.warning(
                "Unexpected error loading settings from %s: %s. Using defaults.",
                self._path,
                exc,
            )
            return SettingsModel()

    def save(self, settings: SettingsModel) -> None:
        """Save settings to disk using atomic write (temp file + rename).

        Creates parent directories if they don't exist.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)

        data = settings.model_dump(mode="json")
        json_str = json.dumps(data, indent=2, ensure_ascii=False)

        # Atomic write: write to temp file via the mkstemp fd, then rename
        fd, tmp_path_str = tempfile.mkstemp(
            dir=str(self._path.parent),
            suffix=".tmp",
            prefix=".settings_",
        )
        tmp_path = Path(tmp_path_str)
        try:
            import os

            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json_str)
            tmp_path.replace(self._path)
        except Exception:
            # Clean up temp file on failure
            tmp_path.unlink(missing_ok=True)
            raise
