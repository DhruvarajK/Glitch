"""Explicit, priority-ordered state transitions."""
from __future__ import annotations

from typing import Callable

from core.pet.state import (
    STATE_PRIORITY,
    TRANSIENT_STATES,
    PetState,
)
from core.utils.logger import get_logger

log = get_logger("state")


class PetStateMachine:
    """Tracks the current state and refuses transitions that would preempt
    something more important."""

    def __init__(self, initial: PetState = PetState.IDLE) -> None:
        self._state = initial
        self._previous = initial
        self._resume: PetState | None = None
        self._time_in_state = 0.0
        self.on_change: Callable[[PetState, PetState], None] | None = None

    # ---------------------------------------------------------------- state
    @property
    def state(self) -> PetState:
        return self._state

    @property
    def previous(self) -> PetState:
        return self._previous

    @property
    def time_in_state(self) -> float:
        return self._time_in_state

    @property
    def priority(self) -> int:
        return STATE_PRIORITY.get(self._state, 0)

    def is_transient(self) -> bool:
        return self._state in TRANSIENT_STATES

    def can_transition_to(self, state: PetState) -> bool:
        if state is self._state:
            return False
        # A transient state holds the floor until its animation finishes,
        # unless something strictly more important arrives. Ongoing states
        # (idle, walking, sitting, sleeping) can always be left.
        if self.is_transient():
            return STATE_PRIORITY.get(state, 0) > self.priority
        return True

    # ----------------------------------------------------------- transitions
    def transition(
        self, state: PetState, *, force: bool = False, resume_after: bool = False
    ) -> bool:
        if state is self._state:
            return False
        if not force and not self.can_transition_to(state):
            return False

        if resume_after and self._state not in TRANSIENT_STATES:
            self._resume = self._state

        self._previous = self._state
        self._state = state
        self._time_in_state = 0.0
        log.debug("State %s -> %s", self._previous.value, state.value)
        if self.on_change:
            self.on_change(self._previous, state)
        return True

    def resume(self, default: PetState = PetState.IDLE) -> PetState:
        """Return to whatever was interrupted, falling back to `default`."""
        target = self._resume or default
        self._resume = None
        self.transition(target, force=True)
        return target

    def clear_resume(self) -> None:
        self._resume = None

    def update(self, dt: float) -> None:
        self._time_in_state += dt
