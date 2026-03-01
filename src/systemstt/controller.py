"""
AppController — central orchestrator for SystemSTT.

Contains three classes:

- AsyncWorker: Background QThread running a dedicated asyncio event loop.
  Provides schedule() to submit async work from the main thread.
  Emits Qt signals with results back to the main thread.

- AudioBridge: Minimal QObject that marshals audio data from PortAudio's
  callback thread to Qt's main thread via a queued Signal.

- AppController: Wires all components together and drives the dictation
  lifecycle through the DictationStateMachine.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from typing import Any, Optional

import numpy as np
from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication

from systemstt.app import DictationState, DictationStateMachine, StateTransition
from systemstt.audio.level_meter import LevelMeter
from systemstt.audio.recorder import AudioConfig, AudioRecorder
from systemstt.commands.executor import CommandExecutor
from systemstt.commands.parser import CommandParser
from systemstt.commands.registry import CommandAction, CommandRegistry
from systemstt.config.models import EngineType as ConfigEngineType, SettingsModel
from systemstt.config.secure import SecureStore
from systemstt.config.store import SettingsStore
from systemstt.platform.base import HotkeyBinding, HotkeyManager, TextInjector
from systemstt.shutdown import ShutdownManager
from systemstt.stt.base import (
    DetectedLanguage,
    EngineType as STTEngineType,
    STTEngine,
    TranscriptionResult,
)
from systemstt.stt.cloud_api import CloudAPIConfig
from systemstt.stt.engine_manager import EngineManager
from systemstt.stt.local_whisper import (
    LocalWhisperConfig,
    WhisperModelSize as STTWhisperModelSize,
)
from systemstt.ui.floating_pill import FloatingPill
from systemstt.ui.menu_bar import MenuBarWidget

logger = logging.getLogger(__name__)

# Audio buffer thresholds (samples at 16 kHz)
_CLOUD_BUFFER_SAMPLES = 16_000 * 3  # 3 seconds
_LOCAL_BUFFER_SAMPLES = 16_000 * 5  # 5 seconds

# Keychain key for the cloud API key
_API_KEY_NAME = "api_key"


# ---------------------------------------------------------------------------
# AsyncWorker
# ---------------------------------------------------------------------------


class AsyncWorker(QThread):
    """Background thread running a dedicated asyncio event loop.

    Provides ``schedule()`` to submit coroutines from the main thread,
    plus convenience methods that wrap common async operations and emit
    Qt signals with results back to the main thread.
    """

    engine_ready = Signal()
    engine_error = Signal(str)
    transcription_result = Signal(object)  # TranscriptionResult
    transcription_error = Signal(str)
    command_executed = Signal(str)  # confirmation text
    task_error = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._started_event = threading.Event()

    # -- QThread entry point --------------------------------------------------

    def run(self) -> None:  # noqa: D401
        """Thread entry point: creates and runs the asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._started_event.set()

        try:
            self._loop.run_forever()
        finally:
            # Cancel outstanding tasks
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()
            self._loop = None

    # -- Public API -----------------------------------------------------------

    @property
    def loop_running(self) -> bool:
        """Return True if the asyncio loop is running."""
        return self._loop is not None and self._loop.is_running()

    def wait_until_running(self, timeout: float = 5.0) -> None:
        """Block until the event loop is ready (call from main thread)."""
        self._started_event.wait(timeout)

    def schedule(
        self, coro: Any,
    ) -> Optional[concurrent.futures.Future[Any]]:
        """Submit a coroutine to the asyncio loop.

        Returns a ``concurrent.futures.Future`` that can be used to wait for
        the result, or ``None`` if the loop is not running.
        """
        if self._loop is not None and self._loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, self._loop)
        return None

    def stop_loop(self) -> None:
        """Stop the event loop and wait for the thread to finish."""
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self.isRunning():
            self.wait(5000)

    # -- Convenience schedulers -----------------------------------------------

    def schedule_activate_engine(
        self,
        engine_manager: EngineManager,
        engine_type: STTEngineType,
    ) -> None:
        """Activate an STT engine asynchronously."""

        async def _activate() -> None:
            try:
                await engine_manager.activate_engine(engine_type)
                self.engine_ready.emit()
            except Exception as exc:
                self.engine_error.emit(str(exc))

        self.schedule(_activate())

    def schedule_transcribe(
        self,
        engine: STTEngine,
        audio: np.ndarray,
        language_hint: Optional[DetectedLanguage] = None,
    ) -> None:
        """Transcribe audio asynchronously."""

        async def _transcribe() -> None:
            try:
                result = await engine.transcribe(audio, language_hint=language_hint)
                self.transcription_result.emit(result)
            except Exception as exc:
                self.transcription_error.emit(str(exc))

        self.schedule(_transcribe())

    def schedule_execute_command(
        self,
        executor: CommandExecutor,
        action: CommandAction,
        confirmation_text: str,
    ) -> None:
        """Execute a voice command asynchronously."""

        async def _execute() -> None:
            try:
                await executor.execute(action)
                self.command_executed.emit(confirmation_text)
            except Exception as exc:
                self.task_error.emit(str(exc))

        self.schedule(_execute())

    def schedule_inject_text(
        self,
        injector: TextInjector,
        text: str,
    ) -> None:
        """Inject text into the focused application asynchronously."""

        async def _inject() -> None:
            try:
                await injector.inject_text(text)
            except Exception as exc:
                self.task_error.emit(str(exc))

        self.schedule(_inject())


# ---------------------------------------------------------------------------
# AudioBridge
# ---------------------------------------------------------------------------


class AudioBridge(QObject):
    """Marshals audio callbacks from PortAudio's thread to Qt's main thread.

    Assign ``on_chunk`` as the ``AudioRecorder.on_audio_chunk`` callback.
    The ``chunk_received`` signal is automatically queued across threads.
    """

    chunk_received = Signal(object)  # np.ndarray
    error_received = Signal(str)

    def on_chunk(self, chunk: np.ndarray) -> None:
        """Callback for ``AudioRecorder.on_audio_chunk`` (thread-safe)."""
        self.chunk_received.emit(chunk)

    def on_error(self, error: Exception) -> None:
        """Callback for ``AudioRecorder.on_error`` (thread-safe)."""
        self.error_received.emit(str(error))


# ---------------------------------------------------------------------------
# AppController
# ---------------------------------------------------------------------------


class AppController(QObject):
    """Central orchestrator that wires all components together.

    Responsibilities:
    - Creates audio, STT, command, and UI components
    - Connects all Qt signals / slots
    - Drives the DictationStateMachine through IDLE → STARTING → ACTIVE
      → STOPPING → IDLE
    - Buffers audio chunks and dispatches transcription at threshold
    - Processes transcription results: parse → inject text / execute command
    - Handles settings changes from the SettingsWindow
    - Registers shutdown tasks with priority ordering
    """

    # Private signal for marshalling the hotkey callback to the main thread
    _hotkey_activated = Signal()

    def __init__(
        self,
        settings_store: SettingsStore,
        secure_store: SecureStore,
        shutdown_manager: ShutdownManager,
        hotkey_manager: HotkeyManager,
        text_injector: TextInjector,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)

        # External dependencies
        self._settings_store = settings_store
        self._secure_store = secure_store
        self._shutdown_manager = shutdown_manager

        # Load persisted settings
        self._settings: SettingsModel = settings_store.load()

        # -- Core state -------------------------------------------------------
        self._state_machine = DictationStateMachine()
        self._audio_buffer: list[np.ndarray] = []
        self._buffered_samples: int = 0
        self._pending_transcriptions: int = 0
        self._elapsed_seconds: int = 0
        self._current_language: str = "EN"

        # -- Async worker -----------------------------------------------------
        self._async_worker = AsyncWorker(self)

        # -- Audio -------------------------------------------------------------
        self._audio_bridge = AudioBridge(self)
        self._level_meter = LevelMeter()
        self._recorder = AudioRecorder(self._build_audio_config())

        # -- STT ---------------------------------------------------------------
        self._engine_manager = EngineManager(
            local_config=self._build_local_config(),
            cloud_config=self._build_cloud_config(),
        )

        # -- Commands ----------------------------------------------------------
        self._registry = CommandRegistry()
        self._parser = CommandParser(self._registry)
        self._parser.enabled = self._settings.voice_commands_enabled

        # -- Platform services -------------------------------------------------
        self._hotkey_manager = hotkey_manager
        self._text_injector = text_injector
        self._executor = CommandExecutor(
            text_injector=text_injector,
            stop_dictation_callback=self._stop_dictation,
        )

        # -- UI ----------------------------------------------------------------
        self._menu_bar = MenuBarWidget()
        self._floating_pill = FloatingPill()
        self._settings_window: Optional[Any] = None  # lazy-created

        # -- Timers ------------------------------------------------------------
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._on_elapsed_tick)

        # -- Wiring ------------------------------------------------------------
        self._connect_signals()
        self._register_shutdown_tasks()

    # =====================================================================
    # Setup helpers
    # =====================================================================

    def _connect_signals(self) -> None:
        """Wire all Qt signals to their slots."""
        # Hotkey (thread-safe bridge)
        self._hotkey_activated.connect(self._on_dictation_toggle)

        # Menu bar actions
        self._menu_bar.dictation_toggle_requested.connect(self._on_dictation_toggle)
        self._menu_bar.settings_requested.connect(self._on_settings_requested)
        self._menu_bar.quit_requested.connect(self._on_quit_requested)
        self._menu_bar.preview_toggle_requested.connect(self._on_preview_toggle)

        # Audio bridge
        self._audio_bridge.chunk_received.connect(self._on_audio_chunk)
        self._audio_bridge.error_received.connect(self._on_recorder_error_main)

        # Async worker results
        self._async_worker.engine_ready.connect(self._on_engine_ready)
        self._async_worker.engine_error.connect(self._on_engine_error)
        self._async_worker.transcription_result.connect(self._on_transcription_result)
        self._async_worker.transcription_error.connect(self._on_transcription_error)
        self._async_worker.command_executed.connect(self._on_command_executed)
        self._async_worker.task_error.connect(self._on_task_error)

        # Floating pill
        self._floating_pill.position_changed.connect(self._on_pill_position_changed)

        # State machine
        self._state_machine.on_state_changed = self._on_state_changed

    def _register_shutdown_tasks(self) -> None:
        """Register cleanup callbacks with the ShutdownManager."""
        self._shutdown_manager.register(
            self._recorder.stop, priority=10, name="stop-audio",
        )
        self._shutdown_manager.register(
            self._shutdown_engine_sync, priority=20, name="shutdown-stt",
        )
        self._shutdown_manager.register(
            self._hotkey_manager.unregister, priority=30, name="unregister-hotkey",
        )
        self._shutdown_manager.register(
            self._save_settings, priority=50, name="save-settings",
        )
        self._shutdown_manager.register(
            self._async_worker.stop_loop, priority=80, name="stop-async-worker",
        )

    # =====================================================================
    # Config builders
    # =====================================================================

    def _build_audio_config(self) -> AudioConfig:
        return AudioConfig(device_id=self._settings.audio_device_id)

    def _build_hotkey_binding(self) -> HotkeyBinding:
        return HotkeyBinding(
            key=self._settings.hotkey_key,
            modifiers=frozenset(self._settings.hotkey_modifiers),
        )

    def _build_cloud_config(self) -> CloudAPIConfig:
        api_key = self._secure_store.get(_API_KEY_NAME) or ""
        return CloudAPIConfig(
            api_key=api_key,
            api_base_url=self._settings.cloud_api_base_url,
            model=self._settings.cloud_api_model,
        )

    def _build_local_config(self) -> LocalWhisperConfig:
        return LocalWhisperConfig(
            model_size=STTWhisperModelSize(self._settings.local_model_size.value),
            compute_type=self._settings.local_compute_type,
        )

    # =====================================================================
    # Lifecycle
    # =====================================================================

    def start(self) -> None:
        """Start the controller: async worker, hotkey, menu bar."""
        self._async_worker.start()
        self._async_worker.wait_until_running()

        # Check accessibility permission — required for text injection and hotkeys
        if not self._text_injector.has_accessibility_permission():
            logger.warning(
                "Accessibility permission not granted. "
                "Text injection and global hotkey will not work. "
                "Grant permission in System Settings > Privacy & Security > Accessibility."
            )
            self._text_injector.request_accessibility_permission()

        # Register global hotkey
        binding = self._build_hotkey_binding()
        try:
            self._hotkey_manager.register(binding, self._on_hotkey_pressed)
        except Exception as exc:
            logger.error("Failed to register hotkey: %s", exc)

        # Restore pill position
        if self._settings.pill_position_x is not None:
            self._floating_pill.set_position(
                self._settings.pill_position_x,
                self._settings.pill_position_y or 48,
            )

        # Show the menu bar icon
        self._menu_bar.show()

        logger.info("AppController started")

    # =====================================================================
    # Properties
    # =====================================================================

    @property
    def _buffer_threshold(self) -> int:
        """Audio buffer size (samples) before dispatching transcription."""
        if self._settings.engine == ConfigEngineType.CLOUD_API:
            return _CLOUD_BUFFER_SAMPLES
        return _LOCAL_BUFFER_SAMPLES

    # =====================================================================
    # Hotkey (called from the hotkey manager's thread)
    # =====================================================================

    def _on_hotkey_pressed(self) -> None:
        """Called from the hotkey thread. Marshals to main thread via signal."""
        self._hotkey_activated.emit()

    # =====================================================================
    # Dictation lifecycle
    # =====================================================================

    def _on_dictation_toggle(self) -> None:
        """Handle dictation toggle from hotkey or menu bar."""
        state = self._state_machine.state
        if state == DictationState.IDLE:
            self._start_dictation()
        elif state == DictationState.ACTIVE:
            self._stop_dictation()
        elif state == DictationState.ERROR:
            # Dismiss error and return to idle
            self._state_machine.transition_to(
                DictationState.IDLE, "user_dismiss",
            )
            self._menu_bar.set_state_idle(self._current_language)
            self._floating_pill.hide_pill()
        # STARTING / STOPPING: ignore (operation in progress)

    def _start_dictation(self) -> None:
        """Begin dictation: transition to STARTING, activate STT engine."""
        # Warn if accessibility permission is missing — text injection won't work
        if not self._text_injector.has_accessibility_permission():
            logger.warning("Dictation started without accessibility permission")
            self._floating_pill.show_error(
                "Accessibility permission required. Check System Settings.",
                is_warning=True,
            )

        self._state_machine.transition_to(DictationState.STARTING, "user_toggle")

        # Reset buffers
        self._audio_buffer.clear()
        self._buffered_samples = 0
        self._pending_transcriptions = 0
        self._elapsed_seconds = 0

        # Convert config EngineType → STT EngineType
        stt_engine_type = STTEngineType(self._settings.engine.value)
        self._async_worker.schedule_activate_engine(
            self._engine_manager, stt_engine_type,
        )

    def _stop_dictation(self) -> None:
        """Stop dictation: flush buffer, transition to STOPPING → IDLE."""
        state = self._state_machine.state
        if state in (DictationState.STOPPING, DictationState.IDLE):
            return

        if state == DictationState.STARTING:
            # Cannot go STARTING → STOPPING; use ERROR as intermediary
            self._state_machine.transition_to(
                DictationState.ERROR, "cancel_start",
            )
            self._state_machine.transition_to(
                DictationState.IDLE, "error_recovery",
            )
            self._menu_bar.set_state_idle(self._current_language)
            self._floating_pill.hide_pill()
            return

        # ACTIVE → STOPPING
        self._state_machine.transition_to(DictationState.STOPPING, "user_toggle")
        self._elapsed_timer.stop()
        self._recorder.stop()

        # Flush remaining audio buffer
        if self._audio_buffer:
            self._dispatch_transcription()

        # If no pending transcriptions, finish immediately
        if self._pending_transcriptions == 0:
            self._finish_stop()

    def _finish_stop(self) -> None:
        """Complete the stop sequence: transition STOPPING → IDLE, update UI."""
        if self._state_machine.state != DictationState.STOPPING:
            return
        self._state_machine.transition_to(DictationState.IDLE, "stop_complete")
        self._menu_bar.set_state_idle(self._current_language)
        self._floating_pill.hide_pill()
        self._audio_buffer.clear()
        self._buffered_samples = 0

    # =====================================================================
    # Engine callbacks (from AsyncWorker signals)
    # =====================================================================

    def _on_engine_ready(self) -> None:
        """Engine activation succeeded — start recording."""
        if self._state_machine.state != DictationState.STARTING:
            return

        # Hook up audio bridge
        self._recorder.on_audio_chunk = self._audio_bridge.on_chunk
        self._recorder.on_error = self._audio_bridge.on_error

        try:
            self._recorder.start()
        except Exception as exc:
            logger.error("Failed to start audio recorder: %s", exc)
            self._state_machine.transition_to(
                DictationState.ERROR, "recorder_start_failed", error=exc,
            )
            self._menu_bar.set_state_error(self._current_language)
            self._floating_pill.show_error(str(exc))
            QTimer.singleShot(5000, self._auto_recover_from_error)
            return

        self._state_machine.transition_to(DictationState.ACTIVE, "engine_ready")

        # Update UI
        engine_label = (
            "Cloud"
            if self._settings.engine == ConfigEngineType.CLOUD_API
            else "Local"
        )
        self._menu_bar.set_state_active(self._current_language)
        if self._settings.show_status_pill:
            self._floating_pill.show_active(self._current_language, engine_label)

        # Start elapsed timer
        self._elapsed_timer.start()

    def _on_engine_error(self, error_message: str) -> None:
        """Engine activation failed."""
        if self._state_machine.state != DictationState.STARTING:
            return

        logger.error("Engine activation failed: %s", error_message)
        self._state_machine.transition_to(
            DictationState.ERROR,
            "engine_error",
            error=Exception(error_message),
        )
        self._menu_bar.set_state_error(self._current_language)
        self._floating_pill.show_error(error_message)
        QTimer.singleShot(5000, self._auto_recover_from_error)

    def _auto_recover_from_error(self) -> None:
        """Auto-recover from ERROR → IDLE after a timeout."""
        if self._state_machine.state == DictationState.ERROR:
            self._state_machine.transition_to(DictationState.IDLE, "auto_recovery")
            self._menu_bar.set_state_idle(self._current_language)
            self._floating_pill.hide_pill()

    # =====================================================================
    # Audio handling
    # =====================================================================

    def _on_audio_chunk(self, chunk: object) -> None:
        """Handle audio chunk from AudioBridge (main thread)."""
        if not isinstance(chunk, np.ndarray):
            return
        if self._state_machine.state != DictationState.ACTIVE:
            return

        # Compute level for settings window meter
        level_reading = self._level_meter.compute(chunk)
        if self._settings_window is not None:
            from systemstt.ui.settings_window import SettingsWindow

            if isinstance(self._settings_window, SettingsWindow):
                if self._settings_window.isVisible():
                    self._settings_window.update_audio_level(level_reading)

        # Buffer the chunk
        self._audio_buffer.append(chunk)
        self._buffered_samples += len(chunk)

        # Dispatch transcription when threshold reached
        if self._buffered_samples >= self._buffer_threshold:
            self._dispatch_transcription()

    def _dispatch_transcription(self) -> None:
        """Concatenate buffered audio and dispatch for transcription."""
        if not self._audio_buffer:
            return

        # Local Whisper is not safe for concurrent transcriptions (state
        # machine goes READY→TRANSCRIBING).  Keep buffering until the
        # in-flight transcription finishes; the next audio chunk or the
        # stop-flush will pick up the accumulated audio.
        if (
            self._settings.engine == ConfigEngineType.LOCAL_WHISPER
            and self._pending_transcriptions > 0
        ):
            return

        audio = np.concatenate(self._audio_buffer)
        self._audio_buffer.clear()
        self._buffered_samples = 0

        engine = self._engine_manager.active_engine
        if engine is None:
            logger.warning("No active engine for transcription")
            return

        self._pending_transcriptions += 1
        self._async_worker.schedule_transcribe(engine, audio)

    # =====================================================================
    # Transcription result handling
    # =====================================================================

    def _on_transcription_result(self, result: object) -> None:
        """Handle transcription result from AsyncWorker."""
        self._pending_transcriptions = max(0, self._pending_transcriptions - 1)

        if not isinstance(result, TranscriptionResult):
            self._maybe_finish_stop()
            return

        text = result.full_text.strip()
        if not text:
            self._maybe_finish_stop()
            return

        # Update detected language
        if result.primary_language == DetectedLanguage.HEBREW:
            self._current_language = "HE"
        elif result.primary_language == DetectedLanguage.ENGLISH:
            self._current_language = "EN"
        self._menu_bar.update_language(self._current_language)
        self._floating_pill.update_language(self._current_language)

        # Show live preview
        if self._settings.show_live_preview:
            self._floating_pill.show_preview_text(text)

        # Parse for voice commands
        parse_result = self._parser.parse(text)

        if parse_result.has_command and parse_result.command is not None:
            # Inject any text before the command
            if parse_result.text_before:
                self._async_worker.schedule_inject_text(
                    self._text_injector, parse_result.text_before,
                )
            # Execute the command
            self._async_worker.schedule_execute_command(
                self._executor,
                parse_result.command.action,
                parse_result.command.confirmation_text,
            )
        else:
            # Plain text — inject it
            self._async_worker.schedule_inject_text(self._text_injector, text)

        self._maybe_finish_stop()

    def _on_transcription_error(self, error_message: str) -> None:
        """Handle transcription failure."""
        self._pending_transcriptions = max(0, self._pending_transcriptions - 1)
        logger.error("Transcription error: %s", error_message)

        if self._state_machine.state == DictationState.ACTIVE:
            self._floating_pill.show_error(
                f"Transcription failed: {error_message}", is_warning=True,
            )

        self._maybe_finish_stop()

    def _maybe_finish_stop(self) -> None:
        """Finish the stop sequence if we're STOPPING and nothing is pending."""
        if (
            self._state_machine.state == DictationState.STOPPING
            and self._pending_transcriptions == 0
        ):
            self._finish_stop()

    # =====================================================================
    # Command execution callback
    # =====================================================================

    def _on_command_executed(self, confirmation_text: str) -> None:
        """Show command confirmation on the floating pill."""
        if self._state_machine.state in (
            DictationState.ACTIVE,
            DictationState.STOPPING,
        ):
            self._floating_pill.show_command_confirmation(confirmation_text)

    # =====================================================================
    # Error callbacks
    # =====================================================================

    def _on_task_error(self, error_message: str) -> None:
        """Handle a general async task error."""
        logger.error("Async task error: %s", error_message)
        if self._state_machine.state == DictationState.ACTIVE:
            self._floating_pill.show_error(error_message, is_warning=True)

    def _on_recorder_error_main(self, error_message: str) -> None:
        """Handle audio recorder error (marshalled to main thread)."""
        logger.error("Audio recorder error: %s", error_message)
        if self._state_machine.state == DictationState.ACTIVE:
            self._elapsed_timer.stop()
            self._state_machine.transition_to(
                DictationState.ERROR,
                "recorder_error",
                error=Exception(error_message),
            )
            self._menu_bar.set_state_error(self._current_language)
            self._floating_pill.show_error(error_message)
            QTimer.singleShot(5000, self._auto_recover_from_error)

    # =====================================================================
    # Elapsed timer
    # =====================================================================

    def _on_elapsed_tick(self) -> None:
        """Update the floating pill elapsed time every second."""
        self._elapsed_seconds += 1
        self._floating_pill.update_elapsed_time(self._elapsed_seconds)

    # =====================================================================
    # State machine callback
    # =====================================================================

    def _on_state_changed(self, transition: StateTransition) -> None:
        """Log state transitions."""
        logger.debug(
            "Dictation: %s -> %s (trigger=%s)",
            transition.from_state.name,
            transition.to_state.name,
            transition.trigger,
        )

    # =====================================================================
    # UI handlers
    # =====================================================================

    def _on_settings_requested(self) -> None:
        """Show the settings window (lazy-created)."""
        from systemstt.ui.settings_window import SettingsWindow

        if self._settings_window is None:
            self._settings_window = SettingsWindow(self._settings)
            assert isinstance(self._settings_window, SettingsWindow)
            self._settings_window.settings_changed.connect(
                self._on_setting_changed,
            )
            self._settings_window.hotkey_changed.connect(
                self._on_hotkey_changed,
            )
            self._settings_window.engine_changed.connect(
                self._on_engine_changed,
            )
            self._settings_window.api_key_changed.connect(
                self._on_api_key_changed,
            )
            self._settings_window.model_download_requested.connect(
                self._on_model_download_requested,
            )
        else:
            assert isinstance(self._settings_window, SettingsWindow)
            self._settings_window.update_from_settings(self._settings)

        self._settings_window.show()
        self._settings_window.raise_()

    def _on_quit_requested(self) -> None:
        """Quit the application.

        Runs shutdown tasks directly rather than relying on ``aboutToQuit``,
        which may not fire reliably when ``setQuitOnLastWindowClosed(False)``
        is set and background QThreads are active.
        """
        self._shutdown_manager.shutdown()
        app = QApplication.instance()
        if app is not None:
            app.exit(0)

    def _on_preview_toggle(self) -> None:
        """Toggle the live-preview setting."""
        new_value = not self._settings.show_live_preview
        self._settings = self._settings.model_copy(
            update={"show_live_preview": new_value},
        )
        self._settings_store.save(self._settings)
        if not new_value:
            self._floating_pill.hide_preview()

    def _on_pill_position_changed(self, x: int, y: int) -> None:
        """Persist the new pill position."""
        self._settings = self._settings.model_copy(
            update={"pill_position_x": x, "pill_position_y": y},
        )
        self._settings_store.save(self._settings)

    # =====================================================================
    # Settings handlers
    # =====================================================================

    def _on_setting_changed(self, key: str, value: object) -> None:
        """Apply a single setting change from the SettingsWindow."""
        try:
            self._settings = self._settings.model_copy(update={key: value})
            self._settings_store.save(self._settings)
        except Exception as exc:
            logger.warning("Failed to update setting %s: %s", key, exc)
            return

        # Side-effects
        if key == "voice_commands_enabled":
            self._parser.enabled = bool(value)
        elif key in ("audio_device_id", "audio_device_name"):
            self._recorder.update_config(self._build_audio_config())
        elif key == "show_status_pill":
            if (
                not bool(value)
                and self._state_machine.state == DictationState.ACTIVE
            ):
                self._floating_pill.hide_pill()
        elif key == "show_live_preview":
            if not bool(value):
                self._floating_pill.hide_preview()
        elif key in ("cloud_api_base_url", "cloud_api_model"):
            self._engine_manager.update_cloud_config(self._build_cloud_config())
        elif key in ("local_model_size", "local_compute_type"):
            self._engine_manager.update_local_config(self._build_local_config())

    def _on_hotkey_changed(self, binding: object) -> None:
        """Apply a hotkey change from the SettingsWindow."""
        if not isinstance(binding, HotkeyBinding):
            return
        try:
            self._hotkey_manager.update_binding(binding)
        except Exception as exc:
            logger.error("Failed to update hotkey: %s", exc)
            return

        self._settings = self._settings.model_copy(
            update={
                "hotkey_key": binding.key,
                "hotkey_modifiers": list(binding.modifiers),
            },
        )
        self._settings_store.save(self._settings)

    def _on_engine_changed(self, engine_name: str) -> None:
        """Apply an engine type change from the SettingsWindow."""
        try:
            ConfigEngineType(engine_name)
        except ValueError:
            logger.warning("Unknown engine type: %s", engine_name)
            return

        self._settings = self._settings.model_copy(
            update={"engine": engine_name},
        )
        self._settings_store.save(self._settings)
        # Engine will be activated on next dictation start

    def _on_api_key_changed(self, api_key: str) -> None:
        """Store the API key in the keychain and update engine config."""
        self._secure_store.set(_API_KEY_NAME, api_key)
        self._engine_manager.update_cloud_config(self._build_cloud_config())

    def _on_model_download_requested(self, model_name: str) -> None:
        """Download a Whisper model asynchronously."""

        async def _download() -> None:
            from systemstt.stt.local_whisper import LocalWhisperEngine

            config = LocalWhisperConfig(
                model_size=STTWhisperModelSize(model_name),
            )
            engine = LocalWhisperEngine(config)
            try:
                await engine.download_model()
            except Exception as exc:
                self.task_error.emit(str(exc))  # type: ignore[attr-defined]
                logger.error("Model download failed: %s", exc)

        self._async_worker.schedule(_download())

    # =====================================================================
    # Shutdown helpers
    # =====================================================================

    def _shutdown_engine_sync(self) -> None:
        """Synchronously shut down the STT engine via the async worker."""
        if not self._async_worker.loop_running:
            return
        future = self._async_worker.schedule(self._engine_manager.shutdown())
        if future is not None:
            try:
                future.result(timeout=5.0)
            except Exception as exc:
                logger.warning("Engine shutdown error: %s", exc)

    def _save_settings(self) -> None:
        """Save current settings to disk."""
        try:
            self._settings_store.save(self._settings)
        except Exception as exc:
            logger.warning("Failed to save settings on shutdown: %s", exc)
