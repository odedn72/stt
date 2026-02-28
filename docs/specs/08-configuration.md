# 08 — Configuration and Persistence
**Version:** 1.0
**Date:** 2026-02-28
**Status:** Draft

---

## 1. Goal

Manage all user preferences — define the settings model with sensible defaults, persist settings to disk as JSON, and store sensitive data (API keys) in the OS keychain. Configuration changes take effect immediately without requiring an application restart.

**MRD requirements:**
- FR-001: Configurable hotkey (stored in settings)
- FR-008: Configurable STT engine (stored in settings)
- FR-009: Persistent settings — "app remembers the last configuration on restart"
- FR-011: Configurable Whisper model size
- FR-013: Audio input device selection
- NFR-006: API key stored securely (OS keychain)
- NFR-007: Sensible defaults — "work with minimal configuration out of the box"

**Design spec references:**
- Section 6: Settings window (all configurable values)
- Section 8.2: Default state on first launch

---

## 2. Interface

### 2.1 SettingsModel

```python
from pydantic import BaseModel, Field
from enum import Enum


class EngineType(str, Enum):
    CLOUD_API = "cloud_api"
    LOCAL_WHISPER = "local_whisper"


class WhisperModelSize(str, Enum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class SettingsModel(BaseModel):
    """
    Complete application settings model.

    Pydantic model with defaults matching the design spec section 8.2.
    Serialized to/from JSON for persistence.

    Sensitive fields (API key) are NOT stored in this model — they are
    stored and retrieved separately via SecureStore.
    """

    # --- General Tab ---
    hotkey_key: str = "space"
    hotkey_modifiers: list[str] = Field(default_factory=lambda: ["option"])
    start_on_login: bool = False
    show_in_dock: bool = False

    # --- Floating Indicator ---
    show_status_pill: bool = True
    show_live_preview: bool = False
    pill_position_x: int | None = None   # None = default position
    pill_position_y: int | None = None

    # --- Engine Tab ---
    engine: EngineType = EngineType.CLOUD_API
    cloud_api_provider: str = "openai"
    cloud_api_base_url: str = "https://api.openai.com/v1"
    cloud_api_model: str = "whisper-1"
    local_model_size: WhisperModelSize = WhisperModelSize.MEDIUM
    local_compute_type: str = "int8"

    # --- Audio Tab ---
    audio_device_id: int | None = None    # None = system default
    audio_device_name: str | None = None  # Stored for display; device_id is authoritative

    # --- Commands Tab ---
    voice_commands_enabled: bool = True

    # --- Application ---
    check_for_updates: bool = False

    class Config:
        use_enum_values = True
```

### 2.2 SettingsStore

```python
from pathlib import Path


class SettingsStore:
    """
    Loads and saves SettingsModel to a JSON file.

    File location: ~/.config/systemstt/settings.json

    Behaviors:
    - If the file doesn't exist, returns defaults (first launch).
    - If the file is corrupted/invalid, logs a warning and returns defaults.
    - Writes are atomic (write to temp file, then rename).
    - Creates parent directories if they don't exist.
    """

    DEFAULT_PATH = Path.home() / ".config" / "systemstt" / "settings.json"

    def __init__(self, path: Path | None = None) -> None:
        """
        Args:
            path: Override the default settings file path (useful for testing).
        """
        ...

    def load(self) -> SettingsModel:
        """
        Load settings from disk.

        Returns:
            SettingsModel populated from the JSON file, or defaults if
            the file doesn't exist or is invalid.
        """
        ...

    def save(self, settings: SettingsModel) -> None:
        """
        Save settings to disk.

        Writes atomically: creates a temp file in the same directory,
        writes the JSON, then renames to the final path.

        Raises:
            SettingsLoadError: If writing fails (disk full, permissions, etc.)
        """
        ...

    @property
    def file_path(self) -> Path:
        """Return the path to the settings file."""
        ...
```

### 2.3 SecureStore (Abstract Base Class)

```python
from abc import ABC, abstractmethod


class SecureStore(ABC):
    """
    Abstract interface for storing and retrieving sensitive values
    (API keys, tokens) using the OS-level secure storage.
    """

    @abstractmethod
    def get(self, key: str) -> str | None:
        """
        Retrieve a secret value by key.

        Returns:
            The stored value, or None if not found.

        Raises:
            KeychainAccessError: If the keychain is inaccessible.
        """
        ...

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """
        Store a secret value.

        Args:
            key: The key name (e.g., "openai_api_key").
            value: The secret value to store.

        Raises:
            KeychainAccessError: If the keychain is inaccessible.
        """
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Delete a stored secret. Safe to call if key doesn't exist.

        Raises:
            KeychainAccessError: If the keychain is inaccessible.
        """
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists in the secure store."""
        ...
```

### 2.4 MacOSKeychainStore

```python
class MacOSKeychainStore(SecureStore):
    """
    macOS Keychain implementation using the Security framework via PyObjC.

    Service name: "systemstt"
    Account names map to key names (e.g., "openai_api_key").
    """

    SERVICE_NAME = "systemstt"

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
```

### 2.5 SettingsManager

```python
from collections.abc import Callable


class SettingsManager:
    """
    High-level settings management that coordinates the SettingsModel,
    SettingsStore, and SecureStore.

    This is the single point of access for all settings operations.
    The App Core and UI interact with SettingsManager, not with the
    underlying stores directly.
    """

    def __init__(
        self,
        store: SettingsStore,
        secure_store: SecureStore,
    ) -> None: ...

    @property
    def settings(self) -> SettingsModel:
        """Return the current settings (in-memory copy)."""
        ...

    def load(self) -> SettingsModel:
        """Load settings from disk and secure store. Returns the loaded model."""
        ...

    def save(self) -> None:
        """Persist current settings to disk."""
        ...

    def update(self, **kwargs: object) -> None:
        """
        Update one or more settings and persist immediately.

        Example:
            manager.update(engine="local_whisper", local_model_size="small")

        Raises:
            pydantic.ValidationError: If the new values fail validation.
        """
        ...

    def get_api_key(self) -> str | None:
        """Retrieve the API key from the secure store."""
        ...

    def set_api_key(self, key: str) -> None:
        """Store an API key in the secure store."""
        ...

    def delete_api_key(self) -> None:
        """Delete the API key from the secure store."""
        ...

    @property
    def on_settings_changed(self) -> Callable[[str, object], None] | None:
        """Callback invoked when any setting changes. Args: (key, new_value)."""
        ...

    @on_settings_changed.setter
    def on_settings_changed(self, callback: Callable[[str, object], None] | None) -> None: ...
```

---

## 3. Data Models

### 3.1 Settings File Format

Location: `~/.config/systemstt/settings.json`

Example content:
```json
{
  "hotkey_key": "space",
  "hotkey_modifiers": ["option"],
  "start_on_login": false,
  "show_in_dock": false,
  "show_status_pill": true,
  "show_live_preview": false,
  "pill_position_x": null,
  "pill_position_y": null,
  "engine": "cloud_api",
  "cloud_api_provider": "openai",
  "cloud_api_base_url": "https://api.openai.com/v1",
  "cloud_api_model": "whisper-1",
  "local_model_size": "medium",
  "local_compute_type": "int8",
  "audio_device_id": null,
  "audio_device_name": null,
  "voice_commands_enabled": true,
  "check_for_updates": false
}
```

### 3.2 Secure Store Keys

| Key Name | Value | Notes |
|----------|-------|-------|
| `openai_api_key` | The user's OpenAI API key | Used by CloudAPIEngine |

Future keys can be added for additional providers without schema changes.

### 3.3 Default Values (First Launch)

Per design spec section 8.2:

| Setting | Default | Rationale |
|---------|---------|-----------|
| Engine | Cloud API | Best accuracy for Intel Mac (MRD section 7) |
| Hotkey | `Option+Space` | Standard, unlikely to conflict |
| Language detection | Auto | Always auto (no setting to override) |
| Show status pill | On | User should see dictation state |
| Show live preview | Off | Less visual clutter by default |
| Voice commands | On | Core feature |
| Show in dock | Off | Menu bar app convention |
| Model size | Medium | Best quality/speed for CPU (MRD section 7) |
| Compute type | int8 | Required for acceptable speed on Intel i9 |

---

## 4. Dependencies

| Dependency | Usage |
|-----------|-------|
| pydantic | Settings model validation, serialization, defaults |
| PyObjC (pyobjc-framework-Security) | macOS Keychain access |

**Internal dependencies:**
- `systemstt.errors` — `SettingsLoadError`, `KeychainAccessError`

---

## 5. Error Handling

| Error | Condition | Behavior |
|-------|-----------|----------|
| `SettingsLoadError` | JSON file corrupted, invalid JSON | Log warning; return default SettingsModel. The corrupt file is backed up as `settings.json.bak` before being overwritten on next save. |
| `SettingsLoadError` | Cannot write to settings file (permissions, disk full) | Log error; settings remain in memory but will be lost on restart. Notification to user. |
| `KeychainAccessError` | Keychain locked, inaccessible, or permissions denied | Log error; API key unavailable. Cloud engine will fail with "No API key". User directed to re-enter key. |
| `pydantic.ValidationError` | Invalid value passed to `update()` | Raised to caller. Settings are not changed. |

**Atomic writes:** To prevent data loss, settings are written to a temp file first, then atomically renamed. This ensures that a crash during write doesn't corrupt the settings file.

---

## 6. Notes for Developer

### 6.1 Pydantic Usage

```python
from pydantic import BaseModel
import json
from pathlib import Path

# Load
path = Path("~/.config/systemstt/settings.json").expanduser()
if path.exists():
    data = json.loads(path.read_text())
    settings = SettingsModel(**data)
else:
    settings = SettingsModel()  # All defaults

# Save
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(settings.model_dump_json(indent=2))

# Update a single field
settings_dict = settings.model_dump()
settings_dict["engine"] = "local_whisper"
settings = SettingsModel(**settings_dict)
```

### 6.2 macOS Keychain Access

```python
# Conceptual PyObjC usage for Keychain
from Security import (
    SecItemAdd,
    SecItemCopyMatching,
    SecItemUpdate,
    SecItemDelete,
    kSecClass,
    kSecClassGenericPassword,
    kSecAttrService,
    kSecAttrAccount,
    kSecValueData,
    kSecReturnData,
    kSecMatchLimit,
    kSecMatchLimitOne,
)
from Foundation import NSData

SERVICE = "systemstt"

def keychain_set(account: str, value: str) -> None:
    query = {
        kSecClass: kSecClassGenericPassword,
        kSecAttrService: SERVICE,
        kSecAttrAccount: account,
        kSecValueData: value.encode("utf-8"),
    }
    # Try update first; if not found, add
    status = SecItemUpdate(
        {kSecClass: kSecClassGenericPassword, kSecAttrService: SERVICE, kSecAttrAccount: account},
        {kSecValueData: value.encode("utf-8")},
    )
    if status != 0:  # errSecItemNotFound
        SecItemAdd(query, None)

def keychain_get(account: str) -> str | None:
    query = {
        kSecClass: kSecClassGenericPassword,
        kSecAttrService: SERVICE,
        kSecAttrAccount: account,
        kSecReturnData: True,
        kSecMatchLimit: kSecMatchLimitOne,
    }
    status, result = SecItemCopyMatching(query, None)
    if status == 0 and result:
        return bytes(result).decode("utf-8")
    return None
```

### 6.3 Atomic File Writes

```python
import tempfile
import os

def atomic_write(path: Path, content: str) -> None:
    """Write content to a file atomically using rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=".settings_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.rename(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```

### 6.4 Settings Change Notification

When `SettingsManager.update()` is called:
1. Validate the new values using pydantic.
2. Update the in-memory SettingsModel.
3. Persist to disk (atomic write).
4. Invoke `on_settings_changed(key, new_value)` for each changed field.

The App Core listens to `on_settings_changed` and reacts:
- `engine` changed -> switch the STT engine (via EngineManager)
- `hotkey_*` changed -> re-register the hotkey
- `show_status_pill` changed -> show/hide the pill
- `audio_device_id` changed -> reconfigure the AudioRecorder
- etc.

### 6.5 Forward Compatibility

When loading settings:
- Unknown keys in the JSON are silently ignored (pydantic handles this).
- Missing keys use default values (pydantic handles this).
- This means the app can be upgraded without losing settings, and old settings files remain compatible.

### 6.6 Testing

- **SettingsModel tests:** Test default values match the design spec. Test serialization round-trip (model -> JSON -> model). Test validation (invalid values rejected).
- **SettingsStore tests:** Use a temp directory for the settings file. Test load from nonexistent file (returns defaults). Test load from corrupt file (returns defaults). Test save + load round-trip. Test atomic write (simulate crash by killing the process during write — the old file should be intact).
- **SecureStore tests:** Mock the Keychain APIs. Test get/set/delete/exists operations. Test error handling when Keychain is inaccessible.
- **SettingsManager tests:** Test the full flow: load -> update -> save -> reload. Test that `on_settings_changed` is called with correct arguments.
