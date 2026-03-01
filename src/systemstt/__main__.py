"""
Entry point for SystemSTT.

Responsibilities:
1. Parse CLI arguments (--version, --log-level)
2. Configure structured logging (file + stderr + crash log)
3. Install crash handler for unhandled exceptions
4. Install signal handlers for graceful shutdown (SIGINT, SIGTERM)
5. Initialize the Qt application
6. Create the platform factory (detect macOS/Windows)
7. Load configuration
8. Create and start the App Core (orchestrator)
9. Enter the Qt event loop
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from systemstt import __version__
from systemstt.logging_config import configure_logging, install_crash_handler
from systemstt.shutdown import ShutdownManager


def main() -> None:
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        prog="systemstt",
        description="System-wide speech-to-text for macOS",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("SYSTEMSTT_LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)",
    )
    args = parser.parse_args()

    # 1. Configure structured logging (file, stderr, crash log)
    configure_logging(args.log_level)

    # 2. Install crash handler for unhandled exceptions
    install_crash_handler()

    logger = logging.getLogger("systemstt")
    logger.info("SystemSTT v%s starting", __version__)
    logger.info("Python %s on %s", sys.version, sys.platform)

    # 3. Set up graceful shutdown manager
    shutdown_manager = ShutdownManager()
    shutdown_manager.install_signal_handlers()

    # Register log flushing as the last shutdown task
    shutdown_manager.register(
        lambda: None,  # _flush_logs is called automatically by shutdown()
        priority=99,
        name="final-log-flush",
    )

    # 4. Create Qt application (must exist before any QWidget)
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running with only tray icon
    app.setApplicationName("SystemSTT")

    # 5. Apply global theme stylesheet
    from systemstt.ui.theme import generate_qss

    app.setStyleSheet(generate_qss())

    # 6. Create stores
    from systemstt.config.store import SettingsStore
    from systemstt.platform.macos.keychain import MacOSKeychainStore

    settings_store = SettingsStore()
    secure_store = MacOSKeychainStore()

    # 7. Create platform services
    from systemstt.platform.macos.hotkey_manager import MacOSHotkeyManager
    from systemstt.platform.macos.text_injector import MacOSTextInjector

    hotkey_manager = MacOSHotkeyManager()
    text_injector = MacOSTextInjector()

    # 8. Create and start the app controller (orchestrator)
    from systemstt.controller import AppController

    controller = AppController(
        settings_store=settings_store,
        secure_store=secure_store,
        shutdown_manager=shutdown_manager,
        hotkey_manager=hotkey_manager,
        text_injector=text_injector,
    )
    controller.start()

    # 9. Connect graceful shutdown to Qt's aboutToQuit signal
    app.aboutToQuit.connect(shutdown_manager.shutdown)

    logger.info("SystemSTT v%s ready — entering event loop", __version__)

    # 10. Enter the Qt event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
