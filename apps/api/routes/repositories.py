from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.auth import CurrentUser, get_current_user
from database.connection import get_db_session
from database.models import Repository

router = APIRouter(prefix="/repositories", tags=["Repositories"])


class RepositoryCreate(BaseModel):
    owner: str = Field(..., examples=["shreyvirmani"])
    name: str = Field(..., examples=["Devaura"])
    provider: str = Field(default="github", examples=["github"])
    default_branch: str = Field(default="main", examples=["main"])
    clone_url: str = Field(..., examples=["https://github.com/shreyvirmani/Devaura.git"])


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
    """Retrieve all monitored repositories."""
    result = await session.execute(select(Repository).order_by(Repository.updated_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(
    payload: RepositoryCreate,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> RepositoryResponse:
    """Register a new repository for Devaura monitoring."""
    # Check for existing repository
    existing = await session.execute(
        select(Repository).where(
            Repository.owner == payload.owner,
            Repository.name == payload.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repository {payload.owner}/{payload.name} is already registered.",
        )

    repo = Repository(
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
    """Retrieve details for a single repository."""
    result = await session.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repo_id} not found.",
        )
    return repo
