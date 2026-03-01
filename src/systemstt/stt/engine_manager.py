"""
EngineManager — manages STT engine lifecycle and hot-swapping.

Provides a single point of control for activating, switching between,
and shutting down STT engines.
"""

from __future__ import annotations

import logging

from systemstt.errors import STTEngineError
from systemstt.stt.base import EngineType, STTEngine
from systemstt.stt.cloud_api import CloudAPIConfig, CloudAPIEngine
from systemstt.stt.local_whisper import LocalWhisperConfig, LocalWhisperEngine

logger = logging.getLogger(__name__)


class EngineManager:
    """Manages STT engine lifecycle and switching."""

    def __init__(
        self,
        local_config: LocalWhisperConfig,
        cloud_config: CloudAPIConfig,
    ) -> None:
        self._local_config = local_config
        self._cloud_config = cloud_config
        self._active_engine: STTEngine | None = None
        self._active_engine_type: EngineType | None = None

    @property
    def active_engine(self) -> STTEngine | None:
        """Return the currently active engine, or None."""
        return self._active_engine

    @property
    def active_engine_type(self) -> EngineType | None:
        """Return the type of the currently active engine, or None."""
        return self._active_engine_type

    async def activate_engine(self, engine_type: EngineType) -> None:
        """Activate the specified engine type.

        If a different engine is currently active, it will be shut down first.
        Raises STTEngineError if initialization fails.
        """
        # Shut down current engine if different
        if self._active_engine is not None:
            await self._active_engine.shutdown()
            self._active_engine = None
            self._active_engine_type = None

        # Create new engine
        if engine_type == EngineType.CLOUD_API:
            engine: STTEngine = CloudAPIEngine(self._cloud_config)
        elif engine_type == EngineType.LOCAL_WHISPER:
            engine = LocalWhisperEngine(self._local_config)
        else:
            raise STTEngineError(f"Unknown engine type: {engine_type}")

        # Initialize
        await engine.initialize()

        self._active_engine = engine
        self._active_engine_type = engine_type
        logger.info("Activated engine: %s", engine_type.value)

    async def shutdown(self) -> None:
        """Shut down the active engine if any."""
        if self._active_engine is not None:
            await self._active_engine.shutdown()
            self._active_engine = None
            self._active_engine_type = None

    def update_local_config(self, config: LocalWhisperConfig) -> None:
        """Update the local engine configuration for next activation."""
        self._local_config = config

    def update_cloud_config(self, config: CloudAPIConfig) -> None:
        """Update the cloud engine configuration for next activation."""
        self._cloud_config = config
