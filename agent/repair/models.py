"""Devaura Phase 5 Domain Contracts & Pydantic Schemas.

Defines validated data structures for RepairContext, RepairPlan,
PatchResult, PatchRisk, RepairApproval, and Phase 6 Handoff contract.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
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

    # Phase 6 Verification & Bounded Loop States
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    ANALYZING_FAILURE = "ANALYZING_FAILURE"
    REPAIR_RETRY_ELIGIBLE = "REPAIR_RETRY_ELIGIBLE"

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
    REPAIR_EXHAUSTED = "REPAIR_EXHAUSTED"
    NO_PROGRESS = "NO_PROGRESS"
    VERIFICATION_BLOCKED = "VERIFICATION_BLOCKED"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"


class CheckType(str, Enum):
    TESTS = "TESTS"
    LINT = "LINT"
    TYPECHECK = "TYPECHECK"


class CheckStatus(str, Enum):
    NOT_RUN = "NOT_RUN"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
    BLOCKED = "BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"


class OverallVerificationStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"


class FailureClassification(str, Enum):
    CODE_FAILURE = "CODE_FAILURE"
    TEST_FAILURE = "TEST_FAILURE"
    LINT_FAILURE = "LINT_FAILURE"
    TYPECHECK_FAILURE = "TYPECHECK_FAILURE"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    TIMEOUT = "TIMEOUT_ERROR"
    PERMISSION_FAILURE = "PERMISSION_FAILURE"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    SECURITY_BLOCK = "SECURITY_BLOCK"
    UNKNOWN = "UNKNOWN"


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


class TestFailure(BaseModel):
    """Normalized structured failure from test/lint/typecheck execution."""
    model_config = ConfigDict(extra="ignore")

    test_name: str
    file: str
    line: Optional[int] = None
    error_type: str = "AssertionError"
    message: str = ""
    traceback: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    confidence: float = 1.0

    @property
    def exception_type(self) -> str:
        return self.error_type


class VerificationCheck(BaseModel):
    """Execution outcome of a single verification check (tests, lint, typecheck)."""
    model_config = ConfigDict(extra="ignore")

    check_type: CheckType
    command: str
    status: CheckStatus = CheckStatus.NOT_RUN
    exit_code: int = 0
    duration_ms: float = 0.0
    stdout: str = ""
    stderr: str = ""
    parsed_errors: List[TestFailure] = Field(default_factory=list)
    resource_usage: Dict[str, Any] = Field(default_factory=dict)


class FailureSignature(BaseModel):
    """Deterministic cryptographic fingerprint of a failure condition."""
    model_config = ConfigDict(extra="ignore")

    signature_hash: str
    check_type: str
    error_summary: str
    file_path: str
    line_number: Optional[int] = None
    test_name: Optional[str] = None


class FailureAnalysisReport(BaseModel):
    """Failure diagnosis for verification failure informing retry decisions."""
    model_config = ConfigDict(extra="ignore")

    failure_type: FailureClassification = FailureClassification.CODE_FAILURE
    failure_signature: str
    root_cause_summary: str
    affected_files: List[str] = Field(default_factory=list)
    affected_symbols: List[str] = Field(default_factory=list)
    can_retry: bool = True
    retry_block_reason: Optional[str] = None
    suggested_changes: List[str] = Field(default_factory=list)


class VerificationRun(BaseModel):
    """Comprehensive record of a verification execution across configured checks."""
    model_config = ConfigDict(extra="ignore")

    verification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repair_id: str
    attempt_number: int = 1
    workspace_id: str
    commit_or_base_revision: str = "HEAD"
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    status: OverallVerificationStatus = OverallVerificationStatus.PARTIAL
    checks: List[VerificationCheck] = Field(default_factory=list)
    overall_result: str = "FAILED"
    failure_analysis: Optional[FailureAnalysisReport] = None


class RepairAttemptInfo(BaseModel):
    """Audit record for an attempt in the bounded repair loop."""
    model_config = ConfigDict(extra="ignore")

    attempt_number: int
    patch_hash: str
    unified_diff: str
    approval_status: str
    verification_status: str
    created_at: datetime = Field(default_factory=utc_now)


class VerifiedRepairResult(BaseModel):
    """Phase 7 Handoff Contract: Verified repair ready for PR preparation."""
    model_config = ConfigDict(extra="ignore")

    repair_id: str
    investigation_id: str
    repository: str
    base_revision: str
    final_workspace_id: str
    final_patch_hash: str
    changed_files: List[str] = Field(default_factory=list)
    verification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    verification_status: str = "VERIFIED"
    checks: List[Dict[str, Any]] = Field(default_factory=list)
    attempts: List[Dict[str, Any]] = Field(default_factory=list)
    final_diff: str

