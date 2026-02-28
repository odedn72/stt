# 04 — Voice Command Processor
**Version:** 1.0
**Date:** 2026-02-28
**Status:** Draft

---

## 1. Goal

Intercept transcription text before it is injected into the active application, detect voice command phrases, and execute the corresponding actions. Voice commands allow the user to edit text and control dictation without touching the keyboard.

**MRD requirements:**
- FR-007: Voice commands — "delete the last sentence", "delete the last word", "undo", "new line", "new paragraph", "select all", "copy", "paste", "stop dictation"
- MRD Section 9: Voice commands are English-only in v1.

**Design spec references:**
- Section 5.7: Pill shows voice command acknowledgment ("Deleted last word", etc.) for 2 seconds.
- Section 6.6: Commands tab shows the read-only command table with enable/disable toggle.

---

## 2. Interface

### 2.1 CommandRegistry

```python
from dataclasses import dataclass
from enum import Enum
from typing import Callable


class CommandAction(Enum):
    """Built-in actions that voice commands can trigger."""
    DELETE_LAST_WORD = "delete_last_word"
    DELETE_LAST_SENTENCE = "delete_last_sentence"
    UNDO = "undo"
    NEW_LINE = "new_line"
    NEW_PARAGRAPH = "new_paragraph"
    SELECT_ALL = "select_all"
    COPY = "copy"
    PASTE = "paste"
    STOP_DICTATION = "stop_dictation"


@dataclass(frozen=True)
class VoiceCommand:
    """A voice command definition."""
    trigger_phrases: tuple[str, ...]   # All phrases that trigger this command
    action: CommandAction              # The action to execute
    display_name: str                  # Human-readable name for UI
    confirmation_text: str             # Text shown in pill after execution


class CommandRegistry:
    """
    Registry of all known voice commands.

    In v1, all commands are built-in. The registry is read-only.
    In v2, custom commands may be added (ref MRD FR-021).
    """

    def __init__(self) -> None:
        """Initialize with built-in commands."""
        ...

    @property
    def commands(self) -> list[VoiceCommand]:
        """Return all registered commands."""
        ...

    def get_command_by_action(self, action: CommandAction) -> VoiceCommand | None:
        """Look up a command by its action type."""
        ...
```

### 2.2 CommandParser

```python
@dataclass(frozen=True)
class ParseResult:
    """Result of parsing transcription text for commands."""
    has_command: bool
    command: VoiceCommand | None        # The matched command, if any
    text_before: str                    # Text before the command phrase
    text_after: str                     # Text after the command phrase
    matched_phrase: str                 # The exact phrase that matched


class CommandParser:
    """
    Detects voice commands in transcription text.

    The parser checks if the transcription text contains any registered
    command trigger phrases. Commands are only detected at utterance
    boundaries (see Notes for Developer).
    """

    def __init__(self, registry: CommandRegistry) -> None: ...

    def parse(self, text: str) -> ParseResult:
        """
        Parse transcription text for voice commands.

        Args:
            text: Transcribed text from the STT engine.

        Returns:
            ParseResult indicating whether a command was found and
            any surrounding text.
        """
        ...

    @property
    def enabled(self) -> bool:
        """Whether voice command parsing is active."""
        ...

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable voice command parsing."""
        ...
```

### 2.3 CommandExecutor

```python
from collections.abc import Callable


class CommandExecutor:
    """
    Executes voice command actions by delegating to platform services.

    The executor translates CommandAction values into system-level
    operations (keystrokes, text manipulation, app control).
    """

    def __init__(
        self,
        text_injector: "TextInjector",          # For text manipulation actions
        stop_dictation_callback: Callable[[], None],  # For stop command
    ) -> None: ...

    async def execute(self, action: CommandAction) -> None:
        """
        Execute a voice command action.

        Args:
            action: The command action to execute.

        Raises:
            TextInjectionError: If the action requires text manipulation
                               and injection fails.
        """
        ...
```

---

## 3. Data Models

### 3.1 Built-in Command Registry (v1)

| Action | Trigger Phrases | Keyboard Equivalent | Confirmation Text |
|--------|----------------|--------------------|--------------------|
| DELETE_LAST_WORD | "delete last word", "delete the last word" | `⌥⌫` (Option+Backspace) | "Deleted last word" |
| DELETE_LAST_SENTENCE | "delete last sentence", "delete the last sentence" | Select sentence + `⌫` | "Deleted last sentence" |
| UNDO | "undo", "undo that" | `⌘Z` | "Undone" |
| NEW_LINE | "new line", "newline" | `↩` (Return) | "New line" |
| NEW_PARAGRAPH | "new paragraph" | `↩↩` (Return twice) | "New paragraph" |
| SELECT_ALL | "select all", "select everything" | `⌘A` | "Selected all" |
| COPY | "copy", "copy that" | `⌘C` | "Copied" |
| PASTE | "paste", "paste that" | `⌘V` | "Pasted" |
| STOP_DICTATION | "stop dictation", "stop listening" | N/A (internal signal) | "Dictation stopped" |

### 3.2 Trigger Phrase Matching Rules

1. **Case-insensitive:** "Delete Last Word" matches "delete last word".
2. **Punctuation-stripped:** Whisper may add punctuation. "Delete last word." should match.
3. **Whitespace-normalized:** Multiple spaces collapsed to single space.
4. **Boundary detection:** Commands are matched at the end of the transcription text OR as standalone utterances. A command in the middle of a sentence is NOT treated as a command (see section 6, note 2).

---

## 4. Dependencies

**Internal dependencies:**
- `systemstt.platform.base.TextInjector` — for executing keyboard-based actions
- `systemstt.errors` — no command-specific errors in v1 (failures propagate as TextInjectionError)

**No external dependencies.** The command processor is pure Python.

---

## 5. Error Handling

| Error | Condition | Behavior |
|-------|-----------|----------|
| `TextInjectionError` | Failed to execute keyboard shortcut | Pill shows error; command acknowledged but action failed |
| Command not recognized | Text doesn't match any trigger | No error — text is passed through to text injection normally |

The voice command processor should NEVER cause dictation to fail. If a command execution fails, the error is reported to the UI but dictation continues.

---

## 6. Notes for Developer

### 6.1 Command Detection Strategy

The parser should use a **suffix-matching** strategy:

1. Normalize the incoming text (lowercase, strip punctuation, normalize whitespace).
2. Check if the normalized text **ends with** any trigger phrase.
3. If a match is found at the end, extract the text before the command phrase.
4. If there is text before the command, inject that text first, THEN execute the command.
5. If the entire text IS the command (no preceding text), just execute the command.

**Why suffix matching?** When the user says "The quick brown fox delete last word", the intent is: type "The quick brown fox", then delete "fox". The command is at the end of the utterance because the user says it after the dictated text.

### 6.2 Avoiding False Positives

The trigger phrases are chosen to be unlikely in normal dictation. However:
- "copy" and "paste" are common English words. To mitigate: only match these as standalone utterances (the entire transcription is just "copy" or "paste"), not when embedded in a sentence.
- "undo" is less common in normal speech but could appear. Same mitigation: prefer standalone match.
- For phrases like "delete last word" — these are multi-word and highly unlikely in normal dictation, so suffix matching is safe.

**Implementation:** Categorize commands as:
- **Strict standalone:** "copy", "paste", "undo" — match only when the entire utterance is the command phrase (possibly with minor filler).
- **Suffix-safe:** "delete last word", "delete last sentence", "new line", "new paragraph", "select all", "stop dictation" — safe to suffix-match because they are multi-word and distinctive.

### 6.3 Action Execution via Keyboard Simulation

Most commands map to keyboard shortcuts. The `CommandExecutor` delegates to the `TextInjector` platform service, which can simulate keypresses:

```python
# Conceptual — actual implementation uses the platform TextInjector
async def _execute_delete_last_word(self) -> None:
    # macOS: Option+Backspace deletes the previous word
    await self.text_injector.send_keystroke(
        key="backspace", modifiers=["option"]
    )

async def _execute_undo(self) -> None:
    # macOS: Cmd+Z
    await self.text_injector.send_keystroke(
        key="z", modifiers=["command"]
    )

async def _execute_new_line(self) -> None:
    # Send Return key
    await self.text_injector.send_keystroke(key="return")

async def _execute_new_paragraph(self) -> None:
    # Send Return key twice
    await self.text_injector.send_keystroke(key="return")
    await self.text_injector.send_keystroke(key="return")
```

### 6.4 DELETE_LAST_SENTENCE Implementation

"Delete last sentence" is more complex than a single keystroke:
1. Approach A (simple): Use `⌘⇧←` (Cmd+Shift+Left) to select to the beginning of the line, then `⌫` to delete. This works for single-line sentences but not multi-line.
2. Approach B (tracking): Maintain a buffer of recently injected text. When "delete last sentence" is detected, calculate how many characters to delete (back to the last sentence-ending punctuation), then send that many backspaces.
3. **Recommended for v1:** Approach A — simple and good enough for most use cases. The user can always say "undo" to recover. Document the limitation.

### 6.5 STOP_DICTATION Command

This command does NOT use the text injector. Instead, the `CommandExecutor` calls the `stop_dictation_callback` provided at construction. This signals the App Core to stop dictation, equivalent to pressing the hotkey.

### 6.6 Integration with App Core

The processing pipeline in the App Core is:

```
TranscriptionResult from STT Engine
        │
        ▼
CommandParser.parse(result.full_text)
        │
        ├── has_command = True
        │       │
        │       ├── text_before not empty → inject text_before
        │       │
        │       └── execute command action
        │           │
        │           └── emit signal: command_executed(confirmation_text)
        │                   │
        │                   └── UI: pill shows confirmation
        │
        └── has_command = False
                │
                └── inject full_text into active app
```

### 6.7 Testing

- **CommandParser tests:** Test each trigger phrase matches correctly. Test case insensitivity, punctuation stripping. Test that commands in the middle of text do NOT match. Test standalone vs suffix modes.
- **CommandExecutor tests:** Mock the `TextInjector`. Verify correct keystrokes are sent for each action. Verify `stop_dictation_callback` is called for STOP_DICTATION.
- **Integration tests:** Feed sample transcription text through the parser and verify the correct routing (inject text vs execute command vs both).
