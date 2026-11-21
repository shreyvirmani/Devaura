"""Pull Request State Machine.

Enforces deterministic transitions for the Devaura Phase 7 PR Orchestration lifecycle:
PR_ELIGIBILITY_CHECK -> PR_CONTEXT_READY -> GIT_STATE_VALIDATED ->
BRANCH_READY -> COMMIT_READY -> PR_METADATA_READY -> AWAITING_PR_APPROVAL ->
PR_APPROVED -> BRANCH_PUSHING -> BRANCH_PUSHED -> PR_CREATING -> PR_CREATED -> PR_MONITORING.
"""

from typing import Set, Union
from agent.pr.models import PRState


class InvalidPRStateTransitionError(ValueError):
    """Raised when an illegal pull request state transition is attempted."""
    pass


class PullRequestStateMachine:
    """Finite State Machine governing PR preparation, approval, push, and creation."""

    VALID_TRANSITIONS: dict[PRState, Set[PRState]] = {
        PRState.PR_ELIGIBILITY_CHECK: {
            PRState.PR_CONTEXT_READY,
            PRState.PR_BLOCKED,
            PRState.PR_BLOCKED_UNVERIFIED,
            PRState.PR_BLOCKED_PATCH_CHANGED,
            PRState.PR_BLOCKED_AUTH,
            PRState.PR_BLOCKED_SECURITY,
        },
        PRState.PR_CONTEXT_READY: {
            PRState.GIT_STATE_VALIDATED,
            PRState.PR_BLOCKED_GIT_STATE,
            PRState.PR_BLOCKED_SECURITY,
            PRState.PR_BLOCKED,
        },
        PRState.GIT_STATE_VALIDATED: {
            PRState.BRANCH_READY,
            PRState.BRANCH_CREATION_FAILED,
            PRState.PR_BLOCKED_GIT_STATE,
            PRState.PR_BLOCKED_SECURITY,
        },
        PRState.BRANCH_READY: {
            PRState.COMMIT_READY,
            PRState.COMMIT_FAILED,
            PRState.PR_BLOCKED_COMMIT_MISMATCH,
            PRState.PR_BLOCKED_SECURITY,
        },
        PRState.COMMIT_READY: {
            PRState.PR_METADATA_READY,
            PRState.PR_BLOCKED,
            PRState.PR_ALREADY_EXISTS,
        },
        PRState.PR_METADATA_READY: {
            PRState.AWAITING_PR_APPROVAL,
            PRState.PR_ALREADY_EXISTS,
            PRState.PR_BLOCKED,
        },
        PRState.AWAITING_PR_APPROVAL: {
            PRState.PR_APPROVED,
            PRState.PR_APPROVAL_REJECTED,
            PRState.PR_BLOCKED_PATCH_CHANGED,
            PRState.PR_BLOCKED,
        },
        PRState.PR_APPROVED: {
            PRState.BRANCH_PUSHING,
            PRState.PR_BLOCKED_AUTH,
            PRState.PR_BLOCKED_PATCH_CHANGED,
            PRState.PR_BLOCKED_GIT_STATE,
            PRState.PUSH_FAILED,
            PRState.PR_BLOCKED,
        },
        PRState.BRANCH_PUSHING: {
            PRState.BRANCH_PUSHED,
            PRState.PUSH_FAILED,
            PRState.PR_BLOCKED_AUTH,
            PRState.PR_BLOCKED_GIT_STATE,
        },
        PRState.BRANCH_PUSHED: {
            PRState.PR_CREATING,
            PRState.PR_CREATION_FAILED,
            PRState.PR_ALREADY_EXISTS,
            PRState.PR_BLOCKED_AUTH,
        },
        PRState.PR_CREATING: {
            PRState.PR_CREATED,
            PRState.PR_CREATION_FAILED,
            PRState.PR_ALREADY_EXISTS,
            PRState.PR_BLOCKED_AUTH,
        },
        PRState.PR_CREATED: {
            PRState.PR_MONITORING,
        },
        PRState.PR_MONITORING: {
            PRState.PR_MONITORING,  # Self-loop for continuous polling
        },
        # Terminal / Failure States
        PRState.PR_BLOCKED: set(),
        PRState.PR_BLOCKED_UNVERIFIED: set(),
        PRState.PR_BLOCKED_PATCH_CHANGED: set(),
        PRState.PR_BLOCKED_COMMIT_MISMATCH: set(),
        PRState.PR_BLOCKED_AUTH: set(),
        PRState.PR_BLOCKED_GIT_STATE: set(),
        PRState.PR_BLOCKED_SECURITY: set(),
        PRState.PR_APPROVAL_REJECTED: set(),
        PRState.BRANCH_CREATION_FAILED: set(),
        PRState.COMMIT_FAILED: set(),
        PRState.PUSH_FAILED: set(),
        PRState.PR_CREATION_FAILED: set(),
        PRState.PR_ALREADY_EXISTS: set(),
    }

    def __init__(self, initial_state: Union[PRState, str] = PRState.PR_ELIGIBILITY_CHECK):
        if isinstance(initial_state, str):
            self._state = PRState(initial_state)
        else:
            self._state = initial_state

    @property
    def current_state(self) -> PRState:
        return self._state

    def can_transition(self, to_state: Union[PRState, str]) -> bool:
        """Check whether transition to target state is legally permissible."""
        target = PRState(to_state) if isinstance(to_state, str) else to_state
        allowed = self.VALID_TRANSITIONS.get(self._state, set())
        return target in allowed

    def transition(self, to_state: Union[PRState, str]) -> PRState:
        """Advance state machine to target state or raise InvalidPRStateTransitionError."""
        target = PRState(to_state) if isinstance(to_state, str) else to_state
        if not self.can_transition(target):
            raise InvalidPRStateTransitionError(
                f"Invalid PR state transition from '{self._state.value}' to '{target.value}'."
            )
        self._state = target
        return self._state
