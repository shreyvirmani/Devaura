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
from sqlalchemy.orm import selectinload

from agent.repair.approval_gate import (
    ApprovalRequiredError,
    HumanApprovalGate,
    PatchIntegrityError,
)
from agent.repair.context_builder import RepairContextBuilder
from agent.repair.models import (
    ApprovalStatus,
    CheckStatus,
    CheckType,
    FailureAnalysisReport,
    FailureClassification,
    OverallVerificationStatus,
    PatchRiskLevel,
    RepairContext,
    RepairExecutionResult,
    RepairPlan,
    RepairState,
    VerificationRun,
    VerifiedRepairResult,
)
from agent.repair.patch_generator import PatchGenerator, ScopeViolationError
from agent.repair.planner import RepairPlanner
from agent.repair.risk_analyzer import PatchRiskAnalyzer
from agent.repair.state_machine import (
    InvalidRepairStateTransitionError,
    RepairStateMachine,
)
from agent.repair.loop_coordinator import (
    LoopLimitExceededError,
    NoProgressError,
    RepairLoopCoordinator,
)
from agent.verification.analyzer import VerificationAnalyzer
from agent.verification.normalizer import OutputNormalizer
from agent.verification.runner import VerificationRunner
from apps.api.auth import CurrentUser, get_current_user
from apps.api.logger import logger
from database.connection import get_db_session
from database.models import (
    FailureSignatureRecord,
    Investigation,
    PatchRecord,
    PatchRiskRecord,
    RepairApprovalRecord,
    RepairAttemptRecord,
    RepairContextRecord,
    RepairEventRecord,
    RepairPlanRecord,
    RepairRecord,
    RepairWorkspaceRecord,
    Repository,
    VerificationCheckRecord,
    VerificationRunRecord,
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


class VerifyRequest(BaseModel):
    custom_commands: Optional[Dict[str, str]] = None
    timeout_seconds: Optional[int] = 120


class RepairRetryRequest(BaseModel):
    custom_modified_contents: Optional[Dict[str, str]] = None
    reason: Optional[str] = "Retrying repair after verification failure"


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
        "current_attempt": record.current_attempt,
        "max_attempts": record.max_attempts,
        "latest_verification_id": record.latest_verification_id,
    }


def serialize_verification_check(check: VerificationCheckRecord) -> Dict[str, Any]:
    return {
        "id": check.id,
        "verification_run_id": check.verification_run_id,
        "check_type": check.check_type,
        "command": check.command,
        "status": check.status,
        "exit_code": check.exit_code,
        "duration_ms": check.duration_ms,
        "stdout": check.stdout,
        "stderr": check.stderr,
        "parsed_errors": check.parsed_errors_json,
        "resource_usage": check.resource_usage_json,
        "created_at": check.created_at,
    }


def serialize_verification_run(
    run: VerificationRunRecord,
    checks: Optional[List[VerificationCheckRecord]] = None,
) -> Dict[str, Any]:
    raw_checks = checks
    if raw_checks is None:
        try:
            raw_checks = run.checks
        except Exception:
            raw_checks = []

    return {
        "id": run.id,
        "repair_id": run.repair_id,
        "attempt_number": run.attempt_number,
        "workspace_id": run.workspace_id,
        "status": run.status,
        "overall_result": run.overall_result,
        "failure_analysis": run.failure_analysis_json,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "checks": [serialize_verification_check(c) for c in (raw_checks or [])],
    }


def serialize_repair_attempt(attempt: RepairAttemptRecord) -> Dict[str, Any]:
    return {
        "id": attempt.id,
        "repair_id": attempt.repair_id,
        "attempt_number": attempt.attempt_number,
        "patch_hash": attempt.patch_hash,
        "unified_diff": attempt.unified_diff,
        "approval_token": attempt.approval_token,
        "status": attempt.status,
        "created_at": attempt.created_at,
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

    # Persist or update workspace record
    if repair.workspace:
        repair.workspace.isolated_path = exec_res.isolated_path
        repair.workspace.base_revision = exec_res.base_revision
        repair.workspace.status = "APPLIED"
    else:
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


# -----------------------------------------------------------------------------
# Phase 6: Verification & Bounded Repair Loop Endpoints
# -----------------------------------------------------------------------------
@router.post("/{repair_id}/verify", response_model=Dict[str, Any])
async def verify_repair(
    repair_id: str,
    body: Optional[VerifyRequest] = None,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Execute tests, linter, and typechecker strictly inside the sandbox workspace.

    Evaluates outcomes, normalizes errors, computes failure signatures, and
    determines whether retry is eligible or bounded attempts are exhausted.
    """
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")

    if not repair.workspace or not os.path.exists(repair.workspace.isolated_path):
        raise HTTPException(
            status_code=400,
            detail="Cannot verify: Sandbox workspace does not exist or patch has not been applied.",
        )

    # 1. State machine transition to VERIFYING
    sm = RepairStateMachine(repair.status)
    try:
        sm.transition(RepairState.VERIFYING)
        repair.status = sm.current_state.value
        await session.commit()
    except InvalidRepairStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Run verification suite inside sandbox runner
    workspace_root = os.getcwd()
    runner = VerificationRunner(
        workspace_path=repair.workspace.isolated_path,
        source_repo_root=workspace_root,
    )

    custom_cmds = body.custom_commands if body else None
    timeout_secs = body.timeout_seconds if body else None

    v_run: VerificationRun = runner.run_verification_suite(
        repair_id=repair.id,
        attempt_number=repair.current_attempt,
        custom_commands=custom_cmds,
        timeout_seconds=timeout_secs,
    )

    # 3. Persist verification run record
    run_rec = VerificationRunRecord(
        id=v_run.verification_id,
        repair_id=repair.id,
        attempt_number=repair.current_attempt,
        workspace_id=v_run.workspace_id,
        status="COMPLETED",
        overall_result=v_run.overall_result,
        failure_analysis_json={},
        started_at=v_run.started_at,
        completed_at=datetime.now(),
    )
    session.add(run_rec)

    # 4. Persist individual check records
    created_check_records = []
    for c in v_run.checks:
        chk_rec = VerificationCheckRecord(
            verification_run_id=v_run.verification_id,
            check_type=c.check_type.value,
            command=c.command,
            status=c.status.value,
            exit_code=c.exit_code,
            duration_ms=c.duration_ms,
            stdout=c.stdout,
            stderr=c.stderr,
            parsed_errors_json=[pe.model_dump(mode="json") for pe in c.parsed_errors],
            resource_usage_json=c.resource_usage,
        )
        session.add(chk_rec)
        created_check_records.append(chk_rec)

    # 5. Process Outcome
    if v_run.overall_result == "PASSED":
        sm.transition(RepairState.VERIFIED)
        repair.status = sm.current_state.value
        await record_event(
            session,
            repair.id,
            "VERIFICATION_PASSED",
            f"All verification checks passed in attempt {repair.current_attempt}. Ready for Phase 7 PR handoff.",
        )
    else:
        sm.transition(RepairState.VERIFICATION_FAILED)
        sm.transition(RepairState.ANALYZING_FAILURE)

        # Retrieve prior failure signatures and patch hashes for this repair (strictly from prior attempts)
        prev_sigs_query = await session.execute(
            select(FailureSignatureRecord.signature_hash).where(
                FailureSignatureRecord.repair_id == repair.id,
                FailureSignatureRecord.attempt_number < repair.current_attempt,
            )
        )
        prev_sigs = list(prev_sigs_query.scalars().all())

        prev_hashes_query = await session.execute(
            select(RepairAttemptRecord.patch_hash).where(
                RepairAttemptRecord.repair_id == repair.id,
                RepairAttemptRecord.attempt_number < repair.current_attempt,
            )
        )
        prev_hashes = list(prev_hashes_query.scalars().all())

        analyzer = VerificationAnalyzer()
        current_patch_hash = repair.patch.patch_hash if repair.patch else ""

        analysis: FailureAnalysisReport = analyzer.analyze(
            verification_run=v_run,
            previous_signatures=prev_sigs,
            previous_patch_hashes=prev_hashes,
            current_patch_hash=current_patch_hash,
        )
        run_rec.failure_analysis_json = analysis.model_dump(mode="json")

        # Persist signature if computed
        if analysis.failure_signature and analysis.failure_signature != "no_failures_detected":
            sig_file = analysis.affected_files[0] if analysis.affected_files else ""
            sig_test = analysis.affected_symbols[0] if analysis.affected_symbols else None
            sig_check_type = "unknown"
            for c in v_run.checks:
                if c.status in {CheckStatus.FAILED, CheckStatus.INFRASTRUCTURE_ERROR, CheckStatus.TIMEOUT, CheckStatus.BLOCKED}:
                    sig_check_type = c.check_type.value
                    break

            sig_rec = FailureSignatureRecord(
                repair_id=repair.id,
                attempt_number=repair.current_attempt,
                signature_hash=analysis.failure_signature,
                check_type=sig_check_type,
                error_summary=analysis.root_cause_summary,
                file_path=sig_file,
                test_name=sig_test,
            )
            session.add(sig_rec)

        # State resolution
        if repair.current_attempt >= repair.max_attempts:
            sm.transition(RepairState.REPAIR_EXHAUSTED)
            repair.status = sm.current_state.value
            await record_event(
                session,
                repair.id,
                "REPAIR_EXHAUSTED",
                f"Maximum allowed repair attempts ({repair.max_attempts}) exhausted. Bounded loop stopped.",
            )
        elif analysis.failure_type == FailureClassification.INFRASTRUCTURE_FAILURE:
            sm.transition(RepairState.INFRASTRUCTURE_FAILURE)
            repair.status = sm.current_state.value
            await record_event(
                session,
                repair.id,
                "INFRASTRUCTURE_FAILURE",
                f"Infrastructure failure: {analysis.root_cause_summary}",
            )
        elif analysis.failure_type == FailureClassification.SECURITY_BLOCK:
            sm.transition(RepairState.VERIFICATION_BLOCKED)
            repair.status = sm.current_state.value
            await record_event(
                session,
                repair.id,
                "VERIFICATION_BLOCKED",
                f"Verification command blocked by policy: {analysis.root_cause_summary}",
            )
        elif not analysis.can_retry and "Identical" in (analysis.retry_block_reason or ""):
            sm.transition(RepairState.NO_PROGRESS)
            repair.status = sm.current_state.value
            await record_event(
                session,
                repair.id,
                "NO_PROGRESS",
                "Identical failure signature observed with no progress. Halting repair loop.",
            )
        elif analysis.can_retry:
            sm.transition(RepairState.REPAIR_RETRY_ELIGIBLE)
            repair.status = sm.current_state.value
            await record_event(
                session,
                repair.id,
                "RETRY_ELIGIBLE",
                f"Verification failed on attempt {repair.current_attempt}. Eligible for retry {repair.current_attempt + 1}/{repair.max_attempts}.",
            )
        else:
            repair.status = RepairState.VERIFICATION_FAILED.value
            await record_event(
                session,
                repair.id,
                "VERIFICATION_FAILED",
                f"Verification failed: {analysis.root_cause_summary}",
            )

    repair.latest_verification_id = run_rec.id

    # Update or add attempt record
    att_res = await session.execute(
        select(RepairAttemptRecord).where(
            RepairAttemptRecord.repair_id == repair.id,
            RepairAttemptRecord.attempt_number == repair.current_attempt,
        )
    )
    att = att_res.scalar_one_or_none()
    if not att:
        att = RepairAttemptRecord(
            repair_id=repair.id,
            attempt_number=repair.current_attempt,
            patch_hash=repair.patch.patch_hash if repair.patch else "unknown",
            unified_diff=repair.patch.unified_diff if repair.patch else "",
            approval_token=repair.approval.approval_token if repair.approval else None,
            status=repair.status,
        )
        session.add(att)
    else:
        att.status = repair.status

    await session.commit()
    await session.refresh(repair)

    return {
        "repair": serialize_repair(repair),
        "verification_run": serialize_verification_run(run_rec, checks=created_check_records),
    }


@router.get("/{repair_id}/verification", response_model=Dict[str, Any])
async def get_latest_verification(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve latest sandbox verification run and checks for repair."""
    result = await session.execute(
        select(VerificationRunRecord)
        .options(selectinload(VerificationRunRecord.checks))
        .where(VerificationRunRecord.repair_id == repair_id)
        .order_by(desc(VerificationRunRecord.started_at))
    )
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail="No verification run found for this repair")
    return serialize_verification_run(run)


@router.get("/{repair_id}/verification/history", response_model=List[Dict[str, Any]])
async def get_verification_history(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Retrieve full history of verification runs for repair across all attempts."""
    result = await session.execute(
        select(VerificationRunRecord)
        .options(selectinload(VerificationRunRecord.checks))
        .where(VerificationRunRecord.repair_id == repair_id)
        .order_by(VerificationRunRecord.started_at.asc())
    )
    runs = result.scalars().all()
    return [serialize_verification_run(r) for r in runs]


@router.get("/{repair_id}/attempts", response_model=List[Dict[str, Any]])
async def get_repair_attempts(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Retrieve all repair loop attempts with patch hashes and statuses."""
    result = await session.execute(
        select(RepairAttemptRecord)
        .where(RepairAttemptRecord.repair_id == repair_id)
        .order_by(RepairAttemptRecord.attempt_number.asc())
    )
    attempts = result.scalars().all()
    return [serialize_repair_attempt(a) for a in attempts]


@router.post("/{repair_id}/retry", response_model=Dict[str, Any])
async def retry_repair(
    repair_id: str,
    body: Optional[RepairRetryRequest] = None,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Initiate a bounded retry attempt (Attempt N+1, up to maximum 3 attempts).

    Formulates an updated repair plan and non-identical patch informed by verification
    failures, evaluates risk, and resets the mandatory human approval gate.
    """
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")

    # 1. Enforce strict maximum attempt limit
    if repair.current_attempt >= repair.max_attempts:
        sm = RepairStateMachine(repair.status)
        try:
            sm.transition(RepairState.REPAIR_EXHAUSTED)
            repair.status = sm.current_state.value
            await session.commit()
        except Exception:
            pass
        raise HTTPException(
            status_code=400,
            detail=f"Maximum repair attempts ({repair.max_attempts}) exhausted. Cannot initiate retry.",
        )

    # 2. Check retry eligibility state
    if repair.status not in {
        RepairState.REPAIR_RETRY_ELIGIBLE.value,
        RepairState.VERIFICATION_FAILED.value,
    }:
        raise HTTPException(
            status_code=400,
            detail=f"Repair in status '{repair.status}' is not eligible for retry.",
        )

    if not repair.context:
        raise HTTPException(status_code=400, detail="Repair context missing.")

    # 3. Retrieve latest verification run diagnosis
    run_res = await session.execute(
        select(VerificationRunRecord)
        .where(VerificationRunRecord.repair_id == repair.id)
        .order_by(desc(VerificationRunRecord.started_at))
    )
    latest_run = run_res.scalars().first()
    if latest_run and latest_run.failure_analysis_json:
        failure_report = FailureAnalysisReport(**latest_run.failure_analysis_json)
    else:
        failure_report = FailureAnalysisReport(
            failure_signature="manual_retry",
            root_cause_summary="Previous verification checks failed.",
            can_retry=True,
        )

    # 4. Gather previous patch hashes
    hashes_res = await session.execute(
        select(RepairAttemptRecord.patch_hash).where(
            RepairAttemptRecord.repair_id == repair.id
        )
    )
    prev_hashes = list(hashes_res.scalars().all())
    if repair.patch and repair.patch.patch_hash not in prev_hashes:
        prev_hashes.append(repair.patch.patch_hash)

    # 5. Formulate retry attempt via LoopCoordinator
    from agent.repair.models import RepairContext as DomainContext

    inv_res = await session.execute(
        select(Investigation).where(Investigation.id == repair.investigation_id)
    )
    inv = inv_res.scalar_one_or_none()
    failure_dict = {}
    if repair.context and repair.context.context_data:
        failure_dict = repair.context.context_data.get("failure", {})
    if not failure_dict and inv and hasattr(inv, "failure_json") and inv.failure_json:
        failure_dict = inv.failure_json
    if not failure_dict:
        failure_dict = {"error_message": "Verification failure retry"}

    if repair.context and repair.context.context_data:
        ctx_data = dict(repair.context.context_data)
        ctx_data["repository_path"] = os.getcwd()
        if not ctx_data.get("failure"):
            ctx_data["failure"] = failure_dict
        domain_context = DomainContext(**ctx_data)
    else:
        domain_context = DomainContext(
            repair_id=repair.id,
            investigation_id=repair.investigation_id,
            repository_id=repair.repository_id,
            repository_path=os.getcwd(),
            failure=failure_dict,
            affected_files=repair.context.affected_files if repair.context else [],
            affected_symbols=repair.context.affected_symbols if repair.context else [],
            supporting_evidence_ids=repair.context.supporting_evidence_ids if repair.context else [],
            related_tests=repair.context.related_tests if repair.context else [],
        )

    coordinator = RepairLoopCoordinator(workspace_root=os.getcwd())
    try:
        plan, patch, risk = coordinator.prepare_retry_attempt(
            current_attempt=repair.current_attempt,
            context=domain_context,
            failure_report=failure_report,
            previous_patch_hashes=prev_hashes,
            custom_modified_contents=body.custom_modified_contents if body else None,
        )
    except LoopLimitExceededError as lle:
        raise HTTPException(status_code=400, detail=str(lle))
    except NoProgressError as npe:
        sm = RepairStateMachine(repair.status)
        try:
            sm.transition(RepairState.NO_PROGRESS)
            repair.status = sm.current_state.value
            await session.commit()
        except Exception:
            pass
        raise HTTPException(status_code=422, detail=str(npe))

    # 6. Update database models with new attempt
    next_attempt_number = repair.current_attempt + 1
    repair.current_attempt = next_attempt_number

    if repair.plan:
        repair.plan.objective = plan.objective
        repair.plan.root_cause = plan.root_cause
        repair.plan.proposed_changes = [pc.model_dump(mode="json") for pc in plan.proposed_changes]
        repair.plan.tests_to_run = plan.tests_to_run
        repair.plan.risks = plan.risks
        repair.plan.assumptions = plan.assumptions
        repair.plan.confidence = plan.confidence

    if repair.patch:
        repair.patch.unified_diff = patch.unified_diff
        repair.patch.patch_hash = patch.patch_hash
        repair.patch.changed_files = patch.changed_files
        repair.patch.lines_added = patch.lines_added
        repair.patch.lines_removed = patch.lines_removed
        repair.patch.explanation = patch.explanation

    if repair.risk:
        repair.risk.score = risk.score
        repair.risk.level = risk.level.value if hasattr(risk.level, "value") else str(risk.level)
        repair.risk.findings = [f.model_dump(mode="json") for f in risk.findings]
        repair.risk.blocking_findings = risk.blocking_findings
        repair.risk.rationale = risk.rationale

    # Reset human approval gate: Approval on Attempt 1 never carries over to Attempt 2/3
    import uuid
    new_token = str(uuid.uuid4())
    if repair.approval:
        repair.approval.patch_hash = patch.patch_hash
        repair.approval.status = ApprovalStatus.PENDING.value
        repair.approval.approved_by = None
        repair.approval.approval_token = new_token
        repair.approval.approved_at = None
        repair.approval.rejection_reason = None
    else:
        repair.approval = RepairApprovalRecord(
            repair_id=repair.id,
            patch_hash=patch.patch_hash,
            status=ApprovalStatus.PENDING.value,
            approval_token=new_token,
        )
        session.add(repair.approval)

    # 7. State transitions: PLANNING -> PLAN_READY -> PATCH_GENERATING -> PATCH_READY -> RISK_ANALYZED -> AWAITING_APPROVAL
    sm = RepairStateMachine(repair.status)
    sm.transition(RepairState.PLANNING)
    sm.transition(RepairState.PLAN_READY)
    sm.transition(RepairState.PATCH_GENERATING)
    sm.transition(RepairState.PATCH_READY)
    sm.transition(RepairState.RISK_ANALYZED)
    sm.transition(RepairState.AWAITING_APPROVAL)
    repair.status = sm.current_state.value

    # Record new attempt
    new_attempt_rec = RepairAttemptRecord(
        repair_id=repair.id,
        attempt_number=next_attempt_number,
        patch_hash=patch.patch_hash,
        unified_diff=patch.unified_diff,
        approval_token=new_token,
        status="AWAITING_APPROVAL",
    )
    session.add(new_attempt_rec)

    await record_event(
        session,
        repair.id,
        "REPAIR_RETRY_INITIATED",
        f"Initiated retry attempt {next_attempt_number}/{repair.max_attempts}. Human approval required for new patch ({patch.patch_hash[:8]}).",
    )

    await session.commit()
    await session.refresh(repair)

    return serialize_repair(repair)


@router.get("/{repair_id}/status", response_model=Dict[str, Any])
async def get_repair_status(
    repair_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Summary status endpoint reporting attempt count, verification status, and Phase 7 eligibility."""
    result = await session.execute(
        select(RepairRecord).where(RepairRecord.id == repair_id)
    )
    repair = result.scalar_one_or_none()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")

    return {
        "repair_id": repair.id,
        "status": repair.status,
        "current_attempt": repair.current_attempt,
        "max_attempts": repair.max_attempts,
        "can_retry": repair.status == RepairState.REPAIR_RETRY_ELIGIBLE.value and repair.current_attempt < repair.max_attempts,
        "is_exhausted": repair.status == RepairState.REPAIR_EXHAUSTED.value or repair.current_attempt >= repair.max_attempts,
        "is_verified": repair.status == RepairState.VERIFIED.value,
        "patch_applied": repair.workspace is not None,
        "approval_status": repair.approval.status if repair.approval else "NONE",
        "phase7_ready": repair.status == RepairState.VERIFIED.value,
    }
