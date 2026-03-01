"""
macOS Keychain wrapper for secure secret storage.

Uses Security framework via PyObjC to store, retrieve, and delete
secrets in the macOS Keychain.
"""

from __future__ import annotations

import logging

from systemstt.config.secure import SecureStore
from systemstt.errors import KeychainAccessError

logger = logging.getLogger(__name__)

# These will be the actual PyObjC Security framework functions.
# They are imported at module level so they can be mocked in tests.
try:
    from Security import (  # type: ignore[import-untyped]
        SecItemAdd,
        SecItemCopyMatching,
        SecItemDelete,
        SecItemUpdate,
        kSecAttrAccount,
        kSecAttrService,
        kSecClass,
        kSecClassGenericPassword,
        kSecMatchLimit,
        kSecMatchLimitOne,
        kSecReturnData,
        kSecValueData,
    )
except ImportError:
    # Allow importing on non-macOS for testing with mocks
    SecItemAdd = None
    SecItemCopyMatching = None
    SecItemUpdate = None
    SecItemDelete = None

# Keychain error codes
_ERR_SEC_SUCCESS = 0
_ERR_SEC_ITEM_NOT_FOUND = -25300


class MacOSKeychainStore(SecureStore):
    """macOS Keychain-backed implementation of SecureStore."""

    SERVICE_NAME = "systemstt"

    def _build_query(self, key: str) -> dict[str, object]:
        """Build a base keychain query dict for the given key."""
        return {
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: self.SERVICE_NAME,
            kSecAttrAccount: key,
        }

    def get(self, key: str) -> str | None:
        """Retrieve a secret from the Keychain.

        Returns None if the key is not found. Raises KeychainAccessError
        on unexpected failures.
        """
        try:
            query = self._build_query(key)
            query[kSecReturnData] = True
            query[kSecMatchLimit] = kSecMatchLimitOne

            status, data = SecItemCopyMatching(query, None)

            if status == _ERR_SEC_ITEM_NOT_FOUND:
                return None

            if status != _ERR_SEC_SUCCESS:
                raise KeychainAccessError(
                    f"Failed to retrieve key '{key}' from Keychain (status={status})"
                )

            if data is None:
                return None

            if isinstance(data, bytes):
                return data.decode("utf-8")
            # NSData/CFData from Security framework — convert to bytes first
            if hasattr(data, "bytes"):
                return bytes(data).decode("utf-8")
            return bytes(data).decode("utf-8")
        except KeychainAccessError:
            raise
        except Exception as exc:
            raise KeychainAccessError(f"Failed to access Keychain for key '{key}': {exc}") from exc

    def set(self, key: str, value: str) -> None:
        """Store a secret in the Keychain.

        Creates a new entry or updates an existing one.
        Raises KeychainAccessError on failure.
        """
        value_data = value.encode("utf-8")
        query = self._build_query(key)
        update_attrs = {kSecValueData: value_data}

        # Try to update first (in case the item already exists)
        status = SecItemUpdate(query, update_attrs)

        if status == _ERR_SEC_SUCCESS:
            return

        if status == _ERR_SEC_ITEM_NOT_FOUND:
            # Item doesn't exist yet, add it
            add_attrs = dict(query)
            add_attrs[kSecValueData] = value_data
            result = SecItemAdd(add_attrs, None)
            # SecItemAdd returns (status, item_ref) tuple
            add_status = result[0] if isinstance(result, tuple) else result
            if add_status != _ERR_SEC_SUCCESS:
                raise KeychainAccessError(
                    f"Failed to store key '{key}' in Keychain (status={add_status})"
                )
            return

        raise KeychainAccessError(f"Failed to update key '{key}' in Keychain (status={status})")

    def delete(self, key: str) -> None:
        """Delete a secret from the Keychain.

        No-op if the key doesn't exist.
        """
        query = self._build_query(key)
        status = SecItemDelete(query)

        if status in (_ERR_SEC_SUCCESS, _ERR_SEC_ITEM_NOT_FOUND):
            return

        raise KeychainAccessError(f"Failed to delete key '{key}' from Keychain (status={status})")

    def exists(self, key: str) -> bool:
        """Check if a key exists in the Keychain."""
        try:
            query = self._build_query(key)
            query[kSecReturnData] = True
            query[kSecMatchLimit] = kSecMatchLimitOne

            status, _data = SecItemCopyMatching(query, None)
            return bool(status == _ERR_SEC_SUCCESS)
        except Exception:
            return False
