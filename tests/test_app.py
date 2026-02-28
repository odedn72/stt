# TDD: Written from spec 06-hotkey-lifecycle.md
"""
Tests for DictationStateMachine and AppCore (orchestrator).

Spec 06 defines:
- DictationState: IDLE, STARTING, ACTIVE, STOPPING, ERROR
- Valid transitions (section 3.3)
- Invalid transitions raise ValueError
- StateTransition records
- State change callbacks

Design spec section 14: State machine summary.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from systemstt.app import DictationStateMachine, DictationState, StateTransition


# ---------------------------------------------------------------------------
# DictationState enum tests
# ---------------------------------------------------------------------------

class TestDictationState:
    """Tests for the DictationState enum."""

    def test_idle_state(self) -> None:
        assert DictationState.IDLE is not None

    def test_starting_state(self) -> None:
        assert DictationState.STARTING is not None

    def test_active_state(self) -> None:
        assert DictationState.ACTIVE is not None

    def test_stopping_state(self) -> None:
        assert DictationState.STOPPING is not None

    def test_error_state(self) -> None:
        assert DictationState.ERROR is not None


# ---------------------------------------------------------------------------
# StateTransition data model tests
# ---------------------------------------------------------------------------

class TestStateTransition:
    """Tests for the StateTransition record."""

    def test_transition_fields(self) -> None:
        transition = StateTransition(
            from_state=DictationState.IDLE,
            to_state=DictationState.STARTING,
            trigger="hotkey",
        )
        assert transition.from_state == DictationState.IDLE
        assert transition.to_state == DictationState.STARTING
        assert transition.trigger == "hotkey"
        assert transition.error is None

    def test_transition_with_error(self) -> None:
        err = RuntimeError("mic disconnected")
        transition = StateTransition(
            from_state=DictationState.ACTIVE,
            to_state=DictationState.ERROR,
            trigger="device_error",
            error=err,
        )
        assert transition.error is err

    def test_transition_is_frozen(self) -> None:
        transition = StateTransition(
            from_state=DictationState.IDLE,
            to_state=DictationState.STARTING,
            trigger="hotkey",
        )
        with pytest.raises(AttributeError):
            transition.trigger = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DictationStateMachine initialization tests
# ---------------------------------------------------------------------------

class TestDictationStateMachineInit:
    """Tests for state machine initialization."""

    def test_initial_state_is_idle(self) -> None:
        sm = DictationStateMachine()
        assert sm.state == DictationState.IDLE

    def test_on_state_changed_default_is_none(self) -> None:
        sm = DictationStateMachine()
        assert sm.on_state_changed is None

    def test_on_state_changed_can_be_set(self) -> None:
        sm = DictationStateMachine()
        callback = MagicMock()
        sm.on_state_changed = callback
        assert sm.on_state_changed is callback


# ---------------------------------------------------------------------------
# Valid transitions tests (spec 06, section 3.3)
# ---------------------------------------------------------------------------

class TestDictationStateMachineValidTransitions:
    """Tests for all valid state transitions."""

    def test_idle_to_starting(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        assert sm.state == DictationState.STARTING

    def test_starting_to_active(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        assert sm.state == DictationState.ACTIVE

    def test_starting_to_error(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ERROR, "init_failed", error=RuntimeError("failed"))
        assert sm.state == DictationState.ERROR

    def test_active_to_stopping(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        sm.transition_to(DictationState.STOPPING, "hotkey")
        assert sm.state == DictationState.STOPPING

    def test_active_to_error(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        sm.transition_to(DictationState.ERROR, "mic_disconnected")
        assert sm.state == DictationState.ERROR

    def test_stopping_to_idle(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        sm.transition_to(DictationState.STOPPING, "hotkey")
        sm.transition_to(DictationState.IDLE, "teardown_complete")
        assert sm.state == DictationState.IDLE

    def test_error_to_idle(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ERROR, "init_failed")
        sm.transition_to(DictationState.IDLE, "user_dismissed")
        assert sm.state == DictationState.IDLE

    def test_error_to_starting(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ERROR, "init_failed")
        sm.transition_to(DictationState.STARTING, "retry")
        assert sm.state == DictationState.STARTING


# ---------------------------------------------------------------------------
# Invalid transitions tests
# ---------------------------------------------------------------------------

class TestDictationStateMachineInvalidTransitions:
    """Tests that invalid transitions raise ValueError."""

    def test_idle_to_active_invalid(self) -> None:
        sm = DictationStateMachine()
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.ACTIVE, "invalid")

    def test_idle_to_stopping_invalid(self) -> None:
        sm = DictationStateMachine()
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.STOPPING, "invalid")

    def test_idle_to_idle_invalid(self) -> None:
        sm = DictationStateMachine()
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.IDLE, "invalid")

    def test_starting_to_stopping_invalid(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.STOPPING, "invalid")

    def test_starting_to_idle_invalid(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.IDLE, "invalid")

    def test_active_to_starting_invalid(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.STARTING, "invalid")

    def test_active_to_idle_invalid(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.IDLE, "invalid")

    def test_stopping_to_active_invalid(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        sm.transition_to(DictationState.STOPPING, "hotkey")
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.ACTIVE, "invalid")

    def test_stopping_to_error_invalid(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        sm.transition_to(DictationState.STOPPING, "hotkey")
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.ERROR, "invalid")

    def test_error_to_active_invalid(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ERROR, "init_failed")
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.ACTIVE, "invalid")

    def test_error_to_stopping_invalid(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ERROR, "init_failed")
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.STOPPING, "invalid")


# ---------------------------------------------------------------------------
# can_transition_to tests
# ---------------------------------------------------------------------------

class TestDictationStateMachineCanTransition:
    """Tests for the can_transition_to query method."""

    def test_idle_can_transition_to_starting(self) -> None:
        sm = DictationStateMachine()
        assert sm.can_transition_to(DictationState.STARTING) is True

    def test_idle_cannot_transition_to_active(self) -> None:
        sm = DictationStateMachine()
        assert sm.can_transition_to(DictationState.ACTIVE) is False

    def test_idle_cannot_transition_to_idle(self) -> None:
        sm = DictationStateMachine()
        assert sm.can_transition_to(DictationState.IDLE) is False

    def test_active_can_transition_to_stopping(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        assert sm.can_transition_to(DictationState.STOPPING) is True

    def test_active_can_transition_to_error(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        assert sm.can_transition_to(DictationState.ERROR) is True

    def test_error_can_transition_to_idle(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ERROR, "init_failed")
        assert sm.can_transition_to(DictationState.IDLE) is True

    def test_error_can_transition_to_starting(self) -> None:
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ERROR, "init_failed")
        assert sm.can_transition_to(DictationState.STARTING) is True


# ---------------------------------------------------------------------------
# State change callback tests
# ---------------------------------------------------------------------------

class TestDictationStateMachineCallbacks:
    """Tests for the on_state_changed callback."""

    def test_callback_invoked_on_transition(self) -> None:
        sm = DictationStateMachine()
        callback = MagicMock()
        sm.on_state_changed = callback
        sm.transition_to(DictationState.STARTING, "hotkey")
        callback.assert_called_once()

    def test_callback_receives_state_transition(self) -> None:
        sm = DictationStateMachine()
        callback = MagicMock()
        sm.on_state_changed = callback
        sm.transition_to(DictationState.STARTING, "hotkey")
        transition = callback.call_args[0][0]
        assert isinstance(transition, StateTransition)
        assert transition.from_state == DictationState.IDLE
        assert transition.to_state == DictationState.STARTING
        assert transition.trigger == "hotkey"

    def test_callback_receives_error_on_error_transition(self) -> None:
        sm = DictationStateMachine()
        callback = MagicMock()
        sm.on_state_changed = callback
        sm.transition_to(DictationState.STARTING, "hotkey")
        err = RuntimeError("device error")
        sm.transition_to(DictationState.ERROR, "device_error", error=err)
        transition = callback.call_args[0][0]
        assert transition.error is err

    def test_callback_not_invoked_on_invalid_transition(self) -> None:
        sm = DictationStateMachine()
        callback = MagicMock()
        sm.on_state_changed = callback
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.ACTIVE, "invalid")
        callback.assert_not_called()

    def test_multiple_transitions_invoke_callback_each_time(self) -> None:
        sm = DictationStateMachine()
        callback = MagicMock()
        sm.on_state_changed = callback
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        sm.transition_to(DictationState.STOPPING, "hotkey")
        sm.transition_to(DictationState.IDLE, "teardown_complete")
        assert callback.call_count == 4


# ---------------------------------------------------------------------------
# Full lifecycle test
# ---------------------------------------------------------------------------

class TestDictationStateMachineFullLifecycle:
    """End-to-end state machine lifecycle tests."""

    def test_full_happy_path_cycle(self) -> None:
        """IDLE -> STARTING -> ACTIVE -> STOPPING -> IDLE."""
        sm = DictationStateMachine()
        assert sm.state == DictationState.IDLE
        sm.transition_to(DictationState.STARTING, "hotkey")
        assert sm.state == DictationState.STARTING
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        assert sm.state == DictationState.ACTIVE
        sm.transition_to(DictationState.STOPPING, "hotkey")
        assert sm.state == DictationState.STOPPING
        sm.transition_to(DictationState.IDLE, "teardown_complete")
        assert sm.state == DictationState.IDLE

    def test_error_recovery_cycle(self) -> None:
        """IDLE -> STARTING -> ERROR -> STARTING -> ACTIVE -> STOPPING -> IDLE."""
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ERROR, "init_failed")
        sm.transition_to(DictationState.STARTING, "retry")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        sm.transition_to(DictationState.STOPPING, "hotkey")
        sm.transition_to(DictationState.IDLE, "teardown_complete")
        assert sm.state == DictationState.IDLE

    def test_active_error_to_idle(self) -> None:
        """IDLE -> STARTING -> ACTIVE -> ERROR -> IDLE."""
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        sm.transition_to(DictationState.ERROR, "mic_disconnected")
        sm.transition_to(DictationState.IDLE, "user_dismissed")
        assert sm.state == DictationState.IDLE

    def test_multiple_dictation_sessions(self) -> None:
        """Two full IDLE->ACTIVE->IDLE cycles."""
        sm = DictationStateMachine()
        for _ in range(2):
            sm.transition_to(DictationState.STARTING, "hotkey")
            sm.transition_to(DictationState.ACTIVE, "init_complete")
            sm.transition_to(DictationState.STOPPING, "hotkey")
            sm.transition_to(DictationState.IDLE, "teardown_complete")
        assert sm.state == DictationState.IDLE


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestDictationStateMachineEdgeCases:
    """Edge case tests for the state machine."""

    def test_transition_preserves_state_on_invalid_attempt(self) -> None:
        """State should not change when an invalid transition is attempted."""
        sm = DictationStateMachine()
        assert sm.state == DictationState.IDLE
        with pytest.raises(ValueError):
            sm.transition_to(DictationState.ACTIVE, "invalid")
        assert sm.state == DictationState.IDLE

    def test_can_transition_to_returns_false_for_all_invalid_from_stopping(self) -> None:
        """From STOPPING, only IDLE is valid."""
        sm = DictationStateMachine()
        sm.transition_to(DictationState.STARTING, "hotkey")
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        sm.transition_to(DictationState.STOPPING, "hotkey")
        assert sm.can_transition_to(DictationState.STARTING) is False
        assert sm.can_transition_to(DictationState.ACTIVE) is False
        assert sm.can_transition_to(DictationState.STOPPING) is False
        assert sm.can_transition_to(DictationState.ERROR) is False
        assert sm.can_transition_to(DictationState.IDLE) is True

    def test_on_state_changed_set_to_none_stops_callbacks(self) -> None:
        """Setting on_state_changed to None should stop callbacks."""
        sm = DictationStateMachine()
        callback = MagicMock()
        sm.on_state_changed = callback
        sm.transition_to(DictationState.STARTING, "hotkey")
        assert callback.call_count == 1
        sm.on_state_changed = None
        sm.transition_to(DictationState.ACTIVE, "init_complete")
        # Callback should not have been called again
        assert callback.call_count == 1

    def test_error_transition_includes_error_object(self) -> None:
        """Transitioning to ERROR should attach the error to the transition."""
        sm = DictationStateMachine()
        callback = MagicMock()
        sm.on_state_changed = callback
        sm.transition_to(DictationState.STARTING, "hotkey")
        error = RuntimeError("mic failure")
        sm.transition_to(DictationState.ERROR, "mic_error", error=error)
        last_transition = callback.call_args_list[-1][0][0]
        assert last_transition.error is error
        assert last_transition.from_state == DictationState.STARTING
        assert last_transition.to_state == DictationState.ERROR
