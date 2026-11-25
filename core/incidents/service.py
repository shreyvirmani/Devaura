"""Devaura Incident Creation & Idempotency Service.

Provides:
1. Idempotent incident creation from NormalizedEvent / IncidentCandidate.
2. Workspace queued-job quota enforcement without dropping events.
3. Crash-safe job enqueueing (recovers if incident was created without a job).
4. Audit logging for incident.created, incident.queued, and job.created.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple
import uuid
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.audit import record_audit_event
from apps.api.config import get_settings
from core.events.normalizer import IncidentCandidate
from database.models.incidents import Incident, IncidentStatus, Job, JobStatus, JobType


async def create_or_get_incident_and_enqueue_job(
    db: AsyncSession,
    workspace_id: str,
    repository_id: str,
    candidate: IncidentCandidate,
    correlation_id: Optional[str] = None,
) -> Tuple[Incident, Optional[Job], bool]:
    """Idempotently persist an Incident and enqueue an investigation Job.

    Returns:
        (incident, job, created_new)
    """
    settings = get_settings()
    corr_id = correlation_id or str(uuid.uuid4())

    # 1. Check for existing incident using deterministic dedup_key
    existing_stmt = select(Incident).where(Incident.dedup_key == candidate.dedup_key)
    existing_res = await db.execute(existing_stmt)
    existing_incident = existing_res.scalar_one_or_none()

    if existing_incident:
        # Crash-safety: if incident exists but has no job yet (e.g. crash before enqueue)
        # and is not blocked/cancelled/resolved, enqueue a job now.
        job_stmt = select(Job).where(Job.incident_id == existing_incident.id).order_by(Job.created_at.desc())
        job_res = await db.execute(job_stmt)
        existing_job = job_res.scalars().first()

        if (
            existing_job is None
            and existing_incident.status in (IncidentStatus.NEW.value, IncidentStatus.QUEUED.value)
        ):
            job = await _enqueue_investigation_job(db, existing_incident, settings.JOB_MAX_ATTEMPTS)
            return existing_incident, job, False

        return existing_incident, existing_job, False

    # 2. Check workspace queued/running job quota
    active_jobs_stmt = select(func.count(Job.id)).where(
        Job.workspace_id == workspace_id,
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value, JobStatus.RETRY_WAIT.value]),
    )
    active_jobs_count = (await db.execute(active_jobs_stmt)).scalar() or 0
    quota_exceeded = active_jobs_count >= settings.WORKSPACE_MAX_QUEUED_JOBS

    # 3. Create Incident
    incident = Incident(
        workspace_id=workspace_id,
        repository_id=repository_id,
        source=candidate.source.value,
        external_event_id=candidate.external_event_id,
        external_run_id=candidate.external_run_id,
        external_check_id=candidate.external_check_id,
        dedup_key=candidate.dedup_key,
        type=candidate.incident_type.value,
        status=IncidentStatus.BLOCKED_QUOTA.value if quota_exceeded else IncidentStatus.QUEUED.value,
        title=candidate.title,
        summary=candidate.summary,
        failure_signature=candidate.failure_signature,
        commit_sha=candidate.commit_sha,
        branch=candidate.branch,
        workflow_name=candidate.workflow_name,
        workflow_run_url=candidate.workflow_run_url,
        correlation_id=corr_id,
        detected_at=datetime.now(timezone.utc),
        metadata_json=candidate.metadata,
    )

    try:
        db.add(incident)
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Concurrent delivery won the race — fetch existing
        retry_res = await db.execute(select(Incident).where(Incident.dedup_key == candidate.dedup_key))
        race_incident = retry_res.scalar_one()
        job_res = await db.execute(select(Job).where(Job.incident_id == race_incident.id))
        return race_incident, job_res.scalars().first(), False

    await record_audit_event(
        db=db,
        action="incident.created",
        resource_type="incident",
        resource_id=incident.id,
        workspace_id=workspace_id,
        outcome="SUCCESS",
        details={
            "dedup_key": incident.dedup_key,
            "source": incident.source,
            "type": incident.type,
            "correlation_id": corr_id,
            "blocked_quota": quota_exceeded,
        },
    )

    if quota_exceeded:
        return incident, None, True

    # 4. Enqueue Durable Investigation Job
    job = await _enqueue_investigation_job(db, incident, settings.JOB_MAX_ATTEMPTS)
    return incident, job, True


async def enqueue_job(
    db: AsyncSession,
    incident: Incident,
    job_type: JobType,
    payload: Optional[dict] = None,
    max_attempts: Optional[int] = None,
) -> Job:
    """Idempotently create a durable QUEUED job of the given type for an incident."""
    settings = get_settings()
    # Prevent duplicate active jobs of the same type for the same incident
    existing_stmt = select(Job).where(
        Job.incident_id == incident.id,
        Job.job_type == job_type.value,
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value, JobStatus.RETRY_WAIT.value]),
    )
    existing_job = (await db.execute(existing_stmt)).scalars().first()
    if existing_job:
        return existing_job

    job = Job(
        workspace_id=incident.workspace_id,
        incident_id=incident.id,
        job_type=job_type.value,
        status=JobStatus.QUEUED.value,
        attempt_count=0,
        max_attempts=max_attempts or settings.JOB_MAX_ATTEMPTS,
        available_at=datetime.now(timezone.utc),
        correlation_id=incident.correlation_id,
        payload=payload or {},
    )
    db.add(job)
    await db.flush()

    await record_audit_event(
        db=db,
        action="job.created",
        resource_type="job",
        resource_id=job.id,
        workspace_id=incident.workspace_id,
        outcome="SUCCESS",
        details={
            "incident_id": incident.id,
            "job_type": job.job_type,
            "correlation_id": job.correlation_id,
        },
    )
    return job


async def _enqueue_investigation_job(
    db: AsyncSession,
    incident: Incident,
    max_attempts: int,
) -> Job:
    """Create a durable QUEUED investigation job for the incident."""
    incident.status = IncidentStatus.QUEUED.value
    job = await enqueue_job(db, incident, JobType.INVESTIGATE_INCIDENT, max_attempts=max_attempts)
    await record_audit_event(
        db=db,
        action="incident.queued",
        resource_type="incident",
        resource_id=incident.id,
        workspace_id=incident.workspace_id,
        outcome="SUCCESS",
        details={"job_id": job.id, "correlation_id": incident.correlation_id},
    )
    return job
