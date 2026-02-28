# TDD: Written from spec 02-audio-capture.md
"""
Tests for DeviceEnumerator — lists and monitors audio input devices.

All sounddevice calls are mocked.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from systemstt.audio.devices import DeviceEnumerator, AudioDevice


# ---------------------------------------------------------------------------
# AudioDevice data model tests
# ---------------------------------------------------------------------------

class TestAudioDevice:
    """Tests for the AudioDevice dataclass."""

    def test_audio_device_fields(self) -> None:
        device = AudioDevice(
            device_id=0,
            name="Built-in Microphone",
            is_default=True,
            max_input_channels=1,
            sample_rate=44100.0,
        )
        assert device.device_id == 0
        assert device.name == "Built-in Microphone"
        assert device.is_default is True
        assert device.max_input_channels == 1
        assert device.sample_rate == 44100.0

    def test_audio_device_is_frozen(self) -> None:
        device = AudioDevice(
            device_id=0, name="Mic", is_default=True,
            max_input_channels=1, sample_rate=44100.0,
        )
        with pytest.raises(AttributeError):
            device.name = "Other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DeviceEnumerator tests
# ---------------------------------------------------------------------------

class TestDeviceEnumeratorListDevices:
    """Tests for listing available input devices."""

    @patch("systemstt.audio.devices.sd")
    def test_list_input_devices_returns_only_input_devices(
        self, mock_sd: MagicMock, mock_audio_devices: list[dict[str, Any]]
    ) -> None:
        mock_sd.query_devices.return_value = mock_audio_devices
        mock_sd.default.device = (0, 2)  # (input_default, output_default)
        enum = DeviceEnumerator()
        devices = enum.list_input_devices()
        # Only devices with max_input_channels > 0 should be returned
        assert len(devices) == 2
        names = [d.name for d in devices]
        assert "Built-in Microphone" in names
        assert "USB Mic Pro" in names
        assert "Speakers" not in names

    @patch("systemstt.audio.devices.sd")
    def test_list_input_devices_returns_audio_device_instances(
        self, mock_sd: MagicMock, mock_audio_devices: list[dict[str, Any]]
    ) -> None:
        mock_sd.query_devices.return_value = mock_audio_devices
        mock_sd.default.device = (0, 2)
        enum = DeviceEnumerator()
        devices = enum.list_input_devices()
        for device in devices:
            assert isinstance(device, AudioDevice)

    @patch("systemstt.audio.devices.sd")
    def test_list_input_devices_empty_when_no_devices(
        self, mock_sd: MagicMock
    ) -> None:
        mock_sd.query_devices.return_value = []
        mock_sd.default.device = (-1, -1)
        enum = DeviceEnumerator()
        devices = enum.list_input_devices()
        assert devices == []

    @patch("systemstt.audio.devices.sd")
    def test_list_input_devices_marks_default(
        self, mock_sd: MagicMock, mock_audio_devices: list[dict[str, Any]]
    ) -> None:
        mock_sd.query_devices.return_value = mock_audio_devices
        mock_sd.default.device = (0, 2)  # device 0 is default input
        enum = DeviceEnumerator()
        devices = enum.list_input_devices()
        default_devices = [d for d in devices if d.is_default]
        assert len(default_devices) == 1
        assert default_devices[0].device_id == 0


class TestDeviceEnumeratorGetDevice:
    """Tests for getting specific devices."""

    @patch("systemstt.audio.devices.sd")
    def test_get_default_device_returns_default(
        self, mock_sd: MagicMock, mock_audio_devices: list[dict[str, Any]]
    ) -> None:
        mock_sd.query_devices.return_value = mock_audio_devices
        mock_sd.default.device = (0, 2)
        enum = DeviceEnumerator()
        default = enum.get_default_device()
        assert default is not None
        assert default.device_id == 0
        assert default.is_default is True

    @patch("systemstt.audio.devices.sd")
    def test_get_default_device_returns_none_when_no_input_devices(
        self, mock_sd: MagicMock
    ) -> None:
        mock_sd.query_devices.return_value = [
            {"name": "Speakers", "index": 0, "max_input_channels": 0,
             "max_output_channels": 2, "default_samplerate": 44100.0},
        ]
        mock_sd.default.device = (-1, 0)
        enum = DeviceEnumerator()
        default = enum.get_default_device()
        assert default is None

    @patch("systemstt.audio.devices.sd")
    def test_get_device_by_id_returns_correct_device(
        self, mock_sd: MagicMock, mock_audio_devices: list[dict[str, Any]]
    ) -> None:
        mock_sd.query_devices.return_value = mock_audio_devices
        mock_sd.default.device = (0, 2)
        enum = DeviceEnumerator()
        device = enum.get_device_by_id(1)
        assert device is not None
        assert device.name == "USB Mic Pro"

    @patch("systemstt.audio.devices.sd")
    def test_get_device_by_id_returns_none_for_nonexistent(
        self, mock_sd: MagicMock, mock_audio_devices: list[dict[str, Any]]
    ) -> None:
        mock_sd.query_devices.return_value = mock_audio_devices
        mock_sd.default.device = (0, 2)
        enum = DeviceEnumerator()
        device = enum.get_device_by_id(999)
        assert device is None

    @patch("systemstt.audio.devices.sd")
    def test_get_device_by_id_returns_none_for_output_only_device(
        self, mock_sd: MagicMock, mock_audio_devices: list[dict[str, Any]]
    ) -> None:
        mock_sd.query_devices.return_value = mock_audio_devices
        mock_sd.default.device = (0, 2)
        enum = DeviceEnumerator()
        device = enum.get_device_by_id(2)  # Speakers (output only)
        assert device is None


class TestDeviceEnumeratorRefresh:
    """Tests for device refresh functionality."""

    @patch("systemstt.audio.devices.sd")
    def test_refresh_returns_updated_device_list(
        self, mock_sd: MagicMock
    ) -> None:
        # First call: one device
        mock_sd.query_devices.return_value = [
            {"name": "Mic A", "index": 0, "max_input_channels": 1,
             "max_output_channels": 0, "default_samplerate": 44100.0},
        ]
        mock_sd.default.device = (0, -1)
        enum = DeviceEnumerator()
        devices1 = enum.list_input_devices()
        assert len(devices1) == 1

        # After refresh: two devices
        mock_sd.query_devices.return_value = [
            {"name": "Mic A", "index": 0, "max_input_channels": 1,
             "max_output_channels": 0, "default_samplerate": 44100.0},
            {"name": "Mic B", "index": 1, "max_input_channels": 1,
             "max_output_channels": 0, "default_samplerate": 48000.0},
        ]
        devices2 = enum.refresh()
        assert len(devices2) == 2


# ---------------------------------------------------------------------------
# DeviceEnumerator edge case tests
# ---------------------------------------------------------------------------

class TestDeviceEnumeratorEdgeCases:
    """Edge case tests for device enumeration."""

    @patch("systemstt.audio.devices.sd")
    def test_query_devices_exception_returns_empty_list(
        self, mock_sd: MagicMock
    ) -> None:
        """When sounddevice raises an exception, list_input_devices returns []."""
        mock_sd.query_devices.side_effect = RuntimeError("PortAudio not available")
        enum = DeviceEnumerator()
        devices = enum.list_input_devices()
        assert devices == []

    @patch("systemstt.audio.devices.sd")
    def test_single_device_returned_as_dict_not_list(
        self, mock_sd: MagicMock
    ) -> None:
        """When sounddevice returns a single device (not a list), handle gracefully."""
        single_device = {
            "name": "Solo Mic", "index": 0, "max_input_channels": 1,
            "max_output_channels": 0, "default_samplerate": 44100.0,
        }
        mock_sd.query_devices.return_value = single_device
        mock_sd.default.device = (0, -1)
        enum = DeviceEnumerator()
        devices = enum.list_input_devices()
        assert len(devices) == 1
        assert devices[0].name == "Solo Mic"

    @patch("systemstt.audio.devices.sd")
    def test_device_with_missing_name_uses_unknown(
        self, mock_sd: MagicMock
    ) -> None:
        """A device dict missing 'name' should default to 'Unknown'."""
        mock_sd.query_devices.return_value = [
            {"index": 0, "max_input_channels": 1, "max_output_channels": 0,
             "default_samplerate": 44100.0},
        ]
        mock_sd.default.device = (0, -1)
        enum = DeviceEnumerator()
        devices = enum.list_input_devices()
        assert len(devices) == 1
        assert devices[0].name == "Unknown"

    @patch("systemstt.audio.devices.sd")
    def test_get_default_device_when_query_fails_returns_none(
        self, mock_sd: MagicMock
    ) -> None:
        """When query_devices fails, get_default_device should return None."""
        mock_sd.query_devices.side_effect = RuntimeError("fail")
        enum = DeviceEnumerator()
        assert enum.get_default_device() is None
