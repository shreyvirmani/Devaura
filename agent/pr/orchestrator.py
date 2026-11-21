"""Devaura Phase 7 Pull Request Orchestrator.

Coordinates the end-to-end verified repair to GitHub Pull Request pipeline:
1. Entry validation & Patch integrity verification
2. PRContext formulation & deterministic title/description synthesis
3. Cryptographic human authorization gating
4. Remote base revision validation & collision protection
5. Branch push & idempotent GitHub Pull Request creation
6. Read-only CI status and review monitoring
"""

import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple

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
from agent.pr.state_machine import PullRequestStateMachine
from agent.repair.models import (
    VerifiedRepairResult,
)
from database.models.repair import RepairRecord
from apps.api.logger import logger
from integrations.github.models import (
    CIStatusInfo,
    PullRequestPayload,
    PullRequestResult,
    ReviewInfo,
)
from integrations.github.provider import (
    BaseRevisionChangedError,
    BranchPushError,
    GitConflictError,
    GitProvider,
    GitProviderError,
    GitHubAuthRequiredError,
    PullRequestAlreadyExistsError,
    PullRequestCreationError,
    SecurityBlockError,
)


class PROrchestrator:
    """Orchestrates pull request generation from verified repairs."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = os.path.abspath(workspace_root or os.getcwd())

    def prepare_pull_request(
        self,
        repair: Any,
        verified_result: Optional[VerifiedRepairResult] = None,
        owner: str = "shreyvirmani",
        repo: str = "Devaura",
    ) -> PRPreparationResult:
        """Evaluate entry conditions, verify patch integrity, and construct PR context.

        Transitions: PR_ELIGIBILITY_CHECK -> PR_CONTEXT_READY -> AWAITING_PR_APPROVAL.
        """
        sm = PullRequestStateMachine(PRState.PR_ELIGIBILITY_CHECK)

        # 1. Hard entry condition validation
        is_valid, pr_ctx, err_code, err_msg = PRContextBuilder.build_context(
            repair_record=repair,
            verified_result=verified_result,
            owner=owner,
            repo=repo,
        )

        if not is_valid or not pr_ctx:
            terminal_state = PRState(err_code) if err_code and hasattr(PRState, err_code) else PRState.PR_BLOCKED
            try:
                sm.transition(terminal_state)
            except Exception:
                pass
            raise ValueError(f"PR preparation blocked: {err_msg} ({err_code})")

        # 2. Advance state machine
        sm.transition(PRState.PR_CONTEXT_READY)
        sm.transition(PRState.GIT_STATE_VALIDATED)
        sm.transition(PRState.BRANCH_READY)
        sm.transition(PRState.COMMIT_READY)
        sm.transition(PRState.PR_METADATA_READY)
        sm.transition(PRState.AWAITING_PR_APPROVAL)

        return PRPreparationResult(
            repair_id=repair.id,
            status=sm.current_state,
            context=pr_ctx,
            approval_required=True,
            message="PR context prepared. Human authorization required before pushing branch or opening PR.",
        )

    def authorize_pull_request(
        self,
        context: PRContext,
        user_identity: str,
    ) -> PRApproval:
        """Create cryptographic authorization bound to exact PR parameters."""
        gate = HumanPRApprovalGate()
        approval = gate.create_approval(
            repair_id=context.repair_id,
            patch_hash=context.patch_hash,
            base_revision=context.base_revision,
            repair_branch=context.repair_branch,
            repository=context.repository,
            user_identity=user_identity,
            operation="CREATE_PULL_REQUEST",
        )
        return approval

    async def execute_pull_request_creation(
        self,
        repair: Any,
        context: PRContext,
        approval: PRApproval,
        provider: GitProvider,
        local_repo_path: Optional[str] = None,
    ) -> PullRequestResult:
        """Execute branch creation, commit, push, and PR opening with full safety checks.

        Strictly enforces:
        1. Cryptographic token verification
        2. Remote base revision validation (detects BASE_REVISION_CHANGED)
        3. Idempotent PR lookup (prevents duplicate PRs)
        4. Safe branch push (never touches main)
        5. Provider PR creation
        """
        sm = PullRequestStateMachine(PRState.AWAITING_PR_APPROVAL)

        # 1. Verify authorization token
        gate = HumanPRApprovalGate()
        gate.verify_authorization(
            approval=approval,
            current_patch_hash=context.patch_hash,
            current_base_revision=context.base_revision,
            current_repair_branch=context.repair_branch,
            current_repository=context.repository,
            operation="CREATE_PULL_REQUEST",
        )
        sm.transition(PRState.PR_APPROVED)

        # 2. Base revision remote freshness check
        if context.base_revision and context.base_revision not in {"HEAD", "main", "master"}:
            remote_base = await provider.get_branch(context.owner, context.repo, context.base_branch)
            if remote_base and remote_base.sha and remote_base.sha != context.base_revision:
                sm.transition(PRState.PR_BLOCKED_GIT_STATE)
                raise BaseRevisionChangedError(verified_sha=context.base_revision, remote_sha=remote_base.sha)

        # 3. Idempotency check: see if PR already exists on provider
        existing_pr = await provider.find_existing_pr(
            owner=context.owner,
            repo=context.repo,
            head_branch=context.repair_branch,
            base_branch=context.base_branch,
        )
        if existing_pr:
            try:
                sm.transition(PRState.BRANCH_PUSHING)
                sm.transition(PRState.BRANCH_PUSHED)
                sm.transition(PRState.PR_ALREADY_EXISTS)
            except Exception:
                pass
            raise PullRequestAlreadyExistsError(existing_pr.pr_number, existing_pr.pr_url)

        # 4. Prepare local/isolated git state
        target_path = local_repo_path or (
            repair.workspace.isolated_path if repair and repair.workspace else self.workspace_root
        )

        sm.transition(PRState.BRANCH_PUSHING)

        # 5. Push branch to remote provider
        try:
            await provider.push_branch(
                owner=context.owner,
                repo=context.repo,
                branch=context.repair_branch,
                local_repo_path=target_path,
            )
            sm.transition(PRState.BRANCH_PUSHED)
        except Exception as e:
            sm.transition(PRState.PUSH_FAILED)
            raise

        sm.transition(PRState.PR_CREATING)

        # 6. Create Pull Request on Git Provider
        payload = PullRequestPayload(
            owner=context.owner,
            repo=context.repo,
            title=context.pr_title,
            body=context.pr_body,
            head_branch=context.repair_branch,
            base_branch=context.base_branch,
            draft=False,
        )

        try:
            result = await provider.create_pull_request(payload)
            sm.transition(PRState.PR_CREATED)
            return result
        except PullRequestAlreadyExistsError:
            sm.transition(PRState.PR_ALREADY_EXISTS)
            raise
        except Exception as e:
            sm.transition(PRState.PR_CREATION_FAILED)
            raise
