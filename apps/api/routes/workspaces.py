"""Devaura Workspaces & Tenant Scoped Endpoints.

Handles Workspace CRUD, Member Management, and Tenant-Scoped Resources
(Repositories, Incidents, Repairs, and Audit Events).
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import CurrentUser, create_auth_error, require_authenticated_user
from apps.api.authorization import (
    WorkspaceContext,
    get_workspace_context,
    require_workspace_admin,
    require_workspace_member,
    require_workspace_owner,
    verify_investigation_in_workspace,
    verify_repository_in_workspace,
)
from database.connection import get_db
from database.models import (
    AuditEventRecord,
    Investigation,
    RepairRecord,
    Repository,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)

router = APIRouter(prefix="/workspaces", tags=["Workspaces & Tenancy"])


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", slug) or "workspace"


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------

class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class UpdateWorkspaceRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    settings: Optional[Dict[str, Any]] = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str
    owner_id: str
    is_active: bool
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    role: Optional[str] = None


class MemberResponse(BaseModel):
    id: str
    user_id: str
    email: str
    name: str
    role: str
    created_at: datetime


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: WorkspaceRole = WorkspaceRole.MEMBER


class UpdateMemberRoleRequest(BaseModel):
    role: WorkspaceRole


class AuditEventResponse(BaseModel):
    id: str
    actor_email: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    outcome: str
    details: Dict[str, Any]
    created_at: datetime


# -------------------------------------------------------------------------
# Workspace CRUD
# -------------------------------------------------------------------------

@router.get("", response_model=List[WorkspaceResponse])
async def list_user_workspaces(
    current_user: CurrentUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List all workspaces the authenticated user belongs to."""
    stmt = (
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == current_user.id, Workspace.is_active == True)
        .order_by(desc(Workspace.created_at))
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            owner_id=ws.owner_id,
            is_active=ws.is_active,
            settings=ws.settings,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
            role=role,
        )
        for ws, role in rows
    ]


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: CreateWorkspaceRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new workspace with the authenticated user as OWNER."""
    base_slug = slugify(payload.slug or payload.name)
    slug = f"{base_slug}-{current_user.id[:6]}"

    # Verify uniqueness of slug
    existing = await db.execute(select(Workspace).where(Workspace.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{int(datetime.now().timestamp())}"

    workspace = Workspace(
        name=payload.name.strip(),
        slug=slug,
        owner_id=current_user.id,
        is_active=True,
        settings=payload.settings or {},
    )
    db.add(workspace)
    await db.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role=WorkspaceRole.OWNER.value,
    )
    db.add(member)

    audit = AuditEventRecord(
        workspace_id=workspace.id,
        actor_id=current_user.id,
        actor_email=current_user.email,
        action="workspace.create",
        resource_type="workspace",
        resource_id=workspace.id,
        outcome="SUCCESS",
        details={"name": workspace.name, "slug": workspace.slug},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(workspace)

    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        owner_id=workspace.owner_id,
        is_active=workspace.is_active,
        settings=workspace.settings,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        role=WorkspaceRole.OWNER.value,
    )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    ctx: WorkspaceContext = Depends(require_workspace_member),
):
    """Get single workspace details by ID or slug."""
    ws = ctx.workspace
    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        owner_id=ws.owner_id,
        is_active=ws.is_active,
        settings=ws.settings,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
        role=ctx.role.value,
    )


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    payload: UpdateWorkspaceRequest,
    request: Request,
    ctx: WorkspaceContext = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update workspace name or settings (Requires ADMIN or OWNER)."""
    ws = ctx.workspace
    if payload.name is not None:
        ws.name = payload.name.strip()
    if payload.settings is not None:
        ws.settings = {**ws.settings, **payload.settings}
    ws.updated_at = datetime.now(timezone.utc)

    audit = AuditEventRecord(
        workspace_id=ws.id,
        actor_id=ctx.user_id,
        actor_email=ctx.user.email,
        action="workspace.update",
        resource_type="workspace",
        resource_id=ws.id,
        outcome="SUCCESS",
        details={"updated_fields": list(payload.model_dump(exclude_unset=True).keys())},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(ws)

    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        owner_id=ws.owner_id,
        is_active=ws.is_active,
        settings=ws.settings,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
        role=ctx.role.value,
    )


@router.delete("/{workspace_id}")
async def delete_workspace(
    request: Request,
    ctx: WorkspaceContext = Depends(require_workspace_owner),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete/deactivate a workspace (Requires OWNER)."""
    ws = ctx.workspace
    ws.is_active = False
    ws.updated_at = datetime.now(timezone.utc)

    audit = AuditEventRecord(
        workspace_id=ws.id,
        actor_id=ctx.user_id,
        actor_email=ctx.user.email,
        action="workspace.delete",
        resource_type="workspace",
        resource_id=ws.id,
        outcome="SUCCESS",
        details={"name": ws.name},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)
    await db.commit()

    return {"status": "success", "message": f"Workspace '{ws.name}' deactivated."}


# -------------------------------------------------------------------------
# Member Management
# -------------------------------------------------------------------------

@router.get("/{workspace_id}/members", response_model=List[MemberResponse])
async def list_workspace_members(
    ctx: WorkspaceContext = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """List all members of a workspace."""
    stmt = (
        select(WorkspaceMember, User)
        .join(User, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == ctx.workspace_id)
        .order_by(WorkspaceMember.created_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        MemberResponse(
            id=m.id,
            user_id=u.id,
            email=u.email,
            name=u.name,
            role=m.role,
            created_at=m.created_at,
        )
        for m, u in rows
    ]


@router.post("/{workspace_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_workspace_member(
    payload: AddMemberRequest,
    request: Request,
    ctx: WorkspaceContext = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add or invite a member to the workspace (Requires ADMIN or OWNER)."""
    # Look up user by email
    stmt = select(User).where(User.email == payload.email.lower())
    result = await db.execute(stmt)
    target_user = result.scalar_one_or_none()

    if not target_user:
        # For simplicity create user shell if invited
        target_user = User(
            email=payload.email.lower(),
            name=payload.email.split("@")[0],
            is_active=True,
        )
        db.add(target_user)
        await db.flush()

    # Check if already a member
    existing_stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == ctx.workspace_id,
        WorkspaceMember.user_id == target_user.id,
    )
    if (await db.execute(existing_stmt)).scalar_one_or_none():
        raise create_auth_error(
            status.HTTP_409_CONFLICT,
            "MEMBER_ALREADY_EXISTS",
            "User is already a member of this workspace.",
        )

    # Only OWNER can grant OWNER role
    if payload.role == WorkspaceRole.OWNER and not ctx.is_owner():
        raise create_auth_error(
            status.HTTP_403_FORBIDDEN,
            "CANNOT_ASSIGN_OWNER",
            "Only workspace owners can assign the OWNER role.",
        )

    member = WorkspaceMember(
        workspace_id=ctx.workspace_id,
        user_id=target_user.id,
        role=payload.role.value,
        invited_by=ctx.user_id,
    )
    db.add(member)

    audit = AuditEventRecord(
        workspace_id=ctx.workspace_id,
        actor_id=ctx.user_id,
        actor_email=ctx.user.email,
        action="workspace.member_add",
        resource_type="workspace_member",
        resource_id=target_user.id,
        outcome="SUCCESS",
        details={"member_email": target_user.email, "role": payload.role.value},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(member)

    return MemberResponse(
        id=member.id,
        user_id=target_user.id,
        email=target_user.email,
        name=target_user.name,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_workspace_member(
    user_id: str,
    request: Request,
    ctx: WorkspaceContext = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from the workspace (Requires ADMIN or OWNER)."""
    # Prevent removing the workspace owner
    if user_id == ctx.workspace.owner_id:
        raise create_auth_error(
            status.HTTP_403_FORBIDDEN,
            "CANNOT_REMOVE_OWNER",
            "The workspace owner cannot be removed.",
        )

    stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == ctx.workspace_id,
        WorkspaceMember.user_id == user_id,
    )
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()

    if not member:
        raise create_auth_error(
            status.HTTP_404_NOT_FOUND,
            "MEMBER_NOT_FOUND",
            "Member not found in this workspace.",
        )

    await db.delete(member)

    audit = AuditEventRecord(
        workspace_id=ctx.workspace_id,
        actor_id=ctx.user_id,
        actor_email=ctx.user.email,
        action="workspace.member_remove",
        resource_type="workspace_member",
        resource_id=user_id,
        outcome="SUCCESS",
        details={"removed_user_id": user_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)
    await db.commit()

    return {"status": "success", "message": "Member removed from workspace."}


# -------------------------------------------------------------------------
# Workspace-Scoped Resources: Repositories
# -------------------------------------------------------------------------

@router.get("/{workspace_id}/repositories")
async def list_workspace_repositories(
    ctx: WorkspaceContext = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """List repositories strictly scoped to this workspace."""
    stmt = (
        select(Repository)
        .where(Repository.workspace_id == ctx.workspace_id)
        .order_by(desc(Repository.created_at))
    )
    result = await db.execute(stmt)
    repos = result.scalars().all()
    return [
        {
            "id": r.id,
            "workspace_id": r.workspace_id,
            "owner": r.owner,
            "name": r.name,
            "full_name": r.full_name or f"{r.owner}/{r.name}",
            "provider": r.provider,
            "default_branch": r.default_branch,
            "clone_url": r.clone_url,
            "private": r.private if hasattr(r, "private") else True,
            "connection_status": r.connection_status if hasattr(r, "connection_status") else "CONNECTED",
            "github_installation_id": r.github_installation_id if hasattr(r, "github_installation_id") else None,
            "github_repository_id": r.github_repository_id if hasattr(r, "github_repository_id") else None,
            "last_webhook_received_at": r.last_webhook_received_at if hasattr(r, "last_webhook_received_at") else None,
            "last_indexed_at": r.last_indexed_at if hasattr(r, "last_indexed_at") else None,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in repos
    ]


@router.get("/{workspace_id}/repositories/{repository_id}")
async def get_workspace_repository(
    repository_id: str,
    ctx: WorkspaceContext = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """Get single repository strictly scoped to this workspace (with IDOR prevention)."""
    repo = await verify_repository_in_workspace(repository_id, ctx.workspace_id, db)
    return {
        "id": repo.id,
        "workspace_id": repo.workspace_id,
        "owner": repo.owner,
        "name": repo.name,
        "full_name": repo.full_name or f"{repo.owner}/{repo.name}",
        "provider": repo.provider,
        "default_branch": repo.default_branch,
        "clone_url": repo.clone_url,
        "private": repo.private if hasattr(repo, "private") else True,
        "connection_status": repo.connection_status if hasattr(repo, "connection_status") else "CONNECTED",
        "github_installation_id": repo.github_installation_id if hasattr(repo, "github_installation_id") else None,
        "github_repository_id": repo.github_repository_id if hasattr(repo, "github_repository_id") else None,
        "permissions_snapshot": repo.permissions_snapshot if hasattr(repo, "permissions_snapshot") else {},
        "last_webhook_received_at": repo.last_webhook_received_at if hasattr(repo, "last_webhook_received_at") else None,
        "last_indexed_at": repo.last_indexed_at if hasattr(repo, "last_indexed_at") else None,
        "created_at": repo.created_at,
        "updated_at": repo.updated_at,
    }


@router.post("/{workspace_id}/repositories", status_code=status.HTTP_201_CREATED)
async def connect_workspace_repository(
    payload: Dict[str, Any],
    request: Request,
    ctx: WorkspaceContext = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Connect a repository strictly to this workspace (Requires ADMIN)."""
    repo = Repository(
        workspace_id=ctx.workspace_id,
        owner=payload["owner"],
        name=payload["name"],
        provider=payload.get("provider", "github"),
        default_branch=payload.get("default_branch", "main"),
        clone_url=payload["clone_url"],
    )
    db.add(repo)
    await db.flush()

    audit = AuditEventRecord(
        workspace_id=ctx.workspace_id,
        actor_id=ctx.user_id,
        actor_email=ctx.user.email,
        action="repository.connect",
        resource_type="repository",
        resource_id=repo.id,
        outcome="SUCCESS",
        details={"repo": f"{repo.owner}/{repo.name}"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(repo)

    return {
        "id": repo.id,
        "workspace_id": repo.workspace_id,
        "owner": repo.owner,
        "name": repo.name,
        "provider": repo.provider,
        "default_branch": repo.default_branch,
        "clone_url": repo.clone_url,
        "created_at": repo.created_at,
    }


# -------------------------------------------------------------------------
# Workspace-Scoped Resources: Incidents / Investigations
# -------------------------------------------------------------------------

@router.get("/{workspace_id}/incidents")
async def list_workspace_incidents(
    limit: int = Query(50, ge=1, le=100),
    ctx: WorkspaceContext = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """List investigations/incidents strictly scoped to this workspace."""
    stmt = (
        select(Investigation)
        .join(Repository, Investigation.repository_id == Repository.id)
        .where(
            (Investigation.workspace_id == ctx.workspace_id) | (Repository.workspace_id == ctx.workspace_id)
        )
        .order_by(desc(Investigation.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    invs = result.scalars().all()
    return [
        {
            "id": inv.id,
            "workspace_id": ctx.workspace_id,
            "repository_id": inv.repository_id,
            "title": inv.title,
            "summary": inv.summary,
            "status": inv.status,
            "failure_type": inv.failure_type,
            "evidence_sufficiency": inv.evidence_sufficiency,
            "confidence": inv.confidence,
            "created_at": inv.created_at,
            "updated_at": inv.updated_at,
        }
        for inv in invs
    ]


# -------------------------------------------------------------------------
# Workspace-Scoped Resources: Audit Events
# -------------------------------------------------------------------------

@router.get("/{workspace_id}/audit-events", response_model=List[AuditEventResponse])
async def list_workspace_audit_events(
    limit: int = Query(50, ge=1, le=200),
    ctx: WorkspaceContext = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """List audit events for this workspace (Requires ADMIN or OWNER)."""
    stmt = (
        select(AuditEventRecord)
        .where(AuditEventRecord.workspace_id == ctx.workspace_id)
        .order_by(desc(AuditEventRecord.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    return [
        AuditEventResponse(
            id=e.id,
            actor_email=e.actor_email,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            outcome=e.outcome,
            details=e.details,
            created_at=e.created_at,
        )
        for e in events
    ]
