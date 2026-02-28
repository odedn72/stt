"""SystemSTT: System-wide speech-to-text for macOS."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("systemstt")
except PackageNotFoundError:  # pragma: no cover — only when not installed
    __version__ = "0.0.0-dev"
