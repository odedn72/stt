# TDD: Written from spec 02-audio-capture.md
"""
Tests for LevelMeter — computes audio level from PCM samples.

LevelMeter is a pure function: takes a chunk, returns a LevelReading.
Tests use synthetic audio (silence, sine waves, clipping) as numpy arrays.

dBFS thresholds from spec 02, section 6, note 6:
    SILENT: rms_db < -60
    TOO_QUIET: -60 <= rms_db < -40
    OK: -40 <= rms_db < -6
    LOUD: -6 <= rms_db < -1
    CLIPPING: rms_db >= -1 or peak_db >= -0.5
"""

from __future__ import annotations

import numpy as np
import pytest

from systemstt.audio.level_meter import LevelMeter, LevelReading, AudioLevel


# ---------------------------------------------------------------------------
# AudioLevel enum tests
# ---------------------------------------------------------------------------

class TestAudioLevel:
    """Tests for the AudioLevel enum."""

    def test_silent_value(self) -> None:
        assert AudioLevel.SILENT.value == "silent"

    def test_too_quiet_value(self) -> None:
        assert AudioLevel.TOO_QUIET.value == "too_quiet"

    def test_ok_value(self) -> None:
        assert AudioLevel.OK.value == "ok"

    def test_loud_value(self) -> None:
        assert AudioLevel.LOUD.value == "loud"

    def test_clipping_value(self) -> None:
        assert AudioLevel.CLIPPING.value == "clipping"


# ---------------------------------------------------------------------------
# LevelReading data model tests
# ---------------------------------------------------------------------------

class TestLevelReading:
    """Tests for the LevelReading dataclass."""

    def test_level_reading_fields(self) -> None:
        reading = LevelReading(rms_db=-20.0, peak_db=-15.0, level=AudioLevel.OK)
        assert reading.rms_db == -20.0
        assert reading.peak_db == -15.0
        assert reading.level == AudioLevel.OK

    def test_level_reading_is_frozen(self) -> None:
        reading = LevelReading(rms_db=-20.0, peak_db=-15.0, level=AudioLevel.OK)
        with pytest.raises(AttributeError):
            reading.rms_db = -10.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# LevelMeter computation tests
# ---------------------------------------------------------------------------

class TestLevelMeterSilence:
    """Tests for silence detection."""

    def test_silence_classified_as_silent(self, silence_chunk: np.ndarray) -> None:
        meter = LevelMeter()
        reading = meter.compute(silence_chunk)
        assert reading.level == AudioLevel.SILENT

    def test_silence_rms_is_negative_infinity_or_very_low(
        self, silence_chunk: np.ndarray
    ) -> None:
        meter = LevelMeter()
        reading = meter.compute(silence_chunk)
        # For true silence, rms_db should be -inf or very negative
        assert reading.rms_db < -60


class TestLevelMeterQuiet:
    """Tests for quiet audio detection."""

    def test_quiet_audio_classified_as_too_quiet(
        self, quiet_chunk: np.ndarray
    ) -> None:
        meter = LevelMeter()
        reading = meter.compute(quiet_chunk)
        assert reading.level == AudioLevel.TOO_QUIET

    def test_quiet_audio_rms_in_expected_range(
        self, quiet_chunk: np.ndarray
    ) -> None:
        meter = LevelMeter()
        reading = meter.compute(quiet_chunk)
        assert -60 <= reading.rms_db < -40


class TestLevelMeterNormal:
    """Tests for normal speaking level."""

    def test_normal_sine_classified_as_ok(
        self, sine_wave_chunk: np.ndarray
    ) -> None:
        meter = LevelMeter()
        reading = meter.compute(sine_wave_chunk)
        assert reading.level == AudioLevel.OK

    def test_normal_sine_rms_in_expected_range(
        self, sine_wave_chunk: np.ndarray
    ) -> None:
        meter = LevelMeter()
        reading = meter.compute(sine_wave_chunk)
        # 0.5 amplitude sine wave: RMS = 0.5/sqrt(2) ~ 0.354
        # 20 * log10(0.354) ~ -9 dB
        assert -40 <= reading.rms_db < -1


class TestLevelMeterLoud:
    """Tests for loud audio detection."""

    def test_loud_audio_classified_as_loud_or_clipping(
        self, loud_chunk: np.ndarray
    ) -> None:
        meter = LevelMeter()
        reading = meter.compute(loud_chunk)
        # 0.99 amplitude: RMS ~ -3dB, should be LOUD or possibly CLIPPING
        assert reading.level in (AudioLevel.LOUD, AudioLevel.CLIPPING)


class TestLevelMeterClipping:
    """Tests for clipping detection."""

    def test_clipping_audio_classified_as_clipping(
        self, clipping_chunk: np.ndarray
    ) -> None:
        meter = LevelMeter()
        reading = meter.compute(clipping_chunk)
        assert reading.level == AudioLevel.CLIPPING

    def test_clipping_peak_near_zero_dbfs(
        self, clipping_chunk: np.ndarray
    ) -> None:
        meter = LevelMeter()
        reading = meter.compute(clipping_chunk)
        assert reading.peak_db >= -0.5


class TestLevelMeterEdgeCases:
    """Tests for edge cases in level computation."""

    def test_empty_chunk_returns_silent(self, empty_chunk: np.ndarray) -> None:
        meter = LevelMeter()
        reading = meter.compute(empty_chunk)
        assert reading.level == AudioLevel.SILENT

    def test_single_sample_chunk(self) -> None:
        meter = LevelMeter()
        chunk = np.array([0.5], dtype=np.float32)
        reading = meter.compute(chunk)
        assert isinstance(reading, LevelReading)

    def test_peak_is_always_gte_rms(self, sine_wave_chunk: np.ndarray) -> None:
        meter = LevelMeter()
        reading = meter.compute(sine_wave_chunk)
        assert reading.peak_db >= reading.rms_db

    def test_returns_level_reading_type(self, sine_wave_chunk: np.ndarray) -> None:
        meter = LevelMeter()
        reading = meter.compute(sine_wave_chunk)
        assert isinstance(reading, LevelReading)
        assert isinstance(reading.level, AudioLevel)

    def test_all_negative_samples(self) -> None:
        """Audio with all negative samples should still compute valid levels."""
        meter = LevelMeter()
        chunk = np.full(8000, -0.5, dtype=np.float32)
        reading = meter.compute(chunk)
        assert isinstance(reading, LevelReading)
        assert reading.rms_db < 0  # Should be negative dBFS

    def test_dc_offset_signal(self) -> None:
        """A constant DC signal (non-zero, non-clipping) computes valid levels."""
        meter = LevelMeter()
        chunk = np.full(8000, 0.1, dtype=np.float32)
        reading = meter.compute(chunk)
        # RMS of constant 0.1 = 0.1 => 20*log10(0.1) = -20 dBFS
        assert -25 <= reading.rms_db <= -15

    def test_boundary_between_silent_and_too_quiet(self) -> None:
        """Audio at exactly the SILENT/TOO_QUIET boundary.

        Per spec, -60 dBFS is TOO_QUIET, not SILENT.
        Amplitude for -60 dBFS RMS sine: 10^(-60/20) * sqrt(2) ~ 0.001414
        """
        meter = LevelMeter()
        num_samples = 8000
        t = np.linspace(0, 0.5, num_samples, endpoint=False, dtype=np.float32)
        # Amplitude chosen so RMS is right at -60 dBFS
        amplitude = 10 ** (-60 / 20) * np.sqrt(2)
        chunk = (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        reading = meter.compute(chunk)
        # The RMS should be very close to -60 dBFS
        assert -61 <= reading.rms_db <= -59

    def test_peak_db_for_clipping_chunk(self, clipping_chunk: np.ndarray) -> None:
        """Peak of a full-scale signal should be at 0 dBFS."""
        meter = LevelMeter()
        reading = meter.compute(clipping_chunk)
        # peak is 1.0, so 20*log10(1.0) = 0 dBFS
        assert reading.peak_db == pytest.approx(0.0, abs=0.01)

    def test_rms_db_for_silence_is_negative_infinity(
        self, silence_chunk: np.ndarray
    ) -> None:
        """True silence (all zeros) should have rms_db = -inf."""
        meter = LevelMeter()
        reading = meter.compute(silence_chunk)
        assert reading.rms_db == float("-inf")
