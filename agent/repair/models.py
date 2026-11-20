"""Devaura Phase 5 Domain Contracts & Pydantic Schemas.

Defines validated data structures for RepairContext, RepairPlan,
PatchResult, PatchRisk, RepairApproval, and Phase 6 Handoff contract.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RepairState(str, Enum):
    CREATED = "CREATED"
    CONTEXT_BUILDING = "CONTEXT_BUILDING"
    CONTEXT_READY = "CONTEXT_READY"
    PLANNING = "PLANNING"
    PLAN_READY = "PLAN_READY"
    PATCH_GENERATING = "PATCH_GENERATING"
    PATCH_READY = "PATCH_READY"
    RISK_ANALYZED = "RISK_ANALYZED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    APPLYING = "APPLYING"
    PATCH_APPLIED_PENDING_VERIFICATION = "PATCH_APPLIED_PENDING_VERIFICATION"

    # Terminal failure states
    REPAIR_BLOCKED = "REPAIR_BLOCKED"
    REPAIR_BLOCKED_INSUFFICIENT_EVIDENCE = "REPAIR_BLOCKED_INSUFFICIENT_EVIDENCE"
    PLAN_FAILED = "PLAN_FAILED"
    PATCH_FAILED = "PATCH_FAILED"
    RISK_BLOCKED = "RISK_BLOCKED"
    REJECTED = "REJECTED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    PATCH_CHANGED = "PATCH_CHANGED"
    APPLICATION_FAILED = "APPLICATION_FAILED"


class PatchRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INVALIDATED = "INVALIDATED"


class ProposedChange(BaseModel):
    """Specific atomic code modification proposed by the repair planner."""
    model_config = ConfigDict(extra="ignore")

    file: str
    location: str
    change_type: str = "DEFENSIVE_GUARD"
    rationale: str
    evidence_ids: List[str] = Field(default_factory=list)
    expected_effect: str


class RepairContext(BaseModel):
    """Structured, validated context derived from Phase 4 investigation."""
    model_config = ConfigDict(extra="ignore")

    repair_id: str
    investigation_id: str
    repository_id: str
    repository_path: str
    repository_revision: str = "HEAD"
    failure: Dict[str, Any] = Field(default_factory=dict)
    selected_root_cause: Dict[str, Any] = Field(default_factory=dict)
    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    affected_files: List[str] = Field(default_factory=list)
    affected_symbols: List[str] = Field(default_factory=list)
    affected_lines: Dict[str, List[int]] = Field(default_factory=dict)
    related_tests: List[str] = Field(default_factory=list)
    recent_changes: List[Dict[str, Any]] = Field(default_factory=list)
    unresolved_evidence: List[str] = Field(default_factory=list)
    forbidden_assumptions: List[str] = Field(default_factory=list)
    repair_scope: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class RepairPlan(BaseModel):
    """Structured, evidence-backed repair strategy."""
    model_config = ConfigDict(extra="ignore")

    repair_id: str
    investigation_id: str
    objective: str
    root_cause: str
    affected_files: List[str] = Field(default_factory=list)
    affected_symbols: List[str] = Field(default_factory=list)
    proposed_changes: List[ProposedChange] = Field(default_factory=list)
    tests_to_run: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    confidence: float = 0.5
    created_at: datetime = Field(default_factory=utc_now)


class PatchResult(BaseModel):
    """Generated code patch and deterministic integrity hash."""
    model_config = ConfigDict(extra="ignore")

    status: str = "GENERATED"
    unified_diff: str
    patch_hash: str
    changed_files: List[str] = Field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    explanation: str = ""
    assumptions: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)
    model_metadata: Dict[str, Any] = Field(default_factory=dict)


class PatchRiskFinding(BaseModel):
    """Single risk finding produced by static patch analysis."""
    model_config = ConfigDict(extra="ignore")

    category: str
    description: str
    is_blocking: bool = False
    severity: str = "MEDIUM"


class PatchRisk(BaseModel):
    """Multi-dimensional risk analysis of a proposed patch."""
    model_config = ConfigDict(extra="ignore")

    score: float = 0.0
    level: PatchRiskLevel = PatchRiskLevel.LOW
    findings: List[PatchRiskFinding] = Field(default_factory=list)
    blocking_findings: List[str] = Field(default_factory=list)
    rationale: str = ""
    analyzed_at: datetime = Field(default_factory=utc_now)


class RepairApproval(BaseModel):
    """Cryptographically bound human authorization record."""
    model_config = ConfigDict(extra="ignore")

    repair_id: str
    patch_hash: str
    approved_by: str
    approved_at: datetime = Field(default_factory=utc_now)
    status: ApprovalStatus = ApprovalStatus.APPROVED
    approval_token: str
    rejection_reason: Optional[str] = None


class RepairExecutionResult(BaseModel):
    """Phase 6 Handoff Contract: Patch applied in sandbox awaiting verification."""
    model_config = ConfigDict(extra="ignore")

    repair_id: str
    investigation_id: str
    repository: str
    base_revision: str
    workspace_id: str
    isolated_path: str
    patch_hash: str
    changed_files: List[str] = Field(default_factory=list)
    diff: str
    application_status: str = "APPLIED"
    verification_status: str = "PENDING"
