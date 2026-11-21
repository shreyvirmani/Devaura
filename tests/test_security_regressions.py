"""Devaura Security & Safety Regression Test Suite (Phase 8).

Strictly asserts zero safety violations across 7 critical attack surfaces:
1. Sensitive file blocking (.env, .pem, .key, id_rsa, credentials, secrets)
2. Path traversal blocking (../../, ..\\..\\, absolute sensitive paths)
3. Approval bypass blocking (apply, retry, and PR without human authorization)
4. Post-approval patch tampering detection (PATCH_CHANGED)
5. Base revision mutation & drift detection (BaseRevisionChangedError)
6. Base branch push protection (main, master, release, force-push)
7. Credential & secret leakage redaction in logs, events, and descriptions
"""

import pytest
from agent.events import RedactionFilter, tracker
from agent.pr.approval_gate import HumanPRApprovalGate, PRApprovalRequiredError
from agent.pr.context_builder import PRContextBuilder
from agent.pr.git_manager import GitStateManager
from agent.repair.approval_gate import ApprovalRequiredError, HumanApprovalGate, PatchIntegrityError
from agent.repair.patch_generator import PatchScopeGuard, ScopeViolationError
from agent.repair.state_machine import RepairStateMachine
from agent.repair.models import ApprovalStatus, PatchRiskLevel, RepairState
from integrations.github.client import GitHubClient
from integrations.github.mock_provider import MockGitProvider
from integrations.github.provider import BaseRevisionChangedError, SecurityBlockError


class TestSecurityRegressions:
    """Rigorous defensive assertion suite."""

    # --------------------------------------------------------------------------
    # 1. Sensitive Files
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("bad_file", [
        ".env",
        ".env.production",
        "certs/server.pem",
        "keys/private.key",
        "id_rsa",
        "id_ed25519",
        "credentials.json",
        "config/secrets.yaml",
    ])
    def test_sensitive_file_blocking_in_patch_scope(self, bad_file):
        """Sensitive files are strictly forbidden from patch inclusion."""
        guard = PatchScopeGuard(allowed_files=["app/main.py", bad_file])
        with pytest.raises(ScopeViolationError):
            guard.validate_patch(
                file_path=bad_file,
                unified_diff=f"--- a/{bad_file}\n+++ b/{bad_file}\n@@ -1 +1 @@\n-secret\n+leaked\n",
            )

    # --------------------------------------------------------------------------
    # 2. Path Traversal
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("traversal_path", [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "app/../../../sensitive.txt",
        "/etc/shadow",
        "C:\\Windows\\System32\\cmd.exe",
    ])
    def test_path_traversal_blocking(self, traversal_path):
        """Path traversal and escape attempts are blocked."""
        guard = PatchScopeGuard(allowed_files=["app/main.py"])
        with pytest.raises(ScopeViolationError):
            guard.validate_file_path(traversal_path)

    # --------------------------------------------------------------------------
    # 3. Approval Bypass
    # --------------------------------------------------------------------------
    def test_approval_bypass_blocked_for_patch_application(self):
        """Applying a patch without valid human approval is blocked."""
        gate = HumanApprovalGate()
        diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-1\n+2\n"

        # Attempt with unapproved status
        from agent.repair.models import RepairApproval
        unapproved = RepairApproval(
            repair_id="rep-1",
            patch_hash=gate.compute_patch_hash(diff),
            approved_by="pending-user",
            status=ApprovalStatus.PENDING,
            approval_token="unapproved_token",
        )
        with pytest.raises(ApprovalRequiredError):
            gate.verify_authorization(unapproved, diff)

    def test_approval_bypass_blocked_for_pr_creation(self):
        """PR authorization requires explicit human identity."""
        pr_gate = HumanPRApprovalGate()
        with pytest.raises(PRApprovalRequiredError):
            pr_gate.create_approval(
                repair_id="rep-1",
                patch_hash="abc",
                base_revision="HEAD",
                repair_branch="devaura/repair/rep-1",
                repository="devaura/repo",
                user_identity="devaura-agent",
            )

    # --------------------------------------------------------------------------
    # 4. Post-Approval Patch Tampering
    # --------------------------------------------------------------------------
    def test_patch_tampering_detected(self):
        """Any modification to patch after human approval is detected and rejected."""
        gate = HumanApprovalGate()
        diff_approved = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-1\n+2\n"
        diff_tampered = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-1\n+3\n"

        approval = gate.create_approval("rep-1", diff_approved, "engineer@devaura.ai")
        with pytest.raises(PatchIntegrityError):
            gate.verify_authorization(approval, diff_tampered)

    # --------------------------------------------------------------------------
    # 5. Base Revision Mutation & Drift
    # --------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_base_revision_mutation_blocked(self):
        """Remote base revision divergence halts PR creation with BaseRevisionChangedError."""
        provider = MockGitProvider(initial_default_branch_sha="original_sha_000")
        provider.simulate_base_revision_divergence("shreyvirmani", "Devaura", "drifted_remote_sha_999")

        from integrations.github.models import PullRequestPayload
        payload = PullRequestPayload(
            owner="shreyvirmani",
            repo="Devaura",
            title="fix",
            body="fix",
            head_branch="devaura/repair/12345678",
            base_branch="main",
        )
        with pytest.raises(BaseRevisionChangedError) as exc_info:
            await provider.create_pull_request(payload)
        assert exc_info.value.remote_sha == "drifted_remote_sha_999"

    # --------------------------------------------------------------------------
    # 6. Protected Branch Protection
    # --------------------------------------------------------------------------
    @pytest.mark.parametrize("protected_branch", [
        "main",
        "master",
        "release",
        "release/v1.0",
        "production",
    ])
    @pytest.mark.asyncio
    async def test_protected_branch_push_blocked(self, protected_branch):
        """Direct push to protected branches is unconditionally blocked."""
        provider = MockGitProvider()
        with pytest.raises(SecurityBlockError):
            await provider.push_branch(
                owner="shreyvirmani",
                repo="Devaura",
                branch_name=protected_branch,
                commit_sha="any_sha",
            )

    # --------------------------------------------------------------------------
    # 7. Secret Redaction & Leakage Audit
    # --------------------------------------------------------------------------
    def test_credential_redaction_filter(self):
        """Secrets, private keys, and tokens are scrubbed from event metadata."""
        dirty_payload = {
            "github_token": "ghp_1234567890abcdef1234567890abcdef",
            "pr_token": "pr-auth-abcdef1234567890abcdef1234567890",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----",
            "normal_field": "safe_information",
            "nested": {
                "api_key": "secret_key_value_here",
                "status": "OK",
            },
        }
        clean_payload = RedactionFilter.redact_data(dirty_payload)

        # Assert no sensitive tokens survive in cleartext
        clean_str = str(clean_payload)
        assert "ghp_1234567890" not in clean_str
        assert "pr-auth-" not in clean_str
        assert "BEGIN RSA PRIVATE KEY" not in clean_str
        assert "secret_key_value_here" not in clean_str
        assert clean_payload["normal_field"] == "safe_information"
        assert clean_payload["nested"]["status"] == "OK"
