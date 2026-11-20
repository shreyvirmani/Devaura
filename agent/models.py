"""Devaura Agent & Investigation Models.

Defines data contracts for investigation requests, normalized evidence,
stack frames, test failures, root cause candidates, and investigation reports.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FailureType(str, Enum):
    TEST_FAILURE = "TEST_FAILURE"
    BUILD_FAILURE = "BUILD_FAILURE"
    TYPECHECK_FAILURE = "TYPECHECK_FAILURE"
    LINT_FAILURE = "LINT_FAILURE"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    CI_FAILURE = "CI_FAILURE"
    SECURITY_FINDING = "SECURITY_FINDING"
    USER_REPORTED_BUG = "USER_REPORTED_BUG"
    UNKNOWN = "UNKNOWN"


class InvestigationState(str, Enum):
    CREATED = "CREATED"
    INVESTIGATING = "INVESTIGATING"  # backward-compatible alias
    COLLECTING_EVIDENCE = "COLLECTING_EVIDENCE"
    EVIDENCE_READY = "EVIDENCE_READY"
    ANALYZING = "ANALYZING"
    CANDIDATES_GENERATED = "CANDIDATES_GENERATED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EvidenceSource(str, Enum):
    CODE_INTELLIGENCE = "CODE_INTELLIGENCE"
    GIT = "GIT"
    TEST = "TEST"
    CI = "CI"
    STACK_TRACE = "STACK_TRACE"
    LOG = "LOG"
    USER_REPORT = "USER_REPORT"
    MCP = "MCP"


class EvidenceType(str, Enum):
    SYMBOL = "SYMBOL"
    CALL_RELATIONSHIP = "CALL_RELATIONSHIP"
    IMPORT_RELATIONSHIP = "IMPORT_RELATIONSHIP"
    TEST_RELATIONSHIP = "TEST_RELATIONSHIP"
    STACK_FRAME = "STACK_FRAME"
    COMMIT = "COMMIT"
    BLAME = "BLAME"
    CODE_CHANGE = "CODE_CHANGE"
    TEST_FAILURE = "TEST_FAILURE"
    ERROR_MESSAGE = "ERROR_MESSAGE"
    LOG_ENTRY = "LOG_ENTRY"


class EvidenceSufficiency(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    PARTIALLY_SUFFICIENT = "PARTIALLY_SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"


class ParsedStackFrame(BaseModel):
    """Deterministic representation of a single stack frame."""
    model_config = ConfigDict(extra="ignore")

    file: str
    line: int
    function: str
    module: Optional[str] = None
    code_context: Optional[str] = None
    is_application_code: bool = True
    symbol_id: Optional[str] = None
    resolution_status: str = ResolutionStatus.UNRESOLVED.value


class ParsedStackTrace(BaseModel):
    """Deterministic representation of a parsed stack trace."""
    model_config = ConfigDict(extra="ignore")

    raw_trace: str
    exception_type: str = "UnknownException"
    error_message: str = ""
    frames: List[ParsedStackFrame] = Field(default_factory=list)
    failing_frame: Optional[ParsedStackFrame] = None
    caller_frame: Optional[ParsedStackFrame] = None


class ParsedTestFailure(BaseModel):
    """Deterministic representation of a test failure."""
    model_config = ConfigDict(extra="ignore")

    test_file: str
    test_function: str
    assertion: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    exception: Optional[str] = None
    stack_trace: Optional[str] = None
    tested_symbol_id: Optional[str] = None
    tested_file: Optional[str] = None
    confidence: float = 1.0


class InvestigationRequest(BaseModel):
    """Standardized investigation initiation request."""
    model_config = ConfigDict(extra="ignore")

    investigation_id: Optional[str] = None
    repository_id: str
    issue_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    failure_type: FailureType = FailureType.UNKNOWN
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    failed_tests: List[Any] = Field(default_factory=list)
    ci_run_id: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = "main"
    created_at: datetime = Field(default_factory=utc_now)
    status: InvestigationState = InvestigationState.CREATED


class NormalizedEvidence(BaseModel):
    """Normalized atomic piece of collected evidence with full provenance."""
    model_config = ConfigDict(extra="ignore")

    evidence_id: str
    investigation_id: str
    source: EvidenceSource
    type: EvidenceType
    content: str
    repository_path: Optional[str] = None
    symbol_id: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    commit_sha: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RootCauseCandidateSchema(BaseModel):
    """Diagnosed root-cause hypothesis backed by traceable evidence."""
    model_config = ConfigDict(extra="ignore")

    candidate_id: str
    title: str
    description: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    affected_symbols: List[str] = Field(default_factory=list)
    affected_files: List[str] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    reasoning: str = ""


class InvestigationReport(BaseModel):
    """Final explainable investigation outcome delivered to user and future planner."""
    model_config = ConfigDict(extra="ignore")

    investigation_id: str
    repository_id: str
    status: InvestigationState
    evidence_sufficiency: EvidenceSufficiency
    summary: str
    root_cause_candidates: List[RootCauseCandidateSchema] = Field(default_factory=list)
    top_candidate: Optional[RootCauseCandidateSchema] = None
    overall_confidence: float = 0.0
    ranked_evidence: List[NormalizedEvidence] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    recommended_next_steps: List[str] = Field(default_factory=list)
    iteration_count: int = 0
    duration_ms: float = 0.0
