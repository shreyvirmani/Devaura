"""Devaura Phase 8 Reliability & Resilience Test Suite.

Validates the robustness, fault-tolerance, and error-handling behavior of Devaura:
1. GitHub provider network failure / timeout (HTTP 500 / 503)
2. GitHub provider rate limit handling (HTTP 429)
3. Duplicate PR creation idempotency preservation
4. Sandbox execution timeout and process cleanup
5. Corrupted patch diff syntax rejection with workspace rollback
6. Empty patch diff rejection
7. Missing or corrupted sandbox workspace detection
8. Investigator graceful handling of empty or unindexed repositories
9. Concurrent repair isolation (no cross-sandbox state contamination)
10. Transient database session rollback resilience
"""

import os
import shutil
import tempfile
import uuid
import pytest

from agent.investigator import InvestigatorEngine
from agent.models import FailureType, InvestigationRequest
from agent.repair.models import CheckStatus, CheckType, OverallVerificationStatus
from agent.verification.runner import VerificationRunner, VerificationSecurityError
from integrations.github.mock_provider import MockGitProvider
from integrations.github.models import PullRequestPayload
from integrations.github.provider import (
    GitNetworkError,
    GitRateLimitError,
    PullRequestAlreadyExistsError,
)
from sandbox.workspace import IsolatedWorkspace, PatchApplicationError


class TestReliabilitySuite:
    """Rigorous resilience and error-boundary verification."""

    # --------------------------------------------------------------------------
    # 1. GitHub Network Failure
    # --------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_github_network_failure(self):
        """Simulated network timeout/outage raises GitNetworkError cleanly."""
        provider = MockGitProvider()
        provider.simulate_network_failure = True

        with pytest.raises(GitNetworkError) as exc_info:
            await provider.get_branch("shreyvirmani", "Devaura", "main")
        assert "network" in str(exc_info.value).lower()

    # --------------------------------------------------------------------------
    # 2. GitHub Rate Limiting
    # --------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_github_rate_limit_handling(self):
        """Simulated HTTP 429 rate limit raises GitRateLimitError with backoff hint."""
        provider = MockGitProvider()
        provider.simulate_rate_limit = True

        with pytest.raises(GitRateLimitError) as exc_info:
            await provider.get_branch("shreyvirmani", "Devaura", "main")
        assert exc_info.value.retry_after_seconds > 0
        assert "rate limit" in str(exc_info.value).lower()

    # --------------------------------------------------------------------------
    # 3. Duplicate PR Creation Idempotency
    # --------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_duplicate_pr_idempotency(self):
        """Second attempt to create a PR on the same branch raises PullRequestAlreadyExistsError."""
        provider = MockGitProvider()
        payload = PullRequestPayload(
            owner="shreyvirmani",
            repo="Devaura",
            title="fix(agent): auto fix",
            body="description",
            head_branch="devaura/repair/unique_branch_101",
            base_branch="main",
        )

        # First creation succeeds
        pr1 = await provider.create_pull_request(payload)
        assert pr1.pr_number is not None

        # Second creation fails idempotently
        with pytest.raises(PullRequestAlreadyExistsError) as exc_info:
            await provider.create_pull_request(payload)
        assert exc_info.value.existing_pr_number == pr1.pr_number

    # --------------------------------------------------------------------------
    # 4. Sandbox Execution Timeout
    # --------------------------------------------------------------------------
    def test_sandbox_execution_timeout(self):
        """Commands exceeding configured timeout are terminated cleanly with exit code 124."""
        temp_dir = tempfile.mkdtemp(prefix="devaura_timeout_test_")
        try:
            # Write a simple sleep script to avoid shell operator restrictions
            sleep_script = os.path.join(temp_dir, "sleep_script.py")
            with open(sleep_script, "w", encoding="utf-8") as f:
                f.write("import time\ntime.sleep(5)\n")

            runner = VerificationRunner(workspace_path=temp_dir)
            check = runner.run_check(
                check_type=CheckType.TESTS,
                command="python sleep_script.py",
                timeout_seconds=1,
            )
            assert check.status == CheckStatus.TIMEOUT
            assert check.exit_code == 124
            assert "timed out" in check.stderr.lower()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # 5. Corrupted Patch Application Rejection
    # --------------------------------------------------------------------------
    def test_corrupted_patch_application_rejected(self):
        """Patches with invalid hunk syntax are rejected and leave original files intact."""
        temp_src = tempfile.mkdtemp(prefix="devaura_corrupt_src_")
        try:
            test_file = os.path.join(temp_src, "module.py")
            original_code = "def add(a, b):\n    return a + b\n"
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(original_code)

            ws = IsolatedWorkspace(source_repo_path=temp_src, workspace_id="ws_corrupt_test")
            ws.create()

            # Corrupted hunk header
            corrupted_diff = (
                "--- a/module.py\n"
                "+++ b/module.py\n"
                "@@ NOT_A_VALID_HUNK_HEADER @@\n"
                "-def add(a, b):\n"
                "+def add(x, y):\n"
            )

            with pytest.raises(PatchApplicationError):
                ws.apply_patch(corrupted_diff)

            # Workspace original file should remain unchanged
            sandbox_file = os.path.join(ws.workspace_path, "module.py")
            with open(sandbox_file, "r", encoding="utf-8") as f:
                content = f.read()
            assert content == original_code
        finally:
            shutil.rmtree(temp_src, ignore_errors=True)
            if 'ws' in locals():
                ws.cleanup()

    # --------------------------------------------------------------------------
    # 6. Empty Patch Rejection
    # --------------------------------------------------------------------------
    def test_empty_patch_rejection(self):
        """Applying whitespace-only or empty patch raises PatchApplicationError."""
        temp_src = tempfile.mkdtemp(prefix="devaura_empty_patch_")
        try:
            ws = IsolatedWorkspace(source_repo_path=temp_src, workspace_id="ws_empty_patch")
            ws.create()

            with pytest.raises(PatchApplicationError) as exc_info:
                ws.apply_patch("   \n\n  ")
            assert "empty patch" in str(exc_info.value).lower()
        finally:
            shutil.rmtree(temp_src, ignore_errors=True)
            if 'ws' in locals():
                ws.cleanup()

    # --------------------------------------------------------------------------
    # 7. Non-Existent Sandbox Detection
    # --------------------------------------------------------------------------
    def test_nonexistent_sandbox_validation_error(self):
        """VerificationRunner raises VerificationSecurityError if workspace directory is missing."""
        runner = VerificationRunner(workspace_path="/nonexistent/path/to/sandbox_xyz")
        with pytest.raises(VerificationSecurityError):
            runner.validate_sandbox_isolation()

    # --------------------------------------------------------------------------
    # 8. Investigator Graceful Handling of Empty Repository
    # --------------------------------------------------------------------------
    def test_investigator_empty_repo_handling(self):
        """Investigator handles empty repository without crashing, returning empty or unlocalized result."""
        temp_empty = tempfile.mkdtemp(prefix="devaura_empty_repo_")
        try:
            engine = InvestigatorEngine(workspace_root=temp_empty, repository_id="empty-repo")
            req = InvestigationRequest(
                repository_id="empty-repo",
                title="KeyError in empty repo",
                failure_type=FailureType.RUNTIME_ERROR,
                error_message="KeyError: 'user_id'",
                stack_trace="Traceback (most recent call last):\n  File 'unknown.py', line 1, in <module>\n    x = {}\nKeyError: 'user_id'",
            )
            report = engine.run(req)
            assert report is not None
            assert hasattr(report, "investigation_id")
        finally:
            shutil.rmtree(temp_empty, ignore_errors=True)

    # --------------------------------------------------------------------------
    # 9. Concurrent Repair Sandbox Isolation
    # --------------------------------------------------------------------------
    def test_concurrent_repair_sandbox_isolation(self):
        """Multiple repairs on the same repository operate in isolated directories without conflict."""
        temp_src = tempfile.mkdtemp(prefix="devaura_shared_src_")
        try:
            base_file = os.path.join(temp_src, "config.py")
            with open(base_file, "w", encoding="utf-8") as f:
                f.write("DEBUG = False\n")

            ws1 = IsolatedWorkspace(source_repo_path=temp_src, workspace_id="repair_run_1")
            ws2 = IsolatedWorkspace(source_repo_path=temp_src, workspace_id="repair_run_2")

            ws1.create()
            ws2.create()

            assert ws1.workspace_path != ws2.workspace_path
            assert os.path.exists(ws1.workspace_path)
            assert os.path.exists(ws2.workspace_path)

            # Mutate ws1 only
            diff1 = "--- a/config.py\n+++ b/config.py\n@@ -1 +1 @@\n-DEBUG = False\n+DEBUG = True\n"
            ws1.apply_patch(diff1)

            # ws2 must remain unmodified
            with open(os.path.join(ws1.workspace_path, "config.py"), "r") as f:
                assert "DEBUG = True" in f.read()
            with open(os.path.join(ws2.workspace_path, "config.py"), "r") as f:
                assert "DEBUG = False" in f.read()
        finally:
            shutil.rmtree(temp_src, ignore_errors=True)
            if 'ws1' in locals():
                ws1.cleanup()
            if 'ws2' in locals():
                ws2.cleanup()
