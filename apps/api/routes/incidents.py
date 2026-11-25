"""Devaura Workspace-Scoped Incidents & Durable Jobs Endpoints.

Enforces strict tenant isolation (User -> Workspace -> Incident / Job)
and provides full observability into incident lifecycle, investigation
evidence, jobs, and audit timelines.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.audit import record_audit_event
from apps.api.auth import create_auth_error
from apps.api.authorization import (
    WorkspaceContext,
    require_workspace_admin,
    require_workspace_member,
)
from apps.api.config import get_settings
from core.incidents.service import _enqueue_investigation_job
from database.connection import get_db
from database.models import (
    AuditEventRecord,
    Incident,
    IncidentStatus,
    Investigation,
    Job,
    JobStatus,
    PullRequest,
    RepairRecord,
    Repository,
)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["Incidents & Jobs"])


async def _verify_incident_in_workspace(
    incident_id: str,
    workspace_id: str,
    db: AsyncSession,
) -> Incident:
    stmt = select(Incident).where(
        Incident.id == incident_id,
        Incident.workspace_id == workspace_id,
    )
    res = await db.execute(stmt)
    incident = res.scalar_one_or_none()
    if not incident:
        raise create_auth_error(
            status.HTTP_404_NOT_FOUND,
            "INCIDENT_NOT_FOUND",
            "Incident not found in this workspace.",
        )
    return incident


def _serialize_job(job: Job) -> Dict[str, Any]:
    return {
        "id": job.id,
        "workspace_id": job.workspace_id,
        "incident_id": job.incident_id,
        "job_type": job.job_type,
        "status": job.status,
        "attempt_count": job.attempt_count,
        "max_attempts": job.max_attempts,
        "available_at": job.available_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "lease_expires_at": job.lease_expires_at,
        "worker_id": job.worker_id,
        "last_error": job.last_error,
        "failure_classification": job.failure_classification,
        "correlation_id": job.correlation_id,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _serialize_incident_summary(inc: Incident) -> Dict[str, Any]:
    latest_job = inc.jobs[-1] if inc.jobs else None
    return {
        "id": inc.id,
        "workspace_id": inc.workspace_id,
        "repository_id": inc.repository_id,
        "repository_full_name": (
            inc.repository.full_name or f"{inc.repository.owner}/{inc.repository.name}"
            if inc.repository
            else None
        ),
        "investigation_id": inc.investigation_id,
        "investigation_status": inc.investigation.status if inc.investigation else None,
        "source": inc.source,
        "external_event_id": inc.external_event_id,
        "external_run_id": inc.external_run_id,
        "external_check_id": inc.external_check_id,
        "type": inc.type,
        "status": inc.status,
        "title": inc.title,
        "summary": inc.summary,
        "failure_signature": inc.failure_signature,
        "commit_sha": inc.commit_sha,
        "branch": inc.branch,
        "workflow_name": inc.workflow_name,
        "workflow_run_url": inc.workflow_run_url,
        "correlation_id": inc.correlation_id,
        "detected_at": inc.detected_at,
        "started_at": inc.started_at,
        "resolved_at": inc.resolved_at,
        "created_at": inc.created_at,
        "updated_at": inc.updated_at,
        "latest_job": _serialize_job(latest_job) if latest_job else None,
    }


@router.get("/incidents")
async def list_workspace_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    repository_id: Optional[str] = Query(None),
    ctx: WorkspaceContext = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """List incidents strictly scoped to the workspace."""
    stmt = (
        select(Incident)
        .where(Incident.workspace_id == ctx.workspace_id)
        .order_by(desc(Incident.detected_at))
    )
    if status_filter:
        stmt = stmt.where(Incident.status == status_filter)
    if repository_id:
        stmt = stmt.where(Incident.repository_id == repository_id)

    res = await db.execute(stmt)
    incidents = res.scalars().all()
    return [_serialize_incident_summary(inc) for inc in incidents]


@router.get("/incidents/{incident_id}")
async def get_workspace_incident_detail(
    incident_id: str,
    ctx: WorkspaceContext = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve complete workspace-scoped incident details, timeline, investigation, and linked repair/PR state."""
    inc = await _verify_incident_in_workspace(incident_id, ctx.workspace_id, db)

    # Investigation details
    investigation_data = None
    if inc.investigation_id:
        inv_res = await db.execute(
            select(Investigation).where(
                Investigation.id == inc.investigation_id,
                Investigation.workspace_id == ctx.workspace_id,
            )
        )
        inv = inv_res.scalar_one_or_none()
        if inv:
            investigation_data = {
                "id": inv.id,
                "status": inv.status,
                "evidence_sufficiency": inv.evidence_sufficiency,
                "root_cause": inv.root_cause,
                "confidence": inv.confidence,
                "created_at": inv.created_at,
                "updated_at": inv.updated_at,
                "evidence_items": [
                    {
                        "id": ev.id,
                        "source": ev.source,
                        "type": ev.type,
                        "content": ev.content,
                        "repository_path": ev.repository_path,
                        "symbol_id": ev.symbol_id,
                        "line_start": ev.line_start,
                        "line_end": ev.line_end,
                        "confidence": ev.confidence,
                        "relevance": ev.relevance,
                    }
                    for ev in (inv.evidence_items or [])
                ],
                "root_cause_candidates": [
                    {
                        "id": c.id,
                        "title": c.title,
                        "description": c.description,
                        "confidence": c.confidence,
                        "affected_files": c.affected_files,
                        "affected_symbols": c.affected_symbols,
                        "reasoning": c.reasoning,
                    }
                    for c in (inv.root_cause_candidates or [])
                ],
                "investigation_steps": [
                    {
                        "id": s.id,
                        "step_number": s.step_number,
                        "action": s.action,
                        "tool_name": s.tool_name,
                        "observation": s.observation,
                        "created_at": s.created_at,
                    }
                    for s in (inv.investigation_steps or [])
                ],
            }

    # Linked repairs (if any exist for the investigation)
    repair_data = None
    pr_data = None
    if inc.investigation_id:
        rep_res = await db.execute(
            select(RepairRecord)
            .where(
                RepairRecord.investigation_id == inc.investigation_id,
                RepairRecord.workspace_id == ctx.workspace_id,
            )
            .order_by(desc(RepairRecord.created_at))
        )
        rep = rep_res.scalars().first()
        if rep:
            repair_data = {
                "id": rep.id,
                "status": rep.status,
                "created_at": rep.created_at,
                "updated_at": rep.updated_at,
            }

        pr_res = await db.execute(
            select(PullRequest)
            .where(PullRequest.investigation_id == inc.investigation_id)
            .order_by(desc(PullRequest.created_at))
        )
        pr = pr_res.scalars().first()
        if pr:
            pr_data = {
                "id": pr.id,
                "provider_pr_id": pr.provider_pr_id,
                "url": pr.url,
                "status": pr.status,
                "created_at": pr.created_at,
            }

    # Timeline from AuditEventRecord matching correlation_id or resource_id
    audit_stmt = (
        select(AuditEventRecord)
        .where(
            AuditEventRecord.workspace_id == ctx.workspace_id,
            (AuditEventRecord.resource_id == inc.id)
            | (AuditEventRecord.resource_id.in_([j.id for j in (inc.jobs or [])])),
        )
        .order_by(AuditEventRecord.created_at.asc())
    )
    audit_res = await db.execute(audit_stmt)
    timeline = [
        {
            "id": a.id,
            "action": a.action,
            "resource_type": a.resource_type,
            "resource_id": a.resource_id,
            "outcome": a.outcome,
            "details": a.details,
            "created_at": a.created_at,
        }
        for a in audit_res.scalars().all()
    ]

    summary = _serialize_incident_summary(inc)
    summary["metadata"] = inc.metadata_json or {}
    summary["jobs"] = [_serialize_job(j) for j in (inc.jobs or [])]
    summary["investigation"] = investigation_data
    summary["repair"] = repair_data
    summary["pull_request"] = pr_data
    summary["timeline"] = timeline
    return summary


@router.post("/incidents/{incident_id}/cancel")
async def cancel_workspace_incident(
    incident_id: str,
    request: Request,
    ctx: WorkspaceContext = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an incident and any pending jobs (Requires ADMIN)."""
    inc = await _verify_incident_in_workspace(incident_id, ctx.workspace_id, db)
    now = datetime.now(timezone.utc)
    inc.status = IncidentStatus.CANCELLED.value
    inc.updated_at = now

    for job in inc.jobs or []:
        if job.status in (JobStatus.QUEUED.value, JobStatus.RETRY_WAIT.value):
            job.status = JobStatus.CANCELLED.value
            job.completed_at = now
            await record_audit_event(
                db=db,
                action="job.cancelled",
                resource_type="job",
                resource_id=job.id,
                workspace_id=ctx.workspace_id,
                actor_id=ctx.user_id,
                actor_email=ctx.user.email,
                outcome="SUCCESS",
                details={"incident_id": inc.id},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("User-Agent"),
            )

    await db.commit()
    return {"status": "cancelled", "incident_id": inc.id}


@router.post("/incidents/{incident_id}/retry", status_code=status.HTTP_201_CREATED)
async def retry_workspace_incident(
    incident_id: str,
    ctx: WorkspaceContext = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enqueue a fresh investigation job for a failed or quota-blocked incident (Requires ADMIN)."""
    inc = await _verify_incident_in_workspace(incident_id, ctx.workspace_id, db)
    settings = get_settings()
    job = await _enqueue_investigation_job(db, inc, settings.JOB_MAX_ATTEMPTS)
    await db.commit()
    await db.refresh(job)
    return _serialize_job(job)


@router.get("/jobs")
async def list_workspace_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    ctx: WorkspaceContext = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """List durable background jobs strictly scoped to the workspace."""
    stmt = select(Job).where(Job.workspace_id == ctx.workspace_id).order_by(desc(Job.created_at))
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    res = await db.execute(stmt)
    return [_serialize_job(j) for j in res.scalars().all()]


@router.get("/jobs/{job_id}")
async def get_workspace_job(
    job_id: str,
    ctx: WorkspaceContext = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single job strictly scoped to the workspace."""
    stmt = select(Job).where(Job.id == job_id, Job.workspace_id == ctx.workspace_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise create_auth_error(
            status.HTTP_404_NOT_FOUND,
            "JOB_NOT_FOUND",
            "Job not found in this workspace.",
        )
    return _serialize_job(job)
