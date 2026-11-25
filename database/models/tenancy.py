"""Devaura Multi-Tenancy & Audit Logging Models.

Defines Workspaces, Workspace Memberships (Owner, Admin, Member),
and append-only Audit Events.
"""

from datetime import datetime, timezone
from enum import Enum
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.connection import Base


def utc_now() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


class WorkspaceRole(str, Enum):
    """Hierarchical workspace access roles."""
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class Workspace(Base):
    """A multi-tenant workspace isolating repositories, incidents, and repairs."""
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id], lazy="selectin")
    members: Mapped[List["WorkspaceMember"]] = relationship(
        "WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan", lazy="selectin"
    )
    repositories: Mapped[List["Repository"]] = relationship(
        "Repository", back_populates="workspace", cascade="all, delete-orphan", lazy="selectin"
    )
    audit_events: Mapped[List["AuditEventRecord"]] = relationship(
        "AuditEventRecord", back_populates="workspace", cascade="all, delete-orphan", lazy="selectin"
    )
    github_installations: Mapped[List["GitHubAppInstallation"]] = relationship(
        "GitHubAppInstallation", back_populates="workspace", cascade="all, delete-orphan", lazy="selectin"
    )
    webhook_events: Mapped[List["WebhookEventRecord"]] = relationship(
        "WebhookEventRecord", back_populates="workspace", cascade="all, delete-orphan", lazy="selectin"
    )


class WorkspaceMember(Base):
    """Membership link associating a User with a Workspace and role."""
    __tablename__ = "workspace_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), default=WorkspaceRole.MEMBER.value, nullable=False)
    invited_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Table-level uniqueness constraint
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="memberships", lazy="selectin")


class AuditEventRecord(Base):
    """Append-only audit trail capturing security-critical actions and tenant events."""
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    outcome: Mapped[str] = mapped_column(String(20), default="SUCCESS", nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Relationships
    workspace: Mapped[Optional["Workspace"]] = relationship("Workspace", back_populates="audit_events")


class GitHubAppInstallation(Base):
    """Represents a GitHub App installation authorized for a workspace."""
    __tablename__ = "github_app_installations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    installation_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)  # GitHub numeric ID
    account_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)  # User or Org login
    account_type: Mapped[str] = mapped_column(String(20), default="User", nullable=False)  # User or Organization
    account_avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    repository_selection: Mapped[str] = mapped_column(String(20), default="all", nullable=False)  # all | selected
    permissions: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    events: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="github_installations")
    repositories: Mapped[List["Repository"]] = relationship(
        "Repository", back_populates="github_installation", cascade="all, delete-orphan", lazy="selectin"
    )


class WebhookEventRecord(Base):
    """Durable append-only event log for GitHub webhooks ensuring replay resistance and idempotency."""
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    delivery_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)  # X-GitHub-Delivery
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # X-GitHub-Event
    installation_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    workspace_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    repository_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True, index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)  # Sanitized payload
    status: Mapped[str] = mapped_column(String(30), default="RECEIVED", nullable=False, index=True)  # RECEIVED, PROCESSED, DUPLICATE, IGNORED, REJECTED
    signature_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    workspace: Mapped[Optional["Workspace"]] = relationship("Workspace", back_populates="webhook_events")
