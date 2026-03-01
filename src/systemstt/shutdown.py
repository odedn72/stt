"""
Graceful shutdown handling for SystemSTT.

Manages orderly teardown of application resources when the user quits,
the system sends SIGTERM, or an unrecoverable error occurs.

Shutdown order (inverse of startup):
1. Stop dictation if active (flush audio buffer, final transcription)
2. Unregister global hotkey
3. Stop audio capture
4. Release STT engine resources (unload model, close HTTP connections)
5. Save settings to disk
6. Close UI (Qt event loop exit)
7. Flush and close log handlers

Usage:
    from systemstt.shutdown import ShutdownManager

    manager = ShutdownManager()
    manager.register(cleanup_audio, priority=10)
    manager.register(cleanup_engine, priority=20)
    manager.register(save_settings, priority=30)

    # On shutdown:
    manager.shutdown()
"""

from __future__ import annotations

import contextlib
import logging
import signal
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass(order=True)
class _ShutdownTask:
    """A cleanup task to run during shutdown.

    Lower priority numbers run first.
    """

    priority: int
    name: str = field(compare=False)
    callback: Callable[[], None] = field(compare=False)


class ShutdownManager:
    """Manages orderly application shutdown.

    Components register cleanup callbacks with a priority. When shutdown()
    is called, callbacks execute in priority order (lowest first). Each
    callback is wrapped in a try/except so a failure in one does not
    prevent others from running.

    Priority guidelines:
        10 - Stop active dictation (audio flush)
        20 - Unregister hotkey
        30 - Stop audio capture
        40 - Release STT engine
        50 - Save settings
        60 - Close UI
        90 - Flush log handlers
    """

    def __init__(self) -> None:
        self._tasks: list[_ShutdownTask] = []
        self._shutting_down: bool = False
        self._signals_installed: bool = False

    @property
    def is_shutting_down(self) -> bool:
        """Whether shutdown is currently in progress."""
        return self._shutting_down

    def register(
        self,
        callback: Callable[[], None],
        priority: int = 50,
        name: str | None = None,
    ) -> None:
        """Register a cleanup callback to run during shutdown.

        Args:
            callback: Function to call during shutdown. Must not raise.
            priority: Execution order (lower = earlier). Default 50.
            name: Human-readable name for logging. Defaults to callback name.
        """
        fallback = str(getattr(callback, "__name__", repr(callback)))
        task_name: str = name if name is not None else fallback
        self._tasks.append(
            _ShutdownTask(
                priority=priority,
                name=task_name,
                callback=callback,
            )
        )
        logger.debug("Registered shutdown task: %s (priority %d)", task_name, priority)

    def install_signal_handlers(self) -> None:
        """Install SIGINT and SIGTERM handlers that trigger graceful shutdown.

        If a QApplication instance is running, the handler calls
        ``QApplication.quit()`` so the Qt event loop shuts down cleanly
        (which fires ``aboutToQuit`` and lets Qt run its own cleanup).
        Otherwise it falls back to ``sys.exit(0)``.

        Safe to call multiple times; only installs once.
        """
        if self._signals_installed:
            return

        def _signal_handler(signum: int, _frame: object) -> None:
            sig_name = signal.Signals(signum).name
            logger.info("Received %s — initiating graceful shutdown", sig_name)
            self.shutdown()

            # Prefer QApplication.quit() when a Qt event loop is running so
            # that aboutToQuit is emitted and Qt cleans up properly.
            try:
                from PySide6.QtWidgets import QApplication  # noqa: PLC0415

                app = QApplication.instance()
                if app is not None:
                    app.quit()
                    return
            except ImportError:
                pass

            sys.exit(0)

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
        self._signals_installed = True
        logger.debug("Signal handlers installed (SIGINT, SIGTERM)")

    def shutdown(self) -> None:
        """Execute all registered shutdown tasks in priority order.

        Each task runs inside a try/except so that a failure in one task
        does not prevent subsequent tasks from executing. This method is
        idempotent: calling it multiple times has no additional effect.
        """
        if self._shutting_down:
            logger.debug("Shutdown already in progress, skipping")
            return

        self._shutting_down = True
        logger.info("Graceful shutdown initiated (%d tasks registered)", len(self._tasks))

        # Sort by priority (lowest first)
        sorted_tasks = sorted(self._tasks)

        for task in sorted_tasks:
            try:
                logger.debug("Running shutdown task: %s (priority %d)", task.name, task.priority)
                task.callback()
                logger.debug("Shutdown task completed: %s", task.name)
            except Exception:
                logger.exception("Shutdown task failed: %s", task.name)

        logger.info("Graceful shutdown complete")

        # Flush all log handlers as the very last step
        self._flush_logs()

    @staticmethod
    def _flush_logs() -> None:
        """Flush and close all handlers on the systemstt logger."""
        root_logger = logging.getLogger("systemstt")
        for handler in root_logger.handlers:
            with contextlib.suppress(Exception):
                handler.flush()
