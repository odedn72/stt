"""
LevelMeter — computes audio level from PCM samples.

Pure function: takes a chunk of audio samples, returns a LevelReading
with RMS level in dBFS, peak level in dBFS, and a categorical level.

dBFS thresholds from spec 02, section 6, note 6:
    SILENT: rms_db < -60
    TOO_QUIET: -60 <= rms_db < -40
    OK: -40 <= rms_db < -6
    LOUD: -6 <= rms_db < -1
    CLIPPING: rms_db >= -1 or peak_db >= -0.5
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class AudioLevel(StrEnum):
    """Categorical audio level classification."""

    SILENT = "silent"
    TOO_QUIET = "too_quiet"
    OK = "ok"
    LOUD = "loud"
    CLIPPING = "clipping"


@dataclass(frozen=True)
class LevelReading:
    """Result of a level computation."""

    rms_db: float
    peak_db: float
    level: AudioLevel


class LevelMeter:
    """Computes audio levels from PCM sample arrays."""

    def compute(self, chunk: np.ndarray) -> LevelReading:  # type: ignore[type-arg]
        """Compute RMS and peak levels for the given audio chunk.

        Args:
            chunk: 1D numpy array of float32 audio samples.

        Returns:
            LevelReading with rms_db, peak_db, and categorical level.
        """
        if chunk.size == 0:
            return LevelReading(
                rms_db=float("-inf"),
                peak_db=float("-inf"),
                level=AudioLevel.SILENT,
            )

        # Compute RMS
        rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
        peak = float(np.max(np.abs(chunk)))

        # Convert to dBFS (0 dBFS = full scale = amplitude 1.0)
        rms_db = 20.0 * math.log10(rms) if rms > 0 else float("-inf")
        peak_db = 20.0 * math.log10(peak) if peak > 0 else float("-inf")

        # Classify level
        level = self._classify(rms_db, peak_db)

        return LevelReading(rms_db=rms_db, peak_db=peak_db, level=level)

    def _classify(self, rms_db: float, peak_db: float) -> AudioLevel:
        """Classify audio level based on dBFS thresholds.

        Thresholds from spec 02, section 6, note 6:
            SILENT: rms_db < -60
            TOO_QUIET: -60 <= rms_db < -40
            OK: -40 <= rms_db < -6
            LOUD: -6 <= rms_db < -1
            CLIPPING: rms_db >= -1 or peak_db >= -0.5
        """
        # Check for clipping first (highest priority)
        if rms_db >= -1.0 or peak_db >= -0.5:
            return AudioLevel.CLIPPING

        if rms_db < -60.0:
            return AudioLevel.SILENT

        if rms_db < -40.0:
            return AudioLevel.TOO_QUIET

        if rms_db < -6.0:
            return AudioLevel.OK

        # -6 <= rms_db < -1
        return AudioLevel.LOUD
