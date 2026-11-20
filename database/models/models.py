import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.connection import Base


def utc_now() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


class AgentState(str, Enum):
    IDLE = "IDLE"
    INVESTIGATING = "INVESTIGATING"
    DIAGNOSED = "DIAGNOSED"
    PLAN_READY = "PLAN_READY"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    REPAIRING = "REPAIRING"
    VERIFYING = "VERIFYING"
    REPAIR_FAILED = "REPAIR_FAILED"
    REPAIR_SUCCEEDED = "REPAIR_SUCCEEDED"
    REVIEWING = "REVIEWING"
    WAITING_FOR_PR_APPROVAL = "WAITING_FOR_PR_APPROVAL"
    PR_CREATED = "PR_CREATED"
    COMPLETED = "COMPLETED"


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


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    CONTROLLED = "CONTROLLED"
    DANGEROUS = "DANGEROUS"


class CheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_AVAILABLE = "not_available"
    NOT_RUN = "not_run"


# 1. User Model
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


# 2. Repository Model
class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), default="github", nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    clone_url: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation", back_populates="repository", cascade="all, delete-orphan", lazy="selectin"
    )
    pull_requests: Mapped[List["PullRequest"]] = relationship(
        "PullRequest", back_populates="repository", cascade="all, delete-orphan", lazy="selectin"
    )


# 3. MCP Server Model
class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    transport: Mapped[str] = mapped_column(String(50), default="stdio", nullable=False)  # stdio, sse, http
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="disconnected", nullable=False)  # connected, disconnected, error
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tools: Mapped[List["MCPTool"]] = relationship(
        "MCPTool", back_populates="server", cascade="all, delete-orphan", lazy="selectin"
    )


# 4. MCP Tool Model
class MCPTool(Base):
    __tablename__ = "mcp_tools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    server_id: Mapped[str] = mapped_column(String(36), ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    risk_level: Mapped[str] = mapped_column(String(20), default=RiskLevel.SAFE.value, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    server: Mapped["MCPServer"] = relationship("MCPServer", back_populates="tools")


# 5. Investigation Model
class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="issue", nullable=False)  # issue, pr, ci_failure, test_failure
    source_id: Mapped[str] = mapped_column(String(100), default="1", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=InvestigationState.CREATED.value, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    failure_type: Mapped[str] = mapped_column(String(50), default=FailureType.UNKNOWN.value, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failed_tests: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    ci_run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    evidence_sufficiency: Mapped[str] = mapped_column(String(50), default=EvidenceSufficiency.INSUFFICIENT.value, nullable=False)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="investigations", lazy="selectin")
    evidence_items: Mapped[List["Evidence"]] = relationship(
        "Evidence", back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )
    root_cause_candidates: Mapped[List["RootCauseCandidate"]] = relationship(
        "RootCauseCandidate", back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )
    investigation_steps: Mapped[List["InvestigationStep"]] = relationship(
        "InvestigationStep", back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )
    repair_plans: Mapped[List["RepairPlan"]] = relationship(
        "RepairPlan", back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )
    repair_attempts: Mapped[List["RepairAttempt"]] = relationship(
        "RepairAttempt", back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )
    tool_executions: Mapped[List["ToolExecution"]] = relationship(
        "ToolExecution", back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )


# 6. Evidence Model
class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default=EvidenceSource.CODE_INTELLIGENCE.value, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    repository_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    symbol_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    line_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    line_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    relevance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="evidence_items")


# 6b. Root Cause Candidate Model
class RootCauseCandidate(Base):
    __tablename__ = "root_cause_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    affected_symbols: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    affected_files: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    contradicting_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="root_cause_candidates")


# 6c. Investigation Step Model (Execution Timeline & Audit Trail)
class InvestigationStep(Base):
    __tablename__ = "investigation_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tool_input: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    tool_output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    observation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="investigation_steps")


# Backward-compatible alias
InvestigationEvidence = Evidence


# 7. Repair Plan Model
class RepairPlan(Base):
    __tablename__ = "repair_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    plan: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="repair_plans")


# 8. Repair Attempt Model
class RepairAttempt(Base):
    __tablename__ = "repair_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="started", nullable=False)
    patch: Mapped[str] = mapped_column(Text, default="", nullable=False)
    test_results: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="repair_attempts", lazy="selectin")
    verification_runs: Mapped[List["VerificationRun"]] = relationship(
        "VerificationRun", back_populates="repair_attempt", cascade="all, delete-orphan", lazy="selectin"
    )


# 9. Verification Run Model
class VerificationRun(Base):
    __tablename__ = "verification_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_attempt_id: Mapped[str] = mapped_column(String(36), ForeignKey("repair_attempts.id", ondelete="CASCADE"), nullable=False)
    test_status: Mapped[str] = mapped_column(String(20), default=CheckStatus.NOT_RUN.value, nullable=False)
    lint_status: Mapped[str] = mapped_column(String(20), default=CheckStatus.NOT_RUN.value, nullable=False)
    typecheck_status: Mapped[str] = mapped_column(String(20), default=CheckStatus.NOT_RUN.value, nullable=False)
    security_status: Mapped[str] = mapped_column(String(20), default=CheckStatus.NOT_RUN.value, nullable=False)
    test_output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repair_attempt: Mapped["RepairAttempt"] = relationship("RepairAttempt", back_populates="verification_runs")


# 10. Tool Execution Model
class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="SET NULL"), nullable=True)
    server: Mapped[str] = mapped_column(String(100), nullable=False)
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    input_data: Mapped[dict[str, Any]] = mapped_column("input", JSON, default=dict)
    output_data: Mapped[dict[str, Any]] = mapped_column("output", JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    investigation: Mapped[Optional["Investigation"]] = relationship("Investigation", back_populates="tool_executions")


# 11. Pull Request Model
class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    provider_pr_id: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="pull_requests")
