"""Devaura Server-Side Authorization & Multi-Tenant Boundary.

Enforces:
1. User-to-Workspace membership verification
2. Role-based operation gating (OWNER, ADMIN, MEMBER)
3. Workspace resource isolation & IDOR prevention
"""

from typing import Optional
from fastapi import Depends, HTTPException, Path, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import CurrentUser, create_auth_error, require_authenticated_user
from database.connection import get_db
from database.models import (
    Investigation,
    RepairRecord,
    Repository,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
)


class WorkspaceContext:
    """Resolved and authorized workspace session context."""

    def __init__(
        self,
        workspace: Workspace,
        member: WorkspaceMember,
        user: CurrentUser,
    ):
        self.workspace = workspace
        self.member = member
        self.user = user
        self.role = WorkspaceRole(member.role)

    @property
    def workspace_id(self) -> str:
        return self.workspace.id

    @property
    def user_id(self) -> str:
        return self.user.id

    def is_owner(self) -> bool:
        return self.role == WorkspaceRole.OWNER or self.user.is_superuser

    def is_admin_or_owner(self) -> bool:
        return self.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN) or self.user.is_superuser

    def can_manage_repositories(self) -> bool:
        return self.is_admin_or_owner()

    def can_manage_members(self) -> bool:
        return self.is_admin_or_owner()

    def can_delete_workspace(self) -> bool:
        return self.is_owner()

    def can_approve_repairs(self) -> bool:
        # By default owners and admins can approve; members can approve if allowed by workspace settings
        if self.is_admin_or_owner():
            return True
        return bool(self.workspace.settings.get("allow_member_approvals", False))


async def get_workspace_context(
    workspace_id: str = Path(..., description="Target Workspace UUID or slug"),
    current_user: CurrentUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceContext:
    """Dependency: Resolves and authorizes workspace access for current user.
    
    Verifies:
    1. Workspace exists
    2. User is an active member of that workspace
    3. Rejects cross-tenant access with HTTP 403
    """
    # Look up workspace by ID or slug
    stmt = select(Workspace).where(
        (Workspace.id == workspace_id) | (Workspace.slug == workspace_id)
    )
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()

    if not workspace or not workspace.is_active:
        raise create_auth_error(
            status.HTTP_404_NOT_FOUND,
            "WORKSPACE_NOT_FOUND",
            "Workspace not found or inactive.",
        )

    # Superuser bypass for platform maintenance
    if current_user.is_superuser:
        # Create virtual owner membership
        virtual_member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=current_user.id,
            role=WorkspaceRole.OWNER.value,
        )
        return WorkspaceContext(workspace, virtual_member, current_user)

    # Verify user's server-side membership in this workspace
    member_stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace.id,
        WorkspaceMember.user_id == current_user.id,
    )
    member_result = await db.execute(member_stmt)
    membership = member_result.scalar_one_or_none()

    if not membership:
        raise create_auth_error(
            status.HTTP_403_FORBIDDEN,
            "WORKSPACE_ACCESS_DENIED",
            "You do not have access to this workspace.",
        )

    return WorkspaceContext(workspace, membership, current_user)


async def require_workspace_member(
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkspaceContext:
    """Requires at minimum MEMBER role in the workspace."""
    return ctx


async def require_workspace_admin(
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkspaceContext:
    """Requires ADMIN or OWNER role in the workspace."""
    if not ctx.is_admin_or_owner():
        raise create_auth_error(
            status.HTTP_403_FORBIDDEN,
            "INSUFFICIENT_PERMISSIONS",
            "Administrator privileges required for this workspace operation.",
        )
    return ctx


async def require_workspace_owner(
    ctx: WorkspaceContext = Depends(get_workspace_context),
) -> WorkspaceContext:
    """Requires OWNER role in the workspace."""
    if not ctx.is_owner():
        raise create_auth_error(
            status.HTTP_403_FORBIDDEN,
            "OWNER_REQUIRED",
            "Owner privileges required for this workspace operation.",
        )
    return ctx


# =========================================================================
# Resource Isolation & IDOR Verification Helpers
# =========================================================================

async def verify_repository_in_workspace(
    repo_id: str,
    workspace_id: str,
    db: AsyncSession,
) -> Repository:
    """Verify repository exists and strictly belongs to the specified workspace."""
    stmt = select(Repository).where(
        Repository.id == repo_id,
        Repository.workspace_id == workspace_id,
    )
    result = await db.execute(stmt)
    repo = result.scalar_one_or_none()
    if not repo:
        raise create_auth_error(
            status.HTTP_404_NOT_FOUND,
            "REPOSITORY_NOT_FOUND",
            "Repository not found in this workspace.",
        )
    return repo


async def verify_investigation_in_workspace(
    inv_id: str,
    workspace_id: str,
    db: AsyncSession,
) -> Investigation:
    """Verify investigation exists and belongs to the workspace (directly or via repo)."""
    stmt = (
        select(Investigation)
        .join(Repository, Investigation.repository_id == Repository.id)
        .where(
            Investigation.id == inv_id,
            (Investigation.workspace_id == workspace_id) | (Repository.workspace_id == workspace_id),
        )
    )
    result = await db.execute(stmt)
    inv = result.scalar_one_or_none()
    if not inv:
        raise create_auth_error(
            status.HTTP_404_NOT_FOUND,
            "INVESTIGATION_NOT_FOUND",
            "Investigation not found in this workspace.",
        )
    return inv


async def verify_repair_in_workspace(
    repair_id: str,
    workspace_id: str,
    db: AsyncSession,
) -> RepairRecord:
    """Verify repair exists and belongs to the workspace."""
    stmt = (
        select(RepairRecord)
        .join(Repository, RepairRecord.repository_id == Repository.id)
        .where(
            RepairRecord.id == repair_id,
            (RepairRecord.workspace_id == workspace_id) | (Repository.workspace_id == workspace_id),
        )
    )
    result = await db.execute(stmt)
    repair = result.scalar_one_or_none()
    if not repair:
        raise create_auth_error(
            status.HTTP_404_NOT_FOUND,
            "REPAIR_NOT_FOUND",
            "Repair not found in this workspace.",
        )
    return repair


async def get_user_workspace_ids(user: CurrentUser, db: AsyncSession) -> list[str]:
    """Return all workspace IDs the authenticated user belongs to."""
    res = await db.execute(
        select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
    )
    return list(res.scalars().all())


async def resolve_user_workspace_id(
    requested_workspace_id: Optional[str],
    user: CurrentUser,
    db: AsyncSession,
) -> Optional[str]:
    """Resolve and authorize a target workspace_id for a real user."""
    from apps.api.auth import DEV_USER

    if user.id == DEV_USER.id and not requested_workspace_id:
        return None
    ws_ids = await get_user_workspace_ids(user, db)
    if requested_workspace_id:
        if requested_workspace_id not in ws_ids and not user.is_superuser:
            raise create_auth_error(
                status.HTTP_403_FORBIDDEN,
                "FORBIDDEN",
                "You do not have access to this workspace.",
            )
        return requested_workspace_id
    if not ws_ids:
        raise create_auth_error(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "User does not belong to any workspace.",
        )
    return ws_ids[0]


async def require_resource_workspace_access(
    workspace_id: Optional[str],
    user: CurrentUser,
    db: AsyncSession,
) -> None:
    """Enforce server-side workspace isolation for top-level resource endpoints."""
    from apps.api.auth import DEV_USER

    if user.is_superuser or user.id == DEV_USER.id:
        return
    if not workspace_id:
        raise create_auth_error(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "Resource is not scoped to an accessible workspace.",
        )
    ws_ids = await get_user_workspace_ids(user, db)
    if workspace_id not in ws_ids:
        raise create_auth_error(
            status.HTTP_403_FORBIDDEN,
            "FORBIDDEN",
            "Cross-workspace access denied.",
        )
