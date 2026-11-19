from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.auth import CurrentUser, get_current_user
from database.connection import get_db_session
from database.models import (
    AgentState,
    Investigation,
    PullRequest,
    RepairAttempt,
    VerificationRun,
)

router = APIRouter(prefix="/repairs", tags=["Repairs"])


class VerificationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    test_status: str
    lint_status: str
    typecheck_status: str
    security_status: str
    test_output: str
    created_at: datetime


class RepairAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str
    attempt_number: int
    status: str
    patch: str
    test_results: dict[str, Any]
    error: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    verification_runs: List[VerificationRunResponse] = []


@router.get("/{repair_id}", response_model=RepairAttemptResponse)
async def get_repair(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> RepairAttemptResponse:
    """Retrieve details of a repair attempt."""
    result = await session.execute(
        select(RepairAttempt).where(RepairAttempt.id == repair_id)
    )
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Repair attempt not found")
    return attempt


@router.get("/{repair_id}/diff")
async def get_repair_diff(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Inspect unified diff and semantic explanations for this repair attempt."""
    result = await session.execute(
        select(RepairAttempt).where(RepairAttempt.id == repair_id)
    )
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Repair attempt not found")

    return {
        "repair_id": attempt.id,
        "attempt_number": attempt.attempt_number,
        "patch": attempt.patch,
        "has_changes": bool(attempt.patch.strip()),
    }


@router.get("/{repair_id}/verification")
async def get_repair_verification(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve normalized verification results (test, lint, typecheck)."""
    result = await session.execute(
        select(VerificationRun).where(VerificationRun.repair_attempt_id == repair_id)
    )
    runs = list(result.scalars().all())
    return {
        "repair_id": repair_id,
        "runs": runs,
    }


@router.post("/{repair_id}/approve")
async def approve_pr_creation(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Human Approval Gate: Explicitly authorize publishing fix branch & opening PR."""
    result = await session.execute(
        select(RepairAttempt).where(RepairAttempt.id == repair_id)
    )
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Repair attempt not found")

    # Fetch investigation
    inv_res = await session.execute(
        select(Investigation).where(Investigation.id == attempt.investigation_id)
    )
    inv = inv_res.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    inv.status = AgentState.PR_CREATED.value
    await session.commit()

    return {
        "repair_id": repair_id,
        "investigation_id": inv.id,
        "status": inv.status,
        "message": "Approved for Pull Request creation. Git branch will be pushed and PR submitted.",
        "approved_by": user.email,
    }
