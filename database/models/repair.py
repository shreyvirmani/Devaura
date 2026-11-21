"""Devaura Phase 5 Repair Relational Database Models.

Persists repair contexts, plans, patches, risk analyses, approvals,
isolated workspaces, and execution audit events.
"""

from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any, Dict, List, Optional
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


class RepairRecord(Base):
    __tablename__ = "repairs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(60), default=RepairState.CREATED.value, nullable=False, index=True)
    target_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    base_revision: Mapped[str] = mapped_column(String(64), default="HEAD", nullable=False)
    current_attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    latest_verification_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    context: Mapped[Optional["RepairContextRecord"]] = relationship(
        "RepairContextRecord", back_populates="repair", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    plan: Mapped[Optional["RepairPlanRecord"]] = relationship(
        "RepairPlanRecord", back_populates="repair", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    patch: Mapped[Optional["PatchRecord"]] = relationship(
        "PatchRecord", back_populates="repair", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    risk: Mapped[Optional["PatchRiskRecord"]] = relationship(
        "PatchRiskRecord", back_populates="repair", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    approval: Mapped[Optional["RepairApprovalRecord"]] = relationship(
        "RepairApprovalRecord", back_populates="repair", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    workspace: Mapped[Optional["RepairWorkspaceRecord"]] = relationship(
        "RepairWorkspaceRecord", back_populates="repair", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    events: Mapped[List["RepairEventRecord"]] = relationship(
        "RepairEventRecord", back_populates="repair", cascade="all, delete-orphan", lazy="selectin"
    )
    attempts: Mapped[List["RepairAttemptRecord"]] = relationship(
        "RepairAttemptRecord", back_populates="repair", cascade="all, delete-orphan", lazy="selectin"
    )
    verification_runs: Mapped[List["VerificationRunRecord"]] = relationship(
        "VerificationRunRecord", back_populates="repair", cascade="all, delete-orphan", lazy="selectin"
    )
    failure_signatures: Mapped[List["FailureSignatureRecord"]] = relationship(
        "FailureSignatureRecord", back_populates="repair", cascade="all, delete-orphan", lazy="selectin"
    )
    pull_request: Mapped[Optional["PullRequestRecord"]] = relationship(
        "PullRequestRecord", back_populates="repair", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )


class RepairContextRecord(Base):
    __tablename__ = "repair_contexts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), unique=True, nullable=False)
    investigation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    affected_files: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    affected_symbols: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    supporting_evidence_ids: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    related_tests: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    context_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validation_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repair: Mapped["RepairRecord"] = relationship("RepairRecord", back_populates="context")


class RepairPlanRecord(Base):
    __tablename__ = "repair_plans_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), unique=True, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_changes: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    tests_to_run: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    risks: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    assumptions: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repair: Mapped["RepairRecord"] = relationship("RepairRecord", back_populates="plan")


class PatchRecord(Base):
    __tablename__ = "repair_patches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), unique=True, nullable=False)
    unified_diff: Mapped[str] = mapped_column(Text, nullable=False)
    patch_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    changed_files: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    lines_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lines_removed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    model_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repair: Mapped["RepairRecord"] = relationship("RepairRecord", back_populates="patch")


class PatchRiskRecord(Base):
    __tablename__ = "patch_risks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), unique=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    level: Mapped[str] = mapped_column(String(20), default=PatchRiskLevel.LOW.value, nullable=False)
    findings: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    blocking_findings: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repair: Mapped["RepairRecord"] = relationship("RepairRecord", back_populates="risk")


class RepairApprovalRecord(Base):
    __tablename__ = "repair_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), unique=True, nullable=False)
    patch_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=ApprovalStatus.PENDING.value, nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approval_token: Mapped[str] = mapped_column(String(64), default=lambda: str(uuid.uuid4()), nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repair: Mapped["RepairRecord"] = relationship("RepairRecord", back_populates="approval")


class RepairWorkspaceRecord(Base):
    __tablename__ = "repair_workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), unique=True, nullable=False)
    isolated_path: Mapped[str] = mapped_column(String(500), nullable=False)
    base_revision: Mapped[str] = mapped_column(String(64), default="HEAD", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="CREATED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repair: Mapped["RepairRecord"] = relationship("RepairRecord", back_populates="workspace")


class RepairEventRecord(Base):
    __tablename__ = "repair_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repair: Mapped["RepairRecord"] = relationship("RepairRecord", back_populates="events")


class RepairAttemptRecord(Base):
    __tablename__ = "repair_attempts_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    patch_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    unified_diff: Mapped[str] = mapped_column(Text, default="", nullable=False)
    approval_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="STARTED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repair: Mapped["RepairRecord"] = relationship("RepairRecord", back_populates="attempts")


class VerificationRunRecord(Base):
    __tablename__ = "verification_runs_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="RUNNING", nullable=False)
    overall_result: Mapped[str] = mapped_column(String(30), default="FAILED", nullable=False)
    failure_analysis_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    repair: Mapped["RepairRecord"] = relationship("RepairRecord", back_populates="verification_runs")
    checks: Mapped[List["VerificationCheckRecord"]] = relationship(
        "VerificationCheckRecord", back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )


class VerificationCheckRecord(Base):
    __tablename__ = "verification_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    verification_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("verification_runs_v2.id", ondelete="CASCADE"), nullable=False, index=True)
    check_type: Mapped[str] = mapped_column(String(20), nullable=False)
    command: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="NOT_RUN", nullable=False)
    exit_code: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    stdout: Mapped[str] = mapped_column(Text, default="", nullable=False)
    stderr: Mapped[str] = mapped_column(Text, default="", nullable=False)
    parsed_errors_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    resource_usage_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    run: Mapped["VerificationRunRecord"] = relationship("VerificationRunRecord", back_populates="checks")


class FailureSignatureRecord(Base):
    __tablename__ = "failure_signatures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    check_type: Mapped[str] = mapped_column(String(20), nullable=False)
    error_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    test_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repair: Mapped["RepairRecord"] = relationship("RepairRecord", back_populates="failure_signatures")

