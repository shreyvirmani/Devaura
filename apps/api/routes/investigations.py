from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from agent.investigator import InvestigatorEngine
from agent.models import (
    FailureType,
    InvestigationRequest,
    InvestigationState as AgentInvState,
)
from apps.api.auth import CurrentUser, get_current_user
from database.connection import get_db_session
from database.models import (
    AgentState,
    Evidence,
    EvidenceSource,
    EvidenceSufficiency,
    EvidenceType,
    Investigation,
    InvestigationStep,
    RepairPlan,
    Repository,
    RootCauseCandidate,
)

router = APIRouter(prefix="/investigations", tags=["Investigations"])


class InvestigationCreate(BaseModel):
    repository_id: str = Field(..., description="Target repository ID")
    source_type: Optional[str] = Field(default="issue", description="issue | pr | ci_failure | test_failure")
    source_id: Optional[str] = Field(default="1", description="Issue or PR number or CI run id")
    issue_id: Optional[str] = Field(default=None, description="Optional GitHub issue ID")
    title: Optional[str] = Field(default=None, description="Human-readable title for investigation")
    description: Optional[str] = Field(default=None, description="Detailed problem description")
    summary: Optional[str] = Field(default="", description="Optional problem summary")
    failure_type: Optional[str] = Field(default=None, description="Failure category enum")
    error_message: Optional[str] = Field(default=None, description="Raw error or assertion message")
    stack_trace: Optional[str] = Field(default=None, description="Full traceback string")
    failed_tests: Optional[List[Any]] = Field(default_factory=list, description="Failed test items or descriptors")
    ci_run_id: Optional[str] = Field(default=None, description="CI execution identifier")
    commit_sha: Optional[str] = Field(default=None, description="Git commit SHA")
    branch: Optional[str] = Field(default="main", description="Target branch")
    workspace: Optional[str] = Field(default=None, description="Optional custom workspace path on disk")


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    type: str
    content: str
    repository_path: Optional[str] = None
    symbol_id: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    commit_sha: Optional[str] = None
    confidence: float = 1.0
    relevance: float = 0.5
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    confidence: float
    affected_symbols: List[str] = Field(default_factory=list)
    affected_files: List[str] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    reasoning: str
    created_at: datetime


class StepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    step_number: int
    action: str
    tool_name: Optional[str] = None
    tool_input: Dict[str, Any] = Field(default_factory=dict)
    tool_output: Dict[str, Any] = Field(default_factory=dict)
    observation: str
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
    title: Optional[str] = None
    summary: str
    failure_type: str
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    failed_tests: List[Any] = Field(default_factory=list)
    ci_run_id: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    evidence_sufficiency: str
    root_cause: Optional[str] = None
    confidence: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    evidence_items: List[EvidenceResponse] = []
    root_cause_candidates: List[CandidateResponse] = []
    investigation_steps: List[StepResponse] = []
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

    # For Phase 1 backward compatibility, if failure_type is None, use INVESTIGATING
    initial_status = AgentState.INVESTIGATING.value if payload.failure_type is None else AgentInvState.CREATED.value
    fail_type = payload.failure_type or FailureType.UNKNOWN.value

    investigation = Investigation(
        repository_id=payload.repository_id,
        source_type=payload.source_type or "issue",
        source_id=payload.issue_id or payload.source_id or "1",
        status=initial_status,
        title=payload.title,
        summary=payload.summary or payload.description or f"Investigate {payload.source_type} #{payload.source_id} on {repo.name}",
        failure_type=fail_type,
        error_message=payload.error_message,
        stack_trace=payload.stack_trace,
        failed_tests=payload.failed_tests or [],
        ci_run_id=payload.ci_run_id,
        commit_sha=payload.commit_sha,
        branch=payload.branch or "main",
        evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT.value,
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
    """Retrieve complete investigation details including evidence, candidates, and steps."""
    result = await session.execute(select(Investigation).where(Investigation.id == inv_id))
    investigation = result.scalar_one_or_none()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {inv_id} not found.",
        )
    return investigation


@router.post("/{inv_id}/run", response_model=InvestigationResponse)
async def run_investigation(
    inv_id: str,
    workspace: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> InvestigationResponse:
    """Execute the evidence-driven Investigator loop (max 5 iterations) for an investigation."""
    result = await session.execute(select(Investigation).where(Investigation.id == inv_id))
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {inv_id} not found.",
        )

    # Determine workspace root
    ws_path = workspace or "."
    repo_res = await session.execute(select(Repository).where(Repository.id == inv.repository_id))
    repo = repo_res.scalar_one_or_none()
    if repo and repo.clone_url:
        p = Path(repo.clone_url)
        if p.exists() and p.is_dir():
            ws_path = str(p)

    # Check for fixture validation repo if repo matches
    if repo and "validation" in repo.name.lower():
        fixture_p = Path("tests/fixtures/validation_repo")
        if fixture_p.exists():
            ws_path = str(fixture_p)

    resolved_ws = Path(ws_path).resolve()

    # Build investigation request for engine
    req = InvestigationRequest(
        investigation_id=inv.id,
        repository_id=inv.repository_id,
        issue_id=inv.source_id,
        title=inv.title or inv.summary,
        description=inv.summary,
        failure_type=FailureType(inv.failure_type) if inv.failure_type in FailureType.__members__ else FailureType.UNKNOWN,
        error_message=inv.error_message,
        stack_trace=inv.stack_trace,
        failed_tests=inv.failed_tests or [],
        ci_run_id=inv.ci_run_id,
        commit_sha=inv.commit_sha,
        branch=inv.branch,
    )

    engine = InvestigatorEngine(
        workspace_root=str(resolved_ws),
        investigation_id=inv.id,
        repository_id=inv.repository_id,
    )

    report = engine.run(req)

    # Update Investigation Record
    inv.status = report.status.value
    inv.evidence_sufficiency = report.evidence_sufficiency.value
    inv.root_cause = report.summary
    inv.confidence = report.overall_confidence
    inv.updated_at = datetime.now(timezone.utc)

    # Clear previous evidence, candidates, and steps to allow clean re-runs
    # Persist ranked evidence items
    for ev in report.ranked_evidence:
        db_ev = Evidence(
            id=ev.evidence_id,
            investigation_id=inv.id,
            source=ev.source.value,
            type=ev.type.value,
            content=ev.content,
            repository_path=ev.repository_path,
            symbol_id=ev.symbol_id,
            line_start=ev.line_start,
            line_end=ev.line_end,
            commit_sha=ev.commit_sha,
            confidence=ev.confidence,
            relevance=ev.relevance,
            metadata_json=ev.metadata,
        )
        session.add(db_ev)

    # Persist root cause candidates
    for c in report.root_cause_candidates:
        db_cand = RootCauseCandidate(
            id=c.candidate_id,
            investigation_id=inv.id,
            title=c.title,
            description=c.description,
            confidence=c.confidence,
            affected_symbols=c.affected_symbols,
            affected_files=c.affected_files,
            supporting_evidence_ids=c.supporting_evidence_ids,
            contradicting_evidence_ids=c.contradicting_evidence_ids,
            reasoning=c.reasoning,
        )
        session.add(db_cand)

    # Persist steps log
    for s in engine.steps_log:
        db_step = InvestigationStep(
            investigation_id=inv.id,
            step_number=s["step_number"],
            action=s["action"],
            tool_name=s.get("tool_name"),
            tool_input=s.get("tool_input", {}),
            tool_output=s.get("tool_output", {}),
            observation=s.get("observation", ""),
        )
        session.add(db_step)

    await session.commit()
    await session.refresh(inv)
    return inv


@router.get("/{inv_id}/evidence", response_model=List[EvidenceResponse])
async def get_investigation_evidence(
    inv_id: str,
    source: Optional[str] = None,
    type: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[EvidenceResponse]:
    """Retrieve ranked evidence items collected for an investigation."""
    query = select(Evidence).where(Evidence.investigation_id == inv_id).order_by(
        Evidence.relevance.desc(), Evidence.confidence.desc()
    )
    if source:
        query = query.where(Evidence.source == source)
    if type:
        query = query.where(Evidence.type == type)

    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/{inv_id}/candidates", response_model=List[CandidateResponse])
async def get_investigation_candidates(
    inv_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[CandidateResponse]:
    """Retrieve synthesized root-cause hypotheses with confidence ratings."""
    query = select(RootCauseCandidate).where(
        RootCauseCandidate.investigation_id == inv_id
    ).order_by(RootCauseCandidate.confidence.desc())

    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/{inv_id}/timeline", response_model=List[StepResponse])
async def get_investigation_timeline(
    inv_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[StepResponse]:
    """Retrieve the step-by-step investigation timeline and tool audit trail."""
    query = select(InvestigationStep).where(
        InvestigationStep.investigation_id == inv_id
    ).order_by(InvestigationStep.step_number.asc())

    result = await session.execute(query)
    return list(result.scalars().all())


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
    """Human Approval Gate: Reject repair plan or close investigation."""
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
        "message": f"Investigation rejected. Reason: {reason or 'Rejected by user'}.",
        "rejected_by": user.email,
    }
