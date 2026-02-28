"""
SecureStore — abstract interface for platform-specific secret storage.

On macOS this is backed by the Keychain. On Windows (v2) it would use
the Windows Credential Manager.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SecureStore(ABC):
    """Abstract interface for secure secret storage."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Retrieve a secret by key. Returns None if not found."""
        ...

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """Store a secret. Creates or updates the entry."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a secret by key. No-op if key doesn't exist."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists in the secure store."""
        ...
