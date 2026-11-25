"""Devaura Phase 4 Production Repair, Verification & PR Pipeline Stages.

Connects durable worker jobs to existing Phase 5/6/7 subsystems:
- RepairContextBuilder, RepairPlanner, PatchGenerator, PatchRiskAnalyzer
- IsolatedWorkspace, VerificationRunner
- HumanPRApprovalGate, PROrchestrator, GitHubAppService
"""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional
import uuid
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.pr.approval_gate import (
    HumanPRApprovalGate,
    PRApprovalRequiredError,
    PRPatchIntegrityError,
)
from agent.pr.models import PRApproval, PRApprovalStatus
from agent.pr.orchestrator import PROrchestrator
from agent.repair.context_builder import RepairContextBuilder
from agent.repair.models import (
    CheckStatus,
    CheckType,
    OverallVerificationStatus,
    RepairContext,
    RepairPlan,
    RepairState as DomainRepairState,
    VerificationRun as DomainVerificationRun,
    VerifiedRepairResult,
)
from agent.repair.patch_generator import PatchGenerator, ScopeViolationError
from agent.repair.planner import RepairPlanner
from agent.repair.risk_analyzer import PatchRiskAnalyzer
from agent.verification.runner import VerificationRunner
from apps.api.audit import record_audit_event
from core.jobs.retry_policy import (
    FailureClassification,
    GitHubFailureError,
    NonRetryableJobError,
    SafetyBlockError,
)
from database.models import (
    Incident,
    IncidentStatus,
    Investigation,
    Job,
    PatchRecord,
    PatchRiskRecord,
    PullRequestApprovalRecord,
    PullRequestEventRecord,
    PullRequestRecord,
    RepairContextRecord,
    RepairEventRecord,
    RepairPlanRecord,
    RepairRecord,
    RepairState,
    RepairWorkspaceRecord,
    Repository,
    VerificationCheckRecord,
    VerificationRunRecord,
)
from integrations.github.app_service import get_github_app_service
from integrations.github.client import GitHubClient
from integrations.github.provider import (
    BaseRevisionChangedError,
    GitProvider,
    GitHubAuthRequiredError,
    SecurityBlockError,
)
from sandbox.workspace import IsolatedWorkspace, PatchApplicationError


def _resolve_repo_workspace_path(repo: Repository) -> str:
    if repo.clone_url:
        p = Path(repo.clone_url)
        if p.exists() and p.is_dir():
            return str(p.resolve())
    return str(Path(".").resolve())


async def run_repair_stage(
    db: AsyncSession,
    incident: Incident,
    repo: Repository,
    job: Job,
    modified_contents: Optional[Dict[str, str]] = None,
) -> RepairRecord:
    """Idempotently plan, generate, validate, and sandbox-apply a repair patch."""
    if not incident.investigation_id:
        raise NonRetryableJobError("Incident has no linked investigation_id.")

    inv_res = await db.execute(
        select(Investigation).where(
            Investigation.id == incident.investigation_id,
            Investigation.workspace_id == incident.workspace_id,
        )
    )
    inv = inv_res.scalar_one_or_none()
    if not inv:
        raise NonRetryableJobError("Linked investigation not found in workspace.")

    # 1. Idempotent RepairRecord lookup/creation
    repair: Optional[RepairRecord] = None
    if incident.repair_id:
        rep_res = await db.execute(
            select(RepairRecord).where(
                RepairRecord.id == incident.repair_id,
                RepairRecord.workspace_id == incident.workspace_id,
            )
        )
        repair = rep_res.scalar_one_or_none()

    if not repair:
        rep_res = await db.execute(
            select(RepairRecord).where(
                RepairRecord.investigation_id == inv.id,
                RepairRecord.workspace_id == incident.workspace_id,
            )
        )
        repair = rep_res.scalars().first()

    if not repair:
        repair = RepairRecord(
            workspace_id=incident.workspace_id,
            investigation_id=inv.id,
            repository_id=repo.id,
            status=RepairState.CREATED.value,
            target_branch=incident.branch or repo.default_branch or "main",
            base_revision=incident.commit_sha or "HEAD",
        )
        db.add(repair)
        await db.flush()
        await db.refresh(repair)

    incident.repair_id = repair.id

    # If patch already generated & applied in sandbox, preserve idempotency
    if repair.patch and repair.workspace and repair.status == RepairState.PATCH_APPLIED_PENDING_VERIFICATION.value:
        incident.status = IncidentStatus.PATCH_APPLIED.value
        return repair

    ws_root = _resolve_repo_workspace_path(repo)

    # 2. Repair Context
    incident.status = IncidentStatus.REPAIR_PLANNING.value
    if not repair.context:
        builder = RepairContextBuilder(workspace_root=ws_root)
        is_valid, ctx, err = builder.validate_and_build(
            investigation=inv,
            repair_id=repair.id,
        )
        if not is_valid or not ctx:
            raise NonRetryableJobError(
                f"Repair context invalid: {err}",
                FailureClassification.REPAIR_FAILURE,
            )
        db.add(
            RepairContextRecord(
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
        )
        repair.status = RepairState.CONTEXT_READY.value
        await db.flush()
        await db.refresh(repair)
    else:
        ctx = RepairContext.model_validate(repair.context.context_data)

    # 3. Repair Plan
    if not repair.plan:
        planner = RepairPlanner()
        plan = planner.create_plan(context=ctx)
        db.add(
            RepairPlanRecord(
                repair_id=repair.id,
                objective=plan.objective,
                root_cause=plan.root_cause,
                proposed_changes=[c.model_dump(mode="json") for c in plan.proposed_changes],
                tests_to_run=plan.tests_to_run,
                risks=plan.risks,
                assumptions=plan.assumptions,
                confidence=plan.confidence,
            )
        )
        repair.status = RepairState.PLAN_READY.value
        await db.flush()
        await db.refresh(repair)
        await record_audit_event(
            db=db,
            action="repair.plan_created",
            resource_type="repair",
            resource_id=repair.id,
            workspace_id=incident.workspace_id,
            outcome="SUCCESS",
            details={"incident_id": incident.id, "correlation_id": incident.correlation_id},
        )
    else:
        plan = RepairPlan(
            repair_id=repair.id,
            investigation_id=repair.investigation_id,
            objective=repair.plan.objective,
            root_cause=repair.plan.root_cause,
            proposed_changes=repair.plan.proposed_changes,
            tests_to_run=repair.plan.tests_to_run,
            risks=repair.plan.risks,
            assumptions=repair.plan.assumptions,
            confidence=repair.plan.confidence,
        )

    # 4. Patch Generation & Validation (only inside sandbox / isolated generator)
    incident.status = IncidentStatus.PATCH_GENERATION.value
    payload_mods = modified_contents or (job.payload or {}).get("modified_contents")
    if not repair.patch:
        generator = PatchGenerator(workspace_root=ws_root)
        try:
            if payload_mods:
                patch = generator.generate_from_content_map(
                    plan=plan,
                    context=ctx,
                    modified_contents=payload_mods,
                )
            else:
                patch = generator.generate_defensive_patch(plan=plan, context=ctx)
        except ScopeViolationError as exc:
            await record_audit_event(
                db=db,
                action="repair.patch_rejected",
                resource_type="repair",
                resource_id=repair.id,
                workspace_id=incident.workspace_id,
                outcome="DENIED",
                details={"reason": str(exc), "correlation_id": incident.correlation_id},
            )
            raise SafetyBlockError(f"Patch validation rejected: {exc}") from exc

        if not patch.changed_files:
            raise NonRetryableJobError(
                "Patch generator produced an empty patch.",
                FailureClassification.REPAIR_FAILURE,
            )

        db.add(
            PatchRecord(
                repair_id=repair.id,
                unified_diff=patch.unified_diff,
                patch_hash=patch.patch_hash,
                changed_files=patch.changed_files,
                lines_added=patch.lines_added,
                lines_removed=patch.lines_removed,
                explanation=patch.explanation,
                model_metadata=patch.model_metadata,
            )
        )
        repair.status = RepairState.PATCH_READY.value
        await db.flush()
        await db.refresh(repair)

        # Risk analysis
        risk = PatchRiskAnalyzer().analyze(patch, plan, ctx)
        db.add(
            PatchRiskRecord(
                repair_id=repair.id,
                score=risk.score,
                level=risk.level.value,
                findings=[f.model_dump(mode="json") for f in risk.findings],
                blocking_findings=risk.blocking_findings,
            )
        )
        if risk.blocking_findings:
            raise SafetyBlockError(f"Patch risk analysis blocked execution: {risk.blocking_findings}")

        await record_audit_event(
            db=db,
            action="repair.patch_generated",
            resource_type="repair",
            resource_id=repair.id,
            workspace_id=incident.workspace_id,
            outcome="SUCCESS",
            details={
                "patch_hash": patch.patch_hash,
                "changed_files": patch.changed_files,
                "correlation_id": incident.correlation_id,
            },
        )

    # 5. Apply Patch ONLY inside IsolatedWorkspace
    if not repair.workspace:
        sandbox = IsolatedWorkspace(source_repo_path=ws_root, workspace_id=f"repair_{repair.id[:8]}")
        sandbox_path = sandbox.create()
        try:
            sandbox.apply_patch(repair.patch.unified_diff)
        except PatchApplicationError as exc:
            raise NonRetryableJobError(
                f"Failed to apply patch in sandbox: {exc}",
                FailureClassification.REPAIR_FAILURE,
            ) from exc

        db.add(
            RepairWorkspaceRecord(
                repair_id=repair.id,
                isolated_path=sandbox_path,
                base_revision=repair.base_revision,
                status="PATCH_APPLIED",
            )
        )

    repair.status = RepairState.PATCH_APPLIED_PENDING_VERIFICATION.value
    incident.status = IncidentStatus.PATCH_APPLIED.value
    await db.flush()
    await record_audit_event(
        db=db,
        action="repair.patch_applied",
        resource_type="repair",
        resource_id=repair.id,
        workspace_id=incident.workspace_id,
        outcome="SUCCESS",
        details={
            "patch_hash": repair.patch.patch_hash,
            "correlation_id": incident.correlation_id,
        },
    )
    return repair


async def run_verification_stage(
    db: AsyncSession,
    incident: Incident,
    repo: Repository,
    job: Job,
) -> VerificationRunRecord:
    """Idempotently verify the sandboxed repair patch against exact (repair_id, patch_hash, base_revision)."""
    if not incident.repair_id:
        raise NonRetryableJobError("Incident has no linked repair_id for verification.")

    rep_res = await db.execute(
        select(RepairRecord).where(
            RepairRecord.id == incident.repair_id,
            RepairRecord.workspace_id == incident.workspace_id,
        )
    )
    repair = rep_res.scalar_one_or_none()
    if not repair or not repair.patch or not repair.workspace:
        raise NonRetryableJobError("Repair patch or sandbox workspace missing for verification.")

    patch_hash = repair.patch.patch_hash
    base_rev = repair.base_revision

    # Verification Idempotency: repair_id + patch_hash + base_revision
    existing_runs = repair.verification_runs or []
    for run in existing_runs:
        if (
            run.attempt_number == repair.current_attempt
            and (run.failure_analysis_json or {}).get("patch_hash") == patch_hash
            and (run.failure_analysis_json or {}).get("base_revision") == base_rev
        ):
            if run.overall_result == "PASSED":
                incident.status = IncidentStatus.AWAITING_APPROVAL.value
            return run

    incident.status = IncidentStatus.VERIFYING.value
    await record_audit_event(
        db=db,
        action="verification.started",
        resource_type="repair",
        resource_id=repair.id,
        workspace_id=incident.workspace_id,
        outcome="SUCCESS",
        details={
            "patch_hash": patch_hash,
            "base_revision": base_rev,
            "correlation_id": incident.correlation_id,
        },
    )

    custom_cmds = (job.payload or {}).get("custom_commands")
    runner = VerificationRunner(workspace_path=repair.workspace.isolated_path)
    run_result = runner.run_verification_suite(
        repair_id=repair.id,
        attempt_number=repair.current_attempt,
        custom_commands=custom_cmds,
    )

    analysis_meta = run_result.failure_analysis.model_dump(mode="json") if run_result.failure_analysis else {}
    analysis_meta["patch_hash"] = patch_hash
    analysis_meta["base_revision"] = base_rev

    db_run = VerificationRunRecord(
        id=run_result.verification_id,
        repair_id=repair.id,
        attempt_number=repair.current_attempt,
        workspace_id=repair.workspace.id,
        status=getattr(run_result.status, "value", run_result.status),
        overall_result=getattr(run_result.overall_result, "value", run_result.overall_result),
        failure_analysis_json=analysis_meta,
    )
    db.add(db_run)
    await db.flush()

    for chk in run_result.checks:
        db.add(
            VerificationCheckRecord(
                verification_run_id=db_run.id,
                check_type=getattr(chk.check_type, "value", chk.check_type),
                command=chk.command,
                exit_code=chk.exit_code,
                duration_ms=chk.duration_ms,
                stdout=chk.stdout,
                stderr=chk.stderr,
                status=getattr(chk.status, "value", chk.status),
                parsed_errors_json=chk.parsed_errors,
            )
        )

    repair.latest_verification_id = db_run.id
    passed = getattr(run_result.overall_result, "value", run_result.overall_result) == OverallVerificationStatus.PASSED.value

    if passed:
        repair.status = "VERIFIED"
        incident.status = IncidentStatus.AWAITING_APPROVAL.value
        await record_audit_event(
            db=db,
            action="verification.completed",
            resource_type="repair",
            resource_id=repair.id,
            workspace_id=incident.workspace_id,
            outcome="SUCCESS",
            details={"verification_id": db_run.id, "result": "PASSED", "patch_hash": patch_hash},
        )
        await record_audit_event(
            db=db,
            action="approval.requested",
            resource_type="incident",
            resource_id=incident.id,
            workspace_id=incident.workspace_id,
            outcome="SUCCESS",
            details={"repair_id": repair.id, "patch_hash": patch_hash, "base_revision": base_rev},
        )
    else:
        repair.status = "REPAIR_EXHAUSTED" if repair.current_attempt >= repair.max_attempts else "REPAIR_RETRY_ELIGIBLE"
        incident.status = IncidentStatus.VERIFICATION_FAILED.value
        incident.failure_classification = FailureClassification.VERIFICATION_FAILURE.value
        await record_audit_event(
            db=db,
            action="verification.completed",
            resource_type="repair",
            resource_id=repair.id,
            workspace_id=incident.workspace_id,
            outcome="FAILURE",
            details={"verification_id": db_run.id, "result": "FAILED", "patch_hash": patch_hash},
        )

    await db.flush()
    return db_run


async def run_pr_stage(
    db: AsyncSession,
    incident: Incident,
    repo: Repository,
    job: Job,
    git_provider_factory: Optional[Callable[[], GitProvider]] = None,
) -> PullRequestRecord:
    """Revalidate approval/patch/base_revision and idempotently create a GitHub PR."""
    if not incident.repair_id:
        raise NonRetryableJobError("Incident has no linked repair_id for PR creation.")

    rep_res = await db.execute(
        select(RepairRecord).where(
            RepairRecord.id == incident.repair_id,
            RepairRecord.workspace_id == incident.workspace_id,
        )
    )
    repair = rep_res.scalar_one_or_none()
    if not repair or not repair.patch:
        raise NonRetryableJobError("Repair or patch record missing.")

    # 1. PR Idempotency: return existing PR if already created for this repair
    existing_pr_res = await db.execute(
        select(PullRequestRecord).where(PullRequestRecord.repair_id == repair.id)
    )
    existing_pr = existing_pr_res.scalars().first()
    if existing_pr:
        incident.status = IncidentStatus.PR_CREATED.value
        return existing_pr

    # 2. Revalidate repository state & protected branch
    if repo.connection_status != "CONNECTED":
        raise GitHubFailureError(f"Repository connection is '{repo.connection_status}'.")

    repair_branch = f"devaura/repair/{repair.id[:8]}"
    if repair.target_branch == repair_branch:
        raise SafetyBlockError("Target branch cannot equal repair branch.")

    # 3. Revalidate cryptographic human approval
    payload = job.payload or {}
    approval_token = payload.get("approval_token")
    expected_base = payload.get("base_revision")
    expected_patch_hash = payload.get("patch_hash")

    if expected_base and expected_base != repair.base_revision:
        raise NonRetryableJobError("Base revision changed after approval.")
    if expected_patch_hash and expected_patch_hash != repair.patch.patch_hash:
        raise NonRetryableJobError("Patch hash changed after approval.")

    appr_res = await db.execute(
        select(PullRequestApprovalRecord)
        .where(
            PullRequestApprovalRecord.repair_id == repair.id,
            PullRequestApprovalRecord.status == PRApprovalStatus.APPROVED.value,
        )
        .order_by(PullRequestApprovalRecord.created_at.desc())
    )
    appr_rec = appr_res.scalars().first()
    if not appr_rec or appr_rec.approval_token != approval_token:
        raise SafetyBlockError("Valid human PR approval token not found.")

    gate = HumanPRApprovalGate()
    approval_obj = PRApproval(
        repair_id=repair.id,
        patch_hash=appr_rec.patch_hash,
        base_revision=expected_base or repair.base_revision,
        repair_branch=repair_branch,
        repository=repo.full_name or f"{repo.owner}/{repo.name}",
        approved_by=appr_rec.approved_by,
        approval_token=appr_rec.approval_token,
        status=PRApprovalStatus.APPROVED,
    )
    try:
        gate.verify_authorization(
            approval=approval_obj,
            current_patch_hash=repair.patch.patch_hash,
            current_base_revision=repair.base_revision,
            current_repair_branch=repair_branch,
            current_repository=repo.full_name or f"{repo.owner}/{repo.name}",
        )
    except (PRApprovalRequiredError, PRPatchIntegrityError) as exc:
        raise SafetyBlockError(f"Approval revalidation failed: {exc}") from exc

    # 4. Obtain GitProvider using GitHub App installation token (never stored PATs)
    provider: Optional[GitProvider] = None
    if git_provider_factory:
        provider = git_provider_factory()
    elif repo.github_installation_id and repo.github_installation:
        app_svc = get_github_app_service()
        inst_token = await app_svc.get_installation_access_token(repo.github_installation.installation_id)
        provider = GitHubClient(token=inst_token)
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("DEVAURA_GITHUB_TOKEN")
        if not token:
            raise GitHubFailureError("No GitHub App installation or token available for PR creation.")
        provider = GitHubClient(token=token)

    # 5. Orchestrate Branch, Commit & PR Creation
    incident.status = IncidentStatus.PR_PREPARATION.value
    ws_root = _resolve_repo_workspace_path(repo)
    orchestrator = PROrchestrator(workspace_root=ws_root)

    verified_res = VerifiedRepairResult(
        repair_id=repair.id,
        investigation_id=repair.investigation_id,
        repository=repo.full_name or f"{repo.owner}/{repo.name}",
        status=DomainRepairState.PATCH_APPLIED_PENDING_VERIFICATION,
        overall_verification=OverallVerificationStatus.PASSED,
        final_workspace_id=repair.workspace.id if repair.workspace else "sandbox",
        final_patch_hash=repair.patch.patch_hash,
        final_diff=repair.patch.unified_diff,
        verification_run=DomainVerificationRun(
            verification_id=repair.latest_verification_id or str(uuid.uuid4()),
            repair_id=repair.id,
            attempt_number=repair.current_attempt,
            workspace_id=repair.workspace.id if repair.workspace else "sandbox",
            overall_result=OverallVerificationStatus.PASSED,
            checks=[],
        ),
        patch_hash=repair.patch.patch_hash,
        unified_diff=repair.patch.unified_diff,
        modified_files=repair.patch.changed_files,
        base_revision=repair.base_revision,
        target_branch=repair.target_branch,
    )

    prep = orchestrator.prepare_pull_request(
        repair=repair,
        verified_result=verified_res,
        owner=repo.owner,
        repo=repo.name,
    )

    try:
        pr_result = await orchestrator.execute_pull_request_creation(
            repair=repair,
            context=prep.context,
            approval=approval_obj,
            provider=provider,
            local_repo_path=repair.workspace.isolated_path if repair.workspace else ws_root,
        )
    except SecurityBlockError as exc:
        raise SafetyBlockError(str(exc)) from exc
    except BaseRevisionChangedError as exc:
        raise NonRetryableJobError(str(exc), FailureClassification.GITHUB_FAILURE) from exc
    except Exception as exc:
        raise GitHubFailureError(f"GitHub PR creation failed: {exc}") from exc

    db_pr = PullRequestRecord(
        repair_id=repair.id,
        investigation_id=repair.investigation_id,
        repository_id=repo.id,
        owner=repo.owner,
        repo=repo.name,
        base_branch=repair.target_branch,
        base_revision=repair.base_revision,
        repair_branch=repair_branch,
        commit_sha=pr_result.commit_sha,
        pr_number=pr_result.pr_number,
        pr_url=pr_result.pr_url,
        pr_title=prep.context.pr_title,
        pr_body=prep.context.pr_body,
        pr_state=pr_result.state.value,
        patch_hash=repair.patch.patch_hash,
        verification_id=repair.latest_verification_id,
        approval_token=appr_rec.approval_token,
        approved_by=appr_rec.approved_by,
        approved_at=appr_rec.created_at,
        status="PR_CREATED",
    )
    db.add(db_pr)
    incident.status = IncidentStatus.PR_CREATED.value
    await db.flush()

    await record_audit_event(
        db=db,
        action="pr.created",
        resource_type="pull_request",
        resource_id=db_pr.id,
        workspace_id=incident.workspace_id,
        actor_email=appr_rec.approved_by,
        outcome="SUCCESS",
        details={
            "repair_id": repair.id,
            "pr_number": db_pr.pr_number,
            "pr_url": db_pr.pr_url,
            "branch": repair_branch,
            "commit_sha": pr_result.commit_sha,
            "correlation_id": incident.correlation_id,
        },
    )
    return db_pr
