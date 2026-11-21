"""Devaura Phase 7 Pull Request Domain Models & Contracts.

Defines validated data structures for PRContext, PRState, PRApproval,
PRPreparationResult, and audit contracts.
"""

from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PRState(str, Enum):
    # Active operational states
    PR_ELIGIBILITY_CHECK = "PR_ELIGIBILITY_CHECK"
    PR_CONTEXT_READY = "PR_CONTEXT_READY"
    GIT_STATE_VALIDATED = "GIT_STATE_VALIDATED"
    BRANCH_READY = "BRANCH_READY"
    COMMIT_READY = "COMMIT_READY"
    PR_METADATA_READY = "PR_METADATA_READY"
    AWAITING_PR_APPROVAL = "AWAITING_PR_APPROVAL"
    PR_APPROVED = "PR_APPROVED"
    BRANCH_PUSHING = "BRANCH_PUSHING"
    BRANCH_PUSHED = "BRANCH_PUSHED"
    PR_CREATING = "PR_CREATING"
    PR_CREATED = "PR_CREATED"
    PR_MONITORING = "PR_MONITORING"

    # Terminal failure states
    PR_BLOCKED = "PR_BLOCKED"
    PR_BLOCKED_UNVERIFIED = "PR_BLOCKED_UNVERIFIED"
    PR_BLOCKED_PATCH_CHANGED = "PR_BLOCKED_PATCH_CHANGED"
    PR_BLOCKED_COMMIT_MISMATCH = "PR_BLOCKED_COMMIT_MISMATCH"
    PR_BLOCKED_AUTH = "PR_BLOCKED_AUTH"
    PR_BLOCKED_GIT_STATE = "PR_BLOCKED_GIT_STATE"
    PR_BLOCKED_SECURITY = "PR_BLOCKED_SECURITY"
    PR_APPROVAL_REJECTED = "PR_APPROVAL_REJECTED"
    BRANCH_CREATION_FAILED = "BRANCH_CREATION_FAILED"
    COMMIT_FAILED = "COMMIT_FAILED"
    PUSH_FAILED = "PUSH_FAILED"
    PR_CREATION_FAILED = "PR_CREATION_FAILED"
    PR_ALREADY_EXISTS = "PR_ALREADY_EXISTS"


class PRApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INVALIDATED = "INVALIDATED"


class PRContext(BaseModel):
    """Structured context derived from Phase 6 VerifiedRepairResult for PR creation."""
    model_config = ConfigDict(extra="ignore")

    repair_id: str
    investigation_id: str
    repository: str
    owner: str
    repo: str
    base_branch: str = "main"
    base_revision: str
    repair_branch: str
    commit_message: str
    pr_title: str
    pr_body: str
    changed_files: List[str] = Field(default_factory=list)
    patch_hash: str
    verification_id: str
    verification_summary: Dict[str, Any] = Field(default_factory=dict)
    root_cause_summary: str = ""
    repair_summary: str = ""
    risk_summary: Dict[str, Any] = Field(default_factory=dict)
    attempt_count: int = 1
    created_at: datetime = Field(default_factory=utc_now)


class PRApproval(BaseModel):
    """Cryptographically bound human authorization record for PR creation."""
    model_config = ConfigDict(extra="ignore")

    repair_id: str
    patch_hash: str
    base_revision: str
    repair_branch: str
    repository: str
    operation: str = "CREATE_PULL_REQUEST"
    approved_by: str
    approved_at: datetime = Field(default_factory=utc_now)
    approval_token: str
    status: PRApprovalStatus = PRApprovalStatus.APPROVED
    rejection_reason: Optional[str] = None


class PRPreparationResult(BaseModel):
    """Result of PR preparation phase awaiting human authorization."""
    model_config = ConfigDict(extra="ignore")

    repair_id: str
    status: PRState = PRState.AWAITING_PR_APPROVAL
    context: PRContext
    approval_required: bool = True
    approval_token: Optional[str] = None
    message: str = "PR context ready. Explicit human approval required before push and PR creation."
