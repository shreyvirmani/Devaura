"""Devaura Durable Background Job Worker.

Provides:
1. Atomic job claiming with conditional SQL UPDATE (prevents duplicate execution).
2. Lease establishment and expired-lease crash recovery.
3. Workspace concurrency limits.
4. Bounded retry policy with explicit classification (RETRYABLE, NON_RETRYABLE, PROVIDER_QUOTA_EXHAUSTED).
5. Integration with the existing InvestigatorEngine pipeline.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import socket
from typing import Any, Callable, Dict, Optional
import uuid
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent.investigator import InvestigatorEngine
from agent.models import FailureType, InvestigationRequest
from apps.api.audit import record_audit_event
from apps.api.config import get_settings
from apps.api.logger import logger
from core.incidents.service import enqueue_job
from core.jobs.retry_policy import (
    FailureClassification,
    NonRetryableJobError,
    ProviderQuotaExhaustedError,
    RetryableJobError,
    classify_exception,
    compute_backoff_seconds,
    is_retryable_classification,
)
from core.repairs.eligibility import evaluate_repair_eligibility
from core.repairs.pipeline import run_pr_stage, run_repair_stage, run_verification_stage
from database.connection import get_session_maker
from database.models import (
    Evidence,
    Incident,
    IncidentStatus,
    Investigation,
    InvestigationStep,
    Job,
    JobStatus,
    JobType,
    Repository,
    RootCauseCandidate,
)


InvestigationRunner = Callable[[Incident, Repository, AsyncSession], Any]


class DurableJobWorker:
    """Database-backed durable job worker with atomic claiming and lease recovery."""

    def __init__(
        self,
        worker_id: Optional[str] = None,
        investigation_runner: Optional[InvestigationRunner] = None,
        git_provider_factory: Optional[Callable[[], Any]] = None,
    ):
        self.worker_id = worker_id or f"worker-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.investigation_runner = investigation_runner
        self.git_provider_factory = git_provider_factory
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    async def recover_expired_leases(self, db: AsyncSession) -> int:
        """Find RUNNING jobs whose lease has expired and recover or dead-letter them."""
        now = datetime.now(timezone.utc)
        stmt = select(Job).where(
            Job.status == JobStatus.RUNNING.value,
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at < now,
        )
        res = await db.execute(stmt)
        expired_jobs = res.scalars().all()
        recovered_count = 0

        for job in expired_jobs:
            recovered_count += 1
            if job.attempt_count >= job.max_attempts:
                job.status = JobStatus.DEAD_LETTER.value
                job.completed_at = now
                job.lease_expires_at = None
                job.last_error = "Worker lease expired after reaching max_attempts."
                job.failure_classification = FailureClassification.RETRYABLE.value

                inc_res = await db.execute(select(Incident).where(Incident.id == job.incident_id))
                inc = inc_res.scalar_one_or_none()
                if inc:
                    inc.status = IncidentStatus.FAILED.value
                    await record_audit_event(
                        db=db,
                        action="incident.failed",
                        resource_type="incident",
                        resource_id=inc.id,
                        workspace_id=inc.workspace_id,
                        outcome="FAILURE",
                        details={"reason": "LEASE_EXPIRED_MAX_ATTEMPTS", "job_id": job.id},
                    )
                await record_audit_event(
                    db=db,
                    action="job.failed",
                    resource_type="job",
                    resource_id=job.id,
                    workspace_id=job.workspace_id,
                    outcome="FAILURE",
                    details={"reason": "LEASE_EXPIRED_MAX_ATTEMPTS", "status": job.status},
                )
            else:
                job.status = JobStatus.QUEUED.value
                job.lease_expires_at = None
                job.worker_id = None
                job.available_at = now
                job.last_error = "Recovered from expired worker lease."
                await record_audit_event(
                    db=db,
                    action="job.retry_scheduled",
                    resource_type="job",
                    resource_id=job.id,
                    workspace_id=job.workspace_id,
                    outcome="SUCCESS",
                    details={"reason": "LEASE_EXPIRED_RECOVERY", "attempt_count": job.attempt_count},
                )

        if recovered_count:
            await db.commit()
        return recovered_count

    async def claim_next_job(
        self,
        db: AsyncSession,
        workspace_id: Optional[str] = None,
    ) -> Optional[Job]:
        """Atomically claim the next available QUEUED or RETRY_WAIT job."""
        settings = get_settings()
        now = datetime.now(timezone.utc)
        lease_expires = now + timedelta(seconds=settings.JOB_LEASE_DURATION_SECONDS)

        # Recover any abandoned/expired jobs first
        await self.recover_expired_leases(db)

        stmt = (
            select(Job)
            .where(
                Job.status.in_([JobStatus.QUEUED.value, JobStatus.RETRY_WAIT.value]),
                Job.available_at <= now,
            )
            .order_by(Job.available_at.asc(), Job.created_at.asc())
            .limit(20)
        )
        if workspace_id:
            stmt = stmt.where(Job.workspace_id == workspace_id)

        candidates = (await db.execute(stmt)).scalars().all()

        for candidate in candidates:
            # Enforce per-workspace concurrent job limit
            running_count_stmt = select(func.count(Job.id)).where(
                Job.workspace_id == candidate.workspace_id,
                Job.status == JobStatus.RUNNING.value,
            )
            running_count = (await db.execute(running_count_stmt)).scalar() or 0
            if running_count >= settings.WORKSPACE_MAX_CONCURRENT_JOBS:
                continue

            # Atomic conditional update to prevent two workers claiming the same job
            upd = (
                update(Job)
                .where(
                    Job.id == candidate.id,
                    Job.status.in_([JobStatus.QUEUED.value, JobStatus.RETRY_WAIT.value]),
                )
                .values(
                    status=JobStatus.RUNNING.value,
                    worker_id=self.worker_id,
                    started_at=candidate.started_at or now,
                    lease_expires_at=lease_expires,
                    attempt_count=candidate.attempt_count + 1,
                    updated_at=now,
                )
            )
            res = await db.execute(upd)
            if res.rowcount == 1:
                await db.commit()
                claimed_res = await db.execute(select(Job).where(Job.id == candidate.id))
                claimed = claimed_res.scalar_one()

                await record_audit_event(
                    db=db,
                    action="job.claimed",
                    resource_type="job",
                    resource_id=claimed.id,
                    workspace_id=claimed.workspace_id,
                    outcome="SUCCESS",
                    details={
                        "worker_id": self.worker_id,
                        "attempt_count": claimed.attempt_count,
                        "correlation_id": claimed.correlation_id,
                    },
                )
                await db.commit()
                return claimed

        return None

    async def execute_job(self, db: AsyncSession, job: Job) -> Job:
        """Execute a claimed job, updating Incident, Investigation, and Job state."""
        settings = get_settings()
        now = datetime.now(timezone.utc)

        # Load Incident & Repository with strict workspace scoping
        inc_res = await db.execute(
            select(Incident).where(
                Incident.id == job.incident_id,
                Incident.workspace_id == job.workspace_id,
            )
        )
        incident = inc_res.scalar_one_or_none()
        if not incident:
            return await self._handle_job_failure(
                db, job, None, NonRetryableJobError("Incident not found in job workspace.")
            )

        repo_res = await db.execute(
            select(Repository).where(
                Repository.id == incident.repository_id,
                Repository.workspace_id == job.workspace_id,
            )
        )
        repo = repo_res.scalar_one_or_none()
        if not repo:
            return await self._handle_job_failure(
                db, job, incident, NonRetryableJobError("Repository not found in job workspace.")
            )

        if repo.connection_status == "ACCESS_REVOKED":
            return await self._handle_job_failure(
                db, job, incident, NonRetryableJobError("Repository access_revoked.")
            )

        # Transition Incident -> INVESTIGATING
        incident.status = IncidentStatus.INVESTIGATING.value
        if not incident.started_at:
            incident.started_at = now
        await record_audit_event(
            db=db,
            action="incident.investigation_started",
            resource_type="incident",
            resource_id=incident.id,
            workspace_id=incident.workspace_id,
            outcome="SUCCESS",
            details={"job_id": job.id, "correlation_id": job.correlation_id},
        )
        await db.commit()

        try:
            if job.job_type == JobType.INVESTIGATE_INCIDENT.value:
                runner = self.investigation_runner or self._default_investigation_runner
                await asyncio.wait_for(
                    runner(incident, repo, db),
                    timeout=settings.INVESTIGATION_MAX_RUNTIME_SECONDS,
                )

                done_at = datetime.now(timezone.utc)
                job.status = JobStatus.SUCCEEDED.value
                job.completed_at = done_at
                job.lease_expires_at = None
                job.last_error = None
                incident.status = IncidentStatus.INVESTIGATED.value
                incident.updated_at = done_at

                await record_audit_event(
                    db=db,
                    action="incident.investigation_completed",
                    resource_type="incident",
                    resource_id=incident.id,
                    workspace_id=incident.workspace_id,
                    outcome="SUCCESS",
                    details={
                        "investigation_id": incident.investigation_id,
                        "correlation_id": incident.correlation_id,
                    },
                )

                # Explicit Phase 4 Repair Eligibility Gate
                inv = None
                if incident.investigation_id:
                    inv = (
                        await db.execute(select(Investigation).where(Investigation.id == incident.investigation_id))
                    ).scalar_one_or_none()
                decision = evaluate_repair_eligibility(incident, inv, repo)
                incident.eligibility_status = decision.eligible
                incident.eligibility_reason = decision.reason
                if decision.failure_classification:
                    incident.failure_classification = decision.failure_classification

                await record_audit_event(
                    db=db,
                    action="incident.eligibility_checked",
                    resource_type="incident",
                    resource_id=incident.id,
                    workspace_id=incident.workspace_id,
                    outcome="SUCCESS" if decision.eligible else "DENIED",
                    details=decision.model_dump(mode="json"),
                )

                if decision.eligible:
                    incident.status = IncidentStatus.REPAIR_PENDING.value
                    await enqueue_job(db, incident, JobType.REPAIR_INCIDENT)
                else:
                    incident.status = decision.incident_status.value

            elif job.job_type == JobType.REPAIR_INCIDENT.value:
                await run_repair_stage(db, incident, repo, job)
                job.status = JobStatus.SUCCEEDED.value
                job.completed_at = datetime.now(timezone.utc)
                job.lease_expires_at = None
                job.last_error = None
                incident.status = IncidentStatus.VERIFICATION_QUEUED.value
                await enqueue_job(
                    db,
                    incident,
                    JobType.VERIFY_REPAIR,
                    payload={"custom_commands": (job.payload or {}).get("custom_commands")},
                )

            elif job.job_type == JobType.VERIFY_REPAIR.value:
                await run_verification_stage(db, incident, repo, job)
                job.status = JobStatus.SUCCEEDED.value
                job.completed_at = datetime.now(timezone.utc)
                job.lease_expires_at = None
                job.last_error = None

            elif job.job_type == JobType.CREATE_PR.value:
                await run_pr_stage(
                    db,
                    incident,
                    repo,
                    job,
                    git_provider_factory=self.git_provider_factory,
                )
                job.status = JobStatus.SUCCEEDED.value
                job.completed_at = datetime.now(timezone.utc)
                job.lease_expires_at = None
                job.last_error = None
            else:
                raise NonRetryableJobError(f"Unsupported job_type: {job.job_type}")

            await record_audit_event(
                db=db,
                action="job.completed",
                resource_type="job",
                resource_id=job.id,
                workspace_id=job.workspace_id,
                outcome="SUCCESS",
                details={"incident_id": incident.id, "job_type": job.job_type, "correlation_id": job.correlation_id},
            )
            await db.commit()
            return job

        except asyncio.TimeoutError as exc:
            return await self._handle_job_failure(
                db, job, incident, RetryableJobError(f"Investigation timed out: {exc}")
            )
        except Exception as exc:
            return await self._handle_job_failure(db, job, incident, exc)

    async def _handle_job_failure(
        self,
        db: AsyncSession,
        job: Job,
        incident: Optional[Incident],
        exc: Exception,
    ) -> Job:
        """Classify failure and transition Job & Incident according to explicit retry policy."""
        now = datetime.now(timezone.utc)
        classification = classify_exception(exc)
        job.last_error = str(exc)[:2000]
        job.failure_classification = classification.value
        job.lease_expires_at = None

        if classification == FailureClassification.PROVIDER_QUOTA_EXHAUSTED:
            job.status = JobStatus.PROVIDER_QUOTA_EXHAUSTED.value
            job.completed_at = now
            if incident:
                incident.status = IncidentStatus.PROVIDER_QUOTA_EXHAUSTED.value
                incident.failure_classification = classification.value
            await self._audit_failure(db, job, incident, classification)
            await db.commit()
            return job

        if classification == FailureClassification.RETRYABLE and job.attempt_count < job.max_attempts:
            backoff = compute_backoff_seconds(job.attempt_count)
            job.status = JobStatus.RETRY_WAIT.value
            job.available_at = now + timedelta(seconds=backoff)
            job.worker_id = None
            if incident:
                incident.status = IncidentStatus.QUEUED.value
            await record_audit_event(
                db=db,
                action="job.retry_scheduled",
                resource_type="job",
                resource_id=job.id,
                workspace_id=job.workspace_id,
                outcome="SUCCESS",
                details={
                    "attempt_count": job.attempt_count,
                    "backoff_seconds": backoff,
                    "classification": classification.value,
                    "correlation_id": job.correlation_id,
                },
            )
            await db.commit()
            return job

        # Terminal failure (NON_RETRYABLE or max_attempts reached)
        job.status = (
            JobStatus.DEAD_LETTER.value
            if classification == FailureClassification.RETRYABLE
            else JobStatus.FAILED.value
        )
        job.completed_at = now
        if incident:
            status_map = {
                FailureClassification.SAFETY_BLOCK: IncidentStatus.SAFETY_BLOCK.value,
                FailureClassification.GITHUB_FAILURE: IncidentStatus.GITHUB_FAILURE.value,
                FailureClassification.VERIFICATION_FAILURE: IncidentStatus.VERIFICATION_FAILED.value,
                FailureClassification.REPAIR_FAILURE: IncidentStatus.REPAIR_FAILED.value,
                FailureClassification.INFORMATION_LEAKAGE: IncidentStatus.INFORMATION_LEAKAGE.value,
                FailureClassification.INFRASTRUCTURE_FAILURE: IncidentStatus.INFRASTRUCTURE_FAILURE.value,
            }
            incident.status = status_map.get(classification, IncidentStatus.FAILED.value)
            incident.failure_classification = classification.value
        await self._audit_failure(db, job, incident, classification)
        await db.commit()
        return job

    async def _audit_failure(
        self,
        db: AsyncSession,
        job: Job,
        incident: Optional[Incident],
        classification: FailureClassification,
    ) -> None:
        await record_audit_event(
            db=db,
            action="job.failed",
            resource_type="job",
            resource_id=job.id,
            workspace_id=job.workspace_id,
            outcome="FAILURE",
            details={
                "status": job.status,
                "classification": classification.value,
                "attempt_count": job.attempt_count,
                "correlation_id": job.correlation_id,
            },
        )
        if incident:
            await record_audit_event(
                db=db,
                action="incident.failed",
                resource_type="incident",
                resource_id=incident.id,
                workspace_id=incident.workspace_id,
                outcome="FAILURE",
                details={
                    "job_id": job.id,
                    "classification": classification.value,
                    "correlation_id": incident.correlation_id,
                },
            )

    async def _default_investigation_runner(
        self,
        incident: Incident,
        repo: Repository,
        db: AsyncSession,
    ) -> Investigation:
        """Invoke the existing InvestigatorEngine and persist linked Investigation records."""
        # Create or reuse Investigation linked to workspace, repository, and incident
        inv: Optional[Investigation] = None
        if incident.investigation_id:
            inv_res = await db.execute(select(Investigation).where(Investigation.id == incident.investigation_id))
            inv = inv_res.scalar_one_or_none()

        if not inv:
            inv = Investigation(
                workspace_id=incident.workspace_id,
                repository_id=repo.id,
                source_type=incident.source,
                source_id=incident.external_run_id or incident.external_check_id or incident.id,
                title=incident.title,
                summary=incident.summary,
                failure_type=FailureType.CI_FAILURE.value,
                ci_run_id=incident.external_run_id,
                commit_sha=incident.commit_sha,
                branch=incident.branch or repo.default_branch,
            )
            db.add(inv)
            await db.flush()
            incident.investigation_id = inv.id

        # Resolve local workspace path if clone_url points to a local directory, else "."
        ws_path = "."
        if repo.clone_url:
            p = Path(repo.clone_url)
            if p.exists() and p.is_dir():
                ws_path = str(p)
        resolved_ws = Path(ws_path).resolve()

        req = InvestigationRequest(
            investigation_id=inv.id,
            repository_id=repo.id,
            issue_id=inv.source_id,
            title=inv.title or inv.summary,
            description=inv.summary,
            failure_type=FailureType.CI_FAILURE,
            ci_run_id=inv.ci_run_id,
            commit_sha=inv.commit_sha,
            branch=inv.branch,
        )

        engine = InvestigatorEngine(
            workspace_root=str(resolved_ws),
            investigation_id=inv.id,
            repository_id=repo.id,
        )
        # Run synchronous InvestigatorEngine in thread pool to keep async worker responsive
        report = await asyncio.to_thread(engine.run, req)

        inv.status = report.status.value
        inv.evidence_sufficiency = report.evidence_sufficiency.value
        inv.root_cause = report.summary
        inv.confidence = report.overall_confidence
        inv.updated_at = datetime.now(timezone.utc)

        for ev in report.ranked_evidence:
            db.add(
                Evidence(
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
            )

        for cand in report.root_cause_candidates:
            db.add(
                RootCauseCandidate(
                    id=cand.candidate_id,
                    investigation_id=inv.id,
                    title=cand.title,
                    description=cand.description,
                    confidence=cand.confidence,
                    affected_symbols=cand.affected_symbols,
                    affected_files=cand.affected_files,
                    supporting_evidence_ids=cand.supporting_evidence_ids,
                    contradicting_evidence_ids=cand.contradicting_evidence_ids,
                    reasoning=cand.reasoning,
                )
            )

        for s in engine.steps_log:
            db.add(
                InvestigationStep(
                    investigation_id=inv.id,
                    step_number=s["step_number"],
                    action=s["action"],
                    tool_name=s.get("tool_name"),
                    tool_input=s.get("tool_input", {}),
                    tool_output=s.get("tool_output", {}),
                    observation=s.get("observation", ""),
                )
            )

        await db.flush()
        return inv

    async def process_one(self, workspace_id: Optional[str] = None) -> Optional[Job]:
        """Claim and execute a single job using a fresh DB session."""
        session_maker = get_session_maker()
        async with session_maker() as db:
            job = await self.claim_next_job(db, workspace_id=workspace_id)
            if not job:
                return None
            return await self.execute_job(db, job)

    async def run_loop(self) -> None:
        """Continuous polling loop for background worker execution."""
        settings = get_settings()
        logger.info(
            f"Starting DurableJobWorker {self.worker_id}",
            extra={"component": "job_worker", "worker_id": self.worker_id},
        )
        while not self._stop_event.is_set():
            try:
                processed = await self.process_one()
                if processed is None:
                    await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)
            except Exception as exc:
                logger.error(
                    f"DurableJobWorker loop error: {exc}",
                    extra={"component": "job_worker", "worker_id": self.worker_id},
                )
                await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)
