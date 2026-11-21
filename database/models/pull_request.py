"""Devaura Phase 7 Pull Request Relational Database Models.

Persists pull request records, cryptographic PR approvals, and audit event logs.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
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


class PullRequestRecord(Base):
    __tablename__ = "pull_requests_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), index=True, nullable=False)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), index=True, nullable=False)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="github", nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    repo: Mapped[str] = mapped_column(String(100), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    base_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    repair_branch: Mapped[str] = mapped_column(String(100), nullable=False)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pr_url: Mapped[str] = mapped_column(String(500), nullable=False)
    pr_title: Mapped[str] = mapped_column(String(255), nullable=False)
    pr_body: Mapped[str] = mapped_column(Text, nullable=False)
    pr_state: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    patch_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    approval_token: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(60), default="PR_CREATED", nullable=False, index=True)
    ci_status_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    review_status_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    repair: Mapped["RepairRecord"] = relationship("RepairRecord", back_populates="pull_request")
    approvals: Mapped[List["PullRequestApprovalRecord"]] = relationship(
        "PullRequestApprovalRecord", back_populates="pull_request", cascade="all, delete-orphan", lazy="selectin"
    )
    events: Mapped[List["PullRequestEventRecord"]] = relationship(
        "PullRequestEventRecord", back_populates="pull_request", cascade="all, delete-orphan", lazy="selectin"
    )


class PullRequestApprovalRecord(Base):
    __tablename__ = "pr_approvals_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), nullable=False)
    pr_record_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("pull_requests_v2.id", ondelete="CASCADE"), nullable=True)
    patch_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_token: Mapped[str] = mapped_column(String(100), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="APPROVED", nullable=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    pull_request: Mapped[Optional["PullRequestRecord"]] = relationship("PullRequestRecord", back_populates="approvals")


class PullRequestEventRecord(Base):
    __tablename__ = "pr_events_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repair_id: Mapped[str] = mapped_column(String(36), ForeignKey("repairs.id", ondelete="CASCADE"), nullable=False)
    pr_record_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("pull_requests_v2.id", ondelete="CASCADE"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(255), default="system", nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    pull_request: Mapped[Optional["PullRequestRecord"]] = relationship("PullRequestRecord", back_populates="events")
