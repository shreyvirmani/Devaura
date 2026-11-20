"""Repair State Machine.

Enforces deterministic transitions for the Devaura repair lifecycle:
CREATED -> CONTEXT_BUILDING -> CONTEXT_READY -> PLANNING -> PLAN_READY ->
PATCH_GENERATING -> PATCH_READY -> RISK_ANALYZED -> AWAITING_APPROVAL ->
APPROVED -> APPLYING -> PATCH_APPLIED_PENDING_VERIFICATION
"""

from typing import Set, Union
from agent.repair.models import RepairState


class InvalidRepairStateTransitionError(ValueError):
    """Raised when an illegal repair state transition is attempted."""
    pass


class RepairStateMachine:
    """Finite State Machine guarding repair workflow and patch safety."""

    VALID_TRANSITIONS: dict[RepairState, Set[RepairState]] = {
        RepairState.CREATED: {
            RepairState.CONTEXT_BUILDING,
            RepairState.REPAIR_BLOCKED,
            RepairState.REPAIR_BLOCKED_INSUFFICIENT_EVIDENCE,
        },
        RepairState.CONTEXT_BUILDING: {
            RepairState.CONTEXT_READY,
            RepairState.REPAIR_BLOCKED,
            RepairState.REPAIR_BLOCKED_INSUFFICIENT_EVIDENCE,
        },
        RepairState.CONTEXT_READY: {
            RepairState.PLANNING,
            RepairState.REPAIR_BLOCKED,
        },
        RepairState.PLANNING: {
            RepairState.PLAN_READY,
            RepairState.PLAN_FAILED,
            RepairState.REPAIR_BLOCKED,
        },
        RepairState.PLAN_READY: {
            RepairState.PATCH_GENERATING,
            RepairState.REPAIR_BLOCKED,
        },
        RepairState.PATCH_GENERATING: {
            RepairState.PATCH_READY,
            RepairState.PATCH_FAILED,
            RepairState.REPAIR_BLOCKED,
        },
        RepairState.PATCH_READY: {
            RepairState.RISK_ANALYZED,
            RepairState.RISK_BLOCKED,
            RepairState.REPAIR_BLOCKED,
        },
        RepairState.RISK_ANALYZED: {
            RepairState.AWAITING_APPROVAL,
            RepairState.RISK_BLOCKED,
            RepairState.REPAIR_BLOCKED,
        },
        RepairState.AWAITING_APPROVAL: {
            RepairState.APPROVED,
            RepairState.REJECTED,
            RepairState.APPROVAL_EXPIRED,
            RepairState.REPAIR_BLOCKED,
        },
        RepairState.APPROVED: {
            RepairState.APPLYING,
            RepairState.PATCH_CHANGED,
            RepairState.REJECTED,
            RepairState.APPLICATION_FAILED,
        },
        RepairState.APPLYING: {
            RepairState.PATCH_APPLIED_PENDING_VERIFICATION,
            RepairState.APPLICATION_FAILED,
            RepairState.PATCH_CHANGED,
        },
        RepairState.PATCH_APPLIED_PENDING_VERIFICATION: set(),  # Terminal in Phase 5
        # Failure / Terminal States
        RepairState.REPAIR_BLOCKED: set(),
        RepairState.REPAIR_BLOCKED_INSUFFICIENT_EVIDENCE: set(),
        RepairState.PLAN_FAILED: set(),
        RepairState.PATCH_FAILED: set(),
        RepairState.RISK_BLOCKED: set(),
        RepairState.REJECTED: set(),
        RepairState.APPROVAL_EXPIRED: set(),
        RepairState.PATCH_CHANGED: set(),
        RepairState.APPLICATION_FAILED: set(),
    }

    def __init__(self, initial_state: Union[RepairState, str] = RepairState.CREATED):
        if isinstance(initial_state, str):
            self._state = RepairState(initial_state)
        else:
            self._state = initial_state

    @property
    def current_state(self) -> RepairState:
        return self._state

    def can_transition(self, to_state: Union[RepairState, str]) -> bool:
        """Check whether transition to target state is legally permissible."""
        target = RepairState(to_state) if isinstance(to_state, str) else to_state
        allowed = self.VALID_TRANSITIONS.get(self._state, set())
        return target in allowed

    def transition(self, to_state: Union[RepairState, str]) -> RepairState:
        """Execute state transition or raise InvalidRepairStateTransitionError."""
        target = RepairState(to_state) if isinstance(to_state, str) else to_state
        if not self.can_transition(target):
            raise InvalidRepairStateTransitionError(
                f"Illegal repair state transition from '{self._state.value}' to '{target.value}'."
            )
        self._state = target
        return self._state
