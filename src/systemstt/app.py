"""
Application core — DictationStateMachine and AppCore orchestrator.

The DictationStateMachine manages the dictation lifecycle:
IDLE -> STARTING -> ACTIVE -> STOPPING -> IDLE, with ERROR handling.

The state machine validates all transitions and notifies listeners
via the on_state_changed callback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class DictationState(Enum):
    """States in the dictation lifecycle."""

    IDLE = auto()
    STARTING = auto()
    ACTIVE = auto()
    STOPPING = auto()
    ERROR = auto()


@dataclass(frozen=True)
class StateTransition:
    """Record of a state transition."""

    from_state: DictationState
    to_state: DictationState
    trigger: str
    error: Optional[Exception] = None


# Valid state transitions: maps from_state -> set of allowed to_states
_VALID_TRANSITIONS: dict[DictationState, frozenset[DictationState]] = {
    DictationState.IDLE: frozenset({DictationState.STARTING}),
    DictationState.STARTING: frozenset({DictationState.ACTIVE, DictationState.ERROR}),
    DictationState.ACTIVE: frozenset({DictationState.STOPPING, DictationState.ERROR}),
    DictationState.STOPPING: frozenset({DictationState.IDLE}),
    DictationState.ERROR: frozenset({DictationState.IDLE, DictationState.STARTING}),
}


class DictationStateMachine:
    """Manages the dictation state and validates transitions.

    Valid transitions:
        IDLE -> STARTING        (hotkey pressed)
        STARTING -> ACTIVE      (audio + engine ready)
        STARTING -> ERROR       (initialization failed)
        ACTIVE -> STOPPING      (hotkey pressed, or "stop dictation" command)
        ACTIVE -> ERROR         (runtime error: mic disconnected, API failure)
        STOPPING -> IDLE        (buffers flushed, cleanup complete)
        ERROR -> IDLE           (user acknowledged error, or auto-recovered)
        ERROR -> STARTING       (retry)
    """

    def __init__(self) -> None:
        self._state: DictationState = DictationState.IDLE
        self._on_state_changed: Optional[Callable[[StateTransition], None]] = None

    @property
    def state(self) -> DictationState:
        """Current state."""
        return self._state

    @property
    def on_state_changed(self) -> Optional[Callable[[StateTransition], None]]:
        """Callback invoked on every state change."""
        return self._on_state_changed

    @on_state_changed.setter
    def on_state_changed(
        self, callback: Optional[Callable[[StateTransition], None]]
    ) -> None:
        """Set the callback for state changes."""
        self._on_state_changed = callback

    def transition_to(
        self,
        new_state: DictationState,
        trigger: str,
        error: Optional[Exception] = None,
    ) -> None:
        """Attempt a state transition.

        Args:
            new_state: The target state.
            trigger: Description of what caused the transition.
            error: Attached error for ERROR transitions.

        Raises:
            ValueError: If the transition is not valid from the current state.
        """
        if not self.can_transition_to(new_state):
            raise ValueError(
                f"Invalid transition: {self._state.name} -> {new_state.name} "
                f"(trigger: {trigger})"
            )

        old_state = self._state
        self._state = new_state

        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            trigger=trigger,
            error=error,
        )

        logger.info(
            "State transition: %s -> %s (trigger: %s)",
            old_state.name,
            new_state.name,
            trigger,
        )

        if self._on_state_changed is not None:
            self._on_state_changed(transition)

    def can_transition_to(self, new_state: DictationState) -> bool:
        """Check if a transition to the given state is valid from the current state."""
        allowed = _VALID_TRANSITIONS.get(self._state, frozenset())
        return new_state in allowed
