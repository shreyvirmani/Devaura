"""Devaura Phase 5 Repair REST API Routes.

Exposes end-to-end endpoints for:
1. Creating repairs linked to Phase 4 investigations
2. Building and validating RepairContext contracts
3. Formulating evidence-backed RepairPlans
4. Generating scoped patches and multi-dimensional risk analyses
5. Human approval and rejection gate
6. Applying approved patches inside isolated sandboxes (Phase 6 handoff)
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.repair.approval_gate import (
    ApprovalRequiredError,
    HumanApprovalGate,
    PatchIntegrityError,
)
from agent.repair.context_builder import RepairContextBuilder
from agent.repair.models import (
    ApprovalStatus,
    PatchRiskLevel,
    RepairContext,
    RepairExecutionResult,
    RepairPlan,
    RepairState,
)
from agent.repair.patch_generator import PatchGenerator, ScopeViolationError
from agent.repair.planner import RepairPlanner
from agent.repair.risk_analyzer import PatchRiskAnalyzer
from agent.repair.state_machine import (
    InvalidRepairStateTransitionError,
    RepairStateMachine,
)
from apps.api.auth import CurrentUser, get_current_user
from apps.api.logger import logger
from database.connection import get_db_session
from database.models import (
    Investigation,
    PatchRecord,
    PatchRiskRecord,
    RepairApprovalRecord,
    RepairContextRecord,
    RepairEventRecord,
    RepairPlanRecord,
    RepairRecord,
    Repository,
)
from sandbox.isolated_runner import IsolatedRunner
from sandbox.workspace import PatchApplicationError

router = APIRouter(prefix="/repairs", tags=["Repairs"])


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------
class RepairCreateRequest(BaseModel):
    investigation_id: str
    candidate_id: Optional[str] = None
    target_branch: Optional[str] = "main"


class RepairContextRequest(BaseModel):
    candidate_id: Optional[str] = None


class RepairPlanRequest(BaseModel):
    objective: Optional[str] = None


class RepairPatchRequest(BaseModel):
    modified_contents: Optional[Dict[str, str]] = None
    explanation: Optional[str] = None


class RepairApproveRequest(BaseModel):
    patch_hash: str


class RepairRejectRequest(BaseModel):
    reason: Optional[str] = "Rejected by reviewer"


class RepairResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    investigation_id: str
    repository_id: str
    status: str
    target_branch: str
    base_revision: str
    created_at: datetime
    updated_at: datetime
    context: Optional[Dict[str, Any]] = None
    plan: Optional[Dict[str, Any]] = None
    patch: Optional[Dict[str, Any]] = None
    risk: Optional[Dict[str, Any]] = None
    approval: Optional[Dict[str, Any]] = None
    workspace: Optional[Dict[str, Any]] = None


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
async def record_event(
    session: AsyncSession,
    repair_id: str,
    event_type: str,
    description: str,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> None:
    event = RepairEventRecord(
        repair_id=repair_id,
        event_type=event_type,
        description=description,
        metadata_json=metadata_json or {},
    )
    session.add(event)


def serialize_repair(record: RepairRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "investigation_id": record.investigation_id,
        "repository_id": record.repository_id,
        "status": record.status,
        "target_branch": record.target_branch,
        "base_revision": record.base_revision,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "context": {
            "id": record.context.id,
            "candidate_id": record.context.candidate_id,
            "affected_files": record.context.affected_files,
            "affected_symbols": record.context.affected_symbols,
            "supporting_evidence_ids": record.context.supporting_evidence_ids,
            "related_tests": record.context.related_tests,
            "is_valid": record.context.is_valid,
            "validation_error": record.context.validation_error,
        }
        if record.context
        else None,
        "plan": {
            "id": record.plan.id,
            "objective": record.plan.objective,
            "root_cause": record.plan.root_cause,
            "proposed_changes": record.plan.proposed_changes,
            "tests_to_run": record.plan.tests_to_run,
            "risks": record.plan.risks,
            "confidence": record.plan.confidence,
        }
        if record.plan
        else None,
        "patch": {
            "id": record.patch.id,
            "patch_hash": record.patch.patch_hash,
            "changed_files": record.patch.changed_files,
            "lines_added": record.patch.lines_added,
            "lines_removed": record.patch.lines_removed,
            "explanation": record.patch.explanation,
        }
        if record.patch
        else None,
        "risk": {
            "id": record.risk.id,
            "score": record.risk.score,
            "level": record.risk.level,
            "findings": record.risk.findings,
            "blocking_findings": record.risk.blocking_findings,
            "rationale": record.risk.rationale,
        }
        if record.risk
        else None,
        "approval": {
            "id": record.approval.id,
            "status": record.approval.status,
            "approved_by": record.approval.approved_by,
            "patch_hash": record.approval.patch_hash,
            "approval_token": record.approval.approval_token,
            "rejection_reason": record.approval.rejection_reason,
            "approved_at": record.approval.approved_at,
        }
        if record.approval
        else None,
        "workspace": {
            "id": record.workspace.id,
            "isolated_path": record.workspace.isolated_path,
            "status": record.workspace.status,
        }
        if record.workspace
        else None,
    }


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_repair(
    body: RepairCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Initialize a new repair lifecycle linked to an investigation."""
    inv_res = await session.execute(
        select(Investigation).where(Investigation.id == body.investigation_id)
    )
    inv = inv_res.scalar_one_or_none()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{body.investigation_id}' not found.",
        )

    repair = RepairRecord(
        investigation_id=inv.id,
        repository_id=inv.repository_id,
        status=RepairState.CREATED.value,
        target_branch=body.target_branch or "main",
        base_revision=inv.commit_sha or "HEAD",
    )
    session.add(repair)
    await session.flush()

    await record_event(
        session,
        repair_id=repair.id,
        event_type="REPAIR_CREATED",
        description=f"Repair initiated for investigation {inv.id} by {user.email}",
    )
    await session.commit()
    await session.refresh(repair)

    return serialize_repair(repair)


@router.get("", response_model=List[Dict[str, Any]])
async def list_repairs(
    investigation_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List repairs with optional investigation_id filter."""
    stmt = select(RepairRecord).order_by(desc(RepairRecord.created_at))
    if investigation_id:
        stmt = stmt.where(RepairRecord.investigation_id == investigation_id)
    result = await session.execute(stmt)
    repairs = list(result.scalars().all())
    return [serialize_repair(r) for r in repairs]


@router.get("/{repair_id}", response_model=Dict[str, Any])
async def get_repair(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve full details of a repair attempt."""
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repair '{repair_id}' not found.",
        )
    return serialize_repair(repair)


@router.post("/{repair_id}/context", response_model=Dict[str, Any])
async def build_repair_context(
    repair_id: str,
    body: Optional[RepairContextRequest] = None,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Build and validate RepairContext from Phase 4 investigation evidence."""
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")

    sm = RepairStateMachine(repair.status)
    try:
        sm.transition(RepairState.CONTEXT_BUILDING)
        repair.status = sm.current_state.value
        await session.commit()
    except InvalidRepairStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    inv_res = await session.execute(
        select(Investigation).where(Investigation.id == repair.investigation_id)
    )
    inv = inv_res.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Linked investigation not found")

    # Fetch repository clone path or fallback to current workspace
    repo_res = await session.execute(
        select(Repository).where(Repository.id == repair.repository_id)
    )
    repo = repo_res.scalar_one_or_none()
    workspace_root = os.getcwd()

    builder = RepairContextBuilder(workspace_root=workspace_root)
    candidate_id = body.candidate_id if body else None
    is_valid, ctx, err = builder.validate_and_build(
        investigation=inv,
        selected_candidate_id=candidate_id,
        repair_id=repair.id,
    )

    if not is_valid or not ctx:
        sm.transition(RepairState.REPAIR_BLOCKED_INSUFFICIENT_EVIDENCE)
        repair.status = sm.current_state.value
        context_rec = RepairContextRecord(
            repair_id=repair.id,
            investigation_id=inv.id,
            candidate_id=candidate_id or "unknown",
            affected_files=[],
            affected_symbols=[],
            supporting_evidence_ids=[],
            related_tests=[],
            context_data={},
            is_valid=False,
            validation_error=err,
        )
        session.add(context_rec)
        await record_event(
            session,
            repair_id=repair.id,
            event_type="CONTEXT_BUILD_BLOCKED",
            description=f"Context building blocked: {err}",
        )
        await session.commit()
        return {
            "status": repair.status,
            "is_valid": False,
            "error": err,
        }

    sm.transition(RepairState.CONTEXT_READY)
    repair.status = sm.current_state.value

    # Persist context record
    context_rec = RepairContextRecord(
        repair_id=repair.id,
        investigation_id=inv.id,
        candidate_id=ctx.selected_root_cause.get("candidate_id", "c-1"),
        affected_files=ctx.affected_files,
        affected_symbols=ctx.affected_symbols,
        supporting_evidence_ids=[
            e.get("evidence_id") for e in ctx.supporting_evidence if e.get("evidence_id")
        ],
        related_tests=ctx.related_tests,
        context_data=ctx.model_dump(mode="json"),
        is_valid=True,
        validation_error=None,
    )
    session.add(context_rec)
    await record_event(
        session,
        repair_id=repair.id,
        event_type="CONTEXT_READY",
        description=f"Repair context ready. Affected files: {ctx.affected_files}",
    )
    await session.commit()
    await session.refresh(repair)

    return serialize_repair(repair)


@router.post("/{repair_id}/plan", response_model=Dict[str, Any])
async def generate_repair_plan(
    repair_id: str,
    body: Optional[RepairPlanRequest] = None,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Formulate an evidence-backed RepairPlan from the ready context."""
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")

    if not repair.context or not repair.context.is_valid:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate plan: Valid RepairContext is missing or failed validation.",
        )

    sm = RepairStateMachine(repair.status)
    try:
        sm.transition(RepairState.PLANNING)
        repair.status = sm.current_state.value
        await session.commit()
    except InvalidRepairStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ctx = RepairContext.model_validate(repair.context.context_data)
    planner = RepairPlanner()
    try:
        plan = planner.create_plan(
            context=ctx,
            custom_objective=body.objective if body else None,
        )
    except Exception as e:
        sm.transition(RepairState.PLAN_FAILED)
        repair.status = sm.current_state.value
        await record_event(session, repair.id, "PLAN_FAILED", f"Plan generation error: {e}")
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {e}")

    sm.transition(RepairState.PLAN_READY)
    repair.status = sm.current_state.value

    plan_rec = RepairPlanRecord(
        repair_id=repair.id,
        objective=plan.objective,
        root_cause=plan.root_cause,
        proposed_changes=[c.model_dump(mode="json") for c in plan.proposed_changes],
        tests_to_run=plan.tests_to_run,
        risks=plan.risks,
        assumptions=plan.assumptions,
        confidence=plan.confidence,
    )
    session.add(plan_rec)
    await record_event(
        session,
        repair_id=repair.id,
        event_type="PLAN_READY",
        description=f"Repair plan generated with {len(plan.proposed_changes)} proposed change(s).",
    )
    await session.commit()
    await session.refresh(repair)

    return serialize_repair(repair)


@router.post("/{repair_id}/patch", response_model=Dict[str, Any])
async def generate_patch(
    repair_id: str,
    body: Optional[RepairPatchRequest] = None,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate scoped patch diff and run multi-dimensional static risk analysis."""
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")

    if not repair.plan or not repair.context:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate patch without valid RepairContext and RepairPlan.",
        )

    sm = RepairStateMachine(repair.status)
    try:
        sm.transition(RepairState.PATCH_GENERATING)
        repair.status = sm.current_state.value
        await session.commit()
    except InvalidRepairStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ctx = RepairContext.model_validate(repair.context.context_data)
    plan = RepairPlan(
        repair_id=repair.id,
        investigation_id=repair.investigation_id,
        objective=repair.plan.objective,
        root_cause=repair.plan.root_cause,
        affected_files=repair.context.affected_files,
        affected_symbols=repair.context.affected_symbols,
        proposed_changes=[],
        tests_to_run=repair.plan.tests_to_run,
        risks=repair.plan.risks,
        assumptions=repair.plan.assumptions,
        confidence=repair.plan.confidence,
    )

    workspace_root = os.getcwd()
    generator = PatchGenerator(workspace_root=workspace_root)

    try:
        if body and body.modified_contents:
            patch_result = generator.generate_from_content_map(
                plan=plan,
                context=ctx,
                modified_contents=body.modified_contents,
                explanation=body.explanation,
            )
        else:
            patch_result = generator.generate_defensive_patch(plan=plan, context=ctx)
    except ScopeViolationError as sve:
        sm.transition(RepairState.PATCH_FAILED)
        repair.status = sm.current_state.value
        await record_event(session, repair.id, "PATCH_SCOPE_VIOLATION", str(sve))
        await session.commit()
        raise HTTPException(status_code=400, detail=f"Patch scope violation: {sve}")
    except Exception as e:
        sm.transition(RepairState.PATCH_FAILED)
        repair.status = sm.current_state.value
        await record_event(session, repair.id, "PATCH_FAILED", str(e))
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Patch generation failed: {e}")

    sm.transition(RepairState.PATCH_READY)

    # Static Risk Analysis
    risk_analyzer = PatchRiskAnalyzer()
    risk_result = risk_analyzer.analyze(patch_result, plan, ctx)

    sm.transition(RepairState.RISK_ANALYZED)

    if risk_result.blocking_findings or risk_result.level == PatchRiskLevel.CRITICAL:
        sm.transition(RepairState.RISK_BLOCKED)
        repair.status = sm.current_state.value
    else:
        sm.transition(RepairState.AWAITING_APPROVAL)
        repair.status = sm.current_state.value

    # Persist patch and risk
    patch_rec = PatchRecord(
        repair_id=repair.id,
        unified_diff=patch_result.unified_diff,
        patch_hash=patch_result.patch_hash,
        changed_files=patch_result.changed_files,
        lines_added=patch_result.lines_added,
        lines_removed=patch_result.lines_removed,
        explanation=patch_result.explanation,
        model_metadata=patch_result.model_metadata,
    )
    session.add(patch_rec)

    risk_rec = PatchRiskRecord(
        repair_id=repair.id,
        score=risk_result.score,
        level=risk_result.level.value,
        findings=[f.model_dump(mode="json") for f in risk_result.findings],
        blocking_findings=risk_result.blocking_findings,
        rationale=risk_result.rationale,
    )
    session.add(risk_rec)

    # Also prepare pending approval record
    approval_rec = RepairApprovalRecord(
        repair_id=repair.id,
        patch_hash=patch_result.patch_hash,
        status=ApprovalStatus.PENDING.value,
    )
    session.add(approval_rec)

    await record_event(
        session,
        repair_id=repair.id,
        event_type="PATCH_AND_RISK_READY",
        description=f"Patch {patch_result.patch_hash[:8]} generated. Risk: {risk_result.level.value}.",
    )
    await session.commit()
    await session.refresh(repair)

    return serialize_repair(repair)


@router.get("/{repair_id}/risk", response_model=Dict[str, Any])
async def get_patch_risk(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Inspect static risk evaluation of proposed patch."""
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair or not repair.risk:
        raise HTTPException(status_code=404, detail="Risk evaluation not found for repair")

    return {
        "repair_id": repair.id,
        "score": repair.risk.score,
        "level": repair.risk.level,
        "findings": repair.risk.findings,
        "blocking_findings": repair.risk.blocking_findings,
        "rationale": repair.risk.rationale,
    }


@router.get("/{repair_id}/diff", response_model=Dict[str, Any])
async def get_repair_diff(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve full unified diff and changed files for review."""
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair or not repair.patch:
        raise HTTPException(status_code=404, detail="Patch not found for repair")

    return {
        "repair_id": repair.id,
        "patch_hash": repair.patch.patch_hash,
        "changed_files": repair.patch.changed_files,
        "lines_added": repair.patch.lines_added,
        "lines_removed": repair.patch.lines_removed,
        "explanation": repair.patch.explanation,
        "unified_diff": repair.patch.unified_diff,
    }


@router.post("/{repair_id}/approve", response_model=Dict[str, Any])
async def approve_repair(
    repair_id: str,
    body: RepairApproveRequest,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Human Approval Gate: Grant authorization bound to exact patch SHA-256."""
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair or not repair.patch:
        raise HTTPException(status_code=404, detail="Repair or patch not found")

    # Guard: State check
    sm = RepairStateMachine(repair.status)
    try:
        sm.transition(RepairState.APPROVED)
    except InvalidRepairStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    gate = HumanApprovalGate()
    try:
        approval_domain = gate.create_approval(
            repair_id=repair.id,
            unified_diff=repair.patch.unified_diff,
            user_identity=user.email,
        )
    except ApprovalRequiredError as are:
        raise HTTPException(status_code=403, detail=str(are))

    # Guard: Cryptographic hash match
    if body.patch_hash != repair.patch.patch_hash:
        raise HTTPException(
            status_code=400,
            detail=f"Approval hash '{body.patch_hash}' does not match patch hash '{repair.patch.patch_hash}'.",
        )

    repair.status = RepairState.APPROVED.value

    # Update or insert approval record
    if repair.approval:
        repair.approval.status = ApprovalStatus.APPROVED.value
        repair.approval.approved_by = user.email
        repair.approval.patch_hash = repair.patch.patch_hash
        repair.approval.approval_token = approval_domain.approval_token
        repair.approval.approved_at = datetime.now()
    else:
        approval_rec = RepairApprovalRecord(
            repair_id=repair.id,
            patch_hash=repair.patch.patch_hash,
            status=ApprovalStatus.APPROVED.value,
            approved_by=user.email,
            approval_token=approval_domain.approval_token,
            approved_at=datetime.now(),
        )
        session.add(approval_rec)

    await record_event(
        session,
        repair_id=repair.id,
        event_type="REPAIR_APPROVED",
        description=f"Repair approved by {user.email} (token: {approval_domain.approval_token[:8]})",
    )
    await session.commit()
    await session.refresh(repair)

    return serialize_repair(repair)


@router.post("/{repair_id}/reject", response_model=Dict[str, Any])
async def reject_repair(
    repair_id: str,
    body: Optional[RepairRejectRequest] = None,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Human Review: Explicitly reject proposed repair with audit reason."""
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")

    sm = RepairStateMachine(repair.status)
    try:
        sm.transition(RepairState.REJECTED)
        repair.status = sm.current_state.value
    except InvalidRepairStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    reason = body.reason if body else "Rejected by human reviewer"
    if repair.approval:
        repair.approval.status = ApprovalStatus.REJECTED.value
        repair.approval.rejection_reason = reason
    else:
        approval_rec = RepairApprovalRecord(
            repair_id=repair.id,
            patch_hash=repair.patch.patch_hash if repair.patch else "no-patch",
            status=ApprovalStatus.REJECTED.value,
            approved_by=user.email,
            rejection_reason=reason,
        )
        session.add(approval_rec)

    await record_event(
        session,
        repair_id=repair.id,
        event_type="REPAIR_REJECTED",
        description=f"Repair rejected by {user.email}: {reason}",
    )
    await session.commit()
    await session.refresh(repair)

    return serialize_repair(repair)


@router.post("/{repair_id}/apply", response_model=Dict[str, Any])
async def apply_approved_patch(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Apply approved patch strictly inside isolated sandbox workspace.

    Original source repository is untouched. Transitions to Phase 6 handoff state:
    PATCH_APPLIED_PENDING_VERIFICATION.
    """
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair or not repair.patch or not repair.approval:
        raise HTTPException(
            status_code=400,
            detail="Cannot apply patch: Approved patch and authorization record required.",
        )

    # 1. State machine check
    sm = RepairStateMachine(repair.status)
    try:
        sm.transition(RepairState.APPLYING)
        repair.status = sm.current_state.value
        await session.commit()
    except InvalidRepairStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Cryptographic authorization verification
    gate = HumanApprovalGate()
    try:
        from agent.repair.models import RepairApproval
        approval_domain = RepairApproval(
            repair_id=repair.id,
            patch_hash=repair.approval.patch_hash,
            approved_by=repair.approval.approved_by or "unknown",
            status=ApprovalStatus(repair.approval.status),
            approval_token=repair.approval.approval_token,
        )
        gate.verify_authorization(approval_domain, repair.patch.unified_diff)
    except PatchIntegrityError as pie:
        sm.transition(RepairState.PATCH_CHANGED)
        repair.status = sm.current_state.value
        await record_event(session, repair.id, "PATCH_CHANGED", str(pie))
        await session.commit()
        raise HTTPException(status_code=409, detail=str(pie))
    except ApprovalRequiredError as are:
        raise HTTPException(status_code=403, detail=str(are))

    # 3. Apply inside isolated sandbox runner
    workspace_root = os.getcwd()
    runner = IsolatedRunner()

    try:
        from agent.repair.models import PatchResult
        patch_domain = PatchResult(
            status="GENERATED",
            unified_diff=repair.patch.unified_diff,
            patch_hash=repair.patch.patch_hash,
            changed_files=repair.patch.changed_files,
            lines_added=repair.patch.lines_added,
            lines_removed=repair.patch.lines_removed,
            explanation=repair.patch.explanation,
        )
        exec_res: RepairExecutionResult = runner.run_patch_application(
            repair_id=repair.id,
            investigation_id=repair.investigation_id,
            repository_id=repair.repository_id,
            source_repo_path=workspace_root,
            patch=patch_domain,
            base_revision=repair.base_revision,
        )
    except PatchApplicationError as pae:
        sm.transition(RepairState.APPLICATION_FAILED)
        repair.status = sm.current_state.value
        await record_event(session, repair.id, "APPLICATION_FAILED", str(pae))
        await session.commit()
        raise HTTPException(status_code=500, detail=str(pae))

    sm.transition(RepairState.PATCH_APPLIED_PENDING_VERIFICATION)
    repair.status = sm.current_state.value

    # Persist workspace record
    from database.models import RepairWorkspaceRecord
    ws_rec = RepairWorkspaceRecord(
        repair_id=repair.id,
        isolated_path=exec_res.isolated_path,
        base_revision=exec_res.base_revision,
        status="APPLIED",
    )
    session.add(ws_rec)

    await record_event(
        session,
        repair_id=repair.id,
        event_type="PATCH_APPLIED",
        description=f"Patch applied in isolated sandbox {exec_res.workspace_id}. Handoff to Phase 6 ready.",
    )
    await session.commit()
    await session.refresh(repair)

    return {
        "repair": serialize_repair(repair),
        "execution_result": exec_res.model_dump(mode="json"),
    }
