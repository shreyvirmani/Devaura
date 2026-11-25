"""Devaura Authentication Endpoints.

Handles User Signup, Login, Session Verification, and Current User resolution.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import (
    CurrentUser,
    create_auth_error,
    get_current_user_optional,
    require_authenticated_user,
)
from apps.api.security import create_access_token, hash_password, verify_password
from database.connection import get_db
from database.models import AuditEventRecord, User, Workspace, WorkspaceMember, WorkspaceRole

router = APIRouter(prefix="/auth", tags=["Authentication"])


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    name: str = Field(..., min_length=2, max_length=100)
    workspace_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class WorkspaceSummary(BaseModel):
    id: str
    name: str
    slug: str
    role: str
    is_owner: bool


class UserProfileResponse(BaseModel):
    id: str
    email: str
    name: str
    is_superuser: bool
    workspaces: List[WorkspaceSummary]


class AuthSuccessResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse
    default_workspace_id: str


def slugify(text: str) -> str:
    """Generate a clean URL slug from text."""
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug or "workspace"


@router.post("/signup", response_model=AuthSuccessResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignUpRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user, create their initial workspace, and issue an access token."""
    # Check if user already exists
    existing_stmt = select(User).where(User.email == payload.email.lower())
    result = await db.execute(existing_stmt)
    if result.scalar_one_or_none():
        raise create_auth_error(
            status.HTTP_409_CONFLICT,
            "EMAIL_ALREADY_EXISTS",
            "An account with this email address already exists.",
        )

    # 1. Create User
    new_user = User(
        email=payload.email.lower(),
        name=payload.name.strip(),
        hashed_password=hash_password(payload.password),
        is_active=True,
        is_superuser=False,
    )
    db.add(new_user)
    await db.flush()

    # 2. Create Initial Workspace
    ws_name = payload.workspace_name.strip() if payload.workspace_name else f"{new_user.name}'s Workspace"
    base_slug = slugify(ws_name)
    slug = f"{base_slug}-{new_user.id[:6]}"

    workspace = Workspace(
        name=ws_name,
        slug=slug,
        owner_id=new_user.id,
        is_active=True,
        settings={"default": True},
    )
    db.add(workspace)
    await db.flush()

    # 3. Associate Owner Membership
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=new_user.id,
        role=WorkspaceRole.OWNER.value,
    )
    db.add(member)

    # 4. Record Audit Event
    audit = AuditEventRecord(
        workspace_id=workspace.id,
        actor_id=new_user.id,
        actor_email=new_user.email,
        action="user.signup",
        resource_type="user",
        resource_id=new_user.id,
        outcome="SUCCESS",
        details={"workspace_id": workspace.id, "workspace_name": ws_name},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)
    await db.commit()

    # 5. Issue JWT
    token = create_access_token(subject=new_user.id, email=new_user.email)
    from apps.api.config import get_settings
    response.set_cookie(
        key="devaura_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=get_settings().is_staging_or_production or request.url.scheme == "https",
        max_age=86400,
    )

    return AuthSuccessResponse(
        access_token=token,
        token_type="bearer",
        user=UserProfileResponse(
            id=new_user.id,
            email=new_user.email,
            name=new_user.name,
            is_superuser=new_user.is_superuser,
            workspaces=[
                WorkspaceSummary(
                    id=workspace.id,
                    name=workspace.name,
                    slug=workspace.slug,
                    role=WorkspaceRole.OWNER.value,
                    is_owner=True,
                )
            ],
        ),
        default_workspace_id=workspace.id,
    )


@router.post("/login", response_model=AuthSuccessResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password, issuing a session JWT."""
    stmt = select(User).where(User.email == payload.email.lower())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise create_auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_CREDENTIALS",
            "Invalid email or password.",
        )

    if not verify_password(payload.password, user.hashed_password):
        # Record failed login audit event if user exists
        audit = AuditEventRecord(
            workspace_id=None,
            actor_id=user.id,
            actor_email=user.email,
            action="user.login_failed",
            resource_type="user",
            resource_id=user.id,
            outcome="DENIED",
            details={"reason": "incorrect_password"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
        db.add(audit)
        await db.commit()

        raise create_auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_CREDENTIALS",
            "Invalid email or password.",
        )

    if not user.is_active:
        raise create_auth_error(
            status.HTTP_403_FORBIDDEN,
            "ACCOUNT_DISABLED",
            "This user account has been disabled.",
        )

    # Fetch user's workspaces
    ws_stmt = (
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == user.id, Workspace.is_active == True)
    )
    ws_result = await db.execute(ws_stmt)
    workspace_rows = ws_result.all()

    workspaces = [
        WorkspaceSummary(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            role=role,
            is_owner=(role == WorkspaceRole.OWNER.value),
        )
        for ws, role in workspace_rows
    ]

    default_ws_id = workspaces[0].id if workspaces else ""

    # Record successful login audit event
    audit = AuditEventRecord(
        workspace_id=default_ws_id or None,
        actor_id=user.id,
        actor_email=user.email,
        action="user.login",
        resource_type="user",
        resource_id=user.id,
        outcome="SUCCESS",
        details={"workspaces_count": len(workspaces)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(audit)
    await db.commit()

    token = create_access_token(subject=user.id, email=user.email)
    from apps.api.config import get_settings
    response.set_cookie(
        key="devaura_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=get_settings().is_staging_or_production or request.url.scheme == "https",
        max_age=86400,
    )

    return AuthSuccessResponse(
        access_token=token,
        token_type="bearer",
        user=UserProfileResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            is_superuser=user.is_superuser,
            workspaces=workspaces,
        ),
        default_workspace_id=default_ws_id,
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_me(
    current_user: CurrentUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the currently authenticated user's profile and active workspaces."""
    ws_stmt = (
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == current_user.id, Workspace.is_active == True)
    )
    ws_result = await db.execute(ws_stmt)
    workspace_rows = ws_result.all()

    workspaces = [
        WorkspaceSummary(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            role=role,
            is_owner=(role == WorkspaceRole.OWNER.value),
        )
        for ws, role in workspace_rows
    ]

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        is_superuser=current_user.is_superuser,
        workspaces=workspaces,
    )


@router.post("/logout")
async def logout(response: Response):
    """Sign out by clearing the session cookie."""
    response.delete_cookie(key="devaura_token")
    return {"status": "success", "message": "Logged out successfully."}
