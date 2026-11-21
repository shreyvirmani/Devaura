"""Devaura Phase 7 Pull Request Orchestration & Human Review Test Cases.

Comprehensive test suite validating TC-01 through TC-24:
- TC-01: Entry Condition Enforcement: Unverified repair rejected
- TC-02: Entry Condition Enforcement: Patch hash mismatch fails PR preparation
- TC-03: Entry Condition Enforcement: Post-verification mutations blocked
- TC-04: PR Context Synthesis: Conventional commit title generation
- TC-05: PR Context Synthesis: Evidence-backed markdown description
- TC-06: PR Context Synthesis: Sensitive file detection blocks PR
- TC-07: Branch Isolation: Branch naming convention devaura/repair/{id[:8]}
- TC-08: Branch Isolation: Base branch protection (never touch main)
- TC-09: Branch Isolation: Collision handling for existing branches
- TC-10: Staged Commit: Only verified files staged
- TC-11: Commit Attribution: Correct author & committer metadata
- TC-12: Human Approval Gate: HMAC-SHA256 token generation
- TC-13: Human Approval Gate: Cryptographic parameter binding
- TC-14: Human Approval Gate: Agent self-approval prohibited
- TC-15: Human Approval Gate: Phase 5/6 token cannot be reused for Phase 7
- TC-16: Remote Base Validation: Matching base revision passes
- TC-17: Remote Base Validation: Stale base revision raises BaseRevisionChangedError
- TC-18: Git Provider Idempotency: Duplicate PR prevention
- TC-19: Provider Error Handling: GitHub authentication failure (HTTP 401)
- TC-20: Provider Error Handling: Rate limiting (HTTP 429)
- TC-21: Provider Error Handling: Network failure / timeout
- TC-22: CI Status Monitoring: Structured CI check-run reporting
- TC-23: Review Status Monitoring: Structured PR review state reporting
- TC-24: MCP Tool Integration: 10 tools registered with correct RiskLevel policies
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
import pytest

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
    PatchResult,
    RepairApproval,
    RepairContext,
    RepairPlan,
    VerifiedRepairResult,
)
from database.models.repair import RepairRecord
from integrations.github.client import GitHubClient
from integrations.github.mock_provider import MockGitProvider
from integrations.github.models import (
    BranchInfo,
    CIStatus,
    CIStatusInfo,
    CommitInfo,
    PullRequestPayload,
    PullRequestResult,
    PullRequestState,
    ReviewInfo,
    ReviewStatus,
)
from integrations.github.provider import (
    BaseRevisionChangedError,
    BranchPushError,
    GitConflictError,
    GitNetworkError,
    GitProvider,
    GitRateLimitError,
    GitHubAuthRequiredError,
    PullRequestAlreadyExistsError,
    PullRequestCreationError,
    SecurityBlockError,
)
from mcp.models import RiskLevel
from mcp.server.devaura_server import get_native_mcp_server


class MockRepair:
    """Helper mock simulating database RepairRecord."""

    def __init__(
        self,
        repair_id: str = "rep-test-01",
        status: str = "VERIFIED",
        patch_hash: str = "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
        diff: str = "--- a/auth.py\n+++ b/auth.py\n@@ -1 +1 @@\n-old\n+new\n",
        changed_files: list = None,
        base_revision: str = "base_rev_12345",
        workspace_path: str = None,
    ):
        self.id = repair_id
        self.investigation_id = f"inv-{repair_id[:8]}"
        self.repository_id = "repo-devaura"
        self.status = status
        self.base_revision = base_revision
        self.target_branch = "main"
        self.latest_verification_id = f"ver-{repair_id[:8]}"
        self.current_attempt = 1
        self.max_attempts = 3
        self.patch = type(
            "Patch",
            (),
            {
                "patch_hash": patch_hash,
                "unified_diff": diff,
                "changed_files": changed_files or ["auth.py"],
                "lines_added": 1,
                "lines_removed": 1,
                "explanation": "Fix null pointer in auth",
            },
        )()
        self.plan = type(
            "Plan",
            (),
            {
                "objective": "Resolve null check issue in auth module",
                "root_cause": "Unchecked None token index",
                "tests_to_run": ["tests/test_auth.py"],
                "proposed_changes": [],
            },
        )()
        self.workspace = type(
            "Workspace",
            (),
            {"isolated_path": workspace_path or tempfile.gettempdir(), "status": "APPLIED"},
        )()


@pytest.fixture
def temp_git_repo():
    """Create a temporary initialized git repository."""
    tmp_dir = tempfile.mkdtemp(prefix="devaura_test_git_")
    subprocess.run(["git", "init"], cwd=tmp_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=tmp_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@devaura.ai"], cwd=tmp_dir, check=True)

    # Initial commit on main
    main_file = os.path.join(tmp_dir, "auth.py")
    with open(main_file, "w") as f:
        f.write("# initial auth file\n")
    subprocess.run(["git", "add", "auth.py"], cwd=tmp_dir, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=tmp_dir, check=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=tmp_dir, check=True)

    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


# ------------------------------------------------------------------------------
# TC-01: Entry Condition Enforcement: Unverified repair rejected
# ------------------------------------------------------------------------------
def test_tc01_unverified_repair_rejected():
    repair = MockRepair(status="AWAITING_APPROVAL")
    is_valid, ctx, code, msg = PRContextBuilder.build_context(repair)
    assert not is_valid
    assert ctx is None
    assert code == "PR_BLOCKED_UNVERIFIED"
    assert "AWAITING_APPROVAL" in msg


# ------------------------------------------------------------------------------
# TC-02: Entry Condition Enforcement: Patch hash mismatch fails PR preparation
# ------------------------------------------------------------------------------
def test_tc02_patch_hash_mismatch_fails():
    repair = MockRepair(status="VERIFIED", patch_hash="hash_aaa")
    verified_res = VerifiedRepairResult(
        repair_id=repair.id,
        investigation_id=repair.investigation_id,
        repository="shreyvirmani/Devaura",
        base_revision="rev_1",
        final_workspace_id="/tmp",
        final_patch_hash="hash_bbb",  # Mismatch!
        changed_files=["auth.py"],
        final_diff="diff",
        verification_status="VERIFIED",
        checks=[],
        attempts=[],
    )
    is_valid, ctx, code, msg = PRContextBuilder.build_context(repair, verified_result=verified_res)
    assert not is_valid
    assert code in {"PR_BLOCKED_PATCH_CHANGED", "PR_BLOCKED_PATCH_MISMATCH"}
    assert "modified after verification" in msg or "mismatch" in msg.lower()


# ------------------------------------------------------------------------------
# TC-03: Entry Condition Enforcement: Post-verification mutations blocked
# ------------------------------------------------------------------------------
def test_tc03_post_verification_mutations_blocked(temp_git_repo):
    # Mutate a file not in verified changes
    rogue_file = os.path.join(temp_git_repo, "rogue.py")
    with open(rogue_file, "w") as f:
        f.write("malicious payload")

    mgr = GitStateManager(repo_path=temp_git_repo)
    with pytest.raises(SecurityBlockError) as exc_info:
        mgr.create_repair_commit(
            commit_message="fix(auth): clean fix",
            allowed_files=["auth.py"],
        )
    assert "Unverified dirty file detected" in str(exc_info.value)


# ------------------------------------------------------------------------------
# TC-04: PR Context Synthesis: Conventional commit title generation
# ------------------------------------------------------------------------------
def test_tc04_pr_title_conventional_commits():
    repair = MockRepair(status="VERIFIED")
    is_valid, ctx, _, _ = PRContextBuilder.build_context(repair)
    assert is_valid
    assert ctx is not None
    assert ctx.pr_title.startswith("fix")
    assert not ctx.pr_title.endswith(".")


# ------------------------------------------------------------------------------
# TC-05: PR Context Synthesis: Evidence-backed markdown description
# ------------------------------------------------------------------------------
def test_tc05_pr_description_structured():
    repair = MockRepair(status="VERIFIED")
    is_valid, ctx, _, _ = PRContextBuilder.build_context(repair)
    assert is_valid
    assert "## Summary" in ctx.pr_body
    assert "## Root Cause" in ctx.pr_body
    assert "## Verification" in ctx.pr_body
    assert "Tests:" in ctx.pr_body
    assert "Lint:" in ctx.pr_body
    assert "Typecheck:" in ctx.pr_body
    assert "## Files Changed" in ctx.pr_body
    assert "Devaura" in ctx.pr_body


# ------------------------------------------------------------------------------
# TC-06: PR Context Synthesis: Sensitive file detection blocks PR
# ------------------------------------------------------------------------------
def test_tc06_sensitive_files_blocked():
    repair = MockRepair(status="VERIFIED", changed_files=["auth.py", ".env.production"])
    is_valid, ctx, code, msg = PRContextBuilder.build_context(repair)
    assert not is_valid
    assert code in {"PR_BLOCKED_SECURITY", "PR_BLOCKED_SENSITIVE_FILES"}
    assert ".env.production" in msg


# ------------------------------------------------------------------------------
# TC-07: Branch Isolation: Branch naming convention devaura/repair/{id[:8]}
# ------------------------------------------------------------------------------
def test_tc07_branch_isolation_naming():
    repair_id = "rep-abcdef1234567890"
    repair = MockRepair(repair_id=repair_id, status="VERIFIED")
    is_valid, ctx, _, _ = PRContextBuilder.build_context(repair)
    assert is_valid
    assert ctx.repair_branch == "devaura/repair/rep-abcd"


# ------------------------------------------------------------------------------
# TC-08: Branch Isolation: Base branch protection (never touch main)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc08_base_branch_strictly_protected():
    provider = MockGitProvider()
    with pytest.raises(SecurityBlockError) as exc_info:
        await provider.push_branch(
            owner="shreyvirmani",
            repo="Devaura",
            branch="main",  # Protected base branch!
            local_repo_path="/tmp",
        )
    assert "Cannot push directly to base branch" in str(exc_info.value)


# ------------------------------------------------------------------------------
# TC-09: Branch Isolation: Collision handling for existing branches
# ------------------------------------------------------------------------------
def test_tc09_branch_collision_handling(temp_git_repo):
    mgr = GitStateManager(repo_path=temp_git_repo)
    # First creation succeeds
    b1 = mgr.prepare_repair_branch("devaura/repair/rep-0001")
    assert b1.name == "devaura/repair/rep-0001"
    assert b1.is_current

    # Switching back to main
    subprocess.run(["git", "checkout", "main"], cwd=temp_git_repo, check=True)

    # Second invocation switches into existing branch cleanly
    b2 = mgr.prepare_repair_branch("devaura/repair/rep-0001")
    assert b2.name == "devaura/repair/rep-0001"
    assert b2.is_current


# ------------------------------------------------------------------------------
# TC-10: Staged Commit: Only verified files staged
# ------------------------------------------------------------------------------
def test_tc10_staged_commit_verified_files_only(temp_git_repo):
    auth_file = os.path.join(temp_git_repo, "auth.py")
    with open(auth_file, "a") as f:
        f.write("# added fix\n")

    mgr = GitStateManager(repo_path=temp_git_repo)
    commit = mgr.create_repair_commit(
        commit_message="fix(auth): verify staged files",
        allowed_files=["auth.py"],
    )
    assert commit.sha is not None
    assert "fix(auth): verify staged files" in commit.message


# ------------------------------------------------------------------------------
# TC-11: Commit Attribution: Correct author & committer metadata
# ------------------------------------------------------------------------------
def test_tc11_commit_attribution(temp_git_repo):
    auth_file = os.path.join(temp_git_repo, "auth.py")
    with open(auth_file, "a") as f:
        f.write("# attribution test\n")

    mgr = GitStateManager(repo_path=temp_git_repo)
    commit = mgr.create_repair_commit(
        commit_message="fix(auth): attribution test",
        allowed_files=["auth.py"],
        author_name="Devaura Repair Agent",
        author_email="repair-agent@devaura.ai",
    )
    assert "Devaura Repair Agent" in commit.author
    assert "repair-agent@devaura.ai" in commit.author


# ------------------------------------------------------------------------------
# TC-12: Human Approval Gate: HMAC-SHA256 token generation
# ------------------------------------------------------------------------------
def test_tc12_human_approval_gate_hmac_token():
    gate = HumanPRApprovalGate(secret_key="test-secret")
    approval = gate.create_approval(
        repair_id="rep-12345",
        patch_hash="patch_hash_1",
        base_revision="base_sha_1",
        repair_branch="devaura/repair/rep-1234",
        repository="shreyvirmani/Devaura",
        user_identity="human-reviewer@devaura.ai",
    )
    assert approval.approval_token.startswith("pr-auth-")
    assert approval.status == PRApprovalStatus.APPROVED


# ------------------------------------------------------------------------------
# TC-13: Human Approval Gate: Cryptographic parameter binding
# ------------------------------------------------------------------------------
def test_tc13_approval_token_binding():
    gate = HumanPRApprovalGate(secret_key="test-secret")
    approval = gate.create_approval(
        repair_id="rep-12345",
        patch_hash="patch_hash_1",
        base_revision="base_sha_1",
        repair_branch="devaura/repair/rep-1234",
        repository="shreyvirmani/Devaura",
        user_identity="human-reviewer@devaura.ai",
    )

    # Valid check passes
    gate.verify_authorization(
        approval=approval,
        current_patch_hash="patch_hash_1",
        current_base_revision="base_sha_1",
        current_repair_branch="devaura/repair/rep-1234",
        current_repository="shreyvirmani/Devaura",
    )

    # Tampered patch hash fails
    with pytest.raises(PRPatchIntegrityError):
        gate.verify_authorization(
            approval=approval,
            current_patch_hash="tampered_hash",
            current_base_revision="base_sha_1",
            current_repair_branch="devaura/repair/rep-1234",
            current_repository="shreyvirmani/Devaura",
        )


# ------------------------------------------------------------------------------
# TC-14: Human Approval Gate: Agent self-approval prohibited
# ------------------------------------------------------------------------------
def test_tc14_agent_self_approval_prohibited():
    gate = HumanPRApprovalGate()
    for forbidden_id in ["agent", "devaura-agent", "autonomous-loop", "bot"]:
        with pytest.raises(PRApprovalRequiredError) as exc_info:
            gate.create_approval(
                repair_id="rep-123",
                patch_hash="hash",
                base_revision="base",
                repair_branch="branch",
                repository="repo",
                user_identity=forbidden_id,
            )
        assert "Autonomous agent self-approval is forbidden" in str(exc_info.value)


# ------------------------------------------------------------------------------
# TC-15: Human Approval Gate: Phase 5/6 token cannot be reused for Phase 7
# ------------------------------------------------------------------------------
def test_tc15_phase5_phase6_token_cannot_be_reused():
    gate = HumanPRApprovalGate()
    # Generated with operation="REPAIR_APPROVAL" (Phase 5)
    p5_approval = gate.create_approval(
        repair_id="rep-123",
        patch_hash="hash",
        base_revision="base",
        repair_branch="branch",
        repository="repo",
        user_identity="human-reviewer",
        operation="REPAIR_APPROVAL",
    )

    # Attempting to use for "CREATE_PULL_REQUEST" (Phase 7) must fail
    with pytest.raises(PRPatchIntegrityError) as exc_info:
        gate.verify_authorization(
            approval=p5_approval,
            current_patch_hash="hash",
            current_base_revision="base",
            current_repair_branch="branch",
            current_repository="repo",
            operation="CREATE_PULL_REQUEST",
        )
    assert "Operation 'CREATE_PULL_REQUEST' does not match" in str(exc_info.value)


# ------------------------------------------------------------------------------
# TC-16: Remote Base Validation: Matching base revision passes
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc16_remote_base_validation_success():
    provider = MockGitProvider(initial_default_branch_sha="base_sha_clean")
    branch = await provider.get_branch("shreyvirmani", "Devaura", "main")
    assert branch.sha == "base_sha_clean"


# ------------------------------------------------------------------------------
# TC-17: Remote Base Validation: Stale base revision raises BaseRevisionChangedError
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc17_stale_base_revision_blocked():
    provider = MockGitProvider(initial_default_branch_sha="new_main_sha_9999")
    orchestrator = PROrchestrator()
    repair = MockRepair(status="VERIFIED", base_revision="verified_sha_1111")
    is_valid, ctx, _, _ = PRContextBuilder.build_context(repair)

    gate = HumanPRApprovalGate()
    approval = gate.create_approval(
        repair_id=repair.id,
        patch_hash=ctx.patch_hash,
        base_revision=ctx.base_revision,
        repair_branch=ctx.repair_branch,
        repository=ctx.repository,
        user_identity="human-reviewer",
        operation="CREATE_PULL_REQUEST",
    )

    with pytest.raises(BaseRevisionChangedError) as exc_info:
        await orchestrator.execute_pull_request_creation(
            repair=repair,
            context=ctx,
            approval=approval,
            provider=provider,
            local_repo_path="/tmp",
        )
    assert exc_info.value.verified_sha == "verified_sha_1111"
    assert exc_info.value.remote_sha == "new_main_sha_9999"


# ------------------------------------------------------------------------------
# TC-18: Git Provider Idempotency: Duplicate PR prevention
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc18_git_provider_idempotency():
    provider = MockGitProvider()
    payload = PullRequestPayload(
        owner="shreyvirmani",
        repo="Devaura",
        title="fix: test idempotency",
        body="test description",
        head_branch="devaura/repair/rep-001",
        base_branch="main",
    )
    # First creation succeeds
    res1 = await provider.create_pull_request(payload)
    assert res1.pr_number >= 1

    # Second creation with identical head and base branch raises PullRequestAlreadyExistsError
    with pytest.raises(PullRequestAlreadyExistsError) as exc_info:
        await provider.create_pull_request(payload)
    assert exc_info.value.existing_pr_number == res1.pr_number


# ------------------------------------------------------------------------------
# TC-19: Provider Error Handling: GitHub authentication failure (HTTP 401)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc19_provider_auth_failure_handling():
    provider = MockGitProvider()
    provider.simulate_auth_failure = True
    payload = PullRequestPayload(
        owner="shreyvirmani",
        repo="Devaura",
        title="fix: auth failure",
        body="test",
        head_branch="devaura/repair/auth",
        base_branch="main",
    )
    with pytest.raises(GitHubAuthRequiredError):
        await provider.create_pull_request(payload)


# ------------------------------------------------------------------------------
# TC-20: Provider Error Handling: Rate limiting (HTTP 429)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc20_provider_rate_limiting():
    provider = MockGitProvider()
    provider.simulate_rate_limit = True
    with pytest.raises(GitRateLimitError) as exc_info:
        await provider.get_branch("shreyvirmani", "Devaura", "main")
    assert exc_info.value.reset_timestamp > 0


# ------------------------------------------------------------------------------
# TC-21: Provider Error Handling: Network failure / timeout
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc21_provider_network_failure():
    provider = MockGitProvider()
    provider.simulate_network_error = True
    with pytest.raises(GitNetworkError):
        await provider.get_branch("shreyvirmani", "Devaura", "main")


# ------------------------------------------------------------------------------
# TC-22: CI Status Monitoring: Structured CI check-run reporting
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc22_ci_status_monitoring():
    provider = MockGitProvider()
    ci = await provider.get_ci_status("shreyvirmani", "Devaura", "commit_sha_123")
    assert ci.overall_status in {CIStatus.SUCCESS, CIStatus.PENDING}
    assert ci.total_checks >= 1
    assert ci.checks[0].check_name == "devaura/verification"


# ------------------------------------------------------------------------------
# TC-23: Review Status Monitoring: Structured PR review state reporting
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc23_review_status_monitoring():
    provider = MockGitProvider()
    review = await provider.get_review_status("shreyvirmani", "Devaura", 1)
    assert review.review_status in {ReviewStatus.PENDING, ReviewStatus.APPROVED}


# ------------------------------------------------------------------------------
# TC-24: MCP Tool Integration: 10 tools registered with correct RiskLevel policies
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tc24_mcp_native_tools_policy():
    server = get_native_mcp_server()
    tools = await server.list_tools()
    tool_map = {t.name: t for t in tools}

    expected_pr_tools = {
        # SAFE
        "get_pr_context": RiskLevel.SAFE,
        "get_pull_request": RiskLevel.SAFE,
        "get_pull_request_history": RiskLevel.SAFE,
        "get_pr_status": RiskLevel.SAFE,
        # CONTROLLED
        "prepare_pull_request": RiskLevel.CONTROLLED,
        "prepare_repair_branch": RiskLevel.CONTROLLED,
        "prepare_repair_commit": RiskLevel.CONTROLLED,
        "request_pr_approval": RiskLevel.CONTROLLED,
        # DANGEROUS
        "push_repair_branch": RiskLevel.DANGEROUS,
        "create_pull_request": RiskLevel.DANGEROUS,
    }

    for name, expected_risk in expected_pr_tools.items():
        assert name in tool_map, f"MCP tool '{name}' not registered in native server"
        mgr_tool = server._tool_manager.get_tool(name)
        risk = getattr(mgr_tool.fn, "risk_level", None)
        assert risk == expected_risk, f"MCP tool '{name}' expected risk {expected_risk}, got {risk}"
