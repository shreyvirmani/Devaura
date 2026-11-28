from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.auth import DEV_USER, CurrentUser, get_current_user
from apps.api.authorization import (
    get_user_workspace_ids,
    require_resource_workspace_access,
    resolve_user_workspace_id,
)
from database.connection import get_db_session
from database.models import Repository

router = APIRouter(prefix="/repositories", tags=["Repositories"])


class RepositoryCreate(BaseModel):
    owner: str = Field(..., examples=["shreyvirmani"])
    name: str = Field(..., examples=["Devaura"])
    provider: str = Field(default="github", examples=["github"])
    default_branch: str = Field(default="main", examples=["main"])
    clone_url: str = Field(..., examples=["https://github.com/shreyvirmani/Devaura.git"])
    workspace_id: Optional[str] = None


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner: str
    name: str
    provider: str
    default_branch: str
    clone_url: str
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=List[RepositoryResponse])
async def list_repositories(
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[RepositoryResponse]:
    """Retrieve monitored repositories scoped to the user's workspaces."""
    stmt = select(Repository).order_by(Repository.updated_at.desc())
    if not user.is_superuser and user.id != DEV_USER.id:
        ws_ids = await get_user_workspace_ids(user, session)
        if not ws_ids:
            return []
        stmt = stmt.where(Repository.workspace_id.in_(ws_ids))
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(
    payload: RepositoryCreate,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> RepositoryResponse:
    """Register a new repository for Devaura monitoring within an authorized workspace."""
    workspace_id = await resolve_user_workspace_id(payload.workspace_id, user, session)

    existing_stmt = select(Repository).where(
        Repository.owner == payload.owner,
        Repository.name == payload.name,
    )
    if workspace_id is not None:
        existing_stmt = existing_stmt.where(Repository.workspace_id == workspace_id)
    existing = await session.execute(existing_stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repository {payload.owner}/{payload.name} is already registered.",
        )

    repo = Repository(
        workspace_id=workspace_id,
        owner=payload.owner,
        name=payload.name,
        provider=payload.provider,
        default_branch=payload.default_branch,
        clone_url=payload.clone_url,
    )
    session.add(repo)
    await session.commit()
    await session.refresh(repo)
    return repo


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(
    repo_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> RepositoryResponse:
    """Retrieve details for a single repository (workspace-isolated)."""
    result = await session.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repo_id} not found.",
        )
    await require_resource_workspace_access(repo.workspace_id, user, session)
    return repo
