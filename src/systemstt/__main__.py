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

    logger.info("SystemSTT v%s ready", __version__)

    # The actual Qt application setup will be added in later phases.
    # When the Qt app is wired in, the pattern will be:
    #
    #   app = QApplication(sys.argv)
    #   ...create components...
    #   shutdown_manager.register(audio_recorder.stop, priority=10, name="stop-audio")
    #   shutdown_manager.register(stt_engine.shutdown, priority=20, name="release-stt")
    #   shutdown_manager.register(hotkey_manager.unregister, priority=30, name="unregister-hotkey")
    #   shutdown_manager.register(settings_store.save, priority=50, name="save-settings")
    #   app.aboutToQuit.connect(shutdown_manager.shutdown)
    #   sys.exit(app.exec())


if __name__ == "__main__":
    main()
