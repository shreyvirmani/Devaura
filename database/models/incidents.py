"""Devaura Incident Lifecycle & Durable Job Execution Models.

Defines:
- Incident & IncidentStatus / IncidentSource / IncidentType
- Job & JobStatus / JobType
"""

from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.connection import Base


def utc_now() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


class IncidentStatus(str, Enum):
    """Lifecycle states for a Devaura Incident (separate from Repair FSM)."""
    NEW = "NEW"
    QUEUED = "QUEUED"
    BLOCKED_QUOTA = "BLOCKED_QUOTA"
    INVESTIGATING = "INVESTIGATING"
    INVESTIGATED = "INVESTIGATED"
    REPAIR_PENDING = "REPAIR_PENDING"
    REPAIRING = "REPAIRING"
    VERIFYING = "VERIFYING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    PR_CREATED = "PR_CREATED"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class IncidentSource(str, Enum):
    GITHUB_WORKFLOW_RUN = "github_workflow_run"
    GITHUB_CHECK_RUN = "github_check_run"
    GITHUB_PUSH = "github_push"
    GITHUB_PULL_REQUEST = "github_pull_request"
    MANUAL = "manual"


class IncidentType(str, Enum):
    CI_FAILURE = "CI_FAILURE"
    CHECK_FAILURE = "CHECK_FAILURE"
    TEST_FAILURE = "TEST_FAILURE"
    BUILD_FAILURE = "BUILD_FAILURE"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    UNKNOWN = "UNKNOWN"


class JobType(str, Enum):
    INVESTIGATE_INCIDENT = "INVESTIGATE_INCIDENT"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RETRY_WAIT = "RETRY_WAIT"
    DEAD_LETTER = "DEAD_LETTER"
    PROVIDER_QUOTA_EXHAUSTED = "PROVIDER_QUOTA_EXHAUSTED"


class Incident(Base):
    """First-class workspace-scoped Incident created from normalized failure events."""
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    investigation_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("investigations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    source: Mapped[str] = mapped_column(String(50), default=IncidentSource.GITHUB_WORKFLOW_RUN.value, nullable=False)
    external_event_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    external_run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    external_check_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    dedup_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    type: Mapped[str] = mapped_column(String(50), default=IncidentType.CI_FAILURE.value, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=IncidentStatus.NEW.value, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    failure_signature: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    workflow_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    workflow_run_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    correlation_id: Mapped[str] = mapped_column(String(64), default=lambda: str(uuid.uuid4()), nullable=False, index=True)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", lazy="selectin")
    investigation: Mapped[Optional["Investigation"]] = relationship("Investigation", lazy="selectin")
    jobs: Mapped[List["Job"]] = relationship(
        "Job", back_populates="incident", cascade="all, delete-orphan", lazy="selectin"
    )


class Job(Base):
    """Durable database-backed background job with atomic claim and lease recovery."""
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    job_type: Mapped[str] = mapped_column(String(50), default=JobType.INVESTIGATE_INCIDENT.value, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=JobStatus.QUEUED.value, nullable=False, index=True)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    worker_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_classification: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    correlation_id: Mapped[str] = mapped_column(String(64), default=lambda: str(uuid.uuid4()), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="jobs")
