from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.auth import CurrentUser, get_current_user
from database.connection import get_db_session
from database.models import AgentState, Evidence, Investigation, RepairPlan, Repository

router = APIRouter(prefix="/investigations", tags=["Investigations"])


class InvestigationCreate(BaseModel):
    repository_id: str = Field(..., description="Target repository ID")
    source_type: str = Field(..., examples=["issue"], description="issue | pr | ci_failure")
    source_id: str = Field(..., examples=["42"], description="Issue or PR number or CI run id")
    summary: Optional[str] = Field(default="", description="Optional problem summary")


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    source: str
    content: str
    metadata_json: dict[str, Any]
    created_at: datetime


class RepairPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan: dict[str, Any]
    risk_level: str
    confidence: float
    approved_at: Optional[datetime]
    created_at: datetime


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    source_type: str
    source_id: str
    status: str
    summary: str
    root_cause: Optional[str]
    confidence: Optional[float]
    created_at: datetime
    updated_at: datetime
    evidence_items: List[EvidenceResponse] = []
    repair_plans: List[RepairPlanResponse] = []


@router.get("", response_model=List[InvestigationResponse])
async def list_investigations(
    repository_id: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[InvestigationResponse]:
    """Retrieve all investigations, optionally filtered by repository."""
    query = select(Investigation).order_by(Investigation.created_at.desc())
    if repository_id:
        query = query.where(Investigation.repository_id == repository_id)
    result = await session.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=InvestigationResponse, status_code=status.HTTP_201_CREATED)
async def create_investigation(
    payload: InvestigationCreate,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> InvestigationResponse:
    """Initiate a new Devaura investigation for an issue, PR, or CI failure."""
    # Verify repository exists
    repo_res = await session.execute(select(Repository).where(Repository.id == payload.repository_id))
    repo = repo_res.scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {payload.repository_id} not found.",
        )

    investigation = Investigation(
        repository_id=payload.repository_id,
        source_type=payload.source_type,
        source_id=payload.source_id,
        status=AgentState.INVESTIGATING.value,
        summary=payload.summary or f"Investigate {payload.source_type} #{payload.source_id} on {repo.name}",
    )
    session.add(investigation)
    await session.commit()
    await session.refresh(investigation)
    return investigation


@router.get("/{inv_id}", response_model=InvestigationResponse)
async def get_investigation(
    inv_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> InvestigationResponse:
    """Retrieve complete investigation details including evidence and plans."""
    result = await session.execute(
        select(Investigation).where(Investigation.id == inv_id)
    )
    investigation = result.scalar_one_or_none()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {inv_id} not found.",
        )
    return investigation


@router.post("/{inv_id}/approve")
async def approve_repair_plan(
    inv_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Human Approval Gate: Authorize execution of the repair plan in sandbox."""
    result = await session.execute(
        select(Investigation).where(Investigation.id == inv_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    if inv.status not in [AgentState.PLAN_READY.value, AgentState.WAITING_FOR_APPROVAL.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve investigation in state '{inv.status}'. Must be PLAN_READY or WAITING_FOR_APPROVAL.",
        )

    inv.status = AgentState.REPAIRING.value
    await session.commit()
    return {
        "investigation_id": inv_id,
        "status": inv.status,
        "message": "Repair plan approved. Agent transitioning to REPAIRING in isolated sandbox.",
        "approved_by": user.email,
    }


@router.post("/{inv_id}/reject")
async def reject_repair_plan(
    inv_id: str,
    reason: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Human Approval Gate: Reject the proposed repair plan."""
    result = await session.execute(
        select(Investigation).where(Investigation.id == inv_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    inv.status = AgentState.IDLE.value
    await session.commit()
    return {
        "investigation_id": inv_id,
        "status": inv.status,
        "message": f"Repair plan rejected: {reason or 'No reason provided'}",
        "rejected_by": user.email,
    }
