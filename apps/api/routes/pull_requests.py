"""Devaura Phase 7 Pull Request REST API Routes.

Exposes endpoints for:
1. Validating repair verification integrity and synthesizing PRContext.
2. Generating cryptographic human authorization tokens for PR creation.
3. Managing human review (approvals and rejections).
4. Committing, pushing branch, and opening GitHub Pull Request.
5. Monitoring PR lifecycle, CI checks, and review states.
6. Pull request audit logging and event history.
"""

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent.pr.approval_gate import (
    HumanPRApprovalGate,
    PRApprovalRequiredError,
    PRPatchIntegrityError,
)
from agent.pr.context_builder import PRContextBuilder
from agent.pr.git_manager import GitStateManager
from agent.pr.models import (
    PRApproval,
    PRApprovalStatus,
    PRContext,
    PRPreparationResult,
    PRState,
)
from agent.pr.orchestrator import PROrchestrator
from agent.repair.models import (
    OverallVerificationStatus,
    VerifiedRepairResult,
)
from apps.api.auth import CurrentUser, get_current_user
from apps.api.logger import logger
from database.connection import get_db_session
from database.models import (
    Investigation,
    PullRequestApprovalRecord,
    PullRequestEventRecord,
    PullRequestRecord,
    RepairRecord,
    Repository,
)
from integrations.github.client import GitHubClient
from integrations.github.models import (
    CIStatusInfo,
    PullRequestPayload,
    PullRequestResult,
    PullRequestState,
    ReviewInfo,
)
from integrations.github.provider import (
    BaseRevisionChangedError,
    BranchPushError,
    GitConflictError,
    GitProvider,
    GitHubAuthRequiredError,
    PullRequestAlreadyExistsError,
    PullRequestCreationError,
    SecurityBlockError,
)

router = APIRouter(tags=["pull_requests"])

# In-memory storage for PR contexts that are awaiting creation
_PR_CONTEXT_STORE: Dict[str, PRContext] = {}


def get_git_provider() -> GitProvider:
    """Retrieve production GitProvider.
    
    In runtime and production paths, returns real authenticated GitHubClient.
    If GITHUB_TOKEN is unset, strictly raises GitHubAuthRequiredError (NO silent mock fallback).
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("DEVAURA_GITHUB_TOKEN")
    if token and len(token.strip()) > 0:
        return GitHubClient(token=token.strip())
    raise GitHubAuthRequiredError(
        "GitHub token not configured. Real GitHub operations require GITHUB_TOKEN in .env. Silent mock fallback is disabled."
    )


# ------------------------------------------------------------------------------
# Request & Response Schemas
# ------------------------------------------------------------------------------

class PRPrepareRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    owner: str = Field(default="shreyvirmani", description="Repository owner")
    repo: str = Field(default="Devaura", description="Repository name")


class PRApproveRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    approver: str = Field(default="human-operator", description="Human reviewer identifier")
    comments: Optional[str] = Field(default=None, description="Optional approval comments")


class PRRejectRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    approver: str = Field(default="human-operator", description="Human reviewer identifier")
    reason: str = Field(..., description="Rejection reason")


class PRCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    approval_token: str = Field(..., description="HMAC-SHA256 PR approval token")
    approver: str = Field(default="human-operator", description="Human reviewer identifier")
    draft: bool = Field(default=False, description="Whether to open as draft PR")


def serialize_pr_record(pr: PullRequestRecord) -> Dict[str, Any]:
    return {
        "id": pr.id,
        "repair_id": pr.repair_id,
        "investigation_id": pr.investigation_id,
        "repository_id": pr.repository_id,
        "provider": pr.provider,
        "owner": pr.owner,
        "repo": pr.repo,
        "base_branch": pr.base_branch,
        "base_revision": pr.base_revision,
        "repair_branch": pr.repair_branch,
        "commit_sha": pr.commit_sha,
        "pr_number": pr.pr_number,
        "pr_url": pr.pr_url,
        "pr_title": pr.pr_title,
        "pr_body": pr.pr_body,
        "pr_state": pr.pr_state,
        "patch_hash": pr.patch_hash,
        "verification_id": pr.verification_id,
        "approval_token": pr.approval_token,
        "approved_by": pr.approved_by,
        "approved_at": pr.approved_at.isoformat() if pr.approved_at else None,
        "status": pr.status,
        "ci_status": pr.ci_status_json,
        "review_status": pr.review_status_json,
        "metadata": pr.metadata_json,
        "created_at": pr.created_at.isoformat() if pr.created_at else None,
        "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
    }


def serialize_pr_event(event: PullRequestEventRecord) -> Dict[str, Any]:
    return {
        "id": event.id,
        "repair_id": event.repair_id,
        "pr_record_id": event.pr_record_id,
        "event_type": event.event_type,
        "description": event.description,
        "actor": event.actor,
        "metadata": event.metadata_json,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


# ------------------------------------------------------------------------------
# 1. POST /api/v1/repairs/{repair_id}/pr/prepare
# ------------------------------------------------------------------------------
@router.post(
    "/repairs/{repair_id}/pr/prepare",
    status_code=status.HTTP_200_OK,
    summary="Prepare Pull Request Context & Metadata",
)
async def prepare_pull_request(
    repair_id: str,
    req: PRPrepareRequest = PRPrepareRequest(),
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
):
    stmt = (
        select(RepairRecord)
        .where(RepairRecord.id == repair_id)
        .options(
            selectinload(RepairRecord.context),
            selectinload(RepairRecord.plan),
            selectinload(RepairRecord.patch),
            selectinload(RepairRecord.risk),
            selectinload(RepairRecord.approval),
            selectinload(RepairRecord.workspace),
            selectinload(RepairRecord.verification_runs),
            selectinload(RepairRecord.attempts),
            selectinload(RepairRecord.pull_request),
        )
    )
    result = await db.execute(stmt)
    repair = result.scalar_one_or_none()
    if not repair:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repair '{repair_id}' not found.",
        )

    # Hard entry validation: Must be VERIFIED
    if repair.status != "VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repair '{repair_id}' has status '{repair.status}'. PR creation requires status 'VERIFIED'.",
        )

    if not repair.patch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repair '{repair_id}' does not have an associated patch.",
        )

    # Synthesize VerifiedRepairResult from DB record
    latest_run = repair.verification_runs[-1] if repair.verification_runs else None
    verified_result = VerifiedRepairResult(
        repair_id=repair.id,
        investigation_id=repair.investigation_id,
        repository=f"{req.owner}/{req.repo}",
        base_revision=repair.base_revision or "HEAD",
        final_workspace_id=repair.workspace.isolated_path if repair.workspace else os.getcwd(),
        final_patch_hash=repair.patch.patch_hash,
        changed_files=repair.patch.changed_files or [],
        final_diff=repair.patch.unified_diff or "",
        verification_status="VERIFIED",
        checks=[],
        attempts=[],
    )

    orchestrator = PROrchestrator()
    try:
        prep_res = orchestrator.prepare_pull_request(
            repair=repair,
            verified_result=verified_result,
            owner=req.owner,
            repo=req.repo,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Cache PR context
    _PR_CONTEXT_STORE[repair_id] = prep_res.context

    # Audit event
    event = PullRequestEventRecord(
        repair_id=repair_id,
        event_type="PR_PREPARED",
        description=f"PR metadata prepared for branch {prep_res.context.repair_branch}",
        actor=user.username,
        metadata_json={
            "branch": prep_res.context.repair_branch,
            "patch_hash": prep_res.context.patch_hash,
            "changed_files": prep_res.context.changed_files,
        },
    )
    db.add(event)
    await db.commit()

    return prep_res.model_dump(mode="json")


# ------------------------------------------------------------------------------
# 2. GET /api/v1/repairs/{repair_id}/pr/context
# ------------------------------------------------------------------------------
@router.get(
    "/repairs/{repair_id}/pr/context",
    status_code=status.HTTP_200_OK,
    summary="Get Prepared PR Context",
)
async def get_pr_context(
    repair_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
):
    ctx = _PR_CONTEXT_STORE.get(repair_id)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PR context not found for repair '{repair_id}'. Call /prepare first.",
        )
    return ctx.model_dump(mode="json")


# ------------------------------------------------------------------------------
# 3. POST /api/v1/repairs/{repair_id}/pr/approve
# ------------------------------------------------------------------------------
@router.post(
    "/repairs/{repair_id}/pr/approve",
    status_code=status.HTTP_200_OK,
    summary="Cryptographic Human Authorization for PR Creation",
)
async def approve_pull_request(
    repair_id: str,
    req: PRApproveRequest = PRApproveRequest(),
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
):
    ctx = _PR_CONTEXT_STORE.get(repair_id)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PR context not found for repair '{repair_id}'. Call /prepare first.",
        )

    # Prohibit agent self-approval
    actor = req.approver or user.username
    if actor.lower() in {"agent", "devaura-agent", "system", "autonomous", "bot"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Autonomous agents are forbidden from approving PR creation. Human reviewer required.",
        )

    orchestrator = PROrchestrator()
    approval = orchestrator.authorize_pull_request(
        context=ctx,
        user_identity=actor,
    )

    # Persist approval record
    db_approval = PullRequestApprovalRecord(
        repair_id=repair_id,
        patch_hash=ctx.patch_hash,
        approval_token=approval.approval_token,
        approved_by=actor,
        status="APPROVED",
    )
    db.add(db_approval)

    # Audit event
    event = PullRequestEventRecord(
        repair_id=repair_id,
        event_type="PR_APPROVED",
        description=f"PR creation authorized by human operator '{actor}'",
        actor=actor,
        metadata_json={
            "approval_token": approval.approval_token,
            "patch_hash": ctx.patch_hash,
            "comments": req.comments,
        },
    )
    db.add(event)
    await db.commit()

    return approval.model_dump(mode="json")


# ------------------------------------------------------------------------------
# 4. POST /api/v1/repairs/{repair_id}/pr/reject
# ------------------------------------------------------------------------------
@router.post(
    "/repairs/{repair_id}/pr/reject",
    status_code=status.HTTP_200_OK,
    summary="Reject Pull Request Creation",
)
async def reject_pull_request(
    repair_id: str,
    req: PRRejectRequest,
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
):
    ctx = _PR_CONTEXT_STORE.get(repair_id)
    actor = req.approver or user.username

    # Persist rejection record
    db_rejection = PullRequestApprovalRecord(
        repair_id=repair_id,
        patch_hash=ctx.patch_hash if ctx else "unknown",
        approval_token="",
        approved_by=actor,
        status="REJECTED",
        rejection_reason=req.reason,
    )
    db.add(db_rejection)

    event = PullRequestEventRecord(
        repair_id=repair_id,
        event_type="PR_REJECTED",
        description=f"PR creation rejected by '{actor}': {req.reason}",
        actor=actor,
        metadata_json={"reason": req.reason},
    )
    db.add(event)
    await db.commit()

    return {
        "status": "PR_REJECTED",
        "repair_id": repair_id,
        "actor": actor,
        "reason": req.reason,
    }


# ------------------------------------------------------------------------------
# 5. POST /api/v1/repairs/{repair_id}/pr/create
# ------------------------------------------------------------------------------
@router.post(
    "/repairs/{repair_id}/pr/create",
    status_code=status.HTTP_201_CREATED,
    summary="Commit, Push, and Open GitHub Pull Request",
)
async def create_pull_request(
    repair_id: str,
    req: PRCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
):
    ctx = _PR_CONTEXT_STORE.get(repair_id)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PR context not found for repair '{repair_id}'. Call /prepare first.",
        )

    stmt = (
        select(RepairRecord)
        .where(RepairRecord.id == repair_id)
        .options(
            selectinload(RepairRecord.patch),
            selectinload(RepairRecord.workspace),
            selectinload(RepairRecord.pull_request),
        )
    )
    result = await db.execute(stmt)
    repair = result.scalar_one_or_none()
    if not repair:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repair '{repair_id}' not found.",
        )

    # Check for existing PR record in DB
    existing_stmt = select(PullRequestRecord).where(PullRequestRecord.repair_id == repair_id)
    res_pr = await db.execute(existing_stmt)
    existing_db_pr = res_pr.scalar_one_or_none()
    if existing_db_pr:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"PR #{existing_db_pr.pr_number} already exists for repair '{repair_id}': {existing_db_pr.pr_url}",
        )

    # Verify authorization
    gate = HumanPRApprovalGate()
    approval = PRApproval(
        repair_id=repair_id,
        patch_hash=ctx.patch_hash,
        base_revision=ctx.base_revision,
        repair_branch=ctx.repair_branch,
        repository=ctx.repository,
        approval_token=req.approval_token,
        approved_by=req.approver or user.username,
        status=PRApprovalStatus.APPROVED,
    )

    try:
        gate.verify_authorization(
            approval=approval,
            current_patch_hash=ctx.patch_hash,
            current_base_revision=ctx.base_revision,
            current_repair_branch=ctx.repair_branch,
            current_repository=ctx.repository,
            operation="CREATE_PULL_REQUEST",
        )
    except PRApprovalRequiredError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except PRPatchIntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    # Determine workspace directory
    target_path = repair.workspace.isolated_path if repair.workspace else os.getcwd()

    # Stage verified changes and create commit
    try:
        git_mgr = GitStateManager(repo_path=target_path)
        git_mgr.prepare_repair_branch(ctx.repair_branch)
        commit_info = git_mgr.create_repair_commit(
            commit_message=ctx.commit_message,
            allowed_files=ctx.changed_files,
            author_name="Devaura Repair Agent",
            author_email="repair-agent@devaura.ai",
        )
    except Exception as e:
        logger.warning(f"Git commit step notice: {e}")
        commit_info = None

    # Push and create PR using provider
    provider = get_git_provider()
    orchestrator = PROrchestrator(workspace_root=target_path)

    try:
        pr_result = await orchestrator.execute_pull_request_creation(
            repair=repair,
            context=ctx,
            approval=approval,
            provider=provider,
            local_repo_path=target_path,
        )
    except BaseRevisionChangedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Base revision changed from {e.verified_sha} to {e.remote_sha}. Repair re-verification required.",
        )
    except PullRequestAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pull request already exists on Git provider: {e.existing_url}",
        )
    except (GitConflictError, SecurityBlockError) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (GitHubAuthRequiredError, BranchPushError, PullRequestCreationError) as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    # Persist PullRequestRecord
    db_pr = PullRequestRecord(
        repair_id=repair.id,
        investigation_id=repair.investigation_id,
        repository_id=repair.repository_id,
        provider="github",
        owner=ctx.owner,
        repo=ctx.repo,
        base_branch=ctx.base_branch,
        base_revision=ctx.base_revision,
        repair_branch=ctx.repair_branch,
        commit_sha=pr_result.commit_sha or (commit_info.sha if commit_info else "none"),
        pr_number=pr_result.pr_number,
        pr_url=pr_result.pr_url,
        pr_title=pr_result.title,
        pr_body=pr_result.body,
        pr_state=pr_result.state.value,
        patch_hash=ctx.patch_hash,
        verification_id=repair.latest_verification_id,
        approval_token=req.approval_token,
        approved_by=req.approver or user.username,
        approved_at=datetime.now(timezone.utc),
        status="PR_CREATED",
        ci_status_json={},
        review_status_json={},
        metadata_json={
            "changed_files": ctx.changed_files,
            "provider_type": provider.provider_type.value,
        },
    )
    db.add(db_pr)

    # Event log
    event = PullRequestEventRecord(
        repair_id=repair_id,
        pr_record_id=db_pr.id,
        event_type="PR_CREATED",
        description=f"GitHub PR #{pr_result.pr_number} opened: {pr_result.pr_url}",
        actor=req.approver or user.username,
        metadata_json={
            "pr_number": pr_result.pr_number,
            "pr_url": pr_result.pr_url,
            "branch": ctx.repair_branch,
        },
    )
    db.add(event)
    await db.commit()
    await db.refresh(db_pr)

    return serialize_pr_record(db_pr)


# ------------------------------------------------------------------------------
# 6. GET /api/v1/repairs/{repair_id}/pr
# ------------------------------------------------------------------------------
@router.get(
    "/repairs/{repair_id}/pr",
    status_code=status.HTTP_200_OK,
    summary="Get Pull Request Details for Repair",
)
async def get_pull_request(
    repair_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
):
    stmt = select(PullRequestRecord).where(PullRequestRecord.repair_id == repair_id)
    res = await db.execute(stmt)
    pr = res.scalar_one_or_none()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pull request found for repair '{repair_id}'.",
        )
    return serialize_pr_record(pr)


# ------------------------------------------------------------------------------
# 7. GET /api/v1/repairs/{repair_id}/pr/status
# ------------------------------------------------------------------------------
@router.get(
    "/repairs/{repair_id}/pr/status",
    status_code=status.HTTP_200_OK,
    summary="Query Live PR CI & Review Status",
)
async def get_pr_status(
    repair_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
):
    stmt = select(PullRequestRecord).where(PullRequestRecord.repair_id == repair_id)
    res = await db.execute(stmt)
    pr = res.scalar_one_or_none()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pull request found for repair '{repair_id}'.",
        )

    provider = get_git_provider()
    try:
        ci_info = await provider.get_ci_status(
            owner=pr.owner, repo=pr.repo, commit_sha=pr.commit_sha or "HEAD"
        )
        review_info = await provider.get_review_status(
            owner=pr.owner, repo=pr.repo, pr_number=pr.pr_number
        )
    except Exception as e:
        logger.warning(f"Failed to fetch live PR status from provider: {e}")
        ci_info = CIStatusInfo()
        review_info = ReviewInfo()

    # Update in DB
    pr.ci_status_json = ci_info.model_dump(mode="json")
    pr.review_status_json = review_info.model_dump(mode="json")
    await db.commit()

    return {
        "repair_id": repair_id,
        "pr_number": pr.pr_number,
        "pr_url": pr.pr_url,
        "pr_state": pr.pr_state,
        "ci_status": ci_info.model_dump(mode="json"),
        "review_status": review_info.model_dump(mode="json"),
    }


# ------------------------------------------------------------------------------
# 8. GET /api/v1/repairs/{repair_id}/pr/history
# ------------------------------------------------------------------------------
@router.get(
    "/repairs/{repair_id}/pr/history",
    status_code=status.HTTP_200_OK,
    summary="Audit Trail of PR Lifecycle Events",
)
async def get_pr_history(
    repair_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
):
    stmt = (
        select(PullRequestEventRecord)
        .where(PullRequestEventRecord.repair_id == repair_id)
        .order_by(desc(PullRequestEventRecord.created_at))
    )
    res = await db.execute(stmt)
    events = res.scalars().all()
    return [serialize_pr_event(e) for e in events]


# ------------------------------------------------------------------------------
# 9. GET /api/v1/pull-requests
# ------------------------------------------------------------------------------
@router.get(
    "/pull-requests",
    status_code=status.HTTP_200_OK,
    summary="List All Pull Requests",
)
async def list_pull_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    user: CurrentUser = Depends(get_current_user),
):
    stmt = (
        select(PullRequestRecord)
        .order_by(desc(PullRequestRecord.created_at))
        .offset(skip)
        .limit(limit)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()
    return [serialize_pr_record(r) for r in records]
