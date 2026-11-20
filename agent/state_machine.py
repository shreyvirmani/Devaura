"""Investigation State Machine.

Enforces deterministic transitions for the Devaura investigation lifecycle:
CREATED -> COLLECTING_EVIDENCE -> EVIDENCE_READY -> ANALYZING -> CANDIDATES_GENERATED -> COMPLETED
(or FAILED from any non-terminal state).
"""

from typing import Set
from agent.models import InvestigationState


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal investigation state transition is attempted."""
    pass


class InvestigationStateMachine:
    """Finite State Machine guarding investigation progress."""

    VALID_TRANSITIONS: dict[InvestigationState, Set[InvestigationState]] = {
        InvestigationState.CREATED: {
            InvestigationState.COLLECTING_EVIDENCE,
            InvestigationState.FAILED,
        },
        InvestigationState.INVESTIGATING: {
            InvestigationState.COLLECTING_EVIDENCE,
            InvestigationState.FAILED,
        },
        InvestigationState.COLLECTING_EVIDENCE: {
            InvestigationState.EVIDENCE_READY,
            InvestigationState.FAILED,
        },
        InvestigationState.EVIDENCE_READY: {
            InvestigationState.ANALYZING,
            InvestigationState.FAILED,
        },
        InvestigationState.ANALYZING: {
            InvestigationState.CANDIDATES_GENERATED,
            InvestigationState.FAILED,
        },
        InvestigationState.CANDIDATES_GENERATED: {
            InvestigationState.COMPLETED,
            InvestigationState.FAILED,
        },
        InvestigationState.COMPLETED: set(),  # Terminal
        InvestigationState.FAILED: set(),     # Terminal
    }

    def __init__(self, initial_state: InvestigationState = InvestigationState.CREATED):
        self._state = initial_state

    @property
    def current_state(self) -> InvestigationState:
        return self._state

    def can_transition(self, to_state: InvestigationState) -> bool:
        """Check whether transition to target state is legally permissible."""
        allowed = self.VALID_TRANSITIONS.get(self._state, set())
        return to_state in allowed

    def transition(self, to_state: InvestigationState) -> InvestigationState:
        """Execute state transition or raise InvalidStateTransitionError."""
        if not self.can_transition(to_state):
            raise InvalidStateTransitionError(
                f"Illegal state transition from '{self._state.value}' to '{to_state.value}'."
            )
        self._state = to_state
        return self._state
