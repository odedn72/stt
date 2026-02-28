# TDD: Written from spec 08-configuration.md
"""
Tests for SecureStore ABC and MacOSKeychainStore.

All Keychain APIs (SecItemAdd, SecItemCopyMatching, etc.) are mocked.
Tests verify:
- get/set/delete/exists operations
- Error handling when keychain is inaccessible
- Service name is 'systemstt'
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from systemstt.config.secure import SecureStore
from systemstt.platform.macos.keychain import MacOSKeychainStore
from systemstt.errors import KeychainAccessError


# ---------------------------------------------------------------------------
# SecureStore ABC tests
# ---------------------------------------------------------------------------

class TestSecureStoreABC:
    """Tests that SecureStore cannot be instantiated directly."""

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            SecureStore()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# MacOSKeychainStore service name
# ---------------------------------------------------------------------------

class TestMacOSKeychainStoreServiceName:
    """Tests for the keychain service name."""

    def test_service_name_is_systemstt(self) -> None:
        assert MacOSKeychainStore.SERVICE_NAME == "systemstt"


# ---------------------------------------------------------------------------
# MacOSKeychainStore.set tests
# ---------------------------------------------------------------------------

class TestMacOSKeychainStoreSet:
    """Tests for storing secrets in the keychain."""

    @patch("systemstt.platform.macos.keychain.SecItemAdd")
    @patch("systemstt.platform.macos.keychain.SecItemUpdate")
    def test_set_stores_value(
        self, mock_update: MagicMock, mock_add: MagicMock
    ) -> None:
        # SecItemUpdate returns non-zero (not found), so SecItemAdd is called
        mock_update.return_value = -25300  # errSecItemNotFound
        mock_add.return_value = 0  # success
        store = MacOSKeychainStore()
        store.set("openai_api_key", "sk-test-123")
        assert mock_add.called or mock_update.called

    @patch("systemstt.platform.macos.keychain.SecItemAdd")
    @patch("systemstt.platform.macos.keychain.SecItemUpdate")
    def test_set_updates_existing_value(
        self, mock_update: MagicMock, mock_add: MagicMock
    ) -> None:
        mock_update.return_value = 0  # success (item existed, was updated)
        store = MacOSKeychainStore()
        store.set("openai_api_key", "sk-new-key")
        mock_update.assert_called()

    @patch("systemstt.platform.macos.keychain.SecItemAdd", return_value=-25291)
    @patch("systemstt.platform.macos.keychain.SecItemUpdate", return_value=-25291)
    def test_set_raises_keychain_access_error_on_failure(
        self, mock_update: MagicMock, mock_add: MagicMock
    ) -> None:
        store = MacOSKeychainStore()
        with pytest.raises(KeychainAccessError):
            store.set("openai_api_key", "sk-test")


# ---------------------------------------------------------------------------
# MacOSKeychainStore.get tests
# ---------------------------------------------------------------------------

class TestMacOSKeychainStoreGet:
    """Tests for retrieving secrets from the keychain."""

    @patch("systemstt.platform.macos.keychain.SecItemCopyMatching")
    def test_get_returns_stored_value(self, mock_copy: MagicMock) -> None:
        mock_copy.return_value = (0, b"sk-test-123")
        store = MacOSKeychainStore()
        value = store.get("openai_api_key")
        assert value == "sk-test-123"

    @patch("systemstt.platform.macos.keychain.SecItemCopyMatching")
    def test_get_returns_none_when_not_found(self, mock_copy: MagicMock) -> None:
        mock_copy.return_value = (-25300, None)  # errSecItemNotFound
        store = MacOSKeychainStore()
        value = store.get("nonexistent_key")
        assert value is None

    @patch("systemstt.platform.macos.keychain.SecItemCopyMatching")
    def test_get_raises_keychain_access_error_on_failure(
        self, mock_copy: MagicMock
    ) -> None:
        mock_copy.side_effect = Exception("Keychain locked")
        store = MacOSKeychainStore()
        with pytest.raises(KeychainAccessError):
            store.get("openai_api_key")


# ---------------------------------------------------------------------------
# MacOSKeychainStore.delete tests
# ---------------------------------------------------------------------------

class TestMacOSKeychainStoreDelete:
    """Tests for deleting secrets from the keychain."""

    @patch("systemstt.platform.macos.keychain.SecItemDelete")
    def test_delete_removes_value(self, mock_delete: MagicMock) -> None:
        mock_delete.return_value = 0  # success
        store = MacOSKeychainStore()
        store.delete("openai_api_key")
        mock_delete.assert_called()

    @patch("systemstt.platform.macos.keychain.SecItemDelete")
    def test_delete_nonexistent_key_is_safe(self, mock_delete: MagicMock) -> None:
        mock_delete.return_value = -25300  # errSecItemNotFound
        store = MacOSKeychainStore()
        store.delete("nonexistent_key")  # Should not raise


# ---------------------------------------------------------------------------
# MacOSKeychainStore.exists tests
# ---------------------------------------------------------------------------

class TestMacOSKeychainStoreExists:
    """Tests for checking if a key exists."""

    @patch("systemstt.platform.macos.keychain.SecItemCopyMatching")
    def test_exists_returns_true_when_key_found(self, mock_copy: MagicMock) -> None:
        mock_copy.return_value = (0, b"some-value")
        store = MacOSKeychainStore()
        assert store.exists("openai_api_key") is True

    @patch("systemstt.platform.macos.keychain.SecItemCopyMatching")
    def test_exists_returns_false_when_key_not_found(self, mock_copy: MagicMock) -> None:
        mock_copy.return_value = (-25300, None)
        store = MacOSKeychainStore()
        assert store.exists("nonexistent_key") is False
