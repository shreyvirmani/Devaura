"""Devaura GitHub App Integration & Repository Management Endpoints.

Handles:
1. GitHub App Installation URL generation with state parameter.
2. Linking GitHub App installations to workspaces.
3. Discovering available repositories for an installation.
4. Authoritatively connecting repositories to workspaces (anti-spoofing).
5. Disconnecting repositories and installations.
6. Detailed repository health and Devaura readiness status inspection.
"""

from datetime import datetime, timezone
import secrets
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import CurrentUser, create_auth_error, require_authenticated_user
from apps.api.authorization import (
    WorkspaceContext,
    get_workspace_context,
    require_workspace_admin,
    require_workspace_member,
    require_workspace_owner,
    verify_repository_in_workspace,
)
from database.connection import get_db
from database.models import (
    AuditEventRecord,
    GitHubAppInstallation,
    Investigation,
    PullRequest,
    RepairRecord,
    Repository,
    Workspace,
)
from integrations.github.app_service import (
    GitHubAppAuthError,
    GitHubAppError,
    GitHubRepoNotFoundError,
    get_github_app_service,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/github", tags=["GitHub App & Repositories"])


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------

class InstallUrlResponse(BaseModel):
    install_url: str
    state: str
    app_slug: str


class RecordInstallationRequest(BaseModel):
    installation_id: int
    state: Optional[str] = None
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    account_type: Optional[str] = "Organization"
    account_avatar_url: Optional[str] = None
    repository_selection: Optional[str] = "selected"
    permissions: Optional[Dict[str, Any]] = None
    events: Optional[List[str]] = None


class InstallationResponse(BaseModel):
    id: str
    workspace_id: str
    installation_id: int
    account_id: Optional[int]
    account_name: str
    account_type: str
    account_avatar_url: Optional[str]
    repository_selection: str
    permissions: Dict[str, Any]
    events: List[str]
    is_active: bool
    installed_at: datetime
    updated_at: datetime


class DiscoveredRepositoryItem(BaseModel):
    id: int
    name: str
    full_name: str
    owner: str
    private: bool
    default_branch: str
    is_connected: bool
    connected_repository_id: Optional[str] = None
    permissions: Dict[str, Any]


class DiscoveredRepositoriesResponse(BaseModel):
    installation_id: int
    total_count: int
    repositories: List[DiscoveredRepositoryItem]


class ConnectRepositoryRequest(BaseModel):
    installation_id: int
    owner: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    default_branch: Optional[str] = None


class RepositoryDetailResponse(BaseModel):
    repository: Dict[str, Any]
    installation: Optional[Dict[str, Any]]
    health: Dict[str, Any]


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------

@router.get("/install-url", response_model=InstallUrlResponse)
async def get_github_install_url(
    ctx: WorkspaceContext = Depends(require_workspace_admin),
):
    """Generate the GitHub App installation URL for this workspace (Requires ADMIN)."""
    service = get_github_app_service()
    state_token = f"ws_{ctx.workspace_id}_{secrets.token_urlsafe(16)}"
    url = service.generate_install_url(ctx.workspace_id, state_token)

    from apps.api.config import get_settings
    settings = get_settings()

    return InstallUrlResponse(
        install_url=url,
        state=state_token,
        app_slug=settings.GITHUB_APP_SLUG or "devaura-repair",
    )


@router.post("/installations", response_model=InstallationResponse, status_code=status.HTTP_201_CREATED)
async def record_installation(
    payload: RecordInstallationRequest,
    request: Request,
    ctx: WorkspaceContext = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Link a GitHub App installation to this workspace (Requires ADMIN)."""
    # Check if installation exists anywhere
    existing_stmt = select(GitHubAppInstallation).where(
        GitHubAppInstallation.installation_id == payload.installation_id
    )
    res = await db.execute(existing_stmt)
    existing = res.scalar_one_or_none()

    if existing:
        if existing.workspace_id != ctx.workspace_id:
            raise create_auth_error(
                status.HTTP_409_CONFLICT,
                "INSTALLATION_ALREADY_LINKED",
                "This GitHub App installation is already linked to another workspace.",
            )
        # Reactivate if it was previously deactivated
        existing.is_active = True
        existing.updated_at = datetime.now(timezone.utc)
        if payload.account_name:
            existing.account_name = payload.account_name
        if payload.account_avatar_url:
            existing.account_avatar_url = payload.account_avatar_url
        if payload.permissions:
            existing.permissions = payload.permissions
        installation = existing
    else:
        installation = GitHubAppInstallation(
            workspace_id=ctx.workspace_id,
            installation_id=payload.installation_id,
            account_id=payload.account_id or 0,
            account_name=payload.account_name or f"gh-account-{payload.installation_id}",
            account_type=payload.account_type or "Organization",
            account_avatar_url=payload.account_avatar_url,
            repository_selection=payload.repository_selection or "selected",
            permissions=payload.permissions or {},
            events=payload.events or [],
            is_active=True,
        )
        db.add(installation)

    await db.flush()

    audit = AuditEventRecord(
        workspace_id=ctx.workspace_id,
        actor_id=ctx.user_id,
        actor_email=ctx.user.email,
        action="github.installation.connected",
        resource_type="github_installation",
        resource_id=installation.id,
        outcome="SUCCESS",
        details={
            "installation_id": installation.installation_id,
            "account_name": installation.account_name,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(installation)

    return InstallationResponse(
        id=installation.id,
        workspace_id=installation.workspace_id,
        installation_id=installation.installation_id,
        account_id=installation.account_id,
        account_name=installation.account_name,
        account_type=installation.account_type,
        account_avatar_url=installation.account_avatar_url,
        repository_selection=installation.repository_selection,
        permissions=installation.permissions,
        events=installation.events,
        is_active=installation.is_active,
        installed_at=installation.installed_at,
        updated_at=installation.updated_at,
    )


@router.get("/installations", response_model=List[InstallationResponse])
async def list_installations(
    ctx: WorkspaceContext = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """List active GitHub App installations linked to this workspace."""
    stmt = (
        select(GitHubAppInstallation)
        .where(
            GitHubAppInstallation.workspace_id == ctx.workspace_id,
            GitHubAppInstallation.is_active == True,
        )
        .order_by(desc(GitHubAppInstallation.installed_at))
    )
    result = await db.execute(stmt)
    installations = result.scalars().all()

    return [
        InstallationResponse(
            id=inst.id,
            workspace_id=inst.workspace_id,
            installation_id=inst.installation_id,
            account_id=inst.account_id,
            account_name=inst.account_name,
            account_type=inst.account_type,
            account_avatar_url=inst.account_avatar_url,
            repository_selection=inst.repository_selection,
            permissions=inst.permissions,
            events=inst.events,
            is_active=inst.is_active,
            installed_at=inst.installed_at,
            updated_at=inst.updated_at,
        )
        for inst in installations
    ]


@router.delete("/installations/{installation_id}")
async def disconnect_installation(
    installation_id: int,
    request: Request,
    ctx: WorkspaceContext = Depends(require_workspace_owner),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a GitHub App installation from this workspace (Requires OWNER)."""
    stmt = select(GitHubAppInstallation).where(
        GitHubAppInstallation.workspace_id == ctx.workspace_id,
        GitHubAppInstallation.installation_id == installation_id,
    )
    res = await db.execute(stmt)
    installation = res.scalar_one_or_none()

    if not installation:
        raise create_auth_error(
            status.HTTP_404_NOT_FOUND,
            "INSTALLATION_NOT_FOUND",
            f"GitHub App installation {installation_id} not found in this workspace.",
        )

    installation.is_active = False
    installation.updated_at = datetime.now(timezone.utc)

    # Mark associated repositories as ACCESS_REVOKED
    repos_stmt = select(Repository).where(
        Repository.workspace_id == ctx.workspace_id,
        Repository.github_installation_id == installation.id,
    )
    repos_res = await db.execute(repos_stmt)
    repos = repos_res.scalars().all()
    for repo in repos:
        repo.connection_status = "ACCESS_REVOKED"

    audit = AuditEventRecord(
        workspace_id=ctx.workspace_id,
        actor_id=ctx.user_id,
        actor_email=ctx.user.email,
        action="github.installation.disconnected",
        resource_type="github_installation",
        resource_id=installation.id,
        outcome="SUCCESS",
        details={"installation_id": installation.installation_id},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)
    await db.commit()

    return {"status": "disconnected", "installation_id": installation_id}


@router.get("/installations/{installation_id}/repositories", response_model=DiscoveredRepositoriesResponse)
async def discover_installation_repositories(
    installation_id: int,
    ctx: WorkspaceContext = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """Discover repositories accessible to the GitHub App installation."""
    stmt = select(GitHubAppInstallation).where(
        GitHubAppInstallation.workspace_id == ctx.workspace_id,
        GitHubAppInstallation.installation_id == installation_id,
        GitHubAppInstallation.is_active == True,
    )
    res = await db.execute(stmt)
    installation = res.scalar_one_or_none()

    if not installation:
        raise create_auth_error(
            status.HTTP_404_NOT_FOUND,
            "INSTALLATION_NOT_FOUND",
            f"Active GitHub App installation {installation_id} not found in this workspace.",
        )

    service = get_github_app_service()
    try:
        gh_repos = await service.get_installation_repositories(installation_id)
    except GitHubAppError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "GITHUB_API_ERROR", "message": str(e)}},
        )

    # Query currently connected repos in this workspace
    connected_stmt = select(Repository).where(
        Repository.workspace_id == ctx.workspace_id,
        Repository.connection_status == "CONNECTED",
    )
    connected_res = await db.execute(connected_stmt)
    connected_repos = connected_res.scalars().all()
    connected_map = {
        r.github_repository_id: r.id for r in connected_repos if r.github_repository_id
    }
    connected_names_map = {
        f"{r.owner}/{r.name}".lower(): r.id for r in connected_repos
    }

    items = []
    for r in gh_repos:
        repo_id = r.get("id")
        full_name = r.get("full_name", f"{r.get('owner', {}).get('login', '')}/{r.get('name', '')}")
        connected_id = connected_map.get(repo_id) or connected_names_map.get(full_name.lower())

        owner_login = r.get("owner", {}).get("login", "") if isinstance(r.get("owner"), dict) else str(r.get("owner", ""))

        items.append(
            DiscoveredRepositoryItem(
                id=repo_id,
                name=r.get("name", ""),
                full_name=full_name,
                owner=owner_login,
                private=bool(r.get("private", True)),
                default_branch=r.get("default_branch", "main"),
                is_connected=bool(connected_id),
                connected_repository_id=connected_id,
                permissions=r.get("permissions", {}),
            )
        )

    return DiscoveredRepositoriesResponse(
        installation_id=installation_id,
        total_count=len(items),
        repositories=items,
    )


@router.post("/repositories/connect", status_code=status.HTTP_201_CREATED)
async def connect_repository(
    payload: ConnectRepositoryRequest,
    request: Request,
    ctx: WorkspaceContext = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Authoritatively verify and connect a GitHub repository to the workspace (Requires ADMIN)."""
    # 1. Verify installation belongs to workspace
    stmt = select(GitHubAppInstallation).where(
        GitHubAppInstallation.workspace_id == ctx.workspace_id,
        GitHubAppInstallation.installation_id == payload.installation_id,
        GitHubAppInstallation.is_active == True,
    )
    res = await db.execute(stmt)
    installation = res.scalar_one_or_none()

    if not installation:
        raise create_auth_error(
            status.HTTP_404_NOT_FOUND,
            "INSTALLATION_NOT_FOUND",
            f"Active GitHub App installation {payload.installation_id} not found in this workspace.",
        )

    # 2. Server-side validation via GitHub App installation (Anti-Spoofing)
    service = get_github_app_service()
    try:
        gh_data = await service.get_repository_details(
            payload.installation_id, payload.owner, payload.name
        )
    except GitHubRepoNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "REPOSITORY_NOT_FOUND_ON_GITHUB", "message": str(e)}},
        )
    except GitHubAppError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "GITHUB_API_ERROR", "message": str(e)}},
        )

    # 3. Check if already connected in this workspace
    gh_repo_id = gh_data["id"]
    owner = gh_data["owner"]["login"] if isinstance(gh_data["owner"], dict) else str(gh_data["owner"])
    name = gh_data["name"]

    existing_stmt = select(Repository).where(
        Repository.workspace_id == ctx.workspace_id,
        (Repository.github_repository_id == gh_repo_id) |
        ((Repository.owner == owner) & (Repository.name == name)),
    )
    existing_res = await db.execute(existing_stmt)
    existing_repo = existing_res.scalar_one_or_none()

    if existing_repo:
        if existing_repo.connection_status == "CONNECTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "REPOSITORY_ALREADY_CONNECTED",
                        "message": f"Repository {owner}/{name} is already connected to this workspace.",
                    }
                },
            )
        # Reactivate previously disconnected repository
        existing_repo.connection_status = "CONNECTED"
        existing_repo.github_installation_id = installation.id
        existing_repo.github_repository_id = gh_repo_id
        existing_repo.full_name = gh_data.get("full_name") or f"{owner}/{name}"
        existing_repo.private = gh_data.get("private", True)
        existing_repo.default_branch = payload.default_branch or gh_data.get("default_branch", "main")
        existing_repo.clone_url = gh_data.get("clone_url") or f"https://github.com/{owner}/{name}.git"
        existing_repo.permissions_snapshot = gh_data.get("permissions", {})
        repo = existing_repo
    else:
        repo = Repository(
            workspace_id=ctx.workspace_id,
            github_installation_id=installation.id,
            github_repository_id=gh_repo_id,
            owner=owner,
            name=name,
            full_name=gh_data.get("full_name") or f"{owner}/{name}",
            provider="github",
            default_branch=payload.default_branch or gh_data.get("default_branch", "main"),
            clone_url=gh_data.get("clone_url") or f"https://github.com/{owner}/{name}.git",
            private=gh_data.get("private", True),
            connection_status="CONNECTED",
            permissions_snapshot=gh_data.get("permissions", {}) or {},
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
        details={
            "repo": f"{owner}/{name}",
            "github_repository_id": gh_repo_id,
            "private": repo.private,
        },
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
        "full_name": repo.full_name,
        "provider": repo.provider,
        "default_branch": repo.default_branch,
        "clone_url": repo.clone_url,
        "private": repo.private,
        "connection_status": repo.connection_status,
        "github_installation_id": repo.github_installation_id,
        "github_repository_id": repo.github_repository_id,
        "created_at": repo.created_at,
        "updated_at": repo.updated_at,
    }


@router.delete("/repositories/{repository_id}")
async def disconnect_repository(
    repository_id: str,
    request: Request,
    ctx: WorkspaceContext = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a repository from this workspace (Requires ADMIN)."""
    repo = await verify_repository_in_workspace(repository_id, ctx.workspace_id, db)

    repo.connection_status = "DISCONNECTED"
    repo.updated_at = datetime.now(timezone.utc)

    audit = AuditEventRecord(
        workspace_id=ctx.workspace_id,
        actor_id=ctx.user_id,
        actor_email=ctx.user.email,
        action="repository.disconnect",
        resource_type="repository",
        resource_id=repo.id,
        outcome="SUCCESS",
        details={"repo": f"{repo.owner}/{repo.name}"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)
    await db.commit()

    return {"status": "disconnected", "repository_id": repository_id}


@router.get("/repositories/{repository_id}/detail", response_model=RepositoryDetailResponse)
async def get_repository_detail(
    repository_id: str,
    ctx: WorkspaceContext = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """Get comprehensive repository health, installation details, and Devaura readiness status."""
    repo = await verify_repository_in_workspace(repository_id, ctx.workspace_id, db)

    # 1. Fetch Installation info if attached
    installation_info = None
    if repo.github_installation_id:
        inst_stmt = select(GitHubAppInstallation).where(
            GitHubAppInstallation.id == repo.github_installation_id
        )
        inst_res = await db.execute(inst_stmt)
        inst = inst_res.scalar_one_or_none()
        if inst:
            installation_info = {
                "id": inst.id,
                "installation_id": inst.installation_id,
                "account_name": inst.account_name,
                "account_type": inst.account_type,
                "account_avatar_url": inst.account_avatar_url,
                "is_active": inst.is_active,
            }

    # 2. Compute Health & Metrics (No synthetic/fake data)
    # Active incidents: investigations in progress
    active_incidents_stmt = select(func.count(Investigation.id)).where(
        Investigation.repository_id == repo.id,
        Investigation.workspace_id == ctx.workspace_id,
        Investigation.status.in_(["INVESTIGATING", "ANALYZING", "ROOT_CAUSE_IDENTIFIED"]),
    )
    active_incidents = (await db.execute(active_incidents_stmt)).scalar() or 0

    total_investigations_stmt = select(func.count(Investigation.id)).where(
        Investigation.repository_id == repo.id,
        Investigation.workspace_id == ctx.workspace_id,
    )
    total_investigations = (await db.execute(total_investigations_stmt)).scalar() or 0

    total_repairs_stmt = select(func.count(RepairRecord.id)).where(
        RepairRecord.repository_id == repo.id,
        RepairRecord.workspace_id == ctx.workspace_id,
    )
    total_repairs = (await db.execute(total_repairs_stmt)).scalar() or 0

    total_prs_stmt = select(func.count(PullRequest.id)).where(
        PullRequest.repository_id == repo.id,
    )
    total_prs = (await db.execute(total_prs_stmt)).scalar() or 0

    repo_data = {
        "id": repo.id,
        "workspace_id": repo.workspace_id,
        "owner": repo.owner,
        "name": repo.name,
        "full_name": repo.full_name or f"{repo.owner}/{repo.name}",
        "provider": repo.provider,
        "default_branch": repo.default_branch,
        "clone_url": repo.clone_url,
        "private": repo.private,
        "connection_status": repo.connection_status,
        "github_installation_id": repo.github_installation_id,
        "github_repository_id": repo.github_repository_id,
        "permissions_snapshot": repo.permissions_snapshot or {},
        "last_webhook_received_at": repo.last_webhook_received_at,
        "last_indexed_at": repo.last_indexed_at,
        "created_at": repo.created_at,
        "updated_at": repo.updated_at,
    }

    health_data = {
        "connection_status": repo.connection_status,
        "code_intelligence": {
            "status": "indexed" if repo.last_indexed_at else "not_indexed",
            "last_indexed_at": repo.last_indexed_at,
        },
        "last_webhook_received_at": repo.last_webhook_received_at,
        "active_incidents_count": active_incidents,
        "recent_investigations_count": total_investigations,
        "recent_repairs_count": total_repairs,
        "recent_pull_requests_count": total_prs,
    }

    return RepositoryDetailResponse(
        repository=repo_data,
        installation=installation_info,
        health=health_data,
    )
