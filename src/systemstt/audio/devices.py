"""
DeviceEnumerator — lists and monitors audio input devices.

Wraps sounddevice's device query APIs to provide a clean interface
for discovering available input devices.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import sounddevice as sd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioDevice:
    """Represents a single audio input device."""

    device_id: int
    name: str
    is_default: bool
    max_input_channels: int
    sample_rate: float


class DeviceEnumerator:
    """Enumerates and queries available audio input devices."""

    def list_input_devices(self) -> list[AudioDevice]:
        """Return a list of all input-capable audio devices.

        Only devices with max_input_channels > 0 are included.
        The default input device is marked with is_default=True.
        """
        try:
            all_devices = sd.query_devices()
            default_input_id, _ = sd.default.device
        except Exception as exc:
            logger.warning("Failed to query audio devices: %s", exc)
            return []

        if not isinstance(all_devices, list):
            all_devices = [all_devices]

        result: list[AudioDevice] = []
        for dev_info in all_devices:
            if dev_info.get("max_input_channels", 0) > 0:
                dev_id = dev_info.get("index", -1)
                result.append(
                    AudioDevice(
                        device_id=dev_id,
                        name=dev_info.get("name", "Unknown"),
                        is_default=(dev_id == default_input_id),
                        max_input_channels=dev_info.get("max_input_channels", 0),
                        sample_rate=dev_info.get("default_samplerate", 44100.0),
                    )
                )
        return result

    def get_default_device(self) -> Optional[AudioDevice]:
        """Return the default input device, or None if no input devices exist."""
        devices = self.list_input_devices()
        for dev in devices:
            if dev.is_default:
                return dev
        return None

    def get_device_by_id(self, device_id: int) -> Optional[AudioDevice]:
        """Return an input device by its ID, or None if not found or not input-capable."""
        devices = self.list_input_devices()
        for dev in devices:
            if dev.device_id == device_id:
                return dev
        return None

    def refresh(self) -> list[AudioDevice]:
        """Re-query devices and return the updated list."""
        return self.list_input_devices()
