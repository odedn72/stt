"""
Tests for the AppController, AsyncWorker, and AudioBridge.

Verifies the central orchestrator wires components correctly and drives
the dictation lifecycle through the DictationStateMachine.
"""

from __future__ import annotations

import asyncio
import os

# Force offscreen rendering before any Qt import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import numpy as np
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from systemstt.app import DictationState
from systemstt.config.models import EngineType as ConfigEngineType, SettingsModel
from systemstt.controller import (
    AppController,
    AsyncWorker,
    AudioBridge,
    _CLOUD_BUFFER_SAMPLES,
    _LOCAL_BUFFER_SAMPLES,
    _SILENCE_RMS_THRESHOLD,
)
from systemstt.stt.base import (
    DetectedLanguage,
    EngineType as STTEngineType,
    TranscriptionResult,
    TranscriptionSegment,
)


# ---------------------------------------------------------------------------
# Session-scoped QApplication
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def qapp() -> QApplication:
    """Ensure a QApplication instance exists."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audio_chunk(num_samples: int) -> np.ndarray:
    """Create a non-silent audio chunk (sine wave) for tests."""
    t = np.linspace(0, num_samples / 16000, num_samples, endpoint=False, dtype=np.float32)
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def _make_transcription_result(
    text: str = "Hello world",
    language: DetectedLanguage = DetectedLanguage.ENGLISH,
) -> TranscriptionResult:
    return TranscriptionResult(
        segments=[
            TranscriptionSegment(
                text=text,
                language=language,
                start_time=0.0,
                end_time=1.0,
                confidence=0.95,
                is_partial=False,
            ),
        ],
        full_text=text,
        primary_language=language,
        processing_time_ms=100.0,
    )


# ---------------------------------------------------------------------------
# Mock dependencies fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_deps() -> dict[str, Any]:
    """Create all mocked dependencies for AppController."""
    settings_store = MagicMock()
    settings_store.load.return_value = SettingsModel()
    settings_store.save = MagicMock()

    secure_store = MagicMock()
    secure_store.get.return_value = "test-api-key"

    shutdown_manager = MagicMock()
    shutdown_manager.register = MagicMock()

    hotkey_manager = MagicMock()
    hotkey_manager.register = MagicMock()
    hotkey_manager.unregister = MagicMock()
    hotkey_manager.update_binding = MagicMock()
    type(hotkey_manager).is_registered = PropertyMock(return_value=False)

    text_injector = MagicMock()
    text_injector.inject_text = AsyncMock()
    text_injector.send_keystroke = AsyncMock()
    text_injector.has_accessibility_permission = MagicMock(return_value=True)

    return {
        "settings_store": settings_store,
        "secure_store": secure_store,
        "shutdown_manager": shutdown_manager,
        "hotkey_manager": hotkey_manager,
        "text_injector": text_injector,
    }


# ===========================================================================
# AsyncWorker tests
# ===========================================================================


class TestAsyncWorker:
    """Tests for the AsyncWorker QThread."""

    def test_start_and_stop(self) -> None:
        worker = AsyncWorker()
        worker.start()
        worker.wait_until_running()
        assert worker.isRunning()
        assert worker.loop_running

        worker.stop_loop()
        assert not worker.isRunning()
        assert not worker.loop_running

    def test_schedule_runs_coroutine(self) -> None:
        worker = AsyncWorker()
        worker.start()
        worker.wait_until_running()

        result_box: list[int] = []

        async def _work() -> None:
            result_box.append(42)

        future = worker.schedule(_work())
        assert future is not None
        future.result(timeout=2.0)
        assert result_box == [42]

        worker.stop_loop()

    def test_schedule_returns_none_when_not_running(self) -> None:
        worker = AsyncWorker()
        # Not started — schedule should return None without running the coro
        coro = asyncio.sleep(0)
        result = worker.schedule(coro)
        assert result is None
        coro.close()  # Avoid "coroutine was never awaited" warning

    def test_engine_ready_signal(self) -> None:
        worker = AsyncWorker()
        worker.start()
        worker.wait_until_running()

        received: list[bool] = []
        worker.engine_ready.connect(lambda: received.append(True))

        engine_manager = MagicMock()
        engine_manager.activate_engine = AsyncMock()

        worker.schedule_activate_engine(
            engine_manager, STTEngineType.CLOUD_API,
        )

        # Wait for signal
        _wait_for(lambda: len(received) > 0)
        assert received == [True]
        engine_manager.activate_engine.assert_awaited_once_with(
            STTEngineType.CLOUD_API,
        )

        worker.stop_loop()

    def test_engine_error_signal(self) -> None:
        worker = AsyncWorker()
        worker.start()
        worker.wait_until_running()

        errors: list[str] = []
        worker.engine_error.connect(lambda msg: errors.append(msg))

        engine_manager = MagicMock()
        engine_manager.activate_engine = AsyncMock(
            side_effect=Exception("load failed"),
        )

        worker.schedule_activate_engine(
            engine_manager, STTEngineType.LOCAL_WHISPER,
        )

        _wait_for(lambda: len(errors) > 0)
        assert "load failed" in errors[0]

        worker.stop_loop()

    def test_transcription_result_signal(self) -> None:
        worker = AsyncWorker()
        worker.start()
        worker.wait_until_running()

        results: list[TranscriptionResult] = []
        worker.transcription_result.connect(lambda r: results.append(r))

        expected = _make_transcription_result()

        engine = MagicMock()
        engine.transcribe = AsyncMock(return_value=expected)

        audio = np.zeros(8000, dtype=np.float32)
        worker.schedule_transcribe(engine, audio)

        _wait_for(lambda: len(results) > 0)
        assert results[0].full_text == "Hello world"

        worker.stop_loop()

    def test_transcription_error_signal(self) -> None:
        worker = AsyncWorker()
        worker.start()
        worker.wait_until_running()

        errors: list[str] = []
        worker.transcription_error.connect(lambda msg: errors.append(msg))

        engine = MagicMock()
        engine.transcribe = AsyncMock(side_effect=Exception("api timeout"))

        audio = np.zeros(8000, dtype=np.float32)
        worker.schedule_transcribe(engine, audio)

        _wait_for(lambda: len(errors) > 0)
        assert "api timeout" in errors[0]

        worker.stop_loop()

    def test_schedule_inject_text(self) -> None:
        worker = AsyncWorker()
        worker.start()
        worker.wait_until_running()

        injector = MagicMock()
        injector.inject_text = AsyncMock()

        worker.schedule_inject_text(injector, "Hello")

        # Wait for coroutine to complete
        _wait_for(lambda: injector.inject_text.await_count > 0)
        injector.inject_text.assert_awaited_once_with("Hello")

        worker.stop_loop()


# ===========================================================================
# AudioBridge tests
# ===========================================================================


class TestAudioBridge:
    """Tests for the AudioBridge signal marshalling."""

    def test_chunk_signal_emitted(self) -> None:
        bridge = AudioBridge()
        received: list[np.ndarray] = []
        bridge.chunk_received.connect(lambda c: received.append(c))

        chunk = np.zeros(100, dtype=np.float32)
        bridge.on_chunk(chunk)

        # Direct connection in same thread — signal arrives immediately
        assert len(received) == 1
        np.testing.assert_array_equal(received[0], chunk)

    def test_error_signal_emitted(self) -> None:
        bridge = AudioBridge()
        errors: list[str] = []
        bridge.error_received.connect(lambda msg: errors.append(msg))

        bridge.on_error(RuntimeError("mic disconnected"))

        assert len(errors) == 1
        assert "mic disconnected" in errors[0]


# ===========================================================================
# AppController tests
# ===========================================================================


class TestAppControllerConstruction:
    """Tests for AppController creation and initial state."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_construction(
        self,
        mock_engine_mgr_cls: MagicMock,
        mock_recorder_cls: MagicMock,
        mock_pill_cls: MagicMock,
        mock_menu_cls: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Controller creates all components on init."""
        controller = AppController(**mock_deps)

        assert controller._state_machine.state == DictationState.IDLE
        mock_recorder_cls.assert_called_once()
        mock_engine_mgr_cls.assert_called_once()
        mock_menu_cls.assert_called_once()
        mock_pill_cls.assert_called_once()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_loads_settings(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Constructor loads settings from the store."""
        controller = AppController(**mock_deps)

        mock_deps["settings_store"].load.assert_called_once()
        assert isinstance(controller._settings, SettingsModel)

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_registers_shutdown_tasks(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Constructor registers shutdown tasks."""
        AppController(**mock_deps)

        sm = mock_deps["shutdown_manager"]
        # Expect at least: stop-audio, shutdown-stt, unregister-hotkey,
        # save-settings, stop-async-worker
        assert sm.register.call_count >= 5


class TestAppControllerStart:
    """Tests for AppController.start()."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    @patch.object(AsyncWorker, "start")
    @patch.object(AsyncWorker, "wait_until_running")
    def test_start_registers_hotkey(
        self,
        _mock_wait: MagicMock,
        _mock_worker_start: MagicMock,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller.start()

        mock_deps["hotkey_manager"].register.assert_called_once()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    @patch.object(AsyncWorker, "start")
    @patch.object(AsyncWorker, "wait_until_running")
    def test_start_shows_menu_bar(
        self,
        _mock_wait: MagicMock,
        _mock_worker_start: MagicMock,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        mock_menu_cls: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller.start()

        controller._menu_bar.show.assert_called_once()


class TestDictationLifecycle:
    """Tests for the full dictation lifecycle."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_toggle_from_idle_starts_dictation(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        controller._on_dictation_toggle()

        assert controller._state_machine.state == DictationState.STARTING
        controller._async_worker.schedule_activate_engine.assert_called_once()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_engine_ready_transitions_to_active(
        self,
        _mock_em: MagicMock,
        mock_rec_cls: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        # Start dictation
        controller._on_dictation_toggle()
        assert controller._state_machine.state == DictationState.STARTING

        # Simulate engine ready
        controller._on_engine_ready()
        assert controller._state_machine.state == DictationState.ACTIVE
        controller._recorder.start.assert_called_once()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_engine_error_transitions_to_error(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        controller._on_dictation_toggle()
        controller._on_engine_error("model not found")

        assert controller._state_machine.state == DictationState.ERROR
        controller._floating_pill.show_error.assert_called_once_with(
            "model not found",
        )

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_toggle_from_active_stops_dictation(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        # Go through IDLE → STARTING → ACTIVE
        controller._on_dictation_toggle()
        controller._on_engine_ready()
        assert controller._state_machine.state == DictationState.ACTIVE

        # Stop (no buffered audio)
        controller._on_dictation_toggle()
        assert controller._state_machine.state == DictationState.IDLE
        controller._recorder.stop.assert_called_once()
        controller._floating_pill.hide_pill.assert_called()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_toggle_from_error_dismisses(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        # Go to ERROR
        controller._on_dictation_toggle()
        controller._on_engine_error("fail")
        assert controller._state_machine.state == DictationState.ERROR

        # Toggle from ERROR → IDLE
        controller._on_dictation_toggle()
        assert controller._state_machine.state == DictationState.IDLE

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_toggle_during_starting_is_ignored(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        controller._on_dictation_toggle()
        assert controller._state_machine.state == DictationState.STARTING

        # Second toggle during STARTING is ignored
        controller._on_dictation_toggle()
        assert controller._state_machine.state == DictationState.STARTING


class TestAudioBuffering:
    """Tests for audio buffering and transcription dispatch."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_chunks_accumulated_below_threshold(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        # Enter ACTIVE state
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        # Send a small chunk (below threshold)
        chunk = np.zeros(8000, dtype=np.float32)  # 0.5s
        controller._on_audio_chunk(chunk)

        assert controller._buffered_samples == 8000
        assert len(controller._audio_buffer) == 1
        controller._async_worker.schedule_transcribe.assert_not_called()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_threshold_dispatches_transcription(
        self,
        mock_em_cls: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        # Setup mock engine
        mock_engine = MagicMock()
        controller._engine_manager.active_engine = mock_engine

        # Enter ACTIVE state
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        # Send enough data to cross the 3s threshold (cloud default)
        chunk = _make_audio_chunk(_CLOUD_BUFFER_SAMPLES + 1000)
        controller._on_audio_chunk(chunk)

        controller._async_worker.schedule_transcribe.assert_called_once()
        assert controller._buffered_samples == 0
        assert controller._pending_transcriptions == 1

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_chunks_ignored_when_not_active(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)

        # State is IDLE — chunks should be ignored
        chunk = np.zeros(8000, dtype=np.float32)
        controller._on_audio_chunk(chunk)

        assert controller._buffered_samples == 0


class TestTranscriptionResultHandling:
    """Tests for processing transcription results."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_plain_text_injected(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        # Enter ACTIVE state
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        result = _make_transcription_result("Hello world")
        controller._on_transcription_result(result)

        controller._async_worker.schedule_inject_text.assert_called_once_with(
            mock_deps["text_injector"], "Hello world",
        )

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_voice_command_detected(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        # Enter ACTIVE state
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        # Send text that contains a voice command at the end
        result = _make_transcription_result("some text new line")
        controller._on_transcription_result(result)

        # Should inject "some text" and execute the new_line command
        controller._async_worker.schedule_inject_text.assert_called_once()
        call_args = controller._async_worker.schedule_inject_text.call_args
        assert call_args[0][1] == "some text"

        controller._async_worker.schedule_execute_command.assert_called_once()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_empty_text_ignored(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        controller._on_dictation_toggle()
        controller._on_engine_ready()

        result = _make_transcription_result("   ")
        controller._on_transcription_result(result)

        controller._async_worker.schedule_inject_text.assert_not_called()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_hebrew_language_detected(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        controller._on_dictation_toggle()
        controller._on_engine_ready()

        result = _make_transcription_result(
            "\u05e9\u05dc\u05d5\u05dd \u05e2\u05d5\u05dc\u05dd",
            DetectedLanguage.HEBREW,
        )
        controller._on_transcription_result(result)

        assert controller._current_language == "HE"
        controller._menu_bar.update_language.assert_called_with("HE")

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_live_preview_shown_when_enabled(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        # Enable live preview in settings
        mock_deps["settings_store"].load.return_value = SettingsModel(
            show_live_preview=True,
        )

        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        controller._on_dictation_toggle()
        controller._on_engine_ready()

        result = _make_transcription_result("Hello world")
        controller._on_transcription_result(result)

        controller._floating_pill.show_preview_text.assert_called_once_with(
            "Hello world",
        )


class TestStopWithFlush:
    """Tests for stopping dictation with buffered audio."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_stop_flushes_buffer(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        mock_engine = MagicMock()
        controller._engine_manager.active_engine = mock_engine

        # Go ACTIVE
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        # Buffer some audio (below threshold, non-silent)
        chunk = _make_audio_chunk(8000)
        controller._on_audio_chunk(chunk)
        assert controller._buffered_samples == 8000

        # Stop — should flush the buffer
        controller._on_dictation_toggle()
        assert controller._state_machine.state == DictationState.STOPPING
        controller._async_worker.schedule_transcribe.assert_called_once()
        assert controller._pending_transcriptions == 1

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_stop_finishes_after_flush_result(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        mock_engine = MagicMock()
        controller._engine_manager.active_engine = mock_engine

        # Go ACTIVE, buffer audio (non-silent), stop
        controller._on_dictation_toggle()
        controller._on_engine_ready()
        controller._on_audio_chunk(_make_audio_chunk(8000))
        controller._on_dictation_toggle()
        assert controller._state_machine.state == DictationState.STOPPING

        # Deliver the flush transcription result
        result = _make_transcription_result("final words")
        controller._on_transcription_result(result)

        # Should now be IDLE
        assert controller._state_machine.state == DictationState.IDLE


class TestSettingsHandlers:
    """Tests for settings change handlers."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_voice_commands_toggle(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)

        controller._on_setting_changed("voice_commands_enabled", False)
        assert controller._parser.enabled is False

        controller._on_setting_changed("voice_commands_enabled", True)
        assert controller._parser.enabled is True

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_api_key_stored_in_keychain(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)

        controller._on_api_key_changed("sk-new-key-123")

        mock_deps["secure_store"].set.assert_called_once_with(
            "api_key", "sk-new-key-123",
        )
        controller._engine_manager.update_cloud_config.assert_called()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_engine_changed_saves_settings(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)

        controller._on_engine_changed("local_whisper")

        assert controller._settings.engine == ConfigEngineType.LOCAL_WHISPER
        mock_deps["settings_store"].save.assert_called()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_preview_toggle(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        assert controller._settings.show_live_preview is False

        controller._on_preview_toggle()
        assert controller._settings.show_live_preview is True

        controller._on_preview_toggle()
        assert controller._settings.show_live_preview is False
        controller._floating_pill.hide_preview.assert_called()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_pill_position_saved(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)

        controller._on_pill_position_changed(100, 200)

        assert controller._settings.pill_position_x == 100
        assert controller._settings.pill_position_y == 200
        mock_deps["settings_store"].save.assert_called()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_hotkey_changed(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)

        from systemstt.platform.base import HotkeyBinding

        new_binding = HotkeyBinding(
            key="d", modifiers=frozenset({"command"}),
        )
        controller._on_hotkey_changed(new_binding)

        mock_deps["hotkey_manager"].update_binding.assert_called_once_with(
            new_binding,
        )
        assert controller._settings.hotkey_key == "d"
        assert "command" in controller._settings.hotkey_modifiers


class TestQuitAndShutdown:
    """Tests for quit handling."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_quit_requested_calls_app_quit(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)

        with patch.object(QApplication, "instance") as mock_instance:
            mock_app = MagicMock()
            mock_instance.return_value = mock_app
            controller._on_quit_requested()
            mock_app.exit.assert_called_once_with(0)


class TestBufferThreshold:
    """Tests for buffer threshold based on engine type."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_cloud_threshold(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Cloud engine uses 3s buffer threshold."""
        controller = AppController(**mock_deps)
        assert controller._settings.engine == ConfigEngineType.CLOUD_API
        assert controller._buffer_threshold == _CLOUD_BUFFER_SAMPLES

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_local_threshold(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Local engine uses 5s buffer threshold."""
        mock_deps["settings_store"].load.return_value = SettingsModel(
            engine=ConfigEngineType.LOCAL_WHISPER,
        )
        controller = AppController(**mock_deps)
        assert controller._buffer_threshold == _LOCAL_BUFFER_SAMPLES


class TestHallucinationFiltering:
    """Tests for hallucination filtering in transcription result handling."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_hallucination_text_not_injected(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Known hallucination patterns should not be injected as text."""
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        controller._on_dictation_toggle()
        controller._on_engine_ready()

        result = _make_transcription_result("Thank you for watching.")
        controller._on_transcription_result(result)

        controller._async_worker.schedule_inject_text.assert_not_called()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_trailing_artifact_stripped_before_injection(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Trailing hallucination artifacts should be stripped from injected text."""
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        controller._on_dictation_toggle()
        controller._on_engine_ready()

        result = _make_transcription_result("Meeting at 3pm. Thank you for watching.")
        controller._on_transcription_result(result)

        controller._async_worker.schedule_inject_text.assert_called_once_with(
            mock_deps["text_injector"], "Meeting at 3pm.",
        )

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_normal_text_passes_through(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Normal text should pass through the filter unchanged."""
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        controller._on_dictation_toggle()
        controller._on_engine_ready()

        result = _make_transcription_result("Send the email to John")
        controller._on_transcription_result(result)

        controller._async_worker.schedule_inject_text.assert_called_once_with(
            mock_deps["text_injector"], "Send the email to John",
        )


class TestContextPromptTracking:
    """Tests for context prompt tracking across transcription chunks."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_first_chunk_has_no_context(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """First transcription dispatch should have no context_prompt."""
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        mock_engine = MagicMock()
        controller._engine_manager.active_engine = mock_engine

        # Go ACTIVE
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        # Send enough non-silent data to cross threshold
        chunk = _make_audio_chunk(_CLOUD_BUFFER_SAMPLES + 1000)
        controller._on_audio_chunk(chunk)

        call_kwargs = controller._async_worker.schedule_transcribe.call_args
        assert call_kwargs[1]["context_prompt"] is None

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_second_chunk_receives_previous_text(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """After first result, second dispatch should include previous text as context."""
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        mock_engine = MagicMock()
        controller._engine_manager.active_engine = mock_engine

        # Go ACTIVE
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        # First chunk dispatched (non-silent)
        chunk = _make_audio_chunk(_CLOUD_BUFFER_SAMPLES + 1000)
        controller._on_audio_chunk(chunk)

        # Deliver first transcription result
        result = _make_transcription_result("Hello world")
        controller._on_transcription_result(result)

        # Second chunk dispatched
        controller._on_audio_chunk(chunk)

        # The second schedule_transcribe call should have context_prompt
        assert controller._async_worker.schedule_transcribe.call_count == 2
        second_call = controller._async_worker.schedule_transcribe.call_args
        assert second_call[1]["context_prompt"] == "Hello world"

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_context_resets_on_new_session(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Context should reset when a new dictation session starts."""
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        mock_engine = MagicMock()
        controller._engine_manager.active_engine = mock_engine

        # First session: go ACTIVE, get a result
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        result = _make_transcription_result("first session text")
        controller._pending_transcriptions = 1
        controller._on_transcription_result(result)
        assert controller._last_transcription_text == "first session text"

        # Stop and start new session
        controller._on_dictation_toggle()  # stop
        controller._on_dictation_toggle()  # start new session

        assert controller._last_transcription_text is None


class TestSilenceDetection:
    """Tests for cloud API silence detection."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_silent_chunk_skipped_for_cloud(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Silent audio should not be dispatched to the cloud API."""
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        mock_engine = MagicMock()
        controller._engine_manager.active_engine = mock_engine

        # Go ACTIVE (default engine is cloud_api)
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        # Send silent audio above threshold size
        silent_chunk = np.zeros(_CLOUD_BUFFER_SAMPLES + 1000, dtype=np.float32)
        controller._on_audio_chunk(silent_chunk)

        # Should NOT dispatch transcription for silent audio
        controller._async_worker.schedule_transcribe.assert_not_called()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_non_silent_chunk_dispatched_for_cloud(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Non-silent audio should be dispatched to the cloud API."""
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        mock_engine = MagicMock()
        controller._engine_manager.active_engine = mock_engine

        # Go ACTIVE
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        # Send a loud sine wave above threshold size
        num_samples = _CLOUD_BUFFER_SAMPLES + 1000
        t = np.linspace(0, num_samples / 16000, num_samples, endpoint=False, dtype=np.float32)
        loud_chunk = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        controller._on_audio_chunk(loud_chunk)

        controller._async_worker.schedule_transcribe.assert_called_once()

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_silent_chunk_not_skipped_for_local_whisper(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        """Local Whisper has built-in VAD, so silence should still be dispatched."""
        mock_deps["settings_store"].load.return_value = SettingsModel(
            engine=ConfigEngineType.LOCAL_WHISPER,
        )
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        mock_engine = MagicMock()
        controller._engine_manager.active_engine = mock_engine

        # Go ACTIVE
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        # Send silent audio above threshold size
        silent_chunk = np.zeros(_LOCAL_BUFFER_SAMPLES + 1000, dtype=np.float32)
        controller._on_audio_chunk(silent_chunk)

        # Local Whisper should still get the audio (VAD handles it internally)
        controller._async_worker.schedule_transcribe.assert_called_once()

    def test_is_silent_static_method(self) -> None:
        """Test the _is_silent static method directly."""
        assert AppController._is_silent(np.zeros(1000, dtype=np.float32)) is True

        loud = np.full(1000, 0.5, dtype=np.float32)
        assert AppController._is_silent(loud) is False

        empty = np.array([], dtype=np.float32)
        assert AppController._is_silent(empty) is True


class TestAutoRecovery:
    """Tests for auto-recovery from error state."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_auto_recovery_transitions_to_idle(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        # Go to ERROR
        controller._on_dictation_toggle()
        controller._on_engine_error("fail")
        assert controller._state_machine.state == DictationState.ERROR

        # Manually trigger recovery (in real app, QTimer does this)
        controller._auto_recover_from_error()
        assert controller._state_machine.state == DictationState.IDLE

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_auto_recovery_noop_when_not_in_error(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)

        # In IDLE, recovery should be a no-op
        controller._auto_recover_from_error()
        assert controller._state_machine.state == DictationState.IDLE


class TestCommandExecution:
    """Tests for command execution callbacks."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_command_confirmation_shown(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        # Enter ACTIVE state
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        controller._on_command_executed("Deleted last word")

        controller._floating_pill.show_command_confirmation.assert_called_once_with(
            "Deleted last word",
        )


class TestRecorderError:
    """Tests for recorder error handling."""

    @patch("systemstt.controller.MenuBarWidget")
    @patch("systemstt.controller.FloatingPill")
    @patch("systemstt.controller.AudioRecorder")
    @patch("systemstt.controller.EngineManager")
    def test_recorder_error_transitions_to_error_state(
        self,
        _mock_em: MagicMock,
        _mock_rec: MagicMock,
        _mock_pill: MagicMock,
        _mock_menu: MagicMock,
        mock_deps: dict[str, Any],
    ) -> None:
        controller = AppController(**mock_deps)
        controller._async_worker = MagicMock()
        controller._async_worker.schedule_activate_engine = MagicMock()

        # Go ACTIVE
        controller._on_dictation_toggle()
        controller._on_engine_ready()

        # Simulate recorder error
        controller._on_recorder_error_main("device disconnected")

        assert controller._state_machine.state == DictationState.ERROR
        controller._menu_bar.set_state_error.assert_called()
        controller._floating_pill.show_error.assert_called_with(
            "device disconnected",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wait_for(
    condition: Any,
    timeout_ms: int = 2000,
    interval_ms: int = 10,
) -> None:
    """Spin the Qt event loop until *condition()* is truthy or timeout."""
    app = QApplication.instance()
    assert app is not None
    elapsed = 0
    while not condition() and elapsed < timeout_ms:
        app.processEvents()
        import time

        time.sleep(interval_ms / 1000)
        elapsed += interval_ms
    if not condition():
        raise TimeoutError(f"Condition not met within {timeout_ms}ms")
