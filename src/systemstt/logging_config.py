"""
Structured logging configuration for SystemSTT.

Provides:
- Rotating file handler (5 MB, 3 backups) to ~/.local/share/systemstt/systemstt.log
- Stderr handler for development
- Structured log format with timestamps, levels, and logger names
- Crash log handler that captures unhandled exceptions to a separate file
- Sensitive data filtering (API keys are never logged)

Usage:
    from systemstt.logging_config import configure_logging
    configure_logging("DEBUG")
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from typing import TYPE_CHECKING

from systemstt.constants import LOG_DIR, LOG_FILE

if TYPE_CHECKING:
    import types

# Crash log captures only ERROR/CRITICAL and unhandled exceptions
CRASH_LOG_FILE = LOG_DIR / "crash.log"

# Maximum log file size and backup count
_MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3

# Patterns that should never appear in logs
_SENSITIVE_PATTERNS = frozenset({
    "api_key",
    "api-key",
    "apikey",
    "secret",
    "password",
    "token",
    "authorization",
})

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive data from log records.

    Scans log messages *and* log args for patterns that might contain API keys,
    passwords, or other secrets and replaces them with [REDACTED].

    The filter inspects three surfaces:
    1. ``record.msg`` — the format string itself (e.g. ``"api_key=abc123"``)
    2. ``record.args`` — the interpolation values (tuple or dict form)
    3. The fully formatted message (``record.getMessage()``) — catches cases
       where neither ``msg`` nor individual args contain a sensitive pattern
       but the combined result does.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter the log record, redacting sensitive content."""
        # 1. Redact the format string itself
        if isinstance(record.msg, str):
            record.msg = self._redact_if_needed(record.msg)

        # 2. Redact interpolation args (tuple or dict)
        if isinstance(record.args, dict):
            record.args = {
                k: self._redact_if_needed(v) if isinstance(v, str) else v
                for k, v in record.args.items()
            }
        elif isinstance(record.args, tuple):
            record.args = tuple(
                self._redact_if_needed(a) if isinstance(a, str) else a
                for a in record.args
            )

        # 3. Check the fully formatted message for anything that slipped
        #    through (e.g. the format string is clean but the combined
        #    result contains a sensitive pattern).
        formatted = record.getMessage()
        if self._contains_sensitive(formatted):
            record.msg = self._redact(formatted)
            record.args = None

        return True

    @staticmethod
    def _contains_sensitive(text: str) -> bool:
        """Return True if *text* contains any sensitive pattern."""
        lowered = text.lower()
        return any(p in lowered for p in _SENSITIVE_PATTERNS)

    @classmethod
    def _redact_if_needed(cls, value: str) -> str:
        """Redact *value* only when it contains a sensitive pattern."""
        if cls._contains_sensitive(value):
            return cls._redact(value)
        return value

    @staticmethod
    def _redact(message: str) -> str:
        """Replace potential secret values in key=value or key: value patterns."""
        # This is a best-effort filter. The primary defense is not logging
        # secrets in the first place (see CLAUDE.md conventions).
        for pattern in _SENSITIVE_PATTERNS:
            # Match patterns like: api_key=abc123, api_key: abc123, "api_key": "abc123"
            message = re.sub(
                rf'({pattern})\s*[=:]\s*["\']?(\S+)["\']?',
                r'\1=[REDACTED]',
                message,
                flags=re.IGNORECASE,
            )
        return message


def configure_logging(level_name: str) -> None:
    """Configure the application logging system.

    Sets up:
    - Root 'systemstt' logger with the specified level
    - Rotating file handler (5 MB, 3 backups)
    - Stderr handler for console output
    - Crash log handler (ERROR+ only) for post-mortem analysis
    - Sensitive data filter on all handlers

    Args:
        level_name: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, level_name.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)
    sensitive_filter = SensitiveDataFilter()

    # Main rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=_MAX_LOG_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    file_handler.addFilter(sensitive_filter)

    # Stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(level)
    stderr_handler.addFilter(sensitive_filter)

    # Crash log handler — captures only ERROR and above
    crash_handler = logging.handlers.RotatingFileHandler(
        CRASH_LOG_FILE,
        maxBytes=_MAX_LOG_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    crash_handler.setFormatter(formatter)
    crash_handler.setLevel(logging.ERROR)
    crash_handler.addFilter(sensitive_filter)

    # Configure the root systemstt logger
    root_logger = logging.getLogger("systemstt")
    root_logger.setLevel(level)

    # Clear any existing handlers (prevents duplicate handlers on re-configure)
    root_logger.handlers.clear()

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(crash_handler)


def install_crash_handler() -> None:
    """Install a global unhandled exception handler.

    Captures any unhandled exception, logs it to the crash log,
    and then calls the default excepthook so the traceback still
    appears on stderr.
    """
    _original_excepthook = sys.excepthook
    logger = logging.getLogger("systemstt.crash")

    def _crash_handler(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Log unhandled exceptions before the process exits."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Let KeyboardInterrupt pass through cleanly
            _original_excepthook(exc_type, exc_value, exc_tb)
            return

        logger.critical(
            "Unhandled exception — SystemSTT is crashing",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        _original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _crash_handler
