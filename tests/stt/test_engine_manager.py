# TDD: Written from spec 03-stt-engine.md
"""
Tests for EngineManager — manages STT engine lifecycle and hot-swapping.

Tests verify:
- Active engine management
- Engine switching (hot-swap without restart)
- Config updates
- Shutdown behavior
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from systemstt.errors import STTEngineError
from systemstt.stt.base import EngineState, EngineType
from systemstt.stt.cloud_api import CloudAPIConfig
from systemstt.stt.engine_manager import EngineManager
from systemstt.stt.local_whisper import LocalWhisperConfig, WhisperModelSize

# ---------------------------------------------------------------------------
# EngineManager initialization tests
# ---------------------------------------------------------------------------


class TestEngineManagerInit:
    """Tests for EngineManager creation and initial state."""

    def test_active_engine_is_none_initially(self) -> None:
        local_config = LocalWhisperConfig()
        cloud_config = CloudAPIConfig(api_key="sk-test")
        manager = EngineManager(local_config, cloud_config)
        assert manager.active_engine is None

    def test_active_engine_type_is_none_initially(self) -> None:
        local_config = LocalWhisperConfig()
        cloud_config = CloudAPIConfig(api_key="sk-test")
        manager = EngineManager(local_config, cloud_config)
        assert manager.active_engine_type is None


# ---------------------------------------------------------------------------
# EngineManager activation tests
# ---------------------------------------------------------------------------


class TestEngineManagerActivation:
    """Tests for engine activation and switching."""

    @pytest.mark.asyncio
    @patch("systemstt.stt.engine_manager.CloudAPIEngine")
    async def test_activate_cloud_engine(self, mock_cloud_cls: MagicMock) -> None:
        mock_engine = AsyncMock()
        mock_engine.engine_type = EngineType.CLOUD_API
        mock_engine.state = EngineState.READY
        mock_engine.initialize = AsyncMock()
        mock_engine.shutdown = AsyncMock()
        mock_cloud_cls.return_value = mock_engine

        local_config = LocalWhisperConfig()
        cloud_config = CloudAPIConfig(api_key="sk-test")
        manager = EngineManager(local_config, cloud_config)

        await manager.activate_engine(EngineType.CLOUD_API)
        assert manager.active_engine is not None
        assert manager.active_engine_type == EngineType.CLOUD_API

    @pytest.mark.asyncio
    @patch("systemstt.stt.engine_manager.LocalWhisperEngine")
    async def test_activate_local_engine(self, mock_local_cls: MagicMock) -> None:
        mock_engine = AsyncMock()
        mock_engine.engine_type = EngineType.LOCAL_WHISPER
        mock_engine.state = EngineState.READY
        mock_engine.initialize = AsyncMock()
        mock_engine.shutdown = AsyncMock()
        mock_local_cls.return_value = mock_engine

        local_config = LocalWhisperConfig()
        cloud_config = CloudAPIConfig(api_key="sk-test")
        manager = EngineManager(local_config, cloud_config)

        await manager.activate_engine(EngineType.LOCAL_WHISPER)
        assert manager.active_engine_type == EngineType.LOCAL_WHISPER

    @pytest.mark.asyncio
    @patch("systemstt.stt.engine_manager.LocalWhisperEngine")
    @patch("systemstt.stt.engine_manager.CloudAPIEngine")
    async def test_switching_engine_shuts_down_previous(
        self, mock_cloud_cls: MagicMock, mock_local_cls: MagicMock
    ) -> None:
        mock_cloud = AsyncMock()
        mock_cloud.engine_type = EngineType.CLOUD_API
        mock_cloud.state = EngineState.READY
        mock_cloud_cls.return_value = mock_cloud

        mock_local = AsyncMock()
        mock_local.engine_type = EngineType.LOCAL_WHISPER
        mock_local.state = EngineState.READY
        mock_local_cls.return_value = mock_local

        local_config = LocalWhisperConfig()
        cloud_config = CloudAPIConfig(api_key="sk-test")
        manager = EngineManager(local_config, cloud_config)

        await manager.activate_engine(EngineType.CLOUD_API)
        await manager.activate_engine(EngineType.LOCAL_WHISPER)

        # Cloud engine should have been shut down
        mock_cloud.shutdown.assert_called_once()
        assert manager.active_engine_type == EngineType.LOCAL_WHISPER

    @pytest.mark.asyncio
    @patch("systemstt.stt.engine_manager.CloudAPIEngine")
    async def test_activate_engine_failure_raises_stt_engine_error(
        self, mock_cloud_cls: MagicMock
    ) -> None:
        mock_engine = AsyncMock()
        mock_engine.initialize.side_effect = STTEngineError("init failed")
        mock_cloud_cls.return_value = mock_engine

        local_config = LocalWhisperConfig()
        cloud_config = CloudAPIConfig(api_key="sk-test")
        manager = EngineManager(local_config, cloud_config)

        with pytest.raises(STTEngineError):
            await manager.activate_engine(EngineType.CLOUD_API)


# ---------------------------------------------------------------------------
# EngineManager shutdown tests
# ---------------------------------------------------------------------------


class TestEngineManagerShutdown:
    """Tests for manager shutdown."""

    @pytest.mark.asyncio
    @patch("systemstt.stt.engine_manager.CloudAPIEngine")
    async def test_shutdown_shuts_down_active_engine(self, mock_cloud_cls: MagicMock) -> None:
        mock_engine = AsyncMock()
        mock_engine.engine_type = EngineType.CLOUD_API
        mock_engine.state = EngineState.READY
        mock_cloud_cls.return_value = mock_engine

        local_config = LocalWhisperConfig()
        cloud_config = CloudAPIConfig(api_key="sk-test")
        manager = EngineManager(local_config, cloud_config)

        await manager.activate_engine(EngineType.CLOUD_API)
        await manager.shutdown()

        mock_engine.shutdown.assert_called()
        assert manager.active_engine is None

    @pytest.mark.asyncio
    async def test_shutdown_when_no_engine_is_safe(self) -> None:
        local_config = LocalWhisperConfig()
        cloud_config = CloudAPIConfig(api_key="sk-test")
        manager = EngineManager(local_config, cloud_config)
        await manager.shutdown()  # Should not raise


# ---------------------------------------------------------------------------
# EngineManager config update tests
# ---------------------------------------------------------------------------


class TestEngineManagerConfigUpdate:
    """Tests for configuration updates."""

    def test_update_local_config(self) -> None:
        local_config = LocalWhisperConfig()
        cloud_config = CloudAPIConfig(api_key="sk-test")
        manager = EngineManager(local_config, cloud_config)

        new_config = LocalWhisperConfig(model_size=WhisperModelSize.SMALL)
        manager.update_local_config(new_config)
        # Config should be stored for next activation (no assertion on internals,
        # but should not raise)

    def test_update_cloud_config(self) -> None:
        local_config = LocalWhisperConfig()
        cloud_config = CloudAPIConfig(api_key="sk-test")
        manager = EngineManager(local_config, cloud_config)

        new_config = CloudAPIConfig(api_key="sk-new-key")
        manager.update_cloud_config(new_config)
        # Should not raise
